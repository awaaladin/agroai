from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict

from app.api.deps import get_sessions
from app.core.rate_limit import limit
from app.core.security import current_device
from app.services.session_store import SessionStore
from app.services.share_card import build_share_card

router = APIRouter(tags=["session"])


class ShareCardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID


class ShareCardResponse(BaseModel):
    session_id: str
    text: str  # plain text, ready for the Web Share API or a wa.me/?text= link


@router.post("/share-card", response_model=ShareCardResponse, dependencies=[Depends(limit("general"))])
async def share_card(
    body: ShareCardRequest,
    device_id: Annotated[str, Depends(current_device)],
    sessions: Annotated[SessionStore, Depends(get_sessions)],
) -> ShareCardResponse:
    """Compact summary for an extension officer. No image is stored or included."""
    session = await sessions.get(str(body.session_id), device_id)
    if session is None:
        raise HTTPException(404, "That conversation has ended. Please check your crop again.")
    try:
        return ShareCardResponse(session_id=session.id, text=build_share_card(session))
    except ValueError:
        raise HTTPException(409, "There is no crop check in this conversation yet. Please take a photo first.")


@router.delete("/session/{session_id}", status_code=204, dependencies=[Depends(limit("general"))])
async def delete_session(
    session_id: UUID,
    device_id: Annotated[str, Depends(current_device)],
    sessions: Annotated[SessionStore, Depends(get_sessions)],
) -> Response:
    """Delete a session immediately. Idempotent: 204 whether or not it existed."""
    await sessions.delete(str(session_id), device_id)
    return Response(status_code=204)
