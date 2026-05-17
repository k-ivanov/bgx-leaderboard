"""S6 — Visit-tracking request/response schemas for POST /api/track.

Byte-faithful port of ``backend/app/schemas/track.py``. Every class is a
Django Ninja ``Schema`` (``ninja.Schema`` subclasses ``pydantic.BaseModel``),
so the validation contract — required/optional fields, bounds, and the
``extra="forbid"`` rejection of unknown fields — is identical to the frozen
FastAPI Pydantic v2 schema. Field NAMES, ORDER, TYPES, and DEFAULTS match the
oracle exactly (the pinned renderer never re-sorts keys, so the frontend's
``openapi-typescript`` client regenerates with no diff and the response body
is byte-identical to the FastAPI ``{"ok":true}``).
"""

from __future__ import annotations

from typing import Optional

from ninja import Schema
from pydantic import ConfigDict, Field


class TrackIn(Schema):
    """One visit event from the frontend router's afterEach hook.

    Payload size is capped by the S6 pre-parse middleware
    (``core.track_guards.TrackPayloadSizeLimitMiddleware``); per-IP rate limit
    is applied by the S6 Ninja throttle (``core.track_guards.TrackRateThrottle``).

    ``extra="forbid"`` (oracle ``ConfigDict(extra="forbid")``) rejects unknown
    fields with a 422 — identical to the FastAPI behavior.
    """

    model_config = ConfigDict(extra="forbid")

    page: str = Field(..., min_length=1, max_length=64)
    category: Optional[str] = Field(default=None, max_length=64)
    season_year: Optional[int] = Field(default=None, ge=1900, le=2999)
    event_slug: Optional[str] = Field(default=None, max_length=64)
    rider_slug: Optional[str] = Field(default=None, max_length=128)
    # When page='compare' the second rider's slug. Server normalizes the
    # pair alphabetically before persisting so (A,B) and (B,A) collapse.
    compared_with_slug: Optional[str] = Field(default=None, max_length=128)


class TrackOut(Schema):
    ok: bool
