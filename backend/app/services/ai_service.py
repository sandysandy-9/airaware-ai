"""Grounded AI Air Quality Assistant Service.

Uses verified environmental data as immutable ground truth.
Includes Gemini API integration and an intelligent offline deterministic fallback.
"""

import os
from typing import Dict, List, Optional
import httpx

from app.engine.cpcb_breakpoints import AQI_CATEGORIES, POLLUTANT_INFO
from app.engine.recommendation_rules import generate_recommendations
from app.schemas.ai_chat import AIChatRequest, AIChatResponse, ChatMessage
from app.schemas.air_quality import AirQualityCurrentResponse


class AIAssistantService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "").strip()

    def _assemble_grounded_context(
        self,
        ctx: Optional[AirQualityCurrentResponse],
        compare_ctx: Optional[List[AirQualityCurrentResponse]] = None,
    ) -> str:
        if not ctx and not compare_ctx:
            return "No specific location data is currently selected."

        lines = ["=== VERIFIED ENVIRONMENTAL CONTEXT (GROUND TRUTH) ==="]

        if ctx:
            lines.append(f"Primary Location: {ctx.location.name} ({ctx.location.city}, {ctx.location.state or 'India'})")
            lines.append(f"Coordinates: {ctx.location.latitude}, {ctx.location.longitude}")
            lines.append(f"Calculated CPCB AQI: {ctx.aqi} ({ctx.category or 'Unknown Category'})")
            lines.append(f"Dominant Pollutant: {ctx.dominant_pollutant_name or ctx.dominant_pollutant or 'None'}")
            lines.append(f"Data Source: {ctx.data_source}")
            lines.append(f"Observation Time: {ctx.observation_time}")
            lines.append(f"Data Freshness: {ctx.data_freshness}")
            lines.append("\nMeasured Criteria Pollutants:")
            for p_code, p_data in ctx.pollutants.items():
                if p_data.is_missing:
                    lines.append(f"  - {p_data.name} ({p_code}): Sensor Unavailable / Not Monitored")
                else:
                    lines.append(f"  - {p_data.name} ({p_code}): {p_data.concentration} {p_data.unit} (Sub-index: {p_data.sub_index}, Category: {p_data.category})")

        if compare_ctx:
            lines.append("\nComparison Locations Context:")
            for c in compare_ctx:
                lines.append(f"  - {c.location.name}: AQI {c.aqi} ({c.category}), Dominant: {c.dominant_pollutant}, Observed: {c.observation_time}")

        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)

    def _deterministic_grounded_reply(
        self,
        prompt: str,
        ctx: Optional[AirQualityCurrentResponse],
        compare_ctx: Optional[List[AirQualityCurrentResponse]] = None,
    ) -> AIChatResponse:
        """Deterministic response engine grounded strictly in verified data without LLM hallucination."""
        lower_q = prompt.lower()
        sources = ["Central Pollution Control Board (CPCB) NAQI Guidelines", "Open-Meteo Copernicus CAMS"]

        if not ctx and not compare_ctx:
            return AIChatResponse(
                reply=(
                    "Welcome to AirAware AI! Please select a location from the dashboard (e.g. New Delhi, Mumbai, Bengaluru) "
                    "or enter custom coordinates to view verified real-time air quality readings and personalized precautions."
                ),
                grounded_in_data=True,
                model_used="deterministic-rules-engine",
                sources_cited=sources,
            )

        # 1. Comparison query
        if compare_ctx and any(w in lower_q for w in ["compare", "difference", "cleaner", "worse", "better", "versus", "vs"]):
            items_str = []
            for c in compare_ctx:
                items_str.append(f"• **{c.location.name}**: AQI {c.aqi} ({c.category or 'N/A'}) - Dominant: {c.dominant_pollutant_name or c.dominant_pollutant}")
            
            cleanest = min([c for c in compare_ctx if c.aqi is not None], key=lambda x: x.aqi, default=None)
            highest = max([c for c in compare_ctx if c.aqi is not None], key=lambda x: x.aqi, default=None)
            
            summary = (
                f"### Location Air Quality Comparison\n\n"
                + "\n".join(items_str) + "\n\n"
            )
            if cleanest and highest and cleanest != highest:
                summary += f"Currently, **{cleanest.location.name}** has the lowest recorded AQI ({cleanest.aqi}), while **{highest.location.name}** has the highest ({highest.aqi}). Note: Always check individual observation timestamps before comparing freshness."
            
            return AIChatResponse(
                reply=summary,
                grounded_in_data=True,
                model_used="deterministic-rules-engine",
                sources_cited=sources,
            )

        if not ctx:
            return AIChatResponse(
                reply="Please select an active location to inspect its specific pollutant metrics.",
                grounded_in_data=True,
                model_used="deterministic-rules-engine",
                sources_cited=sources,
            )

        aqi = ctx.aqi
        cat = ctx.category or "Unknown"
        dom = ctx.dominant_pollutant_name or ctx.dominant_pollutant or "criteria pollutants"
        loc_name = ctx.location.name

        # 2. Dominant pollutant inquiry
        if any(w in lower_q for w in ["dominant", "which pollutant", "contributing most", "main pollutant", "driver"]):
            dom_detail = ctx.pollutants.get(ctx.dominant_pollutant or "")
            conc_str = f"{dom_detail.concentration} {dom_detail.unit}" if dom_detail and dom_detail.concentration is not None else "measured level"
            sub_str = f"with an individual sub-index of {dom_detail.sub_index}" if dom_detail and dom_detail.sub_index else ""
            reply = (
                f"In **{loc_name}**, the dominant pollutant driving the current AQI is **{dom}** ({ctx.dominant_pollutant.upper() if ctx.dominant_pollutant else ''}).\n\n"
                f"• **Current Concentration**: {conc_str} {sub_str}.\n"
                f"• **Significance**: Under CPCB methodology, the overall AQI is dictated by the highest sub-index among monitored criteria pollutants.\n"
                f"• **Health Impact**: {dom_detail.health_effects if dom_detail else 'Prolonged exposure may trigger airway irritation.'}\n"
                f"• **Typical Sources**: {dom_detail.sources if dom_detail else 'Combustion and ambient particulate sources.'}"
            )
            return AIChatResponse(
                reply=reply,
                grounded_in_data=True,
                model_used="deterministic-rules-engine",
                sources_cited=sources,
            )

        # 3. Meaning of AQI / What does it mean
        if any(w in lower_q for w in ["what does", "mean", "meaning", "explain aqi", "is it safe", "how bad"]):
            cat_info = AQI_CATEGORIES.get(cat, {})
            reply = (
                f"The current CPCB Air Quality Index in **{loc_name}** is **{aqi}**, classified as **{cat}**.\n\n"
                f"• **CPCB Classification**: {cat_info.get('description', 'Standard environmental benchmark')}.\n"
                f"• **Health Advisory**: {cat_info.get('advisory', 'Limit prolonged outdoor exertion if vulnerable.')}\n"
                f"• **Key Driver**: {dom} is currently the primary contributor.\n"
                f"• **Data Provenance**: Measured at {ctx.observation_time} via {ctx.data_source}."
            )
            return AIChatResponse(
                reply=reply,
                grounded_in_data=True,
                model_used="deterministic-rules-engine",
                sources_cited=sources,
            )

        # 4. Precautions, exercise, sports, outdoor activity
        if any(w in lower_q for w in ["precaution", "exercise", "running", "jogging", "walk", "sport", "mask", "outdoors", "outside"]):
            recs = generate_recommendations(
                aqi_category=cat,
                aqi=aqi,
                dominant_pollutant=ctx.dominant_pollutant,
                activity="running" if ("run" in lower_q or "sport" in lower_q or "jog" in lower_q) else "walking",
                vulnerability_group="respiratory" if ("asthma" in lower_q or "breath" in lower_q or "lung" in lower_q) else "general",
            )
            precautions_md = "\n".join([f"• {p}" for p in recs.actionable_precautions])
            reply = (
                f"### Evidence-Based Health Guidance for {loc_name} (AQI: {aqi} - {cat})\n\n"
                f"**Headline**: {recs.headline}\n\n"
                f"**Recommended Actionable Steps**:\n{precautions_md}\n\n"
                f"• **Respiratory Protection**: {recs.protective_gear or 'None mandatory.'}\n"
                f"• **Indoor Environment**: {recs.indoor_guidance}\n\n"
                f"> *Note: {recs.disclaimer}*"
            )
            return AIChatResponse(
                reply=reply,
                grounded_in_data=True,
                model_used="deterministic-rules-engine",
                sources_cited=sources,
            )

        # 5. Default grounded environmental summary
        missing_list = [p.name for p in ctx.pollutants.values() if p.is_missing]
        missing_note = f" (Sensors currently unavailable: {', '.join(missing_list)})" if missing_list else ""
        reply = (
            f"Here is the verified environmental intelligence for **{loc_name}**:\n\n"
            f"• **Overall CPCB AQI**: **{aqi}** ({cat})\n"
            f"• **Dominant Pollutant**: {dom}\n"
            f"• **PM2.5**: {ctx.pollutants.get('pm25', {}).concentration or 'N/A'} µg/m³\n"
            f"• **PM10**: {ctx.pollutants.get('pm10', {}).concentration or 'N/A'} µg/m³\n"
            f"• **Observed**: {ctx.observation_time} ({ctx.data_freshness})\n"
            f"• **Data Source**: {ctx.data_source}{missing_note}\n\n"
            f"You can ask me about specific precautions, outdoor exercise safety, pollutant sources, or compare with other cities."
        )
        return AIChatResponse(
            reply=reply,
            grounded_in_data=True,
            model_used="deterministic-rules-engine",
            sources_cited=sources,
        )

    async def generate_response(self, req: AIChatRequest) -> AIChatResponse:
        """Generate grounded response via Gemini LLM if configured, or failover gracefully to deterministic engine."""
        grounded_context = self._assemble_grounded_context(req.current_context, req.comparison_context)

        # If no Gemini API key, use verified deterministic engine
        if not self.api_key:
            return self._deterministic_grounded_reply(req.message, req.current_context, req.comparison_context)

        # Gemini API call with strict grounding instructions
        system_instruction = (
            "You are AirAware AI, an authoritative urban air quality intelligence assistant. "
            "You MUST ONLY interpret the verified data provided in the context below. "
            "STRICT RULES:\n"
            "1. NEVER invent or fabricate pollutant readings, AQI values, or timestamps.\n"
            "2. Never override the pre-calculated CPCB AQI or category provided in the context.\n"
            "3. If a pollutant measurement is missing or sensor is unavailable, explicitly state that it is not monitored.\n"
            "4. Provide practical, evidence-based health guidance adhering to CPCB and WHO guidelines.\n"
            "5. Never provide medical diagnoses, treatment prescriptions, or absolute guarantees of safety.\n"
            "6. Always state the data source and observation time when discussing readings.\n\n"
            f"{grounded_context}"
        )

        gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

        contents = []
        for msg in (req.chat_history or [])[-6:]:
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        contents.append({"role": "user", "parts": [{"text": req.message}]})

        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.post(gemini_url, json=payload)
                if res.status_code == 200:
                    resp_json = res.json()
                    candidates = resp_json.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        return AIChatResponse(
                            reply=text,
                            grounded_in_data=True,
                            model_used="gemini-1.5-flash",
                            sources_cited=["CPCB NAQI Standard", "Open-Meteo Copernicus CAMS"],
                        )
        except Exception:
            pass  # Failover to deterministic

        # Graceful fallback to verified deterministic engine
        return self._deterministic_grounded_reply(req.message, req.current_context, req.comparison_context)


ai_assistant_service = AIAssistantService()
