"""Accounts, saved history and the personal context the advisor uses. Photos are never stored."""
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.core.config import Settings
from app.core.security import hash_pin, mask_phone, normalize_phone, valid_pin, verify_pin
from app.db.models import ChatMessageRow, CheckRow, User
from app.schemas.accounts import ChatTurn, CheckSummary, ConversationSummary, Profile, ProfileUpdate
from app.schemas.diagnose import DiagnoseResponse
from app.services.crop_names import normalize_crop

log = logging.getLogger("agroai.accounts")

MAX_HISTORY_KEPT = 200  # checks per farmer
MAX_CHAT_KEPT = 200
CONTEXT_CHECKS = 5  # past checks the advisor is told about
CONTEXT_CHAT = 6  # recent chat turns the advisor is reminded of
CONVERSATION_GAP = timedelta(minutes=45)  # a longer silence starts a new conversation


class AccountError(Exception):
    def __init__(self, status: int, message: str, message_pcm: str = ""):
        super().__init__(message)
        self.status = status
        self.message = message
        self.message_pcm = message_pcm or message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@dataclass
class FarmerContext:
    """What the advisor knows about a logged-in farmer. Built fresh for every request."""

    first_name: str = ""
    town: str = ""
    crops: list[str] = field(default_factory=list)
    notes: str = ""
    language: str = "en"
    recent_checks: list[dict] = field(default_factory=list)  # {date, crop, problem, confidence, escalate}
    recent_chat: list[dict] = field(default_factory=list)  # {role, text}


