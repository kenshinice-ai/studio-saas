(() => {
  // legacy-root/src/panels/_shared.jsx
  var aud = (cents) => (Number(cents || 0) / 100).toLocaleString("en-AU", { style: "currency", currency: "AUD" });
  var fmtApiDate = (value) => {
    if (!value) return "—";
    const iso3 = String(value).match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso3) return `${iso3[3]}/${iso3[2]}/${iso3[1]}`;
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value);
    const pad = (n) => String(n).padStart(2, "0");
    return `${pad(parsed.getDate())}/${pad(parsed.getMonth() + 1)}/${parsed.getFullYear()}`;
  };
  var monthRange = () => {
    const now = /* @__PURE__ */ new Date();
    const iso3 = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return { from: iso3(new Date(now.getFullYear(), now.getMonth(), 1)), to: iso3(now) };
  };

  // legacy-root/src/panels/filter_bar.jsx
  var { useMemo } = React;
  var RANGE_PRESETS = [
    { key: "this_month", label: "本月" },
    { key: "last_month", label: "上月" },
    { key: "last_30", label: "近 30 天" }
  ];
  var iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  function presetRange(key, today = /* @__PURE__ */ new Date()) {
    const y = today.getFullYear(), m = today.getMonth();
    if (key === "this_month") return { start: iso(new Date(y, m, 1)), end: iso(new Date(y, m + 1, 0)) };
    if (key === "last_month") return { start: iso(new Date(y, m - 1, 1)), end: iso(new Date(y, m, 0)) };
    if (key === "last_30") {
      const from = new Date(today);
      from.setDate(from.getDate() - 29);
      return { start: iso(from), end: iso(today) };
    }
    return { start: "", end: "" };
  }
  function FilterBar({
    range,
    onRange,
    searchPlaceholder = "搜索…",
    query,
    onQuery,
    buckets,
    bucket,
    onBucket,
    total,
    totalNoun = "条",
    extra = null,
    extraDirty = false,
    onClearExtra = null
  }) {
    const dirty = useMemo(() => Boolean(
      query && query.trim() || buckets && bucket && bucket !== buckets[0]?.key || range && (range.start || range.end) || extraDirty
    ), [query, bucket, buckets, range, extraDirty]);
    function clearAll() {
      if (onQuery) onQuery("");
      if (onBucket && buckets?.length) onBucket(buckets[0].key);
      if (onRange) onRange(presetRange("this_month"));
      if (onClearExtra) onClearExtra();
    }
    return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-3 space-y-2" }, range && /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-end gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-[11px] text-gray-500" }, "起", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: range.start || "",
        onChange: (e) => onRange({ ...range, start: e.target.value }),
        className: "block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "text-[11px] text-gray-500" }, "止", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: range.end || "",
        onChange: (e) => onRange({ ...range, end: e.target.value }),
        className: "block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5" }, RANGE_PRESETS.map((preset) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: preset.key,
        type: "button",
        onClick: () => onRange(presetRange(preset.key)),
        className: "min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      preset.label
    )))), extra, query !== null && query !== void 0 && /* @__PURE__ */ React.createElement(
      "input",
      {
        value: query,
        onChange: (e) => onQuery(e.target.value),
        placeholder: searchPlaceholder,
        className: "w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    ), buckets && buckets.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5" }, buckets.map((item) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: item.key,
        type: "button",
        onClick: () => onBucket(item.key),
        className: `min-h-[44px] px-3 rounded-xl text-xs font-bold border ${bucket === item.key ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-700 border-gray-200"}`
      },
      item.label,
      typeof item.count === "number" ? ` ${item.count}` : ""
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 text-[11px] text-gray-500" }, /* @__PURE__ */ React.createElement("span", null, `共 ${total} ${totalNoun}`), dirty && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: clearAll,
        className: "min-h-[44px] px-2 font-bold text-indigo-600"
      },
      "清除筛选"
    )));
  }

  // legacy-root/src/panels/billing.jsx
  var { useState, useEffect, useCallback, useMemo: useMemo2, useRef } = React;
  var STATUS_LABEL = {
    draft: "草稿",
    issued: "已开具",
    part_paid: "部分付款",
    paid: "已付清",
    void: "已作废"
  };
  function invoiceFinancialState(invoice) {
    const total = Math.max(0, Number(invoice?.total_cents || 0));
    const paid = Math.max(0, Number(invoice?.amount_paid_cents || 0));
    const credited = Math.max(0, Number(invoice?.amount_credited_cents || 0));
    const refunded = Math.max(0, Number(invoice?.amount_refunded_cents || 0));
    const balance = Number.isFinite(Number(invoice?.balance_cents)) ? Number(invoice.balance_cents) : total - paid - credited;
    const netReceivedCents = Math.max(0, Number(invoice?.net_received_cents ?? paid - refunded));
    let creditState = "none";
    if (total > 0 && credited >= total) creditState = "fully_credited";
    else if (credited > 0) creditState = "partially_credited";
    return { total, paid, credited, refunded, balance, netReceivedCents, creditState };
  }
  var CREDIT_STATE_LABEL = {
    partially_credited: "部分贷记",
    fully_credited: "已全额贷记"
  };
  var isOverdue = (invoice) => {
    if (!["issued", "part_paid"].includes(invoice.status)) return false;
    if (!invoice.due_date) return false;
    const due = new Date(invoice.due_date);
    if (Number.isNaN(due.getTime())) return false;
    return due < new Date((/* @__PURE__ */ new Date()).toDateString());
  };
  function StatusChip({ invoice }) {
    const overdue = isOverdue(invoice);
    const financial = invoiceFinancialState(invoice);
    const cls = overdue ? "bg-red-50 text-red-700 border-red-200" : invoice.status === "paid" ? "bg-green-50 text-green-700 border-green-200" : invoice.status === "part_paid" ? "bg-blue-50 text-blue-700 border-blue-200" : invoice.status === "draft" ? "bg-gray-100 text-gray-600 border-gray-200" : "bg-gray-50 text-gray-600 border-gray-200";
    const label = overdue ? "逾期" : STATUS_LABEL[invoice.status] || invoice.status;
    return /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1" }, /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${cls}` }, label), financial.creditState !== "none" && /* @__PURE__ */ React.createElement("span", { className: "text-[10px] font-bold px-1.5 py-0.5 rounded border border-indigo-200 bg-indigo-50 text-indigo-700 whitespace-nowrap" }, CREDIT_STATE_LABEL[financial.creditState]));
  }
  function Kpi({ label, value, sub, tone }) {
    const toneCls = tone === "alert" ? "text-red-600" : tone === "good" ? "text-green-700" : "text-gray-900";
    return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold uppercase tracking-wide text-gray-500" }, label), /* @__PURE__ */ React.createElement("p", { className: `text-xl font-bold tabular-nums ${toneCls}` }, value), sub && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500" }, sub));
  }
  function printableAddress(address) {
    if (!address) return "";
    if (typeof address === "string") return address;
    return [address.line1, address.line2, address.suburb, address.state, address.postcode, address.country].filter(Boolean).join(", ");
  }
  function InvoicePrintableDocument({ document: document2 }) {
    if (!document2) return null;
    const meta = document2.document || {};
    const supplier = document2.supplier || {};
    const recipient = document2.recipient || {};
    const totals = document2.totals || {};
    const payment = document2.paymentSummary || {};
    const bank = supplier.bank || {};
    const issued = meta.status !== "draft";
    const title = meta.kind === "credit_note" ? "Credit Note" : supplier.gstRegistered ? "Tax Invoice" : "Invoice";
    const status = meta.statusLabel || meta.status || "";
    const optional = (label, value) => value ? /* @__PURE__ */ React.createElement("div", { className: "invoice-field", key: label }, /* @__PURE__ */ React.createElement("dt", null, label), /* @__PURE__ */ React.createElement("dd", null, value)) : null;
    return /* @__PURE__ */ React.createElement("article", { className: "invoice-customer-document bg-white text-gray-900 border border-gray-200 rounded-xl p-6 sm:p-8" }, /* @__PURE__ */ React.createElement("header", { className: "flex flex-wrap items-start justify-between gap-6 border-b border-gray-300 pb-5" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-2xl font-bold tracking-tight" }, title), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1" }, status)), /* @__PURE__ */ React.createElement("div", { className: "text-right text-xs tabular-nums" }, meta.number && /* @__PURE__ */ React.createElement("p", { className: "font-bold text-base" }, meta.number), meta.issueDate && /* @__PURE__ */ React.createElement("p", null, "Issue date: ", fmtApiDate(meta.issueDate)), meta.dueDate && /* @__PURE__ */ React.createElement("p", null, "Due date: ", fmtApiDate(meta.dueDate)), /* @__PURE__ */ React.createElement("p", null, "Currency: ", meta.currency || "AUD"), !issued && /* @__PURE__ */ React.createElement("p", { className: "invoice-draft-watermark", "aria-label": "Draft" }, "DRAFT"))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-6 py-5 border-b border-gray-200 text-xs" }, /* @__PURE__ */ React.createElement("section", null, /* @__PURE__ */ React.createElement("h2", { className: "font-bold text-gray-500 uppercase tracking-wide mb-2" }, "Supplier"), /* @__PURE__ */ React.createElement("dl", { className: "space-y-1" }, optional("Legal name", supplier.legalName), optional("Trading name", supplier.tradingName), optional("ABN", supplier.abn), optional("Address", printableAddress(supplier.address)), optional("Email", supplier.contactEmail), optional("Phone", supplier.contactPhone), optional("Website", supplier.website))), /* @__PURE__ */ React.createElement("section", null, /* @__PURE__ */ React.createElement("h2", { className: "font-bold text-gray-500 uppercase tracking-wide mb-2" }, "Bill to"), /* @__PURE__ */ React.createElement("dl", { className: "space-y-1" }, optional("Name", recipient.displayName), optional("Company", recipient.companyName), optional("Contact", recipient.contactName), optional("ABN", recipient.abn), optional("Address", recipient.billingAddress), optional("Email", recipient.email), optional("Mobile", recipient.mobile), optional("PO reference", recipient.purchaseOrderRef)))), /* @__PURE__ */ React.createElement("table", { className: "w-full text-xs my-5 invoice-lines-table" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "border-b border-gray-300 text-left" }, /* @__PURE__ */ React.createElement("th", { className: "py-2 pr-2" }, "Description"), /* @__PURE__ */ React.createElement("th", { className: "py-2 px-2 text-right" }, "Qty"), /* @__PURE__ */ React.createElement("th", { className: "py-2 px-2 text-right" }, "Unit"), /* @__PURE__ */ React.createElement("th", { className: "py-2 px-2 text-right" }, "Net"), /* @__PURE__ */ React.createElement("th", { className: "py-2 px-2 text-right" }, "Tax rate"), /* @__PURE__ */ React.createElement("th", { className: "py-2 pl-2 text-right" }, "Tax"), /* @__PURE__ */ React.createElement("th", { className: "py-2 pl-2 text-right" }, "Gross"))), /* @__PURE__ */ React.createElement("tbody", null, (document2.lines || []).map((line) => /* @__PURE__ */ React.createElement("tr", { key: line.id || `${line.description}-${line.quantity}`, className: "border-b border-gray-100 align-top" }, /* @__PURE__ */ React.createElement("td", { className: "py-2 pr-2" }, line.description), /* @__PURE__ */ React.createElement("td", { className: "py-2 px-2 text-right tabular-nums" }, line.quantity), /* @__PURE__ */ React.createElement("td", { className: "py-2 px-2 text-right tabular-nums" }, aud(line.unitPriceCents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 px-2 text-right tabular-nums" }, aud(line.netCents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 px-2 text-right tabular-nums" }, (Number(line.taxRateBp || 0) / 100).toFixed(2), "%"), /* @__PURE__ */ React.createElement("td", { className: "py-2 pl-2 text-right tabular-nums" }, aud(line.taxCents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 pl-2 text-right tabular-nums" }, aud(line.totalCents)))))), /* @__PURE__ */ React.createElement("div", { className: "ml-auto w-full max-w-sm space-y-1 text-xs tabular-nums" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between" }, /* @__PURE__ */ React.createElement("span", null, "Subtotal"), /* @__PURE__ */ React.createElement("span", null, aud(totals.subtotalCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between" }, /* @__PURE__ */ React.createElement("span", null, "GST / tax"), /* @__PURE__ */ React.createElement("span", null, aud(totals.taxCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between border-t border-gray-300 pt-2 font-bold text-sm" }, /* @__PURE__ */ React.createElement("span", null, "Total"), /* @__PURE__ */ React.createElement("span", null, aud(totals.totalCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between" }, /* @__PURE__ */ React.createElement("span", null, "Paid"), /* @__PURE__ */ React.createElement("span", null, aud(payment.amountPaidCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between" }, /* @__PURE__ */ React.createElement("span", null, "Refunded"), /* @__PURE__ */ React.createElement("span", null, aud(payment.amountRefundedCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between" }, /* @__PURE__ */ React.createElement("span", null, "Net received"), /* @__PURE__ */ React.createElement("span", null, aud(payment.netReceivedCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between" }, /* @__PURE__ */ React.createElement("span", null, "Credited"), /* @__PURE__ */ React.createElement("span", null, aud(payment.amountCreditedCents))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between font-bold" }, /* @__PURE__ */ React.createElement("span", null, "Balance"), /* @__PURE__ */ React.createElement("span", null, aud(payment.balanceCents)))), (meta.note || recipient.purchaseOrderRef || supplier.paymentNote || bank.accountName || (payment.payments || []).length > 0) && /* @__PURE__ */ React.createElement("footer", { className: "border-t border-gray-200 mt-6 pt-4 text-xs space-y-2" }, meta.note && /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("strong", null, "Notes:"), " ", meta.note), recipient.purchaseOrderRef && /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("strong", null, "PO reference:"), " ", recipient.purchaseOrderRef), supplier.paymentNote && /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("strong", null, "Payment:"), " ", supplier.paymentNote), bank.accountName && /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("strong", null, "Remittance:"), " ", bank.accountName, bank.bsb ? ` · BSB ${bank.bsb}` : "", bank.accountNo ? ` · ${bank.accountNo}` : ""), (payment.payments || []).map((item) => /* @__PURE__ */ React.createElement("p", { key: item.id || item.receivedAt }, /* @__PURE__ */ React.createElement("strong", null, "Payment received:"), " ", aud(item.amountCents), " · ", item.method || item.status))));
  }
  function BillingPanel({
    api,
    showToast,
    canIssue,
    canTakePayment,
    canExportData,
    tenantSlug: tenantSlug2,
    accountId,
    onClearAccount,
    students,
    studentPicker
  }) {
    const [invoices, setInvoices] = useState([]);
    const [selectedId, setSelectedId] = useState("");
    const [detail, setDetail] = useState(null);
    const [checked, setChecked] = useState(() => /* @__PURE__ */ new Set());
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState("");
    const [creating, setCreating] = useState(false);
    const [accounts, setAccounts] = useState([]);
    const [query, setQuery] = useState("");
    const [bucket, setBucket] = useState("all");
    const [range, setRange] = useState(() => ({ start: "", end: "" }));
    const [payerEdit, setPayerEdit] = useState(null);
    const [payerSaving, setPayerSaving] = useState(false);
    const [creditNoteDetail, setCreditNoteDetail] = useState(null);
    const load = useCallback(async () => {
      setLoading(true);
      try {
        const query2 = accountId ? `?accountId=${encodeURIComponent(accountId)}` : "";
        const data = await api(`/billing/invoices${query2}`);
        setInvoices(data.invoices || []);
        const payers = await api("/billing/accounts").catch(() => ({ accounts: [] }));
        setAccounts(payers.accounts || []);
        setError("");
      } catch (e) {
        setError(e.status === 403 ? "这个工作室尚未开通开票功能。" : `账单加载失败：${e.message}`);
      } finally {
        setLoading(false);
      }
    }, [api, accountId]);
    useEffect(() => {
      load();
    }, [load]);
    useEffect(() => {
      if (!selectedId) {
        setDetail(null);
        return;
      }
      let cancelled = false;
      api(`/billing/invoices/${selectedId}`).then((d) => {
        if (!cancelled) setDetail(d);
      }).catch((e) => {
        if (!cancelled) showToast(`发票详情加载失败：${e.message}`, "warn");
      });
      return () => {
        cancelled = true;
      };
    }, [selectedId, api]);
    const summary = useMemo2(() => {
      const issued = invoices.filter((i) => i.status !== "draft" && i.status !== "void");
      const drafts = invoices.filter((i) => i.status === "draft");
      const overdue = invoices.filter(isOverdue);
      const billed = issued.reduce((s, i) => s + Number(i.total_cents || 0), 0);
      const netReceivedCents = issued.reduce((s, i) => s + invoiceFinancialState(i).netReceivedCents, 0);
      const credited = issued.reduce((s, i) => s + invoiceFinancialState(i).credited, 0);
      const refunded = issued.reduce((s, i) => s + invoiceFinancialState(i).refunded, 0);
      return {
        billed,
        netReceivedCents,
        credited,
        refunded,
        drafts: drafts.length,
        overdueCents: overdue.reduce((s, i) => s + Number(i.balance_cents || 0), 0),
        overdueAccounts: new Set(overdue.map((i) => i.billing_account_id)).size,
        collectedPercent: billed > 0 ? Math.round(netReceivedCents / billed * 100) : null
      };
    }, [invoices]);
    const draftIds = useMemo2(
      () => invoices.filter((i) => i.status === "draft").map((i) => String(i.id)),
      [invoices]
    );
    const createInvoice = async (form) => {
      setBusy(true);
      try {
        const draft = await api("/billing/invoice-drafts", {
          method: "POST",
          body: JSON.stringify(form)
        });
        const invoiceId = draft.invoice?.id || draft.invoiceId;
        showToast("草稿已建好，复核后再开具", "success");
        setCreating(false);
        await load();
        setSelectedId(String(invoiceId));
      } catch (e) {
        showToast(`新建发票失败：${e.message}`, "error");
        throw e;
      } finally {
        setBusy(false);
      }
    };
    const visible = useMemo2(() => {
      const text = query.trim().toLowerCase();
      return invoices.filter((invoice) => {
        if (bucket === "overdue" && !isOverdue(invoice)) return false;
        if (bucket === "unpaid" && !(Number(invoice.balance_cents) > 0 && invoice.status !== "draft")) return false;
        if (bucket === "draft" && invoice.status !== "draft") return false;
        if (range.start && invoice.issue_date && String(invoice.issue_date) < range.start) return false;
        if (range.end && invoice.issue_date && String(invoice.issue_date) > range.end) return false;
        if (!text) return true;
        return `${invoice.account_name || ""} ${invoice.number || ""}`.toLowerCase().includes(text);
      });
    }, [invoices, query, bucket, range]);
    const buckets = useMemo2(() => [
      { key: "all", label: "全部", count: invoices.length },
      { key: "overdue", label: "逾期", count: invoices.filter(isOverdue).length },
      {
        key: "unpaid",
        label: "未付清",
        count: invoices.filter((i) => Number(i.balance_cents) > 0 && i.status !== "draft").length
      },
      { key: "draft", label: "草稿", count: invoices.filter((i) => i.status === "draft").length }
    ], [invoices]);
    const exportCsv = (view) => {
      if (!canExportData || !tenantSlug2) return;
      const params = new URLSearchParams({ view, includeDrafts: "0" });
      if (range.start) params.set("from", range.start);
      if (range.end) params.set("to", range.end);
      if (accountId) params.set("accountId", accountId);
      const link = document.createElement("a");
      link.href = `/s/${encodeURIComponent(tenantSlug2)}/v1/billing/invoices/export.csv?${params.toString()}`;
      link.download = `invoices-${view}.csv`;
      link.rel = "noopener";
      document.body.appendChild(link);
      link.click();
      link.remove();
      showToast(view === "summary" ? "发票汇总 CSV 已开始下载" : "发票行项目 CSV 已开始下载", "success");
    };
    const checkedDrafts = useMemo2(
      () => draftIds.filter((id) => checked.has(id)),
      [draftIds, checked]
    );
    const toggle = (id) => {
      setChecked((prev) => {
        const next = new Set(prev);
        if (next.has(id)) next.delete(id);
        else next.add(id);
        return next;
      });
    };
    const issueSelected = async () => {
      if (!checkedDrafts.length || busy) return;
      setBusy(true);
      let ok = 0;
      const failed = [];
      for (const id of checkedDrafts) {
        try {
          await api(`/billing/invoices/${id}/issue`, { method: "POST" });
          ok += 1;
        } catch (e) {
          failed.push(e.message);
        }
      }
      setBusy(false);
      setChecked(/* @__PURE__ */ new Set());
      await load();
      if (failed.length) showToast(`发出 ${ok} 张，${failed.length} 张失败：${failed[0]}`, "warn");
      else showToast(`已发出 ${ok} 张发票`, "success");
    };
    const recordPayment = async () => {
      if (!detail || busy) return;
      const balance = Number(detail.invoice.balance_cents || 0);
      if (balance <= 0) {
        showToast("这张单已经没有欠款了", "warn");
        return;
      }
      setBusy(true);
      try {
        await api("/billing/payments", {
          method: "POST",
          body: JSON.stringify({
            billingAccountId: detail.invoice.billing_account_id,
            // Name the invoice the operator is looking at. Without it the server
            // allocated oldest-first and this invoice never moved, so the button
            // looked broken and each press quietly paid down a different one.
            invoiceId: detail.invoice.id,
            amountCents: balance,
            method: "bank_transfer",
            autoAllocate: true
          })
        });
        showToast(`已登记 ${aud(balance)}`, "success");
        await load();
        const refreshed = await api(`/billing/invoices/${selectedId}`);
        setDetail(refreshed);
      } catch (e) {
        showToast(`登记收款失败：${e.message}`, "warn");
      } finally {
        setBusy(false);
      }
    };
    const printCustomerDocument = (customerDocument, containerSelector, titleOverride) => {
      if (!customerDocument) return;
      const meta = customerDocument.document || {};
      const title = titleOverride || (meta.kind === "credit_note" ? "Credit Note" : customerDocument.supplier?.gstRegistered ? "Tax Invoice" : "Invoice");
      const number = meta.number || "Draft";
      const container = containerSelector ? document.querySelector(containerSelector) : null;
      if (containerSelector && !container) return;
      const previousTitle = document.title;
      if (container) container.classList.add("invoice-print-target");
      const cleanup = () => {
        document.body.classList.remove("invoice-print-mode");
        if (container) container.classList.remove("invoice-print-target");
      };
      const restore = () => {
        cleanup();
        document.title = previousTitle;
      };
      document.title = `${title} · ${number}`;
      document.body.classList.add("invoice-print-mode");
      window.addEventListener("afterprint", restore, { once: true });
      window.print();
      window.setTimeout(restore, 1500);
    };
    const printInvoice = () => {
      if (!detail) return;
      printCustomerDocument(detail.document, ".invoice-printable");
    };
    const [reminderNote, setReminderNote] = useState(null);
    const recordReminder = async () => {
      if (!detail || busy) return;
      setBusy(true);
      try {
        await api(`/billing/invoices/${detail.invoice.id}/reminders`, {
          method: "POST",
          body: JSON.stringify({
            note: (reminderNote || "").trim() || void 0,
            requestId: crypto.randomUUID()
          })
        });
        showToast("已记录提醒", "success");
        setReminderNote(null);
        setDetail(await api(`/billing/invoices/${selectedId}`));
      } catch (e) {
        showToast(`记录提醒失败：${e.message}`, "warn");
      } finally {
        setBusy(false);
      }
    };
    const [statement, setStatement] = useState(null);
    const openStatement = (acctId, acctName) => {
      const now = /* @__PURE__ */ new Date();
      const month = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
      setStatement({ month, data: null, accountId: acctId, accountName: acctName });
    };
    useEffect(() => {
      if (!statement?.accountId || !statement.month) return;
      let cancelled = false;
      api(`/billing/payers/${statement.accountId}/statement?month=${encodeURIComponent(statement.month)}`).then((d) => {
        if (!cancelled) setStatement((s) => s && { ...s, data: d });
      }).catch((e) => {
        if (!cancelled) showToast(`月结单加载失败：${e.message}`, "warn");
      });
      return () => {
        cancelled = true;
      };
    }, [statement?.accountId, statement?.month, api]);
    const openPayerEditor = () => {
      if (!detail?.invoice) return;
      setPayerEdit({
        name: detail.invoice.account_name || "",
        kind: detail.invoice.account_kind || "family",
        contactName: detail.invoice.account_contact_name || "",
        email: detail.invoice.account_email || "",
        mobile: detail.invoice.account_mobile || "",
        companyName: detail.invoice.account_company_name || "",
        abn: detail.invoice.account_abn || "",
        billingAddress: detail.invoice.account_billing_address || "",
        paymentTermsDays: String(detail.invoice.account_payment_terms_days ?? 14),
        purchaseOrderRef: detail.invoice.account_purchase_order_ref || "",
        language: detail.invoice.account_language || "",
        note: ""
      });
    };
    const savePayer = async () => {
      if (!detail?.invoice?.billing_account_id || !payerEdit || payerSaving) return;
      setPayerSaving(true);
      try {
        await api(`/billing/accounts/${detail.invoice.billing_account_id}`, {
          method: "PATCH",
          body: JSON.stringify(payerEdit)
        });
        showToast("付款方资料已更新；已开具发票继续读取冻结快照", "success");
        setPayerEdit(null);
        await load();
        setDetail(await api(`/billing/invoices/${selectedId}`));
      } catch (e) {
        showToast(`付款方更新失败：${e.message}`, "warn");
      } finally {
        setPayerSaving(false);
      }
    };
    const openCreditNote = async (noteId) => {
      try {
        setCreditNoteDetail(await api(`/billing/credit-notes/${noteId}`));
      } catch (e) {
        showToast(`贷记单加载失败：${e.message}`, "warn");
      }
    };
    if (loading) return /* @__PURE__ */ React.createElement("div", { className: "p-6 text-sm text-gray-500" }, "正在加载账单…");
    if (error) return /* @__PURE__ */ React.createElement("div", { className: "p-6 text-sm text-red-600" }, error);
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, creating && /* @__PURE__ */ React.createElement(
      NewInvoiceDialog,
      {
        api,
        accounts,
        students,
        studentPicker,
        busy,
        onClose: () => setCreating(false),
        onSubmit: createInvoice
      }
    ), accountId && /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 px-4 py-3 rounded-xl bg-amber-50 border border-amber-100" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold text-amber-800" }, "只看这个账单账户", invoices[0]?.account_name ? ` · ${invoices[0].account_name}` : ""), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => onClearAccount && onClearAccount(),
        className: "ml-auto min-h-[44px] px-3 rounded-lg border border-amber-200 bg-white text-xs font-bold text-amber-800"
      },
      "显示全部"
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, /* @__PURE__ */ React.createElement(Kpi, { label: "已开票", value: aud(summary.billed), sub: `${invoices.length} 张 · 含 GST` }), /* @__PURE__ */ React.createElement(
      Kpi,
      {
        label: "净收款（扣除退款）",
        value: aud(summary.netReceivedCents),
        tone: "good",
        sub: summary.collectedPercent === null ? "暂无已开具发票" : `${summary.collectedPercent}% · 贷记 ${aud(summary.credited)} · 退款 ${aud(summary.refunded)}`
      }
    ), /* @__PURE__ */ React.createElement(
      Kpi,
      {
        label: "逾期",
        value: aud(summary.overdueCents),
        tone: summary.overdueCents > 0 ? "alert" : void 0,
        sub: `${summary.overdueAccounts} 个家庭`
      }
    ), /* @__PURE__ */ React.createElement(Kpi, { label: "待发草稿", value: String(summary.drafts), sub: summary.drafts ? "勾选后可批量发出" : "没有待发的" })), /* @__PURE__ */ React.createElement("div", { className: "ui-golden-split" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0 space-y-2" }, /* @__PURE__ */ React.createElement(
      FilterBar,
      {
        range,
        onRange: setRange,
        query,
        onQuery: setQuery,
        searchPlaceholder: "搜付款方或发票号",
        buckets,
        bucket,
        onBucket: setBucket,
        total: visible.length,
        totalNoun: "张"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden min-w-0" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold" }, "发票"), canExportData && /* @__PURE__ */ React.createElement("div", { className: "ml-auto flex flex-wrap items-center gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "text-[11px] text-gray-500" }, "会计导出不含草稿 · 当前筛选范围"), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => exportCsv("summary"),
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "发票汇总 CSV"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => exportCsv("lines"),
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "行项目 CSV"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => exportCsv("ledger"),
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "会计流水 CSV"
    )), canIssue && checkedDrafts.length === 0 && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setCreating(true),
        className: `${canExportData ? "" : "ml-auto "}min-h-[44px] px-3 rounded-lg border border-indigo-200 bg-white text-xs font-bold text-indigo-700`
      },
      "新建发票"
    ), checkedDrafts.length > 0 && canIssue && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: issueSelected,
        disabled: busy,
        className: "ml-auto min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
      },
      "批量发出 (",
      checkedDrafts.length,
      ")"
    )), invoices.length === 0 ? /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-xs text-gray-500" }, "还没有发票。点击“新建发票”创建草稿，复核后再开具。") : visible.length === 0 ? (
      /* 「一张都没有」和「筛完没剩下」是两句话。第二句要告诉人怎么退出去。 */
      /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-xs text-gray-500" }, `没有符合当前筛选的发票。清除筛选可以看到全部 ${invoices.length} 张。`)
    ) : visible.map((invoice) => /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        key: invoice.id,
        onClick: () => setSelectedId(String(invoice.id)),
        className: `w-full text-left flex items-center gap-2 px-3 py-2 border-b border-gray-100 min-h-[44px]
                                ${String(invoice.id) === selectedId ? "bg-indigo-50" : "hover:bg-gray-50"}`
      },
      invoice.status === "draft" && canIssue && /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "checkbox",
          checked: checked.has(String(invoice.id)),
          onChange: () => toggle(String(invoice.id)),
          onClick: (e) => e.stopPropagation(),
          "aria-label": `选择 ${invoice.account_name} 的草稿`
        }
      ),
      /* @__PURE__ */ React.createElement("span", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-bold truncate" }, invoice.account_name), /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-500 truncate" }, invoice.number || "草稿 · 未编号", invoice.due_date ? ` · 到期 ${fmtApiDate(invoice.due_date)}` : "")),
      /* @__PURE__ */ React.createElement("span", { className: "ml-auto flex items-center gap-2" }, /* @__PURE__ */ React.createElement(StatusChip, { invoice }), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold tabular-nums ${isOverdue(invoice) ? "text-red-600" : ""}` }, aud(invoiceFinancialState(invoice).balance ?? invoice.total_cents)))
    )))), /* @__PURE__ */ React.createElement("div", { className: "invoice-printable grid gap-3 min-w-0" }, !detail ? /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-6 text-xs text-gray-500" }, "选择左边的一张发票查看明细。") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(InvoicePrintableDocument, { document: detail.document }), /* @__PURE__ */ React.createElement("div", { className: "payer-edit bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start gap-3 px-4 py-3 border-b border-gray-200" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold" }, "付款方资料"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500 mt-1" }, "当前发票收件人：", detail.invoice.account_name, " · ", detail.invoice.account_kind || "family", detail.invoice.account_email ? ` · ${detail.invoice.account_email}` : "", detail.invoice.account_mobile ? ` · ${detail.invoice.account_mobile}` : ""), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-indigo-700 mt-1" }, "已开具发票不会改变：客户文档继续使用 issued snapshot。")), /* @__PURE__ */ React.createElement("span", { className: "ml-auto flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => openStatement(detail.invoice.billing_account_id, detail.invoice.account_name),
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "月结单"
    ), canIssue && !payerEdit && /* @__PURE__ */ React.createElement("button", { type: "button", onClick: openPayerEditor, className: "min-h-[44px] px-3 rounded-lg border border-indigo-200 bg-white text-xs font-bold text-indigo-700" }, "查看 / 编辑付款方"))), payerEdit && /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-500" }, "姓名 / 名称", /* @__PURE__ */ React.createElement("input", { value: payerEdit.name, onChange: (e) => setPayerEdit({ ...payerEdit, name: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-500" }, "类型", /* @__PURE__ */ React.createElement("select", { value: payerEdit.kind, onChange: (e) => setPayerEdit({ ...payerEdit, kind: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" }, /* @__PURE__ */ React.createElement("option", { value: "person" }, "个人"), /* @__PURE__ */ React.createElement("option", { value: "family" }, "家庭"), /* @__PURE__ */ React.createElement("option", { value: "organisation" }, "机构"))), /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-500" }, "邮箱", /* @__PURE__ */ React.createElement("input", { type: "email", value: payerEdit.email, onChange: (e) => setPayerEdit({ ...payerEdit, email: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-500" }, "手机", /* @__PURE__ */ React.createElement("input", { value: payerEdit.mobile, onChange: (e) => setPayerEdit({ ...payerEdit, mobile: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-500" }, "联系人", /* @__PURE__ */ React.createElement("input", { value: payerEdit.contactName, onChange: (e) => setPayerEdit({ ...payerEdit, contactName: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-500" }, "付款期限（天）", /* @__PURE__ */ React.createElement("input", { type: "number", min: "0", max: "3650", value: payerEdit.paymentTermsDays, onChange: (e) => setPayerEdit({ ...payerEdit, paymentTermsDays: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" }))), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "账单地址", /* @__PURE__ */ React.createElement("input", { value: payerEdit.billingAddress, onChange: (e) => setPayerEdit({ ...payerEdit, billingAddress: e.target.value }), className: "mt-1 w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => setPayerEdit(null), disabled: payerSaving, className: "flex-1 min-h-[44px] rounded-xl border border-gray-200 text-xs font-bold" }, "取消"), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: savePayer, disabled: payerSaving, className: "flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold disabled:opacity-50" }, payerSaving ? "保存中…" : "保存付款方")))), /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 px-4 py-3 border-b border-gray-200" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold" }, detail.invoice.number || "草稿", " · ", detail.invoice.account_name), /* @__PURE__ */ React.createElement("span", { className: "ml-auto" }, /* @__PURE__ */ React.createElement(StatusChip, { invoice: detail.invoice }))), /* @__PURE__ */ React.createElement("div", { className: "p-4 overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full min-w-[26rem] text-xs" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "text-[10px] uppercase tracking-wide text-gray-500" }, /* @__PURE__ */ React.createElement("th", { className: "text-left py-2" }, "项目"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "数量"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "单价"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "税"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "小计"))), /* @__PURE__ */ React.createElement("tbody", null, (detail.lines || []).map((line) => /* @__PURE__ */ React.createElement("tr", { key: line.id, className: "border-t border-gray-100" }, /* @__PURE__ */ React.createElement("td", { className: "py-2" }, line.description), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, line.quantity), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(line.unit_price_cents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(line.tax_cents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(line.total_cents))))))), /* @__PURE__ */ React.createElement("div", { className: "px-4 pb-4 -mt-1 space-y-1 text-xs" }, (() => {
      const financial = invoiceFinancialState(detail.invoice);
      return /* @__PURE__ */ React.createElement("div", { className: "mb-2 rounded-lg border border-indigo-100 bg-indigo-50/60 p-2 text-[11px] text-indigo-900" }, /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, financial.creditState === "fully_credited" ? "已全额贷记" : financial.creditState === "partially_credited" ? "部分贷记" : "未贷记"), /* @__PURE__ */ React.createElement("span", { className: "ml-2" }, "净收款 ", aud(financial.netReceivedCents), "（原收款 ", aud(financial.paid), "，退款 ", aud(financial.refunded), "）"));
    })(), /* @__PURE__ */ React.createElement("div", { className: "flex items-baseline gap-3 border-t border-gray-200 pt-2 font-bold" }, /* @__PURE__ */ React.createElement("span", null, "应付"), /* @__PURE__ */ React.createElement("span", { className: "ml-auto tabular-nums" }, aud(detail.invoice.total_cents))), Number(detail.invoice.amount_paid_cents) > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-baseline gap-3 text-green-700" }, /* @__PURE__ */ React.createElement("span", null, "已付"), /* @__PURE__ */ React.createElement("span", { className: "ml-auto tabular-nums" }, "−", aud(detail.invoice.amount_paid_cents))), Number(detail.invoice.amount_credited_cents) > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-baseline gap-3 text-indigo-700" }, /* @__PURE__ */ React.createElement("span", null, "已贷记"), /* @__PURE__ */ React.createElement("span", { className: "ml-auto tabular-nums" }, "−", aud(detail.invoice.amount_credited_cents))), /* @__PURE__ */ React.createElement("div", { className: "flex items-baseline gap-3 font-bold" }, /* @__PURE__ */ React.createElement("span", null, "余额"), /* @__PURE__ */ React.createElement("span", { className: "ml-auto tabular-nums" }, aud(detail.invoice.balance_cents))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2 items-center mt-3" }, detail.invoice.status === "draft" && canIssue && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: busy,
        onClick: async () => {
          setBusy(true);
          try {
            await api(`/billing/invoices/${selectedId}/issue`, { method: "POST" });
            showToast("已开具", "success");
            await load();
            setDetail(await api(`/billing/invoices/${selectedId}`));
          } catch (e) {
            if (e.status === 409 && e.code === "invoice_profile_incomplete") {
              const missing = (e.payload?.missing || []).join("、");
              showToast(`开票信息不全${missing ? `（缺：${missing}）` : ""}——请到 系统设置 → 开票信息 补齐后再开具。`, "warn");
            } else showToast(`开具失败：${e.message}`, "warn");
          } finally {
            setBusy(false);
          }
        },
        className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
      },
      "开具发票"
    ), detail.invoice.status !== "draft" && Number(detail.invoice.balance_cents) > 0 && canTakePayment && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: recordPayment,
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
      },
      "登记收款"
    ), detail.invoice.status !== "draft" && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: printInvoice,
        className: "no-print min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "打印 / 存为 PDF"
    ), detail.invoice.status !== "draft" && detail.invoice.status !== "void" && Number(detail.invoice.balance_cents) > 0 && canTakePayment && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setReminderNote(""),
        disabled: busy,
        className: "no-print min-h-[44px] px-3 rounded-lg border border-amber-200 bg-amber-50 text-xs font-bold text-amber-800 disabled:opacity-50"
      },
      "记录提醒"
    ), detail.invoice.status !== "draft" && /* @__PURE__ */ React.createElement("span", { className: "text-[11px] text-gray-500" }, "已开具的发票不可修改，改错请开贷记单冲销后重开。")), reminderNote !== null && /* @__PURE__ */ React.createElement("div", { className: "no-print mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-amber-900 font-bold" }, "记录一次催款提醒（只入历史，不发送任何消息）"), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: reminderNote,
        onChange: (e) => setReminderNote(e.target.value),
        maxLength: 500,
        placeholder: "备注（选填）：如 已电话联系家长，约定周五转账",
        className: "w-full min-h-[44px] px-3 border border-amber-200 rounded-xl text-sm bg-white"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setReminderNote(null),
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl border border-gray-200 text-xs font-bold bg-white"
      },
      "取消"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: recordReminder,
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl bg-amber-600 text-white text-xs font-bold disabled:opacity-50"
      },
      busy ? "记录中…" : "确认记录"
    ))))), (detail.creditNotes || []).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 border-b border-gray-200 text-xs font-bold" }, "关联贷记单与退款"), (detail.creditNotes || []).map((note) => /* @__PURE__ */ React.createElement("div", { key: note.id, className: "flex flex-wrap items-baseline gap-x-3 gap-y-1 px-4 py-2 border-b border-gray-100 last:border-0 text-[11px]" }, /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, note.number || "贷记单草稿"), /* @__PURE__ */ React.createElement("span", null, note.status === "issued" ? "已开具" : note.status), /* @__PURE__ */ React.createElement("span", { className: "tabular-nums" }, "−", aud(note.total_cents)), note.refund_id && /* @__PURE__ */ React.createElement("span", { className: "text-green-700" }, "已退款 ", aud(note.refunded_cents)), note.payment_status && /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "付款：", note.payment_status), note.reason && /* @__PURE__ */ React.createElement("span", { className: "text-gray-500 truncate" }, note.reason), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => openCreditNote(note.id), className: "ml-auto min-h-[44px] px-2 rounded-lg border border-gray-200 text-[11px] font-bold text-indigo-700" }, "查看 / 打印贷记单")))), creditNoteDetail && /* @__PURE__ */ React.createElement("div", { className: "credit-note-document space-y-2" }, /* @__PURE__ */ React.createElement(InvoicePrintableDocument, { document: creditNoteDetail.document }), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => printCustomerDocument(creditNoteDetail.document, ".credit-note-document"), className: "no-print min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700" }, "打印贷记单")), statement && /* @__PURE__ */ React.createElement("div", { className: "statement-document bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "no-print flex flex-wrap items-center gap-2 px-4 py-3 border-b border-gray-200" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold" }, "月结单 · ", statement.accountName), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "month",
        value: statement.month,
        onChange: (e) => setStatement((s) => s && { ...s, month: e.target.value, data: null }),
        className: "min-h-[44px] px-2 border border-gray-200 rounded-lg text-xs"
      }
    ), /* @__PURE__ */ React.createElement("span", { className: "ml-auto flex gap-2" }, statement.data && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => printCustomerDocument({ document: { number: `${statement.accountName} · ${statement.month}` } }, ".statement-document", "Statement"),
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "打印 / 存为 PDF"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setStatement(null),
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-500"
      },
      "关闭"
    ))), !statement.data ? /* @__PURE__ */ React.createElement("p", { className: "px-4 py-4 text-xs text-gray-500" }, "月结单加载中…") : /* @__PURE__ */ React.createElement("article", { className: "invoice-customer-document p-4 text-xs" }, /* @__PURE__ */ React.createElement("header", { className: "flex items-baseline justify-between border-b border-gray-300 pb-2 mb-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-base font-bold" }, "Statement · 月结单"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-500" }, statement.data.payer?.name, " · ", fmtApiDate(statement.data.periodStart), " — ", fmtApiDate(statement.data.periodEnd))), /* @__PURE__ */ React.createElement("p", { className: "tabular-nums text-right" }, "期初 ", aud(statement.data.openingBalanceCents), /* @__PURE__ */ React.createElement("br", null), /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, "期末 ", aud(statement.data.closingBalanceCents)))), (statement.data.lines || []).length === 0 ? /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 py-2" }, "本期没有账务往来。") : /* @__PURE__ */ React.createElement("table", { className: "w-full text-[11px]" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "text-[10px] uppercase tracking-wide text-gray-500" }, /* @__PURE__ */ React.createElement("th", { className: "text-left py-1.5" }, "日期"), /* @__PURE__ */ React.createElement("th", { className: "text-left py-1.5" }, "单据"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-1.5" }, "应收"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-1.5" }, "收款/贷记"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-1.5" }, "余额"))), /* @__PURE__ */ React.createElement("tbody", null, statement.data.lines.map((line, i) => /* @__PURE__ */ React.createElement("tr", { key: i, className: "border-t border-gray-100" }, /* @__PURE__ */ React.createElement("td", { className: "py-1.5 tabular-nums" }, fmtApiDate(line.ts)), /* @__PURE__ */ React.createElement("td", { className: "py-1.5" }, line.number ? `${line.number} · ` : "", line.description), /* @__PURE__ */ React.createElement("td", { className: "py-1.5 text-right tabular-nums" }, Number(line.debitCents) > 0 ? aud(line.debitCents) : ""), /* @__PURE__ */ React.createElement("td", { className: "py-1.5 text-right tabular-nums" }, Number(line.creditCents) > 0 ? `−${aud(line.creditCents)}` : ""), /* @__PURE__ */ React.createElement("td", { className: "py-1.5 text-right tabular-nums" }, aud(line.balanceCents)))))))), /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 border-b border-gray-200 text-xs font-bold" }, "这张单发生过什么"), (detail.events || []).length === 0 ? /* @__PURE__ */ React.createElement("p", { className: "px-4 py-4 text-[11px] text-gray-500" }, "还没有记录。开具、送达、收款、推送 Xero 都会出现在这里。") : (detail.events || []).map((event, i) => {
      const LABEL = {
        issued: "已开具",
        sent: "已送达",
        part_paid: "部分付款",
        paid: "已付清",
        refunded: "已退款",
        voided: "已作废",
        overdue: "已逾期",
        credited: "已贷记",
        credit_settled: "充值已结算",
        xero_pushed: "已推送 Xero",
        reminder_recorded: "已记录提醒"
      };
      const d = event.detail || {};
      const amount = Number(d.amount_cents || 0);
      const balance = d.balance_cents === void 0 ? null : Number(d.balance_cents);
      return /* @__PURE__ */ React.createElement("div", { key: i, className: "flex items-baseline gap-2 px-4 py-2 border-b border-gray-100 last:border-0 text-[11px]" }, /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, LABEL[event.event_type] || event.event_type), amount > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, aud(amount)), balance !== null && /* @__PURE__ */ React.createElement("span", { className: "text-gray-400" }, "余额 ", aud(balance)), d.note && /* @__PURE__ */ React.createElement("span", { className: "text-gray-500 truncate max-w-[16rem]" }, d.note), /* @__PURE__ */ React.createElement("span", { className: "ml-auto text-gray-500 tabular-nums" }, fmtApiDate(event.occurred_at)));
    }))))));
  }
  function BillingAccountPicker({
    api,
    accounts,
    students = [],
    studentPicker,
    value,
    onStateChange,
    payerError,
    onPayerError,
    initialStudentId = "",
    hideStudentSelector = false
  }) {
    const StudentPicker2 = studentPicker;
    const payerErrorRef = useRef(null);
    const [mode, setMode] = useState("student");
    const [studentId, setStudentId] = useState(initialStudentId || "");
    const [studentPayers, setStudentPayers] = useState([]);
    const [studentSuggestion, setStudentSuggestion] = useState(null);
    const [studentLoading, setStudentLoading] = useState(false);
    const [query, setQuery] = useState("");
    const [searchResults, setSearchResults] = useState([]);
    const [creating, setCreating] = useState(false);
    const [createConfirmed, setCreateConfirmed] = useState(false);
    const [kind, setKind] = useState("person");
    const [fields, setFields] = useState({
      name: "",
      contactName: "",
      email: "",
      mobile: "",
      companyName: "",
      abn: "",
      billingAddress: "",
      paymentTermsDays: "14",
      purchaseOrderRef: "",
      language: "en",
      note: ""
    });
    const [studentDraft, setStudentDraft] = useState({
      kind: "family",
      name: "",
      contactName: "",
      email: "",
      mobile: "",
      billingAddress: "",
      paymentTermsDays: "14",
      language: "en"
    });
    const [linkedStudentIds, setLinkedStudentIds] = useState([]);
    const setField = (key) => (e) => {
      setCreateConfirmed(false);
      setFields((prev) => ({ ...prev, [key]: e.target.value }));
    };
    const setStudentDraftField = (key) => (e) => {
      setCreateConfirmed(false);
      setStudentDraft((prev) => ({ ...prev, [key]: e.target.value }));
    };
    const selectedStudent = students.find((student) => String(student.id) === String(studentId));
    useEffect(() => {
      if (initialStudentId === void 0) return;
      setMode("student");
      setStudentId(initialStudentId || "");
      setQuery("");
      setCreating(false);
      setCreateConfirmed(false);
      setLinkedStudentIds(initialStudentId ? [initialStudentId] : []);
    }, [initialStudentId]);
    useEffect(() => {
      if (payerError && payerErrorRef.current) payerErrorRef.current.focus();
    }, [payerError]);
    useEffect(() => {
      if (mode !== "student" || !studentId) {
        setStudentPayers([]);
        setStudentSuggestion(null);
        setStudentLoading(false);
        if (mode === "student") onStateChange({ mode, accountId: "", createPayload: null, linkedStudentIds: [] });
        return void 0;
      }
      let alive = true;
      setStudentLoading(true);
      onPayerError("");
      api(`/billing/accounts?studentId=${encodeURIComponent(studentId)}&limit=100`).then((data) => {
        if (!alive) return;
        const payers = data.accounts || [];
        setStudentPayers(payers);
        setStudentSuggestion(data.suggestedPayer || null);
        if (payers.length === 0) {
          const suggestion = data.suggestedPayer || {};
          setStudentDraft((prev) => ({
            ...prev,
            kind: suggestion.kind || "family",
            name: suggestion.name || selectedStudent?.name || "",
            contactName: suggestion.contactName || "",
            email: suggestion.email || "",
            mobile: suggestion.mobile || "",
            billingAddress: suggestion.billingAddress || "",
            paymentTermsDays: String(suggestion.paymentTermsDays ?? prev.paymentTermsDays ?? "14"),
            language: suggestion.language || "en"
          }));
        }
        if (payers.length === 1) onStateChange({ mode, accountId: String(payers[0].id), createPayload: null, linkedStudentIds: [studentId] });
        else if (!payers.some((payer) => String(payer.id) === String(value))) onStateChange({ mode, accountId: "", createPayload: null, linkedStudentIds: [] });
      }).catch((error) => {
        if (alive) onPayerError(`付款方加载失败：${error.message}`);
      }).finally(() => {
        if (alive) setStudentLoading(false);
      });
      return () => {
        alive = false;
      };
    }, [api, mode, studentId, selectedStudent?.name]);
    useEffect(() => {
      if (mode !== "custom" || !query.trim()) {
        setSearchResults([]);
        return void 0;
      }
      let alive = true;
      const timer = setTimeout(() => {
        api(`/billing/accounts?q=${encodeURIComponent(query.trim())}&limit=50`).then((data) => {
          if (alive) setSearchResults(data.accounts || []);
        }).catch((error) => {
          if (alive) onPayerError(`付款方搜索失败：${error.message}`);
        });
      }, 180);
      return () => {
        alive = false;
        clearTimeout(timer);
      };
    }, [api, mode, query]);
    const createPayload = useMemo2(() => {
      if (mode === "student") {
        if (!studentId || studentPayers.length > 0 || !createConfirmed) return null;
        if (!String(studentDraft.name || "").trim()) return null;
        return {
          ...studentDraft,
          kind: studentDraft.kind || "family",
          name: String(studentDraft.name).trim(),
          studentId
        };
      }
      if (!creating || !createConfirmed) return null;
      const displayName = String(kind === "organisation" ? fields.companyName : fields.name).trim();
      if (!displayName) return null;
      return {
        ...fields,
        name: displayName,
        contactName: kind === "organisation" ? String(fields.contactName || fields.name).trim() : fields.contactName,
        kind,
        studentIds: linkedStudentIds
      };
    }, [mode, studentId, studentPayers, createConfirmed, studentDraft, creating, kind, fields, linkedStudentIds]);
    useEffect(() => {
      onStateChange({
        mode,
        accountId: mode === "student" && studentPayers.length === 1 ? String(studentPayers[0].id) : String(value || ""),
        createPayload,
        createConfirmed,
        linkedStudentIds: mode === "student" ? studentId ? [studentId] : [] : linkedStudentIds
      });
    }, [mode, value, studentId, studentPayers, linkedStudentIds, createPayload, createConfirmed]);
    const chooseMode = (nextMode) => {
      setMode(nextMode);
      onPayerError("");
      setCreating(false);
      setCreateConfirmed(false);
      setQuery("");
      setLinkedStudentIds([]);
      if (nextMode === "student") onStateChange({ mode: nextMode, accountId: "", createPayload: null, linkedStudentIds: [] });
    };
    const visibleAccounts = query.trim() ? searchResults : accounts.slice(0, 20);
    const selectedPayer = [...accounts, ...studentPayers, ...searchResults].find((payer) => String(payer.id) === String(value));
    const toggleLinkedStudent = (studentKey) => {
      setLinkedStudentIds((prev) => prev.includes(String(studentKey)) ? prev.filter((id) => id !== String(studentKey)) : [...prev, String(studentKey)]);
      setCreateConfirmed(false);
    };
    return /* @__PURE__ */ React.createElement("fieldset", { className: "space-y-2", "aria-describedby": "billing-account-help" }, /* @__PURE__ */ React.createElement("legend", { className: "block text-xs font-bold text-gray-600" }, "开给谁"), /* @__PURE__ */ React.createElement("p", { id: "billing-account-help", className: "text-[11px] text-gray-500" }, "学员是服务对象；付款方是发票收件人。两条入口最终都选择同一个付款方记录。"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => chooseMode("student"),
        "aria-pressed": mode === "student",
        className: `min-h-[44px] rounded-xl border text-sm font-bold ${mode === "student" ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-gray-200 bg-white text-gray-700"}`
      },
      "已有学员"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => chooseMode("custom"),
        "aria-pressed": mode === "custom",
        className: `min-h-[44px] rounded-xl border text-sm font-bold ${mode === "custom" ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-gray-200 bg-white text-gray-700"}`
      },
      "其他个人或机构"
    )), mode === "student" && /* @__PURE__ */ React.createElement("div", { className: "space-y-2 rounded-xl border border-gray-200 p-3" }, !hideStudentSelector && StudentPicker2 ? /* @__PURE__ */ React.createElement(
      StudentPicker2,
      {
        students,
        value: studentId || null,
        onChange: (next) => {
          setCreateConfirmed(false);
          setStudentId(next || "");
          onStateChange({ mode, accountId: "", createPayload: null, linkedStudentIds: next ? [next] : [] });
        },
        placeholder: "搜索并选择学员",
        showBal: false
      }
    ) : !hideStudentSelector ? /* @__PURE__ */ React.createElement(
      "select",
      {
        value: studentId,
        onChange: (event) => {
          setCreateConfirmed(false);
          setStudentId(event.target.value);
        },
        "aria-label": "选择学员",
        className: "w-full min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "请选择学员"),
      students.map((student) => /* @__PURE__ */ React.createElement("option", { key: student.id, value: student.id }, student.name))
    ) : /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-600" }, "当前学员：", /* @__PURE__ */ React.createElement("strong", null, selectedStudent?.name || "—"), "；下面只选择这次发票的付款方。"), studentLoading && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500" }, "正在查询该学员的付款方…"), !studentLoading && studentId && studentPayers.length === 0 && /* @__PURE__ */ React.createElement("div", { className: "space-y-2 rounded-lg bg-amber-50 border border-amber-100 p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-amber-900" }, "0 个付款方：这个学员还没有付款方"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-amber-800" }, "资料只用于预填；填写或修改后，必须明确点击“创建并使用此付款方”才会创建记录。"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "付款方类型", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: studentDraft.kind,
        onChange: setStudentDraftField("kind"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "person" }, "个人 / Person"),
      /* @__PURE__ */ React.createElement("option", { value: "family" }, "家庭 / Family"),
      /* @__PURE__ */ React.createElement("option", { value: "organisation" }, "机构 / Organisation")
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "姓名 / 名称 *", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: studentDraft.name,
        onChange: setStudentDraftField("name"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "联系人（可选）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: studentDraft.contactName,
        onChange: setStudentDraftField("contactName"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "邮箱 / Email", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "email",
        value: studentDraft.email,
        onChange: setStudentDraftField("email"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "手机 / Mobile", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: studentDraft.mobile,
        onChange: setStudentDraftField("mobile"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "语言 / Language", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: studentDraft.language,
        onChange: setStudentDraftField("language"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "zh" }, "中文"),
      /* @__PURE__ */ React.createElement("option", { value: "en" }, "English")
    ))), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "账单地址 / Billing address（可选）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: studentDraft.billingAddress,
        onChange: setStudentDraftField("billingAddress"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-[11px] text-gray-600" }, "付款期限 / Payment terms（天）", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        max: "3650",
        value: studentDraft.paymentTermsDays,
        onChange: setStudentDraftField("paymentTermsDays"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: !String(studentDraft.name || "").trim(),
        onClick: () => {
          setCreateConfirmed(true);
          onStateChange({ mode, accountId: "", createPayload: null, linkedStudentIds: [studentId], createConfirmed: true });
        },
        className: "w-full min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "创建并使用此付款方 ",
      /* @__PURE__ */ React.createElement("span", { className: "text-[11px] font-normal" }, "/ Create and use this payer")
    ), createConfirmed && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold text-emerald-700" }, "已确认创建；提交草稿或开票时才会写入付款方记录。")), !studentLoading && studentPayers.length > 0 && /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "已关联付款方（", studentPayers.length, " 个，", studentPayers.length === 1 ? "已默认选中，可切换" : "不会默认选择，必须明确选择", "）", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: value || "",
        onChange: (event) => {
          setCreateConfirmed(false);
          onStateChange({ mode, accountId: event.target.value, createPayload: null, linkedStudentIds: [studentId] });
        },
        "aria-describedby": "billing-account-payer-help",
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "请选择付款方"),
      studentPayers.map((payer) => /* @__PURE__ */ React.createElement("option", { key: payer.id, value: payer.id }, payer.name, " · ", payer.kind, payer.email ? ` · ${payer.email}` : "", payer.mobile ? ` · ${payer.mobile}` : ""))
    ), /* @__PURE__ */ React.createElement("span", { id: "billing-account-payer-help", className: "block mt-1 text-[11px] text-gray-400" }, studentPayers.length === 1 ? `已默认选中：${studentPayers[0].name}（${studentPayers[0].kind || "payer"}；${studentPayers[0].email || studentPayers[0].mobile || "无联系方式"}）` : "有多个付款方时不会自动猜测或合并；请核对类型和联系方式后选择。", /* @__PURE__ */ React.createElement("span", { className: "block mt-1" }, "付款方快照会在开具时冻结；之后修改付款方资料不会改写已开具发票。")))), mode === "custom" && /* @__PURE__ */ React.createElement("div", { className: "space-y-2 rounded-xl border border-gray-200 p-3" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "先搜索已有付款方 / Search before creating", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: query,
        onChange: (event) => {
          setQuery(event.target.value);
          setCreateConfirmed(false);
          onPayerError("");
        },
        placeholder: "姓名、机构、邮箱、电话或 ABN",
        "aria-label": "搜索已有付款方",
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), visibleAccounts.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "max-h-40 overflow-y-auto rounded-lg border border-gray-100" }, visibleAccounts.map((payer) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: payer.id,
        type: "button",
        onClick: () => {
          setCreateConfirmed(false);
          onStateChange({ mode, accountId: String(payer.id), createPayload: null, linkedStudentIds });
          setCreating(false);
        },
        className: `w-full min-h-[44px] px-3 text-left text-sm border-b border-gray-100 last:border-0 ${String(payer.id) === String(value) ? "bg-indigo-50" : "bg-white hover:bg-gray-50"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, payer.name),
      /* @__PURE__ */ React.createElement("span", { className: "ml-2 text-[11px] text-gray-500" }, payer.kind, payer.email ? ` · ${payer.email}` : "", payer.mobile ? ` · ${payer.mobile}` : "")
    ))), selectedPayer && !creating && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-indigo-700" }, "已选付款方：", selectedPayer.name), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: !query.trim(),
        onClick: () => {
          setCreating(true);
          setCreateConfirmed(false);
          onStateChange({ mode, accountId: "", createPayload: null, linkedStudentIds });
        },
        className: "min-h-[44px] px-3 rounded-xl border border-indigo-200 bg-white text-xs font-bold text-indigo-700 disabled:opacity-50"
      },
      query.trim() ? "仍未找到？新建个人或机构付款方" : "先搜索，仍未找到再新建付款方"
    ), !query.trim() && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500" }, "为避免同名重复，请先搜索姓名、机构、邮箱、电话或 ABN。"), creating && /* @__PURE__ */ React.createElement("div", { className: "space-y-2 border-t border-gray-100 pt-2" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "类型", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: kind,
        onChange: (event) => {
          setKind(event.target.value);
          setCreateConfirmed(false);
        },
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "person" }, "个人"),
      /* @__PURE__ */ React.createElement("option", { value: "organisation" }, "机构"),
      /* @__PURE__ */ React.createElement("option", { value: "family" }, "个人/家庭（兼容旧类型）")
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, kind === "organisation" ? "联系人姓名（可选）" : "姓名", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: kind === "organisation" ? fields.contactName : fields.name,
        onChange: setField(kind === "organisation" ? "contactName" : "name"),
        "aria-describedby": "billing-payer-name-error",
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), kind === "organisation" && /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "机构名称", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: fields.companyName,
        onChange: setField("companyName"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), kind !== "organisation" && /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "联系人（可选）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: fields.contactName,
        onChange: setField("contactName"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "邮箱", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "email",
        value: fields.email,
        onChange: setField("email"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "电话", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: fields.mobile,
        onChange: setField("mobile"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "ABN（可选）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: fields.abn,
        onChange: setField("abn"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    ))), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "账单地址（可选）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: fields.billingAddress,
        onChange: setField("billingAddress"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "付款期限（天）", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        max: "3650",
        value: fields.paymentTermsDays,
        onChange: setField("paymentTermsDays"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "PO reference（可选）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: fields.purchaseOrderRef,
        onChange: setField("purchaseOrderRef"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "语言", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: fields.language,
        onChange: setField("language"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "en" }, "English"),
      /* @__PURE__ */ React.createElement("option", { value: "zh" }, "中文")
    ))), /* @__PURE__ */ React.createElement("div", { className: "block text-xs text-gray-500" }, "可选关联服务对象（0..N）", /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2 mt-1", "aria-label": "可选关联服务对象" }, students.map((student) => {
      const selected = linkedStudentIds.includes(String(student.id));
      return /* @__PURE__ */ React.createElement(
        "button",
        {
          key: student.id,
          type: "button",
          className: `payer-chip min-h-[44px] px-3 rounded-full border text-xs font-bold ${selected ? "border-indigo-500 bg-indigo-50 text-indigo-700" : "border-gray-200 bg-white text-gray-600"}`,
          "aria-pressed": selected,
          onClick: () => toggleLinkedStudent(student.id)
        },
        selected ? "✓ " : "",
        student.name
      );
    }), !students.length && /* @__PURE__ */ React.createElement("span", { className: "text-[11px] text-gray-400" }, "暂无可关联服务对象"))), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: !String(kind === "organisation" ? fields.companyName : fields.name).trim(),
        onClick: () => setCreateConfirmed(true),
        className: "w-full min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "创建并使用此付款方 ",
      /* @__PURE__ */ React.createElement("span", { className: "text-[11px] font-normal" }, "/ Create and use this payer")
    ), createConfirmed && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold text-emerald-700" }, "已确认创建；提交草稿或开票时才会写入付款方记录。"))), payerError && /* @__PURE__ */ React.createElement("p", { id: "billing-payer-name-error", ref: payerErrorRef, tabIndex: "-1", role: "alert", className: "text-xs text-red-600" }, payerError));
  }
  function NewInvoiceDialog({ api, accounts, students = [], studentPicker, busy, onClose, onSubmit }) {
    const Picker = studentPicker;
    const payerErrorRef = useRef(null);
    const invoiceDraftRequestRef = useRef({ signature: "", id: "" });
    const [payerState, setPayerState] = useState({ accountId: "", createPayload: null, linkedStudentIds: [], mode: "student" });
    const [payerError, setPayerError] = useState("");
    const [possibleDuplicates, setPossibleDuplicates] = useState([]);
    const [allowPossibleDuplicate, setAllowPossibleDuplicate] = useState(false);
    const [note, setNote] = useState("");
    const [lines, setLines] = useState([
      { description: "", quantity: "1", unitPrice: "", taxRateBp: "1000", sourceKind: "manual", studentId: "" }
    ]);
    const setLine = (i, key) => (e) => setLines((rows) => rows.map((row, idx) => idx === i ? { ...row, [key]: e.target.value } : row));
    const total = lines.reduce((sum, line) => {
      const net = Number(line.quantity || 0) * Number(line.unitPrice || 0);
      return sum + net + net * (Number(line.taxRateBp || 0) / 1e4);
    }, 0);
    const payerReady = Boolean(payerState.accountId || payerState.createPayload);
    const ready = payerReady && lines.some((l) => l.description.trim() && Number(l.unitPrice) > 0);
    const nextInvoiceDraftRequestId = (signature) => {
      if (invoiceDraftRequestRef.current.signature !== signature) {
        const id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `invoice-draft-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        invoiceDraftRequestRef.current = { signature, id };
      }
      return invoiceDraftRequestRef.current.id;
    };
    useEffect(() => {
      if (payerError && payerErrorRef.current) payerErrorRef.current.focus();
    }, [payerError]);
    useEffect(() => {
      const closeOnEscape = (event) => {
        if (event.key === "Escape" && !busy) onClose();
      };
      document.addEventListener("keydown", closeOnEscape);
      return () => document.removeEventListener("keydown", closeOnEscape);
    }, [busy, onClose]);
    const submit = async () => {
      setPayerError("");
      try {
        let payer = null;
        if (payerState.accountId) {
          payer = { accountId: String(payerState.accountId) };
        } else if (payerState.createPayload) {
          const { studentId: _studentId, studentIds: _studentIds, ...create } = payerState.createPayload;
          payer = { create, linkedStudentIds: payerState.linkedStudentIds };
        }
        if (!payer) {
          setPayerError("请选择或创建付款方。");
          return;
        }
        const aggregateLines = lines.map((line) => ({
          description: line.description.trim(),
          quantity: line.quantity,
          unitPriceCents: Math.round(Number(line.unitPrice) * 100),
          taxRateBp: Number(line.taxRateBp),
          sourceKind: line.sourceKind || "manual",
          studentId: line.studentId || null
        }));
        const signature = JSON.stringify({ payer, note, lines: aggregateLines, allowPossibleDuplicate });
        const requestId = nextInvoiceDraftRequestId(signature);
        await onSubmit({
          requestId,
          payer,
          invoice: { note },
          lines: aggregateLines,
          allowPossibleDuplicate
        });
        setPossibleDuplicates([]);
        setAllowPossibleDuplicate(false);
      } catch (error) {
        if (error.status === 409 && error.details?.possibleDuplicates) {
          setPossibleDuplicates(error.details.possibleDuplicates);
          setAllowPossibleDuplicate(false);
        }
        setPayerError(error.message || "付款方保存失败，请检查输入后重试。");
      }
    };
    return /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white w-full sm:max-w-xl rounded-t-2xl sm:rounded-2xl p-5 space-y-3 max-h-[90vh] overflow-y-auto", role: "dialog", "aria-modal": "true", "aria-labelledby": "new-invoice-title" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { id: "new-invoice-title", className: "text-lg font-bold text-gray-800" }, "新建发票"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, "先存成草稿。复核无误后在列表里开具 —— 开具会定号码和到期日，之后金额不能再改。")), /* @__PURE__ */ React.createElement(
      BillingAccountPicker,
      {
        api,
        accounts,
        students,
        studentPicker: Picker,
        value: payerState.accountId,
        onStateChange: setPayerState,
        payerError,
        onPayerError: setPayerError
      }
    ), possibleDuplicates.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-amber-200 bg-amber-50 p-3 space-y-2", role: "alert" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-amber-900" }, "发现可能重复的付款方，请先核对"), /* @__PURE__ */ React.createElement("ul", { className: "text-[11px] text-amber-900 list-disc pl-4 space-y-1" }, possibleDuplicates.map((payer) => /* @__PURE__ */ React.createElement("li", { key: payer.id }, payer.name, " · ", payer.kind, payer.email ? ` · ${payer.email}` : "", payer.mobile ? ` · ${payer.mobile}` : ""))), /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-2 min-h-[44px] text-xs text-amber-900" }, /* @__PURE__ */ React.createElement("input", { type: "checkbox", checked: allowPossibleDuplicate, onChange: (event) => setAllowPossibleDuplicate(event.target.checked), className: "mt-1 w-5 h-5 accent-amber-600" }), /* @__PURE__ */ React.createElement("span", null, "我已核对并明确允许新建，不自动合并；继续时会记录原因和候选付款方。"))), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, lines.map((line, i) => /* @__PURE__ */ React.createElement("div", { key: i, className: "border border-gray-200 rounded-xl p-3 space-y-2" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "项目说明", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: line.description,
        onChange: setLine(i, "description"),
        placeholder: "例如「第三学期学费」",
        "aria-describedby": `invoice-line-${i}-help`,
        className: "w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-3 gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "数量", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        step: "0.01",
        value: line.quantity,
        onChange: setLine(i, "quantity"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "单价（未税）", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        step: "0.01",
        value: line.unitPrice,
        onChange: setLine(i, "unitPrice"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "税率", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: line.taxRateBp,
        onChange: setLine(i, "taxRateBp"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "1000" }, "GST 10%"),
      /* @__PURE__ */ React.createElement("option", { value: "0" }, "不计税")
    ))), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "收入分类", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: line.sourceKind,
        onChange: setLine(i, "sourceKind"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "manual" }, "手工收入"),
      /* @__PURE__ */ React.createElement("option", { value: "package" }, "课包/课时收入（仅分类）")
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "服务对象（可选）", Picker ? /* @__PURE__ */ React.createElement("div", { className: "mt-1" }, /* @__PURE__ */ React.createElement(
      Picker,
      {
        students,
        value: line.studentId || null,
        onChange: (value) => setLines((rows) => rows.map((row, idx) => idx === i ? { ...row, studentId: value || "" } : row)),
        placeholder: "搜索并选择学员（仅报告归属）",
        showBal: false
      }
    )) : /* @__PURE__ */ React.createElement(
      "select",
      {
        value: line.studentId,
        onChange: setLine(i, "studentId"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "不关联学员"),
      students.map((s) => /* @__PURE__ */ React.createElement("option", { key: s.id, value: s.id }, s.name))
    ), /* @__PURE__ */ React.createElement("span", { id: `invoice-line-${i}-help`, className: "block mt-1 text-[11px] text-gray-400" }, "只表达收入报告归属，不改变课时余额；未选择时发送 null。")))), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setLines((rows) => [...rows, { description: "", quantity: "1", unitPrice: "", taxRateBp: "1000", sourceKind: "manual", studentId: "" }]),
        className: "min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-700"
      },
      "再加一行"
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-500" }, "备注（选填）", /* @__PURE__ */ React.createElement(
      "input",
      {
        value: note,
        onChange: (e) => setNote(e.target.value),
        className: "w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500" }, "合计约 ", aud(Math.round(total * 100)), "（含税）"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: onClose,
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50"
      },
      "取消"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: submit,
        disabled: busy || !ready,
        className: "flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "存为草稿"
    ))));
  }

  // legacy-root/src/panels/finance.jsx
  var { useState: useState2, useEffect: useEffect2, useCallback: useCallback2, useMemo: useMemo3 } = React;
  var RATE_BASIS_LABEL = {
    per_lesson: "按节",
    per_session: "按场",
    per_hour: "按小时",
    per_head: "按人头",
    percent_of_tuition: "按学费比例"
  };
  var ENGAGEMENT = {
    contractor: { label: "承包", cls: "bg-gray-100 text-gray-600 border-gray-200", canPush: true },
    employee: { label: "仅清单", cls: "bg-blue-50 text-blue-700 border-blue-200", canPush: false },
    unset: { label: "待补用工性质", cls: "bg-red-50 text-red-700 border-red-200", canPush: false }
  };
  function Num({ label, value, sub, tone }) {
    const cls = tone === "warn" ? "text-amber-700" : tone === "muted" ? "text-gray-400" : "text-gray-900";
    return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold uppercase tracking-wide text-gray-500" }, label), /* @__PURE__ */ React.createElement("p", { className: `text-xl font-bold tabular-nums ${cls}` }, value), sub && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500" }, sub));
  }
  function PayrollView({ api, showToast, range, onRange }) {
    const [teachers, setTeachers] = useState2([]);
    const [query, setQuery] = useState2("");
    const [selected, setSelected] = useState2(null);
    const [sheet, setSheet] = useState2(null);
    const [loading, setLoading] = useState2(true);
    const [error, setError] = useState2("");
    useEffect2(() => {
      let cancelled = false;
      setLoading(true);
      api(`/teaching/summary?from=${range.from}&to=${range.to}`).then((d) => {
        if (!cancelled) {
          setTeachers(d.teachers || []);
          setError("");
        }
      }).catch((e) => {
        if (!cancelled) setError(e.status === 403 ? "这个套餐未包含老师课酬清单。" : `加载失败：${e.message}`);
      }).finally(() => {
        if (!cancelled) setLoading(false);
      });
      return () => {
        cancelled = true;
      };
    }, [api, range.from, range.to]);
    useEffect2(() => {
      if (!selected) {
        setSheet(null);
        return;
      }
      let cancelled = false;
      api(`/teaching/timesheet?teacherUserId=${selected}&from=${range.from}&to=${range.to}`).then((d) => {
        if (!cancelled) setSheet(d);
      }).catch((e) => {
        if (!cancelled) showToast(`课时明细加载失败：${e.message}`, "warn");
      });
      return () => {
        cancelled = true;
      };
    }, [selected, api, range.from, range.to]);
    if (loading) return /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 p-4" }, "正在加载课酬…");
    if (error) return /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600 p-4" }, error);
    if (!teachers.length) {
      return /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 p-4" }, "本期还没有归集到课时。课时来自点名记录，点完名这里就会有数。");
    }
    const visible = teachers.filter((t) => !query.trim() || String(t.full_name || "").toLowerCase().includes(query.trim().toLowerCase()));
    const current = teachers.find((t) => String(t.teacher_user_id) === selected);
    const engagement = ENGAGEMENT[current?.engagement] || ENGAGEMENT.unset;
    return /* @__PURE__ */ React.createElement("div", { className: "ui-golden-split" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0 space-y-2" }, /* @__PURE__ */ React.createElement(
      FilterBar,
      {
        range: { start: range.from, end: range.to },
        onRange: (next) => onRange({ from: next.start, to: next.end }),
        query,
        onQuery: setQuery,
        searchPlaceholder: "搜老师姓名",
        total: visible.length,
        totalNoun: "位"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden min-w-0" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 border-b border-gray-200 text-xs font-bold" }, "老师"), visible.length === 0 && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-xs text-gray-500" }, `没有匹配的老师。清除筛选可以看到全部 ${teachers.length} 位。`), visible.map((t) => {
      const eng = ENGAGEMENT[t.engagement] || ENGAGEMENT.unset;
      return /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          key: t.teacher_user_id,
          onClick: () => setSelected(String(t.teacher_user_id)),
          className: `w-full text-left flex items-center gap-2 px-3 py-2 border-b border-gray-100 min-h-[44px]
                                ${String(t.teacher_user_id) === selected ? "bg-indigo-50" : "hover:bg-gray-50"}`
        },
        /* @__PURE__ */ React.createElement("span", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-bold truncate" }, t.full_name), /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-500" }, t.sessions, " 节 · ", Math.round((t.paid_minutes || 0) / 60), " 小时")),
        /* @__PURE__ */ React.createElement("span", { className: "ml-auto flex items-center gap-2" }, /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${eng.cls}` }, eng.label), /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold tabular-nums" }, aud(t.cost_cents)))
      );
    }))), /* @__PURE__ */ React.createElement("div", { className: "grid gap-3 min-w-0" }, !sheet ? /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-6 text-xs text-gray-500" }, "选择一位老师，查看本期课时明细。") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, /* @__PURE__ */ React.createElement(Num, { label: "实际上了", value: sheet.summary.actual_sessions, sub: "节" }), /* @__PURE__ */ React.createElement(Num, { label: "计入课酬", value: sheet.summary.paid_sessions, sub: "节" }), /* @__PURE__ */ React.createElement(Num, { label: "不计课酬", value: sheet.summary.unpaid_sessions, sub: "节", tone: sheet.summary.unpaid_sessions ? "warn" : "muted" }), /* @__PURE__ */ React.createElement(Num, { label: "本期应付", value: aud(sheet.summary.amount_cents), sub: `${Math.round((sheet.summary.paid_minutes || 0) / 60)} 小时` })), /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 px-4 py-3 border-b border-gray-200" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold" }, current?.full_name, " · ", range.from, " → ", range.to), /* @__PURE__ */ React.createElement("span", { className: `ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap ${engagement.cls}` }, engagement.label)), /* @__PURE__ */ React.createElement("div", { className: "p-4 overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-xs" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "text-[10px] uppercase tracking-wide text-gray-500" }, /* @__PURE__ */ React.createElement("th", { className: "text-left py-2" }, "日期"), /* @__PURE__ */ React.createElement("th", { className: "text-left py-2" }, "课程"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "时长"), /* @__PURE__ */ React.createElement("th", { className: "text-left py-2" }, "费率基准"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "金额"))), /* @__PURE__ */ React.createElement("tbody", null, (sheet.sessions || []).map((s, i) => (
      /* 请假但按政策计费 → warning 底；工作室取消不计 → 降透明度。
         同一张表里，钱的两种「不正常」看起来必须不一样。 */
      /* @__PURE__ */ React.createElement("tr", { key: i, className: `border-t border-gray-100 ${s.counts_for_pay ? "" : "opacity-50"}` }, /* @__PURE__ */ React.createElement("td", { className: "py-2" }, fmtApiDate(s.occurred_on)), /* @__PURE__ */ React.createElement("td", { className: "py-2" }, s.course_name || "—"), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, s.duration_minutes, " 分钟"), /* @__PURE__ */ React.createElement("td", { className: "py-2" }, s.counts_for_pay ? RATE_BASIS_LABEL[s.rate_basis] || s.rate_basis || "未设费率" : "不计课酬"), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(s.amount_cents)))
    )), /* @__PURE__ */ React.createElement("tr", { className: "border-t border-gray-200 font-bold" }, /* @__PURE__ */ React.createElement("td", { className: "py-2", colSpan: 4 }, "本期应付"), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(sheet.summary.amount_cents))))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2 items-center mt-3" }, engagement.canPush ? /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold"
      },
      "推送 Xero 应付账单"
    ) : /* @__PURE__ */ React.createElement("span", { className: "text-[11px] text-gray-500" }, current?.engagement === "employee" ? "雇员工资不作为应付账单推送 —— 那会绕开薪资科目。导出清单交给财务走薪资流程。" : "未记录用工性质，无法决定这笔钱怎么进账。请先在老师资料里选择雇员或 ABN 承包。"), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        className: "min-h-[44px] px-3 rounded-lg bg-white border border-gray-300 text-xs font-bold"
      },
      "导出 CSV"
    )))))));
  }
  function ReportsView({ api, range }) {
    const [data, setData] = useState2({});
    const [error, setError] = useState2("");
    useEffect2(() => {
      let cancelled = false;
      Promise.all([
        api(`/reports/revenue?from=${range.from}&to=${range.to}`).catch((e) => ({ __err: e })),
        api("/reports/receivables").catch((e) => ({ __err: e }))
      ]).then(([revenue, receivables]) => {
        if (cancelled) return;
        const failed = [revenue, receivables].find((r) => r && r.__err);
        if (failed) setError(failed.__err.status === 403 ? "这个套餐未包含经营报表。" : `报表加载失败：${failed.__err.message}`);
        else setData({ revenue, receivables });
      });
      return () => {
        cancelled = true;
      };
    }, [api, range.from, range.to]);
    if (error) return /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600 p-4" }, error);
    if (!data.revenue) return /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 p-4" }, "正在加载报表…");
    const buckets = data.receivables?.buckets || {};
    const total = data.receivables?.totalCents || 0;
    const BUCKETS = [
      ["current", "未到期", ""],
      ["d1_30", "1–30 天", "bg-amber-100 border-amber-300"],
      ["d31_60", "31–60 天", "bg-red-100 border-red-300"],
      ["d61_90", "61–90 天", "bg-red-100 border-red-300"],
      ["d90_plus", "90 天以上", "bg-red-100 border-red-300"]
    ];
    return /* @__PURE__ */ React.createElement("div", { className: "grid gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, /* @__PURE__ */ React.createElement(Num, { label: "本期开票", value: aud(data.revenue.totals?.gross_cents), sub: `${data.revenue.totals?.invoices || 0} 张` }), /* @__PURE__ */ React.createElement(Num, { label: "其中 GST", value: aud(data.revenue.totals?.tax_cents) }), /* @__PURE__ */ React.createElement(Num, { label: "贷记冲销", value: aud(data.revenue.credits?.credited_cents) }), /* @__PURE__ */ React.createElement(Num, { label: "应收未收", value: aud(total), tone: total > 0 ? "warn" : "muted" })), /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 px-4 py-3 border-b border-gray-200" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold" }, "应收账龄"), /* @__PURE__ */ React.createElement("span", { className: "ml-auto text-[11px] text-gray-500" }, "每个数字背后的发票都在下面的清单里")), /* @__PURE__ */ React.createElement("div", { className: "p-4 grid gap-1.5" }, BUCKETS.map(([key, label, cls]) => {
      const cents = buckets[key] || 0;
      const pct = total > 0 ? Math.round(cents / total * 100) : 0;
      return /* @__PURE__ */ React.createElement(
        "div",
        {
          key,
          className: "grid items-center gap-2 text-xs",
          style: { gridTemplateColumns: "80px 1fr 84px" }
        },
        /* @__PURE__ */ React.createElement("span", null, label),
        /* @__PURE__ */ React.createElement("span", { className: "h-4 rounded bg-gray-100 border border-gray-200 overflow-hidden" }, /* @__PURE__ */ React.createElement(
          "span",
          {
            className: `block h-full rounded border ${cls || "bg-blue-100 border-blue-300"}`,
            style: { width: `${Math.max(pct, cents > 0 ? 2 : 0)}%` }
          }
        )),
        /* @__PURE__ */ React.createElement("span", { className: "text-right tabular-nums" }, aud(cents))
      );
    }))), (data.revenue.byKind || []).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 border-b border-gray-200 text-xs font-bold" }, "收入构成"), /* @__PURE__ */ React.createElement("div", { className: "p-4 overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-xs" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "text-[10px] uppercase tracking-wide text-gray-500" }, /* @__PURE__ */ React.createElement("th", { className: "text-left py-2" }, "来源"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "张数"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "不含税"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "税"), /* @__PURE__ */ React.createElement("th", { className: "text-right py-2" }, "合计"))), /* @__PURE__ */ React.createElement("tbody", null, data.revenue.byKind.map((k, i) => /* @__PURE__ */ React.createElement("tr", { key: i, className: "border-t border-gray-100" }, /* @__PURE__ */ React.createElement("td", { className: "py-2" }, k.source_kind), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, k.invoices), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(k.net_cents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(k.tax_cents)), /* @__PURE__ */ React.createElement("td", { className: "py-2 text-right tabular-nums" }, aud(k.gross_cents)))))))));
  }
  function FinancePanel({ api, showToast }) {
    const [view, setView] = useState2("payroll");
    const [range, setRange] = useState2(monthRange);
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 items-center" }, [["payroll", "课酬"], ["reports", "报表"]].map(([key, label]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        key,
        onClick: () => setView(key),
        "aria-pressed": view === key,
        className: `min-h-[44px] px-4 rounded-lg text-xs font-bold border
                              ${view === key ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-300"}`
      },
      label
    ))), view === "payroll" ? /* @__PURE__ */ React.createElement(PayrollView, { api, showToast, range, onRange: setRange }) : /* @__PURE__ */ React.createElement(ReportsView, { api, range }));
  }

  // legacy-root/src/panels/integrations.jsx
  var { useState: useState3, useEffect: useEffect3, useCallback: useCallback3 } = React;
  var BLOCKER_TEXT = {
    addon_not_active: "尚未开通 Xero 加购 —— 这一项由平台方授予",
    not_connected: "还没有连接到 Xero 组织",
    mapping_not_confirmed: "科目与税率映射还没有确认",
    demo_run_not_completed: "还没有在 Xero 测试组织跑通一个完整周期",
    single_entry_not_answered: "还没有回答「是否已有别的通道在同步」",
    transport_not_available: "当前版本尚未接入 Xero transport"
  };
  function Step({ n, done, active, title, children }) {
    const badge = done ? "bg-green-50 text-green-700 border-green-200" : active ? "bg-indigo-600 text-white border-indigo-600" : "bg-gray-100 text-gray-500 border-gray-200";
    return /* @__PURE__ */ React.createElement("div", { className: `flex gap-3 items-start p-3 rounded-xl border ${active ? "border-indigo-200 bg-indigo-50" : "border-gray-200 bg-white"}` }, /* @__PURE__ */ React.createElement("span", { className: `w-7 h-7 rounded-full grid place-items-center text-xs font-bold border flex-none ${badge}` }, done ? "✓" : n), /* @__PURE__ */ React.createElement("div", { className: "text-xs min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold mb-0.5" }, title), /* @__PURE__ */ React.createElement("div", { className: "text-gray-600" }, children)));
  }
  function IntegrationsPanel({ api, showToast, canManage }) {
    const [state, setState] = useState3(null);
    const [busy, setBusy] = useState3(false);
    const [error, setError] = useState3("");
    const [queue, setQueue] = useState3(null);
    const [mapDraft, setMapDraft] = useState3(null);
    const [demoReport, setDemoReport] = useState3(null);
    const [reconcileReport, setReconcileReport] = useState3(null);
    const load = useCallback3(async () => {
      try {
        const st = await api("/integrations/xero");
        setState(st);
        setError("");
        setMapDraft((prev) => prev || Object.fromEntries(
          (st.mappableKinds || []).map((k) => {
            const row = (st.mappings || []).find((m) => m.item_kind === k) || {};
            return [k, { accountCode: row.account_code || "", taxType: row.tax_type || "" }];
          })
        ));
        if (st.transportAvailable) {
          try {
            setQueue(await api("/integrations/xero/queue"));
          } catch {
          }
        }
      } catch (e) {
        setError(e.status === 403 ? "" : `集成状态加载失败：${e.message}`);
        setState(null);
      }
    }, [api]);
    useEffect3(() => {
      load();
    }, [load]);
    useEffect3(() => {
      const params = new URLSearchParams(window.location.search);
      const flag = params.get("xero");
      if (!flag) return;
      const message = params.get("xeroMessage") || "";
      if (flag === "connected") showToast("Xero 已连接", "success");
      else if (flag === "cancelled") showToast("已取消 Xero 授权，未做任何更改", "warn");
      else showToast(`Xero 连接失败：${message || "未知原因"}`, "warn");
      params.delete("xero");
      params.delete("xeroMessage");
      const rest = params.toString();
      window.history.replaceState({}, "", window.location.pathname + (rest ? `?${rest}` : ""));
    }, []);
    const [armDisconnect, setArmDisconnect] = useState3(false);
    const connectNow = async () => {
      if (busy) return;
      setBusy(true);
      try {
        const d = await api("/integrations/xero/connect-url", { method: "POST", body: "{}" });
        window.location.href = d.url;
      } catch (e) {
        showToast(e.message, "warn");
        setBusy(false);
      }
    };
    const disconnectNow = async () => {
      if (busy) return;
      if (!armDisconnect) {
        setArmDisconnect(true);
        return;
      }
      setBusy(true);
      try {
        await api("/integrations/xero/disconnect", { method: "POST", body: "{}" });
        showToast("已断开 Xero 连接", "success");
        await load();
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
        setArmDisconnect(false);
      }
    };
    const refreshCheck = async () => {
      if (busy) return;
      setBusy(true);
      try {
        await api("/integrations/xero/refresh-check", { method: "POST", body: "{}" });
        showToast("令牌有效（必要时已自动续期）", "success");
        await load();
      } catch (e) {
        showToast(`令牌检查未通过：${e.message}`, "warn");
        await load();
      } finally {
        setBusy(false);
      }
    };
    const step = async (name, extra = {}) => {
      if (busy) return;
      setBusy(true);
      try {
        const body = name === "single_entry" ? JSON.stringify(extra) : JSON.stringify({ step: name });
        const path = name === "single_entry" ? "/integrations/xero/single-entry" : "/integrations/xero/gate";
        await api(path, { method: "POST", body });
        await load();
        showToast("已更新", "success");
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    const saveMappings = async () => {
      if (busy || !mapDraft) return;
      setBusy(true);
      try {
        const mappings = Object.entries(mapDraft).map(([itemKind, v]) => ({
          itemKind,
          accountCode: v.accountCode.trim(),
          taxType: v.taxType.trim()
        }));
        await api("/integrations/xero/mappings", { method: "PUT", body: JSON.stringify({ mappings }) });
        showToast("映射已保存", "success");
        await load();
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    const demoRun = async () => {
      if (busy) return;
      setBusy(true);
      setDemoReport(null);
      try {
        const r = await api("/integrations/xero/gate", { method: "POST", body: JSON.stringify({ step: "demo_run" }) });
        setDemoReport(r.demoRun || null);
        showToast(r.ok ? "试跑通过：全部推送成功，对账 0 差异" : "试跑未通过，看下方报告", r.ok ? "success" : "warn");
        await load();
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    const pushNow = async () => {
      if (busy) return;
      setBusy(true);
      try {
        const r = await api("/integrations/xero/push-now", { method: "POST", body: "{}" });
        showToast(`已处理 ${r.processed} 项：成功 ${r.sent}，失败 ${r.failed}，稍后重试 ${r.deferred}`, r.failed ? "warn" : "success");
        await load();
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    const backfillNow = async () => {
      if (busy) return;
      setBusy(true);
      try {
        const r = await api("/integrations/xero/backfill", { method: "POST", body: "{}" });
        showToast(`已排队 ${r.queued.total} 张（发票 ${r.queued.invoice} / 贷记 ${r.queued.credit_note} / 收款 ${r.queued.payment}）`, "success");
        await load();
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    const replayJob = async (jobId) => {
      if (busy) return;
      setBusy(true);
      try {
        await api(`/integrations/xero/errors/${jobId}/replay`, { method: "POST", body: "{}" });
        showToast("已重新入队（沿用同一幂等键）", "success");
        await load();
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    const runReconcile = async () => {
      if (busy) return;
      setBusy(true);
      setReconcileReport(null);
      try {
        const r = await api("/integrations/xero/reconciliation");
        setReconcileReport(r);
        showToast(r.diffCount === 0 ? `对账通过：${r.checked} 张全部一致` : `发现 ${r.diffCount} 处差异`, r.diffCount === 0 ? "success" : "warn");
      } catch (e) {
        showToast(e.message, "warn");
      } finally {
        setBusy(false);
      }
    };
    if (error) return /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600" }, error);
    if (!state) {
      return /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-gray-200 bg-white p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold mb-1" }, "Xero 预接入（Preview）"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-600" }, "当前版本只展示接入准备状态，不会向 Xero 发送任何数据。 映射、连接与 gate 状态会保留，真实 transport 上线后再开放生产操作。"));
    }
    const s = state.settings || {};
    const blockers = state.blockers || [];
    const has = (key) => !blockers.includes(key);
    const transportAvailable = state.transportAvailable === true;
    const preview = !transportAvailable;
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold" }, preview ? "Xero 预接入（Preview）" : "Xero 集成"), !preview && /* @__PURE__ */ React.createElement("span", { className: "text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap bg-amber-50 text-amber-800 border-amber-200" }, "Beta"), /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold px-1.5 py-0.5 rounded border whitespace-nowrap
          ${preview ? "bg-blue-50 text-blue-700 border-blue-200" : state.pushEnabled ? "bg-green-50 text-green-700 border-green-200" : "bg-gray-100 text-gray-600 border-gray-200"}` }, preview ? "预览状态 · 不发送数据" : state.pushEnabled ? "推送已开启" : "推送未开启"), s.last_pushed_at && /* @__PURE__ */ React.createElement("span", { className: "text-[11px] text-gray-500" }, "历史记录：上次推送 ", fmtApiDate(s.last_pushed_at))), preview ? /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-blue-200 bg-blue-50 p-4 text-[11px] text-blue-900" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold mb-1" }, "Xero 预接入说明"), /* @__PURE__ */ React.createElement("p", null, "可以连接 / 断开自己的 Xero 组织（建议先用 Demo Company 测试）；当前版本仍不会向 Xero 推送任何单据数据。")) : /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-blue-200 bg-blue-50 p-4 text-[11px] text-blue-900" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold mb-1" }, "单向推送"), /* @__PURE__ */ React.createElement("p", null, "已开具的发票、贷记单与收款按队列推入你的 Xero 组织；不做双向同步，不从 Xero 回改任何本地单据。 先用 Demo Company 完成试跑，再连正式账套。"), /* @__PURE__ */ React.createElement("p", { className: "mt-1.5" }, "功能处于 Beta：正在用一个完整结算月的真实账目验证，期间请照常核对 Xero 里的单据。")), (() => {
      const cx = state.connection || {};
      if (!cx.configured) return /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-gray-200 bg-white p-4 text-[11px] text-gray-600" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 mb-1" }, "Xero 连接 · 服务器未配置"), /* @__PURE__ */ React.createElement("p", null, "缺少：", (cx.configMissing || []).join("、") || "凭据", "。请运营方在服务器上运行 deploy/aws/set_xero_env.sh 配置后重启。"));
      if (cx.connected) return /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-green-200 bg-green-50 p-4 text-[11px] text-green-900" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold mb-1" }, "已连接 Xero · ", cx.orgName || "组织"), /* @__PURE__ */ React.createElement("p", { className: "mb-2" }, "连接于 ", cx.connectedAt ? cx.connectedAt.slice(0, 10) : "—", "；访问令牌到期后会自动续期。"), canManage && /* @__PURE__ */ React.createElement("span", { className: "flex gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: refreshCheck,
          disabled: busy,
          className: "min-h-[44px] px-3 rounded-lg border border-green-300 bg-white text-[11px] font-bold text-green-800 disabled:opacity-50"
        },
        "测试令牌自愈"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: disconnectNow,
          disabled: busy,
          className: `min-h-[44px] px-3 rounded-lg border text-[11px] font-bold disabled:opacity-50 ${armDisconnect ? "bg-red-600 text-white border-red-600" : "border-red-200 bg-white text-red-700"}`
        },
        armDisconnect ? "再点一次，确认断开" : "断开连接"
      ), armDisconnect && /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => setArmDisconnect(false),
          className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-[11px] font-bold text-gray-600"
        },
        "取消"
      )));
      return /* @__PURE__ */ React.createElement("div", { className: `rounded-xl border p-4 text-[11px] ${cx.status === "expired" || cx.status === "error" ? "border-amber-300 bg-amber-50 text-amber-900" : "border-gray-200 bg-white text-gray-700"}` }, /* @__PURE__ */ React.createElement("p", { className: "font-bold mb-1" }, cx.status === "expired" ? "Xero 连接已过期，需要重新授权" : cx.status === "error" ? "Xero 连接出错，需要重新授权" : cx.status === "revoked" ? "Xero 已断开" : "尚未连接 Xero"), cx.lastError && /* @__PURE__ */ React.createElement("p", { className: "mb-2 text-[10px] opacity-80" }, cx.lastError), /* @__PURE__ */ React.createElement("p", { className: "mb-2" }, "授权后本工作室即与你的 Xero 组织建立连接（建议先选 Demo Company）；连接本身不推送任何数据。"), canManage ? /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: connectNow,
          disabled: busy,
          className: "min-h-[44px] px-4 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50"
        },
        cx.status === "expired" || cx.status === "error" || cx.status === "revoked" ? "重新连接 Xero" : "连接 Xero"
      ) : /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-500" }, "需要 Owner / Manager 权限发起连接。"));
    })(), /* @__PURE__ */ React.createElement("div", { className: "ui-golden-split" }, /* @__PURE__ */ React.createElement("div", { className: "grid gap-2 min-w-0" }, /* @__PURE__ */ React.createElement(Step, { n: 1, done: state.entitled, title: "加购权利" }, state.entitled ? "已开通" : "由平台方授予，租户侧只读"), /* @__PURE__ */ React.createElement(
      Step,
      {
        n: 2,
        done: state.connection?.connected || state.connected,
        active: state.entitled && !(state.connection?.connected || state.connected),
        title: "连接 Xero"
      },
      state.connection?.connected ? `已连接 ${state.connection.orgName || ""}` : "用上方「连接 Xero」按钮授权自己的组织（先用 Demo Company）"
    ), /* @__PURE__ */ React.createElement(Step, { n: 3, done: has("mapping_not_confirmed"), active: state.connected && !has("mapping_not_confirmed"), title: "科目与税率映射" }, state.missingMappings?.length ? `还差：${state.missingMappings.join("、")}` : has("mapping_not_confirmed") ? "会计已确认" : "填完后由会计确认"), /* @__PURE__ */ React.createElement(Step, { n: 4, done: has("demo_run_not_completed"), title: "测试组织试跑" }, has("demo_run_not_completed") ? "已跑通一个完整周期" : preview ? "预览版只显示准备状态，不会发起试跑" : "先在 Xero 测试组织跑通，再连生产账套"), /* @__PURE__ */ React.createElement(Step, { n: 5, done: has("single_entry_not_answered"), title: "单一入口" }, has("single_entry_not_answered") ? s.single_entry_decision === "clearing_account" ? `走清算账户 ${s.clearing_account_code}` : "已关闭其他通道的同步" : "还没有回答")), /* @__PURE__ */ React.createElement("div", { className: "grid gap-3 min-w-0" }, !has("single_entry_not_answered") && state.connected && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-red-200 bg-red-50 p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-red-700 mb-1" }, "先回答这个"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-700 mb-2" }, "你们的收款渠道（比如 Square）是不是", /* @__PURE__ */ React.createElement("strong", null, "已经在往同一个 Xero 组织同步"), "？ 如果是，我们再推一遍，Xero 里就会出现两套记录。"), canManage && !preview && /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: busy,
        onClick: () => step("single_entry", { decision: "ours_only" }),
        className: "min-h-[44px] px-3 rounded-lg bg-white border border-gray-300 text-xs font-bold"
      },
      "已关掉对方的同步"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: busy,
        onClick: () => {
          const code = window.prompt("清算账户科目号");
          if (code) step("single_entry", { decision: "clearing_account", clearingAccountCode: code });
        },
        className: "min-h-[44px] px-3 rounded-lg bg-white border border-gray-300 text-xs font-bold"
      },
      "保留，走清算账户"
    )), preview && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500" }, "预览阶段只读显示，不修改 gate。")), !preview && state.connection?.connected && mapDraft && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-gray-200 bg-white p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold mb-1" }, "科目与税率映射"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500 mb-2" }, "科目号与税率代码来自你的 Xero 账套（会计提供）。必填：tuition（学费收入）、bank（收款入账账户）； lesson / manual 行按 tuition 科目入账。"), /* @__PURE__ */ React.createElement("div", { className: "grid gap-1.5" }, (state.mappableKinds || []).map((kind) => /* @__PURE__ */ React.createElement("div", { key: kind, className: "flex items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("span", { className: `text-[11px] w-28 flex-none ${state.requiredKinds?.includes(kind) ? "font-bold" : "text-gray-500"}` }, kind, state.requiredKinds?.includes(kind) ? " *" : ""), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: mapDraft[kind]?.accountCode || "",
        disabled: !canManage || busy,
        onChange: (e) => setMapDraft({ ...mapDraft, [kind]: { ...mapDraft[kind], accountCode: e.target.value } }),
        placeholder: "科目号，如 200",
        className: "w-28 min-h-[44px] px-2 rounded-lg border border-gray-300 text-[11px]"
      }
    ), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: mapDraft[kind]?.taxType || "",
        disabled: !canManage || busy,
        onChange: (e) => setMapDraft({ ...mapDraft, [kind]: { ...mapDraft[kind], taxType: e.target.value } }),
        placeholder: "税率代码，如 OUTPUT",
        className: "w-32 min-h-[44px] px-2 rounded-lg border border-gray-300 text-[11px]"
      }
    )))), canManage && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 mt-2 flex-wrap" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: saveMappings,
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg border border-gray-300 bg-white text-[11px] font-bold disabled:opacity-50"
      },
      "保存映射"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => step("confirm_mapping"),
        disabled: busy || !!state.missingMappings?.length,
        className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50"
      },
      "会计已确认映射"
    )), !!state.missingMappings?.length && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-amber-700 mt-1.5" }, "还差必填映射：", state.missingMappings.join("、"))), !preview && state.connection?.connected && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-gray-200 bg-white p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold mb-1" }, "测试组织试跑"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-600 mb-2" }, "把已开具的单据全部推入当前连接的组织（应为 Demo Company），随后逐张读回对账。 推送成功且对账 0 差异，这一步才算完成。"), canManage && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: demoRun,
        disabled: busy || !has("mapping_not_confirmed"),
        className: "min-h-[44px] px-4 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50"
      },
      has("demo_run_not_completed") ? "再跑一次（推送新增单据）" : "开始试跑"
    ), !has("mapping_not_confirmed") && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500 mt-1.5" }, "先完成并确认上方映射。"), demoReport && /* @__PURE__ */ React.createElement("div", { className: `mt-2 rounded-lg border p-3 text-[11px] ${demoReport.clean ? "border-green-200 bg-green-50 text-green-900" : "border-amber-300 bg-amber-50 text-amber-900"}` }, /* @__PURE__ */ React.createElement("p", { className: "font-bold" }, demoReport.clean ? "试跑通过" : "试跑未通过", " · 排队 ", demoReport.queued?.total ?? 0, " / 推送 ", demoReport.pushed, " / 失败 ", demoReport.failed, " · 对账差异 ", demoReport.reconciliation?.diffCount ?? "—"), (demoReport.jobs || []).filter((j) => j.outcome !== "sent").slice(0, 5).map((j) => /* @__PURE__ */ React.createElement("p", { key: j.id, className: "mt-1 opacity-80" }, j.kind, ": ", j.error)))), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-gray-200 bg-white p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold mb-2" }, "Xero 推送"), preview ? /* @__PURE__ */ React.createElement("div", { className: "rounded-lg border border-blue-100 bg-blue-50 p-3 text-[11px] text-blue-900" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold" }, "当前版本尚未开放生产推送"), /* @__PURE__ */ React.createElement("p", { className: "mt-1" }, "Xero transport 尚未上线；不会向 Xero 发送任何数据。")) : state.canEnablePush ? canManage ? /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: busy,
        onClick: () => step(state.pushEnabled ? "disable_push" : "enable_push"),
        className: `min-h-[44px] px-4 rounded-lg text-xs font-bold
                          ${state.pushEnabled ? "bg-white border border-gray-300 text-gray-700" : "bg-indigo-600 text-white"}`
      },
      state.pushEnabled ? "暂停推送" : "开启推送"
    ) : /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500" }, "需要 owner 权限。") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: true,
        className: "min-h-[44px] px-4 rounded-lg bg-gray-100 text-gray-400 text-xs font-bold cursor-not-allowed"
      },
      "还不能开启"
    ), /* @__PURE__ */ React.createElement("ul", { className: "mt-2 text-[11px] text-gray-600 list-disc pl-4" }, blockers.map((b) => /* @__PURE__ */ React.createElement("li", { key: b }, BLOCKER_TEXT[b] || b)))), /* @__PURE__ */ React.createElement("p", { className: "mt-2 text-[11px] text-gray-500" }, preview ? "已有映射、ID 对应表与错误队列仍可查看；真实 transport 上线后再开放推送。" : "暂停只停新的推送。连接、映射、ID 对应表与错误队列都保留，年末封账可以放心用。")), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-gray-200 bg-white p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold mb-1" }, "推送队列"), preview ? /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-600" }, "预接入阶段只保留已有历史记录与映射状态；不会创建新的 Xero 推送任务。") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-600 mb-2" }, "队列每 5 分钟自动处理一次。失败的单据带原因列在下面，修好后一键重放 —— 重放沿用同一个幂等键，不会在 Xero 里产生第二张。", /* @__PURE__ */ React.createElement("strong", null, "原因几乎总是会计要改的一处映射。")), queue?.counts && /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-700 mb-2" }, "待推 ", queue.counts.queued ?? 0, " · 失败 ", queue.counts.failed ?? 0, " · 已推 ", queue.counts.sent ?? 0), canManage && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap mb-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: backfillNow,
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg border border-gray-300 bg-white text-[11px] font-bold disabled:opacity-50"
      },
      "排队积压单据"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: pushNow,
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-[11px] font-bold disabled:opacity-50"
      },
      "立即推送"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: runReconcile,
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg border border-gray-300 bg-white text-[11px] font-bold disabled:opacity-50"
      },
      "逐张对账"
    )), (queue?.jobs || []).filter((j) => j.status === "failed").slice(0, 8).map((j) => /* @__PURE__ */ React.createElement("div", { key: j.id, className: "rounded-lg border border-red-200 bg-red-50 p-2 mb-1.5 text-[11px] text-red-900" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold" }, j.local_kind, " · 第 ", j.attempts, " 次尝试失败"), /* @__PURE__ */ React.createElement("p", { className: "opacity-90 break-all" }, j.last_error), canManage && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => replayJob(j.id),
        disabled: busy,
        className: "mt-1 min-h-[44px] px-2.5 rounded-lg border border-red-300 bg-white text-[11px] font-bold text-red-700 disabled:opacity-50"
      },
      "修好了，重放"
    ))), reconcileReport && /* @__PURE__ */ React.createElement("div", { className: `rounded-lg border p-2 text-[11px] ${reconcileReport.diffCount === 0 ? "border-green-200 bg-green-50 text-green-900" : "border-amber-300 bg-amber-50 text-amber-900"}` }, /* @__PURE__ */ React.createElement("p", { className: "font-bold" }, "对账：检查 ", reconcileReport.checked, " 张，差异 ", reconcileReport.diffCount, " 处"), (reconcileReport.diffs || []).slice(0, 6).map((d, i) => /* @__PURE__ */ React.createElement("p", { key: i, className: "mt-0.5 opacity-90" }, d.kind, " ", d.number, " · ", d.field, "：本地 ", String(d.local), " ↔ Xero ", String(d.xero)))))))));
  }

  // legacy-root/src/panels/billing_identity.jsx
  var { useState: useState4, useEffect: useEffect4, useCallback: useCallback4 } = React;
  var TEXT_FIELDS = [
    ["legal_name", "法定主体名称", "开票主体的注册名，例如 Paradise Production Pty Ltd"],
    ["trading_name", "经营名称", "对外使用的工作室名，可与法定名称不同"],
    ["abn", "ABN", "11 位澳洲商业号码"],
    ["address_line1", "地址第一行", ""],
    ["address_line2", "地址第二行", ""],
    ["suburb", "区/市", ""],
    ["state", "州", "VIC / NSW / QLD …"],
    ["postcode", "邮编", ""],
    ["contact_email", "开票邮箱", "家长回信会到这里"],
    ["contact_phone", "开票电话", ""],
    ["bank_account_name", "收款户名", ""],
    ["bank_bsb", "BSB", ""],
    ["bank_account_no", "银行账号", ""]
  ];
  function BillingIdentityPanel({ api, showToast, canManage }) {
    const [form, setForm] = useState4(null);
    const [busy, setBusy] = useState4(false);
    const [error, setError] = useState4("");
    const load = useCallback4(async () => {
      try {
        const res = await api("/billing/identity");
        setForm(res.identity);
        setError("");
      } catch (e) {
        setError(e.status === 403 ? "这个工作室尚未开通开票功能。" : `加载失败：${e.message}`);
      }
    }, [api]);
    useEffect4(() => {
      load();
    }, [load]);
    if (error) return /* @__PURE__ */ React.createElement("p", { className: "text-sm text-red-600" }, error);
    if (!form) return null;
    const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
    async function save() {
      setBusy(true);
      try {
        const res = await api("/billing/identity", { method: "PUT", body: JSON.stringify(form) });
        setForm(res.identity);
        showToast("开票信息已保存", "success");
      } catch (e) {
        showToast(e.message || "保存失败", "error");
      } finally {
        setBusy(false);
      }
    }
    const gstWithoutAbn = form.gst_registered && !String(form.abn || "").trim();
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500" }, "这些内容会印在每一张发票上。没有它们，开具会被拒绝 —— 一张收了 GST 却不写 ABN 的单据，家长的会计用不了。"), !form.configured && /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-4 py-3" }, "还没有填过。填完之前无法开具任何发票。"), /* @__PURE__ */ React.createElement("label", { className: `flex items-center gap-3 min-h-[44px] px-4 rounded-xl border ${form.gst_registered ? "border-indigo-500 bg-indigo-50" : "border-gray-200"}` }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        checked: !!form.gst_registered,
        disabled: !canManage,
        onChange: () => setForm((f) => ({ ...f, gst_registered: !f.gst_registered }))
      }
    ), /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-800" }, "已注册 GST")), gstWithoutAbn && /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-red-700" }, "勾了「已注册 GST」就必须填 ABN，否则保存会被拒绝。"), !form.gst_registered && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, "未注册 GST 时，发票行的税率请选「不计税」，单据也不会自称税务发票。"), /* @__PURE__ */ React.createElement("div", { className: "grid sm:grid-cols-2 gap-3" }, TEXT_FIELDS.map(([key, label, hint]) => /* @__PURE__ */ React.createElement("label", { key, className: "block text-xs text-gray-400" }, label, /* @__PURE__ */ React.createElement(
      "input",
      {
        value: form[key] || "",
        onChange: set(key),
        disabled: !canManage,
        placeholder: hint,
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm text-gray-800 disabled:bg-gray-50"
      }
    )))), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "付款说明", /* @__PURE__ */ React.createElement(
      "textarea",
      {
        value: form.payment_note || "",
        onChange: set("payment_note"),
        rows: 2,
        disabled: !canManage,
        placeholder: "例如：请在到期日前转账，并在备注里写上发票号。",
        className: "block w-full mt-1 px-3 py-2 border border-gray-200 rounded-xl text-sm text-gray-800 disabled:bg-gray-50"
      }
    )), canManage && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: save,
        disabled: busy,
        className: "min-h-[44px] px-5 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "保存开票信息"
    ));
  }

  // legacy-root/src/panels/progress_reports.jsx
  var { useState: useState5, useEffect: useEffect5, useCallback: useCallback5 } = React;
  function OverdueReports({ api, showToast, onOpenStudent }) {
    const [rows, setRows] = useState5([]);
    const [loading, setLoading] = useState5(true);
    const [error, setError] = useState5("");
    const load = useCallback5(async () => {
      setLoading(true);
      try {
        const d = await api("/progress-reports/overdue");
        setRows(d.overdue || []);
        setError("");
      } catch (e) {
        setError(e.status === 403 ? "这个套餐未包含成长报告。" : `加载失败：${e.message}`);
      } finally {
        setLoading(false);
      }
    }, [api]);
    useEffect5(() => {
      load();
    }, [load]);
    if (loading) return /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 p-4" }, "正在加载…");
    if (error) return /* @__PURE__ */ React.createElement("p", { className: "text-sm text-red-600 p-4" }, error);
    if (!rows.length) {
      return /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-600" }, "没有逾期未写的报告"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1" }, "到期的草稿会自动出现在这里，并提醒对应的老师 —— 官网上那句「每 4–8 节课一份进度报告」由系统兜底。"));
    }
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, rows.map((r) => {
      const days = Number(r.days_overdue || 0);
      return /* @__PURE__ */ React.createElement("div", { key: r.id, className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-3 flex items-center gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-sm truncate" }, r.display_name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, "周期至 ", fmtApiDate(r.period_end), " · 由 ", r.teacher_name || "未指派老师", " 撰写")), /* @__PURE__ */ React.createElement("span", { className: `ml-auto text-xs font-bold px-2 py-1 rounded whitespace-nowrap border
              ${days > 14 ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}` }, "逾期 ", days, " 天"), /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => onOpenStudent && onOpenStudent(r.student_id),
          className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold whitespace-nowrap"
        },
        "去写"
      ));
    }));
  }

  // legacy-root/src/panels/student_reports.jsx
  var { useState: useState6, useEffect: useEffect6, useCallback: useCallback6 } = React;
  function lastMonth() {
    const now = /* @__PURE__ */ new Date();
    const end = new Date(now.getFullYear(), now.getMonth(), 0);
    const start = new Date(end.getFullYear(), end.getMonth(), 1);
    const iso3 = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    return { start: iso3(start), end: iso3(end) };
  }
  function StudentProgressReports({ api, studentId, studentName, canWrite, canPublish, showToast }) {
    const [reports, setReports] = useState6(null);
    const [openId, setOpenId] = useState6(null);
    const [draft, setDraft] = useState6("");
    const [busy, setBusy] = useState6(false);
    const [period, setPeriod] = useState6(lastMonth);
    const load = useCallback6(async () => {
      try {
        const res = await api(`/students/${studentId}/progress-reports`);
        setReports(res.reports || []);
      } catch (e) {
        setReports([]);
      }
    }, [api, studentId]);
    useEffect6(() => {
      load();
    }, [load]);
    if (reports === null) return null;
    async function createDraft() {
      if (!period.start || !period.end) {
        showToast("请先选择周期", "error");
        return;
      }
      setBusy(true);
      try {
        const res = await api("/progress-reports", {
          method: "POST",
          body: JSON.stringify({ studentId, periodStart: period.start, periodEnd: period.end })
        });
        showToast("已按这个周期整理出草稿", "success");
        await load();
        setOpenId(res.report?.id || null);
        setDraft("");
      } catch (e) {
        showToast(e.message || "整理失败", "error");
      } finally {
        setBusy(false);
      }
    }
    async function saveComment(report) {
      setBusy(true);
      try {
        await api(`/progress-reports/${report.id}`, { method: "PATCH", body: JSON.stringify({ teacherComment: draft }) });
        showToast("评语已保存", "success");
        await load();
      } catch (e) {
        showToast(e.message || "保存失败", "error");
      } finally {
        setBusy(false);
      }
    }
    async function publish(report) {
      if (draft !== (report.teacher_comment || "")) await saveComment(report);
      setBusy(true);
      try {
        await api(`/progress-reports/${report.id}/publish`, { method: "POST" });
        showToast("已发布给家长", "success");
        setOpenId(null);
        await load();
      } catch (e) {
        showToast(e.message || "发布失败", "error");
      } finally {
        setBusy(false);
      }
    }
    return /* @__PURE__ */ React.createElement("div", { className: "border border-amber-100 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-amber-50 px-4 py-3 flex items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-amber-800" }, "成长报告", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-amber-500 text-xs" }, "(", reports.length, " 份)"))), canWrite && /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 bg-white border-b border-gray-100 flex flex-wrap items-end gap-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-400" }, "周期起", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: period.start,
        onChange: (e) => setPeriod((p) => ({ ...p, start: e.target.value })),
        className: "block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm text-gray-800"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "text-xs text-gray-400" }, "周期止", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: period.end,
        onChange: (e) => setPeriod((p) => ({ ...p, end: e.target.value })),
        className: "block mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm text-gray-800"
      }
    )), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: createDraft,
        disabled: busy,
        className: "min-h-[44px] px-4 rounded-xl bg-amber-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "整理这一段"
    )), !reports.length && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-sm text-gray-400 text-center" }, "还没有报告。选好周期点「整理这一段」，出勤、课堂笔记会自动填进草稿，你只需要写评语。"), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, reports.map((r) => {
      const open = openId === r.id;
      const published = r.status === "published";
      const content = r.content || {};
      const att = content.attendance || null;
      return /* @__PURE__ */ React.createElement("div", { key: r.id }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setOpenId(open ? null : r.id);
            setDraft(r.teacher_comment || "");
          },
          className: "w-full min-h-[44px] px-4 py-3 flex items-center justify-between gap-3 text-left active:bg-gray-50"
        },
        /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-700" }, fmtApiDate(r.period_start), " – ", fmtApiDate(r.period_end)),
        /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2 flex-shrink-0" }, r.teacher_name && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400" }, r.teacher_name), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-0.5 rounded-full ${published ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}` }, published ? "已发布" : "草稿"))
      ), open && /* @__PURE__ */ React.createElement("div", { className: "px-4 pb-4 space-y-3 bg-gray-50/60" }, att && Number(att.scheduled) > 0 && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-3 gap-2" }, [["应到", att.scheduled], ["已到", att.attended], ["出勤率", att.ratePercent == null ? "—" : `${att.ratePercent}%`]].map(([label, value]) => /* @__PURE__ */ React.createElement("div", { key: label, className: "bg-white p-3 rounded-xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, label), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, value)))), Array.isArray(content.lessons) && content.lessons.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-xl border border-gray-100 divide-y divide-gray-50 max-h-48 overflow-y-auto" }, content.lessons.map((l, i) => /* @__PURE__ */ React.createElement("div", { key: i, className: "px-3 py-2 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 mr-2" }, fmtApiDate(l.class_date)), /* @__PURE__ */ React.createElement("span", { className: "text-gray-700" }, l.note)))), published ? /* @__PURE__ */ React.createElement("div", { className: "bg-white p-3 rounded-xl border border-emerald-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-emerald-700 font-bold mb-1" }, "老师评语 · 已冻结"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-700 whitespace-pre-wrap" }, r.teacher_comment)) : canWrite ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement(
        "textarea",
        {
          value: draft,
          onChange: (e) => setDraft(e.target.value),
          rows: 4,
          placeholder: "上面的数字是证据，这段话才是报告本身。写给家长看。",
          className: "w-full px-3 py-2 border border-gray-200 rounded-xl text-sm text-gray-800"
        }
      ), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2 mt-2" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => saveComment(r),
          disabled: busy,
          className: "min-h-[44px] px-4 rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50"
        },
        "保存草稿"
      ), canPublish && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => publish(r),
          disabled: busy || !draft.trim(),
          className: "min-h-[44px] px-4 rounded-xl bg-emerald-600 text-white text-sm font-bold disabled:opacity-50"
        },
        "发布给家长"
      )), !draft.trim() && canPublish && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-1.5" }, "写完评语才能发布 —— 后端也是这么拦的。")) : /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400" }, "这份草稿由 ", r.teacher_name || "任课老师", " 撰写。")));
    })));
  }
  function StudentBillingAccount({ api, studentId, onOpenBilling }) {
    const [accounts, setAccounts] = useState6(null);
    useEffect6(() => {
      let live = true;
      api(`/billing/accounts?studentId=${encodeURIComponent(studentId)}`).then((res) => {
        if (live) setAccounts(res.accounts || []);
      }).catch(() => {
        if (live) setAccounts([]);
      });
      return () => {
        live = false;
      };
    }, [api, studentId]);
    if (!accounts || !accounts.length) return null;
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, accounts.map((a) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: a.id,
        onClick: () => onOpenBilling && onOpenBilling(a.id),
        className: "w-full min-h-[44px] bg-gray-50 p-4 rounded-2xl border border-gray-100 flex items-center justify-between gap-3 text-left active:bg-gray-100"
      },
      /* @__PURE__ */ React.createElement("span", null, /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400" }, "账单账户"), /* @__PURE__ */ React.createElement("span", { className: "block font-bold text-gray-800" }, a.name)),
      /* @__PURE__ */ React.createElement("span", { className: "text-right flex-shrink-0" }, /* @__PURE__ */ React.createElement("span", { className: "block text-xs text-gray-400" }, "未结"), /* @__PURE__ */ React.createElement("span", { className: `font-bold ${a.balance_cents > 0 ? "text-rose-600" : "text-emerald-600"}` }, aud(a.balance_cents)))
    )));
  }

  // legacy-root/src/panels/private_lessons.jsx
  var { useState: useState7, useEffect: useEffect7, useCallback: useCallback7, useMemo: useMemo4 } = React;
  var WEEKDAYS = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
  var STATUS_LABEL2 = { active: "进行中", paused: "暂停", ended: "已结束" };
  var WHO = [
    { value: "student", label: "学员请假" },
    { value: "studio", label: "工作室停课" }
  ];
  var iso2 = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  function PrivateLessonsPanel({ api, showToast, canWrite, canWritePolicy, students }) {
    const [view, setView] = useState7("upcoming");
    const [series, setSeries] = useState7([]);
    const [occurrences, setOccurrences] = useState7([]);
    const [credits, setCredits] = useState7([]);
    const [policy, setPolicy] = useState7(null);
    const [loading, setLoading] = useState7(true);
    const [error, setError] = useState7("");
    const [busy, setBusy] = useState7(false);
    const [cancelling, setCancelling] = useState7(null);
    const [creating, setCreating] = useState7(false);
    const range = useMemo4(() => {
      const start = /* @__PURE__ */ new Date();
      const end = /* @__PURE__ */ new Date();
      end.setDate(end.getDate() + 13);
      return { start: iso2(start), end: iso2(end) };
    }, []);
    const load = useCallback7(async () => {
      setLoading(true);
      try {
        const [s, o, c, p] = await Promise.all([
          api("/scheduling/series"),
          api(`/scheduling/occurrences?start=${range.start}&end=${range.end}`),
          api("/scheduling/credits"),
          api("/scheduling/policy")
        ]);
        setSeries(s.series || []);
        setOccurrences(o.occurrences || []);
        setCredits(c.credits || []);
        setPolicy(p.policy || null);
        setError("");
      } catch (e) {
        setError(e.status === 403 ? "这个工作室尚未开通一对一循环课。" : `加载失败：${e.message}`);
      } finally {
        setLoading(false);
      }
    }, [api, range.start, range.end]);
    useEffect7(() => {
      load();
    }, [load]);
    async function cancelOne(form) {
      setBusy(true);
      try {
        const res = await api("/scheduling/occurrences/cancel", {
          method: "POST",
          body: JSON.stringify({
            seriesId: form.seriesId,
            onDate: form.onDate,
            cancelledBy: form.cancelledBy,
            reason: form.reason
          })
        });
        showToast(
          `已记录：${res.chargeable ? "照常计费" : "不计费"}、${res.counts_for_pay ? "老师照付课酬" : "不计课酬"}${res.grants_credit ? "、已发一次补课额度" : ""}`,
          "success"
        );
        setCancelling(null);
        await load();
      } catch (e) {
        showToast(e.message || "取消失败", "error");
      } finally {
        setBusy(false);
      }
    }
    async function undo(exceptionId) {
      setBusy(true);
      try {
        await api(`/scheduling/exceptions/${exceptionId}`, { method: "DELETE" });
        showToast("已撤销这次变更，随之发出的补课额度也已作废", "success");
        await load();
      } catch (e) {
        showToast(e.message || "撤销失败", "error");
      } finally {
        setBusy(false);
      }
    }
    async function createSeries(form) {
      setBusy(true);
      try {
        await api("/scheduling/series", {
          method: "POST",
          body: JSON.stringify({
            studentId: form.studentId,
            weekday: Number(form.weekday),
            startTime: form.startTime,
            durationMinutes: Number(form.durationMinutes),
            startsOn: form.startsOn,
            room: form.room,
            note: form.note
          })
        });
        showToast("循环课已排好", "success");
        setCreating(false);
        await load();
      } catch (e) {
        showToast(e.message || "排课失败", "error");
      } finally {
        setBusy(false);
      }
    }
    async function useCredit(credit) {
      const onDate = window.prompt(
        `给 ${credit.student_name} 安排补课，日期（YYYY-MM-DD）：`,
        range.start
      );
      if (!onDate) return;
      setBusy(true);
      try {
        await api(`/scheduling/credits/${credit.id}/consume`, {
          method: "POST",
          body: JSON.stringify({ onDate })
        });
        showToast("补课已登记，这次额度已用掉", "success");
        await load();
      } catch (e) {
        showToast(e.message || "登记失败", "error");
      } finally {
        setBusy(false);
      }
    }
    if (loading) return /* @__PURE__ */ React.createElement("div", { className: "p-6 text-sm text-gray-500" }, "正在加载一对一课程…");
    if (error) return /* @__PURE__ */ React.createElement("div", { className: "p-6 text-sm text-red-600" }, error);
    const liveCredits = credits.filter((c) => !c.is_expired);
    const expiredCredits = credits.filter((c) => c.is_expired);
    return /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-3 gap-3" }, /* @__PURE__ */ React.createElement(
      Stat,
      {
        label: "循环课",
        value: String(series.filter((s) => s.status === "active").length),
        sub: `${series.filter((s) => s.status === "paused").length} 个暂停中`
      }
    ), /* @__PURE__ */ React.createElement(
      Stat,
      {
        label: "未来两周",
        value: String(occurrences.filter((o) => !o.exception_kind).length),
        sub: `${occurrences.filter((o) => o.exception_kind).length} 次有变更`
      }
    ), /* @__PURE__ */ React.createElement(
      Stat,
      {
        label: "待补课",
        value: String(liveCredits.length),
        tone: liveCredits.length ? "warn" : void 0,
        sub: expiredCredits.length ? `${expiredCredits.length} 次已过期` : "没有欠着的"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center gap-2" }, [["upcoming", "未来两周"], ["series", "循环课"], ["credits", "补课额度"], ["policy", "请假规则"]].map(([key, label]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key,
        type: "button",
        onClick: () => setView(key),
        className: `min-h-[44px] px-4 rounded-xl text-sm font-bold border ${view === key ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-700 border-gray-200"}`
      },
      label
    )), canWrite && view === "series" && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setCreating(true),
        className: "ml-auto min-h-[44px] px-4 rounded-xl bg-emerald-600 text-white text-sm font-bold"
      },
      "排一节循环课"
    )), view === "upcoming" && /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, !occurrences.length && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-sm text-gray-400 text-center" }, "未来两周没有一对一课程。排课后会自动展开到这里，节假日与暂停会自动跳过。"), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, occurrences.map((o) => /* @__PURE__ */ React.createElement(
      "div",
      {
        key: `${o.series_id}-${o.on_date}`,
        className: `px-4 py-3 flex flex-wrap items-center gap-3 ${o.exception_kind ? "bg-gray-50/60" : ""}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-700 w-28 flex-shrink-0" }, fmtApiDate(o.on_date)),
      /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-500 w-14 flex-shrink-0" }, o.start_time),
      /* @__PURE__ */ React.createElement("span", { className: `text-sm flex-1 min-w-0 truncate ${o.exception_kind ? "text-gray-400 line-through" : "text-gray-800 font-bold"}` }, o.student_name, o.teacher_name && /* @__PURE__ */ React.createElement("span", { className: "ml-2 text-xs font-normal text-gray-400" }, o.teacher_name)),
      o.exception_kind ? /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2 flex-shrink-0" }, /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-0.5 rounded-full ${o.chargeable ? "bg-amber-50 text-amber-700" : "bg-gray-100 text-gray-500"}` }, o.chargeable ? "计费" : "不计费"), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-0.5 rounded-full ${o.counts_for_pay ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}` }, o.counts_for_pay ? "算课酬" : "不算课酬"), canWrite && /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => undo(o.exception_id),
          disabled: busy,
          className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-600 disabled:opacity-50"
        },
        "撤销"
      )) : canWrite ? /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => setCancelling({ seriesId: o.series_id, onDate: o.on_date, name: o.student_name }),
          className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700 flex-shrink-0"
        },
        "请假 / 停课"
      ) : null
    )))), view === "series" && /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, !series.length && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-sm text-gray-400 text-center" }, "还没有一对一循环课。排一节后，它每周自动出现，不用每周手动加。"), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, series.map((s) => /* @__PURE__ */ React.createElement("div", { key: s.id, className: "px-4 py-3 flex flex-wrap items-center gap-3" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-800 flex-1 min-w-0 truncate" }, s.student_name), /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-500" }, WEEKDAYS[s.weekday], " ", s.start_time, " · ", s.duration_minutes, " 分钟"), s.teacher_name && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400" }, s.teacher_name), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-0.5 rounded-full ${s.status === "active" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}` }, STATUS_LABEL2[s.status], s.status === "paused" && s.paused_to && ` 至 ${fmtApiDate(s.paused_to)}`), canWrite && /* @__PURE__ */ React.createElement(
      SeriesActions,
      {
        series: s,
        api,
        showToast,
        onDone: load,
        busy,
        setBusy
      }
    ))))), view === "credits" && /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl overflow-hidden" }, !credits.length && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-6 text-sm text-gray-400 text-center" }, "没有欠着的补课。提前请假产生的额度会出现在这里。"), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, credits.map((c) => /* @__PURE__ */ React.createElement("div", { key: c.id, className: "px-4 py-3 flex flex-wrap items-center gap-3" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-800 flex-1 min-w-0 truncate" }, c.student_name), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400" }, fmtApiDate(c.earned_from_date), " 请假产生"), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-0.5 rounded-full ${c.is_expired ? "bg-gray-100 text-gray-500" : "bg-amber-50 text-amber-700"}` }, c.is_expired ? "已过期" : c.expires_on ? `${fmtApiDate(c.expires_on)} 前有效` : "不过期"), canWrite && !c.is_expired && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => useCredit(c),
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg bg-indigo-600 text-white text-xs font-bold disabled:opacity-50"
      },
      "安排补课"
    ))))), view === "policy" && policy && /* @__PURE__ */ React.createElement(
      PolicyEditor,
      {
        policy,
        api,
        showToast,
        canWrite: canWritePolicy,
        onSaved: load
      }
    ), cancelling && /* @__PURE__ */ React.createElement(
      CancelDialog,
      {
        target: cancelling,
        policy,
        busy,
        onClose: () => setCancelling(null),
        onSubmit: cancelOne
      }
    ), creating && /* @__PURE__ */ React.createElement(
      CreateDialog,
      {
        students,
        busy,
        onClose: () => setCreating(false),
        onSubmit: createSeries
      }
    ));
  }
  function Stat({ label, value, sub, tone }) {
    const accent = tone === "warn" ? "text-amber-700" : "text-gray-800";
    return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, label), /* @__PURE__ */ React.createElement("p", { className: `text-2xl font-bold ${accent}` }, value), sub && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, sub));
  }
  function SeriesActions({ series, api, showToast, onDone, busy, setBusy }) {
    async function setStatus(status) {
      setBusy(true);
      try {
        await api(`/scheduling/series/${series.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status })
        });
        showToast(status === "ended" ? "这门循环课已结束" : `已${status === "paused" ? "暂停" : "恢复"}`, "success");
        await onDone();
      } catch (e) {
        showToast(e.message || "操作失败", "error");
      } finally {
        setBusy(false);
      }
    }
    return /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2 flex-shrink-0" }, series.status === "active" ? /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setStatus("paused"),
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-700 disabled:opacity-50"
      },
      "暂停"
    ) : /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setStatus("active"),
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg border border-emerald-200 bg-white text-xs font-bold text-emerald-700 disabled:opacity-50"
      },
      "恢复"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setStatus("ended"),
        disabled: busy,
        className: "min-h-[44px] px-3 rounded-lg border border-gray-200 bg-white text-xs font-bold text-gray-500 disabled:opacity-50"
      },
      "结束"
    ));
  }
  function CancelDialog({ target, policy, busy, onClose, onSubmit }) {
    const [cancelledBy, setCancelledBy] = useState7("student");
    const [reason, setReason] = useState7("");
    return /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 space-y-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-lg font-bold text-gray-800" }, target.name, " · ", fmtApiDate(target.onDate)), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, "这一下决定三件事：还收不收钱、老师算不算课酬、要不要补一次课。")), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, WHO.map((w) => /* @__PURE__ */ React.createElement(
      "label",
      {
        key: w.value,
        className: `flex items-center gap-3 min-h-[44px] px-4 rounded-xl border cursor-pointer ${cancelledBy === w.value ? "border-indigo-500 bg-indigo-50" : "border-gray-200"}`
      },
      /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "radio",
          name: "cancelledBy",
          value: w.value,
          checked: cancelledBy === w.value,
          onChange: () => setCancelledBy(w.value)
        }
      ),
      /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-800" }, w.label)
    ))), policy && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, cancelledBy === "studio" ? `工作室停课：${policy.studio_cancel_chargeable ? "照常计费" : "不计费"}，老师照付课酬。` : `提前 ${policy.notice_hours} 小时以上算按时请假，${policy.makeup_credit_on_notice ? "发补课额度" : "不发补课额度"}；临时请假${policy.late_absence_chargeable ? "照常计费" : "不计费"}。`, " ", "提前量由系统按工作室时钟计算。"), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        value: reason,
        onChange: (e) => setReason(e.target.value),
        rows: 2,
        placeholder: "备注（选填）：家长来电说明的原因",
        className: "w-full px-3 py-2 border border-gray-200 rounded-xl text-sm"
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: onClose,
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50"
      },
      "取消"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        disabled: busy,
        onClick: () => onSubmit({ ...target, cancelledBy, reason }),
        className: "flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "确认记录"
    ))));
  }
  function CreateDialog({ students, busy, onClose, onSubmit }) {
    const [form, setForm] = useState7({
      studentId: "",
      weekday: "1",
      startTime: "16:00",
      durationMinutes: "30",
      startsOn: iso2(/* @__PURE__ */ new Date()),
      room: "",
      note: ""
    });
    const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
    return /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white w-full sm:max-w-md rounded-t-2xl sm:rounded-2xl p-5 space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-lg font-bold text-gray-800" }, "排一节循环课"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500" }, "每周同一时间自动出现，节假日与暂停会自动跳过。"), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "学员", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: form.studentId,
        onChange: set("studentId"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "请选择"),
      (students || []).map((s) => /* @__PURE__ */ React.createElement("option", { key: s.id, value: s.id }, s.name))
    )), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "星期", /* @__PURE__ */ React.createElement(
      "select",
      {
        value: form.weekday,
        onChange: set("weekday"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      },
      WEEKDAYS.map((label, i) => /* @__PURE__ */ React.createElement("option", { key: i, value: i }, label))
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "开始时间", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "time",
        value: form.startTime,
        onChange: set("startTime"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "时长（分钟）", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "5",
        step: "5",
        value: form.durationMinutes,
        onChange: set("durationMinutes"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "起始日期", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: form.startsOn,
        onChange: set("startsOn"),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 pt-1" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: onClose,
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-700 disabled:opacity-50"
      },
      "取消"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => onSubmit(form),
        disabled: busy || !form.studentId,
        className: "flex-1 min-h-[44px] rounded-xl bg-emerald-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "排课"
    ))));
  }
  function PolicyEditor({ policy, api, showToast, canWrite, onSaved }) {
    const [form, setForm] = useState7(policy);
    const [busy, setBusy] = useState7(false);
    async function save() {
      setBusy(true);
      try {
        await api("/scheduling/policy", { method: "PUT", body: JSON.stringify(form) });
        showToast("请假规则已更新", "success");
        await onSaved();
      } catch (e) {
        showToast(e.message || "保存失败", "error");
      } finally {
        setBusy(false);
      }
    }
    const toggle = (key) => () => setForm((f) => ({ ...f, [key]: !f[key] }));
    return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-xl p-4 space-y-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500" }, "这四项决定一次请假的后果。它们是四个独立的开关，不是一个 —— 临时请假通常「收钱」且「照付老师」，工作室停课通常两者相反。"), /* @__PURE__ */ React.createElement("div", { className: "grid sm:grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "提前多少小时算按时请假", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        value: form.notice_hours,
        disabled: !canWrite,
        onChange: (e) => setForm((f) => ({ ...f, notice_hours: Number(e.target.value) })),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm disabled:bg-gray-50"
      }
    )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs text-gray-400" }, "补课额度多少天后过期（留空＝不过期）", /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "1",
        value: form.makeup_expiry_days ?? "",
        disabled: !canWrite,
        onChange: (e) => setForm((f) => ({
          ...f,
          makeup_expiry_days: e.target.value === "" ? null : Number(e.target.value)
        })),
        className: "block w-full mt-1 min-h-[44px] px-3 border border-gray-200 rounded-xl text-sm disabled:bg-gray-50"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, [
      ["makeup_credit_on_notice", "按时请假发一次补课额度"],
      ["late_absence_chargeable", "临时请假照常计费"],
      ["late_absence_pays_teacher", "临时请假老师照付课酬"],
      ["studio_cancel_chargeable", "工作室停课照常计费"]
    ].map(([key, label]) => /* @__PURE__ */ React.createElement(
      "label",
      {
        key,
        className: `flex items-center gap-3 min-h-[44px] px-4 rounded-xl border ${canWrite ? "cursor-pointer" : ""} ${form[key] ? "border-indigo-500 bg-indigo-50" : "border-gray-200"}`
      },
      /* @__PURE__ */ React.createElement("input", { type: "checkbox", checked: !!form[key], disabled: !canWrite, onChange: toggle(key) }),
      /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-800" }, label)
    ))), canWrite && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: save,
        disabled: busy,
        className: "min-h-[44px] px-5 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50"
      },
      "保存规则"
    ));
  }

  // legacy-root/src/components.jsx
  var { useState: useState8, useEffect: useEffect8, useMemo: useMemo5, useRef: useRef2, useCallback: useCallback8 } = React;
  var tenantSlug = window.STUDIOSAAS_TENANT_SLUG || new URLSearchParams(location.search).get("tenant") || (location.pathname.match(/^\/([^/]+)(?:\/cms)?\/?$/) || [])[1] || "";
  var nowAU = () => (/* @__PURE__ */ new Date()).toLocaleString("en-AU", {
    timeZone: "Australia/Melbourne",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false
  });
  var todayISO = () => (/* @__PURE__ */ new Date()).toLocaleDateString("en-CA");
  var shiftDate = (iso3, delta) => {
    const d = /* @__PURE__ */ new Date(`${iso3}T12:00:00`);
    d.setDate(d.getDate() + delta);
    return d.toLocaleDateString("en-CA");
  };
  var fmtDate = (s) => {
    if (!s) return "—";
    const m = String(s).match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? `${m[3]}/${m[2]}/${m[1]}` : String(s).split(" ")[0];
  };
  var daysSince = (iso3) => {
    if (!iso3) return 9999;
    const d = new Date(iso3);
    return isNaN(d) ? 9999 : Math.floor((Date.now() - d) / 864e5);
  };
  var fmtDT = (s) => {
    const m = String(s || "").match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    return m ? `${m[1]} ${m[2]}` : s ? String(s) : "—";
  };
  var REG_STATUS_ZH = {
    pending: "待审核",
    contacted: "已联系",
    trial_booked: "已约试听",
    waiting: "跟进中",
    approved: "已批准",
    converted: "已建档",
    rejected: "已拒绝",
    duplicate: "重复申请",
    lost: "已流失",
    archived: "已归档"
  };
  var TENANT_SLUG = window.STUDIOSAAS_TENANT_SLUG || "";
  var CMS_ROUTE_TABS = /* @__PURE__ */ new Set([
    "dashboard",
    "roster",
    "courses",
    "students",
    "works",
    "new_student",
    "pending",
    "billing",
    "topup",
    "finance",
    "logs",
    "stats",
    "settings"
  ]);
  var CMS_ROUTE_SECTIONS = Object.assign(/* @__PURE__ */ Object.create(null), {
    settings: {
      allowed: [
        "account",
        "team",
        "operational",
        "billing-identity",
        "integrations",
        "maintenance",
        "workspace"
      ],
      fallback: "account"
    },
    /* 排课页的两个职能。`checkin` 是 fallback，也就是没有 `?section=` 时
       落到的分区 —— 不按角色推导、不记忆上次选择：这一页每天被不同的人在
       不同设备上打开，记忆会让两个人看到不同的首屏，而他们要对的是同一份
       名单。 */
    roster: {
      allowed: ["checkin", "plan"],
      fallback: "checkin"
    }
  });
  var readCmsSection = (tab, params) => {
    const scope = CMS_ROUTE_SECTIONS[tab];
    if (!scope || !Array.isArray(scope.allowed)) return "";
    const requested = params.get("section") || "";
    return scope.allowed.includes(requested) ? requested : scope.fallback;
  };
  var readCmsRoute = () => {
    const params = new URLSearchParams(window.location.search || "");
    const requested = params.get("view") || params.get("tab") || "dashboard";
    const tab = CMS_ROUTE_TABS.has(requested) ? requested : "dashboard";
    return {
      tab,
      pendingTab: params.get("type") === "booking" || params.get("type") === "bookings" ? "bookings" : params.get("type") === "reports" ? "reports" : "registrations",
      /* Scoped, not raw: a `section` that arrived with another tab must not
         become the settings page's state. */
      settingsSection: tab === "settings" ? readCmsSection(tab, params) : "account",
      rosterSection: tab === "roster" ? readCmsSection(tab, params) : "checkin",
      recordId: params.get("id") || ""
    };
  };
  var v1Api = async (path, options = {}) => {
    const headers = {
      "Content-Type": "application/json",
      "X-Requested-With": "StudioSaaS",
      ...options.headers || {}
    };
    const r = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1${path}`, {
      credentials: "include",
      ...options,
      headers
    });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) {
      const err = new Error(d.message || d.error || `HTTP ${r.status}`);
      err.status = r.status;
      err.details = d.details || null;
      err.code = d.error || null;
      err.payload = d;
      throw err;
    }
    return d;
  };
  var AUDIT_ACTION_ZH = {
    "student.created": "新生建档",
    "student.updated": "更新档案",
    "student.archived": "归档学员",
    "daily_roster.added": "加入排课",
    "daily_roster.cancelled": "取消排课",
    "daily_roster.restored": "恢复排课",
    "daily_roster.updated": "调整排课",
    "schedule.created": "新增班次",
    "schedule.updated": "修改班次",
    "schedule.deleted": "删除班次",
    "portfolio.uploaded": "上传作品",
    "portfolio.updated": "修改作品",
    "portfolio.deleted": "删除作品",
    "portfolio.share_link_created": "生成分享链接",
    "portfolio.share_link_revoked": "撤销分享链接",
    "registration.created": "收到注册申请",
    "student_access.generated": "生成家长访问码",
    "student_access.revoked": "撤销家长访问码",
    "student_access.unlocked": "解锁家长访问",
    "package.created": "新增课包",
    "package.updated": "修改课包",
    "package.archived": "下架课包",
    "course.created": "新增课程",
    "course.updated": "修改课程",
    "course.archived": "归档课程",
    "data.exported": "导出数据",
    "brand.published": "发布网站",
    "team.member_upserted": "新增/更新成员",
    "team.member_updated": "调整成员权限",
    "operations.default_class_time_updated": "修改默认上课时间"
  };
  var auditNote = (action, meta) => {
    const m = meta || {};
    if (action === "daily_roster.added") {
      const n = Array.isArray(m.students) ? m.students.length : 1;
      const when = m.classTime ? ` ${m.classTime}` : "";
      return `${m.date || ""}${when}${n > 1 ? ` · ${n} 人` : ""}${m.oneToOne ? " · 1 对 1" : ""}`.trim();
    }
    if (action.startsWith("daily_roster.")) return String(m.date || "");
    if (action === "data.exported") return `${m.type || ""}${m.rows ? ` · ${m.rows} 行` : ""}`.trim();
    if (action === "operations.default_class_time_updated") return String(m.defaultClassTime || m.value || "");
    if (action.startsWith("schedule.")) return String(m.label || m.name || "");
    if (action.startsWith("team.")) return String(m.email || m.role || "");
    if (action === "registration.created") return String(m.name || m.mobile || "");
    return String(m.title || m.name || m.note || "");
  };
  var parseMonthKey = (ds) => {
    if (!ds) return null;
    const s = String(ds);
    const a = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (a) return `${a[3]}-${a[2].padStart(2, "0")}`;
    const b = s.match(/^(\d{4})\/(\d{1,2})\/(\d{1,2})/);
    if (b) return `${b[1]}-${b[2].padStart(2, "0")}`;
    const c = s.match(/^(\d{4})-(\d{2})/);
    if (c) return `${c[1]}-${c[2]}`;
    return null;
  };
  var fmtMK = (k) => {
    if (!k) return "";
    const [y, m] = k.split("-");
    return `${m}/${y}`;
  };
  var tenantOwnedLogoUrl = (brand) => {
    const source = brand?.logo_url || brand?.logoUrl || "";
    return ["/logo.png", "/logo-light.png", "/favicon.svg"].includes(source) ? "" : source;
  };
  function TenantBrandLogo({ className = "" }) {
    const [brand, setBrand] = useState8(() => window.STUDIOSAAS_BRAND || {});
    useEffect8(() => {
      const syncBrand = (event) => setBrand(event?.detail || window.STUDIOSAAS_BRAND || {});
      window.addEventListener("studiosaas:brand", syncBrand);
      syncBrand();
      return () => window.removeEventListener("studiosaas:brand", syncBrand);
    }, []);
    const source = tenantOwnedLogoUrl(brand);
    if (!source) return null;
    return /* @__PURE__ */ React.createElement(
      "img",
      {
        src: source,
        alt: `${brand.name || brand.studioName || "Studio"} logo`,
        className,
        onError: (event) => {
          event.currentTarget.hidden = true;
        }
      }
    );
  }
  function BarChart({ items, color = "var(--info)", h = 140, prefix = "" }) {
    if (!items?.length) return /* @__PURE__ */ React.createElement("p", { className: "text-center text-gray-400 text-sm py-6" }, "暂无数据");
    const max = Math.max(...items.map((d) => d.v), 0.01);
    const W = 54, PAD = 6;
    return /* @__PURE__ */ React.createElement("svg", { viewBox: `0 0 ${items.length * W} ${h + 24}`, className: "w-full overflow-visible" }, items.map((d, i) => {
      const bh = Math.max(2, d.v / max * (h - 12));
      return /* @__PURE__ */ React.createElement("g", { key: i, transform: `translate(${i * W + PAD},0)` }, /* @__PURE__ */ React.createElement("rect", { x: 4, y: h - bh, width: W - PAD * 2, height: bh, fill: color, rx: 3, opacity: 0.82 }), d.v > 0 && /* @__PURE__ */ React.createElement("text", { x: (W - PAD * 2) / 2 + 4, y: h - bh - 4, textAnchor: "middle", fontSize: 8, fill: "var(--ink2)", fontWeight: "bold" }, prefix, d.v), /* @__PURE__ */ React.createElement("text", { x: (W - PAD * 2) / 2 + 4, y: h + 16, textAnchor: "middle", fontSize: 7.5, fill: "var(--muted)" }, d.l));
    }));
  }
  function Tabs({ idBase, label, items, value, onChange, className = "" }) {
    const refs = useRef2({});
    const stripRef = useRef2(null);
    const order = items.map((i) => i.value);
    const alignSelected = useCallback8(() => {
      const strip = stripRef.current, node = refs.current[value];
      if (!strip || !node || typeof node.getBoundingClientRect !== "function") return;
      const view = strip.getBoundingClientRect(), tab = node.getBoundingClientRect();
      const overLeft = view.left - tab.left;
      const overRight = tab.right - view.right;
      if (overLeft <= 0 && overRight <= 0) return;
      strip.scrollLeft += overLeft > 0 ? -(overLeft + 8) : overRight + 8;
    }, [value]);
    useEffect8(() => {
      alignSelected();
      const strip = stripRef.current;
      if (!strip || typeof ResizeObserver !== "function") return;
      const observer = new ResizeObserver(() => alignSelected());
      observer.observe(strip);
      return () => observer.disconnect();
    }, [alignSelected, items.length]);
    const onKeyDown = (event) => {
      const keys = { ArrowRight: 1, ArrowLeft: -1 };
      let next = null;
      if (event.key in keys) next = order[(order.indexOf(value) + keys[event.key] + order.length) % order.length];
      else if (event.key === "Home") next = order[0];
      else if (event.key === "End") next = order[order.length - 1];
      if (!next) return;
      event.preventDefault();
      onChange(next);
      const node = refs.current[next];
      if (node) node.focus();
    };
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        role: "tablist",
        "aria-label": label,
        onKeyDown,
        ref: stripRef,
        className: `flex gap-1 overflow-x-auto border-b border-gray-200 ${className}`
      },
      items.map((item) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: item.value,
          type: "button",
          role: "tab",
          id: `${idBase}-tab-${item.value}`,
          "aria-selected": value === item.value,
          "aria-controls": `${idBase}-panel-${item.value}`,
          tabIndex: value === item.value ? 0 : -1,
          ref: (node) => {
            refs.current[item.value] = node;
          },
          onClick: () => onChange(item.value),
          className: `relative min-h-[44px] px-4 text-sm font-bold whitespace-nowrap flex items-center gap-1.5 ${value === item.value ? "text-indigo-700" : "text-gray-500"}`
        },
        item.icon && /* @__PURE__ */ React.createElement(Icon, { name: item.icon, className: "w-4 h-4" }),
        item.label,
        value === item.value && /* @__PURE__ */ React.createElement("span", { "aria-hidden": "true", className: "absolute left-2 right-2 bottom-0 h-0.5 rounded-full bg-indigo-600" })
      ))
    );
  }
  function TabPanel({ idBase, name, active, children }) {
    if (!active) return null;
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        role: "tabpanel",
        id: `${idBase}-panel-${name}`,
        "aria-labelledby": `${idBase}-tab-${name}`,
        tabIndex: 0,
        className: "space-y-3 focus:outline-none"
      },
      children
    );
  }
  function EmptyState({ icon = null, main = "暂无数据", sub = "", action = null, onAction = null }) {
    const glyph = icon || /* @__PURE__ */ React.createElement(Icon, { name: "inbox", className: "w-8 h-8" });
    return /* @__PURE__ */ React.createElement("div", { className: "cms-empty-state" }, /* @__PURE__ */ React.createElement("div", { className: "cms-empty-state__icon" }, glyph), /* @__PURE__ */ React.createElement("p", { className: "cms-empty-state__title" }, main), sub && /* @__PURE__ */ React.createElement("p", { className: "cms-empty-state__description" }, sub), action && onAction && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: onAction,
        className: "cms-empty-state__action"
      },
      action
    ));
  }
  function BalBadge({ n }) {
    const v = parseInt(n, 10) || 0;
    if (v === 0) return /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-red-100 text-red-700 whitespace-nowrap" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-3.5 h-3.5" }), "0");
    if (v <= 2) return /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-orange-100 text-orange-700 whitespace-nowrap" }, /* @__PURE__ */ React.createElement(Icon, { name: "bolt", className: "w-3.5 h-3.5" }), v);
    if (v <= 4) return /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-amber-100 text-amber-700 whitespace-nowrap" }, /* @__PURE__ */ React.createElement(Icon, { name: "bolt", className: "w-3.5 h-3.5" }), v);
    return /* @__PURE__ */ React.createElement("span", { className: "px-2.5 py-1 rounded-lg text-xs font-bold bg-green-100 text-green-700 whitespace-nowrap" }, v);
  }
  function Toast({ msg, type, action, onDone }) {
    useEffect8(() => {
      const t = setTimeout(onDone, action ? 6e3 : 2700);
      return () => clearTimeout(t);
    }, []);
    const bg = type === "error" ? "bg-red-600" : type === "warn" ? "bg-amber-500" : "bg-gray-900";
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        role: "status",
        "aria-live": "polite",
        className: `toast toast-bottom fixed left-1/2 -translate-x-1/2 z-[999] ${bg} text-white px-5 py-3 rounded-2xl shadow-2xl text-sm font-bold max-w-xs text-center`
      },
      /* @__PURE__ */ React.createElement("div", { className: "inline-flex items-center gap-2 justify-center" }, /* @__PURE__ */ React.createElement(Icon, { name: type === "error" ? "warning" : type === "warn" ? "bolt" : "check", className: "w-4 h-4" }), /* @__PURE__ */ React.createElement("span", null, msg)),
      action && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            action.onClick();
            onDone();
          },
          className: "mt-2 w-full bg-white/20 active:bg-white/30 rounded-lg py-1.5 text-xs font-bold"
        },
        action.label
      )
    );
  }
  function CmsNotificationCenter({
    notifications = [],
    unreadCount = 0,
    open,
    onToggle,
    onSelect,
    onMarkAllRead,
    loadError = ""
  }) {
    const formatCreatedAt = (value) => {
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return "";
      return date.toLocaleString("zh-CN", { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" });
    };
    return /* @__PURE__ */ React.createElement("div", { className: "relative flex-shrink-0" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: onToggle,
        "aria-label": "打开通知",
        "aria-expanded": open,
        className: "relative w-9 h-9 flex items-center justify-center rounded-lg cms-chrome-item"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "bell", className: "w-5 h-5" }),
      unreadCount > 0 && /* @__PURE__ */ React.createElement(
        "span",
        {
          "aria-label": `${unreadCount} 条未读通知`,
          className: "absolute -top-1 -right-1 bg-red-500 text-white text-[9px] font-bold px-1 rounded-full min-w-[16px] leading-4 text-center"
        },
        unreadCount > 99 ? "99+" : unreadCount
      )
    ), open && /* @__PURE__ */ React.createElement("div", { className: "absolute right-0 top-11 z-[70] w-[min(92vw,24rem)] bg-white border border-gray-200 rounded-2xl shadow-2xl overflow-hidden text-gray-900" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 border-b border-gray-100 flex items-center gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "font-bold text-sm flex-1" }, "通知"), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: onMarkAllRead,
        disabled: unreadCount === 0,
        className: "text-xs font-bold text-indigo-600 disabled:text-gray-300 min-h-[44px]"
      },
      "全部已读"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: onToggle,
        "aria-label": "关闭通知",
        className: "text-gray-400 text-xl leading-none px-1 min-h-[44px]"
      },
      "×"
    )), loadError && /* @__PURE__ */ React.createElement("div", { role: "status", className: "px-4 py-2 text-xs font-bold text-amber-700 bg-amber-50 border-b border-amber-100" }, loadError), /* @__PURE__ */ React.createElement("div", { className: "max-h-[min(60vh,24rem)] overflow-y-auto" }, notifications.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "px-4 py-10 text-center text-sm text-gray-400" }, "暂无通知") : notifications.map((notification) => /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        key: notification.id,
        onClick: () => onSelect(notification),
        "aria-label": `${notification.title}${notification.read ? "，已读" : "，未读"}`,
        className: `w-full text-left px-4 py-3 border-b border-gray-100 last:border-b-0 hover:bg-gray-50 active:bg-gray-100 ${notification.read ? "bg-white" : "bg-indigo-50/60"}`
      },
      /* @__PURE__ */ React.createElement("div", { className: "flex items-start gap-2.5" }, /* @__PURE__ */ React.createElement("span", { className: `mt-1.5 w-2 h-2 rounded-full flex-shrink-0 ${notification.read ? "bg-gray-200" : "bg-indigo-500"}`, "aria-hidden": "true" }), /* @__PURE__ */ React.createElement("span", { className: "min-w-0 flex-1" }, /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-sm truncate" }, notification.title), /* @__PURE__ */ React.createElement("span", { className: "text-[10px] text-gray-400 flex-shrink-0" }, formatCreatedAt(notification.createdAt))), /* @__PURE__ */ React.createElement("span", { className: "block mt-1 text-xs text-gray-600 leading-relaxed break-words" }, notification.summary)))
    )))));
  }
  function useModalFocus(isOpen, onClose, dialogRef, initialFocusRef = null) {
    const closeRef = useRef2(onClose);
    closeRef.current = onClose;
    useEffect8(() => {
      if (!isOpen) return;
      const previousFocus = document.activeElement;
      const selector = [
        "button:not([disabled])",
        "[href]",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        '[tabindex]:not([tabindex="-1"])'
      ].join(",");
      const onKey = (event) => {
        if (event.key === "Escape") {
          event.preventDefault();
          closeRef.current();
          return;
        }
        if (event.key !== "Tab") return;
        const focusable = [...dialogRef.current?.querySelectorAll(selector) || []];
        if (!focusable.length) {
          event.preventDefault();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      };
      document.addEventListener("keydown", onKey);
      const timer = setTimeout(() => {
        const target = initialFocusRef?.current || dialogRef.current?.querySelector(selector);
        target?.focus();
      }, 0);
      return () => {
        document.removeEventListener("keydown", onKey);
        clearTimeout(timer);
        if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
      };
    }, [isOpen, dialogRef, initialFocusRef]);
  }
  function ConfirmDialog({ dialog, onClose }) {
    const [typed, setTyped] = useState8("");
    const boxRef = useRef2(null);
    const onCloseRef = useRef2(onClose);
    onCloseRef.current = onClose;
    useEffect8(() => {
      setTyped(dialog?.promptDefault || "");
    }, [dialog]);
    const dismiss = () => {
      if (dialog && dialog.acknowledge && dialog.onConfirm) dialog.onConfirm();
      onCloseRef.current();
    };
    const dismissRef = useRef2(dismiss);
    dismissRef.current = dismiss;
    useEffect8(() => {
      if (!dialog) return;
      const prevFocus = document.activeElement;
      const onKey = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          dismissRef.current();
          return;
        }
        if (e.key !== "Tab") return;
        const focusable = [...boxRef.current?.querySelectorAll(
          'button:not([disabled]), input:not([disabled]), [href], [tabindex]:not([tabindex="-1"])'
        ) || []];
        if (!focusable.length) {
          e.preventDefault();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      };
      document.addEventListener("keydown", onKey);
      const t = setTimeout(() => {
        const box = boxRef.current;
        if (box && !box.contains(document.activeElement)) {
          const target = box.querySelector("input, button");
          if (target) target.focus();
        }
      }, 0);
      return () => {
        document.removeEventListener("keydown", onKey);
        clearTimeout(t);
        if (prevFocus && typeof prevFocus.focus === "function") prevFocus.focus();
      };
    }, [dialog]);
    if (!dialog) return null;
    const needsText = Boolean(dialog.requireText);
    const isPrompt = Boolean(dialog.prompt);
    const ready = needsText ? typed.trim() === String(dialog.requireText).trim() : !isPrompt || !dialog.promptRequired || Boolean(typed.trim());
    const confirmLabel = dialog.confirmText || (dialog.acknowledge ? "知道了 / OK" : "确认");
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "fixed inset-0 bg-black/50 z-[95] flex items-center justify-center p-4",
        onClick: dismiss,
        role: "dialog",
        "aria-modal": "true",
        "aria-describedby": "confirm-dialog-message",
        "aria-labelledby": dialog.title ? "confirm-dialog-title" : void 0,
        "aria-label": dialog.title ? void 0 : "确认操作"
      },
      /* @__PURE__ */ React.createElement("div", { ref: boxRef, className: "bg-white rounded-2xl p-6 max-w-sm w-full shadow-2xl anim", onClick: (e) => e.stopPropagation() }, dialog.title && /* @__PURE__ */ React.createElement("p", { id: "confirm-dialog-title", className: "font-bold text-gray-800 mb-2" }, dialog.title), /* @__PURE__ */ React.createElement("p", { id: "confirm-dialog-message", className: "text-gray-500 text-sm leading-relaxed mb-4 whitespace-pre-line" }, dialog.message), needsText && /* @__PURE__ */ React.createElement("div", { className: "mb-5" }, /* @__PURE__ */ React.createElement("label", { className: "block text-xs font-bold text-gray-600 mb-1.5" }, "请输入 ", /* @__PURE__ */ React.createElement("span", { className: "font-mono text-red-600" }, dialog.requireText), " 以确认"), /* @__PURE__ */ React.createElement(
        "input",
        {
          value: typed,
          onChange: (e) => setTyped(e.target.value),
          autoFocus: true,
          className: "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-red-400"
        }
      )), isPrompt && !needsText && /* @__PURE__ */ React.createElement("div", { className: "mb-5" }, dialog.promptLabel && /* @__PURE__ */ React.createElement("label", { className: "block text-xs font-bold text-gray-600 mb-1.5" }, dialog.promptLabel), /* @__PURE__ */ React.createElement(
        "input",
        {
          value: typed,
          onChange: (e) => setTyped(e.target.value),
          autoFocus: true,
          placeholder: dialog.promptPlaceholder || "",
          onKeyDown: (e) => {
            if (e.key === "Enter" && ready) {
              dialog.onConfirm(typed);
              onClose();
            }
          },
          className: "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400"
        }
      )), /* @__PURE__ */ React.createElement("div", { className: "flex gap-3" }, !dialog.acknowledge && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: onClose,
          className: "flex-1 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm"
        },
        "取消"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            if (!ready) return;
            if (dialog.onConfirm) dialog.onConfirm(isPrompt ? typed : void 0);
            onClose();
          },
          disabled: !ready,
          className: `flex-1 py-3 font-bold rounded-xl text-sm text-white ${dialog.danger ? "bg-red-600 active:bg-red-700" : "bg-indigo-600 active:bg-indigo-700"} ${ready ? "" : "opacity-40 cursor-not-allowed"}`
        },
        confirmLabel
      )))
    );
  }
  function StudentPicker({ students, value, onChange, placeholder = "-- 选择学员 --", showBal = true }) {
    const [q, setQ] = useState8("");
    const [open, setOpen] = useState8(false);
    const ref = useRef2(null);
    const sel = students.find((s) => s.id === value);
    useEffect8(() => {
      if (!value) setQ("");
    }, [value]);
    const filtered = useMemo5(
      () => q ? students.filter((s) => s.name.toLowerCase().includes(q.toLowerCase())) : students,
      [students, q]
    );
    useEffect8(() => {
      const h = (e) => {
        if (ref.current && !ref.current.contains(e.target)) setOpen(false);
      };
      document.addEventListener("mousedown", h);
      document.addEventListener("touchstart", h, { passive: true });
      return () => {
        document.removeEventListener("mousedown", h);
        document.removeEventListener("touchstart", h);
      };
    }, []);
    return /* @__PURE__ */ React.createElement("div", { ref, className: "relative" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center border border-gray-300 rounded-xl bg-white focus-within:ring-2 focus-within:ring-indigo-500 overflow-hidden" }, /* @__PURE__ */ React.createElement("span", { className: "pl-3 text-gray-400 flex-shrink-0" }, /* @__PURE__ */ React.createElement(Icon, { name: "search" })), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        placeholder: sel ? sel.name : placeholder,
        value: open ? q : sel ? sel.name : "",
        onFocus: () => {
          setQ("");
          setOpen(true);
        },
        onChange: (e) => {
          setQ(e.target.value);
          setOpen(true);
        },
        className: "flex-1 px-2 py-3 outline-none bg-transparent"
      }
    ), sel && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => {
          onChange(null);
          setQ("");
        },
        "aria-label": "清除选择",
        className: "pr-3 text-gray-400 active:text-gray-700 text-xl leading-none py-3 px-2"
      },
      "×"
    )), open && /* @__PURE__ */ React.createElement("div", { className: "absolute z-50 w-full mt-1 bg-white border border-gray-200 rounded-xl shadow-2xl max-h-52 overflow-y-auto sl" }, !filtered.length ? /* @__PURE__ */ React.createElement("div", { className: "p-4 text-center text-gray-400 text-sm" }, "无匹配") : filtered.map((s) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: s.id,
        type: "button",
        onClick: () => {
          onChange(s.id);
          setQ(s.name);
          setOpen(false);
        },
        className: `w-full text-left px-4 py-3 active:bg-indigo-50 text-sm flex justify-between items-center min-h-[44px] ${s.id === value ? "bg-indigo-50" : "hover:bg-indigo-50"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "font-medium truncate pr-2" }, s.name),
      showBal && /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance })
    ))));
  }
  function mediaSrc(value, fallbackBase = "photos") {
    const raw = String(value || "").trim();
    if (!raw) return "";
    if (raw.startsWith("media:")) {
      const id = raw.slice(6);
      const slug = window.STUDIOSAAS_TENANT_SLUG || new URLSearchParams(location.search).get("tenant") || "";
      return `/s/${encodeURIComponent(slug)}/v1/media/${encodeURIComponent(id)}`;
    }
    return `/${fallbackBase}/${encodeURIComponent(raw)}`;
  }
  function portfolioImgSrc(studentId, item) {
    if (item?.mediaUrl) return item.mediaUrl;
    const filename = item?.filename || "";
    if (String(filename).startsWith("media:")) return mediaSrc(filename, "portfolio");
    return `/portfolio/img/${encodeURIComponent(studentId)}/${encodeURIComponent(filename)}`;
  }
  function portfolioThumbSrc(studentId, item) {
    const src = portfolioImgSrc(studentId, item);
    if (src.includes("/v1/media/")) return mediaVariantSrc(src, "thumb");
    return src;
  }
  function mediaVariantSrc(src, variant) {
    const url = new URL(src, window.location.origin);
    url.searchParams.delete("thumb");
    url.searchParams.set("variant", variant);
    return `${url.pathname}${url.search}${url.hash}`;
  }
  function portfolioSrcSet(studentId, item) {
    const src = portfolioImgSrc(studentId, item);
    if (!src.includes("/v1/media/")) return void 0;
    return `${mediaVariantSrc(src, "thumb")} 360w, ${mediaVariantSrc(src, "medium")} 960w, ${mediaVariantSrc(src, "display")} 2000w`;
  }
  function PhotoAvatar({ photo, name, size = "sm" }) {
    const cls = size === "sm" ? "w-9 h-9 text-xs" : size === "md" ? "w-14 h-14 text-base" : "w-20 h-20 text-2xl";
    const initials = (name || "?").trim().split(/\s+/).map((w) => w[0] || "").slice(0, 2).join("").toUpperCase() || "?";
    if (photo) return /* @__PURE__ */ React.createElement("img", { src: mediaSrc(photo), className: `${cls} rounded-full object-cover flex-shrink-0 border-2 border-white shadow-sm`, alt: name });
    return /* @__PURE__ */ React.createElement("div", { className: `${cls} rounded-full bg-indigo-100 flex items-center justify-center text-indigo-600 font-bold flex-shrink-0 border-2 border-white shadow-sm` }, initials);
  }
  var ICON_PATHS = {
    dashboard: "M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z",
    calendar: "M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5",
    users: "M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z",
    clipboard: "M9 12h3.75M9 15h3.75M9 18h3.75m3 .75H18a2.25 2.25 0 002.25-2.25V6.108c0-1.135-.845-2.098-1.976-2.192a48.424 48.424 0 00-1.123-.08m-5.801 0c-.065.21-.1.433-.1.664 0 .414.336.75.75.75h4.5a.75.75 0 00.75-.75 2.25 2.25 0 00-.1-.664m-5.8 0A2.251 2.251 0 0113.5 2.25H15c1.012 0 1.867.668 2.15 1.586m-5.8 0c-.376.023-.75.05-1.124.08C9.095 4.01 8.25 4.973 8.25 6.108V8.25m0 0H4.875c-.621 0-1.125.504-1.125 1.125v11.25c0 .621.504 1.125 1.125 1.125h9.75c.621 0 1.125-.504 1.125-1.125V9.375c0-.621-.504-1.125-1.125-1.125H8.25z",
    money: "M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
    scroll: "M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z",
    trend: "M2.25 18L9 11.25l4.306 4.306A11.95 11.95 0 0119.8 10.6M21.75 6.75h-4.5m4.5 0v4.5",
    search: "M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z",
    phone: "M2.25 6.75c0 8.284 6.716 15 15 15h2.25a2.25 2.25 0 002.25-2.25v-1.372c0-.516-.351-.966-.852-1.091l-4.423-1.106c-.44-.11-.902.055-1.173.417l-.97 1.293c-.282.376-.769.542-1.21.38a12.035 12.035 0 01-7.143-7.143c-.162-.441.004-.928.38-1.21l1.293-.97c.363-.271.527-.734.417-1.173L6.963 3.102a1.125 1.125 0 00-1.091-.852H4.5A2.25 2.25 0 002.25 4.5v2.25z",
    mail: "M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75",
    image: "M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909m-18 3.75h16.5a1.5 1.5 0 001.5-1.5V6a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 6v12a1.5 1.5 0 001.5 1.5zm10.5-11.25h.008v.008h-.008V8.25zm.375 0a.375.375 0 11-.75 0 .375.375 0 01.75 0z",
    upload: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 7.5 7.5 12M12 7.5v12",
    palette: "M4.098 19.902a3.75 3.75 0 005.304 0l6.401-6.402M6.75 21A3.75 3.75 0 013 17.25V4.125C3 3.504 3.504 3 4.125 3h5.25c.621 0 1.125.504 1.125 1.125v4.072M6.75 21a3.75 3.75 0 003.75-3.75V8.197M6.75 21h13.125c.621 0 1.125-.504 1.125-1.125v-5.25c0-.621-.504-1.125-1.125-1.125h-4.072M10.5 8.197l2.88-2.88c.438-.439 1.15-.439 1.59 0l3.712 3.713c.44.44.44 1.152 0 1.59l-2.879 2.88M6.75 17.25h.008v.008H6.75v-.008z",
    refresh: "M16.023 9.348h4.992V4.356m-4.993 4.992l3.181-3.183a8.25 8.25 0 00-11.667 0L3.75 9.348m0 0V4.356m0 4.992h4.992m-4.993 5.304h4.993v4.992m-4.992-4.992l3.18 3.183a8.25 8.25 0 0011.668 0l3.182-3.183m0 0h-4.99m4.99 0v4.992",
    chevronLeft: "M15.75 19.5L8.25 12l7.5-7.5",
    chevronRight: "M8.25 4.5l7.5 7.5-7.5 7.5",
    download: "M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5 12 4.5",
    warning: "M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-2.98-1.5-3.846 0L2.697 16.126zM12 15.75h.008v.008H12v-.008z",
    check: "M4.5 12.75l6 6 9-13.5",
    bolt: "M3.75 13.5l10.5-11.25L12 10.5h7.5L9 21.75 12 13.5H3.75z",
    clock: "M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z",
    cake: "M12 8.25v-1.5m0 1.5c-1.355 0-2.697.056-4.024.166C6.845 8.51 6 9.473 6 10.608v2.513m6-4.871c1.355 0 2.697.056 4.024.166C17.155 8.51 18 9.473 18 10.608v2.513M15 8.25v-1.5m-6 1.5v-1.5m12 9.75l-1.5.75a3.354 3.354 0 01-3 0 3.354 3.354 0 00-3 0 3.354 3.354 0 01-3 0 3.354 3.354 0 00-3 0 3.354 3.354 0 01-3 0L3 16.5m15-3.379a48.474 48.474 0 00-6-.371c-2.032 0-4.034.126-6 .371m12 0c.39.049.777.102 1.163.16 1.07.16 1.837 1.094 1.837 2.175v5.169c0 .621-.504 1.125-1.125 1.125H4.125A1.125 1.125 0 013 20.625v-5.169c0-1.081.768-2.015 1.837-2.175A48.111 48.111 0 016 13.121",
    chat: "M20.25 8.511c.884.284 1.5 1.128 1.5 2.097v4.286c0 1.136-.847 2.1-1.98 2.193-.34.027-.68.052-1.02.072v3.091l-3-3c-1.354 0-2.694-.055-4.02-.163a2.115 2.115 0 01-.825-.242m9.345-8.334a2.126 2.126 0 00-.476-.095 48.64 48.64 0 00-8.048 0c-1.131.094-1.976 1.057-1.976 2.192v4.286c0 .837.46 1.58 1.155 1.951m9.345-8.334V6.637c0-1.621-1.152-3.026-2.76-3.235A48.455 48.455 0 0011.25 3c-2.115 0-4.198.137-6.24.402-1.608.209-2.76 1.614-2.76 3.235v6.226c0 1.621 1.152 3.026 2.76 3.235.577.075 1.157.14 1.74.194V21l4.155-4.155",
    pencil: "M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10",
    printer: "M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5z",
    heart: "M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z",
    lock: "M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z",
    logout: "M15.75 9V5.25A2.25 2.25 0 0013.5 3h-6a2.25 2.25 0 00-2.25 2.25v13.5A2.25 2.25 0 007.5 21h6a2.25 2.25 0 002.25-2.25V15M12 9l-3 3m0 0l3 3m-3-3h12.75",
    cog: "M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.324.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 011.37.49l1.296 2.247a1.125 1.125 0 01-.26 1.431l-1.003.827c-.293.24-.438.613-.431.992a6.759 6.759 0 010 .255c-.007.378.138.75.43.99l1.005.828c.424.35.534.954.26 1.43l-1.298 2.247a1.125 1.125 0 01-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.57 6.57 0 01-.22.128c-.331.183-.581.495-.644.869l-.213 1.28c-.09.543-.56.941-1.11.941h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 01-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 01-1.369-.49l-1.297-2.247a1.125 1.125 0 01.26-1.431l1.004-.827c.292-.24.437-.613.43-.992a6.932 6.932 0 010-.255c.007-.378-.138-.75-.43-.99l-1.004-.828a1.125 1.125 0 01-.26-1.43l1.297-2.247a1.125 1.125 0 011.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.087.22-.128.332-.183.582-.495.644-.869l.214-1.281zM15 12a3 3 0 11-6 0 3 3 0 016 0z",
    stethoscope: "M4.5 3.75v5.25a5.25 5.25 0 0010.5 0V3.75M6.75 3.75h-2.25m8.25 0h2.25M9.75 14.25v1.5a4.5 4.5 0 009 0v-2.25m0 0a1.5 1.5 0 100-3 1.5 1.5 0 000 3z",
    device: "M10.5 1.5H8.25A2.25 2.25 0 006 3.75v16.5a2.25 2.25 0 002.25 2.25h7.5A2.25 2.25 0 0018 20.25V3.75a2.25 2.25 0 00-2.25-2.25H13.5m-3 0V3h3V1.5m-3 0h3m-3 18.75h3",
    recycle: "M16.023 9.348h4.992V4.356m-4.993 4.992l3.181-3.183a8.25 8.25 0 00-11.667 0L3.75 9.348m0 0V4.356m0 4.992h4.992m-4.993 5.304h4.993v4.992m-4.992-4.992l3.18 3.183a8.25 8.25 0 0011.668 0l3.182-3.183m0 0h-4.99m4.99 0v4.992",
    shield: "M9 12.75L11.25 15 15 9.75m-3-7.036A11.959 11.959 0 013.598 6 11.99 11.99 0 003 9.749c0 5.592 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.31-.21-2.571-.598-3.751h-.152c-3.196 0-6.1-1.248-8.25-3.285z",
    trash: "M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0",
    save: "M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z",
    camera: "M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316zM16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z",
    folder: "M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z",
    bell: "M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0",
    broom: "M9.53 16.122a3 3 0 00-5.78 1.128 2.25 2.25 0 01-2.4 2.245 4.5 4.5 0 008.4-2.245c0-.399-.078-.78-.22-1.128zm0 0a15.998 15.998 0 003.388-1.62m-5.043-.025a15.994 15.994 0 011.622-3.395m3.42 3.42a15.995 15.995 0 004.764-4.648l3.876-5.814a1.151 1.151 0 00-1.597-1.597L14.146 6.32a15.996 15.996 0 00-4.649 4.763m3.42 3.42a6.776 6.776 0 00-3.42-3.42",
    star: "M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z",
    card: "M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-3.75 3h15a2.25 2.25 0 002.25-2.25V6.75A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25v10.5A2.25 2.25 0 004.5 19.5z",
    target: "M12 21a9 9 0 100-18 9 9 0 000 18zm0-3a6 6 0 100-12 6 6 0 000 12zm0-3a3 3 0 100-6 3 3 0 000 6z",
    note: "M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L6.832 19.82a4.5 4.5 0 01-1.897 1.13l-2.685.8.8-2.685a4.5 4.5 0 011.13-1.897L16.863 4.487zm0 0L19.5 7.125",
    archiveBox: "M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z",
    restore: "M9 15L3 9m0 0l6-6M3 9h12a6 6 0 010 12h-3",
    plus: "M12 4.5v15m7.5-7.5h-15",
    close: "M6 18L18 6M6 6l12 12",
    ellipsis: "M6.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM12.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0zM18.75 12a.75.75 0 11-1.5 0 .75.75 0 011.5 0z",
    inbox: "M2.25 13.5h3.86a2.25 2.25 0 012.012 1.244l.256.512a2.25 2.25 0 002.013 1.244h3.218a2.25 2.25 0 002.013-1.244l.256-.512a2.25 2.25 0 012.013-1.244h3.859m-19.5.338V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18v-4.162c0-.224-.034-.447-.1-.661L19.24 5.338a2.25 2.25 0 00-2.15-1.588H6.911a2.25 2.25 0 00-2.15 1.588L2.35 13.177a2.25 2.25 0 00-.1.661z"
  };
  function Icon({ name, className = "w-5 h-5" }) {
    const path = ICON_PATHS[name];
    if (!path) return null;
    return /* @__PURE__ */ React.createElement(
      "svg",
      {
        className: `${className} flex-shrink-0`,
        viewBox: "0 0 24 24",
        fill: "none",
        stroke: "currentColor",
        strokeWidth: "1.6",
        strokeLinecap: "round",
        strokeLinejoin: "round",
        "aria-hidden": "true",
        focusable: "false"
      },
      /* @__PURE__ */ React.createElement("path", { d: path })
    );
  }
  function PhotoUploader({ value, onChange, notify }) {
    const [uploading, setUploading] = useState8(false);
    const handleFile = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      if (file.size > 5 * 1024 * 1024) {
        notify("照片不能超过 5MB", { danger: true });
        return;
      }
      setUploading(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/media/upload`, {
          method: "POST",
          credentials: "include",
          headers: { "X-Requested-With": "StudioSaaS" },
          body: fd
        });
        const d = await r.json();
        if (d.filename) onChange(d.filename);
      } catch {
        notify("上传失败，请重试", { danger: true });
      } finally {
        setUploading(false);
        e.target.value = "";
      }
    };
    const btnBase = uploading ? "bg-gray-100 text-gray-400 border-gray-200 cursor-not-allowed" : "";
    return /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-4" }, value ? /* @__PURE__ */ React.createElement("img", { src: mediaSrc(value), alt: "学员照片预览", className: "w-14 h-14 rounded-full object-cover border-2 border-indigo-100 flex-shrink-0" }) : /* @__PURE__ */ React.createElement("div", { className: "w-14 h-14 rounded-full bg-gray-100 flex items-center justify-center text-2xl border-2 border-dashed border-gray-300 flex-shrink-0 text-gray-400" }, /* @__PURE__ */ React.createElement(Icon, { name: "camera", className: "w-6 h-6" })), /* @__PURE__ */ React.createElement("div", { className: "space-y-1.5" }, /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("label", { className: `cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[44px] ${btnBase || "bg-indigo-50 text-indigo-700 border-indigo-200 active:bg-indigo-100"}` }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "folder", className: "w-4 h-4" }), uploading ? "上传中..." : value ? "更换" : "选择"), /* @__PURE__ */ React.createElement("input", { type: "file", accept: "image/*", onChange: handleFile, disabled: uploading, className: "hidden" })), /* @__PURE__ */ React.createElement("label", { className: `cursor-pointer inline-flex items-center gap-1.5 px-3 py-2 text-sm font-bold rounded-xl border min-h-[44px] ${btnBase || "bg-purple-50 text-purple-700 border-purple-200 active:bg-purple-100"}` }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "camera", className: "w-4 h-4" }), "拍照"), /* @__PURE__ */ React.createElement("input", { type: "file", accept: "image/*", capture: "environment", onChange: handleFile, disabled: uploading, className: "hidden" }))), value && /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => onChange(""), className: "text-xs text-red-400 active:text-red-600" }, "移除照片")));
  }
  function StudentTimeline({ api, studentId, openInvoice }) {
    const [state, setState] = useState8({ loading: false, data: null, error: null });
    const KIND = {
      registration: ["clipboard", "报名"],
      approval: ["check", "批准建档"],
      topup: ["card", "充值"],
      refund: ["card", "退款"],
      deduction: ["calendar", "扣课"],
      invoice: ["money", "发票"],
      payment: ["money", "收款"],
      credit_note: ["money", "贷记"],
      report: ["star", "成长报告"]
    };
    const load = async () => {
      setState((s) => ({ ...s, loading: true, error: null }));
      try {
        const d = await api(`/students/${encodeURIComponent(studentId)}/timeline?limit=50`);
        setState({ loading: false, data: d, error: null });
      } catch (e) {
        setState({ loading: false, data: null, error: e.message });
      }
    };
    return /* @__PURE__ */ React.createElement(
      "details",
      {
        className: "border border-gray-200 rounded-2xl overflow-hidden",
        onToggle: (e) => {
          if (e.currentTarget.open && !state.data && !state.loading) load();
        }
      },
      /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Icon, { name: "clock", className: "w-4 h-4" }), "学员时间线", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400 text-xs" }, "报名 · 课时 · 账务 · 报告，一条流水")),
      /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, state.loading && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-3 text-xs text-gray-400" }, "加载中…"), state.error && /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 text-xs text-red-500 flex items-center gap-3" }, /* @__PURE__ */ React.createElement("span", null, "时间线加载失败：", state.error), /* @__PURE__ */ React.createElement("button", { onClick: load, className: "min-h-[44px] px-2.5 rounded-lg border border-red-200 font-bold" }, "重试")), state.data && (state.data.entries || []).length === 0 && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-3 text-xs text-gray-400" }, "还没有可显示的记录。"), state.data && (state.data.entries || []).map((entry, i) => {
        const [icon, label] = KIND[entry.kind] || ["info", entry.kind];
        return /* @__PURE__ */ React.createElement("div", { key: i, className: "px-4 py-2.5 flex items-baseline gap-2 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5 font-bold text-gray-700 flex-shrink-0" }, /* @__PURE__ */ React.createElement(Icon, { name: icon, className: "w-3.5 h-3.5 text-gray-400" }), label), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-600 truncate" }, entry.title), Number.isFinite(entry.credits) && entry.credits !== null && entry.credits !== 0 && /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold ${entry.credits > 0 ? "text-indigo-700" : "text-gray-500"}` }, entry.credits > 0 ? `+${entry.credits}` : entry.credits, " 课时"), Number.isFinite(entry.amountCents) && entry.amountCents !== null && entry.amountCents !== 0 && /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold text-emerald-700" }, "$", (entry.amountCents / 100).toFixed(2)), entry.invoiceId && openInvoice && /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => openInvoice(entry.invoiceId),
            className: "text-xs font-bold text-indigo-600 underline decoration-dotted"
          },
          "查看单据"
        ), /* @__PURE__ */ React.createElement("span", { className: "ml-auto text-xs text-gray-400 tabular-nums flex-shrink-0" }, String(entry.ts).slice(0, 10)));
      }), state.data?.hasMore && /* @__PURE__ */ React.createElement("p", { className: "px-4 py-2 text-[11px] text-gray-400" }, "只显示最近 50 条；更早的记录见充值/上课记录与账单中心。"))
    );
  }
  function MaintSection({ onRestored, renewTh, saveRenewTh, confirm: confirm2, notify }) {
    const [hc, setHc] = useState8(null);
    const [hcBusy, setHcBusy] = useState8(false);
    const [cfg, setCfg] = useState8(null);
    const [pw, setPw] = useState8("");
    const [cfgMsg, setCfgMsg] = useState8(null);
    const say = (text, tone = "info") => setCfgMsg(text ? { text, tone } : null);
    const [bks, setBks] = useState8(null);
    const [bkSel, setBkSel] = useState8(null);
    const [busy, setBusy] = useState8(false);
    const post = (url, body) => fetch(url, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    const [stale, setStale] = useState8(false);
    useEffect8(() => {
      fetch("/api/config", { credentials: "include" }).then((r) => {
        if (r.status === 404) {
          setStale(true);
          return null;
        }
        return r.json();
      }).then((d) => {
        if (d) setCfg(d);
      }).catch(() => {
      });
    }, []);
    const runHC = async () => {
      setHcBusy(true);
      try {
        const r = await fetch("/api/healthcheck", { credentials: "include" });
        if (r.status === 404) {
          setStale(true);
          setHc(null);
          return;
        }
        setHc(await r.json());
      } catch {
        setHc({ error: "连接失败" });
      } finally {
        setHcBusy(false);
      }
    };
    const saveCfg = async () => {
      if (!cfg) return;
      setBusy(true);
      say("");
      try {
        const body = {
          email_to: cfg.email_to,
          smtp_user: cfg.smtp_user,
          smtp_host: cfg.smtp_host,
          smtp_port: cfg.smtp_port,
          weekly_enabled: cfg.weekly_enabled,
          renew_threshold: renewTh
        };
        if (pw) body.smtp_password = pw;
        const r = await post("/api/config", body);
        if (r.status === 404) {
          setStale(true);
          say("");
          return;
        }
        say(r.ok ? "已保存" : `保存失败 (HTTP ${r.status})`, r.ok ? "ok" : "error");
        if (r.ok && pw) {
          setPw("");
          setCfg((c) => ({ ...c, hasPassword: true }));
        }
      } catch {
        say("连接失败", "error");
      } finally {
        setBusy(false);
      }
    };
    const testEmail = async () => {
      setBusy(true);
      say("发送中…（请先点过「保存配置」）");
      try {
        const r = await post("/api/email-test", {});
        const d = await r.json();
        say(d.ok ? "测试邮件已发出，请查收（含每周汇总预览）" : d.error || "发送失败", d.ok ? "ok" : "error");
      } catch {
        say("连接失败", "error");
      } finally {
        setBusy(false);
      }
    };
    const loadBks = async () => {
      try {
        const r = await fetch("/api/backups", { credentials: "include" });
        const d = await r.json();
        if (Array.isArray(d) && d.length && typeof d[0] === "string") {
          setStale(true);
          setBks([]);
          return;
        }
        setBks(Array.isArray(d) ? d : []);
      } catch {
        setBks([]);
      }
    };
    const clearPwaCache = async () => {
      try {
        if ("serviceWorker" in navigator) {
          const regs = await navigator.serviceWorker.getRegistrations();
          regs.forEach((r) => r.active && r.active.postMessage({ type: "CLEAR_LPCMS_CACHE" }));
        }
        if ("caches" in window) {
          const keys = await caches.keys();
          await Promise.all(keys.filter((k) => k.startsWith("lpcms-")).map((k) => caches.delete(k)));
        }
        notify("PWA 缓存已清理，页面将刷新。若主屏幕 App 图标仍未更新，请删除后重新添加。", { onConfirm: () => window.location.reload() });
      } catch (e) {
        notify("缓存清理失败，请关闭 App 后重新打开。", { danger: true });
      }
    };
    const pickBk = async (name) => {
      try {
        const r = await fetch(`/api/backups/${name}/summary`, { credentials: "include" });
        setBkSel({ name, ...await r.json() });
      } catch {
      }
    };
    const runRestore = async () => {
      setBusy(true);
      try {
        const r = await post("/api/restore", { filename: bkSel.name });
        const d = await r.json();
        if (d.ok) {
          notify(`恢复完成：${d.students} 名学员 / ${d.logs} 条日志。页面即将刷新数据。`, { onConfirm: onRestored });
        } else notify(d.error || "恢复失败", { danger: true });
      } catch {
        notify("连接失败", { danger: true });
      } finally {
        setBusy(false);
      }
    };
    const doRestore = () => {
      if (!bkSel || !bkSel.valid) return;
      confirm2(
        `该备份：${bkSel.students} 名学员 / ${bkSel.logs} 条日志
与当前相比：学员 ${bkSel.diffStudents >= 0 ? "+" : ""}${bkSel.diffStudents} / 日志 ${bkSel.diffLogs >= 0 ? "+" : ""}${bkSel.diffLogs}

当前数据会先自动另存为 pre_restore 备份（可再恢复回来），然后被该备份覆盖。`,
        runRestore,
        { title: `恢复备份 ${bkSel.name}`, danger: true, requireText: bkSel.name, confirmText: "覆盖当前数据" }
      );
    };
    const inp = "w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm focus:ring-2 focus:ring-indigo-400";
    if (stale) return /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "bg-red-50 border border-red-300 rounded-xl p-3 space-y-1.5" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-red-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-4 h-4" }), "服务器还在运行旧版本"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600" }, "界面已是新版，但数据体检 / 邮件 / 备份恢复需要新版 server.py 支持。请："), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600 font-mono bg-red-100 rounded-lg px-2 py-1.5" }, "1. 用新版 server.py 覆盖 CMS 目录里的旧文件", /* @__PURE__ */ React.createElement("br", null), "2. 终端运行 ./cms.sh restart", /* @__PURE__ */ React.createElement("br", null), "3. 刷新本页面"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-500" }, "验证方法：浏览器打开 /api/ping，version 应为 7.3.1")));
    return /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide" }, /* @__PURE__ */ React.createElement(Icon, { name: "stethoscope", className: "w-4 h-4" }), "数据体检"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: runHC,
        disabled: hcBusy,
        className: "w-full bg-teal-50 active:bg-teal-100 disabled:opacity-50 text-teal-700 border border-teal-200 py-2.5 rounded-xl font-bold text-sm"
      },
      hcBusy ? "体检中…" : "运行数据体检"
    ), hc && !hc.error && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-200 rounded-xl p-3 space-y-1 text-xs text-gray-600" }, /* @__PURE__ */ React.createElement("p", null, "学员 ", hc.students, "（活跃 ", hc.activeStudents, "）· 日志 ", hc.logs, " 条 · 库 ", hc.dbSizeKB, " KB"), /* @__PURE__ */ React.createElement("p", { className: hc.mismatchCount ? "text-amber-600 font-bold" : "text-green-600" }, "账目核对: ", hc.mismatchCount ? `${hc.mismatchCount} 人不一致` : "全部一致 ✓"), (hc.mismatches || []).slice(0, 8).map((m, i) => /* @__PURE__ */ React.createElement("p", { key: i, className: "pl-2 text-amber-700" }, "· ", m.name, ": 余额 ", m.balance, "，日志合计 ", m.logsSum, "（差 ", m.diff > 0 ? "+" : "", m.diff, "）")), hc.duplicateNames.length > 0 && /* @__PURE__ */ React.createElement("p", { className: "text-amber-600" }, "重名学员: ", hc.duplicateNames.join("、")), hc.missingPhotos.length > 0 && /* @__PURE__ */ React.createElement("p", { className: "text-amber-600" }, "照片文件丢失: ", hc.missingPhotos.length, " 人"), hc.conflictCopies.length > 0 && /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-red-600 font-bold" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-4 h-4" }), "iCloud 冲突副本: ", hc.conflictCopies.join("、")), /* @__PURE__ */ React.createElement("p", null, "待审申请 ", hc.pendingCount, " 条 · 最近备份 ", hc.lastBackup || "无", "（", hc.backupCount, " 份）")), hc && hc.error && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-500" }, "体检失败，请重试")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide" }, /* @__PURE__ */ React.createElement(Icon, { name: "bolt", className: "w-4 h-4" }), "待续课提醒阈值（剩余 ≤N 节）"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, [1, 2, 3, 5].map((d) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: d,
        onClick: () => {
          saveRenewTh(d);
          post("/api/config", { renew_threshold: d }).catch(() => {
          });
        },
        className: `flex-1 py-2 rounded-xl text-xs font-bold border ${renewTh === d ? "bg-indigo-600 text-white border-indigo-600" : "bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100"}`
      },
      d,
      " 节"
    ))), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "影响学员页「低余额」筛选和每周邮件中的待续课名单")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide" }, /* @__PURE__ */ React.createElement(Icon, { name: "device", className: "w-4 h-4" }), "主屏幕 App / PWA 缓存"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: clearPwaCache,
        className: "w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm"
      },
      "清理 PWA 缓存并刷新"
    ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "用于更新主屏幕图标、Service Worker 或修复旧页面缓存。")), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide" }, /* @__PURE__ */ React.createElement(Icon, { name: "mail", className: "w-4 h-4" }), "每周汇总邮件（周一 10:00）"), !cfg ? /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "加载中…") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { htmlFor: "cfg-email-to", className: "block text-xs font-bold text-gray-500 mb-1" }, "收件邮箱"), /* @__PURE__ */ React.createElement(
      "input",
      {
        id: "cfg-email-to",
        className: inp,
        placeholder: "you@example.com",
        value: cfg.email_to || "",
        onChange: (e) => setCfg({ ...cfg, email_to: e.target.value })
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { htmlFor: "cfg-smtp-user", className: "block text-xs font-bold text-gray-500 mb-1" }, "发件 Gmail 地址"), /* @__PURE__ */ React.createElement(
      "input",
      {
        id: "cfg-smtp-user",
        className: inp,
        placeholder: "studio@gmail.com",
        value: cfg.smtp_user || "",
        onChange: (e) => setCfg({ ...cfg, smtp_user: e.target.value })
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { htmlFor: "cfg-smtp-pass", className: "block text-xs font-bold text-gray-500 mb-1" }, "Gmail 应用专用密码"), /* @__PURE__ */ React.createElement(
      "input",
      {
        id: "cfg-smtp-pass",
        className: inp,
        type: "password",
        value: pw,
        onChange: (e) => setPw(e.target.value),
        placeholder: cfg.hasPassword ? "已保存，留空不变" : "16 位应用专用密码"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-600" }, "每周一自动发送"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setCfg({ ...cfg, weekly_enabled: !cfg.weekly_enabled }),
        className: `relative inline-flex h-6 w-11 items-center rounded-full transition ${cfg.weekly_enabled ? "bg-indigo-600" : "bg-gray-300"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: `inline-block h-4 w-4 transform rounded-full bg-white transition ${cfg.weekly_enabled ? "translate-x-6" : "translate-x-1"}` })
    )), cfgMsg && /* @__PURE__ */ React.createElement("p", { className: `text-xs font-medium ${cfgMsg.tone === "ok" ? "text-green-600" : cfgMsg.tone === "error" ? "text-red-500" : "text-gray-500"}` }, cfgMsg.text), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: saveCfg,
        disabled: busy,
        className: "flex-1 bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm"
      },
      "保存配置"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: testEmail,
        disabled: busy,
        className: "flex-1 bg-white border border-indigo-300 active:bg-indigo-50 disabled:opacity-50 text-indigo-700 py-2.5 rounded-xl font-bold text-sm"
      },
      "发送测试邮件"
    )), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "需要 Gmail「应用专用密码」，获取方法见《邮件设置教程》文档"))), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 uppercase tracking-wide" }, /* @__PURE__ */ React.createElement(Icon, { name: "recycle", className: "w-4 h-4" }), "备份与恢复"), !bks ? /* @__PURE__ */ React.createElement("button", { onClick: loadBks, className: "w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-2.5 rounded-xl font-bold text-sm" }, "查看备份列表") : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "max-h-44 overflow-y-auto space-y-1 modal-scroll" }, bks.length === 0 && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 text-center py-2" }, "暂无备份"), bks.map((b) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: b.name,
        onClick: () => pickBk(b.name),
        className: `w-full text-left px-3 py-2 rounded-xl border text-xs ${bkSel?.name === b.name ? "border-indigo-400 bg-indigo-50" : "border-gray-200 bg-gray-50 active:bg-gray-100"}`
      },
      /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-700" }, b.mtime),
      /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 ml-2" }, (b.size / 1024).toFixed(0), " KB"),
      b.name.startsWith("pre_restore") && /* @__PURE__ */ React.createElement("span", { className: "ml-1 text-amber-600 font-bold" }, "恢复前存档")
    ))), bkSel && (bkSel.valid ? /* @__PURE__ */ React.createElement("div", { className: "bg-indigo-50 border border-indigo-200 rounded-xl p-3 space-y-1 text-xs text-indigo-800" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold" }, bkSel.students, " 名学员 · ", bkSel.logs, " 条日志"), /* @__PURE__ */ React.createElement("p", null, "与当前相比: 学员 ", bkSel.diffStudents >= 0 ? "+" : "", bkSel.diffStudents, " · 日志 ", bkSel.diffLogs >= 0 ? "+" : "", bkSel.diffLogs), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: doRestore,
        disabled: busy,
        className: "w-full mt-1 bg-red-600 active:bg-red-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm"
      },
      "恢复此备份（双重确认）"
    )) : /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-500" }, "该备份文件已损坏，不可恢复")))));
  }
  function LoginScreen({ onLogin }) {
    const [email, setEmail] = useState8(() => localStorage.getItem(`lp_admin_email_${tenantSlug}`) || "");
    const [pw, setPw] = useState8("");
    const [busy, setBusy] = useState8(false);
    const [err, setErr] = useState8("");
    const submit = async (e) => {
      e && e.preventDefault();
      if (!email || !pw) {
        setErr("请输入管理员邮箱和密码");
        return;
      }
      setBusy(true);
      setErr("");
      try {
        const r = await fetch("/s/" + encodeURIComponent(tenantSlug) + "/v1/auth/legacy-login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password: pw }),
          credentials: "include"
        });
        const d = await r.json();
        if (d.ok) {
          localStorage.setItem(`lp_admin_email_${tenantSlug}`, email);
          onLogin();
        } else {
          setErr(d.message || d.error || "密码错误");
          setPw("");
        }
      } catch {
        setErr("连接失败，请重试");
      } finally {
        setBusy(false);
      }
    };
    return /* @__PURE__ */ React.createElement("div", { className: "min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-900 to-indigo-950 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-3xl p-8 w-full max-w-xs shadow-2xl text-center anim" }, /* @__PURE__ */ React.createElement(TenantBrandLogo, { className: "w-36 max-h-20 object-contain mx-auto mb-3" }), /* @__PURE__ */ React.createElement("p", { className: "tenant-slogan text-sm text-gray-500 italic mb-4" }, "Learn, grow, and feel confident."), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400 mb-6" }, "请输入 Studio CMS 账号"), /* @__PURE__ */ React.createElement("form", { onSubmit: submit, className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "text-left" }, /* @__PURE__ */ React.createElement("label", { htmlFor: "cms-login-email", className: "block text-xs font-bold text-gray-500 mb-1" }, "管理员邮箱"), /* @__PURE__ */ React.createElement(
      "input",
      {
        id: "cms-login-email",
        type: "email",
        placeholder: "you@example.com",
        value: email,
        onChange: (e) => setEmail(e.target.value),
        autoFocus: true,
        className: "w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-sm focus:ring-2 focus:ring-indigo-500"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "text-left" }, /* @__PURE__ */ React.createElement("label", { htmlFor: "cms-login-password", className: "block text-xs font-bold text-gray-500 mb-1" }, "密码"), /* @__PURE__ */ React.createElement(
      "input",
      {
        id: "cms-login-password",
        type: "password",
        value: pw,
        onChange: (e) => setPw(e.target.value),
        className: "w-full p-3 border border-gray-300 rounded-xl outline-none text-center text-lg tracking-widest focus:ring-2 focus:ring-indigo-500"
      }
    )), err && /* @__PURE__ */ React.createElement("p", { className: "text-red-500 text-xs font-medium" }, err), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "submit",
        disabled: busy || !email || !pw,
        className: "w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-3 rounded-xl font-bold text-sm"
      },
      busy ? "验证中..." : "进入系统 →"
    )), /* @__PURE__ */ React.createElement("p", { className: "mt-6 pt-4 border-t border-gray-100 text-[10px] tracking-wide text-gray-400" }, "Powered by Paradise Production")));
  }

  // legacy-root/src/panels/dashboard.jsx
  function DashboardSection(props) {
    const {
      activityMap,
      actorRole,
      actorRoleLabel,
      allowedTabs,
      analytics,
      arSummary,
      bizStats,
      canViewFinancialAnalytics,
      canWriteAttendance,
      canWriteCredits,
      canWriteStudents,
      copyText,
      db,
      inactiveDays,
      loadSchedules,
      pendingCount,
      scheduleLoadError,
      setFilterBy,
      setGOpen,
      setGQ,
      setRDate,
      setSortBy,
      setSrch,
      setTab,
      setTuStu,
      showToast,
      todayCheckedCount,
      todayEffectiveCount,
      renderMessage
    } = props;
    const birthdayWish = (name) => renderMessage(
      "birthday",
      "{student} 您好！{studio} 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、收获满满～",
      { student: name }
    );
    return /* @__PURE__ */ React.createElement("div", { className: "cms-dashboard-root anim space-y-5" }, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "dashboard", className: "w-4 h-4" }), "工作台"), (() => {
      const actionsByRole = {
        owner: [["pending", "处理待处理", pendingCount, "clipboard"], ["roster", "查看今日课程", todayEffectiveCount, "calendar"], ["students", "搜索学员", analytics.totalStudents, "users"], ["stats", "查看经营统计", null, "trend"]],
        platform_super_admin: [["pending", "处理待处理", pendingCount, "clipboard"], ["roster", "查看今日课程", todayEffectiveCount, "calendar"], ["students", "搜索学员", analytics.totalStudents, "users"], ["stats", "查看经营统计", null, "trend"]],
        super_admin: [["pending", "处理待处理", pendingCount, "clipboard"], ["roster", "查看今日课程", todayEffectiveCount, "calendar"], ["students", "搜索学员", analytics.totalStudents, "users"], ["stats", "查看经营统计", null, "trend"]],
        manager: [["pending", "处理待处理", pendingCount, "clipboard"], ["roster", "查看今日课程", todayEffectiveCount, "calendar"], ["topup", "充值与退款", null, "money"], ["stats", "查看经营统计", null, "trend"]],
        teacher: [["roster", "今日课程名单", todayEffectiveCount, "calendar"], ["students", "查找学员", analytics.totalStudents, "users"], ["works", "上传作品", null, "image"], ["logs", "查看操作记录", null, "scroll"]],
        front_desk: [["pending", "处理报名与约课", pendingCount, "clipboard"], ["roster", "查看今日课程", todayEffectiveCount, "calendar"], ["new_student", "新建学员", null, "plus"], ["topup", "充值与退款", null, "money"]],
        staff: [["pending", "处理待处理", pendingCount, "clipboard"], ["roster", "查看今日课程", todayEffectiveCount, "calendar"], ["students", "查找学员", analytics.totalStudents, "users"], ["works", "管理作品", null, "image"]]
      };
      const actions = (actionsByRole[actorRole] || actionsByRole.staff).filter(([key]) => allowedTabs.includes(key));
      return /* @__PURE__ */ React.createElement("section", { className: "rounded-2xl border border-indigo-100 bg-white p-4 shadow-sm", "aria-labelledby": "role-workbench-title" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", { id: "role-workbench-title", className: "text-sm font-bold text-gray-900" }, "今日重点"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "按你的角色排列最常用的工作入口")), /* @__PURE__ */ React.createElement("span", { className: "text-[11px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-100 rounded-full px-2.5 py-1" }, actorRoleLabel)), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 lg:grid-cols-4 gap-2" }, actions.slice(0, 4).map(([key, label, count, icon]) => /* @__PURE__ */ React.createElement("button", { key, type: "button", onClick: () => setTab(key), className: "min-h-[62px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left hover:border-indigo-300 hover:bg-indigo-50" }, /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-1.5 text-xs font-bold text-gray-700" }, /* @__PURE__ */ React.createElement(Icon, { name: icon, className: "w-4 h-4 text-indigo-600" }), label), count !== null && /* @__PURE__ */ React.createElement("span", { className: "block text-lg font-bold text-indigo-700 mt-1 tabular-nums" }, count)))));
    })(), actorRole === "teacher" && /* @__PURE__ */ React.createElement("div", { className: "md:hidden rounded-2xl border border-emerald-200 bg-emerald-50 p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-emerald-900 mb-2" }, "教师手机快捷流程 · 3 步完成今日工作"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-3 gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setRDate(todayISO());
          setTab("roster");
        },
        className: "min-h-[56px] rounded-xl bg-white border border-emerald-200 px-2 py-2 text-[11px] font-bold text-emerald-900"
      },
      "1 · 今日名单"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setGOpen(true);
          setGQ("");
        },
        className: "min-h-[56px] rounded-xl bg-white border border-emerald-200 px-2 py-2 text-[11px] font-bold text-emerald-900"
      },
      "2 · 找到学员"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setTab("students");
          showToast("选择学员后，在作品区上传今日作品。");
        },
        className: "min-h-[56px] rounded-xl bg-emerald-700 px-2 py-2 text-[11px] font-bold text-white"
      },
      "3 · 上传作品"
    ))), scheduleLoadError && /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700" }, /* @__PURE__ */ React.createElement("span", { className: "flex-1" }, scheduleLoadError), /* @__PURE__ */ React.createElement("button", { onClick: loadSchedules, className: "rounded-xl border border-red-200 bg-white px-3 py-2 text-xs font-bold min-h-[44px]" }, "重试")), /* @__PURE__ */ React.createElement("div", { className: TENANT_SLUG ? "cms-dashboard-lead" : "" }, TENANT_SLUG && /* @__PURE__ */ React.createElement("div", { className: "cms-command-card bg-gradient-to-br from-indigo-900 to-indigo-700 text-white rounded-2xl p-4 shadow-lg" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-indigo-200 tracking-wider" }, "TODAY · 今日指挥台"), /* @__PURE__ */ React.createElement("p", { className: "font-bold mt-0.5" }, "先处理最需要行动的事项")), /* @__PURE__ */ React.createElement("span", { className: "text-xs bg-white/10 border border-white/20 px-2.5 py-1 rounded-full" }, fmtDate(todayISO()))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-3 gap-2 mb-3" }, [
      ["应到", todayEffectiveCount, "人", () => {
        setRDate(todayISO());
        setTab("roster");
      }],
      ["已签到", todayCheckedCount, "人", () => {
        setRDate(todayISO());
        setTab("roster");
      }],
      ["低课时", analytics.lowBalance.length, "人", () => {
        setSortBy("bal-asc");
        setFilterBy("low");
        setTab("students");
      }]
    ].map(([label, value, unit, go]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: label,
        type: "button",
        onClick: go || void 0,
        disabled: !go,
        className: `rounded-xl bg-white/10 border border-white/10 p-2.5 text-left ${go ? "active:bg-white/20" : ""}`
      },
      /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-indigo-200" }, label, go && /* @__PURE__ */ React.createElement("span", { className: "ml-1" }, "→")),
      /* @__PURE__ */ React.createElement("p", { className: "text-xl font-bold" }, value, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal ml-1" }, unit))
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 sm:grid-cols-4 gap-2" }, canWriteAttendance && /* @__PURE__ */ React.createElement("button", { onClick: () => {
      setRDate(todayISO());
      setTab("roster");
    }, className: "bg-white text-indigo-800 rounded-xl py-2.5 text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "今日排课")), canWriteStudents && /* @__PURE__ */ React.createElement("button", { onClick: () => setTab("new_student"), className: "bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-4 h-4" }), "新建学员")), allowedTabs.includes("pending") && /* @__PURE__ */ React.createElement("button", { onClick: () => setTab("pending"), className: "bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "clipboard", className: "w-4 h-4" }), "审核报名")), canWriteCredits && /* @__PURE__ */ React.createElement("button", { onClick: () => setTab("topup"), className: "bg-indigo-600 border border-indigo-400 rounded-xl py-2.5 text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "money", className: "w-4 h-4" }), "充值结算")))), /* @__PURE__ */ React.createElement("div", { className: "cms-kpi-grid" }, [
      { l: "学员总数", v: `${analytics.totalStudents} 人`, c: "text-gray-800", action: () => {
        setSortBy("date-desc");
        setFilterBy("all");
        setTab("students");
      } },
      { l: "全部剩余课时", v: `${analytics.totalBalance} 课时`, c: "text-indigo-600", action: () => {
        setSortBy("bal-desc");
        setFilterBy("active");
        setTab("students");
      } },
      { l: "今日排课", v: `${TENANT_SLUG ? todayEffectiveCount : analytics.todayRoster.length} 人`, c: "text-gray-700", action: () => setTab("roster") },
      canViewFinancialAnalytics ? { l: "历史总营收", v: `$${analytics.totalRevenue.toFixed(0)}`, c: "text-emerald-600", action: () => setTab("stats") } : { l: "本月出勤", v: `${bizStats?.attended_month || 0} 人次`, c: "text-emerald-600", action: () => setTab("roster") }
    ].map(({ l, v, c, action }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: l,
        onClick: action,
        className: "bg-white p-4 rounded-2xl shadow-sm border border-indigo-100 text-left w-full active:bg-indigo-50 transition"
      },
      /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, l, " ", /* @__PURE__ */ React.createElement("span", { className: "text-indigo-400" }, "→")),
      /* @__PURE__ */ React.createElement("p", { className: `text-2xl font-bold ${c}` }, v)
    )))), (() => {
      const todoClear = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) === 0 && s.lastActive);
      const todoLast = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) === 1);
      const todoRisk = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.id] || 0) === 0);
      const now = /* @__PURE__ */ new Date();
      now.setHours(0, 0, 0, 0);
      const bdayWithin = (s, span) => {
        if (!s.birthday || s.archived) return false;
        const mm = parseInt(s.birthday.slice(5, 7), 10), dd = parseInt(s.birthday.slice(8, 10), 10);
        if (!mm || !dd) return false;
        for (let i = 0; i < span; i++) {
          const d = new Date(now.getFullYear(), now.getMonth(), now.getDate() + i);
          if (d.getMonth() + 1 === mm && d.getDate() === dd) return true;
          if (mm === 2 && dd === 29 && d.getMonth() === 2 && d.getDate() === 1 && new Date(d.getFullYear(), 1, 29).getDate() !== 29) return true;
        }
        return false;
      };
      const todoBdayWeek = db.students.filter((s) => bdayWithin(s, 8));
      const todoBdayMonth = db.students.filter((s) => {
        if (!s.birthday || s.archived) return false;
        return s.birthday.slice(5, 7) === String(now.getMonth() + 1).padStart(2, "0") && !todoBdayWeek.includes(s);
      });
      const todoFollowUp = (db.pending || []).filter((item) => item.nextFollowUpAt && String(item.nextFollowUpAt).slice(0, 10) <= todayISO());
      const total = todoClear.length + todoLast.length + todoRisk.length + todoBdayWeek.length + todoBdayMonth.length + todoFollowUp.length;
      if (!total) return null;
      const names = (arr, max = 4) => arr.slice(0, max).map((s) => s.name).join("、") + (arr.length > max ? ` 等${arr.length}人` : "");
      return /* @__PURE__ */ React.createElement("div", { className: "bg-white border border-gray-200 rounded-2xl overflow-hidden shadow-sm" }, /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 bg-gray-50 border-b flex items-center justify-between" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 font-bold text-gray-700 text-sm" }, /* @__PURE__ */ React.createElement(Icon, { name: "clock", className: "w-4 h-4" }), "今日待办"), /* @__PURE__ */ React.createElement("span", { className: "bg-indigo-600 text-white text-xs font-bold px-2 py-0.5 rounded-full" }, total, " 项")), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, todoFollowUp.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-indigo-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-4 h-4" }), "报名跟进到期 · ", todoFollowUp.length, " 项"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, todoFollowUp.slice(0, 4).map((item) => `${item.firstName || ""} ${item.lastName || ""}`.trim()).join("、"))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setTab("pending"),
          className: "flex-shrink-0 text-xs text-indigo-600 font-bold bg-indigo-50 active:bg-indigo-100 border border-indigo-200 px-3 py-1.5 rounded-xl min-h-[44px]"
        },
        "处理 →"
      )), todoClear.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-red-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-4 h-4" }), "课时已清零 · ", todoClear.length, " 人"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, names(todoClear))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setFilterBy("zero");
            setTab("students");
          },
          className: "flex-shrink-0 text-xs text-red-600 font-bold bg-red-50 active:bg-red-100 border border-red-200 px-3 py-1.5 rounded-xl min-h-[44px]"
        },
        "查看 →"
      )), todoLast.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-orange-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "bolt", className: "w-4 h-4" }), "最后 1 课时 · ", todoLast.length, " 人"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, names(todoLast))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setFilterBy("low");
            setTab("students");
          },
          className: "flex-shrink-0 text-xs text-orange-600 font-bold bg-orange-50 active:bg-orange-100 border border-orange-200 px-3 py-1.5 rounded-xl min-h-[44px]"
        },
        "查看 →"
      )), todoRisk.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between px-4 py-3 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-amber-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-4 h-4" }), "流失风险 · ", todoRisk.length, " 人"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate mt-0.5" }, names(todoRisk))), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setFilterBy("tag-risk");
            setTab("students");
          },
          className: "flex-shrink-0 text-xs text-amber-600 font-bold bg-amber-50 active:bg-amber-100 border border-amber-200 px-3 py-1.5 rounded-xl min-h-[44px]"
        },
        "查看 →"
      )), todoBdayWeek.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-pink-600" }, /* @__PURE__ */ React.createElement(Icon, { name: "cake", className: "w-4 h-4" }), "本周生日 · ", todoBdayWeek.length, " 人"), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            const msg = todoBdayWeek.map((s) => birthdayWish(s.name)).join("\n");
            copyText(msg, "祝福语已复制");
          },
          className: "flex-shrink-0 text-xs text-pink-600 font-bold bg-pink-50 active:bg-pink-100 border border-pink-200 px-3 py-1.5 rounded-xl min-h-[44px]"
        },
        "复制祝福 →"
      )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5" }, todoBdayWeek.map((s) => /* @__PURE__ */ React.createElement("span", { key: s.id, className: "inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700" }, s.name, s.mobile && /* @__PURE__ */ React.createElement("a", { href: `sms:${s.mobile.replace(/\s/g, "")}?body=${encodeURIComponent(birthdayWish(s.name))}`, "aria-label": "发送祝福短信", className: "text-pink-400 ml-0.5 active:text-pink-600 inline-flex" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-3.5 h-3.5" })))))), todoBdayMonth.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "px-4 py-3 space-y-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-pink-400" }, /* @__PURE__ */ React.createElement(Icon, { name: "cake", className: "w-4 h-4" }), "本月生日 · ", todoBdayMonth.length, " 人"), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            const msg = todoBdayMonth.map((s) => birthdayWish(s.name)).join("\n");
            copyText(msg, "祝福语已复制");
          },
          className: "flex-shrink-0 text-xs text-pink-400 font-bold bg-pink-50 active:bg-pink-100 border border-pink-100 px-3 py-1.5 rounded-xl min-h-[44px]"
        },
        "复制祝福 →"
      )), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5" }, todoBdayMonth.map((s) => /* @__PURE__ */ React.createElement("span", { key: s.id, className: "inline-flex items-center gap-1 bg-pink-50 border border-pink-100 rounded-full px-2.5 py-1 text-xs text-pink-700" }, s.name, s.mobile && /* @__PURE__ */ React.createElement("a", { href: `sms:${s.mobile.replace(/\s/g, "")}?body=${encodeURIComponent(birthdayWish(s.name))}`, "aria-label": "发送祝福短信", className: "text-pink-400 ml-0.5 active:text-pink-600 inline-flex" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-3.5 h-3.5" }))))))));
    })(), (() => {
      const rows = [];
      if ((db.pending || []).length > 0 && allowedTabs.includes("pending")) rows.push({
        key: "pending",
        icon: "clipboard",
        text: `${(db.pending || []).length} 位学员等待审核`,
        cta: "去审核",
        go: () => setTab("pending")
      });
      if (analytics.inactive.length > 0) rows.push({
        key: "inactive",
        icon: "calendar",
        text: `${analytics.inactive.length} 名学员有余额但超过 ${inactiveDays} 天未上课`,
        chips: analytics.inactive.slice(0, 12).map((s) => /* @__PURE__ */ React.createElement(
          "button",
          {
            key: s.id,
            type: "button",
            onClick: () => {
              setTab("students");
              setSrch(s.name);
            },
            className: "px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-100 text-amber-800 border border-amber-200 active:bg-amber-200 min-h-[44px]"
          },
          s.name,
          " (",
          s.balance,
          "课 · ",
          daysSince(s.lastActive) < 9999 ? `${daysSince(s.lastActive)}天前` : "从未上课",
          ")"
        ))
      });
      if (arSummary && arSummary.unpaidCount > 0) rows.push({
        key: "ar",
        icon: "invoice",
        text: `未付清 ${arSummary.unpaidCount} 张${arSummary.overdueCount > 0 ? `，其中逾期 ${arSummary.overdueCount} 张` : ""} · 应收 ${`$${(arSummary.unpaidCents / 100).toFixed(2)}`}`,
        cta: "进账单中心",
        go: () => setTab("billing")
      });
      if (analytics.lowBalance.length > 0) rows.push({
        key: "low",
        icon: "bolt",
        text: `${analytics.lowBalance.length} 名学员余额 ≤ 2 课时`,
        cta: "看名单",
        go: () => {
          setSortBy("bal-asc");
          setFilterBy("low");
          setTab("students");
        },
        chips: analytics.lowBalance.map((s) => /* @__PURE__ */ React.createElement("span", { key: s.id, className: "inline-flex items-stretch" }, /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: () => {
              setTab("students");
              setSrch(s.name);
            },
            className: `px-3 py-1.5 rounded-l-lg text-xs font-bold border min-h-[44px] ${parseInt(s.balance, 10) === 0 ? "bg-red-100 text-red-700 border-red-200" : "bg-amber-100 text-amber-800 border-amber-200"}`
          },
          s.name,
          " (",
          s.balance,
          ")"
        ), canWriteCredits && /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: () => {
              setTuStu(s.id);
              setTab("topup");
            },
            title: "去充值",
            "aria-label": `为 ${s.name} 充值`,
            className: "px-2.5 rounded-r-lg text-xs font-bold border border-l-0 min-h-[44px] bg-emerald-50 text-emerald-700 border-emerald-200 active:bg-emerald-100"
          },
          /* @__PURE__ */ React.createElement(Icon, { name: "money", className: "w-4 h-4" })
        )))
      });
      if (!rows.length) return null;
      const goButton = (row) => row.go ? /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: (e) => {
            e.preventDefault();
            e.stopPropagation();
            row.go();
          },
          className: "shrink-0 px-2 min-h-[44px] text-xs font-bold text-indigo-600 active:text-indigo-800 whitespace-nowrap"
        },
        row.cta,
        " →"
      ) : null;
      return /* @__PURE__ */ React.createElement("section", { className: "bg-white rounded-2xl shadow-sm border border-amber-200 overflow-hidden", "aria-labelledby": "needs-attention-title" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 bg-amber-50 border-b border-amber-200 px-4 py-3" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-4 h-4 text-amber-700" }), /* @__PURE__ */ React.createElement("h3", { id: "needs-attention-title", className: "text-sm font-bold text-amber-900" }, "需要注意"), /* @__PURE__ */ React.createElement("span", { className: "ml-auto rounded-full border border-amber-300 bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800 tabular-nums" }, rows.length)), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-100" }, rows.map((row) => row.chips ? /* @__PURE__ */ React.createElement("details", { key: row.key, className: "group" }, /* @__PURE__ */ React.createElement("summary", { className: "flex cursor-pointer select-none items-center gap-3 px-4 py-2 min-h-[44px] active:bg-amber-50" }, /* @__PURE__ */ React.createElement(Icon, { name: row.icon, className: "w-4 h-4 shrink-0 text-amber-600" }), /* @__PURE__ */ React.createElement("span", { className: "flex-1 text-sm text-gray-700" }, row.text), goButton(row), /* @__PURE__ */ React.createElement("span", { className: "shrink-0 text-indigo-600 group-open:rotate-180 transition-transform", "aria-hidden": "true" }, "⌄")), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2 px-4 pb-3" }, row.chips)) : /* @__PURE__ */ React.createElement(
        "button",
        {
          key: row.key,
          type: "button",
          onClick: row.go,
          className: "flex w-full items-center gap-3 px-4 py-2 min-h-[44px] text-left active:bg-amber-50"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: row.icon, className: "w-4 h-4 shrink-0 text-amber-600" }),
        /* @__PURE__ */ React.createElement("span", { className: "flex-1 text-sm text-gray-700" }, row.text),
        /* @__PURE__ */ React.createElement("span", { className: "shrink-0 px-2 text-xs font-bold text-indigo-600 whitespace-nowrap" }, row.cta, " →")
      ))));
    })(), TENANT_SLUG && bizStats && /* @__PURE__ */ React.createElement("details", { className: "bg-white rounded-2xl shadow-sm border border-emerald-100" }, /* @__PURE__ */ React.createElement("summary", { className: "inline-flex items-center gap-1.5 cursor-pointer px-4 py-3 font-bold text-sm text-gray-800 select-none" }, /* @__PURE__ */ React.createElement(Icon, { name: "trend", className: "w-4 h-4" }), canViewFinancialAnalytics ? "经营真账（估算）" : "教学出勤", " ", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-gray-400" }, "已上课 ", bizStats.attended_total, " 人次", bizStats.avg_price !== void 0 ? ` · 加权均价 $${bizStats.avg_price}/课时` : "")), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3 px-4 pb-4" }, [
      ["已上课人次", `${bizStats.attended_total} 次`, `本月 ${bizStats.attended_month} 次`, "text-gray-800"],
      ...bizStats.earned_revenue !== void 0 ? [["已赚收入(估)", `$${bizStats.earned_revenue}`, "人次 × 加权均价", "text-emerald-600"]] : [],
      ...bizStats.prepaid_liability !== void 0 ? [["预收未耗(负债)", `$${bizStats.prepaid_liability}`, "剩余课时 × 均价", "text-amber-600"]] : [],
      ...bizStats.cash_net !== void 0 ? [["净现金收入", `$${bizStats.cash_net}`, "充值 − 退款", "text-indigo-600"]] : []
    ].map(([l, v, sub, c]) => /* @__PURE__ */ React.createElement("div", { key: l, className: "bg-gray-50 border border-gray-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, l), /* @__PURE__ */ React.createElement("p", { className: `text-xl font-bold ${c}` }, v), /* @__PURE__ */ React.createElement("p", { className: "text-[10px] text-gray-400 mt-0.5" }, sub))))), TENANT_SLUG && (() => {
      const students = db.students.filter((student) => !student.archived);
      const metrics = [
        ["专区已就绪", students.filter((s) => s.mobile && s.hasAccessCode).length, "portal-ready", "lock"],
        ["缺少手机号", students.filter((s) => !s.mobile).length, "portal-missing-mobile", "phone"],
        ["专区未启用", students.filter((s) => s.mobile && !s.hasAccessCode).length, "portal-disabled", "warning"],
        ["私人内容受阻", students.filter((s) => (s.portfolio || []).length > 0 && (!s.mobile || !s.hasAccessCode)).length, "portal-content-blocked", "image"],
        ["作品已公开", students.filter((s) => (s.portfolio || []).some((item) => item.public || item.visibility === "shared")).length, "publication-live", "image"],
        ["公开授权有效", students.filter((s) => s.publicationConsent?.status === "confirmed").length, "publication-ready", "shield"],
        ["有作品但缺授权", students.filter((s) => (s.portfolio || []).length > 0 && s.publicationConsent?.status !== "confirmed").length, "publication-missing-consent", "warning"]
      ];
      return /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3 mb-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-sm text-gray-800" }, "学员专区与作品发布"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "点击数字直接处理对应学员")), /* @__PURE__ */ React.createElement(Icon, { name: "shield", className: "w-5 h-5 text-indigo-500" })), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-2" }, metrics.map(([label, value, filter, icon]) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: filter,
          type: "button",
          onClick: () => {
            setFilterBy(filter);
            setTab("students");
          },
          className: "min-h-[68px] rounded-xl border border-gray-200 bg-gray-50 px-3 py-2 text-left active:border-indigo-300 active:bg-indigo-50"
        },
        /* @__PURE__ */ React.createElement("span", { className: "flex items-center gap-1.5 text-xs text-gray-500" }, /* @__PURE__ */ React.createElement(Icon, { name: icon, className: "w-3.5 h-3.5" }), label),
        /* @__PURE__ */ React.createElement("span", { className: "mt-1 block text-xl font-bold text-gray-900 tabular-nums" }, value)
      ))));
    })(), allowedTabs.includes("logs") && /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setTab("logs"),
        className: "flex w-full items-center gap-3 rounded-2xl border border-gray-100 bg-white px-4 py-3 min-h-[44px] text-left shadow-sm active:bg-gray-50"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "scroll", className: "w-4 h-4 shrink-0 text-gray-400" }),
      /* @__PURE__ */ React.createElement("span", { className: "flex-1 text-sm text-gray-700" }, "最近操作"),
      /* @__PURE__ */ React.createElement("span", { className: "shrink-0 text-xs font-bold text-indigo-600" }, "全部 →")
    ));
  }

  // legacy-root/src/panels/scheduling.jsx
  var { useState: useState9 } = React;
  function CoursesSection(props) {
    const {
      archiveCourse,
      busy,
      canManageOperations,
      courseEdit,
      courses,
      saveCourse,
      setCourseEdit,
      setTab
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-5 max-w-6xl mx-auto" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-2 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-5 h-5" }), "课程目录"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, "维护可被固定课表引用的课程条目；公开课表是否展示详情仍由 Studio Admin 控制。")), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => setTab("roster", { section: "plan" }), className: "min-h-[44px] px-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-bold" }, "查看课程安排 →")), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-[1.618fr_1fr] gap-5 items-start" }, /* @__PURE__ */ React.createElement("section", { id: "courseManager", className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-5 space-y-3 scroll-mt-24", "aria-labelledby": "course-list-title" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", { id: "course-list-title", className: "font-bold text-gray-900" }, "已启用课程"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, courses.length, " 门课程")), canManageOperations && /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => setCourseEdit({ name: "", description: "", ageRange: "", durationMinutes: 60, priceAud: "" }), className: "min-h-[44px] px-3 rounded-xl bg-indigo-600 text-white text-xs font-bold" }, /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-4 h-4 inline mr-1" }), "添加课程")), courses.length === 0 && /* @__PURE__ */ React.createElement(EmptyState, { icon: /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-8 h-8" }), main: "还没有课程", sub: "先添加一门课程，再回到课程安排关联固定班次。", action: canManageOperations ? "添加第一门课程" : "", onAction: canManageOperations ? () => setCourseEdit({ name: "", description: "", ageRange: "", durationMinutes: 60, priceAud: "" }) : void 0 }), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, courses.map((course) => /* @__PURE__ */ React.createElement("article", { key: course.id, className: "rounded-2xl border border-gray-200 bg-gray-50 p-4 flex items-start gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "w-10 h-10 rounded-xl bg-indigo-100 text-indigo-700 inline-flex items-center justify-center flex-shrink-0" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-5 h-5" })), /* @__PURE__ */ React.createElement("div", { className: "min-w-0 flex-1" }, /* @__PURE__ */ React.createElement("h4", { className: "font-bold text-gray-900 truncate" }, course.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1" }, [course.age_range && `适龄 ${course.age_range}`, course.duration_minutes && `${course.duration_minutes} 分钟`, course.price_aud_cents ? `AUD ${(course.price_aud_cents / 100).toFixed(2)}` : "未标价"].filter(Boolean).join(" · ")), course.description && /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-600 mt-2 leading-relaxed" }, course.description)), canManageOperations && /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-1 flex-shrink-0" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => setCourseEdit({ id: course.id, name: course.name, description: course.description || "", ageRange: course.age_range || "", durationMinutes: course.duration_minutes || 60, priceAud: course.price_aud_cents ? String(course.price_aud_cents / 100) : "" }), className: "min-h-[44px] px-3 rounded-xl text-xs font-bold text-indigo-700 hover:bg-indigo-100" }, "编辑"), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => archiveCourse(course), "aria-label": `归档课程 ${course.name}`, className: "min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-red-600 hover:bg-red-50" }, /* @__PURE__ */ React.createElement(Icon, { name: "archiveBox", className: "w-4 h-4" }))))))), /* @__PURE__ */ React.createElement("aside", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-5", "aria-labelledby": "course-help-title" }, /* @__PURE__ */ React.createElement("h3", { id: "course-help-title", className: "font-bold text-gray-900" }, "这组信息会影响什么？"), /* @__PURE__ */ React.createElement("div", { className: "mt-3 space-y-3 text-sm text-gray-600 leading-relaxed" }, /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("strong", { className: "text-gray-800" }, "课程名称和简介"), "：供固定课表关联，是否对外显示取决于 Studio Admin 的公开课表开关。"), /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("strong", { className: "text-gray-800" }, "适龄段、时长和价格"), "：用于公开课程详情和内部排课参考，不会改动已经保存的排课。"), /* @__PURE__ */ React.createElement("p", { className: "rounded-xl bg-amber-50 border border-amber-100 px-3 py-2 text-xs text-amber-800" }, "归档不是删除。历史排课仍保留原课程名称，新排课不会再出现已归档课程。")))), courseEdit && canManageOperations && /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 z-[70] bg-black/40 flex items-end md:items-center justify-center p-0 md:p-4", role: "dialog", "aria-modal": "true", "aria-labelledby": "course-editor-title", onClick: () => setCourseEdit(null) }, /* @__PURE__ */ React.createElement("div", { className: "bg-white w-full md:max-w-xl rounded-t-2xl md:rounded-2xl p-5 md:p-6 space-y-4", onClick: (e) => e.stopPropagation() }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", { id: "course-editor-title", className: "text-lg font-bold text-gray-900" }, courseEdit.id ? "编辑课程" : "添加课程"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1" }, "带 * 为必填；保存后可在课程安排中关联。")), /* @__PURE__ */ React.createElement("label", { className: "block text-sm font-bold text-gray-700" }, "课程名称 *", /* @__PURE__ */ React.createElement("input", { id: "course-name", type: "text", required: true, value: courseEdit.name, onChange: (e) => setCourseEdit((p) => ({ ...p, name: e.target.value })), placeholder: "例如：儿童油画基础", className: "mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500" }), /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-normal text-gray-400 mt-1" }, "用于内部排课和公开课表标题。")), /* @__PURE__ */ React.createElement("label", { className: "block text-sm font-bold text-gray-700" }, "课程简介 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填"), /* @__PURE__ */ React.createElement("textarea", { rows: "3", value: courseEdit.description, onChange: (e) => setCourseEdit((p) => ({ ...p, description: e.target.value })), placeholder: "介绍课程内容、适合的学习目标", className: "mt-1 w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500" }), /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-normal text-gray-400 mt-1" }, "会随公开课表配置显示给访客。")), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-3 gap-3" }, /* @__PURE__ */ React.createElement("label", { className: "block text-sm font-bold text-gray-700" }, "适龄段 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填"), /* @__PURE__ */ React.createElement("input", { type: "text", value: courseEdit.ageRange, onChange: (e) => setCourseEdit((p) => ({ ...p, ageRange: e.target.value })), placeholder: "6–9 岁", className: "mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500" })), /* @__PURE__ */ React.createElement("label", { className: "block text-sm font-bold text-gray-700" }, "时长（分钟） *", /* @__PURE__ */ React.createElement("input", { type: "number", min: "1", required: true, value: courseEdit.durationMinutes, onChange: (e) => setCourseEdit((p) => ({ ...p, durationMinutes: e.target.value })), className: "mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500" })), /* @__PURE__ */ React.createElement("label", { className: "block text-sm font-bold text-gray-700" }, "价格（AUD） ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填"), /* @__PURE__ */ React.createElement("input", { type: "number", min: "0", step: "0.01", value: courseEdit.priceAud, onChange: (e) => setCourseEdit((p) => ({ ...p, priceAud: e.target.value })), placeholder: "0.00", className: "mt-1 w-full min-h-[46px] px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500" }))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 pt-1" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => setCourseEdit(null), className: "flex-1 min-h-[48px] rounded-xl border border-gray-300 text-sm font-bold text-gray-600" }, "取消"), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: saveCourse, disabled: busy, className: "flex-1 min-h-[48px] rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50" }, busy ? "保存中…" : "保存课程")))));
  }
  var closeMenu = (e) => {
    const menu = e.currentTarget.closest("details");
    if (menu) menu.open = false;
  };
  function RosterSection(props) {
    const {
      WEEKDAYS: WEEKDAYS2,
      addToRoster,
      applyGroup,
      availRoster,
      batchCheckIn,
      busy,
      canExportData,
      canManageOperations,
      canWriteAttendance,
      canWriteScheduling,
      checkIn,
      checkInWindow,
      copyRosterDaily,
      copyRosterReminders,
      copyText,
      courses,
      dayIds,
      db,
      defaultClassTime,
      deleteGroup,
      deleteSchedule,
      groupToSchedule,
      grpSel,
      icsBusy,
      loadSchedules,
      nextOccurrence,
      openIcsPreview,
      rDate,
      rOneToOne,
      rPick,
      rTime,
      removeFromRoster,
      renderMessage,
      renewTh,
      restoreCancellation,
      rosterDone,
      rosterMetaFor,
      rosterSlotFor,
      saveCancellation,
      saveGroup,
      saveSchedule,
      schedCancel,
      schedEdit,
      schedOverlap,
      rosterSection,
      schedPick,
      scheduleLoadError,
      scheduledForDate,
      schedules,
      setGrpSel,
      setRDate,
      setRosterSection,
      setROneToOne,
      setRPick,
      setRTime,
      setSchedCancel,
      setSchedEdit,
      setSchedPick,
      setTab,
      showToast,
      sortedAZ,
      teachableMembers,
      tenantDisplayName,
      undoCheckIn,
      updateRosterEntry
    } = props;
    const [monthOpen, setMonthOpen] = useState9(() => {
      try {
        return localStorage.getItem("lp_ui_roster_month") === "1";
      } catch (e) {
        return false;
      }
    });
    const toggleMonth = () => setMonthOpen((open) => {
      try {
        localStorage.setItem("lp_ui_roster_month", open ? "0" : "1");
      } catch (e) {
      }
      return !open;
    });
    const rosterTabs = Boolean(TENANT_SLUG);
    const RosterPanel = ({ name, active, children }) => rosterTabs ? /* @__PURE__ */ React.createElement(TabPanel, { idBase: "roster", name, active }, children) : /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, children);
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "课程安排"), scheduleLoadError && /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 rounded-2xl border border-red-200 bg-red-50 p-3 text-sm text-red-700" }, /* @__PURE__ */ React.createElement("span", { className: "flex-1" }, scheduleLoadError), /* @__PURE__ */ React.createElement("button", { onClick: loadSchedules, className: "rounded-xl border border-red-200 bg-white px-3 py-2 text-xs font-bold min-h-[44px]" }, "重试")), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-planner bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "w-full" }, /* @__PURE__ */ React.createElement("label", { className: "cms-roster-date-label text-xs font-bold text-gray-500 mb-1 block" }, "课程日期"), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-date-nav" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setRDate(shiftDate(rDate, -1)),
        "aria-label": "前一天",
        className: "cms-roster-date-button"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "chevronLeft", className: "w-4 h-4" })
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setRDate(todayISO()),
        "aria-current": rDate === todayISO() ? "date" : void 0,
        className: "cms-roster-today"
      },
      "今天"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => setRDate(shiftDate(rDate, 1)),
        "aria-label": "后一天",
        className: "cms-roster-date-button"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "chevronRight", className: "w-4 h-4" })
    ), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: rDate,
        onChange: (e) => setRDate(e.target.value),
        "aria-label": "选择课程日期",
        className: "w-full px-3 py-3 min-h-[50px] border border-gray-300 rounded-xl font-bold text-gray-900 focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), (() => {
      const countFor = (iso3, weekday) => {
        const manual = db.rosters[iso3] || [];
        const sched = schedules.filter((sc) => sc.weekday === weekday).flatMap((sc) => sc.students.map((st) => st.id));
        return (/* @__PURE__ */ new Set([...sched, ...manual])).size;
      };
      const cell = (d, { outside = false } = {}) => {
        const iso3 = d.toLocaleDateString("en-CA");
        const n = countFor(iso3, d.getDay());
        const isSel = iso3 === rDate, isToday = iso3 === todayISO();
        return /* @__PURE__ */ React.createElement(
          "button",
          {
            key: iso3,
            type: "button",
            onClick: () => setRDate(iso3),
            "aria-current": isSel ? "date" : void 0,
            "aria-label": `${WEEKDAYS2[d.getDay()]} ${fmtDate(iso3)}，${n} 人`,
            className: `cms-roster-week-day ${isSel ? "is-selected" : ""} ${isToday ? "is-today" : ""} ${outside ? "is-outside" : ""}`
          },
          /* @__PURE__ */ React.createElement("p", { className: "text-[10px] opacity-70" }, monthOpen ? "" : WEEKDAYS2[d.getDay()], isToday ? "·今" : ""),
          /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold" }, d.getDate()),
          /* @__PURE__ */ React.createElement("p", { className: "text-[10px] font-bold opacity-80" }, n > 0 ? n : "—")
        );
      };
      const anchor = /* @__PURE__ */ new Date(`${rDate}T12:00:00`);
      if (!monthOpen) {
        const monday = new Date(anchor);
        monday.setDate(anchor.getDate() - (anchor.getDay() + 6) % 7);
        return /* @__PURE__ */ React.createElement("div", { className: "cms-roster-week", role: "group", "aria-label": "本周课程日期" }, [0, 1, 2, 3, 4, 5, 6].map((i) => {
          const d = new Date(monday);
          d.setDate(monday.getDate() + i);
          return cell(d);
        }));
      }
      const year = anchor.getFullYear(), month = anchor.getMonth();
      const first = new Date(year, month, 1);
      const lead = (first.getDay() + 6) % 7;
      const start = new Date(year, month, 1 - lead);
      const cells = Array.from({ length: 42 }, (_, i) => new Date(year, month, 1 - lead + i));
      const shown = cells.slice(35).every((d) => d.getMonth() !== month) ? cells.slice(0, 35) : cells;
      const jump = (delta) => setRDate(new Date(year, month + delta, 1).toLocaleDateString("en-CA"));
      return /* @__PURE__ */ React.createElement("div", { className: "space-y-1" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => jump(-1),
          "aria-label": "上个月",
          className: "cms-roster-date-button"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "chevronLeft", className: "w-4 h-4" })
      ), /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-800" }, year, " 年 ", month + 1, " 月"), /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => jump(1),
          "aria-label": "下个月",
          className: "cms-roster-date-button"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "chevronRight", className: "w-4 h-4" })
      )), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-month-head", "aria-hidden": "true" }, ["一", "二", "三", "四", "五", "六", "日"].map((w) => /* @__PURE__ */ React.createElement("span", { key: w }, w))), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-month", role: "group", "aria-label": "本月课程日期" }, shown.map((d) => cell(d, { outside: d.getMonth() !== month }))));
    })(), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: toggleMonth,
        "aria-expanded": monthOpen,
        className: "w-full min-h-[44px] text-xs font-bold text-indigo-600 active:text-indigo-800"
      },
      monthOpen ? "收起为本周 ⌃" : "展开整月 ⌄"
    ), (() => {
      const valid = dayIds.filter((id) => {
        const s = db.students.find((x) => x.id === id);
        return s && !s.archived;
      });
      const done = valid.filter((id) => rosterDone.has(id)).length;
      const low = valid.filter((id) => {
        const s = db.students.find((x) => x.id === id);
        return s && (parseInt(s.balance, 10) || 0) <= renewTh;
      }).length;
      if (!valid.length) return null;
      return /* @__PURE__ */ React.createElement("div", { className: "cms-roster-summary", "aria-live": "polite" }, /* @__PURE__ */ React.createElement("strong", null, rDate === todayISO() ? "今日" : fmtDate(rDate), " · ", valid.length, " 人"), /* @__PURE__ */ React.createElement("span", { className: "is-success" }, "已签到 ", done), rDate < todayISO() ? valid.length - done > 0 && /* @__PURE__ */ React.createElement("span", { className: "is-warning" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "inline-block w-3.5 h-3.5 mr-1" }), "未签到 ", valid.length - done) : /* @__PURE__ */ React.createElement("span", null, "待上课 ", valid.length - done), low > 0 && /* @__PURE__ */ React.createElement("span", { className: "is-warning" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "inline-block w-3.5 h-3.5 mr-1" }), "低余额 ", low), checkInWindow.reason && /* @__PURE__ */ React.createElement("span", { className: "is-warning" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "inline-block w-3.5 h-3.5 mr-1" }), checkInWindow.reason));
    })()), rosterTabs && /* @__PURE__ */ React.createElement(
      Tabs,
      {
        idBase: "roster",
        label: "课程安排分区",
        value: rosterSection,
        onChange: setRosterSection,
        items: [
          { value: "checkin", label: "今日签到", icon: "check" },
          { value: "plan", label: "排课设置", icon: "settings" }
        ]
      }
    ), /* @__PURE__ */ React.createElement(RosterPanel, { name: "checkin", active: rosterSection === "checkin" }, (() => {
      const ids = dayIds.filter((id) => {
        const st = db.students.find((x) => x.id === id);
        return st && !st.archived;
      });
      if (!ids.length) return null;
      const slots = {};
      ids.forEach((id) => {
        const t = (rosterSlotFor(rDate, id) || "").trim() || "__unset";
        (slots[t] = slots[t] || []).push(id);
      });
      const groups = Object.entries(slots).sort(([a], [b]) => a === "__unset" ? 1 : b === "__unset" ? -1 : a.localeCompare(b));
      const nameOf = (id) => db.students.find((x) => x.id === id)?.name || "";
      const conflicted = groups.some(([, arr]) => arr.filter((id) => !!rosterMetaFor(rDate, id).oneToOne).length > 0 && arr.length > 1);
      return /* @__PURE__ */ React.createElement("details", { className: "cms-roster-slot-panel", open: conflicted }, /* @__PURE__ */ React.createElement("summary", { className: "list-none cursor-pointer min-h-[44px] flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-sm text-gray-800 inline-flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Icon, { name: "clock", className: "w-4 h-4" }), "时段安排", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-gray-400" }, conflicted ? "有 1 对 1 时间冲突" : `${groups.length} 个时段`)), /* @__PURE__ */ React.createElement("span", { className: "text-indigo-600", "aria-hidden": "true" }, "⌄")), /* @__PURE__ */ React.createElement("div", { className: "space-y-1.5 pt-2" }, groups.map(([t, arr]) => {
        const soloIds = arr.filter((id) => !!rosterMetaFor(rDate, id).oneToOne);
        const clash = soloIds.length > 0 && arr.length > 1;
        return /* @__PURE__ */ React.createElement("div", { key: t, className: `cms-roster-slot-row ${clash ? "has-conflict" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap items-center gap-x-2 gap-y-1 text-xs" }, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-800 min-w-[56px]" }, t === "__unset" ? "时间未设置" : t), /* @__PURE__ */ React.createElement("span", { className: "px-2 py-0.5 rounded-full bg-white border border-gray-200 font-bold" }, arr.length, " 人"), /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, arr.map(nameOf).filter(Boolean).join("、"))), soloIds.length > 0 && /* @__PURE__ */ React.createElement("p", { className: `mt-1 text-xs font-bold ${clash ? "text-red-700" : "text-indigo-600"}` }, clash ? `1 对 1 时间冲突：${soloIds.map(nameOf).join("、")} 与同时段其他排课重叠` : `1 对 1：${soloIds.map(nameOf).join("、")}`));
      })));
    })(), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b px-4 py-3 flex justify-between items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-sm text-gray-800" }, fmtDate(rDate), " · ", dayIds.filter((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived;
    }).length, " 人", scheduledForDate.length > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-indigo-500 ml-1" }, `（课表 ${scheduledForDate.length} 班）`)), dayIds.length > 0 && /* @__PURE__ */ React.createElement("details", { className: "cms-day-actions-mobile" }, /* @__PURE__ */ React.createElement("summary", null, /* @__PURE__ */ React.createElement(Icon, { name: "ellipsis", className: "w-4 h-4" }), "当日操作"), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-menu", onClick: closeMenu }, canExportData && /* @__PURE__ */ React.createElement("button", { onClick: () => openIcsPreview("roster"), disabled: icsBusy }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "导出当日 ICS"), /* @__PURE__ */ React.createElement("button", { onClick: copyRosterDaily }, /* @__PURE__ */ React.createElement(Icon, { name: "clipboard", className: "w-4 h-4" }), "复制日报"), dayIds.some((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.mobile;
    }) && /* @__PURE__ */ React.createElement("button", { onClick: copyRosterReminders }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "批量提醒"), canWriteAttendance && dayIds.some((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.balance > 0;
    }) && /* @__PURE__ */ React.createElement("button", { onClick: batchCheckIn, disabled: busy || !checkInWindow.ok, title: checkInWindow.ok ? void 0 : checkInWindow.reason }, /* @__PURE__ */ React.createElement(Icon, { name: "check", className: "w-4 h-4" }), "批量签到并扣课时"))), /* @__PURE__ */ React.createElement("div", { role: "group", "aria-label": "当日导出与批量操作", className: "cms-day-actions-desktop flex gap-2 flex-wrap" }, dayIds.length > 0 && canExportData && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => openIcsPreview("roster"),
        disabled: icsBusy,
        className: "border border-gray-200 bg-white text-gray-700 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px] inline-flex items-center gap-1.5 disabled:opacity-50"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }),
      "导出当日 ICS"
    ), dayIds.length > 0 && /* @__PURE__ */ React.createElement("button", { onClick: copyRosterDaily, className: "bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "clipboard", className: "w-4 h-4" }), "日报")), dayIds.some((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.mobile;
    }) && /* @__PURE__ */ React.createElement("button", { onClick: copyRosterReminders, className: "bg-white border border-green-300 active:bg-green-50 text-green-700 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "批量提醒")), canWriteAttendance && dayIds.some((id) => {
      const s = db.students.find((x) => x.id === id);
      return s && !s.archived && s.balance > 0;
    }) && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: batchCheckIn,
        disabled: busy || !checkInWindow.ok,
        title: checkInWindow.ok ? void 0 : checkInWindow.reason,
        className: "inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 disabled:opacity-40 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "bolt", className: "w-4 h-4" }),
      "批量签到并扣课时"
    ))), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-list divide-y divide-gray-100" }, !dayIds.length && /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        icon: /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-8 h-8" }),
        main: "今天还没有排课",
        sub: TENANT_SLUG ? "在下方「调整这一天的名单」加人；要让每周都自动排入，用页尾的「固定课表」建一个班次。" : "在下方「调整这一天的名单」添加学员即可开始今天的排课。",
        action: canWriteAttendance ? "添加学员" : "",
        onAction: canWriteAttendance ? () => {
          const el = document.getElementById("rosterAddStudent");
          if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
        } : void 0
      }
    ), dayIds.map((sid) => {
      const s = db.students.find((x) => x.id === sid);
      if (!s || s.archived) return null;
      const entry = rosterMetaFor(rDate, sid);
      const isDone = rosterDone.has(s.id);
      const lowBal = (parseInt(s.balance, 10) || 0) <= renewTh && !isDone;
      const slot = rosterSlotFor(rDate, sid);
      const dayIsPast = rDate < todayISO();
      const rosterStatus = isDone ? "已签到" : entry.status === "makeup" ? "补课" : dayIsPast ? "未签到" : "待上课";
      return /* @__PURE__ */ React.createElement("div", { key: sid, className: `cms-roster-row hover-row ${lowBal ? "is-low" : ""}` }, /* @__PURE__ */ React.createElement("div", { className: "cms-roster-info" }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }), /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 min-w-0 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-900 truncate" }, s.name), entry.oneToOne && /* @__PURE__ */ React.createElement("span", { className: "text-[11px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-200 rounded-full px-2 py-0.5" }, "1 对 1"), /* @__PURE__ */ React.createElement("span", { className: `text-[11px] font-bold rounded-full px-2 py-0.5 border ${isDone ? "bg-green-50 border-green-200 text-green-700" : entry.status === "makeup" ? "bg-blue-50 border-blue-200 text-blue-700" : rosterStatus === "未签到" ? "bg-amber-50 border-amber-200 text-amber-700" : "bg-gray-50 border-gray-200 text-gray-600"}` }, rosterStatus)), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate" }, [s.mobile || "未填写手机", slot, entry.note].filter(Boolean).join(" · "))), /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance })), /* @__PURE__ */ React.createElement("div", { className: `cms-roster-actions ${lowBal ? "has-reminder" : ""}` }, TENANT_SLUG && entry.id && canWriteAttendance && /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "time",
          defaultValue: entry.classTime || "",
          "aria-label": `${s.name} 的上课时间`,
          onChange: (e) => {
            const entryId = entry.id;
            updateRosterEntry(entryId, { classTime: e.target.value || "" }).then(() => showToast(e.target.value ? `${s.name} 上课时间改为 ${e.target.value}` : `${s.name} 已清除上课时间`)).catch((err) => showToast(err.message || "时间未能保存", "error"));
          },
          className: "cms-roster-time px-2 py-2 border border-gray-300 rounded-xl bg-white text-xs font-bold min-h-[44px] outline-none focus:ring-2 focus:ring-indigo-500"
        }
      ), TENANT_SLUG && (!entry.id || !canWriteAttendance) && /* @__PURE__ */ React.createElement("span", { className: "cms-roster-time px-3 py-2 border border-gray-200 rounded-xl bg-gray-50 text-xs font-bold text-gray-700 min-h-[44px] inline-flex items-center" }, slot || "未设时间"), lowBal && /* @__PURE__ */ React.createElement("button", { onClick: () => {
        const msg = renderMessage(
          "renewal",
          "{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。",
          { student: s.name, balance: s.balance, note: (parseInt(s.balance, 10) || 0) === 0 ? "（已用完）" : "" }
        );
        copyText(msg, `已复制给 ${s.name} 的催费提醒`);
      }, className: "cms-roster-reminder" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "续费提醒"), isDone || !canWriteAttendance ? /* @__PURE__ */ React.createElement("button", { disabled: true, className: "cms-roster-primary is-done" }, /* @__PURE__ */ React.createElement(Icon, { name: "check", className: "w-4 h-4" }), isDone ? "已签到" : "待上课") : /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => checkIn(s.id, s.name),
          disabled: busy || s.balance <= 0 || !checkInWindow.ok,
          title: checkInWindow.ok ? void 0 : checkInWindow.reason,
          "aria-label": `为 ${s.name} 签到并扣 1 课时`,
          className: "cms-roster-primary"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "check", className: "w-4 h-4" }),
        !checkInWindow.ok ? "不可签到" : s.balance > 0 ? "签到并扣 1 课时" : "余额不足"
      ), /* @__PURE__ */ React.createElement("details", { className: "cms-roster-more", name: "roster-student-actions" }, /* @__PURE__ */ React.createElement("summary", { "aria-label": `${s.name} 更多操作` }, /* @__PURE__ */ React.createElement(Icon, { name: "ellipsis", className: "w-5 h-5" })), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-menu", onClick: closeMenu }, /* @__PURE__ */ React.createElement("div", { className: "cms-roster-menu__context" }, /* @__PURE__ */ React.createElement("strong", null, s.name), /* @__PURE__ */ React.createElement("span", null, fmtDate(rDate), " · ", slot || "时间未设置", " · 余额 ", s.balance)), entry.id && canWriteAttendance && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("p", { className: "cms-roster-menu__label" }, "课程状态"), /* @__PURE__ */ React.createElement("button", { onClick: () => {
        updateRosterEntry(entry.id, { status: "scheduled" }).then(() => showToast(`${s.name} 已标记为待上课`)).catch((err) => showToast(err.message || "课程状态未能保存", "error"));
      }, disabled: busy || entry.status !== "makeup", "aria-current": entry.status !== "makeup" ? "true" : void 0 }, /* @__PURE__ */ React.createElement(Icon, { name: "check", className: "w-4 h-4" }), "待上课"), /* @__PURE__ */ React.createElement("button", { onClick: () => {
        updateRosterEntry(entry.id, { status: "makeup" }).then(() => showToast(`${s.name} 已标记为补课`)).catch((err) => showToast(err.message || "课程状态未能保存", "error"));
      }, disabled: busy || entry.status === "makeup", "aria-current": entry.status === "makeup" ? "true" : void 0 }, /* @__PURE__ */ React.createElement(Icon, { name: "refresh", className: "w-4 h-4" }), "补课"), /* @__PURE__ */ React.createElement("div", { className: "cms-roster-menu__separator" })), s.mobile && /* @__PURE__ */ React.createElement("a", { href: `sms:${s.mobile.replace(/\s/g, "")}?body=${encodeURIComponent(`提醒：您的上课时间是 ${fmtDate(rDate)}${slot ? ` ${slot}` : ""}，请准时到课。${tenantDisplayName} 期待见到您！`)}` }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "发短信提醒"), entry.id && canWriteAttendance && /* @__PURE__ */ React.createElement("button", { onClick: () => {
        updateRosterEntry(entry.id, { oneToOne: !entry.oneToOne }).then(() => showToast(entry.oneToOne ? "已改为普通班课" : "已标记为 1 对 1")).catch((err) => showToast(err.message || "排课类型未能保存", "error"));
      }, disabled: busy }, /* @__PURE__ */ React.createElement(Icon, { name: "users", className: "w-4 h-4" }), entry.oneToOne ? "改为普通班课" : "标记为 1 对 1"), isDone && canWriteAttendance && /* @__PURE__ */ React.createElement("button", { onClick: () => {
        undoCheckIn(s.id, s.name);
      }, disabled: busy }, /* @__PURE__ */ React.createElement(Icon, { name: "refresh", className: "w-4 h-4" }), "撤销本日签到"), entry.id && canWriteAttendance ? /* @__PURE__ */ React.createElement("button", { onClick: () => {
        removeFromRoster(s.id);
      }, disabled: busy, className: "is-danger" }, /* @__PURE__ */ React.createElement(Icon, { name: "trash", className: "w-4 h-4" }), "移出本日课程安排") : /* @__PURE__ */ React.createElement("p", { className: "cms-roster-menu__source" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), entry.id ? "当前角色只读" : "来自固定课表，需在页尾的固定课表中调整")))));
    }))), (canWriteAttendance || canManageOperations) && /* @__PURE__ */ React.createElement("div", { className: "cms-roster-tools bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 font-bold text-sm text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-4 h-4" }), "调整这一天的名单"), canWriteAttendance && /* @__PURE__ */ React.createElement("div", { className: "cms-roster-add", id: "rosterAddStudent" }, /* @__PURE__ */ React.createElement("div", { className: "cms-roster-add-fields" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "添加学员"), /* @__PURE__ */ React.createElement(StudentPicker, { students: availRoster, value: rPick, onChange: setRPick, placeholder: "搜索并选择学员..." })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "上课时间"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "time",
        value: rTime,
        onChange: (e) => setRTime(e.target.value),
        "aria-label": "上课时间",
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl bg-white text-sm font-bold min-h-[50px] outline-none focus:ring-2 focus:ring-indigo-500"
      }
    )), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: addToRoster,
        disabled: !rPick || busy,
        className: "cms-roster-add-button bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-3 rounded-xl font-bold text-sm min-h-[50px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-4 h-4" }),
      rPick ? "加入课程安排" : "请先选择学员"
    )), /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-2 mt-2 text-xs font-bold text-gray-500 min-h-[44px]" }, /* @__PURE__ */ React.createElement("input", { type: "checkbox", checked: rOneToOne, onChange: (e) => setROneToOne(e.target.checked), className: "w-4 h-4" }), "1 对 1（同时段还有其他人时会提示冲突）")), /* @__PURE__ */ React.createElement("details", { className: `group ${canWriteAttendance ? "pt-3 border-t border-gray-100" : ""}` }, /* @__PURE__ */ React.createElement("summary", { className: "list-none cursor-pointer min-h-[44px] flex items-center justify-between gap-3 text-xs font-bold text-gray-600" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "clipboard", className: "w-4 h-4" }), "班组模板与批量工具"), /* @__PURE__ */ React.createElement("span", { className: "text-indigo-600 group-open:rotate-180 transition-transform", "aria-hidden": "true" }, "⌄")), /* @__PURE__ */ React.createElement("div", { className: "pt-2 flex gap-2 items-center flex-wrap" }, /* @__PURE__ */ React.createElement(
      "select",
      {
        value: grpSel,
        onChange: (e) => setGrpSel(e.target.value),
        className: "px-2 py-2 border border-gray-300 rounded-xl bg-white text-sm font-medium min-h-[44px] outline-none focus:ring-2 focus:ring-indigo-500"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "-- 选择模板 --"),
      Object.keys(db.groups || {}).sort().map((g) => /* @__PURE__ */ React.createElement("option", { key: g, value: g }, `${g}（${(db.groups[g] || []).length} 人）`))
    ), canWriteAttendance && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: applyGroup,
        disabled: !grpSel || busy,
        className: "bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]"
      },
      "套用到当前日期"
    ), canManageOperations && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: saveGroup,
        disabled: busy,
        className: "bg-white text-gray-600 border border-gray-300 active:bg-gray-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]"
      },
      "保存当前为模板"
    ), canManageOperations && grpSel && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: deleteGroup,
        disabled: busy,
        className: "bg-white text-red-500 border border-red-200 active:bg-red-50 px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]"
      },
      "删除"
    ), canManageOperations && TENANT_SLUG && grpSel && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: groupToSchedule,
        disabled: busy,
        className: "inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-3 py-2 rounded-xl text-xs font-bold min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }),
      "转为每周班次"
    ))))), rosterTabs && /* @__PURE__ */ React.createElement(RosterPanel, { name: "plan", active: rosterSection === "plan" }, TENANT_SLUG && /* @__PURE__ */ React.createElement("details", { className: "border border-indigo-100 rounded-2xl overflow-hidden group" }, /* @__PURE__ */ React.createElement("summary", { className: "list-none cursor-pointer min-h-[44px] px-4 py-3 flex items-center justify-between gap-3 bg-indigo-50 text-sm font-bold text-indigo-800" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "一对一循环课与补课额度"), /* @__PURE__ */ React.createElement("span", { className: "group-open:rotate-180 transition-transform", "aria-hidden": "true" }, "⌄")), /* @__PURE__ */ React.createElement("div", { className: "p-3 bg-white" }, /* @__PURE__ */ React.createElement(
      PrivateLessonsPanel,
      {
        api: v1Api,
        showToast,
        canWrite: canWriteScheduling,
        canWritePolicy: canManageOperations,
        students: db.students.filter((s) => !s.archived)
      }
    ))), TENANT_SLUG && /* @__PURE__ */ React.createElement("details", { id: "rosterSchedules", className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden group" }, /* @__PURE__ */ React.createElement("summary", { className: "list-none cursor-pointer min-h-[52px] px-4 py-3 flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-2 min-w-0" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4 text-gray-500" }), /* @__PURE__ */ React.createElement("span", null, /* @__PURE__ */ React.createElement("span", { className: "block text-sm font-bold text-gray-800" }, "固定课表"), /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-normal text-gray-400" }, schedules.length ? `${schedules.length} 个每周班次` : "创建每周自动排课班次"))), /* @__PURE__ */ React.createElement("span", { className: "text-indigo-600 group-open:rotate-180 transition-transform", "aria-hidden": "true" }, "⌄")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 font-bold text-sm text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "每周课表 ", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-gray-400" }, "固定班次按周几自动排入当日名单")), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => openIcsPreview("schedule"),
        disabled: icsBusy || schedules.length === 0,
        title: schedules.length ? "导出所有固定班次，不包含学员姓名" : "请先新增固定班次",
        className: "inline-flex items-center gap-1.5 border border-indigo-200 bg-indigo-50 text-indigo-700 px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px] active:bg-indigo-100 disabled:opacity-50"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-3.5 h-3.5" }),
      "固定课表 ICS"
    ), canManageOperations && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSchedEdit({ label: "", weekday: (/* @__PURE__ */ new Date()).getDay(), startTime: defaultClassTime, durationMinutes: 60, capacity: 10, studentIds: [], courseId: "", teacherUserId: "", isPublic: false, room: "" }),
        className: "inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-4 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-3.5 h-3.5" }),
      "新增班次"
    ))), schedules.length === 0 && !schedEdit && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "还没有固定班次。例如「周三 16:00 素描班」——保存后每周三会自动出现在当日排课里。"), schedules.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, schedules.map((sc) => /* @__PURE__ */ React.createElement("div", { key: sc.id, className: `border rounded-xl px-3 py-2 ${sc.weekday === (/* @__PURE__ */ new Date(`${rDate}T12:00:00`)).getDay() ? "border-indigo-300 bg-indigo-50" : "border-gray-200 bg-gray-50"}` }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-gray-800" }, WEEKDAYS2[sc.weekday], " ", sc.startTime, " · ", sc.label || "未命名班次"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-500 mt-0.5" }, sc.students.length, "/", sc.capacity, " 人 · ", sc.durationMinutes, " 分钟", sc.teacherName && /* @__PURE__ */ React.createElement(React.Fragment, null, " · ", sc.teacherName, " 老师"), sc.room && /* @__PURE__ */ React.createElement(React.Fragment, null, " · ", sc.room)), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] mt-0.5" }, sc.isPublic ? /* @__PURE__ */ React.createElement("span", { className: "text-green-700" }, "● 已公开", sc.teacherUserId && !sc.teacherIsPublic ? "（不显示老师姓名）" : "") : /* @__PURE__ */ React.createElement("span", { className: "text-gray-400" }, "○ 仅内部可见")), (sc.cancellations || []).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "mt-1 space-y-0.5" }, sc.cancellations.map((c) => /* @__PURE__ */ React.createElement("p", { key: c.date, className: "text-[11px] text-amber-700" }, c.date, " 停课", c.note ? ` · ${c.note}` : "", canManageOperations && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => restoreCancellation(sc, c.date),
        disabled: busy,
        className: "ml-1.5 font-bold text-indigo-600 active:text-indigo-800"
      },
      "恢复"
    )))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 mt-1" }, canManageOperations && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSchedEdit({ id: sc.id, label: sc.label, weekday: sc.weekday, startTime: sc.startTime, durationMinutes: sc.durationMinutes, capacity: sc.capacity, studentIds: sc.students.map((st) => st.id), courseId: sc.courseId || "", teacherUserId: sc.teacherUserId || "", isPublic: !!sc.isPublic, room: sc.room || "" }),
        className: "text-[11px] font-bold text-indigo-600 active:text-indigo-800"
      },
      "编辑"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSchedCancel({ id: sc.id, label: sc.label || "未命名班次", date: nextOccurrence(sc.weekday), note: "" }),
        className: "text-[11px] font-bold text-amber-600 active:text-amber-800"
      },
      "停课"
    ), /* @__PURE__ */ React.createElement("button", { onClick: () => deleteSchedule(sc), className: "text-[11px] font-bold text-red-500 active:text-red-700" }, "删除")))))), schedEdit && /* @__PURE__ */ React.createElement("div", { className: "border-t border-gray-100 pt-3 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 lg:grid-cols-5 gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "col-span-2" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "班次名称"), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: schedEdit.label,
        onChange: (e) => setSchedEdit((p) => ({ ...p, label: e.target.value })),
        placeholder: "如：周三素描班",
        className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "周几"), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: schedEdit.weekday,
        onChange: (e) => setSchedEdit((p) => ({ ...p, weekday: Number(e.target.value) })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500"
      },
      WEEKDAYS2.map((w, i) => /* @__PURE__ */ React.createElement("option", { key: i, value: i }, w))
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "开始时间"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "time",
        value: schedEdit.startTime,
        onChange: (e) => setSchedEdit((p) => ({ ...p, startTime: e.target.value })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "容量"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "1",
        value: schedEdit.capacity,
        onChange: (e) => setSchedEdit((p) => ({ ...p, capacity: e.target.value })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 lg:grid-cols-3 gap-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "关联课程", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "（选填）")), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: schedEdit.courseId || "",
        onChange: (e) => setSchedEdit((p) => ({ ...p, courseId: e.target.value })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "不关联课程"),
      courses.map((c) => /* @__PURE__ */ React.createElement("option", { key: c.id, value: c.id }, c.name))
    ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400 mt-1" }, courses.length ? "关联后，课程简介和适龄段可用于公开课表；未关联时只用班次名称。" : "还没有课程。", /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => {
          setTab("courses");
          setTimeout(() => document.getElementById("courseManager")?.scrollIntoView({ block: "center" }), 80);
        },
        className: "ml-1 font-bold text-indigo-600 active:text-indigo-800 underline"
      },
      courses.length ? "管理课程" : "去添加课程 →"
    ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "授课老师", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "（选填）")), /* @__PURE__ */ React.createElement(
      "select",
      {
        value: schedEdit.teacherUserId || "",
        onChange: (e) => setSchedEdit((p) => ({ ...p, teacherUserId: e.target.value })),
        className: "w-full px-2 py-2.5 border border-gray-300 rounded-xl bg-white outline-none focus:ring-2 focus:ring-indigo-500"
      },
      /* @__PURE__ */ React.createElement("option", { value: "" }, "未指定"),
      teachableMembers.map((m) => /* @__PURE__ */ React.createElement("option", { key: m.user_id, value: m.user_id }, m.full_name))
    ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400 mt-1" }, "指定后，同一位老师同时段被排两处会提示冲突。")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "地点 / 教室", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "（选填）")), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: schedEdit.room || "",
        onChange: (e) => setSchedEdit((p) => ({ ...p, room: e.target.value })),
        placeholder: "如：A 教室",
        className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    ))), /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-2.5 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2.5 min-h-[44px] cursor-pointer" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        checked: !!schedEdit.isPublic,
        onChange: (e) => setSchedEdit((p) => ({ ...p, isPublic: e.target.checked })),
        className: "mt-0.5 w-4 h-4 accent-indigo-600"
      }
    ), /* @__PURE__ */ React.createElement("span", { className: "flex-1" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-700" }, "在公开课表上展示这个班次"), /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-400 mt-0.5" }, "默认不展示。一对一时段、内部补课、留给特定家庭的试听位不应该出现在公网上。", schedEdit.teacherUserId && (() => {
      const m = teachableMembers.find((x) => x.user_id === schedEdit.teacherUserId);
      return m && !m.show_on_public_timetable ? /* @__PURE__ */ React.createElement("span", { className: "block text-amber-600 mt-0.5" }, m.full_name, " 尚未同意在公开课表显示姓名，课表会照常展示但不带老师。可在「设置 · 团队与权限」里逐人开启。") : null;
    })()))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, `班次学员（${schedEdit.studentIds.length} 人）`), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-1.5 mb-2" }, schedEdit.studentIds.map((id) => {
      const s = db.students.find((x) => x.id === id);
      return s ? /* @__PURE__ */ React.createElement("span", { key: id, className: "inline-flex items-center gap-1 bg-indigo-50 border border-indigo-200 text-indigo-700 rounded-full px-2.5 py-1 text-xs font-bold" }, s.name, /* @__PURE__ */ React.createElement("button", { onClick: () => setSchedEdit((p) => ({ ...p, studentIds: p.studentIds.filter((x) => x !== id) })), "aria-label": "移出", className: "text-indigo-400 active:text-red-500 p-1 -m-1 inline-flex items-center justify-center" }, /* @__PURE__ */ React.createElement(Icon, { name: "close", className: "w-3 h-3" }))) : null;
    })), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ.filter((s) => !schedEdit.studentIds.includes(s.id)), value: schedPick, onChange: setSchedPick, placeholder: "搜索并添加学员..." })), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          if (!schedPick) return;
          if (schedEdit.studentIds.includes(schedPick)) {
            showToast("该学员已在本班次中", "warn");
            setSchedPick(null);
            return;
          }
          const other = schedules.find((sc) => sc.id !== schedEdit.id && schedOverlap(sc, schedEdit) && sc.students.some((st) => st.id === schedPick));
          if (other) showToast(`注意：该学员同时段已在「${other.label}」，已加入但请确认不冲突`, "warn");
          setSchedEdit((p) => ({ ...p, studentIds: [...p.studentIds, schedPick] }));
          setSchedPick(null);
        },
        disabled: !schedPick,
        className: "bg-indigo-50 text-indigo-700 border border-indigo-200 active:bg-indigo-100 disabled:opacity-40 px-4 py-2.5 rounded-xl text-xs font-bold"
      },
      "加入班次"
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 justify-end" }, /* @__PURE__ */ React.createElement("button", { onClick: () => setSchedEdit(null), className: "bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50" }, "取消"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: saveSchedule,
        disabled: busy,
        className: "bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold"
      },
      schedEdit.id ? "保存修改" : "创建班次"
    ))), schedCancel && /* @__PURE__ */ React.createElement("div", { className: "border-t border-gray-100 pt-3 space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-gray-800" }, "标记停课 · ", schedCancel.label), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "停课日期"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        value: schedCancel.date,
        onChange: (e) => setSchedCancel((p) => ({ ...p, date: e.target.value })),
        className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400 mt-1" }, "必须落在这个班次上课的那一天，默认已填好下一次。")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "原因", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "（选填，会显示给家长）")), /* @__PURE__ */ React.createElement(
      "input",
      {
        value: schedCancel.note,
        onChange: (e) => setSchedCancel((p) => ({ ...p, note: e.target.value })),
        placeholder: "如：公众假期 / 老师培训",
        className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl outline-none focus:ring-2 focus:ring-indigo-500"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 justify-end" }, /* @__PURE__ */ React.createElement("button", { onClick: () => setSchedCancel(null), className: "bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50" }, "取消"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: saveCancellation,
        disabled: busy,
        className: "bg-amber-600 active:bg-amber-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold"
      },
      "标记停课"
    )))))));
  }

  // legacy-root/src/panels/media.jsx
  function WorksSection(props) {
    const {
      canWritePortfolio,
      portfolioEntries,
      setEditP,
      setPortUpload,
      setSelS,
      setStudentProfileTab,
      setTab,
      setWorksBucket,
      setWorksQuery,
      worksBucket,
      worksBuckets,
      worksQuery,
      worksVisible
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-5 max-w-6xl mx-auto" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-2 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-5 h-5" }), "作品管理"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, "从这里按学员浏览作品；具体上传、编辑和公开授权仍在学员档案中完成。")), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => setTab("students"), className: "min-h-[44px] px-4 rounded-xl border border-indigo-200 bg-indigo-50 text-indigo-700 text-sm font-bold" }, "进入学员档案 →")), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, [["作品总数", portfolioEntries.length, "text-gray-900"], ["已公开", portfolioEntries.filter(({ item }) => item.public || item.visibility === "shared").length, "text-emerald-700"], ["待授权", portfolioEntries.filter(({ student }) => student.publicationConsent?.status !== "confirmed").length, "text-amber-700"], ["有作品学员", new Set(portfolioEntries.map(({ student }) => student.id)).size, "text-indigo-700"]].map(([label, value, color]) => /* @__PURE__ */ React.createElement("div", { key: label, className: "bg-white rounded-2xl border border-gray-100 shadow-sm p-4" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, label), /* @__PURE__ */ React.createElement("p", { className: `text-2xl font-bold mt-1 ${color}` }, value)))), /* @__PURE__ */ React.createElement(
      FilterBar,
      {
        query: worksQuery,
        onQuery: setWorksQuery,
        searchPlaceholder: "搜学员姓名或作品说明",
        buckets: worksBuckets,
        bucket: worksBucket,
        onBucket: setWorksBucket,
        total: worksVisible.length,
        totalNoun: "件"
      }
    ), /* @__PURE__ */ React.createElement("section", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-5", "aria-labelledby": "works-list-title" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-3 mb-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h3", { id: "works-list-title", className: "font-bold text-gray-900" }, "最近作品"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "按作品日期倒序 · 最多显示最近 50 件")), /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold text-gray-500" }, worksVisible.length, " 件")), !portfolioEntries.length ? /* @__PURE__ */ React.createElement(EmptyState, { icon: /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-8 h-8" }), main: "还没有作品", sub: "打开学员档案后，在作品区上传第一件作品。", action: "查看学员", onAction: () => setTab("students") }) : !worksVisible.length ? /* @__PURE__ */ React.createElement(EmptyState, { icon: /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-8 h-8" }), main: "没有符合筛选的作品", sub: "换一个分类，或清空搜索词。" }) : /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3" }, worksVisible.slice(0, 50).map(({ student, item }) => {
      const shared = item.public || item.visibility === "shared";
      return /* @__PURE__ */ React.createElement("article", { key: `${student.id}-${item.id || item.filename || item.date}`, className: "overflow-hidden rounded-2xl border border-gray-200 bg-gray-50" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => {
        setTab("students", { recordId: student.id });
        setSelS(student);
        setEditP(false);
        setTimeout(() => setStudentProfileTab("portfolio"), 0);
      }, className: "block w-full text-left focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500" }, /* @__PURE__ */ React.createElement("div", { className: "aspect-[4/3] bg-gray-100 overflow-hidden" }, item.filename ? /* @__PURE__ */ React.createElement("img", { src: portfolioThumbSrc(student.id, item), loading: "lazy", alt: `${student.name} 的作品`, className: "w-full h-full object-cover" }) : /* @__PURE__ */ React.createElement("div", { className: "w-full h-full inline-flex items-center justify-center text-gray-300" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-10 h-10" }))), /* @__PURE__ */ React.createElement("div", { className: "p-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between gap-2" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-900 truncate" }, item.title || item.note || "未命名作品"), /* @__PURE__ */ React.createElement("span", { className: `flex-shrink-0 text-[11px] font-bold px-2 py-0.5 rounded-full border ${shared ? "bg-emerald-50 border-emerald-200 text-emerald-700" : "bg-gray-100 border-gray-200 text-gray-500"}` }, shared ? "已公开" : "未公开")), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1 truncate" }, student.name, " · ", fmtDate(item.date)), item.note && item.title && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-1 line-clamp-2" }, item.note))), canWritePortfolio && /* @__PURE__ */ React.createElement("div", { className: "px-3 pb-3" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => {
        setTab("students", { recordId: student.id });
        setSelS(student);
        setEditP(false);
        setTimeout(() => {
          setStudentProfileTab("portfolio");
          setPortUpload(true);
        }, 0);
      }, className: "w-full min-h-[44px] rounded-xl border border-indigo-200 bg-white text-xs font-bold text-indigo-700 hover:bg-indigo-50" }, "在该学员下继续上传")));
    }))));
  }

  // legacy-root/src/panels/students.jsx
  function StudentsSection(props) {
    const {
      archiveSelected,
      busy,
      canManageOperations,
      canWriteAttendance,
      canWriteCredits,
      canWriteStudents,
      copySelectedReminders,
      copyText,
      exportStudentsCSV,
      filterBy,
      getTag,
      isStudentScheduledOn,
      pageStudents,
      preferenceRows,
      renderMessage,
      renewTh,
      scheduleStudentToday,
      selectedStudentIds,
      selectedStudents,
      setEditP,
      setFilterBy,
      setSelS,
      setSelectedStudentIds,
      setSortBy,
      setSrch,
      setStudentPage,
      setTab,
      setTuStu,
      sortBy,
      sortedFiltered,
      srch,
      studentPage,
      studentPageCount,
      toggleSelectPage,
      toggleSelectStudent
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden text-xl font-bold text-gray-800" }, `学员档案 (${sortedFiltered.length})`), /* @__PURE__ */ React.createElement("p", { className: "hidden md:block text-sm font-bold text-gray-500" }, `共 ${sortedFiltered.length} 人`), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, canManageOperations && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportStudentsCSV,
        className: "inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-4 py-2.5 rounded-xl font-bold text-sm min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }),
      "CSV"
    ), canWriteStudents && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setTab("new_student"),
        className: "inline-flex items-center gap-1.5 bg-indigo-600 active:bg-indigo-700 text-white px-5 py-2.5 rounded-xl font-bold text-sm shadow-md min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-4 h-4" }),
      "新建"
    ))), /* @__PURE__ */ React.createElement(
      FilterBar,
      {
        total: sortedFiltered.length,
        totalNoun: "人",
        extraDirty: Boolean(filterBy !== "all" || srch),
        onClearExtra: () => {
          setFilterBy("all");
          setSrch("");
        },
        extra: /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "relative" }, /* @__PURE__ */ React.createElement("span", { className: "absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none" }, /* @__PURE__ */ React.createElement(Icon, { name: "search" })), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "text",
            placeholder: "搜索姓名 / 电话 / 微信 / 邮箱…（回车打开唯一匹配）",
            value: srch,
            onChange: (e) => setSrch(e.target.value),
            onKeyDown: (e) => {
              if (e.key === "Enter" && sortedFiltered.length === 1) {
                setSelS(sortedFiltered[0]);
                setEditP(false);
              }
            },
            "aria-label": "搜索学员",
            className: "w-full pl-10 pr-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
          }
        )), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto -mx-1 px-1 pb-1" }, /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 items-center", style: { minWidth: "max-content" } }, /* @__PURE__ */ React.createElement(
          "select",
          {
            value: sortBy,
            onChange: (e) => setSortBy(e.target.value),
            className: "px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none font-medium text-sm min-h-[44px] flex-shrink-0"
          },
          /* @__PURE__ */ React.createElement("option", { value: "name-az" }, "名 A→Z"),
          /* @__PURE__ */ React.createElement("option", { value: "name-za" }, "名 Z→A"),
          /* @__PURE__ */ React.createElement("option", { value: "last-az" }, "姓 A→Z"),
          /* @__PURE__ */ React.createElement("option", { value: "last-za" }, "姓 Z→A"),
          /* @__PURE__ */ React.createElement("option", { value: "bal-desc" }, "课时 高→低"),
          /* @__PURE__ */ React.createElement("option", { value: "bal-asc" }, "课时 低→高"),
          /* @__PURE__ */ React.createElement("option", { value: "date-desc" }, "最近活跃")
        ), [["all", "全部"], ["active", "有余额"], ["low", `低余额≤${renewTh}`], ["zero", "已清零"], ["archived", "归档库"], ["tag-hot", "活跃"], ["tag-low", "低频"], ["tag-risk", "流失风险"], ["portal-ready", "专区已就绪"], ["portal-missing-mobile", "缺手机号"], ["portal-disabled", "专区未启用"], ["portal-content-blocked", "私人内容受阻"], ["publication-live", "作品已公开"], ["publication-ready", "公开授权有效"], ["publication-missing-consent", "缺公开授权"]].map(([v, l]) => /* @__PURE__ */ React.createElement(
          "button",
          {
            key: v,
            onClick: () => setFilterBy(v),
            className: `px-4 py-2 rounded-xl text-xs font-bold border min-h-[44px] transition flex-shrink-0 ${filterBy === v ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-300 active:border-indigo-300"}`
          },
          l,
          filterBy === v ? ` · ${sortedFiltered.length}` : ""
        )))))
      }
    ), selectedStudents.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-indigo-50 border border-indigo-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-indigo-700" }, `已选择 ${selectedStudents.length} 人`), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSelectedStudentIds([]),
        className: "bg-white border border-indigo-200 text-indigo-700 px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]"
      },
      "清除选择"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: copySelectedReminders,
        className: "bg-indigo-600 active:bg-indigo-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]"
      },
      "复制续课提醒"
    ), canManageOperations && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: archiveSelected,
        disabled: busy,
        className: "bg-gray-700 active:bg-gray-800 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px] disabled:bg-gray-300"
      },
      "批量归档"
    ))), canWriteCredits && filterBy === "low" && sortedFiltered.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-orange-50 border border-orange-200 rounded-2xl p-4 flex items-center justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-orange-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "bolt", className: "w-4 h-4" }), "待续课学员 ", sortedFiltered.length, " 人（余额 ≤", renewTh, " 节）"), /* @__PURE__ */ React.createElement("button", { onClick: () => {
      const lines = sortedFiltered.map((s) => renderMessage(
        "renewal",
        "{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。",
        { student: s.name, balance: s.balance, note: "" }
      ));
      copyText(lines.join("\n\n"), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
    }, className: "bg-orange-600 active:bg-orange-700 text-white px-4 py-2 rounded-xl text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "clipboard", className: "w-4 h-4" }), "复制全部提醒话术"))), !sortedFiltered.length && /* @__PURE__ */ React.createElement(
      EmptyState,
      {
        icon: /* @__PURE__ */ React.createElement(Icon, { name: "search", className: "w-8 h-8" }),
        main: "没有符合条件的学员",
        sub: srch ? `没有姓名、电话、微信或邮箱包含「${srch}」的学员。换个关键词，或清空搜索看全部。` : "当前筛选条件下没有学员。点下方按钮回到全部名单。",
        action: srch ? "清空搜索" : "查看全部学员",
        onAction: () => {
          setSrch("");
          setFilterBy("all");
        }
      }
    ), sortedFiltered.length > 0 && /* @__PURE__ */ React.createElement("label", { className: "flex items-center gap-2 text-xs font-bold text-gray-500 px-1" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        className: "w-4 h-4",
        checked: pageStudents.length > 0 && pageStudents.every((item) => selectedStudentIds.includes(item.id)),
        onChange: (e) => toggleSelectPage(e.target.checked)
      }
    ), `选择本页 ${pageStudents.length} 人`), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3" }, pageStudents.map((s) => /* @__PURE__ */ React.createElement("div", { key: s.id, className: `bg-white rounded-2xl p-4 shadow-sm border hover-row transition flex flex-col justify-between print-card ${selectedStudentIds.includes(s.id) ? "ring-2 ring-indigo-400 border-indigo-200" : s.archived ? "border-gray-200 opacity-70" : parseInt(s.balance, 10) === 0 ? "border-red-100" : parseInt(s.balance, 10) <= 2 ? "border-orange-100" : "border-gray-100"}` }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-start mb-2 gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2.5 min-w-0" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        className: "w-4 h-4 flex-shrink-0",
        "aria-label": `选择 ${s.name}`,
        checked: selectedStudentIds.includes(s.id),
        onChange: () => toggleSelectStudent(s.id)
      }
    ), /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }), /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800 break-words leading-snug" }, s.name), s.archived && /* @__PURE__ */ React.createElement("span", { className: "text-xs bg-gray-100 text-gray-500 px-1.5 rounded mt-0.5 inline-block" }, "归档"))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-col items-end gap-1 flex-shrink-0" }, /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }), (() => {
      const t = getTag(s);
      return t ? /* @__PURE__ */ React.createElement("span", { className: `inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-bold ${t.cls}` }, /* @__PURE__ */ React.createElement(Icon, { name: t.icon, className: "w-3 h-3" }), t.label) : null;
    })())), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-4 h-4" }), " ", s.mobile || "—"), s.email && /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "mail", className: "w-4 h-4" }), " ", s.email), preferenceRows(s).slice(0, 1).map((row) => /* @__PURE__ */ React.createElement("p", { key: row.key, className: "text-gray-400 text-sm" }, row.label, "：", row.value)), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mt-0.5 flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), " ", fmtDate(s.lastActive), daysSince(s.lastActive) < 9999 ? ` · ${daysSince(s.lastActive)}天前` : "")), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 mt-3" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setSelS(s);
          setEditP(false);
        },
        className: "flex-1 bg-gray-50 active:bg-gray-100 border border-gray-200 text-gray-700 py-3 rounded-xl text-sm font-bold min-h-[44px]"
      },
      "详情"
    ), !s.archived && /* @__PURE__ */ React.createElement(React.Fragment, null, canWriteCredits && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setTuStu(s.id);
          setTab("topup");
        },
        title: "快速充值",
        "aria-label": "快速充值",
        className: "px-3.5 py-3 rounded-xl font-bold bg-emerald-50 active:bg-emerald-100 text-emerald-700 border border-emerald-200 min-h-[44px] flex items-center justify-center"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "money" })
    ), canWriteAttendance && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => scheduleStudentToday(s),
        disabled: busy,
        className: "flex-1 py-3 rounded-xl text-sm font-bold text-white min-h-[44px] bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 inline-flex items-center justify-center gap-1.5"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }),
      isStudentScheduledOn(s.id, todayISO()) ? "查看排课" : "加入排课"
    )))))), studentPageCount > 1 && /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-center gap-3 pt-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setStudentPage((p) => Math.max(1, p - 1)),
        disabled: studentPage <= 1,
        className: "px-4 py-2 rounded-xl text-sm font-bold border border-gray-300 bg-white disabled:opacity-40 min-h-[44px]"
      },
      "上一页"
    ), /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-500 font-bold" }, `第 ${studentPage} / ${studentPageCount} 页`), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setStudentPage((p) => Math.min(studentPageCount, p + 1)),
        disabled: studentPage >= studentPageCount,
        className: "px-4 py-2 rounded-xl text-sm font-bold border border-gray-300 bg-white disabled:opacity-40 min-h-[44px]"
      },
      "下一页"
    )), sortedFiltered.length > 15 && /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          const m = document.querySelector("main");
          if (m) m.scrollTo({ top: 0, behavior: "smooth" });
          else window.scrollTo({ top: 0, behavior: "smooth" });
        },
        className: "fixed bottom-24 right-4 md:bottom-8 z-40 w-11 h-11 bg-indigo-600 active:bg-indigo-700 text-white rounded-full shadow-lg flex items-center justify-center text-lg",
        title: "回到顶部",
        "aria-label": "回到顶部"
      },
      "↑"
    ));
  }
  function NewStudentSection(props) {
    const {
      busy,
      formPhoto,
      handleAddStudent,
      notify,
      preferenceProfile,
      setFormPhoto,
      setTab
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim bg-white rounded-2xl p-6 max-w-xl mx-auto shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-2 text-xl font-bold mb-5 text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-5 h-5" }), "新建学员档案"), /* @__PURE__ */ React.createElement("form", { onSubmit: handleAddStudent, className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-2 block" }, "照片 Photo ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(PhotoUploader, { value: formPhoto, onChange: setFormPhoto, notify })), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "First Name (名) *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        required: true,
        name: "firstName",
        placeholder: "如 Holly",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "Last Name (姓) ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "lastName",
        placeholder: "如 Chen",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "电话"), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "mobile",
        placeholder: "04xx xxx xxx",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "初始课时"), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "balance",
        type: "number",
        min: "0",
        defaultValue: "0",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "微信号 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "wechat",
        placeholder: "如 wechat_id",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "邮箱 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: "email",
        type: "email",
        placeholder: "example@email.com",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("details", { className: "border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100" }, preferenceProfile().title, " ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填 / Optional")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, preferenceProfile().fields.map((field) => /* @__PURE__ */ React.createElement("div", { key: field.key }, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, field.label), /* @__PURE__ */ React.createElement(
      "input",
      {
        name: `pref_${field.key}`,
        placeholder: field.placeholder,
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "生日 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        name: "birthday",
        min: "1920-01-01",
        max: "2099-12-31",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "入学日期"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "date",
        name: "enrollmentDate",
        defaultValue: todayISO(),
        min: "1900-01-01",
        max: todayISO(),
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "备注"), /* @__PURE__ */ React.createElement(
      "textarea",
      {
        name: "remark",
        rows: "3",
        placeholder: "备注信息...",
        className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
      }
    )), /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 pt-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "submit",
        disabled: busy,
        className: "flex-1 bg-indigo-600 active:bg-indigo-700 text-white py-3.5 rounded-xl font-bold text-sm shadow-md min-h-[52px]"
      },
      "确认建档"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "button",
        onClick: () => {
          setTab("students");
          setFormPhoto("");
        },
        className: "px-6 py-3.5 bg-gray-100 active:bg-gray-200 text-gray-700 rounded-xl font-bold text-sm min-h-[52px]"
      },
      "取消"
    ))));
  }
  function PendingSection(props) {
    const {
      advanceRegistration,
      approveCredits,
      approveStudent,
      approveTenant,
      bookings,
      busy,
      canReviewBookings,
      db,
      dupPick,
      followUpDates,
      pendingCount,
      pendingTab,
      preferenceRows,
      rejectStudent,
      reviewBooking,
      setApproveCredits,
      setDupPick,
      setFollowUpDates,
      setPendingTab,
      setTab,
      showToast
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "clipboard", className: "w-4 h-4" }), "待处理"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, "新报名和约课申请共用一个收件箱，按业务类型分开处理。")), /* @__PURE__ */ React.createElement("span", { className: "rounded-full bg-amber-50 border border-amber-200 px-3 py-1 text-xs font-bold text-amber-700" }, pendingCount, " 项等待处理")), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, [
      ["registrations", "新报名", (db.pending || []).length],
      ["bookings", "约课", bookings.length],
      ["reports", "成长报告", ""]
    ].map(([key, label, count]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key,
        onClick: () => setPendingTab(key),
        className: `px-4 py-2 rounded-xl text-sm font-bold min-h-[44px] border ${pendingTab === key ? "bg-indigo-600 text-white border-indigo-600" : "bg-white text-gray-600 border-gray-200 active:bg-gray-50"}`
      },
      label,
      " ",
      count
    ))), pendingTab === "reports" && /* @__PURE__ */ React.createElement(
      OverdueReports,
      {
        api: v1Api,
        showToast,
        onOpenStudent: (id) => setTab("students", { recordId: id })
      }
    ), pendingTab === "bookings" && /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, !bookings.length && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-600" }, "没有待处理的约课申请"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400 mt-1 max-w-sm mx-auto leading-relaxed" }, "在 Studio Admin 的「Timetable」里打开公开课表并允许约课后，家长可以在课表页留下姓名和手机号申请上课，申请会出现在这里。")), bookings.map((bk) => /* @__PURE__ */ React.createElement("div", { key: bk.id, className: "bg-white rounded-2xl shadow-sm border border-amber-200 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3 flex-wrap" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-base font-bold text-gray-800" }, bk.contactName, bk.isExistingStudent ? /* @__PURE__ */ React.createElement("span", { className: "ml-2 align-middle inline-block text-[10px] font-bold bg-green-100 text-green-700 border border-green-300 rounded-full px-2 py-0.5" }, "已是学员", bk.matchedStudent ? ` · ${bk.matchedStudent}` : "") : /* @__PURE__ */ React.createElement("span", { className: "ml-2 align-middle inline-block text-[10px] font-bold bg-gray-100 text-gray-600 border border-gray-300 rounded-full px-2 py-0.5" }, "新访客")), /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm text-gray-500" }, /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-4 h-4" }), bk.contactPhone), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-600 mt-1" }, bk.date, " ", bk.startTime, " · ", bk.title || "未命名班次"), bk.message && /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1 whitespace-pre-wrap" }, bk.message)), /* @__PURE__ */ React.createElement("div", { className: "text-right flex-shrink-0" }, /* @__PURE__ */ React.createElement("p", { className: `text-xs font-bold ${bk.seatsLeft === 0 ? "text-gray-500" : "text-green-700"}` }, bk.seatsLeft === 0 ? "已满" : `还有 ${bk.seatsLeft} 位`), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "容量 ", bk.capacity))), bk.seatsLeft === 0 && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-xl px-3 py-2" }, "这节课已经满了。批准会被拒绝——先提高班次容量，或婉拒并联系家长改约。"), canReviewBookings && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 justify-end" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => reviewBooking(bk, "declined"),
        disabled: busy,
        className: "bg-white border border-gray-300 text-gray-600 px-4 py-2 rounded-xl text-sm font-bold active:bg-gray-50 min-h-[44px]"
      },
      "婉拒"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => reviewBooking(bk, "approved"),
        disabled: busy,
        className: "bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 text-white px-5 py-2 rounded-xl text-sm font-bold min-h-[44px]"
      },
      bk.isExistingStudent ? "批准并排课" : "批准并转报名"
    ))))), pendingTab === "registrations" && /* @__PURE__ */ React.createElement(React.Fragment, null, !(db.pending || []).length && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-10 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-4xl mb-3" }, /* @__PURE__ */ React.createElement(Icon, { name: "check", className: "w-4 h-4" })), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-600" }, "没有待审核的报名"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-400 mt-1 max-w-sm mx-auto leading-relaxed" }, "家长在官网或报名页提交后，申请会出现在这里等你批准。把报名页链接发出去就能开始收。")), (db.pending || []).map((pen) => {
      const fullName = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
      const normP = (p) => (p || "").replace(/[\s\-\(\)]+/g, "");
      const penMobile = normP(pen.mobile);
      const isDupPending = !!penMobile && (db.pending || []).some((o) => o.id !== pen.id && normP(o.mobile) === penMobile);
      return /* @__PURE__ */ React.createElement("div", { key: pen.id, className: "bg-white rounded-2xl shadow-sm border border-amber-200 p-5 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start gap-4" }, pen.photo ? /* @__PURE__ */ React.createElement("img", { src: mediaSrc(pen.photo), className: "w-16 h-16 rounded-full object-cover flex-shrink-0 border-2 border-indigo-100", alt: fullName }) : /* @__PURE__ */ React.createElement("div", { className: "w-16 h-16 rounded-full bg-indigo-100 flex items-center justify-center text-2xl font-bold text-indigo-600 flex-shrink-0" }, (pen.firstName || "?")[0].toUpperCase()), /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-lg font-bold text-gray-800" }, fullName, isDupPending && /* @__PURE__ */ React.createElement("span", { className: "ml-2 align-middle inline-block text-[10px] font-bold bg-amber-100 text-amber-700 border border-amber-300 rounded-full px-2 py-0.5", title: "另有一条待审核申请使用相同手机号" }, "疑似重复")), /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm text-gray-500" }, /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-4 h-4" }), pen.mobile || "—", pen.wechat ? ` · ${pen.wechat}` : "", pen.email ? ` · ${pen.email}` : ""), pen.birthday && /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-pink-500 mt-0.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "cake", className: "w-4 h-4" }), fmtDate(pen.birthday)), pen.mobile && (() => {
        const match = db.students.filter((s) => !s.archived && normP(s.mobile) === normP(pen.mobile));
        return match.length > 0 ? /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-blue-500 mt-0.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "device", className: "w-4 h-4" }), "此电话已有学员：", match.map((s) => s.firstName && s.lastName ? `${s.firstName} ${s.lastName}` : s.name || "").join("、")) : null;
      })(), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "提交时间: ", /* @__PURE__ */ React.createElement("span", { title: pen.submittedAt || "" }, fmtDT(pen.submittedAt)), " · 来源: ", pen.source === "portal" ? "门户网站" : "快速报名", " · 状态: ", REG_STATUS_ZH[pen.status || "pending"] || pen.status))), preferenceRows(pen).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2 text-sm" }, preferenceRows(pen).map((row) => /* @__PURE__ */ React.createElement("div", { key: row.key, className: "bg-gray-50 rounded-2xl p-4 border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, row.label), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, row.value)))), pen.message && /* @__PURE__ */ React.createElement("div", { className: "bg-amber-50 border border-amber-200 rounded-2xl p-4 text-sm text-gray-700" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-amber-500 font-bold mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "留言"), /* @__PURE__ */ React.createElement("p", null, pen.message)), /* @__PURE__ */ React.createElement("div", { className: "bg-blue-50 border border-blue-100 rounded-2xl p-3 flex flex-wrap items-end gap-2" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-blue-700 mb-1 block" }, "下次跟进"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "date",
          value: followUpDates[pen.id] || "",
          onChange: (e) => setFollowUpDates((p) => ({ ...p, [pen.id]: e.target.value })),
          className: "px-3 py-2 border border-blue-200 rounded-xl text-sm"
        }
      )), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => advanceRegistration(pen.id, "contacted"),
          disabled: busy,
          className: "px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm"
        },
        "已联系"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => advanceRegistration(pen.id, "trial_booked"),
          disabled: busy,
          className: "px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm"
        },
        "已约试听"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => advanceRegistration(pen.id, "waiting"),
          disabled: busy,
          className: "px-3 py-2 bg-white border border-blue-200 text-blue-700 font-bold rounded-xl text-sm"
        },
        "继续跟进"
      )), /* @__PURE__ */ React.createElement("div", { className: "flex items-end gap-3 pt-2 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-500 mb-1 block" }, "初始课时数"), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "number",
          min: "0",
          placeholder: "0",
          value: approveCredits[pen.id] ?? "",
          onChange: (e) => setApproveCredits((p) => ({ ...p, [pen.id]: e.target.value })),
          className: "w-full px-3 py-2.5 border border-gray-300 rounded-xl font-bold text-xl focus:ring-2 focus:ring-indigo-500 outline-none text-indigo-700"
        }
      )), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-shrink-0" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => rejectStudent(pen.id),
          disabled: busy,
          className: "inline-flex items-center justify-center gap-1.5 px-4 py-2.5 bg-red-50 active:bg-red-100 text-red-700 border border-red-200 font-bold rounded-xl text-sm min-h-[44px]"
        },
        "拒绝"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => approveStudent(pen.id),
          disabled: busy,
          className: "px-5 py-2.5 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm min-h-[44px]"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "check", className: "w-4 h-4" }), "批准建档")
      ))));
    })), dupPick && /* @__PURE__ */ React.createElement("div", { className: "fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4", role: "dialog", "aria-modal": "true" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-2xl max-w-md w-full p-5 space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-sm" }, "疑似已有档案 — ", dupPick.fullName), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, "发现下列可能是同一名学员的既有档案。并入会把这次报名归到既有学员名下（初始课时也入其账本）；确认是新学员则继续新建。不会自动合并。"), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, dupPick.candidates.map((c) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: c.studentId,
        disabled: busy,
        onClick: () => approveTenant(dupPick.pid, dupPick.fullName, dupPick.credits, c.studentId),
        className: "w-full text-left px-3 py-2.5 rounded-xl border border-indigo-200 bg-indigo-50 active:bg-indigo-100 min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-indigo-800" }, c.name),
      /* @__PURE__ */ React.createElement("span", { className: "block text-xs text-gray-500" }, [c.phone, c.email].filter(Boolean).join(" · "), c.matchedOn?.length ? ` · 命中：${c.matchedOn.join("/")}` : ""),
      /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-bold text-indigo-600 mt-0.5" }, "并入这个档案 →")
    ))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 pt-1" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setDupPick(null),
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl border border-gray-200 text-xs font-bold"
      },
      "取消"
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => approveTenant(dupPick.pid, dupPick.fullName, dupPick.credits, null),
        disabled: busy,
        className: "flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold"
      },
      "确认是新学员，新建档案"
    )))));
  }

  // legacy-root/src/panels/topup.jsx
  function TopupSection(props) {
    const {
      archivePackage,
      busy,
      canManageOperations,
      canRefund,
      canRegisterSettlementPayment,
      canSyncRefund,
      canUseSettlementBilling,
      db,
      handleRefund,
      handleTopUp,
      pkgCredits,
      pkgEditId,
      pkgName,
      pkgPrice,
      refundSourceError,
      refundSources,
      refundSourcesBusy,
      resetPackageEditor,
      rfAdjustDocuments,
      rfAmountTouched,
      rfAmt,
      rfCr,
      rfReason,
      rfSourceId,
      savePackage,
      setPkgCredits,
      setPkgEditId,
      setPkgName,
      setPkgPrice,
      setRfAdjustDocuments,
      setRfAmountTouched,
      setRfAmt,
      setRfCr,
      setRfReason,
      setRfSourceId,
      setSettleMode,
      setSettlementPayer,
      setSettlementPayerError,
      setSettlementPayerState,
      setTuCr,
      setTuCreateInvoice,
      setTuFee,
      setTuPay,
      setTuPaymentReceived,
      setTuPkg,
      setTuStu,
      settleMode,
      settlementAccounts,
      settlementPayerError,
      settlementPayerIntentRef,
      settlementPayerState,
      settlementResolvedAccountRef,
      settlementTaxCodes,
      sortedAZ,
      tuCr,
      tuCreateInvoice,
      tuFee,
      tuPay,
      tuPaymentReceived,
      tuPkg,
      tuStu
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim bg-white rounded-2xl shadow-sm border border-gray-100 p-6 max-w-2xl mx-auto" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-3 mb-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "money", className: "w-4 h-4" }), "充值与退款"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-500 mt-1" }, "先选择学员，再完成充值或退款；支付渠道只记录实际收款方式，不在 CMS 内接入在线支付。"))), canManageOperations && /* @__PURE__ */ React.createElement("details", { open: true, className: "mb-5 rounded-2xl border border-indigo-100 bg-indigo-50/60 overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "cursor-pointer select-none px-4 py-3 min-h-[48px] inline-flex items-center gap-2 text-sm font-bold text-indigo-900" }, /* @__PURE__ */ React.createElement(Icon, { name: "card", className: "w-4 h-4" }), "套餐管理 ", /* @__PURE__ */ React.createElement("span", { className: "text-xs font-normal text-indigo-500" }, `${(db.packages || []).length} 个套餐`)), /* @__PURE__ */ React.createElement("div", { className: "p-4 pt-1 space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-indigo-700 leading-relaxed" }, "这里定义前台充值时可快速选择的课包。修改套餐不会改动历史充值记录；删除前请确认它不再需要被新收款使用。"), (db.packages || []).map((pkg) => /* @__PURE__ */ React.createElement("div", { key: pkg.id, className: "flex items-center gap-3 rounded-xl border border-indigo-100 bg-white px-3 py-2.5" }, /* @__PURE__ */ React.createElement("div", { className: "min-w-0 flex-1" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-gray-800 truncate" }, pkg.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-0.5" }, pkg.credits, " 课时 · AUD ", Number(pkg.price || 0).toFixed(2))), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => {
      setPkgEditId(pkg.id);
      setPkgName(pkg.name);
      setPkgCredits(String(pkg.credits));
      setPkgPrice(String(pkg.price));
    }, className: "min-h-[44px] px-3 rounded-xl text-xs font-bold text-indigo-700 hover:bg-indigo-50" }, "编辑"), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => archivePackage(pkg), "aria-label": `删除套餐 ${pkg.name}`, className: "min-h-[44px] min-w-[44px] inline-flex items-center justify-center rounded-xl text-red-600 hover:bg-red-50" }, /* @__PURE__ */ React.createElement(Icon, { name: "trash", className: "w-4 h-4" })))), pkgEditId === null && /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => {
      setPkgEditId(0);
      setPkgName("");
      setPkgCredits("");
      setPkgPrice("");
    }, className: "w-full min-h-[44px] rounded-xl border border-dashed border-indigo-300 bg-white text-indigo-700 text-xs font-bold hover:bg-indigo-50" }, /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-4 h-4 inline mr-1" }), "添加套餐"), pkgEditId !== null && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-indigo-200 bg-white p-3 space-y-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-indigo-900" }, pkgEditId === 0 ? "添加套餐" : "编辑套餐"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-3 gap-3" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "套餐名称 *", /* @__PURE__ */ React.createElement("input", { type: "text", value: pkgName, onChange: (e) => setPkgName(e.target.value), placeholder: "例如：10 课时包", className: "mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "课时数 *", /* @__PURE__ */ React.createElement("input", { type: "number", min: "1", value: pkgCredits, onChange: (e) => setPkgCredits(e.target.value), placeholder: "10", className: "mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm" })), /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "价格（AUD） *", /* @__PURE__ */ React.createElement("input", { type: "number", min: "0", step: "0.01", value: pkgPrice, onChange: (e) => setPkgPrice(e.target.value), placeholder: "500.00", className: "mt-1 w-full min-h-[44px] px-3 py-2 border border-gray-300 rounded-xl text-sm" }))), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400" }, "价格仅供内部入账和套餐快选显示；银行转账仍由工作室线下核对。"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: resetPackageEditor, className: "flex-1 min-h-[44px] rounded-xl border border-gray-300 text-xs font-bold text-gray-600" }, "取消"), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: savePackage, disabled: busy, className: "flex-1 min-h-[44px] rounded-xl bg-indigo-600 text-white text-xs font-bold disabled:opacity-50" }, busy ? "保存中…" : "保存套餐"))))), TENANT_SLUG && canRefund && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 mb-5" }, [["topup", "充值"], ["refund", "退款退课"]].map(([m, l]) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: m,
        type: "button",
        onClick: () => setSettleMode(m),
        className: `flex-1 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${settleMode === m ? m === "refund" ? "border-red-400 bg-red-50 text-red-700" : "border-indigo-500 bg-indigo-100 text-indigo-900" : "border-gray-200 bg-white text-gray-500 active:border-indigo-300"}`
      },
      l
    ))), /* @__PURE__ */ React.createElement("form", { onSubmit: settleMode === "refund" ? handleRefund : handleTopUp, className: "space-y-5" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "选择学员"), /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: tuStu, onChange: (next) => {
      setTuStu(next);
      setSettlementPayerState({ mode: "student", accountId: "", createPayload: null, linkedStudentIds: next ? [next] : [] });
      settlementResolvedAccountRef.current = "";
      settlementPayerIntentRef.current = "";
    }, placeholder: "搜索学员姓名..." }), tuStu && (() => {
      const s = db.students.find((x) => x.id === tuStu);
      return s ? /* @__PURE__ */ React.createElement("div", { className: "mt-2 flex items-center gap-3 bg-indigo-50 border border-indigo-100 rounded-xl px-4 py-3" }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }), /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 text-sm truncate" }, s.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, s.mobile || "—", s.wechat ? ` · ${s.wechat}` : "")), /* @__PURE__ */ React.createElement("div", { className: "text-right flex-shrink-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "当前余额"), /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }))) : null;
    })(), tuStu && (() => {
      const s = db.students.find((x) => x.id === tuStu);
      const recent = !s ? [] : db.logs.filter((l) => (l.studentId === s.id || !l.studentId && l.studentName === s.name) && (l.action === "充值购课" || l.action === "退款退课")).slice(0, 3);
      if (!recent.length) return null;
      return /* @__PURE__ */ React.createElement("div", { className: "mt-2 border border-gray-100 rounded-xl divide-y divide-gray-50 text-xs" }, recent.map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "flex items-center justify-between px-3 py-2" }, /* @__PURE__ */ React.createElement("span", { className: l.action === "退款退课" ? "text-red-500 font-bold" : "text-gray-600 font-bold" }, l.action), /* @__PURE__ */ React.createElement("span", { className: `font-bold ${l.action === "退款退课" ? "text-red-500" : "text-gray-700"}` }, String(l.change), " 课时 · $", l.feePaid || 0), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400" }, String(l.date).split(",")[0]))));
    })()), settleMode === "refund" ? /* @__PURE__ */ React.createElement("div", { className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "rounded-2xl border border-red-100 bg-red-50/50 p-3 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-red-900" }, "先选择原充值"), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-red-700" }, "退款必须从一笔明确的 purchase 开始；系统不会按学员余额猜来源。"), refundSourcesBusy && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, "正在加载可退充值…"), refundSourceError && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600", role: "alert" }, refundSourceError), !refundSourcesBusy && !refundSources.filter((source) => Number(source.availableCredits || 0) > 0).length && !refundSourceError && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500" }, "没有剩余课时可退的原充值。已全部退完的来源会保留在账本中，但不会再出现在可选列表。"), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, refundSources.filter((source) => Number(source.availableCredits || 0) > 0).map((source) => {
      const selected = String(source.sourceTransactionId) === String(rfSourceId);
      return /* @__PURE__ */ React.createElement(
        "button",
        {
          key: source.sourceTransactionId,
          type: "button",
          onClick: () => {
            setRfSourceId(String(source.sourceTransactionId));
            setRfCr(String(source.availableCredits || ""));
            setRfAmt((Number(source.availableAmountCents || 0) / 100).toFixed(2));
            setRfAmountTouched(false);
            setRfAdjustDocuments(Boolean(source.syncAvailable && canSyncRefund));
          },
          className: `w-full text-left rounded-xl border p-3 min-h-[68px] ${selected ? "border-red-400 bg-white ring-2 ring-red-100" : "border-gray-200 bg-white"}`
        },
        /* @__PURE__ */ React.createElement("div", { className: "flex items-start gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-bold text-gray-800 truncate" }, source.invoiceNumber || "Credits-only purchase", " · ", source.purchasedCredits, " 课时"), /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-500 mt-1" }, "剩余 ", source.availableCredits, " 节 · 可退 $", (Number(source.availableAmountCents || 0) / 100).toFixed(2), " · 已退 ", source.refundCount, " 次")), /* @__PURE__ */ React.createElement("span", { className: `text-[10px] font-bold px-2 py-1 rounded-full ${source.syncAvailable ? "bg-emerald-50 text-emerald-700" : "bg-gray-100 text-gray-500"}` }, source.syncAvailable ? "可同步单据" : "无完整桥接")),
        /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-400 mt-1" }, "发票 ", source.invoiceStatus || "—", " · 付款 ", source.paymentStatus || "—")
      );
    }))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "退课节数 *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0.01",
        step: "0.01",
        required: true,
        value: rfCr,
        onChange: (e) => {
          const next = e.target.value;
          setRfCr(next);
          if (!rfAmountTouched) {
            const selectedSource = refundSources.find((item) => String(item.sourceTransactionId) === String(rfSourceId));
            const credits = Number(next || 0);
            const availableCredits = Number(selectedSource?.availableCredits || 0);
            const availableAmount = Number(selectedSource?.availableAmountCents || 0);
            if (selectedSource && availableCredits > 0) setRfAmt((availableAmount * credits / availableCredits / 100).toFixed(2));
          }
        },
        className: "w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "退款金额 (AUD) *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        min: "0",
        step: "0.01",
        required: true,
        value: rfAmt,
        onChange: (e) => {
          setRfAmountTouched(true);
          setRfAmt(e.target.value);
        },
        className: "w-full px-3 py-3 border border-red-200 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-red-400 outline-none text-red-600"
      }
    ))), (() => {
      const source = refundSources.find((item) => String(item.sourceTransactionId) === String(rfSourceId));
      const credits = Number(rfCr || 0);
      const availableCredits = Number(source?.availableCredits || 0);
      const suggested = source && availableCredits > 0 ? Math.round(Number(source.availableAmountCents || 0) * credits / availableCredits) : 0;
      const actual = Math.round((parseFloat(rfAmt) || 0) * 100);
      const variance = actual - suggested;
      return source && Number.isFinite(variance) && Math.abs(variance) > 0 ? /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2", role: "status" }, "按原充值未退比例建议退款 ", `$${(suggested / 100).toFixed(2)}`, "；当前人工金额 ", `$${(actual / 100).toFixed(2)}`, "，偏差 ", `${variance > 0 ? "+" : ""}$${(variance / 100).toFixed(2)}`, "。请确认有效单价并填写退款原因，系统不会替你猜税务决定。") : null;
    })(), (() => {
      const source = refundSources.find((item) => String(item.sourceTransactionId) === String(rfSourceId));
      return /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-2.5 min-h-[44px] rounded-xl border border-red-100 bg-white p-3 cursor-pointer" }, /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "checkbox",
          checked: rfAdjustDocuments,
          disabled: !canSyncRefund || !source?.syncAvailable,
          onChange: (event) => setRfAdjustDocuments(event.target.checked),
          className: "mt-1 w-5 h-5 accent-red-600"
        }
      ), /* @__PURE__ */ React.createElement("span", { className: "flex-1 text-sm font-bold text-red-900" }, "同步处理原发票与付款", /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] font-normal text-red-700 mt-0.5" }, !source ? "先选择一笔原充值。" : source.syncAvailable && canSyncRefund ? "将同时开具贷记单、登记付款退款并保留桥接证据。" : "没有完整 bridge，或当前角色缺少 credits:refund / payments:refund / billing:issue。")));
    })(), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "退款方式"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, ["现金", "微信", "银行转账", "其他"].map((pm) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: pm,
        type: "button",
        onClick: () => setTuPay(pm),
        className: `px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay === pm ? "border-red-400 bg-red-50 text-red-700" : "border-gray-200 bg-white text-gray-600 active:border-red-300"}`
      },
      pm
    )))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "退款原因 *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        required: true,
        value: rfReason,
        onChange: (e) => setRfReason(e.target.value),
        placeholder: "如 搬家、时间冲突、课程不合适...",
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-red-400 outline-none text-sm"
      }
    )), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 bg-red-50 border border-red-100 rounded-xl px-3 py-2" }, "勾选同步时会生成贷记单并调整付款；不勾选时只改课时账本和现金净额，不会改变发票或付款记录。所有操作都会记入账本与操作日志。")) : /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "套餐快选"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 lg:grid-cols-3 gap-2 mb-4" }, (db.packages || []).map((pkg) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: pkg.id,
        type: "button",
        onClick: () => {
          if (tuPkg === String(pkg.id)) {
            setTuCr("");
            setTuFee("");
            setTuPkg("");
          } else {
            setTuCr(String(pkg.credits));
            setTuFee(String(pkg.price));
            setTuPkg(String(pkg.id));
          }
        },
        className: `py-3 px-2 border-2 rounded-xl text-sm font-bold min-h-[50px] ${tuPkg === String(pkg.id) ? "border-indigo-500 bg-indigo-100 text-indigo-900" : "border-indigo-200 bg-indigo-50 active:bg-indigo-100 text-indigo-800"}`
      },
      pkg.name,
      /* @__PURE__ */ React.createElement("br", null),
      /* @__PURE__ */ React.createElement("span", { className: "font-normal text-xs" }, pkg.credits, "课时 · $", pkg.price)
    ))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3 mb-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "课时数 *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        name: "credits",
        min: "1",
        required: true,
        value: tuCr,
        onChange: (e) => setTuCr(e.target.value),
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none"
      }
    )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "实收金额 (AUD) *"), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "number",
        name: "fee",
        min: "0",
        step: "0.01",
        required: true,
        value: tuFee,
        onChange: (e) => setTuFee(e.target.value),
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl font-bold text-2xl focus:ring-2 focus:ring-indigo-500 outline-none text-green-700"
      }
    ))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1.5 block" }, "付款方式"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 flex-wrap" }, ["现金", "微信", "银行转账", "其他"].map((pm) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: pm,
        type: "button",
        onClick: () => setTuPay(pm),
        className: `px-5 py-2.5 rounded-xl text-sm font-bold border-2 min-h-[44px] ${tuPay === pm ? "border-indigo-500 bg-indigo-100 text-indigo-900" : "border-gray-200 bg-white text-gray-600 active:border-indigo-300"}`
      },
      pm
    )))), TENANT_SLUG && canUseSettlementBilling && /* @__PURE__ */ React.createElement("div", { className: "space-y-3 rounded-2xl border border-indigo-100 bg-indigo-50/50 p-3" }, /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-2.5 min-h-[44px] cursor-pointer" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        checked: tuCreateInvoice,
        disabled: Number(tuFee || 0) <= 0,
        onChange: (event) => setTuCreateInvoice(event.target.checked),
        className: "mt-1 w-5 h-5 accent-indigo-600"
      }
    ), /* @__PURE__ */ React.createElement("span", { className: "flex-1 text-sm font-bold text-indigo-900" }, "同时创建发票", /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] font-normal text-indigo-700 mt-0.5" }, "只有金额大于 0 才能开票；开具后金额和抬头会冻结。"))), tuCreateInvoice && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
      BillingAccountPicker,
      {
        api: v1Api,
        accounts: settlementAccounts,
        students: sortedAZ,
        studentPicker: StudentPicker,
        initialStudentId: tuStu || "",
        hideStudentSelector: true,
        value: settlementPayerState.accountId,
        onStateChange: setSettlementPayer,
        payerError: settlementPayerError,
        onPayerError: setSettlementPayerError
      }
    ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-indigo-700" }, settlementTaxCodes.length ? `税码：${(settlementTaxCodes.find((code) => code.is_default) || settlementTaxCodes[0]).code} · ${Number((settlementTaxCodes.find((code) => code.is_default) || settlementTaxCodes[0]).rate_bp || 0) / 100}%` : "当前未配置税码，发票将按 0% 税率计算。"), /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-2.5 min-h-[44px] cursor-pointer" }, /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "checkbox",
        checked: tuPaymentReceived,
        disabled: !canRegisterSettlementPayment || Number(tuFee || 0) <= 0,
        onChange: (event) => setTuPaymentReceived(event.target.checked),
        className: "mt-1 w-5 h-5 accent-indigo-600"
      }
    ), /* @__PURE__ */ React.createElement("span", { className: "flex-1 text-sm font-bold text-indigo-900" }, "款项已经收到，同时登记付款", /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] font-normal text-indigo-700 mt-0.5" }, "关闭后只开具未付款发票，不会猜测或冲销旧发票。"))))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "备注 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
      "input",
      {
        type: "text",
        name: "tuRemark",
        placeholder: "如 节假日赠课、补偿调课...",
        className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none text-sm"
      }
    ))), /* @__PURE__ */ React.createElement(
      "button",
      {
        type: "submit",
        disabled: busy || !tuStu,
        className: `w-full disabled:bg-gray-300 text-white py-4 rounded-xl font-bold text-sm shadow-xl min-h-[56px] ${settleMode === "refund" ? "bg-red-500 active:bg-red-600" : "bg-indigo-600 active:bg-indigo-700"}`
      },
      busy ? "处理中..." : settleMode === "refund" ? "确认退款退课" : "确认收款并入账"
    )));
  }

  // legacy-root/src/panels/reports.jsx
  function LogsSection(props) {
    const {
      canManageOperations,
      displayNote,
      exportLogsCSV,
      filteredLogs,
      lAct,
      lDateFrom,
      lDateTo,
      lPage,
      lSrch,
      lStu,
      logActions,
      logPageCount,
      pagedLogs,
      setLAct,
      setLDateFrom,
      setLDateTo,
      setLPage,
      setLSrch,
      setLStu,
      sortedAZ
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-4" }, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden inline-flex items-center gap-1.5 text-xl font-bold text-gray-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "scroll", className: "w-4 h-4" }), "操作日志"), /* @__PURE__ */ React.createElement(
      FilterBar,
      {
        range: { start: lDateFrom, end: lDateTo },
        onRange: (next) => {
          setLDateFrom(next.start || "");
          setLDateTo(next.end || "");
        },
        query: lStu ? null : lSrch,
        onQuery: setLSrch,
        searchPlaceholder: "或输入关键字搜索…",
        total: filteredLogs.length,
        totalNoun: "条",
        extraDirty: Boolean(lStu || lAct),
        onClearExtra: () => {
          setLStu(null);
          setLAct("");
        },
        extra: /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: lStu, onChange: setLStu, placeholder: "精确筛选学员…", showBal: false })), /* @__PURE__ */ React.createElement(
          "select",
          {
            value: lAct,
            onChange: (e) => setLAct(e.target.value),
            className: "px-3 py-3 border border-gray-200 rounded-xl bg-white focus:ring-2 focus:ring-indigo-500 outline-none min-h-[44px]"
          },
          /* @__PURE__ */ React.createElement("option", { value: "" }, "全部操作"),
          logActions.map((a) => /* @__PURE__ */ React.createElement("option", { key: a, value: a }, a))
        ))
      }
    ), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-2" }, [
      { l: "本月", fn: () => {
        const n = /* @__PURE__ */ new Date();
        const y = n.getFullYear(), m = String(n.getMonth() + 1).padStart(2, "0");
        setLDateFrom(`${y}-${m}-01`);
        setLDateTo(`${y}-${m}-${String(new Date(y, n.getMonth() + 1, 0).getDate()).padStart(2, "0")}`);
      } },
      { l: "近30天", fn: () => {
        const t = /* @__PURE__ */ new Date(), f = new Date(t - 30 * 864e5);
        setLDateFrom(f.toLocaleDateString("en-CA"));
        setLDateTo(t.toLocaleDateString("en-CA"));
      } },
      { l: "本年", fn: () => {
        const y = (/* @__PURE__ */ new Date()).getFullYear();
        setLDateFrom(`${y}-01-01`);
        setLDateTo(`${y}-12-31`);
      } }
    ].map(({ l, fn }) => /* @__PURE__ */ React.createElement(
      "button",
      {
        key: l,
        type: "button",
        onClick: fn,
        className: "px-3 py-1.5 bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 rounded-xl text-xs font-bold min-h-[44px]"
      },
      l
    ))), canManageOperations && /* @__PURE__ */ React.createElement("div", { className: "flex" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportLogsCSV,
        className: "inline-flex items-center gap-1.5 ml-auto bg-white border border-gray-200 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-xs min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }),
      "CSV"
    ))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-left" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "border-b-2 border-gray-100 text-gray-400 text-xs" }, /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "时间"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "学员"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "操作"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "变动"))), /* @__PURE__ */ React.createElement("tbody", null, pagedLogs.map((l) => /* @__PURE__ */ React.createElement("tr", { key: l.id, className: "border-b border-gray-50 hover-row" }, /* @__PURE__ */ React.createElement("td", { className: "p-3 text-gray-400 text-xs font-mono whitespace-nowrap" }, l.date), /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-gray-800 text-sm" }, l.studentName), /* @__PURE__ */ React.createElement("td", { className: "p-3" }, /* @__PURE__ */ React.createElement("span", { className: `px-1.5 py-0.5 rounded text-xs font-bold border ${l.action === "充值购课" ? "bg-green-100 text-green-700 border-green-200" : l.action === "上课签到" ? "bg-indigo-100 text-indigo-700 border-indigo-200" : l.action && l.action.includes("手动") ? "bg-orange-100 text-orange-700 border-orange-200" : l.action && (l.action.includes("拒绝") || l.action.includes("删除")) ? "bg-red-100 text-red-700 border-red-200" : "bg-gray-100 text-gray-700 border-gray-200"}` }, l.action), l.payMethod && /* @__PURE__ */ React.createElement("span", { className: "ml-1 bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded text-xs" }, l.payMethod), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 block mt-0.5" }, displayNote(l.note)), l.actorEmail && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 block" }, "操作人：", l.actorEmail), l.feePaid > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-green-600 font-bold" }, "$", l.feePaid)), /* @__PURE__ */ React.createElement("td", { className: `p-3 font-bold ${String(l.change).startsWith("-") ? "text-orange-500" : l.change === "0" || l.change === 0 ? "text-gray-400" : "text-green-500"}` }, l.change))), !pagedLogs.length && /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("td", { colSpan: "4", className: "p-8 text-center text-gray-400" }, "无记录"))))), logPageCount > 1 && /* @__PURE__ */ React.createElement("div", { className: "p-3 border-t flex items-center justify-center gap-1.5" }, /* @__PURE__ */ React.createElement("button", { disabled: lPage === 1, onClick: () => setLPage(1), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]" }, "«"), /* @__PURE__ */ React.createElement("button", { disabled: lPage === 1, onClick: () => setLPage((p) => p - 1), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]" }, "‹"), /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-600 px-2" }, lPage, " / ", logPageCount), /* @__PURE__ */ React.createElement("button", { disabled: lPage === logPageCount, onClick: () => setLPage((p) => p + 1), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]" }, "›"), /* @__PURE__ */ React.createElement("button", { disabled: lPage === logPageCount, onClick: () => setLPage(logPageCount), className: "px-3 py-2 rounded-lg bg-gray-100 active:bg-gray-200 disabled:opacity-40 text-sm font-bold min-h-[44px]" }, "»"))));
  }
  function StatsSection(props) {
    const {
      analytics,
      bizReport,
      exportBizCSV,
      exportRevenueCSV,
      payBreakdown,
      sFrom,
      sPeriod,
      sStu,
      sStu2,
      sTo,
      sYear,
      setSFrom,
      setSPeriod,
      setSStu,
      setSStu2,
      setSTo,
      setSYear,
      sortedAZ,
      statsData,
      studentStats
    } = props;
    return /* @__PURE__ */ React.createElement("div", { className: "anim space-y-5" }, /* @__PURE__ */ React.createElement("h2", { className: "md:hidden text-xl font-bold text-gray-800 flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Icon, { name: "trend", className: "w-6 h-6" }), " 经营统计"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-4 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gradient-to-br from-indigo-500 to-indigo-700 p-4 rounded-2xl text-white shadow-md" }, /* @__PURE__ */ React.createElement("p", { className: "text-indigo-100 text-xs mb-1" }, "历史总营收"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold" }, "$", analytics.totalRevenue.toFixed(0))), /* @__PURE__ */ React.createElement("div", { className: "bg-white p-4 rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, "建档学员"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold text-gray-800" }, analytics.totalStudents)), /* @__PURE__ */ React.createElement("div", { className: "bg-white p-4 rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, "累计消课"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold text-indigo-600" }, analytics.totalCheckins)), /* @__PURE__ */ React.createElement("div", { className: "bg-white p-4 rounded-2xl shadow-sm border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-xs mb-1" }, "课时资产池"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl md:text-3xl font-bold text-emerald-600" }, analytics.totalBalance))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between mb-3" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "近 12 个月营收 (AUD)"), sStu && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg" }, "全局数据")), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto -mx-1 px-1" }, /* @__PURE__ */ React.createElement("div", { style: { minWidth: "580px" } }, /* @__PURE__ */ React.createElement(BarChart, { items: analytics.chart12.map((d) => ({ v: d.rev, l: d.l })), color: "var(--info)", h: 130 })))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between mb-3" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm" }, "近 12 个月消课次数"), sStu && /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded-lg" }, "全局数据")), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto -mx-1 px-1" }, /* @__PURE__ */ React.createElement("div", { style: { minWidth: "580px" } }, /* @__PURE__ */ React.createElement(BarChart, { items: analytics.chart12.map((d) => ({ v: d.ci, l: d.l })), color: "var(--success)", h: 130 }))))), payBreakdown.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-700 text-sm mb-3" }, "付款方式分布"), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-3" }, payBreakdown.map(([pm, d]) => /* @__PURE__ */ React.createElement("div", { key: pm, className: "bg-gray-50 border border-gray-100 rounded-xl px-4 py-3 text-center min-w-[90px]" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, pm), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, "$", d.revenue.toFixed(0)), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, d.count, " 次"))))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 p-4" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center justify-between mb-3" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 font-bold text-gray-700 text-sm" }, /* @__PURE__ */ React.createElement(Icon, { name: "dashboard", className: "w-4 h-4" }), "经营月报（近 6 个月）"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportBizCSV,
        className: "inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-1.5 rounded-xl text-xs font-bold min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }),
      "导出 CSV"
    )), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-sm", style: { minWidth: "480px" } }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "text-xs text-gray-400 border-b" }, /* @__PURE__ */ React.createElement("th", { className: "text-left py-2 px-2" }, "月份"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "营收"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "充值"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "消课"), /* @__PURE__ */ React.createElement("th", { className: "text-right px-2" }, "新学员"))), /* @__PURE__ */ React.createElement("tbody", null, bizReport.rows.map((r) => /* @__PURE__ */ React.createElement("tr", { key: r.k, className: "border-b border-gray-50" }, /* @__PURE__ */ React.createElement("td", { className: "py-2 px-2 font-bold text-gray-700" }, r.label), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 font-bold text-indigo-700" }, "$", r.rev.toFixed(0)), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 text-gray-600" }, r.topups, " 笔"), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 text-gray-600" }, r.ci, " 次"), /* @__PURE__ */ React.createElement("td", { className: "text-right px-2 text-gray-600" }, r.newStu || "—")))))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-3 mt-4" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 mb-2" }, "课包销量排行（历史累计）"), bizReport.pkgRank.length === 0 && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "暂无充值记录"), bizReport.pkgRank.slice(0, 5).map(([name, d], i) => /* @__PURE__ */ React.createElement("div", { key: name, className: "flex items-center justify-between py-1 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-700" }, i + 1, ". ", name), /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-800" }, "$", d.revenue.toFixed(0), " ", /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 font-normal" }, "/ ", d.count, " 笔"))))), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 mb-2" }, "消课节奏（近 180 天）"), /* @__PURE__ */ React.createElement("p", { className: "text-2xl font-bold text-emerald-600" }, bizReport.avgGap ? bizReport.avgGap.toFixed(1) : "—", " ", /* @__PURE__ */ React.createElement("span", { className: "text-sm font-normal text-gray-500" }, "天/次")), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-1" }, "规律上课学员 ", bizReport.regularStu, " 人的平均上课间隔。间隔变长 = 出勤率下降的早期信号")))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b p-4 space-y-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800" }, "财务明细报表"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: exportRevenueCSV,
        className: "inline-flex items-center gap-1.5 bg-white border border-gray-300 active:bg-gray-50 text-gray-600 px-3 py-2 rounded-xl font-bold text-sm min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }),
      "CSV"
    ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-1 bg-gray-100 p-1 rounded-xl" }, [["monthly", "月度"], ["yearly", "年度"], ["custom", "自定义"]].map(([v, l]) => /* @__PURE__ */ React.createElement("button", { key: v, onClick: () => setSPeriod(v), className: `px-3 py-2 rounded-lg text-sm font-bold min-h-[44px] ${sPeriod === v ? "bg-white shadow text-indigo-700" : "text-gray-500"}` }, l))))), /* @__PURE__ */ React.createElement("div", { className: "flex flex-wrap gap-3 items-center" }, sPeriod === "monthly" && /* @__PURE__ */ React.createElement(
      "select",
      {
        value: sYear,
        onChange: (e) => setSYear(e.target.value),
        className: "px-2 py-2 border border-gray-300 rounded-xl bg-white focus:ring-2 focus:ring-indigo-400 outline-none text-sm min-h-[44px]"
      },
      /* @__PURE__ */ React.createElement("option", { value: "all" }, "所有年份"),
      analytics.availYears.map((y) => /* @__PURE__ */ React.createElement("option", { key: y, value: y }, y, "年"))
    ), sPeriod === "custom" && /* Fix ⑩: type="month" gives YYYY-MM value, matches our monthKey format exactly */
    /* @__PURE__ */ React.createElement("div", { className: "flex flex-col sm:flex-row sm:items-center gap-2 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "font-medium text-gray-500" }, "自定义范围"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("input", { type: "month", value: sFrom, onChange: (e) => setSFrom(e.target.value), className: "flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]" }), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, "至"), /* @__PURE__ */ React.createElement("input", { type: "month", value: sTo, onChange: (e) => setSTo(e.target.value), className: "flex-1 sm:flex-none px-2 py-2 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-400 outline-none min-h-[44px]" }))), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 ml-auto" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm text-gray-500" }, "筛选:"), /* @__PURE__ */ React.createElement("div", { className: "w-48" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: sStu, onChange: setSStu, placeholder: "全部学员", showBal: false })))), statsData.rows.length > 0 && /* @__PURE__ */ React.createElement("div", { className: "flex gap-4 text-sm" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "合计: ", /* @__PURE__ */ React.createElement("span", { className: "font-bold text-green-600" }, "$", statsData.totalRev.toFixed(2))), /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "消课: ", /* @__PURE__ */ React.createElement("span", { className: "font-bold text-indigo-600" }, statsData.totalCI, " 次")), statsData.totalCI > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-gray-500" }, "均价/课: ", /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, "$", (statsData.totalRev / statsData.totalCI).toFixed(1))))), /* @__PURE__ */ React.createElement("div", { className: "overflow-x-auto" }, /* @__PURE__ */ React.createElement("table", { className: "w-full text-left" }, /* @__PURE__ */ React.createElement("thead", null, /* @__PURE__ */ React.createElement("tr", { className: "border-b border-gray-100 text-gray-400 text-xs" }, /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "周期"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "入账流水"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "消课"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "充值次数"), /* @__PURE__ */ React.createElement("th", { className: "p-3 font-bold" }, "均价/课"))), /* @__PURE__ */ React.createElement("tbody", null, statsData.rows.map((r) => /* @__PURE__ */ React.createElement("tr", { key: r.key, className: "border-b border-gray-50 hover-row text-sm" }, /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-gray-700" }, sPeriod === "yearly" ? `${r.key}年` : fmtMK(r.key)), /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-green-600" }, "$", r.revenue.toFixed(2)), /* @__PURE__ */ React.createElement("td", { className: "p-3 font-bold text-indigo-600" }, r.checkins), /* @__PURE__ */ React.createElement("td", { className: "p-3 text-gray-600" }, r.topups), /* @__PURE__ */ React.createElement("td", { className: "p-3 text-gray-500" }, r.checkins > 0 ? `$${(r.revenue / r.checkins).toFixed(1)}` : "-"))), !statsData.rows.length && /* @__PURE__ */ React.createElement("tr", null, /* @__PURE__ */ React.createElement("td", { colSpan: "5", className: "p-8 text-center text-gray-400" }, "暂无数据")))))), /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border-b p-4" }, /* @__PURE__ */ React.createElement("h3", { className: "font-bold text-gray-800 mb-3" }, "学员个人分析"), /* @__PURE__ */ React.createElement("div", { className: "max-w-xs" }, /* @__PURE__ */ React.createElement(StudentPicker, { students: sortedAZ, value: sStu2, onChange: setSStu2, placeholder: "选择学员查看详情...", showBal: true }))), studentStats ? /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-4" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 md:grid-cols-5 gap-3" }, [
      { l: "当前余额", v: `${studentStats.student.balance} 课时`, c: "text-indigo-700" },
      { l: "累计消课", v: `${studentStats.checkins} 次`, c: "text-gray-700" },
      { l: "累计购课", v: `${studentStats.totalBought} 课时`, c: "text-gray-700" },
      { l: "累计消费", v: `$${studentStats.totalSpent.toFixed(0)}`, c: "text-green-600" },
      { l: "充值次数", v: `${studentStats.topupCount} 次`, c: "text-gray-700" }
    ].map(({ l, v, c }) => /* @__PURE__ */ React.createElement("div", { key: l, className: "bg-gray-50 p-3 rounded-xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, l), /* @__PURE__ */ React.createElement("p", { className: `text-lg font-bold ${c}` }, v)))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3 text-sm text-gray-500" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-4 h-4" }), studentStats.student.mobile || "—"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "mail", className: "w-4 h-4" }), studentStats.student.email || "—"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "target", className: "w-4 h-4" }), "首次: ", studentStats.first ? String(studentStats.first).split(",")[0] : "—"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "clock", className: "w-4 h-4" }), "最近: ", studentStats.last ? String(studentStats.last).split(",")[0] : "—")), studentStats.student.remark && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-3 rounded-xl text-sm text-gray-600 border border-gray-100 inline-flex items-start gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "note", className: "w-4 h-4" }), studentStats.student.remark), /* @__PURE__ */ React.createElement("div", { className: "border border-gray-100 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 px-3 py-2 text-xs font-bold text-gray-600 border-b" }, "交易记录 (", studentStats.logs.length, ")"), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50 max-h-56 overflow-y-auto sl" }, studentStats.logs.slice(0, 50).map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "px-3 py-2.5 flex justify-between text-sm min-h-[44px] items-center" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "font-medium text-gray-700" }, l.action), " ", l.payMethod && /* @__PURE__ */ React.createElement("span", { className: "text-blue-500 ml-1 text-xs" }, l.payMethod), " ", /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, l.note)), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 flex-shrink-0" }, l.feePaid > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-green-600 font-bold text-xs" }, "$", l.feePaid), /* @__PURE__ */ React.createElement("span", { className: `font-bold text-xs ${String(l.change).startsWith("-") ? "text-orange-500" : "text-green-500"}` }, l.change), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, String(l.date).split(",")[0]))))))) : /* @__PURE__ */ React.createElement("div", { className: "p-10 text-center text-gray-400 text-sm" }, "选择一名学员查看个人数据")));
  }

  // legacy-root/src/panels/student_profile.jsx
  function StudentProfileModal(props) {
    const {
      accessCodeResult,
      archiveStudent,
      attHistory,
      busy,
      canPublishProgress,
      canUseSettlementBilling,
      canWriteAttendance,
      canWriteCredits,
      canWritePortfolio,
      canWriteProgress,
      canWriteStudents,
      consentEdit,
      copyText,
      db,
      editP,
      editPhoto,
      generateStudentAccessCode,
      handleDelete,
      handleUpdateStudent,
      isStudentScheduledOn,
      notify,
      openGrowthReport,
      portfolioDoDelete,
      preferenceProfile,
      preferenceRows,
      preferenceValue,
      profileDialogRef,
      revokeStudentAccessCode,
      save,
      savePublicationConsent,
      scheduleStudentToday,
      selS,
      setConsentEdit,
      setEditP,
      setEditPhoto,
      setPortEdit,
      setPortLB,
      setPortUpload,
      setSelS,
      setStudentProfileTab,
      setTab,
      setTuStu,
      showToast,
      studentProfileTab,
      tab,
      withdrawPublicationConsent,
      workNoun
    } = props;
    return /* @__PURE__ */ React.createElement(
      "div",
      {
        ref: profileDialogRef,
        className: "fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center sm:p-4 backdrop-blur-sm",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "student-profile-title"
      },
      /* @__PURE__ */ React.createElement("div", { className: "bg-white w-full sm:rounded-3xl shadow-2xl overflow-hidden anim border-t sm:border border-gray-200 flex flex-col cms-profile-sheet" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center p-4 bg-gray-50 border-b flex-shrink-0" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2.5 min-w-0" }, /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: selS.photo, name: selS.name, size: "sm" }), /* @__PURE__ */ React.createElement("h3", { id: "student-profile-title", className: "text-lg font-bold text-gray-900 truncate" }, selS.name), /* @__PURE__ */ React.createElement(BalBadge, { n: selS.balance }), selS.archived && /* @__PURE__ */ React.createElement("span", { className: "text-xs bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full shrink-0" }, "归档")), /* @__PURE__ */ React.createElement("button", { onClick: () => {
        setSelS(null);
        setEditP(false);
      }, "aria-label": "关闭", className: "text-gray-400 active:text-gray-700 text-2xl font-bold p-2 -mr-1 min-h-[44px] min-w-[44px] flex items-center justify-center" }, "×")), !editP && /* @__PURE__ */ React.createElement(
        Tabs,
        {
          idBase: "student-profile",
          label: "学员档案分类",
          value: studentProfileTab,
          onChange: setStudentProfileTab,
          className: "px-2 bg-white flex-shrink-0",
          items: [
            { value: "profile", label: "概览", icon: "users" },
            { value: "details", label: "资料", icon: "clipboard" },
            { value: "records", label: "记录", icon: "calendar" },
            ...canWritePortfolio ? [{ value: "portfolio", label: `${workNoun}集`, icon: "image" }] : [],
            ...TENANT_SLUG && canWriteStudents ? [{ value: "portal", label: "专区", icon: "lock" }] : []
          ]
        }
      ), /* @__PURE__ */ React.createElement("div", { className: "modal-scroll cms-profile-body flex-1 min-h-0" }, !editP ? /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement(TabPanel, { idBase: "student-profile", name: "profile", active: studentProfileTab === "profile" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-4 h-4" }), "电话"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.mobile || "—")), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "最近上课"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, fmtDate(selS.lastActive)))), (selS.wechat || selS.email) && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, selS.wechat && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "微信号"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.wechat)), selS.email && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-gray-400 mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "mail", className: "w-4 h-4" }), "邮箱"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 text-sm break-all" }, selS.email))), TENANT_SLUG && /* @__PURE__ */ React.createElement(
        StudentBillingAccount,
        {
          api: v1Api,
          studentId: selS.id,
          onOpenBilling: (id) => {
            setSelS(null);
            setTab("billing", { recordId: id });
          }
        }
      ), selS.remark && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "备注"), /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-700 whitespace-pre-wrap" }, selS.remark)), !selS.mobile && !selS.wechat && !selS.email && !selS.remark && /* @__PURE__ */ React.createElement(EmptyState, { icon: /* @__PURE__ */ React.createElement(Icon, { name: "phone", className: "w-8 h-8" }), main: "还没有联系方式", sub: "点击下方「编辑」补充电话、微信或邮箱" })), /* @__PURE__ */ React.createElement(TabPanel, { idBase: "student-profile", name: "details", active: studentProfileTab === "details" }, /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "First Name (名)"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.firstName || selS.name || "—")), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "Last Name (姓)"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, selS.lastName || "—"))), (selS.birthday || selS.enrollmentDate) && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, selS.birthday && /* @__PURE__ */ React.createElement("div", { className: "bg-pink-50 p-4 rounded-2xl border border-pink-100" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-pink-400 mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "cake", className: "w-4 h-4" }), "生日"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, fmtDate(selS.birthday))), selS.enrollmentDate && /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 p-4 rounded-2xl border border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mb-1" }, "入学日期"), /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800" }, fmtDate(selS.enrollmentDate)))), preferenceRows(selS).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2" }, preferenceRows(selS).map((row) => /* @__PURE__ */ React.createElement("div", { key: row.key, className: "bg-indigo-50 p-3 rounded-2xl border border-indigo-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-indigo-400 mb-0.5" }, row.label), /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-indigo-800" }, row.value)))), canWriteStudents && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => archiveStudent(selS.id, selS.name, !selS.archived),
          className: `w-full py-3 rounded-xl text-sm font-bold border min-h-[50px] ${selS.archived ? "bg-green-50 active:bg-green-100 text-green-700 border-green-200" : "bg-gray-50 active:bg-gray-100 text-gray-500 border-gray-200"}`
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: selS.archived ? "restore" : "archiveBox", className: "w-4 h-4" }), selS.archived ? "恢复学员" : "归档学员")
      )), /* @__PURE__ */ React.createElement(TabPanel, { idBase: "student-profile", name: "records", active: studentProfileTab === "records" }, TENANT_SLUG && /* @__PURE__ */ React.createElement(
        StudentTimeline,
        {
          api: v1Api,
          studentId: selS.id,
          openInvoice: canUseSettlementBilling ? (iid) => {
            setSelS(null);
            setEditP(false);
            setTab("billing", { recordId: String(iid) });
          } : null
        }
      ), TENANT_SLUG && /* @__PURE__ */ React.createElement(
        StudentProgressReports,
        {
          api: v1Api,
          studentId: selS.id,
          studentName: selS.name,
          canWrite: canWriteProgress,
          canPublish: canPublishProgress,
          showToast
        }
      ), canWriteCredits && (() => {
        const topupsAll = db.logs.filter((l) => (l.studentId === selS.id || !l.studentId && l.studentName === selS.name) && l.action === "充值购课");
        const topups = topupsAll.slice(0, 10);
        if (!topupsAll.length) return null;
        return /* @__PURE__ */ React.createElement("details", { className: "border border-gray-200 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100 flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Icon, { name: "card", className: "w-4 h-4" }), "充值记录 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400 text-xs" }, "(", topupsAll.length, " 条", topupsAll.length > 10 ? " · 显示最近10条" : "", ")")), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50" }, topups.map((l) => /* @__PURE__ */ React.createElement("div", { key: l.id, className: "px-4 py-2.5 flex justify-between items-center text-sm" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-indigo-700" }, "+", l.change), /* @__PURE__ */ React.createElement("span", { className: "ml-2 text-xs text-gray-400" }, l.payMethod || ""), l.note && /* @__PURE__ */ React.createElement("span", { className: "ml-1 text-xs text-gray-400 truncate" }, l.note)), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 flex-shrink-0" }, l.feePaid > 0 && /* @__PURE__ */ React.createElement("span", { className: "text-green-600 font-bold text-xs" }, "$", l.feePaid), /* @__PURE__ */ React.createElement("span", { className: "text-gray-400 text-xs" }, String(l.date).split(",")[0]))))));
      })(), TENANT_SLUG && attHistory && attHistory.length > 0 && /* @__PURE__ */ React.createElement("details", { className: "border border-blue-100 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "inline-flex items-center gap-1.5 bg-blue-50 px-4 py-3 cursor-pointer select-none text-sm font-bold text-blue-700" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "上课记录 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-blue-400 text-xs ml-1" }, "(近 ", attHistory.length, " 次)")), /* @__PURE__ */ React.createElement("div", { className: "divide-y divide-gray-50 max-h-64 overflow-y-auto sl" }, attHistory.map((a) => /* @__PURE__ */ React.createElement("div", { key: a.id, className: `px-4 py-2.5 flex items-center justify-between text-sm ${a.reversed_at ? "opacity-50" : ""}` }, /* @__PURE__ */ React.createElement("span", { className: "font-bold text-gray-700" }, fmtDate(String(a.class_date || a.attended_at).slice(0, 10))), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-400 flex-1 text-center truncate px-2" }, a.note || "常规课程"), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold ${a.reversed_at ? "text-gray-400" : "text-green-600"}` }, a.reversed_at ? "已撤销" : "✓ 已签"))))), !(canWriteCredits && db.logs.some((l) => (l.studentId === selS.id || !l.studentId && l.studentName === selS.name) && l.action === "充值购课")) && !(TENANT_SLUG && attHistory && attHistory.length > 0) && /* @__PURE__ */ React.createElement(EmptyState, { icon: /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-8 h-8" }), main: "还没有记录", sub: "充值与上课签到会自动出现在这里" })), TENANT_SLUG && canWriteStudents && /* @__PURE__ */ React.createElement(TabPanel, { idBase: "student-profile", name: "portal", active: studentProfileTab === "portal" }, /* @__PURE__ */ React.createElement("div", { className: "border border-indigo-100 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-indigo-50 px-4 py-3 flex items-center justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-indigo-800" }, /* @__PURE__ */ React.createElement(Icon, { name: "lock", className: "w-4 h-4" }), "学员专区"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-indigo-500 mt-0.5" }, "姓名、手机与独立 6 位访问码验证；访问码不会保存明文。")), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-1 rounded-full shrink-0 ${selS.hasAccessCode ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}` }, selS.hasAccessCode ? "已启用" : "未启用")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, !selS.mobile && /* @__PURE__ */ React.createElement("p", { className: "text-xs rounded-xl bg-amber-50 border border-amber-100 text-amber-700 p-3" }, "请先补充学员手机号码，再生成访问码。"), accessCodeResult?.studentId === selS.id && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl border border-amber-200 bg-amber-50 p-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-amber-800" }, "仅显示一次，请立即安全交给家长或成年学员"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-3 mt-2" }, /* @__PURE__ */ React.createElement("code", { className: "text-2xl tracking-[0.3em] font-bold text-gray-900" }, accessCodeResult.code), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => copyText(accessCodeResult.code, "访问码已复制"),
          className: "ml-auto px-3 py-2 rounded-lg bg-white border border-amber-200 text-xs font-bold text-amber-800 min-h-[44px]"
        },
        "复制"
      ))), selS.accessCodeUpdatedAt && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "最近更新：", fmtDate(selS.accessCodeUpdatedAt)), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement(
        "button",
        {
          disabled: busy || !selS.mobile,
          onClick: () => selS.hasAccessCode ? confirm("生成新访问码后，旧访问码和现有登录会话会立即失效。继续？", generateStudentAccessCode, { confirmText: "生成新码" }) : generateStudentAccessCode(),
          className: "w-full py-2.5 rounded-xl bg-indigo-600 active:bg-indigo-700 text-white text-sm font-bold disabled:bg-gray-300 min-h-[44px]"
        },
        selS.hasAccessCode ? "更换访问码" : "生成访问码"
      ), selS.hasAccessCode && /* @__PURE__ */ React.createElement("details", { className: "mt-3 rounded-xl border border-gray-200 bg-gray-50 px-3 py-2" }, /* @__PURE__ */ React.createElement("summary", { className: "cursor-pointer text-xs font-bold text-gray-500 select-none" }, "高级操作"), /* @__PURE__ */ React.createElement("div", { className: "pt-3 flex items-center gap-3" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 flex-1" }, "停用后，当前访问码和所有已登录会话会立即失效。"), /* @__PURE__ */ React.createElement(
        "button",
        {
          disabled: busy,
          onClick: revokeStudentAccessCode,
          className: "px-3 py-2 rounded-lg bg-white border border-red-200 text-red-700 text-xs font-bold min-h-[44px]"
        },
        "停用学员专区"
      ))))))), canWritePortfolio && /* @__PURE__ */ React.createElement(TabPanel, { idBase: "student-profile", name: "portfolio", active: studentProfileTab === "portfolio" }, TENANT_SLUG && /* @__PURE__ */ React.createElement("div", { className: `border rounded-2xl overflow-hidden ${selS.publicationConsent?.status === "confirmed" ? "border-emerald-100" : selS.publicationConsent?.status === "withdrawn" ? "border-amber-100" : "border-gray-200"}` }, /* @__PURE__ */ React.createElement("div", { className: `px-4 py-3 flex items-center justify-between gap-3 ${selS.publicationConsent?.status === "confirmed" ? "bg-emerald-50" : selS.publicationConsent?.status === "withdrawn" ? "bg-amber-50" : "bg-gray-50"}` }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-gray-900" }, /* @__PURE__ */ React.createElement(Icon, { name: "shield", className: "w-4 h-4" }), "官网作品公开授权"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-0.5" }, "授权与撤回均追加为不可覆盖的审计记录。")), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold px-2 py-1 rounded-full shrink-0 ${selS.publicationConsent?.status === "confirmed" ? "bg-emerald-600 text-white" : selS.publicationConsent?.status === "withdrawn" ? "bg-amber-100 text-amber-700" : "bg-gray-100 text-gray-500"}` }, selS.publicationConsent?.status === "confirmed" ? "有效" : selS.publicationConsent?.status === "withdrawn" ? "已撤回" : "未记录")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, selS.publicationConsent?.status === "confirmed" && /* @__PURE__ */ React.createElement("div", { className: "text-xs text-gray-600 space-y-1" }, /* @__PURE__ */ React.createElement("p", null, "授权人：", /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, selS.publicationConsent.by || "—"), " · ", selS.publicationConsent.relationship || "—", " · ", selS.publicationConsent.method || "—"), /* @__PURE__ */ React.createElement("p", { className: "text-gray-400" }, "记录时间：", fmtDate(selS.publicationConsent.at), " · 告知版本 ", selS.publicationConsent.noticeVersion || "—")), consentEdit?.mode === "confirm" && /* @__PURE__ */ React.createElement("div", { className: "space-y-2 rounded-xl bg-gray-50 border border-gray-100 p-3" }, /* @__PURE__ */ React.createElement(
        "input",
        {
          value: consentEdit.by,
          onChange: (e) => setConsentEdit((p) => ({ ...p, by: e.target.value })),
          placeholder: "授权人姓名 *",
          maxLength: 120,
          className: "w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm outline-none focus:ring-2 focus:ring-emerald-400"
        }
      ), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement(
        "select",
        {
          value: consentEdit.relationship,
          onChange: (e) => setConsentEdit((p) => ({ ...p, relationship: e.target.value })),
          className: "px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white"
        },
        /* @__PURE__ */ React.createElement("option", { value: "" }, "与学员关系 *"),
        /* @__PURE__ */ React.createElement("option", null, "监护人"),
        /* @__PURE__ */ React.createElement("option", null, "本人"),
        /* @__PURE__ */ React.createElement("option", null, "其他授权人")
      ), /* @__PURE__ */ React.createElement(
        "select",
        {
          value: consentEdit.method,
          onChange: (e) => setConsentEdit((p) => ({ ...p, method: e.target.value })),
          className: "px-3 py-2.5 border border-gray-200 rounded-xl text-sm bg-white"
        },
        /* @__PURE__ */ React.createElement("option", { value: "" }, "授权方式 *"),
        /* @__PURE__ */ React.createElement("option", null, "书面确认"),
        /* @__PURE__ */ React.createElement("option", null, "电子确认"),
        /* @__PURE__ */ React.createElement("option", null, "当面确认")
      )), /* @__PURE__ */ React.createElement(
        "textarea",
        {
          value: consentEdit.note,
          onChange: (e) => setConsentEdit((p) => ({ ...p, note: e.target.value })),
          placeholder: "备注（可选，不要记录证件号码）",
          rows: "2",
          maxLength: 500,
          className: "w-full px-3 py-2.5 border border-gray-200 rounded-xl text-sm resize-none"
        }
      ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("button", { onClick: () => setConsentEdit(null), className: "flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-bold text-gray-500" }, "取消"), /* @__PURE__ */ React.createElement("button", { disabled: busy, onClick: savePublicationConsent, className: "flex-1 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold disabled:opacity-50" }, "记录授权"))), consentEdit?.mode === "withdraw" && /* @__PURE__ */ React.createElement("div", { className: "space-y-2 rounded-xl bg-red-50 border border-red-100 p-3" }, /* @__PURE__ */ React.createElement(
        "textarea",
        {
          value: consentEdit.note,
          onChange: (e) => setConsentEdit((p) => ({ ...p, note: e.target.value })),
          placeholder: "撤回原因 *（将写入审计记录）",
          rows: "2",
          maxLength: 500,
          className: "w-full px-3 py-2.5 border border-red-200 rounded-xl text-sm resize-none"
        }
      ), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-red-600" }, "确认后，该学员当前所有官网公开作品会立即下架，私人作品仍保留。"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("button", { onClick: () => setConsentEdit(null), className: "flex-1 py-2.5 rounded-xl border border-gray-200 bg-white text-sm font-bold text-gray-500" }, "取消"), /* @__PURE__ */ React.createElement("button", { disabled: busy, onClick: withdrawPublicationConsent, className: "flex-1 py-2.5 rounded-xl bg-red-600 text-white text-sm font-bold disabled:opacity-50" }, "撤回并下架"))), !consentEdit && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setConsentEdit({ mode: "confirm", by: "", relationship: "", method: "", note: "" }),
          className: "flex-1 py-2.5 rounded-xl bg-indigo-600 active:bg-indigo-700 text-white text-sm font-bold min-h-[44px]"
        },
        selS.publicationConsent?.status === "confirmed" ? "追加新授权记录" : "记录授权"
      ), selS.publicationConsent?.status === "confirmed" && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setConsentEdit({ mode: "withdraw", note: "" }),
          className: "px-4 py-2.5 rounded-xl bg-white border border-red-200 text-red-700 text-sm font-bold min-h-[44px]"
        },
        "撤回"
      )))), (() => {
        const items = selS.portfolio || [];
        return (
          /* purple maps to the info role, and a section heading is not a
             state — it was painting a whole panel blue for no reason a reader
             could act on. Headings take the neutral ramp; the upload button is
             the primary action here and takes the accent, like every other
             filled action in this console. */
          /* @__PURE__ */ React.createElement("div", { className: "border border-gray-200 rounded-2xl overflow-hidden" }, /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 px-4 py-3 flex items-center justify-between" }, /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-gray-900 flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-4 h-4" }), " ", workNoun, "集", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-500 text-xs ml-1" }, `(${items.length} 张)`)), /* @__PURE__ */ React.createElement(
            "button",
            {
              onClick: () => setPortUpload(true),
              className: "text-xs bg-indigo-600 active:bg-indigo-700 text-white px-3 py-1.5 rounded-lg font-bold"
            },
            "+ 上传"
          )), items.length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "px-4 py-7 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-2xl mb-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-4 h-4" })), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "还没有作品，点击「上传」添加第一张")) : /* @__PURE__ */ React.createElement("div", { className: "p-2.5 grid grid-cols-3 gap-2" }, items.map((item, idx) => /* @__PURE__ */ React.createElement(
            "div",
            {
              key: item.id,
              className: "port-thumb relative group cursor-pointer rounded-xl overflow-hidden bg-gray-100",
              style: { aspectRatio: "1" },
              role: "button",
              tabIndex: 0,
              "aria-label": `查看${item.title || fmtDate(item.date)}作品`,
              onKeyDown: (event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setPortLB({ items, idx });
                }
              },
              onClick: () => setPortLB({ items, idx })
            },
            /* @__PURE__ */ React.createElement("div", { className: "img-skel absolute inset-0", id: `sk-${item.id}` }),
            /* @__PURE__ */ React.createElement(
              "img",
              {
                src: portfolioThumbSrc(selS.id, item),
                srcSet: portfolioSrcSet(selS.id, item),
                sizes: "(max-width: 640px) 33vw, 220px",
                alt: item.title || `${selS.name}的作品 ${idx + 1}`,
                loading: "lazy",
                className: "w-full h-full object-cover relative",
                onLoad: (e) => {
                  const sk = document.getElementById(`sk-${item.id}`);
                  if (sk) sk.style.display = "none";
                },
                onError: (e) => {
                  e.target.style.display = "none";
                }
              }
            ),
            /* @__PURE__ */ React.createElement("div", { className: "absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent px-1.5 pt-4 pb-1" }, item.title && /* @__PURE__ */ React.createElement("p", { className: "text-white text-xs font-bold leading-tight truncate" }, item.title), /* @__PURE__ */ React.createElement("p", { className: "text-white text-xs leading-tight truncate" }, fmtDate(item.date), item.note ? " ·" : "")),
            item.public && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1 left-1 rounded-full bg-emerald-500 text-white text-[10px] font-bold px-2 py-0.5 shadow" }, "官网"),
            /* @__PURE__ */ React.createElement("div", { className: "port-actions absolute top-0.5 right-0.5 hidden group-hover:flex gap-1 z-10" }, /* @__PURE__ */ React.createElement(
              "button",
              {
                onClick: (e) => {
                  e.stopPropagation();
                  setPortEdit({ sid: String(selS.id), item, note: item.note || "", title: item.title || "", date: item.date || todayISO(), public: !!item.public });
                },
                "aria-label": "编辑",
                className: "bg-white/90 rounded-lg p-2 shadow leading-none flex items-center justify-center"
              },
              /* @__PURE__ */ React.createElement(Icon, { name: "pencil", className: "w-4 h-4" })
            ), /* @__PURE__ */ React.createElement(
              "button",
              {
                onClick: (e) => {
                  e.stopPropagation();
                  portfolioDoDelete(String(item.id));
                },
                "aria-label": "删除",
                className: "bg-red-500 rounded-lg p-2 text-white shadow leading-none flex items-center justify-center"
              },
              /* @__PURE__ */ React.createElement(Icon, { name: "trash", className: "w-4 h-4" })
            ))
          ))))
        );
      })(), canWritePortfolio && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => openGrowthReport(selS),
          className: "w-full py-3 rounded-xl text-sm font-bold bg-indigo-600 active:bg-indigo-700 text-white min-h-[50px] shadow-sm"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "star", className: "w-4 h-4" }), "生成成长报告（发给家长）")
      ))) : /* @__PURE__ */ React.createElement("form", { onSubmit: handleUpdateStudent, className: "space-y-4" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-2 block" }, "照片 Photo ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(PhotoUploader, { value: editPhoto, onChange: setEditPhoto, notify })), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "First Name (名) *"), /* @__PURE__ */ React.createElement("input", { name: "firstName", defaultValue: selS.firstName || selS.name || "", required: true, className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold" })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "Last Name (姓) ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("input", { name: "lastName", defaultValue: selS.lastName || "", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none font-bold" }))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "电话"), /* @__PURE__ */ React.createElement("input", { name: "mobile", defaultValue: selS.mobile, placeholder: "04xx xxx xxx", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-indigo-700 mb-1 block" }, "课时余额"), /* @__PURE__ */ React.createElement("input", { name: "balance", type: "number", min: "0", defaultValue: selS.balance, required: true, className: "w-full px-3 py-3 border-2 border-indigo-300 bg-white text-indigo-800 font-bold text-xl rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" }), /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-xs text-amber-500 mt-1" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-4 h-4" }), "修改将记入日志"))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "微信号 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("input", { name: "wechat", defaultValue: selS.wechat || "", placeholder: "如 wechat_id", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" })), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "邮箱 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("input", { name: "email", type: "email", defaultValue: selS.email || "", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none" }))), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-sm font-bold text-gray-500 mb-1 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "cake", className: "w-4 h-4" }), "生日 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "date",
          name: "birthday",
          defaultValue: selS.birthday || "",
          min: "1920-01-01",
          max: "2099-12-31",
          className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
        }
      )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "入学日期 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
        "input",
        {
          type: "date",
          name: "enrollmentDate",
          defaultValue: selS.enrollmentDate || "",
          min: "1900-01-01",
          max: todayISO(),
          className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
        }
      ), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400 mt-1" }, "可补录系统启用前的真实入学日期"))), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, "备注"), /* @__PURE__ */ React.createElement("textarea", { name: "remark", defaultValue: selS.remark, rows: "3", className: "w-full px-3 py-3 border border-gray-300 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none resize-none" })), /* @__PURE__ */ React.createElement("details", { className: "border border-gray-200 rounded-xl overflow-hidden" }, /* @__PURE__ */ React.createElement("summary", { className: "px-4 py-3 text-sm font-bold text-gray-500 cursor-pointer select-none bg-gray-50 active:bg-gray-100" }, preferenceProfile().title, " ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement("div", { className: "p-4 space-y-3" }, preferenceProfile().fields.map((field) => /* @__PURE__ */ React.createElement("div", { key: field.key }, /* @__PURE__ */ React.createElement("label", { className: "text-sm font-bold text-gray-500 mb-1 block" }, field.label), /* @__PURE__ */ React.createElement(
        "input",
        {
          name: `pref_${field.key}`,
          defaultValue: preferenceValue(selS, field.key),
          placeholder: field.placeholder,
          className: "w-full px-3 py-3 border border-gray-200 rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none"
        }
      ))))), /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center pt-3 border-t border-gray-100" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => handleDelete(selS.id, selS.name),
          disabled: busy,
          className: "px-4 py-3 bg-red-50 active:bg-red-100 text-red-700 font-bold rounded-xl text-sm border border-red-200 min-h-[50px]"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "trash", className: "w-4 h-4" }), "永久删除")
      ), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => confirm("放弃未保存的修改？", () => {
        setEditP(false);
        setEditPhoto("");
      }, { confirmText: "放弃修改" }), className: "px-4 py-3 bg-gray-100 active:bg-gray-200 text-gray-700 font-bold rounded-xl text-sm min-h-[50px]" }, "取消"), /* @__PURE__ */ React.createElement("button", { type: "submit", disabled: busy, className: "inline-flex items-center gap-1.5 px-6 py-3 bg-indigo-600 active:bg-indigo-700 text-white font-bold rounded-xl text-sm shadow-md min-h-[50px]" }, /* @__PURE__ */ React.createElement(Icon, { name: "save", className: "w-4 h-4" }), "保存"))))), !editP && /* @__PURE__ */ React.createElement("div", { className: "cms-profile-actions flex-shrink-0 border-t border-gray-200 bg-gray-50" }, /* @__PURE__ */ React.createElement("div", { className: "cms-profile-actions-row" }, canWriteAttendance && !selS.archived && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => scheduleStudentToday(selS),
          disabled: busy,
          className: "py-3 rounded-xl text-sm font-bold bg-indigo-600 active:bg-indigo-700 disabled:bg-gray-300 min-h-[50px] inline-flex items-center justify-center gap-1.5"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }),
        isStudentScheduledOn(selS.id, todayISO()) ? "查看今日排课" : "加入今日排课"
      ), canWriteStudents && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setEditP(true);
            setEditPhoto(selS.photo || "");
          },
          className: "py-3 rounded-xl text-sm font-bold bg-white border-2 border-indigo-100 active:bg-indigo-50 text-indigo-700 min-h-[50px]"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "pencil", className: "w-4 h-4" }), "编辑")
      )), canWriteCredits && !selS.archived && /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setTuStu(selS.id);
            setSelS(null);
            setEditP(false);
            setTab("topup");
          },
          className: "w-full py-3 rounded-xl text-sm font-bold bg-white border border-gray-200 active:bg-gray-50 text-gray-700 min-h-[50px]"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "money", className: "w-4 h-4" }), "快速充值")
      )))
    );
  }

  // legacy-root/src/cms-app.jsx
  var { useState: useState10, useEffect: useEffect9, useMemo: useMemo6, useRef: useRef3, useCallback: useCallback9 } = React;
  function App() {
    const [db, setDb] = useState10({ students: [], logs: [], rosters: {}, pending: [] });
    const [auditEvents, setAuditEvents] = useState10([]);
    const initialCmsRoute = useMemo6(() => readCmsRoute(), []);
    const [tab, setTabState] = useState10(initialCmsRoute.tab);
    const [pendingTab, setPendingTabState] = useState10(initialCmsRoute.pendingTab);
    const [settingsSection, setSettingsSectionState] = useState10(initialCmsRoute.settingsSection);
    const [rosterSection, setRosterSectionState] = useState10(initialCmsRoute.rosterSection);
    const [routeRecordId, setRouteRecordId] = useState10(initialCmsRoute.recordId);
    const [moreOpen, setMoreOpen] = useState10(false);
    const [selS, setSelS] = useState10(null);
    const [editP, setEditP] = useState10(false);
    const [studentProfileTab, setStudentProfileTab] = useState10("profile");
    const [busy, setBusy] = useState10(false);
    const [conn, setConn] = useState10(false);
    const [connErr, setConnErr] = useState10(null);
    const [accessDenied, setAccessDenied] = useState10(null);
    const [toast, setToast] = useState10(null);
    const [cmsNotifications, setCmsNotifications] = useState10([]);
    const [cmsNotificationUnreadCount, setCmsNotificationUnreadCount] = useState10(0);
    const [cmsNotificationOpen, setCmsNotificationOpen] = useState10(false);
    const [cmsNotificationError, setCmsNotificationError] = useState10("");
    const cmsNotificationCursorRef = useRef3(0);
    const cmsNotificationPollingRef = useRef3(false);
    const [confirmDialog, setConfirmDialog] = useState10(null);
    const [showSettings, setShowSettings] = useState10(initialCmsRoute.tab === "settings");
    const [userMenuOpen, setUserMenuOpen] = useState10(false);
    const [loggedIn, setLoggedIn] = useState10(false);
    const [pwOld, setPwOld] = useState10("");
    const [pwNew1, setPwNew1] = useState10("");
    const [pwNew2, setPwNew2] = useState10("");
    const [pwBusy, setPwBusy] = useState10(false);
    const [pwMsg, setPwMsg] = useState10(null);
    const [gOpen, setGOpen] = useState10(false);
    const [gQ, setGQ] = useState10("");
    const [portLB, setPortLB] = useState10(null);
    const [portUpload, setPortUpload] = useState10(false);
    const [portUpFile, setPortUpFile] = useState10(null);
    const [portEdit, setPortEdit] = useState10(null);
    const [portBusy, setPortBusy] = useState10(false);
    const portLightboxDialogRef = useRef3(null);
    const portUploadDialogRef = useRef3(null);
    const portEditDialogRef = useRef3(null);
    const searchDialogRef = useRef3(null);
    const settingsDialogRef = useRef3(null);
    const profileDialogRef = useRef3(null);
    const [accessCodeResult, setAccessCodeResult] = useState10(null);
    const [consentEdit, setConsentEdit] = useState10(null);
    useEffect9(() => {
      setAccessCodeResult(null);
      setConsentEdit(null);
      setStudentProfileTab("profile");
    }, [selS?.id]);
    const lbTouchX = useRef3(0);
    const syncCmsRoute = useCallback9((patch = {}, replace = false) => {
      const current = readCmsRoute();
      const next = { ...current, ...patch };
      const url = new URL(window.location.href);
      const params = url.searchParams;
      if (next.tab && next.tab !== "dashboard") params.set("view", next.tab);
      else params.delete("view");
      params.delete("tab");
      if (next.tab === "pending" && next.pendingTab === "bookings") params.set("type", "booking");
      else if (next.tab === "pending" && next.pendingTab === "reports") params.set("type", "reports");
      else params.delete("type");
      if (next.tab === "settings" && next.settingsSection && next.settingsSection !== "account") params.set("section", next.settingsSection);
      else if (next.tab === "roster" && next.rosterSection && next.rosterSection !== "checkin") params.set("section", next.rosterSection);
      else params.delete("section");
      if (next.recordId && ["students", "pending", "works", "billing"].includes(next.tab)) params.set("id", next.recordId);
      else params.delete("id");
      const nextUrl = `${url.pathname}${params.toString() ? `?${params.toString()}` : ""}${url.hash}`;
      window.history[replace ? "replaceState" : "pushState"]({}, "", nextUrl);
    }, []);
    const setTab = useCallback9((nextTab, options = {}) => {
      const next = CMS_ROUTE_TABS.has(nextTab) ? nextTab : "dashboard";
      setTabState(next);
      setShowSettings(next === "settings");
      const nextRecordId = options.recordId || "";
      setRouteRecordId(nextRecordId);
      const patch = { tab: next, recordId: nextRecordId };
      if (next === "roster") {
        const scope = CMS_ROUTE_SECTIONS.roster;
        const section = scope.allowed.includes(options.section) ? options.section : scope.fallback;
        setRosterSectionState(section);
        patch.rosterSection = section;
      }
      syncCmsRoute(patch, !!options.replace);
    }, [syncCmsRoute]);
    const setPendingTab = useCallback9((nextPendingTab) => {
      const next = ["bookings", "reports"].includes(nextPendingTab) ? nextPendingTab : "registrations";
      setPendingTabState(next);
      setTabState("pending");
      setShowSettings(false);
      syncCmsRoute({ tab: "pending", pendingTab: next });
    }, [syncCmsRoute]);
    const setSettingsSection = useCallback9((nextSection) => {
      setSettingsSectionState(nextSection);
      setTabState("settings");
      setShowSettings(true);
      syncCmsRoute({ tab: "settings", settingsSection: nextSection });
    }, [syncCmsRoute]);
    const setRosterSection = useCallback9((nextSection) => {
      setRosterSectionState(nextSection);
      setTabState("roster");
      setShowSettings(false);
      syncCmsRoute({ tab: "roster", rosterSection: nextSection });
    }, [syncCmsRoute]);
    useEffect9(() => {
      const onPopState = () => {
        const next = readCmsRoute();
        setTabState(next.tab);
        setPendingTabState(next.pendingTab);
        setSettingsSectionState(next.settingsSection);
        setRosterSectionState(next.rosterSection);
        setRouteRecordId(next.recordId);
        setShowSettings(next.tab === "settings");
        setUserMenuOpen(false);
      };
      window.addEventListener("popstate", onPopState);
      return () => window.removeEventListener("popstate", onPopState);
    }, []);
    useModalFocus(Boolean(portLB) && !confirmDialog, () => setPortLB(null), portLightboxDialogRef);
    useModalFocus(Boolean(portUpload) && !confirmDialog, () => {
      if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
      setPortUpload(false);
      setPortUpFile(null);
    }, portUploadDialogRef);
    useModalFocus(Boolean(portEdit) && !confirmDialog, () => setPortEdit(null), portEditDialogRef);
    useModalFocus(Boolean(gOpen) && !confirmDialog, () => {
      setGOpen(false);
      setGQ("");
    }, searchDialogRef);
    useModalFocus(
      Boolean(selS) && !portLB && !portUpload && !portEdit && !confirmDialog,
      () => {
        setSelS(null);
        setEditP(false);
      },
      profileDialogRef
    );
    const [inactiveDays, setInactiveDays] = useState10(() => parseInt(localStorage.getItem("lp_inactive_days") || "90", 10));
    const saveInactiveDays = (v) => {
      const n = parseInt(v, 10);
      if (n > 0) {
        setInactiveDays(n);
        localStorage.setItem("lp_inactive_days", String(n));
      }
    };
    const [srch, setSrch] = useState10("");
    const [sortBy, setSortBy] = useState10("date-desc");
    const [filterBy, setFilterBy] = useState10("all");
    const STUDENTS_PER_PAGE = 24;
    const [studentPage, setStudentPage] = useState10(1);
    const [selectedStudentIds, setSelectedStudentIds] = useState10([]);
    const [rDate, setRDate] = useState10(todayISO);
    const [rPick, setRPick] = useState10(null);
    const [defaultClassTime, setDefaultClassTime] = useState10("14:30");
    const [defaultClassTimeDraft, setDefaultClassTimeDraft] = useState10("14:30");
    const [operationalSettingsBusy, setOperationalSettingsBusy] = useState10(false);
    const [rTime, setRTime] = useState10("14:30");
    const [icsPreview, setIcsPreview] = useState10(null);
    const [icsNotice, setIcsNotice] = useState10("");
    const [icsBusy, setIcsBusy] = useState10(false);
    const icsDialogRef = useRef3(null);
    const icsCloseButtonRef = useRef3(null);
    const [rOneToOne, setROneToOne] = useState10(false);
    const [grpSel, setGrpSel] = useState10("");
    const [schedules, setSchedules] = useState10([]);
    const [scheduleLoadError, setScheduleLoadError] = useState10("");
    const [bizStats, setBizStats] = useState10(null);
    const [attHistory, setAttHistory] = useState10(null);
    const [schedEdit, setSchedEdit] = useState10(null);
    const [schedPick, setSchedPick] = useState10(null);
    const [courses, setCourses] = useState10([]);
    const [schedCancel, setSchedCancel] = useState10(null);
    const [bookings, setBookings] = useState10([]);
    const [courseEdit, setCourseEdit] = useState10(null);
    const [renewTh, setRenewTh] = useState10(() => parseInt(localStorage.getItem("lp_renew_threshold") || "2", 10));
    const saveRenewTh = (v) => {
      const n = parseInt(v, 10);
      if (n >= 0) {
        setRenewTh(n);
        localStorage.setItem("lp_renew_threshold", String(n));
      }
    };
    const [tuStu, setTuStu] = useState10(null);
    const [settleMode, setSettleMode] = useState10("topup");
    const [rfCr, setRfCr] = useState10("");
    const [rfAmt, setRfAmt] = useState10("");
    const [rfAmountTouched, setRfAmountTouched] = useState10(false);
    const [rfReason, setRfReason] = useState10("");
    const [rfSourceId, setRfSourceId] = useState10("");
    const [refundSources, setRefundSources] = useState10([]);
    const [refundSourcesBusy, setRefundSourcesBusy] = useState10(false);
    const [refundSourceError, setRefundSourceError] = useState10("");
    const [rfAdjustDocuments, setRfAdjustDocuments] = useState10(false);
    const [tuCr, setTuCr] = useState10("");
    const [tuFee, setTuFee] = useState10("");
    const [tuPkg, setTuPkg] = useState10("");
    const [tuPay, setTuPay] = useState10("微信");
    const [tuCreateInvoice, setTuCreateInvoice] = useState10(false);
    const [tuPaymentReceived, setTuPaymentReceived] = useState10(true);
    const [settlementAccounts, setSettlementAccounts] = useState10([]);
    const [settlementTaxCodes, setSettlementTaxCodes] = useState10([]);
    const [settlementPayerState, setSettlementPayerState] = useState10({
      mode: "student",
      accountId: "",
      createPayload: null,
      linkedStudentIds: []
    });
    const [settlementPayerError, setSettlementPayerError] = useState10("");
    const settlementResolvedAccountRef = useRef3("");
    const settlementPayerIntentRef = useRef3("");
    const settlementRequestRef = useRef3({ signature: "", id: "" });
    const refundRequestRef = useRef3({ signature: "", id: "" });
    const [lSrch, setLSrch] = useState10("");
    const [lStu, setLStu] = useState10(null);
    const [lAct, setLAct] = useState10("");
    const [lDateFrom, setLDateFrom] = useState10("");
    const [lDateTo, setLDateTo] = useState10("");
    const [lPage, setLPage] = useState10(1);
    const LPP = 30;
    const [sPeriod, setSPeriod] = useState10("monthly");
    const [sYear, setSYear] = useState10(String((/* @__PURE__ */ new Date()).getFullYear()));
    const [sFrom, setSFrom] = useState10("");
    const [sTo, setSTo] = useState10("");
    const [sStu, setSStu] = useState10(null);
    const [sStu2, setSStu2] = useState10(null);
    const [approveCredits, setApproveCredits] = useState10({});
    const [dupPick, setDupPick] = useState10(null);
    const [arSummary, setArSummary] = useState10(null);
    const [followUpDates, setFollowUpDates] = useState10({});
    const [pkgEditId, setPkgEditId] = useState10(null);
    const [pkgName, setPkgName] = useState10("");
    const [pkgCredits, setPkgCredits] = useState10("");
    const [pkgPrice, setPkgPrice] = useState10("");
    const [tenantBrand, setTenantBrand] = useState10(() => window.STUDIOSAAS_BRAND || {});
    const [team, setTeam] = useState10([]);
    const [teamBusy, setTeamBusy] = useState10(false);
    const [teamForm, setTeamForm] = useState10({ fullName: "", email: "", role: "teacher", temporaryPassword: "" });
    const [actorRole, setActorRole] = useState10("");
    const ownerRoles = ["owner", "platform_super_admin", "super_admin"];
    const roleTabs = {
      owner: ["dashboard", "pending", "roster", "courses", "students", "works", "new_student", "billing", "topup", "finance", "logs", "stats", "settings"],
      platform_super_admin: ["dashboard", "pending", "roster", "courses", "students", "works", "new_student", "billing", "topup", "finance", "logs", "stats", "settings"],
      super_admin: ["dashboard", "pending", "roster", "courses", "students", "works", "new_student", "billing", "topup", "finance", "logs", "stats", "settings"],
      manager: ["dashboard", "pending", "roster", "courses", "students", "works", "new_student", "billing", "topup", "finance", "logs", "stats", "settings"],
      teacher: ["dashboard", "roster", "courses", "students", "works", "logs", "settings"],
      /* 前台带 roster。后端早就给了 scheduling:write（一对一循环课、停课、
         补课），本轮又加了 attendance:write —— 但这一页不在名单里，那两个
         权限在界面上就是死的：canWriteScheduling 里的 front_desk 只在
         RosterSection 内部被消费，而前台打开 ?view=roster 会被踢回工作台。 */
      front_desk: ["dashboard", "pending", "roster", "students", "new_student", "billing", "topup", "logs", "settings"],
      /* 助教 = 老师的可见面，一个不多。ROLE_PERMISSIONS 里 STAFF ⊂ TEACHER，
         这一行是它在导航上的对应物；以前 staff 比 teacher 多出待处理、
         新建学员、账单和充值四项，正好是它不该有的那几件。 */
      staff: ["dashboard", "roster", "courses", "students", "works", "logs", "settings"]
    };
    const allowedTabs = roleTabs[actorRole] || ["dashboard"];
    const canManageOperations = [...ownerRoles, "manager"].includes(actorRole);
    const canExportData = [...ownerRoles, "manager"].includes(actorRole);
    const canViewFinancialAnalytics = [...ownerRoles, "manager"].includes(actorRole);
    const canWriteStudents = [...ownerRoles, "manager", "front_desk"].includes(actorRole);
    const canWriteCredits = [...ownerRoles, "manager", "front_desk"].includes(actorRole);
    const canUseSettlementBilling = TENANT_SLUG && ["owner", "manager", "front_desk", "platform_super_admin", "super_admin"].includes(actorRole);
    const canRegisterSettlementPayment = TENANT_SLUG && ["owner", "manager", "front_desk", "platform_super_admin", "super_admin"].includes(actorRole);
    const canWritePortfolio = [...ownerRoles, "manager", "teacher", "staff"].includes(actorRole);
    const canWriteScheduling = [...ownerRoles, "manager", "front_desk"].includes(actorRole);
    const canWriteProgress = [...ownerRoles, "manager", "teacher"].includes(actorRole);
    const canPublishProgress = [...ownerRoles, "manager"].includes(actorRole);
    const canWriteAttendance = [...ownerRoles, "manager", "teacher", "staff", "front_desk"].includes(actorRole);
    const canReviewBookings = [...ownerRoles, "manager", "front_desk"].includes(actorRole);
    const canRefund = [...ownerRoles, "manager"].includes(actorRole);
    const canSyncRefund = TENANT_SLUG && ["owner", "manager", "platform_super_admin", "super_admin"].includes(actorRole);
    const canViewCmsNotifications = ["owner", "manager", "front_desk", "platform_super_admin", "super_admin"].includes(actorRole);
    const SETTINGS_SECTIONS = [
      ["account", "账号与安全", true],
      ["team", "团队与权限", canManageOperations],
      ["operational", "运营默认", canManageOperations],
      ["billing-identity", "开票信息", canManageOperations],
      ["integrations", "集成", ownerRoles.includes(actorRole)],
      ["maintenance", "数据维护", canManageOperations],
      ["workspace", "工作区链接", true]
    ];
    useEffect9(() => {
      if (tab !== "settings" || !actorRole) return;
      const visible = SETTINGS_SECTIONS.filter(([, , ok]) => ok !== false).map(([key]) => key);
      if (!visible.length) return;
      const resolved = visible.includes(settingsSection) ? settingsSection : visible[0];
      const raw = new URLSearchParams(window.location.search || "").get("section") || "account";
      if (resolved !== settingsSection) setSettingsSectionState(resolved);
      if (raw !== resolved) syncCmsRoute({ tab: "settings", settingsSection: resolved }, true);
    }, [tab, settingsSection, actorRole, canManageOperations]);
    const [formPhoto, setFormPhoto] = useState10("");
    const [editPhoto, setEditPhoto] = useState10("");
    const cooldowns = useRef3(/* @__PURE__ */ new Set());
    const wasDownRef = useRef3(false);
    const showToast = (msg, type = "success", action = null) => setToast({ msg, type, action, key: Date.now() });
    useEffect9(() => {
      const syncBrand = (event) => setTenantBrand(event?.detail || window.STUDIOSAAS_BRAND || {});
      window.addEventListener("studiosaas:brand", syncBrand);
      syncBrand();
      return () => window.removeEventListener("studiosaas:brand", syncBrand);
    }, []);
    useEffect9(() => {
      if (!canUseSettlementBilling || tab !== "topup") return void 0;
      let alive = true;
      Promise.all([
        v1Api("/billing/accounts?limit=100").catch(() => ({ accounts: [] })),
        v1Api("/billing/tax-codes").catch(() => ({ taxCodes: [] }))
      ]).then(([accountsData, taxData]) => {
        if (!alive) return;
        setSettlementAccounts(accountsData.accounts || []);
        setSettlementTaxCodes((taxData.taxCodes || []).filter((code) => code.is_active !== false));
      });
      return () => {
        alive = false;
      };
    }, [canUseSettlementBilling, tab]);
    useEffect9(() => {
      if (!TENANT_SLUG || settleMode !== "refund" || !tuStu || !canRefund) {
        setRefundSources([]);
        setRefundSourcesBusy(false);
        setRefundSourceError("");
        setRfSourceId("");
        setRfAdjustDocuments(false);
        return void 0;
      }
      let alive = true;
      setRefundSourcesBusy(true);
      setRefundSourceError("");
      v1Api(`/students/${encodeURIComponent(tuStu)}/credit-refunds`).then((data) => {
        if (!alive) return;
        const sources = data.sources || [];
        setRefundSources(sources);
        if (!sources.some((source) => String(source.sourceTransactionId) === String(rfSourceId))) setRfSourceId("");
      }).catch((error) => {
        if (alive) setRefundSourceError(`可退充值加载失败：${error.message}`);
      }).finally(() => {
        if (alive) setRefundSourcesBusy(false);
      });
      return () => {
        alive = false;
      };
    }, [settleMode, tuStu, canRefund]);
    useEffect9(() => {
      if (TENANT_SLUG && canManageOperations) loadTeam();
    }, [actorRole]);
    useEffect9(() => {
      if (showSettings && TENANT_SLUG && canManageOperations) loadTeam();
    }, [showSettings]);
    useEffect9(() => {
      if (actorRole && !allowedTabs.includes(tab)) setTab("dashboard");
    }, [actorRole, tab]);
    const tenantLogoUrl = tenantOwnedLogoUrl(tenantBrand);
    const tenantDisplayName = tenantBrand.name || tenantBrand.studioName || "Studio";
    const venueNoun = (tenantBrand.venue_noun || tenantBrand.venueNoun || {}).zh || "工作室";
    const workNoun = (tenantBrand.work_noun || tenantBrand.workNoun || {}).zh || "作品";
    const messageTemplates = tenantBrand.message_templates || tenantBrand.messageTemplates || {};
    const renderMessage = (key, fallback, values = {}) => {
      const template = String(messageTemplates[key] || fallback);
      return Object.keys({ studio: tenantDisplayName, venue: venueNoun, work: workNoun, ...values }).reduce((text, name) => text.split(`{${name}}`).join(
        String({ studio: tenantDisplayName, venue: venueNoun, work: workNoun, ...values }[name] ?? "")
      ), template);
    };
    const preferenceProfile = () => {
      const raw = tenantBrand.registration_profile || tenantBrand.registrationProfile || {};
      const fields = Array.isArray(raw.fields) && raw.fields.length ? raw.fields : [
        { key: "interests", label: "Interests", placeholder: "What does the student enjoy?" },
        { key: "experience", label: "Experience", placeholder: "Beginner, some experience, advanced" },
        { key: "goals", label: "Goals", placeholder: "Confidence, skills, exam prep, fun" }
      ];
      return {
        title: raw.title || "Student Preferences",
        fields: fields.filter((f) => f && f.key && f.label).map((f) => ({
          key: String(f.key).trim(),
          label: String(f.label).trim(),
          placeholder: String(f.placeholder || "").trim()
        }))
      };
    };
    const preferenceValue = (source, key) => {
      const prefs = source?.preferences && typeof source.preferences === "object" ? source.preferences : {};
      return prefs[key] ?? source?.[key] ?? "";
    };
    const collectPreferences = (fd) => {
      const prefs = {};
      preferenceProfile().fields.forEach((field) => {
        prefs[field.key] = (fd.get(`pref_${field.key}`) || "").trim();
      });
      return prefs;
    };
    const legacyPreferenceKeys = ["artStyle", "favArtist", "experience", "goals"];
    const legacyPreferenceValues = (prefs, fd = null, source = null) => {
      const out = {};
      legacyPreferenceKeys.forEach((key) => {
        out[key] = (prefs[key] || (fd ? fd.get(key) : "") || source?.[key] || "").trim();
      });
      return out;
    };
    const preferenceRows = (source) => {
      const prefs = source?.preferences && typeof source.preferences === "object" ? source.preferences : {};
      return preferenceProfile().fields.map((field) => ({ ...field, value: prefs[field.key] ?? source?.[field.key] ?? "" })).filter((row) => row.value);
    };
    const copyText = (str, successMsg) => {
      const onOk = () => showToast(successMsg || "已复制");
      const onFail = () => showToast("复制失败，请手动复制", "error");
      const doFallback = () => {
        try {
          const ta = document.createElement("textarea");
          ta.value = str;
          ta.style.cssText = "position:fixed;opacity:0;top:0;left:0;pointer-events:none;";
          document.body.appendChild(ta);
          ta.focus();
          ta.select();
          const copied = document.execCommand("copy");
          document.body.removeChild(ta);
          copied ? onOk() : onFail();
        } catch (e) {
          onFail();
        }
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(str).then(onOk).catch(doFallback);
      } else {
        doFallback();
      }
    };
    const confirm2 = (message, onConfirm, opts = {}) => setConfirmDialog({ message, onConfirm, ...opts });
    const notify = (message, opts = {}) => setConfirmDialog({ message, acknowledge: true, ...opts });
    const loadTeam = async () => {
      if (!TENANT_SLUG) return;
      try {
        const data = await v1Api("/team");
        setTeam(data.team || []);
      } catch (e) {
        setTeam([]);
        showToast(`团队成员加载失败：${e.message}`, "error");
      }
    };
    const createTeamMember = async () => {
      if (teamBusy) return;
      if (!teamForm.fullName.trim() || !teamForm.email.trim() || teamForm.temporaryPassword.length < 8) {
        showToast("请填写姓名、邮箱和至少8位临时密码", "warn");
        return;
      }
      setTeamBusy(true);
      try {
        await v1Api("/team", { method: "POST", body: JSON.stringify(teamForm) });
        setTeamForm({ fullName: "", email: "", role: "teacher", temporaryPassword: "" });
        await loadTeam();
        showToast("团队成员已添加，请通过安全渠道发送临时密码");
      } catch (e) {
        showToast(`添加失败：${e.message}`, "error");
      } finally {
        setTeamBusy(false);
      }
    };
    const updateTeamMember = async (member, status) => {
      if (teamBusy || member.role === "owner") return;
      setTeamBusy(true);
      try {
        await v1Api(`/team/${member.id}`, { method: "PATCH", body: JSON.stringify({ role: member.role, status }) });
        await loadTeam();
        showToast(status === "active" ? "成员已启用" : "成员已停用");
      } catch (e) {
        showToast(`更新失败：${e.message}`, "error");
      } finally {
        setTeamBusy(false);
      }
    };
    const updateTeamPublicity = async (member, patch) => {
      if (teamBusy || member.role === "owner") return;
      setTeamBusy(true);
      try {
        await v1Api(`/team/${member.id}`, { method: "PATCH", body: JSON.stringify({
          role: member.role,
          status: member.status,
          ...patch
        }) });
        await loadTeam();
        await loadSchedules();
        showToast(patch.showOnPublicTimetable === void 0 ? "对外显示名已保存" : patch.showOnPublicTimetable ? "已允许在公开课表显示姓名" : "已取消公开显示姓名");
      } catch (e) {
        showToast(`更新失败：${e.message}`, "error");
      } finally {
        setTeamBusy(false);
      }
    };
    useEffect9(() => {
      const h = (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "k") {
          e.preventDefault();
          setGOpen((o) => !o);
          setGQ("");
        }
      };
      window.addEventListener("keydown", h);
      return () => window.removeEventListener("keydown", h);
    }, []);
    useEffect9(() => {
      if (!icsPreview) return;
      const previousFocus = document.activeElement;
      const focusableSelector = [
        "button:not([disabled])",
        "[href]",
        "input:not([disabled])",
        "select:not([disabled])",
        "textarea:not([disabled])",
        '[tabindex]:not([tabindex="-1"])'
      ].join(",");
      const onKey = (e) => {
        if (e.key === "Escape") {
          e.preventDefault();
          setIcsPreview(null);
          return;
        }
        if (e.key !== "Tab") return;
        const focusable = [...icsDialogRef.current?.querySelectorAll(focusableSelector) || []];
        if (!focusable.length) {
          e.preventDefault();
          return;
        }
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      };
      document.addEventListener("keydown", onKey);
      const timer = setTimeout(() => icsCloseButtonRef.current?.focus(), 0);
      return () => {
        document.removeEventListener("keydown", onKey);
        clearTimeout(timer);
        if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
      };
    }, [icsPreview]);
    useEffect9(() => {
      const onKey = (e) => {
        if (portLB) {
          if (e.key === "ArrowRight") setPortLB((p) => p && p.idx < p.items.length - 1 ? { ...p, idx: p.idx + 1 } : p);
          if (e.key === "ArrowLeft") setPortLB((p) => p && p.idx > 0 ? { ...p, idx: p.idx - 1 } : p);
        }
      };
      window.addEventListener("keydown", onKey);
      return () => window.removeEventListener("keydown", onKey);
    }, [portLB]);
    useEffect9(() => {
      setAttHistory(null);
      if (!TENANT_SLUG || !selS?.id) return;
      let alive = true;
      v1Api(`/attendance?studentId=${encodeURIComponent(selS.id)}&limit=20`).then((d) => {
        if (alive) setAttHistory(d.attendance || []);
      }).catch(() => {
        if (alive) setAttHistory([]);
      });
      return () => {
        alive = false;
      };
    }, [selS?.id]);
    const refreshSession = () => fetch("/v1/auth/me", { credentials: "include" }).then((r) => r.json()).then((d) => {
      const memberships = d.memberships || [];
      const platformMembership = memberships.find((m) => !m.tenant_slug && ["platform_super_admin", "super_admin"].includes(m.role));
      const tenantMembership = memberships.find((m) => m.tenant_slug === tenantSlug);
      const effectiveRole = platformMembership?.role || tenantMembership?.role || "";
      if (d.ok && ["owner", "manager", "teacher", "front_desk", "staff", "platform_super_admin", "super_admin"].includes(effectiveRole)) {
        setActorRole(effectiveRole);
        setLoggedIn(true);
      }
    }).catch(() => {
    });
    useEffect9(() => {
      refreshSession();
    }, []);
    const apiHeaders = () => ({ "Content-Type": "application/json" });
    const revRef = useRef3(0);
    useEffect9(() => {
      if (loggedIn) load();
    }, [loggedIn]);
    useEffect9(() => {
      if (tab !== "dashboard" || !TENANT_SLUG || !canUseSettlementBilling) return;
      let gone = false;
      v1Api("/billing/invoices").then((d) => {
        if (gone) return;
        const issued = (d.invoices || []).filter((i) => i.status !== "draft" && i.status !== "void");
        const unpaid = issued.filter((i) => Number(i.balance_cents) > 0);
        setArSummary({
          unpaidCents: unpaid.reduce((s, i) => s + Number(i.balance_cents || 0), 0),
          unpaidCount: unpaid.length,
          overdueCount: unpaid.filter(isOverdue).length
        });
      }).catch(() => {
        if (!gone) setArSummary(null);
      });
      return () => {
        gone = true;
      };
    }, [tab, loggedIn]);
    useEffect9(() => {
      if (!loggedIn) return;
      const id = setInterval(async () => {
        try {
          const r = await fetch("/api/ping");
          if (r.ok) {
            if (wasDownRef.current) {
              wasDownRef.current = false;
              load();
              showToast("已重新连接，数据已刷新");
            }
          } else {
            wasDownRef.current = true;
            setConn(false);
          }
        } catch {
          wasDownRef.current = true;
          setConn(false);
        }
      }, 3e4);
      return () => clearInterval(id);
    }, [loggedIn]);
    useEffect9(() => {
      if (!loggedIn || !TENANT_SLUG || !canViewCmsNotifications) {
        setCmsNotifications([]);
        setCmsNotificationUnreadCount(0);
        cmsNotificationCursorRef.current = 0;
        setCmsNotificationOpen(false);
        setCmsNotificationError("");
        return void 0;
      }
      let alive = true;
      cmsNotificationCursorRef.current = 0;
      const mergeNotifications = (incoming, replace = false) => {
        setCmsNotifications((previous) => {
          const byId = new Map((replace ? [] : previous).map((item) => [item.id, item]));
          incoming.forEach((item) => byId.set(item.id, item));
          return Array.from(byId.values()).sort((a, b) => Number(b.sequence || 0) - Number(a.sequence || 0)).slice(0, 50);
        });
      };
      const poll = async (initial = false) => {
        if (!alive || cmsNotificationPollingRef.current) return;
        cmsNotificationPollingRef.current = true;
        const cursor = cmsNotificationCursorRef.current;
        try {
          const query = initial ? "?limit=30" : `?after=${encodeURIComponent(String(cursor))}&limit=30`;
          const data = await v1Api(`/notifications${query}`);
          if (!alive) return;
          const incoming = Array.isArray(data.notifications) ? data.notifications : [];
          mergeNotifications(incoming, initial);
          const nextCursor = Number(data.nextCursor ?? data.cursor ?? cursor);
          if (Number.isFinite(nextCursor) && nextCursor >= cursor) {
            cmsNotificationCursorRef.current = nextCursor;
          }
          setCmsNotificationUnreadCount(Number(data.unreadCount || 0));
          setCmsNotificationError("");
          if (!initial && incoming.length > 0) {
            const latest = incoming[incoming.length - 1];
            showToast(`${latest.title} · ${latest.summary}`, "warn", {
              label: "查看通知",
              onClick: () => setCmsNotificationOpen(true)
            });
          }
        } catch (error) {
          if (alive) setCmsNotificationError(error?.message || "通知暂时无法更新");
        } finally {
          cmsNotificationPollingRef.current = false;
        }
      };
      poll(true);
      const id = setInterval(() => {
        if (document.visibilityState !== "hidden") poll(false);
      }, 3e4);
      const onVisibility = () => {
        if (document.visibilityState === "visible") poll(false);
      };
      document.addEventListener("visibilitychange", onVisibility);
      return () => {
        alive = false;
        clearInterval(id);
        document.removeEventListener("visibilitychange", onVisibility);
      };
    }, [loggedIn, actorRole]);
    const markCmsNotificationRead = async (notification) => {
      try {
        const data = await v1Api(`/notifications/${encodeURIComponent(notification.id)}/read`, {
          method: "POST",
          body: JSON.stringify({})
        });
        setCmsNotifications((previous) => previous.map((item) => item.id === notification.id ? { ...item, read: true } : item));
        setCmsNotificationUnreadCount(Number(data.unreadCount || 0));
        return true;
      } catch {
        showToast("通知状态更新失败", "error");
        return false;
      }
    };
    const openCmsNotification = async (notification) => {
      const marked = notification.read || await markCmsNotificationRead(notification);
      if (!marked) return;
      setCmsNotificationOpen(false);
      if (notification.targetTab && allowedTabs.includes(notification.targetTab)) {
        if (notification.targetTab === "pending" && notification.targetSubtab) {
          setPendingTab(notification.targetSubtab);
        } else {
          setTab(notification.targetTab, { recordId: notification.targetId || notification.recordId || "" });
        }
      }
    };
    const markAllCmsNotificationsRead = async () => {
      try {
        const data = await v1Api("/notifications/read-all", {
          method: "POST",
          body: JSON.stringify({})
        });
        setCmsNotifications((previous) => previous.map((item) => ({ ...item, read: true })));
        setCmsNotificationUnreadCount(Number(data.unreadCount || 0));
      } catch {
        showToast("通知状态更新失败", "error");
      }
    };
    const doLogout = async () => {
      await fetch("/v1/auth/logout", { method: "POST", credentials: "include" }).catch(() => {
      });
      setLoggedIn(false);
      setConn(false);
      setDb({ students: [], logs: [], rosters: {}, pending: [] });
      setShowSettings(false);
      setCmsNotificationOpen(false);
      setCmsNotifications([]);
      setCmsNotificationUnreadCount(0);
    };
    const changeWebPw = async () => {
      if (!pwOld || !pwNew1) {
        setPwMsg({ text: "请填写旧密码和新密码", tone: "error" });
        return;
      }
      if (pwNew1 !== pwNew2) {
        setPwMsg({ text: "两次新密码不一致", tone: "error" });
        return;
      }
      if (pwNew1.length < 8) {
        setPwMsg({ text: "新密码至少 8 位", tone: "error" });
        return;
      }
      setPwBusy(true);
      setPwMsg(null);
      try {
        const r = await fetch("/v1/auth/change-password", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ oldPassword: pwOld, newPassword: pwNew1 }),
          credentials: "include"
        });
        const d = await r.json();
        if (d.ok) {
          setPwOld("");
          setPwNew1("");
          setPwNew2("");
          setPwMsg({ text: "密码已更新", tone: "ok" });
        } else {
          setPwMsg({ text: String(d.message || d.error || "修改失败"), tone: "error" });
        }
      } catch {
        setPwMsg({ text: "连接失败", tone: "error" });
      } finally {
        setPwBusy(false);
      }
    };
    const load = async () => {
      setBusy(true);
      setConnErr(null);
      setAccessDenied(null);
      try {
        const r = await fetch("/api/data", { credentials: "include" });
        if (r.status === 401) {
          setLoggedIn(false);
          setBusy(false);
          return;
        }
        if (r.status === 403) {
          const body = await r.json().catch(() => ({}));
          setAccessDenied({ code: body.error || "forbidden", message: body.message || "" });
          setBusy(false);
          return;
        }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const d = await r.json();
        if (!d.rosters) d.rosters = {};
        d.students = d.students.map((s) => ({
          email: "",
          wechat: "",
          archived: false,
          firstName: s.name || "",
          lastName: "",
          photo: "",
          experience: "",
          goals: "",
          preferences: {},
          birthday: "",
          ...s
        }));
        if (!d.pending) d.pending = [];
        if (!d.packages) d.packages = [{ id: 1, name: "标准课包", credits: 10, price: 1200 }];
        const nextDefaultClassTime = d.operationalSettings?.defaultClassTime || "14:30";
        setDefaultClassTime(nextDefaultClassTime);
        setDefaultClassTimeDraft(nextDefaultClassTime);
        setRTime((current) => current === "14:30" ? nextDefaultClassTime : current || nextDefaultClassTime);
        revRef.current = d.rev || 1;
        setDb(d);
        setConn(true);
        loadSchedules();
        loadAuditEvents();
      } catch (e) {
        setConnErr(e.message);
      } finally {
        setBusy(false);
      }
    };
    const save = async (nd, force = false) => {
      setDb(nd);
      try {
        const body = { ...nd, rev: revRef.current, ...force ? { force: true } : {} };
        const r = await fetch("/api/save", {
          method: "POST",
          headers: apiHeaders(),
          credentials: "include",
          body: JSON.stringify(body)
        });
        if (r.status === 401) {
          showToast("登录已过期，请重新登录 / Session expired", "error");
          setTimeout(doLogout, 1500);
          return false;
        }
        if (r.status === 403) {
          showToast("无权保存此租户数据 / No permission for this tenant.", "error");
          setTimeout(load, 800);
          return false;
        }
        if (r.status === 409) {
          const d2 = await r.json().catch(() => ({}));
          if (d2.status === "conflict") {
            showToast("数据已在其他设备/标签页被修改，正在刷新…", "error");
            setTimeout(load, 800);
          } else if (d2.status === "shrink_guard") {
            confirm2(
              `安全拦截：${d2.message || `数据量将从 ${d2.current} 减少到 ${d2.incoming}`} 如果这不是你刻意删除的结果，请选择取消并刷新页面！`,
              async () => save(nd, true),
              { danger: true, confirmText: "我确认，继续保存" }
            );
          }
          return false;
        }
        if (!r.ok) throw new Error("save failed");
        const d = await r.json().catch(() => null);
        if (d && d.rev) {
          revRef.current = d.rev;
          setDb((prev) => ({ ...prev, rev: d.rev }));
        }
        return true;
      } catch (err) {
        if (!String(err).includes("401")) showToast("数据未能同步到服务器！", "error");
        return false;
      }
    };
    const exportDB = () => {
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([JSON.stringify(db, null, 2)], { type: "application/json" }));
      a.download = `Studio_${todayISO()}.json`;
      a.click();
    };
    const activityMap = useMemo6(() => {
      const map = {};
      const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1e3;
      const idsByName = /* @__PURE__ */ new Map();
      db.students.forEach((student) => {
        const ids = idsByName.get(student.name) || [];
        ids.push(student.id);
        idsByName.set(student.name, ids);
      });
      db.logs.forEach((l) => {
        if (l.action !== "上课签到") return;
        const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        if (m) {
          const d = /* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}`);
          if (!isNaN(d) && d.getTime() >= cutoff) {
            const legacyIds = idsByName.get(l.studentName) || [];
            const key = l.studentId || (legacyIds.length === 1 ? legacyIds[0] : "");
            if (key) map[key] = (map[key] || 0) + 1;
          }
        }
      });
      return map;
    }, [db.logs, db.students]);
    const getTag = (s) => {
      const cnt = activityMap[s.id] || 0;
      if (cnt >= 4) return { icon: "bolt", label: "活跃", cls: "bg-red-100 text-red-700" };
      if (cnt >= 1) return { icon: "clock", label: "低频", cls: "bg-gray-100 text-gray-500" };
      if ((parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays)
        return { icon: "warning", label: "流失风险", cls: "bg-orange-100 text-orange-600" };
      return null;
    };
    useEffect9(() => {
      setStudentPage(1);
      setSelectedStudentIds([]);
    }, [srch, sortBy, filterBy]);
    const sortedFiltered = useMemo6(() => {
      let list = [...db.students];
      if (filterBy === "archived") {
        list = list.filter((s) => s.archived);
      } else {
        if (!filterBy || filterBy === "all") list = list.filter((s) => !s.archived);
        if (filterBy === "active") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0);
        if (filterBy === "low") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && (parseInt(s.balance, 10) || 0) <= renewTh);
        if (filterBy === "zero") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) === 0);
        if (filterBy === "tag-hot") list = list.filter((s) => !s.archived && (activityMap[s.id] || 0) >= 4);
        if (filterBy === "tag-low") list = list.filter((s) => !s.archived && (activityMap[s.id] || 0) >= 1 && (activityMap[s.id] || 0) < 4);
        if (filterBy === "tag-risk") list = list.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays && (activityMap[s.id] || 0) === 0);
        if (filterBy === "portal-ready") list = list.filter((s) => !s.archived && !!s.mobile && !!s.hasAccessCode);
        if (filterBy === "portal-missing-mobile") list = list.filter((s) => !s.archived && !s.mobile);
        if (filterBy === "portal-disabled") list = list.filter((s) => !s.archived && !!s.mobile && !s.hasAccessCode);
        if (filterBy === "portal-content-blocked") list = list.filter((s) => !s.archived && (s.portfolio || []).length > 0 && (!s.mobile || !s.hasAccessCode));
        if (filterBy === "publication-live") list = list.filter((s) => !s.archived && (s.portfolio || []).some((item) => item.public || item.visibility === "shared"));
        if (filterBy === "publication-ready") list = list.filter((s) => !s.archived && s.publicationConsent?.status === "confirmed");
        if (filterBy === "publication-missing-consent") list = list.filter((s) => !s.archived && (s.portfolio || []).length > 0 && s.publicationConsent?.status !== "confirmed");
      }
      if (srch) {
        const q = srch.toLowerCase();
        list = list.filter(
          (s) => s.name.toLowerCase().includes(q) || (s.firstName || "").toLowerCase().includes(q) || (s.lastName || "").toLowerCase().includes(q) || (s.mobile || "").includes(srch) || (s.email || "").toLowerCase().includes(q) || (s.wechat || "").toLowerCase().includes(q)
        );
      }
      const cmp = (a, b, dir = 1) => {
        const an = a || "", bn = b || "";
        return dir * an.localeCompare(bn, "zh-CN");
      };
      if (sortBy === "name-az") list.sort((a, b) => cmp(a.name, b.name));
      if (sortBy === "name-za") list.sort((a, b) => cmp(b.name, a.name));
      if (sortBy === "last-az") list.sort((a, b) => {
        const r = cmp(a.lastName, b.lastName);
        return r !== 0 ? r : cmp(a.firstName, b.firstName);
      });
      if (sortBy === "last-za") list.sort((a, b) => {
        const r = cmp(b.lastName, a.lastName);
        return r !== 0 ? r : cmp(b.firstName, a.firstName);
      });
      if (sortBy === "bal-desc") list.sort((a, b) => (parseInt(b.balance, 10) || 0) - (parseInt(a.balance, 10) || 0));
      if (sortBy === "bal-asc") list.sort((a, b) => (parseInt(a.balance, 10) || 0) - (parseInt(b.balance, 10) || 0));
      if (sortBy === "date-desc") list.sort((a, b) => (b.lastActive || "").localeCompare(a.lastActive || ""));
      return list;
    }, [db.students, srch, sortBy, filterBy, activityMap, inactiveDays, renewTh]);
    const studentPageCount = Math.max(1, Math.ceil(sortedFiltered.length / STUDENTS_PER_PAGE));
    const pageStudents = useMemo6(() => {
      const page = Math.min(studentPage, studentPageCount);
      return sortedFiltered.slice((page - 1) * STUDENTS_PER_PAGE, page * STUDENTS_PER_PAGE);
    }, [sortedFiltered, studentPage, studentPageCount]);
    const selectedStudents = useMemo6(
      () => sortedFiltered.filter((s) => selectedStudentIds.includes(s.id)),
      [sortedFiltered, selectedStudentIds]
    );
    const toggleSelectStudent = (sid) => setSelectedStudentIds((prev) => prev.includes(sid) ? prev.filter((id) => id !== sid) : [...prev, sid]);
    const toggleSelectPage = (checked) => setSelectedStudentIds((prev) => {
      const ids = pageStudents.map((s) => s.id);
      return checked ? Array.from(/* @__PURE__ */ new Set([...prev, ...ids])) : prev.filter((id) => !ids.includes(id));
    });
    const sortedAZ = useMemo6(
      () => [...db.students].filter((s) => !s.archived).sort((a, b) => a.name.localeCompare(b.name, "zh-CN")),
      [db.students]
    );
    const portfolioEntries = useMemo6(
      () => db.students.filter((student) => !student.archived).flatMap((student) => (student.portfolio || []).map((item) => ({ student, item }))).sort((a, b) => String(b.item.date || "").localeCompare(String(a.item.date || ""))),
      [db.students]
    );
    const [worksQuery, setWorksQuery] = useState10("");
    const [worksBucket, setWorksBucket] = useState10("all");
    const worksIsShared = (item) => Boolean(item.public || item.visibility === "shared");
    const worksBuckets = useMemo6(() => {
      const consented = ({ student }) => student.publicationConsent?.status === "confirmed";
      return [
        { key: "all", label: "全部", count: portfolioEntries.length },
        { key: "shared", label: "已公开", count: portfolioEntries.filter(({ item }) => worksIsShared(item)).length },
        { key: "private", label: "未公开", count: portfolioEntries.filter(({ item }) => !worksIsShared(item)).length },
        { key: "noconsent", label: "待授权", count: portfolioEntries.filter((e) => !consented(e)).length }
      ];
    }, [portfolioEntries]);
    const worksVisible = useMemo6(() => {
      const needle = worksQuery.trim().toLowerCase();
      return portfolioEntries.filter(({ student, item }) => {
        if (worksBucket === "shared" && !worksIsShared(item)) return false;
        if (worksBucket === "private" && worksIsShared(item)) return false;
        if (worksBucket === "noconsent" && student.publicationConsent?.status === "confirmed") return false;
        if (!needle) return true;
        return [student.name, item.title, item.note].some((v) => String(v || "").toLowerCase().includes(needle));
      });
    }, [portfolioEntries, worksQuery, worksBucket]);
    useEffect9(() => {
      if (tab !== "students" || !routeRecordId) return;
      const student = db.students.find((item) => String(item.id) === String(routeRecordId));
      if (student && selS?.id !== student.id) {
        setSelS(student);
        setEditP(false);
      }
    }, [tab, routeRecordId, db.students]);
    const scheduledForDate = useMemo6(() => {
      if (!TENANT_SLUG || !schedules.length) return [];
      const wd = (/* @__PURE__ */ new Date(`${rDate}T12:00:00`)).getDay();
      return schedules.filter((sc) => sc.weekday === wd);
    }, [schedules, rDate]);
    const scheduledIdSet = useMemo6(
      () => new Set(scheduledForDate.flatMap((sc) => sc.students.map((st) => st.id))),
      [scheduledForDate]
    );
    const dayIds = useMemo6(() => {
      const manual = db.rosters[rDate] || [];
      return [.../* @__PURE__ */ new Set([...scheduledIdSet, ...manual])];
    }, [db.rosters, rDate, scheduledIdSet]);
    const todayEffectiveCount = useMemo6(() => {
      const manual = db.rosters[todayISO()] || [];
      const wd = (/* @__PURE__ */ new Date()).getDay();
      const sched = schedules.filter((sc) => sc.weekday === wd).flatMap((sc) => sc.students.map((st) => st.id));
      return (/* @__PURE__ */ new Set([...sched, ...manual])).size;
    }, [db.rosters, schedules]);
    const todayCheckedCount = useMemo6(() => {
      const d = todayISO().split("-");
      const prefix = `${d[2]}/${d[1]}/${d[0]}`;
      return new Set(db.logs.filter((l) => l.action === "上课签到" && String(l.date).startsWith(prefix)).map((l) => l.studentId || l.studentName)).size;
    }, [db.logs]);
    const availRoster = useMemo6(
      () => sortedAZ.filter((s) => !dayIds.includes(s.id)),
      [sortedAZ, dayIds]
    );
    const analytics = useMemo6(() => {
      const totalStudents = db.students.filter((s) => !s.archived).length;
      const totalBalance = db.students.reduce((a, b) => a + (parseInt(b.balance, 10) || 0), 0);
      const totalCheckins = db.logs.filter((l) => l.action === "上课签到").length;
      const totalRevenue = db.logs.reduce((s, l) => s + (parseFloat(l.feePaid) || 0), 0);
      const lowBalance = [...db.students].filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) <= 2).sort((a, b) => (parseInt(a.balance, 10) || 0) - (parseInt(b.balance, 10) || 0));
      const inactive = db.students.filter((s) => !s.archived && (parseInt(s.balance, 10) || 0) > 0 && daysSince(s.lastActive) > inactiveDays).sort((a, b) => daysSince(b.lastActive) - daysSince(a.lastActive));
      const todayRoster = db.rosters[todayISO()] || [];
      const allMonths = {}, allYears = {};
      db.logs.forEach((l) => {
        const mk = parseMonthKey(l.date);
        if (!mk) return;
        const yk = mk.split("-")[0];
        if (!allMonths[mk]) allMonths[mk] = { revenue: 0, checkins: 0, topups: 0 };
        if (!allYears[yk]) allYears[yk] = { revenue: 0, checkins: 0 };
        if (l.action === "上课签到") {
          allMonths[mk].checkins++;
          allYears[yk].checkins++;
        }
        if (l.feePaid) {
          allMonths[mk].revenue += parseFloat(l.feePaid);
          allYears[yk].revenue += parseFloat(l.feePaid);
        }
        if (l.action === "充值购课") allMonths[mk].topups++;
      });
      const monthlyReports = Object.keys(allMonths).sort().reverse().map((k) => ({ key: k, ...allMonths[k] }));
      const yearlyReports = Object.keys(allYears).sort().reverse().map((k) => ({ key: k, ...allYears[k] }));
      const availYears = Object.keys(allYears).sort().reverse();
      const now = /* @__PURE__ */ new Date();
      const chart12 = Array.from({ length: 12 }, (_, i) => {
        const d = new Date(now.getFullYear(), now.getMonth() - 11 + i, 1);
        const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        const mo = allMonths[k] || { revenue: 0, checkins: 0 };
        const lbl = `${String(d.getMonth() + 1).padStart(2, "0")}/${String(d.getFullYear()).slice(2)}`;
        return { k, l: lbl, rev: Math.round(mo.revenue), ci: mo.checkins };
      });
      const recentGroups = [];
      let curDateKey = null;
      for (const log of db.logs.slice(0, 30)) {
        const dk = String(log.date).split(",")[0];
        if (dk !== curDateKey) {
          curDateKey = dk;
          if (recentGroups.length >= 3) break;
          recentGroups.push({ date: dk, logs: [] });
        }
        if (recentGroups.length && recentGroups[recentGroups.length - 1].logs.length < 5)
          recentGroups[recentGroups.length - 1].logs.push(log);
      }
      return { totalStudents, totalBalance, totalCheckins, totalRevenue, lowBalance, inactive, todayRoster, monthlyReports, yearlyReports, availYears, chart12, recentGroups };
    }, [db, inactiveDays]);
    const statsData = useMemo6(() => {
      let logs = sStu ? db.logs.filter((l) => {
        const s = db.students.find((x) => x.id === sStu);
        return s && (l.studentId === s.id || !l.studentId && l.studentName === s.name);
      }) : db.logs;
      if (sPeriod === "custom") {
        const from = sFrom && sTo && sFrom > sTo ? sTo : sFrom;
        const to = sFrom && sTo && sFrom > sTo ? sFrom : sTo;
        logs = logs.filter((l) => {
          const mk = parseMonthKey(l.date);
          if (!mk) return false;
          return (!from || mk >= from) && (!to || mk <= to);
        });
      } else if (sPeriod === "monthly" && sYear !== "all") {
        logs = logs.filter((l) => {
          const mk = parseMonthKey(l.date);
          return mk && mk.startsWith(sYear);
        });
      }
      const byP = {};
      logs.forEach((l) => {
        const mk = parseMonthKey(l.date);
        if (!mk) return;
        const key = sPeriod === "yearly" ? mk.split("-")[0] : mk;
        if (!byP[key]) byP[key] = { revenue: 0, checkins: 0, topups: 0 };
        if (l.action === "上课签到") byP[key].checkins++;
        if (l.action === "充值购课") {
          byP[key].topups++;
        }
        if (l.feePaid) byP[key].revenue += parseFloat(l.feePaid);
      });
      const rows = Object.keys(byP).sort().reverse().map((k) => ({ key: k, ...byP[k] }));
      return { rows, totalRev: rows.reduce((s, r) => s + r.revenue, 0), totalCI: rows.reduce((s, r) => s + r.checkins, 0) };
    }, [db, sPeriod, sYear, sFrom, sTo, sStu]);
    const studentStats = useMemo6(() => {
      if (!sStu2) return null;
      const s = db.students.find((x) => x.id === sStu2);
      if (!s) return null;
      const logs = db.logs.filter((l) => l.studentId === s.id || !l.studentId && l.studentName === s.name);
      const totalSpent = logs.reduce((sum, l) => sum + (parseFloat(l.feePaid) || 0), 0);
      const checkins = logs.filter((l) => l.action === "上课签到").length;
      const topups = logs.filter((l) => l.action === "充值购课");
      const totalBought = topups.reduce((sum, l) => {
        const c = String(l.change).replace("+", "");
        return sum + (parseInt(c) || 0);
      }, 0);
      return {
        student: s,
        totalSpent,
        checkins,
        totalBought,
        topupCount: topups.length,
        first: logs.length ? logs[logs.length - 1].date : "",
        last: logs.length ? logs[0].date : "",
        logs
      };
    }, [db, sStu2]);
    const gResults = useMemo6(() => {
      if (!gQ.trim()) return [];
      const q = gQ.trim().toLowerCase();
      return db.students.filter((s) => !s.archived && (s.name.toLowerCase().includes(q) || (s.firstName || "").toLowerCase().includes(q) || (s.lastName || "").toLowerCase().includes(q) || (s.mobile || "").includes(q) || (s.wechat || "").toLowerCase().includes(q))).slice(0, 10);
    }, [db.students, gQ]);
    const logDateISO = (ds) => {
      const m = String(ds).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
      return m ? `${m[3]}-${m[2]}-${m[1]}` : "";
    };
    const auditAsLogs = useMemo6(() => {
      if (!TENANT_SLUG || !auditEvents.length) return [];
      const nameById = new Map(db.students.map((s) => [String(s.id), s.name]));
      return auditEvents.reduce((rows, ev) => {
        const label = AUDIT_ACTION_ZH[ev.action];
        if (!label) return rows;
        const meta = ev.metadata || {};
        const sid = ev.resourceType === "student" ? String(ev.resourceId || "") : String(Array.isArray(meta.students) && meta.students[0] || "");
        const when = new Date(ev.createdAt);
        if (isNaN(when.getTime())) return rows;
        const dd = String(when.getDate()).padStart(2, "0");
        const mm = String(when.getMonth() + 1).padStart(2, "0");
        rows.push({
          id: `audit-${ev.id}`,
          studentId: sid || null,
          studentName: nameById.get(sid) || "—",
          action: label,
          change: "0",
          feePaid: 0,
          note: auditNote(ev.action, meta),
          date: `${dd}/${mm}/${when.getFullYear()}, ${when.toTimeString().slice(0, 8)}`,
          actorEmail: ev.actorEmail || "",
          _ts: when.getTime()
        });
        return rows;
      }, []);
    }, [auditEvents, db.students]);
    const displayNote = (note) => {
      const s = String(note || "");
      if (/^Core opening balance import/i.test(s)) return "数据迁移期初余额";
      return s;
    };
    const logTimestamp = (l) => {
      if (typeof l._ts === "number") return l._ts;
      const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})(?:,\s*(\d{2}):(\d{2}):(\d{2}))?/);
      if (!m) return 0;
      const t = /* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}T${m[4] || "00"}:${m[5] || "00"}:${m[6] || "00"}`);
      return isNaN(t.getTime()) ? 0 : t.getTime();
    };
    const allLogs = useMemo6(() => auditAsLogs.length ? [...db.logs, ...auditAsLogs].sort((a, b) => logTimestamp(b) - logTimestamp(a)) : db.logs, [db.logs, auditAsLogs]);
    const filteredLogs = useMemo6(() => {
      const stuName = lStu ? (db.students.find((x) => x.id === lStu) || {}).name : null;
      return allLogs.filter((l) => {
        if (stuName && l.studentName !== stuName) return false;
        if (lSrch && !l.studentName.toLowerCase().includes(lSrch.toLowerCase())) return false;
        if (lAct && l.action !== lAct) return false;
        if (lDateFrom || lDateTo) {
          const iso3 = logDateISO(l.date);
          if (lDateFrom && iso3 < lDateFrom) return false;
          if (lDateTo && iso3 > lDateTo) return false;
        }
        return true;
      });
    }, [allLogs, db.students, lStu, lSrch, lAct, lDateFrom, lDateTo]);
    const logPageCount = Math.max(1, Math.ceil(filteredLogs.length / LPP));
    const pagedLogs = filteredLogs.slice((lPage - 1) * LPP, lPage * LPP);
    const logActions = useMemo6(() => [...new Set(allLogs.map((l) => l.action))].sort(), [allLogs]);
    useEffect9(() => {
      setLPage(1);
    }, [lStu, lSrch, lAct, lDateFrom, lDateTo]);
    useEffect9(() => {
      if (lPage > logPageCount) setLPage(logPageCount);
    }, [logPageCount]);
    const bizReport = useMemo6(() => {
      const now = /* @__PURE__ */ new Date();
      const months = Array.from({ length: 6 }, (_, i) => {
        const d = new Date(now.getFullYear(), now.getMonth() - 5 + i, 1);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
      });
      const rows = months.map((k) => ({
        k,
        label: `${k.split("-")[1]}/${k.split("-")[0].slice(2)}`,
        rev: 0,
        ci: 0,
        topups: 0,
        newStu: 0
      }));
      const byKey = Object.fromEntries(rows.map((r) => [r.k, r]));
      const pkgSales = {};
      db.logs.forEach((l) => {
        const mk = parseMonthKey(l.date);
        const r = mk && byKey[mk];
        if (r) {
          if (l.action === "上课签到") r.ci++;
          if (l.action === "充值购课") {
            r.topups++;
            r.rev += parseFloat(l.feePaid) || 0;
          }
          if (l.action === "新生注册" || l.action === "批准注册") r.newStu++;
        }
        if (l.action === "充值购课") {
          const m = String(l.note || "").match(/套餐:\s*([^|]+)/);
          const name = m ? m[1].trim() : "自定义";
          if (!pkgSales[name]) pkgSales[name] = { count: 0, revenue: 0 };
          pkgSales[name].count++;
          pkgSales[name].revenue += parseFloat(l.feePaid) || 0;
        }
      });
      const cutoff = Date.now() - 180 * 24 * 3600 * 1e3;
      const perStu = {};
      db.logs.forEach((l) => {
        if (l.action !== "上课签到") return;
        const m = String(l.date).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        if (!m) return;
        const t = (/* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}`)).getTime();
        if (t < cutoff) return;
        const key = l.studentId || l.studentName;
        (perStu[key] = perStu[key] || []).push(t);
      });
      let gaps = [];
      Object.values(perStu).forEach((ts) => {
        if (ts.length < 2) return;
        ts.sort((a, b) => a - b);
        for (let i = 1; i < ts.length; i++) gaps.push((ts[i] - ts[i - 1]) / 864e5);
      });
      const avgGap = gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 0;
      const pkgRank = Object.entries(pkgSales).sort((a, b) => b[1].revenue - a[1].revenue);
      return { rows, pkgRank, avgGap, regularStu: Object.values(perStu).filter((t) => t.length >= 2).length };
    }, [db.logs]);
    const exportBizCSV = () => {
      const head = ["月份", "营收(AUD)", "充值笔数", "消课次数", "新增学员"];
      const lines = bizReport.rows.map((r) => [r.label, r.rev.toFixed(0), r.topups, r.ci, r.newStu]);
      const pkg = bizReport.pkgRank.map(([n, d]) => ["课包:" + n, d.revenue.toFixed(0), d.count, "", ""]);
      const csv = [head, ...lines, [], ["课包销量排行", "营收", "笔数"], ...pkg].map((r) => r.join(",")).join("\n");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }));
      a.download = `Studio_经营月报_${todayISO()}.csv`;
      a.click();
    };
    const payBreakdown = useMemo6(() => {
      const map = {};
      db.logs.filter((l) => l.action === "充值购课").forEach((l) => {
        const pm = l.payMethod || "未记录";
        if (!map[pm]) map[pm] = { count: 0, revenue: 0 };
        map[pm].count++;
        map[pm].revenue += parseFloat(l.feePaid) || 0;
      });
      return Object.entries(map).sort((a, b) => b[1].revenue - a[1].revenue);
    }, [db.logs]);
    const mkLog = (sName, action, change, note, fee = 0, extra = {}) => {
      const matches = db.students.filter((x) => x.name === sName);
      const sidObj = matches.length === 1 ? { studentId: matches[0].id } : {};
      return { id: Date.now(), date: nowAU(), studentName: sName, ...sidObj, action, change, note, feePaid: fee, ...extra };
    };
    const checkIn = async (sid, sname) => {
      if (cooldowns.current.has(sid)) {
        showToast("请稍候再次操作", "warn");
        return;
      }
      if (busy) return;
      if (!checkInWindow.ok) {
        showToast(`${fmtDate(rDate)}：${checkInWindow.reason}`, "warn");
        return;
      }
      const student = db.students.find((s) => s.id === sid);
      if (!student || student.balance <= 0) {
        showToast(`${sname} 课时余额不足`, "error");
        return;
      }
      if (checkInWindow.future) {
        const before = Number(student.balance) || 0;
        confirm2(
          `${checkInWindow.reason}（${fmtDate(rDate)}）。${sname} 的余额会从 ${before} 变成 ${Math.max(0, before - 1)} 课时。`,
          () => runCheckIn(sid, sname, student),
          { confirmText: `仍然签到 · ${before} → ${Math.max(0, before - 1)}` }
        );
        return;
      }
      return runCheckIn(sid, sname, student);
    };
    const runCheckIn = async (sid, sname, student) => {
      if (busy) return;
      cooldowns.current.add(sid);
      setTimeout(() => cooldowns.current.delete(sid), 3e3);
      setBusy(true);
      try {
        let nb;
        if (TENANT_SLUG) {
          const res = await v1Api("/attendance/check-in", {
            method: "POST",
            body: JSON.stringify({ studentId: sid, note: "常规课程消耗", classDate: rDate })
          });
          nb = Number(res.newBalance);
          await load();
        } else {
          nb = Math.max(0, student.balance - 1);
          const ns = db.students.map((s) => s.id === sid ? { ...s, balance: nb, lastActive: todayISO() } : s);
          const ok = await save({ ...db, students: ns, logs: [mkLog(sname, "上课签到", -1, "常规课程消耗", 0, { studentId: sid }), ...db.logs] });
          if (!ok) return;
        }
        if (selS?.id === sid) setSelS((p) => ({ ...p, balance: nb }));
        const confirmMsg = nb === 0 ? renderMessage("checkin_empty", "{student} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～", { student: sname }) : renderMessage("checkin", "{student} 今日已完成签到 ✓ 当前剩余 {balance} 课时。{studio} 感谢您的支持！", { student: sname, balance: nb });
        const act = { label: "复制签到确认（发家长）", onClick: () => copyText(confirmMsg, "签到确认已复制") };
        if (nb === 0) showToast(`${sname} 课时已清零！请提醒续课`, "warn", act);
        else showToast(`${sname} 签到 ✓ 剩余 ${nb} 课时`, "success", act);
      } catch (e) {
        showToast(`签到失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const undoCheckIn = (sid, sname) => {
      const m = String(rDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
      const datePrefix = m ? `${m[3]}/${m[2]}/${m[1]}` : "";
      const exactEntry = TENANT_SLUG ? db.logs.find((l) => l.studentId === sid && l.action === "上课签到" && l.attendanceId && String(l.date).startsWith(datePrefix)) : null;
      if (TENANT_SLUG && !exactEntry) {
        showToast(`未找到 ${fmtDate(rDate)} 的准确签到记录，未执行撤销`, "warn");
        return;
      }
      const undoBefore = Number((db.students.find((s) => s.id === sid) || {}).balance) || 0;
      confirm2(`撤销 ${sname} 在 ${fmtDate(rDate)} 的签到，扣掉的 1 课时会退回 TA 的余额：${undoBefore} → ${undoBefore + 1} 课时。

这条撤销会写进操作日志，可以随时再签一次。`, async () => {
        if (busy) return;
        setBusy(true);
        try {
          if (TENANT_SLUG) {
            await v1Api(`/attendance/${exactEntry.attendanceId}/void`, {
              method: "POST",
              body: JSON.stringify({ note: "管理员撤销" })
            });
            await load();
          } else {
            const idx = db.logs.findIndex((l) => (l.studentId === sid || !l.studentId && l.studentName === sname) && l.action === "上课签到");
            if (idx === -1) {
              showToast("未找到签到记录", "warn");
              return;
            }
            const ns = db.students.map((s) => s.id === sid ? { ...s, balance: (parseInt(s.balance, 10) || 0) + 1 } : s);
            const nl = db.logs.filter((_, i) => i !== idx);
            const ok = await save({ ...db, students: ns, logs: [mkLog(sname, "撤销签到", "+1", "管理员撤销", 0, { studentId: sid }), ...nl] });
            if (!ok) return;
          }
          if (selS?.id === sid) setSelS((p) => ({ ...p, balance: (parseInt(p.balance, 10) || 0) + 1 }));
          showToast(`已撤销 ${sname} 签到`, "warn");
        } catch (e) {
          showToast(`撤销失败：${e.message}`, "error");
        } finally {
          setBusy(false);
        }
      }, { confirmText: "确认撤销" });
    };
    const [rosterAttendance, setRosterAttendance] = useState10(null);
    useEffect9(() => {
      if (!TENANT_SLUG) {
        setRosterAttendance(null);
        return void 0;
      }
      let cancelled = false;
      (async () => {
        try {
          const d = await v1Api(`/attendance?date=${encodeURIComponent(rDate)}&limit=500`);
          if (!cancelled) setRosterAttendance(d.attendance || []);
        } catch (e) {
          if (!cancelled) setRosterAttendance(null);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [rDate]);
    const rosterDone = useMemo6(() => {
      const done = /* @__PURE__ */ new Set();
      if (rosterAttendance) {
        rosterAttendance.forEach((a) => {
          if (!a.reversed_at) done.add(a.student_id);
        });
        return done;
      }
      const m = String(rDate).match(/^(\d{4})-(\d{2})-(\d{2})$/);
      const prefix = m ? `${m[3]}/${m[2]}/${m[1]}` : "__none__";
      db.logs.forEach((l) => {
        if (l.action === "上课签到" && String(l.date).startsWith(prefix)) {
          if (l.studentId) done.add(l.studentId);
          else {
            const s = db.students.find((x) => x.name === l.studentName);
            if (s) done.add(s.id);
          }
        }
      });
      return done;
    }, [rosterAttendance, db.logs, db.students, rDate]);
    const checkInWindow = useMemo6(() => {
      const picked = /* @__PURE__ */ new Date(`${rDate}T00:00:00`);
      const midnight = /* @__PURE__ */ new Date();
      midnight.setHours(0, 0, 0, 0);
      const days = Math.round((picked - midnight) / 864e5);
      if (Number.isNaN(days)) return { ok: true, future: false, reason: "" };
      if (days > 1) return { ok: false, future: true, reason: "这一天还没到，不能签到扣课时" };
      if (days < -90) return { ok: false, future: false, reason: "超过 90 天的课程不能再补签" };
      return { ok: true, future: days > 0, reason: days > 0 ? "这是明天的课，现在签到就会先扣掉课时" : "" };
    }, [rDate]);
    const WEEKDAYS2 = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    const loadSchedules = async () => {
      if (!TENANT_SLUG) return;
      setScheduleLoadError("");
      try {
        const d = await v1Api("/class-schedules");
        setSchedules(d.schedules || []);
      } catch (e) {
        setScheduleLoadError(`固定课表加载失败：${e.message}`);
      }
      await loadCourses();
      try {
        const b = await v1Api("/class-bookings");
        setBookings(b.bookings || []);
      } catch {
        setBookings([]);
      }
      try {
        const dash = await v1Api("/dashboard");
        setBizStats((dash.dashboard || {}).business || null);
      } catch (e) {
        setScheduleLoadError((current) => current || `经营数据加载失败：${e.message}`);
      }
    };
    const loadAuditEvents = async () => {
      if (!TENANT_SLUG) return;
      try {
        const d = await v1Api("/audit-logs?limit=200");
        setAuditEvents(d.auditLogs || []);
      } catch {
        setAuditEvents([]);
      }
    };
    const schedOverlap = (a, b) => {
      if (Number(a.weekday) !== Number(b.weekday)) return false;
      const toMin = (t) => {
        const [h, m] = String(t).split(":").map(Number);
        return h * 60 + (m || 0);
      };
      const aS = toMin(a.startTime), aE = aS + (Number(a.durationMinutes) || 60);
      const bS = toMin(b.startTime), bE = bS + (Number(b.durationMinutes) || 60);
      return aS < bE && bS < aE;
    };
    const schedClash = (a, b) => {
      if (!schedOverlap(a, b)) return false;
      const at = a.teacherUserId || "", bt = b.teacherUserId || "";
      if (!at && !bt) return true;
      return at !== "" && at === bt;
    };
    const saveSchedule = async (conflictConfirmed = false) => {
      if (!schedEdit || busy) return;
      if (!schedEdit.label.trim()) {
        showToast("请输入班次名称（如：周三素描班）", "error");
        return;
      }
      const clash = schedules.find((sc) => sc.id !== schedEdit.id && schedClash(sc, schedEdit));
      if (clash && !conflictConfirmed) {
        const who = clash.teacherUserId && clash.teacherUserId === schedEdit.teacherUserId ? `${clash.teacherName || "同一位老师"}同时段已排「${clash.label}」` : `与「${clash.label}」（${WEEKDAYS2[clash.weekday]} ${clash.startTime}）时段重叠`;
        confirm2(
          `「${schedEdit.label.trim()}」${who}，仍要保存吗？`,
          () => saveSchedule(true),
          { confirmText: "仍然保存" }
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
          courseId: schedEdit.courseId || "",
          teacherUserId: schedEdit.teacherUserId || "",
          isPublic: !!schedEdit.isPublic,
          room: (schedEdit.room || "").trim()
        });
        const d = schedEdit.id ? await v1Api(`/class-schedules/${schedEdit.id}`, { method: "PATCH", body }) : await v1Api("/class-schedules", { method: "POST", body });
        setSchedules(d.schedules || []);
        setSchedEdit(null);
        showToast("每周课表已保存");
      } catch (e) {
        showToast(`课表保存失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const deleteSchedule = (sc) => {
      confirm2(`删除固定班次「${sc.label}」后，之后的日期不会再自动排入这批学员。

已经排过的日期、已签到的记录和学员课时都不受影响。`, async () => {
        if (busy) return;
        setBusy(true);
        try {
          const d = await v1Api(`/class-schedules/${sc.id}`, { method: "DELETE" });
          setSchedules(d.schedules || []);
          if (schedEdit && schedEdit.id === sc.id) setSchedEdit(null);
          showToast(`班次「${sc.label}」已删除`, "warn");
        } catch (e) {
          showToast(`删除失败：${e.message}`, "error");
        } finally {
          setBusy(false);
        }
      }, { danger: true, confirmText: "确认删除" });
    };
    const teachableMembers = useMemo6(
      () => team.filter((m) => m.status === "active" && ["owner", "manager", "teacher"].includes(m.role)),
      [team]
    );
    const nextOccurrence = (weekday) => {
      const today = /* @__PURE__ */ new Date(`${todayISO()}T12:00:00`);
      const delta = (Number(weekday) - today.getDay() + 7) % 7;
      const d = new Date(today.getTime() + delta * 864e5);
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
    };
    const saveCancellation = async () => {
      if (!schedCancel || busy) return;
      setBusy(true);
      try {
        const d = await v1Api(`/class-schedules/${schedCancel.id}/cancellations`, {
          method: "POST",
          body: JSON.stringify({ date: schedCancel.date, note: (schedCancel.note || "").trim() })
        });
        setSchedules(d.schedules || []);
        setSchedCancel(null);
        showToast("已标记停课");
      } catch (e) {
        showToast(`标记停课失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const restoreCancellation = async (sc, date) => {
      if (busy) return;
      setBusy(true);
      try {
        const d = await v1Api(`/class-schedules/${sc.id}/cancellations/${date}`, { method: "DELETE" });
        setSchedules(d.schedules || []);
        showToast(`${date} 恢复上课`);
      } catch (e) {
        showToast(`恢复失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const loadCourses = async () => {
      try {
        const c = await v1Api("/courses");
        setCourses((c.courses || []).filter((x) => x.is_active !== false));
      } catch {
        setCourses([]);
      }
    };
    const saveCourse = async () => {
      if (!courseEdit || busy) return;
      const name = (courseEdit.name || "").trim();
      if (!name) {
        showToast("请填写课程名称", "warn");
        return;
      }
      setBusy(true);
      try {
        const body = JSON.stringify({
          name,
          description: (courseEdit.description || "").trim(),
          ageRange: (courseEdit.ageRange || "").trim(),
          durationMinutes: Number(courseEdit.durationMinutes) || 60,
          /* 接口收的是元，服务端转成分存。价格留空就是 0 —— 不是每家
             工作室都想在课程上标价，公开课表的价格开关默认也是关的。 */
          priceAud: courseEdit.priceAud === "" ? 0 : Number(courseEdit.priceAud) || 0
        });
        if (courseEdit.id) await v1Api(`/courses/${courseEdit.id}`, { method: "PATCH", body });
        else await v1Api("/courses", { method: "POST", body });
        await loadCourses();
        setCourseEdit(null);
        showToast(courseEdit.id ? "课程已更新" : "课程已添加");
      } catch (e) {
        showToast(`保存失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const archiveCourse = (course) => {
      const used = schedules.filter((sc) => sc.courseId === course.id);
      confirm2(
        `归档课程「${course.name}」后，它不会再出现在新排课的下拉里。` + (used.length ? `

注意：目前有 ${used.length} 个班次正在关联它，那些班次不受影响，公开课表仍会显示这门课的名称。` : "") + "\n\n已有的排课、账目和历史记录都不受影响。",
        async () => {
          if (busy) return;
          setBusy(true);
          try {
            await v1Api(`/courses/${course.id}`, { method: "DELETE" });
            await loadCourses();
            showToast(`课程「${course.name}」已归档`, "warn");
          } catch (e) {
            showToast(`归档失败：${e.message}`, "error");
          } finally {
            setBusy(false);
          }
        },
        { danger: true, confirmText: "确认归档" }
      );
    };
    const resetPackageEditor = () => {
      setPkgEditId(null);
      setPkgName("");
      setPkgCredits("");
      setPkgPrice("");
    };
    const savePackage = async () => {
      if (busy) return;
      if (!pkgName.trim() || !pkgCredits || !pkgPrice) {
        showToast("请填写套餐名称、课时数和价格", "warn");
        return;
      }
      const credits = parseInt(pkgCredits, 10);
      const price = parseFloat(pkgPrice);
      if (!Number.isFinite(credits) || credits < 1 || !Number.isFinite(price) || price < 0) {
        showToast("课时数必须大于 0，价格不能为负数", "warn");
        return;
      }
      const packages = pkgEditId === 0 ? [...db.packages || [], { id: Date.now(), name: pkgName.trim(), credits, price }] : (db.packages || []).map((pkg) => pkg.id === pkgEditId ? { ...pkg, name: pkgName.trim(), credits, price } : pkg);
      const ok = await save({ ...db, packages });
      if (!ok) return;
      const adding = pkgEditId === 0;
      resetPackageEditor();
      showToast(adding ? "套餐已添加" : "套餐已更新");
    };
    const archivePackage = (pkg) => {
      if ((db.packages || []).length <= 1) {
        showToast("至少保留一个套餐", "warn");
        return;
      }
      confirm2(`删除套餐「${pkg.name}」？已有充值记录不会被删除。`, async () => {
        const ok = await save({ ...db, packages: (db.packages || []).filter((item) => item.id !== pkg.id) });
        if (ok) showToast("套餐已删除", "warn");
      }, { danger: true, confirmText: "删除套餐" });
    };
    const reviewBooking = async (bk, status) => {
      if (busy) return;
      setBusy(true);
      try {
        const d = await v1Api(`/class-bookings/${bk.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status })
        });
        setBookings(d.bookings || []);
        if (status === "approved") {
          await load();
          showToast(bk.isExistingStudent ? `已批准，${bk.matchedStudent || bk.contactName} 已排入 ${bk.date}` : "已批准，并已建立一条待审核报名");
        } else {
          showToast("已婉拒这条申请", "warn");
        }
      } catch (e) {
        showToast(`处理失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const groupToSchedule = () => {
      const ids = (db.groups || {})[grpSel] || [];
      if (!grpSel || !ids.length) {
        showToast("请先选择一个班组模板", "warn");
        return;
      }
      setSchedEdit({
        label: grpSel,
        weekday: (/* @__PURE__ */ new Date()).getDay(),
        startTime: defaultClassTime,
        durationMinutes: 60,
        capacity: Math.max(10, ids.length),
        studentIds: ids,
        courseId: "",
        teacherUserId: "",
        isPublic: false,
        room: ""
      });
      const block = document.getElementById("rosterSchedules");
      if (block) {
        block.open = true;
        requestAnimationFrame(() => block.scrollIntoView({ behavior: "smooth", block: "start" }));
      }
      showToast("已带入模板学员，请确认周几与时间后保存");
    };
    const addDailyRosterStudents = async (date, studentIds, source = "manual", status = "scheduled", extra = {}) => {
      if (!TENANT_SLUG) return null;
      const data = await v1Api("/daily-roster", {
        method: "POST",
        body: JSON.stringify({ date, studentIds, source, status, ...extra })
      });
      await load();
      return data;
    };
    const updateRosterEntry = async (entryId, patch) => {
      if (!TENANT_SLUG || !entryId) return null;
      const data = await v1Api(`/daily-roster/${entryId}`, {
        method: "PATCH",
        body: JSON.stringify(patch)
      });
      await load();
      return data;
    };
    const rosterMetaFor = (date, sid) => (db.rosterEntries?.[date] || {})[sid] || {};
    const rosterSlotFor = (date, sid) => {
      const explicit = rosterMetaFor(date, sid).classTime;
      if (explicit) return explicit;
      const weekday = (/* @__PURE__ */ new Date(`${date}T12:00:00`)).getDay();
      return schedules.find(
        (schedule) => schedule.weekday === weekday && schedule.students.some((student) => student.id === sid)
      )?.startTime || "";
    };
    const CALENDAR_KINDS = Object.freeze({
      roster: { serverKind: "daily-roster", previewPath: "/daily-roster/calendar", downloadPath: "/daily-roster/calendar.ics" },
      schedule: { serverKind: "weekly-schedules", previewPath: "/class-schedules/calendar", downloadPath: "/class-schedules/calendar.ics" }
    });
    const calendarContract = (kind) => {
      const contract = CALENDAR_KINDS[kind];
      if (!contract) throw new Error("未知的日历导出类型，请刷新页面后重试");
      return contract;
    };
    const calendarPreviewPath = (kind, rosterDate = rDate) => {
      const contract = calendarContract(kind);
      return kind === "roster" ? `${contract.previewPath}?date=${encodeURIComponent(rosterDate)}` : contract.previewPath;
    };
    const fetchIcsPreview = async (kind, rosterDate = rDate) => {
      const data = await v1Api(calendarPreviewPath(kind, rosterDate));
      const calendar = data.calendar || {};
      if (!/^[0-9a-f]{64}$/.test(calendar.revision || "")) {
        throw new Error("日历预览缺少有效版本，请刷新页面后重试");
      }
      const contract = calendarContract(kind);
      if (calendar.kind !== contract.serverKind) {
        throw new Error("日历预览类型与下载类型不一致，请刷新页面后重试");
      }
      return { ...calendar, downloadKind: kind };
    };
    const openIcsPreview = async (kind) => {
      setIcsBusy(true);
      setIcsNotice("");
      try {
        setIcsPreview(await fetchIcsPreview(kind));
      } catch (err) {
        showToast(err.message || "日历预览加载失败", "error");
      } finally {
        setIcsBusy(false);
      }
    };
    const downloadIcs = async (preview) => {
      setIcsBusy(true);
      try {
        const kind = preview?.downloadKind;
        const contract = calendarContract(kind);
        const revision = preview?.revision || "";
        if (!/^[0-9a-f]{64}$/.test(revision)) {
          throw new Error("日历预览版本无效，请关闭后重新预览");
        }
        const query = new URLSearchParams({ revision });
        if (kind === "roster") query.set("date", preview.date || rDate);
        const path = `${contract.downloadPath}?${query}`;
        const r = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1${path}`, {
          credentials: "include",
          headers: { "X-Requested-With": "StudioSaaS" }
        });
        if (!r.ok) {
          const detail = await r.json().catch(() => ({}));
          if (r.status === 409 && detail.error === "calendar_revision_conflict") {
            setIcsPreview(await fetchIcsPreview(kind, preview.date || rDate));
            setIcsNotice("排课刚刚发生变化，预览已自动刷新。请核对后再次下载。");
            return;
          }
          throw new Error(detail.message || detail.error || `下载失败（HTTP ${r.status}）`);
        }
        const type = r.headers.get("Content-Type") || "";
        if (!type.includes("calendar")) throw new Error("服务器未返回日历文件，请重新登录后再试");
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = preview.filename || r.headers.get("Content-Disposition")?.match(/filename="?([^";]+)"?/)?.[1] || (kind === "roster" ? `roster-${rDate}.ics` : "calendar.ics");
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1e3);
        setIcsPreview(null);
        setIcsNotice("");
        showToast("日历文件已下载");
      } catch (err) {
        showToast(err.message || "下载失败", "error");
      } finally {
        setIcsBusy(false);
      }
    };
    const saveDefaultClassTime = async () => {
      if (operationalSettingsBusy) return;
      if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(defaultClassTimeDraft)) {
        showToast("默认上课时间必须是有效的 HH:MM", "error");
        return;
      }
      setOperationalSettingsBusy(true);
      try {
        const data = await v1Api("/operational-settings", {
          method: "PATCH",
          body: JSON.stringify({ defaultClassTime: defaultClassTimeDraft })
        });
        const saved = data.defaultClassTime;
        setDefaultClassTime(saved);
        setDefaultClassTimeDraft(saved);
        setRTime(saved);
        showToast(`默认上课时间已设为 ${saved}`);
      } catch (error) {
        showToast(`默认时间保存失败：${error.message}`, "error");
      } finally {
        setOperationalSettingsBusy(false);
      }
    };
    const copyRosterDaily = () => {
      const lines = dayIds.map((id) => {
        const student = db.students.find((item) => item.id === id);
        return student && !student.archived ? `${student.name}（剩余${student.balance}课时）` : null;
      }).filter(Boolean);
      const heading = rDate === todayISO() ? "今日上课" : "上课名单";
      copyText(`【${heading} ${lines.length} 人 - ${fmtDate(rDate)}】
${lines.join("\n")}`, "日报已复制到剪贴板");
    };
    const copyRosterReminders = () => {
      const lines = dayIds.map((id) => {
        const student = db.students.find((item) => item.id === id);
        if (!student || student.archived || !student.mobile) return null;
        const slot = rosterSlotFor(rDate, id);
        return `${student.name}（${student.mobile}）
提醒：您的上课时间是 ${fmtDate(rDate)}${slot ? ` ${slot}` : ""}，请准时到课。${tenantDisplayName} 期待见到您！`;
      }).filter(Boolean);
      copyText(lines.join("\n\n"), `已复制 ${lines.length} 条提醒内容`);
    };
    const batchCheckIn = () => {
      const ids = dayIds;
      const already = ids.filter((id) => rosterDone.has(id)).length;
      const archived = ids.filter((id) => db.students.find((x) => x.id === id)?.archived).length;
      const insufficient = ids.filter((id) => {
        const s = db.students.find((x) => x.id === id);
        return s && !s.archived && s.balance <= 0 && !rosterDone.has(id);
      }).length;
      const elig = ids.filter((id) => {
        const s = db.students.find((x) => x.id === id);
        return s && !s.archived && s.balance > 0 && !rosterDone.has(id);
      });
      if (!checkInWindow.ok) {
        showToast(`${fmtDate(rDate)}：${checkInWindow.reason}`, "warn");
        return;
      }
      if (!elig.length) {
        showToast(already ? "这一天排课的学员均已签到 ✓" : "这一天没有可签到/消课的学员", "warn");
        return;
      }
      const futureWarning = checkInWindow.future ? `⚠ ${checkInWindow.reason}。` : "";
      confirm2(`批量签到确认 · ${fmtDate(rDate)}：${futureWarning}排课 ${ids.length} 人；已签到 ${already} 人；余额不足 ${insufficient} 人；已归档 ${archived} 人；本次实际执行 ${elig.length} 人。`, async () => {
        if (busy) return;
        setBusy(true);
        try {
          if (TENANT_SLUG) {
            const failed = [];
            for (const id of elig) {
              const s = db.students.find((x) => x.id === id);
              if (!s) continue;
              try {
                await v1Api("/attendance/check-in", {
                  method: "POST",
                  body: JSON.stringify({ studentId: id, note: "批量签到/消课", classDate: rDate })
                });
              } catch (e) {
                failed.push(`${s.name}（${e.message || "原因未知"}）`);
              }
            }
            await load();
            const succeeded = elig.length - failed.length;
            if (failed.length) showToast(`批量签到完成：成功 ${succeeded} 人，失败 ${failed.length} 人 —— ${failed.join("；")}`, "warn");
            else showToast(`批量签到完成：实际成功 ${succeeded} 人`);
          } else {
            let cur = { ...db };
            const base = Date.now();
            elig.forEach((id, i) => {
              const s = cur.students.find((x) => x.id === id);
              if (!s) return;
              const nb = Math.max(0, s.balance - 1);
              cur = {
                ...cur,
                students: cur.students.map((x) => x.id === id ? { ...x, balance: nb, lastActive: todayISO() } : x),
                logs: [{ ...mkLog(s.name, "上课签到", -1, "批量签到/消课", 0, { studentId: id }), id: base + i }, ...cur.logs]
              };
            });
            const ok = await save(cur);
            if (!ok) return;
            showToast(`批量签到/消课完成，共 ${elig.length} 人`);
          }
        } finally {
          setBusy(false);
        }
      }, { confirmText: `签到/消课 ${elig.length} 人` });
    };
    const saveGroup = () => {
      const ids = dayIds.filter((id) => db.students.some((s) => s.id === id && !s.archived));
      if (!ids.length) {
        showToast("当前日期没有排课可保存", "warn");
        return;
      }
      confirm2(`将当前日期的 ${ids.length} 位学员保存为可复用的班组模板。`, async (raw) => {
        const name = String(raw || "").trim();
        if (!name) return;
        const ok = await save({ ...db, groups: { ...db.groups || {}, [name]: ids } });
        if (!ok) return;
        showToast(`模板「${name}」已保存（${ids.length} 人）`);
      }, {
        title: "保存班组模板",
        prompt: true,
        promptRequired: true,
        promptLabel: "模板名称",
        promptPlaceholder: "如：周六上午班",
        confirmText: "保存模板"
      });
    };
    const applyGroup = async () => {
      if (!grpSel) return;
      const ids = (db.groups || {})[grpSel] || [];
      const cur = db.rosters[rDate] || [];
      const add = ids.filter((id) => !cur.includes(id) && db.students.some((s) => s.id === id && !s.archived));
      if (!add.length) {
        showToast("模板学员均已在当前排课中", "warn");
        return;
      }
      if (TENANT_SLUG) await addDailyRosterStudents(
        rDate,
        add,
        "group",
        "scheduled",
        { classTime: rTime || defaultClassTime || null }
      );
      else {
        const ok = await save({ ...db, rosters: { ...db.rosters, [rDate]: [...cur, ...add] } });
        if (!ok) return;
      }
      showToast(`已套用「${grpSel}」，新增 ${add.length} 人`);
    };
    const deleteGroup = () => {
      if (!grpSel) return;
      confirm2(`删除班组模板「${grpSel}」后，将无法再一键套用这组学员。

已经用它排过的课、学员档案和课时都不受影响。`, async () => {
        const g = { ...db.groups || {} };
        delete g[grpSel];
        const ok = await save({ ...db, groups: g });
        if (!ok) return;
        setGrpSel("");
        showToast("模板已删除", "warn");
      }, { danger: true, confirmText: "删除模板" });
    };
    const isStudentScheduledOn = (sid, date) => {
      const manual = (db.rosters[date] || []).includes(sid);
      const wd = (/* @__PURE__ */ new Date(`${date}T12:00:00`)).getDay();
      const fixed = schedules.some((sc) => Number(sc.weekday) === wd && sc.students.some((st) => st.id === sid));
      return manual || fixed;
    };
    const scheduleStudentToday = async (student) => {
      if (!student || student.archived || busy) return;
      const date = todayISO();
      setRDate(date);
      setSelS(null);
      setEditP(false);
      setTab("roster");
      if (isStudentScheduledOn(student.id, date)) {
        showToast(`${student.name} 已在今日排课中`);
        return;
      }
      setBusy(true);
      try {
        const cur = db.rosters[date] || [];
        if (TENANT_SLUG) await addDailyRosterStudents(
          date,
          [student.id],
          "profile",
          "scheduled",
          { classTime: rosterSlotFor(date, student.id) || defaultClassTime || null }
        );
        else {
          const ok = await save({ ...db, rosters: { ...db.rosters, [date]: [...cur, student.id] } });
          if (!ok) return;
        }
        showToast(`${student.name} 已加入今日排课`);
      } finally {
        setBusy(false);
      }
    };
    const openGrowthReport = (s) => {
      const logs = db.logs.filter((l) => l.studentId === s.id || !l.studentId && l.studentName === s.name);
      const parseD = (d) => {
        const m = String(d).match(/^(\d{2})\/(\d{2})\/(\d{4})/);
        return m ? /* @__PURE__ */ new Date(`${m[3]}-${m[2]}-${m[1]}`) : null;
      };
      const checkins = logs.filter((l) => l.action === "上课签到");
      const dates = logs.map((l) => parseD(l.date)).filter(Boolean).sort((a, b) => a - b);
      const explicitJoinDate = /^\d{4}-\d{2}-\d{2}$/.test(String(s.enrollmentDate || "")) ? /* @__PURE__ */ new Date(`${s.enrollmentDate}T12:00:00`) : null;
      const joinDate = explicitJoinDate && explicitJoinDate <= /* @__PURE__ */ new Date() ? explicitJoinDate : dates.length ? dates[0] : null;
      const days = joinDate ? Math.max(1, Math.round((Date.now() - joinDate) / 864e5)) : 0;
      const bal = parseInt(s.balance, 10) || 0;
      const port = s.portfolio || [];
      const now = /* @__PURE__ */ new Date();
      const monthsSinceJoin = joinDate ? (now.getFullYear() - joinDate.getFullYear()) * 12 + (now.getMonth() - joinDate.getMonth()) + 1 : 6;
      const monthSpan = Math.max(2, Math.min(6, monthsSinceJoin));
      const months = Array.from({ length: monthSpan }, (_, i) => {
        const d = new Date(now.getFullYear(), now.getMonth() - (monthSpan - 1) + i, 1);
        return { k: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`, l: `${d.getMonth() + 1}月`, n: 0 };
      });
      const mIdx = Object.fromEntries(months.map((m, i) => [m.k, i]));
      checkins.forEach((l) => {
        const d = parseD(l.date);
        if (!d) return;
        const k = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
        if (k in mIdx) months[mIdx[k]].n++;
      });
      const maxM = Math.max(1, ...months.map((m) => m.n));
      const esc = (t) => String(t || "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
      const fmtD = (d) => d ? `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}/${d.getFullYear()}` : "—";
      const reportBrand = tenantBrand || {};
      const reportSlogan = reportBrand.slogan || "Learn, grow, and feel confident.";
      const reportStudioName = reportBrand.name || tenantDisplayName || "Studio";
      const reportLogoUrl = tenantLogoUrl;
      const safeReportColor = (value, fallback) => /^#[0-9a-f]{6}$/i.test(String(value || "")) ? String(value) : fallback;
      const reportAccent = safeReportColor(reportBrand.primary_color || reportBrand.primaryColor, "#b08d57");
      const reportAccentDark = safeReportColor(reportBrand.secondary_color || reportBrand.secondaryColor, "#6f5b3e");
      const isNew = checkins.length === 0;
      const teacherNote = String(s.reportNote || s.teacherNote || "").trim();
      const shareMsg = isNew ? `欢迎 ${s.name} 加入 ${reportStudioName}！学习旅程刚刚启程，期待记录每一份成长与快乐。` : `${s.name} 在 ${reportStudioName} 已经学习了 ${days} 天，累计上课 ${checkins.length} 次，完成${workNoun} ${port.length} 份。`;
      const portHTML = port.length ? port.map((p) => `
            <figure class="art">
                <img src="${portfolioImgSrc(s.id, p)}" alt="作品"/>
                <figcaption>${esc(p.note) || "　"}<span>${esc((p.date || "").split("-").reverse().join("/"))}</span></figcaption>
            </figure>`).join("") : `<p class="empty">暂无${workNoun}记录 · 上传后报告会更精彩</p>`;
      const barsHTML = months.map((m) => `
            <div class="bar"><span class="bn">${m.n || ""}</span><div class="fill" style="height:${Math.max(3, Math.round(m.n / maxM * 76))}px"></div><span class="bl">${m.l}</span></div>`).join("");
      const photoHTML = s.photo ? `<img class="avatar" src="${mediaSrc(s.photo)}" alt=""/>` : `<div class="avatar ph">${esc((s.name || "?").slice(0, 1))}</div>`;
      const reportJoinText = reportBrand.category === "art" ? "艺术之旅刚刚启程" : "学习旅程刚刚启程";
      const rlang = (() => {
        try {
          return localStorage.getItem("studiosaas_admin_language") === "en" ? "en" : "zh";
        } catch (e) {
          return "zh";
        }
      })();
      const RT = rlang === "en" ? {
        htmlLang: "en",
        tag: "Student Growth Report",
        attended: "Lessons attended",
        works: "Works completed",
        balance: "Lessons remaining",
        days: "Days with us",
        footprint: (n) => `Last ${n} months`,
        gallery: (n) => `Portfolio (${n})`,
        note: "A note from the teacher",
        generated: (d, n) => `Report generated ${d} · ${n}`,
        joined: (n, d, days2) => `${days2} days at ${n} · joined ${d}`,
        welcome: (n) => `Welcome to ${n}`,
        emptyWorks: "No works recorded yet",
        print: "Print / Save as PDF",
        copy: "Copy note",
        copied: "✓ Copied"
      } : {
        htmlLang: "zh",
        tag: "学员成长报告",
        attended: "累计上课",
        works: "完成作品",
        balance: "剩余课时",
        days: "陪伴天数",
        footprint: (n) => `近 ${n} 个月上课足迹`,
        gallery: (n) => `作品集（${n} 幅）`,
        note: "老师寄语",
        generated: (d, n) => `报告生成于 ${d} · ${n}`,
        joined: (n, d, days2) => `已在 ${n} 成长陪伴 <b>${days2}</b> 天 · 入学于 ${d}`,
        welcome: (n) => `欢迎加入 ${n}`,
        emptyWorks: "暂无作品记录",
        print: "打印 / 存为 PDF",
        copy: "复制寄语",
        copied: "✓ 已复制寄语"
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
    <div class="stat"><div class="v">${isNew ? "—" : days}</div><div class="l">${RT.days}</div></div>
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
  </div>` : ""}
  <div class="foot">
	    <div class="fslogan">${esc(reportSlogan)}</div>
	    ${RT.generated(fmtD(/* @__PURE__ */ new Date()), esc(reportStudioName))}
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
      const w = window.open("", "_blank");
      if (!w) {
        showToast("请允许弹出窗口以查看报告", "warn");
        return;
      }
      w.document.write(html);
      w.document.close();
    };
    const archiveStudent = (sid, sname, archive) => {
      confirm2(
        archive ? `${sname} 会移出日常名单，不再出现在排课和搜索结果里。

课时、上课记录和作品都完整保留，在「归档库」筛选下随时可以恢复。` : `${sname} 会回到日常名单，可以正常排课和签到。

课时余额和历史记录保持原样。`,
        async () => {
          if (busy) return;
          setBusy(true);
          try {
            const ns = db.students.map((s) => s.id === sid ? { ...s, archived: archive } : s);
            const ok = await save({ ...db, students: ns, logs: [mkLog(sname, archive ? "归档学员" : "恢复学员", "0", archive ? "移入归档库" : "从归档库恢复", 0, { studentId: sid }), ...db.logs] });
            if (!ok) return;
            setSelS(null);
            setEditP(false);
            showToast(`${sname} 已${archive ? "归档" : "恢复"}`, "warn");
          } finally {
            setBusy(false);
          }
        },
        { confirmText: archive ? "确认归档" : "确认恢复" }
      );
    };
    const copySelectedReminders = () => {
      if (!selectedStudents.length) return;
      const lines = selectedStudents.map((s) => renderMessage(
        "renewal",
        "{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。",
        { student: s.name, balance: s.balance, note: (parseInt(s.balance, 10) || 0) === 0 ? "（已用完）" : "" }
      ));
      copyText(lines.join("\n\n"), `已复制 ${lines.length} 条续课提醒，可逐条粘贴到微信`);
    };
    const archiveSelected = () => {
      const targets = selectedStudents.filter((s) => !s.archived);
      if (!targets.length) {
        showToast("所选学员均已归档", "warn");
        return;
      }
      confirm2(`${targets.length} 名学员会移出日常名单，不再出现在排课和搜索结果里。

课时、上课记录和作品都完整保留，在「归档库」筛选下随时可以恢复。`, async () => {
        if (busy) return;
        setBusy(true);
        try {
          const ids = new Set(targets.map((s) => s.id));
          const ns = db.students.map((s) => ids.has(s.id) ? { ...s, archived: true } : s);
          const logs = targets.map((s) => mkLog(s.name, "归档学员", "0", "批量移入归档库", 0, { studentId: s.id }));
          const ok = await save({ ...db, students: ns, logs: [...logs, ...db.logs] });
          if (!ok) return;
          setSelectedStudentIds([]);
          showToast(`已归档 ${targets.length} 名学员`, "warn");
        } finally {
          setBusy(false);
        }
      }, { confirmText: `归档 ${targets.length} 人`, danger: true });
    };
    const settlementPaymentMethod = { "现金": "cash", "银行转账": "bank_transfer", "其他": "other", "微信": "other" };
    const nextSettlementRequestId = (signature) => {
      if (settlementRequestRef.current.signature !== signature) {
        const id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `settlement-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        settlementRequestRef.current = { signature, id };
      }
      return settlementRequestRef.current.id;
    };
    const setSettlementPayer = (next) => {
      const payerIntent = next.createPayload ? `create:${JSON.stringify(next.createPayload)}` : `account:${next.accountId || ""}`;
      if (settlementPayerIntentRef.current !== payerIntent) {
        settlementResolvedAccountRef.current = "";
        settlementPayerIntentRef.current = payerIntent;
      }
      setSettlementPayerState(next);
    };
    const handleTopUp = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const credits = parseInt(fd.get("credits"), 10);
      const fee = parseFloat(fd.get("fee")) || 0;
      const amountCents = Math.round(fee * 100);
      const tuRemark = (fd.get("tuRemark") || "").trim();
      const createInvoice = Boolean(TENANT_SLUG && canUseSettlementBilling && tuCreateInvoice);
      const paymentReceived = Boolean(createInvoice && canRegisterSettlementPayment && tuPaymentReceived && amountCents > 0);
      const taxCode = settlementTaxCodes.find((code) => code.is_default) || settlementTaxCodes[0] || null;
      if (!tuStu) {
        showToast("请选择学员", "error");
        return;
      }
      if (isNaN(credits) || credits <= 0) {
        showToast("请输入有效课时数", "error");
        return;
      }
      if (fee < 0) {
        showToast("金额无效", "error");
        return;
      }
      if (createInvoice && amountCents <= 0) {
        showToast("金额为 0 时不能创建发票，请关闭“同时创建发票”。", "error");
        return;
      }
      const payerIntent = settlementPayerState.createPayload ? `create:${JSON.stringify(settlementPayerState.createPayload)}` : `account:${settlementPayerState.accountId || ""}`;
      const signature = JSON.stringify({
        studentId: tuStu,
        credits,
        amountCents,
        packageId: tuPkg || null,
        paymentMethod: settlementPaymentMethod[tuPay] || "other",
        note: tuRemark,
        createInvoice,
        paymentReceived,
        taxCodeId: taxCode?.id || null,
        payerIntent
      });
      const requestId = nextSettlementRequestId(signature);
      const s0 = db.students.find((x) => x.id === tuStu);
      const payerName = settlementPayerState.accountId ? settlementAccounts.find((a) => String(a.id) === String(settlementPayerState.accountId))?.name || "已选付款方" : settlementPayerState.createPayload?.name || "待创建付款方";
      const grossLabel = `$${fee.toFixed(2)}`;
      const rateBp = Number(taxCode?.rate_bp || 0);
      const taxEstimate = amountCents > 0 ? Math.max(0, amountCents - Math.round(amountCents * 1e4 / (1e4 + rateBp || 1e4))) : 0;
      const confirmation = createInvoice ? `确认 ${s0?.name || ""} 充值 ${credits} 课时，gross ${grossLabel}（预计税额 $${(taxEstimate / 100).toFixed(2)}），付款方：${payerName}；${paymentReceived ? `开票并登记已收款（${tuPay}）` : "开票但暂不登记收款"}？` : `确认为 ${s0?.name || ""} 充值 ${credits} 课时，实收 ${grossLabel}（${tuPay}）${fee === 0 ? "——免费充课" : ""}？`;
      const doTopUp = async () => {
        if (busy) return;
        setBusy(true);
        try {
          const s = db.students.find((x) => x.id === tuStu);
          if (!s) throw new Error("学员不存在或已改变。");
          const noteStr = [`套餐: ${tuPkg || "自定义"}`, `付款: ${tuPay}`, ...tuRemark ? [tuRemark] : []].join(" | ");
          let settlement = null;
          if (TENANT_SLUG) {
            if (createInvoice) {
              let billingAccountId = settlementResolvedAccountRef.current || settlementPayerState.accountId;
              if (!billingAccountId && settlementPayerState.createPayload) {
                const payload = { ...settlementPayerState.createPayload };
                if (payload.studentId) delete payload.studentIds;
                const created = await v1Api("/billing/accounts", {
                  method: "POST",
                  body: JSON.stringify(payload)
                });
                billingAccountId = String(created.account?.id || "");
                settlementResolvedAccountRef.current = billingAccountId;
              }
              if (!billingAccountId) throw new Error("请选择或创建付款方。");
              if (settlementPayerState.mode === "custom" && settlementPayerState.linkedStudentIds.length) {
                await v1Api(`/billing/accounts/${billingAccountId}/members`, {
                  method: "POST",
                  body: JSON.stringify({ studentIds: settlementPayerState.linkedStudentIds })
                });
              }
              settlement = await v1Api(`/students/${s.id}/credit-settlements`, {
                method: "POST",
                body: JSON.stringify({
                  requestId,
                  credits: String(credits),
                  amountCents,
                  paymentMethod: settlementPaymentMethod[tuPay] || "other",
                  packageId: tuPkg || null,
                  note: noteStr,
                  billing: {
                    createInvoice: true,
                    billingAccountId,
                    taxCodeId: taxCode?.id || null,
                    issueNow: true,
                    paymentReceived
                  }
                })
              });
            } else {
              settlement = await v1Api(`/students/${s.id}/credit-settlements`, {
                method: "POST",
                body: JSON.stringify({
                  requestId,
                  credits: String(credits),
                  amountCents,
                  paymentMethod: settlementPaymentMethod[tuPay] || "other",
                  packageId: tuPkg || null,
                  note: noteStr,
                  billing: { createInvoice: false }
                })
              });
            }
            await load();
          } else {
            const ns = db.students.map((x) => x.id === tuStu ? { ...x, balance: (parseInt(x.balance, 10) || 0) + credits, lastActive: todayISO() } : x);
            const ok = await save({ ...db, students: ns, logs: [mkLog(s.name, "充值购课", `+${credits}`, noteStr, fee, { payMethod: tuPay, studentId: s.id }), ...db.logs] });
            if (!ok) return;
          }
          e.target.reset();
          setTuCr("");
          setTuFee("");
          setTuPkg("");
          setTuPay("微信");
          setTuStu(null);
          setTuCreateInvoice(false);
          setTuPaymentReceived(true);
          setSettlementPayerState({ mode: "student", accountId: "", createPayload: null, linkedStudentIds: [] });
          settlementResolvedAccountRef.current = "";
          settlementPayerIntentRef.current = "";
          const newBal = (parseInt(s.balance, 10) || 0) + credits;
          const cMsg = renderMessage(
            "topup",
            "{student} 您好！已为您成功充值 {credits} 课时{fee}，当前账户共 {balance} 课时。感谢您对 {studio} 的信任！",
            { student: s.name, credits, fee: fee ? `（实收 $${fee.toFixed(2)}）` : "", balance: newBal }
          );
          const invoiceAction = settlement?.invoiceId ? { label: "查看发票", onClick: () => setTab("billing", { recordId: settlement.invoiceId }) } : { label: "复制充值确认（发家长）", onClick: () => copyText(cMsg, "充值确认已复制") };
          showToast(
            createInvoice ? `${s.name} 充值 ${credits} 课时，已${paymentReceived ? "开票并登记收款" : "开票待收款"}` : `${s.name} 充值 ${credits} 课时 / $${fee.toFixed(2)}`,
            "success",
            invoiceAction
          );
        } catch (err) {
          showToast(`充值失败：${err.message}`, "error");
        } finally {
          setBusy(false);
        }
      };
      confirm2(confirmation, doTopUp, { confirmText: createInvoice ? "确认开票并入账" : fee === 0 ? "确认免费充课" : "确认入账" });
    };
    const nextRefundRequestId = (signature) => {
      if (refundRequestRef.current.signature !== signature) {
        const id = window.crypto && window.crypto.randomUUID ? window.crypto.randomUUID() : `refund-${Date.now()}-${Math.random().toString(16).slice(2)}`;
        refundRequestRef.current = { signature, id };
      }
      return refundRequestRef.current.id;
    };
    const handleRefund = async (e) => {
      e.preventDefault();
      if (!canRefund) {
        showToast("当前角色无退款权限", "error");
        return;
      }
      const credits = Number(rfCr);
      const amountCents = Math.round((parseFloat(rfAmt) || 0) * 100);
      const source = refundSources.find((item) => String(item.sourceTransactionId) === String(rfSourceId));
      const s = db.students.find((x) => x.id === tuStu);
      if (!s) {
        showToast("请选择学员", "error");
        return;
      }
      if (!source) {
        showToast("请选择一笔原充值，再继续退款", "error");
        return;
      }
      if (!Number.isFinite(credits) || credits <= 0) {
        showToast("请输入有效退课节数", "error");
        return;
      }
      if (credits > Number(source.availableCredits || 0)) {
        showToast(`退课节数不能超过所选原充值剩余 ${source.availableCredits} 节`, "error");
        return;
      }
      if (amountCents < 0) {
        showToast("退款金额无效", "error");
        return;
      }
      if (rfAdjustDocuments && (amountCents <= 0 || amountCents > Number(source.availableAmountCents || 0))) {
        showToast(`同步退款金额不能超过所选原充值剩余 $${(Number(source.availableAmountCents || 0) / 100).toFixed(2)}`, "error");
        return;
      }
      if (!rfReason.trim()) {
        showToast("请填写退款原因", "error");
        return;
      }
      if (rfAdjustDocuments && (!canSyncRefund || !source.syncAvailable)) {
        showToast("该充值没有完整的发票/付款桥，不能同步调整钱款单据。", "error");
        return;
      }
      const signature = JSON.stringify({
        studentId: tuStu,
        sourceCreditTransactionId: rfSourceId,
        credits,
        amountCents,
        paymentMethod: settlementPaymentMethod[tuPay] || "other",
        reason: rfReason.trim(),
        adjustDocuments: rfAdjustDocuments
      });
      const requestId = nextRefundRequestId(signature);
      const invoiceLabel = source.invoiceNumber || "未关联发票";
      const confirmation = rfAdjustDocuments ? `确认 ${s.name} 从原充值 ${invoiceLabel} 退 ${credits} 节、退款 $${(amountCents / 100).toFixed(2)}（${tuPay}），同时开具贷记单并登记付款退款？` : `确认 ${s.name} 从原充值 ${invoiceLabel} 退 ${credits} 节、退款 $${(amountCents / 100).toFixed(2)}（${tuPay}）？只改课时账本和现金净额，不改变发票或付款记录。`;
      confirm2(confirmation, async () => {
        if (busy) return;
        setBusy(true);
        try {
          let result = null;
          if (rfAdjustDocuments) {
            result = await v1Api(`/students/${encodeURIComponent(s.id)}/credit-refunds`, {
              method: "POST",
              body: JSON.stringify({
                requestId,
                sourceCreditTransactionId: rfSourceId,
                credits: String(credits),
                amountCents,
                paymentMethod: settlementPaymentMethod[tuPay] || "other",
                reason: rfReason.trim(),
                billing: { adjustDocuments: true }
              })
            });
          } else {
            result = await v1Api(`/students/${encodeURIComponent(s.id)}/credit-refunds`, {
              method: "POST",
              body: JSON.stringify({
                requestId,
                sourceCreditTransactionId: rfSourceId,
                credits: String(credits),
                amountCents,
                paymentMethod: settlementPaymentMethod[tuPay] || "other",
                reason: rfReason.trim(),
                billing: { adjustDocuments: false }
              })
            });
          }
          await load();
          setRfCr("");
          setRfAmt("");
          setRfAmountTouched(false);
          setRfReason("");
          setRfSourceId("");
          setRfAdjustDocuments(false);
          setRefundSources([]);
          setTuStu(null);
          const newBal = (parseFloat(s.balance) || 0) - credits;
          const cMsg = `${s.name} 您好！已为您办理退课 ${credits} 节、退款 $${(amountCents / 100).toFixed(2)}（${tuPay}），当前剩余 ${newBal} 课时。感谢您的理解与支持。`;
          const action = result?.invoiceId ? { label: "查看原发票", onClick: () => setTab("billing", { recordId: result.invoiceId }) } : { label: "复制退款确认（发家长）", onClick: () => copyText(cMsg, "退款确认已复制") };
          showToast(
            rfAdjustDocuments ? `${s.name} 已退款并开具贷记单 $${(amountCents / 100).toFixed(2)}` : `${s.name} 退课 ${credits} 节 / 退款 $${(amountCents / 100).toFixed(2)}`,
            "warn",
            action
          );
        } catch (err) {
          showToast(`退款失败：${err.message}`, "error");
        } finally {
          setBusy(false);
        }
      }, { danger: true, confirmText: rfAdjustDocuments ? "确认退款并开贷记单" : `确认退课 ${credits} 节` });
    };
    const handleAddStudent = (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const firstName = fd.get("firstName").trim();
      const lastName = fd.get("lastName").trim();
      if (!firstName) {
        showToast("First Name 不能为空", "error");
        return;
      }
      const fullName = lastName ? `${firstName} ${lastName}` : firstName;
      const mobile = fd.get("mobile").trim();
      const email = fd.get("email").trim();
      const wechat = (fd.get("wechat") || "").trim();
      const balance = parseInt(fd.get("balance") || "0", 10);
      const remark = fd.get("remark") || "";
      const preferences = collectPreferences(fd);
      const legacyPrefs = legacyPreferenceValues(preferences, fd);
      const birthday = (fd.get("birthday") || "").trim();
      const enrollmentDate = (fd.get("enrollmentDate") || todayISO()).trim();
      const doCreate = async () => {
        if (busy) return;
        setBusy(true);
        try {
          const ns = {
            id: Date.now(),
            firstName,
            lastName,
            name: fullName,
            mobile,
            email,
            wechat,
            photo: formPhoto,
            preferences,
            ...legacyPrefs,
            birthday,
            enrollmentDate,
            balance,
            remark,
            lastActive: todayISO(),
            archived: false
          };
          const ok = await save({ ...db, students: [ns, ...db.students], logs: [mkLog(fullName, "新生注册", `+${balance}`, "系统建档", 0, { studentId: ns.id }), ...db.logs] });
          if (!ok) return;
          e.target.reset();
          setFormPhoto("");
          setTab("students");
          setSrch("");
          showToast(`${fullName} 已建档`);
        } finally {
          setBusy(false);
        }
      };
      if (db.students.some((s) => s.name.toLowerCase() === fullName.toLowerCase())) {
        confirm2(`已存在同名学员 "${fullName}"，仍要继续建档？`, doCreate, { confirmText: "继续建档" });
      } else {
        doCreate();
      }
    };
    const handleUpdateStudent = async (e) => {
      e.preventDefault();
      const fd = new FormData(e.target);
      const firstName = fd.get("firstName").trim();
      if (!firstName) {
        showToast("First Name 不能为空", "error");
        return;
      }
      if (busy) return;
      setBusy(true);
      try {
        const lastName = fd.get("lastName").trim();
        const newName = lastName ? `${firstName} ${lastName}` : firstName;
        const mobile = fd.get("mobile").trim();
        const email = fd.get("email").trim();
        const wechat = (fd.get("wechat") || "").trim();
        const balance = parseInt(fd.get("balance") || String(selS.balance ?? 0), 10) || 0;
        const remark = fd.get("remark") || "";
        const preferences = collectPreferences(fd);
        const legacyPrefs = legacyPreferenceValues(preferences, fd, selS);
        const birthday = (fd.get("birthday") || "").trim();
        const enrollmentDate = (fd.get("enrollmentDate") || "").trim();
        const diff = balance - (parseInt(selS.balance, 10) || 0);
        const oldName = selS.name;
        const ns = db.students.map((s) => s.id === selS.id ? { ...s, firstName, lastName, name: newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, enrollmentDate, photo: editPhoto, ...diff !== 0 ? { lastActive: todayISO() } : {} } : s);
        const otherSameName = db.students.some((s) => s.id !== selS.id && (s.name || "").toLowerCase() === oldName.toLowerCase());
        const nl = oldName !== newName ? db.logs.map((l) => {
          if (l.studentId === selS.id) return { ...l, studentName: newName };
          if (!l.studentId && !otherSameName && l.studentName === oldName) return { ...l, studentName: newName };
          return l;
        }) : db.logs;
        const changeStr = diff !== 0 ? diff > 0 ? `+${diff}` : `${diff}` : "0";
        const enrollmentDateChanged = enrollmentDate !== (selS.enrollmentDate || "");
        const noteStr = diff !== 0 ? "管理端校准" : oldName !== newName ? `改名: ${oldName}→${newName}` : enrollmentDateChanged ? `入学日期: ${selS.enrollmentDate || "未设置"}→${enrollmentDate || "未设置"}` : "信息修改";
        if (TENANT_SLUG) {
          const ok = await save({ ...db, students: ns, logs: nl });
          if (!ok) return;
          if (diff !== 0) {
            await v1Api(`/students/${selS.id}/credit-transactions`, {
              method: "POST",
              body: JSON.stringify({
                transactionType: "adjustment",
                legacy_type: diff > 0 ? "adjustment_in" : "adjustment_out",
                amount: Math.abs(diff),
                note: "管理端校准"
              })
            });
            await load();
          }
        } else {
          const ok = await save({ ...db, students: ns, logs: [mkLog(newName, diff !== 0 ? "调整课时" : "更新档案", changeStr, noteStr, 0, { studentId: selS.id }), ...nl] });
          if (!ok) return;
        }
        setSelS({ ...selS, firstName, lastName, name: newName, mobile, email, wechat, balance, remark, preferences, ...legacyPrefs, birthday, enrollmentDate, photo: editPhoto, ...diff !== 0 ? { lastActive: todayISO() } : {} });
        setEditP(false);
        showToast("档案已更新");
      } finally {
        setBusy(false);
      }
    };
    const handleDelete = (sid, sname) => {
      confirm2(`此操作不可撤销。

将永久删除 ${sname} 的学员档案与全部排课记录。历史操作日志会保留（用于审计），但档案本身无法恢复。

如果只是想让 TA 不再出现在名单里，请改用「归档」——归档随时可以恢复。`, async () => {
        if (busy) return;
        setBusy(true);
        try {
          const ns = db.students.filter((s) => s.id !== sid);
          const nr = { ...db.rosters };
          Object.keys(nr).forEach((d) => {
            nr[d] = nr[d].filter((id) => id !== sid);
          });
          const ok = await save({ ...db, students: ns, rosters: nr, logs: [mkLog(sname, "彻底删除档案", "0", "管理员移除", 0, { studentId: sid }), ...db.logs] });
          if (!ok) return;
          setSelS(null);
          setEditP(false);
          showToast(`${sname} 已移除`, "warn");
        } finally {
          setBusy(false);
        }
      }, { danger: true, confirmText: "永久删除" });
    };
    const patchSelectedStudent = (patch) => {
      setSelS((current) => current ? { ...current, ...patch } : current);
      setDb((current) => ({
        ...current,
        students: current.students.map((student) => student.id === selS?.id ? { ...student, ...patch } : student)
      }));
    };
    const generateStudentAccessCode = async () => {
      if (!selS || !TENANT_SLUG) return;
      setBusy(true);
      try {
        const data = await v1Api(`/students/${encodeURIComponent(selS.id)}/access-code`, {
          method: "POST",
          body: "{}"
        });
        setAccessCodeResult({ studentId: selS.id, code: data.code });
        patchSelectedStudent({ hasAccessCode: true, accessCodeUpdatedAt: data.updatedAt });
        showToast("学员专区访问码已生成；明文只显示这一次");
      } catch (e) {
        showToast(`访问码生成失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const revokeStudentAccessCode = () => {
      if (!selS || !TENANT_SLUG) return;
      confirm2(`${selS.name} 当前的访问码会立即作废，已登录的会话也会马上退出，家长将无法再查询课时与记录。

之后可以随时重新生成一个新访问码交给家长。`, async () => {
        setBusy(true);
        try {
          await v1Api(`/students/${encodeURIComponent(selS.id)}/access-code`, { method: "DELETE" });
          setAccessCodeResult(null);
          patchSelectedStudent({ hasAccessCode: false, accessCodeUpdatedAt: null });
          showToast("学员专区已停用", "warn");
        } catch (e) {
          showToast(`停用失败：${e.message}`, "error");
        } finally {
          setBusy(false);
        }
      }, { danger: true, confirmText: "停用专区" });
    };
    const savePublicationConsent = async () => {
      if (!selS || !consentEdit || consentEdit.mode !== "confirm") return;
      if (!consentEdit.by.trim() || !consentEdit.relationship || !consentEdit.method) {
        showToast("请填写授权人、关系和授权方式", "warn");
        return;
      }
      setBusy(true);
      try {
        const data = await v1Api(`/students/${encodeURIComponent(selS.id)}/publication-consent`, {
          method: "PUT",
          body: JSON.stringify({
            consentBy: consentEdit.by,
            relationship: consentEdit.relationship,
            consentMethod: consentEdit.method,
            noticeVersion: "2026-07-18",
            note: consentEdit.note || ""
          })
        });
        patchSelectedStudent({ publicationConsent: {
          status: "confirmed",
          by: data.consent.consentBy,
          relationship: data.consent.relationship,
          method: data.consent.consentMethod,
          noticeVersion: data.consent.noticeVersion,
          at: data.consent.createdAt
        } });
        setConsentEdit(null);
        showToast("官网作品展示授权已记录");
      } catch (e) {
        showToast(`授权保存失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const withdrawPublicationConsent = () => {
      if (!selS || consentEdit?.mode !== "withdraw") return;
      if (!consentEdit.note.trim()) {
        showToast("请填写撤回原因，便于后续审计", "warn");
        return;
      }
      confirm2(`${selS.name} 目前展示在官网的内容会立即全部下架，家长和访客都不会再看到。

私人记录不受影响，仍保留在学员专区里。撤回会作为一条不可覆盖的审计记录留存。`, async () => {
        setBusy(true);
        try {
          const data = await v1Api(`/students/${encodeURIComponent(selS.id)}/publication-consent`, {
            method: "DELETE",
            body: JSON.stringify({ note: consentEdit.note.trim() })
          });
          const portfolio = (selS.portfolio || []).map((item) => ({ ...item, public: false, visibility: "private" }));
          patchSelectedStudent({ publicationConsent: { status: "withdrawn", at: data.consent.createdAt }, portfolio });
          setConsentEdit(null);
          showToast(`授权已撤回，${data.unpublishedItems || 0} 件作品已下架`, "warn");
        } catch (e) {
          showToast(`撤回失败：${e.message}`, "error");
        } finally {
          setBusy(false);
        }
      }, { danger: true, confirmText: "撤回并下架" });
    };
    const portfolioDoUpload = async (file, note, date, title, isPublic = false) => {
      if (!selS) return;
      setPortBusy(true);
      try {
        const fd = new FormData();
        fd.append("file", file);
        fd.append("studentId", String(selS.id));
        fd.append("note", note || "");
        fd.append("title", title || "");
        fd.append("date", date || todayISO());
        fd.append("public", isPublic ? "1" : "0");
        const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/upload`, {
          method: "POST",
          credentials: "include",
          headers: { "X-Requested-With": "StudioSaaS" },
          body: fd
        });
        if (r.status === 401) {
          showToast("登录已过期", "error");
          return;
        }
        if (!r.ok) {
          showToast("上传失败，请重试", "error");
          return;
        }
        const res = await r.json();
        const newPort = [res.item, ...selS.portfolio || []];
        setSelS((p) => ({ ...p, portfolio: newPort }));
        setDb((d) => ({ ...d, students: d.students.map((s) => s.id === selS.id ? { ...s, portfolio: newPort } : s) }));
        showToast(`${workNoun}已上传`, "success");
        if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
        setPortUpload(false);
        setPortUpFile(null);
      } catch (e) {
        showToast("上传失败", "error");
      } finally {
        setPortBusy(false);
      }
    };
    const portfolioDoDelete = async (pid) => {
      if (!selS) return;
      confirm2(`此操作不可撤销。

照片会从服务器删除，家长在学员专区也将不再看到它。如果只是不想公开展示，取消勾选「展示到官网作品墙」即可，照片仍会保留在私人记录里。`, async () => {
        const sid = String(selS.id);
        try {
          const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(pid)}`, {
            method: "DELETE",
            credentials: "include",
            headers: { "X-Requested-With": "StudioSaaS" }
          });
          if (r.status === 401) {
            showToast("登录已过期，请重新登录", "error");
            return;
          }
          if (!r.ok) {
            showToast("删除失败", "error");
            return;
          }
          const newPort = (selS.portfolio || []).filter((i) => String(i.id) !== String(pid));
          setSelS((p) => ({ ...p, portfolio: newPort }));
          setDb((d) => ({ ...d, students: d.students.map((s) => s.id === selS.id ? { ...s, portfolio: newPort } : s) }));
          if (portLB) {
            if (newPort.length === 0) setPortLB(null);
            else setPortLB((p) => ({ ...p, items: newPort, idx: Math.max(0, Math.min(p.idx, newPort.length - 1)) }));
          }
          showToast("已删除", "warn");
        } catch (e) {
          showToast("删除失败", "error");
        }
      }, { danger: true, confirmText: "删除" });
    };
    const portfolioDoUpdateNote = async () => {
      if (!portEdit) return;
      const { sid, item, note, date, title, public: isPublic = false } = portEdit;
      try {
        const r = await fetch(`/s/${encodeURIComponent(tenantSlug)}/v1/legacy-cms/portfolio/${encodeURIComponent(sid)}/${encodeURIComponent(item.id)}`, {
          method: "PATCH",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "StudioSaaS"
          },
          body: JSON.stringify({ note, date, title, public: isPublic })
        });
        if (r.status === 401) {
          showToast("登录已过期，请重新登录", "error");
          return;
        }
        if (!r.ok) {
          showToast("更新失败", "error");
          return;
        }
        const newPort = (selS?.portfolio || []).map((i) => String(i.id) === String(item.id) ? { ...i, note, date, title, public: isPublic, visibility: isPublic ? "shared" : "private" } : i);
        setSelS((p) => p ? { ...p, portfolio: newPort } : p);
        setDb((d) => ({ ...d, students: d.students.map((s) => s.id === selS?.id ? { ...s, portfolio: newPort } : s) }));
        setPortLB((p) => p ? { ...p, items: newPort } : null);
        setPortEdit(null);
        showToast("已更新", "success");
      } catch (e) {
        showToast("更新失败", "error");
      }
    };
    const addToRoster = async () => {
      if (!rPick || busy) return;
      if (dayIds.includes(rPick)) {
        const s = db.students.find((x) => x.id === rPick);
        showToast(`${s ? s.name : "该学员"} 已在当日名单中`, "warn");
        setRPick(null);
        return;
      }
      setBusy(true);
      try {
        const cur = db.rosters[rDate] || [];
        if (!cur.includes(rPick)) {
          if (TENANT_SLUG) {
            await addDailyRosterStudents(
              rDate,
              [rPick],
              "manual",
              "scheduled",
              { classTime: rTime || null, oneToOne: rOneToOne }
            );
            if (rTime) {
              const same = (db.rosters[rDate] || []).filter((id) => (rosterMetaFor(rDate, id).classTime || "") === rTime).length + 1;
              const name = db.students.find((x) => x.id === rPick)?.name || "学员";
              showToast(
                `${name} 已加入 ${rTime}；该时段共 ${same} 人`,
                rOneToOne && same > 1 ? "warn" : "success"
              );
            }
          } else {
            const ok = await save({ ...db, rosters: { ...db.rosters, [rDate]: [...cur, rPick] } });
            if (!ok) return;
          }
        }
        setRPick(null);
        setROneToOne(false);
      } finally {
        setBusy(false);
      }
    };
    const removeFromRoster = async (sid) => {
      if (busy) return;
      setBusy(true);
      try {
        if (TENANT_SLUG) {
          const entry = (db.rosterEntries?.[rDate] || {})[sid];
          if (!entry?.id) {
            showToast("未找到可移除的手动排课记录", "warn");
            return;
          }
          await v1Api(`/daily-roster/${encodeURIComponent(entry.id)}`, { method: "DELETE" });
          await load();
          showToast("已从当日排课移除", "warn", {
            label: "撤销移除",
            onClick: async () => {
              try {
                await v1Api(`/daily-roster/${encodeURIComponent(entry.id)}/undo`, { method: "POST", body: "{}" });
                await load();
                showToast("已恢复当日排课");
              } catch (e) {
                showToast(`恢复失败：${e.message}`, "error");
              }
            }
          });
        } else {
          const ok = await save({ ...db, rosters: { ...db.rosters, [rDate]: (db.rosters[rDate] || []).filter((id) => id !== sid) } });
          if (!ok) return;
        }
      } finally {
        setBusy(false);
      }
    };
    const approveTenant = async (pid, fullName, credits, existingStudentId) => {
      setBusy(true);
      try {
        const res = await v1Api(`/registrations/${pid}`, {
          method: "PATCH",
          body: JSON.stringify({ status: "approved", ...existingStudentId ? { existingStudentId } : {} })
        });
        const newSid = existingStudentId || res.student_id || res.registration && res.registration.student_id;
        if (credits > 0 && newSid) {
          await v1Api(`/students/${newSid}/credit-transactions`, {
            method: "POST",
            body: JSON.stringify({ transactionType: "migration", amount: credits, note: "注册审批初始课时" })
          });
        }
        await load();
        showToast(existingStudentId ? `${fullName} 的报名已并入既有档案` : `${fullName} 已批准建档，家长将收到确认邮件`);
        setApproveCredits((p) => {
          const n = { ...p };
          delete n[pid];
          return n;
        });
      } catch (e) {
        showToast(`批准失败：${e.message}`, "error");
      } finally {
        setBusy(false);
        setDupPick(null);
      }
    };
    const approveStudent = async (pid) => {
      const pen = (db.pending || []).find((p) => p.id === pid);
      if (!pen) return;
      if (busy) return;
      const credits = parseInt(approveCredits[pid] || "0", 10);
      const fn = pen.firstName || "", ln = pen.lastName || "";
      const fullName = ln ? `${fn} ${ln}` : fn;
      const doApprove = async () => {
        setBusy(true);
        try {
          if (TENANT_SLUG) {
            const dc = await v1Api(`/registrations/${pid}/duplicate-candidates`).catch(() => ({ candidates: [] }));
            if ((dc.candidates || []).length) {
              setBusy(false);
              setDupPick({ pid, fullName, credits, candidates: dc.candidates });
              return;
            }
            await approveTenant(pid, fullName, credits, null);
            return;
          } else {
            const ns = {
              id: Date.now(),
              firstName: fn,
              lastName: ln,
              name: fullName,
              mobile: pen.mobile || "",
              wechat: pen.wechat || "",
              email: pen.email || "",
              photo: pen.photo || "",
              preferences: pen.preferences || {},
              ...legacyPreferenceValues(pen.preferences || {}, null, pen),
              birthday: pen.birthday || "",
              balance: credits,
              remark: pen.message || "",
              lastActive: todayISO(),
              archived: false
            };
            const newPending = (db.pending || []).filter((p) => p.id !== pid);
            const ok = await save({
              ...db,
              students: [ns, ...db.students],
              pending: newPending,
              logs: [mkLog(fullName, "批准注册", `+${credits}`, `来自注册门户，管理员审批`, 0, { studentId: ns.id }), ...db.logs]
            });
            if (!ok) return;
            showToast(`${fullName} 已批准建档`);
          }
          setApproveCredits((p) => {
            const n = { ...p };
            delete n[pid];
            return n;
          });
        } catch (e) {
          showToast(`批准失败：${e.message}`, "error");
        } finally {
          setBusy(false);
        }
      };
      if (db.students.some((s) => s.name.toLowerCase() === fullName.toLowerCase())) {
        confirm2(`已存在同名学员 "${fullName}"，仍要继续建档？`, doApprove, { confirmText: "继续建档" });
      } else {
        doApprove();
      }
    };
    const rejectStudent = (pid) => {
      const pen = (db.pending || []).find((p) => p.id === pid);
      if (!pen) return;
      const name = pen.lastName ? `${pen.firstName} ${pen.lastName}` : pen.firstName;
      confirm2(`拒绝 "${name}" 的注册申请？${TENANT_SLUG ? "（家长将收到通知邮件）" : "并删除该记录？"}`, async (raw) => {
        if (busy) return;
        setBusy(true);
        try {
          if (TENANT_SLUG) {
            const note = String(raw || "").trim();
            await v1Api(`/registrations/${pid}`, {
              method: "PATCH",
              body: JSON.stringify({ status: "rejected", reviewNote: note || "管理员拒绝注册申请" })
            });
            await load();
          } else {
            const newPending = (db.pending || []).filter((p) => p.id !== pid);
            const ok = await save({
              ...db,
              pending: newPending,
              logs: [mkLog(name, "拒绝注册", "0", "管理员拒绝注册申请"), ...db.logs]
            });
            if (!ok) return;
          }
          setApproveCredits((p) => {
            const n = { ...p };
            delete n[pid];
            return n;
          });
          showToast(`${name} 的申请已拒绝`, "warn");
        } catch (e) {
          showToast(`操作失败：${e.message}`, "error");
        } finally {
          setBusy(false);
        }
      }, {
        danger: true,
        confirmText: "确认拒绝",
        prompt: TENANT_SLUG ? true : false,
        promptLabel: "拒绝原因（将随通知邮件发送给家长，可留空）",
        promptPlaceholder: "可留空"
      });
    };
    const advanceRegistration = async (pid, status) => {
      if (busy || !TENANT_SLUG) return;
      setBusy(true);
      try {
        const nextDate = followUpDates[pid] || "";
        await v1Api(`/registrations/${pid}`, {
          method: "PATCH",
          body: JSON.stringify({
            status,
            nextFollowUpAt: nextDate ? `${nextDate}T09:00:00` : "",
            reviewNote: status === "contacted" ? "Studio contacted this lead." : ""
          })
        });
        await load();
        showToast(status === "contacted" ? "已标记联系" : status === "trial_booked" ? "已预约试听" : "已加入跟进");
      } catch (e) {
        showToast(`更新失败：${e.message}`, "error");
      } finally {
        setBusy(false);
      }
    };
    const downloadTenantExport = async (path, fallbackName) => {
      if (!TENANT_SLUG) return;
      try {
        const response = await fetch(`/s/${encodeURIComponent(TENANT_SLUG)}/v1/export/${path}`, { credentials: "include" });
        if (!response.ok) {
          const body = await response.json().catch(() => ({}));
          throw new Error(body.message || `HTTP ${response.status}`);
        }
        const blob = await response.blob();
        const disposition = response.headers.get("Content-Disposition") || "";
        const match = disposition.match(/filename="?([^";]+)"?/i);
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = match?.[1] || fallbackName;
        a.click();
        setTimeout(() => URL.revokeObjectURL(url), 1e3);
      } catch (error) {
        showToast(`导出失败：${error.message}`, "error");
      }
    };
    const exportStudentsCSV = () => downloadTenantExport("students.csv", `Studio_Students_${todayISO()}.csv`);
    const exportRevenueCSV = () => downloadTenantExport("revenue.csv", `Studio_Revenue_${todayISO()}.csv`);
    const exportLogsCSV = () => downloadTenantExport("credit-ledger.csv", `Studio_Ledger_${todayISO()}.csv`);
    const requestLogout = () => {
      closeSettings();
      confirm2("确认退出登录？", doLogout, { confirmText: "退出登录" });
    };
    if (!loggedIn) return /* @__PURE__ */ React.createElement(LoginScreen, { onLogin: refreshSession });
    if (!conn && accessDenied) return /* @__PURE__ */ React.createElement("div", { className: "min-h-screen flex items-center justify-center bg-gray-900 text-white p-4" }, /* @__PURE__ */ React.createElement("div", { className: "text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-center mb-3 text-amber-400" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-12 h-12" })), /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-3" }, "无权访问该工作室 / Access denied"), accessDenied.code === "support_session_required" ? /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-3 leading-relaxed" }, "平台账号需要先在 Super Admin 控制台为该工作室开启支持会话（含原因）后才能进入。", /* @__PURE__ */ React.createElement("br", null), "Start an audited support session for this studio from the Super Admin console first.") : /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-3 leading-relaxed" }, "当前账号没有访问该工作室的权限。如需协助请联系工作室负责人。", /* @__PURE__ */ React.createElement("br", null), "This account does not have access to this studio."), accessDenied.message && /* @__PURE__ */ React.createElement("p", { className: "text-gray-500 text-xs bg-gray-900 p-2 rounded mb-4" }, accessDenied.message), /* @__PURE__ */ React.createElement("button", { onClick: load, className: "bg-indigo-600 active:bg-indigo-700 px-8 py-3 rounded-xl font-bold w-full mb-2" }, "重新检查 / Check again"), /* @__PURE__ */ React.createElement("button", { onClick: doLogout, className: "bg-gray-700 active:bg-gray-600 px-8 py-3 rounded-xl font-bold w-full" }, "退出登录 / Log out")));
    if (!conn) return /* @__PURE__ */ React.createElement("div", { className: "min-h-screen flex items-center justify-center bg-gray-900 text-white p-4" }, /* @__PURE__ */ React.createElement("div", { className: "text-center p-8 max-w-md bg-gray-800 rounded-2xl shadow-2xl border border-gray-700 anim w-full" }, connErr ? /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("div", { className: "flex justify-center mb-3 text-amber-400" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-12 h-12" })), /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mb-3" }, "连接失败 / Connection failed"), TENANT_SLUG ? /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-3 leading-relaxed" }, "服务暂时不可达，请稍后重试；如持续出现请联系支持。", /* @__PURE__ */ React.createElement("br", null), "The service is temporarily unreachable — please retry shortly.") : (
      /* Standalone edition only: the local dev hint stays accurate there. */
      /* @__PURE__ */ React.createElement("p", { className: "text-gray-400 text-sm mb-3 leading-relaxed" }, "请确认终端正在运行 ", /* @__PURE__ */ React.createElement("code", { className: "text-indigo-400 bg-gray-900 px-1 rounded" }, "python3 server.py"))
    ), /* @__PURE__ */ React.createElement("p", { className: "text-red-400 text-xs font-mono bg-gray-900 p-2 rounded mb-4" }, connErr), /* @__PURE__ */ React.createElement("button", { onClick: load, className: "bg-indigo-600 active:bg-indigo-700 px-8 py-3 rounded-xl font-bold w-full" }, "重新连接")) : /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("span", { className: "sp mb-3 w-10 h-10 border-4 block mx-auto" }), /* @__PURE__ */ React.createElement("h2", { className: "text-xl font-bold mt-3" }, "连接中..."))));
    const pendingCount = (db.pending || []).length + bookings.length;
    const NAV_GROUPS = [
      { key: "today", label: "今日", items: [
        { k: "dashboard", i: "dashboard", l: "工作台", s: "工作台" },
        { k: "pending", i: "clipboard", l: "待处理", s: "待处理", badge: pendingCount }
      ] },
      { key: "teaching", label: "教学运营", items: [
        { k: "roster", i: "calendar", l: "课程安排", s: "课表" },
        { k: "courses", i: "calendar", l: "课程目录", s: "课程" },
        { k: "students", i: "users", l: "学员档案", s: "学员" },
        { k: "works", i: "image", l: "作品管理", s: "作品" }
      ] },
      { key: "business", label: "经营", items: [
        { k: "billing", i: "money", l: "账单发票", s: "账单" },
        { k: "topup", i: "money", l: "充值与退款", s: "结算" },
        { k: "finance", i: "trend", l: "课酬与报表", s: "财务" },
        { k: "stats", i: "trend", l: "经营统计", s: "统计" }
      ] },
      { key: "records", label: "记录", items: [
        { k: "logs", i: "scroll", l: "操作日志", s: "日志" }
      ] }
    ].map((group) => ({ ...group, items: group.items.filter((item) => allowedTabs.includes(item.k)) })).filter((group) => group.items.length > 0);
    const NAV = NAV_GROUPS.flatMap((group) => group.items);
    const CMS_PAGE_TITLE_EXTRAS = { settings: "系统设置", new_student: "新建学员档案" };
    const cmsPageTitle = CMS_PAGE_TITLE_EXTRAS[tab] || (NAV.find((item) => item.k === tab) || {}).l || "Studio CMS";
    const actorRoleLabel = {
      owner: "Owner",
      manager: "Manager",
      teacher: "Teacher",
      front_desk: "Front Desk",
      staff: "Staff",
      platform_super_admin: "平台管理员",
      super_admin: "超级管理员"
    }[actorRole] || "工作区成员";
    const actorIdentity = (() => {
      try {
        return localStorage.getItem(`lp_admin_email_${TENANT_SLUG || "root"}`) || "当前账号";
      } catch {
        return "当前账号";
      }
    })();
    const closeSettings = () => {
      setShowSettings(false);
      if (tab === "settings") setTab("dashboard");
    };
    return /* @__PURE__ */ React.createElement("div", { className: "flex h-screen bg-gray-50" }, toast && /* @__PURE__ */ React.createElement(Toast, { key: toast.key, msg: toast.msg, type: toast.type, action: toast.action, onDone: () => setToast(null) }), icsPreview && /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "fixed inset-0 z-[60] flex items-end md:items-center justify-center bg-black/40 p-0 md:p-4",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "ics-dialog-title",
        "aria-describedby": "ics-dialog-help",
        onClick: (e) => {
          if (e.target === e.currentTarget) {
            setIcsPreview(null);
            setIcsNotice("");
          }
        }
      },
      /* @__PURE__ */ React.createElement("div", { ref: icsDialogRef, className: "bg-white w-full md:max-w-lg md:rounded-2xl rounded-t-2xl max-h-[88vh] overflow-y-auto" }, /* @__PURE__ */ React.createElement("div", { className: "px-5 py-4 border-b border-gray-100 flex items-start justify-between gap-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { id: "ics-dialog-title", className: "font-bold text-gray-900" }, icsPreview.downloadKind === "roster" ? "导出当日排课" : "导出固定课表"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-0.5" }, icsPreview.date ? `${fmtDate(icsPreview.date)} · ` : "", "Apple / Google 通用 .ics")), /* @__PURE__ */ React.createElement(
        "button",
        {
          ref: icsCloseButtonRef,
          onClick: () => {
            setIcsPreview(null);
            setIcsNotice("");
          },
          "aria-label": "关闭日历预览",
          className: "text-gray-400 text-2xl leading-none px-2 min-h-[44px]"
        },
        "×"
      )), /* @__PURE__ */ React.createElement("div", { className: "p-5 space-y-3" }, icsNotice && /* @__PURE__ */ React.createElement("div", { role: "status", className: "rounded-xl px-4 py-3 bg-amber-50 border border-amber-200 text-xs font-bold text-amber-800" }, icsNotice), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-3 gap-2" }, [["events", "日历事件"], ["classes", "普通班课"], ["oneToOne", "1 对 1"]].map(([k, label]) => /* @__PURE__ */ React.createElement("div", { key: k, className: "bg-gray-50 rounded-xl py-3 text-center" }, /* @__PURE__ */ React.createElement("p", { className: "text-xl font-bold text-gray-900" }, icsPreview.stats?.[k] ?? 0), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-0.5" }, label)))), (icsPreview.events || []).length === 0 ? /* @__PURE__ */ React.createElement("div", { className: "text-center py-6 px-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm text-gray-600 font-bold" }, "没有可导出的课程"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1.5 leading-relaxed" }, icsPreview.downloadKind === "roster" ? "这一天的排课是空的。先在下方名单里加入学员，再回来导出。" : "还没有固定班次。在「每周课表」新增班次后，这里就会有内容。")) : (icsPreview.events || []).map((ev) => /* @__PURE__ */ React.createElement("div", { key: ev.uid, className: "border border-gray-100 rounded-xl px-4 py-3" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-start justify-between gap-2" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-900 text-sm" }, ev.summary), /* @__PURE__ */ React.createElement("span", { className: "text-[11px] font-bold px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 flex-shrink-0" }, ev.allDay ? "全天 · 未设时间" : `${ev.durationMinutes} 分钟${ev.durationSource === "default" ? " · 默认" : ""}`)), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-1" }, ev.timeRange), (ev.participants || []).length > 0 && /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-500 mt-0.5" }, ev.participants.join("、")))), (icsPreview.skipped || []).length > 0 && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl px-4 py-3 bg-amber-50 border border-amber-200" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-amber-800" }, icsPreview.skipped.length, " 项未导出"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-amber-700 mt-1" }, icsPreview.skipped.map((x) => {
        const why = { cancelled: "已取消", "no-class-time": "未设置上课时间" }[x.reason] || x.reason || "";
        return [x.studentName, why].filter(Boolean).join(" · ");
      }).filter(Boolean).join("；"))), /* @__PURE__ */ React.createElement("div", { className: "rounded-xl px-4 py-3 bg-gray-50 text-xs text-gray-600 space-y-1" }, /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, "时区："), icsPreview.timezone?.name, icsPreview.timezone?.abbreviations?.length ? `（含 ${icsPreview.timezone.abbreviations.join("/")} 规则）` : ""), icsPreview.location && /* @__PURE__ */ React.createElement("p", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold" }, "地点："), icsPreview.location)), icsPreview.includesStudentNames && /* @__PURE__ */ React.createElement("div", { className: "rounded-xl px-4 py-3 bg-amber-50 border border-amber-200 text-xs text-amber-800" }, "此文件包含学员姓名。导入后它会留在对方的日历里，请只发给应当看到的人。"), /* @__PURE__ */ React.createElement("p", { id: "ics-dialog-help", className: "text-xs text-gray-500 leading-relaxed" }, "Apple 日历可直接打开此文件；Google 日历请在电脑端「设置 → 导入和导出」导入。 同一个文件两者通用。", icsPreview.subscribable === false && "文件是当前排课的快照，之后修改排课需要重新下载。")), /* @__PURE__ */ React.createElement("div", { className: "px-5 py-4 border-t border-gray-100 flex gap-2" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => {
            setIcsPreview(null);
            setIcsNotice("");
          },
          className: "flex-1 border border-gray-200 rounded-xl py-3 text-sm font-bold text-gray-700 min-h-[44px]"
        },
        "取消"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => downloadIcs(icsPreview),
          disabled: icsBusy || !(icsPreview.stats?.events > 0),
          title: icsPreview.stats?.events > 0 ? "" : "没有可导出的课程",
          className: "flex-1 bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white rounded-xl py-3 text-sm font-bold min-h-[44px] inline-flex items-center justify-center gap-1.5"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }),
        "下载 .ics"
      )))
    ), /* @__PURE__ */ React.createElement(ConfirmDialog, { dialog: confirmDialog, onClose: () => setConfirmDialog(null) }), portLB && portLB.items.length > 0 && /* @__PURE__ */ React.createElement(
      "div",
      {
        ref: portLightboxDialogRef,
        className: "fixed inset-0 bg-black/95 z-[90] flex flex-col",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "portfolio-lightbox-title",
        style: { paddingBottom: "env(safe-area-inset-bottom,0px)", paddingTop: "env(safe-area-inset-top,0px)" },
        onTouchStart: (e) => {
          lbTouchX.current = e.touches[0].clientX;
          lbTouchX._y = e.touches[0].clientY;
        },
        onTouchEnd: (e) => {
          const dx = e.changedTouches[0].clientX - lbTouchX.current;
          const dy = e.changedTouches[0].clientY - (lbTouchX._y || 0);
          if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) setPortLB((p) => {
            if (!p) return p;
            const next = dx < 0 ? Math.min(p.items.length - 1, p.idx + 1) : Math.max(0, p.idx - 1);
            return { ...p, idx: next };
          });
        }
      },
      /* @__PURE__ */ React.createElement(
        "div",
        {
          className: "flex justify-between items-center px-4 py-3 flex-shrink-0",
          style: { paddingTop: "max(12px,env(safe-area-inset-top,12px))" }
        },
        /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { id: "portfolio-lightbox-title", className: "text-white font-bold text-sm truncate" }, portLB.items[portLB.idx]?.title || fmtDate(portLB.items[portLB.idx]?.date)), portLB.items[portLB.idx]?.title && /* @__PURE__ */ React.createElement("p", { className: "text-white/50 text-[11px] truncate" }, fmtDate(portLB.items[portLB.idx]?.date)), portLB.items[portLB.idx]?.note && /* @__PURE__ */ React.createElement("p", { className: "inline-flex items-center gap-1.5 text-white/60 text-xs truncate" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), portLB.items[portLB.idx].note)),
        /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 flex-shrink-0" }, /* @__PURE__ */ React.createElement("span", { className: "text-white/40 text-xs" }, portLB.idx + 1, " / ", portLB.items.length), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => {
              const cur = portLB.items[portLB.idx];
              if (cur && selS) {
                setPortEdit({ sid: String(selS.id), item: cur, note: cur.note || "", title: cur.title || "", date: cur.date || todayISO(), public: !!cur.public });
                setPortLB(null);
              }
            },
            "aria-label": "编辑",
            className: "text-white/80 active:text-white w-9 h-9 flex items-center justify-center"
          },
          /* @__PURE__ */ React.createElement(Icon, { name: "pencil", className: "w-4 h-4" })
        ), /* @__PURE__ */ React.createElement("button", { onClick: () => setPortLB(null), "aria-label": "关闭", className: "text-white text-2xl font-bold w-10 h-10 flex items-center justify-center" }, "×"))
      ),
      /* @__PURE__ */ React.createElement(
        "div",
        {
          className: "flex-1 flex items-center justify-center px-2 min-h-0",
          onClick: () => setPortLB(null)
        },
        /* @__PURE__ */ React.createElement(
          "img",
          {
            src: portfolioImgSrc(selS?.id, portLB.items[portLB.idx]),
            srcSet: portfolioSrcSet(selS?.id, portLB.items[portLB.idx]),
            sizes: "100vw",
            alt: portLB.items[portLB.idx]?.title || `${selS?.name || "学员"}的作品 ${portLB.idx + 1}`,
            className: "max-w-full max-h-full object-contain rounded-xl shadow-2xl",
            onClick: (e) => e.stopPropagation(),
            onError: (e) => {
              e.target.style.display = "none";
              e.target.nextSibling && (e.target.nextSibling.style.display = "flex");
            }
          }
        ),
        /* @__PURE__ */ React.createElement("div", { style: { display: "none" }, className: "flex-col items-center justify-center gap-2 text-white/50" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5 text-4xl" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-4 h-4" })), /* @__PURE__ */ React.createElement("span", { className: "text-sm" }, "图片加载失败"))
      ),
      /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center px-4 py-3 flex-shrink-0" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setPortLB((p) => ({ ...p, idx: Math.max(0, p.idx - 1) })),
          disabled: portLB.idx === 0,
          className: "py-2.5 px-6 bg-white/20 active:bg-white/30 text-white rounded-xl font-bold text-sm disabled:opacity-30 min-h-[44px]"
        },
        "← 上一张"
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => portfolioDoDelete(String(portLB.items[portLB.idx]?.id)),
          "aria-label": "删除",
          className: "py-2.5 px-4 bg-red-500 active:bg-red-600 text-white rounded-xl text-sm min-h-[44px] flex items-center justify-center"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "trash", className: "w-4 h-4" })
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setPortLB((p) => ({ ...p, idx: Math.min(p.items.length - 1, p.idx + 1) })),
          disabled: portLB.idx === portLB.items.length - 1,
          className: "py-2.5 px-6 bg-white/20 active:bg-white/30 text-white rounded-xl font-bold text-sm disabled:opacity-30 min-h-[44px]"
        },
        "下一张 →"
      ))
    ), portUpload && /* @__PURE__ */ React.createElement(
      "div",
      {
        ref: portUploadDialogRef,
        className: "fixed inset-0 bg-black/70 z-[85] flex items-end sm:items-center justify-center sm:p-4",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "portfolio-upload-title",
        onClick: (e) => {
          if (e.target === e.currentTarget) {
            if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
            setPortUpload(false);
            setPortUpFile(null);
          }
        }
      },
      /* @__PURE__ */ React.createElement(
        "div",
        {
          className: "bg-white w-full sm:rounded-3xl sm:max-w-md shadow-2xl overflow-hidden anim",
          style: { paddingBottom: "env(safe-area-inset-bottom,0px)" }
        },
        /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center px-5 pt-5 pb-3" }, /* @__PURE__ */ React.createElement("h3", { id: "portfolio-upload-title", className: "font-bold text-gray-800 text-lg flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Icon, { name: "upload" }), " 上传", workNoun), /* @__PURE__ */ React.createElement("button", { onClick: () => {
          if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
          setPortUpload(false);
          setPortUpFile(null);
        }, "aria-label": "关闭", className: "text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center" }, "×")),
        /* @__PURE__ */ React.createElement("div", { className: "px-5 pb-5" }, !portUpFile ? /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("div", { className: "flex gap-3" }, /* @__PURE__ */ React.createElement("label", { className: "flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-purple-300 rounded-2xl cursor-pointer active:bg-purple-50 hover:bg-purple-50 transition-colors" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-400" }, /* @__PURE__ */ React.createElement(Icon, { name: "camera", className: "w-8 h-8" })), /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-purple-700" }, "拍照"), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "file",
            accept: "image/*",
            capture: "environment",
            className: "hidden",
            onChange: (e) => {
              const file = e.target.files[0];
              if (!file) return;
              if (file.size > 10 * 1024 * 1024) {
                showToast("文件太大，请先压缩", "error");
                return;
              }
              setPortUpFile({ file, dataUrl: URL.createObjectURL(file), note: "", date: todayISO(), public: false });
            }
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "flex-1 flex flex-col items-center justify-center gap-2 py-6 border-2 border-dashed border-indigo-300 rounded-2xl cursor-pointer active:bg-indigo-50 hover:bg-indigo-50 transition-colors" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5 text-3xl" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-4 h-4" })), /* @__PURE__ */ React.createElement("span", { className: "text-sm font-bold text-indigo-700" }, "从相册"), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "file",
            accept: "image/*",
            className: "hidden",
            onChange: (e) => {
              const file = e.target.files[0];
              if (!file) return;
              if (file.size > 10 * 1024 * 1024) {
                showToast("文件太大，请先压缩", "error");
                return;
              }
              setPortUpFile({ file, dataUrl: URL.createObjectURL(file), note: "", date: todayISO(), public: false });
            }
          }
        ))), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 text-center mt-3" }, "支持 JPG/PNG，最大 10 MB")) : /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("img", { src: portUpFile.dataUrl, alt: "待上传作品预览", className: "w-full h-52 object-cover rounded-2xl mb-4 bg-gray-100" }), /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "作品日期"), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "date",
            value: portUpFile.date,
            onChange: (e) => setPortUpFile((p) => ({ ...p, date: e.target.value })),
            className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
          }
        )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-4 h-4" }), "作品标题 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填")), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "text",
            value: portUpFile.title || "",
            onChange: (e) => setPortUpFile((p) => ({ ...p, title: e.target.value })),
            placeholder: "如：星空下的向日葵",
            maxLength: 40,
            className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
          }
        ), /* @__PURE__ */ React.createElement("p", { className: "mt-1.5 text-[11px] leading-relaxed text-gray-400" }, "按录入的语言原样显示，不随官网语言切换。")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "老师评语 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "选填，家长可见")), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "text",
            value: portUpFile.note,
            onChange: (e) => setPortUpFile((p) => ({ ...p, note: e.target.value })),
            placeholder: "如：水彩练习 第1期",
            maxLength: 50,
            className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-3 rounded-xl border border-purple-100 bg-purple-50 p-3 text-sm text-purple-900" }, /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "checkbox",
            checked: !!portUpFile.public,
            disabled: selS?.publicationConsent?.status !== "confirmed",
            onChange: (e) => setPortUpFile((p) => ({ ...p, public: e.target.checked })),
            className: "mt-0.5 w-4 h-4 flex-shrink-0 disabled:opacity-40"
          }
        ), /* @__PURE__ */ React.createElement("span", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold block" }, "展示到官网作品墙"), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-purple-700" }, selS?.publicationConsent?.status === "confirmed" ? "该学员已有有效公开授权；标题和评语不得包含学员全名。" : "请先在学员档案中记录公开授权，才能开启官网展示。")))), /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 mt-4" }, /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => {
              if (portUpFile?.dataUrl) URL.revokeObjectURL(portUpFile.dataUrl);
              setPortUpFile(null);
            },
            className: "flex-1 py-3 rounded-xl border border-gray-200 text-sm font-bold text-gray-500 active:bg-gray-50 min-h-[50px]"
          },
          "重新选择"
        ), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => portfolioDoUpload(portUpFile.file, portUpFile.note, portUpFile.date, portUpFile.title, portUpFile.public),
            disabled: portBusy,
            className: "flex-1 py-3 rounded-xl bg-purple-600 active:bg-purple-700 text-white text-sm font-bold disabled:opacity-50 min-h-[50px]"
          },
          portBusy ? "上传中..." : "确认上传"
        ))))
      )
    ), portEdit && /* @__PURE__ */ React.createElement(
      "div",
      {
        ref: portEditDialogRef,
        className: "fixed inset-0 bg-black/60 z-[85] flex items-end sm:items-center justify-center sm:p-4",
        role: "dialog",
        "aria-modal": "true",
        "aria-labelledby": "portfolio-edit-title",
        onClick: (e) => {
          if (e.target === e.currentTarget) setPortEdit(null);
        }
      },
      /* @__PURE__ */ React.createElement(
        "div",
        {
          className: "bg-white w-full sm:rounded-3xl sm:max-w-sm rounded-t-3xl p-5 shadow-2xl anim",
          style: { paddingBottom: "max(20px,env(safe-area-inset-bottom,20px))" }
        },
        /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center mb-4" }, /* @__PURE__ */ React.createElement("h3", { id: "portfolio-edit-title", className: "inline-flex items-center gap-1.5 font-bold text-gray-800 text-lg" }, /* @__PURE__ */ React.createElement(Icon, { name: "pencil", className: "w-4 h-4" }), "编辑作品信息"), /* @__PURE__ */ React.createElement("button", { onClick: () => setPortEdit(null), "aria-label": "关闭", className: "text-gray-400 text-2xl font-bold w-10 h-10 flex items-center justify-center" }, "×")),
        /* @__PURE__ */ React.createElement("div", { className: "space-y-3" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "calendar", className: "w-4 h-4" }), "作品日期"), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "date",
            value: portEdit.date,
            onChange: (e) => setPortEdit((p) => ({ ...p, date: e.target.value })),
            className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
          }
        )), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "image", className: "w-4 h-4" }), "作品标题"), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "text",
            value: portEdit.title || "",
            onChange: (e) => setPortEdit((p) => ({ ...p, title: e.target.value })),
            maxLength: 40,
            className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
          }
        ), /* @__PURE__ */ React.createElement("p", { className: "mt-1.5 text-[11px] leading-relaxed text-gray-400" }, "按录入的语言原样显示，不随官网语言切换。")), /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("label", { className: "inline-flex items-center gap-1.5 text-xs font-bold text-gray-500 mb-1.5 block" }, /* @__PURE__ */ React.createElement(Icon, { name: "chat", className: "w-4 h-4" }), "老师评语 ", /* @__PURE__ */ React.createElement("span", { className: "font-normal text-gray-400" }, "家长可见")), /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "text",
            value: portEdit.note,
            onChange: (e) => setPortEdit((p) => ({ ...p, note: e.target.value })),
            maxLength: 50,
            className: "w-full px-3 py-3 border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-purple-400 outline-none"
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-3 rounded-xl border border-purple-100 bg-purple-50 p-3 text-sm text-purple-900" }, /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "checkbox",
            checked: !!portEdit.public,
            disabled: selS?.publicationConsent?.status !== "confirmed",
            onChange: (e) => setPortEdit((p) => ({ ...p, public: e.target.checked })),
            className: "mt-0.5 w-4 h-4 flex-shrink-0 disabled:opacity-40"
          }
        ), /* @__PURE__ */ React.createElement("span", null, /* @__PURE__ */ React.createElement("span", { className: "font-bold block" }, "展示到官网作品墙"), /* @__PURE__ */ React.createElement("span", { className: "text-xs text-purple-700" }, selS?.publicationConsent?.status === "confirmed" ? "关闭后仍保留在学员私人作品集。" : "当前没有有效公开授权，作品只能保持私人可见。")))),
        /* @__PURE__ */ React.createElement("div", { className: "flex gap-3 mt-4" }, /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => setPortEdit(null),
            className: "flex-1 py-3 rounded-xl border border-gray-200 text-sm font-bold text-gray-500 active:bg-gray-50 min-h-[50px]"
          },
          "取消"
        ), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: portfolioDoUpdateNote,
            className: "flex-1 py-3 rounded-xl bg-purple-600 active:bg-purple-700 text-white text-sm font-bold min-h-[50px]"
          },
          "保存"
        ))
      )
    ), gOpen && /* @__PURE__ */ React.createElement(
      "div",
      {
        ref: searchDialogRef,
        className: "fixed inset-0 bg-black/60 z-[80] flex items-start justify-center pt-[10vh] px-4 backdrop-blur-sm",
        role: "dialog",
        "aria-modal": "true",
        "aria-label": "搜索学员",
        onClick: () => {
          setGOpen(false);
          setGQ("");
        }
      },
      /* @__PURE__ */ React.createElement("div", { className: "bg-white rounded-2xl shadow-2xl w-full max-w-md overflow-hidden anim", onClick: (e) => e.stopPropagation() }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 px-4 py-3 border-b" }, /* @__PURE__ */ React.createElement("span", { className: "text-gray-400" }, /* @__PURE__ */ React.createElement(Icon, { name: "search", className: "w-5 h-5" })), /* @__PURE__ */ React.createElement(
        "input",
        {
          autoFocus: true,
          type: "text",
          placeholder: "搜索学员姓名、电话、微信号...",
          value: gQ,
          onChange: (e) => setGQ(e.target.value),
          onKeyDown: (e) => {
            if (e.key === "Escape") {
              setGOpen(false);
              setGQ("");
            }
          },
          className: "flex-1 outline-none text-gray-800 text-sm bg-transparent placeholder-gray-400"
        }
      ), /* @__PURE__ */ React.createElement("kbd", { className: "hidden sm:inline text-xs text-gray-400 bg-gray-100 px-2 py-1 rounded font-mono" }, "ESC"), /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => {
            setGOpen(false);
            setGQ("");
          },
          "aria-label": "关闭搜索",
          className: "text-gray-400 active:text-gray-700 text-xl inline-flex items-center justify-center"
        },
        "×"
      )), /* @__PURE__ */ React.createElement("div", { className: "max-h-80 overflow-y-auto sl" }, !gQ.trim() && /* @__PURE__ */ React.createElement("p", { className: "text-center text-gray-400 text-sm py-8" }, "输入姓名、手机号或微信号搜索"), gQ.trim() && !gResults.length && /* @__PURE__ */ React.createElement("p", { className: "text-center text-gray-400 text-sm py-8" }, "未找到匹配学员"), gResults.map((s) => {
        const tag = getTag(s);
        return /* @__PURE__ */ React.createElement(
          "button",
          {
            key: s.id,
            className: "w-full flex items-center gap-3 px-4 py-3 hover:bg-indigo-50 active:bg-indigo-100 border-b border-gray-50 text-left min-h-[56px]",
            onClick: () => {
              setTab("students");
              setSelS(s);
              setEditP(false);
              setGOpen(false);
              setGQ("");
            }
          },
          /* @__PURE__ */ React.createElement(PhotoAvatar, { photo: s.photo, name: s.name, size: "sm" }),
          /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "font-bold text-gray-800 text-sm truncate" }, s.name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, s.mobile || "—", s.wechat ? ` · ${s.wechat}` : "")),
          /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 flex-shrink-0" }, tag && /* @__PURE__ */ React.createElement("span", { className: `inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-bold ${tag.cls}` }, /* @__PURE__ */ React.createElement(Icon, { name: tag.icon, className: "w-3 h-3" }), tag.label), /* @__PURE__ */ React.createElement(BalBadge, { n: s.balance }))
        );
      })), /* @__PURE__ */ React.createElement("div", { className: "px-4 py-2 bg-gray-50 text-xs text-gray-400 border-t" }, "点击学员查看档案 · ", /* @__PURE__ */ React.createElement("kbd", { className: "bg-gray-200 px-1 rounded font-mono" }, "⌘K"), " 打开 / 关闭"))
    ), /* @__PURE__ */ React.createElement("div", { className: "md:hidden mobile-top-bar fixed top-0 left-0 right-0 z-40 cms-chrome border-b flex items-center px-3 gap-2.5" }, tenantLogoUrl && /* @__PURE__ */ React.createElement("img", { src: tenantLogoUrl, alt: `${tenantDisplayName} logo`, className: "h-8 w-auto max-w-[96px] object-contain flex-shrink-0" }), /* @__PURE__ */ React.createElement("span", { className: "font-bold text-base flex-1 truncate" }, tenantDisplayName, " CMS"), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => {
          setGOpen(true);
          setGQ("");
        },
        "aria-label": "搜索",
        className: "w-9 h-9 flex items-center justify-center rounded-lg cms-chrome-item flex-shrink-0"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "search" })
    ), canViewCmsNotifications && /* @__PURE__ */ React.createElement(
      CmsNotificationCenter,
      {
        notifications: cmsNotifications,
        unreadCount: cmsNotificationUnreadCount,
        open: cmsNotificationOpen,
        onToggle: () => setCmsNotificationOpen((open) => !open),
        onSelect: openCmsNotification,
        onMarkAllRead: markAllCmsNotificationsRead,
        loadError: cmsNotificationError
      }
    ), /* @__PURE__ */ React.createElement(
      "button",
      {
        onClick: () => setSettingsSection("account"),
        "aria-label": "设置",
        className: "w-9 h-9 flex items-center justify-center rounded-lg cms-chrome-item flex-shrink-0"
      },
      /* @__PURE__ */ React.createElement(Icon, { name: "cog" })
    )), /* @__PURE__ */ React.createElement(
      "aside",
      {
        className: "hidden md:flex w-60 cms-chrome border-r flex-col flex-shrink-0",
        style: { paddingTop: "env(safe-area-inset-top, 0px)" }
      },
      /* @__PURE__ */ React.createElement("div", { className: "p-4 border-b cms-chrome-edge flex items-center gap-2.5" }, tenantLogoUrl && /* @__PURE__ */ React.createElement("img", { src: tenantLogoUrl, alt: `${tenantDisplayName} logo`, className: "h-9 w-auto max-w-[96px] object-contain flex-shrink-0" }), /* @__PURE__ */ React.createElement("div", { className: "min-w-0 flex-1" }, /* @__PURE__ */ React.createElement("h1", { className: "hidden md:block text-base font-bold tracking-wide truncate" }, tenantDisplayName), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400 tracking-wide" }, "Studio CMS"))),
      /* @__PURE__ */ React.createElement("nav", { className: "flex-1 px-3 py-4 space-y-4 overflow-y-auto", "aria-label": "CMS 主导航" }, NAV_GROUPS.map((group) => /* @__PURE__ */ React.createElement("section", { key: group.key, "aria-labelledby": `cms-nav-${group.key}` }, /* @__PURE__ */ React.createElement("p", { id: `cms-nav-${group.key}`, className: "px-2 mb-1 text-[11px] font-bold tracking-wide text-gray-400" }, group.label), /* @__PURE__ */ React.createElement("div", { className: "space-y-0.5" }, group.items.map(({ k, i, l, badge }) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: k,
          onClick: () => setTab(k),
          "aria-current": tab === k ? "page" : void 0,
          className: `w-full text-left px-3 py-2.5 rounded-xl flex items-center gap-2.5 text-sm min-h-[44px] cms-chrome-item ${tab === k ? "is-active font-bold" : ""}`
        },
        /* @__PURE__ */ React.createElement(Icon, { name: i }),
        /* @__PURE__ */ React.createElement("span", null, l),
        k === "dashboard" && analytics.lowBalance.length > 0 && /* @__PURE__ */ React.createElement("span", { className: "ml-auto bg-red-500 text-white text-xs font-bold px-1.5 py-0.5 rounded-full" }, analytics.lowBalance.length),
        badge > 0 && /* @__PURE__ */ React.createElement("span", { className: "ml-auto bg-amber-400 text-white text-xs font-bold px-1.5 py-0.5 rounded-full" }, badge)
      )))))),
      /* @__PURE__ */ React.createElement("div", { className: "p-3 border-t cms-chrome-edge space-y-1.5", style: { paddingBottom: "calc(env(safe-area-inset-bottom,0px) + 12px)" } }, TENANT_SLUG && /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-1.5 pb-1" }, /* @__PURE__ */ React.createElement(
        "a",
        {
          href: `/${encodeURIComponent(TENANT_SLUG)}/studio-admin`,
          className: "flex items-center justify-center rounded-lg bg-indigo-600 text-white active:bg-indigo-700 px-2 py-2.5 text-[11px] font-bold min-h-[44px]"
        },
        "网站与品牌"
      ), /* @__PURE__ */ React.createElement(
        "a",
        {
          href: `/${encodeURIComponent(TENANT_SLUG)}`,
          target: "_blank",
          rel: "noopener",
          className: "flex items-center justify-center rounded-lg cms-chrome-item border cms-chrome-edge px-2 py-2.5 text-[11px] font-bold min-h-[44px]"
        },
        "公开网站"
      )), /* @__PURE__ */ React.createElement("div", { className: "text-xs text-center rounded-lg p-1.5 border bg-green-50 text-green-700 border-green-200" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement("span", { className: "w-2 h-2 rounded-full bg-green-500", "aria-hidden": "true" }), "已连接")), db.logs.length > 1e3 && /* @__PURE__ */ React.createElement("div", { className: "text-xs text-center rounded-lg p-1.5 border bg-amber-50 text-amber-700 border-amber-200" }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "warning", className: "w-3.5 h-3.5" }), "日志 ", db.logs.length, " 条")), canManageOperations && !TENANT_SLUG && /* @__PURE__ */ React.createElement("button", { onClick: exportDB, className: "inline-flex items-center gap-1.5 w-full cms-chrome-item border cms-chrome-edge p-2.5 rounded-xl text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }), "备份导出"), /* @__PURE__ */ React.createElement("button", { onClick: load, disabled: busy, className: "inline-flex items-center gap-1.5 w-full cms-chrome-item border cms-chrome-edge p-2.5 rounded-xl text-xs font-bold min-h-[44px]" }, /* @__PURE__ */ React.createElement(Icon, { name: "refresh", className: "w-4 h-4" }), "刷新"), /* @__PURE__ */ React.createElement("button", { onClick: () => setSettingsSection("account"), className: `w-full cms-chrome-item border cms-chrome-edge p-2.5 rounded-xl text-xs font-bold min-h-[44px] ${tab === "settings" ? "is-active" : ""}` }, /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "cog", className: "w-4 h-4" }), "系统设置")), /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => confirm2("确认退出登录？下次进入需重新输入密码。", doLogout, { confirmText: "退出登录" }),
          className: "w-full cms-chrome-item p-2.5 rounded-xl text-xs font-bold min-h-[44px] active:bg-red-50 active:text-red-700"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "logout", className: "w-4 h-4" }), "退出登录")
      ))
    ), /* @__PURE__ */ React.createElement(
      "main",
      {
        className: "flex-1 overflow-y-auto p-4 md:pt-0 md:p-6 md:pb-0 sl mobile-main-top mobile-pb",
        style: {
          paddingTop: "calc(1.5rem + env(safe-area-inset-top, 0px))",
          paddingBottom: "env(safe-area-inset-bottom, 0px)"
        }
      },
      /* @__PURE__ */ React.createElement("header", { className: "hidden md:flex sticky top-0 z-30 -mx-6 px-6 h-16 items-center gap-4 bg-gray-50/95 backdrop-blur border-b border-gray-200" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 min-w-[210px]" }, tab !== "dashboard" && /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => setTab("dashboard"),
          "aria-label": "返回工作台",
          className: "w-10 h-10 inline-flex items-center justify-center rounded-xl cms-chrome-item border border-gray-200"
        },
        /* @__PURE__ */ React.createElement(Icon, { name: "chevronLeft" })
      ), /* @__PURE__ */ React.createElement("div", { className: "min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold tracking-[0.16em] text-indigo-500 uppercase" }, "Studio CMS"), /* @__PURE__ */ React.createElement("h2", { className: "text-lg font-bold text-gray-900 truncate" }, cmsPageTitle))), /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => {
            setGOpen(true);
            setGQ("");
          },
          "aria-label": "搜索学员、手机号或功能",
          className: "flex-1 max-w-2xl min-h-[44px] px-4 rounded-xl border border-gray-200 bg-white text-left text-sm text-gray-400 shadow-sm hover:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-400"
        },
        /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-2" }, /* @__PURE__ */ React.createElement(Icon, { name: "search", className: "w-4 h-4" }), "搜索学员、手机号或功能"),
        /* @__PURE__ */ React.createElement("kbd", { className: "float-right hidden lg:inline-flex rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] font-mono text-gray-500" }, "⌘K")
      ), /* @__PURE__ */ React.createElement("div", { className: "ml-auto flex items-center gap-2" }, canViewCmsNotifications && /* @__PURE__ */ React.createElement(
        CmsNotificationCenter,
        {
          notifications: cmsNotifications,
          unreadCount: cmsNotificationUnreadCount,
          open: cmsNotificationOpen,
          onToggle: () => setCmsNotificationOpen((open) => !open),
          onSelect: openCmsNotification,
          onMarkAllRead: markAllCmsNotificationsRead,
          loadError: cmsNotificationError
        }
      ), /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: load,
          disabled: busy,
          title: "刷新 CMS 数据",
          "aria-label": "刷新 CMS 数据",
          className: "hidden lg:inline-flex items-center gap-2 min-h-[44px] px-3 rounded-xl border border-gray-200 bg-white text-xs font-bold text-gray-600 hover:border-indigo-300 disabled:opacity-50"
        },
        /* @__PURE__ */ React.createElement("span", { className: `w-2 h-2 rounded-full ${conn ? "bg-emerald-500" : "bg-amber-400"}`, "aria-hidden": "true" }),
        conn ? "已同步" : "连接中"
      ), /* @__PURE__ */ React.createElement("div", { className: "relative" }, /* @__PURE__ */ React.createElement(
        "button",
        {
          type: "button",
          onClick: () => setUserMenuOpen((open) => !open),
          "aria-expanded": userMenuOpen,
          "aria-haspopup": "menu",
          className: "min-h-[44px] inline-flex items-center gap-2 rounded-xl px-2 hover:bg-white focus:outline-none focus:ring-2 focus:ring-indigo-400"
        },
        /* @__PURE__ */ React.createElement("span", { className: "w-9 h-9 rounded-full bg-indigo-100 text-indigo-700 inline-flex items-center justify-center text-sm font-bold" }, (actorRoleLabel[0] || "U").toUpperCase()),
        /* @__PURE__ */ React.createElement("span", { className: "hidden xl:block text-left max-w-[140px]" }, /* @__PURE__ */ React.createElement("span", { className: "block text-xs font-bold text-gray-800 truncate" }, actorIdentity), /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-400" }, actorRoleLabel))
      ), userMenuOpen && /* @__PURE__ */ React.createElement("div", { role: "menu", className: "absolute right-0 top-12 z-50 w-64 rounded-2xl border border-gray-200 bg-white p-2 shadow-xl anim" }, /* @__PURE__ */ React.createElement("div", { className: "px-3 py-2 border-b border-gray-100 mb-1" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-800 truncate" }, actorIdentity), /* @__PURE__ */ React.createElement("p", { className: "text-[11px] text-gray-400 mt-0.5" }, actorRoleLabel)), /* @__PURE__ */ React.createElement("button", { type: "button", role: "menuitem", onClick: () => {
        setUserMenuOpen(false);
        setSettingsSection("account");
      }, className: "w-full text-left px-3 py-2.5 rounded-xl text-sm font-bold hover:bg-indigo-50" }, "账号与安全"), /* @__PURE__ */ React.createElement("div", { className: "px-3 py-2 text-[11px] text-gray-400 font-bold" }, "界面语言"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-1 px-1 mb-1" }, /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => document.querySelector('[data-cms-language="zh"]')?.click(), className: "min-h-[44px] rounded-lg bg-gray-50 text-xs font-bold text-gray-700 hover:bg-indigo-50" }, "中文"), /* @__PURE__ */ React.createElement("button", { type: "button", onClick: () => document.querySelector('[data-cms-language="en"]')?.click(), className: "min-h-[44px] rounded-lg bg-gray-50 text-xs font-bold text-gray-700 hover:bg-indigo-50" }, "English")), TENANT_SLUG && /* @__PURE__ */ React.createElement("a", { role: "menuitem", href: `/${encodeURIComponent(TENANT_SLUG)}/studio-admin`, className: "block px-3 py-2.5 rounded-xl text-sm font-bold text-indigo-700 hover:bg-indigo-50" }, "网站与品牌 · Studio Admin"), /* @__PURE__ */ React.createElement("button", { type: "button", role: "menuitem", onClick: () => {
        setUserMenuOpen(false);
        confirm2("确认退出登录？下次进入需重新输入密码。", doLogout, { confirmText: "退出登录" });
      }, className: "w-full text-left px-3 py-2.5 rounded-xl text-sm font-bold text-red-600 hover:bg-red-50" }, "退出登录"))))),
      tab === "dashboard" && /* @__PURE__ */ React.createElement(DashboardSection, { ...{ activityMap, actorRole, actorRoleLabel, allowedTabs, analytics, arSummary, bizStats, canViewFinancialAnalytics, canWriteAttendance, canWriteCredits, canWriteStudents, copyText, db, inactiveDays, loadSchedules, pendingCount, renderMessage, scheduleLoadError, setFilterBy, setGOpen, setGQ, setRDate, setSortBy, setSrch, setTab, setTuStu, showToast, todayCheckedCount, todayEffectiveCount } }),
      tab === "courses" && /* @__PURE__ */ React.createElement(CoursesSection, { ...{ archiveCourse, busy, canManageOperations, courseEdit, courses, saveCourse, setCourseEdit, setTab } }),
      tab === "roster" && /* @__PURE__ */ React.createElement(RosterSection, { ...{ WEEKDAYS: WEEKDAYS2, addToRoster, applyGroup, availRoster, batchCheckIn, busy, canExportData, canManageOperations, canWriteAttendance, canWriteScheduling, checkIn, checkInWindow, copyRosterDaily, copyRosterReminders, copyText, courses, dayIds, db, defaultClassTime, deleteGroup, deleteSchedule, groupToSchedule, grpSel, icsBusy, loadSchedules, nextOccurrence, openIcsPreview, rDate, rOneToOne, rPick, rTime, removeFromRoster, renderMessage, renewTh, restoreCancellation, rosterDone, rosterMetaFor, rosterSection, rosterSlotFor, saveCancellation, saveGroup, saveSchedule, schedCancel, schedEdit, schedOverlap, schedPick, scheduleLoadError, scheduledForDate, schedules, setGrpSel, setRDate, setROneToOne, setRPick, setRosterSection, setRTime, setSchedCancel, setSchedEdit, setSchedPick, setTab, showToast, sortedAZ, teachableMembers, tenantDisplayName, undoCheckIn, updateRosterEntry } }),
      tab === "works" && /* @__PURE__ */ React.createElement(WorksSection, { ...{ canWritePortfolio, portfolioEntries, setEditP, setPortUpload, setSelS, setStudentProfileTab, setTab, setWorksBucket, setWorksQuery, worksBucket, worksBuckets, worksQuery, worksVisible } }),
      tab === "students" && /* @__PURE__ */ React.createElement(StudentsSection, { ...{ archiveSelected, busy, canManageOperations, canWriteAttendance, canWriteCredits, canWriteStudents, copySelectedReminders, copyText, exportStudentsCSV, filterBy, getTag, isStudentScheduledOn, pageStudents, preferenceRows, renderMessage, renewTh, scheduleStudentToday, selectedStudentIds, selectedStudents, setEditP, setFilterBy, setSelS, setSelectedStudentIds, setSortBy, setSrch, setStudentPage, setTab, setTuStu, sortBy, sortedFiltered, srch, studentPage, studentPageCount, toggleSelectPage, toggleSelectStudent } }),
      tab === "new_student" && /* @__PURE__ */ React.createElement(NewStudentSection, { ...{ busy, formPhoto, handleAddStudent, notify, preferenceProfile, setFormPhoto, setTab } }),
      tab === "pending" && /* @__PURE__ */ React.createElement(PendingSection, { ...{ advanceRegistration, approveCredits, approveStudent, approveTenant, bookings, busy, canReviewBookings, db, dupPick, followUpDates, pendingCount, pendingTab, preferenceRows, rejectStudent, reviewBooking, setApproveCredits, setDupPick, setFollowUpDates, setPendingTab, setTab, showToast } }),
      tab === "billing" && /* @__PURE__ */ React.createElement(
        BillingPanel,
        {
          api: v1Api,
          showToast,
          canIssue: canWriteCredits,
          canTakePayment: canWriteCredits,
          canExportData,
          tenantSlug: TENANT_SLUG,
          students: sortedAZ.filter((s) => !s.archived),
          studentPicker: StudentPicker,
          accountId: routeRecordId,
          onClearAccount: () => setTab("billing")
        }
      ),
      tab === "finance" && /* @__PURE__ */ React.createElement(FinancePanel, { api: v1Api, showToast }),
      tab === "topup" && /* @__PURE__ */ React.createElement(TopupSection, { ...{ archivePackage, busy, canManageOperations, canRefund, canRegisterSettlementPayment, canSyncRefund, canUseSettlementBilling, db, handleRefund, handleTopUp, pkgCredits, pkgEditId, pkgName, pkgPrice, refundSourceError, refundSources, refundSourcesBusy, resetPackageEditor, rfAdjustDocuments, rfAmountTouched, rfAmt, rfCr, rfReason, rfSourceId, savePackage, setPkgCredits, setPkgEditId, setPkgName, setPkgPrice, setRfAdjustDocuments, setRfAmountTouched, setRfAmt, setRfCr, setRfReason, setRfSourceId, setSettleMode, setSettlementPayer, setSettlementPayerError, setSettlementPayerState, setTuCr, setTuCreateInvoice, setTuFee, setTuPay, setTuPaymentReceived, setTuPkg, setTuStu, settleMode, settlementAccounts, settlementPayerError, settlementPayerIntentRef, settlementPayerState, settlementResolvedAccountRef, settlementTaxCodes, sortedAZ, tuCr, tuCreateInvoice, tuFee, tuPay, tuPaymentReceived, tuPkg, tuStu } }),
      tab === "logs" && /* @__PURE__ */ React.createElement(LogsSection, { ...{ canManageOperations, displayNote, exportLogsCSV, filteredLogs, lAct, lDateFrom, lDateTo, lPage, lSrch, lStu, logActions, logPageCount, pagedLogs, setLAct, setLDateFrom, setLDateTo, setLPage, setLSrch, setLStu, sortedAZ } }),
      tab === "stats" && /* @__PURE__ */ React.createElement(StatsSection, { ...{ analytics, bizReport, exportBizCSV, exportRevenueCSV, payBreakdown, sFrom, sPeriod, sStu, sStu2, sTo, sYear, setSFrom, setSPeriod, setSStu, setSStu2, setSTo, setSYear, sortedAZ, statsData, studentStats } }),
      selS && /* @__PURE__ */ React.createElement(StudentProfileModal, { ...{ accessCodeResult, archiveStudent, attHistory, busy, canPublishProgress, canUseSettlementBilling, canWriteAttendance, canWriteCredits, canWritePortfolio, canWriteProgress, canWriteStudents, consentEdit, copyText, db, editP, editPhoto, generateStudentAccessCode, handleDelete, handleUpdateStudent, isStudentScheduledOn, notify, openGrowthReport, portfolioDoDelete, preferenceProfile, preferenceRows, preferenceValue, profileDialogRef, revokeStudentAccessCode, save, savePublicationConsent, scheduleStudentToday, selS, setConsentEdit, setEditP, setEditPhoto, setPortEdit, setPortLB, setPortUpload, setSelS, setStudentProfileTab, setTab, setTuStu, showToast, studentProfileTab, tab, withdrawPublicationConsent, workNoun } }),
      showSettings && /* @__PURE__ */ React.createElement(
        "div",
        {
          ref: settingsDialogRef,
          className: "anim",
          style: { paddingTop: "env(safe-area-inset-top, 0px)", paddingBottom: "max(16px, env(safe-area-inset-bottom, 16px))" }
        },
        /* @__PURE__ */ React.createElement("div", { className: "w-full" }, /* @__PURE__ */ React.createElement("div", { className: "flex justify-between items-center mb-5" }, /* @__PURE__ */ React.createElement(
          "h3",
          {
            id: "settings-page-title",
            className: "md:hidden inline-flex items-center gap-1.5 font-bold text-gray-800 text-xl"
          },
          /* @__PURE__ */ React.createElement(Icon, { name: "cog", className: "w-5 h-5" }),
          "系统设置"
        )), /* @__PURE__ */ React.createElement(
          Tabs,
          {
            idBase: "settings",
            label: "系统设置分区",
            className: "mb-6",
            value: settingsSection,
            onChange: setSettingsSection,
            items: SETTINGS_SECTIONS.filter(([, , visible]) => visible !== false).map(([value, label]) => ({ value, label }))
          }
        ), /* @__PURE__ */ React.createElement("div", { className: "md:hidden mb-4 pb-4 border-b border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide mb-2" }, "界面语言"), /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-2 gap-2" }, /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: () => document.querySelector('[data-cms-language="zh"]')?.click(),
            className: "min-h-[44px] rounded-xl border border-gray-200 bg-gray-50 text-sm font-bold text-gray-700"
          },
          "中文"
        ), /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: () => document.querySelector('[data-cms-language="en"]')?.click(),
            className: "min-h-[44px] rounded-xl border border-gray-200 bg-gray-50 text-sm font-bold text-gray-700"
          },
          "English"
        ))), TENANT_SLUG && ownerRoles.includes(actorRole) && /* @__PURE__ */ React.createElement(
          "a",
          {
            href: `/${TENANT_SLUG}/studio-admin`,
            target: "_blank",
            rel: "noopener",
            className: "block bg-indigo-50 border border-indigo-200 rounded-xl px-4 py-3 text-sm font-bold text-indigo-700 active:bg-indigo-100"
          },
          "网站、Logo、配色与注册表设置 →",
          /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-normal text-indigo-400 mt-0.5" }, "打开 Studio Admin 管理公开门户、注册表字段、品牌文案和页面展示")
        ), canManageOperations && /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "team", active: settingsSection === "team" }, /* @__PURE__ */ React.createElement("div", null, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "团队与权限"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 mt-0.5" }, "Owner 管理团队与对外身份；Manager 负责日常运营与钱；Front Desk 负责报名、建档、充值与当天的排课签到；Teacher 负责课表、签到、作品与学习报告；助教是 Teacher 去掉署名权的版本，不碰钱也不碰报名。")), /* @__PURE__ */ React.createElement("div", { className: "space-y-2" }, team.map((member) => /* @__PURE__ */ React.createElement("div", { key: member.id, className: "bg-gray-50 border border-gray-200 rounded-xl px-3 py-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2" }, /* @__PURE__ */ React.createElement("div", { className: "flex-1 min-w-0" }, /* @__PURE__ */ React.createElement("p", { className: "text-sm font-bold text-gray-700 truncate" }, member.full_name), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 truncate" }, member.email, " · ", member.role, " · ", member.status)), ownerRoles.includes(actorRole) && member.role !== "owner" && /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            disabled: teamBusy,
            onClick: () => updateTeamMember(member, member.status === "active" ? "disabled" : "active"),
            className: "text-xs font-bold px-2 py-1 rounded-lg border border-gray-200 text-gray-600"
          },
          member.status === "active" ? "停用" : "启用"
        )), ownerRoles.includes(actorRole) && member.role !== "owner" && ["manager", "teacher"].includes(member.role) && /* @__PURE__ */ React.createElement("div", { className: "mt-2 pt-2 border-t border-gray-200 space-y-2" }, /* @__PURE__ */ React.createElement("label", { className: "flex items-start gap-2.5 min-h-[44px] cursor-pointer" }, /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "checkbox",
            disabled: teamBusy,
            checked: !!member.show_on_public_timetable,
            onChange: (e) => updateTeamPublicity(member, { showOnPublicTimetable: e.target.checked }),
            className: "mt-0.5 w-4 h-4 accent-indigo-600"
          }
        ), /* @__PURE__ */ React.createElement("span", { className: "flex-1" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs font-bold text-gray-600" }, "可在公开课表显示姓名"), /* @__PURE__ */ React.createElement("span", { className: "block text-[11px] text-gray-400 mt-0.5" }, "默认关闭。被排了一节课不等于同意把名字放到公网上，这一项由本人决定后再开。"))), member.show_on_public_timetable && /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 items-end" }, /* @__PURE__ */ React.createElement("label", { className: "flex-1 text-[11px] font-bold text-gray-500" }, "对外显示名（留空则用 ", member.full_name, "）", /* @__PURE__ */ React.createElement(
          "input",
          {
            defaultValue: member.public_display_name || "",
            placeholder: "如：Lucy 老师",
            disabled: teamBusy,
            onBlur: (e) => {
              const v = e.target.value.trim();
              if (v !== (member.public_display_name || "")) updateTeamPublicity(member, { publicDisplayName: v });
            },
            className: "mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"
          }
        ))))))), ownerRoles.includes(actorRole) ? /* @__PURE__ */ React.createElement("div", { className: "grid grid-cols-1 sm:grid-cols-2 gap-2 bg-indigo-50 border border-indigo-100 rounded-xl p-3" }, /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "姓名 *", /* @__PURE__ */ React.createElement(
          "input",
          {
            value: teamForm.fullName,
            onChange: (e) => setTeamForm((p) => ({ ...p, fullName: e.target.value })),
            placeholder: "如：Lucy Wang",
            className: "mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "邮箱 *", /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "email",
            value: teamForm.email,
            onChange: (e) => setTeamForm((p) => ({ ...p, email: e.target.value })),
            placeholder: "name@example.com",
            className: "mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "角色 *", /* @__PURE__ */ React.createElement(
          "select",
          {
            value: teamForm.role,
            onChange: (e) => setTeamForm((p) => ({ ...p, role: e.target.value })),
            className: "mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"
          },
          /* @__PURE__ */ React.createElement("option", { value: "manager" }, "Manager 店长"),
          /* @__PURE__ */ React.createElement("option", { value: "teacher" }, "Teacher 老师"),
          /* @__PURE__ */ React.createElement("option", { value: "front_desk" }, "Front Desk 前台"),
          /* @__PURE__ */ React.createElement("option", { value: "staff" }, "Assistant 助教")
        )), /* @__PURE__ */ React.createElement("label", { className: "text-xs font-bold text-gray-600" }, "临时密码 *", /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "password",
            value: teamForm.temporaryPassword,
            onChange: (e) => setTeamForm((p) => ({ ...p, temporaryPassword: e.target.value })),
            placeholder: "至少 8 位",
            className: "mt-1 w-full px-3 py-2 border border-gray-300 rounded-xl text-sm min-h-[44px]"
          }
        )), /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: createTeamMember,
            disabled: teamBusy,
            className: "sm:col-span-2 bg-indigo-600 text-white py-2.5 rounded-xl font-bold text-sm disabled:opacity-50"
          },
          "添加团队成员"
        )) : /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400 bg-gray-50 border border-gray-100 rounded-xl px-3 py-2" }, "当前角色可查看团队；只有 Owner 可以新增、停用或更改成员角色。")), /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "account", active: settingsSection === "account" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "修改登录密码"), /* @__PURE__ */ React.createElement("label", { className: "block text-xs font-bold text-gray-600" }, "当前密码", /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "password",
            autoComplete: "current-password",
            placeholder: "输入当前密码",
            value: pwOld,
            onChange: (e) => setPwOld(e.target.value),
            className: "mt-1 w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm min-h-[44px] focus:ring-2 focus:ring-indigo-400"
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs font-bold text-gray-600" }, "新密码 *", /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "password",
            autoComplete: "new-password",
            placeholder: "至少 8 位",
            value: pwNew1,
            onChange: (e) => setPwNew1(e.target.value),
            className: "mt-1 w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm min-h-[44px] focus:ring-2 focus:ring-indigo-400"
          }
        )), /* @__PURE__ */ React.createElement("label", { className: "block text-xs font-bold text-gray-600" }, "确认新密码 *", /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "password",
            autoComplete: "new-password",
            placeholder: "再次输入新密码",
            value: pwNew2,
            onChange: (e) => setPwNew2(e.target.value),
            className: "mt-1 w-full p-2.5 border border-gray-300 rounded-xl outline-none text-sm min-h-[44px] focus:ring-2 focus:ring-indigo-400"
          }
        )), pwMsg && /* @__PURE__ */ React.createElement("p", { className: `text-xs font-medium ${pwMsg.tone === "ok" ? "text-green-600" : "text-red-500"}` }, pwMsg.text), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: changeWebPw,
            disabled: pwBusy,
            className: "w-full bg-indigo-600 active:bg-indigo-700 disabled:opacity-50 text-white py-2.5 rounded-xl font-bold text-sm"
          },
          pwBusy ? "更新中..." : "更新密码"
        )), canManageOperations && /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "operational", active: settingsSection === "operational" }, TENANT_SLUG && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "课程安排默认时间"), /* @__PURE__ */ React.createElement("p", { className: "text-xs text-gray-400" }, "用于新排课、班组模板和新建固定班次；不会改动已保存的课程。"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2 items-end" }, /* @__PURE__ */ React.createElement("label", { className: "flex-1 text-xs font-bold text-gray-500" }, "默认上课时间", /* @__PURE__ */ React.createElement(
          "input",
          {
            type: "time",
            value: defaultClassTimeDraft,
            onChange: (e) => setDefaultClassTimeDraft(e.target.value),
            className: "mt-1 w-full px-3 py-2.5 border border-gray-300 rounded-xl bg-white text-sm font-bold min-h-[46px] outline-none focus:ring-2 focus:ring-indigo-500"
          }
        )), /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: saveDefaultClassTime,
            disabled: operationalSettingsBusy || defaultClassTimeDraft === defaultClassTime,
            className: "px-4 py-2.5 rounded-xl bg-indigo-600 text-white text-sm font-bold min-h-[46px] disabled:opacity-40"
          },
          operationalSettingsBusy ? "保存中…" : "保存"
        ))), /* @__PURE__ */ React.createElement("div", { className: "mt-4 pt-4 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "未到访预警天数"), /* @__PURE__ */ React.createElement("div", { className: "flex gap-2" }, [60, 90, 120, 180].map((d) => /* @__PURE__ */ React.createElement(
          "button",
          {
            key: d,
            onClick: () => saveInactiveDays(d),
            className: `flex-1 py-2 rounded-xl text-xs font-bold border ${inactiveDays === d ? "bg-indigo-600 text-white border-indigo-600" : "bg-gray-50 text-gray-600 border-gray-200 active:bg-gray-100"}`
          },
          d,
          "天"
        ))))), canManageOperations && (() => {
          const cutoffStr = (() => {
            const d = /* @__PURE__ */ new Date();
            d.setDate(d.getDate() - 90);
            return d.toISOString().slice(0, 10);
          })();
          const oldKeys = Object.keys(db.rosters || {}).filter((d) => d < cutoffStr);
          const cleanRosters = () => {
            if (!oldKeys.length) {
              showToast("没有需要清理的旧排课");
              return;
            }
            confirm2(`清理 90 天前的排课记录（${oldKeys.length} 条）？
此操作不影响任何统计数据。`, async () => {
              const nd = { ...db, rosters: { ...db.rosters } };
              oldKeys.forEach((k) => delete nd.rosters[k]);
              const ok = await save(nd);
              if (!ok) return;
              showToast(`已清理 ${oldKeys.length} 条旧排课`);
            }, { confirmText: "清理" });
          };
          return /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "maintenance", active: settingsSection === "maintenance" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "排课数据清理"), /* @__PURE__ */ React.createElement("div", { className: "bg-gray-50 border border-gray-200 rounded-xl px-3 py-2 flex items-center gap-2" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-500 flex-1" }, "90天前旧排课"), /* @__PURE__ */ React.createElement("span", { className: `text-xs font-bold ${oldKeys.length > 0 ? "text-amber-600" : "text-green-600"}` }, oldKeys.length, " 条")), /* @__PURE__ */ React.createElement(
            "button",
            {
              onClick: cleanRosters,
              disabled: oldKeys.length === 0,
              className: "w-full bg-amber-50 active:bg-amber-100 disabled:opacity-40 text-amber-700 border border-amber-200 py-2.5 rounded-xl font-bold text-sm"
            },
            /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "broom", className: "w-4 h-4" }), "清理旧排课")
          ), !TENANT_SLUG && /* @__PURE__ */ React.createElement(
            MaintSection,
            {
              renewTh,
              saveRenewTh,
              onRestored: () => {
                closeSettings();
                load();
              },
              confirm: confirm2,
              notify
            }
          ));
        })(), canManageOperations && /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "billing-identity", active: settingsSection === "billing-identity" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "开票信息"), /* @__PURE__ */ React.createElement(
          BillingIdentityPanel,
          {
            api: v1Api,
            showToast,
            canManage: ownerRoles.includes(actorRole)
          }
        )), ownerRoles.includes(actorRole) && /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "integrations", active: settingsSection === "integrations" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "集成"), /* @__PURE__ */ React.createElement(IntegrationsPanel, { api: v1Api, showToast, canManage: ownerRoles.includes(actorRole) })), /* @__PURE__ */ React.createElement(TabPanel, { idBase: "settings", name: "workspace", active: settingsSection === "workspace" }, /* @__PURE__ */ React.createElement("p", { className: "text-xs font-bold text-gray-500 uppercase tracking-wide" }, "学员注册页面"), /* @__PURE__ */ React.createElement("div", { className: "flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-xl px-3 py-2" }, /* @__PURE__ */ React.createElement("span", { className: "text-xs text-gray-500 flex-1 font-mono truncate" }, window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`), /* @__PURE__ */ React.createElement(
          "button",
          {
            type: "button",
            onClick: () => copyText(window.STUDIOSAAS_REGISTER_URL || `${window.location.origin}/register`, "链接已复制"),
            className: "text-xs text-indigo-600 font-bold active:text-indigo-800 flex-shrink-0"
          },
          "复制"
        ))), /* @__PURE__ */ React.createElement("div", { className: "mt-3 pt-3 border-t border-gray-100 space-y-2" }, /* @__PURE__ */ React.createElement("button", { onClick: requestLogout, className: "w-full bg-gray-100 active:bg-gray-200 text-gray-700 py-3 rounded-xl font-bold text-sm" }, "退出登录"), /* @__PURE__ */ React.createElement("div", { className: "md:hidden space-y-2 pt-2 border-t border-gray-100" }, /* @__PURE__ */ React.createElement("p", { className: "text-[11px] font-bold text-gray-400 uppercase tracking-wide pb-0.5" }, "快捷操作"), TENANT_SLUG && /* @__PURE__ */ React.createElement(React.Fragment, null, /* @__PURE__ */ React.createElement(
          "a",
          {
            href: `/${encodeURIComponent(TENANT_SLUG)}/studio-admin`,
            className: "flex items-center justify-center w-full bg-indigo-600 active:bg-indigo-700 py-3 rounded-xl font-bold text-sm min-h-[44px]"
          },
          "网站与品牌 · Studio Admin"
        ), /* @__PURE__ */ React.createElement(
          "a",
          {
            href: `/${encodeURIComponent(TENANT_SLUG)}`,
            target: "_blank",
            rel: "noopener",
            className: "flex items-center justify-center w-full bg-gray-50 active:bg-gray-100 text-gray-700 border border-gray-200 py-3 rounded-xl font-bold text-sm min-h-[44px]"
          },
          "查看公开网站"
        )), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => {
              load();
              closeSettings();
            },
            disabled: busy,
            className: "w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm"
          },
          /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "refresh", className: "w-4 h-4" }), "刷新数据")
        ), canManageOperations && !TENANT_SLUG && /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => {
              exportDB();
              closeSettings();
            },
            className: "w-full bg-indigo-50 active:bg-indigo-100 text-indigo-700 border border-indigo-200 py-3 rounded-xl font-bold text-sm"
          },
          /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "download", className: "w-4 h-4" }), "备份导出")
        ), /* @__PURE__ */ React.createElement(
          "button",
          {
            onClick: () => {
              closeSettings();
              confirm2("确认退出登录？下次进入需重新输入密码。", doLogout, { confirmText: "退出登录" });
            },
            className: "w-full bg-red-50 active:bg-red-100 text-red-600 border border-red-200 py-3 rounded-xl font-bold text-sm"
          },
          /* @__PURE__ */ React.createElement("span", { className: "inline-flex items-center gap-1.5" }, /* @__PURE__ */ React.createElement(Icon, { name: "logout", className: "w-4 h-4" }), "退出登录")
        ))))
      ),
      /* @__PURE__ */ React.createElement("footer", { className: "mt-8 pb-6 text-center text-[10px] tracking-wide text-gray-400" }, "© 2026 ", tenantDisplayName, " · Powered by Paradise Production")
    ), moreOpen && /* @__PURE__ */ React.createElement("div", { className: "md:hidden fixed inset-0 z-[45]", onClick: () => setMoreOpen(false) }), moreOpen && /* @__PURE__ */ React.createElement(
      "div",
      {
        className: "md:hidden fixed bottom-[calc(56px+env(safe-area-inset-bottom,0px))] left-0 right-0 z-[46] cms-chrome border-t px-4 py-3 grid grid-cols-4 gap-2 anim",
        onClick: (e) => e.stopPropagation()
      },
      [{ k: "courses", i: "", s: "课程" }, { k: "works", i: "", s: "作品" }, { k: "logs", i: "", s: "日志" }, { k: "stats", i: "", s: "统计" }, { k: "pending", i: "", s: "待处理", badge: pendingCount }, { k: "new_student", i: /* @__PURE__ */ React.createElement(Icon, { name: "plus", className: "w-[22px] h-[22px]" }), s: "新建" }, { k: "settings", i: "", s: "设置" }].filter((item) => allowedTabs.includes(item.k)).map(({ k, i, s, badge }) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: k,
          onClick: () => {
            setTab(k);
            setMoreOpen(false);
          },
          className: `flex flex-col items-center justify-center py-2.5 gap-0.5 rounded-xl relative cms-chrome-item ${["courses", "works", "logs", "stats", "pending", "new_student", "settings"].includes(tab) && tab === k ? "is-active" : ""}`
        },
        /* @__PURE__ */ React.createElement("span", { className: "text-[22px] leading-none" }, i),
        /* @__PURE__ */ React.createElement("span", { className: "text-[10px] font-bold leading-none tracking-tight" }, s),
        badge > 0 && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1 right-2 bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4" }, badge)
      ))
    ), /* @__PURE__ */ React.createElement(
      "nav",
      {
        className: "md:hidden fixed bottom-0 left-0 right-0 z-40 cms-chrome border-t flex",
        style: { paddingBottom: "env(safe-area-inset-bottom,0px)", transform: "translateZ(0)", willChange: "transform" }
      },
      [{ k: "dashboard", i: "", s: "工作台" }, { k: "roster", i: "", s: "课表" }, { k: "students", i: "", s: "档案" }, { k: "topup", i: "", s: "充值" }].filter((item) => allowedTabs.includes(item.k)).map(({ k, i, s }) => /* @__PURE__ */ React.createElement(
        "button",
        {
          key: k,
          onClick: () => {
            setTab(k);
            setMoreOpen(false);
          },
          "aria-current": tab === k ? "page" : void 0,
          className: `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative cms-chrome-item cms-chrome-tab ${tab === k ? "is-active" : ""}`
        },
        /* @__PURE__ */ React.createElement("span", { className: "text-[22px] leading-none" }, i),
        /* @__PURE__ */ React.createElement("span", { className: "text-[10px] font-bold leading-none tracking-tight" }, s),
        k === "dashboard" && analytics.lowBalance.length > 0 && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1.5 right-[18%] bg-red-500 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4" }, analytics.lowBalance.length)
      )),
      /* @__PURE__ */ React.createElement(
        "button",
        {
          onClick: () => setMoreOpen((o) => !o),
          className: `flex-1 flex flex-col items-center justify-center py-2 gap-0.5 min-h-[52px] relative cms-chrome-item cms-chrome-tab ${moreOpen || ["courses", "works", "logs", "stats", "pending", "new_student", "settings"].includes(tab) ? "is-active" : ""}`
        },
        /* @__PURE__ */ React.createElement("span", { className: "leading-none inline-flex items-center justify-center h-[22px]" }, moreOpen ? /* @__PURE__ */ React.createElement(Icon, { name: "close", className: "w-[22px] h-[22px]" }) : /* @__PURE__ */ React.createElement(Icon, { name: "ellipsis", className: "w-[22px] h-[22px]" })),
        /* @__PURE__ */ React.createElement("span", { className: "text-[10px] font-bold leading-none tracking-tight" }, "更多"),
        pendingCount > 0 && !moreOpen && /* @__PURE__ */ React.createElement("span", { className: "absolute top-1.5 right-[18%] bg-amber-400 text-white text-[9px] font-bold px-1 rounded-full min-w-[15px] text-center leading-4" }, pendingCount)
      )
    ));
  }
  ReactDOM.createRoot(document.getElementById("root")).render(/* @__PURE__ */ React.createElement(App, null));
})();
