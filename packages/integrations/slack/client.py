from __future__ import annotations

from packages.integrations.base import IntegrationClient


class SlackClient(IntegrationClient):
    """Slack integration client for messaging and channel operations."""

    def __init__(self):
        super().__init__("slack")
        self._connected = False

    def health_check(self) -> bool:
        return self._connected

    def post_message(self, channel: str, text: str, thread_ts: str | None = None) -> dict:
        """Post a message to a Slack channel."""
        return {
            "status": "not_sent",
            "channel": channel,
            "stub": True,
            "message": "Slack integration not configured. Connect Slack in Settings.",
        }

    def read_channel(self, channel: str, limit: int = 20) -> list[dict]:
        """Read recent messages from a Slack channel."""
        return []

    def thread_reply(self, channel: str, thread_ts: str, text: str) -> dict:
        """Reply to a thread in a Slack channel."""
        return {
            "status": "not_sent",
            "channel": channel,
            "thread_ts": thread_ts,
            "stub": True,
            "message": "Slack integration not configured. Connect Slack in Settings.",
        }
