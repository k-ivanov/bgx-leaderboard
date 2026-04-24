"""Import a per-event CSV (2026+ format) into the Postgres schema.

The CSV has Bulgarian headers:
    Поз, Ст.№, Състезател, Мотор, Отбор, Време, Старт, GPS, CP, Об., Точки, Тотал, Изоставане

Usage:
    python -m scripts.import_event \\
        --season 2026 \\
        --category expert --category-name "Expert" \\
        --event karnare --event-name "Kyrnare" --event-date 2026-04-18 \\
        --file scripts/seed_data/bgx-results-2026/karnare_2026_navigation_expert.csv

Re-running replaces all results for the (event, category) pair but keeps
riders so their team/bike info stays in sync if the CSV was corrected.
"""

import argparse
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select

from src.db import get_session
from src.db.models import Category, Event, EventResult, Rider, Season


HEADER_ALIASES = {
    "position": "Поз",
    "race_number": "Ст.№",
    "competitor": "Състезател",
    "bike": "Мотор",
    "team": "Отбор",
    "time": "Време",
    "start": "Старт",
    "gps": "GPS",
    "cp": "CP",
    "laps": "Об.",
    "points": "Точки",
    "total": "Тотал",
    "gap": "Изоставане",
}


def _split_name(competitor: str) -> tuple[str, str]:
    parts = competitor.strip().split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _parse_time_to_ms(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = value.strip()
    if not v or v == "0":
        return None
    # "HH:MM:SS[.fraction]" or "MM:SS[.fraction]"
    segments = v.split(":")
    try:
        if len(segments) == 3:
            h, m, s = segments
            total = int(h) * 3600 + int(m) * 60 + float(s)
        elif len(segments) == 2:
            m, s = segments
            total = int(m) * 60 + float(s)
        else:
            total = float(v)
    except ValueError:
        return None
    return int(round(total * 1000))


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        return int(v)
    except ValueError:
        try:
            return int(float(v))
        except ValueError:
            return None


def _parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_position(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    v = value.strip().upper()
    if not v or v in {"DNF", "DNS", "DSQ"}:
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _get_or_create_season(session, year: int) -> Season:
    season = session.execute(select(Season).where(Season.year == year)).scalar_one_or_none()
    if season is None:
        season = Season(
            year=year,
            name=f"BGX Hard Enduro {year}",
            slug=str(year),
            is_current=True,
            championship_format="per_event",
        )
        session.add(season)
        session.flush()
    return season


def _get_or_create_category(session, season: Season, code: str, display: str) -> Category:
    cat = session.execute(
        select(Category).where(Category.season_id == season.id, Category.code == code)
    ).scalar_one_or_none()
    if cat is None:
        cat = Category(
            season_id=season.id,
            code=code,
            display_name=display,
            sort_order=len(season.categories),
        )
        session.add(cat)
        session.flush()
    return cat


def _get_or_create_event(
    session,
    season: Season,
    slug: str,
    name: str,
    event_date: Optional[date],
    event_type: Optional[str],
) -> Event:
    ev = session.execute(
        select(Event).where(Event.season_id == season.id, Event.slug == slug)
    ).scalar_one_or_none()
    if ev is None:
        ev = Event(
            season_id=season.id,
            slug=slug,
            name=name,
            event_date=event_date,
            sort_order=len(season.events),
            event_type=event_type,
        )
        session.add(ev)
        session.flush()
    else:
        # Update metadata if the caller provided more detail.
        if event_date is not None:
            ev.event_date = event_date
        if event_type is not None:
            ev.event_type = event_type
        if name:
            ev.name = name
    return ev


def import_event(
    csv_path: Path,
    *,
    season_year: int,
    category_code: str,
    category_display: Optional[str],
    event_slug: str,
    event_name: str,
    event_date: Optional[date],
    event_type: Optional[str],
) -> None:
    with get_session() as session:
        season = _get_or_create_season(session, season_year)
        category = _get_or_create_category(
            session, season, category_code, category_display or category_code.title()
        )
        event = _get_or_create_event(
            session, season, event_slug, event_name, event_date, event_type
        )

        # Wipe existing results for this (event, category) pair to support re-runs.
        # Results are identified via the rider's category_id.
        category_riders = select(Rider.id).where(Rider.category_id == category.id)
        session.execute(
            delete(EventResult).where(
                EventResult.event_id == event.id,
                EventResult.rider_id.in_(category_riders),
            )
        )
        session.flush()

        with csv_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                race_num = _parse_int(row.get(HEADER_ALIASES["race_number"]))
                if race_num is None:
                    continue
                first, last = _split_name(row.get(HEADER_ALIASES["competitor"], ""))

                rider = session.execute(
                    select(Rider).where(
                        Rider.category_id == category.id,
                        Rider.race_number == race_num,
                    )
                ).scalar_one_or_none()
                if rider is None:
                    rider = Rider(
                        season_id=season.id,
                        category_id=category.id,
                        race_number=race_num,
                        first_name=first,
                        last_name=last,
                    )
                    session.add(rider)
                else:
                    rider.first_name = first or rider.first_name
                    rider.last_name = last or rider.last_name
                rider.team = (row.get(HEADER_ALIASES["team"]) or "").strip() or rider.team
                rider.bike = (row.get(HEADER_ALIASES["bike"]) or "").strip() or rider.bike
                session.flush()

                position = _parse_position(row.get(HEADER_ALIASES["position"]))
                points = _parse_float(row.get(HEADER_ALIASES["points"]))
                time_ms = _parse_time_to_ms(row.get(HEADER_ALIASES["total"])) or _parse_time_to_ms(
                    row.get(HEADER_ALIASES["time"])
                )
                start_ms = _parse_time_to_ms(row.get(HEADER_ALIASES["start"]))
                gps_penalty_ms = _parse_time_to_ms(row.get(HEADER_ALIASES["gps"]))
                cp_count = _parse_int(row.get(HEADER_ALIASES["cp"]))
                laps = _parse_int(row.get(HEADER_ALIASES["laps"]))
                gap_ms = _parse_time_to_ms(row.get(HEADER_ALIASES["gap"]))

                session.add(
                    EventResult(
                        event_id=event.id,
                        rider_id=rider.id,
                        position=position,
                        points=points,
                        time_ms=time_ms,
                        start_time_ms=start_ms,
                        gps_penalty_ms=gps_penalty_ms,
                        cp_count=cp_count,
                        laps=laps,
                        gap_ms=gap_ms,
                    )
                )

        print(f"imported {csv_path.name} → season={season_year} event={event_slug} category={category_code}")


def _parse_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    return datetime.strptime(s, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a per-event BGX CSV into Postgres.")
    parser.add_argument("--file", type=Path, required=True, help="Path to the event CSV.")
    parser.add_argument("--season", type=int, required=True, help="Season year (e.g. 2026).")
    parser.add_argument("--category", required=True, help="Category code (e.g. expert).")
    parser.add_argument("--category-name", help="Human-readable category name.")
    parser.add_argument("--event", required=True, help="Event slug (e.g. karnare).")
    parser.add_argument("--event-name", required=True, help="Event display name.")
    parser.add_argument("--event-date", help="Event date in YYYY-MM-DD.")
    parser.add_argument("--event-type", help="Optional event type (e.g. navigation).")
    args = parser.parse_args()

    import_event(
        args.file,
        season_year=args.season,
        category_code=args.category,
        category_display=args.category_name,
        event_slug=args.event,
        event_name=args.event_name,
        event_date=_parse_date(args.event_date),
        event_type=args.event_type,
    )


if __name__ == "__main__":
    main()
