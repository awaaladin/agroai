"""Tables. Knowledge (crops, problems, aliases, safety lists, region) is editable data; sessions are short-lived."""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, MetaData, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship



def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    # No schema here on purpose: Database.engine maps it (Postgres only), so SQLite and tests are unaffected.
    metadata = MetaData()


class Region(Base):
    """Key/value facts about the region (rain seasons), e.g. key='main_rains', value='March to July'."""

    __tablename__ = "region"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Crop(Base):
    __tablename__ = "crops"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)  # 'cassava'
    local_names: Mapped[list] = mapped_column(JSON, default=list)
    growth_stages: Mapped[list] = mapped_column(JSON, default=list)  # [{name, period, notes}]
    planting_calendar: Mapped[str] = mapped_column(Text, default="")
    problems: Mapped[list["CropProblem"]] = relationship(back_populates="crop", cascade="all, delete-orphan",
                                                         order_by="CropProblem.position", lazy="selectin")


class CropProblem(Base):
    __tablename__ = "crop_problems"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    crop_key: Mapped[str] = mapped_column(ForeignKey("crops.key", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str] = mapped_column(String(40))  # virus, fungus, pest, bacteria...
    serious: Mapped[bool] = mapped_column(Boolean, default=False)  # serious or fast spreading -> escalate
    signs: Mapped[str] = mapped_column(Text)
    low_cost_actions: Mapped[str] = mapped_column(Text)
    crop: Mapped[Crop] = relationship(back_populates="problems")


class CropAlias(Base):
    """Any name a farmer might use for a crop: 'akpu', 'isu', 'oka', 'corn', 'banana'..."""

    __tablename__ = "crop_aliases"
    alias: Mapped[str] = mapped_column(String(60), primary_key=True)  # lower case
    crop_key: Mapped[str] = mapped_column(ForeignKey("crops.key", ondelete="CASCADE"))


class SafetyTerm(Base):
    """Chemical and scope safety lists. kind is one of the KINDS in app.db.seed."""

    __tablename__ = "safety_terms"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, default=0)


class SessionRow(Base):
    """A farmer's short-lived conversation. Deleted when it expires or when the farmer deletes it."""

    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(64))  # device uuid or "user:<uuid>"
    data: Mapped[str] = mapped_column(Text)  # JSON of the Session model
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_sessions_expires_at", "expires_at"),)


class User(Base):
    """A farmer's account. Phone number plus PIN; no email, no password reset by email."""

    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # +2348031234567
    pin_hash: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(80), default="")
    language: Mapped[str] = mapped_column(String(4), default="en")
    town: Mapped[str] = mapped_column(String(60), default="")
    lat: Mapped[float | None] = mapped_column(nullable=True)  # rounded to 2 decimals
    lon: Mapped[float | None] = mapped_column(nullable=True)
    crops: Mapped[list] = mapped_column(JSON, default=list)  # crops this farmer grows
    notes: Mapped[str] = mapped_column(Text, default="")  # the farmer's own notes about the farm
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CheckRow(Base):
    """One saved crop check (the answer only: photos are never stored)."""

    __tablename__ = "checks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    crop: Mapped[str] = mapped_column(String(40), default="")
    problem: Mapped[str] = mapped_column(String(200), default="")
    confidence: Mapped[float] = mapped_column(default=0.0)
    escalate: Mapped[bool] = mapped_column(Boolean, default=False)
    symptoms: Mapped[str] = mapped_column(Text, default="")
    data: Mapped[str] = mapped_column(Text)  # JSON of the DiagnoseResponse


class ChatMessageRow(Base):
    """Chat turns kept for logged-in farmers so the advisor remembers earlier conversations."""

    __tablename__ = "chat_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    role: Mapped[str] = mapped_column(String(10))  # farmer | advisor
    text: Mapped[str] = mapped_column(Text)
