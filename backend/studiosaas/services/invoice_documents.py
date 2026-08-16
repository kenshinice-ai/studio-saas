"""Stable invoice and credit-note document primitives.

The API, CSV exporter and PDF renderer all need the same legal facts.  This
module is deliberately pure: it accepts database-shaped mappings and returns
JSON-shaped data without doing any formatting with floats or reaching into the
database.  Drafts use the live supplier/payer fields; once a document is
issued, the stored snapshots are the only identity source used here.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from typing import Any, Iterable, Mapping


STATUS_LABELS = {
    "draft": {"zh": "草稿", "en": "Draft"},
    "issued": {"zh": "已开具", "en": "Issued"},
    "part_paid": {"zh": "部分付款", "en": "Part paid"},
    "paid": {"zh": "已付清", "en": "Paid"},
    "void": {"zh": "已作废", "en": "Void"},
}


def csv_safe_cell(value: Any) -> Any:
    """Prevent spreadsheet formula execution for user-controlled text."""

    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def _string(value: Any) -> str:
    return "" if value is None else str(value)


def _id(value: Any) -> str | None:
    return None if value is None else str(value)


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _integer(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(value)


def decimal_quantity(value: Any) -> str:
    """Return a finite DB quantity as a non-float decimal string."""

    try:
        quantity = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invoice quantity must be a decimal value.") from exc
    if not quantity.is_finite():
        raise ValueError("Invoice quantity must be finite.")
    # ``format(..., 'f')`` preserves two-place values from numeric(10,2) and
    # never emits a binary float or scientific notation into a document.
    return format(quantity, "f")


def _mapping(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return dict(parsed) if isinstance(parsed, Mapping) else {}
    return {}


def _address(source: Mapping[str, Any], *, snapshot: bool) -> dict[str, str]:
    raw = _mapping(source.get("address")) if snapshot else {}
    if snapshot:
        return {
            "line1": _string(raw.get("line1")),
            "line2": _string(raw.get("line2")),
            "suburb": _string(raw.get("suburb")),
            "state": _string(raw.get("state")),
            "postcode": _string(raw.get("postcode")),
            "country": _string(raw.get("country") or "Australia"),
        }
    return {
        "line1": _string(source.get("supplier_address_line1")),
        "line2": _string(source.get("supplier_address_line2")),
        "suburb": _string(source.get("supplier_suburb")),
        "state": _string(source.get("supplier_state")),
        "postcode": _string(source.get("supplier_postcode")),
        "country": _string(source.get("supplier_country") or "Australia"),
    }


def supplier_for_invoice(invoice: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the supplier identity, preferring an issued snapshot."""

    is_snapshot = _string(invoice.get("status")) != "draft" and bool(
        _mapping(invoice.get("supplier_snapshot"))
    )
    source = _mapping(invoice.get("supplier_snapshot")) if is_snapshot else invoice
    if is_snapshot:
        bank = _mapping(source.get("bank"))
        return {
            "schemaVersion": source.get("schemaVersion"),
            "isSnapshot": True,
            "configured": bool(source.get("configured")),
            "legalName": _string(source.get("legalName")),
            "tradingName": _string(source.get("tradingName")),
            "abn": _string(source.get("abn")),
            "gstRegistered": bool(source.get("gstRegistered")),
            "address": _address(source, snapshot=True),
            "contactEmail": _string(source.get("contactEmail")),
            "contactPhone": _string(source.get("contactPhone")),
            "website": _string(source.get("website")),
            "bank": {
                "accountName": _string(bank.get("accountName")),
                "bsb": _string(bank.get("bsb")),
                "accountNo": _string(bank.get("accountNo")),
            },
            "paymentNote": _string(source.get("paymentNote")),
        }
    return {
        "schemaVersion": None,
        "isSnapshot": False,
        "configured": bool(invoice.get("supplier_configured")),
        "legalName": _string(invoice.get("supplier_legal_name")),
        "tradingName": _string(invoice.get("supplier_trading_name")),
        "abn": _string(invoice.get("supplier_abn")),
        "gstRegistered": bool(invoice.get("supplier_gst_registered")),
        "address": _address(invoice, snapshot=False),
        "contactEmail": _string(invoice.get("supplier_contact_email")),
        "contactPhone": _string(invoice.get("supplier_contact_phone")),
        "website": _string(invoice.get("supplier_website")),
        "bank": {
            "accountName": _string(invoice.get("supplier_bank_account_name")),
            "bsb": _string(invoice.get("supplier_bank_bsb")),
            "accountNo": _string(invoice.get("supplier_bank_account_no")),
        },
        "paymentNote": _string(invoice.get("supplier_payment_note")),
    }


def recipient_for_invoice(invoice: Mapping[str, Any]) -> dict[str, Any]:
    """Resolve the payer identity, preferring an issued snapshot."""

    is_snapshot = _string(invoice.get("status")) != "draft" and bool(
        _mapping(invoice.get("recipient_snapshot"))
    )
    source = _mapping(invoice.get("recipient_snapshot")) if is_snapshot else invoice
    if is_snapshot:
        return {
            "schemaVersion": source.get("schemaVersion"),
            "isSnapshot": True,
            "displayName": _string(source.get("displayName")),
            "kind": _string(source.get("kind") or "family"),
            "contactName": _string(source.get("contactName")),
            "companyName": _string(source.get("companyName")),
            "abn": _string(source.get("abn")),
            "email": _string(source.get("email")),
            "mobile": _string(source.get("mobile")),
            "billingAddress": _string(source.get("billingAddress")),
            "paymentTermsDays": _integer(source.get("paymentTermsDays")),
            "purchaseOrderRef": _string(source.get("purchaseOrderRef")),
            "language": _string(source.get("language")),
        }
    return {
        "schemaVersion": None,
        "isSnapshot": False,
        "displayName": _string(invoice.get("account_name")),
        "kind": _string(invoice.get("account_kind") or "family"),
        "contactName": _string(invoice.get("account_contact_name")),
        "companyName": _string(invoice.get("account_company_name")),
        "abn": _string(invoice.get("account_abn")),
        "email": _string(invoice.get("account_email")),
        "mobile": _string(invoice.get("account_mobile")),
        "billingAddress": _string(invoice.get("account_billing_address")),
        "paymentTermsDays": _integer(invoice.get("account_payment_terms_days")),
        "purchaseOrderRef": _string(invoice.get("account_purchase_order_ref")),
        "language": _string(invoice.get("account_language")),
    }


