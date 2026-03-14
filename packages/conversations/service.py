from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from packages.common.models import utc_now_iso


@dataclass
class ConversationThread:
    thread_id: str
    title: str
    org_id: str
    workspace_id: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConversationMessage:
    message_id: str
    thread_id: str
    role: str  # "user" | "friday" | "status"
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["metadata"] = self.metadata  # keep as dict, not serialized
        return d


class ConversationService:
    """Persistent conversation threads and messages backed by SQLite."""

    def __init__(self, db_path: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversation_threads (
                thread_id   TEXT PRIMARY KEY,
                title       TEXT NOT NULL DEFAULT 'New conversation',
                org_id      TEXT NOT NULL DEFAULT 'org-1',
                workspace_id TEXT,
                created_at  TEXT NOT NULL,
                updated_at  TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conversation_messages (
                message_id   TEXT PRIMARY KEY,
                thread_id    TEXT NOT NULL REFERENCES conversation_threads(thread_id) ON DELETE CASCADE,
                role         TEXT NOT NULL,
                content      TEXT NOT NULL DEFAULT '',
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at   TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_conv_msgs_thread
                ON conversation_messages(thread_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_conv_threads_org
                ON conversation_threads(org_id, updated_at);
        """)
        self._conn.commit()

    # ── Threads ──────────────────────────────────────────────────────────────

    def create_thread(
        self,
        org_id: str = "org-1",
        workspace_id: str | None = None,
        title: str = "New conversation",
        thread_id: str | None = None,
    ) -> ConversationThread:
        now = utc_now_iso()
        tid = thread_id or f"thread_{uuid.uuid4().hex[:12]}"
        thread = ConversationThread(
            thread_id=tid,
            title=title,
            org_id=org_id,
            workspace_id=workspace_id,
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO conversation_threads "
            "(thread_id, title, org_id, workspace_id, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (thread.thread_id, thread.title, thread.org_id, thread.workspace_id, thread.created_at, thread.updated_at),
        )
        self._conn.commit()
        return thread

    def get_thread(self, thread_id: str) -> ConversationThread | None:
        row = self._conn.execute(
            "SELECT * FROM conversation_threads WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        if row is None:
            return None
        return ConversationThread(**dict(row))

    def list_threads(self, org_id: str = "org-1", limit: int = 100) -> list[ConversationThread]:
        rows = self._conn.execute(
            "SELECT * FROM conversation_threads WHERE org_id = ? ORDER BY updated_at DESC LIMIT ?",
            (org_id, limit),
        ).fetchall()
        return [ConversationThread(**dict(r)) for r in rows]

    def rename_thread(self, thread_id: str, title: str) -> ConversationThread | None:
        now = utc_now_iso()
        self._conn.execute(
            "UPDATE conversation_threads SET title = ?, updated_at = ? WHERE thread_id = ?",
            (title, now, thread_id),
        )
        self._conn.commit()
        return self.get_thread(thread_id)

    def delete_thread(self, thread_id: str) -> None:
        self._conn.execute("DELETE FROM conversation_threads WHERE thread_id = ?", (thread_id,))
        self._conn.commit()

    def touch_thread(self, thread_id: str) -> None:
        """Update updated_at to now (called when a new message is added)."""
        self._conn.execute(
            "UPDATE conversation_threads SET updated_at = ? WHERE thread_id = ?",
            (utc_now_iso(), thread_id),
        )
        self._conn.commit()

    # ── Messages ─────────────────────────────────────────────────────────────

    def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
        message_id: str | None = None,
    ) -> ConversationMessage:
        # Auto-create thread if it doesn't exist (handles threads created client-side)
        if not self.get_thread(thread_id):
            self.create_thread(thread_id=thread_id)

        msg = ConversationMessage(
            message_id=message_id or f"msg_{uuid.uuid4().hex[:12]}",
            thread_id=thread_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self._conn.execute(
            "INSERT INTO conversation_messages (message_id, thread_id, role, content, metadata_json, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (msg.message_id, msg.thread_id, msg.role, msg.content, json.dumps(msg.metadata), msg.created_at),
        )
        self.touch_thread(thread_id)
        self._conn.commit()
        return msg

    def get_messages(self, thread_id: str, limit: int = 200) -> list[ConversationMessage]:
        rows = self._conn.execute(
            "SELECT * FROM conversation_messages WHERE thread_id = ? ORDER BY created_at ASC LIMIT ?",
            (thread_id, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            meta = {}
            try:
                meta = json.loads(d.get("metadata_json") or "{}")
            except Exception:
                pass
            result.append(ConversationMessage(
                message_id=d["message_id"],
                thread_id=d["thread_id"],
                role=d["role"],
                content=d["content"],
                metadata=meta,
                created_at=d["created_at"],
            ))
        return result

    def thread_message_count(self, thread_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM conversation_messages WHERE thread_id = ?", (thread_id,)
        ).fetchone()
        return int(row[0]) if row else 0
