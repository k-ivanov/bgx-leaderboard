"""X4 — management-command importer tests.

Three concerns are pinned here:

1. **``_split_name`` behavior** — the ported ``backend/tests/test_import.py``
   cases, verbatim, now importing from the X4 ``import_race_day`` command
   module instead of ``scripts.import_race_day``. Pure-function; no DB.

2. **Importer DB behavior** (``@pytest.mark.django_db``) — golden row
   shaping for ``import_race_day`` on a synthetic unified-2024 CSV, the
   ``import_race_day`` / ``upsert_calendar`` **manual-edit-preservation**
   contract (operator-set ``facebook_event_url`` / ``description`` survive
   a re-import — X4 acceptance criterion), the ``import_2025``
   ``Race_<slug>`` / ``0``-DNS / ``0.0``-DNF semantics, and ``seed_new``'s
   ``ImportLog`` (filename+sha256) dedup.

These use pytest-django's isolated test DB (the F2 ``managed=True`` models
build the schema there) — they are Tier-1 (no ``seeded_orm`` /
``parity_rig`` fixture, so not auto-marked ``parity``) but inherently need
Postgres, exactly like the prior slices' ``@pytest.mark.django_db`` tests
(``test_admin.py`` etc.). The end-to-end *golden parity vs the old
``backend/scripts`` importer on the real ``seed_data/`` CSVs* is proven
out-of-band against the seeded ``bgx_oracle`` / a scratch DB (the X4
acceptance evidence) — replaying all 35 real CSVs inside a unit test would
just re-assert the same thing far more slowly.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.management.commands.import_2025 import import_2025
from core.management.commands.import_race_day import _split_name, import_race_day
from core.management.commands.seed_new import seed_new
from core.management.commands.upsert_calendar import upsert_year
from core.models import (
    Category,
    Event,
    EventResult,
    ImportLog,
    Rider,
    Season,
)


# ===========================================================================
# 1. _split_name — ported verbatim from backend/tests/test_import.py
# ===========================================================================


@pytest.mark.parametrize(
    ("full", "expected_first", "expected_last"),
    [
        # Normal case: first name + Bulgarian uppercase last name.
        ("Станислав КИРИЛОВ", "Станислав", "КИРИЛОВ"),
        # Multi-word first name.
        ("Жан-Пол ИВАНОВ", "Жан-Пол", "ИВАНОВ"),
        # Latin name.
        ("Alexander STRACKE", "Alexander", "STRACKE"),
        # No uppercase last name → fall back to last token.
        ("ivan ivanov", "ivan", "ivanov"),
    ],
)
def test_split_name_basic(full, expected_first, expected_last):
    first, last = _split_name(full)
    assert first == expected_first
    assert last == expected_last


@pytest.mark.parametrize(
    ("full", "expected_first", "expected_last"),
    [
        # Trailing race time leaks in from a misaligned CSV cell.
        ("Георги ГЕОРГИЕВ 3:34:40.7", "Георги", "ГЕОРГИЕВ"),
        ("Иван ПЕТРОВ 1:02:03", "Иван", "ПЕТРОВ"),
        ("Mark JONES 12:34:56.123", "Mark", "JONES"),
        # Multiple trailing times — strip all of them.
        ("Иван ПЕТРОВ 1:02:03 2:34:56", "Иван", "ПЕТРОВ"),
    ],
)
def test_split_name_strips_trailing_time(full, expected_first, expected_last):
    first, last = _split_name(full)
    assert first == expected_first
    assert last == expected_last


def test_split_name_empty_after_strip():
    """If the cell is JUST a time, return empty (caller should skip the row)."""
    first, last = _split_name("1:02:03")
    assert first == ""
    assert last == ""


# ===========================================================================
# Helpers
# ===========================================================================

_UNIFIED_CSV = (
    "year,event,day,class,status,position,start_number,rider_name,"
    "motorcycle,club,gps_penalty,cp_penalty,laps,total_time,start_time,"
    "points,gap_to_leader\n"
    "2099,Тестово Хард Ендуро,1,ПРОФИ,FIN,1,7,Иван ИВАНОВ,KTM,Team A,"
    "0,0,3,1:02:03,9:00:00,25,0\n"
    "2099,Тестово Хард Ендуро,1,ПРОФИ,DNF,,13,Петър ПЕТРОВ,Husqvarna,"
    "Team B,0,0,1,0,9:01:00,0.0,0\n"
    "2099,Тестово Хард Ендуро,1,ЕКСПЕРТ,FIN,1,42,Георги ГЕОРГИЕВ,Beta,"
    "Team C,0,0,2,1:10:00,9:02:00,25,0\n"
)


def _write(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ===========================================================================
# 2. import_race_day — golden row shaping
# ===========================================================================


@pytest.mark.django_db
def test_import_race_day_shapes_rows(tmp_path, capsys):
    csv_path = _write(
        tmp_path, "hard_enduro_testtown-2099-day1.csv", _UNIFIED_CSV
    )
    import_race_day(csv_path)

    season = Season.objects.get(year=2099)
    assert season.name == "BGX Hard Enduro 2099"
    assert season.slug == "2099"
    assert season.is_current is False
    assert season.championship_format == "per_event"

    event = Event.objects.get(season=season, slug="testtown")
    # Display name comes from the CSV's `event` column, not the slug.
    assert event.name == "Тестово Хард Ендуро"

    # Two categories dispatched via the `class` column.
    assert set(
        Category.objects.filter(season=season).values_list("code", flat=True)
    ) == {"profi", "expert"}

    profi = Category.objects.get(season=season, code="profi")
    r7 = Rider.objects.get(category=profi, race_number=7)
    assert (r7.first_name, r7.last_name) == ("Иван", "ИВАНОВ")
    assert r7.team == "Team A" and r7.bike == "KTM"

    er7 = EventResult.objects.get(event=event, rider=r7)
    assert er7.day == 1
    assert er7.position == 1
    assert float(er7.points) == 25.0
    # 1:02:03 → ((1*3600)+(2*60)+3)*1000
    assert er7.time_ms == ((1 * 3600) + (2 * 60) + 3) * 1000
    assert er7.status == "FIN"

    # DNF row: no position, points 0.0, total_time "0" → time_ms 0.
    r13 = Rider.objects.get(category=profi, race_number=13)
    er13 = EventResult.objects.get(event=event, rider=r13)
    assert er13.position is None
    assert float(er13.points) == 0.0
    assert er13.time_ms == 0
    assert er13.status == "DNF"


@pytest.mark.django_db
def test_import_race_day_reimport_replaces_results_not_duplicates(tmp_path):
    csv_path = _write(
        tmp_path, "hard_enduro_testtown-2099-day1.csv", _UNIFIED_CSV
    )
    import_race_day(csv_path)
    import_race_day(csv_path)  # second run

    event = Event.objects.get(slug="testtown")
    # 3 result rows total (not 6) — the (event, day, category) wipe ran.
    assert EventResult.objects.filter(event=event).count() == 3
    # Riders not duplicated either.
    assert Rider.objects.filter(season__year=2099).count() == 3


# ===========================================================================
# 3. import_race_day — manual-edit preservation (X4 acceptance criterion)
# ===========================================================================


@pytest.mark.django_db
def test_import_race_day_preserves_operator_edited_event_fields(tmp_path):
    """An operator-set facebook_event_url / description / event_date /
    location / event_type MUST survive a re-import (the importer only
    refreshes ``name``)."""
    csv_path = _write(
        tmp_path, "hard_enduro_testtown-2099-day1.csv", _UNIFIED_CSV
    )
    import_race_day(csv_path)

    event = Event.objects.get(slug="testtown")
    # Operator edits via /admin.
    from datetime import date

    event.facebook_event_url = "https://fb.com/events/123"
    event.description = "Operator-curated blurb. Do not clobber."
    event.event_date = date(2099, 7, 1)
    event.location = "Тестово"
    event.event_type = "hard_enduro"
    event.save()

    # Re-import the SAME CSV (e.g. a corrected results file).
    import_race_day(csv_path)

    event.refresh_from_db()
    assert event.facebook_event_url == "https://fb.com/events/123"
    assert event.description == "Operator-curated blurb. Do not clobber."
    assert str(event.event_date) == "2099-07-01"
    assert event.location == "Тестово"
    assert event.event_type == "hard_enduro"
    # `name` is the only field the importer refreshes.
    assert event.name == "Тестово Хард Ендуро"


@pytest.mark.django_db
def test_import_race_day_refreshes_only_name_on_changed_event_name(tmp_path):
    """If the CSV's `event` column changes, `name` updates — but editorial
    columns still don't (scoped UPDATE)."""
    p1 = _write(
        tmp_path, "hard_enduro_testtown-2099-day1.csv", _UNIFIED_CSV
    )
    import_race_day(p1)
    ev = Event.objects.get(slug="testtown")
    ev.facebook_event_url = "https://fb.com/keep-me"
    ev.save()

    p2 = _write(
        tmp_path,
        "hard_enduro_testtown-2099-day1.csv",
        _UNIFIED_CSV.replace("Тестово Хард Ендуро", "Тестово Хард Ендуро 2099"),
    )
    import_race_day(p2)

    ev.refresh_from_db()
    assert ev.name == "Тестово Хард Ендуро 2099"  # refreshed
    assert ev.facebook_event_url == "https://fb.com/keep-me"  # preserved


