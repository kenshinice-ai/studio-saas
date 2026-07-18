#!/usr/bin/env bash
# Start the local StudioSaaS stack with PostgreSQL, schema, demo data, and API.

set -euo pipefail

# Homebrew versioned PostgreSQL formulae are keg-only, so their client tools
# are not necessarily available on the default PATH.
for pg_bin in /opt/homebrew/opt/postgresql@18/bin /opt/homebrew/opt/postgresql@17/bin /opt/homebrew/opt/postgresql@16/bin; do
  if [ -d "$pg_bin" ]; then
    export PATH="$pg_bin:$PATH"
    break
  fi
done

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$PROJECT_ROOT/backend"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
DB_NAME="${STUDIOSAAS_DB_NAME:-studiosaas_local_test}"
DB_USER="${STUDIOSAAS_DB_USER:-$(whoami)}"
DB_HOST="${STUDIOSAAS_DB_HOST:-localhost}"
DB_PORT="${STUDIOSAAS_DB_PORT:-5432}"
PORT="${PORT:-}"
STUDENTS_PER_TENANT="${STUDENTS_PER_TENANT:-24}"
DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}}"
DATA_DIR="${CMS_DATA_DIR:-/private/tmp/studiosaas_cms_data}"
AUTO_STOP_PORT="${STUDIOSAAS_AUTO_STOP_PORT:-1}"

say() {
  printf "\n==> %s\n" "$1"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    printf "Missing required command: %s\n" "$1" >&2
    exit 1
  fi
}

say "Checking local tools"
need_cmd psql
need_cmd createdb
need_cmd pg_isready

if [ ! -x "$PYTHON" ]; then
  say "Creating Python virtual environment"
  python3 -m venv "$PROJECT_ROOT/.venv"
  "$PYTHON" -m pip install -r "$APP_ROOT/requirements.txt"
fi

say "Checking Python dependencies"
if ! "$PYTHON" -c "import flask, waitress, psycopg" >/dev/null 2>&1; then
  "$PYTHON" -m pip install -r "$APP_ROOT/requirements.txt"
fi

pick_port() {
  local preferred="${1:-8899}"
  local port

  if command -v lsof >/dev/null 2>&1; then
    port="$preferred"
    while [ "$port" -lt $((preferred + 20)) ]; do
      if [ -z "$(lsof -tiTCP:"$port" -sTCP:LISTEN -nP 2>/dev/null || true)" ]; then
        printf "%s\n" "$port"
        return 0
      fi
      port=$((port + 1))
    done
    printf "No free local port found from %s to %s.\n" "$preferred" "$((preferred + 19))" >&2
    return 1
  fi

  "$PYTHON" - "$preferred" <<'PY'
import socket
import sys

preferred = int(sys.argv[1] or "8899")
for port in range(preferred, preferred + 20):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("0.0.0.0", port))
        except OSError:
            continue
        print(port)
        raise SystemExit(0)
raise SystemExit("No free local port found from %s to %s." % (preferred, preferred + 19))
PY
}

port_pids() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$1" -sTCP:LISTEN -nP 2>/dev/null | sort -u
  fi
}

stop_port_if_requested() {
  local port="$1"
  local pids
  pids="$(port_pids "$port" || true)"
  if [ -z "$pids" ]; then
    return 0
  fi

  if [ "$AUTO_STOP_PORT" != "1" ]; then
    printf "Port %s is already in use by PID(s): %s\n" "$port" "$(printf "%s" "$pids" | tr '\n' ' ')" >&2
    printf "Stop them first, or run with PORT=8900.\n" >&2
    exit 1
  fi

  say "Stopping existing local server on port $port"
  printf "%s\n" "$pids" | while IFS= read -r pid; do
    [ -n "$pid" ] || continue
    kill "$pid" 2>/dev/null || true
  done
  sleep 1

  pids="$(port_pids "$port" || true)"
  if [ -n "$pids" ]; then
    printf "%s\n" "$pids" | while IFS= read -r pid; do
      [ -n "$pid" ] || continue
      kill -9 "$pid" 2>/dev/null || true
    done
    sleep 1
  fi

  pids="$(port_pids "$port" || true)"
  if [ -n "$pids" ]; then
    printf "Could not free port %s. Remaining PID(s): %s\n" "$port" "$(printf "%s" "$pids" | tr '\n' ' ')" >&2
    printf "Open Activity Monitor or Terminal and stop the old Python server, then rerun this command.\n" >&2
    exit 1
  fi
}

