from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class ActivityEntry:
    activity_id: str
    org_id: str
    actor_id: str          # user or agent who triggered the action
    action: str            # e.g. "task.created", "kr.updated", "okr.checkin"
    entity_type: str       # "task" | "key_result" | "objective" | "initiative" | "process" | …
    entity_id: str
    entity_title: str      # denormalized for cheap display without joins
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # metadata is already a dict from asdict; keep it nested
        return d


class ActivityService:
    """Append-only cross-entity activity log backed by SQLite."""

    VALID_ACTIONS = {
        "task.created", "task.updated", "task.completed", "task.assigned",
        "objective.created", "objective.updated", "objective.completed",
        "kr.created", "kr.updated", "kr.linked_kpi",
        "initiative.created", "initiative.updated",
        "okr.checkin",
        "process.created", "process.updated",
        "decision.logged",
        "notification.sent",
        "generic",
    }

    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or Path("data/friday_activity.sqlite3")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS activity (
                activity_id  TEXT PRIMARY KEY,
                org_id       TEXT NOT NULL,
                actor_id     TEXT NOT NULL DEFAULT 'system',
                action       TEXT NOT NULL,
                entity_type  TEXT NOT NULL,
                entity_id    TEXT NOT NULL,
                entity_title TEXT NOT NULL DEFAULT '',
                metadata     TEXT NOT NULL DEFAULT '{}',
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_activity_org_time
                ON activity (org_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_activity_entity
                ON activity (entity_type, entity_id, created_at DESC);
        """)
        self._conn.commit()

    # ── Write ──────────────────────────────────────────────────────────────

    def log(
        self,
        action: str,
        entity_type: str,
        entity_id: str,
        entity_title: str = "",
        actor_id: str = "system",
        org_id: str = "org-1",
        **metadata: Any,
    ) -> ActivityEntry:
        entry = ActivityEntry(
            activity_id=f"act_{uuid4().hex[:12]}",
            org_id=org_id,
            actor_id=actor_id,
            action=action if action in self.VALID_ACTIONS else "generic",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_title=entity_title,
            metadata=metadata or {},
        )
        self._conn.execute(
            """INSERT INTO activity
               (activity_id, org_id, actor_id, action,
                entity_type, entity_id, entity_title, metadata, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (entry.activity_id, entry.org_id, entry.actor_id, entry.action,
             entry.entity_type, entry.entity_id, entry.entity_title,
             json.dumps(entry.metadata), entry.created_at),
        )
        self._conn.commit()
        return entry

    # ── Read ───────────────────────────────────────────────────────────────

    def list_for_org(
        self,
        org_id: str = "org-1",
        limit: int = 50,
        action_prefix: str | None = None,
        entity_type: str | None = None,
    ) -> list[ActivityEntry]:
        q = "SELECT * FROM activity WHERE org_id = ?"
        params: list[Any] = [org_id]
        if action_prefix:
            q += " AND action LIKE ?"
            params.append(action_prefix.rstrip("%") + "%")
        if entity_type:
            q += " AND entity_type = ?"
            params.append(entity_type)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        rows = self._conn.execute(q, params).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> list[ActivityEntry]:
        rows = self._conn.execute(
            """SELECT * FROM activity
               WHERE entity_type = ? AND entity_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (entity_type, entity_id, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def list_for_actor(
        self,
        actor_id: str,
        org_id: str = "org-1",
        limit: int = 50,
    ) -> list[ActivityEntry]:
        rows = self._conn.execute(
            """SELECT * FROM activity
               WHERE org_id = ? AND actor_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (org_id, actor_id, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    # ── Helper ─────────────────────────────────────────────────────────────

    def _row_to_entry(self, row: sqlite3.Row) -> ActivityEntry:
        return ActivityEntry(
            activity_id=row["activity_id"],
            org_id=row["org_id"],
            actor_id=row["actor_id"],
            action=row["action"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            entity_title=row["entity_title"],
            metadata=json.loads(row["metadata"] or "{}"),
            created_at=row["created_at"],
        )
