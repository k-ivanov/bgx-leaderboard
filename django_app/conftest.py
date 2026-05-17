"""F3 test harness — conftest + DB + 2025 golden fixtures + clients + rig.

Replaces the F1 placeholder conftest (which only had to let the scaffold
suite run with zero real tests). This is the shared harness EVERY slice
(S1–S7) and X4 imports — decision I7-test=A. No slice ships its own DB
fixture, its own oracle, or a bespoke lookup; they all come from here +
``tests/parity.py``.

The three-database parity architecture (decision I7-test=A)
-----------------------------------------------------------
The F2 ``--fake-initial`` adoption (I2-arch=A) means the new app NEVER issues
``CREATE TABLE`` for the 8 domain tables in prod — it adopts the live
prod-shaped schema. The honest test substrate is therefore the REAL schema
seeded with the 2025 golden data, NOT a Django-built ephemeral one. But F2's
``@pytest.mark.django_db`` model tests legitimately want a clean isolated
schema (they ``.create()`` rows). One shared DB cannot satisfy both — the
shared-state contamination that naively breaks F2's ``create(year=2025)``
against the committed golden 2025 row. So F3 uses THREE databases:

* ``bgx_oracle`` — the FROZEN ``backend/`` FastAPI app's DB (parity oracle).
* ``bgx_django`` — the NEW Django app's DB. BOTH are seeded from the SAME
  ``seed_data/`` so any byte diff is a real divergence, never data skew.
* pytest-django's default ``test_<…>`` — created/migrated/destroyed by
  pytest-django as usual for ``@pytest.mark.django_db`` model tests (F2,
  write-path slices). UNTOUCHED by this conftest → F2 isolation preserved.

The parity rig (``tests/parity.ParityRig``) spins BOTH apps as SUBPROCESSES
(each on its own venv + its own DB) and diffs over HTTP — fully decoupled
from pytest-django's DB lifecycle. F3's own DB-unit tests (resolvers,
schemas) read the seeded ``bgx_django`` read-only via ``seeded_orm`` (an
explicit unblocked connection — they do NOT use ``@pytest.mark.django_db``,
so they never engage pytest-django's test-DB machinery and never collide
with F2).

Public fixtures
---------------
* ``seeded_orm``        — Django ORM bound to the seeded ``bgx_django``
                          (read-only for the 8 domain tables; idempotent
                          seed check). For F3 unit tests.
* ``parity_rig``        — session-scoped ``ParityRig`` (both stacks spun) or
                          a clean skip with the exact command.
* ``django_client``     — Django ``test.Client`` (pytest-django default DB;
                          for non-parity routing/header tests).
* ``assert_json_parity``— re-exported from ``tests.parity``.

NEVER fakes a green parity result: if a stack can't be spun the parity
fixtures ``pytest.skip`` with a precise reason + the exact command.
"""

from __future__ import annotations

import os
import socket

import pytest

# --- F1-compatible DB bootstrap (runs BEFORE Django settings import) -------
# pytest-django's default DB is derived from DATABASE_URL. Default it to the
# canonical dev DB so `@pytest.mark.django_db` model tests (F2 etc.) get the
# usual isolated `test_bgx`. If no Postgres at all → keep the F1 sqlite
# :memory: fallback so metadata/no-DB suites still run.
_DEFAULT_DB_URL = "postgresql://bgx:bgx@localhost:5432/bgx"
# The seeded DB F3's unit tests + the new-app parity subprocess read.
SEEDED_NEW_DB_URL = os.getenv(
    "NEW_DATABASE_URL", "postgresql://bgx:bgx@localhost:5432/bgx_django"
)


