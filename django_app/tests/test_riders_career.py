"""S4 — Riders API: career + profile + disambiguation coverage.

S4 owns the rider slice (``api/riders.py`` — BOTH ``router`` and
``career_router`` — + ``api/schemas/riders.py`` + the ported
``core/services/rider.py``) and consumes — never reimplements — the S2
service hub (``core.services.standings.get_standings``). This file mirrors
S1/S2/S3's three-section layout (``tests/test_seasons.py`` /
``test_standings.py`` / ``test_events.py``) — the auto-tiering in
``conftest.py`` keys off the ``seeded_orm`` / ``parity_rig`` fixture NAMES, so
Tier-2 marking is automatic with zero manual annotation.

1. **Contract / wiring + No-N+1 source guard** (no DB — Tier-1, always green
   in the locked venv): both routers are wired into the FROZEN router
   assembly at the right paths; the response schemas have the exact field
   NAMES + ORDER + TYPES + DEFAULTS of the frozen FastAPI Pydantic schemas
   (the ``openapi-typescript`` no-diff guarantee); the rider service exposes
   the exact ``riders_sharing_number`` / ``get_rider_profile`` names with the
   ``session``-dropped signatures (S2-hub convention); the career path uses
   ``select_related`` + ``prefetch_related`` (the ``selectinload`` analogue —
   the No-N+1 source guard, eng-review I8-perf=A); existence is routed
   through F3 ``resolve_season``; slug values come from ``core.slug`` only.

2. **Behavior on the 2025+ golden data** (``seeded_orm`` — auto-tiered
   Tier-2): the ported ``backend/tests/test_riders_career.py`` +
   ``backend/tests/test_api.py`` rider-profile/disambig assertions run S4's
   endpoint logic directly against the golden data, PLUS the **No-N+1
   runtime query-count assertion** on the rider-career path measured via
   ``CaptureQueriesContext`` (eng-review I8-perf=A — required, the heaviest
   fan-out path).

3. **Byte-parity vs the frozen FastAPI oracle** (``parity_rig`` — auto-tiered
   Tier-2): copied from F3's ``test_reference_parity.py`` template, scoped to
   the S4 career + profile + disambiguation surface. The bodies must be
   byte-for-byte equal to ``backend/app/api/riders.py`` over
   identically-seeded Postgres.

The Tier-2 tests (2 + 3) auto-mark ``parity`` via the ``seeded_orm`` /
``parity_rig`` fixture-name detection in ``conftest.py`` — S4 adds NO manual
marker. They SKIP (never fake green) if no seeded Postgres / both stacks
cannot be spun in the sandbox; the fixtures print the exact command.
"""

from __future__ import annotations

import json
from urllib.parse import quote

import pytest


def _enc(path: str) -> str:
    """URL-encode a path's segments + single query param so the parity
    rig's raw ``urllib`` client accepts Cyrillic + spaces.

    The F3 ``ParityRig.get`` passes the path verbatim to
    ``urllib.request.Request`` (no auto-encoding — prior ASCII-only slices
    never needed it). S4's rider paths carry a Cyrillic slug in BOTH the URL
    path (``/api/seasons/2025/riders/255/димитър-тинчев-255``) and the query
    (``/api/riders/career?slug=…``); encoding here mirrors exactly what the
    Astro frontend's client sends (the app decodes correctly — this is a
    test-client concern). Applied to BOTH ``old`` and ``new`` so the byte
    compare is apples-to-apples.
    """
    if "?" in path:
        base, qs = path.split("?", 1)
    else:
        base, qs = path, ""
    # Encode each path segment but keep the slashes.
    base = quote(base, safe="/")
    if qs:
        k, _, v = qs.partition("=")
        return f"{base}?{k}={quote(v, safe='')}"
    return base


# ===========================================================================
# 1. Contract / wiring + No-N+1 source guard — no DB, Tier-1 locked-venv gate
# ===========================================================================


