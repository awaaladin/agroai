"""SpeechToTextProvider interface, and a Gemini implementation (audio understanding via generateContent).

Audio is processed in memory only: never written to disk, never logged. Pidgin is transcribed as Nigerian
English/Pidgin speech; accuracy is best-effort, so the app always lets the farmer edit the text before sending.
"""
import base64
import logging
from abc import ABC, abstractmethod

import httpx

from app.ai.provider import ProviderError
from app.core.config import Settings
from app.schemas.common import Language

log = logging.getLogger("agroai.stt")

PROMPTS = {
    Language.en: "Transcribe this short voice message exactly as spoken, in English. Reply with only the words spoken, no commentary.",
    Language.pcm: ("Transcribe this short voice message exactly as spoken. The speaker is a Nigerian farmer, probably speaking "
                   "Nigerian Pidgin or Nigerian English. Keep Pidgin words as spoken. Reply with only the words spoken, no commentary."),
}
EMPTY = {
    Language.en: "I could not hear any words. Please speak closer to the phone and try again.",
    Language.pcm: "I no hear any word. Abeg speak near the phone and try again.",
}
ALLOWED_AUDIO = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/aac",
                 "audio/flac", "audio/x-m4a", "audio/m4a"}


def base_mime(content_type: str | None) -> str:
    """'audio/webm;codecs=opus' -> 'audio/webm'."""
    return (content_type or "").split(";")[0].strip().lower()


class SpeechToTextProvider(ABC):
    name: str
    spend_cap = None  # a core.rate_limit.SpendCap for paid providers

    @abstractmethod
    async def transcribe(self, audio: bytes, mime: str, language: Language) -> str:
        """Return the spoken words (may be empty if nothing was heard)."""


class GeminiSTT(SpeechToTextProvider):
    name = "gemini"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=settings.gemini_timeout_seconds)

    async def transcribe(self, audio: bytes, mime: str, language: Language) -> str:
        body = {
            "contents": [{"role": "user", "parts": [
                {"inline_data": {"mime_type": mime, "data": base64.standard_b64encode(audio).decode("ascii")}},
                {"text": PROMPTS[language]},
            ]}],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 1024},
        }
        if self.spend_cap is not None:
            await self.spend_cap.reserve()
        r = None
        for model in self.settings.gemini_models:  # same overload fallback as the vision provider
            try:
                r = await self.client.post(f"{self.settings.gemini_base_url}/models/{model}:generateContent", json=body,
                                           headers={"x-goog-api-key": self.settings.gemini_api_key})
            except httpx.TransportError:
                r = None
                continue
            if r.status_code not in {404, 429, 500, 502, 503, 504}:
                break
        if r is None:
            raise ProviderError("I cannot reach my ears right now. Please type your question instead.", 503)
        if r.status_code == 429:
            raise ProviderError("Many farmers are asking at once. Please try again in a minute.", 429)
        if r.status_code >= 400:
            log.error("gemini stt error", extra={"extra_fields": {"status": r.status_code}})
            raise ProviderError("I could not hear you just now. Please type your question instead.", 503)
        cands = r.json().get("candidates") or []
        parts = (cands[0].get("content", {}).get("parts", []) if cands else [])
        return "".join(p.get("text", "") for p in parts if not p.get("thought")).strip().strip('"')


def build_stt(settings: Settings) -> SpeechToTextProvider | None:
    """Real speech-to-text needs a Gemini key (Anthropic has no audio input). None = /v1/transcribe answers 503."""
    return GeminiSTT(settings) if settings.gemini_api_key else None
