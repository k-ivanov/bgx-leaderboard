"""Wipe the championship tables and re-import every year folder in seed_data/.

Layout:

    backend/scripts/seed_data/
        <year>/                    e.g. 2025/, 2026/
            calendar.json          season + event metadata (see below)
            *.csv                  aggregate format: {category}.csv
                                   per-event format:  {race}_{category}.csv
                                   per-event multi-day: {race}_day{N}_{category}.csv

Format auto-detect:
  - championship_format="aggregate_2025" in calendar.json   → aggregate import
  - championship_format="per_event" in calendar.json        → per-event import

Usage:
    python -m scripts.seed_all                 # wipe + reimport every year
    python -m scripts.seed_all --year 2026     # wipe + reimport one year only
    python -m scripts.seed_all --no-wipe       # add/update without wiping

Safe to re-run. Visit (analytics) rows are NOT deleted — only championship
data (seasons, categories, events, riders, event_results).
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

from sqlalchemy import delete, select

from src.db import get_session
from src.db.models import Category, Event, EventResult, Rider, Season

from scripts import import_2025
from scripts.import_event import import_event
from scripts.seed_calendar import _get_or_create_season


SEED_ROOT = Path(__file__).resolve().parent / "seed_data"
AGGREGATE_FORMAT = "aggregate_2025"
PER_EVENT_FORMAT = "per_event"


# ---------------------------------------------------------------------------
# Wipe
# ---------------------------------------------------------------------------

def wipe_championship_data() -> None:
    """Delete all championship data. Keeps Visit rows (analytics)."""
    with get_session() as session:
        # Order matters: delete children first. EventResult depends on Event + Rider;
        # Rider + Event + Category depend on Season. With ON DELETE CASCADE in place
        # the single delete on Season handles all descendants.
        session.execute(delete(Season))
    print("✓ wiped championship data (visits preserved)")


# ---------------------------------------------------------------------------
# Calendar file
# ---------------------------------------------------------------------------

def _load_calendar(year_dir: Path) -> dict:
    calendar_path = year_dir / "calendar.json"
    if not calendar_path.is_file():
        raise SystemExit(
            f"Missing {calendar_path}. Create it with season_name, championship_format, "
            f"is_current, events[]."
        )
    with calendar_path.open(encoding="utf-8") as f:
        data = json.load(f)
    if "events" not in data or not isinstance(data["events"], list):
        raise SystemExit(f"{calendar_path}: 'events' list missing or malformed.")
    return data


def _parse_event_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    return datetime.strptime(raw, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Shared — upsert season + events + categories
# ---------------------------------------------------------------------------

def _upsert_calendar(year: int, calendar: dict) -> None:
    """Create/update Season + its Event rows from calendar.json."""
    season_name = calendar.get("season_name", f"BGX Hard Enduro {year}")
    is_current = bool(calendar.get("is_current", False))
    championship_format = calendar.get("championship_format", PER_EVENT_FORMAT)

    with get_session() as session:
        season = _get_or_create_season(session, year, season_name)
        season.is_current = is_current
        season.championship_format = championship_format

        existing_events = {
            ev.slug: ev
            for ev in session.execute(
                select(Event).where(Event.season_id == season.id)
            ).scalars()
        }

        for sort_order, entry in enumerate(calendar["events"]):
            slug = entry["slug"]
            event_date = _parse_event_date(entry.get("event_date"))
            location = entry.get("location")
            event_type = entry.get("event_type")
            name = entry["name"]

            ev = existing_events.get(slug)
            if ev is None:
                ev = Event(
                    season_id=season.id,
                    slug=slug,
                    name=name,
                    event_date=event_date,
                    location=location,
                    event_type=event_type,
                    sort_order=sort_order,
                )
                session.add(ev)
            else:
                ev.name = name
                ev.event_date = event_date
                ev.location = location
                ev.event_type = event_type
                ev.sort_order = sort_order

    print(f"  ✓ {year} season + {len(calendar['events'])} races")


# ---------------------------------------------------------------------------
# Per-event import
# ---------------------------------------------------------------------------

# Filename patterns for per-event CSVs:
#   {race_slug}_{category_code}.csv                      (single day)
#   {race_slug}_day{N}_{category_code}.csv               (multi-day)
#
# Race slugs can contain underscores or dashes (e.g. "gorna-malina",
# "stara_zagora"). We resolve ambiguity by trying each race slug as a
# prefix of the filename stem.
_DAY_RE = re.compile(r"^day(?P<n>\d+)$", re.IGNORECASE)


def _parse_per_event_filename(
    stem: str,
    race_slugs: Iterable[str],
) -> Optional[tuple[str, str, int]]:
    """Return (race_slug, category_code, day) for a per-event CSV stem.

    Returns None when no known race slug matches as a prefix.
    """
    # Try longest slugs first so e.g. "stara_zagora" wins over a hypothetical "stara".
    for race_slug in sorted(race_slugs, key=len, reverse=True):
        prefix = f"{race_slug}_"
        if stem.startswith(prefix):
            rest = stem[len(prefix):]
            # Check for a day indicator right after the race slug.
            day = 1
            parts = rest.split("_", 1)
            if parts and (match := _DAY_RE.match(parts[0])):
                day = int(match.group("n"))
                rest = parts[1] if len(parts) > 1 else ""
            if not rest:
                continue
            return race_slug, rest, day
    return None


def _category_display_name(code: str) -> str:
    """Fallback category display name when the source data doesn't supply one."""
    # Align with src/seasons.py::CATEGORIES_2025 capitalization.
    from src.seasons import CATEGORIES_2025
    for c, display in CATEGORIES_2025:
        if c == code:
            return display
    return code.replace("_", " ").title()


