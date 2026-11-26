"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertRule, TriggeredAlert, AirQualityPipelineResponse } from "../lib/types";

const STORAGE_KEY_RULES = "airaware_alert_rules_v1";
const STORAGE_KEY_HISTORY = "airaware_alert_history_v1";

export function sanitizeAlertRules(raw: unknown): AlertRule[] {
  if (!Array.isArray(raw)) return [];
  const valid: AlertRule[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    if (
      typeof obj.id !== "string" ||
      !obj.id.trim() ||
      typeof obj.city !== "string" ||
      !obj.city.trim() ||
      typeof obj.thresholdAqi !== "number" ||
      !Number.isFinite(obj.thresholdAqi) ||
      obj.thresholdAqi < 0 ||
      obj.thresholdAqi > 500 ||
      typeof obj.enabled !== "boolean"
    ) {
      continue;
    }
    valid.push({
      id: obj.id,
      city: obj.city,
      thresholdAqi: obj.thresholdAqi,
      enabled: obj.enabled,
      createdAt: typeof obj.createdAt === "string" ? obj.createdAt : new Date(0).toISOString(),
    });
  }
  return valid;
}

export function sanitizeAlertHistory(raw: unknown): TriggeredAlert[] {
  if (!Array.isArray(raw)) return [];
  const valid: TriggeredAlert[] = [];
  for (const entry of raw) {
    if (!entry || typeof entry !== "object") continue;
    const obj = entry as Record<string, unknown>;
    if (
      typeof obj.id !== "string" ||
      !obj.id.trim() ||
      typeof obj.city !== "string" ||
      !obj.city.trim() ||
      typeof obj.aqi !== "number" ||
      !Number.isFinite(obj.aqi) ||
      typeof obj.category !== "string" ||
      typeof obj.timestamp !== "string" ||
      typeof obj.message !== "string"
    ) {
      continue;
    }
    valid.push({
      id: obj.id,
      city: obj.city,
      aqi: obj.aqi,
      category: obj.category,
      timestamp: obj.timestamp,
      message: obj.message,
    });
  }
  return valid.slice(0, 20);
}

export interface AlertStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
  removeItem?(key: string): void;
}

export function createDefaultAlertRules(): AlertRule[] {
  return [
    {
      id: "rule-default-1",
      city: "New Delhi",
      thresholdAqi: 200,
      enabled: true,
      createdAt: new Date().toISOString(),
    },
  ];
}

/**
 * Load alert rules from storage:
 * - Seeds default rule ONLY when no key exists yet (stored === null).
 * - Preserves an explicitly stored empty array ("[]").
 * - Recovers safely to [] when JSON is malformed or stored structure is invalid.
 */
export function loadInitialAlertRules(storage: AlertStorageLike): AlertRule[] {
  try {
    const storedRules = storage.getItem(STORAGE_KEY_RULES);
    if (storedRules === null) {
      const defaultRules = createDefaultAlertRules();
      try {
        storage.setItem(STORAGE_KEY_RULES, JSON.stringify(defaultRules));
      } catch {
        // Ignore storage write errors (e.g. private browsing quota)
      }
      return defaultRules;
    }
    return sanitizeAlertRules(JSON.parse(storedRules));
  } catch {
    return [];
  }
}

export function loadInitialAlertHistory(storage: AlertStorageLike): TriggeredAlert[] {
  try {
    const storedHistory = storage.getItem(STORAGE_KEY_HISTORY);
    if (!storedHistory) return [];
    return sanitizeAlertHistory(JSON.parse(storedHistory));
  } catch {
    return [];
  }
}

