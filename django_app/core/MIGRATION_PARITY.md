# F2 — Column-by-Column Migration Parity

**Task:** F2 (Models + db_table pinning + fake-initial migration).
**Branch:** `django/f2-models`.
**Source of truth:** the live Postgres schema produced by running every
`backend/alembic/versions/0001..0007` migration (the SQLAlchemy models in
`backend/src/db/models.py` are the secondary cross-reference).

This file proves **zero schema drift** on the 8 adopted tables. It was not
hand-written from the models — it is the empirically-introspected diff between:

* **Oracle DB** — a fresh Postgres built by `alembic upgrade head` on the
  real `backend/alembic` migrations (a faithful prod-schema clone).
* **Django** — the schema `core/migrations/0001_initial` produces, plus the
  result of `migrate --fake-initial` run against the oracle DB.

Reproduce: see `core/MIGRATION_REHEARSAL.md`.

---

## 0. Headline result

| Check | Result |
|---|---|
| `makemigrations --check --dry-run` | **No changes detected** (exit 0) — model ⇔ migration consistent |
| `migrate core --fake-initial` vs prod-clone | `core.0001_initial ... FAKED` — **no DDL** issued to the 8 tables |
| 8-table column fingerprint, before vs after fake-initial | **byte-identical** (62 columns, indexes, constraints) |
| Django-from-scratch vs Alembic, order-independent | 62/62 columns identical type/len/precision/scale/nullability |
| Named `uq_*` constraints | match **name-for-name** |
| 5 explicit named indexes | **byte-identical** (name, table, columns, btree) |
| Django contrib tables | created fresh (`auth_*`, `django_*`) — **expected** |

---

## 1. Per-table column map (Django field → Alembic / live column)

Type key: `int4` = Postgres `integer` (32-bit), `int8` = `bigint`,
`vN` = `varchar(N)`, `num(6,2)` = `numeric(6,2)`, `tstz` = `timestamp with
time zone`. Nullable column = real DB `is_nullable`. "Alembic" = the migration
that introduced/created the column.

### `season`  (model `Season`, `db_table="season"`)

| Django field | db_column | Django type | Live column type | Null | Default (live) | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0001 |
| `year` | `year` | `IntegerField(unique=True)` | `int4` | NO | — | 0001 |
| `name` | `name` | `CharField(128)` | `v128` | NO | — | 0001 |
| `slug` | `slug` | `CharField(64, unique=True)` | `v64` | NO | — | 0001 |
| `is_current` | `is_current` | `BooleanField(default=False)` | `bool` | NO | `false` | 0001 |
| `championship_format` | `championship_format` | `CharField(32, default="per_event")` | `v32` | NO | `'per_event'` | 0001 |

### `category`  (model `Category`, `db_table="category"`)

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0001 |
| `season` | `season_id` | `FK(Season, CASCADE, db_index=False)` | `int4` | NO | — | 0001 |
| `code` | `code` | `CharField(64)` | `v64` | NO | — | 0001 |
| `display_name` | `display_name` | `CharField(128)` | `v128` | NO | — | 0001 |
| `sort_order` | `sort_order` | `IntegerField(default=0)` | `int4` | NO | `0` | 0001 |

Unique: `uq_category_season_code (season_id, code)` — Alembic 0001. ✔

### `event`  (model `Event`, `db_table="event"`)

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0001 |
| `season` | `season_id` | `FK(Season, CASCADE, db_index=False)` | `int4` | NO | — | 0001 |
| `slug` | `slug` | `CharField(64)` | `v64` | NO | — | 0001 |
| `name` | `name` | `CharField(128)` | `v128` | NO | — | 0001 |
| `event_date` | `event_date` | `DateField(null=True)` | `date` | YES | — | 0001 |
| `location` | `location` | `CharField(128, null=True)` | `v128` | YES | — | 0001 |
| `sort_order` | `sort_order` | `IntegerField(default=0)` | `int4` | NO | `0` | 0001 |
| `event_type` | `event_type` | `CharField(64, null=True)` | `v64` | YES | — | 0001 |
| `facebook_event_url` | `facebook_event_url` | `CharField(255, null=True)` | `v255` | YES | — | **0007** |
| `description` | `description` | `TextField(null=True)` | `text` | YES | — | **0007** |

Unique: `uq_event_season_slug (season_id, slug)` — Alembic 0001. ✔

