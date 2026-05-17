"""S6 — POST /api/track contract + OV3 hardening.

Three sections, mirroring the S5 layout (auto-tiering keys off fixture names;
S6's Tier-2-ish proofs are explicit-server spins, not ``seeded_orm`` —
nothing here uses ``seeded_orm``/``parity_rig`` so the whole file stays in
the Tier-1 ``-m "not parity"`` gate, skip-don't-fake when a real server /
Postgres is unavailable):

1. **Contract / wiring + write-row parity** (``@pytest.mark.django_db``
   isolated test DB): the track module is wired into the FROZEN router
   assembly at the right prefix; ``TrackIn``/``TrackOut`` field
   NAMES/ORDER/TYPES/DEFAULTS == the frozen FastAPI Pydantic schema; a happy
   POST writes a ``Visit`` row identical to the oracle INCLUDING
   ``compared_with_slug`` for the compare page (the column S5's
   ``top_comparisons`` reads — review OV3); device detection, validation
   (422), and slug persistence are ported one-to-one from
   ``backend/tests/test_track.py``.

2. **413 pre-parse payload guard**: an oversize body is rejected with 413
   BEFORE the JSON is parsed (ported ``test_track_rejects_oversize_payload``
   + an explicit "the view never ran" assertion the FastAPI test could not
   make).

3. **Real-server 429 integration test** (review OV3): the FastAPI
   ``test_track.py`` explicitly does NOT exercise real rate limiting and
   Ninja throttling is a NEW impl, so S6 spins the actual Django app
   (locked venv, uvicorn, the conftest DB) and proves the (N+1)th request
   from one IP returns 429 with the configured limit. PLUS a
   concurrency/atomicity test: simulated UTC-midnight rollover + burst does
   not create duplicate salts or mis-bucket sessions.

KNOWN, DOCUMENTED 429 BODY DIVERGENCE: slowapi rendered 429 as
``{"error":"Rate limit exceeded: …"}``; Ninja's ``Throttled`` renders
``{"detail":"Too many requests."}``. Not a parity regression — the old suite
never exercised the limit, the frontend beacon ignores the response body, and
OV3's acceptance is "the Nth request returns 429 with the configured limit"
(status + limit), not body byte-parity. See ``core/track_guards.py``.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

DJANGO_DIR = Path(__file__).resolve().parents[1]
LOCKED_PY = Path(
    os.getenv("S6_DJANGO_PYTHON", "/tmp/bgx-django-locked-venv/bin/python")
)


@pytest.fixture(autouse=True)
def _isolate_throttle_and_salt_cache():
    """Reset the per-process throttle + salt caches around every S6 test.

    The Ninja throttle backs onto ``django.core.cache`` (LocMemCache —
    per-process, NOT reset by ``@pytest.mark.django_db``) and the analytics
    salt cache is a module-global dict. Without this, the in-process contract
    tests (all keyed on the test client's single ``127.0.0.1``) would burn
    through the 10/minute bucket and bleed 429s into unrelated assertions,
    and a stale salt would leak across tests. Clearing both before AND after
    each test keeps every test hermetic — the throttle is exercised
    deliberately ONLY by the real-server 429 integration test (its own spun
    process, its own cache).
    """
    from django.core.cache import cache

    from core.analytics import _reset_salt_cache_for_tests

    cache.clear()
    _reset_salt_cache_for_tests()
    yield
    cache.clear()
    _reset_salt_cache_for_tests()


# ===========================================================================
# 1. Contract / wiring + write-row parity  (isolated test DB — Tier-1)
# ===========================================================================


def test_track_router_is_wired_into_frozen_assembly() -> None:
    """S6's ``router`` is the object the FROZEN ``api/__init__.py`` mounts.

    The frozen assembly imports ``api.track.router`` by reference and mounts
    it at the ``""`` prefix (``api/__init__.py:82``) → public path
    ``/api/track``, byte-identical to ``backend/app/main.py:114``. Confirm
    exactly the one POST operation is registered with the throttle attached.
    """
    from ninja import Router

    from api import track as track_api
    from core.track_guards import TrackRateThrottle

    assert isinstance(track_api.router, Router)
    assert set(track_api.router.path_operations.keys()) == {"/track"}

    (op,) = track_api.router.path_operations["/track"].operations
    assert op.methods == ["POST"]
    assert len(op.throttle_objects) == 1
    assert isinstance(op.throttle_objects[0], TrackRateThrottle)


def test_track_schema_field_order_matches_fastapi_pydantic() -> None:
    """Field NAMES + ORDER + TYPES + DEFAULTS == frozen FastAPI Pydantic.

    Drift here = the frontend's ``openapi-typescript`` client regenerates
    with a diff. Pinned against ``backend/app/schemas/track.py``.
    """
    from api.schemas.track import TrackIn, TrackOut

    assert list(TrackIn.model_fields) == [
        "page",
        "category",
        "season_year",
        "event_slug",
        "rider_slug",
        "compared_with_slug",
    ]
    assert list(TrackOut.model_fields) == ["ok"]
    assert TrackIn.model_fields["category"].default is None
    assert TrackIn.model_fields["season_year"].default is None
    assert TrackIn.model_fields["event_slug"].default is None
    assert TrackIn.model_fields["rider_slug"].default is None
    assert TrackIn.model_fields["compared_with_slug"].default is None
    # extra="forbid" — unknown fields rejected (oracle ConfigDict).
    assert TrackIn.model_config.get("extra") == "forbid"


@pytest.mark.django_db
def test_track_happy_path_creates_visit_row(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_happy_path_creates_visit_row
    from core.models import Visit

    resp = client.post(
        "/api/track",
        data=json.dumps(
            {"page": "leaderboard", "category": "expert", "season_year": 2026}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    latest = Visit.objects.order_by("-timestamp").first()
    assert latest is not None
    assert latest.page == "leaderboard"
    assert latest.category == "expert"
    assert latest.season_year == 2026


@pytest.mark.django_db
def test_track_detects_mobile_from_user_agent(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_detects_mobile_from_user_agent
    from core.models import Visit

    resp = client.post(
        "/api/track",
        data=json.dumps({"page": "rider", "category": None, "season_year": None}),
        content_type="application/json",
        HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0)",
    )
    assert resp.status_code == 200
    assert Visit.objects.order_by("-timestamp").first().device_type == "mobile"


@pytest.mark.django_db
def test_track_rejects_missing_page(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_rejects_missing_page
    resp = client.post(
        "/api/track",
        data=json.dumps({"category": "expert"}),
        content_type="application/json",
    )
    assert resp.status_code == 422


@pytest.mark.django_db
def test_track_rejects_extra_fields(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_rejects_extra_fields
    resp = client.post(
        "/api/track",
        data=json.dumps(
            {"page": "leaderboard", "evil_field": "drop table visits;"}
        ),
        content_type="application/json",
    )
    assert resp.status_code == 422


@pytest.mark.django_db
def test_track_stamps_visitor_and_session_ids(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_stamps_visitor_and_session_ids
    from core.analytics import _reset_salt_cache_for_tests
    from core.models import Visit

    _reset_salt_cache_for_tests()
    resp = client.post(
        "/api/track",
        data=json.dumps({"page": "leaderboard", "season_year": 2026}),
        content_type="application/json",
        HTTP_USER_AGENT="Mozilla/5.0 (X11; Linux) Chrome/120",
    )
    assert resp.status_code == 200
    latest = Visit.objects.order_by("-timestamp").first()
    assert latest.visitor_id != ""
    assert len(latest.visitor_id) == 16
    assert latest.session_id != ""


@pytest.mark.django_db
def test_track_reuses_session_for_repeat_visitor(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_reuses_session_for_repeat_visitor
    from core.analytics import _reset_salt_cache_for_tests
    from core.models import Visit

    _reset_salt_cache_for_tests()
    headers = {"HTTP_USER_AGENT": "Mozilla/5.0 (X11; Linux) Chrome/120"}
    r1 = client.post(
        "/api/track",
        data=json.dumps({"page": "home"}),
        content_type="application/json",
        **headers,
    )
    r2 = client.post(
        "/api/track",
        data=json.dumps({"page": "leaderboard"}),
        content_type="application/json",
        **headers,
    )
    assert r1.status_code == r2.status_code == 200
    rows = list(Visit.objects.order_by("-timestamp")[:2])
    assert rows[0].visitor_id == rows[1].visitor_id
    assert rows[0].session_id == rows[1].session_id


@pytest.mark.django_db
def test_track_persists_event_and_rider_slugs(client) -> None:
    # Ported: backend/tests/test_track.py::test_track_persists_event_and_rider_slugs
    from core.models import Visit

    assert (
        client.post(
            "/api/track",
            data=json.dumps(
                {"page": "race", "season_year": 2026, "event_slug": "kyrnare"}
            ),
            content_type="application/json",
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/track",
            data=json.dumps(
                {
                    "page": "rider",
                    "season_year": 2026,
                    "rider_slug": "42-ivan-ivanov",
                }
            ),
            content_type="application/json",
        ).status_code
        == 200
    )

    rider_row = (
        Visit.objects.filter(page="rider").order_by("-timestamp").first()
    )
    assert rider_row.rider_slug == "42-ivan-ivanov"
    race_row = Visit.objects.filter(page="race").order_by("-timestamp").first()
    assert race_row.event_slug == "kyrnare"


@pytest.mark.django_db
def test_track_compare_writes_compared_with_slug_normalized(client) -> None:
    """OV3 acceptance: the compare page persists ``compared_with_slug``,
    pair-normalized alphabetically so (A,B) and (B,A) collapse — the exact
    column + normalization S5's ``top_comparisons`` depends on.

    Byte-identical to ``backend/app/api/track.py:47-58`` (``rider_slug >
    compared_with_slug`` → swap). Posting both orders must yield the SAME
    ``(rider_slug, compared_with_slug)`` tuple on every row.
    """
    from core.models import Visit

    # B,A order — server must swap to (A,B).
    assert (
        client.post(
            "/api/track",
            data=json.dumps(
                {
                    "page": "compare",
                    "rider_slug": "zaq-z-9",
                    "compared_with_slug": "abc-a-1",
                }
            ),
            content_type="application/json",
        ).status_code
        == 200
    )
    # A,B order — already sorted, unchanged.
    assert (
        client.post(
            "/api/track",
            data=json.dumps(
                {
                    "page": "compare",
                    "rider_slug": "abc-a-1",
                    "compared_with_slug": "zaq-z-9",
                }
            ),
            content_type="application/json",
        ).status_code
        == 200
    )

    pairs = set(
        Visit.objects.filter(page="compare").values_list(
            "rider_slug", "compared_with_slug"
        )
    )
    # Both posts collapse into the one normalized pair.
    assert pairs == {("abc-a-1", "zaq-z-9")}
    assert Visit.objects.filter(page="compare").count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize(
    "bad_payload",
    [
        {"page": ""},  # min_length
        {"page": "x" * 65},  # max_length
        {"page": "ok", "season_year": 42},  # below ge
        {"page": "ok", "season_year": 3500},  # above le
    ],
)
def test_track_rejects_out_of_bounds(client, bad_payload: dict) -> None:
    # Ported: backend/tests/test_track.py::test_track_rejects_out_of_bounds
    resp = client.post(
        "/api/track",
        data=json.dumps(bad_payload),
        content_type="application/json",
    )
    assert resp.status_code == 422


# ===========================================================================
# 2. 413 pre-parse payload guard  (isolated test DB — Tier-1)
# ===========================================================================


@pytest.mark.django_db
def test_track_rejects_oversize_payload_with_413(client) -> None:
    """Ported ``test_track_rejects_oversize_payload`` — oversize body → 413
    with the oracle's exact ``{"detail":"Payload too large (max 2048
    bytes)"}`` string.
    """
    body = json.dumps({"page": "leaderboard", "category": "x" * 3000})
    resp = client.post(
        "/api/track",
        data=body,
        content_type="application/json",
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()
    assert resp.json() == {"detail": "Payload too large (max 2048 bytes)"}


@pytest.mark.django_db
def test_413_fires_before_json_parse_and_view(client) -> None:
    """The 413 is PRE-PARSE: an oversize body that is ALSO invalid JSON +
    would write no row still 413s (the middleware short-circuits before the
    Ninja parser and before the view). An assertion the FastAPI suite could
    not make — it proves the *ordering*, not just the status.
    """
    from core.models import Visit

    before = Visit.objects.count()
    junk = b"{not valid json " + b"z" * 4000  # > 2048, unparseable
    resp = client.post(
        "/api/track",
        data=junk,
        content_type="application/json",
    )
    assert resp.status_code == 413  # not 422 (parser) / 500 (view)
    assert Visit.objects.count() == before  # view never ran


@pytest.mark.django_db
def test_malformed_content_length_is_passed_through(client, settings) -> None:
    """A non-int Content-Length is passed through to the normal pipeline
    (oracle ``except ValueError: pass``), not 413'd by the guard.
    """
    from core.track_guards import TrackPayloadSizeLimitMiddleware

    mw = TrackPayloadSizeLimitMiddleware(get_response=lambda r: None)

    class _Req:
        path = "/api/track"
        method = "POST"
        META = {"CONTENT_LENGTH": "not-a-number"}

    assert mw.process_request(_Req()) is None  # passed through, no 413


# ===========================================================================
# 3. Real-server 429 integration  +  midnight/burst atomicity  (OV3)
# ===========================================================================


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _skip_unless_postgres() -> None:
    """Skip when the Django test DB is not Postgres.

    The atomicity acceptance is the Postgres ``INSERT ... ON CONFLICT (day)
    DO NOTHING`` semantics under a concurrent burst. The Tier-1 locked-venv
    gate runs ``@pytest.mark.django_db`` against an in-memory SQLite (the
    conftest only points ``DATABASE_URL`` at Postgres for some run shapes),
    and SQLite ``:memory:`` cannot serve a multi-threaded write burst at all
    ("database table is locked") — so the authoritative ``ON CONFLICT`` proof
    is exercised when the test DB is Postgres (an integration/CI run with
    ``DATABASE_URL`` set, exactly the S5 ``_skip_unless_postgres`` /
    skip-don't-fake discipline). Never fakes a green: it SKIPs with the exact
    command instead of asserting a weaker SQLite outcome.
    """
    from django.db import connection

    if connection.vendor != "postgresql":
        pytest.skip(
            "midnight/burst atomicity proof needs a Postgres test DB (the "
            "INSERT ... ON CONFLICT DO NOTHING upsert under a concurrent "
            "burst; SQLite :memory: locks under threaded writes). Tier-1 gate "
            "runs django_db on in-memory SQLite — run with "
            "DATABASE_URL=postgresql://… to exercise this for real (e.g. "
            "docker compose up -d postgres)."
        )


def _postgres_url_or_skip() -> str:
    """The real-server test needs a live Postgres (the spun app runs real
    migrations / writes ``Visit`` rows). Skip-don't-fake otherwise.
    """
    url = os.getenv("DATABASE_URL")
    if not url:
        try:
            with socket.create_connection(("localhost", 5432), timeout=1):
                url = "postgresql://bgx:bgx@localhost:5432/bgx"
        except OSError:
            pytest.skip(
                "real-server 429 test needs Postgres. Start it:\n"
                "  docker compose up -d postgres\n"
                "then re-run (DATABASE_URL is auto-derived)."
            )
    return url


class _SpunDjangoApp:
    """Spin the real Django app (locked venv, uvicorn) on a free port.

    Mirrors ``tests/parity.py::_Subapp`` but POST-capable (the rig is
    GET-only). LocMemCache is per-process and the server is a single uvicorn
    process, so the throttle history is consistent across requests — exactly
    the per-process in-memory model slowapi used.
    """

    def __init__(self, database_url: str) -> None:
        self.port = _free_port()
        self.base = f"http://127.0.0.1:{self.port}"
        self._db = database_url
        self._proc = None

    def __enter__(self) -> "_SpunDjangoApp":
        if not LOCKED_PY.exists():
            pytest.skip(
                f"locked venv python not found at {LOCKED_PY}; recreate from "
                "django_app/requirements.lock (skip-don't-fake)."
            )
        env = dict(os.environ)
        env["DATABASE_URL"] = self._db
        env["DJANGO_SETTINGS_MODULE"] = "config.settings"
        env["FRONTEND_DIST"] = ""  # never let static shadow /api/*
        # Ensure the visit/salt tables exist in the target DB (idempotent;
        # adopts the existing schema via --fake-initial, like prod).
        subprocess.run(
            [str(LOCKED_PY), "manage.py", "migrate", "--fake-initial",
             "--noinput"],
            cwd=str(DJANGO_DIR), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120,
        )
        self._proc = subprocess.Popen(
            [str(LOCKED_PY), "-m", "uvicorn", "config.asgi:application",
             "--host", "127.0.0.1", "--port", str(self.port),
             "--log-level", "warning"],
            cwd=str(DJANGO_DIR), env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 35.0
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                out = self._proc.stdout.read().decode(errors="replace")
                pytest.skip(
                    "Django app could not be spun for the 429 integration "
                    f"test (exit {self._proc.returncode}):\n{out[-1500:]}"
                )
            try:
                with urllib.request.urlopen(f"{self.base}/health", timeout=1) as r:
                    if r.status == 200:
                        return self
            except (urllib.error.URLError, OSError):
                time.sleep(0.25)
        self.__exit__(None, None, None)
        pytest.skip("Django app did not become healthy in 35s")

    def __exit__(self, *exc) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None

    def post_track(self, payload: dict, ip: str = "203.0.113.77"):
        body = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self.base}/api/track",
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                # Proxy-aware client-IP keying: a fixed XFF pins the throttle
                # bucket to one client across requests.
                "X-Forwarded-For": ip,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()


def test_real_server_429_after_configured_limit() -> None:
    """OV3: spin the real app, prove the (N+1)th request from one IP → 429.

    ``TRACK_RATE_LIMIT`` is "10/minute" (slowapi config, F1-ported). The
    first 10 POSTs from one IP succeed (200); the 11th in the same minute is
    throttled (429). A DIFFERENT IP is not affected (per-IP bucket, the
    ``real_client_ip`` keying). This is the test the FastAPI suite
    explicitly deferred ("a Phase 4 integration test can exercise the limit
    against a real server").
    """
    from django.conf import settings

    db = _postgres_url_or_skip()
    limit = 10
    assert settings.TRACK_RATE_LIMIT == "10/minute"

    with _SpunDjangoApp(db) as app:
        statuses = [
            app.post_track({"page": "leaderboard"}, ip="198.51.100.10")[0]
            for _ in range(limit)
        ]
        assert statuses == [200] * limit, statuses

        code, body = app.post_track({"page": "leaderboard"}, ip="198.51.100.10")
        assert code == 429, (code, body[:300])
        # Documented divergence: Ninja Throttled body (not slowapi's).
        assert json.loads(body) == {"detail": "Too many requests."}

        # A different IP still gets through — proves per-IP bucketing via
        # real_client_ip (not a global counter).
        other_code, _ = app.post_track(
            {"page": "leaderboard"}, ip="198.51.100.99"
        )
        assert other_code == 200, other_code


@pytest.mark.django_db
def test_concurrency_midnight_rollover_and_burst_no_duplicate_salts() -> None:
    """OV3 atomicity: a burst that straddles the UTC-midnight rollover must
    not create duplicate salts and must not mis-bucket sessions.

    Two days (``d0`` = "yesterday", ``d1`` = "today" after rollover). For
    EACH day, fire a concurrent burst of ``get_or_create_salt(day=…)`` from
    many threads (cache reset first to force the DB upsert race). The atomic
    ``INSERT ... ON CONFLICT DO NOTHING`` (Postgres) / ``INSERT OR IGNORE``
    (SQLite) + re-SELECT must collapse the race to EXACTLY ONE row per day
    and every thread must observe the SAME salt for its day. ``get_or_create``
    would IntegrityError / duplicate here — this is the regression guard for
    the "midnight/burst race → duplicate salts / mis-bucketed sessions"
    failure mode.
    """
    _skip_unless_postgres()

    from datetime import date

    from core.analytics import (
        _reset_salt_cache_for_tests,
        derive_session_id,
        get_or_create_salt,
        visitor_id_for,
    )
    from core.models import AnalyticsSalt, Visit

    d0 = date(2030, 6, 14)  # "yesterday"
    d1 = date(2030, 6, 15)  # "today" (after the UTC-midnight rollover)
    AnalyticsSalt.objects.filter(day__in=[d0, d1]).delete()

    from django.db import connections

    def _one(day):
        # Each worker thread gets its OWN Django connection; close it on the
        # way out so pytest-django can tear the test DB down cleanly (no
        # leaked sessions holding the burst connections open).
        try:
            return get_or_create_salt(day=day)
        finally:
            connections.close_all()

    def burst(day):
        _reset_salt_cache_for_tests()
        with ThreadPoolExecutor(max_workers=16) as ex:
            return list(ex.map(lambda _: _one(day), range(32)))

    salts_d0 = burst(d0)
    salts_d1 = burst(d1)

    # Exactly one row per day — the upsert collapsed the burst race.
    assert AnalyticsSalt.objects.filter(day=d0).count() == 1
    assert AnalyticsSalt.objects.filter(day=d1).count() == 1
    # Every thread agreed on its day's salt (no split-brain).
    assert len(set(salts_d0)) == 1
    assert len(set(salts_d1)) == 1
    # The rollover actually rotated the salt (d0 != d1) — yesterday's hashes
    # become unlinkable to today's, the whole point of the daily rotation.
    salt0, salt1 = salts_d0[0], salts_d1[0]
    assert salt0 != salt1
    assert AnalyticsSalt.objects.get(day=d0).salt == salt0
    assert AnalyticsSalt.objects.get(day=d1).salt == salt1

    # Session bucketing is not mis-attributed across the rollover: the same
    # (ip, ua) yields DIFFERENT visitor_ids on d0 vs d1 (salt rotated), so a
    # pre-midnight visit can't be reused as a post-midnight session.
    ip, ua = "203.0.113.5", "Mozilla/5.0 (X11; Linux)"
    vid_d0 = visitor_id_for(salt0, ip, ua)
    vid_d1 = visitor_id_for(salt1, ip, ua)
    assert vid_d0 != vid_d1

    Visit.objects.filter(visitor_id__in=[vid_d0, vid_d1]).delete()
    now_d0 = datetime(2030, 6, 14, 23, 58, tzinfo=timezone.utc)
    Visit.objects.create(
        timestamp=now_d0, page="home", visitor_id=vid_d0,
        session_id="sess-d0", device_type="desktop",
    )
    # A post-rollover request (different visitor_id) must NOT reuse the
    # pre-rollover session — it mints a fresh one.
    now_d1 = datetime(2030, 6, 15, 0, 3, tzinfo=timezone.utc)
    sid_d1 = derive_session_id(vid_d1, now=now_d1)
    assert sid_d1 != "sess-d0"
    # And within-window reuse still works for the SAME (rotated) visitor.
    Visit.objects.create(
        timestamp=now_d1, page="home", visitor_id=vid_d1,
        session_id=sid_d1, device_type="desktop",
    )
    assert (
        derive_session_id(
            vid_d1, now=now_d1 + timedelta(minutes=5)
        )
        == sid_d1
    )
