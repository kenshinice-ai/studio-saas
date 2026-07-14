import errno, json, os, re, shutil, socket, time, secrets, hashlib
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, redirect, send_from_directory, session
from threading import Lock
from studiosaas import api_v1
from studiosaas.auth import init_auth_blueprints
from studiosaas.errors import api_error
from studiosaas.workspaces import RESERVED_SLUGS, WorkspaceError, validate_tenant_slug

# ── S4: Unified per-IP rate limiter (login / public upload / balance / token) ─
# One dict per bucket; entries are swept periodically so memory never grows
# unbounded during months-long uninterrupted runs.
_rate_buckets = {}     # bucket → { ip → [timestamps] }
_rate_lock    = Lock()
_rate_last_sweep = [time.time()]
RATE_SWEEP_EVERY = 600          # purge stale IPs every 10 minutes

def _client_ip():
    """Real client IP. Proxy headers (CF-Connecting-IP / X-Forwarded-For) are
    only trusted when the request arrives from localhost — i.e. through the
    local cloudflared tunnel. Direct LAN clients can't spoof their way past
    the rate limiter by sending fake headers."""
    ra = (request.remote_addr or 'unknown')
    if ra in ('127.0.0.1', '::1', 'localhost'):
        return ((request.headers.get('CF-Connecting-IP')
                 or request.headers.get('X-Forwarded-For')
                 or ra).split(',')[0].strip())
    return ra

def _rate_ok(bucket, max_calls, window):
    """Return True if this IP may make another call in `bucket`."""
    ip  = _client_ip()
    now = time.time()
    with _rate_lock:
        # Periodic sweep: drop IPs whose entries are all expired (S4 memory fix)
        if now - _rate_last_sweep[0] > RATE_SWEEP_EVERY:
            _rate_last_sweep[0] = now
            for b in list(_rate_buckets):
                log = _rate_buckets[b]
                for k in list(log):
                    if not any(now - t < 3600 for t in log[k]):
                        del log[k]
                if not log:
                    del _rate_buckets[b]
        log    = _rate_buckets.setdefault(bucket, {})
        recent = [t for t in log.get(ip, []) if now - t < window]
        if len(recent) >= max_calls:
            log[ip] = recent
            return False
        recent.append(now)
        log[ip] = recent
    return True

def _public_upload_ok(): return _rate_ok('upload',   5, 60)
def _login_ok():         return _rate_ok('login',    5, 300)
def _query_ok():         return _rate_ok('query',   10, 60)   # balance / portfolio token
def _register_ok():      return _rate_ok('register', 5, 60)   # P1: stop pending-list flooding

# Security: do NOT expose the CMS root as a static directory.
# Only explicit allowlist routes below may serve files (index/register/PWA/logo/icons).
# This prevents accidental public access to database.json, .api_secret, .cms_config.json, backups, tests, etc.
app = Flask(__name__, static_folder=None)
RUNTIME_ENV = os.environ.get('STUDIOSAAS_ENV', 'local').strip().lower() or 'local'
init_auth_blueprints(app)
app.register_blueprint(api_v1, url_prefix='/v1')
app.register_blueprint(api_v1, url_prefix='/s/<path_tenant_slug>/v1', name='studiosaas_api_v1_by_slug')
PORT          = int(os.environ.get('PORT', 8000))   # overridable for tests
APP_DIR       = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT  = os.environ.get('STUDIOSAAS_PROJECT_ROOT', '').strip() or os.path.dirname(APP_DIR)
if not os.path.isabs(PROJECT_ROOT):
    PROJECT_ROOT = os.path.abspath(os.path.join(APP_DIR, PROJECT_ROOT))
app.config['PROJECT_ROOT'] = PROJECT_ROOT
# AWS/Linux friendly data separation:
#   - local/mac default: app directory, same behavior as before
#   - AWS recommended:  CMS_DATA_DIR=/opt/letspaint-cms/data
# Keeping mutable data outside code makes git pulls/release overwrites safe.
DATA_DIR      = os.environ.get('CMS_DATA_DIR', '').strip() or APP_DIR
if not os.path.isabs(DATA_DIR):
    DATA_DIR = os.path.abspath(os.path.join(APP_DIR, DATA_DIR))
def _data_path(*parts):
    return os.path.join(DATA_DIR, *parts)
os.makedirs(DATA_DIR, exist_ok=True)
DB_FILE       = _data_path('database.json')
BACKUP_DIR    = _data_path('backups')
PHOTO_DIR     = _data_path('photos')
PORTFOLIO_DIR = _data_path('portfolio')
SECRET_FILE   = _data_path('.api_secret')
PW_FILE       = _data_path('.cms_password')
app.config['PHOTO_DIR'] = PHOTO_DIR
MAX_BACKUPS   = 30   # 1 backup/hr rate limit → ~30 hours of rolling coverage
APP_VERSION   = '4.3.3-aws'
ALLOWED_EXT   = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
EXT_MIME_TYPES = {
    'jpg': {'image/jpeg'},
    'jpeg': {'image/jpeg'},
    'png': {'image/png'},
    'gif': {'image/gif'},
    'webp': {'image/webp'},
}

# B4: Magic-byte signatures for allowed image types
def _is_image_bytes(header: bytes) -> bool:
    """Return True only if the file header matches a known image format."""
    if header[:3] == b'\xff\xd8\xff':              return True  # JPEG
    if header[:8] == b'\x89PNG\r\n\x1a\n':         return True  # PNG
    if header[:6] in (b'GIF87a', b'GIF89a'):        return True  # GIF
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP': return True  # WEBP
    return False

def _upload_ext_error(f, allowed_ext=ALLOWED_EXT):
    """Return `(ext, error)` after validating filename and MIME metadata."""
    filename = f.filename or ''
    if os.path.basename(filename) != filename or '\\' in filename or not filename:
        return '', 'Invalid filename'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_ext:
        return ext, f'File type .{ext} not allowed'
    mime = (getattr(f, 'mimetype', '') or '').lower()
    if mime and mime != 'application/octet-stream' and mime not in EXT_MIME_TYPES.get(ext, set()):
        return ext, 'MIME type does not match file extension'
    return ext, ''
DEFAULT_PW    = '0801'
db_lock       = Lock()

# ── Portfolio view tokens — in-memory, 1 hour TTL ─────────────────────────────
_portfolio_tokens = {}    # token → {'sid': str, 'expires': float}
_ptok_lock        = Lock()

# ── Request size limit: 20 MB total (individual photos capped at 5 MB below) ──
app.config['MAX_CONTENT_LENGTH'] = 20 * 1024 * 1024

# ── Session: 30-day cookie, signed with API secret ───────────────────────────
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY']    = True
app.config['SESSION_COOKIE_SAMESITE']    = 'Lax'

# ── Session idle timeout (A5) ───────────────────────────────────────
# v1 sessions expire after 24h of inactivity, or 30 days when the login
# asked to be remembered. last_seen is refreshed at most once a minute
# to avoid Set-Cookie churn. Sessions predating the policy (no last_seen)
# are stamped on their next request.
SESSION_IDLE_SECONDS          = 24 * 3600
SESSION_IDLE_REMEMBER_SECONDS = 30 * 24 * 3600

@app.before_request
def _session_idle_guard():
    if 'user_id' not in session:
        return None
    now = time.time()
    last = session.get('last_seen')
    if last is not None:
        limit = SESSION_IDLE_REMEMBER_SECONDS if session.get('remember') else SESSION_IDLE_SECONDS
        if now - float(last) > limit:
            session.clear()
            return None
    if last is None or now - float(last) > 60:
        session['last_seen'] = now
    return None

# ── CSRF guard (A4) ─────────────────────────────────────────────────
# Cookie-authenticated mutations on the v1 API must carry a custom header
# that cross-site forms cannot set. Requests without a session are exempt
# (they fail auth anyway, and public endpoints stay curl-friendly); the
# legacy /api/* surface keeps its own token model and is out of scope.
CSRF_HEADER_NAME  = 'X-Requested-With'
CSRF_HEADER_VALUE = 'StudioSaaS'

@app.before_request
def _csrf_guard():
    if request.method in ('GET', 'HEAD', 'OPTIONS'):
        return None
    path = request.path
    if not (path.startswith('/v1/') or (path.startswith('/s/') and '/v1/' in path)):
        return None
    # Public endpoints never authorise via the session, so CSRF adds nothing —
    # and a logged-in staff member browsing the public portal must not be
    # blocked from the registration/balance forms.
    if path.startswith('/v1/public/'):
        return None
    if 'user_id' not in session:
        return None
    if request.headers.get(CSRF_HEADER_NAME, '') == CSRF_HEADER_VALUE:
        return None
    return jsonify({
        'error': 'forbidden',
        'message': f"Missing CSRF protection header ({CSRF_HEADER_NAME}).",
    }), 403
# S13: opt-in Secure flag (set COOKIE_SECURE=1 when access is HTTPS-only).
# Default off because LAN access uses plain http://<ip>:8000.
if os.environ.get('COOKIE_SECURE') == '1' or RUNTIME_ENV in {'pilot', 'production'}:
    app.config['SESSION_COOKIE_SECURE'] = True

