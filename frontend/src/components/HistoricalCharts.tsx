"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { RefreshCw, AlertCircle } from "lucide-react";
import { HistoricalTrendsResponse, HistoricalPoint } from "../lib/types";
import { fetchHistoricalTrends } from "../lib/api";

interface HistoricalChartsProps {
  city: string;
}

export function HistoricalCharts({ city }: HistoricalChartsProps) {
  const [pastDays, setPastDays] = useState<number>(7);
  const [activeMetric, setActiveMetric] = useState<string>("aqi");
  const [trends, setTrends] = useState<HistoricalTrendsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestSeqRef = useRef(0);

  const loadTrends = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    setLoading(true);
    setError(null);
    try {
      const res = await fetchHistoricalTrends({
        city,
        pastDays,
      });
      if (seq === requestSeqRef.current) {
        setTrends(res);
      }
    } catch (err: unknown) {
      if (seq === requestSeqRef.current) {
        const msg = err instanceof Error ? err.message : "Failed to load historical data";
        setError(msg);
      }
    } finally {
      if (seq === requestSeqRef.current) {
        setLoading(false);
      }
    }
  }, [city, pastDays]);

  useEffect(() => {
    loadTrends();
  }, [loadTrends]);

  const metricsConfig: Record<string, { label: string; unit: string; color: string }> = {
    aqi: { label: "Indicative Index", unit: "Index", color: "#f97316" },
    pm25: { label: "PM2.5", unit: "µg/m³", color: "#ef4444" },
    pm10: { label: "PM10", unit: "µg/m³", color: "#eab308" },
    no2: { label: "NO2", unit: "µg/m³", color: "#38bdf8" },
    so2: { label: "SO2", unit: "µg/m³", color: "#a855f7" },
    co: { label: "CO", unit: "mg/m³", color: "#10b981" },
    o3: { label: "O3", unit: "µg/m³", color: "#06b6d4" },
  };

  const currentCfg = metricsConfig[activeMetric] || metricsConfig.aqi;

  // Chart data formatting
  const chartData = (trends?.data_points || []).map((pt) => {
    const d = new Date(pt.timestamp);
    const dateLabel = pastDays <= 2
      ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      : `${d.toLocaleDateString([], { month: "short", day: "numeric" })} ${d.getHours()}:00`;

    return {
      time: dateLabel,
      fullTime: d.toLocaleString("en-IN"),
      val: pt[activeMetric as keyof HistoricalPoint] as number | null,
      dominant: pt.dominant_pollutant,
    };
  });

  // Calculate statistics
  const validVals = chartData.map((d) => d.val).filter((v): v is number => v !== null && v !== undefined);
  const avg = validVals.length > 0 ? (validVals.reduce((a, b) => a + b, 0) / validVals.length).toFixed(1) : "—";
  const max = validVals.length > 0 ? Math.max(...validVals).toFixed(1) : "—";
  const min = validVals.length > 0 ? Math.min(...validVals).toFixed(1) : "—";

  return (
    <div className="bg-navy-900/90 border border-navy-800 rounded-3xl p-6 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-navy-800">
        <div>
          <h2 className="text-xl font-bold text-white tracking-tight">Historical Air Quality Trends</h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Model-derived hourly atmospheric estimates (Copernicus CAMS) for {trends?.location.name || city}
          </p>
        </div>

        {/* Range Selector */}
        <div
          role="group"
          aria-label="Historical time window"
          className="flex items-center space-x-1.5 bg-navy-850 p-1 rounded-xl border border-navy-700/60 self-start sm:self-auto"
        >
          {[
            { days: 1, label: "24h" },
            { days: 7, label: "7 Days" },
            { days: 14, label: "14 Days" },
            { days: 30, label: "30 Days" },
          ].map((item) => (
            <button
              key={item.days}
              type="button"
              aria-pressed={pastDays === item.days}
              onClick={() => setPastDays(item.days)}
              className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all ${
                pastDays === item.days
                  ? "bg-cyan-500 text-slate-950 shadow-sm"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* Metric Switcher Tabs */}
      <div role="group" aria-label="Historical metric selector" className="flex flex-wrap gap-2">
        {Object.entries(metricsConfig).map(([key, cfg]) => (
          <button
            key={key}
            type="button"
            aria-pressed={activeMetric === key}
            onClick={() => setActiveMetric(key)}
            className={`px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border ${
              activeMetric === key
                ? "bg-navy-800 text-white border-cyan-500/50 shadow-sm"
                : "bg-navy-850/60 text-slate-300 hover:text-white border-navy-700/40"
            }`}
          >
            <span style={{ color: activeMetric === key ? cfg.color : undefined }}>●</span> {cfg.label}
          </button>
        ))}
      </div>

      {error && (
        <div
          role="alert"
          className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-center justify-between text-xs text-amber-300"
        >
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={loadTrends}
            className="px-2.5 py-1 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 font-semibold text-amber-200"
          >
            Retry
          </button>
        </div>
      )}

      {/* Statistics Bar */}
      <div className="grid grid-cols-3 gap-4">
        <div className="p-3.5 rounded-2xl bg-navy-850 border border-navy-700/60">
          <span className="text-[11px] text-slate-400 font-semibold block">Period Average</span>
          <span className="text-lg font-black text-white">{avg}</span>{" "}
          <span className="text-xs text-slate-400">{currentCfg.unit}</span>
        </div>
        <div className="p-3.5 rounded-2xl bg-navy-850 border border-navy-700/60">
          <span className="text-[11px] text-rose-400 font-semibold block">Peak Estimate</span>
          <span className="text-lg font-black text-rose-300">{max}</span>{" "}
          <span className="text-xs text-slate-400">{currentCfg.unit}</span>
        </div>
        <div className="p-3.5 rounded-2xl bg-navy-850 border border-navy-700/60">
          <span className="text-[11px] text-emerald-400 font-semibold block">Lowest Estimate</span>
          <span className="text-lg font-black text-emerald-300">{min}</span>{" "}
          <span className="text-xs text-slate-400">{currentCfg.unit}</span>
        </div>
      </div>

      {/* Chart Canvas */}
      {loading ? (
        <div className="h-64 flex flex-col items-center justify-center space-y-2">
          <RefreshCw className="w-6 h-6 text-cyan-400 animate-spin" />
          <span className="text-xs text-slate-400">Loading model-derived historical atmospheric estimates...</span>
        </div>
      ) : chartData.length > 0 ? (
        <div
          role="region"
          aria-label={`Historical ${currentCfg.label} chart for ${trends?.location.name || city} over the past ${pastDays === 1 ? "24 hours" : `${pastDays} days`}`}
          className="h-72 w-full pt-4"
        >
          <p className="sr-only">
            {`Displayed ${chartData.length} hourly model-derived ${currentCfg.label} (${currentCfg.unit}) estimates for ${trends?.location.name || city} from ${chartData[0].fullTime} to ${chartData[chartData.length - 1].fullTime}. Period average: ${avg} ${currentCfg.unit}; Peak: ${max} ${currentCfg.unit}; Lowest: ${min} ${currentCfg.unit}.`}
          </p>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="metricGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={currentCfg.color} stopOpacity={0.4} />
                  <stop offset="95%" stopColor={currentCfg.color} stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
              <XAxis
                dataKey="time"
                stroke="#94a3b8"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: "#334155" }}
              />
              <YAxis
                stroke="#94a3b8"
                fontSize={10}
                tickLine={false}
                axisLine={{ stroke: "#334155" }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const dataPoint = payload[0].payload;
                    return (
                      <div className="bg-navy-950 border border-navy-700 p-3 rounded-xl shadow-xl text-xs space-y-1">
                        <p className="text-slate-400 font-medium">{dataPoint.fullTime}</p>
                        <p className="text-white font-bold">
                          {currentCfg.label}:{" "}
                          <span style={{ color: currentCfg.color }}>
                            {dataPoint.val} {currentCfg.unit}
                          </span>
                        </p>
                        {dataPoint.dominant && (
                          <p className="text-[11px] text-slate-400 uppercase">
                            Dominant: {dataPoint.dominant}
                          </p>
                        )}
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area
                type="monotone"
                dataKey="val"
                stroke={currentCfg.color}
                strokeWidth={2.5}
                fillOpacity={1}
                fill="url(#metricGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="h-64 flex flex-col items-center justify-center text-xs text-slate-400">
          No historical model estimate points available for this period.
        </div>
      )}

      {/* Provenance Footer */}
      <div className="text-[11px] text-slate-400 flex flex-col sm:flex-row sm:items-center justify-between gap-1 pt-3 border-t border-navy-800">
        <span>Data Source: {trends?.data_source || "Open-Meteo Copernicus CAMS (Model-Derived)"}</span>
        <span className="italic">
          {trends?.note || "Indicative CAMS model estimates — not physical monitoring station observations"}
        </span>
      </div>
    </div>
  );
}
