"""Schemas for Personalised Action and Recommendation requests and responses."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.engine.recommendation_rules import (
    ActivityType,
    VulnerabilityGroup,
    ExposureDuration,
    TriggeredRule,
)
from app.providers.factory import validate_city_input


class RecommendationRequest(BaseModel):
    """Authoritative location + non-sensitive personal context for recommendations.

    Client-supplied AQI, categories, pollutant concentrations, or dominant pollutants
    are strictly forbidden; the backend computes air-quality context from verified provider data only.
    """

    model_config = ConfigDict(extra="forbid")

    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    city: Optional[str] = Field(None, min_length=1, max_length=64)
    activity: ActivityType = ActivityType.WALKING
    vulnerability_group: VulnerabilityGroup = VulnerabilityGroup.GENERAL
    duration: ExposureDuration = ExposureDuration.THIRTY_TO_SIXTY_MIN

    @field_validator("city")
    @classmethod
    def _validate_city(cls, v: Optional[str]) -> Optional[str]:
        return validate_city_input(v) if v is not None else None


class RecommendationResponse(BaseModel):
    """Explainable Stage 3.2 deterministic recommendation response grounded in INDICATIVE_MODEL_INDEX."""

    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"] = "AVAILABLE"
    location_name: Optional[str] = None
    index_type: Literal["INDICATIVE_MODEL_INDEX"] = "INDICATIVE_MODEL_INDEX"
    is_official_cpcb_station_aqi: Literal[False] = False
    guidance_classification: str = (
        "PRODUCT_RULE_ENGINE_GUIDANCE (distinct from official CPCB NAQI numerical breakpoints)"
    )
    aqi: Optional[int] = None
    aqi_category: str
    dominant_pollutant: Optional[str] = None
    activity: str
    vulnerability_group: str
    duration: str
    advisory_level: str
    headline: str
    actionable_precautions: List[str]
    protective_gear: Optional[str] = None
    indoor_guidance: str
    disclaimer: str
    triggered_rules: List[TriggeredRule] = Field(default_factory=list)
    pollutant_context_status: Dict[str, str] = Field(default_factory=dict)
    data_freshness: str = "UNKNOWN_RUN_AGE"
    temporal_summary: Dict[str, Any] = Field(default_factory=dict)
    uncertainty_notes: List[str] = Field(default_factory=list)
