#!/usr/bin/env bash
# 双击停止由 START_STUDIOSAAS_ONLINE.command 启动的进程。
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
source "$PROJECT_ROOT/scripts/startup_common.sh"
LOG_DIR="$HOME/.studiosaas"
touch "$LOG_DIR/online-stop.request"

say "Stopping managed StudioSaaS application"
stop_managed_process "$LOG_DIR/online-app.pid" "server.py"

say "Stopping managed Cloudflare Tunnel"
stop_managed_process "$LOG_DIR/online-tunnel.pid" "cloudflared"

echo ""
read -n 1 -s -r -p "完成。按任意键关闭窗口..."
