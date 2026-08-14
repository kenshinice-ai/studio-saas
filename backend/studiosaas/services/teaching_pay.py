"""What each teacher taught, what it is worth, and nothing beyond that.

This module produces a **summary**: the sessions a teacher taught in a period,
the rate each was computed at, and what they add up to. It stops there. It does
not withhold tax, calculate superannuation, produce a payslip, generate a bank
file or lodge anything with a revenue authority. Those are the work of a
registered payroll provider and an accountant, and a scheduling system that
performed them would be answering for a studio's tax compliance.

The reason one hourly rate was never enough: a studio pays per lesson for
private tuition, per head for a group class whose economics depend on it
filling, a share of tuition for a senior teacher, and a flat call-out for an
ensemble rehearsal or a school incursion — often all four in the same week.
That is why the spreadsheet outlives every system offering a single rate field.

Two numbers that look like one are kept apart throughout:

* whether a session is **charged to the student**;
* whether it **pays the teacher**.

A student who cancels inside the notice window is usually charged *and* the
teacher is usually paid. A studio that cancels usually neither. Collapsing them
into one boolean is the specific bug this module is shaped to avoid.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from ..db import fetch_all, fetch_one


class PayError(RuntimeError):
    """A pay figure could not be produced, and guessing would be worse."""


RATE_BASES = ("per_lesson", "per_hour", "per_head", "percent_of_tuition", "per_session")


@dataclass(frozen=True)
class Rate:
    basis: str
    amount_cents: int | None
    percent_bp: int | None


def resolve_rate(
    conn,
    tenant_id: str,
    teacher_user_id: str,
    *,
    course_id: str | None,
    on_date: date,
) -> Rate | None:
    """Find the rate that applied to this teacher, for this course, on this day.

    Resolution is most-specific-first: a rate naming the course beats the
    teacher's default, and among equally specific rows the one that came into
    effect most recently wins. Rows whose window has closed are excluded rather
    than ranked, so an expired rate can never resurface because nothing replaced
    it — that would pay somebody last year's money without anyone deciding to.
    """

    row = fetch_one(
        conn,
        """
        SELECT basis, amount_cents, percent_bp
        FROM teacher_pay_rates
        WHERE tenant_id = %s
          AND teacher_user_id = %s
          AND (course_id = %s OR course_id IS NULL)
          AND effective_from <= %s
          AND (effective_to IS NULL OR effective_to >= %s)
        ORDER BY (course_id IS NOT NULL) DESC, effective_from DESC
        LIMIT 1
        """,
        (tenant_id, teacher_user_id, course_id, on_date, on_date),
    )
    if not row:
        return None
    return Rate(
        basis=row["basis"],
        amount_cents=row["amount_cents"],
        percent_bp=row["percent_bp"],
    )


def session_amount(
    rate: Rate,
    *,
    duration_minutes: int = 0,
    student_count: int = 1,
    tuition_basis_cents: int = 0,
) -> int:
    """Turn a rate and the facts of a session into an amount in cents.

    Rounds once, half-up, for the same reason invoice tax does: an accountant's
    arithmetic rounds halves away from zero, and matching it is cheaper than
    explaining why we do not.
    """

    if rate.basis == "per_lesson" or rate.basis == "per_session":
        return int(rate.amount_cents or 0)

    if rate.basis == "per_hour":
        hours = Decimal(duration_minutes) / Decimal(60)
        return int(
            (hours * Decimal(rate.amount_cents or 0)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )

    if rate.basis == "per_head":
        return int(rate.amount_cents or 0) * max(0, int(student_count))

    if rate.basis == "percent_of_tuition":
        return int(
            (
                Decimal(tuition_basis_cents) * Decimal(rate.percent_bp or 0) / Decimal(10000)
            ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    raise PayError(f"Unknown rate basis: {rate.basis}")


def upsert_session(
    conn,
    tenant_id: str,
    *,
    teacher_user_id: str,
    occurred_on: date,
    course_id: str | None = None,
    start_time: Any = None,
    duration_minutes: int = 0,
    student_count: int = 1,
    source: str = "roster",
    series_id: str | None = None,
    schedule_id: str | None = None,
    counts_for_pay: bool = True,
    tuition_basis_cents: int = 0,
    note: str = "",
) -> dict[str, Any] | None:
    """Record one taught session, priced at the rate in force that day.

    Idempotent on the natural key (teacher, day, series/schedule, time), so the
    collector can be re-run over a period as often as anybody likes — after a
    correction to the roster, for instance — without inventing duplicate work.

    A session belonging to a confirmed period is left alone: those figures have
    been signed off, and changing them behind a teacher's back is precisely what
    the locking exists to prevent. Corrections go on the next period as an
    adjustment.
    """

    rate = resolve_rate(
        conn, tenant_id, teacher_user_id, course_id=course_id, on_date=occurred_on
    )
    amount = 0
    if rate and counts_for_pay:
        amount = session_amount(
            rate,
            duration_minutes=duration_minutes,
            student_count=student_count,
            tuition_basis_cents=tuition_basis_cents,
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO teaching_sessions (
                tenant_id, teacher_user_id, course_id, occurred_on, start_time,
                duration_minutes, student_count, source, series_id, schedule_id,
                counts_for_pay, rate_basis, rate_amount_cents, rate_percent_bp,
                tuition_basis_cents, amount_cents, note
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, teacher_user_id, occurred_on,
                         COALESCE(series_id, '00000000-0000-0000-0000-000000000000'::uuid),
                         COALESCE(schedule_id, '00000000-0000-0000-0000-000000000000'::uuid),
                         COALESCE(start_time, '00:00'::time))
              WHERE source <> 'manual'
              DO UPDATE SET
                  duration_minutes = EXCLUDED.duration_minutes,
                  student_count = EXCLUDED.student_count,
                  counts_for_pay = EXCLUDED.counts_for_pay,
                  rate_basis = EXCLUDED.rate_basis,
                  rate_amount_cents = EXCLUDED.rate_amount_cents,
                  rate_percent_bp = EXCLUDED.rate_percent_bp,
                  tuition_basis_cents = EXCLUDED.tuition_basis_cents,
                  amount_cents = EXCLUDED.amount_cents,
                  updated_at = now()
              WHERE teaching_sessions.locked_at IS NULL
            RETURNING id, amount_cents, counts_for_pay
            """,
            (
                tenant_id, teacher_user_id, course_id, occurred_on, start_time,
                duration_minutes, student_count, source, series_id, schedule_id,
                counts_for_pay,
                rate.basis if rate else None,
                rate.amount_cents if rate else None,
                rate.percent_bp if rate else None,
                tuition_basis_cents, amount, note,
            ),
        )
        written = cur.fetchone()

    if written is not None:
        return written

    # The `DO UPDATE ... WHERE locked_at IS NULL` above declines to touch a
    # session belonging to a confirmed period, which is right — but it declines
    # *silently*, returning no row. Leaving it there would mean a re-run of the
    # collector after confirmation quietly discarded the correction and told
    # nobody, which is the shape of bug that surfaces months later as "the
    # numbers don't add up". Say so instead.
    locked = fetch_one(
        conn,
        """
        SELECT s.id, p.period_start, p.period_end
        FROM teaching_sessions s
        LEFT JOIN teacher_pay_periods p ON p.id = s.period_id
        WHERE s.tenant_id = %s
          AND s.teacher_user_id = %s
          AND s.occurred_on = %s
          AND COALESCE(s.series_id, '00000000-0000-0000-0000-000000000000'::uuid)
              = COALESCE(%s::uuid, '00000000-0000-0000-0000-000000000000'::uuid)
          AND COALESCE(s.schedule_id, '00000000-0000-0000-0000-000000000000'::uuid)
              = COALESCE(%s::uuid, '00000000-0000-0000-0000-000000000000'::uuid)
          AND COALESCE(s.start_time, '00:00'::time) = COALESCE(%s::time, '00:00'::time)
          AND s.locked_at IS NOT NULL
        """,
        (tenant_id, teacher_user_id, occurred_on, series_id, schedule_id, start_time),
    )
    if locked:
        raise PayError(
            f"The session on {occurred_on} belongs to a pay period that has already been "
            "confirmed. Record the difference as an adjustment on the current period so "
            "the change is dated and attributable."
        )
    raise PayError("The teaching session could not be recorded.")


