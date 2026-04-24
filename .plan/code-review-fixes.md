# Plan: Fix Code Review Findings (`refactor/fastapi-vue` → `development`)

> Addresses [`.code_review/refactor-fastapi-vue-to-development-review.md`](../.code_review/refactor-fastapi-vue-to-development-review.md).
>
> All 7 findings accepted as valid. Minor calibrations noted below.
> Target: land as a series of focused commits on `refactor/fastapi-vue` before merging to `development`.

---

## Finding assessment + calibration

| # | Severity | Finding | My take | Calibration |
|---|---|---|---|---|
| F1 | High | `/stats` static page is public | **Accept.** Missed this — SSG + auth on API only = page is actually public. | Recommending a slightly different fix than the reviewer (see below) — keep the shell static + noindex, but remove the build-time data fetch and render client-side behind HTTP Basic. Simpler than server-rendering `/stats`. |
| F2 | Medium | Stats auth fail-open when `STATS_PASSWORD` empty | **Accept.** | Add `STATS_DEV_MODE` opt-in flag. Empty password with no dev flag in a deployed container = 503 at startup. |
| F3 | Medium | `conftest.py` autouse DB seed breaks "DB-free" tests | **Accept.** Clear defect. | Straight fix: remove `autouse=True`, make DB tests explicitly request the fixture. |
| F4 | Medium | Dockerfile duplicates deps from `pyproject.toml` | **Accept.** | Replace the explicit `pip install "fastapi>=..." …` with `pip install .` against the copied `pyproject.toml`. |
| F5 | Medium | Root + year redirects baked in at build time | **Accept.** Real operational regression vs the old FastHTML app. | Move `/` and `/{year}/` to FastAPI-level 302s registered BEFORE the static mount. Keeps everything else SSG. |
| F6 | Low | Broad `except Exception` in `FrontendStatic` | **Accept.** | Catch only `StarletteHTTPException` / `FileNotFoundError`. |
| F7 | Low | No automated linting | **Accept — scoped.** The reviewer asks for Python + frontend + CI. For initial scope, ship **Ruff (format + lint)** for Python and **ESLint flat config + Prettier** for the frontend, wired into `make check`. CI workflow is a separate follow-up (noted as roadmap in `PROJECT.md` §15). |

**None of the findings require pushback.** One recommendation is refined (F1), one is scope-reduced (F7).

---

## Execution order

Commits are sized to stay reviewable. Each row is one commit.

| # | Commit title | Finding | Files touched | Rough effort |
|---|---|---|---|---|
| C1 | `fix(tests): make DB seeding opt-in per test module (F3)` | F3 | `backend/tests/conftest.py`, `backend/tests/test_api.py`, `backend/tests/test_track.py`, `backend/tests/test_standings_2025.py` | ~15 min |
| C2 | `fix(docker): install backend from pyproject.toml (F4)` | F4 | `Dockerfile` | ~5 min |
| C3 | `fix(backend): narrow exception handling in FrontendStatic (F6)` | F6 | `backend/app/main.py`, `backend/tests/test_mount_order.py` | ~15 min |
| C4 | `fix(backend): stats auth fail-closed in prod (F2)` | F2 | `backend/app/config.py`, `backend/app/auth.py`, `backend/app/main.py`, `backend/tests/test_api.py`, docs | ~30 min |
| C5 | `fix(backend): dynamic redirects for / and /{year} (F5)` | F5 | `backend/app/main.py` + new `backend/app/api/redirects.py`, `frontend/src/pages/index.astro`, `frontend/src/pages/[year]/index.astro`, tests | ~45 min |
| C6 | `fix(frontend): /stats fetches client-side with HTTP Basic (F1)` | F1 | `frontend/src/pages/stats.astro`, `backend/app/main.py` (path-gate), new `frontend/src/components/stats/*.vue` (island), tests, docs | ~90 min |
| C7 | `chore: add Ruff + ESLint + Prettier, wire into make check (F7)` | F7 | `backend/pyproject.toml`, `frontend/.eslintrc.*` + `.prettierrc`, `frontend/package.json`, `Makefile`, `PROJECT.md`/`CLAUDE.md` | ~60 min |

