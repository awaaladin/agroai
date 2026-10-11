import pytest
from pydantic import ValidationError

from tests.fakes.mock_provider import CASES, HEALTHY_WORDS, MockProvider, build_diagnosis, pick_case
from app.ai.provider import ChatInput, DiagnoseInput
from app.schemas.chat import ChatRequest
from app.schemas.common import LOW_CONFIDENCE, Language
from app.schemas.diagnose import Action, Assessment, Diagnosis
from app.services.crop_names import normalize_crop
from tests.conftest import make_image

REQUIRED = {"cassava_mosaic", "yam_anthracnose", "maize_fall_armyworm", "plantain_black_sigatoka", "pepper_leaf_curl", "healthy"}


def test_mock_covers_required_diagnoses():
    assert set(CASES) == REQUIRED


@pytest.mark.parametrize("key", sorted(REQUIRED))
@pytest.mark.parametrize("lang", list(Language))
def test_every_canned_diagnosis_is_valid_and_complete(key, lang):
    d = build_diagnosis(key, lang)
    Diagnosis.model_validate(d.model_dump())
    a = d.assessment
    assert a.what_i_see and a.why_i_think_so and a.what_could_change_my_mind
    assert d.actions and [x.step for x in d.actions] == list(range(1, len(d.actions) + 1))
    assert d.farmer_questions and d.spoken_text
    assert not any(c in d.spoken_text for c in "*#•\n-")  # written to be read aloud: no symbols or lists


def test_pidgin_differs_from_english():
    for key in REQUIRED:
        assert build_diagnosis(key, Language.en).spoken_text != build_diagnosis(key, Language.pcm).spoken_text


def test_low_confidence_always_escalates():
    for key in REQUIRED:
        for lang in Language:
            d = build_diagnosis(key, lang)
            if d.assessment.confidence < LOW_CONFIDENCE:
                assert d.escalate.recommended and d.escalate.reason


def test_healthy_does_not_escalate_and_has_a_low_confidence_case():
    assert not build_diagnosis("healthy", Language.en).escalate.recommended
    assert any(c["conf"] < LOW_CONFIDENCE for c in CASES.values())


def test_no_dosages_in_canned_text():
    import re
    for key in REQUIRED:
        for lang in Language:
            blob = build_diagnosis(key, lang).model_dump_json()
            assert not re.search(r"\d+\s?(ml|mls|g|kg|litre|liter|l)\b", blob, re.I), key


def test_pick_case_by_crop_and_symptoms():
    img = make_image()
    assert pick_case(img, "cassava", None) == "cassava_mosaic"
    assert pick_case(img, "maize", None) == "maize_fall_armyworm"
    assert pick_case(img, "maize", f"it looks {HEALTHY_WORDS[0]}") == "healthy"
    assert pick_case(img, None, None) == pick_case(img, None, None)  # deterministic


async def test_mock_chat_declines_out_of_scope():
    ans = await MockProvider().chat(ChatInput(message="Can you give me a loan?", language=Language.en))
    assert "farming" in ans.answer_text.lower()


def test_chat_request_validation():
    with pytest.raises(ValidationError):
        ChatRequest(message="")
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", lat=95)
    with pytest.raises(ValidationError):
        ChatRequest(message="hi", language="fr")
    assert ChatRequest(message="hi").language is Language.en


def test_action_when_is_restricted():
    with pytest.raises(ValidationError):
        Action(step=1, what="x", when="yesterday", why="y")
    with pytest.raises(ValidationError):
        Assessment(likely_problem="x", confidence=1.5, what_i_see="a", why_i_think_so="b", what_could_change_my_mind="c")


@pytest.mark.parametrize("raw,expected", [("Akpu", "cassava"), (" ISU ", "yam"), ("ubi", "yam"), ("ede", "cocoyam"), ("Oka", "maize"), ("tomato", "tomato"), ("", None), (None, None)])
def test_local_crop_names(raw, expected):
    assert normalize_crop(raw) == expected


async def test_mock_diagnose_directly():
    d = await MockProvider().diagnose(DiagnoseInput(image=make_image(), mime="image/jpeg", language=Language.pcm, crop="yam"))
    assert d.crop.name == "yam"
