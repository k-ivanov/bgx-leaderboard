"""S5 — Stats API + auth gate: owned test coverage.

S5 owns the stats slice (``api/stats.py`` + ``api/schemas/stats.py``) — the
private auth-gated analytics endpoint. This file mirrors the S1/S2
three-section layout (``tests/test_seasons.py`` / ``tests/test_standings.py``)
— the auto-tiering in ``conftest.py`` keys off the ``seeded_orm`` /
``parity_rig`` fixture NAMES, so Tier-2 marking is automatic with zero manual
annotation.

1. **Contract / wiring + auth gate** (no seeded Postgres — Tier-1, runs in
   the locked-venv gate): the stats module is wired into the FROZEN router
   assembly at the right prefix; the response schemas have the exact field
   NAMES + ORDER + TYPES + DEFAULTS of the frozen FastAPI Pydantic schemas
   (the ``openapi-typescript`` no-diff guarantee); the endpoint ORM ordering
   is the byte-equivalent of the FastAPI ``ORDER BY``; and the **auth gate**
   (the S5-specific surface) is exercised in all THREE states + the bad-b64
   edge against pytest-django's isolated test DB via ``@pytest.mark.django_db``
   (NOT ``seeded_orm`` — so it is Tier-1, not auto-tiered ``parity``; it does
   not need the golden data, only an empty isolated ``visit`` table).

2. **Aggregation numbers on a controlled Visit fixture** (``@pytest.mark.
   django_db`` against the isolated test DB — Tier-1): ported behavior from
   ``backend/tests/test_api.py`` stats assertions PLUS the
   ``top_comparisons`` aggregation (the S5-acceptance "aggregation numbers
   incl. top_comparisons byte-parity on a fixture dataset"). ``visit`` is one
   of the 8 domain tables the ``seeded_orm`` read-only invariant forbids
   writing, and ``seed_data/`` carries NO visit rows (visits are runtime
   analytics, not golden data) — so the aggregation-numbers proof uses a
   controlled fixture in pytest-django's isolated DB, exactly the substrate
   F2/scaffold model tests use.

3. **Byte-parity vs the frozen FastAPI oracle** (``parity_rig`` — auto-tiered
   Tier-2): copied from F3's ``test_reference_parity.py`` template, scoped to
   the S5 stats surface. Both seeded DBs carry NO visit rows (visits aren't
   golden data), so the parity rig proves the **empty-aggregation
   serialization is byte-identical** (the realistic seeded state — every
   key, the ``avg_session_seconds`` float ``0.0``, the empty arrays, key
   order, Cyrillic-safe renderer) AND the auth-gate 401 bodies/headers are
   byte-identical to the spun oracle in all three states.

KNOWN ENV NOTE (carried from S1/S2): F3's ``seeded_orm`` fixture has a
pre-existing connection-rebind bug that can ERROR under intermittent
Postgres (tracked separately, NOT an S5 bug, out of S5 scope). S5's Tier-2
proof is ``parity_rig`` (subprocesses, decoupled from that bug); the
``@pytest.mark.django_db`` tests use pytest-django's own isolated test DB,
not ``seeded_orm``. Nothing here fakes a green: the parity tests SKIP with
the exact command when both stacks cannot be spun.
"""

from __future__ import annotations

import base64
import json

import pytest


