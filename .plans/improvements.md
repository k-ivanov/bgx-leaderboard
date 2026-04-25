# Improvements working plan

_Generated 2026-04-25._

A prioritized list of improvements after a sweep of every feature surface (backend API, frontend pages, admin, analytics, seeding, deploy). Items are grouped by **how much they hurt today** and tagged with a rough effort estimate (`S` <½ day, `M` ½–2 days, `L` >2 days).

The bug list at the top is the ship-blocking subset — everything else is roadmap work.

---

## P0 — Bugs / regressions to fix this week

| # | Item | Effort | Notes |
|---|---|---|---|
| 1 | **Backend test suite is broken** — 4 modules error at collection because `sqladmin` isn't in the venv. `pytest` returns "22 collected, 4 errors" instead of the 64 the README claims. | S | `pip install sqladmin` in `pyproject.toml` deps (or move sqladmin import behind a feature flag / lazy import inside `create_app`). Add `pytest --collect-only` to a CI step so this never silently regresses. |
| 2 | **Seed importer + dev server are not auto-synced.** A new race CSV in `seed_data/` does nothing until somebody runs `python -m scripts.import_race_day --file <csv>` AND restarts the Astro dev server (getStaticPaths cache). Caused the buhovo 2026 404. | S | Add `make seed-new` target that scans `seed_data/` for unseeded files, imports them, and HUPs the running Astro proc. Or have `import_race_day` write a sentinel file that Vite watches. |
| 3 | **2025 data is missing Six Days** (per `.reports/2025-validation-vs-hardendurobulgaria.com.md`). | M | Locate the official CSV (or scrape from hardendurobulgaria.com), fit the existing importer schema, drop into `seed_data/2025/`, re-seed. |
| 4 | **Some rider names contain time strings** (e.g. `"Георги ГЕОРГИЕВ 3:34:40.7"`) — bad CSV cells that the importer is accepting verbatim into `Rider.first_name + last_name`. | S | Defensive parser in `import_race_day._split_name`: reject any token matching `\d+:\d{2}:\d{2}` and route the time to `time_ms` instead, or surface a soft error so the human can fix the CSV. |
| 5 | **`/sitemap-index.xml` is referenced from `robots.txt` but doesn't exist** — Phase 4 deferred, but search engines hitting that URL get a 404 right now. | S | Either generate one as a post-build step (we have ~1600 routes; build a flat `sitemap.xml` in `scripts/build_sitemap.py`) or remove the line from `robots.txt` until the generator ships. |

## P1 — Production readiness

| # | Item | Effort | Notes |
|---|---|---|---|
| 6 | **No CI** — `.github/` doesn't exist. Every regression has to be caught by hand. | M | GitHub Actions: matrix of {pytest, npm run build, npm run typecheck, ruff/mypy}. Block PR merge on red. Cache uv + node_modules. |
| 7 | **No deploy gate** — `git push origin main` triggers Railway directly with no health-check wait. | S | Use Railway's "deploy on success" hook tied to the CI pipeline added in #6. Or add a `make deploy` target that runs tests, builds the image, then `railway up`. |
| 8 | **No alerting** — if `/api/track` starts returning 500, nobody knows. The proxy bug fixed this session went undetected for an unknown amount of time. | M | Either push to Sentry / Honeycomb (managed) or add a 3-line Railway logdrain rule that alerts on `5xx` rate > 1% over 5 min. |
| 9 | **Stats page only fetches on first mount.** Refresh requires a manual page reload. | S | Add `setInterval(load, 60_000)` to `StatsView.vue`, plus a "last updated" timestamp in the corner. |
| 10 | **No backup story for the visit-tracking DB.** `Visit` rows accumulate forever in Postgres and there's no rotation, no archive, no GDPR-style purge. | M | Cron job: `DELETE FROM visit WHERE timestamp < NOW() - INTERVAL '180 days'` (matches the analytics window). Optional: nightly `pg_dump` to S3-compatible storage. |
| 11 | **No CSP / security headers.** | S | Add `secure_headers` middleware in FastAPI: `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin`. Astro static HTML can serve `<meta>` fallbacks. |

