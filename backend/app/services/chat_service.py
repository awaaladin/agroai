"""Chat: continue the diagnosis context, pull in weather only for time-sensitive questions."""
from app.ai.provider import ChatInput, VisionProvider
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import LOW_CONFIDENCE, Escalate, Language
from app.services.diagnose_service import LOW_CONFIDENCE_REASON
from app.services.session_store import Session, SessionStore
from app.weather.provider import WeatherProvider, advice_for

# Spraying, planting, harvesting, drying and rain questions depend on the forecast.
TIME_SENSITIVE = (
    "spray", "plant", "harvest", "dry", "drying", "rain", "fertili", "weed", "when should", "wetin time", "which time", "water",
)


def is_time_sensitive(message: str) -> bool:
    msg = message.lower()
    return any(w in msg for w in TIME_SENSITIVE)


class ChatService:
    def __init__(self, vision: VisionProvider, weather: WeatherProvider, sessions: SessionStore, accounts=None):
        self.vision = vision
        self.weather = weather
        self.sessions = sessions
        self.accounts = accounts

    async def run(self, device_id: str, req: ChatRequest, session: Session | None, user_id: str | None = None) -> ChatResponse:
        """`session` is the caller-verified existing session, or None to start a new one."""
        if session is None:
            session = await self.sessions.create(
                device_id, language=req.language, crop=req.crop, lat=req.lat, lon=req.lon,
            )
        # Fresh location or crop from the client wins over what the session remembers.
        lat = req.lat if req.lat is not None else session.lat
        lon = req.lon if req.lon is not None else session.lon
        crop = req.crop or session.crop
        if req.lat is not None and req.lon is not None:
            session.lat, session.lon = req.lat, req.lon  # rounded by the model validator
        session.language = req.language

        advice = await advice_for(self.weather, lat, lon, crop) if is_time_sensitive(req.message) else None
        farmer = await self.accounts.context(user_id) if self.accounts else None
        answer = await self.vision.chat(ChatInput(
            message=req.message, language=req.language, crop=crop, diagnosis=session.diagnosis,
            history=list(session.history), weather=advice, farmer=farmer,
        ))
        if answer.confidence < LOW_CONFIDENCE and not answer.escalate.recommended and session.diagnosis is not None:
            answer.escalate = Escalate(recommended=True, reason=LOW_CONFIDENCE_REASON[req.language])

        session.add_turn("farmer", req.message)
        session.add_turn("advisor", answer.answer_text)
        await self.sessions.save(session)
        if user_id and self.accounts:
            await self.accounts.save_chat(user_id, req.message, answer.answer_text)
        return ChatResponse(session_id=session.id, **answer.model_dump())
