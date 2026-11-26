"""Lightweight in-memory sliding-window rate limiter for API endpoint protection.

Single-process limitation:
Rate-limit counters are held strictly inside the current Python process.
In multi-worker deployments (multiple Uvicorn/Gunicorn workers or instances),
limits are enforced independently per process rather than globally shared.
"""

from collections import OrderedDict, deque
import ipaddress
import threading
import time
from typing import Collection, Deque, Optional
from fastapi import HTTPException, Request

from app.core.config import Settings, settings


class SlidingWindowRateLimiter:
    """Thread-safe single-process per-client-IP sliding window rate limiter with bounded memory."""

    def __init__(
        self,
        max_requests_per_minute: Optional[int] = None,
        window_seconds: int = 60,
        max_tracked_clients: Optional[int] = None,
    ):
        configured_limit = (
            settings.rate_limit_requests_per_minute
            if max_requests_per_minute is None
            else max_requests_per_minute
        )
        configured_cap = (
            settings.rate_limit_max_tracked_clients
            if max_tracked_clients is None
            else max_tracked_clients
        )
        self.max_requests = max(1, int(configured_limit))
        self.window_seconds = max(1, int(window_seconds))
        self.max_tracked_clients = max(1, int(configured_cap))
        self._hits: "OrderedDict[str, Deque[float]]" = OrderedDict()
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, config: Optional[Settings] = None, window_seconds: int = 60) -> "SlidingWindowRateLimiter":
        """Construct a rate limiter bound to explicit or fresh Settings."""
        cfg = config or Settings()
        return cls(
            max_requests_per_minute=cfg.rate_limit_requests_per_minute,
            window_seconds=window_seconds,
            max_tracked_clients=cfg.rate_limit_max_tracked_clients,
        )

    def reconfigure(
        self,
        *,
        max_requests_per_minute: Optional[int] = None,
        window_seconds: Optional[int] = None,
        max_tracked_clients: Optional[int] = None,
    ) -> None:
        """Update rate-limit thresholds cleanly and reset active windows."""
        with self._lock:
            if max_requests_per_minute is not None:
                self.max_requests = max(1, int(max_requests_per_minute))
            if window_seconds is not None:
                self.window_seconds = max(1, int(window_seconds))
            if max_tracked_clients is not None:
                self.max_tracked_clients = max(1, int(max_tracked_clients))
            self._hits.clear()

    def _prune_stale_locked(self, cutoff: float) -> None:
        stale_keys = []
        for key, q in self._hits.items():
            while q and q[0] < cutoff:
                q.popleft()
            if not q:
                stale_keys.append(key)
        for key in stale_keys:
            del self._hits[key]

    @property
    def tracked_client_count(self) -> int:
        with self._lock:
            return len(self._hits)

    def check(self, client_key: str) -> None:
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            q = self._hits.get(client_key)
            if q is not None:
                while q and q[0] < cutoff:
                    q.popleft()
                if not q:
                    del self._hits[client_key]
                    q = None

            if q is None:
                if len(self._hits) >= self.max_tracked_clients:
                    self._prune_stale_locked(cutoff)
                while len(self._hits) >= self.max_tracked_clients:
                    self._hits.popitem(last=False)
                q = deque()
                self._hits[client_key] = q
            else:
                self._hits.move_to_end(client_key)

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
    max_tracked_clients=settings.rate_limit_max_tracked_clients,
)


def resolve_client_ip(
    request: Request,
    trusted_proxies: Optional[Collection[str]] = None,
) -> str:
    """Resolve client IP without trusting X-Forwarded-For unless peer IP is an explicit trusted proxy."""
    peer_ip = request.client.host if request.client and request.client.host else "unknown"
    trusted = set(trusted_proxies if trusted_proxies is not None else settings.trusted_proxy_ips)
    if not trusted or peer_ip not in trusted:
        return peer_ip

    xff = request.headers.get("x-forwarded-for")
    if not xff:
        return peer_ip

    hops = [h.strip() for h in xff.split(",") if h.strip()]
    # Walk right-to-left skipping configured trusted proxies so spoofed leftmost values are never trusted
    for hop in reversed(hops):
        if hop in trusted:
            continue
        try:
            return str(ipaddress.ip_address(hop))
        except ValueError:
            return peer_ip
    return peer_ip


async def enforce_rate_limit(request: Request) -> None:
    """FastAPI dependency enforcing sliding-window rate limits per resolved client IP."""
    rate_limiter.check(resolve_client_ip(request))
