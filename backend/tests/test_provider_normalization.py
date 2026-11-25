"""Automated unit and integration tests for Open-Meteo provider normalization, validation, and error handling."""

from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from unittest.mock import AsyncMock, patch
import httpx
import pytest

from app.providers.models import ProviderError, ProviderValidationError
from app.providers.open_meteo import (
    OpenMeteoProvider,
    haversine_distance_km,
    normalize_open_meteo_response,
    parse_provider_timestamp_to_utc,
)


def _make_synthetic_open_meteo_payload(
    *,
    hours: int = 4,
    pm25_vals=None,
    co_unit: str = "μg/m³",
    include_nh3: bool = True,
    timezone_name: str = "Asia/Kolkata",
    utc_offset: int = 19800,
):
    """Build a synthetic Open-Meteo response payload strictly for isolated unit testing."""
    base = datetime(2026, 11, 24, 0, 0)
    times = [(base + timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(hours)]
    hourly = {
        "time": times,
        "pm2_5": pm25_vals if pm25_vals is not None else [55.0] * hours,
        "pm10": [90.0] * hours,
        "nitrogen_dioxide": [25.0] * hours,
        "sulphur_dioxide": [12.0] * hours,
        "carbon_monoxide": [1200.0] * hours,
        "ozone": [40.0] * hours,
    }
    units = {
        "time": "iso8601",
        "pm2_5": "μg/m³",
        "pm10": "μg/m³",
        "nitrogen_dioxide": "μg/m³",
        "sulphur_dioxide": "μg/m³",
        "carbon_monoxide": co_unit,
        "ozone": "μg/m³",
    }
    if include_nh3:
        hourly["ammonia"] = [None] * hours
        units["ammonia"] = "μg/m³"

    return {
        "latitude": 28.599998,
        "longitude": 77.20001,
        "generationtime_ms": 0.4,
        "utc_offset_seconds": utc_offset,
        "timezone": timezone_name,
        "timezone_abbreviation": "IST",
        "elevation": 214.0,
        "hourly_units": units,
        "hourly": hourly,
    }


def test_successful_provider_response_parsing_synthetic():
    """[SYNTHETIC UNIT TEST] Verify successful normalization, CO unit conversion (µg/m³ -> mg/m³), and provenance."""
    payload = _make_synthetic_open_meteo_payload(hours=3)
    retrieval = datetime(2026, 11, 24, 6, 0, tzinfo=timezone.utc)
    meta_json = {
        "last_run_initialisation_time": int(datetime(2026, 11, 24, 0, 0, tzinfo=timezone.utc).timestamp()),
        "last_run_modification_time": int(datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc).timestamp()),
        "last_run_availability_time": int(datetime(2026, 11, 24, 5, 0, tzinfo=timezone.utc).timestamp()),
        "temporal_resolution_seconds": 3600,
        "update_interval_seconds": 43200,
        "data_end_time": int(datetime(2026, 11, 29, 0, 0, tzinfo=timezone.utc).timestamp()),
    }

    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="cams_global",
        request_url="https://air-quality-api.open-meteo.com/v1/air-quality",
        request_params={"domains": "cams_global"},
        http_status=200,
        retrieval_time_utc=retrieval,
        raw_meta_json=meta_json,
        meta_source_url="https://air-quality-api.open-meteo.com/data/cams_global/static/meta.json",
    )

    assert norm.http_status == 200
    assert norm.pollutant_stats["pm25"].valid_count == 3
    assert norm.pollutant_stats["co"].reported_unit == "μg/m³"
    assert norm.pollutant_stats["co"].expected_target_unit == "mg/m³"
    assert norm.pollutant_series["co"][0].value == pytest.approx(1.2)
    assert "nh3" in norm.unavailable_pollutants
    assert norm.metadata.metadata_verified_for_response is True
    assert norm.metadata.native_temporal_resolution == "UNKNOWN_PENDING_VERIFICATION"


