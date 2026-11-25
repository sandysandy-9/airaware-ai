"use client";

import React, { useState } from "react";
import {
  AlertTriangle,
  Info,
  Clock,
  Database,
  ChevronRight,
  ShieldAlert,
  Flame,
  MapPin,
} from "lucide-react";
import { AirQualityPipelineResponse } from "../lib/types";
import { AQI_CATEGORY_META } from "../lib/constants";
import { buildTemporalProvenanceItems } from "../lib/provenance";

interface AQIGaugeProps {
  data: AirQualityPipelineResponse;
}

export function AQIGauge({ data }: AQIGaugeProps) {
  const [showDriverDetails, setShowDriverDetails] = useState(false);

  const idx = data.indicative_index;
  const aqi = idx.value;
  const categoryKey = (idx.category || "GOOD") as keyof typeof AQI_CATEGORY_META;
  const meta = AQI_CATEGORY_META[categoryKey] || AQI_CATEGORY_META.GOOD;
  const dominantCode = idx.dominant_pollutant;
  const dominantDetail = dominantCode ? data.pollutants[dominantCode] : null;

  // Gauge arc (0–500 → 0–100%)
  const clampedAqi = aqi !== null ? Math.min(500, Math.max(0, aqi)) : 0;
  const progressPercent = (clampedAqi / 500) * 100;
  const strokeDashoffset = 251.3 - (251.3 * progressPercent) / 100;

  // Freshness label
  const freshnessLabel =
    data.freshness.status === "CURRENT_CYCLE"
      ? "Current Cycle"
      : data.freshness.status === "AGING_CYCLE"
      ? "Aging Cycle"
      : data.freshness.status === "STALE_CYCLE"
      ? "Stale Cycle"
      : "Unknown Run Age";

  const temporalItems = buildTemporalProvenanceItems(data.temporal_governance);

  return (
    <div className="bg-navy-900/90 border border-navy-800 rounded-3xl p-6 shadow-xl relative overflow-hidden">
      {/* Background ambient glow */}
      <div
        className="absolute top-0 right-0 w-80 h-80 rounded-full blur-3xl opacity-15 pointer-events-none -mr-20 -mt-20"
        style={{ backgroundColor: meta.color }}
      />

      {/* Provenance disclosure banner */}
      <div className="mb-4 p-2.5 rounded-xl bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-300/80 flex items-start gap-2">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber-400/70" />
        <span>
          <strong>Indicative Model Index</strong> — computed from Copernicus CAMS atmospheric model
          estimates using CPCB NAQI breakpoints. This is <em>not</em> an official CPCB continuous
          monitoring station (CAAQMS) AQI reading.
        </span>
      </div>

      <div className="flex flex-col lg:flex-row items-center justify-between gap-8">
        {/* Left: Semi-Circular Gauge */}
        <div className="flex flex-col items-center justify-center relative w-64 h-48 sm:w-72 sm:h-52">
          <svg className="w-full h-full transform" viewBox="0 0 200 130">
            <path
              d="M 20 110 A 80 80 0 0 1 180 110"
              fill="none"
              stroke="#1e293b"
              strokeWidth="16"
              strokeLinecap="round"
            />
            {aqi !== null && (
              <path
                d="M 20 110 A 80 80 0 0 1 180 110"
                fill="none"
                stroke={meta.color}
                strokeWidth="16"
                strokeLinecap="round"
                strokeDasharray="251.3"
                strokeDashoffset={strokeDashoffset}
                className="transition-all duration-1000 ease-out"
              />
            )}
          </svg>

          <div className="absolute top-16 flex flex-col items-center justify-center text-center">
            {aqi !== null ? (
              <>
                <span className="text-5xl sm:text-6xl font-black tracking-tight text-white">
                  {aqi}
                </span>
                <span className="text-xs uppercase tracking-widest font-bold text-slate-400 mt-1">
                  Indicative Index
                </span>
              </>
            ) : (
              <div className="flex flex-col items-center">
                <AlertTriangle className="w-8 h-8 text-amber-400 mb-1" />
                <span className="text-sm font-semibold text-amber-300">Insufficient Data</span>
              </div>
            )}
          </div>

          <div className="w-full flex justify-between px-4 text-[11px] font-semibold text-slate-500 -mt-3">
            <span>0 (Good)</span>
            <span>200</span>
            <span>500 (Severe)</span>
          </div>
        </div>

        {/* Right: Status & Health Interpretation */}
        <div className="flex-1 space-y-4 w-full">
          {/* Location & Category */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
                <MapPin className="w-5 h-5 text-cyan-400" />
                {data.location.name}
              </h2>
              <p className="text-xs text-slate-400">
                {data.location.city}, {data.location.state || "India"} •{" "}
                <span className="font-mono text-slate-400">
                  {data.coordinates.returned_latitude?.toFixed(3) ??
                    data.coordinates.requested_latitude.toFixed(3)}
                  °N,{" "}
                  {data.coordinates.returned_longitude?.toFixed(3) ??
                    data.coordinates.requested_longitude.toFixed(3)}
                  °E
                </span>
                {data.coordinates.geodesic_snap_distance_km != null && (
                  <span className="text-slate-500">
                    {" "}
                    (grid snap: {data.coordinates.geodesic_snap_distance_km.toFixed(1)} km)
                  </span>
                )}
              </p>
            </div>

            <div
              className={`px-4 py-1.5 rounded-full text-xs font-bold uppercase tracking-wider ${meta.badgeColor} shadow-md`}
            >
              {meta.label}
            </div>
          </div>

          {/* Health Impact */}
          <div className={`p-4 rounded-2xl border ${meta.bgColor} ${meta.borderColor}`}>
            <p className="text-sm text-slate-200 font-medium leading-relaxed">
              {meta.description}
            </p>
          </div>

          {/* Dominant Pollutant */}
          {dominantDetail && dominantDetail.status === "SUFFICIENT" && (
            <div className="bg-navy-850/80 border border-navy-700/60 rounded-2xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
              <div className="flex items-center space-x-3">
                <div className="w-10 h-10 rounded-xl bg-orange-500/15 border border-orange-500/30 flex items-center justify-center text-orange-400 shrink-0">
                  <Flame className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <span className="text-xs text-slate-400">Primary Index Driver:</span>
                    <span className="text-sm font-bold text-white">
                      {dominantDetail.name}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    Concentration:{" "}
                    <span className="font-semibold text-white">
                      {dominantDetail.concentration != null
                        ? dominantDetail.concentration.toFixed(1)
                        : "—"}{" "}
                      {dominantDetail.unit}
                    </span>{" "}
                    (Sub-Index:{" "}
                    <span className="font-semibold text-orange-400">
                      {dominantDetail.sub_index ?? "—"}
                    </span>
                    )
                  </p>
                </div>
              </div>

              <button
                onClick={() => setShowDriverDetails(!showDriverDetails)}
                className="text-xs font-medium text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 shrink-0"
              >
                <span>{showDriverDetails ? "Hide details" : "Why it matters"}</span>
                <ChevronRight
                  className={`w-3.5 h-3.5 transform transition-transform ${
                    showDriverDetails ? "rotate-90" : ""
                  }`}
                />
              </button>
            </div>
          )}

          {/* Expandable details */}
          {showDriverDetails && dominantDetail && (
            <div className="bg-navy-950/70 border border-navy-700/50 rounded-2xl p-4 text-xs text-slate-300 space-y-2 animate-fadeIn">
              <div>
                <strong className="text-white">Health Impact:</strong> {dominantDetail.health_effects}
              </div>
              <div>
                <strong className="text-white">Typical Sources:</strong> {dominantDetail.sources}
              </div>
              <p className="text-[11px] text-slate-400 italic">
                Under CPCB NAQI methodology, the highest individual sub-index dictates the composite
                index value.
              </p>
            </div>
          )}

          {/* Provenance & Timestamps Footer */}
          <div className="pt-2.5 border-t border-navy-800 text-[11px] text-slate-400 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center space-x-1.5">
                <Database className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                <span>
                  {data.provider.provider_name} ({data.provider.domain_requested})
                </span>
              </div>
              <div className="flex items-center space-x-1.5">
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    data.freshness.status === "CURRENT_CYCLE"
                      ? "bg-emerald-400 animate-pulse"
                      : data.freshness.status === "AGING_CYCLE"
                      ? "bg-amber-400"
                      : "bg-red-400"
                  }`}
                />
                <span>{freshnessLabel}</span>
                {data.freshness.cache_hit && (
                  <span className="text-slate-500">(cached)</span>
                )}
              </div>
            </div>

            {temporalItems.length > 0 && (
              <div
                aria-label="Model temporal provenance"
                className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[11px] text-slate-400"
              >
                {temporalItems.map((item) => (
                  <div key={item.id} className="flex items-center gap-1.5">
                    {item.id === "valid_time" && (
                      <Clock className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                    )}
                    <span className="text-slate-500">{item.label}:</span>
                    <span className="font-mono text-slate-300">{item.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
