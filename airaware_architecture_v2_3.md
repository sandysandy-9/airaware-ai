# AirAware AI — Architecture Specification Version 2.3 (Final Validation)

**Document Version:** 2.3.0  
**Status:** Final Pre-Implementation Specification — Pending Approval  
**Parent Baseline:** v2.2 (Accepted)  
**Scope of Changes:** Rolling-average sufficiency rules, Open-Meteo provider metadata integration, freshness classification policy, safety invariant restatement, 10 new automated test cases, final implementation checklist, empirical validation assumptions.

> [!IMPORTANT]
> This document introduces **no new product features**. Every section corrects a methodological deficiency identified in v2.2 or formally restates a safety invariant that must survive implementation unchanged. No application code is written or approved in this document.

---

## Table of Contents

1. [Challenge Requirement Verification Matrix](#1-challenge-requirement-verification-matrix)
2. [Temporal Semantics — Unchanged from v2.2, Formally Restated](#2-temporal-semantics--unchanged-from-v22-formally-restated)
3. [Corrected Rolling-Average Sufficiency Rules](#3-corrected-rolling-average-sufficiency-rules)
4. [Open-Meteo Provider Metadata Integration](#4-open-meteo-provider-metadata-integration)
5. [Improved Freshness Classification Policy](#5-improved-freshness-classification-policy)
6. [Safety Invariant — Refuse-on-Insufficient-Data](#6-safety-invariant--refuse-on-insufficient-data)
7. [CPCB Methodology and INDICATIVE_MODEL_INDEX](#7-cpcb-methodology-and-indicative_model_index)
8. [Backend Trust Boundary](#8-backend-trust-boundary)
9. [System Architecture Diagram — Unchanged from v2.2](#9-system-architecture-diagram--unchanged-from-v22)
10. [Test Specification — New Cases (v2.3)](#10-test-specification--new-cases-v23)
11. [Final Implementation Checklist](#11-final-implementation-checklist)
12. [Assumptions Requiring Empirical Validation](#12-assumptions-requiring-empirical-validation)

---

## 1. Challenge Requirement Verification Matrix

Identical to v2.2. Reproduced here for self-containment.

```
[Tier 1: Challenge Requirements — Pending Verification against Official Hack2Skill Challenge 6 Statement]
  ├── [P-REQ-01] Location-specific air quality assessment
  ├── [P-REQ-02] Identification of key contributing air pollutants
  ├── [P-REQ-03] Interpretation and health significance of observed values
  ├── [P-REQ-04] Personalised, evidence-based precautionary guidance
  ├── [P-REQ-05] Comparative evaluation of air quality across locations
  ├── [P-REQ-06] Exploration of historical environmental patterns (where genuine records exist)
  ├── [P-REQ-07] Conversational natural-language interface for air quality inquiries
  └── [P-REQ-08] Transparent disclosure of data sources, observation timestamps, and reliability

[Tier 2: Engineering Architecture Decisions — Formulated by Our Engineering Team]
  ├── [ENG-DEC-01] Application of CPCB NAQI breakpoints to criteria pollutant concentrations
  ├── [ENG-DEC-02] Pollutant-specific averaging periods (24h for PM/gases; 8h for CO/O3)
  ├── [ENG-DEC-03] Separate documentation of station completeness rules vs. model processing assumptions
  ├── [ENG-DEC-04] Clear taxonomy: Physical Station Data vs. Modelled Atmospheric Grid Estimates
  ├── [ENG-DEC-05] Open-Meteo (Copernicus CAMS) as primary verified zero-config provider
  ├── [ENG-DEC-06] Deterministic health matrix linking CPCB/WHO advisories to activities & cohorts
  ├── [ENG-DEC-07] Strict backend trust boundary: Server-authoritative calculations; client context rejected
  └── [ENG-DEC-08] Rigorous temporal semantics (all 6 fields) + Open-Meteo provider metadata fields (5 fields)

[Tier 3: Additional Product Enhancements — Proposed by Our Team]
  ├── [PROP-FEAT-01] Client-side threshold alert manager with 3-hour deduplication window
  ├── [PROP-FEAT-02] Multi-city comparison warning on observation timestamp discrepancies
  ├── [PROP-FEAT-03] Interactive Recharts visualizer with statistical indicators (avg, peak, minimum)
  └── [PROP-FEAT-04] In-memory spatial TTL cache for rate-limiting protection with documented multi-worker limits
```

---

## 2. Temporal Semantics — Unchanged from v2.2, Formally Restated

The following six temporal fields defined in v2.2 are **unchanged**. They are restated here because v2.3 introduces provider-metadata fields that complement them, and both sets must be understood together.

### 2.1 The Six Temporal Fields

```
         model_issue_time         retrieval_time        valid_time (forecast example)
                │                        │                          │
                ▼                        ▼                          ▼
────────────────┼────────────────────────┼──────────────────────────┼──────────────► UTC
                │◄── model_run_age_h ───►│                          │
                │                        │◄── valid_time_offset_h ──►│  (positive = future)
                │◄──────────── forecast_lead_h ──────────────────────►│
```

| Field | Symbol | Formula | Null condition |
|---|---|---|---|
| `model_issue_time` | $T_{\text{issue}}$ | From provider metadata | Null if metadata unavailable |
| `valid_time` | $T_{\text{valid}}$ | From API hourly timestamp | Never null |
| `retrieval_time` | $T_{\text{retrieval}}$ | Wall-clock at response receipt | Never null |
| `model_run_age_hours` | $\Delta T_{\text{run}}$ | $(T_{\text{retrieval}} - T_{\text{issue}}) / 3600$ | Null if `model_issue_time` null |
| `forecast_lead_hours` | $\Delta T_{\text{lead}}$ | $(T_{\text{valid}} - T_{\text{issue}}) / 3600$ | Null if `model_issue_time` null |
| `valid_time_offset_hours` | $\Delta T_{\text{offset}}$ | $(T_{\text{valid}} - T_{\text{retrieval}}) / 3600$ | Never null |

**Rule:** If `model_issue_time` is unavailable from provider metadata, it is `null`. It is never estimated, inferred, or back-calculated from other fields.

### 2.2 Interpretation Conventions

- $\Delta T_{\text{offset}} > +0.5\text{ h}$: Future forecast step.
- $-0.5\text{ h} \le \Delta T_{\text{offset}} \le +0.5\text{ h}$: Approximately current atmospheric window.
- $\Delta T_{\text{offset}} < -0.5\text{ h}$: Historical model analysis.
- These are not categories returned to the client; they are inputs to the freshness classification defined in Section 5.

---

## 3. Corrected Rolling-Average Sufficiency Rules

> [!IMPORTANT]
> This section replaces the node-count-only rules stated in v2.2. The core correction is: **node counts alone do not prove adequate temporal coverage**. Two native 3-hour nodes at 03:00 and 06:00 span only 3 hours, not 8. Minimum coverage must be expressed in time-hours actually covered, not in nodes counted.

### 3.1 Why Node Counts Are Insufficient

CAMS Global native temporal resolution is nominally 3 hours. This means one model output exists per 3-hour interval. When eight such nodes are present (covering a 21-hour span, e.g. 00:00–21:00), computing a 24-hour rolling average is feasible with appropriate handling. However:

- **Two nodes at adjacent 3-hour positions (e.g. 03:00 and 06:00) together represent only the interval [03:00, 06:00] — a span of 3 hours.** Applying these two nodes to an 8-hour rolling-average calculation provides only 37.5% temporal coverage. This is not sufficient.
- **Node count** tells you how many data points exist. **Temporal span** tells you how much of the target window is actually covered. Only span determines sufficiency.

### 3.2 Formal Window Definitions

#### 3.2.1 24-Hour Rolling Window (PM2.5, PM10, NO₂, SO₂, NH₃)

```
Window start:  W_start = valid_time − 23h  (inclusive boundary)
Window end:    W_end   = valid_time         (inclusive boundary)
Window width:  24 hours
```

The window is left-inclusive and right-inclusive at both boundary timestamps.  
Example: for valid_time = 2024-03-15 14:00 UTC, window = [2024-03-15 14:00 UTC − 23h, 2024-03-15 14:00 UTC] = [2024-03-14 15:00 UTC, 2024-03-15 14:00 UTC].

#### 3.2.2 8-Hour Rolling Window (CO, O₃)

```
Window start:  W_start = valid_time − 7h   (inclusive boundary)
Window end:    W_end   = valid_time         (inclusive boundary)
Window width:  8 hours
```

Example: for valid_time = 2024-03-15 14:00 UTC, window = [2024-03-15 06:00 UTC, 2024-03-15 14:00 UTC].

### 3.3 Sample Collection Within Window

#### 3.3.1 Native Node Definition
A **native node** is a data point whose timestamp corresponds to a native model output time — that is, `timestamp mod temporal_resolution_seconds == 0` relative to the model's reference epoch. This is determined from the `temporal_resolution_seconds` field obtained from provider metadata (Section 4), not from a hardcoded assumption.

#### 3.3.2 Interpolated Value Definition
Any value returned by the API at a timestamp that is NOT a native node position is an **interpolated value**. It represents a provider-side interpolation between adjacent native nodes. It is not an independent model observation.

**Rule:** Interpolated values may be used in rolling-average calculations if and only if the native nodes that produced them are known to be within or adjacent to the window. Interpolated values are marked as `source: "interpolated"` in the data structure.

#### 3.3.3 Boundary Sample Handling

When a window boundary (W_start or W_end) falls between two native node timestamps:

1. Identify the two native nodes that bracket the boundary: $N_{\text{before}}$ (at $t_{\text{before}} \le W_{\text{boundary}}$) and $N_{\text{after}}$ (at $t_{\text{after}} > W_{\text{boundary}}$).
2. If both $N_{\text{before}}$ and $N_{\text{after}}$ exist and both have valid concentration values, **linear interpolation** may be applied to estimate a concentration at the exact boundary:

$$C_{\text{boundary}} = C_{\text{before}} + \frac{(W_{\text{boundary}} - t_{\text{before}})}{(t_{\text{after}} - t_{\text{before}})} \cdot (C_{\text{after}} - C_{\text{before}})$$

3. If either bracketing node is absent or invalid, the boundary is flagged as `BOUNDARY_UNRESOLVED`. The interval between the last known node and the boundary is treated as a gap.
4. Interpolated boundary values are marked `source: "boundary_interpolated"` and do not count as native nodes for coverage calculation.

### 3.4 Numerical Averaging Method

**Method: Uniform weighted mean of native-node concentration values within the window.**

Atmospheric pollutant concentrations are expressed as mass-per-volume ($\mu g/m^3$) or parts-per-billion (ppb). They are **not rates** (not flux, not cumulative quantities). Therefore:

- **Do not use the trapezoidal rule**. The trapezoidal rule is appropriate for integrating a rate over time (e.g., cumulative dose). It is not appropriate for computing a time-mean concentration from discrete point samples.
- Use arithmetic mean: $\bar{C} = \frac{1}{N} \sum_{i=1}^{N} C_{t_i}$ where $C_{t_i}$ are the concentration values of native nodes within the window.
- If a boundary interpolation was performed, the boundary value may be included as an additional data point (marked `source: "boundary_interpolated"`). Its weight is equal to any native node.

**Documentation requirement:** The implementation must log, for every rolling-average calculation:
- Number of native nodes used.
- Number of interpolated boundary values used.
- Total temporal span covered.
- Averaging method applied.
- Resulting concentration and sufficiency verdict.

### 3.5 Temporal Coverage Calculation

Temporal coverage is computed as the **sum of durations attributable to present nodes**, not simply node count × resolution.

#### 3.5.1 Coverage Accounting Algorithm

```
For each present node at timestamp t_i within [W_start, W_end]:
  - Left boundary of this node's interval:  max(t_i - (resolution/2), W_start)
  - Right boundary of this node's interval: min(t_i + (resolution/2), W_end)
  - If left boundary < right boundary: add (right - left) to covered_seconds

coverage_fraction = covered_seconds / window_width_seconds
```

Where `resolution` is `temporal_resolution_seconds` from provider metadata.

> [!NOTE]
> This half-interval attribution algorithm assigns each node responsibility for half the gap before it and half the gap after it. It is a standard Voronoi-style decomposition appropriate for uniformly sampled series. For irregular spacing, use the actual midpoints between adjacent nodes.

#### 3.5.2 Sufficiency Thresholds

| Averaging period | Window width | Min temporal coverage | Min coverage fraction | Min native nodes that can achieve this |
|---|---|---|---|---|
| 24-hour | 24h (86400s) | ≥ 18h (64800s) | ≥ 75% | ≥ 6 of 8 nominal nodes |
| 8-hour | 8h (28800s) | ≥ 7h (25200s) | ≥ 87.5% | ≥ 3 of 3 nominal nodes spanning ≥ 7h |

**Critical 8-hour rule:** If two 3-hourly nodes are present (e.g. at 03:00 and 06:00 UTC for a window ending at 10:00 UTC), their attributed coverage spans only 3 hours (1.5h + 1.5h around the two nodes, clipped to window boundaries). Coverage fraction = 3h/8h = 37.5%. This is below the 87.5% threshold. Status: `INSUFFICIENT_DATA`.

#### 3.5.3 Return Values

If coverage_fraction ≥ threshold:
```json
{
  "status": "SUFFICIENT",
  "coverage_fraction": 0.875,
  "covered_hours": 7.0,
  "nodes_used": 3,
  "rolling_average_ugm3": 42.7,
  "averaging_method": "arithmetic_mean_native_nodes",
  "boundary_interpolations": 0
}
```

If coverage_fraction < threshold:
```json
{
  "status": "INSUFFICIENT_DATA",
  "reason": "TEMPORAL_COVERAGE_BELOW_THRESHOLD",
  "coverage_fraction": 0.375,
  "covered_hours": 3.0,
  "nodes_used": 2,
  "required_coverage_fraction": 0.875,
  "rolling_average_ugm3": null
}
```

### 3.6 Missing Interval Handling

A **gap** exists when a native-node timestamp within the window is absent (no data returned) or carries a null/NaN concentration value.

| Gap scenario | Action |
|---|---|
| Single missing native node, coverage still above threshold | Proceed; document gap in coverage accounting |
| Multiple missing nodes, coverage above threshold | Proceed; document all gaps |
| Total coverage falls below threshold | Return `INSUFFICIENT_DATA` with `reason: "GAPS_EXCEED_TOLERANCE"` |
| Entire window absent | Return `INSUFFICIENT_DATA` with `reason: "NO_DATA_IN_WINDOW"` |
| Provider returns NaN or negative value | Treat as absent; do not substitute zero |

**Rule:** Never fill gaps by carrying forward the last known value (LOCF) or by any zero-order hold. This would fabricate environmental readings. If a gap exists and coverage is still sufficient, only native nodes and valid boundary interpolations are averaged; the gap intervals contribute zero to the coverage sum.

### 3.7 Irregular Interval Handling

Provider data may arrive with irregular timestamps due to API behavior, caching, or latency.

```
Detection: If any consecutive pair (t_i, t_{i+1}) satisfies:
  abs((t_{i+1} - t_i) - temporal_resolution_seconds) > 60 seconds
Then: flag the series as IRREGULAR_SAMPLING

If IRREGULAR_SAMPLING:
  - Use actual midpoints between consecutive nodes for coverage calculation
    (instead of fixed resolution/2 intervals)
  - Log the irregularity and all timestamp differences
  - Apply the same coverage threshold
  - If timestamps are duplicated (t_i == t_{i+1}): deduplicate, keep first value
```

---

## 4. Open-Meteo Provider Metadata Integration

> [!IMPORTANT]
> The v2.2 specification assumed a hardcoded 3-hour native resolution. This section replaces that assumption with a requirement to read actual provider metadata from the Open-Meteo API response. If metadata is unavailable, the resolution value must be `null` and the rolling-average engine must refuse to proceed.

### 4.1 Open-Meteo Metadata Fields

Open-Meteo exposes model metadata in its API response under the top-level key structure documented at https://open-meteo.com/en/docs. The following fields are relevant:

| Metadata field | JSON path in Open-Meteo response | Description |
|---|---|---|
| `last_run_initialisation_time` | To be verified against live API response | UTC timestamp of the most recent model run initialization |
| `last_run_modification_time` | To be verified against live API response | UTC timestamp of last modification to the model run data |
| `last_run_availability_time` | To be verified against live API response | UTC timestamp when this model run's data became available via API |
| `temporal_resolution_seconds` | To be verified against live API response | Native temporal resolution of the model in seconds |
| `update_interval_seconds` | To be verified against live API response | Expected interval between successive model run updates |

> [!WARNING]
> The exact JSON keys and paths for these metadata fields **must be empirically verified** against a live Open-Meteo API response before implementation begins. The names above are taken from Open-Meteo's public documentation, but field availability, naming, and nesting may differ between model types (CAMS Global vs. CAMS European vs. ERA5). See Section 12 for empirical validation requirements.

### 4.2 Metadata Capture and Mapping

```
Open-Meteo API Response
└── [metadata object — path TBD from live response]
    ├── last_run_initialisation_time  → model_issue_time (maps to Temporal Semantics field §2.1)
    ├── last_run_modification_time    → provider_metadata.last_modification_time
    ├── last_run_availability_time    → provider_metadata.last_availability_time
    ├── temporal_resolution_seconds   → provider_metadata.temporal_resolution_seconds
    └── update_interval_seconds       → provider_metadata.update_interval_seconds
```

**Mapping rule:** `last_run_initialisation_time` is the primary source for `model_issue_time` (the $T_{\text{issue}}$ field in §2.1). If `last_run_initialisation_time` is unavailable, `model_issue_time` is `null`.

### 4.3 Resolution Taxonomy — Four Distinct Concepts

The implementation must clearly distinguish:

| Concept | Symbol | Description | Source |
|---|---|---|---|
| Native model resolution | $R_{\text{native}}$ | Actual time step between independent NWP solver outputs | `temporal_resolution_seconds` from metadata |
| API-returned resolution | $R_{\text{API}}$ | Timestamp granularity of the API response array | Observed from response timestamps |
| Interpolated values | — | Values at timestamps not aligned to native nodes | Flagged when $R_{\text{API}} < R_{\text{native}}$ |
| Independently generated values | — | Model outputs at native-node positions | Present when timestamp % $R_{\text{native}}$ == 0 |

**Rule:** When the Open-Meteo API returns hourly values but `temporal_resolution_seconds` = 10800 (3 hours), the implementation must classify:
- Timestamps at 00:00, 03:00, 06:00, … → `source: "native_model_output"`
- Timestamps at 01:00, 02:00, 04:00, … → `source: "interpolated_by_provider"`

**Rule:** Interpolated values may be used in the averaging calculation (§3.4) but are marked distinctly. They do not increase the native-node count or the coverage calculation beyond their attributed interval.

### 4.4 Metadata Unavailability Protocol

If the Open-Meteo API response does not include any of the metadata fields:

```
provider_metadata = {
  "temporal_resolution_seconds": null,
  "update_interval_seconds": null,
  "last_run_initialisation_time": null,
  "last_run_modification_time": null,
  "last_run_availability_time": null,
  "metadata_available": false,
  "metadata_unavailable_reason": "FIELD_ABSENT_FROM_API_RESPONSE"
}
```

**Consequence on rolling average:** If `temporal_resolution_seconds` is `null`, the engine cannot classify native vs. interpolated nodes. Status: `INSUFFICIENT_DATA` with `reason: "PROVIDER_RESOLUTION_UNKNOWN"`. The rolling-average calculation must not proceed with an assumed resolution.

**Consequence on freshness classification:** If `last_run_availability_time` or `update_interval_seconds` is `null`, the freshness classification falls back to the model-run-age-only path defined in §5.4.

### 4.5 Documentation of CAMS Global Spatial Characteristics

The following must appear in every API response that returns CAMS-derived data:

```json
{
  "data_source_note": {
    "provider": "Open-Meteo (Copernicus CAMS Global)",
    "data_type": "MODELLED_ATMOSPHERIC_GRID_ESTIMATE",
    "index_type": "INDICATIVE_MODEL_INDEX",
    "not_a_monitoring_station": true,
    "spatial_resolution_degrees": "0.4° × 0.4° (approx. 44 km at equator) — verify from metadata",
    "applies_cpcb_breakpoints_to_model_data": true,
    "cpcb_breakpoints_disclaimer": "CPCB NAQI breakpoints are designed for physical monitoring station measurements with defined averaging-period completeness rules. Applying them to model-derived concentrations produces an INDICATIVE_MODEL_INDEX. This is not an official CPCB station AQI.",
    "historical_note": "Model archive data represents past model analysis fields, not measured observations from physical instruments."
  }
}
```

---

## 5. Improved Freshness Classification Policy

> [!IMPORTANT]
> The v2.2 specification used a provisional 20-hour threshold for `STALE_MODEL_RUN`. This section replaces that hardcoded threshold with a metadata-driven policy. The 20-hour value survives only as a **last-resort fallback** when provider metadata is unavailable.

### 5.1 Four Independent Freshness Dimensions

Freshness is multi-dimensional. No single number can represent it. The implementation exposes all four dimensions independently:

| Dimension | Field | Description |
|---|---|---|
| Model run age | `model_run_age_hours` | How long ago the model simulation was computed |
| Time since data became available | `hours_since_availability` | How long this model run's output has been accessible |
| Forecast lead time | `forecast_lead_hours` | How far ahead from model init the valid_time represents |
| Valid-time offset | `valid_time_offset_hours` | Whether the valid_time is past, present, or future relative to now |

### 5.2 Primary Classification Algorithm (Metadata Available)

**Step 1 — Compute expected availability of a newer cycle:**

```
expected_next_available = last_run_availability_time + update_interval_seconds
grace_period            = 1800 seconds (30 minutes, to allow for delivery delays)
newer_cycle_overdue     = (retrieval_time > expected_next_available + grace_period)
```

**Step 2 — Compute hours since this run became available:**

```
hours_since_availability = (retrieval_time - last_run_availability_time) / 3600
```

**Step 3 — Classify model_run_freshness:**

```
If newer_cycle_overdue == True:
  model_run_freshness = "POTENTIALLY_SUPERSEDED"
  reason = "A newer model cycle was expected by {expected_next_available} but data 
            still reflects run initialized at {model_issue_time}"
Elif hours_since_availability < (update_interval_seconds / 3600):
  model_run_freshness = "CURRENT_CYCLE"
Else:
  model_run_freshness = "AGING_CYCLE"
  reason = "Data is from a cycle {hours_since_availability:.1f}h old; 
            update interval is {update_interval_seconds/3600:.1f}h"
```

**Step 4 — Classify valid_time_type:**

```
If valid_time_offset_hours > +0.5:
  valid_time_type = "FORECAST_ESTIMATE"
Elif valid_time_offset_hours >= -0.5:
  valid_time_type = "CURRENT_ESTIMATE"
Else:
  valid_time_type = "HISTORICAL_ANALYSIS"
```

**Step 5 — Compose overall freshness:**

```
freshness = {
  "model_run_freshness":    <from Step 3>,
  "valid_time_type":        <from Step 4>,
  "model_run_age_hours":    <from §2.1>,
  "hours_since_availability": <from Step 2>,
  "forecast_lead_hours":    <from §2.1>,
  "valid_time_offset_hours": <from §2.1>,
  "newer_cycle_overdue":    <from Step 1>,
  "expected_next_cycle_at": <expected_next_available as ISO-8601>,
  "classification_basis":   "PROVIDER_METADATA"
}
```

### 5.3 Interaction Between Dimensions

Both `model_run_freshness` and `valid_time_type` can carry independently significant values simultaneously. The safety invariant (§6) evaluates them together:

| model_run_freshness | valid_time_type | Recommendation permitted? |
|---|---|---|
| `CURRENT_CYCLE` | `CURRENT_ESTIMATE` | YES (ideal case) |
| `CURRENT_CYCLE` | `FORECAST_ESTIMATE` | YES — clearly label as forecast |
| `CURRENT_CYCLE` | `HISTORICAL_ANALYSIS` | YES — clearly label as past analysis |
| `AGING_CYCLE` | `CURRENT_ESTIMATE` | YES — display aging warning |
| `AGING_CYCLE` | `FORECAST_ESTIMATE` | YES — display both labels |
| `POTENTIALLY_SUPERSEDED` | any | CONDITIONAL — see §6 |
| any | any (data missing) | NO — `INSUFFICIENT_DATA` |

### 5.4 Fallback Classification (Metadata Unavailable)

When `last_run_availability_time` or `update_interval_seconds` is null:

```
If model_run_age_hours is null:
  freshness.classification_basis = "NO_METADATA"
  freshness.model_run_freshness  = "UNKNOWN_RUN_AGE"
  recommendation_permitted       = False
  reason = "Cannot determine model run age; metadata unavailable"

Elif model_run_age_hours <= 12:
  freshness.model_run_freshness  = "PRESUMED_CURRENT"
  freshness.classification_basis = "FALLBACK_RUN_AGE_ONLY"
  recommendation_permitted       = True (with warning)

Elif model_run_age_hours <= 20:
  freshness.model_run_freshness  = "PRESUMED_AGING"
  freshness.classification_basis = "FALLBACK_RUN_AGE_ONLY"
  recommendation_permitted       = True (with aging warning)

Else:  # model_run_age_hours > 20
  freshness.model_run_freshness  = "PRESUMED_STALE"
  freshness.classification_basis = "FALLBACK_RUN_AGE_ONLY"
  recommendation_permitted       = False
  reason = "Model run age exceeds 20h fallback threshold and metadata unavailable 
            to verify currency"
```

> [!NOTE]
> The 20-hour threshold in the fallback path is a **provisional policy value**. It has not been validated against actual Open-Meteo CAMS update behavior. When empirical validation is conducted (§12), this value must be replaced with the observed actual update interval.

### 5.5 Labels Prohibited in API Responses

The following labels must never appear in a production API response:

| Prohibited label | Reason |
|---|---|
| `"LIVE"` | Implies physical real-time sensor measurement; CAMS is a model |
| `"Real-time station reading"` | CAMS provides grid-point model estimates |
| `"Official CPCB AQI"` | Requires physical station compliance chain |
| `"Measured observation"` | Implies physical instrument; model data is not measured |
| Freshness label derived solely from retrieval time | Retrieval time says nothing about data age |

---

## 6. Safety Invariant — Refuse-on-Insufficient-Data

> [!CAUTION]
> This invariant is permanent. It may not be relaxed, bypassed, or made configurable. If data is unavailable or insufficient for any of the conditions below, the recommendation engine must return a clear unavailable-data state rather than generating health recommendations.

### 6.1 Conditions That Block Recommendations

```
BLOCK recommendation if ANY of the following:

A. TEMPORAL COVERAGE INSUFFICIENT
   - rolling_average_status == "INSUFFICIENT_DATA" for any required pollutant
   - Applies to: PM2.5, PM10 (require 24h average), CO, O3 (require 8h average)

B. REQUIRED POLLUTANT MISSING
   - PM2.5 or PM10 is absent (at least one must be present for CPCB-style index)
   - If PM2.5 and PM10 both absent: BLOCK

C. MODEL DATA EXCEEDS FRESHNESS POLICY
   - Fallback path: model_run_age_hours > 20 AND metadata unavailable
   - Metadata path: newer_cycle_overdue AND hours_since_availability > (update_interval_seconds × 2.0)

D. PROVIDER METADATA RESOLUTION UNKNOWN
   - temporal_resolution_seconds == null
   - Cannot classify native vs. interpolated nodes

E. ALL PROVIDER DATA UNAVAILABLE
   - HTTP error from provider (5xx), timeout, or empty response
   - Downstream: return HTTP 503 with structured error body

F. EXPLICITLY STALE VALID TIME
   - valid_time is more than 48 hours in the past relative to retrieval_time
   - i.e., valid_time_offset_hours < -48
```

### 6.2 Blocked Response Structure

When any block condition is met:

```json
{
  "recommendation_status": "UNAVAILABLE",
  "reason_code": "INSUFFICIENT_DATA | MISSING_POLLUTANT | STALE_DATA | RESOLUTION_UNKNOWN | PROVIDER_UNAVAILABLE | STALE_VALID_TIME",
  "reason_detail": "Human-readable explanation of why recommendations cannot be generated",
  "data_snapshot": {
    "valid_time": "<ISO-8601 or null>",
    "retrieval_time": "<ISO-8601>",
    "model_run_age_hours": "<float or null>",
    "coverage_fraction": "<float or null>",
    "blocking_conditions_met": ["<list of condition codes>"]
  },
  "recommendations": null
}
```

### 6.3 AI Chat Safety

When the AI chat module is invoked and block conditions are met:

- The grounding context passed to the LLM must include the block status and reason.
- The LLM system prompt must instruct the model to acknowledge the data gap and not substitute general health advice as if it were location-specific air-quality guidance.
- The deterministic fallback must generate a data-gap response (not a health recommendation) explaining why location-specific guidance is currently unavailable.

---

## 7. CPCB Methodology and INDICATIVE_MODEL_INDEX

### 7.1 Formal Designation

Every index value computed by AirAware AI from CAMS-derived concentrations carries the designation: **`INDICATIVE_MODEL_INDEX`**.

This designation is permanent and non-negotiable. It reflects the following factual conditions:

1. CPCB NAQI breakpoints are defined for concentration measurements from certified physical monitoring stations following a specific sampling protocol.
2. CAMS provides model-derived atmospheric chemistry fields at 0.4° × 0.4° spatial resolution.
3. CAMS does not follow, and is not required to follow, CPCB's minimum data sufficiency rules (16-hour data requirement, minimum three pollutants including PM2.5 or PM10).
4. Applying CPCB breakpoints to CAMS data produces an index that uses CPCB numerics but cannot claim CPCB station compliance.
5. The result is an indicative model-derived index suitable for general guidance; it is not an official CPCB station AQI.

### 7.2 Sub-Index Calculation (Unchanged from v2.2)

For each applicable pollutant where a valid rolling average has been computed:

```
sub_index_p = AQI_lo + ((AQI_hi - AQI_lo) / (C_hi - C_lo)) × (C_avg - C_lo)

Where:
  C_avg = rolling average concentration (24h or 8h) from §3
  [C_lo, C_hi] = CPCB concentration breakpoint bracket containing C_avg
  [AQI_lo, AQI_hi] = corresponding CPCB AQI sub-index bracket
```

**Composite index:**
```
INDICATIVE_MODEL_INDEX = max(sub_index_p for all pollutants p with valid rolling averages)
```

**Dominant pollutant:** The pollutant p that produced the maximum sub-index.

### 7.3 Minimum Pollutant Requirement

```
If count(pollutants with valid rolling average) < 3: return INSUFFICIENT_DATA
If (PM2.5 valid average) == False AND (PM10 valid average) == False: return INSUFFICIENT_DATA
```

This mirrors the spirit of CPCB's requirement without claiming CPCB station compliance. The requirement is documented as an engineering quality control rule, not as a claimed CPCB regulatory compliance assertion.

---

## 8. Backend Trust Boundary

This section is unchanged from v2.2. Restated for completeness.

### 8.1 Authoritative Computation Chain

```
Client Request → Backend Validates Location → Backend Fetches from Provider
              → Backend Computes Rolling Averages → Backend Computes Sub-Indices
              → Backend Computes INDICATIVE_MODEL_INDEX → Backend Derives Recommendations
              → Backend Returns Full Structured Response
              → Client Displays Result (no computation)
```

### 8.2 Client Context Rejection

The backend must **reject** as authoritative any of the following values when received from the client:

- `aqi` or `aqi_value` — recalculate from raw concentrations
- `aqi_category` — reclassify from calculated index
- `dominant_pollutant` — reidentify from sub-index comparison
- Any pre-computed risk score
- Any freshness label generated client-side

**Rule for `/api/v1/recommendations` endpoint:** Accept location identifiers (lat/lon or location string) as the only inputs relevant to data retrieval. All environmental context must be fetched and computed by the server.

### 8.3 AI Context Trust

LLM-generated text must never override a computed environmental value. The LLM receives a read-only structured grounding context. It cannot modify index values, override freshness classifications, or lift block conditions.

---

## 9. System Architecture Diagram — Unchanged from v2.2

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         AirAware AI — System Architecture                       │
└─────────────────────────────────────────────────────────────────────────────────┘

[Browser Client]
   └── Next.js Frontend (React, Tailwind, Recharts)
         ├── Display only — no AQI computation
         ├── Shows INDICATIVE_MODEL_INDEX badge
         ├── Shows all 6 temporal fields + 5 provider metadata fields
         └── HTTPS/REST → Backend API

[Backend — FastAPI / Python 3.11]
   ├── API Layer (routes)
   │   ├── POST /api/v1/air-quality      ← accepts lat/lon only
   │   ├── POST /api/v1/recommendations  ← accepts lat/lon only; rejects client AQI
   │   ├── POST /api/v1/compare          ← accepts list of lat/lon pairs
   │   ├── GET  /api/v1/historical       ← accepts lat/lon + date range
   │   └── POST /api/v1/chat             ← accepts user message + session_id
   │
   ├── Domain Layer
   │   ├── RollingAverageEngine          ← §3 implementation
   │   ├── CPCBBreakpoints               ← 8-pollutant breakpoint table
   │   ├── SubIndexCalculator            ← §7.2 implementation
   │   ├── IndicativeModelIndex          ← §7 composite + minimum pollutant check
   │   ├── RecommendationEngine          ← deterministic health matrix
   │   └── SafetyInvariantGuard          ← §6 block condition checker
   │
   ├── Provider Layer
   │   ├── providers/modelled/
   │   │   └── open_meteo_cams.py        ← §4 metadata capture + §3 rolling window
   │   └── providers/measured/           ← Documented architecture; adapters pending tokens
   │       ├── waqi_adapter.py           [NOT ACTIVE without user-supplied API token]
   │       └── ogd_adapter.py            [NOT ACTIVE]
   │
   ├── Service Layer
   │   ├── CacheService                  ← TTL cache (5 min AQ, 10 min comparison)
   │   ├── AIService                     ← Gemini grounding; deterministic fallback
   │   └── FreshnessClassifier           ← §5 metadata-driven + fallback algorithm
   │
   └── Schema Layer (Pydantic v2)
       ├── AirQualityResponse            ← includes all 6 temporal + 5 metadata fields
       ├── RollingAverageResult          ← includes status, coverage_fraction, nodes_used
       ├── FreshnessClassification       ← all 4 dimensions from §5.1
       └── RecommendationResponse        ← UNAVAILABLE structure from §6.2

[External Services]
   ├── Open-Meteo CAMS API (verified, zero-config) ← Primary provider
   └── Google Gemini API (optional AI enhancement)
```

---

## 10. Test Specification — New Cases (v2.3)

All test cases below are specifications. They define **what** must be tested and **what result** the implementation must produce. They do not contain implementation code.

**Test file location:** `backend/tests/test_temporal_semantics.py` (new file, to be created)

---

### TEST-01: `test_two_node_insufficient_8h_window`

**Purpose:** Verify that two native nodes spanning only 3 hours are correctly rejected for an 8-hour rolling average.

**Setup:**
```
window:            [06:00 UTC, 14:00 UTC]  (8h, CO measurement for valid_time 14:00)
temporal_resolution_seconds: 10800 (3h)
provider nodes available: [{"t": "09:00", "co_ppb": 1.2}, {"t": "12:00", "co_ppb": 1.4}]
```

**Coverage calculation:**
- Node at 09:00: left=max(09:00−1.5h, 06:00)=07:30, right=min(09:00+1.5h, 14:00)=10:30 → 3h
- Node at 12:00: left=10:30, right=min(13:30, 14:00)=13:30 → 3h
- covered = 6h, window = 8h, fraction = 75%

**Expected result:** `status: "INSUFFICIENT_DATA"`, `reason: "TEMPORAL_COVERAGE_BELOW_THRESHOLD"`, `coverage_fraction: 0.75`, `required_coverage_fraction: 0.875`

> [!NOTE]
> This corrects the erroneous v2.2 claim that two nodes are "sufficient for an 8-hour average." 75% < 87.5% threshold for 8h window.

---

### TEST-02: `test_complete_24h_window`

**Purpose:** Confirm that 8 native nodes covering the full 24-hour window produces a successful average.

**Setup:**
```
window: [2024-03-14 15:00 UTC, 2024-03-15 15:00 UTC]  (valid_time = 15:00)
temporal_resolution_seconds: 10800 (3h)
nodes: 8 nodes at 15:00, 18:00, 21:00, 00:00, 03:00, 06:00, 09:00, 12:00
       all with pm25_ugm3 values: [45, 52, 61, 58, 44, 39, 42, 48]
```

**Expected result:** `status: "SUFFICIENT"`, `coverage_fraction: 1.0`, `nodes_used: 8`, `rolling_average_ugm3: 48.625` (arithmetic mean of 8 values)

---

### TEST-03: `test_incomplete_24h_window_above_threshold`

**Purpose:** Verify 6 of 8 nodes (75% coverage) is accepted for a 24-hour PM2.5 average.

**Setup:**
```
Same window as TEST-02; nodes at 03:00 and 06:00 are absent (null).
Remaining 6 nodes: [45, 52, 61, 58, 42, 48]
```

**Coverage:** 6 nodes × 3h attribution each = 18h covered = 75% of 24h = meets threshold.

**Expected result:** `status: "SUFFICIENT"`, `coverage_fraction: 0.75`, `nodes_used: 6`, `rolling_average_ugm3: 51.0`

---

### TEST-04: `test_incomplete_24h_window_below_threshold`

**Purpose:** Verify that 5 of 8 nodes (coverage < 75%) is rejected.

**Setup:**
```
Same window as TEST-02; nodes at 03:00, 06:00, and 09:00 are absent.
Remaining 5 nodes: [45, 52, 61, 58, 48]
```

**Coverage:** 5 × 3h = 15h = 62.5% < 75% threshold.

**Expected result:** `status: "INSUFFICIENT_DATA"`, `reason: "TEMPORAL_COVERAGE_BELOW_THRESHOLD"`, `coverage_fraction: 0.625`, `required_coverage_fraction: 0.75`, `rolling_average_ugm3: null`

---

### TEST-05: `test_boundary_interpolation_applied`

**Purpose:** Verify that linear interpolation is correctly applied when the window boundary falls between native nodes.

**Setup:**
```
window: [2024-03-15 06:00 UTC, 2024-03-16 06:00 UTC]  (24h, non-round-hour boundary)
Native nodes near W_start (06:00 UTC): 
  node at 05:00: pm25=40.0 (1h before boundary) — wait, 3h resolution means:
  Revise: nodes at 03:00 (pm25=40.0) and 06:00 (pm25=46.0) bracket W_start=06:00
  W_start = 06:00 is exactly on a node — no interpolation needed in this sub-case.
  
Sub-case: W_start = 06:30 UTC (non-aligned):
  node at 06:00: pm25=46.0, node at 09:00: pm25=52.0
  boundary_value = 46.0 + ((06:30−06:00)/(09:00−06:00)) × (52.0−46.0) = 46.0 + (0.5/3)×6 = 47.0
  source: "boundary_interpolated"
```

**Expected result:**
- Boundary value = 47.0 µg/m³ tagged `source: "boundary_interpolated"`
- Included in average calculation
- `boundary_interpolations: 1` in result metadata

---

### TEST-06: `test_missing_samples_irregular_intervals`

**Purpose:** Verify that irregular timestamp gaps are detected, logged, and handled without crashing or silently corrupting the average.

**Setup:**
```
Nodes received (PM2.5, 24h window):
  [00:00: 50, 03:30: 48, 07:00: 55, 10:00: 61, 13:00: 58, 16:00: 45, 19:00: 42, 22:00: 49]
  Gaps between: 3.5h, 3.5h, 3h, 3h, 3h, 3h, 3h — irregular
```

**Expected result:**
- `irregular_sampling_detected: true`
- Coverage calculated using actual midpoints between consecutive nodes
- `status: "SUFFICIENT"` if total coverage ≥ 18h, else `"INSUFFICIENT_DATA"`
- Timestamps and gaps logged in `sampling_irregularities` array

---

### TEST-07: `test_dynamic_provider_temporal_resolution`

**Purpose:** Verify that the engine reads `temporal_resolution_seconds` from provider metadata and does not assume 10800 (3h).

**Setup:**
```
Scenario A: metadata returns temporal_resolution_seconds = 10800
  → Nodes at 00:00, 03:00, 06:00 are native
  → Node at 01:00 is classified "interpolated_by_provider"

Scenario B: metadata returns temporal_resolution_seconds = 3600 (hypothetical hourly model)
  → All hourly nodes are native
  → Different coverage calculation applies

Scenario C: metadata returns temporal_resolution_seconds = null
  → Engine must refuse to classify nodes
  → Return INSUFFICIENT_DATA with reason: PROVIDER_RESOLUTION_UNKNOWN
```

**Expected result:** Each scenario produces the correct classification without hardcoded resolution assumptions.

---

### TEST-08: `test_model_availability_vs_initialization`

**Purpose:** Verify that `last_run_availability_time` ≠ `model_issue_time` and that both are captured and exposed independently.

**Setup:**
```
Provider metadata:
  last_run_initialisation_time: 2024-03-15 00:00 UTC  → model_issue_time
  last_run_availability_time:   2024-03-15 06:30 UTC  → provider_metadata.last_availability_time
  (6.5h gap represents model run + post-processing + API publication delay)
retrieval_time:                 2024-03-15 08:00 UTC
```

**Expected result:**
```json
{
  "model_issue_time": "2024-03-15T00:00:00Z",
  "provider_metadata": {
    "last_run_availability_time": "2024-03-15T06:30:00Z"
  },
  "model_run_age_hours": 8.0,
  "hours_since_availability": 1.5
}
```
Both fields present, independently valued. `model_run_age_hours` ≠ `hours_since_availability`.

---

### TEST-09: `test_delayed_model_update_flagged`

**Purpose:** Verify that when retrieval_time exceeds expected_next_available + grace_period, the response is flagged as `POTENTIALLY_SUPERSEDED`.

**Setup:**
```
last_run_availability_time: 2024-03-15 06:30 UTC
update_interval_seconds:    43200  (12h)
expected_next_available:    2024-03-15 18:30 UTC
grace_period:               1800s (30 min)
retrieval_time:             2024-03-15 20:00 UTC  (1h past grace period)
```

**Expected result:**
```json
{
  "freshness": {
    "model_run_freshness": "POTENTIALLY_SUPERSEDED",
    "newer_cycle_overdue": true,
    "expected_next_cycle_at": "2024-03-15T18:30:00Z",
    "classification_basis": "PROVIDER_METADATA"
  }
}
```
Recommendation permitted: CONDITIONAL (per §5.3 table — depends on `hours_since_availability`).

---

### TEST-10: `test_old_cycle_future_forecast_dual_classification`

**Purpose:** Verify that an old model run with a future valid_time correctly receives both `POTENTIALLY_SUPERSEDED` and `FORECAST_ESTIMATE` simultaneously.

**Setup:**
```
model_issue_time:           2024-03-14 00:00 UTC  (>24h ago)
valid_time:                 2024-03-15 18:00 UTC  (future)
retrieval_time:             2024-03-15 10:00 UTC
update_interval_seconds:    43200 (12h)
last_run_availability_time: 2024-03-14 06:30 UTC
expected_next_available:    2024-03-14 18:30 UTC  (long past)
model_run_age_hours:        34.0
valid_time_offset_hours:    +8.0
hours_since_availability:   27.5
```

**Expected result:**
```json
{
  "freshness": {
    "model_run_freshness": "POTENTIALLY_SUPERSEDED",
    "valid_time_type": "FORECAST_ESTIMATE",
    "model_run_age_hours": 34.0,
    "forecast_lead_hours": 42.0,
    "valid_time_offset_hours": 8.0,
    "newer_cycle_overdue": true,
    "classification_basis": "PROVIDER_METADATA"
  }
}
```

**Recommendation status:** `UNAVAILABLE` — `hours_since_availability` (27.5h) > `update_interval_seconds/3600 × 2.0` (24.0h): block condition C met.

---

## 11. Final Implementation Checklist

This checklist defines every code change that must be made before the application can be considered v2.3-compliant. Each item references the section of this document that governs it.

### 11.1 Backend — Provider Layer

- [ ] **`app/providers/open_meteo.py`** — Rewrite to v2.3 specification:
  - [ ] Fetch provider metadata fields: `temporal_resolution_seconds`, `update_interval_seconds`, `last_run_initialisation_time`, `last_run_modification_time`, `last_run_availability_time` (§4.1)
  - [ ] Handle metadata unavailability gracefully with null fields (§4.4)
  - [ ] Classify each API data point as `native_model_output` or `interpolated_by_provider` based on `temporal_resolution_seconds` (§4.3)
  - [ ] Feed classified nodes to `RollingAverageEngine` rather than using single hourly values (§3)
  - [ ] Populate all 6 temporal fields: `model_issue_time`, `valid_time`, `retrieval_time`, `model_run_age_hours`, `forecast_lead_hours`, `valid_time_offset_hours` (§2.1)
  - [ ] Add `data_source_note` block to every response (§4.5)

- [ ] **`app/providers/base.py`** — Add abstract methods for metadata retrieval; ensure measured vs. modelled taxonomy is enforced (§9 architecture diagram)

### 11.2 Backend — Domain Layer (new directory or rename of `engine/`)

- [ ] **`app/domain/rolling_average.py`** — New module implementing §3 exactly:
  - [ ] Window definition (§3.2): exact start/end boundaries per pollutant type
  - [ ] Node classification using `temporal_resolution_seconds` from metadata (§3.3.1)
  - [ ] Boundary sample handling and linear interpolation (§3.3.3)
  - [ ] Arithmetic mean numerical method — not trapezoidal (§3.4)
  - [ ] Voronoi/half-interval coverage algorithm (§3.5.1)
  - [ ] Sufficiency thresholds: 75% for 24h, 87.5% for 8h (§3.5.2)
  - [ ] Irregular interval detection and midpoint-based coverage (§3.6 / §3.7)
  - [ ] `INSUFFICIENT_DATA` return for all failure modes with reason codes (§3.5.3)

- [ ] **`app/domain/safety_guard.py`** — New module implementing §6.1 block conditions A–F:
  - [ ] All six block conditions checked before recommendation generation
  - [ ] Blocked response structure (§6.2) returned when any condition met
  - [ ] AI chat grounding context updated with block status (§6.3)

- [ ] **`app/domain/freshness.py`** — New module implementing §5:
  - [ ] Primary algorithm using provider metadata (§5.2)
  - [ ] Fallback algorithm using model_run_age_hours only (§5.4)
  - [ ] All four freshness dimensions exposed (§5.1)
  - [ ] Prohibited labels enforced — no "LIVE", "Real-time station reading" (§5.5)

- [ ] **`app/domain/indicative_index.py`** — Rename/refactor of `cpcb_calculator.py`:
  - [ ] Accept rolling averages from `rolling_average.py`, not raw hourly values
  - [ ] Minimum pollutant validation (§7.3)
  - [ ] `INDICATIVE_MODEL_INDEX` designation on every output (§7.1)

### 11.3 Backend — Schema Layer

- [ ] **`app/schemas/air_quality.py`** — Add/update fields:
  - [ ] All 6 temporal fields (§2.1) — `model_issue_time` nullable
  - [ ] 5 provider metadata fields in nested `ProviderMetadata` schema (§4.1)
  - [ ] `data_type: Literal["MODELLED_ATMOSPHERIC_GRID_ESTIMATE"]` (§4.5)
  - [ ] `index_type: Literal["INDICATIVE_MODEL_INDEX"]` (§7.1)
  - [ ] `RollingAverageResult` schema: status, coverage_fraction, nodes_used, boundary_interpolations (§3.5.3)
  - [ ] `FreshnessClassification` schema: all 4 dimensions + classification_basis (§5.1)

- [ ] **`app/schemas/recommendation.py`** — Add `RecommendationUnavailable` schema per §6.2

### 11.4 Backend — API Layer

- [ ] **`app/api/routes_recommendations.py`** — Remove all client-supplied AQI fields from request schema; derive from server-computed rolling averages + sub-indices only (§8.2)
- [ ] **`app/api/routes_air_quality.py`** — Validate that only location identifiers (lat/lon or location string) are accepted as environmental-data inputs (§8.1)
- [ ] **`app/api/routes_ai.py`** — Build LLM grounding context server-side from verified data; block condition state must be included in context; LLM must not override computed values (§8.3)

### 11.5 Backend — Tests

- [ ] **`backend/tests/test_temporal_semantics.py`** — New file; implement all 10 test cases from §10 exactly
- [ ] **`backend/tests/test_cpcb_calculator.py`** — Update to pass rolling averages rather than hourly values to calculator
- [ ] **`backend/tests/test_api_routes.py`** — Add tests verifying that client-supplied AQI fields are rejected (§8.2)
- [ ] Confirm all tests pass with `uv run pytest --offline --no-sync` where possible, `BypassSandbox: true` for async-dependent API tests

### 11.6 Frontend

- [ ] **`src/app/page.tsx`** — Remove any client-side AQI computation or passing of `aqi`/`dominant_pollutant` to backend recommendation endpoint (§8.2)
- [ ] **`src/components/AQIGauge.tsx`** (or equivalent) — Add `INDICATIVE_MODEL_INDEX` badge; display index type, not "AQI" (§7.1)
- [ ] **`src/lib/types.ts`** — Align TypeScript types with updated backend schemas: all 6 temporal fields, 5 metadata fields, freshness object, `UNAVAILABLE` recommendation state
- [ ] **`src/components/`** — Display `freshness.model_run_freshness` and `freshness.valid_time_type` in the data source disclosure panel
- [ ] **`src/components/`** — Display `data_source_note` prominently for every location card

### 11.7 Documentation

- [ ] `README.md` — Update with v2.3 architecture summary; include INDICATIVE_MODEL_INDEX disclaimer
- [ ] `airaware_architecture_v2_3.md` — Commit to workspace root (this document)
- [ ] `METHODOLOGY.md` (new file) — Detailed explanation of rolling-average approach, temporal semantics, and freshness policy for end users

---

## 12. Assumptions Requiring Empirical Validation

The following assumptions are **stated as facts** in the codebase or would need to be to implement the system. Each must be validated against real API behavior before the production deployment.

| # | Assumption | Why it matters | Validation method |
|---|---|---|---|
| A1 | Open-Meteo CAMS response includes `last_run_initialisation_time` at the JSON path assumed | Used for `model_issue_time` (§4.1); if absent, all dependent fields are null | Make a live API call to `/v1/air-quality?models=cams_global&...`; inspect raw JSON for metadata keys |
| A2 | Open-Meteo CAMS response includes `last_run_availability_time` | Used for freshness classification (§5.2); if absent, fallback path applies | Same live API call; check for field presence |
| A3 | `temporal_resolution_seconds` is returned by Open-Meteo for CAMS Global | Drives native-vs-interpolated node classification (§4.3) | Same live API call; note actual value |
| A4 | `update_interval_seconds` is returned by Open-Meteo for CAMS Global | Drives `expected_next_available` calculation (§5.2); if absent, fallback applies | Same live API call |
| A5 | CAMS Global native resolution is 3h (10800s) | §3 coverage arithmetic; determines how many native nodes per window | Verify from `temporal_resolution_seconds` in live response AND from ECMWF CAMS documentation |
| A6 | The CAMS Global model runs approximately every 12h | Governs provisional fallback threshold choice (§5.4) | Check Open-Meteo documentation and `update_interval_seconds` from live response |
| A7 | 20-hour fallback threshold for `PRESUMED_STALE` adequately represents actual update behavior | §5.4 fallback; if model runs every 12h, 20h may already be two missed cycles | Empirically observe model run availability over 72h; replace 20h with actual `update_interval_seconds × 1.5` |
| A8 | Open-Meteo hourly API output for CAMS is provider-side linear interpolation between 3h native nodes | §4.3 classification of `interpolated_by_provider`; if Open-Meteo uses a different method, label changes | Review Open-Meteo source/documentation for interpolation method; note in METHODOLOGY.md |
| A9 | CPCB breakpoints in `cpcb_breakpoints.py` match the most recent published CPCB NAQI table | §7.2 sub-index calculation; outdated breakpoints produce incorrect index values | Compare implementation table to current CPCB NAQI guidelines (CPCB 2014/2023 revision); document version |
| A10 | The 87.5% coverage threshold for 8h windows is an appropriate engineering threshold | §3.5.2; too strict → frequent INSUFFICIENT_DATA; too lenient → poor quality estimates | Review against available literature on data sufficiency for rolling averages; may need expert domain input |
| A11 | 75% coverage threshold for 24h windows is appropriate | Same as A10 | Same validation approach |
| A12 | Linear interpolation is appropriate for boundary samples | §3.3.3; if concentration changes non-linearly at boundaries, linear interpolation introduces error | Acceptable for now given CAMS's smooth spatial/temporal fields; flag as known limitation |
| A13 | Arithmetic mean (not time-weighted mean) is appropriate for rolling-average calculation | §3.4; if native nodes are irregular, uniform arithmetic mean underweights denser intervals | For nominal 3h uniform spacing, arithmetic mean = time-weighted mean; for irregular spacing (§3.7), midpoint-based coverage serves as a proxy weight |
| A14 | Gemini API is accessible during hackathon judging | AI recommendation enhancement depends on this; deterministic fallback exists | Verify API key validity; test with quota at expected request rate |
| A15 | Open-Meteo CAMS provides PM2.5, PM10, NO₂, SO₂, CO, O₃, and NH₃ for the requested coordinates | §7.3 minimum pollutant requirement; if NH₃ unavailable, sub-index count may fall below 3 | Test with Indian urban coordinates; note which pollutants are returned |

---

## Document End

**Version:** 2.3.0  
**Status:** Awaiting implementation approval  
**Author:** AirAware AI Engineering Team  
**Parent:** airaware_architecture_v2_2.md (accepted baseline)  
**Next step:** Upon approval, proceed with implementation in priority order per §11.

> [!CAUTION]
> Do not begin implementation until this document is formally approved. The existing application code (committed at git hash `0110c9c`) is non-compliant with v2.1–v2.3 requirements in multiple critical areas documented in §11. All listed items in §11 must be addressed before the application can be considered architecture-compliant.
