from __future__ import annotations

from packages.integrations.base import IntegrationClient


class EmailService(IntegrationClient):
    """Unified email interface. Delegates to Gmail or Outlook based on connected provider."""

    def __init__(self):
        super().__init__("email")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def draft(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> dict:
        """Create an email draft."""
        return {
            "status": "draft",
            "to": to,
            "subject": subject,
            "stub": True,
            "message": "Email integration not configured. Connect Gmail or Outlook in Settings.",
        }

    def send(
        self,
        to: list[str],
        subject: str,
        body: str,
        cc: list[str] | None = None,
    ) -> dict:
        """Send an email. In production, requires approval."""
        return {
            "status": "not_sent",
            "to": to,
            "subject": subject,
            "stub": True,
            "message": "Email integration not configured.",
        }

    def read_inbox(self, limit: int = 20) -> list[dict]:
        return []

    def search(self, query: str, limit: int = 10) -> list[dict]:
        return []
