"""Provider factory and standard Indian cities registry."""

import re
from typing import Dict, Optional
import unicodedata
from app.providers.base import BaseAirQualityProvider
from app.providers.open_meteo import OpenMeteoProvider

MAX_CITY_NAME_LENGTH = 64
_SAFE_CITY_PATTERN = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,63}$")
_DISALLOWED_CITY_PHRASES = (
    "ignore",
    "instruction",
    "override",
    "pretend",
    "system prompt",
    "reveal",
    "api key",
    "prescribe",
    "aqi",
    "cpcb station",
)


def validate_city_input(city_name: str) -> str:
    """Validate and sanitize client-supplied city strings against instruction/control injection."""
    if not isinstance(city_name, str):
        raise ValueError("City name must be a string.")
    for ch in city_name:
        if ord(ch) < 32 or unicodedata.category(ch).startswith("C"):
            raise ValueError("City name contains disallowed control or formatting characters.")
    cleaned = city_name.strip()
    if not cleaned:
        raise ValueError("City name must not be empty.")
    if len(cleaned) > MAX_CITY_NAME_LENGTH:
        raise ValueError(f"City name exceeds maximum length ({MAX_CITY_NAME_LENGTH} characters).")
    if not _SAFE_CITY_PATTERN.match(cleaned):
        raise ValueError(
            "City name contains unsupported characters. Use letters, spaces, hyphens, or apostrophes only."
        )
    lowered = cleaned.lower()
    for phrase in _DISALLOWED_CITY_PHRASES:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered):
            raise ValueError("City name contains disallowed instruction-like phrasing.")
    return cleaned


MAJOR_INDIAN_CITIES: Dict[str, Dict] = {
    "delhi": {"name": "New Delhi", "city": "Delhi", "state": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "mumbai": {"name": "Mumbai", "city": "Mumbai", "state": "Maharashtra", "lat": 19.0760, "lon": 72.8777},
    "bengaluru": {"name": "Bengaluru", "city": "Bengaluru", "state": "Karnataka", "lat": 12.9716, "lon": 77.5946},
    "kolkata": {"name": "Kolkata", "city": "Kolkata", "state": "West Bengal", "lat": 22.5726, "lon": 88.3639},
    "chennai": {"name": "Chennai", "city": "Chennai", "state": "Tamil Nadu", "lat": 13.0827, "lon": 80.2707},
    "hyderabad": {"name": "Hyderabad", "city": "Hyderabad", "state": "Telangana", "lat": 17.3850, "lon": 78.4867},
    "ahmedabad": {"name": "Ahmedabad", "city": "Ahmedabad", "state": "Gujarat", "lat": 23.0225, "lon": 72.5714},
    "pune": {"name": "Pune", "city": "Pune", "state": "Maharashtra", "lat": 18.5204, "lon": 73.8567},
    "lucknow": {"name": "Lucknow", "city": "Lucknow", "state": "Uttar Pradesh", "lat": 26.8467, "lon": 80.9462},
    "jaipur": {"name": "Jaipur", "city": "Jaipur", "state": "Rajasthan", "lat": 26.9124, "lon": 75.7873},
    "patna": {"name": "Patna", "city": "Patna", "state": "Bihar", "lat": 25.5941, "lon": 85.1376},
    "chandigarh": {"name": "Chandigarh", "city": "Chandigarh", "state": "Punjab / Haryana", "lat": 30.7333, "lon": 76.7794},
    "varanasi": {"name": "Varanasi", "city": "Varanasi", "state": "Uttar Pradesh", "lat": 25.3176, "lon": 82.9739},
    "kochi": {"name": "Kochi", "city": "Kochi", "state": "Kerala", "lat": 9.9312, "lon": 76.2673},
    "bhopal": {"name": "Bhopal", "city": "Bhopal", "state": "Madhya Pradesh", "lat": 23.2599, "lon": 77.4126},
}


def get_default_provider() -> BaseAirQualityProvider:
    """Return default active air quality provider."""
    return OpenMeteoProvider()


def resolve_location(
    city_name: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict:
    """Resolve city name or exact geographic coordinates without trusting raw client display strings."""
    if (latitude is None) != (longitude is None) and not city_name:
        raise ValueError("Both 'latitude' and 'longitude' must be provided when querying by coordinates.")

    validated_city = validate_city_input(city_name) if city_name is not None else None

    if latitude is not None and longitude is not None:
        # Preserve exact requested coordinates and emit ONLY a neutral server-generated display label.
        display_name = f"Custom Coordinates ({latitude:.4f}, {longitude:.4f})"
        city_label = "Custom Coordinates"
        state_label = "India"
        for c in MAJOR_INDIAN_CITIES.values():
            dist_sq = (c["lat"] - latitude) ** 2 + (c["lon"] - longitude) ** 2
            if dist_sq < 0.05:  # within ~25 km reference label only
                city_label = c["city"]
                state_label = c["state"]
                display_name = f"Near {c['name']} ({latitude:.4f}, {longitude:.4f})"
                break
        return {
            "name": display_name,
            "city": city_label,
            "state": state_label,
            "lat": float(latitude),
            "lon": float(longitude),
        }

    if validated_city:
        key = validated_city.lower()
        if key in MAJOR_INDIAN_CITIES:
            return MAJOR_INDIAN_CITIES[key]
        for c_key, c_info in MAJOR_INDIAN_CITIES.items():
            if key in c_info["name"].lower() or key in c_key:
                return c_info
        raise ValueError(
            f"Unknown city '{validated_city}'. Choose a supported city from /api/v1/air-quality/cities or supply latitude and longitude."
        )

    # Default to Delhi reference coordinates if unspecified
    return MAJOR_INDIAN_CITIES["delhi"]
