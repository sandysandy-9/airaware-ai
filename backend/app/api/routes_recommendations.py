"""API routes for deterministic, explainable Stage 3.2 health & activity recommendations."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes_air_quality import provider_error_to_http_exception, reject_client_override_params
from app.core.rate_limiter import enforce_rate_limit
from app.engine.recommendation_rules import evaluate_assessment_recommendations
from app.providers.factory import resolve_location
from app.providers.models import ProviderError, ProviderValidationError
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.air_quality_service import air_quality_service

router = APIRouter(prefix="/recommendations", tags=["Personalised Recommendations"])


@router.post(
    "",
    response_model=RecommendationResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(reject_client_override_params)],
)
async def get_personalised_recommendations(req: RecommendationRequest):
    """Generate explainable deterministic recommendations strictly from server-assessed indicative air quality."""
    try:
        loc = resolve_location(city_name=req.city, latitude=req.latitude, longitude=req.longitude)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "InvalidLocationQuery", "message": str(exc)},
        ) from exc

    try:
        assessment = await air_quality_service.assess_location(
            location_name=loc["name"],
            city=loc.get("city", loc["name"]),
            state=loc.get("state"),
            latitude=loc["lat"],
            longitude=loc["lon"],
        )
    except (ProviderError, ProviderValidationError) as exc:
        raise provider_error_to_http_exception(exc, "/recommendations") from exc

    eval_res = evaluate_assessment_recommendations(
        assessment,
        activity=req.activity.value,
        sensitivity_preference=req.vulnerability_group.value,
        duration=req.duration.value,
    )

    if eval_res.status != "AVAILABLE" or eval_res.recommendation is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "IndicativeIndexUnavailable",
                "status": "INSUFFICIENT_DATA",
                "message": assessment.indicative_index.eligibility_reason,
                "index_type": assessment.indicative_index.index_type,
                "is_official_cpcb_station_aqi": False,
                "safe_general_guidance": eval_res.safe_general_guidance,
                "triggered_rules": [r.model_dump() for r in eval_res.triggered_rules],
                "uncertainty_notes": eval_res.uncertainty_notes,
            },
        )

    rec = eval_res.recommendation
    tg = assessment.temporal_governance
    return RecommendationResponse(
        status="AVAILABLE",
        location_name=loc["name"],
        index_type="INDICATIVE_MODEL_INDEX",
        is_official_cpcb_station_aqi=False,
        guidance_classification=eval_res.guidance_classification,
        aqi=rec.aqi,
        aqi_category=rec.aqi_category,
        dominant_pollutant=rec.dominant_pollutant,
        activity=rec.activity.value,
        vulnerability_group=rec.vulnerability_group.value,
        duration=rec.duration.value,
        advisory_level=rec.advisory_level.value,
        headline=rec.headline,
        actionable_precautions=rec.actionable_precautions,
        protective_gear=rec.protective_gear,
        indoor_guidance=rec.indoor_guidance,
        disclaimer=rec.disclaimer,
        triggered_rules=eval_res.triggered_rules,
        pollutant_context_status=eval_res.pollutant_context_status,
        data_freshness=assessment.freshness.status,
        temporal_summary={
            "valid_time": tg.valid_time.isoformat(),
            "model_issue_time": tg.model_issue_time.isoformat() if tg.model_issue_time else None,
            "retrieval_time": tg.retrieval_time.isoformat(),
            "valid_time_vs_retrieval": tg.valid_time_vs_retrieval,
            "model_run_relation": tg.model_run_relation,
            "data_source_type": tg.data_source_type,
            "cache_hit": assessment.freshness.cache_hit,
        },
        uncertainty_notes=eval_res.uncertainty_notes,
    )
