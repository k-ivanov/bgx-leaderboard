"""GET /api/seasons/{year}/categories/{category_code}/events/{event_slug}."""

from fastapi import APIRouter, Depends, HTTPException, Path, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_category, get_session
from app.schemas.common import (
    CategoryRef,
    EventRef,
    SeasonRef,
    build_rider_ref,
)
from app.schemas.results import EventResultRowOut, EventResultsOut
from src.db.models import Category, Event, EventResult, Rider

router = APIRouter(prefix="/api/seasons", tags=["race-results"])


@router.get(
    "/{year}/categories/{category_code}/events/{event_slug}",
    response_model=EventResultsOut,
)
def get_race_results(
    event_slug: str = Path(...),
    category: Category = Depends(get_category),
    session: Session = Depends(get_session),
) -> EventResultsOut:
    season = category.season

    event = session.execute(
        select(Event).where(Event.season_id == season.id, Event.slug == event_slug)
    ).scalar_one_or_none()
    if event is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Race '{event_slug}' not found in season {season.year}",
        )

    # Join results → riders filtered to this category, eager load rider for RiderRef.
    results = list(
        session.execute(
            select(EventResult)
            .join(Rider, EventResult.rider_id == Rider.id)
            .where(
                EventResult.event_id == event.id,
                Rider.category_id == category.id,
            )
            .options(selectinload(EventResult.rider))
            .order_by(
                EventResult.position.nulls_last(),
                EventResult.time_ms.nulls_last(),
                EventResult.id,
            )
        ).scalars()
    )

    rows = [
        EventResultRowOut(
            position=r.position,
            rider=build_rider_ref(r.rider),
            points=float(r.points) if r.points is not None else None,
            time_ms=r.time_ms,
            gap_ms=r.gap_ms,
            gps_penalty_ms=r.gps_penalty_ms,
            laps=r.laps,
            cp_count=r.cp_count,
            notes=r.notes,
        )
        for r in results
    ]

    return EventResultsOut(
        season=SeasonRef.model_validate(season),
        category=CategoryRef.model_validate(category),
        event=EventRef.model_validate(event),
        rows=rows,
    )
