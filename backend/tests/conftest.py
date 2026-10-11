import asyncio
import functools
import io
import random
import uuid

import fakeredis
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings
from app.main import create_app
from tests.fakes.mock_provider import MockProvider
from tests.fakes.mock_stt import MockSTT
from tests.fakes.mock_weather import MockWeatherProvider


@pytest.fixture(scope="session", autouse=True)
def _knowledge(tmp_path_factory):
    """Load the crop/safety snapshot from a real, freshly seeded SQLite database (the app reads the same way)."""
    from app.db.engine import Database

    async def load():
        db = Database(f"sqlite+aiosqlite:///{tmp_path_factory.mktemp('kb') / 'kb.db'}")
        await db.ensure_ready()
        await db.dispose()

    asyncio.run(load())


@pytest.fixture(autouse=True)
def _database_url(tmp_path, monkeypatch):
    """Every test gets its own empty SQLite file; nothing is ever written to the working directory."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def settings() -> Settings:
    return Settings(jwt_secret="test-secret-test-secret-test-secret-123", env="test", _env_file=None)


@pytest.fixture
def redis():
    return fakeredis.FakeAsyncRedis(decode_responses=True)


@pytest.fixture
def make_client(settings, redis):
    """Factory so a test can swap in another weather scenario."""

    def _make(weather=None) -> TestClient:
        return TestClient(create_app(settings, redis=redis, vision=MockProvider(), stt=MockSTT(),
                              weather_provider=weather or MockWeatherProvider()))

    return _make


@pytest.fixture
def client(make_client) -> TestClient:
    with make_client() as c:
        yield c


def auth_headers(client: TestClient, device_id: str | None = None) -> dict:
    r = client.post("/v1/auth/anon", json={"device_id": device_id or str(uuid.uuid4())})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def headers(client) -> dict:
    return auth_headers(client)


@functools.cache
def make_image(color=(70, 140, 60), size=(400, 400), fmt="JPEG") -> bytes:
    """A detailed, bright image (leaf-like texture): passes the quality gate. Dark colours still fail the dark check."""
    rnd = random.Random(7)
    clip = lambda v: max(0, min(255, v))  # noqa: E731
    img = Image.new("RGB", size)
    img.putdata([tuple(clip(c + rnd.randint(-40, 40)) for c in color) for _ in range(size[0] * size[1])])
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()
