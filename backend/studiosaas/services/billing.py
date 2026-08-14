"""Invoices, credit notes, statements and receivables ageing.

Three rules run through everything in this module.

**Money is integer cents.** No float ever touches an amount. Tax is computed
with :class:`~decimal.Decimal` and ``ROUND_HALF_UP``, not with :func:`round`,
because Python rounds halves to even — ``round(2.5)`` is ``2`` — and an invoice
that disagrees with the accountant's arithmetic by one cent costs more to
explain than it did to compute.

**An issued invoice is immutable.** The database enforces it with a trigger
(migration 0034); this module simply never tries. Corrections are credit notes.

**"Overdue" is derived, never stored.** It is a function of ``due_date`` and the
clock, so it is computed at read time. A stored flag would need a nightly job to
stay true and would be wrong for everybody who looked between runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Sequence

from ..db import fetch_all, fetch_one


class BillingError(RuntimeError):
    """A billing rule was violated in a way the caller should hear about."""


# ── arithmetic ───────────────────────────────────────────────────────────


def line_amounts(
    quantity: Decimal | str | int | float,
    unit_price_cents: int,
    tax_rate_bp: int,
) -> tuple[int, int, int]:
    """Compute one invoice line.

    Args:
        quantity: How many, as a decimal with up to two places.
        unit_price_cents: Price of one, in cents, tax exclusive.
        tax_rate_bp: Tax rate in basis points — 10% GST is ``1000``.

    Returns:
        ``(net_cents, tax_cents, total_cents)``, all integers, where
        ``total_cents == net_cents + tax_cents``.

    Rounding happens once, on the tax of the whole line. Rounding per unit and
    multiplying afterwards drifts on quantities like 3 × $33.33, which is how
    an invoice ends up a cent away from the quote that produced it.
    """

    qty = Decimal(str(quantity))
    if qty <= 0:
        raise BillingError("Quantity must be greater than zero.")
    if unit_price_cents < 0:
        raise BillingError("Unit price cannot be negative.")
    if not 0 <= tax_rate_bp <= 10000:
        raise BillingError("Tax rate must be between 0 and 10000 basis points.")

    net = (qty * Decimal(unit_price_cents)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    tax = (net * Decimal(tax_rate_bp) / Decimal(10000)).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return int(net), int(tax), int(net + tax)


def totals_from_lines(lines: Iterable[dict[str, Any]]) -> tuple[int, int, int]:
    """Sum a set of already-computed lines into invoice totals."""

    subtotal = sum(int(line["net_cents"]) for line in lines)
    tax = sum(int(line["tax_cents"]) for line in lines)
    return subtotal, tax, subtotal + tax


# ── document numbering ───────────────────────────────────────────────────


def next_document_number(conn, tenant_id: str, kind: str = "invoice") -> str:
    """Allocate the next number for a tenant, without gaps.

    A Postgres sequence is the wrong tool here. Sequences keep counting through
    a rolled-back transaction, so a failed issue attempt burns a number and
    leaves a hole that somebody eventually has to account for. A counter row
    taken with ``UPDATE ... RETURNING`` inside the issuing transaction rolls back
    with everything else.

    The cost is that issuing serialises per tenant. At studio volume — tens of
    invoices in a burst at term start — that lock is never contended long enough
    to notice, and gapless numbering is worth more than the concurrency.
    """

    if kind not in {"invoice", "credit_note"}:
        raise BillingError(f"Unknown document kind: {kind}")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO document_number_sequences (tenant_id, kind, prefix, next_value)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (tenant_id, kind) DO NOTHING
            """,
            (tenant_id, kind, "INV-" if kind == "invoice" else "CN-"),
        )
        cur.execute(
            """
            UPDATE document_number_sequences
               SET next_value = next_value + 1, updated_at = now()
             WHERE tenant_id = %s AND kind = %s
            RETURNING prefix, next_value - 1 AS allocated
            """,
            (tenant_id, kind),
        )
        row = cur.fetchone()
    if not row:
        raise BillingError("Could not allocate a document number.")
    return f"{row['prefix']}{int(row['allocated']):04d}"


# ── who is issuing ───────────────────────────────────────────────────────


#: A studio that has never opened the settings page has no row, which is a
#: different state from a row full of blanks: "we never asked" versus "they
#: left it empty". Callers need to tell those apart, so the default carries
#: ``configured: False`` rather than pretending to be saved data.
BILLING_IDENTITY_FIELDS = (
    "legal_name", "trading_name", "abn", "gst_registered",
    "address_line1", "address_line2", "suburb", "state", "postcode", "country",
    "contact_email", "contact_phone", "website",
    "bank_account_name", "bank_bsb", "bank_account_no", "payment_note",
)


