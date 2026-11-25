"""Thread-safe bounded in-memory TTL + LRU cache for environmental data.

Single-process limitation:
This cache stores entries strictly inside the current Python worker process memory.
Multi-worker deployments (e.g., multiple Uvicorn/Gunicorn workers or containers)
do NOT share cached entries or eviction state across processes.
"""

from collections import OrderedDict
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.core.config import settings


class TTLCache:
    """Thread-safe in-memory TTL cache with bounded LRU capacity.

    Accesses update LRU ordering for capacity management only; expiration
    timestamps remain fixed to write time so reads never extend upstream
    data freshness or TTL lifetime.
    """

    def __init__(self, default_ttl_seconds: int = 600, max_size: int = 256):
        self._lock = threading.RLock()
        self._cache: OrderedDict[str, Tuple[float, Any]] = OrderedDict()
        self._default_ttl = max(0, int(default_ttl_seconds))
        self._max_size = max(1, int(max_size))

    @property
    def max_size(self) -> int:
        with self._lock:
            return self._max_size

    @property
    def default_ttl_seconds(self) -> int:
        with self._lock:
            return self._default_ttl

    def configure(
        self,
        *,
        default_ttl_seconds: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> None:
        """Update cache limits safely (evicting excess oldest entries if shrunk)."""
        with self._lock:
            if default_ttl_seconds is not None:
                self._default_ttl = max(0, int(default_ttl_seconds))
            if max_size is not None:
                self._max_size = max(1, int(max_size))
                self._purge_expired_locked(time.monotonic())
                while len(self._cache) > self._max_size:
                    self._cache.popitem(last=False)

    def _make_key(self, prefix: str, lat: float, lon: float, extra: str = "") -> str:
        # Round to 2 decimal places (~1 km grid)
        return f"{prefix}:{round(lat, 2)}:{round(lon, 2)}:{extra}"

    def _purge_expired_locked(self, now: float) -> int:
        expired_keys = [k for k, (expires_at, _) in self._cache.items() if now >= expires_at]
        for k in expired_keys:
            del self._cache[k]
        return len(expired_keys)

    def prune_expired(self) -> int:
        """Explicitly purge all expired entries and return the count removed."""
        with self._lock:
            return self._purge_expired_locked(time.monotonic())

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expires_at, val = entry
            if now >= expires_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return val

    def set(self, key: str, val: Any, ttl: Optional[int] = None) -> None:
        ttl_sec = self._default_ttl if ttl is None else ttl
        now = time.monotonic()
        with self._lock:
            self._purge_expired_locked(now)
            if ttl_sec <= 0:
                self._cache.pop(key, None)
                return
            expires_at = now + ttl_sec
            if key in self._cache:
                self._cache[key] = (expires_at, val)
                self._cache.move_to_end(key)
                return
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
            self._cache[key] = (expires_at, val)

    def size(self) -> int:
        """Return active (non-expired) entry count after purging expired entries."""
        with self._lock:
            self._purge_expired_locked(time.monotonic())
            return len(self._cache)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()


cache_service = TTLCache(
    default_ttl_seconds=settings.cache_ttl_seconds,
    max_size=settings.cache_max_entries,
)
