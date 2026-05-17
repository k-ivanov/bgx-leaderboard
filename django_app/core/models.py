"""Ported Django ORM models — FILLED BY F2.

These 8 models are a *byte-for-byte schema mirror* of the existing production
schema built by ``backend/alembic/versions/0001..0007`` (the SQLAlchemy models
in ``backend/src/db/models.py`` are the secondary reference; the Alembic
migrations + the live Postgres they produce are the authoritative source).

Adoption invariant (decision I2-arch=A)
---------------------------------------
The 8 tables ``season``, ``category``, ``event``, ``rider``, ``event_result``,
``visit``, ``import_log``, ``analytics_salt`` are adopted with **ZERO schema
change** — ``manage.py migrate --fake-initial`` records ``0001_initial`` as
applied without issuing any ``CREATE/ALTER/DROP`` against them. Django's own
``auth`` / ``admin`` / ``sessions`` / ``contenttypes`` tables ARE created
fresh — that is expected and documented (``MIGRATION_REHEARSAL.md``).

Why these field choices (verified against the live Alembic-built schema):

* **PK = AutoField, not BigAutoField.** The real ``*_id_seq`` sequences are
  32-bit ``integer`` (Alembic ``sa.Integer()`` primary keys). ``core``'s
  ``AppConfig.default_auto_field`` is pinned to ``AutoField`` so the implicit
  ``id`` is ``integer`` — matching prod. (Project-wide default stays
  ``BigAutoField``; Django contrib tables are created fresh and may use
  ``bigint`` — that is fine and intentional.)
* **No implicit FK index.** Django adds ``db_index=True`` to ForeignKeys by
  default, but the real Postgres schema has **no** index on
  ``category.season_id``, ``event.season_id``, ``rider.season_id``,
  ``rider.category_id`` (Alembic created none). Every FK therefore pins
  ``db_index=False`` to stay an honest mirror. ``event_result.event_id`` /
  ``rider_id`` DO have explicit indexes (``ix_result_event`` /
  ``ix_result_rider``) — reproduced via ``Meta.indexes`` with the exact names.
* **``db_column`` is pinned on every field** and ``Meta.db_table`` on every
  model so nothing depends on Django's name derivation.
* ``server_default`` parity: Postgres column defaults are reproduced with
  ``default=`` (Django writes the value app-side; the existing prod rows
  already carry the Alembic ``server_default`` so no data changes).
* ``__str__`` bodies are ported verbatim from ``backend/src/db/models.py``.

See ``core/MIGRATION_PARITY.md`` for the full column-by-column diff table and
``core/MIGRATION_REHEARSAL.md`` for the HITL prod-clone fake-initial runbook.
"""

from __future__ import annotations

from django.db import models


class Season(models.Model):
    """``season`` — one championship year. Alembic 0001."""

    id = models.AutoField(primary_key=True, db_column="id")
    year = models.IntegerField(db_column="year", unique=True)
    name = models.CharField(max_length=128, db_column="name")
    slug = models.CharField(max_length=64, unique=True, db_column="slug")
    is_current = models.BooleanField(default=False, db_column="is_current")
    # 'per_event' (default) | 'aggregate_2025' (legacy). See the SQLAlchemy
    # model docstring + docs/scoring.md — behavior is owned by S2, not F2.
    championship_format = models.CharField(
        max_length=32, default="per_event", db_column="championship_format"
    )

    class Meta:
        db_table = "season"
        managed = True

    def __str__(self) -> str:
        return str(self.year)


class Category(models.Model):
    """``category`` — a class within a season (Expert, Hobby, …). Alembic 0001."""

    id = models.AutoField(primary_key=True, db_column="id")
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        db_column="season_id",
        db_index=False,
        related_name="categories",
    )
    code = models.CharField(max_length=64, db_column="code")
    display_name = models.CharField(max_length=128, db_column="display_name")
    sort_order = models.IntegerField(default=0, db_column="sort_order")

    class Meta:
        db_table = "category"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["season", "code"], name="uq_category_season_code"
            )
        ]

    def __str__(self) -> str:
        return f"{self.display_name} ({self.season.year})"


