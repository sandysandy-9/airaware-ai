"""API routes for current air quality observations."""

from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query

from app.providers.factory import get_default_provider, resolve_location, MAJOR_INDIAN_CITIES
from app.schemas.air_quality import AirQualityCurrentResponse
from app.services.cache_service import cache_service

router = APIRouter(prefix="/air-quality", tags=["Air Quality"])


@router.get("/cities", response_model=List[Dict])
async def list_monitored_cities():
    """Return pre-configured major Indian metropolitan monitoring locations."""
    return [
        {
            "id": key,
            "name": val["name"],
            "city": val["city"],
            "state": val["state"],
            "latitude": val["lat"],
            "longitude": val["lon"],
        }
        for key, val in MAJOR_INDIAN_CITIES.items()
    ]


@router.get("/current", response_model=AirQualityCurrentResponse)
async def get_current_air_quality(
    city: Optional[str] = Query(None, description="City name (e.g. 'Delhi', 'Mumbai')"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Latitude coordinate"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Longitude coordinate"),
):
    """Retrieve verified real-time air quality and official CPCB AQI for a location."""
    # Location validation
    loc = resolve_location(city_name=city, latitude=latitude, longitude=longitude)
    lat = loc["lat"]
    lon = loc["lon"]
    loc_name = loc["name"]
    resolved_city = loc.get("city", loc_name)

    # Check cache
    cache_key = f"current:{round(lat, 2)}:{round(lon, 2)}"
    cached = cache_service.get(cache_key)
    if cached:
        return cached

    provider = get_default_provider()
    result = await provider.get_current_air_quality(
        location_name=loc_name,
        latitude=lat,
        longitude=lon,
        city=resolved_city,
    )

    # Cache successful results for 15 minutes
    if result.status == "SUCCESS":
        cache_service.set(cache_key, result, ttl=900)

    return result
