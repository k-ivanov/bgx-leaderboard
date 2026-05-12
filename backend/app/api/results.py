"""GET /api/seasons/{year}/categories/{category_code}/events/{event_slug}."""

from typing import Optional

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
from src.services.scoring import compute_event_scoring

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
            .order_by(EventResult.day, EventResult.id)
        ).scalars()
    )

    grouped: dict[int, list[EventResult]] = {}
    for r in results:
        grouped.setdefault(r.rider_id, []).append(r)

    def _sum_or_none(rows: list[EventResult], field: str) -> Optional[int]:
        vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
        return sum(vals) if vals else None

    # Combined-time scoring: eligible riders rank by sum(time_ms) across
    # every day of the event, points come from the canonical BGX table.
    # Ineligible riders (DNF any day, missing day) show with points=None,
    # no position, after the ranked block.
    scoring = compute_event_scoring(results)

    eligible_rows: list[tuple[int, EventResultRowOut]] = []
    ineligible_rows: list[EventResultRowOut] = []
    for rider_id, rider_rows in grouped.items():
        rider = rider_rows[0].rider
        score = scoring.get(rider_id)
        notes = next((r.notes for r in rider_rows if r.notes), None)
        cp_count = next((r.cp_count for r in rider_rows if r.cp_count is not None), None)
        time_ms = _sum_or_none(rider_rows, "time_ms")

        is_eligible = score is not None and score.combined_position is not None
        row = EventResultRowOut(
            position=None,
            rider=build_rider_ref(rider),
            points=score.points if is_eligible else None,
            time_ms=score.combined_time_ms if is_eligible else time_ms,
            gap_ms=_sum_or_none(rider_rows, "gap_ms"),
            gps_penalty_ms=_sum_or_none(rider_rows, "gps_penalty_ms"),
            laps=_sum_or_none(rider_rows, "laps"),
            cp_count=cp_count,
            notes=notes,
        )
        if is_eligible:
            eligible_rows.append((score.combined_position, row))
        else:
            ineligible_rows.append(row)

    eligible_rows.sort(key=lambda x: (x[0], x[1].rider.race_number))
    ineligible_rows.sort(key=lambda r: r.rider.race_number)

    rows: list[EventResultRowOut] = []
    for pos, row in eligible_rows:
        row.position = pos
        rows.append(row)
    rows.extend(ineligible_rows)

    return EventResultsOut(
        season=SeasonRef.model_validate(season),
        category=CategoryRef.model_validate(category),
        event=EventRef.model_validate(event),
        rows=rows,
    )
