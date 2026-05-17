# BGX Navigation Dashboard — Project Notes

Public read-only dashboard for the BGX Hard Enduro Championship (Bulgarian
motorcycle series). Shows per-season leaderboards, race results, rider
profiles, and a race calendar.

## Stack at a glance

| Layer | Tech | Lives in |
|---|---|---|
| Frontend | Astro 4 SSG + Tailwind, 0 KB JS baseline (unchanged) | `frontend/` |
| Backend (NEW) | Django 6 + Django Ninja 1.x + Pydantic v2 | `django_app/` |
| Backend (FROZEN oracle) | FastAPI 0.110 + Pydantic v2 + SQLAlchemy 2 | `backend/app/` |
| Data (NEW) | Postgres + Django migrations | `django_app/core/migrations/` |
| Data (FROZEN oracle) | Postgres + Alembic migrations | `backend/alembic/`, `backend/src/db/` |
| Services (domain) | Pure-Python computed leaderboards + rider profiles | `django_app/core/services/`, `backend/src/services/` |
| Deploy | Single Docker image, Railway | `Dockerfile.django` (new), `Dockerfile` (frozen), `railway.json` |

The refactor from FastHTML to FastAPI + Astro SSG was done across Phases 0–5.
Full history: `.plan/refactor-plan.md` and the three review files alongside it.

## Vocabulary (design-review.md §14)

- **Leaderboard** — the per-category table of riders sorted by points.
  Not "Standings" or "Ranking".
- **Race** / **Races** — a single event in the season calendar. Not "Event".
  (Note: the DB table is still called `event`; only the UI renames.)
- **Round** — numeric position in the calendar (R1, R2, …).
- **Points** — scores per placing. Abbreviation `Pts` in tight cells.
- **Hard Enduro** — the only event type surfaced in UI.
- **Rider** — not "Competitor" or "Pilot".

## Key architectural invariants

1. **Rider identity** = `(race_number, first_name, last_name)` per season.
   Race numbers alone are NOT unique — reused across categories and between
   people. Everywhere in the API, a rider is represented by `RiderRef`
   (`backend/app/schemas/common.py`) which includes the slug.
2. **Slug is computed server-side**. `backend/app/slug.py::rider_slug`
   produces `{first}-{last}-{race_number}`. The race_number is included on
   purpose: real-world rider names collide ("Иван ИВАНОВ" appears with 4
   distinct numbers in the dataset, almost certainly multiple people).
   Trade-off: a rider whose race_number changes between seasons fragments
   into separate `/rider/{slug}` URLs. Frontend never recomputes slugs —
   always consumes `RiderRef.slug` from the API.
3. **URL contract** (frontend-restructure.md). The public surface is now:
   - `/` — landing with single CTA → `/results`
   - `/results?season=&category=&race=` — single results page (Vue SPA island)
   - `/rider/{slug}` — multi-season profile, one page per slug (SSG)
   - `/stats` — auth-gated dashboard
   - `/api/*` — read-only JSON API
   Every legacy URL (`/{year}`, `/{year}/{cat}`, `/{year}/{cat}/{slug}`,
   `/{year}/events`, `/{year}/events/{slug}`, `/{year}/r/{n}/{slug}`) issues
   a 301 redirect to the new shape via `app/redirects.py`. Bookmarks + search
   indexed pages keep working; do NOT re-introduce per-year Astro pages.
4. **Mount order in `app.main`**: `/api/*` → `/health` → `/admin` →
   legacy redirect router → `/` StaticFiles. The redirect router MUST stay
   between admin and StaticFiles or `dist/{year}/{cat}/index.html` will
   shadow the 301. Tested by `tests/test_mount_order.py` and
   `tests/test_redirects.py`.
5. **Zero JS per page** is the Phase 2 baseline. Interactive features
   (filters, comparison, charts) are added as Vue islands only where needed.
6. **Standings are an archive, not a mirror** of the official championship
   scoring. Multi-day events sum cumulatively, no drop-worst rule, some races
   may be intentionally absent. Full policy: [`docs/scoring.md`](docs/scoring.md).

