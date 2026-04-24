"""Private analytics endpoint schemas (auth-gated)."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class DeviceCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device_type: str
    count: int


class CategoryVisitCount(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: Optional[str] = None
    season_year: Optional[int] = None
    count: int


class RecentVisit(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    timestamp: datetime
    page: str
    category: Optional[str] = None
    season_year: Optional[int] = None
    device_type: str


class StatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    total_visits: int
    devices: list[DeviceCount]
    per_category: list[CategoryVisitCount]
    recent: list[RecentVisit]
