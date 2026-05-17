"""pytest-django bootstrap (F1 scaffold harness).

F1 only needs the harness to RUN (zero real tests is acceptable per the task
plan). The full parity rig — 2025 golden fixtures, the Ninja ``TestClient``,
and the old↔new ``assert_json_parity`` rig that spins the frozen ``backend/``
app — is F3's responsibility, not F1's.

This conftest does one F1 thing: if ``DATABASE_URL`` is not set, fall back to
an in-memory SQLite test DB so the scaffold suite runs in CI / a fresh
checkout without a live Postgres. When ``DATABASE_URL`` IS set, pytest-django
uses the real (Postgres) config from ``config.settings`` and creates an
isolated test database as usual.
"""

import os

# Must run BEFORE Django settings import. config.settings honors this env var
# (see the DATABASES block + the OLD→DJANGO mapping table there).
if not os.getenv("DATABASE_URL"):
    os.environ.setdefault("DJANGO_ALLOW_NO_DB", "1")