## P2 — Data correctness / scoring

| # | Item | Effort | Notes |
|---|---|---|---|
| 12 | **Multi-day vs single-day points** — our import sums every day of a weekend; hardendurobulgaria.com (and possibly the official championship rules) only count day 1. | M | Decide: do we want an authoritative archive (current behavior) OR a faithful mirror of the official scoring? Preferred: keep both — store per-day, render with a `?day=1\|all` query param on the leaderboard. |
| 13 | **Drop-worst-race rule not implemented** for seasons with 7+ events. Official BGX rule discards each rider's worst result. | M | Add `championship_format='drop_worst_when_n_events:7'` enum and implement in `services/standings.py`. Existing `'per_event'` keeps current behavior. Configure per season in the admin panel. |
| 14 | **Per-event tiebreakers aren't documented or visible.** Two riders with the same total points are ordered by `id` today (incidental). | S | Document the tiebreaker (best position count → second best → … → race number ascending) in `services/standings.py` and add a unit test. |
| 15 | **Categories are duplicated per season.** A schema improvement would make `Category` a season-shared lookup with a many-to-many to `Season`. Today every season redeclares 7 rows. | L | Holdable — only worth it if you add a 4th+ season. |

## P3 — Frontend UX

| # | Item | Effort | Notes |
|---|---|---|---|
| 16 | **No rider search.** Visitors who know a name but not a race number have to scroll. | M | Top-nav search box → `/[year]/r/?q=...` Vue island that hits a new `/api/seasons/{year}/riders/search?q=...` endpoint. Fuzzy match on name + race number. |
| 17 | **No multi-season rider profile.** Once a rider page loads, you only see one season of their history. | M | Add a "career" tab on the rider page that aggregates results across every season they appear in. Backend: `/api/riders/by-name/{slug}` returning every `(season_year, race_number, results)` row. |
| 18 | **No "compare riders" view.** | M | `/[year]/compare?r=255&r=347` Vue island; pulls both standings rows and renders a side-by-side table. |
| 19 | **Tables overflow on mobile.** Existing `.scrollx` class works but the content density is brutal at 375px. | M | Per-table responsive collapse: hide low-priority columns under a sm breakpoint; make the rider name + total points always visible. |
| 20 | **No exportable standings.** Coaches and riders ask for CSV/PDF. | S | `Export ↓` link on every leaderboard → `/api/seasons/{year}/standings/{cat}.csv` (`?format=csv` query param). PDF can wait. |
| 21 | **No share affordances.** Race results pages don't have an OG image generator. | M | Build `/api/og/race/{year}/{slug}.png` that renders the podium + winner photo via Pillow or Playwright at request time. |
| 22 | **Stats page can't filter.** Only "last 30 days" and only the global aggregate. | S | Add `?from=YYYY-MM-DD&to=...&category=expert` to `/api/stats` and corresponding UI in the StatsView island. |
| 23 | **Dark theme has 7 unique tokens; light theme has 6.** They mostly mirror, but `--color-podium-bronze` is `#b45309` on light and `#f97316` on dark — different hues, not just brightness. Not necessarily wrong, just inconsistent with the "tokens flip on `.dark`" doc invariant. | S | Pick one convention and stick to it. Either make every token semantically paired, or document the deliberate divergences. |
| 24 | **Theme preference doesn't sync across devices.** Cookie only. | S | If user accounts ever land, push to server. For now, leave. |

## P4 — Developer experience

