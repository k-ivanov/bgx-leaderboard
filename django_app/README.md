# django_app — Django 6 + Django Ninja rewrite (F1 scaffold)

This is the **side-by-side** new backend created by task **F1** of the Django
rewrite (`.plan/django-ninja-tasks.md`). It lives in a new top-level path; the
existing `backend/` (FastAPI) tree is **frozen and untouched** — it stays the
deployable parity oracle until the I1 cutover (decision I3-arch=A). Nothing
under `backend/` or `frontend/` was modified by F1.

## Directory layout & why

```
django_app/
├── manage.py            # entrypoint; adds package root to sys.path
├── pyproject.toml       # SEPARATE dep set (does not touch backend/pyproject.toml)
│                         # + pytest-django config
├── conftest.py          # F1 harness bootstrap (no-PG fallback for the scaffold)
├── config/              # project config — settings, FROZEN urls, asgi/wsgi
│   ├── settings.py      # ports EVERY env var from the FastAPI app (mapping below)
│   ├── urls.py          # ⚠ FROZEN BY F1 — load-bearing resolution order
│   ├── asgi.py          # prod entrypoint (gunicorn + uvicorn worker)
│   └── wsgi.py
├── api/                 # Django Ninja layer
│   ├── __init__.py      # ⚠ FROZEN BY F1 — the single NinjaAPI + all router slots
│   ├── seasons.py       # S1  ┐
│   ├── standings.py     # S2  │ each slice agent fills ONLY its own
│   ├── events.py        # S3  │ api/<domain>.py module — empty Router()
│   ├── results.py       # S7  │ placeholders in F1
│   ├── riders.py        # S4  │ (router + career_router)
│   ├── stats.py         # S5  │
│   ├── track.py         # S6  ┘
│   ├── docs.py          # X2 gated-docs slot placeholder
│   └── schemas/         # F3 fills shared Ninja Schemas (RiderRef, …)
├── core/                # the `core` Django app
│   ├── models.py        # F2 fills (8 tables, db_table-pinned, fake-initial)
│   ├── admin.py         # X3 fills
│   ├── migrations/      # F2 generates 0001_initial
│   └── management/commands/   # X4 fills (ported importers)
├── redirects/           # X1 fills (legacy 301s + static catch-all)
└── tests/               # F1 scaffold smoke tests; F3 brings the parity rig
```

**Why this layout:** `config/` (settings + the *frozen* URLconf), `core/` (one
Django app for the ORM models + admin + importers), and `api/` (the Ninja
routers) are three flat, single-responsibility packages. Every parallel slice
owns exactly one module under `api/`, `redirects/`, `core/admin.py`, or
`core/management/` — no two slices write the same file, and **no slice touches
the two FROZEN files** (`config/urls.py`, `api/__init__.py`). This is the
shared-write-hotspot elimination from decision I1-arch=A.

## ⚠ FROZEN files (do not edit in any slice task)

- `api/__init__.py` — the single `NinjaAPI` instance + the full router
  assembly. Every S1–S7 slot is pre-stubbed as an empty `ninja.Router`.
- `config/urls.py` — the root URLconf, written once in the **load-bearing
  order**: `/api/*` → `/health` → `/admin/` → legacy 301s → catch-all static.
  Mis-ordering = static shadows the API/redirects (CLAUDE.md invariant #4 /
  total-outage failure mode). `APPEND_SLASH = False` is part of the contract.

Slice agents fill only their own module; the router objects are imported by
reference, so replacing the empty `Router()` body is all that's needed.

## OLD → DJANGO env-var / setting mapping

Source of truth ported: `backend/app/config.py` + `backend/src/config.py`
(plus the two process-level vars the Dockerfile/start.sh use). The same env
vars are read with the same names + defaults.

