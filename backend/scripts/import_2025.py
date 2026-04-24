"""Import the 2025 season's pre-aggregated CSVs into the Postgres schema.

Each `Race_<slug>` cell maps to an event_result row.
`0` (integer) in the CSV means DNS (did not start) — no event_result row.
`0.0` (float) means DNF or zero points — stored as points=0.0.
This distinction is preserved by reading the CSV as raw strings.

Running multiple times is safe: the 2025 season is fully rebuilt each run.
"""

import argparse
import csv
from pathlib import Path

from sqlalchemy import delete, select

from src.db import get_session
from src.db.models import Category, Event, EventResult, Rider, Season
from src.seasons import CATEGORIES_2025, RACE_ORDER_2025

DEFAULT_CSV_DIR = Path(__file__).resolve().parent / "seed_data" / "2025"


def _wipe_season(session, season: Season) -> None:
    # Full cascade: deleting the season removes its categories, events, riders,
    # and (via event FK cascade) event_results.
    session.execute(delete(Season).where(Season.id == season.id))
    session.flush()


def import_2025(csv_dir: Path, *, is_current: bool = False) -> None:
    with get_session() as session:
        existing = session.execute(select(Season).where(Season.year == 2025)).scalar_one_or_none()
        if existing is not None:
            _wipe_season(session, existing)

        season = Season(
            year=2025,
            name="BGX Hard Enduro 2025",
            slug="2025",
            is_current=is_current,
            championship_format="aggregate_2025",
        )
        session.add(season)
        session.flush()

        cat_by_code = {}
        for sort_order, (code, display) in enumerate(CATEGORIES_2025):
            cat = Category(
                season_id=season.id,
                code=code,
                display_name=display,
                sort_order=sort_order,
            )
            session.add(cat)
            cat_by_code[code] = cat
        session.flush()

        event_by_slug = {}
        for sort_order, (slug, name) in enumerate(RACE_ORDER_2025):
            ev = Event(
                season_id=season.id,
                slug=slug,
                name=name,
                sort_order=sort_order,
            )
            session.add(ev)
            event_by_slug[slug] = ev
        session.flush()

        for code, _display in CATEGORIES_2025:
            path = csv_dir / f"{code}.csv"
            if not path.exists():
                print(f"skip: {path} not found")
                continue
            category = cat_by_code[code]
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    race_num = int(row["RaceNumber"])
                    first = row["FirstName"].strip()
                    last = row["LastName"].strip()
                    rider = Rider(
                        season_id=season.id,
                        category_id=category.id,
                        race_number=race_num,
                        first_name=first,
                        last_name=last,
                    )
                    session.add(rider)
                    session.flush()

                    for race_slug, _ in RACE_ORDER_2025:
                        cell = (row.get(f"Race_{race_slug}") or "").strip()
                        if cell == "" or cell == "0":
                            # empty or integer 0 → DNS, no result row
                            continue
                        points = float(cell)
                        session.add(
                            EventResult(
                                event_id=event_by_slug[race_slug].id,
                                rider_id=rider.id,
                                points=points,
                            )
                        )
            print(f"imported {code}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import 2025 BGX season aggregates into Postgres.")
    parser.add_argument(
        "--csv-dir",
        type=Path,
        default=DEFAULT_CSV_DIR,
        help="Directory containing <category>.csv files (default: scripts/seed_data/2025)",
    )
    parser.add_argument(
        "--is-current",
        action="store_true",
        help="Mark 2025 as the current season (usually you want this only for testing).",
    )
    args = parser.parse_args()
    import_2025(args.csv_dir, is_current=args.is_current)
    print("done")


if __name__ == "__main__":
    main()
