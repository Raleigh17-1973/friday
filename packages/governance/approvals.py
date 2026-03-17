from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

from packages.common.models import ApprovalRequest


class ApprovalService:
    def __init__(self, db_path: Path | None = None) -> None:
        self._store: dict[str, ApprovalRequest] = {}
        self._by_run: dict[str, list[str]] = defaultdict(list)
        self._db: sqlite3.Connection | None = None
        if db_path is not None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._db = sqlite3.connect(str(db_path), check_same_thread=False)
            self._ensure_schema()
            self._load_from_db()

    def _approval_payload(self, req: ApprovalRequest) -> dict:
        return {
            "approval_id": req.approval_id,
            "run_id": req.run_id,
            "reason": req.reason,
            "action_summary": req.action_summary,
            "requested_scopes": req.requested_scopes,
            "created_at": req.created_at,
            "status": req.status,
            "assignee": req.assignee,
        }

    def _ensure_schema(self) -> None:
        if self._db is None:
            return
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS approvals ("
            "approval_id TEXT PRIMARY KEY, run_id TEXT, data TEXT NOT NULL)"
        )
        columns = {
            str(row[1])
            for row in self._db.execute("PRAGMA table_info(approvals)")
        }
        if "data" not in columns:
            self._db.execute("ALTER TABLE approvals ADD COLUMN data TEXT")
            columns.add("data")

        legacy_columns = {
            "approval_id",
            "run_id",
            "reason",
            "action_summary",
            "requested_scopes",
            "created_at",
            "status",
            "assignee",
        }
        if legacy_columns.intersection(columns):
            select_columns = [name for name in legacy_columns if name in columns]
            if select_columns:
                query = (
                    "SELECT approval_id, run_id, data, "
                    + ", ".join(select_columns)
                    + " FROM approvals"
                )
                for row in self._db.execute(query):
                    approval_id = row[0]
                    run_id = row[1]
                    data = row[2]
                    if data:
                        continue
                    offset = 3
                    legacy_data = {
                        column: row[offset + index]
                        for index, column in enumerate(select_columns)
                    }
                    payload = {
                        "approval_id": legacy_data.get("approval_id") or approval_id,
                        "run_id": legacy_data.get("run_id") or run_id or "",
                        "reason": legacy_data.get("reason") or "",
                        "action_summary": legacy_data.get("action_summary") or "",
                        "requested_scopes": json.loads(legacy_data["requested_scopes"])
                        if isinstance(legacy_data.get("requested_scopes"), str)
                        else (legacy_data.get("requested_scopes") or []),
                        "created_at": legacy_data.get("created_at") or "",
                        "status": legacy_data.get("status") or "pending",
                        "assignee": legacy_data.get("assignee"),
                    }
                    self._db.execute(
                        "UPDATE approvals SET data = ? WHERE approval_id = ?",
                        (json.dumps(payload), approval_id),
                    )
        self._db.commit()

    def _load_from_db(self) -> None:
        if self._db is None:
            return
        for row in self._db.execute("SELECT data FROM approvals"):
            data = json.loads(row[0])
            req = ApprovalRequest(
                approval_id=data["approval_id"],
                run_id=data["run_id"],
                reason=data["reason"],
                action_summary=data["action_summary"],
                requested_scopes=data["requested_scopes"],
                created_at=data.get("created_at", ""),
                status=data.get("status", "pending"),
                assignee=data.get("assignee"),
            )
            self._store[req.approval_id] = req
            self._by_run[req.run_id].append(req.approval_id)

    def _persist(self, req: ApprovalRequest) -> None:
        if self._db is None:
            return
        data = json.dumps(self._approval_payload(req))
        self._db.execute(
            "INSERT OR REPLACE INTO approvals (approval_id, run_id, data) VALUES (?, ?, ?)",
            (req.approval_id, req.run_id, data),
        )
        self._db.commit()

    def create(self, req: ApprovalRequest) -> ApprovalRequest:
        self._store[req.approval_id] = req
        self._by_run[req.run_id].append(req.approval_id)
        self._persist(req)
        return req

    def approve(self, approval_id: str) -> ApprovalRequest:
        req = self._store[approval_id]
        req.status = "approved"
        self._persist(req)
        return req

    def reject(self, approval_id: str) -> ApprovalRequest:
        req = self._store[approval_id]
        req.status = "rejected"
        self._persist(req)
        return req

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._store[approval_id]

    def assign(self, approval_id: str, assignee: str) -> ApprovalRequest:
        """Phase 9: Assign a reviewer to an approval request."""
        req = self._store[approval_id]
        req.assignee = assignee
        self._persist(req)
        return req

    def list_pending(self) -> list[ApprovalRequest]:
        return [r for r in self._store.values() if r.status == "pending"]

    def list_for_assignee(self, assignee: str) -> list[ApprovalRequest]:
        """Phase 9: Return all approvals assigned to a specific reviewer."""
        return [r for r in self._store.values() if r.assignee == assignee]

    def list_all(self) -> list[ApprovalRequest]:
        return list(self._store.values())
