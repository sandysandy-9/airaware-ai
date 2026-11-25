# AirAware AI — Stage 3.1 Independent Final Engineering Audit Report

**Audit Date (IST):** 2026-11-25  
**Reviewer Role:** Independent Senior Backend Reviewer  
**Scope:** Verification of Stage 3.1 Production Backend & Core Data Pipeline against frozen Stage 1 (`airaware_architecture_v2_4_3.md`, `stage1_test_evidence_v243.json`) and Stage 2.1 evidence.  
**Audit Posture:** Zero implementation source files, schemas, routes, configs, Stage 1 math, or Stage 2 evidence were modified during this audit. No git commits or pushes were executed.

---

## Executive Verdict

**VERDICT: `NEEDS REMEDIATION BEFORE STAGE 3.2` (1 Critical, 1 High, 3 Medium, 2 Low Findings)**

While the Stage 3.1 rolling-window trapezoidal integrator, Stage 2.1 temporal governance separation, Open-Meteo adapter hardening, and API validation layers are structurally sound (`52 / 52` pytest cases passing), independent empirical probing uncovered a **Critical numerical defect** inherited from Stage 0 in `cpcb_calculator.py` (`lines 95–120`): continuous floating-point rolling averages falling in the decimal gap between integer CPCB brackets (e.g., `pm25 = 30.5`, `60.5`, `120.5`, `co = 1.05`) miss all `[c_low, c_high]` intervals and fall back to `breakpoints[0]`, returning **incorrect sub-indices and mislabeling severe concentrations as `GOOD`**.

**Recommendation:** Request approval to apply a targeted remediation patch (fixing `cpcb_calculator.py` continuous interval matching plus the Medium comparison/cache/rate-limiter items) before beginning Stage 3.2.

---

## 1. Audit Checklist Summary

| # | Checklist Item | Status | Highest Severity | Key Empirical Outcome |
|---|---|---|---|---|
| 1 | `rolling_window.py` vs all 20 cases in `stage1_test_evidence_v243.json` | **PASS** | Low | `0` numerical mismatches across all 20 frozen cases (`dur`, `cov`, `integral`, `mean`). |
| 2 | `indicative_index.py` & CPCB breakpoint evaluation | **FAIL** | **Critical** | Composite eligibility & labeling pass, but `cpcb_calculator.py` misclassifies continuous floats between integer brackets (`pm25=120.5` → `sub_index=201`, `"GOOD"`). |
| 3 | Cache provenance preservation & freshness truthfulness | **NEEDS ATTENTION** | Medium | Original `retrieval_time` & `cache_hit` preserved accurately; `TTLCache` & `_inflight_locks` lack thread lock & bounded eviction. |
| 4 | Comparison ranking across times, snaps & unavailable indices | **NEEDS ATTENTION** | Medium | Cleanly handles partial provider failures; however, 1-of-N success sets `cleanest == most_polluted` instead of `None`. |
| 5 | Backend trust boundary (rejecting client AQI/risk overrides) | **NEEDS ATTENTION** | High (Stage 0) | Stage 3.1 `/current` & `/compare` enforce strict `422` rejection; legacy Stage 0 `/recommendations` & `/ai/chat` remain mounted pending Stage 3.2. |
| 6 | Coordinate validation, timeouts, HTTP errors & malformed payloads | **PASS** | Low | `NaN`/`Inf`/out-of-bounds/half-pairs return `422`; timeouts `504`; upstream errors `503`. Minor unguarded `float(returned_lat)`. |
| 7 | CORS, rate limiting, secret redaction, env config & exceptions | **NEEDS ATTENTION** | Medium | CORS, traceback suppression & `SecretRedactingFilter` work properly; `rate_limiter.py` hardcodes `120` instead of reading `settings`. |
| 8 | Complete backend test suite execution | **PASS** | — | **`52 passed, 0 failed`** in `5.41s` (`pytest tests -v`). |
| 9 | Stage 1 SHA-256 & Stage 2.1 evidence integrity | **PASS** | — | `stage1_test_evidence_v243.json` SHA-256 unchanged; all `9` Stage 2 JSON files parse cleanly. |
| 10 | Git diff audit for secrets, debug code & unrelated edits | **PASS** | — | Zero credentials, zero stray debug code; only expected Stage 2–3.1 paths modified/added. |

