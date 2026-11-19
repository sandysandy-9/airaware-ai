"""API routes for deterministic health and activity recommendations."""

from fastapi import APIRouter
from app.engine.recommendation_rules import generate_recommendations
from app.providers.factory import get_default_provider, resolve_location
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.cache_service import cache_service

router = APIRouter(prefix="/recommendations", tags=["Personalised Recommendations"])


@router.post("", response_model=RecommendationResponse)
async def get_personalised_recommendations(req: RecommendationRequest):
    """Generate deterministic, evidence-based recommendations for user's activity and vulnerability."""
    aqi_val = req.aqi
    cat_val = req.aqi_category
    dom_pol = req.dominant_pollutant
    loc_name = req.city or "Selected Location"

    # If AQI is not provided directly by client, resolve location and query current AQI
    if aqi_val is None or cat_val is None:
        loc = resolve_location(city_name=req.city, latitude=req.latitude, longitude=req.longitude)
        loc_name = loc["name"]
        
        c_key = f"current:{round(loc['lat'], 2)}:{round(loc['lon'], 2)}"
        cached = cache_service.get(c_key)
        if cached:
            current_data = cached
        else:
            provider = get_default_provider()
            current_data = await provider.get_current_air_quality(
                location_name=loc["name"],
                latitude=loc["lat"],
                longitude=loc["lon"],
                city=loc.get("city", loc["name"]),
            )
        
        aqi_val = current_data.aqi
        cat_val = current_data.category
        dom_pol = current_data.dominant_pollutant

    rec_result = generate_recommendations(
        aqi_category=cat_val,
        aqi=aqi_val,
        dominant_pollutant=dom_pol,
        activity=req.activity.value,
        vulnerability_group=req.vulnerability_group.value,
        duration=req.duration.value,
    )

    return RecommendationResponse(
        location_name=loc_name,
        aqi=rec_result.aqi,
        aqi_category=rec_result.aqi_category,
        dominant_pollutant=rec_result.dominant_pollutant,
        activity=rec_result.activity.value,
        vulnerability_group=rec_result.vulnerability_group.value,
        duration=rec_result.duration.value,
        advisory_level=rec_result.advisory_level.value,
        headline=rec_result.headline,
        actionable_precautions=rec_result.actionable_precautions,
        protective_gear=rec_result.protective_gear,
        indoor_guidance=rec_result.indoor_guidance,
        disclaimer=rec_result.disclaimer,
    )
