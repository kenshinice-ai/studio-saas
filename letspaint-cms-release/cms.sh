#!/bin/bash
# ═══════════════════════════════════════════════════════════════════
#  Let's Paint Studio CMS — 管理脚本 / Management Script
# ───────────────────────────────────────────────────────────────────
#
#  用法 / Usage:
#
#    ./cms.sh              启动全部服务（Flask + Cloudflare 隧道）
#                          Start all services (Flask + Cloudflare tunnel)
#
#    ./cms.sh --no-tunnel  只启动 Flask，不开外网隧道（局域网模式）
#                          Start Flask only, no public tunnel (LAN mode)
#
#    ./cms.sh setup        【首次/系统升级后】创建 Python 环境并装齐全部依赖
#                          [First run / after OS upgrade] Build venv + install deps
#
#    ./cms.sh tunnel       单独开启外网隧道（Flask 已在运行时）
#    ./cms.sh tunnel stop  单独关闭外网隧道，Flask 继续运行
#
#    ./cms.sh stop         停止所有运行中的服务
#                          Stop all running services
#
#    ./cms.sh restart      重启所有服务（先停止再启动）
#                          Restart all services (stop then start)
#
#    ./cms.sh status       查看当前运行状态和地址
#                          Show current status and URLs
#
#    ./cms.sh check        上线前检查（文件/权限/数据库/PWA/暴露风险）
#                          Preflight checks before going live
#
#    ./cms.sh package      生成正式发布 zip（不包含数据库/密钥/照片/备份）
#                          Build release zip without private data
#
#    ./cms.sh vendor       下载本地前端依赖（React/Tailwind/Babel），减少 CDN 依赖
#                          Download local frontend vendor scripts
#
#    ./cms.sh clean        清理生产目录杂项（移动到 cleanup_时间戳，不删除数据）
#                          Move non-production clutter aside
#
#    ./cms.sh logs         实时查看 Flask 和隧道日志（Ctrl+C 退出）
#                          Tail live logs (Ctrl+C to quit)
#
#    ./cms.sh server       【仅供 launchd plist 使用】前台运行 Flask
#                          [For launchd plist only] Run Flask in foreground
#
# ───────────────────────────────────────────────────────────────────
#  常用操作 / Common tasks:
#
#    首次启动 First start:     ./cms.sh
#    重启服务 Restart:         ./cms.sh restart
#    查看状态 Check status:    ./cms.sh status
#    查看日志 View logs:       ./cms.sh logs
#    上线检查 Preflight:       ./cms.sh check
#    打包发布 Package:         ./cms.sh package
#    停止服务 Stop:            ./cms.sh stop
#
#  日志文件 / Log files:
#    Flask:  /tmp/letspaint_flask.log
#    隧道:   /tmp/letspaint_tunnel.log
#
#  开机自启 / Auto-start on login:
#    1. 修改 cloudflare-setup/com.letspaintstudio.plist 中的路径
#       Edit the path in cloudflare-setup/com.letspaintstudio.plist
#    2. cp cloudflare-setup/com.letspaintstudio.plist ~/Library/LaunchAgents/
#    3. launchctl load ~/Library/LaunchAgents/com.letspaintstudio.plist
#    4. 验证: curl http://localhost:8000/api/ping
#       Verify: curl http://localhost:8000/api/ping
#
# ═══════════════════════════════════════════════════════════════════

PORT=8000
DIR="$(cd "$(dirname "$0")" && pwd)"
FLASK_LOG=/tmp/letspaint_flask.log
TUNNEL_LOG=/tmp/letspaint_tunnel.log
RELEASE_VERSION=4.3.3-aws-13.238.231.137
DATA_DIR="${CMS_DATA_DIR:-$DIR}"
CURL="$(command -v curl || echo /usr/bin/curl)"

# ── O2: 固定 Python 环境 / Pinned Python environment ────────────────
# venv 放在本地用户目录（不放进 iCloud 项目文件夹——venv 含上千个小文件，
# 会拖垮 iCloud 同步）。macOS 系统升级后只需重跑 ./cms.sh setup 即可恢复。
VENV="${LPCMS_VENV:-$HOME/.letspaint_venv}"
if [ -x "$VENV/bin/python3" ]; then
    PY="$VENV/bin/python3"
else
    PY="$(command -v python3 || echo python3)"
fi

# ── 内部工具 / Internal helpers ────────────────────────────────────

_flask_pid()  { lsof -t -i:$PORT 2>/dev/null | head -1; }
_tunnel_pid() { pgrep -f "cloudflared tunnel" 2>/dev/null | head -1; }

