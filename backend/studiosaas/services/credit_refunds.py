"""Atomic refunds that reverse a credit purchase and its money trail.

The legacy credits-only endpoint remains available for historical data and for
an operator who deliberately chooses not to touch money documents.  This
module is the strict, document-adjusting path: it starts from one explicit
purchase bridge, locks every related record, writes the negative credit
movement, credit note, payment refund and refund bridge in one transaction, and
records an idempotency result before the request returns.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import json
from typing import Any, Mapping
import uuid

from ..audit import record_audit_event
from ..db import fetch_all, fetch_one
from . import billing
from .credit_settlements import _operation_start, payload_hash


class CreditRefundError(RuntimeError):
    """A refund cannot be applied without violating a ledger invariant."""


class CreditRefundConflict(CreditRefundError):
    """The idempotency key is active or already describes another request."""


def _uuid(value: Any, label: str, *, required: bool = False) -> str | None:
    text = str(value or "").strip()
    if not text:
        if required:
            raise CreditRefundError(f"{label} is required.")
        return None
    try:
        return str(uuid.UUID(text))
    except (ValueError, AttributeError, TypeError) as exc:
        raise CreditRefundError(f"{label} must be a UUID.") from exc


def _credits(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"))
    except Exception as exc:  # Decimal has several concrete exception types.
        raise CreditRefundError("credits must be a positive decimal.") from exc
    if amount <= 0 or amount.as_tuple().exponent < -2:
        raise CreditRefundError("credits must be a positive decimal with at most two decimals.")
    return amount


def _cents(value: Any) -> int:
    if isinstance(value, bool):
        raise CreditRefundError("amountCents must be a non-negative integer.")
    try:
        amount = int(value)
    except (TypeError, ValueError) as exc:
        raise CreditRefundError("amountCents must be a non-negative integer.") from exc
    if str(value).strip() != str(amount) or amount < 0:
        raise CreditRefundError("amountCents must be a non-negative integer.")
    return amount


def _strict_bool(value: Any, label: str, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise CreditRefundError(f"{label} must be true or false.")


def _finish_operation(conn, tenant_id: str, request_id: str, result: Mapping[str, Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE financial_operation_requests
               SET status = 'succeeded', result = %s::jsonb,
                   credit_transaction_id = %s,
                   payment_id = %s,
                   credit_note_id = %s,
                   refund_id = %s,
                   updated_at = now(), completed_at = now()
             WHERE tenant_id = %s AND request_id = %s
               AND operation_kind = 'credit_refund'
            """,
            (
                json.dumps(dict(result), ensure_ascii=False),
                result.get("refundTransactionId"),
                result.get("paymentId"),
                result.get("creditNoteId"),
                result.get("refundId"),
                tenant_id,
                request_id,
            ),
        )


