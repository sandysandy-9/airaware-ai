import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

const require = createRequire(import.meta.url);

// Transpile TSX/TS module in memory with custom require stubs (zero extra test dependencies)
function loadTsModule(relPath, customRequires = {}) {
  const fullPath = path.resolve(relPath);
  const src = fs.readFileSync(fullPath, "utf8");
  const { outputText } = ts.transpileModule(src, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2020,
      jsx: ts.JsxEmit.React,
      esModuleInterop: true,
    },
  });
  const mod = { exports: {} };
  const req = (id) => {
    if (id in customRequires) return customRequires[id];
    if (id === "react") return React;
    if (id === "lucide-react") {
      return new Proxy(
        {},
        {
          get: (_t, prop) => (props) =>
            React.createElement("svg", { "data-icon": String(prop), ...props }),
        }
      );
    }
    return require(id);
  };
  new Function("module", "exports", "require", "React", outputText)(
    mod,
    mod.exports,
    req,
    React
  );
  return mod.exports;
}

const constantsMod = loadTsModule("src/lib/constants.ts");
const provenanceMod = loadTsModule("src/lib/provenance.ts");
const comparisonMod = loadTsModule("src/lib/comparison.ts");

// ─── DEF-02: TriggeredRule rendering ──────────────────────────────────

test("DEF-02: TriggeredRulesPanel renders actual rule_id, status, scope, and reason without invented text", () => {
  const { TriggeredRulesPanel } = loadTsModule("src/components/RecommendationStudio.tsx", {
    "../lib/constants": constantsMod,
    "../lib/api": { fetchRecommendations: async () => ({}) },
  });

  const html = renderToStaticMarkup(
    React.createElement(TriggeredRulesPanel, {
      rules: [
        {
          rule_id: "RULE-CAT-POOR-HIGH_RISK",
          scope: "PRODUCT_ACTIVITY_RULE",
          status: "APPLIED",
          reason: "Product preventive guidance triggered for CPCB indicative category POOR.",
        },
        {
          rule_id: "RULE-EMPTY-FIELDS",
          scope: "",
          status: "",
          reason: "",
        },
      ],
    })
  );

  assert.match(html, /RULE-CAT-POOR-HIGH_RISK/);
  assert.match(html, /APPLIED/);
  assert.match(html, /PRODUCT ACTIVITY RULE/);
  assert.match(html, /Product preventive guidance triggered for CPCB indicative category POOR\./);
  // Missing/empty fields degrade gracefully without "→" or "undefined"
  assert.match(html, /RULE-EMPTY-FIELDS/);
  assert.match(html, /RECORDED/);
  assert.match(html, /Rule recorded without additional explanation\./);
  assert.doesNotMatch(html, /undefined/);
  assert.doesNotMatch(html, /→/);
});

// ─── DEF-04: AQIGauge temporal provenance & missing optional fields ───

