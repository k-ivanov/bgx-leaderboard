#!/usr/bin/env bash
# Restore a Postgres dump from db_dumps/ into a target database.
#
# Modes:
#   ./scripts/db-restore.sh local <file>           # local docker postgres
#   ./scripts/db-restore.sh prod  <file>           # prod via $PROD_DATABASE_URL or `railway run`
#   ./scripts/db-restore.sh url   <URL> <file>     # arbitrary URL
#
# <file> is a path relative to the project root or an absolute path. Files
# ending in .gz are decompressed inline.
#
# Why a separate script: production seeding and ad-hoc restores are
# fundamentally the same operation — write SQL to a target — but they
# carry different risks. Having one script with a target check keeps the
# blast radius obvious in shell history and CI logs.
#
# Notes:
#   - Restores into 'prod' will refuse to run unless --yes is passed,
#     because pointing the wrong DATABASE_URL at this script will
#     overwrite live data.
#   - Use --data-only to skip schema (assumes target already migrated).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

usage() {
    sed -n '2,22p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 2
}

if [[ $# -lt 2 ]]; then usage; fi

MODE="$1"; shift
URL_ARG=""
case "$MODE" in
    local|prod) ;;
    url)
        if [[ $# -lt 2 ]]; then echo "[db-restore] 'url' mode needs URL and file." >&2; usage; fi
        URL_ARG="$1"; shift
        ;;
    -h|--help) usage ;;
    *) echo "[db-restore] unknown mode: $MODE" >&2; usage ;;
esac

