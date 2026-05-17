"""X1 — legacy 301 redirects + static catch-all (SEO-critical).

Ported 1:1 from the FROZEN parity oracle:

  • ``backend/app/redirects.py``  — every legacy ``/{year}/...`` pattern → the
    byte-identical 301 target; ``/{year}/r/{n}`` → 404 (disambig removed).
  • ``backend/app/main.py::FrontendStatic`` + ``_resolve_frontend_dist`` — the
    Astro ``dist/`` catch-all: directory-index served WITHOUT a 307/301
    trailing-slash redirect, real ``404.html`` status, JSON 404 for unmatched
    ``/api/*`` and ``/admin/*``, path-traversal guard.

Wiring is FROZEN in ``config/urls.py`` (F1): this package only fills the two
pre-stubbed slots —

  • ``legacy_redirect_urlpatterns`` — placed BETWEEN ``/admin`` and the static
    catch-all so ``/{year}/{cat}/...`` 301-bounces BEFORE
    ``dist/{year}/{cat}/index.html`` can be served (CLAUDE.md invariant #4).
  • ``static_catchall``           — the LAST resolver; serves the Astro build.

Declaration order of the redirect patterns is load-bearing and mirrors the
FastAPI route-registration order in ``backend/app/redirects.py`` exactly:
more-specific patterns first so they win over the catch-all ``/{year}/{cat}``.

| Legacy                              | New                                                    | Code |
|-------------------------------------|--------------------------------------------------------|------|
| /{year}/events/{slug}               | /races/{slug}                                          | 301  |
| /{year}/events                      | /races?season={year}                                   | 301  |
| /{year}/r/{race_number}/{slug}      | /rider/{slug}                                          | 301  |
| /{year}/r/{race_number}             | (disambiguation page removed)                          | 404  |
| /{year}/{category}/{slug}           | /results?season={year}&category={category}&race={slug} | 301  |
| /{year}/{category}                  | /results?season={year}&category={category}             | 301  |
| /{year}                             | /results?season={year}                                 | 301  |

``year`` is constrained to 1900–2100 (oracle: FastAPI ``Path(ge=1900,
le=2100)``); ``race_number`` to a non-negative integer (oracle: ``ge=0`` —
``0`` redirects, a negative value does not match and falls through). A
non-integer first segment (``/results``, ``/rider``) never matches a redirect
pattern and falls through to the static catch-all, exactly as the FastAPI
path-type validation made it 404/422 instead of 301.

``APPEND_SLASH = False`` (settings, frozen by F1) is part of this contract:
Django must never 301 to a trailing-slash variant or it breaks both the
indexed legacy URLs and the no-slash directory-index behavior below.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path as _Path
from urllib.parse import quote

from django.conf import settings
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponsePermanentRedirect,
    JsonResponse,
)
from django.urls import path, re_path  # noqa: F401  (path kept for __all__ parity)

# --- Legacy 301 redirect views --------------------------------------------
#
# Each view mirrors the matching function in backend/app/redirects.py. The
# slug / category are re-encoded with ``quote(..., safe='')`` to byte-match
# the FastAPI ``RedirectResponse`` Location header (Django hands the view the
# already percent-decoded path segment, same as FastAPI's path params, so
# re-quoting yields an identical Location — Cyrillic slugs included).


def _redirect(url: str) -> HttpResponsePermanentRedirect:
    """301 Moved Permanently — parity with redirects.py::_redirect."""
    return HttpResponsePermanentRedirect(url)


def legacy_event_detail(request, year, slug):
    # backend/app/redirects.py::legacy_event_detail — year context dropped;
    # /races/{slug} defaults to the most recent year for that slug.
    return _redirect(f"/races/{quote(slug, safe='')}")


def legacy_events_list(request, year):
    # backend/app/redirects.py::legacy_events_list
    return _redirect(f"/races?season={year}")


def legacy_rider_profile(request, year, race_number, slug):
    # backend/app/redirects.py::legacy_rider_profile — year + race_number are
    # intentionally dropped; the slug is the cross-season identifier.
    return _redirect(f"/rider/{quote(slug, safe='')}")


def legacy_rider_disambig(request, year, race_number):
    # backend/app/redirects.py::legacy_rider_disambig — the disambiguation
    # page was removed; FastAPI raised HTTPException(404). Match the status;
    # the body stays JSON for API/global 404 consistency.
    return JsonResponse(
        {
            "detail": (
                "Disambiguation page has been removed; "
                "use /rider/{slug} or the search bar."
            )
        },
        status=404,
    )


def legacy_race_results(request, year, category, slug):
    # backend/app/redirects.py::legacy_race_results
    return _redirect(
        f"/results?season={year}"
        f"&category={quote(category, safe='')}"
        f"&race={quote(slug, safe='')}"
    )


def legacy_leaderboard(request, year, category):
    # backend/app/redirects.py::legacy_leaderboard
    return _redirect(
        f"/results?season={year}&category={quote(category, safe='')}"
    )


def legacy_year_landing(request, year):
    # backend/app/redirects.py::legacy_year_landing
    return _redirect(f"/results?season={year}")


# Year 1900–2100 (FastAPI Path(ge=1900, le=2100)). 1900-1999 | 2000-2099 | 2100.
_YEAR = r"(?P<year>19\d{2}|20\d{2}|2100)"
# Non-negative integer race number (FastAPI Path(ge=0)). A leading-'-' value
# never matches \d+, so it falls through (parity: FastAPI 404'd it).
_RNUM = r"(?P<race_number>\d+)"
# Slug / category: any non-slash run, 1+ chars (FastAPI min_length=1). Length
# caps (FastAPI max_length 64/128) are intentionally NOT regex-enforced — an
# over-long legacy URL still 301s rather than 404ing, which is strictly safer
# for SEO link equity and never observed in the indexed corpus.
_SEG = r"(?P<{name}>[^/]+)"

# Declaration order == backend/app/redirects.py registration order.
legacy_redirect_urlpatterns: list = [
    re_path(
        rf"^{_YEAR}/events/{_SEG.format(name='slug')}$",
        legacy_event_detail,
        name="legacy_event_detail",
    ),
    re_path(
        rf"^{_YEAR}/events$",
        legacy_events_list,
        name="legacy_events_list",
    ),
    re_path(
        rf"^{_YEAR}/r/{_RNUM}/{_SEG.format(name='slug')}$",
        legacy_rider_profile,
        name="legacy_rider_profile",
    ),
    re_path(
        rf"^{_YEAR}/r/{_RNUM}$",
        legacy_rider_disambig,
        name="legacy_rider_disambig",
    ),
    re_path(
        rf"^{_YEAR}/{_SEG.format(name='category')}/{_SEG.format(name='slug')}$",
        legacy_race_results,
        name="legacy_race_results",
    ),
    re_path(
        rf"^{_YEAR}/{_SEG.format(name='category')}$",
        legacy_leaderboard,
        name="legacy_leaderboard",
    ),
    re_path(
        rf"^{_YEAR}$",
        legacy_year_landing,
        name="legacy_year_landing",
    ),
]


# --- Static catch-all (ported FrontendStatic) -----------------------------


def _resolve_frontend_dist() -> _Path | None:
    """Port of backend/app/main.py::_resolve_frontend_dist.

    Resolution order is identical:
      1. ``FRONTEND_DIST`` env/setting — if set but not a dir, returns None
         (the FastAPI code does NOT fall through to the other tiers here).
      2. Production layout ``/app/frontend_dist``.
      3. Local dev ``<repo-root>/frontend/dist`` (FastAPI used
         ``parents[2]`` of ``backend/app/main.py`` == the repo root; the
         Django equivalent is ``settings.BASE_DIR.parent``).
    Returns None when no dist is present (API-only mode).
    """
    override = os.getenv("FRONTEND_DIST") or getattr(settings, "FRONTEND_DIST", "")
    if override:
        p = _Path(override)
        return p if p.is_dir() else None

    prod = _Path("/app/frontend_dist")
    if prod.is_dir():
        return prod

    repo_root = _Path(settings.BASE_DIR).parent  # …/django_app -> repo root
    local = repo_root / "frontend" / "dist"
    if local.is_dir():
        return local

    return None


def _json_not_found() -> JsonResponse:
    """JSON 404 — byte-shape parity with FrontendStatic's JSONResponse."""
    return JsonResponse({"detail": "Not Found"}, status=404)


