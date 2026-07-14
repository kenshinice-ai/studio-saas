/* StudioSaaS CMS application source (JSX).
 * Edit THIS file, then rebuild the browser bundle with:
 *   bash backend/scripts/build_cms.sh
 * The compiled output (backend/frontend/assets/cms-app.js) is what
 * legacy-root/index.html actually loads — do not edit it by hand.
 */

const { useState, useEffect, useMemo, useRef, useCallback } = React;
const tenantSlug = window.STUDIOSAAS_TENANT_SLUG
    || new URLSearchParams(location.search).get('tenant')
    || ((location.pathname.match(/^\/([^/]+)(?:\/cms)?\/?$/) || [])[1])
    || '';

/* ═══════════════════ DATE UTILS (AU DD/MM/YYYY) ════════════════ */
const nowAU = () => new Date().toLocaleString('en-AU', {
    timeZone:'Australia/Melbourne', day:'2-digit', month:'2-digit', year:'numeric',
    hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false
});
const todayISO  = () => new Date().toLocaleDateString('en-CA');
/* B1: shift an ISO date by N days (local-safe via noon anchor) */
const shiftDate = (iso, delta) => {
    const d = new Date(`${iso}T12:00:00`);
    d.setDate(d.getDate() + delta);
    return d.toLocaleDateString('en-CA');
};
const fmtDate   = (s) => {
    if (!s) return '—';
    const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : String(s).split(' ')[0];
};
const daysSince = (iso) => {
    if (!iso) return 9999;
    const d = new Date(iso);
    return isNaN(d) ? 9999 : Math.floor((Date.now() - d) / 864e5);
};
/* A2: tenant 模式下签到/课时改走 v1 账本端点（与 Studio Admin 同一本账）。
   根目录单店模式（无 tenantSlug）保持原有整包保存路径不变。 */
const TENANT_SLUG = window.STUDIOSAAS_TENANT_SLUG || '';
const v1Api = async (path, options = {}) => {
    const r = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1${path}`, {
        credentials: 'include',
        headers: {'Content-Type': 'application/json'},
        ...options,
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
        const err = new Error(d.message || d.error || `HTTP ${r.status}`);
        err.status = r.status;
        throw err;
    }
    return d;
};

const parseMonthKey = (ds) => {
    if (!ds) return null;
    const s = String(ds);
    const a = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);  if (a) return `${a[3]}-${a[2].padStart(2,'0')}`;
    const b = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/);  if (b) return `${b[1]}-${b[2].padStart(2,'0')}`;
    const c = s.match(/^(\d{4})-(\d{2})/);                  if (c) return `${c[1]}-${c[2]}`;
    return null;
};
const fmtMK = (k) => { if (!k) return ''; const [y,m]=k.split('-'); return `${m}/${y}`; };

/* ═══════════════════ PIN  (Fix #9: sessionStorage) ═════════════ */
const PIN_KEY     = 'lp_pin_v1';
const SESSION_KEY = 'lp_sess_v1';
const getPin      = () => { try { const v=localStorage.getItem(PIN_KEY); return v?atob(v).replace('lp:',''):null; } catch{return null;} };
const savePin     = (p) => localStorage.setItem(PIN_KEY, btoa('lp:'+p));
const sessOK      = () => sessionStorage.getItem(SESSION_KEY)==='1';
const markSess    = () => sessionStorage.setItem(SESSION_KEY,'1');
const clearSess   = () => sessionStorage.removeItem(SESSION_KEY);

/* ── PIN Screen ── */
function PINScreen({ onUnlock }) {
    const stored = getPin();
    const isSetup = !stored;
    const [dig,  setDig]  = useState(['','','','']);
    const [conf, setConf] = useState(['','','','']);
    const [step, setStep] = useState(isSetup ? 'set' : 'enter');
    const [err,  setErr]  = useState('');
    const refs = useRef([]);

    const focus = (i) => refs.current[i]?.focus();

    const push = (val, arr, setArr, base) => {
        const i = arr.findIndex(d => d==='');
        if (i === -1) return;
        const na = [...arr]; na[i] = val; setArr(na);
        if (i < 3) focus(base + i + 1);
        if (i === 3) setTimeout(() => submit([...na]), 60);
    };
    const pop = (arr, setArr, base) => {
        const rev = [...arr].reverse();
        const i = rev.findIndex(d => d !== '');
        if (i === -1) return;
        const na = [...arr]; na[3-i] = ''; setArr(na);
        focus(base + 3 - i);
    };
    const submit = (filled) => {
        const pin = filled.join('');
        if (pin.length < 4) return;
        setErr('');
        if (step === 'enter') {
            if (pin === stored) onUnlock();
            else { setErr('PIN 不正确，请重试'); setDig(['','','','']); setTimeout(() => focus(0), 60); }
        } else if (step === 'set') {
            setStep('confirm'); setConf(['','','','']); setTimeout(() => focus(4), 60);
        } else {
            if (pin === dig.join('')) { savePin(dig.join('')); onUnlock(); }
            else { setErr('两次输入不一致，请重新设置'); setConf(['','','','']); setTimeout(() => focus(4), 60); }
        }
    };

    const Dots = ({arr}) => (
        <div className="flex gap-3 justify-center my-5">
            {arr.map((d,i) => <div key={i} className={`pin-dot ${d?'on':''}`}/>)}
        </div>
    );
    const Inputs = ({arr, setArr, base}) => (
        <div className="flex gap-3 justify-center">
            {arr.map((_,i) => (
                <input key={i} ref={el=>refs.current[base+i]=el}
                    type="password" inputMode="numeric" maxLength={1}
                    value={arr[i]} className="pin-input"
                    onChange={e => { const v=e.target.value.replace(/\D/,''); if(v) push(v,arr,setArr,base); }}
                    onKeyDown={e => { if(e.key==='Backspace') pop(arr,setArr,base); }}
                />
            ))}
        </div>
    );

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-900 to-indigo-950 p-4">
            <div className="bg-white rounded-3xl p-8 w-full max-w-xs shadow-2xl text-center anim">
	                <img src="/logo.png" alt="Studio" className="w-36 mx-auto mb-3"/>
	                <p className="tenant-slogan text-sm text-gray-500 italic mb-4">Learn, grow, and feel confident.</p>
	                <p className="text-sm text-gray-400 mb-4">
                    {step==='set' ? '首次使用，请设置 4 位 PIN 码' : step==='confirm' ? '再次输入确认 PIN' : '输入 PIN 码解锁'}
                </p>
                {step !== 'confirm'
                    ? <><Dots arr={dig}/><Inputs arr={dig} setArr={setDig} base={0}/></>
                    : <><Dots arr={conf}/><Inputs arr={conf} setArr={setConf} base={4}/></>
                }
                {err && <p className="text-red-500 text-xs mt-4 font-medium">{err}</p>}
                {step==='enter' && (
                    <details className="mt-5 text-left">
                        <summary className="text-xs text-gray-400 cursor-pointer select-none text-center">忘记 PIN？</summary>
                        <p className="text-xs text-gray-400 mt-2 bg-gray-50 rounded-xl p-3 leading-relaxed">
                            在浏览器开发者工具的 Console 中运行：<br/>
                            <code className="text-indigo-600 font-mono break-all">localStorage.removeItem('lp_pin_v1')</code><br/>
                            刷新页面后即可重新设置 PIN。
                        </p>
                    </details>
                )}
            </div>
        </div>
    );
}

/* ═══════════════════ SVG BAR CHART ════════════════════════════ */
function BarChart({ items, color='#6366f1', h=140, prefix='' }) {
    if (!items?.length) return <p className="text-center text-gray-400 text-sm py-6">暂无数据</p>;
    const max = Math.max(...items.map(d=>d.v), 0.01);
    const W=54, PAD=6;
    return (
        <svg viewBox={`0 0 ${items.length*W} ${h+24}`} className="w-full overflow-visible">
            {items.map((d,i) => {
                const bh = Math.max(2, (d.v/max)*(h-12));
                return (
                    <g key={i} transform={`translate(${i*W+PAD},0)`}>
                        <rect x={4} y={h-bh} width={W-PAD*2} height={bh} fill={color} rx={3} opacity={0.82}/>
                        {d.v>0 && <text x={(W-PAD*2)/2+4} y={h-bh-4} textAnchor="middle" fontSize={8} fill="#374151" fontWeight="bold">{prefix}{d.v}</text>}
                        <text x={(W-PAD*2)/2+4} y={h+16} textAnchor="middle" fontSize={7.5} fill="#9ca3af">{d.l}</text>
                    </g>
                );
            })}
        </svg>
    );
}

/* ═══════════════════ BALANCE BADGE ════════════════════════════ */
/* B5 (v4.7): 统一空状态组件 — 图标 + 主文 + 次文 */
function EmptyState({icon='📭', main='暂无数据', sub=''}) {
    return (
        <div className="p-8 text-center">
            <p className="text-4xl mb-2">{icon}</p>
            <p className="font-bold text-gray-500 text-sm">{main}</p>
            {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
        </div>
    );
}

function BalBadge({ n }) {
    const v = parseInt(n,10)||0;
    if (v===0) return <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-red-100 text-red-700 whitespace-nowrap">0 ⚠️</span>;
    if (v<=2)  return <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-orange-100 text-orange-700 whitespace-nowrap">{v} ⚡</span>;
    if (v<=4)  return <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-700 whitespace-nowrap">{v}</span>;
    return           <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-green-100 text-green-700 whitespace-nowrap">{v}</span>;
}

/* ═══════════════════ TOAST ════════════════════════════════════ */
function Toast({ msg, type, action, onDone }) {
    /* G2: toasts with a copy action stay longer so they can be tapped */
    useEffect(() => { const t=setTimeout(onDone, action?6000:2700); return()=>clearTimeout(t); }, []);
    const bg = type==='error'?'bg-red-600':type==='warn'?'bg-amber-500':'bg-gray-900';
    return (
        <div className={`toast toast-bottom fixed left-1/2 -translate-x-1/2 z-[999] ${bg} text-white px-5 py-3 rounded-2xl shadow-2xl text-sm font-bold max-w-xs text-center`}>
            <div>{type==='error'?'❌':type==='warn'?'⚠️':'✅'} {msg}</div>
            {action && (
                <button onClick={()=>{action.onClick(); onDone();}}
                    className="mt-2 w-full bg-white/20 active:bg-white/30 rounded-lg py-1.5 text-xs font-bold">
                    {action.label}
                </button>
            )}
        </div>
    );
}

/* ═══════════════════ Fix #8: CUSTOM CONFIRM DIALOG ═══════════ */
function ConfirmDialog({ dialog, onClose }) {
    if (!dialog) return null;
    return (
        <div className="fixed inset-0 bg-black/50 z-[95] flex items-center justify-center p-4" onClick={onClose}>
            <div className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl anim" onClick={e=>e.stopPropagation()}>
                {dialog.title && <p className="font-bold text-gray-800 mb-2">{dialog.title}</p>}
                <p className="text-gray-500 text-sm leading-relaxed mb-6">{dialog.message}</p>
                <div className="flex gap-3">
                    <button onClick={onClose}
                        className="flex-1 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm">
                        取消
                    </button>
                    <button onClick={() => { dialog.onConfirm(); onClose(); }}
                        className={`flex-1 py-3 font-bold rounded-xl text-sm text-white ${dialog.danger?'bg-red-600 active:bg-red-700':'bg-indigo-600 active:bg-indigo-700'}`}>
                        {dialog.confirmText || '确认'}
                    </button>
                </div>
            </div>
        </div>
    );
}

/* ═══════════════════ Fix #1+5: SEARCHABLE STUDENT PICKER ═════ */
function StudentPicker({ students, value, onChange, placeholder='-- 选择学员 --', showBal=true }) {
    const [q,    setQ]    = useState('');
    const [open, setOpen] = useState(false);
    const ref = useRef(null);
    const sel = students.find(s => s.id===value);

    /* Fix #1: reset internal search text when value is cleared externally */
    useEffect(() => { if (!value) setQ(''); }, [value]);

    const filtered = useMemo(() =>
        q ? students.filter(s => s.name.toLowerCase().includes(q.toLowerCase())) : students,
    [students, q]);

    /* Fix #5: also listen for touchstart to close on iPad tap-outside */
    useEffect(() => {
        const h = e => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
        document.addEventListener('mousedown',  h);
        document.addEventListener('touchstart', h, {passive:true});
        return () => {
            document.removeEventListener('mousedown',  h);
            document.removeEventListener('touchstart', h);
        };
    }, []);

    return (
        <div ref={ref} className="relative">
            <div className="flex items-center border border-gray-300 rounded-xl bg-white focus-within:ring-2 focus-within:ring-indigo-500 overflow-hidden">
                <span className="pl-3 text-gray-400 flex-shrink-0">🔍</span>
                <input type="text"
                    placeholder={sel ? sel.name : placeholder}
                    value={open ? q : (sel ? sel.name : '')}
                    onFocus={() => { setQ(''); setOpen(true); }}
                    onChange={e => { setQ(e.target.value); setOpen(true); }}
                    className="flex-1 px-2 py-3 outline-none bg-transparent"
                />
                {sel && (
                    <button type="button" onClick={() => { onChange(null); setQ(''); }}
                        className="pr-3 text-gray-400 active:text-gray-700 text-xl leading-none py-3 px-2">×</button>
                )}
            </div>
            {open && (
                <div className="absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-2xl max-h-52 overflow-y-auto sl">
                    {!filtered.length
                        ? <div className="p-4 text-center text-gray-400 text-sm">无匹配</div>
                        : filtered.map(s => (
                            <button key={s.id} type="button"
                                onClick={() => { onChange(s.id); setQ(s.name); setOpen(false); }}
                                className={`w-full text-left px-4 py-3 active:bg-indigo-50 text-sm flex justify-between items-center min-h-[44px] ${s.id===value?'bg-indigo-50':'hover:bg-indigo-50'}`}>
                                <span className="font-medium truncate pr-2">{s.name}</span>
                                {showBal && <BalBadge n={s.balance}/>}
                            </button>
                        ))
                    }
                </div>
            )}
        </div>
    );
}

function mediaSrc(value, fallbackBase='photos') {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (raw.startsWith('media:')) {
        const id = raw.slice(6);
        const slug = window.STUDIOSAAS_TENANT_SLUG || new URLSearchParams(location.search).get('tenant') || '';
        return `/s/${encodeURIComponent(slug)}/v1/media/${encodeURIComponent(id)}`;
    }
    return `/${fallbackBase}/${encodeURIComponent(raw)}`;
}

function portfolioImgSrc(studentId, item) {
    if (item?.mediaUrl) return item.mediaUrl;
    const filename = item?.filename || '';
    if (String(filename).startsWith('media:')) return mediaSrc(filename, 'portfolio');
    return `/portfolio/img/${encodeURIComponent(studentId)}/${encodeURIComponent(filename)}`;
}

/* S3: 列表网格用 360px 缩略图（v1 媒体路由 ?thumb=1），灯箱/打印仍用原图 */
function portfolioThumbSrc(studentId, item) {
    const src = portfolioImgSrc(studentId, item);
    if (src.includes('/v1/media/')) return src + (src.includes('?') ? '&' : '?') + 'thumb=1';
    return src;
}

/* ═══════════════════ PHOTO AVATAR ════════════════════════════ */
function PhotoAvatar({ photo, name, size='sm' }) {
    const cls = size==='sm' ? 'w-9 h-9 text-xs' : size==='md' ? 'w-14 h-14 text-base' : 'w-20 h-20 text-2xl';
    const initials = (name||'?').trim().split(/\s+/).map(w=>w[0]||'').slice(0,2).join('').toUpperCase()||'?';
    if (photo) return <img src={mediaSrc(photo)} className={`${cls} rounded-full object-cover flex-shrink-0 border-2 border-white shadow-sm`} alt={name}/>;
    return <div className={`${cls} rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold flex-shrink-0 border-2 border-white shadow-sm`}>{initials}</div>;
}

/* ═══════════════════ PHOTO UPLOADER ══════════════════════════ */
function PhotoUploader({ value, onChange }) {
    const [uploading, setUploading] = useState(false);
    const handleFile = async (e) => {
        const file = e.target.files[0]; if (!file) return;
        if (file.size > 5*1024*1024) { alert('照片不能超过 5MB'); return; }
        setUploading(true);
        try {
            const fd = new FormData(); fd.append('file', file);
            /* S2: same-origin fetch carries the session cookie — no token needed */
            const r  = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/media/upload`, {method:'POST', credentials:'include', body:fd});
            const d  = await r.json();
            if (d.filename) onChange(d.filename);
        } catch { alert('上传失败，请重试'); }
        finally { setUploading(false); e.target.value=''; }
    };
    const btnBase = uploading ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed' : '';
    return (
        <div className="flex items-center gap-4">
            {value
                ? <img src={mediaSrc(value)} className="w-14 h-14 rounded-full object-cover border-2 border-indigo-100 flex-shrink-0"/>
                : <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center text-2xl border-2 border-dashed border-gray-300 flex-shrink-0">📷</div>
            }
            <div className="space-y-1.5">
                <div className="flex gap-2 flex-wrap">
                    <label className={`cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[40px] ${btnBase||'bg-indigo-50 text-indigo-700 border-indigo-200 active:bg-indigo-100'}`}>
                        📁 {uploading ? '上传中...' : value ? '更换' : '选择'}
                        <input type="file" accept="image/*" onChange={handleFile} disabled={uploading} className="hidden"/>
                    </label>
                    <label className={`cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[40px] ${btnBase||'bg-purple-50 text-purple-700 border-purple-200 active:bg-purple-100'}`}>
                        📷 拍照
                        <input type="file" accept="image/*" capture="environment" onChange={handleFile} disabled={uploading} className="hidden"/>
                    </label>
                </div>
                {value && <button type="button" onClick={()=>onChange('')} className="text-xs text-red-400 active:text-red-600">移除照片</button>}
            </div>
        </div>
    );
}