---

## 2. Detailed Findings by Severity

### [CRITICAL-01] Continuous Floating-Point Concentrations Fall Between Integer CPCB Brackets
- **Checklist Item:** #2 (`indicative_index.py` & `cpcb_calculator.py`)
- **Files & Lines:**
  - `backend/app/engine/cpcb_breakpoints.py` (`lines 61–125`)
  - `backend/app/engine/cpcb_calculator.py` (`lines 94–120`)
  - Consumed by `backend/app/engine/rolling_window.py` (`line 193`) → `backend/app/engine/indicative_index.py` (`line 42`)
- **Root Cause:**
  `CPCB_BREAKPOINTS` defines discrete integer-separated intervals (e.g., `pm25`: `(0, 30)`, `(31, 60)`, `(61, 90)`, `(91, 120)`, `(121, 250)`, `(251, 350)`; `co`: `(0.0, 1.0)`, `(1.1, 2.0)`, `(2.1, 10.0)`). Stage 3.1 rolling-window averages produce continuous floats (e.g., `30.5`, `60.5`, `120.5`, `1.05`). In `cpcb_calculator.py` lines `95–98`, `bp.c_low <= concentration <= bp.c_high` fails for every range when `concentration` lies in any inter-bracket gap. Line `119` then falls back to `matched_bp = breakpoints[0]`, extrapolating outside `[0, 30]` and stamping `category = "GOOD"`.
- **Empirical Reproduction (`scratch/audit_stage3_1.py`):**
  ```text
  pm25=30.5  -> sub_index=51,  category=GOOD, valid=True
  pm25=60.5  -> sub_index=101, category=GOOD, valid=True
  pm25=90.5  -> sub_index=151, category=GOOD, valid=True
  pm25=120.5 -> sub_index=201, category=GOOD, valid=True   # Expected ~300/301 POOR/VERY_POOR!
  pm10=100.5 -> sub_index=100, category=GOOD, valid=True   # Expected ~101 MODERATE!
  co=1.05    -> sub_index=52,  category=GOOD, valid=True
  co=2.05    -> sub_index=102, category=GOOD, valid=True
  o3=100.5   -> sub_index=100, category=GOOD, valid=True
  ```
- **Required Fix (Requires Approval):** Round concentration to standard CPCB precision (`round(concentration)` for µg/m³ pollutants, `round(concentration, 1)` for `co`/`pb`, OR interpolate continuously across adjacent `[prev.c_high, next.c_low]` transitions using `(i_low - 1, c_prev_high)` / CPCB standard continuous breakpoint table) and add regression unit tests covering `30.5`, `60.5`, `90.5`, `120.5`, `1.05`, `2.05`.

---

### [HIGH-01] Stage 0 Client-Override Routes Still Mounted on Active FastAPI Application
- **Checklist Item:** #5 (Backend trust boundary)
- **Files & Lines:**
  - `backend/app/main.py` (`lines 75–76`)
  - `backend/app/api/routes_recommendations.py` (`lines 15–23`)
  - `backend/app/schemas/recommendation.py` (`lines 21–23`)
  - `backend/app/schemas/ai_chat.py` (`line 15`)
- **Finding:** All Stage 3.1 endpoints (`/api/v1/air-quality/current` and `/api/v1/air-quality/compare` GET/POST) strictly reject client-supplied `aqi`, `category`, `dominant_pollutant`, `risk_score`, and `data_freshness` with `HTTP 422`. However, pre-existing Stage 0 routes `/api/v1/recommendations` and `/api/v1/ai/chat` remain active and accept client-provided `aqi` / `current_context`.
- **Context:** Explicitly deferred by Stage 3.1 Section 11 to Stage 3.2 ("AI chatbot... health recommendations belong to later milestones"). Tracked here as a **High** pre-production blocker for Stage 3.2.

