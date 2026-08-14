"""Recurring private lessons, dated deviations, and make-up credits.

The tables landed in migration 0033 with the argument for their shape. This is
the layer that decides things, and there is really only one decision in it:

    when a lesson does not happen, who still pays and who still gets paid?

Those are two questions, not one. A student who cancels an hour before is
usually charged *and* the teacher is usually paid — the room was held, the
evening was blocked. A studio that closes for a public holiday charges nobody
and pays everybody. Collapsing them into a single "cancelled" flag is the bug
`lesson_exceptions` exists to prevent, so the resolver below returns both
answers plus a third: whether the family is owed a make-up.

:func:`resolve_absence` is deliberately a pure function over a policy dict. It
is the part that must be right, and it can be tested exhaustively without a
database — which matters, because getting it wrong does not raise an error, it
quietly bills a family for a lesson the studio cancelled.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from ..db import fetch_all, fetch_one


class SchedulingError(RuntimeError):
    """A scheduling action was refused, with a reason a studio can act on."""


#: Matches the column defaults in migration 0033. Duplicated here rather than
#: read from the table because a tenant that has never opened the settings page
#: must still be able to cancel a lesson, and falling back to "free for
#: everyone" would be the expensive direction to be wrong in.
DEFAULT_POLICY: dict[str, Any] = {
    "notice_hours": 24,
    "makeup_credit_on_notice": True,
    "makeup_expiry_days": None,
    "late_absence_chargeable": True,
    "late_absence_pays_teacher": True,
    "studio_cancel_chargeable": False,
}

#: Who called it off. The answer changes the money, so it is a required input
#: rather than something inferred from who is logged in — the front desk enters
#: most cancellations on behalf of whoever rang up.
CANCELLED_BY_STUDENT = "student"
CANCELLED_BY_STUDIO = "studio"


def policy(conn, tenant_id: str) -> dict[str, Any]:
    """This studio's cancellation policy, with defaults filled in."""

    row = fetch_one(
        conn,
        """
        SELECT notice_hours, makeup_credit_on_notice, makeup_expiry_days,
               late_absence_chargeable, late_absence_pays_teacher,
               studio_cancel_chargeable
        FROM scheduling_policies WHERE tenant_id = %s
        """,
        (tenant_id,),
    )
    return dict(row) if row else dict(DEFAULT_POLICY)


