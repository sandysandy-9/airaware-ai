# AirAware AI — Stage 2: Live Provider Validation Evidence Report

**Execution Timestamp (UTC):** `2026-11-25T06:45:47.750216+00:00`  
**Recommendation:** **`CONDITIONAL ACCEPT`**  
**Frozen Baseline:** Architecture v2.4.3 (`stage1_test_evidence_v243.json`, SHA-256 `D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773`)  

## 1. Executive Summary
CONDITIONAL ACCEPT: Open-Meteo cams_global reliably provides 6 core criteria pollutants (PM2.5, PM10, NO2, SO2, CO in µg/m³, O3) across Delhi, Mumbai, and Chennai with complete 24h and 8h rolling-window coverage, verified Asia/Kolkata timestamps, and explicit domain=cams_global metadata alignment. Accepted conditionally because: (1) NH3 is completely absent across all 3 Indian cities; (2) upstream ECMWF native surface temporal resolution cannot be conclusively confirmed from Open-Meteo JSON/meta.json (meta.json reports 3600s Open-Meteo grid step while docs mention 3-hourly source) and remains UNKNOWN_PENDING_VERIFICATION; (3) model grid resolution (~0.4 deg) is a regional estimate, never equivalent to CPCB physical station measurements; and (4) domains=auto lacks verified metadata correspondence.

## 2. Test Environment and Execution Time
- **Execution UTC:** `2026-11-25T06:45:47.750216+00:00`
- **Python Version:** `3.11.18`
- **Platform:** `Windows-10-10.0.26300-SP0`
- **HTTP Client:** `httpx 0.28.1`

## 3. Provider Endpoints and Request Parameters
- **Primary Air Quality Endpoint:** `https://air-quality-api.open-meteo.com/v1/air-quality`
- **Model Metadata Endpoint:** `https://air-quality-api.open-meteo.com/data/cams_global/static/meta.json`
- **Requested Variables:** `pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,carbon_monoxide,ozone,ammonia`
- **Date Range:** `start_date=2026-11-23`, `end_date=2026-11-27`
- **Requested Timezone:** `Asia/Kolkata`
- **Domains Tested:** `cams_global`, `auto`

| City | Domain | HTTP Status | Retrieval Time (UTC) | Raw Evidence File |
|---|---|---|---|---|
| Delhi | `cams_global` | 200 | `2026-11-25T06:45:48.732193+00:00` | `stage2_raw_responses/delhi_cams_global_raw.json` |
| Delhi | `auto` | 200 | `2026-11-25T06:45:50.373569+00:00` | `stage2_raw_responses/delhi_auto_raw.json` |
| Mumbai | `cams_global` | 200 | `2026-11-25T06:45:51.228617+00:00` | `stage2_raw_responses/mumbai_cams_global_raw.json` |
| Mumbai | `auto` | 200 | `2026-11-25T06:45:52.869109+00:00` | `stage2_raw_responses/mumbai_auto_raw.json` |
| Chennai | `cams_global` | 200 | `2026-11-25T06:45:53.749001+00:00` | `stage2_raw_responses/chennai_cams_global_raw.json` |
| Chennai | `auto` | 200 | `2026-11-25T06:45:55.405069+00:00` | `stage2_raw_responses/chennai_auto_raw.json` |

## 4. Delhi Results
- **Requested Coords:** `(28.6139, 77.209)`
- **Returned Coords (`cams_global`):** `(28.599998, 77.20001)` | Geodesic Snap Distance: **1.7776 km** | Elevation: `214.0 m`
- **Timezone:** `Asia/Kolkata` (`utc_offset_seconds=19800`)
- **Stage 1 Index Eligibility (`cams_global`):** `eligible=True`, `INDICATIVE_MODEL_INDEX=212` (`POOR`), Dominant: `pm25`
- **Unavailable Pollutants:** `['nh3']`
- **`cams_global` vs `auto` Comparison:** `series_identical=True`, `coordinates_identical=True`, `mismatches={}`

## 5. Mumbai Results
- **Requested Coords:** `(19.076, 72.8777)`
- **Returned Coords (`cams_global`):** `(19.099998, 72.90001)` | Geodesic Snap Distance: **3.552 km** | Elevation: `6.0 m`
- **Timezone:** `Asia/Kolkata` (`utc_offset_seconds=19800`)
- **Stage 1 Index Eligibility (`cams_global`):** `eligible=True`, `INDICATIVE_MODEL_INDEX=116` (`MODERATE`), Dominant: `pm25`
- **Unavailable Pollutants:** `['nh3']`
- **`cams_global` vs `auto` Comparison:** `series_identical=True`, `coordinates_identical=True`, `mismatches={}`

