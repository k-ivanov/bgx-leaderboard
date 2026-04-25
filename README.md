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

The site serves pre-generated static HTML for every route (all 700+ URLs —
leaderboards, race results, every rider profile). Same URLs as the previous
FastHTML app (`/2026/expert`, `/2025/r/42/ivan-ivanov`, etc.).

## Quick start

```bash
# 1. Start local Postgres
docker compose up -d postgres

# 2. Backend (terminal A)
cd backend && ./start.sh                 # uvicorn on :5001 with --reload

# 3. Seed 2025 data (one-time)
source backend/.venv/bin/activate
cd backend && python -m scripts.import_2025

# 4. Frontend dev server (terminal B)
cd frontend && npm install && npm run dev  # Astro on :4321, /api proxied to :5001
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
cd backend && pytest        # 64 tests (API contract, slug pin, mount order,
                            # CORS absence, track, 2025 golden)
```

## Project layout

```
.
├── backend/
│   ├── app/                  # FastAPI app
│   │   ├── api/              # 7 routers mounted at /api/*
│   │   ├── schemas/          # Pydantic v2 response models
│   │   ├── auth.py           # HTTP Basic for /api/stats
│   │   ├── deps.py           # shared FastAPI Depends
│   │   ├── main.py           # app factory + static mount
│   │   └── slug.py           # pinned rider slug
│   ├── src/                  # shared domain code
│   │   ├── db/               # SQLAlchemy models + session
│   │   ├── services/         # leaderboard + rider computation
│   │   ├── config.py         # env + DATABASE_URL handling
│   │   └── seasons.py
│   ├── alembic/              # DB migrations
│   ├── scripts/              # CSV importers (2025 aggregate, 2026 per-event)
│   ├── tests/                # 64 pytest tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── pages/            # Astro file-based routing
│   │   ├── layouts/          # BaseLayout.astro (SEO head, nav, footer)
│   │   ├── components/       # common primitives + layout
│   │   ├── lib/              # api.ts (typed fetch), copy.ts (microcopy), format.ts
│   │   └── styles/           # global.css (tokens + print)
│   └── package.json
├── Dockerfile                # multi-stage: node → python
├── docker-compose.yml        # local Postgres + dashboard
├── railway.json              # Railway deploy config
└── .plan/                    # planning + review artifacts
    ├── refactor-plan.md
    ├── ceo-review.md
    ├── design-review.md
    └── eng-review.md
```

## Docs

- [`DEPLOYMENT.md`](DEPLOYMENT.md) — deploy + env vars + metrics
- [`CLAUDE.md`](CLAUDE.md) — project conventions for humans + AI agents
- [`.plan/design-review.md`](.plan/design-review.md) — design source of truth (tokens, components, SEO templates, copy library, print, perf budgets)

## License

Unofficial fan project. Data from the BGX Hard Enduro Championship.
