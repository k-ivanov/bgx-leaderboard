"""Visit-tracking request schema for POST /api/track (eng-review N7)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class TrackIn(BaseModel):
    """One visit event from the frontend router's afterEach hook.

    Payload size is capped by middleware; per-IP rate limit is applied by slowapi.
    """
    model_config = ConfigDict(extra="forbid")

    page: str = Field(..., min_length=1, max_length=64)
    category: Optional[str] = Field(default=None, max_length=64)
    season_year: Optional[int] = Field(default=None, ge=1900, le=2999)
    event_slug: Optional[str] = Field(default=None, max_length=64)
    rider_slug: Optional[str] = Field(default=None, max_length=128)


class TrackOut(BaseModel):
    ok: bool
