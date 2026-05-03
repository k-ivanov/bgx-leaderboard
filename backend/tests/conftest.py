"""Shared pytest fixtures.

DB-backed tests opt in explicitly via ``@pytest.mark.usefixtures("seeded_db")``
(or a module-level ``pytestmark``). Tests that only exercise HTTP routing,
slug parsing, CORS absence, etc. run without Postgres.

The ``seeded_db`` fixture is idempotent: it runs ``alembic upgrade head`` and
then ``scripts.seed_all`` with ``wipe=True`` once per pytest session.
"""

import pytest
from alembic import command
from alembic.config import Config
from pathlib import Path


def _alembic_cfg() -> Config:
    """Alembic Config pointing at backend/alembic.ini regardless of cwd."""
    ini = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = Config(str(ini))
    # `script_location` in the ini file is relative; alembic resolves it
    # against the ini's directory, so no override needed.
    return cfg


@pytest.fixture(scope="session")
def seeded_db() -> None:
    """Apply migrations + wipe + reseed from ``seed_data/`` at the repo root."""
    command.upgrade(_alembic_cfg(), "head")
    from scripts.seed_all import seed_all
    seed_all(wipe=True)
