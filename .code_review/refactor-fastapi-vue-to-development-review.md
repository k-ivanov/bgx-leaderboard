# PR Review: `refactor/fastapi-vue` -> `development`

## Scope

Senior-level review of the refactor from the legacy FastHTML app to the new FastAPI + Astro split, focused on:

- correctness and behavioral regressions
- security and operational safety
- design patterns and maintainability
- coding standards and test coverage

Reviewed against `git diff development...refactor/fastapi-vue`.

## Findings

### 1. High: `/stats` is no longer actually private because the page is statically generated and served without auth

**Why this matters**

The PR treats `/stats` as a private analytics page, but only `/api/stats` is protected with HTTP Basic. The actual `/stats` page is generated at build time by Astro and then served as static HTML. That means the page itself is public.

**Evidence**

- `frontend/src/pages/stats.astro:13-25` fetches stats during the build and embeds either a snapshot or a fallback empty state into static HTML.
- `frontend/astro.config.mjs:17` sets `output: 'static'`, so `/stats` is pre-rendered.
- `backend/app/api/stats.py:20-24` protects only `/api/stats`, not `/stats`.

**Impact**

- If the image is built in an environment where `STATS_PASSWORD` is unset or the backend is reachable without auth, private analytics data can be baked into a public page.
- If the image is built with `STATS_PASSWORD` enabled, the page still remains public, but now it silently degrades to a static “unavailable” page rather than a protected analytics view.

**Recommendation**

Move `/stats` to server-rendered delivery behind the same auth gate, or add server-side protection for the page route itself. As implemented, the “private analytics page” requirement is not met.

### 2. Medium: stats authentication is fail-open, not fail-closed

**Why this matters**

The stats endpoint becomes public whenever `STATS_PASSWORD` is missing. For a sensitive/internal endpoint, that is the wrong default.

**Evidence**

- `backend/app/config.py:13-15` sets `STATS_PASSWORD = os.getenv("STATS_PASSWORD", "")`.
- `backend/app/auth.py:23-24` returns early and disables auth entirely when the value is empty.

**Impact**

Any deployment misconfiguration exposes visit analytics with no warning. This is especially risky in a refactor where infrastructure, Docker, and Railway wiring all changed in the same PR.

**Recommendation**

Fail closed in non-dev environments. At minimum, gate the “no password means no auth” behavior behind an explicit development flag and make production startup fail if stats auth is not configured.

### 3. Medium: the “DB-free” tests are not actually DB-free because the suite autoloads a Postgres seeding fixture

**Why this matters**

Several tests are documented as DB-independent, but the global autouse fixture forces a database connection for the whole suite. That makes the test story misleading and weakens confidence in local/CI verification.

**Evidence**

- `backend/tests/conftest.py:13-15` seeds 2025 data with a session-scoped autouse fixture.
- `backend/tests/test_cors.py:14-17` explicitly says it uses `/api/openapi.json` so the test does not require Postgres.
- `backend/tests/test_mount_order.py:16-18` describes DB-free route behavior checks.
- `Makefile:199-203` works around this by running `pytest --noconftest` for `test-fast`, which confirms the normal test layout is not truly isolated.

**Observed behavior**

Running `backend/.venv/bin/python -m pytest backend/tests/test_mount_order.py backend/tests/test_cors.py backend/tests/test_slug.py` failed before assertions with `psycopg2.OperationalError` from the autouse seed fixture.

**Impact**

- Developers and CI runners without a reachable Postgres instance cannot trust the “fast” subset unless they know the special Makefile path.
- IDE or direct `pytest` execution gives a misleading failure mode unrelated to the tests themselves.

**Recommendation**

Remove global DB seeding from `conftest.py` and make DB setup opt-in per module/fixture. Keep DB-free tests truly isolated.

### 4. Medium: the Docker runtime duplicates dependency declarations instead of installing from `pyproject.toml`

**Why this matters**

The backend dependencies now have two sources of truth: `backend/pyproject.toml` and the explicit `pip install` list in the Dockerfile. That is a maintainability and release risk.

