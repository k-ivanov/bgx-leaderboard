"""The 2025 BGX Hard Enduro calendar.

Slugs here must match the event slugs already imported by
`scripts/import_2025.py` (they are derived from the `Race_*` column names
in the aggregate CSVs: kyrnare, stara_zagora, buhovo, gorna_malina,
alba_damascena, six_days, kirkovo).

Run with:

    python -m scripts.seed_calendar --season 2025
"""

from datetime import date

from scripts.seed_data.calendar_2026 import CalendarEntry


CALENDAR: list[CalendarEntry] = [
    CalendarEntry("kyrnare",        "Хард Ендуро Кърнаре",          date(2025, 3, 28), "Кърнаре",       "Навигация + Ендурокрос"),
    CalendarEntry("stara_zagora",   "Хард Ендуро Стара Загора",     date(2025, 4, 12), "Стара Загора",  "2 дни навигация"),
    CalendarEntry("buhovo",         "Хард Ендуро Бухово",           date(2025, 5, 3),  "Бухово",        "2 дни навигация"),
    CalendarEntry("gorna_malina",   "Хард Ендуро Горна Малина",     date(2025, 5, 17), "Горна Малина",  "2 дни навигация"),
    CalendarEntry("alba_damascena", "EnduroX Alba - Damascena",     date(2025, 6, 14), "Скобелево",     "Навигация + Ендурокрос"),
    CalendarEntry("six_days",       "Six Days Crazy Job",           date(2025, 8, 10), "Габрово",       "Ендурокрос + Навигация"),
    CalendarEntry("kirkovo",        "Хард Ендуро Кирково",          date(2025, 9, 20), "Кирково",       "Навигация + Ендурокрос"),
]

SEASON_NAME = "BGX Hard Enduro 2025"
