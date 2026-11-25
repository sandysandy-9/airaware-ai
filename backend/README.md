# AirAware AI — Production Backend (Stage 3.1 Foundation)

> Authoritative FastAPI data pipeline converting Open-Meteo Copernicus CAMS Global atmospheric grid series into validated rolling averages and clearly labelled `INDICATIVE_MODEL_INDEX` outputs under frozen Architecture v2.4.3 and Stage 2.1 Temporal Governance rules.

---

## 1. Project Setup & Dependency Installation

- **Python Requirement:** Python `>= 3.11` (verified on Python `3.11.18`)
- **Core Stack:** FastAPI, Uvicorn, Pydantic v2, httpx, python-dotenv, pytest

### Using existing `.venv` or creating a virtual environment:
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Install package and dev test dependencies:
pip install -e ".[dev]"
```

*(If using `uv`: `uv sync --dev` inside `backend/`.)*

---

## 2. Environment Configuration

Copy the repository root `.env.example` to `.env` (never commit real secrets or API tokens to Git):

```dotenv
ENVIRONMENT=development
DEBUG=false
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Provider Settings (Zero-Config Primary: Open-Meteo CAMS Global)
OPEN_METEO_CONNECT_TIMEOUT_SECONDS=5.0
OPEN_METEO_READ_TIMEOUT_SECONDS=12.0

# Frozen Stage 1 Math Parameter (Configurable Engineering Proposal)
AIRAWARE_MAX_SUPPORTED_GAP_SECONDS=14400.0

# Caching & Protection
AIRAWARE_CACHE_TTL_SECONDS=600
AIRAWARE_RATE_LIMIT_PER_MIN=120
```

All sensitive credentials (e.g. future optional `GEMINI_API_KEY`) are read purely from environment variables and automatically scrubbed from logs via `SecretRedactingFilter`.

---

## 3. Starting the Backend

```bash
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Interactive OpenAPI schema documentation is served at `http://127.0.0.1:8000/docs`.

---

## 4. Stage 3.1 Core API Endpoints

> **Strict Trust Boundary:** Client-supplied query overrides (`aqi`, `aqi_category`, `category`, `dominant_pollutant`, `risk_score`, `recommendation`, `data_freshness`) and extra comparison fields are rejected with `HTTP 422`. All indices are calculated authoritatively on the server.

### `GET /health`
Returns service health status, version, CPCB breakpoint reference, and `INDICATIVE_MODEL_INDEX` designation.

### `GET /api/v1/air-quality/cities`
Lists supported reference Indian cities with explicit non-station coordinate provenance (`coordinate_role: "REFERENCE_CITY_CENTER"`, `not_a_monitoring_station: true`).

### `GET /api/v1/air-quality/current`
Accepts validated geographic inputs (`city` or `latitude` + `longitude`), fetches bounded historical+forecast series from `domains=cams_global` (`timezone=Asia/Kolkata`), runs Stage 1 piecewise-linear trapezoidal rolling integration (`24h` for PM2.5, PM10, NO₂, SO₂; `8h` for CO, O₃; `Gmax = 14,400s`), converts CO from `µg/m³` to `mg/m³`, and computes `INDICATIVE_MODEL_INDEX`.

- **Example Request:**
  `GET /api/v1/air-quality/current?latitude=28.6139&longitude=77.2090`
