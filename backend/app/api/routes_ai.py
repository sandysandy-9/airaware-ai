"""API routes for Grounded AI Air Quality Assistant."""

from fastapi import APIRouter
from app.schemas.ai_chat import AIChatRequest, AIChatResponse
from app.services.ai_service import ai_assistant_service

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post("/chat", response_model=AIChatResponse)
async def chat_with_assistant(req: AIChatRequest):
    """Interact with the grounded air quality AI assistant."""
    return await ai_assistant_service.generate_response(req)
