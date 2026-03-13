from __future__ import annotations

from packages.integrations.base import IntegrationClient


class ConfluenceClient(IntegrationClient):
    """Confluence integration client for wiki and documentation."""

    def __init__(self):
        super().__init__("confluence")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def read_page(self, page_id: str) -> dict:
        """Read a Confluence page by ID."""
        return {
            "page_id": page_id,
            "content": None,
            "stub": True,
            "message": "Confluence integration not configured. Connect Confluence in Settings.",
        }

    def write_page(
        self,
        space_key: str,
        title: str,
        body: str,
        parent_id: str | None = None,
    ) -> dict:
        """Create or update a Confluence page."""
        return {
            "status": "not_created",
            "space_key": space_key,
            "title": title,
            "stub": True,
            "message": "Confluence integration not configured. Connect Confluence in Settings.",
        }

    def search(self, cql: str, limit: int = 20) -> list[dict]:
        """Search Confluence using CQL."""
        return []
