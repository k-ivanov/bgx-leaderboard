"""Import a single race-day CSV in the unified 2024+ format.

Expected columns (one row per (rider, day)):

    year, event_file, event, day, class, status, position, start_number,
    rider_name, motorcycle, club, ride_time, gps_penalty, cp_penalty, laps,
    total_time, start_time, finish_time, points, gap_to_leader, partial_time

The file contains results for ALL categories at one race day — the `class`
column dispatches rows to categories.

Semantics:
  - `total_time` (ride_time + penalties) → EventResult.time_ms
  - `gps_penalty` → gps_penalty_ms
  - `cp_penalty` → cp_penalty_ms
  - `status` → status (FIN / DNF / DNS / …)
  - `motorcycle` → Rider.bike
  - `club` → Rider.team
  - `rider_name` "First LAST" → split into first_name/last_name via casing

Filename pattern accepted:
    <prefix>_<race_slug>-<year>-day<N>.csv   (hard_enduro_botevgrad-2024-day1.csv)
    <prefix>_<race_slug>_<year>-day<N>.csv   (hard_enduro_kirkovo_2025-day1.csv)

Prefix values seen in source data: ``hard_enduro``, ``endurox``. The race
slug is whatever's left between the prefix and the year. Display name
comes from the CSV's `event` column.
"""

from __future__ import annotations

import argparse
import csv
import re
from datetime import date
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select

from src.db import get_session
from src.db.models import Category, Event, EventResult, Rider, Season


# ---------------------------------------------------------------------------
# Class (Bulgarian label in CSV) → category code
# ---------------------------------------------------------------------------

CLASS_MAP: dict[str, tuple[str, str]] = {
    # CSV label                     → (code,            display_name)
    "ПРОФИ":             ("profi",           "ПРОФИ"),
    "ЕКСПЕРТ":           ("expert",          "ЕКСПЕРТ"),
    "СТАНДАРТ":          ("standard",        "СТАНДАРТ"),
    "СТАНДАРТ ДЖУНИЪР":  ("standard_junior", "СТАНДАРТ-ДЖУНИЪР"),
    "СТАНДАРТ-ДЖУНИЪР":  ("standard_junior", "СТАНДАРТ-ДЖУНИЪР"),
    "ЖЕНИ":              ("women",           "ЖЕНИ"),
    "СЕНЬОРИ 40+":       ("seniors_40",      "СЕНЬОРИ 40+"),
    "СЕНЬОРИ 50+":       ("seniors_50",      "СЕНЬОРИ 50+"),
}

# Sort order for categories within a season (applied on first creation).
CATEGORY_SORT_ORDER: dict[str, int] = {
    "profi": 0,
    "expert": 1,
    "standard": 2,
    "standard_junior": 3,
    "women": 4,
    "seniors_40": 5,
    "seniors_50": 6,
}


# ---------------------------------------------------------------------------
# Filename parser
# ---------------------------------------------------------------------------

_FILENAME_RE = re.compile(
    r"""^
    (?:hard_enduro_|endurox_|enduro_|)   # optional prefix
    (?P<slug>.+?)                         # race slug (may contain - or _)
    [-_](?P<year>\d{4})                   # year separator: '-' or '_'
    -day(?P<day>\d+)                      # day marker
    $""",
    re.VERBOSE,
)


def parse_filename(stem: str) -> Optional[tuple[str, int, int]]:
    """Return (race_slug, year, day) or None if the name doesn't match."""
    m = _FILENAME_RE.match(stem)
    if not m:
        return None
    return m.group("slug"), int(m.group("year")), int(m.group("day"))


# ---------------------------------------------------------------------------
# Parsers for the CSV fields
# ---------------------------------------------------------------------------