def open_period(
    conn,
    tenant_id: str,
    teacher_user_id: str,
    *,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Get or create the pay period a teacher's sessions will roll up into."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO teacher_pay_periods
                (tenant_id, teacher_user_id, period_start, period_end)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, teacher_user_id, period_start, period_end)
              DO UPDATE SET updated_at = now()
            RETURNING id, status, period_start, period_end
            """,
            (tenant_id, teacher_user_id, period_start, period_end),
        )
        return cur.fetchone()


def recalculate_period(conn, tenant_id: str, period_id: str) -> dict[str, Any]:
    """Attach the period's sessions to it and re-total.

    Only unconfirmed periods move. Once a teacher has signed off, the total they
    signed off on is the total, and a later correction belongs to the next period
    as an adjustment — visible, dated and attributable — rather than as a silent
    revision of a number somebody already agreed to.
    """

    period = fetch_one(
        conn,
        """
        SELECT id, teacher_user_id, period_start, period_end, status
        FROM teacher_pay_periods WHERE tenant_id = %s AND id = %s
        """,
        (tenant_id, period_id),
    )
    if not period:
        raise PayError("Pay period not found.")
    if period["status"] != "open":
        raise PayError("This period has been confirmed; use an adjustment instead.")

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE teaching_sessions
               SET period_id = %s, updated_at = now()
             WHERE tenant_id = %s
               AND teacher_user_id = %s
               AND occurred_on BETWEEN %s AND %s
               AND locked_at IS NULL
            """,
            (period_id, tenant_id, period["teacher_user_id"],
             period["period_start"], period["period_end"]),
        )
        cur.execute(
            """
            UPDATE teacher_pay_periods p
               SET sessions_cents = COALESCE((
                       SELECT SUM(amount_cents) FROM teaching_sessions
                        WHERE period_id = p.id AND counts_for_pay
                   ), 0),
                   adjustments_cents = COALESCE((
                       SELECT SUM(amount_cents) FROM teacher_pay_adjustments
                        WHERE period_id = p.id
                   ), 0),
                   updated_at = now()
             WHERE p.tenant_id = %s AND p.id = %s
            RETURNING id, sessions_cents, adjustments_cents, total_cents, status
            """,
            (tenant_id, period_id),
        )
        return cur.fetchone()


