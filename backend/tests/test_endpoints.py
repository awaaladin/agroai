import uuid

import pytest

from tests.fakes.mock_provider import MockProvider
from tests.fakes.mock_weather import MockWeatherProvider
from tests.conftest import auth_headers, make_image


def post_diagnose(client, headers, image=None, content_type="image/jpeg", **form):
    files = {"image": ("leaf.jpg", image if image is not None else make_image(), content_type)}
    return client.post("/v1/diagnose", headers=headers, files=files, data=form)


# --- diagnose ---------------------------------------------------------------------------------

def test_diagnose_returns_full_contract(client, headers):
    r = post_diagnose(client, headers, crop="cassava", lat="5.0517", lon="7.9128", language="en")
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"session_id", "image_quality", "crop", "assessment", "actions", "prevention",
                         "farmer_questions", "weather_note", "escalate", "spoken_text"}
    assert uuid.UUID(body["session_id"])
    assert body["image_quality"] == {"usable": True, "issue": None, "advice": None}
    assert body["crop"]["name"] == "cassava"
    assert body["assessment"]["likely_problem"] == "Cassava mosaic disease"
    assert body["actions"][0]["step"] == 1 and body["actions"][0]["when"] in {"today", "this_week", "next_season"}
    assert body["weather_note"]  # location given -> weather rules ran


def test_diagnose_pidgin_and_local_crop_name(client, headers):
    body = post_diagnose(client, headers, crop="akpu", language="pcm").json()
    assert body["crop"]["name"] == "cassava"
    assert "dey" in body["spoken_text"]


def test_diagnose_without_location_has_no_weather_note(client, headers):
    assert post_diagnose(client, headers, crop="yam").json()["weather_note"] is None


def test_low_confidence_diagnosis_escalates(client, headers):
    body = post_diagnose(client, headers, crop="pepper").json()
    assert body["assessment"]["confidence"] < 0.6
    assert body["escalate"]["recommended"] is True and body["escalate"]["reason"]


def test_healthy_plant(client, headers):
    body = post_diagnose(client, headers, symptoms_text="it looks healthy to me").json()
    assert "healthy" in body["assessment"]["likely_problem"].lower()
    assert body["escalate"]["recommended"] is False


def test_dark_photo_is_unusable_and_not_guessed(client, headers):
    body = post_diagnose(client, headers, image=make_image(color=(5, 5, 5))).json()
    assert body["image_quality"]["usable"] is False and body["image_quality"]["issue"] == "too_dark"
    assert body["assessment"] is None and body["crop"] is None and body["session_id"] is None
    assert body["spoken_text"] == body["image_quality"]["advice"]


def test_tiny_photo_asks_to_come_closer_in_pidgin(client, headers):
    body = post_diagnose(client, headers, image=make_image(size=(80, 80)), language="pcm").json()
    assert body["image_quality"]["issue"] == "too_small"
    assert "near" in body["spoken_text"]


def test_unusable_photo_never_calls_the_ai(settings, redis):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.ai.provider import VisionProvider

    class Boom(VisionProvider):
        name = "boom"
        async def diagnose(self, req): raise AssertionError("AI must not be called")
        async def chat(self, req): raise AssertionError("AI must not be called")

    with TestClient(create_app(settings, redis=redis, vision=Boom(), weather_provider=MockWeatherProvider())) as c:
        r = post_diagnose(c, auth_headers(c), image=make_image(color=(0, 0, 0)))
        assert r.status_code == 200 and r.json()["image_quality"]["usable"] is False


@pytest.mark.parametrize("fmt,ct", [("PNG", "image/png"), ("WEBP", "image/webp")])
def test_png_and_webp_accepted(client, headers, fmt, ct):
    assert post_diagnose(client, headers, image=make_image(fmt=fmt), content_type=ct).status_code == 200


def test_wrong_content_type_rejected(client, headers):
    assert post_diagnose(client, headers, content_type="application/pdf").status_code == 415


def test_fake_image_bytes_rejected(client, headers):
    assert post_diagnose(client, headers, image=b"%PDF-1.4 not really an image").status_code == 415


def test_corrupt_jpeg_rejected(client, headers):
    assert post_diagnose(client, headers, image=b"\xff\xd8\xff" + b"garbage" * 50).status_code == 422


def test_oversize_rejected(client, headers):
    big = make_image() + b"\0" * (5 * 1024 * 1024)
    assert post_diagnose(client, headers, image=big).status_code == 413


@pytest.mark.parametrize("form", [{"lat": "95", "lon": "7"}, {"lat": "5"}, {"language": "fr"}, {"crop": "x" * 41}])
def test_bad_form_values_rejected(client, headers, form):
    assert post_diagnose(client, headers, **form).status_code == 422


def test_missing_image_is_422(client, headers):
    assert client.post("/v1/diagnose", headers=headers, data={"crop": "yam"}).status_code == 422


# --- chat -------------------------------------------------------------------------------------