def _strip(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    return v or None


def _parse_int(v: Optional[str]) -> Optional[int]:
    v = _strip(v)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _parse_float(v: Optional[str]) -> Optional[float]:
    v = _strip(v)
    if v is None:
        return None
    try:
        return float(v)
    except ValueError:
        return None


_TIME_RE = re.compile(
    r"""^
    (?:(?P<h>\d+):)?                  # optional hours
    (?P<m>\d+):                       # minutes
    (?P<s>\d+(?:\.\d+)?)              # seconds, optional decimal
    $""",
    re.VERBOSE,
)


def _parse_time_ms(v: Optional[str]) -> Optional[int]:
    """Parse `HH:MM:SS[.cs]` or `MM:SS[.cs]` into milliseconds. `0` stays as 0."""
    v = _strip(v)
    if v is None or v == "0":
        return 0 if v == "0" else None
    m = _TIME_RE.match(v)
    if not m:
        return None
    h = int(m.group("h") or 0)
    minutes = int(m.group("m"))
    seconds = float(m.group("s"))
    total_seconds = h * 3600 + minutes * 60 + seconds
    return int(total_seconds * 1000)


_TIME_TOKEN_RE = re.compile(r"^\d+:\d{2}:\d{2}(?:\.\d+)?$")


def _split_name(full: str) -> tuple[str, str]:
    """Split "Станислав КИРИЛОВ" → ("Станислав", "КИРИЛОВ").

    Heuristic: last name is the run of words that are ALL UPPERCASE (Bulgarian
    convention for last names in these CSVs). Everything before that is the
    first name. If no uppercase run, fall back to last whitespace split.

    Defensive: trailing tokens that look like a wall-clock time
    (HH:MM:SS or HH:MM:SS.x) are stripped — they are leakage from a
    misaligned CSV cell, not part of the rider's name. Without this we
    end up with rows like "Георги ГЕОРГИЕВ 3:34:40.7" in the rider table.
    """
    tokens = full.strip().split()
    # Strip trailing time tokens.
    while tokens and _TIME_TOKEN_RE.match(tokens[-1]):
        tokens.pop()
    if not tokens:
        return "", ""
    # Find first token that is fully uppercase (Cyrillic or Latin).
    split_idx = None
    for i, t in enumerate(tokens):
        if t == t.upper() and any(ch.isalpha() for ch in t):
            split_idx = i
            break
    if split_idx is None or split_idx == 0:
        # Fall back: last token is the last name.
        return " ".join(tokens[:-1]).strip(), tokens[-1]
    first = " ".join(tokens[:split_idx]).strip()
    last = " ".join(tokens[split_idx:]).strip()
    return first, last


# ---------------------------------------------------------------------------
# DB upserts
# ---------------------------------------------------------------------------

def _get_or_create_season(session, year: int) -> Season:
    season = session.execute(select(Season).where(Season.year == year)).scalar_one_or_none()
    if season is None:
        season = Season(
            year=year,
            name=f"BGX Hard Enduro {year}",
            slug=str(year),
            is_current=False,
            championship_format="per_event",
        )
        session.add(season)
        session.flush()
    return season


def _get_or_create_category(session, season: Season, code: str, display_name: str) -> Category:
    cat = session.execute(
        select(Category).where(Category.season_id == season.id, Category.code == code)
    ).scalar_one_or_none()
    if cat is None:
        cat = Category(
            season_id=season.id,
            code=code,
            display_name=display_name,
            sort_order=CATEGORY_SORT_ORDER.get(code, 99),
        )
        session.add(cat)
        session.flush()
    elif cat.display_name != display_name:
        cat.display_name = display_name
    return cat


def _get_or_create_event(
    session, season: Season, slug: str, name: str,
) -> Event:
    ev = session.execute(
        select(Event).where(Event.season_id == season.id, Event.slug == slug)
    ).scalar_one_or_none()
    if ev is None:
        ev = Event(
            season_id=season.id,
            slug=slug,
            name=name,
            sort_order=len(season.events),
        )
        session.add(ev)
        session.flush()
    else:
        # Keep the name fresh; leave event_date / location / event_type
        # alone so operator edits via /admin aren't overwritten.
        ev.name = name
    return ev


def _get_or_create_rider(
    session,
    season: Season,
    category: Category,
    race_number: int,
    first: str,
    last: str,
    team: Optional[str],
    bike: Optional[str],
) -> Rider:
    rider = session.execute(
        select(Rider).where(
            Rider.category_id == category.id,
            Rider.race_number == race_number,
        )
    ).scalar_one_or_none()
    if rider is None:
        rider = Rider(
            season_id=season.id,
            category_id=category.id,
            race_number=race_number,
            first_name=first,
            last_name=last,
            team=team,
            bike=bike,
        )
        session.add(rider)
        session.flush()
    else:
        if first:
            rider.first_name = first
        if last:
            rider.last_name = last
        if team:
            rider.team = team
        if bike:
            rider.bike = bike
    return rider


# ---------------------------------------------------------------------------
# Import driver
# ---------------------------------------------------------------------------

def import_race_day(csv_path: Path) -> None:
    parsed = parse_filename(csv_path.stem)
    if parsed is None:
        raise SystemExit(
            f"{csv_path.name}: filename doesn't match expected pattern "
            f"'<prefix>_<race>-<year>-day<N>.csv'"
        )
    race_slug, year, day = parsed

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print(f"  (empty) {csv_path.name}")
        return

    # Race display name comes from the CSV itself (first row's `event`).
    event_name = (rows[0].get("event") or "").strip() or race_slug

    skipped: list[str] = []
    imported = 0

    with get_session() as session:
        season = _get_or_create_season(session, year)
        event = _get_or_create_event(session, season, race_slug, event_name)

        # Wipe existing results for this (event, day) — but only across the
        # categories present in this CSV. Avoids touching unrelated data.
        categories_seen_codes: set[int] = set()

        # Pass 1: figure out which categories this CSV covers.
        classes_in_file = {r.get("class", "").strip() for r in rows}
        for cls_label in classes_in_file:
            if cls_label not in CLASS_MAP:
                if cls_label:
                    skipped.append(f"unknown class {cls_label!r}")
                continue
            code, display = CLASS_MAP[cls_label]
            cat = _get_or_create_category(session, season, code, display)
            categories_seen_codes.add(cat.id)

        if categories_seen_codes:
            rider_ids_for_cats = select(Rider.id).where(Rider.category_id.in_(categories_seen_codes))
            session.execute(
                delete(EventResult).where(
                    EventResult.event_id == event.id,
                    EventResult.day == day,
                    EventResult.rider_id.in_(rider_ids_for_cats),
                )
            )
            session.flush()

        # Pass 2: upsert riders + insert fresh EventResult rows.
        for row in rows:
            cls_label = (row.get("class") or "").strip()
            mapped = CLASS_MAP.get(cls_label)
            if mapped is None:
                continue
            code, display = mapped
            category = _get_or_create_category(session, season, code, display)

            race_number = _parse_int(row.get("start_number"))
            name = (row.get("rider_name") or "").strip()
            first, last = _split_name(name)
            if race_number is None or not last:
                skipped.append(f"row missing number/name: {row}")
                continue

            rider = _get_or_create_rider(
                session,
                season,
                category,
                race_number,
                first,
                last,
                team=_strip(row.get("club")),
                bike=_strip(row.get("motorcycle")),
            )

            session.add(
                EventResult(
                    event_id=event.id,
                    rider_id=rider.id,
                    day=day,
                    position=_parse_int(row.get("position")),
                    points=_parse_float(row.get("points")),
                    time_ms=_parse_time_ms(row.get("total_time")),
                    start_time_ms=_parse_time_ms(row.get("start_time")),
                    gps_penalty_ms=_parse_time_ms(row.get("gps_penalty")),
                    cp_penalty_ms=_parse_time_ms(row.get("cp_penalty")),
                    laps=_parse_int(row.get("laps")),
                    gap_ms=_parse_time_ms(row.get("gap_to_leader")),
                    status=_strip(row.get("status")),
                )
            )
            imported += 1

    print(
        f"  ✓ {csv_path.name} → {year}/{race_slug} day={day}  "
        f"{imported} result(s){'' if not skipped else f' ({len(skipped)} skipped)'}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a single race-day CSV.")
    parser.add_argument("--file", type=Path, required=True, help="Path to the race-day CSV.")
    args = parser.parse_args()
    import_race_day(args.file)


if __name__ == "__main__":
    main()
