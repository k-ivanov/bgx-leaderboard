"""Pin the rider slug algorithm (eng-review CQ-1 / N4).

Any change here creates 404s on pre-existing URLs. Don't touch without
a redirect-table plan.
"""

import pytest

from app.slug import rider_slug


@pytest.mark.parametrize(
    "first, last, expected",
    [
        ("Ivan", "Ivanov", "ivan-ivanov"),
        ("IVAN", "IVANOV", "ivan-ivanov"),
        ("Ivan", "Ivanov ", "ivan-ivanov"),
        (" Ivan ", " Ivanov ", "ivan-ivanov"),
        ("Petar Van Der", "Berg", "petar-van-der-berg"),
        ("João", "Silva-Costa", "joão-silva-costa"),
        ("Пётр", "Петров", "пётр-петров"),
        ("Ivan  ", "  Double Space", "ivan-double-space"),
    ],
)
def test_rider_slug_matches_pinned_algorithm(first: str, last: str, expected: str) -> None:
    assert rider_slug(first, last) == expected


def test_rider_slug_is_stable_for_identical_inputs() -> None:
    """Repeated calls with identical inputs must return identical output."""
    a = rider_slug("Ivan", "Ivanov")
    b = rider_slug("Ivan", "Ivanov")
    assert a == b == "ivan-ivanov"


def test_rider_slug_differs_for_different_people() -> None:
    assert rider_slug("Ivan", "Ivanov") != rider_slug("Marin", "Marinov")