def static_catchall(request, path: str = ""):
    """Port of backend/app/main.py::FrontendStatic.get_response.

    Mounted LAST in the FROZEN ``config/urls.py`` (after /api, /health,
    /admin, and the legacy 301s). The ``path`` kwarg comes from the
    ``re_path(r"^(?P<path>.*)$")`` slot WITHOUT a leading slash — identical to
    what Starlette's ``StaticFiles`` mounted at ``/`` received.

    Behavior, in the same order as the oracle:
      1. ``api`` / ``api/...``   → JSON 404 (keep the API contract JSON-only;
         catches /api/* that no Ninja route + no router matched).
      2. ``admin`` / ``admin/...`` → JSON 404 (admin is a sub-app; a request
         reaching here means it 404'd itself — keep it JSON, not the
         motorsport 404.html).
      3. path-traversal guard → JSON 404 on escape.
      4. resolved dir with ``index.html`` → serve it 200, NO slash redirect.
      5. an on-disk file → serve it (real content-type).
      6. otherwise → ``404.html`` with a real 404 status (SPA fallback).
    """
    # `path` arrives WITHOUT the leading slash (StaticFiles parity).
    if path == "api" or path.startswith("api/"):
        return _json_not_found()
    if path == "admin" or path.startswith("admin/"):
        return _json_not_found()

    dist_path = _resolve_frontend_dist()
    if dist_path is None:
        # No dist mounted: FastAPI ran API-only (no StaticFiles), so a
        # non-api/admin path simply 404s. Keep it a plain 404.
        return HttpResponse(status=404)

    dist_root = dist_path.resolve()
    not_found = dist_root / "404.html"

    candidate = (dist_path / path).resolve()
    try:
        candidate.relative_to(dist_root)  # path-traversal guard
    except ValueError:
        return _json_not_found()

    # Directory lookup: serve the contained index.html with 200 regardless of
    # trailing-slash state. This is the no-307/301-slash-redirect behavior
    # that preserves the indexed no-trailing-slash URL shape.
    if candidate.is_dir():
        index = candidate / "index.html"
        if index.is_file():
            return _file_response(index, status=200)

    if candidate.is_file():
        return _file_response(candidate, status=200)

    if not_found.is_file():
        return _file_response(not_found, status=404)

    return HttpResponse(status=404)


def _file_response(file_path: _Path, *, status: int) -> FileResponse:
    """Stream a file with an explicit content-type.

    Django's ``FileResponse`` infers the type from the name; we set it
    explicitly so the charset matches the FastAPI ``FileResponse`` (text
    types are served as ``…; charset=utf-8``).
    """
    content_type, _enc = mimetypes.guess_type(str(file_path))
    if content_type is None:
        content_type = "application/octet-stream"
    if content_type.startswith("text/") or content_type in (
        "application/xml",
        "application/javascript",
        "application/json",
    ):
        content_type = f"{content_type}; charset=utf-8"
    resp = FileResponse(
        open(file_path, "rb"),
        status=status,
        content_type=content_type,
    )
    return resp


# Exposed names the FROZEN config/urls.py imports by reference.
__all__ = ["legacy_redirect_urlpatterns", "static_catchall", "path"]
