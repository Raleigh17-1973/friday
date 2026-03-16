"""apps/api/deps.py — Shared application singletons.

Import `service`, `admin_auth`, `rate_limiter`, and `upload_store` from here
rather than re-instantiating them in each module.  Router modules and middleware
all reference these same objects.

`upload_store` is an in-process dict keyed by context_id (str) → file metadata.
It is intentionally ephemeral — lost on restart.  Replace with Redis or a DB
table for production deployments that need persistence across restarts.
"""
from __future__ import annotations

from apps.api.service import FridayService
from apps.api.security import AdminAuth, RateLimiter

# Core singletons — created once at module import time.
service: FridayService = FridayService()
admin_auth: AdminAuth = AdminAuth()
rate_limiter: RateLimiter = RateLimiter()

# In-process upload context store: context_id -> {"filename": str, "text": str, "type": str}
upload_store: dict[str, dict] = {}
