from __future__ import annotations

from packages.integrations.base import IntegrationClient


class JiraClient(IntegrationClient):
    """Jira integration client for issue tracking and sprint management."""

    def __init__(self):
        super().__init__("jira")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def create_issue(
        self,
        project: str,
        summary: str,
        issue_type: str = "Task",
        description: str = "",
        assignee: str | None = None,
        priority: str = "Medium",
    ) -> dict:
        """Create a Jira issue."""
        return {
            "status": "not_created",
            "project": project,
            "summary": summary,
            "stub": True,
            "message": "Jira integration not configured. Connect Jira in Settings.",
        }

    def update_issue(self, issue_key: str, fields: dict) -> dict:
        """Update fields on an existing Jira issue."""
        return {
            "status": "not_updated",
            "issue_key": issue_key,
            "stub": True,
            "message": "Jira integration not configured. Connect Jira in Settings.",
        }

    def search(self, jql: str, limit: int = 20) -> list[dict]:
        """Search issues using JQL."""
        return []

    def sprint_status(self, board_id: str) -> dict:
        """Get the current sprint status for a board."""
        return {
            "board_id": board_id,
            "sprint": None,
            "stub": True,
            "message": "Jira integration not configured. Connect Jira in Settings.",
        }
