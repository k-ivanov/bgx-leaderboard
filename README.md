# BGX Navigation Dashboard

Public read-only dashboard for the **BGX Hard Enduro Championship** — Bulgarian
motorcycle racing series. Shows per-season leaderboards, race results, rider
profiles, and the race calendar.

> **Heads up on point totals.** This site is an archive of every result published, not a mirror of the official scoring. Point totals may differ from other sources — see [`docs/scoring.md`](docs/scoring.md) for the policy and [`.reports/2025-validation-vs-hardendurobulgaria.md`](.reports/2025-validation-vs-hardendurobulgaria.md) for a row-by-row comparison.

## Stack

- **Backend**: FastAPI + Pydantic v2 + SQLAlchemy 2 (`backend/app/`)
- **Frontend**: Astro 4 SSG + Tailwind, 0 KB JS baseline (`frontend/`)
- **Database**: Postgres + Alembic migrations
- **Deploy**: Single Docker image on Railway

The site serves pre-generated static HTML for every route (~1800 URLs —
leaderboards, race results, every rider profile). Same URLs as the previous
FastHTML app (`/2026/expert`, `/2025/r/42/ivan-ivanov`, etc.). Two Vue islands
hydrate on top: rider search in the nav and the auth-gated `/stats` dashboard.

## Quick start

```bash
# Easy mode: one command does everything (Postgres, backend, frontend).
make dev

# Manual mode (two terminals):
docker compose up -d postgres            # Postgres
make dev-backend                         # uvicorn on :5001 (admin + stats: admin/letmein)
make dev-frontend                        # Astro on :4321, /api proxied to :5001

# Seed (idempotent — only imports CSVs not yet logged):
make seed-new                            # all years
make seed-new YEAR=2026                  # one year
```

Open <http://localhost:4321>.

## Production build

```bash
./scripts/build-image.sh bgx-dashboard:latest
docker run --rm -p 5001:5001 \
  -e DATABASE_URL=postgresql+psycopg2://bgx:bgx@host.docker.internal:5432/bgx \
  bgx-dashboard:latest
```

Full deploy steps in [`DEPLOYMENT.md`](DEPLOYMENT.md).

## Tests

```bash
cd backend && pytest        # 89 tests (API contract, slug pin, mount order,
                            # CORS absence, track, security headers, search,
                            # career, tiebreakers, 2025 golden)
```

CI runs the same on every push + PR — see `.github/workflows/ci.yml`.

## Project layout

```
.
├── backend/
│   ├── app/                  # FastAPI app
│   │   ├── api/              # 8 routers mounted at /api/*
│   │   ├── schemas/          # Pydantic v2 response models
│   │   ├── auth.py           # HTTP Basic for /api/stats (router-level)
│   │   ├── security_headers.py  # CSP, HSTS, X-Frame-Options middleware
│   │   ├── admin.py          # SQLAdmin panel
│   │   ├── deps.py           # shared FastAPI Depends
│   │   ├── main.py           # app factory + static mount
│   │   └── slug.py           # pinned rider slug
│   ├── src/                  # shared domain code
│   │   ├── db/               # SQLAlchemy models + session
│   │   ├── services/         # leaderboard + rider computation
│   │   ├── config.py         # env + DATABASE_URL handling
│   │   └── seasons.py
│   ├── alembic/              # DB migrations (5 so far)
│   ├── scripts/              # CSV importers + idempotent seed-new
│   ├── tests/                # 89 pytest tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/            # Astro file-based routing (~1800 routes)
│   │   ├── layouts/          # BaseLayout.astro (SEO head, nav, footer, tracking)
│   │   ├── components/       # common primitives + layout + Vue islands
│   │   ├── lib/              # api.ts (typed fetch), copy.ts (microcopy), format.ts
│   │   ├── assets/           # logo set (optimized via astro:assets)
│   │   └── styles/           # global.css (tokens + print)
│   ├── public/               # favicons + robots.txt
│   ├── scripts/              # build-sitemap.mjs (post-build SEO)
│   └── package.json
├── Dockerfile                # multi-stage: node → python
├── docker-compose.yml        # local Postgres + dashboard
├── railway.json              # Railway deploy config
├── .github/workflows/        # CI: pytest + frontend build
├── docs/                     # scoring policy + (eventually) deploy notes
├── .plan/                    # historical refactor + review artifacts
├── .plans/                   # forward-looking improvement playbooks
└── .reports/                 # data validation reports
```

## Docs

- [`docs/scoring.md`](docs/scoring.md) — how standings are computed (and why they may differ from other sources)
- [`DEPLOYMENT.md`](DEPLOYMENT.md) — deploy + env vars + metrics
- [`CLAUDE.md`](CLAUDE.md) — project conventions for humans + AI agents
- [`.plan/design-review.md`](.plan/design-review.md) — design source of truth (tokens, components, SEO templates, copy library, print, perf budgets)
- [`.plans/improvements.md`](.plans/improvements.md) — prioritized improvement roadmap (P0–P6)
- [`.plans/p0-p4-detailed.md`](.plans/p0-p4-detailed.md) — execution playbook for P0–P4 items
- [`.reports/2025-validation-vs-hardendurobulgaria.md`](.reports/2025-validation-vs-hardendurobulgaria.md) — row-by-row check vs hardendurobulgaria.com

## License

Unofficial fan project. Data from the BGX Hard Enduro Championship.