**Evidence**

- `backend/pyproject.toml:8-25` defines the backend runtime and dev dependencies.
- `Dockerfile:58-71` repeats the runtime dependency list manually.

**Impact**

The two lists will drift over time. A dependency can be added, removed, or version-bumped in one place and not the other, producing “works locally, breaks in container” behavior that is hard to diagnose.

**Recommendation**

Install the backend package from `backend/pyproject.toml` in the image (`pip install .` or equivalent lock-based install) and keep a single dependency source of truth.

### 5. Medium: root redirects are now frozen at build time and can go stale when season metadata changes

**Why this matters**

The old app resolved “current season” dynamically at request time. The new implementation bakes redirects into static output.

**Evidence**

- `frontend/astro.config.mjs:17` configures a static build.
- `frontend/src/pages/index.astro:5-9` resolves the current season during build and emits a static redirect.
- `frontend/src/pages/[year]/index.astro:12-14` resolves the first category during build and emits a static redirect.

**Impact**

If `season.is_current` changes or category ordering changes in the database, `/` and `/{year}/` remain wrong until a full frontend rebuild. That is an operational behavior change, not just an implementation detail.

**Recommendation**

Either accept this explicitly and document it as a rebuild requirement, or move these redirects behind request-time logic.

### 6. Low: broad exception swallowing in the static mount masks real server-side faults as 404s

**Why this matters**

The static mount turns any exception from `StaticFiles` into a branded 404 page.

**Evidence**

- `backend/app/main.py:194-199` catches `Exception` broadly and serves `404.html`.

**Impact**

Filesystem permission issues, unexpected runtime errors, and other non-404 conditions become indistinguishable from legitimate missing routes. That reduces observability and can hide deployment problems.

**Recommendation**

Catch only the specific “not found” cases you intend to translate. Let unexpected exceptions surface as 5xx responses.

### 7. Low: standards enforcement is mostly manual; the repo does not enforce Python or frontend linting/formatting

**Why this matters**

For a refactor of this size, relying on manual discipline is not enough. The PR introduces a large new backend, frontend, build system, and deployment flow without automated style or static-analysis gates.

**Evidence**

- `backend/pyproject.toml:21-36` contains pytest config but no Ruff/Black/Mypy setup.
- `frontend/package.json:6-14` contains `astro check` and API type generation, but no ESLint or Prettier scripts.
- `Makefile:193-210` runs pytest and `astro check`, but no lint/format/static-analysis targets.

**Impact**

- Standards compliance is subjective and reviewer-dependent.
- Design-pattern drift and low-signal style churn are more likely in future PRs.

**Recommendation**

Add at least one enforced Python linter/formatter and one frontend linter/formatter, then wire them into `make check` and CI.

## Positive Notes

- The API surface is much cleaner than the previous monolith: routers, schemas, and shared dependencies are separated sensibly.
- The route mount ordering and `/api/*` JSON 404 behavior are explicitly documented and tested, which is a good defensive design choice.
- The `/api/track` endpoint has reasonable hardening for a lightweight analytics endpoint: schema validation, payload size cap, and rate limiting.
- The typed frontend API layer is a good direction; generating the OpenAPI schema into TS types reduces contract drift.

## Open Questions

1. Is the intent for `/stats` to be truly private in production, or is the current “public page with build-time snapshot” behavior considered acceptable?
2. Is the single-container Docker build expected to be reproducible in CI without an already-running API, or is the live backend dependency during `astro build` an accepted constraint?
3. Should season/category redirects remain dynamic, or is a rebuild-on-data-change workflow acceptable for this product?

## Verification Notes

- Reviewed the branch diff and the new backend/frontend runtime paths directly.
- Ran a lightweight pytest subset locally:
  - `backend/.venv/bin/python -m pytest backend/tests/test_mount_order.py backend/tests/test_cors.py backend/tests/test_slug.py`
- That run failed in setup because `backend/tests/conftest.py` unconditionally seeds Postgres, so I could not validate the DB-free tests as claimed without a reachable database.
