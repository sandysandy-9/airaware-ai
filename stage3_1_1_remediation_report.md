# AirAware AI — Stage 3.1.1 Remediation & Verification Report

**Date:** 2026-11-25  
**Scope:** Targeted remediation of `CRITICAL-01`, `HIGH-01`, `MEDIUM-01`, `MEDIUM-02`, `MEDIUM-03`, `LOW-01`, and `LOW-02` from [stage3_1_final_audit_report.md](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/stage3_1_final_audit_report.md) without redesigning Architecture v2.4.3 or beginning Stage 3.2.

---

## 1. Audit Findings & Resolutions

| Finding | Severity | Root Cause | Remediation Implemented | Verification Status |
| :--- | :--- | :--- | :--- | :--- |
| **CRITICAL-01** | Critical | `calculate_sub_index` checked `bp.c_low <= conc <= bp.c_high` over integer-separated CPCB bounds (e.g., `30..31`, `60..61`, `100..101`, `1.0..1.1`), falling back to `breakpoints[0]` (`GOOD`) for continuous floats such as `30.5`, `60.5`, `90.5`, `120.5`, `100.5`, `1.05`, `2.05`, and lacking `NaN`/`Inf`/`bool` rejection. | Updated `calculate_sub_index` in [cpcb_calculator.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/cpcb_calculator.py) to match continuous contiguous intervals `(prev_bp.c_high, curr_bp.c_high]` with continuous CPCB lower index adjustment (`i_low - 1` when `i_low > 50`), reject non-finite/non-numeric/`bool`/negative inputs cleanly, and derive categories strictly via `_resolve_aqi_category` without altering frozen [cpcb_breakpoints.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/cpcb_breakpoints.py). | **Resolved & Tested** (48 parametric & regression tests passing) |
| **HIGH-01** | High | Legacy Stage 0 endpoints `POST /api/v1/recommendations` and `POST /api/v1/ai/chat` trusted client-supplied `aqi`, `aqi_category`, `dominant_pollutant`, `current_context`, and `comparison_context` as authoritative. | Removed override fields and added `ConfigDict(extra="forbid")` on `RecommendationRequest` ([recommendation.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/schemas/recommendation.py)) and `AIChatRequest` ([ai_chat.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/schemas/ai_chat.py)). Refactored [routes_recommendations.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_recommendations.py) to compute context authoritatively via `air_quality_service.assess_location(...)` (returning HTTP `503` on insufficient data and `422` on spoofed fields). Disabled [routes_ai.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_ai.py) (`503 AssistantPendingStage32`) and hardened [ai_service.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/services/ai_service.py) pending Stage 3.2. | **Resolved & Tested** (trust-boundary & override rejection tests passing) |
| **MEDIUM-01** | Medium | `routes_comparison.py` ranked `cleanest_location` and `most_polluted_location` whenever `len(available_assessments) >= 1` (single survivor after partial failure) and omitted explicit warnings for `INSUFFICIENT_DATA` exclusions and `retrieval_time` spread. | Updated `_run_comparison` in [routes_comparison.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_comparison.py) to require `len(available_assessments) >= 2`, emit `None` + explanatory warning when `< 2` valid indicative indices exist, warn on `INSUFFICIENT_DATA` exclusions and `retrieval_time` spread `>= 60s`, and preserve `valid_time`, `model_issue_time`, and grid-snap warnings. | **Resolved & Tested** (all 7 required comparison scenarios passing) |
| **MEDIUM-02** | Medium | `TTLCache` was unbounded without thread locking; `AirQualityPipelineService._inflight_locks` leaked completed lock entries. | Replaced `TTLCache` in [cache_service.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/services/cache_service.py) with a thread-safe (`threading.RLock`) `OrderedDict` LRU+TTL cache bounded by `settings.cache_max_entries` ([config.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/core/config.py)), fixed write-time expiration (reads never extend TTL/freshness), eager expired-entry purge, and ref-counted `_InflightLockEntry` cleanup in [air_quality_service.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/services/air_quality_service.py). Documented single-process scope. | **Resolved & Tested** (eviction, expiry, thread-safety, and async coalescing/cleanup tests passing) |
| **MEDIUM-03** | Medium | `SlidingWindowRateLimiter` instantiated global `rate_limiter` with hardcoded `max_requests_per_minute=120`, ignoring `settings.rate_limit_requests_per_minute`. | Wired `SlidingWindowRateLimiter` in [rate_limiter.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/core/rate_limiter.py) to `settings.rate_limit_requests_per_minute`, added `from_settings()` / `reconfigure()`, and documented single-process scope. | **Resolved & Tested** (env-loading and dual-limit enforcement tests passing) |
| **LOW-01** | Low | `app/engine/rolling_window.py` skipped non-intersecting intervals (`clip_start >= clip_end`) without incrementing `rejected_intervals_count`, leaving `TEST-13` at `0` vs frozen `1`. | Updated [rolling_window.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/rolling_window.py) to count outside-window intervals in `rejected_intervals_count` (with reason in `rejected_gap_reasons`) without changing accepted intervals, duration, coverage, integrals, or means. | **Resolved & Tested** (20/20 exact Stage 1 evidence match including `TEST-13`) |
| **LOW-02** | Low | `open_meteo.py` executed unguarded `float(returned_lat)` / `float(returned_lon)`, risking raw `ValueError`/`TypeError` (HTTP `500`) on malformed or non-finite values. | Added `_parse_validated_coordinate(...)` and finite-elevation guard in [open_meteo.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/providers/open_meteo.py), raising `ProviderValidationError` mapped to HTTP `502`. | **Resolved & Tested** (unit & API `502` regression tests passing) |

