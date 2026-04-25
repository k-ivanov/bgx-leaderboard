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
