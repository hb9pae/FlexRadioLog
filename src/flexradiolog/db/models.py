"""Database models for FlexRadioLog."""

from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return current UTC datetime (naive for consistent SQLite storage)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def calculate_duration_seconds(start: datetime, end: datetime) -> int:
    """Calculate duration in seconds between two datetimes handling tzinfo."""
    s = start.replace(tzinfo=None) if start.tzinfo is not None else start
    e = end.replace(tzinfo=None) if end.tzinfo is not None else end
    return max(0, int((e - s).total_seconds()))


def calculate_duration_float(start: datetime, end: datetime) -> float:
    """Calculate duration as float seconds between two datetimes handling tzinfo."""
    s = start.replace(tzinfo=None) if start.tzinfo is not None else start
    e = end.replace(tzinfo=None) if end.tzinfo is not None else end
    return max(0.0, round((e - s).total_seconds(), 3))


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


class IpAllocation(Base):
    """Mapping of client IP addresses to callsigns and operators."""
    __tablename__ = "ip_allocations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_address: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    callsign: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    operator_name: Mapped[Optional[str]] = mapped_column(String(128), default="")
    notes: Mapped[Optional[str]] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class Session(Base):
    """User/Client connection session to the FlexRadio."""
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    client_uuid: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    client_handle: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    client_ip: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    callsign: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    client_name: Mapped[Optional[str]] = mapped_column(String(64), default="")
    station: Mapped[Optional[str]] = mapped_column(String(64), default="")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    disconnect_reason: Mapped[Optional[str]] = mapped_column(String(64), default="ACTIVE")

    # Relationships
    ptt_events: Mapped[List["PttEvent"]] = relationship("PttEvent", back_populates="session", cascade="all, delete-orphan")


class PttEvent(Base):
    """Individual PTT keying event with frequency and duration."""
    __tablename__ = "ptt_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="SET NULL"), index=True)
    client_handle: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0)
    frequency_hz: Mapped[int] = mapped_column(Integer, index=True, default=0)
    band: Mapped[str] = mapped_column(String(32), index=True, default="Unknown")
    mode: Mapped[Optional[str]] = mapped_column(String(32), default="")
    tx_slice_id: Mapped[Optional[int]] = mapped_column(Integer)

    # Relationships
    session: Mapped[Optional["Session"]] = relationship("Session", back_populates="ptt_events")


class SystemEvent(Base):
    """Operational and system log events."""
    __tablename__ = "system_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True, default="INFO")
    message: Mapped[str] = mapped_column(Text, nullable=False)