def test_chat_without_session_creates_one(client, headers):
    r = client.post("/v1/chat", headers=headers, json={"message": "My cassava leaves are yellow", "language": "en"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert uuid.UUID(body["session_id"])
    assert body["answer_text"] and body["spoken_text"] and body["follow_up_suggestions"]
    assert set(body["escalate"]) == {"recommended", "reason"} and 0 <= body["confidence"] <= 1


def test_chat_continues_diagnosis_context(client, headers):
    d = post_diagnose(client, headers, crop="maize").json()
    r = client.post("/v1/chat", headers=headers, json={"session_id": d["session_id"], "message": "What should I do first?"})
    body = r.json()
    assert body["session_id"] == d["session_id"]
    assert "Fall armyworm" in body["answer_text"] and body["escalate"]["recommended"] is True


def test_chat_history_accumulates_in_session(client, headers):
    sid = client.post("/v1/chat", headers=headers, json={"message": "hello"}).json()["session_id"]
    client.post("/v1/chat", headers=headers, json={"session_id": sid, "message": "and again"})
    import json
    from app.db.models import SessionRow

    async def fetch():
        async with client.app.state.db.session() as db:
            return json.loads((await db.get(SessionRow, sid)).data)

    session = client.portal.call(fetch)
    assert [t["role"] for t in session["history"]] == ["farmer", "advisor", "farmer", "advisor"]


def test_chat_pulls_weather_for_spraying_question(client, headers):
    r = client.post("/v1/chat", headers=headers, json={"message": "Can I spray today?", "lat": 5.05, "lon": 7.91})
    assert "spraying" in r.json()["answer_text"].lower()


def test_chat_rain_blocks_spraying_advice(make_client):
    with make_client(MockWeatherProvider("rain")) as c:
        r = c.post("/v1/chat", headers=auth_headers(c), json={"message": "Can I spray today?", "lat": 5.05, "lon": 7.91})
        assert "do not spray" in r.json()["answer_text"].lower()


def test_chat_does_not_fetch_weather_for_other_questions(client, headers):
    r = client.post("/v1/chat", headers=headers, json={"message": "What is a good variety?", "lat": 5.05, "lon": 7.91})
    assert "spraying" not in r.json()["answer_text"].lower()


def test_chat_declines_out_of_scope(client, headers):
    r = client.post("/v1/chat", headers=headers, json={"message": "I need a loan from the bank"})
    assert "farming" in r.json()["answer_text"].lower()


def test_chat_unknown_session_is_404(client, headers):
    r = client.post("/v1/chat", headers=headers, json={"session_id": str(uuid.uuid4()), "message": "hi"})
    assert r.status_code == 404


def test_chat_cannot_use_another_devices_session(client):
    a, b = auth_headers(client), auth_headers(client)
    sid = client.post("/v1/chat", headers=a, json={"message": "hi"}).json()["session_id"]
    assert client.post("/v1/chat", headers=b, json={"session_id": sid, "message": "hi"}).status_code == 404


@pytest.mark.parametrize("payload", [{"message": ""}, {"message": "x" * 1001}, {"message": "hi", "language": "yo"}, {}])
def test_chat_validation(client, headers, payload):
    assert client.post("/v1/chat", headers=headers, json=payload).status_code == 422


# --- weather ----------------------------------------------------------------------------------

def test_weather_advice_contract(client, headers):
    r = client.get("/v1/weather/advice", headers=headers, params={"lat": 5.05171, "lon": 7.91279, "crop": "maize"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["lat"], body["lon"]) == (5.05, 7.91)
    assert len(body["days"]) == 5
    assert set(body["days"][0]) == {"date", "condition_code", "high_c", "low_c", "rain_chance_pct", "rain_mm", "wind_kph"}
    assert body["advice"] and set(body["advice"][0]) == {"code", "severity", "message", "message_pcm", "dates"}


def test_weather_rain_scenario_warns(make_client):
    with make_client(MockWeatherProvider("rain")) as c:
        body = c.get("/v1/weather/advice", headers=auth_headers(c), params={"lat": 5, "lon": 7.9}).json()
        assert body["advice"][0]["code"] == "no_spray_rain_likely"


@pytest.mark.parametrize("params", [{"lat": 91, "lon": 7}, {"lat": 5}, {"lat": "x", "lon": 7}])
def test_weather_validation(client, headers, params):
    assert client.get("/v1/weather/advice", headers=headers, params=params).status_code == 422


def test_weather_provider_failure_is_503(settings, redis):
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.weather.provider import WeatherProvider

    class Down(WeatherProvider):
        name = "down"
        async def forecast(self, lat, lon): raise RuntimeError("down")

    with TestClient(create_app(settings, redis=redis, vision=MockProvider(), weather_provider=Down())) as c:
        assert c.get("/v1/weather/advice", headers=auth_headers(c), params={"lat": 5, "lon": 7}).status_code == 503
        # a diagnosis still works when weather is down
        r = post_diagnose(c, auth_headers(c), crop="yam", lat="5", lon="7")
        assert r.status_code == 200 and r.json()["weather_note"] is None


# --- session ----------------------------------------------------------------------------------

def test_delete_session_removes_it(client, headers):
    sid = post_diagnose(client, headers, crop="yam").json()["session_id"]
    assert client.delete(f"/v1/session/{sid}", headers=headers).status_code == 204
    assert client.post("/v1/chat", headers=headers, json={"session_id": sid, "message": "hi"}).status_code == 404


def test_delete_is_idempotent_and_private(client):
    a, b = auth_headers(client), auth_headers(client)
    sid = post_diagnose(client, a, crop="yam").json()["session_id"]
    assert client.delete(f"/v1/session/{sid}", headers=b).status_code == 204  # no-op for another device
    assert client.post("/v1/chat", headers=a, json={"session_id": sid, "message": "hi"}).status_code == 200
    assert client.delete(f"/v1/session/{uuid.uuid4()}", headers=a).status_code == 204


def test_delete_rejects_bad_uuid(client, headers):
    assert client.delete("/v1/session/not-a-uuid", headers=headers).status_code == 422


def test_openapi_and_docs_available(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
