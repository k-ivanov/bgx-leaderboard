"""Upsert a season calendar (list of events) into Postgres.

Usage:
    python -m scripts.seed_calendar --season 2026

Reads the calendar definition from `scripts.seed_data.calendar_<year>` —
a Python module that exposes a `CALENDAR` list and an optional
`SEASON_NAME`. See `scripts/seed_data/calendar_2026.py` for the template.

Safe to re-run after editing the calendar: names, dates, types, and sort
order are updated in place, and new rounds are appended.
"""

import argparse
import importlib

from sqlalchemy import select

from src.db import get_session
from src.db.models import Event, Season


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
    module_name = f"scripts.seed_data.calendar_{year}"
    try:
        calendar_module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"No calendar module found at {module_name}. "
            f"Create scripts/seed_data/calendar_{year}.py with a CALENDAR list."
        ) from exc

    entries = getattr(calendar_module, "CALENDAR", None)
    if not entries:
        raise SystemExit(f"{module_name}.CALENDAR is empty.")
    season_name = getattr(calendar_module, "SEASON_NAME", f"BGX Hard Enduro {year}")

    with get_session() as session:
        season = _get_or_create_season(session, year, season_name)

        existing = {
            ev.slug: ev
            for ev in session.execute(
                select(Event).where(Event.season_id == season.id)
            ).scalars()
        }

        for sort_order, entry in enumerate(entries):
            slug = entry.slug
            ev = existing.get(slug)
            if ev is None:
                ev = Event(
                    season_id=season.id,
                    slug=slug,
                    name=entry.name,
                    event_date=entry.event_date,
                    location=entry.location,
                    event_type=entry.event_type,
                    sort_order=sort_order,
                )
                session.add(ev)
                print(f"+ add:    {year} {sort_order + 1:>2}. {slug:<16} {entry.name} ({entry.event_date})")
            else:
                ev.name = entry.name
                ev.event_date = entry.event_date
                ev.location = entry.location
                ev.event_type = entry.event_type
                ev.sort_order = sort_order
                print(f"~ update: {year} {sort_order + 1:>2}. {slug:<16} {entry.name} ({entry.event_date})")

    print(f"done — {len(entries)} event(s) in the {year} calendar")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a season's event calendar.")
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g. 2026).")
    args = parser.parse_args()
    seed_calendar(args.season)


if __name__ == "__main__":
    main()
