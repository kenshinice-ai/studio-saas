"""Panels may only render components they can actually see.

`build_cms.sh --bundle` is what lets the CMS be more than one file, and it also
draws a line that did not exist before: each file is its own module scope. An
identifier defined in ``cms-app.jsx`` — ``Icon``, ``Kpi``, ``EmptyState`` — is
simply not there inside ``panels/*.jsx`` unless it is imported or passed.

The failure is not a missing icon. A JSX tag that resolves to ``undefined``
throws during render, React unmounts the tree, and the entire console goes
white. That happened once, to ``<Icon>`` in the student progress-report panel,
and the compiler said nothing: esbuild does not resolve JSX component names, and
every existing test greps the source for substrings that were all still present.

So the check has to look at what the JSX actually references and subtract what
the file can reach. Deriving both sides is the point — a hardcoded list of
banned names would go stale the first time somebody adds a component to
``cms-app.jsx``, which is exactly the class of guard that has already failed
this project four times.
"""

from __future__ import annotations

import re

from _cms_sources import CMS_SRC_DIR, cms_source_text

#: Real globals: the page loads React and ReactDOM from /vendor before the
#: bundle, and index.html's only other contract is `<div id="root">`.
BROWSER_GLOBALS = {"React", "ReactDOM", "Fragment"}

#: `<Foo>` and `<Foo.Bar>` — the leading capital is what makes JSX treat a tag
#: as a component reference rather than an HTML element.
JSX_TAG = re.compile(r"<([A-Z][A-Za-z0-9_]*)")
IMPORTED = re.compile(r"import\s*\{([^}]*)\}\s*from|import\s+([A-Za-z0-9_]+)\s+from")
DECLARED = re.compile(r"(?:function|const|let|class)\s+([A-Z][A-Za-z0-9_]*)")


#: Comments in these files are prose about the code, and the prose talks about
#: components by name — the very comment explaining why `<Icon>` is unreachable
#: contains `<Icon>`. Scanning them would make the guard fail on its own
#: documentation, so strip them first.
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _code_only(text: str) -> str:
    return COMMENT.sub("", text)


def _reachable_names(text: str) -> set[str]:
    names = set(BROWSER_GLOBALS)
    for braced, default in IMPORTED.findall(text):
        for part in braced.split(","):
            name = part.split(" as ")[-1].strip()
            if name:
                names.add(name)
        if default:
            names.add(default)
    names.update(DECLARED.findall(text))
    # Destructured hooks and helpers: `const { useState } = React`.
    for block in re.findall(r"const\s*\{([^}]*)\}\s*=", text):
        names.update(part.split(":")[-1].strip() for part in block.split(",") if part.strip())
    return names


def test_panels_only_render_components_they_can_reach():
    panels = sorted((CMS_SRC_DIR / "panels").glob("*.jsx"))
    assert panels, "no panels found — did the source move?"

    unreachable: dict[str, set[str]] = {}
    for path in panels:
        text = _code_only(path.read_text(encoding="utf-8"))
        missing = set(JSX_TAG.findall(text)) - _reachable_names(text)
        if missing:
            unreachable[path.name] = missing

    assert not unreachable, (
        "These panels render components that do not exist in their module scope. "
        "esbuild will compile this and the browser will white-screen on first "
        "render. Import them, pass them as props, or write the markup directly: "
        f"{ {k: sorted(v) for k, v in unreachable.items()} }"
    )


def test_panels_stringify_request_bodies():
    """`v1Api` spreads its options into ``fetch`` — the body must be a string.

    ``fetch`` does not serialise a plain object; it stringifies it to
    ``"[object Object]"`` and sends that with a JSON content type. The server
    answers 400 "Request body must be a JSON object", which reads like a schema
    problem and is not one. Nothing in the request path can catch this: the JSX
    compiles, the call is made, and only the response is wrong.

    A helper that serialised for you would be the better fix, but changing
    ``v1Api``'s contract now would silently double-encode every existing caller
    that already stringifies. Policing the panels is the cheaper half.
    """

    offenders = []
    for path in sorted((CMS_SRC_DIR / "panels").glob("*.jsx")):
        text = _code_only(path.read_text(encoding="utf-8"))
        for line_no, line in enumerate(text.splitlines(), start=1):
            if re.search(r"\bbody:\s*[{\[]", line):
                offenders.append(f"{path.name}:{line_no}")

    assert not offenders, (
        "These calls pass an object as `body`; fetch will send the literal "
        f"string '[object Object]'. Wrap them in JSON.stringify: {offenders}"
    )


