from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _notif_id() -> str:
    return f"notif_{uuid.uuid4().hex[:12]}"


VALID_TYPES = {
    "approval_required",
    "task_assigned",
    "okr_checkin_due",
    "alert",
    "mention",
    "general",
}


@dataclass
class Notification:
    notification_id: str
    recipient_id: str
    type: str                           # approval_required / task_assigned / okr_checkin_due / alert / general
    title: str
    body: str
    entity_type: str | None = None      # "approval", "task", "objective", etc.
    entity_id: str | None = None        # ID of the linked entity
    read: bool = False
    created_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["read"] = bool(d["read"])
        return d


class NotificationService:
    """SQLite-backed in-app notification system."""

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id TEXT PRIMARY KEY,
        recipient_id    TEXT NOT NULL,
        type            TEXT NOT NULL DEFAULT 'general',
        title           TEXT NOT NULL,
        body            TEXT NOT NULL DEFAULT '',
        entity_type     TEXT,
        entity_id       TEXT,
        read            INTEGER NOT NULL DEFAULT 0,
        created_at      TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_notif_recipient ON notifications(recipient_id, read, created_at);
    """

    def __init__(self, db_path: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._CREATE_SQL)
        self._conn.commit()

    def _row_to_notif(self, row: sqlite3.Row) -> Notification:
        d = dict(row)
        d["read"] = bool(d["read"])
        return Notification(**d)

    # ── Create ────────────────────────────────────────────────────────────────

    def create(
        self,
        recipient_id: str,
        title: str,
        body: str = "",
        type: str = "general",
        entity_type: str | None = None,
        entity_id: str | None = None,
    ) -> Notification:
        notif = Notification(
            notification_id=_notif_id(),
            recipient_id=recipient_id,
            type=type if type in VALID_TYPES else "general",
            title=title,
            body=body,
            entity_type=entity_type,
            entity_id=entity_id,
            read=False,
            created_at=_utc_now(),
        )
        self._conn.execute(
            """INSERT INTO notifications
               (notification_id, recipient_id, type, title, body, entity_type, entity_id, read, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                notif.notification_id, notif.recipient_id, notif.type,
                notif.title, notif.body, notif.entity_type, notif.entity_id,
                int(notif.read), notif.created_at,
            ),
        )
        self._conn.commit()
        return notif

    # ── Read ──────────────────────────────────────────────────────────────────

    def list(
        self,
        recipient_id: str,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        if unread_only:
            rows = self._conn.execute(
                "SELECT * FROM notifications WHERE recipient_id = ? AND read = 0 ORDER BY created_at DESC LIMIT ?",
                (recipient_id, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM notifications WHERE recipient_id = ? ORDER BY created_at DESC LIMIT ?",
                (recipient_id, limit),
            ).fetchall()
        return [self._row_to_notif(r) for r in rows]

    def count_unread(self, recipient_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as n FROM notifications WHERE recipient_id = ? AND read = 0",
            (recipient_id,),
        ).fetchone()
        return int(row["n"]) if row else 0

    # ── Mark read ─────────────────────────────────────────────────────────────

    def mark_read(self, notification_id: str) -> bool:
        cur = self._conn.execute(
            "UPDATE notifications SET read = 1 WHERE notification_id = ?",
            (notification_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def mark_all_read(self, recipient_id: str) -> int:
        cur = self._conn.execute(
            "UPDATE notifications SET read = 1 WHERE recipient_id = ? AND read = 0",
            (recipient_id,),
        )
        self._conn.commit()
        return cur.rowcount

    # ── Delete ────────────────────────────────────────────────────────────────

    def delete(self, notification_id: str) -> bool:
        cur = self._conn.execute(
            "DELETE FROM notifications WHERE notification_id = ?",
            (notification_id,),
        )
        self._conn.commit()
        return cur.rowcount > 0
