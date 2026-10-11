from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.db.engine import Database
from app.db.models import SessionRow
from app.schemas.common import Language
from app.services.session_store import MAX_HISTORY, PURGE_EVERY, SessionStore


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now


@pytest.fixture
async def db(tmp_path):
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 's.db'}")
    await database.ensure_ready()
    yield database
    await database.dispose()


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(db, clock):
    return SessionStore(db, ttl_seconds=1800, clock=clock)


async def row(db, sid):
    async with db.session() as s:
        return await s.get(SessionRow, sid)


async def test_session_has_30_minute_ttl(store, db, clock):
    s = await store.create("dev1")
    r = await row(db, s.id)
    assert r.expires_at.replace(tzinfo=timezone.utc) == clock.now + timedelta(seconds=1800)


async def test_ttl_refreshed_on_read(store, db, clock):
    s = await store.create("dev1")
    clock.now += timedelta(minutes=29)
    assert await store.get(s.id, "dev1") is not None
    clock.now += timedelta(minutes=29)  # would be 58 min after creation: alive only because the read refreshed it
    assert await store.get(s.id, "dev1") is not None


async def test_session_expires_and_is_removed(store, db, clock):
    s = await store.create("dev1")
    clock.now += timedelta(minutes=31)
    assert await store.get(s.id, "dev1") is None
    assert await row(db, s.id) is None  # purged, not just hidden


async def test_location_rounded_to_two_decimals(store):
    s = await store.create("dev1", lat=5.123456, lon=7.987654, language=Language.pcm)
    got = await store.get(s.id, "dev1")
    assert (got.lat, got.lon) == (5.12, 7.99) and got.language is Language.pcm


async def test_other_device_cannot_read_or_delete(store):
    s = await store.create("dev1")
    assert await store.get(s.id, "dev2") is None
    assert await store.delete(s.id, "dev2") is False
    assert await store.get(s.id, "dev1") is not None


async def test_delete_is_immediate(store, db):
    s = await store.create("dev1")
    assert await store.delete(s.id, "dev1") is True
    assert await row(db, s.id) is None


async def test_save_persists_changes(store):
    s = await store.create("dev1")
    s.add_turn("farmer", "hello")
    await store.save(s)
    assert (await store.get(s.id, "dev1")).history == [{"role": "farmer", "text": "hello"}]


async def test_history_is_capped(store):
    s = await store.create("dev1")
    for i in range(MAX_HISTORY + 5):
        s.add_turn("farmer", str(i))
    assert len(s.history) == MAX_HISTORY and s.history[-1]["text"] == str(MAX_HISTORY + 4)


async def test_expired_rows_are_purged_as_the_store_is_used(store, db, clock):
    for _ in range(5):
        await store.create("dev1")
    clock.now += timedelta(hours=1)
    for _ in range(PURGE_EVERY):
        await store.create("dev2")
    async with db.session() as s:
        remaining = await s.scalar(select(func.count()).select_from(SessionRow))
    assert remaining == PURGE_EVERY  # only the fresh ones survive
