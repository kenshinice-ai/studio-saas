#!/usr/bin/env bash
# 双击启动【公网测试模式】：环境 → PostgreSQL → 迁移 → 应用 → 健康检查 → Tunnel。
# 关闭这个终端窗口会停止由本启动器启动的应用和隧道。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_ROOT/scripts/startup_common.sh"

RUNTIME_DIR="$PROJECT_ROOT/.runtime"
RUNTIME_ENV="$RUNTIME_DIR/online.env"
[ -f "$RUNTIME_ENV" ] || die \
  "Portable runtime configuration is missing: $RUNTIME_ENV"
set -a
# shellcheck disable=SC1090
source "$RUNTIME_ENV"
set +a

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
DATA_DIR="$RUNTIME_DIR/cms-data"
LOG_DIR="$RUNTIME_DIR/logs"
CREDENTIALS_DIR="$RUNTIME_DIR/credentials"
CREDENTIAL_FILE="$CREDENTIALS_DIR/pilot-credentials.txt"
CLOUDFLARE_DIR="$RUNTIME_DIR/cloudflare"
CF_CREDENTIALS="$CLOUDFLARE_DIR/tunnel-credentials.json"
TUNNEL_NAME="${STUDIOSAAS_TUNNEL_NAME:-}"
APP_PID_FILE="$LOG_DIR/online-app.pid"
TUNNEL_PID_FILE="$LOG_DIR/online-tunnel.pid"
STOP_REQUEST_FILE="$LOG_DIR/online-stop.request"
mkdir -p "$LOG_DIR" "$DATA_DIR" "$CREDENTIALS_DIR" "$CLOUDFLARE_DIR"
rm -f "$STOP_REQUEST_FILE"

say "Checking and installing required environment"
ensure_brew_command cloudflared cloudflared
ensure_brew_command curl curl
ensure_brew_command lsof lsof
ensure_postgres_tools
PYTHON="$(ensure_python_environment "$PROJECT_ROOT")"

[ -r "$CF_CREDENTIALS" ] || die \
  "Portable Tunnel credentials are missing: $CF_CREDENTIALS"
[ -n "$TUNNEL_NAME" ] || die \
  "STUDIOSAAS_TUNNEL_NAME is required in $RUNTIME_ENV."

say "Checking PostgreSQL"
if [ -n "$CUSTOM_DATABASE_URL" ]; then
  ensure_database_connection "$DATABASE_URL"
else
  ensure_postgres_running "$DB_HOST" "$DB_PORT"
  ensure_database_exists "$DB_HOST" "$DB_PORT" "$DB_NAME"
fi

say "Applying ordered database migrations"
(cd "$PROJECT_ROOT/backend" && STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/run_migrations.py)

say "Checking the existing StudioSaaS Super Admin login without changing its password"
(
  cd "$PROJECT_ROOT/backend"
  STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
    "$PYTHON" scripts/seed_super_admin.py \
      --email "$ADMIN_EMAIL" \
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
  CMS_DATA_DIR="$DATA_DIR" \
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
# The project-local credential JSON and explicit URL make the connector
# independent of ~/.cloudflared and of the folder's absolute location.
cloudflared tunnel --url "http://localhost:$PORT" \
  run --credentials-file "$CF_CREDENTIALS" "$TUNNEL_NAME" >>"$LOG_DIR/cloudflared.log" 2>&1 &
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
echo "  配置:  $RUNTIME_ENV"
echo "  凭据:  $CREDENTIAL_FILE"
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
