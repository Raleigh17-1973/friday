from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from packages.memory.repository import MemoryRepository


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

    @classmethod
    def with_sqlite(cls, db_path: Path) -> "LayeredMemoryService":
        return cls(repository=MemoryRepository(db_path))

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

    def upsert_semantic(self, org_id: str, facts: dict[str, Any]) -> None:
        self._semantic_by_org[org_id].update(facts)
        if self._repository is not None:
            self._repository.upsert_semantic(org_id, facts)

    def add_episode(self, org_id: str, episode: dict[str, Any], *, run_id: str = "unknown") -> None:
        self._episodic_by_org[org_id].append(episode)
        if self._repository is not None:
            self._repository.add_episode(org_id, run_id, episode)

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
