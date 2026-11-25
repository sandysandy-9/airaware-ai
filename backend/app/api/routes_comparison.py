"""Stage 3.1 API routes for multi-location air quality comparison."""

import asyncio
from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.routes_air_quality import reject_client_override_params
from app.core.logging import get_logger
from app.core.rate_limiter import enforce_rate_limit
from app.providers.factory import resolve_location
from app.providers.models import ProviderError, ProviderValidationError
from app.schemas.air_quality import AirQualityPipelineResponse
from app.schemas.comparison import (
    ComparisonResponse,
    LocationComparisonQuery,
    LocationComparisonResultItem,
    MultiLocationCompareRequest,
)
from app.services.air_quality_service import air_quality_service

logger = get_logger(__name__)
router = APIRouter(prefix="/air-quality", tags=["Comparison"])


def _parse_query_locations(
    cities: Optional[List[str]],
    locations: Optional[str],
) -> List[LocationComparisonQuery]:
    """Parse GET query parameters into 2..6 validated LocationComparisonQuery items."""
    parsed: List[LocationComparisonQuery] = []

    if cities:
        for entry in cities:
            for item in entry.split(","):
                cleaned = item.strip()
                if cleaned:
                    parsed.append(LocationComparisonQuery(city=cleaned))

    if locations:
        chunks = [c.strip() for c in locations.replace("|", ";").split(";") if c.strip()]
        for chunk in chunks:
            parts = [p.strip() for p in chunk.split(",")]
            if len(parts) == 2:
                try:
                    lat = float(parts[0])
                    lon = float(parts[1])
                    if not (math.isfinite(lat) and math.isfinite(lon)):
                        raise ValueError("Non-finite coordinates")
                    if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                        raise HTTPException(
                            status_code=422,
                            detail={
                                "error": "InvalidCoordinateBounds",
                                "message": f"Coordinates ({lat}, {lon}) out of bounds [-90,90], [-180,180].",
                            },
                        )
                    parsed.append(LocationComparisonQuery(latitude=lat, longitude=lon))
                    continue
                except ValueError:
                    pass
            # Treat comma-separated strings as city names
            for part in parts:
                if part:
                    parsed.append(LocationComparisonQuery(city=part))

    if len(parsed) < 2 or len(parsed) > 6:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "InvalidComparisonCount",
                "message": f"Provide between 2 and 6 locations to compare (received {len(parsed)}).",
            },
        )
    return parsed


