from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any

from packages.common.models import ProcessDocument
from packages.process.repository import SQLiteProcessRepository
from packages.process.service import _completeness_score


class ProcessAnalytics:
    """Org-level health metrics and per-process completeness breakdowns."""

    def __init__(self, repo: SQLiteProcessRepository) -> None:
        self._repo = repo

    def org_health(self, org_id: str, stale_days: int = 90) -> dict[str, Any]:
        docs = self._repo.list_by_org(org_id)
        if not docs:
            return {
                "total_processes": 0,
                "avg_completeness": 0.0,
                "stale_count": 0,
                "draft_count": 0,
                "active_count": 0,
                "missing_owners_count": 0,
                "low_completeness_count": 0,
            }

        cutoff = datetime.now(timezone.utc) - timedelta(days=stale_days)
        stale = 0
        missing_owners = 0
        low_completeness = 0

        for doc in docs:
            try:
                updated = datetime.fromisoformat(doc.updated_at.replace("Z", "+00:00"))
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if updated < cutoff:
                    stale += 1
            except (ValueError, AttributeError):
                pass

            if not doc.roles:
                missing_owners += 1
            if doc.completeness_score < 0.5:
                low_completeness += 1

        scores = [doc.completeness_score for doc in docs]
        avg = round(sum(scores) / len(scores), 2) if scores else 0.0

        return {
            "total_processes": len(docs),
            "avg_completeness": avg,
            "stale_count": stale,
            "draft_count": sum(1 for d in docs if d.status == "draft"),
            "active_count": sum(1 for d in docs if d.status == "active"),
            "missing_owners_count": missing_owners,
            "low_completeness_count": low_completeness,
        }

    def stale_processes(self, org_id: str, days: int = 90) -> list[ProcessDocument]:
        docs = self._repo.list_by_org(org_id)
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = []
        for doc in docs:
            try:
                updated = datetime.fromisoformat(doc.updated_at.replace("Z", "+00:00"))
                if updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                if updated < cutoff:
                    result.append(doc)
            except (ValueError, AttributeError):
                result.append(doc)
        return result

    def completeness_breakdown(self, process_id: str) -> dict[str, Any]:
        doc = self._repo.get_latest(process_id)
        if doc is None:
            return {"error": "process not found"}
        from packages.process.service import ProcessService
        return ProcessService.completeness_breakdown(doc)