@pytest.mark.django_db
def test_upsert_calendar_preserves_human_curated_fields(tmp_path):
    """upsert_calendar refreshes name/date/location/sort_order but never
    facebook_event_url / description (X4 acceptance criterion)."""
    season = Season.objects.create(
        year=2026,
        name="BGX Hard Enduro 2026",
        slug="2026",
        is_current=False,
        championship_format="per_event",
    )
    # Pre-existing event with operator edits.
    ev = Event.objects.create(
        season=season,
        slug="kyrnare",
        name="stale name",
        sort_order=99,
    )
    ev.facebook_event_url = "https://fb.com/events/keep"
    ev.description = "Curated. Survive the upsert."
    ev.save()

    from core.management.commands.upsert_calendar import CALENDAR_2026

    upsert_year(2026, CALENDAR_2026)

    ev.refresh_from_db()
    # Calendar fields refreshed.
    assert ev.name == "Хард Ендуро Кърнаре 2026"
    assert str(ev.event_date) == "2026-03-28"
    assert ev.location == "Кърнаре"
    assert ev.sort_order == 0
    # Human-curated fields preserved.
    assert ev.facebook_event_url == "https://fb.com/events/keep"
    assert ev.description == "Curated. Survive the upsert."
    # New calendar-only events created.
    assert Event.objects.filter(season=season).count() == len(CALENDAR_2026)