def _skip_unless_postgres() -> None:
    """Skip when the Django test DB is not Postgres.

    The ``avg_session_seconds`` aggregation is a byte-faithful port of the
    oracle's Postgres ``EXTRACT(epoch FROM …)`` SQL, so any test that runs
    the FULL ``get_stats`` aggregation needs a Postgres test DB. The Tier-1
    locked-venv gate runs ``@pytest.mark.django_db`` against in-memory SQLite
    (no Postgres) — these tests then SKIP cleanly (never fake a green; the
    authoritative Postgres proof is the Tier-2 ``parity_rig`` byte-compare
    against the spun oracle, and these same tests run for real when the test
    DB is Postgres, e.g. an integration/CI run with ``DATABASE_URL`` set —
    exactly the S1/S2 ``seeded_orm`` skip-don't-fake discipline). The
    pure-401 auth tests do NOT call this: their rejection path returns before
    any DB read, so they exercise the gate fully on SQLite too.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip(
            "stats aggregation needs a Postgres test DB (avg_session_seconds "
            "ports the oracle's EXTRACT(epoch …) SQL; SQLite has no epoch "
            "extract). Tier-1 gate runs django_db on in-memory SQLite — the "
            "authoritative Postgres proof is the Tier-2 parity_rig. Run with "
            "DATABASE_URL=postgresql://… to exercise this for real."
        )


# ===========================================================================
# 1. Contract / wiring — no seeded Postgres, runs in the Tier-1 gate
# ===========================================================================


def test_stats_router_is_wired_into_frozen_assembly() -> None:
    """S5's ``router`` is the object the FROZEN ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.stats.router`` by reference and mounts
    it at the ``""`` prefix (``api/__init__.py:81``) so the public path is
    ``/api/stats`` — byte-identical to ``backend/app/main.py:113``. S5 fills
    that module's ``router`` — confirm exactly the one stats operation is
    registered and nothing else leaked in.
    """
    from ninja import Router

    from api import stats as stats_api

    assert isinstance(stats_api.router, Router)

    paths = set(stats_api.router.path_operations.keys())
    assert paths == {"/stats"}, paths


def test_stats_endpoint_matches_fastapi_source_signature() -> None:
    """S5 endpoint contract mirrors ``backend/app/api/stats.py``.

    One GET operation, response schema ``StatsOut``. The FastAPI handler took
    no path/query params (the auth was a router-level ``Depends``); the
    Django port takes only ``request`` (the auth gate runs explicitly inside
    the handler — the F3-style ``Depends`` → explicit-call redesign).
    """
    from api import stats as stats_api
    from api.schemas.stats import StatsOut

    po = stats_api.router.path_operations["/stats"]
    (op,) = po.operations
    assert op.methods == ["GET"]
    assert op.response_models[200] is not None
    assert StatsOut.__name__ == "StatsOut"


def test_stats_schema_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    The pinned renderer never re-sorts keys (``api/renderers.py``), so JSON
    key order == schema field-declaration order. If S5's schema field order
    ever drifts from ``backend/app/schemas/stats.py`` the frontend's
    ``openapi-typescript`` client regenerates WITH a diff. Pin the exact
    contract here — every nested schema, in order.
    """
    from api.schemas.stats import (
        CategoryVisitCount,
        ComparisonCount,
        DeviceCount,
        RaceVisitCount,
        RecentVisit,
        RiderVisitCount,
        StatsOut,
    )

    assert list(DeviceCount.model_fields) == ["device_type", "count"]
    assert list(CategoryVisitCount.model_fields) == [
        "category",
        "season_year",
        "count",
    ]
    assert list(RaceVisitCount.model_fields) == [
        "season_year",
        "event_slug",
        "count",
    ]
    assert list(RiderVisitCount.model_fields) == [
        "season_year",
        "rider_slug",
        "count",
    ]
    assert list(ComparisonCount.model_fields) == ["slug_a", "slug_b", "count"]
    assert list(RecentVisit.model_fields) == [
        "timestamp",
        "page",
        "category",
        "season_year",
        "event_slug",
        "rider_slug",
        "device_type",
    ]
    assert list(StatsOut.model_fields) == [
        "total_visits",
        "unique_visitors_today",
        "unique_visitors_7d",
        "unique_visitors_30d",
        "sessions_today",
        "avg_session_seconds",
        "devices",
        "per_category",
        "per_race",
        "per_rider",
        "top_comparisons",
        "recent",
    ]

    # Optional fields default to None (null-safe), as in FastAPI.
    assert CategoryVisitCount.model_fields["category"].default is None
    assert CategoryVisitCount.model_fields["season_year"].default is None
    assert RaceVisitCount.model_fields["season_year"].default is None
    assert RiderVisitCount.model_fields["season_year"].default is None
    assert RecentVisit.model_fields["category"].default is None
    assert RecentVisit.model_fields["season_year"].default is None
    assert RecentVisit.model_fields["event_slug"].default is None
    assert RecentVisit.model_fields["rider_slug"].default is None


