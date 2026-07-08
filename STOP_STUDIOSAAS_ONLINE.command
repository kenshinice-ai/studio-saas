#!/usr/bin/env bash
# 双击停止：Cloudflare 隧道 + 本地服务（8899）。
set -uo pipefail

echo "==> 停止 Cloudflare 隧道"
pkill -f "cloudflared tunnel run studiosaas" 2>/dev/null && echo "  已停止" || echo "  没有在跑"

echo "==> 停止本地服务 (端口 8899)"
PIDS="$(lsof -tiTCP:8899 -sTCP:LISTEN -nP 2>/dev/null || true)"
if [ -n "$PIDS" ]; then
  echo "$PIDS" | xargs kill 2>/dev/null || true
  echo "  已停止"
else
  echo "  没有在跑"
fi

echo ""
read -n 1 -s -r -p "完成。按任意键关闭窗口..."