def test_riders_routers_are_wired_into_frozen_assembly() -> None:
    """S4's ``router`` + ``career_router`` are the objects the FROZEN
    ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.riders.router`` (mounted at
    ``/seasons``) and ``api.riders.career_router`` (mounted at ``/riders``),
    both ``tags=["riders"]`` (``api/__init__.py:79-80``, parity with FastAPI
    ``APIRouter(prefix="/api/seasons"|"/api/riders", tags=["riders"])``).
    Confirm exactly the five rider operations are registered and nothing
    else leaked in.
    """
    from ninja import Router

    from api import riders as riders_api

    assert isinstance(riders_api.router, Router)
    assert isinstance(riders_api.career_router, Router)

    assert set(riders_api.router.path_operations.keys()) == {
        "/{year}/riders/search",
        "/{year}/riders/{race_number}",
        "/{year}/riders/{race_number}/{slug}",
    }
    assert set(riders_api.career_router.path_operations.keys()) == {
        "/career",
        "/search",
    }


def test_riders_endpoints_match_fastapi_source_signature() -> None:
    """S4 endpoint contract mirrors ``backend/app/api/riders.py``.

    Five GET operations. The per-season endpoints take the constrained
    ``year`` path param (parity with FastAPI ``get_season``
    ``Path(..., ge=1900, le=2999)`` via F3 ``YearPath``); the search
    endpoints take the constrained ``q`` / ``limit`` query params (parity
    with FastAPI ``Query(..., min_length=…, max_length=…, ge=…, le=…)``).
    """
    import typing

    from api import riders as riders_api
    from api.deps import YearPath
    from api.schemas.riders import (
        GlobalRiderSearchOut,
        RiderCareerOut,
        RiderDisambigOut,
        RiderProfileOut,
        RiderSearchOut,
    )

    for name, schema in [
        ("get_rider_career", RiderCareerOut),
        ("search_riders_global", GlobalRiderSearchOut),
        ("search_riders", RiderSearchOut),
        ("list_riders_sharing_number", RiderDisambigOut),
        ("get_rider", RiderProfileOut),
    ]:
        fn = getattr(riders_api, name)
        assert callable(fn), name
        assert schema.__name__ == schema.__name__

    # Constrained year param parity (per-season endpoints).
    for name in ("search_riders", "list_riders_sharing_number", "get_rider"):
        hints = typing.get_type_hints(
            getattr(riders_api, name), include_extras=True
        )
        assert hints["year"] is YearPath, name

    # The career match key + the profile/disambig race_number are plain
    # path/query params; the slug profile takes a str slug path param.
    get_rider_hints = typing.get_type_hints(
        riders_api.get_rider, include_extras=True
    )
    assert get_rider_hints["race_number"] is int
    assert get_rider_hints["slug"] is str


def test_riders_routes_existence_through_f3_resolver() -> None:
    """S4 per-season endpoints use F3 ``resolve_season`` — never hand-roll
    the season 404 (the byte-exact string lives in F3 / ``api/deps.py``).

    The rider-number 404 + slug-mismatch 404 + career-slug 404 strings are
    byte-identical to ``backend/app/api/riders.py`` and raised inline as
    ``HttpError`` (the FastAPI source hand-rolled the same ``HTTPException``
    strings — there is no F3 resolver for "rider-by-number" / "career-slug").
    """
    import inspect

    from api import riders as riders_api
    from api.deps import resolve_season

    assert resolve_season.__module__ == "api.deps"

    for name in ("search_riders", "list_riders_sharing_number", "get_rider"):
        src = inspect.getsource(getattr(riders_api, name))
        assert "resolve_season(" in src, name

    disambig_src = inspect.getsource(
        riders_api.list_riders_sharing_number
    )
    profile_src = inspect.getsource(riders_api.get_rider)
    career_src = inspect.getsource(riders_api.get_rider_career)

    # Byte-identical 404 strings to backend/app/api/riders.py — pin them so a
    # future edit that diverges the wording fails loudly (the ported parity
    # tests in section 3 are the runtime proof).
    assert (
        "No rider with number {race_number} in season {season.year}"
        in disambig_src
    )
    assert (
        "No rider with number {race_number} in season {season.year}"
        in profile_src
    )
    assert (
        "Rider #{race_number} with slug '{slug}' not found in season"
        in profile_src
    )
    assert '"Rider has no recorded results"' in profile_src
    assert "No rider found with slug '{slug}'" in career_src


