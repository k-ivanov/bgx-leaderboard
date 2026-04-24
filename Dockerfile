FROM python:3.12-slim

LABEL version="0.2.0"
LABEL description="BGX Hard Enduro Championship Dashboard — FastAPI backend"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001 \
    HOST=0.0.0.0

WORKDIR /app

# System deps: psycopg2-binary ships with its own libpq, so no build tools needed.
# curl is kept for Docker healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps via pyproject.toml. Copy only the project metadata first
# to maximize Docker layer cache reuse across code-only changes.
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/src/README.md ./src/README.md
# Install runtime deps declared in pyproject.toml. We don't need the hatchling
# build backend for a running container, so pip is told to install only
# dependencies, not the project package itself.
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
        "pandas>=2.0.0"

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/app ./app
COPY backend/src ./src
COPY backend/scripts ./scripts

EXPOSE 5001

# Apply pending migrations, then boot the FastAPI app.
# uvicorn replaces the old `python main.py` FastHTML entry (deleted in Phase 5).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-5001}"]
