"""Stage 3.1 Production Pipeline & API Endpoint Tests (Synthetic Unit Tests & Live Integration Tests)."""

import asyncio
from datetime import datetime, timedelta, timezone
import threading
import time
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.core.logging import redact_secrets
from app.core.rate_limiter import SlidingWindowRateLimiter, rate_limiter
from app.engine.indicative_index import compute_indicative_model_index
from app.engine.rolling_window import RollingWindowResult, integrate_rolling_window
from app.main import app
from app.providers.factory import resolve_location
from app.providers.models import ProviderError, ProviderValidationError
from app.providers.open_meteo import normalize_open_meteo_response
from app.services.air_quality_service import AirQualityPipelineService
from app.services.cache_service import TTLCache, cache_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    cache_service.clear()
    rate_limiter.reset()
    yield
    cache_service.clear()
    rate_limiter.reset()


def _build_synthetic_72h_payload(
    *,
    anchor_utc: datetime,
    pm25_val: float = 95.0,
    pm10_val: float = 120.0,
    no2_val: float = 35.0,
    so2_val: float = 18.0,
    co_ug_val: float = 1500.0,
    o3_val: float = 65.0,
    include_pm: bool = True,
    omit_pollutants: set[str] | None = None,
    missing_hours_indices: set[int] | None = None,
    lat_returned: float = 28.599998,
    lon_returned: float = 77.20001,
):
    """Build deterministic synthetic 72h hourly Open-Meteo payload centered around anchor_utc in IST."""
    omit = omit_pollutants or set()
    missing_idx = missing_hours_indices or set()
    # Anchor start at -48h IST
    start_utc = anchor_utc - timedelta(hours=48)
    times = [(start_utc + timedelta(hours=i) + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%dT%H:%M") for i in range(73)]

    def _arr(val):
        return [None if i in missing_idx else val for i in range(73)]

    hourly = {"time": times}
    units = {"time": "iso8601"}

    mapping = {
        "pm2_5": (pm25_val if include_pm else None, "μg/m³"),
        "pm10": (pm10_val if include_pm else None, "μg/m³"),
        "nitrogen_dioxide": (no2_val, "μg/m³"),
        "sulphur_dioxide": (so2_val, "μg/m³"),
        "carbon_monoxide": (co_ug_val, "μg/m³"),
        "ozone": (o3_val, "μg/m³"),
        "ammonia": (None, "μg/m³"),
    }
    for k, (v, u) in mapping.items():
        if k in omit:
            continue
        hourly[k] = [None] * 73 if v is None else _arr(v)
        units[k] = u

    meta = {
        "last_run_initialisation_time": int((anchor_utc - timedelta(hours=18)).timestamp()),
        "last_run_modification_time": int((anchor_utc - timedelta(hours=8)).timestamp()),
        "last_run_availability_time": int((anchor_utc - timedelta(hours=8)).timestamp()),
        "temporal_resolution_seconds": 3600,
        "update_interval_seconds": 43200,
        "data_end_time": int((anchor_utc + timedelta(hours=72)).timestamp()),
    }

    payload = {
        "latitude": lat_returned,
        "longitude": lon_returned,
        "generationtime_ms": 0.3,
        "utc_offset_seconds": 19800,
        "timezone": "Asia/Kolkata",
        "timezone_abbreviation": "IST",
        "elevation": 214.0,
        "hourly_units": units,
        "hourly": hourly,
    }
    return payload, meta


# --- 1. Core Pipeline & Engine Synthetic Tests ---


def test_resolve_location_preserves_exact_coordinates_synthetic():
    """[SYNTHETIC UNIT TEST] Custom coordinates near a city must NOT be overwritten by city centroid."""
    loc = resolve_location(latitude=28.5000, longitude=77.1000)
    assert loc["lat"] == 28.5000
    assert loc["lon"] == 77.1000
    assert "28.5000" in loc["name"]

    # Partial coordinate pair must raise ValueError
    with pytest.raises(ValueError, match="Both 'latitude' and 'longitude'"):
        resolve_location(latitude=28.5000, longitude=None)


def test_secret_redaction_filter_synthetic():
    """[SYNTHETIC UNIT TEST] Verify logging helper strips credentials and tokens."""
    raw = "Error calling service with GEMINI_API_KEY=AIzaSyDummySecretValue1234567890 and Bearer abc.def.ghi"
    scrubbed = redact_secrets(raw)
    assert "AIzaSyDummySecretValue1234567890" not in scrubbed
    assert "abc.def.ghi" not in scrubbed
    assert "[REDACTED_SECRET]" in scrubbed


def test_pipeline_valid_indicative_index_and_dominant_pollutant_synthetic():
    """[SYNTHETIC UNIT TEST] Verify rolling windows feed INDICATIVE_MODEL_INDEX and attribute PM2.5 properly."""
    anchor = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)
    retrieval = anchor + timedelta(minutes=25)
    payload, meta = _build_synthetic_72h_payload(anchor_utc=anchor, pm25_val=95.0, co_ug_val=1500.0)

    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="cams_global",
        request_url="https://air-quality-api.open-meteo.com/v1/air-quality",
        request_params={"domains": "cams_global"},
        http_status=200,
        retrieval_time_utc=retrieval,
        raw_meta_json=meta,
        meta_source_url="https://air-quality-api.open-meteo.com/data/cams_global/static/meta.json",
        target_valid_time_utc=anchor,
    )

    svc = AirQualityPipelineService()
    res = svc.build_assessment_from_normalized(
        normalized=norm,
        location_name="New Delhi",
        city="Delhi",
        state="Delhi",
        target_valid_time_utc=anchor,
    )

    assert res.status == "SUCCESS"
    assert res.index_type == "INDICATIVE_MODEL_INDEX"
    assert res.is_official_cpcb_station_aqi is False
    assert res.indicative_index.status == "AVAILABLE"
    assert res.indicative_index.value is not None and 201 <= res.indicative_index.value <= 300
    assert res.indicative_index.dominant_pollutant == "pm25"
    assert res.pollutants["co"].unit == "mg/m³"
    assert res.pollutants["co"].concentration == pytest.approx(1.5)
    assert res.pollutants["nh3"].status == "UNAVAILABLE"
    assert res.pollutants["nh3"].concentration is None
    assert res.temporal_governance.valid_time_vs_retrieval == "PAST"
    assert res.temporal_governance.model_run_relation == "FORECAST"
    assert res.temporal_governance.data_source_type == "MODEL_DERIVED"
    assert res.freshness.status == "CURRENT_CYCLE"


