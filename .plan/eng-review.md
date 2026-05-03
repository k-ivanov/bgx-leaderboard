# Engineering Review — Refactor Plan (FastHTML → FastAPI + Vue 3 Pre-rendered SPA)

> Review of `.plan/refactor-plan.md` after Phase 1 (CEO) + Phase 2 (Design) closure. Run as Phase 3 of `/autoplan` on branch `refactor/fastapi-vue`, commit `cd2118f`.
> **Voices:** Claude primary + Claude subagent. Codex CLI unavailable → single-voice mode `[subagent-only]`.
> **Overall eng completeness: 6.5 / 10 (primary + subagent agree).**

---

## Step 0 — Scope Challenge

Reading the actual code being refactored:

| Sub-problem | Existing code (lines) | Reuse strategy |
|---|---|---|
| Domain models | `src/db/models.py` (139) | Straight port to `backend/app/db/models.py` |
| DB session + engine | `src/db/session.py` (29) | Same |
| Standings calculation (both formats) | `src/services/standings.py` (158) | Same — already returns `StandingsRow` dataclasses |
| Rider profile + disambiguation | `src/services/rider.py` (129) | Same |
| Visit tracking (device detection) | `src/database.py` (~79) | Logic reused; **implementation moves to `POST /api/track`** (not middleware — see HC-4 below) |
| Alembic migration | `alembic/versions/0001_initial_schema.py` | Same |
| Seed constants | `src/seasons.py` | Same |
| Golden test | `tests/test_standings_2025.py` (129) | Same |

**Reuse proportion:** ~800 of the ~1100 lines of backend Python are moved unchanged. Rewrite is concentrated in `routes.py` (547 lines → thin API routers) and the discarded `ui/` DSL.

**Scope is tight and justified.** No reduce/expand recommendation from primary.

---

## ARCHITECTURE — Dependency Diagram

```
                                 ┌──────────┐
                Browser ────────▶│ Railway  │ (single service, HTTPS)
                                 └────┬─────┘
                                      ▼
                       ┌─────────────────────────────┐
                       │  FastAPI (Uvicorn, :5001)   │
                       │                             │
                       │  Mount order (CRITICAL):    │
                       │   1. /api/*    routers      │
                       │   2. /health                │
                       │   3. /app/*    StaticFiles  │
                       │   4. /*        SPA fallback │
                       │   5. /         302 → /app/  │
                       │   6. /{year}/..  302 → /app │
                       │                             │
                       │  ┌───────────────────┐      │
                       │  │  api/             │      │
                       │  │  seasons.py       │      │
                       │  │  standings.py     │      │
                       │  │  events.py        │      │
                       │  │  results.py       │      │
                       │  │  riders.py        │      │
                       │  │  stats.py (AUTH!) │      │
                       │  │  track.py (POST)  │      │
                       │  │  deps.py (shared) │      │
                       │  └──────────┬────────┘      │
                       │             │               │
                       │  ┌──────────▼────────┐      │
                       │  │ schemas/ (Pyd v2) │      │
                       │  │  common.py        │      │
                       │  │  ↳ RiderRef       │      │
                       │  │  seasons, events, │      │
                       │  │  standings, rider │      │
                       │  └──────────┬────────┘      │
                       │             │               │
                       │  ┌──────────▼────────┐      │
                       │  │ services/ (pure)  │──────┼──▶ Postgres
                       │  │ + db/             │      │
                       │  └───────────────────┘      │
                       │                             │
                       │  StaticFiles(dir="frontend_dist") ─▶ frontend_dist/
                       │                                     (~25 pre-rendered HTML)
                       └─────────────────────────────┘
```

**Architecture findings (primary + subagent agree):**

| # | Finding | Severity | Voice |
|---|---|---|---|
| A-1 | Mount order not specified in plan — `/api/nonexistent` could return `index.html` if SPA catch-all mounts first | HIGH | both |
| A-2 | `services/` returns ORM relationships (lazy-loaded); Pydantic response serialization across the boundary can trigger queries post-commit | MEDIUM | subagent |
| A-3 | Router files will duplicate helpers (`_get_season`, `_rider_slug`, `_all_years`, `_not_found`). Plan doesn't call out shared deps | MEDIUM | subagent |
| A-4 | No shared `RiderRef` schema — plan mentions "rider identifier must include slug", but scope isn't modeled | MEDIUM | subagent |

