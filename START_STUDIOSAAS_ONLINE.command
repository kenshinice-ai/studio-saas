#!/usr/bin/env bash
# 双击启动【公网测试模式】：本地服务 + Cloudflare 隧道 → https://studiosaas.cc.cd
# 关闭这个终端窗口 = 同时停掉服务和隧道（按需打开，不常驻）。
# 与 START_STUDIOSAAS_LOCAL 不同：不重灌数据、不重置密码，只启动。

set -euo pipefail

for pg_bin in /opt/homebrew/opt/postgresql@18/bin /opt/homebrew/opt/postgresql@17/bin /opt/homebrew/opt/postgresql@16/bin; do
  if [ -d "$pg_bin" ]; then
    export PATH="$pg_bin:$PATH"
    break
  fi
done

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
PYTHON="$PROJECT_ROOT/.venv/bin/python"
DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$(whoami)@localhost:5432/studiosaas_local_test}"
PORT=8899
LOG_DIR="$HOME/.studiosaas"
mkdir -p "$LOG_DIR"

command -v cloudflared >/dev/null 2>&1 || {
  echo "缺少 cloudflared。请先运行: brew install cloudflared" >&2
  exit 1
}

CF_CONFIG=""
for candidate in "$HOME/.cloudflared/config.yml" "$HOME/.cloudflared/config.yaml"; do
  if [ -f "$candidate" ]; then
    CF_CONFIG="$candidate"
    break
  fi
done
CF_CREDENTIALS="$(find "$HOME/.cloudflared" -maxdepth 1 -type f -name '*.json' -print -quit 2>/dev/null || true)"
if [ -z "$CF_CONFIG" ] && [ -z "$CF_CREDENTIALS" ]; then
  echo "尚未配置 Cloudflare Tunnel。请先运行以下一次性命令：" >&2
  echo "  cloudflared tunnel login" >&2
  echo "  cloudflared tunnel create studiosaas" >&2
  echo "  cloudflared tunnel route dns studiosaas studiosaas.cc.cd" >&2
  echo "然后重新运行本启动器。" >&2
  exit 1
fi

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
if [ -n "$CF_CONFIG" ]; then
  /opt/homebrew/bin/cloudflared tunnel --config "$CF_CONFIG" run studiosaas >>"$LOG_DIR/cloudflared.log" 2>&1 &
else
  /opt/homebrew/bin/cloudflared tunnel --url "http://localhost:$PORT" \
    run --credentials-file "$CF_CREDENTIALS" studiosaas >>"$LOG_DIR/cloudflared.log" 2>&1 &
fi
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
