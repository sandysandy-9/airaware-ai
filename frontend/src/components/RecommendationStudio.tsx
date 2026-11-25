"use client";

import React, { useState, useEffect } from "react";
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Heart,
  Home,
  Flame,
  RefreshCw,
  Info,
  FileText,
} from "lucide-react";
import {
  ACTIVITY_OPTIONS,
  VULNERABILITY_OPTIONS,
  DURATION_OPTIONS,
} from "../lib/constants";
import {
  AirQualityPipelineResponse,
  RecommendationResponse,
  TriggeredRule,
} from "../lib/types";
import { fetchRecommendations } from "../lib/api";

export function TriggeredRulesPanel({ rules }: { rules: TriggeredRule[] }) {
  if (!rules || rules.length === 0) return null;
  return (
    <div className="bg-navy-850/80 border border-navy-700/60 rounded-2xl p-4 space-y-2.5">
      <h4 className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
        <FileText className="w-4 h-4 text-slate-400" />
        <span>Triggered Rules ({rules.length})</span>
      </h4>
      <ul className="space-y-2">
        {rules.map((rule, idx) => {
          const statusRaw = (rule.status || "").trim();
          const statusLabel = statusRaw ? statusRaw.replace(/_/g, " ") : "RECORDED";
          const statusTone =
            statusRaw === "BLOCKED"
              ? "bg-red-500/15 text-red-300 border-red-500/30"
              : statusRaw === "ISSUED_WITH_REDUCED_SPECIFICITY"
              ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
              : "bg-cyan-500/10 text-cyan-300 border-cyan-500/25";
          const scopeLabel = rule.scope ? rule.scope.replace(/_/g, " ") : null;

          return (
            <li
              key={rule.rule_id || idx}
              className="text-[11px] text-slate-300 bg-navy-900/50 border border-navy-800/80 rounded-xl px-3 py-2 space-y-1"
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-cyan-300 font-semibold">
                  {rule.rule_id || `RULE-${idx + 1}`}
                </span>
                <span
                  className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${statusTone}`}
                >
                  {statusLabel}
                </span>
                {scopeLabel && (
                  <span className="text-[10px] uppercase tracking-wider text-slate-400">
                    {scopeLabel}
                  </span>
                )}
              </div>
              <p className="text-slate-300 leading-relaxed">
                {rule.reason?.trim() || "Rule recorded without additional explanation."}
              </p>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface RecommendationStudioProps {
  currentAirQuality: AirQualityPipelineResponse;
  selectedActivity?: string;
  onActivityChange?: (activity: string) => void;
  selectedVulnerability?: string;
  onVulnerabilityChange?: (vulnerability: string) => void;
  selectedDuration?: string;
  onDurationChange?: (duration: string) => void;
}

export function RecommendationStudio({
  currentAirQuality,
  selectedActivity: controlledActivity,
  onActivityChange,
  selectedVulnerability: controlledVulnerability,
  onVulnerabilityChange,
  selectedDuration: controlledDuration,
  onDurationChange,
}: RecommendationStudioProps) {
  const [internalActivity, setInternalActivity] = useState("walking");
  const [internalVulnerability, setInternalVulnerability] = useState("general");
  const [internalDuration, setInternalDuration] = useState("30-60m");

  const selectedActivity = controlledActivity ?? internalActivity;
  const setSelectedActivity = onActivityChange ?? setInternalActivity;
  const selectedVulnerability = controlledVulnerability ?? internalVulnerability;
  const setSelectedVulnerability = onVulnerabilityChange ?? setInternalVulnerability;
  const selectedDuration = controlledDuration ?? internalDuration;
  const setSelectedDuration = onDurationChange ?? setInternalDuration;
  const [recommendations, setRecommendations] = useState<RecommendationResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadRecommendations = async () => {
    setLoading(true);
    setError(null);
    try {
      // NEVER send aqi, aqi_category, or dominant_pollutant — backend forbids them.
      const res = await fetchRecommendations({
        city: currentAirQuality.location.name,
        latitude: currentAirQuality.coordinates.requested_latitude,
        longitude: currentAirQuality.coordinates.requested_longitude,
        activity: selectedActivity,
        vulnerability_group: selectedVulnerability,
        duration: selectedDuration,
      });
      setRecommendations(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to calculate recommendations";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadRecommendations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedActivity, selectedVulnerability, selectedDuration, currentAirQuality.location.name]);

  const advisoryColorMap: Record<string, { bg: string; text: string; border: string }> = {
    LOW_RISK: { bg: "bg-emerald-500/15", text: "text-emerald-400", border: "border-emerald-500/30" },
    MODERATE_CAUTION: { bg: "bg-amber-500/15", text: "text-amber-400", border: "border-amber-500/30" },
    HIGH_RISK: { bg: "bg-orange-500/15", text: "text-orange-400", border: "border-orange-500/30" },
    VERY_HIGH_RISK: { bg: "bg-red-500/15", text: "text-red-400", border: "border-red-500/30" },
    EMERGENCY_AVOID: { bg: "bg-red-950/40", text: "text-red-300", border: "border-red-800/60" },
    UNAVAILABLE: { bg: "bg-slate-500/15", text: "text-slate-400", border: "border-slate-500/30" },
  };

  const currentAdvColor = recommendations
    ? advisoryColorMap[recommendations.advisory_level] || advisoryColorMap.MODERATE_CAUTION
    : advisoryColorMap.LOW_RISK;

  const aqiDisplay = currentAirQuality.indicative_index.value;

  return (
    <div className="bg-navy-900/90 border border-navy-800 rounded-3xl p-6 shadow-xl space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2">
            <h3 className="text-xl font-bold text-white tracking-tight">
              Personalised Action Studio
            </h3>
            <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
              Deterministic Rules Engine
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Evidence-based precautions for {currentAirQuality.location.name} (Indicative Index:{" "}
            {aqiDisplay ?? "N/A"})
          </p>
        </div>

        <button
          onClick={loadRecommendations}
          disabled={loading}
          className="self-start sm:self-auto px-3 py-1.5 rounded-xl bg-navy-800 hover:bg-navy-700 text-xs font-semibold text-slate-300 hover:text-white transition-colors flex items-center space-x-1.5"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Selectors */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <Flame className="w-3.5 h-3.5 text-cyan-400" />
            <span>1. Planned Activity</span>
          </label>
          <div className="grid grid-cols-2 gap-2">
            {ACTIVITY_OPTIONS.map((act) => (
              <button
                key={act.id}
                onClick={() => setSelectedActivity(act.id)}
                className={`p-2.5 rounded-xl text-left text-xs font-semibold transition-all border ${
                  selectedActivity === act.id
                    ? "bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-sm"
                    : "bg-navy-850 text-slate-400 hover:text-slate-200 border-navy-700/60 hover:border-navy-600"
                }`}
              >
                {act.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <Heart className="w-3.5 h-3.5 text-rose-400" />
            <span>2. Sensitivity Cohort</span>
          </label>
          <div className="space-y-1.5">
            {VULNERABILITY_OPTIONS.map((vuln) => (
              <button
                key={vuln.id}
                onClick={() => setSelectedVulnerability(vuln.id)}
                className={`w-full p-2 rounded-xl text-left transition-all border ${
                  selectedVulnerability === vuln.id
                    ? "bg-rose-500/15 text-rose-300 border-rose-500/40 shadow-sm"
                    : "bg-navy-850 text-slate-400 hover:text-slate-200 border-navy-700/60 hover:border-navy-600"
                }`}
              >
                <div className="text-xs font-semibold">{vuln.label}</div>
                <div className="text-[10px] text-slate-400 truncate">{vuln.desc}</div>
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-xs font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
            <Clock className="w-3.5 h-3.5 text-amber-400" />
            <span>3. Expected Duration</span>
          </label>
          <div className="space-y-2">
            {DURATION_OPTIONS.map((dur) => (
              <button
                key={dur.id}
                onClick={() => setSelectedDuration(dur.id)}
                className={`w-full p-2.5 rounded-xl text-left text-xs font-semibold transition-all border ${
                  selectedDuration === dur.id
                    ? "bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-sm"
                    : "bg-navy-850 text-slate-400 hover:text-slate-200 border-navy-700/60 hover:border-navy-600"
                }`}
              >
                {dur.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/25 flex items-center space-x-2 text-xs text-amber-300">
          <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Results */}
      {recommendations && (
        <div className="space-y-4 pt-4 border-t border-navy-800">
          {/* Advisory Banner */}
          <div
            className={`p-4 rounded-2xl border ${currentAdvColor.bg} ${currentAdvColor.border} flex items-start space-x-3`}
          >
            <ShieldAlert className={`w-5 h-5 ${currentAdvColor.text} shrink-0 mt-0.5`} />
            <div>
              <div className="flex items-center space-x-2">
                <span
                  className={`text-xs font-black uppercase tracking-wider ${currentAdvColor.text}`}
                >
                  {recommendations.advisory_level.replace(/_/g, " ")}
                </span>
                <span className="text-xs text-slate-400">•</span>
                <span className="text-xs text-slate-300 font-semibold">
                  {recommendations.headline}
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Precautions */}
            <div className="bg-navy-850/80 border border-navy-700/60 rounded-2xl p-4 space-y-3">
              <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Actionable Precautions</span>
              </h4>
              <ul className="space-y-2">
                {recommendations.actionable_precautions.map((p, idx) => (
                  <li
                    key={idx}
                    className="flex items-start space-x-2 text-xs text-slate-200 leading-relaxed"
                  >
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0 mt-1.5" />
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="space-y-4">
              {/* Mask */}
              <div className="bg-navy-850/80 border border-navy-700/60 rounded-2xl p-4 space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <span>Protective Mask Guidance</span>
                </h4>
                <p className="text-xs text-slate-200">
                  {recommendations.protective_gear ||
                    "No special mask required for healthy adults."}
                </p>
              </div>

              {/* Indoor */}
              <div className="bg-navy-850/80 border border-navy-700/60 rounded-2xl p-4 space-y-2">
                <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-400 flex items-center gap-1.5">
                  <Home className="w-4 h-4 text-emerald-400" />
                  <span>Indoor Environment Advisory</span>
                </h4>
                <p className="text-xs text-slate-200">{recommendations.indoor_guidance}</p>
              </div>
            </div>
          </div>

          {/* Triggered Rules */}
          <TriggeredRulesPanel rules={recommendations.triggered_rules} />

          {/* Uncertainty Notes */}
          {recommendations.uncertainty_notes.length > 0 && (
            <div className="p-3 rounded-xl bg-amber-500/5 border border-amber-500/15 text-[11px] text-amber-300/80 space-y-1">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400">
                <Info className="w-3.5 h-3.5" />
                <span>Uncertainty Notes</span>
              </div>
              {recommendations.uncertainty_notes.map((note, idx) => (
                <p key={idx}>{note}</p>
              ))}
            </div>
          )}

          {/* Disclaimer */}
          <div className="text-[11px] text-slate-400 p-3 rounded-xl bg-navy-950/60 border border-navy-800 leading-relaxed">
            <strong className="text-slate-300">Disclaimer:</strong> {recommendations.disclaimer}
          </div>
        </div>
      )}
    </div>
  );
}
