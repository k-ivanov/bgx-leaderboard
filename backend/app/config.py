"""App-level configuration. Thin wrapper around ``src.config`` + new FastAPI-era env vars."""

import os

from src.config import (  # noqa: F401 — re-export for callers
    APP_VERSION,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEFAULT_SEASON_YEAR,
    get_database_url,
)

# Empty string means "no auth required" — local dev default. In Railway, set this
# env var to require HTTP Basic on `/api/stats` (see eng-review SC-1 / N6).
STATS_PASSWORD = os.getenv("STATS_PASSWORD", "")

# /api/track payload cap and rate limit (eng-review SC-2 / N7).
TRACK_MAX_BYTES = 2048
TRACK_RATE_LIMIT = "10/minute"

# Admin panel auth. ADMIN_PASSWORD is the primary gate.
#   - When empty:   /admin routes return 403 (explicit opt-in; no silent dev bypass,
#                   since the admin panel can write/delete data).
#   - When set:     session-based login at /admin/login with ADMIN_USERNAME +
#                   ADMIN_PASSWORD. Sessions signed with ADMIN_SESSION_SECRET.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ADMIN_SESSION_SECRET = os.getenv(
    "ADMIN_SESSION_SECRET",
    # Dev-only fallback. In any deployment, set this to a long random string.
    "dev-only-insecure-please-override-in-production",
)