---

### [MEDIUM-01] Comparison Ranking Outputs Single Surviving Location as Both Cleanest & Most Polluted
- **Checklist Item:** #4 (Comparison ranking behavior)
- **Files & Lines:** `backend/app/api/routes_comparison.py` (`lines 135–143`)
- **Finding:** When 2 locations are compared and 1 fails (`PROVIDER_UNAVAILABLE` or `INSUFFICIENT_DATA`), `available_assessments` has length `1`. Because line `137` checks `if available_assessments:`, both `cleanest_location` and `most_polluted_location` return the same city (observed in `Audit Probe D`: `cleanest: New Delhi ...`, `most_polluted: New Delhi ...`). Additionally, differences in cached `retrieval_time` across items and excluded `INSUFFICIENT_DATA` items are not explicitly noted in `data_integrity_warnings`.
- **Recommended Fix:** Require `if len(available_assessments) >= 2:` to populate `cleanest_location` / `most_polluted_location` (leaving both `None` with an explanatory warning when `< 2` indices are available), and warn if `retrieval_time` values differ across comparison items.

---

### [MEDIUM-02] Unbounded In-Memory `TTLCache` & `_inflight_locks` Without Concurrency Lock / Eviction
- **Checklist Item:** #3 (Cache provenance & stability)
- **Files & Lines:**
  - `backend/app/services/cache_service.py` (`lines 7–30`)
  - `backend/app/services/air_quality_service.py` (`line 25`)
- **Finding:** `air_quality_service.py` accurately preserves original `retrieval_time_utc`, exposes `cache_hit`, and avoids stale labels. However, `TTLCache` has no `threading.Lock()` and no maximum key limit (`maxsize`/LRU eviction), and `_inflight_locks` inserts a new `asyncio.Lock` per unique `(lat, lon, date)` key without ever pruning completed entries. Repeated distinct-coordinate queries will grow process memory monotonically.

---

### [MEDIUM-03] `SlidingWindowRateLimiter` Hardcodes Limit Instead of Reading `settings`
- **Checklist Item:** #7 (Environment configuration & rate limiting)
- **Files & Lines:**
  - `backend/app/core/rate_limiter.py` (`line 40`)
  - `backend/app/core/config.py` (`line 52`)
- **Finding:** `rate_limiter = SlidingWindowRateLimiter(max_requests_per_minute=120, window_seconds=60)` ignores `settings.rate_limit_requests_per_minute` (`AIRAWARE_RATE_LIMIT_PER_MIN`). Changing `.env` has no effect on the active dependency.

---

### [LOW-01] `rolling_window.py` Outside-Window Accounting Difference on `TEST-13`
- **Checklist Item:** #1 (`rolling_window.py` vs `stage1_test_evidence_v243.json`)
- **Files & Lines:** `backend/app/engine/rolling_window.py` (`line 143`)
- **Finding:** Numerical parity is `100%` (`0` mismatches across all 20 cases for `supported_duration_seconds`, `coverage_percentage`, `integrated_concentration`, and `time_weighted_mean`). Only `TEST-13` (samples completely outside `[W_s, W_e]`) reports `rejected_intervals_count = 0` vs `1` in `stage1_test_evidence_v243.json` because line `143` restricts `rejected_intervals_count` to intervals intersecting the rolling window.

---

### [LOW-02] Minor Type Coercion Guard in `normalize_open_meteo_response`
- **Checklist Item:** #6 (Malformed provider responses)
- **Files & Lines:** `backend/app/providers/open_meteo.py` (`lines 243–245`)
- **Finding:** `float(returned_lat)` / `float(returned_lon)` is not wrapped in `try/except (TypeError, ValueError)` to raise `ProviderValidationError` (if Open-Meteo returned `"N/A"` for coordinates, it would trigger HTTP `500` instead of `502 InvalidProviderResponse`). `NaN`/`Inf` in query parameters return `HTTP 422` cleanly on both `/current` and `/compare`.

---

## 3. Executed Commands & Observed Evidence