## Migration status: Django + Django Ninja rewrite (pre-cutover)

The FastAPI app in `backend/` is being replaced by a Django 6 + Django Ninja
app in `django_app/`. The new app is byte-parity-verified against the frozen
FastAPI oracle (slices F1–F3, X1–X4, S1–S7; I1 readiness verified). Until the
**I1 cutover**, `backend/` stays the deployable oracle + rollback target and is
**frozen — do NOT edit it**. New work happens in `django_app/`. The instructions
below give the Django commands first; the **frozen** FastAPI commands are kept
verbatim afterwards for the oracle/rollback path. See
[`django_app/README.md`](django_app/README.md) for the full layout and the env
mapping, and `.plan/MIGRATION_REHEARSAL.md` for the cutover runbook.

## Running locally (Django — the new app)

Two terminals:

```bash
# Postgres (seeded scratch DBs: bgx_django, bgx_oracle)
docker compose up -d postgres

# Terminal A — Django backend (ASGI; the prod process model)
cd django_app
DATABASE_URL=postgresql://bgx:bgx@localhost:5432/bgx_django \
  gunicorn config.asgi:application -k uvicorn.workers.UvicornWorker -b 127.0.0.1:5001
# (dev alt: DATABASE_URL=... python manage.py runserver 5001)

# Terminal B — frontend (unchanged)
cd frontend && npm install && npm run dev   # Astro on :4321, /api proxied to :5001
```

Migrate + seed once (local scratch DB only — NEVER prod):

```bash
cd django_app
DATABASE_URL=postgresql://bgx:bgx@localhost:5432/bgx_django python manage.py migrate
DATABASE_URL=postgresql://bgx:bgx@localhost:5432/bgx_django python manage.py seed_all
# (per-year importers also exist: seed_new, import_2025, import_race_day,
#  upsert_calendar, scoring_diff_2026, bootstrap_admin)
```

### Frozen FastAPI app (oracle / rollback only — do NOT edit `backend/`)

```bash
docker compose up -d postgres
cd backend && ./start.sh            # uvicorn on :5001 with --reload
# Seed once: cd backend && python -m scripts.import_2025
```

## Tests

Two-tier verification for the Django app (orchestrator decision B):

```bash
cd django_app
# Tier-1 — fast, no live DB, gates every slice (~268 passed / 5 skipped):
pytest -m "not parity"
# Tier-2 — needs the seeded Postgres, the hard I1 parity gate
#          (~114 passed / 1 xfailed):
DATABASE_URL=postgresql://bgx:bgx@localhost:5432/bgx_django pytest -m parity
```

Frozen FastAPI suite (oracle only): `cd backend && pytest`.

## Build the production image

```bash
# Django flavor (the new app — Stage 2 = manage.py migrate + gunicorn ASGI):
./scripts/build-image.sh bgx-dashboard:latest django   # -> Dockerfile.django
# Frozen FastAPI flavor (oracle / rollback; default if 2nd arg omitted):
./scripts/build-image.sh bgx-dashboard:latest          # -> Dockerfile
# Both probe localhost:5001/health, then run the multi-stage Docker build.
# Stage 1 (Astro SSG) is identical for both flavors.
```

## Review artifacts

- [`.plan/refactor-plan.md`](.plan/refactor-plan.md) — the plan + execution phases
- [`.plan/ceo-review.md`](.plan/ceo-review.md) — strategy/scope review (user challenges + expansions)
- [`.plan/design-review.md`](.plan/design-review.md) — the design source of truth (tokens, view anatomy, states matrix, vocabulary, microcopy, SEO, print, perf budgets)
- [`.plan/eng-review.md`](.plan/eng-review.md) — architecture, test matrix, security, hidden complexity

## Success metrics (post-launch)

Track M1–M7 per design-review.md §21 in `.plan/metrics.md`:
- M1 LCP, M2 bundle size, M3 organic sessions, M4 indexed pages,
- M5 visits/week, M6 mobile share, M7 time-to-ship-next-feature.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke context-save / context-restore
- Code quality, health check → invoke health
