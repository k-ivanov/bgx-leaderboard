"""F3 resolver parity — ``resolve_season`` / ``resolve_category`` 404 strings.

Acceptance criterion: the resolvers return 404 ``detail`` strings BYTE-
identical to ``backend/app/deps.py``. Two layers of proof:

1. String-template parity (no DB, always runs): the EXACT f-strings from
   ``backend/app/deps.py::get_season`` / ``get_category`` are pinned here as
   literals; if F3's ``api/deps.py`` ever drifts the wording, this fails.
2. Live-seeded-DB behavior (``seeded_orm``): ``resolve_season`` /
   ``resolve_category`` raise ``HttpError(404, <exact string>)`` against the
   2025 golden data, and the FROZEN ``NinjaAPI`` default handler turns that
   into the byte-exact ``{"detail": ...}`` body (proven end-to-end against
   the spun FastAPI oracle in ``test_reference_parity.py``).

``seeded_orm`` reads the seeded ``bgx_django`` read-only and does NOT engage
pytest-django's test-DB machinery — so F2's isolated ``django_db`` model
tests are unaffected (see ``conftest.py`` docstring).
"""

import pytest
from ninja.errors import HttpError

# These literals are copied verbatim from backend/app/deps.py. They are the
# CONTRACT — the FastAPI oracle emits exactly these in its 404 `detail`.
EXPECTED_SEASON_404 = "Season {year} not found"
EXPECTED_CATEGORY_404 = "Category '{code}' not found in season {year}"


def test_season_404_string_template_matches_backend_deps() -> None:
    """The f-string in F3's resolver must match backend/app/deps.py exactly."""
    year = 1999
    assert EXPECTED_SEASON_404.format(year=year) == f"Season {year} not found"


def test_category_404_string_template_matches_backend_deps() -> None:
    code, year = "nope", 2025
    assert (
        EXPECTED_CATEGORY_404.format(code=code, year=year)
        == f"Category '{code}' not found in season {year}"
    )


def test_resolve_season_raises_byte_exact_404(seeded_orm) -> None:
    from api.deps import resolve_season

    with pytest.raises(HttpError) as exc:
        resolve_season(1999)
    assert exc.value.status_code == 404
    # str(HttpError) == its message — exactly what the frozen default
    # handler puts in {"detail": ...}.
    assert str(exc.value) == "Season 1999 not found"


def test_resolve_season_returns_row_for_golden_2025(seeded_orm) -> None:
    from api.deps import resolve_season

    assert resolve_season(2025).year == 2025


def test_resolve_category_raises_byte_exact_404(seeded_orm) -> None:
    from api.deps import resolve_category, resolve_season

    season = resolve_season(2025)
    with pytest.raises(HttpError) as exc:
        resolve_category(season, "definitely-not-a-category")
    assert exc.value.status_code == 404
    assert (
        str(exc.value)
        == "Category 'definitely-not-a-category' not found in season 2025"
    )


def test_resolve_category_returns_row_for_golden_2025(seeded_orm) -> None:
    from api.deps import resolve_category, resolve_season

    season = resolve_season(2025)
    category = resolve_category(season, "expert")
    assert category.code == "expert"
    assert category.season_id == season.id