1. **Stage 1 Mathematical Parity & CPCB Breakpoint Probe:**
   - Command: `backend\.venv\Scripts\python.exe scratch\audit_stage3_1.py`
   - Result: `Rolling Window Numerical Mismatches: []`; `TEST-13` `rejected_intervals_count` `(0, 1)`; confirmed CPCB gap bug on all `8` continuous decimal test values (`30.5`, `60.5`, `90.5`, `120.5`, `100.5`, `1.05`, `2.05`, `100.5`).
2. **HTTP Edge-Case Probes (`NaN`, `Inf`, CORS Preflight, Partial Compare):**
   - Command: `backend\.venv\Scripts\python.exe scratch\audit_probes.py`
   - Result:
     - `GET /current?latitude=nan&longitude=77.2` → `422`
     - `GET /current?latitude=inf&longitude=77.2` → `422`
     - `GET /compare?locations=nan,77.2;19.0,72.8` → `422`
     - `GET /compare?locations=200.0,77.2;19.0,72.8` → `422`
     - `OPTIONS /current` (`Origin: http://localhost:3000`) → `200`, `Access-Control-Allow-Origin: http://localhost:3000`
     - `OPTIONS /current` (`Origin: https://evil.example`) → `400`, `None`
     - Partial failure `/compare?cities=delhi,mumbai` → `200`, both `cleanest_location` and `most_polluted_location` set to `"New Delhi (INDICATIVE_MODEL_INDEX 232, POOR)"`.
3. **Complete Backend Test Suite:**
   - Command: `Set-Location backend; .\.venv\Scripts\python.exe -m pytest tests -v`
   - Result: **`52 passed, 0 failed`** in `5.41s`.
4. **Baseline SHA-256, Stage 2 JSON & Working-Tree Hygiene:**
   - `stage1_test_evidence_v243.json` SHA-256: `D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773` (unchanged)
   - `airaware_architecture_v2_4_3.md` SHA-256: `896A1D91A5B1E5CD5B08AC3DFAA6B2890F6B615A5BD9C62DE56B9204A8435148` (unchanged)
   - `evidence/stage2/*.json`: `9 / 9` JSON files parsed with 0 errors.
   - `git diff --stat`: `14` tracked files modified (`.env.example`, `backend/app/main.py`, `routes_air_quality.py`, `routes_comparison.py`, `factory.py`, `open_meteo.py`, `schemas/{air_quality,comparison}.py`, 6 `__init__.py` whitespace lines). Zero secrets leaked (`print()` appears only twice inside `city_validation.py` `__main__`).

---

## 4. Remaining Production Limitations

1. **Coarse Model Spatial Scale (~0.4° Grid):** Open-Meteo `cams_global` snaps coordinates (`1.8–3.7 km` in tested cities) and cannot resolve street canyons or physical CAAQMS station microclimates.
2. **Ammonia (`nh3`) Unavailable in India:** Persistently `null` across Delhi, Mumbai, and Chennai in `cams_global`.
3. **Unverified Native Resolution:** Upstream ECMWF surface-field native resolution vs Open-Meteo's `3600s` `meta.json` grid step remains `UNKNOWN_PENDING_VERIFICATION`.
4. **Single-Worker Process State:** In-memory TTL caching and per-IP sliding-window rate limiting do not share state across multiple Uvicorn/Gunicorn worker processes or container replicas.
5. **Dual-Process Cold Cache Pressure:** Fresh instances without Redis depend on upstream `air-quality-api.open-meteo.com` reachability.

---

## 5. Readiness Decision for Stage 3.2

**DO NOT PROCEED TO STAGE 3.2 YET.**  
Approve remediation of **`[CRITICAL-01]`** (`cpcb_calculator.py` continuous floating-point breakpoint gap) — and recommended **`[MEDIUM-01]`**, **`[MEDIUM-02]`**, **`[MEDIUM-03]`** — prior to starting Stage 3.2. Once patched and re-tested, the Stage 3.1 foundation will be fully cleared for Stage 3.2.
