# Race calendar + per-race pages

<!-- Approved design: variant C (Map + List).
     Mockup: ~/.gstack/projects/k-ivanov-bgx-leaderboard/designs/race-calendar-20260506/variant-C-map.html -->

## Context

The dashboard answers "how is rider X doing" and "what are the standings for season Y," but has no surface that answers "which races happen this year, where, and when?" Today's user has to dig into `/results?season=2026&category=expert` and infer the calendar from the race buttons. Bookmarking a single race or sharing it on Facebook is also ad-hoc.

This adds:
1. A `/races` page that shows every race in the current season with a stylized map + scrollable list (variant C from /design-shotgun on 2026-05-06).
2. A per-race page at `/races/{slug}` with a short description, key facts, a Facebook-event CTA, and links into the leaderboard / per-category results.

Today is 2026-05-06; 2 of 7 races are done, the next is Карнаре on 23 May. The page must visually distinguish past / next / upcoming.

## URL surface

```
/races                       → calendar view for the current season
/races/{race-slug}           → per-race detail page (one HTML per slug, SSG)
```

The `/races` page redirects implicit `?season=2026` from `/races` so a clean canonical URL is `/races` for the current year. A `?season=2025` query param shows past seasons (same template).

Existing `/{year}/events` and `/{year}/events/{slug}` legacy URLs already 301 to nothing useful per `app/redirects.py` — extend the redirect router so they 301 to `/races?season={year}` and `/races/{slug}` respectively, preserving any existing search-engine equity.

## Schema additions

`Event` gets two optional fields:

| Field | Type | Purpose |
|---|---|---|
| `facebook_event_url` | `VARCHAR(255) NULL` | Direct link to the FB event page. Populated where the organizer publishes one. Null = no FB link, button hides. |
| `description` | `TEXT NULL` | 2–4 sentences of human prose about the race. Track length, terrain, registration deadline, etc. Null = no description, page falls back to a default per-event-type blurb. |

Migration `0007_event_facebook_and_description.py` — additive, nullable, no data loss.

Where the values come from: the seed CSVs don't carry these fields, so a separate edit path is needed. Two options (pick during implementation):
- (a) **Admin UI** — extend SQLAdmin `/admin` to expose Event with editable fields. User edits inline. (Best UX, cheap.)
- (b) **YAML overlay** — a `seed_data/_events.yaml` file keyed by `(year, slug)` with FB URLs + descriptions, applied during `seed_all`. (Reproducible from git, but slower edit cycle.)
- Default: **(a)**. SQLAdmin is already mounted; one new view is ~10 lines.

## Critical files

| File | Action |
|---|---|
| `backend/alembic/versions/0007_event_facebook_and_description.py` | NEW — migration adding the two columns |
| `backend/src/db/models.py` | Modify — add `facebook_event_url`, `description` to `Event` |
| `backend/app/schemas/common.py` | Modify — add the two fields to `EventRef` (or split into `EventRef` + `EventDetailRef` if EventRef gets too heavy on existing pages) |
| `backend/app/api/events.py` | Modify — `/api/seasons/{year}/events` already exists; just confirm it returns the new fields. Already uses EventRef so should be automatic. |
| `backend/app/admin.py` | Modify — register an `EventAdmin` view exposing the editable fields |
| `frontend/src/pages/races.astro` | NEW — `/races` page. Astro shell + Vue island for the map+list interaction. |
| `frontend/src/pages/races/[slug].astro` | NEW — per-race page (SSG, one HTML per slug per season; getStaticPaths from the API). |
| `frontend/src/components/RaceCalendarView.vue` | NEW — `client:only="vue"` island. Reads season from URL, fetches events, renders map + list with the inline expand interaction. |
| `frontend/src/components/RaceMapBulgaria.astro` | NEW — the Bulgaria silhouette SVG. Static, accepts a `pins` prop with `(slug, x, y, status)`. |
| `frontend/src/lib/copy.ts` | Add — `races` namespace (existing `races` and `raceOverview` namespaces are for legacy patterns; verify or extend). |
| `backend/app/redirects.py` | Modify — add 301s from `/{year}/events` → `/races?season={year}`, `/{year}/events/{slug}` → `/races/{slug}` |
| `frontend/src/pages/rider/[slug].astro` | (later) Replace race-name plain text in career table with link to `/races/{slug}` |

## Map coordinates

Pin positions are hardcoded in `RaceMapBulgaria.astro` keyed by event slug. Variant C uses approximate-but-recognizable Bulgarian geography:

| Slug pattern | x | y | Note |
|---|---:|---:|---|
| `buhovo` | 120 | 170 | Sofia outskirts |
| `kyrnare` / `karnare` | 240 | 190 | Karlovo region |
| `alba-damascena` | 290 | 210 | Kazanlak |
| `kornica` | 155 | 265 | Pirin |
| `stara-zagora` / `stara_zagora` | 320 | 240 | central-south |
| `kirkovo` | 380 | 275 | south-east |
| `bansko` | 165 | 280 | south-west |
| `gorna-malina` / `gorna_malina` | 175 | 175 | east of Sofia |
| `sopot` | 215 | 195 | central north |
| `varna` | 425 | 175 | coast |
| `botevgrad` | 175 | 165 | north-west of Sofia |
| `sevtopolis` | 285 | 215 | Kazanlak area |

Slugs not in this table get a fallback pin in the center of the map with a `?` label so the page never breaks for new locations.

## Per-race page anatomy

