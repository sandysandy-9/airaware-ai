"""Stage 2 compatibility wrapper delegating directly to the production rolling-window and indicative-index engines."""

from datetime import datetime, timedelta
from typing import Dict, List
from pydantic import BaseModel

from app.engine.indicative_index import compute_indicative_model_index
from app.engine.rolling_window import (
    DEFAULT_GMAX_SECONDS,
    POLLUTANT_WINDOW_HOURS,
    RollingWindowResult,
    integrate_rolling_window,
)
from app.providers.models import NormalizedProviderSeries, NormalizedSample

# Preserve Stage 2 type alias cleanly without duplicating logic
Stage1IntegrationResult = RollingWindowResult
integrate_stage1_window = integrate_rolling_window


class Stage1CompatibilityAudit(BaseModel):
    """City-level compatibility summary across all criteria pollutants under Stage 1 rules."""

    valid_time_utc: datetime
    g_max_seconds: float
    pollutant_results: Dict[str, RollingWindowResult]
    eligible_pollutants: List[str]
    insufficient_pollutants: List[str]
    indicative_index_eligible: bool
    indicative_model_index: int | None = None
    indicative_category: str | None = None
    indicative_dominant_pollutant: str | None = None
    index_type: str = "INDICATIVE_MODEL_INDEX"
    eligibility_reason: str


def evaluate_stage1_compatibility(
    normalized: NormalizedProviderSeries,
    valid_time_utc: datetime,
    g_max_seconds: float = DEFAULT_GMAX_SECONDS,
) -> Stage1CompatibilityAudit:
    """Evaluate all 6 criteria pollutants in NormalizedProviderSeries against Stage 1 rules."""
    pollutant_results: Dict[str, RollingWindowResult] = {}

    for canon_code, win_hours in POLLUTANT_WINDOW_HOURS.items():
        samples_list: List[NormalizedSample] = normalized.pollutant_series.get(canon_code, [])
        raw_pairs = [(s.timestamp_utc, s.value) for s in samples_list]
        target_unit = (
            normalized.pollutant_stats[canon_code].expected_target_unit
            if canon_code in normalized.pollutant_stats
            else ("mg/m³" if canon_code == "co" else "µg/m³")
        )
        w_end = valid_time_utc
        w_start = valid_time_utc - timedelta(hours=win_hours)

        pollutant_results[canon_code] = integrate_rolling_window(
            raw_pairs,
            pollutant=canon_code,
            unit=target_unit,
            window_start_utc=w_start,
            window_end_utc=w_end,
            g_max_seconds=g_max_seconds,
        )

    idx_res = compute_indicative_model_index(pollutant_results, normalized.unavailable_pollutants)
    insufficient = [c for c in POLLUTANT_WINDOW_HOURS if c not in idx_res.eligible_pollutants]

    return Stage1CompatibilityAudit(
        valid_time_utc=valid_time_utc,
        g_max_seconds=g_max_seconds,
        pollutant_results=pollutant_results,
        eligible_pollutants=idx_res.eligible_pollutants,
        insufficient_pollutants=insufficient,
        indicative_index_eligible=idx_res.status == "AVAILABLE",
        indicative_model_index=idx_res.value,
        indicative_category=idx_res.category,
        indicative_dominant_pollutant=idx_res.dominant_pollutant,
        eligibility_reason=idx_res.eligibility_reason,
    )
