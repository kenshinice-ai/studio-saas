"""Recording money in, and allocating it to what it paid for.

The platform is not a payment facilitator. Each tenant connects their own
merchant account, the payer completes the transaction on the provider's hosted
page, and what arrives here is a notification that it happened. No card number
reaches this process, which keeps PCI scope at the lightest tier and keeps us
out of the funds flow, the chargeback flow and the licensing that goes with
both.

Providers sit behind one interface because a studio's existing merchant
relationship is not ours to redirect. Stripe is implemented first for reach;
Square exists because a studio already taking payments through it should not
have to change banks to change scheduling software.

Two invariants are enforced by the database rather than here (migration 0035):
a payment can never be allocated to more than it was worth, and an invoice's
paid total is always exactly the sum of its allocations. This module can
therefore allocate without first re-reading and re-checking totals, and a bug
in it becomes a failed transaction rather than a wrong balance.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any, Sequence

from ..db import fetch_all, fetch_one


class PaymentError(RuntimeError):
    """A payment could not be recorded or allocated as asked."""


SUPPORTED_PROVIDERS = ("stripe", "square")

#: Methods the front desk can record by hand. Card and direct debit are absent
#: on purpose: those arrive from a provider, and letting somebody type one in
#: creates a payment with no counterpart in any merchant account.
MANUAL_METHODS = ("bank_transfer", "cash", "other")


@dataclass(frozen=True)
class Allocation:
    invoice_id: str
    amount_cents: int


def record_payment(
    conn,
    tenant_id: str,
    *,
    billing_account_id: str,
    amount_cents: int,
    method: str,
    provider: str | None = None,
    provider_ref: str = "",
    fee_cents: int = 0,
    surcharge_cents: int = 0,
    received_at: Any = None,
    idempotency_key: str | None = None,
    note: str = "",
    recorded_by_user_id: str | None = None,
) -> dict[str, Any]:
    """Record that money arrived.

    ``idempotency_key`` is what makes a retry safe. A double-clicked button, a
    replayed webhook and a retried API call all carry the same key, conflict on
    the unique index, and resolve to the single row that already exists rather
    than to a second payment nobody made.
    """

    if amount_cents <= 0:
        raise PaymentError("A payment must be greater than zero.")
    if method not in MANUAL_METHODS + ("card", "direct_debit"):
        raise PaymentError(f"Unknown payment method: {method}")
    if provider is not None and provider not in SUPPORTED_PROVIDERS:
        raise PaymentError(f"Unknown provider: {provider}")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO payments (
                tenant_id, billing_account_id, method, provider, provider_ref,
                amount_cents, fee_cents, surcharge_cents, received_at,
                idempotency_key, note, recorded_by_user_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, now()), %s, %s, %s)
            ON CONFLICT (tenant_id, idempotency_key) DO NOTHING
            RETURNING id, amount_cents, received_at, status
            """,
            (
                tenant_id, billing_account_id, method, provider, provider_ref,
                amount_cents, fee_cents, surcharge_cents, received_at,
                idempotency_key, note, recorded_by_user_id,
            ),
        )
        row = cur.fetchone()

    if row:
        return row

    # The conflict path: somebody already recorded this exact payment. Return
    # theirs rather than raising, because the caller's intent — "this payment
    # exists" — is satisfied.
    existing = fetch_one(
        conn,
        """
        SELECT id, amount_cents, received_at, status
        FROM payments WHERE tenant_id = %s AND idempotency_key = %s
        """,
        (tenant_id, idempotency_key),
    )
    if not existing:
        raise PaymentError("Payment could not be recorded.")
    return existing


