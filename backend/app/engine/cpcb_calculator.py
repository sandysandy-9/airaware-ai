"""Central Pollution Control Board (CPCB) NAQI Calculation Engine.

Implements the official linear interpolation formula:
    Ip = [(I_hi - I_lo) / (B_hi - B_lo)] * (Cp - B_lo) + I_lo

Enforces the official CPCB rule:
- Minimum of 3 pollutants must be monitored.
- At least one of PM10 or PM2.5 MUST be included.
- Overall AQI = max(sub-index of all valid monitored pollutants).
- Dominant pollutant = pollutant with the highest sub-index.
"""

from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.engine.cpcb_breakpoints import (
    AQI_CATEGORIES,
    CPCB_BREAKPOINTS,
    POLLUTANT_INFO,
    BreakpointRange,
)


class SubIndexResult(BaseModel):
    pollutant: str
    concentration: float
    unit: str
    sub_index: Optional[int] = None
    category: Optional[str] = None
    color: Optional[str] = None
    valid: bool = True
    error: Optional[str] = None


class CPCBAQIResult(BaseModel):
    aqi: Optional[int] = None
    category: Optional[str] = None
    color: Optional[str] = None
    dominant_pollutant: Optional[str] = None
    status: str  # "SUCCESS", "INSUFFICIENT_DATA", "INVALID_DATA"
    status_message: str
    monitored_pollutants_count: int
    has_particulate_matter: bool
    sub_indices: Dict[str, SubIndexResult]
    missing_pollutants: List[str]
    methodology: str = (
        "Central Pollution Control Board (CPCB) India National Air Quality Index (NAQI) Guidelines"
    )


def calculate_sub_index(pollutant: str, concentration: float) -> SubIndexResult:
    """Calculate the individual sub-index for a single pollutant using CPCB breakpoints.
    
    Args:
        pollutant: Code of pollutant (e.g. 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3', 'nh3', 'pb')
        concentration: Measured concentration value in appropriate unit (µg/m³ except CO in mg/m³)
    
    Returns:
        SubIndexResult containing sub-index value, category, and validity status.
    """
    pol_key = pollutant.lower().replace(".", "").replace("-", "")
    info = POLLUTANT_INFO.get(pol_key, {"unit": "µg/m³"})
    unit = info["unit"]

    if concentration is None:
        return SubIndexResult(
            pollutant=pol_key,
            concentration=0.0,
            unit=unit,
            valid=False,
            error="Measurement is null or missing",
        )

    if concentration < 0:
        return SubIndexResult(
            pollutant=pol_key,
            concentration=concentration,
            unit=unit,
            valid=False,
            error=f"Invalid negative concentration ({concentration} {unit}). Sensor fault or calibration error.",
        )

    breakpoints = CPCB_BREAKPOINTS.get(pol_key)
    if not breakpoints:
        return SubIndexResult(
            pollutant=pol_key,
            concentration=concentration,
            unit=unit,
            valid=False,
            error=f"No official CPCB breakpoints defined for pollutant '{pollutant}'.",
        )

    # Find the breakpoint interval
    matched_bp: Optional[BreakpointRange] = None
    for bp in breakpoints:
        if bp.c_low <= concentration <= bp.c_high:
            matched_bp = bp
            break

    # If concentration exceeds highest breakpoint (Severe threshold)
    if not matched_bp and concentration > breakpoints[-1].c_high:
        matched_bp = breakpoints[-1]
        sub_index = 500  # CPCB NAQI max index scale is 500
        category = "SEVERE"
        color = AQI_CATEGORIES["SEVERE"]["color"]
        return SubIndexResult(
            pollutant=pol_key,
            concentration=round(concentration, 2),
            unit=unit,
            sub_index=sub_index,
            category=category,
            color=color,
            valid=True,
            error="Concentration exceeds upper scale of CPCB Severe bracket (>500 cap).",
        )

    if not matched_bp:
        # Edge case: slightly below 0 (handled above) or not matching
        matched_bp = breakpoints[0]

    # Linear interpolation formula:
    # Ip = [(I_hi - I_lo) / (B_hi - B_lo)] * (Cp - B_lo) + I_lo
    c_diff = matched_bp.c_high - matched_bp.c_low
    if c_diff == 0:
        sub_index = matched_bp.i_low
    else:
        ip = (
            (matched_bp.i_high - matched_bp.i_low) / c_diff
        ) * (concentration - matched_bp.c_low) + matched_bp.i_low
        sub_index = int(round(ip))

    # Clamp sub-index between 0 and 500
    sub_index = max(0, min(500, sub_index))

    # Resolve category
    category = matched_bp.category
    color = AQI_CATEGORIES[category]["color"]

    return SubIndexResult(
        pollutant=pol_key,
        concentration=round(concentration, 2),
        unit=unit,
        sub_index=sub_index,
        category=category,
        color=color,
        valid=True,
    )


