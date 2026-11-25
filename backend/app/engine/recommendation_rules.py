"""Deterministic Personalised Air Quality Recommendation Engine.

Adheres strictly to Central Pollution Control Board (CPCB) public health advisories
and World Health Organization (WHO) Global Air Quality Guidelines.

Computes actionable, deterministic precautions based on:
1. AQI Category & Dominant Pollutant
2. Activity Type (Walking, Running, Cycling, Commuting, Outdoor Sports, Indoor)
3. Vulnerability Group (General, Children, Elderly, Respiratory/Asthma, Cardiovascular, Pregnant)
4. Exposure Duration (<30m, 30-60m, 1-2h, >2h)
"""

from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.schemas.air_quality import AirQualityPipelineResponse


class ActivityType(str, Enum):
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    COMMUTING = "commuting"
    OUTDOOR_SPORTS = "outdoor_sports"
    INDOOR = "indoor"


class VulnerabilityGroup(str, Enum):
    GENERAL = "general"
    CHILDREN = "children"
    ELDERLY = "elderly"
    RESPIRATORY = "respiratory"
    CARDIOVASCULAR = "cardiovascular"
    PREGNANT = "pregnant"


class ExposureDuration(str, Enum):
    LESS_THAN_30_MIN = "<30m"
    THIRTY_TO_SIXTY_MIN = "30-60m"
    ONE_TO_TWO_HOURS = "1-2h"
    MORE_THAN_TWO_HOURS = ">2h"


class AdvisoryLevel(str, Enum):
    NORMAL = "LOW_RISK"
    MODERATE = "MODERATE_CAUTION"
    HIGH = "HIGH_RISK"
    VERY_HIGH = "VERY_HIGH_RISK"
    EMERGENCY = "EMERGENCY_AVOID"
    UNAVAILABLE = "UNAVAILABLE"


class TriggeredRule(BaseModel):
    """Explainable provenance record for a deterministic recommendation rule evaluation."""

    rule_id: str
    scope: Literal["PRODUCT_ACTIVITY_RULE", "CPCB_CATEGORY_MAPPING", "POLLUTANT_CAVEAT", "DATA_PROVENANCE"]
    status: Literal["APPLIED", "ISSUED_WITH_REDUCED_SPECIFICITY", "BLOCKED"]
    required_pollutants: List[str] = Field(default_factory=list)
    optional_pollutants: List[str] = Field(default_factory=list)
    reason: str


class RecommendationResult(BaseModel):
    aqi: Optional[int]
    aqi_category: str
    dominant_pollutant: Optional[str]
    activity: ActivityType
    vulnerability_group: VulnerabilityGroup
    duration: ExposureDuration
    advisory_level: AdvisoryLevel
    headline: str
    actionable_precautions: List[str]
    protective_gear: Optional[str]
    indoor_guidance: str
    disclaimer: str = (
        "This guidance is derived from official Central Pollution Control Board (CPCB) and "
        "World Health Organization (WHO) environmental health advisories. It is intended for preventive "
        "risk mitigation and does not substitute professional medical consultation or guarantee absolute safety."
    )


