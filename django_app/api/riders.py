"""S4 — Riders API (per-season profile + disambiguation + search + career).

Port of ``backend/app/api/riders.py`` (BOTH the per-season ``router``,
prefix ``/api/seasons`` — ``backend/app/main.py:111`` — and the cross-season
``career_router``, prefix ``/api/riders`` — ``backend/app/main.py:112``).
Built by copying the F3 worked reference pattern in ``api/seasons.py`` (see
its PATTERN CHECKLIST) — identical to how S2 (``api/standings.py``) and S3
(``api/events.py``) were built:

* FROZEN-FILE CONTRACT (decision I1-arch=A): this module owns ONLY the body
  below. ``api/__init__.py`` (the single ``NinjaAPI`` + router assembly,
  which mounts ``api.riders.router`` at ``/seasons`` and
  ``api.riders.career_router`` at ``/riders``, both ``tags=["riders"]``) and
  ``config/urls.py`` are FROZEN — never edited. The module-level names
  ``router`` / ``career_router`` are kept exactly as the frozen slots
  pre-stubbed them.

* The FastAPI handlers resolved the season via ``Depends(get_season)`` (which
  chains ``Path(..., ge=1900, le=2999)``) and validated query params with
  ``Query(..., min_length=…, max_length=…, ge=…, le=…)``. Django Ninja has no
  ``Depends``; per F3 (``api/deps.py``) season existence becomes an explicit
  ``resolve_season`` call + the ``YearPath`` annotation, and the query-param
  constraints become ``Annotated[…, Query(...)]`` so Ninja's Pydantic
  validation raises the SAME 422 error-list shape FastAPI emits. The
  OBSERVABLE contract is byte-identical:
    - bad ``year``        → ``YearPath`` 422 or ``resolve_season`` 404
      ``{"detail":"Season {year} not found"}`` (string lives byte-exact in F3);
    - missing/over-long ``q`` / out-of-range ``limit`` → 422 Pydantic body;
    - unknown ``race_number`` → 404 ``{"detail":"No rider with number
      {race_number} in season {year}"}`` (byte-identical to
      ``backend/app/api/riders.py``, raised inline as ``HttpError`` — the
      FastAPI source hand-rolled the same ``HTTPException`` string; there is
      no F3 resolver for "rider-by-number");
    - slug mismatch / no results / unknown career slug → the byte-identical
      404 detail strings from ``backend/app/api/riders.py``.

* The rider service comes from the ported ``core.services.rider``
  (``riders_sharing_number`` / ``get_rider_profile`` — algorithm bodies
  verbatim, SQLAlchemy → Django ORM with ``prefetch_related`` to avoid N+1).
  The general-classification rank comes from the S2 service hub
  (``core.services.standings.get_standings`` — consumed read-only, Lane D;
  NOT reimplemented). The career endpoint is the heaviest fan-out path
  (eng-review I8-perf=A): candidates are loaded with
  ``select_related``/``prefetch_related`` so the query count stays within
  bounds regardless of how many seasons/categories/results the rider has —
  the No-N+1 acceptance criterion (proven in ``tests/test_riders_career.py``
  via ``CaptureQueriesContext``).

* Slug values come from ``core.slug.rider_slug`` ONLY (F3 byte-identical copy
  of ``backend/app/slug.py``) — never recomputed in S4. ``build_rider_ref``
  (F3 ``api/schemas/common.py``) does the slug computation; this module
  imports ``rider_slug`` only for the slug-MATCH key (career/profile lookup),
  exactly as ``backend/app/api/riders.py`` did.

* The response is built with the F3 common refs + the S4
  ``api/schemas/riders.py`` schemas; the pinned renderer
  (``api/renderers.py``) makes the bytes byte-identical to the parity oracle.
  The iteration here mirrors ``backend/app/api/riders.py`` line-for-line so
  the JSON shape + ordering match byte-for-byte.
"""

from __future__ import annotations

