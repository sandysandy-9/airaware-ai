"""Schemas for Multi-Location Comparison."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.air_quality import AirQualityCurrentResponse


class LocationComparisonItem(BaseModel):
    city_or_location: str
    latitude: float
    longitude: float
    air_quality: AirQualityCurrentResponse


class ComparisonResponse(BaseModel):
    generated_at: str
    comparison_items: List[LocationComparisonItem]
    cleanest_location: Optional[str] = None
    most_polluted_location: Optional[str] = None
    data_integrity_warning: Optional[str] = None
