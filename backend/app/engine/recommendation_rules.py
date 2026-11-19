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
from typing import List, Optional
from pydantic import BaseModel, Field


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

    cat = (aqi_category or "SATISFACTORY").upper().strip()
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
        headline = "Ideal Air Quality: Outdoor activities are safe for all groups."
        precautions.append("Air quality poses no measurable health risk. Enjoy outdoor activities, sports, and exercise freely.")
        precautions.append("Good time to naturally ventilate indoor spaces and exchange stale indoor air.")
        gear = "No protective mask required."

    elif cat == "SATISFACTORY":
        if is_sensitive and is_high_intensity and is_long_duration:
            level = AdvisoryLevel.MODERATE
            headline = "Acceptable Air Quality: Sensitive individuals should pace extended workouts."
            precautions.append("Air quality is generally acceptable for healthy individuals.")
            precautions.append(f"Individuals with {vuln.value} sensitivity should monitor for mild throat or airway irritation during prolonged exertion.")
            gear = "Comfortable cloth or surgical mask optional if sensitive to dust."
        else:
            level = AdvisoryLevel.NORMAL
            headline = "Satisfactory Air Quality: Outdoor exercise and commuting are safe."
            precautions.append("Air quality is considered acceptable for the vast majority of the population.")
            precautions.append("Normal outdoor walks, cycling, and sports can proceed as planned.")
            gear = "No special respiratory protection required for general public."

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

    else:  # SEVERE
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
