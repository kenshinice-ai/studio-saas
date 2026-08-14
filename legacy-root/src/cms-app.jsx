/* StudioSaaS CMS application source (JSX).
 * Edit THIS file, then rebuild the browser bundle with:
 *   bash backend/scripts/build_cms.sh
 * The compiled output (backend/frontend/assets/cms-app.js) is what
 * legacy-root/index.html actually loads — do not edit it by hand.
 */

import { BillingPanel } from "./panels/billing.jsx";
import { FinancePanel } from "./panels/finance.jsx";
import { IntegrationsPanel } from "./panels/integrations.jsx";
import { BillingIdentityPanel } from "./panels/billing_identity.jsx";
import { OverdueReports } from "./panels/progress_reports.jsx";
import { StudentProgressReports, StudentBillingAccount } from "./panels/student_reports.jsx";
import { PrivateLessonsPanel } from "./panels/private_lessons.jsx";

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
/* 待审核列表的提交时间：数据库原始值形如 "2026-07-26 21:31:15.046556+10:00"，
   微秒和时区偏移是噪音。截到分钟展示（原始值保留在 title 里）。
   值本身已带 studio 本地偏移，直接截取即是 studio 当地时间，无需换算。 */
const fmtDT = (s) => {
    const m = String(s||'').match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    return m ? `${m[1]} ${m[2]}` : (s ? String(s) : '—');
};
/* 注册申请状态 → 中文标签（EN 由 cms-i18n.js 词典层翻译）。
   与 api_v1.py update_registration_status 的 allowed_statuses 对齐。 */
const REG_STATUS_ZH = {
    pending:'待审核', contacted:'已联系', trial_booked:'已约试听', waiting:'跟进中',
    approved:'已批准', converted:'已建档', rejected:'已拒绝', duplicate:'重复申请',
    lost:'已流失', archived:'已归档',
};
/* A2: tenant 模式下签到/课时改走 v1 账本端点（与 Studio Admin 同一本账）。
   根目录单店模式（无 tenantSlug）保持原有整包保存路径不变。 */
const TENANT_SLUG = window.STUDIOSAAS_TENANT_SLUG || '';

/* CMS navigation is intentionally URL-addressable.  Notifications, browser
   back/forward, bookmarks and support links should all open the same work
   surface instead of losing the operator in a single in-memory tab state. */
const CMS_ROUTE_TABS = new Set([
    'dashboard', 'roster', 'courses', 'students', 'works', 'new_student',
    'pending', 'billing', 'topup', 'finance', 'logs', 'stats', 'settings'
]);
const readCmsRoute = () => {
    const params = new URLSearchParams(window.location.search || '');
    const requested = params.get('view') || params.get('tab') || 'dashboard';
    return {
        tab: CMS_ROUTE_TABS.has(requested) ? requested : 'dashboard',
        pendingTab: params.get('type') === 'booking' || params.get('type') === 'bookings'
            ? 'bookings'
            : params.get('type') === 'reports' ? 'reports' : 'registrations',
        settingsSection: params.get('section') || 'account',
        recordId: params.get('id') || '',
    };
};
const v1Api = async (path, options = {}) => {
    const headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'StudioSaaS',
        ...(options.headers || {}),
    };
    const r = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1${path}`, {
        credentials: 'include',
        ...options,
        headers,
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
        const err = new Error(d.message || d.error || `HTTP ${r.status}`);
        err.status = r.status;
        throw err;
    }
    return d;
};

/* Server audit actions the operations log shows, mapped to the same Chinese
   labels the ledger-derived rows already use.

   This is a WHITE list on purpose. audit_logs also carries platform noise
   (auth.*, support.*, tenant.*, public.*) that does not belong in a studio's
   operations log, and it carries attendance.checked_in / attendance.voided /
   credit.adjusted, which db.logs ALREADY contains as ledger rows — listing
   those here would show every check-in twice. */
const AUDIT_ACTION_ZH = {
    'student.created':                     '新生建档',
    'student.updated':                     '更新档案',
    'student.archived':                    '归档学员',
    'daily_roster.added':                  '加入排课',
    'daily_roster.cancelled':              '取消排课',
    'daily_roster.restored':               '恢复排课',
    'daily_roster.updated':                '调整排课',
    'schedule.created':                    '新增班次',
    'schedule.updated':                    '修改班次',
    'schedule.deleted':                    '删除班次',
    'portfolio.uploaded':                  '上传作品',
    'portfolio.updated':                   '修改作品',
    'portfolio.deleted':                   '删除作品',
    'portfolio.share_link_created':        '生成分享链接',
    'portfolio.share_link_revoked':        '撤销分享链接',
    'registration.created':                '收到注册申请',
    'student_access.generated':            '生成家长访问码',
    'student_access.revoked':              '撤销家长访问码',
    'student_access.unlocked':             '解锁家长访问',
    'package.created':                     '新增课包',
    'package.updated':                     '修改课包',
    'package.archived':                    '下架课包',
    'course.created':                      '新增课程',
    'course.updated':                      '修改课程',
    'course.archived':                     '归档课程',
    'data.exported':                       '导出数据',
    'brand.published':                     '发布网站',
    'team.member_upserted':                '新增/更新成员',
    'team.member_updated':                 '调整成员权限',
    'operations.default_class_time_updated':'修改默认上课时间',
};
/* Human-readable detail per audit action. The raw metadata is machine shape
   (uuid lists, asset ids); showing it verbatim is what produced rows like
   "Core opening balance import source:c318f4e42f05 student:1783863014768". */
const auditNote = (action, meta) => {
    const m = meta || {};
    if (action === 'daily_roster.added') {
        const n = Array.isArray(m.students) ? m.students.length : 1;
        const when = m.classTime ? ` ${m.classTime}` : '';
        return `${m.date || ''}${when}${n > 1 ? ` · ${n} 人` : ''}${m.oneToOne ? ' · 1 对 1' : ''}`.trim();
    }
    if (action.startsWith('daily_roster.')) return String(m.date || '');
    if (action === 'data.exported')  return `${m.type || ''}${m.rows ? ` · ${m.rows} 行` : ''}`.trim();
    if (action === 'operations.default_class_time_updated') return String(m.defaultClassTime || m.value || '');
    if (action.startsWith('schedule.')) return String(m.label || m.name || '');
    if (action.startsWith('team.'))     return String(m.email || m.role || '');
    if (action === 'registration.created') return String(m.name || m.mobile || '');
    return String(m.title || m.name || m.note || '');
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

const tenantOwnedLogoUrl = (brand) => {
    const source = brand?.logo_url || brand?.logoUrl || '';
    return ['/logo.png', '/logo-light.png', '/favicon.svg'].includes(source) ? '' : source;
};

/**
 * Render only the configured tenant logo and react to the shared brand event.
 *
 * There is intentionally no PWE or Paradise fallback: tenant-owned CMS
 * surfaces keep the tenant name as the complete identity when no logo exists.
 */
function TenantBrandLogo({ className = '' }) {
    const [brand, setBrand] = useState(() => window.STUDIOSAAS_BRAND || {});
    useEffect(() => {
        const syncBrand = (event) => setBrand(event?.detail || window.STUDIOSAAS_BRAND || {});
        window.addEventListener('studiosaas:brand', syncBrand);
        syncBrand();
        return () => window.removeEventListener('studiosaas:brand', syncBrand);
    }, []);
    const source = tenantOwnedLogoUrl(brand);
    if (!source) return null;
    return (
        <img
            src={source}
            alt={`${brand.name || brand.studioName || 'Studio'} logo`}
            className={className}
            onError={(event) => { event.currentTarget.hidden = true; }}
        />
    );
}

/* ═══════════════════ SVG BAR CHART ════════════════════════════ */
function BarChart({ items, color='var(--info)', h=140, prefix='' }) {
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
                        {d.v>0 && <text x={(W-PAD*2)/2+4} y={h-bh-4} textAnchor="middle" fontSize={8} fill="var(--ink2)" fontWeight="bold">{prefix}{d.v}</text>}
                        <text x={(W-PAD*2)/2+4} y={h+16} textAnchor="middle" fontSize={7.5} fill="var(--muted)">{d.l}</text>
                    </g>
                );
            })}
        </svg>
    );
}

/* ═══════════════════ TABS (WAI-ARIA tab pattern) ══════════════ */
/* The full contract, not just role="tab": a tablist owns exactly one tab stop
 * (roving tabindex), Left/Right move between tabs, Home/End jump to the ends,
 * and every tab points at the panel it controls so a screen reader can say
 * "tab 2 of 5" and then read the right region. `backend/frontend/studio-admin.html`
 * implements the same contract imperatively (see its bindEvents / ArrowLeft
 * handler at :4422); this is the React equivalent so the two admin surfaces
 * behave identically under the keyboard.
 *
 * Tabs are 44px tall and the strip scrolls horizontally rather than wrapping,
 * because a wrapped tablist on a phone puts two rows of targets under a thumb
 * that is aiming for one. */
function Tabs({idBase, label, items, value, onChange, className=''}) {
    const refs = useRef({});
    const order = items.map(i => i.value);
    const onKeyDown = (event) => {
        const keys = {ArrowRight: 1, ArrowLeft: -1};
        let next = null;
        if (event.key in keys) next = order[(order.indexOf(value) + keys[event.key] + order.length) % order.length];
        else if (event.key === 'Home') next = order[0];
        else if (event.key === 'End') next = order[order.length - 1];
        if (!next) return;
        event.preventDefault();
        onChange(next);
        const node = refs.current[next];
        if (node) node.focus();
    };
    return (
        <div role="tablist" aria-label={label} onKeyDown={onKeyDown}
            className={`flex gap-1 overflow-x-auto border-b border-gray-200 ${className}`}>
            {items.map(item => (
                <button key={item.value} type="button" role="tab" id={`${idBase}-tab-${item.value}`}
                    aria-selected={value === item.value} aria-controls={`${idBase}-panel-${item.value}`}
                    tabIndex={value === item.value ? 0 : -1}
                    ref={node => { refs.current[item.value] = node; }}
                    onClick={() => onChange(item.value)}
                    className={`relative min-h-[44px] px-4 text-sm font-bold whitespace-nowrap flex items-center gap-1.5 ${value === item.value ? 'text-indigo-700' : 'text-gray-500'}`}>
                    {item.icon && <Icon name={item.icon} className="w-4 h-4"/>}{item.label}
                    {/* A real element, not `after:bg-indigo-600`. The theme
                        override layer matches class SUBSTRINGS, so a variant
                        prefix is invisible to it: `after:bg-indigo-600` reads
                        as `bg-indigo-600` and fills the BUTTON — measured
                        1.00:1, accent text on an accent block. A child span
                        carries the same class with nothing to misread. */}
                    {value === item.value &&
                        <span aria-hidden="true" className="absolute left-2 right-2 bottom-0 h-0.5 rounded-full bg-indigo-600"/>}
                </button>
            ))}
        </div>
    );
}

function TabPanel({idBase, name, active, children}) {
    if (!active) return null;
    return (
        <div role="tabpanel" id={`${idBase}-panel-${name}`} aria-labelledby={`${idBase}-tab-${name}`}
            tabIndex={0} className="space-y-3 focus:outline-none">
            {children}
        </div>
    );
}

/* ═══════════════════ BALANCE BADGE ════════════════════════════ */
/* B5 (v4.7): 统一空状态组件 — 图标 + 主文 + 次文 */
function EmptyState({icon=null, main='暂无数据', sub='', action=null, onAction=null}) {
    const glyph = icon || <Icon name="inbox" className="w-8 h-8"/>;
    return (
        <div className="cms-empty-state">
            <div className="cms-empty-state__icon">{glyph}</div>
            <p className="cms-empty-state__title">{main}</p>
            {sub && <p className="cms-empty-state__description">{sub}</p>}
            {action && onAction && (
                <button onClick={onAction}
                    className="cms-empty-state__action">
                    {action}
                </button>
            )}
        </div>
    );
}

function BalBadge({ n }) {
    const v = parseInt(n,10)||0;
    if (v===0) return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-red-100 text-red-700 whitespace-nowrap"><Icon name="warning" className="w-3.5 h-3.5"/>0</span>;
    if (v<=2)  return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-orange-100 text-orange-700 whitespace-nowrap"><Icon name="bolt" className="w-3.5 h-3.5"/>{v}</span>;
    /* a11y: the low state must not differ from normal by colour alone */
    if (v<=4)  return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-700 whitespace-nowrap"><Icon name="bolt" className="w-3.5 h-3.5"/>{v}</span>;
    return           <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-green-100 text-green-700 whitespace-nowrap">{v}</span>;
}

/* ═══════════════════ TOAST ════════════════════════════════════ */
function Toast({ msg, type, action, onDone }) {
    /* G2: toasts with a copy action stay longer so they can be tapped */
    useEffect(() => { const t=setTimeout(onDone, action?6000:2700); return()=>clearTimeout(t); }, []);
    const bg = type==='error'?'bg-red-600':type==='warn'?'bg-amber-500':'bg-gray-900';
    return (
        <div role="status" aria-live="polite"
             className={`toast toast-bottom fixed left-1/2 -translate-x-1/2 z-[999] ${bg} text-white px-5 py-3 rounded-2xl shadow-2xl text-sm font-bold max-w-xs text-center`}>
            <div className="inline-flex items-center gap-2 justify-center">
                <Icon name={type==='error'?'warning':type==='warn'?'bolt':'check'} className="w-4 h-4"/>
                <span>{msg}</span>
            </div>
            {action && (
                <button onClick={()=>{action.onClick(); onDone();}}
                    className="mt-2 w-full bg-white/20 active:bg-white/30 rounded-lg py-1.5 text-xs font-bold">
                    {action.label}
                </button>
            )}
        </div>
    );
}

/* ═══════════════════ CMS NOTIFICATIONS ════════════════════════ */
function CmsNotificationCenter({
    notifications = [],
    unreadCount = 0,
    open,
    onToggle,
    onSelect,
    onMarkAllRead,
    loadError = '',
}) {
    const formatCreatedAt = value => {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return '';
        return date.toLocaleString('zh-CN', {month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'});
    };
    return (
        <div className="relative flex-shrink-0">
            <button type="button" onClick={onToggle} aria-label="打开通知" aria-expanded={open}
                className="relative w-9 h-9 flex items-center justify-center rounded-lg cms-chrome-item">
                <Icon name="bell" className="w-5 h-5"/>
                {unreadCount > 0 && (
                    <span aria-label={`${unreadCount} 条未读通知`}
                        className="absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold px-1 rounded-full min-w-[16px] leading-4 text-center">
                        {unreadCount > 99 ? '99+' : unreadCount}
                    </span>
                )}
            </button>
            {open && (
                <div className="absolute right-0 top-11 z-[70] w-[min(92vw,24rem)] bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden text-gray-900">
                    <div className="px-4 py-3 border-b border-gray-100 flex items-center gap-3">
                        <div className="font-bold text-sm flex-1">通知</div>
                        <button type="button" onClick={onMarkAllRead} disabled={unreadCount === 0}
                            className="text-xs font-bold text-indigo-600 disabled:text-gray-300 min-h-[32px]">全部已读</button>
                        <button type="button" onClick={onToggle} aria-label="关闭通知"
                            className="text-gray-400 text-xl leading-none px-1 min-h-[32px]">×</button>
                    </div>
                    {loadError && <div role="status" className="px-4 py-2 text-xs font-bold text-amber-700 bg-amber-50 border-b border-amber-100">{loadError}</div>}
                    <div className="max-h-[min(60vh,24rem)] overflow-y-auto">
                        {notifications.length === 0 ? (
                            <div className="px-4 py-10 text-center text-sm text-gray-400">暂无通知</div>
                        ) : notifications.map(notification => (
                            <button type="button" key={notification.id} onClick={() => onSelect(notification)}
                                aria-label={`${notification.title}${notification.read ? '，已读' : '，未读'}`}
                                className={`w-full text-left px-4 py-3 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 active:bg-gray-100 ${notification.read ? 'bg-white' : 'bg-indigo-50/60'}`}>
                                <div className="flex items-start gap-2.5">
                                    <span className={`mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${notification.read ? 'bg-gray-200' : 'bg-indigo-500'}`} aria-hidden="true"></span>
                                    <span className="min-w-0 flex-1">
                                        <span className="flex items-center gap-2">
                                            <span className="font-bold text-sm truncate">{notification.title}</span>
                                            <span className="text-[10px] text-gray-400 flex-shrink-0">{formatCreatedAt(notification.createdAt)}</span>
                                        </span>
                                        <span className="block mt-1 text-xs text-gray-600 leading-relaxed break-words">{notification.summary}</span>
                                    </span>
                                </div>
                            </button>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
}

/** Keep keyboard focus inside an open modal and restore it on close. */
function useModalFocus(isOpen, onClose, dialogRef, initialFocusRef=null) {
    const closeRef = useRef(onClose);
    closeRef.current = onClose;
    useEffect(() => {
        if (!isOpen) return;
        const previousFocus = document.activeElement;
        const selector = [
            'button:not([disabled])', '[href]', 'input:not([disabled])',
            'select:not([disabled])', 'textarea:not([disabled])',
            '[tabindex]:not([tabindex="-1"])',
        ].join(',');
        const onKey = event => {
            if (event.key === 'Escape') {
                event.preventDefault();
                closeRef.current();
                return;
            }
            if (event.key !== 'Tab') return;
            const focusable = [...(dialogRef.current?.querySelectorAll(selector) || [])];
            if (!focusable.length) { event.preventDefault(); return; }
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (event.shiftKey && document.activeElement === first) {
                event.preventDefault(); last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
                event.preventDefault(); first.focus();
            }
        };
        document.addEventListener('keydown', onKey);
        const timer = setTimeout(() => {
            const target = initialFocusRef?.current || dialogRef.current?.querySelector(selector);
            target?.focus();
        }, 0);
        return () => {
            document.removeEventListener('keydown', onKey);
            clearTimeout(timer);
            if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
        };
    }, [isOpen, dialogRef, initialFocusRef]);
}

/* ═══════════════════ Fix #8: CUSTOM CONFIRM DIALOG ═══════════ */
/* The one dialog in the app.
 *
 * There used to be two: this component (20+ call sites) and bare
 * window.alert / window.confirm — and the single most destructive action,
 * restoring a backup over live data, was on the native one. `requireText`
 * makes a genuinely irreversible action ask the operator to type a word, and
 * `acknowledge` renders a one-button notice so alert() has a home too. */
function ConfirmDialog({ dialog, onClose }) {
    const [typed, setTyped] = useState('');
    const boxRef = useRef(null);
    /* keep the latest onClose without re-running the a11y effect every render */
    const onCloseRef = useRef(onClose);
    onCloseRef.current = onClose;
    useEffect(() => { setTyped(dialog?.promptDefault || ''); }, [dialog]);
    /* a11y: Escape closes; focus moves into the dialog on open (the cancel /
       confirm button when no input autoFocuses) and returns to the previously
       focused element on close — matches the admin consoles' dialogs. */
    /* Dismissing an `acknowledge` notice must still run its onConfirm —
       post-restore/PWA notices rely on it to reload; Escape and overlay
       click are dismissals, not cancellations, for a one-button dialog. */
    const dismiss = () => {
        if (dialog && dialog.acknowledge && dialog.onConfirm) dialog.onConfirm();
        onCloseRef.current();
    };
    const dismissRef = useRef(dismiss);
    dismissRef.current = dismiss;
    useEffect(() => {
        if (!dialog) return;
        const prevFocus = document.activeElement;
        const onKey = (e) => {
            if (e.key === 'Escape') { e.preventDefault(); dismissRef.current(); return; }
            if (e.key !== 'Tab') return;
            const focusable = [...(boxRef.current?.querySelectorAll(
                'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
            ) || [])];
            if (!focusable.length) { e.preventDefault(); return; }
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
            else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
        };
        document.addEventListener('keydown', onKey);
        const t = setTimeout(() => {
            const box = boxRef.current;
            if (box && !box.contains(document.activeElement)) {
                const target = box.querySelector('input, button');
                if (target) target.focus();
            }
        }, 0);
        return () => {
            document.removeEventListener('keydown', onKey);
            clearTimeout(t);
            if (prevFocus && typeof prevFocus.focus === 'function') prevFocus.focus();
        };
    }, [dialog]);
    if (!dialog) return null;
    const needsText = Boolean(dialog.requireText);
    const isPrompt = Boolean(dialog.prompt);
    const ready = needsText
        ? typed.trim() === String(dialog.requireText).trim()
        : (!isPrompt || !dialog.promptRequired || Boolean(typed.trim()));
    const confirmLabel = dialog.confirmText || (dialog.acknowledge ? '知道了 / OK' : '确认');
    return (
        <div className="fixed inset-0 bg-black/50 z-[95] flex items-center justify-center p-4" onClick={dismiss}
             role="dialog" aria-modal="true" aria-describedby="confirm-dialog-message"
             aria-labelledby={dialog.title ? 'confirm-dialog-title' : undefined}
             aria-label={dialog.title ? undefined : '确认操作'}>
            <div ref={boxRef} className="bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl anim" onClick={e=>e.stopPropagation()}>
                {dialog.title && <p id="confirm-dialog-title" className="font-bold text-gray-800 mb-2">{dialog.title}</p>}
                <p id="confirm-dialog-message" className="text-gray-500 text-sm leading-relaxed mb-4 whitespace-pre-line">{dialog.message}</p>
                {needsText && (
                    <div className="mb-5">
                        <label className="block text-xs font-bold text-gray-600 mb-1.5">
                            请输入 <span className="font-mono text-red-600">{dialog.requireText}</span> 以确认
                        </label>
                        <input value={typed} onChange={e=>setTyped(e.target.value)} autoFocus
                            className="w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-red-400"/>
                    </div>
                )}
                {isPrompt && !needsText && (
                    <div className="mb-5">
                        {dialog.promptLabel && <label className="block text-xs font-bold text-gray-600 mb-1.5">{dialog.promptLabel}</label>}
                        <input value={typed} onChange={e=>setTyped(e.target.value)} autoFocus
                            placeholder={dialog.promptPlaceholder || ''}
                            onKeyDown={e=>{ if (e.key==='Enter' && ready) { dialog.onConfirm(typed); onClose(); } }}
                            className="w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"/>
                    </div>
                )}
                <div className="flex gap-3">
                    {!dialog.acknowledge && (
                        <button onClick={onClose}
                            className="flex-1 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm">
                            取消
                        </button>
                    )}
                    <button onClick={() => { if (!ready) return; if (dialog.onConfirm) dialog.onConfirm(isPrompt ? typed : undefined); onClose(); }}
                        disabled={!ready}
                        className={`flex-1 py-3 font-bold rounded-xl text-sm text-white ${dialog.danger?'bg-red-600 active:bg-red-700':'bg-indigo-600 active:bg-indigo-700'} ${ready?'':'opacity-40 cursor-not-allowed'}`}>
                        {confirmLabel}
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
                <span className="pl-3 text-gray-400 flex-shrink-0"><Icon name="search"/></span>
                <input type="text"
                    placeholder={sel ? sel.name : placeholder}
                    value={open ? q : (sel ? sel.name : '')}
                    onFocus={() => { setQ(''); setOpen(true); }}
                    onChange={e => { setQ(e.target.value); setOpen(true); }}
                    className="flex-1 px-2 py-3 outline-none bg-transparent"
                />
                {sel && (
                    <button type="button" onClick={() => { onChange(null); setQ(''); }}
                        aria-label="清除选择" className="pr-3 text-gray-400 active:text-gray-700 text-xl leading-none py-3 px-2">×</button>
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
    if (src.includes('/v1/media/')) return mediaVariantSrc(src, 'thumb');
    return src;
}

/** Add an explicit safe media derivative without discarding signed query data. */
function mediaVariantSrc(src, variant) {
    const url = new URL(src, window.location.origin);
    url.searchParams.delete('thumb');
    url.searchParams.set('variant', variant);
    return `${url.pathname}${url.search}${url.hash}`;
}

/** Responsive candidates for canonical media; legacy imported files stay unchanged. */
function portfolioSrcSet(studentId, item) {
    const src = portfolioImgSrc(studentId, item);
    if (!src.includes('/v1/media/')) return undefined;
    return `${mediaVariantSrc(src, 'thumb')} 360w, ${mediaVariantSrc(src, 'medium')} 960w, ${mediaVariantSrc(src, 'display')} 2000w`;
}

/* ═══════════════════ PHOTO AVATAR ════════════════════════════ */
function PhotoAvatar({ photo, name, size='sm' }) {
    const cls = size==='sm' ? 'w-9 h-9 text-xs' : size==='md' ? 'w-14 h-14 text-base' : 'w-20 h-20 text-2xl';
    const initials = (name||'?').trim().split(/\s+/).map(w=>w[0]||'').slice(0,2).join('').toUpperCase()||'?';
    if (photo) return <img src={mediaSrc(photo)} className={`${cls} rounded-full object-cover flex-shrink-0 border-2 border-white shadow-sm`} alt={name}/>;
    return <div className={`${cls} rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold flex-shrink-0 border-2 border-white shadow-sm`}>{initials}</div>;
}

/* ═══════════════════ ICONS ══════════════════════════════════
 * Emoji were doing the job of icons across the app: their glyphs differ
 * sharply between Windows, Android and macOS, they cannot take the brand
 * colour or a stroke weight, and a screen reader reads "" aloud as
 * "bar chart" mid-sentence. These are Heroicons outline paths drawn in
 * currentColor and hidden from assistive tech, so the adjacent label is what
 * gets announced.
 */
const ICON_PATHS = {
    dashboard: 'M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z',
    calendar: 'M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5',
    users: 'M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z',
    clipboard: 'M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z',
    money: 'M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    scroll: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z',
    trend: 'M2.25 18L9 11.25l4.306 4.306A11.95 11.95 0 0119.8 10.6M21.75 6.75h-4.5m4.5 0v4.5',
    search: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z',
    phone: 'M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z',
    mail: 'M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75',
    image: 'M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z',
    upload: 'M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 7.5 7.5 12M12 7.5v12',
    palette: 'M4.098 19.902a3.75 3.75 0 005.304 0l6.401-6.402M6.75 21A3.75 3.75 0 013 17.25V4.125C3 3.504 3.504 3 4.125 3h5.25c.621 0 1.125.504 1.125 1.125v4.072M6.75 21a3.75 3.75 0 003.75-3.75V8.197M6.75 21h13.125c.621 0 1.125-.504 1.125-1.125v-5.25c0-.621-.504-1.125-1.125-1.125h-4.072M10.5 8.197l2.88-2.88c.438-.439 1.15-.439 1.59 0l3.712 3.713c.44.44.44 1.152 0 1.59l-2.879 2.88M6.75 17.25h.008v.008H6.75v-.008z',
    refresh: 'M16.023 9.348h4.992V4.356m-4.993 4.992l3.181-3.183a8.25 8.25 0 00-11.667 0L3.75 9.348m0 0V4.356m0 4.992h4.992m-4.993 5.304h4.993v4.992m-4.992-4.992l3.18 3.183a8.25 8.25 0 0011.668 0l3.182-3.183m0 0h-4.99m4.99 0v4.992',
    chevronLeft: 'M15.75 19.5L8.25 12l7.5-7.5',
    chevronRight: 'M8.25 4.5l7.5 7.5-7.5 7.5',
    download: 'M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5 12 4.5',
    warning: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-2.98-1.5-3.846 0L2.697 16.126zM12 15.75h.008v.008H12v-.008z',
    check: 'M4.5 12.75l6 6 9-13.5',
    bolt: 'M3.75 13.5l10.5-11.25L12 10.5h7.5L9 21.75 12 13.5H3.75z',
    clock: 'M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z',
    cake: 'M12 8.25v-1.5m0 1.5c-1.355 0-2.697.056-4.024.166C6.845 8.51 6 9.473 6 10.608v2.513m6-4.871c1.355 0 2.697.056 4.024.166C17.155 8.51 18 9.473 18 10.608v2.513M15 8.25v-1.5m-6 1.5v-1.5m12 9.75l-1.5.75a3.354 3.354 0 01-3 0 3.354 3.354 0 00-3 0 3.354 3.354 0 01-3 0 3.354 3.354 0 00-3 0 3.354 3.354 0 01-3 0L3 16.5m15-3.379a48.474 48.474 0 00-6-.371c-2.032 0-4.034.126-6 .371m12 0c.39.049.777.102 1.163.16 1.07.16 1.837 1.094 1.837 2.175v5.169c0 .621-.504 1.125-1.125 1.125H4.125A1.125 1.125 0 013 20.625v-5.169c0-1.081.768-2.015 1.837-2.175A48.111 48.111 0 016 13.121',
    chat: 'M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155',
    pencil: 'M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10',
    printer: 'M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5z',
    heart: 'M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z',
    lock: 'M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z',
    logout: 'M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75',
    cog: 'M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281zM15 12a3 3 0 11-6 0 3 3 0 016 0z',
    stethoscope: 'M4.5 3.75v5.25a5.25 5.25 0 0010.5 0V3.75M6.75 3.75h-2.25m8.25 0h2.25M9.75 14.25v1.5a4.5 4.5 0 009 0v-2.25m0 0a1.5 1.5 0 100-3 1.5 1.5 0 000 3z',
    device: 'M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3',
    recycle: 'M16.023 9.348h4.992V4.356m-4.993 4.992l3.181-3.183a8.25 8.25 0 00-11.667 0L3.75 9.348m0 0V4.356m0 4.992h4.992m-4.993 5.304h4.993v4.992m-4.992-4.992l3.18 3.183a8.25 8.25 0 0011.668 0l3.182-3.183m0 0h-4.99m4.99 0v4.992',
    shield: 'M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z',
    trash: 'M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0',
    save: 'M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z',
    camera: 'M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316zM16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z',
    folder: 'M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z',
    bell: 'M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0',
    broom: 'M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42',
    star: 'M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z',
    card: 'M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z',
    target: 'M12 21a9 9 0 100-18 9 9 0 000 18zm0-3a6 6 0 100-12 6 6 0 000 12zm0-3a3 3 0 100-6 3 3 0 000 6z',
    note: 'M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125',
    archiveBox: 'M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z',
    restore: 'M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3',
    plus: 'M12 4.5v15m7.5-7.5h-15',
    close: 'M6 18L18 6M6 6l12 12',
    ellipsis: 'M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM12.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM18.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0z',
    inbox: 'M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H6.911a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z'
};

function Icon({ name, className = 'w-5 h-5' }) {
    const path = ICON_PATHS[name];
    if (!path) return null;
    return (
        <svg className={`${className} flex-shrink-0`} viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
             aria-hidden="true" focusable="false">
            <path d={path}/>
        </svg>
    );
}

/* ═══════════════════ PHOTO UPLOADER ══════════════════════════ */
function PhotoUploader({ value, onChange, notify }) {
    const [uploading, setUploading] = useState(false);
    const handleFile = async (e) => {
        const file = e.target.files[0]; if (!file) return;
        if (file.size > 5*1024*1024) { notify('照片不能超过 5MB', {danger:true}); return; }
        setUploading(true);
        try {
            const fd = new FormData(); fd.append('file', file);
            /* S2: same-origin fetch carries the session cookie — no token needed */
            const r  = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/media/upload`, {
                method:'POST', credentials:'include',
                headers:{'X-Requested-With':'StudioSaaS'}, body:fd,
            });
            const d  = await r.json();
            if (d.filename) onChange(d.filename);
        } catch { notify('上传失败，请重试', {danger:true}); }
        finally { setUploading(false); e.target.value=''; }
    };
    const btnBase = uploading ? 'bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed' : '';
    return (
        <div className="flex items-center gap-4">
            {value
                ? <img src={mediaSrc(value)} alt="学员照片预览" className="w-14 h-14 rounded-full object-cover border-2 border-indigo-100 flex-shrink-0"/>
                : <div className="w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center text-2xl border-2 border-dashed border-gray-300 flex-shrink-0 text-gray-400"><Icon name="camera" className="w-6 h-6"/></div>
            }
            <div className="space-y-1.5">
                <div className="flex gap-2 flex-wrap">
                    <label className={`cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[44px] ${btnBase||'bg-indigo-50 text-indigo-700 border-indigo-200 active:bg-indigo-100'}`}>
                        <span className="inline-flex items-center gap-1.5"><Icon name="folder" className="w-4 h-4"/>{uploading ? '上传中...' : value ? '更换' : '选择'}</span>
                        <input type="file" accept="image/*" onChange={handleFile} disabled={uploading} className="hidden"/>
                    </label>
                    <label className={`cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[44px] ${btnBase||'bg-purple-50 text-purple-700 border-purple-200 active:bg-purple-100'}`}>
                        <span className="inline-flex items-center gap-1.5"><Icon name="camera" className="w-4 h-4"/>拍照</span>
                        <input type="file" accept="image/*" capture="environment" onChange={handleFile} disabled={uploading} className="hidden"/>
                    </label>
                </div>
                {value && <button type="button" onClick={()=>onChange('')} className="text-xs text-red-400 active:text-red-600">移除照片</button>}
            </div>
        </div>
    );
}

/* ═══════════════ MAINTENANCE PANEL（体检/邮件/备份恢复）═══════════ */
/* confirm/notify come from the app shell so this panel uses the same dialog
   as the other 20+ call sites instead of the browser's native ones. */
function MaintSection({ onRestored, renewTh, saveRenewTh, confirm, notify }) {
    const [hc, setHc]         = useState(null);
    const [hcBusy, setHcBusy] = useState(false);
    const [cfg, setCfg]       = useState(null);
    const [pw, setPw]         = useState('');
    const [cfgMsg, setCfgMsg] = useState(null);   // {text, tone}
    const say = (text, tone='info') => setCfgMsg(text ? {text, tone} : null);
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
        setBusy(true); say('');
        try {
            const body = {email_to:cfg.email_to, smtp_user:cfg.smtp_user, smtp_host:cfg.smtp_host,
                          smtp_port:cfg.smtp_port, weekly_enabled:cfg.weekly_enabled, renew_threshold:renewTh};
            if (pw) body.smtp_password = pw;
            const r = await post('/api/config', body);
            if (r.status === 404) { setStale(true); say(''); return; }
            say(r.ok ? '已保存' : `保存失败 (HTTP ${r.status})`, r.ok ? 'ok' : 'error');
            if (r.ok && pw) { setPw(''); setCfg(c=>({...c, hasPassword:true})); }
        } catch { say('连接失败', 'error'); }
        finally { setBusy(false); }
    };
    const testEmail = async () => {
        setBusy(true); say('发送中…（请先点过「保存配置」）');
        try {
            const r = await post('/api/email-test', {});
            const d = await r.json();
            say(d.ok ? '测试邮件已发出，请查收（含每周汇总预览）' : (d.error || '发送失败'), d.ok ? 'ok' : 'error');
        } catch { say('连接失败', 'error'); }
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
            notify('PWA 缓存已清理，页面将刷新。若主屏幕 App 图标仍未更新，请删除后重新添加。', {onConfirm: () => window.location.reload()});
        } catch(e) {
            notify('缓存清理失败，请关闭 App 后重新打开。', {danger:true});
        }
    };
    const pickBk = async (name) => {
        try { const r = await fetch(`/api/backups/${name}/summary`, {credentials:'include'});
              setBkSel({name, ...(await r.json())}); } catch {}
    };
    const runRestore = async () => {
        setBusy(true);
        try {
            const r = await post('/api/restore', {filename: bkSel.name});
            const d = await r.json();
            if (d.ok) { notify(`恢复完成：${d.students} 名学员 / ${d.logs} 条日志。页面即将刷新数据。`, {onConfirm: onRestored}); }
            else notify(d.error || '恢复失败', {danger:true});
        } catch { notify('连接失败', {danger:true}); }
        finally { setBusy(false); }
    };
    /* Restoring overwrites live student and attendance data. This is the most
       destructive action in the CMS, so it asks the operator to type the backup
       name rather than accepting two reflexive clicks on a native confirm(). */
    const doRestore = () => {
        if (!bkSel || !bkSel.valid) return;
        confirm(
            `该备份：${bkSel.students} 名学员 / ${bkSel.logs} 条日志\n` +
            `与当前相比：学员 ${bkSel.diffStudents>=0?'+':''}${bkSel.diffStudents} / 日志 ${bkSel.diffLogs>=0?'+':''}${bkSel.diffLogs}\n\n` +
            '当前数据会先自动另存为 pre_restore 备份（可再恢复回来），然后被该备份覆盖。',
            runRestore,
            {title:`恢复备份 ${bkSel.name}`, danger:true, requireText:bkSel.name, confirmText:'覆盖当前数据'}
        );
    };
    const inp = "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400";
    if (stale) return (
        <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="bg-red-50 border border-red-300 rounded-xl p-3 space-y-1.5">
                <p className="inline-flex items-center gap-1.5 text-xs font-bold text-red-700"><Icon name="warning" className="w-4 h-4"/>服务器还在运行旧版本</p>
                <p className="text-xs text-red-600">界面已是新版，但数据体检 / 邮件 / 备份恢复需要新版 server.py 支持。请：</p>
                <p className="text-xs text-red-600 font-mono bg-red-100 rounded-lg px-2 py-1.5">1. 用新版 server.py 覆盖 CMS 目录里的旧文件<br/>2. 终端运行 ./cms.sh restart<br/>3. 刷新本页面</p>
                <p className="text-xs text-red-500">验证方法：浏览器打开 /api/ping，version 应为 7.3.1</p>
            </div>
        </div>
    );
    return (<>
        {/* 数据体检 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide"><Icon name="stethoscope" className="w-4 h-4"/>数据体检</p>
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
                    {hc.conflictCopies.length>0 && <p className="inline-flex items-center gap-1.5 text-red-600 font-bold"><Icon name="warning" className="w-4 h-4"/>iCloud 冲突副本: {hc.conflictCopies.join('、')}</p>}
                    <p>待审申请 {hc.pendingCount} 条 · 最近备份 {hc.lastBackup||'无'}（{hc.backupCount} 份）</p>
                </div>)}
            {hc && hc.error && <p className="text-xs text-red-500">体检失败，请重试</p>}
        </div>
        {/* 待续课阈值 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide"><Icon name="bolt" className="w-4 h-4"/>待续课提醒阈值（剩余 ≤N 节）</p>
            <div className="flex gap-2">
                {[1,2,3,5].map(d=>(
                    <button key={d} onClick={()=>{saveRenewTh(d); post('/api/config',{renew_threshold:d}).catch(()=>{});}}
                        className={`flex-1 py-2 rounded-xl text-xs font-bold border ${renewTh===d?'bg-indigo-600 text-white border-indigo-600':'bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100'}`}>{d} 节</button>))}
            </div>
            <p className="text-[11px] text-gray-400">影响学员页「低余额」筛选和每周邮件中的待续课名单</p>
        </div>
        {/* PWA 缓存 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide"><Icon name="device" className="w-4 h-4"/>主屏幕 App / PWA 缓存</p>
            <button onClick={clearPwaCache}
                className="w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm">
                清理 PWA 缓存并刷新</button>
            <p className="text-[11px] text-gray-400">用于更新主屏幕图标、Service Worker 或修复旧页面缓存。</p>
        </div>
        {/* 每周汇总邮件 */}
        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
            <p className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide"><Icon name="mail" className="w-4 h-4"/>每周汇总邮件（周一 10:00）</p>
            {!cfg ? <p className="text-xs text-gray-400">加载中…</p> : (<>
                <div>
                    <label htmlFor="cfg-email-to" className="block text-xs font-bold text-gray-500 mb-1">收件邮箱</label>
                    <input id="cfg-email-to" className={inp} placeholder="you@example.com" value={cfg.email_to||''}
                        onChange={e=>setCfg({...cfg, email_to:e.target.value})}/>
                </div>
                <div>
                    <label htmlFor="cfg-smtp-user" className="block text-xs font-bold text-gray-500 mb-1">发件 Gmail 地址</label>
                    <input id="cfg-smtp-user" className={inp} placeholder="studio@gmail.com" value={cfg.smtp_user||''}
                        onChange={e=>setCfg({...cfg, smtp_user:e.target.value})}/>
                </div>
                <div>
                    <label htmlFor="cfg-smtp-pass" className="block text-xs font-bold text-gray-500 mb-1">Gmail 应用专用密码</label>
                    <input id="cfg-smtp-pass" className={inp} type="password" value={pw} onChange={e=>setPw(e.target.value)}
                        placeholder={cfg.hasPassword?'已保存，留空不变':'16 位应用专用密码'}/>
                </div>
                <div className="flex items-center justify-between">
                    <p className="text-xs font-bold text-gray-600">每周一自动发送</p>
                    <button onClick={()=>setCfg({...cfg, weekly_enabled:!cfg.weekly_enabled})}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${cfg.weekly_enabled?'bg-indigo-600':'bg-gray-300'}`}>
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${cfg.weekly_enabled?'translate-x-6':'translate-x-1'}`}/></button>
                </div>
                {cfgMsg && <p className={`text-xs font-medium ${cfgMsg.tone==='ok'?'text-green-600':cfgMsg.tone==='error'?'text-red-500':'text-gray-500'}`}>{cfgMsg.text}</p>}
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
            <p className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide"><Icon name="recycle" className="w-4 h-4"/>备份与恢复</p>
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
	                <TenantBrandLogo className="w-36 max-h-20 object-contain mx-auto mb-3"/>
	                <p className="tenant-slogan text-sm text-gray-500 italic mb-4">Learn, grow, and feel confident.</p>
	                <p className="text-sm text-gray-400 mb-6">请输入 Studio CMS 账号</p>
                <form onSubmit={submit} className="space-y-3">
                    <div className="text-left">
                        <label htmlFor="cms-login-email" className="block text-xs font-bold text-gray-500 mb-1">管理员邮箱</label>
                        <input
                            id="cms-login-email"
                            type="email"
                            placeholder="you@example.com"
                            value={email}
                            onChange={e => setEmail(e.target.value)}
                            autoFocus
                            className="w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-sm focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>
                    <div className="text-left">
                        <label htmlFor="cms-login-password" className="block text-xs font-bold text-gray-500 mb-1">密码</label>
                        <input
                            id="cms-login-password"
                            type="password"
                            value={pw}
                            onChange={e => setPw(e.target.value)}
                            className="w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-lg tracking-widest focus:ring-2 focus:ring-indigo-500"
                        />
                    </div>
                    {err && <p className="text-red-500 text-xs font-medium">{err}</p>}
                    <button type="submit" disabled={busy || !email || !pw}
                        className="w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm">
                        {busy ? '验证中...' : '进入系统 →'}
                    </button>
                </form>
                <p className="mt-6 pt-4 border-t border-gray-100 text-[10px] tracking-wide text-gray-400">
                    Powered by Paradise Production
                </p>
            </div>
        </div>
    );
}