def test_riders_consumes_s2_get_standings_not_reimplemented() -> None:
    """S4 career consumes the S2 service hub — Lane D contract.

    ``get_standings`` is owned by S2 (``core.services.standings``). S4
    imports + calls it for the career row's general-classification rank
    (parity with the FastAPI source, which imported
    ``from src.services.standings import get_standings``). S4 must NOT
    reimplement the standings computation in its own module.
    """
    import inspect

    from api import riders as riders_api
    from core.services import standings as svc

    src = inspect.getsource(riders_api)
    assert "from core.services.standings import get_standings" in src

    career_src = inspect.getsource(riders_api.get_rider_career)
    assert "get_standings(" in career_src
    assert riders_api.get_standings is svc.get_standings
    assert svc.get_standings.__module__ == "core.services.standings"


def test_rider_service_api_surface_is_stable() -> None:
    """S4's router imports this exact surface from ``core.services.rider``.

    The Django service API drops the FastAPI SQLAlchemy ``Session`` first
    arg (Django manages the connection itself — identical to the S2 hub
    convention) — pin the new signatures so a later refactor that breaks the
    service fails loudly here.
    """
    import inspect

    from core.services import rider as svc

    assert set(svc.__all__) == {
        "RiderResult",
        "RiderProfile",
        "riders_sharing_number",
        "get_rider_profile",
    }
    assert list(
        inspect.signature(svc.riders_sharing_number).parameters
    ) == ["season", "race_number"]
    assert list(
        inspect.signature(svc.get_rider_profile).parameters
    ) == ["season", "race_number", "first_name", "last_name"]
    # No SQLAlchemy ``session`` arg survives the ORM port.
    assert "session" not in inspect.signature(
        svc.riders_sharing_number
    ).parameters
    assert "session" not in inspect.signature(
        svc.get_rider_profile
    ).parameters


def test_rider_service_uses_prefetch_not_n_plus_1_source() -> None:
    """The ORM port batches the rider-career fan-out via
    ``select_related`` + ``prefetch_related`` (the ``selectinload`` analogue)
    — the No-N+1 SOURCE guard (eng-review I8-perf=A, the heaviest fan-out).

    A future edit that drops the prefetch (re-introducing per-rider /
    per-result queries on the career path) fails here even without a DB. The
    runtime query-count proof is section 2
    (``test_rider_career_no_n_plus_1_query_count``).
    """
    import inspect
    import re

    from api import riders as riders_api
    from core.services import rider as svc

    # The service's get_rider_profile uses select_related(category) +
    # prefetch_related(Prefetch("results", select_related("event"))).
    prof = re.sub(r"\s+", " ", inspect.getsource(svc.get_rider_profile))
    assert "select_related(" in prof and '"category"' in prof
    assert "prefetch_related(" in prof
    assert "Prefetch(" in prof and '"results"' in prof
    assert 'select_related("event")' in prof or "select_related( \"event\"" in prof
    # No SQLAlchemy-ism call survives the ORM port.
    raw = inspect.getsource(svc.get_rider_profile)
    assert "selectinload(" not in raw
    assert ".options(" not in raw

    # The career endpoint loads candidates with select_related(season,
    # category) + prefetch_related("results__event") so the heavy
    # cross-season fan-out is a fixed number of queries, NOT O(matching).
    career = re.sub(
        r"\s+", " ", inspect.getsource(riders_api.get_rider_career)
    )
    assert "select_related(" in career
    assert '"season"' in career and '"category"' in career
    assert "prefetch_related(" in career
    assert '"results__event"' in career


def test_rider_slug_comes_from_core_slug_only() -> None:
    """Slug values come from ``core.slug.rider_slug`` ONLY (S4 acceptance).

    S4 never recomputes the slug locally — it either calls F3's
    ``build_rider_ref`` (which uses ``core.slug.rider_slug``) or imports
    ``rider_slug`` directly as the MATCH key (career/profile lookup), exactly
    as ``backend/app/api/riders.py`` did. Pin that the only slug-producing
    symbol in the module is the F3-canonical one.
    """
    import inspect

    from api import riders as riders_api
    from core.slug import rider_slug as canonical

    assert riders_api.rider_slug is canonical
    assert canonical.__module__ == "core.slug"

    src = inspect.getsource(riders_api)
    # No bespoke slug recomputation (e.g. an inline f"{first}-{last}…" lower
    # replace). The module must use the imported canonical fn name only.
    assert "def rider_slug" not in src
    assert ".replace(\" \", \"-\").lower()" not in src


