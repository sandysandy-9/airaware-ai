"""Production Stage 3.1 Air Quality Data Pipeline Service."""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from app.core.config import settings
from app.core.logging import get_logger
from app.engine.cpcb_breakpoints import POLLUTANT_INFO
from app.engine.indicative_index import IndicativeModelIndexResult, compute_indicative_model_index
from app.engine.rolling_window import POLLUTANT_WINDOW_HOURS, RollingWindowResult, integrate_rolling_window
from app.providers.models import NormalizedProviderSeries
from app.providers.open_meteo import OpenMeteoProvider, normalize_open_meteo_response
from app.schemas.air_quality import (
    AirQualityPipelineResponse,
    CoordinateProvenance,
    FreshnessSummary,
    LocationInfo,
    PollutantRollingDetail,
    ProviderProvenance,
)
from app.services.cache_service import cache_service

logger = get_logger(__name__)


class _InflightLockEntry:
    """Reference-counted single-flight lock entry safe for concurrent async cleanup."""

    __slots__ = ("lock", "waiters")

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.waiters = 0


class AirQualityPipelineService:
    """Orchestrates validated Open-Meteo fetching, safe TTL caching, Stage 1 integration, and Stage 2.1 governance.

    Note: Single-flight lock coalescing and cache lookups are scoped to a single Python process.
    """

    def __init__(self, provider: Optional[OpenMeteoProvider] = None):
        self.provider = provider or OpenMeteoProvider()
        self._inflight_locks: Dict[str, _InflightLockEntry] = {}

    def _acquire_inflight_entry(self, key: str) -> _InflightLockEntry:
        entry = self._inflight_locks.get(key)
        if entry is None:
            entry = _InflightLockEntry()
            self._inflight_locks[key] = entry
        entry.waiters += 1
        return entry

    def _release_inflight_entry(self, key: str, entry: _InflightLockEntry) -> None:
        entry.waiters -= 1
        if entry.waiters <= 0 and self._inflight_locks.get(key) is entry:
            del self._inflight_locks[key]

    @property
    def inflight_lock_count(self) -> int:
        """Diagnostic count of currently active in-flight lock keys."""
        return len(self._inflight_locks)

    async def assess_location(
        self,
        *,
        location_name: str,
        city: str,
        state: Optional[str],
        latitude: float,
        longitude: float,
        domain: str = settings.open_meteo_domain,
        valid_time_utc: Optional[datetime] = None,
    ) -> AirQualityPipelineResponse:
        """Execute full validated pipeline for a geographic point."""
        now_utc = datetime.now(timezone.utc)
        target_valid = (
            valid_time_utc.astimezone(timezone.utc)
            if valid_time_utc is not None
            else now_utc.replace(minute=0, second=0, microsecond=0)
        )

        # Convert target UTC valid time to provider local IST (+05:30) for aligned start_date/end_date
        target_ist = target_valid + timedelta(hours=5, minutes=30)
        start_date_str = (target_ist - timedelta(days=2)).strftime("%Y-%m-%d")
        end_date_str = (target_ist + timedelta(days=1)).strftime("%Y-%m-%d")

        cache_key = f"om_raw:{domain}:{latitude:.4f}:{longitude:.4f}:{start_date_str}:{end_date_str}"
        cache_hit = False
        normalized: Optional[NormalizedProviderSeries] = None

        cached_entry = cache_service.get(cache_key)
        if cached_entry is not None:
            raw_data, status_code, req_url, req_params, retrieval_time, raw_meta, meta_url = cached_entry
            cache_hit = True
        else:
            inflight = self._acquire_inflight_entry(cache_key)
            try:
                async with inflight.lock:
                    cached_entry = cache_service.get(cache_key)
                    if cached_entry is not None:
                        raw_data, status_code, req_url, req_params, retrieval_time, raw_meta, meta_url = cached_entry
                        cache_hit = True
                    else:
                        normalized, raw_data, raw_meta = await self.provider.fetch_validated_series(
                            latitude=latitude,
                            longitude=longitude,
                            start_date=start_date_str,
                            end_date=end_date_str,
                            domain=domain,
                            timezone_name=settings.open_meteo_timezone,
                            target_valid_time_utc=target_valid,
                        )
                        cache_service.set(
                            cache_key,
                            (
                                raw_data,
                                normalized.http_status,
                                normalized.request_url,
                                normalized.request_params,
                                normalized.retrieval_time_utc,
                                raw_meta,
                                normalized.metadata.metadata_source_url,
                            ),
                            ttl=settings.cache_ttl_seconds,
                        )
            finally:
                self._release_inflight_entry(cache_key, inflight)

        if normalized is None:
            normalized = normalize_open_meteo_response(
                raw_data,
                requested_latitude=latitude,
                requested_longitude=longitude,
                domain_requested=domain,
                request_url=req_url,
                request_params=req_params,
                http_status=status_code,
                retrieval_time_utc=retrieval_time,
                raw_meta_json=raw_meta,
                meta_source_url=meta_url,
                target_valid_time_utc=target_valid,
            )

        return self.build_assessment_from_normalized(
            normalized=normalized,
            location_name=location_name,
            city=city,
            state=state,
            target_valid_time_utc=target_valid,
            cache_hit=cache_hit,
        )

    async def assess_locations(
        self,
        resolved_locs: Sequence[Dict[str, Any]],
    ) -> List[Any]:
        """Concurrently run authoritative assessments across multiple resolved locations."""
        tasks = [
            self.assess_location(
                location_name=loc["name"],
                city=loc.get("city", loc["name"]),
                state=loc.get("state"),
                latitude=loc["lat"],
                longitude=loc["lon"],
            )
            for loc in resolved_locs
        ]
        return list(await asyncio.gather(*tasks, return_exceptions=True))

    def build_assessment_from_normalized(
        self,
        *,
        normalized: NormalizedProviderSeries,
        location_name: str,
        city: str,
        state: Optional[str],
        target_valid_time_utc: datetime,
        cache_hit: bool = False,
    ) -> AirQualityPipelineResponse:
        """Pure Stage 1 + Stage 2.1 transformation over normalized provider data (enables deterministic testing)."""
        rolling_results: Dict[str, RollingWindowResult] = {}
        pollutant_details: Dict[str, PollutantRollingDetail] = {}

        for canon_code, win_hours in POLLUTANT_WINDOW_HOURS.items():
            samples_list = normalized.pollutant_series.get(canon_code, [])
            raw_pairs = [(s.timestamp_utc, s.value) for s in samples_list]
            stats = normalized.pollutant_stats.get(canon_code)
            target_unit = stats.expected_target_unit if stats else ("mg/m³" if canon_code == "co" else "µg/m³")
            reported_unit = stats.reported_unit if stats else None

            w_end = target_valid_time_utc
            w_start = target_valid_time_utc - timedelta(hours=win_hours)

            res = integrate_rolling_window(
                raw_pairs,
                pollutant=canon_code,
                unit=target_unit,
                window_start_utc=w_start,
                window_end_utc=w_end,
                g_max_seconds=settings.max_supported_gap_seconds,
            )
            rolling_results[canon_code] = res

            meta_info = POLLUTANT_INFO.get(canon_code, {})
            pollutant_details[canon_code] = PollutantRollingDetail(
                code=canon_code,
                name=meta_info.get("name", canon_code.upper()),
                status=res.status,
                concentration=res.time_weighted_mean if res.status != "UNAVAILABLE" else None,
                unit=target_unit,
                reported_unit=reported_unit,
                sub_index=res.sub_index if res.status == "SUFFICIENT" else None,
                category=res.sub_index_category if res.status == "SUFFICIENT" else None,
                color=res.sub_index_color if res.status == "SUFFICIENT" else None,
                averaging_period=f"{win_hours} hours (trapezoidal)",
                rolling_window=res,
                unavailable_reason=res.insufficiency_reason,
                description=meta_info.get("description", ""),
                health_effects=meta_info.get("health_effects", ""),
                sources=meta_info.get("primary_sources", ""),
            )

        # Explicitly include NH3 status (never fabricate 0.0)
        nh3_stats = normalized.pollutant_stats.get("nh3")
        nh3_info = POLLUTANT_INFO.get("nh3", {})
        if "nh3" in normalized.unavailable_pollutants or nh3_stats is None or nh3_stats.is_empty:
            pollutant_details["nh3"] = PollutantRollingDetail(
                code="nh3",
                name=nh3_info.get("name", "Ammonia"),
                status="UNAVAILABLE",
                concentration=None,
                unit="µg/m³",
                reported_unit=nh3_stats.reported_unit if nh3_stats else None,
                sub_index=None,
                category=None,
                color=None,
                averaging_period="24 hours (trapezoidal)",
                rolling_window=None,
                unavailable_reason="Not supplied or null in upstream Open-Meteo CAMS Global response.",
                description=nh3_info.get("description", ""),
                health_effects=nh3_info.get("health_effects", ""),
                sources=nh3_info.get("primary_sources", ""),
            )

        indicative_idx: IndicativeModelIndexResult = compute_indicative_model_index(
            rolling_results, normalized.unavailable_pollutants
        )

        tg = normalized.temporal_governance
        assert tg is not None, "TemporalGovernance must always be constructed on normalized series."

        freshness = _derive_freshness(normalized, cache_hit=cache_hit)

        warnings: List[str] = [
            "Model-derived atmospheric grid estimate (Open-Meteo CAMS Global ~0.4 deg), not an official CPCB CAAQMS physical station observation."
        ]
        if "nh3" in normalized.unavailable_pollutants:
            warnings.append("Ammonia (NH3) is unavailable from CAMS Global at this location and was excluded (not substituted with zero).")
        if not normalized.metadata.metadata_verified_for_response:
            warnings.append("Model initialization metadata could not be verified for this domain; model_run_relation is UNKNOWN.")
        if tg.valid_time_vs_retrieval == "PAST" and tg.model_run_relation == "FORECAST":
            warnings.append(
                f"Valid time precedes retrieval time but represents a +{tg.forecast_lead_hours:.1f}h forecast lead relative to model initialization."
            )
        if cache_hit:
            warnings.append(
                f"Served from TTL cache; retrieval_time ({tg.retrieval_time.isoformat()}) reflects the original upstream retrieval."
            )
        warnings.extend(normalized.anomalies)
        warnings.extend(normalized.timezone_parsing_notes)

        overall_status = "SUCCESS" if indicative_idx.status == "AVAILABLE" else "INSUFFICIENT_DATA"
        status_msg = (
            f"Indicative model index {indicative_idx.value} ({indicative_idx.category}) computed from {len(indicative_idx.eligible_pollutants)} sufficient rolling windows."
            if overall_status == "SUCCESS"
            else indicative_idx.eligibility_reason
        )

        return AirQualityPipelineResponse(
            status=overall_status,
            status_message=status_msg,
            location=LocationInfo(
                name=location_name,
                city=city,
                state=state,
                latitude=normalized.requested_latitude,
                longitude=normalized.requested_longitude,
            ),
            coordinates=CoordinateProvenance(
                requested_latitude=normalized.requested_latitude,
                requested_longitude=normalized.requested_longitude,
                returned_latitude=normalized.returned_latitude,
                returned_longitude=normalized.returned_longitude,
                geodesic_snap_distance_km=normalized.geodesic_distance_km,
                elevation_m=normalized.elevation_m,
            ),
            provider=ProviderProvenance(
                provider_name=normalized.provider_name,
                domain_requested=normalized.metadata.domain_requested,
                model_name=normalized.metadata.model_name,
                metadata_verified=normalized.metadata.metadata_verified_for_response,
                native_temporal_resolution=normalized.metadata.native_temporal_resolution,
                meta_temporal_resolution_seconds=normalized.metadata.meta_temporal_resolution_seconds,
                api_output_frequency_seconds=normalized.metadata.api_output_frequency_seconds,
                update_interval_seconds=normalized.metadata.update_interval_seconds,
                last_run_modification_time=normalized.metadata.last_run_modification_time,
                last_run_availability_time=normalized.metadata.last_run_availability_time,
                spatial_resolution_note=normalized.metadata.spatial_resolution_note,
                cache_hit=cache_hit,
            ),
            indicative_index=indicative_idx,
            pollutants=pollutant_details,
            unavailable_pollutants=sorted(list(set(normalized.unavailable_pollutants))),
            temporal_governance=tg,
            freshness=freshness,
            warnings=warnings,
        )


