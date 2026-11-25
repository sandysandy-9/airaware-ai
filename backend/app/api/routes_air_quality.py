"""Stage 3.1 API routes for authoritative air quality queries and city provenance registry."""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.core.logging import get_logger
from app.core.rate_limiter import enforce_rate_limit
from app.providers.factory import MAJOR_INDIAN_CITIES, resolve_location
from app.providers.models import ProviderError, ProviderValidationError
from app.schemas.air_quality import AirQualityPipelineResponse
from app.services.air_quality_service import air_quality_service

logger = get_logger(__name__)
router = APIRouter(prefix="/air-quality", tags=["Air Quality"])

FORBIDDEN_OVERRIDE_PARAMS = frozenset(
    {
        "aqi",
        "aqi_category",
        "category",
        "dominant_pollutant",
        "risk_score",
        "recommendation",
        "data_freshness",
        "pollutants",
        "sub_indices",
        "current_context",
        "comparison_context",
        "timestamps",
        "health_risk",
        "recommendation_context",
    }
)


async def reject_client_override_params(request: Request) -> None:
    """Trust boundary: reject client-supplied AQI, risk scores, or freshness labels in query params."""
    supplied = set(k.lower() for k in request.query_params.keys()) & FORBIDDEN_OVERRIDE_PARAMS
    if supplied:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "TrustBoundaryViolation",
                "message": (
                    f"Client-supplied environmental metrics or overrides are not permitted: {sorted(supplied)}. "
                    "The backend computes all index values and classifications authoritatively."
                ),
            },
        )


def provider_error_to_http_exception(exc: Exception, endpoint: str) -> HTTPException:
    """Map upstream provider/validation errors consistently without leaking tracebacks."""
    if isinstance(exc, ProviderError):
        logger.warning("Upstream provider error on %s: %s", endpoint, type(exc).__name__)
        status = 504 if exc.is_timeout else 503
        return HTTPException(
            status_code=status,
            detail={
                "error": "ProviderTimeout" if exc.is_timeout else "ProviderUnavailable",
                "message": "Upstream Open-Meteo CAMS Global service is temporarily unavailable.",
                "index_type": "INDICATIVE_MODEL_INDEX",
            },
        )
    if isinstance(exc, ProviderValidationError):
        logger.warning("Upstream validation error on %s: %s", endpoint, str(exc))
        return HTTPException(
            status_code=502,
            detail={
                "error": "InvalidProviderResponse",
                "message": "Upstream environmental payload failed schema or integrity validation.",
                "index_type": "INDICATIVE_MODEL_INDEX",
            },
        )
    raise exc


@router.get("/cities", response_model=List[Dict])
async def list_monitored_cities():
    """Return reference Indian city coordinates with explicit non-station provenance."""
    return [
        {
            "id": key,
            "name": val["name"],
            "city": val["city"],
            "state": val["state"],
            "latitude": val["lat"],
            "longitude": val["lon"],
            "coordinate_role": "REFERENCE_CITY_CENTER",
            "not_a_monitoring_station": True,
            "provider_domain": "cams_global",
        }
        for key, val in MAJOR_INDIAN_CITIES.items()
    ]


@router.get(
    "/current",
    response_model=AirQualityPipelineResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(reject_client_override_params)],
)
async def get_current_air_quality(
    city: Optional[str] = Query(None, min_length=1, max_length=100, description="Reference city name (e.g. 'Delhi', 'Mumbai')"),
    latitude: Optional[float] = Query(None, ge=-90.0, le=90.0, description="Requested latitude [-90, 90]"),
    longitude: Optional[float] = Query(None, ge=-180.0, le=180.0, description="Requested longitude [-180, 180]"),
):
    """Compute authoritative indicative air-quality assessment using rolling windows on Open-Meteo CAMS Global."""
    try:
        loc = resolve_location(city_name=city, latitude=latitude, longitude=longitude)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"error": "InvalidLocationQuery", "message": str(exc)}) from exc

    try:
        return await air_quality_service.assess_location(
            location_name=loc["name"],
            city=loc.get("city", loc["name"]),
            state=loc.get("state"),
            latitude=loc["lat"],
            longitude=loc["lon"],
        )
    except (ProviderError, ProviderValidationError) as exc:
        raise provider_error_to_http_exception(exc, "/current") from exc