## 6. Chennai Results
- **Requested Coords:** `(13.0827, 80.2707)`
- **Returned Coords (`cams_global`):** `(13.099998, 80.30002)` | Geodesic Snap Distance: **3.7126 km** | Elevation: `12.0 m`
- **Timezone:** `Asia/Kolkata` (`utc_offset_seconds=19800`)
- **Stage 1 Index Eligibility (`cams_global`):** `eligible=True`, `INDICATIVE_MODEL_INDEX=62` (`SATISFACTORY`), Dominant: `o3`
- **Unavailable Pollutants:** `['nh3']`
- **`cams_global` vs `auto` Comparison:** `series_identical=True`, `coordinates_identical=True`, `mismatches={}`

## 7. Pollutant Availability and Units (`cams_global`)
| City | Pollutant | Present | Valid / Total | Nulls | Non-Finite | Negatives | Reported Unit | Normalized Unit | Max Gap (s) |
|---|---|---|---|---|---|---|---|---|---|
| Delhi | `pm25` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Delhi | `pm10` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Delhi | `no2` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Delhi | `so2` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Delhi | `co` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `mg/m³` | 3600.0 |
| Delhi | `o3` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Delhi | `nh3` | True | 0 / 120 | 120 | 0 | 0 | `μg/m³` | `µg/m³` | None |
| Mumbai | `pm25` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Mumbai | `pm10` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Mumbai | `no2` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Mumbai | `so2` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Mumbai | `co` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `mg/m³` | 3600.0 |
| Mumbai | `o3` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Mumbai | `nh3` | True | 0 / 120 | 120 | 0 | 0 | `μg/m³` | `µg/m³` | None |
| Chennai | `pm25` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Chennai | `pm10` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Chennai | `no2` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Chennai | `so2` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Chennai | `co` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `mg/m³` | 3600.0 |
| Chennai | `o3` | True | 120 / 120 | 0 | 0 | 0 | `μg/m³` | `µg/m³` | 3600.0 |
| Chennai | `nh3` | True | 0 / 120 | 120 | 0 | 0 | `μg/m³` | `µg/m³` | None |

## 8. Requested versus Returned Coordinates
| City | Requested (Lat, Lon) | Returned (Lat, Lon) | Geodesic Distance (km) | Elevation (m) |
|---|---|---|---|---|
| Delhi | `(28.6139, 77.209)` | `(28.599998, 77.20001)` | 1.7776 km | 214.0 |
| Mumbai | `(19.076, 72.8777)` | `(19.099998, 72.90001)` | 3.552 km | 6.0 |
| Chennai | `(13.0827, 80.2707)` | `(13.099998, 80.30002)` | 3.7126 km | 12.0 |

## 9. Temporal Resolution Findings
- **API Output Timestamp Frequency:** Verified **3600 seconds (1 hour)** across all 3 cities.
- **Open-Meteo `cams_global/static/meta.json` `temporal_resolution_seconds`:** Reported as **`3600` seconds (1 hour)**.
- **Upstream ECMWF Native Surface-Field Temporal Resolution:** Marked **`UNKNOWN_PENDING_VERIFICATION`**. Open-Meteo overview documentation describes CAMS Global as 3-hourly, while `meta.json` reports `3600s` on the stored API grid and hourly API outputs display non-constant step changes. Per Stage 1 and Stage 2 strict scientific governance rules, AirAware AI does not infer native resolution from modulo math or model names alone.
- **Timezone Parsing Finding:** Host Windows Python lacks built-in `tzdata` for `Asia/Kolkata`. Our adapter logs this explicitly and localizes naive provider timestamps deterministically via `utc_offset_seconds=19800` (+05:30 IST, non-DST) before normalizing all calculations to UTC.

## 10. Valid-Time Distribution & Model-Run Relation (MODEL_DERIVED)
> All returned series are **`MODEL_DERIVED`** grid outputs. Past-valid model forecasts (`model_issue_time < valid_time < retrieval_time`) are explicitly distinguished from prior-cycle archived outputs (`UNKNOWN` run relation) and are never labeled as physical observations.

