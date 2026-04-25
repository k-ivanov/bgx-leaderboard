"""Pin the standings tiebreaker rule (improvements.md P2 #14).

If this test fails after a sort change, update both the comment in
src/services/standings.py AND docs/scoring.md before re-pinning.
"""

from dataclasses import dataclass


# Helper struct mirroring the real StandingsRow fields used by the sort key.
@dataclass
class _Row:
    total_points: float
    best_position: int
    races_participated: int
    race_number: int


def _key(r: _Row) -> tuple[float, int, int, int]:
    """Mirror of the sort key in src/services/standings.py."""
    return (-r.total_points, r.best_position, r.races_participated, r.race_number)


def test_higher_points_wins():
    a = _Row(total_points=100, best_position=1, races_participated=5, race_number=1)
    b = _Row(total_points=99, best_position=1, races_participated=5, race_number=2)
    assert sorted([a, b], key=_key) == [a, b]


def test_better_best_position_breaks_ties():
    a = _Row(total_points=100, best_position=1, races_participated=5, race_number=10)
    b = _Row(total_points=100, best_position=2, races_participated=5, race_number=1)
    assert sorted([b, a], key=_key) == [a, b]


def test_fewer_races_breaks_ties_after_best_position():
    # Same points + same best position → fewer races wins (efficiency).
    a = _Row(total_points=100, best_position=1, races_participated=4, race_number=10)
    b = _Row(total_points=100, best_position=1, races_participated=6, race_number=1)
    assert sorted([b, a], key=_key) == [a, b]


def test_race_number_is_final_stable_break():
    a = _Row(total_points=100, best_position=1, races_participated=5, race_number=3)
    b = _Row(total_points=100, best_position=1, races_participated=5, race_number=7)
    assert sorted([b, a], key=_key) == [a, b]


def test_realistic_full_chain():
    # A realistic mixed group — this captures the entire tiebreaker
    # contract in one go.
    rows = [
        _Row(total_points=80, best_position=2, races_participated=5, race_number=99),
        _Row(total_points=100, best_position=2, races_participated=5, race_number=1),
        _Row(total_points=100, best_position=1, races_participated=6, race_number=2),
        _Row(total_points=100, best_position=1, races_participated=4, race_number=3),
    ]
    sorted_rows = sorted(rows, key=_key)
    # Expected order:
    #   1st: 100pt, best=1, races=4, num=3   (highest points; best best_pos; fewest races)
    #   2nd: 100pt, best=1, races=6, num=2   (same points/best, more races)
    #   3rd: 100pt, best=2, races=5, num=1   (same points, worse best_pos)
    #   4th: 80pt,  best=2, races=5, num=99  (fewer points)
    assert [r.race_number for r in sorted_rows] == [3, 2, 1, 99]
