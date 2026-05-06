"""Upsert per-year race calendar metadata (date / location / sort order).

Why this exists:
  CSV-driven `seed_all` only knows about races that already happened. Future
  races on bgx.bg's calendar have no results yet, so they never get created.
  This script seeds those entries (and updates the dates/locations of the
  past ones the importer left blank).

Idempotent. Safe to re-run on every CI build. Never overwrites the
human-curated `facebook_event_url` or `description` columns — those are
edited via /admin (SQLAdmin) and survive re-runs.

Usage:
    python -m scripts.upsert_calendar         # all years
    python -m scripts.upsert_calendar --year 2026
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Optional, TypedDict

from sqlalchemy import select

from src.db import get_session
from src.db.models import Event, Season


class CalendarEntry(TypedDict):
    slug: str
    name: str
    event_date: date
    location: str


# Source: bgx.bg/ — official 2026 calendar. event_date is set to the FIRST
# day of multi-day races (Friday for 3-day events, Saturday for 2-day).
CALENDAR_2026: list[CalendarEntry] = [
    {"slug": "kyrnare",        "name": "Хард Ендуро Кърнаре 2026",            "event_date": date(2026, 3, 28),  "location": "Кърнаре"},
    {"slug": "buhovo",         "name": "Hard Enduro Buhovo 2026",             "event_date": date(2026, 4, 25),  "location": "Бухово"},
    {"slug": "botevgrad",      "name": "Hard Enduro Botevgrad 2026",          "event_date": date(2026, 5, 9),   "location": "Ботевград"},
    {"slug": "gorna_malina",   "name": "Хард Ендуро Горна Малина 2026",       "event_date": date(2026, 6, 6),   "location": "Горна Малина"},
    {"slug": "alba-damascena", "name": "EnduroX Дамасцена 2026",              "event_date": date(2026, 6, 20),  "location": "Скобелево"},
    {"slug": "vratsa",         "name": "Хард Ендуро Враца 2026",              "event_date": date(2026, 7, 3),   "location": "Враца"},
    {"slug": "bansko",         "name": "Three Mountains Hard Enduro Bansko 2026", "event_date": date(2026, 7, 18), "location": "Банско"},
    {"slug": "six_crazy_job",  "name": "Six Days Crazy Job 2026",             "event_date": date(2026, 8, 21),  "location": "Габрово"},
    {"slug": "uran",           "name": "Uran Enduro 2026",                    "event_date": date(2026, 9, 11),  "location": "Сеславци"},
    {"slug": "kirkovo",        "name": "Хард Ендуро Кирково 2026",            "event_date": date(2026, 9, 26),  "location": "Кирково"},
]


CALENDARS: dict[int, list[CalendarEntry]] = {
    2026: CALENDAR_2026,
}


def upsert_year(year: int, entries: list[CalendarEntry]) -> None:
    with get_session() as session:
        season = session.scalars(
            select(Season).where(Season.year == year)
        ).one_or_none()
        if season is None:
            print(f"  skip {year}: season row missing (run seed_all first)")
            return

        for sort_order, entry in enumerate(entries):
            existing = session.scalars(
                select(Event).where(
                    Event.season_id == season.id,
                    Event.slug == entry["slug"],
                )
            ).one_or_none()

            if existing is None:
                session.add(Event(
                    season_id=season.id,
                    slug=entry["slug"],
                    name=entry["name"],
                    event_date=entry["event_date"],
                    location=entry["location"],
                    sort_order=sort_order,
                ))
                action = "+"
            else:
                # Refresh the calendar fields, leave human-edited fields alone.
                existing.name = entry["name"]
                existing.event_date = entry["event_date"]
                existing.location = entry["location"]
                existing.sort_order = sort_order
                action = "~"
            print(f"  {action} {year} {entry['slug']:18} {entry['event_date']} {entry['location']}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--year", type=int, help="Only upsert this year.")
    args = p.parse_args()

    targets = {args.year: CALENDARS[args.year]} if args.year else CALENDARS
    for year, entries in sorted(targets.items()):
        print(f"== {year} == ({len(entries)} races)")
        upsert_year(year, entries)
    print("✓ calendar upserted")


if __name__ == "__main__":
    main()
