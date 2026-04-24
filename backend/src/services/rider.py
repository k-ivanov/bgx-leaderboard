"""Rider-detail query: collect all results for a given (race_number, name)
across every category they raced in for a given season.

A rider is identified by the tuple (season, race_number, first_name, last_name).
Race numbers alone are not unique — two different people can share one
(e.g. 2025 #920 was both a junior rider and a standard rider), and the same
person sometimes races in multiple categories within a season.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Category, Event, EventResult, Rider, Season
from .standings import position_from_points


@dataclass
class RiderResult:
    event: Event
    category: Category
    position: Optional[int]
    points: Optional[float]
    time_ms: Optional[int]
    gap_ms: Optional[int]
    gps_penalty_ms: Optional[int]
    laps: Optional[int]


@dataclass
class RiderProfile:
    race_number: int
    first_name: str
    last_name: str
    team: Optional[str]
    bike: Optional[str]
    categories: list[Category]          # all categories this person races in
    results: list[RiderResult]          # sorted by event order, then category
    total_events: int                   # distinct events in this season


def riders_sharing_number(session: Session, season: Season, race_number: int) -> list[tuple[str, str]]:
    """Distinct (first, last) pairs for the given race number in this season.

    Used to detect ambiguity: if the same number is used by two different
    people (different names), the detail page shows a disambiguation.
    """
    rows = session.execute(
        select(Rider.first_name, Rider.last_name)
        .where(Rider.season_id == season.id, Rider.race_number == race_number)
        .distinct()
    ).all()
    return [(f, l) for (f, l) in rows]


def get_rider_profile(
    session: Session,
    season: Season,
    race_number: int,
    first_name: str,
    last_name: str,
) -> Optional[RiderProfile]:
    riders = list(
        session.execute(
            select(Rider)
            .where(
                Rider.season_id == season.id,
                Rider.race_number == race_number,
                Rider.first_name == first_name,
                Rider.last_name == last_name,
            )
            .options(
                selectinload(Rider.results).selectinload(EventResult.event),
                selectinload(Rider.category),
            )
        ).scalars()
    )
    if not riders:
        return None

    categories = sorted(
        {r.category for r in riders},
        key=lambda c: (c.sort_order, c.id),
    )

    # Pick the first non-empty team/bike across the rider's category rows
    # so the detail page has something to show even if one row is blank.
    team = next((r.team for r in riders if r.team), None)
    bike = next((r.bike for r in riders if r.bike), None)

    results: list[RiderResult] = []
    for rider in riders:
        for er in rider.results:
            points = float(er.points) if er.points is not None else None
            # 2025 aggregate data doesn't store raw per-event positions;
            # derive from points (BGX table) so the UI shows a ranking.
            position = er.position
            if position is None and points is not None and points > 0:
                position = position_from_points(points)
            results.append(
                RiderResult(
                    event=er.event,
                    category=rider.category,
                    position=position,
                    points=points,
                    time_ms=er.time_ms,
                    gap_ms=er.gap_ms,
                    gps_penalty_ms=er.gps_penalty_ms,
                    laps=er.laps,
                )
            )
    results.sort(key=lambda r: (r.event.sort_order, r.event.id, r.category.sort_order))

    total_events = session.execute(
        select(Event.id).where(Event.season_id == season.id)
    ).all()

    return RiderProfile(
        race_number=race_number,
        first_name=first_name,
        last_name=last_name,
        team=team,
        bike=bike,
        categories=categories,
        results=results,
        total_events=len(total_events),
    )
