"""S2 — Standings/Leaderboard API.

Port of ``backend/app/api/standings.py``
(``GET /api/seasons/{year}/standings/{category_code}`` — the Leaderboard
endpoint, ``backend/app/main.py:108``). Built by copying the F3 worked
reference pattern in ``api/seasons.py`` (see its PATTERN CHECKLIST):

* FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
  below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly,
  which mounts ``api.standings.router`` at ``/seasons``) and
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
  (one fewer query; behavior identical).
* The response is built with the F3 common refs + the S2
  ``api/schemas/standings.py`` schemas; the pinned renderer
  (``api/renderers.py``) makes the bytes byte-identical to the parity
  oracle. The per-row ``rider`` uses ``build_rider_ref`` (F3 ``core.slug``)
  exactly as the FastAPI router did.
* The scoring/standings algorithms come from the S2 service hub
  (``core.services.standings`` — ``events_for_season`` / ``get_standings``,
  ported verbatim; the No-N+1 ``prefetch_related`` is in that module). The
  iteration here mirrors ``backend/app/api/standings.py`` line-for-line so
  the JSON shape + ordering match byte-for-byte.
"""

from __future__ import annotations

from ninja import Router

from api.deps import YearPath, resolve_category, resolve_season
from api.schemas.common import CategoryRef, EventRef, SeasonRef, build_rider_ref
from api.schemas.standings import RiderEventEntryOut, StandingsOut, StandingsRowOut
from core.services.standings import events_for_season, get_standings

router = Router()


@router.get("/{year}/standings/{category_code}", response=StandingsOut)
def get_leaderboard(
    request, year: YearPath, category_code: str
) -> StandingsOut:
    """GET /api/seasons/{year}/standings/{category_code} — the Leaderboard.

    Port of ``backend/app/api/standings.py::get_leaderboard``. Byte-parity:
    same path, same response schema + field order, same row construction.
    """
    season = resolve_season(year)
    category = resolve_category(season, category_code)

    events = events_for_season(season)
    rows = get_standings(season, category)

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
                best_position=None if row.imputed_only else row.best_position,
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