**Total wall-clock:** ~4 hours for everything.

---

## Detail per commit

### C1 — `fix(tests): make DB seeding opt-in per test module (F3)`

**Problem:** `backend/tests/conftest.py` declares `_seed_2025_session` with `scope="session", autouse=True`. Every test in the suite — even the ones whose docstring says "DB-free" — forces a Postgres connection. `make test-fast` only works because it bypasses conftest entirely, which is a leaky workaround.

**Change:**
- Remove `autouse=True` from `_seed_2025_session`. Keep the fixture; rename to `seed_2025` for clarity.
- In `backend/tests/test_api.py`, `test_track.py`, `test_standings_2025.py`: add an explicit dependency on `seed_2025` via a module-scoped `pytest.fixture(autouse=True, scope="module")` that requests it. So those suites still seed exactly once each.
- `backend/tests/test_slug.py`, `test_mount_order.py`, `test_cors.py`: no change needed — they'll now run without touching Postgres.
- `Makefile:test-fast` can drop the `--noconftest` workaround.

**Acceptance:**
- `backend/.venv/bin/python -m pytest backend/tests/test_slug.py backend/tests/test_mount_order.py backend/tests/test_cors.py` succeeds without Postgres running.
- `pytest` full suite: still 64/64 with DB up.
- `make test-fast` still 18/18.

### C2 — `fix(docker): install backend from pyproject.toml (F4)`

**Problem:** `Dockerfile` lines 58–71 hardcode every runtime dep; `backend/pyproject.toml` declares the same list. Drift is a matter of time.

**Change:**
- Replace the explicit `pip install "fastapi>=0.110" …` block with:
  ```dockerfile
  COPY backend/pyproject.toml /app/pyproject.toml
  COPY backend/src/README.md /app/src/README.md  # required by hatchling
  RUN pip install --no-cache-dir --upgrade pip \
      && pip install --no-cache-dir /app --no-deps=false
  ```
  Or simpler: `pip install --no-cache-dir -e /app/` (editable works at build, avoids a wheel build).
- Leave dev-only deps (`pytest`, `httpx`) out of the runtime image since `pip install .` without `[dev]` extra skips them.

**Acceptance:**
- `./scripts/build-image.sh` succeeds.
- Container boots, `make smoke` green.
- Changing a dep in `pyproject.toml` + rebuilding picks it up (manual check: bump a minor version, confirm image picks it up).

### C3 — `fix(backend): narrow exception handling in FrontendStatic (F6)`

**Problem:** `backend/app/main.py` `FrontendStatic.get_response` does `except Exception: return 404.html`. A filesystem permission error, a runtime bug, or any unexpected failure becomes indistinguishable from "page doesn't exist".

**Change:**
- Import `starlette.exceptions.HTTPException` and `from starlette.responses import FileResponse`.
- Replace `except Exception` with `except HTTPException as e: if e.status_code == 404: serve 404.html else: raise`.
- Also handle `FileNotFoundError` explicitly (mainly for safety during the fallback file-stat path).
- Let all other exceptions propagate — FastAPI's default handler will return 500 JSON for them, which is what we want.
- Add a test: inject a StaticFiles that raises `PermissionError` and assert the response is 500, not 404.

**Acceptance:**
- Existing mount-order tests still pass.
- New test: `test_static_mount_surfaces_5xx_errors` passes (PermissionError → 500, not 404.html).

### C4 — `fix(backend): stats auth fail-closed in prod (F2)`

**Problem:** `STATS_PASSWORD=""` disables auth globally. Any Railway misconfig (env var unset by mistake) silently exposes visit analytics.

**Change:**
- Add env var `BGX_ENV` defaulting to empty; canonical values `dev`, `prod`.
- In `backend/app/config.py`:
  ```python
  BGX_ENV = os.getenv("BGX_ENV", "").lower()
  STATS_DEV_BYPASS = BGX_ENV in ("", "dev")
  ```
