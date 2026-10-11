"""GeminiProvider against a mocked HTTP transport. No network, no key."""
import base64
import json

import httpx
import pytest

from app.ai.gemini_provider import GeminiProvider, inline_schema
from tests.fakes.mock_provider import build_diagnosis
from app.ai.provider import ChatInput, DiagnoseInput, ProviderError
from app.core.config import Settings
from app.main import build_vision
from app.schemas.chat import ChatAnswer
from app.schemas.common import Language
from app.schemas.diagnose import Diagnosis, PhotoRejected, VisionOutput
from tests.conftest import make_image


def gemini_reply(parsed, finish="STOP", parts_extra=()):
    text = parsed if isinstance(parsed, str) else parsed.model_dump_json()
    return {"candidates": [{"finishReason": finish, "content": {"parts": [*parts_extra, {"text": text}]}}],
            "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 7}}


class Server:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        out = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]  # last one repeats
        if isinstance(out, Exception):
            raise out
        return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)

    def body(self, i=0):
        return json.loads(self.requests[i].content)


def provider(server) -> GeminiProvider:
    settings = Settings(gemini_api_key="test-key", _env_file=None)
    return GeminiProvider(settings, client=httpx.AsyncClient(transport=httpx.MockTransport(server)))


def good(lang=Language.en, key="yam_anthracnose"):
    return VisionOutput(photo_usable=True, diagnosis=build_diagnosis(key, lang))


def diag_input(**kw):
    base = dict(image=make_image(), mime="image/jpeg", language=Language.en, crop="yam", symptoms_text="brown spots")
    return DiagnoseInput(**{**base, **kw})


def test_inline_schema_has_no_refs_or_defs():
    schema = inline_schema(VisionOutput.model_json_schema())
    blob = json.dumps(schema)
    assert "$ref" not in blob and "$defs" not in blob and '"title"' not in blob
    assert "likely_problem" in blob and "photo_usable" in blob


async def test_diagnose_request_shape_and_result():
    s = Server(gemini_reply(good()))
    result = await provider(s).diagnose(diag_input())
    assert isinstance(result, Diagnosis) and result.assessment.likely_problem == "Yam anthracnose"

    req = s.requests[0]
    assert req.url.path.endswith("/models/gemini-3.5-flash:generateContent")
    assert req.headers["x-goog-api-key"] == "test-key" and "test-key" not in str(req.url)
    body = s.body()
    assert body["systemInstruction"]["parts"][0]["text"].startswith("You are AgroAI Advisor")
    cfg = body["generationConfig"]
    assert cfg["responseMimeType"] == "application/json" and "$ref" not in json.dumps(cfg["responseJsonSchema"])
    parts = body["contents"][0]["parts"]
    assert parts[0]["inline_data"]["mime_type"] == "image/jpeg"
    assert base64.b64decode(parts[0]["inline_data"]["data"]).startswith(b"\xff\xd8")
    assert "<farmer_text>brown spots</farmer_text>" in parts[1]["text"]


async def test_pidgin_prompt_and_thought_parts_ignored():
    s = Server(gemini_reply(good(Language.pcm), parts_extra=[{"thought": True, "text": "private reasoning"}]))
    result = await provider(s).diagnose(diag_input(language=Language.pcm))
    assert isinstance(result, Diagnosis)
    assert "Nigerian Pidgin" in s.body()["systemInstruction"]["parts"][0]["text"]


async def test_photo_rejection():
    out = VisionOutput(photo_usable=False, photo_issue="not_a_plant", photo_advice="Show me the leaf.")
    result = await provider(Server(gemini_reply(out))).diagnose(diag_input())
    assert isinstance(result, PhotoRejected) and result.issue == "not_a_plant"


async def test_invalid_json_retried_once_with_feedback():
    s = Server(gemini_reply("this is not json"), gemini_reply(good()))
    assert isinstance(await provider(s).diagnose(diag_input()), Diagnosis)
    # the retry merges the feedback into the same user turn (Gemini roles must alternate)
    contents = s.body(1)["contents"]
    assert len(contents) == 1 and "not valid" in contents[0]["parts"][-1]["text"]


