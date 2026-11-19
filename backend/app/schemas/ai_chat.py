"""Schemas for Grounded AI Air Quality Assistant."""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.air_quality import AirQualityCurrentResponse


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AIChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    current_context: Optional[AirQualityCurrentResponse] = None
    comparison_context: Optional[List[AirQualityCurrentResponse]] = None
    chat_history: Optional[List[ChatMessage]] = Field(default_factory=list)


class AIChatResponse(BaseModel):
    reply: str
    grounded_in_data: bool = True
    model_used: str  # "gemini-1.5-pro", "gemini-1.5-flash", "deterministic-engine"
    sources_cited: List[str]
    disclaimer: str = (
        "AI assistant interprets real verified measurements and CPCB health guidance. "
        "It cannot prescribe medical therapies or override laboratory-grade sensor data."
    )