### `rider`  (model `Rider`, `db_table="rider"`)

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0001 |
| `season` | `season_id` | `FK(Season, CASCADE, db_index=False)` | `int4` | NO | — | 0001 |
| `category` | `category_id` | `FK(Category, CASCADE, db_index=False)` | `int4` | NO | — | 0001 |
| `race_number` | `race_number` | `IntegerField` | `int4` | NO | — | 0001 |
| `first_name` | `first_name` | `CharField(128)` | `v128` | NO | — | 0001 |
| `last_name` | `last_name` | `CharField(128)` | `v128` | NO | — | 0001 |
| `team` | `team` | `CharField(255, null=True)` | `v255` | YES | — | 0001 |
| `bike` | `bike` | `CharField(255, null=True)` | `v255` | YES | — | 0001 |

Unique: `uq_rider_category_race_number (category_id, race_number)` — 0001. ✔

### `event_result`  (model `EventResult`, `db_table="event_result"`)

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0001 |
| `event` | `event_id` | `FK(Event, CASCADE, db_index=False)` | `int4` | NO | — | 0001 |
| `rider` | `rider_id` | `FK(Rider, CASCADE, db_index=False)` | `int4` | NO | — | 0001 |
| `day` | `day` | `IntegerField(default=1)` | `int4` | NO | `1` | **0002** |
| `position` | `position` | `IntegerField(null=True)` | `int4` | YES | — | 0001 |
| `points` | `points` | `DecimalField(max_digits=6, decimal_places=2, null=True)` | `num(6,2)` | YES | — | 0001 |
| `time_ms` | `time_ms` | `BigIntegerField(null=True)` | `int8` | YES | — | 0001 |
| `start_time_ms` | `start_time_ms` | `BigIntegerField(null=True)` | `int8` | YES | — | 0001 |
| `gps_penalty_ms` | `gps_penalty_ms` | `BigIntegerField(null=True)` | `int8` | YES | — | 0001 |
| `cp_penalty_ms` | `cp_penalty_ms` | `BigIntegerField(null=True)` | `int8` | YES | — | **0003** |
| `cp_count` | `cp_count` | `IntegerField(null=True)` | `int4` | YES | — | 0001 |
| `laps` | `laps` | `IntegerField(null=True)` | `int4` | YES | — | 0001 |
| `gap_ms` | `gap_ms` | `BigIntegerField(null=True)` | `int8` | YES | — | 0001 |
| `status` | `status` | `CharField(8, null=True)` | `v8` | YES | — | **0003** |
| `notes` | `notes` | `TextField(null=True)` | `text` | YES | — | 0001 |

Unique: `uq_result_event_rider_day (event_id, rider_id, day)` — Alembic 0002
(replaced the 0001 `uq_result_event_rider`; the live DB carries only the
day-scoped one — reproduced). ✔
Indexes: `ix_result_event (event_id)`, `ix_result_rider (rider_id)` — 0001. ✔

### `visit`  (model `Visit`, `db_table="visit"`)

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0001 |
| `timestamp` | `timestamp` | `DateTimeField` | `tstz` | NO | `now()` | 0001 |
| `page` | `page` | `CharField(64)` | `v64` | NO | — | 0001 |
| `category` | `category` | `CharField(64, null=True)` | `v64` | YES | — | 0001 |
| `season_year` | `season_year` | `IntegerField(null=True)` | `int4` | YES | — | 0001 |
| `device_type` | `device_type` | `CharField(16, default="unknown")` | `v16` | NO | `'unknown'` | 0001 |
| `visitor_id` | `visitor_id` | `CharField(32, default="")` | `v32` | NO | `''` | **0004** |
| `session_id` | `session_id` | `CharField(36, default="")` | `v36` | NO | `''` | **0004** |
| `event_slug` | `event_slug` | `CharField(64, null=True)` | `v64` | YES | — | **0004** |
| `rider_slug` | `rider_slug` | `CharField(128, null=True)` | `v128` | YES | — | **0004** |
| `compared_with_slug` | `compared_with_slug` | `CharField(128, null=True)` | `v128` | YES | — | **0006** |

Indexes: `ix_visit_timestamp (timestamp)` — Alembic 0001;
`ix_visit_visitor_time (visitor_id, timestamp)` — Alembic 0004. ✔

### `import_log`  (model `ImportLog`, `db_table="import_log"`)  — Alembic 0005

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `id` | `id` | `AutoField` | `int4` PK | NO | identity/seq | 0005 |
| `source_filename` | `source_filename` | `CharField(255)` | `v255` | NO | — | 0005 |
| `sha256` | `sha256` | `CharField(64)` | `v64` | NO | — | 0005 |
| `imported_at` | `imported_at` | `DateTimeField` | `tstz` | NO | `now()` | 0005 |
| `rows_imported` | `rows_imported` | `IntegerField(default=0)` | `int4` | NO | `0` | 0005 |

