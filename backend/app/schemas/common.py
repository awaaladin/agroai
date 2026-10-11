from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

# Below this the AI must say it is unsure and hand over to a human.
LOW_CONFIDENCE = 0.6


class Language(str, Enum):
    en = "en"
    pcm = "pcm"  # Nigerian Pidgin


class Escalate(BaseModel):
    recommended: bool = False
    reason: str | None = None
