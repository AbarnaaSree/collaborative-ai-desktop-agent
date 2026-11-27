import httpx

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.models import User
from app.schemas.ai_chat import AIChatRequest, AIChatResponse
from app.services.openrouter_service import generate_ai_reply


router = APIRouter(
    prefix="/ai",
    tags=["AI Assistant"],
)


@router.post(
    "/chat",
    response_model=AIChatResponse,
    status_code=status.HTTP_200_OK,
)
async def chat_with_ai(
    request: AIChatRequest,
    current_user: User = Depends(get_current_user),
):
    """Send a message to the authenticated user's AI assistant."""

    try:
        reply = await generate_ai_reply(request.message)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider could not process the request",
        ) from error

    return AIChatResponse(
        reply=reply,
        model=settings.OPENROUTER_MODEL,
    )
