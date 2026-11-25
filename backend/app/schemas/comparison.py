"""Schemas for Stage 3.1 Multi-Location Air Quality Comparison."""

from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.providers.factory import validate_city_input
from app.schemas.air_quality import AirQualityPipelineResponse


class LocationComparisonQuery(BaseModel):
    """Authoritative location query; rejects extra client-supplied AQI/risk overrides."""

    model_config = ConfigDict(extra="forbid")

    city: Optional[str] = Field(None, min_length=1, max_length=64)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)

    @field_validator("city")
    @classmethod
    def _validate_city(cls, v: Optional[str]) -> Optional[str]:
        return validate_city_input(v) if v is not None else None


class MultiLocationCompareRequest(BaseModel):
    """POST request model for /api/v1/air-quality/compare."""

    model_config = ConfigDict(extra="forbid")

    locations: List[LocationComparisonQuery] = Field(..., min_length=2, max_length=6)


class LocationComparisonResultItem(BaseModel):
    """Single city/coordinate entry in a cross-location comparison."""

    requested_location: str
    requested_latitude: float
    requested_longitude: float
    status: Literal["SUCCESS", "INSUFFICIENT_DATA", "PROVIDER_UNAVAILABLE"]
    assessment: Optional[AirQualityPipelineResponse] = None
    error: Optional[str] = None


class ComparisonResponse(BaseModel):
    """Stage 3.1 response for GET and POST /api/v1/air-quality/compare."""

    generated_at_utc: datetime
    index_type: Literal["INDICATIVE_MODEL_INDEX"] = "INDICATIVE_MODEL_INDEX"
    requested_count: int
    successful_count: int
    failed_count: int
    comparison_items: List[LocationComparisonResultItem]
    cleanest_location: Optional[str] = None
    most_polluted_location: Optional[str] = None
    data_integrity_warnings: List[str] = Field(default_factory=list)
