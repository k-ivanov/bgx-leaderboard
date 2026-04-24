"""GET /api/seasons/{year}/events, GET /api/seasons/{year}/events/{slug}."""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import get_season, get_session
from app.schemas.common import CategoryRef, EventRef, SeasonRef
from app.schemas.events import EventDetailOut, EventListOut
from src.db.models import Category, Event, Season
from src.services.standings import events_for_season

router = APIRouter(prefix="/api/seasons", tags=["races"])


@router.get("/{year}/events", response_model=EventListOut)
def list_races(
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> EventListOut:
    events = events_for_season(session, season)
    return EventListOut(
        season=SeasonRef.model_validate(season),
        events=[EventRef.model_validate(e) for e in events],
    )


@router.get("/{year}/events/{event_slug}", response_model=EventDetailOut)
def get_race_detail(
    event_slug: str = Path(...),
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> EventDetailOut:
    event = session.execute(
        select(Event).where(Event.season_id == season.id, Event.slug == event_slug)
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race '{event_slug}' not found in season {season.year}",
        )

    categories = list(
        session.execute(
            select(Category)
            .where(Category.season_id == season.id)
            .order_by(Category.sort_order, Category.id)
        ).scalars()
    )

    return EventDetailOut(
        season=SeasonRef.model_validate(season),
        event=EventRef.model_validate(event),
        categories=[CategoryRef.model_validate(c) for c in categories],
    )