def test_indicative_index_insufficient_when_pm_missing_synthetic():
    """[SYNTHETIC UNIT TEST] Eligibility fails cleanly when both PM2.5 and PM10 are unavailable."""
    anchor = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)
    payload, meta = _build_synthetic_72h_payload(anchor_utc=anchor, include_pm=False)

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
    svc = AirQualityPipelineService()
    res = svc.build_assessment_from_normalized(
        normalized=norm,
        location_name="Test",
        city="Test",
        state="IN",
        target_valid_time_utc=anchor,
    )
    assert res.status == "INSUFFICIENT_DATA"
    assert res.indicative_index.status == "INSUFFICIENT_DATA"
    assert res.indicative_index.value is None
    assert res.indicative_index.has_particulate_matter is False


def test_insufficient_rolling_window_coverage_blocks_pollutant_synthetic():
    """[SYNTHETIC UNIT TEST] A >4h gap causing <75% coverage invalidates that pollutant's sub-index."""
    anchor = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)
    # In 72h series, index 48 is anchor (valid_time), indices 24..48 are the 24h window.
    # Knock out 10 consecutive hours in window (indices 30..39 -> 10h gap > Gmax, leaving <75% coverage).
    w_end = anchor
    w_start = w_end - timedelta(hours=24)
    samples = [
        (w_start + timedelta(hours=h), 80.0)
        for h in range(25)
        if h not in range(6, 17)  # 11h gap [5h..17h] = 12h missing -> 50% coverage < 75%
    ]
    res = integrate_rolling_window(
        samples, pollutant="pm25", unit="µg/m³", window_start_utc=w_start, window_end_utc=w_end
    )
    assert res.status == "INSUFFICIENT_DATA"
    assert res.stage1_window_supported is False
    assert res.coverage_percentage == 50.0
    assert res.sub_index is None

    # Confirm index calculation refuses insufficient PM2.5 if PM10 also insufficient
    comp = compute_indicative_model_index({"pm25": res}, ["nh3"])
    assert comp.status == "INSUFFICIENT_DATA"
    assert comp.value is None


