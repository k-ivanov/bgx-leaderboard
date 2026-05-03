# syntax=docker/dockerfile:1.7

# BGX Navigation Dashboard — multi-stage build.
#   Stage 1 (node)   : builds the Astro SSG frontend against a reachable FastAPI.
#   Stage 2 (python) : runtime — FastAPI serves /api/* and mounts dist/ at /.
#
# Two build modes for Stage 1:
#   - From-scratch (default): Astro calls the FastAPI backend via
#     getStaticPaths at build time. Needs a reachable API. Locally, pass
#     `--build-arg API_URL=http://host.docker.internal:5001` and run
#     scripts/build-image.sh — it stands up the host backend first.
#   - Pre-built: the caller has already produced `frontend/dist` (e.g., a
#     GitHub Actions job that ran `npm run build` against a services-based
#     Postgres + uvicorn). Pass `--build-arg PREBUILT_DIST=1` and Stage 1
#     skips npm install + build entirely. This is what
#     `.github/workflows/release.yml` uses to ship to GHCR → Railway,
#     since Railway's build environment can't reach a backend.

###############################################################################
# Stage 1 — frontend build
###############################################################################
FROM node:20-alpine AS frontend

ARG API_URL=http://host.docker.internal:5001
ARG PREBUILT_DIST=0
ENV API_URL=${API_URL} \
    NODE_ENV=production

WORKDIR /work

# Install Node deps only when we're building from scratch.
# (Cached as a separate layer — rebuilds only on lockfile change.)
COPY frontend/package.json frontend/package-lock.json ./
RUN if [ "$PREBUILT_DIST" != "1" ]; then npm ci --no-audit --no-fund; fi

# Copy sources (including dist/ when PREBUILT_DIST=1).
COPY frontend/ ./
RUN if [ "$PREBUILT_DIST" = "1" ]; then \
      echo "Using pre-built dist/ from build context"; \
      test -d dist && [ -n "$(ls -A dist 2>/dev/null)" ] \
        || { echo "ERROR: PREBUILT_DIST=1 but frontend/dist is missing or empty"; exit 1; }; \
    else \
      echo "Building Astro from scratch against API at ${API_URL}"; \
      npm run build; \
    fi

###############################################################################
# Stage 2 — python runtime
###############################################################################
FROM python:3.12-slim AS runtime

LABEL version="0.2.0"
LABEL description="BGX Hard Enduro Championship Dashboard (FastAPI + Astro SSG)"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001 \
    HOST=0.0.0.0 \
    FRONTEND_DIST=/app/frontend_dist

WORKDIR /app

# System deps. psycopg2-binary ships its own libpq, so no build tools needed.
# curl is kept for Docker healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Python deps (declared in backend/pyproject.toml — kept explicit here so that
# the cached layer only busts when deps change, not on every code touch).
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        "fastapi>=0.110" \
        "uvicorn[standard]>=0.27" \
        "gunicorn>=21.0.0" \
        "pydantic>=2.5" \
        "sqlalchemy>=2.0,<3.0" \
        "psycopg2-binary>=2.9" \
        "alembic>=1.13" \
        "python-dotenv>=1.0" \
        "slowapi>=0.1.9" \
        "pandas>=2.0.0" \
        "sqladmin>=0.19" \
        "itsdangerous>=2.2"

# Backend source
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/src ./src
COPY backend/scripts ./scripts
COPY backend/pyproject.toml ./pyproject.toml

# Frontend build output
COPY --from=frontend /work/dist ./frontend_dist

EXPOSE 5001

# Apply migrations, then boot uvicorn. Railway re-runs this on every deploy.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-5001}"]