def _tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pg_host_port(url: str) -> tuple[str, int]:
    """``postgresql[+driver]://…:PORT/db`` → ``(host, port)``.

    Strips any SQLAlchemy ``+driver`` suffix so ``urlparse`` sees a plain
    scheme, then extracts the host/port the seeded DB actually lives at —
    so reachability is probed against the URL we will bind to, NOT a
    hardcoded ``localhost:5432`` (the connection-rebind determinism bug:
    the old probe could pass while the real seeded host was unreachable).
    """
    from urllib.parse import urlparse

    clean = url
    for pre in (
        "postgresql+psycopg2://",
        "postgresql+psycopg://",
        "postgres+psycopg2://",
    ):
        if clean.startswith(pre):
            clean = "postgresql://" + clean[len(pre):]
            break
    try:
        p = urlparse(clean)
        return p.hostname or "localhost", p.port or 5432
    except Exception:
        return "localhost", 5432


if not os.getenv("DATABASE_URL"):
    if _tcp_open("localhost", 5432):
        os.environ["DATABASE_URL"] = _DEFAULT_DB_URL
    else:
        os.environ.setdefault("DJANGO_ALLOW_NO_DB", "1")


def _seeded_pg_reachable() -> bool:
    """TCP-probe the host/port the ``seeded_orm`` fixture will actually bind
    to (``SEEDED_NEW_DB_URL``), not a hardcoded ``localhost:5432``.

    A green here is necessary-but-not-sufficient: ``seeded_orm`` ALSO
    verifies the bound connection with a real query and SKIPs (never
    ERRORs / never silently uses the sqlite no-DB fallback) if the
    connection cannot actually be opened — robust to intermittent
    reachability between this probe and the bind.
    """
    if os.getenv("DJANGO_ALLOW_NO_DB"):
        return False
    host, port = _pg_host_port(SEEDED_NEW_DB_URL)
    return _tcp_open(host, port)


def _seeded_skip_message() -> str:
    """Precise skip reason + the exact command to start + seed Postgres."""
    host, port = _pg_host_port(SEEDED_NEW_DB_URL)
    return (
        f"seeded Postgres for the bgx_django parity DB unreachable at "
        f"{host}:{port} (seeded_orm requires a live, seeded Postgres — it "
        f"never falls back to the sqlite no-DB path). Start + seed it:\n"
        f"  docker compose up -d postgres\n"
        f"  cd backend && DATABASE_URL={SEEDED_NEW_DB_URL} "
        f".venv/bin/python -m alembic upgrade head && "
        f"DATABASE_URL={SEEDED_NEW_DB_URL} "
        f".venv/bin/python -m scripts.seed_all"
    )


