"""P1-02 accounting readability and export contracts."""

from pathlib import Path

from _cms_sources import CMS_SRC_DIR


ROOT = Path(__file__).resolve().parents[1]
API = (ROOT / "studiosaas/api_v1.py").read_text(encoding="utf-8")
PANEL = (CMS_SRC_DIR / "panels/billing.jsx").read_text(encoding="utf-8")


def test_invoice_list_and_ui_derive_credit_states_and_net_received():
    start = API.index('@api_v1.route("/billing/invoices", methods=["GET", "POST"])')
    block = API[start:API.index('@api_v1.route("/billing/invoices/<invoice_id>"', start)]
    assert "amount_credited_cents" in block
    assert "net_received_cents" in block
    assert "credited" in block

    assert "invoiceFinancialState" in PANEL
    assert "部分贷记" in PANEL
    assert "已全额贷记" in PANEL
    assert "netReceivedCents" in PANEL
    assert "已收到（扣除退款）" in PANEL or "净收款" in PANEL


def test_accounting_export_distinguishes_invoices_credit_notes_payments_and_refunds():
    start = API.index('@api_v1.route("/billing/invoices/export.csv"')
    export = API[start:API.index('@api_v1.route("/billing/invoice-drafts"', start)]
    assert "ledger" in export
    for table in ("credit_notes", "payments", "refunds"):
        assert table in export
    assert "Record Type" in export
    assert "csv_safe_cell" in export
    assert "_export_audit" in export


def test_credit_note_detail_and_payer_edit_routes_are_snapshot_safe():
    assert '@api_v1.route("/billing/credit-notes/<credit_note_id>"' in API
    assert "build_credit_note_document" in API
    assert '@api_v1.route("/billing/accounts/<account_id>", methods=["GET", "PATCH"])' in API
    assert "recipient_snapshot" in API
    assert "payer-edit" in PANEL or "编辑付款方" in PANEL
    assert "issued 的发票仍读取快照" in PANEL or "已开具发票不会改变" in PANEL
