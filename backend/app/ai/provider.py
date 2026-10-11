"""VisionProvider interface: the only place the rest of the app talks to an AI."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.schemas.chat import ChatAnswer
from app.schemas.common import Language
from app.schemas.diagnose import Diagnosis, PhotoRejected
from app.schemas.weather import AdviceItem


@dataclass
class DiagnoseInput:
    image: bytes  # in memory only, never written to disk or logged
    mime: str
    language: Language
    crop: str | None = None
    symptoms_text: str | None = None
    weather: list[AdviceItem] | None = None  # deterministic rules the AI may explain
    farmer: object | None = None  # accounts.FarmerContext for logged-in farmers


@dataclass
class ChatInput:
    message: str
    language: Language
    crop: str | None = None
    diagnosis: Diagnosis | None = None  # context from an earlier photo check
    history: list[dict] = field(default_factory=list)  # [{"role": "farmer"|"advisor", "text": ...}]
    weather: list[AdviceItem] | None = None
    farmer: object | None = None  # accounts.FarmerContext for logged-in farmers


class ProviderError(Exception):
    """The AI could not give a safe, valid answer. `user_message` is friendly and safe to show."""

    def __init__(self, user_message: str, status_code: int = 503):
        super().__init__(user_message)
        self.user_message = user_message
        self.status_code = status_code


class VisionProvider(ABC):
    name: str

    @abstractmethod
    async def diagnose(self, req: DiagnoseInput) -> Diagnosis | PhotoRejected:
        """A diagnosis, or PhotoRejected when the photo is unusable (blurry, too far, not a plant)."""

    @abstractmethod
    async def chat(self, req: ChatInput) -> ChatAnswer: ...
