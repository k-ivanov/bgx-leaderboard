"""Wipe the championship tables and re-import every year folder in seed_data/.

Layout (repo root):

    seed_data/
        <year>/                e.g. 2024/, 2025/, 2026/
            *.csv              One CSV per (race, day). Filenames like
                                 hard_enduro_botevgrad-2024-day1.csv
                                 endurox_alba-damascena-2024-day1.csv
                                 hard_enduro_kirkovo_2025-day1.csv

Each CSV follows the unified 2024+ format — one row per rider per day,
with all categories in one file (dispatched via the `class` column).

Usage:
    python -m scripts.seed_all                 # wipe + reimport every year
    python -m scripts.seed_all --year 2026     # wipe + reimport one year only
    python -m scripts.seed_all --no-wipe       # add/update without wiping

Visit (analytics) rows are NOT deleted — only championship data (seasons,
categories, events, riders, event_results).
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

from sqlalchemy import delete

from src.db import get_session
from src.db.models import Season

from scripts.import_race_day import import_race_day


# seed_data lives at the repo root (sibling of backend/). Resolve from this
# file's location so cwd doesn't matter.
SEED_ROOT = Path(__file__).resolve().parents[2] / "seed_data"

_YEAR_RE = re.compile(r"^\d{4}$")


# ---------------------------------------------------------------------------
# Wipe
# ---------------------------------------------------------------------------

def wipe_championship_data() -> None:
    """Delete all championship data. Keeps Visit rows (analytics).

    ON DELETE CASCADE on Season → Category/Event/Rider/EventResult means a
    single Season delete cleans up everything downstream.
    """
    with get_session() as session:
        session.execute(delete(Season))
    print("✓ wiped championship data (visits preserved)")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _year_dirs(only_year: Optional[int]) -> list[Path]:
    if not SEED_ROOT.is_dir():
        raise SystemExit(f"seed_data root missing: {SEED_ROOT}")
    dirs = [
        d for d in sorted(SEED_ROOT.iterdir())
        if d.is_dir() and _YEAR_RE.match(d.name)
    ]
    if only_year is not None:
        dirs = [d for d in dirs if int(d.name) == only_year]
        if not dirs:
            raise SystemExit(f"No folder named {only_year} under {SEED_ROOT}")
    return dirs


def seed_all(only_year: Optional[int] = None, wipe: bool = True) -> None:
    if wipe:
        wipe_championship_data()

    for year_dir in _year_dirs(only_year):
        year = int(year_dir.name)
        csvs = sorted(year_dir.glob("*.csv"))
        print(f"\n== {year} ==  ({len(csvs)} race-day CSV(s))")
        if not csvs:
            print(f"  (no CSVs in {year_dir})")
            continue
        for csv_path in csvs:
            import_race_day(csv_path)

    print("\n✓ done")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--year", type=int, help="Only seed this year (e.g. 2026).")
    p.add_argument("--no-wipe", action="store_true", help="Skip the initial wipe.")
    args = p.parse_args()
    seed_all(only_year=args.year, wipe=not args.no_wipe)


if __name__ == "__main__":
    main()