export function useAlerts() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [history, setHistory] = useState<TriggeredAlert[]>([]);
  const [activeBanner, setActiveBanner] = useState<TriggeredAlert | null>(null);

  // Load from local storage with strict schema validation
  useEffect(() => {
    try {
      setRules(loadInitialAlertRules(localStorage));
      setHistory(loadInitialAlertHistory(localStorage));
    } catch {
      // LocalStorage unavailable
    }
  }, []);

  const persistRules = (updated: AlertRule[]) => {
    try {
      localStorage.setItem(STORAGE_KEY_RULES, JSON.stringify(updated));
    } catch {}
  };

  const saveRules = (updated: AlertRule[]) => {
    setRules(updated);
    persistRules(updated);
  };

  const addRule = (city: string, thresholdAqi: number) => {
    const newRule: AlertRule = {
      id: `rule-${Date.now()}`,
      city,
      thresholdAqi,
      enabled: true,
      createdAt: new Date().toISOString(),
    };
    setRules((prev) => {
      const updated = [...prev, newRule];
      persistRules(updated);
      return updated;
    });
  };

  const toggleRule = (id: string) => {
    setRules((prev) => {
      const updated = prev.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r));
      persistRules(updated);
      return updated;
    });
  };

  const deleteRule = (id: string) => {
    setRules((prev) => {
      const updated = prev.filter((r) => r.id !== id);
      persistRules(updated);
      return updated;
    });
  };

  const checkThreshold = useCallback(
    (currentData: AirQualityPipelineResponse) => {
      if (!currentData || currentData.indicative_index.status !== "AVAILABLE") return;
      const aqi = currentData.indicative_index.value;
      if (aqi === null || aqi === undefined) return;

      const locName = currentData.location.name.toLowerCase();
      const category = currentData.indicative_index.category || "Unknown";
      const freshnessStatus = currentData.freshness?.status || "UNKNOWN_RUN_AGE";
      const isStaleOrUnknown =
        freshnessStatus === "STALE_CYCLE" ||
        freshnessStatus === "UNKNOWN_RUN_AGE" ||
        freshnessStatus === "AGING_CYCLE";
      const freshnessDisclosure = isStaleOrUnknown
        ? ` [Data freshness: ${freshnessStatus.replace(/_/g, " ")} — model cycle may be stale]`
        : "";

      for (const rule of rules) {
        if (!rule.enabled) continue;
        const ruleCity = rule.city.toLowerCase();
        if (
          locName.includes(ruleCity) ||
          ruleCity.includes(locName) ||
          rule.city === "All Cities"
        ) {
          if (aqi >= rule.thresholdAqi) {
            // Deduplicate within 3 hours
            const threeHoursAgo = Date.now() - 3 * 60 * 60 * 1000;
            const recent = history.find(
              (h) =>
                h.city.toLowerCase() === currentData.location.name.toLowerCase() &&
                new Date(h.timestamp).getTime() > threeHoursAgo
            );

            if (!recent) {
              const triggered: TriggeredAlert = {
                id: `alert-${Date.now()}`,
                city: currentData.location.name,
                aqi: aqi,
                category: category,
                timestamp: new Date().toISOString(),
                message: `Indicative Model Index (CAMS model-derived estimate, not official CPCB station AQI) in ${currentData.location.name} is ${aqi} (${category}), exceeding your threshold of ${rule.thresholdAqi}.${freshnessDisclosure}`,
              };

              setActiveBanner(triggered);
              const updatedHistory = [triggered, ...history].slice(0, 20);
              setHistory(updatedHistory);
              try {
                localStorage.setItem(
                  STORAGE_KEY_HISTORY,
                  JSON.stringify(updatedHistory)
                );
              } catch {}
            }
          }
        }
      }
    },
    [rules, history]
  );

  const dismissBanner = () => {
    setActiveBanner(null);
  };

  const clearHistory = () => {
    setHistory([]);
    try {
      localStorage.removeItem(STORAGE_KEY_HISTORY);
    } catch {}
  };

  return {
    rules,
    history,
    activeBanner,
    addRule,
    toggleRule,
    deleteRule,
    checkThreshold,
    dismissBanner,
    clearHistory,
  };
}
