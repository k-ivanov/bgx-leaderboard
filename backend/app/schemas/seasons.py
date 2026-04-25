"""Season endpoint schemas."""

from pydantic import BaseModel, ConfigDict

from .common import CategoryRef, EventRef, SeasonRef


class SeasonListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seasons: list[SeasonRef]


class SeasonDetailOut(BaseModel):
    """Season metadata plus its categories and events."""
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    categories: list[CategoryRef]
    events: list[EventRef]
    rider_count: int