| City | Past-Valid Total | Past-Valid Forecast (`lead>0, t<ret`) | Prior Cycles (`UNKNOWN` rel) | Future-Valid Forecast (`t>ret`) | Source Type |
|---|---|---|---|---|---|
| Delhi | 61 (`2026-11-22T18:30:00+00:00` to `2026-11-25T06:30:00+00:00`) | 19 | 42 | 59 | `MODEL_DERIVED` |
| Mumbai | 61 (`2026-11-22T18:30:00+00:00` to `2026-11-25T06:30:00+00:00`) | 19 | 42 | 59 | `MODEL_DERIVED` |
| Chennai | 61 (`2026-11-22T18:30:00+00:00` to `2026-11-25T06:30:00+00:00`) | 19 | 42 | 59 | `MODEL_DERIVED` |

### Temporal Governance Verification (`current_hour` Anchor)
| City | Domain | `valid_time` | `retrieval_time` | `model_issue_time` | `valid_time_vs_retrieval` | `model_run_relation` | `forecast_lead_hours` | `data_source_type` |
|---|---|---|---|---|---|---|---|---|
| Delhi | `cams_global` | `2026-11-25T06:00:00Z` | `2026-11-25T06:45:48.732193Z` | `2026-11-24T12:00:00Z` | `PAST` | `FORECAST` | 18.0 | `MODEL_DERIVED` |
| Delhi | `auto` | `2026-11-25T06:00:00Z` | `2026-11-25T06:45:50.373569Z` | `None` | `PAST` | `UNKNOWN` | None | `MODEL_DERIVED` |
| Mumbai | `cams_global` | `2026-11-25T06:00:00Z` | `2026-11-25T06:45:51.228617Z` | `2026-11-24T12:00:00Z` | `PAST` | `FORECAST` | 18.0 | `MODEL_DERIVED` |
| Mumbai | `auto` | `2026-11-25T06:00:00Z` | `2026-11-25T06:45:52.869109Z` | `None` | `PAST` | `UNKNOWN` | None | `MODEL_DERIVED` |
| Chennai | `cams_global` | `2026-11-25T06:00:00Z` | `2026-11-25T06:45:53.749001Z` | `2026-11-24T12:00:00Z` | `PAST` | `FORECAST` | 18.0 | `MODEL_DERIVED` |
| Chennai | `auto` | `2026-11-25T06:00:00Z` | `2026-11-25T06:45:55.405069Z` | `None` | `PAST` | `UNKNOWN` | None | `MODEL_DERIVED` |

## 11. Boundary Validation (Current Hour `cams_global`)
| City | Pollutant | Window (h) | Left Boundary Supported | Right Boundary Supported | Coverage % | Mean | Exceeds Gmax? |
|---|---|---|---|---|---|---|---|
| Delhi | `pm25` | 24h | True | True | 100.0% | 94.0948 | False |
| Delhi | `pm10` | 24h | True | True | 100.0% | 96.7167 | False |
| Delhi | `no2` | 24h | True | True | 100.0% | 46.8 | False |
| Delhi | `so2` | 24h | True | True | 100.0% | 35.224 | False |
| Delhi | `co` | 8h | True | True | 100.0% | 1.5924 | False |
| Delhi | `o3` | 8h | True | True | 100.0% | 46.4375 | False |
| Mumbai | `pm25` | 24h | True | True | 100.0% | 65.3906 | False |
| Mumbai | `pm10` | 24h | True | True | 100.0% | 68.2781 | False |
| Mumbai | `no2` | 24h | True | True | 100.0% | 35.7339 | False |
| Mumbai | `so2` | 24h | True | True | 100.0% | 25.1109 | False |
| Mumbai | `co` | 8h | True | True | 100.0% | 0.5322 | False |
| Mumbai | `o3` | 8h | True | True | 100.0% | 73.4531 | False |
| Chennai | `pm25` | 24h | True | True | 100.0% | 4.5245 | False |
| Chennai | `pm10` | 24h | True | True | 100.0% | 6.2552 | False |
| Chennai | `no2` | 24h | True | True | 100.0% | 5.5833 | False |
| Chennai | `so2` | 24h | True | True | 100.0% | 3.5969 | False |
| Chennai | `co` | 8h | True | True | 100.0% | 0.2396 | False |
| Chennai | `o3` | 8h | True | True | 100.0% | 61.5 | False |

