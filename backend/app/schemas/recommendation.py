"""Schemas for Personalised Action and Recommendation requests and responses."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.engine.recommendation_rules import (
    ActivityType,
    VulnerabilityGroup,
    ExposureDuration,
    AdvisoryLevel,
)


class RecommendationRequest(BaseModel):
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    city: Optional[str] = None
    activity: ActivityType = ActivityType.WALKING
    vulnerability_group: VulnerabilityGroup = VulnerabilityGroup.GENERAL
    duration: ExposureDuration = ExposureDuration.THIRTY_TO_SIXTY_MIN
    # Optional override if client already has verified AQI
    aqi: Optional[int] = None
    aqi_category: Optional[str] = None
    dominant_pollutant: Optional[str] = None


class RecommendationResponse(BaseModel):
    location_name: Optional[str] = None
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
