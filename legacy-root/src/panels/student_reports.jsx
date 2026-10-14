/* 学员档案里的三块：成长报告的撰写与发布、这个孩子由谁付账，以及给家长的日历订阅。
 *
 * 报告写在学员档案里，而不是一个独立的「报告」页面 —— 这条在 v10.1 的界面
 * 方案里论证过：写报告和「谁的报告还没写」是两个问题，后者是待处理收件箱里
 * 的工作清单，前者需要的是孩子本人的档案。老师写评语的时候要看着出勤和课堂
 * 笔记，那些就在这一页上。
 *
 * 所以这个组件把 content 里的证据摊开放在评语框旁边，而不是让老师对着一个
 * 空白输入框回忆一个学期。后端 /students/<id>/progress-reports 一次返回
 * content 和 teacher_comment，就是为了不让这一页有「评语已到、证据未到」的
 * 中间态。
 *
 * 这里不用 <Icon>：--bundle 之后每个文件是独立模块作用域，cms-app.jsx 里的
 * Icon 在这边是未定义标识符，而 JSX 里一个未定义的组件不是空白一块，是整个
 * React 树抛错白屏。tests/test_cms_panels.py 现在会替我们抓这件事。
 */
import { aud, fmtApiDate } from './_shared.jsx';
import { DraftButton } from './drafting.jsx';

const { useState, useEffect, useCallback } = React;

/** 期间的默认值：上一个自然月。老师九月初写的是八月。 */
function lastMonth() {
    const now = new Date();
    const end = new Date(now.getFullYear(), now.getMonth(), 0);
    const start = new Date(end.getFullYear(), end.getMonth(), 1);
    const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    return { start: iso(start), end: iso(end) };
}

