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
