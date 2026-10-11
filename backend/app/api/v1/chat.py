from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_chat_service, get_sessions
from app.core.rate_limit import limit
from app.core.security import Principal, current_principal
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.crop_names import normalize_crop
from app.services.session_store import SessionStore

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(limit("general")), Depends(limit("chat"))])
async def chat(
    body: ChatRequest,
    principal: Annotated[Principal, Depends(current_principal)],
    service: Annotated[ChatService, Depends(get_chat_service)],
    sessions: Annotated[SessionStore, Depends(get_sessions)],
) -> ChatResponse:
    session = None
    if body.session_id is not None:
        session = await sessions.get(str(body.session_id), principal.owner)
        if session is None:
            raise HTTPException(404, "That conversation has ended. Please start a new one.")
    body.crop = normalize_crop(body.crop)
    return await service.run(principal.owner, body, session, user_id=principal.user_id)
