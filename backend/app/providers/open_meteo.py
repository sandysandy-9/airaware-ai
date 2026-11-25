"""Open-Meteo Copernicus CAMS Real Environmental Data Provider & Stage 2 Validation Adapter."""

import asyncio
from datetime import datetime, timedelta, timezone
import math
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.engine.cpcb_calculator import calculate_cpcb_aqi
from app.engine.cpcb_breakpoints import POLLUTANT_INFO
from app.providers.base import BaseAirQualityProvider
from app.providers.models import (
    NormalizedProviderSeries,
    NormalizedSample,
    PollutantSeriesStats,
    ProviderError,
    ProviderModelMetadata,
    ProviderValidationError,
    TemporalGovernance,
)
from app.schemas.air_quality import (
    AirQualityCurrentResponse,
    HistoricalPoint,
    HistoricalTrendsResponse,
    LocationInfo,
    PollutantDetail,
)

# Canonical mapping from Open-Meteo Air Quality API variables to AirAware internal codes
OPEN_METEO_POLLUTANT_MAP: Dict[str, Tuple[str, str]] = {
    "pm2_5": ("pm25", "µg/m³"),
    "pm10": ("pm10", "µg/m³"),
    "nitrogen_dioxide": ("no2", "µg/m³"),
    "sulphur_dioxide": ("so2", "µg/m³"),
    "carbon_monoxide": ("co", "mg/m³"),  # Converted from reported µg/m³ -> mg/m³
    "ozone": ("o3", "µg/m³"),
    "ammonia": ("nh3", "µg/m³"),
}