- In `backend/app/auth.py::require_stats_auth`:
  - If `STATS_PASSWORD` is non-empty → existing behavior (check Basic header).
  - If empty AND `STATS_DEV_BYPASS` true → allow (existing dev convenience).
  - If empty AND not dev → raise 503 with `"detail": "Stats endpoint not configured"` + log a WARNING once at startup.
- In `app.main::create_app`: if `STATS_PASSWORD == ""` AND `BGX_ENV == "prod"`, emit a loud warning log at app startup so it's visible in Railway logs.
- Update `DEPLOYMENT.md` env-var table: document `BGX_ENV` requirement for production.
- Update `test_api.py::test_stats_is_accessible_in_dev_mode` to set `BGX_ENV=""` or keep default (still passes).
- Add `test_stats_requires_password_in_prod`: monkeypatch `BGX_ENV=prod`, `STATS_PASSWORD=""`, assert 503.

**Acceptance:**
- 65/65 tests green (the one new).
- Local dev (no env vars) still works — `/api/stats` returns 200.
- Container with `BGX_ENV=prod STATS_PASSWORD=""` returns 503 on `/api/stats`.

### C5 — `fix(backend): dynamic redirects for / and /{year} (F5)`

**Problem:** Current `/` and `/{year}/` redirects are pre-rendered at build time from the DB state at that moment. If the admin flips `is_current` to a new season, the static redirects still point at the old one until the next rebuild.

**Change:**
- Create `backend/app/api/redirects.py` with two FastAPI routes:
  - `GET /` → query `SELECT year FROM season WHERE is_current=true ORDER BY year DESC LIMIT 1`, fall back to `max(year)`, 302 to `/{year}/{first_category}`.
  - `GET /{year:int}/` (and `/{year}` via trailing-slash normalization) → find first category for that season, 302 to `/{year}/{category}`.
- Register these routes in `app.main::create_app` AFTER `/api/*` routers and BEFORE the static mount. FastAPI's path-specific routes win over StaticFiles' catch-all.
- Delete `frontend/src/pages/index.astro` and `frontend/src/pages/[year]/index.astro` — they're no longer needed (FastAPI handles those paths).
- Add tests:
  - `test_root_redirect_dynamic` — seed 2 seasons, flip `is_current`, assert redirect target changes without rebuilding.
  - `test_year_redirect_dynamic` — hit `/2026/`, assert 302 to a real category.

**Acceptance:**
- 67/67 tests green (two new).
- Manual: toggle `UPDATE season SET is_current=true WHERE year=2025; UPDATE season SET is_current=false WHERE year=2026;` — `GET /` now redirects to `/2025/...` without a rebuild.

### C6 — `fix(frontend): /stats fetches client-side with HTTP Basic (F1)`

**Problem:** `/stats` is a statically generated page. If the build succeeds (with password or dev bypass), the snapshot is embedded in public HTML. If the build fails auth, the page still exists publicly as "stats unavailable" — i.e. the shell is always public.

**Fix (better than the reviewer's "server-render /stats" because it preserves the SSG architecture):**

1. **Keep the static shell** at `/stats`, but strip the build-time data fetch. The page renders only the `noindex` head tag + a Vue island that fetches `/api/stats` on mount.
2. **Protect the page URL at the FastAPI layer.** Extend `FrontendStatic` to require HTTP Basic when the request path starts with `/stats`. Reuses the same `STATS_PASSWORD` check as the API.
3. **Client-side fetch** in the Vue island. Browser gets a 401 from `/api/stats` → native basic-auth prompt → retries with credentials. Same flow the user already expects.

**Files:**
- `frontend/src/pages/stats.astro` — remove `const stats = await api.getStats()` + all the build-time rendering. Reduce to shell + `<StatsDashboard client:only="vue" />`.
- New `frontend/src/components/stats/StatsDashboard.vue` — mounts, fetches `/api/stats`, renders the existing three sections (stat cards + per-category table + recent visits).
- `backend/app/main.py::FrontendStatic.get_response` — add: if path starts with `stats` AND not dev-bypass, require `Authorization: Basic`.
- `backend/tests/test_api.py` — add `test_stats_page_requires_auth_in_prod` to cover the path-level gate.
- Update `PROJECT.md` §3.7 + §13 to reflect the new model.

**Acceptance:**
- 68/68 tests green.
- In dev: visiting `/stats` at `localhost:4321` → shell renders, island calls `/api/stats`, data appears (no auth needed, dev bypass).
- In prod mode: visiting `/stats` → 401 Basic Auth challenge from FastAPI before any HTML is served. After correct password, shell loads, island fetches `/api/stats` with the now-cached Basic Auth header, data renders.

### C7 — `chore: add Ruff + ESLint + Prettier (F7)`

**Scope-reduced from reviewer's ask** — ship Ruff (format + lint in one tool, replacing Black/Flake8/isort) and ESLint + Prettier. Skip Mypy for now (Pydantic + Astro's own type-checking already cover a lot; adding Mypy is its own scope).

