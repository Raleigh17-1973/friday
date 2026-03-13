from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class MemoryRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists semantic_memories (
                  org_id text not null,
                  memory_key text not null,
                  memory_value text not null,
                  primary key(org_id, memory_key)
                );

                create table if not exists episodic_memories (
                  id integer primary key autoincrement,
                  org_id text not null,
                  run_id text not null,
                  event_json text not null,
                  created_at text default current_timestamp
                );

                create table if not exists memory_candidates (
                  candidate_id text primary key,
                  run_id text not null,
                  org_id text not null,
                  candidate_type text not null,
                  content text not null,
                  risk_level text not null,
                  auto_accepted integer not null,
                  promoted integer not null default 0,
                  approval_required integer not null default 0,
                  created_at text default current_timestamp
                );
                """
            )

    def upsert_semantic(self, org_id: str, facts: dict[str, Any]) -> None:
        with self._connect() as conn:
            for key, value in facts.items():
                conn.execute(
                    """
                    insert into semantic_memories(org_id, memory_key, memory_value)
                    values (?, ?, ?)
                    on conflict(org_id, memory_key)
                    do update set memory_value = excluded.memory_value
                    """,
                    (org_id, key, json.dumps(value)),
                )

    def get_semantic(self, org_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                "select memory_key, memory_value from semantic_memories where org_id = ?",
                (org_id,),
            ).fetchall()
        return {row["memory_key"]: json.loads(row["memory_value"]) for row in rows}

    def add_episode(self, org_id: str, run_id: str, event: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                "insert into episodic_memories(org_id, run_id, event_json) values (?, ?, ?)",
                (org_id, run_id, json.dumps(event)),
            )

    def get_episodes(self, org_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                select event_json from episodic_memories
                where org_id = ?
                order by id desc
                limit ?
                """,
                (org_id, limit),
            ).fetchall()
        return [json.loads(row["event_json"]) for row in rows]

    def save_candidate(
        self,
        *,
        candidate_id: str,
        run_id: str,
        org_id: str,
        candidate_type: str,
        content: dict[str, Any],
        risk_level: str,
        auto_accepted: bool,
        approval_required: bool,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into memory_candidates(
                    candidate_id, run_id, org_id, candidate_type, content,
                    risk_level, auto_accepted, promoted, approval_required
                ) values (?, ?, ?, ?, ?, ?, ?, coalesce((select promoted from memory_candidates where candidate_id=?),0), ?)
                """,
                (
                    candidate_id,
                    run_id,
                    org_id,
                    candidate_type,
                    json.dumps(content),
                    risk_level,
                    1 if auto_accepted else 0,
                    candidate_id,
                    1 if approval_required else 0,
                ),
            )

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                select candidate_id, run_id, org_id, candidate_type, content,
                       risk_level, auto_accepted, promoted, approval_required
                from memory_candidates where candidate_id = ?
                """,
                (candidate_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "candidate_id": row["candidate_id"],
            "run_id": row["run_id"],
            "org_id": row["org_id"],
            "candidate_type": row["candidate_type"],
            "content": json.loads(row["content"]),
            "risk_level": row["risk_level"],
            "auto_accepted": bool(row["auto_accepted"]),
            "promoted": bool(row["promoted"]),
            "approval_required": bool(row["approval_required"]),
        }

    def mark_candidate_promoted(self, candidate_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "update memory_candidates set promoted = 1 where candidate_id = ?",
                (candidate_id,),
            )

    # ------------------------------------------------------------------
    # Vector search stubs — no-op for SQLite, overridden in Postgres
    # ------------------------------------------------------------------

    def store_embedding(
        self, org_id: str, content_key: str, text: str, embedding: list[float]
    ) -> None:
        """Store an embedding vector alongside content. No-op on SQLite."""

    def vector_search(
        self, org_id: str, embedding: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Return top-k semantically similar records. Returns [] on SQLite."""
        return []


# ---------------------------------------------------------------------------
# Postgres + pgvector repository
# ---------------------------------------------------------------------------

class PostgresMemoryRepository(MemoryRepository):
    """Full-featured memory repository backed by Postgres with pgvector.

    Activate by setting the FRIDAY_MEMORY_DATABASE_URL environment variable
    to a PostgreSQL DSN (e.g. ``postgresql://user:pass@host:5432/friday``).

    Requires ``psycopg[binary]>=3.1`` (already in the ``phase3`` optional dep
    group) and a Postgres server with the pgvector extension installed:
        ``CREATE EXTENSION IF NOT EXISTS vector;``

    Supabase provides pgvector out of the box on its free tier.
    """

    def __init__(self, dsn: str) -> None:
        try:
            import psycopg  # type: ignore[import]
        except ModuleNotFoundError as exc:  # pragma: no cover
            raise RuntimeError(
                "psycopg is required for PostgresMemoryRepository. "
                "Run: pip install 'psycopg[binary]>=3.1'"
            ) from exc

        self._psycopg = psycopg
        self._dsn = dsn
        self._init_postgres()

    # Override parent init — no SQLite setup needed
    def _connect(self):  # type: ignore[override]
        return self._psycopg.connect(self._dsn)

    def _init_postgres(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                # Enable pgvector if not already enabled
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS semantic_memories (
                        org_id     text NOT NULL,
                        memory_key text NOT NULL,
                        memory_value text NOT NULL,
                        PRIMARY KEY (org_id, memory_key)
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS episodic_memories (
                        id         bigserial PRIMARY KEY,
                        org_id     text NOT NULL,
                        run_id     text NOT NULL,
                        event_json jsonb NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_candidates (
                        candidate_id     text PRIMARY KEY,
                        run_id           text NOT NULL,
                        org_id           text NOT NULL,
                        candidate_type   text NOT NULL,
                        content          jsonb NOT NULL,
                        risk_level       text NOT NULL,
                        auto_accepted    boolean NOT NULL DEFAULT false,
                        promoted         boolean NOT NULL DEFAULT false,
                        approval_required boolean NOT NULL DEFAULT false,
                        created_at       timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_embeddings (
                        id           bigserial PRIMARY KEY,
                        org_id       text NOT NULL,
                        content_key  text NOT NULL,
                        content_text text NOT NULL,
                        embedding    vector(1536),
                        metadata     jsonb,
                        created_at   timestamptz NOT NULL DEFAULT now(),
                        UNIQUE (org_id, content_key)
                    )
                    """
                )
                # IVFFlat index for fast ANN search (skipped if already exists)
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS memory_embeddings_vec_idx
                    ON memory_embeddings USING ivfflat (embedding vector_cosine_ops)
                    WITH (lists = 50)
                    """
                )
            conn.commit()

    # ---- Semantic memories ----

    def upsert_semantic(self, org_id: str, facts: dict[str, Any]) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                for key, value in facts.items():
                    cur.execute(
                        """
                        INSERT INTO semantic_memories(org_id, memory_key, memory_value)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (org_id, memory_key)
                        DO UPDATE SET memory_value = excluded.memory_value
                        """,
                        (org_id, key, json.dumps(value)),
                    )
            conn.commit()

    def get_semantic(self, org_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT memory_key, memory_value FROM semantic_memories WHERE org_id = %s",
                    (org_id,),
                )
                rows = cur.fetchall()
        return {row[0]: json.loads(row[1]) for row in rows}

    # ---- Episodic memories ----

    def add_episode(self, org_id: str, run_id: str, event: dict[str, Any]) -> None:
        from psycopg.types.json import Jsonb  # type: ignore[import]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO episodic_memories(org_id, run_id, event_json) VALUES (%s, %s, %s)",
                    (org_id, run_id, Jsonb(event)),
                )
            conn.commit()

    def get_episodes(self, org_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_json FROM episodic_memories
                    WHERE org_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                rows = cur.fetchall()
        out = []
        for row in rows:
            v = row[0]
            out.append(dict(v) if not isinstance(v, dict) else v)
        return out

    # ---- Candidates ----

    def save_candidate(
        self,
        *,
        candidate_id: str,
        run_id: str,
        org_id: str,
        candidate_type: str,
        content: dict[str, Any],
        risk_level: str,
        auto_accepted: bool,
        approval_required: bool,
    ) -> None:
        from psycopg.types.json import Jsonb  # type: ignore[import]

        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_candidates(
                        candidate_id, run_id, org_id, candidate_type, content,
                        risk_level, auto_accepted, approval_required
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (candidate_id) DO UPDATE
                        SET content = excluded.content,
                            risk_level = excluded.risk_level
                    """,
                    (
                        candidate_id, run_id, org_id, candidate_type,
                        Jsonb(content), risk_level, auto_accepted, approval_required,
                    ),
                )
            conn.commit()

    def get_candidate(self, candidate_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT candidate_id, run_id, org_id, candidate_type, content,
                           risk_level, auto_accepted, promoted, approval_required
                    FROM memory_candidates WHERE candidate_id = %s
                    """,
                    (candidate_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        content = row[4]
        return {
            "candidate_id": row[0],
            "run_id": row[1],
            "org_id": row[2],
            "candidate_type": row[3],
            "content": dict(content) if not isinstance(content, dict) else content,
            "risk_level": row[5],
            "auto_accepted": bool(row[6]),
            "promoted": bool(row[7]),
            "approval_required": bool(row[8]),
        }

    def mark_candidate_promoted(self, candidate_id: str) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE memory_candidates SET promoted = true WHERE candidate_id = %s",
                    (candidate_id,),
                )
            conn.commit()

    # ---- Vector / embedding methods ----

    def store_embedding(
        self, org_id: str, content_key: str, text: str, embedding: list[float]
    ) -> None:
        """Upsert an embedding vector for a piece of content."""
        # Format as Postgres vector literal: '[0.1, 0.2, ...]'
        vec_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO memory_embeddings(org_id, content_key, content_text, embedding)
                    VALUES (%s, %s, %s, %s::vector)
                    ON CONFLICT (org_id, content_key)
                    DO UPDATE SET content_text = excluded.content_text,
                                  embedding    = excluded.embedding
                    """,
                    (org_id, content_key, text[:4000], vec_str),
                )
            conn.commit()

    def vector_search(
        self, org_id: str, embedding: list[float], top_k: int = 5
    ) -> list[dict[str, Any]]:
        """Return top-k records by cosine similarity to the given embedding."""
        vec_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content_key, content_text,
                           1 - (embedding <=> %s::vector) AS similarity
                    FROM memory_embeddings
                    WHERE org_id = %s
                      AND embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (vec_str, org_id, vec_str, top_k),
                )
                rows = cur.fetchall()
        return [
            {"content_key": r[0], "content_text": r[1], "similarity": float(r[2])}
            for r in rows
        ]
