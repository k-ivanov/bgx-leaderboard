"""X4 — ``manage.py seed_all`` — Django port of
``backend/scripts/seed_all.py``.

Wipe the championship tables and re-import every year folder in
``seed_data/``. Driver logic is verbatim; the only changes are:

* ``from scripts.import_race_day import import_race_day`` → the X4
  ``import_race_day`` command's module-level ``import_race_day`` callable.
* ``session.execute(delete(Season))`` → ``Season.objects.all().delete()``
  inside ``transaction.atomic()`` (ON DELETE CASCADE on Season →
  Category/Event/Rider/EventResult still cleans everything downstream;
  ``Visit`` / analytics rows are NOT deleted, exactly as before).
* ``Path(__file__).resolve().parents[2] / "seed_data"`` → resolved from
  this command file's location to the repo root (``parents[4]``); cwd is
  still irrelevant.

Original docstring (preserved verbatim) ---------------------------------------

Wipe the championship tables and re-import every year folder in seed_data/.

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
    python manage.py seed_all                 # wipe + reimport every year
    python manage.py seed_all --year 2026     # wipe + reimport one year only
    python manage.py seed_all --no-wipe       # add/update without wiping

Visit (analytics) rows are NOT deleted — only championship data (seasons,
categories, events, riders, event_results).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Season

from .import_race_day import import_race_day


# seed_data lives at the repo root. This file is
# django_app/core/management/commands/seed_all.py — parents[4] is the repo
# root (django_app/core/management/commands/ → repo). cwd doesn't matter.
SEED_ROOT = Path(__file__).resolve().parents[4] / "seed_data"

_YEAR_RE = re.compile(r"^\d{4}$")


# ---------------------------------------------------------------------------
# Wipe
# ---------------------------------------------------------------------------

def wipe_championship_data(*, stdout=None) -> None:
    """Delete all championship data. Keeps Visit rows (analytics).

    ON DELETE CASCADE on Season → Category/Event/Rider/EventResult means a
    single Season delete cleans up everything downstream.
    """
    with transaction.atomic():
        Season.objects.all().delete()
    msg = "✓ wiped championship data (visits preserved)"
    if stdout is not None:
        stdout.write(msg)
    else:
        print(msg)


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


def seed_all(
    only_year: Optional[int] = None, wipe: bool = True, *, stdout=None
) -> None:
    def _emit(msg: str) -> None:
        if stdout is not None:
            stdout.write(msg)
        else:
            print(msg)

    if wipe:
        wipe_championship_data(stdout=stdout)

    for year_dir in _year_dirs(only_year):
        year = int(year_dir.name)
        csvs = sorted(year_dir.glob("*.csv"))
        _emit(f"\n== {year} ==  ({len(csvs)} race-day CSV(s))")
        if not csvs:
            _emit(f"  (no CSVs in {year_dir})")
            continue
        for csv_path in csvs:
            import_race_day(csv_path, stdout=stdout)

    _emit("\n✓ done")


class Command(BaseCommand):
    help = "Wipe championship tables and re-import every year in seed_data/."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="Only seed this year (e.g. 2026).",
        )
        parser.add_argument(
            "--no-wipe",
            action="store_true",
            help="Skip the initial wipe.",
        )

    def handle(self, *args, **options):
        seed_all(
            only_year=options.get("year"),
            wipe=not options.get("no_wipe"),
            stdout=self.stdout,
        )
