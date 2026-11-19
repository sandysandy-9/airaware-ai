"""API Integration and Security tests using FastAPI TestClient."""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Verify system health check."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "CPCB" in data["aqi_standard"]


def test_list_cities():
    """Verify pre-configured Indian cities endpoint."""
    response = client.get("/api/v1/air-quality/cities")
    assert response.status_code == 200
    cities = response.json()
    assert len(cities) >= 10
    city_names = [c["name"] for c in cities]
    assert "New Delhi" in city_names
    assert "Mumbai" in city_names
    assert "Bengaluru" in city_names


def test_recommendations_endpoint():
    """Verify deterministic recommendation endpoint."""
    payload = {
        "city": "New Delhi",
        "activity": "running",
        "vulnerability_group": "respiratory",
        "duration": "1-2h",
        "aqi": 280,
        "aqi_category": "POOR",
        "dominant_pollutant": "pm25",
    }
    response = client.post("/api/v1/recommendations", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["aqi"] == 280
    assert data["aqi_category"] == "POOR"
    assert data["advisory_level"] == "VERY_HIGH_RISK"
    assert len(data["actionable_precautions"]) > 0
    assert "N95" in data["protective_gear"]


def test_ai_chat_offline_grounded():
    """Verify AI chat assistant provides deterministic, data-grounded answers without external LLM."""
    payload = {
        "message": "Which pollutant is contributing most?",
        "current_context": {
            "location": {
                "name": "Anand Vihar, Delhi",
                "city": "Delhi",
                "latitude": 28.65,
                "longitude": 77.30,
            },
            "aqi": 340,
            "category": "VERY_POOR",
            "dominant_pollutant": "pm25",
            "dominant_pollutant_name": "Particulate Matter ≤ 2.5 µm",
            "status": "SUCCESS",
            "status_message": "Valid CPCB NAQI calculated successfully.",
            "observation_time": "2026-11-19T08:00:00Z",
            "retrieval_time": "2026-11-19T08:15:00Z",
            "data_source": "Open-Meteo Copernicus CAMS",
            "data_freshness": "LIVE (< 1h)",
            "pollutants": {
                "pm25": {
                    "code": "pm25",
                    "name": "Particulate Matter ≤ 2.5 µm",
                    "concentration": 185.0,
                    "unit": "µg/m³",
                    "sub_index": 340,
                    "category": "VERY_POOR",
                    "is_missing": False,
                    "description": "Fine particles",
                    "health_effects": "Respiratory illness",
                    "sources": "Vehicular exhaust and burning",
                }
            },
        },
    }
    response = client.post("/api/v1/ai/chat", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["grounded_in_data"] is True
    assert "pm25" in data["reply"].lower() or "particulate matter" in data["reply"].lower()
    assert "340" in data["reply"] or "185" in data["reply"]


def test_coordinate_validation_bounds():
    """Security/Validation: verify invalid coordinates are rejected by Pydantic validation."""
    # Latitude > 90
    response = client.get("/api/v1/air-quality/current?latitude=120.0&longitude=77.0")
    assert response.status_code == 422

    # Longitude < -180
    response = client.get("/api/v1/air-quality/current?latitude=28.0&longitude=-250.0")
    assert response.status_code == 422
