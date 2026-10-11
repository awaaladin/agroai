"""Shared logic for real LLM providers (Anthropic, Gemini): prompts, safety audit, one retry, friendly errors.

A subclass only translates our neutral `Turn`s into its vendor's request and returns a `Generated`.
Nothing here logs prompts, images or answers.
"""
import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai import prompts
from app.ai.provider import ChatInput, DiagnoseInput, ProviderError, VisionProvider
from app.knowledge.safety import audit_diagnosis, audit_text
from app.schemas.chat import ChatAnswer
from app.schemas.common import Language
from app.schemas.diagnose import Diagnosis, PhotoRejected, VisionOutput

log = logging.getLogger("agroai.ai")
T = TypeVar("T", bound=BaseModel)

ATTEMPTS = 2  # first try + one retry

DEFAULT_PHOTO_ADVICE = {
    Language.en: "I could not judge that photo. Come closer to the leaf, hold your phone still, and try again.",
    Language.pcm: "I no fit see that photo well. Come near the leaf, hold your phone steady, and try again.",
}
FRIENDLY_FAILURE = {
    Language.en: "I could not give you a safe answer just now. Please try again, or ask your extension officer.",
    Language.pcm: "I no fit give you safe answer now. Abeg try again, or ask your extension officer.",
}
REFUSED = {
    Language.en: "I cannot help with that one. Please ask your extension officer.",
    Language.pcm: "I no fit help with that one. Abeg ask your extension officer.",
}


@dataclass
class Turn:
    """Vendor-neutral chat turn. `image` is (bytes, mime) and only ever on a user turn."""

    role: str  # "user" | "assistant"
    text: str
    image: tuple[bytes, str] | None = None


@dataclass
class Generated:
    parsed: BaseModel | None  # None when the answer was empty or cut off
    refused: bool = False
    usage: dict = field(default_factory=dict)  # token counts only


class _Unsafe(Exception):
    def __init__(self, problems: list[str]):
        self.problems = problems


class LLMProvider(VisionProvider):
    spend_cap = None  # a core.rate_limit.SpendCap, set by create_app; counts every paid model call

    @abstractmethod
    async def _generate(self, system: str, turns: list[Turn], fmt: type[T], effort: str) -> Generated:
        """One model call. Raise ProviderError for transport problems; pydantic.ValidationError for invalid JSON."""

    # --- public API -----------------------------------------------------------------------------

    async def diagnose(self, req: DiagnoseInput) -> Diagnosis | PhotoRejected:
        text = prompts.diagnose_user_text(req.language, req.crop, req.symptoms_text, req.weather, req.farmer)

        def check(out: VisionOutput) -> None:
            if out.photo_usable and out.diagnosis is None:
                raise ValueError("usable photo but no diagnosis")
            if out.diagnosis is not None and out.photo_usable:
                problems = audit_diagnosis(out.diagnosis)
                if problems:
                    raise _Unsafe(problems)

        out = await self._ask(
            system=prompts.system_prompt(req.language), turns=[Turn("user", text, image=(req.image, req.mime))],
            fmt=VisionOutput, check=check, language=req.language, effort="medium",
        )
        if not out.photo_usable or out.diagnosis is None:
            return PhotoRejected(issue=out.photo_issue or "blurry",
                                 advice=out.photo_advice or DEFAULT_PHOTO_ADVICE[req.language])
        return out.diagnosis

    async def chat(self, req: ChatInput) -> ChatAnswer:
        context = prompts.chat_context_text(req.crop, req.diagnosis, req.weather, req.language, req.farmer, req.forecast)
        turns = [Turn("user" if t["role"] == "farmer" else "assistant", t["text"]) for t in req.history]
        turns.append(Turn("user", f"<context>\n{context}\n</context>\n\n<farmer_text>{req.message}</farmer_text>"))

        def check(out: ChatAnswer) -> None:
            problems = audit_text("\n".join([out.answer_text, out.spoken_text, *out.follow_up_suggestions]))
            if problems:
                raise _Unsafe(problems)

        return await self._ask(
            system=prompts.chat_system_prompt(req.language), turns=turns, fmt=ChatAnswer,
            check=check, language=req.language, effort="low",
        )

    # --- retry loop -----------------------------------------------------------------------------

    async def _ask(self, *, system: str, turns: list[Turn], fmt: type[T], check, language: Language, effort: str) -> T:
        """Call the model; retry once on invalid, cut-off or unsafe output; otherwise raise a friendly ProviderError."""
        feedback: str | None = None
        for attempt in range(ATTEMPTS):
            sent = turns + [Turn("user", feedback)] if feedback else turns
            if self.spend_cap is not None:
                await self.spend_cap.reserve()  # RateLimited (429) when today's budget is used up
            try:
                gen = await self._generate(system, sent, fmt, effort)
            except ValidationError:
                log.warning("invalid model JSON", extra={"extra_fields": {"attempt": attempt}})
                feedback = "Your previous answer was not valid for the required JSON format. Answer again, exactly in that format."
                continue
            log.info("ai call", extra={"extra_fields": {"provider": self.name, "prompt_version": prompts.PROMPT_VERSION,
                                                        "attempt": attempt, **gen.usage}})
            if gen.refused:
                raise ProviderError(REFUSED[language], 422)
            if gen.parsed is None:  # empty or cut off by the token limit
                feedback = "Your previous answer was cut off or empty. Answer again, more briefly, in the required JSON format."
                continue
            try:
                check(gen.parsed)
                return gen.parsed
            except _Unsafe as exc:
                log.warning("unsafe model output rejected", extra={"extra_fields": {"attempt": attempt, "problems": exc.problems}})
                feedback = ("Your previous answer was rejected because it " + "; ".join(exc.problems) +
                            ". Answer again and follow every safety rule.")
            except ValueError:
                feedback = "Your previous answer was incomplete. Answer again in the required JSON format."
        raise ProviderError(FRIENDLY_FAILURE[language], 503)
