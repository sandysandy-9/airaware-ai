"""Indicative Model Index Engine enforcing v2.4.3 CPCB breakpoints & eligibility rules."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel

from app.engine.cpcb_breakpoints import POLLUTANT_INFO
from app.engine.cpcb_calculator import resolve_aqi_category, round_half_up_non_negative
from app.engine.rolling_window import RollingWindowResult

# Deterministic priority order in the rare event two pollutants tie on integer sub-index
TIE_BREAK_ORDER: tuple[str, ...] = ("pm25", "pm10", "o3", "no2", "so2", "co")


class IndicativeModelIndexResult(BaseModel):
    """Composite INDICATIVE_MODEL_INDEX outcome; never represented as official CPCB station AQI."""

    status: Literal["AVAILABLE", "INSUFFICIENT_DATA"]
    index_type: Literal["INDICATIVE_MODEL_INDEX"] = "INDICATIVE_MODEL_INDEX"
    is_official_cpcb_station_aqi: Literal[False] = False
    value: Optional[int] = None
    category: Optional[str] = None
    color: Optional[str] = None
    dominant_pollutant: Optional[str] = None
    dominant_pollutant_name: Optional[str] = None
    eligible_pollutants: List[str]
    insufficient_or_unavailable_pollutants: List[str]
    has_particulate_matter: bool
    eligibility_reason: str
    methodology_note: str = (
        "CPCB NAQI breakpoints applied to model-derived rolling averages from Copernicus CAMS atmospheric grid data. "
        "This produces an INDICATIVE_MODEL_INDEX and is NOT an official CPCB continuous monitoring station (CAAQMS) AQI."
    )


def compute_indicative_model_index(
    rolling_results: Dict[str, RollingWindowResult],
    unavailable_pollutants: List[str],
) -> IndicativeModelIndexResult:
    """Compute composite INDICATIVE_MODEL_INDEX from validated rolling-window assessments."""
    eligible: List[str] = []
    not_eligible: List[str] = list(unavailable_pollutants)

    for code, res in rolling_results.items():
        if res.status == "SUFFICIENT" and res.sub_index is not None:
            eligible.append(code)
        elif code not in not_eligible:
            not_eligible.append(code)

    has_pm = ("pm25" in eligible) or ("pm10" in eligible)
    is_eligible = (len(eligible) >= 3) and has_pm

    if not is_eligible:
        reasons: List[str] = []
        if len(eligible) < 3:
            reasons.append(f"only {len(eligible)} eligible pollutants (minimum 3 required)")
        if not has_pm:
            reasons.append("neither PM2.5 nor PM10 has sufficient rolling-window support")
        return IndicativeModelIndexResult(
            status="INSUFFICIENT_DATA",
            value=None,
            category=None,
            color=None,
            dominant_pollutant=None,
            dominant_pollutant_name=None,
            eligible_pollutants=eligible,
            insufficient_or_unavailable_pollutants=sorted(list(set(not_eligible))),
            has_particulate_matter=has_pm,
            eligibility_reason=f"INSUFFICIENT_DATA for INDICATIVE_MODEL_INDEX: {'; '.join(reasons)}.",
        )

    def _sort_key(code: str) -> tuple[float, int]:
        rr = rolling_results[code]
        raw_val = rr.raw_sub_index if rr.raw_sub_index is not None else float(rr.sub_index or 0)
        prio = -TIE_BREAK_ORDER.index(code) if code in TIE_BREAK_ORDER else -99
        return (raw_val, prio)

    dom_code = max(eligible, key=_sort_key)
    dom_res = rolling_results[dom_code]
    dom_raw = dom_res.raw_sub_index if dom_res.raw_sub_index is not None else float(dom_res.sub_index or 0)
    dom_val = round_half_up_non_negative(dom_raw)
    dom_cat, dom_color = resolve_aqi_category(dom_val)
    dom_name = POLLUTANT_INFO.get(dom_code, {}).get("name", dom_code.upper())

    pm_note = "PM2.5" if "pm25" in eligible else "PM10"
    return IndicativeModelIndexResult(
        status="AVAILABLE",
        value=dom_val,
        category=dom_cat,
        color=dom_color,
        dominant_pollutant=dom_code,
        dominant_pollutant_name=dom_name,
        eligible_pollutants=eligible,
        insufficient_or_unavailable_pollutants=sorted(list(set(not_eligible))),
        has_particulate_matter=has_pm,
        eligibility_reason=(
            f"Eligible for INDICATIVE_MODEL_INDEX: {len(eligible)} sufficient criteria pollutants "
            f"({', '.join(eligible)}), including {pm_note}."
        ),
    )