def allocate(
    conn,
    tenant_id: str,
    payment_id: str,
    allocations: Sequence[Allocation],
) -> list[dict[str, Any]]:
    """Apply a payment to one or more invoices.

    The over-allocation check and the invoice total resync both live in database
    triggers, so this is a plain insert. A caller that tries to spend the same
    money twice gets a constraint violation, not a silently wrong ledger.
    """

    written: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for item in allocations:
            if item.amount_cents <= 0:
                raise PaymentError("An allocation must be greater than zero.")
            cur.execute(
                """
                INSERT INTO payment_allocations (tenant_id, payment_id, invoice_id, amount_cents)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (payment_id, invoice_id) DO UPDATE
                   SET amount_cents = EXCLUDED.amount_cents
                RETURNING id, invoice_id, amount_cents
                """,
                (tenant_id, payment_id, item.invoice_id, item.amount_cents),
            )
            written.append(cur.fetchone())

    # An invoice's history recorded exactly two things — issued and voided — so
    # "这张单发生过什么" answered "issued" for a document that had since been paid
    # in full. Money arriving is the event a studio is most likely to be asked
    # about ("we paid that in July"), and it was the one thing the ledger did not
    # keep. Read the status back AFTER the insert, because the invoice totals are
    # resynced by a trigger: this records what the invoice became, not what the
    # caller hoped it would become.
    from .billing import record_event

    for row in written:
        state = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, str(row["invoice_id"])),
        ) or {}
        record_event(
            conn, tenant_id, str(row["invoice_id"]),
            "paid" if state.get("status") == "paid" else "part_paid",
            None,
            {
                "amount_cents": int(row["amount_cents"]),
                "balance_cents": int(state.get("balance_cents") or 0),
                "payment_id": str(payment_id),
            },
        )
    return written


def auto_allocate(
    conn,
    tenant_id: str,
    payment_id: str,
    prefer_invoice_id: str | None = None,
) -> list[dict[str, Any]]:
    """Spend a payment against the account's oldest unpaid invoices first.

    Oldest-first is the convention families and accountants both expect, and it
    is the one that keeps the ageing report honest: money should retire the debt
    that has been outstanding longest, not the one that is easiest to clear.

    Anything left over stays unallocated and shows up as credit on the account,
    which is the correct representation of an overpayment — it is still the
    family's money.
    """

    payment = fetch_one(
        conn,
        """
        SELECT p.id, p.billing_account_id,
               p.amount_cents - p.refunded_cents
                 - COALESCE((SELECT SUM(amount_cents) FROM payment_allocations
                              WHERE payment_id = p.id), 0) AS unallocated_cents
        FROM payments p
        WHERE p.tenant_id = %s AND p.id = %s AND p.status = 'succeeded'
        """,
        (tenant_id, payment_id),
    )
    if not payment:
        raise PaymentError("Payment not found.")

    remaining = int(payment["unallocated_cents"] or 0)
    if remaining <= 0:
        return []

    # `prefer_invoice_id` is what an operator means when they press 登记收款 while
    # looking at ONE invoice. Without it the money went to the oldest open debt —
    # correct as a default, and wrong as an answer to "record payment for THIS
    # invoice". On production it read as the button doing nothing: the invoice on
    # screen never changed, so the operator pressed again, and each press paid
    # down a different older invoice. Oldest-first still governs whatever is left
    # over, because an overpayment is still the family's money.
    open_invoices = fetch_all(
        conn,
        """
        SELECT id, balance_cents
        FROM invoices
        WHERE tenant_id = %s AND billing_account_id = %s
          AND status IN ('issued', 'part_paid') AND balance_cents > 0
        ORDER BY (id = %s) DESC, due_date NULLS LAST, issue_date, number
        """,
        (tenant_id, payment["billing_account_id"], prefer_invoice_id),
    )

    plan: list[Allocation] = []
    for invoice in open_invoices:
        if remaining <= 0:
            break
        take = min(remaining, int(invoice["balance_cents"]))
        plan.append(Allocation(invoice_id=str(invoice["id"]), amount_cents=take))
        remaining -= take

    return allocate(conn, tenant_id, payment_id, plan) if plan else []


