"""Leaderboard (per-category, per-season) response schemas."""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class RiderEventEntryOut(BaseModel):
    """A rider's result in a single event within the leaderboard table."""
    model_config = ConfigDict(from_attributes=True)

    event_slug: str
    points: float
    position: int


class StandingsRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    final_position: int
    rider: RiderRef
    events: list[RiderEventEntryOut]
    total_points: float
    races_participated: int
    # null when the rider has no real finishes anywhere — the underlying
    # value would otherwise be `position_from_points(0) = 21`, which makes
    # the table show "21" for someone who only DNF'd. Frontend renders
    # null as "—".
    best_position: Optional[int] = None
    worst_event_slug: Optional[str] = None
    worst_dropped: Optional[float] = None


class StandingsOut(BaseModel):
    """Full leaderboard response for one category within one season."""
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    category: CategoryRef
    events: list[EventRef]
    rows: list[StandingsRowOut]
    championship_format: str
