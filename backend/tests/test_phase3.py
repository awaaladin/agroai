import json
import logging
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai.llm_provider import LLMProvider, Turn
from tests.fakes.mock_provider import MockProvider, build_diagnosis
from tests.fakes.mock_stt import MockSTT
from tests.fakes.mock_weather import MockWeatherProvider
from app.core.config import Settings
from app.core.memory_store import MemoryStore
from app.core.rate_limit import RateLimited, SpendCap, hit
from app.main import create_app
from app.schemas.chat import ChatAnswer
from app.schemas.common import Language
from app.schemas.diagnose import VisionOutput
from app.ai.provider import ChatInput, DiagnoseInput
from tests.conftest import auth_headers, make_image
from tests.test_endpoints import post_diagnose


def settings_with(**kw) -> Settings:
    return Settings(jwt_secret="test-secret-test-secret-test-secret-123", env="test", _env_file=None, **kw)


def make(**kw) -> TestClient:
    store = kw.pop("store", None) or MemoryStore()
    return TestClient(create_app(settings_with(**kw), redis=store, vision=MockProvider(), weather_provider=MockWeatherProvider(), stt=MockSTT()))


# --- rate limiter core --------------------------------------------------------------------------

class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


async def test_hit_counts_and_resets_after_the_window():
    clock = Clock()
    store = MemoryStore(clock)
    results = [await hit(store, "k", 3, 60) for _ in range(4)]
    assert [r[0] for r in results] == [True, True, True, False]
    assert 0 < results[-1][1] <= 60
    clock.now += 61
    assert (await hit(store, "k", 3, 60))[0] is True  # fresh window


async def test_counter_without_expiry_heals():
    store = MemoryStore()
    await store.set("k", "5")  # simulates a crash between incr and expire
    allowed, ttl = await hit(store, "k", 3, 60)
    assert allowed is False and ttl == 60 and await store.ttl("k") == 60


# --- rate limits over HTTP ----------------------------------------------------------------------

def test_diagnose_is_limited_per_device_with_retry_after():
    with make(rate_diagnose_device_per_hour=2) as c:
        h = auth_headers(c)
        assert post_diagnose(c, h, crop="yam").status_code == 200
        assert post_diagnose(c, h, crop="yam").status_code == 200
        r = post_diagnose(c, h, crop="yam")
        assert r.status_code == 429
        retry = int(r.headers["retry-after"])
        assert 1 <= retry <= 3600
        body = r.json()
        assert "too fast" in body["detail"] and "dey ask too fast" in body["detail_pcm"] and body["retry_after"] == retry
        # another device on the same IP is not blocked by the device limit
        assert post_diagnose(c, auth_headers(c), crop="yam").status_code == 200


def test_other_endpoints_have_their_own_buckets():
    with make(rate_diagnose_device_per_hour=1) as c:
        h = auth_headers(c)
        post_diagnose(c, h, crop="yam")
        assert post_diagnose(c, h, crop="yam").status_code == 429
        assert c.post("/v1/chat", headers=h, json={"message": "hi"}).status_code == 200  # chat unaffected
        assert c.get("/v1/weather/advice", headers=h, params={"lat": 5, "lon": 7}).status_code == 200


