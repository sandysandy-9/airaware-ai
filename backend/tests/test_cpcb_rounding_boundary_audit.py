"""Stage 3.1.2 & 3.1.3 Independent CPCB Rounding, Boundary, and Input Rejection Audit Tests.

Verifies ROUND_HALF_UP spreadsheet-aligned integer conversion, full-precision
composite maximum & dominant pollutant selection, all 8 criteria pollutant tables,
boundary continuity, invalid input rejection, and CPCB workbook regression cases.
"""

from datetime import datetime, timedelta, timezone
import math
import pytest

from app.engine.cpcb_breakpoints import AQI_CATEGORIES, CPCB_BREAKPOINTS
from app.engine.cpcb_calculator import calculate_cpcb_aqi, calculate_sub_index
from app.engine.indicative_index import compute_indicative_model_index
from app.engine.rolling_window import RollingWindowResult


def _expected_category_for_int(sub_index: int) -> str:
    for cat_name, cat_data in AQI_CATEGORIES.items():
        low, high = cat_data["range"]
        if low <= sub_index <= high:
            return cat_name
    raise AssertionError(f"Unexpected sub_index outside 0..500: {sub_index}")


@pytest.mark.parametrize("pollutant", list(CPCB_BREAKPOINTS.keys()))
def test_all_pollutant_breakpoints_continuity_monotonicity_and_500_cap(pollutant: str):
    """[STAGE 3.1.2 AUDIT] Verify every breakpoint, neighbors, gaps, final bracket, and 500 cap."""
    bps = CPCB_BREAKPOINTS[pollutant]
    test_points = [0.0]

    for idx, bp in enumerate(bps):
        if idx > 0:
            prev_high = bps[idx - 1].c_high
            gap_mid = (prev_high + bp.c_low) / 2.0
            test_points.extend([prev_high + 1e-4, gap_mid, bp.c_low - 1e-4])
        test_points.extend(
            [
                bp.c_low,
                (bp.c_low + bp.c_high) / 2.0,
                bp.c_high - 1e-4,
                bp.c_high,
            ]
        )

    final_high = bps[-1].c_high
    test_points.extend([final_high + 1e-4, final_high + 1.0, final_high * 2.0, 1e6])
    ordered_points = sorted(set(test_points))

    prev_sub = -1
    for val in ordered_points:
        res = calculate_sub_index(pollutant, val)
        assert res.valid is True, f"{pollutant}={val} unexpectedly invalid: {res.error}"
        assert res.sub_index is not None
        assert isinstance(res.sub_index, int)
        assert 0 <= res.sub_index <= 500
        assert res.sub_index >= prev_sub, (
            f"Non-monotonic output for {pollutant} at {val}: {res.sub_index} < {prev_sub}"
        )
        assert res.category == _expected_category_for_int(res.sub_index)
        if val > bps[0].c_high:
            assert res.sub_index >= bps[0].i_high, (
                f"Potential fallback to first breakpoint for {pollutant}={val}: {res}"
            )
        prev_sub = res.sub_index

    # Verify exact first breakpoint, exact final breakpoint, and >final cap
    first_res = calculate_sub_index(pollutant, 0.0)
    assert first_res.sub_index == 0
    assert first_res.category == "GOOD"

    top_res = calculate_sub_index(pollutant, final_high)
    assert top_res.sub_index == 500
    assert top_res.category == "SEVERE"

    cap_res = calculate_sub_index(pollutant, final_high * 3.0)
    assert cap_res.sub_index == 500
    assert cap_res.category == "SEVERE"


