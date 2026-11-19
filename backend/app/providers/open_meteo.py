"""Open-Meteo Copernicus CAMS Real Environmental Data Provider."""

from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx

from app.engine.cpcb_calculator import calculate_cpcb_aqi, calculate_sub_index
from app.engine.cpcb_breakpoints import POLLUTANT_INFO
from app.providers.base import BaseAirQualityProvider
from app.schemas.air_quality import (
    AirQualityCurrentResponse,
    HistoricalPoint,
    HistoricalTrendsResponse,
    LocationInfo,
    PollutantDetail,
)


class OpenMeteoProvider(BaseAirQualityProvider):
    name = "Open-Meteo (Copernicus CAMS & In-Situ Atmospheric Observations)"
    BASE_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

    async def get_current_air_quality(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        city: Optional[str] = None,
    ) -> AirQualityCurrentResponse:
        now_iso = datetime.now(timezone.utc).isoformat()
        resolved_city = city or location_name

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "timezone": "auto",
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            # Handle upstream failure gracefully without fabricating mock data
            return AirQualityCurrentResponse(
                location=LocationInfo(
                    name=location_name,
                    city=resolved_city,
                    latitude=latitude,
                    longitude=longitude,
                ),
                aqi=None,
                category=None,
                color=None,
                dominant_pollutant=None,
                dominant_pollutant_name=None,
                status="ERROR",
                status_message=f"Environmental data source unavailable: {str(e)}",
                observation_time=now_iso,
                retrieval_time=now_iso,
                data_source=self.name,
                data_freshness="UNAVAILABLE",
                pollutants={},
            )

        current = data.get("current", {})
        obs_time = current.get("time", now_iso)

        # Raw values from API
        raw_pm25 = current.get("pm2_5")
        raw_pm10 = current.get("pm10")
        raw_no2 = current.get("nitrogen_dioxide")
        raw_so2 = current.get("sulphur_dioxide")
        raw_co_ug = current.get("carbon_monoxide")
        raw_o3 = current.get("ozone")

        # Conversion: Open-Meteo returns CO in µg/m³; CPCB uses mg/m³
        co_mg = (raw_co_ug / 1000.0) if raw_co_ug is not None else None

        # Build concentration dict for CPCB calculation
        concentrations: Dict[str, Optional[float]] = {
            "pm25": float(raw_pm25) if raw_pm25 is not None else None,
            "pm10": float(raw_pm10) if raw_pm10 is not None else None,
            "no2": float(raw_no2) if raw_no2 is not None else None,
            "so2": float(raw_so2) if raw_so2 is not None else None,
            "co": float(co_mg) if co_mg is not None else None,
            "o3": float(raw_o3) if raw_o3 is not None else None,
            "nh3": None,  # Not provided in standard open-meteo hourly feed
            "pb": None,   # Lead is only sampled periodically via filter gravimetry
        }

        # Calculate official CPCB NAQI
        cpcb_result = calculate_cpcb_aqi(concentrations)

        # Build detailed pollutant representations
        pollutant_details: Dict[str, PollutantDetail] = {}
        for pol_code, sub_res in cpcb_result.sub_indices.items():
            meta = POLLUTANT_INFO.get(pol_code, {})
            is_miss = not sub_res.valid or (sub_res.concentration == 0.0 and sub_res.error is not None)
            conc_val = sub_res.concentration if not is_miss else None

            pollutant_details[pol_code] = PollutantDetail(
                code=pol_code,
                name=meta.get("name", pol_code.upper()),
                concentration=conc_val,
                unit=sub_res.unit,
                sub_index=sub_res.sub_index if sub_res.valid else None,
                category=sub_res.category if sub_res.valid else None,
                color=sub_res.color if sub_res.valid else None,
                is_missing=is_miss,
                error=sub_res.error,
                description=meta.get("description", ""),
                health_effects=meta.get("health_effects", ""),
                sources=meta.get("primary_sources", ""),
            )

        dom_name = None
        if cpcb_result.dominant_pollutant:
            dom_name = POLLUTANT_INFO.get(cpcb_result.dominant_pollutant, {}).get("name")

        return AirQualityCurrentResponse(
            location=LocationInfo(
                name=location_name,
                city=resolved_city,
                latitude=latitude,
                longitude=longitude,
            ),
            aqi=cpcb_result.aqi,
            category=cpcb_result.category,
            color=cpcb_result.color,
            dominant_pollutant=cpcb_result.dominant_pollutant,
            dominant_pollutant_name=dom_name,
            status=cpcb_result.status,
            status_message=cpcb_result.status_message,
            observation_time=obs_time,
            retrieval_time=now_iso,
            data_source=self.name,
            data_freshness="LIVE (< 1h)",
            pollutants=pollutant_details,
        )

    async def get_historical_air_quality(
        self,
        location_name: str,
        latitude: float,
        longitude: float,
        past_days: int = 7,
    ) -> HistoricalTrendsResponse:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
            "past_days": max(1, min(30, past_days)),
            "timezone": "auto",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        pm25_list = hourly.get("pm2_5", [])
        pm10_list = hourly.get("pm10", [])
        no2_list = hourly.get("nitrogen_dioxide", [])
        so2_list = hourly.get("sulphur_dioxide", [])
        co_list = hourly.get("carbon_monoxide", [])
        o3_list = hourly.get("ozone", [])

        points: List[HistoricalPoint] = []
        for i, t in enumerate(times):
            p25 = pm25_list[i] if i < len(pm25_list) else None
            p10 = pm10_list[i] if i < len(pm10_list) else None
            no2 = no2_list[i] if i < len(no2_list) else None
            so2 = so2_list[i] if i < len(so2_list) else None
            co_ug = co_list[i] if i < len(co_list) else None
            co_mg = (co_ug / 1000.0) if co_ug is not None else None
            o3 = o3_list[i] if i < len(o3_list) else None

            # Calculate CPCB AQI for this historical hour
            concs = {
                "pm25": p25,
                "pm10": p10,
                "no2": no2,
                "so2": so2,
                "co": co_mg,
                "o3": o3,
            }
            cpcb_res = calculate_cpcb_aqi(concs)

            points.append(
                HistoricalPoint(
                    timestamp=t,
                    aqi=cpcb_res.aqi,
                    pm25=round(p25, 1) if p25 is not None else None,
                    pm10=round(p10, 1) if p10 is not None else None,
                    no2=round(no2, 1) if no2 is not None else None,
                    so2=round(so2, 1) if so2 is not None else None,
                    co=round(co_mg, 2) if co_mg is not None else None,
                    o3=round(o3, 1) if o3 is not None else None,
                    dominant_pollutant=cpcb_res.dominant_pollutant,
                )
            )

        start_time = times[0] if times else ""
        end_time = times[-1] if times else ""

        return HistoricalTrendsResponse(
            location=LocationInfo(
                name=location_name,
                city=location_name,
                latitude=latitude,
                longitude=longitude,
            ),
            start_time=start_time,
            end_time=end_time,
            data_source=self.name,
            interval="1 hour",
            data_points=points,
            total_points=len(points),
        )