FILE_ARG="$1"; shift
if [[ ! "$FILE_ARG" = /* ]]; then
    FILE="$ROOT/$FILE_ARG"
else
    FILE="$FILE_ARG"
fi

CONFIRM=false
DATA_ONLY=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --yes|--force) CONFIRM=true ;;
        --data-only)   DATA_ONLY=true ;;
        *) echo "[db-restore] unknown flag: $1" >&2; usage ;;
    esac
    shift
done

if [[ ! -f "$FILE" ]]; then
    echo "[db-restore] dump file not found: $FILE" >&2
    exit 1
fi

# Resolve target URL. For local, we go through the docker container so we
# don't need a host psql; for prod/url we use a one-off postgres:16 image.
case "$MODE" in
    local)
        if ! docker ps --format '{{.Names}}' | grep -q '^bgx-postgres$'; then
            echo "[db-restore] bgx-postgres container is not running. Try: make db-up" >&2
            exit 1
        fi
        TARGET_DESC="local docker postgres (bgx-postgres)"
        ;;
    prod)
        URL="${PROD_DATABASE_URL:-}"
        if [[ -z "$URL" ]]; then
            if ! command -v railway >/dev/null 2>&1; then
                echo "[db-restore] PROD_DATABASE_URL is unset and 'railway' CLI is not installed." >&2
                exit 1
            fi
            # Try the Postgres service under common name casings. Prefer
            # DATABASE_PUBLIC_URL — DATABASE_URL points to *.railway.internal
            # which only resolves inside Railway's private network, not from
            # this laptop.
            vars=""
            for svc in Postgres postgres postgres-db; do
                if vars="$(railway variables --service "$svc" --kv 2>/dev/null)" && [[ -n "$vars" ]]; then
                    break
                fi
                vars=""
            done
            if [[ -z "$vars" ]]; then
                echo "[db-restore] couldn't read variables from any known Postgres service name (tried: Postgres, postgres, postgres-db)." >&2
                echo "[db-restore] check 'railway status' / 'railway variables --service <name>' or pass PROD_DATABASE_URL=… directly." >&2
                exit 1
            fi
            URL="$(printf '%s\n' "$vars" | awk -F= '/^DATABASE_PUBLIC_URL=/{ sub(/^DATABASE_PUBLIC_URL=/,""); print; exit }')"
            if [[ -z "$URL" ]]; then
                URL="$(printf '%s\n' "$vars" | awk -F= '/^DATABASE_URL=/{ sub(/^DATABASE_URL=/,""); print; exit }')"
            fi
            if [[ -z "$URL" ]]; then
                echo "[db-restore] Postgres service has neither DATABASE_PUBLIC_URL nor DATABASE_URL. Pass PROD_DATABASE_URL=…" >&2
                exit 1
            fi
            if [[ "$URL" == *.railway.internal* ]]; then
                echo "[db-restore] only an internal *.railway.internal URL is exposed; that host won't resolve from your laptop." >&2
                echo "[db-restore] enable a public proxy on the Postgres service (DATABASE_PUBLIC_URL) or pass PROD_DATABASE_URL=… directly." >&2
                exit 1
            fi
        fi
        URL="${URL/#postgres:\/\//postgresql://}"
        TARGET_DESC="PRODUCTION ($(echo "$URL" | sed -E 's#://[^@]+@#://***@#'))"
        ;;
    url)
        URL="${URL_ARG/#postgres:\/\//postgresql://}"
        TARGET_DESC="$(echo "$URL" | sed -E 's#://[^@]+@#://***@#')"
        ;;
esac

echo "[db-restore] target: $TARGET_DESC"
echo "[db-restore] file:   $FILE"
$DATA_ONLY && echo "[db-restore] mode:   --data-only"

# Confirmation gate. Always require for prod; require for any restore that
# might overwrite (full dumps DROP IF EXISTS, so they will).
if [[ "$MODE" == "prod" ]] && ! $CONFIRM; then
    echo "[db-restore] refusing to write to PRODUCTION without --yes." >&2
    exit 1
fi

# Choose the decompression frontend.
if [[ "$FILE" == *.gz ]]; then
    DECOMPRESS=(gunzip -c "$FILE")
else
    DECOMPRESS=(cat "$FILE")
fi

# --data-only assumes the target schema already exists (e.g. via Alembic) and
# the dump only carries COPY blocks. Existing rows would collide on PKs, so we
# pre-truncate the exact tables the dump targets. Table names come from the
# dump itself (grep is restricted to `[a-zA-Z_]+`, so no injection surface).
TABLES=""
if $DATA_ONLY; then
    TABLES="$("${DECOMPRESS[@]}" | grep -oE '^COPY public\.[a-zA-Z_]+' | awk '{print $2}' | paste -sd, -)"
    if [[ -z "$TABLES" ]]; then
        echo "[db-restore] --data-only: no 'COPY public.<table>' lines found in dump; nothing to truncate." >&2
        exit 1
    fi
    echo "[db-restore] --data-only: will TRUNCATE ${TABLES} RESTART IDENTITY CASCADE before COPY"
fi

case "$MODE" in
    local)
        # -e: stop on first SQL error so a bad dump fails loudly.
        if $DATA_ONLY; then
            echo "[db-restore] truncating local tables…"
            docker exec -i bgx-postgres psql -U bgx -d bgx -v ON_ERROR_STOP=1 \
                -c "TRUNCATE TABLE ${TABLES} RESTART IDENTITY CASCADE;" >/tmp/db-restore-truncate.log
        fi
        echo "[db-restore] streaming into local Postgres…"
        "${DECOMPRESS[@]}" | docker exec -i bgx-postgres psql -U bgx -d bgx -v ON_ERROR_STOP=1 >/tmp/db-restore-local.log
        ;;
    prod|url)
        if $DATA_ONLY; then
            echo "[db-restore] truncating tables on ${TARGET_DESC}…"
            docker run --rm -i postgres:16-alpine \
                psql "$URL" -v ON_ERROR_STOP=1 \
                -c "TRUNCATE TABLE ${TABLES} RESTART IDENTITY CASCADE;" >/tmp/db-restore-truncate.log
        fi
        echo "[db-restore] streaming into ${TARGET_DESC}…"
        "${DECOMPRESS[@]}" \
            | docker run --rm -i postgres:16-alpine \
                psql "$URL" -v ON_ERROR_STOP=1 \
            >/tmp/db-restore-target.log
        ;;
esac

echo "[db-restore] ✓ done. (Last 5 lines of psql log:)"
tail -5 /tmp/db-restore-local.log /tmp/db-restore-target.log 2>/dev/null | tail -10 || true
