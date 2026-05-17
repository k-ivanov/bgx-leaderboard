"""Rider endpoint schemas (profile + disambiguation + search + career).

S4 byte-faithful port of ``backend/app/schemas/riders.py``. Field NAMES +
ORDER + TYPES + DEFAULTS are identical to the frozen FastAPI Pydantic schemas
so the pinned renderer (``api/renderers.py``, never re-sorts keys) emits JSON
with byte-identical key order and the frontend's ``openapi-typescript`` client
regenerates with NO diff for the rider paths:

  GET /api/seasons/{year}/riders/search          → RiderSearchOut
  GET /api/seasons/{year}/riders/{race_number}    → RiderDisambigOut
  GET /api/seasons/{year}/riders/{n}/{slug}       → RiderProfileOut
  GET /api/riders/career                          → RiderCareerOut
  GET /api/riders/search                          → GlobalRiderSearchOut

``ninja.Schema`` subclasses ``pydantic.BaseModel`` and ships
``model_config = {"from_attributes": True}`` by default, so it is the exact
analogue of the FastAPI ``ConfigDict(from_attributes=True)`` — every
``Schema.model_validate(<Django model instance>)`` reads attributes off the
ORM object exactly like the old SQLAlchemy ``model_validate`` did.

The nested ``RiderRef`` / ``CategoryRef`` / ``EventRef`` / ``SeasonRef`` ride
entirely on the F3 ``api/schemas/common.py`` — reusing the shared refs is what
keeps the typed client stable across every rider-bearing endpoint. ``slug`` on
every ``RiderRef`` is computed server-side via ``core.slug.rider_slug`` (F3
byte-identical copy of ``backend/app/slug.py``) and is consumed verbatim.
"""

from __future__ import annotations

from typing import Optional

from ninja import Schema

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class RiderResultOut(Schema):
    """A single (event, category) result within a rider's season profile."""

    event: EventRef
    category: CategoryRef
    position: Optional[int] = None
    points: Optional[float] = None
    time_ms: Optional[int] = None
    gap_ms: Optional[int] = None
    gps_penalty_ms: Optional[int] = None
    laps: Optional[int] = None


class RiderProfileOut(Schema):
    """Singular rider page: header meta + every result this season."""

    season: SeasonRef
    rider: RiderRef
    categories: list[CategoryRef]
    results: list[RiderResultOut]
    total_events: int


class RiderDisambigEntryOut(Schema):
    """One candidate in the disambiguation list (two riders sharing a race number)."""

    rider: RiderRef
    categories: list[CategoryRef]


class RiderDisambigOut(Schema):
    """Response when multiple (first, last) pairs share a race number in a season."""

    season: SeasonRef
    race_number: int
    candidates: list[RiderDisambigEntryOut]


class RiderSearchResultOut(Schema):
    """One row in the rider search response.

    ``category`` is the first category the rider competes in (riders may
    appear in multiple categories per season; UI links to the first).
    """

    rider: RiderRef
    category: CategoryRef
    season_year: int


class RiderSearchOut(Schema):
    """Response for /api/seasons/{year}/riders/search."""

    season: SeasonRef
    query: str
    results: list[RiderSearchResultOut]


class GlobalRiderSearchOut(Schema):
    """Response for /api/riders/search (cross-season).

    Each row carries its own season_year, so the caller can render a
    year tag. Results are deduped by rider slug — a rider who raced in
    multiple seasons appears once, with the most recent (year, category).
    """

    query: str
    results: list[RiderSearchResultOut]


class RiderCareerSeasonOut(Schema):
    """One row in a rider's multi-season history (P3 #17).

    ``results`` carries every per-event row (already collapsed across days)
    so the rider profile page can render with a single API call.
    """

    season_year: int
    race_number: int
    category: CategoryRef
    team: Optional[str] = None
    bike: Optional[str] = None
    # The rider's general-classification rank in this (season, category) at
    # the time of the API call. Computed from the same `get_standings`
    # function that powers /api/seasons/{year}/standings/{cat}, so the
    # value matches what's shown on the leaderboard. Null when the rider
    # is a registered Rider row but has zero EventResult rows (skipped by
    # the standings algorithm at line 141 of standings.py).
    final_position: Optional[int] = None
    races_participated: int
    total_points: float
    best_position: Optional[int] = None
    results: list[RiderResultOut] = []


class RiderCareerOut(Schema):
    """Response for /api/riders/career.

    Groups every Rider row (across all seasons) whose name matches the
    queried slug, returning one summary row per (season_year, category).
    """

    slug: str
    first_name: str
    last_name: str
    seasons: list[RiderCareerSeasonOut]


__all__ = [
    "RiderResultOut",
    "RiderProfileOut",
    "RiderDisambigEntryOut",
    "RiderDisambigOut",
    "RiderSearchResultOut",
    "RiderSearchOut",
    "GlobalRiderSearchOut",
    "RiderCareerSeasonOut",
    "RiderCareerOut",
]
