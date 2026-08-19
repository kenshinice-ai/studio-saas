"""Pure contract tests for the InvoiceDocument DTO."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.services.invoice_documents import (  # noqa: E402
    build_credit_note_document,
    build_invoice_document,
    csv_safe_cell,
    decimal_quantity,
)


def _invoice(status: str = "issued"):
    return {
        "id": "invoice-1",
        "status": status,
        "number": "INV-0001" if status != "draft" else None,
        "currency": "AUD",
        "issue_date": date(2026, 8, 16) if status != "draft" else None,
        "due_date": date(2026, 8, 30) if status != "draft" else None,
        "subtotal_cents": 1001,
        "tax_cents": 100,
        "total_cents": 1101,
        "amount_paid_cents": 501 if status == "part_paid" else 1101 if status == "paid" else 0,
        "amount_credited_cents": 0,
        "balance_cents": 600 if status == "part_paid" else 0 if status == "paid" else 1101,
        "note": "这是很长的备注：" + "家长会计需要保留的文字。" * 4,
        "purchase_order_ref": "PO-中文-2026-08",
        "created_at": datetime(2026, 8, 15, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 8, 16, tzinfo=timezone.utc),
        "voided_at": datetime(2026, 8, 17, tzinfo=timezone.utc) if status == "void" else None,
        "void_reason": "重复开具" if status == "void" else "",
        "supplier_snapshot": {
            "schemaVersion": 1,
            "configured": True,
            "legalName": "New Legal Pty Ltd",
            "tradingName": "新法律工作室",
            "abn": "11 222 333 444",
            "gstRegistered": True,
            "address": {"line1": "1 Long Street", "line2": "Suite 99", "suburb": "Melbourne", "state": "VIC", "postcode": "3000", "country": "Australia"},
            "contactEmail": "billing@example.test",
            "contactPhone": "+61 3 9000 0000",
            "website": "https://example.test",
            "bank": {"accountName": "New Legal Pty Ltd", "bsb": "000000", "accountNo": "123456"},
            "paymentNote": "请在到期日前付款。",
        } if status != "draft" else {},
        "recipient_snapshot": {
            "schemaVersion": 1,
            "displayName": "很长的机构名称（墨尔本校区）",
            "kind": "organisation",
            "contactName": "财务联系人",
            "companyName": "很长的机构名称（墨尔本校区）",
            "abn": "55 666 777 888",
            "email": "accounts@organisation.test",
            "mobile": "+61 400 000 000",
            "billingAddress": "第一行很长的地址\n第二行地址\nMelbourne VIC 3000",
            "paymentTermsDays": 14,
            "purchaseOrderRef": "PO-中文-2026-08",
            "language": "zh",
        } if status != "draft" else {},
        "account_name": "Live payer should not replace the snapshot",
        "account_kind": "family",
        "account_contact_name": "Live contact",
        "account_email": "live@example.test",
        "account_payment_terms_days": 7,
        "account_language": "en",
        "supplier_configured": True,
        "supplier_legal_name": "Live Legal Pty Ltd",
    }


def _lines():
    return [{
        "id": "line-1",
        "description": "第三学期学费（含 GST）",
        "quantity": Decimal("3.33"),
        "unit_price_cents": 301,
        "tax_rate_bp": 1000,
        "net_cents": 1001,
        "tax_cents": 100,
        "total_cents": 1101,
        "source_kind": "tuition",
        "source_id": "source-1",
        "student_id": "student-1",
    }]


def test_quantity_is_decimal_string_and_never_float():
    assert decimal_quantity(Decimal("3.30")) == "3.30"
    assert decimal_quantity("0.10") == "0.10"
    assert "e" not in decimal_quantity("1000.00").lower()


def test_csv_safe_cell_neutralises_spreadsheet_formulas_but_preserves_numbers():
    assert csv_safe_cell("=HYPERLINK(\"https://evil.test\")") == "'=HYPERLINK(\"https://evil.test\")"
    assert csv_safe_cell("+61 400 000 000") == "'+61 400 000 000"
    assert csv_safe_cell("normal text") == "normal text"
    assert csv_safe_cell(1001) == 1001


def test_issued_document_uses_snapshots_and_exposes_all_money_as_cents():
    document = build_invoice_document(
        _invoice("part_paid"),
        _lines(),
        [{"id": "payment-1", "method": "bank_transfer", "provider": None,
          "status": "succeeded", "amount_cents": 501, "allocated_cents": 501,
          "refunded_cents": 0, "received_at": datetime(2026, 8, 16, tzinfo=timezone.utc),
          "note": ""}],
        language="zh",
    )
    assert document["recipient"]["isSnapshot"] is True
    assert document["recipient"]["displayName"].startswith("很长的机构")
    assert document["supplier"]["legalName"] == "New Legal Pty Ltd"
    assert document["document"]["statusLabel"] == "部分付款"
    assert document["lines"][0]["quantity"] == "3.33"
    assert document["lines"][0]["netCents"] == 1001
    assert document["totals"] == {"subtotalCents": 1001, "taxCents": 100, "totalCents": 1101}
    assert document["paymentSummary"]["amountPaidCents"] == 501
    assert document["paymentSummary"]["balanceCents"] == 600


def test_draft_document_uses_live_preview_and_supports_english_labels():
    draft = _invoice("draft")
    draft.update({
        "account_name": "Live Family",
        "account_kind": "family",
        "account_contact_name": "Live Parent",
        "account_email": "live@example.test",
        "account_payment_terms_days": 21,
        "account_language": "en",
        "supplier_legal_name": "Live Legal Pty Ltd",
        "supplier_trading_name": "Live Studio",
        "supplier_abn": "11 222 333 444",
        "supplier_gst_registered": False,
        "supplier_country": "Australia",
    })
    document = build_invoice_document(draft, _lines(), language="en")
    assert document["recipient"]["isSnapshot"] is False
    assert document["recipient"]["displayName"] == "Live Family"
    assert document["supplier"]["legalName"] == "Live Legal Pty Ltd"
    assert document["document"]["statusLabel"] == "Draft"
    assert document["document"]["number"] is None


def test_paid_and_void_statuses_keep_status_labels_and_credit_note_reuses_primitives():
    paid = build_invoice_document(_invoice("paid"), _lines(), language="en")
    void = build_invoice_document(_invoice("void"), _lines(), language="zh")
    credit = build_credit_note_document(_invoice("issued"), _lines(), language="en")
    assert paid["statusLabel"] == "Paid"
    assert paid["paymentSummary"]["balanceCents"] == 0
    assert void["statusLabel"] == "已作废"
    assert void["document"]["voidReason"] == "重复开具"
    assert credit["document"]["kind"] == "credit_note"
    assert credit["lines"][0]["taxCents"] == 100


def test_detail_route_requests_decimal_quantities_and_returns_the_document_dto():
    api = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas" / "api_v1").glob("*.py")))
    detail = api.split('def billing_invoice_detail(', 1)[1].split(
        '@api_v1.route("/billing/invoices/<invoice_id>/lines"', 1
    )[0]
    assert "quantity::text AS quantity" in detail
    assert "LEFT JOIN tenant_billing_identity" in detail
    assert "payment_allocations" in detail
    assert "creditNotes" in detail
    assert "LEFT JOIN refunds" in detail
    assert "build_invoice_document" in detail
    assert '"document": document' in detail


def test_invoice_csv_export_is_tenant_scoped_permission_gated_and_formula_safe():
    api = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas" / "api_v1").glob("*.py")))
    start = api.index('@api_v1.route("/billing/invoices/export.csv"')
    export = api[start:api.index('@api_v1.route("/billing/invoices",', start)]
    assert '@permission_required("billing:read")' in export
    assert 'require_permission(getattr(g, "actor", None), "data:export")' in export
    assert "includeDrafts" in export
    assert "_INVOICE_EXPORT_MAX_ROWS" in export
    assert "_INVOICE_EXPORT_MAX_DAYS" in api
    assert "recipient_for_invoice" in export
    assert "csv_safe_cell" in export
    assert "_export_audit" in export