| Old (env var / constant) | Old location | Django setting | Notes |
|---|---|---|---|
| `DATABASE_URL` | src/config.py | `DATABASES['default']` | Same var. Required (same error message when unset). SQLAlchemy `+psycopg2` suffix **stripped** (Django uses psycopg3). Railway bare `postgres://` accepted. |
| `DEFAULT_SEASON_YEAR` (2026) | src/config.py | `DEFAULT_SEASON_YEAR` | Same var/default, int. |
| `APP_VERSION` ("0.1.0") | src/config.py constant | `APP_VERSION` | Ported constant; drives `/health`. |
| `STATS_PASSWORD` ("") | app/config.py | `STATS_PASSWORD` | Same var/default. S5/X2. |
| `ADMIN_USERNAME` ("admin") | app/config.py | `ADMIN_USERNAME` | Same var/default. X3. |
| `ADMIN_PASSWORD` ("") | app/config.py | `ADMIN_PASSWORD` | Same var/default. Empty = admin disabled. X3. |
| `ADMIN_SESSION_SECRET` | app/config.py | `SECRET_KEY` + `ADMIN_SESSION_SECRET` | Same var. Drives Django `SECRET_KEY` (native session signing) and kept verbatim for X3. Same dev-only fallback literal. |
| `FRONTEND_DIST` | app/main.py | `FRONTEND_DIST` | Same var. X1 static catch-all uses it. |
| `PORT` (5001) | Dockerfile/start.sh | `SERVER_PORT` | Process-level; gunicorn binds it. |
| `HOST` (0.0.0.0) | Dockerfile/start.sh | `SERVER_HOST` | Process-level; gunicorn binds it. |
| `TRACK_MAX_BYTES` (2048) | app/config.py constant | `TRACK_MAX_BYTES` | Ported. S6. |
| `TRACK_RATE_LIMIT` ("10/minute") | app/config.py constant | `TRACK_RATE_LIMIT` | Ported. S6 throttling. |
| *(new)* `DJANGO_SECRET_KEY` | — | `SECRET_KEY` override | Optional dedicated Django secret; falls back to `ADMIN_SESSION_SECRET`. |
| *(new)* `DJANGO_DEBUG` | — | `DEBUG` | Defaults False (old app had no debug). |
| *(new)* `DJANGO_ALLOWED_HOSTS` | — | `ALLOWED_HOSTS` | Django host validation (no FastAPI equiv). Scaffold default `*`; X2 hardens for Railway. |

The three `DJANGO_*` vars are Django-only requirements with no FastAPI
equivalent; they default to safe values so the scaffold boots. Security
headers / CSP / proxy-TLS are deliberately **out of F1 scope** (task X2).

## Running locally

```bash
# 1. Postgres (same one the old app uses)
docker compose up -d postgres
export DATABASE_URL=postgresql://bgx:bgx@localhost:5432/bgx

# 2. Install the (separate) Django deps
cd django_app
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"

# 3. Boot
python manage.py runserver 0.0.0.0:5001
curl -s localhost:5001/health
# -> {"status": "ok", "service": "bgx-dashboard-api", "version": "0.1.0"}
```

Without Postgres, `DJANGO_ALLOW_NO_DB=1 python manage.py runserver` boots on
an in-memory SQLite DB (scaffold smoke only — F2 brings the real schema).

## Running the OLD app (parity oracle, unchanged)

The frozen FastAPI app is still the spec. One command to run it for diffing:

```bash
cd backend && ./start.sh        # uvicorn on :5001 (unchanged)
# or: docker compose up -d postgres && (cd backend && uvicorn app.main:app --port 5001)
```

## Tests

```bash
cd django_app && pytest          # F1 scaffold smoke tests (4); exits 0.
```

F3 replaces/extends this with the 2025 golden fixtures + the old↔new
`assert_json_parity` rig. F1 only proves the harness runs.

## Container

`Dockerfile.django` (parallel to the unchanged `./Dockerfile`):

```bash
./scripts/build-image.sh bgx-dashboard:django-f1 django
# Stage 1 = Astro (identical to the FastAPI image).
# Stage 2 = `manage.py migrate --noinput` then gunicorn -k uvicorn.workers.UvicornWorker.
docker run --rm -p 5001:5001 -e DATABASE_URL=postgresql://bgx:bgx@host.docker.internal:5432/bgx bgx-dashboard:django-f1
```

Gunicorn is retained with a uvicorn ASGI worker (decision OV2=B). The original
`./Dockerfile` and the default `build-image.sh` invocation are byte-unchanged.
