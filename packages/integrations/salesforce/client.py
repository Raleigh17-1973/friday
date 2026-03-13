from __future__ import annotations

from packages.integrations.base import IntegrationClient


class SalesforceClient(IntegrationClient):
    """Salesforce integration client for CRM operations."""

    def __init__(self):
        super().__init__("salesforce")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def get_pipeline(self, stage: str | None = None, limit: int = 50) -> dict:
        """Get the sales pipeline, optionally filtered by stage."""
        return {
            "pipeline": [],
            "stub": True,
            "message": "Salesforce integration not configured. Connect Salesforce in Settings.",
        }

    def search_accounts(self, query: str, limit: int = 20) -> list[dict]:
        """Search Salesforce accounts."""
        return []

    def update_opportunity(self, opportunity_id: str, fields: dict) -> dict:
        """Update an opportunity in Salesforce."""
        return {
            "status": "not_updated",
            "opportunity_id": opportunity_id,
            "stub": True,
            "message": "Salesforce integration not configured. Connect Salesforce in Settings.",
        }