def test_unverified_auto_provenance_synthetic():
    """[SYNTHETIC UNIT TEST] Verify domain='auto' preserves UNKNOWN model_run_relation and UNKNOWN_RUN_AGE."""
    anchor = datetime(2026, 11, 25, 6, 0, tzinfo=timezone.utc)
    payload, meta = _build_synthetic_72h_payload(anchor_utc=anchor)

    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="auto",
        request_url="https://example.test",
        request_params={"domains": "auto"},
        http_status=200,
        retrieval_time_utc=anchor,
        raw_meta_json=meta,
        target_valid_time_utc=anchor,
    )
    res = AirQualityPipelineService().build_assessment_from_normalized(
        normalized=norm,
        location_name="Delhi",
        city="Delhi",
        state="Delhi",
        target_valid_time_utc=anchor,
    )
    assert res.provider.metadata_verified is False
    assert res.temporal_governance.model_issue_time is None
    assert res.temporal_governance.model_run_relation == "UNKNOWN"
    assert res.freshness.status == "UNKNOWN_RUN_AGE"


# --- 2. Stage 3.1 API Route Tests (Synthetic Mocks & Validation) ---


def test_api_health_and_cities_provenance():
    """Verify /health and /cities expose INDICATIVE_MODEL_INDEX & non-station provenance."""
    h_resp = client.get("/health")
    assert h_resp.status_code == 200
    h_data = h_resp.json()
    assert h_data["status"] == "healthy"
    assert h_data["index_type"] == "INDICATIVE_MODEL_INDEX"

    c_resp = client.get("/api/v1/air-quality/cities")
    assert c_resp.status_code == 200
    cities = c_resp.json()
    assert len(cities) >= 10
    assert all(c["coordinate_role"] == "REFERENCE_CITY_CENTER" for c in cities)
    assert all(c["not_a_monitoring_station"] is True for c in cities)


def test_api_current_rejects_client_overrides_and_bad_coords():
    """[SYNTHETIC API TEST] Trust boundary and bounds checks on GET /api/v1/air-quality/current."""
    # Client AQI override must be rejected
    r_override = client.get("/api/v1/air-quality/current?city=delhi&aqi=45")
    assert r_override.status_code == 422
    assert r_override.json()["detail"]["error"] == "TrustBoundaryViolation"

    # Single coordinate without pair must be rejected
    r_half = client.get("/api/v1/air-quality/current?latitude=28.6139")
    assert r_half.status_code == 422

    # Unknown city must be rejected cleanly
    r_unk = client.get("/api/v1/air-quality/current?city=NonExistentCityXYZ")
    assert r_unk.status_code == 422


def test_api_current_provider_timeout_and_http_error_no_stack_trace():
    """[SYNTHETIC API TEST] Timeout returns 504, HTTP error returns 503, and no raw traceback leaks."""
    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        new=AsyncMock(side_effect=ProviderError("Timed out reading from https://secret-internal", is_timeout=True)),
    ):
        r_to = client.get("/api/v1/air-quality/current?city=delhi")
        assert r_to.status_code == 504
        body = r_to.json()
        assert body["detail"]["error"] == "ProviderTimeout"
        assert "Traceback" not in str(body)

    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        new=AsyncMock(side_effect=ProviderError("HTTP 502 Bad Gateway", http_status=502)),
    ):
        r_err = client.get("/api/v1/air-quality/current?city=mumbai")
        assert r_err.status_code == 503
        assert r_err.json()["detail"]["error"] == "ProviderUnavailable"


