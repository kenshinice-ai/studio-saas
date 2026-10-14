/* Claude 起草：一个按钮和一个对话框，所有起草入口共用。
 *
 * 只起草，人确认后再发（Lee，2026-10-14）。这个对话框做四件事：选语言（约课
 * 回复还要选决定）→ 起草 → 让员工改 → 由员工自己复制、或用自己的邮件/短信
 * 应用打开。系统不发送任何东西。
 *
 * 草稿旁边列出 Claude 用到的事实；Claude 说缺的事实、草稿里对不上事实的数字
 * 和日期，都放在发送按钮上方，让人发之前一定看得到。
 *
 * 按钮只在店主打开了起草、服务器也配好了的时候出现。设置只问一次服务器，
 * 一页上几十个按钮共用同一个结果。
 */
import { Icon, useModalFocus, v1Api } from "../components.jsx";

const { useState, useEffect, useRef } = React;

let settingsPromise = null;
/** 起草设置：每次加载页面只问一次。改了设置后调用 refreshDraftingSettings()。 */
export function loadDraftingSettings() {
    if (!settingsPromise) {
        settingsPromise = v1Api('/drafting/settings').catch(() => ({ enabled: false, available: false }));
    }
    return settingsPromise;
}
export function refreshDraftingSettings() { settingsPromise = null; return loadDraftingSettings(); }

export function useDraftingReady() {
    const [ready, setReady] = useState(false);
    useEffect(() => {
        let live = true;
        loadDraftingSettings().then(s => { if (live) setReady(Boolean(s.enabled && s.available)); });
        return () => { live = false; };
    }, []);
    return ready;
}

const FACT_LABELS = {
    studio: '工作室', student_first_name: '学员', parent_name: '家长', lessons_left: '剩余课时',
    last_attended: '上次来', packages: '课包', missed_in_a_row: '连续没来', makeup_expires_on: '补课额度到期',
    missed_lesson_on: '请假那天', payer_name: '付款方', invoice_number: '发票号', amount_outstanding_aud: '未付金额 (AUD)',
    invoice_total_aud: '发票总额 (AUD)', due_date: '到期日', days_overdue: '逾期天数', how_to_pay: '付款方式',
    contact_name: '联系人', class_name: '班次', staff_note: '要点', class_date: '日期', start_time: '时间', decision: '决定',
    period_start: '周期开始', period_end: '周期结束', attendance: '出勤', lesson_notes: '课堂笔记', works: '作品',
};

function factValue(key, value) {
    if (value === null || value === undefined || value === '') return '—';
    if (key === 'lesson_notes' && Array.isArray(value)) return `${value.length} 条`;
    if (key === 'attendance' && typeof value === 'object') return `${value.attended ?? '—'} / ${value.scheduled ?? '—'}`;
    if (key === 'packages' && Array.isArray(value)) return value.length ? value.map(p => `${p.name} · ${p.lessons} · $${p.price_aud}`).join('；') : '—';
    if (key === 'how_to_pay' && typeof value === 'object') return Object.values(value).filter(Boolean).join(' · ') || '—';
    if (Array.isArray(value)) return value.join('、') || '—';
    if (typeof value === 'object') return Object.values(value).join(' · ');
    return String(value);
}

const ERROR_TEXT = {
    disabled: '起草没有打开。店主可以在「系统设置 → AI 起草」里打开。',
    unavailable: '这台服务器还没有配置起草服务。',
    limit: '这个月的起草次数已经用完。',
    busy: '同时起草的太多了，请过一分钟再试。',
    timeout: '起草超时了，请再试一次，或者直接手写。',
    unreachable: '连不上起草服务，请稍后再试，或者直接手写。',
    declined: '这一条没能起草，请直接手写。',
    needs_decision: '请先选择：批准、婉拒还是询问。',
};

/* mailto: / sms: 链接过长时会静默失败（产品页实测：中文约 140 字就打不开）。
   超出预算就先把正文复制到剪贴板，链接里只带标题。 */
const URL_BUDGET = 1500;

