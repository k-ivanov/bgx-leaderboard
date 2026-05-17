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


if not os.getenv("DATABASE_URL"):
    if _tcp_open("localhost", 5432):
        os.environ["DATABASE_URL"] = _DEFAULT_DB_URL
    else:
        os.environ.setdefault("DJANGO_ALLOW_NO_DB", "1")


def _postgres_reachable() -> bool:
    return _tcp_open("localhost", 5432) and not os.getenv("DJANGO_ALLOW_NO_DB")


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
    if not _postgres_reachable():
        pytest.skip(
            "no Postgres on localhost:5432. Start + seed it:\n"
            "  docker compose up -d postgres\n"
            "  cd backend && DATABASE_URL=" + SEEDED_NEW_DB_URL + " "
            ".venv/bin/python -m alembic upgrade head && "
            "DATABASE_URL=" + SEEDED_NEW_DB_URL + " "
            ".venv/bin/python -m scripts.seed_all"
        )

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
    # Drop any connection opened against the old config.
    connections["default"].close()

    with django_db_blocker.unblock():
        from core.models import Season

        if not Season.objects.filter(year=2025).exists():
            pytest.skip(
                f"bgx_django not seeded with the 2025 golden data. Seed it:\n"
                f"  cd backend && DATABASE_URL={SEEDED_NEW_DB_URL} "
                f".venv/bin/python -m scripts.seed_all"
            )
        yield

    # Restore the original default config + drop the rebporary connection.
    connections["default"].close()
    default.clear()
    default.update(saved)


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
