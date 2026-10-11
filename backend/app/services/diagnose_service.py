"""Photo diagnosis: quality gate -> weather rules -> AI -> guardrails -> session."""
from app.ai.provider import DiagnoseInput, VisionProvider
from app.schemas.common import LOW_CONFIDENCE, Escalate, Language
from app.knowledge import is_known_crop
from app.services.crop_names import normalize_crop
from app.schemas.diagnose import DiagnoseResponse, Diagnosis, ImageQuality, PhotoRejected
from app.schemas.weather import AdviceItem
from app.services.image_utils import assess_quality
from app.services.session_store import SessionStore
from app.weather.provider import WeatherProvider, advice_for

LOW_CONFIDENCE_REASON = {
    Language.en: "I am not sure about this one. An extension officer who can see the plants should confirm it.",
    Language.pcm: "I no sure about this one. Make extension officer wey fit see the plants confirm am.",
}


def weather_note(advice: list[AdviceItem] | None, language: Language) -> str | None:
    """One sentence for the diagnosis: the most urgent warning, or the all-clear for spraying."""
    if not advice:
        return None
    pick = next((a for a in advice if a.severity == "warning"), None) or next((a for a in advice if a.code == "spray_ok"), None)
    if pick is None:
        return None
    return pick.message_pcm if language is Language.pcm else pick.message


UNKNOWN_CROP_MAX_CONFIDENCE = 0.55  # crops outside the knowledge base get a general answer, never a confident one


def apply_guardrails(diagnosis: Diagnosis, language: Language) -> Diagnosis:
    """Enforce the honesty rules whatever the provider returned: unknown crops are capped, low confidence escalates."""
    diagnosis.crop.name = normalize_crop(diagnosis.crop.name) or diagnosis.crop.name  # "Plantain" -> "plantain"
    if not is_known_crop(diagnosis.crop.name) and diagnosis.assessment.confidence > UNKNOWN_CROP_MAX_CONFIDENCE:
        diagnosis.assessment.confidence = UNKNOWN_CROP_MAX_CONFIDENCE
    if diagnosis.assessment.confidence < LOW_CONFIDENCE and not diagnosis.escalate.recommended:
        diagnosis.escalate = Escalate(recommended=True, reason=LOW_CONFIDENCE_REASON[language])
    return diagnosis


class DiagnoseService:
    def __init__(self, vision: VisionProvider, weather: WeatherProvider, sessions: SessionStore, accounts=None):
        self.vision = vision
        self.weather = weather
        self.sessions = sessions
        self.accounts = accounts  # AccountService: personal context and saved history for logged-in farmers

    async def run(
        self, *, device_id: str, image: bytes, mime: str, language: Language, crop: str | None,
        symptoms_text: str | None, lat: float | None, lon: float | None, user_id: str | None = None,
    ) -> DiagnoseResponse:
        quality = assess_quality(image, language)  # ValueError if undecodable
        if not quality.usable:
            # Do not guess, and do not spend an AI call.
            return DiagnoseResponse(session_id=None, image_quality=quality, spoken_text=quality.advice or "")

        advice = await advice_for(self.weather, lat, lon, crop)
        farmer = await self.accounts.context(user_id) if self.accounts else None
        diagnosis = await self.vision.diagnose(DiagnoseInput(
            image=image, mime=mime, language=language, crop=crop, symptoms_text=symptoms_text, weather=advice,
            farmer=farmer,
        ))
        if isinstance(diagnosis, PhotoRejected):  # the AI judged the photo unusable (blurry, too far, not a plant)
            rejected = ImageQuality(usable=False, issue=diagnosis.issue, advice=diagnosis.advice)
            return DiagnoseResponse(session_id=None, image_quality=rejected, spoken_text=diagnosis.advice)
        diagnosis = apply_guardrails(diagnosis, language)

        session = await self.sessions.create(
            device_id, language=language, crop=diagnosis.crop.name, lat=lat, lon=lon,
            diagnosis=diagnosis, symptoms_text=symptoms_text,
        )
        response = DiagnoseResponse(
            session_id=session.id, image_quality=quality, weather_note=weather_note(advice, language),
            **diagnosis.model_dump(),
        )
        if user_id and self.accounts:
            await self.accounts.save_check(user_id, response, symptoms_text)  # answer only: the photo is never stored
        return response
