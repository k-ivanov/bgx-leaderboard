"""GET /api/seasons, GET /api/seasons/{year}."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import get_season, get_session
from app.schemas.common import CategoryRef, EventRef, SeasonRef
from app.schemas.seasons import SeasonDetailOut, SeasonListOut
from src.db.models import Category, Event, Rider, Season

router = APIRouter(prefix="/api/seasons", tags=["seasons"])


@router.get("", response_model=SeasonListOut)
def list_seasons(session: Session = Depends(get_session)) -> SeasonListOut:
    seasons = list(
        session.execute(select(Season).order_by(Season.year.desc())).scalars()
    )
    return SeasonListOut(seasons=[SeasonRef.model_validate(s) for s in seasons])


@router.get("/{year}", response_model=SeasonDetailOut)
def get_season_detail(
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> SeasonDetailOut:
    categories = list(
        session.execute(
            select(Category)
            .where(Category.season_id == season.id)
            .order_by(Category.sort_order, Category.id)
        ).scalars()
    )
    events = list(
        session.execute(
            select(Event)
            .where(Event.season_id == season.id)
            .order_by(Event.sort_order, Event.id)
        ).scalars()
    )
    rider_count = session.execute(
        select(func.count(Rider.id)).where(Rider.season_id == season.id)
    ).scalar_one()
    return SeasonDetailOut(
        season=SeasonRef.model_validate(season),
        categories=[CategoryRef.model_validate(c) for c in categories],
        events=[EventRef.model_validate(e) for e in events],
        rider_count=rider_count,
    )
