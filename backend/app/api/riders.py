"""Rider endpoints.

- GET /api/seasons/{year}/riders/search?q=…             → fuzzy match (P3 #16)
- GET /api/seasons/{year}/riders/{race_number}          → disambiguation list (1+ candidates)
- GET /api/seasons/{year}/riders/{race_number}/{slug}   → singular rider profile
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_season, get_session
from app.schemas.common import (
    CategoryRef,
    EventRef,
    SeasonRef,
    build_rider_ref,
)
from app.schemas.riders import (
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
from app.slug import rider_slug
from src.db.models import Category, EventResult, Rider, Season
from src.services.rider import (
    get_rider_profile,
    riders_sharing_number,
)

router = APIRouter(prefix="/api/seasons", tags=["riders"])

career_router = APIRouter(prefix="/api/riders", tags=["riders"])


@career_router.get(
    "/career",
    response_model=RiderCareerOut,
)
def get_rider_career(
    slug: str = Query(..., min_length=1, max_length=128),
    session: Session = Depends(get_session),
) -> RiderCareerOut:
    """Multi-season career view for a rider (P3 #17).

    Match key is the computed slug (`first-last`, lowercased,
    spaces→hyphens). Every Rider row whose computed slug equals the
    query is grouped by (season_year, category) and aggregated.

    Why slug, not (race_number, name)? A rider can change race numbers
    between seasons but the name stays. Slug is the most stable
    identifier we have without explicit person-IDs.

    Edge: two unrelated people with identical names will collide.
    Acceptable in practice for this domain.
    """
    needle = slug.strip().lower()

    # Pull every Rider whose computed slug matches. The slug isn't
    # stored, so we filter in Python after a name-based prefilter.
    candidates = list(
        session.execute(
            select(Rider)
            .options(selectinload(Rider.season), selectinload(Rider.category))
        ).scalars()
    )
    matching = [
        r for r in candidates
        if rider_slug(r.first_name, r.last_name, r.race_number) == needle
    ]
    if not matching:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rider found with slug '{slug}'",
        )

    # Aggregate per (season, category). One rider can race in multiple
    # categories within a season (rare); each is a separate row.
    rows: list[RiderCareerSeasonOut] = []
    for rider in matching:
        result_rows = list(
            session.execute(
                select(EventResult)
                .where(EventResult.rider_id == rider.id)
                .options(selectinload(EventResult.event))
            ).scalars()
        )
        if not result_rows:
            continue
        # Group results by event so multi-day weekends count as ONE race
        # for races_participated, but their points sum (matches our
        # standings policy in src/services/standings.py).
        per_event: dict[int, list[EventResult]] = {}
        for r in result_rows:
            per_event.setdefault(r.event_id, []).append(r)
        races_participated = len(per_event)
        total_points = sum(
            float(r.points or 0) for r in result_rows
        )
        positions_with_value = [
            r.position for r in result_rows if r.position is not None
        ]
        best_position = min(positions_with_value) if positions_with_value else None

        per_event_results = _collapse_event_results(rider.category, per_event)

        rows.append(
            RiderCareerSeasonOut(
                season_year=rider.season.year,
                race_number=rider.race_number,
                category=CategoryRef.model_validate(rider.category),
                team=rider.team,
                bike=rider.bike,
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


@career_router.get(
    "/search",
    response_model=GlobalRiderSearchOut,
)
def search_riders_global(
    q: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    session: Session = Depends(get_session),
) -> GlobalRiderSearchOut:
    """Cross-season rider search.

    Same tokenization rules as the per-season endpoint above (whitespace-
    AND across tokens, each token ORs across first_name / last_name /
    race_number). Results are deduped by computed slug — riders who
    raced multiple seasons appear once with their most recent
    (year, category). UI links to /rider/{slug}, which is multi-season
    by design, so showing every (year, category) row would just be noise.
    """
    needle = q.strip()
    if not needle:
        return GlobalRiderSearchOut(query=q, results=[])

    base_q = (
        select(Rider, Category, Season)
        .join(Category, Rider.category_id == Category.id)
        .join(Season, Rider.season_id == Season.id)
    )
    tokens = needle.split()
    per_token = []
    for t in tokens:
        pat = f"%{t.lower()}%"
        or_terms = [Rider.first_name.ilike(pat), Rider.last_name.ilike(pat)]
        try:
            or_terms.append(Rider.race_number == int(t))
        except ValueError:
            pass
        per_token.append(or_(*or_terms))

    rows = list(session.execute(base_q.where(and_(*per_token))).all())

    # Dedup by slug, keep the entry with the highest (most recent) year.
    # Slug now includes race_number, so the same person who changed numbers
    # between seasons appears as multiple rows here — that's intentional
    # (we have no person_id to merge them, and the alternative would
    # quietly hide one identity behind another).
    by_slug: dict[str, tuple[Rider, Category, Season]] = {}
    for rider, cat, season in rows:
        slug = rider_slug(rider.first_name, rider.last_name, rider.race_number)
        existing = by_slug.get(slug)
        if existing is None or season.year > existing[2].year:
            by_slug[slug] = (rider, cat, season)

    needle_lower = needle.lower()

    def _rank(triple: tuple[Rider, Category, Season]) -> tuple[int, int, str]:
        rider, _cat, season = triple
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
        # picks the higher year first), then alphabetical by last name.
        return (tier, -season.year, rider.last_name.lower())

    chosen = sorted(by_slug.values(), key=_rank)[:limit]

    results = [
        RiderSearchResultOut(
            rider=build_rider_ref(rider),
            category=CategoryRef.model_validate(cat),
            season_year=season.year,
        )
        for rider, cat, season in chosen
    ]
    return GlobalRiderSearchOut(query=q, results=results)


@router.get(
    "/{year}/riders/search",
    response_model=RiderSearchOut,
)
def search_riders(
    q: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(10, ge=1, le=50),
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> RiderSearchOut:
    """Case-insensitive substring match on first_name, last_name, race_number.

    Returns at most `limit` results, ranked by best-match heuristic:
      1. exact race_number match (numeric query) first;
      2. then last_name prefix match;
      3. then first_name prefix match;
      4. then everything else.
    """
    needle = q.strip()
    if not needle:
        return RiderSearchOut(season=SeasonRef.model_validate(season), query=q, results=[])

    base_q = (
        select(Rider, Category)
        .join(Category, Rider.category_id == Category.id)
        .where(Rider.season_id == season.id)
    )

    # Tokenize on whitespace and AND across tokens so "Илиян Кръстев" matches
    # a rider whose first_name has "Илиян" AND last_name has "Кръстев". Each
    # token still ORs across (first_name, last_name, race_number) so users
    # can mix names with race numbers, e.g. "169 Кръстев".
    tokens = needle.split()
    per_token = []
    for t in tokens:
        pat = f"%{t.lower()}%"
        or_terms = [Rider.first_name.ilike(pat), Rider.last_name.ilike(pat)]
        try:
            or_terms.append(Rider.race_number == int(t))
        except ValueError:
            pass
        per_token.append(or_(*or_terms))

    candidates = list(session.execute(base_q.where(and_(*per_token))).all())

    # Rank: see docstring above.
    needle_lower = needle.lower()
    def _rank(pair: tuple[Rider, Category]) -> tuple[int, str]:
        rider, _cat = pair
        if needle.isdigit() and rider.race_number == int(needle):
            return (0, rider.last_name.lower())
        if rider.last_name.lower().startswith(needle_lower):
            return (1, rider.last_name.lower())
        if rider.first_name.lower().startswith(needle_lower):
            return (2, rider.last_name.lower())
        return (3, rider.last_name.lower())

    candidates.sort(key=_rank)
    candidates = candidates[:limit]

    results = [
        RiderSearchResultOut(
            rider=build_rider_ref(rider),
            category=CategoryRef.model_validate(cat),
            season_year=season.year,
        )
        for rider, cat in candidates
    ]
    return RiderSearchOut(
        season=SeasonRef.model_validate(season),
        query=q,
        results=results,
    )


@router.get(
    "/{year}/riders/{race_number}",
    response_model=RiderDisambigOut,
)
def list_riders_sharing_number(
    race_number: int = Path(..., ge=0),
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> RiderDisambigOut:
    """Returns every (first, last) pair sharing ``race_number`` in this season.

    Use case: when multiple people race with the same number (common when a
    number is shared across categories or reissued), the frontend shows a
    disambiguation page before resolving to a singular rider.
    """
    pairs = riders_sharing_number(session, season, race_number)
    if not pairs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rider with number {race_number} in season {season.year}",
        )

    # For each (first, last), gather one representative Rider (any category)
    # plus the set of categories they race in.
    candidates: list[RiderDisambigEntryOut] = []
    for first, last in pairs:
        riders_for_person = list(
            session.execute(
                select(Rider)
                .where(
                    Rider.season_id == season.id,
                    Rider.race_number == race_number,
                    Rider.first_name == first,
                    Rider.last_name == last,
                )
                .options(selectinload(Rider.category))
            ).scalars()
        )
        if not riders_for_person:
            continue
        # Use the first row as the "representative" for RiderRef (team/bike fallback).
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
                categories=[CategoryRef.model_validate(c) for c in categories],
            )
        )

    return RiderDisambigOut(
        season=SeasonRef.model_validate(season),
        race_number=race_number,
        candidates=candidates,
    )


@router.get(
    "/{year}/riders/{race_number}/{slug}",
    response_model=RiderProfileOut,
)
def get_rider(
    race_number: int = Path(..., ge=0),
    slug: str = Path(..., min_length=1),
    season: Season = Depends(get_season),
    session: Session = Depends(get_session),
) -> RiderProfileOut:
    """Resolves the rider matching (season, race_number, slug) to a full profile.

    404 if the race_number doesn't exist in the season, the slug doesn't match any
    (first, last) pair with that number, or the rider has no results.
    """
    pairs = riders_sharing_number(session, season, race_number)
    if not pairs:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No rider with number {race_number} in season {season.year}",
        )

    match: Optional[tuple[str, str]] = None
    for first, last in pairs:
        if rider_slug(first, last, race_number) == slug.lower():
            match = (first, last)
            break

    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rider #{race_number} with slug '{slug}' not found in season {season.year}",
        )

    profile = get_rider_profile(session, season, race_number, match[0], match[1])
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rider has no recorded results",
        )

    # Build a representative RiderRef using the real Rider ORM (with team/bike).
    # get_rider_profile returns a dataclass; fabricate a lightweight shim.
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
        categories=[CategoryRef.model_validate(c) for c in profile.categories],
        results=results_out,
        total_events=profile.total_events,
    )


def _pick_representative_rider(riders: list[Rider]) -> Rider:
    """Prefer an ORM Rider with non-null team and bike; fall back to first."""
    for r in riders:
        if r.team and r.bike:
            return r
    for r in riders:
        if r.team or r.bike:
            return r
    return riders[0]


def _build_rider_ref_from_profile(profile) -> "RiderRef":  # type: ignore[name-defined]
    """Convert ``RiderProfile`` dataclass to a ``RiderRef`` schema."""
    from app.schemas.common import RiderRef

    return RiderRef(
        race_number=profile.race_number,
        first_name=profile.first_name,
        last_name=profile.last_name,
        slug=rider_slug(profile.first_name, profile.last_name, profile.race_number),
        team=profile.team,
        bike=profile.bike,
    )


def _collapse_event_results(
    category: Category,
    per_event: dict[int, list[EventResult]],
) -> list[RiderResultOut]:
    """Collapse multi-day rows per event into one RiderResultOut, sum points/time, sort by event.sort_order."""
    out: list[RiderResultOut] = []
    for day_rows in per_event.values():
        event = day_rows[0].event

        points_vals = [float(r.points) for r in day_rows if r.points is not None]
        points = sum(points_vals) if points_vals else None

        positions = [r.position for r in day_rows if r.position is not None]
        position = min(positions) if positions else None

        def _sum(field: str, rows: list[EventResult] = day_rows) -> Optional[int]:
            vals = [getattr(r, field) for r in rows if getattr(r, field) is not None]
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
