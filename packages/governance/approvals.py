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
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS approvals ("
                "approval_id TEXT PRIMARY KEY, run_id TEXT, data TEXT NOT NULL)"
            )
            self._db.commit()
            self._load_from_db()

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
        data = json.dumps({
            "approval_id": req.approval_id,
            "run_id": req.run_id,
            "reason": req.reason,
            "action_summary": req.action_summary,
            "requested_scopes": req.requested_scopes,
            "created_at": req.created_at,
            "status": req.status,
            "assignee": req.assignee,
        })
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