# P0-2 (pilot): requests arriving through the cloudflared tunnel are HTTPS at
# the Cloudflare edge, so the session cookie they receive gets the Secure
# attribute even when the global flag is off. Local http://localhost
# development and the in-process test clients are unaffected. The tunnel is
# identified the same way as _client_ip(): loopback origin carrying a
# CF-Connecting-IP header. (Flask writes the session cookie after
# after_request hooks run, so this must live in the session interface.)
from flask.sessions import SecureCookieSessionInterface

class _TunnelAwareSessionInterface(SecureCookieSessionInterface):
    def get_cookie_secure(self, flask_app):
        if super().get_cookie_secure(flask_app):
            return True
        try:
            return (request.remote_addr in ('127.0.0.1', '::1')
                    and bool(request.headers.get('CF-Connecting-IP')
                             or request.headers.get('X-Forwarded-Proto') == 'https'))
        except RuntimeError:          # outside a request context
            return False

app.session_interface = _TunnelAwareSessionInterface()

# ── CORS (S9): the SPA is same-origin, so by default NO CORS headers are sent.
# Set env var CORS_ORIGIN only if you ever host a page on another domain.
CORS_ORIGIN = os.environ.get('CORS_ORIGIN', '')


# ── API secret (auto-generated on first run, stored in .api_secret) ───────────
def _get_or_create_secret():
    configured = os.environ.get('STUDIOSAAS_SECRET_KEY', '').strip()
    if configured:
        if len(configured) < 32:
            raise RuntimeError('STUDIOSAAS_SECRET_KEY must be at least 32 characters.')
        return configured
    if RUNTIME_ENV == 'production':
        raise RuntimeError('STUDIOSAAS_SECRET_KEY is required in production.')
    if os.path.exists(SECRET_FILE):
        with open(SECRET_FILE, 'r') as f:
            s = f.read().strip()
        if len(s) >= 32:
            return s
    token = secrets.token_urlsafe(32)
    with open(SECRET_FILE, 'w') as f:
        f.write(token)
    try: os.chmod(SECRET_FILE, 0o600)
    except Exception: pass
    print(f'🔑  新 API 密钥已生成并保存至 {SECRET_FILE}')
    return token

API_SECRET = _get_or_create_secret()
# Use API_SECRET to sign Flask sessions — stable across restarts
app.secret_key = API_SECRET


# ── Password helpers (S3: PBKDF2 with per-password random salt) ──────────────
PBKDF2_ITER = 600_000

def _hash_pw_legacy(pw):
    """Old scheme (SHA-256, fixed salt) — kept only to verify+migrate old files."""
    return hashlib.sha256(f'lps-cms:{pw}'.encode('utf-8')).hexdigest()

