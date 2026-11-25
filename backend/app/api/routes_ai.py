"""API routes for Stage 3.2 Server-Grounded AI Air Quality Assistant."""

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes_air_quality import provider_error_to_http_exception, reject_client_override_params
from app.core.rate_limiter import enforce_rate_limit
from app.providers.models import ProviderError, ProviderValidationError
from app.schemas.ai_chat import AIChatRequest, AIChatResponse
from app.services.ai_service import ai_assistant_service

router = APIRouter(prefix="/ai", tags=["AI Assistant"])


@router.post(
    "/chat",
    response_model=AIChatResponse,
    dependencies=[Depends(enforce_rate_limit), Depends(reject_client_override_params)],
)
async def chat_with_assistant(req: AIChatRequest):
    """Answer air-quality questions strictly grounded in backend-assessed data with deterministic fallback."""
    try:
        return await ai_assistant_service.generate_response(req)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"error": "InvalidLocationQuery", "message": str(exc)},
        ) from exc
    except (ProviderError, ProviderValidationError) as exc:
        raise provider_error_to_http_exception(exc, "/ai/chat") from exc
