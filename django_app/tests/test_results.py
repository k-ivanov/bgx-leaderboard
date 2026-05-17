"""S7 — Results API: owned test coverage  *(added — review OV1)*.

S7 owns the per-race Results slice (``api/results.py`` +
``api/schemas/results.py``) — the endpoint the frontend's PRIMARY
``/results`` SPA island calls (``ResultsView.vue:93``). It consumes — never
reimplements — the S2 scoring service hub
(``core.services.scoring.compute_event_scoring``) and the F3 resolvers. This
file mirrors S2's / S3's three-section layout
(``tests/test_standings.py`` / ``test_events.py``) — the auto-tiering in
``conftest.py`` keys off the ``seeded_orm`` / ``parity_rig`` fixture NAMES,
so Tier-2 marking is automatic with zero manual annotation.

1. **Contract / wiring** (no DB — Tier-1, always green in the locked venv):
   the results module is wired into the FROZEN router assembly at the right
   path with the right ``tags``; the response schemas have the exact field
   NAMES + ORDER + TYPES + DEFAULTS of the frozen FastAPI Pydantic schemas
   (``backend/app/schemas/results.py`` — the ``openapi-typescript`` no-diff
   guarantee); existence is routed through the F3 ``resolve_season`` /
   ``resolve_category`` (never a hand-rolled season/category 404) and the
   race 404 string is byte-identical to ``backend/app/api/results.py``; S7
   consumes ``compute_event_scoring`` from the S2 hub (not reimplemented);
   the ranked/unranked split + tie ordering + ``ORDER BY day, id`` data
   fetch mirror the FastAPI source line-for-line.

2. **Behavior on the 2025 golden data** (``seeded_orm`` — auto-tiered
   Tier-2): the ported ``backend/tests/test_api.py:151`` Race Results
   contract assertions (``test_race_results_expert_kyrnare_2025`` /
   ``test_race_results_404_for_bad_category`` /
   ``test_race_results_404_for_bad_event``) run S7's endpoint logic directly
   against the golden data, plus a bad-year case (F3 ``resolve_season``
   ordering parity) and a multi-day per-day-breakdown shape case.

3. **Byte-parity vs the frozen FastAPI oracle** (``parity_rig`` —
   auto-tiered Tier-2): copied from F3's ``test_reference_parity.py`` /
   S2/S3's template, scoped to the S7 Race Results surface. The bodies must
   be byte-for-byte equal to ``backend/app/api/results.py`` over
   identically-seeded Postgres — single-day, multi-day (day_1/day_2 split),
   and the per_event 2026 season (real ISO event dates on the nested
   EventRef).

The Tier-2 tests (2 + 3) auto-mark ``parity`` via the
``seeded_orm`` / ``parity_rig`` fixture-name detection in ``conftest.py`` —
S7 adds NO manual marker. They SKIP (never fake green) if no seeded
Postgres / both stacks cannot be spun in the sandbox; the fixtures print the
exact command.

Parity note — NO unordered-heap divergence in S7
------------------------------------------------
Unlike S2/S4 (whose oracle ``selectinload(Rider.results)`` reverse-collection
emitted NO ``ORDER BY`` → an unspecified Postgres-heap per-row array order
that had to be normalized + surfaced to I1), the FastAPI Results source
(``backend/app/api/results.py``) uses ``selectinload(EventResult.rider)`` (a
FORWARD many-to-one — Django ``select_related``) AND an EXPLICIT,
deterministic ``ORDER BY EventResult.day, EventResult.id`` on the results
query, then re-sorts the final ``rows`` by ``(combined_position,
race_number)`` / ``race_number``. Every observable axis is deterministic in
BOTH stacks, so there is NOTHING to normalize — ``assert_json_parity`` runs
in FULL with no divergence shim. (Recorded here so a future reader does not
expect an S2-style strip helper.)
"""

from __future__ import annotations

import json

import pytest


# ===========================================================================
# 1. Contract / wiring — no DB, runs in the Tier-1 locked-venv gate
# ===========================================================================


