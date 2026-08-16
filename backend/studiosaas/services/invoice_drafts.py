"""Atomic, idempotent creation of a payer and an invoice draft.

The browser used to create a payer, create a draft, and then append each line
as separate requests.  This service is the single aggregate command used by
the CMS: every input is checked before a domain row is inserted, and the
existing financial-operation table makes a lost response safe to replay.
"""

from __future__ import annotations

from decimal import Decimal
import json
import re
import uuid
from typing import Any, Mapping

from ..audit import record_audit_event
from ..db import fetch_all, fetch_one
from . import billing
from .credit_settlements import (
    CreditSettlementConflict,
    _finish_operation,
    _operation_start,
    payload_hash,
)


class InvoiceDraftError(RuntimeError):
    """A draft command was invalid or could not be completed."""


class InvoiceDraftConflict(InvoiceDraftError):
    """The request conflicts with an existing idempotency or duplicate gate."""

    status = 409

    def __init__(self, message: str, *, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


_SOURCE_KINDS = {
    "manual", "tuition", "package", "lesson", "rental", "goods", "ticket",
    "engagement", "opening_balance",
}
_ACCOUNT_FIELDS = {
    "name", "kind", "contactName", "email", "mobile", "companyName", "abn",
    "billingAddress", "paymentTermsDays", "purchaseOrderRef", "language", "note",
}
_LINE_FIELDS = {
    "description", "quantity", "unitPriceCents", "taxCodeId", "taxRateBp",
    "sourceKind", "sourceId", "studentId",
}


def _uuid(value: Any, label: str, *, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise InvoiceDraftError(f"{label} is required.")
        return None
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError, TypeError) as exc:
        raise InvoiceDraftError(f"{label} must be a UUID.") from exc


def _text(value: Any, label: str, *, default: str = "", limit: int = 500) -> str:
    if value is None:
        return default
    if isinstance(value, (dict, list, tuple, set)):
        raise InvoiceDraftError(f"{label} must be text.")
    return str(value).strip()[:limit]


def _strict_bool(value: Any, label: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise InvoiceDraftError(f"{label} must be true or false.")
    return value


def _strict_int(value: Any, label: str, *, default: int | None = None) -> int:
    if value is None or value == "":
        if default is None:
            raise InvoiceDraftError(f"{label} is required.")
        return default
    if isinstance(value, bool) or isinstance(value, float):
        raise InvoiceDraftError(f"{label} must be an integer.")
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise InvoiceDraftError(f"{label} must be an integer.") from exc
    if str(value).strip() != str(number):
        raise InvoiceDraftError(f"{label} must be an integer.")
    return number


def _quantity(value: Any) -> Decimal:
    if isinstance(value, (bool, float)):
        raise InvoiceDraftError("quantity must be a decimal string with at most two decimal places.")
    try:
        quantity = Decimal(str(value))
    except Exception as exc:  # Decimal has several concrete error subclasses.
        raise InvoiceDraftError("quantity must be a decimal string.") from exc
    if not quantity.is_finite() or quantity <= 0:
        raise InvoiceDraftError("quantity must be greater than zero.")
    if abs(quantity.as_tuple().exponent) > 2:
        raise InvoiceDraftError("quantity may have at most two decimal places.")
    return quantity


def _normalise_account(raw: Mapping[str, Any]) -> dict[str, Any]:
    unknown = sorted(set(raw) - _ACCOUNT_FIELDS)
    if unknown:
        raise InvoiceDraftError(f"Unknown payer create field(s): {', '.join(unknown)}")

    kind = _text(raw.get("kind"), "payer.kind", default="family") or "family"
    if kind not in {"person", "family", "organisation"}:
        raise InvoiceDraftError("payer.kind must be person, family, or organisation.")
    name = _text(raw.get("name"), "payer.name")
    company_name = _text(raw.get("companyName"), "payer.companyName")
    if kind == "organisation":
        if not (name or company_name):
            raise InvoiceDraftError("An organisation needs a company name.")
        name = name or company_name
    elif not name:
        raise InvoiceDraftError("A personal or family payer needs a name.")

    email = _text(raw.get("email"), "payer.email").lower()
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise InvoiceDraftError("payer.email must be a valid email address or empty.")
    mobile = _text(raw.get("mobile"), "payer.mobile")
    if mobile and not re.fullmatch(r"[+0-9() .-]{6,32}", mobile):
        raise InvoiceDraftError("payer.mobile must contain phone characters only.")
    abn = _text(raw.get("abn"), "payer.abn")
    abn_digits = re.sub(r"\D", "", abn)
    if abn and len(abn_digits) != 11:
        raise InvoiceDraftError("payer.abn must contain 11 digits, with spaces optional.")
    language = _text(raw.get("language"), "payer.language")
    if language not in {"", "zh", "en"}:
        raise InvoiceDraftError("payer.language must be empty, zh, or en.")
    payment_terms_days = _strict_int(
        raw.get("paymentTermsDays"), "payer.paymentTermsDays", default=14
    )
    if not 0 <= payment_terms_days <= 3650:
        raise InvoiceDraftError("payer.paymentTermsDays must be between 0 and 3650.")

    return {
        "name": name,
        "kind": kind,
        "contactName": _text(raw.get("contactName"), "payer.contactName"),
        "email": email,
        "mobile": mobile,
        "companyName": company_name,
        "abn": abn,
        "billingAddress": _text(raw.get("billingAddress"), "payer.billingAddress"),
        "paymentTermsDays": payment_terms_days,
        "purchaseOrderRef": _text(raw.get("purchaseOrderRef"), "payer.purchaseOrderRef"),
        "language": language,
        "note": _text(raw.get("note"), "payer.note"),
        "_abnDigits": abn_digits,
    }


def _normalise_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    allowed = {"requestId", "payer", "invoice", "lines", "allowPossibleDuplicate"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise InvoiceDraftError(f"Unknown invoice draft field(s): {', '.join(unknown)}")

    request_id = _uuid(payload.get("requestId"), "requestId", required=True)
    payer = payload.get("payer")
    if not isinstance(payer, Mapping):
        raise InvoiceDraftError("payer must be an object.")
    payer_unknown = sorted(set(payer) - {"accountId", "create", "linkedStudentIds"})
    if payer_unknown:
        raise InvoiceDraftError(f"Unknown payer field(s): {', '.join(payer_unknown)}")
    has_account = bool(str(payer.get("accountId") or "").strip())
    has_create = payer.get("create") is not None
    if has_account == has_create:
        raise InvoiceDraftError("payer must contain exactly one of accountId or create.")

    linked_raw = payer.get("linkedStudentIds")
    if has_account:
        if linked_raw is not None:
            raise InvoiceDraftError("linkedStudentIds is only valid with payer.create.")
        payer_norm: dict[str, Any] = {
            "accountId": _uuid(payer.get("accountId"), "payer.accountId", required=True),
        }
    else:
        if not isinstance(payer.get("create"), Mapping):
            raise InvoiceDraftError("payer.create must be an object.")
        if linked_raw is None:
            linked_raw = []
        if not isinstance(linked_raw, list):
            raise InvoiceDraftError("payer.linkedStudentIds must be an array.")
        linked_ids: list[str] = []
        for raw_id in linked_raw:
            parsed = _uuid(raw_id, "payer.linkedStudentIds item", required=True)
            if parsed not in linked_ids:
                linked_ids.append(parsed)
        if len(linked_ids) > 100:
            raise InvoiceDraftError("payer.linkedStudentIds cannot contain more than 100 students.")
        payer_norm = {"create": _normalise_account(payer["create"]), "linkedStudentIds": linked_ids}

    invoice = payload.get("invoice") or {}
    if not isinstance(invoice, Mapping):
        raise InvoiceDraftError("invoice must be an object.")
    invoice_unknown = sorted(set(invoice) - {"note", "purchaseOrderRef"})
    if invoice_unknown:
        raise InvoiceDraftError(f"Unknown invoice field(s): {', '.join(invoice_unknown)}")
    invoice_norm = {
        "note": _text(invoice.get("note"), "invoice.note"),
        "purchaseOrderRef": _text(invoice.get("purchaseOrderRef"), "invoice.purchaseOrderRef"),
    }

    lines = payload.get("lines")
    if not isinstance(lines, list) or not lines:
        raise InvoiceDraftError("lines must contain at least one invoice line.")
    if len(lines) > 100:
        raise InvoiceDraftError("lines cannot contain more than 100 invoice lines.")
    line_norm: list[dict[str, Any]] = []
    for index, raw_line in enumerate(lines, start=1):
        if not isinstance(raw_line, Mapping):
            raise InvoiceDraftError(f"line {index} must be an object.")
        unknown_line = sorted(set(raw_line) - _LINE_FIELDS)
        if unknown_line:
            raise InvoiceDraftError(f"Unknown line {index} field(s): {', '.join(unknown_line)}")
        description = _text(raw_line.get("description"), f"line {index}.description")
        if not description:
            raise InvoiceDraftError(f"line {index} needs a description.")
        unit_price = _strict_int(raw_line.get("unitPriceCents"), f"line {index}.unitPriceCents")
        if unit_price < 0:
            raise InvoiceDraftError(f"line {index}.unitPriceCents cannot be negative.")
        tax_rate = _strict_int(raw_line.get("taxRateBp"), f"line {index}.taxRateBp", default=0)
        if not 0 <= tax_rate <= 10000:
            raise InvoiceDraftError(f"line {index}.taxRateBp must be between 0 and 10000.")
        source_kind = _text(raw_line.get("sourceKind"), f"line {index}.sourceKind", default="manual") or "manual"
        if source_kind not in _SOURCE_KINDS:
            raise InvoiceDraftError(f"line {index}.sourceKind is not supported.")
        line_norm.append({
            "description": description,
            "quantity": _quantity(raw_line.get("quantity", "1")),
            "unitPriceCents": unit_price,
            "taxCodeId": _uuid(raw_line.get("taxCodeId"), f"line {index}.taxCodeId"),
            "taxRateBp": tax_rate,
            "sourceKind": source_kind,
            "sourceId": _uuid(raw_line.get("sourceId"), f"line {index}.sourceId"),
            "studentId": _uuid(raw_line.get("studentId"), f"line {index}.studentId"),
        })

    allow_duplicate = _strict_bool(
        payload.get("allowPossibleDuplicate"), "allowPossibleDuplicate", default=False
    )
    # Decimal and UUID values are normalised into JSON-safe strings before the
    # digest is calculated.  Equivalent retries therefore share one key.
    canonical = {
        "requestId": request_id,
        "payer": payer_norm,
        "invoice": invoice_norm,
        "lines": [
            {**line, "quantity": format(line["quantity"], "f")}
            for line in line_norm
        ],
        "allowPossibleDuplicate": allow_duplicate,
    }
    return {
        "requestId": request_id,
        "payer": payer_norm,
        "invoice": invoice_norm,
        "lines": line_norm,
        "allowPossibleDuplicate": allow_duplicate,
        "canonical": canonical,
    }


def _duplicate_candidates(conn, tenant_id: str, account: Mapping[str, Any]) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = [tenant_id]
    if account["_abnDigits"]:
        clauses.append("regexp_replace(COALESCE(abn, ''), '[^0-9]', '', 'g') = %s")
        params.append(account["_abnDigits"])
    if account["email"]:
        clauses.append("lower(trim(email)) = %s")
        params.append(account["email"])
    if account["mobile"]:
        clauses.append("regexp_replace(COALESCE(mobile, ''), '[^0-9]', '', 'g') = %s")
        params.append(re.sub(r"\D", "", account["mobile"]))
    if not clauses:
        return []
    return fetch_all(
        conn,
        f"""
        SELECT id, name, kind, company_name, email, mobile, abn
        FROM billing_accounts
        WHERE tenant_id = %s AND status = 'active' AND ({' OR '.join(clauses)})
        ORDER BY lower(name), id
        LIMIT 10
        """,
        tuple(params),
    )


def create_invoice_draft(
    conn,
    tenant_id: str,
    payload: Mapping[str, Any],
    *,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Validate and create one payer/invoice/lines aggregate in one transaction."""

    if not isinstance(payload, Mapping):
        raise InvoiceDraftError("A JSON object is required.")
    data = _normalise_payload(payload)
    digest = payload_hash(data["canonical"])
    try:
        operation, replayed = _operation_start(
            conn, tenant_id, data["requestId"], "invoice_draft_create", digest
        )
    except CreditSettlementConflict as exc:
        raise InvoiceDraftConflict(str(exc)) from exc
    if replayed:
        return operation

    payer = data["payer"]
    existing_account = None
    create_account = payer.get("create")
    linked_ids = payer.get("linkedStudentIds", [])
    if payer.get("accountId"):
        existing_account = fetch_one(
            conn,
            """
            SELECT id, name, kind, contact_name, email, mobile, company_name, abn,
                   billing_address, payment_terms_days, purchase_order_ref, language
            FROM billing_accounts
            WHERE tenant_id = %s AND id = %s AND status = 'active'
            FOR SHARE
            """,
            (tenant_id, payer["accountId"]),
        )
        if not existing_account:
            raise InvoiceDraftError("Billing account was not found.")

    student_ids = set(linked_ids)
    student_ids.update(line["studentId"] for line in data["lines"] if line["studentId"])
    found_students = {}
    if student_ids:
        found_students = {
            str(row["id"]): row
            for row in fetch_all(
                conn,
                "SELECT id FROM students WHERE tenant_id = %s AND id = ANY(%s::uuid[])",
                (tenant_id, list(student_ids)),
            )
        }
        missing = sorted(student_ids - set(found_students))
        if missing:
            raise InvoiceDraftError("One or more students were not found.")

    tax_ids = {line["taxCodeId"] for line in data["lines"] if line["taxCodeId"]}
    tax_codes = {}
    if tax_ids:
        tax_codes = {
            str(row["id"]): row
            for row in fetch_all(
                conn,
                """
                SELECT id, rate_bp, is_active
                FROM tax_codes
                WHERE tenant_id = %s AND id = ANY(%s::uuid[])
                """,
                (tenant_id, list(tax_ids)),
            )
        }
        if set(tax_codes) != tax_ids or any(not row["is_active"] for row in tax_codes.values()):
            raise InvoiceDraftError("One or more tax codes were not found or are inactive.")

    duplicate_candidates: list[dict[str, Any]] = []
    if create_account:
        duplicate_candidates = _duplicate_candidates(conn, tenant_id, create_account)
        if duplicate_candidates and not data["allowPossibleDuplicate"]:
            raise InvoiceDraftConflict(
                "A possible duplicate payer was found. Review it before creating another payer.",
                details={
                    "requiresReview": True,
                    "possibleDuplicates": [
                        {**row, "id": str(row["id"])} for row in duplicate_candidates
                    ],
                },
            )

    calculated_lines: list[dict[str, Any]] = []
    for index, line in enumerate(data["lines"], start=1):
        if line["taxCodeId"] and int(tax_codes[line["taxCodeId"]]["rate_bp"]) != line["taxRateBp"]:
            raise InvoiceDraftError(f"line {index}.taxRateBp must match its tax code.")
        net, tax, total = billing.line_amounts(
            line["quantity"], line["unitPriceCents"], line["taxRateBp"]
        )
        calculated_lines.append({**line, "netCents": net, "taxCents": tax, "totalCents": total})

    account_id = str(existing_account["id"]) if existing_account else None
    with conn.cursor() as cur:
        if create_account:
            cur.execute(
                """
                INSERT INTO billing_accounts
                    (tenant_id, name, kind, contact_name, email, mobile,
                     company_name, abn, billing_address, payment_terms_days,
                     purchase_order_ref, language, note)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant_id, create_account["name"], create_account["kind"],
                    create_account["contactName"], create_account["email"], create_account["mobile"],
                    create_account["companyName"], create_account["abn"], create_account["billingAddress"],
                    create_account["paymentTermsDays"], create_account["purchaseOrderRef"],
                    create_account["language"], create_account["note"],
                ),
            )
            account_id = str(cur.fetchone()["id"])
            for student_id in linked_ids:
                cur.execute(
                    """
                    INSERT INTO billing_account_members (tenant_id, billing_account_id, student_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (billing_account_id, student_id) DO NOTHING
                    """,
                    (tenant_id, account_id, student_id),
                )

        cur.execute(
            """
            INSERT INTO invoices (tenant_id, billing_account_id, note, purchase_order_ref)
            VALUES (%s, %s, %s, %s)
            RETURNING id, status, total_cents
            """,
            (tenant_id, account_id, data["invoice"]["note"], data["invoice"]["purchaseOrderRef"]),
        )
        invoice = cur.fetchone()
        line_ids: list[str] = []
        for sort_order, line in enumerate(calculated_lines):
            cur.execute(
                """
                INSERT INTO invoice_lines
                    (tenant_id, invoice_id, description, quantity, unit_price_cents,
                     tax_code_id, tax_rate_bp, tax_cents, total_cents,
                     source_kind, source_id, student_id, sort_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant_id, invoice["id"], line["description"], line["quantity"],
                    line["unitPriceCents"], line["taxCodeId"], line["taxRateBp"],
                    line["taxCents"], line["totalCents"], line["sourceKind"],
                    line["sourceId"], line["studentId"], sort_order,
                ),
            )
            line_ids.append(str(cur.fetchone()["id"]))

    totals = billing.recalculate_totals(conn, tenant_id, str(invoice["id"]))
    billing.record_event(
        conn, tenant_id, str(invoice["id"]), "drafted", actor_user_id,
        {"request_id": data["requestId"], "line_count": len(line_ids)},
    )
    if create_account:
        record_audit_event(
            conn,
            action="billing_account.created",
            resource_type="billing_account",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_id=account_id or "",
            metadata_json=json.dumps({
                "requestId": data["requestId"],
                "studentIds": linked_ids,
                "possibleDuplicateCount": len(duplicate_candidates),
                "possibleDuplicateReview": (
                    "operator explicitly allowed a possible duplicate"
                    if duplicate_candidates else ""
                ),
            }, ensure_ascii=False),
        )

    result = {
        "requestId": data["requestId"],
        "payer": {
            "accountId": account_id,
            "created": bool(create_account),
            "possibleDuplicates": [
                {**row, "id": str(row["id"])} for row in duplicate_candidates
            ],
        },
        "invoice": {"id": str(invoice["id"]), "status": invoice["status"], **totals},
        "invoiceId": str(invoice["id"]),
        "lineIds": line_ids,
        "replayed": False,
    }
    _finish_operation(conn, tenant_id, data["requestId"], "invoice_draft_create", result)
    record_audit_event(
        conn,
        action="invoice.drafted",
        resource_type="invoice",
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        resource_id=str(invoice["id"]),
        metadata_json=json.dumps({
            "requestId": data["requestId"],
            "payerAccountId": account_id,
            "lineIds": line_ids,
        }, ensure_ascii=False),
    )
    return result
