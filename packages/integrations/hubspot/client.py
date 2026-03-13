from __future__ import annotations

from packages.integrations.base import IntegrationClient


class HubSpotClient(IntegrationClient):
    """HubSpot integration client for CRM and marketing operations."""

    def __init__(self):
        super().__init__("hubspot")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def get_deals(self, stage: str | None = None, limit: int = 50) -> list[dict]:
        """Get deals from HubSpot, optionally filtered by stage."""
        return []

    def search_contacts(self, query: str, limit: int = 20) -> list[dict]:
        """Search HubSpot contacts."""
        return []
