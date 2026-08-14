"""Four management reports. Four, not a report builder.

A generic report builder is a product in its own right, and studios do not want
one — they want the four answers they currently reconstruct in a spreadsheet
every month. Building exactly those four, well, is a smaller job than building a
builder badly.

Every figure here is drillable: each report returns both the aggregate and the
identifiers needed to fetch the rows behind it. A number a studio cannot open is
a screenshot, and the first time it disagrees with their intuition they stop
trusting the whole report.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..db import fetch_all, fetch_one


def revenue(conn, tenant_id: str, *, start: date, end: date) -> dict[str, Any]:
    """What was invoiced, split by what it was for and by tax.

    Reads issued documents rather than payments: this is revenue billed, which
    is the number that reconciles to the accounting ledger. Cash collected is a
    different question and is answered by :func:`receivables`.
    """

    by_kind = fetch_all(
        conn,
        """
        SELECT l.source_kind,
               COUNT(DISTINCT i.id)                    AS invoices,
               SUM(l.total_cents - l.tax_cents)        AS net_cents,
               SUM(l.tax_cents)                        AS tax_cents,
               SUM(l.total_cents)                      AS gross_cents
        FROM invoice_lines l
        JOIN invoices i ON i.tenant_id = l.tenant_id AND i.id = l.invoice_id
        WHERE l.tenant_id = %s
          AND i.status IN ('issued', 'part_paid', 'paid')
          AND i.issue_date BETWEEN %s AND %s
        GROUP BY l.source_kind
        ORDER BY gross_cents DESC
        """,
        (tenant_id, start, end),
    )
    totals = fetch_one(
        conn,
        """
        SELECT COALESCE(SUM(subtotal_cents), 0) AS net_cents,
               COALESCE(SUM(tax_cents), 0)      AS tax_cents,
               COALESCE(SUM(total_cents), 0)    AS gross_cents,
               COUNT(*)                          AS invoices
        FROM invoices
        WHERE tenant_id = %s AND status IN ('issued', 'part_paid', 'paid')
          AND issue_date BETWEEN %s AND %s
        """,
        (tenant_id, start, end),
    ) or {}
    credits = fetch_one(
        conn,
        """
        SELECT COALESCE(SUM(total_cents), 0) AS credited_cents
        FROM credit_notes
        WHERE tenant_id = %s AND status = 'issued' AND issue_date BETWEEN %s AND %s
        """,
        (tenant_id, start, end),
    ) or {}
    return {"byKind": by_kind, "totals": totals, "credits": credits}


def receivables(conn, tenant_id: str, *, as_of: date | None = None) -> dict[str, Any]:
    """Who owes what, and for how long.

    Returns the account-level rollup plus the invoice ids behind each row, so
    the follow-up list a studio actually works from is one click away rather
    than a second query somebody has to think of.
    """

    when = as_of or date.today()
    rows = fetch_all(
        conn,
        """
        SELECT a.id AS billing_account_id, a.name, a.email, a.mobile,
               i.id AS invoice_id, i.number, i.due_date, i.balance_cents,
               GREATEST(0, (%s::date - i.due_date)) AS days_overdue
        FROM invoices i
        JOIN billing_accounts a ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
        WHERE i.tenant_id = %s AND i.status IN ('issued', 'part_paid') AND i.balance_cents > 0
        ORDER BY i.due_date NULLS LAST
        """,
        (when, tenant_id),
    )

    buckets = {"current": 0, "d1_30": 0, "d31_60": 0, "d61_90": 0, "d90_plus": 0}
    for row in rows:
        days = int(row["days_overdue"] or 0)
        key = (
            "current" if days <= 0
            else "d1_30" if days <= 30
            else "d31_60" if days <= 60
            else "d61_90" if days <= 90
            else "d90_plus"
        )
        buckets[key] += int(row["balance_cents"])

    return {
        "asOf": when.isoformat(),
        "buckets": buckets,
        "totalCents": sum(buckets.values()),
        "invoices": rows,
    }


def teacher_cost(conn, tenant_id: str, *, start: date, end: date) -> dict[str, Any]:
    """What teaching cost, per teacher, against what it billed.

    The margin column is the reason this report exists. A studio can usually say
    what it pays a teacher and what it charges for a lesson, and almost never
    what the two come to once absences, make-ups and unfilled group places are
    accounted for.
    """

    rows = fetch_all(
        conn,
        """
        SELECT s.teacher_user_id, u.full_name,
               -- How the teacher is engaged decides what may happen to this
               -- figure next: a contractor's total can become a payable bill,
               -- an employee's must not. A cost report that omits it invites
               -- exactly the wrong action.
               COALESCE(e.engagement, 'unset')                      AS engagement,
               COUNT(*)                                            AS sessions,
               COUNT(*) FILTER (WHERE NOT s.counts_for_pay)        AS unpaid_sessions,
               COALESCE(SUM(s.duration_minutes) FILTER (WHERE s.counts_for_pay), 0) AS paid_minutes,
               COALESCE(SUM(s.amount_cents) FILTER (WHERE s.counts_for_pay), 0)     AS cost_cents,
               COALESCE(SUM(s.tuition_basis_cents), 0)             AS billed_cents
        FROM teaching_sessions s
        JOIN users u ON u.id = s.teacher_user_id
        LEFT JOIN teacher_engagements e
               ON e.tenant_id = s.tenant_id AND e.teacher_user_id = s.teacher_user_id
        WHERE s.tenant_id = %s AND s.occurred_on BETWEEN %s AND %s
        GROUP BY s.teacher_user_id, u.full_name, e.engagement
        ORDER BY cost_cents DESC
        """,
        (tenant_id, start, end),
    )
    for row in rows:
        billed = int(row["billed_cents"] or 0)
        cost = int(row["cost_cents"] or 0)
        row["margin_cents"] = billed - cost
        # Only meaningful when something was billed; a teacher whose lessons are
        # invoiced by package rather than per session has no per-session billed
        # figure, and inventing a percentage from zero would be a lie.
        row["margin_percent"] = round((billed - cost) * 100 / billed) if billed else None
    return {"teachers": rows}


def attendance(conn, tenant_id: str, *, start: date, end: date) -> dict[str, Any]:
    """Attendance, and the students whose pattern has changed.

    The list that matters is not the average — it is the handful of students
    who have quietly stopped coming. A studio that sees them in week three keeps
    some of them; one that sees them at the end of term does not.
    """

    summary = fetch_one(
        conn,
        """
        SELECT COUNT(*) AS entries,
               COUNT(*) FILTER (WHERE status = 'scheduled') AS attended,
               COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
               COUNT(*) FILTER (WHERE status = 'makeup')    AS makeups
        FROM daily_roster_entries
        WHERE tenant_id = %s AND roster_date BETWEEN %s AND %s
        """,
        (tenant_id, start, end),
    ) or {}

    at_risk = fetch_all(
        conn,
        """
        SELECT s.id AS student_id, s.display_name,
               MAX(r.roster_date) AS last_seen,
               COUNT(*) FILTER (WHERE r.status = 'cancelled') AS recent_cancellations
        FROM students s
        JOIN daily_roster_entries r ON r.tenant_id = s.tenant_id AND r.student_id = s.id
        WHERE s.tenant_id = %s AND s.status = 'active' AND r.roster_date BETWEEN %s AND %s
        GROUP BY s.id, s.display_name
        HAVING COUNT(*) FILTER (WHERE r.status = 'cancelled') >= 2
            OR MAX(r.roster_date) < %s::date - INTERVAL '21 days'
        ORDER BY last_seen
        """,
        (tenant_id, start, end, end),
    )

    low_balance = fetch_all(
        conn,
        """
        SELECT s.id AS student_id, s.display_name,
               ca.balance::float AS balance, ca.low_balance_threshold::float AS threshold
        FROM credit_accounts ca
        JOIN students s ON s.tenant_id = ca.tenant_id AND s.id = ca.student_id
        WHERE ca.tenant_id = %s AND s.status = 'active'
          AND ca.balance <= ca.low_balance_threshold
        ORDER BY ca.balance
        LIMIT 50
        """,
        (tenant_id,),
    )

    return {"summary": summary, "atRisk": at_risk, "lowBalance": low_balance}


def default_period(days: int = 30) -> tuple[date, date]:
    """A sane default window so a report can be opened without a form."""

    end = date.today()
    return end - timedelta(days=days), end
