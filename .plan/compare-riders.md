# Rider comparison

## Context

Today the dashboard answers "how is one rider doing." It does not answer
"how does this rider stack up against that one." Two riders' profile pages
sit side-by-side in two browser tabs and the user does the math in their
head — career totals, head-to-head matchups, who beat whom in races they
both ran. We can do that math and present it.

This adds a comparison feature with two entry points (a "Compare with…"
button on `/rider/{slug}`, and a standalone `/compare` page that picks both
riders from scratch). The comparison view shows a stats card on top
(career numbers side-by-side) and a head-to-head table below (only races
both riders entered, with positions / times / a winner column).

No category restriction — allow any two riders to be compared. Domain is
permissive on purpose: the user knows what they're looking at, and an
"expert vs women's-category" comparison is sometimes exactly what someone
wants to see.

## URL + routing

```
/compare                       → empty-state page with two search inputs
/compare?a={slug-a}&b={slug-b} → rendered comparison view
```

Query params instead of path params (`/compare/{a}/{b}`) because Astro's
static build would otherwise need `getStaticPaths` over a 882×882 = 778k
slug cartesian product. Query params keep the build to one HTML file and
all logic happens client-side in a Vue island.

The "Compare with…" button on `/rider/{slug}` navigates to
`/compare?a={current}&b={selected}` once a second rider is picked.

## Data flow

No new backend endpoint. The Vue island fetches `/api/riders/career?slug=…`
twice (once per rider) and composes the comparison client-side:

- **Stats card** — read straight from each `RiderCareerOut` response.
- **Head-to-head table** — intersection of `seasons[*].results[*].event_slug`
  across both riders. For each shared event, render side-by-side.

The career endpoint already returns everything needed (per-season
totals, per-event positions, points, slugs). No backend work.

## Critical files

| File | Action |
|---|---|
| `frontend/src/pages/compare/index.astro` | NEW — empty-state page (logo + two search boxes + tagline) |
| `frontend/src/components/CompareView.vue` | NEW — `client:only="vue"` island; reads `?a&b`, fetches both careers, renders stats + head-to-head |
| `frontend/src/components/CompareSearch.vue` | NEW — search dropdown identical to `RiderSearch.vue` but accepts a callback prop instead of navigating; used twice on the empty-state page and once on the rider profile |
| `frontend/src/pages/rider/[slug].astro` | MODIFY — add "Compare with…" button next to the page title; mounts a `CompareSearch` island that navigates to `/compare?a={current-slug}&b={selected-slug}` on pick |
| `frontend/src/lib/copy.ts` | ADD — `compare.title`, `compare.searchA`, `compare.searchB`, `compare.empty`, `compare.headToHead`, etc. |
| `frontend/src/lib/api.ts` | OPTIONAL — small helper `getCompareCareers(a, b)` that fans out two parallel `getRiderCareer` calls |

## View anatomy

### Empty state — `/compare`

```
┌──────────────────────────────────────────────────────┐
│  Сравнение на състезатели                            │
│  Изберете два състезателя за съпоставка              │
│                                                       │
│  [ Search box A ]   срещу   [ Search box B ]         │
└──────────────────────────────────────────────────────┘
```

Once both are picked → navigate to `/compare?a=…&b=…`. Single search
populated → keep on `/compare`, prompt for the other.

### Comparison view — `/compare?a=…&b=…`

```
┌────────────────────────────────────────────────────────────────┐
│  Сравнение                                                      │
│                                                                  │
│  ┌──────────────────────────┐    ┌────────────────────────────┐│
│  │ Илиян Кръстев  #169     │    │ Стефан Делев  #44          ││
│  │ Експерт · 2024, 2025    │    │ Експерт · 2025              ││
│  │ Сезони:           2     │    │ Сезони:           1          ││
│  │ Стартове:         8     │    │ Стартове:         4          ││
│  │ Финиша:           5     │    │ Финиша:           3          ││
│  │ Най-добро:        15-и  │    │ Най-добро:        24-и       ││
│  │ Точки общо:       12    │    │ Точки общо:       0          ││
│  └──────────────────────────┘    └────────────────────────────┘│
│                                                                  │
│  Лице в лице · 3 общи състезания                               │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ Състезание         │ Кръстев   │ Делев     │ Победител │  │
│  ├──────────────────────────────────────────────────────────┤  │
│  │ Алба Дамасцена 2025│ 22-и · — │ 24-и · — │ Кръстев   │  │
│  │ Кърнаре 2025       │ DNF      │ 30-и · — │ Делев     │  │
│  │ Стара Загора 2025  │ DNF      │ DNF       │ —          │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Резултати: Кръстев 1 · Делев 1 · Равно 1                      │
└────────────────────────────────────────────────────────────────┘
```

When the intersection is empty: replace the head-to-head table with a
single line — "Тези двама състезатели не са се срещали в едно
състезание."

## Tasks

### 1. Backend — none

The `/api/riders/career` endpoint already returns enough data. Verify
once with `curl /api/riders/career?slug=мартин-маринов` against local.

### 2. CompareSearch.vue (new)