def billing_identity(conn, tenant_id: str) -> dict[str, Any]:
    """The studio's own details, as they belong on an invoice."""

    row = fetch_one(
        conn,
        f"SELECT {', '.join(BILLING_IDENTITY_FIELDS)} FROM tenant_billing_identity "
        "WHERE tenant_id = %s",
        (tenant_id,),
    )
    if not row:
        blank = {field: "" for field in BILLING_IDENTITY_FIELDS}
        blank["gst_registered"] = False
        blank["country"] = "Australia"
        return {**blank, "configured": False}
    return {**row, "configured": True}


def save_billing_identity(conn, tenant_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Upsert the issuing identity, keeping anything the caller did not send."""

    current = billing_identity(conn, tenant_id)
    merged = {field: values.get(field, current[field]) for field in BILLING_IDENTITY_FIELDS}
    merged["gst_registered"] = bool(merged["gst_registered"])
    merged["abn"] = str(merged["abn"] or "").strip()

    # Mirrors the CHECK constraint so the studio gets a sentence rather than a
    # constraint violation. The database still has the last word.
    if merged["gst_registered"] and not merged["abn"]:
        raise BillingError(
            "A GST-registered studio has to record its ABN — without it the GST "
            "on your invoices is not claimable by the family or their accountant."
        )

    columns = ", ".join(BILLING_IDENTITY_FIELDS)
    placeholders = ", ".join(["%s"] * len(BILLING_IDENTITY_FIELDS))
    updates = ", ".join(f"{field} = EXCLUDED.{field}" for field in BILLING_IDENTITY_FIELDS)
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO tenant_billing_identity (tenant_id, {columns})
            VALUES (%s, {placeholders})
            ON CONFLICT (tenant_id) DO UPDATE SET {updates}, updated_at = now()
            RETURNING {columns}
            """,
            (tenant_id, *[merged[field] for field in BILLING_IDENTITY_FIELDS]),
        )
        saved = cur.fetchone()
    return {**saved, "configured": True}


def issuing_blockers(conn, tenant_id: str, invoice_id: str) -> list[dict[str, str]]:
    """What would make this document invalid if it went out now.

    Returns a list rather than the first problem, for the same reason the Xero
    gate does: a studio that fixes one blocker and is immediately shown another
    stops believing the screen.

    Only conditions that make the *document* wrong are in here. A missing
    address is untidy; a GST line with no supplier ABN is a document the
    customer's accountant will reject, and it is the product's fault for
    letting it out.
    """

    identity = billing_identity(conn, tenant_id)
    taxed = fetch_one(
        conn,
        "SELECT COALESCE(SUM(tax_cents), 0) AS tax FROM invoice_lines "
        "WHERE tenant_id = %s AND invoice_id = %s",
        (tenant_id, invoice_id),
    ) or {}
    charges_gst = int(taxed.get("tax") or 0) > 0

    blockers: list[dict[str, str]] = []
    if not (identity["legal_name"] or identity["trading_name"]):
        blockers.append({
            "code": "no_supplier_name",
            "message": "The invoice does not say who is issuing it. "
                       "Add your studio's legal or trading name in Settings.",
        })
    if charges_gst and not identity["abn"]:
        blockers.append({
            "code": "gst_without_abn",
            "message": "This invoice charges GST but your ABN is missing, so the "
                       "family cannot claim it. Add your ABN in Settings.",
        })
    if charges_gst and not identity["gst_registered"]:
        blockers.append({
            "code": "gst_without_registration",
            "message": "This invoice charges GST but the studio is not marked as "
                       "GST-registered. Either register the setting or remove the "
                       "tax rate from the lines.",
        })
    return blockers


# ── invoice lifecycle ────────────────────────────────────────────────────