from typing import Annotated, Optional

from ninja import Query, Router
from ninja.errors import HttpError

from api.deps import YearPath, resolve_season
from api.schemas.common import (
    CategoryRef,
    EventRef,
    SeasonRef,
    build_rider_ref,
)
from api.schemas.riders import (
    GlobalRiderSearchOut,
    RiderCareerOut,
    RiderCareerSeasonOut,
    RiderDisambigEntryOut,
    RiderDisambigOut,
    RiderProfileOut,
    RiderResultOut,
    RiderSearchOut,
    RiderSearchResultOut,
)
from core.models import Category, EventResult, Rider
from core.services.rider import get_rider_profile, riders_sharing_number
from core.services.standings import get_standings
from core.slug import rider_slug

router = Router()

career_router = Router()


# Query-param constraints mirroring the FastAPI ``Query(...)`` declarations in
# ``backend/app/api/riders.py``. Ninja validates these BEFORE the handler runs
# and emits the same 422 Pydantic-error body the FastAPI app does for a
# missing / too-long ``q`` or an out-of-range ``limit``.
CareerSlugQ = Annotated[str, Query(min_length=1, max_length=128)]
SearchQ = Annotated[str, Query(min_length=1, max_length=64)]
SearchLimit = Annotated[int, Query(ge=1, le=50)]


@career_router.get("/career", response=RiderCareerOut)
def get_rider_career(
    request, slug: CareerSlugQ
) -> RiderCareerOut:
    """GET /api/riders/career — multi-season career view (P3 #17).

    Port of ``backend/app/api/riders.py::get_rider_career``. Byte-parity:
    same path, same query-param constraint, same response schema + field
    order, same aggregation + sort, same 404 string.

    Match key is the computed slug (``first-last-number``, lowercased,
    spaces→hyphens). Every Rider row whose computed slug equals the query is
    grouped by (season_year, category) and aggregated.

    Why slug, not (race_number, name)? A rider can change race numbers
    between seasons but the name stays. Slug is the most stable identifier we
    have without explicit person-IDs.

    Edge: two unrelated people with identical names will collide. Acceptable
    in practice for this domain.
    """
    needle = slug.strip().lower()

    # Pull every Rider whose computed slug matches. The slug isn't stored, so
    # we filter in Python after loading the rows. ``select_related`` JOINs
    # season + category in the ONE base query (the FastAPI source used
    # ``selectinload(Rider.season)`` / ``selectinload(Rider.category)``); the
    # No-N+1 fan-out guard for the per-rider results is the
    # ``prefetch_related`` below.
    candidates = list(
        Rider.objects.select_related("season", "category").prefetch_related(
            "results__event"
        )
    )
    matching = [
        r
        for r in candidates
        if rider_slug(r.first_name, r.last_name, r.race_number) == needle
    ]
    if not matching:
        raise HttpError(404, f"No rider found with slug '{slug}'")

    # Aggregate per (season, category). One rider can race in multiple
    # categories within a season (rare); each is a separate row. Standings
    # are cached per (season_id, category_id) — a rider can only appear once
    # per (season, category), but the cache also avoids recomputing if
    # ``matching`` happens to include duplicates.
    standings_cache: dict[tuple[int, int], list] = {}

    rows: list[RiderCareerSeasonOut] = []
    for rider in matching:
        result_rows = list(rider.results.all())
        if not result_rows:
            continue
        # Group results by event so multi-day weekends count as ONE race for
        # races_participated, but their points sum (matches our standings
        # policy in core/services/standings.py).
        per_event: dict[int, list[EventResult]] = {}
        for r in result_rows:
            per_event.setdefault(r.event_id, []).append(r)
        races_participated = len(per_event)
        total_points = sum(float(r.points or 0) for r in result_rows)
        positions_with_value = [
            r.position for r in result_rows if r.position is not None
        ]
        best_position = (
            min(positions_with_value) if positions_with_value else None
        )

        per_event_results = _collapse_event_results(rider.category, per_event)

        # Look up the rider's general-classification rank in the season
        # standings. Same get_standings the leaderboard endpoint uses, so the
        # number matches what /results shows (S2 hub — consumed, not
        # reimplemented).
        cache_key = (rider.season_id, rider.category_id)
        if cache_key not in standings_cache:
            standings_cache[cache_key] = get_standings(
                rider.season, rider.category
            )
        final_position = next(
            (
                sr.final_position
                for sr in standings_cache[cache_key]
                if sr.rider.id == rider.id
            ),
            None,
        )

        rows.append(
            RiderCareerSeasonOut(
                season_year=rider.season.year,
                race_number=rider.race_number,
                category=CategoryRef.model_validate(rider.category),
                team=rider.team,
                bike=rider.bike,
                final_position=final_position,
                races_participated=races_participated,
                total_points=total_points,
                best_position=best_position,
                results=per_event_results,
            )
        )

    rows.sort(key=lambda r: (-r.season_year, r.category.sort_order))

    rep = matching[0]
    return RiderCareerOut(
        slug=rider_slug(rep.first_name, rep.last_name, rep.race_number),
        first_name=rep.first_name,
        last_name=rep.last_name,
        seasons=rows,
    )


