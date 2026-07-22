#!/usr/bin/env bash
# Start the local StudioSaaS stack in a strict, observable sequence.

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$PROJECT_ROOT/scripts/startup_common.sh"

APP_ROOT="$PROJECT_ROOT/backend"
DB_NAME="${STUDIOSAAS_DB_NAME:-studiosaas_local_test}"
DB_USER="${STUDIOSAAS_DB_USER:-$(whoami)}"
DB_HOST="${STUDIOSAAS_DB_HOST:-localhost}"
DB_PORT="${STUDIOSAAS_DB_PORT:-5432}"
PORT="${PORT:-8899}"
ADMIN_EMAIL="admin@studiosaas.local"
ADMIN_PASSWORD="${STUDIOSAAS_ADMIN_PASSWORD:-StudioSaaS@LetsPaint2026!}"
CUSTOM_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-}"
DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}}"
DATA_DIR="${CMS_DATA_DIR:-/private/tmp/studiosaas_cms_data}"
SEED_DEMO="${STUDIOSAAS_SEED_DEMO:-0}"
STUDENTS_PER_TENANT="${STUDENTS_PER_TENANT:-24}"
LOG_DIR="$HOME/.studiosaas"
APP_PID_FILE="$LOG_DIR/local-app.pid"
mkdir -p "$LOG_DIR" "$DATA_DIR"

say "Checking and installing required environment"
ensure_brew_command curl curl
ensure_brew_command lsof lsof
ensure_postgres_tools
PYTHON="$(ensure_python_environment "$PROJECT_ROOT")"

say "Checking PostgreSQL"
if [ -n "$CUSTOM_DATABASE_URL" ]; then
  ensure_database_connection "$DATABASE_URL"
else
  ensure_postgres_running "$DB_HOST" "$DB_PORT"
  ensure_database_exists "$DB_HOST" "$DB_PORT" "$DB_NAME"
fi

say "Applying ordered database migrations"
(
  cd "$APP_ROOT"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/run_migrations.py
)

if [ "$SEED_DEMO" = "1" ]; then
  say "Seeding explicitly requested demo data"
  (
    cd "$APP_ROOT"
    STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
      "$PYTHON" scripts/seed_random_demo_data.py --students-per-tenant "$STUDENTS_PER_TENANT"
  )
elif [ "$SEED_DEMO" != "0" ]; then
  die "STUDIOSAAS_SEED_DEMO must be 0 or 1."
else
  say "Skipping demo data (set STUDIOSAAS_SEED_DEMO=1 to opt in)"
fi

say "Ensuring local Super Admin login"
(
  cd "$APP_ROOT"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
    "$PYTHON" scripts/seed_super_admin.py \
      --email "$ADMIN_EMAIL" \
      --password "$ADMIN_PASSWORD" \
      --reset-password \
      --credential-file "$HOME/.studiosaas/pilot-credentials.txt" \
      --no-print-password
)

say "Checking managed process and port $PORT"
stop_managed_process "$APP_PID_FILE" "server.py"
require_free_port "$PORT"

APP_PID=""
cleanup() {
  [ -z "$APP_PID" ] || kill "$APP_PID" 2>/dev/null || true
  rm -f "$APP_PID_FILE"
}
trap cleanup EXIT INT TERM

say "Starting StudioSaaS application"
(
  cd "$APP_ROOT"
  exec env \
  PORT="$PORT" \
  CMS_DATA_DIR="$DATA_DIR" \
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
  STUDIOSAAS_PUBLIC_BASE_DOMAIN=localhost \
  "$PYTHON" server.py
) >>"$LOG_DIR/local-app.log" 2>&1 &
APP_PID=$!
printf "%s\n" "$APP_PID" >"$APP_PID_FILE"
wait_for_url "http://localhost:$PORT/v1/health" "Local StudioSaaS health" 45

printf "\nStudioSaaS is ready:\n"
printf "  Super Admin:        http://localhost:%s/super-admin\n" "$PORT"
printf "  Let's Paint Studio: http://localhost:%s/lets-paint-studio\n" "$PORT"
printf "  Health:             http://localhost:%s/v1/health\n" "$PORT"
printf "  Log:                %s/local-app.log\n\n" "$LOG_DIR"

wait "$APP_PID"