def _derive_freshness(normalized: NormalizedProviderSeries, cache_hit: bool) -> FreshnessSummary:
    """Classify cycle currency transparently without inventing 'LIVE' labels."""
    tg = normalized.temporal_governance
    meta = normalized.metadata

    if tg is None or tg.model_run_age_hours is None or not meta.metadata_verified_for_response:
        return FreshnessSummary(
            status="UNKNOWN_RUN_AGE",
            cache_hit=cache_hit,
            disclaimer=(
                "Verified model initialization time unavailable; cycle age cannot be established. "
                "Data represents a model-derived atmospheric grid estimate."
            ),
        )

    avail_dt = meta.last_run_availability_time
    interval_sec = meta.update_interval_seconds
    if avail_dt is not None and interval_sec and interval_sec > 0:
        hours_since_avail = (tg.retrieval_time - avail_dt).total_seconds() / 3600.0
        interval_hours = interval_sec / 3600.0
        if hours_since_avail <= interval_hours:
            f_status = "CURRENT_CYCLE"
        elif hours_since_avail <= interval_hours * 1.5:
            f_status = "AGING_CYCLE"
        else:
            f_status = "STALE_CYCLE"
        return FreshnessSummary(
            status=f_status,
            cache_hit=cache_hit,
            disclaimer=(
                f"Model cycle initialized {tg.model_run_age_hours:.2f}h before retrieval; "
                f"available {hours_since_avail:.2f}h before retrieval (nominal cycle interval {interval_hours:.1f}h)."
            ),
        )

    age_h = tg.model_run_age_hours
    if age_h <= 12.0:
        f_status = "CURRENT_CYCLE"
    elif age_h <= 24.0:
        f_status = "AGING_CYCLE"
    else:
        f_status = "STALE_CYCLE"

    return FreshnessSummary(
        status=f_status,
        cache_hit=cache_hit,
        disclaimer=f"Model cycle initialized {age_h:.2f}h before retrieval (model-derived grid data).",
    )


def rank_available_assessments(
    available_assessments: Sequence[AirQualityPipelineResponse],
) -> Tuple[Optional[str], Optional[str]]:
    """Return formatted (lowest, highest) indicative index summary labels when >= 2 locations qualify."""
    valid = [
        a
        for a in available_assessments
        if a.indicative_index.status == "AVAILABLE" and a.indicative_index.value is not None
    ]
    if len(valid) < 2:
        return None, None
    ordered = sorted(valid, key=lambda a: a.indicative_index.value or 0)
    first, last = ordered[0], ordered[-1]
    cleanest = f"{first.location.name} (INDICATIVE_MODEL_INDEX {first.indicative_index.value}, {first.indicative_index.category})"
    most_polluted = f"{last.location.name} (INDICATIVE_MODEL_INDEX {last.indicative_index.value}, {last.indicative_index.category})"
    return cleanest, most_polluted


air_quality_service = AirQualityPipelineService()