---

## 2. Exact Files Changed (Stage 3.1.1)

### Production Source Files
1. [cpcb_calculator.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/cpcb_calculator.py)
2. [recommendation.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/schemas/recommendation.py)
3. [routes_recommendations.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_recommendations.py)
4. [routes_air_quality.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_air_quality.py)
5. [ai_chat.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/schemas/ai_chat.py)
6. [routes_ai.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_ai.py)
7. [ai_service.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/services/ai_service.py)
8. [routes_comparison.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/api/routes_comparison.py)
9. [config.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/core/config.py)
10. [cache_service.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/services/cache_service.py)
11. [air_quality_service.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/services/air_quality_service.py)
12. [rate_limiter.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/core/rate_limiter.py)
13. [rolling_window.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/rolling_window.py)
14. [open_meteo.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/providers/open_meteo.py)

### Test Files Updated / Extended
1. [test_cpcb_calculator.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/tests/test_cpcb_calculator.py)
2. [test_api_routes.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/tests/test_api_routes.py)
3. [test_provider_normalization.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/tests/test_provider_normalization.py)
4. [test_provider_temporal_validation.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/tests/test_provider_temporal_validation.py)
5. [test_stage3_pipeline_and_api.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/tests/test_stage3_pipeline_and_api.py)

---

## 3. CPCB Interpolation Formula & Output Conversion Behavior

Frozen breakpoint tables in [cpcb_breakpoints.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/cpcb_breakpoints.py) remain unmodified. Inside `calculate_sub_index`:

1. **Input validation:** Rejects `None`, `bool`, non-numeric values, non-finite floats (`NaN`, `+Inf`, `-Inf`), negative concentrations, and unsupported pollutant codes (`valid=False`, `sub_index=None`).
2. **Upper-bound clamp:** If `conc > breakpoints[-1].c_high`, clamps directly to `sub_index = 500`, `category = "SEVERE"` without unintended extrapolation beyond AQI 500 or fallback to `breakpoints[0]`.
3. **Continuous bracket selection:**
   - First bracket ($C_p \le \text{bp}_0.\text{c\_high}$): $B_{LO} = \text{bp}_0.\text{c\_low}$, $B_{HI} = \text{bp}_0.\text{c\_high}$, $I_{LO} = \text{bp}_0.\text{i\_low}$ ($= 0 \le 50$), $I_{HI} = \text{bp}_0.\text{i\_high}$ ($= 50$).
   - Subsequent brackets $k \ge 1$ ($\text{bp}_{k-1}.\text{c\_high} < C_p \le \text{bp}_k.\text{c\_high}$): $B_{LO} = \text{bp}_{k-1}.\text{c\_high}$, $B_{HI} = \text{bp}_k.\text{c\_high}$, $I_{LO} = \text{bp}_k.\text{i\_low} - 1$ when $\text{bp}_k.\text{i\_low} > 50$ (producing `50, 100, 200, 300, 400`, preserving continuity per CPCB guidelines without modifying frozen table rows), and $I_{HI} = \text{bp}_k.\text{i\_high}$.
