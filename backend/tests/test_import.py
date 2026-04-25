"""Pin import_race_day._split_name behavior.

Particularly the defensive trailing-time-token strip (P0 #4).
"""

import pytest

from scripts.import_race_day import _split_name


@pytest.mark.parametrize(
    ("full", "expected_first", "expected_last"),
    [
        # Normal case: first name + Bulgarian uppercase last name.
        ("Станислав КИРИЛОВ", "Станислав", "КИРИЛОВ"),
        # Multi-word first name.
        ("Жан-Пол ИВАНОВ", "Жан-Пол", "ИВАНОВ"),
        # Latin name.
        ("Alexander STRACKE", "Alexander", "STRACKE"),
        # No uppercase last name → fall back to last token.
        ("ivan ivanov", "ivan", "ivanov"),
    ],
)
def test_split_name_basic(full, expected_first, expected_last):
    first, last = _split_name(full)
    assert first == expected_first
    assert last == expected_last


@pytest.mark.parametrize(
    ("full", "expected_first", "expected_last"),
    [
        # Trailing race time leaks in from a misaligned CSV cell.
        ("Георги ГЕОРГИЕВ 3:34:40.7", "Георги", "ГЕОРГИЕВ"),
        ("Иван ПЕТРОВ 1:02:03", "Иван", "ПЕТРОВ"),
        ("Mark JONES 12:34:56.123", "Mark", "JONES"),
        # Multiple trailing times — strip all of them.
        ("Иван ПЕТРОВ 1:02:03 2:34:56", "Иван", "ПЕТРОВ"),
    ],
)
def test_split_name_strips_trailing_time(full, expected_first, expected_last):
    first, last = _split_name(full)
    assert first == expected_first
    assert last == expected_last


def test_split_name_empty_after_strip():
    """If the cell is JUST a time, return empty (caller should skip the row)."""
    first, last = _split_name("1:02:03")
    assert first == ""
    assert last == ""