async def test_unsafe_answer_retried_then_blocked():
    d = build_diagnosis("yam_anthracnose", Language.en)
    d.spoken_text += " Spray paraquat, 50ml per tank."
    bad = VisionOutput(photo_usable=True, diagnosis=d)
    s = Server(gemini_reply(bad), gemini_reply(good()))
    result = await provider(s).diagnose(diag_input())
    assert "paraquat" not in result.spoken_text and "banned or restricted pesticide" in s.body(1)["contents"][0]["parts"][-1]["text"]

    with pytest.raises(ProviderError) as exc:
        await provider(Server(gemini_reply(bad), gemini_reply(bad))).diagnose(diag_input())
    assert "paraquat" not in exc.value.user_message


async def test_max_tokens_is_retried():
    s = Server(gemini_reply('{"photo_usable": tr', finish="MAX_TOKENS"), gemini_reply(good()))
    assert isinstance(await provider(s).diagnose(diag_input()), Diagnosis) and len(s.requests) == 2


@pytest.mark.parametrize("response", [
    {"promptFeedback": {"blockReason": "SAFETY"}},
    {"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]},
    {"candidates": [{"finishReason": "IMAGE_SAFETY"}]},
])
async def test_blocked_is_a_422(response):
    with pytest.raises(ProviderError) as exc:
        await provider(Server(response)).diagnose(diag_input(language=Language.pcm))
    assert exc.value.status_code == 422 and "extension officer" in exc.value.user_message


@pytest.mark.parametrize("outcome,status", [
    (httpx.Response(429, json={"error": {"message": "quota"}}), 429),
    (httpx.Response(500), 503),
    (httpx.Response(403, json={"error": {"message": "API key not valid"}}), 503),
    (httpx.ConnectError("down"), 503),
])
async def test_http_errors_are_friendly(outcome, status):
    with pytest.raises(ProviderError) as exc:
        await provider(Server(outcome)).diagnose(diag_input())
    assert exc.value.status_code == status
    assert "quota" not in exc.value.user_message and "key" not in exc.value.user_message.lower()


async def test_chat_roles_alternate_and_map_to_model():
    answer = ChatAnswer(answer_text="Wait for the rain to stop. Follow the label and wear gloves if you spray.",
                        spoken_text="Wait for the rain to stop.", follow_up_suggestions=["When?"], confidence=0.7)
    s = Server(gemini_reply(answer))
    history = [{"role": "farmer", "text": "hi"}, {"role": "advisor", "text": "hello"}]
    out = await provider(s).chat(ChatInput(message="Can I spray?", language=Language.en, history=history))
    assert out.confidence == 0.7
    assert [c["role"] for c in s.body()["contents"]] == ["user", "model", "user"]


def test_build_vision_gemini_needs_key():
    with pytest.raises(ValueError):
        build_vision(Settings(vision_provider="gemini", gemini_api_key="", _env_file=None))
    assert build_vision(Settings(vision_provider="gemini", gemini_api_key="k", _env_file=None)).name == "gemini"


async def test_key_and_content_not_logged(caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    await provider(Server(gemini_reply(good()))).diagnose(diag_input(symptoms_text="very private words"))
    logged = " ".join(r.getMessage() + str(getattr(r, "extra_fields", "")) for r in caplog.records)
    assert "test-key" not in logged and "very private words" not in logged


def urls(server):
    return [r.url.path.split("/models/")[1].split(":")[0] for r in server.requests]


async def test_overloaded_model_falls_back_to_the_next_one():
    s = Server(httpx.Response(503, json={"error": {"status": "UNAVAILABLE"}}), gemini_reply(good()))
    assert isinstance(await provider(s).diagnose(diag_input()), Diagnosis)
    assert urls(s) == ["gemini-3.5-flash", "gemini-3.6-flash"]


@pytest.mark.parametrize("status", [404, 429])
async def test_retired_or_rate_limited_model_falls_back(status):
    s = Server(httpx.Response(status), httpx.Response(503), gemini_reply(good()))
    assert isinstance(await provider(s).diagnose(diag_input()), Diagnosis)
    assert urls(s) == ["gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite"]


async def test_all_models_down_is_a_friendly_503():
    s = Server(httpx.Response(503))
    with pytest.raises(ProviderError) as exc:
        await provider(s).diagnose(diag_input())
    assert exc.value.status_code == 503 and len(s.requests) == 3


async def test_bad_key_does_not_try_other_models():
    s = Server(httpx.Response(403, json={"error": {"message": "API key not valid"}}))
    with pytest.raises(ProviderError):
        await provider(s).diagnose(diag_input())
    assert len(s.requests) == 1


def test_fallback_models_come_from_settings():
    st = Settings(gemini_model="a", gemini_fallback_models=" b, c ,", _env_file=None)
    assert st.gemini_models == ["a", "b", "c"]