def test_every_pay_basis_has_a_human_name():
    """`per_hour` reached a teacher's pay sheet, printed as `per_hour`.

    The five bases are a database enum. A panel that renders the raw value is
    not broken in any way a test notices — it renders, it is even correct — it
    is simply English machine vocabulary on a document a person is meant to
    read and query. Missing one basis only shows up at the studio that happens
    to pay that way, which is the worst kind of gap to leave to chance.
    """

    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[1]
    service = (backend_root / "studiosaas/services/teaching_pay.py").read_text(encoding="utf-8")
    bases = set(re.search(r"RATE_BASES = \(([^)]*)\)", service).group(1).replace('"', "").split(", "))
    bases = {basis.strip() for basis in bases if basis.strip()}

    panel = (CMS_SRC_DIR / "panels" / "finance.jsx").read_text(encoding="utf-8")
    labelled = set(re.findall(r"^\s{2}(\w+):\s*'", panel, re.M))

    missing = sorted(bases - labelled)
    assert not missing, (
        f"These pay bases would print as their raw enum value on a pay sheet: {missing}"
    )


def test_no_panel_hardcodes_the_golden_grid_without_a_breakpoint():
    """φ splits a wide screen. On a phone it splits 375px into 143px.

    The panels each wrote `gridTemplateColumns: var(--ui-golden-columns-reverse)`
    as an inline style, which applies at every width — so the master/detail
    layout stayed two columns on a phone, where the secondary column is too
    narrow for a date input. It rendered, so nothing failed; it was simply
    unusable, and only visible by looking at the page at that width.

    `.ui-golden-split` in ui-tokens.css stacks by default and applies φ from
    768px up. One definition, so a new panel cannot forget the breakpoint.
    """

    offenders = []
    for path in sorted((CMS_SRC_DIR / "panels").glob("*.jsx")):
        text = _code_only(path.read_text(encoding="utf-8"))
        if "gridTemplateColumns: 'var(--ui-golden-columns" in text:
            offenders.append(path.name)

    assert not offenders, (
        "These panels apply the golden ratio at every width, including phone "
        f"widths where the secondary column collapses: {offenders}. "
        "Use className=\"ui-golden-split\"."
    )


def test_billing_detail_payment_targets_invoice_refreshes_detail_and_renders_real_amounts():
    """The detail drawer must pay the invoice being viewed and show its new history."""

    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    start = panel.index("  const recordPayment = async () =>")
    end = panel.index("\n  if (loading)", start)
    payment = _code_only(panel[start:end])

    assert "billingAccountId: detail.invoice.billing_account_id" in payment
    assert "invoiceId: detail.invoice.id" in payment
    assert "autoAllocate: true" in payment
    assert "await load();" in payment
    assert "const refreshed = await api(`/billing/invoices/${selectedId}`);" in payment
    assert "setDetail(refreshed);" in payment

    events_start = panel.index("                  const d = event.detail || {};")
    events_end = panel.index("                })}", events_start)
    events = _code_only(panel[events_start:events_end])
    assert "d.amount_cents" in events
    assert "amount > 0" in events
    assert "d.balance_cents === undefined ? null" in events


def test_billing_empty_state_describes_manual_invoice_creation_only():
    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")

    assert "还没有发票。点击“新建发票”创建草稿，复核后再开具。" in panel
    assert "周期账单会自动生成草稿" not in panel
    assert "周期账单一次生成几十张草稿" not in panel


def test_manual_invoice_lines_do_not_claim_credit_settlement_and_use_explicit_classification():
    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")

    assert "isCredits" not in panel
    assert "这一行是课时充值" not in panel
    assert "与「充值与退款」对应" not in panel
    assert "value={line.sourceKind}" in panel
    assert 'value="package"' in panel
    assert "sourceKind: line.sourceKind || 'manual'" in panel
    assert "studentId: line.studentId || null" in panel
    assert "studentPicker" in panel
    assert "只表达收入报告归属，不改变课时余额" in panel
    assert "同时创建发票" not in panel
    assert "同步处理原发票与付款" not in panel


def test_billing_account_picker_has_student_and_custom_payer_paths():
    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")

    assert "function BillingAccountPicker" in panel
    assert "已有学员" in panel
    assert "其他个人或机构" in panel
    assert "studentId=${encodeURIComponent(studentId)}" in panel
    assert "possibleDuplicates" in panel  # duplicates are shown for explicit operator review
    assert "studentIds" in panel
    assert "0..N" in panel
    assert "billing-account-help" in panel
    assert "grid-cols-1 md:grid-cols-3" in panel
    assert "保留发票行" in panel or "Keep payer fields" in panel
    assert "不改变课时余额" in panel


def test_billing_account_picker_requires_explicit_create_and_uses_accessible_payer_chips():
    """A missing payer must remain a reviewable choice, never an implicit POST.

    The same picker is used by invoice drafts and top-up billing.  A 0-payer
    suggestion therefore needs an explicit create/use action, while an N-payer
    result must stay unselected until the operator chooses one.  Custom linked
    subjects are chips/buttons rather than a native multi-select so the flow is
    usable at 375px and keyboard accessible.
    """

    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")

    assert "createConfirmed" in panel
    assert "创建并使用此付款方" in panel
    assert "Create and use this payer" in panel
    assert "0 个付款方" in panel or "没有付款方" in panel
    assert "付款方快照" in panel or "payer snapshot" in panel
    assert "payer-chip" in panel
    assert "select multiple" not in panel
    assert "type=\"button\"" in panel


