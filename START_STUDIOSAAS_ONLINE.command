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
PORT="${PORT:-8901}"
PUBLIC_URL="${STUDIOSAAS_PUBLIC_URL:-https://studiosaas.cc.cd}"
PUBLIC_BASE_DOMAIN="${STUDIOSAAS_PUBLIC_BASE_DOMAIN:-studiosaas.cc.cd}"
EXPECTED_APP_VERSION="$(tr -d '[:space:]' < "$PROJECT_ROOT/VERSION")"
ADMIN_EMAIL="admin@studiosaas.local"
ADMIN_PASSWORD="${STUDIOSAAS_ADMIN_PASSWORD:-}"
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
CF_CREDENTIALS="${STUDIOSAAS_TUNNEL_CREDENTIALS:-}"
TUNNEL_NAME="${STUDIOSAAS_TUNNEL_NAME:-}"
if [ -z "$CF_CONFIG" ] && [ -z "$CF_CREDENTIALS" ]; then
  die "Cloudflare Tunnel is not configured. Provide ~/.cloudflared/config.yml, or explicitly set STUDIOSAAS_TUNNEL_CREDENTIALS and STUDIOSAAS_TUNNEL_NAME."
fi
if [ -z "$CF_CONFIG" ] && [ -z "$TUNNEL_NAME" ]; then
  die "STUDIOSAAS_TUNNEL_NAME is required when no Cloudflare config file is present."
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
ADMIN_ARGS=(
  --email "$ADMIN_EMAIL"
  --no-print-password
)
if [ -n "$ADMIN_PASSWORD" ]; then
  ADMIN_ARGS+=(
    --password "$ADMIN_PASSWORD"
    --reset-password
    --credential-file "$HOME/.studiosaas/pilot-credentials.txt"
  )
fi
(
  cd "$PROJECT_ROOT/backend"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
    "$PYTHON" scripts/seed_super_admin.py "${ADMIN_ARGS[@]}"
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
  STUDIOSAAS_MODE=saas \
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
  STUDIOSAAS_PUBLIC_BASE_DOMAIN="$PUBLIC_BASE_DOMAIN" \
  "$PYTHON" server.py
) >>"$LOG_DIR/online-app.log" 2>&1 &
APP_PID=$!
printf "%s\n" "$APP_PID" >"$APP_PID_FILE"
wait_for_url "http://localhost:$PORT/v1/health" "Local StudioSaaS health" 45

say "Starting Cloudflare Tunnel"
if [ -n "$CF_CONFIG" ]; then
  # The config file is authoritative for both tunnel identity and ingress.
  # Supplying a hard-coded name here can override a rotated tunnel and attach
  # the public hostname to an obsolete connector.
  cloudflared tunnel --config "$CF_CONFIG" run >>"$LOG_DIR/cloudflared.log" 2>&1 &
else
  cloudflared tunnel --url "http://localhost:$PORT" \
    run --credentials-file "$CF_CREDENTIALS" "$TUNNEL_NAME" >>"$LOG_DIR/cloudflared.log" 2>&1 &
fi
TUNNEL_PID=$!
printf "%s\n" "$TUNNEL_PID" >"$TUNNEL_PID_FILE"
wait_for_url "$PUBLIC_URL/v1/health" "Public StudioSaaS health" 45

say "Verifying local/public release and database parity"
"$PYTHON" "$PROJECT_ROOT/backend/scripts/verify_tunnel_parity.py" \
  --local-base-url "http://localhost:$PORT" \
  --public-base-url "$PUBLIC_URL" \
  --expected-app-version "$EXPECTED_APP_VERSION" \
  --expected-mode saas

echo ""
echo "  公网:  $PUBLIC_URL"
echo "  本地:  http://localhost:$PORT"
echo "  停止:  关闭本窗口，或双击 STOP_STUDIOSAAS_ONLINE.command"
echo "  日志:  $LOG_DIR/online-app.log 和 $LOG_DIR/cloudflared.log"
echo "  提示:  本窗口只管理本次启动的 PID；演示前仍需确认 Cloudflare 没有旧连接器残留。"
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
