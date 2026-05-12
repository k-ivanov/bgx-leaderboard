#!/usr/bin/env bash
# Mirror local Postgres → production Railway Postgres in one shot.
#
# Pipeline:
#   1. (default) Back up prod first  → db_dumps/prod-pre-sync-<ts>.sql.gz
#   2. Dump local data-only          → db_dumps/local-for-prod-<ts>.sql.gz
#   3. TRUNCATE matching tables on prod, then COPY the local data in.
#
# Schema is assumed to already match (alembic upgrade head ran on prod).
#
# Prerequisites:
#   - docker  (for bgx-postgres + postgres:18-alpine image)
#   - railway CLI linked to this project; `railway status` must show a
#     service named "Postgres" exposing DATABASE_PUBLIC_URL.
#   - local bgx-postgres container running (`make db-up`).
#
# Usage:
#   ./scripts/sync-local-to-prod.sh                    # interactive confirm
#   ./scripts/sync-local-to-prod.sh --yes              # skip confirm
#   ./scripts/sync-local-to-prod.sh --no-prod-backup   # skip safety dump
#   PROD_SERVICE=postgres ./scripts/sync-local-to-prod.sh   # alt service name

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DUMP_DIR="$ROOT/db_dumps"
PROD_SERVICE="${PROD_SERVICE:-Postgres}"
TS="$(date -u +%Y%m%d-%H%M%SZ)"

CONFIRM=false
PROD_BACKUP=true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|--force)    CONFIRM=true ;;
        --no-prod-backup) PROD_BACKUP=false ;;
        -h|--help)        sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "[sync] unknown flag: $1" >&2; exit 2 ;;
    esac
    shift
done

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
command -v docker  >/dev/null || { echo "[sync] docker is required." >&2; exit 1; }
command -v railway >/dev/null || { echo "[sync] railway CLI is required (npm i -g @railway/cli)." >&2; exit 1; }
if ! docker ps --format '{{.Names}}' | grep -q '^bgx-postgres$'; then
    echo "[sync] local Postgres 'bgx-postgres' is not running. Try: make db-up" >&2
    exit 1
fi

if ! $CONFIRM; then
    printf "[sync] This will OVERWRITE production data with the contents of your local DB.\n"
    printf "[sync] Type 'yes' to proceed: "
    read -r reply
    [[ "$reply" == "yes" ]] || { echo "[sync] aborted."; exit 1; }
fi

mkdir -p "$DUMP_DIR"

# ---------------------------------------------------------------------------
# Prod helpers. We funnel commands through `railway run --service Postgres`
# so the DATABASE_URL is bound by Railway in the subprocess only — it never
# lands in this script's argv, env, or output. The `${DATABASE_PUBLIC_URL:-…}`
# fallback prefers the public proxy URL; *.railway.internal won't resolve
# from a developer laptop.
# ---------------------------------------------------------------------------
prod_psql() {
    railway run --service "$PROD_SERVICE" -- bash -c '
        URL="${DATABASE_PUBLIC_URL:-$DATABASE_URL}"
        docker run --rm -i postgres:18-alpine psql "$URL" -v ON_ERROR_STOP=1 "$@"
    ' bash "$@"
}
prod_pg_dump() {
    railway run --service "$PROD_SERVICE" -- bash -c '
        URL="${DATABASE_PUBLIC_URL:-$DATABASE_URL}"
        docker run --rm -i postgres:18-alpine pg_dump "$@" "$URL"
    ' bash "$@"
}

# ---------------------------------------------------------------------------
# 1. Optional prod safety backup
# ---------------------------------------------------------------------------
BACKUP=""
if $PROD_BACKUP; then
    BACKUP="$DUMP_DIR/prod-pre-sync-${TS}.sql.gz"
    echo "[sync] step 1/3: backing up prod → $BACKUP"
    prod_pg_dump --no-owner --no-privileges --clean --if-exists \
        | gzip -9 > "$BACKUP"
    echo "[sync]   size: $(du -h "$BACKUP" | awk '{print $1}')"
else
    echo "[sync] step 1/3: prod backup SKIPPED (--no-prod-backup)"
fi

# ---------------------------------------------------------------------------
# 2. Dump local (data-only). Schema lives in alembic, so we never push DDL.
# ---------------------------------------------------------------------------
LOCAL_DUMP="$DUMP_DIR/local-for-prod-${TS}.sql.gz"
echo "[sync] step 2/3: dumping local → $LOCAL_DUMP"
docker exec bgx-postgres pg_dump -U bgx -d bgx \
    --no-owner --no-privileges --data-only --disable-triggers \
    | gzip -9 > "$LOCAL_DUMP"
echo "[sync]   size: $(du -h "$LOCAL_DUMP" | awk '{print $1}')"

# ---------------------------------------------------------------------------
# 3. Restore onto prod
#    Truncate exactly the tables the dump COPYs into; then stream the dump
#    through psql. RESTART IDENTITY CASCADE resets sequences too, so the
#    COPY blocks (which include sequence setvals) replay correctly.
# ---------------------------------------------------------------------------
TABLES="$(gunzip -c "$LOCAL_DUMP" | grep -oE '^COPY public\.[a-zA-Z_]+' | awk '{print $2}' | sort -u | paste -sd, -)"
if [[ -z "$TABLES" ]]; then
    echo "[sync] no COPY blocks in local dump — nothing to push." >&2
    exit 1
fi
echo "[sync] step 3/3: TRUNCATE + COPY on prod  (tables: $TABLES)"
prod_psql -c "TRUNCATE TABLE $TABLES RESTART IDENTITY CASCADE;" >/dev/null
gunzip -c "$LOCAL_DUMP" | prod_psql >/tmp/sync-local-to-prod.log

echo "[sync] ✓ local → prod sync complete."
echo "[sync]   local dump: $LOCAL_DUMP"
if [[ -n "$BACKUP" ]]; then
    echo "[sync]   rollback : ./scripts/db-restore.sh prod $BACKUP --yes"
fi
