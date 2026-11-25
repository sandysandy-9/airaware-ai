"""Automated unit and integration tests for Stage 1 temporal compatibility & boundary validation."""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import pytest

from app.engine.rolling_window import integrate_rolling_window
from app.providers.models import ProviderModelMetadata, ProviderValidationError
from app.providers.open_meteo import (
    OpenMeteoProvider,
    build_temporal_governance,
    parse_provider_timestamp_to_utc,
)
from app.validation.temporal_validation import (
    DEFAULT_GMAX_SECONDS,
    evaluate_stage1_compatibility,
    integrate_stage1_window,
)


def test_duplicate_timestamps_identical_and_conflicting_synthetic():
    """[SYNTHETIC UNIT TEST] Verify identical duplicates deduplicate while conflicting duplicates are rejected."""
    w_end = datetime(2026, 11, 24, 14, 0, tzinfo=timezone.utc)
    w_start = w_end - timedelta(hours=24)

    # Identical duplicate at +2h
    samples_ident = [
        (w_start + timedelta(hours=h), 50.0) for h in range(0, 25, 2)
    ] + [(w_start + timedelta(hours=2), 50.0)]

    res_ident = integrate_stage1_window(
        samples_ident, pollutant="pm25", unit="µg/m³", window_start_utc=w_start, window_end_utc=w_end
    )
    assert res_ident.coverage_percentage == 100.0
    assert res_ident.time_weighted_mean == 50.0
    assert any("Identical duplicate" in a for a in res_ident.anomalies)

    # Conflicting duplicate at +4h (40.0 vs 80.0) -> ambiguous, timestamp excluded; 2h->6h is 4h <= Gmax
    samples_conflict = [
        (w_start, 50.0),
        (w_start + timedelta(hours=2), 50.0),
        (w_start + timedelta(hours=4), 40.0),
        (w_start + timedelta(hours=4), 80.0),
        (w_start + timedelta(hours=6), 50.0),
    ] + [(w_start + timedelta(hours=h), 50.0) for h in range(8, 25, 2)]

    res_conflict = integrate_stage1_window(
        samples_conflict, pollutant="pm25", unit="µg/m³", window_start_utc=w_start, window_end_utc=w_end
    )
    assert res_conflict.valid_input_points == 12
    assert res_conflict.coverage_percentage == 100.0
    assert res_conflict.time_weighted_mean == 50.0
    assert any("CONFLICTING duplicate" in a for a in res_conflict.anomalies)


def test_missing_boundary_samples_synthetic():
    """[SYNTHETIC UNIT TEST] Verify left or right missing boundaries cannot be fabricated and mark unsupported."""
    w_end = datetime(2026, 11, 24, 14, 0, tzinfo=timezone.utc)
    w_start = w_end - timedelta(hours=24)

    # Missing left boundary: starts at +2h
    samples_no_left = [(w_start + timedelta(hours=h), 60.0) for h in range(2, 25, 2)]
    res_no_left = integrate_stage1_window(
        samples_no_left, pollutant="pm25", unit="µg/m³", window_start_utc=w_start, window_end_utc=w_end
    )
    assert res_no_left.left_boundary_supported is False
    assert res_no_left.right_boundary_supported is True
    assert res_no_left.supported_duration_seconds == 79200.0
    assert res_no_left.stage1_window_supported is False

    # Missing right boundary: ends at +22h
    samples_no_right = [(w_start + timedelta(hours=h), 60.0) for h in range(0, 23, 2)]
    res_no_right = integrate_stage1_window(
        samples_no_right, pollutant="pm25", unit="µg/m³", window_start_utc=w_start, window_end_utc=w_end
    )
    assert res_no_right.left_boundary_supported is True
    assert res_no_right.right_boundary_supported is False
    assert res_no_right.supported_duration_seconds == 79200.0
    assert res_no_right.stage1_window_supported is False


def test_excessive_timestamp_gaps_rejected_synthetic():
    """[SYNTHETIC UNIT TEST] Verify gaps strictly greater than Gmax (14400s) remain uncovered."""
    w_end = datetime(2026, 11, 24, 14, 0, tzinfo=timezone.utc)
    w_start = w_end - timedelta(hours=24)

    # Gap of 4h + 1s between +4h and +8h00m01s
    samples = [
        (w_start, 30.0),
        (w_start + timedelta(hours=4), 50.0),
        (w_start + timedelta(hours=8, seconds=1), 70.0),
        (w_end, 60.0),
    ]
    res = integrate_stage1_window(
        samples,
        pollutant="pm25",
        unit="µg/m³",
        window_start_utc=w_start,
        window_end_utc=w_end,
        g_max_seconds=DEFAULT_GMAX_SECONDS,
    )
    assert res.any_gap_exceeds_gmax is True
    assert res.accepted_intervals_count == 1
    assert res.rejected_intervals_count == 2
    assert res.supported_duration_seconds == 14400.0
    assert res.time_weighted_mean == 40.0
    assert res.stage1_window_supported is False


