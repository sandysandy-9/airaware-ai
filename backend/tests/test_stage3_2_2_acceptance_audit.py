"""Stage 3.2.2 Independent Acceptance Audit Tests (Concurrency, Snapshot Isolation & Recommendation Safety).

Strictly additive tests; modifies zero production modules.
"""

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from unittest.mock import AsyncMock, patch
import pytest

from app.engine.recommendation_rules import (
    AdvisoryLevel,
    evaluate_assessment_recommendations,
    generate_recommendations,
)
from app.providers.open_meteo import normalize_open_meteo_response
from app.schemas.ai_chat import AIChatRequest
from app.services.ai_service import AIAssistantService
from app.services.air_quality_service import air_quality_service
from app.services.cache_service import cache_service


def _fixture_for_city(
    *,
    lat: float,
    lon: float,
    pm25: float,
    no2: float = 30.0,
    so2: float = 15.0,
    sufficient: bool = True,
    include_pm: bool = True,
    stale_h: int = 1,
    meta_missing: bool = False,
    future: bool = False,
    past_forecast: bool = False,
):
    now_h = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    target_valid = now_h + timedelta(hours=3) if future else (now_h - timedelta(hours=2) if past_forecast else now_h)
    hours_ist = [
        (target_valid + timedelta(hours=5, minutes=30) - timedelta(hours=k)).strftime("%Y-%m-%dT%H:%M")
        for k in range(30, -1, -1)
    ]
    n = len(hours_ist)
    payload = {
        "latitude": round(lat, 1),
        "longitude": round(lon, 1),
        "timezone": "Asia/Kolkata",
        "utc_offset_seconds": 19800,
        "hourly": {
            "time": hours_ist,
            "pm2_5": [pm25] * n if (sufficient and include_pm) else [None] * n,
            "pm10": [120.0] * n if (sufficient and include_pm) else [None] * n,
            "nitrogen_dioxide": [no2] * n,
            "sulphur_dioxide": [so2] * n if sufficient else [None] * n,
            "carbon_monoxide": [900.0] * n if sufficient else [None] * n,
            "ozone": [55.0] * n if sufficient else [None] * n,
        },
        "hourly_units": {"pm2_5": "µg/m³", "carbon_monoxide": "μg/m³"},
    }
    if meta_missing:
        meta = None
    elif past_forecast:
        meta = {
            "last_run_initialisation_time": int((now_h - timedelta(hours=18)).timestamp()),
            "last_run_availability_time": int((now_h - timedelta(hours=16)).timestamp()),
            "last_run_modification_time": int((now_h - timedelta(hours=16)).timestamp()),
            "data_end_time": int((now_h + timedelta(hours=48)).timestamp()),
            "temporal_resolution_seconds": 3600,
            "update_interval_seconds": 43200,
        }
    else:
        meta = {
            "last_run_initialisation_time": int((now_h - timedelta(hours=stale_h + 2)).timestamp()),
            "last_run_availability_time": int((now_h - timedelta(hours=stale_h)).timestamp()),
            "last_run_modification_time": int((now_h - timedelta(hours=stale_h)).timestamp()),
            "data_end_time": int((now_h + timedelta(hours=48)).timestamp()),
            "temporal_resolution_seconds": 3600,
            "update_interval_seconds": 21600,
        }
    norm = normalize_open_meteo_response(
        payload,
        requested_latitude=lat,
        requested_longitude=lon,
        domain_requested="cams_global",
        request_url="https://example.test",
        request_params={},
        http_status=200,
        retrieval_time_utc=now_h,
        raw_meta_json=meta,
        target_valid_time_utc=target_valid,
    )
    return norm, payload, meta


