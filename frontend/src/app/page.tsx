"use client";

import React, { useState, useEffect } from "react";
import {
  Wind,
  AlertTriangle,
  RefreshCw,
  Search,
  CheckCircle,
  X,
  ShieldAlert,
  Sliders,
  Activity,
  Layers,
  History,
  Bot,
} from "lucide-react";
import { Navbar } from "../components/Navbar";
import { AQIGauge } from "../components/AQIGauge";
import { PollutantGrid } from "../components/PollutantGrid";
import { RecommendationStudio } from "../components/RecommendationStudio";
import { LocationComparison } from "../components/LocationComparison";
import { HistoricalCharts } from "../components/HistoricalCharts";
import { AIChatDrawer } from "../components/AIChatDrawer";
import { AlertsManager } from "../components/AlertsManager";
import { MethodologyModal } from "../components/MethodologyModal";
import { useAlerts } from "../hooks/useAlerts";
import { fetchCurrentAirQuality } from "../lib/api";
import { AirQualityCurrentResponse } from "../lib/types";
import { POPULAR_CITIES } from "../lib/constants";

export default function Home() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedCityId, setSelectedCityId] = useState("delhi");
  const [searchQuery, setSearchQuery] = useState("");
  const [airQuality, setAirQuality] = useState<AirQualityCurrentResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modals state
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [methodologyOpen, setMethodologyOpen] = useState(false);

  // Alerts Hook
  const {
    rules,
    history,
    activeBanner,
    addRule,
    toggleRule,
    deleteRule,
    checkThreshold,
    dismissBanner,
    clearHistory,
  } = useAlerts();

  const loadData = async (cityName: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCurrentAirQuality({ city: cityName });
      setAirQuality(data);
      checkThreshold(data);
    } catch (err: any) {
      setError(err.message || "Failed to load air quality measurements.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const cityObj = POPULAR_CITIES.find((c) => c.id === selectedCityId) || POPULAR_CITIES[0];
    loadData(cityObj.name);
  }, [selectedCityId]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    loadData(searchQuery.trim());
  };

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col">
      {/* Top Navigation */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        selectedCity={selectedCityId}
        setSelectedCity={setSelectedCityId}
        onOpenAlerts={() => setAlertsOpen(true)}
        onOpenMethodology={() => setMethodologyOpen(true)}
        alertCount={history.length}
        dataFreshness={airQuality?.data_freshness}
      />

      {/* Threshold Alert Banner */}
      {activeBanner && (
        <div className="bg-red-500/20 border-b border-red-500/30 px-4 py-2.5 text-xs text-red-200 flex items-center justify-between">
          <div className="max-w-7xl mx-auto w-full flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />
            <span className="font-semibold">{activeBanner.message}</span>
          </div>
          <button
            onClick={dismissBanner}
            className="p-1 rounded-lg hover:bg-red-500/30 text-red-300 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Main Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        {/* Search & Location Bar */}
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-96">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search Indian city or station..."
              className="w-full bg-navy-900 border border-navy-800 focus:border-cyan-500 rounded-2xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none transition-colors"
            />
          </form>

          {/* Tab quick pills for mobile / small screen */}
          <div className="flex lg:hidden overflow-x-auto w-full gap-2 py-1 no-scrollbar">
            {[
              { id: "dashboard", label: "Dashboard" },
              { id: "recommendations", label: "Actions" },
              { id: "comparison", label: "Compare" },
              { id: "historical", label: "History" },
              { id: "ai-assistant", label: "AI Chat" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-3 py-1 rounded-xl text-xs font-semibold whitespace-nowrap transition-colors border ${
                  activeTab === tab.id
                    ? "bg-cyan-500 text-slate-950 border-cyan-400"
                    : "bg-navy-900 text-slate-300 border-navy-800"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Global Error Banner if API fails */}
        {error && (
          <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => {
                const c = POPULAR_CITIES.find((x) => x.id === selectedCityId) || POPULAR_CITIES[0];
                loadData(c.name);
              }}
              className="px-3 py-1 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-xs font-bold text-amber-200"
            >
              Retry
            </button>
          </div>
        )}

        {/* Dynamic Tab Content */}
        {loading && !airQuality ? (
          <div className="h-96 flex flex-col items-center justify-center space-y-3">
            <RefreshCw className="w-8 h-8 text-cyan-400 animate-spin" />
            <span className="text-sm text-slate-400">Loading verified environmental measurements...</span>
          </div>
        ) : airQuality ? (
          <div className="space-y-6">
            {/* TAB 1: DASHBOARD */}
            {activeTab === "dashboard" && (
              <div className="space-y-6 animate-fadeIn">
                <AQIGauge data={airQuality} />
                <PollutantGrid pollutants={airQuality.pollutants} />
                <RecommendationStudio currentAirQuality={airQuality} />
              </div>
            )}

            {/* TAB 2: ACTION STUDIO */}
            {activeTab === "recommendations" && (
              <div className="animate-fadeIn">
                <RecommendationStudio currentAirQuality={airQuality} />
              </div>
            )}

            {/* TAB 3: LOCATION COMPARISON */}
            {activeTab === "comparison" && (
              <div className="animate-fadeIn">
                <LocationComparison />
              </div>
            )}

            {/* TAB 4: HISTORICAL TRENDS */}
            {activeTab === "historical" && (
              <div className="animate-fadeIn">
                <HistoricalCharts city={airQuality.location.name} />
              </div>
            )}

            {/* TAB 5: AI CONVERSATIONAL ASSISTANT */}
            {activeTab === "ai-assistant" && (
              <div className="animate-fadeIn">
                <AIChatDrawer currentAirQuality={airQuality} />
              </div>
            )}
          </div>
        ) : null}
      </main>

      {/* Footer */}
      <footer className="border-t border-navy-800 bg-navy-950/80 py-6 mt-12 text-center text-xs text-slate-400 space-y-2">
        <div className="flex flex-wrap items-center justify-center gap-4 text-[11px]">
          <span>AirAware AI v1.0.0</span>
          <span>•</span>
          <span>Official CPCB India NAQI Standard</span>
          <span>•</span>
          <span>Copernicus Atmosphere Monitoring Service (CAMS)</span>
          <span>•</span>
          <button onClick={() => setMethodologyOpen(true)} className="text-cyan-400 hover:underline">
            Methodology & Provenance
          </button>
        </div>
        <p className="text-[10px] text-slate-400">
          Built for the Urban Air Quality Intelligence Challenge. All readings reflect verified environmental observations.
        </p>
      </footer>

      {/* Threshold Alerts Modal */}
      <AlertsManager
        isOpen={alertsOpen}
        onClose={() => setAlertsOpen(false)}
        rules={rules}
        history={history}
        onAddRule={addRule}
        onToggleRule={toggleRule}
        onDeleteRule={deleteRule}
        onClearHistory={clearHistory}
      />

      {/* CPCB Methodology & Data Transparency Modal */}
      <MethodologyModal
        isOpen={methodologyOpen}
        onClose={() => setMethodologyOpen(false)}
      />
    </div>
  );
}
