"""Short-lived sessions in the database. 30-minute TTL, refreshed on use, deleted at expiry or on request.

Location is rounded to 2 decimals and stays only inside the session. Expired rows are never returned and are purged
as the store is used, so nothing outlives its time.
"""
import uuid
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select

from app.db.models import SessionRow
from app.schemas.common import Language
from app.schemas.diagnose import Diagnosis

MAX_HISTORY = 12  # turns kept for chat context
PURGE_EVERY = 25  # sweep expired rows every N creates


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)  # SQLite returns naive datetimes


class Session(BaseModel):
    id: str
    device_id: str
    language: Language = Language.en
    crop: str | None = None
    lat: float | None = None  # rounded to 2 decimals (~1 km)
    lon: float | None = None
    diagnosis: Diagnosis | None = None
    symptoms_text: str | None = None
    history: list[dict] = Field(default_factory=list)

    @field_validator("lat", "lon")
    @classmethod
    def _round(cls, v: float | None) -> float | None:
        return None if v is None else round(v, 2)

    def add_turn(self, role: str, text: str) -> None:
        self.history.append({"role": role, "text": text})
        del self.history[:-MAX_HISTORY]


class SessionStore:
    def __init__(self, db, ttl_seconds: int, clock=_now):
        self.db = db
        self.ttl = ttl_seconds
        self._clock = clock
        self._creates = 0

    def _expiry(self) -> datetime:
        return self._clock() + timedelta(seconds=self.ttl)

    async def create(self, device_id: str, **fields) -> Session:
        session = Session(id=str(uuid.uuid4()), device_id=device_id, **fields)
        async with self.db.session() as s:
            s.add(SessionRow(id=session.id, device_id=device_id, data=session.model_dump_json(), expires_at=self._expiry()))
            self._creates += 1
            if self._creates % PURGE_EVERY == 0:
                await s.execute(delete(SessionRow).where(SessionRow.expires_at < self._clock()))
            await s.commit()
        return session

    async def save(self, session: Session) -> None:
        async with self.db.session() as s:
            row = await s.get(SessionRow, session.id)
            if row is None:  # expired and purged meanwhile: recreate so the reply is not lost
                row = SessionRow(id=session.id, device_id=session.device_id, data="", expires_at=self._expiry())
                s.add(row)
            row.data = session.model_dump_json()
            row.expires_at = self._expiry()
            await s.commit()

    async def get(self, session_id: str, device_id: str) -> Session | None:
        """The session if it exists, is unexpired and belongs to this device; refreshes the TTL."""
        async with self.db.session() as s:
            row = await s.get(SessionRow, session_id)
            if row is None:
                return None
            if _aware(row.expires_at) <= self._clock():
                await s.delete(row)
                await s.commit()
                return None
            if row.device_id != device_id:
                return None  # same answer as "not found" so IDs cannot be probed
            row.expires_at = self._expiry()
            await s.commit()
            return Session.model_validate_json(row.data)

    async def delete(self, session_id: str, device_id: str) -> bool:
        async with self.db.session() as s:
            row = await s.get(SessionRow, session_id)
            if row is None or row.device_id != device_id:
                return False
            await s.delete(row)
            await s.commit()
            return True

    async def count(self) -> int:
        from sqlalchemy import func
        async with self.db.session() as s:
            return await s.scalar(select(func.count()).select_from(SessionRow)) or 0
