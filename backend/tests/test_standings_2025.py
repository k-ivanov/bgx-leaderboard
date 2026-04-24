"""Golden test: the standings service must exactly reproduce the 2025 CSVs.

Runs against a live Postgres. Assumes scripts.import_2025 has run (or runs it here).
"""

import csv
from pathlib import Path

import pytest
from sqlalchemy import select

from scripts.import_2025 import DEFAULT_CSV_DIR, import_2025
from src.db import get_session
from src.db.models import Category, Season
from src.seasons import CATEGORIES_2025, RACE_ORDER_2025
from src.services.standings import get_standings


@pytest.fixture(scope="module", autouse=True)
def _seed_2025():
    import_2025(DEFAULT_CSV_DIR)


def _load_csv_rows(category_code: str) -> list[dict]:
    path = DEFAULT_CSV_DIR / f"{category_code}.csv"
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


@pytest.mark.parametrize("category_code,_display", CATEGORIES_2025)
def test_standings_match_csv(category_code: str, _display: str) -> None:
    expected_rows = _load_csv_rows(category_code)

    with get_session() as session:
        season = session.execute(select(Season).where(Season.year == 2025)).scalar_one()
        category = session.execute(
            select(Category).where(
                Category.season_id == season.id, Category.code == category_code
            )
        ).scalar_one()
        standings = get_standings(session, season, category)

    by_race_number = {row.rider.race_number: row for row in standings}
    assert len(by_race_number) == len(expected_rows), (
        f"rider count mismatch for {category_code}"
    )

    for expected in expected_rows:
        race_num = int(expected["RaceNumber"])
        actual = by_race_number.get(race_num)
        assert actual is not None, f"missing rider #{race_num} in {category_code}"

        expected_total = float(expected["TotalPoints"])
        expected_participated = int(expected["RacesParticipated"])

        # Core migration invariants — the standings service must preserve
        # the CSV's total_points and races_participated exactly.
        assert actual.total_points == pytest.approx(expected_total), (
            f"{category_code} #{race_num}: total_points "
            f"actual={actual.total_points} expected={expected_total}"
        )
        assert actual.races_participated == expected_participated, (
            f"{category_code} #{race_num}: races_participated "
            f"actual={actual.races_participated} expected={expected_participated}"
        )

        # best_position and final_position are display-derived and depend
        # on per-event positions that the aggregate CSVs do not expose
        # (tied scores, non-BGX-table event scoring like six_days). We
        # track them in a separate top-of-board assertion below.

        expected_dropped_str = (expected.get("WorstResultDropped") or "").strip()
        if expected_dropped_str == "":
            assert actual.worst_dropped is None, (
                f"{category_code} #{race_num}: expected no drop, "
                f"but got dropped={actual.worst_dropped} ({actual.worst_event_slug})"
            )
        else:
            expected_dropped = float(expected_dropped_str)
            assert actual.worst_dropped == pytest.approx(expected_dropped), (
                f"{category_code} #{race_num}: worst_dropped "
                f"actual={actual.worst_dropped} expected={expected_dropped}"
            )

        for race_slug, _ in RACE_ORDER_2025:
            cell = (expected.get(f"Race_{race_slug}") or "").strip()
            if cell == "" or cell == "0":
                assert race_slug not in actual.events_by_slug, (
                    f"{category_code} #{race_num}: unexpected result for {race_slug}"
                )
            else:
                entry = actual.events_by_slug.get(race_slug)
                assert entry is not None, (
                    f"{category_code} #{race_num}: missing result for {race_slug}"
                )
                assert entry.points == pytest.approx(float(cell)), (
                    f"{category_code} #{race_num} {race_slug}: points "
                    f"actual={entry.points} expected={cell}"
                )


@pytest.mark.parametrize("category_code,_display", CATEGORIES_2025)
def test_podium_matches_csv(category_code: str, _display: str) -> None:
    """Top-3 finishers are typically unambiguous (no score ties) and serve
    as a headline regression check."""
    expected_rows = _load_csv_rows(category_code)
    expected_top3 = [
        (int(r["FinalPosition"]), int(r["RaceNumber"]))
        for r in expected_rows
        if int(r["FinalPosition"]) <= 3
    ]

    with get_session() as session:
        season = session.execute(select(Season).where(Season.year == 2025)).scalar_one()
        category = session.execute(
            select(Category).where(
                Category.season_id == season.id, Category.code == category_code
            )
        ).scalar_one()
        standings = get_standings(session, season, category)

    actual_top3 = [
        (row.final_position, row.rider.race_number)
        for row in standings
        if row.final_position <= 3
    ]
    assert actual_top3 == expected_top3, (
        f"{category_code}: podium mismatch — actual={actual_top3} expected={expected_top3}"
    )