- [ ] Copy the dropdown UX from `RiderSearch.vue` — debounced search
  via `/api/riders/search`, arrow-key nav, Enter to select, Esc to
  close.
- [ ] Replace the navigation behavior with a `@select` event emit so
  callers decide what to do with the picked rider.
- [ ] Used in three places: rider profile button, compare empty-state
  search A, compare empty-state search B.

### 3. /compare page + CompareView.vue (new)

- [ ] `frontend/src/pages/compare/index.astro` — Astro shell, mounts
  `CompareView` as `client:only="vue"`. SEO title + description in
  `copy.ts`.
- [ ] `CompareView.vue` reads `URLSearchParams` for `a` and `b`:
  - both empty → render two `CompareSearch` islands with "vs"
    between them. On both selected, push to history `?a=…&b=…` and
    re-trigger the rendering branch.
  - one populated → show that rider's name + a single CompareSearch
    asking for the other.
  - both populated → fetch both careers in parallel, render stats
    card + head-to-head table.
- [ ] Loading state, 404 state (one of the slugs doesn't exist),
  empty intersection state.

### 4. Stats card

- [ ] Reusable `<RiderStatsCard rider={career} />` component or just
  inline JSX. Stats from `RiderCareerOut`:
  - Categories per season (e.g. "Експерт · 2024, 2025")
  - `seasons.length` → "Сезони"
  - `sum(season.races_participated)` → "Стартове"
  - `sum(season.results.filter(r => r.position !== null).length)` →
    "Финиша" (real finishes, not imputed)
  - `min(season.best_position)` ignoring nulls → "Най-добро"
  - `sum(season.total_points)` → "Точки общо"

### 5. Head-to-head table

- [ ] Compute intersection: `Set(A.events) ∩ Set(B.events)` keyed on
  `event_slug` + `season_year` (since two events with the same slug
  but different years are different events).
- [ ] For each shared event, render: event name, A's
  (position, time, status), B's (position, time, status), winner
  cell.
- [ ] Winner rules:
  - Both have explicit positions → lower position wins.
  - One has explicit position, the other DNF → finisher wins.
  - Both DNF / DNS → "—" (tie).
- [ ] Summary line: "Резултати: A {x} · B {y} · Равно {z}".

### 6. Rider profile entry point

- [ ] Add a "Сравни с…" button next to the rider name on
  `/rider/{slug}.astro`. Clicking opens a `CompareSearch` overlay
  (similar to nav search, anchored under the button).
- [ ] On select, `window.location.href = /compare?a={current}&b={picked}`.

### 7. Microcopy + nav

- [ ] All Bulgarian strings live in `copy.ts` under a new `compare`
  namespace. No inline strings in components.
- [ ] No nav-bar entry for /compare in v1. The two entry points
  (rider profile + direct URL) are enough; nav is already crowded.
- [ ] Add `<a href="/compare">Сравнение</a>` to the footer once the
  feature is shipped, for discoverability. (Optional, can be a
  follow-up.)

### 8. Tests

- [ ] No backend tests (no backend change).
- [ ] Manual QA on local dev: pick two riders that share races,
  verify the head-to-head table; pick two that don't, verify empty
  state; pick a slug that doesn't exist, verify 404 state.
- [ ] If we add the optional `getCompareCareers` helper, a tiny unit
  test that asserts both fetches fan out in parallel.

### 9. Ship

- [ ] Land `feature/compare-riders` → `main` via merge or fast-forward.
- [ ] Push to main → GHA release.yml builds → `railway redeploy --from-source --yes`.
- [ ] Hard-refresh, click through the flow on prod.

## Out of scope

- Chart visualizations (bar charts, line charts of points-over-time).
  The first cut is tabular only.
- More than two riders at once. Pairwise only.
- Cross-season analytics ("how each rider has improved year over year"
  shown in the comparison context — that's already on each rider's
  profile page).
- Sharing-friendly OG cards per comparison URL. Static OG is fine; can
  follow up if comparisons get shared a lot.
- Saved / favorited comparisons.
- A nav-bar entry for /compare (deferred to follow-up; footer link
  only at first).

## Success criteria

- From any rider profile, "Сравни с…" + pick → loads a comparison view in ≤ 2 clicks.
- From the homepage, /compare loads, accepts two picks, navigates to the comparison view.
- Head-to-head table is correct on a manually-verified pair.
- Empty intersection renders friendly Bulgarian copy, not an empty `<table>`.
- Bundle size impact stays under +20 KB JS gzip (CompareView is the only new island).

## Open questions

1. **Layout density on mobile** — stats card + head-to-head table will be
   tight on a phone. Stack vertically on narrow screens (stats card A,
   stats card B, then table). Decide while implementing; not blocking.
2. **Should the head-to-head row link to the per-race results page?**
   Cheap to add. Default: yes — clicking a row navigates to
   `/results?season=…&category=…&race=…`. Confirm during implementation.
3. **Search exclusion** — when the user is on the rider profile and
   opens "Сравни с…", should the dropdown EXCLUDE the current rider from
   results so they can't compare a rider with themselves? Default: yes,
   filter client-side. Trivial.
