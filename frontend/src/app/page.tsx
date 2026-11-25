"use client";

import React, { useState, useEffect } from "react";
import {
  AlertTriangle,
  RefreshCw,
  Search,
  X,
  ShieldAlert,
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
import { fetchCities, fetchCurrentAirQuality } from "../lib/api";
import { AirQualityPipelineResponse, CityInfo } from "../lib/types";
import { POPULAR_CITIES } from "../lib/constants";

function formatFreshnessLabel(status?: string): string | undefined {
  if (!status) return undefined;
  switch (status) {
    case "CURRENT_CYCLE":
      return "Current Cycle";
    case "AGING_CYCLE":
      return "Aging Cycle";
    case "STALE_CYCLE":
      return "Stale Cycle";
    case "UNKNOWN_RUN_AGE":
      return "Model Cycle";
    default:
      return status.replace(/_/g, " ");
  }
}

export default function Home() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [selectedCityId, setSelectedCityId] = useState("delhi");
  const [cities, setCities] = useState<CityInfo[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [airQuality, setAirQuality] = useState<AirQualityPipelineResponse | null>(null);
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

  useEffect(() => {
    fetchCities()
      .then((list) => {
        if (Array.isArray(list) && list.length > 0) {
          setCities(list);
        }
      })
      .catch(() => {
        // Fallback to POPULAR_CITIES in Navbar if /cities is unreachable
      });
  }, []);

  const loadData = async (cityName: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCurrentAirQuality({ city: cityName });
      setAirQuality(data);
      checkThreshold(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load air quality estimates.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const backendCity = cities.find((c) => c.id === selectedCityId);
    const fallbackCity = POPULAR_CITIES.find((c) => c.id === selectedCityId) || POPULAR_CITIES[0];
    loadData(backendCity ? backendCity.name : fallbackCity.name);
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
        cities={cities}
        onOpenAlerts={() => setAlertsOpen(true)}
        onOpenMethodology={() => setMethodologyOpen(true)}
        alertCount={history.length}
        dataFreshness={formatFreshnessLabel(airQuality?.freshness?.status)}
      />

      {/* Threshold Alert Banner */}
      {activeBanner && (
        <div
          role="alert"
          className="bg-red-500/20 border-b border-red-500/30 px-4 py-2.5 text-xs text-red-200 flex items-center justify-between"
        >
          <div className="max-w-7xl mx-auto w-full flex items-center space-x-2">
            <ShieldAlert className="w-4 h-4 text-red-400 shrink-0" />
            <span className="font-semibold">{activeBanner.message}</span>
          </div>
          <button
            onClick={dismissBanner}
            aria-label="Dismiss alert banner"
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
          <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-96 flex gap-2">
            <div className="relative flex-1">
              <Search className="w-4 h-4 absolute left-3.5 top-2.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search supported Indian city (e.g. Delhi, Pune)..."
                aria-label="Search city"
                className="w-full bg-navy-900 border border-navy-800 focus:border-cyan-500 rounded-2xl pl-10 pr-4 py-2 text-xs text-white placeholder-slate-500 focus:outline-none transition-colors"
              />
            </div>
            <button
              type="submit"
              className="px-4 py-2 rounded-2xl bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/30 text-xs font-semibold transition-colors"
            >
              Go
            </button>
          </form>

          {/* Tab quick pills for mobile / small screen */}
          <nav aria-label="Mobile sections" className="flex lg:hidden overflow-x-auto w-full gap-2 py-1 no-scrollbar">
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
          </nav>
        </div>

        {/* Global Error Banner if API fails */}
        {error && (
          <div
            role="alert"
            className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between"
          >
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
            <span className="text-sm text-slate-400">
              Loading model-derived air quality estimates...
            </span>
          </div>
        ) : airQuality ? (
          <div className="space-y-6">
            {/* Warnings from backend */}
            {airQuality.warnings.length > 0 && (
              <div className="p-3 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-xs text-amber-300 space-y-1">
                {airQuality.warnings.map((w, i) => (
                  <p key={i} className="flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 text-amber-400" />
                    <span>{w}</span>
                  </p>
                ))}
              </div>
            )}

            {/* TAB 1: DASHBOARD */}
            {activeTab === "dashboard" && (
              <div className="space-y-6 animate-fadeIn">
                <AQIGauge data={airQuality} />
                <PollutantGrid
                  pollutants={airQuality.pollutants}
                  unavailablePollutants={airQuality.unavailable_pollutants}
                />
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
      <footer className="border-t border-navy-800 bg-navy-950/80 py-6 mt-12 text-center text-xs text-slate-400 space-y-2 px-4">
        <div className="flex flex-wrap items-center justify-center gap-4 text-[11px]">
          <span>AirAware AI</span>
          <span>•</span>
          <span>Indicative CPCB NAQI Breakpoints</span>
          <span>•</span>
          <span>Copernicus Atmosphere Monitoring Service (CAMS Global)</span>
          <span>•</span>
          <button onClick={() => setMethodologyOpen(true)} className="text-cyan-400 hover:underline">
            Methodology &amp; Provenance
          </button>
        </div>
        <p className="text-[10px] text-slate-400">
          All index values are INDICATIVE_MODEL_INDEX computed from Copernicus CAMS Global
          model-derived estimates, not official CPCB physical monitoring station (CAAQMS)
          observations.
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
