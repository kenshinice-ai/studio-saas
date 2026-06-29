#!/usr/bin/env bash
set -euo pipefail
APP_DIR="/opt/letspaint-cms"
DATA_DIR="${CMS_DATA_DIR:-$APP_DIR/data}"
OUT_DIR="$APP_DIR/server_backups"
mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/letspaint-data-$TS.tar.gz"

items=()
for item in database.json photos portfolio backups .api_secret .cms_password .cms_config.json; do
  [ -e "$DATA_DIR/$item" ] && items+=("$item")
done
if [ "${#items[@]}" -eq 0 ]; then
  echo "❌ 没有找到可备份的数据: $DATA_DIR"
  exit 1
fi

tar -czf "$OUT" -C "$DATA_DIR" "${items[@]}"
chmod 600 "$OUT"
find "$OUT_DIR" -name 'letspaint-data-*.tar.gz' -type f -mtime +30 -delete
echo "✅ 本地备份已生成: $OUT"