def refund(
    conn,
    tenant_id: str,
    payment_id: str,
    *,
    amount_cents: int,
    reason: str = "",
    provider_ref: str = "",
    credit_note_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Record money going back, and keep the invoice arithmetic consistent.

    Refunding releases allocations from the newest invoice backwards, which is
    the mirror of oldest-first allocation: the debt that was cleared most
    recently is the one that reopens.
    """

    payment = fetch_one(
        conn,
        """
        SELECT amount_cents, refunded_cents
        FROM payments WHERE tenant_id = %s AND id = %s FOR UPDATE
        """,
        (tenant_id, payment_id),
    )
    if not payment:
        raise PaymentError("Payment not found.")
    available = int(payment["amount_cents"]) - int(payment["refunded_cents"])
    if amount_cents <= 0 or amount_cents > available:
        raise PaymentError(f"Refundable amount is {available} cents.")

    remaining = amount_cents
    allocations = fetch_all(
        conn,
        """
        SELECT id, invoice_id, amount_cents
        FROM payment_allocations
        WHERE tenant_id = %s AND payment_id = %s
        ORDER BY created_at DESC
        """,
        (tenant_id, payment_id),
    )
    with conn.cursor() as cur:
        touched_invoices: set[str] = set()
        for item in allocations:
            if remaining <= 0:
                break
            take = min(remaining, int(item["amount_cents"]))
            new_amount = int(item["amount_cents"]) - take
            if new_amount == 0:
                cur.execute("DELETE FROM payment_allocations WHERE id = %s", (item["id"],))
            else:
                cur.execute(
                    "UPDATE payment_allocations SET amount_cents = %s WHERE id = %s",
                    (new_amount, item["id"]),
                )
            remaining -= take
            touched_invoices.add(str(item["invoice_id"]))

        cur.execute(
            """
            UPDATE payments
               SET refunded_cents = refunded_cents + %s,
                   status = CASE WHEN refunded_cents + %s >= amount_cents
                                 THEN 'refunded' ELSE status END
             WHERE tenant_id = %s AND id = %s
            """,
            (amount_cents, amount_cents, tenant_id, payment_id),
        )
        cur.execute(
            """
            INSERT INTO refunds (tenant_id, payment_id, credit_note_id, amount_cents,
                                 provider_ref, reason, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, amount_cents
            """,
            (tenant_id, payment_id, credit_note_id, amount_cents, provider_ref,
             reason, actor_user_id),
        )
        refund_row = cur.fetchone()

    # A refund puts an invoice back into debt, and an invoice whose history stops
    # at "issued" cannot answer why. Recorded after the cursor closes so the
    # trigger-maintained totals are the ones being read.
    from .billing import record_event

    for invoice_id in sorted(touched_invoices):
        state = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, invoice_id),
        ) or {}
        record_event(
            conn, tenant_id, invoice_id, "refunded", actor_user_id,
            {"balance_cents": int(state.get("balance_cents") or 0),
             "payment_id": str(payment_id), "reason": reason or ""},
        )
    return refund_row


# ── provider webhooks ────────────────────────────────────────────────────


def verify_stripe_signature(payload: bytes, header: str, secret: str, *, tolerance: int = 300) -> bool:
    """Check a Stripe webhook signature.

    Compared with :func:`hmac.compare_digest` rather than ``==`` so the check
    does not leak, through timing, how much of a forged signature was right.
    """

    import time

    if not header or not secret:
        return False
    parts = dict(
        piece.split("=", 1) for piece in header.split(",") if "=" in piece
    )
    timestamp = parts.get("t")
    signature = parts.get("v1")
    if not timestamp or not signature:
        return False
    try:
        if abs(time.time() - int(timestamp)) > tolerance:
            return False
    except ValueError:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def claim_provider_event(
    conn,
    *,
    provider: str,
    event_id: str,
    tenant_id: str | None,
    event_type: str,
    payload: dict[str, Any],
) -> bool:
    """Take ownership of an inbound provider event exactly once.

    Returns ``True`` when this call is the first to see the event and should go
    on to process it, and ``False`` when it has been seen before — the correct
    response to a redelivery is to acknowledge it and do nothing, because the
    work was already done.
    """

    import json as _json

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO payment_provider_events
                (provider, event_id, tenant_id, event_type, payload)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (provider, event_id) DO NOTHING
            RETURNING id
            """,
            (provider, event_id, tenant_id, event_type, _json.dumps(payload)),
        )
        return cur.fetchone() is not None


def mark_event_processed(conn, provider: str, event_id: str, error: str = "") -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE payment_provider_events
               SET processed_at = now(), error_message = %s
             WHERE provider = %s AND event_id = %s
            """,
            (error, provider, event_id),
        )


def new_idempotency_key(prefix: str = "pay") -> str:
    """A key for callers that have no natural one of their own."""

    return f"{prefix}_{secrets.token_urlsafe(18)}"
