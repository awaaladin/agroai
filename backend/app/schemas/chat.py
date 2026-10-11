from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Confidence, Escalate, Language


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID | None = None
    message: str = Field(min_length=1, max_length=1000)
    language: Language = Language.en
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    crop: str | None = Field(default=None, max_length=40)


class ChatAnswer(BaseModel):
    """What a VisionProvider returns for a chat turn."""

    answer_text: str
    spoken_text: str
    follow_up_suggestions: list[str] = []
    escalate: Escalate = Escalate()
    confidence: Confidence


class ChatResponse(ChatAnswer):
    session_id: str
