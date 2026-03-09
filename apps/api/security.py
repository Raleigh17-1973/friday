from __future__ import annotations

import os
import time
from collections import defaultdict, deque
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


class AdminAuth:
    def __init__(self, env_key: str = "FRIDAY_ADMIN_API_KEY") -> None:
        self._key = os.getenv(env_key, "").strip()

    def require(self, request: Request) -> None:
        if not self._key:
            raise HTTPException(status_code=503, detail="admin key not configured")
        provided = request.headers.get("x-admin-api-key", "").strip()
        if provided != self._key:
            raise HTTPException(status_code=403, detail="forbidden")


class RateLimiter:
    def __init__(self, requests_per_minute: int = 120) -> None:
        self._rpm = requests_per_minute
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.time()
        window_start = now - 60.0
        bucket = self._buckets[key]
        while bucket and bucket[0] < window_start:
            bucket.popleft()
        if len(bucket) >= self._rpm:
            raise HTTPException(status_code=429, detail="rate limit exceeded")
        bucket.append(now)
