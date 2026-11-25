"use client";

import React from "react";
import {
  Wind,
  Bell,
  Activity,
  Layers,
  History,
  Bot,
  BookOpen,
  MapPin,
} from "lucide-react";
import { POPULAR_CITIES } from "../lib/constants";
import { CityInfo } from "../lib/types";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedCity: string;
  setSelectedCity: (cityId: string) => void;
  cities?: CityInfo[];
  onOpenAlerts: () => void;
  onOpenMethodology: () => void;
  alertCount: number;
  dataFreshness?: string;
}

export function Navbar({
  activeTab,
  setActiveTab,
  selectedCity,
  setSelectedCity,
  cities,
  onOpenAlerts,
  onOpenMethodology,
  alertCount,
  dataFreshness,
}: NavbarProps) {
  const cityOptions =
    cities && cities.length > 0
      ? cities.map((c) => ({ id: c.id, name: c.name, state: c.state }))
      : POPULAR_CITIES;

  return (
    <header className="sticky top-0 z-40 bg-navy-950/85 backdrop-blur-md border-b border-navy-800">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between gap-2 h-16">
          {/* Logo & Platform Title */}
          <button
            type="button"
            className="flex items-center space-x-2 sm:space-x-3 text-left focus:outline-none shrink-0"
            onClick={() => setActiveTab("dashboard")}
          >
            <div className="w-8 h-8 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-cyan-500/20 shrink-0">
              <Wind className="w-4 h-4 sm:w-5 sm:h-5 text-navy-950" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5 sm:space-x-2">
                <span className="font-bold text-base sm:text-lg tracking-tight text-white">AirAware</span>
                <span className="hidden sm:inline-block text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">
                  AI
                </span>
              </div>
              <p className="text-[10px] text-slate-400 hidden sm:block">
                Indicative Urban Air Intelligence
              </p>
            </div>
          </button>

          {/* Center: City Quick Switcher */}
          <div className="flex items-center space-x-1.5 sm:space-x-2 bg-navy-900/90 border border-navy-700/60 rounded-xl px-2 sm:px-3 py-1.5 min-w-0 max-w-[148px] sm:max-w-xs lg:max-w-sm">
            <MapPin className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-cyan-400 shrink-0" />
            <select
              value={selectedCity}
              onChange={(e) => setSelectedCity(e.target.value)}
              aria-label="Select city"
              className="w-full min-w-0 truncate bg-transparent text-xs sm:text-sm text-slate-200 font-medium focus:outline-none cursor-pointer pr-1"
            >
              {cityOptions.map((c) => (
                <option key={c.id} value={c.id} className="bg-navy-900 text-white">
                  {c.name}, {c.state}
                </option>
              ))}
            </select>
            {dataFreshness && (
              <span className="hidden md:inline-flex items-center text-[11px] px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse mr-1.5" />
                {dataFreshness}
              </span>
            )}
          </div>

          {/* Navigation Links */}
          <nav aria-label="Main navigation" className="hidden lg:flex items-center space-x-1">
            <button
              onClick={() => setActiveTab("dashboard")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 ${
                activeTab === "dashboard"
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-300 hover:text-white hover:bg-navy-800/60"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Dashboard</span>
            </button>
            <button
              onClick={() => setActiveTab("recommendations")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 ${
                activeTab === "recommendations"
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-300 hover:text-white hover:bg-navy-800/60"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Action Studio</span>
            </button>
            <button
              onClick={() => setActiveTab("comparison")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 ${
                activeTab === "comparison"
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-300 hover:text-white hover:bg-navy-800/60"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Comparison</span>
            </button>
            <button
              onClick={() => setActiveTab("historical")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 ${
                activeTab === "historical"
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-300 hover:text-white hover:bg-navy-800/60"
              }`}
            >
              <History className="w-3.5 h-3.5" />
              <span>Historical</span>
            </button>
            <button
              onClick={() => setActiveTab("ai-assistant")}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center space-x-1.5 ${
                activeTab === "ai-assistant"
                  ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/30"
                  : "text-slate-300 hover:text-white hover:bg-navy-800/60"
              }`}
            >
              <Bot className="w-3.5 h-3.5" />
              <span>AI Assistant</span>
            </button>
          </nav>

          {/* Action Icons */}
          <div className="flex items-center space-x-1.5 sm:space-x-2 shrink-0">
            <button
              onClick={onOpenMethodology}
              className="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-navy-800/80 transition-colors border border-navy-700/50"
              title="CPCB Methodology & Data Provenance"
              aria-label="Open CPCB Methodology and Data Provenance"
            >
              <BookOpen className="w-4 h-4" />
            </button>
            <button
              onClick={onOpenAlerts}
              className="relative p-2 rounded-xl text-slate-300 hover:text-white hover:bg-navy-800/80 transition-colors border border-navy-700/50"
              title="Threshold Alerts & History"
              aria-label="Open Threshold Alerts and History"
            >
              <Bell className="w-4 h-4" />
              {alertCount > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-[10px] font-bold text-white flex items-center justify-center animate-bounce">
                  {alertCount}
                </span>
              )}
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
