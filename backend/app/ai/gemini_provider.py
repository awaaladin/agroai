"""Google Gemini provider (REST generateContent). Has a free tier via Google AI Studio.

Same prompts, safety audit and retry as the Anthropic provider (see LLMProvider).
Privacy note: on Google's free tier, submitted content may be used to improve Google's products.
"""
import base64
import logging

import httpx

from app.ai.llm_provider import Generated, LLMProvider, Turn
from app.ai.provider import ProviderError
from app.core.config import Settings

log = logging.getLogger("agroai.ai")

MAX_OUTPUT_TOKENS = 8192  # thinking tokens count toward this on 2.5+ models
# finishReason / blockReason values that mean the model or Google's filters declined to answer.
RETRY_NEXT_MODEL = {404, 429, 500, 502, 503, 504}
BLOCKED = {"SAFETY", "PROHIBITED_CONTENT", "IMAGE_SAFETY", "BLOCKLIST", "SPII", "RECITATION", "OTHER"}


def inline_schema(schema: dict) -> dict:
    """Pydantic JSON schema -> self-contained schema: resolve $ref/$defs, drop titles and defaults."""
    defs = schema.get("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            return {k: walk(v) for k, v in node.items() if k not in {"$defs", "title", "default"}}
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.model = settings.gemini_model  # the preferred model; fallbacks are in settings.gemini_models
        self.client = client or httpx.AsyncClient(timeout=settings.gemini_timeout_seconds)

    @staticmethod
    def _contents(turns: list[Turn]) -> list[dict]:
        """Gemini wants roles user/model; consecutive turns of one role are merged into one content."""
        contents: list[dict] = []
        for t in turns:
            role = "model" if t.role == "assistant" else "user"
            parts = []
            if t.image is not None:
                data, mime = t.image
                parts.append({"inline_data": {"mime_type": mime, "data": base64.standard_b64encode(data).decode("ascii")}})
            parts.append({"text": t.text})
            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})
        return contents

    async def _post_with_fallback(self, body: dict) -> httpx.Response:
        """Try each configured model in turn while one is overloaded (503), rate limited (429) or retired (404)."""
        r = None
        for model in self.settings.gemini_models:
            url = f"{self.settings.gemini_base_url}/models/{model}:generateContent"
            try:
                r = await self.client.post(url, json=body, headers={"x-goog-api-key": self.settings.gemini_api_key})
            except httpx.TransportError:
                r = None
                continue
            r.model_used = model
            if r.status_code not in RETRY_NEXT_MODEL:
                break
            log.warning("gemini model unavailable", extra={"extra_fields": {"model": model, "status": r.status_code}})
        if r is None:
            raise ProviderError("I cannot reach my brain right now. Please try again soon.", 503)
        return r

    async def _generate(self, system, turns, fmt, effort) -> Generated:
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": self._contents(turns),
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": inline_schema(fmt.model_json_schema()),
                "maxOutputTokens": MAX_OUTPUT_TOKENS,
                "temperature": 0.3,
            },
        }
        r = await self._post_with_fallback(body)
        if r.status_code == 429:
            raise ProviderError("Many farmers are asking at once. Please try again in a minute.", 429)
        if r.status_code >= 400:
            # 400/403 usually mean a bad key, an unavailable region, or a retired model: an operator problem.
            log.error("gemini error", extra={"extra_fields": {"status": r.status_code, "model": r.model_used}})
            raise ProviderError("Something went wrong on my side. Please try again soon.", 503)
        data = r.json()
        meta = data.get("usageMetadata", {})
        usage = {"model": r.model_used, "input_tokens": meta.get("promptTokenCount"),
                 "output_tokens": meta.get("candidatesTokenCount")}
        if data.get("promptFeedback", {}).get("blockReason"):
            return Generated(parsed=None, refused=True, usage=usage)
        candidates = data.get("candidates") or []
        cand = candidates[0] if candidates else {}
        finish = cand.get("finishReason")
        usage["stop_reason"] = finish
        if finish in BLOCKED:
            return Generated(parsed=None, refused=True, usage=usage)
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))
        if not text.strip() or finish == "MAX_TOKENS":
            return Generated(parsed=None, usage=usage)
        return Generated(parsed=fmt.model_validate_json(text), usage=usage)
