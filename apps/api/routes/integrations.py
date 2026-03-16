from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from apps.api.deps import service
from apps.api.security import AuthContext

router = APIRouter()


def _auth(request: Request) -> AuthContext:
    return getattr(request.state, "auth", None) or AuthContext(
        user_id="user-1", org_id="org-1", roles=["user"]
    )


class SlackPostPayload(BaseModel):
    channel: str
    text: str
    org_id: str = "org-1"
    thread_ts: Optional[str] = None


@router.get("/credentials")
def list_credentials(org_id: str = "org-1") -> list[dict]:
    return [c.to_dict() for c in service.credentials.list_credentials(org_id=org_id)]


@router.get("/integrations/status")
def integration_status(org_id: str = "org-1") -> dict:
    """Check which integrations are connected."""
    providers = ["google", "slack", "jira", "linear", "confluence", "notion", "salesforce", "hubspot", "gmail", "outlook"]
    return {p: service.credentials.has_credential(p, org_id) for p in providers}


@router.get("/integrations/slack/status")
def slack_status(org_id: str = "org-1") -> dict:
    """Return Slack connection status for the org, including team/bot metadata."""
    connected = service.credentials.has_credential("slack", org_id)
    if not connected:
        return {"connected": False}
    try:
        cred = service.credentials.get_credential("slack", org_id)
        meta = (cred.metadata or {}) if cred else {}
        return {"connected": True, "team": meta.get("team", ""), "bot": meta.get("bot", "")}
    except Exception:
        return {"connected": True}


@router.get("/integrations/slack/connect")
def slack_oauth_connect(
    org_id: str = "org-1",
    redirect_uri: str = "http://localhost:8000/integrations/slack/callback",
    frontend_url: str = "http://localhost:3000",
):
    """Redirect browser to Slack OAuth authorization URL."""
    import os
    import urllib.parse
    from fastapi.responses import RedirectResponse
    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    if not client_id:
        # Redirect back to settings with an error rather than raising
        return RedirectResponse(url=f"{frontend_url}/settings?error=slack_not_configured")
    scopes = "channels:read,chat:write,users:read,im:write"
    # Embed frontend_url in redirect_uri so callback can redirect back correctly
    callback_uri = f"{redirect_uri}?frontend_url={urllib.parse.quote(frontend_url)}"
    auth_url = (
        "https://slack.com/oauth/v2/authorize"
        f"?client_id={client_id}"
        f"&scope={scopes}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri, safe='')}"
        f"&state={org_id}"
    )
    return RedirectResponse(url=auth_url)


@router.get("/integrations/slack/callback")
def slack_oauth_callback(
    code: str = "",
    state: str = "org-1",
    error: str = "",
    frontend_url: str = "http://localhost:3000",
) -> "RedirectResponse":
    """Handle Slack OAuth callback — exchange code for token, persist, redirect to frontend."""
    import os
    import httpx
    from fastapi.responses import RedirectResponse as _Redirect
    settings_url = f"{frontend_url}/settings"
    if error:
        return _Redirect(url=f"{settings_url}?error={error}")
    client_id = os.environ.get("SLACK_CLIENT_ID", "")
    client_secret = os.environ.get("SLACK_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        return _Redirect(url=f"{settings_url}?error=slack_not_configured")
    try:
        resp = httpx.post(
            "https://slack.com/api/oauth.v2.access",
            data={"code": code, "client_id": client_id, "client_secret": client_secret},
            timeout=10,
        )
        data = resp.json()
    except Exception:
        return _Redirect(url=f"{settings_url}?error=token_exchange_failed")
    if not data.get("ok"):
        err_code = data.get("error", "oauth_failed")
        return _Redirect(url=f"{settings_url}?error={err_code}")
    token: str = data.get("access_token", "")
    team: str = (data.get("team") or {}).get("name", "")
    bot_name: str = (data.get("bot_user_id") or "")
    try:
        service.credentials.store_credential(
            provider="slack", org_id=state, token=token,
            metadata={"team": team, "bot": bot_name, "scope": data.get("scope", "")},
        )
    except Exception:
        pass
    return _Redirect(url=f"{settings_url}?slack_oauth=success")


@router.delete("/integrations/slack/disconnect")
def slack_disconnect(org_id: str = "org-1") -> dict:
    """Remove stored Slack credentials for the org."""
    try:
        service.credentials.delete_credential("slack", org_id)
    except Exception:
        pass
    return {"ok": True, "connected": False}


@router.post("/integrations/slack/post")
def slack_post_message(payload: SlackPostPayload) -> dict:
    """Post a message to a Slack channel on behalf of the org."""
    token: Optional[str] = None
    try:
        if service.credentials.has_credential("slack", payload.org_id):
            cred = service.credentials.get_credential("slack", payload.org_id)
            token = cred.token if cred else None
    except Exception:
        pass
    from packages.integrations.slack.client import SlackClient
    client = SlackClient(token=token)
    return client.post_message(payload.channel, payload.text, thread_ts=payload.thread_ts)


@router.post("/webhooks/inbound/{source}", status_code=202)
async def inbound_webhook(source: str, request: Request) -> dict:
    """Generic inbound webhook router.

    Currently handles: slack (Slack Events API — URL verification + mention events).
    Returns 202 Accepted immediately.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    if source == "slack":
        # Slack URL verification challenge
        if body.get("type") == "url_verification":
            return {"challenge": body.get("challenge", "")}
        event = body.get("event", {})
        event_type = event.get("type", "")
        if event_type in ("app_mention", "message"):
            channel = event.get("channel", "")
            user = event.get("user", "")
            text = event.get("text", "")
            try:
                service.activity.log(
                    action="webhook_event", entity_type="slack_message", entity_id=channel,
                    entity_title=text[:80], actor_id=user or "slack",
                    event_type=event_type, channel=channel,
                )
            except Exception:
                pass

    return {"ok": True, "source": source, "status": "received"}


@router.post("/voice/transcribe")
async def transcribe_voice(file: UploadFile = File(...)) -> dict:
    from dataclasses import asdict
    audio_bytes = await file.read()
    result = service.voice.transcribe_bytes(audio_bytes, filename=file.filename or "audio.mp3")
    return asdict(result)
