# Django 6 + Django Ninja Rewrite — Parallel Task Breakdown

Source plan: `~/.claude/plans/is-it-feasible-to-joyful-gem.md`
Decisions locked: Django 6 + Django Ninja · port to Django ORM · Astro SSG
frontend unchanged · big-bang single cutover (no rollback/strangler — user
choice) · near-zero SEO impact (gated by acceptance checklist).

> **Reviewed 2026-05-17 — /plan-eng-review + Codex outside voice.**
> 11 decisions applied (8 review findings + S7 + 4 Codex hardening bundles;
> gunicorn swap kept, Codex OV2 rejected). See `## GSTACK REVIEW REPORT` at
> the end. Scope was challenged and the user chose big-bang as-is; the cutover
> failure mode is documented in `## Failure modes`, not re-litigated.

**Why these slices are safe to parallelize:** the Astro frontend is untouched,
so every backend slice's "done" is objective — its endpoints must return JSON
semantically + format equal to the current FastAPI app, validated by the
**existing pytest suite run against the old app side-by-side as the parity
oracle** and the frontend's generated OpenAPI typed client. The old behavior
is the spec.

---

## Parallelization map

```
Wave 0 (spine, serial):   F1 ─► F2(HITL) ─► F3
                            └─► X1, X2 (start as soon as F1 lands)

Wave 1a (parallel, after F3):  S1 · S2 · S5 · S6
        (after F2):            X3 · X4*   (*X4 also waits on S2)

Wave 1b (parallel, after S2):  S3 · S4 · S7

Wave 2 (serial, after all):    I1 (HITL — cutover)
```

Peak concurrency ≈ 6–8 agents. Each task = one branch + one PR.

**Claiming protocol for agents:** one agent per task ID. Branch
`django/<task-id>-<slug>`. **F1 freezes the router assembly + `config/urls.py`
order with every router slot pre-stubbed (decision I1-arch=A) — no slice ever
edits that file.** Each slice edits only its own `api/<domain>.py` module.
New Django code lives **side-by-side** with the existing `backend/` tree;
`backend/app` + `backend/src` stay frozen and deployable as the parity oracle
until I1 (decision I3-arch=A).

| ID | Title | Type | Blocked by | Owns (primary files) |
|----|-------|------|-----------|----------------------|
| F1 | Scaffold Django 6 + Ninja + frozen router assembly | AFK | — | `config/`, Dockerfile Stage 2 |
| F2 | Models + db_table pin + fake-initial | HITL | F1 | `core/models.py`, `core/migrations/` |
| F3 | Shared foundation: resolvers + serialization + test harness | AFK | F2 | `core/slug.py`, `api/deps.py`, `api/schemas/common`, `tests/conftest.py` |
| S1 | Seasons API | AFK | F3 | `api/seasons.py` |
| S2 | Standings + scoring service & router | AFK | F3 | `core/services/{standings,scoring}.py`, `api/standings.py` |
| S3 | Events / Races API | AFK | S2 | `api/events.py` |
| S4 | Riders API (career + search) | AFK | S2 | `core/services/rider.py`, `api/riders.py` |
| S5 | Stats API + auth gate | AFK | F3 | `api/stats.py`, `core/analytics.py` (read) |
| S6 | Track / analytics-write (incl. compare-tracking) | AFK | F3 | `api/track.py`, `core/analytics.py` (write) |
| **S7** | **Results API** *(added — review OV1)* | AFK | S2 | `api/results.py` |
| X1 | Legacy 301 redirects + static serving | AFK | F1 | `redirects/`, static catch-all view |
| X2 | Security headers + proxy/TLS + gated docs | AFK | F1 | security middleware, settings |
| X3 | Django admin (incl. auth bootstrap + opt-in parity) | AFK | F2 | `core/admin.py` |
| X4 | Management commands (importers) | AFK | **F2 + S2** | `core/management/commands/` |
| I1 | Integration & cutover | HITL | all | Dockerfile, Railway, SEO gate |

