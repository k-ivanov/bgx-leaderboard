"""Season endpoint schemas (F3 reference — S1 owns/extends this).

Byte-faithful port of ``backend/app/schemas/seasons.py``. F3 ships these so
the ONE worked reference endpoint (``api/seasons.py``) is complete and
copyable; S1 (blocked-by F3) extends/owns the seasons slice from here.
Field names + order + types are identical to the Pydantic schemas so the
frontend's ``openapi-typescript`` client regenerates with no diff.
"""

from __future__ import annotations

from ninja import Schema

from .common import CategoryRef, EventRef, SeasonRef


class SeasonListOut(Schema):
    seasons: list[SeasonRef]


class SeasonDetailOut(Schema):
    """Season metadata plus its categories and events."""

    season: SeasonRef
    categories: list[CategoryRef]
    events: list[EventRef]
    rider_count: int


__all__ = ["SeasonListOut", "SeasonDetailOut"]