```
┌─────────────────────────────────────────────────────────────┐
│ HERO                                                         │
│  R3 · 23 МАЙ 2026                                            │
│  КЪРНАРЕ 2026                                                │
│  📍 Карнаре, Пловдивско · ⏱ Старт 09:30 · ✓/⏳ status pill  │
│                                                              │
│  [Description prose, 2-4 sentences]                          │
│                                                              │
│  [📘 Facebook събитие]  [Виж класирането →]                  │
├─────────────────────────────────────────────────────────────┤
│ RESULTS BY CATEGORY (if race is past)                       │
│  Per-category links → /results?race={slug}&category=…        │
├─────────────────────────────────────────────────────────────┤
│ NAV: Prev race · Next race                                   │
└─────────────────────────────────────────────────────────────┘
```

For past races, surface the top-3 of every category that ran. For upcoming races, surface only the meta + FB CTA.

## Tasks

### 1. Schema + migration

- [ ] Add `facebook_event_url` and `description` to `Event` model
- [ ] Generate migration `0007_event_facebook_and_description`
- [ ] Apply locally; verify column added

### 2. API surface

- [ ] Confirm `EventRef` carries the new fields after Pydantic regen (it should, via `from_attributes=True`)
- [ ] Verify `/api/seasons/{year}/events` returns the new fields end-to-end
- [ ] If splitting EventRef vs EventDetailRef: do that now to avoid bloating standings responses

### 3. SQLAdmin editing

- [ ] Register `EventAdmin` in `backend/app/admin.py` exposing `name`, `slug`, `event_date`, `location`, `facebook_event_url`, `description`
- [ ] Verify on `/admin` that the form saves correctly

### 4. Map component

- [ ] `RaceMapBulgaria.astro` — SVG silhouette, pin-positions table, status-based styling (filled/outlined/pulsing)
- [ ] Accepts `pins: { slug, x, y, status, label }[]` and a `selected: slug | null` prop
- [ ] Pin click emits an event the parent island handles (via plain DOM custom event, since the map is an Astro static component and the parent is a Vue island — use `client:load` or pass interactivity through a small Vue wrapper)

### 5. /races page

- [ ] `frontend/src/pages/races.astro` — Astro shell, mounts `RaceCalendarView` as `client:only="vue"`
- [ ] `RaceCalendarView.vue` — reads `?season=` (default to current year), fetches `/api/seasons/{year}/events`, computes status (past/next/future) from `event_date` vs today, renders the map + list with inline expansion
- [ ] Empty state: "Все още няма насрочени състезания за {year}."

### 6. /races/{slug} page

- [ ] `frontend/src/pages/races/[slug].astro` — SSG, `getStaticPaths` enumerates all (year, slug) combos
- [ ] Hero section, FB CTA when URL is set, fallback when null
- [ ] For past races: list categories that ran with links to `/results?season={y}&category={c}&race={slug}`
- [ ] For upcoming: hide the results section, show "Регистрация / стартов лист" placeholder if data permits

### 7. Microcopy

- [ ] Extend or replace the existing `races` and `raceOverview` namespaces in `copy.ts` with the new vocabulary (`statusUpcoming`, `statusNext`, `statusCompleted`, `fbCta`, `viewLeaderboard`, `noFbEvent`, etc.)

### 8. Redirects

- [ ] Add 301 from `/{year}/events` → `/races?season={year}`
- [ ] Add 301 from `/{year}/events/{slug}` → `/races/{slug}`
- [ ] Pin in `tests/test_redirects.py`

### 9. Tests

- [ ] Backend: contract test for `/api/seasons/2026/events` showing the new fields when populated and null when not
- [ ] Frontend: manual QA at `localhost:4321/races` and `/races/buhovo` for both populated and null FB URL cases

### 10. Rider profile + race linking

- [ ] In the rider career table, the per-event row already links to `/results?...` — add a separate small "i" icon or link that goes to `/races/{slug}` so users can read about the race itself, not just its results

### 11. SEO

- [ ] Add `SportsEvent` JSON-LD on `/races/{slug}` (Tier 2 of the SEO plan — perfect fit for this page)
- [ ] Sitemap will pick up the new pages automatically via `build-sitemap.mjs`

### 12. Ship

- [ ] Backend tests green
- [ ] Astro build green (page count goes up by ~7 per season for race detail pages)
- [ ] Push to main, redeploy
- [ ] Once live, populate FB URLs + descriptions via `/admin` for the 2026 races

## Out of scope

- Embedded Facebook feed widgets (heavy, we just link out)
- A registration form for upcoming races (organizer publishes via FB)
- Map pan / zoom interactivity (the SVG is decorative, not interactive)
- Per-race weather forecast (mockup showed it, dropping for v1)
- Track GPX / route map (would need additional data + tooling)

## Success criteria

- `/races` shows every event for the current season with correct status (past/next/upcoming) by date
- `/races/{slug}` exists for every event seeded, with at minimum: name, date, location, round, FB CTA when URL is set
- `/admin` lets the user edit `facebook_event_url` and `description` per event without writing SQL
- Variant-C visual fidelity: dark theme, Oswald headings, deep orange accent, map silhouette, pulsing pin on next race
- Legacy `/{year}/events*` URLs 301 to the new shape

## Approved mockup reference

`~/.gstack/projects/k-ivanov-bgx-leaderboard/designs/race-calendar-20260506/variant-C-map.html`

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 0 | — | — |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** NO REVIEWS YET — run `/autoplan` for full review pipeline, or individual reviews above.