| # | Item | Effort | Notes |
|---|---|---|---|
| 25 | **README likely stale after the FastAPI refactor.** Last touched in Phase 1; the actual stack is now FastAPI + Astro, not FastHTML. | S | Sync `README.md` against the current `CLAUDE.md` + `.plan/refactor-plan.md`. |
| 26 | **No `make seed` shortcut for "import every CSV that's not yet in the DB"** — `seed_all` exists but does a wipe-and-rebuild by default. Risky on a dev DB with bookmarks/state. | S | Add `make seed-incremental` that diffs `seed_data/**/*.csv` against the `event_result` table by source filename and only imports new files. |
| 27 | **No OpenAPI docs in dev.** `/docs` returns 404 in prod (good for security) but it'd help local development. | S | Mount `app.openapi_url` only when `os.getenv('ENV') == 'dev'`. |
| 28 | **No Storybook / component gallery** for the Astro components — designers can't preview `PositionBadge`, `PointsPill`, etc. in isolation. | M | Add `pnpm dlx histoire@latest init` or a static `/_dev/components` page that imports every common component with sample props. Plan-deferred — only worth it if the component count grows past ~15. |
| 29 | **No type generation pipeline trigger** — `api.openapi.ts` is generated but the generator command (`npm run generate:api-types`) only runs by hand. Easy to ship out-of-sync types. | S | Add a pre-commit hook (or `make types`) that regenerates the file and fails if `git diff` is non-empty. |

## P5 — Privacy / compliance

| # | Item | Effort | Notes |
|---|---|---|---|
| 30 | **Visit tracking has no purge endpoint.** Even though visitor IDs are pseudonymous (daily-rotating salt), there's no "forget me" mechanism. | S | `DELETE /api/track/me` — derives the visitor_id from the request fingerprint and removes today's rows. (Useless without a cookie since the salt rotates daily, but worth documenting.) |
| 31 | **`session_id` derivation isn't documented in user-facing copy.** A privacy-aware visitor opening DevTools sees `session_id` in the POST payload and might wonder. | S | Footer link → `/privacy` static page explaining: no cookies, no localStorage, salt rotates daily, no IP stored. |
| 32 | **Admin password is `letmein` by default.** Fine for dev; the Makefile help line surfaces it. Make sure Railway env actually overrides — verify with a one-shot script. | S | Add a `make verify-prod-secrets` target that hits `/admin/login` with `letmein` against the prod URL and screams if it succeeds. |

## P6 — Nice-to-haves

| # | Item | Effort |
|---|---|---|
| 33 | Per-race podium photo support (file upload via /admin) | M |
| 34 | Rider profile pictures (file upload, served via Astro Image) | M |
| 35 | Season-end trophy / award ceremony page | M |
| 36 | Notifications: "your favorite rider scored" via web-push (requires service worker — breaks zero-JS baseline) | L |
| 37 | English UI toggle (i18n: currently Bulgarian only) | L |

---

## Suggested execution order

1. **Week 1**: P0 items 1, 2, 4, 5 (½ day each — clears the bug board).
2. **Week 1–2**: P0 #3 (locate Six Days CSV) + P1 #6 (CI). Both unblock everything downstream.
3. **Week 2**: P1 #9, #10, #11 (alerting can wait if traffic is still in the hundreds/day).
4. **Week 3**: P2 scoring decisions (#12–#14). These need a stakeholder call — what's the championship's actual scoring rule? Then implement.
5. **Week 4+**: pick one P3 UX item per release. The biggest visitor-impact wins are #16 (search), #17 (multi-season profile), #19 (mobile tables).

## What I deliberately did not include

- **Switch to SSR.** The static-output story is working. Don't abandon it because of one edge case.
- **Replace SQLAdmin.** It's ugly but functional. Custom admin is L+ effort for marginal gain.
- **Replace Postgres with something fancier.** Visits are <50/day right now. Postgres is the right tool for the next 100x.
- **Add a CDN.** Railway already fronts the static assets. Revisit when you have a global audience.
- **Adopt a frontend framework other than Astro + Vue islands.** The current setup ships ~0KB JS per non-stats page. Don't trade that away.

## Out of band — current session pickup items

- The dev backend is currently running with `STATS_PASSWORD=letmein ADMIN_PASSWORD=letmein`. To re-launch from scratch: `make dev-backend` (already configured to default to those values).
- `.reports/2025-validation-vs-hardendurobulgaria.md` is the source of truth for the data-correctness items above.
