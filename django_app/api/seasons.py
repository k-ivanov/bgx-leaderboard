"""S1 — Seasons API.  ←★ THE F3 WORKED REFERENCE ENDPOINT ★→

F3 fills THIS module as the **single fully-worked reference endpoint** that
every S1–S7 slice agent COPIES. It is the canonical pattern: how to consume
the F3 resolvers (``api/deps.py``), the F3 common schemas
(``api/schemas/common.py``), the pinned parity renderer (auto-installed by
``core.apps.CoreConfig.ready`` — slices wire nothing), and how the FROZEN
``NinjaAPI`` default exception handlers already produce the byte-exact
FastAPI ``{"detail": ...}`` 404 contract.

Port of ``backend/app/api/seasons.py`` (prefix ``/api/seasons``,
``backend/app/main.py:107``). Two endpoints, deliberately covering BOTH F3
patterns a slice needs:

  GET /api/seasons        — list (no resolver; pure schema + renderer parity)
  GET /api/seasons/{year} — detail (``YearPath`` 422 validation +
                            ``resolve_season`` byte-exact 404 + nested
                            ``CategoryRef``/``EventRef``/``SeasonRef``)

FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly) and
``config/urls.py`` (resolution order) are FROZEN — never edited by any slice.
The ``router`` object below is imported BY REFERENCE into the frozen
assembly; filling it here is all a slice does. S1 OWNS this module after F3
merges (F3 hands over a green, parity-proven reference; S1 extends as needed
— e.g. extra query params — without ever touching the frozen files).

PATTERN CHECKLIST (copy this for every S1–S7 endpoint)
------------------------------------------------------
1. ``from ninja import Router`` ; ``router = Router()`` — keep the SAME
   module-level name the frozen assembly imports (``router`` /
   ``career_router``); the F1 slot is already pre-stubbed with it.
2. Response schema = an ``api/schemas/<domain>.py`` ``Schema`` built from F3
   common refs (``SeasonRef``/``CategoryRef``/``EventRef``/``RiderRef``).
   Field order == FastAPI Pydantic order == JSON key order (renderer never
   re-sorts) → ``openapi-typescript`` regenerates with no diff.
3. Path params the FastAPI app constrained with ``Path(ge=…, le=…)`` use the
   F3 ``YearPath`` (or an equivalent ``Annotated[int, Path(...)]``) so Ninja
   emits the SAME 422 Pydantic-error body the oracle does.
4. Existence lookups go through F3 ``resolve_season`` / ``resolve_category``
   — NEVER hand-roll the 404 string; the byte-exact detail lives in F3.
5. Build the response with ``Schema.model_validate(<Django instance>)`` (or
   ``.from_orm`` for ``RiderRef``). The pinned renderer makes the bytes
   byte-identical to the parity oracle — slices wire nothing for that.
6. Prove it: add a parity test using ``tests.parity.assert_json_parity``
   against the spun FastAPI oracle (copy ``tests/test_reference_parity.py``).
"""

from __future__ import annotations

from ninja import Router

from api.deps import YearPath, resolve_season
from api.schemas.common import CategoryRef, EventRef, SeasonRef
from api.schemas.seasons import SeasonDetailOut, SeasonListOut
from core.models import Category, Event, Rider, Season

router = Router()


@router.get("", response=SeasonListOut)
def list_seasons(request) -> SeasonListOut:
    """GET /api/seasons — every season, newest year first.

    Port of ``backend/app/api/seasons.py::list_seasons``. Ordering is
    byte-identical: ``ORDER BY year DESC`` (FastAPI
    ``select(Season).order_by(Season.year.desc())``).
    """
    seasons = list(Season.objects.order_by("-year"))
    return SeasonListOut(
        seasons=[SeasonRef.model_validate(s) for s in seasons]
    )


@router.get("/{year}", response=SeasonDetailOut)
def get_season_detail(request, year: YearPath) -> SeasonDetailOut:
    """GET /api/seasons/{year} — season + categories + events + rider count.

    Port of ``backend/app/api/seasons.py::get_season_detail``.

    * ``year: YearPath`` reproduces FastAPI's ``Path(..., ge=1900,
      le=2999)`` → non-integer / out-of-range ``year`` yields the SAME 422
      Pydantic error-list body (Ninja's frozen default validation handler).
    * ``resolve_season`` raises the byte-exact 404
      (``{"detail":"Season {year} not found"}``) via the FROZEN default
      ``HttpError`` handler — no custom handler, no frozen-file edit.
    * Category/Event ordering is byte-identical to the oracle:
      ``ORDER BY sort_order, id``.
    """
    season = resolve_season(year)
    categories = list(
        Category.objects.filter(season_id=season.id).order_by(
            "sort_order", "id"
        )
    )
    events = list(
        Event.objects.filter(season_id=season.id).order_by("sort_order", "id")
    )
    rider_count = Rider.objects.filter(season_id=season.id).count()
    return SeasonDetailOut(
        season=SeasonRef.model_validate(season),
        categories=[CategoryRef.model_validate(c) for c in categories],
        events=[EventRef.model_validate(e) for e in events],
        rider_count=rider_count,
    )
