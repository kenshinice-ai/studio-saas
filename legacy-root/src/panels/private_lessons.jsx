/* 一对一循环课与补课额度。
 *
 * 这一块和班课不同的地方，全在「这节课没上」之后发生的事。班课缺席是一条
 * 考勤记录；1v1 缺席要当场回答两个问题 —— 这节还收不收钱、老师这节还算不算
 * 课酬 —— 外加第三个：家长欠不欠一次补课。三个答案不一样，所以界面上也分开
 * 显示，取消完把服务端算出来的结果原样告诉操作的人。
 *
 * 提前量由后端按工作室时钟算，不从浏览器传。一台慢一天的客户端会把「临时
 * 取消」变成「提前取消」，那是真金白银。
 *
 * 组件不 import Icon —— --bundle 之后主文件的标识符在这里不存在，
 * tests/test_cms_panels.py 会拦这件事。
 */
import { fmtApiDate } from './_shared.jsx';

const { useState, useEffect, useCallback, useMemo } = React;

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六'];

const STATUS_LABEL = { active: '进行中', paused: '暂停', ended: '已结束' };

/* 取消归因决定钱的走向，所以必须是操作的人明确选的，不能从登录身份推断 ——
   大部分取消是前台替打电话来的家长录进去的。 */
const WHO = [
    { value: 'student', label: '学员请假' },
    { value: 'studio', label: '工作室停课' },
];

const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