_lan_ip() {
    ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") {print $(i+1); exit}}'
    hostname -I 2>/dev/null | awk '{print $1}'
    ipconfig getifaddr en0 2>/dev/null
}


_free_port() {
    for PID in $(lsof -t -i:$PORT 2>/dev/null); do
        kill -9 "$PID" 2>/dev/null
        echo "   已终止 PID $PID / Killed PID $PID"
    done
    for i in $(seq 1 20); do
        sleep 0.5
        lsof -t -i:$PORT &>/dev/null || return 0
    done
    echo "   ❌ 端口 $PORT 无法释放 / Port $PORT cannot be freed"
    return 1
}

_do_stop() {
    local FPID=$(_flask_pid)
    local TPID=$(_tunnel_pid)
    local any=0
    if [ -n "$FPID" ]; then
        kill "$FPID" 2>/dev/null
        echo "   ✅ Flask (PID $FPID) 已停止 / stopped"
        any=1
    fi
    if [ -n "$TPID" ]; then
        kill "$TPID" 2>/dev/null
        echo "   ✅ 隧道 (PID $TPID) 已停止 / Tunnel stopped"
        any=1
    fi
    pkill -f "letspaint.*watchdog" 2>/dev/null
    [ "$any" = "0" ] && echo "   （无运行中的服务 / No services running）"
}

_start_flask() {
    echo "② 启动 Flask / Starting Flask..."
    _free_port || return 1
    cd "$DIR"
    # -u: 关闭 Python 输出缓冲，启动横幅和日志即时写入文件（否则 ./cms.sh logs 看不到）
    "$PY" -u server.py >> "$FLASK_LOG" 2>&1 &
    FLASK_PID=$!
    for i in $(seq 1 20); do
        sleep 0.5
        "$CURL" -s http://localhost:$PORT/api/ping 2>/dev/null | grep -q "ok" && break
        if [ "$i" = "20" ]; then
            echo "   ❌ Flask 启动失败 / Flask failed to start"
            echo "   查看日志: tail $FLASK_LOG"
            tail -5 "$FLASK_LOG"
            return 1
        fi
    done
    local LAN
    LAN=$(_lan_ip | head -1); [ -z "$LAN" ] && LAN="?"
    echo "   ✅ Flask 已就绪 PID $FLASK_PID / Flask ready"
    echo "      本地:   http://localhost:$PORT"
    echo "      局域网: http://$LAN:$PORT"
}

_start_tunnel() {
    if ! command -v cloudflared &>/dev/null; then
        echo "③ 跳过隧道 / Tunnel skipped (cloudflared not installed)"
        echo "   安装: brew install cloudflare/cloudflare/cloudflared"
        return
    fi
    echo "③ 启动 Cloudflare 隧道 / Starting tunnel..."
    > "$TUNNEL_LOG"   # 清空旧日志，防止 grep 匹配到上一次的地址 / Clear stale log before new tunnel
    cloudflared tunnel --url http://localhost:$PORT >> "$TUNNEL_LOG" 2>&1 &
    TUNNEL_PID=$!
    local URL=''
    for i in $(seq 1 30); do
        sleep 1
        URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1)
        [ -n "$URL" ] && break
    done
    if [ -n "$URL" ]; then
        echo "$URL" > "$DIR/current_url.txt"
        echo "   ✅ 外网地址 / Public URL: $URL"
        echo "      管理后台: $URL/"
        echo "      学员注册: $URL/register"
        echo "      已保存 current_url.txt / Saved"
        # Watchdog: update current_url.txt if tunnel reconnects with new URL
        (
            while sleep 15; do
                NEW=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | tail -1)
                SAVED=$(cat "$DIR/current_url.txt" 2>/dev/null)
                [ -n "$NEW" ] && [ "$NEW" != "$SAVED" ] && echo "$NEW" > "$DIR/current_url.txt"
            done
        ) &
    else
        echo "   ⚠️  未能获取隧道 URL / Could not get tunnel URL"
        echo "   查看日志: tail $TUNNEL_LOG"
    fi
}

_print_divider() {
    echo ""
    echo "════════════════════════════════════════"
    echo "  CMS 运行中 / Running  —  Ctrl+C 停止"
    echo "════════════════════════════════════════"
    echo ""
}


