"""Lightweight in-memory sliding-window rate limiter for API endpoint protection.

Single-process limitation:
Rate-limit counters are held strictly inside the current Python process.
In multi-worker deployments (multiple Uvicorn/Gunicorn workers or instances),
limits are enforced independently per process rather than globally shared.
"""

from collections import deque
import threading
import time
from typing import Deque, Dict, Optional
from fastapi import HTTPException, Request

from app.core.config import Settings, settings


class SlidingWindowRateLimiter:
    """Thread-safe single-process per-client-IP sliding window rate limiter."""

    def __init__(
        self,
        max_requests_per_minute: Optional[int] = None,
        window_seconds: int = 60,
    ):
        configured_limit = (
            settings.rate_limit_requests_per_minute
            if max_requests_per_minute is None
            else max_requests_per_minute
        )
        self.max_requests = max(1, int(configured_limit))
        self.window_seconds = max(1, int(window_seconds))
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, config: Optional[Settings] = None, window_seconds: int = 60) -> "SlidingWindowRateLimiter":
        """Construct a rate limiter bound to explicit or fresh Settings."""
        cfg = config or Settings()
        return cls(
            max_requests_per_minute=cfg.rate_limit_requests_per_minute,
            window_seconds=window_seconds,
        )

    def reconfigure(
        self,
        *,
        max_requests_per_minute: Optional[int] = None,
        window_seconds: Optional[int] = None,
    ) -> None:
        """Update rate-limit thresholds cleanly and reset active windows."""
        with self._lock:
            if max_requests_per_minute is not None:
                self.max_requests = max(1, int(max_requests_per_minute))
            if window_seconds is not None:
                self.window_seconds = max(1, int(window_seconds))
            self._hits.clear()

    def check(self, client_key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._hits.setdefault(client_key, deque())
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.max_requests:
                raise HTTPException(
                    status_code=429,
                    detail={
                        "error": "RateLimitExceeded",
                        "message": "Too many requests; please wait briefly before querying again.",
                    },
                )
            q.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


rate_limiter = SlidingWindowRateLimiter(
    max_requests_per_minute=settings.rate_limit_requests_per_minute,
    window_seconds=60,
)


async def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing sliding-window rate limits per client IP."""
    client_host = request.client.host if request.client else "unknown"
    rate_limiter.check(client_host)
