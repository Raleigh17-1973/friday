"""Integration client base class with circuit breaker and rate limiting."""
from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod


class CircuitBreaker:
    """Simple circuit breaker: opens after N failures, resets after timeout."""

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._last_failure_time = 0.0
        self._is_open = False

    @property
    def is_open(self) -> bool:
        if self._is_open and (time.time() - self._last_failure_time) > self.reset_timeout:
            # half-open: allow a retry
            self._is_open = False
            self._failures = 0
        return self._is_open

    def record_success(self) -> None:
        self._failures = 0
        self._is_open = False

    def record_failure(self) -> None:
        self._failures += 1
        self._last_failure_time = time.time()
        if self._failures >= self.failure_threshold:
            self._is_open = True


class TokenBucketRateLimiter:
    """Simple token bucket rate limiter."""

    def __init__(self, rate: float = 10.0, burst: int = 20) -> None:
        self.rate = rate
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.time()

    def acquire(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now
        if self._tokens < 1:
            wait = (1 - self._tokens) / self.rate
            time.sleep(wait)
            self._tokens = 0
        else:
            self._tokens -= 1


class IntegrationClient(ABC):
    """Base class for all external service integration clients."""

    def __init__(self, provider_name: str) -> None:
        self._provider = provider_name
        self._log = logging.getLogger(f"integration.{provider_name}")
        self._circuit_breaker = CircuitBreaker()
        self._rate_limiter = TokenBucketRateLimiter()

    @abstractmethod
    def health_check(self) -> bool: ...

    def _execute_with_retry(self, fn, max_retries: int = 3, base_delay: float = 1.0):
        """Execute a callable with retry, circuit breaker, and rate limiting."""
        if self._circuit_breaker.is_open:
            raise ConnectionError(f"{self._provider} circuit breaker is open")

        self._rate_limiter.acquire()

        last_error: Exception | None = None
        for attempt in range(max_retries):
            try:
                result = fn()
                self._circuit_breaker.record_success()
                return result
            except Exception as e:
                last_error = e
                self._circuit_breaker.record_failure()
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    self._log.warning(
                        "Attempt %d failed: %s, retrying in %.1fs",
                        attempt + 1,
                        e,
                        delay,
                    )
                    time.sleep(delay)

        raise last_error  # type: ignore[misc]

    @property
    def circuit_breaker_status(self) -> dict:
        return {
            "provider": self._provider,
            "is_open": self._circuit_breaker.is_open,
            "failures": self._circuit_breaker._failures,
        }