class Event(models.Model):
    """``event`` — a race in the calendar (UI: "Race"). Alembic 0001 + 0007."""

    id = models.AutoField(primary_key=True, db_column="id")
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        db_column="season_id",
        db_index=False,
        related_name="events",
    )
    slug = models.CharField(max_length=64, db_column="slug")
    name = models.CharField(max_length=128, db_column="name")
    event_date = models.DateField(null=True, blank=True, db_column="event_date")
    location = models.CharField(
        max_length=128, null=True, blank=True, db_column="location"
    )
    sort_order = models.IntegerField(default=0, db_column="sort_order")
    event_type = models.CharField(
        max_length=64, null=True, blank=True, db_column="event_type"
    )
    # Editorial (Alembic 0007) — set via admin, never by the importer.
    facebook_event_url = models.CharField(
        max_length=255, null=True, blank=True, db_column="facebook_event_url"
    )
    description = models.TextField(null=True, blank=True, db_column="description")

    class Meta:
        db_table = "event"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["season", "slug"], name="uq_event_season_slug"
            )
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.season.year})"


class Rider(models.Model):
    """``rider`` — a rider entry, scoped to (season, category). Alembic 0001."""

    id = models.AutoField(primary_key=True, db_column="id")
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        db_column="season_id",
        db_index=False,
        related_name="riders",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        db_column="category_id",
        db_index=False,
        related_name="riders",
    )
    race_number = models.IntegerField(db_column="race_number")
    first_name = models.CharField(max_length=128, db_column="first_name")
    last_name = models.CharField(max_length=128, db_column="last_name")
    team = models.CharField(
        max_length=255, null=True, blank=True, db_column="team"
    )
    bike = models.CharField(
        max_length=255, null=True, blank=True, db_column="bike"
    )

    class Meta:
        db_table = "rider"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["category", "race_number"],
                name="uq_rider_category_race_number",
            )
        ]

    def __str__(self) -> str:
        return f"#{self.race_number} {self.first_name} {self.last_name}"


class EventResult(models.Model):
    """``event_result`` — one rider's result for one event-day.

    Alembic 0001 (base) + 0002 (``day`` + per-day unique) + 0003
    (``cp_penalty_ms`` + ``status``). The real Postgres column order is
    base-cols, then ``day``, ``cp_penalty_ms``, ``status`` appended last;
    ``--fake-initial`` does not compare column order so this is parity-safe.
    """

    id = models.AutoField(primary_key=True, db_column="id")
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        db_column="event_id",
        db_index=False,
        related_name="results",
    )
    rider = models.ForeignKey(
        Rider,
        on_delete=models.CASCADE,
        db_column="rider_id",
        db_index=False,
        related_name="results",
    )
    # Day within the event (1 for single-day). server_default "1" (Alembic 0002).
    day = models.IntegerField(default=1, db_column="day")
    position = models.IntegerField(
        null=True, blank=True, db_column="position"
    )
    # Postgres numeric(6,2).
    points = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
        db_column="points",
    )
    time_ms = models.BigIntegerField(
        null=True, blank=True, db_column="time_ms"
    )
    start_time_ms = models.BigIntegerField(
        null=True, blank=True, db_column="start_time_ms"
    )
    gps_penalty_ms = models.BigIntegerField(
        null=True, blank=True, db_column="gps_penalty_ms"
    )
    # Alembic 0003. cp_count (count) is distinct and kept for forward compat.
    cp_penalty_ms = models.BigIntegerField(
        null=True, blank=True, db_column="cp_penalty_ms"
    )
    cp_count = models.IntegerField(
        null=True, blank=True, db_column="cp_count"
    )
    laps = models.IntegerField(null=True, blank=True, db_column="laps")
    gap_ms = models.BigIntegerField(
        null=True, blank=True, db_column="gap_ms"
    )
    # FIN / DNF / DNS / DSQ — Alembic 0003. Nullable for legacy rows.
    status = models.CharField(
        max_length=8, null=True, blank=True, db_column="status"
    )
    notes = models.TextField(null=True, blank=True, db_column="notes")

    class Meta:
        db_table = "event_result"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["event", "rider", "day"],
                name="uq_result_event_rider_day",
            )
        ]
        indexes = [
            models.Index(fields=["event"], name="ix_result_event"),
            models.Index(fields=["rider"], name="ix_result_rider"),
        ]

    def __str__(self) -> str:
        pos = f"P{self.position}" if self.position else "—"
        day_suffix = f" D{self.day}" if self.day > 1 else ""
        return f"{pos} {self.rider} @ {self.event}{day_suffix}"


