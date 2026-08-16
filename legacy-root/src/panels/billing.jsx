/* 账单工作区 — 谁欠钱、这张单是什么、钱到了没有。
 *
 * 第一个从 cms-app.jsx 里分出来的面板。它之所以能是独立文件，是因为
 * build_cms.sh 开了 --bundle；之所以敢是独立文件，是因为契约测试现在
 * 读整个 legacy-root/src/ 目录，而不是一个写死的文件名。
 *
 * 颜色一律按语义选色系，不按色相：index.html 把 red/rose 映射到 --danger、
 * green 系映射到 --success、amber 系映射到 --warning、indigo/purple 映射到
 * 租户主色。所以这里写 text-red-600 的意思是「这是危险状态」，
 * 换成陶土配色的工作室看到的是陶土主题里的危险色，不是红色。
 *
 * 共享能力（api / toast / 权限）由 props 传入而不是 import，避免和主文件
 * 形成循环依赖，也让这个面板可以被单独测试。
 */

import { aud, fmtApiDate } from "./_shared.jsx";
import { FilterBar, presetRange } from "./filter_bar.jsx";

const { useState, useEffect, useCallback, useMemo } = React;

const STATUS_LABEL = {
  draft: '草稿', issued: '已开具', part_paid: '部分付款', paid: '已付清', void: '已作废',
};

/* 逾期是推导的，不是存的 —— 后端刻意不存这个状态，因为存了就需要夜间任务
   维护，而两次运行之间它是错的。这里用同一条规则算。 */
const isOverdue = (invoice) => {
  if (!['issued', 'part_paid'].includes(invoice.status)) return false;
  if (!invoice.due_date) return false;
  const due = new Date(invoice.due_date);
  if (Number.isNaN(due.getTime())) return false;
  return due < new Date(new Date().toDateString());
};