def _hash_pw(pw, salt_hex=None):
    """PBKDF2-HMAC-SHA256, stored as  pbkdf2$<iterations>$<salt>$<hash>."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    dk   = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'), salt, PBKDF2_ITER)
    return f'pbkdf2${PBKDF2_ITER}${salt.hex()}${dk.hex()}'

def _verify_pw(pw, stored):
    """Check pw against stored hash. Returns (ok, needs_upgrade)."""
    if stored.startswith('pbkdf2$'):
        try:
            _, it, salt_hex, hash_hex = stored.split('$')
            dk = hashlib.pbkdf2_hmac('sha256', pw.encode('utf-8'),
                                     bytes.fromhex(salt_hex), int(it))
            return (secrets.compare_digest(dk.hex(), hash_hex), False)
        except Exception:
            return (False, False)
    # Legacy 64-char SHA-256 hex → verify, then caller upgrades transparently
    return (secrets.compare_digest(_hash_pw_legacy(pw), stored), True)

def _get_pw_hash():
    """Return the legacy CMS password hash, with defaults limited to local dev."""
    if os.path.exists(PW_FILE):
        with open(PW_FILE, 'r') as f:
            h = f.read().strip()
        if h:
            return h
    if RUNTIME_ENV in {'pilot', 'production'}:
        raise RuntimeError(
            'Legacy CMS password is not configured. '
            'Run backend/scripts/rotate_pilot_credentials.py before deployment.'
        )
    h = _hash_pw(DEFAULT_PW)
    with open(PW_FILE, 'w') as f:
        f.write(h)
    try: os.chmod(PW_FILE, 0o600)
    except Exception: pass
    print(f'🔐  本地开发默认密码已设置，哈希保存至 {PW_FILE}')
    return h

def _set_pw_hash(pw):
    h = _hash_pw(pw)
    with open(PW_FILE, 'w') as f:
        f.write(h)
    try: os.chmod(PW_FILE, 0o600)
    except Exception: pass
    return h

# ── F2: Phone normalization — strip spaces/dashes for comparison ──────────────
def _norm_phone(p):
    """Normalize phone number: remove spaces, dashes, parentheses.
    str() coercion: public endpoints may receive numbers/None instead of strings."""
    return re.sub(r'[\s\-\(\)]+', '', str(p or ''))

def _norm_name(n):
    """Lowercase + collapse internal whitespace for name comparison."""
    return re.sub(r'\s+', ' ', str(n or '').strip()).lower()

def _name_matches(query, s):
    """F3: Exact (case/space-insensitive) match against firstName, lastName,
    full name, or 'first last' — students may type any of these forms.
    Replaces the old substring match ('li' no longer matches 'Alice')."""
    q     = _norm_name(query)
    if not q:
        return False
    first = _norm_name(s.get('firstName') or '')
    last  = _norm_name(s.get('lastName')  or '')
    full  = _norm_name(s.get('name')      or '')
    candidates = {first, last, full,
                  (first + ' ' + last).strip(),
                  (last + ' ' + first).strip()}
    candidates.discard('')
    return q in candidates

def _find_student(db, name_q, phone_q):
    """Shared lookup for /api/balance and /api/portfolio/token:
    normalized phone must match exactly AND name must match per _name_matches."""
    for s in db.get('students', []):
        if s.get('archived'):
            continue
        if _norm_phone(s.get('mobile', '')) != phone_q:
            continue
        if _name_matches(name_q, s):
            return s
    return None

def _auth_ok():
    """Admin auth: logged-in browser session, or X-API-Key header (scripts).
    S2: ?token= query param removed — it leaked the secret into logs/history."""
    return (_session_ok() or
            request.headers.get('X-API-Key') == API_SECRET)


# ── R2: App config (.cms_config.json) — email settings etc. ──────────────────
CONFIG_FILE  = _data_path('.cms_config.json')
_config_lock = Lock()

def _load_config():
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def _save_config(cfg):
    tmp = CONFIG_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)
    try: os.chmod(CONFIG_FILE, 0o600)
    except Exception: pass


# ── R3: Email (smtplib — stdlib only, works with Gmail app passwords) ────────
def _send_email(cfg, subject, body):
    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header
    host = cfg.get('smtp_host') or 'smtp.gmail.com'
    port = int(cfg.get('smtp_port') or 587)
    user = (cfg.get('smtp_user') or '').strip()
    pw   = (cfg.get('smtp_password') or '').strip()
    to   = (cfg.get('email_to') or '').strip()
    if not (user and pw and to):
        raise RuntimeError('邮件未配置完整（需要发件 Gmail、应用专用密码、收件邮箱）')
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = Header(subject, 'utf-8')
    msg['From']    = user
    msg['To']      = to
    if port == 465:
        s = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        s = smtplib.SMTP(host, port, timeout=20)
        s.starttls()
    try:
        s.login(user, pw)
        s.sendmail(user, [to], msg.as_string())
    finally:
        s.quit()


# ── R4: Data health check ─────────────────────────────────────────────────────
def _parse_change(c):
    try:
        return int(str(c).replace('+', '').strip() or 0)
    except Exception:
        return 0

def _healthcheck(db):
    """Reconcile every student's balance against their log history and report
    structural issues. Read-only — never modifies anything."""
    students, logs = db.get('students', []), db.get('logs', [])
    name_counts, name_to_sid = {}, {}
    for s in students:
        k = _norm_name(s.get('name') or '')
        if k:
            name_counts[k] = name_counts.get(k, 0) + 1
            name_to_sid[k] = str(s.get('id'))
    sums, has_log = {}, set()
    for l in logs:
        sid = str(l.get('studentId') or '')
        if not sid:
            k = _norm_name(l.get('studentName') or '')
            sid = name_to_sid.get(k, '') if name_counts.get(k) == 1 else ''
        if sid:
            sums[sid] = sums.get(sid, 0) + _parse_change(l.get('change'))
            has_log.add(sid)
    mismatches = []
    for s in students:
        sid = str(s.get('id'))
        if sid in has_log:
            bal = _parse_change(s.get('balance'))
            if sums[sid] != bal:
                mismatches.append({'name': s.get('name', ''), 'balance': bal,
                                   'logsSum': sums[sid], 'diff': bal - sums[sid]})
    photo_files = set(os.listdir(PHOTO_DIR)) if os.path.exists(PHOTO_DIR) else set()
    missing_photos = [s.get('name', '') for s in students
                      if s.get('photo') and s.get('photo') not in photo_files]
    bks = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')) \
          if os.path.exists(BACKUP_DIR) else []
    last_bk = ''
    if bks:
        last_bk = datetime.fromtimestamp(
            os.path.getmtime(os.path.join(BACKUP_DIR, bks[-1]))).strftime('%d/%m/%Y %H:%M')
    conflicts = [f for f in os.listdir(DATA_DIR) if re.match(r'^database[ _]\d+\.json$', f)] if os.path.isdir(DATA_DIR) else []
    return {
        'checkedAt':       datetime.now().strftime('%d/%m/%Y %H:%M'),
        'students':        len(students),
        'activeStudents':  sum(1 for s in students if not s.get('archived')),
        'logs':            len(logs),
        'mismatches':      mismatches[:30],
        'mismatchCount':   len(mismatches),
        'duplicateNames':  sorted(k for k, c in name_counts.items() if c > 1),
        'pendingCount':    len(db.get('pending', [])),
        'pendingOldest':   (db.get('pending') or [{}])[0].get('submittedAt', '') if db.get('pending') else '',
        'missingPhotos':   missing_photos[:20],
        'logsWithoutId':   sum(1 for l in logs if not l.get('studentId')),
        'backupCount':     len(bks),
        'lastBackup':      last_bk,
        'conflictCopies':  conflicts,
        'dbSizeKB':        round(os.path.getsize(DB_FILE) / 1024, 1) if os.path.exists(DB_FILE) else 0,
    }


# ── R5: Weekly summary email ──────────────────────────────────────────────────
def _weekly_report(db):
    now  = datetime.now()
    week = {(now - timedelta(days=i)).strftime('%d/%m/%Y') for i in range(7)}
    in_week  = lambda l: str(l.get('date', ''))[:10] in week
    checkins = [l for l in db.get('logs', []) if l.get('action') == '上课签到' and in_week(l)]
    topups   = [l for l in db.get('logs', []) if l.get('action') == '充值购课' and in_week(l)]
    revenue  = sum(float(l.get('feePaid') or 0) for l in topups)
    newstu   = [l for l in db.get('logs', []) if l.get('action') in ('新生注册', '批准注册') and in_week(l)]
    th       = int(_load_config().get('renew_threshold', 2))
    low      = sorted([s for s in db.get('students', [])
                       if not s.get('archived') and 0 < _parse_change(s.get('balance')) <= th],
                      key=lambda s: _parse_change(s.get('balance')))
    # G1: birthdays in the next 7 days (compare month-day only, year-agnostic)
    upcoming_bd = []
    for s in db.get('students', []):
        if s.get('archived'):
            continue
        bd = str(s.get('birthday') or '')
        m = re.match(r'^\d{4}-(\d{2})-(\d{2})$', bd)
        if not m:
            continue
        for i in range(7):
            d = now + timedelta(days=i)
            if (d.month, d.day) == (int(m.group(1)), int(m.group(2))):
                upcoming_bd.append((d.strftime('%d/%m'), s.get('name', '')))
                break
    hc = _healthcheck(db)
    L  = []
    L.append(f"Let's Paint Studio — 每周经营汇总（{now.strftime('%d/%m/%Y')}）")
    L.append('=' * 38)
    L.append(f'本周签到:     {len(checkins)} 次')
    L.append(f'本周充值:     {len(topups)} 笔，共 ${revenue:,.0f}')
    L.append(f'本周新学员:   {len(newstu)} 人')
    L.append(f'待审核申请:   {hc["pendingCount"]} 条' + (f'（最早 {hc["pendingOldest"]}）' if hc['pendingOldest'] else ''))
    L.append('')
    L.append(f'⚡ 待续课名单（余额 ≤{th} 节，共 {len(low)} 人）')
    for s in low[:30]:
        L.append(f'   · {s.get("name","")}  剩余 {_parse_change(s.get("balance"))} 节')
    if len(low) > 30: L.append(f'   …另有 {len(low)-30} 人')
    if not low: L.append('   （无，全员余额充足 🎉）')
    L.append('')
    L.append(f'🎂 本周生日（未来 7 天，共 {len(upcoming_bd)} 人）')
    for d, n in upcoming_bd:
        L.append(f'   · {d}  {n}')
    if not upcoming_bd: L.append('   （本周无学员生日）')
    L.append('')
    L.append('🩺 数据体检')
    L.append(f'   学员 {hc["students"]} 人（活跃 {hc["activeStudents"]}）/ 日志 {hc["logs"]} 条 / 数据库 {hc["dbSizeKB"]} KB')
    L.append(f'   账目不一致: {hc["mismatchCount"]} 人' + ('（请在设置页查看明细）' if hc['mismatchCount'] else ' ✓'))
    L.append(f'   最近备份: {hc["lastBackup"] or "无"}（共 {hc["backupCount"]} 份）')
    if hc['conflictCopies']:
        L.append(f'   ⚠️ iCloud 冲突副本: {", ".join(hc["conflictCopies"])} — 请尽快处理！')
    L.append('')
    L.append('— Let\'s Paint CMS 自动发送，回复无效。配置可在系统设置中修改。')
    return '\n'.join(L)

def _weekly_email_loop():
    """Daemon thread: send the weekly summary on Monday >= 10:00 local time.
    If the Mac was asleep/off at that moment, catches up later in the week.
    After 3 consecutive failures, backs off for 6 hours to avoid hammering SMTP."""
    fails = 0
    while True:
        time.sleep(300)
        try:
            cfg = _load_config()
            if not cfg.get('weekly_enabled'):
                continue
            now = datetime.now()
            iso = now.isocalendar()
            wk  = f'{iso[0]}-W{iso[1]:02d}'
            due = (now.weekday() > 0) or (now.weekday() == 0 and now.hour >= 10)
            if due and cfg.get('last_sent_week') != wk:
                with db_lock:
                    db = _load_db()
                _send_email(cfg, f"🎨 Let's Paint 每周汇总 · {now.strftime('%d/%m/%Y')}",
                            _weekly_report(db))
                with _config_lock:
                    cfg = _load_config()
                    cfg['last_sent_week'] = wk
                    _save_config(cfg)
                fails = 0
                print(f'📧 每周汇总邮件已发送 → {cfg.get("email_to")}', flush=True)
        except Exception as e:
            fails += 1
            print(f'⚠️  每周邮件发送失败（第 {fails} 次）: {e}', flush=True)
            if fails >= 3:
                print('⚠️  连续 3 次失败，暂停 6 小时后重试（请检查设置页邮件配置）', flush=True)
                time.sleep(6 * 3600)
                fails = 0

def _session_ok():
    """Return True if the browser session is authenticated."""
    return session.get('auth') is True

def _portfolio_token_ok(token):
    """Return student id (str) if a valid portfolio view token, else None."""
    if not token:
        return None
    with _ptok_lock:
        # B7: proactively purge expired tokens when the dict grows large
        if len(_portfolio_tokens) > 100:
            now = time.time()
            stale = [k for k, v in _portfolio_tokens.items() if now > v['expires']]
            for k in stale:
                del _portfolio_tokens[k]
        entry = _portfolio_tokens.get(token)
        if not entry:
            return None
        if time.time() > entry['expires']:
            del _portfolio_tokens[token]
            return None
        return entry['sid']


# ── CORS (only when explicitly configured) + access log under waitress ───────
_USING_WAITRESS = False   # set True in __main__ when waitress serves the app

@app.after_request
def add_cors(r):
    if CORS_ORIGIN:
        r.headers['Access-Control-Allow-Origin']  = CORS_ORIGIN
        r.headers['Access-Control-Allow-Methods'] = 'GET, POST, PATCH, DELETE, OPTIONS'
        r.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-API-Key'
        if CORS_ORIGIN != '*':
            r.headers['Access-Control-Allow-Credentials'] = 'true'
    # Waitress prints no access log; keep cms.sh logs identical to before.
    if _USING_WAITRESS:
        try:
            print(f'{_client_ip()} - [{datetime.now().strftime("%d/%b/%Y %H:%M:%S")}] '
                  f'"{request.method} {request.path}" {r.status_code}', flush=True)
        except Exception:
            pass
    return r

@app.route('/api/data',               methods=['OPTIONS'])
@app.route('/api/save',               methods=['OPTIONS'])
@app.route('/api/register',           methods=['OPTIONS'])
@app.route('/api/balance',            methods=['OPTIONS'])
@app.route('/api/upload',             methods=['OPTIONS'])
@app.route('/api/upload-public',      methods=['OPTIONS'])
@app.route('/api/login',              methods=['OPTIONS'])
@app.route('/api/logout',             methods=['OPTIONS'])
@app.route('/api/change-password',    methods=['OPTIONS'])
@app.route('/api/portfolio/upload',   methods=['OPTIONS'])
@app.route('/api/portfolio/token',    methods=['OPTIONS'])
def handle_options(): return '', 204

@app.route('/api/portfolio/<sid>/<pid>', methods=['OPTIONS'])
def handle_portfolio_options(sid, pid): return '', 204


# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(413)
def too_large(_):
    return api_error('文件或请求体过大（上限 20 MB）', 413)

@app.errorhandler(404)
def not_found(_):
    return api_error('Not found', 404)

@app.errorhandler(500)
def server_error(e):
    return api_error(str(e), 500)


# ── DB helpers ────────────────────────────────────────────────────────────────
def _load_db():
    if not os.path.exists(DB_FILE):
        return {'students': [], 'logs': [], 'rosters': {}, 'pending': [], 'packages': []}
    with open(DB_FILE, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    if not content:
        return {'students': [], 'logs': [], 'rosters': {}, 'pending': [], 'packages': []}
    data = json.loads(content)
    data.setdefault('students', [])
    data.setdefault('logs',     [])
    data.setdefault('rosters',  {})
    data.setdefault('pending',  [])
    data.setdefault('packages', [{'id': 1, 'name': '标准课包', 'credits': 10, 'price': 1200}])
    data.setdefault('rev', 1)   # D2: optimistic-lock revision counter
    return data

# ── C2: Atomic write — write to .tmp then os.replace (crash-safe) ─────────────
def _save_db(data):
    _rotate_backup()
    tmp = DB_FILE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_FILE)  # atomic on POSIX; replaces in one syscall

def _rotate_backup():
    if not os.path.exists(DB_FILE): return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bks = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith('.json'))
    # Rate-limit: skip if a backup was created less than 60 minutes ago
    # This prevents 10 check-ins filling all backup slots within an hour.
    # With MAX_BACKUPS=30 and 1/hr cap → ~30 hours of rolling coverage.
    if bks:
        m = re.match(r'database_(\d{8}_\d{6})\.json', bks[-1])
        if m:
            last_dt = datetime.strptime(m.group(1), '%Y%m%d_%H%M%S')
            if (datetime.now() - last_dt).total_seconds() < 3600:
                return  # Recent backup exists — skip this save
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    shutil.copy2(DB_FILE, os.path.join(BACKUP_DIR, f'database_{ts}.json'))
    bks = sorted(f for f in os.listdir(BACKUP_DIR) if f.endswith('.json'))
    while len(bks) > MAX_BACKUPS:
        os.remove(os.path.join(BACKUP_DIR, bks.pop(0)))


# ── Core routes ───────────────────────────────────────────────────────────────
# Public static allowlist. Everything else in the project root is private by default.
def _public_file(filename, mimetype=None, cache_seconds=3600):
    allowed = {
        'super-admin.html', 'manifest.json', 'sw.js',
        'logo.png', 'logo-light.png', 'icon-192.png', 'icon-512.png',
        'apple-touch-icon.png', 'manifest-student.json'
    }
    base_dir = PROJECT_ROOT
    if filename not in allowed or not os.path.isfile(os.path.join(base_dir, filename)):
        return api_error('Not found', 404)
    resp = send_from_directory(base_dir, filename)
    if mimetype:
        resp.headers['Content-Type'] = mimetype
    resp.headers['Cache-Control'] = f'public, max-age={cache_seconds}'
    return resp

def _legacy_file(filename, mimetype=None, cache_seconds=0):
    """Serve archived single-tenant shells only through explicit tenant routes."""
    allowed = {'index.html', 'register.html'}
    legacy_dir = os.path.join(PROJECT_ROOT, 'legacy-root')
    target = os.path.join(legacy_dir, filename)
    if filename not in allowed or not os.path.isfile(target):
        return api_error('Not found', 404)
    resp = send_from_directory(legacy_dir, filename)
    if mimetype:
        resp.headers['Content-Type'] = mimetype
    resp.headers['Cache-Control'] = f'public, max-age={cache_seconds}'
    return resp

@app.route('/')
def serve_index():
    return _public_file('super-admin.html', 'text/html; charset=utf-8', 0)

@app.route('/register')
def serve_register():
    return api_error('Use /<tenant_slug>/register for tenant registration.', 404)

@app.route('/super-admin')
def serve_super_admin():
    return _public_file('super-admin.html', 'text/html; charset=utf-8', 0)

@app.route('/_legacy/register')
def serve_legacy_register():
    return _legacy_file('register.html', 'text/html; charset=utf-8', 0)

@app.route('/studio-admin')
def serve_studio_admin():
    # A tenant slug is mandatory for the Studio Admin context. Never recover
    # it from browser localStorage or silently choose a demo tenant.
    return redirect('/super-admin#tenants', code=302)

@app.route('/assets/<path:filename>')
def serve_shared_assets(filename):
    # Shared frontend runtime (ui-common.js, shared CSS). Same safety rules
    # as /vendor: basename only, no traversal.
    safe = os.path.basename(filename)
    resp = send_from_directory(os.path.join(app.root_path, 'frontend', 'assets'), safe)
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route('/setup-password')
def serve_setup_password():
    # One-time password-setup page; the token arrives as a query parameter
    # and is validated by POST /v1/auth/setup-password.
    return send_from_directory(os.path.join(app.root_path, 'frontend'),
                               'setup-password.html')

@app.route('/shared/portfolio')
def serve_shared_portfolio():
    # Public read-only portfolio viewer; the share token arrives as a query
    # parameter and is validated by GET /v1/public/portfolio/<token>.
    return send_from_directory(os.path.join(app.root_path, 'frontend'),
                               'shared-portfolio.html')

def _tenant_page(tenant_slug, filename):
    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    tenant_dir = os.path.join(PROJECT_ROOT, 'tenants', tenant_slug)
    target = os.path.join(tenant_dir, filename)
    if tenant_slug in RESERVED_SLUGS or not os.path.isfile(target):
        return api_error('Not found', 404)
    return send_from_directory(tenant_dir, filename)

@app.route('/<tenant_slug>')
@app.route('/<tenant_slug>/')
def serve_tenant_home(tenant_slug):
    # B5: the tenant root is the public landing page generated from
    # tenant-template/index.html. The legacy CMS stays at /<slug>/cms.
    # Fall back to the CMS shell for workspaces predating the template.
    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    landing = os.path.join(PROJECT_ROOT, 'tenants', tenant_slug, 'index.html')
    if os.path.isfile(landing):
        return _tenant_page(tenant_slug, 'index.html')
    return serve_tenant_cms_shell(tenant_slug)

@app.route('/<tenant_slug>/cms')
def serve_tenant_cms_shell(tenant_slug):
    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    if not os.path.isfile(os.path.join(PROJECT_ROOT, 'tenants', tenant_slug, 'tenant.json')):
        return api_error('Not found', 404)
    return _legacy_file('index.html', 'text/html; charset=utf-8', 0)

@app.route('/<tenant_slug>/studio-admin')
def serve_tenant_studio_admin(tenant_slug):
    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    if not os.path.isfile(os.path.join(PROJECT_ROOT, 'tenants', tenant_slug, 'tenant.json')):
        return api_error('Not found', 404)
    return send_from_directory(os.path.join(APP_DIR, 'frontend'),
                               'studio-admin.html')

@app.route('/<tenant_slug>/cms/studio-admin')
def serve_tenant_cms_studio_admin_alias(tenant_slug):
    """Alias matching the tenant surface model (portal / cms / studio-admin /
    register); the canonical URL stays /<slug>/studio-admin."""
    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    return redirect(f'/{tenant_slug}/studio-admin', code=302)

@app.route('/<tenant_slug>/register')
def serve_tenant_register(tenant_slug):
    return _tenant_page(tenant_slug, 'register.html')

# ── G6: PWA assets (public — needed before login for install/icon) ───────────
@app.route('/manifest.json')
def serve_manifest():
    return _public_file('manifest.json', 'application/manifest+json', 0)

@app.route('/manifest-student.json')
def serve_manifest_student():
    return _public_file('manifest-student.json', 'application/manifest+json', 0)

@app.route('/<tenant_slug>/manifest-student.json')
def serve_tenant_manifest_student(tenant_slug):
    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    tenant_file = os.path.join(PROJECT_ROOT, 'tenants', tenant_slug, 'tenant.json')
    if not os.path.isfile(tenant_file):
        return api_error('Not found', 404)
    with open(tenant_file, 'r', encoding='utf-8') as f:
        tenant = json.load(f)
    name = str(tenant.get('name') or tenant_slug)
    manifest = {
        'name': f'{name} Student Portal',
        'short_name': name[:24],
        'description': f'{name} student registration, balance, and portfolio portal',
        'id': f'/{tenant_slug}/register',
        'start_url': f'/{tenant_slug}/register',
        'scope': f'/{tenant_slug}/',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': '#fffdf9',
        'theme_color': '#fffdf9',
        'lang': 'zh-CN',
        'icons': [
            {'src': '/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
            {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
        ],
    }
    resp = jsonify(manifest)
    resp.headers['Content-Type'] = 'application/manifest+json'
    resp.headers['Cache-Control'] = 'public, max-age=0'
    return resp


@app.route('/<tenant_slug>/manifest-cms.json')
def serve_tenant_manifest_cms(tenant_slug):
    """Return a tenant-scoped install manifest for the staff CMS."""

    try:
        validate_tenant_slug(tenant_slug)
    except WorkspaceError:
        return api_error('Not found', 404)
    tenant_file = os.path.join(PROJECT_ROOT, 'tenants', tenant_slug, 'tenant.json')
    if not os.path.isfile(tenant_file):
        return api_error('Not found', 404)
    with open(tenant_file, 'r', encoding='utf-8') as f:
        tenant = json.load(f)
    name = str(tenant.get('name') or tenant_slug)
    manifest = {
        'name': f'{name} CMS',
        'short_name': f'{name[:18]} CMS',
        'description': f'{name} staff operations workspace',
        'id': f'/{tenant_slug}/cms',
        'start_url': f'/{tenant_slug}/cms',
        'scope': f'/{tenant_slug}/',
        'display': 'standalone',
        'orientation': 'portrait',
        'background_color': '#312e81',
        'theme_color': '#312e81',
        'lang': 'zh-CN',
        'icons': [
            {'src': '/icon-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
            {'src': '/icon-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any maskable'},
        ],
    }
    resp = jsonify(manifest)
    resp.headers['Content-Type'] = 'application/manifest+json'
    resp.headers['Cache-Control'] = 'public, max-age=0'
    return resp

@app.route('/sw.js')
def serve_sw():
    # Service worker must be served from root scope with no-cache so updates apply.
    resp = _public_file('sw.js', 'application/javascript; charset=utf-8', 0)
    resp.headers['Content-Type']  = 'application/javascript'
    resp.headers['Cache-Control'] = 'no-cache'
    resp.headers['Service-Worker-Allowed'] = '/'
    return resp

@app.route('/logo.png')
def serve_logo():      return _public_file('logo.png', 'image/png')
@app.route('/logo-light.png')
def serve_logolight(): return _public_file('logo-light.png', 'image/png')
@app.route('/icon-192.png')
def serve_icon192():   return _public_file('icon-192.png', 'image/png')
@app.route('/icon-512.png')
def serve_icon512():   return _public_file('icon-512.png', 'image/png')
@app.route('/apple-touch-icon.png')
def serve_appleicon(): return _public_file('apple-touch-icon.png', 'image/png')
@app.route('/apple-touch-icon-precomposed.png')
def serve_appleicon2(): return _public_file('apple-touch-icon.png', 'image/png')
@app.route('/favicon.ico')
def serve_favicon(): return _public_file('icon-192.png', 'image/png')

VENDOR_FILES = {
    'react.production.min.js': 'application/javascript; charset=utf-8',
    'react-dom.production.min.js': 'application/javascript; charset=utf-8',
    'tailwindcss.js': 'application/javascript; charset=utf-8',
}

@app.route('/vendor/<path:filename>')
def serve_vendor(filename):
    safe = os.path.basename(filename)
    if safe not in VENDOR_FILES:
        return api_error('Not found', 404)
    # Absolute path — the old relative check broke whenever the server was
    # launched from a different working directory (vendor 404 -> CDN-only).
    path = os.path.join(app.root_path, 'vendor', safe)
    if not os.path.isfile(path):
        return api_error('Not found', 404)
    resp = send_from_directory(os.path.join(app.root_path, 'vendor'), safe)
    resp.headers['Content-Type'] = VENDOR_FILES[safe]
    resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    return resp


@app.route('/photos/<path:filename>')
def serve_photo(filename):
    # S1: photos may contain student face shots — admin only.
    # Admin <img> tags are same-origin so the session cookie flows automatically.
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    return send_from_directory(PHOTO_DIR, os.path.basename(filename))


@app.route('/public-assets/<path:filename>')
def serve_public_asset(filename):
    """Serve vetted public uploads such as tenant logos."""
    safe = os.path.basename(filename)
    if not (safe.startswith('pub_') or safe.startswith('tenant_logo_')):
        return api_error('Not found', 404)
    path = os.path.join(PHOTO_DIR, safe)
    if not os.path.isfile(path):
        return api_error('Not found', 404)
    return send_from_directory(PHOTO_DIR, safe)


# ── API: session auth ─────────────────────────────────────────────────────────
@app.route('/api/me', methods=['GET'])
def get_me():
    """Check if the current browser session is authenticated."""
    return jsonify({'loggedIn': _session_ok()})

@app.route('/api/login', methods=['POST'])
def login():
    """Validate password and set a 30-day session cookie."""
    # C3: Rate limit login attempts to prevent brute-force
    if not _login_ok():
        return api_error('登录尝试过于频繁，请 5 分钟后再试 / Too many attempts, please wait 5 minutes', 429)
    data = request.json or {}
    pw   = (data.get('password') or '').strip()
    if not pw:
        return api_error('请输入密码', 400)
    ok, needs_upgrade = _verify_pw(pw, _get_pw_hash())
    if ok:
        if needs_upgrade:        # S3: transparently re-hash legacy SHA-256 file
            _set_pw_hash(pw)
            print('🔐  密码哈希已自动升级为 PBKDF2')
        session.permanent = True
        session['auth']   = True
        return jsonify({'ok': True})
    return api_error('密码错误', 401)

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'ok': True})

@app.route('/api/change-password', methods=['POST'])
def change_password():
    """Change the admin password. Requires active session + correct current password."""
    if not _session_ok():
        return api_error('Unauthorized', 401)
    data    = request.json or {}
    old_pw  = (data.get('oldPassword') or '').strip()
    new_pw  = (data.get('newPassword') or '').strip()
    if not old_pw or not new_pw:
        return api_error('请填写旧密码和新密码', 400)
    if len(new_pw) < 8:
        return api_error('新密码至少 8 位', 400)
    ok, _ = _verify_pw(old_pw, _get_pw_hash())
    if not ok:
        return api_error('旧密码错误', 401)
    _set_pw_hash(new_pw)
    return jsonify({'ok': True})


# ── S2: /api/init removed — the SPA now authenticates purely via its session
# cookie, so the master API secret is never handed to the browser.
# (X-API-Key header auth is kept in _auth_ok for scripts/automation.)


# ── API: health check (always public) ────────────────────────────────────────
@app.route('/api/ping', methods=['GET'])
def ping():
    # O1: engine/version visible here so you can confirm waitress is active
    # straight from the browser — no need to dig through startup logs.
    return jsonify({'ok': True, 'time': datetime.now().isoformat(),
                    'engine': 'waitress' if _USING_WAITRESS else 'flask-dev',
                    'version': APP_VERSION})


# ── API: data & save ──────────────────────────────────────────────────────────
@app.route('/api/data', methods=['GET'])
def get_data():
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    with db_lock:
        try:
            return jsonify(_load_db())
        except Exception as e:
            print(f'⚠️  读取异常: {e}')
            return api_error('Database read failed.', 500)

@app.route('/api/save', methods=['POST'])
def save_data():
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    data = request.json
    if not data or not isinstance(data.get('students'), list) or not isinstance(data.get('logs'), list):
        return api_error('Invalid structure', 400)
    force = bool(data.pop('force', False))
    data.setdefault('pending',  [])
    data.setdefault('packages', [{'id': 1, 'name': '标准课包', 'credits': 10, 'price': 1200}])
    with db_lock:
        try:
            # B2: Portfolio is managed exclusively via /api/portfolio/* endpoints.
            # Always restore server-side portfolio to prevent a stale client tab
            # from silently overwriting photos uploaded in another tab/session.
            current = _load_db()
            curr_port = {str(s['id']): s.get('portfolio', [])
                         for s in current.get('students', [])}
            for s in data['students']:
                sid = str(s.get('id', ''))
                if sid in curr_port:
                    s['portfolio'] = curr_port[sid]

            # D2: Optimistic lock — reject stale writes from another tab/device.
            # The client echoes back the rev it loaded; mismatch = concurrent edit.
            try:
                client_rev = int(data.get('rev')) if data.get('rev') is not None else None
            except (TypeError, ValueError):
                client_rev = None   # malformed rev → treat as legacy client (no lock)
            if client_rev is not None and client_rev != int(current.get('rev', 1)):
                return jsonify({'status': 'conflict',
                                'message': '数据已在其他设备/标签页被修改，请刷新后重试',
                                'rev': current.get('rev', 1)}), 409

            # D1: Disaster guard — refuse a save that wipes out >20% of students
            # unless the client explicitly confirms with force=true.
            # D1c: a save that empties the list entirely is ALWAYS challenged,
            # regardless of size — total wipe is never a routine operation.
            curr_n, new_n = len(current.get('students', [])), len(data['students'])
            if not force and curr_n > 0 and new_n == 0:
                return jsonify({'status': 'shrink_guard',
                                'message': f'本次保存将清空全部 {curr_n} 名学员，已拦截。'
                                           f'如确认无误请在弹窗中选择继续。',
                                'current': curr_n, 'incoming': 0}), 409
            if not force and curr_n >= 10 and new_n < curr_n * 0.8:
                return jsonify({'status': 'shrink_guard',
                                'message': f'学员数将从 {curr_n} 减少到 {new_n}，已拦截。'
                                           f'如确认无误请在弹窗中选择继续。',
                                'current': curr_n, 'incoming': new_n}), 409
            # D1b: same guard for the log history — normal operation only ever
            # removes one log at a time (undo), so a >50% drop means a bug.
            curr_l, new_l = len(current.get('logs', [])), len(data['logs'])
            if not force and curr_l >= 50 and new_l < curr_l * 0.5:
                return jsonify({'status': 'shrink_guard',
                                'message': f'历史日志将从 {curr_l} 条减少到 {new_l} 条，已拦截。'
                                           f'如确认无误请在弹窗中选择继续。',
                                'current': curr_l, 'incoming': new_l}), 409

            data['rev'] = int(current.get('rev', 1)) + 1
            _save_db(data)
            return jsonify({'status':'success', 'rev': data['rev']})
        except Exception as e:
            print(f'⚠️  写入异常: {e}')
            return api_error(str(e), 500)


# ── API: photo upload ─────────────────────────────────────────────────────────
@app.route('/api/upload', methods=['POST'])
def upload_photo():
    return jsonify({
        'error': 'legacy_upload_disabled',
        'message': 'Use /s/<tenant_slug>/v1/legacy-cms/media/upload instead.'
    }), 410
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    if 'file' not in request.files:
        return api_error('No file part', 400)
    f = request.files['file']
    if not f.filename:
        return api_error('Empty filename', 400)
    f.seek(0, 2); file_size = f.tell(); f.seek(0)
    if file_size > 5 * 1024 * 1024:
        return api_error('File too large (max 5 MB)', 400)
    ext, upload_error = _upload_ext_error(f)
    if upload_error:
        return api_error(upload_error, 400)
    # S5: magic-byte check — same protection as the other two upload endpoints
    header = f.read(16); f.seek(0)
    if not _is_image_bytes(header):
        return api_error('文件内容不是有效图片 / File is not a valid image', 400)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    # S1: random suffix → unguessable filename (also kills same-ms collisions)
    filename = f'{int(time.time()*1000)}_{secrets.token_hex(4)}.{ext}'
    f.save(os.path.join(PHOTO_DIR, filename))
    return jsonify({'filename': filename, 'url': f'/public-assets/{filename}'})


# ── API: public photo upload (register page — no login required) ──────────────
@app.route('/api/upload-public', methods=['POST'])
def upload_photo_public():
    return jsonify({
        'error': 'legacy_upload_disabled',
        'message': 'Use /v1/public/<tenant_slug>/registration-media instead.'
    }), 410
    if not _public_upload_ok():
        return api_error('上传太频繁，请稍后再试 / Too many uploads, please wait', 429)
    if 'file' not in request.files:
        return api_error('No file part', 400)
    f = request.files['file']
    if not f.filename:
        return api_error('Empty filename', 400)
    f.seek(0, 2); file_size = f.tell(); f.seek(0)
    if file_size > 5 * 1024 * 1024:
        return api_error('File too large (max 5 MB)', 400)
    ext, upload_error = _upload_ext_error(f)
    if upload_error:
        return api_error(upload_error, 400)
    # N1: Validate magic bytes — same protection as portfolio_upload (B4)
    header = f.read(16); f.seek(0)
    if not _is_image_bytes(header):
        return api_error('文件内容不是有效图片 / File is not a valid image', 400)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    filename = f'pub_{int(time.time()*1000)}_{secrets.token_hex(4)}.{ext}'   # S1
    f.save(os.path.join(PHOTO_DIR, filename))
    return jsonify({'filename': filename, 'url': f'/photos/{filename}'})


# ── API: student self-registration (always public) ────────────────────────────
@app.route('/api/register', methods=['POST'])
def register_student():
    # P1: rate-limited — a public endpoint that writes to the DB must not be floodable
    if not _register_ok():
        return api_error('提交太频繁，请稍后再试 / Too many submissions, please wait', 429)
    data  = request.json or {}
    # P2: server-side length caps — a public endpoint must never be able to
    # bloat the database with megabyte-sized strings (request cap is 20 MB).
    def fld(key, n):
        return (str(data.get(key) or '')).strip()[:n]
    first = fld('firstName', 80)
    last  = fld('lastName',  80)
    phone = fld('mobile',    40)
    if not first or not phone:
        return api_error('firstName and mobile are required', 400)
    with db_lock:
        try:
            db = _load_db()
            # R2: Smart dedup — only block on exact firstName+lastName+mobile triple match.
            # Siblings sharing a parent's phone (same mobile, different names) are allowed.
            # Same name with different phone (common name) is allowed.
            # Only exact triple match means "this is definitely the same person".
            name_key = (first + ' ' + last).strip().lower()
            norm_phone = _norm_phone(phone)

            for p in db.get('pending', []):
                p_name = ((p.get('firstName','') + ' ' + p.get('lastName','')).strip()).lower()
                if p_name == name_key and _norm_phone(p.get('mobile','')) == norm_phone:
                    return jsonify({
                        'duplicate': 'pending',
                        'error': '您的申请正在等待老师审核，请耐心等待通知。/ Your application is pending review, please wait for your teacher to contact you.'
                    })
            for s in db.get('students', []):
                if s.get('archived'): continue
                s_name = ((s.get('firstName','') + ' ' + s.get('lastName','')).strip() or s.get('name','')).lower()
                if s_name == name_key and _norm_phone(s.get('mobile','')) == norm_phone:
                    return jsonify({
                        'duplicate': 'student',
                        'error': '您已是我们的在册学员！请在"查询课时"页面查看您的余额，或直接联系老师。/ You are already registered! Please check your balance in the "Check Balance" tab or contact your teacher.'
                    })

            # P3: guarantee a unique id even for same-millisecond submissions
            new_id = int(time.time() * 1000)
            taken  = {p.get('id') for p in db.get('pending', [])} | \
                     {s.get('id') for s in db.get('students', [])}
            while new_id in taken:
                new_id += 1
            entry = {
                'id':          new_id,
                'submittedAt': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'firstName':   first,
                'lastName':    last,
                'mobile':      phone,
                'wechat':      fld('wechat',     80),
                'email':       fld('email',     120),
                'photo':       fld('photo',     120),
                'artStyle':    fld('artStyle',  120),
                'favArtist':   fld('favArtist', 120),
                'experience':  fld('experience',300),
                'goals':       fld('goals',     300),
                'birthday':    fld('birthday',   20),
                'message':     fld('message',   500),
            }
            db['pending'].append(entry)
            # P1: hard cap — even if rate limiting is somehow bypassed, the
            # pending list can never grow without bound and bloat the DB.
            if len(db['pending']) > 200:
                db['pending'] = db['pending'][-200:]
            _save_db(db)
            return jsonify({'success': True})
        except Exception as e:
            print(f'⚠️  注册异常: {e}')
            return api_error(str(e), 500)


# ── API: balance query (always public) ───────────────────────────────────────
@app.route('/api/balance', methods=['POST'])
def check_balance():
    # S4: rate-limited — prevents name+phone enumeration
    if not _query_ok():
        return api_error('查询太频繁，请稍后再试 / Too many queries, please wait', 429)
    data    = request.json or {}
    name_q  = str(data.get('name')  or '').strip()
    phone_q = _norm_phone(data.get('phone'))  # F2: normalize phone for comparison
    if not name_q or not phone_q:
        return jsonify({'match': False}), 200
    with db_lock:
        try:
            db = _load_db()
            s  = _find_student(db, name_q, phone_q)   # F3: exact-match rules
            if s:
                # D3: match logs by studentId first (rename-proof); fall back to
                # studentName for any record the startup backfill couldn't map.
                sid = str(s.get('id'))
                checkins = sorted(
                    [l for l in db.get('logs', [])
                     if l.get('action') == '上课签到' and
                        (str(l.get('studentId', '')) == sid or
                         (not l.get('studentId') and l.get('studentName') == s.get('name')))],
                    key=lambda l: l.get('id', 0), reverse=True
                )
                return jsonify({
                    'match':          True,
                    'name':           s.get('name', ''),
                    'balance':        s.get('balance', 0),
                    'total_checkins': len(checkins),
                    'logs':           [{'date': l.get('date', '')} for l in checkins[:20]]
                })
            return jsonify({'match': False})
        except Exception as e:
            print(f'⚠️  余额查询异常: {e}')
            return api_error(str(e), 500)


# ── API: portfolio ────────────────────────────────────────────────────────────

@app.route('/api/portfolio/upload', methods=['POST'])
def portfolio_upload():
    return jsonify({
        'error': 'legacy_upload_disabled',
        'message': 'Use /s/<tenant_slug>/v1/legacy-cms/portfolio/upload instead.'
    }), 410
    if not (_auth_ok() or _session_ok()):
        return api_error('Unauthorized', 401)
    sid      = (request.form.get('studentId') or '').strip()
    note     = (request.form.get('note')      or '').strip()[:50]   # N2: cap at 50 chars server-side
    date_str = (request.form.get('date')      or datetime.now().strftime('%Y-%m-%d')).strip()
    # N3: validate date format YYYY-MM-DD
    if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        date_str = datetime.now().strftime('%Y-%m-%d')
    if not sid:
        return api_error('studentId required', 400)
    if 'file' not in request.files:
        return api_error('No file part', 400)
    f = request.files['file']
    if not f.filename:
        return api_error('Empty filename', 400)
    f.seek(0, 2); file_size = f.tell(); f.seek(0)
    if file_size > 10 * 1024 * 1024:
        return api_error('File too large (max 10 MB)', 400)
    ext, upload_error = _upload_ext_error(f)
    if upload_error:
        return api_error(upload_error, 400)
    # B4: Validate magic bytes — extension alone is not enough
    header = f.read(16); f.seek(0)
    if not _is_image_bytes(header):
        return api_error('文件内容不是有效图片 / File is not a valid image', 400)
    # B9: Add random suffix to avoid millisecond-level ID collision
    pid = f"{int(time.time() * 1000)}_{secrets.token_hex(4)}"
    student_dir = os.path.join(PORTFOLIO_DIR, str(sid))
    os.makedirs(student_dir, exist_ok=True)
    filename = f'{pid}.{ext}'
    filepath = os.path.join(student_dir, filename)
    f.save(filepath)
    with db_lock:
        try:
            db = _load_db()
            for s in db['students']:
                if str(s.get('id')) == str(sid):
                    # #3 fix: refuse upload for archived students
                    if s.get('archived'):
                        try: os.remove(filepath)
                        except Exception: pass
                        return api_error('已归档学员无法上传作品 / Student is archived', 403)
                    s.setdefault('portfolio', [])
                    item = {'id': pid, 'filename': filename, 'date': date_str, 'note': note}
                    s['portfolio'].insert(0, item)   # newest first
                    # B8: If _save_db fails, clean up the already-written file
                    try:
                        _save_db(db)
                    except Exception as e:
                        try: os.remove(filepath)
                        except Exception: pass
                        print(f'⚠️  作品集DB写入失败，已清理文件: {e}')
                        return api_error('保存失败，请重试', 500)
                    return jsonify({'ok': True, 'item': item})
        except Exception as e:
            try: os.remove(filepath)
            except Exception: pass
            return api_error(str(e), 500)
    # Student not found — clean up orphan file
    try: os.remove(filepath)
    except Exception: pass
    return api_error('Student not found', 404)


@app.route('/api/portfolio/<sid>/<pid>', methods=['DELETE'])
def portfolio_delete(sid, pid):
    return jsonify({
        'error': 'legacy_upload_disabled',
        'message': 'Use /s/<tenant_slug>/v1/legacy-cms/portfolio/<student_id>/<portfolio_item_id> instead.'
    }), 410
    if not (_auth_ok() or _session_ok()):
        return api_error('Unauthorized', 401)
    with db_lock:
        db = _load_db()
        for s in db['students']:
            if str(s.get('id')) == str(sid):
                portfolio = s.get('portfolio', [])
                item = next((i for i in portfolio if str(i.get('id')) == str(pid)), None)
                if not item:
                    return api_error('Not found', 404)
                filepath = os.path.join(PORTFOLIO_DIR, str(sid), item['filename'])
                try: os.remove(filepath)
                except Exception: pass
                s['portfolio'] = [i for i in portfolio if str(i.get('id')) != str(pid)]
                _save_db(db)
                return jsonify({'ok': True})
    return api_error('Student not found', 404)


@app.route('/api/portfolio/<sid>/<pid>', methods=['PATCH'])
def portfolio_update(sid, pid):
    return jsonify({
        'error': 'legacy_upload_disabled',
        'message': 'Use /s/<tenant_slug>/v1/legacy-cms/portfolio/<student_id>/<portfolio_item_id> instead.'
    }), 410
    if not (_auth_ok() or _session_ok()):
        return api_error('Unauthorized', 401)
    data     = request.json or {}
    note     = (data.get('note') or '').strip()[:50]   # N2: cap at 50 chars server-side
    date_str = (data.get('date') or '').strip()
    # N3: only accept valid YYYY-MM-DD; ignore malformed dates
    if date_str and not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        date_str = ''
    with db_lock:
        db = _load_db()
        for s in db['students']:
            if str(s.get('id')) == str(sid):
                for item in s.get('portfolio', []):
                    if str(item.get('id')) == str(pid):
                        item['note'] = note
                        if date_str:
                            item['date'] = date_str
                        _save_db(db)
                        return jsonify({'ok': True})
                return api_error('Item not found', 404)
    return api_error('Student not found', 404)


@app.route('/portfolio/img/<sid>/<filename>')
def serve_portfolio_img(sid, filename):
    """Serve portfolio images — admin session/API key or valid student token."""
    token = request.args.get('token', '')
    # Admin paths
    if _session_ok() or _auth_ok():
        safe_dir  = os.path.join(PORTFOLIO_DIR, os.path.basename(sid))
        safe_file = os.path.basename(filename)
        return send_from_directory(safe_dir, safe_file)
    # Student token path
    token_sid = _portfolio_token_ok(token)
    if token_sid and str(token_sid) == str(sid):
        safe_dir  = os.path.join(PORTFOLIO_DIR, os.path.basename(sid))
        safe_file = os.path.basename(filename)
        return send_from_directory(safe_dir, safe_file)
    return api_error('Unauthorized', 401)


@app.route('/api/portfolio/token', methods=['POST'])
def get_portfolio_token():
    return jsonify({
        'error': 'legacy_upload_disabled',
        'message': 'Use /v1/public/<tenant_slug>/portfolio-token instead.'
    }), 410
    """Verify student name+phone; return 1-hour token + portfolio metadata."""
    # S4: rate-limited — same protection as /api/balance
    if not _query_ok():
        return api_error('查询太频繁，请稍后再试 / Too many queries, please wait', 429)
    data    = request.json or {}
    name_q  = str(data.get('name')  or '').strip()
    phone_q = _norm_phone(data.get('phone'))
    if not name_q or not phone_q:
        return jsonify({'ok': False}), 400
    # B5: Find matching student under db_lock, then release before acquiring _ptok_lock
    # — avoids nested lock acquisition which is a latent deadlock risk.
    matched = None
    with db_lock:
        db = _load_db()
        s  = _find_student(db, name_q, phone_q)   # F3: shared exact-match rules
        if s:
            matched = {'id': str(s['id']), 'portfolio': s.get('portfolio', [])}
    if matched:
        token = secrets.token_urlsafe(24)
        with _ptok_lock:  # acquired AFTER db_lock is released — safe ordering
            _portfolio_tokens[token] = {
                'sid':     matched['id'],
                'expires': time.time() + 3600
            }
        return jsonify({
            'ok':        True,
            'token':     token,
            'sid':       matched['id'],
            'portfolio': matched['portfolio']
        })
    return jsonify({'ok': False}), 200


# ── API: app config (admin session only) ─────────────────────────────────────
@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if not _session_ok():
        return api_error('Unauthorized', 401)
    with _config_lock:
        cfg = _load_config()
        if request.method == 'GET':
            return jsonify({'email_to':       cfg.get('email_to', ''),
                            'smtp_user':      cfg.get('smtp_user', ''),
                            'smtp_host':      cfg.get('smtp_host', 'smtp.gmail.com'),
                            'smtp_port':      cfg.get('smtp_port', 587),
                            'weekly_enabled': bool(cfg.get('weekly_enabled')),
                            'hasPassword':    bool(cfg.get('smtp_password')),
                            'renew_threshold': cfg.get('renew_threshold', 2),
                            'last_sent_week': cfg.get('last_sent_week', '')})
        data = request.json or {}
        for k in ('email_to', 'smtp_user', 'smtp_host'):
            if k in data:
                cfg[k] = str(data.get(k) or '').strip()[:200]
        if 'smtp_port' in data:
            try: cfg['smtp_port'] = int(data['smtp_port'])
            except (TypeError, ValueError): pass
        if data.get('smtp_password'):           # empty → keep existing password
            # Gmail displays app passwords WITH spaces ("abcd efgh ijkl mnop") —
            # strip all whitespace so a direct paste just works.
            cfg['smtp_password'] = re.sub(r'\s+', '', str(data['smtp_password']))[:200]
        if 'renew_threshold' in data:
            try: cfg['renew_threshold'] = max(0, int(data['renew_threshold']))
            except (TypeError, ValueError): pass
        if 'weekly_enabled' in data:
            en = bool(data['weekly_enabled'])
            # First enable: mark the current week as sent so the first email
            # goes out next Monday 10:00, not immediately.
            if en and not cfg.get('weekly_enabled') and not cfg.get('last_sent_week'):
                iso = datetime.now().isocalendar()
                cfg['last_sent_week'] = f'{iso[0]}-W{iso[1]:02d}'
            cfg['weekly_enabled'] = en
        _save_config(cfg)
        return jsonify({'ok': True})


@app.route('/api/email-test', methods=['POST'])
def email_test():
    if not _session_ok():
        return api_error('Unauthorized', 401)
    if not _rate_ok('email', 3, 300):
        return api_error('测试太频繁，请 5 分钟后再试', 429)
    cfg = _load_config()
    try:
        with db_lock:
            db = _load_db()
        _send_email(cfg, "🎨 Let's Paint CMS 测试邮件",
                    '这是一封测试邮件。收到即说明邮件配置成功！\n\n'
                    '——以下是当前每周汇总的预览——\n\n' + _weekly_report(db))
        return jsonify({'ok': True})
    except Exception as e:
        return api_error(str(e), 400)


@app.route('/api/healthcheck', methods=['GET'])
def api_healthcheck():
    if not _session_ok():
        return api_error('Unauthorized', 401)
    with db_lock:
        db = _load_db()
    return jsonify(_healthcheck(db))


# ── Backup list / summary / download / restore ────────────────────────────────
@app.route('/api/backups', methods=['GET'])
def list_backups():
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    if not os.path.exists(BACKUP_DIR): return jsonify([])
    files = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith('.json')], reverse=True)[:50]
    out = []
    for fn in files:
        p = os.path.join(BACKUP_DIR, fn)
        out.append({'name': fn, 'size': os.path.getsize(p),
                    'mtime': datetime.fromtimestamp(os.path.getmtime(p)).strftime('%d/%m/%Y %H:%M')})
    return jsonify(out)


@app.route('/api/backups/<filename>/summary', methods=['GET'])
def backup_summary(filename):
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(path):
        return api_error('Not found', 404)
    ok, data = _validate_db(path)
    if not ok:
        return jsonify({'valid': False})
    with db_lock:
        cur = _load_db()
    return jsonify({'valid': True,
                    'students': len(data.get('students', [])),
                    'logs':     len(data.get('logs', [])),
                    'diffStudents': len(data.get('students', [])) - len(cur.get('students', [])),
                    'diffLogs':     len(data.get('logs', []))     - len(cur.get('logs', []))})


@app.route('/api/restore', methods=['POST'])
def restore_backup():
    """R6: One-click restore. The current DB is ALWAYS saved as a
    pre_restore_* backup first, so a restore is itself reversible."""
    if not _session_ok():
        return api_error('Unauthorized', 401)
    fname = os.path.basename(str((request.json or {}).get('filename') or ''))
    path  = os.path.join(BACKUP_DIR, fname)
    if not fname.endswith('.json') or not os.path.exists(path):
        return api_error('备份不存在', 404)
    ok, data = _validate_db(path)
    if not ok:
        return api_error('该备份文件已损坏，无法恢复', 400)
    with db_lock:
        current = _load_db()
        os.makedirs(BACKUP_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        if os.path.exists(DB_FILE):
            shutil.copy2(DB_FILE, os.path.join(BACKUP_DIR, f'pre_restore_{ts}.json'))
        for key, default in (('students', []), ('logs', []), ('rosters', {}), ('pending', [])):
            data.setdefault(key, default)
        data['rev'] = int(current.get('rev', 1)) + 1   # bump → other tabs reload
        tmp = DB_FILE + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DB_FILE)
    print(f'♻️  已从 {fname} 恢复（恢复前状态已存为 pre_restore_{ts}.json）', flush=True)
    return jsonify({'ok': True, 'students': len(data['students']),
                    'logs': len(data['logs']), 'rev': data['rev']})

@app.route('/api/backups/<filename>', methods=['GET'])
def download_backup(filename):
    if not _auth_ok():
        return api_error('Unauthorized', 401)
    safe = os.path.basename(filename)
    path = os.path.join(BACKUP_DIR, safe)
    if not os.path.exists(path): return api_error('Not found', 404)
    return send_from_directory(BACKUP_DIR, safe, as_attachment=True)


# ── Startup self-check ────────────────────────────────────────────────────────
def _validate_db(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            d = json.loads(f.read().strip())
        return isinstance(d.get('students'), list), d
    except Exception:
        return False, None

def _startup_check():
    ok, data = _validate_db(DB_FILE) if os.path.exists(DB_FILE) else (True, None)
    if not ok:
        print('❌ 数据库文件损坏，尝试从备份恢复...')
        if not os.path.exists(BACKUP_DIR): return
        for bk in sorted(os.listdir(BACKUP_DIR), reverse=True):
            bk_path = os.path.join(BACKUP_DIR, bk)
            ok, data = _validate_db(bk_path)
            if ok:
                shutil.copy2(bk_path, DB_FILE)
                print(f'✅ 已从备份恢复: {bk}')
                break
        else:
            print('⚠️  所有备份均已损坏，请手动处理。')
            return
    else:
        print('✅ 数据库校验通过')

    # Ensure mutable data directories exist
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(PHOTO_DIR, exist_ok=True)
    os.makedirs(PORTFOLIO_DIR, exist_ok=True)

    # C1: One-time migration — add birthday/portfolio fields + ensure packages key
    if data:
        migrated = False
        for s in data.get('students', []):
            if 'birthday' not in s:
                s['birthday'] = ''
                migrated = True
            if 'portfolio' not in s:
                s['portfolio'] = []
                migrated = True
        if not data.get('packages'):
            data['packages'] = [{'id': 1, 'name': '标准课包', 'credits': 10, 'price': 1200}]
            migrated = True
        if 'rev' not in data:          # D2: seed revision counter
            data['rev'] = 1
            migrated = True
        # D3: One-time backfill — link historical logs to student ids by name.
        # New logs carry studentId from the frontend; old ones get it here so
        # renaming a student no longer breaks their check-in history.
        name_to_id = {}
        for s in data.get('students', []):
            for key in {_norm_name(s.get('name') or ''),
                        _norm_name((s.get('firstName','') + ' ' + s.get('lastName','')).strip())}:
                if key:
                    # Names are not unique — only map unambiguous ones
                    name_to_id[key] = None if key in name_to_id else s.get('id')
        backfilled = 0
        for l in data.get('logs', []):
            if not l.get('studentId'):
                sid = name_to_id.get(_norm_name(l.get('studentName') or ''))
                if sid:
                    l['studentId'] = sid
                    backfilled += 1
        if backfilled:
            migrated = True
            print(f'✅ 已为 {backfilled} 条历史日志补全 studentId')
        if migrated:
            try:
                _save_db(data)
                print('✅ 数据迁移完成：补全 birthday/portfolio/rev/studentId 字段')
            except Exception as e:
                print(f'⚠️  迁移写入失败（非致命）: {e}')

    _check_icloud_conflicts()
    _cleanup_orphan_photos(data)


def _check_icloud_conflicts():
    """R1: Detect iCloud sync-conflict copies like 'database 2.json'.
    They silently fork the data — warn loudly so they get merged by hand."""
    try:
        pat = re.compile(r'^database[ _]\d+\.json$')
        hits = [f for f in os.listdir(DATA_DIR) if pat.match(f)] if os.path.isdir(DATA_DIR) else []
        if hits:
            print('=' * 58)
            print(f'⚠️⚠️  检测到 iCloud 冲突副本: {", ".join(hits)}')
            print('⚠️⚠️  这是 iCloud 同步冲突的产物，主库可能缺少其中的改动。')
            print('⚠️⚠️  请对比内容后手动合并，再删除副本文件！')
            print('=' * 58)
    except Exception:
        pass


def _cleanup_orphan_photos(data):
    """D4: Delete photos in PHOTO_DIR that no student/pending entry references
    and that are older than 48 h (buffer protects just-uploaded, not-yet-
    submitted registration photos)."""
    try:
        if not os.path.exists(PHOTO_DIR) or not data:
            return
        referenced = {s.get('photo') for s in data.get('students', [])} | \
                     {p.get('photo') for p in data.get('pending',  [])}
        referenced.discard(''); referenced.discard(None)
        cutoff, removed = time.time() - 48 * 3600, 0
        for fn in os.listdir(PHOTO_DIR):
            path = os.path.join(PHOTO_DIR, fn)
            if (os.path.isfile(path) and fn not in referenced
                    and os.path.getmtime(path) < cutoff):
                os.remove(path)
                removed += 1
        if removed:
            print(f'🧹 已清理 {removed} 张无引用的孤儿照片（>48h）')
    except Exception as e:
        print(f'⚠️  孤儿照片清理跳过: {e}')

def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return '无法获取'


if __name__ == '__main__':
    _startup_check()
    _get_pw_hash()   # ensure default password file exists on first run
    # R5: weekly summary email scheduler (daemon — dies with the server)
    import threading as _threading
    _threading.Thread(target=_weekly_email_loop, daemon=True).start()
    lan = _local_ip()
    print('\n' + '='*58)
    print("🎨  Let's Paint CMS — Server Online!")
    print('='*58)
    print(f'  Super Admin →  http://localhost:{PORT}')
    print(f'  局域网    →  http://{lan}:{PORT}')
    print(f'  租户 CMS  →  http://{lan}:{PORT}/<tenant_slug>')
    print(f'  学员注册  →  http://{lan}:{PORT}/<tenant_slug>/register')
    print(f'  健康检查  →  http://localhost:{PORT}/api/ping')
    print(f'  数据目录  →  {DATA_DIR}')
    print(f'  数据库    →  {DB_FILE}')
    print(f'  备份目录  →  {BACKUP_DIR}/  (保留最近 {MAX_BACKUPS} 份)')
    print(f'  作品集    →  {PORTFOLIO_DIR}/<student_id>/')
    print(f"  旧版 CMS 密码 →  {'已配置' if RUNTIME_ENV in {'pilot', 'production'} else '本地开发密码已配置'}")
    print('='*58 + '\n')
    # ── O1: waitress (production WSGI) with automatic fallback ───────────────
    # waitress only replaces the HTTP layer; all routes/locks/logic are
    # untouched. If it is missing or fails to start, fall back to the Flask
    # dev server so the CMS is never left unable to boot.
    try:
        from waitress import serve
        _USING_WAITRESS = True          # enables access log in add_cors
        print('🚀  服务器引擎: waitress (生产级)\n')
        serve(app, host='0.0.0.0', port=PORT, threads=8,
              channel_timeout=60, ident='LetsPaintCMS')
    except ImportError:
        _USING_WAITRESS = False
        print('ℹ️   未安装 waitress，回退到 Flask 开发服务器（功能完全一致）')
        print('ℹ️   安装方法: ./cms.sh setup\n')
        app.run(host='0.0.0.0', port=PORT, threaded=True)
    except Exception as e:
        if getattr(e, 'errno', None) == errno.EADDRINUSE or 'Address already in use' in str(e):
            print(f'❌ 端口 {PORT} 已被占用。请停止旧服务后重试，或用 PORT=8900 启动。')
            raise SystemExit(1) from e
        _USING_WAITRESS = False
        print(f'⚠️  waitress 启动失败（{e}），回退到 Flask 开发服务器\n')
        app.run(host='0.0.0.0', port=PORT, threaded=True)
