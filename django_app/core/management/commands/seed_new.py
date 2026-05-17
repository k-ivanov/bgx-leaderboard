"""X4 — ``manage.py seed_new`` — Django port of
``backend/scripts/seed_new.py``.

Incremental, idempotent seeder: import every CSV under ``seed_data/`` that
is not yet in the DB. The (filename, sha256) dedup against ``import_log``
is preserved **exactly** (X4 acceptance criterion):

* ``session.scalars(select(ImportLog))`` → ``ImportLog.objects.all()`` —
  the ``logged`` set of ``(source_filename, sha256)`` tuples is built the
  same way and checked the same way (``key in logged`` short-circuits).
* ``session.add(ImportLog(...)); session.commit()`` per imported file →
  ``ImportLog.objects.create(...)`` (its own commit, so a failure
  mid-batch still records the files that did land — same behavior as the
  SQLAlchemy per-file ``session.commit()``).
* ``rows_imported`` is recorded as ``0`` exactly as in the original (the
  importer's own output line is the source of truth for counts).

Original docstring (preserved verbatim) ---------------------------------------

Incremental seeder — import every CSV under seed_data/ that is not yet in the DB.

Idempotent. Walks the seed_data tree, computes a sha256 for each file,
checks the `import_log` table, and only calls `import_race_day` for
files (filename, sha256) tuples that have not been logged before. Each
successful import writes a row to `import_log`.

Safe to run repeatedly. Does NOT wipe the DB.

Usage:
    python manage.py seed_new                 # all years
    python manage.py seed_new --year 2026     # one year only
    python manage.py seed_new --dry-run       # report what would be imported

Covers improvements.md P0 #2 + P4 #26.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import ImportLog

from .import_race_day import import_race_day


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _seed_root() -> Path:
    # django_app/core/management/commands/seed_new.py → repo root → seed_data/
    return Path(__file__).resolve().parents[4] / "seed_data"


def find_csvs(year: int | None) -> list[Path]:
    root = _seed_root()
    if not root.exists():
        raise SystemExit(f"seed_data root not found: {root}")
    if year is None:
        return sorted(root.glob("*/*.csv"))
    return sorted((root / str(year)).glob("*.csv"))


def seed_new(
    year: int | None = None, dry_run: bool = False, *, stdout=None
) -> None:
    def _emit(msg: str) -> None:
        if stdout is not None:
            stdout.write(msg)
        else:
            print(msg)

    csvs = find_csvs(year)
    if not csvs:
        _emit("no CSVs found")
        return

    imported = 0
    skipped = 0

    # Build the set of (filename, sha) tuples already imported.
    logged = {
        (row.source_filename, row.sha256)
        for row in ImportLog.objects.all()
    }

    for csv in csvs:
        sha = _sha256(csv)
        key = (csv.name, sha)
        if key in logged:
            skipped += 1
            continue

        _emit(f"  → {csv.relative_to(_seed_root().parent)}")
        if dry_run:
            imported += 1
            continue

        # Count rows imported by re-counting before/after isn't worth it
        # for an idempotent helper; record 0 and let the importer's own
        # output line be the source of truth for row counts.
        import_race_day(csv, stdout=stdout)
        ImportLog.objects.create(
            source_filename=csv.name,
            sha256=sha,
            imported_at=datetime.now(timezone.utc),
            rows_imported=0,
        )
        imported += 1

    if dry_run:
        _emit(
            f"\ndry-run: would import {imported} file(s); "
            f"{skipped} already logged"
        )
    else:
        _emit(
            f"\ndone: imported {imported} file(s); "
            f"skipped {skipped} already logged"
        )


class Command(BaseCommand):
    help = (
        "Incrementally import seed_data CSVs not yet in import_log "
        "(filename+sha256 dedup). Idempotent; never wipes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="Only consider this year's folder.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print but don't import.",
        )

    def handle(self, *args, **options):
        seed_new(
            year=options.get("year"),
            dry_run=options.get("dry_run", False),
            stdout=self.stdout,
        )