def test_stats_endpoint_orm_ordering_is_byte_equivalent_to_fastapi() -> None:
    """S5's ORM ``order_by`` / ``limit`` clauses == the FastAPI ``ORDER BY``.

    The ordering + limits are observable in the JSON array order/length, so
    they are part of the byte-parity contract. FastAPI:
      * per_category/per_race/per_rider/top_comparisons:
        ``order_by(func.count(Visit.id).desc())`` (+ ``limit(_TOP_N=50)`` on
        race/rider/comparisons)
      * recent: ``order_by(Visit.timestamp.desc()).limit(25)``
    Assert S5's source uses the exact equivalents.
    """
    import inspect

    from api import stats as stats_api

    src = inspect.getsource(stats_api.get_stats)
    assert 'order_by("-count")' in src
    assert "_TOP_N" in src and "_TOP_N = 50" in inspect.getsource(stats_api)
    assert 'order_by("-timestamp")[:25]' in src


def test_stats_auth_gate_mirrors_backend_auth_module() -> None:
    """S5's auth gate is the explicit-call port of ``backend/app/auth.py``.

    The FastAPI app gated the router with
    ``dependencies=[Depends(require_stats_auth)]``; the Django port calls
    ``_require_stats_auth`` as the FIRST thing the handler does (F3-style
    ``Depends`` → explicit redesign). Source-level guard that the gate is
    still the first line of defense + uses a constant-time compare.
    """
    import inspect

    from api import stats as stats_api

    handler_src = inspect.getsource(stats_api.get_stats)
    # auth check is the first thing the handler does (before any DB read).
    assert "_require_stats_auth(request)" in handler_src
    body = handler_src.split("\n")
    blocked_idx = next(
        i for i, ln in enumerate(body) if "_require_stats_auth(request)" in ln
    )
    total_idx = next(
        i for i, ln in enumerate(body) if "Visit.objects.count()" in ln
    )
    assert blocked_idx < total_idx, "auth gate must run BEFORE any DB read"

    gate_src = inspect.getsource(stats_api._require_stats_auth)
    assert "secrets.compare_digest(" in gate_src  # constant-time compare
    assert "settings.STATS_PASSWORD" in gate_src
    assert "Not authenticated" in gate_src
    assert "Invalid credentials" in gate_src
    realm = inspect.getsource(stats_api._unauthorized)
    assert "WWW-Authenticate" in realm


# --- The auth gate, all three states + the bad-b64 edge --------------------
# These need an isolated ``visit`` table (the gate path 'correct creds'
# returns StatsOut, which runs the aggregation) but NOT the golden data, so
# they use pytest-django's own isolated test DB via ``@pytest.mark.django_db``
# (NOT ``seeded_orm`` → NOT auto-tiered ``parity`` → Tier-1).


@pytest.mark.django_db
def test_auth_open_when_stats_password_unset(settings) -> None:
    """Dev mode: ``STATS_PASSWORD`` empty → gate is a NO-OP, endpoint open.

    Parity with ``backend/app/auth.py:23-24`` and
    ``backend/tests/test_api.py::test_stats_is_accessible_in_dev_mode``.
    """
    _skip_unless_postgres()
    from django.test import RequestFactory

    from api.schemas.stats import StatsOut
    from api.stats import get_stats

    settings.STATS_PASSWORD = ""
    out = get_stats(RequestFactory().get("/api/stats"))
    # dev-open → the StatsOut object (not an HttpResponse 401).
    assert isinstance(out, StatsOut)
    assert out.total_visits == 0  # empty isolated DB
    assert out.avg_session_seconds == 0.0
    assert isinstance(out.avg_session_seconds, float)
    assert out.devices == []
    assert out.per_category == []
    assert out.per_race == []
    assert out.per_rider == []
    assert out.top_comparisons == []
    assert out.recent == []


@pytest.mark.django_db
def test_auth_401_without_creds_when_password_set(settings) -> None:
    """``STATS_PASSWORD`` set + no creds → 401 ``{"detail":"Not
    authenticated"}`` + ``WWW-Authenticate: Basic realm="stats"``.

    Ported ``backend/tests/test_api.py::test_stats_requires_auth_when_
    password_set`` (the unauth branch). Byte-exact body verified empirically
    against the spun FastAPI oracle.
    """
    from django.test import RequestFactory

    from api.stats import get_stats

    settings.STATS_PASSWORD = "correct-horse-battery-staple"
    resp = get_stats(RequestFactory().get("/api/stats"))
    assert resp.status_code == 401
    assert resp.content == b'{"detail":"Not authenticated"}'
    assert resp["WWW-Authenticate"] == 'Basic realm="stats"'
    assert resp["WWW-Authenticate"].lower().startswith("basic")
    assert resp["Content-Type"].startswith("application/json")


