"""API Integration and Security tests using FastAPI TestClient."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.providers.open_meteo import normalize_open_meteo_response
from app.services.cache_service import cache_service

client = TestClient(app)


def _mock_pipeline_assessment(pm25_val: float = 115.0, sufficient: bool = True):
    anchor = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    hours_ist = [
        (anchor + timedelta(hours=5, minutes=30) - timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M")
        for k in range(30, -1, -1)
    ]
    n = len(hours_ist)
    payload = {
        "latitude": 28.6,
        "longitude": 77.2,
        "timezone": "Asia/Kolkata",
        "utc_offset_seconds": 19800,
        "hourly": {
            "time": hours_ist,
            "pm2_5": [pm25_val] * n if sufficient else [None] * n,
            "pm10": [120.0] * n if sufficient else [None] * n,
            "nitrogen_dioxide": [30.0] * n,
            "sulphur_dioxide": [15.0] * n if sufficient else [None] * n,
            "carbon_monoxide": [900.0] * n if sufficient else [None] * n,
            "ozone": [55.0] * n if sufficient else [None] * n,
        },
        "hourly_units": {"pm2_5": "µg/m³", "carbon_monoxide": "μg/m³"},
    }
    meta = {
        "last_run_initialisation_time": int((anchor - timedelta(hours=4)).timestamp()),
        "last_run_availability_time": int((anchor - timedelta(hours=1)).timestamp()),
        "last_run_modification_time": int((anchor - timedelta(hours=1)).timestamp()),
        "temporal_resolution_seconds": 3600,
        "update_interval_seconds": 21600,
    }
    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="cams_global",
        request_url="https://example.test",
        request_params={},
        http_status=200,
        retrieval_time_utc=anchor,
        raw_meta_json=meta,
        target_valid_time_utc=anchor,
    )
    return norm, payload, meta


def test_health_endpoint():
    """Verify system health check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "CPCB" in data["aqi_standard"]


def test_list_cities():
    """Verify pre-configured Indian cities endpoint."""
    response = client.get("/api/v1/air-quality/cities")
    assert response.status_code == 200
    cities = response.json()
    assert len(cities) >= 10
    city_names = [c["name"] for c in cities]
    assert "New Delhi" in city_names
    assert "Mumbai" in city_names
    assert "Bengaluru" in city_names


def test_recommendations_rejects_client_aqi_override_and_uses_backend_pipeline_synthetic():
    """[HIGH-01 REGRESSION] Recommendations must compute authoritative index server-side and reject client overrides."""
    cache_service.clear()
    # 1. Spoofed body fields must fail schema validation (422)
    spoofed_payload = {
        "city": "New Delhi",
        "activity": "running",
        "vulnerability_group": "respiratory",
        "duration": "1-2h",
        "aqi": 15,
        "aqi_category": "GOOD",
        "dominant_pollutant": "co",
    }
    spoof_resp = client.post("/api/v1/recommendations", json=spoofed_payload)
    assert spoof_resp.status_code == 422

    # 2. Query override attempts must also be rejected (422)
    query_spoof = client.post(
        "/api/v1/recommendations?aqi=10",
        json={"city": "New Delhi", "activity": "running"},
    )
    assert query_spoof.status_code == 422

    # 3. Valid request uses backend pipeline (PM2.5=115 -> POOR 283), never client overrides
    norm, payload_raw, meta = _mock_pipeline_assessment(pm25_val=115.0, sufficient=True)
    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        new=AsyncMock(return_value=(norm, payload_raw, meta)),
    ):
        ok_resp = client.post(
            "/api/v1/recommendations",
            json={
                "city": "New Delhi",
                "activity": "running",
                "vulnerability_group": "respiratory",
                "duration": "1-2h",
            },
        )
    assert ok_resp.status_code == 200
    data = ok_resp.json()
    assert data["index_type"] == "INDICATIVE_MODEL_INDEX"
    assert data["aqi"] == 283
    assert data["aqi_category"] == "POOR"
    assert data["dominant_pollutant"] == "pm25"
    assert data["advisory_level"] == "VERY_HIGH_RISK"
    assert "N95" in data["protective_gear"]


def test_recommendations_returns_503_when_indicative_index_insufficient_synthetic():
    """[HIGH-01 REGRESSION] Insufficient authoritative data returns 503 instead of guessing."""
    cache_service.clear()
    norm, payload_raw, meta = _mock_pipeline_assessment(sufficient=False)
    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        new=AsyncMock(return_value=(norm, payload_raw, meta)),
    ):
        resp = client.post(
            "/api/v1/recommendations",
            json={"city": "New Delhi", "activity": "walking"},
        )
    assert resp.status_code == 503
    assert resp.json()["detail"]["error"] == "IndicativeIndexUnavailable"


@pytest.mark.asyncio
async def test_ai_chat_rejects_client_context_and_uses_server_grounding_synthetic():
    """[STAGE 3.2] AI chat rejects manipulated client context (422) and uses backend-grounded pipeline cleanly."""
    cache_service.clear()
    # 1. Manipulated current_context or comparison_context is rejected (422)
    spoof_resp = client.post(
        "/api/v1/ai/chat",
        json={
            "message": "Is air safe?",
            "current_context": {"aqi": 340, "category": "VERY_POOR"},
        },
    )
    assert spoof_resp.status_code == 422

    cmp_spoof = client.post(
        "/api/v1/ai/chat",
        json={
            "message": "Compare",
            "comparison_context": [{"aqi": 10}],
        },
    )
    assert cmp_spoof.status_code == 422

    # 2. Server-grounded request succeeds via backend pipeline + deterministic fallback
    norm, payload_raw, meta = _mock_pipeline_assessment(pm25_val=115.0, sufficient=True)
    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        new=AsyncMock(return_value=(norm, payload_raw, meta)),
    ):
        ok_resp = client.post(
            "/api/v1/ai/chat",
            json={"message": "Which pollutant is dominant in New Delhi?", "city": "New Delhi"},
        )
    assert ok_resp.status_code == 200
    body = ok_resp.json()
    assert body["grounded_in_data"] is True
    assert body["explanation_mode"] == "deterministic_fallback"
    assert body["verified_context"]["indicative_index_value"] == 283
    assert body["verified_context"]["dominant_pollutant"] == "pm25"
    assert body["verified_context"]["index_type"] == "INDICATIVE_MODEL_INDEX"
    assert body["verified_context"]["is_official_cpcb_station_aqi"] is False
    assert "pm25" in body["reply"].lower() or "particulate matter" in body["reply"].lower()
    assert "340" not in body["reply"]


def test_coordinate_validation_bounds():
    """Security/Validation: verify invalid coordinates are rejected by Pydantic validation."""
    # Latitude > 90
    response = client.get("/api/v1/air-quality/current?latitude=120.0&longitude=77.0")
    assert response.status_code == 422

    # Longitude < -180
    response = client.get("/api/v1/air-quality/current?latitude=28.0&longitude=-250.0")
    assert response.status_code == 422