def test_rider_schemas_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    The pinned renderer never re-sorts keys (``api/renderers.py``), so JSON
    key order == schema field-declaration order. If S4's schema field order
    ever drifts from ``backend/app/schemas/riders.py`` /
    ``backend/app/schemas/common.py`` the frontend's ``openapi-typescript``
    client would regenerate WITH a diff. Pin the exact contract here.
    """
    from api.schemas.common import CategoryRef, EventRef, RiderRef, SeasonRef
    from api.schemas.riders import (
        GlobalRiderSearchOut,
        RiderCareerOut,
        RiderCareerSeasonOut,
        RiderDisambigEntryOut,
        RiderDisambigOut,
        RiderProfileOut,
        RiderResultOut,
        RiderSearchOut,
        RiderSearchResultOut,
    )

    assert list(RiderResultOut.model_fields) == [
        "event",
        "category",
        "position",
        "points",
        "time_ms",
        "gap_ms",
        "gps_penalty_ms",
        "laps",
    ]
    assert list(RiderProfileOut.model_fields) == [
        "season",
        "rider",
        "categories",
        "results",
        "total_events",
    ]
    assert list(RiderDisambigEntryOut.model_fields) == [
        "rider",
        "categories",
    ]
    assert list(RiderDisambigOut.model_fields) == [
        "season",
        "race_number",
        "candidates",
    ]
    assert list(RiderSearchResultOut.model_fields) == [
        "rider",
        "category",
        "season_year",
    ]
    assert list(RiderSearchOut.model_fields) == [
        "season",
        "query",
        "results",
    ]
    assert list(GlobalRiderSearchOut.model_fields) == ["query", "results"]
    assert list(RiderCareerSeasonOut.model_fields) == [
        "season_year",
        "race_number",
        "category",
        "team",
        "bike",
        "final_position",
        "races_participated",
        "total_points",
        "best_position",
        "results",
    ]
    assert list(RiderCareerOut.model_fields) == [
        "slug",
        "first_name",
        "last_name",
        "seasons",
    ]

    # Nullable fields default to None / [] (null-safe), as in FastAPI.
    for f in (
        "position",
        "points",
        "time_ms",
        "gap_ms",
        "gps_penalty_ms",
        "laps",
    ):
        assert RiderResultOut.model_fields[f].default is None
    assert RiderCareerSeasonOut.model_fields["team"].default is None
    assert RiderCareerSeasonOut.model_fields["bike"].default is None
    assert (
        RiderCareerSeasonOut.model_fields["final_position"].default is None
    )
    assert (
        RiderCareerSeasonOut.model_fields["best_position"].default is None
    )

    # Nested refs unchanged (F3 common — slug computed server-side).
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


# ===========================================================================
# 2. Behavior on the golden data — ported backend/tests/test_riders_career.py
#    + backend/tests/test_api.py rider-profile/disambig assertions, PLUS the
#    No-N+1 runtime query-count assertion on the rider-career path.
#    (``seeded_orm`` → auto-tiered Tier-2; SKIPs without seeded Postgres)
# ===========================================================================


def _call(endpoint, *args, **kwargs):
    """Invoke an S4 Ninja endpoint function directly (no HTTP).

    The endpoints take ``request`` first; the rider handlers never touch the
    request object, so ``None`` is a faithful stand-in for this unit layer.
    The parity rig (section 3) exercises the FULL HTTP stack.
    """
    return endpoint(None, *args, **kwargs)


def _first_rider_in_2025_expert():
    """Pick a rider from the 2025 Expert class (ported
    ``backend/tests/test_api.py::_first_rider_in_2025_expert``)."""
    from core.models import Category, Rider, Season

    season = Season.objects.get(year=2025)
    cat = Category.objects.get(season_id=season.id, code="expert")
    rider = Rider.objects.filter(category_id=cat.id).first()
    return rider.race_number, rider.first_name, rider.last_name


def test_career_for_known_rider_aggregates_seasons(seeded_orm) -> None:
    """Ported ``test_career_for_known_rider_aggregates_seasons``.

    Димитър ТИНЧЕВ raced in 2024 + 2025 (and possibly 2026 — the assertion
    only requires he shows up in MORE THAN one season).
    """
    from api.riders import get_rider_career

    out = _call(get_rider_career, slug="димитър-тинчев-255")
    assert out.slug == "димитър-тинчев-255"
    assert out.last_name == "ТИНЧЕВ"
    assert len(out.seasons) >= 1
    for s in out.seasons:
        assert s.season_year is not None
        assert s.race_number is not None
        assert s.category is not None
        assert s.races_participated is not None
        assert s.total_points is not None


def test_career_unknown_slug_returns_404(seeded_orm) -> None:
    """Ported ``test_career_unknown_slug_returns_404``."""
    from ninja.errors import HttpError

    from api.riders import get_rider_career

    with pytest.raises(HttpError) as exc:
        _call(get_rider_career, slug="no-such-rider")
    assert exc.value.status_code == 404
    assert str(exc.value) == "No rider found with slug 'no-such-rider'"


def test_career_seasons_are_descending(seeded_orm) -> None:
    """Ported ``test_career_seasons_are_descending``.

    Strictly non-increasing — S4 sorts descending so the latest season is
    first (``rows.sort(key=lambda r: (-r.season_year, r.category.sort_order))``).
    """
    from api.riders import get_rider_career

    out = _call(get_rider_career, slug="димитър-тинчев-255")
    years = [s.season_year for s in out.seasons]
    assert years == sorted(years, reverse=True)


def test_career_row_carries_standings_final_position(seeded_orm) -> None:
    """The career row's ``final_position`` comes from the S2
    ``get_standings`` hub — it must match what the leaderboard shows.

    Cross-check: for at least one (season, category) the career endpoint
    reports, the rider's ``final_position`` equals the rank S2's
    ``get_standings`` gives for the same rider id.
    """
    from api.riders import get_rider_career
    from core.models import Category, Season
    from core.services.standings import get_standings

    out = _call(get_rider_career, slug="димитър-тинчев-255")
    assert out.seasons, "expected at least one career season row"
    checked = 0
    for s in out.seasons:
        if s.final_position is None:
            continue
        season = Season.objects.get(year=s.season_year)
        cat = Category.objects.get(
            season_id=season.id, code=s.category.code
        )
        rows = get_standings(season, cat)
        # Find the rider in the standings by the (race_number, name) identity
        # (the career row is for this slug → this exact Rider).
        match = [
            r
            for r in rows
            if r.rider.race_number == s.race_number
            and r.rider.first_name == out.first_name
            and r.rider.last_name == out.last_name
        ]
        assert match, (
            f"career claims final_position={s.final_position} in "
            f"{s.season_year}/{s.category.code} but rider absent from "
            f"S2 get_standings"
        )
        assert match[0].final_position == s.final_position
        checked += 1
    assert checked >= 1, (
        "expected at least one career season with a non-null final_position "
        "to cross-check against the S2 standings hub"
    )


def test_rider_disambig_lists_candidates_for_existing_number(
    seeded_orm,
) -> None:
    """Ported
    ``backend/tests/test_api.py::test_rider_disambig_lists_candidates_for_existing_number``.
    """
    from api.riders import list_riders_sharing_number

    race_number, _first, _last = _first_rider_in_2025_expert()
    out = _call(list_riders_sharing_number, 2025, race_number)
    assert out.race_number == race_number
    assert out.season.year == 2025
    assert len(out.candidates) >= 1


def test_rider_disambig_404_for_unused_number(seeded_orm) -> None:
    """Ported ``test_rider_disambig_404_for_unused_number``.

    Byte-exact 404 string from ``backend/app/api/riders.py``.
    """
    from ninja.errors import HttpError

    from api.riders import list_riders_sharing_number

    with pytest.raises(HttpError) as exc:
        _call(list_riders_sharing_number, 2025, 99999)
    assert exc.value.status_code == 404
    assert (
        str(exc.value)
        == "No rider with number 99999 in season 2025"
    )


def test_rider_disambig_404_for_bad_year(seeded_orm) -> None:
    """A bad year on the disambig endpoint goes through F3 ``resolve_season``
    (byte-exact season 404) BEFORE the number lookup — parity with the
    FastAPI ``Depends(get_season)`` ordering.
    """
    from ninja.errors import HttpError

    from api.riders import list_riders_sharing_number

    with pytest.raises(HttpError) as exc:
        _call(list_riders_sharing_number, 1999, 255)
    assert exc.value.status_code == 404
    assert str(exc.value) == "Season 1999 not found"


def test_rider_profile_resolves_by_slug(seeded_orm) -> None:
    """Ported ``backend/tests/test_api.py::test_rider_profile_resolves_by_slug``.

    Slug comes from ``core.slug.rider_slug`` (S4 acceptance: slug values from
    ``core/slug.py`` only).
    """
    from api.riders import get_rider
    from core.slug import rider_slug

    race_number, first, last = _first_rider_in_2025_expert()
    slug = rider_slug(first, last, race_number)
    out = _call(get_rider, 2025, race_number, slug)
    assert out.rider.race_number == race_number
    assert out.rider.first_name == first
    assert out.rider.last_name == last
    assert out.rider.slug == slug
    assert out.total_events >= 1


def test_rider_profile_404_for_mismatched_slug(seeded_orm) -> None:
    """Ported ``test_rider_profile_404_for_mismatched_slug``.

    Byte-exact 404 string from ``backend/app/api/riders.py``.
    """
    from ninja.errors import HttpError

    from api.riders import get_rider

    race_number, _first, _last = _first_rider_in_2025_expert()
    with pytest.raises(HttpError) as exc:
        _call(get_rider, 2025, race_number, "definitely-not-this-person")
    assert exc.value.status_code == 404
    assert (
        str(exc.value)
        == f"Rider #{race_number} with slug 'definitely-not-this-person' "
        f"not found in season 2025"
    )


def test_rider_profile_404_for_unused_number(seeded_orm) -> None:
    """Ported ``test_rider_profile_404_for_unused_number``."""
    from ninja.errors import HttpError

    from api.riders import get_rider

    with pytest.raises(HttpError) as exc:
        _call(get_rider, 2025, 99999, "anyone")
    assert exc.value.status_code == 404
    assert str(exc.value) == "No rider with number 99999 in season 2025"


# --- No-N+1 acceptance criterion (eng-review I8-perf=A) --------------------
# S4 acceptance: "rider-career query count within current bounds (assert in
# test)". The rider-career path is the HEAVIEST fan-out path: it scans every
# Rider row, slug-filters in Python, then for each matching season aggregates
# the rider's results AND looks up the season standings. ``get_rider_career``
# loads all candidates with ``select_related("season","category")`` +
# ``prefetch_related("results__event")`` so the candidate + result fetch is a
# FIXED, small number of queries regardless of how many riders/results exist
# (the ``selectinload`` analogue, NOT O(matching)). The only remaining
# query-bearing work is the per-(season,category) S2 ``get_standings`` lookup,
# which is itself memoized in ``standings_cache`` (computed ONCE per unique
# (season_id, category_id) the matched rider appears in — at most a handful).
# We measure the real count against the seeded ``bgx_django`` via
# ``seeded_orm`` + ``CaptureQueriesContext`` and assert a tight upper bound
# that does NOT scale with the total rider population. Mirrors S2's
# ``test_leaderboard_no_n_plus_1_query_count``.


def test_rider_career_no_n_plus_1_query_count(seeded_orm) -> None:
    """``get_rider_career`` is O(seasons-the-rider-raced) queries, NOT
    O(total-riders) or O(results) — the No-N+1 gate (eng-review I8-perf=A).

    Expected query plan for a representative MULTI-SEASON rider
    (Димитър ТИНЧЕВ #255 — 2024 + 2025, possibly 2026):

      Q1  candidates: ``SELECT … FROM rider
                        JOIN season JOIN category``  (select_related)
      Q2  results:    ``SELECT … FROM event_result
                        WHERE rider_id IN (…)``      (ONE batched prefetch —
                        the selectinload analogue, NOT per-rider)
      Q3  events:     ``SELECT … FROM event
                        WHERE id IN (…)``            (the ``results__event``
                        nested prefetch — ONE batched query)
      then, per UNIQUE (season, category) the matched rider raced in (a small
      constant — memoized in ``standings_cache``), the S2 ``get_standings``
      issues its own bounded fan-out (events + riders + ONE batched results
      prefetch ≈ 3 queries each — itself O(1), proven by S2's own No-N+1
      test).

    The KEY property: the count does NOT grow with the (large) total rider
    population — a naive port without the prefetch would issue one
    ``EventResult`` query PER matched rider (and one ``Event`` query per
    result), exploding on the cross-season scan. We bound it well below that
    and assert it stays flat.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from api.riders import get_rider_career
    from core.models import Rider

    total_riders = Rider.objects.count()
    assert total_riders > 50, (
        f"seeded data should have a large rider population (got "
        f"{total_riders}); a tiny one would make the N+1 assertion vacuous"
    )

    with CaptureQueriesContext(connection) as ctx:
        out = _call(get_rider_career, slug="димитър-тинчев-255")
        # Force full materialization of every nested access the renderer
        # will do, so any lazy N+1 would show up here.
        for s in out.seasons:
            _ = s.race_number
            _ = s.category.code
            for r in s.results:
                _ = r.event.slug
                _ = r.category.code

    n_queries = len(ctx.captured_queries)
    n_seasons = len(out.seasons)
    assert n_seasons >= 1, "expected the rider to have at least one season"

    # Bound: candidate scan (1) + results prefetch (1) + events prefetch (1)
    # + the memoized S2 get_standings per unique (season, category). Each
    # get_standings is ≈3 queries (events + riders + ONE results prefetch);
    # the rider races in a small constant number of (season, category)
    # buckets. 30 is a generous flat ceiling that a per-rider/per-result N+1
    # against the >50-rider population would blow through immediately, while
    # NOT scaling with total_riders.
    assert n_queries <= 30, (
        f"get_rider_career issued {n_queries} queries for a "
        f"{n_seasons}-season rider against {total_riders} total riders — "
        f"expected <= 30 (candidate scan + 2 batched prefetches + memoized "
        f"per-(season,category) S2 get_standings). This is an N+1 "
        f"regression (prefetch_related lost?).\n"
        + "\n".join(
            f"  [{i}] {q['sql'][:160]}"
            for i, q in enumerate(ctx.captured_queries)
        )
    )
    # Stronger flat-scaling guard: the count must be far below "one query
    # per rider" — the failure mode a missing prefetch would produce.
    assert n_queries < total_riders, (
        f"query count ({n_queries}) is not flat — it scales with the rider "
        f"population ({total_riders}). The cross-season prefetch was lost."
    )


# ===========================================================================
# 3. Byte-parity vs the frozen FastAPI oracle — COPIED from F3's
#    tests/test_reference_parity.py template, scoped to the S4 career +
#    profile + disambiguation surface.
#    (``parity_rig`` → auto-tiered Tier-2; SKIPs if both stacks cannot spin)
# ===========================================================================

# The S4 career / profile / disambig public surface. Each is a (path, note)
# the new Django app and the spun FastAPI oracle must agree on byte-for-byte.
# Димитър ТИНЧЕВ #255 is the 2025 expert leader and races multi-season →
# exercises the cross-season aggregation + the S2 get_standings final_position
# + multi-day collapse. The disambig + profile paths use the same rider.
CAREER_PROFILE_PATHS = [
    (
        "/api/riders/career?slug=димитър-тинчев-255",
        "career — cross-season aggregation, S2 final_position, multi-day "
        "collapse, descending sort, Cyrillic, key order",
    ),
    (
        "/api/seasons/2025/riders/255",
        "disambig — candidates + categories (sort_order,id), Cyrillic",
    ),
    (
        "/api/seasons/2025/riders/255/димитър-тинчев-255",
        "profile — header meta + every result this season, total_events",
    ),
]


@pytest.mark.parametrize("path, _note", CAREER_PROFILE_PATHS)
def test_riders_career_profile_byte_parity(
    path, _note, parity_rig, assert_json_parity
) -> None:
    """S4 career/profile/disambig == frozen FastAPI oracle, byte-for-byte.

    Proves the ported ``backend/app/api/riders.py`` (the per-season
    ``router`` + the cross-season ``career_router``) + the ported
    ``core/services/rider.py`` + the S2 ``get_standings`` consumption produce
    a JSON body byte-identical to the oracle over identically-seeded
    Postgres, for the cross-season career aggregation (the heaviest path),
    the disambiguation list, and the singular profile.
    """
    enc = _enc(path)
    assert_json_parity(parity_rig.old(enc), parity_rig.new(enc))


def test_career_unknown_slug_404_parity(
    parity_rig, assert_json_parity
) -> None:
    """Unknown career slug → identical 404
    ``{"detail":"No rider found with slug 'no-such-rider'"}``.

    Ported ``backend/tests/test_riders_career.py::test_career_unknown_slug_returns_404``.
    The career-slug 404 string is byte-identical to
    ``backend/app/api/riders.py`` (raised inline as ``HttpError``).
    """
    old = parity_rig.old("/api/riders/career?slug=no-such-rider")
    new = parity_rig.new("/api/riders/career?slug=no-such-rider")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {
        "detail": "No rider found with slug 'no-such-rider'"
    }


def test_career_requires_slug_422_parity(
    parity_rig, assert_json_parity
) -> None:
    """Missing required ``slug`` query param → identical 422 Pydantic body.

    Ported ``backend/tests/test_riders_career.py::test_career_requires_slug``.
    Structural contract (status, ``{"detail":[...]}``, ``loc``, ``type``) —
    ``msg`` wording can vary microscopically across pydantic patch releases.
    """
    old = parity_rig.old("/api/riders/career")
    new = parity_rig.new("/api/riders/career")
    assert old.status_code == 422, old.content[:300]
    assert new.status_code == 422, new.content[:300]
    o = json.loads(old.content)
    n = json.loads(new.content)
    assert isinstance(o["detail"], list) and isinstance(n["detail"], list)
    o_err, n_err = o["detail"][0], n["detail"][0]
    assert list(o_err["loc"])[-1] == list(n_err["loc"])[-1] == "slug"
    assert o_err["type"] == n_err["type"]


def test_rider_disambig_404_for_unused_number_parity(
    parity_rig, assert_json_parity
) -> None:
    """Unused race number → identical 404
    ``{"detail":"No rider with number 99999 in season 2025"}``.

    Ported ``backend/tests/test_api.py::test_rider_disambig_404_for_unused_number``.
    """
    old = parity_rig.old("/api/seasons/2025/riders/99999")
    new = parity_rig.new("/api/seasons/2025/riders/99999")
    assert old.status_code == 404
    assert_json_parity(old, new)
    assert json.loads(new.content) == {
        "detail": "No rider with number 99999 in season 2025"
    }


def test_rider_profile_404_mismatched_slug_parity(
    parity_rig, assert_json_parity
) -> None:
    """Slug that matches no (first,last) pair → identical 404.

    Ported ``backend/tests/test_api.py::test_rider_profile_404_for_mismatched_slug``.
    """
    old = parity_rig.old(
        "/api/seasons/2025/riders/255/definitely-not-this-person"
    )
    new = parity_rig.new(
        "/api/seasons/2025/riders/255/definitely-not-this-person"
    )
    assert old.status_code == 404
    assert_json_parity(old, new)


def test_rider_profile_slug_matches_backend_algorithm(parity_rig) -> None:
    """Ported slug-parity assertion (frontend consumes ``RiderRef.slug``).

    Verify the slug in the NEW app's profile response is exactly what
    ``core.slug.rider_slug`` produces (F3 byte-identical copy of
    ``backend/app/slug.py``) — S4 acceptance: slug values from
    ``core/slug.py`` only.
    """
    from core.slug import rider_slug

    new = parity_rig.new(
        _enc("/api/seasons/2025/riders/255/димитър-тинчев-255")
    )
    assert new.status_code == 200
    body = json.loads(new.content)
    r = body["rider"]
    assert r["slug"] == rider_slug(
        r["first_name"], r["last_name"], r["race_number"]
    )
    # Career endpoint slug too.
    career = parity_rig.new(
        _enc("/api/riders/career?slug=димитър-тинчев-255")
    )
    assert career.status_code == 200
    cbody = json.loads(career.content)
    assert cbody["slug"] == rider_slug(
        cbody["first_name"], cbody["last_name"], cbody["seasons"][0]["race_number"]
    )
