"""Events / Races endpoint schemas.

S3 byte-faithful port of ``backend/app/schemas/events.py``. Field NAMES +
ORDER + TYPES + DEFAULTS are identical to the frozen FastAPI Pydantic schemas
so the pinned renderer (``api/renderers.py``, never re-sorts keys) emits JSON
with byte-identical key order and the frontend's ``openapi-typescript`` client
regenerates with NO diff for the ``/api/seasons/{year}/events`` +
``/api/seasons/{year}/events/{slug}`` paths.

``ninja.Schema`` subclasses ``pydantic.BaseModel`` and ships
``model_config = {"from_attributes": True}`` by default, so it is the exact
analogue of the FastAPI ``ConfigDict(from_attributes=True)`` — every
``Schema.model_validate(<Django model instance>)`` reads attributes off the
ORM object exactly like the old SQLAlchemy ``model_validate`` did.

Editorial fields (``facebook_event_url``, ``description``) ride entirely on
the F3 ``EventRef`` (``api/schemas/common.py``): both are
``Optional[str] = None`` there, so they surface identically and **null-safe**
(absent → ``null``) just as the FastAPI app did. S3 does not redeclare them —
reusing the shared ref is what keeps the ``openapi-typescript`` client stable
across every event-bearing endpoint (S1 detail, S2 leaderboard, S3 races).

Vocabulary note: UI copy says "Race/Races"; the DB table + the ORM model +
these schema field names stay ``event``/``EventRef`` (the API contract is
frozen — renaming would diff the typed client). Only the OpenAPI ``tags`` say
``races`` (set in the FROZEN ``api/__init__.py`` — not here).
"""

from __future__ import annotations

from ninja import Schema

from .common import CategoryRef, EventRef, SeasonRef


class EventListOut(Schema):
    """The races in a season — ``GET /api/seasons/{year}/events``."""

    season: SeasonRef
    events: list[EventRef]


class EventDetailOut(Schema):
    """Single race plus the categories that compete in it.

    ``GET /api/seasons/{year}/events/{event_slug}``. Byte-faithful port of
    ``backend/app/schemas/events.py::EventDetailOut`` (including the
    docstring) — same field NAMES + ORDER + TYPES.
    """

    season: SeasonRef
    event: EventRef
    categories: list[CategoryRef]


__all__ = ["EventListOut", "EventDetailOut"]
