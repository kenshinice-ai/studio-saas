/* 财务 — 钱出去的那一半，以及月底看的三张表。
 *
 * 和「账单」分开是因为它们是两个人的工作：账单是前台每天开的单，财务是
 * 老板月底收的口。这条线不是我划的，是后端权限划的 —— front_desk 有
 * billing:*，没有 payroll:* 和 reports:read，所以这个面板对前台根本不显示。
 *
 * 这个模块停在「清单」为止：算出每位老师该拿多少、依据哪几节课、导出给
 * 财务。不跑批、不生成 RCTI、不出银行文件、不算代扣与养老金。
 */

import { aud, fmtApiDate, monthRange } from "./_shared.jsx";
import { FilterBar, presetRange } from "./filter_bar.jsx";

const { useState, useEffect, useCallback, useMemo } = React;

/* 计费方式在库里是枚举，给人看的表里不该出现 per_hour。五种都要有名字，
   缺一种就会在某个工作室的课酬单上露出英文。RATE_BASES 在
   services/teaching_pay.py，两边必须同步。 */
const RATE_BASIS_LABEL = {
  per_lesson: '按节',
  per_session: '按场',
  per_hour: '按小时',
  per_head: '按人头',
  percent_of_tuition: '按学费比例',
};

/* 用工性质决定这笔钱能怎么进 Xero，所以它是个动作提示而不是标签。
   雇员的工资作为应付账单推进 Xero 会绕开薪资科目造成错账；没记录的
   拒绝猜 —— 猜错要到年末由会计在别人的账套里发现。 */
const ENGAGEMENT = {
  contractor: { label: '承包', cls: 'bg-gray-100 text-gray-600 border-gray-200', canPush: true },
  employee: { label: '仅清单', cls: 'bg-blue-50 text-blue-700 border-blue-200', canPush: false },
  unset: { label: '待补用工性质', cls: 'bg-red-50 text-red-700 border-red-200', canPush: false },
};

function Num({ label, value, sub, tone }) {
  const cls = tone === 'warn' ? 'text-amber-700' : tone === 'muted' ? 'text-gray-400' : 'text-gray-900';
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-3">
      <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`text-xl font-bold tabular-nums ${cls}`}>{value}</p>
      {sub && <p className="text-[11px] text-gray-500">{sub}</p>}
    </div>
  );
}

