"""GET /api/seasons/{year}/standings/{category_code} — the Leaderboard endpoint."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import get_category, get_session
from app.schemas.common import (
    CategoryRef,
    EventRef,
    SeasonRef,
    build_rider_ref,
)
from app.schemas.standings import (
    RiderEventEntryOut,
    StandingsOut,
    StandingsRowOut,
)
from src.db.models import Category
from src.services.standings import events_for_season, get_standings

router = APIRouter(prefix="/api/seasons", tags=["leaderboard"])


@router.get(
    "/{year}/standings/{category_code}",
    response_model=StandingsOut,
)
def get_leaderboard(
    category: Category = Depends(get_category),
    session: Session = Depends(get_session),
) -> StandingsOut:
    season = category.season
    events = events_for_season(session, season)
    rows = get_standings(session, season, category)

    out_rows: list[StandingsRowOut] = []
    for row in rows:
        out_rows.append(
            StandingsRowOut(
                final_position=row.final_position,
                rider=build_rider_ref(row.rider),
                events=[
                    RiderEventEntryOut(
                        event_slug=slug,
                        points=entry.points,
                        position=entry.position,
                    )
                    for slug, entry in row.events_by_slug.items()
                ],
                total_points=row.total_points,
                races_participated=row.races_participated,
                best_position=row.best_position,
                worst_event_slug=row.worst_event_slug,
                worst_dropped=row.worst_dropped,
            )
        )

    return StandingsOut(
        season=SeasonRef.model_validate(season),
        category=CategoryRef.model_validate(category),
        events=[EventRef.model_validate(ev) for ev in events],
        rows=out_rows,
        championship_format=season.championship_format,
    )