def generate_recommendations(
    aqi_category: Optional[str],
    aqi: Optional[int] = None,
    dominant_pollutant: Optional[str] = None,
    activity: str = "walking",
    vulnerability_group: str = "general",
    duration: str = "30-60m",
) -> RecommendationResult:
    """Generate deterministic, evidence-based health guidance."""
    # Normalize inputs
    try:
        act = ActivityType(activity.lower().strip())
    except ValueError:
        act = ActivityType.WALKING

    try:
        vuln = VulnerabilityGroup(vulnerability_group.lower().strip())
    except ValueError:
        vuln = VulnerabilityGroup.GENERAL

    try:
        dur = ExposureDuration(duration.lower().strip())
    except ValueError:
        dur = ExposureDuration.THIRTY_TO_SIXTY_MIN

    cat = (aqi_category or "").upper().strip()
    valid_categories = {"GOOD", "SATISFACTORY", "MODERATE", "POOR", "VERY_POOR", "SEVERE"}
    if cat not in valid_categories:
        return RecommendationResult(
            aqi=None,
            aqi_category="UNAVAILABLE",
            dominant_pollutant=None,
            activity=act,
            vulnerability_group=vuln,
            duration=dur,
            advisory_level=AdvisoryLevel.UNAVAILABLE,
            headline="Insufficient or Invalid Air Quality Evidence: Activity advisory unavailable.",
            actionable_precautions=[
                "Environmental air quality evidence is unavailable or invalid; never assume conditions are safe.",
                "Consult local official CPCB CAAQMS bulletins before planning strenuous outdoor exertion.",
            ],
            protective_gear="Respiratory gear guidance unavailable without a verified air quality category.",
            indoor_guidance="Maintain standard indoor precautions until verified air quality readings are available.",
        )

    is_sensitive = vuln in [
        VulnerabilityGroup.CHILDREN,
        VulnerabilityGroup.ELDERLY,
        VulnerabilityGroup.RESPIRATORY,
        VulnerabilityGroup.CARDIOVASCULAR,
        VulnerabilityGroup.PREGNANT,
    ]
    is_high_intensity = act in [
        ActivityType.RUNNING,
        ActivityType.CYCLING,
        ActivityType.OUTDOOR_SPORTS,
    ]
    is_long_duration = dur in [
        ExposureDuration.ONE_TO_TWO_HOURS,
        ExposureDuration.MORE_THAN_TWO_HOURS,
    ]

    precautions: List[str] = []
    gear: Optional[str] = None
    indoor_guide = "Maintain standard indoor ventilation with open windows when ambient air is clean."

    # Decision Matrix based on CPCB Official Categories
    if cat == "GOOD":
        level = AdvisoryLevel.NORMAL
        headline = (
            "Good Modeled Air Quality: Low indicative risk for outdoor activities based on CAMS estimates "
            "(verify local conditions; not a physical station reading)."
        )
        precautions.append(
            "Modeled pollutant concentrations indicate low health risk for most people, though street-level conditions and individual sensitivities can vary."
        )
        precautions.append(
            "Generally favorable conditions to naturally ventilate indoor spaces unless nearby traffic or dust sources are present."
        )
        gear = "No special protective mask typically required for general outdoor activity."

    elif cat == "SATISFACTORY":
        if is_sensitive and is_high_intensity and is_long_duration:
            level = AdvisoryLevel.MODERATE
            headline = "Satisfactory Modeled Air Quality: Sensitive individuals should pace extended workouts."
            precautions.append("Modeled air quality is generally acceptable for healthy adults, though prolonged high-intensity exertion increases inhaled dose.")
            precautions.append(f"Individuals with {vuln.value} sensitivity should monitor for mild throat or airway irritation during prolonged exertion.")
            gear = "Comfortable cloth or surgical mask optional if sensitive to dust."
        else:
            level = AdvisoryLevel.NORMAL
            headline = (
                "Satisfactory Modeled Air Quality: Lower modeled risk for outdoor exercise and commuting; "
                "monitor individual sensitivity."
            )
            precautions.append(
                "Modeled air quality is generally acceptable for most healthy adults, though unusually sensitive individuals may experience minor breathing discomfort."
            )
            precautions.append(
                "Standard outdoor walks, cycling, and sports carry lower modeled exposure risk, subject to local street-level variation and model uncertainty."
            )
            gear = "No special respiratory protection typically required for the general public."

    elif cat == "MODERATE":
        if is_sensitive:
            level = AdvisoryLevel.HIGH
            headline = "Moderate Air Quality: Sensitive groups should curtail heavy outdoor exertion."
            precautions.append(f"People in the {vuln.value} category (asthma, heart disease, elderly, children) should reduce extended heavy outdoor workouts.")
            precautions.append("Keep emergency respiratory medications (e.g. prescribed quick-relief inhalers) within reach.")
            if is_high_intensity:
                precautions.append("Substitute high-aerobic outdoor training with indoor gym or home workouts.")
            gear = "N95 / FFP2 respirator recommended for sensitive individuals during prolonged transit."
            indoor_guide = "Close windows facing busy roads during peak traffic hours."
        else:
            level = AdvisoryLevel.MODERATE
            headline = "Moderate Air Quality: Generally tolerable, but avoid overexertion near congested roads."
            precautions.append("Healthy individuals may notice minor throat irritation or coughing during extended high-intensity workouts.")
            if is_high_intensity and is_long_duration:
                precautions.append("Reduce the duration of continuous outdoor sports or choose green parks away from traffic arteries.")
            gear = "Protective mask optional, but useful during heavy traffic commutes."
            indoor_guide = "Ventilate indoor areas during midday when atmospheric boundary layer disperses particulates."

    elif cat == "POOR":
        if is_sensitive:
            level = AdvisoryLevel.VERY_HIGH
            headline = "Poor Air Quality: Significant health hazard for sensitive cohorts."
            precautions.append(f"Individuals with {vuln.value} conditions MUST avoid all strenuous outdoor activities.")
            precautions.append("Remain in filtered indoor environments as much as possible.")
            precautions.append("Keep all asthma/COPD rescue medications accessible at all times.")
            gear = "Well-fitted N95 / FFP2 / KN95 respirator mandatory if outdoor transit is unavoidable."
            indoor_guide = "Keep windows and external doors closed. Operate HEPA air purifiers if available."
        else:
            level = AdvisoryLevel.HIGH
            headline = "Poor Air Quality: Unhealthy for all groups on prolonged exposure."
            precautions.append("Prolonged outdoor exertion can cause noticeable breathing discomfort, throat burning, and eye irritation.")
            if is_high_intensity:
                precautions.append("Cancel or reschedule outdoor running, competitive matches, and heavy cycling to indoor alternatives.")
            if act == ActivityType.COMMUTING:
                precautions.append("Keep vehicle windows rolled up and switch AC recirculation mode to 'Internal'.")
            gear = "N95 / FFP2 respirator strongly advised for any outdoor exposure exceeding 15 minutes."
            indoor_guide = "Minimize outdoor air intake. Use wet mopping instead of dry dusting to control indoor dust."

    elif cat == "VERY_POOR":
        level = AdvisoryLevel.VERY_HIGH
        headline = "Very Poor Air Quality: Severe respiratory hazard. Restrict all outdoor activity."
        precautions.append("Everyone, regardless of baseline health, is at risk of respiratory discomfort and lung inflammation.")
        precautions.append("Suspension of all outdoor physical training, running, walking, and school sports is strongly urged.")
        if is_sensitive:
            precautions.append(f"High vulnerability alert for {vuln.value}: Stay indoors under air-filtered conditions to prevent acute exacerbations.")
        if act == ActivityType.COMMUTING:
            precautions.append("Use closed public transit (metro, enclosed cabs) over open two-wheelers or auto-rickshaws.")
        gear = "Certified N95 / FFP2 / FFP3 mask with airtight facial seal required for any step outdoors."
        indoor_guide = "Seal window cracks. Run HEPA filtration units continuously. Avoid indoor burning, frying, or incense."

    elif cat == "SEVERE":
        level = AdvisoryLevel.EMERGENCY
        headline = "Severe Air Quality: Public Health Emergency. Absolute indoor containment advised."
        precautions.append("Emergency environmental threshold: Air toxicity affects healthy adults and severely jeopardizes sensitive groups.")
        precautions.append("All non-essential outdoor travel and exercise should be immediately halted.")
        precautions.append("Schools and outdoor workplaces should enforce emergency pollution protective protocols.")
        if is_sensitive:
            precautions.append(f"URGENT: {vuln.value} individuals experiencing breathlessness or chest pressure should seek prompt medical assistance.")
        gear = "Strict N95 / FFP3 respirator essential even for brief outdoor transit."
        indoor_guide = "Absolute indoor lockdown. Keep all windows and doors sealed. Run multi-stage HEPA air purifiers at high speed."

    # Specific pollutant-targeted caveat
    if dominant_pollutant == "o3":
        precautions.append("Ozone Alert: Ground-level ozone peaks in afternoon sunlight. Shift any unavoidable outdoor movement to early morning or after dusk.")
    elif dominant_pollutant in ["pm25", "pm10"]:
        precautions.append("Particulate Alert: Winter smog and calm morning winds trap fine particulates near ground level. Avoid dawn/dusk outdoor jogs.")
    elif dominant_pollutant == "co":
        precautions.append("Carbon Monoxide Alert: Avoid lingering near idling engines, subterranean parking lots, or poorly ventilated traffic junctions.")
    elif dominant_pollutant == "no2":
        precautions.append("Nitrogen Dioxide Alert: Elevated NO2 typically concentrates near heavy vehicular corridors; avoid exercising along busy roadways.")
    elif dominant_pollutant == "so2":
        precautions.append("Sulphur Dioxide Alert: Sensitive airways react quickly to SO2 plumes; minimize outdoor exposure downwind of combustion sources.")

    return RecommendationResult(
        aqi=aqi,
        aqi_category=cat,
        dominant_pollutant=dominant_pollutant,
        activity=act,
        vulnerability_group=vuln,
        duration=dur,
        advisory_level=level,
        headline=headline,
        actionable_precautions=precautions,
        protective_gear=gear,
        indoor_guidance=indoor_guide,
    )


