"""Private analytics endpoint schemas (auth-gated)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DeviceCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_type: str
    count: int


class CategoryVisitCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: Optional[str] = None
    season_year: Optional[int] = None
    count: int


class RaceVisitCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season_year: Optional[int] = None
    event_slug: str
    count: int


class RiderVisitCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season_year: Optional[int] = None
    rider_slug: str
    count: int


class ComparisonCount(BaseModel):
    """One row in the top-comparisons aggregation. Slugs are normalized
    alphabetically by the track endpoint so (A,B) and (B,A) bucket as
    one pair."""
    model_config = ConfigDict(from_attributes=True)

    slug_a: str
    slug_b: str
    count: int


class RecentVisit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    page: str
    category: Optional[str] = None
    season_year: Optional[int] = None
    event_slug: Optional[str] = None
    rider_slug: Optional[str] = None
    device_type: str


class StatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_visits: int
    unique_visitors_today: int
    unique_visitors_7d: int
    unique_visitors_30d: int
    sessions_today: int
    avg_session_seconds: float
    devices: list[DeviceCount]
    per_category: list[CategoryVisitCount]
    per_race: list[RaceVisitCount]
    per_rider: list[RiderVisitCount]
    top_comparisons: list[ComparisonCount]
    recent: list[RecentVisit]
