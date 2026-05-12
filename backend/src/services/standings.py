"""Compute season standings for a category from event_result rows.

Supports two championship formats:
  - 'aggregate_2025': the 2025 rule — if a rider participated in every event,
    their worst score is dropped from the total.
  - 'per_event': no drop; total is the plain sum of event points.

For 2025 data we don't have raw per-event positions, only points per rider.
Points are converted to a position via the BGX championship points table
(25→1, 22→2, 20→3, 18→4, 16→5, 15→6, … 1→20, 0→21).

For 2026+ per-event data with day-by-day times, an event's points are
computed by ``services.scoring.compute_event_scoring``: rank eligible
riders by combined time across all days, then award from the canonical
25/22/20/… table. Full policy: ``docs/scoring.md``.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..db.models import Category, Event, EventResult, Rider, Season
from .scoring import compute_event_scoring

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
    # True when the rider has no explicit finish position in any event
    # they entered (every row is DNF / DNS / DSQ, or position is missing).
    # Such riders' best_position is imputed from points via
    # position_from_points and would otherwise unfairly outrank riders
    # whose explicit positions happen to be > 21. Used as a sort-key
    # demoter — see the chain comment near the bottom of get_standings.
    imputed_only: bool
    # Sum across the rider's events of (finishers − position + 1) / finishers,
    # only counting events where the rider has a real (explicit) finish
    # position. DNF / DNS / DSQ / imputed-from-points positions contribute 0.
    # Used as a season tiebreaker after best_position; never exposed via API.
    # See docs/scoring.md "Tiebreakers" for the rationale.
    total_inverse_position: float
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

    # Combined-time event scoring, computed once per event for this category.
    # Each rider's per-event entry below reads its points & position from
    # this table; if the rider is ineligible (DNF any day / missing day),
    # they appear with points=0 and position=None.
    rider_ids_in_cat = {r.id for r in riders}
    event_scoring: dict[int, dict] = {}
    for ev in events:
        cat_results = [
            er for r in riders for er in r.results if er.event_id == ev.id
        ]
        if cat_results:
            event_scoring[ev.id] = compute_event_scoring(cat_results)

    # Field-size lookup for the percentile tiebreaker. Counts eligible
    # finishers (riders with a real combined position) per event in this
    # category.
    finishers_per_event: dict[int, int] = {}
    for eid, scores in event_scoring.items():
        finishers_per_event[eid] = sum(
            1 for s in scores.values() if s.combined_position is not None
        )

    rows: list[StandingsRow] = []

    for rider in riders:
        per_event: dict[int, list] = {}
        for er in rider.results:
            per_event.setdefault(er.event_id, []).append(er)

        entries: dict[str, RiderEventEntry] = {}
        total_inverse_position = 0.0
        has_any_explicit_finish = False
        for event_id, _day_rows in per_event.items():
            ev = event_by_id.get(event_id)
            if ev is None:
                continue
            score = event_scoring.get(event_id, {}).get(rider.id)
            if score is None:
                continue
            event_points = score.points
            event_position = score.combined_position
            if event_position is not None:
                has_any_explicit_finish = True
                finishers = finishers_per_event.get(event_id, 0)
                if finishers > 0:
                    contribution = (finishers - event_position + 1) / finishers
                    total_inverse_position += max(0.0, min(1.0, contribution))
            entries[ev.slug] = RiderEventEntry(
                event=ev,
                points=event_points,
                position=event_position if event_position is not None else position_from_points(event_points),
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
                imputed_only=not has_any_explicit_finish,
                total_inverse_position=total_inverse_position,
                worst_event_slug=worst_event_slug,
                worst_dropped=worst_dropped,
            )
        )

    # Tiebreaker chain — pinned by tests/test_standings_tiebreakers.py.
    # Full rationale + worked examples in docs/scoring.md "Tiebreakers".
    #   1. Higher total_points wins.
    #   2. Riders with at least one explicit finish position rank above
    #      riders whose every event was DNF / DNS / DSQ (only-imputed).
    #      Otherwise a back-of-pack 23rd-place finish (best_position=23)
    #      loses to a never-finished rider whose best_position is imputed
    #      to 21 from 0 points.
    #   3. Then better best_position (1 beats 2). Within each tier above
    #      the imputed-only tier, this is the dominant ranking field.
    #   4. Then HIGHER total_inverse_position wins. Per-event percentile
    #      sum (finishers − position + 1) / finishers across each event
    #      the rider entered. Rewards "better finishes" — events with
    #      no explicit position contribute 0.
    #   5. Then MORE races_participated wins. Among riders tied on
    #      everything above (typically the imputed-only group, where
    #      total_inverse_position is 0 for everyone), this rewards
    #      "showing up" — a rider who DNF'd 3 races outranks one
    #      who DNF'd 1.
    #   6. Then lower race_number — final stable break, deterministic.
    rows.sort(
        key=lambda r: (
            -r.total_points,
            r.imputed_only,
            r.best_position,
            -r.total_inverse_position,
            -r.races_participated,
            r.rider.race_number,
        )
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
