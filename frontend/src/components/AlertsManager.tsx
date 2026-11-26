"use client";

import React, { useState } from "react";
import { X, Bell, Plus, Trash2 } from "lucide-react";
import { AlertRule, CityInfo, TriggeredAlert } from "../lib/types";
import { POPULAR_CITIES } from "../lib/constants";
import { ModalDialog } from "./ModalDialog";

interface AlertsManagerProps {
  isOpen: boolean;
  onClose: () => void;
  rules: AlertRule[];
  history: TriggeredAlert[];
  cities?: CityInfo[];
  onAddRule: (city: string, thresholdAqi: number) => void;
  onToggleRule: (id: string) => void;
  onDeleteRule: (id: string) => void;
  onClearHistory: () => void;
}

export function AlertsManager({
  isOpen,
  onClose,
  rules,
  history,
  cities,
  onAddRule,
  onToggleRule,
  onDeleteRule,
  onClearHistory,
}: AlertsManagerProps) {
  const [selectedCity, setSelectedCity] = useState("New Delhi");
  const [threshold, setThreshold] = useState(200);
  const [activeTab, setActiveTab] = useState<"rules" | "history">("rules");

  const cityOptions =
    cities && cities.length > 0
      ? cities.map((c) => ({ id: c.id, name: c.name }))
      : POPULAR_CITIES;

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    onAddRule(selectedCity, threshold);
  };

  return (
    <ModalDialog
      isOpen={isOpen}
      onClose={onClose}
      labelledBy="alerts-modal-title"
      containerClassName="space-y-5"
    >
      {/* Modal Header */}
      <div className="flex items-center justify-between pb-3 border-b border-navy-800">
        <div className="flex items-center space-x-2.5">
          <div className="w-8 h-8 rounded-xl bg-cyan-500/15 text-cyan-400 flex items-center justify-center">
            <Bell className="w-4 h-4" />
          </div>
          <div>
            <h3 id="alerts-modal-title" className="text-base font-bold text-white">
              Threshold Alert Manager
            </h3>
            <p className="text-[11px] text-slate-400">
              Configure indicative model index alerts (CAMS model-derived, not official station readings)
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close threshold alert manager"
          className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-navy-800 transition-colors"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      {/* Tab switch */}
      <div role="tablist" aria-label="Alert manager sections" className="flex rounded-xl bg-navy-950 p-1 border border-navy-800">
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "rules"}
          onClick={() => setActiveTab("rules")}
          className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "rules" ? "bg-navy-800 text-white shadow-sm" : "text-slate-400 hover:text-white"
          }`}
        >
          Alert Rules ({rules.length})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={activeTab === "history"}
          onClick={() => setActiveTab("history")}
          className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "history" ? "bg-navy-800 text-white shadow-sm" : "text-slate-400 hover:text-white"
          }`}
        >
          Triggered History ({history.length})
        </button>
      </div>

      {activeTab === "rules" ? (
        <div className="space-y-4">
          {/* Create New Rule Form */}
          <form onSubmit={handleAdd} className="bg-navy-850 p-4 rounded-2xl border border-navy-700/60 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400">Add Alert Rule</h4>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label htmlFor="alert-city-select" className="text-[10px] text-slate-400 block mb-1">
                  Target City
                </label>
                <select
                  id="alert-city-select"
                  value={selectedCity}
                  onChange={(e) => setSelectedCity(e.target.value)}
                  className="w-full bg-navy-900 border border-navy-700 text-xs text-white rounded-xl p-2 focus:outline-none"
                >
                  <option value="All Cities">All Monitored Cities</option>
                  {cityOptions.map((c) => (
                    <option key={c.id} value={c.name}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="alert-threshold-range" className="text-[10px] text-slate-400 block mb-1">
                  Indicative Index Threshold ({threshold})
                </label>
                <input
                  id="alert-threshold-range"
                  type="range"
                  min="50"
                  max="450"
                  step="10"
                  value={threshold}
                  onChange={(e) => setThreshold(Number(e.target.value))}
                  className="w-full h-2 bg-navy-950 rounded-lg appearance-none cursor-pointer accent-cyan-400 mt-2"
                />
              </div>
            </div>

            <button
              type="submit"
              className="w-full py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-colors flex items-center justify-center space-x-1.5"
            >
              <Plus className="w-3.5 h-3.5" />
              <span>Save Alert Rule</span>
            </button>
          </form>

          {/* Existing Rules List */}
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {rules.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-4">No alert rules configured.</p>
            ) : (
              rules.map((rule) => (
                <div
                  key={rule.id}
                  className="p-3 rounded-xl bg-navy-850 border border-navy-700/60 flex items-center justify-between text-xs"
                >
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-white">{rule.city}</span>
                      <span className="text-[11px] text-amber-400 font-semibold">
                        Indicative Index ≥ {rule.thresholdAqi}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-400">
                      {rule.enabled ? "Active monitoring" : "Paused"}
                    </span>
                  </div>

                  <div className="flex items-center space-x-2">
                    <button
                      type="button"
                      aria-pressed={rule.enabled}
                      onClick={() => onToggleRule(rule.id)}
                      className={`px-2 py-1 rounded-lg text-[10px] font-semibold border ${
                        rule.enabled
                          ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                          : "bg-slate-800 text-slate-300 border-slate-700"
                      }`}
                    >
                      {rule.enabled ? "Enabled" : "Disabled"}
                    </button>
                    <button
                      type="button"
                      aria-label={`Delete alert rule for ${rule.city}`}
                      onClick={() => onDeleteRule(rule.id)}
                      className="p-1 rounded-lg text-slate-400 hover:text-red-400 hover:bg-navy-800 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      ) : (
        /* Alert History View */
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Triggered Threshold Notifications</span>
            {history.length > 0 && (
              <button
                type="button"
                onClick={onClearHistory}
                className="text-xs text-rose-400 hover:text-rose-300 font-semibold"
              >
                Clear History
              </button>
            )}
          </div>

          <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {history.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">No alerts triggered yet.</p>
            ) : (
              history.map((h) => (
                <div
                  key={h.id}
                  className="p-3 rounded-xl bg-navy-850 border border-navy-700/60 space-y-1 text-xs"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white">{h.city}</span>
                    <span className="text-[10px] text-slate-400">
                      {new Date(h.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">{h.message}</p>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      <div className="pt-2 border-t border-navy-800 flex justify-end">
        <button
          type="button"
          onClick={onClose}
          className="px-4 py-2 rounded-xl bg-navy-800 hover:bg-navy-700 text-xs font-semibold text-white transition-colors"
        >
          Done
        </button>
      </div>
    </ModalDialog>
  );
}
