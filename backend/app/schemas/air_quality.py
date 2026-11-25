"""Data schemas for AirAware AI environmental data models."""

from datetime import datetime
from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from app.engine.indicative_index import IndicativeModelIndexResult
from app.engine.rolling_window import RollingWindowResult
from app.providers.models import TemporalGovernance


class LocationInfo(BaseModel):
    name: str = Field(..., description="Display name of location or monitoring station")
    city: str
    state: Optional[str] = None
    country: str = "India"
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    station_id: Optional[str] = None


class PollutantDetail(BaseModel):
    code: str
    name: str
    concentration: Optional[float] = None
    unit: str
    sub_index: Optional[int] = None
    category: Optional[str] = None
    color: Optional[str] = None
    is_missing: bool = False
    error: Optional[str] = None
    description: str
    health_effects: str
    sources: str


class AirQualityCurrentResponse(BaseModel):
    location: LocationInfo
    aqi: Optional[int] = None
    category: Optional[str] = None
    color: Optional[str] = None
    dominant_pollutant: Optional[str] = None
    dominant_pollutant_name: Optional[str] = None
    status: str  # "SUCCESS", "INSUFFICIENT_DATA", "ERROR"
    status_message: str
    observation_time: str
    retrieval_time: str
    data_source: str
    data_freshness: str  # "LIVE", "FRESH (<1h)", "DELAYED (1-3h)", "STALE (>3h)"
    pollutants: Dict[str, PollutantDetail]
    methodology: str = "CPCB India National Air Quality Index (NAQI) Standard"


class HistoricalPoint(BaseModel):
    timestamp: str
    aqi: Optional[int] = None
    pm25: Optional[float] = None
    pm10: Optional[float] = None
    no2: Optional[float] = None
    so2: Optional[float] = None
    co: Optional[float] = None
    o3: Optional[float] = None
    dominant_pollutant: Optional[str] = None


class HistoricalTrendsResponse(BaseModel):
    location: LocationInfo
    start_time: str
    end_time: str
    data_source: str
    interval: str = "1 hour"
    data_points: List[HistoricalPoint]
    total_points: int
    note: str = (
        "Model-derived historical hourly atmospheric estimates from Open-Meteo Copernicus CAMS Global, "
        "not physical monitoring station observations."
    )


# --- Stage 3.1 Production Pipeline Schemas (v2.4.3 & Stage 2.1 Compliant) ---


class CoordinateProvenance(BaseModel):
    """Explicitly separates requested user coordinates from snapped model grid coordinates."""

    requested_latitude: float
    requested_longitude: float
    returned_latitude: Optional[float] = None
    returned_longitude: Optional[float] = None
    geodesic_snap_distance_km: Optional[float] = None
    elevation_m: Optional[float] = None
    coordinate_role: str = "MODEL_GRID_ESTIMATE"
    is_physical_station: Literal[False] = False


class ProviderProvenance(BaseModel):
    """Source model, domain, resolution status, and metadata provenance."""

    provider_name: str
    domain_requested: str
    model_name: str
    metadata_verified: bool
    native_temporal_resolution: str = "UNKNOWN_PENDING_VERIFICATION"
    meta_temporal_resolution_seconds: Optional[int] = None
    api_output_frequency_seconds: Optional[int] = None
    update_interval_seconds: Optional[int] = None
    last_run_modification_time: Optional[datetime] = None
    last_run_availability_time: Optional[datetime] = None
    spatial_resolution_note: Optional[str] = None
    cache_hit: bool = False


class PollutantRollingDetail(BaseModel):
    """Pollutant assessment derived strictly from frozen trapezoidal rolling-window integration."""

    code: str
    name: str
    status: Literal["SUFFICIENT", "INSUFFICIENT_DATA", "UNAVAILABLE"]
    concentration: Optional[float] = None
    unit: str
    reported_unit: Optional[str] = None
    sub_index: Optional[int] = None
    category: Optional[str] = None
    color: Optional[str] = None
    averaging_period: str
    rolling_window: Optional[RollingWindowResult] = None
    unavailable_reason: Optional[str] = None
    description: str
    health_effects: str
    sources: str


class FreshnessSummary(BaseModel):
    """Transparent model-run cycle freshness derived from verified timestamps (never 'LIVE')."""

    status: Literal["CURRENT_CYCLE", "AGING_CYCLE", "STALE_CYCLE", "UNKNOWN_RUN_AGE"]
    cache_hit: bool
    disclaimer: str


class AirQualityPipelineResponse(BaseModel):
    """Authoritative Stage 3.1 response for /api/v1/air-quality/current."""

    status: Literal["SUCCESS", "INSUFFICIENT_DATA"]
    status_message: str
    index_type: Literal["INDICATIVE_MODEL_INDEX"] = "INDICATIVE_MODEL_INDEX"
    is_official_cpcb_station_aqi: Literal[False] = False
    location: LocationInfo
    coordinates: CoordinateProvenance
    provider: ProviderProvenance
    indicative_index: IndicativeModelIndexResult
    pollutants: Dict[str, PollutantRollingDetail]
    unavailable_pollutants: List[str]
    temporal_governance: TemporalGovernance
    freshness: FreshnessSummary
    warnings: List[str] = Field(default_factory=list)
