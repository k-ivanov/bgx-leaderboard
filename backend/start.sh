#!/bin/bash
# Local dev entrypoint. Run from the backend/ directory.
# For production, see the root-level Dockerfile.

set -euo pipefail

# Allow running from repo root as well: `./backend/start.sh`.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Starting BGX Hard Enduro Dashboard (local dev)..."

if [ ! -d ".venv" ]; then
    echo "Creating virtualenv..."
    python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

if [ ! -f ".env" ]; then
    echo ".env not found in backend/ — copy .env.example to .env and set DATABASE_URL first."
    echo "Quick local Postgres: from repo root run: docker compose up -d postgres"
    exit 1
fi

echo "Applying migrations..."
alembic upgrade head

echo "Starting server on http://localhost:${PORT:-5001}"
python main.py
