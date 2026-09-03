/* StudioSaaS CMS application source (JSX).
 * Edit THIS file, then rebuild the browser bundle with:
 *   bash backend/scripts/build_cms.sh
 * The compiled output (backend/frontend/assets/cms-app.js) is what
 * legacy-root/index.html actually loads — do not edit it by hand.
 */

import { BillingPanel, BillingAccountPicker, isOverdue } from "./panels/billing.jsx";
import { FinancePanel } from "./panels/finance.jsx";
import { IntegrationsPanel } from "./panels/integrations.jsx";
import { BillingIdentityPanel } from "./panels/billing_identity.jsx";
import { OverdueReports } from "./panels/progress_reports.jsx";
import { FilterBar } from "./panels/filter_bar.jsx";
import { StudentProgressReports, StudentBillingAccount } from "./panels/student_reports.jsx";
import { PrivateLessonsPanel } from "./panels/private_lessons.jsx";

import { AUDIT_ACTION_ZH, BalBadge, CMS_ROUTE_SECTIONS, CMS_ROUTE_TABS, CmsNotificationCenter, ConfirmDialog, Icon } from "./components.jsx";
import { LoginScreen, MaintSection, PhotoAvatar, StudentPicker, TENANT_SLUG, Toast } from "./components.jsx";
import { auditNote, daysSince, fmtDate, mediaSrc, nowAU, parseMonthKey } from "./components.jsx";
import { portfolioImgSrc, portfolioSrcSet, readCmsRoute, tenantOwnedLogoUrl, tenantSlug, todayISO } from "./components.jsx";
import { Tabs, TabPanel, useModalFocus, v1Api } from "./components.jsx";
import { DashboardSection } from "./panels/dashboard.jsx";
import { CoursesSection, RosterSection } from "./panels/scheduling.jsx";
import { WorksSection } from "./panels/media.jsx";
import { StudentsSection, NewStudentSection, PendingSection } from "./panels/students.jsx";
import { TopupSection } from "./panels/topup.jsx";
import { LogsSection, StatsSection } from "./panels/reports.jsx";
import { StudentProfileModal } from "./panels/student_profile.jsx";

