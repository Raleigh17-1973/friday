from __future__ import annotations

from packages.integrations.base import IntegrationClient


class NotionClient(IntegrationClient):
    """Notion integration client for pages and databases."""

    def __init__(self):
        super().__init__("notion")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def read_page(self, page_id: str) -> dict:
        """Read a Notion page by ID."""
        return {
            "page_id": page_id,
            "content": None,
            "stub": True,
            "message": "Notion integration not configured. Connect Notion in Settings.",
        }

    def write_page(
        self,
        parent_id: str,
        title: str,
        content: str,
    ) -> dict:
        """Create or update a Notion page."""
        return {
            "status": "not_created",
            "parent_id": parent_id,
            "title": title,
            "stub": True,
            "message": "Notion integration not configured. Connect Notion in Settings.",
        }

    def search_database(self, database_id: str, query: str = "", limit: int = 20) -> list[dict]:
        """Search a Notion database."""
        return []
