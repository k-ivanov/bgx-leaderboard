"""F2 — model/schema parity assertions.

These lock the structural contract in code so a later refactor cannot silently
drift the adopted schema. The *runtime* old↔new JSON parity rig is F3's job;
this file only asserts what F2 owns:

* every model's ``Meta.db_table`` is pinned to the existing Alembic table;
* every column's ``db_column`` is pinned (no Django name derivation);
* PK is ``AutoField`` (int4), not ``BigAutoField`` (int8) — matches the real
  ``*_id_seq`` sequences;
* FK ``on_delete=CASCADE`` + ``db_index=False`` on all 6 FKs;
* the named unique constraints + explicit indexes are present with the exact
  Alembic names;
* ``__str__`` is byte-identical to ``backend/src/db/models.py``.

Pure-metadata tests need no DB. The ``__str__`` cases use ``django_db`` (the
harness falls back to in-memory sqlite when ``DATABASE_URL`` is unset).
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.db import models as dj_models

from core.models import (
    AnalyticsSalt,
    Category,
    Event,
    EventResult,
    ImportLog,
    Rider,
    Season,
    Visit,
)

ALL_MODELS = [
    Season,
    Category,
    Event,
    Rider,
    EventResult,
    Visit,
    ImportLog,
    AnalyticsSalt,
]

EXPECTED_TABLES = {
    Season: "season",
    Category: "category",
    Event: "event",
    Rider: "rider",
    EventResult: "event_result",
    Visit: "visit",
    ImportLog: "import_log",
    AnalyticsSalt: "analytics_salt",
}


def _field(model, name):
    return model._meta.get_field(name)


# --------------------------------------------------------------------------- #
# db_table / db_column pinning
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("model,table", EXPECTED_TABLES.items())
def test_db_table_pinned(model, table):
    assert model._meta.db_table == table


@pytest.mark.parametrize("model", ALL_MODELS)
def test_every_concrete_field_pins_db_column(model):
    """No field may rely on Django's column-name derivation."""
    for f in model._meta.concrete_fields:
        assert f.db_column, f"{model.__name__}.{f.name} has no explicit db_column"


def test_eight_models_only():
    assert len(ALL_MODELS) == 8


# --------------------------------------------------------------------------- #
# PK type: AutoField (int4), never BigAutoField (int8)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "model",
    [Season, Category, Event, Rider, EventResult, Visit, ImportLog],
)
def test_surrogate_pk_is_autofield_not_bigauto(model):
    pk = model._meta.pk
    assert isinstance(pk, dj_models.AutoField)
    assert not isinstance(pk, dj_models.BigAutoField), (
        f"{model.__name__}.id is BigAutoField — real *_id_seq is int4"
    )
    assert pk.db_column == "id"


def test_analytics_salt_pk_is_day_no_surrogate_id():
    pk = AnalyticsSalt._meta.pk
    assert pk.name == "day"
    assert isinstance(pk, dj_models.DateField)
    assert pk.db_column == "day"
    assert not any(f.name == "id" for f in AnalyticsSalt._meta.fields)


# --------------------------------------------------------------------------- #
# Foreign keys: CASCADE + no implicit index (live schema has none)
# --------------------------------------------------------------------------- #

FK_SPECS = [
    (Category, "season", "season_id"),
    (Event, "season", "season_id"),
    (Rider, "season", "season_id"),
    (Rider, "category", "category_id"),
    (EventResult, "event", "event_id"),
    (EventResult, "rider", "rider_id"),
]


@pytest.mark.parametrize("model,fname,col", FK_SPECS)
def test_fk_cascade_and_no_implicit_index(model, fname, col):
    f = _field(model, fname)
    assert isinstance(f, dj_models.ForeignKey)
    assert f.db_column == col
    assert f.remote_field.on_delete is dj_models.CASCADE
    # Live Postgres has NO b-tree on any FK column — Django must not add one.
    assert f.db_index is False, f"{model.__name__}.{fname} would create an implicit FK index"


# --------------------------------------------------------------------------- #
# Unique constraints (exact Alembic names)
# --------------------------------------------------------------------------- #

def _constraint_names(model):
    return {c.name for c in model._meta.constraints}


def test_unique_constraint_names_match_alembic():
    assert "uq_category_season_code" in _constraint_names(Category)
    assert "uq_event_season_slug" in _constraint_names(Event)
    assert "uq_rider_category_race_number" in _constraint_names(Rider)
    # 0002 replaced uq_result_event_rider with the day-scoped one.
    assert "uq_result_event_rider_day" in _constraint_names(EventResult)
    assert "uq_result_event_rider" not in _constraint_names(EventResult)
    # 0005: present in the live DB even though absent from the SA model.
    assert "uq_import_log_file_sha" in _constraint_names(ImportLog)