# ===========================================================================
# 4. import_2025 — Race_<slug> / 0-DNS / 0.0-DNF semantics
# ===========================================================================


@pytest.mark.django_db
def test_import_2025_aggregate_semantics(tmp_path):
    agg_dir = tmp_path / "agg2025"
    agg_dir.mkdir()
    (agg_dir / "profi.csv").write_text(
        "RaceNumber,FirstName,LastName,Race_kyrnare,Race_buhovo,Race_kirkovo\n"
        "7,Иван,ИВАНОВ,25,0,22.0\n"
        "13,Петър,ПЕТРОВ,0,18,0.0\n"
        "99,Георги,ГЕОРГИЕВ,,15,\n",
        encoding="utf-8",
    )

    import_2025(agg_dir)

    season = Season.objects.get(year=2025)
    assert season.championship_format == "aggregate_2025"
    # 8 CATEGORIES_2025 + 7 RACE_ORDER_2025 events created.
    assert Category.objects.filter(season=season).count() == 8
    assert Event.objects.filter(season=season).count() == 7

    profi = Category.objects.get(season=season, code="profi")
    r7 = Rider.objects.get(category=profi, race_number=7)
    # `25` → kyrnare row; `0` → DNS (skipped); `22.0` → kirkovo points=22.
    pts7 = {
        er.event.slug: float(er.points)
        for er in EventResult.objects.filter(rider=r7).select_related("event")
    }
    assert pts7 == {"kyrnare": 25.0, "kirkovo": 22.0}

    r13 = Rider.objects.get(category=profi, race_number=13)
    # `0` kyrnare → skipped; `18` buhovo; `0.0` kirkovo → DNF, points=0 (kept).
    pts13 = {
        er.event.slug: float(er.points)
        for er in EventResult.objects.filter(rider=r13).select_related("event")
    }
    assert pts13 == {"buhovo": 18.0, "kirkovo": 0.0}

    r99 = Rider.objects.get(category=profi, race_number=99)
    # Empty cells skipped; only buhovo=15.
    pts99 = {
        er.event.slug: float(er.points)
        for er in EventResult.objects.filter(rider=r99).select_related("event")
    }
    assert pts99 == {"buhovo": 15.0}


