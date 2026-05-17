# F2 — `migrate --fake-initial` Rehearsal Runbook (HITL gate)

> **This is the human sign-off gate.** F2's branch is NOT auto-merged. A human
> must run §3 (the prod-clone rehearsal) against a restored production DB and
> sign off before merge. The sandbox rehearsal in §2 used an Alembic-built
> *prod-schema clone* (faithful structurally) — it does **not** substitute for
> §3 against real production data with operator-edited rows.

---

## 0. What "adopt with zero schema change" means here

Decision **I2-arch=A**. Two distinct outcomes are *expected and correct*:

* **The 8 existing tables** (`season`, `category`, `event`, `rider`,
  `event_result`, `visit`, `import_log`, `analytics_salt`) — adopted with
  **zero** `CREATE/ALTER/DROP`. `migrate --fake-initial` records
  `core.0001_initial` as applied (`FAKED`) because Django's introspection
  finds all 8 tables already present with matching shape.
* **Django's own contrib tables** (`auth_*`, `django_admin_log`,
  `django_content_type`, `django_migrations`, `django_session`) — **created
  fresh**. This is *required* (admin/auth/sessions need them). The old "no
  CREATE TABLE at all" framing is false once Django admin (X3) exists.
* `alembic_version` (the existing Alembic bookkeeping table) is left
  untouched. Harmless; it can be dropped manually post-cutover if desired
  (not in F2 scope).

X3 note (carried, not implemented here): once Django auth exists,
`createsuperuser` / a credential-bootstrap path **replaces** the old
`ADMIN_PASSWORD` env-gated shared-credential admin. X3 owns that migration of
the operator off `ADMIN_PASSWORD`.

---

## 1. Prerequisites (on the machine running the rehearsal)

```bash
# Django deps (separate from backend/; see django_app/pyproject.toml)
cd django_app
python3 -m venv .venv && . .venv/bin/activate
pip install "django>=6.0,<7.0" "django-ninja>=1.3" "psycopg[binary]>=3.2" \
            "python-dotenv>=1.0" "dj-database-url>=2.2"
# (or: pip install -e ".[dev]" once pyproject gets a build-system table)
```

`pg_dump` / `psql` (client matching the prod Postgres major version).

---

## 2. Sandbox rehearsal already performed (structural clone, NOT prod data)

Run on `django/f2-models` in the agent sandbox. **Result: PASS, structurally.**
Reproducible:

```bash
# A. Build a faithful prod-SCHEMA clone with the REAL Alembic migrations
docker compose up -d postgres
docker exec bgx-postgres psql -U bgx -d bgx -c "CREATE DATABASE bgx_oracle;"
cd backend
DATABASE_URL="postgresql://bgx:bgx@localhost:5432/bgx_oracle" PYTHONPATH=. \
  python -m alembic upgrade head        # 0001 → 0007

# B. Snapshot the 8-table schema fingerprint BEFORE any Django command
#    (information_schema.columns + pg_indexes + table_constraints)

# C. Run Django fake-initial against that clone
cd ../django_app
export DATABASE_URL="postgresql://bgx:bgx@localhost:5432/bgx_oracle"
python manage.py migrate --plan                 # inspect ordering
python manage.py migrate core --fake-initial -v 2
#   -> "Applying core.0001_initial... FAKED"
python manage.py migrate --fake-initial         # contrib apps create fresh

# D. Re-snapshot the 8-table fingerprint and diff vs (B)
```

**Observed (sandbox):**

| Assertion | Result |
|---|---|
| `makemigrations --check --dry-run` | `No changes detected` (exit 0) |
| `migrate core --fake-initial` | `core.0001_initial ... FAKED` (0.013s, no DDL) |
| 8-table column fingerprint, before vs after | **byte-identical** |
| 8-table index fingerprint, before vs after | **byte-identical** |
| 8-table constraint fingerprint, before vs after | **byte-identical** |
| Contrib tables after `migrate` | `auth_*`, `django_admin_log`, `django_content_type`, `django_migrations`, `django_session` created |
| `django_migrations` rows | `core.0001_initial` + contrib all recorded |
| Order-independent Django-from-scratch vs Alembic | 62/62 columns identical type/len/precision/scale/nullability; all named `uq_*` + 5 explicit indexes byte-identical |

Cosmetic, fake-initial-irrelevant differences (column order, PK
IDENTITY-vs-sequence, FK auto-names, `season_slug_*_like` index) are
catalogued in `MIGRATION_PARITY.md §3`. None caused DDL against the 8 tables.

---

## 3. PRODUCTION-CLONE rehearsal — the HITL step (a human must run this)

> **Not yet performed.** The agent sandbox has no access to a restored
> production database. This section is the exact procedure for the human
> sign-off. Run it against a **restored clone of prod**, never prod itself.