def test_results_router_is_wired_into_frozen_assembly() -> None:
    """S7's ``router`` is the object the FROZEN ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.results.router`` by reference and
    mounts it at ``/seasons`` with ``tags=["race-results"]``
    (``api/__init__.py:78``, parity with FastAPI
    ``APIRouter(prefix="/api/seasons", tags=["race-results"])`` at
    ``backend/app/main.py:110``). S7 fills that module's ``router`` — confirm
    exactly the one Race Results operation is registered and nothing else
    leaked in.
    """
    from ninja import Router

    from api import results as results_api

    assert isinstance(results_api.router, Router)

    paths = set(results_api.router.path_operations.keys())
    assert paths == {
        "/{year}/categories/{category_code}/events/{event_slug}"
    }, paths


def test_results_endpoint_matches_fastapi_source_signature() -> None:
    """S7 endpoint contract mirrors ``backend/app/api/results.py``.

    One GET operation. ``get_race_results`` takes the constrained ``year``
    path param (parity with the FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` via F3 ``YearPath``), the
    ``category_code`` string path param (parity with the FastAPI
    ``get_category`` ``category_code: str = Path(...)``), and the
    ``event_slug`` string path param (parity with the FastAPI
    ``event_slug: str = Path(...)``).
    """
    import typing

    from api import results as results_api
    from api.deps import YearPath
    from api.schemas.results import EventResultsOut

    po = results_api.router.path_operations[
        "/{year}/categories/{category_code}/events/{event_slug}"
    ]
    (op,) = po.operations
    assert op.methods == ["GET"]
    assert op.response_models[200] is not None
    assert EventResultsOut.__name__ == "EventResultsOut"

    hints = typing.get_type_hints(
        results_api.get_race_results, include_extras=True
    )
    assert hints["year"] is YearPath
    assert hints["category_code"] is str
    assert hints["event_slug"] is str


def test_results_routes_existence_through_f3_resolvers() -> None:
    """S7 must use F3 ``resolve_season`` / ``resolve_category`` — never
    hand-roll the season/category 404.

    The season-404 + category-404 strings live byte-exact in F3
    (``api/deps.py``). The race 404 string is byte-identical to
    ``backend/app/api/results.py`` and is raised inline as
    ``HttpError(404, ...)`` (the FastAPI source did the same with
    ``HTTPException(404, detail=...)``; there is no F3 event-by-slug
    resolver — S3 ``get_race_detail`` hand-rolled it identically).
    """
    import inspect

    from api import results as results_api
    from api.deps import resolve_category, resolve_season

    src = inspect.getsource(results_api.get_race_results)

    assert "resolve_season(" in src
    assert "resolve_category(" in src
    assert resolve_season.__module__ == "api.deps"
    assert resolve_category.__module__ == "api.deps"

    # The race 404 string is byte-identical to the FastAPI source
    # (``backend/app/api/results.py``): f"Race '{event_slug}' not found in
    # season {season.year}". Pin the exact f-string + 404 status here so a
    # future edit that diverges the wording fails loudly (the ported parity
    # test in section 3 is the runtime proof). This is the SAME string S3's
    # get_race_detail uses — the two endpoints must stay in lockstep.
    assert (
        "Race '{event_slug}' not found in season {season.year}" in src
        or 'Race \'{event_slug}\' not found in season {season.year}' in src
    )
    assert "HttpError(\n            404," in src or (
        "HttpError(" in src and "404" in src
    )

    # FastAPI ``Depends(get_category)`` chains ``get_season`` FIRST, so a bad
    # year resolves to the season 404 BEFORE the category lookup. S7 must
    # call resolve_season before resolve_category to preserve that ordering.
    assert src.index("resolve_season(") < src.index("resolve_category(")


