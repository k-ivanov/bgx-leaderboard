# Deployment plan — BGX Navigation Dashboard

_Generated 2026-04-27._

End-to-end plan for taking the FastAPI + Astro app from a local laptop to
Railway, including how to seed production with the current local database
and how to re-import everything cleanly when needed.

This document supersedes the older legacy `DEPLOYMENT.md` (which targets
the FastHTML predecessor).

---

## What's being deployed

| Layer | Tech | Lives in |
|---|---|---|
| Frontend | Astro 4 SSG + Tailwind, ~500 pages | `frontend/` → `dist/` |
| Backend | FastAPI 0.110 + Pydantic v2 + SQLAlchemy 2 | `backend/app/` |
| Data | Postgres 16 + Alembic migrations (5 revisions through `0005_import_log`) | `backend/alembic/`, `backend/src/db/` |
| Runtime | Single Docker image — multi-stage build, FastAPI serves Astro `dist/` at `/` | `Dockerfile` |

Production target: **Railway**, Docker builder, single web service + a
Postgres plugin in the same project. `railway.json` is already configured.

---

## Owner intent

> Use the current local database data as seed for the production database.
> Have an easy way to re-import all of my local data into the production DB.

The plan implements both via two complementary mechanisms:

1. **Postgres dumps** (binary-faithful) — capture every table including
   visit analytics, import_log, and seasons exactly as they are locally,
   then push to prod. This is the **fastest path for first launch**.
2. **CSV-driven re-imports** (idempotent) — `make seed-new` walks
   `seed_data/<year>/*.csv`, hashes each file, skips anything in
   `import_log`, and incrementally imports the rest. This is the
   **everyday path for adding new race days** without touching prod
   schema or analytics.

Both paths are first-class. Pick the one that matches the situation.

---

## Architectural facts that constrain the plan

1. **Schema is owned by Alembic.** Production runs
   `alembic upgrade head` on every container start (see Dockerfile
   `CMD`). Any schema dump that fights this will get reverted on the
   next deploy.
2. **Slug is computed server-side.** Re-importing CSVs always recomputes
   the rider slug; never edit slugs in dumps.
3. **`import_log` uniqueness is `(filename, sha256)`.** A re-import only
   skips files that were imported with the *exact same content*. Edit a
   CSV, the new sha re-imports it.
4. **Visit rows are not part of championship data.** `seed-all`
   intentionally does NOT delete `visit` rows — they're independent
   analytics. A full prod backup is the only way to preserve them
   across a `seed-all`.
5. **Mount order in `app.main`** = `/api/*` → `/health` → `/admin` →
   legacy redirects → `StaticFiles`. Don't reorder; legacy redirects
   must intercept `/{year}/...` before StaticFiles serves.

---

## Pre-flight (one-time)

### 1. Railway project + Postgres

```bash
npm i -g @railway/cli         # one-time on your laptop
railway login
cd ~/Work/bgx-navigation-dashboard
railway link                  # link to an existing project, or:
railway init                  # create a new one
```

In the Railway dashboard, add the **Postgres** plugin to the project. It
auto-injects `DATABASE_URL` into the web service. No other config needed
— the FastAPI app normalizes `postgres://` → `postgresql+psycopg2://`
internally on startup (`backend/src/db/session.py`).

### 2. Required env vars on the web service

| Var | Value | Why |
|---|---|---|
| `DATABASE_URL` | injected by the Postgres plugin | Postgres connection. |
| `STATS_PASSWORD` | strong random | Gates `/api/stats`, `/api/docs`, `/api/openapi.json`, and `/stats` page. **Set this — without it, dev defaults expose internals.** |
| `ADMIN_PASSWORD` | strong random | Gates `/admin` SQLAdmin panel. Same caveat. |
| `DEFAULT_SEASON_YEAR` | `2026` | Fallback only when no Season rows exist. Won't be used post-seed. |

Set them via `railway variables set KEY=value` or the dashboard.

### 3. Local image build sanity check

The frontend build (Stage 1 of the Dockerfile) calls the FastAPI at
`getStaticPaths` time to enumerate `/rider/{slug}` paths. Local backend
must be running:

```bash
make db-up                      # postgres
cd backend && ./start.sh        # uvicorn :5001
# in another shell:
make build                      # → bgx-dashboard:latest, ~9 sec frontend + Docker
make run                        # boot the prod image against local Postgres
make health                     # GET /health → {"status":"ok",...}
make smoke                      # hits /, /results, /api/seasons, /rider/{slug}
```

If the smoke pass goes green, the same image will work on Railway.

---

## Path A — seed prod from local Postgres (one-shot bootstrap)

