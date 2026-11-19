"""API routes for multi-location air quality comparison."""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter

from app.providers.factory import get_default_provider, resolve_location
from app.schemas.comparison import ComparisonResponse, LocationComparisonItem
from app.services.cache_service import cache_service

router = APIRouter(prefix="/air-quality", tags=["Comparison"])


class LocationQuery(BaseModel):
    city: Optional[str] = None
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)


class MultiLocationRequest(BaseModel):
    locations: List[LocationQuery] = Field(..., min_length=2, max_length=6)


@router.post("/compare", response_model=ComparisonResponse)
async def compare_locations(req: MultiLocationRequest):
    """Compare real-time air quality metrics across multiple urban locations."""
    provider = get_default_provider()
    now_iso = datetime.now(timezone.utc).isoformat()

    tasks = []
    resolved_locations = []
    for loc_q in req.locations:
        loc = resolve_location(city_name=loc_q.city, latitude=loc_q.latitude, longitude=loc_q.longitude)
        resolved_locations.append(loc)
        
        # Check cache first
        c_key = f"current:{round(loc['lat'], 2)}:{round(loc['lon'], 2)}"
        cached = cache_service.get(c_key)
        if cached:
            # Wrap in completed future
            future = asyncio.Future()
            future.set_result(cached)
            tasks.append(future)
        else:
            tasks.append(
                provider.get_current_air_quality(
                    location_name=loc["name"],
                    latitude=loc["lat"],
                    longitude=loc["lon"],
                    city=loc.get("city", loc["name"]),
                )
            )

    results = await asyncio.gather(*tasks, return_exceptions=True)

    items: List[LocationComparisonItem] = []
    valid_with_aqi = []

    for loc, res in zip(resolved_locations, results):
        if isinstance(res, Exception):
            continue
        items.append(
            LocationComparisonItem(
                city_or_location=loc["name"],
                latitude=loc["lat"],
                longitude=loc["lon"],
                air_quality=res,
            )
        )
        if res.aqi is not None:
            valid_with_aqi.append(res)

    cleanest = None
    most_polluted = None
    warning = None

    if valid_with_aqi:
        # Sort by AQI
        valid_with_aqi.sort(key=lambda x: x.aqi)
        cleanest = f"{valid_with_aqi[0].location.name} (AQI {valid_with_aqi[0].aqi})"
        most_polluted = f"{valid_with_aqi[-1].location.name} (AQI {valid_with_aqi[-1].aqi})"

    # Check for timestamp skew or stale data
    timestamps = [it.air_quality.observation_time for it in items if it.air_quality]
    if len(set(timestamps)) > 1:
        warning = "Note: Comparison contains stations with slightly different observation intervals. Interpret relative rankings with consideration of time variances."

    return ComparisonResponse(
        generated_at=now_iso,
        comparison_items=items,
        cleanest_location=cleanest,
        most_polluted_location=most_polluted,
        data_integrity_warning=warning,
    )
