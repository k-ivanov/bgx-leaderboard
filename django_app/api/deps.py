"""Canonical resolvers (F3 / decision I4-arch=A).

Django Ninja has no FastAPI ``Depends``. ``backend/app/deps.py`` centralized
the per-request season/category lookups behind FastAPI dependencies; the
Django port turns them into **plain helper functions** every slice calls
explicitly from its endpoint body. This is a pattern redesign, not a literal
port — but the OBSERVABLE contract (the 404 ``detail`` strings, the status
code, the response body shape) is byte-identical to the frozen FastAPI app.

What stays identical to ``backend/app/deps.py``
-----------------------------------------------
* ``resolve_season(year)`` → the ``Season`` row, or ``HttpError(404,
  "Season {year} not found")`` — the EXACT string from
  ``backend/app/deps.py::get_season``.
* ``resolve_category(season, code)`` → the ``Category`` row, or
  ``HttpError(404, "Category '{code}' not found in season {season.year}")``
  — the EXACT string from ``backend/app/deps.py::get_category``.
* The year path-parameter range constraint ``1900 <= year <= 2999`` (the
  FastAPI ``Path(..., ge=1900, le=2999)``). Endpoints annotate the path
  param with ``YearPath`` so Ninja's Pydantic validation raises a 422 with
  the same Pydantic-v2 error-list shape FastAPI emits for an out-of-range or
  non-integer ``year`` — see the reference endpoint in ``api/seasons.py``.

Error-handler parity (no FROZEN-file edit needed)
-------------------------------------------------
The frozen ``NinjaAPI`` instance (``api/__init__.py``) installs Ninja's
DEFAULT exception handlers, which already emit the exact FastAPI contract:

  * ``HttpError(status, msg)``     → ``{"detail": msg}`` at ``status``
    (parity with FastAPI ``HTTPException(status, detail=msg)``).
  * unmatched ``/api/*`` (Http404) → ``{"detail": "Not Found"}``
    (parity with FastAPI's default 404; ``settings.DEBUG`` is False in prod
    so no ``": <exc>"`` suffix leaks — verified by the parity rig).
  * request-validation failure     → ``{"detail": [<pydantic errors>]}`` at
    422 (same Pydantic-v2 error list shape FastAPI returns for a bad/out-of-
    range path param).

So F3 does NOT need to register a custom handler (which would require
editing the FROZEN ``api/__init__.py``); it only has to (a) raise
``HttpError`` with the byte-exact detail strings and (b) prove the frozen
defaults match the oracle. The parity rig (``tests/parity.py`` +
``tests/test_reference_parity.py``) is that proof.
"""

from __future__ import annotations

from typing import Annotated

from ninja import Path
from ninja.errors import HttpError

from core.models import Category, Season

# Path-param constraint mirroring FastAPI's ``Path(..., ge=1900, le=2999)``
# in ``backend/app/deps.py::get_season``. Endpoints type their ``year`` path
# argument as ``year: YearPath`` so Ninja validates it BEFORE the handler
# runs and returns the same 422 Pydantic-error body the FastAPI app does for
# a non-integer or out-of-range year.
YearPath = Annotated[int, Path(ge=1900, le=2999)]


def resolve_season(year: int) -> Season:
    """Return the ``Season`` for ``year`` or raise a parity-exact 404.

    Port of ``backend/app/deps.py::get_season`` (sans the FastAPI ``Path``
    binding, which endpoints declare via ``YearPath``). 404 detail string is
    byte-identical: ``f"Season {year} not found"``.
    """
    try:
        return Season.objects.get(year=year)
    except Season.DoesNotExist:
        raise HttpError(404, f"Season {year} not found")


def resolve_category(season: Season, code: str) -> Category:
    """Return the ``Category`` ``code`` within ``season`` or a parity 404.

    Port of ``backend/app/deps.py::get_category``. 404 detail string is
    byte-identical:
    ``f"Category '{code}' not found in season {season.year}"``.
    """
    try:
        return Category.objects.get(season_id=season.id, code=code)
    except Category.DoesNotExist:
        raise HttpError(
            404,
            f"Category '{code}' not found in season {season.year}",
        )


__all__ = ["YearPath", "resolve_season", "resolve_category"]
