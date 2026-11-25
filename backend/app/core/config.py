"""Environment-based runtime configuration with strict zero-secret leakage."""

from dataclasses import dataclass, field
import os
from typing import Dict, List, Optional


def _parse_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _parse_origins(raw: str) -> List[str]:
    origins = [o.strip().rstrip("/") or o.strip() for o in raw.split(",") if o.strip()]
    return origins or ["http://localhost:3000", "http://127.0.0.1:3000"]


def _normalize_optional_secret(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    cleaned = val.strip()
    if not cleaned or cleaned.lower() in {"your_gemini_api_key_here", "changeme", "none", "null"}:
        return None
    return cleaned


@dataclass(frozen=True)
class Settings:
    app_name: str = "AirAware AI — Urban Air Quality Intelligence Platform"
    app_version: str = "3.1.0"
    environment: str = field(default_factory=lambda: os.getenv("ENVIRONMENT", "development"))
    debug: bool = field(default_factory=lambda: _parse_bool(os.getenv("DEBUG"), default=False))
    allowed_origins: List[str] = field(
        default_factory=lambda: _parse_origins(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
        )
    )

    # Primary Provider: Open-Meteo Copernicus CAMS Global
    open_meteo_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPEN_METEO_BASE_URL", "https://air-quality-api.open-meteo.com/v1/air-quality"
        )
    )
    open_meteo_meta_url_template: str = field(
        default_factory=lambda: os.getenv(
            "OPEN_METEO_META_URL_TEMPLATE",
            "https://air-quality-api.open-meteo.com/data/{domain}/static/meta.json",
        )
    )
    open_meteo_domain: str = "cams_global"  # Verified primary Stage 2 domain
    open_meteo_timezone: str = "Asia/Kolkata"
    open_meteo_connect_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("OPEN_METEO_CONNECT_TIMEOUT_SECONDS", "5.0"))
    )
    open_meteo_read_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("OPEN_METEO_READ_TIMEOUT_SECONDS", "12.0"))
    )

    # Stage 1 Frozen Mathematical Parameter (configurable, default 14,400s = 4h)
    max_supported_gap_seconds: float = field(
        default_factory=lambda: float(os.getenv("AIRAWARE_MAX_SUPPORTED_GAP_SECONDS", "14400.0"))
    )

    # Safe Cache & Rate-Limit Protection
    cache_ttl_seconds: int = field(
        default_factory=lambda: int(os.getenv("AIRAWARE_CACHE_TTL_SECONDS", "600"))
    )
    cache_max_entries: int = field(
        default_factory=lambda: int(os.getenv("AIRAWARE_CACHE_MAX_ENTRIES", "256"))
    )
    rate_limit_requests_per_minute: int = field(
        default_factory=lambda: int(os.getenv("AIRAWARE_RATE_LIMIT_PER_MIN", "120"))
    )

    # Stage 3.2 Grounded AI Assistant / LLM Provider Settings (Optional; secret excluded from summaries)
    llm_provider: str = field(
        default_factory=lambda: os.getenv("AIRAWARE_LLM_PROVIDER", "gemini").strip().lower()
    )
    gemini_api_key: Optional[str] = field(
        default_factory=lambda: _normalize_optional_secret(os.getenv("GEMINI_API_KEY"))
    )
    llm_model: str = field(
        default_factory=lambda: os.getenv("AIRAWARE_LLM_MODEL", "gemini-2.0-flash").strip()
    )
    llm_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("AIRAWARE_LLM_TIMEOUT_SECONDS", "10.0"))
    )
    llm_max_retries: int = field(
        default_factory=lambda: max(0, int(os.getenv("AIRAWARE_LLM_MAX_RETRIES", "1")))
    )
    llm_max_input_chars: int = field(
        default_factory=lambda: max(100, int(os.getenv("AIRAWARE_LLM_MAX_INPUT_CHARS", "1000")))
    )

    def __post_init__(self) -> None:
        if self.environment.strip().lower() == "production":
            object.__setattr__(self, "debug", False)
            if "*" in self.allowed_origins:
                raise ValueError(
                    "Wildcard CORS origin ('*') is forbidden when ENVIRONMENT=production. "
                    "Set ALLOWED_ORIGINS to explicit deployed HTTPS frontend origin(s)."
                )

    def safe_summary(self) -> Dict[str, object]:
        """Return non-sensitive settings metadata safe for diagnostics."""
        return {
            "app_version": self.app_version,
            "environment": self.environment,
            "debug": self.debug,
            "open_meteo_domain": self.open_meteo_domain,
            "max_supported_gap_seconds": self.max_supported_gap_seconds,
            "cache_ttl_seconds": self.cache_ttl_seconds,
            "cache_max_entries": self.cache_max_entries,
            "rate_limit_requests_per_minute": self.rate_limit_requests_per_minute,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "llm_configured": bool(self.gemini_api_key),
            "llm_timeout_seconds": self.llm_timeout_seconds,
        }


settings = Settings()