def test_billing_panel_exposes_bounded_summary_and_line_exports():
    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    app = cms_source_text()

    assert "发票汇总 CSV" in panel
    assert "行项目 CSV" in panel
    assert "includeDrafts: '0'" in panel
    assert "当前筛选范围" in panel
    assert "canExportData" in panel and "tenantSlug" in panel
    assert "canExportData={canExportData}" in app
    assert "tenantSlug={TENANT_SLUG}" in app


def test_billing_detail_keeps_print_save_as_pdf_fallback_until_server_renderer_exists():
    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    shell = (CMS_SRC_DIR.parent / "index.html").read_text(encoding="utf-8")
    assert "const printInvoice = () =>" in panel
    assert "window.print()" in panel
    assert "invoice-printable" in panel
    assert "invoice-print-mode" in shell
    assert "Print / Save as PDF" not in panel  # source remains Chinese for CMS i18n


def test_invoice_print_css_does_not_hide_the_snapshot_document_with_root_id_specificity():
    """The printable customer document must survive the CMS print isolation rule."""

    shell = (CMS_SRC_DIR.parent / "index.html").read_text(encoding="utf-8")
    assert "body.invoice-print-mode #root > * { visibility:hidden !important; }" in shell
    assert "body.invoice-print-mode #root * { visibility:hidden !important; }" not in shell
    # v10.8.0: the reveal is scoped to the chosen print target. An unscoped
    # reveal printed every mounted customer document at once (invoice + credit
    # note + statement stacked on the same paper).
    assert "body.invoice-print-mode .invoice-print-target .invoice-customer-document * { visibility:visible !important; }" in shell
    assert "body.invoice-print-mode .invoice-customer-document * { visibility:visible !important; }" not in shell


def test_invoice_print_targets_exactly_one_customer_document():
    """Every print entry point must name the container it prints."""

    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    assert "printCustomerDocument(detail.document, '.invoice-printable')" in panel
    assert "printCustomerDocument(creditNoteDetail.document, '.credit-note-document')" in panel
    assert "'.statement-document', 'Statement'" in panel
    assert "classList.add('invoice-print-target')" in panel
    assert "classList.remove('invoice-print-target')" in panel


def test_invoice_print_temporarily_names_the_customer_document_for_pdf_headers():
    """Browser-generated PDF headers must identify the selected invoice, not CMS."""

    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    assert "const previousTitle = document.title" in panel
    assert "customerDocument.supplier?.gstRegistered ? 'Tax Invoice' : 'Invoice'" in panel
    assert "Tax Invoice" in panel and "Credit Note" in panel
    assert "document.title = `${title} · ${number}`" in panel
    assert "document.title = previousTitle" in panel


def test_invoice_print_document_is_snapshot_dto_only():
    """The customer-facing print root must not read live payer fields."""

    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    assert "function InvoicePrintableDocument" in panel
    start = panel.index("function InvoicePrintableDocument")
    end = panel.index("export function BillingPanel", start)
    printable = panel[start:end]
    assert "document.document" in printable
    assert "document.supplier" in printable
    assert "document.recipient" in printable
    assert "document.lines" in printable
    assert "document.totals" in printable
    assert "detail.invoice" not in printable
    assert "invoice-customer-document" in printable
    assert "Tax Invoice" in printable
    assert "打印 / 存为 PDF" in panel


def test_topup_settlement_ui_has_layered_invoice_controls_and_stable_retry_contract():
    app = cms_source_text()
    picker = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")

    assert "BillingAccountPicker" in app
    assert "同时创建发票" in app
    assert "款项已经收到，同时登记付款" in app
    assert "createInvoice: true" in app
    assert "paymentReceived" in app
    assert "nextSettlementRequestId" in app
    assert "requestId" in app
    assert "查看发票" in app
    assert "/credit-settlements" in app
    assert "/credit-transactions" in app
    assert "hideStudentSelector" in picker
    assert "amountCents" in app
    assert "税码" in app


def test_refund_ui_requires_a_purchase_source_and_gates_document_adjustment():
    app = cms_source_text()
    assert "先选择原充值" in app
    assert "sourceCreditTransactionId" in app
    assert "/credit-refunds" in app
    assert "同步处理原发票与付款" in app
    assert "source.syncAvailable" in app
    assert "canSyncRefund" in app
    assert "不会改变发票或付款记录" in app
    assert "nextRefundRequestId" in app


def test_credit_money_flows_have_no_legacy_ui_fallback():
    """Every top-up/refund checkbox branch carries its source and request key."""

    app = cms_source_text()
    topup = app[app.index("const handleTopUp = async"):app.index("const nextRefundRequestId")]
    assert "/credit-settlements" in topup
    assert "billing: {createInvoice: false}" in topup
    assert "/credit-transactions" not in topup

    refund = app[app.index("const handleRefund = async"):app.index("const handleAddStudent")]
    assert refund.count("/credit-refunds") >= 2
    assert "billing: {adjustDocuments: false}" in refund
    assert "sourceCreditTransactionId: rfSourceId" in refund
    assert "requestId," in refund
    assert "/credit-transactions" not in refund