def test_frozen_stage1_evidence_artifact_parity():
    """[FROZEN STAGE 1 BASELINE VERIFICATION] Verify implementation reproduces stage1_test_evidence_v243.json identically."""
    repo_root = Path(__file__).resolve().parents[2]
    evidence_path = repo_root / "stage1_test_evidence_v243.json"
    assert evidence_path.exists(), "Frozen stage1_test_evidence_v243.json missing"

    data = json.loads(evidence_path.read_text(encoding="utf-8"))
    gmax = float(data["metadata"]["g_max_seconds"])

    for tc in data["test_cases"]:
        ws = datetime.fromisoformat(tc["window"]["start"])
        we = datetime.fromisoformat(tc["window"]["end"])

        raw_samples = []
        for item in tc["input_samples"]:
            ts = datetime.fromisoformat(item["timestamp"])
            c_raw = item["concentration"]
            if c_raw is None:
                val = None
            elif isinstance(c_raw, str):
                val = float(c_raw)  # "nan", "inf"
            else:
                val = float(c_raw)
            raw_samples.append((ts, val))

        pol = "co" if tc["test_id"] == "TEST-20" else "pm25"
        unit = "mg/m³" if pol == "co" else "µg/m³"
        res = integrate_stage1_window(
            raw_samples,
            pollutant=pol,
            unit=unit,
            window_start_utc=ws,
            window_end_utc=we,
            g_max_seconds=gmax,
        )

        assert res.supported_duration_seconds == pytest.approx(tc["supported_duration_seconds"], abs=1e-3), tc["test_id"]
        assert res.coverage_percentage == pytest.approx(tc["coverage_percentage"], abs=1e-3), tc["test_id"]
        assert res.integrated_concentration == pytest.approx(tc["total_integrated_concentration"], abs=1e-2), tc["test_id"]
        if tc["time_weighted_mean"] is None:
            assert res.time_weighted_mean is None, tc["test_id"]
        else:
            assert res.time_weighted_mean == pytest.approx(tc["time_weighted_mean"], abs=1e-3), tc["test_id"]


def test_production_rolling_window_stage1_evidence_20_cases_and_sha256():
    """[FROZEN STAGE 1 BASELINE VERIFICATION] Verify SHA-256 and 20/20 parity of app.engine.rolling_window (including LOW-01 TEST-13)."""
    repo_root = Path(__file__).resolve().parents[2]
    evidence_path = repo_root / "stage1_test_evidence_v243.json"
    raw_bytes = evidence_path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest().upper()
    assert sha256 == "D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773"

    data = json.loads(raw_bytes.decode("utf-8"))
    assert len(data["test_cases"]) == 20
    gmax = float(data["metadata"]["g_max_seconds"])

    for tc in data["test_cases"]:
        ws = datetime.fromisoformat(tc["window"]["start"])
        we = datetime.fromisoformat(tc["window"]["end"])
        raw_samples = []
        for item in tc["input_samples"]:
            ts = datetime.fromisoformat(item["timestamp"])
            c_raw = item["concentration"]
            val = None if c_raw is None else float(c_raw)
            raw_samples.append((ts, val))

        pol = "co" if tc["test_id"] == "TEST-20" else "pm25"
        unit = "mg/m³" if pol == "co" else "µg/m³"
        res = integrate_rolling_window(
            raw_samples,
            pollutant=pol,
            unit=unit,
            window_start_utc=ws,
            window_end_utc=we,
            g_max_seconds=gmax,
        )

        assert res.accepted_intervals_count == len(tc["accepted_intervals"]), tc["test_id"]
        assert res.rejected_intervals_count == len(tc["rejected_intervals"]), tc["test_id"]
        assert res.supported_duration_seconds == pytest.approx(tc["supported_duration_seconds"], abs=1e-3), tc["test_id"]
        assert res.coverage_percentage == pytest.approx(tc["coverage_percentage"], abs=1e-3), tc["test_id"]
        assert res.integrated_concentration == pytest.approx(tc["total_integrated_concentration"], abs=1e-2), tc["test_id"]
        if tc["time_weighted_mean"] is None:
            assert res.time_weighted_mean is None, tc["test_id"]
        else:
            assert res.time_weighted_mean == pytest.approx(tc["time_weighted_mean"], abs=1e-3), tc["test_id"]


