/**
 * AirAware AI — Backend API Client
 * Aligned with Stage 3.1–3.2.3 backend routes and strict extra="forbid" schemas.
 *
 * NEVER send client-supplied AQI, aqi_category, dominant_pollutant, or
 * current_context / comparison_context fields — the backend rejects them.
 */

import {
  AirQualityPipelineResponse,
  HistoricalTrendsResponse,
  ComparisonResponse,
  RecommendationResponse,
  AIChatResponse,
  AIChatMessage,
  CityInfo,
} from "./types";

const BASE_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api/v1"
).replace(/\/+$/, "");

// ─── Helper ─────────────────────────────────────────────────────────

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(
      err.message || err.detail?.message || err.detail || `Request failed (${res.status})`
    );
  }
  return res.json();
}

// ─── City Registry ──────────────────────────────────────────────────

export async function fetchCities(): Promise<CityInfo[]> {
  const res = await fetch(`${BASE_URL}/air-quality/cities`, { cache: "no-store" });
  return handleResponse<CityInfo[]>(res);
}

// ─── Current Air Quality (Stage 3.1 Pipeline) ───────────────────────

export async function fetchCurrentAirQuality(params: {
  city?: string;
  latitude?: number;
  longitude?: number;
}): Promise<AirQualityPipelineResponse> {
  const query = new URLSearchParams();
  if (params.city) query.append("city", params.city);
  if (params.latitude !== undefined) query.append("latitude", params.latitude.toString());
  if (params.longitude !== undefined) query.append("longitude", params.longitude.toString());

  const res = await fetch(`${BASE_URL}/air-quality/current?${query.toString()}`, {
    cache: "no-store",
  });
  return handleResponse<AirQualityPipelineResponse>(res);
}

// ─── Historical Trends ──────────────────────────────────────────────

export async function fetchHistoricalTrends(params: {
  city?: string;
  latitude?: number;
  longitude?: number;
  pastDays?: number;
}): Promise<HistoricalTrendsResponse> {
  const query = new URLSearchParams();
  if (params.city) query.append("city", params.city);
  if (params.latitude !== undefined) query.append("latitude", params.latitude.toString());
  if (params.longitude !== undefined) query.append("longitude", params.longitude.toString());
  query.append("past_days", (params.pastDays || 7).toString());

  const res = await fetch(`${BASE_URL}/air-quality/historical?${query.toString()}`, {
    cache: "no-store",
  });
  return handleResponse<HistoricalTrendsResponse>(res);
}

// ─── Comparison (POST with locations array) ──────────────────────────

export async function fetchComparison(
  locations: Array<{ city?: string; latitude?: number; longitude?: number }>
): Promise<ComparisonResponse> {
  const res = await fetch(`${BASE_URL}/air-quality/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ locations }),
    cache: "no-store",
  });
  return handleResponse<ComparisonResponse>(res);
}

// ─── Recommendations ────────────────────────────────────────────────
// MUST NOT include aqi, aqi_category, dominant_pollutant — backend forbids them.

export async function fetchRecommendations(params: {
  city?: string;
  latitude?: number;
  longitude?: number;
  activity: string;
  vulnerability_group: string;
  duration: string;
}): Promise<RecommendationResponse> {
  const res = await fetch(`${BASE_URL}/recommendations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
    cache: "no-store",
  });
  return handleResponse<RecommendationResponse>(res);
}

// ─── AI Chat ────────────────────────────────────────────────────────
// MUST NOT include current_context or comparison_context — backend forbids them.

export async function sendAIChat(params: {
  message: string;
  city?: string;
  latitude?: number;
  longitude?: number;
  chat_history?: AIChatMessage[];
}): Promise<AIChatResponse> {
  const res = await fetch(`${BASE_URL}/ai/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message: params.message,
      city: params.city,
      latitude: params.latitude,
      longitude: params.longitude,
      chat_history: (params.chat_history || []).slice(-10).map((m) => ({
        role: m.role,
        content: m.content.slice(0, 1000),
      })),
    }),
    cache: "no-store",
  });
  return handleResponse<AIChatResponse>(res);
}
