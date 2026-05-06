"""Shared reference schemas embedded across the API (eng-review N3).

Every rider, category, event, and season reference in the API uses one of
these types. Keeps payloads consistent and makes the frontend's typed
client (generated via openapi-typescript) stable across endpoints.
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.slug import rider_slug
from src.db.models import Category, Event, Rider, Season


class RiderRef(BaseModel):
    """Uniquely identifies a rider within a season.

    ``slug`` is computed on the backend (``app.slug.rider_slug``) and MUST
    be consumed by the frontend verbatim — never recomputed client-side.
    """
    model_config = ConfigDict(from_attributes=True)

    race_number: int
    first_name: str
    last_name: str
    slug: str
    team: Optional[str] = None
    bike: Optional[str] = None

    @classmethod
    def from_orm(cls, rider: Rider) -> "RiderRef":
        return cls(
            race_number=rider.race_number,
            first_name=rider.first_name,
            last_name=rider.last_name,
            slug=rider_slug(rider.first_name, rider.last_name, rider.race_number),
            team=rider.team,
            bike=rider.bike,
        )


class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    display_name: str
    sort_order: int


class EventRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class SeasonRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int
    name: str
    slug: str
    is_current: bool
    championship_format: str


def build_rider_ref(rider: Rider) -> RiderRef:
    """Module-level factory convenience (same as ``RiderRef.from_orm``)."""
    return RiderRef.from_orm(rider)
