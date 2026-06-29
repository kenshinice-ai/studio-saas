#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/letspaint-cms"
DATA_DIR="$APP_DIR/data"
SRC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="${APP_USER:-ubuntu}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 运行: sudo bash deploy/aws/update_lightsail.sh"
  exit 1
fi

echo "① 更新程序文件（不会覆盖 data/）"
rsync -a --delete \
  --exclude 'data/' --exclude 'database.json' --exclude 'database.json.tmp' \
  --exclude 'photos/' --exclude 'portfolio/' --exclude 'backups/' \
  --exclude '.api_secret' --exclude '.cms_password' --exclude '.cms_config.json' \
  --exclude 'release/' --exclude 'cleanup_*/' --exclude '__pycache__/' \
  "$SRC_DIR/" "$APP_DIR/"
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 700 "$DATA_DIR"

if [ -f "$APP_DIR/requirements.txt" ]; then
  sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"
fi

echo "② 重启服务并检查"
systemctl restart letspaint-cms
sleep 2
curl -s http://127.0.0.1:8000/api/ping || true
echo ""
systemctl --no-pager --full status letspaint-cms || true
