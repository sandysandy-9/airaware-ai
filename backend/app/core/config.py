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


def _parse_trusted_proxies(raw: str) -> List[str]:
    return [p.strip() for p in raw.split(",") if p.strip()]


def _validate_origin_url(origin: str, *, is_production: bool) -> None:
    if origin == "*":
        if is_production:
            raise ValueError(
                "Wildcard CORS origin ('*') is forbidden when ENVIRONMENT=production. "
                "Set ALLOWED_ORIGINS to explicit deployed HTTPS frontend origin(s)."
            )
        return
    lowered = origin.lower()
    if not lowered.startswith(("https://", "http://")):
        raise ValueError(f"Invalid CORS origin scheme '{origin}'; expected http:// or https://.")
    if is_production and lowered.startswith("http://"):
        host = lowered[7:].split("/")[0].split(":")[0]
        if host not in {"localhost", "127.0.0.1"}:
            raise ValueError(
                f"Insecure HTTP CORS origin '{origin}' is forbidden when ENVIRONMENT=production; use HTTPS."
            )


_DISALLOWED_ATTESTATION_PLACEHOLDERS = frozenset(
    {
        "changeme",
        "change-me",
        "change_me",
        "none",
        "null",
        "your-secret",
        "your_secret",
        "your-secret-here",
        "your_secret_here",
        "your_attestation_secret_here",
        "your-attestation-secret-here",
        "secret",
        "default",
        "example",
        "placeholder",
        "test",
    }
)
MIN_ATTESTATION_SECRET_CHARS = 32


def _normalize_optional_secret(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    cleaned = val.strip()
    if not cleaned or cleaned.lower() in {"your_gemini_api_key_here", "changeme", "none", "null"}:
        return None
    return cleaned


def validate_attestation_secret(val: Optional[str]) -> Optional[str]:
    """Validate optional HMAC attestation secret.

    - Unset or empty string returns None (single-worker ephemeral key fallback).
    - Whitespace-only, known placeholders, or <32-char secrets fail closed with ValueError.
    """
    if val is None or val == "":
        return None
    if not isinstance(val, str):
        raise ValueError("AIRAWARE_ATTESTATION_SECRET must be a string.")
    if not val.strip():
        raise ValueError("AIRAWARE_ATTESTATION_SECRET must not be whitespace-only.")
    cleaned = val.strip()
    lowered = cleaned.lower()
    if lowered in _DISALLOWED_ATTESTATION_PLACEHOLDERS or lowered.startswith(
        ("changeme", "your-secret", "your_secret", "placeholder")
    ):
        raise ValueError("AIRAWARE_ATTESTATION_SECRET uses a disallowed placeholder value.")
    if len(cleaned) < MIN_ATTESTATION_SECRET_CHARS:
        raise ValueError(
            f"AIRAWARE_ATTESTATION_SECRET must be at least {MIN_ATTESTATION_SECRET_CHARS} characters long."
        )
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
    rate_limit_max_tracked_clients: int = field(
        default_factory=lambda: int(os.getenv("AIRAWARE_RATE_LIMIT_MAX_CLIENTS", "10000"))
    )
    trusted_proxy_ips: List[str] = field(
        default_factory=lambda: _parse_trusted_proxies(os.getenv("TRUSTED_PROXY_IPS", ""))
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
    attestation_secret: Optional[str] = field(
        default_factory=lambda: os.getenv("AIRAWARE_ATTESTATION_SECRET"),
        repr=False,
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "attestation_secret",
            validate_attestation_secret(self.attestation_secret),
        )
        if self.open_meteo_connect_timeout_seconds <= 0 or self.open_meteo_read_timeout_seconds <= 0:
            raise ValueError("Provider timeout values must be strictly positive.")
        if self.llm_timeout_seconds <= 0:
            raise ValueError("AIRAWARE_LLM_TIMEOUT_SECONDS must be strictly positive.")
        if self.max_supported_gap_seconds <= 0:
            raise ValueError("AIRAWARE_MAX_SUPPORTED_GAP_SECONDS must be strictly positive.")
        if self.cache_ttl_seconds < 0 or self.cache_max_entries < 1:
            raise ValueError("Cache TTL must be >= 0 and AIRAWARE_CACHE_MAX_ENTRIES >= 1.")
        if self.rate_limit_requests_per_minute < 1 or self.rate_limit_max_tracked_clients < 1:
            raise ValueError("Rate-limit settings must be >= 1.")

        is_prod = self.environment.strip().lower() == "production"
        if is_prod:
            object.__setattr__(self, "debug", False)
        for origin in self.allowed_origins:
            _validate_origin_url(origin, is_production=is_prod)

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
            "attestation_secret_configured": bool(self.attestation_secret),
            "llm_timeout_seconds": self.llm_timeout_seconds,
        }


settings = Settings()