def test_event_result_unique_is_per_day_triple():
    c = next(
        c for c in EventResult._meta.constraints
        if c.name == "uq_result_event_rider_day"
    )
    assert list(c.fields) == ["event", "rider", "day"]


# --------------------------------------------------------------------------- #
# Explicit named indexes
# --------------------------------------------------------------------------- #

def _index_names(model):
    return {i.name for i in model._meta.indexes}


def test_explicit_indexes_match_alembic_names():
    assert _index_names(EventResult) == {"ix_result_event", "ix_result_rider"}
    assert _index_names(Visit) == {"ix_visit_timestamp", "ix_visit_visitor_time"}
    assert _index_names(ImportLog) == {"ix_import_log_filename"}


def test_visit_visitor_time_index_is_composite():
    idx = next(
        i for i in Visit._meta.indexes if i.name == "ix_visit_visitor_time"
    )
    assert list(idx.fields) == ["visitor_id", "timestamp"]


# --------------------------------------------------------------------------- #
# Column type pins that matter for parity
# --------------------------------------------------------------------------- #

def test_points_is_numeric_6_2():
    f = _field(EventResult, "points")
    assert isinstance(f, dj_models.DecimalField)
    assert f.max_digits == 6 and f.decimal_places == 2
    assert f.null is True


@pytest.mark.parametrize(
    "name", ["time_ms", "start_time_ms", "gps_penalty_ms", "cp_penalty_ms", "gap_ms"]
)
def test_ms_columns_are_bigint(name):
    assert isinstance(_field(EventResult, name), dj_models.BigIntegerField)


def test_charfield_max_lengths_pinned():
    assert _field(Season, "name").max_length == 128
    assert _field(Season, "slug").max_length == 64
    assert _field(Season, "championship_format").max_length == 32
    assert _field(Visit, "visitor_id").max_length == 32
    assert _field(Visit, "session_id").max_length == 36
    assert _field(Visit, "rider_slug").max_length == 128
    assert _field(Visit, "compared_with_slug").max_length == 128
    assert _field(EventResult, "status").max_length == 8
    assert _field(ImportLog, "sha256").max_length == 64


def test_server_default_parity_via_field_default():
    assert _field(Season, "is_current").default is False
    assert _field(Season, "championship_format").default == "per_event"
    assert _field(Category, "sort_order").default == 0
    assert _field(Event, "sort_order").default == 0
    assert _field(EventResult, "day").default == 1
    assert _field(Visit, "device_type").default == "unknown"
    assert _field(Visit, "visitor_id").default == ""
    assert _field(Visit, "session_id").default == ""
    assert _field(ImportLog, "rows_imported").default == 0


# --------------------------------------------------------------------------- #
# __str__ parity — byte-identical to backend/src/db/models.py
# --------------------------------------------------------------------------- #

@pytest.mark.django_db
def test_str_parity_ported_verbatim():
    s = Season.objects.create(
        year=2025, name="Season 2025", slug="2025", is_current=True
    )
    assert str(s) == "2025"  # SA: str(self.year)

    c = Category.objects.create(
        season=s, code="expert", display_name="Expert", sort_order=0
    )
    assert str(c) == "Expert (2025)"  # SA: f"{display_name} ({season.year})"

    e = Event.objects.create(
        season=s, slug="r1", name="Round 1", sort_order=0
    )
    assert str(e) == "Round 1 (2025)"  # SA: f"{name} ({season.year})"

    r = Rider.objects.create(
        season=s, category=c, race_number=7,
        first_name="Иван", last_name="ИВАНОВ",
    )
    assert str(r) == "#7 Иван ИВАНОВ"  # SA: f"#{race_number} {first} {last}"

    # EventResult.__str__: pos / em-dash, " D{day}" only when day > 1.
    er1 = EventResult.objects.create(
        event=e, rider=r, day=1, position=3, points=Decimal("17.00")
    )
    assert str(er1) == f"P3 {r} @ {e}"  # day==1 -> no suffix
    er2 = EventResult.objects.create(
        event=e, rider=r, day=2, position=None
    )
    assert str(er2) == f"— {r} @ {e} D2"  # no position -> "—", day>1 -> " D2"


@pytest.mark.django_db
def test_analytics_salt_roundtrip_date_pk():
    AnalyticsSalt.objects.create(day=date(2026, 5, 17), salt="abc123")
    got = AnalyticsSalt.objects.get(pk=date(2026, 5, 17))
    assert got.salt == "abc123"


@pytest.mark.django_db
def test_visit_and_import_log_minimal_rows():
    Visit.objects.create(
        timestamp=datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc),
        page="results",
    )
    assert Visit.objects.count() == 1
    ImportLog.objects.create(
        source_filename="2025.csv",
        sha256="0" * 64,
        imported_at=datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc),
    )
    assert ImportLog.objects.filter(source_filename="2025.csv").exists()