def test_missing_pollutant_fields_synthetic():
    """[SYNTHETIC UNIT TEST] Verify absent optional pollutant field is flagged unavailable without failing."""
    payload = _make_synthetic_open_meteo_payload(hours=3, include_nh3=False)
    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="auto",
        request_url="https://example.test",
        request_params={},
        http_status=200,
        retrieval_time_utc=datetime(2026, 11, 24, 6, 0, tzinfo=timezone.utc),
    )

    assert norm.pollutant_stats["nh3"].present is False
    assert norm.pollutant_stats["nh3"].is_empty is True
    assert "nh3" in norm.unavailable_pollutants
    assert norm.pollutant_series["nh3"] == []
    # Auto domain must never associate metadata timestamps
    assert norm.metadata.metadata_verified_for_response is False
    assert norm.metadata.last_run_initialisation_time is None


def test_null_nan_infinity_and_negative_values_synthetic():
    """[SYNTHETIC UNIT TEST] Verify null, NaN, Infinity, and negative concentrations are rejected safely (never 0.0)."""
    payload = _make_synthetic_open_meteo_payload(
        hours=5,
        pm25_vals=[42.0, None, float("nan"), float("inf"), -18.5],
    )
    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="cams_global",
        request_url="https://example.test",
        request_params={},
        http_status=200,
        retrieval_time_utc=datetime(2026, 11, 24, 6, 0, tzinfo=timezone.utc),
    )

    stats = norm.pollutant_stats["pm25"]
    assert stats.valid_count == 1
    assert stats.null_count == 1
    assert stats.non_finite_count == 2
    assert stats.negative_count == 1

    flags = [s.validity_flag for s in norm.pollutant_series["pm25"]]
    assert flags == ["VALID", "NULL", "NON_FINITE", "NON_FINITE", "NEGATIVE"]
    vals = [s.value for s in norm.pollutant_series["pm25"]]
    assert vals == [42.0, None, None, None, None]


def test_timestamp_and_array_length_mismatch_raises_synthetic():
    """[SYNTHETIC UNIT TEST] Verify timestamp/pollutant array-length mismatch raises ProviderValidationError."""
    payload = _make_synthetic_open_meteo_payload(hours=4)
    payload["hourly"]["pm2_5"] = [10.0, 20.0]  # Mismatch: 2 vs 4 timestamps

    with pytest.raises(ProviderValidationError, match="Array length mismatch for 'pm2_5'"):
        normalize_open_meteo_response(
            payload,
            requested_latitude=28.6139,
            requested_longitude=77.2090,
            domain_requested="cams_global",
            request_url="https://example.test",
            request_params={},
            http_status=200,
            retrieval_time_utc=datetime(2026, 11, 24, 6, 0, tzinfo=timezone.utc),
        )


def test_timezone_conversion_asia_kolkata_to_utc_synthetic():
    """[SYNTHETIC UNIT TEST] Verify Asia/Kolkata (+05:30 / 19800s) timestamps convert accurately to UTC."""
    dt_utc, _ = parse_provider_timestamp_to_utc("2026-11-25T12:00", "Asia/Kolkata", 19800)
    assert dt_utc == datetime(2026, 11, 25, 6, 30, tzinfo=timezone.utc)

    # ISO string with explicit offset preserves exact instant
    dt_utc_off, _ = parse_provider_timestamp_to_utc("2026-11-25T12:00:00+05:30", None, None)
    assert dt_utc_off == datetime(2026, 11, 25, 6, 30, tzinfo=timezone.utc)


def test_geodesic_coordinate_distance_synthetic():
    """[SYNTHETIC UNIT TEST] Verify geodesic snap distance calculation between requested and returned coordinates."""
    # Delhi: 28.6139, 77.2090 -> snapped 28.599998, 77.20001 (~1.77 km)
    dist = haversine_distance_km(28.6139, 77.2090, 28.599998, 77.20001)
    assert 1.5 < dist < 2.2
    assert haversine_distance_km(19.0760, 72.8777, 19.0760, 72.8777) == 0.0


@pytest.mark.asyncio
async def test_provider_http_error_handling_synthetic():
    """[SYNTHETIC UNIT TEST] Verify non-success HTTP status codes raise ProviderError with status metadata."""
    provider = OpenMeteoProvider(timeout_seconds=5.0)
    req = httpx.Request("GET", provider.BASE_URL)
    resp = httpx.Response(status_code=503, text="Upstream Service Unavailable", request=req)

    with patch("httpx.AsyncClient.get", new=AsyncMock(return_value=resp)):
        with pytest.raises(ProviderError) as exc_info:
            await provider.fetch_raw_air_quality(28.6139, 77.2090, "2026-11-24", "2026-11-25")
        assert exc_info.value.http_status == 503
        assert exc_info.value.is_timeout is False