test("DEF-04: AQIGauge displays available provenance fields and omits null optional values without inventing", () => {
  const { AQIGauge } = loadTsModule("src/components/AQIGauge.tsx", {
    "../lib/constants": constantsMod,
    "../lib/provenance": provenanceMod,
  });

  const baseData = {
    status: "SUCCESS",
    status_message: "OK",
    index_type: "INDICATIVE_MODEL_INDEX",
    is_official_cpcb_station_aqi: false,
    location: {
      name: "New Delhi",
      city: "New Delhi",
      state: "Delhi",
      latitude: 28.61,
      longitude: 77.21,
    },
    coordinates: {
      requested_latitude: 28.61,
      requested_longitude: 77.21,
      returned_latitude: 28.6,
      returned_longitude: 77.2,
      geodesic_snap_distance_km: 1.4,
      elevation_m: null,
      coordinate_role: "MODEL_GRID_ESTIMATE",
      is_physical_station: false,
    },
    provider: {
      provider_name: "Open-Meteo",
      domain_requested: "cams_global",
      model_name: "CAMS Global",
      metadata_verified: true,
      native_temporal_resolution: "1h",
      meta_temporal_resolution_seconds: 3600,
      api_output_frequency_seconds: 3600,
      update_interval_seconds: 43200,
      last_run_modification_time: null,
      last_run_availability_time: null,
      spatial_resolution_note: null,
      cache_hit: false,
    },
    indicative_index: {
      status: "AVAILABLE",
      index_type: "INDICATIVE_MODEL_INDEX",
      is_official_cpcb_station_aqi: false,
      value: 246,
      category: "POOR",
      color: "#F97316",
      dominant_pollutant: "pm25",
      dominant_pollutant_name: "Particulate Matter <= 2.5 um",
      eligible_pollutants: ["pm25", "pm10", "o3"],
      insufficient_or_unavailable_pollutants: ["nh3"],
      has_particulate_matter: true,
      eligibility_reason: "OK",
      methodology_note: "Indicative",
    },
    pollutants: {},
    unavailable_pollutants: ["nh3"],
    temporal_governance: {
      model_issue_time: "2026-11-25T00:00:00Z",
      valid_time: "2026-11-25T14:00:00Z",
      retrieval_time: "2026-11-25T14:30:43Z",
      model_run_age_hours: 14.5,
      forecast_lead_hours: 14.0,
      valid_time_offset_hours: -0.5,
      valid_time_vs_retrieval: "PAST",
      model_run_relation: "FORECAST",
      data_source_type: "MODEL_DERIVED",
      provider_timezone: "UTC",
      provider_utc_offset_seconds: 0,
    },
    freshness: { status: "CURRENT_CYCLE", cache_hit: false, disclaimer: "Model-derived" },
    warnings: [],
  };

  const fullHtml = renderToStaticMarkup(React.createElement(AQIGauge, { data: baseData }));
  assert.match(fullHtml, /Valid time:/);
  assert.match(fullHtml, /2026-11-25 14:00:00 UTC/);
  assert.match(fullHtml, /Model issue time:/);
  assert.match(fullHtml, /2026-11-25 00:00:00 UTC/);
  assert.match(fullHtml, /Retrieved at:/);
  assert.match(fullHtml, /2026-11-25 14:30:43 UTC/);
  assert.match(fullHtml, /Run relation:/);
  assert.match(fullHtml, /FORECAST/);
  assert.match(fullHtml, /Forecast lead:/);
  assert.match(fullHtml, /\+14\.0h/);
  assert.match(fullHtml, /not<\/em> an official CPCB continuous monitoring station/i);

  // When optional model_issue_time and forecast_lead_hours are null, omit cleanly rather than inventing values
  const partialData = {
    ...baseData,
    temporal_governance: {
      ...baseData.temporal_governance,
      model_issue_time: null,
      forecast_lead_hours: null,
      model_run_relation: "UNKNOWN",
    },
  };
  const partialHtml = renderToStaticMarkup(React.createElement(AQIGauge, { data: partialData }));
  assert.match(partialHtml, /Valid time:/);
  assert.match(partialHtml, /Retrieved at:/);
  assert.match(partialHtml, /UNKNOWN/);
  assert.doesNotMatch(partialHtml, /Model issue time:/);
  assert.doesNotMatch(partialHtml, /Forecast lead:/);
});

// ─── DEF-05: City loading, fallback & functional toggle selection ─────

test("DEF-05: comparison city loading uses API list when available, falls back gracefully, and avoids duplicates", () => {
  const {
    resolveComparisonCityOptions,
    toggleComparisonCitySelection,
    buildComparisonRequestPayload,
  } = comparisonMod;

  const apiCities = [
    { id: "delhi", name: "New Delhi", state: "Delhi", latitude: 28.61, longitude: 77.21 },
    { id: "varanasi", name: "Varanasi", state: "Uttar Pradesh", latitude: 25.31, longitude: 82.97 },
    { id: "varanasi", name: "Varanasi Duplicate", state: "Uttar Pradesh", latitude: 25.31, longitude: 82.97 },
  ];
  const merged = resolveComparisonCityOptions(apiCities, constantsMod.POPULAR_CITIES);
  assert.equal(merged.length, 2);
  assert.equal(merged[1].id, "varanasi");

  // Graceful fallback on API failure / empty response
  const fallback = resolveComparisonCityOptions(null, constantsMod.POPULAR_CITIES);
  assert.equal(fallback.length, constantsMod.POPULAR_CITIES.length);

  // Rapid functional toggles prevent duplicates and enforce [2, 6]
  let sel = ["delhi", "mumbai"];
  // Cannot go below 2
  sel = toggleComparisonCitySelection(sel, "delhi");
  assert.deepEqual(sel, ["delhi", "mumbai"]);
  // Add up to 6 cleanly
  for (const cid of ["bengaluru", "kolkata", "chennai", "varanasi", "kochi"]) {
    sel = toggleComparisonCitySelection(sel, cid);
  }
  assert.equal(sel.length, 6);
  assert.ok(!sel.includes("kochi"));
  // Deduplicates dirty input
  const deduped = toggleComparisonCitySelection(["delhi", "delhi", "mumbai", "pune"], "pune");
  assert.deepEqual(deduped, ["delhi", "mumbai"]);

  const payload = buildComparisonRequestPayload(["delhi", "varanasi"], merged);
  assert.deepEqual(payload, [{ city: "New Delhi" }, { city: "Varanasi" }]);

  // Verify LocationComparison source uses fetchCities + functional updater
  const cmpSrc = fs.readFileSync(path.resolve("src/components/LocationComparison.tsx"), "utf8");
  assert.match(cmpSrc, /fetchCities\(\)/);
  assert.match(cmpSrc, /setSelectedCities\(\(prev\)\s*=>\s*toggleComparisonCitySelection\(prev,\s*cityId\)\)/);
});