async def _run_comparison(queries: List[LocationComparisonQuery]) -> ComparisonResponse:
    """Resolve all locations, execute authoritative assessments, and compute provenance warnings."""
    resolved_locs: List[Dict[str, Any]] = []
    for q in queries:
        try:
            resolved_locs.append(
                resolve_location(city_name=q.city, latitude=q.latitude, longitude=q.longitude)
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail={"error": "InvalidLocationQuery", "message": str(exc)}) from exc

    tasks = [
        air_quality_service.assess_location(
            location_name=loc["name"],
            city=loc.get("city", loc["name"]),
            state=loc.get("state"),
            latitude=loc["lat"],
            longitude=loc["lon"],
        )
        for loc in resolved_locs
    ]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    items: List[LocationComparisonResultItem] = []
    available_assessments: List[AirQualityPipelineResponse] = []
    warnings: List[str] = [
        "All comparison values reflect INDICATIVE_MODEL_INDEX derived from Copernicus CAMS Global (~0.4 deg grid), not physical monitoring stations."
    ]
    successful_count = 0
    failed_count = 0

    for loc, res in zip(resolved_locs, raw_results):
        if isinstance(res, (ProviderError, ProviderValidationError, Exception)):
            failed_count += 1
            err_desc = (
                "Upstream provider error or timeout."
                if isinstance(res, ProviderError)
                else "Upstream provider validation failed."
                if isinstance(res, ProviderValidationError)
                else "Location assessment unavailable."
            )
            logger.warning("Comparison sub-request failed for %s: %s", loc["name"], type(res).__name__)
            items.append(
                LocationComparisonResultItem(
                    requested_location=loc["name"],
                    requested_latitude=loc["lat"],
                    requested_longitude=loc["lon"],
                    status="PROVIDER_UNAVAILABLE",
                    assessment=None,
                    error=err_desc,
                )
            )
            continue

        successful_count += 1
        items.append(
            LocationComparisonResultItem(
                requested_location=loc["name"],
                requested_latitude=loc["lat"],
                requested_longitude=loc["lon"],
                status=res.status,
                assessment=res,
                error=None if res.status == "SUCCESS" else res.status_message,
            )
        )
        if res.indicative_index.status == "AVAILABLE" and res.indicative_index.value is not None:
            available_assessments.append(res)

    cleanest: Optional[str] = None
    most_polluted: Optional[str] = None
    insufficient_count = sum(
        1
        for it in items
        if it.assessment is not None and it.assessment.indicative_index.status != "AVAILABLE"
    )

    if len(available_assessments) >= 2:
        available_assessments.sort(key=lambda a: a.indicative_index.value or 0)
        c_first = available_assessments[0]
        c_last = available_assessments[-1]
        cleanest = f"{c_first.location.name} (INDICATIVE_MODEL_INDEX {c_first.indicative_index.value}, {c_first.indicative_index.category})"
        most_polluted = f"{c_last.location.name} (INDICATIVE_MODEL_INDEX {c_last.indicative_index.value}, {c_last.indicative_index.category})"
    else:
        warnings.append(
            f"Cleanest and most-polluted comparison rankings require at least 2 locations with valid "
            f"INDICATIVE_MODEL_INDEX values (found {len(available_assessments)}); ranking fields set to null."
        )

    # Provenance consistency checks
    if failed_count > 0:
        warnings.append(f"{failed_count} of {len(queries)} requested locations could not be retrieved from the provider.")

    if insufficient_count > 0:
        warnings.append(
            f"{insufficient_count} of {len(queries)} requested locations returned INSUFFICIENT_DATA "
            "and were excluded from ranking."
        )

    valid_times = {
        it.assessment.temporal_governance.valid_time
        for it in items
        if it.assessment and it.assessment.temporal_governance.valid_time is not None
    }
    if len(valid_times) > 1:
        warnings.append("Locations in this comparison have differing target valid_time timestamps.")

    issue_times = {
        it.assessment.temporal_governance.model_issue_time
        for it in items
        if it.assessment and it.assessment.temporal_governance.model_issue_time is not None
    }
    if len(issue_times) > 1:
        warnings.append("Locations reflect differing upstream model initialization cycles.")

    retrieval_times = [
        it.assessment.temporal_governance.retrieval_time
        for it in items
        if it.assessment and it.assessment.temporal_governance.retrieval_time is not None
    ]
    if len(retrieval_times) >= 2:
        retrieval_skew_seconds = (max(retrieval_times) - min(retrieval_times)).total_seconds()
        if retrieval_skew_seconds >= 60.0:
            warnings.append(
                f"Locations in this comparison have differing upstream retrieval_time timestamps "
                f"(spread {retrieval_skew_seconds:.0f}s; cached vs freshly retrieved entries may be mixed)."
            )

    snapped_coords = {
        (it.assessment.coordinates.returned_latitude, it.assessment.coordinates.returned_longitude)
        for it in items
        if it.assessment
    }
    if successful_count > 1 and len(snapped_coords) < successful_count:
        warnings.append(
            "Multiple requested locations snapped to the same CAMS Global grid cell due to ~0.4 deg model grid spacing."
        )

    return ComparisonResponse(
        generated_at_utc=datetime.now(timezone.utc),
        requested_count=len(queries),
        successful_count=successful_count,
        failed_count=failed_count,
        comparison_items=items,
        cleanest_location=cleanest,
        most_polluted_location=most_polluted,
        data_integrity_warnings=warnings,
    )


@router.get(
    "/compare",
    response_model=ComparisonResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(reject_client_override_params)],
)
async def compare_locations_get(
    cities: Optional[List[str]] = Query(None, description="City names (comma-separated or repeated), e.g. cities=delhi,mumbai"),
    locations: Optional[str] = Query(
        None,
        description="Semicolon-separated coordinate pairs or city names, e.g. 28.6139,77.2090;19.0760,72.8777",
    ),
):
    """Compare indicative air quality across 2 to 6 locations via GET query parameters."""
    queries = _parse_query_locations(cities, locations)
    return await _run_comparison(queries)


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(reject_client_override_params)],
)
async def compare_locations_post(req: MultiLocationCompareRequest):
    """Compare indicative air quality across 2 to 6 locations via POST body (client overrides rejected)."""
    return await _run_comparison(req.locations)
