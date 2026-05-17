"""Shared reference schemas embedded across the API (F3 / eng-review N3).

Byte-faithful port of ``backend/app/schemas/common.py``. Every rider,
category, event, and season reference in the API uses one of these types so
payloads stay consistent and the frontend's typed client (generated via
``openapi-typescript``) stays stable across endpoints.

Parity contract (decision I4-arch=A)
------------------------------------
* Field NAMES, ORDER, TYPES, and DEFAULTS are identical to the Pydantic v2
  schemas in the frozen FastAPI app. Field declaration order == JSON key
  order (the pinned renderer never re-sorts keys — see ``api/renderers.py``).
* ``RiderRef.slug`` is computed server-side via ``core.slug.rider_slug``
  (byte-for-byte copy of ``backend/app/slug.py``) and MUST be consumed by the
  frontend verbatim — never recomputed client-side.
* These are Django Ninja ``Schema`` objects. ``ninja.Schema`` subclasses
  ``pydantic.BaseModel`` and ships ``model_config = {"from_attributes": True}``
  by default, so ``Schema.model_validate(<Django model instance>)`` reads
  attributes off the ORM object exactly like the old
  ``ConfigDict(from_attributes=True)`` did off the SQLAlchemy object. The
  field set is unchanged, so ``openapi-typescript`` regenerates with no diff.

Why ``from_orm`` is kept
------------------------
``backend/app/schemas/common.py`` exposes ``RiderRef.from_orm(rider)`` and the
module-level ``build_rider_ref(rider)``; ported tests and S1–S7 slices call
them. They are preserved here with identical behavior (compute the slug from
the rider's ``first_name``/``last_name``/``race_number``). NOTE: Pydantic v2
reserves ``from_orm`` as a deprecated alias of ``model_validate`` UNLESS the
subclass overrides it — we override it (as the FastAPI app already did), so
this is the canonical constructor, not the deprecated shim.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from ninja import Schema

from core.slug import rider_slug


class RiderRef(Schema):
    """Uniquely identifies a rider within a season.

    ``slug`` is computed on the backend (``core.slug.rider_slug``) and MUST
    be consumed by the frontend verbatim — never recomputed client-side.
    """

    race_number: int
    first_name: str
    last_name: str
    slug: str
    team: Optional[str] = None
    bike: Optional[str] = None

    @classmethod
    def from_orm(cls, rider) -> "RiderRef":
        """Build a ``RiderRef`` from a Django ``core.models.Rider`` instance.

        Identical field mapping + slug computation to
        ``backend/app/schemas/common.py::RiderRef.from_orm``. The slug uses
        ``core.slug.rider_slug`` (byte-identical to ``backend/app/slug.py``).
        """
        return cls(
            race_number=rider.race_number,
            first_name=rider.first_name,
            last_name=rider.last_name,
            slug=rider_slug(rider.first_name, rider.last_name, rider.race_number),
            team=rider.team,
            bike=rider.bike,
        )


class CategoryRef(Schema):
    code: str
    display_name: str
    sort_order: int


class EventRef(Schema):
    slug: str
    name: str
    event_date: Optional[date] = None
    location: Optional[str] = None
    sort_order: int
    event_type: Optional[str] = None
    # Editorial fields, populated via /admin. Null when not yet set.
    # Hidden from the UI (button hides, fallback copy used) when null.
    facebook_event_url: Optional[str] = None
    description: Optional[str] = None


class SeasonRef(Schema):
    year: int
    name: str
    slug: str
    is_current: bool
    championship_format: str


def build_rider_ref(rider) -> RiderRef:
    """Module-level factory convenience (same as ``RiderRef.from_orm``)."""
    return RiderRef.from_orm(rider)


__all__ = [
    "RiderRef",
    "CategoryRef",
    "EventRef",
    "SeasonRef",
    "build_rider_ref",
]
