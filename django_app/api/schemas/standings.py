"""Leaderboard (per-category, per-season) response schemas.

S2 byte-faithful port of ``backend/app/schemas/standings.py``. Field NAMES +
ORDER + TYPES + DEFAULTS are identical to the frozen FastAPI Pydantic schemas
so the pinned renderer (``api/renderers.py``, never re-sorts keys) emits JSON
with byte-identical key order and the frontend's ``openapi-typescript`` client
regenerates with NO diff for the standings path.

``ninja.Schema`` subclasses ``pydantic.BaseModel`` and ships
``model_config = {"from_attributes": True}`` by default, so it is the exact
analogue of the FastAPI ``ConfigDict(from_attributes=True)`` — ``points:
float`` / ``total_points: float`` still coerce the ORM ``Decimal`` to a
Python ``float`` during response validation (the Decimal→number guard rail
documented in ``api/renderers.py``).
"""

from __future__ import annotations

from typing import Optional

from ninja import Schema

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class RiderEventEntryOut(Schema):
    """A rider's result in a single event within the leaderboard table."""

    event_slug: str
    points: float
    position: int


class StandingsRowOut(Schema):
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


class StandingsOut(Schema):
    """Full leaderboard response for one category within one season."""

    season: SeasonRef
    category: CategoryRef
    events: list[EventRef]
    rows: list[StandingsRowOut]
    championship_format: str


__all__ = ["RiderEventEntryOut", "StandingsRowOut", "StandingsOut"]
