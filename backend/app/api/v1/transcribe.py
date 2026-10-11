from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from app.ai.stt import ALLOWED_AUDIO, EMPTY, base_mime
from app.core.rate_limit import limit
from app.core.security import current_device
from app.schemas.common import Language

router = APIRouter(tags=["transcribe"])
MAX_AUDIO_BYTES = 2 * 1024 * 1024  # about a minute of compressed speech


class TranscribeResponse(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscribeResponse,
             dependencies=[Depends(limit("general")), Depends(limit("chat"))])
async def transcribe(
    request: Request,
    audio: Annotated[UploadFile, File(description="Short voice recording (webm, ogg, mp4, mp3, wav), up to 2 MB")],
    _device: Annotated[str, Depends(current_device)],
    language: Annotated[Language, Form()] = Language.en,
) -> TranscribeResponse:
    """Voice to text for browsers without speech recognition. Audio is processed in memory and never stored."""
    mime = base_mime(audio.content_type)
    if mime not in ALLOWED_AUDIO:
        raise HTTPException(415, "Please send a webm, ogg, mp4, mp3 or wav recording.")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "That recording is too long. Please keep it under one minute.")
    if len(data) < 500:
        raise HTTPException(422, EMPTY[language])
    stt = request.app.state.stt
    if stt is None:
        raise HTTPException(503, "Voice typing is not available right now. Please type your question.")
    text = await stt.transcribe(data, mime, language)
    if not text:
        raise HTTPException(422, EMPTY[language])
    return TranscribeResponse(text=text[:1000])