def test_chat_limit():
    with make(rate_chat_device_per_hour=2) as c:
        h = auth_headers(c)
        codes = [c.post("/v1/chat", headers=h, json={"message": "hi"}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


def test_general_per_minute_limit_covers_cheap_endpoints():
    with make(rate_device_per_minute=3) as c:
        h = auth_headers(c)
        codes = [c.get("/v1/weather/advice", headers=h, params={"lat": 5, "lon": 7}).status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]


def test_ip_limit_stops_a_device_id_farm():
    """Minting new device IDs is free, so the IP limit is what stops a script."""
    with make(rate_diagnose_ip_per_hour=3, rate_diagnose_device_per_hour=50) as c:
        codes = [post_diagnose(c, auth_headers(c), crop="yam").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]


def test_anon_token_requests_are_limited_per_ip():
    with make(rate_anon_ip_per_hour=2) as c:
        codes = [c.post("/v1/auth/anon", json={"device_id": str(uuid.uuid4())}).status_code for _ in range(3)]
        assert codes == [200, 200, 429]


def test_different_ips_are_counted_separately_behind_a_trusted_proxy():
    with make(rate_anon_ip_per_hour=1, trusted_proxy_hops=1) as c:
        def anon(ip):
            return c.post("/v1/auth/anon", json={"device_id": str(uuid.uuid4())}, headers={"X-Forwarded-For": ip}).status_code
        assert [anon("1.1.1.1"), anon("1.1.1.1"), anon("2.2.2.2")] == [200, 429, 200]


def test_spoofed_forwarded_header_is_ignored_without_a_trusted_proxy():
    with make(rate_anon_ip_per_hour=1, trusted_proxy_hops=0) as c:
        codes = [c.post("/v1/auth/anon", json={"device_id": str(uuid.uuid4())},
                        headers={"X-Forwarded-For": f"9.9.9.{i}"}).status_code for i in range(2)]
        assert codes == [200, 429]


def test_health_and_docs_are_not_limited():
    with make(rate_device_per_minute=1, rate_ip_per_minute=1) as c:
        assert all(c.get("/v1/health").status_code == 200 for _ in range(5))


def test_401_comes_before_rate_limiting():
    with make(rate_device_per_minute=1) as c:
        assert [c.get("/v1/weather/advice", params={"lat": 5, "lon": 7}).status_code for _ in range(3)] == [401] * 3


def test_limit_events_are_logged_without_content(caplog):
    caplog.set_level(logging.INFO)
    with make(rate_diagnose_device_per_hour=1) as c:
        h = auth_headers(c)
        post_diagnose(c, h, crop="yam", symptoms_text="private words")
        post_diagnose(c, h, crop="yam", symptoms_text="private words")
    text = " ".join(r.getMessage() + str(getattr(r, "extra_fields", "")) for r in caplog.records)
    assert "rate limit hit" in text and "diagnose" in text
    assert "private words" not in text and "testclient" not in text


# --- daily AI spend cap -------------------------------------------------------------------------

async def test_spend_cap_counts_and_blocks():
    cap = SpendCap(MemoryStore(), 3, now=lambda: datetime(2026, 10, 2, 22, 0, tzinfo=timezone.utc))
    for _ in range(3):
        await cap.reserve()
    with pytest.raises(RateLimited) as exc:
        await cap.reserve()
    assert exc.value.retry_after == 2 * 3600  # until 00:00 UTC
    assert exc.value.scope == "daily_ai_cap" and "tomorrow" in exc.value.message and exc.value.message_pcm
    assert await cap.used_today() == 4


async def test_spend_cap_resets_each_utc_day():
    day = {"now": datetime(2026, 10, 2, 23, 0, tzinfo=timezone.utc)}
    cap = SpendCap(MemoryStore(), 1, now=lambda: day["now"])
    await cap.reserve()
    with pytest.raises(RateLimited):
        await cap.reserve()
    day["now"] = datetime(2026, 10, 3, 0, 1, tzinfo=timezone.utc)
    await cap.reserve()  # new day, new budget


class FakeLLM(LLMProvider):
    """Counts model calls; first returns invalid output so the retry (a second paid call) is exercised."""

    name = "fake"

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    async def _generate(self, system, turns, fmt, effort):
        from app.ai.llm_provider import Generated
        self.calls += 1
        return Generated(parsed=self.outputs.pop(0))


def diag_input():
    return DiagnoseInput(image=make_image(), mime="image/jpeg", language=Language.en, crop="maize")


def good_output():
    return VisionOutput(photo_usable=True, diagnosis=build_diagnosis("maize_fall_armyworm", Language.en))


async def test_retries_count_against_the_cap_and_cap_stops_calls():
    p = FakeLLM([None, good_output(), good_output(), good_output()])  # first answer empty -> retry
    p.spend_cap = SpendCap(MemoryStore(), 3)
    await p.diagnose(diag_input())
    assert p.calls == 2  # retry counted
    await p.diagnose(diag_input())
    assert p.calls == 3
    with pytest.raises(RateLimited):
        await p.diagnose(diag_input())
    assert p.calls == 3  # the capped request never reached the model


def test_cap_over_http_returns_429_with_retry_after_and_never_calls_the_ai():
    store = MemoryStore()
    fake = FakeLLM([good_output()] * 10)
    app = create_app(settings_with(daily_ai_call_limit=1), redis=store, vision=fake, weather_provider=MockWeatherProvider())
    with TestClient(app) as c:
        h = auth_headers(c)
        assert post_diagnose(c, h, crop="maize").status_code == 200
        r = post_diagnose(c, h, crop="maize")
        assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
        assert "tomorrow" in r.json()["detail"]
        assert fake.calls == 1
        # chat is also an AI call
        assert c.post("/v1/chat", headers=h, json={"message": "hi"}).status_code == 429
        # things that do not use the AI still work
        assert c.get("/v1/weather/advice", headers=h, params={"lat": 5, "lon": 7}).status_code == 200


def test_mock_provider_is_never_capped():
    with make(daily_ai_call_limit=1) as c:
        h = auth_headers(c)
        assert all(post_diagnose(c, h, crop="yam").status_code == 200 for _ in range(3))


# --- CORS ---------------------------------------------------------------------------------------

def test_cors_allows_listed_origin_only():
    with make(allowed_origins="https://app.example.com, http://localhost:5173") as c:
        ok = c.get("/v1/health", headers={"Origin": "https://app.example.com"})
        assert ok.headers["access-control-allow-origin"] == "https://app.example.com"
        assert "access-control-allow-credentials" not in ok.headers
        assert "retry-after" in ok.headers.get("access-control-expose-headers", "").lower()
        bad = c.get("/v1/health", headers={"Origin": "https://evil.example.com"})
        assert "access-control-allow-origin" not in bad.headers


def test_cors_preflight():
    with make(allowed_origins="https://app.example.com") as c:
        r = c.options("/v1/diagnose", headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST",
                                               "Access-Control-Request-Headers": "authorization,content-type"})
        assert r.status_code == 200
        assert r.headers["access-control-allow-origin"] == "https://app.example.com"
        assert "authorization" in r.headers["access-control-allow-headers"].lower()
        bad = c.options("/v1/diagnose", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"})
        assert "access-control-allow-origin" not in bad.headers


def test_no_origins_configured_means_no_cors_headers():
    with make() as c:
        assert "access-control-allow-origin" not in c.get("/v1/health", headers={"Origin": "https://x.example.com"}).headers


def test_wildcard_origin_refused_in_production():
    with pytest.raises(ValueError):
        Settings(env="production", jwt_secret="x" * 40, allowed_origins="*", _env_file=None)


def test_cors_headers_also_on_errors():
    with make(allowed_origins="https://app.example.com", rate_device_per_minute=1) as c:
        h = {**auth_headers(c), "Origin": "https://app.example.com"}
        c.get("/v1/weather/advice", headers=h, params={"lat": 5, "lon": 7})
        r = c.get("/v1/weather/advice", headers=h, params={"lat": 5, "lon": 7})
        assert r.status_code == 429 and r.headers["access-control-allow-origin"] == "https://app.example.com"


# --- security headers ---------------------------------------------------------------------------

def test_security_headers_on_api_responses():
    with make() as c:
        r = c.get("/v1/health")
        assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"
        assert r.headers["referrer-policy"] == "no-referrer" and r.headers["cache-control"] == "no-store"
        assert "default-src 'none'" in r.headers["content-security-policy"]
        assert "camera=()" in r.headers["permissions-policy"]
        assert "strict-transport-security" not in r.headers  # only in production


def test_hsts_in_production():
    with TestClient(create_app(Settings(env="production", jwt_secret="x" * 40, _env_file=None), redis=MemoryStore(), vision=MockProvider(), weather_provider=MockWeatherProvider())) as c:
        assert "max-age=31536000" in c.get("/v1/health").headers["strict-transport-security"]


def test_docs_get_a_csp_that_lets_swagger_load():
    with make() as c:
        r = c.get("/docs")
        assert r.status_code == 200 and "cdn.jsdelivr.net" in r.headers["content-security-policy"]
        assert r.headers["x-content-type-options"] == "nosniff" and "cache-control" not in r.headers


def test_security_headers_on_errors_too():
    with make() as c:
        r = c.get("/v1/weather/advice", params={"lat": 5, "lon": 7})
        assert r.status_code == 401 and r.headers["x-frame-options"] == "DENY"


# --- request size limits ------------------------------------------------------------------------

def test_oversized_photo_rejected_by_content_length_before_parsing():
    with make(max_image_bytes=100_000) as c:
        h = auth_headers(c)
        big = b"\xff\xd8\xff" + b"0" * 300_000
        r = c.post("/v1/diagnose", headers=h, files={"image": ("a.jpg", big, "image/jpeg")})
        assert r.status_code == 413 and "too big" in r.json()["detail"]


def test_oversized_streamed_body_without_content_length_is_cut_off():
    with make(max_image_bytes=100_000) as c:
        h = {**auth_headers(c), "Content-Type": "multipart/form-data; boundary=xyz"}

        def chunks():
            yield b"--xyz\r\nContent-Disposition: form-data; name=\"image\"; filename=\"a.jpg\"\r\nContent-Type: image/jpeg\r\n\r\n"
            for _ in range(40):
                yield b"0" * 10_000
            yield b"\r\n--xyz--\r\n"

        r = c.post("/v1/diagnose", headers=h, content=chunks())  # chunked: no Content-Length
        assert r.status_code == 413


def test_json_bodies_are_capped_small():
    with make() as c:
        h = auth_headers(c)
        r = c.post("/v1/chat", headers=h, content=json.dumps({"message": "x" * 100_000}), )
        assert r.status_code == 413


def test_normal_sized_requests_unaffected():
    with make() as c:
        assert post_diagnose(c, auth_headers(c), crop="yam").status_code == 200


# --- strict validation --------------------------------------------------------------------------

@pytest.mark.parametrize("path,body", [
    ("/v1/chat", {"message": "hi", "admin": True}),
    ("/v1/auth/anon", {"device_id": str(uuid.uuid4()), "role": "admin"}),
    ("/v1/share-card", {"session_id": str(uuid.uuid4()), "extra": 1}),
])
def test_unknown_fields_are_rejected(path, body):
    with make() as c:
        headers = {} if path == "/v1/auth/anon" else auth_headers(c)
        assert c.post(path, headers=headers, json=body).status_code == 422


# --- logging ------------------------------------------------------------------------------------

def test_request_id_is_unique_and_logs_have_no_payload(caplog):
    caplog.set_level(logging.INFO)
    with make() as c:
        h = auth_headers(c)
        ids = {c.get("/v1/health").headers["x-request-id"] for _ in range(3)}
        assert len(ids) == 3
        c.post("/v1/chat", headers=h, json={"message": "my secret farm message", "lat": 5.123456, "lon": 7.654321})
    text = " ".join(r.getMessage() + str(getattr(r, "extra_fields", "")) for r in caplog.records)
    assert "agroai.access" in " ".join(r.name for r in caplog.records)
    assert "my secret farm message" not in text and "5.123456" not in text and "Bearer" not in text
