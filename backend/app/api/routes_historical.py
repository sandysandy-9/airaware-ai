"""API routes for model-derived historical air quality trends."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.routes_air_quality import provider_error_to_http_exception, reject_client_override_params
from app.core.logging import get_logger
from app.core.rate_limiter import enforce_rate_limit
from app.providers.factory import get_default_provider, resolve_location
from app.providers.models import ProviderError, ProviderValidationError
from app.schemas.air_quality import HistoricalTrendsResponse
from app.services.cache_service import cache_service

logger = get_logger(__name__)
router = APIRouter(prefix="/air-quality", tags=["Historical Trends"])


@router.get(
    "/historical",
    response_model=HistoricalTrendsResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(reject_client_override_params)],
)
async def get_historical_air_quality(
    city: Optional[str] = Query(None, min_length=1, max_length=100, description="City name"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0),
    past_days: int = Query(7, ge=1, le=30, description="Past days of hourly observations (1-30)"),
):
    """Retrieve model-derived hourly historical series and indicative CPCB calculations."""
    try:
        loc = resolve_location(city_name=city, latitude=latitude, longitude=longitude)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "InvalidLocationQuery", "message": str(exc)},
        ) from exc

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
    except (ProviderError, ProviderValidationError) as exc:
        raise provider_error_to_http_exception(exc, "/historical") from exc
    except Exception as exc:
        logger.warning("Unexpected historical fetch error for %s: %s", loc_name, type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail={
                "error": "HistoricalProviderError",
                "message": "Failed to fetch historical air quality series from upstream provider.",
            },
        ) from exc

    cache_service.set(cache_key, trends, ttl=1800)  # 30 min cache for historical
    return trends
