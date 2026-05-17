"""S5 — Private analytics (stats) endpoint schemas (auth-gated).

Byte-faithful port of ``backend/app/schemas/stats.py``. Every class is a
Django Ninja ``Schema`` (``ninja.Schema`` subclasses ``pydantic.BaseModel``
and ships ``model_config = {"from_attributes": True}`` by default, so
``Schema.model_validate(<Django Visit instance>)`` reads attributes off the
ORM object exactly like the old ``ConfigDict(from_attributes=True)`` did off
the SQLAlchemy object).

Parity contract (mirrors ``api/schemas/common.py``)
---------------------------------------------------
* Field NAMES, ORDER, TYPES, and DEFAULTS are identical to the Pydantic v2
  schemas in the frozen FastAPI app (``backend/app/schemas/stats.py``). Field
  declaration order == JSON key order — the pinned renderer
  (``api/renderers.py``) never re-sorts keys, so the frontend's typed client
  (generated via ``openapi-typescript``) regenerates with no diff and the
  parity rig byte-matches the oracle.
* ``RecentVisit`` is validated from a Django ``core.models.Visit`` instance
  via ``model_validate``; only the surfaced subset of columns is read
  (``timestamp``/``page``/``category``/``season_year``/``event_slug``/
  ``rider_slug``/``device_type``) exactly as the FastAPI schema did.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ninja import Schema


class DeviceCount(Schema):
    device_type: str
    count: int


class CategoryVisitCount(Schema):
    category: Optional[str] = None
    season_year: Optional[int] = None
    count: int


class RaceVisitCount(Schema):
    season_year: Optional[int] = None
    event_slug: str
    count: int


class RiderVisitCount(Schema):
    season_year: Optional[int] = None
    rider_slug: str
    count: int


class ComparisonCount(Schema):
    """One row in the top-comparisons aggregation. Slugs are normalized
    alphabetically by the track endpoint (S6) so (A,B) and (B,A) bucket as
    one pair."""

    slug_a: str
    slug_b: str
    count: int


class RecentVisit(Schema):
    timestamp: datetime
    page: str
    category: Optional[str] = None
    season_year: Optional[int] = None
    event_slug: Optional[str] = None
    rider_slug: Optional[str] = None
    device_type: str


class StatsOut(Schema):
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


__all__ = [
    "DeviceCount",
    "CategoryVisitCount",
    "RaceVisitCount",
    "RiderVisitCount",
    "ComparisonCount",
    "RecentVisit",
    "StatsOut",
]