@career_router.get("/search", response=GlobalRiderSearchOut)
def search_riders_global(
    request,
    q: SearchQ,
    limit: SearchLimit = 10,
) -> GlobalRiderSearchOut:
    """GET /api/riders/search — cross-season rider search.

    Port of ``backend/app/api/riders.py::search_riders_global``. Byte-parity:
    same tokenization (whitespace-AND across tokens, each token ORs across
    first_name / last_name / race_number), same dedup-by-slug, same ranking,
    same response schema + field order.

    Results are deduped by computed slug — riders who raced multiple seasons
    appear once with their most recent (year, category). UI links to
    /rider/{slug}, which is multi-season by design, so showing every
    (year, category) row would just be noise.
    """
    needle = q.strip()
    if not needle:
        return GlobalRiderSearchOut(query=q, results=[])

    base_qs = Rider.objects.select_related("category", "season")

    from django.db.models import Q

    # Build the (AND across tokens, OR within token) filter exactly like the
    # FastAPI ``and_(*[or_(ilike, ilike, race_number==int)])``.
    tokens = needle.split()
    combined = Q()
    for t in tokens:
        pat = t.lower()
        or_q = Q(first_name__icontains=pat) | Q(last_name__icontains=pat)
        try:
            or_q |= Q(race_number=int(t))
        except ValueError:
            pass
        combined &= or_q

    rows = list(base_qs.filter(combined))

    # Dedup by slug, keep the entry with the highest (most recent) year. Slug
    # includes race_number, so the same person who changed numbers between
    # seasons appears as multiple rows here — that's intentional (we have no
    # person_id to merge them, and the alternative would quietly hide one
    # identity behind another).
    by_slug: dict[str, Rider] = {}
    for rider in rows:
        slug = rider_slug(
            rider.first_name, rider.last_name, rider.race_number
        )
        existing = by_slug.get(slug)
        if existing is None or rider.season.year > existing.season.year:
            by_slug[slug] = rider

    needle_lower = needle.lower()

    # KNOWN, DOCUMENTED, PARITY-SAFE DIVERGENCE (surfaced to I1 — the exact
    # pattern S2 established for the per-row ``events`` array order). The
    # FastAPI source's ``_rank`` returns ``(tier, -season.year,
    # last_name.lower())`` with NO category/race-number final break, and its
    # ``select(Rider, Category).join(...)`` has NO ``ORDER BY``. So when a
    # rider races multiple categories in the SAME season (e.g. #255 in both
    # ``profi`` and ``expert``), both rows have an IDENTICAL ``_rank`` key and
    # Python's stable sort preserves whatever unspecified Postgres heap order
    # the join happened to yield — a storage artifact that is stable per-DB
    # but differs between two "identically seeded" DBs (``bgx_oracle`` vs
    # ``bgx_django``). It is NOT a behavior contract: the frontend's search
    # dropdown links to ``/rider/{slug}`` (multi-season by design — the
    # category shown is incidental). The honest, parity-faithful resolution
    # (mirrors S2's ``Prefetch`` calendar-order pin + the S2 parity
    # assertion's order normalization): pin a DETERMINISTIC, semantically
    # meaningful final break — the canonical category order
    # (``category.sort_order``, then ``category.id``) used everywhere else in
    # the API (disambig, S1 detail, S3 detail) — so the new app's output is
    # stable + meaningful, and the parity test normalizes ONLY this one
    # non-semantic divergence before the byte compare.
    def _rank(rider: Rider) -> tuple[int, int, str, int, int]:
        season = rider.season
        # Tier 1: exact race_number for digit-only queries.
        if needle.isdigit() and rider.race_number == int(needle):
            tier = 0
        elif rider.last_name.lower().startswith(needle_lower):
            tier = 1
        elif rider.first_name.lower().startswith(needle_lower):
            tier = 2
        else:
            tier = 3
        # Within a tier, prefer most recent season (negate so ascending sort
        # picks the higher year first), then alphabetical by last name, then
        # the deterministic canonical category order (the documented
        # divergence resolution — see the comment above).
        return (
            tier,
            -season.year,
            rider.last_name.lower(),
            rider.race_number,
            rider.category.sort_order,
            rider.category.id,
        )

    chosen = sorted(by_slug.values(), key=_rank)[:limit]

    results = [
        RiderSearchResultOut(
            rider=build_rider_ref(rider),
            category=CategoryRef.model_validate(rider.category),
            season_year=rider.season.year,
        )
        for rider in chosen
    ]
    return GlobalRiderSearchOut(query=q, results=results)


