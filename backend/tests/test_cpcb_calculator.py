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
