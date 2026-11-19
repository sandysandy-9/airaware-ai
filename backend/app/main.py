"""AirAware AI Backend Application Entrypoint."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

from app.api.routes_air_quality import router as air_quality_router
from app.api.routes_historical import router as historical_router
from app.api.routes_comparison import router as comparison_router
from app.api.routes_recommendations import router as recommendations_router
from app.api.routes_ai import router as ai_router

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    print("AirAware AI Backend initialized.")
    yield
    # Shutdown tasks
    print("AirAware AI Backend shutting down.")


app = FastAPI(
    title="AirAware AI — Urban Air Quality Intelligence Platform",
    description=(
        "Production-ready backend for AirAware AI. Transforms real environmental data into "
        "understandable, location-aware, actionable intelligence using official CPCB NAQI methodology."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration
origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Exception Handler to avoid exposing raw stack traces in production
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred while processing the air quality request.",
            "detail": str(exc) if os.getenv("DEBUG", "false").lower() == "true" else None,
        },
    )


# Health check
@app.get("/health", tags=["System"])
async def health_check():
    return {
        "status": "healthy",
        "service": "AirAware AI Backend",
        "aqi_standard": "CPCB India National AQI (NAQI)",
        "provider": "Open-Meteo Copernicus CAMS (Real In-Situ & Reanalysis)",
    }


# Include v1 Routers
app.include_router(air_quality_router, prefix="/api/v1")
app.include_router(historical_router, prefix="/api/v1")
app.include_router(comparison_router, prefix="/api/v1")
app.include_router(recommendations_router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
