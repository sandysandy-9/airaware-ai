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
  ChevronDown,
} from "lucide-react";
import { POPULAR_CITIES } from "../lib/constants";

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  selectedCity: string;
  setSelectedCity: (cityId: string) => void;
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
  onOpenAlerts,
  onOpenMethodology,
  alertCount,
  dataFreshness,
}: NavbarProps) {
  return (
    <header className="sticky top-0 z-40 bg-navy-950/85 backdrop-blur-md border-b border-navy-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Platform Title */}
          <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab("dashboard")}>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-emerald-400 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Wind className="w-5 h-5 text-navy-950" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">AirAware</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30">
                  AI
                </span>
              </div>
              <p className="text-[10px] text-slate-400 hidden sm:block">CPCB NAQI Urban Intelligence Platform</p>
            </div>
          </div>

          {/* Center: City Quick Switcher */}
          <div className="flex items-center space-x-2 bg-navy-900/90 border border-navy-700/60 rounded-xl px-3 py-1.5">
            <MapPin className="w-4 h-4 text-cyan-400" />
            <select
              value={selectedCity}
              onChange={(e) => setSelectedCity(e.target.value)}
              className="bg-transparent text-sm text-slate-200 font-medium focus:outline-none cursor-pointer pr-1"
            >
              {POPULAR_CITIES.map((c) => (
                <option key={c.id} value={c.id} className="bg-navy-900 text-white">
                  {c.name}, {c.state}
                </option>
              ))}
            </select>
            {dataFreshness && (
              <span className="hidden md:inline-flex items-center text-[11px] px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse mr-1.5" />
                {dataFreshness}
              </span>
            )}
          </div>

          {/* Navigation Links */}
          <nav className="hidden lg:flex items-center space-x-1">
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
          <div className="flex items-center space-x-2">
            <button
              onClick={onOpenMethodology}
              className="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-navy-800/80 transition-colors border border-navy-700/50"
              title="CPCB Methodology & Data Provenance"
            >
              <BookOpen className="w-4 h-4" />
            </button>
            <button
              onClick={onOpenAlerts}
              className="relative p-2 rounded-xl text-slate-300 hover:text-white hover:bg-navy-800/80 transition-colors border border-navy-700/50"
              title="Threshold Alerts & History"
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