def refundable_purchases(conn, tenant_id: str, student_id: str) -> list[dict[str, Any]]:
    """Return explicit purchase sources without exposing another tenant's data."""

    student_id = _uuid(student_id, "studentId", required=True)
    rows = fetch_all(
        conn,
        """
        SELECT ct.id AS source_transaction_id,
               ct.amount::numeric AS purchased_credits,
               ct.fee_aud_cents AS source_fee_aud_cents,
               ct.occurred_at,
               l.invoice_id, l.invoice_line_id, l.payment_id,
               i.number AS invoice_number, i.status AS invoice_status,
               i.total_cents AS invoice_total_cents,
               il.total_cents AS line_total_cents,
               il.tax_cents AS line_tax_cents,
               il.total_cents - il.tax_cents AS line_net_cents,
               p.amount_cents AS payment_amount_cents,
               p.refunded_cents AS payment_refunded_cents,
               p.status AS payment_status,
               COALESCE(rf.refunded_credits, 0)::numeric AS refunded_credits,
               COALESCE(rf.refunded_amount_cents, 0)::bigint AS refunded_amount_cents,
               COALESCE(rf.refund_count, 0)::integer AS refund_count
          FROM credit_transactions ct
          LEFT JOIN credit_financial_links l
            ON l.tenant_id = ct.tenant_id
           AND l.credit_transaction_id = ct.id
           AND l.related_credit_transaction_id IS NULL
          LEFT JOIN invoices i
            ON i.tenant_id = l.tenant_id AND i.id = l.invoice_id
          LEFT JOIN invoice_lines il
            ON il.tenant_id = l.tenant_id AND il.id = l.invoice_line_id
          LEFT JOIN payments p
            ON p.tenant_id = l.tenant_id AND p.id = l.payment_id
          LEFT JOIN (
              SELECT COALESCE(rt.source_credit_transaction_id,
                              rl.related_credit_transaction_id) AS source_transaction_id,
                     SUM((-rt.amount)::numeric) AS refunded_credits,
                     SUM(CASE WHEN r.amount_cents IS NOT NULL
                              THEN r.amount_cents
                              ELSE GREATEST(0, -rt.fee_aud_cents)
                         END) AS refunded_amount_cents,
                     COUNT(*) AS refund_count
                FROM credit_transactions rt
                LEFT JOIN credit_financial_links rl
                  ON rl.tenant_id = rt.tenant_id
                 AND rl.credit_transaction_id = rt.id
                 AND rl.related_credit_transaction_id IS NOT NULL
                LEFT JOIN refunds r
                  ON r.tenant_id = rl.tenant_id AND r.id = rl.refund_id
               WHERE rt.tenant_id = %s
                 AND rt.transaction_type = 'refund'
                 AND (rt.source_credit_transaction_id IS NOT NULL
                      OR rl.related_credit_transaction_id IS NOT NULL)
               GROUP BY COALESCE(rt.source_credit_transaction_id,
                                 rl.related_credit_transaction_id)
          ) rf ON rf.source_transaction_id = ct.id
         WHERE ct.tenant_id = %s
           AND ct.student_id = %s
           AND ct.transaction_type = 'purchase'
         ORDER BY ct.occurred_at DESC, ct.id DESC
        """,
        (tenant_id, tenant_id, student_id),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        purchased_credits = Decimal(str(row["purchased_credits"] or 0)).quantize(Decimal("0.01"))
        refunded_credits = Decimal(str(row["refunded_credits"] or 0)).quantize(Decimal("0.01"))
        line_total = int(row["line_total_cents"] or row["source_fee_aud_cents"] or 0)
        refunded_amount = int(row["refunded_amount_cents"] or 0)
        payment_available = (
            int(row["payment_amount_cents"] or 0)
            - int(row["payment_refunded_cents"] or 0)
            if row["payment_id"] else 0
        )
        if row["invoice_id"]:
            available_amount = max(0, min(line_total - refunded_amount, payment_available))
        else:
            available_amount = max(0, line_total - refunded_amount)
        available_credits = max(Decimal("0"), purchased_credits - refunded_credits)
        complete_bridge = bool(
            row["invoice_id"] and row["invoice_line_id"] and row["payment_id"]
            and row["payment_status"] in {"succeeded", "refunded"}
        )
        out.append({
            "sourceTransactionId": str(row["source_transaction_id"]),
            "purchasedCredits": format(purchased_credits, "f"),
            "refundedCredits": format(refunded_credits, "f"),
            "availableCredits": format(available_credits, "f"),
            "amountCents": line_total,
            "refundedAmountCents": refunded_amount,
            "availableAmountCents": available_amount,
            "invoiceId": str(row["invoice_id"]) if row["invoice_id"] else None,
            "invoiceLineId": str(row["invoice_line_id"]) if row["invoice_line_id"] else None,
            "invoiceNumber": row["invoice_number"],
            "invoiceStatus": row["invoice_status"],
            "paymentId": str(row["payment_id"]) if row["payment_id"] else None,
            "paymentStatus": row["payment_status"],
            "paymentAmountCents": int(row["payment_amount_cents"] or 0),
            "paymentRefundedCents": int(row["payment_refunded_cents"] or 0),
            "refundCount": int(row["refund_count"] or 0),
            "syncAvailable": bool(complete_bridge and available_amount > 0 and available_credits > 0),
            "occurredAt": row["occurred_at"].isoformat() if row["occurred_at"] else None,
        })
    return out


def _refund_tax_split(
    amount_cents: int,
    remaining_net_cents: int,
    remaining_tax_cents: int,
    original_total_cents: int,
    original_net_cents: int,
) -> tuple[int, int]:
    """Allocate a partial gross refund without exceeding original tax/net."""

    if amount_cents <= 0 or amount_cents > remaining_net_cents + remaining_tax_cents:
        raise CreditRefundError("Refund amount exceeds the remaining invoice line.")
    remaining_total = remaining_net_cents + remaining_tax_cents
    if amount_cents == remaining_total:
        return remaining_net_cents, remaining_tax_cents
    if original_total_cents <= 0:
        raise CreditRefundError("The original invoice line has no refundable total.")
    net = int(
        (Decimal(original_net_cents) * Decimal(amount_cents) / Decimal(original_total_cents)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )
    net = max(0, min(net, remaining_net_cents))
    tax = amount_cents - net
    if tax > remaining_tax_cents:
        tax = remaining_tax_cents
        net = amount_cents - tax
    if net > remaining_net_cents or tax < 0:
        raise CreditRefundError("Refund tax allocation exceeds the original line remainder.")
    return net, tax


def create_credit_refund(
    conn,
    tenant_id: str,
    student_id: str,
    payload: Mapping[str, Any],
    *,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Reverse one bridged purchase and its payment atomically."""

    if not isinstance(payload, Mapping):
        raise CreditRefundError("A JSON object is required.")
    allowed = {"requestId", "sourceCreditTransactionId", "credits", "amountCents", "paymentMethod", "reason", "billing"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise CreditRefundError(f"Unknown refund fields: {', '.join(unknown)}")
    request_id = _uuid(payload.get("requestId"), "requestId", required=True)
    student_id = _uuid(student_id, "studentId", required=True)
    source_tx_id = _uuid(payload.get("sourceCreditTransactionId"), "sourceCreditTransactionId", required=True)
    credits = _credits(payload.get("credits"))
    amount_cents = _cents(payload.get("amountCents"))
    payment_method = str(payload.get("paymentMethod") or "bank_transfer").strip()
    reason = str(payload.get("reason") or "").strip()[:500]
    if not reason:
        raise CreditRefundError("A refund reason is required.")
    billing_payload = payload.get("billing") or {}
    if not isinstance(billing_payload, Mapping):
        raise CreditRefundError("billing must be an object.")
    if set(billing_payload) - {"adjustDocuments"}:
        raise CreditRefundError("Unknown billing refund fields.")
    adjust_documents = _strict_bool(
        billing_payload.get("adjustDocuments"), "billing.adjustDocuments", default=True
    )
    digest = payload_hash({**dict(payload), "studentId": student_id})
    operation, replayed = _operation_start(
        conn, tenant_id, request_id, "credit_refund", digest
    )
    if replayed:
        return operation

    # Lock in a deterministic order: source purchase → bridge → payment → account.
    source = fetch_one(
        conn,
        """
        SELECT id, student_id, account_id, amount::numeric AS amount,
               fee_aud_cents,
               balance_after::numeric AS balance_after
          FROM credit_transactions
         WHERE tenant_id = %s AND id = %s AND transaction_type = 'purchase'
         FOR UPDATE
        """,
        (tenant_id, source_tx_id),
    )
    if not source or str(source["student_id"]) != student_id:
        raise CreditRefundError("The original purchase was not found.")

    # Credits-only refunds use the same source-aware endpoint. They never
    # create or mutate an invoice/payment, but still participate in the source
    # aggregate and write provenance directly on the refund row.
    if not adjust_documents:
        prior = fetch_one(
            conn,
            """
            SELECT COALESCE(SUM((-rt.amount)::numeric), 0)::numeric AS refunded_credits,
                   COALESCE(SUM(GREATEST(0, -rt.fee_aud_cents)), 0)::bigint
                       AS refunded_amount_cents
              FROM credit_transactions rt
              LEFT JOIN credit_financial_links rl
                ON rl.tenant_id = rt.tenant_id
               AND rl.credit_transaction_id = rt.id
               AND rl.related_credit_transaction_id IS NOT NULL
             WHERE rt.tenant_id = %s
               AND rt.transaction_type = 'refund'
               AND COALESCE(rt.source_credit_transaction_id,
                            rl.related_credit_transaction_id) = %s
            """,
            (tenant_id, source_tx_id),
        ) or {}
        purchased_credits = Decimal(str(source["amount"] or 0)).quantize(Decimal("0.01"))
        refunded_credits = Decimal(str(prior.get("refunded_credits") or 0)).quantize(Decimal("0.01"))
        available_credits = purchased_credits - refunded_credits
        original_amount = max(0, int(source["fee_aud_cents"] or 0))
        refunded_amount = int(prior.get("refunded_amount_cents") or 0)
        available_amount = max(0, original_amount - refunded_amount)
        if credits > available_credits:
            raise CreditRefundError(
                f"Refundable credits are {format(max(available_credits, Decimal('0')), 'f')}."
            )
        if amount_cents > available_amount:
            raise CreditRefundError(f"Refundable amount is {available_amount} cents.")

        account = fetch_one(
            conn,
            """
            SELECT id, balance::numeric AS balance
              FROM credit_accounts
             WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
             FOR UPDATE
            """,
            (tenant_id, student_id),
        )
        if not account:
            raise CreditRefundError("The student's credit account was not found.")
        balance = Decimal(str(account["balance"] or 0)).quantize(Decimal("0.01"))
        if credits > balance:
            raise CreditRefundError("Refundable credits exceed the student's current balance.")
        new_balance = balance - credits
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (tenant_id, student_id, account_id, actor_user_id, transaction_type,
                     source_credit_transaction_id, amount, balance_after, fee_aud_cents, note)
                VALUES (%s, %s, %s, %s, 'refund', %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant_id, student_id, account["id"], actor_user_id, source_tx_id,
                    -credits, new_balance, -amount_cents, reason,
                ),
            )
            refund_transaction_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                UPDATE credit_accounts SET balance = %s, updated_at = now()
                 WHERE tenant_id = %s AND id = %s
                """,
                (new_balance, tenant_id, account["id"]),
            )
        result = {
            "requestId": request_id,
            "sourceTransactionId": source_tx_id,
            "refundTransactionId": refund_transaction_id,
            "invoiceId": None,
            "invoiceLineId": None,
            "creditNoteId": None,
            "creditNoteLineId": None,
            "creditNoteNumber": None,
            "paymentId": None,
            "refundId": None,
            "financialLinkId": None,
            "creditsRefunded": format(credits, "f"),
            "amountRefundedCents": amount_cents,
            "netRefundedCents": 0,
            "taxRefundedCents": 0,
            "newBalance": format(new_balance, "f"),
            "adjustDocuments": False,
            "replayed": False,
        }
        _finish_operation(conn, tenant_id, request_id, result)
        record_audit_event(
            conn,
            action="credit.refunded",
            resource_type="credit_transaction",
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            resource_id=refund_transaction_id,
            metadata_json=json.dumps(
                {
                    "requestId": request_id,
                    "sourceTransactionId": source_tx_id,
                    "amountCents": amount_cents,
                    "adjustDocuments": False,
                },
                ensure_ascii=False,
            ),
        )
        return result

    link = fetch_one(
        conn,
        """
        SELECT l.id, l.invoice_id, l.invoice_line_id, l.payment_id,
               i.billing_account_id, i.status AS invoice_status,
               i.amount_credited_cents,
               i.number AS invoice_number, i.supplier_snapshot, i.recipient_snapshot,
               il.total_cents, il.tax_cents, il.total_cents - il.tax_cents AS net_cents,
               p.amount_cents AS payment_amount_cents,
               p.refunded_cents AS payment_refunded_cents,
               p.status AS payment_status
          FROM credit_financial_links l
          JOIN invoices i ON i.tenant_id = l.tenant_id AND i.id = l.invoice_id
          JOIN invoice_lines il ON il.tenant_id = l.tenant_id AND il.id = l.invoice_line_id
          JOIN payments p ON p.tenant_id = l.tenant_id AND p.id = l.payment_id
         WHERE l.tenant_id = %s AND l.credit_transaction_id = %s
           AND l.related_credit_transaction_id IS NULL
         FOR UPDATE OF l, i, il, p
        """,
        (tenant_id, source_tx_id),
    )
    if not link or not link["payment_id"]:
        raise CreditRefundError("This purchase has no complete invoice/payment bridge; documents were not changed.")
    if link["invoice_status"] not in {"issued", "part_paid", "paid"}:
        raise CreditRefundError("The original invoice is not an issued, refundable document.")
    if not link["supplier_snapshot"] or not link["recipient_snapshot"]:
        raise CreditRefundError("The original invoice has no immutable identity snapshot.")
    if link["payment_status"] not in {"succeeded", "refunded"}:
        raise CreditRefundError("The original payment is not refundable.")

    payment = fetch_one(
        conn,
        """
        SELECT id, amount_cents, refunded_cents, status
          FROM payments
         WHERE tenant_id = %s AND id = %s
         FOR UPDATE
        """,
        (tenant_id, link["payment_id"]),
    )
    allocation = fetch_one(
        conn,
        """
        SELECT id, amount_cents
          FROM payment_allocations
         WHERE tenant_id = %s AND payment_id = %s AND invoice_id = %s
         FOR UPDATE
        """,
        (tenant_id, link["payment_id"], link["invoice_id"]),
    )
    if not payment or not allocation:
        raise CreditRefundError("The original payment is no longer allocated to its invoice.")

    prior = fetch_one(
        conn,
        """
        SELECT COALESCE(SUM((-rt.amount)::numeric), 0)::numeric AS refunded_credits,
               COALESCE(SUM(CASE WHEN r.amount_cents IS NOT NULL
                                 THEN r.amount_cents
                                 ELSE GREATEST(0, -rt.fee_aud_cents)
                            END), 0)::bigint AS refunded_amount_cents,
               COALESCE(SUM(cnl.total_cents - cnl.tax_cents), 0)::bigint AS refunded_net_cents,
               COALESCE(SUM(cnl.tax_cents), 0)::bigint AS refunded_tax_cents
          FROM credit_transactions rt
          LEFT JOIN credit_financial_links rl
            ON rl.tenant_id = rt.tenant_id
           AND rl.credit_transaction_id = rt.id
           AND rl.related_credit_transaction_id IS NOT NULL
          LEFT JOIN refunds r ON r.tenant_id = rl.tenant_id AND r.id = rl.refund_id
          LEFT JOIN credit_note_lines cnl
            ON cnl.tenant_id = rl.tenant_id AND cnl.credit_note_id = rl.credit_note_id
         WHERE rt.tenant_id = %s
           AND rt.transaction_type = 'refund'
           AND COALESCE(rt.source_credit_transaction_id,
                        rl.related_credit_transaction_id) = %s
        """,
        (tenant_id, source_tx_id),
    ) or {}
    purchased_credits = Decimal(str(source["amount"] or 0)).quantize(Decimal("0.01"))
    refunded_credits = Decimal(str(prior.get("refunded_credits") or 0)).quantize(Decimal("0.01"))
    available_credits = purchased_credits - refunded_credits
    original_total = int(link["total_cents"] or 0)
    original_tax = int(link["tax_cents"] or 0)
    original_net = int(link["net_cents"] or 0)
    refunded_amount = int(prior.get("refunded_amount_cents") or 0)
    remaining_line_amount = original_total - refunded_amount
    remaining_payment = int(payment["amount_cents"]) - int(payment["refunded_cents"])
    available_amount = min(remaining_line_amount, int(allocation["amount_cents"]), remaining_payment)
    if credits > available_credits:
        raise CreditRefundError(f"Refundable credits are {format(max(available_credits, Decimal('0')), 'f')}.")
    if amount_cents > available_amount:
        raise CreditRefundError(f"Refundable amount is {available_amount} cents.")

    account = fetch_one(
        conn,
        """
        SELECT id, balance::numeric AS balance
          FROM credit_accounts
         WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
         FOR UPDATE
        """,
        (tenant_id, student_id),
    )
    if not account:
        raise CreditRefundError("The student's credit account was not found.")
    balance = Decimal(str(account["balance"] or 0)).quantize(Decimal("0.01"))
    if credits > balance:
        raise CreditRefundError("Refundable credits exceed the student's current balance.")
    new_balance = balance - credits
    net_refund, tax_refund = _refund_tax_split(
        amount_cents,
        max(0, original_net - int(prior.get("refunded_net_cents") or 0)),
        max(0, original_tax - int(prior.get("refunded_tax_cents") or 0)),
        original_total,
        original_net,
    )
    if net_refund + tax_refund != amount_cents:
        raise CreditRefundError("Refund tax arithmetic did not balance to the requested amount.")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO credit_transactions
                (tenant_id, student_id, account_id, actor_user_id, transaction_type,
                 source_credit_transaction_id, amount, balance_after, fee_aud_cents, note)
            VALUES (%s, %s, %s, %s, 'refund', %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                tenant_id, student_id, account["id"], actor_user_id, source_tx_id,
                -credits, new_balance, -amount_cents, reason,
            ),
        )
        refund_transaction_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            UPDATE credit_accounts SET balance = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s
            """,
            (new_balance, tenant_id, account["id"]),
        )

        cur.execute(
            """
            INSERT INTO credit_notes
                (tenant_id, billing_account_id, invoice_id, reason,
                 supplier_snapshot, recipient_snapshot, snapshot_schema_version)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            RETURNING id
            """,
            (
                tenant_id, link["billing_account_id"], link["invoice_id"], reason,
                json.dumps(dict(link["supplier_snapshot"]), ensure_ascii=False),
                json.dumps(dict(link["recipient_snapshot"]), ensure_ascii=False),
                billing.SNAPSHOT_SCHEMA_VERSION,
            ),
        )
        credit_note_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO credit_note_lines
                (tenant_id, credit_note_id, description, quantity, unit_price_cents,
                 tax_rate_bp, tax_cents, total_cents)
            SELECT %s, %s, concat('Refund: ', description), 1,
                   %s, tax_rate_bp, %s, %s
              FROM invoice_lines
             WHERE tenant_id = %s AND id = %s
            RETURNING id
            """,
            (tenant_id, credit_note_id, net_refund, tax_refund, amount_cents,
             tenant_id, link["invoice_line_id"]),
        )
        credit_note_line_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            UPDATE credit_notes
               SET number = %s, status = 'issued', issue_date = %s,
                   subtotal_cents = %s, tax_cents = %s, total_cents = %s,
                   issued_at = now(), issued_by_user_id = %s
             WHERE tenant_id = %s AND id = %s AND status = 'draft'
            """,
            (
                billing.next_document_number(conn, tenant_id, "credit_note"),
                date.today(), net_refund, tax_refund, amount_cents,
                actor_user_id, tenant_id, credit_note_id,
            ),
        )
        cur.execute(
            """
            INSERT INTO refunds
                (tenant_id, payment_id, credit_note_id, amount_cents,
                 reason, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant_id, payment["id"], credit_note_id, amount_cents, reason, actor_user_id),
        )
        refund_id = str(cur.fetchone()["id"])

        # The bridge trigger intentionally requires the payment allocation to
        # still exist. Insert the legal evidence first, then release only the
        # amount refunded from this invoice.
        cur.execute(
            """
            INSERT INTO credit_financial_links
                (tenant_id, credit_transaction_id, related_credit_transaction_id,
                 invoice_id, invoice_line_id, payment_id, credit_note_id, refund_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                tenant_id, refund_transaction_id, source_tx_id, link["invoice_id"],
                link["invoice_line_id"], payment["id"], credit_note_id, refund_id,
            ),
        )
        financial_link_id = str(cur.fetchone()["id"])
        # A credit note is an immutable correcting document; the original
        # invoice header remains immutable for identity/amounts, while its
        # mutable settlement column records how much has been credited.  This
        # keeps the generated balance and every export honest after the
        # payment allocation is released below.
        new_credited = int(link["amount_credited_cents"] or 0) + amount_cents
        if new_credited > int(link["total_cents"] or 0):
            raise CreditRefundError("The invoice cannot be credited beyond its total.")
        cur.execute(
            """
            UPDATE invoices
               SET amount_credited_cents = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s
            """,
            (new_credited, tenant_id, link["invoice_id"]),
        )
        new_allocation = int(allocation["amount_cents"]) - amount_cents
        if new_allocation:
            cur.execute(
                "UPDATE payment_allocations SET amount_cents = %s WHERE tenant_id = %s AND id = %s",
                (new_allocation, tenant_id, allocation["id"]),
            )
        else:
            cur.execute(
                "DELETE FROM payment_allocations WHERE tenant_id = %s AND id = %s",
                (tenant_id, allocation["id"]),
            )
        cur.execute(
            """
            UPDATE payments
               SET refunded_cents = refunded_cents + %s,
                   status = CASE WHEN refunded_cents + %s >= amount_cents
                                 THEN 'refunded' ELSE status END
             WHERE tenant_id = %s AND id = %s
            """,
            (amount_cents, amount_cents, tenant_id, payment["id"]),
        )

    billing.record_event(
        conn, tenant_id, link["invoice_id"], "credited", actor_user_id,
        {
            "credit_note_id": credit_note_id,
            "refund_id": refund_id,
            "amount_cents": amount_cents,
            "reason": reason,
        },
    )
    result = {
        "requestId": request_id,
        "sourceTransactionId": source_tx_id,
        "refundTransactionId": refund_transaction_id,
        "invoiceId": str(link["invoice_id"]),
        "invoiceLineId": str(link["invoice_line_id"]),
        "creditNoteId": credit_note_id,
        "creditNoteLineId": credit_note_line_id,
        "creditNoteNumber": fetch_one(
            conn,
            "SELECT number FROM credit_notes WHERE tenant_id = %s AND id = %s",
            (tenant_id, credit_note_id),
        )["number"],
        "paymentId": str(payment["id"]),
        "refundId": refund_id,
        "financialLinkId": financial_link_id,
        "creditsRefunded": format(credits, "f"),
        "amountRefundedCents": amount_cents,
        "netRefundedCents": net_refund,
        "taxRefundedCents": tax_refund,
        "newBalance": format(new_balance, "f"),
        "replayed": False,
    }
    _finish_operation(conn, tenant_id, request_id, result)
    record_audit_event(
        conn,
        action="credit.refunded",
        resource_type="credit_transaction",
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        resource_id=refund_transaction_id,
        metadata_json=json.dumps(
            {
                "requestId": request_id,
                "sourceTransactionId": source_tx_id,
                "creditNoteId": credit_note_id,
                "refundId": refund_id,
                "amountCents": amount_cents,
            },
            ensure_ascii=False,
        ),
    )
    return result