class Visit(models.Model):
    """``visit`` — one cookieless analytics page-view row.

    Alembic 0001 (base) + 0004 (visitor_id/session_id/event_slug/rider_slug
    + ix_visit_visitor_time) + 0006 (compared_with_slug).
    """

    id = models.AutoField(primary_key=True, db_column="id")
    # server_default now(); set app-side by S6. auto_now_add is intentionally
    # NOT used — the write path (S6) sets it; F2 only pins the column shape.
    timestamp = models.DateTimeField(db_column="timestamp")
    page = models.CharField(max_length=64, db_column="page")
    category = models.CharField(
        max_length=64, null=True, blank=True, db_column="category"
    )
    season_year = models.IntegerField(
        null=True, blank=True, db_column="season_year"
    )
    device_type = models.CharField(
        max_length=16, default="unknown", db_column="device_type"
    )
    visitor_id = models.CharField(
        max_length=32, default="", db_column="visitor_id"
    )
    session_id = models.CharField(
        max_length=36, default="", db_column="session_id"
    )
    event_slug = models.CharField(
        max_length=64, null=True, blank=True, db_column="event_slug"
    )
    rider_slug = models.CharField(
        max_length=128, null=True, blank=True, db_column="rider_slug"
    )
    # For page='compare', the second rider's slug (pair normalized
    # alphabetically). Null for every other page type. Alembic 0006.
    compared_with_slug = models.CharField(
        max_length=128, null=True, blank=True, db_column="compared_with_slug"
    )

    class Meta:
        db_table = "visit"
        managed = True
        indexes = [
            models.Index(fields=["timestamp"], name="ix_visit_timestamp"),
            models.Index(
                fields=["visitor_id", "timestamp"],
                name="ix_visit_visitor_time",
            ),
        ]


class ImportLog(models.Model):
    """``import_log`` — one row per imported seed CSV (filename+sha256 dedup).

    Alembic 0005. NOTE: the unique constraint ``uq_import_log_file_sha`` and
    the ``ix_import_log_filename`` index exist in the real schema (added by
    migration 0005) even though they are absent from the SQLAlchemy model —
    the DB is the source of truth, so they are reproduced here.
    """

    id = models.AutoField(primary_key=True, db_column="id")
    source_filename = models.CharField(
        max_length=255, db_column="source_filename"
    )
    sha256 = models.CharField(max_length=64, db_column="sha256")
    # server_default now() (Alembic 0005).
    imported_at = models.DateTimeField(db_column="imported_at")
    rows_imported = models.IntegerField(
        default=0, db_column="rows_imported"
    )

    class Meta:
        db_table = "import_log"
        managed = True
        constraints = [
            models.UniqueConstraint(
                fields=["source_filename", "sha256"],
                name="uq_import_log_file_sha",
            )
        ]
        indexes = [
            models.Index(
                fields=["source_filename"], name="ix_import_log_filename"
            )
        ]


class AnalyticsSalt(models.Model):
    """``analytics_salt`` — daily pseudonymous-ID salt. Date PK. Alembic 0004.

    No surrogate ``id``: the primary key IS ``day`` (a ``DateField``), exactly
    as in the real schema (``analytics_salt_pkey`` on ``day``).
    """

    day = models.DateField(primary_key=True, db_column="day")
    salt = models.CharField(max_length=64, db_column="salt")

    class Meta:
        db_table = "analytics_salt"
        managed = True
