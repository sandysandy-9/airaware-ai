"use client";

import React, { useState } from "react";
import { Info, AlertCircle, X } from "lucide-react";
import { PollutantRollingDetail } from "../lib/types";
import { AQI_CATEGORY_META } from "../lib/constants";

interface PollutantGridProps {
  pollutants: Record<string, PollutantRollingDetail>;
  unavailablePollutants?: string[];
}

export function PollutantGrid({ pollutants, unavailablePollutants = [] }: PollutantGridProps) {
  const [selectedPollutant, setSelectedPollutant] = useState<PollutantRollingDetail | null>(null);

  const displayList = ["pm25", "pm10", "no2", "so2", "co", "o3", "nh3"];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-white tracking-tight">Criteria Pollutants Breakdown</h3>
          <p className="text-xs text-slate-400">
            Model-derived concentrations &amp; indicative CPCB sub-indices from CAMS atmospheric data
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {displayList.map((code) => {
          const item = pollutants[code];
          if (!item) {
            if (!unavailablePollutants.includes(code)) return null;
            return (
              <div
                key={code}
                className="bg-navy-900/80 border border-navy-800 rounded-2xl p-5 opacity-60"
              >
                <span className="text-xs uppercase font-bold text-slate-500 tracking-wider">
                  {code.toUpperCase()}
                </span>
                <div className="mt-4 flex items-center space-x-1.5 text-slate-500 py-1">
                  <AlertCircle className="w-4 h-4 text-slate-500" />
                  <span className="text-xs font-medium">Not Available</span>
                </div>
              </div>
            );
          }

          const isMissing = item.status !== "SUFFICIENT" || item.concentration === null;
          const catMeta = item.category
            ? AQI_CATEGORY_META[item.category as keyof typeof AQI_CATEGORY_META]
            : null;

          return (
            <div
              key={code}
              onClick={() => setSelectedPollutant(item)}
              className="bg-navy-900/80 hover:bg-navy-850 border border-navy-800 hover:border-navy-700/80 rounded-2xl p-5 transition-all cursor-pointer shadow-lg group relative overflow-hidden"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs uppercase font-bold text-cyan-400 tracking-wider">
                    {item.code.toUpperCase()}
                  </span>
                  <h4 className="text-sm font-semibold text-white group-hover:text-cyan-300 transition-colors">
                    {item.name}
                  </h4>
                </div>
                <button
                  className="p-1 rounded-lg text-slate-400 group-hover:text-cyan-300 hover:bg-navy-800 transition-colors"
                  title="View pollutant details"
                >
                  <Info className="w-4 h-4" />
                </button>
              </div>

              <div className="mt-4 flex items-baseline justify-between">
                {isMissing ? (
                  <div className="flex items-center space-x-1.5 text-slate-500 py-1">
                    <AlertCircle className="w-4 h-4 text-slate-500" />
                    <span className="text-xs font-medium">
                      {item.status === "UNAVAILABLE"
                        ? item.unavailable_reason || "Unavailable"
                        : "Insufficient Data"}
                    </span>
                  </div>
                ) : (
                  <>
                    <div className="flex items-baseline space-x-1">
                      <span className="text-2xl font-black text-white">
                        {item.concentration != null ? item.concentration.toFixed(1) : "—"}
                      </span>
                      <span className="text-xs font-semibold text-slate-400">{item.unit}</span>
                    </div>

                    <div className="text-right">
                      <span className="text-xs text-slate-400 block">Sub-Index</span>
                      <span
                        className="text-sm font-bold"
                        style={{ color: item.color || "#94a3b8" }}
                      >
                        {item.sub_index} {item.category ? `(${item.category})` : ""}
                      </span>
                    </div>
                  </>
                )}
              </div>

              {/* Progress bar */}
              <div className="mt-3 w-full bg-navy-950 rounded-full h-1.5 overflow-hidden">
                {!isMissing && item.sub_index !== null ? (
                  <div
                    className="h-full rounded-full transition-all duration-700"
                    style={{
                      width: `${Math.min(100, (item.sub_index / 500) * 100)}%`,
                      backgroundColor: item.color || "#06b6d4",
                    }}
                  />
                ) : (
                  <div className="h-full w-full bg-slate-800/40" />
                )}
              </div>

              {/* Averaging period badge */}
              <div className="mt-2 text-[10px] text-slate-500">
                {item.averaging_period} rolling avg
              </div>
            </div>
          );
        })}
      </div>

      {/* Detail Modal */}
      {selectedPollutant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm animate-fadeIn">
          <div className="bg-navy-900 border border-navy-700 rounded-3xl max-w-lg w-full p-6 shadow-2xl relative space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-navy-800">
              <div className="flex items-center space-x-2">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-400 flex items-center justify-center font-bold text-xs uppercase">
                  {selectedPollutant.code}
                </div>
                <div>
                  <h3 className="text-base font-bold text-white">{selectedPollutant.name}</h3>
                  <span className="text-xs text-slate-400">
                    Unit: {selectedPollutant.unit} • {selectedPollutant.averaging_period} avg
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedPollutant(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-navy-800 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {selectedPollutant.status === "SUFFICIENT" && selectedPollutant.concentration !== null ? (
              <div className="p-4 rounded-2xl bg-navy-850 border border-navy-700/60 flex items-center justify-between">
                <div>
                  <span className="text-xs text-slate-400">Model-Derived Concentration</span>
                  <div className="text-xl font-bold text-white">
                    {selectedPollutant.concentration.toFixed(1)} {selectedPollutant.unit}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400">Indicative Sub-Index</span>
                  <div
                    className="text-xl font-bold"
                    style={{ color: selectedPollutant.color || "#38bdf8" }}
                  >
                    {selectedPollutant.sub_index} ({selectedPollutant.category})
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-300">
                This pollutant has {selectedPollutant.status === "UNAVAILABLE" ? "no available data feed" : "insufficient data"} for the required averaging period. Missing values are never assumed to be zero.
              </div>
            )}

            <div className="space-y-1.5">
              <h5 className="text-xs font-bold uppercase tracking-wider text-cyan-400">What It Means</h5>
              <p className="text-xs text-slate-300 leading-relaxed">{selectedPollutant.description}</p>
            </div>

            <div className="space-y-1.5">
              <h5 className="text-xs font-bold uppercase tracking-wider text-orange-400">Health Impacts</h5>
              <p className="text-xs text-slate-300 leading-relaxed">{selectedPollutant.health_effects}</p>
            </div>

            <div className="space-y-1.5">
              <h5 className="text-xs font-bold uppercase tracking-wider text-emerald-400">Typical Emission Sources</h5>
              <p className="text-xs text-slate-300 leading-relaxed">{selectedPollutant.sources}</p>
            </div>

            <div className="pt-2 border-t border-navy-800 flex justify-end">
              <button
                onClick={() => setSelectedPollutant(null)}
                className="px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-700 text-xs font-semibold text-white transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