export function PrivateLessonsPanel({ api, showToast, canWrite, canWritePolicy, students }) {
    const [view, setView] = useState('upcoming');
    const [series, setSeries] = useState([]);
    const [occurrences, setOccurrences] = useState([]);
    const [credits, setCredits] = useState([]);
    const [policy, setPolicy] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');
    const [busy, setBusy] = useState(false);
    const [cancelling, setCancelling] = useState(null);
    const [creating, setCreating] = useState(false);

    const range = useMemo(() => {
        const start = new Date();
        const end = new Date();
        end.setDate(end.getDate() + 13);
        return { start: iso(start), end: iso(end) };
    }, []);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const [s, o, c, p] = await Promise.all([
                api('/scheduling/series'),
                api(`/scheduling/occurrences?start=${range.start}&end=${range.end}`),
                api('/scheduling/credits'),
                api('/scheduling/policy'),
            ]);
            setSeries(s.series || []);
            setOccurrences(o.occurrences || []);
            setCredits(c.credits || []);
            setPolicy(p.policy || null);
            setError('');
        } catch (e) {
            /* 读路径不把界面打挂：403 只说明这个套餐没开通，不是故障。 */
            setError(e.status === 403
                ? '这个工作室尚未开通一对一循环课。'
                : `加载失败：${e.message}`);
        } finally {
            setLoading(false);
        }
    }, [api, range.start, range.end]);

    useEffect(() => { load(); }, [load]);

    async function cancelOne(form) {
        setBusy(true);
        try {
            const res = await api('/scheduling/occurrences/cancel', {
                method: 'POST',
                body: JSON.stringify({
                    seriesId: form.seriesId,
                    onDate: form.onDate,
                    cancelledBy: form.cancelledBy,
                    reason: form.reason,
                }),
            });
            /* 把服务端的三个答案原样念回来。操作的人需要知道这一下到底
               做了什么决定，而不是一句「已取消」。 */
            showToast(
                `已记录：${res.chargeable ? '照常计费' : '不计费'}、`
                + `${res.counts_for_pay ? '老师照付课酬' : '不计课酬'}`
                + `${res.grants_credit ? '、已发一次补课额度' : ''}`,
                'success');
            setCancelling(null);
            await load();
        } catch (e) {
            showToast(e.message || '取消失败', 'error');
        } finally { setBusy(false); }
    }

    async function undo(exceptionId) {
        setBusy(true);
        try {
            await api(`/scheduling/exceptions/${exceptionId}`, { method: 'DELETE' });
            showToast('已撤销这次变更，随之发出的补课额度也已作废', 'success');
            await load();
        } catch (e) {
            showToast(e.message || '撤销失败', 'error');
        } finally { setBusy(false); }
    }

    async function createSeries(form) {
        setBusy(true);
        try {
            await api('/scheduling/series', {
                method: 'POST',
                body: JSON.stringify({
                    studentId: form.studentId,
                    weekday: Number(form.weekday),
                    startTime: form.startTime,
                    durationMinutes: Number(form.durationMinutes),
                    startsOn: form.startsOn,
                    room: form.room,
                    note: form.note,
                }),
            });
            showToast('循环课已排好', 'success');
            setCreating(false);
            await load();
        } catch (e) {
            showToast(e.message || '排课失败', 'error');
        } finally { setBusy(false); }
    }

    async function useCredit(credit) {
        const onDate = window.prompt(
            `给 ${credit.student_name} 安排补课，日期（YYYY-MM-DD）：`, range.start);
        if (!onDate) return;
        setBusy(true);
        try {
            await api(`/scheduling/credits/${credit.id}/consume`, {
                method: 'POST', body: JSON.stringify({ onDate }),
            });
            showToast('补课已登记，这次额度已用掉', 'success');
            await load();
        } catch (e) {
            showToast(e.message || '登记失败', 'error');
        } finally { setBusy(false); }
    }

    if (loading) return <div className="p-6 text-sm text-gray-500">正在加载一对一课程…</div>;
    if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

    const liveCredits = credits.filter(c => !c.is_expired);
    const expiredCredits = credits.filter(c => c.is_expired);

    return (
        <div className="space-y-3">
            <div className="grid grid-cols-3 gap-3">
                <Stat label="循环课" value={String(series.filter(s => s.status === 'active').length)}
                      sub={`${series.filter(s => s.status === 'paused').length} 个暂停中`} />
                <Stat label="未来两周" value={String(occurrences.filter(o => !o.exception_kind).length)}
                      sub={`${occurrences.filter(o => o.exception_kind).length} 次有变更`} />
                <Stat label="待补课" value={String(liveCredits.length)} tone={liveCredits.length ? 'warn' : undefined}
                      sub={expiredCredits.length ? `${expiredCredits.length} 次已过期` : '没有欠着的'} />
            </div>

            <div className="flex flex-wrap items-center gap-2">
                {[['upcoming', '未来两周'], ['series', '循环课'], ['credits', '补课额度'], ['policy', '请假规则']]
                    .map(([key, label]) => (
                        <button key={key} type="button" onClick={() => setView(key)}
                                className={`min-h-[44px] px-4 rounded-xl text-sm font-bold border ${
                                    view === key
                                        ? 'bg-indigo-600 text-white border-indigo-600'
                                        : 'bg-white text-gray-700 border-gray-200'}`}>
                            {label}
                        </button>
                    ))}
                {canWrite && view === 'series' && (
                    <button type="button" onClick={() => setCreating(true)}
                            className="ml-auto min-h-[44px] px-4 rounded-xl bg-emerald-600 text-white text-sm font-bold">
                        排一节循环课
                    </button>
                )}
            </div>

            {view === 'upcoming' && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    {!occurrences.length && (
                        <p className="px-4 py-6 text-sm text-gray-400 text-center">
                            未来两周没有一对一课程。排课后会自动展开到这里，节假日与暂停会自动跳过。
                        </p>
                    )}
                    <div className="divide-y divide-gray-50">
                        {occurrences.map(o => (
                            <div key={`${o.series_id}-${o.on_date}`}
                                 className={`px-4 py-3 flex flex-wrap items-center gap-3 ${o.exception_kind ? 'bg-gray-50/60' : ''}`}>
                                <span className="text-sm font-bold text-gray-700 w-28 flex-shrink-0">
                                    {fmtApiDate(o.on_date)}
                                </span>
                                <span className="text-sm text-gray-500 w-14 flex-shrink-0">{o.start_time}</span>
                                <span className={`text-sm flex-1 min-w-0 truncate ${o.exception_kind ? 'text-gray-400 line-through' : 'text-gray-800 font-bold'}`}>
                                    {o.student_name}
                                    {o.teacher_name && <span className="ml-2 text-xs font-normal text-gray-400">{o.teacher_name}</span>}
                                </span>
                                {o.exception_kind ? (
                                    <span className="flex items-center gap-2 flex-shrink-0">
                                        {/* 两个答案分开显示。合成一句「已取消」就等于
                                            把这张表存在的理由丢掉。 */}
                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${o.chargeable ? 'bg-amber-50 text-amber-700' : 'bg-gray-100 text-gray-500'}`}>
                                            {o.chargeable ? '计费' : '不计费'}
                                        </span>
                                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${o.counts_for_pay ? 'bg-emerald-50 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                                            {o.counts_for_pay ? '算课酬' : '不算课酬'}
                                        </span>
                                        {canWrite && (
                                            <button type="button" onClick={() => undo(o.exception_id)} disabled={busy}
                                                    className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-600 disabled:opacity-50">
                                                撤销
                                            </button>
                                        )}
                                    </span>
                                ) : canWrite ? (
                                    <button type="button"
                                            onClick={() => setCancelling({ seriesId: o.series_id, onDate: o.on_date, name: o.student_name })}
                                            className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700 flex-shrink-0">
                                        请假 / 停课
                                    </button>
                                ) : null}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {view === 'series' && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    {!series.length && (
                        <p className="px-4 py-6 text-sm text-gray-400 text-center">
                            还没有一对一循环课。排一节后，它每周自动出现，不用每周手动加。
                        </p>
                    )}
                    <div className="divide-y divide-gray-50">
                        {series.map(s => (
                            <div key={s.id} className="px-4 py-3 flex flex-wrap items-center gap-3">
                                <span className="text-sm font-bold text-gray-800 flex-1 min-w-0 truncate">
                                    {s.student_name}
                                </span>
                                <span className="text-sm text-gray-500">
                                    {WEEKDAYS[s.weekday]} {s.start_time} · {s.duration_minutes} 分钟
                                </span>
                                {s.teacher_name && <span className="text-xs text-gray-400">{s.teacher_name}</span>}
                                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${s.status === 'active' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>
                                    {STATUS_LABEL[s.status]}
                                    {s.status === 'paused' && s.paused_to && ` 至 ${fmtApiDate(s.paused_to)}`}
                                </span>
                                {canWrite && (
                                    <SeriesActions series={s} api={api} showToast={showToast}
                                                   onDone={load} busy={busy} setBusy={setBusy} />
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {view === 'credits' && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                    {!credits.length && (
                        <p className="px-4 py-6 text-sm text-gray-400 text-center">
                            没有欠着的补课。提前请假产生的额度会出现在这里。
                        </p>
                    )}
                    <div className="divide-y divide-gray-50">
                        {credits.map(c => (
                            <div key={c.id} className="px-4 py-3 flex flex-wrap items-center gap-3">
                                <span className="text-sm font-bold text-gray-800 flex-1 min-w-0 truncate">
                                    {c.student_name}
                                </span>
                                <span className="text-xs text-gray-400">
                                    {fmtApiDate(c.earned_from_date)} 请假产生
                                </span>
                                {/* 过期是读的时候算出来的，不是存的 —— 存了就得靠夜里
                                    的定时任务维护，而两次运行之间它是错的。 */}
                                <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${c.is_expired ? 'bg-gray-100 text-gray-500' : 'bg-amber-50 text-amber-700'}`}>
                                    {c.is_expired ? '已过期'
                                        : c.expires_on ? `${fmtApiDate(c.expires_on)} 前有效` : '不过期'}
                                </span>
                                {canWrite && !c.is_expired && (
                                    <button type="button" onClick={() => useCredit(c)} disabled={busy}
                                            className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                                        安排补课
                                    </button>
                                )}
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {view === 'policy' && policy && (
                <PolicyEditor policy={policy} api={api} showToast={showToast}
                              canWrite={canWritePolicy} onSaved={load} />
            )}

            {cancelling && (
                <CancelDialog target={cancelling} policy={policy} busy={busy}
                              onClose={() => setCancelling(null)} onSubmit={cancelOne} />
            )}
            {creating && (
                <CreateDialog students={students} busy={busy}
                              onClose={() => setCreating(false)} onSubmit={createSeries} />
            )}
        </div>
    );
}

function Stat({ label, value, sub, tone }) {
    const accent = tone === 'warn' ? 'text-amber-700' : 'text-gray-800';
    return (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
            <p className="text-xs text-gray-400">{label}</p>
            <p className={`text-2xl font-bold ${accent}`}>{value}</p>
            {sub && <p className="text-xs text-gray-400 mt-0.5">{sub}</p>}
        </div>
    );
}

function SeriesActions({ series, api, showToast, onDone, busy, setBusy }) {
    async function setStatus(status) {
        setBusy(true);
        try {
            await api(`/scheduling/series/${series.id}`, {
                method: 'PATCH', body: JSON.stringify({ status }),
            });
            showToast(status === 'ended' ? '这门循环课已结束' : `已${status === 'paused' ? '暂停' : '恢复'}`, 'success');
            await onDone();
        } catch (e) {
            showToast(e.message || '操作失败', 'error');
        } finally { setBusy(false); }
    }

    return (
        <span className="flex items-center gap-2 flex-shrink-0">
            {series.status === 'active' ? (
                <button type="button" onClick={() => setStatus('paused')} disabled={busy}
                        className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700 disabled:opacity-50">
                    暂停
                </button>
            ) : (
                <button type="button" onClick={() => setStatus('active')} disabled={busy}
                        className="min-h-[44px] px-3 rounded-lg border border-emerald-200 bg-white text-xs font-bold text-emerald-700 disabled:opacity-50">
                    恢复
                </button>
            )}
            <button type="button" onClick={() => setStatus('ended')} disabled={busy}
                    className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-500 disabled:opacity-50">
                结束
            </button>
        </span>
    );
}

function CancelDialog({ target, policy, busy, onClose, onSubmit }) {
    const [cancelledBy, setCancelledBy] = useState('student');
    const [reason, setReason] = useState('');

    return (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm">
            <div className="bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 space-y-4">
                <div>
                    <p className="text-lg font-bold text-gray-800">{target.name} · {fmtApiDate(target.onDate)}</p>
                    <p className="text-sm text-gray-500 mt-1">
                        这一下决定三件事：还收不收钱、老师算不算课酬、要不要补一次课。
                    </p>
                </div>

                <div className="space-y-2">
                    {WHO.map(w => (
                        <label key={w.value}
                               className={`flex items-center gap-3 min-h-[44px] px-4 rounded-xl border cursor-pointer ${
                                   cancelledBy === w.value ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200'}`}>
                            <input type="radio" name="cancelledBy" value={w.value}
                                   checked={cancelledBy === w.value}
                                   onChange={() => setCancelledBy(w.value)} />
                            <span className="text-sm font-bold text-gray-800">{w.label}</span>
                        </label>
                    ))}
                </div>

                {policy && (
                    <p className="text-xs text-gray-400">
                        {cancelledBy === 'studio'
                            ? `工作室停课：${policy.studio_cancel_chargeable ? '照常计费' : '不计费'}，老师照付课酬。`
                            : `提前 ${policy.notice_hours} 小时以上算按时请假，`
                              + `${policy.makeup_credit_on_notice ? '发补课额度' : '不发补课额度'}；`
                              + `临时请假${policy.late_absence_chargeable ? '照常计费' : '不计费'}。`}
                        {' '}提前量由系统按工作室时钟计算。
                    </p>
                )}

                <textarea value={reason} onChange={e => setReason(e.target.value)} rows={2}
                          placeholder="备注（选填）：家长来电说明的原因"
                          className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm" />

                <div className="flex gap-2">
                    <button type="button" onClick={onClose} disabled={busy}
                            className="flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50">
                        取消
                    </button>
                    <button type="button" disabled={busy}
                            onClick={() => onSubmit({ ...target, cancelledBy, reason })}
                            className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
                        确认记录
                    </button>
                </div>
            </div>
        </div>
    );
}

function CreateDialog({ students, busy, onClose, onSubmit }) {
    const [form, setForm] = useState({
        studentId: '', weekday: '1', startTime: '16:00',
        durationMinutes: '30', startsOn: iso(new Date()), room: '', note: '',
    });
    const set = (key) => (e) => setForm(f => ({ ...f, [key]: e.target.value }));

    return (
        <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm">
            <div className="bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 space-y-3">
                <p className="text-lg font-bold text-gray-800">排一节循环课</p>
                <p className="text-sm text-gray-500">每周同一时间自动出现，节假日与暂停会自动跳过。</p>

                <label className="block text-xs text-gray-400">学员
                    <select value={form.studentId} onChange={set('studentId')}
                            className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                        <option value="">请选择</option>
                        {(students || []).map(s => (
                            <option key={s.id} value={s.id}>{s.name}</option>
                        ))}
                    </select>
                </label>

                <div className="grid grid-cols-2 gap-3">
                    <label className="block text-xs text-gray-400">星期
                        <select value={form.weekday} onChange={set('weekday')}
                                className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                            {WEEKDAYS.map((label, i) => <option key={i} value={i}>{label}</option>)}
                        </select>
                    </label>
                    <label className="block text-xs text-gray-400">开始时间
                        <input type="time" value={form.startTime} onChange={set('startTime')}
                               className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                    </label>
                    <label className="block text-xs text-gray-400">时长（分钟）
                        <input type="number" min="5" step="5" value={form.durationMinutes}
                               onChange={set('durationMinutes')}
                               className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                    </label>
                    <label className="block text-xs text-gray-400">起始日期
                        <input type="date" value={form.startsOn} onChange={set('startsOn')}
                               className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                    </label>
                </div>

                <div className="flex gap-2 pt-1">
                    <button type="button" onClick={onClose} disabled={busy}
                            className="flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50">
                        取消
                    </button>
                    <button type="button" onClick={() => onSubmit(form)} disabled={busy || !form.studentId}
                            className="flex-1 min-h-[44px] rounded-xl bg-emerald-600 text-white text-sm font-bold disabled:opacity-50">
                        排课
                    </button>
                </div>
            </div>
        </div>
    );
}

function PolicyEditor({ policy, api, showToast, canWrite, onSaved }) {
    const [form, setForm] = useState(policy);
    const [busy, setBusy] = useState(false);

    async function save() {
        setBusy(true);
        try {
            await api('/scheduling/policy', { method: 'PUT', body: JSON.stringify(form) });
            showToast('请假规则已更新', 'success');
            await onSaved();
        } catch (e) {
            showToast(e.message || '保存失败', 'error');
        } finally { setBusy(false); }
    }

    const toggle = (key) => () => setForm(f => ({ ...f, [key]: !f[key] }));

    return (
        <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-4">
            <p className="text-sm text-gray-500">
                这四项决定一次请假的后果。它们是四个独立的开关，不是一个 ——
                临时请假通常「收钱」且「照付老师」，工作室停课通常两者相反。
            </p>

            <div className="grid sm:grid-cols-2 gap-3">
                <label className="block text-xs text-gray-400">提前多少小时算按时请假
                    <input type="number" min="0" value={form.notice_hours} disabled={!canWrite}
                           onChange={e => setForm(f => ({ ...f, notice_hours: Number(e.target.value) }))}
                           className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm disabled:bg-gray-50" />
                </label>
                <label className="block text-xs text-gray-400">补课额度多少天后过期（留空＝不过期）
                    <input type="number" min="1" value={form.makeup_expiry_days ?? ''} disabled={!canWrite}
                           onChange={e => setForm(f => ({
                               ...f, makeup_expiry_days: e.target.value === '' ? null : Number(e.target.value),
                           }))}
                           className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm disabled:bg-gray-50" />
                </label>
            </div>

            <div className="space-y-2">
                {[
                    ['makeup_credit_on_notice', '按时请假发一次补课额度'],
                    ['late_absence_chargeable', '临时请假照常计费'],
                    ['late_absence_pays_teacher', '临时请假老师照付课酬'],
                    ['studio_cancel_chargeable', '工作室停课照常计费'],
                ].map(([key, label]) => (
                    <label key={key}
                           className={`flex items-center gap-3 min-h-[44px] px-4 rounded-xl border ${
                               canWrite ? 'cursor-pointer' : ''} ${form[key] ? 'border-indigo-500 bg-indigo-50' : 'border-gray-200'}`}>
                        <input type="checkbox" checked={!!form[key]} disabled={!canWrite} onChange={toggle(key)} />
                        <span className="text-sm font-bold text-gray-800">{label}</span>
                    </label>
                ))}
            </div>

            {canWrite && (
                <button type="button" onClick={save} disabled={busy}
                        className="min-h-[44px] px-5 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
                    保存规则
                </button>
            )}
        </div>
    );
}