function PayrollView({ api, showToast, range, onRange }) {
  const [teachers, setTeachers] = useState([]);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(null);
  const [sheet, setSheet] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api(`/teaching/summary?from=${range.from}&to=${range.to}`)
      .then(d => { if (!cancelled) { setTeachers(d.teachers || []); setError(''); } })
      .catch(e => { if (!cancelled) setError(e.status === 403 ? '这个套餐未包含老师课酬清单。' : `加载失败：${e.message}`); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [api, range.from, range.to]);

  useEffect(() => {
    if (!selected) { setSheet(null); return; }
    let cancelled = false;
    api(`/teaching/timesheet?teacherUserId=${selected}&from=${range.from}&to=${range.to}`)
      .then(d => { if (!cancelled) setSheet(d); })
      .catch(e => { if (!cancelled) showToast(`课时明细加载失败：${e.message}`, 'warn'); });
    return () => { cancelled = true; };
    // showToast 故意不在依赖里：它每次渲染都是新引用，而它一被调用就会触发
    // 重渲染 —— 放进来会让一个失败的请求变成无限重试。同样的理由，billing
    // 面板那边也要照此办理。
  }, [selected, api, range.from, range.to]);

  if (loading) return <p className="text-xs text-gray-500 p-4">正在加载课酬…</p>;
  if (error) return <p className="text-xs text-red-600 p-4">{error}</p>;
  if (!teachers.length) {
    return (
      <p className="text-xs text-gray-500 p-4">
        本期还没有归集到课时。课时来自点名记录，点完名这里就会有数。
      </p>
    );
  }

  /* 老师搜索筛的是这一列，不是顶部那条 ⌘K —— 全局搜索找的是学员和功能，
     两件事混在一起，就会有人在全局框里输老师名字然后一无所获。 */
  const visible = teachers.filter(t =>
    !query.trim() || String(t.full_name || '').toLowerCase().includes(query.trim().toLowerCase()));

  const current = teachers.find(t => String(t.teacher_user_id) === selected);
  const engagement = ENGAGEMENT[current?.engagement] || ENGAGEMENT.unset;

  return (
    <div className="ui-golden-split">
      <div className="min-w-0 space-y-2">
      <FilterBar
        range={{ start: range.from, end: range.to }}
        onRange={next => onRange({ from: next.start, to: next.end })}
        query={query} onQuery={setQuery}
        searchPlaceholder="搜老师姓名"
        total={visible.length} totalNoun="位" />
      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden min-w-0">
        <div className="px-4 py-3 border-b border-gray-200 text-xs font-bold">老师</div>
        {visible.length === 0 && (
          <p className="px-4 py-6 text-xs text-gray-500">没有匹配的老师。清除筛选可以看到全部 {teachers.length} 位。</p>
        )}
        {visible.map(t => {
          const eng = ENGAGEMENT[t.engagement] || ENGAGEMENT.unset;
          return (
            <button type="button" key={t.teacher_user_id}
                    onClick={() => setSelected(String(t.teacher_user_id))}
                    className={`w-full text-left flex items-center gap-2 px-3 py-2 border-b border-gray-100 min-h-[44px]
                                ${String(t.teacher_user_id) === selected ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}>
              <span className="min-w-0">
                <span className="block text-xs font-bold truncate">{t.full_name}</span>
                <span className="block text-[11px] text-gray-500">{t.sessions} 节 · {Math.round((t.paid_minutes || 0) / 60)} 小时</span>
              </span>
              <span className="ml-auto flex items-center gap-2">
                <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${eng.cls}`}>{eng.label}</span>
                <span className="text-xs font-bold tabular-nums">{aud(t.cost_cents)}</span>
              </span>
            </button>
          );
        })}
      </div>
      </div>

      <div className="grid gap-3 min-w-0">
        {!sheet ? (
          <div className="bg-white border border-gray-200 rounded-xl p-6 text-xs text-gray-500">
            选择一位老师，查看本期课时明细。
          </div>
        ) : (
          <>
            {/* 四个数同屏 —— 老师看到一个总额时的第一句话是「我记得比这个多」。
                给一个数会引出它自己答不了的问题；给四个数，差异就有了去处。 */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <Num label="实际上了" value={sheet.summary.actual_sessions} sub="节" />
              <Num label="计入课酬" value={sheet.summary.paid_sessions} sub="节" />
              <Num label="不计课酬" value={sheet.summary.unpaid_sessions} sub="节" tone={sheet.summary.unpaid_sessions ? 'warn' : 'muted'} />
              <Num label="本期应付" value={aud(sheet.summary.amount_cents)} sub={`${Math.round((sheet.summary.paid_minutes || 0) / 60)} 小时`} />
            </div>

            <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
                <span className="text-xs font-bold">{current?.full_name} · {range.from} → {range.to}</span>
                <span className={`ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${engagement.cls}`}>
                  {engagement.label}
                </span>
              </div>
              <div className="p-4 overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-[10px] uppercase tracking-wide text-gray-500">
                      <th className="text-left py-2">日期</th>
                      <th className="text-left py-2">课程</th>
                      <th className="text-right py-2">时长</th>
                      <th className="text-left py-2">费率基准</th>
                      <th className="text-right py-2">金额</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(sheet.sessions || []).map((s, i) => (
                      /* 请假但按政策计费 → warning 底；工作室取消不计 → 降透明度。
                         同一张表里，钱的两种「不正常」看起来必须不一样。 */
                      <tr key={i} className={`border-t border-gray-100 ${s.counts_for_pay ? '' : 'opacity-50'}`}>
                        <td className="py-2">{fmtApiDate(s.occurred_on)}</td>
                        <td className="py-2">{s.course_name || '—'}</td>
                        <td className="py-2 text-right tabular-nums">{s.duration_minutes} 分钟</td>
                        <td className="py-2">{s.counts_for_pay
                          ? (RATE_BASIS_LABEL[s.rate_basis] || s.rate_basis || '未设费率')
                          : '不计课酬'}</td>
                        <td className="py-2 text-right tabular-nums">{aud(s.amount_cents)}</td>
                      </tr>
                    ))}
                    <tr className="border-t border-gray-200 font-bold">
                      <td className="py-2" colSpan={4}>本期应付</td>
                      <td className="py-2 text-right tabular-nums">{aud(sheet.summary.amount_cents)}</td>
                    </tr>
                  </tbody>
                </table>

                <div className="flex flex-wrap gap-2 items-center mt-3">
                  {engagement.canPush ? (
                    <button type="button"
                            className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold">
                      推送 Xero 应付账单
                    </button>
                  ) : (
                    <span className="text-[11px] text-gray-500">
                      {current?.engagement === 'employee'
                        ? '雇员工资不作为应付账单推送 —— 那会绕开薪资科目。导出清单交给财务走薪资流程。'
                        : '未记录用工性质，无法决定这笔钱怎么进账。请先在老师资料里选择雇员或 ABN 承包。'}
                    </span>
                  )}
                  <button type="button"
                          className="min-h-[44px] px-3 rounded-lg bg-white border border-gray-300 text-xs font-bold">
                    导出 CSV
                  </button>
                </div>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function ReportsView({ api, range }) {
  const [data, setData] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      api(`/reports/revenue?from=${range.from}&to=${range.to}`).catch(e => ({ __err: e })),
      api('/reports/receivables').catch(e => ({ __err: e })),
    ]).then(([revenue, receivables]) => {
      if (cancelled) return;
      const failed = [revenue, receivables].find(r => r && r.__err);
      if (failed) setError(failed.__err.status === 403 ? '这个套餐未包含经营报表。' : `报表加载失败：${failed.__err.message}`);
      else setData({ revenue, receivables });
    });
    return () => { cancelled = true; };
  }, [api, range.from, range.to]);

  if (error) return <p className="text-xs text-red-600 p-4">{error}</p>;
  if (!data.revenue) return <p className="text-xs text-gray-500 p-4">正在加载报表…</p>;

  const buckets = data.receivables?.buckets || {};
  const total = data.receivables?.totalCents || 0;
  const BUCKETS = [
    ['current', '未到期', ''],
    ['d1_30', '1–30 天', 'bg-amber-100 border-amber-300'],
    ['d31_60', '31–60 天', 'bg-red-100 border-red-300'],
    ['d61_90', '61–90 天', 'bg-red-100 border-red-300'],
    ['d90_plus', '90 天以上', 'bg-red-100 border-red-300'],
  ];

  return (
    <div className="grid gap-3">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Num label="本期开票" value={aud(data.revenue.totals?.gross_cents)} sub={`${data.revenue.totals?.invoices || 0} 张`} />
        <Num label="其中 GST" value={aud(data.revenue.totals?.tax_cents)} />
        <Num label="贷记冲销" value={aud(data.revenue.credits?.credited_cents)} />
        <Num label="应收未收" value={aud(total)} tone={total > 0 ? 'warn' : 'muted'} />
      </div>

      <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
        <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
          <span className="text-xs font-bold">应收账龄</span>
          <span className="ml-auto text-[11px] text-gray-500">每个数字背后的发票都在下面的清单里</span>
        </div>
        <div className="p-4 grid gap-1.5">
          {BUCKETS.map(([key, label, cls]) => {
            const cents = buckets[key] || 0;
            const pct = total > 0 ? Math.round((cents / total) * 100) : 0;
            return (
              <div key={key} className="grid items-center gap-2 text-xs"
                   style={{ gridTemplateColumns: '80px 1fr 84px' }}>
                <span>{label}</span>
                {/* 条形而不是饼图：要回答的是「哪一档最多」和「有没有 90 天以上」，
                    长度对这两个问题都比角度好读。 */}
                <span className="h-4 rounded bg-gray-100 border border-gray-200 overflow-hidden">
                  <span className={`block h-full rounded border ${cls || 'bg-blue-100 border-blue-300'}`}
                        style={{ width: `${Math.max(pct, cents > 0 ? 2 : 0)}%` }} />
                </span>
                <span className="text-right tabular-nums">{aud(cents)}</span>
              </div>
            );
          })}
        </div>
      </div>

      {(data.revenue.byKind || []).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 text-xs font-bold">收入构成</div>
          <div className="p-4 overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-[10px] uppercase tracking-wide text-gray-500">
                  <th className="text-left py-2">来源</th>
                  <th className="text-right py-2">张数</th>
                  <th className="text-right py-2">不含税</th>
                  <th className="text-right py-2">税</th>
                  <th className="text-right py-2">合计</th>
                </tr>
              </thead>
              <tbody>
                {data.revenue.byKind.map((k, i) => (
                  <tr key={i} className="border-t border-gray-100">
                    <td className="py-2">{k.source_kind}</td>
                    <td className="py-2 text-right tabular-nums">{k.invoices}</td>
                    <td className="py-2 text-right tabular-nums">{aud(k.net_cents)}</td>
                    <td className="py-2 text-right tabular-nums">{aud(k.tax_cents)}</td>
                    <td className="py-2 text-right tabular-nums">{aud(k.gross_cents)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export function FinancePanel({ api, showToast }) {
  const [view, setView] = useState('payroll');
  /* 期间从只读常量变成 state：它现在是筛选条件，不再是「本月，没得商量」。 */
  const [range, setRange] = useState(monthRange);

  return (
    <div className="space-y-3">
      <div className="flex gap-2 items-center">
        {[['payroll', '课酬'], ['reports', '报表']].map(([key, label]) => (
          <button type="button" key={key} onClick={() => setView(key)}
                  aria-pressed={view === key}
                  className={`min-h-[44px] px-4 rounded-lg text-xs font-bold border
                              ${view === key ? 'bg-indigo-600 text-white border-indigo-600'
                                             : 'bg-white text-gray-600 border-gray-300'}`}>
            {label}
          </button>
        ))}
      </div>

      {view === 'payroll'
        ? <PayrollView api={api} showToast={showToast} range={range} onRange={setRange} />
        : <ReportsView api={api} range={range} />}
    </div>
  );
}
