"""Data schemas for AirAware AI environmental data models."""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


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
    note: str = "Real historical hourly environmental measurements retrieved from atmospheric monitoring models."
