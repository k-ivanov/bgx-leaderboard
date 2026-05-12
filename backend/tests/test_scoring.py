"""Unit tests for combined-time event scoring."""

from __future__ import annotations

from types import SimpleNamespace

from src.services.scoring import compute_event_scoring, points_for_position


def _r(rider_id: int, day: int, status: str, time_ms: int | None) -> SimpleNamespace:
    """Build a fake EventResult-like row. compute_event_scoring only reads
    rider_id, day, status, time_ms — duck typing keeps the test light."""
    return SimpleNamespace(rider_id=rider_id, day=day, status=status, time_ms=time_ms)


def test_points_table_1day() -> None:
    assert points_for_position(1, 1) == 25
    assert points_for_position(2, 1) == 22
    assert points_for_position(20, 1) == 1
    assert points_for_position(21, 1) == 0
    assert points_for_position(None, 1) == 0


def test_points_table_2day() -> None:
    assert points_for_position(1, 2) == 40
    assert points_for_position(2, 2) == 34
    assert points_for_position(3, 2) == 30
    assert points_for_position(12, 2) == 10
    assert points_for_position(13, 2) == 8
    assert points_for_position(20, 2) == 1
    assert points_for_position(21, 2) == 0


def test_single_day_event_ranks_by_time() -> None:
    rows = [
        _r(1, 1, "FIN", 5000),
        _r(2, 1, "FIN", 4000),
        _r(3, 1, "FIN", 6000),
    ]
    scores = compute_event_scoring(rows)
    assert scores[2].combined_position == 1 and scores[2].points == 25
    assert scores[1].combined_position == 2 and scores[1].points == 22
    assert scores[3].combined_position == 3 and scores[3].points == 20
    for s in scores.values():
        assert s.tier == 1


def test_two_day_full_finishers_use_40_table() -> None:
    rows = [
        _r(1, 1, "FIN", 1000), _r(1, 2, "FIN", 1000),  # combined 2000 → 1st
        _r(2, 1, "FIN", 2000), _r(2, 2, "FIN", 2000),  # combined 4000 → 2nd
        _r(3, 1, "FIN", 3000), _r(3, 2, "FIN", 3000),  # combined 6000 → 3rd
    ]
    scores = compute_event_scoring(rows)
    assert scores[1].points == 40 and scores[1].combined_position == 1 and scores[1].tier == 1
    assert scores[2].points == 34 and scores[2].combined_position == 2
    assert scores[3].points == 30 and scores[3].combined_position == 3


def test_day1_only_ranked_after_full_finishers() -> None:
    # 2 full finishers + 1 day-1-only rider. Day-1-only goes to position 3.
    rows = [
        _r(1, 1, "FIN", 1000), _r(1, 2, "FIN", 1000),
        _r(2, 1, "FIN", 2000), _r(2, 2, "FIN", 2000),
        _r(3, 1, "FIN",  500), _r(3, 2, "DNF",  None),  # fastest day 1 but no day 2
    ]
    scores = compute_event_scoring(rows)
    assert scores[1].combined_position == 1 and scores[1].tier == 1
    assert scores[2].combined_position == 2 and scores[2].tier == 1
    assert scores[3].combined_position == 3 and scores[3].tier == 2
    assert scores[3].points == 30  # 3rd on the 2-day table


def test_day1_priority_over_day2() -> None:
    # 1 full finisher, then day-1-only and day-2-only riders.
    rows = [
        _r(1, 1, "FIN", 1000), _r(1, 2, "FIN", 1000),  # full
        _r(2, 1, "FIN",  500), _r(2, 2, "DNF",  None),  # day-1 only
        _r(3, 1, "DNF",  None), _r(3, 2, "FIN",  400),  # day-2 only (faster!)
    ]
    scores = compute_event_scoring(rows)
    assert scores[1].combined_position == 1 and scores[1].tier == 1
    assert scores[2].combined_position == 2 and scores[2].tier == 2  # day-1 before day-2
    assert scores[3].combined_position == 3 and scores[3].tier == 3
    # Both partials still earn points from the 2-day table.
    assert scores[2].points == 34
    assert scores[3].points == 30


def test_no_fin_anywhere_is_zero() -> None:
    rows = [
        _r(1, 1, "FIN", 1000), _r(1, 2, "FIN", 1000),
        _r(2, 1, "DNF",  None), _r(2, 2, "DNS",  None),
    ]
    scores = compute_event_scoring(rows)
    assert scores[1].points == 40
    assert scores[2].combined_position is None
    assert scores[2].points == 0
    assert scores[2].tier is None


def test_tie_on_combined_time_shares_position() -> None:
    rows = [
        _r(1, 1, "FIN", 1000), _r(1, 2, "FIN", 2000),  # combined 3000
        _r(2, 1, "FIN", 2000), _r(2, 2, "FIN", 1000),  # combined 3000
        _r(3, 1, "FIN", 3000), _r(3, 2, "FIN", 3000),  # combined 6000
    ]
    scores = compute_event_scoring(rows)
    assert scores[1].combined_position == 1
    assert scores[2].combined_position == 1
    # Position 2 is skipped because of the tie at position 1.
    assert scores[3].combined_position == 3


def test_empty_results() -> None:
    assert compute_event_scoring([]) == {}


def test_top_20_full_table_1day() -> None:
    rows = [_r(i, 1, "FIN", i * 1000) for i in range(1, 22)]
    scores = compute_event_scoring(rows)
    expected = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    for i, pts in enumerate(expected, start=1):
        assert scores[i].points == pts, f"rider {i}: expected {pts}, got {scores[i].points}"


def test_top_20_full_table_2day() -> None:
    rows = []
    for i in range(1, 22):
        rows.append(_r(i, 1, "FIN", i * 1000))
        rows.append(_r(i, 2, "FIN", i * 1000))
    scores = compute_event_scoring(rows)
    expected = [40, 34, 30, 27, 24, 22, 20, 18, 16, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    for i, pts in enumerate(expected, start=1):
        assert scores[i].points == pts, f"rider {i}: expected {pts}, got {scores[i].points}"