---

## F1 — Scaffold Django 6 + Django Ninja + frozen router assembly

### What to build
A bootable Django 6 project with Django Ninja, created **in a new top-level
path alongside the untouched `backend/` tree** (side-by-side; `backend/` stays
deployable as the parity oracle). One `NinjaAPI` instance whose router
assembly **and `config/urls.py` resolution order are written ONCE here with
every domain/cross-cutting router pre-stubbed to an empty placeholder Router**
in the load-bearing order (`/api/*` → `/health` → `/admin` → legacy 301s →
catch-all static). Settings ported from `backend/app/config.py` +
`backend/src/config.py`. Dockerfile Stage 2 runs `manage.py migrate` then boots
**gunicorn with a uvicorn ASGI worker** (process-model swap retained — review
OV2=B). Astro Stage 1 untouched.

### Acceptance criteria
- [ ] `manage.py runserver` boots; `GET /health` returns the same JSON shape/version as today
- [ ] `config/urls.py` + NinjaAPI assembly contain ALL router slots (S1–S7, X1–X3) pre-stubbed as empty Routers, in the exact load-bearing order, with a comment marking it frozen — slices fill only their own module
- [ ] `backend/app` + `backend/src` untouched and still runnable (parity oracle); a one-command way to run the old app for diffing is documented
- [ ] Settings read the same env vars as the current `config.py` modules (documented mapping)
- [ ] Container builds via `./scripts/build-image.sh`; Stage 1 (Astro) unchanged; Stage 2 boots gunicorn/ASGI and serves `/health`
- [ ] `pytest-django` harness runs (zero tests yet is fine)

### Blocked by
None - can start immediately.

---

## F2 — Models + db_table pinning + fake-initial migration  ⚠️ HITL

### What to build
Port `backend/src/db/models.py` to Django ORM models for all 8 tables. Every
model pins `class Meta: db_table` and exact column names to the existing
Alembic schema. Generate `0001_initial`; rehearse migration on a restored
production-DB clone.

**Invariant (redefined — review I2-arch=A):** the 6 domain tables
(`season`, `category`, `event`, `rider`, `event_result`, `visit`) **plus**
`import_log` and `analytics_salt` are adopted with **zero schema change**
(faked). Django's own `auth`/`admin`/`sessions`/`contenttypes` tables **are
created fresh — that is expected and must be part of the rehearsal**. The
old "no CREATE TABLE at all" framing is false once admin exists.

### Acceptance criteria
- [ ] Column-by-column diff of each Django model vs `backend/alembic/versions/*`; zero drift on the 8 existing tables
- [ ] All FKs/unique constraints/indexes/`server_default`s reproduced (incl. `event_result` per-day unique, visit indexes, `analytics_salt` PK)
- [ ] On a restored prod clone: the 8 existing tables get **no** `CREATE/ALTER/DROP`; Django contrib tables ARE created, and the full sequence is captured in a verification log
- [ ] `__str__` parity preserved
- [ ] Note carried to X3: `createsuperuser`/credential bootstrap replaces the `ADMIN_PASSWORD` gate (see X3)
- [ ] **Human sign-off** on the rehearsal before merge (data-loss gate)

### Blocked by
- F1

---

## F3 — Shared foundation: resolvers + serialization + test harness

### What to build
The shared layer every slice imports. Three responsibilities:

1. **Canonical resolvers (review I4-arch=A):** `core/slug.py` (byte-for-byte
   copy of `backend/app/slug.py`), the common schemas (`RiderRef`,
   `CategoryRef`, `EventRef`, `SeasonRef` + `build_rider_ref`) as Ninja
   `Schema`, and `resolve_season(year)` / `resolve_category(season, code)`
   helpers returning the **exact current 404 detail strings**, plus the
   `NinjaAPI` 404/4xx exception handler — with **one fully-worked reference
   endpoint** slices copy. (Django Ninja has no FastAPI `Depends`; this is a
   pattern redesign, not a literal port.)
