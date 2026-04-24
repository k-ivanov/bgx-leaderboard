# Deployment — Railway + Postgres

The dashboard runs as a single Docker container. It requires a Postgres database; `DATABASE_URL` is the only required environment variable. On startup, the container runs `alembic upgrade head` and then boots the FastHTML server.

## Railway (primary target)

1. **Create the project**

   ```bash
   npm i -g @railway/cli     # once
   railway login
   railway init
   ```

2. **Add the Postgres plugin**

   From the Railway dashboard, add the **Postgres** plugin to the project. Railway injects a `DATABASE_URL` into the web service automatically. No other config is required — the app normalizes `postgres://` to `postgresql+psycopg2://` internally.

3. **Deploy**

   ```bash
   railway up
   ```

   On first boot, `alembic upgrade head` creates the schema. The container then starts the server. Health check: `GET /health`.

4. **Seed the data (one-time per season/event)**

   The image ships with the importer scripts but not the CSVs. Run imports via `railway run` from your laptop — this executes the command against the Railway environment so the production `DATABASE_URL` is used.

   ```bash
   # 2025 championship (aggregate CSVs)
   railway run python -m scripts.import_2025

   # 2026 events — one invocation per event×category CSV
   railway run python -m scripts.import_event \
     --file scripts/seed_data/bgx-results-2026/karnare_2026_navigation_expert.csv \
     --season 2026 \
     --category expert --category-name "Expert" \
     --event karnare --event-name "Kärnäre" --event-date 2026-04-18 --event-type navigation

   railway run python -m scripts.import_event \
     --file scripts/seed_data/bgx-results-2026/karnare_2026_navigation_profi.csv \
     --season 2026 --category profi --category-name "Pro" \
     --event karnare --event-name "Kärnäre" --event-date 2026-04-18 --event-type navigation
   ```

   Imports are idempotent: re-running updates the rows in place.

5. **Set the current season**

   The 2026 importer sets `is_current = true` on the 2026 season. The 2025 importer leaves it off unless you pass `--is-current`. The homepage redirect uses the `is_current` flag.

## Local development

```bash
# 1. Start local Postgres
docker compose up -d postgres

# 2. Copy env and install deps
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Apply schema + seed both seasons
alembic upgrade head
python -m scripts.import_2025
python -m scripts.import_event --file scripts/seed_data/bgx-results-2026/karnare_2026_navigation_expert.csv \
  --season 2026 --category expert --category-name "Expert" \
  --event karnare --event-name "Kärnäre" --event-date 2026-04-18 --event-type navigation
python -m scripts.import_event --file scripts/seed_data/bgx-results-2026/karnare_2026_navigation_profi.csv \
  --season 2026 --category profi --category-name "Pro" \
  --event karnare --event-name "Kärnäre" --event-date 2026-04-18 --event-type navigation

# 4. Run the server
python main.py   # http://localhost:5001
```

## Environment variables

| Var | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | yes | — | Postgres URL. `postgres://` prefixes are normalized automatically. |
| `DEFAULT_SEASON_YEAR` | no | `2026` | Fallback used when no season exists in the DB yet. |
| `PORT` | no | `5001` | HTTP port. Railway sets this for you. |
| `HOST` | no | `0.0.0.0` | Bind address. |

## Schema migrations

Migrations live in `alembic/versions/`. Add new ones with:

```bash
alembic revision --autogenerate -m "short description"
alembic upgrade head
```

Every deploy runs `alembic upgrade head` before starting the app — see the `CMD` in the `Dockerfile`.

## Health check

```bash
curl https://<your-app>.up.railway.app/health
# {"status":"healthy","service":"bgx-navigation-dashboard","version":"0.1.0"}
```

## Verifying persistence

After a redeploy:

```bash
railway run psql $DATABASE_URL -c "SELECT COUNT(*) FROM visit; SELECT COUNT(*) FROM event_result;"
```

Counts should survive the deploy. If they don't, confirm the Postgres plugin is attached to the web service (not just the project).
