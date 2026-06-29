#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/letspaint-cms"
DATA_DIR="$APP_DIR/data"
SRC_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
APP_USER="${APP_USER:-ubuntu}"

if [ "$(id -u)" -ne 0 ]; then
  echo "请用 sudo 运行: sudo bash deploy/aws/install_lightsail.sh"
  exit 1
fi

echo "① 安装系统依赖"
apt-get update
apt-get install -y python3 python3-venv python3-pip nginx curl unzip lsof rsync

echo "② 创建目录"
mkdir -p "$APP_DIR" "$DATA_DIR" "$DATA_DIR/backups" "$DATA_DIR/photos" "$DATA_DIR/portfolio"

# Copy application code, never overwrite mutable data.
echo "③ 复制 CMS 程序到 $APP_DIR"
rsync -a --delete \
  --exclude 'data/' --exclude 'database.json' --exclude 'database.json.tmp' \
  --exclude 'photos/' --exclude 'portfolio/' --exclude 'backups/' \
  --exclude '.api_secret' --exclude '.cms_password' --exclude '.cms_config.json' \
  --exclude 'release/' --exclude 'cleanup_*/' --exclude '__pycache__/' \
  "$SRC_DIR/" "$APP_DIR/"

chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 700 "$DATA_DIR"

# Create empty DB only if this is a brand-new server.
if [ ! -f "$DATA_DIR/database.json" ]; then
  echo '{"students":[],"logs":[],"rosters":{},"pending":[],"packages":[],"rev":1}' > "$DATA_DIR/database.json"
  chown "$APP_USER:$APP_USER" "$DATA_DIR/database.json"
  chmod 600 "$DATA_DIR/database.json"
fi

echo "④ 创建 Python venv 并安装依赖"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

# Try local vendor download. Failure is not fatal because CDN fallback remains.
echo "⑤ 下载前端 vendor 依赖（失败不影响启动，会回退 CDN）"
sudo -u "$APP_USER" bash -lc "cd '$APP_DIR' && LPCMS_VENV='$APP_DIR/.venv' CMS_DATA_DIR='$DATA_DIR' ./cms.sh vendor" || true

echo "⑥ 安装 systemd 服务"
cp "$APP_DIR/deploy/aws/letspaint-cms.service" /etc/systemd/system/letspaint-cms.service
systemctl daemon-reload
systemctl enable letspaint-cms
systemctl restart letspaint-cms

echo "⑦ 配置 Nginx 反向代理"
cp "$APP_DIR/deploy/aws/nginx-letspaint.conf" /etc/nginx/sites-available/letspaint-cms
ln -sf /etc/nginx/sites-available/letspaint-cms /etc/nginx/sites-enabled/letspaint-cms
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

echo "⑧ 状态检查"
sleep 2
systemctl --no-pager --full status letspaint-cms || true
curl -s http://127.0.0.1:8000/api/ping || true
echo ""
echo "✅ 安装完成"
echo "访问: http://13.238.231.137/"
echo "数据目录: $DATA_DIR"
echo "日志: sudo journalctl -u letspaint-cms -f"
