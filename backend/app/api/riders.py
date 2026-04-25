"""Rider endpoints.

- GET /api/seasons/{year}/riders/search?q=…             → fuzzy match (P3 #16)
- GET /api/seasons/{year}/riders/{race_number}          → disambiguation list (1+ candidates)
- GET /api/seasons/{year}/riders/{race_number}/{slug}   → singular rider profile
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.deps import get_season, get_session
from app.schemas.common import (
    CategoryRef,
    EventRef,
    SeasonRef,
    build_rider_ref,
)
from app.schemas.riders import (
    RiderDisambigEntryOut,
    RiderDisambigOut,
    RiderProfileOut,
    RiderResultOut,
    RiderSearchOut,
    RiderSearchResultOut,
)
from app.slug import rider_slug
from src.db.models import Category, Rider, Season
from src.services.rider import (
    get_rider_profile,
    riders_sharing_number,
)

router = APIRouter(prefix="/api/seasons", tags=["riders"])


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

    pattern = f"%{needle.lower()}%"
    base_q = (
        select(Rider, Category)
        .join(Category, Rider.category_id == Category.id)
        .where(Rider.season_id == season.id)
    )

    # Build the OR — if needle parses as int, also match race_number.
    conditions = [
        Rider.first_name.ilike(pattern),
        Rider.last_name.ilike(pattern),
    ]
    try:
        rn = int(needle)
        conditions.append(Rider.race_number == rn)
    except ValueError:
        pass

    candidates = list(session.execute(base_q.where(or_(*conditions))).all())

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
        if rider_slug(first, last) == slug.lower():
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
        slug=rider_slug(profile.first_name, profile.last_name),
        team=profile.team,
        bike=profile.bike,
    )