**Fix for A-1:** Mount order documented in `backend/app/main.py` header comment AND a test in `tests/test_mount_order.py` asserting `GET /api/nonexistent` returns 404 JSON, `GET /app/nonexistent-deep-path` returns index.html.

**Fix for A-2:** Every API endpoint eager-loads with `selectinload` before returning. Pydantic schemas use `from_attributes=True` only on explicitly-loaded relationships.

**Fix for A-3:** `backend/app/api/deps.py` with `get_session`, `get_season(year: int)`, `get_category(season, code)` as FastAPI `Depends()` — 404 via `HTTPException`. All routers use these.

**Fix for A-4:** `backend/app/schemas/common.py::RiderRef { race_number: int, first_name: str, last_name: str, slug: str }` — embedded in Standings, EventResult, RiderProfile schemas. **Slug always computed on the backend**, never by the frontend (closes HC-5 below).

---

## CODE QUALITY

| # | Finding | Severity |
|---|---|---|
| CQ-1 | Current `_rider_slug()` in `routes.py` is `f"{first}-{last}".lower().replace(" ", "-")` — naive. Plan says "deterministic slugify(...)" which is a behavior change (accent stripping, double-dash collapse). Silent URL mutation would break existing shared links. | HIGH |
| CQ-2 | DRY: shared helpers currently inline in `routes.py`; risk of duplication across 6 new router files | MEDIUM |
| CQ-3 | Endpoint naming: `/api/seasons/{year}/categories/{cat}/events/{slug}` — 4 segments, different shape from siblings. Acceptable but document the reason | LOW |

**Fix for CQ-1:** Pin the EXACT current algorithm in `backend/app/slug.py::rider_slug(first, last) -> str`. Do NOT switch to a real slugify library in this refactor. Any future switch requires redirect table entries for mutated slugs.

**Fix for CQ-2:** `api/deps.py` (see A-3). Also `services/common.py` for any shared transforms.

---

## TEST REVIEW — Test Diagram (NEVER SKIP)

For every NEW codepath the plan creates, what test covers it?

| Codepath | Test type | Exists? | Gap / action |
|---|---|---|---|
| `GET /api/seasons` | contract | no | Add `tests/test_api.py::test_list_seasons` |
| `GET /api/seasons/{year}` | contract + 404 | no | Add + negative case |
| `GET /api/seasons/{year}/standings/{category}` | **contract + golden** | partial — `test_standings_2025.py` exists at service level | **Wrap endpoint with same 2025 CSV golden assertions — do not lose the golden guarantee** |
| `GET /api/seasons/{year}/events` | contract | no | Add |
| `GET /api/seasons/{year}/events/{slug}` | contract + 404 | no | Add |
| `GET /api/seasons/{year}/categories/{cat}/events/{slug}` | contract (+ empty-results branch) | no | Add |
| `GET /api/seasons/{year}/riders/{race_number}` (disambiguation list) | contract | no | **Add — seed two riders with same `(year, number)` but different names, assert list** |
| `GET /api/seasons/{year}/riders/{race_number}/{slug}` | contract + 404 + slug-mismatch | no | Add (3 tests) |
| `GET /api/stats` | contract + auth | no | **Auth required; see SC-1 below** |
| `POST /api/track` | contract + integration | no | Assert Visit row created; device_type derived; payload size capped |
| Legacy redirects `/{year}`, `/{year}/{category}`, etc. | integration | no | Add 6 redirect tests |
| SPA fallback | integration | no | `GET /app/deep/unknown/path` → 200 + index.html |
| Static mount | integration | no | `GET /app/assets/*.js` → 200, correct content-type |
| Mount order | integration | no | **`GET /api/nonexistent` → 404 JSON (not index.html)** |
| Pre-render build script | unit + smoke | no | Unit-test `scripts/prerender_routes.py`; smoke: `grep '<title>' dist/2026/expert/index.html` in CI |
| Rider slug stability | unit | no | `rider_slug("João", "Silva-Costa")` pinned to current output |
| Visit source scoping | integration | no | Assert `/api/*` does NOT create Visit; `/app/*` POST /api/track does |
| Frontend router deep-link | e2e | no | Playwright: direct-load `/app/2026/r/42/john-doe`, refresh, assert render |