@router.get("/{year}/riders/search", response=RiderSearchOut)
def search_riders(
    request,
    year: YearPath,
    q: SearchQ,
    limit: SearchLimit = 10,
) -> RiderSearchOut:
    """GET /api/seasons/{year}/riders/search — per-season fuzzy search.

    Port of ``backend/app/api/riders.py::search_riders``. Byte-parity: same
    tokenization, same ranking heuristic, same response schema + field order.

    Case-insensitive substring match on first_name, last_name, race_number.
    Returns at most ``limit`` results, ranked by best-match heuristic:
      1. exact race_number match (numeric query) first;
      2. then last_name prefix match;
      3. then first_name prefix match;
      4. then everything else.
    """
    season = resolve_season(year)

    needle = q.strip()
    if not needle:
        return RiderSearchOut(
            season=SeasonRef.model_validate(season), query=q, results=[]
        )

    from django.db.models import Q

    # Tokenize on whitespace and AND across tokens so "Илиян Кръстев" matches
    # a rider whose first_name has "Илиян" AND last_name has "Кръстев". Each
    # token still ORs across (first_name, last_name, race_number) so users
    # can mix names with race numbers, e.g. "169 Кръстев".
    tokens = needle.split()
    combined = Q()
    for t in tokens:
        pat = t.lower()
        or_q = Q(first_name__icontains=pat) | Q(last_name__icontains=pat)
        try:
            or_q |= Q(race_number=int(t))
        except ValueError:
            pass
        combined &= or_q

    candidates = list(
        Rider.objects.filter(season_id=season.id)
        .select_related("category")
        .filter(combined)
    )

    # Rank: see docstring above.
    needle_lower = needle.lower()

    # KNOWN, DOCUMENTED, PARITY-SAFE DIVERGENCE (surfaced to I1 — same pattern
    # as the global search above + S2's per-row ``events`` order). The FastAPI
    # ``_rank`` returns only ``(tier, last_name.lower())`` and its query has
    # NO ``ORDER BY``, so a rider racing multiple categories in this season
    # (e.g. #255 in ``profi`` + ``expert``) yields rows with an IDENTICAL key;
    # Python's stable sort then preserves an unspecified Postgres heap order
    # that differs between two identically-seeded DBs. Resolution (mirrors S2
    # exactly): pin the deterministic canonical category order
    # (``category.sort_order``, then ``category.id``) as the final stable
    # break; the parity test normalizes ONLY this one non-semantic divergence
    # before the byte compare. Every other observable field is byte-identical.
    def _rank(rider: Rider) -> tuple[int, str, int, int, int]:
        if needle.isdigit() and rider.race_number == int(needle):
            tier = 0
        elif rider.last_name.lower().startswith(needle_lower):
            tier = 1
        elif rider.first_name.lower().startswith(needle_lower):
            tier = 2
        else:
            tier = 3
        return (
            tier,
            rider.last_name.lower(),
            rider.race_number,
            rider.category.sort_order,
            rider.category.id,
        )

    candidates.sort(key=_rank)
    candidates = candidates[:limit]

    results = [
        RiderSearchResultOut(
            rider=build_rider_ref(rider),
            category=CategoryRef.model_validate(rider.category),
            season_year=season.year,
        )
        for rider in candidates
    ]
    return RiderSearchOut(
        season=SeasonRef.model_validate(season),
        query=q,
        results=results,
    )