def save_policy(conn, tenant_id: str, values: dict[str, Any]) -> dict[str, Any]:
    """Upsert the policy, ignoring keys the caller did not send."""

    current = policy(conn, tenant_id)
    merged = {key: values.get(key, current[key]) for key in DEFAULT_POLICY}
    if int(merged["notice_hours"]) < 0:
        raise SchedulingError("Notice hours cannot be negative.")
    expiry = merged["makeup_expiry_days"]
    if expiry is not None and int(expiry) <= 0:
        raise SchedulingError("Make-up credits either expire after some days, or never.")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO scheduling_policies
                (tenant_id, notice_hours, makeup_credit_on_notice, makeup_expiry_days,
                 late_absence_chargeable, late_absence_pays_teacher, studio_cancel_chargeable)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE SET
                notice_hours              = EXCLUDED.notice_hours,
                makeup_credit_on_notice   = EXCLUDED.makeup_credit_on_notice,
                makeup_expiry_days        = EXCLUDED.makeup_expiry_days,
                late_absence_chargeable   = EXCLUDED.late_absence_chargeable,
                late_absence_pays_teacher = EXCLUDED.late_absence_pays_teacher,
                studio_cancel_chargeable  = EXCLUDED.studio_cancel_chargeable,
                updated_at                = now()
            RETURNING notice_hours, makeup_credit_on_notice, makeup_expiry_days,
                      late_absence_chargeable, late_absence_pays_teacher,
                      studio_cancel_chargeable
            """,
            (
                tenant_id,
                int(merged["notice_hours"]),
                bool(merged["makeup_credit_on_notice"]),
                None if expiry is None else int(expiry),
                bool(merged["late_absence_chargeable"]),
                bool(merged["late_absence_pays_teacher"]),
                bool(merged["studio_cancel_chargeable"]),
            ),
        )
        return cur.fetchone()


def resolve_absence(
    active_policy: dict[str, Any],
    *,
    cancelled_by: str,
    hours_notice: float | None,
) -> dict[str, bool]:
    """Decide the three consequences of a lesson not happening.

    Returns ``chargeable`` (does the family still pay), ``counts_for_pay`` (is
    the teacher still paid) and ``grants_credit`` (is a make-up owed).

    The studio branch comes first and ignores notice entirely: a studio that
    closes has given itself whatever notice it liked, and asking "was it more
    than 24 hours" would let a late studio closure bill the family. The teacher
    is always paid for a studio cancellation — the studio made the call, and
    docking the teacher for it is the fastest way to lose them.

    ``hours_notice`` of ``None`` means nobody recorded when the call came in;
    treated as *inside* the window, because the alternative is that every
    unrecorded absence silently becomes free.
    """

    if cancelled_by == CANCELLED_BY_STUDIO:
        return {
            "chargeable": bool(active_policy["studio_cancel_chargeable"]),
            "counts_for_pay": True,
            # A credit only means something if the family was charged. Handing
            # out a credit for a lesson nobody paid for is a second free lesson.
            "grants_credit": bool(active_policy["studio_cancel_chargeable"]),
        }

    if cancelled_by != CANCELLED_BY_STUDENT:
        raise SchedulingError("A cancellation has to be attributed to the student or the studio.")

    in_time = hours_notice is not None and hours_notice >= float(active_policy["notice_hours"])
    if in_time:
        # Enough notice: the slot could be refilled, so nobody is charged and
        # the family keeps the lesson as a credit if the studio offers them.
        return {
            "chargeable": False,
            "counts_for_pay": False,
            "grants_credit": bool(active_policy["makeup_credit_on_notice"]),
        }

    return {
        "chargeable": bool(active_policy["late_absence_chargeable"]),
        "counts_for_pay": bool(active_policy["late_absence_pays_teacher"]),
        # No credit for a late cancellation — that is the entire point of
        # having a notice window.
        "grants_credit": False,
    }


def hours_of_notice(*, lesson_on: date, lesson_at: time, decided_at: datetime | None = None) -> float:
    """Hours between the call coming in and the lesson starting.

    Negative when the call comes after the lesson was due to start, which
    :func:`resolve_absence` treats as no notice rather than as an error — a
    no-show is recorded the next morning more often than not.
    """

    when = decided_at or datetime.now()
    starts = datetime.combine(lesson_on, lesson_at)
    return (starts - when).total_seconds() / 3600.0


# ── the recurring lesson ─────────────────────────────────────────────────


def list_series(conn, tenant_id: str, *, student_id: str | None = None) -> list[dict[str, Any]]:
    """Active and paused series, newest first, with the names attached."""

    return fetch_all(
        conn,
        """
        SELECT ls.id, ls.student_id, ls.weekday,
               to_char(ls.start_time, 'HH24:MI')      AS start_time,
               ls.duration_minutes, ls.room, ls.status,
               to_char(ls.starts_on, 'YYYY-MM-DD')    AS starts_on,
               to_char(ls.ends_on, 'YYYY-MM-DD')      AS ends_on,
               to_char(ls.paused_from, 'YYYY-MM-DD')  AS paused_from,
               to_char(ls.paused_to, 'YYYY-MM-DD')    AS paused_to,
               ls.price_aud_cents, ls.note,
               ls.teacher_user_id, u.full_name AS teacher_name,
               s.display_name AS student_name,
               c.name AS course_name
        FROM lesson_series ls
        JOIN students s ON s.tenant_id = ls.tenant_id AND s.id = ls.student_id
        LEFT JOIN users u   ON u.id = ls.teacher_user_id
        LEFT JOIN courses c ON c.id = ls.course_id
        WHERE ls.tenant_id = %s
          AND ls.status <> 'ended'
          AND (%s = '' OR ls.student_id::text = %s)
        ORDER BY ls.weekday, ls.start_time
        """,
        (tenant_id, student_id or "", student_id or ""),
    )


def create_series(
    conn,
    tenant_id: str,
    *,
    student_id: str,
    weekday: int,
    start_time: str,
    duration_minutes: int,
    starts_on: date,
    teacher_user_id: str | None = None,
    course_id: str | None = None,
    room: str = "",
    ends_on: date | None = None,
    price_aud_cents: int | None = None,
    note: str = "",
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    """Start a weekly private lesson.

    The clash check is advisory and deliberately so: it refuses a *teacher*
    double-booking, which is physically impossible, and says nothing about
    rooms, which studios overbook on purpose all the time.
    """

    if not 0 <= int(weekday) <= 6:
        raise SchedulingError("Weekday has to be 0 (Sunday) through 6 (Saturday).")
    if int(duration_minutes) <= 0:
        raise SchedulingError("A lesson needs a length.")
    if ends_on and ends_on < starts_on:
        raise SchedulingError("A series cannot end before it starts.")

    if teacher_user_id:
        clash = fetch_one(
            conn,
            """
            SELECT s.id, st.display_name AS student_name,
                   to_char(s.start_time, 'HH24:MI') AS start_time
            FROM lesson_series s
            JOIN students st ON st.tenant_id = s.tenant_id AND st.id = s.student_id
            WHERE s.tenant_id = %s AND s.teacher_user_id = %s AND s.weekday = %s
              AND s.status = 'active'
              AND (s.ends_on IS NULL OR s.ends_on >= %s)
              -- Overlap, not equality: a 30-minute lesson starting at 4:15 runs
              -- into one that starts at 4:30, and equality would miss it.
              AND (s.start_time, s.start_time + make_interval(mins => s.duration_minutes))
                  OVERLAPS
                  (%s::time, %s::time + make_interval(mins => %s))
            LIMIT 1
            """,
            (tenant_id, teacher_user_id, int(weekday), starts_on,
             start_time, start_time, int(duration_minutes)),
        )
        if clash:
            raise SchedulingError(
                f"That teacher already has {clash['student_name']} at {clash['start_time']} "
                "on this weekday."
            )

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO lesson_series
                (tenant_id, student_id, course_id, teacher_user_id, weekday, start_time,
                 duration_minutes, room, starts_on, ends_on, price_aud_cents, note,
                 created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s::time, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, status, weekday, to_char(start_time, 'HH24:MI') AS start_time
            """,
            (tenant_id, student_id, course_id, teacher_user_id, int(weekday), start_time,
             int(duration_minutes), room, starts_on, ends_on, price_aud_cents, note,
             created_by_user_id),
        )
        return cur.fetchone()