def confirm_period(
    conn, tenant_id: str, period_id: str, *, confirmed_by_user_id: str
) -> dict[str, Any]:
    """The teacher's own acknowledgement, and the moment the figures freeze.

    Confirmation is deliberately the teacher's action rather than the office's.
    A disagreement about hours is cheap to resolve before anybody is paid and
    expensive afterwards, so the workflow puts the conversation first.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE teacher_pay_periods
               SET status = 'confirmed', confirmed_at = now(),
                   confirmed_by_user_id = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status = 'open'
            RETURNING id, status, total_cents
            """,
            (confirmed_by_user_id, tenant_id, period_id),
        )
        confirmed = cur.fetchone()
        if not confirmed:
            raise PayError("Only an open period can be confirmed.")
        cur.execute(
            "UPDATE teaching_sessions SET locked_at = now() WHERE period_id = %s AND locked_at IS NULL",
            (period_id,),
        )
    return confirmed


def variance(conn, tenant_id: str, teacher_user_id: str, start: date, end: date) -> dict[str, int]:
    """Scheduled against actual, with the difference broken out.

    Four numbers on one screen. A single "hours taught" figure invites the
    question it cannot answer — "that's fewer than I had booked, why?" — and the
    answer is what stops a pay conversation becoming a dispute.
    """

    row = fetch_one(
        conn,
        """
        SELECT
          COUNT(*)                                        AS actual_sessions,
          COUNT(*) FILTER (WHERE counts_for_pay)          AS paid_sessions,
          COUNT(*) FILTER (WHERE NOT counts_for_pay)      AS unpaid_sessions,
          COALESCE(SUM(duration_minutes) FILTER (WHERE counts_for_pay), 0) AS paid_minutes,
          COALESCE(SUM(amount_cents) FILTER (WHERE counts_for_pay), 0)     AS amount_cents
        FROM teaching_sessions
        WHERE tenant_id = %s AND teacher_user_id = %s AND occurred_on BETWEEN %s AND %s
        """,
        (tenant_id, teacher_user_id, start, end),
    ) or {}
    return {key: int(value or 0) for key, value in row.items()}


def payable_summary(conn, tenant_id: str, period_id: str) -> dict[str, Any]:
    """Everything needed to hand a period to whoever runs payroll.

    ``engagement`` is in here because it decides what may happen next: a
    contractor's total can become a payable bill in the accounting ledger, while
    an employee's must not — posting wages as a bill bypasses the payroll
    accounts and misstates the books. When it is unset, the export refuses
    rather than picking one.
    """

    period = fetch_one(
        conn,
        """
        SELECT p.id, p.period_start, p.period_end, p.status,
               p.sessions_cents, p.adjustments_cents, p.total_cents,
               p.confirmed_at,
               u.full_name, u.email,
               COALESCE(e.engagement, 'unset') AS engagement,
               COALESCE(e.abn, '')             AS abn
        FROM teacher_pay_periods p
        JOIN users u ON u.id = p.teacher_user_id
        LEFT JOIN teacher_engagements e
               ON e.tenant_id = p.tenant_id AND e.teacher_user_id = p.teacher_user_id
        WHERE p.tenant_id = %s AND p.id = %s
        """,
        (tenant_id, period_id),
    )
    if not period:
        raise PayError("Pay period not found.")

    sessions = fetch_all(
        conn,
        """
        SELECT s.occurred_on, s.start_time, s.duration_minutes, s.student_count,
               s.counts_for_pay, s.rate_basis, s.amount_cents, c.name AS course_name
        FROM teaching_sessions s
        LEFT JOIN courses c ON c.id = s.course_id
        WHERE s.period_id = %s
        ORDER BY s.occurred_on, s.start_time NULLS LAST
        """,
        (period_id,),
    )
    adjustments = fetch_all(
        conn,
        """
        SELECT label, amount_cents, created_at
        FROM teacher_pay_adjustments WHERE period_id = %s ORDER BY created_at
        """,
        (period_id,),
    )
    return {"period": period, "sessions": sessions, "adjustments": adjustments}