2. **Serialization parity (review I5-cq=A):** pin the Ninja renderer and
   document exact encoding (Decimal→number with fixed scale matching current
   output, datetime ISO format, no key re-sorting). Ship an
   `assert_json_parity(old, new)` test helper.
3. **Test harness (review I7-test=A):** own `tests/conftest.py`, the test DB
   fixture, the **2025 golden fixture data**, the Ninja `TestClient` wiring,
   and the **old↔new parity rig** (spins the frozen `backend/` app and diffs
   responses via `assert_json_parity`).

### Acceptance criteria
- [ ] `core/slug.py` byte-identical; ported `test_slug.py` asserts slug parity on a fixture set
- [ ] `resolve_season`/`resolve_category` return identical 404 detail strings to `backend/app/deps.py`; reference endpoint passes parity rig
- [ ] Common schemas validate from Django instances; `RiderRef.from_orm` JSON byte-matches current API via `assert_json_parity`
- [ ] Renderer pinned + serialization spec documented; `assert_json_parity` helper covers Decimal/date/key-order
- [ ] Harness: conftest + DB + 2025 golden fixtures + TestClient + old↔new parity rig all runnable; one reference parity test green end-to-end
- [ ] S1–S7/X4 depend on this; no slice ships its own DB fixture or bespoke lookup

### Blocked by
- F2

---

## S1 — Seasons API

### What to build
Seasons endpoints (`backend/app/api/seasons.py`): list seasons + season detail
(categories), using F3 resolvers/schemas/parity helper.

### Acceptance criteria
- [ ] Endpoints match current OpenAPI schema; parity via F3 `assert_json_parity` against the old app
- [ ] Ported seasons tests green; frontend `openapi-typescript` regenerates with no diff for these paths

### Blocked by
- F3

---

## S2 — Standings + scoring service & router

### What to build
Port `backend/src/services/scoring.py` + `standings.py` to Django ORM
(algorithm bodies — points→position table, day-aggregation, drop rules,
`events_for_season`, `position_from_points`, `get_standings` — reused verbatim;
SQLAlchemy `select()`/`selectinload()` → Django ORM `select_related`/
`prefetch_related`), plus the standings/leaderboard router. Service hub for
S3/S4/S7.

### Acceptance criteria
- [ ] `test_scoring.py`, `test_standings_tiebreakers.py`, `test_standings_inverse_position.py` ported + green
- [ ] 2025 golden test passes via F3 parity rig
- [ ] **No N+1:** leaderboard query count within current bounds (assert in test)
- [ ] Standings router matches current OpenAPI schema

### Blocked by
- F3

---

## S3 — Events / Races API

### What to build
Events endpoints (`backend/app/api/events.py`): list races for a season + race
detail with categories, consuming `events_for_season` from S2. Vocabulary:
"Race/Races" (DB table stays `event`).

### Acceptance criteria
- [ ] Race list + detail match current OpenAPI schema; 404 detail strings preserved (F3 resolvers)
- [ ] Ported events tests green; editorial fields (`facebook_event_url`, `description`) surface identically (null-safe)

### Blocked by
- S2

---

## S4 — Riders API (career + search)

### What to build
Rider endpoints (`backend/app/api/riders.py` + `career_router`): per-season
profile, cross-season career, disambiguation, fuzzy search — consuming
`core/services/rider.py` (ported) and `get_standings` from S2. The
`/api/riders/career` slug contract feeds prerendered `/rider/{slug}` pages.

### Acceptance criteria
- [ ] `test_riders_career.py`, `test_riders_search.py` ported + green
- [ ] Career/profile/disambig/search byte-parity via F3 rig; slug values from `core/slug.py` only
- [ ] **No N+1:** rider-career query count within current bounds (assert in test) *(added — review I8-perf=A; this is the heaviest fan-out path)*
- [ ] Frontend typed client regenerates with no diff for rider paths

