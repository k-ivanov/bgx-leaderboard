#!/usr/bin/env bash
# Dump a Postgres database to db_dumps/ in the project root.
#
# Modes:
#   ./scripts/db-dump.sh local                 # local docker compose Postgres
#   ./scripts/db-dump.sh prod                  # prod, via $PROD_DATABASE_URL or `railway run`
#   ./scripts/db-dump.sh url postgres://…      # arbitrary URL
#
# Flags (any position after the mode):
#   --data-only            Skip schema; useful for seeding a Railway DB whose
#                          schema already comes from `alembic upgrade head`.
#   --schema-only          Schema (DDL) only — sanity-check what migrations
#                          will produce on a target.
#   --no-clean             Omit the DROP/CREATE prelude (default keeps it,
#                          which makes a full dump idempotent against a DB
#                          that already has data).
#   --tag <name>           Custom suffix on the file name (default: $mode).
#
# Output:
#   db_dumps/<mode>[-<tag>]-<UTC-timestamp>.sql.gz
#
# Notes:
#   - We use `docker run --rm postgres:16-alpine pg_dump …` for the URL mode
#     so the host doesn't need a matching pg_dump installed.
#   - For prod, prefer `PROD_DATABASE_URL=postgres://… ./scripts/db-dump.sh prod`.
#     If unset, we fall through to `railway run -- pg_dump $DATABASE_URL`,
#     which requires the Railway CLI to be linked to the right project.
#   - The full dump uses --clean --if-exists so it can be applied to a
#     database with existing data without manual cleanup. The data-only
#     dump uses --disable-triggers so foreign keys don't fight insert order.

set -euo pipefail

# ----------------------------------------------------------------------------
# Locate the project root from this script's path. Means the script works
# regardless of the caller's CWD.
# ----------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DUMP_DIR="$ROOT/db_dumps"

usage() {
    sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
}

if [[ $# -lt 1 ]]; then usage; fi

MODE="$1"; shift
TAG=""
DATA_ONLY=false
SCHEMA_ONLY=false
NO_CLEAN=false
URL_ARG=""

case "$MODE" in
    local|prod) ;;
    url)
        if [[ $# -lt 1 ]]; then
            echo "[db-dump] 'url' mode requires a Postgres URL." >&2
            usage
        fi
        URL_ARG="$1"; shift
        ;;
    -h|--help) usage ;;
    *)  echo "[db-dump] unknown mode: $MODE" >&2; usage ;;
esac

while [[ $# -gt 0 ]]; do
    case "$1" in
        --data-only)   DATA_ONLY=true ;;
        --schema-only) SCHEMA_ONLY=true ;;
        --no-clean)    NO_CLEAN=true ;;
        --tag)         shift; TAG="${1:-}";;
        *) echo "[db-dump] unknown flag: $1" >&2; usage ;;
    esac
    shift
done

if $DATA_ONLY && $SCHEMA_ONLY; then
    echo "[db-dump] --data-only and --schema-only are mutually exclusive." >&2
    exit 2
fi

mkdir -p "$DUMP_DIR"
TS="$(date -u +%Y%m%d-%H%M%SZ)"
SUFFIX="${TAG:+-$TAG}"
OUT="$DUMP_DIR/${MODE}${SUFFIX}-${TS}.sql.gz"

PG_DUMP_FLAGS=(--no-owner --no-privileges)
if $DATA_ONLY; then
    PG_DUMP_FLAGS+=(--data-only --disable-triggers)
elif $SCHEMA_ONLY; then
    PG_DUMP_FLAGS+=(--schema-only)
elif ! $NO_CLEAN; then
    PG_DUMP_FLAGS+=(--clean --if-exists)
fi

case "$MODE" in
    local)
        if ! docker ps --format '{{.Names}}' | grep -q '^bgx-postgres$'; then
            echo "[db-dump] bgx-postgres container is not running. Try: make db-up" >&2
            exit 1
        fi
        echo "[db-dump] dumping local Postgres → $OUT"
        docker exec bgx-postgres pg_dump \
            -U bgx -d bgx \
            "${PG_DUMP_FLAGS[@]}" \
            | gzip -9 > "$OUT"
        ;;
    prod)
        URL="${PROD_DATABASE_URL:-}"
        if [[ -z "$URL" ]]; then
            if ! command -v railway >/dev/null 2>&1; then
                echo "[db-dump] PROD_DATABASE_URL is unset and 'railway' CLI is not installed." >&2
                echo "[db-dump]   - Set PROD_DATABASE_URL=postgres://…  OR" >&2
                echo "[db-dump]   - Install: npm i -g @railway/cli && railway link" >&2
                exit 1
            fi
            echo "[db-dump] no PROD_DATABASE_URL — falling back to 'railway run' (link the project first)"
            URL="$(railway variables --service postgres --kv 2>/dev/null | awk -F= '/^DATABASE_URL=/{ sub(/^DATABASE_URL=/,""); print; exit }')"
            if [[ -z "$URL" ]]; then
                echo "[db-dump] couldn't resolve DATABASE_URL via 'railway variables'. Pass PROD_DATABASE_URL explicitly." >&2
                exit 1
            fi
        fi
        # Normalize postgres:// → postgresql://, pg_dump accepts both but
        # this matches what the FastAPI app does internally and keeps
        # Railway's default URL form working.
        URL="${URL/#postgres:\/\//postgresql://}"
        echo "[db-dump] dumping prod Postgres → $OUT"
        docker run --rm postgres:16-alpine pg_dump \
            "${PG_DUMP_FLAGS[@]}" \
            "$URL" \
            | gzip -9 > "$OUT"
        ;;
    url)
        URL="${URL_ARG/#postgres:\/\//postgresql://}"
        echo "[db-dump] dumping $URL → $OUT"
        docker run --rm postgres:16-alpine pg_dump \
            "${PG_DUMP_FLAGS[@]}" \
            "$URL" \
            | gzip -9 > "$OUT"
        ;;
esac

SIZE="$(du -h "$OUT" | awk '{print $1}')"
echo "[db-dump] ✓ wrote $OUT ($SIZE)"
