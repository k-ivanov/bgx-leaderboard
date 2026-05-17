"""S3 — Events/Races API.

Port of ``backend/app/api/events.py`` (prefix ``/api/seasons``,
``backend/app/main.py:109``). Two endpoints:

  GET /api/seasons/{year}/events          — the races in a season
  GET /api/seasons/{year}/events/{slug}   — one race + its categories

Built by copying the F3 worked reference pattern in ``api/seasons.py`` (see
its PATTERN CHECKLIST) — identical to how S2 (``api/standings.py``) was built:

* FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
  below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly,
  which mounts ``api.events.router`` at ``/seasons`` with ``tags=["races"]``)
  and ``config/urls.py`` are FROZEN — never edited. The module-level name
  ``router`` is kept exactly as the frozen slot pre-stubbed it.

* The FastAPI handlers resolved the season via ``Depends(get_season)`` (which
  chains ``Path(..., ge=1900, le=2999)``). Django Ninja has no ``Depends``;
  per F3 (``api/deps.py``) this becomes an explicit ``resolve_season`` call +
  the ``YearPath`` annotation. The OBSERVABLE contract is byte-identical:
    - bad ``year``       → ``YearPath`` 422 (out of range / non-int) or
      ``resolve_season`` 404 ``{"detail":"Season {year} not found"}``;
    - unknown ``slug``   → 404
      ``{"detail":"Race '{event_slug}' not found in season {year}"}``.
  The season-404 string lives byte-exact in F3 (``api/deps.py``); the
  race-detail 404 string is byte-identical to ``backend/app/api/events.py``
  (``f"Race '{event_slug}' not found in season {season.year}"``) and is
  raised here as a ``ninja.errors.HttpError`` — the FROZEN NinjaAPI default
  handler renders it as ``{"detail": ...}`` at 404, byte-parity with the
  FastAPI ``HTTPException(404, detail=...)``.

* The season's race list comes from the S2 service hub
  (``core.services.standings.events_for_season`` — ported verbatim; the
  Django service API drops the FastAPI SQLAlchemy ``Session`` first arg).
  This module does NOT reimplement it (decision Lane D: S3 reads S2's
  read-only service). The race-detail handler does its own
  ``Event``/``Category`` lookups exactly as ``backend/app/api/events.py``
  did (the FastAPI source did not route the detail lookup through
  ``events_for_season`` either — it issued a scoped ``select(Event)``).

* The response is built with the F3 common refs
  (``SeasonRef``/``EventRef``/``CategoryRef``) + the S3
  ``api/schemas/events.py`` schemas; the pinned renderer
  (``api/renderers.py``) makes the bytes byte-identical to the parity
  oracle. ``EventRef`` already carries the editorial ``facebook_event_url``
  / ``description`` as ``Optional[str] = None`` (null-safe), so they surface
  identically with zero S3 code.

* Category ordering in the detail response is byte-identical to the oracle:
  ``ORDER BY sort_order, id`` (FastAPI
  ``order_by(Category.sort_order, Category.id)``).
"""

from __future__ import annotations

from ninja import Router
from ninja.errors import HttpError

from api.deps import YearPath, resolve_season
from api.schemas.common import CategoryRef, EventRef, SeasonRef
from api.schemas.events import EventDetailOut, EventListOut
from core.models import Category, Event
from core.services.standings import events_for_season

router = Router()


@router.get("/{year}/events", response=EventListOut)
def list_races(request, year: YearPath) -> EventListOut:
    """GET /api/seasons/{year}/events — the races in a season.

    Port of ``backend/app/api/events.py::list_races``. Byte-parity: same
    path, same response schema + field order, same ``events`` array order.
    The season is resolved via F3 ``resolve_season`` (byte-exact 404) and the
    race list comes from the S2 ``events_for_season`` service hub (consumed,
    not reimplemented — Lane D).
    """
    season = resolve_season(year)
    events = events_for_season(season)
    return EventListOut(
        season=SeasonRef.model_validate(season),
        events=[EventRef.model_validate(e) for e in events],
    )


@router.get("/{year}/events/{event_slug}", response=EventDetailOut)
def get_race_detail(
    request, year: YearPath, event_slug: str
) -> EventDetailOut:
    """GET /api/seasons/{year}/events/{event_slug} — one race + categories.

    Port of ``backend/app/api/events.py::get_race_detail``. Byte-parity:
    same path, same response schema + field order, same row construction,
    same category ordering, same 404 detail string.

    * ``resolve_season`` raises the byte-exact season 404 (F3).
    * Unknown ``event_slug`` raises the byte-exact race 404 string from
      ``backend/app/api/events.py``:
      ``f"Race '{event_slug}' not found in season {season.year}"``.
    * Categories: ``ORDER BY sort_order, id`` (FastAPI parity).
    """
    season = resolve_season(year)

    event = (
        Event.objects.filter(season_id=season.id, slug=event_slug)
        .first()
    )
    if event is None:
        raise HttpError(
            404,
            f"Race '{event_slug}' not found in season {season.year}",
        )

    categories = list(
        Category.objects.filter(season_id=season.id).order_by(
            "sort_order", "id"
        )
    )

    return EventDetailOut(
        season=SeasonRef.model_validate(season),
        event=EventRef.model_validate(event),
        categories=[CategoryRef.model_validate(c) for c in categories],
    )
