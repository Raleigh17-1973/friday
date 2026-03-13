from __future__ import annotations

from packages.integrations.base import IntegrationClient


class LinearClient(IntegrationClient):
    """Linear integration client for issue tracking."""

    def __init__(self):
        super().__init__("linear")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def create_issue(
        self,
        team_id: str,
        title: str,
        description: str = "",
        assignee_id: str | None = None,
        priority: int = 0,
    ) -> dict:
        """Create a Linear issue."""
        return {
            "status": "not_created",
            "team_id": team_id,
            "title": title,
            "stub": True,
            "message": "Linear integration not configured. Connect Linear in Settings.",
        }

    def update_issue(self, issue_id: str, fields: dict) -> dict:
        """Update fields on an existing Linear issue."""
        return {
            "status": "not_updated",
            "issue_id": issue_id,
            "stub": True,
            "message": "Linear integration not configured. Connect Linear in Settings.",
        }

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Search Linear issues."""
        return []
