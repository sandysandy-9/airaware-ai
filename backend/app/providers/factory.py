"""Provider factory and standard Indian cities registry."""

from typing import Dict, List, Optional
from app.providers.base import BaseAirQualityProvider
from app.providers.open_meteo import OpenMeteoProvider


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
    """Resolve city name or geographic coordinates into standard location dict."""
    if city_name:
        key = city_name.lower().strip()
        if key in MAJOR_INDIAN_CITIES:
            return MAJOR_INDIAN_CITIES[key]
        for c_key, c_info in MAJOR_INDIAN_CITIES.items():
            if key in c_info["name"].lower() or key in c_key:
                return c_info

    if latitude is not None and longitude is not None:
        # Check closest city if within 25km
        closest = None
        min_dist_sq = 1e9
        for c in MAJOR_INDIAN_CITIES.values():
            dist_sq = (c["lat"] - latitude) ** 2 + (c["lon"] - longitude) ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest = c
        if closest and min_dist_sq < 0.2:  # roughly 20-30 km
            return closest
        return {
            "name": f"Location ({latitude:.3f}, {longitude:.3f})",
            "city": "Custom Location",
            "state": "India",
            "lat": latitude,
            "lon": longitude,
        }

    # Default to Delhi if unspecified
    return MAJOR_INDIAN_CITIES["delhi"]
