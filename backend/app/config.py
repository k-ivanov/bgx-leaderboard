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