Use this for the initial launch. Mirrors the local DB byte-for-byte
(seasons, categories, events, riders, results, import_log, **and**
visits). After this you'll usually switch to Path B for incremental
imports.

```bash
# 1. Snapshot local DB.
make db-dump
# → db_dumps/local-20260427-093307Z.sql.gz   (64 KB compressed)

# 2. First Railway deploy (creates schema via alembic upgrade head).
railway up
# Wait until /health is 200 — alembic ran, no data yet.

# 3. Restore the snapshot into prod. This DROPs and recreates every
#    table in the dump (SCHEMA + DATA), so you don't need to worry
#    about migrations re-running cleanly afterwards.
PROD_DATABASE_URL="$(railway variables -s postgres --kv | grep DATABASE_URL | cut -d= -f2-)" \
  ./scripts/db-restore.sh prod db_dumps/local-20260427-093307Z.sql.gz --yes
```

**Caveats:**
- Production schema must match the dump's schema. Since both ran the
  same Alembic revisions, this holds — but if you bumped a revision
  since the dump, run `railway run alembic upgrade head` after the
  restore to roll forward.
- Visit rows in the dump carry your local visitor_ids (hashes derived
  from your laptop IP + UA). Harmless but they show up in the stats
  page.
- The dump uses `--clean --if-exists`, so re-running this command is
  safe: it wipes prod tables and rewrites them. For a routine refresh
  after fixing a CSV, prefer Path B + `make db-seed-prod` instead.

---

## Path B — push only data changes (everyday flow)

Use this once prod has a schema. Schema lives on Alembic; only data
moves. This avoids fighting `alembic upgrade head` and is what you'll
run after importing a new race day locally.

```bash
# 1. Import locally first. seed-new is idempotent (skip if you've
#    already imported this CSV).
make seed-new YEAR=2026

# 2. Verify locally.
curl -s http://127.0.0.1:5001/api/seasons/2026 | jq '.events | length'

# 3. Dump just the data.
make db-dump ARGS="--data-only"
# → db_dumps/local-20260427-094505Z.sql.gz  (~30 KB)

# 4. Push to prod. This streams the data-only dump through psql with
#    --disable-triggers so foreign keys don't fight insert order.
PROD_DATABASE_URL="$(railway variables -s postgres --kv | grep DATABASE_URL | cut -d= -f2-)" \
  make db-seed-prod FILE=db_dumps/local-20260427-094505Z.sql.gz
```

**`make db-seed-prod` is gated** — it shows the target host (with the
password redacted) and asks for confirmation before writing. Hit Enter
to proceed, Ctrl-C to abort.

**Caveat:** `--data-only` does not delete prod rows that aren't in your
local dump. If you removed a stray Rider locally, prod will keep the
old row. For a clean reset use Path A or run
`railway run python -m scripts.seed_all` (wipes prod championship
tables, preserves visits).

---

## Path C — re-import from CSVs directly on prod

If you don't want to go through your local DB at all (e.g. CI ran the
seed and you want to apply on prod), the importer scripts work directly
against any `DATABASE_URL`:

```bash
# Idempotent — only loads CSVs not already in import_log.
railway run python -m scripts.seed_new --year 2026

# Wipe + reload one year (keeps visits + import_log fresh):
railway run python -m scripts.seed_all --year 2026
```

`seed_data/` is **not** copied into the Docker image (intentionally —
keeps the image small). `railway run` executes the command against the
prod env from your laptop, so it picks up your local `seed_data/`. If
you need to run this from CI without local CSVs, mount or upload them
explicitly.

---

## The dump tooling (`scripts/db-dump.sh`, `scripts/db-restore.sh`)

Both scripts emit/consume gzipped pg_dump SQL into `./db_dumps/`. The
folder is gitignored (`.gitignore` line 50) so dumps and prod
credentials never end up in commits.

### Dump

```bash
./scripts/db-dump.sh local                       # full local dump
./scripts/db-dump.sh local --data-only           # data only (skip DDL)
./scripts/db-dump.sh local --schema-only         # DDL only — sanity-check
./scripts/db-dump.sh prod                        # uses PROD_DATABASE_URL
./scripts/db-dump.sh prod --tag pre-migration    # custom suffix
./scripts/db-dump.sh url postgres://...          # arbitrary target
```

Makefile shortcuts:

```bash
make db-dump                                     # local
make db-dump ARGS="--data-only"                  # local data-only
make db-dump-prod                                # prod
make db-dump-prod ARGS="--tag nightly"           # prod with tag
```

