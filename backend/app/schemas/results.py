"""Per-race, per-category results (the race-results page)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict

from .common import CategoryRef, EventRef, RiderRef, SeasonRef


class EventResultRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class EventResultsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: SeasonRef
    category: CategoryRef
    event: EventRef
    # Days the event has results for (e.g. [1] or [1, 2]). UI uses the
    # length to decide whether to render per-day columns.
    days: list[int]
    rows: list[EventResultRowOut]
