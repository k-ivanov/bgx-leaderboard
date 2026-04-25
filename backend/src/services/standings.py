"""Compute season standings for a category from event_result rows.

Supports two championship formats:
  - 'aggregate_2025': the 2025 rule — if a rider participated in every event,
    their worst score is dropped from the total.
  - 'per_event': no drop; total is the plain sum of event points.

For 2025 data we don't have raw per-event positions, only points per rider.
Points are converted to a position via the BGX championship points table
(25→1, 22→2, 20→3, 18→4, 16→5, 15→6, … 1→20, 0→21).

For 2026+ per-event data, EventResult.position is set by the importer and
is used directly when present.

Scoring policy (improvements.md P2 #12 — full text in docs/scoring.md):
  Each (rider, event) pair sums every EventResult row across all `day`
  values. A two-day weekend produces ONE event total equal to day-1 +
  day-2 + … . This is deliberate — the dashboard is an archive of every
  result the championship publishes, not a faithful mirror of any
  single scoring rule. The validation report at
  .reports/2025-validation-vs-hardendurobulgaria.md quantifies the
  resulting deltas vs sources that use day-1-only.

  To switch to day-1-only without breaking the archive: add a `?day=1`
  query param at the API layer that filters EventResult.day == 1 and
  document the new behavior in docs/scoring.md.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Category, Event, EventResult, Rider, Season

# BGX 2025 points → position. 0 points maps to 21 ("raced, outside top 20").
_POINTS_TO_POSITION: dict[float, int] = {
    25.0: 1,
    22.0: 2,
    20.0: 3,
    18.0: 4,
    16.0: 5,
    15.0: 6,
    14.0: 7,
    13.0: 8,
    12.0: 9,
    11.0: 10,
    10.0: 11,
    9.0: 12,
    8.0: 13,
    7.0: 14,
    6.0: 15,
    5.0: 16,
    4.0: 17,
    3.0: 18,
    2.0: 19,
    1.0: 20,
    0.0: 21,
}


def position_from_points(points: float) -> int:
    # Exact table match for the canonical BGX values, else interpolate by rank.
    if points in _POINTS_TO_POSITION:
        return _POINTS_TO_POSITION[points]
    # Fractional or non-standard points: map to the nearest rank by comparing
    # against sorted table entries.
    for value, pos in _POINTS_TO_POSITION.items():
        if points >= value:
            return pos
    return 21


@dataclass
class RiderEventEntry:
    event: Event
    points: float
    position: int


@dataclass
class StandingsRow:
    final_position: int
    rider: Rider
    events_by_slug: dict[str, RiderEventEntry]
    total_points: float
    races_participated: int
    best_position: int
    worst_event_slug: Optional[str]
    worst_dropped: Optional[float]


def get_standings(session: Session, season: Season, category: Category) -> list[StandingsRow]:
    events = list(
        session.execute(
            select(Event).where(Event.season_id == season.id).order_by(Event.sort_order, Event.id)
        ).scalars()
    )
    event_by_id = {ev.id: ev for ev in events}
    total_events = len(events)

    riders = list(
        session.execute(
            select(Rider)
            .where(Rider.category_id == category.id)
            .options(selectinload(Rider.results))
        ).scalars()
    )

    rows: list[StandingsRow] = []

    for rider in riders:
        # First group raw results by event, then collapse the per-day rows into
        # a single championship entry. Points sum across days; position is the
        # best (lowest) day's position.
        per_event: dict[int, list] = {}
        for er in rider.results:
            per_event.setdefault(er.event_id, []).append(er)

        entries: dict[str, RiderEventEntry] = {}
        for event_id, day_rows in per_event.items():
            ev = event_by_id.get(event_id)
            if ev is None:
                continue
            total_event_points = sum(float(r.points or 0) for r in day_rows)
            # Best (lowest) position across the days. Fall back to the
            # points-derived position if no day has an explicit position.
            explicit_positions = [r.position for r in day_rows if r.position is not None]
            if explicit_positions:
                best_event_position = min(explicit_positions)
            else:
                best_event_position = position_from_points(total_event_points)
            entries[ev.slug] = RiderEventEntry(
                event=ev,
                points=total_event_points,
                position=best_event_position,
            )

        races_participated = len(entries)
        if races_participated == 0:
            continue

        raw_total = sum(e.points for e in entries.values())
        best_position = min(e.position for e in entries.values())

        worst_event_slug: Optional[str] = None
        worst_dropped: Optional[float] = None
        total = raw_total

        if season.championship_format == "aggregate_2025" and races_participated == total_events:
            worst_entry = min(entries.values(), key=lambda e: (e.points, e.event.sort_order))
            worst_event_slug = worst_entry.event.slug
            # Only record an actual drop if it changes the total. The 2025
            # CSVs annotate WorstRace even when the worst score is 0, but
            # leave WorstResultDropped empty because dropping 0 is a no-op.
            if worst_entry.points > 0:
                worst_dropped = worst_entry.points
                total = raw_total - worst_dropped

        rows.append(
            StandingsRow(
                final_position=0,
                rider=rider,
                events_by_slug=entries,
                total_points=total,
                races_participated=races_participated,
                best_position=best_position,
                worst_event_slug=worst_event_slug,
                worst_dropped=worst_dropped,
            )
        )

    rows.sort(
        key=lambda r: (-r.total_points, r.best_position, r.races_participated, r.rider.race_number)
    )
    for idx, row in enumerate(rows):
        row.final_position = idx + 1

    return rows


def events_for_season(session: Session, season: Season) -> list[Event]:
    return list(
        session.execute(
            select(Event).where(Event.season_id == season.id).order_by(Event.sort_order, Event.id)
        ).scalars()
    )