/* ═══════════════ MAINTENANCE PANEL（体检/邮件/备份恢复）═══════════ */
function MaintSection({ onRestored, renewTh, saveRenewTh }) {
    const [hc, setHc]         = useState(null);
    const [hcBusy, setHcBusy] = useState(false);
    const [cfg, setCfg]       = useState(null);
    const [pw, setPw]         = useState('');
    const [cfgMsg, setCfgMsg] = useState('');
    const [bks, setBks]       = useState(null);
    const [bkSel, setBkSel]   = useState(null);
    const [busy, setBusy]     = useState(false);
    const post = (url, body) => fetch(url, {method:'POST', credentials:'include',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});

    /* 检测旧版服务器：新接口 404 = server.py 没更新或没重启 */
    const [stale, setStale] = useState(false);
    useEffect(() => {
        fetch('/api/config', {credentials:'include'}).then(r => {
            if (r.status === 404) { setStale(true); return null; }
            return r.json();
        }).then(d => { if (d) setCfg(d); }).catch(()=>{});
    }, []);

    const runHC = async () => {
        setHcBusy(true);
        try {
            const r = await fetch('/api/healthcheck', {credentials:'include'});
            if (r.status === 404) { setStale(true); setHc(null); return; }
            setHc(await r.json());
        }
        catch { setHc({error:'连接失败'}); }
        finally { setHcBusy(false); }
    };
    const saveCfg = async () => {
        if (!cfg) return;
        setBusy(true); setCfgMsg('');
        try {
            const body = {email_to:cfg.email_to, smtp_user:cfg.smtp_user, smtp_host:cfg.smtp_host,
                          smtp_port:cfg.smtp_port, weekly_enabled:cfg.weekly_enabled, renew_threshold:renewTh};
            if (pw) body.smtp_password = pw;
            const r = await post('/api/config', body);
            if (r.status === 404) { setStale(true); setCfgMsg(''); return; }
            setCfgMsg(r.ok ? '✅ 已保存' : `❌ 保存失败 (HTTP ${r.status})`);
            if (r.ok && pw) { setPw(''); setCfg(c=>({...c, hasPassword:true})); }
        } catch { setCfgMsg('❌ 连接失败'); }
        finally { setBusy(false); }
    };
    const testEmail = async () => {
        setBusy(true); setCfgMsg('发送中…（请先点过「保存配置」）');
        try {
            const r = await post('/api/email-test', {});
            const d = await r.json();
            setCfgMsg(d.ok ? '✅ 测试邮件已发出，请查收（含每周汇总预览）' : `❌ ${d.error||'发送失败'}`);
        } catch { setCfgMsg('❌ 连接失败'); }
        finally { setBusy(false); }
    };
    const loadBks = async () => {
        try {
            const r = await fetch('/api/backups', {credentials:'include'});
            const d = await r.json();
            /* 旧版服务器返回字符串数组 → 兼容显示并提示升级 */
            if (Array.isArray(d) && d.length && typeof d[0] === 'string') { setStale(true); setBks([]); return; }
            setBks(Array.isArray(d) ? d : []);
        } catch { setBks([]); }
    };
    const clearPwaCache = async () => {
        try {
            if ('serviceWorker' in navigator) {
                const regs = await navigator.serviceWorker.getRegistrations();
                regs.forEach(r => r.active && r.active.postMessage({type:'CLEAR_LPCMS_CACHE'}));
            }
            if ('caches' in window) {
                const keys = await caches.keys();
                await Promise.all(keys.filter(k => k.startsWith('lpcms-')).map(k => caches.delete(k)));
            }
            window.alert('✅ PWA 缓存已清理，页面将刷新。若主屏幕 App 图标仍未更新，请删除后重新添加。');
            window.location.reload();
        } catch(e) {
            window.alert('❌ 缓存清理失败，请关闭 App 后重新打开。');
        }
    };
    const pickBk = async (name) => {
        try { const r = await fetch(`/api/backups/${name}/summary`, {credentials:'include'});
              setBkSel({name, ...(await r.json())}); } catch {}
    };
    const doRestore = async () => {
        if (!bkSel || !bkSel.valid) return;
        const d1 = `确认恢复备份 ${bkSel.name}？\n\n该备份: ${bkSel.students} 名学员 / ${bkSel.logs} 条日志\n与当前相比: 学员 ${bkSel.diffStudents>=0?'+':''}${bkSel.diffStudents} / 日志 ${bkSel.diffLogs>=0?'+':''}${bkSel.diffLogs}`;
        if (!window.confirm(d1)) return;
        if (!window.confirm('再次确认：当前数据会先自动另存为 pre_restore 备份（可再恢复回来），然后被该备份覆盖。继续？')) return;
        setBusy(true);
        try {
            const r = await post('/api/restore', {filename: bkSel.name});
            const d = await r.json();
            if (d.ok) { window.alert(`✅ 恢复完成：${d.students} 名学员 / ${d.logs} 条日志。页面即将刷新数据。`); onRestored(); }
            else window.alert(`❌ ${d.error||'恢复失败'}`);
        } catch { window.alert('❌ 连接失败'); }
        finally { setBusy(false); }
    };
    const inp = "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400";
    if (stale) return (
        <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="bg-red-50 border border-red-300 rounded-xl p-3 space-y-1.5">
                <p className="text-xs font-bold text-red-700">⚠️ 服务器还在运行旧版本</p>
                <p className="text-xs text-red-600">界面已是新版，但数据体检 / 邮件 / 备份恢复需要新版 server.py 支持。请：</p>
                <p className="text-xs text-red-600 font-mono bg-red-100 rounded-lg px-2 py-1.5">1. 用新版 server.py 覆盖 CMS 目录里的旧文件<br/>2. 终端运行 ./cms.sh restart<br/>3. 刷新本页面</p>
                <p className="text-xs text-red-500">验证方法：浏览器打开 /api/ping，version 应为 4.3.3-aws</p>
            </div>
        </div>
    );
    return (<>
        {/* 数据体检 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">🩺 数据体检</p>
            <button onClick={runHC} disabled={hcBusy}
                className="w-full bg-teal-50 active:bg-teal-100 disabled:opacity-50 text-teal-700 border border-teal-200 py-2.5 rounded-xl font-bold text-sm">
                {hcBusy ? '体检中…' : '运行数据体检'}</button>
            {hc && !hc.error && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-1 text-xs text-gray-600">
                    <p>学员 {hc.students}（活跃 {hc.activeStudents}）· 日志 {hc.logs} 条 · 库 {hc.dbSizeKB} KB</p>
                    <p className={hc.mismatchCount?'text-amber-600 font-bold':'text-green-600'}>
                        账目核对: {hc.mismatchCount ? `${hc.mismatchCount} 人不一致` : '全部一致 ✓'}</p>
                    {(hc.mismatches||[]).slice(0,8).map((m,i)=>(
                        <p key={i} className="pl-2 text-amber-700">· {m.name}: 余额 {m.balance}，日志合计 {m.logsSum}（差 {m.diff>0?'+':''}{m.diff}）</p>))}
                    {hc.duplicateNames.length>0 && <p className="text-amber-600">重名学员: {hc.duplicateNames.join('、')}</p>}
                    {hc.missingPhotos.length>0 && <p className="text-amber-600">照片文件丢失: {hc.missingPhotos.length} 人</p>}
                    {hc.conflictCopies.length>0 && <p className="text-red-600 font-bold">⚠️ iCloud 冲突副本: {hc.conflictCopies.join('、')}</p>}
                    <p>待审申请 {hc.pendingCount} 条 · 最近备份 {hc.lastBackup||'无'}（{hc.backupCount} 份）</p>
                </div>)}
            {hc && hc.error && <p className="text-xs text-red-500">体检失败，请重试</p>}
        </div>
        {/* 待续课阈值 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">⚡ 待续课提醒阈值（剩余 ≤N 节）</p>
            <div className="flex gap-2">
                {[1,2,3,5].map(d=>(
                    <button key={d} onClick={()=>{saveRenewTh(d); post('/api/config',{renew_threshold:d}).catch(()=>{});}}
                        className={`flex-1 py-2 rounded-xl text-xs font-bold border ${renewTh===d?'bg-indigo-600 text-white border-indigo-600':'bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100'}`}>{d} 节</button>))}
            </div>
            <p className="text-[11px] text-gray-400">影响学员页「低余额」筛选和每周邮件中的待续课名单</p>
        </div>
        {/* PWA 缓存 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">📱 主屏幕 App / PWA 缓存</p>
            <button onClick={clearPwaCache}
                className="w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm">
                清理 PWA 缓存并刷新</button>
            <p className="text-[11px] text-gray-400">用于更新主屏幕图标、Service Worker 或修复旧页面缓存。</p>
        </div>
        {/* 每周汇总邮件 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">📧 每周汇总邮件（周一 10:00）</p>
            {!cfg ? <p className="text-xs text-gray-400">加载中…</p> : (<>
                <input className={inp} placeholder="收件邮箱" value={cfg.email_to||''}
                    onChange={e=>setCfg({...cfg, email_to:e.target.value})}/>
                <input className={inp} placeholder="发件 Gmail 地址" value={cfg.smtp_user||''}
                    onChange={e=>setCfg({...cfg, smtp_user:e.target.value})}/>
                <input className={inp} type="password" value={pw} onChange={e=>setPw(e.target.value)}
                    placeholder={cfg.hasPassword?'应用专用密码（已保存，留空不变）':'Gmail 应用专用密码（16位）'}/>
                <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-gray-600">每周一自动发送</p>
                    <button onClick={()=>setCfg({...cfg, weekly_enabled:!cfg.weekly_enabled})}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${cfg.weekly_enabled?'bg-indigo-600':'bg-gray-300'}`}>
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${cfg.weekly_enabled?'translate-x-6':'translate-x-1'}`}/></button>
                </div>
                {cfgMsg && <p className={`text-xs font-medium ${cfgMsg.startsWith('✅')?'text-green-600':cfgMsg.startsWith('❌')?'text-red-500':'text-gray-500'}`}>{cfgMsg}</p>}
                <div className="flex gap-2">
                    <button onClick={saveCfg} disabled={busy}
                        className="flex-1 bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm">保存配置</button>
                    <button onClick={testEmail} disabled={busy}
                        className="flex-1 bg-white border border-indigo-300 active:bg-indigo-50 disabled:opacity-50 text-indigo-700 py-2.5 rounded-xl font-bold text-sm">发送测试邮件</button>
                </div>
                <p className="text-[11px] text-gray-400">需要 Gmail「应用专用密码」，获取方法见《邮件设置教程》文档</p>
            </>)}
        </div>
        {/* 备份与恢复 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">♻️ 备份与恢复</p>
            {!bks ? (
                <button onClick={loadBks} className="w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm">查看备份列表</button>
            ) : (<>
                <div className="max-h-44 overflow-y-auto space-y-1 modal-scroll">
                    {bks.length===0 && <p className="text-xs text-gray-400 text-center py-2">暂无备份</p>}
                    {bks.map(b=>(
                        <button key={b.name} onClick={()=>pickBk(b.name)}
                            className={`w-full text-left px-3 py-2 rounded-xl border text-xs ${bkSel?.name===b.name?'border-indigo-400 bg-indigo-50':'border-gray-200 bg-gray-50 active:bg-gray-100'}`}>
                            <span className="font-bold text-gray-700">{b.mtime}</span>
                            <span className="text-gray-400 ml-2">{(b.size/1024).toFixed(0)} KB</span>
                            {b.name.startsWith('pre_restore') && <span className="ml-1 text-amber-600 font-bold">恢复前存档</span>}
                        </button>))}
                </div>
                {bkSel && (bkSel.valid
                    ? <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-3 space-y-1 text-xs text-indigo-800">
                        <p className="font-bold">{bkSel.students} 名学员 · {bkSel.logs} 条日志</p>
                        <p>与当前相比: 学员 {bkSel.diffStudents>=0?'+':''}{bkSel.diffStudents} · 日志 {bkSel.diffLogs>=0?'+':''}{bkSel.diffLogs}</p>
                        <button onClick={doRestore} disabled={busy}
                            className="w-full mt-1 bg-red-600 active:bg-red-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm">恢复此备份（双重确认）</button>
                      </div>
                    : <p className="text-xs text-red-500">该备份文件已损坏，不可恢复</p>)}
            </>)}
        </div>
    </>);
}

/* ═══════════════════ LOGIN SCREEN ════════════════════════════ */
function LoginScreen({ onLogin }) {
    const [email, setEmail] = useState(() => localStorage.getItem(`lp_admin_email_${tenantSlug}`) || '');
    const [pw,   setPw]   = useState('');
    const [busy, setBusy] = useState(false);
    const [err,  setErr]  = useState('');

    const submit = async (e) => {
        e && e.preventDefault();
        if (!email || !pw) { setErr('请输入管理员邮箱和密码'); return; }
        setBusy(true); setErr('');
        try {
            const r = await fetch('/s/' + encodeURIComponent(tenantSlug) + '/v1/auth/legacy-login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({email, password: pw}),
                credentials: 'include'
            });
            const d = await r.json();
            if (d.ok) { localStorage.setItem(`lp_admin_email_${tenantSlug}`, email); onLogin(); }
            else { setErr(d.error || '密码错误'); setPw(''); }
        } catch { setErr('连接失败，请重试'); }
        finally { setBusy(false); }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-900 to-indigo-950 p-4">
            <div className="bg-white rounded-3xl p-8 w-full max-w-xs shadow-2xl text-center anim">
	                <img src="/logo.png" alt="Studio" className="w-36 mx-auto mb-3"/>
	                <p className="tenant-slogan text-sm text-gray-500 italic mb-4">Learn, grow, and feel confident.</p>
	                <p className="text-sm text-gray-400 mb-6">请输入 Studio CMS 账号</p>
                <form onSubmit={submit} className="space-y-3">
                    <input
                        type="email"
                        placeholder="管理员邮箱"
                        value={email}
                        onChange={e => setEmail(e.target.value)}
                        autoFocus
                        className="w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-sm focus:ring-2 focus:ring-indigo-500"
                    />
                    <input
                        type="password"
                        placeholder="密码"
                        value={pw}
                        onChange={e => setPw(e.target.value)}
                        className="w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-lg tracking-widest focus:ring-2 focus:ring-indigo-500"
                    />
                    {err && <p className="text-red-500 text-xs font-medium">{err}</p>}
                    <button type="submit" disabled={busy || !email || !pw}
                        className="w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm">
                        {busy ? '验证中...' : '进入系统 →'}
                    </button>
                </form>
            </div>
        </div>
    );
}

/* ═══════════════════ MAIN APP ════════════════════════════════ */
function App() {
    /* Fix #9: PIN uses sessionStorage so same tab stays unlocked */
    const [pinOK, setPinOK] = useState(sessOK);
    /* P2: PIN is optional — default OFF */
    const [pinEnabled, setPinEnabled] = useState(() => localStorage.getItem('lp_pin_enabled') === 'true');
    const togglePin = (val) => { setPinEnabled(val); localStorage.setItem('lp_pin_enabled', val?'true':'false'); };

    const [db,  setDb]  = useState({students:[],logs:[],rosters:{},pending:[]});
    const [tab, setTab] = useState('dashboard');
    const [moreOpen, setMoreOpen] = useState(false);
    const [selS, setSelS] = useState(null);
    const [editP, setEditP] = useState(false);
    const [busy, setBusy] = useState(false);
    const [conn, setConn] = useState(false);
    const [connErr, setConnErr] = useState(null);
    const [toast, setToast] = useState(null);
    const [confirmDialog, setConfirmDialog] = useState(null); // Fix #8
    const [showSettings, setShowSettings] = useState(false);
    const [newPin1, setNewPin1] = useState('');
    const [newPin2, setNewPin2] = useState('');
    // Auth state
    const [loggedIn, setLoggedIn]   = useState(false);
    const [pwOld,    setPwOld]      = useState('');
    const [pwNew1,   setPwNew1]     = useState('');
    const [pwNew2,   setPwNew2]     = useState('');
    const [pwBusy,   setPwBusy]     = useState(false);
    const [pwMsg,    setPwMsg]      = useState('');
    // Global search
    const [gOpen, setGOpen] = useState(false);
    const [gQ,    setGQ]    = useState('');
    // Portfolio
    const [portLB,      setPortLB]      = useState(null);  // lightbox: {items,idx}
    const [portUpload,  setPortUpload]  = useState(false); // upload modal open
    const [portUpFile,  setPortUpFile]  = useState(null);  // {file,dataUrl,note,date,public}
    const [portEdit,    setPortEdit]    = useState(null);  // {sid,item,note,date,public}
    const [portBusy,    setPortBusy]    = useState(false);
    const lbTouchX    = useRef(0);  // M1: swipe start X
    // Fix ⑪: configurable inactive-days threshold (stored in localStorage)
    const [inactiveDays, setInactiveDays] = useState(() => parseInt(localStorage.getItem('lp_inactive_days')||'90',10));
    const saveInactiveDays = (v) => { const n=parseInt(v,10); if(n>0){setInactiveDays(n);localStorage.setItem('lp_inactive_days',String(n));} };

    // Students tab
    const [srch,     setSrch]     = useState('');
    const [sortBy,   setSortBy]   = useState('date-desc');
    const [filterBy, setFilterBy] = useState('all');

    // Roster tab
    const [rDate, setRDate] = useState(todayISO);
    const [rPick, setRPick] = useState(null);
    const [grpSel, setGrpSel] = useState('');   /* F4: 班组模板选择 */
    /* A1: 每周课表（tenant 模式，存于 PostgreSQL class_schedules） */
    const [schedules, setSchedules] = useState([]);
    /* A3: 经营真账（估算），来自 v1 dashboard */
    const [bizStats, setBizStats] = useState(null);
    /* B3: 档案页上课记录（v4.6），来自 v1 attendance */
    const [attHistory, setAttHistory] = useState(null);
    const [schedEdit, setSchedEdit] = useState(null);   // null | {id?, label, weekday, startTime, durationMinutes, capacity, studentIds}
    const [schedPick, setSchedPick] = useState(null);
    /* F5: 待续课阈值（可在设置页调整） */
    const [renewTh, setRenewTh] = useState(() => parseInt(localStorage.getItem('lp_renew_threshold')||'2',10));
    const saveRenewTh = (v) => { const n=parseInt(v,10); if(n>=0){setRenewTh(n);localStorage.setItem('lp_renew_threshold',String(n));} };

    // Topup tab
    const [tuStu, setTuStu] = useState(null);
    /* A2: 结算页模式 — 充值 / 退款退课（v5.5 方案 B：同页切换，单一路径） */
    const [settleMode, setSettleMode] = useState('topup');
    const [rfCr, setRfCr] = useState('');
    const [rfAmt, setRfAmt] = useState('');
    const [rfReason, setRfReason] = useState('');
    const [tuCr,  setTuCr]  = useState('');
    const [tuFee, setTuFee] = useState('');
    const [tuPkg, setTuPkg] = useState('');
    const [tuPay, setTuPay] = useState('微信');

    // Logs tab
    const [lSrch,     setLSrch]     = useState('');
    const [lStu,      setLStu]      = useState(null); // U3: precise student filter
    const [lAct,      setLAct]      = useState('');
    const [lDateFrom, setLDateFrom] = useState('');
    const [lDateTo,   setLDateTo]   = useState('');
    const [lPage,     setLPage]     = useState(1);
    const LPP = 30;

    // Stats tab
    const [sPeriod, setSPeriod] = useState('monthly');
    const [sYear,   setSYear]   = useState(String(new Date().getFullYear()));
    const [sFrom,   setSFrom]   = useState('');
    const [sTo,     setSTo]     = useState('');
    const [sStu,    setSStu]    = useState(null); // financial report filter
    const [sStu2,   setSStu2]   = useState(null); // individual student analysis

    // Pending approvals state
    const [approveCredits, setApproveCredits] = useState({}); // {pendingId: creditValue}
    const [followUpDates, setFollowUpDates] = useState({}); // {registrationId: YYYY-MM-DD}

    // Package management state (settings)
    const [pkgEditId,  setPkgEditId]  = useState(null); // null=add new, number=editing id
    const [pkgName,    setPkgName]    = useState('');
    const [pkgCredits, setPkgCredits] = useState('');
    const [pkgPrice,   setPkgPrice]   = useState('');
    const [tenantBrand, setTenantBrand] = useState(() => window.STUDIOSAAS_BRAND || {});
    const [team, setTeam] = useState([]);
    const [teamBusy, setTeamBusy] = useState(false);
    const [teamForm, setTeamForm] = useState({fullName:'',email:'',role:'teacher',temporaryPassword:''});
    const [actorRole, setActorRole] = useState('');
    const ownerRoles = ['owner','platform_super_admin','super_admin'];
    const roleTabs = {
        owner: ['dashboard','roster','students','new_student','pending','topup','logs','stats'],
        platform_super_admin: ['dashboard','roster','students','new_student','pending','topup','logs','stats'],
        super_admin: ['dashboard','roster','students','new_student','pending','topup','logs','stats'],
        manager: ['dashboard','roster','students','new_student','pending','topup','logs','stats'],
        teacher: ['dashboard','students','logs'],
        front_desk: ['dashboard','students','new_student','pending','topup','logs'],
        staff: ['dashboard','roster','students','new_student','pending','topup','logs'],
    };
    const allowedTabs = roleTabs[actorRole] || ['dashboard'];
    const canManageOperations = [...ownerRoles,'manager'].includes(actorRole);
    const canWriteStudents = [...ownerRoles,'manager','front_desk','staff'].includes(actorRole);
    const canWriteCredits = [...ownerRoles,'manager','front_desk','staff'].includes(actorRole);
    const canWritePortfolio = [...ownerRoles,'manager','teacher','staff'].includes(actorRole);

    // Photo state for forms (shared — forms can't be open simultaneously)
    const [formPhoto, setFormPhoto] = useState('');
    const [editPhoto, setEditPhoto] = useState(''); // photo state for edit-profile modal

    const cooldowns  = useRef(new Set());
    const wasDownRef = useRef(false);
    const showToast = (msg, type='success', action=null) => setToast({msg, type, action, key:Date.now()});

    useEffect(() => {
        const syncBrand = (event) => setTenantBrand(event?.detail || window.STUDIOSAAS_BRAND || {});
        window.addEventListener('studiosaas:brand', syncBrand);
        syncBrand();
        return () => window.removeEventListener('studiosaas:brand', syncBrand);
    }, []);

    useEffect(() => {
        if (showSettings && TENANT_SLUG && canManageOperations) loadTeam();
    }, [showSettings, actorRole]);

    useEffect(() => {
        if (actorRole && !allowedTabs.includes(tab)) setTab('dashboard');
    }, [actorRole, tab]);

    const tenantLogoUrl = tenantBrand.logo_url || tenantBrand.logoUrl || '/logo-light.png';
    const tenantDisplayName = tenantBrand.name || tenantBrand.studioName || 'Studio';

    const preferenceProfile = () => {
        const raw = tenantBrand.registration_profile || tenantBrand.registrationProfile || {};
        const fields = Array.isArray(raw.fields) && raw.fields.length ? raw.fields : [
            {key:'interests', label:'Interests', placeholder:'What does the student enjoy?'},
            {key:'experience', label:'Experience', placeholder:'Beginner, some experience, advanced'},
            {key:'goals', label:'Goals', placeholder:'Confidence, skills, exam prep, fun'}
        ];
        return {
            title: raw.title || 'Student Preferences',
            fields: fields
                .filter(f => f && f.key && f.label)
                .map(f => ({
                    key: String(f.key).trim(),
                    label: String(f.label).trim(),
                    placeholder: String(f.placeholder || '').trim()
                }))
        };
    };

    const preferenceValue = (source, key) => {
        const prefs = source?.preferences && typeof source.preferences === 'object' ? source.preferences : {};
        return prefs[key] ?? source?.[key] ?? '';
    };

    const collectPreferences = (fd) => {
        const prefs = {};
        preferenceProfile().fields.forEach(field => {
            prefs[field.key] = (fd.get(`pref_${field.key}`) || '').trim();
        });
        return prefs;
    };

    const legacyPreferenceKeys = ['artStyle', 'favArtist', 'experience', 'goals'];
    const legacyPreferenceValues = (prefs, fd=null, source=null) => {
        const out = {};
        legacyPreferenceKeys.forEach(key => {
            out[key] = (prefs[key] || (fd ? fd.get(key) : '') || source?.[key] || '').trim();
        });
        return out;
    };

    const preferenceRows = (source) => {
        const prefs = source?.preferences && typeof source.preferences === 'object' ? source.preferences : {};
        return preferenceProfile().fields
            .map(field => ({...field, value: prefs[field.key] ?? source?.[field.key] ?? ''}))
            .filter(row => row.value);
    };

    /* HTTP-safe clipboard helper — falls back to execCommand when not in secure context */
    const copyText = (str, successMsg) => {
        const onOk   = () => showToast(successMsg || '已复制');
        const onFail = () => showToast('复制失败，请手动复制', 'error');
        const doFallback = () => {
            try {
                const ta = document.createElement('textarea');
                ta.value = str;
                ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0;pointer-events:none;';
                document.body.appendChild(ta);
                ta.focus(); ta.select();
                const copied = document.execCommand('copy');
                document.body.removeChild(ta);
                copied ? onOk() : onFail();
            } catch(e) { onFail(); }
        };
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(str).then(onOk).catch(doFallback);
        } else {
            doFallback();
        }
    };

    /* Fix #8: confirm helper replacing window.confirm */
    const confirm = (message, onConfirm, opts={}) =>
        setConfirmDialog({message, onConfirm, ...opts});

    const loadTeam = async () => {
        if (!TENANT_SLUG) return;
        try {
            const data = await v1Api('/team');
            setTeam(data.team || []);
        } catch (e) {
            setTeam([]);
            showToast(`团队成员加载失败：${e.message}`, 'error');
        }
    };

    const createTeamMember = async () => {
        if (teamBusy) return;
        if (!teamForm.fullName.trim() || !teamForm.email.trim() || teamForm.temporaryPassword.length < 8) {
            showToast('请填写姓名、邮箱和至少8位临时密码', 'warn'); return;
        }
        setTeamBusy(true);
        try {
            await v1Api('/team', {method:'POST', body:JSON.stringify(teamForm)});
            setTeamForm({fullName:'',email:'',role:'teacher',temporaryPassword:''});
            await loadTeam();
            showToast('团队成员已添加，请通过安全渠道发送临时密码');
        } catch (e) { showToast(`添加失败：${e.message}`, 'error'); }
        finally { setTeamBusy(false); }
    };

    const updateTeamMember = async (member, status) => {
        if (teamBusy || member.role === 'owner') return;
        setTeamBusy(true);
        try {
            await v1Api(`/team/${member.id}`, {method:'PATCH', body:JSON.stringify({role:member.role,status})});
            await loadTeam();
            showToast(status === 'active' ? '成员已启用' : '成员已停用');
        } catch (e) { showToast(`更新失败：${e.message}`, 'error'); }
        finally { setTeamBusy(false); }
    };

    /* G1: keyboard shortcut Cmd/Ctrl+K — must be before any early returns (Rules of Hooks) */
    useEffect(() => {
        const h = e => { if ((e.metaKey||e.ctrlKey) && e.key==='k') { e.preventDefault(); setGOpen(o=>!o); setGQ(''); } };
        window.addEventListener('keydown', h);
        return () => window.removeEventListener('keydown', h);
    }, []);

    /* M8+M9: Lightbox keyboard nav (← →) and Escape for all portfolio modals */
    useEffect(() => {
        const onKey = e => {
            if (portLB) {
                if (e.key === 'ArrowRight') setPortLB(p => p && p.idx < p.items.length-1 ? {...p, idx:p.idx+1} : p);
                if (e.key === 'ArrowLeft')  setPortLB(p => p && p.idx > 0               ? {...p, idx:p.idx-1} : p);
                if (e.key === 'Escape')     setPortLB(null);
            } else if (portEdit && e.key === 'Escape')   setPortEdit(null);
            else if (portUpload && e.key === 'Escape') {
                if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
                setPortUpload(false); setPortUpFile(null);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [portLB, portEdit, portUpload, portUpFile]);

    /* B3: 选中学员时拉取上课记录（tenant 模式） */
    useEffect(() => {
        setAttHistory(null);
        if (!TENANT_SLUG || !selS?.id) return;
        let alive = true;
        v1Api(`/attendance?studentId=${encodeURIComponent(selS.id)}&limit=20`)
            .then(d => { if (alive) setAttHistory(d.attendance || []); })
            .catch(() => { if (alive) setAttHistory([]); });
        return () => { alive = false; };
    }, [selS?.id]);

    /* ── Auth: check session on mount and immediately after login ── */
    const refreshSession = () => fetch('/v1/auth/me', {credentials: 'include'})
            .then(r => r.json())
            .then(d => {
                const memberships = d.memberships || [];
                const platformMembership = memberships.find(m => !m.tenant_slug && ['platform_super_admin','super_admin'].includes(m.role));
                const tenantMembership = memberships.find(m => m.tenant_slug === tenantSlug);
                const effectiveRole = platformMembership?.role || tenantMembership?.role || '';
                if (d.ok && ['owner','manager','teacher','front_desk','staff','platform_super_admin','super_admin'].includes(effectiveRole)) {
                    setActorRole(effectiveRole);
                    setLoggedIn(true);
                }
            })
            .catch(() => {});
    useEffect(() => { refreshSession(); }, []);

    /* ── Network (S2: session-cookie auth only — master token never reaches the browser) ── */
    const apiHeaders = () => ({'Content-Type':'application/json'});
    /* D2: latest known DB revision, tracked synchronously in a ref so rapid
       consecutive saves never send a stale rev (React state updates lag). */
    const revRef = useRef(0);

    /* P2 fix: when PIN is disabled, pinOK stays false — check pinEnabled too */
    useEffect(() => { if (loggedIn && (!pinEnabled || pinOK)) load(); }, [loggedIn, pinOK, pinEnabled]);

    /* ── B3 fix: heartbeat — detect server restart, auto-reload on reconnect ── */
    useEffect(() => {
        if (!loggedIn || (pinEnabled && !pinOK)) return;
        const id = setInterval(async () => {
            try {
                const r = await fetch('/api/ping');
                if (r.ok) {
                    if (wasDownRef.current) {
                        wasDownRef.current = false;
                        load();                          // re-fetch data after reconnect
                        showToast('已重新连接，数据已刷新');
                    }
                } else {
                    wasDownRef.current = true;
                    setConn(false);
                }
            } catch {
                wasDownRef.current = true;
                setConn(false);
            }
        }, 30000); // every 30 seconds
        return () => clearInterval(id);
    }, [loggedIn, pinOK, pinEnabled]);
    const doLogout = async () => {
        await fetch('/v1/auth/logout', {method:'POST', credentials:'include'}).catch(()=>{});
        clearSess();   // reset PIN session so next login re-prompts PIN
        setPinOK(false);
        setLoggedIn(false);
        setConn(false);
        setDb({students:[],logs:[],rosters:{},pending:[]});
        setShowSettings(false);
    };

    const changeWebPw = async () => {
        if (!pwOld || !pwNew1) { setPwMsg('请填写旧密码和新密码'); return; }
        if (pwNew1 !== pwNew2)  { setPwMsg('两次新密码不一致'); return; }
        if (pwNew1.length < 8)  { setPwMsg('新密码至少 8 位'); return; }   /* S3 */
        setPwBusy(true); setPwMsg('');
        try {
            const r = await fetch('/v1/auth/change-password', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({oldPassword: pwOld, newPassword: pwNew1}),
                credentials: 'include'
            });
            const d = await r.json();
            if (d.ok) { setPwOld(''); setPwNew1(''); setPwNew2(''); setPwMsg('✅ 密码已更新'); }
            else       { setPwMsg(`❌ ${d.message||d.error||'修改失败'}`); }
        } catch { setPwMsg('❌ 连接失败'); }
        finally { setPwBusy(false); }
    };

    const load = async () => {
        setBusy(true); setConnErr(null);
        try {
            /* S2: session cookie is the auth — no token round-trip needed */
            const r = await fetch('/api/data', {credentials:'include'});
            if (r.status === 401) { setLoggedIn(false); setBusy(false); return; }
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            const d = await r.json();
            if (!d.rosters) d.rosters = {};
            // Migrate: add missing fields (defaults first, then spread so existing values win)
            d.students = d.students.map(s => ({
                email:'', wechat:'', archived:false,
                firstName: s.name||'',
                lastName: '',
                photo:'', artStyle:'', favArtist:'', experience:'', goals:'', preferences:{}, birthday:'',
                ...s
            }));
            if (!d.pending)  d.pending  = [];
            if (!d.packages) d.packages = [{id:1, name:'标准课包', credits:10, price:1200}];
            revRef.current = d.rev || 1;   /* D2 */
            setDb(d); setConn(true);
            loadSchedules();   /* A1: 课表与数据并行加载，失败不阻塞 */
        } catch(e) { setConnErr(e.message); }
        finally { setBusy(false); }
    };
    const save = async (nd, force=false) => {
        setDb(nd);
        try {
            /* D2: always send the freshest rev from the ref (not the possibly
               stale copy inside nd) so back-to-back saves don't self-conflict */
            const body = {...nd, rev: revRef.current, ...(force ? {force:true} : {})};
            const r = await fetch('/api/save', {method:'POST', headers:apiHeaders(),
                                                credentials:'include', body:JSON.stringify(body)});
            if (r.status === 401) { showToast('登录已过期，请重新登录 / Session expired', 'error'); setTimeout(doLogout, 1500); return; }
            if (r.status === 403) { showToast('无权保存此租户数据 / No permission for this tenant.', 'error'); return; }
            if (r.status === 409) {
                const d = await r.json().catch(()=>({}));
                if (d.status === 'conflict') {
                    /* D2: another tab/device saved first — reload, do NOT overwrite */
                    showToast('数据已在其他设备/标签页被修改，正在刷新…', 'error');
                    setTimeout(load, 800);
                } else if (d.status === 'shrink_guard') {
                    /* D1/D1b: server blocked a save that drops a large chunk of data */
                    confirm(`⚠️ 安全拦截：${d.message || `数据量将从 ${d.current} 减少到 ${d.incoming}`} `+
                            `如果这不是你刻意删除的结果，请选择取消并刷新页面！`,
                            async () => { await save(nd, true); },
                            {danger:true, confirmText:'我确认，继续保存'});
                }
                return;
            }
            if (!r.ok) throw new Error('save failed');
            const d = await r.json().catch(()=>null);
            /* D2: adopt the server's new revision so the next save passes the lock */
            if (d && d.rev) { revRef.current = d.rev; setDb(prev => ({...prev, rev: d.rev})); }
        } catch(err) { if (!String(err).includes('401')) showToast('数据未能同步到服务器！', 'error'); }
    };
    const exportDB = () => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([JSON.stringify(db,null,2)], {type:'application/json'}));
        a.download = `Studio_${todayISO()}.json`; a.click();
    };

    /* ── F1: Activity tags (last 30 days check-in count per student) ── */
    const activityMap = useMemo(() => {
        const map = {};
        const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
        db.logs.forEach(l => {
            if (l.action !== '上课签到') return;
            const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
            if (m) {
                const d = new Date(`${m[3]}-${m[2]}-${m[1]}`);
                if (!isNaN(d) && d.getTime() >= cutoff)
                    map[l.studentName] = (map[l.studentName]||0) + 1;
            }
        });
        return map;
    }, [db.logs]);
    const getTag = (s) => {
        const cnt = activityMap[s.name] || 0;
        if (cnt >= 4) return {icon:'🔥', label:'活跃', cls:'bg-red-100 text-red-700'};
        if (cnt >= 1) return {icon:'💤', label:'低频', cls:'bg-gray-100 text-gray-500'};
        if ((parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays)
            return {icon:'⚠️', label:'流失风险', cls:'bg-orange-100 text-orange-600'};
        return null;
    };

    /* G1: 未来 14 天内生日的学员（只比月-日，忽略年份） */
    const upcomingBirthdays = useMemo(() => {
        const now = new Date(); const out = [];
        db.students.forEach(s => {
            if (s.archived) return;
            const m = String(s.birthday||'').match(/^(\d{4})-(\d{2})-(\d{2})$/);
            if (!m) return;
            for (let i=0;i<14;i++) {
                const d = new Date(now.getFullYear(), now.getMonth(), now.getDate()+i);
                if (d.getMonth()+1===parseInt(m[2],10) && d.getDate()===parseInt(m[3],10)) {
                    const age = d.getFullYear() - parseInt(m[1],10);
                    out.push({s, in:i, md:`${m[3]}/${m[2]}`, age}); break;
                }
            }
        });
        return out.sort((a,b)=>a.in-b.in);
    }, [db.students]);

    /* ── Sorted / filtered lists ── */
    const sortedFiltered = useMemo(() => {
        let list = [...db.students];
        if (filterBy === 'archived') {
            list = list.filter(s => s.archived);
        } else {
            if (!filterBy || filterBy === 'all') list = list.filter(s => !s.archived);
            if (filterBy === 'active') list = list.filter(s => !s.archived && (parseInt(s.balance,10)||0)>0);
            if (filterBy === 'low')    list = list.filter(s => !s.archived && (parseInt(s.balance,10)||0)>0 && (parseInt(s.balance,10)||0)<=renewTh);   /* F5 */
            if (filterBy === 'zero')   list = list.filter(s => !s.archived && (parseInt(s.balance,10)||0)===0);
            // F1: activity tag filters
            if (filterBy === 'tag-hot')  list = list.filter(s => !s.archived && (activityMap[s.name]||0) >= 4);
            if (filterBy === 'tag-low')  list = list.filter(s => !s.archived && (activityMap[s.name]||0) >= 1 && (activityMap[s.name]||0) < 4);
            if (filterBy === 'tag-risk') list = list.filter(s => !s.archived && (parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.name]||0) === 0);
        }
        if (srch) {
            const q = srch.toLowerCase();
            list = list.filter(s =>
                s.name.toLowerCase().includes(q) ||
                (s.firstName||'').toLowerCase().includes(q) ||
                (s.lastName||'').toLowerCase().includes(q) ||
                (s.mobile||'').includes(srch) ||
                (s.email||'').toLowerCase().includes(q) ||
                (s.wechat||'').toLowerCase().includes(q)
            );
        }
        const cmp = (a,b,dir=1) => {
            const an=a||'', bn=b||'';
            return dir * an.localeCompare(bn,'zh-CN');
        };
        if (sortBy==='name-az')   list.sort((a,b) => cmp(a.name, b.name));
        if (sortBy==='name-za')   list.sort((a,b) => cmp(b.name, a.name));
        if (sortBy==='last-az')   list.sort((a,b) => {
            const r=cmp(a.lastName,b.lastName); return r!==0?r:cmp(a.firstName,b.firstName);
        });
        if (sortBy==='last-za')   list.sort((a,b) => {
            const r=cmp(b.lastName,a.lastName); return r!==0?r:cmp(b.firstName,a.firstName);
        });
        if (sortBy==='bal-desc')  list.sort((a,b) => (parseInt(b.balance,10)||0) - (parseInt(a.balance,10)||0));
        if (sortBy==='bal-asc')   list.sort((a,b) => (parseInt(a.balance,10)||0) - (parseInt(b.balance,10)||0));
        if (sortBy==='date-desc') list.sort((a,b) => (b.lastActive||'').localeCompare(a.lastActive||''));
        return list;
    }, [db.students, srch, sortBy, filterBy, activityMap, inactiveDays, renewTh]);

    const sortedAZ = useMemo(() =>
        [...db.students].filter(s => !s.archived).sort((a,b) => a.name.localeCompare(b.name,'zh-CN')),
    [db.students]);

    /* A1: 当日应到 = 命中当天 weekday 的课表学员 ∪ 手动排班 */
    const scheduledForDate = useMemo(() => {
        if (!TENANT_SLUG || !schedules.length) return [];
        const wd = new Date(`${rDate}T12:00:00`).getDay();
        return schedules.filter(sc => sc.weekday === wd);
    }, [schedules, rDate]);
    const scheduledIdSet = useMemo(() =>
        new Set(scheduledForDate.flatMap(sc => sc.students.map(st => st.id))),
    [scheduledForDate]);
    const dayIds = useMemo(() => {
        const manual = db.rosters[rDate] || [];
        return [...new Set([...scheduledIdSet, ...manual])];
    }, [db.rosters, rDate, scheduledIdSet]);
    const todayEffectiveCount = useMemo(() => {
        const manual = db.rosters[todayISO()] || [];
        const wd = new Date().getDay();
        const sched = schedules.filter(sc => sc.weekday === wd).flatMap(sc => sc.students.map(st => st.id));
        return new Set([...sched, ...manual]).size;
    }, [db.rosters, schedules]);

    const availRoster = useMemo(() =>
        sortedAZ.filter(s => !dayIds.includes(s.id)),
    [sortedAZ, dayIds]);

    /* ── Analytics ── */
    const analytics = useMemo(() => {
        const totalStudents = db.students.filter(s => !s.archived).length;
        const totalBalance  = db.students.reduce((a,b) => a+(parseInt(b.balance,10)||0), 0);
        const totalCheckins = db.logs.filter(l => l.action==='上课签到').length;
        const totalRevenue  = db.logs.reduce((s,l) => s+(parseFloat(l.feePaid)||0), 0);
        const lowBalance    = [...db.students].filter(s => !s.archived && (parseInt(s.balance,10)||0)<=2)
                             .sort((a,b) => (parseInt(a.balance,10)||0)-(parseInt(b.balance,10)||0));
        const inactive      = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0)>0 && daysSince(s.lastActive)>inactiveDays)
                             .sort((a,b) => daysSince(b.lastActive)-daysSince(a.lastActive));
        const todayRoster   = db.rosters[todayISO()]||[];

        const allMonths={}, allYears={};
        db.logs.forEach(l => {
            const mk=parseMonthKey(l.date); if (!mk) return;
            const yk=mk.split('-')[0];
            if (!allMonths[mk]) allMonths[mk]={revenue:0,checkins:0,topups:0};
            if (!allYears[yk])  allYears[yk] ={revenue:0,checkins:0};
            if (l.action==='上课签到') { allMonths[mk].checkins++; allYears[yk].checkins++; }
            if (l.feePaid) { allMonths[mk].revenue+=parseFloat(l.feePaid); allYears[yk].revenue+=parseFloat(l.feePaid); }
            if (l.action==='充值购课') allMonths[mk].topups++;
        });
        const monthlyReports = Object.keys(allMonths).sort().reverse().map(k=>({key:k,...allMonths[k]}));
        const yearlyReports  = Object.keys(allYears).sort().reverse().map(k=>({key:k,...allYears[k]}));
        const availYears     = Object.keys(allYears).sort().reverse();

        const now = new Date();
        const chart12 = Array.from({length:12}, (_,i) => {
            const d  = new Date(now.getFullYear(), now.getMonth()-11+i, 1);
            const k  = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
            const mo = allMonths[k]||{revenue:0,checkins:0};
            const lbl= `${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getFullYear()).slice(2)}`;
            return {k, l:lbl, rev:Math.round(mo.revenue), ci:mo.checkins};
        });

        /* Fix #11: group recent logs by display date */
        const recentGroups = [];
        let curDateKey = null;
        for (const log of db.logs.slice(0, 30)) {
            const dk = String(log.date).split(',')[0];
            if (dk !== curDateKey) {
                curDateKey = dk;
                if (recentGroups.length >= 3) break;
                recentGroups.push({date:dk, logs:[]});
            }
            if (recentGroups.length && recentGroups[recentGroups.length-1].logs.length < 5)
                recentGroups[recentGroups.length-1].logs.push(log);
        }

        return {totalStudents,totalBalance,totalCheckins,totalRevenue,lowBalance,inactive,todayRoster,monthlyReports,yearlyReports,availYears,chart12,recentGroups};
    }, [db, inactiveDays]);

    /* ── Stats filtered ── */
    const statsData = useMemo(() => {
        let logs = sStu ? db.logs.filter(l => { const s=db.students.find(x=>x.id===sStu); return s && (l.studentId===s.id || (!l.studentId && l.studentName===s.name)); }) : db.logs;   /* D3 */
        if (sPeriod==='custom') {
            // F3: auto-swap if user set sFrom > sTo so data always shows correctly
            const from = (sFrom && sTo && sFrom > sTo) ? sTo   : sFrom;
            const to   = (sFrom && sTo && sFrom > sTo) ? sFrom : sTo;
            // Fix ⑩: sFrom/sTo are now YYYY-MM month strings, compare month keys directly
            logs = logs.filter(l => { const mk=parseMonthKey(l.date); if(!mk) return false; return (!from||mk>=from)&&(!to||mk<=to); });
        } else if (sPeriod==='monthly' && sYear!=='all') {
            logs = logs.filter(l => { const mk=parseMonthKey(l.date); return mk&&mk.startsWith(sYear); });
        }
        const byP = {};
        logs.forEach(l => {
            const mk=parseMonthKey(l.date); if(!mk) return;
            const key = sPeriod==='yearly' ? mk.split('-')[0] : mk;
            if (!byP[key]) byP[key]={revenue:0,checkins:0,topups:0};
            if (l.action==='上课签到') byP[key].checkins++;
            if (l.action==='充值购课'){byP[key].topups++;}
            if (l.feePaid) byP[key].revenue+=parseFloat(l.feePaid);
        });
        const rows = Object.keys(byP).sort().reverse().map(k=>({key:k,...byP[k]}));
        return {rows, totalRev:rows.reduce((s,r)=>s+r.revenue,0), totalCI:rows.reduce((s,r)=>s+r.checkins,0)};
    }, [db, sPeriod, sYear, sFrom, sTo, sStu]);

    const studentStats = useMemo(() => {
        if (!sStu2) return null;
        const s = db.students.find(x=>x.id===sStu2); if (!s) return null;
        const logs = db.logs.filter(l=>l.studentId===s.id || (!l.studentId && l.studentName===s.name));   /* D3 */
        const totalSpent  = logs.reduce((sum,l)=>sum+(parseFloat(l.feePaid)||0),0);
        const checkins    = logs.filter(l=>l.action==='上课签到').length;
        const topups      = logs.filter(l=>l.action==='充值购课');
        const totalBought = topups.reduce((sum,l)=>{const c=String(l.change).replace('+','');return sum+(parseInt(c)||0);},0);
        return {student:s,totalSpent,checkins,totalBought,topupCount:topups.length,
                first:logs.length?logs[logs.length-1].date:'',
                last:logs.length?logs[0].date:'',logs};
    }, [db, sStu2]);

    /* ── G1: Global search results ── */
    const gResults = useMemo(() => {
        if (!gQ.trim()) return [];
        const q = gQ.trim().toLowerCase();
        return db.students.filter(s => !s.archived && (
            s.name.toLowerCase().includes(q) ||
            (s.firstName||'').toLowerCase().includes(q) ||
            (s.lastName||'').toLowerCase().includes(q) ||
            (s.mobile||'').includes(q) ||
            (s.wechat||'').toLowerCase().includes(q)
        )).slice(0, 10);
    }, [db.students, gQ]);

    /* Parse DD/MM/YYYY log date → YYYY-MM-DD for range comparison */
    const logDateISO = (ds) => {
        const m = String(ds).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        return m ? `${m[3]}-${m[2]}-${m[1]}` : '';
    };
    /* Fix #10: log page auto-clamp when data changes */
    const filteredLogs  = useMemo(() => {
        const stuName = lStu ? (db.students.find(x=>x.id===lStu)||{}).name : null;
        return db.logs.filter(l => {
            if (stuName && l.studentName !== stuName) return false;
            if (lSrch && !l.studentName.toLowerCase().includes(lSrch.toLowerCase())) return false;
            if (lAct  && l.action !== lAct) return false;
            if (lDateFrom || lDateTo) {
                const iso = logDateISO(l.date);
                if (lDateFrom && iso < lDateFrom) return false;
                if (lDateTo   && iso > lDateTo)   return false;
            }
            return true;
        });
    }, [db.logs, db.students, lStu, lSrch, lAct, lDateFrom, lDateTo]);
    const logPageCount  = Math.max(1, Math.ceil(filteredLogs.length/LPP));
    const pagedLogs     = filteredLogs.slice((lPage-1)*LPP, lPage*LPP);
    const logActions    = useMemo(() => [...new Set(db.logs.map(l=>l.action))].sort(), [db.logs]);
    useEffect(() => { setLPage(1); }, [lStu, lSrch, lAct, lDateFrom, lDateTo]);
    useEffect(() => { if (lPage > logPageCount) setLPage(logPageCount); }, [logPageCount]);

    /* F7: 经营月报 — 新增学员/课包销量/消课节奏（纯前端计算，零后端） */
    const bizReport = useMemo(() => {
        const now = new Date();
        const months = Array.from({length:6}, (_,i) => {
            const d = new Date(now.getFullYear(), now.getMonth()-5+i, 1);
            return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`;
        });
        const rows = months.map(k => ({k, label:`${k.split('-')[1]}/${k.split('-')[0].slice(2)}`,
                                       rev:0, ci:0, topups:0, newStu:0}));
        const byKey = Object.fromEntries(rows.map(r=>[r.k, r]));
        const pkgSales = {};
        db.logs.forEach(l => {
            const mk = parseMonthKey(l.date);
            const r  = mk && byKey[mk];
            if (r) {
                if (l.action==='上课签到') r.ci++;
                if (l.action==='充值购课') { r.topups++; r.rev += parseFloat(l.feePaid)||0; }
                if (l.action==='新生注册'||l.action==='批准注册') r.newStu++;
            }
            if (l.action==='充值购课') {
                const m = String(l.note||'').match(/套餐:\s*([^|]+)/);
                const name = m ? m[1].trim() : '自定义';
                if (!pkgSales[name]) pkgSales[name] = {count:0, revenue:0};
                pkgSales[name].count++; pkgSales[name].revenue += parseFloat(l.feePaid)||0;
            }
        });
        // 平均消课节奏：近180天有≥2次签到的学员，平均隔几天上一次课
        const cutoff = Date.now() - 180*24*3600*1000;
        const perStu = {};
        db.logs.forEach(l => {
            if (l.action!=='上课签到') return;
            const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
            if (!m) return;
            const t = new Date(`${m[3]}-${m[2]}-${m[1]}`).getTime();
            if (t < cutoff) return;
            const key = l.studentId || l.studentName;
            (perStu[key] = perStu[key]||[]).push(t);
        });
        let gaps = [];
        Object.values(perStu).forEach(ts => {
            if (ts.length < 2) return;
            ts.sort((a,b)=>a-b);
            for (let i=1;i<ts.length;i++) gaps.push((ts[i]-ts[i-1])/86400000);
        });
        const avgGap = gaps.length ? (gaps.reduce((a,b)=>a+b,0)/gaps.length) : 0;
        const pkgRank = Object.entries(pkgSales).sort((a,b)=>b[1].revenue-a[1].revenue);
        return {rows, pkgRank, avgGap, regularStu: Object.values(perStu).filter(t=>t.length>=2).length};
    }, [db.logs]);

    const exportBizCSV = () => {
        const head = ['月份','营收(AUD)','充值笔数','消课次数','新增学员'];
        const lines = bizReport.rows.map(r=>[r.label, r.rev.toFixed(0), r.topups, r.ci, r.newStu]);
        const pkg = bizReport.pkgRank.map(([n,d])=>['课包:'+n, d.revenue.toFixed(0), d.count, '', '']);
        const csv = [head, ...lines, [], ['课包销量排行','营收','笔数'], ...pkg]
            .map(r=>r.join(',')).join('\n');
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob(['﻿'+csv], {type:'text/csv;charset=utf-8'}));
        a.download = `Studio_经营月报_${todayISO()}.csv`; a.click();
    };

    const payBreakdown = useMemo(() => {
        const map={};
        db.logs.filter(l=>l.action==='充值购课').forEach(l => {
            const pm=l.payMethod||'未记录'; if(!map[pm]) map[pm]={count:0,revenue:0};
            map[pm].count++; map[pm].revenue+=parseFloat(l.feePaid)||0;
        });
        return Object.entries(map).sort((a,b)=>b[1].revenue-a[1].revenue);
    }, [db.logs]);

    /* ── Core actions ── */
    /* D3: logs now carry studentId so renaming a student keeps their history.
       Resolved by exact name match only when unambiguous (duplicate names →
       omitted; the server then falls back to name matching). */
    const mkLog = (sName,action,change,note,fee=0,extra={}) => {
        const matches = db.students.filter(x=>x.name===sName);
        const sidObj  = matches.length===1 ? {studentId: matches[0].id} : {};
        return {id:Date.now(), date:nowAU(), studentName:sName, ...sidObj, action, change, note, feePaid:fee, ...extra};
    };

    const checkIn = async (sid, sname) => {
        if (cooldowns.current.has(sid)) { showToast('请稍候再次操作', 'warn'); return; }
        if (busy) return;
        const student = db.students.find(s=>s.id===sid);
        if (!student||student.balance<=0) { showToast(`${sname} 课时余额不足`, 'error'); return; }
        cooldowns.current.add(sid); setTimeout(() => cooldowns.current.delete(sid), 3000);
        setBusy(true);
        try {
            let nb;
            if (TENANT_SLUG) {
                /* A2: 走 v1 账本 — 生成 attendance_sessions + consume 流水，
                   与 Studio Admin 考勤页同一本账 */
                const res = await v1Api('/attendance/check-in', {
                    method: 'POST',
                    body: JSON.stringify({studentId: sid, note: '常规课程消耗', classDate: rDate}),
                });
                nb = Number(res.newBalance);
                await load();
            } else {
                nb = Math.max(0, student.balance-1);
                const ns = db.students.map(s=>s.id===sid?{...s,balance:nb,lastActive:todayISO()}:s);
                await save({...db, students:ns, logs:[mkLog(sname,'上课签到',-1,'常规课程消耗',0,{studentId:sid}),...db.logs]});
            }
            if (selS?.id===sid) setSelS(p=>({...p,balance:nb}));
            /* G2: 一键复制给家长的签到确认话术 */
            const confirmMsg = nb===0
                ? `${sname} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～ 🎨`
                : `${sname} 今日已完成签到 ✓ 当前剩余 ${nb} 课时。Studio 感谢您的支持！🎨`;
            const act = {label:'📋 复制签到确认（发家长）', onClick:()=>copyText(confirmMsg,'签到确认已复制')};
            if (nb===0) showToast(`${sname} 课时已清零！请提醒续课 🔔`, 'warn', act);
            else        showToast(`${sname} 签到 ✓ 剩余 ${nb} 课时`, 'success', act);
        } catch(e) { showToast(`签到失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const undoCheckIn = (sid, sname) => {
        confirm(`撤销 ${sname} 的最近一次签到记录，并恢复 1 课时。`, async () => {
            if (busy) return; // Fix ④: guard against concurrent busy
            setBusy(true);
            try {
                if (TENANT_SLUG) {
                    /* A2: 通过 v1 作废考勤（refund 流水 + 考勤标记 reversed），
                       日志由服务端按撤销语义隐藏对应签到记录 */
                    const entry = db.logs.find(l=>l.studentId===sid&&l.action==='上课签到'&&l.attendanceId);
                    if (!entry) { showToast('未找到签到记录','warn'); return; }
                    await v1Api(`/attendance/${entry.attendanceId}/void`, {
                        method: 'POST',
                        body: JSON.stringify({note: '管理员撤销'}),
                    });
                    await load();
                } else {
                    const idx = db.logs.findIndex(l=>(l.studentId===sid || (!l.studentId && l.studentName===sname))&&l.action==='上课签到');   /* D3 */
                    if (idx===-1) { showToast('未找到签到记录','warn'); return; }
                    const ns = db.students.map(s=>s.id===sid?{...s,balance:(parseInt(s.balance,10)||0)+1}:s);
                    const nl = db.logs.filter((_,i)=>i!==idx);
                    await save({...db, students:ns, logs:[mkLog(sname,'撤销签到','+1','管理员撤销',0,{studentId:sid}),...nl]});
                }
                if (selS?.id===sid) setSelS(p=>({...p,balance:(parseInt(p.balance,10)||0)+1}));
                showToast(`已撤销 ${sname} 签到`, 'warn');
            } catch(e) { showToast(`撤销失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        }, {confirmText:'确认撤销'});
    };

    /* F4a: ids already checked in on the roster date — the batch action must
       skip them, otherwise tapping a few students then hitting 批量签到/消课
       deducts those students TWICE. */
    const rosterDone = useMemo(() => {
        const m = String(rDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
        const prefix = m ? `${m[3]}/${m[2]}/${m[1]}` : '__none__';
        const done = new Set();
        db.logs.forEach(l => {
            if (l.action === '上课签到' && String(l.date).startsWith(prefix)) {
                if (l.studentId) done.add(l.studentId);
                else { const s = db.students.find(x => x.name === l.studentName); if (s) done.add(s.id); }
            }
        });
        return done;
    }, [db.logs, db.students, rDate]);

    /* ── A1: 每周课表 ────────────────────────────────────────── */
    const WEEKDAYS = ['周日','周一','周二','周三','周四','周五','周六'];

    const loadSchedules = async () => {
        if (!TENANT_SLUG) return;
        try {
            const d = await v1Api('/class-schedules');
            setSchedules(d.schedules || []);
        } catch (e) { /* 课表加载失败不阻塞其余功能 */ }
        try {
            const dash = await v1Api('/dashboard');
            setBizStats((dash.dashboard || {}).business || null);
        } catch (e) { /* 经营真账加载失败不阻塞 */ }
    };

    /* B2: 判断两个班次在同一 weekday 是否时间重叠 */
    const schedOverlap = (a, b) => {
        if (Number(a.weekday) !== Number(b.weekday)) return false;
        const toMin = (t) => { const [h,m] = String(t).split(':').map(Number); return h*60+(m||0); };
        const aS = toMin(a.startTime), aE = aS + (Number(a.durationMinutes)||60);
        const bS = toMin(b.startTime), bE = bS + (Number(b.durationMinutes)||60);
        return aS < bE && bS < aE;
    };

    const saveSchedule = async (conflictConfirmed=false) => {
        if (!schedEdit || busy) return;
        if (!schedEdit.label.trim()) { showToast('请输入班次名称（如：周三素描班）', 'error'); return; }
        /* B2-①: 与其他班次时间重叠时给确认提示（v5.2） */
        const clash = schedules.find(sc => sc.id !== schedEdit.id && schedOverlap(sc, schedEdit));
        if (clash && !conflictConfirmed) {
            confirm(
                `「${schedEdit.label.trim()}」与「${clash.label}」（${WEEKDAYS[clash.weekday]} ${clash.startTime}）时段重叠，仍要保存吗？`,
                () => saveSchedule(true),
                {confirmText:'仍然保存'}
            );
            return;
        }
        setBusy(true);
        try {
            const body = JSON.stringify({
                label: schedEdit.label.trim(),
                weekday: Number(schedEdit.weekday),
                startTime: schedEdit.startTime,
                durationMinutes: Number(schedEdit.durationMinutes) || 60,
                capacity: Number(schedEdit.capacity) || 10,
                studentIds: schedEdit.studentIds,
            });
            const d = schedEdit.id
                ? await v1Api(`/class-schedules/${schedEdit.id}`, {method: 'PATCH', body})
                : await v1Api('/class-schedules', {method: 'POST', body});
            setSchedules(d.schedules || []);
            setSchedEdit(null);
            showToast('每周课表已保存');
        } catch (e) { showToast(`课表保存失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const deleteSchedule = (sc) => {
        confirm(`删除班次「${sc.label}」？（不影响任何学员和签到记录）`, async () => {
            if (busy) return;
            setBusy(true);
            try {
                const d = await v1Api(`/class-schedules/${sc.id}`, {method: 'DELETE'});
                setSchedules(d.schedules || []);
                if (schedEdit && schedEdit.id === sc.id) setSchedEdit(null);
                showToast(`班次「${sc.label}」已删除`, 'warn');
            } catch (e) { showToast(`删除失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger: true, confirmText: '确认删除'});
    };

    /* 模板 → 每周班次：把常用班组一键升级为周期课表 */
    const groupToSchedule = () => {
        const ids = (db.groups || {})[grpSel] || [];
        if (!grpSel || !ids.length) { showToast('请先选择一个班组模板', 'warn'); return; }
        setSchedEdit({label: grpSel, weekday: new Date().getDay(), startTime: '16:00',
                      durationMinutes: 60, capacity: Math.max(10, ids.length), studentIds: ids});
        showToast('已带入模板学员，请确认周几与时间后保存');
    };

    const batchCheckIn = () => {
        const ids     = dayIds;
        const already = ids.filter(id => rosterDone.has(id)).length;
        const elig    = ids.filter(id => { const s=db.students.find(x=>x.id===id); return s&&!s.archived&&s.balance>0&&!rosterDone.has(id); });
        if (!elig.length) { showToast(already ? '今日排班学员均已签到 ✓' : '今日无可签到/消课学员', 'warn'); return; }
        const skipNote = already ? `，${already} 人已单独签到将跳过` : '';
        confirm(`确认对今日 ${elig.length} 名学员执行批量签到/消课？（余额为 0、已归档${skipNote}）`, async () => {
            if (busy) return; // Fix ④
            setBusy(true);
            try {
                if (TENANT_SLUG) {
                    /* A2: 逐个走 v1 账本，失败的学员单独提示不影响其他人 */
                    const failed = [];
                    for (const id of elig) {
                        const s = db.students.find(x=>x.id===id); if (!s) continue;
                        try {
                            await v1Api('/attendance/check-in', {
                                method: 'POST',
                                body: JSON.stringify({studentId: id, note: '批量签到/消课', classDate: rDate}),
                            });
                        } catch(e) { failed.push(s.name); }
                    }
                    await load();
                    if (failed.length) showToast(`批量签到/消课完成，${failed.length} 人失败：${failed.join('、')}`, 'warn');
                    else showToast(`批量签到/消课完成，共 ${elig.length} 人`);
                } else {
                    let cur = {...db};
                    const base = Date.now();
                    // Fix ③: use loop index (not student id) to avoid integer overflow collisions
                    elig.forEach((id, i) => {
                        const s=cur.students.find(x=>x.id===id); if(!s) return;
                        const nb=Math.max(0,s.balance-1);
                        cur = {...cur,
                            students:cur.students.map(x=>x.id===id?{...x,balance:nb,lastActive:todayISO()}:x),
                            logs:[{...mkLog(s.name,'上课签到',-1,'批量签到/消课',0,{studentId:id}),id:base+i},...cur.logs]};
                    });
                    await save(cur);
                    showToast(`批量签到/消课完成，共 ${elig.length} 人`);
                }
            } finally { setBusy(false); }
        }, {confirmText:`签到/消课 ${elig.length} 人`});
    };

    /* F4b: 班组模板 — 保存常用班次组合，任意日期一键套用 */
    const saveGroup = () => {
        const ids = db.rosters[rDate]||[];
        if (!ids.length) { showToast('当前日期没有排班可保存', 'warn'); return; }
        const name = (window.prompt('模板名称（如：周六上午班）')||'').trim();
        if (!name) return;
        save({...db, groups: {...(db.groups||{}), [name]: ids}});
        showToast(`模板「${name}」已保存（${ids.length} 人）`);
    };
    const applyGroup = async () => {
        if (!grpSel) return;
        const ids = (db.groups||{})[grpSel]||[];
        const cur = db.rosters[rDate]||[];
        const add = ids.filter(id => !cur.includes(id) && db.students.some(s=>s.id===id&&!s.archived));
        if (!add.length) { showToast('模板学员均已在当前排班中', 'warn'); return; }
        await save({...db, rosters: {...db.rosters, [rDate]: [...cur, ...add]}});
        showToast(`已套用「${grpSel}」，新增 ${add.length} 人`);
    };
    const deleteGroup = () => {
        if (!grpSel) return;
        confirm(`删除模板「${grpSel}」？（不影响任何排班和学员数据）`, async () => {
            const g = {...(db.groups||{})}; delete g[grpSel];
            await save({...db, groups: g}); setGrpSel('');
            showToast('模板已删除', 'warn');
        }, {danger:true, confirmText:'删除模板'});
    };

    const isStudentScheduledOn = (sid, date) => {
        const manual = (db.rosters[date] || []).includes(sid);
        const wd = new Date(`${date}T12:00:00`).getDay();
        const fixed = schedules.some(sc => Number(sc.weekday) === wd && sc.students.some(st => st.id === sid));
        return manual || fixed;
    };

    const scheduleStudentToday = async (student) => {
        if (!student || student.archived || busy) return;
        const date = todayISO();
        setRDate(date);
        setSelS(null);
        setEditP(false);
        setTab('roster');
        if (isStudentScheduledOn(student.id, date)) {
            showToast(`${student.name} 已在今日排课中`);
            return;
        }
        setBusy(true);
        try {
            const cur = db.rosters[date] || [];
            await save({...db, rosters:{...db.rosters, [date]: [...cur, student.id]}});
            showToast(`${student.name} 已加入今日排课`);
        } finally { setBusy(false); }
    };

    /* G3: 学员成长报告 — 生成图文报告页（新窗口，可保存为 PDF / 截图发家长） */
    const openGrowthReport = (s) => {
        const logs = db.logs.filter(l => l.studentId===s.id || (!l.studentId && l.studentName===s.name));
        const parseD = (d) => { const m=String(d).match(/^(\d{2})\/(\d{2})\/(\d{4})/); return m?new Date(`${m[3]}-${m[2]}-${m[1]}`):null; };
        const checkins = logs.filter(l=>l.action==='上课签到');
        const dates    = logs.map(l=>parseD(l.date)).filter(Boolean).sort((a,b)=>a-b);
        const joinDate = dates.length ? dates[0] : null;
        const days     = joinDate ? Math.max(1, Math.round((Date.now()-joinDate)/86400000)) : 0;
        const bal      = parseInt(s.balance,10)||0;
        const port     = (s.portfolio||[]);
        // 近 6 个月上课分布
        const now = new Date();
        const months = Array.from({length:6},(_,i)=>{ const d=new Date(now.getFullYear(),now.getMonth()-5+i,1);
            return {k:`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`, l:`${d.getMonth()+1}月`, n:0}; });
        const mIdx = Object.fromEntries(months.map((m,i)=>[m.k,i]));
        checkins.forEach(l=>{ const d=parseD(l.date); if(!d)return; const k=`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`; if(k in mIdx) months[mIdx[k]].n++; });
        const maxM = Math.max(1, ...months.map(m=>m.n));
        const esc = (t)=>String(t||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
        const fmtD = (d)=>d?`${String(d.getDate()).padStart(2,'0')}/${String(d.getMonth()+1).padStart(2,'0')}/${d.getFullYear()}`:'—';
        /* C5: 零数据兜底 — 新学员尚无记录时用欢迎语 */
        const isNew = checkins.length === 0;
        const shareMsg = isNew
            ? `欢迎 ${s.name} 加入 Studio！艺术之旅刚刚启程，期待用画笔记录每一份成长与快乐 🎨`
            : `${s.name} 在 Studio 已经学习了 ${days} 天，累计上课 ${checkins.length} 次，完成作品 ${port.length} 幅！每一笔都是成长的印记，期待继续陪伴 TA 用画笔探索世界 🎨`;

        const portHTML = port.length ? port.map(p=>`
            <figure class="art">
                <img src="${portfolioImgSrc(s.id, p)}" alt="作品"/>
                <figcaption>${esc(p.note)||'　'}<span>${esc((p.date||'').split('-').reverse().join('/'))}</span></figcaption>
            </figure>`).join('') : '<p class="empty">暂无作品记录 · 上传作品后报告会更精彩 🎨</p>';

        /* C3: 柱高直接算像素（上限 76px），数字标签固定占位不再被顶出 */
        const barsHTML = months.map(m=>`
            <div class="bar"><span class="bn">${m.n||''}</span><div class="fill" style="height:${Math.max(3,Math.round(m.n/maxM*76))}px"></div><span class="bl">${m.l}</span></div>`).join('');

	        const photoHTML = s.photo ? `<img class="avatar" src="${mediaSrc(s.photo)}" alt=""/>`
	            : `<div class="avatar ph">${esc((s.name||'?').slice(0,1))}</div>`;
	        const reportBrand = window.STUDIOSAAS_BRAND || {};
	        const reportSlogan = reportBrand.slogan || 'Learn, grow, and feel confident.';
	        const reportStudioName = reportBrand.name || 'Studio';
	        const reportJoinText = reportBrand.category === 'art'
	            ? '艺术之旅刚刚启程'
	            : '学习旅程刚刚启程';

	        /* C6+v4.3.2: 暖色美术馆风 — 暖米白展墙 + 金铜强调色，作品做彩色主角 */
        const html = `<!doctype html><html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>${esc(s.name)} · 成长报告 · Studio</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#efeae2;color:#3a3a44;padding:24px}
.sheet{max-width:760px;margin:0 auto;background:#fffdf9;border-radius:18px;overflow:hidden;box-shadow:0 10px 36px rgba(60,50,40,.10)}
.brandbar{display:flex;flex-direction:column;align-items:center;gap:7px;padding:32px 30px 18px}
.brandbar img{height:86px;width:auto}
.slogan{font-family:'Snell Roundhand','Savoye LET','Brush Script MT',cursive;font-size:20px;color:#b08d57}
.hero{display:flex;align-items:center;gap:22px;padding:6px 36px 26px;border-bottom:1px solid #ece6db}
.avatar{width:90px;height:90px;border-radius:50%;object-fit:cover;border:3px solid #e6ddcd;flex-shrink:0}
.avatar.ph{display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:800;background:#f0ece4;color:#6f6f7c}
.hero h1{font-size:28px;color:#2f2c33;margin-bottom:5px}
.hero .sub{color:#8a857d;font-size:14px}
.hero .sub b{color:#b08d57}
.hero .tag{display:inline-block;font-size:11px;letter-spacing:2px;color:#b08d57;text-transform:uppercase;margin-bottom:7px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:24px 36px;background:#faf7f1}
.stat{text-align:center;break-inside:avoid}
.stat .v{font-size:30px;font-weight:800;color:#b08d57;line-height:1}
.stat .l{font-size:12px;color:#9a958c;margin-top:6px}
.sec{padding:24px 36px;border-top:1px solid #ece6db;break-inside:avoid;page-break-inside:avoid}
.sec.gal{break-inside:auto;page-break-inside:auto}
.sec h2{font-size:15px;margin-bottom:16px;color:#4a4751;letter-spacing:.5px;display:flex;align-items:center;gap:7px}
.chart{display:flex;align-items:flex-end;gap:16px;padding-top:4px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
.bn{font-size:12px;font-weight:700;color:#b08d57;height:18px}
.fill{width:58%;background:#c4ad84;border-radius:5px 5px 0 0}
.bl{font-size:11px;color:#a8a299;margin-top:7px}
.gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.art{border-radius:12px;overflow:hidden;background:#f7f4ee;border:1px solid #ece6db;break-inside:avoid;page-break-inside:avoid}
.art img{width:100%;height:150px;object-fit:cover;display:block}
.art figcaption{font-size:12px;color:#5b5750;padding:8px 10px;display:flex;flex-direction:column;gap:2px}
.art figcaption span{font-size:11px;color:#a8a299}
.empty{color:#a8a299;text-align:center;padding:24px;font-size:14px}
.msg{background:#faf6ee;border-left:3px solid #b08d57;border-radius:0 12px 12px 0;padding:18px 22px;font-size:15px;line-height:1.8;color:#4a4751}
.foot{text-align:center;padding:22px;color:#aba89f;font-size:12px}
.foot .fslogan{font-family:'Snell Roundhand','Savoye LET','Brush Script MT',cursive;font-size:16px;color:#b08d57;margin-bottom:4px}
.toolbar{max-width:760px;margin:0 auto 16px;display:flex;gap:10px;justify-content:flex-end}
.toolbar button{border:0;border-radius:12px;padding:11px 18px;font-size:14px;font-weight:700;cursor:pointer}
.b1{background:#6f5b3e;color:#fff}.b2{background:#fffdf9;color:#6f5b3e;border:1px solid #ddd0bb}
@media print{body{background:#fff;padding:0}.toolbar{display:none}.sheet{box-shadow:none;border-radius:0}}
@media(max-width:560px){.stats{grid-template-columns:repeat(2,1fr)}.gallery{grid-template-columns:repeat(2,1fr)}.hero{padding:6px 22px 22px}.sec{padding:20px 22px}}
</style></head><body>
<div class="toolbar">
  <button class="b2" id="copybtn">📋 复制成长寄语</button>
  <button class="b1" onclick="window.print()">🖨 保存为 PDF / 打印</button>
</div>
<div class="sheet">
  <div class="brandbar">
    <img src="/logo.png" alt="Studio"/>
	    <div class="slogan">${esc(reportSlogan)}</div>
  </div>
  <div class="hero">
    ${photoHTML}
    <div>
      <span class="tag">学员成长报告 · Growth Report</span>
      <h1>${esc(s.name)}</h1>
	      <div class="sub">${isNew ? `${esc(reportJoinText)} · 欢迎加入 ${esc(reportStudioName)}` : `已在 ${esc(reportStudioName)} 成长陪伴 <b>${days}</b> 天 · 入学于 ${fmtD(joinDate)}`}</div>
    </div>
  </div>
  <div class="stats">
    <div class="stat"><div class="v">${checkins.length}</div><div class="l">累计上课</div></div>
    <div class="stat"><div class="v">${port.length}</div><div class="l">完成作品</div></div>
    <div class="stat"><div class="v">${bal}</div><div class="l">剩余课时</div></div>
    <div class="stat"><div class="v">${isNew ? '—' : days}</div><div class="l">陪伴天数</div></div>
  </div>
  <div class="sec">
    <h2>📈 近 6 个月上课足迹</h2>
    <div class="chart">${barsHTML}</div>
  </div>
  <div class="sec gal">
    <h2>🖼 作品集（${port.length} 幅）</h2>
    <div class="gallery">${portHTML}</div>
  </div>
  <div class="sec">
    <h2>💛 老师寄语</h2>
    <div class="msg">${esc(shareMsg)}</div>
  </div>
  <div class="foot">
	    <div class="fslogan">${esc(reportSlogan)}</div>
	    报告生成于 ${fmtD(new Date())} · ${esc(reportStudioName)}
  </div>
</div>
<script>
/* C1+C2: 安全嵌入文本（不再用引号嵌套的内联 onclick）+ http 环境降级复制 */
var MSG = ${JSON.stringify(shareMsg)};
document.getElementById('copybtn').addEventListener('click', function(){
  var btn = this;
  var ok = function(){ btn.textContent = '✓ 已复制寄语'; };
  var fallback = function(){
    try {
      var ta = document.createElement('textarea');
      ta.value = MSG; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
      document.body.appendChild(ta); ta.focus(); ta.select();
      var done = document.execCommand('copy');
      document.body.removeChild(ta);
      done ? ok() : (btn.textContent = '复制失败，请长按选择');
    } catch(e) { btn.textContent = '复制失败，请长按选择'; }
  };
  if (navigator.clipboard && window.isSecureContext)
    navigator.clipboard.writeText(MSG).then(ok).catch(fallback);
  else fallback();
});
<\/script>
</body></html>`;
        const w = window.open('', '_blank');
        if (!w) { showToast('请允许弹出窗口以查看报告', 'warn'); return; }
        w.document.write(html); w.document.close();
    };

    const archiveStudent = (sid, sname, archive) => {
        confirm(
            archive ? `将 "${sname}" 移入归档库，不影响历史记录，随时可恢复。` : `将 "${sname}" 从归档库恢复为活跃学员。`,
            async () => {
                if (busy) return; // Fix ④
                setBusy(true);
                try {
                    const ns = db.students.map(s=>s.id===sid?{...s,archived:archive}:s);
                    await save({...db, students:ns, logs:[mkLog(sname,archive?'归档学员':'恢复学员','0',archive?'移入归档库':'从归档库恢复',0,{studentId:sid}),...db.logs]});
                    setSelS(null); setEditP(false);
                    showToast(`${sname} 已${archive?'归档':'恢复'}`, 'warn');
                } finally { setBusy(false); }
            },
            {confirmText: archive?'确认归档':'确认恢复'}
        );
    };

    const handleTopUp = async (e) => {
        e.preventDefault();
        const fd      = new FormData(e.target);
        const credits = parseInt(fd.get('credits'),10);
        const fee     = parseFloat(fd.get('fee'))||0;
        if (!tuStu)                     { showToast('请选择学员','error'); return; }
        if (isNaN(credits)||credits<=0) { showToast('请输入有效课时数','error'); return; }

        const tuRemark = (fd.get('tuRemark')||'').trim();
        const doTopUp = async () => {
            if (busy) return;
            setBusy(true);
            try {
                const s = db.students.find(x=>x.id===tuStu); if (!s) return;
                const noteStr = [`套餐: ${tuPkg||'自定义'}`, `付款: ${tuPay}`, ...(tuRemark?[tuRemark]:[])].join(' | ');
                if (TENANT_SLUG) {
                    /* A2: 充值走 v1 账本（purchase 流水，含实收金额） */
                    await v1Api(`/students/${s.id}/credit-transactions`, {
                        method: 'POST',
                        body: JSON.stringify({
                            transactionType: 'purchase',
                            amount: credits,
                            feeAudCents: Math.round(fee * 100),
                            note: noteStr,
                        }),
                    });
                    await load();
                } else {
                    const ns = db.students.map(x=>x.id===tuStu?{...x,balance:(parseInt(x.balance,10)||0)+credits,lastActive:todayISO()}:x);
                    await save({...db, students:ns, logs:[mkLog(s.name,'充值购课',`+${credits}`,noteStr,fee,{payMethod:tuPay,studentId:s.id}),...db.logs]});
                }
                e.target.reset();
                setTuCr(''); setTuFee(''); setTuPkg('');
                setTuPay('微信'); setTuStu(null);
                /* G2: 充值确认话术 */
                const newBal = (parseInt(s.balance,10)||0)+credits;
                const cMsg = `${s.name} 您好！已为您成功充值 ${credits} 课时${fee?`（实收 $${fee}）`:''}，当前账户共 ${newBal} 课时。感谢您对 Studio 的信任！🎨`;
                showToast(`${s.name} 充值 ${credits} 课时 / $${fee}`, 'success',
                    {label:'📋 复制充值确认（发家长）', onClick:()=>copyText(cMsg,'充值确认已复制')});
            } catch(err) { showToast(`充值失败：${err.message}`, 'error'); }
            finally { setBusy(false); }
        };

        /* A4: 充值一律二次确认，核对学员/课时/金额 */
        const s0 = db.students.find(x=>x.id===tuStu);
        confirm(`确认为 ${s0?s0.name:''} 充值 ${credits} 课时，实收 $${fee}（${tuPay}）${fee===0?'——免费充课':''}？`,
            doTopUp, {confirmText: fee===0?'确认免费充课':'确认入账'});
    };

    /* A2: 退款退课 — 节数 ≤ 余额直接扣减，退款金额以负数计入营收（净额自动） */
    const handleRefund = async (e) => {
        e.preventDefault();
        const credits = parseInt(rfCr, 10);
        const amt = parseFloat(rfAmt) || 0;
        const s = db.students.find(x=>x.id===tuStu);
        if (!s)                          { showToast('请选择学员','error'); return; }
        if (isNaN(credits)||credits<=0)  { showToast('请输入有效退课节数','error'); return; }
        if (credits > (parseInt(s.balance,10)||0)) { showToast(`退课节数不能超过剩余课时（${s.balance}）`,'error'); return; }
        if (amt < 0)                     { showToast('退款金额无效','error'); return; }
        if (!rfReason.trim())            { showToast('请填写退款原因','error'); return; }
        confirm(`确认为 ${s.name} 退课 ${credits} 节、退款 $${amt}（${tuPay}）？余额将从 ${s.balance} 减为 ${(parseInt(s.balance,10)||0)-credits}。`, async () => {
            if (busy) return;
            setBusy(true);
            try {
                await v1Api(`/students/${s.id}/credit-transactions`, {
                    method: 'POST',
                    body: JSON.stringify({
                        transactionType: 'refund',
                        legacy_type: 'refund_out',
                        amount: credits,
                        feeAudCents: Math.round(amt * 100),
                        note: `退款退课 | 原因: ${rfReason.trim()} | 方式: ${tuPay}`,
                    }),
                });
                await load();
                setRfCr(''); setRfAmt(''); setRfReason(''); setTuStu(null);
                const cMsg = `${s.name} 您好！已为您办理退课 ${credits} 节${amt?`、退款 $${amt}（${tuPay}）`:''}，当前剩余 ${(parseInt(s.balance,10)||0)-credits} 课时。感谢您的理解与支持。`;
                showToast(`${s.name} 退课 ${credits} 节 / 退款 $${amt}`, 'warn',
                    {label:'📋 复制退款确认（发家长）', onClick:()=>copyText(cMsg,'退款确认已复制')});
            } catch(err) { showToast(`退款失败：${err.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger:true, confirmText:`确认退课 ${credits} 节`});
    };

    const handleAddStudent = (e) => {
        e.preventDefault();
        const fd        = new FormData(e.target);
        const firstName = fd.get('firstName').trim();
        const lastName  = fd.get('lastName').trim();
        if (!firstName) { showToast('First Name 不能为空','error'); return; }
        const fullName = lastName ? `${firstName} ${lastName}` : firstName;
        const mobile   = fd.get('mobile').trim();
        const email    = fd.get('email').trim();
        const wechat   = (fd.get('wechat')   ||'').trim();
        const balance  = parseInt(fd.get('balance')||'0',10);
        const remark   = fd.get('remark')||'';
        const preferences = collectPreferences(fd);
        const legacyPrefs = legacyPreferenceValues(preferences, fd);
        const birthday  = (fd.get('birthday')  ||'').trim();
        const doCreate = async () => {
            if (busy) return; setBusy(true);
            try {
                const ns = {id:Date.now(), firstName, lastName, name:fullName,
                            mobile, email, wechat, photo:formPhoto, preferences, ...legacyPrefs,
                            birthday, balance, remark, lastActive:todayISO(), archived:false};
                await save({...db, students:[ns,...db.students], logs:[mkLog(fullName,'新生注册',`+${balance}`,'系统建档',0,{studentId:ns.id}),...db.logs]});
                e.target.reset(); setFormPhoto(''); setTab('students'); setSrch('');
                showToast(`${fullName} 已建档`);
            } finally { setBusy(false); }
        };
        if (db.students.some(s=>s.name.toLowerCase()===fullName.toLowerCase())) {
            confirm(`已存在同名学员 "${fullName}"，仍要继续建档？`, doCreate, {confirmText:'继续建档'});
        } else {
            doCreate();
        }
    };

    const handleUpdateStudent = async (e) => {
        e.preventDefault();
        const fd        = new FormData(e.target);
        const firstName = fd.get('firstName').trim();
        if (!firstName) { showToast('First Name 不能为空','error'); return; }
        if (busy) return;
        setBusy(true);
        try {
            const lastName  = fd.get('lastName').trim();
            const newName = lastName ? `${firstName} ${lastName}` : firstName;
            const mobile  = fd.get('mobile').trim();
            const email   = fd.get('email').trim();
            const wechat  = (fd.get('wechat') ||'').trim();
            const balance = parseInt(fd.get('balance')||String(selS.balance??0), 10) || 0;
            const remark     = fd.get('remark')||'';
            const preferences = collectPreferences(fd);
            const legacyPrefs = legacyPreferenceValues(preferences, fd, selS);
            const birthday   = (fd.get('birthday')   ||'').trim();
            const diff    = balance - (parseInt(selS.balance,10)||0);
            const oldName = selS.name;
            const ns = db.students.map(s => s.id===selS.id
                ? {...s, firstName, lastName, name:newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, photo:editPhoto, ...(diff!==0?{lastActive:todayISO()}:{})}
                : s);
            // B3 fix + D3: rename logs by studentId when available (precise);
            // fall back to name match only when no other student shares the old name
            const otherSameName = db.students.some(s => s.id !== selS.id && (s.name||'').toLowerCase() === oldName.toLowerCase());
            const nl = (oldName !== newName)
                ? db.logs.map(l => {
                    if (l.studentId === selS.id) return {...l, studentName:newName};
                    if (!l.studentId && !otherSameName && l.studentName===oldName) return {...l, studentName:newName};
                    return l;
                  })
                : db.logs;
            const changeStr = diff!==0 ? (diff>0?`+${diff}`:`${diff}`) : '0';
            const noteStr   = diff!==0 ? '管理端校准' : (oldName!==newName?`改名: ${oldName}→${newName}`:'信息修改');
            if (TENANT_SLUG) {
                /* A2: 档案字段照旧整包保存（余额由服务端忽略）；
                   课时差额单独走 v1 调整流水 */
                await save({...db, students:ns, logs:nl});
                if (diff !== 0) {
                    await v1Api(`/students/${selS.id}/credit-transactions`, {
                        method: 'POST',
                        body: JSON.stringify({
                            transactionType: 'adjustment',
                            legacy_type: diff > 0 ? 'adjustment_in' : 'adjustment_out',
                            amount: Math.abs(diff),
                            note: '管理端校准',
                        }),
                    });
                    await load();
                }
            } else {
                await save({...db, students:ns, logs:[mkLog(newName, diff!==0?'调整课时':'更新档案', changeStr, noteStr, 0, {studentId:selS.id}),...nl]});
            }
            setSelS({...selS, firstName, lastName, name:newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, photo:editPhoto, ...(diff!==0?{lastActive:todayISO()}:{})});
            setEditP(false);
            showToast('档案已更新');
        } finally { setBusy(false); }
    };

    const handleDelete = (sid, sname) => {
        confirm(`永久删除 "${sname}" 及其排课记录。历史日志将保留，但此操作不可逆。建议优先使用「归档」。`, async () => {
            if (busy) return; // Fix ④
            setBusy(true);
            try {
                const ns = db.students.filter(s=>s.id!==sid);
                const nr = {...db.rosters};
                Object.keys(nr).forEach(d => { nr[d]=nr[d].filter(id=>id!==sid); });
                await save({...db, students:ns, rosters:nr, logs:[mkLog(sname,'彻底删除档案','0','管理员移除',0,{studentId:sid}),...db.logs]});
                setSelS(null); setEditP(false);
                showToast(`${sname} 已移除`, 'warn');
            } finally { setBusy(false); }
        }, {danger:true, confirmText:'永久删除'});
    };

    /* ── Portfolio helpers ── */
    const portfolioDoUpload = async (file, note, date, title, isPublic=false) => {
        if (!selS) return;
        setPortBusy(true);
        try {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('studentId', String(selS.id));
            fd.append('note', note || '');
            fd.append('title', title || '');   /* B4 */
            fd.append('date', date || todayISO());
            fd.append('public', isPublic ? '1' : '0');
            fd.append('publicConsentConfirmed', isPublic ? '1' : '0');
            const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/upload`, {
                method: 'POST', credentials:'include', body: fd
            });
            if (r.status === 401) { showToast('登录已过期', 'error'); return; }
            if (!r.ok) { showToast('上传失败，请重试', 'error'); return; }
            const res = await r.json();
            const newPort = [res.item, ...(selS.portfolio || [])];
            setSelS(p => ({...p, portfolio: newPort}));
            setDb(d => ({...d, students: d.students.map(s => s.id===selS.id ? {...s,portfolio:newPort} : s)}));
            showToast('🎨 作品已上传', 'success');
            // B6: Release object URL to free browser memory
            if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
            setPortUpload(false);
            setPortUpFile(null);
        } catch(e) {
            showToast('上传失败', 'error');
        } finally { setPortBusy(false); }
    };

    const portfolioDoDelete = async (pid) => {
        if (!selS) return;
        confirm(`确认删除这张作品照片？此操作不可恢复。`, async () => {
            const sid = String(selS.id);
            try {
                const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(pid)}`, {
                    method: 'DELETE', credentials:'include'
                });
                if (r.status === 401) { showToast('登录已过期，请重新登录', 'error'); return; }
                if (!r.ok) { showToast('删除失败', 'error'); return; }
                const newPort = (selS.portfolio || []).filter(i => String(i.id) !== String(pid));
                setSelS(p => ({...p, portfolio: newPort}));
                setDb(d => ({...d, students: d.students.map(s => s.id===selS.id ? {...s,portfolio:newPort} : s)}));
                // #2 fix: close lightbox when last photo deleted; otherwise clamp idx
                if (portLB) {
                    if (newPort.length === 0) setPortLB(null);
                    else setPortLB(p => ({...p, items: newPort, idx: Math.max(0, Math.min(p.idx, newPort.length-1))}));
                }
                showToast('已删除', 'warn');
            } catch(e) { showToast('删除失败', 'error'); }
        }, {danger:true, confirmText:'删除'});
    };

    const portfolioDoUpdateNote = async () => {
        if (!portEdit) return;
        const {sid, item, note, date, title, public:isPublic=false} = portEdit;
        try {
            const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(item.id)}`, {
                method: 'PATCH',
                credentials:'include', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({note, date, title, public:isPublic, publicConsentConfirmed:isPublic})
            });
            if (r.status === 401) { showToast('登录已过期，请重新登录', 'error'); return; }
            if (!r.ok) { showToast('更新失败', 'error'); return; }
            const newPort = (selS?.portfolio || []).map(i => String(i.id)===String(item.id) ? {...i,note,date,title,public:isPublic,visibility:isPublic?'shared':'private'} : i);
            setSelS(p => p ? ({...p, portfolio: newPort}) : p);
            setDb(d => ({...d, students: d.students.map(s => s.id===selS?.id ? {...s,portfolio:newPort} : s)}));
            // B3: Also sync lightbox items so open lightbox reflects the updated note/date
            setPortLB(p => p ? ({...p, items: newPort}) : null);
            setPortEdit(null);
            showToast('✅ 已更新', 'success');
        } catch(e) { showToast('更新失败', 'error'); }
    };

    const addToRoster = async () => {
        if (!rPick||busy) return;
        /* B2-②: 已在当日名单（含课表来源）时明确提示而非静默（v5.2） */
        if (dayIds.includes(rPick)) {
            const s = db.students.find(x=>x.id===rPick);
            showToast(`${s?s.name:'该学员'} 已在当日名单中`, 'warn');
            setRPick(null);
            return;
        }
        setBusy(true);
        try {
            const cur = db.rosters[rDate]||[];
            if (!cur.includes(rPick)) await save({...db, rosters:{...db.rosters,[rDate]:[...cur,rPick]}});
            setRPick(null); /* Fix #1: clears picker q via useEffect */
        } finally { setBusy(false); }
    };
    const removeFromRoster = async (sid) => {
        if (busy) return; setBusy(true);
        try { await save({...db, rosters:{...db.rosters,[rDate]:(db.rosters[rDate]||[]).filter(id=>id!==sid)}}); }
        finally { setBusy(false); }
    };

    /* ── Pending: approve ── */
    const approveStudent = async (pid) => {
        const pen = (db.pending||[]).find(p=>p.id===pid); if (!pen) return;
        if (busy) return;
        const credits = parseInt(approveCredits[pid]||'0', 10);
        const fn = pen.firstName||'', ln = pen.lastName||'';
        const fullName = ln ? `${fn} ${ln}` : fn;
        const doApprove = async () => {
            setBusy(true);
            try {
                if (TENANT_SLUG) {
                    /* A4: 与 Studio Admin 同一审核状态机 —— 批准即转化建学生、
                       家长自动收到确认邮件；初始课时走期初流水入账本 */
                    const res = await v1Api(`/registrations/${pid}`, {
                        method: 'PATCH',
                        body: JSON.stringify({status: 'approved'}),
                    });
                    const newSid = res.student_id || (res.registration && res.registration.student_id);
                    if (credits > 0 && newSid) {
                        await v1Api(`/students/${newSid}/credit-transactions`, {
                            method: 'POST',
                            body: JSON.stringify({transactionType: 'migration', amount: credits, note: '注册审批初始课时'}),
                        });
                    }
                    await load();
                    showToast(`${fullName} 已批准建档，家长将收到确认邮件`);
                } else {
                    const ns = {
                        id: Date.now(), firstName:fn, lastName:ln, name:fullName,
                        mobile:pen.mobile||'', wechat:pen.wechat||'', email:pen.email||'',
                        photo:pen.photo||'', preferences:pen.preferences||{},
                        ...legacyPreferenceValues(pen.preferences||{}, null, pen),
                        birthday:pen.birthday||'',
                        balance:credits, remark:pen.message||'',
                        lastActive:todayISO(), archived:false
                    };
                    const newPending = (db.pending||[]).filter(p=>p.id!==pid);
                    await save({...db, students:[ns,...db.students], pending:newPending,
                        logs:[mkLog(fullName,'批准注册',`+${credits}`,`来自注册门户，管理员审批`,0,{studentId:ns.id}),...db.logs]});
                    showToast(`${fullName} 已批准建档`);
                }
                setApproveCredits(p => { const n={...p}; delete n[pid]; return n; });
            } catch(e) { showToast(`批准失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        };
        if (db.students.some(s => s.name.toLowerCase() === fullName.toLowerCase())) {
            confirm(`已存在同名学员 "${fullName}"，仍要继续建档？`, doApprove, {confirmText:'继续建档'});
        } else {
            doApprove();
        }
    };

    /* ── Pending: reject ── */
    const rejectStudent = (pid) => {
        const pen = (db.pending||[]).find(p=>p.id===pid); if (!pen) return;
        const name = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
        confirm(`拒绝 "${name}" 的注册申请？${TENANT_SLUG ? '（家长将收到通知邮件）' : '并删除该记录？'}`, async () => {
            if (busy) return; setBusy(true);
            try {
                if (TENANT_SLUG) {
                    /* A4: 拒绝走 v1 状态机，原因随邮件发给家长 */
                    const note = (window.prompt('拒绝原因（将随通知邮件发送给家长，可留空）') || '').trim();
                    await v1Api(`/registrations/${pid}`, {
                        method: 'PATCH',
                        body: JSON.stringify({status: 'rejected', reviewNote: note || '管理员拒绝注册申请'}),
                    });
                    await load();
                } else {
                    const newPending = (db.pending||[]).filter(p=>p.id!==pid);
                    await save({...db, pending:newPending,
                        logs:[mkLog(name,'拒绝注册','0','管理员拒绝注册申请'),...db.logs]});
                }
                setApproveCredits(p => { const n={...p}; delete n[pid]; return n; });
                showToast(`${name} 的申请已拒绝`, 'warn');
            } catch(e) { showToast(`操作失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger:true, confirmText:'确认拒绝'});
    };

    const advanceRegistration = async (pid, status) => {
        if (busy || !TENANT_SLUG) return;
        setBusy(true);
        try {
            const nextDate = followUpDates[pid] || '';
            await v1Api(`/registrations/${pid}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    status,
                    nextFollowUpAt: nextDate ? `${nextDate}T09:00:00` : '',
                    reviewNote: status === 'contacted' ? 'Studio contacted this lead.' : '',
                }),
            });
            await load();
            showToast(status === 'contacted' ? '已标记联系' : status === 'trial_booked' ? '已预约试听' : '已加入跟进');
        } catch (e) { showToast(`更新失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    /* ── Export: CSV ── */
    const downloadTenantExport = async (path, fallbackName) => {
        if (!TENANT_SLUG) return;
        try {
            const response = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1/export/${path}`, {credentials:'include'});
            if (!response.ok) {
                const body = await response.json().catch(()=>({}));
                throw new Error(body.message || `HTTP ${response.status}`);
            }
            const blob = await response.blob();
            const disposition = response.headers.get('Content-Disposition') || '';
            const match = disposition.match(/filename="?([^";]+)"?/i);
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url; a.download = match?.[1] || fallbackName; a.click();
            setTimeout(()=>URL.revokeObjectURL(url), 1000);
        } catch (error) {
            showToast(`导出失败：${error.message}`, 'error');
        }
    };
    const exportStudentsCSV = () => downloadTenantExport('students.csv', `Studio_Students_${todayISO()}.csv`);
    const exportRevenueCSV = () => downloadTenantExport('revenue.csv', `Studio_Revenue_${todayISO()}.csv`);
    const exportLogsCSV = () => downloadTenantExport('credit-ledger.csv', `Studio_Ledger_${todayISO()}.csv`);

    const changePin = () => {
        if (!/^\d{4}$/.test(newPin1)) { showToast('PIN 必须是 4 位数字','error'); return; }
        if (newPin1!==newPin2)         { showToast('两次输入不一致','error'); return; }
        savePin(newPin1); setNewPin1(''); setNewPin2(''); setShowSettings(false);
        showToast('PIN 码已更新');
    };
    const lockScreen = () => { if (!pinEnabled) { setShowSettings(false); confirm('确认退出登录？', doLogout, {confirmText:'退出登录'}); return; } clearSess(); setPinOK(false); setShowSettings(false); };

    /* ── Guards ── */
    if (!loggedIn) return <LoginScreen onLogin={refreshSession}/>;
    if (pinEnabled && !pinOK) return <PINScreen onUnlock={() => { markSess(); setPinOK(true); }}/>;
    if (!conn) return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white p-4">
            <div className="text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full">
                {connErr ? (<>
                    <div className="text-5xl mb-3">⚠️</div>
                    <h2 className="text-xl font-bold mb-3">连接失败</h2>
                    <p className="text-gray-400 text-sm mb-3 leading-relaxed">请确认终端正在运行 <code className="text-indigo-400 bg-gray-900 px-1 rounded">python3 server.py</code></p>
                    <p className="text-red-400 text-xs font-mono bg-gray-900 p-2 rounded mb-4">{connErr}</p>
                    <button onClick={load} className="bg-indigo-600 active:bg-indigo-700 px-8 py-3 rounded-xl font-bold w-full">重新连接</button>
                </>) : (<>
                    <span className="sp mb-3 w-10 h-10 border-4 block mx-auto"></span>
                    <h2 className="text-xl font-bold mt-3">连接中...</h2>
                </>)}
            </div>
        </div>
    );

    const pendingCount = (db.pending||[]).length;
    const NAV = [
        {k:'dashboard',i:'📊',l:'工作台',  s:'工作台'},
        {k:'roster',   i:'📅',l:'每日排课', s:'排课'},
        {k:'students', i:'👥',l:'学员档案', s:'档案'},
        {k:'pending',  i:'📋',l:'待审核',   s:'审核', badge: pendingCount},
        {k:'topup',    i:'💰',l:'充值结算', s:'充值'},
        {k:'logs',     i:'📜',l:'操作日志', s:'日志'},
        {k:'stats',    i:'📈',l:'商业洞察', s:'统计'},
    ].filter(item => allowedTabs.includes(item.k));

    /* ══════════════════════════ RENDER ══════════════════════════ */
    return (
        <div className="flex h-screen bg-gray-50">
            {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} action={toast.action} onDone={()=>setToast(null)}/>}
            <ConfirmDialog dialog={confirmDialog} onClose={()=>setConfirmDialog(null)}/>

            {/* ── Portfolio Lightbox ── */}
            {portLB && portLB.items.length > 0 && (
                <div className="fixed inset-0 bg-black/95 z-[90] flex flex-col"
                    style={{paddingBottom:'env(safe-area-inset-bottom,0px)', paddingTop:'env(safe-area-inset-top,0px)'}}
                    onTouchStart={e=>{ lbTouchX.current = e.touches[0].clientX; lbTouchX._y = e.touches[0].clientY; }}
                    onTouchEnd={e=>{
                        const dx = e.changedTouches[0].clientX - lbTouchX.current;
                        const dy = e.changedTouches[0].clientY - (lbTouchX._y || 0);
                        // #6 fix: only treat as horizontal swipe when |dx|>|dy| (ignore diagonal / vertical scrolls)
                        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) setPortLB(p => {
                            if (!p) return p;
                            const next = dx < 0 ? Math.min(p.items.length-1, p.idx+1) : Math.max(0, p.idx-1);
                            return {...p, idx: next};
                        });
                    }}>
                    {/* M3: safe-area-inset-top for iPhone notch */}
                    <div className="flex justify-between items-center px-4 py-3 flex-shrink-0"
                        style={{paddingTop:'max(12px,env(safe-area-inset-top,12px))'}}>
                        <div className="min-w-0">
                            <p className="text-white font-bold text-sm truncate">{portLB.items[portLB.idx]?.title || fmtDate(portLB.items[portLB.idx]?.date)}</p>
                            {portLB.items[portLB.idx]?.title && <p className="text-white/50 text-[11px] truncate">{fmtDate(portLB.items[portLB.idx]?.date)}</p>}
                            {portLB.items[portLB.idx]?.note && <p className="text-white/60 text-xs truncate">💬 {portLB.items[portLB.idx].note}</p>}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-white/40 text-xs">{portLB.idx+1} / {portLB.items.length}</span>
                            {/* M2: Edit button in lightbox — sole access point on touch devices */}
                            <button onClick={()=>{const cur=portLB.items[portLB.idx];if(cur&&selS)setPortEdit({sid:String(selS.id),item:cur,note:cur.note||'',title:cur.title||'',date:cur.date||todayISO(),public:!!cur.public});}}
                                className="text-white/80 active:text-white w-9 h-9 flex items-center justify-center text-base">✏️</button>
                            <button onClick={()=>setPortLB(null)} className="text-white text-2xl font-bold w-10 h-10 flex items-center justify-center">×</button>
                        </div>
                    </div>
                    <div className="flex-1 flex items-center justify-center px-2 min-h-0"
                        onClick={()=>setPortLB(null)}>
                        {/* #8 fix: onError shows fallback text instead of broken-image icon */}
                        <img
                            src={portfolioImgSrc(selS?.id, portLB.items[portLB.idx])}
                            className="max-w-full max-h-full object-contain rounded-xl shadow-2xl"
                            onClick={e=>e.stopPropagation()}
                            onError={e=>{e.target.style.display='none';e.target.nextSibling&&(e.target.nextSibling.style.display='flex');}}/>
                        <div style={{display:'none'}} className="flex-col items-center justify-center gap-2 text-white/50">
                            <span className="text-4xl">🖼</span>
                            <span className="text-sm">图片加载失败</span>
                        </div>
                    </div>
                    <div className="flex justify-between items-center px-4 py-3 flex-shrink-0">
                        <button onClick={()=>setPortLB(p=>({...p,idx:Math.max(0,p.idx-1)}))}
                            disabled={portLB.idx===0}
                            className="py-2.5 px-6 bg-white/20 active:bg-white/30 text-white rounded-xl font-bold text-sm disabled:opacity-30 min-h-[44px]">
                            ← 上一张
                        </button>
                        <button
                            onClick={()=>portfolioDoDelete(String(portLB.items[portLB.idx]?.id))}
                            className="py-2.5 px-4 bg-red-500/80 active:bg-red-600/80 text-white rounded-xl text-sm min-h-[44px]">🗑</button>
                        <button onClick={()=>setPortLB(p=>({...p,idx:Math.min(p.items.length-1,p.idx+1)}))}
                            disabled={portLB.idx===portLB.items.length-1}
                            className="py-2.5 px-6 bg-white/20 active:bg-white/30 text-white rounded-xl font-bold text-sm disabled:opacity-30 min-h-[44px]">
                            下一张 →
                        </button>
                    </div>
                </div>
            )}

            {/* ── Portfolio Upload Modal ── */}
            {portUpload && (
                <div className="fixed inset-0 bg-black/70 z-[85] flex items-end sm:items-center justify-center sm:p-4"
                    onClick={e=>{if(e.target===e.currentTarget){if(portUpFile?.dataUrl)URL.revokeObjectURL(portUpFile.dataUrl);setPortUpload(false);setPortUpFile(null);}}}>
                    {/* M5: click backdrop to close */}
                    <div className="bg-white w-full sm:rounded-3xl sm:max-w-md shadow-2xl overflow-hidden anim"
                        style={{paddingBottom:'env(safe-area-inset-bottom,0px)'}}>
                        <div className="flex justify-between items-center px-5 pt-5 pb-3">
                            <h3 className="font-bold text-gray-800 text-lg">🎨 上传作品</h3>
                            <button onClick={()=>{if(portUpFile?.dataUrl)URL.revokeObjectURL(portUpFile.dataUrl);setPortUpload(false);setPortUpFile(null);}} className="text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center">×</button>
                        </div>
                        <div className="px-5 pb-5">
                            {!portUpFile ? (
                                <div>
                                    <div className="flex gap-3">
                                        <label className="flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-purple-300 rounded-2xl cursor-pointer active:bg-purple-50 hover:bg-purple-50 transition-colors">
                                            <span className="text-3xl">📷</span>
                                            <span className="text-sm font-bold text-purple-700">拍照</span>
                                            <input type="file" accept="image/*" capture="environment" className="hidden"
                                                onChange={e=>{
                                                    const file=e.target.files[0]; if(!file) return;
                                                    if(file.size>10*1024*1024){showToast('文件太大，请先压缩','error');return;}
                                                    setPortUpFile({file,dataUrl:URL.createObjectURL(file),note:'',date:todayISO(),public:false});
                                                }}/>
                                        </label>
                                        <label className="flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-indigo-300 rounded-2xl cursor-pointer active:bg-indigo-50 hover:bg-indigo-50 transition-colors">
                                            <span className="text-3xl">🖼</span>
                                            <span className="text-sm font-bold text-indigo-700">从相册</span>
                                            <input type="file" accept="image/*" className="hidden"
                                                onChange={e=>{
                                                    const file=e.target.files[0]; if(!file) return;
                                                    if(file.size>10*1024*1024){showToast('文件太大，请先压缩','error');return;}
                                                    setPortUpFile({file,dataUrl:URL.createObjectURL(file),note:'',date:todayISO(),public:false});
                                                }}/>
                                        </label>
                                    </div>
                                    <p className="text-xs text-gray-400 text-center mt-3">支持 JPG/PNG，最大 10 MB</p>
                                </div>
                            ) : (
                                <div>
                                    <img src={portUpFile.dataUrl} className="w-full h-52 object-cover rounded-2xl mb-4 bg-gray-100"/>
                                    <div className="space-y-3">
                                        <div>
                                            <label className="text-xs font-bold text-gray-500 mb-1.5 block">📅 作品日期</label>
                                            <input type="date" value={portUpFile.date}
                                                onChange={e=>setPortUpFile(p=>({...p,date:e.target.value}))}
                                                className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                        </div>
                                        <div>
                                            <label className="text-xs font-bold text-gray-500 mb-1.5 block">🖼 作品标题 <span className="font-normal text-gray-400">选填</span></label>
                                            <input type="text" value={portUpFile.title||''}
                                                onChange={e=>setPortUpFile(p=>({...p,title:e.target.value}))}
                                                placeholder="如：星空下的向日葵" maxLength={40}
                                                className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                        </div>
                                        <div>
                                            <label className="text-xs font-bold text-gray-500 mb-1.5 block">💬 老师评语 <span className="font-normal text-gray-400">选填，家长可见</span></label>
                                            <input type="text" value={portUpFile.note}
                                                onChange={e=>setPortUpFile(p=>({...p,note:e.target.value}))}
                                                placeholder="如：水彩练习 第1期" maxLength={50}
                                                className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                        </div>
                                        <label className="flex items-start gap-3 rounded-xl border border-purple-100 bg-purple-50/60 p-3 text-sm text-purple-900">
                                            <input type="checkbox" checked={!!portUpFile.public}
                                                onChange={e=>setPortUpFile(p=>({...p,public:e.target.checked}))}
                                                className="mt-0.5 w-4 h-4 flex-shrink-0"/>
                                            <span>
                                                <span className="font-bold block">确认已获授权并展示到官网作品墙</span>
                                                <span className="text-xs text-purple-700">勾选即确认家长或成年学员已同意公开；标题和评语不得包含学员全名。</span>
                                            </span>
                                        </label>
                                    </div>
                                    <div className="flex gap-3 mt-4">
                                        <button onClick={()=>{if(portUpFile?.dataUrl)URL.revokeObjectURL(portUpFile.dataUrl);setPortUpFile(null);}}
                                            className="flex-1 py-3 rounded-xl border border-gray-200 text-sm font-bold text-gray-500 active:bg-gray-50 min-h-[50px]">
                                            重新选择
                                        </button>
                                        <button onClick={()=>portfolioDoUpload(portUpFile.file,portUpFile.note,portUpFile.date,portUpFile.title,portUpFile.public)}
                                            disabled={portBusy}
                                            className="flex-1 py-3 rounded-xl bg-purple-600 active:bg-purple-700 text-white text-sm font-bold disabled:opacity-50 min-h-[50px]">
                                            {portBusy ? '上传中...' : '✅ 确认上传'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {/* ── Portfolio Edit Note Modal ── */}
            {/* #4 fix: backdrop click closes; #5 fix: items-end bottom-sheet avoids iOS keyboard overlap */}
            {portEdit && (
                <div className="fixed inset-0 bg-black/60 z-[85] flex items-end sm:items-center justify-center sm:p-4"
                    onClick={e=>{if(e.target===e.currentTarget)setPortEdit(null);}}>
                    <div className="bg-white w-full sm:rounded-3xl sm:max-w-sm rounded-t-3xl p-5 shadow-2xl anim"
                        style={{paddingBottom:'max(20px,env(safe-area-inset-bottom,20px))'}}>
                        <div className="flex justify-between items-center mb-4">
                            <h3 className="font-bold text-gray-800 text-lg">✏️ 编辑作品信息</h3>
                            <button onClick={()=>setPortEdit(null)} className="text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center">×</button>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <label className="text-xs font-bold text-gray-500 mb-1.5 block">📅 作品日期</label>
                                <input type="date" value={portEdit.date}
                                    onChange={e=>setPortEdit(p=>({...p,date:e.target.value}))}
                                    className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                            </div>
                            <div>
                                <label className="text-xs font-bold text-gray-500 mb-1.5 block">🖼 作品标题</label>
                                <input type="text" value={portEdit.title||''}
                                    onChange={e=>setPortEdit(p=>({...p,title:e.target.value}))}
                                    maxLength={40}
                                    className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                            </div>
                            <div>
                                <label className="text-xs font-bold text-gray-500 mb-1.5 block">💬 老师评语 <span className="font-normal text-gray-400">家长可见</span></label>
                                <input type="text" value={portEdit.note}
                                    onChange={e=>setPortEdit(p=>({...p,note:e.target.value}))}
                                    maxLength={50}
                                    className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                            </div>
                            <label className="flex items-start gap-3 rounded-xl border border-purple-100 bg-purple-50/60 p-3 text-sm text-purple-900">
                                <input type="checkbox" checked={!!portEdit.public}
                                    onChange={e=>setPortEdit(p=>({...p,public:e.target.checked}))}
                                    className="mt-0.5 w-4 h-4 flex-shrink-0"/>
                                <span>
                                    <span className="font-bold block">确认已获授权并展示到官网作品墙</span>
                                    <span className="text-xs text-purple-700">每次重新公开都会记录当前管理员和确认时间；关闭后仍保留在私人作品集。</span>
                                </span>
                            </label>
                        </div>
                        <div className="flex gap-3 mt-4">
                            <button onClick={()=>setPortEdit(null)}
                                className="flex-1 py-3 rounded-xl border border-gray-200 text-sm font-bold text-gray-500 active:bg-gray-50 min-h-[50px]">
                                取消
                            </button>
                            <button onClick={portfolioDoUpdateNote}
                                className="flex-1 py-3 rounded-xl bg-purple-600 active:bg-purple-700 text-white text-sm font-bold min-h-[50px]">
                                保存
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* G1: Global Search Overlay */}
            {gOpen && (
                <div className="fixed inset-0 bg-black/60 z-[80] flex items-start justify-center pt-[10vh] px-4 backdrop-blur-sm"
                     onClick={()=>{setGOpen(false);setGQ('');}}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden anim" onClick={e=>e.stopPropagation()}>
                        <div className="flex items-center gap-2 px-4 py-3 border-b">
                            <span className="text-gray-400 text-xl">🔍</span>
                            <input autoFocus type="text" placeholder="搜索学员姓名、电话、微信号..." value={gQ}
                                onChange={e=>setGQ(e.target.value)}
                                onKeyDown={e=>{ if(e.key==='Escape'){setGOpen(false);setGQ('');} }}
                                className="flex-1 outline-none text-gray-800 text-sm bg-transparent placeholder-gray-400"/>
                            <kbd className="hidden sm:inline text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded font-mono">ESC</kbd>
                        </div>
                        <div className="max-h-80 overflow-y-auto sl">
                            {!gQ.trim() && (
                                <p className="text-center text-gray-400 text-sm py-8">输入姓名、手机号或微信号搜索</p>
                            )}
                            {gQ.trim() && !gResults.length && (
                                <p className="text-center text-gray-400 text-sm py-8">未找到匹配学员</p>
                            )}
                            {gResults.map(s => {
                                const tag = getTag(s);
                                return (
                                    <button key={s.id} className="w-full flex items-center gap-3 px-4 py-3 hover:bg-indigo-50 active:bg-indigo-100 border-b border-gray-50 text-left min-h-[56px]"
                                        onClick={()=>{ setTab('students'); setSelS(s); setEditP(false); setGOpen(false); setGQ(''); }}>
                                        <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                                        <div className="flex-1 min-w-0">
                                            <p className="font-bold text-gray-800 text-sm truncate">{s.name}</p>
                                            <p className="text-xs text-gray-400">{s.mobile||'—'}{s.wechat?` · 💬 ${s.wechat}`:''}</p>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0">
                                            {tag && <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${tag.cls}`}>{tag.icon} {tag.label}</span>}
                                            <BalBadge n={s.balance}/>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>
                        <div className="px-4 py-2 bg-gray-50 text-xs text-gray-400 border-t">
                            点击学员查看档案 · <kbd className="bg-gray-200 px-1 rounded font-mono">⌘K</kbd> 打开 / 关闭
                        </div>
                    </div>
                </div>
            )}

            {/* Settings modal */}
            {showSettings && (
                <div className="fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4" onClick={()=>setShowSettings(false)}
                    style={{paddingTop:'max(16px, env(safe-area-inset-top, 16px))', paddingBottom:'max(16px, env(safe-area-inset-bottom, 16px))'}}>
                    <div className="bg-white rounded-2xl p-6 w-full max-w-2xl shadow-2xl anim overflow-y-auto modal-scroll" style={{maxHeight:'90dvh'}} onClick={e=>e.stopPropagation()}>
                        <div className="flex justify-between items-center mb-5">
                            <h3 className="font-bold text-gray-800">⚙️ 系统设置</h3>
                            <button onClick={()=>setShowSettings(false)} className="text-gray-400 active:text-gray-700 text-xl p-1">×</button>
                        </div>
                        {/* A5: Public website and lead-capture settings live in Studio Admin. */}
                        {TENANT_SLUG && ownerRoles.includes(actorRole) && (
                            <a href={`/${TENANT_SLUG}/studio-admin`} target="_blank" rel="noopener"
                                className="block bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3 text-sm font-bold text-indigo-700 active:bg-indigo-100">
                                🎨 网站、Logo、配色与注册表设置 →
                                <p className="text-[11px] font-normal text-indigo-400 mt-0.5">打开 Studio Admin 管理公开门户、注册表字段、品牌文案和页面展示</p>
                            </a>
                        )}
                        {canManageOperations && <div className="mt-4 pt-4 border-t border-gray-100 space-y-3">
                            <div>
                                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">团队与权限</p>
                                <p className="text-xs text-gray-400 mt-0.5">Owner管理团队；Manager负责日常运营，Teacher负责签到与作品，Front Desk负责报名、学员与课时。</p>
                            </div>
                            <div className="space-y-2">
                                {team.map(member=>(
                                    <div key={member.id} className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                        <div className="flex-1 min-w-0">
                                            <p className="text-sm font-bold text-gray-700 truncate">{member.full_name}</p>
                                            <p className="text-xs text-gray-400 truncate">{member.email} · {member.role} · {member.status}</p>
                                        </div>
                                        {ownerRoles.includes(actorRole) && member.role!=='owner' && <button type="button" disabled={teamBusy}
                                            onClick={()=>updateTeamMember(member,member.status==='active'?'disabled':'active')}
                                            className="text-xs font-bold px-2 py-1 rounded-lg border border-gray-200 text-gray-600">
                                            {member.status==='active'?'停用':'启用'}
                                        </button>}
                                    </div>
                                ))}
                            </div>
                            {ownerRoles.includes(actorRole) ? <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 bg-indigo-50 border border-indigo-100 rounded-xl p-3">
                                <input value={teamForm.fullName} onChange={e=>setTeamForm(p=>({...p,fullName:e.target.value}))}
                                    placeholder="姓名" className="px-3 py-2 border border-gray-300 rounded-xl text-sm"/>
                                <input type="email" value={teamForm.email} onChange={e=>setTeamForm(p=>({...p,email:e.target.value}))}
                                    placeholder="邮箱" className="px-3 py-2 border border-gray-300 rounded-xl text-sm"/>
                                <select value={teamForm.role} onChange={e=>setTeamForm(p=>({...p,role:e.target.value}))}
                                    className="px-3 py-2 border border-gray-300 rounded-xl text-sm">
                                    <option value="manager">Manager</option><option value="teacher">Teacher</option><option value="front_desk">Front Desk</option><option value="staff">Staff (legacy)</option>
                                </select>
                                <input type="password" value={teamForm.temporaryPassword} onChange={e=>setTeamForm(p=>({...p,temporaryPassword:e.target.value}))}
                                    placeholder="临时密码（至少8位）" className="px-3 py-2 border border-gray-300 rounded-xl text-sm"/>
                                <button type="button" onClick={createTeamMember} disabled={teamBusy}
                                    className="sm:col-span-2 bg-indigo-600 text-white py-2.5 rounded-xl font-bold text-sm disabled:opacity-50">添加团队成员</button>
                            </div> : <p className="text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-xl px-3 py-2">当前角色可查看团队；只有 Owner 可以新增、停用或更改成员角色。</p>}
                        </div>}
                        {/* 修改登录密码 */}
                        <div className="space-y-2">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">修改登录密码</p>
                            <input type="password" placeholder="当前密码" value={pwOld} onChange={e=>setPwOld(e.target.value)}
                                className="w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"/>
                            <input type="password" placeholder="新密码（≥8位）" value={pwNew1} onChange={e=>setPwNew1(e.target.value)}
                                className="w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"/>
                            <input type="password" placeholder="再次确认新密码" value={pwNew2} onChange={e=>setPwNew2(e.target.value)}
                                className="w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"/>
                            {pwMsg && <p className={`text-xs font-medium ${pwMsg.startsWith('✅')?'text-green-600':'text-red-500'}`}>{pwMsg}</p>}
                            <button onClick={changeWebPw} disabled={pwBusy}
                                className="w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm">
                                {pwBusy ? '更新中...' : '更新密码'}
                            </button>
                        </div>
                        {/* P2: PIN toggle */}
                        <div className="mt-4 pt-4 border-t border-gray-100">
                            <div className="flex items-center justify-between">
                                <div>
                                    <p className="text-xs font-bold text-gray-600">启用屏幕锁（PIN）</p>
                                    <p className="text-xs text-gray-400 mt-0.5">关闭时「锁定」= 退出登录</p>
                                </div>
                                <button onClick={()=>togglePin(!pinEnabled)} className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${pinEnabled?'bg-indigo-600':'bg-gray-300'}`}>
                                    <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${pinEnabled?'translate-x-6':'translate-x-1'}`}/>
                                </button>
                            </div>
                        </div>
                        {pinEnabled && (
                        <div className="space-y-3 mt-4 pt-4 border-t border-gray-100">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">修改 PIN 码</p>
                            <input type="password" inputMode="numeric" maxLength={4} placeholder="新 PIN（4位数字）"
                                value={newPin1} onChange={e=>setNewPin1(e.target.value.replace(/\D/,'').slice(0,4))}
                                className="w-full p-3 border border-gray-300 rounded-xl outline-none tracking-widest text-center text-2xl focus:ring-2 focus:ring-indigo-500"/>
                            <input type="password" inputMode="numeric" maxLength={4} placeholder="再次确认"
                                value={newPin2} onChange={e=>setNewPin2(e.target.value.replace(/\D/,'').slice(0,4))}
                                className="w-full p-3 border border-gray-300 rounded-xl outline-none tracking-widest text-center text-2xl focus:ring-2 focus:ring-indigo-500"/>
                            <button onClick={changePin} className="w-full bg-indigo-600 active:bg-indigo-700 text-white py-3 rounded-xl font-bold text-sm">更新 PIN</button>
                        </div>
                        )}
                        {/* Fix ⑪: configurable inactive-days threshold */}
                        {canManageOperations && <>
                        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">未到访预警天数</p>
                            <div className="flex gap-2">
                                {[60,90,120,180].map(d=>(
                                    <button key={d} onClick={()=>saveInactiveDays(d)}
                                        className={`flex-1 py-2 rounded-xl text-xs font-bold border ${inactiveDays===d?'bg-indigo-600 text-white border-indigo-600':'bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100'}`}>{d}天</button>
                                ))}
                            </div>
                        </div>
                        {/* P1-A: Package management */}
                        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">充值套餐管理</p>
                            {(db.packages||[]).map(pkg=>(
                                <div key={pkg.id} className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-bold text-gray-700 truncate">{pkg.name}</p>
                                        <p className="text-xs text-gray-400">{pkg.credits}课时 · ${pkg.price}</p>
                                    </div>
                                    <button onClick={()=>{ setPkgEditId(pkg.id); setPkgName(pkg.name); setPkgCredits(String(pkg.credits)); setPkgPrice(String(pkg.price)); }}
                                        className="text-xs text-indigo-600 font-bold px-2 py-1 active:text-indigo-800 flex-shrink-0">编辑</button>
                                    <button onClick={()=>{ if((db.packages||[]).length<=1){showToast('至少保留一个套餐','warn');return;} confirm(`删除套餐「${pkg.name}」？`,()=>{ const nd={...db,packages:(db.packages||[]).filter(p=>p.id!==pkg.id)}; save(nd); showToast('套餐已删除'); },{danger:true,confirmText:'删除'}); }}
                                        className="text-xs text-red-500 font-bold px-2 py-1 active:text-red-700 flex-shrink-0">×</button>
                                </div>
                            ))}
                            {pkgEditId===null ? (
                                <button onClick={()=>{ setPkgEditId(0); setPkgName(''); setPkgCredits(''); setPkgPrice(''); }}
                                    className="w-full border border-dashed border-indigo-300 text-indigo-600 rounded-xl py-2 text-xs font-bold active:bg-indigo-50">+ 添加套餐</button>
                            ) : (
                                <div className="space-y-2 bg-indigo-50 border border-indigo-200 rounded-xl p-3">
                                    <p className="text-xs font-bold text-indigo-700">{pkgEditId===0?'添加套餐':'编辑套餐'}</p>
                                    <input placeholder="套餐名称" value={pkgName} onChange={e=>setPkgName(e.target.value)}
                                        className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                    <div className="grid grid-cols-2 gap-2">
                                        <input type="number" placeholder="课时数" min="1" value={pkgCredits} onChange={e=>setPkgCredits(e.target.value)}
                                            className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                        <input type="number" placeholder="价格 $" min="0" value={pkgPrice} onChange={e=>setPkgPrice(e.target.value)}
                                            className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                    </div>
                                    <div className="flex gap-2">
                                        <button onClick={()=>{ setPkgEditId(null); setPkgName(''); setPkgCredits(''); setPkgPrice(''); }}
                                            className="flex-1 py-2 border border-gray-300 rounded-xl text-xs font-bold text-gray-600 active:bg-gray-100">取消</button>
                                        <button onClick={()=>{
                                            if (!pkgName.trim()||!pkgCredits||!pkgPrice){showToast('请填写完整','warn');return;}
                                            const cr=parseInt(pkgCredits,10), pr=parseFloat(pkgPrice);
                                            if(isNaN(cr)||cr<1||isNaN(pr)||pr<0){showToast('课时数/价格无效','warn');return;}
                                            let newPkgs;
                                            if (pkgEditId===0) {
                                                const newId = Date.now();
                                                newPkgs = [...(db.packages||[]), {id:newId, name:pkgName.trim(), credits:cr, price:pr}];
                                            } else {
                                                newPkgs = (db.packages||[]).map(p=>p.id===pkgEditId?{...p,name:pkgName.trim(),credits:cr,price:pr}:p);
                                            }
                                            save({...db, packages:newPkgs});
                                            setPkgEditId(null); setPkgName(''); setPkgCredits(''); setPkgPrice('');
                                            showToast(pkgEditId===0?'套餐已添加':'套餐已更新');
                                        }} className="flex-1 py-2 bg-indigo-600 active:bg-indigo-700 text-white rounded-xl text-xs font-bold">保存</button>
                                    </div>
                                </div>
                            )}
                        </div>
                        </>}
                        {/* U6: Roster cleanup */}
                        {canManageOperations && (()=>{
                            const cutoffStr = (() => { const d=new Date(); d.setDate(d.getDate()-90); return d.toISOString().slice(0,10); })();
                            const oldKeys = Object.keys(db.rosters||{}).filter(d=>d<cutoffStr);
                            const cleanRosters = () => {
                                if (!oldKeys.length) { showToast('没有需要清理的旧排课'); return; }
                                confirm(`清理 90 天前的排课记录（${oldKeys.length} 条）？\n此操作不影响任何统计数据。`, ()=>{
                                    const nd = {...db, rosters:{...db.rosters}};
                                    oldKeys.forEach(k=>delete nd.rosters[k]);
                                    save(nd);
                                    showToast(`已清理 ${oldKeys.length} 条旧排课`);
                                }, {confirmText:'清理'});
                            };
                            return (
                                <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">排课数据清理</p>
                                    <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 flex items-center gap-2">
                                        <span className="text-xs text-gray-500 flex-1">90天前旧排课</span>
                                        <span className={`text-xs font-bold ${oldKeys.length>0?'text-amber-600':'text-green-600'}`}>{oldKeys.length} 条</span>
                                    </div>
                                    <button onClick={cleanRosters} disabled={oldKeys.length===0}
                                        className="w-full bg-amber-50 active:bg-amber-100 disabled:opacity-40 text-amber-700 border border-amber-200 py-2.5 rounded-xl font-bold text-sm">
                                        🧹 清理旧排课
                                    </button>
                                </div>
                            );
                        })()}
                        {/* F1/F5/F6: 数据体检 + 阈值 + 每周邮件 + 备份恢复 */}
                        {!TENANT_SLUG && (
                            <MaintSection renewTh={renewTh} saveRenewTh={saveRenewTh}
                                onRestored={()=>{ setShowSettings(false); load(); }}/>
                        )}
                        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">学员注册页面</p>
                            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                <span className="text-xs text-gray-500 flex-1 font-mono truncate">{window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`}</span>
                                <button type="button" onClick={()=>copyText(window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`,'链接已复制')}
                                    className="text-xs text-indigo-600 font-bold active:text-indigo-800 flex-shrink-0">复制</button>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                            <button onClick={lockScreen} className="w-full bg-gray-100 active:bg-gray-200 text-gray-700 py-3 rounded-xl font-bold text-sm">{pinEnabled?'🔒 锁定屏幕':'🔓 退出登录'}</button>
                            {/* Mobile-only: sidebar actions inaccessible on phone */}
                            <div className="md:hidden space-y-2 pt-2 border-t border-gray-100">
                                <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wide pb-0.5">快捷操作</p>
                                <button onClick={()=>{load();setShowSettings(false);}} disabled={busy}
                                    className="w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm">🔄 刷新数据</button>
                                {canManageOperations && !TENANT_SLUG && <button onClick={()=>{exportDB();setShowSettings(false);}}
                                    className="w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm">⬇️ 备份导出</button>
                                }
                                <button onClick={()=>{setShowSettings(false);confirm('确认退出登录？下次进入需重新输入密码。', doLogout, {confirmText:'退出登录'});}}
                                    className="w-full bg-red-50 active:bg-red-100 text-red-600 border border-red-200 py-3 rounded-xl font-bold text-sm">🔓 退出登录</button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Mobile top bar (md:hidden) ── */}
            <div className="md:hidden mobile-top-bar fixed top-0 left-0 right-0 z-40 bg-indigo-900 text-white flex items-center px-3 gap-2.5 shadow-lg">
                <img src={tenantLogoUrl} alt={tenantDisplayName} className="h-8 w-auto max-w-[96px] object-contain flex-shrink-0"/>
                <span className="font-bold text-base flex-1 truncate">{tenantDisplayName} CMS</span>
                <button onClick={()=>{setGOpen(true);setGQ('');}} aria-label="搜索"
                    className="w-9 h-9 flex items-center justify-center rounded-lg bg-indigo-800 active:bg-indigo-700 text-indigo-200 text-base flex-shrink-0">🔍</button>
                <button onClick={()=>setShowSettings(true)} aria-label="设置"
                    className="w-9 h-9 flex items-center justify-center rounded-lg bg-indigo-800 active:bg-indigo-700 text-indigo-200 text-base flex-shrink-0">⚙️</button>
            </div>

            {/* Sidebar */}
            {/* P1: standalone(PWA)模式下 iPad 侧栏避开状态栏（浏览器内 env=0 无影响） */}
            <aside className="hidden md:flex w-56 bg-indigo-900 text-white flex-col shadow-xl flex-shrink-0"
                style={{paddingTop:'env(safe-area-inset-top, 0px)'}}>
                <div className="p-4 border-b border-indigo-800 flex items-center gap-2.5">
                    <img src={tenantLogoUrl} alt={tenantDisplayName} className="h-9 w-auto max-w-[96px] object-contain flex-shrink-0"/>
                    <h1 className="hidden md:block text-base font-bold tracking-wide flex-1 truncate">{tenantDisplayName}</h1>
                    <button onClick={()=>{setGOpen(true);setGQ('');}} title="全局搜索 ⌘K"
                        className="hidden md:flex items-center justify-center w-8 h-8 rounded-lg bg-indigo-800 active:bg-indigo-700 text-indigo-300 hover:text-white text-base flex-shrink-0">🔍</button>
                </div>
                <nav className="flex-1 px-2 py-4 space-y-0.5 overflow-y-auto">
                    {NAV.map(({k,i,l,badge}) => (
                        <button key={k} onClick={()=>setTab(k)}
                            className={`w-full text-left px-2 py-3 rounded-xl transition flex items-center gap-2 text-sm min-h-[44px] ${tab===k?'bg-indigo-700 font-bold':'active:bg-indigo-800 text-indigo-200'}`}>
                            <span className="text-base w-5 text-center flex-shrink-0">{i}</span>
                            <span>{l}</span>
                            {k==='dashboard' && analytics.lowBalance.length>0 &&
                                <span className="ml-auto bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">{analytics.lowBalance.length}</span>}
                            {badge>0 &&
                                <span className="ml-auto bg-amber-400 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">{badge}</span>}
                        </button>
                    ))}
                </nav>
                <div className="p-3 border-t border-indigo-800 space-y-1.5" style={{paddingBottom:'calc(env(safe-area-inset-bottom,0px) + 12px)'}}>
                    <div className="text-xs text-green-400 text-center bg-indigo-950 rounded-lg p-1.5 border border-indigo-800">🟢 已连接</div>
                    {db.logs.length > 1000 && (
                        <div className="text-xs text-amber-400 text-center bg-indigo-950 rounded-lg p-1.5 border border-amber-800/40">
                            ⚠️ 日志 {db.logs.length} 条
                        </div>
                    )}
                    {canManageOperations && !TENANT_SLUG && <button onClick={exportDB} className="w-full bg-indigo-700 active:bg-indigo-600 p-2.5 rounded-xl text-xs font-bold min-h-[40px]">⬇️ 备份导出</button>}
                    <button onClick={load} disabled={busy} className="w-full bg-indigo-800 active:bg-indigo-700 p-2.5 rounded-xl text-xs font-bold min-h-[40px]">🔄 刷新</button>
                    <button onClick={()=>setShowSettings(true)} className="w-full bg-indigo-800 active:bg-indigo-700 p-2.5 rounded-xl text-xs font-bold min-h-[40px]">⚙️ 设置</button>
                    <button onClick={()=>confirm('确认退出登录？下次进入需重新输入密码。', doLogout, {confirmText:'退出登录'})}
                        className="w-full bg-indigo-950 active:bg-red-900 p-2.5 rounded-xl text-xs font-bold min-h-[40px] text-indigo-300 active:text-white">🔓 退出登录</button>
                </div>
            </aside>

            {/* Main content */}
            {/* P1: 主内容区在 iPad standalone 下避开状态栏与底部 Home 条
                （inline 样式在手机端会被 .mobile-main-top/.mobile-pb 的 !important 覆盖，互不影响） */}
            <main className="flex-1 overflow-y-auto p-4 md:pt-6 md:p-6 md:pb-0 sl mobile-main-top mobile-pb"
                style={{paddingTop:'calc(1.5rem + env(safe-area-inset-top, 0px))',
                        paddingBottom:'env(safe-area-inset-bottom, 0px)'}}>

{/* ═══ DASHBOARD ══════════════════════════════════════════════ */}
{tab==='dashboard' && (
<div className="anim space-y-5">
    <h2 className="text-xl md:text-2xl font-bold text-gray-800">📊 工作台</h2>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[{l:'客户总数',      v:`${analytics.totalStudents} 人`,             c:'text-gray-800',    action:()=>{setSortBy('date-desc');setFilterBy('all');setTab('students');}},
          {l:'全部剩余课时',  v:`${analytics.totalBalance} 课时`,             c:'text-indigo-600',  action:()=>{setSortBy('bal-desc');setFilterBy('active');setTab('students');}},
          {l:'今日排班',      v:`${TENANT_SLUG ? todayEffectiveCount : analytics.todayRoster.length} 人`,         c:'text-gray-700',    action:()=>setTab('roster')},
          {l:'历史总营收',    v:`$${analytics.totalRevenue.toFixed(0)}`,      c:'text-emerald-600', action:()=>setTab('stats')},
        ].map(({l,v,c,action})=>(
            <button key={l} onClick={action}
                className="bg-white p-4 rounded-2xl shadow-sm border border-indigo-100 text-left w-full active:bg-indigo-50 transition">
                <p className="text-gray-400 text-xs mb-1">{l} <span className="text-indigo-400">→</span></p>
                <p className={`text-2xl font-bold ${c}`}>{v}</p>
            </button>
        ))}
    </div>

    {/* A3: 经营真账（估算）— 现金 vs 已赚 vs 预收负债（v5.3） */}
    {TENANT_SLUG && bizStats && (
        <details className="bg-white rounded-2xl shadow-sm border border-emerald-100">
            <summary className="cursor-pointer px-4 py-3 font-bold text-sm text-gray-800 select-none">📈 经营真账（估算） <span className="text-xs font-normal text-gray-400">已上课 {bizStats.attended_total} 人次 · 加权均价 ${bizStats.avg_price}/课时</span></summary>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-4 pb-4">
                {[
                    ['已上课人次', `${bizStats.attended_total} 次`, `本月 ${bizStats.attended_month} 次`, 'text-gray-800'],
                    ['已赚收入(估)', `$${bizStats.earned_revenue}`, '人次 × 加权均价', 'text-emerald-600'],
                    ['预收未耗(负债)', `$${bizStats.prepaid_liability}`, '剩余课时 × 均价', 'text-amber-600'],
                    ['净现金收入', `$${bizStats.cash_net}`, '充值 − 退款', 'text-indigo-600'],
                ].map(([l,v,sub,c]) => (
                    <div key={l} className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                        <p className="text-[11px] text-gray-400">{l}</p>
                        <p className={`text-xl font-bold ${c}`}>{v}</p>
                        <p className="text-[10px] text-gray-400 mt-0.5">{sub}</p>
                    </div>
                ))}
            </div>
        </details>
    )}

    {/* ⏰ 今日待办 */}
    {(()=>{
        const todoClear   = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) === 0 && s.lastActive);
        const todoLast    = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) === 1);
        const todoRisk    = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.name]||0) === 0);
        const now = new Date(); now.setHours(0,0,0,0); // normalise to midnight so today's birthdays are included
        const weekEnd = new Date(now); weekEnd.setDate(weekEnd.getDate()+7);
        const todoBdayWeek  = db.students.filter(s => { if(!s.birthday||s.archived) return false; const bd=new Date(now.getFullYear(),parseInt(s.birthday.slice(5,7),10)-1,parseInt(s.birthday.slice(8,10),10)); return bd>=now&&bd<=weekEnd; });
        const todoBdayMonth = db.students.filter(s => { if(!s.birthday||s.archived) return false; return s.birthday.slice(5,7)===String(now.getMonth()+1).padStart(2,'0') && !todoBdayWeek.includes(s); });
        const total = todoClear.length + todoLast.length + todoRisk.length + todoBdayWeek.length + todoBdayMonth.length;
        if (!total) return null;
        const names = (arr, max=4) => arr.slice(0,max).map(s=>s.name).join('、') + (arr.length>max?` 等${arr.length}人`:'');
        return (
            <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
                    <p className="font-bold text-gray-700 text-sm">⏰ 今日待办</p>
                    <span className="bg-indigo-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">{total} 项</span>
                </div>
                <div className="divide-y divide-gray-50">
                    {todoClear.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="text-sm font-bold text-red-700">🚨 课时已清零 · {todoClear.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoClear)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('zero');setTab('students');}}
                                className="flex-shrink-0 text-xs text-red-600 font-bold bg-red-50 active:bg-red-100 border border-red-200 px-3 py-1.5 rounded-xl min-h-[34px]">查看 →</button>
                        </div>
                    )}
                    {todoLast.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="text-sm font-bold text-orange-700">⚡ 最后 1 课时 · {todoLast.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoLast)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('low');setTab('students');}}
                                className="flex-shrink-0 text-xs text-orange-600 font-bold bg-orange-50 active:bg-orange-100 border border-orange-200 px-3 py-1.5 rounded-xl min-h-[34px]">查看 →</button>
                        </div>
                    )}
                    {todoRisk.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="text-sm font-bold text-amber-700">⚠️ 流失风险 · {todoRisk.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoRisk)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('tag-risk');setTab('students');}}
                                className="flex-shrink-0 text-xs text-amber-600 font-bold bg-amber-50 active:bg-amber-100 border border-amber-200 px-3 py-1.5 rounded-xl min-h-[34px]">查看 →</button>
                        </div>
                    )}
                    {todoBdayWeek.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="text-sm font-bold text-pink-600">🎂 本周生日 · {todoBdayWeek.length} 人</p>
                                <button onClick={()=>{ const msg=todoBdayWeek.map(s=>`🎂 祝 ${s.name} 生日快乐！愿新的一年里画艺大进，心想事成！`).join('\n'); copyText(msg,'祝福语已复制'); }}
                                    className="flex-shrink-0 text-xs text-pink-600 font-bold bg-pink-50 active:bg-pink-100 border border-pink-200 px-3 py-1.5 rounded-xl min-h-[34px]">复制祝福 →</button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {todoBdayWeek.map(s=>(
                                    <span key={s.id} className="inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700">
                                        {s.name}
                                        {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent('🎂 祝 '+s.name+' 生日快乐！愿新的一年里画艺大进，心想事成！')}`} className="text-pink-400 ml-0.5 active:text-pink-600">💬</a>}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    {todoBdayMonth.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="text-sm font-bold text-pink-400">🎈 本月生日 · {todoBdayMonth.length} 人</p>
                                <button onClick={()=>{ const msg=todoBdayMonth.map(s=>`🎂 祝 ${s.name} 生日快乐！愿新的一年里画艺大进，心想事成！`).join('\n'); copyText(msg,'祝福语已复制'); }}
                                    className="flex-shrink-0 text-xs text-pink-400 font-bold bg-pink-50 active:bg-pink-100 border border-pink-100 px-3 py-1.5 rounded-xl min-h-[34px]">复制祝福 →</button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {todoBdayMonth.map(s=>(
                                    <span key={s.id} className="inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700">
                                        {s.name}
                                        {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent('🎂 祝 '+s.name+' 生日快乐！愿新的一年里画艺大进，心想事成！')}`} className="text-pink-400 ml-0.5 active:text-pink-600">💬</a>}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        );
    })()}

    {/* 待审核提醒 */}
    {(db.pending||[]).length>0 && (
        <button onClick={()=>setTab('pending')}
            className="w-full bg-amber-50 border border-amber-300 rounded-2xl p-4 text-left active:bg-amber-100 transition">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="text-2xl">📋</span>
                    <div>
                        <p className="font-bold text-amber-800 text-sm">有待审核的注册申请</p>
                        <p className="text-xs text-amber-600 mt-0.5">{(db.pending||[]).length} 位学员等待审核，点击前往处理</p>
                    </div>
                </div>
                <span className="bg-amber-500 text-white text-sm font-bold px-3 py-1 rounded-full">{(db.pending||[]).length}</span>
            </div>
        </button>
    )}

    {/* 长期未到访 */}
    {analytics.inactive.length>0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
            <p className="font-bold text-blue-800 mb-2 text-sm">📅 长期未到访 — {analytics.inactive.length} 名学员有余额但超过 {inactiveDays} 天未上课</p>
            <div className="flex flex-wrap gap-2">
                {analytics.inactive.slice(0,12).map(s => (
                    <button key={s.id} onClick={()=>{setTab('students');setSrch(s.name);}}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-100 text-blue-800 border border-blue-200 active:bg-blue-200 min-h-[36px]">
                        {s.name} ({s.balance}课 · {daysSince(s.lastActive)}天前)
                    </button>
                ))}
            </div>
        </div>
    )}

    {/* 低余额预警 */}
    {analytics.lowBalance.length>0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
            <p className="font-bold text-amber-800 mb-2 text-sm">⚡ 课时预警 — {analytics.lowBalance.length} 名学员余额 ≤ 2 课时</p>
            <div className="flex flex-wrap gap-2">
                {analytics.lowBalance.map(s => (
                    <button key={s.id} onClick={()=>{setTab('students');setSrch(s.name);}}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold border min-h-[36px] ${parseInt(s.balance,10)===0?'bg-red-100 text-red-700 border-red-200':'bg-amber-100 text-amber-800 border-amber-200'}`}>
                        {s.name} ({s.balance})
                    </button>
                ))}
            </div>
        </div>
    )}

    {/* Fix #11: Recent logs with date grouping */}
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="bg-gray-50 border-b px-4 py-3 flex justify-between items-center">
            <p className="font-bold text-gray-700 text-sm">最近操作</p>
            <button onClick={()=>setTab('logs')} className="text-indigo-500 text-xs active:text-indigo-700">全部 →</button>
        </div>
        {analytics.recentGroups.length===0 && <EmptyState icon="🧾" main="暂无记录" sub="签到与充值后这里会出现流水"/>}
        {analytics.recentGroups.map(({date, logs}) => (
            <div key={date}>
                <div className="px-4 py-1.5 bg-gray-50 border-b border-t border-gray-100">
                    <span className="text-xs font-bold text-gray-400">{date}</span>
                </div>
                {logs.map(l => (
                    <div key={l.id} className="px-4 py-2.5 flex justify-between items-center border-b border-gray-50 last:border-0">
                        <div>
                            <span className="font-bold text-gray-800 text-sm">{l.studentName}</span>
                            <span className="ml-2 text-gray-400 text-xs">{l.action}</span>
                            {l.payMethod && <span className="ml-1 text-blue-400 text-xs">{l.payMethod}</span>}
                        </div>
                        <span className={`font-bold text-sm ${String(l.change).startsWith('-')?'text-orange-500':(l.change==='0'||l.change===0)?'text-gray-400':'text-green-500'}`}>{l.change}</span>
                    </div>
                ))}
            </div>
        ))}
    </div>
</div>
)}

{/* ═══ ROSTER ═════════════════════════════════════════════════ */}
{tab==='roster' && (
<div className="anim space-y-4">
    <h2 className="text-xl md:text-2xl font-bold text-gray-800">📅 每日排课</h2>
    {/* G1: 生日提醒横幅 */}
    {upcomingBirthdays.length>0 && (
        <div className="bg-gradient-to-r from-pink-50 to-rose-50 border border-pink-200 rounded-2xl p-4">
            <div className="flex items-center justify-between gap-2 flex-wrap mb-2">
                <p className="text-sm font-bold text-rose-700">🎂 近 14 天生日（{upcomingBirthdays.length} 人）</p>
            </div>
            <div className="flex flex-wrap gap-2">
                {upcomingBirthdays.map(({s,in:days,md,age})=>(
                    <button key={s.id} onClick={()=>{
                        const msg = `${s.name} 您好！🎉 Studio 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、画笔生花～ 🎨🎂`;
                        copyText(msg, `已复制给 ${s.name} 的生日祝福`);
                    }} className="bg-white border border-pink-200 active:bg-pink-50 rounded-xl px-3 py-2 text-left">
                        <p className="text-sm font-bold text-gray-800">{s.name} <span className="text-xs font-normal text-rose-400">{days===0?'🎉今天':`${md} (${days}天后)`}</span></p>
                        <p className="text-[11px] text-gray-400">点击复制生日祝福话术</p>
                    </button>
                ))}
            </div>
        </div>
    )}
    {/* A1: 每周课表 — 固定班次自动生成每日排班 */}
    {TENANT_SLUG && (
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <div className="flex justify-between items-center gap-2 flex-wrap">
            <p className="font-bold text-sm text-gray-800">📆 每周课表 <span className="text-xs font-normal text-gray-400">固定班次按周几自动排入当日名单</span></p>
            <button onClick={()=>setSchedEdit({label:'', weekday:new Date().getDay(), startTime:'16:00', durationMinutes:60, capacity:10, studentIds:[]})}
                className="bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[36px]">➕ 新增班次</button>
        </div>
        {schedules.length===0 && !schedEdit && (
            <p className="text-xs text-gray-400">还没有固定班次。例如「周三 16:00 素描班」——保存后每周三会自动出现在当日排班里。</p>
        )}
        {schedules.length>0 && (
            <div className="flex flex-wrap gap-2">
                {schedules.map(sc => (
                    <div key={sc.id} className={`border rounded-xl px-3 py-2 ${sc.weekday===new Date(`${rDate}T12:00:00`).getDay()?'border-indigo-300 bg-indigo-50':'border-gray-200 bg-gray-50'}`}>
                        <p className="text-sm font-bold text-gray-800">{WEEKDAYS[sc.weekday]} {sc.startTime} · {sc.label||'未命名班次'}</p>
                        <div className="flex items-center gap-2 mt-1">
                            <span className="text-[11px] text-gray-500">{sc.students.length}/{sc.capacity} 人 · {sc.durationMinutes} 分钟</span>
                            <button onClick={()=>setSchedEdit({id:sc.id, label:sc.label, weekday:sc.weekday, startTime:sc.startTime, durationMinutes:sc.durationMinutes, capacity:sc.capacity, studentIds:sc.students.map(st=>st.id)})}
                                className="text-[11px] font-bold text-indigo-600 active:text-indigo-800">编辑</button>
                            <button onClick={()=>deleteSchedule(sc)} className="text-[11px] font-bold text-red-500 active:text-red-700">删除</button>
                        </div>
                    </div>
                ))}
            </div>
        )}
        {schedEdit && (
            <div className="border-t border-gray-100 pt-3 space-y-3">
                <div className="grid grid-cols-2 lg:grid-cols-5 gap-2">
                    <div className="col-span-2">
                        <label className="text-xs font-bold text-gray-500 mb-1 block">班次名称</label>
                        <input value={schedEdit.label} onChange={e=>setSchedEdit(p=>({...p,label:e.target.value}))} placeholder="如：周三素描班"
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">周几</label>
                        <select value={schedEdit.weekday} onChange={e=>setSchedEdit(p=>({...p,weekday:Number(e.target.value)}))}
                            className="w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500">
                            {WEEKDAYS.map((w,i)=><option key={i} value={i}>{w}</option>)}
                        </select>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">开始时间</label>
                        <input type="time" value={schedEdit.startTime} onChange={e=>setSchedEdit(p=>({...p,startTime:e.target.value}))}
                            className="w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">容量</label>
                        <input type="number" min="1" value={schedEdit.capacity} onChange={e=>setSchedEdit(p=>({...p,capacity:e.target.value}))}
                            className="w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                    </div>
                </div>
                <div>
                    <label className="text-xs font-bold text-gray-500 mb-1 block">班次学员（{schedEdit.studentIds.length} 人）</label>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                        {schedEdit.studentIds.map(id => {
                            const s = db.students.find(x=>x.id===id);
                            return s ? (
                                <span key={id} className="inline-flex items-center gap-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full px-2.5 py-1 text-xs font-bold">
                                    {s.name}
                                    <button onClick={()=>setSchedEdit(p=>({...p,studentIds:p.studentIds.filter(x=>x!==id)}))} className="text-indigo-400 active:text-red-500">✕</button>
                                </span>
                            ) : null;
                        })}
                    </div>
                    <div className="flex gap-2">
                        <div className="flex-1">
                            <StudentPicker students={sortedAZ.filter(s=>!schedEdit.studentIds.includes(s.id))} value={schedPick} onChange={setSchedPick} placeholder="搜索并添加学员..."/>
                        </div>
                        <button onClick={()=>{ if(!schedPick) return;
                            if (schedEdit.studentIds.includes(schedPick)) { showToast('该学员已在本班次中', 'warn'); setSchedPick(null); return; }
                            const other = schedules.find(sc => sc.id !== schedEdit.id && schedOverlap(sc, schedEdit) && sc.students.some(st=>st.id===schedPick));
                            if (other) showToast(`注意：该学员同时段已在「${other.label}」，已加入但请确认不冲突`, 'warn');
                            setSchedEdit(p=>({...p,studentIds:[...p.studentIds,schedPick]})); setSchedPick(null); }} disabled={!schedPick}
                            className="bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-4 py-2.5 rounded-xl text-xs font-bold">加入班次</button>
                    </div>
                </div>
                <div className="flex gap-2 justify-end">
                    <button onClick={()=>setSchedEdit(null)} className="bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50">取消</button>
                    <button onClick={saveSchedule} disabled={busy}
                        className="bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold">{schedEdit.id?'保存修改':'创建班次'}</button>
                </div>
            </div>
        )}
    </div>
    )}

    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex flex-col lg:flex-row gap-3 items-end">
            <div className="w-full lg:w-64">
                <label className="text-xs font-bold text-gray-500 mb-1 block">课程日期</label>
                <div className="flex gap-1.5 items-center">
                    <button type="button" onClick={()=>setRDate(shiftDate(rDate,-1))}
                        className="px-2.5 py-3 bg-white border border-gray-300 rounded-xl text-xs font-bold text-gray-600 active:bg-gray-50">◀</button>
                    <input type="date" value={rDate} onChange={e=>setRDate(e.target.value)}
                        className="flex-1 px-2 py-3 border border-gray-300 rounded-xl font-bold text-indigo-900 focus:ring-2 focus:ring-indigo-500 outline-none min-w-0"/>
                    <button type="button" onClick={()=>setRDate(shiftDate(rDate,1))}
                        className="px-2.5 py-3 bg-white border border-gray-300 rounded-xl text-xs font-bold text-gray-600 active:bg-gray-50">▶</button>
                    {rDate!==todayISO() && <button type="button" onClick={()=>setRDate(todayISO())}
                        className="px-2.5 py-3 bg-indigo-50 border border-indigo-200 rounded-xl text-xs font-bold text-indigo-700 active:bg-indigo-100 flex-shrink-0">今天</button>}
                </div>
                <p className="text-xs text-gray-400 mt-1">{fmtDate(rDate)} {WEEKDAYS[new Date(`${rDate}T12:00:00`).getDay()]}</p>
            </div>
            <div className="flex-1">
                <label className="text-xs font-bold text-gray-500 mb-1 block">添加学员</label>
                <div className="flex gap-2">
                    <div className="flex-1">
                        <StudentPicker students={availRoster} value={rPick} onChange={setRPick} placeholder="搜索并选择学员..."/>
                    </div>
                    <button onClick={addToRoster} disabled={!rPick||busy}
                        className="bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-xl font-bold text-sm min-h-[50px]">加入</button>
                </div>
            </div>
        </div>
        {/* F4b: 班组模板 */}
        <div className="mt-3 pt-3 border-t border-gray-100 flex gap-2 items-center flex-wrap">
            <span className="text-xs font-bold text-gray-500">📋 班组模板</span>
            <select value={grpSel} onChange={e=>setGrpSel(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded-xl bg-white text-sm font-medium min-h-[40px] outline-none focus:ring-2 focus:ring-indigo-500">
                <option value="">-- 选择模板 --</option>
                {Object.keys(db.groups||{}).sort().map(g => <option key={g} value={g}>{g}（{(db.groups[g]||[]).length}人）</option>)}
            </select>
            <button onClick={applyGroup} disabled={!grpSel||busy}
                className="bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]">套用到当前日期</button>
            <button onClick={saveGroup} disabled={busy}
                className="bg-white text-gray-600 border border-gray-300 active:bg-gray-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]">保存当前为模板</button>
            {grpSel && <button onClick={deleteGroup} disabled={busy}
                className="bg-white text-red-500 border border-red-200 active:bg-red-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]">删除</button>}
            {TENANT_SLUG && grpSel && <button onClick={groupToSchedule} disabled={busy}
                className="bg-indigo-600 active:bg-indigo-700 text-white px-3 py-2 rounded-xl text-xs font-bold min-h-[40px]">📆 转为每周班次</button>}
        </div>
    </div>

    {/* B1: 迷你周视图 — 本周七天一键切换，含每日应到人数 */}
    <div className="grid grid-cols-7 gap-1.5">
        {(() => {
            const anchor = new Date(`${rDate}T12:00:00`);
            const monday = new Date(anchor); monday.setDate(anchor.getDate() - ((anchor.getDay() + 6) % 7));
            return [0,1,2,3,4,5,6].map(i => {
                const d = new Date(monday); d.setDate(monday.getDate() + i);
                const iso = d.toLocaleDateString('en-CA');
                const manual = db.rosters[iso] || [];
                const sched = schedules.filter(sc => sc.weekday === d.getDay()).flatMap(sc => sc.students.map(st => st.id));
                const n = new Set([...sched, ...manual]).size;
                const isSel = iso === rDate, isToday = iso === todayISO();
                return (
                    <button key={iso} type="button" onClick={()=>setRDate(iso)}
                        className={`py-2 rounded-xl border text-center ${isSel?'border-indigo-500 bg-indigo-600 text-white':'border-gray-200 bg-white text-gray-600 active:border-indigo-300'}`}>
                        <p className="text-[10px] opacity-70">{WEEKDAYS[d.getDay()]}{isToday?'·今':''}</p>
                        <p className="text-sm font-bold">{d.getDate()}</p>
                        <p className={`text-[10px] font-bold ${isSel?'text-indigo-100':(n>0?'text-indigo-500':'text-gray-300')}`}>{n>0?`${n}人`:'—'}</p>
                    </button>
                );
            });
        })()}
    </div>

    {/* B1: 当日概览条 — 应到/已签/未签/低余额 */}
    {(() => {
        const valid = dayIds.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived;});
        const done = valid.filter(id=>rosterDone.has(id)).length;
        const low = valid.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&(parseInt(s.balance,10)||0)<=renewTh;}).length;
        if (!valid.length) return null;
        return (
            <div className="flex gap-2 flex-wrap">
                {[['应到', valid.length, 'bg-white border-gray-200 text-gray-700'],
                  ['已签', done, 'bg-green-50 border-green-200 text-green-700'],
                  ['未签', valid.length-done, 'bg-indigo-50 border-indigo-200 text-indigo-700'],
                  ['低余额', low, low>0?'bg-amber-50 border-amber-300 text-amber-700':'bg-white border-gray-200 text-gray-400'],
                ].map(([l,v,cls]) => (
                    <span key={l} className={`px-3 py-1.5 rounded-xl border text-xs font-bold ${cls}`}>{l} {v}</span>
                ))}
            </div>
        );
    })()}

    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="bg-gray-50 border-b px-4 py-3 flex justify-between items-center gap-2 flex-wrap">
            <p className="font-bold text-sm text-gray-800">{fmtDate(rDate)} · {dayIds.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived;}).length} 人{scheduledForDate.length>0 && <span className="text-xs font-normal text-indigo-500 ml-1">（课表 {scheduledForDate.length} 班）</span>}</p>
            <div className="flex gap-2">
                {dayIds.length>0 && (
                    <button onClick={()=>{
                        const ids = dayIds;
                        const lines = ids.map(id=>{const s=db.students.find(x=>x.id===id); return s&&!s.archived?`${s.name}（剩余${s.balance}课时）`:null;}).filter(Boolean);
                        const text = `【今日上课 ${lines.length} 人 - ${fmtDate(rDate)}】\n${lines.join('\n')}`;
                        copyText(text,'日报已复制到剪贴板');
                    }} className="bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[36px]">📋 日报</button>
                )}
                {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.mobile;}) && (
                    <button onClick={()=>{
                        const ids=dayIds;
                        const msg=`提醒：您的上课时间是 ${fmtDate(rDate)}，请准时到课。Studio 期待见到您！`;
                        const lines=ids.map(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.mobile?`${s.name}（${s.mobile}）`:null;}).filter(Boolean);
                        copyText(lines.map(l=>`${l}\n${msg}`).join('\n\n'),`已复制 ${lines.length} 条提醒内容`);
                    }} className="bg-white border border-green-300 active:bg-green-50 text-green-700 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[36px]">💬 批量提醒</button>
                )}
                {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.balance>0;}) && (
                    <button onClick={batchCheckIn} disabled={busy}
                        className="bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[36px]">⚡ 批量签到/消课</button>
                )}
            </div>
        </div>
        <div className="divide-y divide-gray-100">
            {!dayIds.length && <EmptyState icon="📅" main="今日暂无排班" sub={TENANT_SLUG?'可在上方「每周课表」建固定班次，命中当天自动排入':''}/>}
            {/* Fix #3: skip archived students in roster */}
            {dayIds.map(sid => {
                const s = db.students.find(x=>x.id===sid);
                if (!s || s.archived) return null;
                const lowBal = (parseInt(s.balance,10)||0) <= renewTh;   /* A5: 课前低余额预警（v4.5） */
                return (
                    <div key={sid} className={`px-4 py-3 flex items-center hover-row gap-3 min-h-[64px] ${lowBal?'bg-amber-50/60':''}`}>
                        <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                        <div className="flex-1 min-w-0">
                            <p className="font-bold text-gray-900 truncate">{s.name}</p>
                            <p className="text-xs text-gray-400">{s.mobile||'—'}{lowBal && <span className="ml-1 text-amber-600 font-bold">⚡ 余额告急</span>}</p>
                        </div>
                        {lowBal && (
                            <button onClick={()=>{
                                const msg = `${s.name} 家长您好！温馨提醒：当前剩余 ${s.balance} 课时${(parseInt(s.balance,10)||0)===0?'（已用完）':''}，为不影响后续上课，欢迎联系老师续课～ 🎨`;
                                copyText(msg, `已复制给 ${s.name} 的催费提醒`);
                            }} className="px-3 py-2.5 bg-amber-100 active:bg-amber-200 text-amber-700 border border-amber-300 rounded-xl text-xs font-bold min-h-[44px] flex-shrink-0">💬 催费</button>
                        )}
                        {rosterDone.has(s.id) && <span className="text-[11px] font-bold text-green-600 bg-green-50 border border-green-200 rounded-full px-2 py-0.5 flex-shrink-0">✓ 已签</span>}
                        <BalBadge n={s.balance}/>
                        <div className="flex gap-1.5 flex-shrink-0">
                            {s.mobile && (
                                <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent(`提醒：您的上课时间是 ${fmtDate(rDate)}，请准时到课。Studio 期待见到您！`)}`}
                                    className="px-3 py-2.5 bg-green-50 active:bg-green-100 text-green-700 border border-green-200 rounded-xl text-xs font-bold min-h-[44px] flex items-center">💬</a>
                            )}
                            {(db.rosters[rDate]||[]).includes(s.id)
                                ? <button onClick={()=>removeFromRoster(s.id)} disabled={busy}
                                    className="px-3 py-2.5 bg-gray-100 active:bg-gray-200 text-gray-600 rounded-xl text-xs font-bold min-h-[44px] min-w-[44px]">移出</button>
                                : <span className="px-3 py-2.5 text-indigo-500 bg-indigo-50 border border-indigo-100 rounded-xl text-xs font-bold min-h-[44px] flex items-center flex-shrink-0" title="来自每周课表">📆</span>}
                            <button onClick={()=>undoCheckIn(s.id,s.name)} disabled={busy}
                                className="hidden md:block px-3 py-2.5 bg-amber-50 active:bg-amber-100 text-amber-700 border border-amber-200 rounded-xl text-xs font-bold min-h-[44px]">↩</button>
                            {rosterDone.has(s.id)
                                ? <button disabled className="px-4 py-2.5 rounded-xl text-sm font-bold text-green-700 bg-green-50 border border-green-200 min-h-[44px] cursor-default">✓</button>
                                : <button onClick={()=>checkIn(s.id,s.name)} disabled={busy||s.balance<=0}
                                    className={`px-4 py-2.5 rounded-xl text-sm font-bold text-white min-h-[44px] ${s.balance>0?'bg-green-600 active:bg-green-700':'bg-gray-300 cursor-not-allowed'}`}>✅</button>}
                        </div>
                    </div>
                );
            })}
        </div>
    </div>
</div>
)}

{/* ═══ STUDENTS ════════════════════════════════════════════════ */}
{tab==='students' && (
<div className="anim space-y-4">
    <div className="flex justify-between items-center gap-3 flex-wrap">
        <h2 className="text-xl md:text-2xl font-bold text-gray-800">学员档案 ({sortedFiltered.length})</h2>
        <div className="flex gap-2">
            {canManageOperations && <button onClick={exportStudentsCSV}
                className="bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-4 py-2.5 rounded-xl font-bold text-sm min-h-[44px]">⬇️ CSV</button>
            }
            {canWriteStudents && <button onClick={()=>setTab('new_student')}
                className="bg-indigo-600 active:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md min-h-[44px]">➕ 新建</button>
            }
        </div>
    </div>

    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <input type="text" placeholder="🔍 搜索姓名 / 电话 / 微信 / 邮箱...（回车打开唯一匹配）" value={srch} onChange={e=>setSrch(e.target.value)}
            onKeyDown={e=>{ if (e.key==='Enter' && sortedFiltered.length===1) { setSelS(sortedFiltered[0]); setEditP(false); } }}
            className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
        <div className="overflow-x-auto -mx-1 px-1 pb-1"><div className="flex gap-2 items-center" style={{minWidth:'max-content'}}>
            <select value={sortBy} onChange={e=>setSortBy(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none font-medium text-sm min-h-[40px] flex-shrink-0">
                <option value="name-az">名 A→Z</option>
                <option value="name-za">名 Z→A</option>
                <option value="last-az">姓 A→Z</option>
                <option value="last-za">姓 Z→A</option>
                <option value="bal-desc">课时 高→低</option>
                <option value="bal-asc">课时 低→高</option>
                <option value="date-desc">最近活跃</option>
            </select>
            {[['all','全部'],['active','有余额'],['low',`低余额≤${renewTh}`],['zero','已清零'],['archived','归档库'],['tag-hot','🔥 活跃'],['tag-low','💤 低频'],['tag-risk','⚠️ 流失风险']].map(([v,l]) => (
                <button key={v} onClick={()=>setFilterBy(v)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold border min-h-[40px] transition flex-shrink-0 ${filterBy===v?'bg-indigo-600 text-white border-indigo-600':'bg-white text-gray-600 border-gray-300 active:border-indigo-300'}`}>{l}{filterBy===v?` · ${sortedFiltered.length}`:''}</button>
            ))}
            {(filterBy!=='all'||srch) && <button onClick={()=>{setFilterBy('all');setSrch('');}}
                className="px-3 py-2 rounded-xl text-xs font-bold border border-red-200 text-red-500 bg-white active:bg-red-50 min-h-[40px] flex-shrink-0">✕ 清除</button>}
        </div></div>
    </div>

    {/* F5: 待续课看板 — 低余额筛选下提供一键复制提醒话术 */}
    {canWriteCredits && filterBy==='low' && sortedFiltered.length>0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
            <p className="text-sm font-bold text-orange-700">⚡ 待续课学员 {sortedFiltered.length} 人（余额 ≤{renewTh} 节）</p>
            <button onClick={()=>{
                const lines = sortedFiltered.map(s=>`${s.name} 您好～您在 Studio 的剩余课时为 ${s.balance} 节，为不影响后续上课安排，欢迎随时联系老师续课哦 🎨`);
                copyText(lines.join('\n\n'), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
            }} className="bg-orange-600 active:bg-orange-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[40px]">📋 复制全部提醒话术</button>
        </div>
    )}
    {!sortedFiltered.length && <EmptyState icon="🔍" main="无匹配学员" sub="试试调整搜索词或筛选条件"/>}
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {sortedFiltered.map(s => (
            <div key={s.id} className={`bg-white rounded-2xl p-4 shadow-sm border hover-row transition flex flex-col justify-between print-card ${s.archived?'border-gray-200 opacity-70':parseInt(s.balance,10)===0?'border-red-100':parseInt(s.balance,10)<=2?'border-orange-100':'border-gray-100'}`}>
                <div>
                    <div className="flex justify-between items-start mb-2 gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                            <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                            <div className="min-w-0">
                                <h3 className="font-bold text-gray-800 break-words leading-snug">{s.name}</h3>
                                {s.archived && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 rounded mt-0.5 inline-block">归档</span>}
                            </div>
                        </div>
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                            <BalBadge n={s.balance}/>
                            {(()=>{const t=getTag(s); return t?<span className={`text-xs px-2 py-0.5 rounded-full font-bold ${t.cls}`}>{t.icon} {t.label}</span>:null;})()}
                        </div>
                    </div>
                    <p className="text-gray-400 text-sm">📞 {s.mobile||'—'}</p>
                    {s.email && <p className="text-gray-400 text-sm">✉️ {s.email}</p>}
                    {s.artStyle && <p className="text-gray-400 text-sm">🎨 {s.artStyle}</p>}
                    <p className="text-gray-400 text-sm mt-0.5">🗓 {fmtDate(s.lastActive)}{daysSince(s.lastActive)<9999?` · ${daysSince(s.lastActive)}天前`:''}</p>
                </div>
                <div className="flex gap-2 mt-3">
                    <button onClick={()=>{setSelS(s);setEditP(false);}}
                        className="flex-1 bg-gray-50 active:bg-gray-100 border border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-bold min-h-[44px]">详情</button>
                    {!s.archived && (<>
                        {canWriteCredits && <button onClick={()=>{setTuStu(s.id);setTab('topup');}}
                            title="快速充值" className="px-3.5 py-3 rounded-xl text-base font-bold bg-emerald-50 active:bg-emerald-100 text-emerald-700 border border-emerald-200 min-h-[44px]">💰</button>
                        }
                        {canManageOperations && <button onClick={()=>scheduleStudentToday(s)} disabled={busy}
                            className="flex-1 py-3 rounded-xl text-sm font-bold text-white min-h-[44px] bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300">📅 {isStudentScheduledOn(s.id,todayISO())?'去排课':'排课'}</button>
                        }
                    </>)}
                </div>
            </div>
        ))}
    </div>
    {/* U7: Back-to-top button when list > 15 */}
    {sortedFiltered.length > 15 && (
        <button onClick={()=>{ const m=document.querySelector('main'); if(m) m.scrollTo({top:0,behavior:'smooth'}); else window.scrollTo({top:0,behavior:'smooth'}); }}
            className="fixed bottom-24 right-4 md:bottom-8 z-40 w-11 h-11 bg-indigo-600 active:bg-indigo-700 text-white rounded-full shadow-lg flex items-center justify-center text-lg"
            title="回到顶部" aria-label="回到顶部">↑</button>
    )}
</div>
)}

{/* ═══ NEW STUDENT ════════════════════════════════════════════ */}
{tab==='new_student' && (
<div className="anim bg-white rounded-2xl p-6 max-w-xl mx-auto shadow-sm border border-gray-100">
    <h2 className="text-xl md:text-2xl font-bold mb-5 text-gray-800">➕ 新建学员档案</h2>
    <form onSubmit={handleAddStudent} className="space-y-4">
        {/* Photo */}
        <div>
            <label className="text-sm font-bold text-gray-500 mb-2 block">照片 Photo <span className="font-normal text-gray-400">选填</span></label>
            <PhotoUploader value={formPhoto} onChange={setFormPhoto}/>
        </div>
        {/* Name */}
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">First Name (名) *</label>
                <input required name="firstName" placeholder="如 Holly"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">Last Name (姓) <span className="font-normal text-gray-400">选填</span></label>
                <input name="lastName" placeholder="如 Chen"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
        {/* Contact + Balance */}
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">电话</label>
                <input name="mobile" placeholder="04xx xxx xxx"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">初始课时</label>
                <input name="balance" type="number" min="0" defaultValue="0"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">微信号 <span className="font-normal text-gray-400">选填</span></label>
                <input name="wechat" placeholder="如 wechat_id"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">邮箱 <span className="font-normal text-gray-400">选填</span></label>
                <input name="email" type="email" placeholder="example@email.com"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
        </div>
	        {/* Tenant-configured student preferences */}
	        <details className="border border-gray-200 rounded-xl overflow-hidden">
	            <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100">
	                {preferenceProfile().title} <span className="font-normal text-gray-400">选填 / Optional</span>
	            </summary>
	            <div className="p-4 space-y-3">
	                {preferenceProfile().fields.map(field => (
	                    <div key={field.key}>
	                        <label className="text-sm font-bold text-gray-500 mb-1 block">{field.label}</label>
	                        <input name={`pref_${field.key}`} placeholder={field.placeholder}
	                            className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
	                    </div>
	                ))}
	            </div>
	        </details>
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1 block">生日 <span className="font-normal text-gray-400">选填</span></label>
            <input type="date" name="birthday" min="1920-01-01" max="2099-12-31"
                className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
        </div>
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1 block">备注</label>
            <textarea name="remark" rows="3" placeholder="备注信息..."
                className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none"></textarea>
        </div>
        <div className="flex gap-3 pt-2">
            <button type="submit" disabled={busy}
                className="flex-1 bg-indigo-600 active:bg-indigo-700 text-white py-3.5 rounded-xl font-bold text-sm shadow-md min-h-[52px]">确认建档</button>
            <button type="button" onClick={()=>{setTab('students');setFormPhoto('');}}
                className="px-6 py-3.5 bg-gray-100 active:bg-gray-200 text-gray-700 rounded-xl font-bold text-sm min-h-[52px]">取消</button>
        </div>
    </form>
</div>
)}

{/* ═══ PENDING ════════════════════════════════════════════════ */}
{tab==='pending' && (
<div className="anim space-y-4">
    <h2 className="text-xl md:text-2xl font-bold text-gray-800">📋 待审核注册 ({(db.pending||[]).length})</h2>
    {!(db.pending||[]).length && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
            <p className="text-4xl mb-3">✅</p>
            <p className="font-bold text-gray-600">暂无待审核申请</p>
            <p className="text-sm text-gray-400 mt-1">学员通过注册页面提交后会显示在这里</p>
        </div>
    )}
    {(db.pending||[]).map(pen => {
        const fullName = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
        return (
            <div key={pen.id} className="bg-white rounded-2xl shadow-sm border border-amber-200 p-5 space-y-4">
                <div className="flex items-start gap-4">
                    {pen.photo
                        ? <img src={mediaSrc(pen.photo)} className="w-16 h-16 rounded-full object-cover flex-shrink-0 border-2 border-indigo-100" alt={fullName}/>
                        : <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-2xl font-bold text-indigo-600 flex-shrink-0">{(pen.firstName||'?')[0].toUpperCase()}</div>
                    }
                    <div className="flex-1 min-w-0">
                        <p className="text-lg font-bold text-gray-800">{fullName}</p>
                        <p className="text-sm text-gray-500">📞 {pen.mobile||'—'}{pen.wechat ? ` · 💬 ${pen.wechat}` : ''}{pen.email ? ` · ✉️ ${pen.email}` : ''}</p>
                        {pen.birthday && <p className="text-xs text-pink-500 mt-0.5">🎂 {fmtDate(pen.birthday)}</p>}
                        {pen.mobile && (() => {
                            const normP = p => (p||'').replace(/[\s\-\(\)]+/g,'');
                            const match = db.students.filter(s=>!s.archived && normP(s.mobile)===normP(pen.mobile));
                            return match.length > 0 ? <p className="text-xs text-blue-500 mt-0.5">📱 此电话已有学员：{match.map(s=>s.firstName&&s.lastName?`${s.firstName} ${s.lastName}`:s.name||'').join('、')}</p> : null;
                        })()}
                        <p className="text-xs text-gray-400 mt-0.5">提交时间: {pen.submittedAt||'—'} · 来源: {pen.source==='portal'?'门户网站':'快速报名'} · 状态: {pen.status||'pending'}</p>
                    </div>
                </div>
	                {preferenceRows(pen).length > 0 && (
	                    <div className="grid grid-cols-2 gap-2 text-sm">
	                        {preferenceRows(pen).map(row => (
	                            <div key={row.key} className="bg-gray-50 rounded-2xl p-4 border border-gray-100">
	                                <p className="text-xs text-gray-400 mb-1">{row.label}</p>
	                                <p className="font-bold text-gray-700 text-sm">{row.value}</p>
	                            </div>
	                        ))}
	                    </div>
	                )}
                {pen.message && (
                    <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-gray-700">
                        <p className="text-xs text-amber-500 font-bold mb-1">💬 留言</p>
                        <p>{pen.message}</p>
                    </div>
                )}
                <div className="bg-blue-50 border border-blue-100 rounded-2xl p-3 flex flex-wrap items-end gap-2">
                    <div>
                        <label className="text-xs font-bold text-blue-700 mb-1 block">下次跟进</label>
                        <input type="date" value={followUpDates[pen.id]||''}
                            onChange={e=>setFollowUpDates(p=>({...p,[pen.id]:e.target.value}))}
                            className="px-3 py-2 border border-blue-200 rounded-xl text-sm"/>
                    </div>
                    <button onClick={()=>advanceRegistration(pen.id,'contacted')} disabled={busy}
                        className="px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm">已联系</button>
                    <button onClick={()=>advanceRegistration(pen.id,'trial_booked')} disabled={busy}
                        className="px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm">已约试听</button>
                    <button onClick={()=>advanceRegistration(pen.id,'waiting')} disabled={busy}
                        className="px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm">继续跟进</button>
                </div>
                <div className="flex items-end gap-3 pt-2 border-t border-gray-100">
                    <div className="flex-1">
                        <label className="text-xs font-bold text-gray-500 mb-1 block">初始课时数</label>
                        <input type="number" min="0" placeholder="0"
                            value={approveCredits[pen.id]??''}
                            onChange={e=>setApproveCredits(p=>({...p,[pen.id]:e.target.value}))}
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl font-bold text-xl focus:ring-2 focus:ring-indigo-500 outline-none text-indigo-700"/>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                        <button onClick={()=>rejectStudent(pen.id)} disabled={busy}
                            className="px-4 py-2.5 bg-red-50 active:bg-red-100 text-red-700 border border-red-200 font-bold rounded-xl text-sm min-h-[44px]">❌ 拒绝</button>
                        <button onClick={()=>approveStudent(pen.id)} disabled={busy}
                            className="px-5 py-2.5 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm min-h-[44px]">✅ 批准建档</button>
                    </div>
                </div>
            </div>
        );
    })}
</div>
)}

{/* ═══ TOPUP ══════════════════════════════════════════════════ */}
{tab==='topup' && (
<div className="anim bg-white rounded-2xl shadow-sm border border-gray-100 p-6 max-w-2xl mx-auto">
    <h2 className="text-xl md:text-2xl font-bold mb-4 text-gray-800">💰 充值 & 结算</h2>
    {TENANT_SLUG && (
        <div className="flex gap-2 mb-5">
            {[['topup','💰 充值'],['refund','💸 退款退课']].map(([m,l]) => (
                <button key={m} type="button" onClick={()=>setSettleMode(m)}
                    className={`flex-1 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${settleMode===m?(m==='refund'?'border-red-400 bg-red-50 text-red-700':'border-indigo-500 bg-indigo-100 text-indigo-900'):'border-gray-200 bg-white text-gray-500 active:border-indigo-300'}`}>{l}</button>
            ))}
        </div>
    )}
    <form onSubmit={settleMode==='refund'?handleRefund:handleTopUp} className="space-y-5">
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1.5 block">选择学员</label>
            <StudentPicker students={sortedAZ} value={tuStu} onChange={setTuStu} placeholder="搜索学员姓名..."/>
            {tuStu && (()=>{const s=db.students.find(x=>x.id===tuStu); return s?(
                <div className="mt-2 flex items-center gap-3 bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3">
                    <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                    <div className="flex-1 min-w-0">
                        <p className="font-bold text-gray-800 text-sm truncate">{s.name}</p>
                        <p className="text-xs text-gray-500">{s.mobile||'—'}{s.wechat ? ` · 💬 ${s.wechat}` : ''}</p>
                    </div>
                    <div className="text-right flex-shrink-0">
                        <p className="text-xs text-gray-400">当前余额</p>
                        <BalBadge n={s.balance}/>
                    </div>
                </div>
            ):null;})()}
            {tuStu && (()=>{
                /* A4: 最近 3 笔充值/退款流水，动手前先核对（v4.7 + v5.5） */
                const s = db.students.find(x=>x.id===tuStu);
                const recent = !s ? [] : db.logs.filter(l =>
                    (l.studentId===s.id || (!l.studentId && l.studentName===s.name)) &&
                    (l.action==='充值购课' || l.action==='退款退课')).slice(0,3);
                if (!recent.length) return null;
                return (
                    <div className="mt-2 border border-gray-100 rounded-xl divide-y divide-gray-50 text-xs">
                        {recent.map(l => (
                            <div key={l.id} className="flex items-center justify-between px-3 py-2">
                                <span className={l.action==='退款退课'?'text-red-500 font-bold':'text-gray-600 font-bold'}>{l.action}</span>
                                <span className={`font-bold ${l.action==='退款退课'?'text-red-500':'text-gray-700'}`}>{String(l.change)} 课时 · ${l.feePaid||0}</span>
                                <span className="text-gray-400">{String(l.date).split(',')[0]}</span>
                            </div>
                        ))}
                    </div>
                );
            })()}
        </div>
        {settleMode==='refund' ? (
        <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">退课节数 *</label>
                    <input type="number" min="1" required value={rfCr} onChange={e=>setRfCr(e.target.value)}
                        className="w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"/>
                </div>
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">退款金额 (AUD) *</label>
                    <input type="number" min="0" step="0.01" required value={rfAmt} onChange={e=>setRfAmt(e.target.value)}
                        className="w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"/>
                </div>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1.5 block">退款方式</label>
                <div className="flex gap-2 flex-wrap">
                    {['现金','微信','银行转账','其他'].map(pm => (
                        <button key={pm} type="button" onClick={()=>setTuPay(pm)}
                            className={`px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay===pm?'border-red-400 bg-red-50 text-red-700':'border-gray-200 bg-white text-gray-600 active:border-red-300'}`}>{pm}</button>
                    ))}
                </div>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">退款原因 *</label>
                <input type="text" required value={rfReason} onChange={e=>setRfReason(e.target.value)} placeholder="如 搬家、时间冲突、课程不合适..."
                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-400 outline-none text-sm"/>
            </div>
            <p className="text-xs text-gray-400 bg-red-50 border border-red-100 rounded-xl px-3 py-2">退款金额将以负数计入营收（净额自动核减）；退课节数直接从剩余课时扣减。此操作会记入账本与操作日志。</p>
        </div>
        ) : (
        <div>
            <label className="text-sm font-bold text-gray-500 mb-1.5 block">套餐快选</label>
            <div className="grid grid-cols-2 lg:grid-cols-3 gap-2 mb-4">
                {(db.packages||[]).map(pkg => (
                    <button key={pkg.id} type="button" onClick={()=>{
                        if (tuPkg===String(pkg.id)) { setTuCr(''); setTuFee(''); setTuPkg(''); }
                        else { setTuCr(String(pkg.credits)); setTuFee(String(pkg.price)); setTuPkg(String(pkg.id)); }
                    }}
                        className={`py-3 px-2 border-2 rounded-xl text-sm font-bold min-h-[50px] ${tuPkg===String(pkg.id)?'border-indigo-500 bg-indigo-100 text-indigo-900':'border-indigo-200 bg-indigo-50 active:bg-indigo-100 text-indigo-800'}`}>
                        {pkg.name}<br/><span className="font-normal text-xs">{pkg.credits}课时 · ${pkg.price}</span>
                    </button>
                ))}
            </div>
            <div className="grid grid-cols-2 gap-3 mb-4">
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">课时数 *</label>
                    <input type="number" name="credits" min="1" required value={tuCr} onChange={e=>setTuCr(e.target.value)}
                        className="w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                </div>
                <div>
                    <label className="text-sm font-bold text-gray-500 mb-1 block">实收金额 (AUD) *</label>
                    <input type="number" name="fee" min="0" step="0.01" required value={tuFee} onChange={e=>setTuFee(e.target.value)}
                        className="w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none text-green-700"/>
                </div>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1.5 block">付款方式</label>
                <div className="flex gap-2 flex-wrap">
                    {['现金','微信','银行转账','其他'].map(pm => (
                        <button key={pm} type="button" onClick={()=>setTuPay(pm)}
                            className={`px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay===pm?'border-indigo-500 bg-indigo-100 text-indigo-900':'border-gray-200 bg-white text-gray-600 active:border-indigo-300'}`}>{pm}</button>
                    ))}
                </div>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">备注 <span className="font-normal text-gray-400">选填</span></label>
                <input type="text" name="tuRemark" placeholder="如 节假日赠课、补偿调课..."
                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"/>
            </div>
        </div>
        )}
        <button type="submit" disabled={busy||!tuStu}
            className={`w-full disabled:bg-gray-300 text-white py-4 rounded-xl font-bold text-sm shadow-xl min-h-[56px] ${settleMode==='refund'?'bg-red-500 active:bg-red-600':'bg-indigo-600 active:bg-indigo-700'}`}>
            {busy?'处理中...':(settleMode==='refund'?'确认退款退课':'确认收款并入账')}
        </button>
    </form>
</div>
)}

{/* ═══ LOGS ═══════════════════════════════════════════════════ */}
{tab==='logs' && (
<div className="anim space-y-4">
    <h2 className="text-xl md:text-2xl font-bold text-gray-800">📜 操作日志</h2>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
                <StudentPicker students={sortedAZ} value={lStu} onChange={setLStu} placeholder="🔍 精确筛选学员..." showBal={false}/>
            </div>
            <select value={lAct} onChange={e=>setLAct(e.target.value)}
                className="px-3 py-3 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none min-h-[50px]">
                <option value="">全部操作</option>
                {logActions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
        </div>
        {!lStu && (
            <input type="text" placeholder="🔍 或输入关键字搜索..." value={lSrch} onChange={e=>setLSrch(e.target.value)}
                className="w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"/>
        )}
        {/* Quick date presets */}
        <div className="flex flex-wrap gap-2">
            {[
                {l:'本月',    fn:()=>{ const n=new Date(); const y=n.getFullYear(),m=String(n.getMonth()+1).padStart(2,'0'); setLDateFrom(`${y}-${m}-01`); setLDateTo(`${y}-${m}-${String(new Date(y,n.getMonth()+1,0).getDate()).padStart(2,'0')}`); }},
                {l:'近30天',  fn:()=>{ const t=new Date(),f=new Date(t-30*864e5); setLDateFrom(f.toLocaleDateString('en-CA')); setLDateTo(t.toLocaleDateString('en-CA')); }},
                {l:'本年',    fn:()=>{ const y=new Date().getFullYear(); setLDateFrom(`${y}-01-01`); setLDateTo(`${y}-12-31`); }},
            ].map(({l,fn})=>(
                <button key={l} type="button" onClick={fn}
                    className="px-3 py-1.5 bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold min-h-[36px]">{l}</button>
            ))}
        </div>
        <div className="flex flex-wrap items-center gap-3">
            <div className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm w-full sm:w-auto">
                <span className="font-medium text-gray-500">日期范围</span>
                <div className="flex items-center gap-2">
                    <input type="date" value={lDateFrom} onChange={e=>setLDateFrom(e.target.value)}
                        className="flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px] text-sm"/>
                    <span className="text-gray-400 text-xs">至</span>
                    <input type="date" value={lDateTo} onChange={e=>setLDateTo(e.target.value)}
                        className="flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px] text-sm"/>
                </div>
            </div>
            {(lStu||lSrch||lAct||lDateFrom||lDateTo) && (
                <button onClick={()=>{setLStu(null);setLSrch('');setLAct('');setLDateFrom('');setLDateTo('');}}
                    className="px-3 py-2 bg-gray-100 active:bg-gray-200 text-gray-500 rounded-xl text-xs font-bold min-h-[40px]">✕ 清除</button>
            )}
            <span className="text-sm text-gray-400">{filteredLogs.length} 条</span>
            {canManageOperations && <button onClick={exportLogsCSV}
                className="ml-auto bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-xs min-h-[40px]">⬇️ CSV</button>
            }
        </div>
    </div>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead><tr className="border-b-2 border-gray-100 text-gray-400 text-xs">
                    <th className="p-3 font-bold">时间</th>
                    <th className="p-3 font-bold">学员</th>
                    <th className="p-3 font-bold">操作</th>
                    <th className="p-3 font-bold">变动</th>
                </tr></thead>
                <tbody>
                    {pagedLogs.map(l => (
                        <tr key={l.id} className="border-b border-gray-50 hover-row">
                            <td className="p-3 text-gray-400 text-xs font-mono whitespace-nowrap">{l.date}</td>
                            <td className="p-3 font-bold text-gray-800 text-sm">{l.studentName}</td>
                            <td className="p-3">
                                <span className={`px-1.5 py-0.5 rounded text-xs font-bold border ${l.action==='充值购课'?'bg-green-100 text-green-700 border-green-200':l.action==='上课签到'?'bg-indigo-100 text-indigo-700 border-indigo-200':l.action&&l.action.includes('手动')?'bg-orange-100 text-orange-700 border-orange-200':l.action&&(l.action.includes('拒绝')||l.action.includes('删除'))?'bg-red-100 text-red-700 border-red-200':'bg-gray-100 text-gray-700 border-gray-200'}`}>{l.action}</span>
                                {l.payMethod && <span className="ml-1 bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-xs">{l.payMethod}</span>}
                                <span className="text-xs text-gray-400 block mt-0.5">{l.note}</span>
                                {l.feePaid>0 && <span className="text-xs text-green-600 font-bold">${l.feePaid}</span>}
                            </td>
                            <td className={`p-3 font-bold ${String(l.change).startsWith('-')?'text-orange-500':(l.change==='0'||l.change===0)?'text-gray-400':'text-green-500'}`}>{l.change}</td>
                        </tr>
                    ))}
                    {!pagedLogs.length && <tr><td colSpan="4" className="p-8 text-center text-gray-400">无记录</td></tr>}
                </tbody>
            </table>
        </div>
        {/* Fix #10: first/last page buttons */}
        {logPageCount>1 && (
            <div className="p-3 border-t flex items-center justify-center gap-1.5">
                <button disabled={lPage===1} onClick={()=>setLPage(1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]">«</button>
                <button disabled={lPage===1} onClick={()=>setLPage(p=>p-1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]">‹</button>
                <span className="text-sm text-gray-600 px-2">{lPage} / {logPageCount}</span>
                <button disabled={lPage===logPageCount} onClick={()=>setLPage(p=>p+1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]">›</button>
                <button disabled={lPage===logPageCount} onClick={()=>setLPage(logPageCount)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[40px]">»</button>
            </div>
        )}
    </div>
</div>
)}

{/* ═══ STATS ══════════════════════════════════════════════════ */}
{tab==='stats' && (
<div className="anim space-y-5">
    <h2 className="text-xl md:text-2xl font-bold text-gray-800">📈 商业洞察</h2>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gradient-to-br from-indigo-500 to-indigo-700 p-4 rounded-2xl text-white shadow-md">
            <p className="text-indigo-100 text-xs mb-1">历史总营收</p><p className="text-2xl md:text-3xl font-bold">${analytics.totalRevenue.toFixed(0)}</p></div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"><p className="text-gray-400 text-xs mb-1">建档学员</p><p className="text-2xl md:text-3xl font-bold text-gray-800">{analytics.totalStudents}</p></div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"><p className="text-gray-400 text-xs mb-1">累计消课</p><p className="text-2xl md:text-3xl font-bold text-indigo-600">{analytics.totalCheckins}</p></div>
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"><p className="text-gray-400 text-xs mb-1">课时资产池</p><p className="text-2xl md:text-3xl font-bold text-emerald-600">{analytics.totalBalance}</p></div>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
                <p className="font-bold text-gray-700 text-sm">近 12 个月营收 (AUD)</p>
                {sStu && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg">全局数据</span>}
            </div>
            <div className="overflow-x-auto -mx-1 px-1"><div style={{minWidth:'580px'}}>
            <BarChart items={analytics.chart12.map(d=>({v:d.rev,l:d.l}))} color="#6366f1" h={130}/>
            </div></div>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
                <p className="font-bold text-gray-700 text-sm">近 12 个月消课次数</p>
                {sStu && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg">全局数据</span>}
            </div>
            <div className="overflow-x-auto -mx-1 px-1"><div style={{minWidth:'580px'}}>
            <BarChart items={analytics.chart12.map(d=>({v:d.ci,l:d.l}))} color="#10b981" h={130}/>
            </div></div>
        </div>
    </div>
    {payBreakdown.length>0 && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <p className="font-bold text-gray-700 text-sm mb-3">付款方式分布</p>
            <div className="flex flex-wrap gap-3">
                {payBreakdown.map(([pm,d]) => (
                    <div key={pm} className="bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 text-center min-w-[90px]">
                        <p className="text-xs text-gray-400 mb-1">{pm}</p>
                        <p className="font-bold text-gray-800">${d.revenue.toFixed(0)}</p>
                        <p className="text-xs text-gray-400">{d.count} 次</p>
                    </div>
                ))}
            </div>
        </div>
    )}
    {/* F7: 经营月报 */}
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
        <div className="flex items-center justify-between mb-3">
            <p className="font-bold text-gray-700 text-sm">📊 经营月报（近 6 个月）</p>
            <button onClick={exportBizCSV}
                className="bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[36px]">⬇️ 导出 CSV</button>
        </div>
        <div className="overflow-x-auto"><table className="w-full text-sm" style={{minWidth:'480px'}}>
            <thead><tr className="text-xs text-gray-400 border-b">
                <th className="text-left py-2 px-2">月份</th><th className="text-right px-2">营收</th>
                <th className="text-right px-2">充值</th><th className="text-right px-2">消课</th>
                <th className="text-right px-2">新学员</th></tr></thead>
            <tbody>{bizReport.rows.map(r=>(
                <tr key={r.k} className="border-b border-gray-50">
                    <td className="py-2 px-2 font-bold text-gray-700">{r.label}</td>
                    <td className="text-right px-2 font-bold text-indigo-700">${r.rev.toFixed(0)}</td>
                    <td className="text-right px-2 text-gray-600">{r.topups} 笔</td>
                    <td className="text-right px-2 text-gray-600">{r.ci} 次</td>
                    <td className="text-right px-2 text-gray-600">{r.newStu||'—'}</td>
                </tr>))}</tbody>
        </table></div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
            <div className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                <p className="text-xs font-bold text-gray-500 mb-2">课包销量排行（历史累计）</p>
                {bizReport.pkgRank.length===0 && <p className="text-xs text-gray-400">暂无充值记录</p>}
                {bizReport.pkgRank.slice(0,5).map(([name,d],i)=>(
                    <div key={name} className="flex items-center justify-between py-1 text-sm">
                        <span className="text-gray-700">{i+1}. {name}</span>
                        <span className="font-bold text-gray-800">${d.revenue.toFixed(0)} <span className="text-xs text-gray-400 font-normal">/ {d.count} 笔</span></span>
                    </div>))}
            </div>
            <div className="bg-gray-50 border border-gray-100 rounded-xl p-3">
                <p className="text-xs font-bold text-gray-500 mb-2">消课节奏（近 180 天）</p>
                <p className="text-2xl font-bold text-emerald-600">{bizReport.avgGap ? bizReport.avgGap.toFixed(1) : '—'} <span className="text-sm font-normal text-gray-500">天/次</span></p>
                <p className="text-xs text-gray-400 mt-1">规律上课学员 {bizReport.regularStu} 人的平均上课间隔。间隔变长 = 出勤率下降的早期信号</p>
            </div>
        </div>
    </div>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="bg-gray-50 border-b p-4 space-y-3">
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
                <h3 className="font-bold text-gray-800">财务明细报表</h3>
                <div className="flex items-center gap-2">
                    <button onClick={exportRevenueCSV}
                        className="bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-sm min-h-[40px]">⬇️ CSV</button>
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-xl">
                        {[['monthly','月度'],['yearly','年度'],['custom','自定义']].map(([v,l]) => (
                            <button key={v} onClick={()=>setSPeriod(v)} className={`px-3 py-2 rounded-lg text-sm font-bold min-h-[40px] ${sPeriod===v?'bg-white shadow text-indigo-700':'text-gray-500'}`}>{l}</button>
                        ))}
                    </div>
                </div>
            </div>
            <div className="flex flex-wrap gap-3 items-center">
                {sPeriod==='monthly' && (
                    <select value={sYear} onChange={e=>setSYear(e.target.value)}
                        className="px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-400 outline-none text-sm min-h-[40px]">
                        <option value="all">所有年份</option>
                        {analytics.availYears.map(y=><option key={y} value={y}>{y}年</option>)}
                    </select>
                )}
                {sPeriod==='custom' && (
                    /* Fix ⑩: type="month" gives YYYY-MM value, matches our monthKey format exactly */
                    <div className="flex flex-col sm:flex-row sm:items-center gap-2 text-sm">
                        <span className="font-medium text-gray-500">自定义范围</span>
                        <div className="flex items-center gap-2">
                            <input type="month" value={sFrom} onChange={e=>setSFrom(e.target.value)} className="flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]"/>
                            <span className="text-gray-400 text-xs">至</span>
                            <input type="month" value={sTo}   onChange={e=>setSTo(e.target.value)}   className="flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]"/>
                        </div>
                    </div>
                )}
                <div className="flex items-center gap-2 ml-auto">
                    <span className="text-sm text-gray-500">筛选:</span>
                    <div className="w-48"><StudentPicker students={sortedAZ} value={sStu} onChange={setSStu} placeholder="全部学员" showBal={false}/></div>
                </div>
            </div>
            {statsData.rows.length>0 && (
                <div className="flex gap-4 text-sm">
                    <span className="text-gray-500">合计: <span className="font-bold text-green-600">${statsData.totalRev.toFixed(2)}</span></span>
                    <span className="text-gray-500">消课: <span className="font-bold text-indigo-600">{statsData.totalCI} 次</span></span>
                    {statsData.totalCI>0 && <span className="text-gray-500">均价/课: <span className="font-bold">${(statsData.totalRev/statsData.totalCI).toFixed(1)}</span></span>}
                </div>
            )}
        </div>
        <div className="overflow-x-auto">
            <table className="w-full text-left">
                <thead><tr className="border-b border-gray-100 text-gray-400 text-xs">
                    <th className="p-3 font-bold">周期</th><th className="p-3 font-bold">入账流水</th>
                    <th className="p-3 font-bold">消课</th><th className="p-3 font-bold">充值次数</th><th className="p-3 font-bold">均价/课</th>
                </tr></thead>
                <tbody>
                    {statsData.rows.map(r => (
                        <tr key={r.key} className="border-b border-gray-50 hover-row text-sm">
                            <td className="p-3 font-bold text-gray-700">{sPeriod==='yearly'?`${r.key}年`:fmtMK(r.key)}</td>
                            <td className="p-3 font-bold text-green-600">${r.revenue.toFixed(2)}</td>
                            <td className="p-3 font-bold text-indigo-600">{r.checkins}</td>
                            <td className="p-3 text-gray-600">{r.topups}</td>
                            <td className="p-3 text-gray-500">{r.checkins>0?`$${(r.revenue/r.checkins).toFixed(1)}`:'-'}</td>
                        </tr>
                    ))}
                    {!statsData.rows.length && <tr><td colSpan="5" className="p-8 text-center text-gray-400">暂无数据</td></tr>}
                </tbody>
            </table>
        </div>
    </div>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
        <div className="bg-gray-50 border-b p-4">
            <h3 className="font-bold text-gray-800 mb-3">学员个人分析</h3>
            <div className="max-w-xs"><StudentPicker students={sortedAZ} value={sStu2} onChange={setSStu2} placeholder="选择学员查看详情..." showBal/></div>
        </div>
        {studentStats ? (
            <div className="p-4 space-y-4">
                <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                    {[{l:'当前余额',v:`${studentStats.student.balance} 课时`,c:'text-indigo-700'},
                      {l:'累计消课',v:`${studentStats.checkins} 次`,c:'text-gray-700'},
                      {l:'累计购课',v:`${studentStats.totalBought} 课时`,c:'text-gray-700'},
                      {l:'累计消费',v:`$${studentStats.totalSpent.toFixed(0)}`,c:'text-green-600'},
                      {l:'充值次数',v:`${studentStats.topupCount} 次`,c:'text-gray-700'},
                    ].map(({l,v,c}) => (
                        <div key={l} className="bg-gray-50 p-3 rounded-xl border border-gray-100">
                            <p className="text-xs text-gray-400 mb-1">{l}</p>
                            <p className={`text-lg font-bold ${c}`}>{v}</p>
                        </div>
                    ))}
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm text-gray-500">
                    <div className="bg-gray-50 p-3 rounded-xl">📞 {studentStats.student.mobile||'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl">✉️ {studentStats.student.email||'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl">🎯 首次: {studentStats.first?String(studentStats.first).split(',')[0]:'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl">🕐 最近: {studentStats.last?String(studentStats.last).split(',')[0]:'—'}</div>
                </div>
                {studentStats.student.remark && <div className="bg-gray-50 p-3 rounded-xl text-sm text-gray-600 border border-gray-100">📝 {studentStats.student.remark}</div>}
                <div className="border border-gray-100 rounded-xl overflow-hidden">
                    <div className="bg-gray-50 px-3 py-2 text-xs font-bold text-gray-600 border-b">交易记录 ({studentStats.logs.length})</div>
                    <div className="divide-y divide-gray-50 max-h-56 overflow-y-auto sl">
                        {studentStats.logs.slice(0,50).map(l => (
                            <div key={l.id} className="px-3 py-2.5 flex justify-between text-sm min-h-[44px] items-center">
                                <div><span className="font-medium text-gray-700">{l.action}</span> {l.payMethod&&<span className="text-blue-500 ml-1 text-xs">{l.payMethod}</span>} <span className="text-gray-400 text-xs">{l.note}</span></div>
                                <div className="flex items-center gap-3 flex-shrink-0">
                                    {l.feePaid>0 && <span className="text-green-600 font-bold text-xs">${l.feePaid}</span>}
                                    <span className={`font-bold text-xs ${String(l.change).startsWith('-')?'text-orange-500':'text-green-500'}`}>{l.change}</span>
                                    <span className="text-gray-400 text-xs">{String(l.date).split(',')[0]}</span>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        ) : <div className="p-10 text-center text-gray-400 text-sm">选择一名学员查看个人数据</div>}
    </div>
</div>
)}

{/* ═══ PROFILE MODAL ══════════════════════════════════════════ */}
{selS && (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm">
        {/* Fix #7: slide-up sheet on mobile, centered modal on iPad */}
        <div className="bg-white w-full sm:rounded-3xl sm:max-w-lg shadow-2xl overflow-hidden anim border-t sm:border border-gray-200">
            <div className="flex justify-between items-center p-4 bg-gray-50 border-b">
                <div className="flex items-center gap-2.5 min-w-0">
                    <PhotoAvatar photo={selS.photo} name={selS.name} size="sm"/>
                    <h3 className="text-lg font-bold text-gray-900 truncate">{selS.name}</h3>
                    <BalBadge n={selS.balance}/>
                    {selS.archived && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full shrink-0">归档</span>}
                </div>
                <button onClick={()=>{setSelS(null);setEditP(false);}} className="text-gray-400 active:text-gray-700 text-2xl font-bold p-2 -mr-1 min-h-[44px] min-w-[44px] flex items-center justify-center">×</button>
            </div>
            {/* Fix ⑧: modal-scroll + safe-area bottom padding for iPad Home bar */}
            <div className="p-5 modal-scroll" style={{maxHeight:'calc(100dvh - 80px)', paddingBottom:'calc(env(safe-area-inset-bottom, 0px) + 20px)'}}>
                {!editP ? (
                    <div className="space-y-3">
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                                <p className="text-xs text-gray-400 mb-1">First Name (名)</p>
                                <p className="font-bold text-gray-800">{selS.firstName||selS.name||'—'}</p>
                            </div>
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                                <p className="text-xs text-gray-400 mb-1">Last Name (姓)</p>
                                <p className="font-bold text-gray-800">{selS.lastName||'—'}</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">📞 电话</p><p className="font-bold text-gray-800">{selS.mobile||'—'}</p></div>
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">🗓 最近上课</p><p className="font-bold text-gray-800">{fmtDate(selS.lastActive)}</p></div>
                        </div>
                        {(selS.wechat||selS.email) && (
                            <div className="grid grid-cols-2 gap-3">
                                {selS.wechat && <div className="bg-green-50 p-4 rounded-2xl border border-green-100"><p className="text-xs text-green-500 mb-1">💬 微信号</p><p className="font-bold text-gray-800">{selS.wechat}</p></div>}
                                {selS.email  && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">✉️ 邮箱</p><p className="font-bold text-gray-800 text-sm break-all">{selS.email}</p></div>}
                            </div>
                        )}
                        {selS.birthday && <div className="bg-pink-50 p-4 rounded-2xl border border-pink-100"><p className="text-xs text-pink-400 mb-1">🎂 生日</p><p className="font-bold text-gray-800">{fmtDate(selS.birthday)}</p></div>}
                        {selS.remark && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">备注</p><p className="text-sm text-gray-700 whitespace-pre-wrap">{selS.remark}</p></div>}
	                        {preferenceRows(selS).length > 0 && (
	                            <div className="grid grid-cols-2 gap-2">
	                                {preferenceRows(selS).map(row => (
	                                    <div key={row.key} className="bg-indigo-50 p-3 rounded-2xl border border-indigo-100">
	                                        <p className="text-xs text-indigo-400 mb-0.5">{row.label}</p>
	                                        <p className="text-sm font-bold text-indigo-800">{row.value}</p>
	                                    </div>
	                                ))}
	                            </div>
	                        )}
                        {/* F2: Topup history collapsible */}
                        {canWriteCredits && (()=>{
                            const topupsAll = db.logs.filter(l=>(l.studentId===selS.id || (!l.studentId && l.studentName===selS.name))&&l.action==='充值购课');   /* D3 */
                            const topups = topupsAll.slice(0,10);
                            if (!topupsAll.length) return null;
                            return (
                                <details className="border border-gray-200 rounded-2xl overflow-hidden">
                                    <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2">
                                        💳 充值记录 <span className="font-normal text-gray-400 text-xs">({topupsAll.length} 条{topupsAll.length>10?' · 显示最近10条':''})</span>
                                    </summary>
                                    <div className="divide-y divide-gray-50">
                                        {topups.map(l=>(
                                            <div key={l.id} className="px-4 py-2.5 flex justify-between items-center text-sm">
                                                <div>
                                                    <span className="font-bold text-indigo-700">+{l.change}</span>
                                                    <span className="ml-2 text-xs text-gray-400">{l.payMethod||''}</span>
                                                    {l.note && <span className="ml-1 text-xs text-gray-400 truncate">{l.note}</span>}
                                                </div>
                                                <div className="flex items-center gap-3 flex-shrink-0">
                                                    {l.feePaid>0 && <span className="text-green-600 font-bold text-xs">${l.feePaid}</span>}
                                                    <span className="text-gray-400 text-xs">{String(l.date).split(',')[0]}</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </details>
                            );
                        })()}
                        {/* B3: 上课记录（v4.6）— 按上课日期，撤销的标灰 */}
                        {TENANT_SLUG && attHistory && attHistory.length > 0 && (
                            <details className="border border-blue-100 rounded-2xl overflow-hidden">
                                <summary className="bg-blue-50 px-4 py-3 cursor-pointer select-none text-sm font-bold text-blue-700">📅 上课记录 <span className="font-normal text-blue-400 text-xs ml-1">(近 {attHistory.length} 次)</span></summary>
                                <div className="divide-y divide-gray-50 max-h-64 overflow-y-auto sl">
                                    {attHistory.map(a => (
                                        <div key={a.id} className={`px-4 py-2.5 flex items-center justify-between text-sm ${a.reversed_at?'opacity-50':''}`}>
                                            <span className="font-bold text-gray-700">{fmtDate(String(a.class_date||a.attended_at).slice(0,10))}</span>
                                            <span className="text-xs text-gray-400 flex-1 text-center truncate px-2">{a.note||'常规课程'}</span>
                                            <span className={`text-xs font-bold ${a.reversed_at?'text-gray-400':'text-green-600'}`}>{a.reversed_at?'已撤销':'✓ 已签'}</span>
                                        </div>
                                    ))}
                                </div>
                            </details>
                        )}

                        {/* ── Portfolio section ── */}
                        {canWritePortfolio && (()=>{
                            const items = selS.portfolio || [];
                            return (
                                <div className="border border-purple-100 rounded-2xl overflow-hidden">
                                    <div className="bg-purple-50 px-4 py-3 flex items-center justify-between">
                                        <span className="text-sm font-bold text-purple-700">🎨 作品集
                                            <span className="font-normal text-purple-400 text-xs ml-1">({items.length} 张)</span>
                                        </span>
                                        <button onClick={()=>setPortUpload(true)}
                                            className="text-xs bg-purple-600 active:bg-purple-700 text-white px-3 py-1.5 rounded-lg font-bold">
                                            + 上传
                                        </button>
                                    </div>
                                    {items.length === 0 ? (
                                        <div className="px-4 py-7 text-center">
                                            <p className="text-2xl mb-1">🖼</p>
                                            <p className="text-xs text-gray-400">还没有作品，点击「上传」添加第一张</p>
                                        </div>
                                    ) : (
                                        <div className="p-2.5 grid grid-cols-3 gap-2">
                                            {items.map((item,idx)=>(
                                                <div key={item.id}
                                                    className="port-thumb relative group cursor-pointer rounded-xl overflow-hidden bg-gray-100"
                                                    style={{aspectRatio:'1'}}
                                                    onClick={()=>setPortLB({items,idx})}>
                                                    {/* M7: skeleton shown until image loads */}
                                                    <div className="img-skel absolute inset-0" id={`sk-${item.id}`}/>
                                                    <img
                                                        src={portfolioThumbSrc(selS.id, item)}
                                                        loading="lazy"
                                                        className="w-full h-full object-cover relative"
                                                        onLoad={e=>{const sk=document.getElementById(`sk-${item.id}`);if(sk)sk.style.display='none';}}
                                                        onError={e=>{e.target.style.display='none';}}/>
                                                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pt-4 pb-1">
                                                        {item.title && <p className="text-white text-xs font-bold leading-tight truncate">{item.title}</p>}
                                                        <p className="text-white text-xs leading-tight truncate">{fmtDate(item.date)}{item.note?' 💬':''}</p>
                                                    </div>
                                                    {item.public && (
                                                        <span className="absolute top-1 left-1 rounded-full bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 shadow">
                                                            官网
                                                        </span>
                                                    )}
                                                    {/* B1: port-actions = hidden on mouse devices (hover:flex), always visible on touch (CSS override) */}
                                                    {/* #7 fix: p-2 + min 32px ensures ≥44px total tap target incl. gap */}
                                                    <div className="port-actions absolute top-0.5 right-0.5 hidden group-hover:flex gap-1 z-10">
                                                        <button
                                                            onClick={e=>{e.stopPropagation();setPortEdit({sid:String(selS.id),item,note:item.note||'',title:item.title||'',date:item.date||todayISO(),public:!!item.public});}}
                                                            className="bg-white/90 rounded-lg p-2 text-xs shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center">✏️</button>
                                                        <button
                                                            onClick={e=>{e.stopPropagation();portfolioDoDelete(String(item.id));}}
                                                            className="bg-red-500 rounded-lg p-2 text-white text-xs shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center">🗑</button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })()}
                        <div className="flex gap-2">
                            {canManageOperations && !selS.archived && <>
                                <button onClick={()=>scheduleStudentToday(selS)} disabled={busy}
                                    className="flex-1 py-3 rounded-xl text-sm font-bold text-white bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 min-h-[50px]">📅 {isStudentScheduledOn(selS.id,todayISO())?'查看今日排课':'加入今日排课'}</button>
                            </>}
                            {canWriteStudents && <button onClick={()=>{setEditP(true);setEditPhoto(selS.photo||'');}}
                                className="flex-1 py-3 rounded-xl text-sm font-bold bg-white border-2 border-indigo-100 active:bg-indigo-50 text-indigo-700 min-h-[50px]">✏️ 编辑</button>
                            }
                        </div>
                        {canWriteCredits && !selS.archived && (
                            <button onClick={()=>{setTuStu(selS.id);setSelS(null);setEditP(false);setTab('topup');}}
                                className="w-full py-3 rounded-xl text-sm font-bold bg-white border border-gray-200 active:bg-gray-50 text-gray-700 min-h-[50px]">
                                💰 快速充值
                            </button>
                        )}
                        {/* G3: 学员成长报告 */}
                        {canWritePortfolio && <button onClick={()=>openGrowthReport(selS)}
                            className="w-full py-3 rounded-xl text-sm font-bold bg-gradient-to-r from-purple-500 to-pink-500 active:from-purple-600 active:to-pink-600 text-white min-h-[50px] shadow-sm">
                            🌟 生成成长报告（发给家长）
                        </button>
                        }
                        {canWriteStudents && <button onClick={()=>archiveStudent(selS.id,selS.name,!selS.archived)}
                            className={`w-full py-3 rounded-xl text-sm font-bold border min-h-[50px] ${selS.archived?'bg-green-50 active:bg-green-100 text-green-700 border-green-200':'bg-gray-50 active:bg-gray-100 text-gray-500 border-gray-200'}`}>
                            {selS.archived ? '📤 恢复学员' : '📦 归档学员'}
                        </button>
                        }
                    </div>
                ) : (
                    <form onSubmit={handleUpdateStudent} className="space-y-4">
                        <div>
                            <label className="text-sm font-bold text-gray-500 mb-2 block">照片 Photo <span className="font-normal text-gray-400">选填</span></label>
                            <PhotoUploader value={editPhoto} onChange={setEditPhoto}/>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">First Name (名) *</label>
                                <input name="firstName" defaultValue={selS.firstName||selS.name||''} required className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">Last Name (姓) <span className="font-normal text-gray-400">选填</span></label>
                                <input name="lastName" defaultValue={selS.lastName||''} className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold"/></div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">电话</label>
                                <input name="mobile" defaultValue={selS.mobile} placeholder="04xx xxx xxx" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div>
                                <label className="text-sm font-bold text-indigo-700 mb-1 block">课时余额</label>
                                <input name="balance" type="number" min="0" defaultValue={selS.balance} required className="w-full px-3 py-3 border border-indigo-300 bg-indigo-50 text-indigo-800 font-bold text-xl rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                                <p className="text-xs text-amber-500 mt-1">⚠️ 修改将记入日志</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">微信号 <span className="font-normal text-gray-400">选填</span></label>
                                <input name="wechat" defaultValue={selS.wechat||''} placeholder="如 wechat_id" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">邮箱 <span className="font-normal text-gray-400">选填</span></label>
                                <input name="email" type="email" defaultValue={selS.email||''} className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                        </div>
                        {/* F1: birthday at top level (not buried in art preferences) */}
                        <div><label className="text-sm font-bold text-gray-500 mb-1 block">🎂 生日 <span className="font-normal text-gray-400">选填</span></label>
                            <input type="date" name="birthday" defaultValue={selS.birthday||''} min="1920-01-01" max="2099-12-31"
                                className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                        <div><label className="text-sm font-bold text-gray-500 mb-1 block">备注</label>
                            <textarea name="remark" defaultValue={selS.remark} rows="3" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none"></textarea></div>
	                        <details className="border border-gray-200 rounded-xl overflow-hidden">
	                            <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100">
	                                {preferenceProfile().title} <span className="font-normal text-gray-400">选填</span>
	                            </summary>
	                            <div className="p-4 space-y-3">
	                                {preferenceProfile().fields.map(field => (
	                                    <div key={field.key}>
	                                        <label className="text-sm font-bold text-gray-500 mb-1 block">{field.label}</label>
	                                        <input name={`pref_${field.key}`} defaultValue={preferenceValue(selS, field.key)} placeholder={field.placeholder}
	                                            className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
	                                    </div>
	                                ))}
	                            </div>
	                        </details>
                        <div className="flex justify-between items-center pt-3 border-t border-gray-100">
                            <button type="button" onClick={()=>handleDelete(selS.id,selS.name)} disabled={busy}
                                className="px-4 py-3 bg-red-50 active:bg-red-100 text-red-700 font-bold rounded-xl text-sm border border-red-200 min-h-[50px]">🗑️ 永久删除</button>
                            <div className="flex gap-2">
                                <button type="button" onClick={()=>confirm('放弃未保存的修改？', ()=>{setEditP(false);setEditPhoto('');}, {confirmText:'放弃修改'})} className="px-4 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm min-h-[50px]">取消</button>
                                <button type="submit" disabled={busy} className="px-6 py-3 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm shadow-md min-h-[50px]">💾 保存</button>
                            </div>
                        </div>
                    </form>
                )}
            </div>
        </div>
    </div>
)}

            </main>

            {/* ── Mobile bottom nav (md:hidden) ── */}
            {/* U1: 5+more mobile nav */}
            {moreOpen && <div className="md:hidden fixed inset-0 z-[45]" onClick={()=>setMoreOpen(false)}/>}
            {moreOpen && (
                <div className="md:hidden fixed bottom-[calc(56px+env(safe-area-inset-bottom,0px))] left-0 right-0 z-[46] bg-indigo-900 border-t border-indigo-700 px-4 py-3 grid grid-cols-4 gap-2 anim"
                     onClick={e=>e.stopPropagation()}>
                    {[{k:'logs',i:'📜',s:'日志'},{k:'stats',i:'📈',s:'统计'},{k:'pending',i:'📋',s:'待审核',badge:pendingCount},{k:'new_student',i:'➕',s:'新建'}].filter(item=>allowedTabs.includes(item.k)).map(({k,i,s,badge})=>(
                        <button key={k} onClick={()=>{setTab(k);setMoreOpen(false);}}
                            className={`flex flex-col items-center justify-center py-2.5 gap-0.5 rounded-xl relative ${['logs','stats','pending','new_student'].includes(tab)&&tab===k?'bg-indigo-700':'active:bg-indigo-800'}`}>
                            <span className="text-[22px] leading-none">{i}</span>
                            <span className={`text-[10px] font-bold leading-none tracking-tight ${['logs','stats','pending','new_student'].includes(tab)&&tab===k?'text-white':'text-indigo-300'}`}>{s}</span>
                            {badge>0 && <span className="absolute top-1 right-2 bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4">{badge}</span>}
                        </button>
                    ))}
                </div>
            )}
            <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-indigo-900 border-t border-indigo-800 flex"
                 style={{paddingBottom:'env(safe-area-inset-bottom,0px)', transform:'translateZ(0)', willChange:'transform'}}>
                {[{k:'dashboard',i:'📊',s:'工作台'},{k:'roster',i:'📅',s:'排课'},{k:'students',i:'👥',s:'档案'},{k:'topup',i:'💰',s:'充值'}].filter(item=>allowedTabs.includes(item.k)).map(({k,i,s}) => (
                    <button key={k} onClick={()=>{setTab(k);setMoreOpen(false);}}
                        className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative ${tab===k?'bg-indigo-700':'active:bg-indigo-800'}`}>
                        <span className="text-[22px] leading-none">{i}</span>
                        <span className={`text-[10px] font-bold leading-none tracking-tight ${tab===k?'text-white':'text-indigo-300'}`}>{s}</span>
                        {k==='dashboard' && analytics.lowBalance.length>0 &&
                            <span className="absolute top-1.5 right-[18%] bg-red-500 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4">{analytics.lowBalance.length}</span>}
                    </button>
                ))}
                {/* More button */}
                <button onClick={()=>setMoreOpen(o=>!o)}
                    className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative ${moreOpen||['logs','stats','pending','new_student'].includes(tab)?'bg-indigo-700':'active:bg-indigo-800'}`}>
                    <span className="text-[22px] leading-none">{moreOpen?'✕':'⋯'}</span>
                    <span className={`text-[10px] font-bold leading-none tracking-tight ${moreOpen||['logs','stats','pending','new_student'].includes(tab)?'text-white':'text-indigo-300'}`}>更多</span>
                    {pendingCount>0 && !moreOpen && <span className="absolute top-1.5 right-[18%] bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4">{pendingCount}</span>}
                </button>
            </nav>
        </div>
    );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
