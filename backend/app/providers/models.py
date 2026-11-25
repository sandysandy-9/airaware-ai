"""Pydantic data models and exception types for Stage 2 validated provider ingestion."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ProviderError(Exception):
    """Raised when an upstream provider HTTP request or transport fails."""

    def __init__(self, message: str, http_status: Optional[int] = None, is_timeout: bool = False):
        super().__init__(message)
        self.http_status = http_status
        self.is_timeout = is_timeout


class ProviderValidationError(Exception):
    """Raised when a provider response payload fails structural schema or length validation."""


class NormalizedSample(BaseModel):
    """Single environmental concentration sample normalized to UTC and canonical units."""

    timestamp_utc: datetime
    original_timestamp: str
    value: Optional[float] = None
    unit: str
    validity_flag: str = Field(
        default="VALID",
        description="VALID, NULL, NON_FINITE, NEGATIVE, DUPLICATE_IDENTICAL, CONFLICTING_DUPLICATE",
    )


class PollutantSeriesStats(BaseModel):
    """Audit statistics for a single pollutant array returned by a provider."""

    field_name: str
    canonical_code: str
    present: bool
    is_empty: bool
    reported_unit: Optional[str] = None
    expected_target_unit: str
    timestamp_count: int
    valid_count: int
    null_count: int
    non_finite_count: int
    negative_count: int
    first_timestamp_provider: Optional[str] = None
    last_timestamp_provider: Optional[str] = None
    first_timestamp_utc: Optional[datetime] = None
    last_timestamp_utc: Optional[datetime] = None
    sample_spacings_seconds: List[float] = Field(default_factory=list)
    missing_interval_count: int = 0
    max_gap_seconds: Optional[float] = None


class ProviderModelMetadata(BaseModel):
    """Model provenance and temporal resolution metadata with strict null preservation."""

    domain_requested: str
    metadata_source_url: Optional[str] = None
    metadata_verified_for_response: bool = False
    correspondence_reason: str
    model_name: str = "UNKNOWN_PENDING_VERIFICATION"
    native_temporal_resolution: str = "UNKNOWN_PENDING_VERIFICATION"
    meta_temporal_resolution_seconds: Optional[int] = None
    api_output_frequency_seconds: Optional[int] = None
    spatial_resolution_note: Optional[str] = None
    last_run_initialisation_time: Optional[datetime] = None
    last_run_modification_time: Optional[datetime] = None
    last_run_availability_time: Optional[datetime] = None
    update_interval_seconds: Optional[int] = None
    data_end_time: Optional[datetime] = None


class TemporalGovernance(BaseModel):
    """Separated temporal governance fields distinguishing valid-time timing vs model-run relation."""

    model_issue_time: Optional[datetime] = None
    valid_time: datetime
    retrieval_time: datetime
    model_run_age_hours: Optional[float] = None
    forecast_lead_hours: Optional[float] = None
    valid_time_offset_hours: float
    valid_time_vs_retrieval: Literal["PAST", "CURRENT", "FUTURE"]
    model_run_relation: Literal["ANALYSIS", "FORECAST", "UNKNOWN"]
    data_source_type: Literal["MODEL_DERIVED"] = "MODEL_DERIVED"
    provider_timezone: Optional[str] = None
    provider_utc_offset_seconds: Optional[int] = None


class NormalizedProviderSeries(BaseModel):
    """Complete normalized multi-pollutant series and provenance returned by Open-Meteo adapter."""

    provider_name: str = "Open-Meteo Air Quality API"
    request_url: str
    request_params: Dict[str, Any]
    http_status: int
    retrieval_time_utc: datetime
    requested_latitude: float
    requested_longitude: float
    returned_latitude: Optional[float] = None
    returned_longitude: Optional[float] = None
    geodesic_distance_km: Optional[float] = None
    elevation_m: Optional[float] = None
    provider_timezone: Optional[str] = None
    utc_offset_seconds: Optional[int] = None
    timestamps_utc: List[datetime]
    original_timestamps: List[str]
    pollutant_series: Dict[str, List[NormalizedSample]]
    pollutant_stats: Dict[str, PollutantSeriesStats]
    unavailable_pollutants: List[str] = Field(default_factory=list)
    anomalies: List[str] = Field(default_factory=list)
    metadata: ProviderModelMetadata
    temporal_governance: Optional[TemporalGovernance] = None
    timezone_parsing_notes: List[str] = Field(default_factory=list)
