#!/usr/bin/env bash
# 双击停止由 START_STUDIOSAAS_ONLINE.command 启动的进程。
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_ROOT/scripts/startup_common.sh"
LOG_DIR="$PROJECT_ROOT/.runtime/logs"
PORTABLE_DB_LEASE="$PROJECT_ROOT/.runtime/database/active-session.json"
[ -d "$LOG_DIR" ] || die "Portable runtime log directory does not exist: $LOG_DIR"
touch "$LOG_DIR/online-stop.request"

say "Stopping managed StudioSaaS application"
stop_managed_process "$LOG_DIR/online-app.pid" "server.py"

say "Stopping managed Cloudflare Tunnel"
stop_managed_process "$LOG_DIR/online-tunnel.pid" "cloudflared"

if [ -f "$PORTABLE_DB_LEASE" ]; then
  say "Waiting for portable database snapshot and handoff"
  for _attempt in $(seq 1 120); do
    [ -f "$PORTABLE_DB_LEASE" ] || break
    sleep 0.5
  done
  [ ! -f "$PORTABLE_DB_LEASE" ] || die \
    "Database handoff did not finish within 60 seconds. Keep the other Mac stopped and inspect the online launcher error before recovery."
  printf "  OK: portable database handoff completed\n"
fi

echo ""
read -n 1 -s -r -p "完成。按任意键关闭窗口..."