@pytest.fixture(scope="session")
def seeded_orm(django_db_blocker):
    """Django ORM bound to the seeded ``bgx_django`` DB (read-only, idempotent).

    F3 unit tests (resolvers / schemas) that need golden data use THIS instead
    of ``@pytest.mark.django_db``. It rebinds the ``default`` connection to
    ``bgx_django`` (the SAME DB the new-app parity subprocess reads, seeded
    from ``seed_data/``) and unblocks DB access WITHOUT engaging pytest-django's
    test-DB create/migrate/destroy — so F2's isolated ``django_db`` tests are
    completely unaffected. Tests using this fixture MUST stay read-only on the
    8 domain tables (parity invariant).
    """
    if not _seeded_pg_reachable():
        pytest.skip(_seeded_skip_message())

    import dj_database_url
    from django.db import connections

    # Point the default connection at the seeded bgx_django DB for this
    # session. config.settings already stripped any +driver suffix logic;
    # here we just hand Django the bare seeded URL.
    cfg = dj_database_url.parse(SEEDED_NEW_DB_URL, conn_max_age=600)
    cfg["ENGINE"] = "django.db.backends.postgresql"
    default = connections.databases["default"]
    saved = dict(default)
    default.update(cfg)
    default.setdefault("TEST", {})
    # Belt-and-suspenders: nothing should create/destroy this DB.
    default["TEST"]["NAME"] = cfg["NAME"]
    default["TEST"]["MIGRATE"] = False
    # Drop any connection opened against the old config (incl. a stale
    # sqlite :memory: handle from the settings no-DB fallback path).
    connections["default"].close()

    def _restore() -> None:
        connections["default"].close()
        default.clear()
        default.update(saved)

    with django_db_blocker.unblock():
        # Verify the rebound connection ACTUALLY works before any test runs.
        # The TCP probe above can pass while the seeded DB is unreachable at
        # bind time (intermittent reachability, wrong port/host, sqlite
        # no-DB fallback already loaded into the settings DATABASES). A
        # Postgres-REQUIRED fixture must NEVER let that surface as an
        # `sqlite3.OperationalError: no such table` ERROR or a raw
        # `django.db.OperationalError` — it cleanly SKIPs with the exact
        # command instead (never fakes a green, never the sqlite path).
        from django.db import OperationalError as DjangoOperationalError
        from django.db import connection as _conn

        try:
            if _conn.vendor != "postgresql":
                raise DjangoOperationalError(
                    f"seeded_orm bound a {_conn.vendor!r} connection, not "
                    f"postgresql (settings no-DB sqlite fallback was active)"
                )
            with _conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        except Exception as exc:  # connection unreachable / wrong backend
            _restore()
            pytest.skip(f"{_seeded_skip_message()}\n  (probe-then-bind verify failed: {exc})")

        from core.models import Season

        if not Season.objects.filter(year=2025).exists():
            _restore()
            pytest.skip(
                f"bgx_django not seeded with the 2025 golden data. Seed it:\n"
                f"  cd backend && DATABASE_URL={SEEDED_NEW_DB_URL} "
                f".venv/bin/python -m scripts.seed_all"
            )
        yield

    # Restore the original default config + drop the temporary connection.
    _restore()


@pytest.fixture()
def django_client():
    """Django ``test.Client`` against pytest-django's default test DB.

    For non-parity routing/header tests. Parity tests use ``parity_rig``
    (subprocesses) instead, so this never needs the golden data.
    """
    from django.test import Client

    return Client()


@pytest.fixture(scope="session")
def parity_rig():
    """Spin BOTH stacks (FastAPI oracle + new Django app) as subprocesses.

    Skips with a precise reason + exact command if either stack can't be
    spun in this sandbox — NEVER fakes a green parity result (F3 acceptance
    requirement).
    """
    from tests.parity import OracleUnavailable, ParityRig

    reason = ParityRig.unavailable_reason()
    if reason is not None:
        pytest.skip(f"parity rig unavailable: {reason}")

    try:
        with ParityRig() as rig:
            yield rig
    except OracleUnavailable as exc:  # pragma: no cover - sandbox-dependent
        pytest.skip(f"parity rig could not be spun: {exc}")


@pytest.fixture()
def assert_json_parity():
    """Re-export the F3 JSON+format parity assertion as a fixture."""
    from tests.parity import assert_json_parity as _impl

    return _impl


# Two-tier verification (orchestrator decision B, 2026-05-17).
#
# Tier-2 = any test that needs a seeded Postgres: it consumes the read-only
# ``seeded_orm`` fixture or the subprocess ``parity_rig``. Auto-mark those
# ``parity`` so:
#   * the fast per-slice gate runs ``pytest -m "not parity"`` (no DB, locked
#     venv, ~seconds) and must be fully green to land a serial slice;
#   * the Postgres-backed gate runs ``pytest -m parity`` at every integration
#     checkpoint and as the hard I1 cutover gate.
# Detection is by FIXTURE NAME, so every S1–S7 slice that copies F3's
# reference/parity template is tiered correctly with zero extra annotation.
_PG_FIXTURES = {"seeded_orm", "parity_rig"}


def pytest_collection_modifyitems(config, items):  # noqa: D401
    for item in items:
        if _PG_FIXTURES & set(getattr(item, "fixturenames", ())):
            item.add_marker(pytest.mark.parity)
