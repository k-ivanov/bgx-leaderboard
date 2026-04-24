# BGX Navigation Dashboard — Project Reference

> Complete technical overview of the BGX Hard Enduro Championship dashboard.
> Covers what the project is, who uses it, every user-facing feature, the
> domain model, how the system is architected, the data pipeline, the full
> API, and how to operate + extend it.
>
> For quick start, see [`README.md`](README.md). For deploy ops, see
> [`DEPLOYMENT.md`](DEPLOYMENT.md). For project conventions, see
> [`CLAUDE.md`](CLAUDE.md). For planning context, see the [`.plan/`](.plan/)
> directory.

---

## Table of contents

1. [What it is](#1-what-it-is)
2. [Who uses it](#2-who-uses-it)
3. [Feature inventory — every page](#3-feature-inventory--every-page)
4. [Domain model](#4-domain-model)
5. [System architecture](#5-system-architecture)
6. [Data pipeline](#6-data-pipeline)
7. [URL scheme](#7-url-scheme)
8. [API reference](#8-api-reference)
9. [Frontend pages — anatomy + data flow](#9-frontend-pages--anatomy--data-flow)
10. [Operating the dashboard](#10-operating-the-dashboard)
11. [Development workflow](#11-development-workflow)
12. [Testing](#12-testing)
13. [Security + privacy](#13-security--privacy)
14. [Success metrics + rollback](#14-success-metrics--rollback)
15. [Roadmap](#15-roadmap)

---

## 1. What it is

**BGX Navigation Dashboard** is a public, read-only web application that
publishes results and standings for the **BGX Hard Enduro Championship** —
a Bulgarian hard-enduro motorcycle racing series.

It shows, per season:
- A **leaderboard** for each competitive class (category).
- The **race calendar** for the season (with each race's location, date, status).
- **Race results** per (race, category).
- A **profile page** for every rider that has competed.
- A private, auth-gated **analytics** page for visit metrics.

Every public URL is pre-rendered to static HTML at build time. No user login,
no comments, no content creation — just read-first content from the
championship's results data.

---

## 2. Who uses it

| Primary user | Typical task | Priority |
|---|---|---|
| Race fans | Check "who's winning Expert this year?" between races | Highest |
| Riders | Look up their own season arc and per-race placings | High |
| Event-day spectators | Check results on mobile right after a race | High |
| Race organizers / federation staff | Review uploaded results; confirm publication | Medium |
| Search engines (Google) | Index rider pages + leaderboards so riders can be found by name | High (drives discovery) |
| Future sponsors | Review traffic + reach for sponsorship decisions | Medium (future) |

Decision rights: the project is a solo-developed fan/federation tool (see
[`.plan/ceo-review.md`](.plan/ceo-review.md) §Stakeholders).

---

## 3. Feature inventory — every page

The site has **8 distinct user-facing pages**, all static HTML:

| # | View | URL | Purpose |
|---|---|---|---|
| 1 | **Landing redirect** | `/` | Redirects to the current season's first category |
| 2 | **Year redirect** | `/{year}` | Redirects to the first category of that year |
| 3 | **Leaderboard** | `/{year}/{category}` | Per-season, per-category standings table |
| 4 | **Races** | `/{year}/events` | Season calendar (race list) |
| 5 | **Race overview** | `/{year}/events/{slug}` | Picker for results by category within one race |
| 6 | **Race results** | `/{year}/{category}/{slug}` | Positions + points + times for one (race, category) |
| 7 | **Rider disambiguation** | `/{year}/r/{race_number}` | When multiple riders share a number |
| 8 | **Rider profile** | `/{year}/r/{race_number}/{slug}` | Header + every result across categories |
| 9 | **Stats** (private) | `/stats` | Auth-gated visit analytics |
| 10 | **Admin** (private) | `/admin/*` | SQLAdmin panel for ORM CRUD |
| 11 | **404** | (SPA fallback) | `Page not found` with CTA back to leaderboard |

Full anatomy (top-to-bottom layout, mobile reflow, stat cards, component
tree) for each view: see [`.plan/design-review.md`](.plan/design-review.md) §4.

### 3.1 Leaderboard (`/{year}/{category}`)

The main value page. For each category:

- **Top stat cards** (4 on desktop, 2-up on mobile):
  - `LEADER` — current champion with their race number + name. Highlighted
    with a `col-span-2` hero treatment on desktop (inspired by the FIM Hard
    Enduro leader hero pattern).
  - `RACES` — races run so far (`X of Y`).
  - `GAP 1→2` — points gap between first and second place.
  - `ACTIVE` — rider count in the class.
- **Race buttons row** — one clickable chip per race in the season,
  numbered `01`/`02`/`03`. Clicking any chip jumps to the race-results view
  for the current category.
- **Category tabs** — horizontal switcher across all categories for this
  season. Clicking preserves the current race context if applicable.
- **Leaderboard table** — one row per rider. Columns:
  `#` (final position badge with podium colors), `No.` (race number,
  monospace), `Rider` (name + team meta), `Total` (points), `Raced`,
  `Best`, `Dropped` (only for `aggregate_2025` championship format), plus
  one column per race showing that rider's points for that race.
  - Podium rows visually distinguished (gold/silver/bronze badge colors).
  - On mobile: `#`, `No.`, `Rider` columns sticky; race columns scroll
    horizontally with a right-edge fade affordance.
  - Every row click-target area → rider profile.

### 3.2 Races (`/{year}/events`)

Season calendar.

- Header: "{year} Races · N races · X upcoming · Y completed".
- Table columns: `#` (round number, monospace), `Race`, `Location`, `Date`
  (short format e.g. `Apr 18`), `Status` (`✓ Completed` / `Upcoming`).
- Past races render muted. Each row click-target → race overview page.

### 3.3 Race overview (`/{year}/events/{slug}`)

Landing page for a race before a category is chosen.

- Big H1 race name.
- Subtitle: `Round N · Long Date · Location, Bulgaria`.
- Grid of category buttons (one per class). Each card says the rider count
  (or `(pending)` if that category has no results yet for this race).
  Click → race results for that (race, category).

### 3.4 Race results (`/{year}/{category}/{slug}`)

One race, one category, sorted by finish position.

- Header: `R{N} · {Race Name} — {Category}` + date + location.
- Navigation band: "← Back to {category} Leaderboard" on the left,
  `← R{N-1} prev · R{N+1} next →` on the right for one-click round-to-round
  navigation within the same category.
- Category tabs swap the category while keeping the same race.
- Table columns (some hidden when all cells are empty):
  `#`, `No.`, `Rider`, `Time` (formatted `H:MM:SS.CS` or `MM:SS.CS`),
  `Pts`, `Laps`, `GPS` (penalty time).
- DNF indicator: position column shows `DNF` badge; `notes` cell may say
  why.

### 3.5 Rider profile (`/{year}/r/{n}/{slug}`)

- Header card: big monospace `#{race_number}`, first + last name, a meta
  line `{team} · {bike} · {primary category}`, and a stats line
  `Best: Nth · Races entered: N · Total points: N`.
- One results table per category the rider entered that season:
  `Round`, `Race`, `Date`, `Position` (podium-colored badge), `Points`,
  `Time`.
- Bottom: link back to that rider's primary-category leaderboard.

### 3.6 Rider disambiguation (`/{year}/r/{n}`)

When two or more riders share a race number in a season (common when a
number is reused across categories — e.g. 2025 #920 was both a Junior and
a Standard rider), this page lists them as clickable cards with enough
context to distinguish (`#N  First Last · Team · Categories` for each).

If only one rider has that number, the page 302-redirects to the singular
profile directly.

### 3.7 Admin panel (private, `/admin`)

SQLAdmin-powered CRUD over the ORM models. Editable for metadata (flip
`is_current` on a season, fix a rider name, correct a race date, delete a
mistakenly-imported result); read-only for `Visit` (audit log).

Login form at `/admin/login`, username from `ADMIN_USERNAME` (default
`admin`), password from `ADMIN_PASSWORD`. Empty `ADMIN_PASSWORD` keeps
admin off — any login returns 400.

Model views:
- **Season** — editable `is_current` inline, sortable by year.
- **Category** — searchable by `code` / `display_name`.
- **Race** (DB table: `event`) — searchable by name/location, sortable by date.
- **Rider** — searchable by name/team/bike.
- **Result** (DB table: `event_result`) — sortable by position.
- **Visit** — read-only audit log.

Bulk race-result imports stay on the `scripts/import_event.py` CLI — that's
the right tool for a 60-row CSV. The admin panel is for corrections, overrides,
and metadata changes.

### 3.8 Stats (private, `/stats`)

Auth-gated (HTTP Basic, `STATS_PASSWORD` env var). Shows:

- Total visits in the last 30 days (snapshot taken at build time).
- Desktop / Mobile / Unknown device-type counts.
- Visits per (category, season) — bar-list style.
- Last 25 visits with timestamp, page, category, season, device.

`<meta name="robots" content="noindex, nofollow">` keeps it out of search.
The endpoint rebuilds its snapshot on each container build; live querying
is planned if the page becomes a more active surface.

---

## 4. Domain model

All entities live in Postgres; ORM definitions in
`backend/src/db/models.py`. Migrations in `backend/alembic/versions/`.

```
┌─────────────┐
│  Season     │  year, name, slug, is_current, championship_format
└─────┬───────┘    (1 to many ↓)
      │
      ├──────────────┬──────────────┐
      │              │              │
┌─────▼──────┐ ┌────▼─────┐  ┌────▼─────┐
│  Category  │ │  Event   │  │  Rider   │  race_number, first, last, team, bike
└─────┬──────┘ └────┬─────┘  └────┬─────┘
      │            │              │
      │ (1-many ↓) │              │
      └─ Rider ────┘              │ (1-many ↓)
                                  │
                           ┌──────▼───────┐
                           │ EventResult  │  position, points, time_ms,
                           └──────────────┘  start_time_ms, gps_penalty_ms,
                                             cp_count, laps, gap_ms, notes

Visit is a side table, not part of the championship graph:
┌─────────────┐
│  Visit      │  timestamp, page, category, season_year, device_type
└─────────────┘
```

### 4.1 Uniqueness + identity rules

| Table | Unique constraint | Notes |
|---|---|---|
| `season` | `year` UNIQUE, `slug` UNIQUE | One season per year |
| `category` | `(season_id, code)` UNIQUE | `code` is the URL-safe key (`expert`, `profi`, `standard_junior`, …) |
| `event` | `(season_id, slug)` UNIQUE | `slug` is URL-safe key (`kyrnare`, `stara_zagora`, …) |
| `rider` | `(category_id, race_number)` UNIQUE | Same person in 2 categories = 2 `Rider` rows (see §4.2) |
| `event_result` | `(event_id, rider_id)` UNIQUE + indexed on both columns | |
| `visit` | no uniqueness; indexed on `timestamp` | |

### 4.2 Rider identity — the subtle rule

**A rider is uniquely identified by `(race_number, first_name, last_name)`
within a season** — not by `race_number` alone.

- Two different people can share a race number across categories (e.g.
  one #42 in Expert, a different #42 in Junior).
- The same person can race multiple categories, producing multiple
  `Rider` rows that all share `(race_number, first_name, last_name)`
  but differ in `category_id`.

The API and frontend treat `(race_number, first_name, last_name, slug)`
as the identity. `RiderRef` in `backend/app/schemas/common.py` carries all
four fields. See [`.plan/eng-review.md`](.plan/eng-review.md) CQ-1 / N3 /
HC-5 for the full reasoning.

### 4.3 Slug — pinned and server-side

`rider.slug = "{first.strip()}-{last.strip()}".replace(" ", "-").lower()`

Implemented in `backend/app/slug.py` and pinned by
`backend/tests/test_slug.py`. Cyrillic is preserved; non-URL-safe chars
are preserved too (historically acceptable, browsers percent-encode).

**Rule**: the frontend **never** recomputes slugs — it always consumes
`RiderRef.slug` from the API. A future switch to a richer slug algorithm
(accent stripping, collision suffixes, etc.) requires a redirect table.

### 4.4 Championship formats

The `season.championship_format` column takes two values:

- **`aggregate_2025`** — legacy CSVs provide per-rider season totals +
  per-race points. The app computes standings by summing race points
  and applying the "drop the worst score if the rider participated in
  every race" rule. Displays the `Dropped` column.
- **`per_event`** — per-race results with raw positions + points.
  The app computes standings by straight summation, no drop. Used from
  2026 onward.

Service logic: `backend/src/services/standings.py::get_standings`.

---

## 5. System architecture

```
                                ┌──────────────┐
              Browser ─────────▶│   Railway    │ (single service, HTTPS)
                                └──────┬───────┘
                                       │
                          ┌────────────▼──────────────┐
                          │  FastAPI (Uvicorn :5001)  │
                          │                           │
                          │  ┌──── Mount order ────┐  │
                          │  │  /api/* routers      │ │
                          │  │  /health             │ │
                          │  │  / StaticFiles       │ │ ─▶ frontend_dist/
                          │  │    (FrontendStatic)  │ │    (~700 static HTML files)
                          │  └──────────────────────┘ │
                          │                           │
                          │  Routers → Services → DB  │
                          │  (Pydantic v2 schemas)    │
                          └────────────┬──────────────┘
                                       │
                              ┌────────▼────────┐
                              │    Postgres     │
                              │  (bgx database) │
                              └─────────────────┘
```

### 5.1 Components

| Component | Lives in | Role |
|---|---|---|
| FastAPI routers | `backend/app/api/*.py` | Bind HTTP verbs + paths to handler functions |
| Shared Deps | `backend/app/deps.py` | `get_session`, `get_season`, `get_category` — FastAPI dependencies reused across routers |
| Pydantic schemas | `backend/app/schemas/*.py` | Response shapes |
| Auth | `backend/app/auth.py` | HTTP Basic gate on `/api/stats` |
| Slug | `backend/app/slug.py` | Pinned rider slug algorithm (one function) |
| FastAPI app factory | `backend/app/main.py` | Wires routers, slowapi limiter, payload-size middleware, static mount |
| Services (domain) | `backend/src/services/` | Pure-Python leaderboard + rider-profile computation |
| ORM models | `backend/src/db/models.py` | SQLAlchemy 2 mapped classes |
| Session | `backend/src/db/session.py` | Engine + sessionmaker |
| Config | `backend/src/config.py` | Env var loading + `DATABASE_URL` normalization |
| Importers | `backend/scripts/import_*.py` | CSV → DB |
| Frontend pages | `frontend/src/pages/**/*.astro` | One file per URL pattern |
| Frontend layouts | `frontend/src/layouts/BaseLayout.astro` | `<html>` shell, SEO head, nav, footer |
| Frontend components | `frontend/src/components/{common,layout}/*.astro` | Primitives + layout chrome |
| API client | `frontend/src/lib/api.ts` | Typed fetch helpers (used at build time in `getStaticPaths`) |
| Microcopy | `frontend/src/lib/copy.ts` | Single source of every user-facing string |
| Formatting helpers | `frontend/src/lib/format.ts` | `formatTime`, `formatDateShort/Long`, `ordinal`, `isPast` |

### 5.2 Why this shape

- **FastAPI + SSG** was chosen over a Vue SPA after a competitive analysis
  of comparable motorsport sites. None run SPAs; all run SSR/SSG. SEO is
  a top priority for a site that depends on Google for discovery (rider
  searches, category searches). See [`.plan/ceo-review.md`](.plan/ceo-review.md)
  Round 2 / UC-4.
- **Astro + 0 KB JS baseline** preserves the best-possible SEO and performance
  of the previous FastHTML app while unlocking modern component ergonomics
  and a clean path to add interactive islands later.
- **Single container** minimizes Railway cost + ops complexity. The Astro
  build runs against a reachable FastAPI at build time, outputs static
  HTML, and FastAPI serves it via `StaticFiles`.

---

## 6. Data pipeline

```
  CSV files                     Python importers                    Postgres
┌────────────────┐              ┌─────────────────┐               ┌────────────┐
│ scripts/       │              │ scripts/        │               │ bgx DB     │
│ seed_data/     │ ───reads──▶  │ import_2025.py  │ ──inserts──▶  │ season,    │
│ bgx-result-    │              │                 │               │ category,  │
│ 2025-full/*   .csv            │ (aggregate      │               │ event,     │
│                │              │  season totals) │               │ rider,     │
│                │              └─────────────────┘               │ event_res  │
│                │                                                │            │
│ bgx-results-   │              ┌─────────────────┐               │            │
│ 2026/*.csv    ─├──reads──▶    │ scripts/        │ ──inserts──▶  │            │
│ (per event ×   │              │ import_event.py │               │            │
│  category)     │              │                 │               │            │
└────────────────┘              │ (single event   │               │            │
                                │  one category)  │               │            │
                                └─────────────────┘               │            │
                                                                  └────┬───────┘
                                                                       │
                                                         ┌─────────────▼─────────────┐
                                                         │ backend/src/services/     │
                                                         │ standings.py (computes    │
                                                         │   leaderboard on request) │
                                                         │ rider.py (rider profile)  │
                                                         └─────────────┬─────────────┘
                                                                       │
                                                         ┌─────────────▼─────────────┐
                                                         │ backend/app/api/* routers │
                                                         │ → JSON responses           │
                                                         └─────────────┬─────────────┘
                                                                       │
                                         ┌─────────────────────────────▼──────────────────────┐
                                         │ Astro build (`npm run build`):                     │
                                         │   getStaticPaths() fetches every enumerable URL,   │
                                         │   emits dist/.../index.html per URL.               │
                                         └─────────────────────────────┬──────────────────────┘
                                                                       │
                                                         ┌─────────────▼──────────────┐
                                                         │ FastAPI StaticFiles mount  │
                                                         │ serves dist/ at root at    │
                                                         │ request time               │
                                                         └────────────────────────────┘
```

### 6.1 Importers

- **`backend/scripts/import_2025.py`** — reads the 8 aggregate CSVs from
  `backend/scripts/seed_data/bgx-result-2025-full/`, creates the 2025
  `Season` row (with `championship_format='aggregate_2025'`), 8
  `Category` rows, 7 `Event` rows (RACE_ORDER_2025), and the rider +
  event_result rows. Idempotent — wipes and rebuilds 2025.
  Run: `python -m scripts.import_2025`.

- **`backend/scripts/import_event.py`** — reads one per-event per-category
  CSV (e.g. `karnare_2026_navigation_expert.csv`), parses the Bulgarian
  header names (`Поз`, `Ст.№`, `Състезател`, `Време`, …), upserts riders,
  replaces the `EventResult` rows for this `(event, category)` pair.
  Idempotent on (event, category).
  Run: `python -m scripts.import_event --file <csv> --season 2026 --category expert --category-name "Expert" --event karnare --event-name "Kyrnare" --event-date 2026-04-18`.

- **`backend/scripts/seed_calendar.py`** — creates a `Season` + `Event`
  skeleton for a new year before any results exist. Lets the site show
  an upcoming-race list without results.

### 6.2 From DB to static HTML

Astro's `getStaticPaths` is called once per file during `npm run build`.
Each bracketed path file (e.g. `[year]/[category]/index.astro`) fetches
the FastAPI to enumerate valid parameter combinations.

At build time, a typical run produces:

- ~2 seasons × 1 landing-redirect = 2 HTML files
- ~2 seasons × ~8 categories = ~16 leaderboard HTML files
- ~2 seasons × 1 = 2 races-list HTML files
- ~15 races × ~8 categories = ~120 race-results HTML files
- ~15 races = 15 race-overview HTML files
- ~500+ rider-profile HTML files (one per unique (race_number, slug) pair)
- ~500+ rider-disambiguation redirect files
- 1 `/stats` + 1 `/404.html` + 1 `/` = 3 extra

Current count: **723 static HTML files** from 2025 + 2026 data (~6.2 MB
total, ~6 KB per page on average).

When the data changes (new race imported, rider name corrected), the image
must be rebuilt to regenerate the static HTML. Rebuilding takes ~5 seconds
for the Astro stage on a warm Node cache; the full Docker image takes
20–30 seconds.

---

## 7. URL scheme

The dashboard preserves **every URL** from the pre-refactor FastHTML app.
No `/app/` prefix, no backward-compat redirects needed.

| Path pattern | Served by | HTTP status on hit |
|---|---|---|
| `/` | Astro redirect → `/{current_year}/expert` | `302` |
| `/health` | FastAPI JSON | `200` |
| `/api/docs`, `/api/openapi.json` | FastAPI Swagger + schema | `200` |
| `/api/**` | FastAPI routers (JSON only) | `200` / `404` (JSON) |
| `/{year}` | Astro redirect → `/{year}/{first_category}` | `302` |
| `/{year}/{category}` | Astro static (leaderboard) | `200` |
| `/{year}/events` | Astro static (races list) | `200` |
| `/{year}/events/{slug}` | Astro static (race overview) | `200` |
| `/{year}/{category}/{eventSlug}` | Astro static (race results) | `200` |
| `/{year}/r/{n}` | Astro static (disambig or 302) | `200` or `302` |
| `/{year}/r/{n}/{slug}` | Astro static (rider profile) | `200` |
| `/stats` | Astro static (auth-gated on the API it queries) | `200` |
| Any other non-API path | 404 HTML (dist/404.html) | `404` |
| Non-matching `/api/*` | JSON `{"detail":"Not Found"}` | `404` |

**Mount order is load-bearing.** FastAPI registers `/api/*` routers and
`/health` first, then mounts `FrontendStatic` at `/`. The static handler
itself returns JSON 404 for any `/api/*` path that fell through (so a
misspelled endpoint never leaks HTML to a JSON client). See
`backend/tests/test_mount_order.py` for the contract tests.

---

## 8. API reference

Every endpoint is `GET` except `POST /api/track`. All responses are
JSON. Request bodies that exist are JSON too.

Full Pydantic schemas live in `backend/app/schemas/`. The OpenAPI schema
is served at `/api/openapi.json`; Swagger UI at `/api/docs`.

### Meta

| Method | Path | Response | Notes |
|---|---|---|---|
| GET | `/health` | `{status, service, version}` | Container + Railway healthcheck |
| GET | `/api/docs` | Swagger UI HTML | Human-readable schema browser |
| GET | `/api/openapi.json` | OpenAPI 3.1 JSON | Source for frontend `npm run generate:api-types` |

### Seasons

| Method | Path | Response | 404 when |
|---|---|---|---|
| GET | `/api/seasons` | `SeasonListOut` | Never |
| GET | `/api/seasons/{year}` | `SeasonDetailOut` (season + categories + events) | `year` has no season row |

### Leaderboard

| Method | Path | Response | 404 when |
|---|---|---|---|
| GET | `/api/seasons/{year}/standings/{category_code}` | `StandingsOut` (header + rows with embedded RiderRef, events, totals, drop info) | year missing, or category missing in that year |

### Races (events)

| Method | Path | Response | 404 when |
|---|---|---|---|
| GET | `/api/seasons/{year}/events` | `EventListOut` | year missing |
| GET | `/api/seasons/{year}/events/{slug}` | `EventDetailOut` (event + categories in that season) | year missing, or slug not in that season |

### Race results

| Method | Path | Response | 404 when |
|---|---|---|---|
| GET | `/api/seasons/{year}/categories/{code}/events/{slug}` | `EventResultsOut` (sorted by position + time) | year, category, or event missing |

### Riders

| Method | Path | Response | 404 when |
|---|---|---|---|
| GET | `/api/seasons/{year}/riders/{race_number}` | `RiderDisambigOut` (list of every `(first, last)` pair sharing the number) | year missing, or no rider with that number |
| GET | `/api/seasons/{year}/riders/{race_number}/{slug}` | `RiderProfileOut` (header + all results across categories) | year missing, number not used, slug doesn't match any rider with that number, or rider has no results |

### Stats (private)

| Method | Path | Response | Auth |
|---|---|---|---|
| GET | `/api/stats` | `StatsOut` (totals + devices + per-category + last 25 recent) | HTTP Basic via `STATS_PASSWORD` env var (empty → dev bypass) |

### Tracking

| Method | Path | Body | Response | Rate limit |
|---|---|---|---|---|
| POST | `/api/track` | `{"page":"leaderboard","category":"expert","season_year":2026}` | `{"ok":true}` | 10/min per IP; 2 KB payload cap |

### Shared schema — `RiderRef`

Embedded in every response that includes a rider:

```json
{
  "race_number": 42,
  "first_name": "Иван",
  "last_name": "Иванов",
  "slug": "иван-иванов",
  "team": "BGX Racing",
  "bike": "KTM 300 XC-W"
}
```

The frontend treats `slug` as opaque — never recomputes. See
[`.plan/design-review.md`](.plan/design-review.md) §3 + §16 + §18 for
how these shape the UI copy and SEO strings.

---

## 9. Frontend pages — anatomy + data flow

Each `.astro` page follows this pattern:

```astro
---
// 1. Imports — layouts, components, lib.
import BaseLayout from '~/layouts/BaseLayout.astro';
import { api } from '~/lib/api';

// 2. getStaticPaths (only on bracketed paths) — enumerates URL params
//    at build time by calling FastAPI.
export async function getStaticPaths() {
  const seasons = await api.listSeasons();
  // ... return [{ params: {...} }, ...]
}

// 3. Per-page data fetch — typically one or two api.* calls.
const { year, category } = Astro.params;
const data = await api.getLeaderboard(Number(year), category!);

// 4. Per-page derived state + SEO metadata.
const title = `...`;
const description = `...`;
const jsonLd = { "@context": "https://schema.org", ... };
---
<BaseLayout title={title} description={description} jsonLd={jsonLd} ...>
  <!-- 5. Markup using components + microcopy. No inline strings. -->
</BaseLayout>
```

The `BaseLayout` handles SEO head tags (`<title>`, meta description,
canonical, OG/Twitter, optional JSON-LD), the sticky nav, and the footer.
It also imports the self-hosted `@fontsource-variable` fonts and the
global stylesheet.

For component inventory, state matrix (loading/empty/error/partial/success),
accessibility rules, motorsport identity guardrails, responsive contract,
print styles, and per-page performance budgets: see
[`.plan/design-review.md`](.plan/design-review.md) §3–§22.

---

## 10. Operating the dashboard

### 10.1 Add a new season (calendar skeleton, no results yet)

```bash
cd backend
source .venv/bin/activate
python -m scripts.seed_calendar        # or directly inject via DB tool
```

The 2026 calendar was seeded this way. The importer creates `Season` +
`Event` rows for every race; categories get populated when the first
event's CSV is imported.

### 10.2 Add a new race + its results (per category)

Run once per CSV — typically 8 CSVs per race (one per class):

```bash
cd backend
source .venv/bin/activate

python -m scripts.import_event \
    --file scripts/seed_data/bgx-results-2026/<race>_<cat>.csv \
    --season 2026 \
    --category expert --category-name "Expert" \
    --event <race_slug> --event-name "<Race Name>" \
    --event-date 2026-04-18
```

The importer:
- Upserts the `Season` and `Event` rows (idempotent).
- Upserts the `Category` row.
- Upserts every `Rider` row seen in the CSV.
- Replaces every `EventResult` for this (event, category) pair.

After the import, the DB is current. To publish: rebuild the Docker
image so the Astro build picks up the new rider + race rows (new URLs
are emitted as static HTML).

### 10.3 Rebuild + deploy after a race

```bash
# From repo root, with FastAPI + Postgres running locally:
./scripts/build-image.sh bgx-dashboard:latest

# Push the image to Railway (or your runner):
railway up --image bgx-dashboard:latest
```

Railway runs `alembic upgrade head && uvicorn …` on boot; no manual
migrations required.

### 10.4 Correct a rider name or number

```bash
# Fix in the source CSV, then re-run the importer:
python -m scripts.import_event --file <corrected csv> ... --category <cat> ... --event <slug> ...
```

⚠️ Changing a rider's `first` + `last` mutates their URL slug
(rider_slug is derived from name). Existing shared links to the old
slug will 404 after the next rebuild. Acceptable for correction during
a season; add a redirect manually in the FastAPI layer if the old URL
had meaningful traffic.

### 10.5 Mark a season current

The landing page (`/`) redirects to `/{current_year}/expert`. "Current"
is determined by the `is_current` flag on `Season`. Set it via SQL or
by re-running the importer with `--is-current`:

```sql
UPDATE season SET is_current = FALSE;
UPDATE season SET is_current = TRUE WHERE year = 2026;
```

Rebuild + deploy to pick it up in the static pages.

### 10.6 Access the private stats page

- In dev (no `STATS_PASSWORD` set): `GET /api/stats` or `/stats` works
  without auth.
- In production: set `STATS_PASSWORD=<strong_secret>` in Railway env.
  Then `curl -u anyuser:<secret> https://<host>/api/stats`. Any username
  works; only the password is checked (constant-time compare).

---

## 11. Development workflow

Two-terminal setup.

**Terminal A — backend**

```bash
docker compose up -d postgres       # local Postgres on 5432
cd backend
./start.sh                          # creates .venv, pip install -e ., alembic, uvicorn --reload
```

Visit <http://localhost:5001/health> and <http://localhost:5001/api/docs>.

**Terminal B — frontend**

```bash
cd frontend
npm install                         # once
npm run dev                         # Astro on :4321 with /api proxied to :5001
```

Visit <http://localhost:4321>. Hot reload works on `.astro`, `.vue`, `.ts`,
and CSS edits. If the API schema changes, regenerate TS types:

```bash
cd frontend
npm run generate:api-types          # writes src/lib/api.openapi.ts
```

The hand-curated `src/lib/api.types.ts` re-exports ergonomic aliases from
the generated file.

### 11.1 Adding a new API endpoint

1. Add Pydantic schema in `backend/app/schemas/<resource>.py`.
2. Add router or handler in `backend/app/api/<resource>.py`. Reuse
   `Depends(get_session)` + `Depends(get_season)` etc. from
   `backend/app/deps.py`.
3. Wire the router into `backend/app/main.py::create_app`.
4. Add a contract test in `backend/tests/test_api.py` (positive + 404).
5. Regenerate frontend TS: `cd frontend && npm run generate:api-types`.
6. Consume from a view via `api.yourNewMethod(...)` in `src/lib/api.ts`.

### 11.2 Adding a new Astro page

1. Create `frontend/src/pages/<path>.astro` using the anatomy from §9.
2. If the URL is parameterized, implement `getStaticPaths()` that fetches
   enumerable values from the API.
3. Use `BaseLayout` + common components; consume copy from `src/lib/copy.ts`.
4. Add SEO fields per [`.plan/design-review.md`](.plan/design-review.md) §18.
5. `npm run build` to verify the page emits static HTML against live data.

### 11.3 Adding a new importer (for a new data source)

Mirror `backend/scripts/import_event.py` structure:

1. Parse the CSV with Pandas + flexible header mapping (Bulgarian or
   English headers).
2. Upsert `Season`, `Category`, `Event`, `Rider` as needed (keep
   idempotent semantics).
3. Replace the `EventResult` rows scoped to (event, category).
4. Add a `make <name>-dry` flag if the data is manually curated.

---

## 12. Testing

All tests live under `backend/tests/` and run via `pytest` from the
`backend/` directory.

```bash
cd backend && pytest                # 64 tests; ~1.4s wall-clock
```

Breakdown:

| File | Count | Scope |
|---|---|---|
| `test_slug.py` | 10 | Pinned rider slug algorithm (incl. Cyrillic) |
| `test_mount_order.py` | 5 | `/api/nonexistent` JSON 404, `/health`, `/api/docs`, `/api/openapi.json`, `/api` vs static mount ordering |
| `test_cors.py` | 3 | No CORS headers leak on any endpoint |
| `test_track.py` | 9 | POST /api/track — happy path, mobile UA detection, Pydantic rejection paths, oversize 413 |
| `test_api.py` | 21 | Contract tests for every endpoint — positive + 404 + disambiguation + stats auth |
| `test_standings_2025.py` | 16 | **Golden test.** Re-imports 2025 CSVs into a fresh DB and asserts the leaderboard output exactly reproduces the aggregated CSVs. Per-category + podium check. |

Session-scoped `conftest.py` seeds the 2025 data once per pytest run (via
`scripts.import_2025`, which is idempotent).

No frontend test suite in the initial refactor. Astro component tests
(Vitest) + Playwright e2e are a Phase 5 polish target when the first
interactive island lands.

---

## 13. Security + privacy

| Concern | Status | Mechanism |
|---|---|---|
| `/api/stats` auth | ✅ | HTTP Basic via `STATS_PASSWORD` env var; constant-time compare |
| CORS | ✅ (same-origin) | No `CORSMiddleware` installed; test asserts no `Access-Control-*` headers leak |
| XSS | ✅ | Astro auto-escapes `{expr}` output; Vue `{{ }}` auto-escapes; `v-html` forbidden when islands are added |
| SQL injection | ✅ | ORM-mediated (SQLAlchemy); path params are typed (`{year:int}`) |
| CSRF | Low risk | Read-only API; `POST /api/track` is the only mutation, same-origin only |
| Rate limit on `/api/track` | ✅ | `slowapi` 10/min per IP + 2 KB payload cap middleware |
| Sensitive data | Low risk | Visit tracking stores only `page`, `category`, `season_year`, `device_type`. No IP, no full UA. |
| GDPR (Bulgarian users) | Manageable | Visit data has no PII. `/stats` auth prevents casual exposure. |
| Mount-order safety | ✅ | `/api/*` fallthrough returns JSON 404 instead of HTML; tested |
| Path traversal (StaticFiles) | ✅ | `FrontendStatic.get_response` guards with `Path.resolve().relative_to(dist)` |

For the full security review, see
[`.plan/eng-review.md`](.plan/eng-review.md) §5 (Security) + §6 (Hidden
complexity).

---

## 14. Success metrics + rollback

Tracked before and after the post-refactor cutover — log snapshots to
`.plan/metrics.md`. Full definitions in
[`.plan/design-review.md`](.plan/design-review.md) §21.

| # | Metric | Source | Target | Rollback trigger |
|---|---|---|---|---|
| M1 | LCP (Largest Contentful Paint) | Lighthouse on `/2026/expert` | < 2.5s | > 4s sustained |
| M2 | JS bundle (gzipped per page) | Astro build report / CI size-limit | ~0 KB for Phase 2 ship | > 100 KB |
| M3 | Organic search sessions (weekly) | Google Search Console | ≥ pre-launch baseline | -25% sustained 14 days |
| M4 | Indexed pages count | Search Console / `site:` query | ≥ pre-launch count after 30d | > 10% drop |
| M5 | Visits per week | DB query on `visit` table | ≥ baseline | -25% sustained 14 days |
| M6 | Mobile session share | DB query (`device_type`) | ~stable | ±15% drift |
| M7 | Time-to-ship-next-feature | informal wall-clock | < 1 week for first filter feature | > 2 weeks = thesis weak |

Rollback procedure: `git revert` the cutover merge on `main`; Railway
auto-deploys the reverted image. Data is untouched (DB schema unchanged).

---

## 15. Roadmap

From [`.plan/ceo-review.md`](.plan/ceo-review.md) dream-state grading
(user-confirmed): every item below is on the table except live-timing
WebSocket (removed from scope).

**Realistic solo (near-term, days–weeks of effort):**
- Filters on leaderboards (team, bike, age group) — Vue island on
  LeaderboardView. Planned as the post-refactor "M7" feature.
- Social share images (OG `image`) per rider and per race — serverless
  OG generator at build time or via Cloudinary.
- Progression charts on rider profiles (Chart.js island, client:visible).
- Rider comparison widget (side-by-side two riders).
- Mobile-first polish pass on the LeaderboardView sticky column (design-review §7.3).

**Needs a partner or external integration (medium-term):**
- Race-day timing system integration (needs a timing partner).
- Push notifications for race events (web push + PWA shell).

**Ops polish:**
- `@astrojs/sitemap` replacement (post-build generator; robots.txt
  already references `/sitemap-index.xml`).
- Font subsetting to trim the 295 KB variable-font payload down toward
  the 80 KB target (design-review §3.2).
- GitHub Actions CI that boots Postgres + uvicorn, runs `build-image.sh`,
  and deploys on merge to `main`.
- Admin UI replacing the `scripts/import_event.py` CLI for race-day
  data entry (eng-review E6).

---

## See also

| Doc | Scope |
|---|---|
| [`README.md`](README.md) | Quick start + stack + project layout |
| [`DEPLOYMENT.md`](DEPLOYMENT.md) | Deploy + env vars + operations |
| [`CLAUDE.md`](CLAUDE.md) | Project conventions for contributors + AI agents |
| [`.plan/refactor-plan.md`](.plan/refactor-plan.md) | The FastHTML → FastAPI + Astro refactor plan |
| [`.plan/ceo-review.md`](.plan/ceo-review.md) | Strategy review (user challenges, scope expansions, success metrics) |
| [`.plan/design-review.md`](.plan/design-review.md) | **Design source of truth** (tokens, view anatomy, states, guardrails, microcopy, SEO templates, perf budgets, print) |
| [`.plan/eng-review.md`](.plan/eng-review.md) | Architecture, test matrix, security, hidden complexity |

## Changelog

- **v0.2.0** (current, on `refactor/fastapi-vue`): FastAPI + Astro SSG
  stack. 723 static HTML pages + JSON API. 64-test suite. Single-container
  deploy. See commits `cab66a3` through `76b9d9d`.
- **v0.1.0** (on `main`, pre-refactor): FastHTML server-rendered + Postgres
  migration + 2026 season data.