def test_api_current_caching_preserves_retrieval_time_synthetic():
    """[SYNTHETIC API TEST] Second request hits cache while preserving original retrieval_time_utc."""
    anchor = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    payload, meta = _build_synthetic_72h_payload(anchor_utc=anchor)
    orig_retrieval = anchor + timedelta(seconds=30)
    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="cams_global",
        request_url="https://air-quality-api.open-meteo.com/v1/air-quality",
        request_params={"domains": "cams_global"},
        http_status=200,
        retrieval_time_utc=orig_retrieval,
        raw_meta_json=meta,
        meta_source_url="https://air-quality-api.open-meteo.com/data/cams_global/static/meta.json",
        target_valid_time_utc=anchor,
    )

    mock_fetch = AsyncMock(return_value=(norm, payload, meta))
    with patch("app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series", new=mock_fetch):
        r1 = client.get("/api/v1/air-quality/current?city=delhi")
        r2 = client.get("/api/v1/air-quality/current?city=delhi")

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert mock_fetch.await_count == 1  # Avoided duplicate upstream call
    d1, d2 = r1.json(), r2.json()
    assert d1["provider"]["cache_hit"] is False
    assert d2["provider"]["cache_hit"] is True
    assert d1["temporal_governance"]["retrieval_time"] == d2["temporal_governance"]["retrieval_time"]


def test_api_compare_get_and_post_validation_and_partial_failure_synthetic():
    """[SYNTHETIC API TEST] Verify GET & POST /compare validation, ranking, and partial provider failures."""
    # Validation: < 2 locations -> 422
    assert client.get("/api/v1/air-quality/compare?cities=delhi").status_code == 422
    # Validation: > 6 locations -> 422
    assert client.get("/api/v1/air-quality/compare?cities=delhi,mumbai,chennai,kolkata,pune,jaipur,kochi").status_code == 422
    # Validation: client AQI override in POST body -> 422
    r_forbid = client.post(
        "/api/v1/air-quality/compare",
        json={"locations": [{"city": "delhi", "aqi": 10}, {"city": "mumbai"}]},
    )
    assert r_forbid.status_code == 422

    anchor = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    async def _side_effect(latitude, longitude, **kwargs):
        if abs(latitude - 28.6139) < 0.1:
            p, m = _build_synthetic_72h_payload(anchor_utc=anchor, pm25_val=110.0)
        elif abs(latitude - 19.0760) < 0.1:
            p, m = _build_synthetic_72h_payload(anchor_utc=anchor, pm25_val=45.0, lat_returned=19.1, lon_returned=72.9)
        else:
            raise ProviderError("Simulated failure for third location", is_timeout=True)
        n = normalize_open_meteo_response(
            p,
            requested_latitude=latitude,
            requested_longitude=longitude,
            domain_requested="cams_global",
            request_url="https://example.test",
            request_params={},
            http_status=200,
            retrieval_time_utc=anchor,
            raw_meta_json=m,
            target_valid_time_utc=anchor,
        )
        return n, p, m

    with patch("app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series", side_effect=_side_effect):
        r_cmp = client.get("/api/v1/air-quality/compare?cities=delhi,mumbai,chennai")

    assert r_cmp.status_code == 200
    body = r_cmp.json()
    assert body["index_type"] == "INDICATIVE_MODEL_INDEX"
    assert body["requested_count"] == 3
    assert body["successful_count"] == 2
    assert body["failed_count"] == 1
    assert "Mumbai" in body["cleanest_location"]
    assert "New Delhi" in body["most_polluted_location"]
    assert body["comparison_items"][2]["status"] == "PROVIDER_UNAVAILABLE"


# --- Stage 3.1.1 Remediation Regression Tests (MEDIUM-01, MEDIUM-02, MEDIUM-03, LOW-02) ---


