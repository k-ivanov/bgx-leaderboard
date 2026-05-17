"""S2 — Standings + scoring service & router: owned test coverage.

S2 owns the scoring/standings service hub (``core/services/scoring.py`` +
``core/services/standings.py``) and the leaderboard router
(``api/standings.py`` + ``api/schemas/standings.py``). This file mirrors S1's
three-section layout (``tests/test_seasons.py``) — the auto-tiering in
``conftest.py`` keys off the ``seeded_orm`` / ``parity_rig`` fixture NAMES, so
Tier-2 marking is automatic with zero manual annotation.

1. **Contract / wiring + pure-unit algorithm** (no DB — Tier-1, always green
   in the locked venv): the leaderboard module is wired into the FROZEN
   router assembly at the right path; the response schemas have the exact
   field NAMES + ORDER + TYPES + DEFAULTS of the frozen FastAPI Pydantic
   schemas (the ``openapi-typescript`` no-diff guarantee); the service API
   exposes the exact ``events_for_season`` / ``position_from_points`` /
   ``get_standings`` names S3/S4/S7 import; and the **ported, verbatim
   algorithm** is pinned by the backend's ``test_scoring.py`` +
   ``test_standings_tiebreakers.py`` (pure Python, zero ORM coupling — they
   run in Tier-1).

2. **Behavior on golden data** (``seeded_orm`` — auto-tiered Tier-2): the
   ported ``backend/tests/test_standings_inverse_position.py`` runs the S2
   ``get_standings`` directly against the 2025 golden data.

3. **Byte-parity vs the frozen FastAPI oracle** (``parity_rig`` — auto-tiered
   Tier-2): copied from F3's ``test_reference_parity.py`` template, scoped to
   the S2 leaderboard surface. Includes the **No-N+1 query-count assertion**
   (S2 acceptance criterion) measured against the seeded ``bgx_django`` via
   ``CaptureQueriesContext``.

KNOWN ENV NOTE (carried from S1): F3's ``seeded_orm`` fixture has a
pre-existing connection-rebind bug that can ERROR under intermittent
Postgres (tracked separately, NOT an S2 bug, out of S2 scope). ``parity_rig``
is the authoritative proof here; the ``seeded_orm`` tests SKIP/ERROR cleanly
without faking a green, exactly as S1 documented.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest


# ===========================================================================
# 1a. Contract / wiring — no DB, runs in the Tier-1 locked-venv gate
# ===========================================================================


def test_standings_router_is_wired_into_frozen_assembly() -> None:
    """S2's ``router`` is the object the FROZEN ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.standings.router`` by reference and
    mounts it at ``/seasons`` (``api/__init__.py:76``). S2 fills that
    module's ``router`` — confirm exactly the one leaderboard operation is
    registered and nothing else leaked in.
    """
    from ninja import Router

    from api import standings as standings_api

    assert isinstance(standings_api.router, Router)

    paths = set(standings_api.router.path_operations.keys())
    assert paths == {"/{year}/standings/{category_code}"}, paths


def test_standings_endpoint_matches_fastapi_source_signature() -> None:
    """S2 endpoint contract mirrors ``backend/app/api/standings.py``.

    One GET operation, response schema ``StandingsOut``, the constrained
    ``year`` path param (parity with the FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` via F3 ``YearPath``) plus the
    ``category_code`` string path param (parity with ``get_category``'s
    ``category_code: str = Path(...)``).
    """
    import typing

    from api import standings as standings_api
    from api.deps import YearPath
    from api.schemas.standings import StandingsOut

    po = standings_api.router.path_operations["/{year}/standings/{category_code}"]
    (op,) = po.operations
    assert op.methods == ["GET"]
    assert op.response_models[200] is not None
    assert StandingsOut.__name__ == "StandingsOut"

    hints = typing.get_type_hints(
        standings_api.get_leaderboard, include_extras=True
    )
    assert hints["year"] is YearPath
    assert hints["category_code"] is str


def test_standings_routes_existence_through_f3_resolvers() -> None:
    """S2 must use F3 ``resolve_season`` / ``resolve_category`` — never
    hand-roll the 404 strings (they live byte-exact in F3 / ``api/deps.py``).

    This is the byte-parity contract for the two 404 paths the ported
    backend tests assert (``test_leaderboard_404_for_bad_year`` /
    ``test_leaderboard_404_for_bad_category``).
    """
    import inspect

    from api import standings as standings_api
    from api.deps import resolve_category, resolve_season

    src = inspect.getsource(standings_api.get_leaderboard)
    assert "resolve_season(" in src
    assert "resolve_category(" in src
    assert resolve_season.__module__ == "api.deps"
    assert resolve_category.__module__ == "api.deps"


def test_standings_schema_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    The pinned renderer never re-sorts keys, so JSON key order == schema
    field-declaration order. If the order drifts from
    ``backend/app/schemas/standings.py`` the frontend's
    ``openapi-typescript`` client regenerates WITH a diff. Pin it here.
    """
    from api.schemas.standings import (
        RiderEventEntryOut,
        StandingsOut,
        StandingsRowOut,
    )

    assert list(RiderEventEntryOut.model_fields) == [
        "event_slug",
        "points",
        "position",
    ]
    assert list(StandingsRowOut.model_fields) == [
        "final_position",
        "rider",
        "events",
        "total_points",
        "races_participated",
        "best_position",
        "worst_event_slug",
        "worst_dropped",
    ]
    assert list(StandingsOut.model_fields) == [
        "season",
        "category",
        "events",
        "rows",
        "championship_format",
    ]

    # Nullable fields default to None (null-safe), as in FastAPI.
    assert StandingsRowOut.model_fields["best_position"].default is None
    assert StandingsRowOut.model_fields["worst_event_slug"].default is None
    assert StandingsRowOut.model_fields["worst_dropped"].default is None


def test_standings_service_api_surface_is_stable() -> None:
    """S3/S4/S7 import this exact surface from ``core.services.standings``.

    The Django service API drops the FastAPI SQLAlchemy ``Session`` first
    arg (Django manages the connection itself) — pin the new signatures so a
    later refactor that breaks the hub fails loudly here.
    """
    import inspect

    from core.services import scoring
    from core.services import standings as svc

    assert set(svc.__all__) == {
        "position_from_points",
        "RiderEventEntry",
        "StandingsRow",
        "get_standings",
        "events_for_season",
    }
    assert set(scoring.__all__) == {
        "points_for_position",
        "EventScore",
        "compute_event_scoring",
    }
    assert list(inspect.signature(svc.get_standings).parameters) == [
        "season",
        "category",
    ]
    assert list(inspect.signature(svc.events_for_season).parameters) == [
        "season"
    ]


def test_standings_service_uses_prefetch_not_n_plus_1_source() -> None:
    """The ORM port batches results via ``prefetch_related``/``Prefetch``
    (the ``selectinload`` analogue) AND pins the deterministic calendar
    order on the prefetch.

    Source-level guard for (a) the No-N+1 acceptance criterion — a future
    edit that drops the prefetch (re-introducing per-rider result queries)
    fails here even without a DB — and (b) the deterministic resolution of
    the documented per-row events-order divergence. The runtime query-count
    proof is section 3 (``CaptureQueriesContext``).
    """
    import inspect
    import re

    from core.services import standings as svc

    # Format-tolerant: the auto-formatter may wrap calls across lines, so
    # match call tokens + args, not an exact single-line spelling.
    src = inspect.getsource(svc.get_standings)
    flat = re.sub(r"\s+", " ", src)
    assert "prefetch_related(" in flat
    assert "Prefetch(" in flat and '"results"' in flat
    # Calendar order pinned on the prefetched results (the documented,
    # deterministic resolution of the events-array-order divergence).
    assert '"event__sort_order", "event_id", "id"' in flat or \
        '"event__sort_order","event_id","id"' in flat
    # Events query keeps the byte-parity (sort_order, id) ordering too.
    assert '"sort_order", "id"' in flat or '"sort_order","id"' in flat
    # No SQLAlchemy-ism call survives in the ORM port (the inline comments
    # legitimately *name* selectinload to document the translation — guard
    # the actual CALL form ``selectinload(`` instead).
    assert "selectinload(" not in src
    assert ".options(" not in src
    assert "session" not in inspect.signature(svc.get_standings).parameters


# ===========================================================================
# 1b. Ported pure-unit algorithm — backend/tests/test_scoring.py
#     (no DB, zero ORM coupling — runs in the Tier-1 locked-venv gate)
# ===========================================================================


def _r(rider_id: int, day: int, status: str, time_ms: int | None) -> SimpleNamespace:
    """Build a fake EventResult-like row. ``compute_event_scoring`` only
    reads rider_id, day, status, time_ms — duck typing keeps the test light
    (identical to ``backend/tests/test_scoring.py::_r``)."""
    return SimpleNamespace(rider_id=rider_id, day=day, status=status, time_ms=time_ms)


def test_points_table_1day() -> None:
    from core.services.scoring import points_for_position

    assert points_for_position(1, 1) == 25
    assert points_for_position(2, 1) == 22
    assert points_for_position(20, 1) == 1
    assert points_for_position(21, 1) == 0
    assert points_for_position(None, 1) == 0


def test_points_table_2day() -> None:
    from core.services.scoring import points_for_position

    assert points_for_position(1, 2) == 40
    assert points_for_position(2, 2) == 34
    assert points_for_position(3, 2) == 30
    assert points_for_position(12, 2) == 10
    assert points_for_position(13, 2) == 8
    assert points_for_position(20, 2) == 1
    assert points_for_position(21, 2) == 0


def test_single_day_event_ranks_by_time() -> None:
    from core.services.scoring import compute_event_scoring

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
    from core.services.scoring import compute_event_scoring

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
    from core.services.scoring import compute_event_scoring

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
    from core.services.scoring import compute_event_scoring

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
    assert scores[2].points == 34
    assert scores[3].points == 30


def test_no_fin_anywhere_is_zero() -> None:
    from core.services.scoring import compute_event_scoring

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
    from core.services.scoring import compute_event_scoring

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
    from core.services.scoring import compute_event_scoring

    assert compute_event_scoring([]) == {}


def test_top_20_full_table_1day() -> None:
    from core.services.scoring import compute_event_scoring

    rows = [_r(i, 1, "FIN", i * 1000) for i in range(1, 22)]
    scores = compute_event_scoring(rows)
    expected = [25, 22, 20, 18, 16, 15, 14, 13, 12, 11, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    for i, pts in enumerate(expected, start=1):
        assert scores[i].points == pts, f"rider {i}: expected {pts}, got {scores[i].points}"


def test_top_20_full_table_2day() -> None:
    from core.services.scoring import compute_event_scoring

    rows = []
    for i in range(1, 22):
        rows.append(_r(i, 1, "FIN", i * 1000))
        rows.append(_r(i, 2, "FIN", i * 1000))
    scores = compute_event_scoring(rows)
    expected = [40, 34, 30, 27, 24, 22, 20, 18, 16, 14, 12, 10, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    for i, pts in enumerate(expected, start=1):
        assert scores[i].points == pts, f"rider {i}: expected {pts}, got {scores[i].points}"


# ===========================================================================
# 1c. Ported pure-unit tiebreaker chain — backend/tests/test_standings_tiebreakers.py
#     (no DB — pins the sort-key contract; runs in the Tier-1 gate)
# ===========================================================================


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
    """Mirror of the sort key in core/services/standings.py.

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
    """#878 МИРЧЕВ vs #600 ГЕЧОВ: a rider with two real 23rd-place finishes
    (best_position=23, imputed_only=False) must rank above a rider who never
    finished anything (best_position=21 imputed from 0 points,
    imputed_only=True). The imputed_only slot fires before best_position."""
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
    """Worked example from the design doc — 60-rider field, three riders all
    at 0 pts, all with explicit finishes. Z (5 mid-pack races) > X (3 better
    races) > Y (5 worse races)."""
    x = _Row(total_points=0, imputed_only=False, best_position=21,
             total_inverse_position=1.80, races_participated=3, race_number=10)
    y = _Row(total_points=0, imputed_only=False, best_position=21,
             total_inverse_position=0.92, races_participated=5, race_number=20)
    z = _Row(total_points=0, imputed_only=False, best_position=21,
             total_inverse_position=2.75, races_participated=5, race_number=30)
    assert sorted([x, y, z], key=_key) == [z, x, y]


def test_more_races_breaks_ties_among_dnf_only_riders():
    """#39 МАНОЛОВ vs #181 МАРЧЕВ: both 0 pts, both imputed_only=True, both
    total_inverse_position=0. The rider who entered MORE races (3 DNFs)
    should rank above the one who entered fewer (1 DNF)."""
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
        _Row(total_points=80, imputed_only=False, best_position=2,
             total_inverse_position=4.0, races_participated=5, race_number=99),
        _Row(total_points=100, imputed_only=False, best_position=2,
             total_inverse_position=4.0, races_participated=5, race_number=1),
        _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=2.0, races_participated=6, race_number=2),
        _Row(total_points=100, imputed_only=False, best_position=1,
             total_inverse_position=4.0, races_participated=4, race_number=3),
    ]
    sorted_rows = sorted(rows, key=_key)
    assert [r.race_number for r in sorted_rows] == [3, 2, 1, 99]


def test_ported_sort_key_matches_production_get_standings_key() -> None:
    """The ported ``_key`` mirror IS the production sort key.

    Pull the exact lambda out of ``get_standings`` source and assert the
    6-component tuple is byte-identical to this file's ``_key`` mirror — so
    if the production chain ever changes, this fails (parity with the
    backend's "update both" pin comment)."""
    import inspect

    from core.services import standings as svc

    src = inspect.getsource(svc.get_standings)
    for token in (
        "-r.total_points",
        "r.imputed_only",
        "r.best_position",
        "-r.total_inverse_position",
        "-r.races_participated",
        "r.rider.race_number",
    ):
        assert token in src, f"sort-key component {token!r} missing/changed"


# ===========================================================================
# 2. Behavior on the 2025 golden data — ported
#    backend/tests/test_standings_inverse_position.py
#    (``seeded_orm`` → auto-tiered Tier-2; SKIPs without seeded Postgres)
# ===========================================================================


def _resolve_cat(year: int, code: str):
    """Resolve (season, category) from the seeded ``bgx_django`` DB."""
    from core.models import Category, Season

    season = Season.objects.get(year=year)
    cat = Category.objects.get(season_id=season.id, code=code)
    return season, cat


def test_inverse_position_is_in_unit_interval_per_event(seeded_orm) -> None:
    """Every per-event contribution sits in [0, 1] (or 0 for non-finishers).

    Ported ``test_inverse_position_is_in_unit_interval_per_event``.
    """
    from core.services.standings import get_standings

    season, cat = _resolve_cat(2025, "expert")
    rows = get_standings(season, cat)
    for row in rows:
        assert 0.0 <= row.total_inverse_position <= float(row.races_participated) + 1e-9


def test_winners_have_highest_inverse_position(seeded_orm) -> None:
    """The leaderboard winner racing every event lands near the top of
    total_inverse_position too. Ported
    ``test_winners_have_highest_inverse_position``.
    """
    from core.services.standings import get_standings

    season, cat = _resolve_cat(2025, "expert")
    rows = get_standings(season, cat)
    top3_inv = [rows[i].total_inverse_position for i in range(min(3, len(rows)))]
    bottom3_inv = [
        rows[-(i + 1)].total_inverse_position for i in range(min(3, len(rows)))
    ]
    assert min(top3_inv) > max(bottom3_inv)


def test_inverse_position_is_active_tiebreaker_after_best_position(
    seeded_orm,
) -> None:
    """The new tiebreaker fires *after* best_position. Ported
    ``test_inverse_position_is_active_tiebreaker_after_best_position``.
    """
    from core.services.standings import get_standings

    season, cat = _resolve_cat(2025, "standard")
    rows = get_standings(season, cat)

    groups: dict[tuple[float, int], list] = {}
    for row in rows:
        groups.setdefault((row.total_points, row.best_position), []).append(row)

    multi_groups = [g for g in groups.values() if len(g) >= 2]
    assert multi_groups, "expected at least one (total_points, best_position) group with ties"

    violations = []
    for group in multi_groups:
        for i in range(len(group) - 1):
            a, b = group[i], group[i + 1]
            if a.total_inverse_position < b.total_inverse_position:
                violations.append(
                    f"  ranks {a.final_position}/{b.final_position}: "
                    f"inv {a.total_inverse_position:.3f} < {b.total_inverse_position:.3f} "
                    f"(both at points={a.total_points}, best_pos={a.best_position})"
                )
    assert not violations, "inverse-position tiebreaker not respected:\n" + "\n".join(violations)


def test_dnf_or_imputed_position_contributes_zero(seeded_orm) -> None:
    """Riders whose only data is imputed positions have
    total_inverse_position == 0. Ported
    ``test_dnf_or_imputed_position_contributes_zero``.
    """
    from core.services.standings import get_standings

    season, cat = _resolve_cat(2025, "standard")
    rows = get_standings(season, cat)

    riders_with_only_imputed = [
        row for row in rows
        if all(
            all(d.position is None for d in row.rider.results.all() if d.event_id == ev_id)
            for ev_id in {d.event_id for d in row.rider.results.all()}
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


# ===========================================================================
# 3. Byte-parity vs the frozen FastAPI oracle + No-N+1 — COPIED from F3's
#    tests/test_reference_parity.py template, scoped to the S2 surface.
#    (``parity_rig`` → auto-tiered Tier-2; SKIPs if both stacks cannot spin)
# ===========================================================================

# The S2 public surface. Each is a (path, note) the new Django app and the
# spun FastAPI oracle must agree on byte-for-byte. 2025 = aggregate_2025
# format (drop-worst path + worst_event_slug/worst_dropped); 2026 =
# per_event format (combined-time scoring path + real event_date refs).
STANDINGS_PATHS = [
    ("/api/seasons/2025/standings/expert",
     "aggregate_2025 — drop-worst rule, worst_* fields, Cyrillic, key order"),
    ("/api/seasons/2025/standings/standard",
     "aggregate_2025 — tiebreaker chain over a big mixed field"),
    ("/api/seasons/2026/standings/expert",
     "per_event — compute_event_scoring path + nested EventRef ISO dates"),
]


# --- The ONE documented, parity-safe divergence (surfaced to I1) -----------
# The FastAPI oracle's ``selectinload(Rider.results)`` emits
# ``SELECT … FROM event_result WHERE rider_id IN (…)`` with NO ``ORDER BY``
# (verified against SQLAlchemy's emitted SQL), so the per-row ``events``
# ARRAY ORDER in the oracle JSON is whatever Postgres heap order
# ``bgx_oracle`` physically has — an unspecified storage artifact, NOT a
# data/behavior contract: it is stable per-DB but differs between two
# "identically seeded" DBs, the Astro frontend never renders ``row.events``,
# and the typed client types it as an unordered array. The S2 service pins a
# DETERMINISTIC, semantically meaningful order (race-calendar:
# event.sort_order → event_id → id). Every OTHER observable field is
# byte-identical. Mirrors F3's documented Content-Type-charset / X1
# catch-all divergences: recorded in code with a precise repro + surfaced to
# I1, never silently absorbed and never faked green.


def _strip_documented_events_order_divergence(resp):
    """Return a response shim with each row's ``events`` array sorted by
    ``event_slug`` — factoring out ONLY the documented, non-semantic,
    parity-safe per-row events-array-order divergence so the byte compare
    proves everything else (scoring, ranking, every value) is identical."""
    from tests.parity import _HTTPResponse

    body = json.loads(resp.content)
    for row in body.get("rows", []):
        row["events"] = sorted(row["events"], key=lambda e: e["event_slug"])
    canonical = json.dumps(
        body, ensure_ascii=False, allow_nan=False, indent=None,
        separators=(",", ":"), sort_keys=False,
    ).encode("utf-8")
    return _HTTPResponse(resp.status_code, canonical, dict(resp.headers))


@pytest.mark.parametrize("path, _note", STANDINGS_PATHS)
def test_standings_endpoint_byte_parity(
    path, _note, parity_rig, assert_json_parity
) -> None:
    """S2 leaderboard == frozen FastAPI oracle, byte-for-byte, EXCEPT the one
    documented per-row ``events``-array-order divergence (see the comment
    above — non-semantic Postgres-heap artifact, surfaced to I1).

    Proves the verbatim-ported scoring/standings algorithm + the ORM
    data-fetch translation produce a JSON body byte-identical to
    ``backend/app/api/standings.py`` over identically-seeded Postgres for
    EVERY observable field (``final_position``, ``total_points``,
    ``best_position``, ``worst_*``, every per-event ``points``/``position``,
    rider, slug, the full tiebreaker ranking) — the 2025 golden parity
    acceptance criterion. ``assert_json_parity`` still runs in full (status,
    semantic JSON equality, the pinned serialization-format spec, the
    media-type prefix) on both bodies after the documented divergence is
    factored out, so a real regression anywhere else still fails loudly.
    """
    old = _strip_documented_events_order_divergence(parity_rig.old(path))
    new = _strip_documented_events_order_divergence(parity_rig.new(path))
    assert_json_parity(old, new)


@pytest.mark.parametrize("path, _note", STANDINGS_PATHS)
def test_standings_new_app_events_order_is_deterministic_calendar_order(
    path, _note, parity_rig
) -> None:
    """Pin the NEW app's resolution of the documented divergence.

    The new app does NOT inherit the oracle's unspecified heap order — it
    pins a deterministic, meaningful order: each row's ``events`` array is in
    race-calendar order (the leaderboard's top-level ``events`` array order,
    which is ``ORDER BY event.sort_order, event.id``). This records the
    contract in code so a future change that loses the ``Prefetch`` ordering
    fails here. (We assert on the NEW app only — the oracle's order is the
    artifact we deliberately do NOT reproduce.)
    """
    new = parity_rig.new(path)
    assert new.status_code == 200
    body = json.loads(new.content)
    calendar = [e["slug"] for e in body["events"]]
    rank = {slug: i for i, slug in enumerate(calendar)}
    for row in body["rows"]:
        got = [e["event_slug"] for e in row["events"]]
        expected = sorted(got, key=lambda s: rank[s])
        assert got == expected, (
            f"row #{row['rider']['race_number']} events not in calendar "
            f"order: {got} (calendar: {calendar})"
        )


def test_standings_404_bad_year_parity(parity_rig, assert_json_parity) -> None:
    """Missing season → identical 404 ``{"detail":"Season 1999 not found"}``.

    Ported ``backend/tests/test_api.py::test_leaderboard_404_for_bad_year``;
    S2 routes existence through F3 ``resolve_season``.
    """
    old = parity_rig.old("/api/seasons/1999/standings/expert")
    new = parity_rig.new("/api/seasons/1999/standings/expert")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {"detail": "Season 1999 not found"}


def test_standings_404_bad_category_parity(
    parity_rig, assert_json_parity
) -> None:
    """Missing category → identical 404
    ``{"detail":"Category 'not-a-real-category' not found in season 2025"}``.

    Ported ``test_leaderboard_404_for_bad_category``; S2 routes existence
    through F3 ``resolve_category`` (byte-exact string lives in F3).
    """
    old = parity_rig.old("/api/seasons/2025/standings/not-a-real-category")
    new = parity_rig.new("/api/seasons/2025/standings/not-a-real-category")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {
        "detail": "Category 'not-a-real-category' not found in season 2025"
    }


@pytest.mark.parametrize("bad_year", ["abc", "3000", "1800"])
def test_standings_422_validation_parity(
    bad_year, parity_rig, assert_json_parity
) -> None:
    """Out-of-range / non-int ``year`` → identical 422 Pydantic-error body.

    Proves S2's ``YearPath`` reproduces the FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` validation. Structural contract
    (status, ``{"detail":[...]}``, ``loc``, ``type``) — ``msg`` wording can
    vary microscopically across pydantic patch releases.
    """
    old = parity_rig.old(f"/api/seasons/{bad_year}/standings/expert")
    new = parity_rig.new(f"/api/seasons/{bad_year}/standings/expert")
    assert old.status_code == 422, old.content[:300]
    assert new.status_code == 422, new.content[:300]

    o = json.loads(old.content)
    n = json.loads(new.content)
    assert isinstance(o["detail"], list) and isinstance(n["detail"], list)
    o_err, n_err = o["detail"][0], n["detail"][0]
    assert list(o_err["loc"]) == list(n_err["loc"]) == ["path", "year"]
    assert o_err["type"] == n_err["type"]


def test_leaderboard_rider_slug_matches_backend_algorithm(
    parity_rig,
) -> None:
    """Ported ``test_leaderboard_rider_slug_matches_backend_algorithm``.

    Frontend consumes ``RiderRef.slug`` verbatim — verify the slug in the
    NEW app's response is exactly what ``core.slug.rider_slug`` produces (F3
    byte-identical copy of ``backend/app/slug.py``).
    """
    from core.slug import rider_slug

    new = parity_rig.new("/api/seasons/2025/standings/expert")
    assert new.status_code == 200
    body = json.loads(new.content)
    assert body["category"]["code"] == "expert"
    assert body["season"]["year"] == 2025
    assert len(body["rows"]) > 0
    assert body["rows"][0]["final_position"] == 1
    for row in body["rows"]:
        expected = rider_slug(
            row["rider"]["first_name"],
            row["rider"]["last_name"],
            row["rider"]["race_number"],
        )
        assert row["rider"]["slug"] == expected


# --- No-N+1 acceptance criterion -------------------------------------------
# S2 acceptance: "leaderboard query count within current bounds (assert in
# test)". ``get_standings`` issues a FIXED, small number of queries
# regardless of how many riders/results the category has, because the
# ``selectinload`` → ``prefetch_related("results")`` translation batches all
# related rows into ONE extra query (NOT one-per-rider). We measure the real
# count against the seeded ``bgx_django`` via ``seeded_orm`` +
# ``CaptureQueriesContext`` and assert a tight upper bound.


def test_leaderboard_no_n_plus_1_query_count(seeded_orm) -> None:
    """``get_standings`` is O(1) queries, NOT O(riders) — the No-N+1 gate.

    Expected query plan for ``get_standings(season, category)``:
      Q1  events:   ``SELECT … FROM event   WHERE season_id=…``
      Q2  riders:   ``SELECT … FROM rider   WHERE category_id=…``
      Q3  results:  ``SELECT … FROM event_result WHERE rider_id IN (…)``
                    (the ONE batched ``prefetch_related`` query — the
                     selectinload analogue, NOT a per-rider query)
    Plus the two F3 resolver lookups the router does BEFORE calling the
    service (season-by-year, category-by-code) — those are O(1) too. We
    bound the SERVICE call (the fan-out hot path) at <= 3 queries, asserting
    it does NOT scale with the (large) expert-2025 rider count.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    season, cat = _resolve_cat(2025, "expert")

    from core.services.standings import get_standings

    with CaptureQueriesContext(connection) as ctx:
        rows = get_standings(season, cat)
        # Force full materialization of the prefetch + every row's nested
        # access the router will do, so any lazy N+1 would show up here.
        for row in rows:
            _ = row.rider.race_number
            _ = list(row.events_by_slug.items())

    n_queries = len(ctx.captured_queries)
    n_riders = len(rows)
    assert n_riders > 20, (
        f"expert-2025 should be a large field (got {n_riders}); a tiny "
        f"field would make the N+1 assertion vacuous"
    )
    assert n_queries <= 3, (
        f"get_standings issued {n_queries} queries for {n_riders} riders — "
        f"expected <= 3 (events + riders + ONE batched results prefetch). "
        f"This is an N+1 regression (prefetch_related lost?).\n"
        + "\n".join(
            f"  [{i}] {q['sql'][:160]}"
            for i, q in enumerate(ctx.captured_queries)
        )
    )