def test_results_consumes_s2_scoring_not_reimplemented() -> None:
    """S7 consumes the S2 scoring service hub — Lane D contract.

    ``compute_event_scoring`` is owned by S2 (``core.services.scoring``,
    S2's verbatim port of ``backend/src/services/scoring.py``). S7 imports +
    calls it for the combined-time scoring (parity with the FastAPI source,
    which imported ``from src.services.scoring import
    compute_event_scoring``). S7 must NOT reimplement the scoring algorithm
    in its own module.
    """
    import inspect

    from api import results as results_api
    from core.services import scoring as svc

    src = inspect.getsource(results_api)
    assert (
        "from core.services.scoring import compute_event_scoring" in src
    )
    handler_src = inspect.getsource(results_api.get_race_results)
    assert "compute_event_scoring(" in handler_src
    # The function S7 calls is the S2-owned one (Lane D: read-only consume).
    assert results_api.compute_event_scoring is svc.compute_event_scoring
    assert svc.compute_event_scoring.__module__ == "core.services.scoring"


def test_results_data_fetch_is_byte_equivalent_to_fastapi() -> None:
    """S7's ORM query mirrors the FastAPI ``select`` exactly.

    FastAPI ``get_race_results``:
      * results: join Rider, filter event_id + Rider.category_id,
        ``selectinload(EventResult.rider)`` (FORWARD m2o → select_related),
        ``order_by(EventResult.day, EventResult.id)`` (EXPLICIT,
        deterministic — NOT an unordered selectinload heap artifact).
      * grouped dict insertion order == query order;
      * final ``rows`` re-sorted ``(combined_position, race_number)`` /
        ``race_number``.
    The ``ORDER BY day, id`` + the final re-sort are observable in the JSON
    array order and the "first non-null wins" notes/cp_count picks, so they
    are part of the byte-parity contract. Assert S7's source uses the exact
    equivalents (no S2-style unordered-heap divergence here — see module
    docstring).
    """
    import inspect

    from api import results as results_api

    src = inspect.getsource(results_api.get_race_results)
    # Forward m2o eager-load → select_related (NOT prefetch_related).
    assert 'select_related("rider")' in src
    assert "prefetch_related(" not in src
    # The explicit deterministic results ordering, preserved verbatim.
    assert (
        'order_by("day", "id")' in src
        or '.order_by(\n            "day", "id"\n        )' in src
    )
    # The final ranked / unranked tie-ordering, byte-identical to FastAPI.
    assert "ranked_rows.sort(key=lambda x: (x[0], x[1].rider.race_number))" in src
    assert "unranked_rows.sort(key=lambda r: r.rider.race_number)" in src