@pytest.mark.asyncio
async def test_audit_b_c_concurrent_requests_and_preference_isolation(caplog):
    """[AUDIT B & C] Concurrent requests across locations/preferences stay isolated with zero snapshot cross-talk or sensitive logging."""
    cache_service.clear()
    caplog.set_level(logging.INFO)
    svc = AIAssistantService()

    async def _side_effect(latitude, longitude, **kwargs):
        await asyncio.sleep(0.02)
        if abs(latitude - 28.6139) < 0.1:
            return _fixture_for_city(lat=latitude, lon=longitude, pm25=115.0)
        return _fixture_for_city(lat=latitude, lon=longitude, pm25=20.0)

    with patch(
        "app.services.air_quality_service.OpenMeteoProvider.fetch_validated_series",
        side_effect=_side_effect,
    ):
        # Run 2 requests for same location with different sensitivity preferences AND a third for Mumbai concurrently
        r_delhi_gen, r_delhi_resp, r_mumbai = await asyncio.gather(
            svc.generate_response(
                AIChatRequest(
                    message="Should I walk?",
                    city="New Delhi",
                    activity="walking",
                    sensitivity_preference="general",
                )
            ),
            svc.generate_response(
                AIChatRequest(
                    message="Should I run?",
                    city="New Delhi",
                    activity="running",
                    sensitivity_preference="respiratory",
                )
            ),
            svc.generate_response(
                AIChatRequest(
                    message="Should I cycle?",
                    city="Mumbai",
                    activity="cycling",
                    sensitivity_preference="elderly",
                )
            ),
        )

    # Context and index isolation
    assert r_delhi_gen.verified_context.location_name == "New Delhi"
    assert r_delhi_gen.verified_context.indicative_index_value == 283
    assert r_delhi_gen.verified_context.advisory_level == "HIGH_RISK"

    assert r_delhi_resp.verified_context.location_name == "New Delhi"
    assert r_delhi_resp.verified_context.indicative_index_value == 283
    assert r_delhi_resp.verified_context.advisory_level == "VERY_HIGH_RISK"

    assert r_mumbai.verified_context.location_name == "Mumbai"
    assert r_mumbai.verified_context.indicative_index_value < 150
    assert r_delhi_gen.verified_context.integrity_sha256 != r_delhi_resp.verified_context.integrity_sha256

    # Ensure personal sensitivity preferences are NOT logged
    logged_text = " ".join(rec.getMessage() for rec in caplog.records).lower()
    assert "respiratory" not in logged_text
    assert "elderly" not in logged_text


def test_audit_b_source_assessment_mutation_does_not_mutate_snapshot():
    """[AUDIT B] Mutating original AirQualityPipelineResponse after snapshot construction leaves snapshot intact."""
    norm, _, _ = _fixture_for_city(lat=28.6139, lon=77.2090, pm25=115.0)
    assessment = air_quality_service.build_assessment_from_normalized(
        location_name="New Delhi",
        city="Delhi",
        state="Delhi",
        normalized=norm,
        target_valid_time_utc=norm.temporal_governance.valid_time,
        cache_hit=False,
    )
    eval_res = evaluate_assessment_recommendations(assessment)
    snap = AIAssistantService()._build_verified_snapshot(assessment=assessment, eval_res=eval_res)

    assessment.pollutants["pm25"].concentration = 9999.0
    assessment.warnings.append("MUTATED_EXTERNAL_WARNING")
    assert snap.pollutants["pm25"].concentration == 115.0
    assert "MUTATED_EXTERNAL_WARNING" not in snap.canonical_snapshot_json


def test_audit_d_recommendation_safety_complete_matrix():
    """[AUDIT D] Verify every insufficient, missing-PM, stale, unknown, and dominant scenario."""
    assert generate_recommendations(None).advisory_level == AdvisoryLevel.UNAVAILABLE
    assert generate_recommendations("UNKNOWN_CAT").advisory_level == AdvisoryLevel.UNAVAILABLE

    for label, kwargs, exp_status, rule_prefix in [
        ("insufficient", dict(sufficient=False), "INSUFFICIENT_DATA", "RULE-GATE-INDEX-SUFFICIENCY"),
        ("missing_pm", dict(sufficient=True, include_pm=False), "INSUFFICIENT_DATA", "RULE-GATE-INDEX-SUFFICIENCY"),
        ("stale_cycle", dict(stale_h=12), "AVAILABLE", "RULE-TEMPORAL-STALE_CYCLE"),
        ("unknown_meta", dict(meta_missing=True), "AVAILABLE", "RULE-TEMPORAL-UNKNOWN_RUN_AGE"),
        ("past_forecast", dict(past_forecast=True), "AVAILABLE", "RULE-TEMPORAL-AGING_CYCLE-PAST-FORECAST"),
        ("future_valid", dict(future=True), "AVAILABLE", "RULE-TEMPORAL-CURRENT_CYCLE-FUTURE"),
    ]:
        norm, _, _ = _fixture_for_city(lat=28.6139, lon=77.2090, pm25=115.0, **kwargs)
        assess = air_quality_service.build_assessment_from_normalized(
            location_name="New Delhi",
            city="Delhi",
            state="Delhi",
            normalized=norm,
            target_valid_time_utc=norm.temporal_governance.valid_time,
            cache_hit=False,
        )
        ev = evaluate_assessment_recommendations(assess)
        assert ev.status == exp_status, label
        assert any(r.rule_id.startswith(rule_prefix) for r in ev.triggered_rules), label
        if exp_status == "INSUFFICIENT_DATA":
            assert ev.recommendation is None
