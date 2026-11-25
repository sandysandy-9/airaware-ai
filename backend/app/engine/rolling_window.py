"""Frozen Stage 1 v2.4.3 Piecewise-Linear Trapezoidal Rolling-Window Engine."""

from datetime import datetime, timedelta, timezone
import math
from typing import Dict, List, Literal, Optional, Tuple
from pydantic import BaseModel, Field

from app.engine.cpcb_calculator import calculate_sub_index

POLLUTANT_WINDOW_HOURS: Dict[str, int] = {
    "pm25": 24,
    "pm10": 24,
    "no2": 24,
    "so2": 24,
    "co": 8,
    "o3": 8,
}

# Project-defined coverage eligibility thresholds (NOT official CPCB CAAQMS regulatory station rules)
WINDOW_MIN_COVERAGE_PCT: Dict[int, float] = {
    24: 75.0,
    8: 87.5,
}

DEFAULT_GMAX_SECONDS = 14400.0  # Configurable engineering interpolation limit (4 hours)


class RollingWindowResult(BaseModel):
    """Result of frozen v2.4.3 gap-aware piecewise-linear trapezoidal time integration."""

    pollutant: str
    unit: str
    window_hours: int
    window_start_utc: datetime
    window_end_utc: datetime
    window_duration_seconds: float
    g_max_seconds: float
    valid_input_points: int
    accepted_intervals_count: int
    rejected_intervals_count: int
    rejected_gap_reasons: List[str] = Field(default_factory=list)
    supported_duration_seconds: float
    coverage_percentage: float
    minimum_coverage_percentage: float
    integrated_concentration: float
    time_weighted_mean: Optional[float] = None
    left_boundary_supported: bool
    right_boundary_supported: bool
    any_gap_exceeds_gmax: bool
    max_observed_gap_seconds: Optional[float] = None
    anomalies: List[str] = Field(default_factory=list)
    status: Literal["SUFFICIENT", "INSUFFICIENT_DATA", "UNAVAILABLE"]
    stage1_window_supported: bool
    insufficiency_reason: Optional[str] = None
    raw_sub_index: Optional[float] = None
    sub_index: Optional[int] = None
    sub_index_category: Optional[str] = None
    sub_index_color: Optional[str] = None