def set_series_status(
    conn, tenant_id: str, series_id: str, *, status: str,
    paused_from: date | None = None, paused_to: date | None = None,
) -> dict[str, Any]:
    """Pause, resume or end a series.

    Ending is a status change, never a delete: the exceptions and make-up
    credits hanging off a series are the studio's record of what it charged
    for, and they have to outlive the arrangement that produced them.
    """

    if status not in {"active", "paused", "ended"}:
        raise SchedulingError("A series is active, paused or ended.")
    if status == "paused" and paused_from and paused_to and paused_to < paused_from:
        raise SchedulingError("A pause cannot end before it begins.")

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE lesson_series
               SET status = %s,
                   paused_from = CASE WHEN %s = 'paused' THEN %s::date ELSE NULL END,
                   paused_to   = CASE WHEN %s = 'paused' THEN %s::date ELSE NULL END,
                   ends_on     = CASE WHEN %s = 'ended'
                                      THEN COALESCE(ends_on, CURRENT_DATE) ELSE ends_on END,
                   updated_at  = now()
             WHERE tenant_id = %s AND id = %s
            RETURNING id, status, to_char(ends_on, 'YYYY-MM-DD') AS ends_on
            """,
            (status, status, paused_from, status, paused_to, status, tenant_id, series_id),
        )
        row = cur.fetchone()
    if not row:
        raise SchedulingError("That series does not exist.")
    return row


def occurrences(
    conn, tenant_id: str, *, start: date, end: date,
    series_id: str | None = None, teacher_user_id: str | None = None,
) -> list[dict[str, Any]]:
    """Every private lesson due between two dates, deviations applied.

    Expanded in SQL rather than in Python because the calendar view asks for a
    fortnight across every series at once, and pulling the templates back to
    walk them here would be a query per series.

    A term closure removes the lesson entirely — it is not an absence anybody
    decided, so it produces no exception row and no credit, and showing it as
    "cancelled" would put a studio holiday in a family's attendance history.
    """

    if end < start:
        raise SchedulingError("The end of the range cannot precede its start.")

    return fetch_all(
        conn,
        """
        SELECT ls.id AS series_id,
               to_char(d::date, 'YYYY-MM-DD')          AS on_date,
               to_char(ls.start_time, 'HH24:MI')       AS start_time,
               ls.duration_minutes, ls.room,
               ls.student_id, s.display_name           AS student_name,
               ls.teacher_user_id, u.full_name         AS teacher_name,
               ex.id                                   AS exception_id,
               ex.kind                                 AS exception_kind,
               ex.chargeable, ex.counts_for_pay,
               to_char(ex.moved_to_date, 'YYYY-MM-DD') AS moved_to_date,
               to_char(ex.moved_to_start_time, 'HH24:MI') AS moved_to_start_time,
               ex.reason
        FROM lesson_series ls
        JOIN students s ON s.tenant_id = ls.tenant_id AND s.id = ls.student_id
        LEFT JOIN users u ON u.id = ls.teacher_user_id
        CROSS JOIN LATERAL generate_series(
            GREATEST(ls.starts_on, %s::date),
            LEAST(COALESCE(ls.ends_on, %s::date), %s::date),
            interval '1 day') AS d
        LEFT JOIN lesson_exceptions ex
               ON ex.tenant_id = ls.tenant_id AND ex.series_id = ls.id
              AND ex.on_date = d::date
        WHERE ls.tenant_id = %s
          -- Paused series stay in the expansion. Filtering them out by status
          -- would make paused_from/paused_to unreachable, and "pause August"
          -- would silently mean "stop forever" — the columns exist because a
          -- family going away for three weeks is the common case.
          AND ls.status IN ('active', 'paused')
          -- lesson_series.weekday follows JS getDay(): 0=Sunday..6=Saturday,
          -- which is what extract(dow) returns. Same convention as
          -- class_schedules, so the two can be merged into one calendar.
          AND extract(dow FROM d)::int = ls.weekday
          AND NOT EXISTS (
                SELECT 1 FROM term_closures tc
                 WHERE tc.tenant_id = ls.tenant_id AND tc.on_date = d::date)
          -- Inside the pause window, nothing runs. A pause with no start date
          -- is an indefinite one, so it swallows the whole range.
          AND NOT (ls.status = 'paused'
                   AND (ls.paused_from IS NULL OR d::date >= ls.paused_from)
                   AND (ls.paused_to IS NULL OR d::date <= ls.paused_to))
          AND (%s = '' OR ls.id::text = %s)
          AND (%s = '' OR ls.teacher_user_id::text = %s)
        ORDER BY d::date, ls.start_time
        """,
        (start, end, end, tenant_id,
         series_id or "", series_id or "",
         teacher_user_id or "", teacher_user_id or ""),
    )


def cancel_occurrence(
    conn,
    tenant_id: str,
    series_id: str,
    *,
    on_date: date,
    cancelled_by: str,
    hours_notice: float | None,
    reason: str = "",
    created_by_user_id: str | None = None,
) -> dict[str, Any]:
    """Record an absence and, if it is owed, the make-up credit that follows.

    Both writes happen in one transaction on purpose. A credit without its
    exception is a free lesson nobody can explain; an exception without its
    credit is a family who was promised a make-up and did not get one. The
    caller commits.
    """

    series = fetch_one(
        conn,
        """
        SELECT student_id, to_char(start_time, 'HH24:MI') AS start_time, status
        FROM lesson_series WHERE tenant_id = %s AND id = %s
        """,
        (tenant_id, series_id),
    )
    if not series:
        raise SchedulingError("That series does not exist.")
    if series["status"] == "ended":
        raise SchedulingError("This series has ended; there is nothing to cancel on it.")

    active_policy = policy(conn, tenant_id)
    outcome = resolve_absence(
        active_policy, cancelled_by=cancelled_by, hours_notice=hours_notice
    )
    kind = ("cancelled_by_studio" if cancelled_by == CANCELLED_BY_STUDIO
            else "cancelled_by_student")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO lesson_exceptions
                (tenant_id, series_id, on_date, kind, chargeable, counts_for_pay,
                 reason, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (series_id, on_date) DO NOTHING
            RETURNING id
            """,
            (tenant_id, series_id, on_date, kind, outcome["chargeable"],
             outcome["counts_for_pay"], reason, created_by_user_id),
        )
        inserted = cur.fetchone()
        if not inserted:
            # The unique index caught a second cancellation of the same date.
            # Refusing loudly beats overwriting, because the first row already
            # decided the money and may already have granted a credit.
            raise SchedulingError(
                "That lesson already has a recorded change. Undo it first if the "
                "decision needs to be different."
            )
        exception_id = inserted["id"]

        credit_id = None
        if outcome["grants_credit"]:
            expiry_days = active_policy["makeup_expiry_days"]
            expires_on = on_date + timedelta(days=int(expiry_days)) if expiry_days else None
            cur.execute(
                """
                INSERT INTO makeup_credits
                    (tenant_id, student_id, earned_from_date, earned_from_exception_id,
                     expires_on, reason, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (tenant_id, series["student_id"], on_date, exception_id,
                 expires_on, reason, created_by_user_id),
            )
            credit_id = cur.fetchone()["id"]
            cur.execute(
                "UPDATE lesson_exceptions SET makeup_credit_id = %s WHERE id = %s",
                (credit_id, exception_id),
            )

    return {
        "exceptionId": str(exception_id),
        "makeupCreditId": str(credit_id) if credit_id else None,
        **outcome,
    }


def undo_occurrence(conn, tenant_id: str, exception_id: str) -> None:
    """Remove a recorded change, and the credit it granted along with it.

    Cancelling the credit rather than deleting it keeps the row that says a
    credit once existed — deleting would let a family's balance change with no
    trace of why.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE makeup_credits SET status = 'cancelled', updated_at = now()
             WHERE tenant_id = %s AND earned_from_exception_id = %s AND status = 'available'
            """,
            (tenant_id, exception_id),
        )
        cur.execute(
            "DELETE FROM lesson_exceptions WHERE tenant_id = %s AND id = %s RETURNING id",
            (tenant_id, exception_id),
        )
        if not cur.fetchone():
            raise SchedulingError("There is no recorded change with that id.")


# ── make-up credits ──────────────────────────────────────────────────────


def credits(
    conn, tenant_id: str, *, student_id: str | None = None, include_spent: bool = False
) -> list[dict[str, Any]]:
    """Make-up credits, with expiry worked out at read time.

    ``status`` in the table stays ``available`` past the expiry date on
    purpose: a stored ``expired`` would need a nightly job, and between two
    runs the column is wrong. The derived ``is_expired`` here is right the
    moment the date passes, at three in the morning included.
    """

    return fetch_all(
        conn,
        """
        SELECT mc.id, mc.student_id, s.display_name AS student_name,
               to_char(mc.earned_from_date, 'YYYY-MM-DD') AS earned_from_date,
               to_char(mc.expires_on, 'YYYY-MM-DD')       AS expires_on,
               mc.status,
               (mc.status = 'available'
                AND mc.expires_on IS NOT NULL
                AND mc.expires_on < CURRENT_DATE)         AS is_expired,
               to_char(mc.consumed_on_date, 'YYYY-MM-DD') AS consumed_on_date,
               mc.reason
        FROM makeup_credits mc
        JOIN students s ON s.tenant_id = mc.tenant_id AND s.id = mc.student_id
        WHERE mc.tenant_id = %s
          AND (%s = '' OR mc.student_id::text = %s)
          AND (%s OR mc.status = 'available')
        ORDER BY mc.expires_on NULLS LAST, mc.earned_from_date
        """,
        (tenant_id, student_id or "", student_id or "", bool(include_spent)),
    )


def consume_credit(
    conn, tenant_id: str, credit_id: str, *, on_date: date,
    series_id: str | None = None, start_time: str | None = None,
    teacher_user_id: str | None = None, created_by_user_id: str | None = None,
) -> dict[str, Any]:
    """Book a make-up lesson against a credit.

    The guard is on the UPDATE rather than on a prior SELECT: two people
    booking the same credit from two screens both pass a check-then-write, and
    only one of them can win a conditional update.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE makeup_credits
               SET status = 'consumed', consumed_on_date = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status = 'available'
               AND (expires_on IS NULL OR expires_on >= CURRENT_DATE)
            RETURNING id, student_id
            """,
            (on_date, tenant_id, credit_id),
        )
        credit = cur.fetchone()
        if not credit:
            raise SchedulingError(
                "That credit is not available — it has been used, cancelled, or has expired."
            )

        exception_id = None
        if series_id:
            cur.execute(
                """
                INSERT INTO lesson_exceptions
                    (tenant_id, series_id, on_date, kind, moved_to_date, moved_to_start_time,
                     teacher_user_id, chargeable, counts_for_pay, makeup_credit_id,
                     created_by_user_id)
                VALUES (%s, %s, %s, 'makeup', %s, %s::time, %s, false, true, %s, %s)
                ON CONFLICT (series_id, on_date) DO NOTHING
                RETURNING id
                """,
                (tenant_id, series_id, on_date, on_date, start_time, teacher_user_id,
                 credit_id, created_by_user_id),
            )
            row = cur.fetchone()
            if not row:
                raise SchedulingError("That date already has a recorded change on this series.")
            exception_id = row["id"]
            cur.execute(
                "UPDATE makeup_credits SET consumed_exception_id = %s WHERE id = %s",
                (exception_id, credit_id),
            )

    return {
        "creditId": str(credit["id"]),
        "studentId": str(credit["student_id"]),
        "exceptionId": str(exception_id) if exception_id else None,
    }


# ── terms ────────────────────────────────────────────────────────────────


def terms(conn, tenant_id: str) -> list[dict[str, Any]]:
    """The studio's calendar spine, most recent first, closures attached."""

    rows = fetch_all(
        conn,
        """
        SELECT t.id, t.name, t.is_active,
               to_char(t.starts_on, 'YYYY-MM-DD') AS starts_on,
               to_char(t.ends_on, 'YYYY-MM-DD')   AS ends_on,
               (SELECT count(*) FROM term_closures tc
                 WHERE tc.tenant_id = t.tenant_id
                   AND tc.on_date BETWEEN t.starts_on AND t.ends_on) AS closure_count
        FROM terms t
        WHERE t.tenant_id = %s
        ORDER BY t.starts_on DESC
        """,
        (tenant_id,),
    )
    return rows


def create_term(
    conn, tenant_id: str, *, name: str, starts_on: date, ends_on: date
) -> dict[str, Any]:
    """Add a term. Overlap is allowed — studios run holiday programmes."""

    if not name.strip():
        raise SchedulingError("A term needs a name.")
    if ends_on < starts_on:
        raise SchedulingError("A term cannot end before it starts.")

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO terms (tenant_id, name, starts_on, ends_on)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, name) DO NOTHING
            RETURNING id, name,
                      to_char(starts_on, 'YYYY-MM-DD') AS starts_on,
                      to_char(ends_on, 'YYYY-MM-DD')   AS ends_on
            """,
            (tenant_id, name.strip(), starts_on, ends_on),
        )
        row = cur.fetchone()
    if not row:
        raise SchedulingError(f"There is already a term called “{name.strip()}”.")
    return row


def closures(conn, tenant_id: str, *, start: date, end: date) -> list[dict[str, Any]]:
    """Dates in the range when nothing runs."""

    return fetch_all(
        conn,
        """
        SELECT to_char(on_date, 'YYYY-MM-DD') AS on_date, label
        FROM term_closures
        WHERE tenant_id = %s AND on_date BETWEEN %s AND %s
        ORDER BY on_date
        """,
        (tenant_id, start, end),
    )


def set_closure(conn, tenant_id: str, *, on_date: date, label: str = "") -> None:
    """Mark a date closed, or update its label."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO term_closures (tenant_id, on_date, label)
            VALUES (%s, %s, %s)
            ON CONFLICT (tenant_id, on_date) DO UPDATE SET label = EXCLUDED.label
            """,
            (tenant_id, on_date, label),
        )


def clear_closure(conn, tenant_id: str, *, on_date: date) -> None:
    """Reopen a date."""

    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM term_closures WHERE tenant_id = %s AND on_date = %s",
            (tenant_id, on_date),
        )
