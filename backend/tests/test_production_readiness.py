"""Stage 3.4 Production Readiness & Security Verification Tests."""

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import app


def test_production_forbids_wildcard_cors(monkeypatch):
    """Wildcard CORS origins must fail closed when ENVIRONMENT=production."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("ALLOWED_ORIGINS", "*")
    with pytest.raises(ValueError, match="Wildcard CORS origin"):
        Settings()


def test_production_forces_debug_false(monkeypatch):
    """Production mode must force debug=False even if DEBUG=true is set."""
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DEBUG", "true")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://airaware.example.com/")
    cfg = Settings()
    assert cfg.debug is False
    assert cfg.allowed_origins == ["https://airaware.example.com"]


def test_historical_route_rejects_override_params_and_bad_city():
    """Historical endpoint must enforce trust-boundary params and clean 422 validation."""
    with TestClient(app) as client:
        res_override = client.get("/api/v1/air-quality/historical?city=Delhi&aqi=10")
        assert res_override.status_code == 422

        res_bad_city = client.get("/api/v1/air-quality/historical?city=InvalidCityXYZ123")
        assert res_bad_city.status_code == 422
        assert res_bad_city.json()["detail"]["error"] == "InvalidLocationQuery"


def test_historical_route_hides_raw_exception_details(monkeypatch):
    """Unexpected upstream exceptions on /historical must not leak raw str(exc) traces."""

    class FailingProvider:
        async def get_historical_air_quality(self, **kwargs):
            raise RuntimeError("SECRET_INTERNAL_TRACE_DO_NOT_LEAK")

    monkeypatch.setattr(
        "app.api.routes_historical.get_default_provider",
        lambda: FailingProvider(),
    )
    with TestClient(app) as client:
        res = client.get("/api/v1/air-quality/historical?city=Mumbai&past_days=1")
        assert res.status_code == 502
        body = res.text
        assert "SECRET_INTERNAL_TRACE_DO_NOT_LEAK" not in body
        assert "HistoricalProviderError" in body
