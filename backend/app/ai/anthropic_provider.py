"""Anthropic Messages API provider (default model claude-sonnet-5-5, set VISION_MODEL to change).

JSON is enforced with structured outputs (Pydantic schema) and validated again client-side. The shared
retry/safety logic lives in LLMProvider.
"""
import base64
import logging

import anthropic

from app.ai import prompts
from app.ai.llm_provider import Generated, LLMProvider, Turn
from app.ai.provider import ProviderError
from app.core.config import Settings

log = logging.getLogger("agroai.ai")

FALLBACK_BETA = "server-side-fallback-2026-07-01"
MAX_TOKENS = 8000  # thinking tokens count toward this; non-streaming stays under SDK timeouts


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings, client: anthropic.AsyncAnthropic | None = None):
        self.settings = settings
        self.model = settings.vision_model
        self.client = client or anthropic.AsyncAnthropic(
            api_key=settings.anthropic_api_key or None, timeout=settings.anthropic_timeout_seconds, max_retries=2,
        )

    @staticmethod
    def _message(turn: Turn) -> dict:
        if turn.image is None:
            return {"role": turn.role, "content": turn.text}
        data, mime = turn.image
        return {"role": turn.role, "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime,
                                         "data": base64.standard_b64encode(data).decode("ascii")}},
            {"type": "text", "text": turn.text},
        ]}

    async def _generate(self, system, turns, fmt, effort) -> Generated:
        kwargs = dict(
            model=self.model, max_tokens=MAX_TOKENS, messages=[self._message(t) for t in turns], output_format=fmt,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": effort},
        )
        try:
            if self.settings.anthropic_refusal_fallback:
                # If the safety classifiers decline, the API re-runs the request on its recommended fallback model.
                resp = await self.client.beta.messages.parse(**kwargs, betas=[FALLBACK_BETA], fallbacks="default")
            else:
                resp = await self.client.messages.parse(**kwargs)
        except anthropic.RateLimitError:
            raise ProviderError("Many farmers are asking at once. Please try again in a minute.", 429)
        except (anthropic.APIConnectionError, anthropic.APITimeoutError):
            raise ProviderError("I cannot reach my brain right now. Please try again soon.", 503)
        except anthropic.APIStatusError as exc:
            log.error("anthropic status error", extra={"extra_fields": {"status": exc.status_code, "model": self.model}})
            raise ProviderError("Something went wrong on my side. Please try again soon.", 503)

        u = getattr(resp, "usage", None)
        usage = {"model": self.model, "input_tokens": getattr(u, "input_tokens", None),
                 "output_tokens": getattr(u, "output_tokens", None),
                 "cache_read": getattr(u, "cache_read_input_tokens", None),
                 "stop_reason": getattr(resp, "stop_reason", None)}
        return Generated(parsed=getattr(resp, "parsed_output", None), refused=resp.stop_reason == "refusal", usage=usage)


__all__ = ["AnthropicProvider", "FALLBACK_BETA", "prompts"]
