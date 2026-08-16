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

const { useState, useEffect, useCallback, useMemo, useRef } = React;

const STATUS_LABEL = {
  draft: '草稿', issued: '已开具', part_paid: '部分付款', paid: '已付清', void: '已作废',
};

/* Credit/refund state is derived from the ledger facts.  It never rewrites the
   payment's paid/refunded status; the distinction is what keeps a credited
   invoice readable to both operators and accountants. */
function invoiceFinancialState(invoice) {
  const total = Math.max(0, Number(invoice?.total_cents || 0));
  const paid = Math.max(0, Number(invoice?.amount_paid_cents || 0));
  const credited = Math.max(0, Number(invoice?.amount_credited_cents || 0));
  const refunded = Math.max(0, Number(invoice?.amount_refunded_cents || 0));
  const balance = Number.isFinite(Number(invoice?.balance_cents))
    ? Number(invoice.balance_cents)
    : total - paid - credited;
  const netReceivedCents = Math.max(0, Number(invoice?.net_received_cents ?? paid - refunded));
  let creditState = 'none';
  if (total > 0 && credited >= total) creditState = 'fully_credited';
  else if (credited > 0) creditState = 'partially_credited';
  return {total, paid, credited, refunded, balance, netReceivedCents, creditState};
}

const CREDIT_STATE_LABEL = {
  partially_credited: '部分贷记',
  fully_credited: '已全额贷记',
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
  const financial = invoiceFinancialState(invoice);
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
  return (
    <span className="inline-flex items-center gap-1">
      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${cls}`}>{label}</span>
      {financial.creditState !== 'none' && <span className="text-[10px] font-bold px-1.5 py-0.5 rounded border border-indigo-200 bg-indigo-50 text-indigo-700 whitespace-nowrap">{CREDIT_STATE_LABEL[financial.creditState]}</span>}
    </span>
  );
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

function printableAddress(address) {
  if (!address) return '';
  if (typeof address === 'string') return address;
  return [address.line1, address.line2, address.suburb, address.state, address.postcode, address.country]
    .filter(Boolean).join(', ');
}

/* The print surface is deliberately a separate document component.  It reads
   only the API's InvoiceDocument DTO, so an issued invoice cannot change when
   an operator edits the live payer or tenant identity after issue. */
function InvoicePrintableDocument({ document }) {
  if (!document) return null;
  const meta = document.document || {};
  const supplier = document.supplier || {};
  const recipient = document.recipient || {};
  const totals = document.totals || {};
  const payment = document.paymentSummary || {};
  const bank = supplier.bank || {};
  const issued = meta.status !== 'draft';
  const title = meta.kind === 'credit_note'
    ? 'Credit Note'
    : (supplier.gstRegistered ? 'Tax Invoice' : 'Invoice');
  const status = meta.statusLabel || meta.status || '';
  const optional = (label, value) => value ? (
    <div className="invoice-field" key={label}><dt>{label}</dt><dd>{value}</dd></div>
  ) : null;
  return (
    <article className="invoice-customer-document bg-white text-gray-900 border border-gray-200 rounded-xl p-6 sm:p-8">
      <header className="flex flex-wrap items-start justify-between gap-6 border-b border-gray-300 pb-5">
        <div>
          <p className="text-2xl font-bold tracking-tight">{title}</p>
          <p className="text-xs text-gray-500 mt-1">{status}</p>
        </div>
        <div className="text-right text-xs tabular-nums">
          {meta.number && <p className="font-bold text-base">{meta.number}</p>}
          {meta.issueDate && <p>Issue date: {fmtApiDate(meta.issueDate)}</p>}
          {meta.dueDate && <p>Due date: {fmtApiDate(meta.dueDate)}</p>}
          <p>Currency: {meta.currency || 'AUD'}</p>
          {!issued && <p className="invoice-draft-watermark" aria-label="Draft">DRAFT</p>}
        </div>
      </header>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 py-5 border-b border-gray-200 text-xs">
        <section>
          <h2 className="font-bold text-gray-500 uppercase tracking-wide mb-2">Supplier</h2>
          <dl className="space-y-1">
            {optional('Legal name', supplier.legalName)}
            {optional('Trading name', supplier.tradingName)}
            {optional('ABN', supplier.abn)}
            {optional('Address', printableAddress(supplier.address))}
            {optional('Email', supplier.contactEmail)}
            {optional('Phone', supplier.contactPhone)}
            {optional('Website', supplier.website)}
          </dl>
        </section>
        <section>
          <h2 className="font-bold text-gray-500 uppercase tracking-wide mb-2">Bill to</h2>
          <dl className="space-y-1">
            {optional('Name', recipient.displayName)}
            {optional('Company', recipient.companyName)}
            {optional('Contact', recipient.contactName)}
            {optional('ABN', recipient.abn)}
            {optional('Address', recipient.billingAddress)}
            {optional('Email', recipient.email)}
            {optional('Mobile', recipient.mobile)}
            {optional('PO reference', recipient.purchaseOrderRef)}
          </dl>
        </section>
      </div>

      <table className="w-full text-xs my-5 invoice-lines-table">
        <thead><tr className="border-b border-gray-300 text-left">
          <th className="py-2 pr-2">Description</th>
          <th className="py-2 px-2 text-right">Qty</th>
          <th className="py-2 px-2 text-right">Unit</th>
          <th className="py-2 px-2 text-right">Net</th>
          <th className="py-2 px-2 text-right">Tax rate</th>
          <th className="py-2 pl-2 text-right">Tax</th>
          <th className="py-2 pl-2 text-right">Gross</th>
        </tr></thead>
        <tbody>
          {(document.lines || []).map(line => (
            <tr key={line.id || `${line.description}-${line.quantity}`} className="border-b border-gray-100 align-top">
              <td className="py-2 pr-2">{line.description}</td>
              <td className="py-2 px-2 text-right tabular-nums">{line.quantity}</td>
              <td className="py-2 px-2 text-right tabular-nums">{aud(line.unitPriceCents)}</td>
              <td className="py-2 px-2 text-right tabular-nums">{aud(line.netCents)}</td>
              <td className="py-2 px-2 text-right tabular-nums">{(Number(line.taxRateBp || 0) / 100).toFixed(2)}%</td>
              <td className="py-2 pl-2 text-right tabular-nums">{aud(line.taxCents)}</td>
              <td className="py-2 pl-2 text-right tabular-nums">{aud(line.totalCents)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="ml-auto w-full max-w-sm space-y-1 text-xs tabular-nums">
        <div className="flex justify-between"><span>Subtotal</span><span>{aud(totals.subtotalCents)}</span></div>
        <div className="flex justify-between"><span>GST / tax</span><span>{aud(totals.taxCents)}</span></div>
        <div className="flex justify-between border-t border-gray-300 pt-2 font-bold text-sm"><span>Total</span><span>{aud(totals.totalCents)}</span></div>
        <div className="flex justify-between"><span>Paid</span><span>{aud(payment.amountPaidCents)}</span></div>
        <div className="flex justify-between"><span>Refunded</span><span>{aud(payment.amountRefundedCents)}</span></div>
        <div className="flex justify-between"><span>Net received</span><span>{aud(payment.netReceivedCents)}</span></div>
        <div className="flex justify-between"><span>Credited</span><span>{aud(payment.amountCreditedCents)}</span></div>
        <div className="flex justify-between font-bold"><span>Balance</span><span>{aud(payment.balanceCents)}</span></div>
      </div>

      {(meta.note || recipient.purchaseOrderRef || supplier.paymentNote || bank.accountName || (payment.payments || []).length > 0) && (
        <footer className="border-t border-gray-200 mt-6 pt-4 text-xs space-y-2">
          {meta.note && <p><strong>Notes:</strong> {meta.note}</p>}
          {recipient.purchaseOrderRef && <p><strong>PO reference:</strong> {recipient.purchaseOrderRef}</p>}
          {supplier.paymentNote && <p><strong>Payment:</strong> {supplier.paymentNote}</p>}
          {bank.accountName && <p><strong>Remittance:</strong> {bank.accountName}{bank.bsb ? ` · BSB ${bank.bsb}` : ''}{bank.accountNo ? ` · ${bank.accountNo}` : ''}</p>}
          {(payment.payments || []).map(item => <p key={item.id || item.receivedAt}><strong>Payment received:</strong> {aud(item.amountCents)} · {item.method || item.status}</p>)}
        </footer>
      )}
    </article>
  );
}

export function BillingPanel({ api, showToast, canIssue, canTakePayment, canExportData, tenantSlug,
  accountId, onClearAccount, students, studentPicker }) {
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
  const [payerEdit, setPayerEdit] = useState(null);
  const [payerSaving, setPayerSaving] = useState(false);
  const [creditNoteDetail, setCreditNoteDetail] = useState(null);

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
    const netReceivedCents = issued.reduce((s, i) => s + invoiceFinancialState(i).netReceivedCents, 0);
    const credited = issued.reduce((s, i) => s + invoiceFinancialState(i).credited, 0);
    const refunded = issued.reduce((s, i) => s + invoiceFinancialState(i).refunded, 0);
    return {
      billed, netReceivedCents, credited, refunded, drafts: drafts.length,
      overdueCents: overdue.reduce((s, i) => s + Number(i.balance_cents || 0), 0),
      overdueAccounts: new Set(overdue.map(i => i.billing_account_id)).size,
      collectedPercent: billed > 0 ? Math.round((netReceivedCents / billed) * 100) : null,
    };
  }, [invoices]);

  const draftIds = useMemo(
    () => invoices.filter(i => i.status === 'draft').map(i => String(i.id)),
    [invoices],
  );
  /* Draft creation is one aggregate command.  The server validates the payer,
     every line, and all tenant references before inserting anything, so a
     transient response loss cannot leave a payer or half-built invoice behind. */
  const createInvoice = async (form) => {
    setBusy(true);
    try {
      const draft = await api('/billing/invoice-drafts', {
        method: 'POST',
        body: JSON.stringify(form),
      });
      const invoiceId = draft.invoice?.id || draft.invoiceId;
      showToast('草稿已建好，复核后再开具', 'success');
      setCreating(false);
      await load();
      setSelectedId(String(invoiceId));
    } catch (e) {
      showToast(`新建发票失败：${e.message}`, 'error');
      throw e;
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

  const exportCsv = view => {
    if (!canExportData || !tenantSlug) return;
    const params = new URLSearchParams({view, includeDrafts: '0'});
    if (range.start) params.set('from', range.start);
    if (range.end) params.set('to', range.end);
    if (accountId) params.set('accountId', accountId);
    const link = document.createElement('a');
    link.href = `/s/${encodeURIComponent(tenantSlug)}/v1/billing/invoices/export.csv?${params.toString()}`;
    link.download = `invoices-${view}.csv`;
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
    showToast(view === 'summary' ? '发票汇总 CSV 已开始下载' : '发票行项目 CSV 已开始下载', 'success');
  };

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

  const printCustomerDocument = (customerDocument) => {
    if (!customerDocument) return;
    const meta = customerDocument.document || {};
    const title = meta.kind === 'credit_note'
      ? 'Credit Note'
      : (customerDocument.supplier?.gstRegistered ? 'Tax Invoice' : 'Invoice');
    const number = meta.number || 'Draft';
    const previousTitle = document.title;
    const cleanup = () => document.body.classList.remove('invoice-print-mode');
    const restore = () => {
      cleanup();
      document.title = previousTitle;
    };
    document.title = `${title} · ${number}`;
    document.body.classList.add('invoice-print-mode');
    window.addEventListener('afterprint', restore, {once: true});
    window.print();
    /* WebKit can omit afterprint when the operator cancels immediately. */
    window.setTimeout(restore, 1500);
  };

  const printInvoice = () => {
    if (!detail) return;
    printCustomerDocument(detail.document);
  };

  const openPayerEditor = () => {
    if (!detail?.invoice) return;
    setPayerEdit({
      name: detail.invoice.account_name || '',
      kind: detail.invoice.account_kind || 'family',
      contactName: detail.invoice.account_contact_name || '',
      email: detail.invoice.account_email || '',
      mobile: detail.invoice.account_mobile || '',
      companyName: detail.invoice.account_company_name || '',
      abn: detail.invoice.account_abn || '',
      billingAddress: detail.invoice.account_billing_address || '',
      paymentTermsDays: String(detail.invoice.account_payment_terms_days ?? 14),
      purchaseOrderRef: detail.invoice.account_purchase_order_ref || '',
      language: detail.invoice.account_language || '',
      note: '',
    });
  };

  const savePayer = async () => {
    if (!detail?.invoice?.billing_account_id || !payerEdit || payerSaving) return;
    setPayerSaving(true);
    try {
      await api(`/billing/accounts/${detail.invoice.billing_account_id}`, {
        method: 'PATCH', body: JSON.stringify(payerEdit),
      });
      showToast('付款方资料已更新；已开具发票继续读取冻结快照', 'success');
      setPayerEdit(null);
      await load();
      setDetail(await api(`/billing/invoices/${selectedId}`));
    } catch (e) {
      showToast(`付款方更新失败：${e.message}`, 'warn');
    } finally { setPayerSaving(false); }
  };

  const openCreditNote = async noteId => {
    try {
      setCreditNoteDetail(await api(`/billing/credit-notes/${noteId}`));
    } catch (e) {
      showToast(`贷记单加载失败：${e.message}`, 'warn');
    }
  };

  if (loading) return <div className="p-6 text-sm text-gray-500">正在加载账单…</div>;
  if (error) return <div className="p-6 text-sm text-red-600">{error}</div>;

  return (
    <div className="space-y-3">
      {/* 深链进来时列表是筛过的，必须说出来。一个看不见的筛选条件，就是
          「为什么账单里只有三张发票」这通电话。 */}
      {creating && (
        <NewInvoiceDialog api={api} accounts={accounts} students={students} studentPicker={studentPicker} busy={busy}
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
        <Kpi label="净收款（扣除退款）" value={aud(summary.netReceivedCents)} tone="good"
             sub={summary.collectedPercent === null ? '暂无已开具发票' : `${summary.collectedPercent}% · 贷记 ${aud(summary.credited)} · 退款 ${aud(summary.refunded)}`} />
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
          <div className="flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200">
            <span className="text-xs font-bold">发票</span>
            {canExportData && (
              <div className="ml-auto flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-gray-500">会计导出不含草稿 · 当前筛选范围</span>
                <button type="button" onClick={() => exportCsv('summary')}
                        className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700">
                  发票汇总 CSV
                </button>
                <button type="button" onClick={() => exportCsv('lines')}
                        className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700">
                  行项目 CSV
                </button>
                <button type="button" onClick={() => exportCsv('ledger')}
                        className="min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700">
                  会计流水 CSV
                </button>
              </div>
            )}
            {canIssue && checkedDrafts.length === 0 && (
              <button type="button" onClick={() => setCreating(true)}
                      className={`${canExportData ? '' : 'ml-auto '}min-h-[44px] px-3 rounded-lg border border-indigo-200 bg-white text-xs font-bold text-indigo-700`}>
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
                  {aud(invoiceFinancialState(invoice).balance ?? invoice.total_cents)}
                </span>
              </span>
            </button>
          ))}
        </div>
        </div>

        <div className="invoice-printable grid gap-3 min-w-0">
          {!detail ? (
            <div className="bg-white border border-gray-200 rounded-xl p-6 text-xs text-gray-500">
              选择左边的一张发票查看明细。
            </div>
          ) : (
            <>
              <InvoicePrintableDocument document={detail.document} />
              <div className="payer-edit bg-white border border-gray-200 rounded-xl overflow-hidden">
                <div className="flex items-start gap-3 px-4 py-3 border-b border-gray-200">
                  <div className="min-w-0">
                    <p className="text-xs font-bold">付款方资料</p>
                    <p className="text-[11px] text-gray-500 mt-1">当前发票收件人：{detail.invoice.account_name} · {detail.invoice.account_kind || 'family'}{detail.invoice.account_email ? ` · ${detail.invoice.account_email}` : ''}{detail.invoice.account_mobile ? ` · ${detail.invoice.account_mobile}` : ''}</p>
                    <p className="text-[11px] text-indigo-700 mt-1">已开具发票不会改变：客户文档继续使用 issued snapshot。</p>
                  </div>
                  {canIssue && !payerEdit && <button type="button" onClick={openPayerEditor} className="ml-auto min-h-[44px] px-3 rounded-lg border border-indigo-200 bg-white text-xs font-bold text-indigo-700">查看 / 编辑付款方</button>}
                </div>
                {payerEdit && (
                  <div className="p-4 space-y-3">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <label className="text-xs text-gray-500">姓名 / 名称
                        <input value={payerEdit.name} onChange={e => setPayerEdit({...payerEdit, name: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                      </label>
                      <label className="text-xs text-gray-500">类型
                        <select value={payerEdit.kind} onChange={e => setPayerEdit({...payerEdit, kind: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                          <option value="person">个人</option><option value="family">家庭</option><option value="organisation">机构</option>
                        </select>
                      </label>
                      <label className="text-xs text-gray-500">邮箱
                        <input type="email" value={payerEdit.email} onChange={e => setPayerEdit({...payerEdit, email: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                      </label>
                      <label className="text-xs text-gray-500">手机
                        <input value={payerEdit.mobile} onChange={e => setPayerEdit({...payerEdit, mobile: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                      </label>
                      <label className="text-xs text-gray-500">联系人
                        <input value={payerEdit.contactName} onChange={e => setPayerEdit({...payerEdit, contactName: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                      </label>
                      <label className="text-xs text-gray-500">付款期限（天）
                        <input type="number" min="0" max="3650" value={payerEdit.paymentTermsDays} onChange={e => setPayerEdit({...payerEdit, paymentTermsDays: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                      </label>
                    </div>
                    <label className="block text-xs text-gray-500">账单地址
                      <input value={payerEdit.billingAddress} onChange={e => setPayerEdit({...payerEdit, billingAddress: e.target.value})} className="mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                    </label>
                    <div className="flex gap-2">
                      <button type="button" onClick={() => setPayerEdit(null)} disabled={payerSaving} className="flex-1 min-h-[44px] rounded-xl border border-gray-200 text-xs font-bold">取消</button>
                      <button type="button" onClick={savePayer} disabled={payerSaving} className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold disabled:opacity-50">{payerSaving ? '保存中…' : '保存付款方'}</button>
                    </div>
                  </div>
                )}
              </div>
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
                  {(() => {
                    const financial = invoiceFinancialState(detail.invoice);
                    return (
                      <div className="mb-2 rounded-lg border border-indigo-100 bg-indigo-50/60 p-2 text-[11px] text-indigo-900">
                        <span className="font-bold">{financial.creditState === 'fully_credited' ? '已全额贷记' : financial.creditState === 'partially_credited' ? '部分贷记' : '未贷记'}</span>
                        <span className="ml-2">净收款 {aud(financial.netReceivedCents)}（原收款 {aud(financial.paid)}，退款 {aud(financial.refunded)}）</span>
                      </div>
                    );
                  })()}
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
                  {Number(detail.invoice.amount_credited_cents) > 0 && (
                    <div className="flex items-baseline gap-3 text-indigo-700">
                      <span>已贷记</span>
                      <span className="ml-auto tabular-nums">−{aud(detail.invoice.amount_credited_cents)}</span>
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
                    {detail.invoice.status !== 'draft' && (
                      <button type="button" onClick={printInvoice}
                              className="no-print min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700">
                        打印 / 存为 PDF
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

              {(detail.creditNotes || []).length > 0 && (
                <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-200 text-xs font-bold">关联贷记单与退款</div>
                  {(detail.creditNotes || []).map(note => (
                    <div key={note.id} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2 border-b border-gray-100 last:border-0 text-[11px]">
                      <span className="font-bold">{note.number || '贷记单草稿'}</span>
                      <span>{note.status === 'issued' ? '已开具' : note.status}</span>
                      <span className="tabular-nums">−{aud(note.total_cents)}</span>
                      {note.refund_id && <span className="text-green-700">已退款 {aud(note.refunded_cents)}</span>}
                      {note.payment_status && <span className="text-gray-500">付款：{note.payment_status}</span>}
                      {note.reason && <span className="text-gray-500 truncate">{note.reason}</span>}
                      <button type="button" onClick={() => openCreditNote(note.id)} className="ml-auto min-h-[44px] px-2 rounded-lg border border-gray-200 text-[11px] font-bold text-indigo-700">查看 / 打印贷记单</button>
                    </div>
                  ))}
                </div>
              )}

              {creditNoteDetail && (
                <div className="credit-note-document space-y-2">
                  <InvoicePrintableDocument document={creditNoteDetail.document} />
                  <button type="button" onClick={() => printCustomerDocument(creditNoteDetail.document)} className="no-print min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700">打印贷记单</button>
                </div>
              )}

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
                    overdue: '已逾期', credited: '已贷记', credit_settled: '充值已结算',
                    xero_pushed: '已推送 Xero',
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


/* A single payer picker for both invoice and (later) settlement entry points.
   Students are service subjects; this component only resolves the tenant-scoped
   billing account that receives the document. */
export function BillingAccountPicker({
  api, accounts, students = [], studentPicker, value, onStateChange,
  payerError, onPayerError, initialStudentId = '', hideStudentSelector = false,
}) {
  const StudentPicker = studentPicker;
  const payerErrorRef = useRef(null);
  const [mode, setMode] = useState('student');
  const [studentId, setStudentId] = useState(initialStudentId || '');
  const [studentPayers, setStudentPayers] = useState([]);
  const [studentSuggestion, setStudentSuggestion] = useState(null);
  const [studentLoading, setStudentLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [creating, setCreating] = useState(false);
  /* A suggested payer is data, not authorization to create a record.  Keep
     the confirmation separate so invoice drafts and settlement billing cannot
     accidentally POST a payer while the operator is still reviewing it. */
  const [createConfirmed, setCreateConfirmed] = useState(false);
  const [kind, setKind] = useState('person');
  const [fields, setFields] = useState({
    name: '', contactName: '', email: '', mobile: '', companyName: '', abn: '',
    billingAddress: '', paymentTermsDays: '14', purchaseOrderRef: '', language: 'en', note: '',
  });
  const [studentDraft, setStudentDraft] = useState({
    kind: 'family', name: '', contactName: '', email: '', mobile: '',
    billingAddress: '', paymentTermsDays: '14', language: 'en',
  });
  const [linkedStudentIds, setLinkedStudentIds] = useState([]);

  const setField = key => e => {
    setCreateConfirmed(false);
    setFields(prev => ({...prev, [key]: e.target.value}));
  };
  const setStudentDraftField = key => e => {
    setCreateConfirmed(false);
    setStudentDraft(prev => ({...prev, [key]: e.target.value}));
  };
  const selectedStudent = students.find(student => String(student.id) === String(studentId));

  useEffect(() => {
    if (initialStudentId === undefined) return;
    setMode('student');
    setStudentId(initialStudentId || '');
    setQuery('');
    setCreating(false);
    setCreateConfirmed(false);
    setLinkedStudentIds(initialStudentId ? [initialStudentId] : []);
  }, [initialStudentId]);

  useEffect(() => {
    if (payerError && payerErrorRef.current) payerErrorRef.current.focus();
  }, [payerError]);

  useEffect(() => {
    if (mode !== 'student' || !studentId) {
      setStudentPayers([]);
      setStudentSuggestion(null);
      setStudentLoading(false);
      if (mode === 'student') onStateChange({mode, accountId: '', createPayload: null, linkedStudentIds: []});
      return undefined;
    }
    let alive = true;
    setStudentLoading(true);
    onPayerError('');
    api(`/billing/accounts?studentId=${encodeURIComponent(studentId)}&limit=100`)
      .then(data => {
        if (!alive) return;
        const payers = data.accounts || [];
        setStudentPayers(payers);
        setStudentSuggestion(data.suggestedPayer || null);
        if (payers.length === 0) {
          const suggestion = data.suggestedPayer || {};
          setStudentDraft(prev => ({
            ...prev,
            kind: suggestion.kind || 'family',
            name: suggestion.name || selectedStudent?.name || '',
            contactName: suggestion.contactName || '',
            email: suggestion.email || '',
            mobile: suggestion.mobile || '',
            billingAddress: suggestion.billingAddress || '',
            paymentTermsDays: String(suggestion.paymentTermsDays ?? prev.paymentTermsDays ?? '14'),
            language: suggestion.language || 'en',
          }));
        }
        if (payers.length === 1) onStateChange({mode, accountId: String(payers[0].id), createPayload: null, linkedStudentIds: [studentId]});
        else if (!payers.some(payer => String(payer.id) === String(value))) onStateChange({mode, accountId: '', createPayload: null, linkedStudentIds: []});
      })
      .catch(error => { if (alive) onPayerError(`付款方加载失败：${error.message}`); })
      .finally(() => { if (alive) setStudentLoading(false); });
    return () => { alive = false; };
  }, [api, mode, studentId, selectedStudent?.name]);

  useEffect(() => {
    if (mode !== 'custom' || !query.trim()) {
      setSearchResults([]);
      return undefined;
    }
    let alive = true;
    const timer = setTimeout(() => {
      api(`/billing/accounts?q=${encodeURIComponent(query.trim())}&limit=50`)
        .then(data => { if (alive) setSearchResults(data.accounts || []); })
        .catch(error => { if (alive) onPayerError(`付款方搜索失败：${error.message}`); });
    }, 180);
    return () => { alive = false; clearTimeout(timer); };
  }, [api, mode, query]);

  const createPayload = useMemo(() => {
    if (mode === 'student') {
      if (!studentId || studentPayers.length > 0 || !createConfirmed) return null;
      if (!String(studentDraft.name || '').trim()) return null;
      return {
        ...studentDraft,
        kind: studentDraft.kind || 'family',
        name: String(studentDraft.name).trim(),
        studentId,
      };
    }
    if (!creating || !createConfirmed) return null;
    /* An organisation's legal/display name is its company name. Keep an
       optional contact separate so a contact cannot become the invoice
       recipient identity by accident. */
    const displayName = String(kind === 'organisation' ? fields.companyName : fields.name).trim();
    if (!displayName) return null;
    return {
      ...fields,
      name: displayName,
      contactName: kind === 'organisation'
        ? String(fields.contactName || fields.name).trim()
        : fields.contactName,
      kind,
      studentIds: linkedStudentIds,
    };
  }, [mode, studentId, studentPayers, createConfirmed, studentDraft, creating, kind, fields, linkedStudentIds]);

  useEffect(() => {
    onStateChange({
      mode,
      accountId: mode === 'student' && studentPayers.length === 1
        ? String(studentPayers[0].id) : String(value || ''),
      createPayload,
      createConfirmed,
      linkedStudentIds: mode === 'student' ? (studentId ? [studentId] : []) : linkedStudentIds,
    });
  }, [mode, value, studentId, studentPayers, linkedStudentIds, createPayload, createConfirmed]);

  const chooseMode = nextMode => {
    setMode(nextMode);
    onPayerError('');
    setCreating(false);
    setCreateConfirmed(false);
    setQuery('');
    setLinkedStudentIds([]);
    if (nextMode === 'student') onStateChange({mode: nextMode, accountId: '', createPayload: null, linkedStudentIds: []});
  };

  const visibleAccounts = query.trim() ? searchResults : accounts.slice(0, 20);
  const selectedPayer = [...accounts, ...studentPayers, ...searchResults]
    .find(payer => String(payer.id) === String(value));

  const toggleLinkedStudent = studentKey => {
    setLinkedStudentIds(prev => prev.includes(String(studentKey))
      ? prev.filter(id => id !== String(studentKey))
      : [...prev, String(studentKey)]);
    setCreateConfirmed(false);
  };

  return (
    <fieldset className="space-y-2" aria-describedby="billing-account-help">
      <legend className="block text-xs font-bold text-gray-600">开给谁</legend>
      <p id="billing-account-help" className="text-[11px] text-gray-500">
        学员是服务对象；付款方是发票收件人。两条入口最终都选择同一个付款方记录。
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <button type="button" onClick={() => chooseMode('student')}
                aria-pressed={mode === 'student'}
                className={`min-h-[44px] rounded-xl border text-sm font-bold ${mode === 'student' ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-gray-200 bg-white text-gray-700'}`}>
          已有学员
        </button>
        <button type="button" onClick={() => chooseMode('custom')}
                aria-pressed={mode === 'custom'}
                className={`min-h-[44px] rounded-xl border text-sm font-bold ${mode === 'custom' ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-gray-200 bg-white text-gray-700'}`}>
          其他个人或机构
        </button>
      </div>

      {mode === 'student' && (
        <div className="space-y-2 rounded-xl border border-gray-200 p-3">
          {!hideStudentSelector && StudentPicker ? (
            <StudentPicker students={students} value={studentId || null}
              onChange={next => { setCreateConfirmed(false); setStudentId(next || ''); onStateChange({mode, accountId: '', createPayload: null, linkedStudentIds: next ? [next] : []}); }}
              placeholder="搜索并选择学员" showBal={false} />
          ) : !hideStudentSelector ? (
            <select value={studentId} onChange={event => { setCreateConfirmed(false); setStudentId(event.target.value); }}
                    aria-label="选择学员" className="w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
              <option value="">请选择学员</option>
              {students.map(student => <option key={student.id} value={student.id}>{student.name}</option>)}
            </select>
          ) : (
            <p className="text-xs text-gray-600">当前学员：<strong>{selectedStudent?.name || '—'}</strong>；下面只选择这次发票的付款方。</p>
          )}
          {studentLoading && <p className="text-[11px] text-gray-500">正在查询该学员的付款方…</p>}
          {!studentLoading && studentId && studentPayers.length === 0 && (
            <div className="space-y-2 rounded-lg bg-amber-50 border border-amber-100 p-3">
              <p className="text-xs font-bold text-amber-900">0 个付款方：这个学员还没有付款方</p>
              <p className="text-[11px] text-amber-800">资料只用于预填；填写或修改后，必须明确点击“创建并使用此付款方”才会创建记录。</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <label className="block text-[11px] text-gray-600">付款方类型
                  <select value={studentDraft.kind} onChange={setStudentDraftField('kind')}
                          className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                    <option value="person">个人 / Person</option>
                    <option value="family">家庭 / Family</option>
                    <option value="organisation">机构 / Organisation</option>
                  </select>
                </label>
                <label className="block text-[11px] text-gray-600">姓名 / 名称 *
                  <input value={studentDraft.name} onChange={setStudentDraftField('name')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-[11px] text-gray-600">联系人（可选）
                  <input value={studentDraft.contactName} onChange={setStudentDraftField('contactName')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-[11px] text-gray-600">邮箱 / Email
                  <input type="email" value={studentDraft.email} onChange={setStudentDraftField('email')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-[11px] text-gray-600">手机 / Mobile
                  <input value={studentDraft.mobile} onChange={setStudentDraftField('mobile')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-[11px] text-gray-600">语言 / Language
                  <select value={studentDraft.language} onChange={setStudentDraftField('language')}
                          className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                    <option value="zh">中文</option>
                    <option value="en">English</option>
                  </select>
                </label>
              </div>
              <label className="block text-[11px] text-gray-600">账单地址 / Billing address（可选）
                <input value={studentDraft.billingAddress} onChange={setStudentDraftField('billingAddress')}
                       className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
              </label>
              <label className="block text-[11px] text-gray-600">付款期限 / Payment terms（天）
                <input type="number" min="0" max="3650" value={studentDraft.paymentTermsDays}
                       onChange={setStudentDraftField('paymentTermsDays')}
                       className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
              </label>
              <button type="button" disabled={!String(studentDraft.name || '').trim()}
                      onClick={() => { setCreateConfirmed(true); onStateChange({mode, accountId: '', createPayload: null, linkedStudentIds: [studentId], createConfirmed: true}); }}
                      className="w-full min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
                创建并使用此付款方 <span className="text-[11px] font-normal">/ Create and use this payer</span>
              </button>
              {createConfirmed && <p className="text-[11px] font-bold text-emerald-700">已确认创建；提交草稿或开票时才会写入付款方记录。</p>}
            </div>
          )}
          {!studentLoading && studentPayers.length > 0 && (
            <label className="block text-xs text-gray-500">已关联付款方（{studentPayers.length} 个，{studentPayers.length === 1 ? '已默认选中，可切换' : '不会默认选择，必须明确选择'}）
              <select value={value || ''} onChange={event => { setCreateConfirmed(false); onStateChange({mode, accountId: event.target.value, createPayload: null, linkedStudentIds: [studentId]}); }}
                      aria-describedby="billing-account-payer-help"
                      className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                <option value="">请选择付款方</option>
                {studentPayers.map(payer => <option key={payer.id} value={payer.id}>{payer.name} · {payer.kind}{payer.email ? ` · ${payer.email}` : ''}{payer.mobile ? ` · ${payer.mobile}` : ''}</option>)}
              </select>
              <span id="billing-account-payer-help" className="block mt-1 text-[11px] text-gray-400">
                {studentPayers.length === 1 ? `已默认选中：${studentPayers[0].name}（${studentPayers[0].kind || 'payer'}；${studentPayers[0].email || studentPayers[0].mobile || '无联系方式'}）` : '有多个付款方时不会自动猜测或合并；请核对类型和联系方式后选择。'}
                <span className="block mt-1">付款方快照会在开具时冻结；之后修改付款方资料不会改写已开具发票。</span>
              </span>
            </label>
          )}
        </div>
      )}

      {mode === 'custom' && (
        <div className="space-y-2 rounded-xl border border-gray-200 p-3">
          <label className="block text-xs text-gray-500">先搜索已有付款方 / Search before creating
            <input value={query} onChange={event => { setQuery(event.target.value); setCreateConfirmed(false); onPayerError(''); }}
                   placeholder="姓名、机构、邮箱、电话或 ABN" aria-label="搜索已有付款方"
                   className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
          </label>
          {visibleAccounts.length > 0 && (
            <div className="max-h-40 overflow-y-auto rounded-lg border border-gray-100">
              {visibleAccounts.map(payer => (
                <button key={payer.id} type="button" onClick={() => { setCreateConfirmed(false); onStateChange({mode, accountId: String(payer.id), createPayload: null, linkedStudentIds}); setCreating(false); }}
                        className={`w-full min-h-[44px] px-3 text-left text-sm border-b border-gray-100 last:border-0 ${String(payer.id) === String(value) ? 'bg-indigo-50' : 'bg-white hover:bg-gray-50'}`}>
                  <span className="font-bold">{payer.name}</span>
                  <span className="ml-2 text-[11px] text-gray-500">{payer.kind}{payer.email ? ` · ${payer.email}` : ''}{payer.mobile ? ` · ${payer.mobile}` : ''}</span>
                </button>
              ))}
            </div>
          )}
          {selectedPayer && !creating && <p className="text-xs text-indigo-700">已选付款方：{selectedPayer.name}</p>}
          <button type="button" disabled={!query.trim()} onClick={() => { setCreating(true); setCreateConfirmed(false); onStateChange({mode, accountId: '', createPayload: null, linkedStudentIds}); }}
                  className="min-h-[44px] px-3 rounded-xl border border-indigo-200 bg-white text-xs font-bold text-indigo-700 disabled:opacity-50">
            {query.trim() ? '仍未找到？新建个人或机构付款方' : '先搜索，仍未找到再新建付款方'}
          </button>
          {!query.trim() && <p className="text-[11px] text-gray-500">为避免同名重复，请先搜索姓名、机构、邮箱、电话或 ABN。</p>}
          {creating && (
            <div className="space-y-2 border-t border-gray-100 pt-2">
              <label className="block text-xs text-gray-500">类型
                <select value={kind} onChange={event => { setKind(event.target.value); setCreateConfirmed(false); }}
                        className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                  <option value="person">个人</option>
                  <option value="organisation">机构</option>
                  <option value="family">个人/家庭（兼容旧类型）</option>
                </select>
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <label className="block text-xs text-gray-500">{kind === 'organisation' ? '联系人姓名（可选）' : '姓名'}
                  <input value={kind === 'organisation' ? fields.contactName : fields.name}
                         onChange={setField(kind === 'organisation' ? 'contactName' : 'name')}
                         aria-describedby="billing-payer-name-error"
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                {kind === 'organisation' && (
                  <label className="block text-xs text-gray-500">机构名称
                    <input value={fields.companyName} onChange={setField('companyName')}
                           className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                  </label>
                )}
                {kind !== 'organisation' && (
                  <label className="block text-xs text-gray-500">联系人（可选）
                    <input value={fields.contactName} onChange={setField('contactName')}
                           className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                  </label>
                )}
                <label className="block text-xs text-gray-500">邮箱
                  <input type="email" value={fields.email} onChange={setField('email')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-500">电话
                  <input value={fields.mobile} onChange={setField('mobile')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-500">ABN（可选）
                  <input value={fields.abn} onChange={setField('abn')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
              </div>
              <label className="block text-xs text-gray-500">账单地址（可选）
                <input value={fields.billingAddress} onChange={setField('billingAddress')}
                       className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
              </label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <label className="block text-xs text-gray-500">付款期限（天）
                  <input type="number" min="0" max="3650" value={fields.paymentTermsDays}
                         onChange={setField('paymentTermsDays')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-500">PO reference（可选）
                  <input value={fields.purchaseOrderRef} onChange={setField('purchaseOrderRef')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-500">语言
                  <select value={fields.language} onChange={setField('language')}
                          className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                    <option value="en">English</option>
                    <option value="zh">中文</option>
                  </select>
                </label>
              </div>
              <div className="block text-xs text-gray-500">可选关联服务对象（0..N）
                <div className="flex flex-wrap gap-2 mt-1" aria-label="可选关联服务对象">
                  {students.map(student => {
                    const selected = linkedStudentIds.includes(String(student.id));
                    return (
                      <button key={student.id} type="button" className={`payer-chip min-h-[44px] px-3 rounded-full border text-xs font-bold ${selected ? 'border-indigo-500 bg-indigo-50 text-indigo-700' : 'border-gray-200 bg-white text-gray-600'}`}
                              aria-pressed={selected} onClick={() => toggleLinkedStudent(student.id)}>
                        {selected ? '✓ ' : ''}{student.name}
                      </button>
                    );
                  })}
                  {!students.length && <span className="text-[11px] text-gray-400">暂无可关联服务对象</span>}
                </div>
              </div>
              <button type="button" disabled={!String(kind === 'organisation' ? fields.companyName : fields.name).trim()}
                      onClick={() => setCreateConfirmed(true)}
                      className="w-full min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
                创建并使用此付款方 <span className="text-[11px] font-normal">/ Create and use this payer</span>
              </button>
              {createConfirmed && <p className="text-[11px] font-bold text-emerald-700">已确认创建；提交草稿或开票时才会写入付款方记录。</p>}
            </div>
          )}
        </div>
      )}
      {payerError && <p id="billing-payer-name-error" ref={payerErrorRef} tabIndex="-1" role="alert" className="text-xs text-red-600">{payerError}</p>}
    </fieldset>
  );
}

/* New invoice: save a draft only. Issuing is a separate action because it
   allocates a permanent number and freezes the document identity. */
function NewInvoiceDialog({ api, accounts, students = [], studentPicker, busy, onClose, onSubmit }) {
  const Picker = studentPicker;
  const payerErrorRef = useRef(null);
  const invoiceDraftRequestRef = useRef({signature: '', id: ''});
  const [payerState, setPayerState] = useState({accountId: '', createPayload: null, linkedStudentIds: [], mode: 'student'});
  const [payerError, setPayerError] = useState('');
  const [possibleDuplicates, setPossibleDuplicates] = useState([]);
  const [allowPossibleDuplicate, setAllowPossibleDuplicate] = useState(false);
  const [note, setNote] = useState('');
  const [lines, setLines] = useState([
    {description: '', quantity: '1', unitPrice: '', taxRateBp: '1000', sourceKind: 'manual', studentId: ''},
  ]);

  const setLine = (i, key) => (e) => setLines(rows =>
    rows.map((row, idx) => idx === i ? {...row, [key]: e.target.value} : row));
  const total = lines.reduce((sum, line) => {
    const net = Number(line.quantity || 0) * Number(line.unitPrice || 0);
    return sum + net + net * (Number(line.taxRateBp || 0) / 10000);
  }, 0);
  const payerReady = Boolean(payerState.accountId || payerState.createPayload);
  const ready = payerReady && lines.some(l => l.description.trim() && Number(l.unitPrice) > 0);

  const nextInvoiceDraftRequestId = signature => {
    if (invoiceDraftRequestRef.current.signature !== signature) {
      const id = (window.crypto && window.crypto.randomUUID)
        ? window.crypto.randomUUID()
        : `invoice-draft-${Date.now()}-${Math.random().toString(16).slice(2)}`;
      invoiceDraftRequestRef.current = {signature, id};
    }
    return invoiceDraftRequestRef.current.id;
  };

  useEffect(() => {
    if (payerError && payerErrorRef.current) payerErrorRef.current.focus();
  }, [payerError]);

  useEffect(() => {
    const closeOnEscape = event => {
      if (event.key === 'Escape' && !busy) onClose();
    };
    document.addEventListener('keydown', closeOnEscape);
    return () => document.removeEventListener('keydown', closeOnEscape);
  }, [busy, onClose]);

  const submit = async () => {
    setPayerError('');
    try {
      let payer = null;
      if (payerState.accountId) {
        payer = {accountId: String(payerState.accountId)};
      } else if (payerState.createPayload) {
        const {studentId: _studentId, studentIds: _studentIds, ...create} = payerState.createPayload;
        payer = {create, linkedStudentIds: payerState.linkedStudentIds};
      }
      if (!payer) {
        setPayerError('请选择或创建付款方。');
        return;
      }
      const aggregateLines = lines.map(line => ({
        description: line.description.trim(),
        quantity: line.quantity,
        unitPriceCents: Math.round(Number(line.unitPrice) * 100),
        taxRateBp: Number(line.taxRateBp),
        sourceKind: line.sourceKind || 'manual',
        studentId: line.studentId || null,
      }));
      const signature = JSON.stringify({payer, note, lines: aggregateLines, allowPossibleDuplicate});
      const requestId = nextInvoiceDraftRequestId(signature);
      await onSubmit({
        requestId,
        payer,
        invoice: {note},
        lines: aggregateLines,
        allowPossibleDuplicate,
      });
      setPossibleDuplicates([]);
      setAllowPossibleDuplicate(false);
    } catch (error) {
      /* Keep payer fields, note, and line items in place so a validation/network
         failure is recoverable rather than forcing the operator to start over. */
      if (error.status === 409 && error.details?.possibleDuplicates) {
        setPossibleDuplicates(error.details.possibleDuplicates);
        setAllowPossibleDuplicate(false);
      }
      setPayerError(error.message || '付款方保存失败，请检查输入后重试。');
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm">
      <div className="bg-white w-full sm:max-w-xl rounded-t-2xl sm:rounded-2xl p-5 space-y-3 max-h-[90vh] overflow-y-auto" role="dialog" aria-modal="true" aria-labelledby="new-invoice-title">
        <div>
          <p id="new-invoice-title" className="text-lg font-bold text-gray-800">新建发票</p>
          <p className="text-sm text-gray-500 mt-1">
            先存成草稿。复核无误后在列表里开具 —— 开具会定号码和到期日，之后金额不能再改。
          </p>
        </div>

        <BillingAccountPicker api={api} accounts={accounts} students={students} studentPicker={Picker}
          value={payerState.accountId} onStateChange={setPayerState}
          payerError={payerError} onPayerError={setPayerError} />

        {possibleDuplicates.length > 0 && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2" role="alert">
            <p className="text-xs font-bold text-amber-900">发现可能重复的付款方，请先核对</p>
            <ul className="text-[11px] text-amber-900 list-disc pl-4 space-y-1">
              {possibleDuplicates.map(payer => <li key={payer.id}>{payer.name} · {payer.kind}{payer.email ? ` · ${payer.email}` : ''}{payer.mobile ? ` · ${payer.mobile}` : ''}</li>)}
            </ul>
            <label className="flex items-start gap-2 min-h-[44px] text-xs text-amber-900">
              <input type="checkbox" checked={allowPossibleDuplicate} onChange={event => setAllowPossibleDuplicate(event.target.checked)} className="mt-1 w-5 h-5 accent-amber-600" />
              <span>我已核对并明确允许新建，不自动合并；继续时会记录原因和候选付款方。</span>
            </label>
          </div>
        )}

        <div className="space-y-2">
          {lines.map((line, i) => (
            <div key={i} className="border border-gray-200 rounded-xl p-3 space-y-2">
              <label className="block text-xs text-gray-500">项目说明
                <input value={line.description} onChange={setLine(i, 'description')}
                       placeholder="例如「第三学期学费」" aria-describedby={`invoice-line-${i}-help`}
                       className="w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
              </label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                <label className="block text-xs text-gray-400">数量
                  <input type="number" min="0" step="0.01" value={line.quantity} onChange={setLine(i, 'quantity')}
                         className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
                </label>
                <label className="block text-xs text-gray-400">单价（未税）
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
              <label className="block text-xs text-gray-400">收入分类
                <select value={line.sourceKind} onChange={setLine(i, 'sourceKind')}
                        className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                  <option value="manual">手工收入</option>
                  <option value="package">课包/课时收入（仅分类）</option>
                </select>
              </label>
              <label className="block text-xs text-gray-400">服务对象（可选）
                {Picker ? (
                  <div className="mt-1">
                    <Picker students={students} value={line.studentId || null}
                      onChange={value => setLines(rows => rows.map((row, idx) => idx === i ? {...row, studentId: value || ''} : row))}
                      placeholder="搜索并选择学员（仅报告归属）" showBal={false} />
                  </div>
                ) : (
                  <select value={line.studentId} onChange={setLine(i, 'studentId')}
                          className="block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm">
                    <option value="">不关联学员</option>
                    {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                )}
                <span id={`invoice-line-${i}-help`} className="block mt-1 text-[11px] text-gray-400">只表达收入报告归属，不改变课时余额；未选择时发送 null。</span>
              </label>
            </div>
          ))}
          <button type="button"
                  onClick={() => setLines(rows => [...rows, {description: '', quantity: '1', unitPrice: '', taxRateBp: '1000', sourceKind: 'manual', studentId: ''}])}
                  className="min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-700">
            再加一行
          </button>
        </div>

        <label className="block text-xs text-gray-500">备注（选填）
          <input value={note} onChange={e => setNote(e.target.value)}
                 className="w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" />
        </label>

        <p className="text-sm text-gray-500">合计约 {aud(Math.round(total * 100))}（含税）</p>

        <div className="flex gap-2">
          <button type="button" onClick={onClose} disabled={busy}
                  className="flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50">
            取消
          </button>
          <button type="button" onClick={submit} disabled={busy || !ready}
                  className="flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50">
            存为草稿
          </button>
        </div>
      </div>
    </div>
  );
}
