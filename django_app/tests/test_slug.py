"""Pin the rider slug algorithm — ported from ``backend/tests/test_slug.py``.

``django_app/core/slug.py`` is a BYTE-FOR-BYTE copy of
``backend/app/slug.py`` (decision I4-arch=A). This file is the byte-faithful
port of the FastAPI suite's ``test_slug.py``: identical parametrized fixture
set + identical assertions, run against ``core.slug.rider_slug``. Slug
parity is part of the URL contract — any change here 404s pre-existing
``/rider/{slug}`` URLs (CLAUDE.md invariant #2). No DB needed (pure fn).
"""

import pytest

from core.slug import rider_slug


@pytest.mark.parametrize(
    "first, last, race_number, expected",
    [
        ("Ivan", "Ivanov", 39, "ivan-ivanov-39"),
        ("IVAN", "IVANOV", 39, "ivan-ivanov-39"),
        ("Ivan", "Ivanov ", 7, "ivan-ivanov-7"),
        (" Ivan ", " Ivanov ", 169, "ivan-ivanov-169"),
        ("Petar Van Der", "Berg", 22, "petar-van-der-berg-22"),
        ("João", "Silva-Costa", 1, "joão-silva-costa-1"),
        ("Пётр", "Петров", 999, "пётр-петров-999"),
        ("Ivan  ", "  Double Space", 0, "ivan-double-space-0"),
    ],
)
def test_rider_slug_matches_pinned_algorithm(
    first: str, last: str, race_number: int, expected: str,
) -> None:
    assert rider_slug(first, last, race_number) == expected


def test_rider_slug_is_stable_for_identical_inputs() -> None:
    """Repeated calls with identical inputs must return identical output."""
    a = rider_slug("Ivan", "Ivanov", 191)
    b = rider_slug("Ivan", "Ivanov", 191)
    assert a == b == "ivan-ivanov-191"


def test_rider_slug_differs_for_different_people() -> None:
    assert rider_slug("Ivan", "Ivanov", 1) != rider_slug("Marin", "Marinov", 1)


def test_rider_slug_disambiguates_same_name_different_number() -> None:
    """The whole reason race_number is in the slug: two strangers who share
    a name must get different URLs."""
    assert rider_slug("Иван", "Иванов", 191) != rider_slug("Иван", "Иванов", 226)


def test_rider_slug_changes_with_race_number_across_seasons() -> None:
    """A rider who changes number between seasons fragments into separate
    profiles. Acceptable — without a person_id the dashboard can't know
    whether a number change means same person or different."""
    assert rider_slug("Илиян", "Манолов", 39) == "илиян-манолов-39"
    assert rider_slug("Илиян", "Манолов", 17) == "илиян-манолов-17"


def test_core_slug_is_byte_identical_to_backend_slug() -> None:
    """``core/slug.py`` MUST be a byte-for-byte copy of ``backend/app/slug.py``.

    Locks decision I4-arch=A in code: a future drift (whitespace, a comment,
    a logic tweak) fails CI here, not silently as 404s in production.
    """
    import hashlib
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    backend_slug = (repo_root / "backend" / "app" / "slug.py").read_bytes()
    core_slug = (repo_root / "django_app" / "core" / "slug.py").read_bytes()
    assert hashlib.sha256(core_slug).hexdigest() == hashlib.sha256(
        backend_slug
    ).hexdigest(), (
        "core/slug.py drifted from backend/app/slug.py — the slug contract "
        "must stay byte-identical (CLAUDE.md invariant #2)."
    )