@pytest.mark.django_db
def test_import_2025_rebuilds_season_idempotently(tmp_path):
    agg_dir = tmp_path / "agg2025"
    agg_dir.mkdir()
    (agg_dir / "profi.csv").write_text(
        "RaceNumber,FirstName,LastName,Race_kyrnare\n7,Иван,ИВАНОВ,25\n",
        encoding="utf-8",
    )
    import_2025(agg_dir)
    import_2025(agg_dir)  # second run wipes + rebuilds

    assert Season.objects.filter(year=2025).count() == 1
    assert Rider.objects.filter(season__year=2025).count() == 1
    assert EventResult.objects.filter(rider__season__year=2025).count() == 1


# ===========================================================================
# 5. seed_new — ImportLog (filename+sha256) dedup preserved
# ===========================================================================


@pytest.mark.django_db
def test_seed_new_logs_and_skips_already_imported(tmp_path, monkeypatch):
    # Build a fake seed_data tree: seed_root/2099/<csv>.
    seed_root = tmp_path / "seed_data"
    year_dir = seed_root / "2099"
    year_dir.mkdir(parents=True)
    csv_name = "hard_enduro_testtown-2099-day1.csv"
    (year_dir / csv_name).write_text(_UNIFIED_CSV, encoding="utf-8")

    import core.management.commands.seed_new as sn

    monkeypatch.setattr(sn, "_seed_root", lambda: seed_root)

    # First run: imports + writes one ImportLog row.
    seed_new(year=2099)
    assert ImportLog.objects.count() == 1
    log = ImportLog.objects.get()
    assert log.source_filename == csv_name
    expected_sha = hashlib.sha256(
        (year_dir / csv_name).read_bytes()
    ).hexdigest()
    assert log.sha256 == expected_sha
    assert log.rows_imported == 0
    assert EventResult.objects.filter(event__slug="testtown").count() == 3

    # Second run: same (filename, sha256) ⇒ skipped, no new log, no dup rows.
    seed_new(year=2099)
    assert ImportLog.objects.count() == 1
    assert EventResult.objects.filter(event__slug="testtown").count() == 3

    # Changing the file content ⇒ new sha ⇒ re-imported + a 2nd log row.
    (year_dir / csv_name).write_text(
        _UNIFIED_CSV.replace("Team A", "Team A2"), encoding="utf-8"
    )
    seed_new(year=2099)
    assert ImportLog.objects.count() == 2
    shas = set(ImportLog.objects.values_list("sha256", flat=True))
    assert expected_sha in shas and len(shas) == 2


@pytest.mark.django_db
def test_seed_new_dry_run_writes_no_log(tmp_path, monkeypatch):
    seed_root = tmp_path / "seed_data"
    year_dir = seed_root / "2099"
    year_dir.mkdir(parents=True)
    (year_dir / "hard_enduro_testtown-2099-day1.csv").write_text(
        _UNIFIED_CSV, encoding="utf-8"
    )

    import core.management.commands.seed_new as sn

    monkeypatch.setattr(sn, "_seed_root", lambda: seed_root)

    seed_new(year=2099, dry_run=True)
    assert ImportLog.objects.count() == 0
    assert Season.objects.filter(year=2099).count() == 0
