# CI/CD setup — GitHub → Railway, deploying from `main`

End-to-end guide for the continuous-integration and continuous-deployment
pipeline. Audience: anyone setting this up from scratch on a fresh
GitHub + Railway account, or onboarding to the existing one.

Goal: a push to `main` runs the full test matrix on GitHub Actions and,
on green, ships the new image to Railway with **no manual step**. Failed
checks block the deploy. Failed deploys roll back to the previous image.

If you're looking for **how data moves** (CSVs, dumps, restores), see
[`data-management.md`](data-management.md). If you're looking for the
**Railway / Postgres mechanics** (env vars, dump/restore tooling), see
[`../.plans/deployment.md`](../.plans/deployment.md).

---

## Architecture in one diagram

```
                         ┌──────────────────────────────────┐
   feature/* ──┐         │           GitHub repo            │
   feature/* ──┤         │                                  │
   feature/* ──┴──PR──▶  │  development  ──PR──▶  main      │
                         │      │                  │        │
                         │      │ CI (push)        │ CI     │
                         │      ▼                  │ +      │
                         │   GitHub Actions        │ deploy │
                         │   • backend pytest      │        │
                         │   • frontend build      │        │
                         │   • API types drift     │        │
                         └─────────────│───────────│────────┘
                                       │ green     │ green
                                       ▼           ▼
                                    (no deploy)   Railway
                                                   • build Dockerfile
                                                   • alembic upgrade head
                                                   • boot uvicorn
                                                   • health-check
                                                   • route traffic
```

- `feature/*` → opens a PR into `development`. CI runs on the PR.
- `development` → PR into `main` once cohesive. CI re-runs on the PR.
- `main` is **prod**. Push to `main` triggers Railway to build + deploy.
- No human runs `railway up`. The Railway app is wired to the GitHub
  repo's `main` branch and rebuilds on every commit there.

---

## Branch strategy

| Branch | Purpose | Protections | Deploys |
|---|---|---|---|
| `main` | Production. Always green, always deployable. | Required checks + 1 review + linear history | Railway → prod |
| `development` | Integration. Multiple features land here, soak together. | Required checks | None (CI only) |
| `feature/*` | Short-lived. Single PR. | None | None |

**Promotion path:** `feature/foo` → `development` → `main`.
Hot-fixes can branch directly off `main`, PR into `main`, then
back-merged into `development` so the branches don't drift. (Not common;
prefer the normal path.)

---

## Required repo configuration on GitHub

These are one-time settings to apply on the GitHub side. All under
`https://github.com/<org>/<repo>/settings`.

### 1. Actions permissions

`Settings → Actions → General`

- **Actions permissions:** Allow all actions and reusable workflows.
- **Workflow permissions:** Read and write permissions
  (so workflows can post check statuses).

### 2. Branch protection — `main`

`Settings → Branches → Branch protection rules → Add rule`

- **Branch name pattern:** `main`
- **Require a pull request before merging:** ✓
  - **Require approvals:** ≥ 1
  - **Dismiss stale reviews:** ✓
- **Require status checks to pass before merging:** ✓
  - Required: **Backend (pytest)**, **Frontend (build + check)**, **API types drift check**
  - **Require branches to be up to date before merging:** ✓
- **Require linear history:** ✓ (no merge commits — keeps the timeline
  readable and `git bisect` boring)
- **Require deployments to succeed before merging:** off — the deploy
  fires *after* merge, not before
- **Allow force pushes:** off
- **Allow deletions:** off

### 3. Branch protection — `development`

Same as `main` minus the linear-history requirement (faster integration,
merge commits are OK there) and minus the approval requirement (solo
dev → 0 reviewers required; small team → 1).

### 4. Repository secrets

`Settings → Secrets and variables → Actions → Repository secrets`

Set these once. They're injected into workflow runs as `${{ secrets.X }}`.

| Secret | Used by | Source |
|---|---|---|
| `RAILWAY_TOKEN` | Optional GitHub Actions deploy step (see §"Alternative CD") | Railway dashboard → Account → Tokens |
| `STATS_PASSWORD` | Not required by CI directly — set on Railway, see §"Railway environment" | Generate strong random |
| `ADMIN_PASSWORD` | Same as above | Generate strong random |