@pytest.mark.asyncio
async def test_live_provider_stage1_compatibility_delhi():
    """[LIVE INTEGRATION TEST] Verify live Open-Meteo Delhi response supports full 24h and 8h Stage 1 windows."""
    provider = OpenMeteoProvider(timeout_seconds=15.0)
    now_utc = datetime.now(timezone.utc)
    valid_t = now_utc.replace(minute=0, second=0, microsecond=0)
    start_str = (valid_t - timedelta(days=2)).strftime("%Y-%m-%d")
    end_str = (valid_t + timedelta(days=2)).strftime("%Y-%m-%d")

    norm, _, _ = await provider.fetch_validated_series(
        latitude=28.6139,
        longitude=77.2090,
        start_date=start_str,
        end_date=end_str,
        domain="cams_global",
        timezone_name="Asia/Kolkata",
        target_valid_time_utc=valid_t,
    )

    audit = evaluate_stage1_compatibility(norm, valid_t, g_max_seconds=DEFAULT_GMAX_SECONDS)
    assert audit.index_type == "INDICATIVE_MODEL_INDEX"
    assert audit.indicative_index_eligible is True
    assert len(audit.eligible_pollutants) >= 3
    assert ("pm25" in audit.eligible_pollutants) or ("pm10" in audit.eligible_pollutants)
    assert audit.pollutant_results["pm25"].left_boundary_supported is True
    assert audit.pollutant_results["pm25"].right_boundary_supported is True
    assert audit.pollutant_results["pm25"].coverage_percentage == 100.0
    assert audit.pollutant_results["co"].window_hours == 8
    assert audit.pollutant_results["co"].coverage_percentage == 100.0
    assert norm.temporal_governance is not None
    assert norm.temporal_governance.data_source_type == "MODEL_DERIVED"
    assert norm.temporal_governance.valid_time_vs_retrieval in ("PAST", "CURRENT", "FUTURE")
    assert norm.temporal_governance.model_run_relation in ("ANALYSIS", "FORECAST", "UNKNOWN")


def _verified_cams_meta(issue_dt: datetime) -> ProviderModelMetadata:
    return ProviderModelMetadata(
        domain_requested="cams_global",
        metadata_verified_for_response=True,
        correspondence_reason="Synthetic verified CAMS metadata for unit test",
        model_name="cams_global",
        native_temporal_resolution="UNKNOWN_PENDING_VERIFICATION",
        last_run_initialisation_time=issue_dt,
    )


def test_temporal_governance_forecast_past_valid_at_retrieval_synthetic():
    """[SYNTHETIC UNIT TEST] Forecast valid time earlier than retrieval must stay FORECAST, not HISTORICAL_ANALYSIS."""
    issue_time = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    valid_time = datetime(2026, 11, 25, 6, 0, 0, tzinfo=timezone.utc)
    retrieval_time = datetime(2026, 11, 25, 6, 34, 4, tzinfo=timezone.utc)

    gov = build_temporal_governance(
        metadata=_verified_cams_meta(issue_time),
        valid_time_utc=valid_time,
        retrieval_time_utc=retrieval_time,
        provider_timezone="Asia/Kolkata",
        utc_offset_seconds=19800,
    )

    assert gov.forecast_lead_hours == pytest.approx(18.0)
    assert gov.valid_time_offset_hours == pytest.approx(-0.5678, abs=1e-4)
    assert gov.valid_time_vs_retrieval == "PAST"
    assert gov.model_run_relation == "FORECAST"
    assert gov.data_source_type == "MODEL_DERIVED"


def test_temporal_governance_forecast_future_valid_synthetic():
    """[SYNTHETIC UNIT TEST] Forecast valid time strictly in the future relative to retrieval."""
    issue_time = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    valid_time = datetime(2026, 11, 25, 18, 0, 0, tzinfo=timezone.utc)
    retrieval_time = datetime(2026, 11, 25, 6, 34, 4, tzinfo=timezone.utc)

    gov = build_temporal_governance(
        metadata=_verified_cams_meta(issue_time),
        valid_time_utc=valid_time,
        retrieval_time_utc=retrieval_time,
        provider_timezone="Asia/Kolkata",
        utc_offset_seconds=19800,
    )

    assert gov.forecast_lead_hours == pytest.approx(30.0)
    assert gov.valid_time_vs_retrieval == "FUTURE"
    assert gov.model_run_relation == "FORECAST"
    assert gov.data_source_type == "MODEL_DERIVED"


