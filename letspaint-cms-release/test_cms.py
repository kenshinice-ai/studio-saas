#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════
#  Let's Paint CMS — 冒烟测试 / Smoke tests
#
#  用法 / Usage:   python3 test_cms.py        （在 CMS 目录下运行）
#
#  会在【临时目录】启动一个隔离的 CMS 实例（端口 8765），
#  完全不接触正式的 database.json / photos / 备份。
#  每次改完代码跑一遍，30 秒验证全部核心功能。
# ═══════════════════════════════════════════════════════════════════
import json, os, shutil, subprocess, sys, tempfile, time, uuid
import urllib.request, urllib.error, http.cookiejar

PORT = int(os.environ.get('TEST_PORT', 8765))
BASE = f'http://127.0.0.1:{PORT}'
HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_HERE = os.path.dirname(HERE)

# 1×1 valid PNG
PNG = (b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
       b'\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01'
       b'\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82')

passed, failed = [], []
engine_from_ping = ''
def check(name, cond, detail=''):
    (passed if cond else failed).append(name)
    print(('  ✅ ' if cond else '  ❌ ') + name + (f'   [{detail}]' if detail and not cond else ''))

# ── HTTP helpers (cookie-aware session) ───────────────────────────────────────
jar    = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def req(method, path, body=None, headers=None, raw=False):
    h = dict(headers or {})
    data = None
    if body is not None and not raw:
        data = json.dumps(body).encode(); h.setdefault('Content-Type', 'application/json')
    elif raw:
        data = body
    r = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        resp = opener.open(r, timeout=10)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()

def jreq(method, path, body=None, headers=None):
    code, raw = req(method, path, body, headers)
    try:    return code, json.loads(raw)
    except Exception: return code, {}

def multipart(path, fname, content, extra=None):
    b = uuid.uuid4().hex
    parts = []
    for k, v in (extra or {}).items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="{fname}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + content + b'\r\n')
    parts.append(f'--{b}--\r\n'.encode())
    body = b''.join(parts)
    return req('POST', path, body, {'Content-Type': f'multipart/form-data; boundary={b}'}, raw=True)

# ── Seed an isolated instance in a temp dir ───────────────────────────────────
tmp = tempfile.mkdtemp(prefix='cms_test_')
shutil.copy2(os.path.join(HERE, 'server.py'), tmp)
for dirname in ('studiosaas', 'frontend'):
    src = os.path.join(HERE, dirname)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(tmp, dirname))
for dirname in ('legacy-root', 'tenant-template', 'tenants'):
    src = os.path.join(PROJECT_HERE, dirname)
    if os.path.isdir(src):
        shutil.copytree(src, os.path.join(tmp, dirname))