def test_comparison_requires_two_valid_indices_and_warns_timestamps_synthetic():
    """[SYNTHETIC API TEST - MEDIUM-01] Rankings require >=2 AVAILABLE indices; insufficient/skewed cases emit warnings."""
    anchor = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    # Case A: 1 AVAILABLE + 1 failed -> ranking fields MUST be null + warning
    async def _one_success_one_fail(latitude, longitude, **kwargs):
        if abs(latitude - 28.6139) < 0.1:
            p, m = _build_synthetic_72h_payload(anchor_utc=anchor, pm25_val=110.0)
            n = normalize_open_meteo_response(
                p,
                requested_latitude=latitude,
                requested_longitude=longitude,
                domain_requested="cams_global",
                request_url="https://example.test",
                request_params={},
                http_status=200,
                retrieval_time_utc=anchor,
                raw_meta_json=m,
                target_valid_time_utc=anchor,
            )
            return n, p, m
        raise ProviderError("Simulated failure", is_timeout=False)

    with patch("app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series", side_effect=_one_success_one_fail):
        r_one = client.get("/api/v1/air-quality/compare?cities=delhi,mumbai")
    assert r_one.status_code == 200
    b_one = r_one.json()
    assert b_one["successful_count"] == 1
    assert b_one["failed_count"] == 1
    assert b_one["cleanest_location"] is None
    assert b_one["most_polluted_location"] is None
    assert any("require at least 2" in w for w in b_one["data_integrity_warnings"])

    cache_service.clear()

    # Case B: 2 unavailable / failing locations -> both rankings null + warnings
    async def _both_fail(latitude, longitude, **kwargs):
        raise ProviderError("Both unavailable", is_timeout=True)

    with patch("app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series", side_effect=_both_fail):
        r_none = client.get("/api/v1/air-quality/compare?cities=delhi,mumbai")
    assert r_none.status_code == 200
    b_none = r_none.json()
    assert b_none["successful_count"] == 0
    assert b_none["failed_count"] == 2
    assert b_none["cleanest_location"] is None
    assert b_none["most_polluted_location"] is None
    assert any("require at least 2" in w for w in b_none["data_integrity_warnings"])

    cache_service.clear()

    # Case C: 1 AVAILABLE + 1 INSUFFICIENT_DATA -> INSUFFICIENT_DATA excluded, rankings null
    async def _one_avail_one_insufficient(latitude, longitude, **kwargs):
        if abs(latitude - 28.6139) < 0.1:
            p, m = _build_synthetic_72h_payload(anchor_utc=anchor, pm25_val=95.0)
        else:
            p, m = _build_synthetic_72h_payload(
                anchor_utc=anchor,
                include_pm=False,
                omit_pollutants={"pm2_5", "pm10"},
                lat_returned=19.1,
                lon_returned=72.9,
            )
        n = normalize_open_meteo_response(
            p,
            requested_latitude=latitude,
            requested_longitude=longitude,
            domain_requested="cams_global",
            request_url="https://example.test",
            request_params={},
            http_status=200,
            retrieval_time_utc=anchor,
            raw_meta_json=m,
            target_valid_time_utc=anchor,
        )
        return n, p, m

    with patch("app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series", side_effect=_one_avail_one_insufficient):
        r_insuff = client.get("/api/v1/air-quality/compare?cities=delhi,mumbai")
    assert r_insuff.status_code == 200
    b_insuff = r_insuff.json()
    assert b_insuff["cleanest_location"] is None
    assert b_insuff["most_polluted_location"] is None
    assert any("INSUFFICIENT_DATA" in w for w in b_insuff["data_integrity_warnings"])

    cache_service.clear()

    # Case D: Differing valid_time, model_issue_time, and retrieval_time (>=60s skew) emit all warnings
    async def _skewed_timestamps(latitude, longitude, **kwargs):
        is_delhi = abs(latitude - 28.6139) < 0.1
        loc_anchor = anchor if is_delhi else (anchor - timedelta(hours=1))
        retrieval_dt = anchor if is_delhi else (anchor - timedelta(minutes=10))
        init_epoch = int((anchor - timedelta(hours=4)).timestamp()) if is_delhi else int((anchor - timedelta(hours=10)).timestamp())
        p, m = _build_synthetic_72h_payload(
            anchor_utc=loc_anchor,
            pm25_val=95.0 if is_delhi else 45.0,
            lat_returned=28.6 if is_delhi else 19.1,
            lon_returned=77.2 if is_delhi else 72.9,
        )
        m["last_run_initialisation_time"] = init_epoch
        n = normalize_open_meteo_response(
            p,
            requested_latitude=latitude,
            requested_longitude=longitude,
            domain_requested="cams_global",
            request_url="https://example.test",
            request_params={},
            http_status=200,
            retrieval_time_utc=retrieval_dt,
            raw_meta_json=m,
            target_valid_time_utc=loc_anchor,
        )
        return n, p, m

    with patch("app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series", side_effect=_skewed_timestamps):
        r_skew = client.get("/api/v1/air-quality/compare?cities=delhi,mumbai")
    assert r_skew.status_code == 200
    w_list = r_skew.json()["data_integrity_warnings"]
    assert any("valid_time" in w for w in w_list)
    assert any("initialization cycles" in w for w in w_list)
    assert any("retrieval_time" in w for w in w_list)


