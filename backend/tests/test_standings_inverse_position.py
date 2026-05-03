"""Integration tests for the percentile-based inverse-position score.

The unit tests in test_standings_tiebreakers.py pin the sort-key contract.
This file pins the *computation* of total_inverse_position against a real
DB session — does the percentile formula land on the right number, and do
the documented edge cases (DNF, zero-pointers) behave as designed.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.db.models import Category, Season
from src.services.standings import get_standings


pytestmark = pytest.mark.usefixtures("seeded_db")


def _category(session: Session, year: int, code: str) -> tuple[Season, Category]:
    season = session.execute(select(Season).where(Season.year == year)).scalar_one()
    cat = session.execute(
        select(Category).where(Category.season_id == season.id, Category.code == code)
    ).scalar_one()
    return season, cat


def test_inverse_position_is_in_unit_interval_per_event():
    """Every per-event contribution sits in [0, 1] (or 0 for non-finishers).
    This is the basic sanity check on the formula."""
    with SessionLocal() as session:
        season, cat = _category(session, 2025, "expert")
        rows = get_standings(session, season, cat)
    # races_participated is the upper bound on the score (1.0 per event max).
    for row in rows:
        assert 0.0 <= row.total_inverse_position <= float(row.races_participated) + 1e-9


def test_winners_have_highest_inverse_position():
    """The leaderboard winner racing every event should land near the top
    of total_inverse_position too — they keep finishing 1st in big fields."""
    with SessionLocal() as session:
        season, cat = _category(session, 2025, "expert")
        rows = get_standings(session, season, cat)
    # Sorted by final_position ascending — top-of-table.
    top3_inv = [rows[i].total_inverse_position for i in range(min(3, len(rows)))]
    bottom3_inv = [
        rows[-(i + 1)].total_inverse_position for i in range(min(3, len(rows)))
    ]
    # Winners have a strictly larger sum than the bottom three. Even if the
    # bottom three have rich finish data, they didn't beat as many people.
    assert min(top3_inv) > max(bottom3_inv)


def test_inverse_position_is_active_tiebreaker_after_best_position():
    """The new tiebreaker fires *after* best_position. Within any group of
    rows tied on (total_points, best_position), total_inverse_position
    must be monotonically non-increasing — race_number is only the final
    fallback when inverse-position also ties."""
    with SessionLocal() as session:
        season, cat = _category(session, 2025, "standard")
        rows = get_standings(session, season, cat)

    # Group rows by their first two sort-key components.
    groups: dict[tuple[float, int], list] = {}
    for row in rows:
        groups.setdefault((row.total_points, row.best_position), []).append(row)

    multi_groups = [g for g in groups.values() if len(g) >= 2]
    assert multi_groups, "expected at least one (total_points, best_position) group with ties"

    violations = []
    for group in multi_groups:
        # Group is already in final_position order (rows came pre-sorted).
        for i in range(len(group) - 1):
            a, b = group[i], group[i + 1]
            if a.total_inverse_position < b.total_inverse_position:
                violations.append(
                    f"  ranks {a.final_position}/{b.final_position}: "
                    f"inv {a.total_inverse_position:.3f} < {b.total_inverse_position:.3f} "
                    f"(both at points={a.total_points}, best_pos={a.best_position})"
                )
    assert not violations, "inverse-position tiebreaker not respected:\n" + "\n".join(violations)


def test_dnf_or_imputed_position_contributes_zero():
    """Riders whose only data is imputed positions (no explicit position
    rows in the DB) should have total_inverse_position == 0. This is the
    case for many older 2025 zero-pointers depending on importer state."""
    with SessionLocal() as session:
        season, cat = _category(session, 2025, "standard")
        rows = get_standings(session, season, cat)

    # Find a rider whose every event entry got the imputed fallback (none of
    # their day-rows had explicit position). Those riders contribute 0 to
    # total_inverse_position, regardless of how many races they "ran".
    riders_with_only_imputed = [
        row for row in rows
        if all(
            all(d.position is None for d in row.rider.results if d.event_id == ev_id)
            for ev_id in {d.event_id for d in row.rider.results}
        )
        and row.races_participated > 0
    ]
    if not riders_with_only_imputed:
        pytest.skip("seeded data has explicit positions for every rider")

    for row in riders_with_only_imputed:
        assert row.total_inverse_position == 0.0, (
            f"rider {row.rider.race_number} has only imputed positions "
            f"but inverse score is {row.total_inverse_position}"
        )
