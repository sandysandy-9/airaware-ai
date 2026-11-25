"""Central Pollution Control Board (CPCB) NAQI Calculation Engine.

Implements the official linear interpolation formula:
    Ip = [(I_hi - I_lo) / (B_hi - B_lo)] * (Cp - B_lo) + I_lo

Enforces the official CPCB rule:
- Minimum of 3 pollutants must be monitored.
- At least one of PM10 or PM2.5 MUST be included.
- Overall AQI = max(sub-index of all valid monitored pollutants).
- Dominant pollutant = pollutant with the highest sub-index.
"""

from decimal import Decimal, ROUND_HALF_UP
import math
from typing import Dict, List, Optional, Tuple, Union
from pydantic import BaseModel, Field

from app.engine.cpcb_breakpoints import (
    AQI_CATEGORIES,
    CPCB_BREAKPOINTS,
    POLLUTANT_INFO,
    BreakpointRange,
)


def round_half_up_non_negative(value: Union[float, int, Decimal]) -> int:
    """Convert a finite non-negative numeric value to int using Decimal ROUND_HALF_UP, clamped [0, 500]."""
    dec = value if isinstance(value, Decimal) else Decimal(str(value))
    if dec < Decimal("0"):
        raise ValueError(f"Expected non-negative value for AQI rounding, got {value!r}")
    rounded = int(dec.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(0, min(500, rounded))


def resolve_aqi_category(sub_index: int) -> Tuple[str, str]:
    """Resolve the official CPCB AQI category name and hex color for an integer AQI value."""
    clamped = max(0, min(500, sub_index))
    for cat_name, cat_data in AQI_CATEGORIES.items():
        low, high = cat_data["range"]
        if low <= clamped <= high:
            return cat_name, cat_data["color"]
    # Defensive fallback should never trigger given contiguous 0..500 CPCB ranges
    return "SEVERE", AQI_CATEGORIES["SEVERE"]["color"]


class SubIndexResult(BaseModel):
    pollutant: str
    concentration: float
    unit: str
    raw_sub_index: Optional[float] = None
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

    if isinstance(concentration, bool) or not isinstance(concentration, (int, float)):
        return SubIndexResult(
            pollutant=pol_key,
            concentration=0.0,
            unit=unit,
            valid=False,
            error=f"Invalid non-numeric concentration ({concentration!r} {unit}).",
        )

    conc = float(concentration)
    if not math.isfinite(conc):
        return SubIndexResult(
            pollutant=pol_key,
            concentration=0.0,
            unit=unit,
            valid=False,
            error=f"Invalid non-finite concentration ({concentration} {unit}).",
        )

    if conc < 0:
        return SubIndexResult(
            pollutant=pol_key,
            concentration=conc,
            unit=unit,
            valid=False,
            error=f"Invalid negative concentration ({conc} {unit}). Sensor fault or calibration error.",
        )

    breakpoints = CPCB_BREAKPOINTS.get(pol_key)
    if not breakpoints:
        return SubIndexResult(
            pollutant=pol_key,
            concentration=conc,
            unit=unit,
            valid=False,
            error=f"No official CPCB breakpoints defined for pollutant '{pollutant}'.",
        )

    # Exceeding highest defined Severe upper concentration bound caps at AQI 500 without extrapolating
    if conc > breakpoints[-1].c_high:
        category, color = resolve_aqi_category(500)
        return SubIndexResult(
            pollutant=pol_key,
            concentration=round(conc, 2),
            unit=unit,
            raw_sub_index=500.0,
            sub_index=500,
            category=category,
            color=color,
            valid=True,
            error="Concentration exceeds upper scale of CPCB Severe bracket (>500 cap).",
        )

    # Continuous piecewise-linear bracket lookup across CPCB thresholds.
    # For the first range [0, c_high_0], B_lo = 0 and I_lo = 0.
    # For subsequent ranges k >= 1 (c_high_{k-1} < Cp <= c_high_k), CPCB continuity sets
    # B_lo = c_high_{k-1} and subtracts 1 from table I_lo when I_lo > 50 (e.g., 51->50, 101->100),
    # eliminating the integer gaps in the static CPCB breakpoint table without altering table values.
    if conc <= breakpoints[0].c_high:
        b_low = breakpoints[0].c_low
        b_high = breakpoints[0].c_high
        i_low = breakpoints[0].i_low
        i_high = breakpoints[0].i_high
    else:
        b_low = breakpoints[0].c_high
        b_high = breakpoints[0].c_high
        i_low = breakpoints[0].i_high
        i_high = breakpoints[0].i_high
        for idx in range(1, len(breakpoints)):
            prev_bp = breakpoints[idx - 1]
            curr_bp = breakpoints[idx]
            if prev_bp.c_high < conc <= curr_bp.c_high:
                b_low = prev_bp.c_high
                b_high = curr_bp.c_high
                i_low = curr_bp.i_low - 1 if curr_bp.i_low > 50 else curr_bp.i_low
                i_high = curr_bp.i_high
                break

    # Linear interpolation formula in Decimal arithmetic to avoid IEEE-754 half-tie drift:
    # Ip = [(I_hi - I_lo) / (B_hi - B_lo)] * (Cp - B_lo) + I_lo
    dec_conc = Decimal(str(conc))
    dec_b_low = Decimal(str(b_low))
    dec_b_high = Decimal(str(b_high))
    dec_c_diff = dec_b_high - dec_b_low
    if dec_c_diff == Decimal("0"):
        ip_dec = Decimal(i_low)
    else:
        ip_dec = (
            (Decimal(i_high - i_low) / dec_c_diff) * (dec_conc - dec_b_low)
        ) + Decimal(i_low)

    ip_dec = max(Decimal("0"), min(Decimal("500"), ip_dec))
    raw_sub_index = float(ip_dec)
    sub_index = round_half_up_non_negative(ip_dec)
    category, color = resolve_aqi_category(sub_index)

    return SubIndexResult(
        pollutant=pol_key,
        concentration=round(conc, 2),
        unit=unit,
        raw_sub_index=raw_sub_index,
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
    valid_raw_sub_indices: Dict[str, float] = {}
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
            valid_raw_sub_indices[key] = (
                res.raw_sub_index if res.raw_sub_index is not None else float(res.sub_index)
            )

    monitored_count = len(valid_raw_sub_indices)
    has_pm = ("pm25" in valid_raw_sub_indices) or ("pm10" in valid_raw_sub_indices)

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
                f"valid pollutant(s) were measured ({', '.join(valid_raw_sub_indices.keys()) or 'none'})."
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
                f"must be monitored. Only gaseous pollutants were measured ({', '.join(valid_raw_sub_indices.keys())})."
            ),
            monitored_pollutants_count=monitored_count,
            has_particulate_matter=False,
            sub_indices=sub_indices,
            missing_pollutants=missing_pollutants,
        )

    # Determine composite max and dominant pollutant on full-precision sub-indices before final ROUND_HALF_UP
    dominant_pol = max(valid_raw_sub_indices, key=lambda k: valid_raw_sub_indices[k])
    overall_aqi = round_half_up_non_negative(valid_raw_sub_indices[dominant_pol])

    # Determine category and color strictly from final reported integer AQI
    category, color = resolve_aqi_category(overall_aqi)

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