**Gap severity: HIGH.** Plan's "one contract test per endpoint" is too thin. Specifically missing negative paths, disambiguation, mount-order assertion, and SPA fallback behavior.

**Test plan artifact** written to: `~/.gstack/projects/k-ivanov-bgx-leaderboard/k-ivanov-refactor-fastapi-vue-test-plan-20260424.md` — contains the full matrix above plus fixture specs.

---

## PERFORMANCE

| # | Finding | Severity | Voice |
|---|---|---|---|
| P-1 | No bundle size budget set. Mosaic Lite + Vue + pinia + router + @vueuse/head + Tailwind can easily blow past 250 KB gzipped | MEDIUM | subagent |
| P-2 | Pre-render needs DB at build time — **CI/Railway build doesn't have one** | HIGH | subagent |
| P-3 | Alembic runs in Docker CMD on every boot — slow cold start | MEDIUM | subagent |
| P-4 | `pool_size=5` default on Postgres — fine for current load; raise to 10/20 for safety | LOW | subagent |
| P-5 | N+1 risk in `get_rider_profile` Pydantic serialization if relationships lazy-load post-commit | MEDIUM | subagent (duplicates A-2) |

**Fix for P-1:** CI gate: `size-limit` or `bundlesize` plugin, threshold 250 KB JS gzipped + 50 KB CSS. Fail PR if exceeded.

**Fix for P-2 (critical for deploy):** Two-step build:
1. Pre-build step runs once (locally or in a scheduled CI job) — hits a reachable DB (dev or prod read replica), writes `frontend/prerender-routes.json` — committed to repo.
2. Vite build consumes the committed JSON. No DB needed at Railway build time.
3. Add a weekly CI job that regenerates the snapshot and opens a PR if stale.

Alternative (simpler): call the deployed production API from the CI build step to get the route list, write locally, proceed. Requires prod API URL + auth for `/api/seasons/{year}/events`.

**Fix for P-3:** Accept alembic-on-boot (idempotent, ~2s with no pending migrations). If cold start becomes painful, move to a Railway "predeploy" command.

---

## SECURITY

| # | Finding | Severity | Voice |
|---|---|---|---|
| SC-1 | `/api/stats` and `/stats` UI are labeled "private" but have **no auth mechanism in plan or current code** — anyone who finds the URL sees visit data | **CRITICAL** | subagent |
| SC-2 | `POST /api/track` is unauthed write endpoint. With E4 (rate-limit) rejected, it's a flood vector | MEDIUM | subagent |
| SC-3 | CORS: plan says same-origin, no CORS middleware. Must add a test asserting no `Access-Control-Allow-Origin` header is emitted | MEDIUM | subagent |
| SC-4 | XSS: Vue auto-escapes; `v-html` forbidden by ESLint rule | MEDIUM (defensive) | subagent |
| SC-5 | SQL injection: ORM-mediated, path params typed. **Confirmed safe** | — | both |
| SC-6 | Visit tracking PII: no IP, no full UA stored, only derived device_type. **Safe** | — | both |

**Fix for SC-1:** Pick one:
- (a) **HTTP Basic Auth** gated by env var `STATS_PASSWORD` — FastAPI `Depends(HTTPBasic)`. Cheap, done in 30 min.
- (b) **Noindex + obscure path** (e.g., `/api/stats-{token}`) — weaker, but matches current FastHTML behavior if that was acceptable.

Recommend (a). Store env var in Railway Secrets.

