"""301 redirects from legacy per-year URLs to the new /results + /rider shape.

Mount order (eng-review A-1): registered AFTER /api routers and BEFORE
StaticFiles, so legacy paths bounce before the static-file fallback can
serve their pre-built index.html.

Mapping (frontend-restructure.md §T2):

| Legacy                                       | New                                           |
|----------------------------------------------|-----------------------------------------------|
| /{year}                                      | /results?season={year}                        |
| /{year}/{category}                           | /results?season={year}&category={category}    |
| /{year}/{category}/{slug}                    | /results?season={year}&category={category}&race={slug} |
| /{year}/events                               | /results?season={year}                        |
| /{year}/events/{slug}                        | /results?season={year}&race={slug}            |
| /{year}/r/{race_number}/{slug}               | /rider/{slug}                                 |
| /{year}/r/{race_number}                      | 404 (disambig page is removed)                |

Declaration order matters — more specific patterns are registered first
so they win over the catch-all `/{year}/{category}`.
"""

from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Path, status
from fastapi.responses import RedirectResponse

router = APIRouter(include_in_schema=False)

_PERMANENT = status.HTTP_301_MOVED_PERMANENTLY


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=_PERMANENT)


@router.get("/{year:int}/events/{slug}")
def legacy_event_detail(
    year: int = Path(..., ge=1900, le=2100),
    slug: str = Path(..., min_length=1, max_length=128),
) -> RedirectResponse:
    return _redirect(f"/results?season={year}&race={quote(slug, safe='')}")


@router.get("/{year:int}/events")
def legacy_events_list(
    year: int = Path(..., ge=1900, le=2100),
) -> RedirectResponse:
    return _redirect(f"/results?season={year}")


@router.get("/{year:int}/r/{race_number:int}/{slug}")
def legacy_rider_profile(
    year: int = Path(..., ge=1900, le=2100),
    race_number: int = Path(..., ge=0),
    slug: str = Path(..., min_length=1, max_length=128),
) -> RedirectResponse:
    # `year` and `race_number` are intentionally dropped — the slug is the
    # cross-season identifier. The new /rider page surfaces both as meta.
    return _redirect(f"/rider/{quote(slug, safe='')}")


@router.get("/{year:int}/r/{race_number:int}")
def legacy_rider_disambig(
    year: int = Path(..., ge=1900, le=2100),
    race_number: int = Path(..., ge=0),
) -> RedirectResponse:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Disambiguation page has been removed; use /rider/{slug} or the search bar.",
    )


@router.get("/{year:int}/{category}/{slug}")
def legacy_race_results(
    year: int = Path(..., ge=1900, le=2100),
    category: str = Path(..., min_length=1, max_length=64),
    slug: str = Path(..., min_length=1, max_length=128),
) -> RedirectResponse:
    return _redirect(
        f"/results?season={year}"
        f"&category={quote(category, safe='')}"
        f"&race={quote(slug, safe='')}"
    )


@router.get("/{year:int}/{category}")
def legacy_leaderboard(
    year: int = Path(..., ge=1900, le=2100),
    category: str = Path(..., min_length=1, max_length=64),
) -> RedirectResponse:
    return _redirect(
        f"/results?season={year}&category={quote(category, safe='')}"
    )


@router.get("/{year:int}")
def legacy_year_landing(
    year: int = Path(..., ge=1900, le=2100),
) -> RedirectResponse:
    return _redirect(f"/results?season={year}")
