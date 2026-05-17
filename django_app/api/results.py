"""S7 — Results API  *(added — review OV1)*.

Port of ``backend/app/api/results.py`` — the per-race, per-category Results
endpoint the frontend's PRIMARY ``/results`` SPA island calls
(``ResultsView.vue:93``; the FROZEN ``api/__init__.py`` mounts
``api.results.router`` at ``/seasons`` with ``tags=["race-results"]`` —
parity with the FastAPI ``APIRouter(prefix="/api/seasons",
tags=["race-results"])`` mounted at ``backend/app/main.py:110``). One
endpoint:

  GET /api/seasons/{year}/categories/{category_code}/events/{event_slug}

This slice was missing from the original 13-task breakdown (review OV1); it
is the OpenAPI Race Results path S3 explicitly left out as S7 scope.

Built by copying the F3 worked reference pattern (``api/seasons.py`` PATTERN
CHECKLIST) — identical to how S2 (``api/standings.py``) / S3
(``api/events.py``) were built:

* FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
  below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly) and
  ``config/urls.py`` are FROZEN — never edited. The module-level name
  ``router`` is kept exactly as the frozen slot pre-stubbed it.

* The FastAPI handler resolved season+category via ``Depends(get_category)``
  (which chains ``get_season`` → ``Path(..., ge=1900, le=2999)``). Django
  Ninja has no ``Depends``; per F3 (``api/deps.py``) this becomes explicit
  ``resolve_season`` / ``resolve_category`` calls + the ``YearPath``
  annotation. The OBSERVABLE contract is byte-identical:
    - bad ``year``      → ``YearPath`` 422 (out of range / non-int) or
      ``resolve_season`` 404 ``{"detail":"Season {year} not found"}``;
    - bad ``category``  → ``resolve_category`` 404
      ``{"detail":"Category '{code}' not found in season {year}"}``.
  Both 404 strings are byte-exact to ``backend/app/deps.py`` (they live in
  F3, never hand-rolled here).

* FastAPI did ``season = category.season`` (SQLAlchemy lazy relationship).
  Here ``season`` is already the row ``resolve_season`` returned and is the
  SAME season ``resolve_category`` scoped the lookup to — use it directly
  (one fewer query; behavior identical, exactly as S2 did).

* Unknown ``event_slug`` raises the byte-exact race 404 string from
  ``backend/app/api/results.py``:
  ``f"Race '{event_slug}' not found in season {season.year}"`` — raised
  inline as ``ninja.errors.HttpError`` (the FastAPI source hand-rolled the
  same ``HTTPException(404, detail=...)``; there is no F3 event-by-slug
  resolver — S3 ``get_race_detail`` does the same).

* The combined-time scoring (with the Tier-1/Tier-2 fallback) comes from the
  S2 service hub (``core.services.scoring.compute_event_scoring`` — ported
  verbatim by S2; the Django service API drops the FastAPI SQLAlchemy
  ``Session`` first arg, exactly like the FastAPI ``results.py`` called it
  with the row list only). This module does NOT reimplement it
  (decision Lane D: S7 reads S2's read-only scoring service). The
  ``EventScore`` dataclass it returns (``combined_position`` /
  ``combined_time_ms`` / ``points``) is the S2 contract.

* Results data-fetch translation. FastAPI:
    ``select(EventResult).join(Rider, EventResult.rider_id == Rider.id)
      .where(EventResult.event_id == event.id,
             Rider.category_id == category.id)
      .options(selectinload(EventResult.rider))
      .order_by(EventResult.day, EventResult.id)``
  →  ``EventResult.objects.filter(event_id=event.id,
        rider__category_id=category.id).select_related("rider")
        .order_by("day", "id")``.
  ``selectinload(EventResult.rider)`` is a FORWARD many-to-one
  (``EventResult.rider``), so the Django analogue is ``select_related`` — NOT
  the reverse-collection ``prefetch_related`` that produced S2/S4's
  unspecified-heap per-row ARRAY divergence. Critically the FastAPI source
  here has an EXPLICIT, deterministic ``ORDER BY EventResult.day,
  EventResult.id`` (it is NOT an unordered ``selectinload`` heap artifact),
  so the iteration order of ``grouped`` (a dict whose insertion order ==
  this query order) is identical in both stacks. The final ``rows`` array is
  then re-sorted by ``(combined_position, race_number)`` (ranked) /
  ``race_number`` (unranked) exactly as FastAPI did — a fully deterministic,
  semantically meaningful order. There is therefore NO unordered-heap
  divergence to resolve in S7 (unlike S2/S4); the ``order_by("day", "id")``
  is preserved verbatim to keep the dict-insertion order — and hence the
  ``cp_count``/``notes``/``status`` "first non-null wins" picks below —
  byte-identical to the oracle.

* The response is built field-by-field (parity with the FastAPI router,
  which constructed ``EventResultRowOut(...)`` explicitly rather than via
  ``model_validate``) with the S7 ``api/schemas/results.py`` schemas + the
  F3 shared refs (``SeasonRef``/``CategoryRef``/``EventRef``) +
  ``build_rider_ref`` (F3 ``core.slug``) — exactly the constructors the
  FastAPI router used. The pinned renderer (``api/renderers.py``) makes the
  bytes byte-identical to the parity oracle.
"""

from __future__ import annotations

from typing import Optional

