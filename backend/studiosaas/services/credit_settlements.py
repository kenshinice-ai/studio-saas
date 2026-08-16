"""Atomic credit top-ups with an optional invoice and payment.

The lesson-credit ledger and the money ledger are deliberately kept separate.
This service is the one place where a purchase may connect them: it writes the
credit movement, the invoice line, the payment allocation and the explicit
``credit_financial_links`` row in one transaction.  A request id is recorded
before any of those writes so a retried browser request can return the original
result without guessing which part of a previous attempt succeeded.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
import uuid
from typing import Any, Mapping

from ..audit import record_audit_event
from ..db import fetch_one
from . import billing, payments


class CreditSettlementError(RuntimeError):
    """A settlement request was invalid or could not be completed safely."""


class CreditSettlementConflict(CreditSettlementError):
    """The request id is already bound to a different or active operation."""


def _uuid(value: Any, label: str, *, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise CreditSettlementError(f"{label} is required.")
        return None
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError, TypeError) as exc:
        raise CreditSettlementError(f"{label} must be a UUID.") from exc


def _strict_bool(value: Any, label: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise CreditSettlementError(f"{label} must be true or false.")


def _credits(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception as exc:  # Decimal raises several concrete subclasses.
        raise CreditSettlementError("credits must be a positive decimal.") from exc
    if amount <= 0:
        raise CreditSettlementError("credits must be a positive decimal.")
    if amount.as_tuple().exponent < -2:
        raise CreditSettlementError("credits may have at most two decimal places.")
    return amount


def _cents(value: Any) -> int:
    if isinstance(value, bool):
        raise CreditSettlementError("amountCents must be a non-negative integer.")
    try:
        amount = int(value)
    except (TypeError, ValueError) as exc:
        raise CreditSettlementError("amountCents must be a non-negative integer.") from exc
    if str(value).strip() != str(amount):
        raise CreditSettlementError("amountCents must be a non-negative integer.")
    if amount < 0:
        raise CreditSettlementError("amountCents must be a non-negative integer.")
    return amount


def _canonical(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def payload_hash(payload: Mapping[str, Any]) -> str:
    """Return the stable hash used by ``financial_operation_requests``."""

    encoded = json.dumps(
        _canonical(payload), ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _gross_split(gross_cents: int, rate_bp: int) -> tuple[int, int]:
    """Reverse a gross amount into integer net/tax cents without floats.

    ``billing.line_amounts`` rounds tax half-up on the whole line.  We search
    the handful of integers around the algebraic estimate so the returned pair
    satisfies the exact invariant ``net + tax == gross`` even at rounding
    boundaries.
    """

    if gross_cents < 0 or not 0 <= rate_bp <= 10000:
        raise CreditSettlementError("Gross amount or tax rate is invalid.")
    if rate_bp == 0:
        return gross_cents, 0
    estimate = int(
        (Decimal(gross_cents) * Decimal(10000) / Decimal(10000 + rate_bp)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    for net in range(max(0, estimate - 4), estimate + 5):
        tax = int(
            (Decimal(net) * Decimal(rate_bp) / Decimal(10000)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
        if net + tax == gross_cents:
            return net, tax
    raise CreditSettlementError(
        "Gross amount cannot be represented exactly for the selected tax code."
    )


def _operation_start(conn, tenant_id: str, request_id: str, operation_kind: str, digest: str):
    """Claim an operation key, or return its already-successful result."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO financial_operation_requests
                (tenant_id, request_id, operation_kind, payload_hash, status)
            VALUES (%s, %s, %s, %s, 'in_progress')
            ON CONFLICT (tenant_id, request_id, operation_kind) DO NOTHING
            RETURNING id, status, payload_hash, result
            """,
            (tenant_id, request_id, operation_kind, digest),
        )
        row = cur.fetchone()
    if row:
        return row, False

    existing = None
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, status, payload_hash, result
            FROM financial_operation_requests
            WHERE tenant_id = %s AND request_id = %s AND operation_kind = %s
            FOR UPDATE
            """,
            (tenant_id, request_id, operation_kind),
        )
        existing = cur.fetchone()
    if not existing:
        raise CreditSettlementConflict("The settlement request could not be claimed; retry.")
    if existing["payload_hash"] != digest:
        raise CreditSettlementConflict(
            "This requestId was already used with different settlement details."
        )
    if existing["status"] == "succeeded":
        result = dict(existing["result"] or {})
        result["replayed"] = True
        return result, True
    raise CreditSettlementConflict("This settlement request is already in progress.")


