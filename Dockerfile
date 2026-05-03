# syntax=docker/dockerfile:1.7

# BGX Navigation Dashboard — multi-stage build.
#   Stage 1 (node)   : builds the Astro SSG frontend against a reachable FastAPI.
#   Stage 2 (python) : runtime — FastAPI serves /api/* and mounts dist/ at /.
#
# The Astro build calls the FastAPI backend via getStaticPaths at build time.
# Pass `--build-arg API_URL=http://host.docker.internal:5001` locally, or point
# at a staging/production API in CI. See scripts/build-image.sh for the
# orchestrated local workflow.

###############################################################################
# Stage 1 — frontend build
###############################################################################
FROM node:20-alpine AS frontend

ARG API_URL=http://host.docker.internal:5001
ENV API_URL=${API_URL} \
    NODE_ENV=production

WORKDIR /work

# Install Node deps (cached as a separate layer — rebuilds only on lockfile change)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund

# Copy sources and build
COPY frontend/ ./
RUN echo "Building Astro against API at ${API_URL}" && \
    npm run build

# Strip any unreferenced _astro/*.js — grep-verified unused in Phase 2 (zero
# pages reference the Vue-runtime artifact). Keep CSS + fonts.
RUN find dist/_astro -name "*.js" -print -delete 2>/dev/null || true


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