@pytest.mark.django_db
def test_auth_401_with_wrong_password_when_password_set(settings) -> None:
    """Wrong password → 401 ``{"detail":"Invalid credentials"}`` + header.

    Ported ``test_stats_requires_auth_when_password_set`` (the bad-pw
    branch). The DISTINCT detail string ("Invalid credentials" vs "Not
    authenticated") is part of the byte-parity contract — Ninja's generic
    ``auth=`` rejection would NOT produce it, which is why S5 ports the gate
    explicitly.
    """
    from django.test import RequestFactory

    from api.stats import get_stats

    settings.STATS_PASSWORD = "correct-horse-battery-staple"
    cred = base64.b64encode(b"anyone:wrong-password").decode()
    resp = get_stats(
        RequestFactory().get(
            "/api/stats", HTTP_AUTHORIZATION="Basic " + cred
        )
    )
    assert resp.status_code == 401
    assert resp.content == b'{"detail":"Invalid credentials"}'
    assert resp["WWW-Authenticate"] == 'Basic realm="stats"'


@pytest.mark.django_db
def test_auth_reachable_with_correct_creds_when_password_set(
    settings,
) -> None:
    """Correct password → endpoint reachable (any non-empty username).

    Ported ``test_stats_requires_auth_when_password_set`` (the ok branch).
    Username is NEVER checked — ``("anyone", <pw>)`` succeeds, mirroring
    ``backend/app/auth.py`` ("The username is not checked").
    """
    _skip_unless_postgres()
    from django.test import RequestFactory

    from api.schemas.stats import StatsOut
    from api.stats import get_stats

    settings.STATS_PASSWORD = "correct-horse-battery-staple"
    cred = base64.b64encode(
        b"anyone:correct-horse-battery-staple"
    ).decode()
    out = get_stats(
        RequestFactory().get(
            "/api/stats", HTTP_AUTHORIZATION="Basic " + cred
        )
    )
    assert isinstance(out, StatsOut)  # passed the gate → ran aggregation
    assert out.total_visits == 0


@pytest.mark.django_db
def test_auth_401_on_unparseable_basic_header(settings) -> None:
    """Malformed Basic header → 401 ``{"detail":"Not authenticated"}``.

    FastAPI's ``HTTPBasic(auto_error=False)`` yields ``None`` for an
    unparseable header (bad base64, no ':' separator, wrong scheme) → the
    "Not authenticated" branch, exactly as X2's ``api/docs.py`` ports it and
    as the spun oracle was verified to behave.
    """
    from django.test import RequestFactory

    from api.stats import get_stats

    settings.STATS_PASSWORD = "secret"
    rf = RequestFactory()

    bad_b64 = get_stats(
        rf.get("/api/stats", HTTP_AUTHORIZATION="Basic !!notbase64==")
    )
    assert bad_b64.status_code == 401
    assert bad_b64.content == b'{"detail":"Not authenticated"}'

    no_colon = get_stats(
        rf.get(
            "/api/stats",
            HTTP_AUTHORIZATION="Basic "
            + base64.b64encode(b"nocolon").decode(),
        )
    )
    assert no_colon.status_code == 401
    assert no_colon.content == b'{"detail":"Not authenticated"}'

    wrong_scheme = get_stats(
        rf.get("/api/stats", HTTP_AUTHORIZATION="Bearer sometoken")
    )
    assert wrong_scheme.status_code == 401
    assert wrong_scheme.content == b'{"detail":"Not authenticated"}'


# ===========================================================================
# 2. Aggregation numbers on a controlled Visit fixture
#    (``@pytest.mark.django_db`` isolated test DB — Tier-1; see module
#    docstring for why this is NOT ``seeded_orm``)
# ===========================================================================


