# AirAware AI — Architecture Specification Version 2.4.3 (Focused Final Stage 1 Amendment)

**Document Version:** 2.4.3  
**Status:** Frozen Stage 1 Mathematical and Data Governance Specification  
**Parent Baseline:** v2.4.2  
**Date:** 24 November 2026  
**Target Submission:** Hack2Skill Challenge 6 (Deadline: 29 November 2026, 11:59 PM IST)  
**Test Evidence Artifact:** `stage1_test_evidence_v243.json`  
**Artifact SHA-256 Checksum:** `D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773`  

> [!IMPORTANT]
> **Stage 1 Implementation Boundary Strictly Preserved:** In strict accordance with execution directives, **zero application source code, API routes, schemas, database models, frontend components, or production configurations have been modified**. This document serves as the final frozen Stage 1 mathematical specification. Stage 1 is frozen upon delivery; execution proceeds to Stage 2 (Provider Validation) upon authorization.

---

## Table of Contents

1. [Provisional Challenge Objectives vs. Engineering Decisions](#1-provisional-challenge-objectives-vs-engineering-decisions)
2. [CAMS Temporal Resolution: Rigorous Multi-Layer Taxonomy](#2-cams-temporal-resolution-rigorous-multi-layer-taxonomy)
3. [Revised $G_{\max}$ Rationale as an Engineering Choice](#3-revised-g_max-rationale-as-an-engineering-choice)
4. [Duplicate Timestamp Handling Policy](#4-duplicate-timestamp-handling-policy)
5. [Invalid Sample Handling Policy & Gap Bridging Disclosure](#5-invalid-sample-handling-policy--gap-bridging-disclosure)
6. [Provider Request & Boundary Verification Strategy](#6-provider-request--boundary-verification-strategy)
7. [Piecewise-Linear Trapezoidal Integration Formulation](#7-piecewise-linear-trapezoidal-integration-formulation)
8. [Complete 20-Test Reproducible Dataset & Audit Evidence](#8-complete-20-test-reproducible-dataset--audit-evidence)
9. [CPCB Regulatory Distinction & INDICATIVE_MODEL_INDEX](#9-cpcb-regulatory-distinction--indicative_model_index)
10. [Reconciled Pollutant Safety & Recommendation Invariants](#10-reconciled-pollutant-safety--recommendation-invariants)
11. [Stage 1 Acceptance Checklist (PASS / FAIL / UNVERIFIED)](#11-stage-1-acceptance-checklist-pass--fail--unverified)

---

## 1. Provisional Challenge Objectives vs. Engineering Decisions

Requirements remain formally partitioned into three distinct tiers:

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
- **[ENG-DEC-03] Gap-Aware Trapezoidal Time Integration:** Continuous piecewise-linear trapezoidal integration; enforcing exact identity between supported integration duration and coverage duration.
- **[ENG-DEC-04] Configurable Maximum Supported Gap ($G_{\max} = 14400\text{s}$):** An internal engineering interpolation limit. Gaps exceeding $G_{\max}$ remain completely uncovered and contribute zero duration and zero concentration.
- **[ENG-DEC-05] Server-Authoritative Trust Boundary:** Complete rejection of client-supplied AQI, category overrides, or precomputed risk scores.
- **[ENG-DEC-06] Rigorous Temporal Semantics & Null Metadata Preservation:** Exposing 6 distinct temporal fields; preserving `model_issue_time = null` when upstream API metadata is absent.

---

## 2. CAMS Temporal Resolution: Rigorous Multi-Layer Taxonomy

### 2.1 Multi-Layer Atmospheric Data Availability Taxonomy

AirAware AI does **not** treat the native temporal resolution of CAMS Global surface pollutant fields as established. The platform strictly distinguishes between five distinct operational layers:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                   Atmospheric Data Temporal Layer Taxonomy                       │
├────────────────────────────────┬─────────────────────────────────────────────────┤
│ 1. ECMWF Source Surface-Field   │ Global surface atmospheric chemistry fields     │
│    Availability                │ generated by ECMWF IFS-CAMS cycles.             │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 2. ECMWF Model- & Pressure-    │ Multi-level vertical profiles of atmospheric    │
│    Level Availability          │ constituents, often archived on separate steps. │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 3. Open-Meteo CAMS Global      │ The internal dataset ingestion resolution used  │
│    Dataset Ingestion           │ by the provider's backend pipelines.            │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 4. Open-Meteo API Output       │ The timestamp frequency returned in the JSON    │
│    Frequency                   │ payload (observed as hourly: 3600 seconds).     │
├────────────────────────────────┼─────────────────────────────────────────────────┤
│ 5. Provider Interpolation /     │ The provider-side resampling algorithm that     │
│    Resampling Method           │ converts native model nodes to hourly output.   │
└────────────────────────────────┴─────────────────────────────────────────────────┘
```

### 2.2 Operational Policy: `UNKNOWN_PENDING_METADATA_VERIFICATION`

> [!CAUTION]
> - Open-Meteo marketing and overview documentation notes general 3-hourly source data for CAMS Global. However, **the live Open-Meteo API response body does NOT return a `temporal_resolution_seconds` or `native_resolution` field for the surface pollutant variables requested**.
> - AirAware AI will **never** claim an established native model resolution based solely on model names, API timestamp spacing, or modulo arithmetic.
> - **Operational Status:** Until the exact provider dataset and relevant surface-pollutant resolution are empirically established against live metadata endpoints in Stage 2, the system records:
>   $$\text{native\_model\_temporal\_resolution} = \text{"UNKNOWN\_PENDING\_METADATA\_VERIFICATION"}$$
> - The integration engine operates strictly on verified timestamps and the internal configurable $G_{\max}$ limit.

---

## 3. Revised $G_{\max}$ Rationale as an Engineering Choice

### 3.1 Status: Internal Configurable Engineering Interpolation Limit
$G_{\max}$ is an **internal engineering design parameter**, not an upstream provider guarantee and not a scientifically verified consequence of a proven native surface-field interval. It is configurable via `AIRAWARE_MAX_SUPPORTED_GAP_SECONDS` (default: 14,400 seconds = 4.0 hours).

### 3.2 Technical Rationale as an Engineering Choice
1. **Engineering Interpolation Limit:** Linear interpolation over time assumes atmospheric concentrations change predictably between measurements. Across short spans, linear approximation is defensible. Beyond 4 hours, diurnal atmospheric dynamics (boundary layer expansion, solar photochemical reactions, traffic peaks) introduce non-linearities that make linear interpolation indefensible.
2. **Conservative Client-Side Boundary:** $G_{\max} = 14,400\text{s}$ represents a strict client-side limit beyond which AirAware AI refuses to interpolate across missing data.
3. **No Claim of Upstream Missed-Cycle Detection:** $G_{\max}$ does **not** claim to detect missing upstream model cycles. If the upstream provider performs its own internal interpolation or smoothing before emitting hourly API timestamps, AirAware AI cannot detect that pre-interpolation from timestamps alone. $G_{\max}$ enforces client-side gap gating on the series actually received.

### 3.3 Verified $G_{\max}$ Sensitivity Sweep

| Tested Gap | Gap (Seconds) | Comparison with $G_{\max}$ | Integration Action | Supported Duration | 24h Coverage % |
|---|---|---|---|---|---|
| **1.0 hour** | 3,600s | $3600 \le 14400$ | **ACCEPTED** | 3,600s (1.0h) | 4.2% |
| **2.0 hours** | 7,200s | $7200 \le 14400$ | **ACCEPTED** | 7,200s (2.0h) | 8.3% |
| **3.0 hours** | 10,800s | $10800 \le 14400$ | **ACCEPTED** | 10,800s (3.0h) | 12.5% |
| **4.0 hours** | 14,400s | $14400 == 14400$ | **ACCEPTED (Exact Threshold)**| 14,400s (4.0h) | 16.7% |
| **4.0h + 1s** | 14,401s | $14401 > 14400$ | **REJECTED (Exceeds $G_{\max}$)** | **0s (0.0h)** | **0.0%** |
| **5.0 hours** | 18,000s | $18000 > 14400$ | **REJECTED (Exceeds $G_{\max}$)** | **0s (0.0h)** | **0.0%** |
| **6.0 hours** | 21,600s | $21600 > 14400$ | **REJECTED (Exceeds $G_{\max}$)** | **0s (0.0h)** | **0.0%** |

---

## 4. Duplicate Timestamp Handling Policy

When multiple sample records share the exact same UTC timestamp $t$, the pipeline applies a strict deterministic policy:

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

1. **Identical Duplicate Values:** If all non-null values at timestamp $t$ are numerically identical within floating-point tolerance ($\max |C_i - C_j| < 10^{-6}$), the redundant sample is deduplicated to a single point $(t, C_1)$ and logged as `DUPLICATE_IDENTICAL_TIMESTAMP`.
2. **Conflicting Duplicate Values:** If values at timestamp $t$ differ ($\max |C_i - C_j| \ge 10^{-6}$):
   - **Strict Rule: Never silently select one value (first, last, or average).**
   - The timestamp is marked **AMBIGUOUS AND UNRELIABLE**.
   - All records at timestamp $t$ are rejected and omitted from valid candidate points.
   - The engine attempts to bridge valid samples on either side of $t$. If the resulting gap satisfies $\le G_{\max}$, it is accepted with explicit interpolation disclosure; if $> G_{\max}$, it remains uncovered.
   - Anomaly logged: `DUPLICATE_CONFLICTING_TIMESTAMP_REJECTED`.
3. **Out-of-Order Input:** Samples are sorted by timestamp prior to duplicate grouping.

---

## 5. Invalid Sample Handling Policy & Gap Bridging Disclosure

1. **Invalid Sample Filter:** Any sample with $C = \text{None}$, $C = \text{NaN}$, $C = \pm\infty$, $C < 0.0$, or conflicting duplicate values is filtered out prior to interval construction.
2. **Bridging Candidate Pairs:** Candidate integration intervals are constructed **only between consecutive remaining valid samples** $(t_i, C_i)$ and $(t_{i+1}, C_{i+1})$.
3. **Explicit Disclosure of Interpolation:** When an invalid or missing sample was removed between $t_i$ and $t_{i+1}$:
   - If raw gap $\Delta t = t_{i+1} - t_i \le G_{\max}$: The interval is accepted. The system explicitly documents this as **linear interpolation across a missing-data interval**, NOT an observed environmental measurement.
   - If raw gap $\Delta t > G_{\max}$: The interval is rejected. It contributes $0.0\text{s}$ duration and $0.0$ integral.

---

## 6. Provider Request & Boundary Verification Strategy

1. **Target-Specific Time-Range Queries:** Do not rely on relative offsets (`past_days=2`, `forecast_days=1`) as a universal guarantee. Construct queries using explicit start and end parameters covering $[W_s - 2\text{h}, W_e + 2\text{h}]$.
2. **Mandatory Response Boundary Verification:**
   - Verify `min(returned_timestamps) <= W_s`. If earliest sample has $t > W_s$, boundary interpolation at $W_s$ is impossible; interval $[W_s, t]$ is flagged `UNSUPPORTED_LEFT_BOUNDARY`.
   - Verify `max(returned_timestamps) >= W_e`. If latest sample has $t < W_e$, boundary interpolation at $W_e$ is impossible; interval $[t, W_e]$ is flagged `UNSUPPORTED_RIGHT_BOUNDARY`.
   - If an entire pollutant array is absent (e.g. $\text{NH}_3$), record it as `unavailable_pollutants` and never substitute zero.

---

## 7. Piecewise-Linear Trapezoidal Integration Formulation

For each accepted interval $[a_i, b_i]$ clipped to window $[W_s, W_e]$:
$$\Delta \tau_i = b_i - a_i \quad (\text{seconds})$$
$$I_i = \left( \frac{C(a_i) + C(b_i)}{2} \right) \cdot \Delta \tau_i$$

Total supported duration and total integrated concentration:
$$D_{\text{supported}} = \sum_{i \in \text{accepted}} \Delta \tau_i, \quad I_{\text{total}} = \sum_{i \in \text{accepted}} I_i$$

Coverage percentage and time-weighted mean:
$$\text{Coverage \%} = \left( \frac{D_{\text{supported}}}{W_e - W_s} \right) \times 100\%, \quad \bar{C} = \frac{I_{\text{total}}}{D_{\text{supported}}}$$

---

## 8. Complete 20-Test Reproducible Dataset & Audit Evidence

### 8.1 Published Test Evidence Artifact
The complete unabbreviated input series, accepted interval endpoints, rejected interval endpoints, clipped intervals, supported durations, coverage percentages, integrated concentrations, and weighted means have been published to the versioned JSON artifact:
- **Artifact Path:** `stage1_test_evidence_v243.json` (root workspace and artifact directory)
- **SHA-256 Checksum:** `D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773`
- **Verification Script:** `scratch/run_full_v242.py` / `scratch/generate_evidence.py`

### 8.2 Summary Table of All 20 Verified Tests

- **24h Window:** $[2026-11-23\text{T}14:00:00\text{Z}, 2026-11-24\text{T}14:00:00\text{Z}]$ ($86,400\text{s}$).
- **8h Window:** $[2026-11-24\text{T}06:00:00\text{Z}, 2026-11-24\text{T}14:00:00\text{Z}]$ ($28,800\text{s}$).
- $G_{\max} = 14,400\text{s}$ (4.0 hours).

| Test ID | Scenario | Input Description | Valid Points | Acc Int | Rej Int | Supported Dur | Coverage % | Integral | Weighted Mean |
|---|---|---|---|---|---|---|---|---|---|
| **TEST-01** | Constant (24h) | 25 hourly points, all $C=50.0$ | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-02** | Linear increase (24h) | 25 hourly points, $C=20 \to 68$ (+2/h) | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 3,801,600.0 | **44.0000** |
| **TEST-03** | Linear decrease (24h) | 25 hourly points, $C=100 \to 28$ (-3/h) | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 5,529,600.0 | **64.0000** |
| **TEST-04** | Irregular intervals (24h)| 10 points (0, 1, 2.5, 5, 8, 12, 15, 18.5, 21, 24h) | 10 | 9 | 0 | 86,400s (24h) | **100.0%** | 4,050,000.0 | **46.8750** |
| **TEST-05** | Missing sample ($\le G_{\max}$)| 2h spacing, 6h missing $\to$ gap [4h, 8h] = 4h = $G_{\max}$ | 12 | 11 | 0 | 86,400s (24h) | **100.0%** | 4,968,000.0 | **57.5000** |
| **TEST-06** | Missing sample ($> G_{\max}$)| 3h spacing, 9h missing $\to$ gap [6h, 12h] = 6h $> G_{\max}$ | 8 | 6 | 1 | 64,800s (18h) | **75.0%** | 3,191,400.0 | **49.2500** |
| **TEST-07** | Gap exactly $G_{\max}$ | 7 points (0, 4, 8, 12, 16, 20, 24h), all gaps = 4h | 7 | 6 | 0 | 86,400s (24h) | **100.0%** | 5,097,600.0 | **59.0000** |
| **TEST-08** | Gap just $> G_{\max}$ | Points at 0h, 4h, 8h+1s, 24h; gap = 14,401s | 4 | 1 | 2 | 14,400s (4h) | **16.7%** | 576,000.0 | **40.0000** |
| **TEST-09** | Missing first boundary | Points from 2h to 24h every 2h; 0h absent | 12 | 11 | 0 | 79,200s (22h) | **91.7%** | 4,197,600.0 | **53.0000** |
| **TEST-10** | Missing last boundary | Points from 0h to 22h every 2h; 24h absent | 12 | 11 | 0 | 79,200s (22h) | **91.7%** | 3,880,800.0 | **49.0000** |
| **TEST-11** | Both boundaries interp | Points at -1h (C=30), +2h (C=60); +22h, +25h | 13 | 12 | 0 | 86,400s (24h) | **100.0%** | 5,616,000.0 | **65.0000** |
| **TEST-12** | Boundary samples exact | 3-hourly points (0, 3, 6, 9, 12, 15, 18, 21, 24h) | 9 | 8 | 0 | 86,400s (24h) | **100.0%** | 6,393,600.0 | **74.0000** |
| **TEST-13** | Zero coverage | Points at -12h, -8h; outside window | 2 | 0 | 1 | **0s (0h)** | **0.0%** | 0.0 | **None** |
| **TEST-14** | Partial coverage (50%) | Hourly points from 0h to 12h; 12h..24h unmonitored | 13 | 12 | 0 | 43,200s (12h) | **50.0%** | 2,419,200.0 | **56.0000** |
| **TEST-15** | Complete coverage (2h) | 13 points from 0h to 24h every 2h ($C=45+1.5h$) | 13 | 12 | 0 | 86,400s (24h) | **100.0%** | 5,443,200.0 | **63.0000** |
| **TEST-16** | Identical duplicates | 2h spacing with duplicate at 2h ($C=50, 50$) | 13 | 12 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-17** | Conflicting duplicates | 2h spacing with conflicting duplicate at 4h ($C=40, 80$) | 12 | 11 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-18** | Invalid (Neg, Null, NaN, Inf)| 13 points; 4h=-10, 8h=None, 12h=NaN, 16h=Inf | 9 | 8 | 0 | 86,400s (24h) | **100.0%** | 4,320,000.0 | **50.0000** |
| **TEST-19** | Exact 24-hour window | 25 hourly points ($C=48.0$) across exactly 86400s | 25 | 24 | 0 | 86,400s (24h) | **100.0%** | 4,147,200.0 | **48.0000** |
| **TEST-20** | Exact 8-hour window (CO) | 9 hourly points ($C=1.0 \to 2.6\text{ mg/m}^3$) across 28800s | 9 | 8 | 0 | 28,800s (8h) | **100.0%** | 51,840.0 | **1.8000** |

### 8.3 Detailed Breakdown for Key Methodological Tests

#### TEST-05 vs. TEST-06 (Distinguishing Missing Sample from Excessive Gap)
- In **TEST-05**, samples exist at 2-hour intervals ($0, 2, 4, 8, 10, \dots, 24\text{h}$); the sample at $6\text{h}$ is missing. The resulting gap between valid sample $4\text{h}$ and valid sample $8\text{h}$ is $8 - 4 = 4\text{ hours} = 14,400\text{ seconds}$. Because $14,400\text{s} \le G_{\max}$ ($14,400\text{s}$), this 4-hour gap is **ACCEPTED** and integrated as a bridged interval with duration $14,400\text{s}$. Total coverage is **100.0%**.
- In **TEST-06**, samples exist at 3-hour intervals ($0, 3, 6, 12, 15, \dots, 24\text{h}$); the sample at $9\text{h}$ is missing. The resulting gap between valid sample $6\text{h}$ and valid sample $12\text{h}$ is $12 - 6 = 6\text{ hours} = 21,600\text{ seconds}$. Because $21,600\text{s} > G_{\max}$ ($14,400\text{s}$), the interval $[6\text{h}, 12\text{h}]$ is **REJECTED**. It contributes $0\text{s}$ duration and $0.0$ integral. Supported duration is $64,800\text{s}$ (18.0h) out of $86,400\text{s}$ ($75.0\%$ coverage). The 6-hour gap remains completely uncovered.

#### TEST-11 (Both Boundaries Interpolated)
- $W_s$ ($14:00$) is bracketed by sample at $-1\text{h}$ ($13:00, C=30$) and sample at $+2\text{h}$ ($16:00, C=60$). Raw gap is $3\text{h} \le G_{\max}$. Clipped interval $[14:00, 16:00]$ has duration $7,200\text{s}$. Linear interpolation at $W_s$ yields $C(14:00) = 30 + (60-30)\times(1/3) = 40.0$. Integral is $((40+60)/2)\times 7200 = 360,000.0$.
- $W_e$ ($14:00$ Day 2) is bracketed by sample at $+22\text{h}$ ($12:00, C=70$) and sample at $+25\text{h}$ ($15:00, C=100$). Raw gap is $3\text{h} \le G_{\max}$. Clipped interval $[12:00, 14:00]$ has duration $7,200\text{s}$. Linear interpolation at $W_e$ yields $C(14:00) = 70 + (100-70)\times(2/3) = 90.0$. Integral is $((70+90)/2)\times 7200 = 576,000.0$.
- All internal intervals are valid ($2\text{h} \le G_{\max}$). Total coverage is **100.0%**, weighted mean is **65.0000**.

#### TEST-17 (Conflicting Duplicate Timestamp Resolution)
- Input series has 2-hour spacing, but at $4\text{h}$ ($18:00$), two conflicting records are provided: $C=40.0$ and $C=80.0$.
- Under policy §4.2, timestamp $18:00$ is ambiguous and **completely rejected**.
- The candidate pair formed across the rejected timestamp connects valid sample $2\text{h}$ ($16:00, C=50$) and valid sample $6\text{h}$ ($20:00, C=50$).
- Raw gap is $20:00 - 16:00 = 4\text{ hours} = 14,400\text{ seconds}$. Because $14,400\text{s} \le G_{\max}$, interval $[16:00, 20:00]$ is **ACCEPTED** as an interpolation across the gap. Duration is $14,400\text{s}$, integral is $((50+50)/2)\times 14400 = 720,000.0$. Total coverage is **100.0%**, weighted mean is **50.0000**.

#### TEST-18 (Invalid Sample Bridging: Negative, Null, NaN, Inf)
- Input series contains 13 points with 2-hour spacing.
  * $4\text{h}$ ($18:00$): $C = -10.0$ (Negative $\to$ filtered out).
  * $8\text{h}$ ($22:00$): $C = \text{None}$ (Null $\to$ filtered out).
  * $12\text{h}$ ($02:00$): $C = \text{NaN}$ (NaN $\to$ filtered out).
  * $16\text{h}$ ($06:00$): $C = \infty$ (Inf $\to$ filtered out).
- Remaining valid points are at hours $0, 2, 6, 10, 14, 18, 20, 22, 24$ (all $C=50.0$).
- Gaps across filtered points: $[2\text{h}, 6\text{h}] = 4\text{h}$, $[6\text{h}, 10\text{h}] = 4\text{h}$, $[10\text{h}, 14\text{h}] = 4\text{h}$, $[14\text{h}, 18\text{h}] = 4\text{h}$.
- Each gap is exactly $14,400\text{s} == G_{\max}$. All intervals are accepted as linear interpolations across missing data. Total coverage is **100.0%**, weighted mean is **50.0000**.

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

| # | Evaluation Criterion | Verdict | Evidence / Status |
|---|---|---|---|
| 1 | **Piecewise-Linear Trapezoidal Integration Math** | **PASS** | Formally specified; Voronoi nearest-neighbour expansion permanently eliminated. |
| 2 | **Supported Duration & Coverage Numerator Identity** | **PASS** | Mathematically proven: $\sum \Delta \tau_i$ is identical for weighting denominator and coverage numerator. |
| 3 | **Exact Duration Windows (24h & 8h)** | **PASS** | Exact 86,400s and 28,800s boundaries; runtime duration assertions specified. |
| 4 | **$G_{\max}$ Engineering Proposal & Sensitivity Sweep** | **PASS** | Formulated strictly as an internal engineering interpolation limit; sensitivity sweep across 1h, 2h, 3h, 4h, 4h+1s, 5h, 6h verified. |
| 5 | **Duplicate Timestamp Policy** | **PASS** | Identical duplicates deduplicated; conflicting duplicates rejected as ambiguous. |
| 6 | **Invalid Sample Handling Policy** | **PASS** | Null, negative, NaN, Inf removed before pair formation; gap bridged only if $\le G_{\max}$ with explicit interpolation disclosure. |
| 7 | **Complete 20-Test Reproducible Dataset** | **PASS** | Published in `stage1_test_evidence_v243.json` (SHA-256: `D6F3940E1A41B095F76FC2C4FEA1A3D1F34A16937B1B134198E78354BED75773`). |
| 8 | **Provider Request Strategy** | **PASS** | Target-specific range parameterization and runtime boundary support checks established. |
| 9 | **Stage 1 Implementation Boundary Preserved** | **PASS** | Zero application source files, API routes, schemas, or databases modified. Working tree verified clean. |
| 10 | **CAMS Global Native Temporal Resolution** | **UNVERIFIED** | Live response payload does not return resolution metadata. Preserved as `UNKNOWN_PENDING_METADATA_VERIFICATION`. **Mandatory Stage 2 verification target.** |
| 11 | **CAMS Model Initialization Timestamp ($T_{\text{issue}}$)** | **UNVERIFIED** | Live response payload does not return $T_{\text{issue}}$. Preserved as `null`. **Mandatory Stage 2 verification target.** |
| 12 | **Ammonia ($\text{NH}_3$) Availability Across Multiple Indian Cities** | **UNVERIFIED** | Confirmed absent at Delhi; multi-city coverage (Mumbai, Chennai) remains a **mandatory Stage 2 verification target.** |

---

**STAGE 1 MATHEMATICAL AND SAFETY SPECIFICATION: FROZEN (PASS).**  
Stage 1 is complete, mathematically airtight, and independently auditable via `stage1_test_evidence_v243.json`. Upstream provider metadata items are strictly designated as **UNVERIFIED** and transition into mandatory verification targets for **STAGE 2 — Open-Meteo Validation**.
