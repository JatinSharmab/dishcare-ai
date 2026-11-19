from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.exceptions import BusinessError
from app.core.security import get_current_customer
from app.schemas.conversation import (
    ChatRequest,
    ChatResponse,
)


router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Agentic AI"],
)


@router.post(
    "",
    response_model=ChatResponse,
)
async def chat(
    payload: ChatRequest,
    request: Request,
    customer_id: Annotated[
        str,
        Depends(get_current_customer),
    ],
):

    engine = getattr(
        request.app.state,
        "chat_engine",
        None,
    )

    if engine is None:

        raise BusinessError(
            503,
            "AI_DISABLED",
            "The AI service is not enabled",
        )

    return await engine.chat(
        customer_id=customer_id,
        message=payload.message,
        session_id=payload.session_id,
    )