def _seed_visits():
    """Insert a controlled Visit fixture exercising every aggregation path.

    Returns ``now`` (UTC) so the test can reason about today/7d/30d windows.
    """
    from datetime import datetime, timezone

    from core.models import Visit

    now = datetime.now(timezone.utc)
    Visit.objects.bulk_create(
        [
            # leaderboard page → per_category
            Visit(timestamp=now, page="leaderboard", category="expert",
                  season_year=2025, device_type="desktop",
                  visitor_id="v1", session_id="s1"),
            Visit(timestamp=now, page="leaderboard", category="expert",
                  season_year=2025, device_type="mobile",
                  visitor_id="v2", session_id="s2"),
            Visit(timestamp=now, page="leaderboard", category="standard",
                  season_year=2025, device_type="mobile",
                  visitor_id="v2", session_id="s2"),
            # rider page → per_rider
            Visit(timestamp=now, page="rider", rider_slug="ivan-ivanov-7",
                  season_year=2025, device_type="desktop",
                  visitor_id="v1", session_id="s1"),
            # race page → per_race
            Visit(timestamp=now, page="race", event_slug="r1-2025",
                  season_year=2025, device_type="desktop",
                  visitor_id="v1", session_id="s1"),
            # compare page → top_comparisons; (a,b) appears twice, (c,d) once
            Visit(timestamp=now, page="compare", rider_slug="a-a-1",
                  compared_with_slug="b-b-2", device_type="desktop",
                  visitor_id="v1", session_id="s1"),
            Visit(timestamp=now, page="compare", rider_slug="a-a-1",
                  compared_with_slug="b-b-2", device_type="mobile",
                  visitor_id="v3", session_id="s3"),
            Visit(timestamp=now, page="compare", rider_slug="c-c-3",
                  compared_with_slug="d-d-4", device_type="mobile",
                  visitor_id="v4", session_id="s4"),
        ]
    )
    return now


@pytest.mark.django_db
def test_aggregation_numbers_on_fixture(settings) -> None:
    """Aggregation numbers match the FastAPI semantics on a fixed dataset.

    Ports the spirit of ``backend/tests/test_api.py`` stats assertions
    (keys/types present) AND pins the actual counts the SQLAlchemy → Django
    ORM translation must produce on a controlled fixture. ``settings``
    leaves ``STATS_PASSWORD`` at its empty test default (dev-open) so the
    aggregation path runs.
    """
    _skip_unless_postgres()
    from django.test import RequestFactory

    from api.stats import get_stats

    _seed_visits()
    out = get_stats(RequestFactory().get("/api/stats"))

    assert out.total_visits == 8
    # 4 distinct non-empty visitor_ids (v1..v4) seen today
    assert out.unique_visitors_today == 4
    assert out.unique_visitors_7d == 4
    assert out.unique_visitors_30d == 4
    # 4 distinct non-empty session_ids (s1..s4) today
    assert out.sessions_today == 4

    # devices: count(id) grouped by device_type → desktop 4, mobile 4
    devices = {d.device_type: d.count for d in out.devices}
    assert devices == {"desktop": 4, "mobile": 4}

    # per_category (page='leaderboard', category not null): expert 2025 ×2,
    # standard 2025 ×1 — ordered by count desc.
    pc = [(c.category, c.season_year, c.count) for c in out.per_category]
    assert pc == [("expert", 2025, 2), ("standard", 2025, 1)]

    # per_race (page='race', event_slug not null)
    pr = [(x.season_year, x.event_slug, x.count) for x in out.per_race]
    assert pr == [(2025, "r1-2025", 1)]

    # per_rider (page='rider', rider_slug not null)
    prd = [(x.season_year, x.rider_slug, x.count) for x in out.per_rider]
    assert prd == [(2025, "ivan-ivanov-7", 1)]

    # top_comparisons (page='compare'): (a-a-1,b-b-2) ×2 ranks above
    # (c-c-3,d-d-4) ×1 — the S5 acceptance "incl. top_comparisons".
    tc = [(t.slug_a, t.slug_b, t.count) for t in out.top_comparisons]
    assert tc == [("a-a-1", "b-b-2", 2), ("c-c-3", "d-d-4", 1)]

    # recent: newest first, capped at 25 (only 8 here)
    assert len(out.recent) == 8
    assert all(hasattr(v, "timestamp") for v in out.recent)

    # avg_session_seconds is a JSON-number float (the Decimal/float guard).
    assert isinstance(out.avg_session_seconds, float)
    assert out.avg_session_seconds >= 0.0


