import io
import random
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageFilter

from tests.fakes.mock_provider import MockProvider, build_diagnosis
from app.ai.provider import ProviderError, VisionProvider
from app.main import create_app
from app.schemas.common import Language
from app.schemas.diagnose import PhotoRejected
from app.services.diagnose_service import UNKNOWN_CROP_MAX_CONFIDENCE
from app.services.image_utils import assess_quality
from tests.fakes.mock_weather import MockWeatherProvider
from tests.conftest import auth_headers, make_image
from tests.test_endpoints import post_diagnose


def textured(blur_radius=0, size=(480, 480)) -> bytes:
    """Noise image (very detailed); blur_radius simulates focus blur."""
    rnd = random.Random(1)
    img = Image.new("RGB", size)
    img.putdata([(rnd.randint(40, 200), rnd.randint(90, 230), rnd.randint(30, 150)) for _ in range(size[0] * size[1])])
    if blur_radius:
        img = img.filter(ImageFilter.GaussianBlur(blur_radius))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def photo_like(blur_radius=0) -> bytes:
    """Blobs with hard edges on a plain background: moderate detail, like a close-up of a leaf."""
    from PIL import ImageDraw
    rnd = random.Random(3)
    img = Image.new("RGB", (1000, 1000), (60, 120, 50))
    draw = ImageDraw.Draw(img)
    for _ in range(120):
        x, y = rnd.randint(0, 950), rnd.randint(0, 950)
        draw.ellipse((x, y, x + rnd.randint(20, 120), y + rnd.randint(20, 120)),
                     fill=(rnd.randint(20, 200), rnd.randint(80, 240), rnd.randint(20, 120)), outline=(10, 40, 10), width=3)
    if blur_radius:
        img = img.filter(ImageFilter.GaussianBlur(blur_radius))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def test_moderate_detail_photo_sharp_passes_blurred_fails():
    assert assess_quality(photo_like(), Language.en).usable
    assert assess_quality(photo_like(blur_radius=2), Language.en).usable  # slightly soft is allowed
    assert assess_quality(photo_like(blur_radius=6), Language.en).issue == "blurry"


# --- blur ---------------------------------------------------------------------------------------

def test_sharp_photo_passes_and_blurry_photo_is_rejected():
    assert assess_quality(textured(), Language.en).usable
    q = assess_quality(textured(blur_radius=12), Language.en)
    assert not q.usable and q.issue == "blurry" and "still" in q.advice


def test_blurry_photo_endpoint_pidgin(client, headers):
    body = post_diagnose(client, headers, image=textured(blur_radius=12), language="pcm").json()
    assert body["image_quality"]["issue"] == "blurry" and body["assessment"] is None and "steady" in body["spoken_text"]


# --- AI-side rejection, guardrails, provider errors --------------------------------------------

class Scripted(VisionProvider):
    name = "scripted"

    def __init__(self, result=None, error=None):
        self.result, self.error = result, error

    async def diagnose(self, req):
        if self.error:
            raise self.error
        return self.result

    async def chat(self, req):
        return await MockProvider().chat(req)


def client_with(settings, redis, vision):
    return TestClient(create_app(settings, redis=redis, vision=vision, weather_provider=MockWeatherProvider()))


def test_ai_rejected_photo_becomes_unusable_response(settings, redis):
    with client_with(settings, redis, Scripted(PhotoRejected(issue="not_a_plant", advice="Show me the leaf please."))) as c:
        body = post_diagnose(c, auth_headers(c)).json()
    assert body["image_quality"] == {"usable": False, "issue": "not_a_plant", "advice": "Show me the leaf please."}
    assert body["session_id"] is None and body["assessment"] is None and body["spoken_text"] == "Show me the leaf please."


