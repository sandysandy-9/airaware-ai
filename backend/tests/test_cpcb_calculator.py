"""Comprehensive unit tests for official CPCB NAQI calculation engine."""

import pytest
from app.engine.cpcb_calculator import (
    calculate_sub_index,
    calculate_cpcb_aqi,
    SubIndexResult,
    CPCBAQIResult,
)


def test_pm25_sub_index_breakpoints():
    """Verify PM2.5 sub-index interpolation at exact CPCB breakpoints."""
    # Good: 0 - 30 -> 0 - 50
    res_0 = calculate_sub_index("pm25", 0.0)
    assert res_0.valid is True
    assert res_0.sub_index == 0
    assert res_0.category == "GOOD"

    res_15 = calculate_sub_index("pm25", 15.0)
    assert res_15.valid is True
    assert res_15.sub_index == 25  # 50/30 * 15 = 25
    assert res_15.category == "GOOD"

    res_30 = calculate_sub_index("pm25", 30.0)
    assert res_30.sub_index == 50
    assert res_30.category == "GOOD"

    # Satisfactory: 31 - 60 -> 51 - 100
    res_60 = calculate_sub_index("pm25", 60.0)
    assert res_60.sub_index == 100
    assert res_60.category == "SATISFACTORY"

    # Moderate: 61 - 90 -> 101 - 200
    res_75 = calculate_sub_index("pm25", 75.0)
    # Ip = (200 - 101) / (90 - 61) * (75 - 61) + 101 = 99/29 * 14 + 101 = 47.79 + 101 = 149
    assert res_75.category == "MODERATE"
    assert 148 <= res_75.sub_index <= 150

    # Poor: 91 - 120 -> 201 - 300
    res_120 = calculate_sub_index("pm25", 120.0)
    assert res_120.sub_index == 300
    assert res_120.category == "POOR"

    # Very Poor: 121 - 250 -> 301 - 400
    res_250 = calculate_sub_index("pm25", 250.0)
    assert res_250.sub_index == 400
    assert res_250.category == "VERY_POOR"

    # Severe: 251 - 350 -> 401 - 500
    res_300 = calculate_sub_index("pm25", 300.0)
    assert res_300.category == "SEVERE"
    assert 401 <= res_300.sub_index <= 500


def test_pm10_sub_index_breakpoints():
    """Verify PM10 sub-index interpolation at exact CPCB breakpoints."""
    res_50 = calculate_sub_index("pm10", 50.0)
    assert res_50.sub_index == 50
    assert res_50.category == "GOOD"

    res_100 = calculate_sub_index("pm10", 100.0)
    assert res_100.sub_index == 100
    assert res_100.category == "SATISFACTORY"

    res_250 = calculate_sub_index("pm10", 250.0)
    assert res_250.sub_index == 200
    assert res_250.category == "MODERATE"

    res_350 = calculate_sub_index("pm10", 350.0)
    assert res_350.sub_index == 300
    assert res_350.category == "POOR"

    res_430 = calculate_sub_index("pm10", 430.0)
    assert res_430.sub_index == 400
    assert res_430.category == "VERY_POOR"


def test_co_sub_index_breakpoints():
    """Verify CO in mg/m³."""
    res_co_1 = calculate_sub_index("co", 1.0)
    assert res_co_1.sub_index == 50
    assert res_co_1.category == "GOOD"

    res_co_10 = calculate_sub_index("co", 10.0)
    assert res_co_10.sub_index == 200
    assert res_co_10.category == "MODERATE"


def test_extreme_values_and_capping():
    """Verify that extreme values above 500 are handled without crashing and capped at 500."""
    res_extreme = calculate_sub_index("pm25", 850.0)
    assert res_extreme.valid is True
    assert res_extreme.sub_index == 500
    assert res_extreme.category == "SEVERE"


def test_negative_concentration_handling():
    """Verify negative concentration is flagged as invalid."""
    res_neg = calculate_sub_index("pm25", -5.0)
    assert res_neg.valid is False
    assert "Invalid negative" in res_neg.error


def test_cpcb_insufficient_data_less_than_three_pollutants():
    """Rule 1: If less than 3 pollutants are monitored, return INSUFFICIENT_DATA."""
    # Only 2 pollutants
    readings = {
        "pm25": 45.0,
        "pm10": 80.0,
    }
    result = calculate_cpcb_aqi(readings)
    assert result.status == "INSUFFICIENT_DATA"
    assert result.aqi is None
    assert result.monitored_pollutants_count == 2
    assert "at least 3 monitored pollutants" in result.status_message


def test_cpcb_insufficient_data_missing_pm():
    """Rule 2: If 3 or more pollutants are present, but neither PM2.5 nor PM10 is monitored, return INSUFFICIENT_DATA."""
    readings = {
        "no2": 45.0,
        "so2": 30.0,
        "co": 1.5,
        "o3": 40.0,
    }
    result = calculate_cpcb_aqi(readings)
    assert result.status == "INSUFFICIENT_DATA"
    assert result.aqi is None
    assert result.has_particulate_matter is False
    assert "mandates that at least one particulate matter" in result.status_message


def test_cpcb_success_calculation_and_dominant_pollutant():
    """Rule 3 & 4: Valid calculation with at least 3 pollutants including PM. Overall AQI is max sub-index."""
    readings = {
        "pm25": 115.0,  # Poor (~283)
        "pm10": 120.0,  # Moderate (~114)
        "no2": 25.0,    # Good (~31)
        "so2": 15.0,    # Good (~19)
        "co": 0.8,      # Good (~40)
    }
    result = calculate_cpcb_aqi(readings)
    assert result.status == "SUCCESS"
    assert result.aqi is not None
    assert result.dominant_pollutant == "pm25"
    assert result.category == "POOR"
    assert result.aqi == result.sub_indices["pm25"].sub_index