def _line(line: Mapping[str, Any]) -> dict[str, Any]:
    tax_cents = _integer(line.get("tax_cents"))
    total_cents = _integer(line.get("total_cents"))
    net_cents = _integer(line.get("net_cents"), total_cents - tax_cents)
    return {
        "id": _id(line.get("id")),
        "description": _string(line.get("description")),
        "quantity": decimal_quantity(line.get("quantity", "0")),
        "unitPriceCents": _integer(line.get("unit_price_cents")),
        "taxRateBp": _integer(line.get("tax_rate_bp")),
        "netCents": net_cents,
        "taxCents": tax_cents,
        "totalCents": total_cents,
        "sourceKind": _string(line.get("source_kind") or "manual"),
        "sourceId": _id(line.get("source_id")),
        "studentId": _id(line.get("student_id")),
    }


def _payment(payment: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": _id(payment.get("id")),
        "method": _string(payment.get("method")),
        "provider": _string(payment.get("provider")),
        "status": _string(payment.get("status")),
        "amountCents": _integer(payment.get("amount_cents")),
        "allocatedCents": _integer(payment.get("allocated_cents")),
        "refundedCents": _integer(payment.get("refunded_cents")),
        "receivedAt": _iso(payment.get("received_at")),
        "note": _string(payment.get("note")),
    }


def _status_label(status: str, language: str) -> str:
    locale = "en" if str(language).lower().startswith("en") else "zh"
    return STATUS_LABELS.get(status, {}).get(locale, status)


def build_document(
    document: Mapping[str, Any],
    lines: Iterable[Mapping[str, Any]],
    payments: Iterable[Mapping[str, Any]] | None = None,
    *,
    kind: str = "invoice",
    language: str = "zh",
) -> dict[str, Any]:
    """Build the shared document DTO used by invoice and credit-note exports."""

    status = _string(document.get("status") or "draft")
    line_documents = [_line(line) for line in lines]
    subtotal = _integer(document.get("subtotal_cents"), sum(line["netCents"] for line in line_documents))
    tax = _integer(document.get("tax_cents"), sum(line["taxCents"] for line in line_documents))
    total = _integer(document.get("total_cents"), subtotal + tax)
    amount_paid = _integer(document.get("amount_paid_cents"))
    amount_credited = _integer(document.get("amount_credited_cents"))
    balance = _integer(document.get("balance_cents"), total - amount_paid - amount_credited)
    amount_refunded = sum(_integer(payment.get("refunded_cents")) for payment in (payments or ()))
    net_received = max(0, amount_paid - amount_refunded)
    metadata = {
        "id": _id(document.get("id")),
        "kind": kind,
        "number": _string(document.get("number")) or None,
        "status": status,
        "statusLabel": _status_label(status, language),
        "currency": _string(document.get("currency") or "AUD"),
        "issueDate": _iso(document.get("issue_date")),
        "dueDate": _iso(document.get("due_date")),
        "note": _string(document.get("note")),
        "purchaseOrderRef": _string(document.get("purchase_order_ref")),
        "createdAt": _iso(document.get("created_at")),
        "updatedAt": _iso(document.get("updated_at")),
        "voidedAt": _iso(document.get("voided_at")),
        "voidReason": _string(document.get("void_reason")),
    }
    return {
        "document": metadata,
        "statusLabel": metadata["statusLabel"],
        "supplier": supplier_for_invoice(document),
        "recipient": recipient_for_invoice(document),
        "lines": line_documents,
        "totals": {
            "subtotalCents": subtotal,
            "taxCents": tax,
            "totalCents": total,
        },
        "paymentSummary": {
            "amountPaidCents": amount_paid,
            "amountRefundedCents": amount_refunded,
            "netReceivedCents": net_received,
            "amountCreditedCents": amount_credited,
            "balanceCents": balance,
            "payments": [_payment(payment) for payment in (payments or ())],
        },
    }


def build_invoice_document(
    invoice: Mapping[str, Any],
    lines: Iterable[Mapping[str, Any]],
    payments: Iterable[Mapping[str, Any]] | None = None,
    *,
    language: str = "zh",
) -> dict[str, Any]:
    """Build the invoice DTO; kept separate as the public API entry point."""

    return build_document(invoice, lines, payments, kind="invoice", language=language)


def build_credit_note_document(
    credit_note: Mapping[str, Any],
    lines: Iterable[Mapping[str, Any]],
    *,
    language: str = "zh",
) -> dict[str, Any]:
    """Build a credit-note DTO from the same line/tax/document primitives."""

    return build_document(credit_note, lines, kind="credit_note", language=language)


# Descriptive alias for callers that prefer the noun over the verb.
invoice_document = build_invoice_document