def test_result_schemas_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    The pinned renderer never re-sorts keys (``api/renderers.py``), so JSON
    key order == schema field-declaration order. If S7's schema field order
    ever drifts from ``backend/app/schemas/results.py`` /
    ``backend/app/schemas/common.py`` the frontend's ``openapi-typescript``
    client would regenerate WITH a diff for the Race Results path. Pin the
    exact contract here.
    """
    from api.schemas.common import CategoryRef, EventRef, RiderRef, SeasonRef
    from api.schemas.results import EventResultRowOut, EventResultsOut

    # EventResultsOut field order == backend/app/schemas/results.py.
    assert list(EventResultsOut.model_fields) == [
        "season",
        "category",
        "event",
        "days",
        "rows",
    ]

    # EventResultRowOut field order == backend/app/schemas/results.py
    # EXACTLY (including the per-day breakdown ordering).
    assert list(EventResultRowOut.model_fields) == [
        "position",
        "rider",
        "points",
        "time_ms",
        "day_1_time_ms",
        "day_2_time_ms",
        "day_1_status",
        "day_2_status",
        "gap_ms",
        "gps_penalty_ms",
        "laps",
        "cp_count",
        "notes",
    ]

    # Optional defaults are null-safe exactly as in FastAPI (every field
    # except ``rider`` defaults None; ``rider`` is required).
    for fname in EventResultRowOut.model_fields:
        if fname == "rider":
            assert EventResultRowOut.model_fields[fname].is_required()
        else:
            assert EventResultRowOut.model_fields[fname].default is None

    # Nested ref schemas — order == backend/app/schemas/common.py exactly.
    assert list(RiderRef.model_fields) == [
        "race_number",
        "first_name",
        "last_name",
        "slug",
        "team",
        "bike",
    ]
    assert list(SeasonRef.model_fields) == [
        "year",
        "name",
        "slug",
        "is_current",
        "championship_format",
    ]
    assert list(CategoryRef.model_fields) == [
        "code",
        "display_name",
        "sort_order",
    ]
    assert list(EventRef.model_fields) == [
        "slug",
        "name",
        "event_date",
        "location",
        "sort_order",
        "event_type",
        "facebook_event_url",
        "description",
    ]


def test_sum_or_none_helper_is_byte_identical_to_fastapi() -> None:
    """The ``_sum_or_none`` helper matches ``backend/app/api/results.py``.

    Only non-null values contribute; an all-null set yields ``None`` (NOT
    ``0``). This is observable in the JSON (``gap_ms`` / ``gps_penalty_ms``
    / ``laps`` come back ``null`` vs ``0``), so it is part of the contract.
    """
    from types import SimpleNamespace

    from api.results import _sum_or_none

    rows = [
        SimpleNamespace(gap_ms=10, laps=None),
        SimpleNamespace(gap_ms=5, laps=None),
        SimpleNamespace(gap_ms=None, laps=None),
    ]
    assert _sum_or_none(rows, "gap_ms") == 15
    # All-null → None, never 0 (the FastAPI parity contract).
    assert _sum_or_none(rows, "laps") is None
    assert _sum_or_none([], "gap_ms") is None


# ===========================================================================
# 2. Behavior on the 2025 golden data — ported backend/tests/test_api.py:151
#    Race Results assertions (``seeded_orm`` → auto-tiered Tier-2; SKIPs
#    without seeded Postgres)
# ===========================================================================


def _call(endpoint, *args):
    """Invoke an S7 Ninja endpoint function directly (no HTTP).

    The endpoint takes ``request`` first; the results handler never touches
    the request object, so ``None`` is a faithful stand-in for this unit
    layer. The parity rig (section 3) exercises the FULL HTTP stack.
    """
    return endpoint(None, *args)


def test_race_results_expert_kyrnare_2025(seeded_orm) -> None:
    """Ported ``backend/tests/test_api.py:151``
    ``test_race_results_expert_kyrnare_2025``.

    Original assertions: 200, ``body["category"]["code"] == "expert"``,
    ``body["event"]["slug"] == "kyrnare"``, ``isinstance(body["rows"],
    list)``. Run S7's endpoint logic directly against the golden data.
    """
    from api.results import get_race_results

    out = _call(get_race_results, 2025, "expert", "kyrnare")
    assert out.category.code == "expert"
    assert out.event.slug == "kyrnare"
    # Rows may be empty for some 2025 aggregate data, but the shape must be
    # right (ported assertion: isinstance(body["rows"], list)).
    assert isinstance(out.rows, list)
    # ``days`` is the per-day axis the UI uses to decide column rendering.
    assert isinstance(out.days, list)
    assert all(isinstance(d, int) for d in out.days)
    assert out.season.year == 2025


def test_race_results_404_for_bad_category(seeded_orm) -> None:
    """Ported ``test_api.py:151 test_race_results_404_for_bad_category``.

    Goes through the F3 ``resolve_category`` → byte-exact ``HttpError(404,
    "Category 'bogus' not found in season 2025")``.
    """
    from ninja.errors import HttpError

    from api.results import get_race_results

    with pytest.raises(HttpError) as exc:
        _call(get_race_results, 2025, "bogus", "kyrnare")
    assert exc.value.status_code == 404
    assert (
        str(exc.value) == "Category 'bogus' not found in season 2025"
    )


def test_race_results_404_for_bad_event(seeded_orm) -> None:
    """Ported ``test_api.py:151 test_race_results_404_for_bad_event``.

    The race 404 string is byte-identical to
    ``backend/app/api/results.py``:
    ``f"Race '{event_slug}' not found in season {season.year}"`` (the SAME
    string S3 ``get_race_detail`` uses).
    """
    from ninja.errors import HttpError

    from api.results import get_race_results

    with pytest.raises(HttpError) as exc:
        _call(get_race_results, 2025, "expert", "bogus-race")
    assert exc.value.status_code == 404
    assert (
        str(exc.value) == "Race 'bogus-race' not found in season 2025"
    )


def test_race_results_404_for_bad_year(seeded_orm) -> None:
    """A bad year goes through F3 ``resolve_season`` (byte-exact season 404)
    BEFORE the category lookup — parity with the FastAPI
    ``Depends(get_category)`` → ``Depends(get_season)`` chain ordering.
    """
    from ninja.errors import HttpError

    from api.results import get_race_results

    with pytest.raises(HttpError) as exc:
        _call(get_race_results, 1999, "expert", "kyrnare")
    assert exc.value.status_code == 404
    assert str(exc.value) == "Season 1999 not found"


def test_race_results_rows_are_well_formed_when_present(seeded_orm) -> None:
    """When a (season, category, race) has results, every row obeys the S7
    contract: ranked rows have a positive integer ``position`` in ascending
    order; unranked rows (``position is None``) sort last; the per-day
    breakdown + headline ``time_ms`` are internally consistent with the
    FastAPI source's ``ranked`` rule.

    Scans the 2025 golden data for the first (expert, race) with rows so the
    assertion exercises the real ranked/unranked split that
    ``compute_event_scoring`` (S2) produces — not a synthetic fixture.
    """
    from api.results import get_race_results
    from core.models import Category, Event, Season

    season = Season.objects.get(year=2025)
    cat = Category.objects.filter(season_id=season.id, code="expert").first()
    assert cat is not None, "2025 expert category must be seeded"

    events = list(
        Event.objects.filter(season_id=season.id).order_by(
            "sort_order", "id"
        )
    )
    chosen = None
    for ev in events:
        out = _call(get_race_results, 2025, "expert", ev.slug)
        if out.rows:
            chosen = out
            break
    if chosen is None:
        pytest.skip(
            "no 2025 expert race with results rows in the golden data — "
            "the empty-rows shape is covered by "
            "test_race_results_expert_kyrnare_2025"
        )

    ranked = [r for r in chosen.rows if r.position is not None]
    unranked = [r for r in chosen.rows if r.position is None]

    # Ranked rows come first, ascending position, positive ints.
    assert chosen.rows[: len(ranked)] == ranked
    assert chosen.rows[len(ranked):] == unranked
    positions = [r.position for r in ranked]
    assert positions == sorted(positions)
    assert all(isinstance(p, int) and p >= 1 for p in positions)

    # FastAPI ``ranked`` rule: points/time_ms populated iff ranked.
    for r in ranked:
        assert r.points is not None
        assert r.time_ms is not None
    for r in unranked:
        assert r.points is None
        assert r.time_ms is None

    # ``days`` is the sorted set of distinct day numbers; for a single-day
    # race that's [1] and every row's day_2_* is null.
    assert chosen.days == sorted(set(chosen.days))
    if chosen.days == [1]:
        for r in chosen.rows:
            assert r.day_2_time_ms is None
            assert r.day_2_status is None


# ===========================================================================
# 3. Byte-parity vs the frozen FastAPI oracle — COPIED from F3's
#    tests/test_reference_parity.py / S2/S3 template, scoped to the S7
#    Race Results surface. (``parity_rig`` → auto-tiered Tier-2; SKIPs if
#    both stacks cannot spin)
#
# NO unordered-heap divergence in S7 (see module docstring): the FastAPI
# source uses selectinload(EventResult.rider) (FORWARD m2o → select_related)
# + an EXPLICIT ORDER BY day, id + a deterministic final rows re-sort, so
# assert_json_parity runs in FULL with NO normalization shim (unlike S2/S4).
# ===========================================================================


def _discover_events(rig, year: int) -> list[str]:
    """Return the race slugs for ``year`` from the NEW app's S3 endpoint.

    Avoids hardcoding fragile slug spellings: the S3
    ``/api/seasons/{year}/events`` list is itself byte-parity-proven, so its
    slugs are a trustworthy, seed-independent source for the (category, slug)
    pairs the S7 parity compare iterates.
    """
    resp = rig.new(f"/api/seasons/{year}/events")
    assert resp.status_code == 200, resp.content[:300]
    return [e["slug"] for e in json.loads(resp.content)["events"]]


def test_results_endpoint_byte_parity_2025(
    parity_rig, assert_json_parity
) -> None:
    """S7 Race Results == frozen FastAPI oracle, byte-for-byte, for EVERY
    2025 race in the ``expert`` category.

    Proves the verbatim-ported ``backend/app/api/results.py`` (the
    ranked/unranked split, the combined-time scoring via the S2
    ``compute_event_scoring`` hub, the ``ORDER BY day, id`` data fetch, the
    per-day ``day_1/day_2`` breakdown, the ``_sum_or_none`` aggregation, the
    Cyrillic rider names, the ``days`` array, the nested season/category/
    event refs + computed slug) produces a JSON body byte-identical to the
    oracle over identically-seeded Postgres. ``assert_json_parity`` runs in
    FULL (status, semantic JSON equality, the pinned serialization-format
    spec, the media-type prefix) — there is NO documented divergence to
    factor out for S7 (see module docstring), so a real regression anywhere
    fails loudly.
    """
    slugs = _discover_events(parity_rig, 2025)
    assert slugs, "2025 must have seeded races"
    for slug in slugs:
        path = f"/api/seasons/2025/categories/expert/events/{slug}"
        assert_json_parity(parity_rig.old(path), parity_rig.new(path))


def test_results_endpoint_byte_parity_2025_multi_category(
    parity_rig, assert_json_parity
) -> None:
    """S7 Race Results byte-parity across MULTIPLE 2025 categories on the
    ``kyrnare`` race.

    Exercises the ``Rider.category_id == category.id`` filter + the
    per-category ``compute_event_scoring`` for several categories, not just
    ``expert`` — proving the category scoping is byte-identical to the
    oracle. ``standard`` is the second category the S2 parity suite already
    proves exists for 2025.
    """
    for code in ("expert", "standard"):
        path = f"/api/seasons/2025/categories/{code}/events/kyrnare"
        assert_json_parity(parity_rig.old(path), parity_rig.new(path))


def test_results_endpoint_byte_parity_2026(
    parity_rig, assert_json_parity
) -> None:
    """S7 Race Results == oracle for the 2026 per_event season.

    2026 is the ``per_event`` championship format with real ISO 8601
    ``event_date`` on the nested ``EventRef`` and (for multi-day races) the
    ``day_1``/``day_2`` per-day breakdown + combined scoring. Proves the
    compute_event_scoring tier-fallback + the ISO-date nested refs are
    byte-identical to the oracle.
    """
    slugs = _discover_events(parity_rig, 2026)
    assert slugs, "2026 must have seeded races"
    for slug in slugs:
        path = f"/api/seasons/2026/categories/expert/events/{slug}"
        assert_json_parity(parity_rig.old(path), parity_rig.new(path))


def test_results_404_bad_year_parity(
    parity_rig, assert_json_parity
) -> None:
    """Missing season → identical 404 ``{"detail":"Season 1999 not found"}``.

    S7 routes existence through F3 ``resolve_season`` (called BEFORE the
    category lookup — parity with FastAPI ``Depends(get_category)`` chaining
    ``get_season`` first).
    """
    old = parity_rig.old(
        "/api/seasons/1999/categories/expert/events/kyrnare"
    )
    new = parity_rig.new(
        "/api/seasons/1999/categories/expert/events/kyrnare"
    )
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {"detail": "Season 1999 not found"}


def test_results_404_bad_category_parity(
    parity_rig, assert_json_parity
) -> None:
    """Unknown category → identical 404
    ``{"detail":"Category 'bogus' not found in season 2025"}``.

    Ported ``backend/tests/test_api.py:151
    test_race_results_404_for_bad_category``. S7 routes existence through F3
    ``resolve_category`` (byte-exact 404 string).
    """
    old = parity_rig.old(
        "/api/seasons/2025/categories/bogus/events/kyrnare"
    )
    new = parity_rig.new(
        "/api/seasons/2025/categories/bogus/events/kyrnare"
    )
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {
        "detail": "Category 'bogus' not found in season 2025"
    }


def test_results_404_bad_event_parity(
    parity_rig, assert_json_parity
) -> None:
    """Unknown race slug → identical 404
    ``{"detail":"Race 'bogus-race' not found in season 2025"}``.

    Ported ``backend/tests/test_api.py:151
    test_race_results_404_for_bad_event``. The race 404 string is
    byte-identical to ``backend/app/api/results.py`` (raised inline as
    ``HttpError``; the FastAPI source hand-rolled the same ``HTTPException``
    string — there is no F3 event-by-slug resolver; this is the SAME string
    S3 ``get_race_detail`` emits).
    """
    old = parity_rig.old(
        "/api/seasons/2025/categories/expert/events/bogus-race"
    )
    new = parity_rig.new(
        "/api/seasons/2025/categories/expert/events/bogus-race"
    )
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {
        "detail": "Race 'bogus-race' not found in season 2025"
    }


@pytest.mark.parametrize("bad_year", ["abc", "3000", "1800"])
def test_results_422_validation_parity(
    bad_year, parity_rig, assert_json_parity
) -> None:
    """Out-of-range / non-int ``year`` → identical 422 Pydantic-error body.

    Proves S7's ``YearPath`` reproduces the FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` validation. Structural contract
    (status, ``{"detail":[...]}``, ``loc``, ``type``) — ``msg`` wording can
    vary microscopically across pydantic patch releases (same tolerance as
    the S2/S3 422 parity tests).
    """
    p = f"/api/seasons/{bad_year}/categories/expert/events/kyrnare"
    old = parity_rig.old(p)
    new = parity_rig.new(p)
    assert old.status_code == 422, old.content[:300]
    assert new.status_code == 422, new.content[:300]

    o = json.loads(old.content)
    n = json.loads(new.content)
    assert isinstance(o["detail"], list) and isinstance(n["detail"], list)
    o_err, n_err = o["detail"][0], n["detail"][0]
    assert list(o_err["loc"]) == list(n_err["loc"]) == ["path", "year"]
    assert o_err["type"] == n_err["type"]


def test_results_per_day_breakdown_byte_parity_on_multi_day_race(
    parity_rig,
) -> None:
    """Explicit per-day-breakdown assertion on the live parity-rig response.

    Beyond the byte compare above, pin in code that for a MULTI-day race
    (``len(days) == 2``) the NEW app emits the ``day_1_time_ms`` /
    ``day_2_time_ms`` / ``day_1_status`` / ``day_2_status`` keys (the
    null-safe per-day contract the FastAPI ``EventResultRowOut`` gave) and
    that they byte-match the oracle. We scan 2026 (the per_event season that
    has real multi-day races) for the first race whose ``days`` is ``[1,
    2]``; if none exists in the sandbox seed we skip (never fake green).
    """
    multi_day = None
    for slug in _discover_events(parity_rig, 2026):
        path = f"/api/seasons/2026/categories/expert/events/{slug}"
        new = parity_rig.new(path)
        assert new.status_code == 200, new.content[:300]
        body = json.loads(new.content)
        if body["days"] == [1, 2]:
            multi_day = (path, body)
            break
    if multi_day is None:
        pytest.skip(
            "no 2026 expert race with a 2-day (days==[1,2]) result set in "
            "the sandbox seed — single-day per-day-null path is covered by "
            "test_results_endpoint_byte_parity_2025"
        )

    path, new_body = multi_day
    # Keys MUST be present (null-safe = explicit null, not omitted) and the
    # NEW body must byte-match the oracle for this multi-day race.
    for row in new_body["rows"]:
        for key in (
            "day_1_time_ms",
            "day_2_time_ms",
            "day_1_status",
            "day_2_status",
        ):
            assert key in row, (row, key)
    old = parity_rig.old(path)
    assert old.status_code == 200
    assert json.loads(old.content) == new_body
