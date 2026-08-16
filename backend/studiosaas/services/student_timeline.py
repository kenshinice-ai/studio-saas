"""E1 (v10.8.0) — one student's history, merged from the records that exist.

The studio's question is "这孩子这半年发生了什么", and before this view the
answer lived in four places: the registration queue, the credit ledger, the
invoice centre and the progress reports. This module only *reads* those
sources and interleaves them; it introduces no new data plane and no write
path of any kind.

Two disciplines:

**Nothing is swallowed.** Each source is read under its own savepoint. A
source that cannot be read costs exactly that source, and its name is put in
``omittedSources`` — an empty list is the healthy state. Stored records are
not user input; a read path never throws over one.

**Timestamps are ISO 8601.** The platform's default JSON encoding renders
datetimes as RFC 1123 (see the api-dates memory); a paging cursor needs
lexicographic order, so entries serialise their ``ts`` explicitly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from ..db import fetch_all

#: Sources in merge order. Keys are what ``omittedSources`` reports and what
#: the route's permission mapping switches off for roles that may not look.
SOURCE_NAMES = ("registrations", "credits", "invoices", "payments", "credit_notes", "reports")

_CREDIT_TITLES = {
    "purchase": "课时充值",
    "consume": "上课扣课",
    "expire": "课时过期",
    "adjustment": "课时调整",
    "refund": "课时退款",
    "migration": "课时迁移",
}


def _entry(
    ts: datetime,
    kind: str,
    title: str,
    *,
    credits: Any = None,
    amount_cents: int | None = None,
    invoice_id: str | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    return {
        "_ts": ts,
        "kind": kind,
        "title": title,
        "credits": credits,
        "amountCents": amount_cents,
        "invoiceId": invoice_id,
        "note": note or None,
    }


def _credit_amount(value: Any):
    """Numeric credit balances keep their value without going through float."""

    if value is None:
        return None
    number = float(value)
    return int(number) if number == int(number) else number


def _registration_entries(conn, tenant_id, student_id, before, cap):
    rows = fetch_all(
        conn,
        """
        SELECT status, submitted_at, reviewed_at, message, review_note
        FROM registrations
        WHERE tenant_id = %s AND student_id = %s
        ORDER BY submitted_at DESC
        LIMIT 200
        """,
        (tenant_id, student_id),
    )
    entries = []
    for row in rows:
        if row["submitted_at"] and (before is None or row["submitted_at"] < before):
            entries.append(_entry(
                row["submitted_at"], "registration", "报名提交", note=row["message"],
            ))
        if (
            row["reviewed_at"]
            and row["status"] in ("approved", "converted")
            and (before is None or row["reviewed_at"] < before)
        ):
            entries.append(_entry(
                row["reviewed_at"], "approval", "报名审批通过", note=row["review_note"],
            ))
    return entries


def _credit_entries(conn, tenant_id, student_id, before, cap):
    rows = fetch_all(
        conn,
        """
        SELECT transaction_type, amount::numeric AS amount, fee_aud_cents, note, occurred_at
        FROM credit_transactions
        WHERE tenant_id = %s AND student_id = %s
          AND (%s::timestamptz IS NULL OR occurred_at < %s)
        ORDER BY occurred_at DESC
        LIMIT %s
        """,
        (tenant_id, student_id, before, before, cap),
    )
    entries = []
    for row in rows:
        amount = _credit_amount(row["amount"])
        tx_type = row["transaction_type"]
        if tx_type == "purchase":
            kind = "topup"
        elif tx_type == "refund":
            kind = "refund"
        elif tx_type in ("consume", "expire"):
            kind = "deduction"
        else:  # adjustment / migration carry their direction in the sign
            kind = "topup" if (amount or 0) >= 0 else "deduction"
        fee = int(row["fee_aud_cents"] or 0)
        entries.append(_entry(
            row["occurred_at"], kind,
            _CREDIT_TITLES.get(tx_type, tx_type),
            credits=amount,
            amount_cents=fee if fee != 0 else None,
            note=row["note"],
        ))
    return entries


def _invoice_entries(conn, tenant_id, student_id, before, cap):
    rows = fetch_all(
        conn,
        """
        SELECT i.id, i.number, i.status, i.note,
               COALESCE(i.issued_at, i.created_at) AS ts,
               SUM(l.total_cents)::int AS student_cents
        FROM invoices i
        JOIN invoice_lines l ON l.tenant_id = i.tenant_id AND l.invoice_id = i.id
        WHERE i.tenant_id = %s AND l.student_id = %s AND i.status <> 'draft'
          AND (%s::timestamptz IS NULL OR COALESCE(i.issued_at, i.created_at) < %s)
        GROUP BY i.id, i.number, i.status, i.note, ts
        ORDER BY ts DESC
        LIMIT %s
        """,
        (tenant_id, student_id, before, before, cap),
    )
    return [
        _entry(
            row["ts"], "invoice",
            f"开具发票 {row['number']}" + ("（已作废）" if row["status"] == "void" else ""),
            amount_cents=int(row["student_cents"]),
            invoice_id=str(row["id"]),
            note=row["note"],
        )
        for row in rows
    ]


def _payment_entries(conn, tenant_id, student_id, before, cap):
    rows = fetch_all(
        conn,
        """
        SELECT p.received_at AS ts, p.note, pa.amount_cents AS allocated_cents,
               i.id AS invoice_id, i.number
        FROM payment_allocations pa
        JOIN payments p ON p.tenant_id = pa.tenant_id AND p.id = pa.payment_id
        JOIN invoices i ON i.tenant_id = pa.tenant_id AND i.id = pa.invoice_id
        WHERE pa.tenant_id = %s AND p.status <> 'failed'
          AND EXISTS (
              SELECT 1 FROM invoice_lines l
              WHERE l.tenant_id = pa.tenant_id AND l.invoice_id = pa.invoice_id
                AND l.student_id = %s
          )
          AND (%s::timestamptz IS NULL OR p.received_at < %s)
        ORDER BY p.received_at DESC
        LIMIT %s
        """,
        (tenant_id, student_id, before, before, cap),
    )
    return [
        _entry(
            row["ts"], "payment", f"收到付款（{row['number']}）",
            amount_cents=int(row["allocated_cents"]),
            invoice_id=str(row["invoice_id"]),
            note=row["note"],
        )
        for row in rows
    ]


def _credit_note_entries(conn, tenant_id, student_id, before, cap):
    rows = fetch_all(
        conn,
        """
        SELECT n.number, n.total_cents, n.reason, n.invoice_id,
               COALESCE(n.issued_at, n.created_at) AS ts
        FROM credit_notes n
        WHERE n.tenant_id = %s AND n.status = 'issued' AND n.invoice_id IS NOT NULL
          AND EXISTS (
              SELECT 1 FROM invoice_lines l
              WHERE l.tenant_id = n.tenant_id AND l.invoice_id = n.invoice_id
                AND l.student_id = %s
          )
          AND (%s::timestamptz IS NULL OR COALESCE(n.issued_at, n.created_at) < %s)
        ORDER BY ts DESC
        LIMIT %s
        """,
        (tenant_id, student_id, before, before, cap),
    )
    return [
        _entry(
            row["ts"], "credit_note", f"开具贷记单 {row['number']}",
            amount_cents=int(row["total_cents"]),
            invoice_id=str(row["invoice_id"]),
            note=row["reason"],
        )
        for row in rows
    ]


def _report_entries(conn, tenant_id, student_id, before, cap):
    rows = fetch_all(
        conn,
        """
        SELECT period_start, period_end, published_at
        FROM progress_reports
        WHERE tenant_id = %s AND student_id = %s
          AND status = 'published' AND published_at IS NOT NULL
          AND (%s::timestamptz IS NULL OR published_at < %s)
        ORDER BY published_at DESC
        LIMIT %s
        """,
        (tenant_id, student_id, before, before, cap),
    )
    return [
        _entry(
            row["published_at"], "report",
            f"成长报告发布（{row['period_start'].isoformat()} ~ {row['period_end'].isoformat()}）",
        )
        for row in rows
    ]


#: Patchable in tests; the merge loop looks sources up here so a failure can
#: be simulated without breaking a real table.
SOURCE_FETCHERS: dict[str, Callable] = {
    "registrations": _registration_entries,
    "credits": _credit_entries,
    "invoices": _invoice_entries,
    "payments": _payment_entries,
    "credit_notes": _credit_note_entries,
    "reports": _report_entries,
}


def student_timeline(
    conn,
    tenant_id: str,
    student_id: str,
    *,
    limit: int = 50,
    before: datetime | None = None,
    include: set[str] | None = None,
) -> dict[str, Any]:
    """Merge the student's events, newest first.

    ``include`` names the sources the caller may read (default: all); sources
    left out — by permission or by a failed read — appear in
    ``omittedSources`` so absence is always visible, never silent.
    """

    wanted = SOURCE_NAMES if include is None else tuple(
        name for name in SOURCE_NAMES if name in include
    )
    omitted = [name for name in SOURCE_NAMES if name not in wanted]

    cap = limit + 1  # one extra per source so hasMore cannot lie at the edge
    entries: list[dict[str, Any]] = []
    for name in wanted:
        with conn.cursor() as cur:
            cur.execute("SAVEPOINT timeline_source")
        try:
            entries.extend(SOURCE_FETCHERS[name](conn, tenant_id, student_id, before, cap))
        except Exception:  # noqa: BLE001 — the omission is reported, not hidden
            with conn.cursor() as cur:
                cur.execute("ROLLBACK TO SAVEPOINT timeline_source")
            omitted.append(name)
        else:
            with conn.cursor() as cur:
                cur.execute("RELEASE SAVEPOINT timeline_source")

    entries.sort(key=lambda entry: (entry["_ts"], entry["kind"]), reverse=True)
    has_more = len(entries) > limit
    page = [
        {
            "ts": entry["_ts"].isoformat(),
            "kind": entry["kind"],
            "title": entry["title"],
            "credits": entry["credits"],
            "amountCents": entry["amountCents"],
            "invoiceId": entry["invoiceId"],
            "note": entry["note"],
        }
        for entry in entries[:limit]
    ]
    return {"entries": page, "hasMore": has_more, "omittedSources": omitted}