class AssessmentRecommendationEvaluation(BaseModel):
    """Server-authoritative Stage 3.2 deterministic recommendation outcome with Tier C traceability."""

    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    index_type: Literal["INDICATIVE_MODEL_INDEX"] = "INDICATIVE_MODEL_INDEX"
    is_official_cpcb_station_aqi: Literal[False] = False
    guidance_classification: str = (
        "PRODUCT_RULE_ENGINE_GUIDANCE (distinct from official CPCB NAQI numerical breakpoints)"
    )
    recommendation: Optional[RecommendationResult] = None
    triggered_rules: List[TriggeredRule] = Field(default_factory=list)
    pollutant_context_status: Dict[str, str] = Field(default_factory=dict)
    uncertainty_notes: List[str] = Field(default_factory=list)
    safe_general_guidance: str = (
        "When modelled coverage or cycle currency is incomplete, consult local official CPCB CAAQMS "
        "monitoring bulletins before strenuous outdoor exertion."
    )


def evaluate_assessment_recommendations(
    assessment: "AirQualityPipelineResponse",
    *,
    activity: str = "walking",
    sensitivity_preference: str = "general",
    duration: str = "30-60m",
) -> AssessmentRecommendationEvaluation:
    """Evaluate authoritative pipeline outputs through reviewed deterministic rules (no LLM)."""
    idx = assessment.indicative_index
    pollutant_status = {code: detail.status for code, detail in assessment.pollutants.items()}
    sufficient_pollutants = [code for code, st in pollutant_status.items() if st == "SUFFICIENT"]
    incomplete_pollutants = [code for code, st in pollutant_status.items() if st != "SUFFICIENT"]

    rules: List[TriggeredRule] = []
    uncertainty: List[str] = [
        "Underlying index is INDICATIVE_MODEL_INDEX derived from Copernicus CAMS atmospheric grid simulations, not a physical CPCB monitoring station."
    ]

    # Gate 1: Composite INDICATIVE_MODEL_INDEX sufficiency (Architecture v2.4.3 Section 10 Tier A)
    if idx.status != "AVAILABLE" or idx.value is None or idx.category is None:
        rules.append(
            TriggeredRule(
                rule_id="RULE-GATE-INDEX-SUFFICIENCY",
                scope="DATA_PROVENANCE",
                status="BLOCKED",
                required_pollutants=["pm25|pm10", ">=3 criteria pollutants"],
                reason=idx.eligibility_reason,
            )
        )
        uncertainty.append(idx.eligibility_reason)
        return AssessmentRecommendationEvaluation(
            status="INSUFFICIENT_DATA",
            recommendation=None,
            triggered_rules=rules,
            pollutant_context_status=pollutant_status,
            uncertainty_notes=uncertainty,
            safe_general_guidance=(
                "Verified air quality evidence is currently insufficient to generate activity-specific risk guidance. "
                "Avoid assuming air quality is safe solely due to missing sensor data, and check local official CPCB CAAQMS bulletins."
            ),
        )

    # Gate 2: Core deterministic product-rule evaluation from validated indicative index
    base_rec = generate_recommendations(
        aqi_category=idx.category,
        aqi=idx.value,
        dominant_pollutant=idx.dominant_pollutant,
        activity=activity,
        vulnerability_group=sensitivity_preference,
        duration=duration,
    )

    rules.append(
        TriggeredRule(
            rule_id=f"RULE-CAT-{idx.category}-{base_rec.advisory_level.value}",
            scope="PRODUCT_ACTIVITY_RULE",
            status="APPLIED",
            required_pollutants=list(idx.eligible_pollutants),
            optional_pollutants=incomplete_pollutants,
            reason=(
                f"Product preventive guidance triggered for CPCB indicative category {idx.category} "
                f"(value={idx.value}), activity='{base_rec.activity.value}', "
                f"sensitivity='{base_rec.vulnerability_group.value}', duration='{base_rec.duration.value}'."
            ),
        )
    )

    # Gate 3: Dominant pollutant caveat traceability (only if verified sufficient)
    dom_code = idx.dominant_pollutant
    if dom_code and pollutant_status.get(dom_code) == "SUFFICIENT":
        rules.append(
            TriggeredRule(
                rule_id=f"RULE-DOMINANT-{dom_code.upper()}",
                scope="POLLUTANT_CAVEAT",
                status="APPLIED",
                required_pollutants=[dom_code],
                reason=f"Dominant driver '{dom_code}' passed rolling-window coverage sufficiency criteria.",
            )
        )

    # Gate 4: Tier C incomplete pollutant specificity disclosure (e.g., unavailable NH3 in CAMS India)
    if incomplete_pollutants:
        rules.append(
            TriggeredRule(
                rule_id="RULE-TIER-C-INCOMPLETE-POLLUTANTS",
                scope="DATA_PROVENANCE",
                status="ISSUED_WITH_REDUCED_SPECIFICITY",
                required_pollutants=sufficient_pollutants,
                optional_pollutants=incomplete_pollutants,
                reason=(
                    f"Guidance issued with reduced specificity because pollutant(s) "
                    f"[{', '.join(incomplete_pollutants)}] are UNAVAILABLE or INSUFFICIENT_DATA "
                    "(never treated as zero)."
                ),
            )
        )
        uncertainty.append(
            f"Excluded incomplete pollutant(s): {', '.join(incomplete_pollutants)} (not substituted with zero)."
        )

    # Gate 5: Temporal governance & cycle freshness uncertainty disclosure (Stage 2.1 + Stage 3.2.2)
    tg = assessment.temporal_governance
    freshness = assessment.freshness
    is_past_forecast = tg.valid_time_vs_retrieval == "PAST" and tg.model_run_relation == "FORECAST"
    has_temporal_uncertainty = (
        freshness.status in ("STALE_CYCLE", "UNKNOWN_RUN_AGE")
        or tg.valid_time_vs_retrieval == "FUTURE"
        or tg.model_run_relation in ("FORECAST", "UNKNOWN")
    )

    if has_temporal_uncertainty:
        if is_past_forecast:
            temporal_note = (
                f"Past-valid forecast model output (valid_time={tg.valid_time.isoformat()}, "
                f"valid_time_vs_retrieval=PAST, model_run_relation=FORECAST, lead={tg.forecast_lead_hours:.1f}h); "
                "this is NOT a historical station analysis or physical observation."
            )
        elif tg.model_run_relation == "UNKNOWN" or freshness.status == "UNKNOWN_RUN_AGE":
            temporal_note = (
                f"Model initialization relationship or run age is unverified "
                f"(valid_time_vs_retrieval={tg.valid_time_vs_retrieval}, model_run_relation={tg.model_run_relation}, "
                f"freshness={freshness.status}); uncertainty is elevated."
            )
        else:
            temporal_note = (
                f"Temporal posture is {tg.valid_time_vs_retrieval}/{tg.model_run_relation} "
                f"with cycle freshness '{freshness.status}'; certainty is reduced relative to current-cycle analyses."
            )

        rules.append(
            TriggeredRule(
                rule_id=f"RULE-TEMPORAL-{freshness.status}-{tg.valid_time_vs_retrieval}-{tg.model_run_relation}",
                scope="DATA_PROVENANCE",
                status="ISSUED_WITH_REDUCED_SPECIFICITY",
                reason=temporal_note,
            )
        )
        uncertainty.append(f"Temporal caveat: {temporal_note}")
    else:
        # Only CURRENT/PAST ANALYSIS cycles within CURRENT_CYCLE/AGING_CYCLE arrive here
        rules.append(
            TriggeredRule(
                rule_id=f"RULE-PROVENANCE-VERIFIED-{tg.model_run_relation}-{freshness.status}",
                scope="DATA_PROVENANCE",
                status="APPLIED",
                reason=(
                    f"Model-derived context verified ({tg.valid_time_vs_retrieval}/{tg.model_run_relation}, "
                    f"freshness={freshness.status}); guidance remains preventive product logic separate from CPCB regulation."
                ),
            )
        )

    return AssessmentRecommendationEvaluation(
        status="AVAILABLE",
        recommendation=base_rec,
        triggered_rules=rules,
        pollutant_context_status=pollutant_status,
        uncertainty_notes=uncertainty,
    )
