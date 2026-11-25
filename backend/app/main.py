"""AirAware AI Backend Application Entrypoint (Stage 3.1 Production Pipeline)."""

from contextlib import asynccontextmanager
import json
from fastapi import FastAPI, Request
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

# Environment-driven CORS configuration
allow_creds = "*" not in settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=allow_creds,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Safe global error handler suppressing raw tracebacks from external API responses."""
    logger.error("Unhandled error on %s %s: %s", request.method, request.url.path, type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected internal error occurred while processing the air quality request.",
        },
    )


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
