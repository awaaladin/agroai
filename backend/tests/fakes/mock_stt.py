"""Test-only fake speech-to-text."""
from app.ai.stt import SpeechToTextProvider
from app.schemas.common import Language


class MockSTT(SpeechToTextProvider):
    name = "mock"

    async def transcribe(self, audio: bytes, mime: str, language: Language) -> str:
        return ("My cassava leaves dey yellow and curl, wetin I fit do?" if language is Language.pcm
                else "My cassava leaves are yellow and curling. What can I do?")