**Fix for SC-2:** Cap `POST /api/track` payload size (e.g., 2 KB), reject payloads larger. Add in-memory per-IP rate limit via Starlette middleware (even though E4 was rejected for the general API, /track specifically is a mutation and needs defense).

**Fix for SC-3:** `tests/test_cors.py::test_no_cors_headers` — assert outgoing response has no `Access-Control-*` headers.

**Fix for SC-4:** ESLint config: `"vue/no-v-html": "error"`.

---

## HIDDEN COMPLEXITY

| # | Finding | Severity |
|---|---|---|
| HC-1 | SPA fallback vs `/api/*` ordering (see A-1) | HIGH |
| HC-2 | Pre-render DB dependency at build time (see P-2) | HIGH |
| HC-3 | Mosaic Lite license audit — Cruip splits free/pro in same org; verify file-by-file | MEDIUM |
| HC-4 | Visit middleware timing: FastAPI middleware runs BEFORE routing, so it can't know the matched route template. Use Depends or POST /api/track | MEDIUM |
| HC-5 | Slug non-determinism across Python/JS boundary. Frontend must never compute slugs — always consume from API (`RiderRef.slug`) | HIGH |
| HC-6 | `@vueuse/head` + pre-render timing: reactive head tags set post-mount won't be in pre-rendered HTML unless using an SSR-compatible head renderer | MEDIUM |
| HC-7 | Category uniqueness vs rider identity: current model has `UniqueConstraint(category_id, race_number)` — matches "same person in 2 categories = 2 rows" semantics. No schema change needed | — (correctness note) |

**Fixes:**
- HC-1 → A-1 fix.
- HC-2 → P-2 fix.
- HC-3 → 30-min Day-0 license audit on specific files being copied; fall back to raw Tailwind if any ambiguity.
- HC-4 → **POST /api/track from Vue Router `afterEach`** (already recommended in plan — lock in as the only tracking mechanism, remove the middleware option).
- HC-5 → API always returns `RiderRef.slug`, frontend never computes. Test: `GET /api/seasons/2025/standings/expert` response contains `slug` for every rider.
- HC-6 → Evaluate: does chosen `vite-plugin-prerender` honor `@vueuse/head` during the prerender pass? If not, use `@unhead/vue` (newer, SSR-native) or inline head tags in Vue Router's `meta` + a small plugin that writes them before prerender. Test: `grep '<title>' frontend/dist/2026/expert/index.html` must return non-empty.

---

## NOT IN SCOPE (deferred)

- Nuxt 3 SSR migration (UC-2 follow-up only if organic traffic regresses post-launch)
- Admin UI replacing import scripts
- Rider comparison, live results, i18n, structured logging (CEO deferrals)
- Real slugify library adoption (CQ-1 — future, requires redirect table)
- Table sort UI (design discipline — stated out-of-scope)

---

## Failure Modes Registry (eng-specific, merges with CEO's)

| Failure | Detection | Rescue | Critical? |
|---|---|---|---|
| Mount order wrong → `/api/*` returns `index.html` | `tests/test_mount_order.py` | Reorder in `main.py` | **YES — breaks API contract silently** |
| Pre-render snapshot missing → CI build fails | CI log | Commit snapshot file or regenerate | YES |
| Slug mutation → existing rider links 404 | Contract test pinning current algorithm | Keep naive algorithm | YES |
| `/stats` exposes visit data to anyone who finds URL | Security scan / pen-test | Add HTTP Basic Auth before launch | **CRITICAL** |
| `/api/track` POST flood writes unbounded rows | Postgres slow log | Payload cap + rate limit | YES |
| N+1 in Pydantic serialization | APM / slow log | Explicit eager-load per endpoint | YES |
| Bundle > 250 KB gzipped | CI size-limit gate | Code-split or drop a dep | NO (warn) |
| Mosaic Lite file carries non-MIT license | Day-0 audit | Drop to raw Tailwind | NO (planned) |
| Head tags missing from pre-rendered HTML (HC-6) | CI grep check | Switch head lib or inline | YES |

---

