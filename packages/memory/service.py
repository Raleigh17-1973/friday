from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.memory.repository import MemoryRepository

_log = logging.getLogger(__name__)


@dataclass
class MemoryBundle:
    working: dict[str, Any]
    conversation: list[dict[str, Any]]
    semantic: dict[str, Any]
    episodic: list[dict[str, Any]]
    procedural: dict[str, Any]


class LayeredMemoryService:
    def __init__(self, *, repository: MemoryRepository | None = None) -> None:
        self._repository = repository
        self._conversation_history: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._semantic_by_org: dict[str, dict[str, Any]] = defaultdict(dict)
        self._episodic_by_org: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._procedural: dict[str, Any] = {
            "approval_rules": ["write actions require explicit approval"],
            "reflection_policy": "governed",
        }
        # In-process cache: sha256(text) → embedding vector
        self._embed_cache: dict[str, list[float]] = {}

    @classmethod
    def with_sqlite(cls, db_path: Path) -> "LayeredMemoryService":
        return cls(repository=MemoryRepository(db_path))

    @classmethod
    def with_postgres(cls, dsn: str) -> "LayeredMemoryService":
        """Return a service backed by Postgres + pgvector.

        Requires ``psycopg[binary]>=3.1`` and a Postgres server with
        the pgvector extension enabled. Supabase provides this for free.
        """
        from packages.memory.repository import PostgresMemoryRepository

        return cls(repository=PostgresMemoryRepository(dsn))

    # ------------------------------------------------------------------
    # Core memory operations
    # ------------------------------------------------------------------

    def load(self, org_id: str, conversation_id: str, working: dict[str, Any]) -> MemoryBundle:
        semantic = dict(self._semantic_by_org[org_id])
        episodic = list(self._episodic_by_org[org_id][-30:])
        if self._repository is not None:
            durable_semantic = self._repository.get_semantic(org_id)
            if durable_semantic:
                semantic.update(durable_semantic)
            durable_episodes = self._repository.get_episodes(org_id, limit=30)
            if durable_episodes:
                episodic = durable_episodes

        return MemoryBundle(
            working=working,
            conversation=list(self._conversation_history[conversation_id][-30:]),
            semantic=semantic,
            episodic=episodic,
            procedural=dict(self._procedural),
        )

    def append_conversation(self, conversation_id: str, event: dict[str, Any]) -> None:
        self._conversation_history[conversation_id].append(event)

    def upsert_semantic(
        self,
        org_id: str,
        facts: dict[str, Any],
        workspace_id: str | None = None,
    ) -> None:
        self._semantic_by_org[org_id].update(facts)
        if self._repository is not None:
            self._repository.upsert_semantic(org_id, facts, workspace_id=workspace_id)
            # Embed each fact so it can be recalled by future queries
            for key, value in facts.items():
                self._store_embedding_async(
                    org_id, f"semantic:{org_id}:{key}", f"{key}: {value}"
                )

    def list_semantic(
        self,
        org_id: str,
        workspace_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Return semantic memories with metadata from the durable repository.

        Falls back to the in-memory store (without metadata) when no repository.
        """
        if self._repository is not None and hasattr(self._repository, "list_semantic"):
            return self._repository.list_semantic(
                org_id, workspace_id=workspace_id, limit=limit, offset=offset
            )
        # In-memory fallback — no workspace filtering, no metadata
        store = self._semantic_by_org.get(org_id, {})
        items = [{"key": k, "value": str(v), "workspace_id": None, "created_at": None, "updated_at": None}
                 for k, v in store.items()]
        return items[offset: offset + limit]

    def list_candidates(self, org_id: str) -> list[dict[str, Any]]:
        """Return pending (unreviewed) memory candidates."""
        if self._repository is not None and hasattr(self._repository, "list_pending_candidates"):
            return self._repository.list_pending_candidates(org_id)
        return []

    def add_episode(self, org_id: str, episode: dict[str, Any], *, run_id: str = "unknown") -> None:
        self._episodic_by_org[org_id].append(episode)
        if self._repository is not None:
            self._repository.add_episode(org_id, run_id, episode)
            # Embed the problem description so it's searchable
            problem = str(episode.get("problem", ""))
            if problem:
                self._store_embedding_async(org_id, f"episode:{run_id}", problem)

    def add_candidate(self, candidate: dict[str, Any], org_id: str) -> None:
        if self._repository is None:
            return
        self._repository.save_candidate(
            candidate_id=str(candidate["candidate_id"]),
            run_id=str(candidate["run_id"]),
            org_id=org_id,
            candidate_type=str(candidate["candidate_type"]),
            content=dict(candidate["content"]),
            risk_level=getattr(candidate["risk_level"], "value", str(candidate["risk_level"])),
            auto_accepted=bool(candidate["auto_accepted"]),
            approval_required=not bool(candidate["auto_accepted"]),
        )

    def promote_candidate(self, candidate_id: str, approved: bool) -> dict[str, Any]:
        if self._repository is None:
            raise KeyError("durable memory repository is not configured")

        candidate = self._repository.get_candidate(candidate_id)
        if candidate is None:
            raise KeyError(candidate_id)

        if candidate["promoted"]:
            return {"status": "already_promoted", "candidate_id": candidate_id}

        if candidate["approval_required"] and not approved:
            return {"status": "approval_required", "candidate_id": candidate_id}

        candidate_type = str(candidate["candidate_type"])
        org_id = str(candidate["org_id"])
        content = dict(candidate["content"])

        if candidate_type in {"user_preference", "business_fact"}:
            self.upsert_semantic(org_id, content)
        elif candidate_type in {"episodic_note", "reusable_lesson", "tool_use_improvement"}:
            self.add_episode(org_id, {"promoted_candidate": candidate_id, **content}, run_id=str(candidate["run_id"]))
        elif candidate_type == "prompt_improvement_proposal":
            self.add_episode(
                org_id,
                {"promoted_candidate": candidate_id, "proposal": content},
                run_id=str(candidate["run_id"]),
            )
        else:
            self.add_episode(org_id, {"promoted_candidate": candidate_id, "content": content}, run_id=str(candidate["run_id"]))

        self._repository.mark_candidate_promoted(candidate_id)
        return {"status": "promoted", "candidate_id": candidate_id, "candidate_type": candidate_type}

    def clear_conversation(self, conversation_id: str) -> None:
        self._conversation_history.pop(conversation_id, None)

    def search(self, org_id: str, query: str) -> dict[str, Any]:
        if self._repository is not None:
            self._semantic_by_org[org_id].update(self._repository.get_semantic(org_id))
            self._episodic_by_org[org_id] = self._repository.get_episodes(org_id, limit=100)

        sem_hits = {
            k: v for k, v in self._semantic_by_org[org_id].items() if query.lower() in f"{k} {v}".lower()
        }
        epi_hits = [item for item in self._episodic_by_org[org_id] if query.lower() in str(item).lower()]
        return {
            "semantic_hits": sem_hits,
            "episodic_hits": epi_hits[-10:],
            "query": query,
        }

    # ------------------------------------------------------------------
    # Semantic recall (RAG)
    # ------------------------------------------------------------------

    def semantic_recall(
        self, org_id: str, query: str, top_k: int = 5,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return top-k semantically similar memories for the given query.

        Uses pgvector cosine similarity when Postgres is configured.
        Falls back to keyword matching on episodic history for SQLite.
        Returns an empty list when no relevant prior context exists.

        Phase 13: When workspace_id is provided, results from the same workspace
        are preferred — workspace-scoped entries are returned first.
        """
        if self._repository is None:
            return []

        # Try vector search first
        embedding = self._embed(query)
        if embedding is not None:
            try:
                results = self._repository.vector_search(org_id, embedding, top_k)
                if results:
                    _log.debug(
                        "semantic_recall: %d vector hits for org=%s", len(results), org_id
                    )
                    if workspace_id:
                        # Boost workspace-scoped entries to the top
                        ws_hits = [r for r in results if r.get("workspace_id") == workspace_id]
                        other_hits = [r for r in results if r.get("workspace_id") != workspace_id]
                        results = (ws_hits + other_hits)[:top_k]
                    return results
            except Exception as exc:
                _log.debug("semantic_recall vector search failed (%s), using keyword fallback", exc)

        # Keyword fallback — works with both SQLite and Postgres
        episodes = self._repository.get_episodes(org_id, limit=100)
        query_lower = query.lower()
        hits = [
            {
                "content_key": f"episode_{i}",
                "content_text": str(ep),
                "similarity": 0.0,
                "workspace_id": ep.get("workspace_id") if isinstance(ep, dict) else None,
            }
            for i, ep in enumerate(episodes)
            if query_lower in str(ep).lower()
        ]
        if workspace_id:
            ws_hits = [h for h in hits if h.get("workspace_id") == workspace_id]
            other_hits = [h for h in hits if h.get("workspace_id") != workspace_id]
            hits = ws_hits + other_hits
        return hits[:top_k]

    # ------------------------------------------------------------------
    # Embedding helpers (best-effort, never block the main flow)
    # ------------------------------------------------------------------

    def _embed(self, text: str) -> list[float] | None:
        """Return a 1536-dim embedding via OpenAI text-embedding-3-small.

        Returns None if OPENAI_API_KEY is not set or the API call fails.
        Results are cached in-process by content hash.
        """
        import os

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return None

        cache_key = hashlib.sha256(text[:8000].encode()).hexdigest()
        if cache_key in self._embed_cache:
            return self._embed_cache[cache_key]

        try:
            import openai  # type: ignore[import]

            client = openai.OpenAI(api_key=api_key)
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input=text[:8000],
            )
            vec: list[float] = response.data[0].embedding
            self._embed_cache[cache_key] = vec
            return vec
        except Exception as exc:
            _log.debug("Embedding call failed: %s", exc)
            return None

    def _store_embedding_async(self, org_id: str, content_key: str, text: str) -> None:
        """Embed text and store in the repository on a daemon thread.

        Failures are logged but never propagated — embedding is best-effort
        and must not slow down the main request path.
        """
        import threading

        def _run() -> None:
            try:
                embedding = self._embed(text)
                if embedding is not None and self._repository is not None:
                    self._repository.store_embedding(org_id, content_key, text, embedding)
            except Exception as exc:
                _log.debug("Background embedding store failed: %s", exc)

        threading.Thread(target=_run, daemon=True).start()