function StatusChip({ invoice }) {
  const overdue = isOverdue(invoice);
  const cls = overdue
    ? 'bg-red-50 text-red-700 border-red-200'
    : invoice.status === 'paid'
    ? 'bg-green-50 text-green-700 border-green-200'
    : invoice.status === 'part_paid'
    ? 'bg-blue-50 text-blue-700 border-blue-200'
    : invoice.status === 'draft'
    ? 'bg-gray-100 text-gray-600 border-gray-200'
    : 'bg-gray-50 text-gray-600 border-gray-200';
  const label = overdue ? '逾期' : (STATUS_LABEL[invoice.status] || invoice.status);
  return <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${cls}`}>{label}</span>;
}

function Kpi({ label, value, sub, tone }) {
  const toneCls = tone === 'alert' ? 'text-red-600' : tone === 'good' ? 'text-green-700' : 'text-gray-900';
  return (
    <div className="bg-white border border-gray-200 rounded-xl p-3">
      <p className="text-[11px] font-bold uppercase tracking-wide text-gray-500">{label}</p>
      <p className={`text-xl font-bold tabular-nums ${toneCls}`}>{value}</p>
      {sub && <p className="text-[11px] text-gray-500">{sub}</p>}
    </div>
  );
}

export function BillingPanel({ api, showToast, canIssue, canTakePayment, accountId, onClearAccount }) {
  const [invoices, setInvoices] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [detail, setDetail] = useState(null);
  const [checked, setChecked] = useState(() => new Set());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [creating, setCreating] = useState(false);
  const [accounts, setAccounts] = useState([]);
  const [query, setQuery] = useState('');
  const [bucket, setBucket] = useState('all');
  const [range, setRange] = useState(() => ({ start: '', end: '' }));

  const load = useCallback(async () => {
    setLoading(true);
    try {
      /* accountId 来自学员档案上的深链。过滤在后端做，不在这里 —— 一个
         两百户的工作室拉回全部发票再筛掉 199 户，第一年还行，第三年不行。 */
      const query = accountId ? `?accountId=${encodeURIComponent(accountId)}` : '';
      const data = await api(`/billing/invoices${query}`);
      setInvoices(data.invoices || []);
      /* 付款方列表和发票一起取：开票对话框第一件事就是选付款方，
         等点开再去拉会让第一次点击慢一拍，而这份数据很小。 */
      const payers = await api('/billing/accounts').catch(() => ({accounts: []}));
      setAccounts(payers.accounts || []);
      setError('');
    } catch (e) {
      /* 读路径永不把控制台打挂：存量租户可能一张发票都没有，
         而一个 402/403 只说明这个套餐没开通，不是故障。 */
      setError(e.status === 403 ? '这个工作室尚未开通开票功能。' : `账单加载失败：${e.message}`);
    } finally {
      setLoading(false);
    }
  }, [api, accountId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!selectedId) { setDetail(null); return; }
    let cancelled = false;
    api(`/billing/invoices/${selectedId}`)
      .then(d => { if (!cancelled) setDetail(d); })
      .catch(e => { if (!cancelled) showToast(`发票详情加载失败：${e.message}`, 'warn'); });
    return () => { cancelled = true; };
    // 同上：showToast 不进依赖，否则失败即无限重试。
  }, [selectedId, api]);

  const summary = useMemo(() => {
    const issued = invoices.filter(i => i.status !== 'draft' && i.status !== 'void');
    const drafts = invoices.filter(i => i.status === 'draft');
    const overdue = invoices.filter(isOverdue);
    const billed = issued.reduce((s, i) => s + Number(i.total_cents || 0), 0);
    const paid = issued.reduce((s, i) => s + Number(i.amount_paid_cents || 0), 0);
    return {
      billed, paid, drafts: drafts.length,
      overdueCents: overdue.reduce((s, i) => s + Number(i.balance_cents || 0), 0),
      overdueAccounts: new Set(overdue.map(i => i.billing_account_id)).size,
      collectedPercent: billed > 0 ? Math.round((paid / billed) * 100) : null,
    };
  }, [invoices]);

  const draftIds = useMemo(
    () => invoices.filter(i => i.status === 'draft').map(i => String(i.id)),
    [invoices],
  );
  /* 一张发票是「先有单据，再往上挂行」两步落地的，因为 issue 是原子的：
     开具那一刻要分配号码、定日期、锁死金额。所以这里建草稿、加行，
     开具留给操作的人按下 —— 建好不等于发出。 */
  const createInvoice = async (form) => {
    setBusy(true);
    try {
      const draft = await api('/billing/invoices', {
        method: 'POST',
        body: JSON.stringify({billingAccountId: form.accountId, note: form.note}),
      });
      const invoiceId = draft.invoice?.id || draft.id;
      for (const line of form.lines) {
        await api(`/billing/invoices/${invoiceId}/lines`, {
          method: 'POST',
          body: JSON.stringify({
            description: line.description,
            quantity: line.quantity,
            unitPriceCents: Math.round(Number(line.unitPrice) * 100),
            taxRateBp: Number(line.taxRateBp),
            /* 课时充值走 source_kind='package' 并带上学员：两本账各自
               记各自的，发票行只是「这笔充值是被这张单收的钱」的指路牌。
               谁也不改谁。 */
            sourceKind: line.isCredits ? 'package' : 'manual',
            studentId: line.studentId || null,
          }),
        });
      }
      showToast('草稿已建好，复核后再开具', 'success');
      setCreating(false);
      await load();
      setSelectedId(String(invoiceId));
    } catch (e) {
      showToast(`新建发票失败：${e.message}`, 'error');
    } finally { setBusy(false); }
  };

  /* 筛选在本地做：这一页已经把发票全取回来了，再为了筛选跑一趟网络，
     只会让点一下药丸有半秒的空白。数量大到需要服务端筛时，FilterBar
     的形状不用变，换的是这个 useMemo。 */
  const visible = useMemo(() => {
    const text = query.trim().toLowerCase();
    return invoices.filter(invoice => {
      if (bucket === 'overdue' && !isOverdue(invoice)) return false;
      if (bucket === 'unpaid' && !(Number(invoice.balance_cents) > 0 && invoice.status !== 'draft')) return false;
      if (bucket === 'draft' && invoice.status !== 'draft') return false;
      if (range.start && invoice.issue_date && String(invoice.issue_date) < range.start) return false;
      if (range.end && invoice.issue_date && String(invoice.issue_date) > range.end) return false;
      if (!text) return true;
      /* 前台接电话时手上只有一个号，对账时手上只有一个姓 —— 两条路都要通。 */
      return `${invoice.account_name || ''} ${invoice.number || ''}`.toLowerCase().includes(text);
    });
  }, [invoices, query, bucket, range]);

  const buckets = useMemo(() => [
    { key: 'all', label: '全部', count: invoices.length },
    { key: 'overdue', label: '逾期', count: invoices.filter(isOverdue).length },
    { key: 'unpaid', label: '未付清',
      count: invoices.filter(i => Number(i.balance_cents) > 0 && i.status !== 'draft').length },
    { key: 'draft', label: '草稿', count: invoices.filter(i => i.status === 'draft').length },
  ], [invoices]);

  const checkedDrafts = useMemo(
    () => draftIds.filter(id => checked.has(id)),
    [draftIds, checked],
  );

  const toggle = (id) => {
    setChecked(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  /* 批量发出：人工创建的多张草稿可以一次复核后发出。
     逐张调用而不是一个批量接口 —— 每张发票的编号分配都要自己的事务，
     一张失败不该把其余的一起回滚掉。 */
  const issueSelected = async () => {
    if (!checkedDrafts.length || busy) return;
    setBusy(true);
    let ok = 0; const failed = [];
    for (const id of checkedDrafts) {
      try {
        await api(`/billing/invoices/${id}/issue`, { method: 'POST' });
        ok += 1;
      } catch (e) {
        failed.push(e.message);
      }
    }
    setBusy(false);
    setChecked(new Set());
    await load();
    if (failed.length) showToast(`发出 ${ok} 张，${failed.length} 张失败：${failed[0]}`, 'warn');
    else showToast(`已发出 ${ok} 张发票`, 'success');
  };

  const recordPayment = async () => {
    if (!detail || busy) return;
    const balance = Number(detail.invoice.balance_cents || 0);
    if (balance <= 0) { showToast('这张单已经没有欠款了', 'warn'); return; }
    setBusy(true);
    try {
      await api('/billing/payments', {
        method: 'POST',
        body: JSON.stringify({
          billingAccountId: detail.invoice.billing_account_id,
          // Name the invoice the operator is looking at. Without it the server
          // allocated oldest-first and this invoice never moved, so the button
          // looked broken and each press quietly paid down a different one.
          invoiceId: detail.invoice.id,
          amountCents: balance,
          method: 'bank_transfer',
          autoAllocate: true,
        }),
      });
      showToast(`已登记 ${aud(balance)}`, 'success');
      await load();
      const refreshed = await api(`/billing/invoices/${selectedId}`);
      setDetail(refreshed);
    } catch (e) {
      showToast(`登记收款失败：${e.message}`, 'warn');
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <div className="p-6 text-sm text-gray-500">正在加载账单…</div>;
  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

  return (
    <div className="space-y-3">
      {/* 深链进来时列表是筛过的，必须说出来。一个看不见的筛选条件，就是
          「为什么账单里只有三张发票」这通电话。 */}
      {creating && (
        <NewInvoiceDialog accounts={accounts} busy={busy}
                          onClose={() => setCreating(false)} onSubmit={createInvoice} />
      )}
      {accountId && (
        <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50 border border-amber-100">
          <span className="text-xs font-bold text-amber-800">
            只看这个账单账户{invoices[0]?.account_name ? ` · ${invoices[0].account_name}` : ''}
          </span>
          <button type="button" onClick={() => onClearAccount && onClearAccount()}
                  className="ml-auto min-h-[44px] px-3 rounded-lg border border-amber-200 bg-white text-xs font-bold text-amber-800">
            显示全部
          </button>
        </div>
      )}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Kpi label="已开票" value={aud(summary.billed)} sub={`${invoices.length} 张 · 含 GST`} />
        <Kpi label="已收到" value={aud(summary.paid)} tone="good"
             sub={summary.collectedPercent === null ? '暂无已开具发票' : `${summary.collectedPercent}% 已收`} />
        <Kpi label="逾期" value={aud(summary.overdueCents)} tone={summary.overdueCents > 0 ? 'alert' : undefined}
             sub={`${summary.overdueAccounts} 个家庭`} />
        <Kpi label="待发草稿" value={String(summary.drafts)} sub={summary.drafts ? '勾选后可批量发出' : '没有待发的'} />
      </div>

      {/* φ 主从：详情是主体（61.8%），列表是导航（38.2%）。
          令牌来自 ui-tokens.css，不是这里编出来的比例。 */}
      <div className="ui-golden-split">
        <div className="min-w-0 space-y-2">
          <FilterBar
            range={range} onRange={setRange}
            query={query} onQuery={setQuery}
            searchPlaceholder="搜付款方或发票号"
            buckets={buckets} bucket={bucket} onBucket={setBucket}
            total={visible.length} totalNoun="张" />
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden min-w-0">
          <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
            <span className="text-xs font-bold">发票</span>
            {canIssue && checkedDrafts.length === 0 && (
              <button type="button" onClick={() => setCreating(true)}
                      className="ml-auto min-h-[44px] px-3 rounded-lg border border-indigo-200 bg-white text-xs font-bold text-indigo-700">
                新建发票
              </button>
            )}
            {checkedDrafts.length > 0 && canIssue && (
              <button type="button" onClick={issueSelected} disabled={busy}
                      className="ml-auto min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                批量发出 ({checkedDrafts.length})
              </button>
            )}
          </div>
          {invoices.length === 0 ? (
            <p className="px-4 py-6 text-xs text-gray-500">还没有发票。点击“新建发票”创建草稿，复核后再开具。</p>
          ) : visible.length === 0 ? (
            /* 「一张都没有」和「筛完没剩下」是两句话。第二句要告诉人怎么退出去。 */
            <p className="px-4 py-6 text-xs text-gray-500">没有符合当前筛选的发票。清除筛选可以看到全部 {invoices.length} 张。</p>
          ) : visible.map(invoice => (
            <button type="button" key={invoice.id} onClick={() => setSelectedId(String(invoice.id))}
                    className={`w-full text-left flex items-center gap-2 px-3 py-2 border-b border-gray-100 min-h-[44px]
                                ${String(invoice.id) === selectedId ? 'bg-indigo-50' : 'hover:bg-gray-50'}`}>
              {invoice.status === 'draft' && canIssue && (
                <input type="checkbox" checked={checked.has(String(invoice.id))}
                       onChange={() => toggle(String(invoice.id))}
                       onClick={e => e.stopPropagation()}
                       aria-label={`选择 ${invoice.account_name} 的草稿`} />
              )}
              <span className="min-w-0">
                <span className="block text-xs font-bold truncate">{invoice.account_name}</span>
                <span className="block text-[11px] text-gray-500 truncate">
                  {invoice.number || '草稿 · 未编号'}
                  {invoice.due_date ? ` · 到期 ${fmtApiDate(invoice.due_date)}` : ''}
                </span>
              </span>
              <span className="ml-auto flex items-center gap-2">
                <StatusChip invoice={invoice} />
                <span className={`text-xs font-bold tabular-nums ${isOverdue(invoice) ? 'text-red-600' : ''}`}>
                  {aud(invoice.balance_cents ?? invoice.total_cents)}
                </span>
              </span>
            </button>
          ))}
        </div>
        </div>

        <div className="grid gap-3 min-w-0">
          {!detail ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6 text-xs text-gray-500">
              选择左边的一张发票查看明细。
            </div>
          ) : (
            <>
              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="flex items-center gap-2 px-4 py-3 border-b border-gray-200">
                  <span className="text-xs font-bold">
                    {detail.invoice.number || '草稿'} · {detail.invoice.account_name}
                  </span>
                  <span className="ml-auto"><StatusChip invoice={detail.invoice} /></span>
                </div>
                <div className="p-4 overflow-x-auto">
                  {/* min-width is what makes the overflow-x-auto above mean
                      anything. With `w-full` alone the table can never exceed its
                      container, so in the narrow detail column the last three
                      money columns compressed toward zero and 应付 / 余额 read as
                      blank rows — the figures were in the response the whole time.
                      A width floor lets the table overflow and the container
                      scroll, which is what that class was there for. */}
                  <table className="w-full min-w-[26rem] text-xs">
                    <thead>
                      <tr className="text-[10px] uppercase tracking-wide text-gray-500">
                        <th className="text-left py-2">项目</th>
                        <th className="text-right py-2">数量</th>
                        <th className="text-right py-2">单价</th>
                        <th className="text-right py-2">税</th>
                        <th className="text-right py-2">小计</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(detail.lines || []).map(line => (
                        <tr key={line.id} className="border-t border-gray-100">
                          <td className="py-2">{line.description}</td>
                          <td className="py-2 text-right tabular-nums">{line.quantity}</td>
                          <td className="py-2 text-right tabular-nums">{aud(line.unit_price_cents)}</td>
                          <td className="py-2 text-right tabular-nums">{aud(line.tax_cents)}</td>
                          <td className="py-2 text-right tabular-nums">{aud(line.total_cents)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* The three numbers that answer "what does this family owe" used
                    to be the last column of a five-column table. In the detail
                    column that table has to scroll sideways, so 应付 / 已付 / 余额
                    rendered as labels with nothing beside them — the figures were
                    in the response all along, just pushed off-screen. They are
                    not line-item detail; they are the answer, and they belong
                    where they cannot be scrolled away from. */}
                <div className="px-4 pb-4 -mt-1 space-y-1 text-xs">
                  <div className="flex items-baseline gap-3 border-t border-gray-200 pt-2 font-bold">
                    <span>应付</span>
                    <span className="ml-auto tabular-nums">{aud(detail.invoice.total_cents)}</span>
                  </div>
                  {Number(detail.invoice.amount_paid_cents) > 0 && (
                    <div className="flex items-baseline gap-3 text-green-700">
                      <span>已付</span>
                      <span className="ml-auto tabular-nums">−{aud(detail.invoice.amount_paid_cents)}</span>
                    </div>
                  )}
                  <div className="flex items-baseline gap-3 font-bold">
                    <span>余额</span>
                    <span className="ml-auto tabular-nums">{aud(detail.invoice.balance_cents)}</span>
                  </div>

                  <div className="flex flex-wrap gap-2 items-center mt-3">
                    {detail.invoice.status === 'draft' && canIssue && (
                      <button type="button" disabled={busy}
                              onClick={async () => {
                                setBusy(true);
                                try {
                                  await api(`/billing/invoices/${selectedId}/issue`, { method: 'POST' });
                                  showToast('已开具', 'success');
                                  await load();
                                  setDetail(await api(`/billing/invoices/${selectedId}`));
                                } catch (e) { showToast(`开具失败：${e.message}`, 'warn'); }
                                finally { setBusy(false); }
                              }}
                              className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                        开具发票
                      </button>
                    )}
                    {detail.invoice.status !== 'draft' && Number(detail.invoice.balance_cents) > 0 && canTakePayment && (
                      <button type="button" onClick={recordPayment} disabled={busy}
                              className="min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">
                        登记收款
                      </button>
                    )}
                    {/* 已开具的发票不可改 —— 这是数据库触发器保证的。给一个点了会报错的
                        按钮比不给更糟，所以这里明确说明它为什么不在。 */}
                    {detail.invoice.status !== 'draft' && (
                      <span className="text-[11px] text-gray-500">
                        已开具的发票不可修改，改错请开贷记单冲销后重开。
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-gray-200 text-xs font-bold">这张单发生过什么</div>
                {(detail.events || []).length === 0 ? (
                  <p className="px-4 py-4 text-[11px] text-gray-500">还没有记录。开具、送达、收款、推送 Xero 都会出现在这里。</p>
                ) : (detail.events || []).map((event, i) => {
                  /* The raw enum was printed straight onto the screen, so a
                     studio read "issued" in an otherwise Chinese interface. The
                     labels are Chinese here because cms-i18n.js translates zh→en
                     for the whole CMS — writing English here would be the one
                     string the language switch could not move. */
                  const LABEL = {
                    issued: '已开具', sent: '已送达', part_paid: '部分付款',
                    paid: '已付清', refunded: '已退款', voided: '已作废',
                    overdue: '已逾期', xero_pushed: '已推送 Xero',
                  };
                  const d = event.detail || {};
                  const amount = Number(d.amount_cents || 0);
                  const balance = d.balance_cents === undefined ? null : Number(d.balance_cents);
                  return (
                    <div key={i} className="flex items-baseline gap-2 px-4 py-2 border-b border-gray-100 last:border-0 text-[11px]">
                      <span className="font-bold">{LABEL[event.event_type] || event.event_type}</span>
                      {amount > 0 && <span className="text-gray-500">{aud(amount)}</span>}
                      {balance !== null && <span className="text-gray-400">余额 {aud(balance)}</span>}
                      <span className="ml-auto text-gray-500 tabular-nums">{fmtApiDate(event.occurred_at)}</span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}


/* 新建发票。刻意只到「草稿」为止 —— 开具是另一个动作，因为开具会分配
   永久号码、按付款条件算到期日、并让金额从此不可改。把两件事合成一个
   按钮，就等于把「我先记一下」和「这份文件已经生效」混为一谈。 */
function NewInvoiceDialog({ accounts, busy, onClose, onSubmit }) {
  const [accountId, setAccountId] = useState('');
  const [note, setNote] = useState('');
  const [lines, setLines] = useState([
    {description: '', quantity: '1', unitPrice: '', taxRateBp: '1000', isCredits: false, studentId: ''},
  ]);

  const setLine = (i, key) => (e) => setLines(rows =>
    rows.map((row, idx) => idx === i ? {...row, [key]: e.target.value} : row));
  const toggleCredits = (i) => () => setLines(rows =>
    rows.map((row, idx) => idx === i ? {...row, isCredits: !row.isCredits} : row));

  const total = lines.reduce((sum, line) => {
    const net = Number(line.quantity || 0) * Number(line.unitPrice || 0);
    return sum + net + net * (Number(line.taxRateBp || 0) / 10000);
  }, 0);

  const ready = accountId && lines.some(l => l.description.trim() && Number(l.unitPrice) > 0);

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm">
      <div className="bg-white w-full sm:max-w-xl rounded-t-2xl sm:rounded-2xl p-5 space-y-3 max-h-[90vh] overflow-y-auto">
        <div>
          <p className="text-lg font-bold text-gray-800">新建发票</p>
          <p className="text-sm text-gray-500 mt-1">
            先存成草稿。复核无误后在列表里开具 —— 开具会定号码和到期日，之后金额不能再改。
          </p>
        </div>

        <label className="block text-xs text-gray-400">付款方
          <select value={accountId} onChange={e => setAccountId(e.target.value)}
                  className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
            <option value="">请选择</option>
            {accounts.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </label>

        <div className="space-y-2">
          {lines.map((line, i) => (
            <div key={i} className="border border-gray-200 rounded-xl p-3 space-y-2">
              <input value={line.description} onChange={setLine(i, 'description')}
                     placeholder="项目说明，例如「第三学期学费」"
                     className="w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
              <div className="grid grid-cols-3 gap-2">
                <label className="block text-xs text-gray-400">数量
                  <input type="number" min="0" step="0.01" value={line.quantity} onChange={setLine(i, 'quantity')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-400">单价（含税前）
                  <input type="number" min="0" step="0.01" value={line.unitPrice} onChange={setLine(i, 'unitPrice')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-400">税率
                  <select value={line.taxRateBp} onChange={setLine(i, 'taxRateBp')}
                          className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                    <option value="1000">GST 10%</option>
                    <option value="0">不计税</option>
                  </select>
                </label>
              </div>
              {/* 与「充值与退款」的联动就在这一行：勾上之后这条发票行会以
                  source_kind='package' 落库，课时账本与钱账本各记各的，
                  发票行只负责说明这笔钱收的是什么。 */}
              <label className="flex items-center gap-2 text-xs text-gray-600">
                <input type="checkbox" checked={line.isCredits} onChange={toggleCredits(i)} />
                这一行是课时充值（与「充值与退款」对应）
              </label>
            </div>
          ))}
          <button type="button"
                  onClick={() => setLines(rows => [...rows, {description: '', quantity: '1', unitPrice: '', taxRateBp: '1000', isCredits: false, studentId: ''}])}
                  className="min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-700">
            再加一行
          </button>
        </div>

        <input value={note} onChange={e => setNote(e.target.value)} placeholder="备注（选填）"
               className="w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />

        <p className="text-sm text-gray-500">合计约 {aud(Math.round(total * 100))}（含税）</p>

        <div className="flex gap-2">
          <button type="button" onClick={onClose} disabled={busy}
                  className="flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50">
            取消
          </button>
          <button type="button" onClick={() => onSubmit({accountId, note, lines})} disabled={busy || !ready}
                  className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
            存为草稿
          </button>
        </div>
      </div>
    </div>
  );
}
