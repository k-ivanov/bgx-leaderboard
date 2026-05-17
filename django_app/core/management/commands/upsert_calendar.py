"""X4 — ``manage.py upsert_calendar`` — Django port of
``backend/scripts/upsert_calendar.py``.

The calendar data (``CALENDAR_2026`` / ``CALENDARS``) is copied **verbatim**.
The only changes are the persistence layer:

* ``session.scalars(select(Season).where(...)).one_or_none()`` →
  ``Season.objects.filter(year=year).first()``
* ``session.scalars(select(Event).where(...)).one_or_none()`` →
  ``Event.objects.filter(season_id=..., slug=...).first()``
* ``session.add(Event(...))`` / dirty-attribute flush →
  ``Event(...).save()`` (insert) / ``existing.save(update_fields=[...])``
  (update). The update path scopes the columns to exactly the four
  calendar fields the SQLAlchemy original reassigned — so the
  human-curated ``facebook_event_url`` / ``description`` are NEVER in the
  UPDATE statement (idempotent, re-run safe — X4 manual-edit preservation).
* ``get_session()`` → ``transaction.atomic()`` per year.

Original docstring (preserved verbatim) ---------------------------------------

Upsert per-year race calendar metadata (date / location / sort order).

Why this exists:
  CSV-driven `seed_all` only knows about races that already happened. Future
  races on bgx.bg's calendar have no results yet, so they never get created.
  This script seeds those entries (and updates the dates/locations of the
  past ones the importer left blank).

Idempotent. Safe to re-run on every CI build. Never overwrites the
human-curated `facebook_event_url` or `description` columns — those are
edited via /admin (SQLAdmin) and survive re-runs.

Usage:
    python manage.py upsert_calendar         # all years
    python manage.py upsert_calendar --year 2026
"""

from __future__ import annotations

from datetime import date
from typing import TypedDict

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Event, Season


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


def upsert_year(
    year: int, entries: list[CalendarEntry], *, stdout=None
) -> None:
    def _emit(msg: str) -> None:
        if stdout is not None:
            stdout.write(msg)
        else:
            print(msg)

    with transaction.atomic():
        season = Season.objects.filter(year=year).first()
        if season is None:
            _emit(f"  skip {year}: season row missing (run seed_all first)")
            return

        for sort_order, entry in enumerate(entries):
            existing = Event.objects.filter(
                season_id=season.id, slug=entry["slug"]
            ).first()

            if existing is None:
                Event(
                    season_id=season.id,
                    slug=entry["slug"],
                    name=entry["name"],
                    event_date=entry["event_date"],
                    location=entry["location"],
                    sort_order=sort_order,
                ).save()
                action = "+"
            else:
                # Refresh the calendar fields, leave human-edited fields
                # alone. SQLAlchemy only flushed the four reassigned
                # attributes; scope the Django UPDATE to exactly those so
                # facebook_event_url / description survive (idempotent).
                existing.name = entry["name"]
                existing.event_date = entry["event_date"]
                existing.location = entry["location"]
                existing.sort_order = sort_order
                existing.save(
                    update_fields=[
                        "name",
                        "event_date",
                        "location",
                        "sort_order",
                    ]
                )
                action = "~"
            _emit(
                f"  {action} {year} {entry['slug']:18} "
                f"{entry['event_date']} {entry['location']}"
            )


class Command(BaseCommand):
    help = "Upsert per-year race calendar metadata (date/location/order)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--year",
            type=int,
            help="Only upsert this year.",
        )

    def handle(self, *args, **options):
        year = options.get("year")
        targets = {year: CALENDARS[year]} if year else CALENDARS
        for yr, entries in sorted(targets.items()):
            self.stdout.write(f"== {yr} == ({len(entries)} races)")
            upsert_year(yr, entries, stdout=self.stdout)
        self.stdout.write("✓ calendar upserted")
