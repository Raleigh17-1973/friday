from __future__ import annotations

from collections import defaultdict

from packages.common.models import ApprovalRequest


class ApprovalService:
    def __init__(self) -> None:
        self._store: dict[str, ApprovalRequest] = {}
        self._by_run: dict[str, list[str]] = defaultdict(list)

    def create(self, req: ApprovalRequest) -> ApprovalRequest:
        self._store[req.approval_id] = req
        self._by_run[req.run_id].append(req.approval_id)
        return req

    def approve(self, approval_id: str) -> ApprovalRequest:
        req = self._store[approval_id]
        req.status = "approved"
        return req

    def reject(self, approval_id: str) -> ApprovalRequest:
        req = self._store[approval_id]
        req.status = "rejected"
        return req

    def get(self, approval_id: str) -> ApprovalRequest:
        return self._store[approval_id]
