"use client";

import React, { useState, useEffect } from "react";
import {
  Layers,
  ArrowUpDown,
  AlertTriangle,
  Clock,
  CheckCircle,
  RefreshCw,
  Plus,
  Trash2,
} from "lucide-react";
import { ComparisonResponse, LocationComparisonItem } from "../lib/types";
import { fetchComparison } from "../lib/api";
import { POPULAR_CITIES, AQI_CATEGORY_META } from "../lib/constants";

export function LocationComparison() {
  const [selectedCities, setSelectedCities] = useState<string[]>([
    "delhi",
    "mumbai",
    "bengaluru",
    "kolkata",
  ]);
  const [comparisonData, setComparisonData] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadComparison = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = selectedCities.map((cid) => ({ city: cid }));
      const data = await fetchComparison(payload);
      setComparisonData(data);
    } catch (err: any) {
      setError(err.message || "Failed to compare locations");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedCities.length >= 2) {
      loadComparison();
    }
  }, [selectedCities]);

  const toggleCity = (cityId: string) => {
    if (selectedCities.includes(cityId)) {
      if (selectedCities.length > 2) {
        setSelectedCities(selectedCities.filter((id) => id !== cityId));
      }
    } else {
      if (selectedCities.length < 6) {
        setSelectedCities([...selectedCities, cityId]);
      }
    }
  };

  return (
    <div className="bg-navy-900/90 border border-navy-800 rounded-3xl p-6 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-xl font-bold text-white tracking-tight">Location Comparison Matrix</h3>
            <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
              Feature D
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Compare verified air quality, dominant pollutants, and observation freshness across 2 to 6 cities
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

      {/* City Toggle Selector */}
      <div className="space-y-2">
        <span className="text-xs font-semibold text-slate-300">Selected Cities to Compare (Select 2 to 6):</span>
        <div className="flex flex-wrap gap-2">
          {POPULAR_CITIES.map((c) => {
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

      {/* Warning Alert if Timestamps skew */}
      {comparisonData?.data_integrity_warning && (
        <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-start space-x-2.5 text-xs text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
          <span>{comparisonData.data_integrity_warning}</span>
        </div>
      )}

      {/* Comparison Table / Grid */}
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center space-y-3">
          <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
          <span className="text-xs text-slate-400">Fetching live observations across locations...</span>
        </div>
      ) : comparisonData ? (
        <div className="space-y-4">
          {/* Quick Metrics Bar */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {comparisonData.cleanest_location && (
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center space-x-3">
                <CheckCircle className="w-5 h-5 text-emerald-400 shrink-0" />
                <div>
                  <span className="text-[11px] uppercase tracking-wider font-bold text-emerald-400">
                    Relatively Cleaner Location
                  </span>
                  <p className="text-sm font-semibold text-white">{comparisonData.cleanest_location}</p>
                </div>
              </div>
            )}
            {comparisonData.most_polluted_location && (
              <div className="p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center space-x-3">
                <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
                <div>
                  <span className="text-[11px] uppercase tracking-wider font-bold text-rose-400">
                    Highest Recorded AQI
                  </span>
                  <p className="text-sm font-semibold text-white">{comparisonData.most_polluted_location}</p>
                </div>
              </div>
            )}
          </div>

          {/* Matrix Table */}
          <div className="overflow-x-auto rounded-2xl border border-navy-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-navy-950 text-slate-400 uppercase tracking-wider text-[10px] border-b border-navy-800">
                <tr>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">CPCB AQI</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Dominant</th>
                  <th className="px-4 py-3">PM2.5 (µg/m³)</th>
                  <th className="px-4 py-3">PM10 (µg/m³)</th>
                  <th className="px-4 py-3">NO2 (µg/m³)</th>
                  <th className="px-4 py-3">Observed</th>
                  <th className="px-4 py-3">Freshness</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/60 bg-navy-900/50">
                {comparisonData.comparison_items.map((item, idx) => {
                  const aq = item.air_quality;
                  const catMeta = aq.category
                    ? AQI_CATEGORY_META[aq.category as keyof typeof AQI_CATEGORY_META]
                    : null;
                  const pm25 = aq.pollutants?.pm25?.concentration ?? "—";
                  const pm10 = aq.pollutants?.pm10?.concentration ?? "—";
                  const no2 = aq.pollutants?.no2?.concentration ?? "—";

                  return (
                    <tr key={idx} className="hover:bg-navy-850/60 transition-colors">
                      <td className="px-4 py-3 font-semibold text-white whitespace-nowrap">
                        {item.city_or_location}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-base font-black text-white">{aq.aqi ?? "N/A"}</span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        {catMeta ? (
                          <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${catMeta.badgeColor}`}>
                            {catMeta.label}
                          </span>
                        ) : (
                          <span className="text-slate-500">N/A</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-medium text-slate-300 uppercase whitespace-nowrap">
                        {aq.dominant_pollutant || "—"}
                      </td>
                      <td className="px-4 py-3 font-mono text-slate-200 whitespace-nowrap">{pm25}</td>
                      <td className="px-4 py-3 font-mono text-slate-200 whitespace-nowrap">{pm10}</td>
                      <td className="px-4 py-3 font-mono text-slate-200 whitespace-nowrap">{no2}</td>
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                        {new Date(aq.observation_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="text-[10px] text-emerald-400 font-medium">{aq.data_freshness}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