def _import_per_event(year: int, year_dir: Path, calendar: dict) -> None:
    events_by_slug = {e["slug"]: e for e in calendar["events"]}
    race_slugs = set(events_by_slug.keys())

    csvs = sorted(year_dir.glob("*.csv"))
    if not csvs:
        print(f"  (no per-event CSVs in {year_dir})")
        return

    count = 0
    for csv_path in csvs:
        parsed = _parse_per_event_filename(csv_path.stem, race_slugs)
        if parsed is None:
            print(f"  ⚠ skip {csv_path.name} — no race-slug prefix matches calendar")
            continue
        race_slug, category_code, day = parsed
        event_meta = events_by_slug[race_slug]
        import_event(
            csv_path,
            season_year=year,
            category_code=category_code,
            category_display=_category_display_name(category_code),
            event_slug=race_slug,
            event_name=event_meta["name"],
            event_date=_parse_event_date(event_meta.get("event_date")),
            event_type=event_meta.get("event_type"),
            day=day,
        )
        count += 1
    print(f"  ✓ imported {count} per-event CSV(s)")


# ---------------------------------------------------------------------------
# Aggregate (2025) import
# ---------------------------------------------------------------------------

def _import_aggregate(year: int, year_dir: Path, calendar: dict) -> None:
    # import_2025.import_2025 uses its own hardcoded layout; point it at the year dir.
    # It will wipe + rebuild the 2025 season entirely.
    is_current = bool(calendar.get("is_current", False))
    import_2025.import_2025(year_dir, is_current=is_current)
    print(f"  ✓ aggregate import: {year}")


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def _year_dirs(only_year: Optional[int]) -> list[Path]:
    if not SEED_ROOT.is_dir():
        raise SystemExit(f"seed_data root missing: {SEED_ROOT}")
    year_re = re.compile(r"^\d{4}$")
    dirs = [
        d for d in sorted(SEED_ROOT.iterdir())
        if d.is_dir() and year_re.match(d.name)
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
        print(f"\n== {year} ==")
        calendar = _load_calendar(year_dir)
        fmt = calendar.get("championship_format", PER_EVENT_FORMAT)

        if fmt == AGGREGATE_FORMAT:
            # Aggregate importer builds the season itself; calendar.json is
            # optional metadata used for future reorganization. We don't call
            # _upsert_calendar because import_2025 wipes+rebuilds the season
            # from the CSV column order — conflicting schedules would drift.
            _import_aggregate(year, year_dir, calendar)
        elif fmt == PER_EVENT_FORMAT:
            _upsert_calendar(year, calendar)
            _import_per_event(year, year_dir, calendar)
        else:
            raise SystemExit(
                f"{year_dir / 'calendar.json'}: unknown championship_format {fmt!r}. "
                f"Expected {AGGREGATE_FORMAT!r} or {PER_EVENT_FORMAT!r}."
            )

    print("\n✓ done")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--year", type=int, help="Only seed this year (e.g. 2026).")
    p.add_argument("--no-wipe", action="store_true", help="Skip the initial wipe.")
    args = p.parse_args()
    seed_all(only_year=args.year, wipe=not args.no_wipe)


if __name__ == "__main__":
    main()
