"""Students who were expected and did not come, several times running.

Lee, 2026-10-14: the dashboard's "students who have stopped coming" means
"missed the last 3 lessons they were scheduled for", not "no class for 90
days". The day count catches a family that has gone quiet, but only after
three months, and it flags a student who simply has nothing booked.

**Expected** on a date, for one student, is any of:

* membership of a weekly class (``class_schedule_students``) on that class's
  weekday, from the day they were added — unless the class was cancelled that
  day (``class_schedule_exceptions``), the studio was closed
  (``term_closures``), or the day's roster cancelled them explicitly;
* an explicit roster entry that is scheduled or a make-up;
* a private lesson from :func:`scheduling.occurrences` — unless the studio
  cancelled it. A lesson the family cancelled still counts as missed: notice
  or not, they did not come, and that is what this list is for.

**Came** means a check-in that has not been reversed. The run counts the
expected dates *after* the student's last check-in, so a check-in on any day —
a make-up nobody put on the roster, say — ends it.

A studio that records no check-ins at all in the window gets an empty list:
without check-ins every expected lesson looks missed, and a list naming every
student is noise, not an exception.

Only dates before today count. Today's class may simply not have been checked
in yet, and a list that flags everybody at 9 a.m. would teach the studio to
ignore it.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from ..db import fetch_all
from . import scheduling

#: Missed lessons in a row before a student is listed (Lee, 2026-10-14).
DEFAULT_STREAK = 3

#: How far back to look. Ten weeks covers three weekly lessons with room for a
#: term break in between, and keeps the query bounded.
LOOKBACK_DAYS = 70


def _daterange(start: date, end: date):
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def missed_streaks(
    conn, tenant_id: str, *, today: date, streak: int = DEFAULT_STREAK,
    lookback_days: int = LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    """Students whose most recent ``streak`` expected lessons were all missed.

    Returns one row per student, longest run first:
    ``{studentId, studentName, missed, lastAttended}``. ``missed`` is the full
    run, which can be longer than ``streak``; ``lastAttended`` is ISO or None.
    """

    end = today - timedelta(days=1)
    start = today - timedelta(days=lookback_days)
    if end < start:
        return []

    names: dict[str, str] = {
        str(row["id"]): row["display_name"]
        for row in fetch_all(
            conn,
            "SELECT id, display_name FROM students WHERE tenant_id = %s AND status <> 'archived'",
            (tenant_id,),
        )
    }

    closures = {
        row["on_date"]
        for row in fetch_all(
            conn,
            "SELECT on_date FROM term_closures WHERE tenant_id = %s AND on_date BETWEEN %s AND %s",
            (tenant_id, start, end),
        )
    }
    class_cancelled = {
        (str(row["schedule_id"]), row["on_date"])
        for row in fetch_all(
            conn,
            """
            SELECT schedule_id, on_date FROM class_schedule_exceptions
             WHERE tenant_id = %s AND cancelled AND on_date BETWEEN %s AND %s
            """,
            (tenant_id, start, end),
        )
    }
    roster_rows = fetch_all(
        conn,
        """
        SELECT student_id, roster_date, status FROM daily_roster_entries
         WHERE tenant_id = %s AND roster_date BETWEEN %s AND %s
        """,
        (tenant_id, start, end),
    )
    roster_cancelled = {
        (str(row["student_id"]), row["roster_date"])
        for row in roster_rows if row["status"] == "cancelled"
    }

    expected: set[tuple[str, date]] = set()

    memberships = fetch_all(
        conn,
        """
        SELECT css.student_id, css.schedule_id, cs.weekday,
               css.added_at::date AS added_on
        FROM class_schedule_students css
        JOIN class_schedules cs ON cs.tenant_id = css.tenant_id AND cs.id = css.schedule_id
        WHERE css.tenant_id = %s AND cs.is_active
        """,
        (tenant_id,),
    )
    for row in memberships:
        student_id = str(row["student_id"])
        schedule_id = str(row["schedule_id"])
        first = max(start, row["added_on"])
        for day in _daterange(first, end):
            # class_schedules.weekday follows JS getDay(): Sunday = 0.
            if day.isoweekday() % 7 != int(row["weekday"]):
                continue
            if day in closures or (schedule_id, day) in class_cancelled:
                continue
            if (student_id, day) in roster_cancelled:
                continue
            expected.add((student_id, day))

    for row in roster_rows:
        if row["status"] in ("scheduled", "makeup"):
            expected.add((str(row["student_id"]), row["roster_date"]))

    for row in scheduling.occurrences(conn, tenant_id, start=start, end=end):
        if row["exception_kind"] == "cancelled_by_studio":
            continue
        on = row["moved_to_date"] if row["exception_kind"] == "rescheduled" and row["moved_to_date"] else row["on_date"]
        day = date.fromisoformat(on)
        if start <= day <= end:
            expected.add((str(row["student_id"]), day))

    last_attended: dict[str, date] = {}
    any_in_window = False
    for row in fetch_all(
        conn,
        """
        SELECT a.student_id,
               COALESCE(a.class_date, (a.attended_at AT TIME ZONE COALESCE(t.timezone, 'Australia/Melbourne'))::date) AS on_date
        FROM attendance_sessions a
        JOIN tenants t ON t.id = a.tenant_id
        WHERE a.tenant_id = %s AND a.reversed_at IS NULL
        """,
        (tenant_id,),
    ):
        student_id, on = str(row["student_id"]), row["on_date"]
        if on > end:
            continue
        any_in_window = any_in_window or on >= start
        if student_id not in last_attended or on > last_attended[student_id]:
            last_attended[student_id] = on

    if not any_in_window:
        return []

    by_student: dict[str, list[date]] = {}
    for student_id, day in expected:
        if student_id in names:
            by_student.setdefault(student_id, []).append(day)

    out = []
    for student_id, days in by_student.items():
        seen = last_attended.get(student_id)
        run = sum(1 for day in days if seen is None or day > seen)
        if run >= streak:
            out.append({
                "studentId": student_id,
                "studentName": names[student_id],
                "missed": run,
                "lastAttended": seen.isoformat() if seen else None,
            })
    out.sort(key=lambda row: (-row["missed"], row["studentName"]))
    return out
