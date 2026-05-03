# Deployment — Railway + Postgres (FastAPI + Astro SSG)

Single Docker image, single Railway service, managed Postgres. The image ships
a FastAPI JSON backend under `/api/*` and the Astro-built static frontend at
every other path (e.g. `/2026/expert`, `/2025/r/42/ivan-ivanov`). All existing
URLs from the pre-refactor FastHTML app are preserved.

## Architecture

```
Browser ──▶ Railway ──▶ FastAPI (Uvicorn, :5001)
                         ├── /api/* routers       → JSON endpoints
                         ├── /health              → JSON health
                         └── /*  StaticFiles      → Astro dist/ (index.html per URL)
                                                   404.html fallback for unknown paths
```

## Build pipeline

The Dockerfile is multi-stage:

- **Stage 1 (`node:20-alpine`)** runs `npm run build` for the Astro frontend.
  Astro calls the FastAPI backend at build time via `getStaticPaths` to
  enumerate rider/category/race URLs. Stage 1 requires a reachable FastAPI
  via the `API_URL` build-arg (default `http://host.docker.internal:5001`).
- **Stage 2 (`python:3.12-slim`)** installs Python deps, copies the backend
  source + Stage 1's `dist/`, boots `uvicorn app.main:app` after running
  `alembic upgrade head`.

Local build helper: `./scripts/build-image.sh [tag]` probes the host API and
hands it to the build, so one command produces a ready-to-run image.

## Railway (primary target)

1. **Create the project**

   ```bash
   npm i -g @railway/cli
   railway login
   railway init
   ```

2. **Add the Postgres plugin**

   From the Railway dashboard, add the **Postgres** plugin to the project.
   Railway injects `DATABASE_URL`. The app normalizes `postgres://` to
   `postgresql+psycopg2://` internally.

3. **Build the image**

   Railway's build runner does not have a reachable FastAPI during Stage 1,
   so you **build the image locally** (or in a CI runner where you boot a
   temporary Postgres + uvicorn first) and **push the image to Railway** via
   the container registry.

   ```bash
   # Local — requires local Postgres + uvicorn running on :5001
   ./scripts/build-image.sh bgx-dashboard:latest

   # Push to Railway's image registry
   railway up --image bgx-dashboard:latest
   ```

   Alternative: use a GitHub Actions workflow that boots services, builds the
   image, and deploys via `railway up`. A `.github/workflows/deploy.yml`
   skeleton is on the roadmap.

4. **Seed the data (one-time per season/event)**

   ```bash
   # 2025 championship (aggregate CSVs — the importer sets is_current=false)
   railway run python -m scripts.import_2025

   # 2026 events — one invocation per (event, category) CSV
   railway run python -m scripts.import_event \
     --file scripts/seed_data/bgx-results-2026/karnare_2026_navigation_expert.csv \
     --season 2026 \
     --category expert --category-name "Expert" \
     --event karnare --event-name "Kärnäre" --event-date 2026-04-18
   ```

   Imports are idempotent — re-running updates rows in place.

5. **Set the `STATS_PASSWORD` env var (recommended before launch)**

   The `/api/stats` endpoint is gated by HTTP Basic Auth when
   `STATS_PASSWORD` is non-empty. Leave empty in dev; set a strong value
   in Railway's secrets for production.

## Local development

Two-terminal setup — backend on `:5001`, Astro dev server on `:4321` with
`/api/*` proxy.

```bash
# 1. Start Postgres
docker compose up -d postgres

# 2. Backend (terminal A)
cd backend
cp .env.example .env          # sets DATABASE_URL to the local compose DB
./start.sh                    # creates venv, installs from pyproject.toml,
                              # runs alembic, boots uvicorn with --reload

# 3. Seed (once)
source backend/.venv/bin/activate
cd backend
python -m scripts.import_2025

# 4. Frontend (terminal B)
cd frontend
npm install
npm run dev                   # http://localhost:4321  (proxies /api to :5001)
```

### Regenerating the API TypeScript types

The generated types live at `frontend/src/lib/api.openapi.ts` and ergonomic
aliases are in `frontend/src/lib/api.types.ts`. When the backend schema
changes, regenerate:

```bash
cd frontend
npm run generate:api-types    # hits http://localhost:5001/api/openapi.json
```

## Environment variables

| Var | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | Postgres URL. `postgres://` prefixes are normalized automatically. |
| `DEFAULT_SEASON_YEAR` | no | `2026` | Fallback used when no season is marked `is_current`. |
| `STATS_PASSWORD` | no (dev) / yes (prod) | empty | Enables HTTP Basic on `/api/stats`. Empty string disables auth. |
| `ADMIN_USERNAME` | no | `admin` | Username for the `/admin` panel login form. |
| `ADMIN_PASSWORD` | no (dev) / yes (prod) | empty | Enables the SQLAdmin panel at `/admin`. Empty string keeps admin **disabled** — any login attempt returns 400. Set a strong value in Railway secrets. |
| `ADMIN_SESSION_SECRET` | no (dev) / **yes (prod)** | dev-only fallback | Signing key for the admin session cookie. **Must override in production.** |
| `PORT` | no | `5001` | HTTP port. Railway sets this for you. |
| `HOST` | no | `0.0.0.0` | Bind address. |
| `FRONTEND_DIST` | no | `/app/frontend_dist` | Override where FastAPI finds the Astro build output. |
| `API_URL` (build-time only) | no | `http://host.docker.internal:5001` | Where Stage 1 fetches during Astro build. |
| `SITE` (build-time only) | no | `http://localhost:5001` | Used by Astro for `<link rel="canonical">` + OG tags. Set to the production URL when building for Railway. |

## Schema migrations

Migrations live in `backend/alembic/versions/`. Add new ones with:

```bash
cd backend
alembic revision --autogenerate -m "short description"
alembic upgrade head
```

Every deploy runs `alembic upgrade head` before starting the app — see the
`CMD` in the root `Dockerfile`.

## Health check

```bash
curl https://<your-app>.up.railway.app/health
# {"status":"ok","service":"bgx-dashboard-api","version":"0.2.0"}
```

## Verifying persistence

After a redeploy:

```bash
railway run psql "$DATABASE_URL" -c \
  "SELECT COUNT(*) FROM visit; SELECT COUNT(*) FROM event_result;"
```

Counts should survive the deploy. If they don't, confirm the Postgres plugin
is attached to the web service (not just the project).

## Success metrics (from design-review.md §21)

Track these before/after the post-launch deploy and log to `.plan/metrics.md`:

- **M1 LCP** — Lighthouse run on `/2026/expert` (target < 2.5s)
- **M2 Bundle size** — Astro build reports; goal: 0 KB JS, < 50 KB CSS
- **M3 Organic search sessions** — Google Search Console, weekly
- **M4 Indexed pages count** — `site:<domain>` query
- **M5 Visits per week** — `SELECT COUNT(*) FROM visit WHERE timestamp > NOW() - INTERVAL '7 days'`
- **M6 Mobile session share** — `SELECT device_type, COUNT(*) FROM visit GROUP BY device_type`
- **M7 Time-to-ship-next-feature** — informal; time the first filter/comparison feature

Rollback criterion: M3 or M5 drops >25% sustained for 14 days — investigate
(likely routing, since every URL is static HTML).
