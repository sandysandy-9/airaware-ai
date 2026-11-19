"""Abstract Base Class for Environmental Data Providers."""

from abc import ABC, abstractmethod
from typing import Optional
from app.schemas.air_quality import AirQualityCurrentResponse, HistoricalTrendsResponse


class BaseAirQualityProvider(ABC):
    """Abstract interface defining required provider methods."""

    name: str

    @abstractmethod
    async def get_current_air_quality(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        city: Optional[str] = None,
    ) -> AirQualityCurrentResponse:
        """Fetch live environmental measurements, validate, and compute official CPCB AQI."""
        pass

    @abstractmethod
    async def get_historical_air_quality(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        past_days: int = 7,
    ) -> HistoricalTrendsResponse:
        """Fetch verified hourly historical observations."""
        pass
