from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any

try:
    from fastapi import HTTPException, Request
except ModuleNotFoundError:  # pragma: no cover
    class HTTPException(Exception):
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    Request = Any


# ── Auth identity ─────────────────────────────────────────────────────────────

@dataclass
class AuthContext:
    """Verified caller identity extracted from the API key."""
    user_id: str
    org_id: str
    roles: list[str] = field(default_factory=lambda: ["user"])


# Fallback identity used in dev mode (no keys configured).
_DEV_CONTEXT = AuthContext(user_id="user-1", org_id="org-1", roles=["user"])

# Routes that are always public — no authentication required.
PUBLIC_PATHS: frozenset[str] = frozenset({"/health", "/ready", "/"})


def _load_api_key_store() -> dict[str, AuthContext]:
    """Parse FRIDAY_API_KEYS env var into a key → AuthContext mapping.

    Format (JSON object):
        {"<api-key>": {"org_id": "acme", "user_id": "alice", "roles": ["user"]}}

    If the variable is absent or empty the store is empty and auth is not
    enforced (dev mode).
    """
    raw = os.getenv("FRIDAY_API_KEYS", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {
            k: AuthContext(
                user_id=str(v.get("user_id", "user-1")),
                org_id=str(v.get("org_id", "org-1")),
                roles=list(v.get("roles", ["user"])),
            )
            for k, v in data.items()
            if isinstance(v, dict)
        }
    except Exception:
        return {}


_API_KEY_STORE: dict[str, AuthContext] = _load_api_key_store()

# Auth is enforced when keys are configured OR when the flag is explicitly set.
AUTH_ENFORCED: bool = bool(_API_KEY_STORE or os.getenv("FRIDAY_AUTH_REQUIRED", ""))


def resolve_auth(request: Request) -> AuthContext | None:
    """Resolve caller identity from the x-api-key request header.

    Returns:
        AuthContext on success.
        None when auth is enforced and the key is missing or invalid
            (caller must respond with 401).
        _DEV_CONTEXT when auth is not enforced (local dev mode).
    """
    path = request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static"):
        return _DEV_CONTEXT

    if not AUTH_ENFORCED:
        # Dev mode: no keys configured — let all requests through with dev identity.
        return _DEV_CONTEXT

    api_key = request.headers.get("x-api-key", "").strip()
    if not api_key:
        return None  # missing key → caller will return 401

    return _API_KEY_STORE.get(api_key)  # None means invalid key → 401


def current_auth(request: Request) -> AuthContext:
    """Return resolved auth context, falling back to the dev context when auth is disabled."""
    auth = getattr(request.state, "auth", None)
    if auth is not None:
        return auth
    return _DEV_CONTEXT


def current_org_id(request: Request) -> str:
    return current_auth(request).org_id


def current_user_id(request: Request) -> str:
    return current_auth(request).user_id


# ── Admin auth ────────────────────────────────────────────────────────────────

class AdminAuth:
    """Gate for admin-only endpoints using a separate long-lived API key.

    The key is read from FRIDAY_ADMIN_API_KEY (not ADMIN_API_KEY — see PR-05).
    """

    def __init__(self, env_key: str = "FRIDAY_ADMIN_API_KEY") -> None:
        self._key = os.getenv(env_key, "").strip()

    def require(self, request: Request) -> None:
        if not self._key:
            raise HTTPException(status_code=503, detail="admin key not configured")
        provided = request.headers.get("x-admin-api-key", "").strip()
        if provided != self._key:
            raise HTTPException(status_code=403, detail="forbidden")

    def audit(self, action: str, request: Request, detail: str = "") -> None:
        """Emit a structured audit log line for admin actions."""
        import logging
        _alog = logging.getLogger("friday.admin_audit")
        provided = request.headers.get("x-admin-api-key", "")
        key_prefix = provided[:6] + "…" if len(provided) > 6 else "???"
        _alog.warning(
            '{"event":"admin_action","action":"%s","key_prefix":"%s","path":"%s","detail":"%s"}',
            action,
            key_prefix,
            request.url.path,
            detail,
        )


# ── Rate limiter ──────────────────────────────────────────────────────────────

class RateLimiter:
    """Sliding-window rate limiter keyed by an arbitrary string.

    Default bucket: 120 req/min (shared).
    Route-specific overrides: pass a custom `rpm` to `check()`.
    """

    def __init__(self, requests_per_minute: int = 120) -> None:
        self._default_rpm = requests_per_minute
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._route_rpm: dict[str, int] = {
            "/chat/stream": 20,   # stricter for long-lived SSE
            "/upload": 10,        # separate budget for file uploads
        }

    def check(self, key: str, path: str = "") -> None:
        rpm = self._route_rpm.get(path, self._default_rpm)
        now = time.time()
        window_start = now - 60.0
        bucket = self._buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= rpm:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        bucket.append(now)
