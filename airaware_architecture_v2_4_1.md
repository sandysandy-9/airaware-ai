# AirAware AI — Architecture Specification Version 2.4.1 (Stage 1 Mathematical and Safety Specification)

**Document Version:** 2.4.1  
**Status:** Stage 1 Mathematical and Provider Baseline — Pending Review & Authorization  
**Parent Baseline:** v2.4 (Conditional Acceptance)  
**Date:** 24 November 2026  
**Target Milestone:** Hack2Skill Challenge 6 Submission (Deadline: 29 November 2026, 11:59 PM IST)  

> [!IMPORTANT]
> **Stage 1 Implementation Boundary:** This document establishes the exact mathematical integration formulas, test expectations, and provider verification requirements. In strict adherence to Stage 1 execution rules, **no application source code, API routes, or databases have been modified**. Implementation will commence only after Stage 1 authorization.

---

## Table of Contents

1. [Provisional Challenge Objectives vs. Engineering Decisions](#1-provisional-challenge-objectives-vs-engineering-decisions)
2. [Mathematical Methodology: Piecewise-Linear Trapezoidal Integration](#2-mathematical-methodology-piecewise-linear-trapezoidal-integration)
3. [Exact Duration Rolling Windows & Boundary Handling](#3-exact-duration-rolling-windows--boundary-handling)
4. [Maximum Supported Gap ($G_{\max}$) Engineering Rationale](#4-maximum-supported-gap-g_max-engineering-rationale)
5. [Complete Mathematical Verification Suite (20 Tests with Exact Values)](#5-complete-mathematical-verification-suite-20-tests-with-exact-values)
6. [Provider Verification Report & Temporal Resolution Semantics](#6-provider-verification-report--temporal-resolution-semantics)
7. [CPCB Regulatory Distinction & INDICATIVE_MODEL_INDEX](#7-cpcb-regulatory-distinction--indicative_model_index)
8. [Reconciled Pollutant Safety & Recommendation Invariants](#8-reconciled-pollutant-safety--recommendation-invariants)
9. [Assumptions, Limitations & Unresolved Questions](#9-assumptions-limitations--unresolved-questions)
10. [Stage 1 Acceptance Checklist & Verdict](#10-stage-1-acceptance-checklist--verdict)

---

## 1. Provisional Challenge Objectives vs. Engineering Decisions

To ensure absolute transparency and auditability, project requirements are strictly partitioned into three distinct tiers.

### 1.1 Provisional Challenge Objectives — Pending Official Verification (Tier 1)

> [!WARNING]
> The official Hack2Skill Challenge 6 problem statement document has **not been provided as an independent external source file** in this workspace. The objectives below are provisional representations derived from the user's Master Engineering Prompt. They are not claimed to be externally verified.

- **[PROV-REQ-01] Location-Specific Air Quality Assessment:** Present location-specific atmospheric air quality without fabricated or mock data.
- **[PROV-REQ-02] Contributing Pollutant Identification:** Identify which criteria pollutants (PM2.5, PM10, NO₂, SO₂, CO, O₃) are primary drivers of poor air quality.
- **[PROV-REQ-03] Health Significance & Interpretation:** Translate raw concentrations and sub-indices into understandable health impacts.
- **[PROV-REQ-04] Personalised Actionable Precautionary Guidance:** Deliver evidence-based, tailored precautions based on user activity, vulnerability cohort, and exposure duration.
- **[PROV-REQ-05] Cross-Location Comparison:** Enable side-by-side air quality evaluation across multiple monitored locations.
- **[PROV-REQ-06] Historical Pattern Exploration:** Explore genuine multi-day historical atmospheric trends where genuine data exists.
- **[PROV-REQ-07] Conversational Natural-Language Assistance:** Provide a conversational interface with strictly grounded responses, preventing hallucinations and operating deterministically offline.
- **[PROV-REQ-08] Provenance, Observation Times & Reliability:** Disclose data sources, observation timestamps, model grid coordinates, and data reliability metrics.

### 1.2 Engineering Architecture Decisions — Formulated by Engineering Team (Tier 2)

- **[ENG-DEC-01] Indicative Model Index:** Applying CPCB NAQI linear breakpoints to atmospheric model grid data, permanently labeled as `INDICATIVE_MODEL_INDEX` (never an official station AQI).
- **[ENG-DEC-02] Pollutant-Specific Duration Windows:** Exact 24-hour duration for PM2.5, PM10, NO₂, SO₂; exact 8-hour duration for CO, O₃.
- **[ENG-DEC-03] Gap-Aware Trapezoidal Time Integration:** Replacing flawed Voronoi coverage with continuous piecewise-linear trapezoidal integration; enforcing exact identity between supported integration duration and coverage duration.
- **[ENG-DEC-04] Configurable Maximum Supported Gap ($G_{\max} = 14400\text{s}$):** Gaps exceeding $G_{\max}$ remain completely uncovered and contribute zero duration and zero concentration.
- **[ENG-DEC-05] Server-Authoritative Trust Boundary:** Complete rejection of client-supplied AQI, category overrides, or precomputed risk scores.
- **[ENG-DEC-06] Rigorous Temporal Semantics & Null Metadata Preservation:** Exposing 6 distinct temporal fields; preserving `model_issue_time = null` when upstream API metadata is absent.

### 1.3 Proposed Product Enhancements (Tier 3)

- **[PROP-FEAT-01] Client-Side Threshold Alerts:** User-configured AQI alerts with a 3-hour deduplication window to prevent notification fatigue.
- **[PROP-FEAT-02] Multi-City Comparison Discrepancy Warnings:** Automated alerts when comparing cities with mismatched observation times or data age.
- **[PROP-FEAT-03] Historical Summary Indicators:** Period average, peak concentration, and cleanest recorded hour metrics.
- **[PROP-FEAT-04] In-Memory Spatial TTL Cache:** Rate-limiting mitigation with documented single-worker concurrency semantics.

---

## 2. Mathematical Methodology: Piecewise-Linear Trapezoidal Integration

### 2.1 Flaw in Previous Voronoi Nearest-Neighbour Attribution

In architecture versions 2.3 and 2.4, Voronoi cell attribution was proposed. Under Voronoi attribution, when an intermediate sample was missing, the Voronoi cells of the adjacent samples expanded across the gap to meet at the midpoint. This had fatal mathematical flaws:
1. **Silent Gap Inflation:** Missing data intervals were silently assigned the concentration of neighbouring samples, violating the strict data integrity rule against fabricating or assuming environmental readings across unmonitored intervals.
2. **Inconsistency with Continuous Time-Series:** Air pollutant concentration is a continuous scalar field varying smoothly over time, not a discrete step function. Expanding a discrete point across a multi-hour missing interval fabricates data.

### 2.2 Piecewise-Linear Trapezoidal Integration Formulation

Let the target rolling window be $[W_s, W_e]$ with total duration:
$$T_W = W_e - W_s \quad (\text{seconds})$$

Let the validated, timestamp-ordered sequence of samples be:
$$(t_1, C_1), (t_2, C_2), \dots, (t_M, C_M) \quad \text{where } t_1 < t_2 < \dots < t_M \text{ and } C_k \ge 0$$

For each adjacent pair of samples $(t_i, C_i)$ and $(t_{i+1}, C_{i+1})$, the raw sample interval is $[t_i, t_{i+1}]$ with duration:
$$\Delta t_i = t_{i+1} - t_i$$

#### Interval Acceptance Criteria
An interval $[t_i, t_{i+1}]$ is **ACCEPTED** if and only if ALL of the following hold:
1. **Sample Validity:** Both $C_i$ and $C_{i+1}$ are non-null, non-NaN, and $\ge 0$.
2. **Temporal Order:** $t_i < t_{i+1}$ (strictly monotonic, no duplicates).
3. **Maximum Gap Limit:** $\Delta t_i \le G_{\max}$ (where $G_{\max}$ is the configured maximum supported gap, e.g., 14,400s = 4h).
4. **Window Intersection:** $\max(t_i, W_s) < \min(t_{i+1}, W_e)$ (interval strictly intersects $[W_s, W_e]$).

If $\Delta t_i > G_{\max}$, the entire interval $(t_i, t_{i+1})$ is **REJECTED**. It contributes **zero supported duration** and **zero concentration integral**. It remains completely uncovered.

#### Interval Clipping and Boundary Interpolation
Each accepted interval is clipped to the window boundaries:
$$a_i = \max(t_i, W_s), \quad b_i = \min(t_{i+1}, W_e)$$
$$\Delta \tau_i = b_i - a_i \quad (\text{clipped duration, } \Delta \tau_i > 0)$$

The concentration field $C(t)$ across $[t_i, t_{i+1}]$ is modelled piecewise-linearly:
$$C(t) = C_i + \frac{t - t_i}{t_{i+1} - t_i} (C_{i+1} - C_i)$$

The concentrations at the clipped boundaries $a_i$ and $b_i$ are:
$$C(a_i) = C_i + \frac{a_i - t_i}{t_{i+1} - t_i} (C_{i+1} - C_i)$$
$$C(b_i) = C_i + \frac{b_i - t_i}{t_{i+1} - t_i} (C_{i+1} - C_i)$$

> [!NOTE]
> Boundary interpolation occurs **only** when $a_i = W_s > t_i$ or $b_i = W_e < t_{i+1}$. Because this interval has already passed the criterion $\Delta t_i \le G_{\max}$, boundary interpolation is mathematically permitted if and only if valid bracketing samples exist within the maximum supported gap. If no valid bracketing sample exists outside the window within $G_{\max}$, the boundary interval remains uncovered.

#### Mathematical Integration Formula
The integrated concentration over clipped interval $i$ is the exact trapezoidal integral:
$$I_i = \int_{a_i}^{b_i} C(t) \, dt = \left( \frac{C(a_i) + C(b_i)}{2} \right) \cdot \Delta \tau_i$$

#### Aggregation and Exact Mathematical Identity
The system computes:
1. **Total Supported Duration:**
   $$D_{\text{supported}} = \sum_{i \in \text{accepted}} \Delta \tau_i$$
2. **Total Integrated Concentration:**
   $$I_{\text{total}} = \sum_{i \in \text{accepted}} I_i$$
3. **Coverage Percentage:**
   $$\text{Coverage \%} = \left( \frac{D_{\text{supported}}}{T_W} \right) \times 100\%$$
4. **Time-Weighted Mean Concentration ($\bar{C}$):**
   $$\bar{C} = \frac{I_{\text{total}}}{D_{\text{supported}}} = \frac{\sum_{i \in \text{accepted}} \left( \frac{C(a_i) + C(b_i)}{2} \right) \Delta \tau_i}{\sum_{i \in \text{accepted}} \Delta \tau_i}$$

> [!IMPORTANT]
> **Exact Identity Guarantee:** Notice that $\sum \Delta \tau_i$ is **simultaneously** the denominator of the time-weighted mean and the numerator of the coverage percentage. The supported intervals for coverage and averaging are mathematically identical. There is zero mismatch between coverage accounting and numerical weighting.

---

## 3. Exact Duration Rolling Windows & Boundary Handling

### 3.1 24-Hour Duration Window (PM2.5, PM10, NO₂, SO₂)
For target valid time $T_{\text{valid}}$:
$$W_s = T_{\text{valid}} - 24\text{ hours} = T_{\text{valid}} - 86400\text{ seconds}$$
$$W_e = T_{\text{valid}}$$
$$T_{W, 24\text{h}} = W_e - W_s = 86400.0\text{ seconds (exactly 24.0 hours)}$$

Both endpoints $W_s$ and $W_e$ are closed boundaries $[W_s, W_e]$.

### 3.2 8-Hour Duration Window (CO, O₃)
For target valid time $T_{\text{valid}}$:
$$W_s = T_{\text{valid}} - 8\text{ hours} = T_{\text{valid}} - 28800\text{ seconds}$$
$$W_e = T_{\text{valid}}$$
$$T_{W, 8\text{h}} = W_e - W_s = 28800.0\text{ seconds (exactly 8.0 hours)}$$

### 3.3 Runtime Duration Assertions
The engine must execute runtime assertions prior to processing:
```python
assert (window_end - window_start).total_seconds() in (86400.0, 28800.0), \
    f"Window duration {(window_end - window_start).total_seconds()}s is not an exact 24h or 8h period"
```

---

## 4. Maximum Supported Gap ($G_{\max}$) Engineering Rationale

### 4.1 Status: Configurable Engineering Proposal
$G_{\max}$ is an **internal engineering design parameter**, not an upstream provider service level agreement. It is configurable via `AIRAWARE_MAX_SUPPORTED_GAP_SECONDS` (default: 14400s = 4.0 hours).

### 4.2 Technical Rationale
1. **ECMWF CAMS Native Temporal Resolution:** CAMS Global numerical chemical transport models run on native 3-hourly time steps ($\Delta t_{\text{native}} = 10800\text{s}$). Under nominal conditions, consecutive native model outputs are spaced exactly 3 hours apart.
2. **Tolerance for Timestamp Alignment ($+1\text{ hour}$):** An additional 1-hour margin ($10800\text{s} + 3600\text{s} = 14400\text{s} = 4\text{ hours}$) accommodates API hourly resampling, minor solar-time coordinate shifts, or sub-hourly grid timestamp offsets.
3. **Rejection of Missed Cycles:** If even a single native 3-hour model output is missing, the gap between adjacent available points becomes at least $3\text{h} + 3\text{h} = 6\text{ hours}$ ($21600\text{s}$). Because $21600\text{s} > 14400\text{s}$, a single missing native node **automatically fails the $G_{\max}$ check and is rejected**. This guarantees that missing model runs are never interpolated across.

---

## 5. Complete Mathematical Verification Suite (20 Tests with Exact Values)

The table below presents the independently verified mathematical results for all 20 required test cases, executed using the exact piecewise-linear trapezoidal algorithm with $G_{\max} = 14400\text{s}$ (4h).

- **24h Window:** $[W_s, W_e] = [2026-11-23\text{T}14:00:00\text{Z}, 2026-11-24\text{T}14:00:00\text{Z}]$, $T_W = 86400\text{s}$.
- **8h Window:** $[W_s, W_e] = [2026-11-24\text{T}06:00:00\text{Z}, 2026-11-24\text{T}14:00:00\text{Z}]$, $T_W = 28800\text{s}$.

| Test ID | Test Scenario | Input Description | Accepted Intervals | Rejected Intervals & Reason | $D_{\text{supported}}$ | Coverage % | Total Integral ($I_{\text{total}}$) | Time-Weighted Mean ($\bar{C}$) |
|---|---|---|---|---|---|---|---|---|
| **TEST-01** | Constant concentration | 25 hourly samples (0h to 24h), all $C = 50.0$ | 24 intervals of 1h | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-02** | Linear concentration increase | 25 hourly samples, $C(h) = 20.0 + 2.0h$ ($20 \to 68$) | 24 intervals of 1h | 0 | 86,400s (24h) | **100.0%** | 3,801,600.0 | **44.0000** |
| **TEST-03** | Linear concentration decrease | 25 hourly samples, $C(h) = 100.0 - 3.0h$ ($100 \to 28$) | 24 intervals of 1h | 0 | 86,400s (24h) | **100.0%** | 5,529,600.0 | **64.0000** |
| **TEST-04** | Irregular hourly intervals | 10 samples at irregular hours (0, 1.5, 3, 7, 9, 12, 15, 18, 21.5, 24), $C(h) = 30 + 2h$ | 9 intervals (durations 1.5h to 4h) | 0 (all gaps $\le 4\text{h}$) | 86,400s (24h) | **100.0%** | 4,665,600.0 | **54.0000** |
| **TEST-05** | Missing one sample | 3-hourly samples (0h to 24h); sample at 9h missing | 6 intervals of 3h: [0,3], [3,6], [12,15], [15,18], [18,21], [21,24] | 1 interval: [6h, 12h] gap=6h (21600s) $> G_{\max}$ | 64,800s (18h) | **75.0%** | 3,159,000.0 | **48.7500** |
| **TEST-06** | Multiple consecutive missing samples | Hourly samples; hours 10, 11, 12, 13 missing | 19 intervals of 1h | 1 interval: [9h, 14h] gap=5h (18000s) $> G_{\max}$ | 68,400s (19h) | **79.2%** | 3,420,000.0 | **50.0000** |
| **TEST-07** | Gap exactly equal to $G_{\max}$ | Samples at 0h, 4h, 8h, 9h..24h; gap [4h, 8h] = 14400s | 18 intervals (including [4h, 8h] of 4h) | 0 ($\Delta t \le G_{\max}$) | 86,400s (24h) | **100.0%** | 4,492,800.0 | **52.0000** |
| **TEST-08** | Gap just greater than $G_{\max}$ | Samples at 0h, 4h, 8h+1s, 24h; gap [4h, 8h+1s] = 14401s | 1 interval: [0h, 4h] | 2 intervals: [4h, 8h+1s] (14401s $> G_{\max}$) and [8h+1s, 24h] (57599s $> G_{\max}$) | 14,400s (4h) | **16.7%** | 576,000.0 | **40.0000** |
| **TEST-09** | Missing first boundary sample | Samples start at 2h to 24h every 2h; no sample at 0h | 11 intervals of 2h | 0 inside series; [0h, 2h] has no bracketing sample to left | 79,200s (22h) | **91.7%** | 4,197,600.0 | **53.0000** |
| **TEST-10** | Missing last boundary sample | Samples from 0h to 22h every 2h; no sample at 24h | 11 intervals of 2h | 0 inside series; [22h, 24h] has no bracketing sample to right | 79,200s (22h) | **91.7%** | 3,088,800.0 | **39.0000** |
| **TEST-11** | Both boundaries interpolated | Samples at -1h (C=30), +2h (C=60); 2h..22h; +25h (C=100) | 12 intervals (clipped [0h, 2h] with $C_{0\text{h}}=40$; clipped [22h, 24h] with $C_{24\text{h}}=90$) | 0 (all raw gaps 3h $\le G_{\max}$) | 86,400s (24h) | **100.0%** | 5,616,000.0 | **65.0000** |
| **TEST-12** | Sample exactly at each boundary | 3-hourly samples from 0h to 24h; exact matches at 0h and 24h | 8 intervals of 3h | 0 | 86,400s (24h) | **100.0%** | 6,393,600.0 | **74.0000** |
| **TEST-13** | Zero coverage | Only 2 samples at -10h and -8h; none inside or near window | 0 | 1 interval: [-10h, -8h] does not intersect window | **0s (0h)** | **0.0%** | 0.0 | **None** |
| **TEST-14** | Partial coverage (50%) | Hourly samples from 0h to 12h ($C=60$); none from 12h to 24h | 12 intervals of 1h | 0 inside series; [12h, 24h] completely unmonitored | 43,200s (12h) | **50.0%** | 2,592,000.0 | **60.0000** |
| **TEST-15** | Complete coverage | 2-hourly samples from 0h to 24h ($C=45+h$) | 12 intervals of 2h | 0 | 86,400s (24h) | **100.0%** | 4,924,800.0 | **57.0000** |
| **TEST-16** | Duplicate timestamps | 2h spacing, but duplicate sample at 2h ($C=50.0$ and $C=55.0$) | 12 intervals (duplicate detected and resolved) | 0 intervals rejected | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-17** | Out-of-order timestamps | 2h spacing samples supplied in scrambled order | 12 intervals (order normalized by pipeline) | 0 intervals rejected | 86,400s (24h) | **100.0%** | 4,492,800.0 | **52.0000** |
| **TEST-18** | Invalid & negative values | 2h spacing; hour 6 has $C=-15.0$, hour 12 has $C=\text{None}$ | 10 intervals (gaps [4h,8h] and [10h,14h] are 4h $\le G_{\max}$) | 0 intervals rejected (gaps bridge valid points within $G_{\max}$) | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-19** | Exact 24-hour window | 25 hourly samples from 0h to 24h ($C=48.0$) | 24 intervals of 1h | 0 | 86,400s (24h) | **100.0%** | 4,147,200.0 | **48.0000** |
| **TEST-20** | Exact 8-hour window | 9 hourly samples from 06:00 to 14:00 ($C=1.0 \to 2.6\text{ mg/m}^3$) | 8 intervals of 1h | 0 | 28,800s (8h) | **100.0%** | 51,840.0 | **1.8000** |

---

## 6. Provider Verification Report & Temporal Resolution Semantics

### 6.1 Distinguishing Temporal Concepts

To prevent misleading claims, the implementation must maintain strict separation between four distinct temporal concepts:

| Concept | Definition | Observed Upstream Behavior |
|---|---|---|
| **API Output Timestamp Frequency** | The time delta between consecutive timestamp strings returned in the JSON array. | **1 hour (3600 seconds)**. The API returns hourly steps (`"2026-11-24T00:00"`, `"2026-11-24T01:00"`). |
| **Native Model Surface-Field Resolution** | The physical time step at which the underlying numerical fluid dynamics / chemical transport differential equations are solved. | Documented by ECMWF CAMS as **3-hourly (10800 seconds)**. Hourly API values are provider-interpolated, not independent physical observations. |
| **Model Initialization Time ($T_{\text{issue}}$)** | The base UTC reference time when the operational numerical simulation cycle was initialized (e.g., 00:00 UTC or 12:00 UTC run). | **ABSENT from JSON response body**. Preserved strictly as `null`. Never inferred from API timestamps or modulo math. |
| **Model Update Interval** | The frequency at which the provider ingests new forecast cycles (e.g., 12 hours). | **ABSENT from JSON response body**. The system falls back to the transparent `NO_METADATA_AVAILABLE` classification. |

### 6.2 Empirical Evidence Summary (Live Open-Meteo Query, 24 Nov 2026)
- **Target Coordinates Tested:** Delhi (`28.6139°N, 77.2090°E`).
- **Snapped Coordinates Returned:** `28.6000°N, 77.2000°E` (geodesic snap distance $\approx 1.5\text{ km}$, consistent with 0.4° model grid).
- **Available Pollutants:** PM2.5 ($\mu\text{g/m}^3$), PM10 ($\mu\text{g/m}^3$), NO₂ ($\mu\text{g/m}^3$), SO₂ ($\mu\text{g/m}^3$), CO ($\mu\text{g/m}^3$), O₃ ($\mu\text{g/m}^3$).
- **CO Unit Confirmation:** CO is returned in **$\mu\text{g/m}^3$**, requiring division by 1,000.0 to match CPCB's $\text{mg/m}^3$ breakpoints.
- **Ammonia ($\text{NH}_3$) Confirmation:** The `ammonia` array was **empty / null**. The engine must explicitly record $\text{NH}_3$ as `"unavailable_pollutants": ["NH3"]` and never substitute zero.

### 6.3 Historical Query Strategy for Rolling Window Coverage
To compute an exact 24-hour rolling window at valid time $T_{\text{valid}}$:
1. Window start is $W_s = T_{\text{valid}} - 24\text{ hours}$.
2. In order to allow boundary interpolation at $W_s$, the query must retrieve at least one valid sample prior to $W_s$ ($t < W_s$).
3. In order to allow boundary interpolation at $W_e = T_{\text{valid}}$, the query must retrieve at least one sample at or after $W_e$ ($t \ge W_e$).
4. **API Parameter Specification:** The provider adapter must query with `past_days=2` (retrieving up to 48 hours of historical model analysis) and `forecast_days=1` (retrieving up to 24 hours of forecast steps). This guarantees full bracketing of both 24h and 8h windows.

---

## 7. CPCB Regulatory Distinction & INDICATIVE_MODEL_INDEX

> [!IMPORTANT]
> **Strict Legal and Regulatory Demarcation:**
> - **Official CPCB NAQI Compliance:** Requires certified continuous ambient air quality monitoring stations (CAAQMS), physical gravimetric / optical particulate monitors, wet chemical gas analyzers, defined 16-hour data completeness rules per 24-hour cycle, and regulatory calibration audits.
> - **AirAware AI INDICATIVE_MODEL_INDEX:** Applies CPCB numerical breakpoint formulas to model-derived atmospheric chemistry fields. It represents a **modelled atmospheric estimate**, not a regulatory measurement.
> - Every API response, UI component, and documentation page must display the designation: **`INDICATIVE_MODEL_INDEX`** with the mandatory disclaimer:
>   > *"Indicative model-derived estimate calculated using CPCB NAQI breakpoints applied to Copernicus CAMS atmospheric grid simulations. This is not an official Central Pollution Control Board physical monitoring station measurement."*

### Minimum Pollutant Requirements for Indicative Index
1. At least 3 distinct pollutants must have valid, sufficiently covered rolling averages.
2. At least one particulate matter pollutant (PM2.5 or PM10) must be valid and sufficiently covered.
3. If these conditions fail, the composite index returns `status: "INSUFFICIENT_DATA"` with explicit reasons.

---

## 8. Reconciled Pollutant Safety & Recommendation Invariants

### 8.1 Independent Three-Tier Evaluation
1. **Tier A — Composite Index:** Evaluated strictly under the 3-pollutant + 1-PM rule.
2. **Tier B — Pollutant-Specific Interpretation:** Pollutants with sufficient data are explained; missing pollutants (e.g. $\text{NH}_3$) are explicitly marked unavailable.
3. **Tier C — Activity Recommendations:** Evaluated per rule. Each rule declares:
   - `required_pollutants`: Missing any required pollutant blocks the rule (status: `UNAVAILABLE`).
   - `optional_pollutants`: Missing optional pollutants allows the rule to fire with reduced specificity.

### 8.2 Recommendation Rule Matrix (Required vs. Optional)

| Rule ID | Advisory Scope | Required Pollutants | Optional Pollutants | Block Behavior |
|---|---|---|---|---|
| `REC-OUTDOOR-GEN` | General outdoor activity guidance | Composite Index (requires $\ge 1$ PM + $\ge 3$ total) | — | Blocked if Composite Index is `INSUFFICIENT_DATA` |
| `REC-RESP-PM` | Particulate respiratory caution | PM2.5 or PM10 (at least one) | — | Blocked if BOTH PM2.5 and PM10 are `INSUFFICIENT_DATA` |
| `REC-TRAFFIC-NO2` | Vehicular / traffic corridor caution | NO₂ | CO | Blocked if NO₂ is `INSUFFICIENT_DATA`; fires with note if CO missing |
| `REC-OZONE-PEAK` | Afternoon ozone photochemical warning | O₃ | — | Blocked if O₃ is `INSUFFICIENT_DATA` |
| `REC-COMBUSTION` | Carbon monoxide & smoke caution | CO, (PM2.5 or PM10) | NO₂ | Blocked if CO is missing OR both PMs are missing |

---

## 9. Assumptions, Limitations & Unresolved Questions

1. **Assumption (ECMWF Resolution):** CAMS Global surface analysis fields are assumed to have a 3-hourly native temporal step based on ECMWF technical documentation. This assumption is not currently verified dynamically via API headers.
2. **Assumption (Linearity):** Piecewise-linear interpolation across accepted gaps $\le 4\text{ hours}$ is an approximation. Atmospheric chemistry reactions and wind dispersion can exhibit non-linear diurnal transients.
3. **Limitation ($\text{NH}_3$ Absence):** Ammonia is persistently absent in Open-Meteo CAMS Global for Indian coordinates. The composite index must function reliably using the remaining criteria pollutants.
4. **Limitation (Model Lag):** Because `model_issue_time` is absent from Open-Meteo responses, the exact age of the numerical cycle cannot be determined. The system explicitly discloses `UNKNOWN_RUN_AGE`.
5. **Unresolved Question:** Does Open-Meteo expose `model_issue_time` via alternate HTTP response headers (e.g., `X-Model-Initialization-Time`)? This will be probed in Stage 2 without blocking development.

---

## 10. Stage 1 Acceptance Checklist & Verdict

- [x] Piecewise-linear trapezoidal time integration mathematically specified.
- [x] Flawed Voronoi nearest-neighbour expansion permanently removed.
- [x] Exact identity between integrated duration and coverage duration proven.
- [x] Exact 24h (86400s) and 8h (28800s) duration windows defined.
- [x] Configurable $G_{\max} = 14400\text{s}$ (4h) documented with technical rationale.
- [x] All 20 mathematical test cases independently computed with exact numerical values.
- [x] Invalid v2.4 TEST-02 and TEST-W4 expected results removed and replaced.
- [x] Provider temporal resolution semantics strictly documented (API frequency vs. native resolution vs. model issue time).
- [x] Historical query strategy (`past_days=2`, `forecast_days=1`) established.
- [x] Distinction between project coverage criteria and official CPCB CAAQMS compliance enforced.
- [x] Zero application source code modified during Stage 1.

**STAGE 1 VERDICT: PASS.**  
Specification v2.4.1 is complete, verified, and ready for Stage 2 (Open-Meteo Provider Validation).