_check_required_files() {
    local missing=0
    local files=(server.py index.html register.html cms.sh requirements.txt manifest.json manifest-student.json sw.js logo.png logo-light.png icon-192.png icon-512.png apple-touch-icon.png)
    for f in "${files[@]}"; do
        if [ -f "$DIR/$f" ]; then echo "  ✅ $f"; else echo "  ❌ 缺少 $f"; missing=1; fi
    done
    return $missing
}

_do_check() {
    echo ""
    echo "🩺  Let's Paint CMS 上线检查 / Preflight check"
    echo "────────────────────────────────────────────"
    local FAIL=0

    echo "① 必需文件 / Required files"
    _check_required_files || FAIL=1

    echo ""
    echo "② Python / JSON 语法"
    cd "$DIR" || exit 1
    PYTHONPYCACHEPREFIX=/tmp/letspaint_pycache "$PY" -m py_compile server.py test_cms.py 2>/tmp/letspaint_check_py.err \
        && echo "  ✅ server.py / test_cms.py 语法 OK" \
        || { echo "  ❌ Python 语法检查失败"; cat /tmp/letspaint_check_py.err; FAIL=1; }
"$PY" - <<'PYJSON' || FAIL=1
import json, glob, os, sys
app_dir = os.getcwd()
data_dir = os.environ.get('CMS_DATA_DIR') or app_dir
checks = [(os.path.join(data_dir, 'database.json'), 'database.json'),
          (os.path.join(app_dir, 'manifest.json'), 'manifest.json'),
          (os.path.join(app_dir, 'manifest-student.json'), 'manifest-student.json')]
for path, label in checks:
    if label == 'database.json' and not os.path.exists(path):
        print(f'  ⚠️  {label} 不存在（新服务器首次运行或尚未迁移数据时正常）')
        continue
    try:
        json.load(open(path, encoding='utf-8'))
        print(f'  ✅ {label} JSON OK')
    except Exception as e:
        print(f'  ❌ {label} JSON 错误: {e}')
        sys.exit(1)
conflicts=[]
for pat in ['database *json','*.icloud','*conflict*','*冲突*']:
    conflicts += glob.glob(os.path.join(data_dir, pat))
if conflicts:
    print('  ⚠️  可能的 iCloud 冲突/占位文件:', ', '.join(os.path.basename(x) for x in sorted(set(conflicts))[:10]))
else:
    print('  ✅ 未发现明显 iCloud 冲突文件')
PYJSON
    "$PY" - <<'PYSTATIC' || FAIL=1
from pathlib import Path
import re, sys
s = Path('server.py').read_text(encoding='utf-8')
errors = []
if 'Flask(__name__, static_folder=None)' not in s:
    errors.append('Flask 未关闭根目录静态暴露 static_folder=None')
if 'def _public_file' not in s or 'send_from_directory(app.root_path' not in s:
    errors.append('未检测到根目录 allowlist 静态路由')
m = re.search(r'allowed\s*=\s*\{([\s\S]*?)\}', s)
if m:
    block = m.group(1)
    for private in ['database.json', '.api_secret', '.cms_config.json', '.cms_password', 'index.html.bak', 'backups']:
        if private in block:
            errors.append(f'allowlist 中包含私密项: {private}')
else:
    errors.append('未找到 public allowed 清单')
if errors:
    for e in errors:
        print('  ❌ 静态路由检查:', e)
    sys.exit(1)
print('  ✅ 静态文件 allowlist 检查 OK')
PYSTATIC

    echo ""
    echo "③ 私密文件权限 / Secret file permissions"
    for f in .api_secret .cms_password .cms_config.json; do
        if [ -f "$DATA_DIR/$f" ]; then
            perm=$(stat -f "%Lp" "$DATA_DIR/$f" 2>/dev/null || stat -c "%a" "$DATA_DIR/$f" 2>/dev/null)
            if [ "$perm" = "600" ]; then echo "  ✅ $f 权限 600"; else echo "  ⚠️  $f 权限 $perm（建议 600）"; fi
        fi
    done

    echo ""
    echo "④ 运行状态 / Runtime"
    if [ -n "$(_flask_pid)" ]; then
        PING=$("$CURL" -s -m 3 http://localhost:$PORT/api/ping 2>/dev/null)
        echo "  ✅ Flask 运行中: $PING"
        for path in /database.json /.api_secret /.cms_config.json /test_cms.py /index.html.bak; do
            code=$("$CURL" -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT$path" 2>/dev/null)
            if [ "$code" = "404" ] || [ "$code" = "401" ]; then echo "  ✅ 私密路径 $path 未公开 ($code)"; else echo "  ❌ 私密路径 $path 返回 $code"; FAIL=1; fi
        done
    else
        echo "  ℹ️  Flask 未运行，跳过 HTTP 暴露检查（启动后再跑 ./cms.sh check 更完整）"
    fi

    echo ""
    echo "⑤ 备份 / Backups"
    if [ -d "$DATA_DIR/backups" ]; then
        cnt=$(find "$DATA_DIR/backups" -name '*.json' -type f | wc -l | tr -d ' ')
        latest=$(find "$DATA_DIR/backups" -name '*.json' -type f -exec basename {} \; | sort | tail -1)
        echo "  ✅ 备份数量: $cnt"
        [ -n "$latest" ] && echo "  最近备份: $latest"
    else
        echo "  ⚠️  backups/ 不存在（首次运行后会自动创建）"
    fi

    echo ""
    echo "⑥ 生产目录提醒 / Cleanup hints"
    for f in _logo_preview.png _visual_check.png "Archive.zip" "Archive 2.zip" index.html.bak; do
        [ -e "$DIR/$f" ] && echo "  ⚠️  可移出生产目录: $f"
    done
    [ -d "$DIR/__pycache__" ] && echo "  ⚠️  可删除: __pycache__/"

    echo ""
    if [ "$FAIL" = "0" ]; then
        echo "✅ 检查完成：未发现阻塞上线的问题"
    else
        echo "❌ 检查完成：存在需要处理的问题"
        exit 1
    fi
}

_do_package() {
    cd "$DIR" || exit 1
    local OUTDIR="$DIR/release"
    local NAME="LetsPaintCMS-v${RELEASE_VERSION}-release.zip"
    local STAGE="/tmp/letspaint_release_${RELEASE_VERSION}_$$"
    rm -rf "$STAGE"
    mkdir -p "$STAGE"
    local files=(server.py index.html register.html cms.sh requirements.txt manifest.json manifest-student.json sw.js logo.png logo-light.png icon-192.png icon-512.png apple-touch-icon.png test_cms.py com.letspaintstudio.plist README_AWS_Lightsail.md DEPLOY_AWS_QUICKSTART.md LIGHTSAIL_INSTANCE_INFO.md STATIC_IP_UPDATE.md .env.aws.example .gitignore CMS_管理员操作手册_v4.3.docx CMS_学员使用指南_v4.3.docx CMS_常见问题解答FAQ_v4.3.docx 改动说明.md 添加到主屏幕教程.md 邮件设置教程.md)
    for f in "${files[@]}"; do
        [ -f "$DIR/$f" ] && cp "$DIR/$f" "$STAGE/"
    done
    if [ -d "$DIR/vendor" ]; then
        mkdir -p "$STAGE/vendor"
        for vf in react.production.min.js react-dom.production.min.js babel.min.js tailwindcss.js README.txt; do
            [ -f "$DIR/vendor/$vf" ] && cp "$DIR/vendor/$vf" "$STAGE/vendor/"
        done
    fi
    if [ -d "$DIR/deploy" ]; then
        mkdir -p "$STAGE/deploy"
        cp -R "$DIR/deploy/." "$STAGE/deploy/"
    fi
    printf "%s\n" \
"Let's Paint CMS v${RELEASE_VERSION} 发布包" \
"" \
"包含：程序文件、PWA 文件、logo/icon、测试脚本和教程。" \
"不包含：database.json、photos/、portfolio/、backups/、.api_secret、.cms_password、.cms_config.json。AWS 推荐把这些放在 CMS_DATA_DIR=/opt/letspaint-cms/data。" \
"" \
"部署：" \
"1. 先备份线上 CMS 目录。" \
"2. 解压本 zip 到 CMS 目录，覆盖同名程序文件。" \
"3. 运行 ./cms.sh restart" \
"4. 运行 ./cms.sh check" > "$STAGE/README-部署说明.txt"
    mkdir -p "$OUTDIR"
    rm -f "$OUTDIR/$NAME"
    "$PY" - "$STAGE" "$OUTDIR/$NAME" <<'PYZIP'
import os, sys, zipfile
stage, out = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(out, 'w', compression=zipfile.ZIP_DEFLATED) as z:
    for base, dirs, files in os.walk(stage):
        dirs[:] = sorted(dirs)
        for fn in sorted(files):
            full = os.path.join(base, fn)
            arc = os.path.relpath(full, stage)
            # Python zipfile marks non-ASCII filenames as UTF-8, avoiding
            # mojibake for Chinese documentation names on macOS/Finder.
            z.write(full, arc)
PYZIP
    rm -rf "$STAGE"
    echo "✅ 发布包已生成: $OUTDIR/$NAME"
    echo "   注意：包内不含数据库/照片/作品集/备份/密钥，避免误覆盖数据。"
}


_do_vendor() {
    local VDIR="$DIR/vendor"
    mkdir -p "$VDIR"
    echo "📦  下载本地前端依赖 / Downloading frontend vendor files..."
    local ok=0
    "$CURL" -L --fail -o "$VDIR/react.production.min.js" https://unpkg.com/react@18.3.1/umd/react.production.min.js && ok=$((ok+1))
    "$CURL" -L --fail -o "$VDIR/react-dom.production.min.js" https://unpkg.com/react-dom@18.3.1/umd/react-dom.production.min.js && ok=$((ok+1))
    "$CURL" -L --fail -o "$VDIR/babel.min.js" https://unpkg.com/@babel/standalone@7.25.7/babel.min.js && ok=$((ok+1))
    "$CURL" -L --fail -o "$VDIR/tailwindcss.js" https://cdn.tailwindcss.com/3.4.17 && ok=$((ok+1))
    if [ "$ok" = "4" ]; then
        echo "✅ vendor 下载完成。现在后台会优先使用本地依赖，CDN 仅作兜底。"
    else
        echo "⚠️  有文件下载失败（成功 $ok/4）。系统仍会自动回退 CDN。"
        exit 1
    fi
}


_do_clean() {
    cd "$DIR" || exit 1
    local TS=$(date +%Y%m%d_%H%M%S)
    local OUT="$DIR/cleanup_$TS"
    mkdir -p "$OUT"
    local moved=0
    for f in _logo_preview.png _visual_check.png "Archive.zip" "Archive 2.zip" index.html.bak CMS_学员使用指南_v3.docx CMS_常见问题解答FAQ_v3.docx CMS_管理员操作手册_v3.docx; do
        if [ -e "$DIR/$f" ]; then mv "$DIR/$f" "$OUT/" && moved=$((moved+1)); fi
    done
    for d in __pycache__ previous cloudflare-setup; do
        if [ -d "$DIR/$d" ]; then mv "$DIR/$d" "$OUT/" && moved=$((moved+1)); fi
    done
    if [ "$moved" = "0" ]; then
        rmdir "$OUT" 2>/dev/null
        echo "✅ 生产目录已经干净，无需清理"
    else
        echo "✅ 已移动 $moved 项到: $OUT"
        echo "   未移动 database/photos/portfolio/backups/密钥，数据安全。"
    fi
}

# ── 主逻辑 / Main ──────────────────────────────────────────────────

CMD="${1:-start}"

case "$CMD" in

  start|""|--no-tunnel)
    echo ""
    echo "🎨  Let's Paint CMS 启动中 / Starting..."
    echo ""
    echo "① 释放端口 $PORT / Freeing port $PORT..."
    _start_flask || exit 1
    # O3: 默认照常开隧道；--no-tunnel 时跳过（纯局域网模式）
    if [ "$CMD" = "--no-tunnel" ] || [ "$2" = "--no-tunnel" ]; then
        echo "③ 已跳过外网隧道（局域网模式）/ Tunnel skipped (LAN mode)"
        echo "   随时可用 ./cms.sh tunnel 单独开启 / Use ./cms.sh tunnel to enable later"
    else
        _start_tunnel
    fi
    _print_divider
    trap "echo ''; echo '停止服务 / Stopping...'; kill \$FLASK_PID \$TUNNEL_PID 2>/dev/null; exit 0" INT TERM
    wait $FLASK_PID
    ;;

  setup)
    # O2: 一键创建/重建 Python 环境并装齐全部依赖
    # One-shot venv bootstrap — run once on first install or after a macOS upgrade.
    echo ""
    echo "🔧  创建 Python 环境 / Building Python environment..."
    SYS_PY="$(command -v python3)"
    if [ -z "$SYS_PY" ]; then
        echo "❌ 未找到 python3，请先安装 Xcode 命令行工具: xcode-select --install"
        exit 1
    fi
    "$SYS_PY" -m venv "$VENV" || { echo "❌ venv 创建失败"; exit 1; }
    "$VENV/bin/pip" install --upgrade pip -q
    if [ -f "$DIR/requirements.txt" ]; then
        "$VENV/bin/pip" install -r "$DIR/requirements.txt" || exit 1
    else
        "$VENV/bin/pip" install flask waitress || exit 1
    fi
    echo ""
    "$VENV/bin/python3" -c "import flask, waitress; print('✅ 依赖就绪: flask', flask.__version__, '| waitress', waitress.__version__)"
    echo "✅ 环境位置: $VENV"
    echo "   现在可以运行 ./cms.sh 启动服务了"
    echo ""
    ;;

  tunnel)
    # O3: 单独控制外网隧道（Flask 不受影响）
    if [ "$2" = "stop" ]; then
        TPID=$(_tunnel_pid)
        if [ -n "$TPID" ]; then
            kill "$TPID" 2>/dev/null
            pkill -f "letspaint.*watchdog" 2>/dev/null
            rm -f "$DIR/current_url.txt"
            echo "✅ 隧道已关闭（Flask 继续运行）/ Tunnel stopped (Flask still running)"
        else
            echo "（隧道未在运行 / Tunnel not running）"
        fi
    else
        if [ -z "$(_flask_pid)" ]; then
            echo "❌ Flask 未运行，请先 ./cms.sh 或 ./cms.sh --no-tunnel"
            exit 1
        fi
        if [ -n "$(_tunnel_pid)" ]; then
            echo "（隧道已在运行 / Tunnel already running）"
            SAVED_URL=$(cat "$DIR/current_url.txt" 2>/dev/null)
            [ -n "$SAVED_URL" ] && echo "   外网地址: $SAVED_URL"
        else
            _start_tunnel
        fi
    fi
    ;;

  server)
    # Foreground Flask-only mode for launchd plist.
    # exec replaces this shell so launchd tracks the Python process directly.
    # -u: unbuffered output so the launchd log file updates in real time.
    cd "$DIR"
    exec "$PY" -u server.py
    ;;

  stop)
    echo ""
    echo "🛑 停止服务 / Stopping services..."
    _do_stop
    echo ""
    ;;

  restart)
    echo ""
    echo "🔄 重启服务 / Restarting..."
    _do_stop
    sleep 1
    echo ""
    echo "🎨  重新启动 / Starting..."
    echo ""
    echo "① 释放端口 $PORT / Freeing port $PORT..."
    _start_flask || exit 1
    _start_tunnel
    _print_divider
    trap "echo ''; echo '停止服务 / Stopping...'; kill \$FLASK_PID \$TUNNEL_PID 2>/dev/null; exit 0" INT TERM
    wait $FLASK_PID
    ;;

  status)
    echo ""
    echo "📊  服务状态 / Service Status"
    echo "──────────────────────────────"
    FPID=$(_flask_pid)
    TPID=$(_tunnel_pid)
    if [ -n "$FPID" ]; then
        LAN=$(_lan_ip | head -1); [ -z "$LAN" ] && LAN="?"
        ENGINE=$("$CURL" -s -m 3 http://localhost:$PORT/api/ping | grep -o '"engine":"[^"]*"' | cut -d'"' -f4)
        echo "  ✅ Flask:   运行中 PID $FPID / Running"
        [ -n "$ENGINE" ] && echo "     引擎:   $ENGINE $([ "$ENGINE" = "waitress" ] && echo '(生产级 ✓)' || echo '(回退模式，运行 ./cms.sh setup 安装 waitress)')"
        echo "     本地:   http://localhost:$PORT"
        echo "     局域网: http://$LAN:$PORT"
    else
        echo "  ❌ Flask:   未运行 / Not running"
    fi
    if [ -n "$TPID" ]; then
        SAVED_URL=$(cat "$DIR/current_url.txt" 2>/dev/null)
        echo "  ✅ 隧道:   运行中 PID $TPID / Tunnel running"
        [ -n "$SAVED_URL" ] && echo "     外网:   $SAVED_URL"
    else
        echo "  ❌ 隧道:   未运行 / Tunnel not running"
    fi
    echo ""
    ;;




  clean)
    _do_clean
    ;;

  vendor)
    _do_vendor
    ;;

  check)
    _do_check
    ;;

  package)
    _do_package
    ;;

  logs)
    echo "📜  实时日志 / Live logs (Ctrl+C 退出 / to quit)"
    echo "────────────────────────────────────────────────"
    tail -f "$FLASK_LOG" "$TUNNEL_LOG" 2>/dev/null
    ;;

  *)
    echo ""
    echo "用法 / Usage: ./cms.sh [start|--no-tunnel|setup|tunnel [stop]|stop|restart|status|check|package|vendor|clean|logs]"
    echo ""
    exit 1
    ;;

esac
