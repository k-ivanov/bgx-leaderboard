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

    # Collapse per-day rows into one entry per rider — multi-day weekends
    # count as ONE race (matches leaderboard + rider profile aggregation).
    grouped: dict[int, list[EventResult]] = {}
    for r in results:
        grouped.setdefault(r.rider_id, []).append(r)

    def _sum_or_none(rows: list[EventResult], field: str) -> Optional[int]:
        vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
        return sum(vals) if vals else None

    # Aggregate per rider, then re-rank within the category by combined
    # (points DESC, time ASC). For multi-day events the per-day position
    # column is meaningless across days — we want overall race standings.
    aggregated: list[tuple[Optional[float], Optional[int], EventResultRowOut]] = []
    for rider_rows in grouped.values():
        rider = rider_rows[0].rider
        points_vals = [float(r.points) for r in rider_rows if r.points is not None]
        points = sum(points_vals) if points_vals else None
        time_ms = _sum_or_none(rider_rows, "time_ms")

        any_finished = any((r.status or "").upper() == "FIN" for r in rider_rows)
        notes = next((r.notes for r in rider_rows if r.notes), None)
        cp_count = next((r.cp_count for r in rider_rows if r.cp_count is not None), None)

        aggregated.append((
            points if any_finished else None,
            time_ms if any_finished else None,
            EventResultRowOut(
                position=None,
                rider=build_rider_ref(rider),
                points=points,
                time_ms=time_ms,
                gap_ms=_sum_or_none(rider_rows, "gap_ms"),
                gps_penalty_ms=_sum_or_none(rider_rows, "gps_penalty_ms"),
                laps=_sum_or_none(rider_rows, "laps"),
                cp_count=cp_count,
                notes=notes,
            ),
        ))

    aggregated.sort(
        key=lambda x: (
            x[0] is None,
            -(x[0] or 0),
            x[1] is None,
            x[1] or 0,
            x[2].rider.race_number,
        )
    )

    rows: list[EventResultRowOut] = []
    next_pos = 1
    for points, _time_ms, row in aggregated:
        if points is not None:
            row.position = next_pos
            next_pos += 1
        rows.append(row)

    return EventResultsOut(
        season=SeasonRef.model_validate(season),
        category=CategoryRef.model_validate(category),
        event=EventRef.model_validate(event),
        rows=rows,
    )
