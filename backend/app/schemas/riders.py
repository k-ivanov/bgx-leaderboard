"""Rider endpoint schemas (profile + disambiguation)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class RiderResultOut(BaseModel):
    """A single (event, category) result within a rider's season profile."""
    model_config = ConfigDict(from_attributes=True)

    event: EventRef
    category: CategoryRef
    position: Optional[int] = None
    points: Optional[float] = None
    time_ms: Optional[int] = None
    gap_ms: Optional[int] = None
    gps_penalty_ms: Optional[int] = None
    laps: Optional[int] = None


class RiderProfileOut(BaseModel):
    """Singular rider page: header meta + every result this season."""
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    rider: RiderRef
    categories: list[CategoryRef]
    results: list[RiderResultOut]
    total_events: int


class RiderDisambigEntryOut(BaseModel):
    """One candidate in the disambiguation list (two riders sharing a race number)."""
    model_config = ConfigDict(from_attributes=True)

    rider: RiderRef
    categories: list[CategoryRef]


class RiderDisambigOut(BaseModel):
    """Response when multiple (first, last) pairs share a race number in a season."""
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    race_number: int
    candidates: list[RiderDisambigEntryOut]


class RiderSearchResultOut(BaseModel):
    """One row in the rider search response.

    `category` is the first category the rider competes in (riders may
    appear in multiple categories per season; UI links to the first).
    """
    model_config = ConfigDict(from_attributes=True)

    rider: RiderRef
    category: CategoryRef
    season_year: int


class RiderSearchOut(BaseModel):
    """Response for /api/seasons/{year}/riders/search."""
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    query: str
    results: list[RiderSearchResultOut]


class RiderCareerSeasonOut(BaseModel):
    """One row in a rider's multi-season history (P3 #17).

    `results` carries every per-event row (already collapsed across days)
    so the rider profile page can render with a single API call.
    """
    model_config = ConfigDict(from_attributes=True)

    season_year: int
    race_number: int
    category: CategoryRef
    team: Optional[str] = None
    bike: Optional[str] = None
    races_participated: int
    total_points: float
    best_position: Optional[int] = None
    results: list[RiderResultOut] = []


class RiderCareerOut(BaseModel):
    """Response for /api/riders/career.

    Groups every Rider row (across all seasons) whose name matches the
    queried slug, returning one summary row per (season_year, category).
    """
    model_config = ConfigDict(from_attributes=True)

    slug: str
    first_name: str
    last_name: str
    seasons: list[RiderCareerSeasonOut]
