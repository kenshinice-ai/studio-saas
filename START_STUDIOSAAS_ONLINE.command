#!/usr/bin/env bash
# 双击启动【公网测试模式】：本地服务 + Cloudflare 隧道 → https://studiosaas.cc.cd
# 关闭这个终端窗口 = 同时停掉服务和隧道（按需打开，不常驻）。
# 与 START_STUDIOSAAS_LOCAL 不同：不重灌数据、不重置密码，只启动。

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$(whoami)@localhost:5432/studiosaas_local_test}"
PORT=8899
LOG_DIR="$HOME/.studiosaas"
mkdir -p "$LOG_DIR"

echo "==> 检查 PostgreSQL"
pg_isready -h localhost -p 5432 >/dev/null || {
  brew services start postgresql@18 2>/dev/null || brew services start postgresql 2>/dev/null || true
  sleep 2
  pg_isready -h localhost -p 5432
}

echo "==> 应用未执行的数据库迁移（幂等，不动数据）"
(cd "$PROJECT_ROOT/backend" && STUDIOSAAS_DATABASE_URL="$DATABASE_URL" "$PYTHON" scripts/run_migrations.py)

echo "==> 清理端口 $PORT 上的旧进程"
lsof -tiTCP:$PORT -sTCP:LISTEN -nP 2>/dev/null | xargs kill 2>/dev/null || true
pkill -f "cloudflared tunnel run studiosaas" 2>/dev/null || true
sleep 1

echo "==> 启动 Cloudflare 隧道（日志: $LOG_DIR/cloudflared.log）"
/opt/homebrew/bin/cloudflared tunnel run studiosaas >>"$LOG_DIR/cloudflared.log" 2>&1 &
TUNNEL_PID=$!
trap 'kill "$TUNNEL_PID" 2>/dev/null || true' EXIT

echo ""
echo "  公网:  https://studiosaas.cc.cd"
echo "  本地:  http://localhost:$PORT"
echo "  停止:  关闭本窗口，或双击 STOP_STUDIOSAAS_ONLINE.command"
echo ""

cd "$PROJECT_ROOT/backend"
PORT=$PORT \
COOKIE_SECURE=1 \
STUDIOSAAS_ENV=pilot \
STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
STUDIOSAAS_PUBLIC_BASE_DOMAIN=studiosaas.cc.cd \
"$PYTHON" server.py
