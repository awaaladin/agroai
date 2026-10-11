from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import Language


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=7, max_length=25)
    pin: str = Field(min_length=4, max_length=6)
    name: str = Field(default="", max_length=80)
    language: Language = Language.en
    town: str = Field(default="", max_length=60)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(min_length=7, max_length=25)
    pin: str = Field(min_length=4, max_length=6)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, max_length=80)
    language: Language | None = None
    town: str | None = Field(default=None, max_length=60)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    crops: list[str] | None = Field(default=None, max_length=10)
    notes: str | None = Field(default=None, max_length=500)


class Profile(BaseModel):
    id: str
    phone: str  # masked: +234*****4567
    name: str
    language: Language
    town: str
    lat: float | None
    lon: float | None
    crops: list[str]
    notes: str
    created_at: datetime
    checks_count: int = 0
    last_check_at: datetime | None = None


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Profile


class CheckSummary(BaseModel):
    id: str
    created_at: datetime
    crop: str
    problem: str
    confidence: float
    escalate: bool


class ConversationSummary(BaseModel):
    """One conversation: a run of chat messages with no long gap between them. `id` is its first message."""

    id: int
    started_at: datetime
    last_at: datetime
    title: str
    messages: int


class ChatTurn(BaseModel):
    role: str  # "farmer" or "advisor"
    text: str
    created_at: datetime
