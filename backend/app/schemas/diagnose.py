from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Confidence, Escalate

When = Literal["today", "this_week", "next_season"]


class ImageQuality(BaseModel):
    usable: bool = True
    issue: str | None = None
    advice: str | None = None


class CropGuess(BaseModel):
    name: str
    confidence: Confidence


class Alternative(BaseModel):
    name: str
    confidence: Confidence


class Assessment(BaseModel):
    likely_problem: str
    confidence: Confidence
    alternatives: list[Alternative] = []
    what_i_see: str
    why_i_think_so: str
    what_could_change_my_mind: str


class Action(BaseModel):
    step: int = Field(ge=1)
    what: str
    when: When
    why: str


class Diagnosis(BaseModel):
    """What a VisionProvider returns (validated; providers get one retry on invalid JSON)."""

    crop: CropGuess
    assessment: Assessment
    actions: list[Action] = Field(min_length=1)
    prevention: list[str] = []
    farmer_questions: list[str] = []
    escalate: Escalate = Escalate()
    spoken_text: str


PhotoIssue = Literal["not_a_plant", "blurry", "too_far", "too_dark"]


class PhotoRejected(BaseModel):
    """A provider's way of saying the photo cannot be judged (so nothing is guessed)."""

    issue: str
    advice: str


class VisionOutput(BaseModel):
    """The JSON the real AI must return: either a usable-photo diagnosis or a photo problem."""

    photo_usable: bool
    photo_issue: PhotoIssue | None = None
    photo_advice: str | None = None
    diagnosis: Diagnosis | None = None


class DiagnoseResponse(BaseModel):
    # session_id, crop and assessment are null when image_quality.usable is false.
    session_id: str | None
    image_quality: ImageQuality
    crop: CropGuess | None = None
    assessment: Assessment | None = None
    actions: list[Action] = []
    prevention: list[str] = []
    farmer_questions: list[str] = []
    weather_note: str | None = None
    escalate: Escalate = Escalate()
    spoken_text: str
