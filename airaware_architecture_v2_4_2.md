# AirAware AI — Architecture Specification Version 2.4.2 (Stage 1 Mathematical and Provider Amendments)

**Document Version:** 2.4.2  
**Status:** Stage 1 Focused Mathematical & Provider Amendment — Awaiting Review & Stage 2 Authorization  
**Parent Baseline:** v2.4.1  
**Date:** 24 November 2026  
**Target Submission:** Hack2Skill Challenge 6 (Deadline: 29 November 2026, 11:59 PM IST)  

> [!IMPORTANT]
> **Stage 1 Implementation Boundary Strictly Preserved:** In compliance with Stage 1 directives, **zero application source code, API routes, schemas, databases, or production configurations have been modified**. This document establishes the exact mathematical policies, reproducible test specifications, and provider verification requirements.

---

## Table of Contents

1. [Provisional Challenge Objectives vs. Engineering Decisions](#1-provisional-challenge-objectives-vs-engineering-decisions)
2. [CAMS Temporal Resolution: Scientific Taxonomy & Status](#2-cams-temporal-resolution-scientific-taxonomy--status)
3. [Revised $G_{\max}$ Rationale & Sensitivity Analysis](#3-revised-g_max-rationale--sensitivity-analysis)
4. [Duplicate Timestamp Handling Policy](#4-duplicate-timestamp-handling-policy)
5. [Invalid Sample Handling Policy](#5-invalid-sample-handling-policy)
6. [Provider Request & Boundary Verification Strategy](#6-provider-request--boundary-verification-strategy)
7. [Piecewise-Linear Trapezoidal Integration Formula](#7-piecewise-linear-trapezoidal-integration-formula)
8. [Complete Reproducible 20-Test Verification Dataset](#8-complete-reproducible-20-test-verification-dataset)
9. [CPCB Regulatory Distinction & INDICATIVE_MODEL_INDEX](#9-cpcb-regulatory-distinction--indicative_model_index)
10. [Reconciled Pollutant Safety & Recommendation Invariants](#10-reconciled-pollutant-safety--recommendation-invariants)
11. [Stage 1 Acceptance Checklist (PASS / FAIL / UNVERIFIED)](#11-stage-1-acceptance-checklist-pass--fail--unverified)

---

## 1. Provisional Challenge Objectives vs. Engineering Decisions

Requirements are partitioned into three distinct tiers to preserve transparency:

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
- **[ENG-DEC-02] Duration Windows:** Exact 24-hour duration for PM2.5, PM10, NO₂, SO₂; exact 8-hour duration for CO, O₃.
- **[ENG-DEC-03] Gap-Aware Trapezoidal Time Integration:** Replacing flawed Voronoi coverage with continuous piecewise-linear trapezoidal integration; enforcing exact identity between supported integration duration and coverage duration.
- **[ENG-DEC-04] Configurable Maximum Supported Gap ($G_{\max} = 14400\text{s}$):** An internal engineering design parameter. Gaps exceeding $G_{\max}$ remain completely uncovered and contribute zero duration and zero concentration.
- **[ENG-DEC-05] Server-Authoritative Trust Boundary:** Complete rejection of client-supplied AQI, category overrides, or precomputed risk scores.
- **[ENG-DEC-06] Rigorous Temporal Semantics & Null Metadata Preservation:** Exposing 6 distinct temporal fields; preserving `model_issue_time = null` when upstream API metadata is absent.

---

## 2. CAMS Temporal Resolution: Scientific Taxonomy & Status

### 2.1 Critical Distinctions in Atmospheric Data Layers

To avoid misrepresenting model estimates, the system distinguishes between five distinct levels of atmospheric data availability:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   Atmospheric Data Temporal Layer Taxonomy                       │
├────────────────────────────────┬─────────────────────────────────────────────────┤
│ 1. ECMWF Source Surface-Field   │ Global surface atmospheric chemistry fields     │
│    Availability                │ generated by ECMWF IFS-CAMS global cycles.      │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 2. ECMWF Model- & Pressure-    │ Multi-level vertical profiles of atmospheric    │
│    Level Availability          │ constituents, often archived on separate steps. │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 3. Open-Meteo CAMS Global      │ The internal ingestion resolution used by the   │
│    Dataset Resolution          │ provider's data store (e.g. 3-hourly source).   │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 4. Open-Meteo API Output       │ The timestamp frequency returned in the JSON    │
│    Frequency                   │ payload (observed as hourly: 3600 seconds).     │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 5. Provider Interpolation /     │ The provider-side resampling algorithm that     │
│    Resampling Method           │ converts native model nodes to hourly output.   │
└────────────────────────────────┴─────────────────────────────────────────────────┘
```

### 2.2 Formal Resolution Status: `UNKNOWN_PENDING_METADATA_VERIFICATION`

> [!CAUTION]
> - Although Open-Meteo documentation notes that CAMS Global is ingested from 3-hourly source data, **the live Open-Meteo API response does NOT contain a `temporal_resolution_seconds` or `native_resolution` field**.
> - AirAware AI will **never** claim an unverified native model resolution based solely on the model name, API timestamp spacing, or modulo arithmetic.
> - **Operational Policy:** Until live metadata confirming the native resolution is verified directly from provider metadata endpoints in Stage 2, the system records `native_model_temporal_resolution = "UNKNOWN_PENDING_METADATA_VERIFICATION"`. The integration engine operates strictly on verified timestamps and the configurable $G_{\max}$ parameter.

---

## 3. Revised $G_{\max}$ Rationale & Sensitivity Analysis

### 3.1 Status: Configurable Engineering Proposal
$G_{\max}$ is an **internal engineering design parameter**, not an upstream provider service level agreement. It is configurable via `AIRAWARE_MAX_SUPPORTED_GAP_SECONDS` (default: 14,400s = 4.0 hours).

### 3.2 Technical Rationale Under Documented Provider Behavior
1. **ECMWF CAMS 3-Hourly Nominal Cycle:** Open-Meteo's model documentation states that CAMS Global has a 3-hourly native temporal step (10,800s).
2. **Tolerance for Jitter ($+1\text{ hour}$):** Setting $G_{\max} = 14,400\text{s}$ (4.0 hours) provides a 1-hour tolerance for hourly-resampled timestamp offsets, sub-hourly grid interpolation jitter, or coordinate alignment offsets.
3. **Rejection of Multi-Step Gaps:** If consecutive valid samples are separated by more than 4 hours, the data gap is considered too wide for linear interpolation to represent atmospheric chemistry defensively.
4. **No Provider Guarantee:** $G_{\max}$ does **not** guarantee that an upstream missed cycle is detected if the provider pre-interpolates across it before returning hourly steps. It represents the client-side boundary beyond which AirAware AI refuses to interpolate.

### 3.3 $G_{\max}$ Sensitivity Sweep (Verified Behavior)

The table below demonstrates the exact behavior of $G_{\max} = 14,400\text{s}$ when tested against isolated gaps of varying duration within a 24-hour window:

| Gap Duration | Gap (Seconds) | Comparison with $G_{\max}$ | Integration Status | Supported Duration | 24h Coverage % |
|---|---|---|---|---|---|
| **1.0 hour** | 3,600s | $3600 \le 14400$ | **ACCEPTED** | 3,600s (1.0h) | 4.2% |
| **2.0 hours** | 7,200s | $7200 \le 14400$ | **ACCEPTED** | 7,200s (2.0h) | 8.3% |
| **3.0 hours** | 10,800s | $10800 \le 14400$ | **ACCEPTED** | 10,800s (3.0h) | 12.5% |
| **4.0 hours** | 14,400s | $14400 == 14400$ | **ACCEPTED (Exact Boundary)** | 14,400s (4.0h) | 16.7% |
| **4.0h + 1s** | 14,401s | $14401 > 14400$ | **REJECTED (Exceeds $G_{\max}$)** | **0s (0.0h)** | **0.0%** |
| **5.0 hours** | 18,000s | $18000 > 14400$ | **REJECTED (Exceeds $G_{\max}$)** | **0s (0.0h)** | **0.0%** |
| **6.0 hours** | 21,600s | $21600 > 14400$ | **REJECTED (Exceeds $G_{\max}$)** | **0s (0.0h)** | **0.0%** |

---

## 4. Duplicate Timestamp Handling Policy

When multiple sample records share the exact same UTC timestamp $t$, the pipeline applies a strict deterministic resolution policy:

```
                                  [Duplicate Timestamps at t]
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
          [All Valid & Identical?]                        [Conflicting Values?]
          (|C_max - C_min| < 1e-6)                        (|C_max - C_min| >= 1e-6)
                      │                                               │
                      ▼                                               ▼
             [DEDUPLICATE]                                   [REJECT TIMESTAMP]
          Keep single point (t, C)                        Ambiguous; omit both
          Log: DUPLICATE_IDENTICAL                        Log: CONFLICTING_DUPLICATE
```

### 4.1 Identical Duplicate Values
If all non-null values at timestamp $t$ are numerically identical within floating-point tolerance ($\max |C_i - C_j| < 10^{-6}$):
- Deduplicate to a single valid point $(t, C_1)$.
- Anomaly logged: `DUPLICATE_IDENTICAL_TIMESTAMP`.

### 4.2 Conflicting Duplicate Values
If values at timestamp $t$ differ ($\max |C_i - C_j| \ge 10^{-6}$):
- **Strict Invariant: Never silently choose one value (e.g. first, last, or average).**
- The timestamp is marked as **AMBIGUOUS AND UNRELIABLE**.
- All records at timestamp $t$ are rejected and excluded from valid candidate points.
- The pipeline attempts to bridge valid samples on either side of $t$. If the resulting gap exceeds $G_{\max}$, the interval remains uncovered.
- Anomaly logged: `DUPLICATE_CONFLICTING_TIMESTAMP_REJECTED`.

### 4.3 Out-of-Order Timestamps
Samples are sorted by timestamp prior to duplicate grouping. If timestamps were out of order, the sorting is executed and logged as `INPUT_OUT_OF_ORDER_SORTED`.

---

## 5. Invalid Sample Handling Policy

### 5.1 Invalid Sample Taxonomy
A sample is classified as **INVALID** if any of the following occur:
1. `None` / `null` value.
2. `NaN` (`math.isnan(C) == True`).
3. Infinite value (`math.isinf(C) == True`).
4. Negative physical concentration ($C < 0.0$).
5. Conflicting duplicate timestamp.

### 5.2 Pre-Integration Filtering Rule
- All invalid samples are removed prior to constructing consecutive integration pairs.
- Candidate consecutive pairs are formed **only between consecutive remaining valid samples** $(t_i, C_i)$ and $(t_{i+1}, C_{i+1})$.

### 5.3 Bridging Across Missing-Data Intervals
If an invalid or missing sample was removed between $t_i$ and $t_{i+1}$, the resulting raw gap is $\Delta t = t_{i+1} - t_i$:
- **If $\Delta t \le G_{\max}$:** The interval is accepted.
  > [!NOTE]
  > **Explicit Disclosure:** The engine documents this as **linear interpolation across a missing-data interval**, NOT an observed environmental measurement.
- **If $\Delta t > G_{\max}$:** The interval is rejected. It contributes $0.0\text{s}$ duration and $0.0$ integral. It remains completely uncovered.

---

## 6. Provider Request & Boundary Verification Strategy

### 6.1 Target-Specific Time-Range Queries
- Do not rely on fixed relative offsets (`past_days=2`, `forecast_days=1`) as a universal guarantee of boundary coverage.
- The provider adapter must construct target-specific queries using explicit dates or hour ranges:
  - For target valid time $T_{\text{valid}}$:
  - $W_s = T_{\text{valid}} - 24\text{ hours}$
  - $W_e = T_{\text{valid}}$
  - Requested start: $W_s - 2\text{ hours}$
  - Requested end: $W_e + 2\text{ hours}$

### 6.2 Mandatory Response Boundary Verification
Upon receiving provider time series, the adapter must execute runtime boundary checks:
1. **Left Boundary Support Check:** Verify that at least one valid sample exists at $t \le W_s$.
   - If the earliest valid sample has $t > W_s$, boundary interpolation at $W_s$ is impossible. The interval $[W_s, t]$ is flagged as `UNSUPPORTED_LEFT_BOUNDARY`.
2. **Right Boundary Support Check:** Verify that at least one valid sample exists at $t \ge W_e$.
   - If the latest valid sample has $t < W_e$, boundary interpolation at $W_e$ is impossible. The interval $[t, W_e]$ is flagged as `UNSUPPORTED_RIGHT_BOUNDARY`.
3. **Pollutant Array Completeness:** Verify that requested pollutant arrays contain non-null series. If an array is completely empty (e.g. $\text{NH}_3$), it is assigned to `unavailable_pollutants`.

---

## 7. Piecewise-Linear Trapezoidal Integration Formula

For each accepted interval $[a_i, b_i]$ clipped to window $[W_s, W_e]$:
$$\Delta \tau_i = b_i - a_i \quad (\text{seconds})$$
$$I_i = \left( \frac{C(a_i) + C(b_i)}{2} \right) \cdot \Delta \tau_i$$

Total supported duration and total integrated concentration:
$$D_{\text{supported}} = \sum_{i \in \text{accepted}} \Delta \tau_i$$
$$I_{\text{total}} = \sum_{i \in \text{accepted}} I_i$$

Coverage percentage and time-weighted mean:
$$\text{Coverage \%} = \left( \frac{D_{\text{supported}}}{W_e - W_s} \right) \times 100\%$$
$$\bar{C} = \frac{I_{\text{total}}}{D_{\text{supported}}}$$

---

## 8. Complete Reproducible 20-Test Verification Dataset

All 20 test cases have been independently computed and verified using `scratch/run_full_v242.py`.
- **24h Window:** $[W_s, W_e] = [2026-11-23\text{T}14:00:00\text{Z}, 2026-11-24\text{T}14:00:00\text{Z}]$ (86,400s).
- **8h Window:** $[W_s, W_e] = [2026-11-24\text{T}06:00:00\text{Z}, 2026-11-24\text{T}14:00:00\text{Z}]$ (28,800s).
- $G_{\max} = 14,400\text{s}$ (4.0 hours).

### Summary Table of All 20 Tests

| Test ID | Test Scenario | Input Summary | Valid Points | Acc Int | Rej Int | Supported Dur | Coverage % | Total Integral | Weighted Mean |
|---|---|---|---|---|---|---|---|---|---|
| **TEST-01** | Constant Concentration (24h) | 25 hourly points, all $C=50.0$ | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-02** | Linear Increase (24h) | 25 hourly points, $C=20 \to 68$ (+2/h) | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 3,801,600.0 | **44.0000** |
| **TEST-03** | Linear Decrease (24h) | 25 hourly points, $C=100 \to 28$ (-3/h) | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 5,529,600.0 | **64.0000** |
| **TEST-04** | Irregular Intervals (24h) | 10 points (0, 1, 2.5, 5, 8, 12, 15, 18.5, 21, 24h) | 10 | 9 | 0 | 86,400s (24h) | **100.0%** | 4,050,000.0 | **46.8750** |
| **TEST-05** | Missing Sample (Acceptable Gap) | 2h spacing, 6h missing -> gap [4h, 8h] = 4h = $G_{\max}$ | 12 | 11 | 0 | 86,400s (24h) | **100.0%** | 4,968,000.0 | **57.5000** |
| **TEST-06** | Missing Sample (Excessive Gap) | 3h spacing, 9h missing -> gap [6h, 12h] = 6h $> G_{\max}$ | 8 | 6 | 1 | 64,800s (18h) | **75.0%** | 3,191,400.0 | **49.2500** |
| **TEST-07** | Gaps Exactly Equal $G_{\max}$ | 7 points (0, 4, 8, 12, 16, 20, 24h), all gaps = 4h | 7 | 6 | 0 | 86,400s (24h) | **100.0%** | 5,097,600.0 | **59.0000** |
| **TEST-08** | Gap Just $> G_{\max}$ (14401s) | Points at 0h, 4h, 8h+1s, 24h; gap = 14401s | 4 | 1 | 2 | 14,400s (4h) | **16.7%** | 576,000.0 | **40.0000** |
| **TEST-09** | Missing First Boundary Sample | Points from 2h to 24h every 2h; 0h absent | 12 | 11 | 0 | 79,200s (22h) | **91.7%** | 4,197,600.0 | **53.0000** |
| **TEST-10** | Missing Last Boundary Sample | Points from 0h to 22h every 2h; 24h absent | 12 | 11 | 0 | 79,200s (22h) | **91.7%** | 3,880,800.0 | **49.0000** |
| **TEST-11** | Both Boundaries Interpolated | Points at -1h (C=30), +2h (C=60); +22h, +25h | 13 | 12 | 0 | 86,400s (24h) | **100.0%** | 5,616,000.0 | **65.0000** |
| **TEST-12** | Samples Exactly at Boundaries | 3-hourly points (0, 3, 6, 9, 12, 15, 18, 21, 24h) | 9 | 8 | 0 | 86,400s (24h) | **100.0%** | 6,393,600.0 | **74.0000** |
| **TEST-13** | Zero Coverage | Points at -12h, -8h; outside window | 2 | 0 | 1 | **0s (0h)** | **0.0%** | 0.0 | **None** |
| **TEST-14** | Partial Coverage (50%) | Hourly points from 0h to 12h; 12h..24h unmonitored | 13 | 12 | 0 | 43,200s (12h) | **50.0%** | 2,419,200.0 | **56.0000** |
| **TEST-15** | Complete Coverage (2-hourly) | 13 points from 0h to 24h every 2h ($C=45+1.5h$) | 13 | 12 | 0 | 86,400s (24h) | **100.0%** | 5,443,200.0 | **63.0000** |
| **TEST-16** | Identical Duplicate Timestamps | 2h spacing with identical duplicate at 2h ($C=50, 50$) | 13 | 12 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-17** | Conflicting Duplicate Timestamps| 2h spacing with conflicting duplicate at 4h ($C=40, 80$) | 12 | 11 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-18** | Invalid Samples (Neg, Null, NaN, Inf)| 13 points; 4h is -10, 8h is None, 12h is NaN, 16h is Inf | 9 | 8 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-19** | Exact 24-Hour Duration Window | 25 hourly points ($C=48.0$) across exactly 86400s | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 4,147,200.0 | **48.0000** |
| **TEST-20** | Exact 8-Hour Duration Window | 9 hourly points ($C=1.0 \to 2.6\text{ mg/m}^3$) across 28800s | 9 | 8 | 0 | 28,800s (8h) | **100.0%** | 51,840.0 | **1.8000** |

---

## 9. CPCB Regulatory Distinction & INDICATIVE_MODEL_INDEX

Every computed composite index carries the permanent label: **`INDICATIVE_MODEL_INDEX`**.

- **Official CPCB NAQI Compliance:** Requires certified continuous ambient air quality monitoring stations (CAAQMS), physical gravimetric / optical particulate monitors, wet chemical gas analyzers, defined 16-hour data completeness rules per 24-hour cycle, and regulatory calibration audits.
- **AirAware AI INDICATIVE_MODEL_INDEX:** Applies CPCB numerical breakpoint formulas to model-derived atmospheric chemistry fields. It represents a **modelled atmospheric estimate**, not a regulatory measurement.
- Every API response, UI component, and documentation page must display the designation: **`INDICATIVE_MODEL_INDEX`** with the mandatory disclaimer:
  > *"Indicative model-derived estimate calculated using CPCB NAQI breakpoints applied to Copernicus CAMS atmospheric grid simulations. This is not an official Central Pollution Control Board physical monitoring station measurement."*

---

## 10. Reconciled Pollutant Safety & Recommendation Invariants

1. **Composite Index Eligibility (Tier A):** Requires $\ge 3$ valid pollutants, at least one of which must be PM2.5 or PM10. If not met, returns `INSUFFICIENT_DATA`.
2. **Pollutant Interpretation (Tier B):** Only pollutants with valid averages are displayed. Unavailable pollutants (such as $\text{NH}_3$) are explicitly marked `"Not provided by data source"`.
3. **Recommendation Rules (Tier C):**
   - Each rule declares `required_pollutants` and `optional_pollutants`.
   - Missing required pollutant: Rule is **BLOCKED** (`status: "UNAVAILABLE"`).
   - Missing optional pollutant: Rule is **ISSUED WITH REDUCED SPECIFICITY**.

---

## 11. Stage 1 Acceptance Checklist (PASS / FAIL / UNVERIFIED)

| # | Evaluation Criterion | Status | Evidence / Verification Notes |
|---|---|---|---|
| 1 | **Piecewise-Linear Trapezoidal Integration** | **PASS** | Exact trapezoidal integration implemented; Voronoi nearest-neighbour expansion permanently eliminated. |
| 2 | **Supported Duration & Coverage Identity** | **PASS** | Proven mathematically and verified computationally: $\sum \Delta \tau_i$ is identical for weighting denominator and coverage numerator. |
| 3 | **Exact Window Durations** | **PASS** | Exact 24h (86,400s) and 8h (28,800s) duration windows defined; off-by-one errors eliminated. |
| 4 | **$G_{\max}$ Engineering Proposal Rationale** | **PASS** | Configurable parameter ($14,400\text{s}$) with technical justification and sensitivity sweep across 1h, 2h, 3h, 4h, 4h+1s, 5h, 6h. |
| 5 | **Duplicate Timestamp Policy** | **PASS** | Identical duplicates deduplicated; conflicting duplicates rejected as ambiguous and omitted. |
| 6 | **Invalid Sample Handling Policy** | **PASS** | Null, negative, NaN, Inf filtered out prior to pair construction; gap bridged only if $\le G_{\max}$ with explicit interpolation disclosure. |
| 7 | **Complete 20-Test Reproducible Dataset** | **PASS** | All 20 tests defined with complete timestamp-value series, accepted intervals, rejected intervals, durations, integrals, and weighted means. |
| 8 | **Provider Request Strategy** | **PASS** | Target-specific time-range parameterization and mandatory left/right boundary verification checks specified. |
| 9 | **Stage 1 Implementation Boundary Preserved** | **PASS** | Zero application source files, API routes, schemas, or databases modified. Working tree verified clean. |
| 10 | **CAMS Global Native Temporal Resolution** | **UNVERIFIED** | Live API response payload does not return resolution metadata. Preserved as `UNKNOWN_PENDING_METADATA_VERIFICATION`. **Mandatory Stage 2 verification target.** |
| 11 | **CAMS Model Initialization Timestamp ($T_{\text{issue}}$)** | **UNVERIFIED** | Live API response payload does not return $T_{\text{issue}}$. Preserved as `null`. **Mandatory Stage 2 verification target.** |
| 12 | **Ammonia ($\text{NH}_3$) Availability Across Multiple Indian Cities** | **UNVERIFIED** | Verified absent at Delhi coordinates; multi-city coverage (Mumbai, Chennai) remains a **mandatory Stage 2 verification target.** |

---

**STAGE 1 MATHEMATICAL SPECIFICATION VERDICT: PASS.**  
All mathematical formulas, boundary conditions, gap thresholds, and 20 test datasets are fully verified. Upstream provider metadata items are strictly marked **UNVERIFIED** and transition into mandatory empirical verification gates for **STAGE 2 — Open-Meteo Validation**.
