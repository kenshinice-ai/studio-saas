/* 通用组件与模块级工具 — v10.11.0 从 cms-app.jsx 顶层机械搬出。
 * 逐字移动：函数体未改，只加了 export。App 与各 panel 从这里 import。
 */

const { useState, useEffect, useMemo, useRef, useCallback } = React;
export const tenantSlug = window.STUDIOSAAS_TENANT_SLUG
    || new URLSearchParams(location.search).get('tenant')
    || ((location.pathname.match(/^\/([^/]+)(?:\/cms)?\/?$/) || [])[1])
    || '';

/* ═══════════════════ DATE UTILS (AU DD/MM/YYYY) ════════════════ */
export const nowAU = () => new Date().toLocaleString('en-AU', {
    timeZone:'Australia/Melbourne', day:'2-digit', month:'2-digit', year:'numeric',
    hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false
});
export const todayISO  = () => new Date().toLocaleDateString('en-CA');
/* B1: shift an ISO date by N days (local-safe via noon anchor) */
export const shiftDate = (iso, delta) => {
    const d = new Date(`${iso}T12:00:00`);
    d.setDate(d.getDate() + delta);
    return d.toLocaleDateString('en-CA');
};
export const fmtDate   = (s) => {
    if (!s) return '—';
    const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : String(s).split(' ')[0];
};
export const daysSince = (iso) => {
    if (!iso) return 9999;
    const d = new Date(iso);
    return isNaN(d) ? 9999 : Math.floor((Date.now() - d) / 864e5);
};
/* 待审核列表的提交时间：数据库原始值形如 "2026-07-26 21:31:15.046556+10:00"，
   微秒和时区偏移是噪音。截到分钟展示（原始值保留在 title 里）。
   值本身已带 studio 本地偏移，直接截取即是 studio 当地时间，无需换算。 */
export const fmtDT = (s) => {
    const m = String(s||'').match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    return m ? `${m[1]} ${m[2]}` : (s ? String(s) : '—');
};
/* 注册申请状态 → 中文标签（EN 由 cms-i18n.js 词典层翻译）。
   与 api_v1.py update_registration_status 的 allowed_statuses 对齐。 */
export const REG_STATUS_ZH = {
    pending:'待审核', contacted:'已联系', trial_booked:'已约试听', waiting:'跟进中',
    approved:'已批准', converted:'已建档', rejected:'已拒绝', duplicate:'重复申请',
    lost:'已流失', archived:'已归档',
};
/* A2: tenant 模式下签到/课时改走 v1 账本端点（与 Studio Admin 同一本账）。
   根目录单店模式（无 tenantSlug）保持原有整包保存路径不变。 */
export const TENANT_SLUG = window.STUDIOSAAS_TENANT_SLUG || '';

/* CMS navigation is intentionally URL-addressable.  Notifications, browser
   back/forward, bookmarks and support links should all open the same work
   surface instead of losing the operator in a single in-memory tab state. */
export const CMS_ROUTE_TABS = new Set([
    'dashboard', 'roster', 'courses', 'students', 'works', 'new_student',
    'pending', 'billing', 'topup', 'finance', 'logs', 'stats', 'settings'
]);
/* `?section=` is ONE parameter shared by every tab, so it can only be read in
   the scope of the tab it arrived with. Before this it was returned raw and
   unchecked — `?section=nonsense` left the settings page on a section that
   does not exist (no panel matched, so every panel hid and the page rendered
   empty), and a section belonging to one tab leaked into another's state.
   Register a tab here to give it a whitelist and a fallback; tabs absent from
   this map ignore `section` entirely. One table, every tab. */
