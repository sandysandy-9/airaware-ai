"use client";

import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Info,
} from "lucide-react";
import { ComparisonResponse } from "../lib/types";
import { fetchCities, fetchComparison } from "../lib/api";
import { POPULAR_CITIES, AQI_CATEGORY_META } from "../lib/constants";
import {
  ComparisonCityOption,
  resolveComparisonCityOptions,
  toggleComparisonCitySelection,
  buildComparisonRequestPayload,
} from "../lib/comparison";

export function LocationComparison() {
  const [availableCities, setAvailableCities] = useState<ComparisonCityOption[]>(POPULAR_CITIES);
  const [selectedCities, setSelectedCities] = useState<string[]>([
    "delhi",
    "mumbai",
    "bengaluru",
    "kolkata",
  ]);
  const [comparisonData, setComparisonData] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    fetchCities()
      .then((list) => {
        if (active) {
          setAvailableCities(resolveComparisonCityOptions(list, POPULAR_CITIES));
        }
      })
      .catch(() => {
        // Keep POPULAR_CITIES as graceful fallback without inventing coordinates
      });
    return () => {
      active = false;
    };
  }, []);

  const loadComparison = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = buildComparisonRequestPayload(selectedCities, availableCities);
      const data = await fetchComparison(payload);
      setComparisonData(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to compare locations";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedCities.length >= 2) {
      loadComparison();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCities]);

  const toggleCity = (cityId: string) => {
    setSelectedCities((prev) => toggleComparisonCitySelection(prev, cityId));
  };

  return (
    <div className="bg-navy-900/90 border border-navy-800 rounded-3xl p-6 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-xl font-bold text-white tracking-tight">
              Location Comparison Matrix
            </h3>
            <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30 whitespace-nowrap shrink-0">
              Indicative Model
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Compare indicative air quality estimates across 2 to 6 cities
          </p>
        </div>

        <button
          onClick={loadComparison}
          disabled={loading}
          className="self-start sm:self-auto px-3.5 py-1.5 rounded-xl bg-navy-800 hover:bg-navy-700 text-xs font-semibold text-slate-300 hover:text-white transition-colors flex items-center space-x-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh Comparison</span>
        </button>
      </div>

      {/* City Selector */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-slate-300">
          Selected Cities (2 to 6):
        </span>
        <div className="flex flex-wrap gap-2">
          {availableCities.map((c) => {
            const isSelected = selectedCities.includes(c.id);
            return (
              <button
                key={c.id}
                onClick={() => toggleCity(c.id)}
                className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border ${
                  isSelected
                    ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-sm"
                    : "bg-navy-850 text-slate-400 hover:text-slate-200 border-navy-700/60 hover:border-navy-600"
                }`}
              >
                {c.name} {isSelected && "✓"}
              </button>
            );
          })}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-start space-x-2.5 text-xs text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {/* Data Integrity Warnings */}
      {comparisonData && comparisonData.data_integrity_warnings.length > 0 && (
        <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-300 space-y-1">
          <div className="flex items-center gap-1.5 font-semibold">
            <AlertTriangle className="w-4 h-4 text-amber-400" />
            <span>Data Integrity Warnings</span>
          </div>
          {comparisonData.data_integrity_warnings.map((w, idx) => (
            <p key={idx}>{w}</p>
          ))}
        </div>
      )}

      {/* Results */}
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center space-y-3">
          <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
          <span className="text-xs text-slate-400">
            Fetching model-derived estimates across locations...
          </span>
        </div>
      ) : comparisonData ? (
        <div className="space-y-4">
          {/* Quick Stats */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {comparisonData.cleanest_location && (
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center space-x-3">
                <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <span className="text-[11px] uppercase tracking-wider font-bold text-emerald-400">
                    Relatively Cleaner
                  </span>
                  <p className="text-sm font-semibold text-white">
                    {comparisonData.cleanest_location}
                  </p>
                </div>
              </div>
            )}
            {comparisonData.most_polluted_location && (
              <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center space-x-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                <div>
                  <span className="text-[11px] uppercase tracking-wider font-bold text-rose-400">
                    Highest Indicative Index
                  </span>
                  <p className="text-sm font-semibold text-white">
                    {comparisonData.most_polluted_location}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Table */}
          <div className="overflow-x-auto rounded-2xl border border-navy-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-navy-950 text-slate-400 uppercase tracking-wider text-[10px] border-b border-navy-800">
                <tr>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Index</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Dominant</th>
                  <th className="px-4 py-3">PM2.5</th>
                  <th className="px-4 py-3">PM10</th>
                  <th className="px-4 py-3">NO2</th>
                  <th className="px-4 py-3">Valid Time</th>
                  <th className="px-4 py-3">Freshness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/60 bg-navy-900/50">
                {comparisonData.comparison_items.map((item, idx) => {
                  if (item.status === "PROVIDER_UNAVAILABLE" || !item.assessment) {
                    return (
                      <tr key={idx} className="opacity-60">
                        <td className="px-4 py-3 font-semibold text-white whitespace-nowrap">
                          {item.requested_location}
                        </td>
                        <td colSpan={8} className="px-4 py-3 text-amber-300 text-xs">
                          {item.error || "Provider unavailable"}
                        </td>
                      </tr>
                    );
                  }

                  const assessment = item.assessment;
                  const aqiVal = assessment.indicative_index.value;
                  const category = assessment.indicative_index.category;
                  const catMeta = category
                    ? AQI_CATEGORY_META[category as keyof typeof AQI_CATEGORY_META]
                    : null;
                  const pm25 = assessment.pollutants?.pm25;
                  const pm10 = assessment.pollutants?.pm10;
                  const no2 = assessment.pollutants?.no2;
                  const freshLabel = assessment.freshness.status.replace(/_/g, " ");

                  return (
                    <tr key={idx} className="hover:bg-navy-850/60 transition-colors">
                      <td className="px-4 py-3 font-semibold text-white whitespace-nowrap">
                        {item.requested_location}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-base font-black text-white">
                          {aqiVal ?? "N/A"}
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {catMeta ? (
                          <span
                            className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${catMeta.badgeColor}`}
                          >
                            {catMeta.label}
                          </span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-300 whitespace-nowrap">
                        {assessment.indicative_index.dominant_pollutant_name || "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-200 whitespace-nowrap">
                        {pm25?.concentration != null ? pm25.concentration.toFixed(1) : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-200 whitespace-nowrap">
                        {pm10?.concentration != null ? pm10.concentration.toFixed(1) : "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-200 whitespace-nowrap">
                        {no2?.concentration != null ? no2.concentration.toFixed(1) : "—"}
                      </td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                        {new Date(assessment.temporal_governance.valid_time).toLocaleTimeString(
                          [],
                          { hour: "2-digit", minute: "2-digit" }
                        )}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-[10px] text-emerald-400 font-medium capitalize">
                          {freshLabel}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Provenance note */}
          <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
            <Info className="w-3.5 h-3.5 text-slate-500" />
            <span>
              All values are indicative model-derived estimates (CAMS Global), not official CPCB
              station readings.
            </span>
          </div>
        </div>
      ) : null}
    </div>
  );
}
