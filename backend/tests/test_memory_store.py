import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.memory_store import MemoryStore
from app.main import build_store, create_app
from tests.fakes.mock_provider import MockProvider
from tests.fakes.mock_weather import MockWeatherProvider
from tests.conftest import auth_headers, make_image


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(clock):
    return MemoryStore(clock)


async def test_set_get_and_missing(store):
    assert await store.get("a") is None
    await store.set("a", "1")
    assert await store.get("a") == "1" and await store.ping() is True


async def test_expiry(store, clock):
    await store.set("a", "1", ex=10)
    assert await store.ttl("a") == 10
    clock.now += 9.9
    assert await store.get("a") == "1"
    clock.now += 0.2
    assert await store.get("a") is None and await store.ttl("a") == -2


async def test_ttl_codes_match_redis(store):
    await store.set("forever", "x")
    assert await store.ttl("forever") == -1 and await store.ttl("nope") == -2


async def test_expire_refreshes_and_ignores_missing(store, clock):
    await store.set("a", "1", ex=10)
    clock.now += 8
    assert await store.expire("a", 100) is True and await store.ttl("a") == 100
    assert await store.expire("missing", 5) is False


async def test_delete(store):
    await store.set("a", "1")
    assert await store.delete("a", "b") == 1 and await store.get("a") is None


async def test_incr_counts_and_keeps_expiry(store, clock):
    assert await store.incr("n") == 1
    await store.expire("n", 60)
    assert await store.incr("n") == 2 and await store.ttl("n") == 60
    clock.now += 61
    assert await store.incr("n") == 1  # expired window starts over


async def test_expired_keys_are_swept(store, clock):
    for i in range(300):
        await store.set(f"k{i}", "v", ex=1)
    clock.now += 5
    for i in range(300):  # more writes trigger the sweep
        await store.set(f"live{i}", "v", ex=100)
    assert len(store._data) < 400


def test_default_settings_use_memory_store():
    assert isinstance(build_store(Settings(_env_file=None)), MemoryStore)
    assert isinstance(build_store(Settings(redis_url="memory://", _env_file=None)), MemoryStore)


def test_redis_url_builds_a_redis_client():
    from redis.asyncio import Redis
    assert isinstance(build_store(Settings(redis_url="redis://localhost:6379/0", _env_file=None)), Redis)


def test_full_journey_without_redis_or_docker():
    """The default app, no injected Redis at all: health, token, diagnose, chat, share card, delete."""
    settings = Settings(jwt_secret="test-secret-test-secret-test-secret-123", _env_file=None)
    with TestClient(create_app(settings, vision=MockProvider(), weather_provider=MockWeatherProvider())) as c:
        assert c.get("/v1/health").json()["redis"] is True
        h = auth_headers(c)
        d = c.post("/v1/diagnose", headers=h, files={"image": ("l.jpg", make_image(), "image/jpeg")},
                   data={"crop": "maize", "lat": "5.05", "lon": "7.91"}).json()
        sid = d["session_id"]
        assert c.post("/v1/chat", headers=h, json={"session_id": sid, "message": "What first?"}).status_code == 200
        assert "Likely problem" in c.post("/v1/share-card", headers=h, json={"session_id": sid}).json()["text"]
        assert c.delete(f"/v1/session/{sid}", headers=h).status_code == 204
        assert c.post("/v1/chat", headers=h, json={"session_id": sid, "message": "hi"}).status_code == 404
        assert c.post("/v1/chat", headers=h, json={"session_id": str(uuid.uuid4()), "message": "hi"}).status_code == 404
