"""Pin the rider slug algorithm.

Slug format: ``{first}-{last}-{race_number}``, lowercased, spaces → hyphens.

Includes race_number on purpose — the same first+last name appears across
multiple identities in the dataset (Иван ИВАНОВ has 4 distinct race numbers).
Without the number, all of them would collide on a single URL.

Any change here creates 404s on pre-existing URLs. Don't touch without a
redirect-table plan.
"""

import pytest

from app.slug import rider_slug


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