/* ═══════════════════ MAIN APP ════════════════════════════════ */
function App() {
    const [db,  setDb]  = useState({students:[],logs:[],rosters:{},pending:[]});
    /* Server-side audit events, merged into the operations log below. db.logs
       is synthesised from the credit ledger, so it only ever contains the four
       money/attendance actions. Archiving, renaming, roster edits, portfolio
       and consent changes were invisible here — the CMS sent them inside
       save(), which persists students and packages and drops everything else. */
    const [auditEvents, setAuditEvents] = useState([]);
    const initialCmsRoute = useMemo(() => readCmsRoute(), []);
    const [tab, setTabState] = useState(initialCmsRoute.tab);
    const [pendingTab, setPendingTabState] = useState(initialCmsRoute.pendingTab);
    const [settingsSection, setSettingsSectionState] = useState(initialCmsRoute.settingsSection);
    const [routeRecordId, setRouteRecordId] = useState(initialCmsRoute.recordId);
    const [moreOpen, setMoreOpen] = useState(false);
    const [selS, setSelS] = useState(null);
    const [editP, setEditP] = useState(false);
    const [studentProfileTab, setStudentProfileTab] = useState('profile');
    const [busy, setBusy] = useState(false);
    const [conn, setConn] = useState(false);
    const [connErr, setConnErr] = useState(null);
    const [toast, setToast] = useState(null);
    const [cmsNotifications, setCmsNotifications] = useState([]);
    const [cmsNotificationUnreadCount, setCmsNotificationUnreadCount] = useState(0);
    const [cmsNotificationOpen, setCmsNotificationOpen] = useState(false);
    const [cmsNotificationError, setCmsNotificationError] = useState('');
    const cmsNotificationCursorRef = useRef(0);
    const cmsNotificationPollingRef = useRef(false);
    const [confirmDialog, setConfirmDialog] = useState(null); // Fix #8
    const [showSettings, setShowSettings] = useState(initialCmsRoute.tab === 'settings');
    const [userMenuOpen, setUserMenuOpen] = useState(false);
    // Auth state
    const [loggedIn, setLoggedIn]   = useState(false);
    const [pwOld,    setPwOld]      = useState('');
    const [pwNew1,   setPwNew1]     = useState('');
    const [pwNew2,   setPwNew2]     = useState('');
    const [pwBusy,   setPwBusy]     = useState(false);
    const [pwMsg,    setPwMsg]      = useState(null);   // {text, tone}
    // Global search
    const [gOpen, setGOpen] = useState(false);
    const [gQ,    setGQ]    = useState('');
    // Portfolio
    const [portLB,      setPortLB]      = useState(null);  // lightbox: {items,idx}
    const [portUpload,  setPortUpload]  = useState(false); // upload modal open
    const [portUpFile,  setPortUpFile]  = useState(null);  // {file,dataUrl,note,date,public}
    const [portEdit,    setPortEdit]    = useState(null);  // {sid,item,note,date,public}
    const [portBusy,    setPortBusy]    = useState(false);
    const portLightboxDialogRef = useRef(null);
    const portUploadDialogRef = useRef(null);
    const portEditDialogRef = useRef(null);
    const searchDialogRef = useRef(null);
    const settingsDialogRef = useRef(null);
    const profileDialogRef = useRef(null);
    const [accessCodeResult, setAccessCodeResult] = useState(null);
    const [consentEdit, setConsentEdit] = useState(null);
    useEffect(() => {
        /* One-time access codes and draft consent data must not follow the
           operator when they switch to another student profile. */
        setAccessCodeResult(null);
        setConsentEdit(null);
        setStudentProfileTab('profile');
    }, [selS?.id]);
    const lbTouchX    = useRef(0);  // M1: swipe start X

    const syncCmsRoute = useCallback((patch = {}, replace = false) => {
        const current = readCmsRoute();
        const next = {...current, ...patch};
        const url = new URL(window.location.href);
        const params = url.searchParams;
        if (next.tab && next.tab !== 'dashboard') params.set('view', next.tab);
        else params.delete('view');
        params.delete('tab');
        // 一条 if/else 链，不是两条 if 加一个 else：后者会让 bookings 先被写入
        // 再被下一句的 else 删掉，深链静默失效。
        if (next.tab === 'pending' && next.pendingTab === 'bookings') params.set('type', 'booking');
        else if (next.tab === 'pending' && next.pendingTab === 'reports') params.set('type', 'reports');
        else params.delete('type');
        if (next.tab === 'settings' && next.settingsSection && next.settingsSection !== 'account') params.set('section', next.settingsSection);
        else params.delete('section');
        if (next.recordId && ['students','pending','works','billing'].includes(next.tab)) params.set('id', next.recordId);
        else params.delete('id');
        const nextUrl = `${url.pathname}${params.toString() ? `?${params.toString()}` : ''}${url.hash}`;
        window.history[replace ? 'replaceState' : 'pushState']({}, '', nextUrl);
    }, []);
    const setTab = useCallback((nextTab, options = {}) => {
        const next = CMS_ROUTE_TABS.has(nextTab) ? nextTab : 'dashboard';
        setTabState(next);
        setShowSettings(next === 'settings');
        const nextRecordId = options.recordId || '';
        setRouteRecordId(nextRecordId);
        syncCmsRoute({tab: next, recordId: nextRecordId}, !!options.replace);
    }, [syncCmsRoute]);
    const setPendingTab = useCallback((nextPendingTab) => {
        const next = ['bookings', 'reports'].includes(nextPendingTab) ? nextPendingTab : 'registrations';
        setPendingTabState(next);
        setTabState('pending');
        setShowSettings(false);
        syncCmsRoute({tab:'pending', pendingTab:next});
    }, [syncCmsRoute]);
    const setSettingsSection = useCallback((nextSection) => {
        setSettingsSectionState(nextSection);
        setTabState('settings');
        setShowSettings(true);
        syncCmsRoute({tab:'settings', settingsSection:nextSection});
    }, [syncCmsRoute]);

    useEffect(() => {
        const onPopState = () => {
            const next = readCmsRoute();
            setTabState(next.tab);
            setPendingTabState(next.pendingTab);
            setSettingsSectionState(next.settingsSection);
            setRouteRecordId(next.recordId);
            setShowSettings(next.tab === 'settings');
            setUserMenuOpen(false);
        };
        window.addEventListener('popstate', onPopState);
        return () => window.removeEventListener('popstate', onPopState);
    }, []);

    useModalFocus(Boolean(portLB) && !confirmDialog, () => setPortLB(null), portLightboxDialogRef);
    useModalFocus(Boolean(portUpload) && !confirmDialog, () => {
        if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
        setPortUpload(false); setPortUpFile(null);
    }, portUploadDialogRef);
    useModalFocus(Boolean(portEdit) && !confirmDialog, () => setPortEdit(null), portEditDialogRef);
    useModalFocus(Boolean(gOpen) && !confirmDialog, () => { setGOpen(false); setGQ(''); }, searchDialogRef);
    useModalFocus(Boolean(showSettings && tab !== 'settings') && !confirmDialog, () => setShowSettings(false), settingsDialogRef);
    useModalFocus(Boolean(selS) && !portLB && !portUpload && !portEdit && !confirmDialog,
        () => { setSelS(null); setEditP(false); }, profileDialogRef);
    // Fix ⑪: configurable inactive-days threshold (stored in localStorage)
    const [inactiveDays, setInactiveDays] = useState(() => parseInt(localStorage.getItem('lp_inactive_days')||'90',10));
    const saveInactiveDays = (v) => { const n=parseInt(v,10); if(n>0){setInactiveDays(n);localStorage.setItem('lp_inactive_days',String(n));} };

    // Students tab
    const [srch,     setSrch]     = useState('');
    const [sortBy,   setSortBy]   = useState('date-desc');
    const [filterBy, setFilterBy] = useState('all');
    /* P2-14: the list rendered every match as a card. A studio with 200+
       students painted 200 cards on every keystroke, and the only concession
       was a back-to-top button. Paged rendering plus multi-select for the bulk
       actions that previously only existed under the low-balance filter. */
    const STUDENTS_PER_PAGE = 24;
    const [studentPage, setStudentPage] = useState(1);
    const [selectedStudentIds, setSelectedStudentIds] = useState([]);

    // Roster tab
    const [rDate, setRDate] = useState(todayISO);
    const [rPick, setRPick] = useState(null);
    /* 0022: the roster answered "who is coming today" but not "when". */
    const [defaultClassTime, setDefaultClassTime] = useState('14:30');
    const [defaultClassTimeDraft, setDefaultClassTimeDraft] = useState('14:30');
    const [operationalSettingsBusy, setOperationalSettingsBusy] = useState(false);
    const [rTime, setRTime] = useState('14:30');
    /* Calendar download: preview first, then fetch the file with credentials. */
    const [icsPreview, setIcsPreview] = useState(null);
    const [icsNotice, setIcsNotice] = useState('');
    const [icsBusy, setIcsBusy] = useState(false);
    const icsDialogRef = useRef(null);
    const icsCloseButtonRef = useRef(null);
    const [rOneToOne, setROneToOne] = useState(false);
    const [grpSel, setGrpSel] = useState('');   /* F4: 班组模板选择 */
    /* A1: 每周课表（tenant 模式，存于 PostgreSQL class_schedules） */
    const [schedules, setSchedules] = useState([]);
    const [scheduleLoadError, setScheduleLoadError] = useState('');
    /* A3: 经营真账（估算），来自 v1 dashboard */
    const [bizStats, setBizStats] = useState(null);
    /* B3: 档案页上课记录（v4.6），来自 v1 attendance */
    const [attHistory, setAttHistory] = useState(null);
    const [schedEdit, setSchedEdit] = useState(null);   // null | {id?, label, weekday, startTime, durationMinutes, capacity, studentIds, courseId, teacherUserId, isPublic, room}
    const [schedPick, setSchedPick] = useState(null);
    /* v8.8.0: courses feed the schedule editor's course dropdown. The column
       has existed since A1 and the CMS never wrote it, so every class carried
       only a hand-typed label — fine internally, not enough for a public page,
       where the description and age range live on the course. */
    const [courses, setCourses] = useState([]);
    const [schedCancel, setSchedCancel] = useState(null);   // null | {id, label, date, note}
    /* v8.10.0: 免注册约课申请。和报名共用「待审核」这一页，分两个标签 ——
       计数分开是因为两者含义不同（新报名 vs 老学员占座），但前台不该有
       两个地方要看。 */
    const [bookings, setBookings] = useState([]);
    /* v8.10.3: 课程管理。`courses` 表和它的接口从 A1 起就有，v8.8.0 给排课加了
       「关联课程」下拉——但 CMS 里从来没有创建课程的界面，所以那个下拉永远只有
       「不关联课程」一个选项。一个指向谁也填不了的列表的控件，等于没有。 */
    const [courseEdit, setCourseEdit] = useState(null);   // null | {id?, name, description, ageRange, durationMinutes, priceAud}
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
        owner: ['dashboard','pending','roster','courses','students','works','new_student','billing','topup','finance','logs','stats','settings'],
        platform_super_admin: ['dashboard','pending','roster','courses','students','works','new_student','billing','topup','finance','logs','stats','settings'],
        super_admin: ['dashboard','pending','roster','courses','students','works','new_student','billing','topup','finance','logs','stats','settings'],
        manager: ['dashboard','pending','roster','courses','students','works','new_student','billing','topup','finance','logs','stats','settings'],
        teacher: ['dashboard','roster','courses','students','works','logs','settings'],
        front_desk: ['dashboard','pending','students','new_student','billing','topup','logs','settings'],
        staff: ['dashboard','pending','roster','courses','students','works','new_student','billing','topup','logs','settings'],
    };
    const allowedTabs = roleTabs[actorRole] || ['dashboard'];
    const canManageOperations = [...ownerRoles,'manager'].includes(actorRole);
    const canExportData = [...ownerRoles,'manager'].includes(actorRole);
    const canViewFinancialAnalytics = [...ownerRoles,'manager'].includes(actorRole);
    const canWriteStudents = [...ownerRoles,'manager','front_desk','staff'].includes(actorRole);
    const canWriteCredits = [...ownerRoles,'manager','front_desk','staff'].includes(actorRole);
    const canWritePortfolio = [...ownerRoles,'manager','teacher','staff'].includes(actorRole);
    /* Mirrors backend progress_reports:* — the teacher who taught the term
       writes the report, and someone senior releases it to the family. That
       split is in ROLE_PERMISSIONS, not a UI nicety: Role.TEACHER has
       progress_reports:write without :publish, so a teacher-only publish
       button would render, be pressed, and 403. */
    /* Mirrors backend scheduling:write — owner/manager/front_desk rearrange the
       timetable; a teacher reads it (scheduling:read) but does not move it. */
    const canWriteScheduling = [...ownerRoles,'manager','front_desk'].includes(actorRole);
    const canWriteProgress = [...ownerRoles,'manager','teacher'].includes(actorRole);
    const canPublishProgress = [...ownerRoles,'manager'].includes(actorRole);
    /* Mirrors backend attendance:write — teacher/staff can run the roster day
       (check-in, per-day scheduling); front_desk cannot. */
    const canWriteAttendance = [...ownerRoles,'manager','teacher','staff'].includes(actorRole);
    /* Backend grants class_bookings:review to Front Desk without granting
       schedule mutation.  Keep that distinction visible in the UI: review
       is an inbox action, not a timetable permission. */
    const canReviewBookings = [...ownerRoles,'manager','front_desk','staff'].includes(actorRole);
    /* Mirrors backend credits:refund — refunds are owner/manager only. */
    const canRefund = [...ownerRoles,'manager'].includes(actorRole);
    /* Mirrors backend portfolio:share — share-link creation is owner/manager only. */
    const canViewCmsNotifications = ['owner','manager','front_desk','staff','platform_super_admin','super_admin'].includes(actorRole);

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

    /* v8.10.3: the team list is no longer loaded only when the settings modal
       opens. It also feeds the schedule editor's 授课老师 dropdown, and that
       dropdown sat empty until you happened to open 设置 once — the data was
       simply not fetched yet, so the control looked broken rather than empty.
       A list two screens depend on cannot be loaded by one of them. */
    useEffect(() => {
        if (TENANT_SLUG && canManageOperations) loadTeam();
    }, [actorRole]);
    useEffect(() => {
        if (showSettings && TENANT_SLUG && canManageOperations) loadTeam();
    }, [showSettings]);

    useEffect(() => {
        if (actorRole && !allowedTabs.includes(tab)) setTab('dashboard');
    }, [actorRole, tab]);

    const tenantLogoUrl = tenantOwnedLogoUrl(tenantBrand);
    const tenantDisplayName = tenantBrand.name || tenantBrand.studioName || 'Studio';
    /* The copy staff paste into WeChat used to say the literal word "Studio"
       and end with a palette emoji — wrong for the piano, dance and game tenants, and
       visible to the parent receiving it. Nouns and templates come from the
       tenant's own brand settings; the studio name is always substituted. */
    const venueNoun = (tenantBrand.venue_noun || tenantBrand.venueNoun || {}).zh || '工作室';
    const workNoun = (tenantBrand.work_noun || tenantBrand.workNoun || {}).zh || '作品';
    const messageTemplates = tenantBrand.message_templates || tenantBrand.messageTemplates || {};
    /* {studio} {student} {balance} {credits} {fee} {work} are filled in below. */
    const renderMessage = (key, fallback, values={}) => {
        const template = String(messageTemplates[key] || fallback);
        return Object.keys({studio:tenantDisplayName, venue:venueNoun, work:workNoun, ...values})
            .reduce((text, name) => text.split(`{${name}}`).join(
                String({studio:tenantDisplayName, venue:venueNoun, work:workNoun, ...values}[name] ?? '')
            ), template);
    };

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
    /* ...and the one-button variant, so window.alert has a home in the same
       dialog rather than a second, differently styled system popup. */
    const notify = (message, opts={}) =>
        setConfirmDialog({message, acknowledge:true, ...opts});

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

    /* v8.8.0: 是否在公开课表上显示这位老师的姓名，以及对外用什么名字。
       这是关于「一个人的名字要不要出现在公网上」的决定，不是版式偏好 ——
       被排了一节课不等于同意公开。默认关，由 Owner 逐人开启。 */
    const updateTeamPublicity = async (member, patch) => {
        if (teamBusy || member.role === 'owner') return;
        setTeamBusy(true);
        try {
            await v1Api(`/team/${member.id}`, {method:'PATCH', body:JSON.stringify({
                role: member.role, status: member.status, ...patch,
            })});
            await loadTeam();
            await loadSchedules();
            showToast(patch.showOnPublicTimetable === undefined ? '对外显示名已保存'
                : (patch.showOnPublicTimetable ? '已允许在公开课表显示姓名' : '已取消公开显示姓名'));
        } catch (e) { showToast(`更新失败：${e.message}`, 'error'); }
        finally { setTeamBusy(false); }
    };

    /* G1: keyboard shortcut Cmd/Ctrl+K — must be before any early returns (Rules of Hooks) */
    useEffect(() => {
        const h = e => { if ((e.metaKey||e.ctrlKey) && e.key==='k') { e.preventDefault(); setGOpen(o=>!o); setGQ(''); } };
        window.addEventListener('keydown', h);
        return () => window.removeEventListener('keydown', h);
    }, []);

    /* Calendar preview is a real modal: move focus in, keep Tab inside, close
       with Escape, then return focus to the control that opened it. */
    useEffect(() => {
        if (!icsPreview) return;
        const previousFocus = document.activeElement;
        const focusableSelector = [
            'button:not([disabled])',
            '[href]',
            'input:not([disabled])',
            'select:not([disabled])',
            'textarea:not([disabled])',
            '[tabindex]:not([tabindex="-1"])',
        ].join(',');
        const onKey = e => {
            if (e.key === 'Escape') {
                e.preventDefault();
                setIcsPreview(null);
                return;
            }
            if (e.key !== 'Tab') return;
            const focusable = [...(icsDialogRef.current?.querySelectorAll(focusableSelector) || [])];
            if (!focusable.length) { e.preventDefault(); return; }
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault(); last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault(); first.focus();
            }
        };
        document.addEventListener('keydown', onKey);
        const timer = setTimeout(() => icsCloseButtonRef.current?.focus(), 0);
        return () => {
            document.removeEventListener('keydown', onKey);
            clearTimeout(timer);
            if (previousFocus && typeof previousFocus.focus === 'function') previousFocus.focus();
        };
    }, [icsPreview]);

    /* Lightbox arrow navigation; modal dismissal/focus lives in useModalFocus. */
    useEffect(() => {
        const onKey = e => {
            if (portLB) {
                if (e.key === 'ArrowRight') setPortLB(p => p && p.idx < p.items.length-1 ? {...p, idx:p.idx+1} : p);
                if (e.key === 'ArrowLeft')  setPortLB(p => p && p.idx > 0               ? {...p, idx:p.idx-1} : p);
            }
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [portLB]);

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

    useEffect(() => { if (loggedIn) load(); }, [loggedIn]);

    /* ── B3 fix: heartbeat — detect server restart, auto-reload on reconnect ── */
    useEffect(() => {
        if (!loggedIn) return;
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
    }, [loggedIn]);

    /* CMS notifications deliberately use polling in phase one. The cursor is
       monotonic, so a slow request or a tab that was backgrounded cannot make
       the next refresh re-show old events. */
    useEffect(() => {
        if (!loggedIn || !TENANT_SLUG || !canViewCmsNotifications) {
            setCmsNotifications([]);
            setCmsNotificationUnreadCount(0);
            cmsNotificationCursorRef.current = 0;
            setCmsNotificationOpen(false);
            setCmsNotificationError('');
            return undefined;
        }
        let alive = true;
        cmsNotificationCursorRef.current = 0;

        const mergeNotifications = (incoming, replace = false) => {
            setCmsNotifications(previous => {
                const byId = new Map((replace ? [] : previous).map(item => [item.id, item]));
                incoming.forEach(item => byId.set(item.id, item));
                return Array.from(byId.values())
                    .sort((a, b) => Number(b.sequence || 0) - Number(a.sequence || 0))
                    .slice(0, 50);
            });
        };
        const poll = async (initial = false) => {
            if (!alive || cmsNotificationPollingRef.current) return;
            cmsNotificationPollingRef.current = true;
            const cursor = cmsNotificationCursorRef.current;
            try {
                const query = initial
                    ? '?limit=30'
                    : `?after=${encodeURIComponent(String(cursor))}&limit=30`;
                const data = await v1Api(`/notifications${query}`);
                if (!alive) return;
                const incoming = Array.isArray(data.notifications) ? data.notifications : [];
                mergeNotifications(incoming, initial);
                const nextCursor = Number(data.nextCursor ?? data.cursor ?? cursor);
                if (Number.isFinite(nextCursor) && nextCursor >= cursor) {
                    cmsNotificationCursorRef.current = nextCursor;
                }
                setCmsNotificationUnreadCount(Number(data.unreadCount || 0));
                setCmsNotificationError('');
                if (!initial && incoming.length > 0) {
                    const latest = incoming[incoming.length - 1];
                    showToast(`${latest.title} · ${latest.summary}`, 'warn', {
                        label: '查看通知',
                        onClick: () => setCmsNotificationOpen(true),
                    });
                }
            } catch (error) {
                if (alive) setCmsNotificationError(error?.message || '通知暂时无法更新');
            } finally {
                cmsNotificationPollingRef.current = false;
            }
        };

        poll(true);
        const id = setInterval(() => {
            if (document.visibilityState !== 'hidden') poll(false);
        }, 30000);
        const onVisibility = () => {
            if (document.visibilityState === 'visible') poll(false);
        };
        document.addEventListener('visibilitychange', onVisibility);
        return () => {
            alive = false;
            clearInterval(id);
            document.removeEventListener('visibilitychange', onVisibility);
        };
    }, [loggedIn, actorRole]);

    const markCmsNotificationRead = async (notification) => {
        try {
            const data = await v1Api(`/notifications/${encodeURIComponent(notification.id)}/read`, {
                method: 'POST',
                body: JSON.stringify({}),
            });
            setCmsNotifications(previous => previous.map(item => item.id === notification.id ? {...item, read:true} : item));
            setCmsNotificationUnreadCount(Number(data.unreadCount || 0));
            return true;
        } catch {
            showToast('通知状态更新失败', 'error');
            return false;
        }
    };
    const openCmsNotification = async notification => {
        const marked = notification.read || await markCmsNotificationRead(notification);
        if (!marked) return;
        setCmsNotificationOpen(false);
        if (notification.targetTab && allowedTabs.includes(notification.targetTab)) {
            if (notification.targetTab === 'pending' && notification.targetSubtab) {
                setPendingTab(notification.targetSubtab);
            } else {
                setTab(notification.targetTab, {recordId:notification.targetId || notification.recordId || ''});
            }
        }
    };
    const markAllCmsNotificationsRead = async () => {
        try {
            const data = await v1Api('/notifications/read-all', {
                method: 'POST',
                body: JSON.stringify({}),
            });
            setCmsNotifications(previous => previous.map(item => ({...item, read:true})));
            setCmsNotificationUnreadCount(Number(data.unreadCount || 0));
        } catch {
            showToast('通知状态更新失败', 'error');
        }
    };
    const doLogout = async () => {
        await fetch('/v1/auth/logout', {method:'POST', credentials:'include'}).catch(()=>{});
        setLoggedIn(false);
        setConn(false);
        setDb({students:[],logs:[],rosters:{},pending:[]});
        setShowSettings(false);
        setCmsNotificationOpen(false);
        setCmsNotifications([]);
        setCmsNotificationUnreadCount(0);
    };

    const changeWebPw = async () => {
        if (!pwOld || !pwNew1) { setPwMsg({text:'请填写旧密码和新密码', tone:'error'}); return; }
        if (pwNew1 !== pwNew2)  { setPwMsg({text:'两次新密码不一致', tone:'error'}); return; }
        if (pwNew1.length < 8)  { setPwMsg({text:'新密码至少 8 位', tone:'error'}); return; }   /* S3 */
        setPwBusy(true); setPwMsg(null);
        try {
            const r = await fetch('/v1/auth/change-password', {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({oldPassword: pwOld, newPassword: pwNew1}),
                credentials: 'include'
            });
            const d = await r.json();
            if (d.ok) { setPwOld(''); setPwNew1(''); setPwNew2(''); setPwMsg({text:'密码已更新', tone:'ok'}); }
            else       { setPwMsg({text:String(d.message||d.error||'修改失败'), tone:'error'}); }
        } catch { setPwMsg({text:'连接失败', tone:'error'}); }
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
                photo:'', experience:'', goals:'', preferences:{}, birthday:'',
                ...s
            }));
            if (!d.pending)  d.pending  = [];
            if (!d.packages) d.packages = [{id:1, name:'标准课包', credits:10, price:1200}];
            const nextDefaultClassTime = d.operationalSettings?.defaultClassTime || '14:30';
            setDefaultClassTime(nextDefaultClassTime);
            setDefaultClassTimeDraft(nextDefaultClassTime);
            setRTime(current => current === '14:30' ? nextDefaultClassTime : (current || nextDefaultClassTime));
            revRef.current = d.rev || 1;   /* D2 */
            setDb(d); setConn(true);
            loadSchedules();   /* A1: 课表与数据并行加载，失败不阻塞 */
            loadAuditEvents();
        } catch(e) { setConnErr(e.message); }
        finally { setBusy(false); }
    };
    /* Returns true when the server accepted the save, false on every handled
       failure (401/403/409/network) — callers must check it before showing a
       success toast, resetting a form or navigating away, otherwise a rejected
       save reads as a success and the optimistic setDb(nd) becomes silent data
       loss on the next reload. */
    const save = async (nd, force=false) => {
        setDb(nd);
        try {
            /* D2: always send the freshest rev from the ref (not the possibly
               stale copy inside nd) so back-to-back saves don't self-conflict */
            const body = {...nd, rev: revRef.current, ...(force ? {force:true} : {})};
            const r = await fetch('/api/save', {method:'POST', headers:apiHeaders(),
                                                credentials:'include', body:JSON.stringify(body)});
            if (r.status === 401) { showToast('登录已过期，请重新登录 / Session expired', 'error'); setTimeout(doLogout, 1500); return false; }
            if (r.status === 403) {
                showToast('无权保存此租户数据 / No permission for this tenant.', 'error');
                /* resync the optimistic setDb(nd) above back to server truth */
                setTimeout(load, 800);
                return false;
            }
            if (r.status === 409) {
                const d = await r.json().catch(()=>({}));
                if (d.status === 'conflict') {
                    /* D2: another tab/device saved first — reload, do NOT overwrite */
                    showToast('数据已在其他设备/标签页被修改，正在刷新…', 'error');
                    setTimeout(load, 800);
                } else if (d.status === 'shrink_guard') {
                    /* D1/D1b: server blocked a save that drops a large chunk of data */
                    confirm(`安全拦截：${d.message || `数据量将从 ${d.current} 减少到 ${d.incoming}`} `+
                            `如果这不是你刻意删除的结果，请选择取消并刷新页面！`,
                            async () => save(nd, true),
                            {danger:true, confirmText:'我确认，继续保存'});
                }
                return false;
            }
            if (!r.ok) throw new Error('save failed');
            const d = await r.json().catch(()=>null);
            /* D2: adopt the server's new revision so the next save passes the lock */
            if (d && d.rev) { revRef.current = d.rev; setDb(prev => ({...prev, rev: d.rev})); }
            return true;
        } catch(err) { if (!String(err).includes('401')) showToast('数据未能同步到服务器！', 'error'); return false; }
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
        const idsByName = new Map();
        db.students.forEach(student => {
            const ids = idsByName.get(student.name) || [];
            ids.push(student.id);
            idsByName.set(student.name, ids);
        });
        db.logs.forEach(l => {
            if (l.action !== '上课签到') return;
            const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
            if (m) {
                const d = new Date(`${m[3]}-${m[2]}-${m[1]}`);
                if (!isNaN(d) && d.getTime() >= cutoff) {
                    /* Current logs carry the immutable student id. Historical
                       name-only logs are assigned only when that name resolves
                       to exactly one student; sharing an activity score between
                       two same-name students is worse than leaving the old event
                       unassigned. */
                    const legacyIds = idsByName.get(l.studentName) || [];
                    const key = l.studentId || (legacyIds.length===1 ? legacyIds[0] : '');
                    if (key) map[key] = (map[key]||0) + 1;
                }
            }
        });
        return map;
    }, [db.logs, db.students]);
    const getTag = (s) => {
        const cnt = activityMap[s.id] || 0;
        if (cnt >= 4) return {icon:'bolt',    label:'活跃',     cls:'bg-red-100 text-red-700'};
        if (cnt >= 1) return {icon:'clock',   label:'低频',     cls:'bg-gray-100 text-gray-500'};
        if ((parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays)
            return {icon:'warning', label:'流失风险', cls:'bg-orange-100 text-orange-600'};
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
    useEffect(() => { setStudentPage(1); setSelectedStudentIds([]); }, [srch, sortBy, filterBy]);

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
            if (filterBy === 'tag-hot')  list = list.filter(s => !s.archived && (activityMap[s.id]||0) >= 4);
            if (filterBy === 'tag-low')  list = list.filter(s => !s.archived && (activityMap[s.id]||0) >= 1 && (activityMap[s.id]||0) < 4);
            if (filterBy === 'tag-risk') list = list.filter(s => !s.archived && (parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.id]||0) === 0);
            if (filterBy === 'portal-ready') list = list.filter(s => !s.archived && !!s.mobile && !!s.hasAccessCode);
            if (filterBy === 'portal-missing-mobile') list = list.filter(s => !s.archived && !s.mobile);
            if (filterBy === 'portal-disabled') list = list.filter(s => !s.archived && !!s.mobile && !s.hasAccessCode);
            if (filterBy === 'portal-content-blocked') list = list.filter(s => !s.archived && (s.portfolio||[]).length>0 && (!s.mobile || !s.hasAccessCode));
            if (filterBy === 'publication-live') list = list.filter(s => !s.archived && (s.portfolio||[]).some(item=>item.public || item.visibility==='shared'));
            if (filterBy === 'publication-ready') list = list.filter(s => !s.archived && s.publicationConsent?.status==='confirmed');
            if (filterBy === 'publication-missing-consent') list = list.filter(s => !s.archived && (s.portfolio||[]).length>0 && s.publicationConsent?.status!=='confirmed');
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

    /* P2-14: one page of cards instead of every match. */
    const studentPageCount = Math.max(1, Math.ceil(sortedFiltered.length / STUDENTS_PER_PAGE));
    const pageStudents = useMemo(() => {
        const page = Math.min(studentPage, studentPageCount);
        return sortedFiltered.slice((page - 1) * STUDENTS_PER_PAGE, page * STUDENTS_PER_PAGE);
    }, [sortedFiltered, studentPage, studentPageCount]);
    /* Selection survives paging but never outlives the filter it was made under. */
    const selectedStudents = useMemo(
        () => sortedFiltered.filter(s => selectedStudentIds.includes(s.id)),
        [sortedFiltered, selectedStudentIds]);

    const toggleSelectStudent = (sid) =>
        setSelectedStudentIds(prev => prev.includes(sid) ? prev.filter(id => id !== sid) : [...prev, sid]);
    const toggleSelectPage = (checked) =>
        setSelectedStudentIds(prev => {
            const ids = pageStudents.map(s => s.id);
            return checked ? Array.from(new Set([...prev, ...ids])) : prev.filter(id => !ids.includes(id));
        });

    const sortedAZ = useMemo(() =>
        [...db.students].filter(s => !s.archived).sort((a,b) => a.name.localeCompare(b.name,'zh-CN')),
    [db.students]);
    const portfolioEntries = useMemo(() => db.students
        .filter(student => !student.archived)
        .flatMap(student => (student.portfolio || []).map(item => ({student, item})))
        .sort((a,b) => String(b.item.date || '').localeCompare(String(a.item.date || ''))),
    [db.students]);

    useEffect(() => {
        if (tab !== 'students' || !routeRecordId) return;
        const student = db.students.find(item => String(item.id) === String(routeRecordId));
        if (student && selS?.id !== student.id) {
            setSelS(student);
            setEditP(false);
        }
    }, [tab, routeRecordId, db.students]);

    /* A1: 当日应到 = 命中当天 weekday 的课表学员 ∪ 手动排课 */
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
    const todayCheckedCount = useMemo(() => {
        const d=todayISO().split('-');
        const prefix=`${d[2]}/${d[1]}/${d[0]}`;
        return new Set(db.logs.filter(l=>l.action==='上课签到'&&String(l.date).startsWith(prefix)).map(l=>l.studentId||l.studentName)).size;
    }, [db.logs]);

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
    /* The operations log is the union of two sources, and neither alone is the
       studio's history: db.logs is synthesised from the credit ledger (money
       and attendance only), while audit_logs is what the server recorded for
       everything else. Kept local to this page — analytics counts check-ins
       and revenue from db.logs and must not see audit rows. */
    const auditAsLogs = useMemo(() => {
        if (!TENANT_SLUG || !auditEvents.length) return [];
        const nameById = new Map(db.students.map(s => [String(s.id), s.name]));
        return auditEvents.reduce((rows, ev) => {
            const label = AUDIT_ACTION_ZH[ev.action];
            if (!label) return rows;
            const meta = ev.metadata || {};
            const sid = ev.resourceType === 'student'
                ? String(ev.resourceId || '')
                : String((Array.isArray(meta.students) && meta.students[0]) || '');
            const when = new Date(ev.createdAt);
            if (isNaN(when.getTime())) return rows;
            const dd = String(when.getDate()).padStart(2,'0');
            const mm = String(when.getMonth()+1).padStart(2,'0');
            rows.push({
                id: `audit-${ev.id}`,
                studentId: sid || null,
                studentName: nameById.get(sid) || '—',
                action: label,
                change: '0',
                feePaid: 0,
                note: auditNote(ev.action, meta),
                date: `${dd}/${mm}/${when.getFullYear()}, ${when.toTimeString().slice(0,8)}`,
                actorEmail: ev.actorEmail || '',
                _ts: when.getTime(),
            });
            return rows;
        }, []);
    }, [auditEvents, db.students]);

    /* Opening-balance rows were written by the migration importer with an
       engineering provenance note ("Core opening balance import source:…
       student:…"). It identifies an import batch, not anything a studio owner
       can read or act on. */
    const displayNote = (note) => {
        const s = String(note || '');
        if (/^Core opening balance import/i.test(s)) return '数据迁移期初余额';
        return s;
    };
    const logTimestamp = (l) => {
        if (typeof l._ts === 'number') return l._ts;
        const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})(?:,\s*(\d{2}):(\d{2}):(\d{2}))?/);
        if (!m) return 0;
        const t = new Date(`${m[3]}-${m[2]}-${m[1]}T${m[4]||'00'}:${m[5]||'00'}:${m[6]||'00'}`);
        return isNaN(t.getTime()) ? 0 : t.getTime();
    };
    const allLogs = useMemo(() => (
        auditAsLogs.length
            ? [...db.logs, ...auditAsLogs].sort((a,b) => logTimestamp(b) - logTimestamp(a))
            : db.logs
    ), [db.logs, auditAsLogs]);

    /* Fix #10: log page auto-clamp when data changes */
    const filteredLogs  = useMemo(() => {
        const stuName = lStu ? (db.students.find(x=>x.id===lStu)||{}).name : null;
        return allLogs.filter(l => {
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
    }, [allLogs, db.students, lStu, lSrch, lAct, lDateFrom, lDateTo]);
    const logPageCount  = Math.max(1, Math.ceil(filteredLogs.length/LPP));
    const pagedLogs     = filteredLogs.slice((lPage-1)*LPP, lPage*LPP);
    const logActions    = useMemo(() => [...new Set(allLogs.map(l=>l.action))].sort(), [allLogs]);
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
                const ok = await save({...db, students:ns, logs:[mkLog(sname,'上课签到',-1,'常规课程消耗',0,{studentId:sid}),...db.logs]});
                if (!ok) return;
            }
            if (selS?.id===sid) setSelS(p=>({...p,balance:nb}));
            /* G2: 一键复制给家长的签到确认话术 */
            const confirmMsg = nb===0
                ? renderMessage('checkin_empty', '{student} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～', {student:sname})
                : renderMessage('checkin', '{student} 今日已完成签到 ✓ 当前剩余 {balance} 课时。{studio} 感谢您的支持！', {student:sname, balance:nb});
            const act = {label:'复制签到确认（发家长）', onClick:()=>copyText(confirmMsg,'签到确认已复制')};
            if (nb===0) showToast(`${sname} 课时已清零！请提醒续课`, 'warn', act);
            else        showToast(`${sname} 签到 ✓ 剩余 ${nb} 课时`, 'success', act);
        } catch(e) { showToast(`签到失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const undoCheckIn = (sid, sname) => {
        const m = String(rDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
        const datePrefix = m ? `${m[3]}/${m[2]}/${m[1]}` : '';
        const exactEntry = TENANT_SLUG
            ? db.logs.find(l=>l.studentId===sid&&l.action==='上课签到'&&l.attendanceId&&String(l.date).startsWith(datePrefix))
            : null;
        if (TENANT_SLUG && !exactEntry) {
            showToast(`未找到 ${fmtDate(rDate)} 的准确签到记录，未执行撤销`, 'warn');
            return;
        }
        confirm(`撤销 ${sname} 在 ${fmtDate(rDate)} 的签到，扣掉的课时会退回 TA 的余额。\n\n这条撤销会写进操作日志，可以随时再签一次。`, async () => {
            if (busy) return; // Fix ④: guard against concurrent busy
            setBusy(true);
            try {
                if (TENANT_SLUG) {
                    /* A2: 通过 v1 作废考勤（refund 流水 + 考勤标记 reversed），
                       日志由服务端按撤销语义隐藏对应签到记录 */
                    await v1Api(`/attendance/${exactEntry.attendanceId}/void`, {
                        method: 'POST',
                        body: JSON.stringify({note: '管理员撤销'}),
                    });
                    await load();
                } else {
                    const idx = db.logs.findIndex(l=>(l.studentId===sid || (!l.studentId && l.studentName===sname))&&l.action==='上课签到');   /* D3 */
                    if (idx===-1) { showToast('未找到签到记录','warn'); return; }
                    const ns = db.students.map(s=>s.id===sid?{...s,balance:(parseInt(s.balance,10)||0)+1}:s);
                    const nl = db.logs.filter((_,i)=>i!==idx);
                    const ok = await save({...db, students:ns, logs:[mkLog(sname,'撤销签到','+1','管理员撤销',0,{studentId:sid}),...nl]});
                    if (!ok) return;
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
        setScheduleLoadError('');
        try {
            const d = await v1Api('/class-schedules');
            setSchedules(d.schedules || []);
        } catch (e) { setScheduleLoadError(`固定课表加载失败：${e.message}`); }
        /* Courses are optional furniture for the editor, not the roster. A
           failure here must not blank the schedule list — the dropdown just
           falls back to "不关联课程". */
        await loadCourses();
        try {
            const b = await v1Api('/class-bookings');
            setBookings(b.bookings || []);
        } catch { setBookings([]); }
        try {
            const dash = await v1Api('/dashboard');
            setBizStats((dash.dashboard || {}).business || null);
        } catch (e) {
            setScheduleLoadError(current=>current || `经营数据加载失败：${e.message}`);
        }
    };

    /* Server-recorded operations, for the log page. /v1/audit-logs is
       owner-scoped (it can expose staff-initiated refunds and exports), so a
       403 for other roles is expected and leaves the ledger-only view intact
       rather than surfacing an error they cannot act on. */
    const loadAuditEvents = async () => {
        if (!TENANT_SLUG) return;
        try {
            const d = await v1Api('/audit-logs?limit=200');
            setAuditEvents(d.auditLogs || []);
        } catch { setAuditEvents([]); }
    };

    /* B2: 判断两个班次在同一 weekday 是否时间重叠 */
    const schedOverlap = (a, b) => {
        if (Number(a.weekday) !== Number(b.weekday)) return false;
        const toMin = (t) => { const [h,m] = String(t).split(':').map(Number); return h*60+(m||0); };
        const aS = toMin(a.startTime), aE = aS + (Number(a.durationMinutes)||60);
        const bS = toMin(b.startTime), bE = bS + (Number(b.durationMinutes)||60);
        return aS < bE && bS < aE;
    };

    /* v8.8.0: 时间重叠不等于冲突 —— 冲突是「同一个老师被排在两处」。
       在有老师之前，只比时间是唯一能比的东西。加上老师之后，只比时间同时
       变得太松（同一位老师撞课不报）和太紧（两位老师同一时段误报）。而一个
       每次保存都跳出来的提示，很快就会被当成必经的一步点掉 ——
       一个总是误报的警告等于没有警告。
       两边都没指定老师时，退回旧行为：无从判断，宁可提醒。 */
    const schedClash = (a, b) => {
        if (!schedOverlap(a, b)) return false;
        const at = a.teacherUserId || '', bt = b.teacherUserId || '';
        if (!at && !bt) return true;
        return at !== '' && at === bt;
    };

    const saveSchedule = async (conflictConfirmed=false) => {
        if (!schedEdit || busy) return;
        if (!schedEdit.label.trim()) { showToast('请输入班次名称（如：周三素描班）', 'error'); return; }
        /* B2-①: 同一位老师被排在两处时给确认提示（v5.2，v8.8.0 改按老师判定） */
        const clash = schedules.find(sc => sc.id !== schedEdit.id && schedClash(sc, schedEdit));
        if (clash && !conflictConfirmed) {
            const who = clash.teacherUserId && clash.teacherUserId === schedEdit.teacherUserId
                ? `${clash.teacherName || '同一位老师'}同时段已排「${clash.label}」`
                : `与「${clash.label}」（${WEEKDAYS[clash.weekday]} ${clash.startTime}）时段重叠`;
            confirm(
                `「${schedEdit.label.trim()}」${who}，仍要保存吗？`,
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
                courseId: schedEdit.courseId || '',
                teacherUserId: schedEdit.teacherUserId || '',
                isPublic: !!schedEdit.isPublic,
                room: (schedEdit.room || '').trim(),
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
        confirm(`删除固定班次「${sc.label}」后，之后的日期不会再自动排入这批学员。\n\n已经排过的日期、已签到的记录和学员课时都不受影响。`, async () => {
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

    /* v8.8.0: 可被指定为授课老师的成员。Owner 也在其中 —— 很多工作室
       就是主理人自己在上课，把 Owner 排除掉会让最常见的情况反而做不到。 */
    const teachableMembers = useMemo(
        () => team.filter(m => m.status === 'active' && ['owner','manager','teacher'].includes(m.role)),
        [team]);

    /* 该班次下一次上课的日期（含今天），停课表和「本周停课」都以它为默认值。 */
    const nextOccurrence = (weekday) => {
        const today = new Date(`${todayISO()}T12:00:00`);
        const delta = (Number(weekday) - today.getDay() + 7) % 7;
        const d = new Date(today.getTime() + delta * 86400000);
        return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    };

    const saveCancellation = async () => {
        if (!schedCancel || busy) return;
        setBusy(true);
        try {
            const d = await v1Api(`/class-schedules/${schedCancel.id}/cancellations`, {
                method: 'POST',
                body: JSON.stringify({date: schedCancel.date, note: (schedCancel.note||'').trim()}),
            });
            setSchedules(d.schedules || []);
            setSchedCancel(null);
            showToast('已标记停课');
        } catch (e) { showToast(`标记停课失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const restoreCancellation = async (sc, date) => {
        if (busy) return;
        setBusy(true);
        try {
            const d = await v1Api(`/class-schedules/${sc.id}/cancellations/${date}`, {method:'DELETE'});
            setSchedules(d.schedules || []);
            showToast(`${date} 恢复上课`);
        } catch (e) { showToast(`恢复失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const loadCourses = async () => {
        try {
            const c = await v1Api('/courses');
            setCourses((c.courses || []).filter(x => x.is_active !== false));
        } catch { setCourses([]); }
    };

    const saveCourse = async () => {
        if (!courseEdit || busy) return;
        const name = (courseEdit.name || '').trim();
        if (!name) { showToast('请填写课程名称', 'warn'); return; }
        setBusy(true);
        try {
            const body = JSON.stringify({
                name,
                description: (courseEdit.description || '').trim(),
                ageRange: (courseEdit.ageRange || '').trim(),
                durationMinutes: Number(courseEdit.durationMinutes) || 60,
                /* 接口收的是元，服务端转成分存。价格留空就是 0 —— 不是每家
                   工作室都想在课程上标价，公开课表的价格开关默认也是关的。 */
                priceAud: courseEdit.priceAud === '' ? 0 : Number(courseEdit.priceAud) || 0,
            });
            if (courseEdit.id) await v1Api(`/courses/${courseEdit.id}`, {method: 'PATCH', body});
            else                await v1Api('/courses', {method: 'POST', body});
            await loadCourses();
            setCourseEdit(null);
            showToast(courseEdit.id ? '课程已更新' : '课程已添加');
        } catch (e) { showToast(`保存失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const archiveCourse = (course) => {
        /* 归档，不是删除。已经排过这门课的班次、已经按它记过的账都还在引用它，
           真删掉会让历史记录指向一个不存在的东西。 */
        const used = schedules.filter(sc => sc.courseId === course.id);
        confirm(
            `归档课程「${course.name}」后，它不会再出现在新排课的下拉里。`
            + (used.length ? `\n\n注意：目前有 ${used.length} 个班次正在关联它，那些班次不受影响，公开课表仍会显示这门课的名称。` : '')
            + '\n\n已有的排课、账目和历史记录都不受影响。',
            async () => {
                if (busy) return;
                setBusy(true);
                try {
                    await v1Api(`/courses/${course.id}`, {method: 'DELETE'});
                    await loadCourses();
                    showToast(`课程「${course.name}」已归档`, 'warn');
                } catch (e) { showToast(`归档失败：${e.message}`, 'error'); }
                finally { setBusy(false); }
            },
            {danger: true, confirmText: '确认归档'});
    };

    const resetPackageEditor = () => {
        setPkgEditId(null); setPkgName(''); setPkgCredits(''); setPkgPrice('');
    };
    const savePackage = async () => {
        if (busy) return;
        if (!pkgName.trim() || !pkgCredits || !pkgPrice) { showToast('请填写套餐名称、课时数和价格', 'warn'); return; }
        const credits = parseInt(pkgCredits, 10);
        const price = parseFloat(pkgPrice);
        if (!Number.isFinite(credits) || credits < 1 || !Number.isFinite(price) || price < 0) { showToast('课时数必须大于 0，价格不能为负数', 'warn'); return; }
        const packages = pkgEditId === 0
            ? [...(db.packages || []), {id:Date.now(), name:pkgName.trim(), credits, price}]
            : (db.packages || []).map(pkg => pkg.id === pkgEditId ? {...pkg, name:pkgName.trim(), credits, price} : pkg);
        const ok = await save({...db, packages});
        if (!ok) return;
        const adding = pkgEditId === 0;
        resetPackageEditor();
        showToast(adding ? '套餐已添加' : '套餐已更新');
    };
    const archivePackage = (pkg) => {
        if ((db.packages || []).length <= 1) { showToast('至少保留一个套餐', 'warn'); return; }
        confirm(`删除套餐「${pkg.name}」？已有充值记录不会被删除。`, async () => {
            const ok = await save({...db, packages:(db.packages || []).filter(item => item.id !== pkg.id)});
            if (ok) showToast('套餐已删除', 'warn');
        }, {danger:true, confirmText:'删除套餐'});
    };

    const reviewBooking = async (bk, status) => {
        if (busy) return;
        setBusy(true);
        try {
            const d = await v1Api(`/class-bookings/${bk.id}`, {
                method: 'PATCH', body: JSON.stringify({status}),
            });
            setBookings(d.bookings || []);
            if (status === 'approved') {
                /* 批准之后名单变了，当日排课要重新拉一次，否则前台看到的是
                   批准之前的那一份。 */
                await load();
                showToast(bk.isExistingStudent
                    ? `已批准，${bk.matchedStudent || bk.contactName} 已排入 ${bk.date}`
                    : '已批准，并已建立一条待审核报名');
            } else {
                showToast('已婉拒这条申请', 'warn');
            }
        } catch (e) { showToast(`处理失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    /* 模板 → 每周班次：把常用班组一键升级为周期课表 */
    const groupToSchedule = () => {
        const ids = (db.groups || {})[grpSel] || [];
        if (!grpSel || !ids.length) { showToast('请先选择一个班组模板', 'warn'); return; }
        setSchedEdit({label: grpSel, weekday: new Date().getDay(), startTime: defaultClassTime,
                      durationMinutes: 60, capacity: Math.max(10, ids.length), studentIds: ids,
                      courseId: '', teacherUserId: '', isPublic: false, room: ''});
        showToast('已带入模板学员，请确认周几与时间后保存');
    };

    const addDailyRosterStudents = async (date, studentIds, source='manual', status='scheduled', extra={}) => {
        if (!TENANT_SLUG) return null;
        const data = await v1Api('/daily-roster', {
            method:'POST',
            body:JSON.stringify({date, studentIds, source, status, ...extra}),
        });
        await load();
        return data;
    };

    /* The correction path: move a student's slot without re-adding them, which
       would reset source and status. */
    const updateRosterEntry = async (entryId, patch) => {
        if (!TENANT_SLUG || !entryId) return null;
        const data = await v1Api(`/daily-roster/${entryId}`, {
            method:'PATCH', body:JSON.stringify(patch),
        });
        await load();
        return data;
    };

    /* Slot metadata for one student on the currently viewed date. */
    const rosterMetaFor = (date, sid) => (db.rosterEntries?.[date] || {})[sid] || {};
    const rosterSlotFor = (date, sid) => {
        const explicit = rosterMetaFor(date, sid).classTime;
        if (explicit) return explicit;
        const weekday = new Date(`${date}T12:00:00`).getDay();
        return schedules.find(schedule =>
            schedule.weekday === weekday && schedule.students.some(student => student.id === sid)
        )?.startTime || '';
    };

    /* The old control was `<a href="…calendar.ics" download>`. A plain
       navigation carries no X-Requested-With header and is not a fetch, so the
       authenticated endpoint answered 401 with a JSON body — and the browser
       saved that JSON as the "calendar" file. Hence the garbled download.
       Fetching with credentials and turning the response into a blob is the
       only way to download from an authenticated endpoint. */
    const CALENDAR_KINDS = Object.freeze({
        roster: {serverKind:'daily-roster', previewPath:'/daily-roster/calendar', downloadPath:'/daily-roster/calendar.ics'},
        schedule: {serverKind:'weekly-schedules', previewPath:'/class-schedules/calendar', downloadPath:'/class-schedules/calendar.ics'},
    });
    const calendarContract = kind => {
        const contract = CALENDAR_KINDS[kind];
        if (!contract) throw new Error('未知的日历导出类型，请刷新页面后重试');
        return contract;
    };
    const calendarPreviewPath = (kind, rosterDate=rDate) => {
        const contract = calendarContract(kind);
        return kind === 'roster'
            ? `${contract.previewPath}?date=${encodeURIComponent(rosterDate)}`
            : contract.previewPath;
    };

    const fetchIcsPreview = async (kind, rosterDate=rDate) => {
        const data = await v1Api(calendarPreviewPath(kind, rosterDate));
        const calendar = data.calendar || {};
        if (!/^[0-9a-f]{64}$/.test(calendar.revision || '')) {
            throw new Error('日历预览缺少有效版本，请刷新页面后重试');
        }
        const contract = calendarContract(kind);
        if (calendar.kind !== contract.serverKind) {
            throw new Error('日历预览类型与下载类型不一致，请刷新页面后重试');
        }
        /* Keep the UI endpoint selector separate from the server-owned document
           kind. The old `{kind, ...calendar}` merge silently replaced `roster`
           with `daily-roster`, so both buttons downloaded the weekly endpoint. */
        return {...calendar, downloadKind:kind};
    };

    const openIcsPreview = async (kind) => {
        setIcsBusy(true);
        setIcsNotice('');
        try {
            setIcsPreview(await fetchIcsPreview(kind));
        } catch (err) {
            showToast(err.message || '日历预览加载失败', 'error');
        } finally { setIcsBusy(false); }
    };

    const downloadIcs = async (preview) => {
        setIcsBusy(true);
        try {
            const kind = preview?.downloadKind;
            const contract = calendarContract(kind);
            const revision = preview?.revision || '';
            if (!/^[0-9a-f]{64}$/.test(revision)) {
                throw new Error('日历预览版本无效，请关闭后重新预览');
            }
            const query = new URLSearchParams({revision});
            if (kind === 'roster') query.set('date', preview.date || rDate);
            const path = `${contract.downloadPath}?${query}`;
            const r = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1${path}`, {
                credentials:'include', headers:{'X-Requested-With':'StudioSaaS'},
            });
            if (!r.ok) {
                const detail = await r.json().catch(() => ({}));
                if (r.status === 409 && detail.error === 'calendar_revision_conflict') {
                    setIcsPreview(await fetchIcsPreview(kind, preview.date || rDate));
                    setIcsNotice('排课刚刚发生变化，预览已自动刷新。请核对后再次下载。');
                    return;
                }
                throw new Error(detail.message || detail.error || `下载失败（HTTP ${r.status}）`);
            }
            const type = r.headers.get('Content-Type') || '';
            /* Guard the exact failure this replaced: if the endpoint answers
               with JSON we must not hand the visitor a .ics full of it. */
            if (!type.includes('calendar')) throw new Error('服务器未返回日历文件，请重新登录后再试');
            const blob = await r.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            /* The server names the file on the CalendarDocument; a name invented
               here is how a roster export ended up called weekly-classes.ics. */
            a.download = preview.filename
                || r.headers.get('Content-Disposition')?.match(/filename="?([^";]+)"?/)?.[1]
                || (kind === 'roster' ? `roster-${rDate}.ics` : 'calendar.ics');
            document.body.appendChild(a); a.click(); a.remove();
            setTimeout(()=>URL.revokeObjectURL(url), 1000);
            setIcsPreview(null);
            setIcsNotice('');
            showToast('日历文件已下载');
        } catch (err) {
            showToast(err.message || '下载失败', 'error');
        } finally { setIcsBusy(false); }
    };

    const saveDefaultClassTime = async () => {
        if (operationalSettingsBusy) return;
        if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(defaultClassTimeDraft)) {
            showToast('默认上课时间必须是有效的 HH:MM', 'error');
            return;
        }
        setOperationalSettingsBusy(true);
        try {
            const data = await v1Api('/operational-settings', {
                method:'PATCH',
                body:JSON.stringify({defaultClassTime:defaultClassTimeDraft}),
            });
            const saved = data.defaultClassTime;
            setDefaultClassTime(saved);
            setDefaultClassTimeDraft(saved);
            setRTime(saved);
            showToast(`默认上课时间已设为 ${saved}`);
        } catch (error) {
            showToast(`默认时间保存失败：${error.message}`, 'error');
        } finally { setOperationalSettingsBusy(false); }
    };

    /** Copy a date-bound roster summary without exposing it to a remote service. */
    const copyRosterDaily = () => {
        const lines = dayIds.map(id=>{
            const student=db.students.find(item=>item.id===id);
            return student&&!student.archived?`${student.name}（剩余${student.balance}课时）`:null;
        }).filter(Boolean);
        copyText(`【今日上课 ${lines.length} 人 - ${fmtDate(rDate)}】\n${lines.join('\n')}`,'日报已复制到剪贴板');
    };

    /** Copy one message per reachable student, preserving the selected roster date and slot. */
    const copyRosterReminders = () => {
        const lines=dayIds.map(id=>{
            const student=db.students.find(item=>item.id===id);
            if(!student||student.archived||!student.mobile)return null;
            const slot=rosterSlotFor(rDate,id);
            return `${student.name}（${student.mobile}）\n提醒：您的上课时间是 ${fmtDate(rDate)}${slot?` ${slot}`:''}，请准时到课。${tenantDisplayName} 期待见到您！`;
        }).filter(Boolean);
        copyText(lines.join('\n\n'),`已复制 ${lines.length} 条提醒内容`);
    };

    const batchCheckIn = () => {
        const ids     = dayIds;
        const already = ids.filter(id => rosterDone.has(id)).length;
        const archived = ids.filter(id => db.students.find(x=>x.id===id)?.archived).length;
        const insufficient = ids.filter(id => {
            const s=db.students.find(x=>x.id===id);
            return s&&!s.archived&&s.balance<=0&&!rosterDone.has(id);
        }).length;
        const elig    = ids.filter(id => { const s=db.students.find(x=>x.id===id); return s&&!s.archived&&s.balance>0&&!rosterDone.has(id); });
        if (!elig.length) { showToast(already ? '今日排课学员均已签到 ✓' : '今日无可签到/消课学员', 'warn'); return; }
        confirm(`批量签到确认：排课 ${ids.length} 人；已签到 ${already} 人；余额不足 ${insufficient} 人；已归档 ${archived} 人；本次实际执行 ${elig.length} 人。`, async () => {
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
                    const succeeded=elig.length-failed.length;
                    if (failed.length) showToast(`批量签到完成：成功 ${succeeded} 人，失败 ${failed.length} 人（${failed.join('、')}）`, 'warn');
                    else showToast(`批量签到完成：实际成功 ${succeeded} 人`);
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
                    const ok = await save(cur);
                    if (!ok) return;
                    showToast(`批量签到/消课完成，共 ${elig.length} 人`);
                }
            } finally { setBusy(false); }
        }, {confirmText:`签到/消课 ${elig.length} 人`});
    };

    /* F4b: 班组模板 — 保存常用班次组合，任意日期一键套用 */
    const saveGroup = () => {
        const ids = db.rosters[rDate]||[];
        if (!ids.length) { showToast('当前日期没有排课可保存', 'warn'); return; }
        confirm(`将当前日期的 ${ids.length} 位学员保存为可复用的班组模板。`, async (raw) => {
            const name = String(raw||'').trim();
            if (!name) return;
            const ok = await save({...db, groups: {...(db.groups||{}), [name]: ids}});
            if (!ok) return;
            showToast(`模板「${name}」已保存（${ids.length} 人）`);
        }, {title:'保存班组模板', prompt:true, promptRequired:true,
            promptLabel:'模板名称', promptPlaceholder:'如：周六上午班', confirmText:'保存模板'});
    };
    const applyGroup = async () => {
        if (!grpSel) return;
        const ids = (db.groups||{})[grpSel]||[];
        const cur = db.rosters[rDate]||[];
        const add = ids.filter(id => !cur.includes(id) && db.students.some(s=>s.id===id&&!s.archived));
        if (!add.length) { showToast('模板学员均已在当前排课中', 'warn'); return; }
        /* A group template is a set of students who sit the same slot, so the
           studio default applies to the whole batch. */
        if (TENANT_SLUG) await addDailyRosterStudents(rDate, add, 'group', 'scheduled',
            {classTime: rTime || defaultClassTime || null});
        else { const ok = await save({...db, rosters: {...db.rosters, [rDate]: [...cur, ...add]}}); if (!ok) return; }
        showToast(`已套用「${grpSel}」，新增 ${add.length} 人`);
    };
    const deleteGroup = () => {
        if (!grpSel) return;
        confirm(`删除班组模板「${grpSel}」后，将无法再一键套用这组学员。\n\n已经用它排过的课、学员档案和课时都不受影响。`, async () => {
            const g = {...(db.groups||{})}; delete g[grpSel];
            const ok = await save({...db, groups: g});
            if (!ok) return;
            setGrpSel('');
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
            /* Without a time the entry lands with class_time NULL and the day
               shows the student under no slot at all. The weekly schedule wins
               when it already places them; otherwise the studio's configured
               default is the same time the roster page's own add box uses. */
            if (TENANT_SLUG) await addDailyRosterStudents(date, [student.id], 'profile', 'scheduled',
                {classTime: rosterSlotFor(date, student.id) || defaultClassTime || null});
            else { const ok = await save({...db, rosters:{...db.rosters, [date]: [...cur, student.id]}}); if (!ok) return; }
            showToast(`${student.name} 已加入今日排课`);
        } finally { setBusy(false); }
    };

    /* G3: 学员成长报告 — 生成图文报告页（新窗口，可保存为 PDF / 截图发家长） */
    const openGrowthReport = (s) => {
        const logs = db.logs.filter(l => l.studentId===s.id || (!l.studentId && l.studentName===s.name));
        const parseD = (d) => { const m=String(d).match(/^(\d{2})\/(\d{2})\/(\d{4})/); return m?new Date(`${m[3]}-${m[2]}-${m[1]}`):null; };
        const checkins = logs.filter(l=>l.action==='上课签到');
        const dates    = logs.map(l=>parseD(l.date)).filter(Boolean).sort((a,b)=>a-b);
        const explicitJoinDate = /^\d{4}-\d{2}-\d{2}$/.test(String(s.enrollmentDate||''))
            ? new Date(`${s.enrollmentDate}T12:00:00`)
            : null;
        const joinDate = explicitJoinDate && explicitJoinDate <= new Date()
            ? explicitJoinDate
            : (dates.length ? dates[0] : null);
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
        const reportBrand = tenantBrand || {};
        const reportSlogan = reportBrand.slogan || 'Learn, grow, and feel confident.';
        const reportStudioName = reportBrand.name || tenantDisplayName || 'Studio';
        const reportLogoUrl = tenantLogoUrl;
        const safeReportColor = (value, fallback) => /^#[0-9a-f]{6}$/i.test(String(value||'')) ? String(value) : fallback;
        const reportAccent = safeReportColor(reportBrand.primary_color||reportBrand.primaryColor, '#b08d57');
        const reportAccentDark = safeReportColor(reportBrand.secondary_color||reportBrand.secondaryColor, '#6f5b3e');
        /* C5: 零数据兜底 — 新学员尚无记录时用欢迎语 */
        const isNew = checkins.length === 0;
        const shareMsg = isNew
            ? `欢迎 ${s.name} 加入 ${reportStudioName}！学习旅程刚刚启程，期待记录每一份成长与快乐。`
            : `${s.name} 在 ${reportStudioName} 已经学习了 ${days} 天，累计上课 ${checkins.length} 次，完成${workNoun} ${port.length} 份！每一次练习都是成长的印记，期待继续陪伴 TA 自信探索。`;

        const portHTML = port.length ? port.map(p=>`
            <figure class="art">
                <img src="${portfolioImgSrc(s.id, p)}" alt="作品"/>
                <figcaption>${esc(p.note)||'　'}<span>${esc((p.date||'').split('-').reverse().join('/'))}</span></figcaption>
            </figure>`).join('') : `<p class="empty">暂无${workNoun}记录 · 上传后报告会更精彩</p>`;

        /* C3: 柱高直接算像素（上限 76px），数字标签固定占位不再被顶出 */
        const barsHTML = months.map(m=>`
            <div class="bar"><span class="bn">${m.n||''}</span><div class="fill" style="height:${Math.max(3,Math.round(m.n/maxM*76))}px"></div><span class="bl">${m.l}</span></div>`).join('');

	        const photoHTML = s.photo ? `<img class="avatar" src="${mediaSrc(s.photo)}" alt=""/>`
	            : `<div class="avatar ph">${esc((s.name||'?').slice(0,1))}</div>`;
	        const reportJoinText = reportBrand.category === 'art'
	            ? '艺术之旅刚刚启程'
	            : '学习旅程刚刚启程';

	        /* C6+v4.3.2: 暖色美术馆风 — 暖米白展墙 + 金铜强调色，作品做彩色主角 */
        const html = `<!doctype html><html lang="zh"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>${esc(s.name)} · 成长报告 · ${esc(reportStudioName)}</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
:root{--accent:${reportAccent};--accent-dark:${reportAccentDark}}
body{font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#efeae2;color:#3a3a44;padding:24px}
.sheet{max-width:760px;margin:0 auto;background:#fffdf9;border-radius:18px;overflow:hidden;box-shadow:0 10px 36px rgba(60,50,40,.10)}
.brandbar{display:flex;flex-direction:column;align-items:center;gap:7px;padding:32px 30px 18px}
.brandbar img{height:86px;width:auto}
.slogan{font-family:'Snell Roundhand','Savoye LET','Brush Script MT',cursive;font-size:20px;color:var(--accent)}
.hero{display:flex;align-items:center;gap:22px;padding:6px 36px 26px;border-bottom:1px solid #ece6db}
.avatar{width:90px;height:90px;border-radius:50%;object-fit:cover;border:3px solid #e6ddcd;flex-shrink:0}
.avatar.ph{display:flex;align-items:center;justify-content:center;font-size:38px;font-weight:800;background:#f0ece4;color:#6f6f7c}
.hero h1{font-size:28px;color:#2f2c33;margin-bottom:5px}
.hero .sub{color:#8a857d;font-size:14px}
.hero .sub b{color:var(--accent)}
.hero .tag{display:inline-block;font-size:11px;letter-spacing:2px;color:var(--accent);text-transform:uppercase;margin-bottom:7px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;padding:24px 36px;background:#faf7f1}
.stat{text-align:center;break-inside:avoid}
.stat .v{font-size:30px;font-weight:800;color:var(--accent);line-height:1}
.stat .l{font-size:12px;color:#9a958c;margin-top:6px}
.sec{padding:24px 36px;border-top:1px solid #ece6db;break-inside:avoid;page-break-inside:avoid}
.sec.gal{break-inside:auto;page-break-inside:auto}
.sec h2{font-size:15px;margin-bottom:16px;color:#4a4751;letter-spacing:.5px;display:flex;align-items:center;gap:7px}
.chart{display:flex;align-items:flex-end;gap:16px;padding-top:4px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end}
.bn{font-size:12px;font-weight:700;color:var(--accent);height:18px}
.fill{width:58%;background:#c4ad84;border-radius:5px 5px 0 0}
.bl{font-size:11px;color:#a8a299;margin-top:7px}
.gallery{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.art{border-radius:12px;overflow:hidden;background:#f7f4ee;border:1px solid #ece6db;break-inside:avoid;page-break-inside:avoid}
.art img{width:100%;height:150px;object-fit:cover;display:block}
.art figcaption{font-size:12px;color:#5b5750;padding:8px 10px;display:flex;flex-direction:column;gap:2px}
.art figcaption span{font-size:11px;color:#a8a299}
.empty{color:#a8a299;text-align:center;padding:24px;font-size:14px}
.msg{background:#faf6ee;border-left:3px solid var(--accent);border-radius:0 12px 12px 0;padding:18px 22px;font-size:15px;line-height:1.8;color:#4a4751}
.foot{text-align:center;padding:22px;color:#aba89f;font-size:12px}
.foot .fslogan{font-family:'Snell Roundhand','Savoye LET','Brush Script MT',cursive;font-size:16px;color:var(--accent);margin-bottom:4px}
.toolbar{max-width:760px;margin:0 auto 16px;display:flex;gap:10px;justify-content:flex-end}
.toolbar button{border:0;border-radius:12px;padding:11px 18px;font-size:14px;font-weight:700;cursor:pointer}
.b1{background:var(--accent-dark);color:#fff}.b2{background:#fffdf9;color:var(--accent-dark);border:1px solid #ddd0bb}
@media print{body{background:#fff;padding:0}.toolbar{display:none}.sheet{box-shadow:none;border-radius:0}}
@media(max-width:560px){.stats{grid-template-columns:repeat(2,1fr)}.gallery{grid-template-columns:repeat(2,1fr)}.hero{padding:6px 22px 22px}.sec{padding:20px 22px}}
</style></head><body>
<div class="toolbar">
  <button class="b2" id="copybtn" className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>复制成长寄语</button>
  <button class="b1" onclick="window.print()" className="inline-flex items-center gap-1.5"><Icon name="printer" className="w-4 h-4"/>保存为 PDF / 打印</button>
</div>
<div class="sheet">
  <div class="brandbar">
    <img src="${esc(reportLogoUrl)}" alt="${esc(reportStudioName)}"/>
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
    <h2 className="inline-flex items-center gap-1.5"><Icon name="trend" className="w-4 h-4"/>近 6 个月上课足迹</h2>
    <div class="chart">${barsHTML}</div>
  </div>
  <div class="sec gal">
    <h2 className="inline-flex items-center gap-1.5"><Icon name="image" className="w-4 h-4"/>作品集（${port.length} 幅）</h2>
    <div class="gallery">${portHTML}</div>
  </div>
  <div class="sec">
    <h2 className="inline-flex items-center gap-1.5"><Icon name="heart" className="w-4 h-4"/>老师寄语</h2>
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
            archive
                ? `${sname} 会移出日常名单，不再出现在排课和搜索结果里。\n\n课时、上课记录和作品都完整保留，在「归档库」筛选下随时可以恢复。`
                : `${sname} 会回到日常名单，可以正常排课和签到。\n\n课时余额和历史记录保持原样。`,
            async () => {
                if (busy) return; // Fix ④
                setBusy(true);
                try {
                    const ns = db.students.map(s=>s.id===sid?{...s,archived:archive}:s);
                    const ok = await save({...db, students:ns, logs:[mkLog(sname,archive?'归档学员':'恢复学员','0',archive?'移入归档库':'从归档库恢复',0,{studentId:sid}),...db.logs]});
                    if (!ok) return;
                    setSelS(null); setEditP(false);
                    showToast(`${sname} 已${archive?'归档':'恢复'}`, 'warn');
                } finally { setBusy(false); }
            },
            {confirmText: archive?'确认归档':'确认恢复'}
        );
    };

    /* P2-14: bulk equivalents of the two things operators actually do in
       batches. Archiving is confirmed once for the whole set rather than
       student by student, and writes one log line per student as before. */
    const copySelectedReminders = () => {
        if (!selectedStudents.length) return;
        const lines = selectedStudents.map(s => renderMessage('renewal',
            '{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。',
            {student:s.name, balance:s.balance, note:(parseInt(s.balance,10)||0)===0?'（已用完）':''}));
        copyText(lines.join('\n\n'), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
    };
    const archiveSelected = () => {
        const targets = selectedStudents.filter(s => !s.archived);
        if (!targets.length) { showToast('所选学员均已归档', 'warn'); return; }
        confirm(`${targets.length} 名学员会移出日常名单，不再出现在排课和搜索结果里。\n\n课时、上课记录和作品都完整保留，在「归档库」筛选下随时可以恢复。`, async () => {
            if (busy) return;
            setBusy(true);
            try {
                const ids = new Set(targets.map(s => s.id));
                const ns = db.students.map(s => ids.has(s.id) ? {...s, archived:true} : s);
                const logs = targets.map(s => mkLog(s.name,'归档学员','0','批量移入归档库',0,{studentId:s.id}));
                const ok = await save({...db, students:ns, logs:[...logs, ...db.logs]});
                if (!ok) return;
                setSelectedStudentIds([]);
                showToast(`已归档 ${targets.length} 名学员`, 'warn');
            } finally { setBusy(false); }
        }, {confirmText:`归档 ${targets.length} 人`, danger:true});
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
                    const ok = await save({...db, students:ns, logs:[mkLog(s.name,'充值购课',`+${credits}`,noteStr,fee,{payMethod:tuPay,studentId:s.id}),...db.logs]});
                    if (!ok) return;
                }
                e.target.reset();
                setTuCr(''); setTuFee(''); setTuPkg('');
                setTuPay('微信'); setTuStu(null);
                /* G2: 充值确认话术 */
                const newBal = (parseInt(s.balance,10)||0)+credits;
                const cMsg = renderMessage('topup',
                    '{student} 您好！已为您成功充值 {credits} 课时{fee}，当前账户共 {balance} 课时。感谢您对 {studio} 的信任！',
                    {student:s.name, credits, fee: fee ? `（实收 $${fee}）` : '', balance:newBal});
                showToast(`${s.name} 充值 ${credits} 课时 / $${fee}`, 'success',
                    {label:'复制充值确认（发家长）', onClick:()=>copyText(cMsg,'充值确认已复制')});
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
        /* E: mirrors backend credits:refund — the toggle is hidden for other
           roles, this guard covers any stale settleMode state */
        if (!canRefund) { showToast('当前角色无退款权限', 'error'); return; }
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
                    {label:'复制退款确认（发家长）', onClick:()=>copyText(cMsg,'退款确认已复制')});
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
        const enrollmentDate = (fd.get('enrollmentDate') || todayISO()).trim();
        const doCreate = async () => {
            if (busy) return; setBusy(true);
            try {
                const ns = {id:Date.now(), firstName, lastName, name:fullName,
                            mobile, email, wechat, photo:formPhoto, preferences, ...legacyPrefs,
                            birthday, enrollmentDate, balance, remark, lastActive:todayISO(), archived:false};
                const ok = await save({...db, students:[ns,...db.students], logs:[mkLog(fullName,'新生注册',`+${balance}`,'系统建档',0,{studentId:ns.id}),...db.logs]});
                if (!ok) return;
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
            const enrollmentDate = (fd.get('enrollmentDate') || '').trim();
            const diff    = balance - (parseInt(selS.balance,10)||0);
            const oldName = selS.name;
            const ns = db.students.map(s => s.id===selS.id
                ? {...s, firstName, lastName, name:newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, enrollmentDate, photo:editPhoto, ...(diff!==0?{lastActive:todayISO()}:{})}
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
            const enrollmentDateChanged = enrollmentDate !== (selS.enrollmentDate||'');
            const noteStr   = diff!==0 ? '管理端校准' : (oldName!==newName?`改名: ${oldName}→${newName}`:enrollmentDateChanged?`入学日期: ${selS.enrollmentDate||'未设置'}→${enrollmentDate||'未设置'}`:'信息修改');
            if (TENANT_SLUG) {
                /* A2: 档案字段照旧整包保存（余额由服务端忽略）；
                   课时差额单独走 v1 调整流水 */
                const ok = await save({...db, students:ns, logs:nl});
                if (!ok) return;
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
                const ok = await save({...db, students:ns, logs:[mkLog(newName, diff!==0?'调整课时':'更新档案', changeStr, noteStr, 0, {studentId:selS.id}),...nl]});
                if (!ok) return;
            }
            setSelS({...selS, firstName, lastName, name:newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, enrollmentDate, photo:editPhoto, ...(diff!==0?{lastActive:todayISO()}:{})});
            setEditP(false);
            showToast('档案已更新');
        } finally { setBusy(false); }
    };

    const handleDelete = (sid, sname) => {
        confirm(`此操作不可撤销。\n\n将永久删除 ${sname} 的学员档案与全部排课记录。历史操作日志会保留（用于审计），但档案本身无法恢复。\n\n如果只是想让 TA 不再出现在名单里，请改用「归档」——归档随时可以恢复。`, async () => {
            if (busy) return; // Fix ④
            setBusy(true);
            try {
                const ns = db.students.filter(s=>s.id!==sid);
                const nr = {...db.rosters};
                Object.keys(nr).forEach(d => { nr[d]=nr[d].filter(id=>id!==sid); });
                const ok = await save({...db, students:ns, rosters:nr, logs:[mkLog(sname,'彻底删除档案','0','管理员移除',0,{studentId:sid}),...db.logs]});
                if (!ok) return;
                setSelS(null); setEditP(false);
                showToast(`${sname} 已移除`, 'warn');
            } finally { setBusy(false); }
        }, {danger:true, confirmText:'永久删除'});
    };

    const patchSelectedStudent = (patch) => {
        setSelS(current => current ? {...current, ...patch} : current);
        setDb(current => ({
            ...current,
            students: current.students.map(student => student.id===selS?.id ? {...student, ...patch} : student),
        }));
    };

    const generateStudentAccessCode = async () => {
        if (!selS || !TENANT_SLUG) return;
        setBusy(true);
        try {
            const data = await v1Api(`/students/${encodeURIComponent(selS.id)}/access-code`, {
                method:'POST', body:'{}'
            });
            setAccessCodeResult({studentId:selS.id, code:data.code});
            patchSelectedStudent({hasAccessCode:true, accessCodeUpdatedAt:data.updatedAt});
            showToast('学员专区访问码已生成；明文只显示这一次');
        } catch (e) { showToast(`访问码生成失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const revokeStudentAccessCode = () => {
        if (!selS || !TENANT_SLUG) return;
        confirm(`${selS.name} 当前的访问码会立即作废，已登录的会话也会马上退出，家长将无法再查询课时与记录。\n\n之后可以随时重新生成一个新访问码交给家长。`, async () => {
            setBusy(true);
            try {
                await v1Api(`/students/${encodeURIComponent(selS.id)}/access-code`, {method:'DELETE'});
                setAccessCodeResult(null);
                patchSelectedStudent({hasAccessCode:false, accessCodeUpdatedAt:null});
                showToast('学员专区已停用', 'warn');
            } catch (e) { showToast(`停用失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger:true, confirmText:'停用专区'});
    };

    const savePublicationConsent = async () => {
        if (!selS || !consentEdit || consentEdit.mode!=='confirm') return;
        if (!consentEdit.by.trim() || !consentEdit.relationship || !consentEdit.method) {
            showToast('请填写授权人、关系和授权方式', 'warn'); return;
        }
        setBusy(true);
        try {
            const data = await v1Api(`/students/${encodeURIComponent(selS.id)}/publication-consent`, {
                method:'PUT',
                body:JSON.stringify({
                    consentBy:consentEdit.by,
                    relationship:consentEdit.relationship,
                    consentMethod:consentEdit.method,
                    noticeVersion:'2026-07-18',
                    note:consentEdit.note||'',
                }),
            });
            patchSelectedStudent({publicationConsent:{
                status:'confirmed',
                by:data.consent.consentBy,
                relationship:data.consent.relationship,
                method:data.consent.consentMethod,
                noticeVersion:data.consent.noticeVersion,
                at:data.consent.createdAt,
            }});
            setConsentEdit(null);
            showToast('官网作品展示授权已记录');
        } catch (e) { showToast(`授权保存失败：${e.message}`, 'error'); }
        finally { setBusy(false); }
    };

    const withdrawPublicationConsent = () => {
        if (!selS || consentEdit?.mode!=='withdraw') return;
        if (!consentEdit.note.trim()) {
            showToast('请填写撤回原因，便于后续审计', 'warn'); return;
        }
        confirm(`${selS.name} 目前展示在官网的内容会立即全部下架，家长和访客都不会再看到。\n\n私人记录不受影响，仍保留在学员专区里。撤回会作为一条不可覆盖的审计记录留存。`, async () => {
            setBusy(true);
            try {
                const data = await v1Api(`/students/${encodeURIComponent(selS.id)}/publication-consent`, {
                    method:'DELETE', body:JSON.stringify({note:consentEdit.note.trim()}),
                });
                const portfolio=(selS.portfolio||[]).map(item=>({...item,public:false,visibility:'private'}));
                patchSelectedStudent({publicationConsent:{status:'withdrawn',at:data.consent.createdAt},portfolio});
                setConsentEdit(null);
                showToast(`授权已撤回，${data.unpublishedItems||0} 件作品已下架`, 'warn');
            } catch (e) { showToast(`撤回失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger:true, confirmText:'撤回并下架'});
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
            const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/upload`, {
                method: 'POST', credentials:'include',
                headers:{'X-Requested-With':'StudioSaaS'}, body: fd
            });
            if (r.status === 401) { showToast('登录已过期', 'error'); return; }
            if (!r.ok) { showToast('上传失败，请重试', 'error'); return; }
            const res = await r.json();
            const newPort = [res.item, ...(selS.portfolio || [])];
            setSelS(p => ({...p, portfolio: newPort}));
            setDb(d => ({...d, students: d.students.map(s => s.id===selS.id ? {...s,portfolio:newPort} : s)}));
            showToast(`${workNoun}已上传`, 'success');
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
        confirm(`此操作不可撤销。\n\n照片会从服务器删除，家长在学员专区也将不再看到它。如果只是不想公开展示，取消勾选「展示到官网作品墙」即可，照片仍会保留在私人记录里。`, async () => {
            const sid = String(selS.id);
            try {
                const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(pid)}`, {
                    method: 'DELETE', credentials:'include',
                    headers:{'X-Requested-With':'StudioSaaS'}
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
                credentials:'include', headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With':'StudioSaaS',
                },
                body: JSON.stringify({note, date, title, public:isPublic})
            });
            if (r.status === 401) { showToast('登录已过期，请重新登录', 'error'); return; }
            if (!r.ok) { showToast('更新失败', 'error'); return; }
            const newPort = (selS?.portfolio || []).map(i => String(i.id)===String(item.id) ? {...i,note,date,title,public:isPublic,visibility:isPublic?'shared':'private'} : i);
            setSelS(p => p ? ({...p, portfolio: newPort}) : p);
            setDb(d => ({...d, students: d.students.map(s => s.id===selS?.id ? {...s,portfolio:newPort} : s)}));
            // B3: Also sync lightbox items so open lightbox reflects the updated note/date
            setPortLB(p => p ? ({...p, items: newPort}) : null);
            setPortEdit(null);
            showToast('已更新', 'success');
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
            if (!cur.includes(rPick)) {
                if (TENANT_SLUG) {
                    await addDailyRosterStudents(rDate, [rPick], 'manual', 'scheduled',
                        {classTime: rTime || null, oneToOne: rOneToOne});
                    /* Say how crowded the slot now is: the front desk books a
                       one-to-one into an occupied hour otherwise, and only
                       finds out when both families arrive. */
                    if (rTime) {
                        const same = (db.rosters[rDate]||[]).filter(id =>
                            (rosterMetaFor(rDate, id).classTime || '') === rTime).length + 1;
                        const name = db.students.find(x=>x.id===rPick)?.name || '学员';
                        showToast(`${name} 已加入 ${rTime}；该时段共 ${same} 人`,
                            rOneToOne && same > 1 ? 'warn' : 'success');
                    }
                }
                else { const ok = await save({...db, rosters:{...db.rosters,[rDate]:[...cur,rPick]}}); if (!ok) return; }
            }
            setRPick(null); /* Fix #1: clears picker q via useEffect */
            setROneToOne(false);   /* one-to-one is per booking, not sticky */
        } finally { setBusy(false); }
    };
    const removeFromRoster = async (sid) => {
        if (busy) return; setBusy(true);
        try {
            if (TENANT_SLUG) {
                const entry = (db.rosterEntries?.[rDate]||{})[sid];
                if (!entry?.id) { showToast('未找到可移除的手动排课记录', 'warn'); return; }
                await v1Api(`/daily-roster/${encodeURIComponent(entry.id)}`, {method:'DELETE'});
                await load();
                showToast('已从当日排课移除', 'warn', {
                    label:'撤销移除',
                    onClick:async()=>{
                        try {
                            await v1Api(`/daily-roster/${encodeURIComponent(entry.id)}/undo`, {method:'POST',body:'{}'});
                            await load(); showToast('已恢复当日排课');
                        } catch(e) { showToast(`恢复失败：${e.message}`, 'error'); }
                    },
                });
            } else {
                const ok = await save({...db, rosters:{...db.rosters,[rDate]:(db.rosters[rDate]||[]).filter(id=>id!==sid)}});
                if (!ok) return;
            }
        }
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
                    const ok = await save({...db, students:[ns,...db.students], pending:newPending,
                        logs:[mkLog(fullName,'批准注册',`+${credits}`,`来自注册门户，管理员审批`,0,{studentId:ns.id}),...db.logs]});
                    if (!ok) return;
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
        confirm(`拒绝 "${name}" 的注册申请？${TENANT_SLUG ? '（家长将收到通知邮件）' : '并删除该记录？'}`, async (raw) => {
            if (busy) return; setBusy(true);
            try {
                if (TENANT_SLUG) {
                    /* A4: 拒绝走 v1 状态机，原因随邮件发给家长 */
                    const note = String(raw||'').trim();
                    await v1Api(`/registrations/${pid}`, {
                        method: 'PATCH',
                        body: JSON.stringify({status: 'rejected', reviewNote: note || '管理员拒绝注册申请'}),
                    });
                    await load();
                } else {
                    const newPending = (db.pending||[]).filter(p=>p.id!==pid);
                    const ok = await save({...db, pending:newPending,
                        logs:[mkLog(name,'拒绝注册','0','管理员拒绝注册申请'),...db.logs]});
                    if (!ok) return;
                }
                setApproveCredits(p => { const n={...p}; delete n[pid]; return n; });
                showToast(`${name} 的申请已拒绝`, 'warn');
            } catch(e) { showToast(`操作失败：${e.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger:true, confirmText:'确认拒绝', prompt:TENANT_SLUG ? true : false,
            promptLabel:'拒绝原因（将随通知邮件发送给家长，可留空）', promptPlaceholder:'可留空'});
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

    const requestLogout = () => {
        closeSettings();
        confirm('确认退出登录？', doLogout, {confirmText:'退出登录'});
    };

    /* ── Guards ── */
    if (!loggedIn) return <LoginScreen onLogin={refreshSession}/>;
    if (!conn) return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white p-4">
            <div className="text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full">
                {connErr ? (<>
                    <div className="flex justify-center mb-3 text-amber-400"><Icon name="warning" className="w-12 h-12"/></div>
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

    /* The badge counts BOTH queues, because it answers one question — "is
       there anything waiting for me?" — and a front desk that only ever sees
       the registration count would let booking requests sit. The two are kept
       apart everywhere they are read as numbers; this is the one place where
       what matters is the total. */
    const pendingCount = (db.pending||[]).length + bookings.length;
    /* Primary navigation follows the operator's mental model: what needs
       action today, teaching operations, business, then historical records.
       Course catalogue and package management are deliberately owned by
       their functional workspaces rather than hidden inside Settings. */
    /* 一份分区清单，标签页和下面的面板都读它。两处各写一份正是「侧栏名 vs
       页面标题」那个 bug 的形状 —— 第三个元素是可见性，因为团队与数据维护
       只对能管运营的人开放。 */
    const SETTINGS_SECTIONS = [
        ['account', '账号与安全', true],
        ['team', '团队与权限', canManageOperations],
        ['operational', '运营默认', canManageOperations],
        ['billing-identity', '开票信息', canManageOperations],
        ['integrations', '集成', ownerRoles.includes(actorRole)],
        ['maintenance', '数据维护', canManageOperations],
        ['workspace', '工作区链接', true],
    ];
    const NAV_GROUPS = [
        {key:'today', label:'今日', items:[
            {k:'dashboard',i:'dashboard',l:'工作台',s:'工作台'},
            {k:'pending',i:'clipboard',l:'待处理',s:'待处理',badge:pendingCount},
        ]},
        {key:'teaching', label:'教学运营', items:[
            {k:'roster',i:'calendar',l:'课程安排', s:'课表'},
            {k:'courses',i:'calendar',l:'课程目录',s:'课程'},
            {k:'students',i:'users',l:'学员档案',s:'学员'},
            {k:'works',i:'image',l:'作品管理',s:'作品'},
        ]},
        {key:'business', label:'经营', items:[
            {k:'billing',i:'money',l:'账单发票',s:'账单'},
            {k:'topup',i:'money',l:'充值与退款',s:'结算'},
            {k:'finance',i:'trend',l:'课酬与报表',s:'财务'},
            {k:'stats',i:'trend',l:'经营统计',s:'统计'},
        ]},
        {key:'records', label:'记录', items:[
            {k:'logs',i:'scroll',l:'操作日志',s:'日志'},
        ]},
    ].map(group => ({...group, items:group.items.filter(item => allowedTabs.includes(item.k))}))
        .filter(group => group.items.length > 0);
    const NAV = NAV_GROUPS.flatMap(group => group.items);
    /* Derived from NAV, not a second hand-written map. The two of them had
       already drifted — the sidebar said 课程/学员/作品 while the page called
       itself 课程目录/学员档案/作品管理, so the same screen answered to two
       names depending on where you looked. Only pages that have no sidebar
       entry need naming here. */
    const CMS_PAGE_TITLE_EXTRAS = {settings:'系统设置', new_student:'新建学员档案'};
    const cmsPageTitle = CMS_PAGE_TITLE_EXTRAS[tab]
        || (NAV.find(item => item.k === tab) || {}).l
        || 'Studio CMS';
    const actorRoleLabel = ({
        owner:'Owner', manager:'Manager', teacher:'Teacher', front_desk:'Front Desk', staff:'Staff',
        platform_super_admin:'平台管理员', super_admin:'超级管理员'
    })[actorRole] || '工作区成员';
    const actorIdentity = (() => {
        try { return localStorage.getItem(`lp_admin_email_${TENANT_SLUG || 'root'}`) || '当前账号'; }
        catch { return '当前账号'; }
    })();
    const closeSettings = () => {
        setShowSettings(false);
        if (tab === 'settings') setTab('dashboard');
    };

    /* ══════════════════════════ RENDER ══════════════════════════ */
    return (
        <div className="flex h-screen bg-gray-50">
            {toast && <Toast key={toast.key} msg={toast.msg} type={toast.type} action={toast.action} onDone={()=>setToast(null)}/>}

            {/* Calendar download. Everything shown here comes from the same
                CalendarDocument the .ics is serialized from, so the counts on
                screen cannot disagree with the file that arrives. */}
            {icsPreview && (
                <div className="fixed inset-0 z-[60] flex items-end md:items-center justify-center bg-black/40 p-0 md:p-4"
                    role="dialog" aria-modal="true" aria-labelledby="ics-dialog-title" aria-describedby="ics-dialog-help"
                    onClick={e=>{ if (e.target === e.currentTarget) {setIcsPreview(null);setIcsNotice('');} }}>
                    <div ref={icsDialogRef} className="bg-white w-full md:max-w-lg md:rounded-2xl rounded-t-2xl max-h-[88vh] overflow-y-auto">
                        <div className="px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-3">
                            <div>
                                <p id="ics-dialog-title" className="font-bold text-gray-900">
                                    {icsPreview.downloadKind === 'roster' ? '导出当日排课' : '导出固定课表'}
                                </p>
                                <p className="text-xs text-gray-500 mt-0.5">
                                    {icsPreview.date ? `${fmtDate(icsPreview.date)} · ` : ''}Apple / Google 通用 .ics
                                </p>
                            </div>
                            <button ref={icsCloseButtonRef} onClick={()=>{setIcsPreview(null);setIcsNotice('');}} aria-label="关闭日历预览"
                                className="text-gray-400 text-2xl leading-none px-2 min-h-[44px]">×</button>
                        </div>

                        <div className="p-5 space-y-3">
                            {icsNotice && (
                                <div role="status" className="rounded-xl px-4 py-3 bg-amber-50 border border-amber-200 text-xs font-bold text-amber-800">
                                    {icsNotice}
                                </div>
                            )}
                            <div className="grid grid-cols-3 gap-2">
                                {[['events','日历事件'],['classes','普通班课'],['oneToOne','1 对 1']].map(([k,label])=>(
                                    <div key={k} className="bg-gray-50 rounded-xl py-3 text-center">
                                        <p className="text-xl font-bold text-gray-900">{icsPreview.stats?.[k] ?? 0}</p>
                                        <p className="text-xs text-gray-500 mt-0.5">{label}</p>
                                    </div>
                                ))}
                            </div>

                            {(icsPreview.events||[]).length === 0
                                ? <div className="text-center py-6 px-2">
                                    <p className="text-sm text-gray-600 font-bold">没有可导出的课程</p>
                                    <p className="text-xs text-gray-500 mt-1.5 leading-relaxed">
                                        {icsPreview.downloadKind === 'roster'
                                            ? '这一天的排课是空的。先在下方名单里加入学员，再回来导出。'
                                            : '还没有固定班次。在「每周课表」新增班次后，这里就会有内容。'}
                                    </p>
                                  </div>
                                : (icsPreview.events||[]).map(ev=>(
                                    <div key={ev.uid} className="border border-gray-100 rounded-xl px-4 py-3">
                                        <div className="flex items-start justify-between gap-2">
                                            <p className="font-bold text-gray-900 text-sm">{ev.summary}</p>
                                            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 flex-shrink-0">
                                                {ev.allDay
                                                    ? '全天 · 未设时间'
                                                    : `${ev.durationMinutes} 分钟${ev.durationSource==='default' ? ' · 默认' : ''}`}
                                            </span>
                                        </div>
                                        <p className="text-xs text-gray-500 mt-1">{ev.timeRange}</p>
                                        {(ev.participants||[]).length>0 && (
                                            <p className="text-xs text-gray-500 mt-0.5">{ev.participants.join('、')}</p>
                                        )}
                                    </div>
                                ))}

                            {(icsPreview.skipped||[]).length>0 && (
                                <div className="rounded-xl px-4 py-3 bg-amber-50 border border-amber-200">
                                    <p className="text-xs font-bold text-amber-800">
                                        {icsPreview.skipped.length} 项未导出
                                    </p>
                                    <p className="text-xs text-amber-700 mt-1">
                                        {icsPreview.skipped.map(x=>{
                                            const why = {cancelled:'已取消', 'no-class-time':'未设置上课时间'}[x.reason] || x.reason || '';
                                            return [x.studentName, why].filter(Boolean).join(' · ');
                                        }).filter(Boolean).join('；')}
                                    </p>
                                </div>
                            )}

                            <div className="rounded-xl px-4 py-3 bg-gray-50 text-xs text-gray-600 space-y-1">
                                <p><span className="font-bold">时区：</span>{icsPreview.timezone?.name}
                                    {icsPreview.timezone?.abbreviations?.length
                                        ? `（含 ${icsPreview.timezone.abbreviations.join('/')} 规则）` : ''}</p>
                                {icsPreview.location && <p><span className="font-bold">地点：</span>{icsPreview.location}</p>}
                            </div>

                            {icsPreview.includesStudentNames && (
                                <div className="rounded-xl px-4 py-3 bg-amber-50 border border-amber-200 text-xs text-amber-800">
                                    此文件包含学员姓名。导入后它会留在对方的日历里，请只发给应当看到的人。
                                </div>
                            )}

                            <p id="ics-dialog-help" className="text-xs text-gray-500 leading-relaxed">
                                Apple 日历可直接打开此文件；Google 日历请在电脑端「设置 → 导入和导出」导入。
                                同一个文件两者通用。
                                {icsPreview.subscribable === false && '文件是当前排课的快照，之后修改排课需要重新下载。'}
                            </p>
                        </div>

                        <div className="px-5 py-4 border-t border-gray-100 flex gap-2">
                            <button onClick={()=>{setIcsPreview(null);setIcsNotice('');}}
                                className="flex-1 border border-gray-200 rounded-xl py-3 text-sm font-bold text-gray-700 min-h-[44px]">取消</button>
                            <button onClick={()=>downloadIcs(icsPreview)}
                                disabled={icsBusy || !(icsPreview.stats?.events > 0)}
                                title={icsPreview.stats?.events > 0 ? '' : '没有可导出的课程'}
                                className="flex-1 bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white rounded-xl py-3 text-sm font-bold min-h-[44px] inline-flex items-center justify-center gap-1.5">
                                <Icon name="download" className="w-4 h-4"/>下载 .ics
                            </button>
                        </div>
                    </div>
                </div>
            )}
            <ConfirmDialog dialog={confirmDialog} onClose={()=>setConfirmDialog(null)}/>

            {/* ── Portfolio Lightbox ── */}
            {portLB && portLB.items.length > 0 && (
                <div ref={portLightboxDialogRef} className="fixed inset-0 bg-black/95 z-[90] flex flex-col"
                    role="dialog" aria-modal="true" aria-labelledby="portfolio-lightbox-title"
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
                            <p id="portfolio-lightbox-title" className="text-white font-bold text-sm truncate">{portLB.items[portLB.idx]?.title || fmtDate(portLB.items[portLB.idx]?.date)}</p>
                            {portLB.items[portLB.idx]?.title && <p className="text-white/50 text-[11px] truncate">{fmtDate(portLB.items[portLB.idx]?.date)}</p>}
                            {portLB.items[portLB.idx]?.note && <p className="inline-flex items-center gap-1.5 text-white/60 text-xs truncate"><Icon name="chat" className="w-4 h-4"/>{portLB.items[portLB.idx].note}</p>}
                        </div>
                        <div className="flex items-center gap-2 flex-shrink-0">
                            <span className="text-white/40 text-xs">{portLB.idx+1} / {portLB.items.length}</span>
                            {/* M2: Edit button in lightbox — sole access point on touch devices */}
                            <button onClick={()=>{const cur=portLB.items[portLB.idx];if(cur&&selS){setPortEdit({sid:String(selS.id),item:cur,note:cur.note||'',title:cur.title||'',date:cur.date||todayISO(),public:!!cur.public});setPortLB(null);}}}
                                aria-label="编辑" className="text-white/80 active:text-white w-9 h-9 flex items-center justify-center"><Icon name="pencil" className="w-4 h-4"/></button>
                            <button onClick={()=>setPortLB(null)} aria-label="关闭" className="text-white text-2xl font-bold w-10 h-10 flex items-center justify-center">×</button>
                        </div>
                    </div>
                    <div className="flex-1 flex items-center justify-center px-2 min-h-0"
                        onClick={()=>setPortLB(null)}>
                        {/* #8 fix: onError shows fallback text instead of broken-image icon */}
                        <img
                            src={portfolioImgSrc(selS?.id, portLB.items[portLB.idx])}
                            srcSet={portfolioSrcSet(selS?.id, portLB.items[portLB.idx])}
                            sizes="100vw"
                            alt={portLB.items[portLB.idx]?.title || `${selS?.name || '学员'}的作品 ${portLB.idx + 1}`}
                            className="max-w-full max-h-full object-contain rounded-xl shadow-2xl"
                            onClick={e=>e.stopPropagation()}
                            onError={e=>{e.target.style.display='none';e.target.nextSibling&&(e.target.nextSibling.style.display='flex');}}/>
                        <div style={{display:'none'}} className="flex-col items-center justify-center gap-2 text-white/50">
                            <span className="inline-flex items-center gap-1.5 text-4xl"><Icon name="image" className="w-4 h-4"/></span>
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
                            aria-label="删除" className="py-2.5 px-4 bg-red-500 active:bg-red-600 text-white rounded-xl text-sm min-h-[44px] flex items-center justify-center"><Icon name="trash" className="w-4 h-4"/></button>
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
                <div ref={portUploadDialogRef} className="fixed inset-0 bg-black/70 z-[85] flex items-end sm:items-center justify-center sm:p-4"
                    role="dialog" aria-modal="true" aria-labelledby="portfolio-upload-title"
                    onClick={e=>{if(e.target===e.currentTarget){if(portUpFile?.dataUrl)URL.revokeObjectURL(portUpFile.dataUrl);setPortUpload(false);setPortUpFile(null);}}}>
                    {/* M5: click backdrop to close */}
                    <div className="bg-white w-full sm:rounded-3xl sm:max-w-md shadow-2xl overflow-hidden anim"
                        style={{paddingBottom:'env(safe-area-inset-bottom,0px)'}}>
                        <div className="flex justify-between items-center px-5 pt-5 pb-3">
                            <h3 id="portfolio-upload-title" className="font-bold text-gray-800 text-lg flex items-center gap-2"><Icon name="upload"/> 上传{workNoun}</h3>
                            <button onClick={()=>{if(portUpFile?.dataUrl)URL.revokeObjectURL(portUpFile.dataUrl);setPortUpload(false);setPortUpFile(null);}} aria-label="关闭" className="text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center">×</button>
                        </div>
                        <div className="px-5 pb-5">
                            {!portUpFile ? (
                                <div>
                                    <div className="flex gap-3">
                                        <label className="flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-purple-300 rounded-2xl cursor-pointer active:bg-purple-50 hover:bg-purple-50 transition-colors">
                                            <span className="text-gray-400"><Icon name="camera" className="w-8 h-8"/></span>
                                            <span className="text-sm font-bold text-purple-700">拍照</span>
                                            <input type="file" accept="image/*" capture="environment" className="hidden"
                                                onChange={e=>{
                                                    const file=e.target.files[0]; if(!file) return;
                                                    if(file.size>10*1024*1024){showToast('文件太大，请先压缩','error');return;}
                                                    setPortUpFile({file,dataUrl:URL.createObjectURL(file),note:'',date:todayISO(),public:false});
                                                }}/>
                                        </label>
                                        <label className="flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-indigo-300 rounded-2xl cursor-pointer active:bg-indigo-50 hover:bg-indigo-50 transition-colors">
                                            <span className="inline-flex items-center gap-1.5 text-3xl"><Icon name="image" className="w-4 h-4"/></span>
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
                                    <img src={portUpFile.dataUrl} alt="待上传作品预览" className="w-full h-52 object-cover rounded-2xl mb-4 bg-gray-100"/>
                                    <div className="space-y-3">
                                        <div>
                                            <label className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block"><Icon name="calendar" className="w-4 h-4"/>作品日期</label>
                                            <input type="date" value={portUpFile.date}
                                                onChange={e=>setPortUpFile(p=>({...p,date:e.target.value}))}
                                                className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                        </div>
                                        <div>
                                            <label className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block"><Icon name="image" className="w-4 h-4"/>作品标题 <span className="font-normal text-gray-400">选填</span></label>
                                            <input type="text" value={portUpFile.title||''}
                                                onChange={e=>setPortUpFile(p=>({...p,title:e.target.value}))}
                                                placeholder="如：星空下的向日葵" maxLength={40}
                                                className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                            <p className="mt-1.5 text-[11px] leading-relaxed text-gray-400">按录入的语言原样显示，不随官网语言切换。</p>
                                        </div>
                                        <div>
                                            <label className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block"><Icon name="chat" className="w-4 h-4"/>老师评语 <span className="font-normal text-gray-400">选填，家长可见</span></label>
                                            <input type="text" value={portUpFile.note}
                                                onChange={e=>setPortUpFile(p=>({...p,note:e.target.value}))}
                                                placeholder="如：水彩练习 第1期" maxLength={50}
                                                className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                        </div>
                                        <label className="flex items-start gap-3 rounded-xl border border-purple-100 bg-purple-50 p-3 text-sm text-purple-900">
                                            <input type="checkbox" checked={!!portUpFile.public}
                                                disabled={selS?.publicationConsent?.status!=='confirmed'}
                                                onChange={e=>setPortUpFile(p=>({...p,public:e.target.checked}))}
                                                className="mt-0.5 w-4 h-4 flex-shrink-0 disabled:opacity-40"/>
                                            <span>
                                                <span className="font-bold block">展示到官网作品墙</span>
                                                <span className="text-xs text-purple-700">{selS?.publicationConsent?.status==='confirmed' ? '该学员已有有效公开授权；标题和评语不得包含学员全名。' : '请先在学员档案中记录公开授权，才能开启官网展示。'}</span>
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
                                            {portBusy ? '上传中...' : '确认上传'}
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
                <div ref={portEditDialogRef} className="fixed inset-0 bg-black/60 z-[85] flex items-end sm:items-center justify-center sm:p-4"
                    role="dialog" aria-modal="true" aria-labelledby="portfolio-edit-title"
                    onClick={e=>{if(e.target===e.currentTarget)setPortEdit(null);}}>
                    <div className="bg-white w-full sm:rounded-3xl sm:max-w-sm rounded-t-3xl p-5 shadow-2xl anim"
                        style={{paddingBottom:'max(20px,env(safe-area-inset-bottom,20px))'}}>
                        <div className="flex justify-between items-center mb-4">
                            <h3 id="portfolio-edit-title" className="inline-flex items-center gap-1.5 font-bold text-gray-800 text-lg"><Icon name="pencil" className="w-4 h-4"/>编辑作品信息</h3>
                            <button onClick={()=>setPortEdit(null)} aria-label="关闭" className="text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center">×</button>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <label className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block"><Icon name="calendar" className="w-4 h-4"/>作品日期</label>
                                <input type="date" value={portEdit.date}
                                    onChange={e=>setPortEdit(p=>({...p,date:e.target.value}))}
                                    className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                            </div>
                            <div>
                                <label className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block"><Icon name="image" className="w-4 h-4"/>作品标题</label>
                                <input type="text" value={portEdit.title||''}
                                    onChange={e=>setPortEdit(p=>({...p,title:e.target.value}))}
                                    maxLength={40}
                                    className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                                <p className="mt-1.5 text-[11px] leading-relaxed text-gray-400">按录入的语言原样显示，不随官网语言切换。</p>
                            </div>
                            <div>
                                <label className="inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block"><Icon name="chat" className="w-4 h-4"/>老师评语 <span className="font-normal text-gray-400">家长可见</span></label>
                                <input type="text" value={portEdit.note}
                                    onChange={e=>setPortEdit(p=>({...p,note:e.target.value}))}
                                    maxLength={50}
                                    className="w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"/>
                            </div>
                            <label className="flex items-start gap-3 rounded-xl border border-purple-100 bg-purple-50 p-3 text-sm text-purple-900">
                                <input type="checkbox" checked={!!portEdit.public}
                                    disabled={selS?.publicationConsent?.status!=='confirmed'}
                                    onChange={e=>setPortEdit(p=>({...p,public:e.target.checked}))}
                                    className="mt-0.5 w-4 h-4 flex-shrink-0 disabled:opacity-40"/>
                                <span>
                                    <span className="font-bold block">展示到官网作品墙</span>
                                    <span className="text-xs text-purple-700">{selS?.publicationConsent?.status==='confirmed' ? '关闭后仍保留在学员私人作品集。' : '当前没有有效公开授权，作品只能保持私人可见。'}</span>
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
                <div ref={searchDialogRef} className="fixed inset-0 bg-black/60 z-[80] flex items-start justify-center pt-[10vh] px-4 backdrop-blur-sm"
                     role="dialog" aria-modal="true" aria-label="搜索学员"
                     onClick={()=>{setGOpen(false);setGQ('');}}>
                    <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden anim" onClick={e=>e.stopPropagation()}>
                        <div className="flex items-center gap-2 px-4 py-3 border-b">
                            <span className="text-gray-400"><Icon name="search" className="w-5 h-5"/></span>
                            <input autoFocus type="text" placeholder="搜索学员姓名、电话、微信号..." value={gQ}
                                onChange={e=>setGQ(e.target.value)}
                                onKeyDown={e=>{ if(e.key==='Escape'){setGOpen(false);setGQ('');} }}
                                className="flex-1 outline-none text-gray-800 text-sm bg-transparent placeholder-gray-400"/>
                            <kbd className="hidden sm:inline text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded font-mono">ESC</kbd>
                            <button type="button" onClick={()=>{setGOpen(false);setGQ('');}} aria-label="关闭搜索"
                                className="text-gray-400 active:text-gray-700 text-xl inline-flex items-center justify-center">×</button>
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
                                            <p className="text-xs text-gray-400">{s.mobile||'—'}{s.wechat?` · ${s.wechat}`:''}</p>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0">
                                            {tag && <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-bold ${tag.cls}`}><Icon name={tag.icon} className="w-3 h-3"/>{tag.label}</span>}
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

            {/* Settings is a full workspace route. The legacy compact entry
                remains a modal only when old code opens it without changing
                the URL; primary navigation always gets a dedicated page. */}
            {showSettings && (
                <div ref={settingsDialogRef}
                    className={tab==='settings'
                        /* 目的地，不是覆盖层。盖住侧栏才需要「返回工作台」——
                           其他页面都不需要，因为它们从没把你带走过。 */
                        ? 'anim'
                        : 'fixed inset-0 bg-black/60 z-[60] flex items-center justify-center p-4'}
                    onClick={tab==='settings' ? undefined : closeSettings}
                    role={tab==='settings' ? undefined : 'dialog'} aria-modal={tab==='settings' ? undefined : 'true'} aria-labelledby="settings-dialog-title"
                    style={{paddingTop:tab==='settings' ? 'env(safe-area-inset-top, 0px)' : 'max(16px, env(safe-area-inset-top, 16px))', paddingBottom:'max(16px, env(safe-area-inset-bottom, 16px))'}}>
                    <div className={tab==='settings'
                        ? 'w-full'
                        : 'bg-white rounded-2xl p-6 w-full max-w-2xl shadow-2xl anim overflow-y-auto modal-scroll'}
                        style={tab==='settings' ? undefined : {maxHeight:'90dvh'}} onClick={e=>e.stopPropagation()}>
                        <div className="flex justify-between items-center mb-5">
                            <h3 id="settings-dialog-title"
                                className={`inline-flex items-center gap-1.5 font-bold text-gray-800 text-xl ${tab==='settings' ? 'md:hidden' : ''}`}>
                                <Icon name="cog" className="w-5 h-5"/>系统设置
                            </h3>
                            {tab!=='settings' && <button onClick={closeSettings} aria-label="关闭" className="text-gray-400 active:text-gray-700 text-xl p-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center">×</button>}
                        </div>
                        {/* 真标签页。之前这里写着 role="tablist"，点击执行的却是
                            scrollIntoView —— 9 个分区始终同时渲染，高亮和你正在看的
                            内容会对不上，而读屏软件被告知有一组标签页却找不到面板。
                            底部下划线的样式和学员档案、待处理、课酬三处一致。 */}
                        {tab==='settings' && <div className="mb-6 flex gap-1 overflow-x-auto border-b border-gray-200" role="tablist" aria-label="系统设置分区">
                            {SETTINGS_SECTIONS.filter(([,,visible])=>visible!==false).map(([key,label])=>(
                                <button key={key} type="button" role="tab" id={`settings-tab-${key}`}
                                    aria-selected={settingsSection===key} aria-controls={`settings-${key}`}
                                    onClick={()=>setSettingsSection(key)}
                                    className={`whitespace-nowrap min-h-[44px] px-3 text-xs font-bold border-b-2 -mb-px ${settingsSection===key?'border-indigo-600 text-indigo-700':'border-transparent text-gray-600 hover:text-gray-800'}`}>{label}</button>
                            ))}
                        </div>}
                        <div className="md:hidden mb-4 pb-4 border-b border-gray-100">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide mb-2">界面语言</p>
                            <div className="grid grid-cols-2 gap-2">
                                <button type="button" onClick={()=>document.querySelector('[data-cms-language="zh"]')?.click()}
                                    className="min-h-[44px] rounded-xl border border-gray-200 bg-gray-50 text-sm font-bold text-gray-700">中文</button>
                                <button type="button" onClick={()=>document.querySelector('[data-cms-language="en"]')?.click()}
                                    className="min-h-[44px] rounded-xl border border-gray-200 bg-gray-50 text-sm font-bold text-gray-700">English</button>
                            </div>
                        </div>
                        {/* A5: Public website and lead-capture settings live in Studio Admin. */}
                        {TENANT_SLUG && ownerRoles.includes(actorRole) && (
                            <a href={`/${TENANT_SLUG}/studio-admin`} target="_blank" rel="noopener"
                                className="block bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3 text-sm font-bold text-indigo-700 active:bg-indigo-100">
                                网站、Logo、配色与注册表设置 →
                                <p className="text-[11px] font-normal text-indigo-400 mt-0.5">打开 Studio Admin 管理公开门户、注册表字段、品牌文案和页面展示</p>
                            </a>
                        )}
                        {canManageOperations && <div id="settings-team" role="tabpanel" aria-labelledby="settings-tab-team" hidden={tab==='settings' && settingsSection!=='team'} className="mt-4 pt-4 border-t border-gray-100 space-y-3 scroll-mt-24">
                            <div>
                                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">团队与权限</p>
                                <p className="text-xs text-gray-400 mt-0.5">Owner管理团队；Manager负责日常运营，Teacher负责签到与作品，Front Desk负责报名、学员与课时。</p>
                            </div>
                            <div className="space-y-2">
                                {team.map(member=>(
                                    <div key={member.id} className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                        <div className="flex items-center gap-2">
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
                                        {/* 公开课表署名。只对会上课的角色出现 —— 前台不会被排课，
                                            给他一个「是否公开姓名」的开关只是多一个要理解的东西。 */}
                                        {ownerRoles.includes(actorRole) && member.role!=='owner'
                                            && ['manager','teacher'].includes(member.role) && (
                                        <div className="mt-2 pt-2 border-t border-gray-200 space-y-2">
                                            <label className="flex items-start gap-2.5 min-h-[44px] cursor-pointer">
                                                <input type="checkbox" disabled={teamBusy}
                                                    checked={!!member.show_on_public_timetable}
                                                    onChange={e=>updateTeamPublicity(member,{showOnPublicTimetable:e.target.checked})}
                                                    className="mt-0.5 w-4 h-4 accent-indigo-600"/>
                                                <span className="flex-1">
                                                    <span className="text-xs font-bold text-gray-600">可在公开课表显示姓名</span>
                                                    <span className="block text-[11px] text-gray-400 mt-0.5">默认关闭。被排了一节课不等于同意把名字放到公网上，这一项由本人决定后再开。</span>
                                                </span>
                                            </label>
                                            {member.show_on_public_timetable && (
                                            <div className="flex gap-2 items-end">
                                                <label className="flex-1 text-[11px] font-bold text-gray-500">
                                                    对外显示名（留空则用 {member.full_name}）
                                                    <input defaultValue={member.public_display_name||''} placeholder="如：Lucy 老师" disabled={teamBusy}
                                                        onBlur={e=>{ const v=e.target.value.trim();
                                                            if (v !== (member.public_display_name||'')) updateTeamPublicity(member,{publicDisplayName:v}); }}
                                                        className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"/>
                                                </label>
                                            </div>
                                            )}
                                        </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                            {ownerRoles.includes(actorRole) ? <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 bg-indigo-50 border border-indigo-100 rounded-xl p-3">
                                <label className="text-xs font-bold text-gray-600">姓名 *
                                    <input value={teamForm.fullName} onChange={e=>setTeamForm(p=>({...p,fullName:e.target.value}))}
                                        placeholder="如：Lucy Wang" className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"/>
                                </label>
                                <label className="text-xs font-bold text-gray-600">邮箱 *
                                    <input type="email" value={teamForm.email} onChange={e=>setTeamForm(p=>({...p,email:e.target.value}))}
                                        placeholder="name@example.com" className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"/>
                                </label>
                                <label className="text-xs font-bold text-gray-600">角色 *
                                    <select value={teamForm.role} onChange={e=>setTeamForm(p=>({...p,role:e.target.value}))}
                                        className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]">
                                        <option value="manager">Manager</option><option value="teacher">Teacher</option><option value="front_desk">Front Desk</option><option value="staff">Staff (legacy)</option>
                                    </select>
                                </label>
                                <label className="text-xs font-bold text-gray-600">临时密码 *
                                    <input type="password" value={teamForm.temporaryPassword} onChange={e=>setTeamForm(p=>({...p,temporaryPassword:e.target.value}))}
                                        placeholder="至少 8 位" className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"/>
                                </label>
                                <button type="button" onClick={createTeamMember} disabled={teamBusy}
                                    className="sm:col-span-2 bg-indigo-600 text-white py-2.5 rounded-xl font-bold text-sm disabled:opacity-50">添加团队成员</button>
                            </div> : <p className="text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-xl px-3 py-2">当前角色可查看团队；只有 Owner 可以新增、停用或更改成员角色。</p>}
                        </div>}
                        {/* 修改登录密码 */}
                        <div id="settings-account" role="tabpanel" aria-labelledby="settings-tab-account" hidden={tab==='settings' && settingsSection!=='account'} className="space-y-2 scroll-mt-24">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">修改登录密码</p>
                            <label className="block text-xs font-bold text-gray-600">当前密码
                                <input type="password" autoComplete="current-password" placeholder="输入当前密码" value={pwOld} onChange={e=>setPwOld(e.target.value)}
                                    className="mt-1 w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm min-h-[44px] focus:ring-2 focus:ring-indigo-400"/>
                            </label>
                            <label className="block text-xs font-bold text-gray-600">新密码 *
                                <input type="password" autoComplete="new-password" placeholder="至少 8 位" value={pwNew1} onChange={e=>setPwNew1(e.target.value)}
                                    className="mt-1 w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm min-h-[44px] focus:ring-2 focus:ring-indigo-400"/>
                            </label>
                            <label className="block text-xs font-bold text-gray-600">确认新密码 *
                                <input type="password" autoComplete="new-password" placeholder="再次输入新密码" value={pwNew2} onChange={e=>setPwNew2(e.target.value)}
                                    className="mt-1 w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm min-h-[44px] focus:ring-2 focus:ring-indigo-400"/>
                            </label>
                            {pwMsg && <p className={`text-xs font-medium ${pwMsg.tone==='ok'?'text-green-600':'text-red-500'}`}>{pwMsg.text}</p>}
                            <button onClick={changeWebPw} disabled={pwBusy}
                                className="w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm">
                                {pwBusy ? '更新中...' : '更新密码'}
                            </button>
                        </div>
                        {/* Tenant-wide roster default: server-owned so every
                            staff device starts new bookings at the same time. */}
                        {canManageOperations && TENANT_SLUG && (
                        <div id="settings-operational" role="tabpanel" aria-labelledby="settings-tab-operational" hidden={tab==='settings' && settingsSection!=='operational'} className="mt-4 pt-4 border-t border-gray-100 space-y-2 scroll-mt-24">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">课程安排默认时间</p>
                            <p className="text-xs text-gray-400">用于新排课、班组模板和新建固定班次；不会改动已保存的课程。</p>
                            <div className="flex gap-2 items-end">
                                <label className="flex-1 text-xs font-bold text-gray-500">
                                    默认上课时间
                                    <input type="time" value={defaultClassTimeDraft}
                                        onChange={e=>setDefaultClassTimeDraft(e.target.value)}
                                        className="mt-1 w-full px-3 py-2.5 border border-gray-300 rounded-xl bg-white text-sm font-bold min-h-[46px] outline-none focus:ring-2 focus:ring-indigo-500"/>
                                </label>
                                <button type="button" onClick={saveDefaultClassTime}
                                    disabled={operationalSettingsBusy || defaultClassTimeDraft===defaultClassTime}
                                    className="px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold min-h-[46px] disabled:opacity-40">
                                    {operationalSettingsBusy?'保存中…':'保存'}
                                </button>
                            </div>
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
                        {false && <>{/* Moved to the functional workspaces. Keep this
                            legacy markup out of the Settings surface while the
                            generated bundle remains backward-compatible. */}
                        {/* v8.10.3: 课程管理。放在充值套餐旁边，因为它们是同一类
                            东西——都是「先定义好、之后到处引用」的条目，而不是每天
                            要做的事。排课编辑器里的下拉有一个链接指到这里。 */}
                        <div id="courseManager" className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">课程管理</p>
                            <p className="text-xs text-gray-400">
                                课程是可以被固定班次「关联」的条目。关联之后，公开课表就能显示课程简介和适龄段；不关联也能正常排课，只是课表上只有班次名称。
                            </p>
                            {!courses.length && !courseEdit && (
                                <p className="text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-xl px-3 py-2">
                                    还没有课程。例如「儿童油画基础」——添加后就能在「课程安排 → 新增班次」里关联它。
                                </p>
                            )}
                            {courses.map(course => (
                                <div key={course.id} className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                    <div className="flex-1 min-w-0">
                                        <p className="text-xs font-bold text-gray-700 truncate">{course.name}</p>
                                        <p className="text-xs text-gray-400 truncate">
                                            {[course.age_range && `适龄 ${course.age_range}`,
                                              course.duration_minutes && `${course.duration_minutes} 分钟`,
                                              course.price_aud_cents ? `$${(course.price_aud_cents/100).toFixed(2)}` : null,
                                             ].filter(Boolean).join(' · ') || '未填写详情'}
                                        </p>
                                    </div>
                                    <button onClick={()=>setCourseEdit({
                                            id: course.id, name: course.name, description: course.description || '',
                                            ageRange: course.age_range || '',
                                            durationMinutes: course.duration_minutes || 60,
                                            priceAud: course.price_aud_cents ? String(course.price_aud_cents/100) : '',
                                        })}
                                        className="text-xs text-indigo-600 font-bold px-3 py-1 min-h-[44px] inline-flex items-center active:text-indigo-800 flex-shrink-0">编辑</button>
                                    <button onClick={()=>archiveCourse(course)} aria-label="归档"
                                        className="text-red-500 font-bold px-2 py-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center active:text-red-700 flex-shrink-0"><Icon name="close" className="w-3.5 h-3.5"/></button>
                                </div>
                            ))}
                            {!courseEdit ? (
                                <button onClick={()=>setCourseEdit({name:'', description:'', ageRange:'', durationMinutes:60, priceAud:''})}
                                    className="w-full border border-dashed border-indigo-300 text-indigo-600 rounded-xl py-2 text-xs font-bold active:bg-indigo-50">+ 添加课程</button>
                            ) : (
                                <div className="space-y-2 bg-indigo-50 border border-indigo-200 rounded-xl p-3">
                                    <p className="text-xs font-bold text-indigo-700">{courseEdit.id?'编辑课程':'添加课程'}</p>
                                    <input placeholder="课程名称，如：儿童油画基础" value={courseEdit.name}
                                        onChange={e=>setCourseEdit(p=>({...p,name:e.target.value}))}
                                        className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                    <textarea placeholder="课程简介（选填，会显示在公开课表上）" rows="2" value={courseEdit.description}
                                        onChange={e=>setCourseEdit(p=>({...p,description:e.target.value}))}
                                        className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                    <div className="grid grid-cols-3 gap-2">
                                        <input placeholder="适龄 6-9" value={courseEdit.ageRange}
                                            onChange={e=>setCourseEdit(p=>({...p,ageRange:e.target.value}))}
                                            className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                        <input type="number" min="1" placeholder="时长(分)" value={courseEdit.durationMinutes}
                                            onChange={e=>setCourseEdit(p=>({...p,durationMinutes:e.target.value}))}
                                            className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                        <input type="number" min="0" step="0.01" placeholder="价格 $" value={courseEdit.priceAud}
                                            onChange={e=>setCourseEdit(p=>({...p,priceAud:e.target.value}))}
                                            className="w-full px-2.5 py-2 border border-gray-300 rounded-xl text-sm outline-none focus:ring-2 focus:ring-indigo-400"/>
                                    </div>
                                    <p className="text-[11px] text-gray-400">简介、适龄段和价格都是选填；公开课表上显示哪些，由 Studio Admin 的 Timetable 开关决定。</p>
                                    <div className="flex gap-2">
                                        <button onClick={()=>setCourseEdit(null)}
                                            className="flex-1 py-2 border border-gray-300 rounded-xl text-xs font-bold text-gray-600 active:bg-gray-100">取消</button>
                                        <button onClick={saveCourse} disabled={busy}
                                            className="flex-1 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold disabled:bg-gray-300">{courseEdit.id?'保存':'添加'}</button>
                                    </div>
                                </div>
                            )}
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
                                        className="text-xs text-indigo-600 font-bold px-3 py-1 min-h-[44px] inline-flex items-center active:text-indigo-800 flex-shrink-0">编辑</button>
                                    <button onClick={()=>{ if((db.packages||[]).length<=1){showToast('至少保留一个套餐','warn');return;} confirm(`删除套餐「${pkg.name}」？`,async ()=>{ const nd={...db,packages:(db.packages||[]).filter(p=>p.id!==pkg.id)}; const ok = await save(nd); if (!ok) return; showToast('套餐已删除'); },{danger:true,confirmText:'删除'}); }}
                                        aria-label="删除" className="text-red-500 font-bold px-2 py-1 min-h-[44px] min-w-[44px] inline-flex items-center justify-center active:text-red-700 flex-shrink-0"><Icon name="close" className="w-3.5 h-3.5"/></button>
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
                                        <button onClick={async ()=>{
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
                                            const ok = await save({...db, packages:newPkgs});
                                            if (!ok) return;
                                            setPkgEditId(null); setPkgName(''); setPkgCredits(''); setPkgPrice('');
                                            showToast(pkgEditId===0?'套餐已添加':'套餐已更新');
                                        }} className="flex-1 py-2 bg-indigo-600 active:bg-indigo-700 text-white rounded-xl text-xs font-bold">保存</button>
                                    </div>
                                </div>
                            )}
                        </div>
                        </>}
                        <div className="mt-4 pt-4 border-t border-gray-100 rounded-xl bg-indigo-50 border-indigo-100 px-4 py-3 space-y-2">
                            <p className="text-xs font-bold text-indigo-800">课程目录与充值套餐已移到对应工作区</p>
                            <p className="text-xs text-indigo-600 leading-relaxed">设置只保留账号、团队、运营默认和数据维护。课程请进入「课程」，套餐请进入「充值与退款」中的「套餐管理」。</p>
                            <div className="grid grid-cols-2 gap-2">
                                {allowedTabs.includes('courses') && <button type="button" onClick={()=>setTab('courses')} className="min-h-[44px] rounded-xl bg-white border border-indigo-200 text-indigo-700 text-xs font-bold">进入课程目录</button>}
                                {allowedTabs.includes('topup') && <button type="button" onClick={()=>setTab('topup')} className="min-h-[44px] rounded-xl bg-white border border-indigo-200 text-indigo-700 text-xs font-bold">进入套餐管理</button>}
                            </div>
                        </div>
                        </>}
                        {/* U6: Roster cleanup */}
                        {canManageOperations && (()=>{
                            const cutoffStr = (() => { const d=new Date(); d.setDate(d.getDate()-90); return d.toISOString().slice(0,10); })();
                            const oldKeys = Object.keys(db.rosters||{}).filter(d=>d<cutoffStr);
                            const cleanRosters = () => {
                                if (!oldKeys.length) { showToast('没有需要清理的旧排课'); return; }
                                confirm(`清理 90 天前的排课记录（${oldKeys.length} 条）？\n此操作不影响任何统计数据。`, async ()=>{
                                    const nd = {...db, rosters:{...db.rosters}};
                                    oldKeys.forEach(k=>delete nd.rosters[k]);
                                    const ok = await save(nd);
                                    if (!ok) return;
                                    showToast(`已清理 ${oldKeys.length} 条旧排课`);
                                }, {confirmText:'清理'});
                            };
                            return (
                                <div id="settings-maintenance" role="tabpanel" aria-labelledby="settings-tab-maintenance" hidden={tab==='settings' && settingsSection!=='maintenance'} className="mt-4 pt-4 border-t border-gray-100 space-y-2 scroll-mt-24">
                                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">排课数据清理</p>
                                    <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 flex items-center gap-2">
                                        <span className="text-xs text-gray-500 flex-1">90天前旧排课</span>
                                        <span className={`text-xs font-bold ${oldKeys.length>0?'text-amber-600':'text-green-600'}`}>{oldKeys.length} 条</span>
                                    </div>
                                    <button onClick={cleanRosters} disabled={oldKeys.length===0}
                                        className="w-full bg-amber-50 active:bg-amber-100 disabled:opacity-40 text-amber-700 border border-amber-200 py-2.5 rounded-xl font-bold text-sm">
                                        <span className="inline-flex items-center gap-1.5"><Icon name="broom" className="w-4 h-4"/>清理旧排课</span>
                                    </button>
                                </div>
                            );
                        })()}
                        {/* F1/F5/F6: 数据体检 + 阈值 + 每周邮件 + 备份恢复 */}
                        {!TENANT_SLUG && (
                            <div id="settings-maintenance-tools" className="scroll-mt-24">
                                <MaintSection renewTh={renewTh} saveRenewTh={saveRenewTh}
                                    onRestored={()=>{ closeSettings(); load(); }}
                                    confirm={confirm} notify={notify}/>
                            </div>
                        )}
                        {/* 开票信息排在集成前面：Xero 是可选的，而没有开票主体
                            身份，一张发票都开不出去。 */}
                        <div id="settings-billing-identity" role="tabpanel" aria-labelledby="settings-tab-billing-identity" hidden={tab==='settings' && settingsSection!=='billing-identity'} className="mt-4 pt-4 border-t border-gray-100 space-y-2 scroll-mt-24">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">开票信息</p>
                            <BillingIdentityPanel api={v1Api} showToast={showToast}
                                canManage={canManageOperations} />
                        </div>
                        <div id="settings-integrations" role="tabpanel" aria-labelledby="settings-tab-integrations" hidden={tab==='settings' && settingsSection!=='integrations'} className="mt-4 pt-4 border-t border-gray-100 space-y-2 scroll-mt-24">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">集成</p>
                            <IntegrationsPanel api={v1Api} showToast={showToast} canManage={ownerRoles.includes(actorRole)} />
                        </div>
                        <div id="settings-workspace" role="tabpanel" aria-labelledby="settings-tab-workspace" hidden={tab==='settings' && settingsSection!=='workspace'} className="mt-4 pt-4 border-t border-gray-100 space-y-2 scroll-mt-24">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">学员注册页面</p>
                            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                <span className="text-xs text-gray-500 flex-1 font-mono truncate">{window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`}</span>
                                <button type="button" onClick={()=>copyText(window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`,'链接已复制')}
                                    className="text-xs text-indigo-600 font-bold active:text-indigo-800 flex-shrink-0">复制</button>
                            </div>
                        </div>
                        <div className="mt-3 pt-3 border-t border-gray-100 space-y-2">
                            <button onClick={requestLogout} className="w-full bg-gray-100 active:bg-gray-200 text-gray-700 py-3 rounded-xl font-bold text-sm">退出登录</button>
                            {/* Mobile-only: sidebar actions inaccessible on phone */}
                            <div className="md:hidden space-y-2 pt-2 border-t border-gray-100">
                                <p className="text-[11px] font-bold text-gray-400 uppercase tracking-wide pb-0.5">快捷操作</p>
                                {TENANT_SLUG && <>
                                {/* Same judgement as the sidebar pair. This list
                                    already reads as filled = do it, soft accent
                                    = secondary, neutral = read-only, danger =
                                    destructive; 网站与品牌 is the one item worth
                                    leading with, so it takes the single filled
                                    slot instead of an unrelated green. */}
                                <a href={`/${encodeURIComponent(TENANT_SLUG)}/studio-admin`}
                                    className="flex items-center justify-center w-full bg-indigo-600 active:bg-indigo-700 py-3 rounded-xl font-bold text-sm min-h-[44px]">网站与品牌 · Studio Admin</a>
                                <a href={`/${encodeURIComponent(TENANT_SLUG)}`} target="_blank" rel="noopener"
                                    className="flex items-center justify-center w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-3 rounded-xl font-bold text-sm min-h-[44px]">查看公开网站</a>
                                </>}
                                <button onClick={()=>{load();closeSettings();}} disabled={busy}
                                    className="w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm"><span className="inline-flex items-center gap-1.5"><Icon name="refresh" className="w-4 h-4"/>刷新数据</span></button>
                                {canManageOperations && !TENANT_SLUG && <button onClick={()=>{exportDB();closeSettings();}}
                                    className="w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm"><span className="inline-flex items-center gap-1.5"><Icon name="download" className="w-4 h-4"/>备份导出</span></button>
                                }
                                <button onClick={()=>{closeSettings();confirm('确认退出登录？下次进入需重新输入密码。', doLogout, {confirmText:'退出登录'});}}
                                    className="w-full bg-red-50 active:bg-red-100 text-red-600 border border-red-200 py-3 rounded-xl font-bold text-sm"><span className="inline-flex items-center gap-1.5"><Icon name="logout" className="w-4 h-4"/>退出登录</span></button>
                            </div>
                        </div>
                    </div>
                </div>
            )}

            {/* ── Mobile top bar (md:hidden) ── */}
            <div className="md:hidden mobile-top-bar fixed top-0 left-0 right-0 z-40 cms-chrome border-b flex items-center px-3 gap-2.5">
                {tenantLogoUrl && <img src={tenantLogoUrl} alt={`${tenantDisplayName} logo`} className="h-8 w-auto max-w-[96px] object-contain flex-shrink-0"/>}
                <span className="font-bold text-base flex-1 truncate">{tenantDisplayName} CMS</span>
                <button onClick={()=>{setGOpen(true);setGQ('');}} aria-label="搜索"
                    className="w-9 h-9 flex items-center justify-center rounded-lg cms-chrome-item flex-shrink-0"><Icon name="search"/></button>
                {canViewCmsNotifications && <CmsNotificationCenter
                    notifications={cmsNotifications} unreadCount={cmsNotificationUnreadCount}
                    open={cmsNotificationOpen} onToggle={()=>setCmsNotificationOpen(open => !open)}
                    onSelect={openCmsNotification} onMarkAllRead={markAllCmsNotificationsRead}
                    loadError={cmsNotificationError}/>}
                <button onClick={()=>setSettingsSection('account')}
                    aria-label="设置" className="w-9 h-9 flex items-center justify-center rounded-lg cms-chrome-item flex-shrink-0"><Icon name="cog"/></button>
            </div>

            {/* Sidebar */}
            {/* P1: standalone(PWA)模式下 iPad 侧栏避开状态栏（浏览器内 env=0 无影响） */}
            <aside className="hidden md:flex w-60 cms-chrome border-r flex-col flex-shrink-0"
                style={{paddingTop:'env(safe-area-inset-top, 0px)'}}>
                <div className="p-4 border-b cms-chrome-edge flex items-center gap-2.5">
                    {tenantLogoUrl && <img src={tenantLogoUrl} alt={`${tenantDisplayName} logo`} className="h-9 w-auto max-w-[96px] object-contain flex-shrink-0"/>}
                    <div className="min-w-0 flex-1">
                        <h1 className="hidden md:block text-base font-bold tracking-wide truncate">{tenantDisplayName}</h1>
                        <p className="text-[11px] text-gray-400 tracking-wide">Studio CMS</p>
                    </div>
                </div>
                <nav className="flex-1 px-3 py-4 space-y-4 overflow-y-auto" aria-label="CMS 主导航">
                    {NAV_GROUPS.map(group => (
                        <section key={group.key} aria-labelledby={`cms-nav-${group.key}`}>
                            <p id={`cms-nav-${group.key}`} className="px-2 mb-1 text-[11px] font-bold tracking-wide text-gray-400">{group.label}</p>
                            <div className="space-y-0.5">
                                {group.items.map(({k,i,l,badge}) => (
                                    <button key={k} onClick={()=>setTab(k)}
                                        aria-current={tab===k ? 'page' : undefined}
                                        className={`w-full text-left px-3 py-2.5 rounded-xl flex items-center gap-2.5 text-sm min-h-[44px] cms-chrome-item ${tab===k?'is-active font-bold':''}`}>
                                        <Icon name={i}/>
                                        <span>{l}</span>
                                        {k==='dashboard' && analytics.lowBalance.length>0 &&
                                            <span className="ml-auto bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">{analytics.lowBalance.length}</span>}
                                        {badge>0 &&
                                            <span className="ml-auto bg-amber-400 text-white text-xs font-bold px-1.5 py-0.5 rounded-full">{badge}</span>}
                                    </button>
                                ))}
                            </div>
                        </section>
                    ))}
                </nav>
                <div className="p-3 border-t cms-chrome-edge space-y-1.5" style={{paddingBottom:'calc(env(safe-area-inset-bottom,0px) + 12px)'}}>
                    {TENANT_SLUG && <div className="grid grid-cols-2 gap-1.5 pb-1">
                        {/* These two are a pair of links OUT of the CMS, not a
                            success state. The green was picked when the CMS had
                            no palette; once every colour maps by role it made an
                            outbound link read as "something succeeded". They are
                            peers, so the difference between them has to be
                            hierarchy, not hue: editing the brand is the
                            accented action, viewing the live site is the quiet
                            read-only one, and it takes the same chrome inset as
                            the 刷新 / 设置 buttons directly below. That contrast
                            survives a palette change; green vs blue did not. */}
                        {/* The ONE saturated fill this surface is allowed. It
                            is the action that leaves the CMS for the branding
                            editor; everything below is chrome. */}
                        <a href={`/${encodeURIComponent(TENANT_SLUG)}/studio-admin`}
                            className="flex items-center justify-center rounded-lg bg-indigo-600 text-white active:bg-indigo-700 px-2 py-2.5 text-[11px] font-bold min-h-[44px]">网站与品牌</a>
                        <a href={`/${encodeURIComponent(TENANT_SLUG)}`} target="_blank" rel="noopener"
                            className="flex items-center justify-center rounded-lg cms-chrome-item border cms-chrome-edge px-2 py-2.5 text-[11px] font-bold min-h-[44px]">公开网站</a>
                    </div>}
                    <div className="text-xs text-center rounded-lg p-1.5 border bg-green-50 text-green-700 border-green-200"><span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-green-500" aria-hidden="true"></span>已连接</span></div>
                    {db.logs.length > 1000 && (
                        <div className="text-xs text-center rounded-lg p-1.5 border bg-amber-50 text-amber-700 border-amber-200">
                            <span className="inline-flex items-center gap-1.5"><Icon name="warning" className="w-3.5 h-3.5"/>日志 {db.logs.length} 条</span>
                        </div>
                    )}
                    {canManageOperations && !TENANT_SLUG && <button onClick={exportDB} className="inline-flex items-center gap-1.5 w-full cms-chrome-item border cms-chrome-edge p-2.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="download" className="w-4 h-4"/>备份导出</button>}
                    <button onClick={load} disabled={busy} className="inline-flex items-center gap-1.5 w-full cms-chrome-item border cms-chrome-edge p-2.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="refresh" className="w-4 h-4"/>刷新</button>
                    <button onClick={()=>setSettingsSection('account')} className={`w-full cms-chrome-item border cms-chrome-edge p-2.5 rounded-xl text-xs font-bold min-h-[44px] ${tab==='settings'?'is-active':''}`}><span className="inline-flex items-center gap-1.5"><Icon name="cog" className="w-4 h-4"/>系统设置</span></button>
                    <button onClick={()=>confirm('确认退出登录？下次进入需重新输入密码。', doLogout, {confirmText:'退出登录'})}
                        className="w-full cms-chrome-item p-2.5 rounded-xl text-xs font-bold min-h-[44px] active:bg-red-50 active:text-red-700"><span className="inline-flex items-center gap-1.5"><Icon name="logout" className="w-4 h-4"/>退出登录</span></button>
                </div>
            </aside>

            {/* Main content */}
            {/* P1: 主内容区在 iPad standalone 下避开状态栏与底部 Home 条
                （inline 样式在手机端会被 .mobile-main-top/.mobile-pb 的 !important 覆盖，互不影响） */}
            <main className="flex-1 overflow-y-auto p-4 md:pt-0 md:p-6 md:pb-0 sl mobile-main-top mobile-pb"
                style={{paddingTop:'calc(1.5rem + env(safe-area-inset-top, 0px))',
                        paddingBottom:'env(safe-area-inset-bottom, 0px)'}}>

                {/* Desktop top app bar. The 240px rail + 960px content measure
                    keeps the shell close to a 1:1.618 visual relationship:
                    identity and navigation stay stable while the working area
                    gets the larger share of the viewport. */}
                <header className="hidden md:flex sticky top-0 z-30 -mx-6 px-6 h-16 items-center gap-4 bg-gray-50/95 backdrop-blur border-b border-gray-200">
                    <div className="flex items-center gap-2 min-w-[210px]">
                        {tab !== 'dashboard' && <button type="button" onClick={()=>setTab('dashboard')} aria-label="返回工作台"
                            className="w-10 h-10 inline-flex items-center justify-center rounded-xl cms-chrome-item border border-gray-200"><Icon name="chevronLeft"/></button>}
                        <div className="min-w-0">
                            <p className="text-[11px] font-bold tracking-[0.16em] text-indigo-500 uppercase">Studio CMS</p>
                            <h2 className="text-lg font-bold text-gray-900 truncate">{cmsPageTitle}</h2>
                        </div>
                    </div>
                    <button type="button" onClick={()=>{setGOpen(true);setGQ('');}} aria-label="搜索学员、手机号或功能"
                        className="flex-1 max-w-2xl min-h-[44px] px-4 rounded-xl border border-gray-200 bg-white text-left text-sm text-gray-400 shadow-sm hover:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-400">
                        <span className="inline-flex items-center gap-2"><Icon name="search" className="w-4 h-4"/>搜索学员、手机号或功能</span>
                        <kbd className="float-right hidden lg:inline-flex rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500">⌘K</kbd>
                    </button>
                    <div className="ml-auto flex items-center gap-2">
                        {canViewCmsNotifications && <CmsNotificationCenter
                            notifications={cmsNotifications} unreadCount={cmsNotificationUnreadCount}
                            open={cmsNotificationOpen} onToggle={()=>setCmsNotificationOpen(open => !open)}
                            onSelect={openCmsNotification} onMarkAllRead={markAllCmsNotificationsRead}
                            loadError={cmsNotificationError}/>}
                        <button type="button" onClick={load} disabled={busy} title="刷新 CMS 数据" aria-label="刷新 CMS 数据"
                            className="hidden lg:inline-flex items-center gap-2 min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-600 hover:border-indigo-300 disabled:opacity-50">
                            <span className={`w-2 h-2 rounded-full ${conn?'bg-emerald-500':'bg-amber-400'}`} aria-hidden="true"></span>{conn?'已同步':'连接中'}
                        </button>
                        <div className="relative">
                            <button type="button" onClick={()=>setUserMenuOpen(open=>!open)} aria-expanded={userMenuOpen} aria-haspopup="menu"
                                className="min-h-[44px] inline-flex items-center gap-2 rounded-xl px-2 hover:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400">
                                <span className="w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 inline-flex items-center justify-center text-sm font-bold">{(actorRoleLabel[0]||'U').toUpperCase()}</span>
                                <span className="hidden xl:block text-left max-w-[140px]"><span className="block text-xs font-bold text-gray-800 truncate">{actorIdentity}</span><span className="block text-[11px] text-gray-400">{actorRoleLabel}</span></span>
                            </button>
                            {userMenuOpen && <div role="menu" className="absolute right-0 top-12 z-50 w-64 rounded-2xl border border-gray-200 bg-white p-2 shadow-xl anim">
                                <div className="px-3 py-2 border-b border-gray-100 mb-1"><p className="text-xs font-bold text-gray-800 truncate">{actorIdentity}</p><p className="text-[11px] text-gray-400 mt-0.5">{actorRoleLabel}</p></div>
                                <button type="button" role="menuitem" onClick={()=>{setUserMenuOpen(false);setSettingsSection('account');}} className="w-full text-left px-3 py-2.5 rounded-xl text-sm font-bold hover:bg-indigo-50">账号与安全</button>
                                <div className="px-3 py-2 text-[11px] text-gray-400 font-bold">界面语言</div>
                                <div className="grid grid-cols-2 gap-1 px-1 mb-1">
                                    <button type="button" onClick={()=>document.querySelector('[data-cms-language="zh"]')?.click()} className="min-h-[44px] rounded-lg bg-gray-50 text-xs font-bold text-gray-700 hover:bg-indigo-50">中文</button>
                                    <button type="button" onClick={()=>document.querySelector('[data-cms-language="en"]')?.click()} className="min-h-[44px] rounded-lg bg-gray-50 text-xs font-bold text-gray-700 hover:bg-indigo-50">English</button>
                                </div>
                                {TENANT_SLUG && <a role="menuitem" href={`/${encodeURIComponent(TENANT_SLUG)}/studio-admin`} className="block px-3 py-2.5 rounded-xl text-sm font-bold text-indigo-700 hover:bg-indigo-50">网站与品牌 · Studio Admin</a>}
                                <button type="button" role="menuitem" onClick={()=>{setUserMenuOpen(false);confirm('确认退出登录？下次进入需重新输入密码。', doLogout, {confirmText:'退出登录'});}} className="w-full text-left px-3 py-2.5 rounded-xl text-sm font-bold text-red-600 hover:bg-red-50">退出登录</button>
                            </div>}
                        </div>
                    </div>
                </header>

{/* ═══ DASHBOARD ══════════════════════════════════════════════ */}
{tab==='dashboard' && (
<div className="cms-dashboard-root anim space-y-5">
    <h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="dashboard" className="w-4 h-4"/>工作台</h2>
    {(()=>{
        const actionsByRole = {
            owner:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','搜索学员',analytics.totalStudents,'users'],['stats','查看经营统计',null,'trend']],
            platform_super_admin:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','搜索学员',analytics.totalStudents,'users'],['stats','查看经营统计',null,'trend']],
            super_admin:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','搜索学员',analytics.totalStudents,'users'],['stats','查看经营统计',null,'trend']],
            manager:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['topup','充值与退款',null,'money'],['stats','查看经营统计',null,'trend']],
            teacher:[['roster','今日课程名单',todayEffectiveCount,'calendar'],['students','查找学员',analytics.totalStudents,'users'],['works','上传作品',null,'image'],['logs','查看操作记录',null,'scroll']],
            front_desk:[['pending','处理报名与约课',pendingCount,'clipboard'],['new_student','新建学员',null,'plus'],['topup','充值与退款',null,'money'],['students','查找学员',analytics.totalStudents,'users']],
            staff:[['pending','处理待处理',pendingCount,'clipboard'],['roster','查看今日课程',todayEffectiveCount,'calendar'],['students','查找学员',analytics.totalStudents,'users'],['works','管理作品',null,'image']],
        };
        const actions = (actionsByRole[actorRole] || actionsByRole.staff).filter(([key])=>allowedTabs.includes(key));
        return <section className="rounded-2xl border border-indigo-100 bg-white p-4 shadow-sm" aria-labelledby="role-workbench-title">
            <div className="flex items-center justify-between gap-3 mb-3"><div><h3 id="role-workbench-title" className="text-sm font-bold text-gray-900">今日重点</h3><p className="text-xs text-gray-400 mt-0.5">按你的角色排列最常用的工作入口</p></div><span className="text-[11px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-100 rounded-full px-2.5 py-1">{actorRoleLabel}</span></div>
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-2">{actions.slice(0,4).map(([key,label,count,icon])=><button key={key} type="button" onClick={()=>setTab(key)} className="min-h-[62px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left hover:border-indigo-300 hover:bg-indigo-50"><span className="flex items-center gap-1.5 text-xs font-bold text-gray-700"><Icon name={icon} className="w-4 h-4 text-indigo-600"/>{label}</span>{count !== null && <span className="block text-lg font-bold text-indigo-700 mt-1 tabular-nums">{count}</span>}</button>)}</div>
        </section>;
    })()}
    {actorRole==='teacher' && <div className="md:hidden rounded-2xl border border-emerald-200 bg-emerald-50 p-3">
        <p className="text-xs font-bold text-emerald-900 mb-2">教师手机快捷流程 · 3 步完成今日工作</p>
        <div className="grid grid-cols-3 gap-2">
            <button onClick={()=>{setRDate(todayISO());setTab('roster');}}
                className="min-h-[56px] rounded-xl bg-white border border-emerald-200 px-2 py-2 text-[11px] font-bold text-emerald-900">1 · 今日名单</button>
            <button onClick={()=>{setGOpen(true);setGQ('');}}
                className="min-h-[56px] rounded-xl bg-white border border-emerald-200 px-2 py-2 text-[11px] font-bold text-emerald-900">2 · 找到学员</button>
            <button onClick={()=>{setTab('students');showToast('选择学员后，在作品区上传今日作品。');}}
                className="min-h-[56px] rounded-xl bg-emerald-700 px-2 py-2 text-[11px] font-bold text-white">3 · 上传作品</button>
        </div>
    </div>}
    {scheduleLoadError && <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        <span className="flex-1">{scheduleLoadError}</span>
        <button onClick={loadSchedules} className="rounded-xl border border-red-200 bg-white px-3 py-2 text-xs font-bold min-h-[44px]">重试</button>
    </div>}
    <div className={TENANT_SLUG ? 'cms-dashboard-lead' : ''}>
    {TENANT_SLUG && (
        <div className="cms-command-card bg-gradient-to-br from-indigo-900 to-indigo-700 text-white rounded-2xl p-4 shadow-lg">
            <div className="flex items-center justify-between gap-3 mb-3">
                <div><p className="text-xs text-indigo-200 tracking-wider">TODAY · 今日指挥台</p><p className="font-bold mt-0.5">先处理最需要行动的事项</p></div>
                <span className="text-xs bg-white/10 border border-white/20 px-2.5 py-1 rounded-full">{fmtDate(todayISO())}</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-3">
                {[
                    ['应到',todayEffectiveCount,'人'],['已签到',todayCheckedCount,'人'],
                    ['待审核',pendingCount,'项'],['低课时',analytics.lowBalance.length,'人'],
                ].map(([label,value,unit])=><div key={label} className="rounded-xl bg-white/10 border border-white/10 p-2.5"><p className="text-[11px] text-indigo-200">{label}</p><p className="text-xl font-bold">{value}<span className="text-xs font-normal ml-1">{unit}</span></p></div>)}
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {canWriteAttendance && <button onClick={()=>{setRDate(todayISO());setTab('roster');}} className="bg-white text-indigo-800 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/>今日排课</span></button>}
                {canWriteStudents && <button onClick={()=>setTab('new_student')} className="bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="plus" className="w-4 h-4"/>新建学员</span></button>}
                {allowedTabs.includes('pending') && <button onClick={()=>setTab('pending')} className="bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>审核报名</span></button>}
                {canWriteCredits && <button onClick={()=>setTab('topup')} className="bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="money" className="w-4 h-4"/>充值结算</span></button>}
            </div>
        </div>
    )}
    <div className="cms-kpi-grid">
        {[{l:'学员总数',      v:`${analytics.totalStudents} 人`,             c:'text-gray-800',    action:()=>{setSortBy('date-desc');setFilterBy('all');setTab('students');}},
          {l:'全部剩余课时',  v:`${analytics.totalBalance} 课时`,             c:'text-indigo-600',  action:()=>{setSortBy('bal-desc');setFilterBy('active');setTab('students');}},
          {l:'今日排课',      v:`${TENANT_SLUG ? todayEffectiveCount : analytics.todayRoster.length} 人`,         c:'text-gray-700',    action:()=>setTab('roster')},
          canViewFinancialAnalytics
            ? {l:'历史总营收', v:`$${analytics.totalRevenue.toFixed(0)}`, c:'text-emerald-600', action:()=>setTab('stats')}
            : {l:'本月出勤', v:`${bizStats?.attended_month || 0} 人次`, c:'text-emerald-600', action:()=>setTab('roster')},
        ].map(({l,v,c,action})=>(
            <button key={l} onClick={action}
                className="bg-white p-4 rounded-2xl shadow-sm border border-indigo-100 text-left w-full active:bg-indigo-50 transition">
                <p className="text-gray-400 text-xs mb-1">{l} <span className="text-indigo-400">→</span></p>
                <p className={`text-2xl font-bold ${c}`}>{v}</p>
            </button>
        ))}
    </div>
    </div>

    {/* v9.1: readiness is operational only when every number opens the exact
        students that need work. The same filter values are available in the
        student list, so this is not a decorative dashboard dead-end. */}
    {TENANT_SLUG && (()=>{
        const students = db.students.filter(student=>!student.archived);
        const metrics = [
            ['专区已就绪', students.filter(s=>s.mobile&&s.hasAccessCode).length, 'portal-ready', 'lock'],
            ['缺少手机号', students.filter(s=>!s.mobile).length, 'portal-missing-mobile', 'phone'],
            ['专区未启用', students.filter(s=>s.mobile&&!s.hasAccessCode).length, 'portal-disabled', 'warning'],
            ['私人内容受阻', students.filter(s=>(s.portfolio||[]).length>0&&(!s.mobile||!s.hasAccessCode)).length, 'portal-content-blocked', 'image'],
            ['作品已公开', students.filter(s=>(s.portfolio||[]).some(item=>item.public||item.visibility==='shared')).length, 'publication-live', 'image'],
            ['公开授权有效', students.filter(s=>s.publicationConsent?.status==='confirmed').length, 'publication-ready', 'shield'],
            ['有作品但缺授权', students.filter(s=>(s.portfolio||[]).length>0&&s.publicationConsent?.status!=='confirmed').length, 'publication-missing-consent', 'warning'],
        ];
        return <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-start justify-between gap-3 mb-3">
                <div><p className="font-bold text-sm text-gray-800">学员专区与作品发布</p><p className="text-xs text-gray-400 mt-0.5">点击数字直接处理对应学员</p></div>
                <Icon name="shield" className="w-5 h-5 text-indigo-500"/>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2">
                {metrics.map(([label,value,filter,icon])=><button key={filter} type="button" onClick={()=>{setFilterBy(filter);setTab('students');}}
                    className="min-h-[68px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left active:border-indigo-300 active:bg-indigo-50">
                    <span className="flex items-center gap-1.5 text-xs text-gray-500"><Icon name={icon} className="w-3.5 h-3.5"/>{label}</span>
                    <span className="mt-1 block text-xl font-bold text-gray-900 tabular-nums">{value}</span>
                </button>)}
            </div>
        </div>;
    })()}

    {/* A3: 经营真账（估算）— 现金 vs 已赚 vs 预收负债（v5.3） */}
    {TENANT_SLUG && bizStats && (
        <details className="bg-white rounded-2xl shadow-sm border border-emerald-100">
            {/* D: roles without analytics:read only receive attended_total/attended_month —
               the financial fields are absent, so render those cards only when present. */}
            <summary className="inline-flex items-center gap-1.5 cursor-pointer px-4 py-3 font-bold text-sm text-gray-800 select-none"><Icon name="trend" className="w-4 h-4"/>{canViewFinancialAnalytics ? '经营真账（估算）' : '教学出勤'} <span className="text-xs font-normal text-gray-400">已上课 {bizStats.attended_total} 人次{bizStats.avg_price !== undefined ? ` · 加权均价 $${bizStats.avg_price}/课时` : ''}</span></summary>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 px-4 pb-4">
                {[
                    ['已上课人次', `${bizStats.attended_total} 次`, `本月 ${bizStats.attended_month} 次`, 'text-gray-800'],
                    ...(bizStats.earned_revenue !== undefined ? [['已赚收入(估)', `$${bizStats.earned_revenue}`, '人次 × 加权均价', 'text-emerald-600']] : []),
                    ...(bizStats.prepaid_liability !== undefined ? [['预收未耗(负债)', `$${bizStats.prepaid_liability}`, '剩余课时 × 均价', 'text-amber-600']] : []),
                    ...(bizStats.cash_net !== undefined ? [['净现金收入', `$${bizStats.cash_net}`, '充值 − 退款', 'text-indigo-600']] : []),
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
        const todoRisk    = db.students.filter(s => !s.archived && (parseInt(s.balance,10)||0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.id]||0) === 0);
        const now = new Date(); now.setHours(0,0,0,0); // normalise to midnight so today's birthdays are included
        const weekEnd = new Date(now); weekEnd.setDate(weekEnd.getDate()+7);
        const todoBdayWeek  = db.students.filter(s => { if(!s.birthday||s.archived) return false; const bd=new Date(now.getFullYear(),parseInt(s.birthday.slice(5,7),10)-1,parseInt(s.birthday.slice(8,10),10)); return bd>=now&&bd<=weekEnd; });
        const todoBdayMonth = db.students.filter(s => { if(!s.birthday||s.archived) return false; return s.birthday.slice(5,7)===String(now.getMonth()+1).padStart(2,'0') && !todoBdayWeek.includes(s); });
        const todoFollowUp = (db.pending||[]).filter(item=>item.nextFollowUpAt && String(item.nextFollowUpAt).slice(0,10)<=todayISO());
        const total = todoClear.length + todoLast.length + todoRisk.length + todoBdayWeek.length + todoBdayMonth.length + todoFollowUp.length;
        if (!total) return null;
        const names = (arr, max=4) => arr.slice(0,max).map(s=>s.name).join('、') + (arr.length>max?` 等${arr.length}人`:'');
        return (
            <div className="bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm">
                <div className="px-4 py-3 bg-gray-50 border-b flex items-center justify-between">
                    <p className="inline-flex items-center gap-1.5 font-bold text-gray-700 text-sm"><Icon name="clock" className="w-4 h-4"/>今日待办</p>
                    <span className="bg-indigo-600 text-white text-xs font-bold px-2 py-0.5 rounded-full">{total} 项</span>
                </div>
                <div className="divide-y divide-gray-50">
                    {todoFollowUp.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-indigo-700"><Icon name="phone" className="w-4 h-4"/>报名跟进到期 · {todoFollowUp.length} 项</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{todoFollowUp.slice(0,4).map(item=>`${item.firstName||''} ${item.lastName||''}`.trim()).join('、')}</p>
                            </div>
                            <button onClick={()=>setTab('pending')}
                                className="flex-shrink-0 text-xs text-indigo-600 font-bold bg-indigo-50 active:bg-indigo-100 border border-indigo-200 px-3 py-1.5 rounded-xl min-h-[38px]">处理 →</button>
                        </div>
                    )}
                    {todoClear.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-red-700"><Icon name="warning" className="w-4 h-4"/>课时已清零 · {todoClear.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoClear)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('zero');setTab('students');}}
                                className="flex-shrink-0 text-xs text-red-600 font-bold bg-red-50 active:bg-red-100 border border-red-200 px-3 py-1.5 rounded-xl min-h-[38px]">查看 →</button>
                        </div>
                    )}
                    {todoLast.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-orange-700"><Icon name="bolt" className="w-4 h-4"/>最后 1 课时 · {todoLast.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoLast)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('low');setTab('students');}}
                                className="flex-shrink-0 text-xs text-orange-600 font-bold bg-orange-50 active:bg-orange-100 border border-orange-200 px-3 py-1.5 rounded-xl min-h-[38px]">查看 →</button>
                        </div>
                    )}
                    {todoRisk.length > 0 && (
                        <div className="flex items-center justify-between px-4 py-3 gap-3">
                            <div className="min-w-0">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-amber-700"><Icon name="warning" className="w-4 h-4"/>流失风险 · {todoRisk.length} 人</p>
                                <p className="text-xs text-gray-400 truncate mt-0.5">{names(todoRisk)}</p>
                            </div>
                            <button onClick={()=>{setFilterBy('tag-risk');setTab('students');}}
                                className="flex-shrink-0 text-xs text-amber-600 font-bold bg-amber-50 active:bg-amber-100 border border-amber-200 px-3 py-1.5 rounded-xl min-h-[38px]">查看 →</button>
                        </div>
                    )}
                    {todoBdayWeek.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-pink-600"><Icon name="cake" className="w-4 h-4"/>本周生日 · {todoBdayWeek.length} 人</p>
                                <button onClick={()=>{ const msg=todoBdayWeek.map(s=>`祝 ${s.name} 生日快乐！愿新的一年里画艺大进，心想事成！`).join('\n'); copyText(msg,'祝福语已复制'); }}
                                    className="flex-shrink-0 text-xs text-pink-600 font-bold bg-pink-50 active:bg-pink-100 border border-pink-200 px-3 py-1.5 rounded-xl min-h-[38px]">复制祝福 →</button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {todoBdayWeek.map(s=>(
                                    <span key={s.id} className="inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700">
                                        {s.name}
                                        {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent('祝 '+s.name+' 生日快乐！愿新的一年里画艺大进，心想事成！')}`} aria-label="发送祝福短信" className="text-pink-400 ml-0.5 active:text-pink-600 inline-flex"><Icon name="chat" className="w-3.5 h-3.5"/></a>}
                                    </span>
                                ))}
                            </div>
                        </div>
                    )}
                    {todoBdayMonth.length > 0 && (
                        <div className="px-4 py-3 space-y-2">
                            <div className="flex items-center justify-between gap-3">
                                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-pink-400"><Icon name="cake" className="w-4 h-4"/>本月生日 · {todoBdayMonth.length} 人</p>
                                <button onClick={()=>{ const msg=todoBdayMonth.map(s=>`祝 ${s.name} 生日快乐！愿新的一年里画艺大进，心想事成！`).join('\n'); copyText(msg,'祝福语已复制'); }}
                                    className="flex-shrink-0 text-xs text-pink-400 font-bold bg-pink-50 active:bg-pink-100 border border-pink-100 px-3 py-1.5 rounded-xl min-h-[38px]">复制祝福 →</button>
                            </div>
                            <div className="flex flex-wrap gap-1.5">
                                {todoBdayMonth.map(s=>(
                                    <span key={s.id} className="inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700">
                                        {s.name}
                                        {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent('祝 '+s.name+' 生日快乐！愿新的一年里画艺大进，心想事成！')}`} aria-label="发送祝福短信" className="text-pink-400 ml-0.5 active:text-pink-600 inline-flex"><Icon name="chat" className="w-3.5 h-3.5"/></a>}
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
                    <span className="inline-flex items-center gap-1.5 text-2xl"><Icon name="clipboard" className="w-4 h-4"/></span>
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
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
            <p className="inline-flex items-center gap-1.5 font-bold text-amber-800 mb-2 text-sm"><Icon name="calendar" className="w-4 h-4"/>长期未到访 — {analytics.inactive.length} 名学员有余额但超过 {inactiveDays} 天未上课</p>
            <div className="flex flex-wrap gap-2">
                {analytics.inactive.slice(0,12).map(s => (
                    <button key={s.id} onClick={()=>{setTab('students');setSrch(s.name);}}
                        className="px-3 py-1.5 rounded-lg text-xs font-bold bg-blue-100 text-amber-800 border border-blue-200 active:bg-blue-200 min-h-[44px]">
                        {/* daysSince returns the 9999 sentinel for "no class on
                            record"; printing it raw read as "9999天前". */}
                        {s.name} ({s.balance}课 · {daysSince(s.lastActive)<9999?`${daysSince(s.lastActive)}天前`:'从未上课'})
                    </button>
                ))}
            </div>
        </div>
    )}

    {/* 低余额预警 */}
    {analytics.lowBalance.length>0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4">
            <p className="inline-flex items-center gap-1.5 font-bold text-amber-800 mb-2 text-sm"><Icon name="bolt" className="w-4 h-4"/>课时预警 — {analytics.lowBalance.length} 名学员余额 ≤ 2 课时</p>
            <div className="flex flex-wrap gap-2">
                {analytics.lowBalance.map(s => (
                    <button key={s.id} onClick={()=>{setTab('students');setSrch(s.name);}}
                        className={`px-3 py-1.5 rounded-lg text-xs font-bold border min-h-[44px] ${parseInt(s.balance,10)===0?'bg-red-100 text-red-700 border-red-200':'bg-amber-100 text-amber-800 border-amber-200'}`}>
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
        {analytics.recentGroups.length===0 && <EmptyState icon={<Icon name="scroll" className="w-8 h-8"/>} main="还没有账目记录"
                sub="签到会记一笔消课，充值会记一笔收入。今天做过其中任何一项，这里就会出现流水。"
                action="去今日排课" onAction={()=>{setRDate(todayISO());setTab('roster');}}/>}
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

{/* ═══ COURSES ════════════════════════════════════════════════ */}
{tab==='courses' && (
<div className="anim space-y-5 max-w-6xl mx-auto">
    <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
            <h2 className="md:hidden inline-flex items-center gap-2 text-xl font-bold text-gray-800"><Icon name="calendar" className="w-5 h-5"/>课程目录</h2>
            <p className="text-sm text-gray-500 mt-1">维护可被固定课表引用的课程条目；公开课表是否展示详情仍由 Studio Admin 控制。</p>
        </div>
        <button type="button" onClick={()=>setTab('roster')} className="min-h-[44px] px-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-bold">查看课程安排 →</button>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-[1.618fr_1fr] gap-5 items-start">
        <section id="courseManager" className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5 space-y-3 scroll-mt-24" aria-labelledby="course-list-title">
            <div className="flex items-center justify-between gap-3"><div><h3 id="course-list-title" className="font-bold text-gray-900">已启用课程</h3><p className="text-xs text-gray-400 mt-0.5">{courses.length} 门课程</p></div>{canManageOperations && <button type="button" onClick={()=>setCourseEdit({name:'',description:'',ageRange:'',durationMinutes:60,priceAud:''})} className="min-h-[44px] px-3 rounded-xl bg-indigo-600 text-white text-xs font-bold"><Icon name="plus" className="w-4 h-4 inline mr-1"/>添加课程</button>}</div>
            {courses.length === 0 && <EmptyState icon={<Icon name="calendar" className="w-8 h-8"/>} main="还没有课程" sub="先添加一门课程，再回到课程安排关联固定班次。" action={canManageOperations ? '添加第一门课程' : ''} onAction={canManageOperations ? ()=>setCourseEdit({name:'',description:'',ageRange:'',durationMinutes:60,priceAud:''}) : undefined}/>}
            <div className="space-y-2">
                {courses.map(course => <article key={course.id} className="rounded-2xl border border-gray-200 bg-gray-50 p-4 flex items-start gap-3">
                    <div className="w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 inline-flex items-center justify-center flex-shrink-0"><Icon name="calendar" className="w-5 h-5"/></div>
                    <div className="min-w-0 flex-1"><h4 className="font-bold text-gray-900 truncate">{course.name}</h4><p className="text-xs text-gray-500 mt-1">{[course.age_range && `适龄 ${course.age_range}`,course.duration_minutes && `${course.duration_minutes} 分钟`,course.price_aud_cents ? `AUD ${(course.price_aud_cents/100).toFixed(2)}` : '未标价'].filter(Boolean).join(' · ')}</p>{course.description && <p className="text-sm text-gray-600 mt-2 leading-relaxed">{course.description}</p>}</div>
                    {canManageOperations && <div className="flex items-center gap-1 flex-shrink-0"><button type="button" onClick={()=>setCourseEdit({id:course.id,name:course.name,description:course.description||'',ageRange:course.age_range||'',durationMinutes:course.duration_minutes||60,priceAud:course.price_aud_cents ? String(course.price_aud_cents/100) : ''})} className="min-h-[44px] px-3 rounded-xl text-xs font-bold text-indigo-700 hover:bg-indigo-100">编辑</button><button type="button" onClick={()=>archiveCourse(course)} aria-label={`归档课程 ${course.name}`} className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-red-600 hover:bg-red-50"><Icon name="archiveBox" className="w-4 h-4"/></button></div>}
                </article>)}
            </div>
        </section>
        <aside className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5" aria-labelledby="course-help-title">
            <h3 id="course-help-title" className="font-bold text-gray-900">这组信息会影响什么？</h3>
            <div className="mt-3 space-y-3 text-sm text-gray-600 leading-relaxed"><p><strong className="text-gray-800">课程名称和简介</strong>：供固定课表关联，是否对外显示取决于 Studio Admin 的公开课表开关。</p><p><strong className="text-gray-800">适龄段、时长和价格</strong>：用于公开课程详情和内部排课参考，不会改动已经保存的排课。</p><p className="rounded-xl bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-800">归档不是删除。历史排课仍保留原课程名称，新排课不会再出现已归档课程。</p></div>
        </aside>
    </div>
    {courseEdit && canManageOperations && <div className="fixed inset-0 z-[70] bg-black/40 flex items-end md:items-center justify-center p-0 md:p-4" role="dialog" aria-modal="true" aria-labelledby="course-editor-title" onClick={()=>setCourseEdit(null)}>
        <div className="bg-white w-full md:max-w-xl rounded-t-2xl md:rounded-2xl p-5 md:p-6 space-y-4" onClick={e=>e.stopPropagation()}>
            <div><h3 id="course-editor-title" className="text-lg font-bold text-gray-900">{courseEdit.id ? '编辑课程' : '添加课程'}</h3><p className="text-xs text-gray-500 mt-1">带 * 为必填；保存后可在课程安排中关联。</p></div>
            <label className="block text-sm font-bold text-gray-700">课程名称 *<input id="course-name" type="text" required value={courseEdit.name} onChange={e=>setCourseEdit(p=>({...p,name:e.target.value}))} placeholder="例如：儿童油画基础" className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/><span className="block text-xs font-normal text-gray-400 mt-1">用于内部排课和公开课表标题。</span></label>
            <label className="block text-sm font-bold text-gray-700">课程简介 <span className="font-normal text-gray-400">选填</span><textarea rows="3" value={courseEdit.description} onChange={e=>setCourseEdit(p=>({...p,description:e.target.value}))} placeholder="介绍课程内容、适合的学习目标" className="mt-1 w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/><span className="block text-xs font-normal text-gray-400 mt-1">会随公开课表配置显示给访客。</span></label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><label className="block text-sm font-bold text-gray-700">适龄段 <span className="font-normal text-gray-400">选填</span><input type="text" value={courseEdit.ageRange} onChange={e=>setCourseEdit(p=>({...p,ageRange:e.target.value}))} placeholder="6–9 岁" className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/></label><label className="block text-sm font-bold text-gray-700">时长（分钟） *<input type="number" min="1" required value={courseEdit.durationMinutes} onChange={e=>setCourseEdit(p=>({...p,durationMinutes:e.target.value}))} className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/></label><label className="block text-sm font-bold text-gray-700">价格（AUD） <span className="font-normal text-gray-400">选填</span><input type="number" min="0" step="0.01" value={courseEdit.priceAud} onChange={e=>setCourseEdit(p=>({...p,priceAud:e.target.value}))} placeholder="0.00" className="mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/></label></div>
            <div className="flex gap-2 pt-1"><button type="button" onClick={()=>setCourseEdit(null)} className="flex-1 min-h-[48px] rounded-xl border border-gray-300 text-sm font-bold text-gray-600">取消</button><button type="button" onClick={saveCourse} disabled={busy} className="flex-1 min-h-[48px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">{busy?'保存中…':'保存课程'}</button></div>
        </div>
    </div>}
</div>
)}

{/* ═══ ROSTER ═════════════════════════════════════════════════ */}
{tab==='roster' && (
<div className="anim space-y-4">
    <h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="calendar" className="w-4 h-4"/>课程安排</h2>
    {/* 一对一循环课收在一个可折叠区块里，而不是新开一个导航项：它和班课
        回答的是同一个问题（这周谁什么时候上课），只是重复方式不同。默认
        折叠，因为只教班课的工作室不该被一块空面板挡住每天要看的课表。 */}
    {TENANT_SLUG && (
        <details className="border border-indigo-100 rounded-2xl overflow-hidden group">
            <summary className="list-none cursor-pointer min-h-[44px] px-4 py-3 flex items-center justify-between gap-3 bg-indigo-50 text-sm font-bold text-indigo-800">
                <span className="inline-flex items-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/>一对一循环课与补课额度</span>
                <span className="group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
            </summary>
            <div className="p-3 bg-white">
                <PrivateLessonsPanel api={v1Api} showToast={showToast}
                    canWrite={canWriteScheduling} students={db.students.filter(s=>!s.archived)} />
            </div>
        </details>
    )}
    {scheduleLoadError && <div className="flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        <span className="flex-1">{scheduleLoadError}</span>
        <button onClick={loadSchedules} className="rounded-xl border border-red-200 bg-white px-3 py-2 text-xs font-bold min-h-[44px]">重试</button>
    </div>}
    {/* G1: 生日提醒横幅 */}
    {upcomingBirthdays.length>0 && (
        <details className="bg-pink-50 border border-pink-200 rounded-2xl overflow-hidden group">
            <summary className="list-none cursor-pointer min-h-[44px] px-4 py-2 flex items-center justify-between gap-3 text-sm font-bold text-rose-700">
                <span className="inline-flex items-center gap-1.5"><Icon name="cake" className="w-4 h-4"/>近 14 天生日（{upcomingBirthdays.length} 人）</span>
                <span className="group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
            </summary>
            <div className="flex flex-wrap gap-2 px-4 pb-4 border-t border-pink-200 pt-3">
                {upcomingBirthdays.map(({s,in:days,md,age})=>(
                    <button key={s.id} onClick={()=>{
                        const msg = renderMessage('birthday',
                            '{student} 您好！{studio} 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、收获满满～',
                            {student:s.name});
                        copyText(msg, `已复制给 ${s.name} 的生日祝福`);
                    }} className="bg-white border border-pink-200 active:bg-pink-50 rounded-xl px-3 py-2 text-left">
                        <p className="text-sm font-bold text-gray-800">{s.name} <span className="text-xs font-normal text-rose-400">{days===0?'今天':`${md} (${days}天后)`}</span></p>
                        <p className="text-[11px] text-gray-400">点击复制生日祝福话术</p>
                    </button>
                ))}
            </div>
        </details>
    )}
    {/* A1: 每周课表 — 固定班次自动生成当日课程安排 */}
    {TENANT_SLUG && (
    <details className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden group">
        <summary className="list-none cursor-pointer min-h-[52px] px-4 py-3 flex items-center justify-between gap-3">
            <span className="inline-flex items-center gap-2 min-w-0">
                <Icon name="calendar" className="w-4 h-4 text-gray-500"/>
                <span><span className="block text-sm font-bold text-gray-800">固定课表</span><span className="block text-xs font-normal text-gray-400">{schedules.length ? `${schedules.length} 个每周班次` : '创建每周自动排课班次'}</span></span>
            </span>
            <span className="text-indigo-600 group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
        </summary>
        <div className="p-4 space-y-3 border-t border-gray-100">
        <div className="flex justify-between items-center gap-2 flex-wrap">
            <p className="inline-flex items-center gap-1.5 font-bold text-sm text-gray-800"><Icon name="calendar" className="w-4 h-4"/>每周课表 <span className="text-xs font-normal text-gray-400">固定班次按周几自动排入当日名单</span></p>
            <div className="flex items-center gap-2 flex-wrap">
                <button onClick={()=>openIcsPreview('schedule')} disabled={icsBusy || schedules.length===0}
                    title={schedules.length ? '导出所有固定班次，不包含学员姓名' : '请先新增固定班次'}
                    className="inline-flex items-center gap-1.5 border border-indigo-200 bg-indigo-50 text-indigo-700 px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px] active:bg-indigo-100 disabled:opacity-50">
                    <Icon name="download" className="w-3.5 h-3.5"/>固定课表 ICS
                </button>
                {/* B: schedule templates hit owner/manager-only endpoints — hide from teacher/staff */}
                {canManageOperations && <button onClick={()=>setSchedEdit({label:'', weekday:new Date().getDay(), startTime:defaultClassTime, durationMinutes:60, capacity:10, studentIds:[], courseId:'', teacherUserId:'', isPublic:false, room:''})}
                    className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="plus" className="w-3.5 h-3.5"/>新增班次</button>}
            </div>
        </div>
        {schedules.length===0 && !schedEdit && (
            <p className="text-xs text-gray-400">还没有固定班次。例如「周三 16:00 素描班」——保存后每周三会自动出现在当日排课里。</p>
        )}
        {schedules.length>0 && (
            <div className="flex flex-wrap gap-2">
                {schedules.map(sc => (
                    <div key={sc.id} className={`border rounded-xl px-3 py-2 ${sc.weekday===new Date(`${rDate}T12:00:00`).getDay()?'border-indigo-300 bg-indigo-50':'border-gray-200 bg-gray-50'}`}>
                        <p className="text-sm font-bold text-gray-800">{WEEKDAYS[sc.weekday]} {sc.startTime} · {sc.label||'未命名班次'}</p>
                        <p className="text-[11px] text-gray-500 mt-0.5">
                            {sc.students.length}/{sc.capacity} 人 · {sc.durationMinutes} 分钟
                            {sc.teacherName && <> · {sc.teacherName} 老师</>}
                            {sc.room && <> · {sc.room}</>}
                        </p>
                        {/* v8.8.0: 公开状态是一句话，不是一个只有开发者看得懂的图标。
                            没有这一行，Owner 只能靠打开编辑器逐个班次确认哪些已经
                            对外可见 —— 而这正是最不该靠回忆的一件事。 */}
                        <p className="text-[11px] mt-0.5">
                            {sc.isPublic
                                ? <span className="text-green-700">● 已公开{sc.teacherUserId && !sc.teacherIsPublic ? '（不显示老师姓名）' : ''}</span>
                                : <span className="text-gray-400">○ 仅内部可见</span>}
                        </p>
                        {(sc.cancellations||[]).length>0 && (
                            <div className="mt-1 space-y-0.5">
                                {sc.cancellations.map(c=>(
                                    <p key={c.date} className="text-[11px] text-amber-700">
                                        {c.date} 停课{c.note?` · ${c.note}`:''}
                                        {canManageOperations && <button onClick={()=>restoreCancellation(sc, c.date)} disabled={busy}
                                            className="ml-1.5 font-bold text-indigo-600 active:text-indigo-800">恢复</button>}
                                    </p>
                                ))}
                            </div>
                        )}
                        <div className="flex items-center gap-2 mt-1">
                            {canManageOperations && <>
                            <button onClick={()=>setSchedEdit({id:sc.id, label:sc.label, weekday:sc.weekday, startTime:sc.startTime, durationMinutes:sc.durationMinutes, capacity:sc.capacity, studentIds:sc.students.map(st=>st.id), courseId:sc.courseId||'', teacherUserId:sc.teacherUserId||'', isPublic:!!sc.isPublic, room:sc.room||''})}
                                className="text-[11px] font-bold text-indigo-600 active:text-indigo-800">编辑</button>
                            <button onClick={()=>setSchedCancel({id:sc.id, label:sc.label||'未命名班次', date:nextOccurrence(sc.weekday), note:''})}
                                className="text-[11px] font-bold text-amber-600 active:text-amber-800">停课</button>
                            <button onClick={()=>deleteSchedule(sc)} className="text-[11px] font-bold text-red-500 active:text-red-700">删除</button>
                            </>}
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
                {/* v8.8.0: 关联课程、授课老师、地点。前两项都是选填 ——
                    一个只在内部用的班次不需要这些，逼着填只会让人乱填。 */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-2">
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">关联课程<span className="font-normal text-gray-400">（选填）</span></label>
                        <select value={schedEdit.courseId||''} onChange={e=>setSchedEdit(p=>({...p,courseId:e.target.value}))}
                            className="w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500">
                            <option value="">不关联课程</option>
                            {courses.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
                        </select>
                        {/* 从「需要它的地方」通向「管理它的地方」。没有这一行，
                            一个空的下拉只会让人以为功能坏了，而不是还没建课程。 */}
                        <p className="text-[11px] text-gray-400 mt-1">
                            {courses.length
                                ? '关联后，课程简介和适龄段可用于公开课表；未关联时只用班次名称。'
                                : '还没有课程。'}
                            <button type="button" onClick={()=>{setTab('courses');setTimeout(()=>document.getElementById('courseManager')?.scrollIntoView({block:'center'}),80);}}
                                className="ml-1 font-bold text-indigo-600 active:text-indigo-800 underline">
                                {courses.length ? '管理课程' : '去添加课程 →'}
                            </button>
                        </p>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">授课老师<span className="font-normal text-gray-400">（选填）</span></label>
                        <select value={schedEdit.teacherUserId||''} onChange={e=>setSchedEdit(p=>({...p,teacherUserId:e.target.value}))}
                            className="w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500">
                            <option value="">未指定</option>
                            {teachableMembers.map(m=><option key={m.user_id} value={m.user_id}>{m.full_name}</option>)}
                        </select>
                        <p className="text-[11px] text-gray-400 mt-1">指定后，同一位老师同时段被排两处会提示冲突。</p>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">地点 / 教室<span className="font-normal text-gray-400">（选填）</span></label>
                        <input value={schedEdit.room||''} onChange={e=>setSchedEdit(p=>({...p,room:e.target.value}))} placeholder="如：A 教室"
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                    </div>
                </div>
                {/* 默认不公开。「已排的课」和「对外招生的课」不是同一批：
                    一对一时段、内部补课、给某个家庭留的试听位都在前者里。 */}
                <label className="flex items-start gap-2.5 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 min-h-[44px] cursor-pointer">
                    <input type="checkbox" checked={!!schedEdit.isPublic}
                        onChange={e=>setSchedEdit(p=>({...p,isPublic:e.target.checked}))}
                        className="mt-0.5 w-4 h-4 accent-indigo-600"/>
                    <span className="flex-1">
                        <span className="text-sm font-bold text-gray-700">在公开课表上展示这个班次</span>
                        <span className="block text-[11px] text-gray-400 mt-0.5">
                            默认不展示。一对一时段、内部补课、留给特定家庭的试听位不应该出现在公网上。
                            {schedEdit.teacherUserId && (() => {
                                const m = teachableMembers.find(x=>x.user_id===schedEdit.teacherUserId);
                                return m && !m.show_on_public_timetable
                                    ? <span className="block text-amber-600 mt-0.5">{m.full_name} 尚未同意在公开课表显示姓名，课表会照常展示但不带老师。可在「设置 · 团队与权限」里逐人开启。</span>
                                    : null;
                            })()}
                        </span>
                    </span>
                </label>
                <div>
                    <label className="text-xs font-bold text-gray-500 mb-1 block">班次学员（{schedEdit.studentIds.length} 人）</label>
                    <div className="flex flex-wrap gap-1.5 mb-2">
                        {schedEdit.studentIds.map(id => {
                            const s = db.students.find(x=>x.id===id);
                            return s ? (
                                <span key={id} className="inline-flex items-center gap-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full px-2.5 py-1 text-xs font-bold">
                                    {s.name}
                                    <button onClick={()=>setSchedEdit(p=>({...p,studentIds:p.studentIds.filter(x=>x!==id)}))} aria-label="移出" className="text-indigo-400 active:text-red-500 p-1 -m-1 inline-flex items-center justify-center"><Icon name="close" className="w-3 h-3"/></button>
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
        {/* v8.8.0 停课：固定课表说的是「每周三」，没有办法说「这个周三不上」。
            少了它，公开课表就是一个收不回的承诺 —— 某周停课，网站照旧写着
            16:00，家长白跑一趟。停课那天是划掉并注明原因，不是让它消失：
            消失看起来像网站坏了，标注停课看起来像有人在管。 */}
        {schedCancel && (
            <div className="border-t border-gray-100 pt-3 space-y-3">
                <p className="text-sm font-bold text-gray-800">标记停课 · {schedCancel.label}</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">停课日期</label>
                        <input type="date" value={schedCancel.date} onChange={e=>setSchedCancel(p=>({...p,date:e.target.value}))}
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                        <p className="text-[11px] text-gray-400 mt-1">必须落在这个班次上课的那一天，默认已填好下一次。</p>
                    </div>
                    <div>
                        <label className="text-xs font-bold text-gray-500 mb-1 block">原因<span className="font-normal text-gray-400">（选填，会显示给家长）</span></label>
                        <input value={schedCancel.note} onChange={e=>setSchedCancel(p=>({...p,note:e.target.value}))} placeholder="如：公众假期 / 老师培训"
                            className="w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"/>
                    </div>
                </div>
                <div className="flex gap-2 justify-end">
                    <button onClick={()=>setSchedCancel(null)} className="bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50">取消</button>
                    <button onClick={saveCancellation} disabled={busy}
                        className="bg-amber-600 active:bg-amber-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold">标记停课</button>
                </div>
            </div>
        )}
        </div>
    </details>
    )}

    <div className="cms-roster-planner bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
            <div className="w-full">
                <label className="text-xs font-bold text-gray-500 mb-1 block">课程日期</label>
                <div className="cms-roster-date-nav">
                    <button type="button" onClick={()=>setRDate(shiftDate(rDate,-1))}
                        aria-label="前一天" className="cms-roster-date-button"><Icon name="chevronLeft" className="w-4 h-4"/></button>
                    <button type="button" onClick={()=>setRDate(todayISO())}
                        aria-current={rDate===todayISO()?'date':undefined} className="cms-roster-today">今天</button>
                    <button type="button" onClick={()=>setRDate(shiftDate(rDate,1))}
                        aria-label="后一天" className="cms-roster-date-button"><Icon name="chevronRight" className="w-4 h-4"/></button>
                    <input type="date" value={rDate} onChange={e=>setRDate(e.target.value)}
                        aria-label="选择课程日期"
                        className="w-full px-3 py-3 min-h-[50px] border border-gray-300 rounded-xl font-bold text-gray-900 focus:ring-2 focus:ring-indigo-500 outline-none"/>
                </div>
            </div>

    {/* B1: 迷你周视图 — 本周七天一键切换，含每日应到人数 */}
    <div className="cms-roster-week" role="group" aria-label="本周课程日期">
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
                        aria-current={isSel?'date':undefined}
                        aria-label={`${WEEKDAYS[d.getDay()]} ${fmtDate(iso)}，${n} 人`}
                        className={`cms-roster-week-day ${isSel?'is-selected':''} ${isToday?'is-today':''}`}>
                        <p className="text-[10px] opacity-70">{WEEKDAYS[d.getDay()]}{isToday?'·今':''}</p>
                        <p className="text-sm font-bold">{d.getDate()}</p>
                        <p className="text-[10px] font-bold opacity-80">{n>0?n:'—'}</p>
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
            <div className="cms-roster-summary" aria-live="polite">
                <strong>{rDate===todayISO()?'今日':fmtDate(rDate)} · {valid.length} 人</strong>
                <span className="is-success">已签到 {done}</span>
                <span>待上课 {valid.length-done}</span>
                {low>0 && <span className="is-warning"><Icon name="warning" className="inline-block w-3.5 h-3.5 mr-1"/>低余额 {low}</span>}
            </div>
        );
    })()}

    {/* 0022: slots. Several people at the same time may be one class, or may be
        a one-to-one that was booked into an occupied hour — which the flat
        list could not show, so it surfaced when both families arrived. */}
    {(()=>{
        const ids = dayIds.filter(id=>{const st=db.students.find(x=>x.id===id);return st&&!st.archived;});
        if (!ids.length) return null;
        const slots = {};
        ids.forEach(id=>{
            const t = (rosterSlotFor(rDate,id) || '').trim() || '__unset';
            (slots[t] = slots[t] || []).push(id);
        });
        const groups = Object.entries(slots).sort(([a],[b]) =>
            a==='__unset' ? 1 : b==='__unset' ? -1 : a.localeCompare(b));
        const nameOf = id => db.students.find(x=>x.id===id)?.name || '';
        return (
            <div className="cms-roster-slot-panel">
                <p className="font-bold text-sm text-gray-800 mb-2 flex items-center gap-2">
                    <Icon name="clock" className="w-4 h-4"/>时段安排
                </p>
                <div className="space-y-1.5">
                {groups.map(([t,arr])=>{
                    const soloIds = arr.filter(id=>!!rosterMetaFor(rDate,id).oneToOne);
                    const clash = soloIds.length>0 && arr.length>1;
                    return (
                        <div key={t} className={`cms-roster-slot-row ${clash?'has-conflict':''}`}>
                            <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs">
                                <span className="font-bold text-gray-800 min-w-[56px]">{t==='__unset'?'时间未设置':t}</span>
                                <span className="px-2 py-0.5 rounded-full bg-white border border-gray-200 font-bold">{arr.length} 人</span>
                                <span className="text-gray-500">{arr.map(nameOf).filter(Boolean).join('、')}</span>
                            </div>
                            {soloIds.length>0 && (
                                <p className={`mt-1 text-xs font-bold ${clash?'text-red-700':'text-indigo-600'}`}>
                                    {clash
                                        ? `1 对 1 时间冲突：${soloIds.map(nameOf).join('、')} 与同时段其他排课重叠`
                                        : `1 对 1：${soloIds.map(nameOf).join('、')}`}
                                </p>
                            )}
                        </div>
                    );
                })}
                </div>
            </div>
        );
    })()}

    <div className="cms-roster-add border-t border-gray-100 pt-3" id="rosterAddStudent">
        <div className="cms-roster-add-fields">
            <div className="min-w-0">
                <label className="text-xs font-bold text-gray-500 mb-1 block">添加学员</label>
                <StudentPicker students={availRoster} value={rPick} onChange={setRPick} placeholder="搜索并选择学员..."/>
            </div>
            <div>
                <label className="text-xs font-bold text-gray-500 mb-1 block">上课时间</label>
                <input type="time" value={rTime} onChange={e=>setRTime(e.target.value)}
                    aria-label="上课时间"
                    className="w-full px-3 py-3 border border-gray-300 rounded-xl bg-white text-sm font-bold min-h-[50px] outline-none focus:ring-2 focus:ring-indigo-500"/>
            </div>
            <button onClick={addToRoster} disabled={!rPick||busy}
                className="cms-roster-add-button bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-xl font-bold text-sm min-h-[50px]">
                <Icon name="plus" className="w-4 h-4"/>{rPick?'加入课程安排':'请先选择学员'}
            </button>
        </div>
        <label className="inline-flex items-center gap-2 mt-2 text-xs font-bold text-gray-500 min-h-[44px]">
            <input type="checkbox" checked={rOneToOne} onChange={e=>setROneToOne(e.target.checked)} className="w-4 h-4"/>
            1 对 1（同时段还有其他人时会提示冲突）
        </label>
    </div>

    {/* F4b: Advanced batch tools stay available without permanently
        pushing the actual day roster below the fold. */}
    <details className="pt-3 border-t border-gray-100 group">
        <summary className="list-none cursor-pointer min-h-[44px] flex items-center justify-between gap-3 text-xs font-bold text-gray-600">
            <span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>班组模板与批量工具</span>
            <span className="text-indigo-600 group-open:rotate-180 transition-transform" aria-hidden="true">⌄</span>
        </summary>
        <div className="pt-2 flex gap-2 items-center flex-wrap">
        <select value={grpSel} onChange={e=>setGrpSel(e.target.value)}
            className="px-2 py-2 border border-gray-300 rounded-xl bg-white text-sm font-medium min-h-[44px] outline-none focus:ring-2 focus:ring-indigo-500">
            <option value="">-- 选择模板 --</option>
            {Object.keys(db.groups||{}).sort().map(g => <option key={g} value={g}>{g}（{(db.groups[g]||[]).length}人）</option>)}
        </select>
        <button onClick={applyGroup} disabled={!grpSel||busy}
            className="bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]">套用到当前日期</button>
        {/* B: template management stays owner/manager; applying a template to a day is a per-day attendance action */}
        {canManageOperations && <button onClick={saveGroup} disabled={busy}
            className="bg-white text-gray-600 border border-gray-300 active:bg-gray-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]">保存当前为模板</button>}
        {canManageOperations && grpSel && <button onClick={deleteGroup} disabled={busy}
            className="bg-white text-red-500 border border-red-200 active:bg-red-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]">删除</button>}
        {canManageOperations && TENANT_SLUG && grpSel && <button onClick={groupToSchedule} disabled={busy}
            className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="calendar" className="w-4 h-4"/>转为每周班次</button>}
        </div>
    </details>
    </div>

    <div className="bg-white rounded-2xl shadow-sm border border-gray-100">
        <div className="bg-gray-50 border-b px-4 py-3 flex justify-between items-center gap-2 flex-wrap">
            <p className="font-bold text-sm text-gray-800">{fmtDate(rDate)} · {dayIds.filter(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived;}).length} 人{scheduledForDate.length>0 && <span className="text-xs font-normal text-indigo-500 ml-1">（课表 {scheduledForDate.length} 班）</span>}</p>
            {dayIds.length>0 && <details className="cms-day-actions-mobile">
                <summary><Icon name="ellipsis" className="w-4 h-4"/>当日操作</summary>
                <div className="cms-roster-menu">
                    {canExportData && <button onClick={()=>openIcsPreview('roster')} disabled={icsBusy}><Icon name="calendar" className="w-4 h-4"/>导出当日 ICS</button>}
                    <button onClick={copyRosterDaily}><Icon name="clipboard" className="w-4 h-4"/>复制日报</button>
                    {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.mobile;}) && <button onClick={copyRosterReminders}><Icon name="chat" className="w-4 h-4"/>批量提醒</button>}
                    {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.balance>0;}) && <button onClick={batchCheckIn} disabled={busy}><Icon name="check" className="w-4 h-4"/>批量签到并扣课时</button>}
                </div>
            </details>}
            <div className="cms-day-actions-desktop flex gap-2 flex-wrap">
                {dayIds.length>0 && canExportData && (
                    <button onClick={()=>openIcsPreview('roster')} disabled={icsBusy}
                        className="border border-gray-200 bg-white text-gray-700 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px] inline-flex items-center gap-1.5 disabled:opacity-50">
                        <Icon name="calendar" className="w-4 h-4"/>导出当日 ICS
                    </button>
                )}
                {dayIds.length>0 && (
                    <button onClick={copyRosterDaily} className="bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>日报</span></button>
                )}
                {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.mobile;}) && (
                    <button onClick={copyRosterReminders} className="bg-white border border-green-300 active:bg-green-50 text-green-700 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="chat" className="w-4 h-4"/>批量提醒</span></button>
                )}
                {dayIds.some(id=>{const s=db.students.find(x=>x.id===id);return s&&!s.archived&&s.balance>0;}) && (
                    <button onClick={batchCheckIn} disabled={busy}
                        className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="bolt" className="w-4 h-4"/>批量签到并扣课时</button>
                )}
            </div>
        </div>
        <div className="cms-roster-list divide-y divide-gray-100">
            {!dayIds.length && <EmptyState icon={<Icon name="calendar" className="w-8 h-8"/>} main="今天还没有排课"
                sub={TENANT_SLUG?'可以在上方「每周课表」建一个固定班次，之后每到这一天会自动排入；也可以直接在下方添加学员。':'在下方添加学员即可开始今天的排课。'}
                action="添加学员" onAction={()=>{const el=document.getElementById('rosterAddStudent'); if(el) el.scrollIntoView({behavior:'smooth',block:'center'});}}/>}
            {/* Fix #3: skip archived students in roster */}
            {dayIds.map(sid => {
                const s = db.students.find(x=>x.id===sid);
                if (!s || s.archived) return null;
                const entry = rosterMetaFor(rDate,sid);
                const isDone = rosterDone.has(s.id);
                const lowBal = (parseInt(s.balance,10)||0) <= renewTh && !isDone;   /* A5: 课前低余额预警（v4.5） */
                const slot = rosterSlotFor(rDate,sid);
                const rosterStatus = isDone ? '已签到' : entry.status==='makeup' ? '补课' : '待上课';
                return (
                    <div key={sid} className={`cms-roster-row hover-row ${lowBal?'is-low':''}`}>
                        <div className="cms-roster-info">
                            <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                            <div className="flex-1 min-w-0">
                                <div className="flex items-center gap-2 min-w-0 flex-wrap">
                                    <p className="font-bold text-gray-900 truncate">{s.name}</p>
                                    {entry.oneToOne && <span className="text-[11px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full px-2 py-0.5">1 对 1</span>}
                                    <span className={`text-[11px] font-bold rounded-full px-2 py-0.5 border ${isDone?'bg-green-50 border-green-200 text-green-700':entry.status==='makeup'?'bg-blue-50 border-blue-200 text-blue-700':'bg-gray-50 border-gray-200 text-gray-600'}`}>{rosterStatus}</span>
                                </div>
                                <p className="text-xs text-gray-400 truncate">{[s.mobile||'未填写手机', slot, entry.note].filter(Boolean).join(' · ')}</p>
                            </div>
                            <BalBadge n={s.balance}/>
                        </div>
                        {/* Correcting the slot in place: re-adding the student would
                            reset their source and status. Only in tenant mode —
                            the legacy JSON store has no entry id to patch. */}
                        <div className={`cms-roster-actions ${lowBal?'has-reminder':''}`}>
                        {TENANT_SLUG && entry.id && (
                            <input type="time" defaultValue={entry.classTime||''}
                                aria-label={`${s.name} 的上课时间`}
                                onChange={e=>{
                                    const entryId = entry.id;
                                    updateRosterEntry(entryId, {classTime: e.target.value || ''})
                                        .then(()=>showToast(e.target.value?`${s.name} 上课时间改为 ${e.target.value}`:`${s.name} 已清除上课时间`))
                                        .catch(err=>showToast(err.message||'时间未能保存', 'error'));
                                }}
                                className="cms-roster-time px-2 py-2 border border-gray-300 rounded-xl bg-white text-xs font-bold min-h-[44px] outline-none focus:ring-2 focus:ring-indigo-500"/>
                        )}
                        {TENANT_SLUG && !entry.id && (
                            <span className="cms-roster-time px-3 py-2 border border-gray-200 rounded-xl bg-gray-50 text-xs font-bold text-gray-700 min-h-[44px] inline-flex items-center">
                                {slot || '未设时间'}
                            </span>
                        )}
                        {lowBal && (
                            <button onClick={()=>{
                                const msg = renderMessage('renewal',
                                    '{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。',
                                    {student:s.name, balance:s.balance, note:(parseInt(s.balance,10)||0)===0?'（已用完）':''});
                                copyText(msg, `已复制给 ${s.name} 的催费提醒`);
                            }} className="cms-roster-reminder"><Icon name="chat" className="w-4 h-4"/>续费提醒</button>
                        )}
                        {isDone
                            ? <button disabled className="cms-roster-primary is-done"><Icon name="check" className="w-4 h-4"/>已签到</button>
                            : <button onClick={()=>checkIn(s.id,s.name)} disabled={busy||s.balance<=0}
                                aria-label={`为 ${s.name} 签到并扣 1 课时`} className="cms-roster-primary"><Icon name="check" className="w-4 h-4"/>{s.balance>0?'签到并扣 1 课时':'余额不足'}</button>}
                        <details className="cms-roster-more" name="roster-student-actions">
                            <summary aria-label={`${s.name} 更多操作`}><Icon name="ellipsis" className="w-5 h-5"/></summary>
                            <div className="cms-roster-menu">
                                <div className="cms-roster-menu__context">
                                    <strong>{s.name}</strong>
                                    <span>{fmtDate(rDate)} · {slot || '时间未设置'} · 余额 {s.balance}</span>
                                </div>
                                {entry.id && <>
                                    <p className="cms-roster-menu__label">课程状态</p>
                                    <button onClick={e=>{updateRosterEntry(entry.id,{status:'scheduled'}).then(()=>showToast(`${s.name} 已标记为待上课`)).catch(err=>showToast(err.message||'课程状态未能保存','error'));e.currentTarget.closest('details')?.removeAttribute('open');}} disabled={busy||entry.status!=='makeup'} aria-current={entry.status!=='makeup'?'true':undefined}><Icon name="check" className="w-4 h-4"/>待上课</button>
                                    <button onClick={e=>{updateRosterEntry(entry.id,{status:'makeup'}).then(()=>showToast(`${s.name} 已标记为补课`)).catch(err=>showToast(err.message||'课程状态未能保存','error'));e.currentTarget.closest('details')?.removeAttribute('open');}} disabled={busy||entry.status==='makeup'} aria-current={entry.status==='makeup'?'true':undefined}><Icon name="refresh" className="w-4 h-4"/>补课</button>
                                    <div className="cms-roster-menu__separator"/>
                                </>}
                                {s.mobile && <a href={`sms:${s.mobile.replace(/\s/g,'')}?body=${encodeURIComponent(`提醒：您的上课时间是 ${fmtDate(rDate)}${slot?` ${slot}`:''}，请准时到课。${tenantDisplayName} 期待见到您！`)}`}><Icon name="chat" className="w-4 h-4"/>发短信提醒</a>}
                                {entry.id && <button onClick={e=>{updateRosterEntry(entry.id,{oneToOne:!entry.oneToOne}).then(()=>showToast(entry.oneToOne?'已改为普通班课':'已标记为 1 对 1')).catch(err=>showToast(err.message||'排课类型未能保存','error'));e.currentTarget.closest('details')?.removeAttribute('open');}} disabled={busy}><Icon name="users" className="w-4 h-4"/>{entry.oneToOne?'改为普通班课':'标记为 1 对 1'}</button>}
                                {isDone && <button onClick={e=>{undoCheckIn(s.id,s.name);e.currentTarget.closest('details')?.removeAttribute('open');}} disabled={busy}><Icon name="refresh" className="w-4 h-4"/>撤销本日签到</button>}
                                {entry.id
                                    ? <button onClick={e=>{removeFromRoster(s.id);e.currentTarget.closest('details')?.removeAttribute('open');}} disabled={busy} className="is-danger"><Icon name="trash" className="w-4 h-4"/>移出本日课程安排</button>
                                    : <p className="cms-roster-menu__source"><Icon name="calendar" className="w-4 h-4"/>来自固定课表，需在上方班次中调整</p>}
                            </div>
                        </details>
                        </div>
                    </div>
                );
            })}
        </div>
    </div>
</div>
)}

{/* ═══ STUDENTS ════════════════════════════════════════════════ */}
{/* ═══ WORKS ══════════════════════════════════════════════════ */}
{tab==='works' && (
<div className="anim space-y-5 max-w-6xl mx-auto">
    <div className="flex items-start justify-between gap-3 flex-wrap">
        <div><h2 className="md:hidden inline-flex items-center gap-2 text-xl font-bold text-gray-800"><Icon name="image" className="w-5 h-5"/>作品管理</h2><p className="text-sm text-gray-500 mt-1">从这里按学员浏览作品；具体上传、编辑和公开授权仍在学员档案中完成。</p></div>
        <button type="button" onClick={()=>setTab('students')} className="min-h-[44px] px-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-bold">进入学员档案 →</button>
    </div>
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[['作品总数',portfolioEntries.length,'text-gray-900'],['已公开',portfolioEntries.filter(({item})=>item.public||item.visibility==='shared').length,'text-emerald-700'],['待授权',portfolioEntries.filter(({student})=>student.publicationConsent?.status!=='confirmed').length,'text-amber-700'],['有作品学员',new Set(portfolioEntries.map(({student})=>student.id)).size,'text-indigo-700']].map(([label,value,color])=><div key={label} className="bg-white rounded-2xl border border-gray-100 shadow-sm p-4"><p className="text-xs text-gray-400">{label}</p><p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p></div>)}
    </div>
    <section className="bg-white rounded-2xl shadow-sm border border-gray-100 p-5" aria-labelledby="works-list-title">
        <div className="flex items-center justify-between gap-3 mb-3"><div><h3 id="works-list-title" className="font-bold text-gray-900">最近作品</h3><p className="text-xs text-gray-400 mt-0.5">按作品日期倒序 · 最多显示最近 50 条</p></div><span className="text-xs font-bold text-gray-500">{portfolioEntries.length} 条</span></div>
        {!portfolioEntries.length ? <EmptyState icon={<Icon name="image" className="w-8 h-8"/>} main="还没有作品" sub="打开学员档案后，在作品区上传第一件作品。" action="查看学员" onAction={()=>setTab('students')}/> : <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">{portfolioEntries.slice(0,50).map(({student,item})=>{
            const shared = item.public || item.visibility === 'shared';
            return <article key={`${student.id}-${item.id||item.filename||item.date}`} className="overflow-hidden rounded-2xl border border-gray-200 bg-gray-50">
                <button type="button" onClick={()=>{setTab('students',{recordId:student.id});setSelS(student);setEditP(false);setTimeout(()=>setStudentProfileTab('portfolio'),0);}} className="block w-full text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500">
                    <div className="aspect-[4/3] bg-gray-100 overflow-hidden">{item.filename ? <img src={portfolioThumbSrc(student.id,item)} loading="lazy" alt={`${student.name} 的作品`} className="w-full h-full object-cover"/> : <div className="w-full h-full inline-flex items-center justify-center text-gray-300"><Icon name="image" className="w-10 h-10"/></div>}</div>
                    <div className="p-3"><div className="flex items-center justify-between gap-2"><p className="font-bold text-gray-900 truncate">{item.title||item.note||'未命名作品'}</p><span className={`flex-shrink-0 text-[11px] font-bold px-2 py-0.5 rounded-full border ${shared?'bg-emerald-50 border-emerald-200 text-emerald-700':'bg-gray-100 border-gray-200 text-gray-500'}`}>{shared?'已公开':'未公开'}</span></div><p className="text-xs text-gray-500 mt-1 truncate">{student.name} · {fmtDate(item.date)}</p>{item.note && item.title && <p className="text-xs text-gray-400 mt-1 line-clamp-2">{item.note}</p>}</div>
                </button>
                {canWritePortfolio && <div className="px-3 pb-3"><button type="button" onClick={()=>{setTab('students',{recordId:student.id});setSelS(student);setEditP(false);setTimeout(()=>{setStudentProfileTab('portfolio');setPortUpload(true);},0);}} className="w-full min-h-[44px] rounded-xl border border-indigo-200 bg-white text-xs font-bold text-indigo-700 hover:bg-indigo-50">在该学员下继续上传</button></div>}
            </article>;
        })}</div>}
    </section>
</div>
)}

{/* ═══ STUDENTS ════════════════════════════════════════════════ */}
{tab==='students' && (
<div className="anim space-y-4">
    <div className="flex justify-between items-center gap-3 flex-wrap">
        <h2 className="md:hidden text-xl font-bold text-gray-800">{`学员档案 (${sortedFiltered.length})`}</h2>
        <p className="hidden md:block text-sm font-bold text-gray-500">{`共 ${sortedFiltered.length} 人`}</p>
        <div className="flex gap-2">
            {canManageOperations && <button onClick={exportStudentsCSV}
                className="inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-4 py-2.5 rounded-xl font-bold text-sm min-h-[44px]"><Icon name="download" className="w-4 h-4"/>CSV</button>
            }
            {canWriteStudents && <button onClick={()=>setTab('new_student')}
                className="inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md min-h-[44px]"><Icon name="plus" className="w-4 h-4"/>新建</button>
            }
        </div>
    </div>

    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <div className="relative">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"><Icon name="search"/></span>
            <input type="text" placeholder="搜索姓名 / 电话 / 微信 / 邮箱…（回车打开唯一匹配）" value={srch} onChange={e=>setSrch(e.target.value)}
                onKeyDown={e=>{ if (e.key==='Enter' && sortedFiltered.length===1) { setSelS(sortedFiltered[0]); setEditP(false); } }}
                aria-label="搜索学员"
                className="w-full pl-10 pr-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
        </div>
        <div className="overflow-x-auto -mx-1 px-1 pb-1"><div className="flex gap-2 items-center" style={{minWidth:'max-content'}}>
            <select value={sortBy} onChange={e=>setSortBy(e.target.value)}
                className="px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none font-medium text-sm min-h-[44px] flex-shrink-0">
                <option value="name-az">名 A→Z</option>
                <option value="name-za">名 Z→A</option>
                <option value="last-az">姓 A→Z</option>
                <option value="last-za">姓 Z→A</option>
                <option value="bal-desc">课时 高→低</option>
                <option value="bal-asc">课时 低→高</option>
                <option value="date-desc">最近活跃</option>
            </select>
            {[['all','全部'],['active','有余额'],['low',`低余额≤${renewTh}`],['zero','已清零'],['archived','归档库'],['tag-hot','活跃'],['tag-low','低频'],['tag-risk','流失风险'],['portal-ready','专区已就绪'],['portal-missing-mobile','缺手机号'],['portal-disabled','专区未启用'],['portal-content-blocked','私人内容受阻'],['publication-live','作品已公开'],['publication-ready','公开授权有效'],['publication-missing-consent','缺公开授权']].map(([v,l]) => (
                <button key={v} onClick={()=>setFilterBy(v)}
                    className={`px-4 py-2 rounded-xl text-xs font-bold border min-h-[44px] transition flex-shrink-0 ${filterBy===v?'bg-indigo-600 text-white border-indigo-600':'bg-white text-gray-600 border-gray-300 active:border-indigo-300'}`}>{l}{filterBy===v?` · ${sortedFiltered.length}`:''}</button>
            ))}
            {(filterBy!=='all'||srch) && <button onClick={()=>{setFilterBy('all');setSrch('');}}
                className="inline-flex items-center gap-1 px-3 py-2 rounded-xl text-xs font-bold border border-red-200 text-red-500 bg-white active:bg-red-50 min-h-[44px] flex-shrink-0"><Icon name="close" className="w-3.5 h-3.5"/>清除</button>}
        </div></div>
    </div>

    {/* P2-14: multi-select toolbar. Bulk archive and bulk reminders used to be
        reachable only through the low-balance filter's single "copy all" button. */}
    {selectedStudents.length > 0 && (
        <div className="bg-indigo-50 border border-indigo-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
            <p className="text-sm font-bold text-indigo-700">{`已选择 ${selectedStudents.length} 人`}</p>
            <div className="flex gap-2 flex-wrap">
                <button onClick={()=>setSelectedStudentIds([])}
                    className="bg-white border border-indigo-200 text-indigo-700 px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]">清除选择</button>
                <button onClick={copySelectedReminders}
                    className="bg-indigo-600 active:bg-indigo-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]">复制续课提醒</button>
                {canManageOperations && (
                    <button onClick={archiveSelected} disabled={busy}
                        className="bg-gray-700 active:bg-gray-800 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px] disabled:bg-gray-300">批量归档</button>
                )}
            </div>
        </div>
    )}
    {/* F5: 待续课看板 — 低余额筛选下提供一键复制提醒话术 */}
    {canWriteCredits && filterBy==='low' && sortedFiltered.length>0 && (
        <div className="bg-orange-50 border border-orange-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap">
            <p className="inline-flex items-center gap-1.5 text-sm font-bold text-orange-700"><Icon name="bolt" className="w-4 h-4"/>待续课学员 {sortedFiltered.length} 人（余额 ≤{renewTh} 节）</p>
            <button onClick={()=>{
                const lines = sortedFiltered.map(s => renderMessage('renewal',
                    '{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。',
                    {student:s.name, balance:s.balance, note:''}));
                copyText(lines.join('\n\n'), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
            }} className="bg-orange-600 active:bg-orange-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="clipboard" className="w-4 h-4"/>复制全部提醒话术</span></button>
        </div>
    )}
    {!sortedFiltered.length && <EmptyState icon={<Icon name="search" className="w-8 h-8"/>} main="没有符合条件的学员"
            sub={srch ? `没有姓名、电话、微信或邮箱包含「${srch}」的学员。换个关键词，或清空搜索看全部。` : '当前筛选条件下没有学员。点下方按钮回到全部名单。'}
            action={srch ? '清空搜索' : '查看全部学员'} onAction={()=>{setSrch('');setFilterBy('all');}}/>}
    {sortedFiltered.length > 0 && (
        <label className="flex items-center gap-2 text-xs font-bold text-gray-500 px-1">
            <input type="checkbox" className="w-4 h-4"
                checked={pageStudents.length>0 && pageStudents.every(item=>selectedStudentIds.includes(item.id))}
                onChange={e=>toggleSelectPage(e.target.checked)}/>
            {`选择本页 ${pageStudents.length} 人`}
        </label>
    )}
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {pageStudents.map(s => (
            <div key={s.id} className={`bg-white rounded-2xl p-4 shadow-sm border hover-row transition flex flex-col justify-between print-card ${selectedStudentIds.includes(s.id)?'ring-2 ring-indigo-400 border-indigo-200':s.archived?'border-gray-200 opacity-70':parseInt(s.balance,10)===0?'border-red-100':parseInt(s.balance,10)<=2?'border-orange-100':'border-gray-100'}`}>
                <div>
                    <div className="flex justify-between items-start mb-2 gap-2">
                        <div className="flex items-center gap-2.5 min-w-0">
                            <input type="checkbox" className="w-4 h-4 flex-shrink-0" aria-label={`选择 ${s.name}`}
                                checked={selectedStudentIds.includes(s.id)}
                                onChange={()=>toggleSelectStudent(s.id)}/>
                            <PhotoAvatar photo={s.photo} name={s.name} size="sm"/>
                            <div className="min-w-0">
                                <h3 className="font-bold text-gray-800 break-words leading-snug">{s.name}</h3>
                                {s.archived && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 rounded mt-0.5 inline-block">归档</span>}
                            </div>
                        </div>
                        <div className="flex flex-col items-end gap-1 flex-shrink-0">
                            <BalBadge n={s.balance}/>
                            {(()=>{const t=getTag(s); return t?<span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-bold ${t.cls}`}><Icon name={t.icon} className="w-3 h-3"/>{t.label}</span>:null;})()}
                        </div>
                    </div>
                    <p className="text-gray-400 text-sm flex items-center gap-1.5"><Icon name="phone" className="w-4 h-4"/> {s.mobile||'—'}</p>
                    {s.email && <p className="text-gray-400 text-sm flex items-center gap-1.5"><Icon name="mail" className="w-4 h-4"/> {s.email}</p>}
                    {preferenceRows(s).slice(0, 1).map(row => (
                        <p key={row.key} className="text-gray-400 text-sm">{row.label}：{row.value}</p>
                    ))}
                    <p className="text-gray-400 text-sm mt-0.5 flex items-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/> {fmtDate(s.lastActive)}{daysSince(s.lastActive)<9999?` · ${daysSince(s.lastActive)}天前`:''}</p>
                </div>
                <div className="flex gap-2 mt-3">
                    <button onClick={()=>{setSelS(s);setEditP(false);}}
                        className="flex-1 bg-gray-50 active:bg-gray-100 border border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-bold min-h-[44px]">详情</button>
                    {!s.archived && (<>
                        {canWriteCredits && <button onClick={()=>{setTuStu(s.id);setTab('topup');}}
                            title="快速充值" aria-label="快速充值" className="px-3.5 py-3 rounded-xl font-bold bg-emerald-50 active:bg-emerald-100 text-emerald-700 border border-emerald-200 min-h-[44px] flex items-center justify-center"><Icon name="money"/></button>
                        }
                        {canWriteAttendance && <button onClick={()=>scheduleStudentToday(s)} disabled={busy}
                            className="flex-1 py-3 rounded-xl text-sm font-bold text-white min-h-[44px] bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 inline-flex items-center justify-center gap-1.5">{/* Same wording as the profile sheet's primary action: the label says
    what the tap does, not where it goes. It used to read 去排课 when the
    student was ALREADY on today's roster and 排课 when they were not,
    which is the opposite of how both read. */}
<Icon name="calendar" className="w-4 h-4"/>{isStudentScheduledOn(s.id,todayISO())?'查看排课':'加入排课'}</button>
                        }
                    </>)}
                </div>
            </div>
        ))}
    </div>
    {studentPageCount > 1 && (
        <div className="flex items-center justify-center gap-3 pt-2">
            <button onClick={()=>setStudentPage(p=>Math.max(1,p-1))} disabled={studentPage<=1}
                className="px-4 py-2 rounded-xl text-sm font-bold border border-gray-300 bg-white disabled:opacity-40 min-h-[44px]">上一页</button>
            <span className="text-sm text-gray-500 font-bold">{`第 ${studentPage} / ${studentPageCount} 页`}</span>
            <button onClick={()=>setStudentPage(p=>Math.min(studentPageCount,p+1))} disabled={studentPage>=studentPageCount}
                className="px-4 py-2 rounded-xl text-sm font-bold border border-gray-300 bg-white disabled:opacity-40 min-h-[44px]">下一页</button>
        </div>
    )}
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
    <h2 className="md:hidden inline-flex items-center gap-2 text-xl font-bold mb-5 text-gray-800"><Icon name="plus" className="w-5 h-5"/>新建学员档案</h2>
    <form onSubmit={handleAddStudent} className="space-y-4">
        {/* Photo */}
        <div>
            <label className="text-sm font-bold text-gray-500 mb-2 block">照片 Photo <span className="font-normal text-gray-400">选填</span></label>
            <PhotoUploader value={formPhoto} onChange={setFormPhoto} notify={notify}/>
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
        <div className="grid grid-cols-2 gap-3">
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">生日 <span className="font-normal text-gray-400">选填</span></label>
                <input type="date" name="birthday" min="1920-01-01" max="2099-12-31"
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
            <div>
                <label className="text-sm font-bold text-gray-500 mb-1 block">入学日期</label>
                <input type="date" name="enrollmentDate" defaultValue={todayISO()} min="1900-01-01" max={todayISO()}
                    className="w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
            </div>
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
    <div className="flex items-start justify-between gap-3 flex-wrap"><div><h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="clipboard" className="w-4 h-4"/>待处理</h2><p className="text-sm text-gray-500 mt-1">新报名和约课申请共用一个收件箱，按业务类型分开处理。</p></div><span className="rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-bold text-amber-700">{pendingCount} 项等待处理</span></div>
    {/* v8.10.0: 一个收件箱，两个标签。计数分开写，是因为两者含义不同 ——
        「新报名」批准后建学员，「约课」批准后占座位，把后者算进前者会让
        「本月新报名」永远虚高，而那正是工作室用来判断投放效果的数字。
        但前台不该有两个地方要看，所以它们在同一页。 */}
    <div className="flex gap-2 flex-wrap">
        {[['registrations','新报名',(db.pending||[]).length],
          ['bookings','约课',bookings.length],
          ['reports','成长报告','']].map(([key,label,count])=>(
            <button key={key} onClick={()=>setPendingTab(key)}
                className={`px-4 py-2 rounded-xl text-sm font-bold min-h-[44px] border ${pendingTab===key?'bg-indigo-600 text-white border-indigo-600':'bg-white text-gray-600 border-gray-200 active:bg-gray-50'}`}>
                {label} {count}
            </button>
        ))}
    </div>
    {pendingTab==='reports' && (
        <OverdueReports api={v1Api} showToast={showToast}
            onOpenStudent={(id)=>setTab('students', {recordId: id})} />
    )}

    {pendingTab==='bookings' && (
    <div className="space-y-3">
        {!bookings.length && (
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
                <p className="font-bold text-gray-600">没有待处理的约课申请</p>
                <p className="text-sm text-gray-400 mt-1 max-w-sm mx-auto leading-relaxed">
                    在 Studio Admin 的「Timetable」里打开公开课表并允许约课后，家长可以在课表页留下姓名和手机号申请上课，申请会出现在这里。
                </p>
            </div>
        )}
        {bookings.map(bk => (
            <div key={bk.id} className="bg-white rounded-2xl shadow-sm border border-amber-200 p-4 space-y-3">
                <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="min-w-0">
                        <p className="text-base font-bold text-gray-800">{bk.contactName}
                            {/* 是否命中老学员只在这里显示。公开表单的回应无论
                                命中与否都完全一致 —— 否则那个表单就成了「这个
                                号码是不是你们的学员」的查询接口。 */}
                            {bk.isExistingStudent
                                ? <span className="ml-2 align-middle inline-block text-[10px] font-bold bg-green-100 text-green-700 border border-green-300 rounded-full px-2 py-0.5">已是学员{bk.matchedStudent?` · ${bk.matchedStudent}`:''}</span>
                                : <span className="ml-2 align-middle inline-block text-[10px] font-bold bg-gray-100 text-gray-600 border border-gray-300 rounded-full px-2 py-0.5">新访客</span>}
                        </p>
                        <p className="inline-flex items-center gap-1.5 text-sm text-gray-500"><Icon name="phone" className="w-4 h-4"/>{bk.contactPhone}</p>
                        <p className="text-sm text-gray-600 mt-1">{bk.date} {bk.startTime} · {bk.title||'未命名班次'}</p>
                        {bk.message && <p className="text-sm text-gray-500 mt-1 whitespace-pre-wrap">{bk.message}</p>}
                    </div>
                    <div className="text-right flex-shrink-0">
                        {/* 容量在「批准」那一刻才是真的，所以这里显示的是现在
                            的余位，而不是提交时的。 */}
                        <p className={`text-xs font-bold ${bk.seatsLeft===0?'text-gray-500':'text-green-700'}`}>
                            {bk.seatsLeft===0?'已满':`还有 ${bk.seatsLeft} 位`}
                        </p>
                        <p className="text-[11px] text-gray-400">容量 {bk.capacity}</p>
                    </div>
                </div>
                {bk.seatsLeft===0 && (
                    <p className="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2">
                        这节课已经满了。批准会被拒绝——先提高班次容量，或婉拒并联系家长改约。
                    </p>
                )}
{canReviewBookings && <div className="flex gap-2 justify-end">
                    <button onClick={()=>reviewBooking(bk,'declined')} disabled={busy}
                        className="bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50 min-h-[44px]">婉拒</button>
                    <button onClick={()=>reviewBooking(bk,'approved')} disabled={busy}
                        className="bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold min-h-[44px]">
                        {bk.isExistingStudent?'批准并排课':'批准并转报名'}
                    </button>
                </div>}
            </div>
        ))}
    </div>
    )}
    {pendingTab==='registrations' && <>
    {!(db.pending||[]).length && (
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center">
            <p className="inline-flex items-center gap-1.5 text-4xl mb-3"><Icon name="check" className="w-4 h-4"/></p>
            <p className="font-bold text-gray-600">没有待审核的报名</p>
            <p className="text-sm text-gray-400 mt-1 max-w-sm mx-auto leading-relaxed">家长在官网或报名页提交后，申请会出现在这里等你批准。把报名页链接发出去就能开始收。</p>
        </div>
    )}
    {(db.pending||[]).map(pen => {
        const fullName = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
        const normP = p => (p||'').replace(/[\s\-\(\)]+/g,'');
        /* 走查发现：同一手机号的重复待审申请（如同一家长提交两次）在列表里
           看不出来。纯前端提示——两张卡都挂琥珀色「疑似重复」角标。 */
        const penMobile = normP(pen.mobile);
        const isDupPending = !!penMobile && (db.pending||[]).some(o => o.id!==pen.id && normP(o.mobile)===penMobile);
        return (
            <div key={pen.id} className="bg-white rounded-2xl shadow-sm border border-amber-200 p-5 space-y-4">
                <div className="flex items-start gap-4">
                    {pen.photo
                        ? <img src={mediaSrc(pen.photo)} className="w-16 h-16 rounded-full object-cover flex-shrink-0 border-2 border-indigo-100" alt={fullName}/>
                        : <div className="w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-2xl font-bold text-indigo-600 flex-shrink-0">{(pen.firstName||'?')[0].toUpperCase()}</div>
                    }
                    <div className="flex-1 min-w-0">
                        <p className="text-lg font-bold text-gray-800">{fullName}
                            {isDupPending && <span className="ml-2 align-middle inline-block text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-300 rounded-full px-2 py-0.5" title="另有一条待审核申请使用相同手机号">疑似重复</span>}
                        </p>
                        <p className="inline-flex items-center gap-1.5 text-sm text-gray-500"><Icon name="phone" className="w-4 h-4"/>{pen.mobile||'—'}{pen.wechat ? ` · ${pen.wechat}` : ''}{pen.email ? ` · ${pen.email}` : ''}</p>
                        {pen.birthday && <p className="inline-flex items-center gap-1.5 text-xs text-pink-500 mt-0.5"><Icon name="cake" className="w-4 h-4"/>{fmtDate(pen.birthday)}</p>}
                        {pen.mobile && (() => {
                            const match = db.students.filter(s=>!s.archived && normP(s.mobile)===normP(pen.mobile));
                            return match.length > 0 ? <p className="inline-flex items-center gap-1.5 text-xs text-blue-500 mt-0.5"><Icon name="device" className="w-4 h-4"/>此电话已有学员：{match.map(s=>s.firstName&&s.lastName?`${s.firstName} ${s.lastName}`:s.name||'').join('、')}</p> : null;
                        })()}
                        <p className="text-xs text-gray-400 mt-0.5">提交时间: <span title={pen.submittedAt||''}>{fmtDT(pen.submittedAt)}</span> · 来源: {pen.source==='portal'?'门户网站':'快速报名'} · 状态: {REG_STATUS_ZH[pen.status||'pending']||pen.status}</p>
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
                        <p className="inline-flex items-center gap-1.5 text-xs text-amber-500 font-bold mb-1"><Icon name="chat" className="w-4 h-4"/>留言</p>
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
                            className="inline-flex items-center justify-center gap-1.5 px-4 py-2.5 bg-red-50 active:bg-red-100 text-red-700 border border-red-200 font-bold rounded-xl text-sm min-h-[44px]">拒绝</button>
                        <button onClick={()=>approveStudent(pen.id)} disabled={busy}
                            className="px-5 py-2.5 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm min-h-[44px]"><span className="inline-flex items-center gap-1.5"><Icon name="check" className="w-4 h-4"/>批准建档</span></button>
                    </div>
                </div>
            </div>
        );
    })}
    </>}
</div>
)}

{/* ═══ TOPUP ══════════════════════════════════════════════════ */}
{tab==='billing' && (
    <BillingPanel
        api={v1Api}
        showToast={showToast}
        canIssue={canWriteCredits}
        canTakePayment={canWriteCredits}
        accountId={routeRecordId}
        onClearAccount={()=>setTab('billing')}
    />
)}

{tab==='finance' && (
    <FinancePanel api={v1Api} showToast={showToast} />
)}

{tab==='topup' && (
<div className="anim bg-white rounded-2xl shadow-sm border border-gray-100 p-6 max-w-2xl mx-auto">
    <div className="flex items-start justify-between gap-3 mb-4"><div><h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="money" className="w-4 h-4"/>充值与退款</h2><p className="text-sm text-gray-500 mt-1">先选择学员，再完成充值或退款；支付渠道只记录实际收款方式，不在 CMS 内接入在线支付。</p></div></div>
    {canManageOperations && <details open className="mb-5 rounded-2xl border border-indigo-100 bg-indigo-50/60 overflow-hidden">
        <summary className="cursor-pointer select-none px-4 py-3 min-h-[48px] inline-flex items-center gap-2 text-sm font-bold text-indigo-900"><Icon name="card" className="w-4 h-4"/>套餐管理 <span className="text-xs font-normal text-indigo-500">{(db.packages||[]).length} 个</span></summary>
        <div className="p-4 pt-1 space-y-3">
            <p className="text-xs text-indigo-700 leading-relaxed">这里定义前台充值时可快速选择的课包。修改套餐不会改动历史充值记录；删除前请确认它不再需要被新收款使用。</p>
            {(db.packages||[]).map(pkg=><div key={pkg.id} className="flex items-center gap-3 rounded-xl border border-indigo-100 bg-white px-3 py-2.5"><div className="min-w-0 flex-1"><p className="text-sm font-bold text-gray-800 truncate">{pkg.name}</p><p className="text-xs text-gray-500 mt-0.5">{pkg.credits} 课时 · AUD {Number(pkg.price||0).toFixed(2)}</p></div><button type="button" onClick={()=>{setPkgEditId(pkg.id);setPkgName(pkg.name);setPkgCredits(String(pkg.credits));setPkgPrice(String(pkg.price));}} className="min-h-[44px] px-3 rounded-xl text-xs font-bold text-indigo-700 hover:bg-indigo-50">编辑</button><button type="button" onClick={()=>archivePackage(pkg)} aria-label={`删除套餐 ${pkg.name}`} className="min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-red-600 hover:bg-red-50"><Icon name="trash" className="w-4 h-4"/></button></div>)}
            {pkgEditId === null && <button type="button" onClick={()=>{setPkgEditId(0);setPkgName('');setPkgCredits('');setPkgPrice('');}} className="w-full min-h-[44px] rounded-xl border border-dashed border-indigo-300 bg-white text-indigo-700 text-xs font-bold hover:bg-indigo-50"><Icon name="plus" className="w-4 h-4 inline mr-1"/>添加套餐</button>}
            {pkgEditId !== null && <div className="rounded-xl border border-indigo-200 bg-white p-3 space-y-3"><p className="text-sm font-bold text-indigo-900">{pkgEditId===0?'添加套餐':'编辑套餐'}</p><div className="grid grid-cols-1 sm:grid-cols-3 gap-3"><label className="text-xs font-bold text-gray-600">套餐名称 *<input type="text" value={pkgName} onChange={e=>setPkgName(e.target.value)} placeholder="例如：10 课时包" className="mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm"/></label><label className="text-xs font-bold text-gray-600">课时数 *<input type="number" min="1" value={pkgCredits} onChange={e=>setPkgCredits(e.target.value)} placeholder="10" className="mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm"/></label><label className="text-xs font-bold text-gray-600">价格（AUD） *<input type="number" min="0" step="0.01" value={pkgPrice} onChange={e=>setPkgPrice(e.target.value)} placeholder="500.00" className="mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm"/></label></div><p className="text-[11px] text-gray-400">价格仅供内部入账和套餐快选显示；银行转账仍由工作室线下核对。</p><div className="flex gap-2"><button type="button" onClick={resetPackageEditor} className="flex-1 min-h-[44px] rounded-xl border border-gray-300 text-xs font-bold text-gray-600">取消</button><button type="button" onClick={savePackage} disabled={busy} className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">{busy?'保存中…':'保存套餐'}</button></div></div>}
        </div>
    </details>}
    {/* E: refunds require credits:refund (owner/manager) — other roles only see the top-up form */}
    {TENANT_SLUG && canRefund && (
        <div className="flex gap-2 mb-5">
            {[['topup','充值'],['refund','退款退课']].map(([m,l]) => (
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
                        <p className="text-xs text-gray-500">{s.mobile||'—'}{s.wechat ? ` · ${s.wechat}` : ''}</p>
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
    <h2 className="md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800"><Icon name="scroll" className="w-4 h-4"/>操作日志</h2>
    <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3">
        <div className="flex flex-col sm:flex-row gap-3">
            <div className="flex-1">
                <StudentPicker students={sortedAZ} value={lStu} onChange={setLStu} placeholder="精确筛选学员…" showBal={false}/>
            </div>
            <select value={lAct} onChange={e=>setLAct(e.target.value)}
                className="px-3 py-3 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none min-h-[50px]">
                <option value="">全部操作</option>
                {logActions.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
        </div>
        {!lStu && (
            <input type="text" placeholder="或输入关键字搜索…" value={lSrch} onChange={e=>setLSrch(e.target.value)}
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
                    className="px-3 py-1.5 bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold min-h-[44px]">{l}</button>
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
                    className="inline-flex items-center gap-1 px-3 py-2 bg-gray-100 active:bg-gray-200 text-gray-500 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="close" className="w-3.5 h-3.5"/>清除</button>
            )}
            <span className="text-sm text-gray-400">{filteredLogs.length} 条</span>
            {canManageOperations && <button onClick={exportLogsCSV}
                className="inline-flex items-center gap-1.5 ml-auto bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-xs min-h-[44px]"><Icon name="download" className="w-4 h-4"/>CSV</button>
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
                                <span className="text-xs text-gray-400 block mt-0.5">{displayNote(l.note)}</span>
                                {l.actorEmail && <span className="text-xs text-gray-400 block">操作人：{l.actorEmail}</span>}
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
                <button disabled={lPage===1} onClick={()=>setLPage(1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">«</button>
                <button disabled={lPage===1} onClick={()=>setLPage(p=>p-1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">‹</button>
                <span className="text-sm text-gray-600 px-2">{lPage} / {logPageCount}</span>
                <button disabled={lPage===logPageCount} onClick={()=>setLPage(p=>p+1)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">›</button>
                <button disabled={lPage===logPageCount} onClick={()=>setLPage(logPageCount)} className="px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]">»</button>
            </div>
        )}
    </div>
</div>
)}

{/* ═══ STATS ══════════════════════════════════════════════════ */}
{tab==='stats' && (
<div className="anim space-y-5">
    <h2 className="md:hidden text-xl font-bold text-gray-800 flex items-center gap-2"><Icon name="trend" className="w-6 h-6"/> 经营统计</h2>
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
            <BarChart items={analytics.chart12.map(d=>({v:d.rev,l:d.l}))} color="var(--info)" h={130}/>
            </div></div>
        </div>
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
            <div className="flex items-center justify-between mb-3">
                <p className="font-bold text-gray-700 text-sm">近 12 个月消课次数</p>
                {sStu && <span className="text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg">全局数据</span>}
            </div>
            <div className="overflow-x-auto -mx-1 px-1"><div style={{minWidth:'580px'}}>
            <BarChart items={analytics.chart12.map(d=>({v:d.ci,l:d.l}))} color="var(--success)" h={130}/>
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
            <p className="inline-flex items-center gap-1.5 font-bold text-gray-700 text-sm"><Icon name="dashboard" className="w-4 h-4"/>经营月报（近 6 个月）</p>
            <button onClick={exportBizCSV}
                className="inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"><Icon name="download" className="w-4 h-4"/>导出 CSV</button>
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
                        className="inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-sm min-h-[44px]"><Icon name="download" className="w-4 h-4"/>CSV</button>
                    <div className="flex gap-1 bg-gray-100 p-1 rounded-xl">
                        {[['monthly','月度'],['yearly','年度'],['custom','自定义']].map(([v,l]) => (
                            <button key={v} onClick={()=>setSPeriod(v)} className={`px-3 py-2 rounded-lg text-sm font-bold min-h-[44px] ${sPeriod===v?'bg-white shadow text-indigo-700':'text-gray-500'}`}>{l}</button>
                        ))}
                    </div>
                </div>
            </div>
            <div className="flex flex-wrap gap-3 items-center">
                {sPeriod==='monthly' && (
                    <select value={sYear} onChange={e=>setSYear(e.target.value)}
                        className="px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-400 outline-none text-sm min-h-[44px]">
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
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="phone" className="w-4 h-4"/>{studentStats.student.mobile||'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="mail" className="w-4 h-4"/>{studentStats.student.email||'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="target" className="w-4 h-4"/>首次: {studentStats.first?String(studentStats.first).split(',')[0]:'—'}</div>
                    <div className="bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5"><Icon name="clock" className="w-4 h-4"/>最近: {studentStats.last?String(studentStats.last).split(',')[0]:'—'}</div>
                </div>
                {studentStats.student.remark && <div className="bg-gray-50 p-3 rounded-xl text-sm text-gray-600 border border-gray-100 inline-flex items-start gap-1.5"><Icon name="note" className="w-4 h-4"/>{studentStats.student.remark}</div>}
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
    <div ref={profileDialogRef} className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm"
        role="dialog" aria-modal="true" aria-labelledby="student-profile-title">
        {/* Fix #7: slide-up sheet on mobile, centered modal on iPad.
            Three fixed bands + one scrolling band: identity / tabs / panel /
            actions. The actions used to be the last thing in the scroll, so
            "加入今日排课" — the most frequent action in the app — sat below a
            portfolio grid and a consent panel. */}
        <div className="bg-white w-full sm:rounded-3xl shadow-2xl overflow-hidden anim border-t sm:border border-gray-200 flex flex-col cms-profile-sheet">
            <div className="flex justify-between items-center p-4 bg-gray-50 border-b flex-shrink-0">
                <div className="flex items-center gap-2.5 min-w-0">
                    <PhotoAvatar photo={selS.photo} name={selS.name} size="sm"/>
                    <h3 id="student-profile-title" className="text-lg font-bold text-gray-900 truncate">{selS.name}</h3>
                    <BalBadge n={selS.balance}/>
                    {selS.archived && <span className="text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full shrink-0">归档</span>}
                </div>
                <button onClick={()=>{setSelS(null);setEditP(false);}} aria-label="关闭" className="text-gray-400 active:text-gray-700 text-2xl font-bold p-2 -mr-1 min-h-[44px] min-w-[44px] flex items-center justify-center">×</button>
            </div>
            {/* Grouped by the question being answered, not by field type:
                概览 = who do I call and when were they last here (what the
                front desk needs in the first five seconds); 资料 = is their
                record correct; 记录 = what happened; 作品 = what have they
                made and may we publish it — the consent panel lives HERE
                because consent only ever means "may this piece go public",
                and splitting the two is what made the old stack a wall;
                专区 = can the parent log in, a different audience entirely. */}
            {!editP && <Tabs idBase="student-profile" label="学员档案分类"
                value={studentProfileTab} onChange={setStudentProfileTab}
                className="px-2 bg-white flex-shrink-0"
                items={[
                    {value:'profile', label:'概览', icon:'users'},
                    {value:'details', label:'资料', icon:'clipboard'},
                    {value:'records', label:'记录', icon:'calendar'},
                    ...(canWritePortfolio ? [{value:'portfolio', label:`${workNoun}集`, icon:'image'}] : []),
                    ...(TENANT_SLUG && canWriteStudents ? [{value:'portal', label:'专区', icon:'lock'}] : []),
                ]}/>}
            {/* Fix ⑧: modal-scroll + safe-area bottom padding for iPad Home bar */}
            <div className="modal-scroll cms-profile-body flex-1 min-h-0">
                {!editP ? (
                    <div className="space-y-3">
                        <TabPanel idBase="student-profile" name="profile" active={studentProfileTab==='profile'}>
                        <div className="grid grid-cols-2 gap-3">
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="phone" className="w-4 h-4"/>电话</p><p className="font-bold text-gray-800">{selS.mobile||'—'}</p></div>
                            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="calendar" className="w-4 h-4"/>最近上课</p><p className="font-bold text-gray-800">{fmtDate(selS.lastActive)}</p></div>
                        </div>
                        {(selS.wechat||selS.email) && (
                            <div className="grid grid-cols-2 gap-3">
                                {selS.wechat && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="chat" className="w-4 h-4"/>微信号</p><p className="font-bold text-gray-800">{selS.wechat}</p></div>}
                                {selS.email  && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1"><Icon name="mail" className="w-4 h-4"/>邮箱</p><p className="font-bold text-gray-800 text-sm break-all">{selS.email}</p></div>}
                            </div>
                        )}
                        {/* 「谁付账、欠多少」和「打给谁」是同一个问题的两半，
                            前台在头五秒里两个都要。归属为空就整块不渲染。 */}
                        {TENANT_SLUG && <StudentBillingAccount api={v1Api} studentId={selS.id}
                            onOpenBilling={(id)=>{ setSelS(null); setTab('billing', {recordId: id}); }} />}
                        {selS.remark && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">备注</p><p className="text-sm text-gray-700 whitespace-pre-wrap">{selS.remark}</p></div>}
                        {!selS.mobile && !selS.wechat && !selS.email && !selS.remark &&
                            <EmptyState icon={<Icon name="phone" className="w-8 h-8"/>} main="还没有联系方式" sub="点击下方「编辑」补充电话、微信或邮箱"/>}
                        </TabPanel>

                        <TabPanel idBase="student-profile" name="details" active={studentProfileTab==='details'}>
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
                        {(selS.birthday||selS.enrollmentDate) && <div className="grid grid-cols-2 gap-3">
                            {selS.birthday && <div className="bg-pink-50 p-4 rounded-2xl border border-pink-100"><p className="inline-flex items-center gap-1.5 text-xs text-pink-400 mb-1"><Icon name="cake" className="w-4 h-4"/>生日</p><p className="font-bold text-gray-800">{fmtDate(selS.birthday)}</p></div>}
                            {selS.enrollmentDate && <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100"><p className="text-xs text-gray-400 mb-1">入学日期</p><p className="font-bold text-gray-800">{fmtDate(selS.enrollmentDate)}</p></div>}
                        </div>}
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
                        {/* Archiving is a lifecycle decision taken a handful of
                            times a year. It used to be the last button in the
                            scroll, one thumb-width below 生成成长报告 — the
                            classic mis-tap. It belongs at the end of the record
                            it changes, not next to the daily actions. */}
                        {canWriteStudents && <button onClick={()=>archiveStudent(selS.id,selS.name,!selS.archived)}
                            className={`w-full py-3 rounded-xl text-sm font-bold border min-h-[50px] ${selS.archived?'bg-green-50 active:bg-green-100 text-green-700 border-green-200':'bg-gray-50 active:bg-gray-100 text-gray-500 border-gray-200'}`}>
                            <span className="inline-flex items-center gap-1.5"><Icon name={selS.archived ? 'restore' : 'archiveBox'} className="w-4 h-4"/>{selS.archived ? '恢复学员' : '归档学员'}</span>
                        </button>
                        }
                        </TabPanel>

                        <TabPanel idBase="student-profile" name="records" active={studentProfileTab==='records'}>
                        {/* 报告排在充值与上课记录之前，因为它是唯一一件等着人做的事；
                            下面两块是它的证据，也是查阅用的历史。老师写评语时
                            要看的出勤和课堂笔记，就在同一屏上。 */}
                        {TENANT_SLUG && <StudentProgressReports api={v1Api} studentId={selS.id}
                            studentName={selS.name} canWrite={canWriteProgress}
                            canPublish={canPublishProgress} showToast={showToast} />}
                        {/* F2: Topup history collapsible */}
                        {canWriteCredits && (()=>{
                            const topupsAll = db.logs.filter(l=>(l.studentId===selS.id || (!l.studentId && l.studentName===selS.name))&&l.action==='充值购课');   /* D3 */
                            const topups = topupsAll.slice(0,10);
                            if (!topupsAll.length) return null;
                            return (
                                <details className="border border-gray-200 rounded-2xl overflow-hidden">
                                    <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2">
                                        <Icon name="card" className="w-4 h-4"/>充值记录 <span className="font-normal text-gray-400 text-xs">({topupsAll.length} 条{topupsAll.length>10?' · 显示最近10条':''})</span>
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
                                <summary className="inline-flex items-center gap-1.5 bg-blue-50 px-4 py-3 cursor-pointer select-none text-sm font-bold text-blue-700"><Icon name="calendar" className="w-4 h-4"/>上课记录 <span className="font-normal text-blue-400 text-xs ml-1">(近 {attHistory.length} 次)</span></summary>
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
                        {!(canWriteCredits && db.logs.some(l=>(l.studentId===selS.id || (!l.studentId && l.studentName===selS.name))&&l.action==='充值购课'))
                            && !(TENANT_SLUG && attHistory && attHistory.length > 0) &&
                            <EmptyState icon={<Icon name="calendar" className="w-8 h-8"/>} main="还没有记录" sub="充值与上课签到会自动出现在这里"/>}
                        </TabPanel>

                        {TENANT_SLUG && canWriteStudents && (
                          <TabPanel idBase="student-profile" name="portal" active={studentProfileTab==='portal'}>
                            <div className="border border-indigo-100 rounded-2xl overflow-hidden">
                                <div className="bg-indigo-50 px-4 py-3 flex items-center justify-between gap-3">
                                    <div>
                                        <p className="inline-flex items-center gap-1.5 text-sm font-bold text-indigo-800"><Icon name="lock" className="w-4 h-4"/>学员专区</p>
                                        <p className="text-xs text-indigo-500 mt-0.5">姓名、手机与独立 6 位访问码验证；访问码不会保存明文。</p>
                                    </div>
                                    <span className={`text-xs font-bold px-2 py-1 rounded-full shrink-0 ${selS.hasAccessCode?'bg-emerald-100 text-emerald-700':'bg-gray-100 text-gray-500'}`}>
                                        {selS.hasAccessCode?'已启用':'未启用'}
                                    </span>
                                </div>
                                <div className="p-4 space-y-3">
                                    {!selS.mobile && <p className="text-xs rounded-xl bg-amber-50 border border-amber-100 text-amber-700 p-3">请先补充学员手机号码，再生成访问码。</p>}
                                    {accessCodeResult?.studentId===selS.id && (
                                        <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                                            <p className="text-xs font-bold text-amber-800">仅显示一次，请立即安全交给家长或成年学员</p>
                                            <div className="flex items-center gap-3 mt-2">
                                                <code className="text-2xl tracking-[0.3em] font-bold text-gray-900">{accessCodeResult.code}</code>
                                                <button onClick={()=>copyText(accessCodeResult.code,'访问码已复制')}
                                                    className="ml-auto px-3 py-2 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-800 min-h-[44px]">复制</button>
                                            </div>
                                        </div>
                                    )}
                                    {selS.accessCodeUpdatedAt && <p className="text-xs text-gray-400">最近更新：{fmtDate(selS.accessCodeUpdatedAt)}</p>}
                                    <div>
                                        <button disabled={busy||!selS.mobile}
                                            onClick={()=>selS.hasAccessCode
                                                ? confirm('生成新访问码后，旧访问码和现有登录会话会立即失效。继续？', generateStudentAccessCode, {confirmText:'生成新码'})
                                                : generateStudentAccessCode()}
                                            className="w-full py-2.5 rounded-xl bg-indigo-600 active:bg-indigo-700 text-white text-sm font-bold disabled:bg-gray-300 min-h-[44px]">
                                            {selS.hasAccessCode?'更换访问码':'生成访问码'}
                                        </button>
                                        {selS.hasAccessCode && (
                                            <details className="mt-3 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
                                                <summary className="cursor-pointer text-xs font-bold text-gray-500 select-none">高级操作</summary>
                                                <div className="pt-3 flex items-center gap-3">
                                                    <p className="text-xs text-gray-500 flex-1">停用后，当前访问码和所有已登录会话会立即失效。</p>
                                                    <button disabled={busy} onClick={revokeStudentAccessCode}
                                                        className="px-3 py-2 rounded-lg bg-white border border-red-200 text-red-700 text-xs font-bold min-h-[44px]">停用学员专区</button>
                                                </div>
                                            </details>
                                        )}
                                    </div>
                                </div>
                            </div>
                          </TabPanel>
                        )}

                        {canWritePortfolio && (
                          <TabPanel idBase="student-profile" name="portfolio" active={studentProfileTab==='portfolio'}>
                        {TENANT_SLUG && (
                            <div className="border border-emerald-100 rounded-2xl overflow-hidden">
                                <div className="bg-emerald-50 px-4 py-3 flex items-center justify-between gap-3">
                                    <div>
                                        <p className="inline-flex items-center gap-1.5 text-sm font-bold text-emerald-800"><Icon name="shield" className="w-4 h-4"/>官网作品公开授权</p>
                                        <p className="text-xs text-emerald-600 mt-0.5">授权与撤回均追加为不可覆盖的审计记录。</p>
                                    </div>
                                    <span className={`text-xs font-bold px-2 py-1 rounded-full shrink-0 ${selS.publicationConsent?.status==='confirmed'?'bg-emerald-600 text-white':selS.publicationConsent?.status==='withdrawn'?'bg-amber-100 text-amber-700':'bg-gray-100 text-gray-500'}`}>
                                        {selS.publicationConsent?.status==='confirmed'?'有效':selS.publicationConsent?.status==='withdrawn'?'已撤回':'未记录'}
                                    </span>
                                </div>
                                <div className="p-4 space-y-3">
                                    {selS.publicationConsent?.status==='confirmed' && (
                                        <div className="text-xs text-gray-600 space-y-1">
                                            <p>授权人：<span className="font-bold">{selS.publicationConsent.by||'—'}</span> · {selS.publicationConsent.relationship||'—'} · {selS.publicationConsent.method||'—'}</p>
                                            <p className="text-gray-400">记录时间：{fmtDate(selS.publicationConsent.at)} · 告知版本 {selS.publicationConsent.noticeVersion||'—'}</p>
                                        </div>
                                    )}
                                    {consentEdit?.mode==='confirm' && (
                                        <div className="space-y-2 rounded-xl bg-gray-50 border border-gray-100 p-3">
                                            <input value={consentEdit.by} onChange={e=>setConsentEdit(p=>({...p,by:e.target.value}))}
                                                placeholder="授权人姓名 *" maxLength={120}
                                                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-emerald-400"/>
                                            <div className="grid grid-cols-2 gap-2">
                                                <select value={consentEdit.relationship} onChange={e=>setConsentEdit(p=>({...p,relationship:e.target.value}))}
                                                    className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white">
                                                    <option value="">与学员关系 *</option><option>监护人</option><option>本人</option><option>其他授权人</option>
                                                </select>
                                                <select value={consentEdit.method} onChange={e=>setConsentEdit(p=>({...p,method:e.target.value}))}
                                                    className="px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white">
                                                    <option value="">授权方式 *</option><option>书面确认</option><option>电子确认</option><option>当面确认</option>
                                                </select>
                                            </div>
                                            <textarea value={consentEdit.note} onChange={e=>setConsentEdit(p=>({...p,note:e.target.value}))}
                                                placeholder="备注（可选，不要记录证件号码）" rows="2" maxLength={500}
                                                className="w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm resize-none"/>
                                            <div className="flex gap-2">
                                                <button onClick={()=>setConsentEdit(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-bold text-gray-500">取消</button>
                                                <button disabled={busy} onClick={savePublicationConsent} className="flex-1 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-bold disabled:opacity-50">记录授权</button>
                                            </div>
                                        </div>
                                    )}
                                    {consentEdit?.mode==='withdraw' && (
                                        <div className="space-y-2 rounded-xl bg-red-50 border border-red-100 p-3">
                                            <textarea value={consentEdit.note} onChange={e=>setConsentEdit(p=>({...p,note:e.target.value}))}
                                                placeholder="撤回原因 *（将写入审计记录）" rows="2" maxLength={500}
                                                className="w-full px-3 py-2.5 border border-red-200 rounded-xl text-sm resize-none"/>
                                            <p className="text-xs text-red-600">确认后，该学员当前所有官网公开作品会立即下架，私人作品仍保留。</p>
                                            <div className="flex gap-2">
                                                <button onClick={()=>setConsentEdit(null)} className="flex-1 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-500">取消</button>
                                                <button disabled={busy} onClick={withdrawPublicationConsent} className="flex-1 py-2.5 rounded-xl bg-red-600 text-white text-sm font-bold disabled:opacity-50">撤回并下架</button>
                                            </div>
                                        </div>
                                    )}
                                    {!consentEdit && (
                                        <div className="flex gap-2">
                                            <button onClick={()=>setConsentEdit({mode:'confirm',by:'',relationship:'',method:'',note:''})}
                                                className="flex-1 py-2.5 rounded-xl bg-emerald-600 text-white text-sm font-bold min-h-[44px]">
                                                {selS.publicationConsent?.status==='confirmed'?'追加新授权记录':'记录授权'}
                                            </button>
                                            {selS.publicationConsent?.status==='confirmed' && <button onClick={()=>setConsentEdit({mode:'withdraw',note:''})}
                                                className="px-4 py-2.5 rounded-xl bg-white border border-red-200 text-red-700 text-sm font-bold min-h-[44px]">撤回</button>}
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* ── Portfolio section ── */}
                        {(()=>{
                            const items = selS.portfolio || [];
                            return (
                                <div className="border border-purple-100 rounded-2xl overflow-hidden">
                                    <div className="bg-purple-50 px-4 py-3 flex items-center justify-between">
                                        <span className="text-sm font-bold text-purple-700 flex items-center gap-1.5"><Icon name="image" className="w-4 h-4"/> {workNoun}集
                                            <span className="font-normal text-purple-400 text-xs ml-1">({items.length} 张)</span>
                                        </span>
                                        <button onClick={()=>setPortUpload(true)}
                                            className="text-xs bg-purple-600 active:bg-purple-700 text-white px-3 py-1.5 rounded-lg font-bold">
                                            + 上传
                                        </button>
                                    </div>
                                    {items.length === 0 ? (
                                        <div className="px-4 py-7 text-center">
                                            <p className="inline-flex items-center gap-1.5 text-2xl mb-1"><Icon name="image" className="w-4 h-4"/></p>
                                            <p className="text-xs text-gray-400">还没有作品，点击「上传」添加第一张</p>
                                        </div>
                                    ) : (
                                        <div className="p-2.5 grid grid-cols-3 gap-2">
                                            {items.map((item,idx)=>(
                                                <div key={item.id}
                                                    className="port-thumb relative group cursor-pointer rounded-xl overflow-hidden bg-gray-100"
                                                    style={{aspectRatio:'1'}}
                                                    role="button" tabIndex={0}
                                                    aria-label={`查看${item.title || fmtDate(item.date)}作品`}
                                                    onKeyDown={event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();setPortLB({items,idx});}}}
                                                    onClick={()=>setPortLB({items,idx})}>
                                                    {/* M7: skeleton shown until image loads */}
                                                    <div className="img-skel absolute inset-0" id={`sk-${item.id}`}/>
                                                    <img
                                                        src={portfolioThumbSrc(selS.id, item)}
                                                        srcSet={portfolioSrcSet(selS.id, item)}
                                                        sizes="(max-width: 640px) 33vw, 220px"
                                                        alt={item.title || `${selS.name}的作品 ${idx + 1}`}
                                                        loading="lazy"
                                                        className="w-full h-full object-cover relative"
                                                        onLoad={e=>{const sk=document.getElementById(`sk-${item.id}`);if(sk)sk.style.display='none';}}
                                                        onError={e=>{e.target.style.display='none';}}/>
                                                    <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pt-4 pb-1">
                                                        {item.title && <p className="text-white text-xs font-bold leading-tight truncate">{item.title}</p>}
                                                        <p className="text-white text-xs leading-tight truncate">{fmtDate(item.date)}{item.note?' ·':''}</p>
                                                    </div>
                                                    {item.public && (
                                                        <span className="absolute top-1 left-1 rounded-full bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 shadow">
                                                            官网
                                                        </span>
                                                    )}
                                                    {/* B1: port-actions = hidden on mouse devices (hover:flex), always visible on touch (CSS override) */}
                                                    {/* Icon stays compact; the shared aria-label rule expands its hit box to 44px. */}
                                                    <div className="port-actions absolute top-0.5 right-0.5 hidden group-hover:flex gap-1 z-10">
                                                        <button
                                                            onClick={e=>{e.stopPropagation();setPortEdit({sid:String(selS.id),item,note:item.note||'',title:item.title||'',date:item.date||todayISO(),public:!!item.public});}}
                                                            aria-label="编辑" className="bg-white/90 rounded-lg p-2 shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center"><Icon name="pencil" className="w-4 h-4"/></button>
                                                        <button
                                                            onClick={e=>{e.stopPropagation();portfolioDoDelete(String(item.id));}}
                                                            aria-label="删除" className="bg-red-500 rounded-lg p-2 text-white shadow leading-none min-w-[32px] min-h-[32px] flex items-center justify-center"><Icon name="trash" className="w-4 h-4"/></button>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            );
                        })()}
                        {/* The growth report is assembled FROM the portfolio, so
                            it is the one action that belongs to a tab rather
                            than to the student. */}
                        {canWritePortfolio && <button onClick={()=>openGrowthReport(selS)}
                            className="w-full py-3 rounded-xl text-sm font-bold bg-gradient-to-r from-purple-500 to-pink-500 active:from-purple-600 active:to-pink-600 text-white min-h-[50px] shadow-sm">
                            <span className="inline-flex items-center gap-1.5"><Icon name="star" className="w-4 h-4"/>生成成长报告（发给家长）</span>
                        </button>
                        }
                          </TabPanel>
                        )}
                    </div>
                ) : (
                    <form onSubmit={handleUpdateStudent} className="space-y-4">
                        <div>
                            <label className="text-sm font-bold text-gray-500 mb-2 block">照片 Photo <span className="font-normal text-gray-400">选填</span></label>
                            <PhotoUploader value={editPhoto} onChange={setEditPhoto} notify={notify}/>
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
                                {/* White, not the indigo-50 fill: a tinted box next
                                    to white siblings reads as disabled, and this is
                                    the one field in the form that writes a ledger
                                    entry. The indigo border carries the emphasis. */}
                                <input name="balance" type="number" min="0" defaultValue={selS.balance} required className="w-full px-3 py-3 border-2 border-indigo-300 bg-white text-indigo-800 font-bold text-xl rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                                <p className="inline-flex items-center gap-1.5 text-xs text-amber-500 mt-1"><Icon name="warning" className="w-4 h-4"/>修改将记入日志</p>
                            </div>
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">微信号 <span className="font-normal text-gray-400">选填</span></label>
                                <input name="wechat" defaultValue={selS.wechat||''} placeholder="如 wechat_id" className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">邮箱 <span className="font-normal text-gray-400">选填</span></label>
                                <input name="email" type="email" defaultValue={selS.email||''} className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                        </div>
                        {/* Birthday and historical enrolment date remain first-class profile fields. */}
                        <div className="grid grid-cols-2 gap-3">
                            <div><label className="inline-flex items-center gap-1.5 text-sm font-bold text-gray-500 mb-1 block"><Icon name="cake" className="w-4 h-4"/>生日 <span className="font-normal text-gray-400">选填</span></label>
                                <input type="date" name="birthday" defaultValue={selS.birthday||''} min="1920-01-01" max="2099-12-31"
                                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/></div>
                            <div><label className="text-sm font-bold text-gray-500 mb-1 block">入学日期 <span className="font-normal text-gray-400">选填</span></label>
                                <input type="date" name="enrollmentDate" defaultValue={selS.enrollmentDate||''} min="1900-01-01" max={todayISO()}
                                    className="w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"/>
                                <p className="text-[11px] text-gray-400 mt-1">可补录系统启用前的真实入学日期</p></div>
                        </div>
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
                                className="px-4 py-3 bg-red-50 active:bg-red-100 text-red-700 font-bold rounded-xl text-sm border border-red-200 min-h-[50px]"><span className="inline-flex items-center gap-1.5"><Icon name="trash" className="w-4 h-4"/>永久删除</span></button>
                            <div className="flex gap-2">
                                <button type="button" onClick={()=>confirm('放弃未保存的修改？', ()=>{setEditP(false);setEditPhoto('');}, {confirmText:'放弃修改'})} className="px-4 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm min-h-[50px]">取消</button>
                                <button type="submit" disabled={busy} className="inline-flex items-center gap-1.5 px-6 py-3 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm shadow-md min-h-[50px]"><Icon name="save" className="w-4 h-4"/>保存</button>
                            </div>
                        </div>
                    </form>
                )}
            </div>
            {/* Outside the scroll, and outside the tabs. Three actions earn
                that: 加入今日排课 is performed many times a day, 快速充值 is
                what you reach for the moment the balance badge in the header
                reads low, and 编辑 is a mode switch that has to work from
                whichever tab you happen to be on. Everything else is either
                rare (归档) or belongs to one tab's subject (成长报告).
                Columns are 1.618 : 1 — the primary action wins the golden
                major share, the secondary takes the minor. */}
            {!editP && (
                <div className="cms-profile-actions flex-shrink-0 border-t border-gray-200 bg-gray-50">
                    <div className="cms-profile-actions-row">
                        {canWriteAttendance && !selS.archived &&
                            <button onClick={()=>scheduleStudentToday(selS)} disabled={busy}
                                className="py-3 rounded-xl text-sm font-bold bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 min-h-[50px] inline-flex items-center justify-center gap-1.5"><Icon name="calendar" className="w-4 h-4"/>{isStudentScheduledOn(selS.id,todayISO())?'查看今日排课':'加入今日排课'}</button>}
                        {canWriteStudents && <button onClick={()=>{setEditP(true);setEditPhoto(selS.photo||'');}}
                            className="py-3 rounded-xl text-sm font-bold bg-white border-2 border-indigo-100 active:bg-indigo-50 text-indigo-700 min-h-[50px]"><span className="inline-flex items-center gap-1.5"><Icon name="pencil" className="w-4 h-4"/>编辑</span></button>}
                    </div>
                    {canWriteCredits && !selS.archived && (
                        <button onClick={()=>{setTuStu(selS.id);setSelS(null);setEditP(false);setTab('topup');}}
                            className="w-full py-3 rounded-xl text-sm font-bold bg-white border border-gray-200 active:bg-gray-50 text-gray-700 min-h-[50px]"><span className="inline-flex items-center gap-1.5"><Icon name="money" className="w-4 h-4"/>快速充值</span></button>
                    )}
                </div>
            )}
        </div>
    </div>
)}

                <footer className="mt-8 pb-6 text-center text-[10px] tracking-wide text-gray-400">
                    © 2026 {tenantDisplayName} · Powered by Paradise Production
                </footer>
            </main>

            {/* ── Mobile bottom nav (md:hidden) ── */}
            {/* U1: 5+more mobile nav */}
            {moreOpen && <div className="md:hidden fixed inset-0 z-[45]" onClick={()=>setMoreOpen(false)}/>}
            {moreOpen && (
                <div className="md:hidden fixed bottom-[calc(56px+env(safe-area-inset-bottom,0px))] left-0 right-0 z-[46] cms-chrome border-t px-4 py-3 grid grid-cols-4 gap-2 anim"
                     onClick={e=>e.stopPropagation()}>
                    {[{k:'courses',i:'',s:'课程'},{k:'works',i:'',s:'作品'},{k:'logs',i:'',s:'日志'},{k:'stats',i:'',s:'统计'},{k:'pending',i:'',s:'待处理',badge:pendingCount},{k:'new_student',i:<Icon name="plus" className="w-[22px] h-[22px]"/>,s:'新建'},{k:'settings',i:'',s:'设置'}].filter(item=>allowedTabs.includes(item.k)).map(({k,i,s,badge})=>(
                        <button key={k} onClick={()=>{setTab(k);setMoreOpen(false);}}
                            className={`flex flex-col items-center justify-center py-2.5 gap-0.5 rounded-xl relative cms-chrome-item ${['courses','works','logs','stats','pending','new_student','settings'].includes(tab)&&tab===k?'is-active':''}`}>
                            <span className="text-[22px] leading-none">{i}</span>
                            <span className="text-[10px] font-bold leading-none tracking-tight">{s}</span>
                            {badge>0 && <span className="absolute top-1 right-2 bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4">{badge}</span>}
                        </button>
                    ))}
                </div>
            )}
            <nav className="md:hidden fixed bottom-0 left-0 right-0 z-40 cms-chrome border-t flex"
                 style={{paddingBottom:'env(safe-area-inset-bottom,0px)', transform:'translateZ(0)', willChange:'transform'}}>
                {[{k:'dashboard',i:'',s:'工作台'},{k:'roster',i:'',s:'课表'},{k:'students',i:'',s:'档案'},{k:'topup',i:'',s:'充值'}].filter(item=>allowedTabs.includes(item.k)).map(({k,i,s}) => (
                    <button key={k} onClick={()=>{setTab(k);setMoreOpen(false);}}
                        aria-current={tab===k ? 'page' : undefined}
                        className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative cms-chrome-item cms-chrome-tab ${tab===k?'is-active':''}`}>
                        <span className="text-[22px] leading-none">{i}</span>
                        <span className="text-[10px] font-bold leading-none tracking-tight">{s}</span>
                        {k==='dashboard' && analytics.lowBalance.length>0 &&
                            <span className="absolute top-1.5 right-[18%] bg-red-500 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4">{analytics.lowBalance.length}</span>}
                    </button>
                ))}
                {/* More button */}
                <button onClick={()=>setMoreOpen(o=>!o)}
                    className={`flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative cms-chrome-item cms-chrome-tab ${moreOpen||['courses','works','logs','stats','pending','new_student','settings'].includes(tab)?'is-active':''}`}>
                    <span className="leading-none inline-flex items-center justify-center h-[22px]">{moreOpen?<Icon name="close" className="w-[22px] h-[22px]"/>:<Icon name="ellipsis" className="w-[22px] h-[22px]"/>}</span>
                    <span className="text-[10px] font-bold leading-none tracking-tight">更多</span>
                    {pendingCount>0 && !moreOpen && <span className="absolute top-1.5 right-[18%] bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4">{pendingCount}</span>}
                </button>
            </nav>
        </div>
    );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
