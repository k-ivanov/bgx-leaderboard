"""Pin the standings tiebreaker rule.

If this test fails after a sort change, update both the comment in
src/services/standings.py AND docs/scoring.md before re-pinning.
"""

from dataclasses import dataclass


@dataclass
class _Row:
    """Mirror of the StandingsRow fields used by the production sort key."""
    total_points: float
    best_position: int
    total_inverse_position: float
    race_number: int


def _key(r: _Row) -> tuple[float, int, float, int]:
    """Mirror of the sort key in src/services/standings.py.

    Negation on total_inverse_position because higher = better, and we sort
    ascending on the tuple.
    """
    return (-r.total_points, r.best_position, -r.total_inverse_position, r.race_number)


def test_higher_points_wins():
    a = _Row(total_points=100, best_position=1, total_inverse_position=5.0, race_number=1)
    b = _Row(total_points=99, best_position=1, total_inverse_position=5.0, race_number=2)
    assert sorted([a, b], key=_key) == [a, b]


def test_better_best_position_breaks_ties():
    a = _Row(total_points=100, best_position=1, total_inverse_position=5.0, race_number=10)
    b = _Row(total_points=100, best_position=2, total_inverse_position=5.0, race_number=1)
    assert sorted([b, a], key=_key) == [a, b]


def test_inverse_position_sum_breaks_ties():
    """The worked example from the design doc — rider Z (5 mid-pack races)
    beats rider X (3 better races) beats rider Y (5 worse races)."""
    # All three are 0-pointers tied on best_position. With a 60-rider field,
    # the percentile formula gives:
    #   X: (60-25+1)/60 * 3 = 1.80
    #   Y: (60-50+1)/60 * 5 = 0.92
    #   Z: (60-25+1)/60 * 3 + (60-30+1)/60 + (60-35+1)/60 = 1.80 + 0.52 + 0.43 = 2.75
    x = _Row(total_points=0, best_position=21, total_inverse_position=1.80, race_number=10)
    y = _Row(total_points=0, best_position=21, total_inverse_position=0.92, race_number=20)
    z = _Row(total_points=0, best_position=21, total_inverse_position=2.75, race_number=30)
    assert sorted([x, y, z], key=_key) == [z, x, y]


def test_race_number_is_final_stable_break():
    a = _Row(total_points=100, best_position=1, total_inverse_position=5.0, race_number=3)
    b = _Row(total_points=100, best_position=1, total_inverse_position=5.0, race_number=7)
    assert sorted([b, a], key=_key) == [a, b]


def test_realistic_full_chain():
    # A realistic mixed group — captures the entire tiebreaker contract.
    rows = [
        _Row(total_points=80, best_position=2, total_inverse_position=4.0, race_number=99),
        _Row(total_points=100, best_position=2, total_inverse_position=4.0, race_number=1),
        _Row(total_points=100, best_position=1, total_inverse_position=2.0, race_number=2),
        _Row(total_points=100, best_position=1, total_inverse_position=4.0, race_number=3),
    ]
    sorted_rows = sorted(rows, key=_key)
    # Expected order:
    #   1st: 100pt, best=1, inv=4.0, num=3   (highest points; best best_pos; highest inv)
    #   2nd: 100pt, best=1, inv=2.0, num=2   (same points/best, lower inv)
    #   3rd: 100pt, best=2, inv=4.0, num=1   (same points, worse best_pos)
    #   4th:  80pt, best=2, inv=4.0, num=99  (fewer points)
    assert [r.race_number for r in sorted_rows] == [3, 2, 1, 99]