def test_ttl_cache_bounded_eviction_expiry_and_thread_safety_synthetic():
    """[SYNTHETIC UNIT TEST - MEDIUM-02] Bounded LRU eviction, active TTL expiry, non-extending reads, and thread safety."""
    cache = TTLCache(default_ttl_seconds=2, max_size=3)
    cache.set("k1", "v1", ttl=10)
    cache.set("k2", "v2", ttl=10)
    cache.set("k3", "v3", ttl=10)
    assert cache.size() == 3

    # Touch k1 so k2 becomes least-recently-used
    assert cache.get("k1") == "v1"
    cache.set("k4", "v4", ttl=10)
    assert cache.size() == 3
    assert cache.get("k2") is None
    assert cache.get("k1") == "v1"
    assert cache.get("k3") == "v3"
    assert cache.get("k4") == "v4"

    # Expiry is fixed to write time; repeated gets must NOT extend TTL
    short_cache = TTLCache(default_ttl_seconds=1, max_size=4)
    short_cache.set("short", "val", ttl=0.05)  # type: ignore[arg-type]
    assert short_cache.get("short") == "val"
    time.sleep(0.08)
    assert short_cache.get("short") is None
    assert short_cache.size() == 0

    # Multi-threaded stress check
    concurrent_cache = TTLCache(default_ttl_seconds=10, max_size=20)
    errors = []

    def _worker(tid: int):
        try:
            for i in range(50):
                concurrent_cache.set(f"t{tid}:{i}", i)
                _ = concurrent_cache.get(f"t{tid}:{i}")
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(idx,)) for idx in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert concurrent_cache.size() <= 20


@pytest.mark.asyncio
async def test_pipeline_inflight_coalescing_cleanup_and_freshness_provenance_synthetic():
    """[SYNTHETIC UNIT TEST - MEDIUM-02] Concurrent identical requests coalesce to 1 fetch and clean up locks safely."""
    cache_service.clear()
    svc = AirQualityPipelineService()
    anchor = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    orig_retrieval = anchor - timedelta(minutes=25)
    payload, meta = _build_synthetic_72h_payload(anchor_utc=anchor, pm25_val=105.0)
    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=28.6139,
        requested_longitude=77.2090,
        domain_requested="cams_global",
        request_url="https://example.test",
        request_params={},
        http_status=200,
        retrieval_time_utc=orig_retrieval,
        raw_meta_json=meta,
        target_valid_time_utc=anchor,
    )

    call_count = 0

    async def _slow_fetch(**kwargs):
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return norm, payload, meta

    with patch.object(svc.provider, "fetch_validated_series", side_effect=_slow_fetch):
        results = await asyncio.gather(
            *[
                svc.assess_location(
                    location_name="New Delhi",
                    city="Delhi",
                    state="Delhi",
                    latitude=28.6139,
                    longitude=77.2090,
                    valid_time_utc=anchor,
                )
                for _ in range(5)
            ]
        )

    assert call_count == 1
    assert svc.inflight_lock_count == 0
    fresh_flags = [r.provider.cache_hit for r in results]
    assert fresh_flags.count(False) == 1
    assert fresh_flags.count(True) == 4
    for r in results:
        assert r.temporal_governance.retrieval_time == orig_retrieval