4. **Interpolation & Integer Conversion:**
   $$I_p = \frac{I_{HI} - I_{LO}}{B_{HI} - B_{LO}} \times (C_p - B_{LO}) + I_{LO}$$
   - `sub_index = max(0, min(500, int(round(ip))))` (Python `round` to nearest integer, matching CPCB integer reporting).
   - `category` and `color` are resolved consistently from the resulting integer `sub_index` via `_resolve_aqi_category(sub_index)` against `AQI_CATEGORIES` (`0-50 GOOD`, `51-100 SATISFACTORY`, `101-200 MODERATE`, `201-300 POOR`, `301-400 VERY_POOR`, `401-500 SEVERE`), guaranteeing category and integer index never contradict.
   - All composite outputs continue to carry `INDICATIVE_MODEL_INDEX` and `is_official_cpcb_station_aqi=False`.

---

## 4. Before / After Numerical Regression Examples

| Pollutant | Concentration | Before (Stage 3.1 Defect) | Continuous Interpolated $I_p$ | After (Stage 3.1.1 Fixed) |
| :--- | :---: | :--- | :---: | :--- |
| `pm25` | `30.5` µg/m³ | `51` (`GOOD` — fallback bug) | `50.8333...` | **`51` (`SATISFACTORY`)** |
| `pm25` | `60.5` µg/m³ | `101` (`GOOD` — fallback bug) | `101.6667...` | **`102` (`MODERATE`)** |
| `pm25` | `90.5` µg/m³ | `151` (`GOOD` — fallback bug) | `201.6667...` | **`202` (`POOR`)** |
| `pm25` | `120.5` µg/m³ | `201` (`GOOD` — fallback bug) | `300.3846...` | **`300` (`POOR`)** |
| `pm10` | `100.5` µg/m³ | `100` (`GOOD` — fallback bug) | `100.3333...` | **`100` (`SATISFACTORY`)** |
| `co` | `1.05` mg/m³ | `52` (`GOOD` — fallback bug) | `52.5000` | **`52` (`SATISFACTORY`)** |
| `co` | `2.05` mg/m³ | `102` (`GOOD` — fallback bug) | `100.6250` | **`101` (`MODERATE`)** |
| `o3` | `100.5` µg/m³ | `100` (`GOOD` — fallback bug) | `100.7353...` | **`101` (`MODERATE`)** |

---

## 5. Executed Test Commands & Results

1. **Full Backend Suite:**
   - Command: `cd backend; .\.venv\Scripts\pytest.exe tests -v --tb=short`
   - Result: **`123 passed, 0 failed, 0 skipped`** (`1` `StarletteDeprecationWarning`) in `7.00s`.
2. **Live Integration Subset:**
   - Command: `cd backend; .\.venv\Scripts\pytest.exe tests -k "live" -v`
   - Result: **`4 passed, 119 deselected`** in `5.06s`:
     - `tests/test_provider_normalization.py::test_live_provider_delhi_integration` — `PASSED`
     - `tests/test_provider_temporal_validation.py::test_live_provider_stage1_compatibility_delhi` — `PASSED`
     - `tests/test_stage3_pipeline_and_api.py::test_live_api_current_delhi` — `PASSED`
     - `tests/test_stage3_pipeline_and_api.py::test_live_api_compare_delhi_and_chennai` — `PASSED`
3. **Synthetic Unit & API Subset:**
   - Command: `cd backend; .\.venv\Scripts\pytest.exe tests -k "not live" -q`
   - Result: **`119 passed, 4 deselected`** in `2.80s`.
4. **Stage 1 Parity Cross-Check (`audit_stage3_1.py`):**
   - Result: `Rolling Window Numerical Mismatches: []`, `Rejected Interval Count Diffs (outside-window accounting): []`.

---

## 6. Live vs Synthetic Test Counts

| Test Category | Executed | Passed | Failed | Skipped |
| :--- | :---: | :---: | :---: | :---: |
| **Live Open-Meteo Integration Tests** (`-k "live"`) | 4 | 4 | 0 | 0 |
| **Synthetic Unit / API / Frozen Parity Tests** (`-k "not live"`) | 119 | 119 | 0 | 0 |
| **Total Backend Pytest Suite** | **123** | **123** | **0** | **0** |

