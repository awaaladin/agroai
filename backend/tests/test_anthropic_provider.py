"""AnthropicProvider with a fake SDK client. No network, no key. Real-API behaviour is checked separately by hand."""
import base64
import logging
from types import SimpleNamespace

import anthropic
import pytest
from pydantic import ValidationError

from app.ai.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from tests.fakes.mock_provider import build_diagnosis
from app.ai.provider import ChatInput, DiagnoseInput, ProviderError
from app.core.config import Settings
from app.schemas.chat import ChatAnswer
from app.schemas.common import Language
from app.schemas.diagnose import Diagnosis, PhotoRejected, VisionOutput
from tests.conftest import make_image

try:  # anthropic 1.x uses httpx2
    import httpx2 as httpx
except ImportError:  # pragma: no cover
    import httpx

REQ = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


class FakeMessages:
    """Records each call and replays queued outcomes (a response or an exception)."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        out = self.outcomes.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def reply(parsed, stop_reason="end_turn"):
    usage = SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0)
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason, usage=usage)


def provider(*outcomes, fallback=True):
    beta, plain = FakeMessages(outcomes), FakeMessages(outcomes)
    client = SimpleNamespace(beta=SimpleNamespace(messages=beta), messages=plain)
    settings = Settings(anthropic_api_key="k", anthropic_refusal_fallback=fallback, _env_file=None)
    return AnthropicProvider(settings, client=client), (beta if fallback else plain)


def good_output(lang=Language.en, key="maize_fall_armyworm"):
    return VisionOutput(photo_usable=True, diagnosis=build_diagnosis(key, lang))


def diag_input(**kw):
    base = dict(image=make_image(), mime="image/jpeg", language=Language.en, crop="maize", symptoms_text="holes in leaves")
    return DiagnoseInput(**{**base, **kw})


async def test_diagnose_success_and_request_shape():
    p, fake = provider(reply(good_output()))
    result = await p.diagnose(diag_input())
    assert isinstance(result, Diagnosis) and result.assessment.likely_problem == "Fall armyworm in maize"

    call = fake.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_format"] is VisionOutput
    assert call["output_config"] == {"effort": "medium"}
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert "temperature" not in call and "thinking" not in call and "tool_choice" not in call  # rejected by the current models
    img, text = call["messages"][0]["content"]
    assert img["type"] == "image" and img["source"]["media_type"] == "image/jpeg"
    assert base64.b64decode(img["source"]["data"]).startswith(b"\xff\xd8")
    assert "<farmer_text>holes in leaves</farmer_text>" in text["text"] and "Fall armyworm" in text["text"]
    assert call["system"][0]["text"].startswith("You are AgroAI Advisor")


async def test_fallback_can_be_disabled():
    p, fake = provider(reply(good_output()), fallback=False)
    await p.diagnose(diag_input())
    assert "betas" not in fake.calls[0] and "fallbacks" not in fake.calls[0]


async def test_pidgin_request_uses_pidgin_prompt():
    p, fake = provider(reply(good_output(Language.pcm)))
    await p.diagnose(diag_input(language=Language.pcm))
    assert "Nigerian Pidgin" in fake.calls[0]["system"][0]["text"]


async def test_ai_can_reject_a_photo():
    out = VisionOutput(photo_usable=False, photo_issue="not_a_plant", photo_advice="Please show me the plant leaf.")
    p, _ = provider(reply(out))
    result = await p.diagnose(diag_input())
    assert isinstance(result, PhotoRejected) and result.issue == "not_a_plant" and "leaf" in result.advice


async def test_rejection_without_advice_gets_a_default_in_the_right_language():
    out = VisionOutput(photo_usable=False, photo_issue="blurry")
    p, _ = provider(reply(out))
    result = await p.diagnose(diag_input(language=Language.pcm))
    assert "steady" in result.advice


async def test_invalid_json_is_retried_once():
    try:
        Diagnosis.model_validate({})
    except ValidationError as err:
        invalid = err
    p, fake = provider(invalid, reply(good_output()))
    result = await p.diagnose(diag_input())
    assert isinstance(result, Diagnosis) and len(fake.calls) == 2
    assert "not valid" in fake.calls[1]["messages"][-1]["content"]


async def test_invalid_twice_gives_friendly_error():
    try:
        Diagnosis.model_validate({})
    except ValidationError as err:
        invalid = err
    p, fake = provider(invalid, invalid)
    with pytest.raises(ProviderError) as exc:
        await p.diagnose(diag_input())
    assert exc.value.status_code == 503 and len(fake.calls) == 2


def unsafe_output(text_mod):
    d = build_diagnosis("maize_fall_armyworm", Language.en)
    d.spoken_text += " " + text_mod
    return VisionOutput(photo_usable=True, diagnosis=d)


async def test_unsafe_answer_is_retried_with_feedback():
    p, fake = provider(reply(unsafe_output("Spray paraquat, mix 50ml per tank.")), reply(good_output()))
    result = await p.diagnose(diag_input())
    assert isinstance(result, Diagnosis) and "paraquat" not in result.spoken_text
    feedback = fake.calls[1]["messages"][-1]["content"]
    assert "banned or restricted pesticide" in feedback and "dose" in feedback


async def test_unsafe_twice_is_never_shown():
    p, _ = provider(reply(unsafe_output("Use paraquat.")), reply(unsafe_output("Use 50 ml of paraquat.")))
    with pytest.raises(ProviderError) as exc:
        await p.diagnose(diag_input())
    assert "paraquat" not in exc.value.user_message


async def test_usable_photo_without_diagnosis_is_retried():
    bad = VisionOutput(photo_usable=True, diagnosis=None)
    p, fake = provider(reply(bad), reply(good_output()))
    assert isinstance(await p.diagnose(diag_input()), Diagnosis) and len(fake.calls) == 2


async def test_cut_off_answer_is_retried():
    p, fake = provider(reply(None, stop_reason="max_tokens"), reply(good_output()))
    assert isinstance(await p.diagnose(diag_input()), Diagnosis) and len(fake.calls) == 2


async def test_refusal_is_reported_not_retried():
    p, fake = provider(reply(None, stop_reason="refusal"))
    with pytest.raises(ProviderError) as exc:
        await p.diagnose(diag_input(language=Language.pcm))
    assert exc.value.status_code == 422 and "extension officer" in exc.value.user_message and len(fake.calls) == 1


@pytest.mark.parametrize("error,status", [
    (anthropic.RateLimitError("rl", response=httpx.Response(429, request=REQ), body=None), 429),
    (anthropic.APIConnectionError(request=REQ), 503),
    (anthropic.APIStatusError("boom", response=httpx.Response(500, request=REQ), body=None), 503),
])
async def test_api_errors_become_friendly_provider_errors(error, status):
    p, fake = provider(error)
    with pytest.raises(ProviderError) as exc:
        await p.diagnose(diag_input())
    assert exc.value.status_code == status and len(fake.calls) == 1
    assert "boom" not in exc.value.user_message


def chat_answer(text="Wait until the rain stops. Follow the label and wear gloves if you spray."):
    return ChatAnswer(answer_text=text, spoken_text=text, follow_up_suggestions=["When will it stop?"], confidence=0.8)


async def test_chat_maps_history_and_context():
    p, fake = provider(reply(chat_answer()))
    d = build_diagnosis("maize_fall_armyworm", Language.en)
    history = [{"role": "farmer", "text": "hello"}, {"role": "advisor", "text": "hi, tell me more"}]
    ans = await p.chat(ChatInput(message="Can I spray today?", language=Language.en, crop="maize", diagnosis=d, history=history))
    assert ans.confidence == 0.8
    call = fake.calls[0]
    assert call["output_format"] is ChatAnswer and call["output_config"] == {"effort": "low"}
    roles = [m["role"] for m in call["messages"]]
    assert roles == ["user", "assistant", "user"]
    last = call["messages"][-1]["content"]
    assert "<farmer_text>Can I spray today?</farmer_text>" in last and "Fall armyworm in maize" in last


async def test_chat_unsafe_answer_retried():
    p, fake = provider(reply(chat_answer("Use endosulfan today.")), reply(chat_answer()))
    ans = await p.chat(ChatInput(message="what to spray", language=Language.en))
    assert "endosulfan" not in ans.answer_text and len(fake.calls) == 2


async def test_nothing_sensitive_is_logged(caplog):
    caplog.set_level(logging.DEBUG)
    p, _ = provider(reply(good_output()))
    img = make_image()
    await p.diagnose(diag_input(image=img, symptoms_text="my secret farm words"))
    logged = " ".join(r.getMessage() + str(getattr(r, "extra_fields", "")) for r in caplog.records)
    assert "secret farm words" not in logged and base64.b64encode(img)[:40].decode() not in logged
    assert "prompt_version" in logged
