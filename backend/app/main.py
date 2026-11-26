"""AirAware AI Backend Application Entrypoint (Stage 3.1 Production Pipeline)."""

from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_ai import router as ai_router
from app.api.routes_air_quality import router as air_quality_router
from app.api.routes_comparison import router as comparison_router
from app.api.routes_historical import router as historical_router
from app.api.routes_recommendations import router as recommendations_router
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AirAware AI Backend initialized (config=%s)", json.dumps(settings.safe_summary()))
    yield
    logger.info("AirAware AI Backend shutting down.")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Production backend for AirAware AI. Processes Open-Meteo Copernicus CAMS Global atmospheric grid data "
        "through gap-aware piecewise-linear trapezoidal integration and exposes clearly labelled INDICATIVE_MODEL_INDEX outputs."
    ),
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

BASELINE_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def apply_security_headers(response: Response, path: str) -> Response:
    """Attach canonical security headers and API no-store caching directive."""
    for name, value in BASELINE_SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    if path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def apply_cors_headers(response: Response, request: Request) -> Response:
    """Apply configured CORS headers on error responses that bypass CORSMiddleware."""
    origin = request.headers.get("origin")
    if not origin:
        return response

    allow_all = "*" in settings.allowed_origins
    if allow_all:
        response.headers.setdefault("Access-Control-Allow-Origin", "*")
        if allow_creds:
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")
    elif origin in settings.allowed_origins:
        response.headers.setdefault("Access-Control-Allow-Origin", origin)
        if allow_creds:
            response.headers.setdefault("Access-Control-Allow-Credentials", "true")

    existing_vary = response.headers.get("Vary", "")
    vary_tokens = [v.strip() for v in existing_vary.split(",") if v.strip()]
    if "Origin" not in vary_tokens:
        vary_tokens.append("Origin")
        response.headers["Vary"] = ", ".join(vary_tokens)
    return response


# Environment-driven CORS configuration (added first so security middleware wraps preflight responses too)
allow_creds = "*" not in settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=allow_creds,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Attach baseline security headers to every HTTP response without altering CORS."""
    response = await call_next(request)
    return apply_security_headers(response, request.url.path)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Safe global error handler suppressing raw tracebacks while preserving security and CORS headers."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    response = JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected internal error occurred while processing the air quality request.",
        },
    )
    apply_security_headers(response, request.url.path)
    return apply_cors_headers(response, request)


@app.get("/health", tags=["System"])
async def health_check():
    """System health check disclosing model-derived index designation."""
    return {
        "status": "healthy",
        "service": "AirAware AI Backend",
        "version": settings.app_version,
        "environment": settings.environment,
        "aqi_standard": "CPCB India National AQI Breakpoints (Indicative Model Index Only)",
        "index_type": "INDICATIVE_MODEL_INDEX",
        "provider": "Open-Meteo Copernicus CAMS Global (Modelled Atmospheric Grid)",
    }


# Include v1 Routers
app.include_router(air_quality_router, prefix="/api/v1")
app.include_router(historical_router, prefix="/api/v1")
app.include_router(comparison_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