PREFERRED_PORT="${PORT:-8899}"
stop_port_if_requested "$PREFERRED_PORT"
PORT="$(pick_port "$PREFERRED_PORT")"

say "Checking PostgreSQL"
if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" >/dev/null 2>&1; then
  if command -v brew >/dev/null 2>&1; then
    brew services start postgresql@18 >/dev/null 2>&1 || brew services start postgresql >/dev/null 2>&1 || true
  fi
fi
pg_isready -h "$DB_HOST" -p "$DB_PORT"

say "Creating database if needed: $DB_NAME"
if ! psql -h "$DB_HOST" -p "$DB_PORT" -d "$DB_NAME" -c "select 1" >/dev/null 2>&1; then
  createdb -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME"
fi

say "Applying ordered database migrations"
(
  cd "$APP_ROOT"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/run_migrations.py
)

say "Seeding randomized demo data"
(
  cd "$APP_ROOT"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/seed_random_demo_data.py --students-per-tenant "$STUDENTS_PER_TENANT"
) || {
  printf "\nWarning: demo data seed failed. The web server will still start.\n" >&2
  printf "Run the seed manually after checking PostgreSQL:\n" >&2
  printf "  cd %s && STUDIOSAAS_DATABASE_URL=%s %s scripts/seed_random_demo_data.py --students-per-tenant %s\n" "$APP_ROOT" "$DATABASE_URL" "$PYTHON" "$STUDENTS_PER_TENANT" >&2
}

say "Generating privacy-safe media variants"
(
  cd "$APP_ROOT"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/backfill_media_variants.py
) || {
  printf "\nWarning: one or more existing images could not be prepared for safe display.\n" >&2
  printf "The server will start, but affected public images stay unavailable until the backfill succeeds.\n" >&2
}

say "Ensuring local Super Admin login"
# P0-1: if credentials were rotated (~/.studiosaas/pilot-credentials.txt),
# keep the rotated password instead of resetting back to the weak default.
PILOT_ADMIN_PW="$(awk '$1=="admin@studiosaas.local"{pw=$2} END{print pw}' "$HOME/.studiosaas/pilot-credentials.txt" 2>/dev/null || true)"
(
  cd "$APP_ROOT"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/seed_super_admin.py --reset-password ${PILOT_ADMIN_PW:+--password "$PILOT_ADMIN_PW"}
) || {
  printf "\nWarning: super admin seed failed. Login may fail until an admin user is seeded.\n" >&2
  printf "Run manually:\n" >&2
  printf "  cd %s && STUDIOSAAS_DATABASE_URL=%s %s scripts/seed_super_admin.py --reset-password\n" "$APP_ROOT" "$DATABASE_URL" "$PYTHON" >&2
}

say "Starting StudioSaaS"
printf "Super Admin: http://localhost:%s\n" "$PORT"
printf "Let's Paint Studio: http://localhost:%s/lets-paint-studio\n" "$PORT"
printf "Let's Play Piano: http://localhost:%s/lets-play-piano\n\n" "$PORT"

cd "$APP_ROOT"
PORT="$PORT" \
CMS_DATA_DIR="$DATA_DIR" \
STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
STUDIOSAAS_PUBLIC_BASE_DOMAIN=localhost \
"$PYTHON" server.py