@router.get("/{year}/riders/{race_number}", response=RiderDisambigOut)
def list_riders_sharing_number(
    request,
    year: YearPath,
    race_number: int,
) -> RiderDisambigOut:
    """GET /api/seasons/{year}/riders/{race_number} — disambiguation list.

    Port of ``backend/app/api/riders.py::list_riders_sharing_number``.
    Byte-parity: same response schema + field order, same category ordering,
    same 404 string.

    Returns every (first, last) pair sharing ``race_number`` in this season.
    Use case: when multiple people race with the same number (common when a
    number is shared across categories or reissued), the frontend shows a
    disambiguation page before resolving to a singular rider.
    """
    season = resolve_season(year)

    pairs = riders_sharing_number(season, race_number)
    if not pairs:
        raise HttpError(
            404,
            f"No rider with number {race_number} in season {season.year}",
        )

    # For each (first, last), gather one representative Rider (any category)
    # plus the set of categories they race in.
    candidates: list[RiderDisambigEntryOut] = []
    for first, last in pairs:
        riders_for_person = list(
            Rider.objects.filter(
                season_id=season.id,
                race_number=race_number,
                first_name=first,
                last_name=last,
            ).select_related("category")
        )
        if not riders_for_person:
            continue
        # Use the first non-empty team/bike row as the representative.
        rider_ref = build_rider_ref(
            _pick_representative_rider(riders_for_person)
        )
        categories = sorted(
            {r.category for r in riders_for_person},
            key=lambda c: (c.sort_order, c.id),
        )
        candidates.append(
            RiderDisambigEntryOut(
                rider=rider_ref,
                categories=[
                    CategoryRef.model_validate(c) for c in categories
                ],
            )
        )

    return RiderDisambigOut(
        season=SeasonRef.model_validate(season),
        race_number=race_number,
        candidates=candidates,
    )