---

## 7. Stage 1 Numerical Parity Results

Verified identically across **20 / 20** test cases (`TEST-01` through `TEST-20`) in both:
- `app.engine.rolling_window.integrate_rolling_window` (tested by `test_production_rolling_window_stage1_evidence_20_cases_and_sha256` and `audit_stage3_1.py`), and
- `app.validation.temporal_validation.integrate_stage1_window` (tested by `test_frozen_stage1_evidence_artifact_parity`).

Specific `LOW-01` alignment confirmed: `TEST-13` now yields `rejected_intervals_count == 1` (`supported_duration_seconds == 0.0`, `coverage_percentage == 0.0`, `integrated_concentration == 0.0`, `time_weighted_mean is None`), producing **0 mismatches** across all numerical outputs and interval counts.

---

## 8. Stage 1 SHA-256 Verification

Verified directly on disk:
- File: [stage1_test_evidence_v243.json](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/stage1_test_evidence_v243.json)
- Observed SHA-256: `D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773` (**EXACT MATCH**; unmodified in `git status`).
- [airaware_architecture_v2_4_3.md](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/airaware_architecture_v2_4_3.md), [cpcb_breakpoints.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/cpcb_breakpoints.py), and [indicative_index.py](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/backend/app/engine/indicative_index.py) remain untouched since Stage 3.1.

---

## 9. Stage 2.1 Evidence Integrity

Verified intact under [evidence/stage2/](file:///e:/sunny/OneDrive/Desktop/AirAware-AI/evidence/stage2):
- Files present and unmodified: `stage2_city_results.json` (3 cities: `delhi`, `mumbai`, `chennai`), `stage2_validation_summary.json` (recording `"stage_version": "Stage 2.1 (Temporal Classification Correction)"`, `"temporal_governance_separation_verified": "PASS"`, `"upstream_ecmwf_native_temporal_resolution": "UNKNOWN"`), `stage2_validation_report.md`, and `stage2_raw_responses/`.
- Stage 2.1 temporal governance tests (`5` synthetic + `1` live test in `test_provider_temporal_validation.py`) all passed.

---

## 10. Remaining Limitations

1. **In-memory single-process cache & rate limiter:** `TTLCache` and `SlidingWindowRateLimiter` are bounded and thread-safe per worker process; multi-worker deployments do not share cache entries or rate-limit counters across processes.
2. **Legacy `/api/v1/ai/chat` endpoint:** Intentionally disabled with HTTP `503 AssistantPendingStage32` so client-supplied context cannot bypass authority until Stage 3.2 backend-grounded orchestration is approved and implemented.
3. **Provider constraints:** CAMS Global in Open-Meteo continues to return `nh3` (`ammonia`) as unavailable over Indian coordinates; `native_temporal_resolution` remains `UNKNOWN_PENDING_VERIFICATION`; all outputs are `INDICATIVE_MODEL_INDEX`, not CPCB CAAQMS station readings.
4. **Rounded sub-index boundary behavior:** Under exact CPCB continuous interpolation + nearest-integer rounding (`int(round(ip))`), values just above `120` (e.g., `pm25 = 120.5 -> 300.3846 -> 300`) or `100` (`pm10 = 100.5 -> 100.3333 -> 100`) round down to `300` (`POOR`) and `100` (`SATISFACTORY`) respectively; `_resolve_aqi_category` guarantees integer sub-indices and categories always remain mutually consistent.
5. **Minor test warning:** `StarletteDeprecationWarning` remains from `starlette.testclient` (`pytest` dependency stack, non-blocking).

---

## 11. Git Diff Summary

Working tree remains uncommitted against `HEAD` (`766d048 docs: freeze Stage 1 architecture specification v2.4.3 with test evidence artifact`) covering Stage 2, Stage 2.1, Stage 3.1, and Stage 3.1.1:
- `git diff --stat` on tracked files: `23 files changed, 1766 insertions(+), 483 deletions(-)` (with `Stage 3.1.1` modifying the 14 production files and 5 test files listed in Section 2).
- `git diff --check`: exit code `0` (no whitespace/conflict markers).

---

## 12. Commit & Push Confirmation

- **No `git commit` was created.**
- **No `git push` was executed.**
- Stage 3.2 development has **NOT** been started.
