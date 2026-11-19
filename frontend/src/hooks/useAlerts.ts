"use client";

import { useState, useEffect, useCallback } from "react";
import { AlertRule, TriggeredAlert, AirQualityCurrentResponse } from "../lib/types";

const STORAGE_KEY_RULES = "airaware_alert_rules_v1";
const STORAGE_KEY_HISTORY = "airaware_alert_history_v1";

export function useAlerts() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [history, setHistory] = useState<TriggeredAlert[]>([]);
  const [activeBanner, setActiveBanner] = useState<TriggeredAlert | null>(null);

  // Load from local storage
  useEffect(() => {
    try {
      const storedRules = localStorage.getItem(STORAGE_KEY_RULES);
      if (storedRules) {
        setRules(JSON.parse(storedRules));
      } else {
        // Default rule: Alert when Delhi AQI exceeds 200 (Poor)
        const defaultRules: AlertRule[] = [
          {
            id: "rule-default-1",
            city: "New Delhi",
            thresholdAqi: 200,
            enabled: true,
            createdAt: new Date().toISOString(),
          },
        ];
        setRules(defaultRules);
        localStorage.setItem(STORAGE_KEY_RULES, JSON.stringify(defaultRules));
      }

      const storedHistory = localStorage.getItem(STORAGE_KEY_HISTORY);
      if (storedHistory) {
        setHistory(JSON.parse(storedHistory));
      }
    } catch {
      // LocalStorage unavailable
    }
  }, []);

  const saveRules = (updated: AlertRule[]) => {
    setRules(updated);
    try {
      localStorage.setItem(STORAGE_KEY_RULES, JSON.stringify(updated));
    } catch {}
  };

  const addRule = (city: string, thresholdAqi: number) => {
    const newRule: AlertRule = {
      id: `rule-${Date.now()}`,
      city,
      thresholdAqi,
      enabled: true,
      createdAt: new Date().toISOString(),
    };
    saveRules([...rules, newRule]);
  };

  const toggleRule = (id: string) => {
    const updated = rules.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r));
    saveRules(updated);
  };

  const deleteRule = (id: string) => {
    const updated = rules.filter((r) => r.id !== id);
    saveRules(updated);
  };

  const checkThreshold = useCallback(
    (currentData: AirQualityCurrentResponse) => {
      if (!currentData || currentData.aqi === null) return;
      const aqi = currentData.aqi;
      const locName = currentData.location.name.toLowerCase();

      for (const rule of rules) {
        if (!rule.enabled) continue;
        const ruleCity = rule.city.toLowerCase();
        if (locName.includes(ruleCity) || ruleCity.includes(locName) || rule.city === "All Cities") {
          if (aqi >= rule.thresholdAqi) {
            // Deduplicate: check if triggered in past 3 hours
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
                category: currentData.category || "Unhealthy",
                timestamp: new Date().toISOString(),
                message: `Air Quality in ${currentData.location.name} has reached ${aqi} (${currentData.category}), exceeding your alert threshold of ${rule.thresholdAqi}.`,
              };

              setActiveBanner(triggered);
              const updatedHistory = [triggered, ...history].slice(0, 20);
              setHistory(updatedHistory);
              try {
                localStorage.setItem(STORAGE_KEY_HISTORY, JSON.stringify(updatedHistory));
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