export function DraftButton({ kind, recordId, label = '起草', title = '用 Claude 起草', compact = false,
                              onUse = null, useLabel = '填入', copyText, className = '' }) {
    const ready = useDraftingReady();
    const [open, setOpen] = useState(false);
    if (!ready) return null;
    return (
        <>
            <button type="button" onClick={() => setOpen(true)} title={title} aria-label={compact ? title : undefined}
                className={className || `inline-flex items-center gap-1 min-h-[44px] px-3 rounded-lg border border-indigo-200 bg-white text-xs font-bold text-indigo-700 active:bg-indigo-50`}>
                <Icon name="chat" className="w-4 h-4"/>{!compact && <span>{label}</span>}
            </button>
            {open && <DraftDialog kind={kind} recordId={recordId} onClose={() => setOpen(false)}
                                  onUse={onUse} useLabel={useLabel} copyText={copyText}/>}
        </>
    );
}

function DraftDialog({ kind, recordId, onClose, onUse, useLabel, copyText }) {
    const dialogRef = useRef(null);
    useModalFocus(true, onClose, dialogRef);
    const [language, setLanguage] = useState(() => (window.CmsI18n && window.CmsI18n.language === 'en') ? 'en' : 'zh');
    const [decision, setDecision] = useState('approved');
    const [staffNote, setStaffNote] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [result, setResult] = useState(null);
    const [subject, setSubject] = useState('');
    const [body, setBody] = useState('');
    const [note, setNote] = useState('');

    async function draft() {
        setBusy(true); setError(''); setNote('');
        try {
            const data = await v1Api('/drafts', {
                method: 'POST',
                body: JSON.stringify({ kind, recordId, language, note: staffNote, ...(kind === 'booking_reply' ? { decision } : {}) }),
            });
            setResult(data);
            setSubject(data.draft.subject || '');
            setBody(data.draft.body || '');
        } catch (e) {
            setError(ERROR_TEXT[e.code] || e.message || '起草失败，请直接手写。');
        } finally { setBusy(false); }
    }

    function copy(text, msg) {
        if (copyText) copyText(text, msg);
        else if (navigator.clipboard) navigator.clipboard.writeText(text);
    }

    function openLink(scheme) {
        const recipient = result?.recipient || {};
        const full = scheme === 'mailto' ? body : (subject ? `${subject}\n${body}` : body);
        const head = scheme === 'mailto'
            ? `mailto:${encodeURIComponent(recipient.email || '')}?subject=${encodeURIComponent(subject)}&body=`
            : `sms:${(recipient.mobile || '').replace(/\s/g, '')}?&body=`;
        const encoded = encodeURIComponent(full);
        if (head.length + encoded.length > URL_BUDGET) {
            copy(full, '正文已复制');
            setNote('正文太长，链接带不下，已复制到剪贴板。请在打开的应用里粘贴。');
            window.location.href = head;
        } else {
            window.location.href = head + encoded;
        }
    }

    const facts = result?.facts || {};
    const unbacked = result?.draft?.unbacked || [];
    const missing = result?.draft?.missing || [];
    const recipient = result?.recipient || {};
    const joiner = (window.CmsI18n && window.CmsI18n.language === 'en') ? ', ' : '、';

    return (
        <div className="fixed inset-0 bg-black/50 z-[90] flex items-end sm:items-center justify-center sm:p-4" onClick={onClose}>
            <div ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="draft-dialog-title"
                 className="bg-white w-full sm:max-w-xl sm:rounded-2xl shadow-2xl max-h-[92vh] flex flex-col" onClick={e => e.stopPropagation()}>
                <div className="flex items-center justify-between px-4 py-3 border-b">
                    <h3 id="draft-dialog-title" className="text-base font-bold text-gray-900">用 Claude 起草</h3>
                    <button type="button" onClick={onClose} aria-label="关闭"
                        className="min-h-[44px] min-w-[44px] text-2xl text-gray-400 active:text-gray-700">×</button>
                </div>
                <div className="p-4 space-y-3 overflow-y-auto">
                    <p className="text-xs text-gray-500">草稿只给你看。改好之后由你自己发出去，系统不会替你发送。</p>
                    <div className="flex flex-wrap gap-2 items-center">
                        <span className="text-xs font-bold text-gray-500">语言</span>
                        {[['zh', '中文'], ['en', 'English']].map(([value, text]) => (
                            <button key={value} type="button" aria-pressed={language === value} onClick={() => setLanguage(value)}
                                className={`min-h-[44px] px-3 rounded-lg border text-xs font-bold ${language === value ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-200'}`}>{text}</button>
                        ))}
                    </div>
                    {kind === 'booking_reply' && (
                        <div className="flex flex-wrap gap-2 items-center">
                            <span className="text-xs font-bold text-gray-500">回复内容</span>
                            {[['approved', '批准'], ['declined', '婉拒'], ['question', '询问']].map(([value, text]) => (
                                <button key={value} type="button" aria-pressed={decision === value} onClick={() => setDecision(value)}
                                    className={`min-h-[44px] px-3 rounded-lg border text-xs font-bold ${decision === value ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-600 border-gray-200'}`}>{text}</button>
                            ))}
                        </div>
                    )}
                    <label className="block text-xs font-bold text-gray-500">想说的要点（选填）
                        <textarea value={staffNote} onChange={e => setStaffNote(e.target.value)} maxLength={300} rows={2}
                            placeholder={kind === 'booking_reply' ? '例如：问孩子几岁、以前有没有学过' : '例如：提一下下周起换教室'}
                            className="mt-1 w-full p-3 border border-gray-200 rounded-xl text-sm"/>
                        <span className="block mt-1 font-normal text-gray-400">这里写的内容会和其他事实一起交给 Claude。</span>
                    </label>
                    <button type="button" onClick={draft} disabled={busy}
                        className="w-full min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:bg-gray-300">
                        {busy ? '正在起草…' : (result ? '重新起草' : '起草')}
                    </button>
                    {error && <p role="alert" className="text-sm text-red-700 bg-red-50 border border-red-200 rounded-xl px-3 py-2">{error}</p>}
                    {result && (
                        <>
                            {(missing.length > 0 || unbacked.length > 0) && (
                                <div role="status" className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2 space-y-1">
                                    {missing.length > 0 && <p><span className="font-bold mr-1">Claude 缺少：</span><span>{missing.join(joiner)}</span></p>}
                                    {unbacked.length > 0 && <p><span className="font-bold mr-1">这些数字或日期不在系统数据里，请核对：</span><span>{unbacked.join(joiner)}</span></p>}
                                </div>
                            )}
                            {!onUse && (
                                <label className="block text-xs font-bold text-gray-500">标题
                                    <input value={subject} onChange={e => setSubject(e.target.value)}
                                        className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"/>
                                </label>
                            )}
                            <label className="block text-xs font-bold text-gray-500">正文
                                <textarea value={body} onChange={e => setBody(e.target.value)} rows={8}
                                    className="mt-1 w-full p-3 border border-gray-200 rounded-xl text-sm leading-relaxed"/>
                            </label>
                            <details className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2">
                                <summary className="cursor-pointer text-xs font-bold text-gray-500 select-none min-h-[44px] flex items-center">Claude 用到的事实</summary>
                                <dl className="pt-2 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
                                    {Object.entries(facts).map(([key, value]) => (
                                        <React.Fragment key={key}>
                                            <dt className="text-gray-400">{FACT_LABELS[key] || key}</dt>
                                            <dd className="text-gray-700 break-words">{factValue(key, value)}</dd>
                                        </React.Fragment>
                                    ))}
                                </dl>
                            </details>
                            {note && <p role="status" className="text-xs text-indigo-700">{note}</p>}
                            <div className="flex flex-wrap gap-2">
                                {onUse ? (
                                    <button type="button" onClick={() => { onUse(body); onClose(); }}
                                        className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold">{useLabel}</button>
                                ) : (
                                    <>
                                        <button type="button" onClick={() => copy(subject ? `${subject}\n\n${body}` : body, '草稿已复制')}
                                            className="flex-1 min-h-[44px] rounded-xl border border-gray-200 text-sm font-bold text-gray-700">复制</button>
                                        {recipient.email && <button type="button" onClick={() => openLink('mailto')}
                                            className="flex-1 min-h-[44px] rounded-xl border border-indigo-200 text-sm font-bold text-indigo-700">用邮件打开</button>}
                                        {recipient.mobile && <button type="button" onClick={() => openLink('sms')}
                                            className="flex-1 min-h-[44px] rounded-xl border border-indigo-200 text-sm font-bold text-indigo-700">用短信打开</button>}
                                    </>
                                )}
                            </div>
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}

/** 系统设置 → AI 起草。只有店主看得到、改得了。
 *
 * 打开这个开关，等于工作室替家长接受：起草时，学员的名、相关的数字和日期、
 * 课堂笔记会交给 Anthropic 处理。所以开关旁边先把这件事说清楚，并链接到
 * 隐私政策那一节。 */
export function DraftingSettings({ showToast }) {
    const [state, setState] = useState(null);
    const [voice, setVoice] = useState('');
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        let live = true;
        refreshDraftingSettings().then(s => { if (live) { setState(s); setVoice(s.voice || ''); } });
        return () => { live = false; };
    }, []);

    if (!state) return null;

    async function save(changes, message) {
        setBusy(true);
        try {
            const next = await v1Api('/drafting/settings', { method: 'PATCH', body: JSON.stringify(changes) });
            setState(current => ({ ...current, ...next }));
            refreshDraftingSettings();
            showToast(message, 'success');
        } catch (e) {
            showToast(`保存失败：${e.message}`, 'error');
        } finally { setBusy(false); }
    }

    return (
        <div className="space-y-3">
            <p className="text-xs font-bold text-gray-500 uppercase tracking-wide">AI 起草</p>
            <p className="text-sm text-gray-700">打开后，成长报告、工作台的例外、逾期发票和约课申请旁边会出现「起草」按钮。Claude 只写草稿，员工改完自己发出去，系统不会替你发送任何消息。</p>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 space-y-1">
                <p className="font-bold">打开之前请知道</p>
                <p>起草时，学员的名（不含姓）、与这条消息有关的数字和日期、课堂笔记，会交给 Anthropic 公司的 AI 模型 Claude 处理，处理可能在澳大利亚以外。电话、邮箱和住址不会发送。Anthropic 不用这些内容训练模型，最多保留 30 天后删除。</p>
                <p>打开即表示你已告知学员和家长这一点。详见{' '}<a className="underline" href="/customer-resources/Privacy_Policy.html#ai-drafting" target="_blank" rel="noopener">隐私政策「用 AI 起草消息」</a>。</p>
            </div>
            {!state.available && <p className="text-xs text-gray-500">这台服务器还没有配置起草服务；打开后按钮也不会出现。</p>}
            <div className="flex items-center gap-3">
                <button type="button" role="switch" aria-checked={state.enabled} disabled={busy}
                    onClick={() => save({ enabled: !state.enabled }, state.enabled ? 'AI 起草已关闭' : 'AI 起草已打开')}
                    className={`min-h-[44px] px-4 rounded-xl text-sm font-bold border ${state.enabled ? 'bg-indigo-600 text-white border-indigo-600' : 'bg-white text-gray-700 border-gray-300'}`}>
                    {state.enabled ? '已打开 · 点此关闭' : '打开 AI 起草'}
                </button>
                <span className="text-xs text-gray-500"><span className="mr-1">本月已起草</span><span>{state.usedThisMonth} / {state.monthlyLimit}</span></span>
            </div>
            <label className="block text-xs font-bold text-gray-500">我们说话的方式（选填）
                <textarea value={voice} onChange={e => setVoice(e.target.value)} maxLength={500} rows={3}
                    placeholder="例如：亲切、简洁，称呼家长「您」。落款：前台小王"
                    className="mt-1 w-full p-3 border border-gray-200 rounded-xl text-sm"/>
            </label>
            <button type="button" disabled={busy || voice === (state.voice || '')} onClick={() => save({ voice }, '已保存')}
                className="min-h-[44px] px-4 rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-40">保存说话方式</button>
        </div>
    );
}