## 12. Model Metadata and Provenance
Captured raw `/data/cams_global/static/meta.json`:
```json
{
  "chunk_time_length": 217,
  "crs_wkt": "GEOGCRS[\"WGS 84\",\n    DATUM[\"World Geodetic System 1984\",\n        ELLIPSOID[\"WGS 84\",6378137,298.257223563]],\n    CS[ellipsoidal,2],\n        AXIS[\"latitude\",north],\n        AXIS[\"longitude\",east],\n        ANGLEUNIT[\"degree\",0.0174532925199433]\n    USAGE[\n        SCOPE[\"grid\"],\n        BBOX[-90.0,-180.0,90.0,179.6]]]",
  "data_end_time": 1795957200,
  "last_run_availability_time": 1795557116,
  "last_run_initialisation_time": 1795521600,
  "last_run_modification_time": 1795557116,
  "temporal_resolution_seconds": 3600,
  "update_interval_seconds": 43200
}
```
- **`domain=cams_global` Metadata Correspondence:** `verified=True`, `model_issue_time=2026-11-24T12:00:00Z`, `update_interval_seconds=43200`.
- **`domain=auto` Metadata Correspondence:** `verified=False`, `model_issue_time=None` (Strict null preservation per Best Match documentation warning).

## 13. Stage 1 Compatibility Matrix
| City | Current Hour (`INDICATIVE_MODEL_INDEX`) | Category | Dominant | Past-Valid (-12h) Eligible | Future-Valid (+12h) Eligible |
|---|---|---|---|---|---|
| Delhi | `212` (`eligible=True`) | `POOR` | `pm25` | True (`129`) | True (`261`) |
| Mumbai | `116` (`eligible=True`) | `MODERATE` | `pm25` | True (`182`) | True (`174`) |
| Chennai | `62` (`eligible=True`) | `SATISFACTORY` | `o3` | True (`53`) | True (`48`) |

## 14. Provider Limitations
1. **Ammonia (`ammonia` / `nh3`) Completely Unavailable:** Returns all `null` across Delhi, Mumbai, and Chennai.
2. **Coarse Spatial Grid (~0.4 deg / ~45 km):** Model grid snaps requested urban coordinates by ~1.5 km to ~5.2 km; cannot resolve street-level hotspots or regulatory station microclimates.
3. **Not a Physical Monitoring Station:** Outputs represent CAMS atmospheric chemistry simulations, NOT CPCB CAAQMS physical measurements.
4. **Metadata Atomicity:** `/v1/air-quality` does not embed `model_issue_time` directly inside the time-series JSON response; correspondence with `static/meta.json` requires explicit `domains=cams_global`.
5. **CO Unit Scale:** Returned in `µg/m³`, requiring explicit division by 1,000 before CPCB `mg/m³` breakpoint evaluation.

## 15. Errors and Anomalies
- **HTTP / Provider Transport Errors:** None.
- **Delhi Notes:** anomalies=[], tz_notes=["Host Python environment lacked tzdata key 'Asia/Kolkata'; converted using provider utc_offset_seconds=19800s."]
- **Mumbai Notes:** anomalies=[], tz_notes=["Host Python environment lacked tzdata key 'Asia/Kolkata'; converted using provider utc_offset_seconds=19800s."]
- **Chennai Notes:** anomalies=[], tz_notes=["Host Python environment lacked tzdata key 'Asia/Kolkata'; converted using provider utc_offset_seconds=19800s."]

## 16. Verification Status Matrix & Recommendation
| Check | Status |
|---|---|
| `cams_global_all_cities_reachable` | **PASS** |
| `auto_domain_all_cities_reachable` | **PASS** |
| `core_6_pollutants_available_all_cities` | **PASS** |
| `ammonia_nh3_available_in_india` | **FAIL** |
| `stage1_rolling_windows_supported_all_cities` | **PASS** |
| `temporal_governance_separation_verified` | **PASS** |
| `upstream_ecmwf_native_temporal_resolution` | **UNKNOWN** |
| `cams_global_meta_json_correspondence` | **PASS** |
| `auto_domain_metadata_correspondence` | **FAIL** |

### Final Stage 2 Recommendation: **`CONDITIONAL ACCEPT`**