### Blocked by
- S2

---

## S5 — Stats API + auth gate

### What to build
Stats dashboard endpoints (`backend/app/api/stats.py`) + the stats auth gate
(`backend/app/auth.py` semantics: any non-empty user + `STATS_PASSWORD`; no-op
when unset). Port the read side of `backend/src/analytics.py` aggregation —
including `top_comparisons` (depends on S6 persisting `compared_with_slug`).

### Acceptance criteria
- [ ] Endpoints match current OpenAPI schema; same auth behavior (401 w/o creds when `STATS_PASSWORD` set; open when unset)
- [ ] Ported analytics/stats tests green; aggregation numbers (incl. `top_comparisons`) byte-parity on a fixture dataset

### Blocked by
- F3

---

## S6 — Track / analytics-write + throttling + payload guard

### What to build
The `POST /api/track` write path: cookieless visitor-id/daily-salt derivation,
device detection, **compare-page tracking (`compared_with_slug`) — feeds stats
`top_comparisons`** *(added — review OV3)*, Ninja built-in throttling (per-IP,
same limit as slowapi, reusing `client_ip.real_client_ip` logic), and the
pre-parse payload-size 413 guard.

**Atomicity requirement (added — review OV3):** the daily-salt create
(`INSERT ... ON CONFLICT DO NOTHING` semantics) + session-reuse "read latest
visit in the same flow" must remain race-safe at UTC midnight rollover and
under burst traffic. A naive Django ORM `get_or_create` is not equivalent —
preserve atomic upsert + the in-process cache behavior.

### Acceptance criteria
- [ ] `POST /api/track` writes a `Visit` row identical to current behavior incl. `compared_with_slug` for the compare page (ported test)
- [ ] Oversize body → 413 before JSON parse
- [ ] **Real-server integration test** for the 429 rate limit *(added — review OV3; the existing `test_track.py` explicitly does NOT exercise real rate limiting, and Ninja throttling is a new impl)*
- [ ] Concurrency test: simulated midnight rollover + burst does not create duplicate salts or mis-bucket sessions
- [ ] `test_client_ip.py`, `test_analytics.py` ported + green

### Blocked by
- F3

---

## S7 — Results API  *(added — review OV1)*

### What to build
Port `backend/app/api/results.py` end to end — the per-race results endpoint
the frontend's primary `/results` SPA island calls
(`ResultsView.vue:93`; mounted `results_api.router` at `main.py:110`).
Consumes the S2 scoring/standings service. This was missing from the original
13-task breakdown.

### Acceptance criteria
- [ ] Results endpoint(s) match current OpenAPI schema; byte-parity via F3 rig
- [ ] The `test_api.py` results contract assertions (`test_api.py:151`) ported + green
- [ ] Frontend typed client regenerates with no diff for results paths
- [ ] `/results` page renders identically against the new API (spot-check in I1)

### Blocked by
- S2

---

## X1 — Legacy 301 redirects + static serving (SEO-critical)

### What to build
Port `backend/app/redirects.py` exactly (every legacy pattern → identical 301
target; `/{year}/r/{n}` → 404) and replicate `FrontendStatic`: directory-index
**without** a 307/301 slash redirect, `404.html` real 404 status, JSON 404 for
unmatched `/api/*` and `/admin/*`, path-traversal guard, `APPEND_SLASH=False`.
Slots into the F1-frozen catch-all position.

### Acceptance criteria
- [ ] Ported `test_redirects.py` + `test_mount_order.py` green
- [ ] `/2026/expert` serves index 200 with **no** slash redirect
- [ ] `/sitemap-index.xml`, `/robots.txt`, `/404.html` byte-identical + correct status (404.html → 404)
- [ ] Unmatched `/api/*` → JSON `{"detail":"Not Found"}`

### Blocked by
- F1