@pytest.mark.django_db
def test_avg_session_seconds_matches_postgres_epoch_semantics(
    settings,
) -> None:
    """``avg_session_seconds`` = avg over sessions of
    (epoch(max ts) - epoch(min ts)), single-hit sessions contributing 0.

    Byte-faithful semantics of the SQLAlchemy subquery
    ``avg(EXTRACT(epoch FROM max(ts)) - EXTRACT(epoch FROM min(ts)))``
    grouped by ``session_id``, coalesced to 0.0. Construct a known dataset:
    one 300-second session + three single-hit (0s) sessions → mean = 75.0.
    """
    _skip_unless_postgres()
    from datetime import datetime, timedelta, timezone

    from django.test import RequestFactory

    from api.stats import get_stats
    from core.models import Visit

    now = datetime.now(timezone.utc)
    Visit.objects.bulk_create(
        [
            Visit(timestamp=now, page="home", device_type="desktop",
                  visitor_id="v1", session_id="long"),
            Visit(timestamp=now + timedelta(seconds=300), page="home",
                  device_type="desktop", visitor_id="v1",
                  session_id="long"),
            Visit(timestamp=now, page="home", device_type="desktop",
                  visitor_id="v2", session_id="short1"),
            Visit(timestamp=now, page="home", device_type="desktop",
                  visitor_id="v3", session_id="short2"),
            Visit(timestamp=now, page="home", device_type="desktop",
                  visitor_id="v4", session_id="short3"),
        ]
    )
    out = get_stats(RequestFactory().get("/api/stats"))
    # (300 + 0 + 0 + 0) / 4 sessions = 75.0
    assert out.avg_session_seconds == pytest.approx(75.0)


# ===========================================================================
# 3. Byte-parity vs the frozen FastAPI oracle — COPIED from F3's
#    tests/test_reference_parity.py template, scoped to the S5 surface.
#    (``parity_rig`` → auto-tiered Tier-2; SKIPs if both stacks cannot spin)
# ===========================================================================

# The S5 public surface. ``seed_data/`` carries NO visit rows (visits are
# runtime analytics, never golden data), so both seeded DBs return the
# empty-aggregation shape — the realistic seeded state. The parity rig proves
# THAT serialization is byte-identical (every key, the ``0`` ints, the
# ``0.0`` float, the empty arrays, declaration key order, the pinned
# renderer's compact/Cyrillic-safe spec) AND the auth-gate 401
# bodies/headers are byte-identical to the spun oracle.
STATS_PATH = "/api/stats"


def test_stats_endpoint_byte_parity_dev_open(
    parity_rig, assert_json_parity
) -> None:
    """S5 stats == frozen FastAPI oracle, byte-for-byte (dev-open path).

    Both subprocess stacks boot WITHOUT ``STATS_PASSWORD`` set (the parity
    rig's ``_Subapp`` inherits the test env, which has no ``STATS_PASSWORD``)
    — so the gate is the dev-mode no-op on BOTH and ``/api/stats`` returns
    200 with the (empty, since neither seeded DB has visit rows) aggregation.
    Proves the empty-aggregation serialization (keys, ``0`` / ``0.0``, empty
    arrays, key order, pinned renderer spec) is byte-identical.
    """
    old = parity_rig.old(STATS_PATH)
    new = parity_rig.new(STATS_PATH)
    assert old.status_code == 200, old.content[:300]
    assert_json_parity(old, new)
    # the realistic seeded state: no visit rows → zeroed/empty aggregation.
    body = json.loads(new.content)
    assert body["total_visits"] == 0
    assert body["avg_session_seconds"] == 0.0
    assert body["devices"] == []
    assert body["top_comparisons"] == []
    assert body["recent"] == []
    assert list(body.keys()) == [
        "total_visits",
        "unique_visitors_today",
        "unique_visitors_7d",
        "unique_visitors_30d",
        "sessions_today",
        "avg_session_seconds",
        "devices",
        "per_category",
        "per_race",
        "per_rider",
        "top_comparisons",
        "recent",
    ]


def test_stats_dev_open_response_keys_present(parity_rig) -> None:
    """Ported ``backend/tests/test_api.py::test_stats_is_accessible_in_dev_
    mode`` — the dev-mode reachability + response-shape contract, asserted on
    the NEW app spun by the parity rig (the oracle side is covered by the
    byte-parity test above).
    """
    new = parity_rig.new(STATS_PATH)
    assert new.status_code == 200
    body = json.loads(new.content)
    assert "total_visits" in body
    assert "unique_visitors_today" in body
    assert "sessions_today" in body
    assert "avg_session_seconds" in body
    assert isinstance(body["devices"], list)
    assert isinstance(body["per_race"], list)
    assert isinstance(body["per_rider"], list)
    assert isinstance(body["recent"], list)
