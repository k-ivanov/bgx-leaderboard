"""GET /api/stats — private analytics (HTTP Basic, eng-review SC-1 / N6)."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import Float, cast, func, select
from sqlalchemy.orm import Session

from app.auth import require_stats_auth
from app.deps import get_session
from app.schemas.stats import (
    CategoryVisitCount,
    ComparisonCount,
    DeviceCount,
    RaceVisitCount,
    RecentVisit,
    RiderVisitCount,
    StatsOut,
)
from src.db.models import Visit

router = APIRouter(
    prefix="/api",
    tags=["stats"],
    # Router-level gate: every endpoint mounted on this router inherits
    # require_stats_auth, so a new /api/stats/* endpoint can't accidentally
    # ship publicly. The page (frontend StatsView island) sends Basic auth
    # via Authorization header.
    dependencies=[Depends(require_stats_auth)],
)


_SESSION_DURATION_WINDOW_DAYS = 30
_TOP_N = 50


@router.get("/stats", response_model=StatsOut)
def get_stats(session: Session = Depends(get_session)) -> StatsOut:
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    week_cutoff = now - timedelta(days=7)
    month_cutoff = now - timedelta(days=30)
    duration_cutoff = now - timedelta(days=_SESSION_DURATION_WINDOW_DAYS)

    total = session.execute(select(func.count(Visit.id))).scalar_one() or 0

    unique_today = session.execute(
        select(func.count(func.distinct(Visit.visitor_id)))
        .where(Visit.timestamp >= today_start)
        .where(Visit.visitor_id != "")
    ).scalar_one() or 0

    unique_7d = session.execute(
        select(func.count(func.distinct(Visit.visitor_id)))
        .where(Visit.timestamp >= week_cutoff)
        .where(Visit.visitor_id != "")
    ).scalar_one() or 0

    unique_30d = session.execute(
        select(func.count(func.distinct(Visit.visitor_id)))
        .where(Visit.timestamp >= month_cutoff)
        .where(Visit.visitor_id != "")
    ).scalar_one() or 0

    sessions_today = session.execute(
        select(func.count(func.distinct(Visit.session_id)))
        .where(Visit.timestamp >= today_start)
        .where(Visit.session_id != "")
    ).scalar_one() or 0

    # Per-session duration (last 30 days): max(ts) - min(ts) grouped by
    # session_id, then average across sessions. A single-hit session
    # contributes 0s; that's the honest reading — we didn't observe them
    # stay longer than one event.
    per_session_duration = (
        select(
            (
                func.extract("epoch", func.max(Visit.timestamp))
                - func.extract("epoch", func.min(Visit.timestamp))
            ).label("seconds")
        )
        .where(Visit.timestamp >= duration_cutoff)
        .where(Visit.session_id != "")
        .group_by(Visit.session_id)
        .subquery()
    )
    avg_session_seconds = session.execute(
        select(func.coalesce(func.avg(cast(per_session_duration.c.seconds, Float)), 0.0))
    ).scalar_one() or 0.0

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

    per_race_rows = session.execute(
        select(Visit.season_year, Visit.event_slug, func.count(Visit.id))
        .where(Visit.page == "race")
        .where(Visit.event_slug.is_not(None))
        .group_by(Visit.season_year, Visit.event_slug)
        .order_by(func.count(Visit.id).desc())
        .limit(_TOP_N)
    ).all()
    per_race = [
        RaceVisitCount(season_year=yr, event_slug=slug, count=cnt)
        for (yr, slug, cnt) in per_race_rows
    ]

    per_rider_rows = session.execute(
        select(Visit.season_year, Visit.rider_slug, func.count(Visit.id))
        .where(Visit.page == "rider")
        .where(Visit.rider_slug.is_not(None))
        .group_by(Visit.season_year, Visit.rider_slug)
        .order_by(func.count(Visit.id).desc())
        .limit(_TOP_N)
    ).all()
    per_rider = [
        RiderVisitCount(season_year=yr, rider_slug=slug, count=cnt)
        for (yr, slug, cnt) in per_rider_rows
    ]

    # Top compared rider pairs. The track endpoint normalizes (A,B) and
    # (B,A) into one ordered tuple before insert, so a plain group-by
    # collapses into one row per real pair.
    top_comparisons_rows = session.execute(
        select(Visit.rider_slug, Visit.compared_with_slug, func.count(Visit.id))
        .where(Visit.page == "compare")
        .where(Visit.rider_slug.is_not(None))
        .where(Visit.compared_with_slug.is_not(None))
        .group_by(Visit.rider_slug, Visit.compared_with_slug)
        .order_by(func.count(Visit.id).desc())
        .limit(_TOP_N)
    ).all()
    top_comparisons = [
        ComparisonCount(slug_a=a, slug_b=b, count=cnt)
        for (a, b, cnt) in top_comparisons_rows
    ]

    recent_rows = list(
        session.execute(
            select(Visit).order_by(Visit.timestamp.desc()).limit(25)
        ).scalars()
    )
    recent = [RecentVisit.model_validate(v) for v in recent_rows]

    return StatsOut(
        total_visits=total,
        unique_visitors_today=unique_today,
        unique_visitors_7d=unique_7d,
        unique_visitors_30d=unique_30d,
        sessions_today=sessions_today,
        avg_session_seconds=float(avg_session_seconds),
        devices=devices,
        per_category=per_category,
        per_race=per_race,
        per_rider=per_rider,
        top_comparisons=top_comparisons,
        recent=recent,
    )