---

## X2 — Security headers + proxy/TLS + gated docs

### What to build
Port `backend/app/security_headers.py` (CSP/HSTS/X-Frame/… same values) as
Django middleware + `SECURE_*` + django-csp, and the auth-gated `/api/docs` +
`/api/openapi.json`. Keep same-origin (no CORS).

**Proxy/TLS (added — review OV3):** the current HSTS logic is
scheme-sensitive. Behind Railway, Django must be configured with
`SECURE_PROXY_SSL_HEADER`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` so the
app correctly believes a forwarded request is HTTPS — `SECURE_*` flags alone
are insufficient.

### Acceptance criteria
- [ ] Every security header present with identical values (ported `test_security_headers.py`)
- [ ] Ported `test_cors.py` green — zero `Access-Control-*` headers
- [ ] `/api/docs` + `/api/openapi.json` 401 w/o creds when `STATS_PASSWORD` set; open in dev
- [ ] A test asserts HSTS is emitted for a forwarded-HTTPS request (proxy header honored), not just direct TLS

### Blocked by
- F1

---

## X3 — Django admin (incl. auth bootstrap + opt-in parity)

### What to build
Replace SQLAdmin with Django admin: `ModelAdmin` for
Season/Category/Event(Race)/Rider/EventResult(Result)/Visit, mirroring current
columns/search/sort/form-exclusions; Visit strictly read-only.

**Auth-model change is in scope, not silent (expanded — review OV3 + I2):**
the current model is env-gated shared credentials + signed session cookie,
disabled entirely when `ADMIN_PASSWORD` is unset. The plan must explicitly
cover: superuser/credential bootstrapping (how it's provisioned in
prod/Railway), the **disable-when-unset opt-in parity** (admin URL
absent/forbidden when not configured — no silent dev bypass), and migrating
the operator off `ADMIN_PASSWORD` onto Django auth.

### Acceptance criteria
- [ ] All 6 model views present with equivalent columns/search/sort; Visit read-only
- [ ] Admin URL absent/forbidden when admin not configured; reachable with provisioned credentials
- [ ] Documented credential-bootstrap path for Railway (no plaintext in image/repo)
- [ ] UI labels follow vocabulary (Race/Result) per `design-review.md §14`

### Blocked by
- F2

---

## X4 — Management commands (importers)

### What to build
Port `backend/scripts/*` (`import_2025`/`import_race_day`/`seed_all`/`seed_new`/
`upsert_calendar`/`scoring_diff_2026.py`) to Django management commands,
rewriting SQLAlchemy queries to Django ORM. `import_race_day` must preserve its
manual-edit-preservation logic. Re-run the 2025 import; assert golden parity.

### Acceptance criteria
- [ ] Commands reproduce identical DB rows vs the current importer on the same CSVs; `import_race_day` preserves operator-edited fields
- [ ] `test_import.py` ported + green
- [ ] `scoring_diff_2026` produces an identical report (requires the S2 scoring service)
- [ ] `ImportLog` dedup (filename+sha256 skip) preserved

### Blocked by
- **F2 + S2** *(corrected — review OV3: `scoring_diff_2026.py:17` imports `compute_event_scoring`, so the report depends on S2, not just F2)*

---

## I1 — Integration & cutover  ⚠️ HITL  (big-bang, no rollback — user choice)

### What to build
Final assembly + production cutover. All slices merged; full `pytest-django`
suite green via the F3 parity rig; OpenAPI diffed old↔new and frontend typed
client regenerated with no breaking diff; SEO acceptance gate executed;
`migrate --fake-initial` rehearsed once more on a fresh prod clone;
Dockerfile/Railway parity confirmed; staged deploy then DNS cutover; **`backend/`
deleted only here**.

### Acceptance criteria
- [ ] Full ported suite green (≈99 tests); golden-2025 + contract = parity proof
- [ ] **Endpoint parity run against a restored PROD clone, not just CSV fixtures** *(added — review OV3; prod has operator-edited fields the CSVs don't reproduce)*
- [ ] OpenAPI diff old↔new: no breaking changes; frontend `openapi-typescript` regenerates clean
- [ ] **SEO acceptance gate passes:** redirect conformance, `APPEND_SLASH=False`/URL shape, static surface (sitemap/robots/404 status), zero CORS, **route-count + sitemap-cardinality parity** (a truncated static build must fail the gate even if all API tests are green — added review OV3), Lighthouse vs M1–M7 unchanged
- [ ] `--fake-initial` rehearsed on a fresh prod clone; 8 domain tables zero drift, Django contrib tables created, data intact
- [ ] **Doc/ops parity** *(added — review I6-cq=A)*: `CLAUDE.md` (Running locally / Seed once / Tests), `backend/start.sh`, `scripts/build-image.sh`, Railway/Dockerfile commands updated to Django equivalents and verified
- [ ] Container builds + boots on Railway settings; spot-checks (`/health`, `/api/seasons`, a `/rider/{slug}`, the `/results` page, 3 legacy 301s) pass on staging
- [ ] **Human sign-off** before DNS cutover

### Blocked by
- All of the above (F1, F2, F3, S1–S7, X1–X4)

---

## NOT in scope

- **Reversible delivery / strangler-fig / scripted rollback** — user explicitly
  chose big-bang single cutover (Step 0, D1=A). Documented as a failure mode
  below, not mitigated.
- **Deferring/cancelling the rewrite** — premise challenged (D1=C available);
  user chose to proceed.
- **gunicorn → keep-uvicorn simplification** — Codex flagged it as gratuitous;
  user kept the gunicorn swap (OV2=B). Not changed.
- **New product features / scoring-rule changes** — pure framework/ORM port;
  behavior parity only.
- **Frontend changes** — Astro `frontend/` byte-for-byte unchanged by design.

## What already exists (reused, not rebuilt)

- `backend/app/slug.py::rider_slug` — pure fn, copied verbatim (F3); slug
  contract must stay byte-identical.
- `backend/src/services/{scoring,standings,rider}.py` — algorithm bodies reused
  verbatim; only the SQLAlchemy query layer is rewritten (S2/S4).
- `backend/src/analytics.py` — visitor-id/salt + device logic reused (S5/S6);
  atomic-upsert behavior must be preserved, not naively reimplemented.
- Pydantic v2 schemas (`backend/app/schemas/*`) — reused as Ninja `Schema`
  (Ninja `Schema` subclasses `pydantic.BaseModel`).
- The ~20-file pytest suite — the parity spec; ported, not rewritten. The
  frozen `backend/` app is the runtime parity oracle (no new oracle built).
- Astro `frontend/` + its `openapi-typescript` client — unchanged; the
  regenerated client is the contract check.

## Failure modes (per new codepath)

| Codepath | Realistic prod failure | Test? | Error handling? | Visible? |
|---|---|---|---|---|
| I1 big-bang cutover | `fake-initial` mis-pin or contract drift takes the public site down; no scripted rollback (user choice) | parity rig + prod-clone rehearsal | manual rollback only | **outage — CRITICAL GAP, accepted by user** |
| S6 daily-salt | midnight/burst race → duplicate salts / mis-bucketed sessions | concurrency test (added) | atomic upsert (required) | silent analytics skew if missed |
| S4 rider-career | missing `prefetch_related` → N+1, slow profiles | query-count assert (added) | none | slow site / DB load |
| X2 HSTS behind proxy | forwarded-HTTPS not detected → HSTS not sent | proxy-header test (added) | settings-dependent | silent security regression |
| X1 mount order | bad merge reorders catch-all → static shadows API | ported mount-order test | n/a | total API outage |
| S7 results | endpoint missing/divergent → primary page blank | ported `test_api.py:151` + parity | F3 404 handler | **visible — main page** |

**Critical gap (accepted):** the I1 cutover has no automated rollback. The user
chose big-bang at the Step 0 scope gate; this is recorded, not re-argued.

## Worktree parallelization strategy

| Lane | Tasks | Shared module risk |
|---|---|---|
| Spine | F1 → F2 → F3 (sequential) | none — distinct dirs; F1 freezes `config/urls.py` so no later lane touches it |
| Lane A | X1 (after F1) | `redirects/` — isolated |
| Lane B | X2 (after F1) | settings/middleware — isolated |
| Lane C | S1, S5, S6 (after F3, parallel) | each owns one `api/*.py` — no overlap |
| Lane D | S2 (after F3) → then S3, S4, S7 (parallel) | S3/S4/S7 each own one `api/*.py`; all read S2's `core/services/*` (read-only after S2 merges) |
| Lane E | X3 (after F2), X4 (after F2+S2) | `core/admin.py` / `management/` — isolated |
| Merge | I1 (after all) | integrates everything |

Launch Spine first. Once F1 lands: A + B in parallel. Once F3 lands: Lane C in
parallel. Once S2 lands: S3 + S4 + S7 in parallel. Lane E parallel after its
deps. **Conflict flag:** none on `config/urls.py` (frozen in F1, decision
I1-arch=A). Residual flag: S3/S4/S7 all import S2's service modules — S2 must
merge before they start (already encoded as blocked-by).

## Implementation Tasks
Synthesized from this review's findings. Each derives from a specific finding.

- [ ] **T1 (P1, human: ~2h / CC: ~20min)** — F1 — Freeze router assembly + `config/urls.py` with all S1–S7/X1–X3 slots pre-stubbed
  - Surfaced by: Architecture — I1-arch (9/10), shared write-hotspot
  - Files: `config/urls.py`, `api/__init__.py`
  - Verify: ported `test_mount_order.py` green; grep shows all router slots present
- [ ] **T2 (P1, human: ~3h / CC: ~30min)** — F2 — Redefine + document migration invariant (8 tables faked, Django contrib fresh) + rehearsal log
  - Surfaced by: Architecture — I2-arch (8/10), F2↔X3 conflict
  - Files: `core/models.py`, `core/migrations/0001_initial.py`, rehearsal runbook
  - Verify: prod-clone `migrate --fake-initial` log shows 8 tables untouched, contrib tables created
- [ ] **T3 (P1, human: ~1h / CC: ~10min)** — plan/F1 — Mandate side-by-side trees; `backend/` frozen as parity oracle until I1
  - Surfaced by: Architecture — I3-arch (8/10)
  - Files: F1 acceptance criteria, repo layout
  - Verify: old app runnable for diffing after F1
- [ ] **T4 (P1, human: ~3h / CC: ~30min)** — F3 — Canonical `resolve_season`/`resolve_category` + reference endpoint
  - Surfaced by: Architecture — I4-arch (8/10)
  - Files: `api/deps.py`, one reference `api/*.py`
  - Verify: 404 strings byte-match `backend/app/deps.py`
- [ ] **T5 (P1, human: ~4h / CC: ~40min)** — F3 — Serialization spec + pinned renderer + `assert_json_parity` helper
  - Surfaced by: Code Quality — I5-cq (8/10)
  - Files: `api/__init__.py` (renderer), `tests/parity.py`
  - Verify: helper proves Decimal/date/key-order parity on a sample payload
- [ ] **T6 (P1, human: ~4h / CC: ~40min)** — F3 — Full test harness (conftest, DB + 2025 golden fixtures, TestClient, old↔new rig)
  - Surfaced by: Test — I7-test (7/10)
  - Files: `tests/conftest.py`, `tests/fixtures/`, `tests/parity.py`
  - Verify: one reference parity test green end-to-end
- [ ] **T7 (P1, human: ~3h / CC: ~30min)** — S7 — Port `api/results.py` + ported results contract
  - Surfaced by: Outside voice — OV1 (results endpoint unowned)
  - Files: `api/results.py`, ported `test_api.py` results assertions
  - Verify: `/results` page renders against new API; `test_api.py:151` ported green
- [ ] **T8 (P2, human: ~2h / CC: ~20min)** — S6 — Compare-tracking (`compared_with_slug`) + real-server 429 test + midnight/burst atomicity test
  - Surfaced by: Outside voice — OV3 (track under-scoped, fake rate-limit parity, analytics race)
  - Files: `api/track.py`, `core/analytics.py`, `tests/test_track*.py`
  - Verify: compare row written; 429 integration test green; concurrency test green
- [ ] **T9 (P2, human: ~30min / CC: ~5min)** — S4 — Add rider-career query-count (N+1) acceptance test
  - Surfaced by: Performance — I8-perf (7/10)
  - Files: `tests/test_riders_career.py`
  - Verify: query count within current bounds
- [ ] **T10 (P2, human: ~1h / CC: ~10min)** — X2 — Proxy/TLS settings (`SECURE_PROXY_SSL_HEADER`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`) + forwarded-HTTPS HSTS test
  - Surfaced by: Outside voice — OV3 (proxy/TLS)
  - Files: `config/settings.py`, `tests/test_security_headers.py`
  - Verify: HSTS emitted for forwarded-HTTPS request
- [ ] **T11 (P2, human: ~2h / CC: ~20min)** — X3 — Admin auth bootstrap + disable-when-unset opt-in parity (documented, not silent)
  - Surfaced by: Outside voice — OV3 + I2-arch
  - Files: `core/admin.py`, `config/urls.py` (env-gated include), X3 runbook
  - Verify: admin absent when unconfigured; reachable with provisioned creds
- [ ] **T12 (P2, human: ~1h / CC: ~10min)** — I1 — Add prod-clone endpoint parity + sitemap/route-count gate + doc/ops parity to acceptance
  - Surfaced by: Code Quality I6-cq + Outside voice OV3
  - Files: I1 acceptance, SEO gate script, `CLAUDE.md`, `start.sh`, `build-image.sh`
  - Verify: truncated static build fails the gate; docs reference Django commands
- [ ] **T13 (P3, human: ~5min / CC: ~2min)** — X4 — Correct dependency edge: blocked-by F2 **+ S2**
  - Surfaced by: Outside voice — OV3 (dependency graph wrong)
  - Files: this plan + orchestrator config
  - Verify: X4 not started before S2 merges

_No new tasks deferred to TODOS — every finding was folded into the plan._

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | not run |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | issues_found | 10 raised; 1 critical miss (S7), 8 hardening folded in, 1 rejected (gunicorn) |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | issues_open | 9 issues (4 arch, 2 cq, 1 test, 1 perf, +S7); all resolved, 1 user-accepted critical gap |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | n/a (backend rewrite) |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | not run |

- **CODEX:** 10 findings; surfaced the critical missing Results API slice (now S7) plus 8 hardening items folded into the plan; gunicorn-drop rejected by user (OV2=B).
- **CROSS-MODEL:** one tension (process model) — user kept gunicorn over Codex's objection. All other Codex findings were additive (no Claude/Codex disagreement) and accepted.
- **UNRESOLVED:** 0 decisions unresolved. 1 critical gap (I1 big-bang cutover, no automated rollback) is **explicitly accepted by the user** at the Step 0 scope gate — recorded in `## Failure modes`, not re-litigated.
- **VERDICT:** ENG review complete, all 11 findings resolved and folded into the task plan (13 → 14 tasks; new S7; X4 dependency corrected; F1/F2/F3/S4/S6/X2/X3/I1 hardened). NOT auto-CLEARED because of the user-accepted no-rollback critical gap — this is a deliberate scope choice, not an open issue. Eng review required gate is satisfied for planning; proceed to implementation when ready.