const { useState, useEffect, useMemo, useRef, useCallback } = React;

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
    const [rosterSection, setRosterSectionState] = useState(initialCmsRoute.rosterSection);
    const [routeRecordId, setRouteRecordId] = useState(initialCmsRoute.recordId);
    const [moreOpen, setMoreOpen] = useState(false);
    const [selS, setSelS] = useState(null);
    const [editP, setEditP] = useState(false);
    const [studentProfileTab, setStudentProfileTab] = useState('profile');
    const [busy, setBusy] = useState(false);
    const [conn, setConn] = useState(false);
    const [connErr, setConnErr] = useState(null);
    /* UI-02: a 403 is not a connection failure. Kept separate from connErr so
       the guard can render a permission screen instead of the retry screen —
       retrying a support-gate denial can never succeed and the old copy told
       production users to start a local dev server. */
    const [accessDenied, setAccessDenied] = useState(null);   // {code, message}
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
        else if (next.tab === 'roster' && next.rosterSection && next.rosterSection !== 'checkin') params.set('section', next.rosterSection);
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
        const patch = {tab: next, recordId: nextRecordId};
        /* 一个「去把固定课表建起来」的入口不该先落在今日名单上。分区照样过
           CMS_ROUTE_SECTIONS 的白名单：调用方写错了就落回 fallback，不会把
           一个不存在的分区写进地址栏。 */
        if (next === 'roster') {
            const scope = CMS_ROUTE_SECTIONS.roster;
            const section = scope.allowed.includes(options.section) ? options.section : scope.fallback;
            setRosterSectionState(section);
            patch.rosterSection = section;
        }
        syncCmsRoute(patch, !!options.replace);
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
    const setRosterSection = useCallback((nextSection) => {
        setRosterSectionState(nextSection);
        setTabState('roster');
        setShowSettings(false);
        syncCmsRoute({tab:'roster', rosterSection:nextSection});
    }, [syncCmsRoute]);

    useEffect(() => {
        const onPopState = () => {
            const next = readCmsRoute();
            setTabState(next.tab);
            setPendingTabState(next.pendingTab);
            setSettingsSectionState(next.settingsSection);
            setRosterSectionState(next.rosterSection);
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
    /* 设置页曾经也是弹窗，这里原本有一次 useModalFocus 守着它。条件是
       `showSettings && tab !== 'settings'` —— 而 showSettings 只在
       tab==='settings' 时为真，所以它从来没有激活过。覆盖层那条渲染分支
       已经删了，这一行跟着删。 */
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
    const [rfAmountTouched, setRfAmountTouched] = useState(false);
    const [rfReason, setRfReason] = useState('');
    const [rfSourceId, setRfSourceId] = useState('');
    const [refundSources, setRefundSources] = useState([]);
    const [refundSourcesBusy, setRefundSourcesBusy] = useState(false);
    const [refundSourceError, setRefundSourceError] = useState('');
    const [rfAdjustDocuments, setRfAdjustDocuments] = useState(false);
    const [tuCr,  setTuCr]  = useState('');
    const [tuFee, setTuFee] = useState('');
    const [tuPkg, setTuPkg] = useState('');
    const [tuPay, setTuPay] = useState('微信');
    /* v10.7 settlement controls: the legacy credits-only path remains the
       default; these states only become visible for tenant money operations. */
    const [tuCreateInvoice, setTuCreateInvoice] = useState(false);
    const [tuPaymentReceived, setTuPaymentReceived] = useState(true);
    const [settlementAccounts, setSettlementAccounts] = useState([]);
    const [settlementTaxCodes, setSettlementTaxCodes] = useState([]);
    const [settlementPayerState, setSettlementPayerState] = useState({
        mode: 'student', accountId: '', createPayload: null, linkedStudentIds: [],
    });
    const [settlementPayerError, setSettlementPayerError] = useState('');
    const settlementResolvedAccountRef = useRef('');
    const settlementPayerIntentRef = useRef('');
    const settlementRequestRef = useRef({signature: '', id: ''});
    const refundRequestRef = useRef({signature: '', id: ''});

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
    /* E5: pending duplicate decision — {pid, fullName, credits, candidates[]} */
    const [dupPick, setDupPick] = useState(null);
    /* E3: receivables snapshot for the workbench. Loaded only when the
       dashboard is open for a role that can see billing — money must appear
       where the day starts, not only inside the invoice centre. */
    const [arSummary, setArSummary] = useState(null);
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
        /* 前台带 roster。后端早就给了 scheduling:write（一对一循环课、停课、
           补课），本轮又加了 attendance:write —— 但这一页不在名单里，那两个
           权限在界面上就是死的：canWriteScheduling 里的 front_desk 只在
           RosterSection 内部被消费，而前台打开 ?view=roster 会被踢回工作台。 */
        front_desk: ['dashboard','pending','roster','students','new_student','billing','topup','logs','settings'],
        /* 助教 = 老师的可见面，一个不多。ROLE_PERMISSIONS 里 STAFF ⊂ TEACHER，
           这一行是它在导航上的对应物；以前 staff 比 teacher 多出待处理、
           新建学员、账单和充值四项，正好是它不该有的那几件。 */
        staff: ['dashboard','roster','courses','students','works','logs','settings'],
    };
    const allowedTabs = roleTabs[actorRole] || ['dashboard'];
    const canManageOperations = [...ownerRoles,'manager'].includes(actorRole);
    const canExportData = [...ownerRoles,'manager'].includes(actorRole);
    const canViewFinancialAnalytics = [...ownerRoles,'manager'].includes(actorRole);
    const canWriteStudents = [...ownerRoles,'manager','front_desk'].includes(actorRole);
    const canWriteCredits = [...ownerRoles,'manager','front_desk'].includes(actorRole);
    const canUseSettlementBilling = TENANT_SLUG && ['owner','manager','front_desk','platform_super_admin','super_admin'].includes(actorRole);
    const canRegisterSettlementPayment = TENANT_SLUG && ['owner','manager','front_desk','platform_super_admin','super_admin'].includes(actorRole);
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
    /* Mirrors backend attendance:write — everyone who is in the building on
       the day. Front desk was the odd one out: it could already take a credit
       off a balance through the raw ledger route, just not through the audited
       one that records an attendance against a class date. */
    const canWriteAttendance = [...ownerRoles,'manager','teacher','staff','front_desk'].includes(actorRole);
    /* Backend grants class_bookings:review to Front Desk without granting
       schedule mutation.  Keep that distinction visible in the UI: review
       is an inbox action, not a timetable permission. */
    const canReviewBookings = [...ownerRoles,'manager','front_desk'].includes(actorRole);
    /* Mirrors backend credits:refund — refunds are owner/manager only. */
    const canRefund = [...ownerRoles,'manager'].includes(actorRole);
    const canSyncRefund = TENANT_SLUG && ['owner','manager','platform_super_admin','super_admin'].includes(actorRole);
    /* Mirrors backend portfolio:share — share-link creation is owner/manager only. */
    /* 报名与预约的提醒，跟着「谁处理它们」走。助教不再有
       registrations:* / class_bookings:review，所以也不该收到这些提醒
       —— 收到了也点不进去。 */
    const canViewCmsNotifications = ['owner','manager','front_desk','platform_super_admin','super_admin'].includes(actorRole);

    /* 一份分区清单，标签页和下面的面板都读它。两处各写一份正是「侧栏名 vs
       页面标题」那个 bug 的形状 —— 第三个元素是可见性，因为团队与数据维护
       只对能管运营的人开放。
       定义在这里而不是渲染体旁边，是因为下面那个 effect 要用它，而 effect
       必须待在 `if (!loggedIn) return <LoginScreen/>`（本文件 :3098）之上：
       那三个提前 return 之下的任何 hook，在登录前后会被调用不同的次数，
       React 直接抛 #310「渲染的 hook 比上一次多」，整页空白。 */
    const SETTINGS_SECTIONS = [
        ['account', '账号与安全', true],
        ['team', '团队与权限', canManageOperations],
        ['operational', '运营默认', canManageOperations],
        ['billing-identity', '开票信息', canManageOperations],
        ['integrations', '集成', ownerRoles.includes(actorRole)],
        ['maintenance', '数据维护', canManageOperations],
        ['workspace', '工作区链接', true],
    ];
    /* 设置 #3 的第二半。`readCmsSection` 只做结构白名单 —— 它不知道谁登录了，
       所以拦不住「这个角色看不到的分区」：manager 打开 ?section=integrations
       是一个合法的 key，却没有对应的标签，于是标签条一个都不选中、面板一个
       都不渲染，整屏是空的。可见性只有上面那张表知道，收敛就只能放在这里。
       用 replaceState 而不是 pushState：这是在纠正一个无效地址，不是一次导航。
       push 会把无效地址留在历史里，用户按一次返回就又掉回空页面。 */
    useEffect(() => {
        /* `!actorRole` 是这里最重要的一个字。角色是登录后异步取回来的，首帧是
           空字符串 —— 那一帧每个按角色开放的分区都「不可见」，于是一个完全
           合法的 ?section=integrations 会在会话回来之前就被收敛成 account，
           连 URL 一起改掉，角色到位后也救不回来。实测过：不带这个判断，
           owner 打开集成、manager 打开团队都会掉回账号页。 */
        if (tab !== 'settings' || !actorRole) return;
        const visible = SETTINGS_SECTIONS.filter(([,,ok]) => ok !== false).map(([key]) => key);
        if (!visible.length) return;
        const resolved = visible.includes(settingsSection) ? settingsSection : visible[0];
        /* 地址栏里原本写的那个值 —— 结构白名单在解析时已经把它兜底过一次，
           所以 settingsSection 看不到它。要把 ?section=乱写 从地址里清掉，
           得拿原值来比。 */
        const raw = new URLSearchParams(window.location.search || '').get('section') || 'account';
        if (resolved !== settingsSection) setSettingsSectionState(resolved);
        if (raw !== resolved) syncCmsRoute({tab:'settings', settingsSection: resolved}, true);
    }, [tab, settingsSection, actorRole, canManageOperations]);

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
        if (!canUseSettlementBilling || tab !== 'topup') return undefined;
        let alive = true;
        Promise.all([
            v1Api('/billing/accounts?limit=100').catch(() => ({accounts: []})),
            v1Api('/billing/tax-codes').catch(() => ({taxCodes: []})),
        ]).then(([accountsData, taxData]) => {
            if (!alive) return;
            setSettlementAccounts(accountsData.accounts || []);
            setSettlementTaxCodes((taxData.taxCodes || []).filter(code => code.is_active !== false));
        });
        return () => { alive = false; };
    }, [canUseSettlementBilling, tab]);

    useEffect(() => {
        if (!TENANT_SLUG || settleMode !== 'refund' || !tuStu || !canRefund) {
            setRefundSources([]);
            setRefundSourcesBusy(false);
            setRefundSourceError('');
            setRfSourceId('');
            setRfAdjustDocuments(false);
            return undefined;
        }
        let alive = true;
        setRefundSourcesBusy(true);
        setRefundSourceError('');
        v1Api(`/students/${encodeURIComponent(tuStu)}/credit-refunds`)
            .then(data => {
                if (!alive) return;
                const sources = data.sources || [];
                setRefundSources(sources);
                if (!sources.some(source => String(source.sourceTransactionId) === String(rfSourceId))) setRfSourceId('');
            })
            .catch(error => { if (alive) setRefundSourceError(`可退充值加载失败：${error.message}`); })
            .finally(() => { if (alive) setRefundSourcesBusy(false); });
        return () => { alive = false; };
    }, [settleMode, tuStu, canRefund]);

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
    /* E3: refresh the receivables card whenever the operator lands on the
       dashboard; a silent failure只清空卡片，不打扰工作台。 */
    useEffect(() => {
        if (tab !== 'dashboard' || !TENANT_SLUG || !canUseSettlementBilling) return;
        let gone = false;
        v1Api('/billing/invoices').then(d => {
            if (gone) return;
            const issued = (d.invoices || []).filter(i => i.status !== 'draft' && i.status !== 'void');
            const unpaid = issued.filter(i => Number(i.balance_cents) > 0);
            setArSummary({
                unpaidCents: unpaid.reduce((s, i) => s + Number(i.balance_cents || 0), 0),
                unpaidCount: unpaid.length,
                overdueCount: unpaid.filter(isOverdue).length,
            });
        }).catch(() => { if (!gone) setArSummary(null); });
        return () => { gone = true; };
    }, [tab, loggedIn]);

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
        setBusy(true); setConnErr(null); setAccessDenied(null);
        try {
            /* S2: session cookie is the auth — no token round-trip needed */
            const r = await fetch('/api/data', {credentials:'include'});
            if (r.status === 401) { setLoggedIn(false); setBusy(false); return; }
            if (r.status === 403) {
                const body = await r.json().catch(() => ({}));
                setAccessDenied({code: body.error || 'forbidden', message: body.message || ''});
                setBusy(false); return;
            }
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

    /* 作品管理接上共享筛选栏。这一页此前没有任何筛选，只有一个「最多显示最近
       50 条」的硬上限 —— 作品一多，想找某个学员的某件作品就只能靠滚动。
       用 FilterBar 而不是再写一遍：账单和课酬已经在用它，而「清除筛选」这类
       东西每重写一次就多一份会各自漂的实现。 */
    const [worksQuery, setWorksQuery] = useState('');
    const [worksBucket, setWorksBucket] = useState('all');
    const worksIsShared = (item) => Boolean(item.public || item.visibility === 'shared');
    const worksBuckets = useMemo(() => {
        const consented = ({student}) => student.publicationConsent?.status === 'confirmed';
        return [
            {key:'all',      label:'全部',   count: portfolioEntries.length},
            {key:'shared',   label:'已公开', count: portfolioEntries.filter(({item}) => worksIsShared(item)).length},
            {key:'private',  label:'未公开', count: portfolioEntries.filter(({item}) => !worksIsShared(item)).length},
            {key:'noconsent',label:'待授权', count: portfolioEntries.filter(e => !consented(e)).length},
        ];
    }, [portfolioEntries]);
    const worksVisible = useMemo(() => {
        const needle = worksQuery.trim().toLowerCase();
        return portfolioEntries.filter(({student, item}) => {
            if (worksBucket === 'shared'    && !worksIsShared(item)) return false;
            if (worksBucket === 'private'   &&  worksIsShared(item)) return false;
            if (worksBucket === 'noconsent' && student.publicationConsent?.status === 'confirmed') return false;
            if (!needle) return true;
            return [student.name, item.title, item.note].some(v => String(v || '').toLowerCase().includes(needle));
        });
    }, [portfolioEntries, worksQuery, worksBucket]);

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
        /* 服务端会拒绝窗口外的日期，但错误是一句英文原文；而「明天」它会放行，
           于是一节还没上的课被静默扣掉一个课时。在这里先拦，用中文说清楚。 */
        if (!checkInWindow.ok) { showToast(`${fmtDate(rDate)}：${checkInWindow.reason}`, 'warn'); return; }
        const student = db.students.find(s=>s.id===sid);
        if (!student||student.balance<=0) { showToast(`${sname} 课时余额不足`, 'error'); return; }
        /* 余额检查挪到确认之前：先问一个注定会失败的问题，比不问更糟。 */
        if (checkInWindow.future) {
            /* 这里曾经是全仓库最后一个裸 window.confirm —— 同一个后台，两套
               对话框：这一句由操作系统画，别的确认由 ConfirmDialog 画。
               改走同一个 helper 之后只剩一套。

               文案也换成算术。「确定现在就扣 1 课时吗？」问不出新信息——
               对方已经按了「签到并扣 1 课时」，知道要扣。真正该给的是结果：
               扣完还剩多少。 */
            const before = Number(student.balance) || 0;
            confirm(
                `${checkInWindow.reason}（${fmtDate(rDate)}）。${sname} 的余额会从 ${before} 变成 ${Math.max(0, before - 1)} 课时。`,
                () => runCheckIn(sid, sname, student),
                {confirmText: `仍然签到 · ${before} → ${Math.max(0, before - 1)}`},
            );
            return;
        }
        return runCheckIn(sid, sname, student);
    };

    /* checkIn 的其余部分。拆出来只是为了让上面的未来日期确认能走回调式的
       ConfirmDialog —— 它不像 window.confirm 那样同步返回一个布尔值。 */
    const runCheckIn = async (sid, sname, student) => {
        if (busy) return;
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
        /* 同一条原则：说结果，不说「确定吗」。撤销会把课时退回去，那就把
           退回后的数字写出来。 */
        const undoBefore = Number((db.students.find(s=>s.id===sid)||{}).balance) || 0;
        confirm(`撤销 ${sname} 在 ${fmtDate(rDate)} 的签到，扣掉的 1 课时会退回 TA 的余额：${undoBefore} → ${undoBefore + 1} 课时。\n\n这条撤销会写进操作日志，可以随时再签一次。`, async () => {
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
    /* 选中这一天的考勤本身。以前「谁已经签到了」是从 db.logs 里筛出来的，
       而那份日志是全局 `ORDER BY occurred_at DESC LIMIT 500`（tenant.py）——
       一间每月流水超过五百条的工作室，四十多天前的签到就掉出了窗口，界面
       于是显示「待上课」，再按一次批量签到就是第二次扣课时。按日期查考勤
       没有这个窗口，`/attendance?date=` 本来就支持（students.py:1363）。 */
    const [rosterAttendance, setRosterAttendance] = useState(null);
    useEffect(() => {
        if (!TENANT_SLUG) { setRosterAttendance(null); return undefined; }
        let cancelled = false;
        (async () => {
            try {
                const d = await v1Api(`/attendance?date=${encodeURIComponent(rDate)}&limit=500`);
                if (!cancelled) setRosterAttendance(d.attendance || []);
            } catch (e) {
                /* 查不到就退回日志推导：宁可少标几个「已签到」（会被服务端
                   的重复校验或操作者自己拦下），也不要在这里假装知道。 */
                if (!cancelled) setRosterAttendance(null);
            }
        })();
        return () => { cancelled = true; };
    }, [rDate]);

    const rosterDone = useMemo(() => {
        const done = new Set();
        if (rosterAttendance) {
            rosterAttendance.forEach(a => { if (!a.reversed_at) done.add(a.student_id); });
            return done;
        }
        const m = String(rDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
        const prefix = m ? `${m[3]}/${m[2]}/${m[1]}` : '__none__';
        db.logs.forEach(l => {
            if (l.action === '上课签到' && String(l.date).startsWith(prefix)) {
                if (l.studentId) done.add(l.studentId);
                else { const s = db.students.find(x => x.name === l.studentName); if (s) done.add(s.id); }
            }
        });
        return done;
    }, [rosterAttendance, db.logs, db.students, rDate]);

    /* 服务端只接受 [今天-90, 今天+1] 的签到日期（students.py 的 check-in）。
       界面以前在任何日期都照常渲染那颗蓝色主按钮：选下周三点下去，弹回一句
       英文原文；选明天则**静默成功**，为一节还没上的课扣掉一个课时。 */
    const checkInWindow = useMemo(() => {
        const picked = new Date(`${rDate}T00:00:00`);
        const midnight = new Date(); midnight.setHours(0, 0, 0, 0);
        const days = Math.round((picked - midnight) / 86400000);
        if (Number.isNaN(days)) return {ok: true, future: false, reason: ''};
        /* 服务端接受 [今天-90, 今天+1]，那个 +1 是刻意留的跨时区余量，不是
           这里该推翻的东西。要修的是「静默」：明天这一天它会**成功**，为一节
           还没上的课扣掉课时，而界面一个字都不说。所以 +1 天仍然放行，但要
           当面问一次；窗口之外才拦。 */
        if (days > 1) return {ok: false, future: true, reason: '这一天还没到，不能签到扣课时'};
        if (days < -90) return {ok: false, future: false, reason: '超过 90 天的课程不能再补签'};
        return {ok: true, future: days > 0, reason: days > 0 ? '这是明天的课，现在签到就会先扣掉课时' : ''};
    }, [rDate]);

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
        /* Reception-scoped since v10.13, like the PATCH beside it. Teachers and
           assistants get a 403 here, which is the answer, not a fault — the
           same shape as loadAuditEvents below. Asking regardless of role keeps
           this correct on the first frame, when `actorRole` has not arrived. */
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
        /* Opening the editor is not enough: it renders inside the 固定课表
           block, which is collapsed and (since the roster reorder) sits at the
           end of the page. Without this the button reads as a no-op. */
        const block = document.getElementById('rosterSchedules');
        if (block) {
            block.open = true;
            requestAnimationFrame(() => block.scrollIntoView({behavior:'smooth', block:'start'}));
        }
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
        /* The heading has to agree with the date beside it: this gets pasted
           into a group chat, where nobody can see which day was selected. */
        const heading = rDate===todayISO() ? '今日上课' : '上课名单';
        copyText(`【${heading} ${lines.length} 人 - ${fmtDate(rDate)}】\n${lines.join('\n')}`,'日报已复制到剪贴板');
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
        if (!checkInWindow.ok) { showToast(`${fmtDate(rDate)}：${checkInWindow.reason}`, 'warn'); return; }
        if (!elig.length) { showToast(already ? '这一天排课的学员均已签到 ✓' : '这一天没有可签到/消课的学员', 'warn'); return; }
        /* 日期写在第一句。这句话以前从「今日」开头，而它读的是任意选中日期——
           排下周三的课时顺手点了批量签到，扣的是那一天的课时，确认框里却一个
           日期字都没有。 */
        const futureWarning = checkInWindow.future ? `⚠ ${checkInWindow.reason}。` : '';
        confirm(`批量签到确认 · ${fmtDate(rDate)}：${futureWarning}排课 ${ids.length} 人；已签到 ${already} 人；余额不足 ${insufficient} 人；已归档 ${archived} 人；本次实际执行 ${elig.length} 人。`, async () => {
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
                        } catch(e) { failed.push(`${s.name}（${e.message||'原因未知'}）`); }
                    }
                    await load();
                    const succeeded=elig.length-failed.length;
                    /* 失败要带原因。只报「失败 3 人（张三、李四、王五）」，
                       操作者拿不到任何可以据以行动的东西。 */
                    if (failed.length) showToast(`批量签到完成：成功 ${succeeded} 人，失败 ${failed.length} 人 —— ${failed.join('；')}`, 'warn');
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
        /* What the page shows for this day is manual ∪ timetable. Saving only
           `db.rosters[rDate]` produced a template missing every student the
           weekly schedule contributed — with no sign anything was left out. */
        const ids = dayIds.filter(id => db.students.some(s => s.id===id && !s.archived));
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
        /* Deliberately the MANUAL list, not `dayIds`. A student the weekly
           timetable places on this date has no daily_roster_entries row, and
           `entry.id` is what unlocks the per-row time, the 待上课/补课 status,
           the 1-on-1 flag and 移出本日课程安排. Applying a template is the only
           remaining way to give them one — addToRoster returns early on
           `dayIds.includes(rPick)`. Deduplicating against the union here read
           as tidier and silently removed the last path: the toast said
           「模板学员均已在当前排课中」 and nothing was created. The list itself
           dedupes through a Set, so no row appears twice. */
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
        /* Start the footprint at enrolment. A student who joined in July was
           charted from March, so four flat months opened a document whose whole
           job is to show a child growing — the chart said "inactive" about a
           period before they had arrived. Never fewer than two columns, so the
           row still reads as a chart rather than a single bar. */
        const monthsSinceJoin = joinDate
            ? (now.getFullYear()-joinDate.getFullYear())*12 + (now.getMonth()-joinDate.getMonth()) + 1
            : 6;
        const monthSpan = Math.max(2, Math.min(6, monthsSinceJoin));
        const months = Array.from({length:monthSpan},(_,i)=>{ const d=new Date(now.getFullYear(),now.getMonth()-(monthSpan-1)+i,1);
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
        /* The generated paragraph read the four numbers back to the parent in an
           exclamation-mark voice and called their child TA. It sat directly under
           a caption a teacher had actually written — and next to a real sentence,
           a template does not read as neutral, it reads as the studio having
           nothing to say. So the block is now the teacher's or it is absent:
           blank space says "no note this time", boilerplate says something worse.
           `shareMsg` still carries a fallback because the copy-to-clipboard button
           needs text; `teacherNote` is what the printed report shows. */
        const teacherNote = String(s.reportNote || s.teacherNote || '').trim();
        const shareMsg = isNew
            ? `欢迎 ${s.name} 加入 ${reportStudioName}！学习旅程刚刚启程，期待记录每一份成长与快乐。`
            : `${s.name} 在 ${reportStudioName} 已经学习了 ${days} 天，累计上课 ${checkins.length} 次，完成${workNoun} ${port.length} 份。`;

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
        /* The report opens in a NEW WINDOW, so cms-i18n.js — which translates the
           rendered DOM of this document — can never reach it. That is why an
           English-speaking studio still sent parents a page whose headings were
           Chinese while the artwork captions were English. The report reads the
           same language the operator is working in and emits its own chrome in
           that language. One document, one language. */
        const rlang = (()=>{ try { return localStorage.getItem('studiosaas_admin_language')==='en' ? 'en' : 'zh'; } catch(e) { return 'zh'; } })();
        const RT = rlang==='en' ? {
            htmlLang:'en', tag:'Student Growth Report',
            attended:'Lessons attended', works:'Works completed', balance:'Lessons remaining', days:'Days with us',
            footprint:(n)=>`Last ${n} months`, gallery:(n)=>`Portfolio (${n})`, note:'A note from the teacher',
            generated:(d,n)=>`Report generated ${d} · ${n}`,
            joined:(n,d,days)=>`${days} days at ${n} · joined ${d}`, welcome:(n)=>`Welcome to ${n}`,
            emptyWorks:'No works recorded yet', print:'Print / Save as PDF', copy:'Copy note', copied:'✓ Copied',
        } : {
            htmlLang:'zh', tag:'学员成长报告',
            attended:'累计上课', works:'完成作品', balance:'剩余课时', days:'陪伴天数',
            footprint:(n)=>`近 ${n} 个月上课足迹`, gallery:(n)=>`作品集（${n} 幅）`, note:'老师寄语',
            generated:(d,n)=>`报告生成于 ${d} · ${n}`,
            joined:(n,d,days)=>`已在 ${n} 成长陪伴 <b>${days}</b> 天 · 入学于 ${d}`, welcome:(n)=>`欢迎加入 ${n}`,
            emptyWorks:'暂无作品记录', print:'打印 / 存为 PDF', copy:'复制寄语', copied:'✓ 已复制寄语',
        };
        const html = `<!doctype html><html lang="${RT.htmlLang}"><head><meta charset="utf-8"/>
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
/* The report is opened into a blank window, so the browser's own print header
   and footer stamped about:blank and a timestamp across a document a parent
   receives. @page removes them and gives the sheet real paper margins.
   break-inside keeps a section from being split across two pages, which is what
   pushed a two-line teacher note onto a second sheet of its own. */
@page{size:A4;margin:12mm}
@media print{
  body{background:#fff;padding:0}
  .toolbar{display:none}
  .sheet{box-shadow:none;border-radius:0;max-width:none}
  .sec,.stats,.hero,.brandbar,.foot{break-inside:avoid;page-break-inside:avoid}
  .gallery{break-inside:auto}
  .art{break-inside:avoid;page-break-inside:avoid}
}
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
      <span class="tag">${RT.tag}</span>
      <h1>${esc(s.name)}</h1>
	      <div class="sub">${isNew ? `${esc(reportJoinText)} · 欢迎加入 ${esc(reportStudioName)}` : `已在 ${esc(reportStudioName)} 成长陪伴 <b>${days}</b> 天 · 入学于 ${fmtD(joinDate)}`}</div>
    </div>
  </div>
  <div class="stats">
    <div class="stat"><div class="v">${checkins.length}</div><div class="l">${RT.attended}</div></div>
    <div class="stat"><div class="v">${port.length}</div><div class="l">${RT.works}</div></div>
    <div class="stat"><div class="v">${bal}</div><div class="l">${RT.balance}</div></div>
    <div class="stat"><div class="v">${isNew ? '—' : days}</div><div class="l">${RT.days}</div></div>
  </div>
  <div class="sec">
    <h2 className="inline-flex items-center gap-1.5"><Icon name="trend" className="w-4 h-4"/>${RT.footprint(monthSpan)}</h2>
    <div class="chart">${barsHTML}</div>
  </div>
  <div class="sec gal">
    <h2 className="inline-flex items-center gap-1.5"><Icon name="image" className="w-4 h-4"/>${RT.gallery(port.length)}</h2>
    <div class="gallery">${portHTML}</div>
  </div>
  ${teacherNote ? `<div class="sec">
    <h2 className="inline-flex items-center gap-1.5"><Icon name="heart" className="w-4 h-4"/>${RT.note}</h2>
    <div class="msg">${esc(teacherNote)}</div>
  </div>` : ''}
  <div class="foot">
	    <div class="fslogan">${esc(reportSlogan)}</div>
	    ${RT.generated(fmtD(new Date()), esc(reportStudioName))}
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

    const settlementPaymentMethod = {'现金':'cash', '银行转账':'bank_transfer', '其他':'other', '微信':'other'};
    const nextSettlementRequestId = (signature) => {
        if (settlementRequestRef.current.signature !== signature) {
            const id = (window.crypto && window.crypto.randomUUID)
                ? window.crypto.randomUUID()
                : `settlement-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            settlementRequestRef.current = {signature, id};
        }
        return settlementRequestRef.current.id;
    };
    const setSettlementPayer = (next) => {
        const payerIntent = next.createPayload
            ? `create:${JSON.stringify(next.createPayload)}`
            : `account:${next.accountId || ''}`;
        if (settlementPayerIntentRef.current !== payerIntent) {
            settlementResolvedAccountRef.current = '';
            settlementPayerIntentRef.current = payerIntent;
        }
        setSettlementPayerState(next);
    };

    const handleTopUp = async (e) => {
        e.preventDefault();
        const fd = new FormData(e.target);
        const credits = parseInt(fd.get('credits'), 10);
        const fee = parseFloat(fd.get('fee')) || 0;
        const amountCents = Math.round(fee * 100);
        const tuRemark = (fd.get('tuRemark') || '').trim();
        const createInvoice = Boolean(TENANT_SLUG && canUseSettlementBilling && tuCreateInvoice);
        const paymentReceived = Boolean(createInvoice && canRegisterSettlementPayment && tuPaymentReceived && amountCents > 0);
        const taxCode = settlementTaxCodes.find(code => code.is_default) || settlementTaxCodes[0] || null;
        if (!tuStu) { showToast('请选择学员', 'error'); return; }
        if (isNaN(credits) || credits <= 0) { showToast('请输入有效课时数', 'error'); return; }
        if (fee < 0) { showToast('金额无效', 'error'); return; }
        if (createInvoice && amountCents <= 0) { showToast('金额为 0 时不能创建发票，请关闭“同时创建发票”。', 'error'); return; }

        const payerIntent = settlementPayerState.createPayload
            ? `create:${JSON.stringify(settlementPayerState.createPayload)}`
            : `account:${settlementPayerState.accountId || ''}`;
        const signature = JSON.stringify({
            studentId: tuStu, credits, amountCents, packageId: tuPkg || null,
            paymentMethod: settlementPaymentMethod[tuPay] || 'other', note: tuRemark,
            createInvoice, paymentReceived, taxCodeId: taxCode?.id || null, payerIntent,
        });
        const requestId = nextSettlementRequestId(signature);
        const s0 = db.students.find(x => x.id === tuStu);
        const payerName = settlementPayerState.accountId
            ? (settlementAccounts.find(a => String(a.id) === String(settlementPayerState.accountId))?.name || '已选付款方')
            : (settlementPayerState.createPayload?.name || '待创建付款方');
        const grossLabel = `$${fee.toFixed(2)}`;
        const rateBp = Number(taxCode?.rate_bp || 0);
        const taxEstimate = amountCents > 0 ? Math.max(0, amountCents - Math.round(amountCents * 10000 / (10000 + rateBp || 10000))) : 0;
        const confirmation = createInvoice
            ? `确认 ${s0?.name || ''} 充值 ${credits} 课时，gross ${grossLabel}（预计税额 $${(taxEstimate / 100).toFixed(2)}），付款方：${payerName}；${paymentReceived ? `开票并登记已收款（${tuPay}）` : '开票但暂不登记收款'}？`
            : `确认为 ${s0?.name || ''} 充值 ${credits} 课时，实收 ${grossLabel}（${tuPay}）${fee === 0 ? '——免费充课' : ''}？`;

        const doTopUp = async () => {
            if (busy) return;
            setBusy(true);
            try {
                const s = db.students.find(x => x.id === tuStu);
                if (!s) throw new Error('学员不存在或已改变。');
                const noteStr = [`套餐: ${tuPkg || '自定义'}`, `付款: ${tuPay}`, ...(tuRemark ? [tuRemark] : [])].join(' | ');
                let settlement = null;
                if (TENANT_SLUG) {
                    if (createInvoice) {
                        let billingAccountId = settlementResolvedAccountRef.current || settlementPayerState.accountId;
                        if (!billingAccountId && settlementPayerState.createPayload) {
                            const payload = {...settlementPayerState.createPayload};
                            if (payload.studentId) delete payload.studentIds;
                            const created = await v1Api('/billing/accounts', {
                                method: 'POST', body: JSON.stringify(payload),
                            });
                            billingAccountId = String(created.account?.id || '');
                            settlementResolvedAccountRef.current = billingAccountId;
                        }
                        if (!billingAccountId) throw new Error('请选择或创建付款方。');
                        if (settlementPayerState.mode === 'custom' && settlementPayerState.linkedStudentIds.length) {
                            await v1Api(`/billing/accounts/${billingAccountId}/members`, {
                                method: 'POST', body: JSON.stringify({studentIds: settlementPayerState.linkedStudentIds}),
                            });
                        }
                        settlement = await v1Api(`/students/${s.id}/credit-settlements`, {
                            method: 'POST',
                            body: JSON.stringify({
                                requestId, credits: String(credits), amountCents,
                                paymentMethod: settlementPaymentMethod[tuPay] || 'other',
                                packageId: tuPkg || null, note: noteStr,
                                billing: {
                                    createInvoice: true, billingAccountId,
                                    taxCodeId: taxCode?.id || null, issueNow: true,
                                    paymentReceived,
                                },
                            }),
                        });
                    } else {
                        /* Every top-up uses the idempotent settlement contract.
                           The no-invoice payload is deliberately minimal: it
                           cannot create an account, tax code, issue, or payment
                           as a side effect. */
                        settlement = await v1Api(`/students/${s.id}/credit-settlements`, {
                            method: 'POST',
                            body: JSON.stringify({
                                requestId, credits: String(credits), amountCents,
                                paymentMethod: settlementPaymentMethod[tuPay] || 'other',
                                packageId: tuPkg || null, note: noteStr,
                                billing: {createInvoice: false},
                            }),
                        });
                    }
                    await load();
                } else {
                    const ns = db.students.map(x => x.id === tuStu
                        ? {...x, balance: (parseInt(x.balance, 10) || 0) + credits, lastActive: todayISO()}
                        : x);
                    const ok = await save({...db, students: ns, logs: [mkLog(s.name, '充值购课', `+${credits}`, noteStr, fee, {payMethod: tuPay, studentId: s.id}), ...db.logs]});
                    if (!ok) return;
                }
                e.target.reset();
                setTuCr(''); setTuFee(''); setTuPkg(''); setTuPay('微信'); setTuStu(null);
                setTuCreateInvoice(false); setTuPaymentReceived(true);
                setSettlementPayerState({mode: 'student', accountId: '', createPayload: null, linkedStudentIds: []});
                settlementResolvedAccountRef.current = '';
                settlementPayerIntentRef.current = '';
                const newBal = (parseInt(s.balance, 10) || 0) + credits;
                const cMsg = renderMessage('topup',
                    '{student} 您好！已为您成功充值 {credits} 课时{fee}，当前账户共 {balance} 课时。感谢您对 {studio} 的信任！',
                    {student: s.name, credits, fee: fee ? `（实收 $${fee.toFixed(2)}）` : '', balance: newBal});
                const invoiceAction = settlement?.invoiceId
                    ? {label: '查看发票', onClick: () => setTab('billing', {recordId: settlement.invoiceId})}
                    : {label: '复制充值确认（发家长）', onClick: () => copyText(cMsg, '充值确认已复制')};
                showToast(createInvoice
                    ? `${s.name} 充值 ${credits} 课时，已${paymentReceived ? '开票并登记收款' : '开票待收款'}`
                    : `${s.name} 充值 ${credits} 课时 / $${fee.toFixed(2)}`,
                    'success', invoiceAction);
            } catch (err) { showToast(`充值失败：${err.message}`, 'error'); }
            finally { setBusy(false); }
        };

        /* A4/D-03: show all money decisions before the atomic request starts. */
        confirm(confirmation, doTopUp, {confirmText: createInvoice ? '确认开票并入账' : (fee === 0 ? '确认免费充课' : '确认入账')});
    };

    const nextRefundRequestId = (signature) => {
        if (refundRequestRef.current.signature !== signature) {
            const id = (window.crypto && window.crypto.randomUUID)
                ? window.crypto.randomUUID()
                : `refund-${Date.now()}-${Math.random().toString(16).slice(2)}`;
            refundRequestRef.current = {signature, id};
        }
        return refundRequestRef.current.id;
    };

    /* E-01: both refund modes start from one selected source. The endpoint
       decides whether documents are adjusted; the old free-form adjustment
       route is no longer a refund UI path. */
    const handleRefund = async (e) => {
        e.preventDefault();
        if (!canRefund) { showToast('当前角色无退款权限', 'error'); return; }
        const credits = Number(rfCr);
        const amountCents = Math.round((parseFloat(rfAmt) || 0) * 100);
        const source = refundSources.find(item => String(item.sourceTransactionId) === String(rfSourceId));
        const s = db.students.find(x => x.id === tuStu);
        if (!s) { showToast('请选择学员', 'error'); return; }
        if (!source) { showToast('请选择一笔原充值，再继续退款', 'error'); return; }
        if (!Number.isFinite(credits) || credits <= 0) { showToast('请输入有效退课节数', 'error'); return; }
        if (credits > Number(source.availableCredits || 0)) {
            showToast(`退课节数不能超过所选原充值剩余 ${source.availableCredits} 节`, 'error'); return;
        }
        if (amountCents < 0) { showToast('退款金额无效', 'error'); return; }
        if (rfAdjustDocuments && (amountCents <= 0 || amountCents > Number(source.availableAmountCents || 0))) {
            showToast(`同步退款金额不能超过所选原充值剩余 $${(Number(source.availableAmountCents || 0) / 100).toFixed(2)}`, 'error'); return;
        }
        if (!rfReason.trim()) { showToast('请填写退款原因', 'error'); return; }
        if (rfAdjustDocuments && (!canSyncRefund || !source.syncAvailable)) {
            showToast('该充值没有完整的发票/付款桥，不能同步调整钱款单据。', 'error'); return;
        }
        const signature = JSON.stringify({
            studentId: tuStu, sourceCreditTransactionId: rfSourceId, credits,
            amountCents, paymentMethod: settlementPaymentMethod[tuPay] || 'other',
            reason: rfReason.trim(), adjustDocuments: rfAdjustDocuments,
        });
        const requestId = nextRefundRequestId(signature);
        const invoiceLabel = source.invoiceNumber || '未关联发票';
        const confirmation = rfAdjustDocuments
            ? `确认 ${s.name} 从原充值 ${invoiceLabel} 退 ${credits} 节、退款 $${(amountCents / 100).toFixed(2)}（${tuPay}），同时开具贷记单并登记付款退款？`
            : `确认 ${s.name} 从原充值 ${invoiceLabel} 退 ${credits} 节、退款 $${(amountCents / 100).toFixed(2)}（${tuPay}）？只改课时账本和现金净额，不改变发票或付款记录。`;
        confirm(confirmation, async () => {
            if (busy) return;
            setBusy(true);
            try {
                let result = null;
                if (rfAdjustDocuments) {
                    result = await v1Api(`/students/${encodeURIComponent(s.id)}/credit-refunds`, {
                        method: 'POST',
                        body: JSON.stringify({
                            requestId,
                            sourceCreditTransactionId: rfSourceId,
                            credits: String(credits), amountCents,
                            paymentMethod: settlementPaymentMethod[tuPay] || 'other',
                            reason: rfReason.trim(), billing: {adjustDocuments: true},
                        }),
                    });
                } else {
                    result = await v1Api(`/students/${encodeURIComponent(s.id)}/credit-refunds`, {
                        method: 'POST',
                        body: JSON.stringify({
                            requestId,
                            sourceCreditTransactionId: rfSourceId,
                            credits: String(credits), amountCents,
                            paymentMethod: settlementPaymentMethod[tuPay] || 'other',
                            reason: rfReason.trim(), billing: {adjustDocuments: false},
                        }),
                    });
                }
                await load();
                setRfCr(''); setRfAmt(''); setRfAmountTouched(false); setRfReason(''); setRfSourceId('');
                setRfAdjustDocuments(false); setRefundSources([]); setTuStu(null);
                const newBal = (parseFloat(s.balance) || 0) - credits;
                const cMsg = `${s.name} 您好！已为您办理退课 ${credits} 节、退款 $${(amountCents / 100).toFixed(2)}（${tuPay}），当前剩余 ${newBal} 课时。感谢您的理解与支持。`;
                const action = result?.invoiceId
                    ? {label: '查看原发票', onClick: () => setTab('billing', {recordId: result.invoiceId})}
                    : {label: '复制退款确认（发家长）', onClick: () => copyText(cMsg, '退款确认已复制')};
                showToast(rfAdjustDocuments
                    ? `${s.name} 已退款并开具贷记单 $${(amountCents / 100).toFixed(2)}`
                    : `${s.name} 退课 ${credits} 节 / 退款 $${(amountCents / 100).toFixed(2)}`,
                    'warn', action);
            } catch (err) { showToast(`退款失败：${err.message}`, 'error'); }
            finally { setBusy(false); }
        }, {danger:true, confirmText: rfAdjustDocuments ? '确认退款并开贷记单' : `确认退课 ${credits} 节`});
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
    /* E5: tenant approval with an explicit duplicate decision. existingStudentId
       null = create a new student (unchanged behaviour); an id = attach the
       registration to that student instead. Never merged automatically. */
    const approveTenant = async (pid, fullName, credits, existingStudentId) => {
        setBusy(true);
        try {
            const res = await v1Api(`/registrations/${pid}`, {
                method: 'PATCH',
                body: JSON.stringify({status: 'approved', ...(existingStudentId ? {existingStudentId} : {})}),
            });
            const newSid = existingStudentId || res.student_id || (res.registration && res.registration.student_id);
            if (credits > 0 && newSid) {
                await v1Api(`/students/${newSid}/credit-transactions`, {
                    method: 'POST',
                    body: JSON.stringify({transactionType: 'migration', amount: credits, note: '注册审批初始课时'}),
                });
            }
            await load();
            showToast(existingStudentId
                ? `${fullName} 的报名已并入既有档案`
                : `${fullName} 已批准建档，家长将收到确认邮件`);
            setApproveCredits(p => { const n={...p}; delete n[pid]; return n; });
        } catch(e) { showToast(`批准失败：${e.message}`, 'error'); }
        finally { setBusy(false); setDupPick(null); }
    };
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
                    /* E5: candidates come from the server BEFORE anything is
                       written; a failure to fetch them must not block approval
                       (the old behaviour), only skip the hint. */
                    const dc = await v1Api(`/registrations/${pid}/duplicate-candidates`).catch(() => ({candidates: []}));
                    if ((dc.candidates || []).length) {
                        setBusy(false);
                        setDupPick({pid, fullName, credits, candidates: dc.candidates});
                        return;
                    }
                    await approveTenant(pid, fullName, credits, null);
                    return;
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
    /* UI-02: permission denials get their own screen. Retrying cannot fix a
       support-gate 403, so the primary action explains the path (Super Admin →
       support session) instead of offering a doomed reconnect loop. */
    if (!conn && accessDenied) return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white p-4">
            <div className="text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full">
                <div className="flex justify-center mb-3 text-amber-400"><Icon name="warning" className="w-12 h-12"/></div>
                <h2 className="text-xl font-bold mb-3">无权访问该工作室 / Access denied</h2>
                {accessDenied.code === 'support_session_required' ? (
                    <p className="text-gray-400 text-sm mb-3 leading-relaxed">平台账号需要先在 Super Admin 控制台为该工作室开启支持会话（含原因）后才能进入。<br/>Start an audited support session for this studio from the Super Admin console first.</p>
                ) : (
                    <p className="text-gray-400 text-sm mb-3 leading-relaxed">当前账号没有访问该工作室的权限。如需协助请联系工作室负责人。<br/>This account does not have access to this studio.</p>
                )}
                {accessDenied.message && <p className="text-gray-500 text-xs bg-gray-900 p-2 rounded mb-4">{accessDenied.message}</p>}
                <button onClick={load} className="bg-indigo-600 active:bg-indigo-700 px-8 py-3 rounded-xl font-bold w-full mb-2">重新检查 / Check again</button>
                <button onClick={doLogout} className="bg-gray-700 active:bg-gray-600 px-8 py-3 rounded-xl font-bold w-full">退出登录 / Log out</button>
            </div>
        </div>
    );
    if (!conn) return (
        <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white p-4">
            <div className="text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full">
                {connErr ? (<>
                    <div className="flex justify-center mb-3 text-amber-400"><Icon name="warning" className="w-12 h-12"/></div>
                    <h2 className="text-xl font-bold mb-3">连接失败 / Connection failed</h2>
                    {TENANT_SLUG ? (
                        <p className="text-gray-400 text-sm mb-3 leading-relaxed">服务暂时不可达，请稍后重试；如持续出现请联系支持。<br/>The service is temporarily unreachable — please retry shortly.</p>
                    ) : (
                        /* Standalone edition only: the local dev hint stays accurate there. */
                        <p className="text-gray-400 text-sm mb-3 leading-relaxed">请确认终端正在运行 <code className="text-indigo-400 bg-gray-900 px-1 rounded">python3 server.py</code></p>
                    )}
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
{tab==='dashboard' && <DashboardSection {...{activityMap, actorRole, actorRoleLabel, allowedTabs, analytics, arSummary, bizStats, canViewFinancialAnalytics, canWriteAttendance, canWriteCredits, canWriteStudents, copyText, db, inactiveDays, loadSchedules, pendingCount, renderMessage, scheduleLoadError, setFilterBy, setGOpen, setGQ, setRDate, setSortBy, setSrch, setTab, setTuStu, showToast, todayCheckedCount, todayEffectiveCount}}/>}

{/* ═══ COURSES ════════════════════════════════════════════════ */}
{tab==='courses' && <CoursesSection {...{archiveCourse, busy, canManageOperations, courseEdit, courses, saveCourse, setCourseEdit, setTab}}/>}

{/* ═══ ROSTER ═════════════════════════════════════════════════ */}
{tab==='roster' && <RosterSection {...{WEEKDAYS, addToRoster, applyGroup, availRoster, batchCheckIn, busy, canExportData, canManageOperations, canWriteAttendance, canWriteScheduling, checkIn, checkInWindow, copyRosterDaily, copyRosterReminders, copyText, courses, dayIds, db, defaultClassTime, deleteGroup, deleteSchedule, groupToSchedule, grpSel, icsBusy, loadSchedules, nextOccurrence, openIcsPreview, rDate, rOneToOne, rPick, rTime, removeFromRoster, renderMessage, renewTh, restoreCancellation, rosterDone, rosterMetaFor, rosterSection, rosterSlotFor, saveCancellation, saveGroup, saveSchedule, schedCancel, schedEdit, schedOverlap, schedPick, scheduleLoadError, scheduledForDate, schedules, setGrpSel, setRDate, setROneToOne, setRPick, setRosterSection, setRTime, setSchedCancel, setSchedEdit, setSchedPick, setTab, showToast, sortedAZ, teachableMembers, tenantDisplayName, undoCheckIn, updateRosterEntry}}/>}

{/* ═══ STUDENTS ════════════════════════════════════════════════ */}
{/* ═══ WORKS ══════════════════════════════════════════════════ */}
{tab==='works' && <WorksSection {...{canWritePortfolio, portfolioEntries, setEditP, setPortUpload, setSelS, setStudentProfileTab, setTab, setWorksBucket, setWorksQuery, worksBucket, worksBuckets, worksQuery, worksVisible}}/>}

{/* ═══ STUDENTS ════════════════════════════════════════════════ */}
{tab==='students' && <StudentsSection {...{archiveSelected, busy, canManageOperations, canWriteAttendance, canWriteCredits, canWriteStudents, copySelectedReminders, copyText, exportStudentsCSV, filterBy, getTag, isStudentScheduledOn, pageStudents, preferenceRows, renderMessage, renewTh, scheduleStudentToday, selectedStudentIds, selectedStudents, setEditP, setFilterBy, setSelS, setSelectedStudentIds, setSortBy, setSrch, setStudentPage, setTab, setTuStu, sortBy, sortedFiltered, srch, studentPage, studentPageCount, toggleSelectPage, toggleSelectStudent}}/>}

{/* ═══ NEW STUDENT ════════════════════════════════════════════ */}
{tab==='new_student' && <NewStudentSection {...{busy, formPhoto, handleAddStudent, notify, preferenceProfile, setFormPhoto, setTab}}/>}

{/* ═══ PENDING ════════════════════════════════════════════════ */}
{tab==='pending' && <PendingSection {...{advanceRegistration, approveCredits, approveStudent, approveTenant, bookings, busy, canReviewBookings, db, dupPick, followUpDates, pendingCount, pendingTab, preferenceRows, rejectStudent, reviewBooking, setApproveCredits, setDupPick, setFollowUpDates, setPendingTab, setTab, showToast}}/>}

{/* ═══ TOPUP ══════════════════════════════════════════════════ */}
{tab==='billing' && (
    <BillingPanel
        api={v1Api}
        showToast={showToast}
        canIssue={canWriteCredits}
        canTakePayment={canWriteCredits}
        canExportData={canExportData}
        tenantSlug={TENANT_SLUG}
        students={sortedAZ.filter(s => !s.archived)}
        studentPicker={StudentPicker}
        accountId={routeRecordId}
        onClearAccount={()=>setTab('billing')}
    />
)}

{tab==='finance' && (
    <FinancePanel api={v1Api} showToast={showToast} />
)}

{tab==='topup' && <TopupSection {...{archivePackage, busy, canManageOperations, canRefund, canRegisterSettlementPayment, canSyncRefund, canUseSettlementBilling, db, handleRefund, handleTopUp, pkgCredits, pkgEditId, pkgName, pkgPrice, refundSourceError, refundSources, refundSourcesBusy, resetPackageEditor, rfAdjustDocuments, rfAmountTouched, rfAmt, rfCr, rfReason, rfSourceId, savePackage, setPkgCredits, setPkgEditId, setPkgName, setPkgPrice, setRfAdjustDocuments, setRfAmountTouched, setRfAmt, setRfCr, setRfReason, setRfSourceId, setSettleMode, setSettlementPayer, setSettlementPayerError, setSettlementPayerState, setTuCr, setTuCreateInvoice, setTuFee, setTuPay, setTuPaymentReceived, setTuPkg, setTuStu, settleMode, settlementAccounts, settlementPayerError, settlementPayerIntentRef, settlementPayerState, settlementResolvedAccountRef, settlementTaxCodes, sortedAZ, tuCr, tuCreateInvoice, tuFee, tuPay, tuPaymentReceived, tuPkg, tuStu}}/>}

{/* ═══ LOGS ═══════════════════════════════════════════════════ */}
{tab==='logs' && <LogsSection {...{canManageOperations, displayNote, exportLogsCSV, filteredLogs, lAct, lDateFrom, lDateTo, lPage, lSrch, lStu, logActions, logPageCount, pagedLogs, setLAct, setLDateFrom, setLDateTo, setLPage, setLSrch, setLStu, sortedAZ}}/>}

{/* ═══ STATS ══════════════════════════════════════════════════ */}
{tab==='stats' && <StatsSection {...{analytics, bizReport, exportBizCSV, exportRevenueCSV, payBreakdown, sFrom, sPeriod, sStu, sStu2, sTo, sYear, setSFrom, setSPeriod, setSStu, setSStu2, setSTo, setSYear, sortedAZ, statsData, studentStats}}/>}

{/* ═══ PROFILE MODAL ══════════════════════════════════════════ */}
{selS && <StudentProfileModal {...{accessCodeResult, archiveStudent, attHistory, busy, canPublishProgress, canUseSettlementBilling, canWriteAttendance, canWriteCredits, canWritePortfolio, canWriteProgress, canWriteStudents, consentEdit, copyText, db, editP, editPhoto, generateStudentAccessCode, handleDelete, handleUpdateStudent, isStudentScheduledOn, notify, openGrowthReport, portfolioDoDelete, preferenceProfile, preferenceRows, preferenceValue, profileDialogRef, revokeStudentAccessCode, save, savePublicationConsent, scheduleStudentToday, selS, setConsentEdit, setEditP, setEditPhoto, setPortEdit, setPortLB, setPortUpload, setSelS, setStudentProfileTab, setTab, setTuStu, showToast, studentProfileTab, tab, withdrawPublicationConsent, workNoun}}/>}


                {/* v10.2.1：这一块必须待在 <main> 里面。
                    它原本是 fixed 覆盖层，在 DOM 树里挂在哪都无所谓 —— 视口定位
                    会把它拉到该在的地方。v10.2.0 把它改成正常流之后，它就渲染在
                    主列之外了：设置内容跑到侧栏左边，主列只剩一个页脚。
                    上一版我用 JS 查过标签、面板和 aria，全对 —— 元素是对的，
                    位置是错的。查 DOM 属性查不出版面，那得看。 */}
            {/* 设置是一个页面，不是弹窗。这里以前还有一条把同一段内容渲染成
                `fixed inset-0` 覆盖层的分支 —— 它不可达：showSettings 只在
                tab==='settings' 时为真（setTab :124、setSettingsSection :139、
                popstate :150 三处都这么写，没有一条路径能让它在别的 tab 上为
                真）。那条分支和同样不可达的 useModalFocus 一起删掉了。 */}
            {showSettings && (
                <div ref={settingsDialogRef} className="anim"
                    style={{paddingTop:'env(safe-area-inset-top, 0px)', paddingBottom:'max(16px, env(safe-area-inset-bottom, 16px))'}}>
                    <div className="w-full">
                        <div className="flex justify-between items-center mb-5">
                            <h3 id="settings-page-title"
                                className="md:hidden inline-flex items-center gap-1.5 font-bold text-gray-800 text-xl">
                                <Icon name="cog" className="w-5 h-5"/>系统设置
                            </h3>
                        </div>
                        {/* 共用原语，不再手写 strip。Tabs 自带 roving tabindex 与
                            Arrow/Home/End；TabPanel 的 `if (!active) return null`
                            正是这一页需要的条件渲染。手写版用 hidden，于是「忘了写
                            hidden」的块会在七个分区里同时出现 —— 这一页六块共享内容
                            就是这么攒出来的，而漏的那块（MaintSection）连
                            role="tabpanel" 都没有，所以历次盘点都少数一个。
                            学员档案（student_profile.jsx:49）是同一对原语的既有用法。 */}
                        <Tabs idBase="settings" label="系统设置分区" className="mb-6"
                            value={settingsSection} onChange={setSettingsSection}
                            items={SETTINGS_SECTIONS.filter(([,,visible])=>visible!==false)
                                .map(([value,label])=>({value,label}))}/>
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
                        {canManageOperations && <TabPanel idBase="settings" name="team" active={settingsSection==='team'}>
                            <div>
                                <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">团队与权限</p>
                                <p className="text-xs text-gray-400 mt-0.5">Owner 管理团队与对外身份；Manager 负责日常运营与钱；Front Desk 负责报名、建档、充值与当天的排课签到；Teacher 负责课表、签到、作品与学习报告；助教是 Teacher 去掉署名权的版本，不碰钱也不碰报名。</p>
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
                                        <option value="manager">Manager 店长</option><option value="teacher">Teacher 老师</option><option value="front_desk">Front Desk 前台</option><option value="staff">Assistant 助教</option>
                                    </select>
                                </label>
                                <label className="text-xs font-bold text-gray-600">临时密码 *
                                    <input type="password" value={teamForm.temporaryPassword} onChange={e=>setTeamForm(p=>({...p,temporaryPassword:e.target.value}))}
                                        placeholder="至少 8 位" className="mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"/>
                                </label>
                                <button type="button" onClick={createTeamMember} disabled={teamBusy}
                                    className="sm:col-span-2 bg-indigo-600 text-white py-2.5 rounded-xl font-bold text-sm disabled:opacity-50">添加团队成员</button>
                            </div> : <p className="text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-xl px-3 py-2">当前角色可查看团队；只有 Owner 可以新增、停用或更改成员角色。</p>}
                        </TabPanel>}
                        {/* 修改登录密码 */}
                        <TabPanel idBase="settings" name="account" active={settingsSection==='account'}>
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
                        </TabPanel>
                        {/* 「运营默认」两组：默认上课时间由服务端持有（每台设备开新
                            排课都从同一时间起步），未到访预警天数存在本机
                            localStorage。后者以前挂在所有面板之外，于是七个分区里
                            各出现一次 —— 这次一并收进本分区。 */}
                        {canManageOperations && (
                        <TabPanel idBase="settings" name="operational" active={settingsSection==='operational'}>
                            {TENANT_SLUG && <>
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
                            </>}
                            {/* Fix ⑪: 未到访预警天数存在本机 localStorage，不随租户走 */}
                            <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">未到访预警天数</p>
                            <div className="flex gap-2">
                                {[60,90,120,180].map(d=>(
                                    <button key={d} onClick={()=>saveInactiveDays(d)}
                                        className={`flex-1 py-2 rounded-xl text-xs font-bold border ${inactiveDays===d?'bg-indigo-600 text-white border-indigo-600':'bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100'}`}>{d}天</button>
                                ))}
                            </div>
                        </div>
                        </TabPanel>
                        )}
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
                                <TabPanel idBase="settings" name="maintenance" active={settingsSection==='maintenance'}>
                                    <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">排课数据清理</p>
                                    <div className="bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 flex items-center gap-2">
                                        <span className="text-xs text-gray-500 flex-1">90天前旧排课</span>
                                        <span className={`text-xs font-bold ${oldKeys.length>0?'text-amber-600':'text-green-600'}`}>{oldKeys.length} 条</span>
                                    </div>
                                    <button onClick={cleanRosters} disabled={oldKeys.length===0}
                                        className="w-full bg-amber-50 active:bg-amber-100 disabled:opacity-40 text-amber-700 border border-amber-200 py-2.5 rounded-xl font-bold text-sm">
                                        <span className="inline-flex items-center gap-1.5"><Icon name="broom" className="w-4 h-4"/>清理旧排课</span>
                                    </button>
                                    {/* F1/F5/F6: 数据体检 + 阈值 + 每周邮件 + 备份恢复。
                                        只有根目录单店模式才有。它以前挂在所有面板
                                        之外、而且只有 id 没有 role="tabpanel" ——
                                        所以它既在七个分区里都露着，又在历次「共享块
                                        有几个」的盘点里被漏数。 */}
                                    {!TENANT_SLUG && (
                                        <MaintSection renewTh={renewTh} saveRenewTh={saveRenewTh}
                                            onRestored={()=>{ closeSettings(); load(); }}
                                            confirm={confirm} notify={notify}/>
                                    )}
                                </TabPanel>
                            );
                        })()}
                        {/* 开票信息排在集成前面：Xero 是可选的，而没有开票主体
                            身份，一张发票都开不出去。 */}
                        {canManageOperations && <TabPanel idBase="settings" name="billing-identity" active={settingsSection==='billing-identity'}>
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">开票信息</p>
                            {/* 能编辑开票主体的是持有 settings:write 的人，只有
                                owner —— PUT /billing/identity 自己就是这么判的
                                （billing.py 的 require_permission）。这里以前传的是
                                canManageOperations，于是 manager 拿到一张能填满、
                                按保存必定 403 的表单。面板本来就有只读态，
                                传对这一个布尔值就够了。 */}
                            <BillingIdentityPanel api={v1Api} showToast={showToast}
                                canManage={ownerRoles.includes(actorRole)} />
                        </TabPanel>}
                        {/* 这两块以前没有角色判断，只有 hidden。于是 teacher /
                            front_desk / staff 打开设置时，标签条只有 2 个，面板却
                            渲染了 4 个 —— 开票信息与集成都会照常挂载并发请求。
                            TabPanel 让未激活的分支 return null，结构上堵住了这个
                            洞；判断仍要补，否则一个 ?section=billing-identity
                            照样能把它挂起来。判断与 SETTINGS_SECTIONS 同源。 */}
                        {ownerRoles.includes(actorRole) && <TabPanel idBase="settings" name="integrations" active={settingsSection==='integrations'}>
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">集成</p>
                            <IntegrationsPanel api={v1Api} showToast={showToast} canManage={ownerRoles.includes(actorRole)} />
                        </TabPanel>}
                        <TabPanel idBase="settings" name="workspace" active={settingsSection==='workspace'}>
                            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">学员注册页面</p>
                            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2">
                                <span className="text-xs text-gray-500 flex-1 font-mono truncate">{window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`}</span>
                                <button type="button" onClick={()=>copyText(window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`,'链接已复制')}
                                    className="text-xs text-indigo-600 font-bold active:text-indigo-800 flex-shrink-0">复制</button>
                            </div>
                        </TabPanel>
                        {/* 共享页脚：退出登录与手机端快捷操作，属于整个设置页而不是
                            任何一个分区，所以刻意留在全部 TabPanel 之外。 */}
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

                {/* 页脚永远是内容列的最后一样东西。在设置还是覆盖层的时候，
                    它排在哪都看不出来；设置变成正常页面之后，它就夹在标签条
                    和面板中间了。 */}
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
