"""Contract coverage for the tenant-scoped invoice CSV exports."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_SOURCE = "\n".join(p.read_text(encoding="utf-8") for p in sorted((PROJECT_ROOT / "backend/studiosaas/api_v1").glob("*.py")))


def test_invoice_export_contract_is_bounded_snapshot_based_and_audited():
    start = API_SOURCE.index('@api_v1.route("/billing/invoices/export.csv"')
    end = API_SOURCE.index('@api_v1.route("/billing/invoices",', start)
    export = API_SOURCE[start:end]
    assert '@permission_required("billing:read")' in export
    assert 'require_permission(getattr(g, "actor", None), "data:export")' in export
    assert "_INVOICE_EXPORT_MAX_ROWS" in export
    assert "_INVOICE_EXPORT_MAX_DAYS" in API_SOURCE
    assert "recipient_for_invoice" in export
    assert "csv_safe_cell" in export
    assert "_export_audit" in export
    assert "_invoice_export_identity_select" in export


def test_invoice_detail_exposes_credit_note_linkage_for_csv_reconciliation():
    start = API_SOURCE.index('@api_v1.route("/billing/invoices/<invoice_id>", methods=["GET"])')
    end = API_SOURCE.index('@api_v1.route("/billing/invoices/<invoice_id>/lines"', start)
    detail = API_SOURCE[start:end]
    assert "credit_notes" in detail
    assert '"creditNotes": credit_notes' in detail
    assert "SELECT i.*" in detail