def test_temporal_governance_valid_time_exact_retrieval_and_analysis_step_synthetic():
    """[SYNTHETIC UNIT TEST] Exact valid==retrieval yields CURRENT; lead==0 yields ANALYSIS; predating issue yields UNKNOWN."""
    issue_time = datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc)
    retrieval_time = datetime(2026, 11, 25, 6, 34, 4, tzinfo=timezone.utc)

    # Exact valid == retrieval (still lead +18.5678h from model_issue_time)
    gov_exact = build_temporal_governance(
        metadata=_verified_cams_meta(issue_time),
        valid_time_utc=retrieval_time,
        retrieval_time_utc=retrieval_time,
        provider_timezone="UTC",
        utc_offset_seconds=0,
    )
    assert gov_exact.valid_time_offset_hours == 0.0
    assert gov_exact.valid_time_vs_retrieval == "CURRENT"
    assert gov_exact.model_run_relation == "FORECAST"
    assert gov_exact.data_source_type == "MODEL_DERIVED"

    # Lead == 0h (exact initialization timestamp of verified run) -> ANALYSIS
    gov_init = build_temporal_governance(
        metadata=_verified_cams_meta(issue_time),
        valid_time_utc=issue_time,
        retrieval_time_utc=retrieval_time,
        provider_timezone="UTC",
        utc_offset_seconds=0,
    )
    assert gov_init.forecast_lead_hours == 0.0
    assert gov_init.valid_time_vs_retrieval == "PAST"
    assert gov_init.model_run_relation == "ANALYSIS"

    # Predating verified model_issue_time (prior cycle whose run metadata is absent) -> UNKNOWN, never ANALYSIS
    prior_time = datetime(2026, 11, 23, 18, 0, 0, tzinfo=timezone.utc)
    gov_prior = build_temporal_governance(
        metadata=_verified_cams_meta(issue_time),
        valid_time_utc=prior_time,
        retrieval_time_utc=retrieval_time,
        provider_timezone="UTC",
        utc_offset_seconds=0,
    )
    assert gov_prior.forecast_lead_hours == pytest.approx(-18.0)
    assert gov_prior.valid_time_vs_retrieval == "PAST"
    assert gov_prior.model_run_relation == "UNKNOWN"


def test_temporal_governance_missing_model_issue_time_synthetic():
    """[SYNTHETIC UNIT TEST] Missing/unverified model_issue_time must preserve nulls and report model_run_relation=UNKNOWN."""
    valid_time = datetime(2026, 11, 25, 6, 0, 0, tzinfo=timezone.utc)
    retrieval_time = datetime(2026, 11, 25, 6, 34, 4, tzinfo=timezone.utc)

    unverified_meta = ProviderModelMetadata(
        domain_requested="auto",
        metadata_verified_for_response=False,
        correspondence_reason="Domain auto does not verify issue time",
        last_run_initialisation_time=None,
    )

    gov = build_temporal_governance(
        metadata=unverified_meta,
        valid_time_utc=valid_time,
        retrieval_time_utc=retrieval_time,
        provider_timezone="Asia/Kolkata",
        utc_offset_seconds=19800,
    )
    assert gov.model_issue_time is None
    assert gov.forecast_lead_hours is None
    assert gov.model_run_age_hours is None
    assert gov.valid_time_vs_retrieval == "PAST"
    assert gov.model_run_relation == "UNKNOWN"
    assert gov.data_source_type == "MODEL_DERIVED"


def test_temporal_governance_missing_or_invalid_timestamps_synthetic():
    """[SYNTHETIC UNIT TEST] Missing, naive, or unparseable valid_time / retrieval_time must raise ProviderValidationError."""
    retrieval_time = datetime(2026, 11, 25, 6, 34, 4, tzinfo=timezone.utc)
    meta = _verified_cams_meta(datetime(2026, 11, 24, 12, 0, 0, tzinfo=timezone.utc))

    # Missing valid_time
    with pytest.raises(ProviderValidationError, match="valid_time"):
        build_temporal_governance(meta, None, retrieval_time, "UTC", 0)

    # Missing retrieval_time
    with pytest.raises(ProviderValidationError, match="retrieval_time"):
        build_temporal_governance(meta, retrieval_time, None, "UTC", 0)

    # Naive valid_time
    with pytest.raises(ProviderValidationError, match="Naive datetime"):
        build_temporal_governance(meta, datetime(2026, 11, 25, 6, 0, 0), retrieval_time, "UTC", 0)

    # Invalid string timestamp
    with pytest.raises(ProviderValidationError, match="Invalid timestamp"):
        build_temporal_governance(meta, "not-a-timestamp", retrieval_time, "UTC", 0)

    # Provider string parser checks empty/malformed strings
    with pytest.raises(ProviderValidationError):
        parse_provider_timestamp_to_utc("", "UTC", 0)
    with pytest.raises(ProviderValidationError):
        parse_provider_timestamp_to_utc("invalid-iso-ts", "UTC", 0)
