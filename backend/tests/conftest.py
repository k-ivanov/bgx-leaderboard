"""Shared pytest fixtures.

Seeds the 2025 season once per session. The importer is idempotent (wipes
and rebuilds the 2025 rows), so running it alongside a module-scoped seed
fixture (e.g., ``test_standings_2025.py``) is safe.
"""

import pytest

from scripts.import_2025 import DEFAULT_CSV_DIR, import_2025


@pytest.fixture(scope="session", autouse=True)
def _seed_2025_session() -> None:
    import_2025(DEFAULT_CSV_DIR)