export function StudentProgressReports({ api, studentId, studentName, canWrite, canPublish, showToast }) {
    const [reports, setReports] = useState(null);
    const [openId, setOpenId] = useState(null);
    const [draft, setDraft] = useState('');
    const [busy, setBusy] = useState(false);
    const [period, setPeriod] = useState(lastMonth);

    const load = useCallback(async () => {
        try {
            const res = await api(`/students/${studentId}/progress-reports`);
            setReports(res.reports || []);
        } catch (e) {
            /* 没有这项权利的租户读不到，这不是错误，只是这一块不显示。 */
            setReports([]);
        }
    }, [api, studentId]);

    useEffect(() => { load(); }, [load]);

    if (reports === null) return null;

    async function createDraft() {
        if (!period.start || !period.end) { showToast('请先选择周期', 'error'); return; }
        setBusy(true);
        try {
            const res = await api('/progress-reports', {
                method: 'POST',
                body: JSON.stringify({ studentId, periodStart: period.start, periodEnd: period.end }),
            });
            showToast('已按这个周期整理出草稿', 'success');
            await load();
            setOpenId(res.report?.id || null);
            setDraft('');
        } catch (e) {
            showToast(e.message || '整理失败', 'error');
        } finally { setBusy(false); }
    }

    async function saveComment(report) {
        setBusy(true);
        try {
            await api(`/progress-reports/${report.id}`, { method: 'PATCH', body: JSON.stringify({ teacherComment: draft }) });
            showToast('评语已保存', 'success');
            await load();
        } catch (e) {
            showToast(e.message || '保存失败', 'error');
        } finally { setBusy(false); }
    }

    async function publish(report) {
        /* 先落盘再发布：发布会冻结这份报告，未保存的评语会连同这次点击一起
         * 丢掉，而界面上看起来像是发布成功了。 */
        if (draft !== (report.teacher_comment || '')) await saveComment(report);
        setBusy(true);
        try {
            await api(`/progress-reports/${report.id}/publish`, { method: 'POST' });
            showToast('已发布给家长', 'success');
            setOpenId(null);
            await load();
        } catch (e) {
            showToast(e.message || '发布失败', 'error');
        } finally { setBusy(false); }
    }

    return (
        <div className="border border-amber-100 rounded-2xl overflow-hidden">
            <div className="bg-amber-50 px-4 py-3 flex items-center justify-between gap-2">
                <p className="inline-flex items-center gap-1.5 text-sm font-bold text-amber-800">
                    成长报告
                    <span className="font-normal text-amber-500 text-xs">({reports.length} 份)</span>
                </p>
            </div>

            {canWrite && (
                <div className="px-4 py-3 bg-white border-b border-gray-100 flex flex-wrap items-end gap-2">
                    <label className="text-xs text-gray-400">
                        周期起
                        <input type="date" value={period.start} onChange={e => setPeriod(p => ({ ...p, start: e.target.value }))}
                            className="block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm text-gray-800" />
                    </label>
                    <label className="text-xs text-gray-400">
                        周期止
                        <input type="date" value={period.end} onChange={e => setPeriod(p => ({ ...p, end: e.target.value }))}
                            className="block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm text-gray-800" />
                    </label>
                    <button onClick={createDraft} disabled={busy}
                        className="min-h-[44px] px-4 rounded-xl bg-amber-600 text-white text-sm font-bold disabled:opacity-50">
                        整理这一段
                    </button>
                </div>
            )}

            {!reports.length && (
                <p className="px-4 py-6 text-sm text-gray-400 text-center">
                    还没有报告。选好周期点「整理这一段」，出勤、课堂笔记会自动填进草稿，你只需要写评语。
                </p>
            )}

            <div className="divide-y divide-gray-50">
                {reports.map(r => {
                    const open = openId === r.id;
                    const published = r.status === 'published';
                    const content = r.content || {};
                    const att = content.attendance || null;
                    return (
                        <div key={r.id}>
                            <button
                                onClick={() => { setOpenId(open ? null : r.id); setDraft(r.teacher_comment || ''); }}
                                className="w-full min-h-[44px] px-4 py-3 flex items-center justify-between gap-3 text-left active:bg-gray-50">
                                <span className="text-sm font-bold text-gray-700">
                                    {fmtApiDate(r.period_start)} – {fmtApiDate(r.period_end)}
                                </span>
                                <span className="flex items-center gap-2 flex-shrink-0">
                                    {r.teacher_name && <span className="text-xs text-gray-400">{r.teacher_name}</span>}
                                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${published ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                                        {published ? '已发布' : '草稿'}
                                    </span>
                                </span>
                            </button>

                            {open && (
                                <div className="px-4 pb-4 space-y-3 bg-gray-50/60">
                                    {/* 出勤来自 daily_roster_entries，课堂笔记来自
                                        attendance_sessions。不用日排课的工作室
                                        前者是空的，于是「应到 0、已到 0」会和下面
                                        三条上课记录同屏出现 —— 这份东西是给家长看的，
                                        一个说了假话的数字比没有这个数字糟得多。
                                        服务层对出勤率已经是这个判断，这里把它
                                        延伸到计数本身。 */}
                                    {att && Number(att.scheduled) > 0 && (
                                        <div className="grid grid-cols-3 gap-2">
                                            {[['应到', att.scheduled], ['已到', att.attended], ['出勤率', att.ratePercent == null ? '—' : `${att.ratePercent}%`]]
                                                .map(([label, value]) => (
                                                    <div key={label} className="bg-white p-3 rounded-xl border border-gray-100">
                                                        <p className="text-xs text-gray-400">{label}</p>
                                                        <p className="font-bold text-gray-800">{value}</p>
                                                    </div>
                                                ))}
                                        </div>
                                    )}

                                    {Array.isArray(content.lessons) && content.lessons.length > 0 && (
                                        <div className="bg-white rounded-xl border border-gray-100 divide-y divide-gray-50 max-h-48 overflow-y-auto">
                                            {content.lessons.map((l, i) => (
                                                <div key={i} className="px-3 py-2 text-sm">
                                                    <span className="text-xs text-gray-400 mr-2">{fmtApiDate(l.class_date)}</span>
                                                    <span className="text-gray-700">{l.note}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}

                                    {published ? (
                                        <div className="bg-white p-3 rounded-xl border border-emerald-100">
                                            <p className="text-xs text-emerald-700 font-bold mb-1">老师评语 · 已冻结</p>
                                            <p className="text-sm text-gray-700 whitespace-pre-wrap">{r.teacher_comment}</p>
                                        </div>
                                    ) : canWrite ? (
                                        <div>
                                            <textarea value={draft} onChange={e => setDraft(e.target.value)} rows={4}
                                                placeholder="上面的数字是证据，这段话才是报告本身。写给家长看。"
                                                className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm text-gray-800" />
                                            <div className="flex flex-wrap gap-2 mt-2">
                                                <button onClick={() => saveComment(r)} disabled={busy}
                                                    className="min-h-[44px] px-4 rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50">
                                                    保存草稿
                                                </button>
                                                {/* Claude 按这一周期的出勤和课堂笔记起草；老师改完再保存。
                                                    起草读的是已保存的报告内容，不是这个输入框。 */}
                                                <DraftButton kind="report_comment" recordId={r.id} label="让 Claude 起草评语"
                                                    onUse={text => setDraft(text)}
                                                    useLabel={draft.trim() ? '填入评语（替换现有内容）' : '填入评语'}/>
                                                {canPublish && (
                                                    <button onClick={() => publish(r)} disabled={busy || !draft.trim()}
                                                        className="min-h-[44px] px-4 rounded-xl bg-emerald-600 text-white text-sm font-bold disabled:opacity-50">
                                                        发布给家长
                                                    </button>
                                                )}
                                            </div>
                                            {!draft.trim() && canPublish && (
                                                <p className="text-xs text-gray-400 mt-1.5">写完评语才能发布 —— 后端也是这么拦的。</p>
                                            )}
                                        </div>
                                    ) : (
                                        <p className="text-sm text-gray-400">这份草稿由 {r.teacher_name || '任课老师'} 撰写。</p>
                                    )}
                                </div>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}

/** 这个孩子由谁付账、这个账户还欠多少。 */
export function StudentBillingAccount({ api, studentId, onOpenBilling }) {
    const [accounts, setAccounts] = useState(null);

    useEffect(() => {
        let live = true;
        api(`/billing/accounts?studentId=${encodeURIComponent(studentId)}`)
            .then(res => { if (live) setAccounts(res.accounts || []); })
            .catch(() => { if (live) setAccounts([]); });
        return () => { live = false; };
    }, [api, studentId]);

    /* 没接账单、或这个孩子还没归到任何账户 —— 两种都不该在档案里堆一块空白。 */
    if (!accounts || !accounts.length) return null;

    return (
        <div className="space-y-2">
            {accounts.map(a => (
                <button key={a.id} onClick={() => onOpenBilling && onOpenBilling(a.id)}
                    className="w-full min-h-[44px] bg-gray-50 p-4 rounded-2xl border border-gray-100 flex items-center justify-between gap-3 text-left active:bg-gray-100">
                    <span>
                        <span className="text-xs text-gray-400">账单账户</span>
                        <span className="block font-bold text-gray-800">{a.name}</span>
                    </span>
                    <span className="text-right flex-shrink-0">
                        <span className="block text-xs text-gray-400">未结</span>
                        <span className={`font-bold ${a.balance_cents > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>
                            {aud(a.balance_cents)}
                        </span>
                    </span>
                </button>
            ))}
        </div>
    );
}

/** 家庭日历订阅：给家长一条链接，孩子的课出现在他们手机自带的日历里。
 *
 * 链接本身就是凭证，服务端只存它的哈希，所以只能在生成的那一刻显示一次。
 * 丢了就再生成一条、停用旧的 —— 和学员专区访问码同一个道理。
 *
 * 版本记录从 v10.0.0 起就说「家长可以订阅」，但直到这里，后台没有任何地方
 * 能发出这条链接，订阅地址在生产角色下也查不到任何一条订阅。
 */
export function StudentCalendarFeed({ api, studentId, copyText, showToast }) {
    const [subs, setSubs] = useState(null);
    const [issued, setIssued] = useState(null);
    const [busy, setBusy] = useState(false);
    const [confirmingId, setConfirmingId] = useState(null);

    const load = useCallback(async () => {
        try {
            const res = await api(`/calendar/subscriptions?studentId=${encodeURIComponent(studentId)}`);
            setSubs(res.subscriptions || []);
        } catch (e) {
            /* 没有这项权利的租户读不到，这一块就不显示。 */
            setSubs(false);
        }
    }, [api, studentId]);

    useEffect(() => { setIssued(null); setConfirmingId(null); load(); }, [load]);

    if (subs === null || subs === false) return null;

    async function issue() {
        setBusy(true);
        try {
            const res = await api('/calendar/subscriptions', {
                method: 'POST',
                body: JSON.stringify({ scope: 'student', studentId }),
            });
            setIssued({ id: res.subscription?.id, url: `${window.location.origin}${res.feedPath}` });
            await load();
        } catch (e) {
            showToast(e.message || '生成失败', 'error');
        } finally { setBusy(false); }
    }

    async function revoke(id) {
        setBusy(true);
        try {
            await api(`/calendar/subscriptions/${id}`, { method: 'DELETE' });
            setConfirmingId(null);
            /* 刚生成的那条被停用了，就别再把一条死链接摆在「请交给家长」的框里。 */
            if (issued && issued.id === id) setIssued(null);
            showToast('订阅链接已停用', 'success');
            await load();
        } catch (e) {
            showToast(e.message || '停用失败', 'error');
        } finally { setBusy(false); }
    }

    const live = subs.length > 0;
    return (
        <div className="border border-indigo-100 rounded-2xl overflow-hidden">
            <div className="bg-indigo-50 px-4 py-3 flex items-center justify-between gap-3">
                <div>
                    <p className="text-sm font-bold text-indigo-800">家庭日历订阅</p>
                    <p className="text-xs text-indigo-500 mt-0.5">家长订阅一次，孩子的课就会出现在他们手机自带的日历里；调课和停课会跟着同步。</p>
                </div>
                <span className={`text-xs font-bold px-2 py-1 rounded-full shrink-0 ${live ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                    {live ? '已启用' : '未启用'}
                </span>
            </div>
            <div className="p-4 space-y-3">
                {issued && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                        <p className="text-xs font-bold text-amber-800">仅显示一次，请现在交给家长</p>
                        <div className="flex items-start gap-3 mt-2">
                            <code className="text-xs text-gray-900 break-all flex-1">{issued.url}</code>
                            <button type="button" onClick={() => copyText(issued.url, '订阅链接已复制')}
                                className="px-3 py-2 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-800 min-h-[44px] shrink-0">复制</button>
                        </div>
                        <p className="text-xs text-amber-700 mt-2">iPhone：设置 → 日历 → 账户 → 添加账户 → 其他 → 添加已订阅的日历。Google 日历：其他日历 → 通过网址添加。</p>
                    </div>
                )}
                <p className="text-xs text-gray-500">手机日历按自己的节奏刷新，当天的临时变动不一定及时到达。</p>
                <button type="button" disabled={busy} onClick={issue}
                    className="w-full py-2.5 rounded-xl bg-indigo-600 active:bg-indigo-700 text-white text-sm font-bold disabled:bg-gray-300 min-h-[44px]">
                    {live ? '再生成一条链接' : '生成订阅链接'}
                </button>
                {live && (
                    <ul className="space-y-2" aria-label="已发出的订阅链接">
                        {subs.map(s => (
                            <li key={s.id} className="rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 flex items-center gap-3">
                                <div className="flex-1 min-w-0 text-xs text-gray-500">
                                    <p><span className="mr-1">生成于</span><span>{fmtApiDate(s.created_at)}</span></p>
                                    <p>
                                        <span className="mr-1">最近同步：</span>
                                        <span>{s.last_fetched_at ? fmtApiDate(s.last_fetched_at) : '还没有同步过'}</span>
                                    </p>
                                </div>
                                {confirmingId === s.id ? (
                                    <div className="flex gap-2 shrink-0">
                                        <button type="button" disabled={busy} onClick={() => setConfirmingId(null)}
                                            className="px-3 py-2 rounded-lg bg-white border border-gray-200 text-xs font-bold text-gray-600 min-h-[44px]">取消</button>
                                        <button type="button" disabled={busy} onClick={() => revoke(s.id)}
                                            className="px-3 py-2 rounded-lg bg-red-600 text-white text-xs font-bold min-h-[44px]">确认停用</button>
                                    </div>
                                ) : (
                                    <button type="button" disabled={busy} onClick={() => setConfirmingId(s.id)}
                                        className="px-3 py-2 rounded-lg bg-white border border-red-200 text-red-700 text-xs font-bold min-h-[44px] shrink-0">停用</button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
                {confirmingId && <p className="text-xs text-gray-500" role="status">停用后这条链接立刻失效，家长日历里的课会在下次刷新时消失。</p>}
            </div>
        </div>
    );
}
