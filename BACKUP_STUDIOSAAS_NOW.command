#!/usr/bin/env bash
# 双击备份：pg_dump 到 backups/postgres/，保留最近 14 份。
# 建议每次公网测试前双击一次。恢复演练见 docs/Admin_Guide.md。
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
DATABASE_URL="${STUDIOSAAS_DATABASE_URL:-postgresql://$(whoami)@localhost:5432/studiosaas_local_test}"

cd "$PROJECT_ROOT/backend"
STUDIOSAAS_DATABASE_URL="$DATABASE_URL" \
  "$PROJECT_ROOT/.venv/bin/python" scripts/backup_postgres.py backup --keep 14

echo ""
echo "最近的备份："
ls -lt "$PROJECT_ROOT/backups/postgres/" | head -5
echo ""
read -n 1 -s -r -p "完成。按任意键关闭窗口..."