def test_cpcb_dominant_pollutant_ozone():
    """Test where ground-level ozone is the dominant pollutant."""
    readings = {
        "pm25": 20.0,   # Good
        "pm10": 40.0,   # Good
        "o3": 250.0,    # Very Poor (~308)
        "no2": 15.0,    # Good
    }
    result = calculate_cpcb_aqi(readings)
    assert result.status == "SUCCESS"
    assert result.dominant_pollutant == "o3"
    assert result.category == "VERY_POOR"


# --- Stage 3.1.1 CRITICAL-01 Regression Tests: Continuous Breakpoint Interpolation ---


@pytest.mark.parametrize(
    ("pollutant", "concentration", "expected_sub_index", "expected_category"),
    [
        # Required 8 continuous gap regression cases (previously fell back to GOOD)
        ("pm25", 30.5, 51, "SATISFACTORY"),
        ("pm25", 60.5, 102, "MODERATE"),
        ("pm25", 90.5, 202, "POOR"),
        ("pm25", 120.5, 300, "POOR"),
        ("pm10", 100.5, 100, "SATISFACTORY"),
        ("co", 1.05, 53, "SATISFACTORY"),
        ("co", 2.05, 101, "MODERATE"),
        ("o3", 100.5, 101, "MODERATE"),
        # Additional continuous gaps across remaining criteria pollutants
        ("pm10", 50.5, 51, "SATISFACTORY"),
        ("pm10", 250.5, 201, "POOR"),
        ("pm10", 350.5, 301, "VERY_POOR"),
        ("pm10", 430.5, 401, "SEVERE"),
        ("pm25", 250.5, 401, "SEVERE"),
        ("no2", 40.5, 51, "SATISFACTORY"),
        ("so2", 80.5, 100, "SATISFACTORY"),
        ("nh3", 200.5, 50, "GOOD"),
        ("pb", 0.505, 51, "SATISFACTORY"),
    ],
)
def test_continuous_fractional_gap_interpolation_synthetic(
    pollutant: str,
    concentration: float,
    expected_sub_index: int,
    expected_category: str,
):
    """Verify continuous concentrations in integer table gaps never fall back to GOOD."""
    res = calculate_sub_index(pollutant, concentration)
    assert res.valid is True
    assert res.sub_index == expected_sub_index
    assert res.category == expected_category


@pytest.mark.parametrize(
    ("concentration", "expected_sub_index", "expected_category"),
    [
        # Exact PM2.5 breakpoints & immediately below/above values
        (0.0, 0, "GOOD"),
        (29.9, 50, "GOOD"),
        (30.0, 50, "GOOD"),
        (30.1, 50, "GOOD"),
        (31.0, 52, "SATISFACTORY"),
        (59.9, 100, "SATISFACTORY"),
        (60.0, 100, "SATISFACTORY"),
        (60.1, 100, "SATISFACTORY"),
        (61.0, 103, "MODERATE"),
        (89.9, 200, "MODERATE"),
        (90.0, 200, "MODERATE"),
        (90.1, 200, "MODERATE"),
        (91.0, 203, "POOR"),
        (119.9, 300, "POOR"),
        (120.0, 300, "POOR"),
        (121.0, 301, "VERY_POOR"),
        (249.9, 400, "VERY_POOR"),
        (250.0, 400, "VERY_POOR"),
        (251.0, 401, "SEVERE"),
        (349.9, 500, "SEVERE"),
        (350.0, 500, "SEVERE"),
        (350.5, 500, "SEVERE"),
        (999.0, 500, "SEVERE"),
    ],
)
def test_pm25_all_breakpoints_and_category_transitions_synthetic(
    concentration: float,
    expected_sub_index: int,
    expected_category: str,
):
    """Verify exact breakpoints, bracket neighbors, extreme values, and monotonicity."""
    res = calculate_sub_index("pm25", concentration)
    assert res.valid is True
    assert res.sub_index == expected_sub_index
    assert res.category == expected_category


@pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf"), -0.01, -10.0, "abc", True, None])
def test_non_finite_and_invalid_inputs_rejected_synthetic(bad_val):
    """Verify non-finite, negative, boolean, and non-numeric values are cleanly rejected."""
    res = calculate_sub_index("pm25", bad_val)  # type: ignore[arg-type]
    assert res.valid is False
    assert res.sub_index is None
    assert res.error is not None

    composite = calculate_cpcb_aqi({"pm25": bad_val, "pm10": 80.0, "no2": 30.0})  # type: ignore[dict-item]
    assert composite.sub_indices["pm25"].valid is False
    assert composite.status == "INSUFFICIENT_DATA"


def test_composite_aqi_reflects_continuous_gap_pm25_synthetic():
    """Verify end-to-end composite AQI computes SATISFACTORY/MODERATE instead of falling back to GOOD."""
    res_sat = calculate_cpcb_aqi({"pm25": 30.5, "pm10": 20.0, "no2": 10.0})
    assert res_sat.status == "SUCCESS"
    assert res_sat.aqi == 51
    assert res_sat.category == "SATISFACTORY"
    assert res_sat.dominant_pollutant == "pm25"

    res_mod = calculate_cpcb_aqi({"pm25": 60.5, "pm10": 20.0, "no2": 10.0})
    assert res_mod.status == "SUCCESS"
    assert res_mod.aqi == 102
    assert res_mod.category == "MODERATE"
    assert res_mod.dominant_pollutant == "pm25"
