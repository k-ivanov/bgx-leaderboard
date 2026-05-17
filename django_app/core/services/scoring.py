"""Combined-time scoring for a (event, category).

S2 port of ``backend/src/services/scoring.py``. The algorithm body
(``points_for_position`` + ``compute_event_scoring`` + the position→points
tables + the three-tier ranking) is reused **VERBATIM** — it is pure Python
with zero ORM coupling: ``compute_event_scoring`` only reads ``r.rider_id``,
``r.day``, ``r.status``, ``r.time_ms`` off each row by duck typing (the
backend's own ``test_scoring.py`` proves this by passing
``types.SimpleNamespace`` rows). The ONLY change vs the FastAPI source is the
``EventResult`` type-hint import: SQLAlchemy ``..db.models`` → Django
``core.models`` (the SQLAlchemy/Django ``EventResult`` expose the same
``rider_id``/``day``/``status``/``time_ms`` attribute names, so the body is
byte-identical and behavior is parity-exact).

----- Original docstring (preserved verbatim) ---------------------------------

Points come from a position table whose maximum depends on how many days
the event has. The BGX scales:

- **1-day events** — max 25 points:
  25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1
- **2-day events** — max 40 points:
  40, 34, 30, 27, 24, 22, 20, 18, 16, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1

Positions outside 1..20 award 0. The 2-day scale is the per-day BGX day-1
and day-2 scales summed at matching positions (25+15, 22+12, 20+10, …).

**Ranking** for a 2-day event proceeds in three tiers:

1. **Full finishers** — riders with ``FIN`` and positive ``time_ms`` on
   every day. Ranked ascending by sum of ``time_ms``.
2. **Day-1-only finishers** — ``FIN`` on day 1 but not day 2. Ranked
   ascending by day-1 ``time_ms``. Placed below every Tier 1 rider.
3. **Day-2-only finishers** — ``FIN`` on day 2 but not day 1. Ranked
   ascending by day-2 ``time_ms``. Placed below every Tier 2 rider.

Riders with no ``FIN`` on any day get ``points=0`` and no position.

Positions count across tiers (1, 2, 3, …, then continue into Tier 2 etc.)
and look up points from the table above — so a Tier-2 rider in position
21+ earns 0, matching the table's tail.

For 1-day events only Tier 1 exists (its "combined time" is just day-1
time), so the policy reduces to "rank by time, award canonical 25/22/…".

This module is the single source of truth for per-event scoring. Both
``services/standings.py`` (season totals) and the per-event results
endpoint (``app/api/results.py``) consume it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from core.models import EventResult

# Position → points tables, keyed by number of days the event has.
# Positions outside 1..20 award 0.
_POINTS_BY_DAYS: dict[int, dict[int, int]] = {
    1: {
        1: 25, 2: 22, 3: 20, 4: 18, 5: 16, 6: 15, 7: 14, 8: 13, 9: 12, 10: 11,
        11: 10, 12: 9, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1,
    },
    2: {
        1: 40, 2: 34, 3: 30, 4: 27, 5: 24, 6: 22, 7: 20, 8: 18, 9: 16, 10: 14,
        11: 12, 12: 10, 13: 8, 14: 7, 15: 6, 16: 5, 17: 4, 18: 3, 19: 2, 20: 1,
    },
}


def points_for_position(position: int | None, n_days: int = 1) -> float:
    if position is None:
        return 0.0
    table = _POINTS_BY_DAYS.get(n_days, _POINTS_BY_DAYS[1])
    return float(table.get(position, 0))


@dataclass
class EventScore:
    """Combined-time score for one rider at one event."""
    rider_id: int
    combined_time_ms: int | None  # None when no FIN at all
    combined_position: int | None  # None when no FIN at all
    points: float
    tier: int | None  # 1 = full finisher, 2 = day-1 only, 3 = day-2 only, None = no FIN


def compute_event_scoring(results: Iterable[EventResult]) -> dict[int, EventScore]:
    """Rank a category's riders at one event by combined time, with
    tier-based fallback for partial finishers.

    ``results`` must be all EventResult rows for one (event, category).
    Returns one EventScore per rider that appeared in any row. Partial
    finishers (FIN one day, not the other) are still ranked — below every
    full finisher — so they earn points if they fall within the top 20.
    """
    by_rider: dict[int, list[EventResult]] = {}
    for r in results:
        by_rider.setdefault(r.rider_id, []).append(r)
    if not by_rider:
        return {}

    all_days = sorted({(r.day or 1) for rows in by_rider.values() for r in rows})
    n_days = len(all_days)

    tier_full: list[tuple[int, int]] = []   # (rider_id, combined_time_ms)
    tier_day1: list[tuple[int, int]] = []   # (rider_id, day_1_time_ms)
    tier_day2: list[tuple[int, int]] = []   # (rider_id, day_2_time_ms)
    no_fin: list[int] = []

    for rider_id, rows in by_rider.items():
        fin_by_day: dict[int, int] = {
            (r.day or 1): int(r.time_ms)
            for r in rows
            if (r.status or "").upper() == "FIN" and (r.time_ms or 0) > 0
        }
        if set(fin_by_day.keys()) == set(all_days):
            tier_full.append((rider_id, sum(fin_by_day.values())))
        elif n_days == 2 and 1 in fin_by_day and 2 not in fin_by_day:
            tier_day1.append((rider_id, fin_by_day[1]))
        elif n_days == 2 and 2 in fin_by_day and 1 not in fin_by_day:
            tier_day2.append((rider_id, fin_by_day[2]))
        else:
            no_fin.append(rider_id)

    tier_full.sort(key=lambda x: x[1])
    tier_day1.sort(key=lambda x: x[1])
    tier_day2.sort(key=lambda x: x[1])

    scores: dict[int, EventScore] = {}

    def _assign(tier_idx: int, items: list[tuple[int, int]], starting_pos: int) -> int:
        """Assign positions + points to a tier. Ties on time share the
        position; the next position skips accordingly. Returns the first
        free position after this tier."""
        last_time: int | None = None
        last_pos = starting_pos - 1
        for offset, (rider_id, time_ms) in enumerate(items):
            pos = starting_pos + offset
            if time_ms == last_time:
                pos = last_pos
            else:
                last_time = time_ms
                last_pos = pos
            scores[rider_id] = EventScore(
                rider_id=rider_id,
                combined_time_ms=time_ms,
                combined_position=pos,
                points=points_for_position(pos, n_days),
                tier=tier_idx,
            )
        return starting_pos + len(items)

    next_pos = 1
    next_pos = _assign(1, tier_full, next_pos)
    next_pos = _assign(2, tier_day1, next_pos)
    next_pos = _assign(3, tier_day2, next_pos)

    for rider_id in no_fin:
        scores[rider_id] = EventScore(
            rider_id=rider_id,
            combined_time_ms=None,
            combined_position=None,
            points=0.0,
            tier=None,
        )

    return scores


__all__ = ["points_for_position", "EventScore", "compute_event_scoring"]