- **Abridged Example Response (Structure Observed on Live Execution):**
```json
{
  "status": "SUCCESS",
  "index_type": "INDICATIVE_MODEL_INDEX",
  "is_official_cpcb_station_aqi": false,
  "location": { "name": "Near New Delhi (28.6139, 77.2090)", "city": "Delhi", "state": "Delhi" },
  "coordinates": {
    "requested_latitude": 28.6139,
    "requested_longitude": 77.209,
    "returned_latitude": 28.599998,
    "returned_longitude": 77.20001,
    "geodesic_snap_distance_km": 1.7776,
    "elevation_m": 214.0,
    "coordinate_role": "MODEL_GRID_ESTIMATE",
    "is_physical_station": false
  },
  "provider": {
    "provider_name": "Open-Meteo Air Quality API",
    "domain_requested": "cams_global",
    "model_name": "cams_global",
    "metadata_verified": true,
    "native_temporal_resolution": "UNKNOWN_PENDING_VERIFICATION",
    "meta_temporal_resolution_seconds": 3600,
    "api_output_frequency_seconds": 3600,
    "cache_hit": false
  },
  "indicative_index": {
    "status": "AVAILABLE",
    "index_type": "INDICATIVE_MODEL_INDEX",
    "is_official_cpcb_station_aqi": false,
    "value": 212,
    "category": "POOR",
    "dominant_pollutant": "pm25",
    "eligible_pollutants": ["pm25", "pm10", "no2", "so2", "co", "o3"],
    "insufficient_or_unavailable_pollutants": ["nh3"]
  },
  "temporal_governance": {
    "model_issue_time": "2026-11-24T12:00:00Z",
    "valid_time": "2026-11-25T06:00:00Z",
    "retrieval_time": "2026-11-25T06:54:44Z",
    "model_run_age_hours": 18.9123,
    "forecast_lead_hours": 18.0,
    "valid_time_offset_hours": -0.9123,
    "valid_time_vs_retrieval": "PAST",
    "model_run_relation": "FORECAST",
    "data_source_type": "MODEL_DERIVED"
  }
}
```

### `GET /api/v1/air-quality/compare` & `POST /api/v1/air-quality/compare`
Evaluates 2 to 6 cities or coordinate pairs concurrently. Identifies `cleanest_location` and `most_polluted_location` only across locations with `AVAILABLE` indicative indices, handles partial upstream failures safely, and warns on timestamp or snapped-grid differences.

- **Example GET Request:**
  `GET /api/v1/air-quality/compare?cities=delhi,mumbai`
  or `GET /api/v1/air-quality/compare?locations=28.6139,77.2090;19.0760,72.8777`

---

## 5. Data Provenance, Temporal Classification & Limitations

1. **Indicative Index vs. Official CPCB Station AQI:**
   - CPCB NAQI breakpoints are legally defined for continuous physical ambient monitoring stations (CAAQMS) under station completeness audits.
   - Copernicus CAMS Global outputs regional atmospheric grid simulations (`~0.4 deg` grid spacing). Applying CPCB formulas yields **`INDICATIVE_MODEL_INDEX` (`is_official_cpcb_station_aqi = false`)**, never a regulatory station measurement.
2. **Separated Temporal Governance:**
   - `valid_time_vs_retrieval` (`PAST`, `CURRENT`, `FUTURE`) measures strictly `valid_time - retrieval_time`.
   - `model_run_relation` (`ANALYSIS`, `FORECAST`, `UNKNOWN`) measures `valid_time - model_issue_time` when authoritative metadata from `cams_global/static/meta.json` is verified.
   - A forecast step (`lead > 0h`) whose `valid_time` precedes retrieval remains classified as `valid_time_vs_retrieval: "PAST"` with `model_run_relation: "FORECAST"` — never falsely inferred as `HISTORICAL_ANALYSIS`.
   - Unverified domains (such as `auto`) retain `model_run_relation: "UNKNOWN"`.
3. **Known Data Limitations:**
   - `ammonia` (`nh3`) is persistently `null` across tested Indian locations (`Delhi`, `Mumbai`, `Chennai`) and is excluded rather than zero-substituted.
   - Carbon monoxide (`carbon_monoxide`) is reported by Open-Meteo in `µg/m³` and divided by `1,000` to convert to `mg/m³` for CPCB breakpoint evaluation.
   - Upstream ECMWF surface-field native temporal step remains `UNKNOWN_PENDING_VERIFICATION` because `static/meta.json` reports Open-Meteo's `3600s` grid store resolution while overview documentation references 3-hourly CAMS cycles.

---

## 6. Running the Automated Test Suite

```bash
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v
```

- **Unit Tests:** Labeled `[SYNTHETIC UNIT TEST]` or `[SYNTHETIC API TEST]` using explicit deterministic fixtures or `httpx` mocks.
- **Stage 1 Parity Check:** `test_frozen_stage1_evidence_artifact_parity` verifies exact agreement with root `stage1_test_evidence_v243.json`.
- **Live Integration Tests:** Marked `[LIVE INTEGRATION TEST]`, executing real HTTP requests against `air-quality-api.open-meteo.com`.
