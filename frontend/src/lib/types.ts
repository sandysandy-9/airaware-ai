/**
 * AirAware AI — Frontend Type Definitions
 * Aligned with Stage 3.1–3.2.3 backend schemas.
 *
 * IMPORTANT: These types mirror the actual FastAPI Pydantic response models.
 * Do NOT add fields that the backend does not return.
 */

// ─── Shared Primitives ──────────────────────────────────────────────

export interface LocationInfo {
  name: string;
  city: string;
  state?: string | null;
  country?: string;
  latitude: number;
  longitude: number;
  station_id?: string | null;
}

// ─── Stage 3.1 Pipeline Response ────────────────────────────────────

export interface CoordinateProvenance {
  requested_latitude: number;
  requested_longitude: number;
  returned_latitude: number | null;
  returned_longitude: number | null;
  geodesic_snap_distance_km: number | null;
  elevation_m: number | null;
  coordinate_role: string;
  is_physical_station: false;
}

export interface ProviderProvenance {
  provider_name: string;
  domain_requested: string;
  model_name: string;
  metadata_verified: boolean;
  native_temporal_resolution: string;
  meta_temporal_resolution_seconds: number | null;
  api_output_frequency_seconds: number | null;
  update_interval_seconds: number | null;
  last_run_modification_time: string | null;
  last_run_availability_time: string | null;
  spatial_resolution_note: string | null;
  cache_hit: boolean;
}

export interface IndicativeModelIndexResult {
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  index_type: "INDICATIVE_MODEL_INDEX";
  is_official_cpcb_station_aqi: false;
  value: number | null;
  category: string | null;
  color: string | null;
  dominant_pollutant: string | null;
  dominant_pollutant_name: string | null;
  eligible_pollutants: string[];
  insufficient_or_unavailable_pollutants: string[];
  has_particulate_matter: boolean;
  eligibility_reason: string;
  methodology_note: string;
}

export interface RollingWindowResult {
  status: string;
  concentration: number | null;
  unit: string;
  valid_points: number;
  total_points: number;
  coverage_percent: number | null;
  window_duration_hours: number;
  gap_seconds_max: number | null;
}

export interface PollutantRollingDetail {
  code: string;
  name: string;
  status: "SUFFICIENT" | "INSUFFICIENT_DATA" | "UNAVAILABLE";
  concentration: number | null;
  unit: string;
  reported_unit: string | null;
  sub_index: number | null;
  category: string | null;
  color: string | null;
  averaging_period: string;
  rolling_window: RollingWindowResult | null;
  unavailable_reason: string | null;
  description: string;
  health_effects: string;
  sources: string;
}

export interface TemporalGovernance {
  model_issue_time: string | null;
  valid_time: string;
  retrieval_time: string;
  model_run_age_hours: number | null;
  forecast_lead_hours: number | null;
  valid_time_offset_hours: number;
  valid_time_vs_retrieval: "PAST" | "CURRENT" | "FUTURE";
  model_run_relation: "ANALYSIS" | "FORECAST" | "UNKNOWN";
  data_source_type: "MODEL_DERIVED";
  provider_timezone: string | null;
  provider_utc_offset_seconds: number | null;
}

export interface FreshnessSummary {
  status: "CURRENT_CYCLE" | "AGING_CYCLE" | "STALE_CYCLE" | "UNKNOWN_RUN_AGE";
  cache_hit: boolean;
  disclaimer: string;
}

/** Authoritative Stage 3.1 response from /api/v1/air-quality/current */
export interface AirQualityPipelineResponse {
  status: "SUCCESS" | "INSUFFICIENT_DATA";
  status_message: string;
  index_type: "INDICATIVE_MODEL_INDEX";
  is_official_cpcb_station_aqi: false;
  location: LocationInfo;
  coordinates: CoordinateProvenance;
  provider: ProviderProvenance;
  indicative_index: IndicativeModelIndexResult;
  pollutants: Record<string, PollutantRollingDetail>;
  unavailable_pollutants: string[];
  temporal_governance: TemporalGovernance;
  freshness: FreshnessSummary;
  warnings: string[];
}

// ─── Historical ─────────────────────────────────────────────────────

export interface HistoricalPoint {
  timestamp: string;
  aqi: number | null;
  pm25: number | null;
  pm10: number | null;
  no2: number | null;
  so2: number | null;
  co: number | null;
  o3: number | null;
  dominant_pollutant: string | null;
}

export interface HistoricalTrendsResponse {
  location: LocationInfo;
  start_time: string;
  end_time: string;
  data_source: string;
  interval: string;
  data_points: HistoricalPoint[];
  total_points: number;
  note: string;
}

// ─── Comparison ─────────────────────────────────────────────────────

export interface LocationComparisonResultItem {
  requested_location: string;
  requested_latitude: number;
  requested_longitude: number;
  status: "SUCCESS" | "INSUFFICIENT_DATA" | "PROVIDER_UNAVAILABLE";
  assessment: AirQualityPipelineResponse | null;
  error: string | null;
}

export interface ComparisonResponse {
  generated_at_utc: string;
  index_type: "INDICATIVE_MODEL_INDEX";
  requested_count: number;
  successful_count: number;
  failed_count: number;
  comparison_items: LocationComparisonResultItem[];
  cleanest_location: string | null;
  most_polluted_location: string | null;
  data_integrity_warnings: string[];
}

// ─── Recommendations ────────────────────────────────────────────────

export interface TriggeredRule {
  rule_id: string;
  description: string;
  effect: string;
}

export interface RecommendationResponse {
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  location_name: string | null;
  index_type: "INDICATIVE_MODEL_INDEX";
  is_official_cpcb_station_aqi: false;
  guidance_classification: string;
  aqi: number | null;
  aqi_category: string;
  dominant_pollutant: string | null;
  activity: string;
  vulnerability_group: string;
  duration: string;
  advisory_level: string;
  headline: string;
  actionable_precautions: string[];
  protective_gear: string | null;
  indoor_guidance: string;
  disclaimer: string;
  triggered_rules: TriggeredRule[];
  pollutant_context_status: Record<string, string>;
  data_freshness: string;
  temporal_summary: Record<string, unknown>;
  uncertainty_notes: string[];
}

// ─── AI Chat ────────────────────────────────────────────────────────

export interface AIChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AIChatResponse {
  reply: string;
  grounded_in_data: boolean;
  explanation_mode: "llm_grounded" | "deterministic_fallback";
  model_used: string;
  llm_fallback_used: boolean;
  llm_fallback_reason: string | null;
  prompt_injection_detected: boolean;
  verified_context: Record<string, unknown>;
  sources_cited: string[];
  warnings: string[];
  disclaimer: string;
}

// ─── Alerts (client-side only) ──────────────────────────────────────

export interface AlertRule {
  id: string;
  city: string;
  thresholdAqi: number;
  enabled: boolean;
  createdAt: string;
}

export interface TriggeredAlert {
  id: string;
  city: string;
  aqi: number;
  category: string;
  timestamp: string;
  message: string;
}

// ─── City Registry ──────────────────────────────────────────────────

export interface CityInfo {
  id: string;
  name: string;
  city: string;
  state: string;
  latitude: number;
  longitude: number;
  coordinate_role: string;
  not_a_monitoring_station: boolean;
  provider_domain: string;
}
