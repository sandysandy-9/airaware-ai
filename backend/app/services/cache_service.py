"""Lightweight in-memory cache with TTL for environmental data."""

import time
from typing import Any, Dict, Optional, Tuple


class TTLCache:
    def __init__(self, default_ttl_seconds: int = 900):  # 15 minutes default
        self._cache: Dict[str, Tuple[float, Any]] = {}
        self._default_ttl = default_ttl_seconds

    def _make_key(self, prefix: str, lat: float, lon: float, extra: str = "") -> str:
        # Round to 2 decimal places (~1 km grid)
        return f"{prefix}:{round(lat, 2)}:{round(lon, 2)}:{extra}"

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        expires_at, val = self._cache[key]
        if time.time() > expires_at:
            del self._cache[key]
            return None
        return val

    def set(self, key: str, val: Any, ttl: Optional[int] = None) -> None:
        ttl_sec = ttl if ttl is not None else self._default_ttl
        self._cache[key] = (time.time() + ttl_sec, val)

    def clear(self) -> None:
        self._cache.clear()


cache_service = TTLCache(default_ttl_seconds=900)
