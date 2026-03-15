"""Slack integration client.

Uses the ``slack-sdk`` package when available. Install with:
    pip install slack-sdk

When the SDK is not installed or no token is configured, all methods return
a descriptive stub response instead of raising exceptions.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from packages.integrations.base import IntegrationClient

_log = logging.getLogger(__name__)

_SDK_AVAILABLE = False
try:
    import slack_sdk  # type: ignore[import]  # noqa: F401
    _SDK_AVAILABLE = True
except ImportError:
    pass


class SlackClient(IntegrationClient):
    """Slack integration client for messaging and channel operations.

    Token resolution order:
    1. ``token`` constructor argument (passed from CredentialService)
    2. ``SLACK_BOT_TOKEN`` environment variable
    3. No-op stub mode — all methods return {"stub": True, ...}
    """

    def __init__(self, token: str | None = None) -> None:
        super().__init__("slack")
        self._token: str | None = token or os.environ.get("SLACK_BOT_TOKEN")
        self._client: Any = None
        self._connected = False
        if self._token and _SDK_AVAILABLE:
            try:
                from slack_sdk import WebClient  # type: ignore[import]
                self._client = WebClient(token=self._token)
                self._connected = True
            except Exception as exc:
                _log.warning("SlackClient: failed to initialise WebClient: %s", exc)

    # ── health ────────────────────────────────────────────────────────────────

    def health_check(self) -> bool:
        """Return True when the token is valid and the Slack API is reachable."""
        if self._client is None:
            return False
        try:
            resp = self._client.auth_test()
            return bool(resp.get("ok"))
        except Exception as exc:
            _log.warning("SlackClient.health_check: %s", exc)
            return False

    # ── messaging ─────────────────────────────────────────────────────────────

    def post_message(
        self,
        channel: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict[str, Any]:
        """Post a message to a Slack channel or thread."""
        if self._client is None:
            return self._stub("post_message", channel=channel)
        try:
            kwargs: dict[str, Any] = {"channel": channel, "text": text}
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            resp = self._client.chat_postMessage(**kwargs)
            return {
                "ok": resp.get("ok"),
                "ts": resp.get("ts"),
                "channel": resp.get("channel"),
            }
        except Exception as exc:
            _log.warning("SlackClient.post_message: %s", exc)
            return {"ok": False, "error": str(exc)}

    def send_dm(self, user_id: str, text: str) -> dict[str, Any]:
        """Send a direct message to a Slack user by their user ID."""
        if self._client is None:
            return self._stub("send_dm", user_id=user_id)
        try:
            # Open a DM conversation first
            conv = self._client.conversations_open(users=[user_id])
            channel = conv["channel"]["id"]
            return self.post_message(channel, text)
        except Exception as exc:
            _log.warning("SlackClient.send_dm: %s", exc)
            return {"ok": False, "error": str(exc)}

    def thread_reply(self, channel: str, thread_ts: str, text: str) -> dict[str, Any]:
        """Reply to a thread in a Slack channel."""
        return self.post_message(channel, text, thread_ts=thread_ts)

    def read_channel(self, channel: str, limit: int = 20) -> list[dict[str, Any]]:
        """Read recent messages from a Slack channel."""
        if self._client is None:
            return []
        try:
            resp = self._client.conversations_history(channel=channel, limit=limit)
            msgs = resp.get("messages") or []
            return [
                {
                    "ts": m.get("ts"),
                    "user": m.get("user"),
                    "text": m.get("text", ""),
                    "thread_ts": m.get("thread_ts"),
                }
                for m in msgs
            ]
        except Exception as exc:
            _log.warning("SlackClient.read_channel: %s", exc)
            return []

    # ── channels + users ──────────────────────────────────────────────────────

    def get_channels(self) -> list[dict[str, Any]]:
        """Return a list of public channels the bot has access to."""
        if self._client is None:
            return []
        try:
            resp = self._client.conversations_list(types="public_channel", limit=200)
            channels = resp.get("channels") or []
            return [{"id": c["id"], "name": c["name"], "num_members": c.get("num_members", 0)} for c in channels]
        except Exception as exc:
            _log.warning("SlackClient.get_channels: %s", exc)
            return []

    def get_users(self) -> list[dict[str, Any]]:
        """Return workspace members (non-bot, non-deleted)."""
        if self._client is None:
            return []
        try:
            resp = self._client.users_list()
            members = resp.get("members") or []
            return [
                {
                    "id": u["id"],
                    "name": u.get("real_name") or u.get("name"),
                    "email": (u.get("profile") or {}).get("email"),
                }
                for u in members
                if not u.get("is_bot") and not u.get("deleted")
            ]
        except Exception as exc:
            _log.warning("SlackClient.get_users: %s", exc)
            return []

    # ── helpers ───────────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    @staticmethod
    def _stub(method: str, **kwargs: Any) -> dict[str, Any]:
        return {
            "ok": False,
            "stub": True,
            "method": method,
            "message": "Slack integration not configured. Connect Slack in Settings.",
            **kwargs,
        }
