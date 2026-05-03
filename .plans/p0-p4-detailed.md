# P0–P4 detailed working plan

_Generated 2026-04-25. Companion to `.plans/improvements.md` (which scopes P0–P6 at a higher level)._

This file is the **execution playbook**: every item gets a problem statement, a concrete design, the files that change, and the commit message. Items are listed in execution order. Each item below maps 1:1 to a commit on `refactor/fastapi-vue`.

## Pre-decisions (from owner)

These shape every item. Confirmed before execution started:

- **Scoring rule = current behavior, documented**. Do NOT switch to day-1-only, do NOT add drop-worst, do NOT import Six Days. Document that we are an archive.
- **Ops items skipped**: alerting (P1 #8), backup (P1 #10), deploy gate (P1 #7) are deferred. Only CSP headers (P1 #11) — which is code-only — ships.
- **Heavy P3**: only search (#16) and multi-season profile (#17). Compare riders (#18), OG image generator (#21), exports (#20), mobile-table redesign (#19), filter (#22), token audit (#23), theme sync (#24) are deferred.
- **Workflow**: commit per sub-item; push after each commit; pytest must pass before any backend commit (after P0 #1 fixes the suite); destination branch is `refactor/fastapi-vue`.

## Execution order at a glance

| # | Item | Tier | Effort | Commit subject |
|---|---|---|---|---|
| 1 | Fix pytest collection | P0 | S | `fix(deps): add sqladmin to backend deps so pytest collects` |
| 2 | `make seed-new` (covers P4 #26 too) | P0 | S | `feat(make): seed-new imports any unimported seed_data CSV` |
| 3 | Document scoring scope | P0 | S | `docs(scoring): explain multi-day-sum archive behavior` |
| 4 | Rider name parser hardening | P0 | S | `fix(import): reject HH:MM:SS tokens in rider name field` |
| 5 | Sitemap generator | P0 | S | `feat(seo): post-build sitemap-index generator` |
| 6 | GitHub Actions CI | P1 | M | `chore(ci): add GitHub Actions for pytest + build + typecheck` |
| 7 | Stats auto-refresh | P1 | S | `feat(stats): auto-refresh dashboard every 60s + last-updated` |
| 8 | CSP + security headers | P1 | S | `feat(security): add CSP/HSTS/X-Frame-Options middleware` |
| 9 | Document multi-day scoring | P2 | S | `docs(standings): inline note on multi-day point totals` |
| 10 | Document no drop-worst | P2 | S | `docs(standings): note that per_event format keeps every race` |
| 11 | Tiebreaker docs + test | P2 | S | `feat(standings): document tiebreaker rule + pin with unit test` |
| 12 | Rider search | P3 | M | `feat(search): GET /api/seasons/{y}/riders/search + nav island` |
| 13 | Multi-season rider profile | P3 | M | `feat(rider): career view aggregating across seasons` |
| 14 | README sync | P4 | S | `docs(readme): align with FastAPI+Astro stack post-refactor` |
| 15 | OpenAPI docs in dev | P4 | S | `feat(devx): mount /docs and /openapi.json when ENV=dev` |
| 16 | Types pipeline check | P4 | S | `chore(types): add make types target with drift check` |

15 commits total (P0 #2 absorbs P4 #26).

---

## P0 — Bugs / regressions

### P0 #1 — ~~Fix pytest collection~~ — **FALSE ALARM, no commit**

**Status.** `sqladmin>=0.19` is already in `backend/pyproject.toml` and installed in the venv (0.25.0). All 63 tests collect and pass cleanly when pytest is run from the right cwd. The "4 collection errors" reported in `.plans/improvements.md` came from a stale shell session where `cd` had been lost. Verified: `cd backend && .venv/bin/pytest -q` → `63 passed`.

No code change needed.

---

### P0 #2 — `make seed-new` (also covers P4 #26)

**Problem.** A new CSV in `seed_data/` does not flow into the DB until somebody manually runs the importer. We hit this with `seed_data/2026/hard_enduro_buhovo_2026-day1.csv` — page 404'd until manual import. Also: `seed_all` does a full wipe, which is overkill and dangerous on a dev DB with bookmarks.

**Design.**
- New `Makefile` target `seed-new`: shells out to a new helper `backend/scripts/seed_new.py`.
- The helper:
    1. Walks `seed_data/**/*.csv`.
    2. For each CSV, derives a stable source identifier (filename + size + mtime hash) and checks against a new `import_log` table (id, source_filename, mtime, sha256, imported_at).
    3. For files not yet logged, calls `import_race_day` then writes the log row.
- New alembic migration `0005_import_log.py` for the table.
- Idempotent: re-running with no new files prints `nothing to import`.

**Files.**
- `Makefile` — `seed-new` target.
- `backend/scripts/seed_new.py` — new helper.
- `backend/alembic/versions/0005_import_log.py` — schema.
- `backend/src/db/models.py` — `ImportLog` model.

**Commit.** `feat(make): seed-new imports any unimported seed_data CSV (incremental, safe)`

---

### P0 #3 — Document scoring scope

**Problem.** Newcomers (and anyone reading the validation report) will wonder why our standings differ from hardendurobulgaria.com. The decision is made (we keep multi-day sums, we omit Six Days, we don't drop the worst race) but not written down.

**Design.** A new top-level `docs/scoring.md` plus a one-paragraph link from `README.md` and `CLAUDE.md`. Cross-links to the validation report.

**Files.**
- `docs/scoring.md` — new.
- `README.md` — link.
- `CLAUDE.md` — link.

**Commit.** `docs(scoring): explain multi-day-sum archive behavior + Six Days omission`

---

### P0 #4 — Rider name parser hardening

**Problem.** The validation report flagged `"Георги ГЕОРГИЕВ 3:34:40.7"` as a rider name in our DB — the importer accepted a row where the `rider_name` column actually contained a name plus a stray time string from a malformed CSV cell.

**Design.** In `backend/scripts/import_race_day._split_name`, if the trailing token matches `\d+:\d{2}:\d{2}(\.\d+)?`, log a warning and strip it from the name. Add a test case in `backend/tests/test_import.py` (new file) feeding the offending row.

**Files.**
- `backend/scripts/import_race_day.py` — `_split_name` defensive check.
- `backend/tests/test_import.py` — new test module.

**Commit.** `fix(import): reject HH:MM:SS tokens in rider name field`

---

### P0 #5 — Sitemap generator

**Problem.** `frontend/public/robots.txt` references `/sitemap-index.xml` but no such file is generated. Search engines hitting that URL get a 404.

**Design.**
- New `frontend/scripts/build-sitemap.mjs` that walks `dist/` after build, collects every `index.html` path, emits `dist/sitemap.xml` with `<url><loc>` entries plus `lastmod` from the file mtime.
- For >10k URLs: emit a `sitemap-index.xml` referencing per-50k-URL chunks. We have ~1600 routes so a single sitemap suffices, but the index keeps the path stable.
- Wire into `package.json`: `"build": "astro build && node scripts/build-sitemap.mjs"`.

**Files.**
- `frontend/scripts/build-sitemap.mjs` — new.
- `frontend/package.json` — `build` script.

**Commit.** `feat(seo): post-build sitemap-index generator`

---

## P1 — Production readiness (code-only items)

### P1 #6 — GitHub Actions CI

**Problem.** No `.github/`. Every regression caught by hand. Backend test suite has been silently broken (P0 #1).

**Design.** `.github/workflows/ci.yml` with two jobs:
- `backend`: ubuntu-latest, sets up Python 3.12, services Postgres 15, `pip install -e backend[dev]`, `alembic upgrade head`, `pytest`.
- `frontend`: ubuntu-latest, Node 20, `npm ci`, `npm run build`, `npm run typecheck` (if it exists; otherwise `tsc --noEmit`).
Triggered on push to `refactor/fastapi-vue` and `main`, and on every PR.

**Files.**
- `.github/workflows/ci.yml` — new.

**Commit.** `chore(ci): add GitHub Actions for pytest + frontend build + typecheck`

---

### P1 #9 — Stats auto-refresh

**Problem.** The stats island fetches once on mount; staying on the page shows stale numbers.

**Design.**
- Add a `setInterval(load, 60_000)` on mount; clear on unmount.
- Display "Updated HH:MM:SS" in small text in the header.
- If a fetch returns 401 (server restarted, sessionStorage stale), drop creds and show login form.

**Files.**
- `frontend/src/components/StatsView.vue` — interval logic + timestamp.
- `frontend/src/lib/copy.ts` — `lastUpdated` label.

**Commit.** `feat(stats): auto-refresh dashboard every 60s + last-updated indicator`

---

### P1 #11 — CSP + security headers

**Problem.** No `Content-Security-Policy`, no `Strict-Transport-Security`, no `X-Frame-Options`, no `Referrer-Policy`. Inline scripts in BaseLayout (theme init, tracking, define:vars JSON) constrain how strict CSP can be — they need either `'unsafe-inline'`, nonces, or hashes.

**Design.**
- New `backend/app/security_headers.py` — Starlette middleware.
- Headers added on every response from FastAPI (which serves `/api/*`, `/health`, AND `/` static files since it mounts `StaticFiles`):
    - `Strict-Transport-Security: max-age=63072000; includeSubDomains` (only when request scheme is https).
    - `X-Frame-Options: DENY`.
    - `Referrer-Policy: strict-origin-when-cross-origin`.
    - `X-Content-Type-Options: nosniff`.
    - `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; font-src 'self' data:; frame-ancestors 'none'; base-uri 'self'`.
- `'unsafe-inline'` for `script-src` is necessary because of the `is:inline` scripts. Nonces would require dynamic HTML rendering, which conflicts with SSG. We accept this tradeoff.
- Wire into `app.main.create_app` after the existing middleware chain.

**Files.**
- `backend/app/security_headers.py` — new middleware.
- `backend/app/main.py` — register middleware.
- `backend/tests/test_security_headers.py` — new tests asserting headers present.

**Commit.** `feat(security): add CSP, HSTS, X-Frame-Options, Referrer-Policy middleware`

---

## P2 — Data correctness (per stakeholder = mostly docs)

### P2 #12 — Document multi-day scoring

**Problem.** `services/standings.py` has no docstring explaining the per-day sum. Future maintainers won't know whether it's by design or a bug.

**Design.** Module-level docstring explaining: every (rider, event_id) pair sums all `EventResult.day` rows for that pair. Refer to `docs/scoring.md` and `.reports/2025-validation-vs-hardendurobulgaria.md`.

**Files.**
- `backend/src/services/standings.py` — docstring.

**Commit.** `docs(standings): inline note on multi-day point totals (archive behavior)`

---

### P2 #13 — Document no drop-worst

**Problem.** Same as above — the `championship_format='per_event'` enum doesn't drop the worst race. No code comment documents this is intentional.

**Design.** Docstring on the `Season.championship_format` field listing the supported values and what each does. Currently only `per_event` exists.

**Files.**
- `backend/src/db/models.py` — `Season.championship_format` docstring.

**Commit.** `docs(models): clarify per_event championship_format keeps every race`

---

### P2 #14 — Tiebreaker docs + test

**Problem.** Two riders with the same total points are ordered by `id` today (incidental). Tiebreaker rule is undocumented.

**Design.**
- Document the tiebreaker chain in `services/standings.py`:
    1. higher total points
    2. more wins (positions == 1)
    3. then more podiums (positions ≤ 3)
    4. then better best result
    5. then race number ascending
- Implement (some of these may already happen by accident; codify them as an explicit `sort key`).
- Add `backend/tests/test_standings_tiebreakers.py` with synthetic season data.

**Files.**
- `backend/src/services/standings.py` — sort key.
- `backend/tests/test_standings_tiebreakers.py` — new.

**Commit.** `feat(standings): document tiebreaker rule + pin with unit test`

---

## P3 — Frontend UX (narrowed to #16 + #17)

### P3 #16 — Rider search

**Problem.** Visitors who know a rider's name (but not their race number) have to scroll the leaderboard. There's no search affordance anywhere on the site.

**Design.**

Backend:
- `GET /api/seasons/{year}/riders/search?q=<query>&limit=10`
- Case-insensitive substring match on `first_name`, `last_name`, and `race_number`.
- Returns `[{rider: RiderRef, category: CategoryRef, season_year: int}]`.

Frontend (Vue island in nav):
- Input box added to `Nav.astro` between year switcher and section links.
- Vue island `RiderSearch.vue`:
    - Debounced fetch on input (300ms).
    - Dropdown overlay with up to 10 results.
    - Arrow-key navigation, Enter to navigate, Esc to close.
    - Click → navigate to rider page.
- Search uses the year currently in the URL (or current season if at root).

**Files.**
- `backend/app/api/riders.py` — search endpoint.
- `backend/app/schemas/riders.py` — `RiderSearchResultOut`.
- `backend/tests/test_riders.py` — search tests.
- `frontend/src/components/RiderSearch.vue` — new island.
- `frontend/src/components/layout/Nav.astro` — mount island.
- `frontend/src/lib/api.ts` — `searchRiders(year, q)`.
- `frontend/src/lib/copy.ts` — placeholder, no-results text.

**Commit.** `feat(search): rider search island in nav + /api/seasons/{y}/riders/search endpoint`

---

### P3 #17 — Multi-season rider profile

**Problem.** Once you're on a rider page (`/2025/r/255/димитър-тинчев`), you only see that season. The rider may have raced in 2024 and 2026 too — that history is invisible.

**Design.**

Backend:
- `GET /api/riders/career/{name_slug}` where `name_slug = "<race_number>-<rider-slug>"` (same shape we already use elsewhere).
- Aggregates across every `Rider` row that matches the slug across all seasons:
    1. Identify candidates by `(slug)` — the slug already encodes name+number.
    2. For each candidate, sum total points + count races + best position.
    3. Order seasons descending.
- Returns `[{season_year, total_points, best_position, races, category, team, bike}]`.
- Edge: same person racing under different numbers across seasons is NOT joined (we have no canonical identity beyond slug).

Frontend:
- New section "Кариера" (Career) added to `[year]/r/[raceNumber]/[slug].astro`.
- Renders a table of `season_year | category | races | best_position | total_points` with a link to each season's standings.
- Empty state if only one season exists.

**Files.**
- `backend/app/api/riders.py` — career endpoint.
- `backend/app/schemas/riders.py` — `RiderCareerOut`.
- `backend/tests/test_riders.py` — career tests.
- `frontend/src/lib/api.ts` — `getRiderCareer(slug)`.
- `frontend/src/pages/[year]/r/[raceNumber]/[slug].astro` — career section.
- `frontend/src/lib/copy.ts` — section heading + column labels.

**Commit.** `feat(rider): career view aggregating results across seasons`

---

## P4 — Developer experience

### P4 #25 — README sync

**Problem.** The current `README.md` predates the FastAPI + Astro refactor. It may still mention FastHTML, old endpoints, or stale paths.

**Design.** Read `README.md`, compare against `CLAUDE.md` (the source of truth), update sections: stack table, quickstart commands, test count, deployment notes, link to `.plans/` and `.reports/`.

**Files.**
- `README.md`.

**Commit.** `docs(readme): align with FastAPI+Astro stack post-refactor`

---

### P4 #27 — OpenAPI docs in dev

**Problem.** `/docs`, `/redoc`, `/openapi.json` all return 404 in this build (intentionally hidden in prod). But local development is harder without the Swagger UI.

**Design.**
- Default `docs_url=None, redoc_url=None, openapi_url=None` on `FastAPI()`.
- When `ENV=dev` (or `STATS_PASSWORD` is set so the `/docs` route can be auth-gated), enable them.
- Wrap `/docs`, `/openapi.json` behind `Depends(require_stats_auth)` even in dev — same gate as the stats dashboard. That way the same `letmein` works.

**Files.**
- `backend/app/main.py` — conditional docs URLs + auth.
- `backend/app/config.py` — `ENV` env var.
- `backend/.env.example` — document `ENV=dev`.

**Commit.** `feat(devx): enable Swagger docs in dev (gated by stats auth)`

---

### P4 #29 — Types pipeline check

**Problem.** `frontend/src/lib/api.openapi.ts` is generated from the backend's OpenAPI schema, but the regen command (`npm run generate:api-types`) only runs by hand. Easy to ship out-of-sync types.

**Design.**
- Add `make types` target that:
    1. Starts the backend on a temp port (or assumes one is running).
    2. Runs `npm run generate:api-types` in the frontend.
    3. Runs `git diff --exit-code frontend/src/lib/api.openapi.ts`.
    4. Exits non-zero if drift detected.
- Document in README under "Developer workflow".
- Also add to CI (P1 #6).

**Files.**
- `Makefile` — `types` target.
- `README.md` — workflow note.
- `.github/workflows/ci.yml` — add as a step (modify the file from P1 #6).

**Commit.** `chore(types): make types target with drift check + CI integration`

---

## Items deferred (not committed)

Skipped per pre-decisions, with rationale:

| Item | Why deferred |
|---|---|
| P1 #7 deploy gate | Railway-specific; needs hands-on platform access. |
| P1 #8 alerting | Needs destination service decision (Sentry/Logtail/Honeycomb). |
| P1 #10 backup | Needs S3 bucket / Railway volume decision. |
| P2 #15 categories denorm | Schema-level refactor; only worth it at 4+ seasons. |
| P3 #18 compare riders | Not in the MVP scope per owner. |
| P3 #19 mobile tables | Not in the MVP scope per owner. |
| P3 #20 export CSV | Not in the MVP scope per owner. |
| P3 #21 OG generator | Needs Pillow/Playwright; heavy add. |
| P3 #22 stats filter | Not in the MVP scope per owner. |
| P3 #23 token audit | Cosmetic; defer. |
| P3 #24 theme sync | Requires user accounts; out of scope. |
| P4 #28 Storybook | Component count low; revisit at ~15+ components. |

These can be picked up in a future iteration. The roadmap in `.plans/improvements.md` carries them.

---

## Verification per commit

**Backend commits.**
```bash
cd backend && .venv/bin/pytest -x -q
```
Must pass before commit.

**Frontend commits.**
```bash
cd frontend && npm run build
```
Must succeed (1599+ pages built).

**Combined.**
After every push, the running dev backend (uvicorn `--reload`) and Astro dev server should auto-pick up changes. Manual smoke-test by hitting the affected URL once.

---

## Stop conditions

If any of the following happens, I stop and surface the issue:

1. A pytest failure that's NOT covered by P0 #1 (preexisting test problem we don't know about).
2. An npm build failure on a page I didn't intend to touch.
3. A migration that needs data backfill (rare for additive changes).
4. A discovery that an item's scope is materially larger than the estimate (e.g., search endpoint needs a search index).

Otherwise: keep going through the list.
