# BGX Navigation Dashboard — Project Notes

Public read-only dashboard for the BGX Hard Enduro Championship (Bulgarian
motorcycle series). Shows per-season leaderboards, race results, rider
profiles, and a race calendar.

## Stack at a glance

| Layer | Tech | Lives in |
|---|---|---|
| Frontend | Astro 4 SSG + Tailwind, 0 KB JS baseline | `frontend/` |
| Backend | FastAPI 0.110 + Pydantic v2 + SQLAlchemy 2 | `backend/app/` |
| Data | Postgres + Alembic migrations | `backend/alembic/`, `backend/src/db/` |
| Services (domain) | Pure-Python computed leaderboards + rider profiles | `backend/src/services/` |
| Deploy | Single Docker image, Railway | `Dockerfile`, `railway.json` |

The refactor from FastHTML to FastAPI + Astro SSG was done across Phases 0–5.
Full history: `.plan/refactor-plan.md` and the three review files alongside it.

## Vocabulary (design-review.md §14)

- **Leaderboard** — the per-category table of riders sorted by points.
  Not "Standings" or "Ranking".
- **Race** / **Races** — a single event in the season calendar. Not "Event".
  (Note: the DB table is still called `event`; only the UI renames.)
- **Round** — numeric position in the calendar (R1, R2, …).
- **Points** — scores per placing. Abbreviation `Pts` in tight cells.
- **Hard Enduro** — the only event type surfaced in UI.
- **Rider** — not "Competitor" or "Pilot".

## Key architectural invariants

1. **Rider identity** = `(race_number, first_name, last_name)` per season.
   Race numbers alone are NOT unique — reused across categories and between
   people. Everywhere in the API, a rider is represented by `RiderRef`
   (`backend/app/schemas/common.py`) which includes the slug.
2. **Slug is computed server-side**. `backend/app/slug.py::rider_slug`
   produces `{first}-{last}-{race_number}`. The race_number is included on
   purpose: real-world rider names collide ("Иван ИВАНОВ" appears with 4
   distinct numbers in the dataset, almost certainly multiple people).
   Trade-off: a rider whose race_number changes between seasons fragments
   into separate `/rider/{slug}` URLs. Frontend never recomputes slugs —
   always consumes `RiderRef.slug` from the API.
3. **URL contract** (frontend-restructure.md). The public surface is now:
   - `/` — landing with single CTA → `/results`
   - `/results?season=&category=&race=` — single results page (Vue SPA island)
   - `/rider/{slug}` — multi-season profile, one page per slug (SSG)
   - `/stats` — auth-gated dashboard
   - `/api/*` — read-only JSON API
   Every legacy URL (`/{year}`, `/{year}/{cat}`, `/{year}/{cat}/{slug}`,
   `/{year}/events`, `/{year}/events/{slug}`, `/{year}/r/{n}/{slug}`) issues
   a 301 redirect to the new shape via `app/redirects.py`. Bookmarks + search
   indexed pages keep working; do NOT re-introduce per-year Astro pages.
4. **Mount order in `app.main`**: `/api/*` → `/health` → `/admin` →
   legacy redirect router → `/` StaticFiles. The redirect router MUST stay
   between admin and StaticFiles or `dist/{year}/{cat}/index.html` will
   shadow the 301. Tested by `tests/test_mount_order.py` and
   `tests/test_redirects.py`.
5. **Zero JS per page** is the Phase 2 baseline. Interactive features
   (filters, comparison, charts) are added as Vue islands only where needed.
6. **Standings are an archive, not a mirror** of the official championship
   scoring. Multi-day events sum cumulatively, no drop-worst rule, some races
   may be intentionally absent. Full policy: [`docs/scoring.md`](docs/scoring.md).

## Running locally

Two terminals:

```bash
# Postgres
docker compose up -d postgres

# Terminal A — backend
cd backend && ./start.sh            # uvicorn on :5001 with --reload

# Terminal B — frontend
cd frontend && npm install && npm run dev   # Astro on :4321, /api proxied to :5001
```

Seed once: `cd backend && python -m scripts.import_2025`.

## Tests

```bash
cd backend
pytest                              # 99 tests: contract, slug, mount order,
                                    # legacy redirects, CORS absence, track,
                                    # 2025 golden
```

## Build the production image

```bash
./scripts/build-image.sh bgx-dashboard:latest
# Probes localhost:5001/health, then multi-stage Docker build.
```

## Review artifacts

- [`.plan/refactor-plan.md`](.plan/refactor-plan.md) — the plan + execution phases
- [`.plan/ceo-review.md`](.plan/ceo-review.md) — strategy/scope review (user challenges + expansions)
- [`.plan/design-review.md`](.plan/design-review.md) — the design source of truth (tokens, view anatomy, states matrix, vocabulary, microcopy, SEO, print, perf budgets)
- [`.plan/eng-review.md`](.plan/eng-review.md) — architecture, test matrix, security, hidden complexity

## Success metrics (post-launch)

Track M1–M7 per design-review.md §21 in `.plan/metrics.md`:
- M1 LCP, M2 bundle size, M3 organic sessions, M4 indexed pages,
- M5 visits/week, M6 mobile share, M7 time-to-ship-next-feature.

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke context-save / context-restore
- Code quality, health check → invoke health
