from __future__ import annotations

from packages.integrations.base import IntegrationClient


class CalendarService(IntegrationClient):
    """Unified calendar interface. Delegates to Google Calendar or Outlook based on connected provider."""

    def __init__(self):
        super().__init__("calendar")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def check_availability(
        self, start: str, end: str, attendees: list[str] | None = None
    ) -> dict:
        """Check availability for a time range."""
        return {
            "available": True,
            "stub": True,
            "message": "Calendar integration not configured. Connect Google Calendar or Outlook in Settings.",
        }

    def create_event(
        self,
        title: str,
        start: str,
        end: str,
        attendees: list[str] | None = None,
        description: str = "",
        location: str = "",
    ) -> dict:
        """Create a calendar event."""
        return {
            "status": "not_created",
            "title": title,
            "start": start,
            "end": end,
            "stub": True,
            "message": "Calendar integration not configured. Connect Google Calendar or Outlook in Settings.",
        }

    def list_events(self, start: str = "", end: str = "", limit: int = 20) -> list[dict]:
        """List calendar events within a date range."""
        return []
