#!/usr/bin/env bash
# Build the production Docker image locally.
#
# The Astro build (Stage 1 of the Dockerfile) needs a reachable FastAPI to
# enumerate routes via getStaticPaths. This script ensures Postgres + a dev
# uvicorn are running on the host, then hands host.docker.internal as the
# API_URL to `docker build`.
#
# Usage:
#   ./scripts/build-image.sh [tag]
#
# If your uvicorn + Postgres are already running on :5001 and :5432, this
# script is essentially `docker build --build-arg API_URL=... -t <tag> .`.

set -euo pipefail

TAG="${1:-bgx-dashboard:latest}"
API_URL="${API_URL:-http://host.docker.internal:5001}"

echo "[build-image] target tag: ${TAG}"
echo "[build-image] Stage 1 API URL: ${API_URL}"

# Sanity: probe the API URL from the host so we know the build won't fail
# immediately. This uses localhost:5001 because that's what host.docker.internal
# resolves to from inside a Docker build.
HOST_API_URL="${API_URL/host.docker.internal/localhost}"
if ! curl -fsS "${HOST_API_URL}/health" > /dev/null; then
    echo "[build-image] FastAPI is not reachable at ${HOST_API_URL}/health"
    echo "[build-image] Start it with: cd backend && ./start.sh"
    echo "[build-image] Or: docker compose up -d postgres && (cd backend && uvicorn app.main:app --port 5001)"
    exit 1
fi

echo "[build-image] FastAPI is healthy. Running docker build…"
DOCKER_BUILDKIT=1 docker build \
    --build-arg "API_URL=${API_URL}" \
    --tag "${TAG}" \
    "$(dirname "$0")/.."

echo "[build-image] Done. Image: ${TAG}"
echo ""
echo "Run with:"
echo "  docker run --rm -p 5001:5001 \\"
echo "    -e DATABASE_URL=postgresql+psycopg2://bgx:bgx@host.docker.internal:5432/bgx \\"
echo "    ${TAG}"