**Change:**
- `backend/pyproject.toml` — add Ruff config under `[tool.ruff]` with sensible defaults (line-length 100, extend-select = ["E", "F", "I", "B", "UP"]), add `ruff` to `[project.optional-dependencies] dev`.
- Run `ruff check --fix .` + `ruff format .` once on the existing code. Commit the resulting formatting changes as part of this commit.
- `frontend/package.json` — add `eslint`, `@typescript-eslint/*`, `eslint-plugin-astro`, `prettier`, `prettier-plugin-astro` to devDependencies. Add `lint` and `format` scripts.
- `frontend/.eslintrc.cjs` or flat config — minimal recommended rules; forbid `v-html` (eng-review SC-4).
- `frontend/.prettierrc` — minimal config matching the existing code style (single quotes, no trailing commas in function args, 2 spaces).
- Run ESLint + Prettier once on the existing tree; commit formatting changes.
- `Makefile` — add `lint-backend` (ruff), `lint-frontend` (eslint + prettier --check), and wire both into `make check`.

**Acceptance:**
- `make check` runs: pytest + astro check + ruff check + eslint + prettier --check. All green.
- A deliberately broken style (`v-html`, unused import, 200-char line) fails the respective linter.
- No Ruff/ESLint/Prettier config files in `.gitignore`.

---

## Testing / verification strategy

After each commit:
1. `make test` passes.
2. `make check-frontend` passes.
3. `make build` still produces a working image.
4. `make smoke` against the running image still returns expected responses.

At the end:
- `make check` green.
- `make build && make run && make smoke && make run-stop` green.
- Manually verify the three behavioral changes:
  - Flip `is_current` between seasons → `GET /` immediately redirects to the new season.
  - Set `BGX_ENV=prod STATS_PASSWORD=""` → `GET /api/stats` returns 503.
  - Visit `/stats` with no auth → 401 challenge from FastAPI.

---

## Open questions (non-blocking — assuming sensible defaults)

1. **F5 redirects:** Do you want `/` and `/{year}/` to eventually be cacheable at a CDN layer? If yes, a `Cache-Control: public, max-age=60` on the 302 is fine; if the dynamic behavior needs to be immediate, keep `no-store`. Defaulting to `no-store` since this is Railway, no CDN in front.
2. **F7 scope:** OK to skip Mypy for this pass? Adding it later is easy; doing it now is ~1-2 extra hours and a first run will likely need 50+ annotations.
3. **F1 UX:** Once `/stats` is behind Basic Auth at the page level, the browser will cache credentials per origin. Acceptable, but if you want auth to time out, we'd need a session cookie instead. Defaulting to browser-cached Basic for simplicity.

---

## What this does NOT address

Explicit non-goals of this plan — already noted in `PROJECT.md` §15 Roadmap or the reviewer's "Out of scope" lens:

- CI pipeline (GitHub Actions) — separate follow-up.
- Font subsetting toward the 80 KB budget — separate polish PR.
- Astro sitemap integration replacement — separate polish PR.
- Production Railway cutover + metrics baselines — requires Search Console access + maintenance window.

---

## Rollback

If any commit regresses behavior unexpectedly, `git revert <sha>` on the individual commit. No data migrations, no schema changes, so every commit in this plan is trivially reversible.
