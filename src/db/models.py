"""SQLAlchemy ORM models for the BGX dashboard."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class Season(Base):
    __tablename__ = "season"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    year: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # 'aggregate_2025' (legacy season-total CSVs, one event row per race) or
    # 'per_event' (per-event raw results, app computes standings).
    championship_format: Mapped[str] = mapped_column(String(32), nullable=False, default="per_event")

    categories: Mapped[list["Category"]] = relationship(back_populates="season", cascade="all, delete-orphan")
    events: Mapped[list["Event"]] = relationship(back_populates="season", cascade="all, delete-orphan")
    riders: Mapped[list["Rider"]] = relationship(back_populates="season", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    season: Mapped[Season] = relationship(back_populates="categories")
    riders: Mapped[list["Rider"]] = relationship(back_populates="category", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("season_id", "code", name="uq_category_season_code"),
    )


class Event(Base):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), nullable=False)
    slug: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    event_date: Mapped[Optional[datetime]] = mapped_column(Date, nullable=True)
    location: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    event_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    season: Mapped[Season] = relationship(back_populates="events")
    results: Mapped[list["EventResult"]] = relationship(back_populates="event", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("season_id", "slug", name="uq_event_season_slug"),
    )


class Rider(Base):
    __tablename__ = "rider"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    season_id: Mapped[int] = mapped_column(ForeignKey("season.id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id", ondelete="CASCADE"), nullable=False)
    race_number: Mapped[int] = mapped_column(Integer, nullable=False)
    first_name: Mapped[str] = mapped_column(String(128), nullable=False)
    last_name: Mapped[str] = mapped_column(String(128), nullable=False)
    team: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bike: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    season: Mapped[Season] = relationship(back_populates="riders")
    category: Mapped[Category] = relationship(back_populates="riders")
    results: Mapped[list["EventResult"]] = relationship(back_populates="rider", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("category_id", "race_number", name="uq_rider_category_race_number"),
    )


class EventResult(Base):
    __tablename__ = "event_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    rider_id: Mapped[int] = mapped_column(ForeignKey("rider.id", ondelete="CASCADE"), nullable=False)

    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    points: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    time_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    start_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    gps_penalty_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    cp_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    laps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gap_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="results")
    rider: Mapped[Rider] = relationship(back_populates="results")

    __table_args__ = (
        UniqueConstraint("event_id", "rider_id", name="uq_result_event_rider"),
        Index("ix_result_event", "event_id"),
        Index("ix_result_rider", "rider_id"),
    )


class Visit(Base):
    __tablename__ = "visit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    page: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    season_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    device_type: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")

    __table_args__ = (
        Index("ix_visit_timestamp", "timestamp"),
    )