Unique: `uq_import_log_file_sha (source_filename, sha256)` — Alembic 0005.
Index: `ix_import_log_filename (source_filename)` — Alembic 0005.
**Note:** these two exist in the live DB (migration 0005) but are **absent
from the SQLAlchemy model** `backend/src/db/models.py`. The DB is the source
of truth, so they are reproduced. ✔

### `analytics_salt`  (model `AnalyticsSalt`, `db_table="analytics_salt"`)  — Alembic 0004

| Django field | db_column | Django type | Live column type | Null | Default | Alembic |
|---|---|---|---|---|---|---|
| `day` | `day` | `DateField(primary_key=True)` | `date` PK | NO | — | 0004 |
| `salt` | `salt` | `CharField(64)` | `v64` | NO | — | 0004 |

No surrogate `id` — the PK **is** `day` (`analytics_salt_pkey ON (day)`). ✔

---

## 2. FK / on_delete parity

All 6 FKs are `ON DELETE CASCADE` in the live schema (introspected via
`information_schema.referential_constraints`), matching the Alembic
`ondelete="CASCADE"` and the SQLAlchemy `ondelete="CASCADE"`. Reproduced as
Django `on_delete=models.CASCADE`:

| FK | columns | delete rule |
|---|---|---|
| `category.season_id → season.id` | season_id | CASCADE |
| `event.season_id → season.id` | season_id | CASCADE |
| `rider.season_id → season.id` | season_id | CASCADE |
| `rider.category_id → category.id` | category_id | CASCADE |
| `event_result.event_id → event.id` | event_id | CASCADE |
| `event_result.rider_id → rider.id` | rider_id | CASCADE |

The reverse SQLAlchemy `cascade="all, delete-orphan"` relationships are an
ORM-side concern, not a DB constraint — Django's ORM-side cascade follows from
`on_delete=CASCADE` + the DB FK; no schema implication.

`db_index=False` is pinned on **every** FK because the live schema has **no**
b-tree index on any FK column (Alembic created none; Postgres does not
auto-index FKs). Django would otherwise emit an implicit FK index, diverging
from prod. (`event_result.event_id`/`rider_id` ARE indexed — but by the
*explicit* `ix_result_event`/`ix_result_rider`, modeled in `Meta.indexes`.)

---

## 3. Documented, fake-initial-irrelevant differences

These appear only if Django ever builds the 8 tables **from scratch**, which
never happens in the prod adoption path (`--fake-initial` issues zero DDL to
existing tables — proven empirically, §0). They are recorded for the HITL
reviewer, not defects:

1. **Physical column order.** Alembic appended `event_result.day`,
   `cp_penalty_ms`, `status` and the FK columns via `ALTER TABLE`, so they
   land last; Django's `CREATE TABLE` inlines them. `--fake-initial` does not
   compare column order — only table+column existence/shape. Order-independent
   diff: **62/62 columns identical**.
2. **PK default mechanism.** Live: `nextval('*_id_seq')` (Alembic SERIAL-style
   sequence). Django 6: `GENERATED BY DEFAULT AS IDENTITY`. **Same `integer`
   type**, different default generator. Under fake-initial the existing
   sequences are untouched and keep working. (`AutoField`, *not*
   `BigAutoField`, is pinned via `CoreConfig.default_auto_field` so the type
   is `int4`, matching prod — `BigAutoField` would have been `int8` drift.)
3. **FK constraint names.** Live: `<table>_<col>_fkey` (Alembic). Django:
   `<table>_<col>_<hash>_fk_<ref>`. Same columns, same CASCADE. fake-initial
   does not touch existing constraints. (The *named* `uq_*` constraints DO
   match exactly — verified name-for-name.)
4. **`season_slug_…_like` pattern-ops index.** Django adds a
   `varchar_pattern_ops` LIKE index for `unique=True` CharFields on Postgres;
   the live schema has only `season_slug_key` (the UNIQUE constraint), no
   `_like` index. Purely a `LIKE` query optimization; absence in prod is
   harmless and fake-initial never creates it.

None of (1)–(4) cause `migrate --fake-initial` to emit DDL against the 8
existing tables — verified: identical schema fingerprint before vs after.
