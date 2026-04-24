"""GET /api/stats — private analytics (HTTP Basic, eng-review SC-1 / N6)."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import require_stats_auth
from app.deps import get_session
from app.schemas.stats import (
    CategoryVisitCount,
    DeviceCount,
    RecentVisit,
    StatsOut,
)
from src.db.models import Visit

router = APIRouter(prefix="/api", tags=["stats"])


@router.get(
    "/stats",
    response_model=StatsOut,
    dependencies=[Depends(require_stats_auth)],
)
def get_stats(session: Session = Depends(get_session)) -> StatsOut:
    total = session.execute(select(func.count(Visit.id))).scalar_one() or 0

    device_rows = session.execute(
        select(Visit.device_type, func.count(Visit.id)).group_by(Visit.device_type)
    ).all()
    devices = [DeviceCount(device_type=dt, count=c) for (dt, c) in device_rows]

    per_cat_rows = session.execute(
        select(Visit.category, Visit.season_year, func.count(Visit.id))
        .where(Visit.page == "leaderboard")
        .where(Visit.category.is_not(None))
        .group_by(Visit.category, Visit.season_year)
        .order_by(func.count(Visit.id).desc())
    ).all()
    per_category = [
        CategoryVisitCount(category=cat, season_year=yr, count=cnt)
        for (cat, yr, cnt) in per_cat_rows
    ]

    recent_rows = list(
        session.execute(
            select(Visit).order_by(Visit.timestamp.desc()).limit(25)
        ).scalars()
    )
    recent = [RecentVisit.model_validate(v) for v in recent_rows]

    return StatsOut(
        total_visits=total,
        devices=devices,
        per_category=per_category,
        recent=recent,
    )