def recalculate_totals(conn, tenant_id: str, invoice_id: str) -> dict[str, int]:
    """Re-sum a draft invoice from its lines and store the result.

    Only meaningful while the invoice is a draft; the trigger rejects the write
    afterwards, which is the intended behaviour rather than an edge case to work
    around.
    """

    row = fetch_one(
        conn,
        """
        SELECT COALESCE(SUM(total_cents - tax_cents), 0) AS subtotal_cents,
               COALESCE(SUM(tax_cents), 0)               AS tax_cents,
               COALESCE(SUM(total_cents), 0)             AS total_cents
        FROM invoice_lines
        WHERE tenant_id = %s AND invoice_id = %s
        """,
        (tenant_id, invoice_id),
    ) or {"subtotal_cents": 0, "tax_cents": 0, "total_cents": 0}

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE invoices
               SET subtotal_cents = %s, tax_cents = %s, total_cents = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status = 'draft'
            """,
            (
                row["subtotal_cents"],
                row["tax_cents"],
                row["total_cents"],
                tenant_id,
                invoice_id,
            ),
        )
    return {key: int(value) for key, value in row.items()}


def issue_invoice(
    conn,
    tenant_id: str,
    invoice_id: str,
    *,
    actor_user_id: str | None = None,
    issue_on: date | None = None,
) -> dict[str, Any]:
    """Turn a draft into a numbered, immutable document.

    Everything that makes an invoice real happens in one transaction: the number
    is allocated, the dates are set, the status changes and the event is
    recorded. A partial version of this — a number with no invoice, or an issued
    invoice with no number — is exactly what the ``invoices_number_matches_status``
    constraint exists to make unrepresentable.
    """

    invoice = fetch_one(
        conn,
        """
        SELECT i.id, i.status, i.total_cents, a.payment_terms_days
        FROM invoices i
        JOIN billing_accounts a
          ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
        WHERE i.tenant_id = %s AND i.id = %s
        """,
        (tenant_id, invoice_id),
    )
    if not invoice:
        raise BillingError("Invoice not found.")
    if invoice["status"] != "draft":
        raise BillingError("Only a draft invoice can be issued.")

    line_count = fetch_one(
        conn,
        "SELECT count(*) AS n FROM invoice_lines WHERE tenant_id = %s AND invoice_id = %s",
        (tenant_id, invoice_id),
    )
    if not line_count or int(line_count["n"]) == 0:
        raise BillingError("An invoice needs at least one line before it can be issued.")

    # Checked here rather than in the route so no code path can issue around it
    # — the same reasoning as putting invoice immutability in a trigger. This
    # refuses only documents that would be *invalid*, never merely untidy ones:
    # a studio with no address can still invoice, a studio charging GST without
    # an ABN cannot, because that document is unusable to the person receiving
    # it.
    blockers = issuing_blockers(conn, tenant_id, invoice_id)
    if blockers:
        raise BillingError(" ".join(blocker["message"] for blocker in blockers))

    recalculate_totals(conn, tenant_id, invoice_id)
    number = next_document_number(conn, tenant_id, "invoice")
    issued_on = issue_on or date.today()
    due_on = issued_on + timedelta(days=int(invoice["payment_terms_days"] or 0))

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE invoices
               SET status = 'issued',
                   number = %s,
                   issue_date = %s,
                   due_date = %s,
                   issued_at = now(),
                   issued_by_user_id = %s,
                   updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status = 'draft'
            RETURNING id, number, status, issue_date, due_date, total_cents, balance_cents
            """,
            (number, issued_on, due_on, actor_user_id, tenant_id, invoice_id),
        )
        issued = cur.fetchone()
    if not issued:
        raise BillingError("Invoice changed while it was being issued.")

    record_event(conn, tenant_id, invoice_id, "issued", actor_user_id, {"number": number})
    return issued


def void_invoice(
    conn,
    tenant_id: str,
    invoice_id: str,
    *,
    reason: str,
    actor_user_id: str | None = None,
) -> None:
    """Void an issued invoice that has taken no money.

    Once any payment has been allocated, voiding is the wrong instrument: the
    money exists and the document has to keep explaining it. That case is a
    credit note, which reverses the charge while leaving both records standing.
    """

    invoice = fetch_one(
        conn,
        "SELECT status, amount_paid_cents FROM invoices WHERE tenant_id = %s AND id = %s",
        (tenant_id, invoice_id),
    )
    if not invoice:
        raise BillingError("Invoice not found.")
    if invoice["status"] == "void":
        return
    if int(invoice["amount_paid_cents"]) > 0:
        raise BillingError(
            "This invoice has payments against it. Reverse it with a credit note "
            "so the payment keeps its explanation."
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE invoices
               SET status = 'void', voided_at = now(), void_reason = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s
            """,
            (reason, tenant_id, invoice_id),
        )
    record_event(conn, tenant_id, invoice_id, "voided", actor_user_id, {"reason": reason})


def record_event(
    conn,
    tenant_id: str,
    invoice_id: str,
    event_type: str,
    actor_user_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Append to a document's history. Append-only by design."""

    import json as _json

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO invoice_events (tenant_id, invoice_id, event_type, actor_user_id, detail)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (tenant_id, invoice_id, event_type, actor_user_id, _json.dumps(detail or {})),
        )


