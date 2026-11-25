"use client";

import React from "react";
import { X, BookOpen, CheckCircle, Database, ShieldAlert, Cpu } from "lucide-react";

interface MethodologyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function MethodologyModal({ isOpen, onClose }: MethodologyModalProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm animate-fadeIn">
      <div className="bg-navy-900 border border-navy-700 rounded-3xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-6 shadow-2xl space-y-6 relative text-xs text-slate-300">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-navy-800">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-cyan-500/15 text-cyan-400 flex items-center justify-center">
              <BookOpen className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">CPCB NAQI Methodology & Provenance</h3>
              <p className="text-[11px] text-slate-400">
                Official Indian Air Quality Index Standards & Environmental Data Architecture
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-navy-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Section 1: Official Formula */}
        <div className="space-y-3">
          <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>1. Official CPCB Sub-Index Formula</span>
          </h4>
          <p className="leading-relaxed">
            India's Central Pollution Control Board (CPCB) calculates the National Air Quality Index (NAQI) using a linear interpolation formula across predefined concentration breakpoints:
          </p>

          <div className="bg-navy-950 p-4 rounded-2xl border border-navy-800 font-mono text-center text-cyan-300 text-sm">
            I_p = [ (I_hi - I_lo) / (B_hi - B_lo) ] * (C_p - B_lo) + I_lo
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
            <div className="p-2 rounded-xl bg-navy-850 border border-navy-800">
              <strong className="text-white block">C_p</strong>
              <span>Measured concentration</span>
            </div>
            <div className="p-2 rounded-xl bg-navy-850 border border-navy-800">
              <strong className="text-white block">B_hi / B_lo</strong>
              <span>Breakpoint bounds</span>
            </div>
            <div className="p-2 rounded-xl bg-navy-850 border border-navy-800">
              <strong className="text-white block">I_hi / I_lo</strong>
              <span>AQI category sub-index</span>
            </div>
            <div className="p-2 rounded-xl bg-navy-850 border border-navy-800">
              <strong className="text-white block">Overall AQI</strong>
              <span>max(I_p1, I_p2, ... I_pn)</span>
            </div>
          </div>
        </div>

        {/* Section 2: Sufficiency Condition */}
        <div className="space-y-2">
          <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
            <CheckCircle className="w-4 h-4 text-emerald-400" />
            <span>2. Data Sufficiency Criteria</span>
          </h4>
          <ul className="space-y-1.5 list-disc list-inside bg-navy-850/60 p-3.5 rounded-2xl border border-navy-800 leading-relaxed">
            <li>
              <strong>Minimum 3 Pollutants Required:</strong> An official AQI cannot be calculated with fewer than 3 monitored criteria pollutants.
            </li>
            <li>
              <strong>Mandatory Particulate Matter:</strong> At least one of PM10 or PM2.5 MUST be monitored. A set consisting purely of gaseous pollutants (e.g. NO2, SO2, CO) is classified as <em>INSUFFICIENT_DATA</em>.
            </li>
            <li>
              <strong>Dominant Pollutant:</strong> The pollutant yielding the maximum sub-index is designated as the dominant air pollutant driving the composite index.
            </li>
          </ul>
        </div>

        {/* Section 3: CPCB Breakpoint Table */}
        <div className="space-y-2">
          <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
            <BookOpen className="w-4 h-4 text-amber-400" />
            <span>3. Official CPCB Breakpoints Table</span>
          </h4>

          <div className="overflow-x-auto rounded-xl border border-navy-800">
            <table className="w-full text-left text-[11px]">
              <thead className="bg-navy-950 text-slate-400 uppercase text-[9px] border-b border-navy-800">
                <tr>
                  <th className="px-3 py-2">Category</th>
                  <th className="px-3 py-2">AQI</th>
                  <th className="px-3 py-2">PM10 (24h)</th>
                  <th className="px-3 py-2">PM2.5 (24h)</th>
                  <th className="px-3 py-2">NO2 (24h)</th>
                  <th className="px-3 py-2">O3 (8h)</th>
                  <th className="px-3 py-2">CO (8h, mg/m³)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800/60 font-mono">
                <tr>
                  <td className="px-3 py-2 font-bold text-emerald-400">Good</td>
                  <td className="px-3 py-2">0 – 50</td>
                  <td className="px-3 py-2">0 – 50</td>
                  <td className="px-3 py-2">0 – 30</td>
                  <td className="px-3 py-2">0 – 40</td>
                  <td className="px-3 py-2">0 – 50</td>
                  <td className="px-3 py-2">0.0 – 1.0</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-bold text-lime-400">Satisfactory</td>
                  <td className="px-3 py-2">51 – 100</td>
                  <td className="px-3 py-2">51 – 100</td>
                  <td className="px-3 py-2">31 – 60</td>
                  <td className="px-3 py-2">41 – 80</td>
                  <td className="px-3 py-2">51 – 100</td>
                  <td className="px-3 py-2">1.1 – 2.0</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-bold text-amber-400">Moderate</td>
                  <td className="px-3 py-2">101 – 200</td>
                  <td className="px-3 py-2">101 – 250</td>
                  <td className="px-3 py-2">61 – 90</td>
                  <td className="px-3 py-2">81 – 180</td>
                  <td className="px-3 py-2">101 – 168</td>
                  <td className="px-3 py-2">2.1 – 10.0</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-bold text-orange-400">Poor</td>
                  <td className="px-3 py-2">201 – 300</td>
                  <td className="px-3 py-2">251 – 350</td>
                  <td className="px-3 py-2">91 – 120</td>
                  <td className="px-3 py-2">181 – 280</td>
                  <td className="px-3 py-2">169 – 208</td>
                  <td className="px-3 py-2">10.1 – 17.0</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-bold text-rose-400">Very Poor</td>
                  <td className="px-3 py-2">301 – 400</td>
                  <td className="px-3 py-2">351 – 430</td>
                  <td className="px-3 py-2">121 – 250</td>
                  <td className="px-3 py-2">281 – 400</td>
                  <td className="px-3 py-2">209 – 748</td>
                  <td className="px-3 py-2">17.1 – 34.0</td>
                </tr>
                <tr>
                  <td className="px-3 py-2 font-bold text-red-300">Severe</td>
                  <td className="px-3 py-2">401 – 500</td>
                  <td className="px-3 py-2">431+</td>
                  <td className="px-3 py-2">251+</td>
                  <td className="px-3 py-2">401+</td>
                  <td className="px-3 py-2">749+</td>
                  <td className="px-3 py-2">34.1+</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        {/* Section 4: Data Provenance */}
        <div className="space-y-2">
          <h4 className="text-sm font-bold text-white flex items-center gap-1.5">
            <Database className="w-4 h-4 text-cyan-400" />
            <span>4. Data Sources & Provenance</span>
          </h4>
          <p className="leading-relaxed">
            AirAware AI connects to <strong>Open-Meteo Air Quality API</strong> powered by the <strong>Copernicus Atmosphere Monitoring Service (CAMS Global)</strong> atmospheric model. Measurements are retrieved in standard units (µg/m³ for PM and gases, mg/m³ for CO) and evaluated via rolling-window integration. Values represent an <strong>INDICATIVE_MODEL_INDEX</strong> and are <em>not</em> official CPCB physical monitoring station (CAAQMS) readings.
          </p>
        </div>

        {/* Section 5: Public Health Disclaimer */}
        <div className="p-3.5 rounded-2xl bg-navy-950 border border-navy-800 text-slate-400 space-y-1">
          <span className="font-bold text-slate-300 block">Health Advisory Notice</span>
          <p className="text-[11px] leading-relaxed">
            Recommendations generated by AirAware AI are derived from public health guidelines issued by the CPCB and World Health Organization (WHO). This software does not provide medical diagnoses or replace consultations with certified healthcare professionals.
          </p>
        </div>

        <div className="pt-2 border-t border-navy-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-xs transition-colors"
          >
            Understood
          </button>
        </div>
      </div>
    </div>
  );
}
