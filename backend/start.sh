#!/bin/bash
# Local dev entrypoint for the FastAPI backend.
# Run from the backend/ directory (or anywhere — this script self-locates).
# For production, see the root-level Dockerfile.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting BGX Hard Enduro Dashboard backend (local dev)..."

if [ ! -d ".venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies from pyproject.toml..."
pip install -q -e .

if [ ! -f ".env" ]; then
    echo ".env not found in backend/ — copy .env.example to .env and set DATABASE_URL first."
    echo "Quick local Postgres: from repo root run: docker compose up -d postgres"
    exit 1
fi

echo "Applying migrations..."
alembic upgrade head

echo "Starting uvicorn on http://${HOST:-0.0.0.0}:${PORT:-5001}"
exec uvicorn app.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "${PORT:-5001}" \
    --reload