def test_rate_limiter_uses_environment_setting_and_multiple_limits_synthetic(monkeypatch):
    """[SYNTHETIC UNIT TEST - MEDIUM-03] SlidingWindowRateLimiter honors AIRAWARE_RATE_LIMIT_PER_MIN across distinct limits."""
    monkeypatch.setenv("AIRAWARE_RATE_LIMIT_PER_MIN", "2")
    cfg_low = Settings()
    assert cfg_low.rate_limit_requests_per_minute == 2
    limiter_low = SlidingWindowRateLimiter.from_settings(cfg_low, window_seconds=60)
    limiter_low.check("10.0.0.1")
    limiter_low.check("10.0.0.1")
    with pytest.raises(Exception) as exc_low:
        limiter_low.check("10.0.0.1")
    assert getattr(exc_low.value, "status_code", None) == 429

    monkeypatch.setenv("AIRAWARE_RATE_LIMIT_PER_MIN", "5")
    cfg_mid = Settings()
    assert cfg_mid.rate_limit_requests_per_minute == 5
    limiter_mid = SlidingWindowRateLimiter.from_settings(cfg_mid, window_seconds=60)
    for _ in range(5):
        limiter_mid.check("10.0.0.2")
    with pytest.raises(Exception) as exc_mid:
        limiter_mid.check("10.0.0.2")
    assert getattr(exc_mid.value, "status_code", None) == 429


def test_api_current_malformed_provider_coords_returns_502_synthetic():
    """[SYNTHETIC API TEST - LOW-02] ProviderValidationError on malformed coords yields controlled 502, never 500."""
    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        new=AsyncMock(side_effect=ProviderValidationError("Malformed 'latitude' in provider response: 'N/A'")),
    ):
        resp = client.get("/api/v1/air-quality/current?city=delhi")
    assert resp.status_code == 502
    detail = resp.json()["detail"]
    assert detail["error"] == "InvalidProviderResponse"


# --- 3. Live Provider Integration Tests (Real Open-Meteo CAMS Global) ---


def test_live_api_current_delhi():
    """[LIVE INTEGRATION TEST] End-to-end GET /api/v1/air-quality/current against live Open-Meteo CAMS Global."""
    resp = client.get("/api/v1/air-quality/current?latitude=28.6139&longitude=77.2090")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert data["index_type"] == "INDICATIVE_MODEL_INDEX"
    assert data["is_official_cpcb_station_aqi"] is False
    assert data["coordinates"]["requested_latitude"] == 28.6139
    assert data["coordinates"]["requested_longitude"] == 77.2090
    assert data["coordinates"]["is_physical_station"] is False
    assert data["coordinates"]["geodesic_snap_distance_km"] is not None
    assert data["pollutants"]["nh3"]["status"] == "UNAVAILABLE"
    assert data["pollutants"]["co"]["unit"] == "mg/m³"
    assert data["temporal_governance"]["data_source_type"] == "MODEL_DERIVED"
    assert data["indicative_index"]["value"] is not None


def test_live_api_compare_delhi_and_chennai():
    """[LIVE INTEGRATION TEST] End-to-end GET /api/v1/air-quality/compare across live Delhi & Chennai."""
    resp = client.get("/api/v1/air-quality/compare?cities=delhi,chennai")
    assert resp.status_code == 200
    data = resp.json()
    assert data["requested_count"] == 2
    assert data["successful_count"] == 2
    assert data["failed_count"] == 0
    assert data["cleanest_location"] is not None
    assert data["most_polluted_location"] is not None
    assert data["comparison_items"][0]["assessment"]["index_type"] == "INDICATIVE_MODEL_INDEX"