## Eng Dual Voices — Consensus Table

```
ENG DUAL VOICES — CONSENSUS TABLE                  (single-voice mode: Codex unavailable)
═══════════════════════════════════════════════════════════════
  Dimension                           Primary  Subagent  Consensus
  ──────────────────────────────────── ──────── ────────── ──────────
  1. Architecture sound?              PARTIAL  PARTIAL    CONFIRMED — fixes A-1..A-4
  2. Test coverage sufficient?        NO       NO         CONFIRMED — gap is material
  3. Performance risks addressed?     PARTIAL  PARTIAL    CONFIRMED — P-1, P-2 missing
  4. Security threats covered?        NO       NO         CONFIRMED — SC-1 critical
  5. Error paths handled?             PARTIAL  PARTIAL    CONFIRMED — 404s implicit
  6. Deployment risk manageable?      PARTIAL  PARTIAL    CONFIRMED — P-2 blocker
═══════════════════════════════════════════════════════════════
```

**0 disagreements. 0 user challenges (no scope changes).**

---

## New Deliverables (fold into plan before coding)

Pre-Phase-1 and Pre-Phase-2 work, ~4-6h total:

| # | Deliverable | Adds to phase | Fixes |
|---|---|---|---|
| N1 | Mount-order spec + test in `main.py` | Phase 1 | A-1, HC-1 |
| N2 | `backend/app/api/deps.py` with shared Depends | Phase 1 | A-3, CQ-2 |
| N3 | `backend/app/schemas/common.py::RiderRef` | Phase 1 | A-4, HC-5 |
| N4 | `backend/app/slug.py::rider_slug()` pinned to current algorithm + unit test | Phase 1 | CQ-1, HC-5 |
| N5 | Expanded test matrix (see Test Review) — replace "one test per endpoint" | Phase 1 + Phase 4 | test gap |
| N6 | `/api/stats` HTTP Basic Auth gated by `STATS_PASSWORD` env var | Phase 1 | **SC-1 (critical)** |
| N7 | `/api/track` payload cap + per-IP rate limit | Phase 1 | SC-2 |
| N8 | CORS assertion test (no headers emitted) | Phase 1 | SC-3 |
| N9 | ESLint `vue/no-v-html: error` rule | Phase 2 | SC-4 |
| N10 | Pre-render DB strategy: commit `frontend/prerender-routes.json` + weekly CI regen | Phase 2 | **P-2 (blocker)** |
| N11 | Bundle size CI gate (250 KB JS / 50 KB CSS gzipped) | Phase 4 | P-1 |
| N12 | Confirmed head renderer works with pre-render (or switch to `@unhead/vue`) | Phase 2 | HC-6 |
| N13 | Mosaic Lite file-by-file license audit (~30 min on Day 0) | Phase 2 | HC-3 |

---

## Eng Completion Summary

| Dimension | Primary | Subagent | Consensus |
|---|---|---|---|
| Architecture | 7/10 | 6/10 | CONFIRMED — partial, A-1 fix mandatory |
| Code quality (as planned) | 7/10 | 6/10 | CONFIRMED — CQ-1 slug pin mandatory |
| Test coverage | 4/10 | 4/10 | CONFIRMED — matrix needed |
| Performance | 6/10 | 6/10 | CONFIRMED — P-2 blocker |
| Security | 3/10 | 3/10 | **CONFIRMED — SC-1 critical** |
| Hidden complexity handling | 5/10 | 5/10 | CONFIRMED — HC-2, HC-5, HC-6 fix needed |
| **Overall eng completeness** | **7/10** | **6/10** | **CONFIRMED 6.5/10** |

**Verdict:** Plan is structurally sound but has 3 deal-breakers that must be closed before coding:
1. **SC-1:** `/api/stats` auth (or ship same exposure as today).
2. **A-1 / HC-1:** Mount order explicit + tested.
3. **P-2 / HC-2:** Pre-render build-time DB strategy decided.

Plus 10 "plan edit" items (N2-N5, N7-N13) that take <4h total to close. No scope change. No user challenges.