# ── reading ──────────────────────────────────────────────────────────────


AGEING_BUCKETS: Sequence[tuple[str, int, int | None]] = (
    ("current", -10_000, 0),
    ("d1_30", 1, 30),
    ("d31_60", 31, 60),
    ("d61_90", 61, 90),
    ("d90_plus", 91, None),
)


@dataclass(frozen=True)
class AgeingRow:
    billing_account_id: str
    name: str
    buckets: dict[str, int]
    total_cents: int


def aged_receivables(conn, tenant_id: str, *, as_of: date | None = None) -> list[AgeingRow]:
    """Who owes what, by how overdue it is.

    Ageing is computed from ``due_date`` against ``as_of`` in one pass rather
    than by five separate queries, so every bucket in a row is answered as of
    the same instant.
    """

    when = as_of or date.today()
    rows = fetch_all(
        conn,
        """
        SELECT a.id AS billing_account_id,
               a.name,
               i.due_date,
               i.balance_cents
        FROM invoices i
        JOIN billing_accounts a
          ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
        WHERE i.tenant_id = %s
          AND i.status IN ('issued', 'part_paid')
          AND i.balance_cents > 0
        ORDER BY a.name, i.due_date
        """,
        (tenant_id,),
    )

    grouped: dict[str, AgeingRow] = {}
    for row in rows:
        account_id = str(row["billing_account_id"])
        entry = grouped.get(account_id)
        if entry is None:
            entry = AgeingRow(
                billing_account_id=account_id,
                name=row["name"],
                buckets={key: 0 for key, _lo, _hi in AGEING_BUCKETS},
                total_cents=0,
            )
            grouped[account_id] = entry

        overdue_days = (when - row["due_date"]).days if row["due_date"] else 0
        for key, low, high in AGEING_BUCKETS:
            if overdue_days >= low and (high is None or overdue_days <= high):
                entry.buckets[key] += int(row["balance_cents"])
                break
        object.__setattr__(entry, "total_cents", entry.total_cents + int(row["balance_cents"]))

    return list(grouped.values())


def account_statement(
    conn, tenant_id: str, billing_account_id: str, *, since: date | None = None
) -> dict[str, Any]:
    """Everything that moved on one account, in the order it happened.

    Invoices and payments are interleaved because that is how a family reads a
    statement — "you charged me, I paid you, you charged me again" — rather than
    as two lists they have to reconcile themselves.
    """

    invoices = fetch_all(
        conn,
        """
        SELECT id, number, status, issue_date, due_date,
               total_cents, amount_paid_cents, amount_credited_cents, balance_cents
        FROM invoices
        WHERE tenant_id = %s AND billing_account_id = %s AND status <> 'draft'
          AND (%s::date IS NULL OR issue_date >= %s::date)
        ORDER BY issue_date, number
        """,
        (tenant_id, billing_account_id, since, since),
    )
    payments = fetch_all(
        conn,
        """
        SELECT id, method, provider, amount_cents, refunded_cents, received_at, note
        FROM payments
        WHERE tenant_id = %s AND billing_account_id = %s AND status = 'succeeded'
          AND (%s::date IS NULL OR received_at::date >= %s::date)
        ORDER BY received_at
        """,
        (tenant_id, billing_account_id, since, since),
    )

    outstanding = sum(int(row["balance_cents"]) for row in invoices)
    unallocated = fetch_one(
        conn,
        """
        SELECT COALESCE(SUM(p.amount_cents - p.refunded_cents), 0)
             - COALESCE((SELECT SUM(al.amount_cents)
                           FROM payment_allocations al
                           JOIN payments p2
                             ON p2.tenant_id = al.tenant_id AND p2.id = al.payment_id
                          WHERE p2.tenant_id = %s AND p2.billing_account_id = %s), 0)
               AS credit_cents
        FROM payments p
        WHERE p.tenant_id = %s AND p.billing_account_id = %s AND p.status = 'succeeded'
        """,
        (tenant_id, billing_account_id, tenant_id, billing_account_id),
    )

    return {
        "invoices": invoices,
        "payments": payments,
        "outstandingCents": outstanding,
        "creditOnAccountCents": max(0, int((unallocated or {}).get("credit_cents") or 0)),
    }