If you use Railway's built-in GitHub integration (the recommended path
below), you don't need `RAILWAY_TOKEN` at all — Railway pulls from
GitHub via its own OAuth. Add the token only if you want a GitHub
Actions step to control deploys explicitly.

---

## The CI workflow (already in place)

`.github/workflows/ci.yml` runs on every push to `main`, `development`,
`refactor/fastapi-vue`, and on every PR. Three jobs:

| Job | What it does | Service deps |
|---|---|---|
| **Backend (pytest)** | Installs `backend/`, runs `alembic upgrade head`, runs `pytest -q` (99 tests). | Postgres 15. |
| **Frontend (build + check)** | Boots a backend (Postgres + uvicorn), runs `npm ci`, `astro check`, `npm run build` (the build's `getStaticPaths` calls the API to enumerate `/rider/{slug}` paths, so the backend must be reachable). | Postgres 15 + uvicorn. |
| **API types drift check** | Boots a backend, regenerates `frontend/src/lib/api.openapi.ts` from `/api/openapi.json`, fails if the file diverged from the committed copy. | Postgres 15 + uvicorn. |

All three are required checks for `main` and `development`.

`astro check` is currently allowed to fail (`npm run check || true`)
because the frontend is in active flux. Tighten this once the surface
stabilizes by removing the `|| true`.

---

## CD — GHCR image, Railway pulls (recommended)

Railway's build environment can't reach a backend during the Docker
build, so the Astro `getStaticPaths` API call fails with
`getaddrinfo ENOTFOUND host.docker.internal`. To work around that, the
image is built in GitHub Actions (where Postgres + uvicorn run as
service containers, exactly like CI), and Railway only **runs** it.

### How it works

`.github/workflows/release.yml` runs on every push to `main`:

1. Spins up Postgres 15 as a service.
2. Installs the backend, runs `alembic upgrade head`, boots uvicorn
   on `:5001`.
3. Runs `npm ci` + `npm run build` against that backend, populating
   `frontend/dist`.
4. Builds the Docker image with `--build-arg PREBUILT_DIST=1`. Stage 1
   of the Dockerfile skips `npm install` + `npm run build` and just
   copies the pre-built `dist/`.
5. Pushes to **`ghcr.io/<org>/<repo>:latest`** and `:sha-<short>`.

Railway watches that registry tag and redeploys when a new image is
pushed.

### One-time setup

1. **Make GHCR image readable.** First push creates the package as
   private. Make it public so Railway doesn't need credentials:
   `https://github.com/users/<you>/packages/container/<repo>/settings`
   → **Change visibility → Public**. (Or keep it private and add a
   Railway deploy token; see below.)

2. **Create or open the Railway project.**

   ```bash
   npm i -g @railway/cli      # one-time on your laptop
   railway login
   cd ~/Work/bgx-navigation-dashboard
   railway init               # creates a new project, OR
   railway link               # links to an existing one
   ```

3. **Add the Postgres plugin.** From the Railway dashboard:
   `New → Database → Add PostgreSQL`. Railway injects `DATABASE_URL`
   into every service in the project.

4. **Configure the service to deploy from the registry.** In the
   Railway service's settings:
   `Source → Image`. Enter `ghcr.io/<org>/<repo>:latest`.
   - **Watch tag:** `latest` (Railway redeploys on tag updates).
   - If the package is private: add `GHCR_USERNAME` (your GitHub
     username) and `GHCR_PASSWORD` (a PAT with `read:packages`)
     under `Source → Private registry credentials`.

5. **Confirm the deploy settings.**
   - **Healthcheck path:** `/health`
   - **Healthcheck timeout:** 60 seconds (covers the alembic step)
   - **Restart policy:** `ON_FAILURE`, max 10 retries (already in `railway.json`)
   - **Pre-deploy command:** none (Dockerfile's `CMD` runs `alembic upgrade head` before the app)

### One-time setup

1. **Create or open the Railway project.**

   ```bash
   npm i -g @railway/cli      # one-time on your laptop
   railway login
   cd ~/Work/bgx-navigation-dashboard
   railway init               # creates a new project, OR
   railway link               # links to an existing one
   ```

2. **Add the Postgres plugin.** From the Railway dashboard:
   `New → Database → Add PostgreSQL`. Railway injects `DATABASE_URL`
   into every service in the project.

3. **Connect the GitHub repo.** In the Railway service's settings:
   `Source → Connect GitHub Repo → <org>/bgx-leaderboard → Branch: main`.
   Authorize Railway to read the repo if it isn't already.

4. **Confirm the build settings.**
   - **Builder:** Dockerfile (auto-detected via `railway.json`)
   - **Watch paths:** leave blank (rebuild on any commit)
   - **Pre-deploy command:** none (Dockerfile's `CMD` runs `alembic upgrade head` before the app)
   - **Healthcheck path:** `/health`
   - **Healthcheck timeout:** 60 seconds (covers the alembic step)
   - **Restart policy:** `ON_FAILURE`, max 10 retries (already in `railway.json`)

5. **Set environment variables on the Railway service.**

   `Variables → New variable` (or `railway variables set …` from CLI):

   | Var | Required | Value |
   |---|---|---|
   | `DATABASE_URL` | yes | _(injected by the Postgres plugin — do not set manually)_ |
   | `STATS_PASSWORD` | yes | strong random; gates `/api/stats`, `/api/docs`, `/api/openapi.json` |
   | `ADMIN_PASSWORD` | yes | strong random; gates `/admin` |
   | `DEFAULT_SEASON_YEAR` | no | `2026` (only used as a fallback before any Season exists) |

   ```bash
   # Generate two random passwords:
   railway variables set STATS_PASSWORD="$(openssl rand -hex 24)"
   railway variables set ADMIN_PASSWORD="$(openssl rand -hex 24)"
   ```

   Forgetting these is the most common day-1 mistake. Without them,
   the dev defaults (`letmein`) leak `/admin` and `/api/stats` to the
   public internet.

6. **Configure custom domain (optional).**

   `Settings → Networking → Custom domain`. Railway issues a TLS cert
   automatically. Update DNS as instructed.

### First production deploy from `main`

Once the Railway service is connected and env vars are set:

1. Open a PR `development → main` (the very first one carries
   everything that's been integrated).
2. Wait for CI green on the PR.
3. Merge with **Rebase and merge** (matches the linear-history rule).
4. Railway picks up the push, runs the multi-stage Dockerfile build
   (frontend stage 1, Python stage 2), runs `alembic upgrade head`,
   boots `uvicorn`, waits for `/health` to return 200, swaps traffic.
   Total time: ~3–5 minutes.
5. Verify:
   ```bash
   curl https://<your-app>.up.railway.app/health
   # → {"status":"ok","service":"bgx-dashboard-api","version":"0.2.0"}
   ```
6. Seed the database — see the
   [Seed paths](../.plans/deployment.md#path-a--seed-prod-from-local-postgres-one-shot-bootstrap)
   in `deployment.md`. The container boots without data; the public
   site shows empty seasons until you push.

### Day-to-day deploy flow

```
1. checkout development
2. git pull
3. make a change in a feature branch, push, open PR into development
4. CI green → merge into development
5. (soak) — verify on staging if you set one up, or in dev
6. Open a PR development → main
7. CI green + 1 review → merge with "Rebase and merge"
8. Railway auto-deploys; ~3–5 min later the change is live.
```

The `main` branch's tip is always the running production commit. To
know what's live, run `git log -1 main` or check the Railway dashboard.

---

## Alternative CD — GitHub Actions explicit deploy

Use this when you need **CI-aware control** over the deploy: gating on
specific job outputs, posting deploy notifications elsewhere, deploying
to multiple environments, etc.

Add `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Railway (prod)

on:
  push:
    branches: [main]

# One deploy at a time. New pushes cancel an in-flight deploy and
# replace it — Railway can't process two `railway up` commands
# against the same service in parallel anyway.
concurrency:
  group: deploy-prod
  cancel-in-progress: true

jobs:
  deploy:
    name: Build + ship
    runs-on: ubuntu-latest
    # Only run if every required CI check on `main` is green.
    needs: []  # implicit — see "wait for CI" notes below
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm i -g @railway/cli@latest

      - name: Deploy
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
        run: |
          # `up --service <name>` deploys the named service in the
          # currently-linked project. The token replaces interactive login.
          railway up --service web --detach

      - name: Wait for healthy /health
        env:
          PROD_URL: ${{ vars.PROD_URL }}    # set under Settings → Variables
        run: |
          for i in $(seq 1 60); do
            if curl -fsS "$PROD_URL/health" >/dev/null; then
              echo "✓ healthy after ${i}s"
              exit 0
            fi
            sleep 5
          done
          echo "✗ timed out waiting for $PROD_URL/health"; exit 1
```

**Notes:**

- `needs:` should reference the CI job IDs once both workflows live in
  the same repo. Easiest: combine deploy with the CI jobs in
  `ci.yml` and gate on `needs: [backend, frontend, types-drift]`.
- `RAILWAY_TOKEN` comes from `Account → Tokens` in Railway. Scope it
  to the project, not the whole account.
- Disable Railway's built-in GitHub integration (§"Source") if you
  switch to this Actions-driven flow — otherwise you get **two**
  deploys per push.

---

## Wait-for-CI on Railway's auto-deploy

Railway's GitHub integration deploys on push, regardless of CI status.
That means a force-push to `main` with broken code would deploy. Two
ways to prevent that:

1. **Branch protection on `main` requires green CI before merge.** Done
   if you set up §"Required repo configuration → Branch protection".
   Force-push is blocked. Merging via PR only happens after green CI.
   Sufficient for a solo or small-team workflow.

2. **Disable Railway auto-deploy and use the GitHub Actions flow** in
   §"Alternative CD". Railway only deploys when the workflow says so,
   and the workflow runs only after the CI jobs succeed.

Pick one. Don't run both — duplicate deploys.

---

## Rollback

### Railway dashboard (fastest)

1. Open the service → **Deployments** tab.
2. Find the last green deploy.
3. **⋯ → Redeploy**. Takes ~30 seconds (Railway already has the image).

### Git revert + push (preferred for the audit trail)

```bash
git checkout main
git pull
git revert <bad-commit>      # creates a new commit that undoes the bad one
git push
# Railway auto-deploys the revert.
```

`git revert` over `git reset --hard` because `main` has linear-history
protection — non-fast-forward pushes are rejected.

### Database rollback (rare)

App-code rollbacks via the two methods above don't touch data.
Schema changes are forward-only (Alembic does support `downgrade`,
but we don't run it on Railway). If a migration corrupted data,
restore from a dump:

```bash
make db-dump-prod ARGS="--tag pre-rollback"          # snapshot what's there now
make db-seed-prod FILE=db_dumps/prod-pre-….sql.gz    # restore the last good dump
```

See `.plans/deployment.md` for the dump/restore tooling.

---

## Post-deploy smoke

The Dockerfile healthcheck verifies `/health` returns 200, which is
"the app started". Two extra checks worth running by hand or in CI
after the deploy completes:

```bash
PROD=https://<your-app>.up.railway.app
curl -fsS $PROD/health                                                         # baseline
curl -fsS $PROD/api/seasons | python3 -m json.tool | head -5                   # API works
curl -fsS -I $PROD/2025/expert | grep -E '^HTTP|^location'                    # legacy redirect works
curl -fsS $PROD/results | grep -o '<title>[^<]*</title>'                       # SSG page served
```

The repo's `make smoke` target wraps these against any `API_URL`:

```bash
API_URL=https://<your-app>.up.railway.app make smoke
```

---

## Monitoring (low-overhead defaults)

- **Railway logs:** `railway logs --service web --tail`. Live tail of
  uvicorn stdout/stderr.
- **Railway metrics:** memory + CPU charts in the dashboard.
- **Visit analytics:** the app's own `/stats` page (Basic auth via
  `STATS_PASSWORD`). Tracks per-page visits, devices, sessions.
- **Uptime:** any external pinger pointed at `/health` (UptimeRobot,
  Pingdom, BetterStack) — three nines is plenty for a public results
  archive; don't over-engineer.

When traffic warrants it, add Sentry:

```bash
pip install sentry-sdk[fastapi]
# wire in backend/app/main.py with SENTRY_DSN env var
```

Out of scope for this doc.

---

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Push to `main` doesn't deploy | Railway GitHub integration not connected to the right branch | Service settings → Source → Branch: main |
| Build hangs at "Stage 1 — frontend build" | Astro `getStaticPaths` can't reach the API. _Should not happen on Railway_ — Stage 1 runs in isolation, the frontend uses a build-time `API_URL`. If you switched to runtime API calls, that won't work in static SSG | Keep all dynamic data behind `getStaticPaths` + `getStaticProps`; the build needs to be reachable to the API only at build time |
| `Failed to call getStaticPaths for src/pages/rider/[slug].astro` in CI | The Frontend job has no backend running. Already fixed — the job stands up Postgres + uvicorn before `npm run build` | Confirm `.github/workflows/ci.yml` matches the version in this repo |
| `relation "season" does not exist` after deploy | `alembic upgrade head` didn't run before the app booted | The Dockerfile `CMD` is `sh -c "alembic upgrade head && uvicorn …"`. Confirm the Railway start command isn't overriding `CMD`. |
| `/admin` and `/api/stats` accept `letmein` | `STATS_PASSWORD` / `ADMIN_PASSWORD` not set on Railway | `railway variables set STATS_PASSWORD=…` and redeploy |
| 502 from Railway after deploy | App boot exceeded the healthcheck timeout (default 30s, alembic + first connection can take 40s on cold Postgres) | Bump the healthcheck timeout in service settings to 60s |
| 99 backend tests pass locally, fail in CI | `DATABASE_URL` in CI points at the GitHub-hosted Postgres which differs by version (16 local vs 15 in CI) | Pin local Postgres to 15 in `docker-compose.yml`, or update CI to 16 — keep them aligned |

---

## Checklist for a fresh setup

Use this when bootstrapping CI/CD on a brand-new GitHub repo + Railway
project. ~30 minutes end-to-end.

- [ ] Create the GitHub repo, push the codebase
- [ ] Add `.github/workflows/ci.yml` (already in this repo)
- [ ] Configure Actions permissions (read+write)
- [ ] Add branch protection on `main` (required checks: backend, frontend, types-drift; 1 review; linear history)
- [ ] Add branch protection on `development` (required checks; no review)
- [ ] Open the first PR `development → main` to seed `main` with the FastAPI architecture
- [ ] Create a Railway project, add the Postgres plugin
- [ ] Connect Railway service to GitHub repo, branch `main`
- [ ] Set `STATS_PASSWORD` + `ADMIN_PASSWORD` on Railway
- [ ] Set healthcheck path = `/health`, timeout = 60s
- [ ] Merge the first PR, wait for Railway to deploy
- [ ] `curl https://<app>.up.railway.app/health` → 200
- [ ] Seed prod data via `make db-seed-prod` (see `data-management.md`)
- [ ] Smoke-check `/`, `/results`, a `/rider/<slug>`, a legacy redirect
- [ ] Add a custom domain (optional)
- [ ] Document the URL + password locations somewhere safe (1Password, etc.)

That's it. Subsequent deploys are zero-touch — write code, open PR,
merge, wait 5 minutes.

---

## File index

| File | Role |
|---|---|
| `.github/workflows/ci.yml` | CI pipeline — pytest, frontend build, API types drift |
| `.github/workflows/deploy.yml` | Optional explicit-deploy workflow (not committed; copy from §"Alternative CD") |
| `Dockerfile` | Multi-stage build (Astro → Python). `CMD` runs `alembic upgrade head` then `uvicorn`. |
| `railway.json` | Tells Railway to use the Dockerfile builder + restart policy |
| `docker-compose.yml` | Local Postgres only — never deployed |
| `.plans/deployment.md` | Railway env vars, dump/restore tooling, three seed paths |
| `docs/data-management.md` | Day-to-day data lifecycle (CSVs, dumps, restores) |
| `docs/cicd-setup.md` | This file. |
