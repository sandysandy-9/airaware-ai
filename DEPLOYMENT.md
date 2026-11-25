# AirAware AI — Production Deployment & Rollback Guide

## 1. Selected Production Architecture

| Component | Platform | Runtime | Configuration File |
|---|---|---|---|
| **Frontend** | **Vercel** | Next.js 14 App Router (`npm run build` / `next start`) | `frontend/vercel.json` |
| **Backend** | **Render** (or any Docker host: Railway, Fly.io, Cloud Run) | Python 3.11 + FastAPI + Uvicorn (single worker) | `render.yaml`, `backend/Dockerfile` |

### Why this architecture
1. **Vercel for `frontend/`**: Native Next.js 14 SSR/static edge delivery, automatic TLS/HTTPS, and build-time injection of `NEXT_PUBLIC_API_URL`.
2. **Render Web Service (Docker) for `backend/`**: Native HTTPS termination, automated `/health` readiness checks, `PORT` injection, and isolated Python 3.11 runtime running a single Uvicorn worker (`--proxy-headers`) so the in-memory `SlidingWindowRateLimiter` and `TTLCache` operate consistently without split-brain state.

---

## 2. Environment Variables

### Backend (Render / Docker Host)

| Variable | Required | Value / Guidance |
|---|---|---|
| `ENVIRONMENT` | Yes | `production` (forces `DEBUG=false` and forbids wildcard `ALLOWED_ORIGINS=*`) |
| `DEBUG` | Yes | `false` |
| `ALLOWED_ORIGINS` | **Yes** | Comma-separated exact HTTPS frontend origin(s), e.g. `https://<your-vercel-domain>` (no trailing slash, no `*`) |
| `AIRAWARE_MAX_SUPPORTED_GAP_SECONDS` | Optional | `14400.0` (frozen Stage 1 `Gmax = 4h` default) |
| `AIRAWARE_CACHE_TTL_SECONDS` | Optional | `600` |
| `AIRAWARE_RATE_LIMIT_PER_MIN` | Optional | `120` |
| `OPEN_METEO_CONNECT_TIMEOUT_SECONDS` | Optional | `5.0` |
| `OPEN_METEO_READ_TIMEOUT_SECONDS` | Optional | `12.0` |
| `GEMINI_API_KEY` | Optional | Secret Gemini API key; if omitted, `/api/v1/ai/chat` runs in deterministic fallback mode |
| `AIRAWARE_LLM_MODEL` | Optional | `gemini-2.0-flash` |

> **Security Note:** Never expose `GEMINI_API_KEY`, `WAQI_API_TOKEN`, or `DATA_GOV_IN_API_KEY` with a `NEXT_PUBLIC_` prefix. All provider/LLM credentials remain strictly server-side.

### Frontend (Vercel)

| Variable | Required | Value / Guidance |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | **Yes** | Public HTTPS URL of the deployed backend API, ending in `/api/v1` (e.g. `https://<your-render-service>/api/v1`) |

---

## 3. Exact Deployment Steps

> **Prerequisite:** Commit and push your reviewed branch to your Git provider (GitHub/GitLab), and sign in to your Render and Vercel accounts.

### Step 1: Deploy the Backend (Render)
1. In the Render Dashboard, click **New + → Blueprint** (or **Web Service**) and connect the repository.
2. Render reads `render.yaml` (`rootDir: backend`, `dockerfilePath: ./Dockerfile`, `healthCheckPath: /health`).
3. Set `ALLOWED_ORIGINS` temporarily to `http://localhost:3000` (updated in Step 3 once the Vercel URL is assigned).
4. Optionally set `GEMINI_API_KEY` as a secret environment variable in Render.
5. Deploy and verify `GET https://<your-backend-domain>/health` returns HTTP `200` with `"status": "healthy"` and `"index_type": "INDICATIVE_MODEL_INDEX"`.

### Step 2: Deploy the Frontend (Vercel)
1. In Vercel, click **Add New → Project** and import the repository.
2. Set **Root Directory** to `frontend`.
3. Add environment variable `NEXT_PUBLIC_API_URL=https://<your-backend-domain>/api/v1`.
4. Deploy (`next build`). Note the assigned production HTTPS origin (`https://<your-vercel-domain>`).

### Step 3: Lock Down Backend CORS Allowlist
1. Return to Render → **Environment** for `airaware-ai-backend`.
2. Update `ALLOWED_ORIGINS` to your exact Vercel HTTPS origin(s), e.g. `https://<your-vercel-domain>` (include custom domains if attached, comma-separated, no trailing slash, no `*`).
3. Trigger a redeploy / restart so `Settings` loads the updated `ALLOWED_ORIGINS`.

### Step 4: Post-Deploy Verification
1. `curl https://<your-backend-domain>/health` → HTTP `200`.
2. `curl "https://<your-backend-domain>/api/v1/air-quality/current?city=New%20Delhi"` → HTTP `200`, `index_type: "INDICATIVE_MODEL_INDEX"`, `is_official_cpcb_station_aqi: false`.
3. Open `https://<your-vercel-domain>` in a browser over HTTPS and confirm zero CORS/console errors across Dashboard, Comparison, Historical, Action Studio, and AI Assistant.

---

## 4. Production Startup Commands (Container / Standalone)

- **Backend**:
  ```bash
  uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
  ```
- **Frontend**:
  ```bash
  npm run build && npm run start -- -p ${PORT:-3000}
  ```

---

## 5. Rollback Instructions

### Frontend (Vercel)
1. Open Vercel Project → **Deployments**.
2. Locate the previous known-good production deployment and select **⋯ → Instant Rollback** (or **Promote to Production**).

### Backend (Render / Container Registry)
1. Open Render Dashboard → **Events** / **Deploys**.
2. Click **Rollback to this deploy** on the last verified image/commit, or revert the commit on the release branch (`git revert <bad-sha>`) and redeploy.
3. Verify `/health` returns `200` and `/api/v1/air-quality/current?city=New%20Delhi` succeeds before closing the incident.