DEFAULT_HOURLY_VARIABLES = ",".join(OPEN_METEO_POLLUTANT_MAP.keys())


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute geodesic surface distance in kilometers using the WGS84 mean Earth radius."""
    earth_radius_km = 6371.0088
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(earth_radius_km * c, 4)


def parse_provider_timestamp_to_utc(
    ts_str: str,
    provider_timezone: Optional[str],
    utc_offset_seconds: Optional[int],
) -> Tuple[datetime, Optional[str]]:
    """Parse an Open-Meteo timestamp string and normalize it strictly to UTC."""
    if not isinstance(ts_str, str) or not ts_str.strip():
        raise ProviderValidationError("Missing or empty provider timestamp string.")
    note: Optional[str] = None
    try:
        dt = datetime.fromisoformat(ts_str.strip())
    except ValueError as exc:
        raise ProviderValidationError(f"Unparseable provider timestamp '{ts_str}': {exc}") from exc

    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc), note

    # Timestamp is naive; localize using provider timezone or utc_offset_seconds
    if provider_timezone and provider_timezone not in ("GMT", "UTC"):
        try:
            zi = ZoneInfo(provider_timezone)
            dt_local = dt.replace(tzinfo=zi)
            return dt_local.astimezone(timezone.utc), note
        except (ZoneInfoNotFoundError, Exception):
            if utc_offset_seconds is not None:
                fixed_tz = timezone(timedelta(seconds=utc_offset_seconds))
                note = (
                    f"Host Python environment lacked tzdata key '{provider_timezone}'; "
                    f"converted using provider utc_offset_seconds={utc_offset_seconds}s."
                )
                return dt.replace(tzinfo=fixed_tz).astimezone(timezone.utc), note
            raise ProviderValidationError(
                f"Cannot localize naive timestamp '{ts_str}': timezone '{provider_timezone}' unavailable and utc_offset_seconds missing."
            )

    if utc_offset_seconds is not None:
        fixed_tz = timezone(timedelta(seconds=utc_offset_seconds))
        return dt.replace(tzinfo=fixed_tz).astimezone(timezone.utc), note

    return dt.replace(tzinfo=timezone.utc), "No timezone or offset provided; assumed UTC."


def _convert_unit_if_needed(
    api_field: str,
    val: float,
    reported_unit: Optional[str],
) -> Tuple[float, str]:
    """Convert raw numeric concentration to canonical target unit."""
    _, target_unit = OPEN_METEO_POLLUTANT_MAP[api_field]

    if api_field == "carbon_monoxide":
        unit_norm = (reported_unit or "").strip().lower()
        if unit_norm in ("μg/m³", "µg/m³", "ug/m3", "ug/m^3"):
            return val / 1000.0, target_unit
        elif unit_norm in ("mg/m³", "mg/m3", "mg/m^3"):
            return val, target_unit
        else:
            raise ProviderValidationError(
                f"Unsupported unit '{reported_unit}' for carbon_monoxide; expected µg/m³ or mg/m³."
            )

    if reported_unit is not None:
        unit_norm = reported_unit.strip().lower()
        if unit_norm not in ("μg/m³", "µg/m³", "ug/m3", "ug/m^3"):
            raise ProviderValidationError(
                f"Unexpected unit '{reported_unit}' for {api_field}; expected µg/m³."
            )

    return val, target_unit


def _ensure_utc_datetime(value: Any, field_name: str) -> datetime:
    """Validate that a required timestamp is present, valid, timezone-aware, and normalized to UTC."""
    if value is None:
        raise ProviderValidationError(f"Missing required timestamp '{field_name}'.")
    if isinstance(value, str):
        if not value.strip():
            raise ProviderValidationError(f"Empty timestamp string for '{field_name}'.")
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise ProviderValidationError(f"Invalid timestamp '{value}' for '{field_name}': {exc}") from exc
        if parsed.tzinfo is None:
            raise ProviderValidationError(f"Timestamp string '{value}' for '{field_name}' lacks timezone offset.")
        return parsed.astimezone(timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ProviderValidationError(f"Naive datetime not permitted for '{field_name}'; UTC required.")
        return value.astimezone(timezone.utc)
    raise ProviderValidationError(f"Unsupported timestamp type {type(value).__name__} for '{field_name}'.")


def build_temporal_governance(
    metadata: ProviderModelMetadata,
    valid_time_utc: Any,
    retrieval_time_utc: Any,
    provider_timezone: Optional[str],
    utc_offset_seconds: Optional[int],
) -> TemporalGovernance:
    """Compute separated valid-time vs retrieval relationship and model-run relation without conflation."""
    v_utc = _ensure_utc_datetime(valid_time_utc, "valid_time")
    r_utc = _ensure_utc_datetime(retrieval_time_utc, "retrieval_time")

    issue_time: Optional[datetime] = None
    if metadata.metadata_verified_for_response and metadata.last_run_initialisation_time is not None:
        issue_time = _ensure_utc_datetime(metadata.last_run_initialisation_time, "model_issue_time")

    # 1. Determine valid-time relationship strictly from valid_time - retrieval_time
    offset_seconds = (v_utc - r_utc).total_seconds()
    offset_hours = round(offset_seconds / 3600.0, 4)
    if offset_seconds < 0:
        valid_time_vs_retrieval = "PAST"
    elif offset_seconds == 0:
        valid_time_vs_retrieval = "CURRENT"
    else:
        valid_time_vs_retrieval = "FUTURE"

    # 2. Determine model-run relation strictly from valid_time - model_issue_time (never from retrieval_time)
    model_run_age_hours: Optional[float] = None
    forecast_lead_hours: Optional[float] = None
    if issue_time is not None:
        model_run_age_hours = round((r_utc - issue_time).total_seconds() / 3600.0, 4)
        lead_seconds = (v_utc - issue_time).total_seconds()
        forecast_lead_hours = round(lead_seconds / 3600.0, 4)
        if lead_seconds > 0:
            model_run_relation = "FORECAST"
        elif lead_seconds == 0:
            model_run_relation = "ANALYSIS"
        else:
            # Valid time predates the verified run's initialization; archived earlier cycle provenance unavailable
            model_run_relation = "UNKNOWN"
    else:
        model_run_relation = "UNKNOWN"

    return TemporalGovernance(
        model_issue_time=issue_time,
        valid_time=v_utc,
        retrieval_time=r_utc,
        model_run_age_hours=model_run_age_hours,
        forecast_lead_hours=forecast_lead_hours,
        valid_time_offset_hours=offset_hours,
        valid_time_vs_retrieval=valid_time_vs_retrieval,
        model_run_relation=model_run_relation,
        data_source_type="MODEL_DERIVED",
        provider_timezone=provider_timezone,
        provider_utc_offset_seconds=utc_offset_seconds,
    )


def _parse_validated_coordinate(raw_val: Any, name: str, min_val: float, max_val: float) -> float:
    """Parse and range-check provider coordinate without raising unhandled ValueError/TypeError."""
    if raw_val is None or isinstance(raw_val, bool):
        raise ProviderValidationError(f"Missing or invalid '{name}' in provider response: {raw_val!r}")
    try:
        parsed = float(raw_val)
    except (TypeError, ValueError) as exc:
        raise ProviderValidationError(
            f"Malformed '{name}' in provider response: {raw_val!r}"
        ) from exc
    if not math.isfinite(parsed) or not (min_val <= parsed <= max_val):
        raise ProviderValidationError(
            f"Out-of-bounds or non-finite '{name}' in provider response: {raw_val!r}"
        )
    return parsed


def normalize_open_meteo_response(
    raw_data: Dict[str, Any],
    *,
    requested_latitude: float,
    requested_longitude: float,
    domain_requested: str,
    request_url: str,
    request_params: Dict[str, Any],
    http_status: int,
    retrieval_time_utc: datetime,
    raw_meta_json: Optional[Dict[str, Any]] = None,
    meta_source_url: Optional[str] = None,
    target_valid_time_utc: Optional[datetime] = None,
) -> NormalizedProviderSeries:
    """Validate and normalize an Open-Meteo Air Quality JSON response into canonical UTC structures."""
    if not isinstance(raw_data, dict):
        raise ProviderValidationError("Provider response root payload must be a JSON object.")

    if "error" in raw_data and raw_data.get("error") is True:
        raise ProviderValidationError(f"Provider returned API error: {raw_data.get('reason', 'Unknown')}")

    hourly = raw_data.get("hourly")
    if not isinstance(hourly, dict):
        raise ProviderValidationError("Missing or invalid 'hourly' object in provider response.")

    raw_times = hourly.get("time")
    if not isinstance(raw_times, list) or len(raw_times) == 0:
        raise ProviderValidationError("Missing or empty 'hourly.time' timestamp array.")

    returned_lat = _parse_validated_coordinate(raw_data.get("latitude"), "latitude", -90.0, 90.0)
    returned_lon = _parse_validated_coordinate(raw_data.get("longitude"), "longitude", -180.0, 180.0)

    geodesic_km = haversine_distance_km(
        requested_latitude, requested_longitude, returned_lat, returned_lon
    )

    provider_tz = raw_data.get("timezone")
    utc_offset = raw_data.get("utc_offset_seconds")
    hourly_units = raw_data.get("hourly_units", {}) or {}
    elevation = raw_data.get("elevation")

    anomalies: List[str] = []
    tz_notes_set = set()

    # Parse all timestamps to UTC
    timestamps_utc: List[datetime] = []
    seen_ts: Dict[datetime, int] = {}

    for idx, t_str in enumerate(raw_times):
        if not isinstance(t_str, str):
            raise ProviderValidationError(f"Non-string timestamp at hourly.time[{idx}].")
        dt_utc, tz_note = parse_provider_timestamp_to_utc(t_str, provider_tz, utc_offset)
        if tz_note:
            tz_notes_set.add(tz_note)
        timestamps_utc.append(dt_utc)
        if dt_utc in seen_ts:
            anomalies.append(f"Duplicate timestamp detected at index {idx}: {t_str} ({dt_utc.isoformat()}).")
        else:
            seen_ts[dt_utc] = idx

    # Infer API output frequency directly from timestamp spacings
    raw_spacings = [
        (timestamps_utc[i + 1] - timestamps_utc[i]).total_seconds()
        for i in range(len(timestamps_utc) - 1)
    ]
    api_output_freq: Optional[int] = None
    if raw_spacings:
        unique_spacings = set(int(s) for s in raw_spacings if s > 0)
        if len(unique_spacings) == 1:
            api_output_freq = next(iter(unique_spacings))

    # Validate array lengths and normalize each pollutant
    pollutant_series: Dict[str, List[NormalizedSample]] = {}
    pollutant_stats: Dict[str, PollutantSeriesStats] = {}
    unavailable_pollutants: List[str] = []
    last_non_null_utc_global: Optional[datetime] = None

    for api_field, (canon_code, target_unit) in OPEN_METEO_POLLUTANT_MAP.items():
        if api_field not in hourly:
            unavailable_pollutants.append(canon_code)
            pollutant_series[canon_code] = []
            pollutant_stats[canon_code] = PollutantSeriesStats(
                field_name=api_field,
                canonical_code=canon_code,
                present=False,
                is_empty=True,
                reported_unit=hourly_units.get(api_field),
                expected_target_unit=target_unit,
                timestamp_count=len(timestamps_utc),
                valid_count=0,
                null_count=len(timestamps_utc),
                non_finite_count=0,
                negative_count=0,
            )
            continue

        raw_arr = hourly[api_field]
        if not isinstance(raw_arr, list):
            raise ProviderValidationError(f"Pollutant field '{api_field}' must be an array.")

        if len(raw_arr) != len(raw_times):
            raise ProviderValidationError(
                f"Array length mismatch for '{api_field}': got {len(raw_arr)}, expected {len(raw_times)}."
            )

        rep_unit = hourly_units.get(api_field)
        samples: List[NormalizedSample] = []
        valid_count = 0
        null_count = 0
        non_finite_count = 0
        negative_count = 0
        valid_timestamps: List[datetime] = []

        for idx, raw_val in enumerate(raw_arr):
            dt_utc = timestamps_utc[idx]
            orig_ts = raw_times[idx]

            if raw_val is None:
                null_count += 1
                samples.append(
                    NormalizedSample(
                        timestamp_utc=dt_utc,
                        original_timestamp=orig_ts,
                        value=None,
                        unit=target_unit,
                        validity_flag="NULL",
                    )
                )
                continue

            try:
                fval = float(raw_val)
            except (TypeError, ValueError):
                non_finite_count += 1
                anomalies.append(f"Non-numeric value {raw_val!r} at {api_field}[{idx}].")
                samples.append(
                    NormalizedSample(
                        timestamp_utc=dt_utc,
                        original_timestamp=orig_ts,
                        value=None,
                        unit=target_unit,
                        validity_flag="NON_FINITE",
                    )
                )
                continue

            if math.isnan(fval) or math.isinf(fval):
                non_finite_count += 1
                anomalies.append(f"Non-finite value ({fval}) at {api_field}[{idx}].")
                samples.append(
                    NormalizedSample(
                        timestamp_utc=dt_utc,
                        original_timestamp=orig_ts,
                        value=None,
                        unit=target_unit,
                        validity_flag="NON_FINITE",
                    )
                )
                continue

            if fval < 0.0:
                negative_count += 1
                anomalies.append(f"Negative concentration ({fval}) at {api_field}[{idx}].")
                samples.append(
                    NormalizedSample(
                        timestamp_utc=dt_utc,
                        original_timestamp=orig_ts,
                        value=None,
                        unit=target_unit,
                        validity_flag="NEGATIVE",
                    )
                )
                continue

            converted_val, final_unit = _convert_unit_if_needed(api_field, fval, rep_unit)
            valid_count += 1
            valid_timestamps.append(dt_utc)
            if last_non_null_utc_global is None or dt_utc > last_non_null_utc_global:
                last_non_null_utc_global = dt_utc

            samples.append(
                NormalizedSample(
                    timestamp_utc=dt_utc,
                    original_timestamp=orig_ts,
                    value=converted_val,
                    unit=final_unit,
                    validity_flag="VALID",
                )
            )

        is_empty = valid_count == 0
        if is_empty:
            unavailable_pollutants.append(canon_code)

        spacings = [
            (valid_timestamps[i + 1] - valid_timestamps[i]).total_seconds()
            for i in range(len(valid_timestamps) - 1)
        ]
        missing_intervals = sum(1 for s in spacings if api_output_freq and s > api_output_freq)
        max_gap = max(spacings) if spacings else None

        pollutant_series[canon_code] = samples
        pollutant_stats[canon_code] = PollutantSeriesStats(
            field_name=api_field,
            canonical_code=canon_code,
            present=True,
            is_empty=is_empty,
            reported_unit=rep_unit,
            expected_target_unit=target_unit,
            timestamp_count=len(raw_times),
            valid_count=valid_count,
            null_count=null_count,
            non_finite_count=non_finite_count,
            negative_count=negative_count,
            first_timestamp_provider=raw_times[0] if raw_times else None,
            last_timestamp_provider=raw_times[-1] if raw_times else None,
            first_timestamp_utc=timestamps_utc[0] if timestamps_utc else None,
            last_timestamp_utc=timestamps_utc[-1] if timestamps_utc else None,
            sample_spacings_seconds=sorted(list(set(spacings))),
            missing_interval_count=missing_intervals,
            max_gap_seconds=max_gap,
        )

    # Evaluate Model Metadata Correspondence strictly
    metadata = _build_verified_metadata(
        domain_requested=domain_requested,
        raw_meta_json=raw_meta_json,
        meta_source_url=meta_source_url,
        api_output_freq=api_output_freq,
        last_non_null_utc=last_non_null_utc_global,
    )

    valid_t = target_valid_time_utc or retrieval_time_utc.replace(minute=0, second=0, microsecond=0)
    temporal_gov = build_temporal_governance(
        metadata=metadata,
        valid_time_utc=valid_t,
        retrieval_time_utc=retrieval_time_utc,
        provider_timezone=provider_tz,
        utc_offset_seconds=utc_offset,
    )

    parsed_elevation: Optional[float] = None
    if elevation is not None and not isinstance(elevation, bool):
        try:
            cand_elev = float(elevation)
            if math.isfinite(cand_elev):
                parsed_elevation = cand_elev
        except (TypeError, ValueError):
            parsed_elevation = None

    return NormalizedProviderSeries(
        request_url=request_url,
        request_params=request_params,
        http_status=http_status,
        retrieval_time_utc=retrieval_time_utc,
        requested_latitude=requested_latitude,
        requested_longitude=requested_longitude,
        returned_latitude=returned_lat,
        returned_longitude=returned_lon,
        geodesic_distance_km=geodesic_km,
        elevation_m=parsed_elevation,
        provider_timezone=provider_tz,
        utc_offset_seconds=utc_offset,
        timestamps_utc=timestamps_utc,
        original_timestamps=raw_times,
        pollutant_series=pollutant_series,
        pollutant_stats=pollutant_stats,
        unavailable_pollutants=unavailable_pollutants,
        anomalies=anomalies,
        metadata=metadata,
        temporal_governance=temporal_gov,
        timezone_parsing_notes=sorted(list(tz_notes_set)),
    )


def _build_verified_metadata(
    *,
    domain_requested: str,
    raw_meta_json: Optional[Dict[str, Any]],
    meta_source_url: Optional[str],
    api_output_freq: Optional[int],
    last_non_null_utc: Optional[datetime],
) -> ProviderModelMetadata:
    """Associate static meta.json ONLY when domain correspondence is explicitly verified."""
    if domain_requested != "cams_global":
        return ProviderModelMetadata(
            domain_requested=domain_requested,
            metadata_source_url=None,
            metadata_verified_for_response=False,
            correspondence_reason=(
                "Domain 'auto' (Best Match) dynamically selects models; Open-Meteo warns metadata timestamps "
                "do not correlate directly with Best Match API updates. Metadata preserved as null."
            ),
            model_name="UNKNOWN_PENDING_VERIFICATION",
            native_temporal_resolution="UNKNOWN_PENDING_VERIFICATION",
            api_output_frequency_seconds=api_output_freq,
        )

    if not raw_meta_json:
        return ProviderModelMetadata(
            domain_requested=domain_requested,
            metadata_source_url=meta_source_url,
            metadata_verified_for_response=False,
            correspondence_reason="meta.json unavailable or not fetched; metadata timestamps preserved as null.",
            model_name="cams_global",
            native_temporal_resolution="UNKNOWN_PENDING_VERIFICATION",
            api_output_frequency_seconds=api_output_freq,
        )

    init_ts = raw_meta_json.get("last_run_initialisation_time")
    mod_ts = raw_meta_json.get("last_run_modification_time")
    avail_ts = raw_meta_json.get("last_run_availability_time")
    end_ts = raw_meta_json.get("data_end_time")

    def _safe_unix_utc(ts_val: Any) -> Optional[datetime]:
        if ts_val is None:
            return None
        try:
            return datetime.fromtimestamp(float(ts_val), tz=timezone.utc)
        except (TypeError, ValueError, OSError, OverflowError):
            return None

    init_dt = _safe_unix_utc(init_ts)
    mod_dt = _safe_unix_utc(mod_ts)
    avail_dt = _safe_unix_utc(avail_ts)
    end_dt = _safe_unix_utc(end_ts)

    correspondence_ok = init_dt is not None and end_dt is not None
    reason = (
        "Explicit domain=cams_global matched against /data/cams_global/static/meta.json. "
        "Note: Upstream ECMWF surface-field native resolution remains UNKNOWN_PENDING_VERIFICATION "
        "(meta.json reports Open-Meteo dataset temporal_resolution_seconds vs documentation 3-hourly reference)."
    )
    if not correspondence_ok:
        reason = "Metadata timestamps in meta.json are missing or invalid; preserving null metadata."
    if end_dt is not None and last_non_null_utc is not None and last_non_null_utc > end_dt:
        correspondence_ok = False
        reason = (
            f"Forecast horizon drift detected: API valid data extends to {last_non_null_utc.isoformat()}, "
            f"exceeding meta.json data_end_time {end_dt.isoformat()}. Preserving null metadata."
        )

    return ProviderModelMetadata(
        domain_requested=domain_requested,
        metadata_source_url=meta_source_url,
        metadata_verified_for_response=correspondence_ok,
        correspondence_reason=reason,
        model_name="cams_global",
        native_temporal_resolution="UNKNOWN_PENDING_VERIFICATION",
        meta_temporal_resolution_seconds=raw_meta_json.get("temporal_resolution_seconds") if correspondence_ok else None,
        api_output_frequency_seconds=api_output_freq,
        spatial_resolution_note="0.4 deg x 0.4 deg global grid per crs_wkt BBOX[-90.0,-180.0,90.0,179.6]",
        last_run_initialisation_time=init_dt if correspondence_ok else None,
        last_run_modification_time=mod_dt if correspondence_ok else None,
        last_run_availability_time=avail_dt if correspondence_ok else None,
        update_interval_seconds=raw_meta_json.get("update_interval_seconds") if correspondence_ok else None,
        data_end_time=end_dt if correspondence_ok else None,
    )


logger = get_logger(__name__)


class OpenMeteoProvider(BaseAirQualityProvider):
    name = "Open-Meteo (Copernicus CAMS Atmospheric Grid)"
    BASE_URL = settings.open_meteo_base_url
    META_URL_TEMPLATE = settings.open_meteo_meta_url_template

    def __init__(
        self,
        timeout_seconds: float = settings.open_meteo_read_timeout_seconds,
        connect_timeout_seconds: float = settings.open_meteo_connect_timeout_seconds,
    ):
        self.timeout_seconds = timeout_seconds
        self.connect_timeout_seconds = connect_timeout_seconds

    def _client_timeout(self) -> httpx.Timeout:
        return httpx.Timeout(timeout=self.timeout_seconds, connect=self.connect_timeout_seconds)

    async def fetch_raw_air_quality(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        domain: str = "cams_global",
        timezone_name: str = "Asia/Kolkata",
        hourly_vars: str = DEFAULT_HOURLY_VARIABLES,
    ) -> Tuple[Dict[str, Any], int, str, Dict[str, Any], datetime]:
        """Fetch raw JSON from Open-Meteo Air Quality API with connect/read timeouts and safe error handling."""
        params: Dict[str, Any] = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": hourly_vars,
            "domains": domain,
            "start_date": start_date,
            "end_date": end_date,
            "timezone": timezone_name,
        }
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout()) as client:
                resp = await client.get(self.BASE_URL, params=params)
                retrieval_time_utc = datetime.now(timezone.utc)
                resp.raise_for_status()
                try:
                    payload = resp.json()
                except ValueError as exc:
                    raise ProviderError(
                        "Invalid JSON payload received from Open-Meteo API.",
                        http_status=resp.status_code,
                    ) from exc
                return payload, resp.status_code, str(resp.url), params, retrieval_time_utc
        except httpx.TimeoutException as exc:
            logger.warning("Open-Meteo request timed out after %.1fs (connect=%.1fs)", self.timeout_seconds, self.connect_timeout_seconds)
            raise ProviderError(
                f"Open-Meteo request timed out after {self.timeout_seconds}s.",
                is_timeout=True,
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.warning("Open-Meteo returned HTTP status %d", exc.response.status_code)
            raise ProviderError(
                f"Open-Meteo HTTP {exc.response.status_code} error.",
                http_status=exc.response.status_code,
            ) from exc
        except httpx.RequestError as exc:
            logger.warning("Open-Meteo connection error: %s", type(exc).__name__)
            raise ProviderError(f"Open-Meteo connection failed: {type(exc).__name__}") from exc

    async def fetch_domain_metadata(self, domain: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """Fetch static model metadata JSON for an explicit domain when supported."""
        if domain != "cams_global":
            return None, None
        meta_url = self.META_URL_TEMPLATE.format(domain=domain)
        try:
            async with httpx.AsyncClient(timeout=self._client_timeout()) as client:
                resp = await client.get(meta_url)
                if resp.status_code == 200:
                    try:
                        return resp.json(), meta_url
                    except ValueError:
                        logger.warning("Invalid JSON in metadata endpoint %s", meta_url)
                        return None, meta_url
                return None, meta_url
        except Exception:
            logger.warning("Failed to retrieve domain metadata from %s", meta_url)
            return None, meta_url

    async def fetch_validated_series(
        self,
        latitude: float,
        longitude: float,
        start_date: str,
        end_date: str,
        domain: str = "cams_global",
        timezone_name: str = "Asia/Kolkata",
        target_valid_time_utc: Optional[datetime] = None,
    ) -> Tuple[NormalizedProviderSeries, Dict[str, Any], Optional[Dict[str, Any]]]:
        """Execute concurrent air-quality + metadata fetch, verification, and Stage 2 normalization."""
        if domain == "cams_global":
            aq_res, meta_res = await asyncio.gather(
                self.fetch_raw_air_quality(
                    latitude=latitude,
                    longitude=longitude,
                    start_date=start_date,
                    end_date=end_date,
                    domain=domain,
                    timezone_name=timezone_name,
                ),
                self.fetch_domain_metadata(domain),
            )
            raw_data, status_code, req_url, req_params, retrieval_time = aq_res
            raw_meta, meta_url = meta_res
        else:
            raw_data, status_code, req_url, req_params, retrieval_time = await self.fetch_raw_air_quality(
                latitude=latitude,
                longitude=longitude,
                start_date=start_date,
                end_date=end_date,
                domain=domain,
                timezone_name=timezone_name,
            )
            raw_meta, meta_url = None, None

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
            target_valid_time_utc=target_valid_time_utc,
        )
        return normalized, raw_data, raw_meta

    # --- Existing Stage 0 Legacy Compatibility Methods (Kept intact until Stage 3 route rewrite) ---
    async def get_current_air_quality(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        city: Optional[str] = None,
    ) -> AirQualityCurrentResponse:
        now_iso = datetime.now(timezone.utc).isoformat()
        resolved_city = city or location_name
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "auto",
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            return AirQualityCurrentResponse(
                location=LocationInfo(name=location_name, city=resolved_city, latitude=latitude, longitude=longitude),
                status="ERROR",
                status_message=f"Environmental data source unavailable: {str(e)}",
                observation_time=now_iso,
                retrieval_time=now_iso,
                data_source=self.name,
                data_freshness="UNAVAILABLE",
                pollutants={},
            )

        current = data.get("current", {})
        obs_time = current.get("time", now_iso)
        raw_co_ug = current.get("carbon_monoxide")
        co_mg = (raw_co_ug / 1000.0) if raw_co_ug is not None else None
        concentrations: Dict[str, Optional[float]] = {
            "pm25": float(current["pm2_5"]) if current.get("pm2_5") is not None else None,
            "pm10": float(current["pm10"]) if current.get("pm10") is not None else None,
            "no2": float(current["nitrogen_dioxide"]) if current.get("nitrogen_dioxide") is not None else None,
            "so2": float(current["sulphur_dioxide"]) if current.get("sulphur_dioxide") is not None else None,
            "co": float(co_mg) if co_mg is not None else None,
            "o3": float(current["ozone"]) if current.get("ozone") is not None else None,
            "nh3": None,
            "pb": None,
        }
        cpcb_result = calculate_cpcb_aqi(concentrations)
        pollutant_details: Dict[str, PollutantDetail] = {}
        for pol_code, sub_res in cpcb_result.sub_indices.items():
            meta = POLLUTANT_INFO.get(pol_code, {})
            is_miss = not sub_res.valid or (sub_res.concentration == 0.0 and sub_res.error is not None)
            conc_val = sub_res.concentration if not is_miss else None
            pollutant_details[pol_code] = PollutantDetail(
                code=pol_code,
                name=meta.get("name", pol_code.upper()),
                concentration=conc_val,
                unit=sub_res.unit,
                sub_index=sub_res.sub_index if sub_res.valid else None,
                category=sub_res.category if sub_res.valid else None,
                color=sub_res.color if sub_res.valid else None,
                is_missing=is_miss,
                error=sub_res.error,
                description=meta.get("description", ""),
                health_effects=meta.get("health_effects", ""),
                sources=meta.get("primary_sources", ""),
            )
        dom_name = (
            POLLUTANT_INFO.get(cpcb_result.dominant_pollutant, {}).get("name")
            if cpcb_result.dominant_pollutant
            else None
        )
        return AirQualityCurrentResponse(
            location=LocationInfo(name=location_name, city=resolved_city, latitude=latitude, longitude=longitude),
            aqi=cpcb_result.aqi,
            category=cpcb_result.category,
            color=cpcb_result.color,
            dominant_pollutant=cpcb_result.dominant_pollutant,
            dominant_pollutant_name=dom_name,
            status=cpcb_result.status,
            status_message=cpcb_result.status_message,
            observation_time=obs_time,
            retrieval_time=now_iso,
            data_source=self.name,
            data_freshness="LIVE (< 1h)",
            pollutants=pollutant_details,
        )

    async def get_historical_air_quality(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        past_days: int = 7,
    ) -> HistoricalTrendsResponse:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "past_days": max(1, min(30, past_days)),
            "timezone": "auto",
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        points: List[HistoricalPoint] = []
        for i, t in enumerate(times):
            def _val(key: str) -> Optional[float]:
                arr = hourly.get(key, [])
                return arr[i] if i < len(arr) else None
            co_ug = _val("carbon_monoxide")
            co_mg = (co_ug / 1000.0) if co_ug is not None else None
            concs = {
                "pm25": _val("pm2_5"),
                "pm10": _val("pm10"),
                "no2": _val("nitrogen_dioxide"),
                "so2": _val("sulphur_dioxide"),
                "co": co_mg,
                "o3": _val("ozone"),
            }
            cpcb_res = calculate_cpcb_aqi(concs)
            points.append(
                HistoricalPoint(
                    timestamp=t,
                    aqi=cpcb_res.aqi,
                    pm25=round(concs["pm25"], 1) if concs["pm25"] is not None else None,
                    pm10=round(concs["pm10"], 1) if concs["pm10"] is not None else None,
                    no2=round(concs["no2"], 1) if concs["no2"] is not None else None,
                    so2=round(concs["so2"], 1) if concs["so2"] is not None else None,
                    co=round(co_mg, 2) if co_mg is not None else None,
                    o3=round(concs["o3"], 1) if concs["o3"] is not None else None,
                    dominant_pollutant=cpcb_res.dominant_pollutant,
                )
            )
        return HistoricalTrendsResponse(
            location=LocationInfo(name=location_name, city=location_name, latitude=latitude, longitude=longitude),
            start_time=times[0] if times else "",
            end_time=times[-1] if times else "",
            data_source=self.name,
            interval="1 hour",
            data_points=points,
            total_points=len(points),
        )
