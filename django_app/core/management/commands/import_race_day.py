"""X4 — ``manage.py import_race_day`` — Django port of
``backend/scripts/import_race_day.py``.

Imports a single race-day CSV in the unified 2024+ format. The parsing /
row-shaping / class-dispatch logic is reused **VERBATIM** from the FastAPI
script (it is pure Python with zero ORM coupling). The ONLY change is the
persistence layer: SQLAlchemy ``get_session`` + ``select``/``delete`` →
Django ORM + ``transaction.atomic``.

Original docstring (preserved verbatim) ---------------------------------------

Import a single race-day CSV in the unified 2024+ format.

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

ORM-translation notes (X4)
--------------------------
* ``get_session()`` (commit-on-success / rollback-on-exception context
  manager) → ``django.db.transaction.atomic()`` — same all-or-nothing
  semantics for one CSV file.
* ``_get_or_create_event`` keeps ``name`` fresh but the SQLAlchemy original
  relied on the ORM only flushing *dirty* attributes, so it never touched
  ``event_date`` / ``location`` / ``event_type`` /
  ``facebook_event_url`` / ``description``. Django ``.save()`` would write
  *every* column, clobbering operator-edited fields. To preserve the
  manual-edit-preservation behavior byte-for-byte we
  ``save(update_fields=["name"])`` on the update path — the editorial
  columns are never in the UPDATE statement.
* ``len(season.events)`` → ``season.events.count()`` (the new event isn't
  saved yet, matching the SQLAlchemy pre-flush count).
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Category, Event, EventResult, Rider, Season


# ---------------------------------------------------------------------------
# Class (Bulgarian label in CSV) → category code
# ---------------------------------------------------------------------------

_CLASS_DAY_SUFFIX_RE = re.compile(r"\s+ДЕН\s+\d+$")


def _normalize_class_label(label: str) -> str:
    """Strip trailing ' ДЕН N' — day is carried in its own column."""
    return _CLASS_DAY_SUFFIX_RE.sub("", label).strip()


CLASS_MAP: dict[str, tuple[str, str]] = {
    # CSV label                     → (code,            display_name)
    "ПРОФИ":             ("profi",           "ПРОФИ"),
    "ЕКСПЕРТ":           ("expert",          "ЕКСПЕРТ"),
    "СТАНДАРТ":          ("standard",        "СТАНДАРТ"),
    "СТАНДАРТ ДЖУНИЪР":  ("standard_junior", "СТАНДАРТ-ДЖУНИЪР"),
    "СТАНДАРТ-ДЖУНИЪР":  ("standard_junior", "СТАНДАРТ-ДЖУНИЪР"),
    # Pre-2025 historical categories. The 2020–2024 CSVs use a single
    # "СЕНЬОРИ" class (no 40+/50+ split) and a single "ДЖУНИЪР" class
    # (no "СТАНДАРТ-" prefix). Modeled as separate codes from the modern
    # equivalents because the rider pools genuinely differed — merging
    # them would fabricate cross-season parity that doesn't exist in the
    # source data.
    "ДЖУНИЪР":           ("junior",          "ДЖУНИЪР"),
    "СЕНЬОРИ":           ("seniors",         "СЕНЬОРИ"),
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
    "junior": 4,
    "women": 5,
    "seniors_40": 6,
    "seniors_50": 7,
    "seniors": 8,
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
# DB upserts (Django ORM port of the SQLAlchemy helpers)
# ---------------------------------------------------------------------------

def _get_or_create_season(year: int) -> Season:
    season = Season.objects.filter(year=year).first()
    if season is None:
        season = Season(
            year=year,
            name=f"BGX Hard Enduro {year}",
            slug=str(year),
            is_current=False,
            championship_format="per_event",
        )
        season.save()
    return season


def _get_or_create_category(season: Season, code: str, display_name: str) -> Category:
    cat = Category.objects.filter(season_id=season.id, code=code).first()
    if cat is None:
        cat = Category(
            season_id=season.id,
            code=code,
            display_name=display_name,
            sort_order=CATEGORY_SORT_ORDER.get(code, 99),
        )
        cat.save()
    elif cat.display_name != display_name:
        cat.display_name = display_name
        # Mirror SQLAlchemy "only the dirty attribute is flushed".
        cat.save(update_fields=["display_name"])
    return cat


def _get_or_create_event(season: Season, slug: str, name: str) -> Event:
    ev = Event.objects.filter(season_id=season.id, slug=slug).first()
    if ev is None:
        ev = Event(
            season_id=season.id,
            slug=slug,
            name=name,
            sort_order=season.events.count(),
        )
        ev.save()
    else:
        # Keep the name fresh; leave event_date / location / event_type
        # (and the editorial facebook_event_url / description) alone so
        # operator edits via /admin aren't overwritten. SQLAlchemy achieved
        # this by only flushing the dirtied `name` attribute; Django's
        # `.save()` writes every column, so we MUST scope the UPDATE with
        # update_fields=["name"] to preserve that manual-edit-preservation
        # behavior byte-for-byte (X4 acceptance criterion).
        ev.name = name
        ev.save(update_fields=["name"])
    return ev


def _get_or_create_rider(
    season: Season,
    category: Category,
    race_number: int,
    first: str,
    last: str,
    team: Optional[str],
    bike: Optional[str],
) -> Rider:
    rider = Rider.objects.filter(
        category_id=category.id, race_number=race_number
    ).first()
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
        rider.save()
    else:
        # SQLAlchemy only flushed the attributes it actually reassigned.
        # Mirror that exactly via update_fields so unrelated columns are
        # untouched on the conditional-update path.
        dirty: list[str] = []
        if first:
            rider.first_name = first
            dirty.append("first_name")
        if last:
            rider.last_name = last
            dirty.append("last_name")
        if team:
            rider.team = team
            dirty.append("team")
        if bike:
            rider.bike = bike
            dirty.append("bike")
        if dirty:
            rider.save(update_fields=dirty)
    return rider


# ---------------------------------------------------------------------------
# Import driver — verbatim algorithm, Django persistence
# ---------------------------------------------------------------------------

def import_race_day(csv_path: Path, *, stdout=None) -> None:
    def _emit(msg: str) -> None:
        if stdout is not None:
            stdout.write(msg)
        else:
            print(msg)

    parsed = parse_filename(csv_path.stem)
    if parsed is None:
        raise CommandError(
            f"{csv_path.name}: filename doesn't match expected pattern "
            f"'<prefix>_<race>-<year>-day<N>.csv'"
        )
    race_slug, year, day = parsed

    with csv_path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        _emit(f"  (empty) {csv_path.name}")
        return

    # Race display name comes from the CSV itself (first row's `event`).
    event_name = (rows[0].get("event") or "").strip() or race_slug

    skipped: list[str] = []
    imported = 0

    with transaction.atomic():
        season = _get_or_create_season(year)
        event = _get_or_create_event(season, race_slug, event_name)

        # Wipe existing results for this (event, day) — but only across the
        # categories present in this CSV. Avoids touching unrelated data.
        categories_seen_codes: set[int] = set()

        # Pass 1: figure out which categories this CSV covers.
        classes_in_file = {
            _normalize_class_label(r.get("class", "").strip()) for r in rows
        }
        for cls_label in classes_in_file:
            if cls_label not in CLASS_MAP:
                if cls_label:
                    skipped.append(f"unknown class {cls_label!r}")
                continue
            code, display = CLASS_MAP[cls_label]
            cat = _get_or_create_category(season, code, display)
            categories_seen_codes.add(cat.id)

        if categories_seen_codes:
            rider_ids_for_cats = Rider.objects.filter(
                category_id__in=categories_seen_codes
            ).values_list("id", flat=True)
            EventResult.objects.filter(
                event_id=event.id,
                day=day,
                rider_id__in=list(rider_ids_for_cats),
            ).delete()

        # Pass 2: upsert riders + insert fresh EventResult rows.
        for row in rows:
            cls_label = _normalize_class_label((row.get("class") or "").strip())
            mapped = CLASS_MAP.get(cls_label)
            if mapped is None:
                continue
            code, display = mapped
            category = _get_or_create_category(season, code, display)

            race_number = _parse_int(row.get("start_number"))
            name = (row.get("rider_name") or "").strip()
            first, last = _split_name(name)
            if race_number is None or not last:
                skipped.append(f"row missing number/name: {row}")
                continue

            rider = _get_or_create_rider(
                season,
                category,
                race_number,
                first,
                last,
                team=_strip(row.get("club")),
                bike=_strip(row.get("motorcycle")),
            )

            EventResult.objects.create(
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
            imported += 1

    _emit(
        f"  ✓ {csv_path.name} → {year}/{race_slug} day={day}  "
        f"{imported} result(s)"
        f"{'' if not skipped else f' ({len(skipped)} skipped)'}"
    )


class Command(BaseCommand):
    help = "Import a single race-day CSV (unified 2024+ format)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            required=True,
            help="Path to the race-day CSV.",
        )

    def handle(self, *args, **options):
        import_race_day(options["file"], stdout=self.stdout)