```bash
# 3.1 Take a fresh logical dump of PROD (read-only; or use the latest backup)
pg_dump --no-owner --no-privileges \
  "$PROD_DATABASE_URL" -Fc -f /tmp/bgx_prod_clone.dump

# 3.2 Restore into a throwaway DB
createdb bgx_prodclone
pg_restore --no-owner --no-privileges -d bgx_prodclone /tmp/bgx_prod_clone.dump

# 3.3 Capture the BEFORE fingerprint of the 8 domain tables + a data snapshot
PSQL="psql bgx_prodclone -tAF'|'"
$PSQL -c "SELECT table_name, ordinal_position, column_name, data_type,
  COALESCE(character_maximum_length::text,''),
  COALESCE(numeric_precision::text,''), COALESCE(numeric_scale::text,''),
  is_nullable, COALESCE(column_default,'')
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name IN
  ('season','category','event','rider','event_result','visit','import_log','analytics_salt')
  ORDER BY 1,2;" > /tmp/before_cols.txt
$PSQL -c "SELECT tablename,indexname,indexdef FROM pg_indexes
  WHERE schemaname='public' AND tablename IN
  ('season','category','event','rider','event_result','visit','import_log','analytics_salt')
  ORDER BY 1,2;" > /tmp/before_idx.txt
# Row counts + a few operator-edited rows (event.facebook_event_url / description)
$PSQL -c "SELECT 'season',count(*) FROM season UNION ALL
  SELECT 'event',count(*) FROM event UNION ALL
  SELECT 'event_result',count(*) FROM event_result UNION ALL
  SELECT 'rider',count(*) FROM rider UNION ALL
  SELECT 'visit',count(*) FROM visit;" > /tmp/before_counts.txt
$PSQL -c "SELECT id,slug,facebook_event_url,description FROM event
  WHERE facebook_event_url IS NOT NULL OR description IS NOT NULL
  ORDER BY id;" > /tmp/before_editorial.txt

# 3.4 Run the Django adoption migration against the clone
cd django_app && . .venv/bin/activate
export DATABASE_URL="postgresql:///bgx_prodclone"   # or full URL to the clone
python manage.py migrate --plan | tee /tmp/migrate_plan.txt
python manage.py migrate --fake-initial -v 2 | tee /tmp/migrate_run.txt

# 3.5 Capture the AFTER fingerprint + data snapshot (same queries as 3.3)
#     -> /tmp/after_cols.txt /tmp/after_idx.txt /tmp/after_counts.txt
#        /tmp/after_editorial.txt

# 3.6 VERIFY (all five must hold)
diff /tmp/before_cols.txt  /tmp/after_cols.txt   # MUST be empty
diff /tmp/before_idx.txt   /tmp/after_idx.txt    # MUST be empty
diff /tmp/before_counts.txt /tmp/after_counts.txt # MUST be empty (no data loss)
diff /tmp/before_editorial.txt /tmp/after_editorial.txt # MUST be empty
grep -E 'core\.0001_initial.*FAKED' /tmp/migrate_run.txt   # MUST match
psql bgx_prodclone -c "\dt" | grep -E 'auth_user|django_session|django_content_type'
#     ^ contrib tables MUST now exist (created fresh)
psql bgx_prodclone -tAc \
  "SELECT app,name FROM django_migrations WHERE app='core';"
#     ^ MUST show core | 0001_initial
```

### Sign-off checklist (human ticks each)

- [ ] `migrate_run.txt` shows `Applying core.0001_initial... FAKED` (no DDL).
- [ ] `before_cols` ≡ `after_cols` (8 tables, zero column drift).
- [ ] `before_idx` ≡ `after_idx` (8 tables, zero index drift).
- [ ] Row counts unchanged on all 8 tables (no data loss).
- [ ] Operator-edited `event.facebook_event_url` / `description` rows
      unchanged (CSV importer never sets these — prod-only data, the reason a
      CSV fixture is insufficient and this prod-clone step exists).
- [ ] Django contrib tables (`auth_*`, `django_*`) created.
- [ ] `django_migrations` has `core | 0001_initial`.
- [ ] Roll the clone forward once more (`migrate` again) → **no-op**
      (idempotent; `No migrations to apply`).
- [ ] **Human signature + date.** This unblocks the F2 merge.

### If any check fails

Do **not** merge. The schema pin in `core/models.py` /
`core/migrations/0001_initial.py` is wrong for the real prod schema (most
likely a column the CSV-seeded sandbox clone never exercised, or a
prod-applied hotfix not in `backend/alembic`). File back to F2: re-introspect
prod, fix the model field / `db_column`, regenerate `0001_initial`, re-run §3.
There is no automated rollback (big-bang, user-accepted — see
`.plan/django-ninja-tasks.md` Failure modes); this gate is the safeguard.

---

## 4. Cleanup

```bash
dropdb bgx_prodclone
rm -f /tmp/bgx_prod_clone.dump /tmp/before_*.txt /tmp/after_*.txt \
      /tmp/migrate_*.txt
```
