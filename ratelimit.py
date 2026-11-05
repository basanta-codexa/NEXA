"""Sliding-window, in-memory rate limiter.

Suitable for a single API process. For multi-instance deployments, swap the
store for Redis and keep the same interface. All limits are env-configurable
and the whole mechanism can be turned off with RATE_LIMIT_ENABLED=false.
"""

from __future__ import annotations

import os
import threading
import time
from collections import deque


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def rate_limits_enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _limits() -> list[tuple[str, tuple[str, int], int]]:
    """Path prefix -> (method, limit) and window in seconds."""
    return [
        ("/tenants/invites", ("POST", _env_int("RATE_LIMIT_INVITES_PER_HOUR", 30)), 3600),
        ("/tenants", ("POST", _env_int("RATE_LIMIT_SIGNUP_PER_HOUR", 10)), 3600),
        ("/users/login", ("POST", _env_int("RATE_LIMIT_LOGIN_PER_MINUTE", 10)), 60),
        ("/agents", ("POST", _env_int("RATE_LIMIT_AGENT_RUN_PER_MINUTE", 20)), 60),
        ("/documents/upload", ("POST", _env_int("RATE_LIMIT_UPLOAD_PER_HOUR", 30)), 3600),
    ]


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                retry = int(bucket[0] + window_seconds - now) + 1
                return False, max(retry, 1)
            bucket.append(now)
            return True, 0

        # unreachable — kept for clarity
        return True, 0

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()

    def prune(self, max_entries: int = 10_000) -> None:
        """Drop empty buckets so memory doesn't grow unbounded."""
        now = time.monotonic()
        with self._lock:
            if len(self._buckets) <= max_entries:
                return
            for key in list(self._buckets):
                bucket = self._buckets[key]
                while bucket and bucket[0] <= now - 3600:
                    bucket.popleft()
                if not bucket:
                    del self._buckets[key]


limiter = SlidingWindowLimiter()


def check_request(path: str, method: str, client_key: str) -> tuple[bool, int, int, int] | None:
    """Return (allowed, limit, remaining, retry_after) for limited routes, else None."""
    if not rate_limits_enabled():
        return None

    for prefix, (required_method, limit), window in _limits():
        if path == prefix or path.startswith(prefix + "/"):
            if method != required_method:
                return None
            allowed, retry = limiter.check(f"{prefix}:{client_key}", limit, window)
            remaining = max(limit - 1, 0) if allowed else 0
            return allowed, limit, remaining, retry

    return None
