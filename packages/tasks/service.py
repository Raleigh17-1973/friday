from __future__ import annotations

import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_id() -> str:
    return f"task_{uuid.uuid4().hex[:12]}"


PRIORITY_ORDER = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
STATUS_VALUES = {"open", "in_progress", "done", "cancelled"}
PRIORITY_VALUES = {"low", "medium", "high", "urgent"}


@dataclass
class Task:
    task_id: str
    title: str
    description: str = ""
    assignee: str | None = None
    due_date: str | None = None          # ISO date string e.g. "2026-03-20"
    priority: str = "medium"             # low / medium / high / urgent
    status: str = "open"                 # open / in_progress / done / cancelled
    workspace_id: str | None = None
    okr_id: str | None = None
    kr_id: str | None = None
    process_id: str | None = None
    initiative_id: str | None = None
    created_by: str = "system"
    created_at: str = field(default_factory=_utc_now)
    updated_at: str = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskService:
    """SQLite-backed task management with OKR / process linkage."""

    _CREATE_SQL = """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id        TEXT PRIMARY KEY,
        title          TEXT NOT NULL,
        description    TEXT NOT NULL DEFAULT '',
        assignee       TEXT,
        due_date       TEXT,
        priority       TEXT NOT NULL DEFAULT 'medium',
        status         TEXT NOT NULL DEFAULT 'open',
        workspace_id   TEXT,
        okr_id         TEXT,
        kr_id          TEXT,
        process_id     TEXT,
        initiative_id  TEXT,
        created_by     TEXT NOT NULL DEFAULT 'system',
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_tasks_assignee   ON tasks(assignee);
    CREATE INDEX IF NOT EXISTS idx_tasks_workspace  ON tasks(workspace_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_status     ON tasks(status);
    CREATE INDEX IF NOT EXISTS idx_tasks_due_date   ON tasks(due_date);
    """

    def __init__(self, db_path: Path | None = None) -> None:
        path = str(db_path) if db_path else ":memory:"
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._CREATE_SQL)
        self._conn.commit()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(**dict(row))

    # ── CRUD ─────────────────────────────────────────────────────────────────

    def create(
        self,
        title: str,
        description: str = "",
        assignee: str | None = None,
        due_date: str | None = None,
        priority: str = "medium",
        status: str = "open",
        workspace_id: str | None = None,
        okr_id: str | None = None,
        kr_id: str | None = None,
        process_id: str | None = None,
        initiative_id: str | None = None,
        created_by: str = "system",
        task_id: str | None = None,
    ) -> Task:
        now = _utc_now()
        tid = task_id or _task_id()
        priority = priority if priority in PRIORITY_VALUES else "medium"
        status = status if status in STATUS_VALUES else "open"
        task = Task(
            task_id=tid,
            title=title,
            description=description,
            assignee=assignee,
            due_date=due_date,
            priority=priority,
            status=status,
            workspace_id=workspace_id,
            okr_id=okr_id,
            kr_id=kr_id,
            process_id=process_id,
            initiative_id=initiative_id,
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        self._conn.execute(
            """INSERT INTO tasks
               (task_id, title, description, assignee, due_date, priority, status,
                workspace_id, okr_id, kr_id, process_id, initiative_id, created_by,
                created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                task.task_id, task.title, task.description, task.assignee,
                task.due_date, task.priority, task.status, task.workspace_id,
                task.okr_id, task.kr_id, task.process_id, task.initiative_id,
                task.created_by, task.created_at, task.updated_at,
            ),
        )
        self._conn.commit()
        return task

    def get(self, task_id: str) -> Task | None:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE task_id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def update(self, task_id: str, **changes: Any) -> Task | None:
        """Update arbitrary fields. Returns updated task or None if not found."""
        allowed = {
            "title", "description", "assignee", "due_date", "priority",
            "status", "workspace_id", "okr_id", "kr_id", "process_id",
            "initiative_id",
        }
        fields = {k: v for k, v in changes.items() if k in allowed}
        if not fields:
            return self.get(task_id)
        if "priority" in fields and fields["priority"] not in PRIORITY_VALUES:
            fields["priority"] = "medium"
        if "status" in fields and fields["status"] not in STATUS_VALUES:
            fields["status"] = "open"
        fields["updated_at"] = _utc_now()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        self._conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE task_id = ?",
            (*fields.values(), task_id),
        )
        self._conn.commit()
        return self.get(task_id)

    def delete(self, task_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ── Queries ───────────────────────────────────────────────────────────────

    def list(
        self,
        assignee: str | None = None,
        workspace_id: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        due_before: str | None = None,   # ISO date string
        okr_id: str | None = None,
        limit: int = 200,
    ) -> list[Task]:
        clauses: list[str] = []
        params: list[Any] = []

        if assignee is not None:
            clauses.append("assignee = ?")
            params.append(assignee)
        if workspace_id is not None:
            clauses.append("workspace_id = ?")
            params.append(workspace_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        if priority is not None:
            clauses.append("priority = ?")
            params.append(priority)
        if due_before is not None:
            clauses.append("due_date IS NOT NULL AND due_date <= ?")
            params.append(due_before)
        if okr_id is not None:
            clauses.append("okr_id = ?")
            params.append(okr_id)

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        rows = self._conn.execute(
            f"SELECT * FROM tasks {where} ORDER BY due_date ASC, updated_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def overdue(self) -> list[Task]:
        """Tasks that are past due and not done/cancelled."""
        today = datetime.now(timezone.utc).date().isoformat()
        rows = self._conn.execute(
            """SELECT * FROM tasks
               WHERE due_date IS NOT NULL
                 AND due_date < ?
                 AND status NOT IN ('done','cancelled')
               ORDER BY due_date ASC""",
            (today,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def due_soon(self, days: int = 7) -> list[Task]:
        """Tasks due within the next N days and not done/cancelled."""
        from datetime import timedelta
        today = datetime.now(timezone.utc).date()
        cutoff = (today + timedelta(days=days)).isoformat()
        today_str = today.isoformat()
        rows = self._conn.execute(
            """SELECT * FROM tasks
               WHERE due_date IS NOT NULL
                 AND due_date >= ?
                 AND due_date <= ?
                 AND status NOT IN ('done','cancelled')
               ORDER BY due_date ASC""",
            (today_str, cutoff),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def count_by_status(self, workspace_id: str | None = None) -> dict[str, int]:
        """Returns {status: count} for the given workspace (or all)."""
        if workspace_id:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) as n FROM tasks WHERE workspace_id = ? GROUP BY status",
                (workspace_id,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT status, COUNT(*) as n FROM tasks GROUP BY status"
            ).fetchall()
        return {r["status"]: r["n"] for r in rows}
