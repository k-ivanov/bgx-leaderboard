"""The 2026 BGX Hard Enduro calendar.

Edit the CALENDAR list, then run:

    python -m scripts.seed_calendar --season 2026

Multi-day events store the first day as `event_date` (our schema uses a
single DATE column). Re-running the seeder updates name/date/location/type
in place and keeps sort order in sync with this list.
"""

from datetime import date
from dataclasses import dataclass


@dataclass
class CalendarEntry:
    slug: str
    name: str
    event_date: date | None
    location: str | None
    event_type: str | None


CALENDAR: list[CalendarEntry] = [
    CalendarEntry("karnare",      "Хард Ендуро Кърнаре",                 date(2026, 3, 28), "Кърнаре",       "Навигация + Ендурокрос"),
    CalendarEntry("buhovo",       "Hard Enduro Buhovo",                  date(2026, 4, 25), "Бухово",        "2 дни навигация"),
    CalendarEntry("botevgrad",    "Хард Ендуро Ботевград",               date(2026, 5, 9),  "Ботевград",     "2 дни навигация"),
    CalendarEntry("gorna-malina", "Хард Ендуро Горна Малина",            date(2026, 6, 6),  "Горна Малина",  "2 дни навигация"),
    CalendarEntry("damascena",    "EnduroX Дамасцена",                   date(2026, 6, 20), "Скобелево",     "Навигация + Ендурокрос"),
    CalendarEntry("vratsa",       "Хард Ендуро Враца",                   date(2026, 7, 3),  "Враца",         "Пролог + 2 дни навигация"),
    CalendarEntry("bansko",       "Three Mountains Hard Enduro Bansko",  date(2026, 7, 18), "Банско",        "2 дни навигация"),
    CalendarEntry("six-days",     "Six Days Crazy Job",                  date(2026, 8, 21), "Габрово",       "Ендурокрос + Навигация"),
    CalendarEntry("uran",         "Uran Enduro",                         date(2026, 9, 11), "Сеславци",      "Пролог + 2 дни навигация"),
    CalendarEntry("kirkovo",      "Хард Ендуро Кирково",                 date(2026, 9, 26), "Кирково",       "Навигация + Ендурокрос"),
]

SEASON_NAME = "BGX Hard Enduro 2026"
