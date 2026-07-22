#!/usr/bin/env bash
# 双击启动【公网测试模式】：环境 → PostgreSQL → 迁移 → 应用 → 健康检查 → Tunnel。
# 关闭这个终端窗口会停止由本启动器启动的应用和隧道。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_ROOT/scripts/startup_common.sh"

DB_NAME="${STUDIOSAAS_DB_NAME:-studiosaas_local_test}"
DB_USER="${STUDIOSAAS_DB_USER:-$(whoami)}"
DB_HOST="${STUDIOSAAS_DB_HOST:-localhost}"
DB_PORT="${STUDIOSAAS_DB_PORT:-5432}"
CUSTOM_DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-}"
DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}}"
PORT="${PORT:-8899}"
PUBLIC_URL="${STUDIOSAAS_PUBLIC_URL:-https://studiosaas.cc.cd}"
ADMIN_EMAIL="admin@studiosaas.local"
ADMIN_PASSWORD="${STUDIOSAAS_ADMIN_PASSWORD:-StudioSaaS@LetsPaint2026!}"
LOG_DIR="$HOME/.studiosaas"
APP_PID_FILE="$LOG_DIR/online-app.pid"
TUNNEL_PID_FILE="$LOG_DIR/online-tunnel.pid"
STOP_REQUEST_FILE="$LOG_DIR/online-stop.request"
mkdir -p "$LOG_DIR"
rm -f "$STOP_REQUEST_FILE"

say "Checking and installing required environment"
ensure_brew_command cloudflared cloudflared
ensure_brew_command curl curl
ensure_brew_command lsof lsof
ensure_postgres_tools
PYTHON="$(ensure_python_environment "$PROJECT_ROOT")"

CF_CONFIG=""
for candidate in "$HOME/.cloudflared/config.yml" "$HOME/.cloudflared/config.yaml"; do
  if [ -f "$candidate" ]; then
    CF_CONFIG="$candidate"
    break
  fi
done
CF_CREDENTIALS="$(find "$HOME/.cloudflared" -maxdepth 1 -type f -name '*.json' -print -quit 2>/dev/null || true)"
if [ -z "$CF_CONFIG" ] && [ -z "$CF_CREDENTIALS" ]; then
  die "Cloudflare Tunnel is not configured. Run cloudflared tunnel login/create/route dns first."
fi

say "Checking PostgreSQL"
if [ -n "$CUSTOM_DATABASE_URL" ]; then
  ensure_database_connection "$DATABASE_URL"
else
  ensure_postgres_running "$DB_HOST" "$DB_PORT"
  ensure_database_exists "$DB_HOST" "$DB_PORT" "$DB_NAME"
fi

say "Applying ordered database migrations"
(cd "$PROJECT_ROOT/backend" && STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/run_migrations.py)

say "Ensuring the fixed StudioSaaS Super Admin login"
(
  cd "$PROJECT_ROOT/backend"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
    "$PYTHON" scripts/seed_super_admin.py \
      --email "$ADMIN_EMAIL" \
      --password "$ADMIN_PASSWORD" \
      --reset-password \
      --credential-file "$HOME/.studiosaas/pilot-credentials.txt" \
      --no-print-password
)

say "Checking managed processes and port $PORT"
stop_managed_process "$APP_PID_FILE" "server.py"
stop_managed_process "$TUNNEL_PID_FILE" "cloudflared"
require_free_port "$PORT"

APP_PID=""
TUNNEL_PID=""
cleanup() {
  [ -z "$TUNNEL_PID" ] || kill "$TUNNEL_PID" 2>/dev/null || true
  [ -z "$APP_PID" ] || kill "$APP_PID" 2>/dev/null || true
  rm -f "$APP_PID_FILE" "$TUNNEL_PID_FILE"
}
trap cleanup EXIT INT TERM

say "Starting StudioSaaS application"
(
  cd "$PROJECT_ROOT/backend"
  exec env \
  PORT="$PORT" \
  COOKIE_SECURE=1 \
  STUDIOSAAS_ENV=pilot \
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
  STUDIOSAAS_PUBLIC_BASE_DOMAIN=studiosaas.cc.cd \
  "$PYTHON" server.py
) >>"$LOG_DIR/online-app.log" 2>&1 &
APP_PID=$!
printf "%s\n" "$APP_PID" >"$APP_PID_FILE"
wait_for_url "http://localhost:$PORT/v1/health" "Local StudioSaaS health" 45

say "Starting Cloudflare Tunnel"
if [ -n "$CF_CONFIG" ]; then
  cloudflared tunnel --config "$CF_CONFIG" run studiosaas >>"$LOG_DIR/cloudflared.log" 2>&1 &
else
  cloudflared tunnel --url "http://localhost:$PORT" \
    run --credentials-file "$CF_CREDENTIALS" studiosaas >>"$LOG_DIR/cloudflared.log" 2>&1 &
fi
TUNNEL_PID=$!
printf "%s\n" "$TUNNEL_PID" >"$TUNNEL_PID_FILE"
wait_for_url "$PUBLIC_URL/v1/health" "Public StudioSaaS health" 45

echo ""
echo "  公网:  $PUBLIC_URL"
echo "  本地:  http://localhost:$PORT"
echo "  停止:  关闭本窗口，或双击 STOP_STUDIOSAAS_ONLINE.command"
echo "  日志:  $LOG_DIR/online-app.log 和 $LOG_DIR/cloudflared.log"
echo ""

while kill -0 "$APP_PID" 2>/dev/null && kill -0 "$TUNNEL_PID" 2>/dev/null; do
  sleep 2
done
if [ -f "$STOP_REQUEST_FILE" ]; then
  rm -f "$STOP_REQUEST_FILE"
  printf "\nStudioSaaS online stack stopped cleanly.\n"
  exit 0
fi
die "The application or Cloudflare Tunnel stopped unexpectedly. Check the log files above."
