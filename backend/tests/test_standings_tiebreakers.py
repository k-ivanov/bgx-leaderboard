"""Pin the standings tiebreaker rule.

If this test fails after a sort change, update both the comment in
src/services/standings.py AND docs/scoring.md before re-pinning.
"""

from dataclasses import dataclass


@dataclass
class _Row:
    """Mirror of the StandingsRow fields used by the production sort key."""
    total_points: float
    imputed_only: bool
    best_position: int
    total_inverse_position: float
    races_participated: int
    race_number: int


def _key(r: _Row) -> tuple[float, bool, int, float, int, int]:
    """Mirror of the sort key in src/services/standings.py.

    Negation on total_inverse_position and races_participated because
    higher = better, and we sort ascending on the tuple.
    """
    return (
        -r.total_points,
        r.imputed_only,
        r.best_position,
        -r.total_inverse_position,
        -r.races_participated,
        r.race_number,
    )


def test_higher_points_wins():
    a = _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=5.0, races_participated=5, race_number=1)
    b = _Row(total_points=99,  imputed_only=False, best_position=1,
             total_inverse_position=5.0, races_participated=5, race_number=2)
    assert sorted([a, b], key=_key) == [a, b]


def test_real_finisher_beats_dnf_only_with_better_imputed_position():
    """The bug from #878 МИРЧЕВ vs #600 ГЕЧОВ: a rider with two real
    23rd-place finishes (best_position=23, imputed_only=False) must
    rank above a rider who never finished anything (best_position=21
    imputed from 0 points, imputed_only=True). The imputed_only slot
    fires before best_position so the real finisher always wins."""
    gechov = _Row(total_points=0, imputed_only=False, best_position=23,
                  total_inverse_position=0.722, races_participated=2, race_number=600)
    mirchev = _Row(total_points=0, imputed_only=True, best_position=21,
                   total_inverse_position=0.0, races_participated=1, race_number=878)
    assert sorted([mirchev, gechov], key=_key) == [gechov, mirchev]


def test_better_best_position_breaks_ties_within_finisher_tier():
    a = _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=5.0, races_participated=5, race_number=10)
    b = _Row(total_points=100, imputed_only=False, best_position=2,
             total_inverse_position=5.0, races_participated=5, race_number=1)
    assert sorted([b, a], key=_key) == [a, b]


def test_inverse_position_sum_breaks_ties():
    """Worked example from the design doc — 60-rider field, three
    riders all at 0 pts, all with explicit finishes. Z (5 mid-pack
    races) > X (3 better races) > Y (5 worse races)."""
    x = _Row(total_points=0, imputed_only=False, best_position=21,
             total_inverse_position=1.80, races_participated=3, race_number=10)
    y = _Row(total_points=0, imputed_only=False, best_position=21,
             total_inverse_position=0.92, races_participated=5, race_number=20)
    z = _Row(total_points=0, imputed_only=False, best_position=21,
             total_inverse_position=2.75, races_participated=5, race_number=30)
    assert sorted([x, y, z], key=_key) == [z, x, y]


def test_more_races_breaks_ties_among_dnf_only_riders():
    """The bug from #39 МАНОЛОВ vs #181 МАРЧЕВ: both 0 pts, both
    imputed_only=True (every entry was a DNF), both with
    total_inverse_position=0. The rider who entered MORE races (3
    DNFs) should rank above the one who entered fewer (1 DNF).
    Without races_participated in the chain, race_number alone
    decides — and 39 < 181 makes the wrong rider win."""
    manolov = _Row(total_points=0, imputed_only=True, best_position=21,
                   total_inverse_position=0.0, races_participated=1, race_number=39)
    marchev = _Row(total_points=0, imputed_only=True, best_position=21,
                   total_inverse_position=0.0, races_participated=3, race_number=181)
    assert sorted([manolov, marchev], key=_key) == [marchev, manolov]


def test_race_number_is_final_stable_break():
    a = _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=5.0, races_participated=5, race_number=3)
    b = _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=5.0, races_participated=5, race_number=7)
    assert sorted([b, a], key=_key) == [a, b]


def test_realistic_full_chain():
    """A realistic mixed group exercising every link in the chain."""
    rows = [
        # 80 pts — loses on points first.
        _Row(total_points=80, imputed_only=False, best_position=2,
             total_inverse_position=4.0, races_participated=5, race_number=99),
        # 100 pts, real best=2, decent shadow — same tier as the next two.
        _Row(total_points=100, imputed_only=False, best_position=2,
             total_inverse_position=4.0, races_participated=5, race_number=1),
        # 100 pts, real best=1, lower shadow — wins best_position vs above.
        _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=2.0, races_participated=6, race_number=2),
        # 100 pts, real best=1, higher shadow — beats above on shadow.
        _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=4.0, races_participated=4, race_number=3),
    ]
    sorted_rows = sorted(rows, key=_key)
    # Expected order:
    #   1st: 100pt, best=1, inv=4.0, num=3   (highest points; best best_pos; highest inv)
    #   2nd: 100pt, best=1, inv=2.0, num=2   (same points/best, lower inv)
    #   3rd: 100pt, best=2, inv=4.0, num=1   (same points, worse best_pos)
    #   4th:  80pt, best=2, inv=4.0, num=99  (fewer points)
    assert [r.race_number for r in sorted_rows] == [3, 2, 1, 99]