class AccountService:
    def __init__(self, db, settings: Settings, store):
        self.db = db
        self.settings = settings
        self.store = store  # rate-limit counters (memory or Redis)

    # ---- register / login ------------------------------------------------------------------------------------

    async def register(self, *, phone: str, pin: str, name: str, language: str, town: str,
                       lat: float | None, lon: float | None) -> User:
        norm = normalize_phone(phone)
        if norm is None:
            raise AccountError(422, "Please enter a Nigerian mobile number, like 0803 123 4567.",
                               "Abeg enter Nigerian phone number, like 0803 123 4567.")
        if not valid_pin(pin):
            raise AccountError(422, "Your PIN must be 4 to 6 numbers.", "Your PIN must be 4 to 6 numbers.")
        async with self.db.session() as s:
            if await s.scalar(select(User).where(User.phone == norm)):
                raise AccountError(409, "This number already has an account. Please log in.",
                                   "This number don get account. Abeg log in.")
            user = User(
                id=str(uuid.uuid4()), phone=norm, pin_hash=hash_pin(pin, norm, self.settings.jwt_secret),
                name=name.strip()[:80], language=language, town=town.strip()[:60],
                lat=None if lat is None else round(lat, 2), lon=None if lon is None else round(lon, 2),
                crops=[], notes="", last_login=_now(),
            )
            s.add(user)
            await s.commit()
            return user

    async def login(self, *, phone: str, pin: str) -> User:
        norm = normalize_phone(phone) or ""
        key = f"agroai:login_fail:{norm or 'invalid'}"
        failures = int((await self.store.get(key)) or 0)
        if failures >= self.settings.login_max_failures:
            wait = max(1, await self.store.ttl(key))
            raise AccountError(429, f"Too many wrong tries. Please wait {wait // 60 + 1} minutes and try again.",
                               f"Too many wrong tries. Abeg wait {wait // 60 + 1} minutes then try again.")
        async with self.db.session() as s:
            user = await s.scalar(select(User).where(User.phone == norm)) if norm else None
            # Always do the expensive hash so a missing account takes as long as a wrong PIN.
            ok = verify_pin(pin, norm, self.settings.jwt_secret, user.pin_hash if user else "scrypt$00$00")
            if not (user and ok):
                n = await self.store.incr(key)
                if n == 1:
                    await self.store.expire(key, self.settings.login_window_seconds)
                raise AccountError(401, "That number or PIN is not right. Please try again.",
                                   "That number or PIN no correct. Abeg try again.")
            await self.store.delete(key)
            user.last_login = _now()
            await s.commit()
            return user

    # ---- profile ---------------------------------------------------------------------------------------------

    async def get(self, user_id: str) -> User:
        async with self.db.session() as s:
            user = await s.get(User, user_id)
        if user is None:
            raise AccountError(401, "Please log in again.")
        return user

    async def profile(self, user: User) -> Profile:
        async with self.db.session() as s:
            count = await s.scalar(select(func.count()).select_from(CheckRow).where(CheckRow.user_id == user.id)) or 0
            last = await s.scalar(select(func.max(CheckRow.created_at)).where(CheckRow.user_id == user.id))
        return Profile(
            id=user.id, phone=mask_phone(user.phone), name=user.name, language=user.language, town=user.town,
            lat=user.lat, lon=user.lon, crops=list(user.crops or []), notes=user.notes, created_at=_aware(user.created_at),
            checks_count=count, last_check_at=_aware(last),
        )

    async def update(self, user_id: str, patch: ProfileUpdate) -> User:
        data = patch.model_dump(exclude_unset=True)
        async with self.db.session() as s:
            user = await s.get(User, user_id)
            if user is None:
                raise AccountError(401, "Please log in again.")
            if "name" in data and data["name"] is not None:
                user.name = data["name"].strip()
            if "language" in data and data["language"] is not None:
                user.language = data["language"].value
            if "town" in data and data["town"] is not None:
                user.town = data["town"].strip()
            if "lat" in data:
                user.lat = None if data["lat"] is None else round(data["lat"], 2)
            if "lon" in data:
                user.lon = None if data["lon"] is None else round(data["lon"], 2)
            if "crops" in data and data["crops"] is not None:
                seen: list[str] = []
                for c in data["crops"]:
                    key = normalize_crop(c)
                    if key and key not in seen:
                        seen.append(key[:40])
                user.crops = seen
            if "notes" in data and data["notes"] is not None:
                user.notes = data["notes"].strip()
            await s.commit()
            return user

    # ---- history ---------------------------------------------------------------------------------------------

    async def save_check(self, user_id: str, response: DiagnoseResponse, symptoms: str | None) -> str | None:
        if response.assessment is None:
            return None
        row = CheckRow(
            id=response.session_id or str(uuid.uuid4()), user_id=user_id, created_at=_now(),
            crop=(response.crop.name if response.crop else "")[:40], problem=response.assessment.likely_problem[:200],
            confidence=response.assessment.confidence, escalate=response.escalate.recommended,
            symptoms=(symptoms or "")[:500], data=response.model_dump_json(),
        )
        async with self.db.session() as s:
            s.add(row)
            await s.commit()
            # Keep the newest MAX_HISTORY_KEPT checks.
            old = (await s.scalars(select(CheckRow.id).where(CheckRow.user_id == user_id)
                                   .order_by(CheckRow.created_at.desc()).offset(MAX_HISTORY_KEPT))).all()
            if old:
                await s.execute(delete(CheckRow).where(CheckRow.id.in_(old)))
                await s.commit()
        return row.id

    async def list_checks(self, user_id: str, limit: int = 20, offset: int = 0) -> list[CheckSummary]:
        async with self.db.session() as s:
            rows = (await s.scalars(select(CheckRow).where(CheckRow.user_id == user_id)
                                    .order_by(CheckRow.created_at.desc()).limit(limit).offset(offset))).all()
        return [CheckSummary(id=r.id, created_at=_aware(r.created_at), crop=r.crop, problem=r.problem,
                             confidence=r.confidence, escalate=r.escalate) for r in rows]

    async def get_check(self, user_id: str, check_id: str) -> tuple[DiagnoseResponse, datetime] | None:
        async with self.db.session() as s:
            row = await s.get(CheckRow, check_id)
        if row is None or row.user_id != user_id:
            return None
        return DiagnoseResponse.model_validate_json(row.data), _aware(row.created_at)

    async def delete_check(self, user_id: str, check_id: str) -> bool:
        async with self.db.session() as s:
            row = await s.get(CheckRow, check_id)
            if row is None or row.user_id != user_id:
                return False
            await s.delete(row)
            await s.commit()
            return True

    async def clear_history(self, user_id: str) -> None:
        async with self.db.session() as s:
            await s.execute(delete(CheckRow).where(CheckRow.user_id == user_id))
            await s.execute(delete(ChatMessageRow).where(ChatMessageRow.user_id == user_id))
            await s.commit()

    async def delete_account(self, user_id: str) -> None:
        await self.clear_history(user_id)
        async with self.db.session() as s:
            user = await s.get(User, user_id)
            if user:
                await s.delete(user)
                await s.commit()

    # ---- chat memory -----------------------------------------------------------------------------------------

    async def save_chat(self, user_id: str, farmer_text: str, advisor_text: str) -> None:
        async with self.db.session() as s:
            s.add(ChatMessageRow(user_id=user_id, role="farmer", text=farmer_text[:1000], created_at=_now()))
            s.add(ChatMessageRow(user_id=user_id, role="advisor", text=advisor_text[:2000], created_at=_now()))
            await s.commit()
            old = (await s.scalars(select(ChatMessageRow.id).where(ChatMessageRow.user_id == user_id)
                                   .order_by(ChatMessageRow.id.desc()).offset(MAX_CHAT_KEPT))).all()
            if old:
                await s.execute(delete(ChatMessageRow).where(ChatMessageRow.id.in_(old)))
                await s.commit()

    async def _conversations(self, user_id: str) -> list[list[ChatMessageRow]]:
        """All kept chat messages for the farmer, split into conversations by time gaps (oldest first)."""
        async with self.db.session() as s:
            rows = (await s.scalars(select(ChatMessageRow).where(ChatMessageRow.user_id == user_id)
                                    .order_by(ChatMessageRow.id.asc()))).all()
        groups: list[list[ChatMessageRow]] = []
        for m in rows:
            if groups and _aware(m.created_at) - _aware(groups[-1][-1].created_at) <= CONVERSATION_GAP:
                groups[-1].append(m)
            else:
                groups.append([m])
        return groups

    async def list_conversations(self, user_id: str, limit: int = 20) -> list[ConversationSummary]:
        """Past conversations, newest first, each titled with the farmer's first question."""
        out = []
        for g in reversed(await self._conversations(user_id)):
            first_q = next((m.text for m in g if m.role == "farmer"), g[0].text)
            title = " ".join(first_q.split())
            out.append(ConversationSummary(
                id=g[0].id, started_at=_aware(g[0].created_at), last_at=_aware(g[-1].created_at),
                title=(title[:57] + "...") if len(title) > 60 else title, messages=len(g),
            ))
        return out[:limit]

    async def get_conversation(self, user_id: str, conversation_id: int) -> list[ChatTurn] | None:
        for g in await self._conversations(user_id):
            if g[0].id == conversation_id:
                return [ChatTurn(role=m.role, text=m.text, created_at=_aware(m.created_at)) for m in g]
        return None

    # ---- personalisation -------------------------------------------------------------------------------------

    async def context(self, user_id: str | None) -> FarmerContext | None:
        """The farmer's profile and recent history, for the advisor. None for guests."""
        if not user_id:
            return None
        async with self.db.session() as s:
            user = await s.get(User, user_id)
            if user is None:
                return None
            checks = (await s.scalars(select(CheckRow).where(CheckRow.user_id == user_id)
                                      .order_by(CheckRow.created_at.desc()).limit(CONTEXT_CHECKS))).all()
            chat = (await s.scalars(select(ChatMessageRow).where(ChatMessageRow.user_id == user_id)
                                    .order_by(ChatMessageRow.id.desc()).limit(CONTEXT_CHAT))).all()
        return FarmerContext(
            first_name=(user.name or "").split(" ")[0][:30], town=user.town, crops=list(user.crops or []),
            notes=user.notes, language=user.language,
            recent_checks=[{"date": _aware(c.created_at).date().isoformat(), "crop": c.crop, "problem": c.problem,
                            "confidence": round(c.confidence, 2), "escalate": c.escalate} for c in checks],
            recent_chat=[{"role": m.role, "text": m.text[:300]} for m in reversed(chat)],
        )
