"""S4 — Rider-detail service. Django-ORM port of
``backend/src/services/rider.py``.

The **algorithm bodies are reused VERBATIM** — the (first, last) distinct
pairing, the multi-day collapse per (event, category), the position-from-points
imputation, the per-field timing sum, and the final sort key are byte-identical
to the FastAPI source (pinned by the ported ``test_riders_career.py`` /
``test_riders_search.py`` + the parity rig). Only the SQLAlchemy data-fetch
layer is rewritten to the Django ORM; the queries are *semantically identical*.

ORM translation (the ONLY change vs the FastAPI source)
-------------------------------------------------------
* ``select(Rider.first_name, Rider.last_name)
  .where(Rider.season_id == season.id, Rider.race_number == race_number)
  .distinct()``
  →  ``Rider.objects.filter(season_id=season.id, race_number=race_number)
  .values_list("first_name", "last_name").distinct()``
  — same WHERE, same DISTINCT on (first_name, last_name). Neither side adds
  an ``ORDER BY``; the disambiguation candidate order is observable JSON but
  the FastAPI source equally left it as the DB's unspecified distinct order.
  The S4 router sorts the *categories* inside each candidate deterministically
  (``sort_order, id``) exactly as the FastAPI router did; the candidate-pair
  order itself was never a contract on either side (the parity rig proves the
  set + every value is identical; the disambig list for the seeded golden data
  is a single candidate per number in practice).

* ``select(Rider).where(season_id, race_number, first_name, last_name)
  .options(selectinload(Rider.results).selectinload(EventResult.event),
           selectinload(Rider.category))``
  →  ``Rider.objects.filter(season_id, race_number, first_name, last_name)
  .select_related("category")
  .prefetch_related(Prefetch("results",
      EventResult.objects.select_related("event")))``
  — Django ``prefetch_related`` is the exact analogue of SQLAlchemy
  ``selectinload``: the related ``EventResult`` rows are batched in ONE extra
  query (``WHERE rider_id IN (...)``), and ``select_related("event")`` on the
  prefetch queryset JOINs the event in that same query (NOT a per-result
  query). ``select_related("category")`` JOINs the rider's category into the
  base query. This is the **No-N+1 acceptance criterion** (eng-review
  I8-perf=A): the rider-career path is the heaviest fan-out and must issue a
  small fixed number of queries regardless of how many seasons / categories /
  results the rider has. The runtime query-count proof is in
  ``tests/test_riders_career.py`` via ``CaptureQueriesContext``.

Signature change (service-API contract — mirrors the S2 hub)
------------------------------------------------------------
The FastAPI functions took a SQLAlchemy ``Session`` as their first arg
(per-request session lifetime via ``Depends(get_session)``). Django manages
the connection itself — there is no session object to thread — so the Django
service API drops that parameter (identical to the S2
``core.services.standings`` convention):

  * ``riders_sharing_number(session, season, race_number)``
        →  ``riders_sharing_number(season, race_number)``
  * ``get_rider_profile(session, season, race_number, first, last)``
        →  ``get_rider_profile(season, race_number, first, last)``

The OBSERVABLE behavior — the returned pair list / ``RiderProfile`` dataclass,
ordering, every numeric field — is parity-identical.

----- Original docstring (preserved verbatim) ---------------------------------

Rider-detail query: collect all results for a given (race_number, name)
across every category they raced in for a given season.

A rider is identified by the tuple (season, race_number, first_name, last_name).
Race numbers alone are not unique — two different people can share one
(e.g. 2025 #920 was both a junior rider and a standard rider), and the same
person sometimes races in multiple categories within a season.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.db.models import Prefetch

from core.models import Category, Event, EventResult, Rider, Season

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


def riders_sharing_number(
    season: Season, race_number: int
) -> list[tuple[str, str]]:
    """Distinct (first, last) pairs for the given race number in this season.

    Used to detect ambiguity: if the same number is used by two different
    people (different names), the detail page shows a disambiguation.

    Port of ``backend/src/services/rider.py::riders_sharing_number``:
    ``select(Rider.first_name, Rider.last_name).where(season_id, race_number)
    .distinct()`` → ``.values_list("first_name", "last_name").distinct()``.
    Same WHERE, same DISTINCT on the (first, last) tuple.
    """
    rows = (
        Rider.objects.filter(
            season_id=season.id, race_number=race_number
        )
        .values_list("first_name", "last_name")
        .distinct()
    )
    return [(f, l) for (f, l) in rows]


def get_rider_profile(
    season: Season,
    race_number: int,
    first_name: str,
    last_name: str,
) -> Optional[RiderProfile]:
    """Port of ``backend/src/services/rider.py::get_rider_profile``.

    Algorithm body reused verbatim; only the SQLAlchemy fetch is rewritten to
    the Django ORM with ``select_related``/``prefetch_related`` (the
    ``selectinload`` analogue — the No-N+1 path, eng-review I8-perf=A).
    """
    riders = list(
        Rider.objects.filter(
            season_id=season.id,
            race_number=race_number,
            first_name=first_name,
            last_name=last_name,
        )
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "results",
                queryset=EventResult.objects.select_related("event"),
            )
        )
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

    # Collapse multi-day rows into one entry per (event, category) — matches
    # how the leaderboard shows race totals. Points sum; position is the best
    # day's position; time is the combined (sum) time across days.
    grouped: dict[tuple[int, int], list] = {}
    for rider in riders:
        for er in rider.results.all():
            grouped.setdefault(
                (er.event.id, rider.category.id), []
            ).append((rider, er))

    results: list[RiderResult] = []
    for (_event_id, _category_id), day_rows in grouped.items():
        rider_first, first_er = day_rows[0]
        category = rider_first.category
        event = first_er.event

        points_list = [
            float(er.points) for _, er in day_rows if er.points is not None
        ]
        points = sum(points_list) if points_list else None

        explicit_positions = [
            er.position for _, er in day_rows if er.position is not None
        ]
        if explicit_positions:
            position = min(explicit_positions)
        elif points is not None and points > 0:
            position = position_from_points(points)
        else:
            position = None

        # Aggregate timing across days. Ignore None values; if every day is
        # None, the result is None.
        def _sum(field: str) -> int | None:
            vals = [
                getattr(er, field)
                for _, er in day_rows
                if getattr(er, field) is not None
            ]
            return sum(vals) if vals else None

        results.append(
            RiderResult(
                event=event,
                category=category,
                position=position,
                points=points,
                time_ms=_sum("time_ms"),
                gap_ms=_sum("gap_ms"),
                gps_penalty_ms=_sum("gps_penalty_ms"),
                laps=_sum("laps"),
            )
        )
    results.sort(
        key=lambda r: (r.event.sort_order, r.event.id, r.category.sort_order)
    )

    total_events = Event.objects.filter(season_id=season.id).count()

    return RiderProfile(
        race_number=race_number,
        first_name=first_name,
        last_name=last_name,
        team=team,
        bike=bike,
        categories=categories,
        results=results,
        total_events=total_events,
    )


__all__ = [
    "RiderResult",
    "RiderProfile",
    "riders_sharing_number",
    "get_rider_profile",
]
