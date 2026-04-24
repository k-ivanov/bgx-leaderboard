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

    def __str__(self) -> str:
        return str(self.year)


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

    def __str__(self) -> str:
        return f"{self.display_name} ({self.season.year})"


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

    def __str__(self) -> str:
        return f"{self.name} ({self.season.year})"


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

    def __str__(self) -> str:
        return f"#{self.race_number} {self.first_name} {self.last_name}"


class EventResult(Base):
    __tablename__ = "event_result"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"), nullable=False)
    rider_id: Mapped[int] = mapped_column(ForeignKey("rider.id", ondelete="CASCADE"), nullable=False)

    # Day number within the event (1 for single-day events, 1-N for multi-day).
    # Championship total for an event = sum of points across all days for the
    # same (rider, event) pair. See services/standings.py.
    day: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")

    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    points: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    time_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    start_time_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    gps_penalty_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # Separate checkpoint penalty time (ms); distinct from cp_count (kept for
    # forward compat — was the count of CPs hit; the new data source publishes
    # penalty time directly).
    cp_penalty_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    cp_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    laps: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gap_ms: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # FIN / DNF / DNS / DSQ. Nullable for legacy rows where status wasn't
    # recorded. UI can still infer a final state from position==None.
    status: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    event: Mapped[Event] = relationship(back_populates="results")
    rider: Mapped[Rider] = relationship(back_populates="results")

    __table_args__ = (
        # Allows the same (event, rider) pair to have one row per day.
        UniqueConstraint("event_id", "rider_id", "day", name="uq_result_event_rider_day"),
        Index("ix_result_event", "event_id"),
        Index("ix_result_rider", "rider_id"),
    )

    def __str__(self) -> str:
        pos = f"P{self.position}" if self.position else "—"
        day_suffix = f" D{self.day}" if self.day > 1 else ""
        return f"{pos} {self.rider} @ {self.event}{day_suffix}"


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