def test_unknown_crop_confidence_is_capped_and_escalated(settings, redis):
    d = build_diagnosis("cassava_mosaic", Language.en)
    d.crop.name = "tomato"
    d.assessment.confidence = 0.95
    d.escalate.recommended = False
    with client_with(settings, redis, Scripted(d)) as c:
        body = post_diagnose(c, auth_headers(c)).json()
    assert body["assessment"]["confidence"] == UNKNOWN_CROP_MAX_CONFIDENCE
    assert body["escalate"]["recommended"] is True


def test_known_crop_confidence_not_capped(settings, redis):
    d = build_diagnosis("healthy", Language.en)
    with client_with(settings, redis, Scripted(d)) as c:
        assert post_diagnose(c, auth_headers(c)).json()["assessment"]["confidence"] == 0.9


@pytest.mark.parametrize("status", [429, 503, 422])
def test_provider_error_is_a_friendly_http_error(settings, redis, status):
    with client_with(settings, redis, Scripted(error=ProviderError("Please try again soon.", status))) as c:
        r = post_diagnose(c, auth_headers(c))
    assert r.status_code == status and r.json() == {"detail": "Please try again soon."}


def test_anthropic_provider_needs_a_key():
    from app.core.config import Settings
    from app.main import build_vision
    with pytest.raises(ValueError):
        build_vision(Settings(vision_provider="anthropic", anthropic_api_key="", _env_file=None))
    assert build_vision(Settings(vision_provider="anthropic", anthropic_api_key="k", _env_file=None)).name == "anthropic"


# --- share card ---------------------------------------------------------------------------------

def test_share_card_content(client, headers):
    d = post_diagnose(client, headers, crop="cassava", lat="5.05171", lon="7.91279", symptoms_text="yellow curling leaves").json()
    r = client.post("/v1/share-card", headers=headers, json={"session_id": d["session_id"]})
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == d["session_id"]
    text = body["text"]
    assert "Crop: cassava" in text and "Cassava mosaic disease" in text and "82%" in text and "sure" in text
    assert "5.05, 7.91" in text and "5.0517" not in text  # about 1 km, not exact
    assert "Farmer observed: yellow curling leaves" in text
    assert "Questions for the officer" in text and "1. " in text
    assert "AI suggestion" in text
    assert "image" not in text.lower().replace("what the app saw", "")


def test_share_card_without_location_or_symptoms(client, headers):
    d = post_diagnose(client, headers, crop="yam").json()
    text = client.post("/v1/share-card", headers=headers, json={"session_id": d["session_id"]}).json()["text"]
    assert "Location" not in text and "Farmer observed" not in text


def test_share_card_includes_escalation_reason(client, headers):
    d = post_diagnose(client, headers, crop="pepper").json()
    text = client.post("/v1/share-card", headers=headers, json={"session_id": d["session_id"]}).json()["text"]
    assert "Why I am sending this" in text and "not sure" in text


def test_share_card_needs_a_diagnosis(client, headers):
    sid = client.post("/v1/chat", headers=headers, json={"message": "hello"}).json()["session_id"]
    assert client.post("/v1/share-card", headers=headers, json={"session_id": sid}).status_code == 409


def test_share_card_session_rules(client):
    a, b = auth_headers(client), auth_headers(client)
    sid = post_diagnose(client, a, crop="yam").json()["session_id"]
    assert client.post("/v1/share-card", headers=b, json={"session_id": sid}).status_code == 404
    assert client.post("/v1/share-card", headers=a, json={"session_id": str(uuid.uuid4())}).status_code == 404
    assert client.post("/v1/share-card", headers=a, json={"session_id": "nope"}).status_code == 422
    assert client.post("/v1/share-card", json={"session_id": sid}).status_code == 401


def test_share_card_after_delete_is_gone(client, headers):
    sid = post_diagnose(client, headers, crop="yam").json()["session_id"]
    client.delete(f"/v1/session/{sid}", headers=headers)
    assert client.post("/v1/share-card", headers=headers, json={"session_id": sid}).status_code == 404
