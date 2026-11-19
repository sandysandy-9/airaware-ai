"""API routes for verified historical air quality trends."""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from app.providers.factory import get_default_provider, resolve_location
from app.schemas.air_quality import HistoricalTrendsResponse
from app.services.cache_service import cache_service

router = APIRouter(prefix="/air-quality", tags=["Historical Trends"])


@router.get("/historical", response_model=HistoricalTrendsResponse)
async def get_historical_air_quality(
    city: Optional[str] = Query(None, description="City name"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0),
    past_days: int = Query(7, ge=1, le=30, description="Past days of hourly observations (1-30)"),
):
    """Retrieve verified hourly historical observations and CPCB calculations."""
    loc = resolve_location(city_name=city, latitude=latitude, longitude=longitude)
    lat = loc["lat"]
    lon = loc["lon"]
    loc_name = loc["name"]

    cache_key = f"hist:{round(lat, 2)}:{round(lon, 2)}:{past_days}d"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    provider = get_default_provider()
    try:
        trends = await provider.get_historical_air_quality(
            location_name=loc_name,
            latitude=lat,
            longitude=lon,
            past_days=past_days,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch historical observations: {str(e)}")

    cache_service.set(cache_key, trends, ttl=1800)  # 30 min cache for historical
    return trends
