"""X4 — ``manage.py import_2025`` — Django port of the legacy
``backend/scripts/import_2025.py`` (the old pre-aggregated 2025 importer
referenced by ``CLAUDE.md``'s "Seed once" note / ``python -m
scripts.import_2025`` flow).

Reconstructed faithfully from the frozen byte-compiled
``backend/scripts/__pycache__/import_2025.cpython-312.pyc`` (the ``.py``
was removed when the unified ``seed_all`` flow superseded the old
``aggregate_2025`` CSV layout, but the ``CLAUDE.md`` contract still names
this command, so it is ported for parity). The control flow, the wide
``Race_<slug>`` cell handling, the ``0``-means-DNS/skip distinction, the
``championship_format="aggregate_2025"`` season, and the per-category
"skip: … not found" path are all reproduced exactly.

The ``src.seasons.CATEGORIES_2025`` / ``RACE_ORDER_2025`` constants the
original imported from ``backend/src/seasons.py`` are inlined verbatim
(``backend/`` is frozen and not importable from ``django_app``; the lists
are static data, copied byte-for-byte from that module).

ORM-translation notes (X4)
--------------------------
* ``get_session()`` → ``transaction.atomic()`` (commit-on-success /
  rollback-on-exception parity).
* ``session.execute(select(Season).where(Season.year == 2025))
  .scalar_one_or_none()`` → ``Season.objects.filter(year=2025).first()``.
* ``_wipe_season``: ``session.execute(delete(Season).where(Season.id ==
  season.id)); session.flush()`` → ``Season.objects.filter(id=...)
  .delete()`` (ON DELETE CASCADE still removes Category/Event/Rider/
  EventResult).
* ``session.add(obj); session.flush()`` → ``obj.save()``.
* The original built ``cat_by_code`` / ``event_by_slug`` dicts in-memory
  and read ``.id`` after a flush; ``.save()`` populates the PK the same
  way, so the dict-keyed wiring is unchanged.

Original docstring (preserved verbatim) ---------------------------------------

Import the 2025 season's pre-aggregated CSVs into the Postgres schema.

Each `Race_<slug>` cell maps to an event_result row.
`0` (integer) in the CSV means DNS (did not start) — no event_result row.
`0.0` (float) means DNF or zero points — stored as points=0.0.
This distinction is preserved by reading the CSV as raw strings.

Running multiple times is safe: the 2025 season is fully rebuilt each run.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import Category, Event, EventResult, Rider, Season


# Inlined verbatim from backend/src/seasons.py (frozen; static data).
RACE_ORDER_2025 = [
    ("kyrnare", "Kyrnare"),
    ("stara_zagora", "Stara Zagora"),
    ("buhovo", "Buhovo"),
    ("gorna_malina", "Gorna Malina"),
    ("alba_damascena", "Alba Damascena"),
    ("six_days", "Six Days"),
    ("kirkovo", "Kirkovo"),
]

CATEGORIES_2025 = [
    ("profi", "Pro"),
    ("expert", "Expert"),
    ("standard", "Standard"),
    ("standard_junior", "Standard Junior"),
    ("junior", "Junior"),
    ("women", "Women"),
    ("seniors_40", "Senior 40+"),
    ("seniors_50", "Senior 50+"),
]


# The original resolved this from backend/scripts/import_2025.py's location:
#   Path(__file__).resolve().parent / "seed_data" / "2025"
# i.e. backend/scripts/seed_data/2025 (a legacy layout that no longer
# exists in the tree — the command then prints "skip: … not found" per
# category, exactly as the original did). Preserved as the default so the
# CLI contract is byte-identical; pass --csv-dir to point at real data.
DEFAULT_CSV_DIR = (
    Path(__file__).resolve().parents[4]
    / "backend"
    / "scripts"
    / "seed_data"
    / "2025"
)


def _wipe_season(season: Season) -> None:
    # delete(Season).where(Season.id == season.id) + flush. ON DELETE
    # CASCADE removes Category/Event/Rider/EventResult downstream.
    Season.objects.filter(id=season.id).delete()


def import_2025(csv_dir: Path, is_current: bool = False, *, stdout=None) -> None:
    def _emit(msg: str) -> None:
        if stdout is not None:
            stdout.write(msg)
        else:
            print(msg)

    with transaction.atomic():
        existing = Season.objects.filter(year=2025).first()
        if existing is not None:
            _wipe_season(existing)

        season = Season(
            year=2025,
            name="BGX Hard Enduro 2025",
            slug="2025",
            is_current=is_current,
            championship_format="aggregate_2025",
        )
        season.save()

        cat_by_code: dict[str, Category] = {}
        for sort_order, (code, display) in enumerate(CATEGORIES_2025):
            cat = Category(
                season_id=season.id,
                code=code,
                display_name=display,
                sort_order=sort_order,
            )
            cat.save()
            cat_by_code[code] = cat

        event_by_slug: dict[str, Event] = {}
        for sort_order, (slug, name) in enumerate(RACE_ORDER_2025):
            ev = Event(
                season_id=season.id,
                slug=slug,
                name=name,
                sort_order=sort_order,
            )
            ev.save()
            event_by_slug[slug] = ev

        for code, _display in CATEGORIES_2025:
            path = csv_dir / f"{code}.csv"
            if not path.exists():
                _emit(f"skip: {path} not found")
                continue
            category = cat_by_code[code]
            with path.open(newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    race_num = int(row["RaceNumber"])
                    first = row["FirstName"].strip()
                    last = row["LastName"].strip()
                    rider = Rider(
                        season_id=season.id,
                        category_id=category.id,
                        race_number=race_num,
                        first_name=first,
                        last_name=last,
                    )
                    rider.save()
                    for race_slug, _ in RACE_ORDER_2025:
                        cell = (row.get(f"Race_{race_slug}") or "").strip()
                        if cell == "" or cell == "0":
                            continue
                        points = float(cell)
                        EventResult.objects.create(
                            event_id=event_by_slug[race_slug].id,
                            rider_id=rider.id,
                            points=points,
                        )
            _emit(f"imported {code}")


class Command(BaseCommand):
    help = "Import 2025 BGX season aggregates into Postgres."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv-dir",
            type=Path,
            default=DEFAULT_CSV_DIR,
            help=(
                "Directory containing <category>.csv files "
                "(default: scripts/seed_data/2025)"
            ),
        )
        parser.add_argument(
            "--is-current",
            action="store_true",
            help=(
                "Mark 2025 as the current season (usually you want this "
                "only for testing)."
            ),
        )

    def handle(self, *args, **options):
        import_2025(
            options["csv_dir"],
            is_current=options.get("is_current", False),
            stdout=self.stdout,
        )
        self.stdout.write("done")
