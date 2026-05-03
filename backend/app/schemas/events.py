"""Events / races endpoint schemas."""

from pydantic import BaseModel, ConfigDict

from .common import CategoryRef, EventRef, SeasonRef


class EventListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    events: list[EventRef]


class EventDetailOut(BaseModel):
    """Single race plus the categories that compete in it."""
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    event: EventRef
    categories: list[CategoryRef]