def _finish_operation(
    conn,
    tenant_id: str,
    request_id: str,
    operation_kind: str,
    result: Mapping[str, Any],
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE financial_operation_requests
               SET status = 'succeeded', result = %s::jsonb,
                   credit_transaction_id = %s,
                   invoice_id = %s,
                   payment_id = %s,
                   updated_at = now(), completed_at = now()
             WHERE tenant_id = %s AND request_id = %s AND operation_kind = %s
            """,
            (
                json.dumps(dict(result), ensure_ascii=False),
                result.get("transactionId"),
                result.get("invoiceId"),
                result.get("paymentId"),
                tenant_id,
                request_id,
                operation_kind,
            ),
        )


def create_credit_settlement(
    conn,
    tenant_id: str,
    student_id: str,
    payload: Mapping[str, Any],
    *,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Create a purchase credit movement and optional invoice/payment atomically.

    ``amountCents`` is the gross customer price (tax included).  If an invoice
    is created, the line is represented as one exact gross line so integer cents
    remain lossless even when a package price is not divisible by its credits.
    """

    if not isinstance(payload, Mapping):
        raise CreditSettlementError("A JSON object is required.")
    allowed = {"requestId", "credits", "amountCents", "paymentMethod", "packageId", "note", "billing"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise CreditSettlementError(f"Unknown settlement fields: {', '.join(unknown)}")

    request_id = _uuid(payload.get("requestId"), "requestId", required=True)
    student_id = _uuid(student_id, "studentId", required=True)
    credits = _credits(payload.get("credits"))
    amount_cents = _cents(payload.get("amountCents", 0))
    package_id = _uuid(payload.get("packageId"), "packageId")
    note = str(payload.get("note") or "").strip()[:500]
    payment_method = str(payload.get("paymentMethod") or "bank_transfer").strip()

    billing_payload = payload.get("billing") or {}
    if not isinstance(billing_payload, Mapping):
        raise CreditSettlementError("billing must be an object.")
    billing_allowed = {
        "createInvoice", "billingAccountId", "taxCodeId", "issueNow", "paymentReceived"
    }
    billing_unknown = sorted(set(billing_payload) - billing_allowed)
    if billing_unknown:
        raise CreditSettlementError(
            f"Unknown billing fields: {', '.join(billing_unknown)}"
        )
    create_invoice = _strict_bool(billing_payload.get("createInvoice"), "billing.createInvoice")
    issue_now = _strict_bool(billing_payload.get("issueNow"), "billing.issueNow")
    payment_received = _strict_bool(
        billing_payload.get("paymentReceived"), "billing.paymentReceived"
    )
    billing_account_id = _uuid(billing_payload.get("billingAccountId"), "billingAccountId")
    tax_code_id = _uuid(billing_payload.get("taxCodeId"), "taxCodeId")

    if create_invoice:
        if not billing_account_id:
            raise CreditSettlementError("billingAccountId is required when creating an invoice.")
        if amount_cents <= 0:
            raise CreditSettlementError("A zero-value top-up cannot create an invoice.")
    elif issue_now or payment_received or billing_account_id or tax_code_id:
        raise CreditSettlementError(
            "Invoice options require billing.createInvoice=true."
        )
    if payment_received and not issue_now:
        raise CreditSettlementError("A payment requires billing.issueNow=true.")
    if payment_received and amount_cents <= 0:
        raise CreditSettlementError("A payment must be greater than zero.")
    if not create_invoice and amount_cents > 0 and payment_method not in payments.MANUAL_METHODS:
        raise CreditSettlementError(f"Unknown payment method: {payment_method}")
    if create_invoice and payment_received and payment_method not in payments.MANUAL_METHODS:
        raise CreditSettlementError(f"Unknown payment method: {payment_method}")

    digest = payload_hash(payload)
    operation_kind = "credit_settlement"
    operation, replayed = _operation_start(
        conn, tenant_id, request_id, operation_kind, digest
    )
    if replayed:
        return operation

    with conn.cursor() as cur:
        student = fetch_one(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant_id, student_id),
        )
        if not student:
            raise CreditSettlementError("Student was not found.")

        account = None
        if create_invoice:
            account = fetch_one(
                conn,
                """
                SELECT id FROM billing_accounts
                WHERE tenant_id = %s AND id = %s AND status = 'active'
                FOR SHARE
                """,
                (tenant_id, billing_account_id),
            )
            if not account:
                raise CreditSettlementError("Billing account was not found.")

        package = None
        if package_id:
            package = fetch_one(
                conn,
                """
                SELECT id, name, credits, is_active
                FROM packages WHERE tenant_id = %s AND id = %s
                FOR SHARE
                """,
                (tenant_id, package_id),
            )
            if not package or not package["is_active"]:
                raise CreditSettlementError("Package was not found or is inactive.")
            if Decimal(str(package["credits"])).quantize(Decimal("0.01")) != credits:
                raise CreditSettlementError("credits must match the selected package.")

        tax_code = None
        if tax_code_id:
            tax_code = fetch_one(
                conn,
                """
                SELECT id, rate_bp, is_active FROM tax_codes
                WHERE tenant_id = %s AND id = %s
                FOR SHARE
                """,
                (tenant_id, tax_code_id),
            )
            if not tax_code or not tax_code["is_active"]:
                raise CreditSettlementError("Tax code was not found or is inactive.")

        # A single locked default account is the balance authority.  The
        # conflict-free insert handles a first top-up for a new student.
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id, course_id)
            VALUES (%s, %s, NULL)
            ON CONFLICT DO NOTHING
            """,
            (tenant_id, student_id),
        )
        cur.execute(
            """
            SELECT id, balance::numeric AS balance
            FROM credit_accounts
            WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            FOR UPDATE
            """,
            (tenant_id, student_id),
        )
        credit_account = cur.fetchone()
        if not credit_account:
            raise CreditSettlementError("The student's credit account could not be locked.")
        current_balance = Decimal(str(credit_account["balance"] or "0")).quantize(Decimal("0.01"))
        new_balance = (current_balance + credits).quantize(Decimal("0.01"))

        fee_cents = amount_cents if (not create_invoice or payment_received) else 0
        cur.execute(
            """
            INSERT INTO credit_transactions
                (tenant_id, student_id, account_id, actor_user_id, transaction_type,
                 amount, balance_after, fee_aud_cents, note)
            VALUES (%s, %s, %s, %s, 'purchase', %s, %s, %s, %s)
            RETURNING id
            """,
            (
                tenant_id, student_id, credit_account["id"], actor_user_id,
                credits, new_balance, fee_cents, note,
            ),
        )
        transaction_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            UPDATE credit_accounts SET balance = %s, updated_at = now()
            WHERE tenant_id = %s AND id = %s
            """,
            (new_balance, tenant_id, credit_account["id"]),
        )

        invoice_id = None
        invoice_line_id = None
        payment_id = None
        allocation_ids: list[str] = []
        financial_link_id = None
        net_cents = 0
        tax_cents = 0
        tax_rate_bp = int(tax_code["rate_bp"]) if tax_code else 0

        if create_invoice:
            net_cents, tax_cents = _gross_split(amount_cents, tax_rate_bp)
            cur.execute(
                """
                INSERT INTO invoices (tenant_id, billing_account_id, note)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (tenant_id, billing_account_id, note),
            )
            invoice_id = str(cur.fetchone()["id"])
            description = (
                f"{package['name']} · {credits} credits" if package
                else f"Credit top-up · {credits} credits"
            )
            cur.execute(
                """
                INSERT INTO invoice_lines
                    (tenant_id, invoice_id, description, quantity, unit_price_cents,
                     tax_code_id, tax_rate_bp, tax_cents, total_cents,
                     source_kind, source_id, student_id, sort_order)
                VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s, 'package', %s, %s, 0)
                RETURNING id
                """,
                (
                    tenant_id, invoice_id, description, net_cents, tax_code_id,
                    tax_rate_bp, tax_cents, amount_cents, package_id, student_id,
                ),
            )
            invoice_line_id = str(cur.fetchone()["id"])
            billing.recalculate_totals(conn, tenant_id, invoice_id)

            if issue_now:
                billing.issue_invoice(
                    conn, tenant_id, invoice_id, actor_user_id=actor_user_id
                )

            if payment_received:
                payment = payments.record_payment(
                    conn,
                    tenant_id,
                    billing_account_id=billing_account_id,
                    amount_cents=amount_cents,
                    method=payment_method,
                    idempotency_key=f"credit-settlement:{request_id}",
                    note=note,
                    recorded_by_user_id=actor_user_id,
                )
                payment_id = str(payment["id"])
                allocations = payments.allocate(
                    conn,
                    tenant_id,
                    payment_id,
                    [payments.Allocation(invoice_id=invoice_id, amount_cents=amount_cents)],
                    actor_user_id=actor_user_id,
                )
                allocation_ids = [str(item["id"]) for item in allocations]

            cur.execute(
                """
                INSERT INTO credit_financial_links
                    (tenant_id, credit_transaction_id, invoice_id, invoice_line_id, payment_id)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (tenant_id, transaction_id, invoice_id, invoice_line_id, payment_id),
            )
            financial_link_id = str(cur.fetchone()["id"])
            billing.record_event(
                conn,
                tenant_id,
                invoice_id,
                "credit_settled",
                actor_user_id,
                {
                    "credit_transaction_id": transaction_id,
                    "payment_id": payment_id,
                    "amount_cents": amount_cents,
                },
            )

        result = {
            "requestId": request_id,
            "transactionId": transaction_id,
            "invoiceId": invoice_id,
            "invoiceLineId": invoice_line_id,
            "paymentId": payment_id,
            "allocationIds": allocation_ids,
            "financialLinkId": financial_link_id,
            "netCents": net_cents,
            "taxCents": tax_cents,
            "totalCents": amount_cents,
            "newBalance": format(new_balance, "f"),
            "replayed": False,
        }
        _finish_operation(conn, tenant_id, request_id, operation_kind, result)
        record_audit_event(
            conn,
            action="credit.settled",
            resource_type="credit_transaction",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_id=transaction_id,
            metadata_json=json.dumps(
                {
                    "requestId": request_id,
                    "invoiceId": invoice_id,
                    "paymentId": payment_id,
                    "amountCents": amount_cents,
                },
                ensure_ascii=False,
            ),
        )
    return result