// ─── DEF-06: Historical model-derived wording ─────────────────────────

test("DEF-06: HistoricalCharts removes Feature E & CPCB AQI and states CAMS model-derived wording", () => {
  const { HistoricalCharts } = loadTsModule("src/components/HistoricalCharts.tsx", {
    "../lib/api": { fetchHistoricalTrends: async () => ({}) },
    recharts: new Proxy(
      {},
      {
        get: (_t, prop) => (props) =>
          React.createElement("div", { "data-recharts": String(prop) }, props?.children),
      }
    ),
  });

  const html = renderToStaticMarkup(React.createElement(HistoricalCharts, { city: "New Delhi" }));
  assert.doesNotMatch(html, /Feature E/);
  assert.doesNotMatch(html, /CPCB AQI/);
  assert.match(html, /Indicative Index/);
  assert.match(html, /Copernicus CAMS/);
  assert.match(html, /not physical monitoring station observations/i);
  assert.doesNotMatch(html, /Real historical/);
});

// ─── DEF-07 & DEF-08: Search Retry, Alert Labels, PollutantGrid A11y & Focus Rings ─

test("DEF-07: page.tsx clears invalid searchQuery on Retry and gives distinct alert aria-labels", () => {
  const pageSrc = fs.readFileSync(path.resolve("src/app/page.tsx"), "utf8");
  assert.match(pageSrc, /role="alert"\s+aria-label="Air quality threshold alert"/);
  assert.match(pageSrc, /role="alert"\s+aria-label="Data loading error"/);
  assert.match(pageSrc, /setSearchQuery\(""\);\s*loadData\(c\.name\);/);
});

const modalDialogMod = loadTsModule("src/components/ModalDialog.tsx");

test("DEF-08: PollutantGrid uses semantic button cards without nested buttons and globals.css defines :focus-visible", () => {
  const { PollutantGrid } = loadTsModule("src/components/PollutantGrid.tsx", {
    "../lib/constants": constantsMod,
    "./ModalDialog": modalDialogMod,
  });

  const html = renderToStaticMarkup(
    React.createElement(PollutantGrid, {
      pollutants: {
        pm25: {
          code: "pm25",
          name: "Particulate Matter <= 2.5 um",
          status: "SUFFICIENT",
          concentration: 103.7,
          unit: "ug/m3",
          reported_unit: "ug/m3",
          sub_index: 246,
          category: "POOR",
          color: "#F97316",
          averaging_period: "24h",
          rolling_window: null,
          unavailable_reason: null,
          description: "Fine particles.",
          health_effects: "Airway irritation.",
          sources: "Traffic and combustion.",
        },
        nh3: {
          code: "nh3",
          name: "Ammonia",
          status: "UNAVAILABLE",
          concentration: null,
          unit: "ug/m3",
          reported_unit: null,
          sub_index: null,
          category: null,
          color: null,
          averaging_period: "24h",
          rolling_window: null,
          unavailable_reason: "Not supplied in CAMS feed",
          description: "Gas.",
          health_effects: "Irritant.",
          sources: "Agriculture.",
        },
      },
      unavailablePollutants: ["nh3"],
    })
  );

  // Two semantic <button type="button"> cards rendered, ZERO nested <button> tags inside cards
  const buttonMatches = html.match(/<button\b/g) || [];
  assert.equal(buttonMatches.length, 2);
  assert.match(html, /aria-label="View details for Particulate Matter &lt;= 2\.5 um \(PM25\)"/);
  assert.match(html, /aria-label="View details for Ammonia \(NH3\)"/);
  assert.match(html, /focus-visible:ring-2/);

  const cssSrc = fs.readFileSync(path.resolve("src/app/globals.css"), "utf8");
  assert.match(cssSrc, /:focus-visible/);
});