def integrate_rolling_window(
    samples: List[Tuple[datetime, Optional[float]]],
    *,
    pollutant: str,
    unit: str,
    window_start_utc: datetime,
    window_end_utc: datetime,
    g_max_seconds: float = DEFAULT_GMAX_SECONDS,
) -> RollingWindowResult:
    """Execute frozen Stage 1 v2.4.3 trapezoidal integration on timestamp-ordered UTC samples."""
    window_duration = (window_end_utc - window_start_utc).total_seconds()
    window_hours = int(round(window_duration / 3600.0))
    if window_duration not in (86400.0, 28800.0):
        raise ValueError(
            f"Exact 24h (86400s) or 8h (28800s) duration window required, got {window_duration}s."
        )

    anomalies: List[str] = []
    if samples:
        is_sorted = all(samples[i][0] <= samples[i + 1][0] for i in range(len(samples) - 1))
        if not is_sorted:
            anomalies.append("Input samples were out-of-order; sorted by UTC timestamp.")

    sorted_raw = sorted(samples, key=lambda x: x[0])

    # Duplicate & invalid sample handling strictly per Stage 1 v2.4.3
    grouped: Dict[datetime, List[Optional[float]]] = {}
    for t, c in sorted_raw:
        t_utc = t.astimezone(timezone.utc) if t.tzinfo else t.replace(tzinfo=timezone.utc)
        grouped.setdefault(t_utc, []).append(c)

    valid_points: List[Tuple[datetime, float]] = []
    for t_utc, vals in grouped.items():
        if len(vals) > 1:
            cleaned = []
            has_invalid = False
            for v in vals:
                if v is None or math.isnan(v) or math.isinf(v) or v < 0.0:
                    has_invalid = True
                else:
                    cleaned.append(float(v))
            if has_invalid:
                anomalies.append(f"Duplicate timestamp {t_utc.isoformat()} contains invalid value(s); rejected.")
                continue
            if abs(max(cleaned) - min(cleaned)) < 1e-6:
                anomalies.append(f"Identical duplicate at {t_utc.isoformat()} deduplicated.")
                valid_points.append((t_utc, cleaned[0]))
            else:
                anomalies.append(
                    f"CONFLICTING duplicate at {t_utc.isoformat()} ({vals}); rejected as ambiguous."
                )
                continue
        else:
            v = vals[0]
            if v is None:
                continue
            if math.isnan(v) or math.isinf(v) or v < 0.0:
                anomalies.append(f"Invalid concentration {v} at {t_utc.isoformat()} excluded.")
                continue
            valid_points.append((t_utc, float(v)))

    accepted_intervals_count = 0
    rejected_intervals_count = 0
    rejected_gap_reasons: List[str] = []
    supported_duration = 0.0
    total_integral = 0.0
    observed_gaps: List[float] = []
    any_exceeds_gmax = False

    left_supported = False
    right_supported = False

    for i in range(len(valid_points) - 1):
        t_i, c_i = valid_points[i]
        t_next, c_next = valid_points[i + 1]
        raw_gap = (t_next - t_i).total_seconds()
        observed_gaps.append(raw_gap)

        if raw_gap <= 0.0:
            continue

        if raw_gap > g_max_seconds:
            any_exceeds_gmax = True
            if max(t_i, window_start_utc) < min(t_next, window_end_utc):
                rejected_intervals_count += 1
                rejected_gap_reasons.append(
                    f"[{t_i.isoformat()} -> {t_next.isoformat()}] gap={raw_gap:.0f}s > Gmax={g_max_seconds:.0f}s"
                )
            continue

        clip_start = max(t_i, window_start_utc)
        clip_end = min(t_next, window_end_utc)
        if clip_start >= clip_end:
            rejected_intervals_count += 1
            rejected_gap_reasons.append(
                f"[{t_i.isoformat()} -> {t_next.isoformat()}] interval does not intersect rolling window"
            )
            continue

        if clip_start == window_start_utc:
            left_supported = True
        if clip_end == window_end_utc:
            right_supported = True

        slope = (c_next - c_i) / raw_gap
        c_a = c_i + slope * (clip_start - t_i).total_seconds()
        c_b = c_i + slope * (clip_end - t_i).total_seconds()

        dur = (clip_end - clip_start).total_seconds()
        integral = ((c_a + c_b) / 2.0) * dur

        accepted_intervals_count += 1
        supported_duration += dur
        total_integral += integral

    coverage_pct = (supported_duration / window_duration) * 100.0
    weighted_mean = (total_integral / supported_duration) if supported_duration > 0.0 else None
    min_cov_pct = WINDOW_MIN_COVERAGE_PCT[window_hours]

    reasons: List[str] = []
    if len(valid_points) == 0 or accepted_intervals_count == 0:
        status: Literal["SUFFICIENT", "INSUFFICIENT_DATA", "UNAVAILABLE"] = "UNAVAILABLE"
        reasons.append("No valid integration intervals exist inside the target window.")
    else:
        if coverage_pct < min_cov_pct:
            reasons.append(f"Coverage {coverage_pct:.2f}% below required {min_cov_pct:.1f}% threshold.")
        if not left_supported:
            reasons.append("Left window boundary is not bracketed within Gmax.")
        if not right_supported:
            reasons.append("Right window boundary is not bracketed within Gmax.")
        status = "SUFFICIENT" if not reasons else "INSUFFICIENT_DATA"

    stage1_supported = status == "SUFFICIENT"
    raw_sub_idx: Optional[float] = None
    sub_idx: Optional[int] = None
    sub_cat: Optional[str] = None
    sub_col: Optional[str] = None
    if stage1_supported and weighted_mean is not None:
        sub_res = calculate_sub_index(pollutant, weighted_mean)
        if sub_res.valid:
            raw_sub_idx = sub_res.raw_sub_index
            sub_idx = sub_res.sub_index
            sub_cat = sub_res.category
            sub_col = sub_res.color
        else:
            status = "INSUFFICIENT_DATA"
            stage1_supported = False
            reasons.append(sub_res.error or "Failed CPCB breakpoint evaluation.")

    return RollingWindowResult(
        pollutant=pollutant,
        unit=unit,
        window_hours=window_hours,
        window_start_utc=window_start_utc,
        window_end_utc=window_end_utc,
        window_duration_seconds=window_duration,
        g_max_seconds=g_max_seconds,
        valid_input_points=len(valid_points),
        accepted_intervals_count=accepted_intervals_count,
        rejected_intervals_count=rejected_intervals_count,
        rejected_gap_reasons=rejected_gap_reasons,
        supported_duration_seconds=round(supported_duration, 4),
        coverage_percentage=round(coverage_pct, 4),
        minimum_coverage_percentage=min_cov_pct,
        integrated_concentration=round(total_integral, 4),
        time_weighted_mean=round(weighted_mean, 4) if weighted_mean is not None else None,
        left_boundary_supported=left_supported,
        right_boundary_supported=right_supported,
        any_gap_exceeds_gmax=any_exceeds_gmax,
        max_observed_gap_seconds=max(observed_gaps) if observed_gaps else None,
        anomalies=anomalies,
        status=status,
        stage1_window_supported=stage1_supported,
        insufficiency_reason="; ".join(reasons) if reasons else None,
        raw_sub_index=raw_sub_idx,
        sub_index=sub_idx,
        sub_index_category=sub_cat,
        sub_index_color=sub_col,
    )
