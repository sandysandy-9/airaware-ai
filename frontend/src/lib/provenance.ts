import type { TemporalGovernance } from "./types";

export interface TemporalProvenanceItem {
  id: string;
  label: string;
  value: string;
}

export function formatUtcIsoTimestamp(raw: string | null | undefined): string | null {
  if (!raw || typeof raw !== "string" || !raw.trim()) return null;
  const parsed = new Date(raw);
  if (Number.isNaN(parsed.getTime())) return null;
  // Explicit UTC timestamp prevents confusion between model issue, valid, and retrieval times
  return parsed.toISOString().replace("T", " ").slice(0, 19) + " UTC";
}

export function formatForecastLead(hours: number | null | undefined): string | null {
  if (typeof hours !== "number" || !Number.isFinite(hours)) return null;
  const sign = hours > 0 ? "+" : "";
  return `${sign}${hours.toFixed(1)}h`;
}

/**
 * Build display-ready temporal provenance items strictly from actual backend response values.
 * Unavailable fields are omitted rather than invented.
 */
export function buildTemporalProvenanceItems(
  tg: TemporalGovernance | null | undefined
): TemporalProvenanceItem[] {
  if (!tg) return [];
  const items: TemporalProvenanceItem[] = [];

  const valid = formatUtcIsoTimestamp(tg.valid_time);
  if (valid) {
    items.push({ id: "valid_time", label: "Valid time", value: valid });
  }

  const issued = formatUtcIsoTimestamp(tg.model_issue_time);
  if (issued) {
    items.push({ id: "model_issue_time", label: "Model issue time", value: issued });
  }

  const retrieved = formatUtcIsoTimestamp(tg.retrieval_time);
  if (retrieved) {
    items.push({ id: "retrieval_time", label: "Retrieved at", value: retrieved });
  }

  if (tg.model_run_relation && tg.model_run_relation.trim()) {
    items.push({
      id: "model_run_relation",
      label: "Run relation",
      value: tg.model_run_relation,
    });
  }

  const lead = formatForecastLead(tg.forecast_lead_hours);
  if (lead) {
    items.push({ id: "forecast_lead_hours", label: "Forecast lead", value: lead });
  }

  return items;
}