def calculate_cpcb_aqi(concentrations: Dict[str, Optional[float]]) -> CPCBAQIResult:
    """Calculate the overall official CPCB National Air Quality Index (NAQI).
    
    Rules:
    1. Minimum 3 valid pollutants must be present.
    2. At least one of PM10 or PM2.5 MUST be included.
    3. Overall AQI = max(valid sub-indices).
    4. Dominant pollutant = pollutant with max sub-index.
    
    Args:
        concentrations: Dict mapping pollutant code to concentration.
            Expected keys include: 'pm25', 'pm10', 'no2', 'so2', 'co', 'o3', 'nh3', 'pb'.
            Note: CO should be in mg/m³.
    
    Returns:
        CPCBAQIResult with calculated AQI, category, dominant pollutant, sub-indices and completeness.
    """
    standard_keys = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3", "pb"]
    sub_indices: Dict[str, SubIndexResult] = {}
    valid_sub_indices: Dict[str, int] = {}
    missing_pollutants: List[str] = []

    for key in standard_keys:
        val = concentrations.get(key)
        if val is None:
            missing_pollutants.append(key)
            sub_indices[key] = SubIndexResult(
                pollutant=key,
                concentration=0.0,
                unit=POLLUTANT_INFO[key]["unit"],
                valid=False,
                error="Not monitored or sensor unavailable",
            )
            continue

        res = calculate_sub_index(key, val)
        sub_indices[key] = res
        if res.valid and res.sub_index is not None:
            valid_sub_indices[key] = res.sub_index

    monitored_count = len(valid_sub_indices)
    has_pm = ("pm25" in valid_sub_indices) or ("pm10" in valid_sub_indices)

    # Check official CPCB sufficiency condition
    if monitored_count < 3:
        return CPCBAQIResult(
            aqi=None,
            category=None,
            color=None,
            dominant_pollutant=None,
            status="INSUFFICIENT_DATA",
            status_message=(
                f"CPCB NAQI requires at least 3 monitored pollutants, but only {monitored_count} "
                f"valid pollutant(s) were measured ({', '.join(valid_sub_indices.keys()) or 'none'})."
            ),
            monitored_pollutants_count=monitored_count,
            has_particulate_matter=has_pm,
            sub_indices=sub_indices,
            missing_pollutants=missing_pollutants,
        )

    if not has_pm:
        return CPCBAQIResult(
            aqi=None,
            category=None,
            color=None,
            dominant_pollutant=None,
            status="INSUFFICIENT_DATA",
            status_message=(
                f"CPCB NAQI mandates that at least one particulate matter indicator (PM2.5 or PM10) "
                f"must be monitored. Only gaseous pollutants were measured ({', '.join(valid_sub_indices.keys())})."
            ),
            monitored_pollutants_count=monitored_count,
            has_particulate_matter=False,
            sub_indices=sub_indices,
            missing_pollutants=missing_pollutants,
        )

    # Overall AQI is the maximum of the sub-indices
    dominant_pol = max(valid_sub_indices, key=lambda k: valid_sub_indices[k])
    overall_aqi = valid_sub_indices[dominant_pol]

    # Determine category
    category = "GOOD"
    for cat_name, cat_data in AQI_CATEGORIES.items():
        low, high = cat_data["range"]
        if low <= overall_aqi <= high:
            category = cat_name
            break

    color = AQI_CATEGORIES[category]["color"]

    return CPCBAQIResult(
        aqi=overall_aqi,
        category=category,
        color=color,
        dominant_pollutant=dominant_pol,
        status="SUCCESS",
        status_message="Valid CPCB NAQI calculated successfully.",
        monitored_pollutants_count=monitored_count,
        has_particulate_matter=True,
        sub_indices=sub_indices,
        missing_pollutants=missing_pollutants,
    )