@router.get("/{year}/riders/{race_number}/{slug}", response=RiderProfileOut)
def get_rider(
    request,
    year: YearPath,
    race_number: int,
    slug: str,
) -> RiderProfileOut:
    """GET /api/seasons/{year}/riders/{race_number}/{slug} — singular profile.

    Port of ``backend/app/api/riders.py::get_rider``. Byte-parity: same
    response schema + field order, same row construction, same 404 strings.

    Resolves the rider matching (season, race_number, slug) to a full
    profile. 404 if the race_number doesn't exist in the season, the slug
    doesn't match any (first, last) pair with that number, or the rider has
    no results.
    """
    season = resolve_season(year)

    pairs = riders_sharing_number(season, race_number)
    if not pairs:
        raise HttpError(
            404,
            f"No rider with number {race_number} in season {season.year}",
        )

    match: Optional[tuple[str, str]] = None
    for first, last in pairs:
        if rider_slug(first, last, race_number) == slug.lower():
            match = (first, last)
            break

    if match is None:
        raise HttpError(
            404,
            f"Rider #{race_number} with slug '{slug}' not found in season "
            f"{season.year}",
        )

    profile = get_rider_profile(
        season, race_number, match[0], match[1]
    )
    if profile is None:
        raise HttpError(404, "Rider has no recorded results")

    # Build a representative RiderRef using the slug computed by
    # core.slug.rider_slug (NEVER recomputed elsewhere). get_rider_profile
    # returns a dataclass; fabricate a lightweight RiderRef shim exactly as
    # the FastAPI router did.
    rider_ref = _build_rider_ref_from_profile(profile)

    results_out = [
        RiderResultOut(
            event=EventRef.model_validate(r.event),
            category=CategoryRef.model_validate(r.category),
            position=r.position,
            points=r.points,
            time_ms=r.time_ms,
            gap_ms=r.gap_ms,
            gps_penalty_ms=r.gps_penalty_ms,
            laps=r.laps,
        )
        for r in profile.results
    ]

    return RiderProfileOut(
        season=SeasonRef.model_validate(season),
        rider=rider_ref,
        categories=[
            CategoryRef.model_validate(c) for c in profile.categories
        ],
        results=results_out,
        total_events=profile.total_events,
    )


def _pick_representative_rider(riders: list[Rider]) -> Rider:
    """Prefer an ORM Rider with non-null team and bike; fall back to first.

    Byte-identical to ``backend/app/api/riders.py::_pick_representative_rider``.
    """
    for r in riders:
        if r.team and r.bike:
            return r
    for r in riders:
        if r.team or r.bike:
            return r
    return riders[0]


def _build_rider_ref_from_profile(profile):
    """Convert ``RiderProfile`` dataclass to a ``RiderRef`` schema.

    Byte-identical to
    ``backend/app/api/riders.py::_build_rider_ref_from_profile``. The slug
    comes from ``core.slug.rider_slug`` ONLY (F3 byte-identical copy of
    ``backend/app/slug.py``) — never recomputed.
    """
    from api.schemas.common import RiderRef

    return RiderRef(
        race_number=profile.race_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        slug=rider_slug(
            profile.first_name, profile.last_name, profile.race_number
        ),
        team=profile.team,
        bike=profile.bike,
    )


def _collapse_event_results(
    category: Category,
    per_event: dict[int, list[EventResult]],
) -> list[RiderResultOut]:
    """Collapse multi-day rows per event into one RiderResultOut, sum
    points/time, sort by event.sort_order.

    Byte-identical to ``backend/app/api/riders.py::_collapse_event_results``.
    """
    out: list[RiderResultOut] = []
    for day_rows in per_event.values():
        event = day_rows[0].event

        points_vals = [
            float(r.points) for r in day_rows if r.points is not None
        ]
        points = sum(points_vals) if points_vals else None

        positions = [
            r.position for r in day_rows if r.position is not None
        ]
        position = min(positions) if positions else None

        def _sum(field: str, rows: list[EventResult] = day_rows) -> Optional[int]:
            vals = [
                getattr(r, field)
                for r in rows
                if getattr(r, field) is not None
            ]
            return sum(vals) if vals else None

        out.append(
            RiderResultOut(
                event=EventRef.model_validate(event),
                category=CategoryRef.model_validate(category),
                position=position,
                points=points,
                time_ms=_sum("time_ms"),
                gap_ms=_sum("gap_ms"),
                gps_penalty_ms=_sum("gps_penalty_ms"),
                laps=_sum("laps"),
            )
        )
    out.sort(key=lambda r: r.event.sort_order)
    return out