export const CMS_ROUTE_SECTIONS = Object.assign(Object.create(null), {
    settings: {
        allowed: ['account', 'team', 'operational', 'billing-identity',
                  'integrations', 'maintenance', 'workspace'],
        fallback: 'account',
    },
});
export const readCmsSection = (tab, params) => {
    /* 原型链上没有东西 —— 这张表用 Object.create(null) 建。否则
       readCmsSection('constructor') 会拿到 Object 的构造函数，绕过下面这行
       判空，再在 scope.allowed.includes 上抛 TypeError；而这个文件里一个
       未捕获的异常会静默掐掉整段渲染。readCmsRoute 自己先过了
       CMS_ROUTE_TABS 白名单，但这个函数是导出的，下一个调用方没这个保证。 */
    const scope = CMS_ROUTE_SECTIONS[tab];
    if (!scope || !Array.isArray(scope.allowed)) return '';
    const requested = params.get('section') || '';
    return scope.allowed.includes(requested) ? requested : scope.fallback;
};
export const readCmsRoute = () => {
    const params = new URLSearchParams(window.location.search || '');
    const requested = params.get('view') || params.get('tab') || 'dashboard';
    const tab = CMS_ROUTE_TABS.has(requested) ? requested : 'dashboard';
    return {
        tab,
        pendingTab: params.get('type') === 'booking' || params.get('type') === 'bookings'
            ? 'bookings'
            : params.get('type') === 'reports' ? 'reports' : 'registrations',
        /* Scoped, not raw: a `section` that arrived with another tab must not
           become the settings page's state. */
        settingsSection: tab === 'settings' ? readCmsSection(tab, params) : 'account',
        recordId: params.get('id') || '',
    };
};
export const v1Api = async (path, options = {}) => {
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
        err.details = d.details || null;
        /* Typed error handling (e.g. invoice_profile_incomplete) needs the
           machine code and payload, not the human sentence in message. */
        err.code = d.error || null;
        err.payload = d;
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
export const AUDIT_ACTION_ZH = {
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
export const auditNote = (action, meta) => {
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

export const parseMonthKey = (ds) => {
    if (!ds) return null;
    const s = String(ds);
    const a = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);  if (a) return `${a[3]}-${a[2].padStart(2,'0')}`;
    const b = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/);  if (b) return `${b[1]}-${b[2].padStart(2,'0')}`;
    const c = s.match(/^(\d{4})-(\d{2})/);                  if (c) return `${c[1]}-${c[2]}`;
    return null;
};
export const fmtMK = (k) => { if (!k) return ''; const [y,m]=k.split('-'); return `${m}/${y}`; };

export const tenantOwnedLogoUrl = (brand) => {
    const source = brand?.logo_url || brand?.logoUrl || '';
    return ['/logo.png', '/logo-light.png', '/favicon.svg'].includes(source) ? '' : source;
};

/**
 * Render only the configured tenant logo and react to the shared brand event.
 *
 * There is intentionally no PWE or Paradise fallback: tenant-owned CMS
 * surfaces keep the tenant name as the complete identity when no logo exists.
 */
export function TenantBrandLogo({ className = '' }) {
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
export function BarChart({ items, color='var(--info)', h=140, prefix='' }) {
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
export function Tabs({idBase, label, items, value, onChange, className=''}) {
    const refs = useRef({});
    const stripRef = useRef(null);
    const order = items.map(i => i.value);
    /* The strip scrolls instead of wrapping (see above), and until now nothing
       ever scrolled the SELECTED tab back into it. Measured on the settings
       page at v10.14.0: seven tabs are 654px of content in a 343px strip at
       375px wide, so the last four render with their tab outside the visible
       box. Deep-linking to ?section=integrations on a phone therefore showed
       the first three tabs — none of them selected — above the 集成 panel, and
       the page read as though nothing was chosen.

       It belongs here rather than at the call site: the roster and stats
       strips are about to use the same primitive, and a fix in `Tabs` is a fix
       they never have to remember. */
    const alignSelected = useCallback(() => {
        const strip = stripRef.current, node = refs.current[value];
        if (!strip || !node || typeof node.getBoundingClientRect !== 'function') return;
        const view = strip.getBoundingClientRect(), tab = node.getBoundingClientRect();
        const overLeft = view.left - tab.left;        // >0: the tab starts before the view
        const overRight = tab.right - view.right;     // >0: it ends after the view
        if (overLeft <= 0 && overRight <= 0) return;  // already whole
        /* 8px so the tab does not end up flush against the edge it scrolled to.
           Rect deltas rather than offsetLeft: the tabs' offsetParent is BODY,
           not the strip, so offsetLeft only agrees with the strip's coordinate
           space while the strip happens to start at x≈0.
           The jump is instant on purpose. This runs on mount for a deep link,
           where an animated strip is a movement nobody asked for, and instant
           needs no `prefers-reduced-motion` branch to stay honest. */
        strip.scrollLeft += overLeft > 0 ? -(overLeft + 8) : (overRight + 8);
    }, [value]);
    /* Aligning once on mount is not enough, and the first attempt shipped that
       way: measured mid-layout the strip was 158px of an eventual 343px, the
       selected tab computed as already visible, the effect returned early and
       — with `value` unchanged — never ran again. So watch the strip instead
       of guessing when it has settled. This also covers rotation and window
       resize, where the same tab can fall out of view without `value` moving. */
    useEffect(() => {
        alignSelected();
        const strip = stripRef.current;
        if (!strip || typeof ResizeObserver !== 'function') return;
        const observer = new ResizeObserver(() => alignSelected());
        observer.observe(strip);
        return () => observer.disconnect();
    }, [alignSelected, items.length]);
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
        <div role="tablist" aria-label={label} onKeyDown={onKeyDown} ref={stripRef}
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

export function TabPanel({idBase, name, active, children}) {
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
export function EmptyState({icon=null, main='暂无数据', sub='', action=null, onAction=null}) {
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

export function BalBadge({ n }) {
    const v = parseInt(n,10)||0;
    if (v===0) return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-red-100 text-red-700 whitespace-nowrap"><Icon name="warning" className="w-3.5 h-3.5"/>0</span>;
    if (v<=2)  return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-orange-100 text-orange-700 whitespace-nowrap"><Icon name="bolt" className="w-3.5 h-3.5"/>{v}</span>;
    /* a11y: the low state must not differ from normal by colour alone */
    if (v<=4)  return <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-700 whitespace-nowrap"><Icon name="bolt" className="w-3.5 h-3.5"/>{v}</span>;
    return           <span className="px-2.5 py-1 rounded-lg text-xs font-bold bg-green-100 text-green-700 whitespace-nowrap">{v}</span>;
}

/* ═══════════════════ TOAST ════════════════════════════════════ */
export function Toast({ msg, type, action, onDone }) {
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
export function CmsNotificationCenter({
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
export function useModalFocus(isOpen, onClose, dialogRef, initialFocusRef=null) {
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
export function ConfirmDialog({ dialog, onClose }) {
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
export function StudentPicker({ students, value, onChange, placeholder='-- 选择学员 --', showBal=true }) {
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

export function mediaSrc(value, fallbackBase='photos') {
    const raw = String(value || '').trim();
    if (!raw) return '';
    if (raw.startsWith('media:')) {
        const id = raw.slice(6);
        const slug = window.STUDIOSAAS_TENANT_SLUG || new URLSearchParams(location.search).get('tenant') || '';
        return `/s/${encodeURIComponent(slug)}/v1/media/${encodeURIComponent(id)}`;
    }
    return `/${fallbackBase}/${encodeURIComponent(raw)}`;
}

export function portfolioImgSrc(studentId, item) {
    if (item?.mediaUrl) return item.mediaUrl;
    const filename = item?.filename || '';
    if (String(filename).startsWith('media:')) return mediaSrc(filename, 'portfolio');
    return `/portfolio/img/${encodeURIComponent(studentId)}/${encodeURIComponent(filename)}`;
}

/* S3: 列表网格用 360px 缩略图（v1 媒体路由 ?thumb=1），灯箱/打印仍用原图 */
export function portfolioThumbSrc(studentId, item) {
    const src = portfolioImgSrc(studentId, item);
    if (src.includes('/v1/media/')) return mediaVariantSrc(src, 'thumb');
    return src;
}

/** Add an explicit safe media derivative without discarding signed query data. */
export function mediaVariantSrc(src, variant) {
    const url = new URL(src, window.location.origin);
    url.searchParams.delete('thumb');
    url.searchParams.set('variant', variant);
    return `${url.pathname}${url.search}${url.hash}`;
}

/** Responsive candidates for canonical media; legacy imported files stay unchanged. */
export function portfolioSrcSet(studentId, item) {
    const src = portfolioImgSrc(studentId, item);
    if (!src.includes('/v1/media/')) return undefined;
    return `${mediaVariantSrc(src, 'thumb')} 360w, ${mediaVariantSrc(src, 'medium')} 960w, ${mediaVariantSrc(src, 'display')} 2000w`;
}

/* ═══════════════════ PHOTO AVATAR ════════════════════════════ */
export function PhotoAvatar({ photo, name, size='sm' }) {
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
export const ICON_PATHS = {
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

export function Icon({ name, className = 'w-5 h-5' }) {
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
export function PhotoUploader({ value, onChange, notify }) {
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

/* ═══════════════ STUDENT TIMELINE（E1）════════════════════════════ */
/* One chronological answer to "这孩子这半年发生了什么" — enrolment, credits,
   invoices, reports in a single stream. Read-only; every money entry links to
   the invoice centre. Fetched lazily on first expand so the profile modal
   stays as fast as before for people who never open it. */
export function StudentTimeline({ api, studentId, openInvoice }) {
    const [state, setState] = useState({loading: false, data: null, error: null});
    const KIND = {
        registration: ['clipboard', '报名'], approval: ['check', '批准建档'],
        topup: ['card', '充值'], refund: ['card', '退款'], deduction: ['calendar', '扣课'],
        invoice: ['money', '发票'], payment: ['money', '收款'],
        credit_note: ['money', '贷记'], report: ['star', '成长报告'],
    };
    const load = async () => {
        setState(s => ({...s, loading: true, error: null}));
        try {
            const d = await api(`/students/${encodeURIComponent(studentId)}/timeline?limit=50`);
            setState({loading: false, data: d, error: null});
        } catch (e) {
            setState({loading: false, data: null, error: e.message});
        }
    };
    return (
        <details className="border border-gray-200 rounded-2xl overflow-hidden"
                 onToggle={e => { if (e.currentTarget.open && !state.data && !state.loading) load(); }}>
            <summary className="px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2">
                <Icon name="clock" className="w-4 h-4"/>学员时间线
                <span className="font-normal text-gray-400 text-xs">报名 · 课时 · 账务 · 报告，一条流水</span>
            </summary>
            <div className="divide-y divide-gray-50">
                {state.loading && <p className="px-4 py-3 text-xs text-gray-400">加载中…</p>}
                {state.error && (
                    <div className="px-4 py-3 text-xs text-red-500 flex items-center gap-3">
                        <span>时间线加载失败：{state.error}</span>
                        <button onClick={load} className="min-h-[44px] px-2.5 rounded-lg border border-red-200 font-bold">重试</button>
                    </div>
                )}
                {state.data && (state.data.entries || []).length === 0 &&
                    <p className="px-4 py-3 text-xs text-gray-400">还没有可显示的记录。</p>}
                {state.data && (state.data.entries || []).map((entry, i) => {
                    const [icon, label] = KIND[entry.kind] || ['info', entry.kind];
                    return (
                        <div key={i} className="px-4 py-2.5 flex items-baseline gap-2 text-sm">
                            <span className="inline-flex items-center gap-1.5 font-bold text-gray-700 flex-shrink-0">
                                <Icon name={icon} className="w-3.5 h-3.5 text-gray-400"/>{label}
                            </span>
                            <span className="text-xs text-gray-600 truncate">{entry.title}</span>
                            {Number.isFinite(entry.credits) && entry.credits !== null && entry.credits !== 0 &&
                                <span className={`text-xs font-bold ${entry.credits > 0 ? 'text-indigo-700' : 'text-gray-500'}`}>{entry.credits > 0 ? `+${entry.credits}` : entry.credits} 课时</span>}
                            {Number.isFinite(entry.amountCents) && entry.amountCents !== null && entry.amountCents !== 0 &&
                                <span className="text-xs font-bold text-emerald-700">${(entry.amountCents / 100).toFixed(2)}</span>}
                            {entry.invoiceId && openInvoice &&
                                <button onClick={() => openInvoice(entry.invoiceId)}
                                        className="text-xs font-bold text-indigo-600 underline decoration-dotted">查看单据</button>}
                            <span className="ml-auto text-xs text-gray-400 tabular-nums flex-shrink-0">{String(entry.ts).slice(0, 10)}</span>
                        </div>
                    );
                })}
                {state.data?.hasMore && <p className="px-4 py-2 text-[11px] text-gray-400">只显示最近 50 条；更早的记录见充值/上课记录与账单中心。</p>}
            </div>
        </details>
    );
}

/* ═══════════════ MAINTENANCE PANEL（体检/邮件/备份恢复）═══════════ */
/* confirm/notify come from the app shell so this panel uses the same dialog
   as the other 20+ call sites instead of the browser's native ones. */
export function MaintSection({ onRestored, renewTh, saveRenewTh, confirm, notify }) {
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
export function LoginScreen({ onLogin }) {
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
            /* `error` 是机器码，`message` 才是给人看的那句。以前先读 error，
               于是登录框上出现过一个孤零零的 `not_found` —— 而服务端同时
               送来的 "Unknown tenant." 被丢掉了，没人知道该去查什么。 */
            else { setErr(d.message || d.error || '密码错误'); setPw(''); }
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