@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected_rounded", "expected_category"),
    [
        # x.49 -> always rounds down (even and odd lower integers)
        ("pm10", 9.49, 9, "GOOD"),
        ("pm10", 10.49, 10, "GOOD"),
        ("pm10", 11.49, 11, "GOOD"),
        ("pm10", 50.49, 50, "GOOD"),
        ("pm10", 250.49, 200, "MODERATE"),
        # x.50 with EVEN lower integer -> ROUND_HALF_UP rounds UP (aligned with Excel '0')
        ("pm10", 0.50, 1, "GOOD"),
        ("pm10", 10.50, 11, "GOOD"),
        ("pm10", 50.50, 51, "SATISFACTORY"),
        ("pm10", 250.50, 201, "POOR"),     # 200.5 -> 201 POOR
        ("pm10", 300.50, 251, "POOR"),     # 250.5 -> 251 POOR
        ("nh3", 34.0, 9, "GOOD"),          # exact Ip = 8.5 -> 9 (matches AQI-Calculator.xls D20)
        ("co", 1.05, 53, "SATISFACTORY"),  # exact Ip = 52.5 -> 53 (matches Excel '0')
        ("co", 1.01, 51, "SATISFACTORY"),  # exact Decimal Ip = 50.5 -> 51 SATISFACTORY
        # x.50 with ODD lower integer -> ROUND_HALF_UP rounds UP
        ("pm10", 1.50, 2, "GOOD"),
        ("pm10", 9.50, 10, "GOOD"),
        ("pm10", 11.50, 12, "GOOD"),
        ("pm10", 51.50, 52, "SATISFACTORY"),
        ("pm10", 301.50, 252, "POOR"),
        ("co", 1.03, 52, "SATISFACTORY"),  # Ip = 51.5 -> 52
        # x.51 -> always rounds up (even and odd lower integers)
        ("pm10", 9.51, 10, "GOOD"),
        ("pm10", 10.51, 11, "GOOD"),
        ("pm10", 11.51, 12, "GOOD"),
        ("pm10", 50.51, 51, "SATISFACTORY"),
        ("pm10", 250.51, 201, "POOR"),
    ],
)
def test_integer_rounding_x49_x50_x51_even_and_odd_ties(
    pollutant: str,
    concentration: float,
    expected_rounded: int,
    expected_category: str,
):
    """[STAGE 3.1.3 REGRESSION] Verify DECIMAL ROUND_HALF_UP across x.49, exact .5 ties, and x.51."""
    res = calculate_sub_index(pollutant, concentration)
    assert res.valid is True
    assert res.sub_index == expected_rounded
    assert res.category == expected_category


def test_official_cpcb_workbook_displayed_outputs_regression():
    """[STAGE 3.1.3 WORKBOOK PARITY] Match official CPCB AQI-Calculator.xls Sheet1 sample outputs."""
    # Exact default inputs inside CPCB AQI-Calculator.xls:
    # PM10=121 -> 114, PM2.5=34 -> 57 (56.6667), NO2=8 -> 10, O3=57 -> 57, NH3=34 -> 9 (8.5), AQI=114
    workbook_readings = {
        "pm10": 121.0,
        "pm25": 34.0,
        "no2": 8.0,
        "o3": 57.0,
        "nh3": 34.0,
    }
    res = calculate_cpcb_aqi(workbook_readings)
    assert res.status == "SUCCESS"
    assert res.sub_indices["pm10"].sub_index == 114
    assert res.sub_indices["pm25"].sub_index == 57
    assert res.sub_indices["no2"].sub_index == 10
    assert res.sub_indices["o3"].sub_index == 57
    assert res.sub_indices["nh3"].sub_index == 9
    assert res.sub_indices["nh3"].raw_sub_index == pytest.approx(8.5, abs=1e-9)
    assert res.aqi == 114
    assert res.dominant_pollutant == "pm10"
    assert res.category == "MODERATE"


