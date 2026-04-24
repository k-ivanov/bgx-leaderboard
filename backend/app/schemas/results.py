"""Per-race, per-category results (the race-results page)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class EventResultRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    position: Optional[int] = None
    rider: RiderRef
    points: Optional[float] = None
    time_ms: Optional[int] = None
    gap_ms: Optional[int] = None
    gps_penalty_ms: Optional[int] = None
    laps: Optional[int] = None
    cp_count: Optional[int] = None
    notes: Optional[str] = None


class EventResultsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    category: CategoryRef
    event: EventRef
    rows: list[EventResultRowOut]
