# Frontend restructure — single results page + multi-season rider profile

_Generated 2026-04-26._

This plan turns the multi-page leaderboard into a **single results page** driven by URL query params, plus a **standalone rider profile** route for the cross-season history. Companion to `.plans/p0-p4-detailed.md`.

## Owner intent (verbatim)

> Landing page = "Резултати" button → main results page.
> Main results page = current season's general ranking by default; dropdown switches season; race buttons filter to a single race; staying on the same URL (filters as query params) so a rider click opens a new page with full multi-season history.

## Final URL shape

| Route | Renders | State source |
|---|---|---|
| `/` | Welcome + single CTA "Резултати" → `/results` | static |
| `/results` | Standings or race results for a (season, category, race?) tuple | `?season=`, `?category=`, `?race=` query params |
| `/rider/<slug>` | Multi-season profile for one rider, newest→oldest | path param |
| `/stats` | Unchanged (auth-gated dashboard) | — |

Old per-season routes (`/2025/expert`, `/2025/r/255/димитър-тинчев`, etc.) become **301 redirects** to the new shapes — the CLAUDE.md invariant "Existing URLs are preserved" is honored via redirects, not by keeping the routes.

## Architectural decisions

1. **`/results` is a static shell + Vue SPA island.** One Astro page builds; the Vue island reads/writes query params via `history.pushState` and renders everything client-side. Pros: instant filter changes without a page reload, single shareable URL. Cons: no SSG-rendered standings (acceptable per stated UX — instant filter swaps win). The rider profile pages (T5) absorb the long-tail SEO instead.

2. **`/rider/<slug>` is SSG.** One pre-built page per rider slug (`getStaticPaths` enumerates from `/api/seasons/*/riders`). Static HTML for SEO + instant first paint. The already-built `getRiderCareer` endpoint feeds it.

3. **Query params are the source of truth.** The Vue island never holds state outside the URL — every change goes through `history.pushState({}, '', '?…')` so the back button + bookmarks + Slack-paste all work.

4. **No client-side router.** Just `pushState` + a `popstate` listener inside the island. Adding @vue/router for one route is over-spec.

5. **Old URLs become redirects** at the FastAPI layer so the frontend doesn't need a routing dance: `app.main` registers `RedirectResponse` handlers for the legacy patterns and FastAPI handles them before StaticFiles. Example: `/2025/r/255/димитър-тинчев` → `/rider/димитър-тинчев`.

## Out of scope

