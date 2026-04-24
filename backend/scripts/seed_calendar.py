"""Upsert a season calendar (list of events) into Postgres.

Usage:
    python -m scripts.seed_calendar --season 2026

Reads `scripts/seed_data/<year>/calendar.json` and upserts Season + Event rows.
Safe to re-run — names, dates, types, and sort order update in place; new
rounds append. Results (EventResult rows) are NOT touched.

For a full reimport (wipe + reseed everything), use ``scripts.seed_all``.
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from src.db import get_session
from src.db.models import Event, Season


SEED_ROOT = Path(__file__).resolve().parent / "seed_data"


def _get_or_create_season(session, year: int, name: str) -> Season:
    season = session.execute(select(Season).where(Season.year == year)).scalar_one_or_none()
    if season is None:
        season = Season(
            year=year,
            name=name,
            slug=str(year),
            is_current=True,
            championship_format="per_event",
        )
        session.add(season)
        session.flush()
    else:
        season.name = name
    return season


def seed_calendar(year: int) -> None:
    calendar_path = SEED_ROOT / str(year) / "calendar.json"
    if not calendar_path.is_file():
        raise SystemExit(
            f"No calendar file at {calendar_path}. "
            f"Create scripts/seed_data/{year}/calendar.json with season_name, "
            f"championship_format, is_current, events[]."
        )
    with calendar_path.open(encoding="utf-8") as f:
        calendar = json.load(f)

    entries = calendar.get("events") or []
    if not entries:
        raise SystemExit(f"{calendar_path}: 'events' list is empty.")
    season_name = calendar.get("season_name", f"BGX Hard Enduro {year}")

    with get_session() as session:
        season = _get_or_create_season(session, year, season_name)
        if "championship_format" in calendar:
            season.championship_format = calendar["championship_format"]
        if "is_current" in calendar:
            season.is_current = bool(calendar["is_current"])

        existing = {
            ev.slug: ev
            for ev in session.execute(
                select(Event).where(Event.season_id == season.id)
            ).scalars()
        }

        for sort_order, entry in enumerate(entries):
            slug = entry["slug"]
            event_date = (
                datetime.strptime(entry["event_date"], "%Y-%m-%d").date()
                if entry.get("event_date") else None
            )
            name = entry["name"]
            location = entry.get("location")
            event_type = entry.get("event_type")
            ev = existing.get(slug)
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
                print(f"+ add:    {year} {sort_order + 1:>2}. {slug:<16} {name} ({event_date})")
            else:
                ev.name = name
                ev.event_date = event_date
                ev.location = location
                ev.event_type = event_type
                ev.sort_order = sort_order
                print(f"~ update: {year} {sort_order + 1:>2}. {slug:<16} {name} ({event_date})")

    print(f"done — {len(entries)} event(s) in the {year} calendar")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a season's event calendar.")
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g. 2026).")
    args = parser.parse_args()
    seed_calendar(args.season)


if __name__ == "__main__":
    main()
