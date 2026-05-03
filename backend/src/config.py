"""Configuration and constants for the BGX Navigation Dashboard."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

APP_VERSION = "0.1.0"

BASE_DIR = Path(__file__).parent.parent

DEFAULT_PORT = 5001
DEFAULT_HOST = "0.0.0.0"


def _normalize_database_url(url: str) -> str:
    # Railway provides postgres:// but SQLAlchemy 2.x requires postgresql://
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env for local dev, "
            "or attach a Postgres plugin on Railway."
        )
    return _normalize_database_url(url)


DEFAULT_SEASON_YEAR = int(os.getenv("DEFAULT_SEASON_YEAR", "2026"))
