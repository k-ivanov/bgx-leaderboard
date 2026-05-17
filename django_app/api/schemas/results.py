"""Per-race, per-category Results endpoint schemas.

S7 byte-faithful port of ``backend/app/schemas/results.py`` (the schemas the
frontend's PRIMARY ``/results`` SPA island consumes — ``ResultsView.vue:93``).
Field NAMES + ORDER + TYPES + DEFAULTS are identical to the frozen FastAPI
Pydantic schemas so the pinned renderer (``api/renderers.py``, never re-sorts
keys) emits JSON with byte-identical key order and the frontend's
``openapi-typescript`` client regenerates with NO diff for the
``/api/seasons/{year}/categories/{category_code}/events/{event_slug}`` path
(the OpenAPI Race Results path S3 explicitly left out as S7 scope).

``ninja.Schema`` subclasses ``pydantic.BaseModel`` and ships
``model_config = {"from_attributes": True}`` by default, so it is the exact
analogue of the FastAPI ``ConfigDict(from_attributes=True)`` — every
``Schema.model_validate(<Django model instance>)`` reads attributes off the
ORM object exactly like the old SQLAlchemy ``model_validate`` did. S7's
handler still constructs the row objects field-by-field (parity with
``backend/app/api/results.py``), not via ``model_validate``, but the nested
``season``/``category``/``event`` refs are built with the F3 shared
``SeasonRef``/``CategoryRef``/``EventRef`` (``api/schemas/common.py``) exactly
as the FastAPI router did — reusing the shared refs is what keeps the typed
client stable across every season/category/event-bearing endpoint.

Vocabulary note: UI copy says "Race"; the DB table + the ORM model + these
schema field names stay ``event``/``EventRef`` (the API contract is frozen —
renaming would diff the typed client). Only the OpenAPI ``tags`` say
``race-results`` (set in the FROZEN ``api/__init__.py`` — not here).
"""

from __future__ import annotations

from typing import Optional

from ninja import Schema

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class EventResultRowOut(Schema):
    """One rider's row on the race-results table.

    Byte-faithful port of ``backend/app/schemas/results.py::EventResultRowOut``
    (including the field comments) — same field NAMES + ORDER + TYPES +
    DEFAULTS. ``points`` is ``Optional[float]`` (parity with the FastAPI
    schema; the ORM ``points`` is a Postgres ``numeric(6,2)`` surfaced through
    the S2 ``compute_event_scoring`` ``EventScore.points: float``).
    """

    position: Optional[int] = None
    rider: RiderRef
    points: Optional[float] = None
    # Headline time: combined for full finishers, day-1 or day-2 time
    # for partial finishers, None for riders who didn't finish anywhere.
    time_ms: Optional[int] = None
    # Per-day breakdown for multi-day events. Null when the rider didn't
    # finish that day (DNF/DNS/missing); for single-day events day_2_*
    # is always null.
    day_1_time_ms: Optional[int] = None
    day_2_time_ms: Optional[int] = None
    day_1_status: Optional[str] = None
    day_2_status: Optional[str] = None
    gap_ms: Optional[int] = None
    gps_penalty_ms: Optional[int] = None
    laps: Optional[int] = None
    cp_count: Optional[int] = None
    notes: Optional[str] = None


class EventResultsOut(Schema):
    """The full race-results payload for one (season, category, race).

    Byte-faithful port of ``backend/app/schemas/results.py::EventResultsOut``
    (including the ``days`` comment) — same field NAMES + ORDER + TYPES. The
    nested refs ride entirely on the F3 shared schemas
    (``SeasonRef``/``CategoryRef``/``EventRef``) so the typed client stays
    stable across every endpoint that embeds them.
    """

    season: SeasonRef
    category: CategoryRef
    event: EventRef
    # Days the event has results for (e.g. [1] or [1, 2]). UI uses the
    # length to decide whether to render per-day columns.
    days: list[int]
    rows: list[EventResultRowOut]


__all__ = ["EventResultRowOut", "EventResultsOut"]