def test_composite_uses_full_precision_before_rounding_tie_dominant_pollutant():
    """[STAGE 3.1.3 REGRESSION] Full-precision max prevents rounded integer ties from misattributing dominant pollutant."""
    # Both pollutants round to 100, but o3 raw_sub_index (100.40) > pm25 raw_sub_index (100.1667)
    # Using calculate_cpcb_aqi (pm25 is earlier in list):
    # pm25=60.05 -> 100 + (100/30)*0.05 = 100.1667 -> 100
    # o3=100.272 -> 100 + (100/68)*0.272 = 100.4000 -> 100
    res = calculate_cpcb_aqi({"pm25": 60.05, "pm10": 40.0, "o3": 100.272, "no2": 20.0})
    assert res.status == "SUCCESS"
    assert res.sub_indices["pm25"].sub_index == 100
    assert res.sub_indices["o3"].sub_index == 100
    assert res.sub_indices["o3"].raw_sub_index > res.sub_indices["pm25"].raw_sub_index
    assert res.dominant_pollutant == "o3"
    assert res.aqi == 100
    assert res.category == "SATISFACTORY"

    # When dominant pollutant crosses a half-boundary (pm10=50.5 -> 50.5 -> 51 vs pm25=30.24 -> 50.4 -> 50)
    res_cross = calculate_cpcb_aqi({"pm25": 30.24, "pm10": 50.5, "no2": 10.0})
    assert res_cross.status == "SUCCESS"
    assert res_cross.dominant_pollutant == "pm10"
    assert res_cross.aqi == 51
    assert res_cross.category == "SATISFACTORY"

    # Also verify Stage 3.1 indicative index pipeline preserves full-precision tie breaking
    w_end = datetime(2026, 11, 25, 12, 0, tzinfo=timezone.utc)
    w_start_24 = w_end - timedelta(hours=24)
    w_start_8 = w_end - timedelta(hours=8)
    rolling = {
        "pm25": RollingWindowResult(
            pollutant="pm25", unit="µg/m³", window_hours=24,
            window_start_utc=w_start_24, window_end_utc=w_end, window_duration_seconds=86400.0,
            g_max_seconds=14400.0, valid_input_points=25, accepted_intervals_count=24,
            rejected_intervals_count=0, supported_duration_seconds=86400.0, coverage_percentage=100.0,
            minimum_coverage_percentage=75.0, integrated_concentration=2600000.0, time_weighted_mean=60.05,
            left_boundary_supported=True, right_boundary_supported=True, any_gap_exceeds_gmax=False,
            status="SUFFICIENT", stage1_window_supported=True,
            raw_sub_index=100.1667, sub_index=100, sub_index_category="SATISFACTORY", sub_index_color="#84CC16",
        ),
        "o3": RollingWindowResult(
            pollutant="o3", unit="µg/m³", window_hours=8,
            window_start_utc=w_start_8, window_end_utc=w_end, window_duration_seconds=28800.0,
            g_max_seconds=14400.0, valid_input_points=9, accepted_intervals_count=8,
            rejected_intervals_count=0, supported_duration_seconds=28800.0, coverage_percentage=100.0,
            minimum_coverage_percentage=87.5, integrated_concentration=2880000.0, time_weighted_mean=100.272,
            left_boundary_supported=True, right_boundary_supported=True, any_gap_exceeds_gmax=False,
            status="SUFFICIENT", stage1_window_supported=True,
            raw_sub_index=100.5, sub_index=101, sub_index_category="MODERATE", sub_index_color="#EAB308",
        ),
        "no2": RollingWindowResult(
            pollutant="no2", unit="µg/m³", window_hours=24,
            window_start_utc=w_start_24, window_end_utc=w_end, window_duration_seconds=86400.0,
            g_max_seconds=14400.0, valid_input_points=25, accepted_intervals_count=24,
            rejected_intervals_count=0, supported_duration_seconds=86400.0, coverage_percentage=100.0,
            minimum_coverage_percentage=75.0, integrated_concentration=1728000.0, time_weighted_mean=20.0,
            left_boundary_supported=True, right_boundary_supported=True, any_gap_exceeds_gmax=False,
            status="SUFFICIENT", stage1_window_supported=True,
            raw_sub_index=25.0, sub_index=25, sub_index_category="GOOD", sub_index_color="#10B981",
        ),
    }
    ind = compute_indicative_model_index(rolling, [])
    assert ind.status == "AVAILABLE"
    assert ind.index_type == "INDICATIVE_MODEL_INDEX"
    assert ind.is_official_cpcb_station_aqi is False
    assert ind.dominant_pollutant == "o3"
    assert ind.value == 101
    assert ind.category == "MODERATE"

    # Also verify TIE_BREAK_ORDER is NOT wrongly beaten by close raw sub-index when rounded integers tie
    rolling["o3"].raw_sub_index = 100.40
    rolling["o3"].sub_index = 100
    ind_tie = compute_indicative_model_index(rolling, [])
    assert ind_tie.dominant_pollutant == "o3"
    assert ind_tie.value == 100
    assert ind_tie.category == "SATISFACTORY"


@pytest.mark.parametrize(
    ("pollutant", "bad_input"),
    [
        ("pm25", None),
        ("pm25", True),
        ("pm25", False),
        ("pm25", "45.0"),
        ("pm25", "not-a-number"),
        ("pm25", []),
        ("pm25", {}),
        ("pm25", float("nan")),
        ("pm25", float("inf")),
        ("pm25", float("-inf")),
        ("pm25", -1e-6),
        ("pm10", -1.0),
        ("co", float("nan")),
        ("o3", float("inf")),
        ("no2", -0.5),
        ("so2", None),
        ("nh3", True),
        ("pb", -0.01),
        ("voc", 50.0),
        ("pm1", 25.0),
    ],
)
def test_invalid_inputs_never_become_good_sub_index(pollutant: str, bad_input):
    """[STAGE 3.1.2 AUDIT] Ensure every invalid/non-finite/unsupported input fails closed and never becomes GOOD."""
    res = calculate_sub_index(pollutant, bad_input)  # type: ignore[arg-type]
    assert res.valid is False
    assert res.sub_index is None
    assert res.category is None
    assert res.category != "GOOD"
    assert res.error is not None


def test_composite_aqi_rejects_invalid_pollutant_without_silently_scoring_good():
    """[STAGE 3.1.2 AUDIT] Invalid pollutant concentrations cannot satisfy 3-pollutant threshold or become GOOD."""
    res = calculate_cpcb_aqi({"pm25": float("nan"), "pm10": True, "no2": "30"})  # type: ignore[dict-item]
    assert res.status == "INSUFFICIENT_DATA"
    assert res.aqi is None
    assert res.category is None
    assert math.isfinite(res.sub_indices["pm25"].concentration)
