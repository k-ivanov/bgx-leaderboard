"""Incremental seeder — import every CSV under seed_data/ that is not yet in the DB.

Idempotent. Walks the seed_data tree, computes a sha256 for each file,
checks the `import_log` table, and only calls `import_race_day` for
files (filename, sha256) tuples that have not been logged before. Each
successful import writes a row to `import_log`.

Safe to run repeatedly. Does NOT wipe the DB.

Usage:
    python -m scripts.seed_new                 # all years
    python -m scripts.seed_new --year 2026     # one year only
    python -m scripts.seed_new --dry-run       # report what would be imported

Covers improvements.md P0 #2 + P4 #26.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from scripts.import_race_day import import_race_day
from src.db.models import ImportLog
from src.db.session import SessionLocal


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _seed_root() -> Path:
    # backend/scripts/seed_new.py → repo root → seed_data/
    return Path(__file__).resolve().parents[2] / "seed_data"


def find_csvs(year: int | None) -> list[Path]:
    root = _seed_root()
    if not root.exists():
        raise SystemExit(f"seed_data root not found: {root}")
    if year is None:
        return sorted(root.glob("*/*.csv"))
    return sorted((root / str(year)).glob("*.csv"))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--year", type=int, help="Only consider this year's folder.")
    p.add_argument("--dry-run", action="store_true", help="Print but don't import.")
    args = p.parse_args()

    csvs = find_csvs(args.year)
    if not csvs:
        print("no CSVs found")
        return

    imported = 0
    skipped = 0
    with SessionLocal() as session:
        # Build the set of (filename, sha) tuples already imported.
        logged = {
            (row.source_filename, row.sha256)
            for row in session.scalars(select(ImportLog))
        }

        for csv in csvs:
            sha = _sha256(csv)
            key = (csv.name, sha)
            if key in logged:
                skipped += 1
                continue

            print(f"  → {csv.relative_to(_seed_root().parent)}")
            if args.dry_run:
                imported += 1
                continue

            # Count rows imported by re-counting before/after isn't worth it
            # for an idempotent helper; record 0 and let the importer's own
            # output line be the source of truth for row counts.
            import_race_day(csv)
            session.add(
                ImportLog(
                    source_filename=csv.name,
                    sha256=sha,
                    imported_at=datetime.now(timezone.utc),
                    rows_imported=0,
                )
            )
            session.commit()
            imported += 1

    if args.dry_run:
        print(f"\ndry-run: would import {imported} file(s); {skipped} already logged")
    else:
        print(f"\ndone: imported {imported} file(s); skipped {skipped} already logged")


if __name__ == "__main__":
    main()