from ninja import Router
from ninja.errors import HttpError

from api.deps import YearPath, resolve_category, resolve_season
from api.schemas.common import (
    CategoryRef,
    EventRef,
    SeasonRef,
    build_rider_ref,
)
from api.schemas.results import EventResultRowOut, EventResultsOut
from core.models import Event, EventResult
from core.services.scoring import compute_event_scoring

router = Router()


def _sum_or_none(rows: list[EventResult], field: str) -> Optional[int]:
    """Sum a per-day field across a rider's day rows, ``None`` if all null.

    Byte-identical to the inner ``_sum_or_none`` in
    ``backend/app/api/results.py``: only non-null values contribute; an
    all-null set yields ``None`` (not ``0``).
    """
    vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
    return sum(vals) if vals else None


@router.get(
    "/{year}/categories/{category_code}/events/{event_slug}",
    response=EventResultsOut,
)
def get_race_results(
    request,
    year: YearPath,
    category_code: str,
    event_slug: str,
) -> EventResultsOut:
    """GET /api/seasons/{year}/categories/{category_code}/events/{event_slug}.

    Port of ``backend/app/api/results.py::get_race_results``. Byte-parity:
    same path, same response schema + field order, same row construction,
    same ranked/unranked split + tie ordering, same per-day breakdown, same
    404 detail strings.

    * ``resolve_season`` raises the byte-exact season 404 (F3).
    * ``resolve_category`` raises the byte-exact category 404 (F3); the
      FastAPI ``Depends(get_category)`` chained ``get_season`` first, so a
      bad year is resolved (→ season 404) BEFORE the category lookup —
      reproduced here by calling ``resolve_season`` first.
    * Unknown ``event_slug`` raises the byte-exact race 404 string from
      ``backend/app/api/results.py``:
      ``f"Race '{event_slug}' not found in season {season.year}"``.
    * Scoring via the S2 ``compute_event_scoring`` service (consumed, not
      reimplemented — Lane D).
    """
    season = resolve_season(year)
    category = resolve_category(season, category_code)

    event = (
        Event.objects.filter(season_id=season.id, slug=event_slug).first()
    )
    if event is None:
        raise HttpError(
            404,
            f"Race '{event_slug}' not found in season {season.year}",
        )

    # Join results → riders filtered to this category, eager load rider for
    # RiderRef. FastAPI used selectinload(EventResult.rider) (a forward
    # many-to-one) → Django select_related. The ORDER BY day, id is EXPLICIT
    # in the FastAPI source (deterministic — NOT an unordered heap artifact),
    # so it is preserved verbatim to keep the grouped-dict insertion order
    # (and the "first non-null wins" notes/cp_count/status picks below)
    # byte-identical to the oracle.
    results = list(
        EventResult.objects.filter(
            event_id=event.id,
            rider__category_id=category.id,
        )
        .select_related("rider")
        .order_by("day", "id")
    )

    grouped: dict[int, list[EventResult]] = {}
    for r in results:
        grouped.setdefault(r.rider_id, []).append(r)

    days_present = sorted({(r.day or 1) for r in results})

    # Combined-time scoring with tier fallback (see core/services/scoring.py;
    # the S2-owned port of src/services/scoring.py — Lane D read-only).
    scoring = compute_event_scoring(results)

    ranked_rows: list[tuple[int, EventResultRowOut]] = []
    unranked_rows: list[EventResultRowOut] = []
    for rider_id, rider_rows in grouped.items():
        rider = rider_rows[0].rider
        score = scoring.get(rider_id)
        notes = next((r.notes for r in rider_rows if r.notes), None)
        cp_count = next(
            (r.cp_count for r in rider_rows if r.cp_count is not None), None
        )
        by_day = {(r.day or 1): r for r in rider_rows}
        d1 = by_day.get(1)
        d2 = by_day.get(2)

        ranked = score is not None and score.combined_position is not None
        row = EventResultRowOut(
            position=None,
            rider=build_rider_ref(rider),
            points=score.points if ranked else None,
            time_ms=score.combined_time_ms if ranked else None,
            day_1_time_ms=(
                d1.time_ms
                if d1 and (d1.status or "").upper() == "FIN"
                else None
            ),
            day_2_time_ms=(
                d2.time_ms
                if d2 and (d2.status or "").upper() == "FIN"
                else None
            ),
            day_1_status=(d1.status if d1 else None),
            day_2_status=(d2.status if d2 else None),
            gap_ms=_sum_or_none(rider_rows, "gap_ms"),
            gps_penalty_ms=_sum_or_none(rider_rows, "gps_penalty_ms"),
            laps=_sum_or_none(rider_rows, "laps"),
            cp_count=cp_count,
            notes=notes,
        )
        if ranked:
            ranked_rows.append((score.combined_position, row))
        else:
            unranked_rows.append(row)

    ranked_rows.sort(key=lambda x: (x[0], x[1].rider.race_number))
    unranked_rows.sort(key=lambda r: r.rider.race_number)

    rows: list[EventResultRowOut] = []
    for pos, row in ranked_rows:
        row.position = pos
        rows.append(row)
    rows.extend(unranked_rows)

    return EventResultsOut(
        season=SeasonRef.model_validate(season),
        category=CategoryRef.model_validate(category),
        event=EventRef.model_validate(event),
        days=days_present,
        rows=rows,
    )
