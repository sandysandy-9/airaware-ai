"""Comprehensive unit tests for the deterministic recommendation engine."""

import pytest
from app.engine.recommendation_rules import (
    generate_recommendations,
    ActivityType,
    VulnerabilityGroup,
    ExposureDuration,
    AdvisoryLevel,
)


def test_good_aqi_all_activities_low_risk():
    """Under Good air quality, general and sensitive groups have Low Risk advisory."""
    res = generate_recommendations(
        aqi_category="GOOD",
        aqi=35,
        dominant_pollutant="pm25",
        activity="running",
        vulnerability_group="general",
        duration="1-2h",
    )
    assert res.advisory_level == AdvisoryLevel.NORMAL
    assert "low indicative risk" in res.headline.lower()
    assert "safe for all groups" not in res.headline.lower()
    assert "are safe" not in res.headline.lower()
    assert len(res.actionable_precautions) > 0


def test_moderate_aqi_sensitive_escalation():
    """Under Moderate air quality, sensitive cohorts (respiratory) are escalated to High Risk."""
    res = generate_recommendations(
        aqi_category="MODERATE",
        aqi=145,
        dominant_pollutant="pm25",
        activity="running",
        vulnerability_group="respiratory",
        duration="1-2h",
    )
    assert res.advisory_level == AdvisoryLevel.HIGH
    assert "sensitive groups" in res.headline.lower()
    assert any("inhaler" in p.lower() for p in res.actionable_precautions)
    assert "N95" in res.protective_gear


def test_poor_aqi_general_commuting():
    """Under Poor air quality, commuting advises closed windows and vehicle recirculation."""
    res = generate_recommendations(
        aqi_category="POOR",
        aqi=240,
        dominant_pollutant="pm10",
        activity="commuting",
        vulnerability_group="general",
        duration="30-60m",
    )
    assert res.advisory_level == AdvisoryLevel.HIGH
    assert any("recirculation" in p.lower() for p in res.actionable_precautions)
    assert "N95" in res.protective_gear


def test_severe_aqi_emergency():
    """Under Severe air quality, an Emergency Avoid advisory is generated for everyone."""
    res = generate_recommendations(
        aqi_category="SEVERE",
        aqi=450,
        dominant_pollutant="pm25",
        activity="walking",
        vulnerability_group="elderly",
        duration=">2h",
    )
    assert res.advisory_level == AdvisoryLevel.EMERGENCY
    assert "emergency" in res.headline.lower()
    assert any("halted" in p.lower() or "lockdown" in res.indoor_guidance.lower() for p in res.actionable_precautions)


def test_dominant_pollutant_ozone_caveat():
    """Ground-level ozone triggers afternoon sunlight specific caution."""
    res = generate_recommendations(
        aqi_category="MODERATE",
        aqi=120,
        dominant_pollutant="o3",
        activity="cycling",
        vulnerability_group="general",
        duration="30-60m",
    )
    assert any("Ozone Alert" in p for p in res.actionable_precautions)


def test_invalid_input_resilience():
    """Invalid enum values fall back gracefully to safe defaults without crashing."""
    res = generate_recommendations(
        aqi_category="NON_EXISTENT_CATEGORY",
        activity="underwater_basket_weaving",
        vulnerability_group="martian",
        duration="10_years",
    )
    assert res.activity == ActivityType.WALKING
    assert res.vulnerability_group == VulnerabilityGroup.GENERAL
    assert res.duration == ExposureDuration.THIRTY_TO_SIXTY_MIN
    assert res.advisory_level is not None