@pytest.mark.asyncio
async def test_provider_timeout_handling_synthetic():
    """[SYNTHETIC UNIT TEST] Verify HTTP request timeouts raise ProviderError with is_timeout=True."""
    provider = OpenMeteoProvider(timeout_seconds=0.5)

    with patch(
        "httpx.AsyncClient.get",
        new=AsyncMock(side_effect=httpx.ReadTimeout("Simulated read timeout")),
    ):
        with pytest.raises(ProviderError) as exc_info:
            await provider.fetch_raw_air_quality(28.6139, 77.2090, "2026-11-24", "2026-11-25")
        assert exc_info.value.is_timeout is True


@pytest.mark.asyncio
async def test_live_provider_delhi_integration():
    """[LIVE INTEGRATION TEST] Query actual Open-Meteo endpoint for Delhi and verify schema & Asia/Kolkata parsing."""
    provider = OpenMeteoProvider(timeout_seconds=15.0)
    now_utc = datetime.now(timezone.utc)
    start_str = (now_utc - timedelta(days=2)).strftime("%Y-%m-%d")
    end_str = (now_utc + timedelta(days=1)).strftime("%Y-%m-%d")

    norm, raw_data, raw_meta = await provider.fetch_validated_series(
        latitude=28.6139,
        longitude=77.2090,
        start_date=start_str,
        end_date=end_str,
        domain="cams_global",
        timezone_name="Asia/Kolkata",
    )

    assert norm.http_status == 200
    assert norm.provider_timezone == "Asia/Kolkata"
    assert norm.utc_offset_seconds == 19800
    assert norm.geodesic_distance_km is not None and norm.geodesic_distance_km < 25.0
    assert norm.pollutant_stats["pm25"].valid_count >= 24
    assert norm.pollutant_stats["co"].reported_unit == "μg/m³"
    assert norm.pollutant_stats["co"].expected_target_unit == "mg/m³"
    assert "nh3" in norm.unavailable_pollutants
    assert raw_meta is not None
    assert norm.metadata.native_temporal_resolution == "UNKNOWN_PENDING_VERIFICATION"


# --- Stage 3.1.1 LOW-02 Regression Tests: Malformed Provider Coordinate Parsing ---


@pytest.mark.parametrize("bad_lat", ["N/A", None, float("nan"), float("inf"), float("-inf"), True, 91.5, -91.0])
def test_malformed_returned_latitude_raises_validation_error_synthetic(bad_lat):
    """[SYNTHETIC UNIT TEST] Malformed or out-of-range provider latitude must raise ProviderValidationError."""
    payload = _make_synthetic_open_meteo_payload()
    payload["latitude"] = bad_lat
    with pytest.raises(ProviderValidationError):
        normalize_open_meteo_response(
            payload,
            requested_latitude=28.6139,
            requested_longitude=77.2090,
            domain_requested="cams_global",
            request_url="https://example.test",
            request_params={},
            http_status=200,
            retrieval_time_utc=datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc),
        )


@pytest.mark.parametrize("bad_lon", ["N/A", None, float("nan"), float("inf"), False, 181.0, -181.0])
def test_malformed_returned_longitude_raises_validation_error_synthetic(bad_lon):
    """[SYNTHETIC UNIT TEST] Malformed or out-of-range provider longitude must raise ProviderValidationError."""
    payload = _make_synthetic_open_meteo_payload()
    payload["longitude"] = bad_lon
    with pytest.raises(ProviderValidationError):
        normalize_open_meteo_response(
            payload,
            requested_latitude=28.6139,
            requested_longitude=77.2090,
            domain_requested="cams_global",
            request_url="https://example.test",
            request_params={},
            http_status=200,
            retrieval_time_utc=datetime(2026, 11, 24, 15, 0, tzinfo=timezone.utc),
        )