- `/[year]/events` and `/[year]/events/{slug}` — race calendar pages. They get redirected to `/results?season=&race=`.
- `/[year]/[category]/[eventSlug]` — old race-result page. Redirected.
- `/[year]/r/[raceNumber]` — disambiguation page. Disappears (the new `/rider/<slug>` matches by slug only; race number lives in the rider's per-season meta).
- `/stats` — untouched.
- Mobile-specific layouts — covered separately under `improvements.md` P3 #19.

---

## Tasks

Each task is self-contained: an agent can take any one of them, finish it on its own branch, and ship a commit. Dependencies are listed where they exist.

### T1 — Backend: confirm the standings + race-results endpoints are sufficient

**Why.** The new results page needs both season-level standings AND per-race results from the same UI. Today they live at `/api/seasons/{y}/standings/{cat}` and `/api/seasons/{y}/categories/{cat}/events/{slug}` respectively. Verify the response shapes are everything the island needs; do NOT add a `?race=` filter to standings — the response shapes legitimately differ (standings carry totals; race results carry times/laps).

**Files.** None.

**AC.** Smoke-curl both endpoints for an arbitrary (season, category, race) and confirm the JSON has every field the island needs. If anything's missing, file a follow-up task; do not fold it into T1.

**Effort.** S (~15 min reading).

---

### T2 — Backend: redirect legacy URLs to the new shapes

**Why.** Honor "URLs are preserved" without keeping the static pages.

**Files.**
- `backend/app/redirects.py` (new) — small module returning a list of route patterns + handlers.
- `backend/app/main.py` — register the redirect routes BEFORE StaticFiles (mount-order rule).
- `backend/tests/test_redirects.py` (new) — assert each legacy path returns 301 with the right `Location`.

**Specs.**

| Legacy | New | Notes |
|---|---|---|
| `/{year:int}` | `/results?season={year}` | year landing |
| `/{year:int}/{category}` | `/results?season={year}&category={category}` | leaderboard |
| `/{year:int}/{category}/{slug}` | `/results?season={year}&category={category}&race={slug}` | race results |
| `/{year:int}/events` | `/results?season={year}` | race list (absorbed) |
| `/{year:int}/events/{slug}` | `/results?season={year}&race={slug}` | race detail |
| `/{year:int}/r/{race_number}/{slug}` | `/rider/{slug}` | rider profile (race_number dropped — slug is unique) |
| `/{year:int}/r/{race_number}` | (404) | disambig page is removed |

**AC.**
- `curl -I http://localhost:5001/2025/expert` → `301`, `Location: /results?season=2025&category=expert`.
- All seven mappings have a passing test.
- `make seed-new` + Astro dev server still serve fine — no path collision with the new shell at `/results` or `/rider/{slug}` (StaticFiles wins for those because they exist as files).

**Effort.** M.

---

### T3 — Frontend: new landing page with single CTA

**Why.** Strip the welcome page back to one obvious next action.

**Files.**
- `frontend/src/pages/index.astro` — replace the existing dense layout with: H1 + lead paragraph + big "Резултати" button → `/results`.
- `frontend/src/lib/copy.ts` — add `home.cta = 'Резултати'`.

**Design notes.**
- Keep the hero logo (it's the brand).
- Drop the season cards (the user explicitly wants a single CTA — choosing happens on the results page).
- Keep the "Какво ще намерите тук" bullets if you want texture; one screen-height total is the target.

**AC.**
- `/` shows H1, lead, hero logo, bullets (optional), and one prominent button labeled "Резултати".
- Button has `href="/results"`.
- No second CTA, no season picker on the landing.

**Effort.** S.

---

### T4 — Frontend: new `/results` page (Vue SPA island)

**Why.** Single page, query-param driven, instant filter swaps without a reload.

**Files.**
- `frontend/src/pages/results.astro` — thin shell: BaseLayout + `<ResultsView client:only="vue" />`. Build-time fetches the season list once and passes it as a prop so the dropdown renders without a round-trip.
- `frontend/src/components/ResultsView.vue` (new, ~250 LOC) — owns all interactivity.
- `frontend/src/lib/copy.ts` — add `results.*` strings.

**State (in URL).**
- `season` — string year, e.g. `2025`. Default = latest season's year.
- `category` — string code, e.g. `expert`. Default = first category in that season.
- `race` — string slug, optional. When present, render race results; when absent, render standings.

**Component layout.**
```
[ Season dropdown ▾ ]   (top of page)
[ ПРОФИ | ЕКСПЕРТ | … ] (category tabs)
[ Генерално класиране | R1 Kyrnare | R2 Buhovo | … ] (race buttons; first selected when ?race is absent)

<table>                 ← either standings or race-results table, depending on ?race
```

**Behavior.**
- On mount: parse current URL params; fill defaults for any missing; if defaults were filled, `replaceState` (NOT `pushState` — first load shouldn't add a history entry).
- On any selector change: update params, `pushState`, re-fetch.
- On `popstate`: re-parse + re-render.
- Loading state: skeleton rows for the table while fetching.
- Error state: friendly empty message with retry button.
- Each rider row: link to `/rider/<slug>`. Render as a real `<a href="…">` so right-click + ctrl-click work; `@click.prevent` is NOT used here (we want a full navigation to the rider page).
- Each race button: real `<a href="…">` with the new full URL. Use `@click.prevent` here to stay on the same page and pushState.

**Data sources.**
- Season list: passed as a build-time prop (Astro→Vue) so the dropdown is interactive on first paint.
- Categories per season: fetched on season change via `api.getSeason(year)`.
- Standings: `api.getLeaderboard(year, category)` (existing).
- Race results: `api.getRaceResults(year, category, raceSlug)` (existing).
- Race list per season: derived from `getSeason(year).events`.

**AC.**
- Landing → click "Резултати" → URL becomes `/results`.
- Page renders standings for the latest season, default category, no race.
- Click another category → URL gains `?category=`, table swaps without a page reload.
- Click a race button → URL gains `?race=`, table swaps to race results.
- Click "Генерално класиране" → URL drops `?race=`, back to standings.
- Use the season dropdown → URL gains `?season=`, race button list refreshes, standings recompute.
- Hit back button → previous filter combination restored.
- Refresh the page on any URL → exact same state.
- A rider row click → opens `/rider/<slug>` in the same tab; ctrl/cmd-click opens a new tab.

**Effort.** L.

---

### T5 — Frontend: new `/rider/[slug]` page (SSG)

**Why.** Each rider gets one canonical URL holding their full multi-season history.

**Files.**
- `frontend/src/pages/rider/[slug].astro` (new). Uses `getStaticPaths` to enumerate every rider slug across every season (dedupe by slug — same rider in multiple seasons collapses to one path).
- `frontend/src/lib/copy.ts` — add `riderProfile.*` strings (some can be reused from existing `rider.*`).
- Delete `frontend/src/pages/[year]/r/[raceNumber]/[slug].astro` and `frontend/src/pages/[year]/r/[raceNumber]/index.astro` (covered by redirects in T2).

**Layout.**
1. Header card: race number (latest active season), full name, current team / bike. If the rider raced in multiple categories in the latest season, list them.
2. **Career** table — every season the rider appears in, newest first, with totals + best position + category.
3. **Per-season detail** sections, newest first. Each section: a small sub-header ("Сезон 2025 · ЕКСПЕРТ · #255") and a table of all their results that season (event name, position, points, time).

**Data.**
- Build-time: `api.getRiderCareer(slug)` (already built — extended in T6) — gives both the career summary AND the per-season results in a single call.

**AC.**
- Every existing rider has a `/rider/<slug>` page (build emits ~600+ pages).
- Newest season is at the top.
- Career table shows even seasons where the rider scored 0 points (for completeness).
- A click on any race name in the per-season detail jumps to `/results?season=<year>&category=<cat>&race=<slug>`.
- Old URLs (`/2025/r/255/димитър-тинчев`) 301-redirect here.
- Page title + meta description mention the latest active category for SEO.

**Effort.** L.

---

### T6 — Backend: extend `RiderCareerOut` with per-season results

**Why.** Save the rider page from N round-trips (one per season). Today the career endpoint returns one summary row per (season, category); add the underlying per-event rows so the frontend renders everything from one call.

**Files.**
- `backend/app/schemas/riders.py` — `RiderCareerSeasonOut` gains `results: list[RiderResultOut]`.
- `backend/app/api/riders.py::get_rider_career` — populate `results` from the `EventResult` rows already loaded (no extra DB query if you add `selectinload(Rider.results)` and join through to `Event` + `Category`).
- `backend/tests/test_riders_career.py` — new test asserting the `results` array is present and ordered by `event.sort_order`.

**AC.**
- `GET /api/riders/career?slug=…` response shape grows; existing fields unchanged.
- Each season row's `results` is sorted by `event.sort_order`.
- All existing `test_riders_career.py` tests still pass.
- Frontend type regen (`make types`) picks up the new field.

**Effort.** M.

---

### T7 — Frontend: rider search redirects to `/rider/<slug>`

**Why.** The Nav search island today links to `/[year]/r/[raceNumber]/<slug>`; that route is going away.

**Files.**
- `frontend/src/components/RiderSearch.vue` — change `navigateTo` from `/${season_year}/r/${race_number}/${slug}` to `/rider/${slug}`.

**AC.**
- Typing "тинч" + Enter on the first result navigates to `/rider/димитър-тинчев`.
- Search still works on every page including `/results`.
- The race-number badge in the dropdown stays (helpful for visual disambiguation) — only the destination URL changes.

**Effort.** S.

---

### T8 — Frontend: post-build sitemap reflects the new URL space

**Why.** `/results` is one URL but renders thousands of permutations. The sitemap should list `/`, `/results`, `/stats`, every `/rider/<slug>` — and NOT the legacy URLs (which redirect now).

**Files.**
- `frontend/scripts/build-sitemap.mjs` — already walks `dist/`. After T5 the rider pages are static so they're picked up automatically. After T2 the legacy pages no longer exist in `dist/` (they redirect, not serve), so they're naturally excluded. Add an assertion: total URL count should drop dramatically.

**AC.**
- `dist/sitemap.xml` contains `/`, `/results`, `/stats`, every `/rider/<slug>`.
- Total URL count drops from ~1800 to ~700 (one per unique rider, plus a handful of fixed pages).
- `/2025/expert` is NOT in the sitemap.

**Effort.** S.

---

### T9 — Tests: route + redirect coverage

**Why.** Belt-and-braces — the URL contract is now load-bearing for SEO + bookmarks.

**Files.**
- `backend/tests/test_redirects.py` (created in T2).
- `frontend/tests/` — Astro doesn't ship a frontend test runner here. Skip unless you want to add one (out of scope).

**AC.**
- Full `pytest -q` passes (currently 89 tests; this adds ~7).
- Manual smoke checklist:
  - `/` → click "Резултати" → `/results`
  - `/results` defaults to latest season + first category, no race
  - Switch season → URL has `?season=…`
  - Switch category → URL has `?category=…`
  - Click race → URL has `?race=…`
  - Click "Генерално" → URL drops `?race=`
  - Back button → previous state restored
  - Click rider → `/rider/<slug>` opens (same tab)
  - Old `/2025/expert` → 301 → `/results?season=2025&category=expert`
  - Old `/2025/r/255/димитър-тинчев` → 301 → `/rider/димитър-тинчев`

**Effort.** M.

---

### T10 — Docs: update CLAUDE.md and README

**Why.** Architectural invariants change. CLAUDE.md needs the new URL map. README needs a paragraph explaining the new flow so future contributors don't try to add another `/[year]/...` route.

**Files.**
- `CLAUDE.md` — replace invariant #3 ("Existing URLs are preserved") with the new shape + redirect note. Add a section "URL contract" with the table from this plan.
- `README.md` — refresh the routes line ("~700 URLs" instead of "~1800"). Mention the SPA-style results page.
- `.plan/refactor-plan.md` and `.plan/eng-review.md` — leave alone (historical).

**AC.**
- CLAUDE.md table matches the actual route map.
- README's project-layout section reflects the new pages.

**Effort.** S.

---

## Suggested execution order

1. **T1, T6** (backend prep — additive only, no breaking changes).
2. **T2** (redirects — lands before the frontend pages move; users on legacy URLs immediately bounce).
3. **T3** (landing — trivial, low-risk).
4. **T4** (results page — the big one).
5. **T5** (rider page — depends on T6).
6. **T7** (search wiring).
7. **T8** (sitemap).
8. **T9** (tests).
9. **T10** (docs).

Branch suggestion: feature branch `feature/url-restructure`, commit per task, single PR at the end.

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Search engines hit the old URLs and lose ranking. | 301 redirects preserve link equity. Sitemap (T8) tells them about the new shape. |
| Users have bookmarks to `/2025/expert/buhovo`. | Same redirects handle them. |
| `/results` ships zero pre-rendered HTML so SEO for category standings is hurt. | Acceptable — the rider profile pages absorb the long-tail SEO (one per rider, full content). The general `/results` page is more like an app than a content page. |
| The Vue island grows beyond ~250 LOC. | Split into `<SeasonDropdown>`, `<CategoryTabs>`, `<RaceButtons>`, `<ResultsTable>` sub-components. |
| Astro `getStaticPaths` for `/rider/[slug]` enumerates every rider across every season — duplicates. | Dedupe by slug in the path-collection step (the existing `[year]/r/[raceNumber]/[slug]` does this with a `Set`). |
| Filter combinations the island doesn't anticipate (e.g., `?race=foo` without `?category=`). | On mount, validate every param; missing or invalid ones get filled with defaults and `replaceState`. Document the precedence in the island's docstring. |
| The Astro dev server caches `getStaticPaths` for the new rider page; adding a rider via `make seed-new` won't surface until restart. | Document the restart step in CLAUDE.md (already documented for the existing pages). |

## Open questions for the owner

(None blocking — the plan picks defaults. List here so they can be flipped without re-planning.)

1. **Race button label** — current term is "Генерално класиране" (per `copy.ts`). Stays the same?
2. **Race button order** — currently chronological by `Event.sort_order`. Keep that, or reverse-chronological (latest race first)?
3. **Category default when switching seasons** — when a season is picked and no `?category=` is in the URL, should the category default to the season's first category, or carry over from the previous season's selection? Plan picks the latter (sticky) for less friction; flip to the former if you prefer predictability.
4. **Rider profile sort within a season** — events newest-first or by `sort_order`? Plan picks `sort_order` (matches the leaderboard).
5. **Mobile behavior of race buttons** — currently they wrap. With the new SPA, consider a horizontal scroll strip with a fade affordance. Plan keeps the wrap; revisit if it gets too tall on small screens.
