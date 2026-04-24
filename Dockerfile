FROM python:3.12-slim

LABEL version="0.1.0"
LABEL description="BGX Hard Enduro Championship Dashboard"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5001 \
    HOST=0.0.0.0

WORKDIR /app

# System deps: psycopg2-binary ships with its own libpq, so no build tools needed.
# curl is kept for Docker healthchecks.
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY backend/src ./src
COPY backend/scripts ./scripts
COPY backend/main.py ./main.py

EXPOSE 5001

# Apply pending migrations, then boot the app. Railway re-runs this on every deploy.
CMD ["sh", "-c", "alembic upgrade head && python main.py"]