The script uses `docker run --rm postgres:16-alpine pg_dump …` for
non-local URLs, so the host doesn't need a matching pg_dump installed.
For local it execs into the existing `bgx-postgres` container.

### Restore

```bash
./scripts/db-restore.sh local <file>             # restore into local DB
./scripts/db-restore.sh prod  <file> --yes       # restore into prod (gated)
./scripts/db-restore.sh url <URL> <file> --yes   # arbitrary target
```

Production restores require an explicit `--yes` flag and `--data-only`
restores are first-class (use them when prod has the schema and you
just want fresh data).

```bash
make db-restore FILE=db_dumps/local-….sql.gz                          # local restore
make db-seed-prod FILE=db_dumps/local-data-….sql.gz                   # prod data refresh (interactive confirm)
```

### Output naming

`db_dumps/<mode>[-<tag>]-<UTC-timestamp>.sql.gz`

- `local-20260427-093253Z.sql.gz`
- `prod-pre-migration-20260427-103015Z.sql.gz`
- `prod-data-20260427-094505Z.sql.gz`

UTC timestamps so dumps sort chronologically across timezones.

---

## Routine deploy flow (after the first launch)

| Step | Command | Notes |
|---|---|---|
| 1 | `make test` | 99 backend tests |
| 2 | `make check-frontend` | `astro check` — type-check across pages + components |
| 3 | `make build` | Multi-stage docker build — needs local backend on :5001 |
| 4 | `make smoke` | `/health`, `/api/seasons`, `/`, `/results`, `/rider/{slug}` |
| 5 | `git push origin <branch>` | If using Railway GitHub integration |
| 6 | `railway up` | Or auto-deployed by step 5 |
| 7 | `curl https://<app>.up.railway.app/health` | Confirm prod is alive |
| 8 | _(if data changed)_ Path B | Push the new data dump |

The image runs `alembic upgrade head` on boot, so schema migrations
land automatically. Data does not — that's deliberate. You decide when
prod gets new race results.

---

## Backups & rollback

A nightly backup is two lines in your shell history:

```bash
# Manual backup before a risky change:
make db-dump-prod ARGS="--tag pre-migration"
# Roll back if needed:
make db-seed-prod FILE=db_dumps/prod-pre-migration-….sql.gz
```

Railway also runs Postgres backups on the platform; `make db-dump-prod`
is the **portable** copy you keep on your laptop in case Railway is
unreachable.

For automated daily backups, add a small GitHub Actions workflow that
runs `./scripts/db-dump.sh prod` and uploads the artifact. (Out of
scope for this plan — the manual flow is sufficient until traffic
warrants automation.)

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pg_dump: error: connection to server failed` (local mode) | `bgx-postgres` container not running | `make db-up` |
| `pg_dump: error: permission denied for schema public` (prod) | Railway's user lacks superuser | Stay on `--data-only`; full restores require recreating tables |
| `relation "season" already exists` during full restore | Target DB had data; the dump's `--clean --if-exists` couldn't drop because of FK references | Restore in a transaction or run `railway run python -m scripts.seed_all` instead |
| `[db-dump] PROD_DATABASE_URL is unset` | Railway CLI not linked or not installed | Pass `PROD_DATABASE_URL=…` directly, OR `npm i -g @railway/cli && railway link` |
| Restore writes 0 rows but no error | `--data-only` dump applied to a DB whose schema doesn't match | Check `alembic current` on both sides — bump the lagging one |
| `make db-seed-prod` blocks waiting | The interactive confirm needs Enter | Run from a real TTY, or use `./scripts/db-restore.sh prod <file> --yes --data-only` non-interactively |

---

## File index

| File | Role |
|---|---|
| `scripts/db-dump.sh` | The dump runner. Three modes: `local`, `prod`, `url`. |
| `scripts/db-restore.sh` | The restore runner. Same three modes. Gated for prod. |
| `Makefile` | Targets `db-dump`, `db-dump-prod`, `db-restore`, `db-seed-prod`. |
| `.gitignore` | Adds `db_dumps/` so dumps + prod creds never get committed. |
| `Dockerfile` | Multi-stage build; CMD runs `alembic upgrade head`. |
| `railway.json` | Tells Railway to use the Dockerfile builder. |
| `backend/scripts/seed_all.py` | Wipes championship data + reimports every CSV. Keeps visits. |
| `backend/scripts/seed_new.py` | Idempotent — only imports CSVs not in `import_log`. |
| `backend/scripts/import_race_day.py` | Single-CSV importer (called by both seeders). |
| `seed_data/<year>/*.csv` | Source-of-truth race results. Filename sha256 keyed in `import_log`. |