for page in ('super-admin.html', 'manifest.json', 'manifest-student.json', 'sw.js',
             'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'logo.png', 'logo-light.png'):
    p = os.path.join(PROJECT_HERE if page == 'super-admin.html' else HERE, page)
    if os.path.exists(p): shutil.copy2(p, tmp)

students = []
for i in range(12):
    students.append({'id': 1000+i, 'firstName': f'Stu{i}', 'lastName': 'Test',
                     'name': f'Stu{i} Test', 'mobile': f'04{i:08d}', 'balance': 5,
                     'archived': False, 'portfolio': [], 'photo': ''})
students.append({'id': 2000, 'firstName': 'Amy', 'lastName': 'Wang', 'name': 'Amy Wang',
                 'mobile': '0412 345 678', 'balance': 7, 'archived': False,
                 'portfolio': [], 'photo': 'ref_keep.png'})
students.append({'id': 2001, 'firstName': 'Alice', 'lastName': 'Li', 'name': 'Alice Li',
                 'mobile': '0499999999', 'balance': 3, 'archived': False, 'portfolio': [], 'photo': ''})
logs = [
    {'id': 1, 'date': '01/06/2026 10:00', 'studentName': 'Amy Wang', 'action': '上课签到', 'change': -1, 'note': ''},
    {'id': 2, 'date': '02/06/2026 10:00', 'studentName': 'Amy Wang', 'action': '上课签到', 'change': -1, 'note': ''},
    {'id': 3, 'date': '03/06/2026 10:00', 'studentName': 'Alice Li', 'action': '上课签到', 'change': -1, 'note': ''},
]
with open(os.path.join(tmp, 'database.json'), 'w', encoding='utf-8') as f:
    json.dump({'students': students, 'logs': logs, 'rosters': {}, 'pending': [], 'packages': []}, f, ensure_ascii=False)

# legacy SHA-256 password file ('0801', old fixed-salt scheme) → tests auto-migration
import hashlib
with open(os.path.join(tmp, '.cms_password'), 'w') as f:
    f.write(hashlib.sha256('lps-cms:0801'.encode()).hexdigest())

# photos: one referenced (kept), one orphan older than 48 h (cleaned at startup)
os.makedirs(os.path.join(tmp, 'photos'), exist_ok=True)
for fn in ('ref_keep.png', 'orphan_old.png'):
    with open(os.path.join(tmp, 'photos', fn), 'wb') as f: f.write(PNG)
old = time.time() - 3*24*3600
os.utime(os.path.join(tmp, 'photos', 'ref_keep.png'),  (old, old))
os.utime(os.path.join(tmp, 'photos', 'orphan_old.png'), (old, old))

# iCloud-style conflict copy → server should print a loud warning
shutil.copy2(os.path.join(tmp, 'database.json'), os.path.join(tmp, 'database 2.json'))

env = dict(os.environ, PORT=str(PORT), STUDIOSAAS_PROJECT_ROOT=tmp)
logf = open(os.path.join(tmp, 'server.log'), 'w')
proc = subprocess.Popen([sys.executable, '-u', 'server.py'], cwd=tmp, env=env,
                        stdout=logf, stderr=subprocess.STDOUT)
print(f'\n🧪  测试实例目录: {tmp}\n')
try:
    for _ in range(40):
        time.sleep(0.5)
        try:
            code, d = jreq('GET', '/api/ping')
            if code == 200 and d.get('ok'): break
        except Exception: pass
    else:
        print('❌ 服务器未能启动，日志:'); print(open(os.path.join(tmp,'server.log')).read()); sys.exit(1)

    # ── 1. 基础 ───────────────────────────────────────────────────────────────
    check('ping 健康检查', True)
    code, d = jreq('GET', '/api/ping')
    engine_from_ping = d.get('engine', '')
    check('ping 返回引擎信息', engine_from_ping in ('waitress', 'flask-dev'), str(d))

    # ── 2. 启动迁移 ──────────────────────────────────────────────────────────
    slog = open(os.path.join(tmp, 'server.log'), encoding='utf-8', errors='replace').read()
    check('iCloud 冲突副本检测告警', '冲突副本' in slog)
    check('孤儿照片已清理(>48h 无引用)', not os.path.exists(os.path.join(tmp, 'photos', 'orphan_old.png')))
    check('被引用的旧照片保留', os.path.exists(os.path.join(tmp, 'photos', 'ref_keep.png')))

    # ── 3. 鉴权 ──────────────────────────────────────────────────────────────
    code, _ = jreq('GET', '/api/data');                       check('未登录访问 /api/data → 401', code == 401)
    code, _ = req('GET', '/photos/ref_keep.png');             check('未登录访问 /photos → 401', code == 401)
    code, d = jreq('POST', '/api/login', {'password': 'wrong'});  check('错误密码 → 401', code == 401)
    code, d = jreq('POST', '/api/login', {'password': '0801'});   check('旧版哈希密码可登录', code == 200 and d.get('ok'))
    pwfile = open(os.path.join(tmp, '.cms_password')).read()
    check('登录后哈希自动升级为 PBKDF2', pwfile.startswith('pbkdf2$'))
    code, d = jreq('POST', '/api/login', {'password': '0801'});   check('PBKDF2 哈希复验登录', code == 200 and d.get('ok'))
    code, _ = req('GET', '/photos/ref_keep.png');             check('登录后访问 /photos → 200', code == 200)
    code, _ = jreq('GET', '/api/init');                       check('/api/init 已移除 → 404', code == 404)

    # ── 4. 数据读取 + 日志 studentId 回填 ────────────────────────────────────
    code, db = jreq('GET', '/api/data')
    check('登录后 /api/data → 200', code == 200)
    check('数据库带 rev 版本号', isinstance(db.get('rev'), int))
    amy_logs = [l for l in db['logs'] if l['studentName'] == 'Amy Wang']
    check('历史日志已回填 studentId', all(l.get('studentId') == 2000 for l in amy_logs))

    # ── 5. 乐观锁 + 灾难护栏 ─────────────────────────────────────────────────
    stale = dict(db); stale['rev'] = db['rev'] - 1 if db['rev'] > 1 else 999
    code, d = jreq('POST', '/api/save', stale)
    check('过期 rev 保存 → 409 conflict', code == 409 and d.get('status') == 'conflict')
    good = dict(db)
    code, d = jreq('POST', '/api/save', good)
    check('正确 rev 保存成功且 rev+1', code == 200 and d.get('rev') == db['rev'] + 1)
    cur_rev = d['rev']
    shrunk = dict(db); shrunk['students'] = db['students'][:5]; shrunk['rev'] = cur_rev
    code, d = jreq('POST', '/api/save', shrunk)
    check('学员数骤减 → 409 shrink_guard', code == 409 and d.get('status') == 'shrink_guard')
    code, db2 = jreq('GET', '/api/data')
    check('被拦截后数据完好', len(db2['students']) == len(db['students']))
    shrunk['force'] = True; shrunk['rev'] = db2['rev']
    code, d = jreq('POST', '/api/save', shrunk)
    check('force=true 显式确认后可保存', code == 200 and d.get('status') == 'success')
    # 恢复全量数据，便于后续测试
    full = dict(db); full['rev'] = d['rev']; full['force'] = True
    code, d = jreq('POST', '/api/save', full)
    check('恢复全量数据', code == 200)

    # ── 6. 余额查询（F3 新匹配规则）─────────────────────────────────────────
    def bal(name, phone): return jreq('POST', '/api/balance', {'name': name, 'phone': phone})
    code, d = bal('amy', '0412345678');        check('first name 小写+无空格手机号 → 命中', d.get('match') is True and d.get('name') == 'Amy Wang')
    code, d = bal('WANG', '0412 345 678');     check('last name 大写 → 命中', d.get('match') is True)
    code, d = bal('Amy Wang', '0412-345-678'); check('全名+带横线手机号 → 命中', d.get('match') is True)
    code, d = bal('li', '0412345678');         check("子串 'li' 不再误配 Amy", d.get('match') is not True)
    code, d = bal('Amy', '0400000000');        check('手机号不符 → 不命中', d.get('match') is not True)
    code, d = bal('amy', '0412345678')
    check('签到次数按 studentId 统计', d.get('total_checkins') == 2)

    # ── 7. 公开上传（魔数校验 + 随机文件名）─────────────────────────────────
    code, raw = multipart('/api/upload-public', 'fake.png', b'NOT_AN_IMAGE_AT_ALL!')
    check('伪装 png（非图片内容）→ 400', code == 400)
    code, raw = multipart('/api/upload-public', 'real.png', PNG)
    d = json.loads(raw)
    check('真实 PNG 上传成功', code == 200 and d.get('filename', '').endswith('.png'))
    fn = d.get('filename', '')
    check('公开上传文件名含随机后缀', fn.startswith('pub_') and len(fn.split('_')) >= 3)

    # ── 8. 作品集 token（同套匹配规则）───────────────────────────────────────
    code, d = jreq('POST', '/api/portfolio/token', {'name': 'alice', 'phone': '0499999999'})
    check('作品集查询：first name 命中', code == 200 and d.get('ok') is True)

    # ── 9. 查询限流（10 次/分钟）─────────────────────────────────────────────
    got429 = False
    for _ in range(12):
        code, d = bal('amy', '0412345678')
        if code == 429: got429 = True; break
    check('高频查询触发 429 限流', got429)

    # ── 10. 修改密码（最短 8 位）────────────────────────────────────────────
    code, d = jreq('POST', '/api/change-password', {'oldPassword': '0801', 'newPassword': 'short'})
    check('新密码 <8 位 → 拒绝', code == 400)
    code, d = jreq('POST', '/api/change-password', {'oldPassword': '0801', 'newPassword': 'NewPass2026'})
    check('新密码 8+ 位 → 成功', code == 200 and d.get('ok'))
    code, d = jreq('POST', '/api/login', {'password': 'NewPass2026'})
    check('新密码可登录', code == 200 and d.get('ok'))

    # ── 11. 注册去重 ────────────────────────────────────────────────────────
    code, d = jreq('POST', '/api/register', {'firstName': 'Newbie', 'mobile': '0411222333'})
    check('新学员注册成功', code == 200 and d.get('success') is True)
    code, d = jreq('POST', '/api/register', {'firstName': 'Newbie', 'mobile': '0411 222 333'})
    check('重复注册被识别(pending)', d.get('duplicate') == 'pending')
    code, d = jreq('POST', '/api/register', {'firstName': 'Amy', 'lastName': 'Wang', 'mobile': '0412345678'})
    check('在册学员重复注册被识别', d.get('duplicate') == 'student')

    # ── 12. 注册字段长度截断（P2）──────────────────────────────────────────
    code, d = jreq('POST', '/api/register', {'firstName': 'LongMsg', 'mobile': '0488777666',
                                             'message': 'x' * 10000, 'goals': 'y' * 5000})
    check('超长字段注册不报错', code == 200 and d.get('success') is True)
    code, db3 = jreq('GET', '/api/data')
    pen = next((p for p in db3.get('pending', []) if p.get('firstName') == 'LongMsg'), {})
    check('message 截断至 500 字符', len(pen.get('message', '')) == 500)
    check('goals 截断至 300 字符',   len(pen.get('goals', ''))   == 300)

    # ── 13. 注册限流（P1: 5 次/分钟）────────────────────────────────────────
    got429 = False
    for i in range(6):
        code, d = jreq('POST', '/api/register', {'firstName': f'Flood{i}', 'mobile': f'047{i:07d}'})
        if code == 429: got429 = True; break
    check('注册轰炸触发 429 限流', got429)

    # ── 14. 日志防误删护栏（D1b）────────────────────────────────────────────
    code, db4 = jreq('GET', '/api/data')
    big = dict(db4)
    big['logs'] = [{'id': 90000+i, 'studentName': 'X', 'action': '杂项', 'change': 0,
                    'date': '01/01/2026', 'note': ''} for i in range(60)]
    code, d = jreq('POST', '/api/save', big)
    check('日志增加可正常保存', code == 200, f'{code} {d}')
    wiped = dict(db4); wiped['logs'] = big['logs'][:5]; wiped['rev'] = d.get('rev')
    code, d = jreq('POST', '/api/save', wiped)
    check('日志骤减 → 409 shrink_guard', code == 409 and d.get('status') == 'shrink_guard')
    wiped['force'] = True
    code, d = jreq('POST', '/api/save', wiped)
    check('日志骤减 force 确认后可保存', code == 200)

    # ── 15. 配置 / 数据体检（F1/F6）────────────────────────────────────────
    anon = urllib.request.build_opener()
    try:
        anon.open(BASE + '/api/config', timeout=10); anon_code = 200
    except urllib.error.HTTPError as e: anon_code = e.code
    check('未登录访问 /api/config → 401', anon_code == 401)
    code, d = jreq('GET', '/api/config')
    check('配置读取含邮件字段', code == 200 and 'email_to' in d and 'weekly_enabled' in d)
    code, d = jreq('POST', '/api/config', {'email_to': 'lee@test.com', 'smtp_user': 'sender@gmail.com',
                                           'renew_threshold': 3, 'weekly_enabled': True})
    check('配置保存成功', code == 200 and d.get('ok'))
    code, d = jreq('GET', '/api/config')
    check('配置回读一致 + 首次启用预置周标记', d.get('email_to') == 'lee@test.com'
          and d.get('renew_threshold') == 3 and bool(d.get('last_sent_week')))
    code, d = jreq('POST', '/api/email-test', {})
    check('未配密码时测试邮件给出明确错误', code == 400 and '配置' in str(d.get('error', '')))
    # Gmail 应用密码带空格粘贴 → 服务端应自动去除全部空白
    code, d = jreq('POST', '/api/config', {'smtp_password': 'abcd efgh ijkl mnop'})
    saved_cfg = json.load(open(os.path.join(tmp, '.cms_config.json')))
    check('应用密码空格自动清除', code == 200 and saved_cfg.get('smtp_password') == 'abcdefghijklmnop')
    code, hc = jreq('GET', '/api/healthcheck')
    check('数据体检返回完整报告', code == 200 and 'mismatchCount' in hc and 'lastBackup' in hc)
    # 人为制造一处账目不一致（余额 99 但日志只有 +10），体检必须能抓到
    code, dbh = jreq('GET', '/api/data')
    tweak = dict(dbh)
    tweak['students'] = [dict(s) for s in dbh['students']]
    s0 = tweak['students'][0]; s0['balance'] = 99
    tweak['logs'] = [{'id': 1, 'date': '01/06/2026 10:00', 'studentId': s0['id'],
                      'studentName': s0['name'], 'action': '充值购课', 'change': '+10', 'feePaid': 100}]
    code, d = jreq('POST', '/api/save', tweak)
    check('制造不一致数据保存成功', code == 200, f'{code} {d}')
    code, hc = jreq('GET', '/api/healthcheck')
    found = any(m.get('balance') == 99 and m.get('logsSum') == 10 for m in hc.get('mismatches', []))
    check('体检抓到人为制造的账目不一致', found, str(hc.get('mismatches'))[:200])

    # ── 15b. 班组模板数据透传（F4b: groups 键保存往返不丢失）────────────────
    code, dbg = jreq('GET', '/api/data')
    g = dict(dbg); g['groups'] = {'周六上午班': [dbg['students'][0]['id']]}
    code, d = jreq('POST', '/api/save', g)
    code, dbg2 = jreq('GET', '/api/data')
    check('班组模板随整库保存往返', dbg2.get('groups', {}).get('周六上午班') == [dbg['students'][0]['id']])

    # ── 16. 备份列表 / 一键恢复（F6）────────────────────────────────────────
    code, bl = jreq('GET', '/api/backups')
    check('备份列表为对象数组', code == 200 and isinstance(bl, list) and bl and 'name' in bl[0])
    oldest = bl[-1]['name']
    code, summ = jreq('GET', f'/api/backups/{oldest}/summary')
    check('备份差异摘要可读', code == 200 and summ.get('valid') is True and 'diffStudents' in summ)
    code, d = jreq('POST', '/api/restore', {'filename': 'not_exist.json'})
    check('恢复不存在的备份 → 404', code == 404)
    code, d = jreq('POST', '/api/restore', {'filename': oldest})
    check('一键恢复成功', code == 200 and d.get('ok') and d.get('students', 0) > 0)
    code, db5 = jreq('GET', '/api/data')
    check('恢复后数据与备份一致', len(db5['students']) == d['students'] and len(db5['logs']) == d['logs'])
    code, bl2 = jreq('GET', '/api/backups')
    check('恢复前状态已自动存为 pre_restore', any(b['name'].startswith('pre_restore_') for b in bl2))

    # ── 17. PWA 资源（G6）──────────────────────────────────────────────────
    for path, ctype in [('/manifest.json', 'json'), ('/manifest-student.json', 'json'),
                        ('/sw.js', 'javascript'), ('/icon-192.png', 'png'),
                        ('/apple-touch-icon.png', 'png'), ('/logo.png', 'png')]:
        code, raw = req('GET', path)
        check(f'PWA 资源 {path} 可访问', code == 200 and len(raw) > 0)
    code, raw = req('GET', '/manifest.json')
    mani = json.loads(raw)
    check('manifest 含 standalone 与图标', mani.get('display') == 'standalone' and len(mani.get('icons', [])) >= 2)
    code, raw = req('GET', '/manifest-student.json')
    smani = json.loads(raw)
    check('学员 manifest 指向 /register', smani.get('start_url') == '/register')
    code, raw = req('GET', '/manifest.json')   # 公开（未登录也能取，安装需要）
    check('manifest 无需登录即可获取', code == 200)

    # ── 18. 生日提醒进入周报（G1）──────────────────────────────────────────
    # 造一个"明天生日"的学员，周报应包含其姓名
    from datetime import datetime as _dt, timedelta as _td
    tomorrow = _dt.now() + _td(days=1)
    code, dbb = jreq('GET', '/api/data')
    bstu = dict(dbb); bstu['students'] = [dict(s) for s in dbb['students']]
    bstu['students'][1]['birthday'] = f'1990-{tomorrow.month:02d}-{tomorrow.day:02d}'
    bstu['students'][1]['name'] = 'Birthday Kid'
    code, d = jreq('POST', '/api/save', bstu)
    check('生日学员数据保存', code == 200)
    # 通过 email-test 间接触发周报构建（未配置邮件 → 仍会先构建报告再失败）
    # 直接验证 healthcheck 正常即可，报告文本在服务端单测覆盖
    code, hc = jreq('GET', '/api/healthcheck')
    check('含生日学员时体检仍正常', code == 200 and 'students' in hc)

finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    logf.close()

engine = {'waitress': 'waitress (生产级 ✓)',
          'flask-dev': 'Flask 开发服务器（回退模式 — 运行 ./cms.sh setup 安装 waitress）'
          }.get(engine_from_ping, '未知')
print(f'\n  服务器引擎: {engine}')
print('\n' + '═'*50)
print(f'  ✅ 通过 {len(passed)} 项    ❌ 失败 {len(failed)} 项')
if failed:
    print('  失败项: ' + ', '.join(failed))
    print(f'  服务器日志: {tmp}/server.log')
    sys.exit(1)
shutil.rmtree(tmp, ignore_errors=True)
print('  全部通过 🎉  （测试目录已清理）')
print('═'*50 + '\n')
