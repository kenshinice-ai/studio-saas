"""Student progress reports, assembled from what the studio already records.

A studio that promises a progress report every few lessons is making a service
commitment that, in almost every case, is kept by a teacher writing one from
memory on a Sunday night. The material for it has been accumulating all along —
attendance, lesson notes, repertoire, exam progress, consented media — it has
simply never been collected into a deliverable.

Two design decisions carry the weight:

**Draft, then publish.** The system assembles; a teacher edits and publishes.
Nothing reaches a parent that a human has not read, because a report is a
professional judgement about a child and an automatically-sent one is worth
less than none.

**Published content is frozen.** The assembled figures are copied into the row
at publication. A later correction to an attendance record must not silently
rewrite a report a parent has already read and may have paid attention to.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from ..db import fetch_all, fetch_one


class ProgressReportError(RuntimeError):
    """A report could not be assembled or published."""


def settings(conn, tenant_id: str) -> dict[str, Any]:
    """Cadence and which sections a studio includes.

    Falls back to sensible defaults rather than raising when a tenant has never
    configured this: a studio should be able to produce its first report without
    visiting a settings page first.
    """

    row = fetch_one(
        conn,
        """
        SELECT cadence_kind, cadence_lessons, include_attendance, include_notes,
               include_repertoire, include_exam, include_media
        FROM progress_report_settings WHERE tenant_id = %s
        """,
        (tenant_id,),
    )
    return row or {
        "cadence_kind": "lessons",
        "cadence_lessons": 6,
        "include_attendance": True,
        "include_notes": True,
        "include_repertoire": True,
        "include_exam": True,
        "include_media": False,
    }


def assemble(
    conn,
    tenant_id: str,
    student_id: str,
    *,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    """Gather the record for one student over one period.

    Read-only. Produces the content a draft is created from, and is also what
    the teacher's editing screen re-reads if they want to refresh before
    publishing.
    """

    config = settings(conn, tenant_id)
    content: dict[str, Any] = {
        "periodStart": period_start.isoformat(),
        "periodEnd": period_end.isoformat(),
    }

    if config["include_attendance"]:
        row = fetch_one(
            conn,
            """
            SELECT COUNT(*) AS scheduled,
                   COUNT(*) FILTER (WHERE status = 'scheduled') AS attended,
                   COUNT(*) FILTER (WHERE status = 'cancelled') AS cancelled,
                   COUNT(*) FILTER (WHERE status = 'makeup')    AS makeups
            FROM daily_roster_entries
            WHERE tenant_id = %s AND student_id = %s AND roster_date BETWEEN %s AND %s
            """,
            (tenant_id, student_id, period_start, period_end),
        ) or {}
        scheduled = int(row.get("scheduled") or 0)
        attended = int(row.get("attended") or 0)
        content["attendance"] = {
            "scheduled": scheduled,
            "attended": attended,
            "cancelled": int(row.get("cancelled") or 0),
            "makeups": int(row.get("makeups") or 0),
            # Guarding the divide matters: a student enrolled mid-period has a
            # zero denominator, and a report that says "0% attendance" about a
            # child who has been to every lesson is worse than one that omits
            # the figure.
            "ratePercent": round(attended * 100 / scheduled) if scheduled else None,
        }

    if config["include_notes"]:
        # ``content`` is stored as jsonb, so every value here has to survive
        # json.dumps. psycopg hands back date objects, which do not — and the
        # failure is a 500 at creation time, on exactly the studios that write
        # the most lesson notes. Casting in SQL rather than post-processing in
        # Python keeps the stored shape identical to what the API returns.
        content["lessons"] = fetch_all(
            conn,
            """
            SELECT to_char(a.class_date, 'YYYY-MM-DD') AS class_date,
                   a.note, c.name AS course_name
            FROM attendance_sessions a
            LEFT JOIN courses c ON c.id = a.course_id
            WHERE a.tenant_id = %s AND a.student_id = %s
              AND a.class_date BETWEEN %s AND %s
              AND a.reversed_at IS NULL AND length(a.note) > 0
            ORDER BY a.class_date
            """,
            (tenant_id, student_id, period_start, period_end),
        )

    if config["include_media"]:
        content["media"] = fetch_all(
            conn,
            """
            SELECT p.id::text AS id, p.title,
                   to_char(p.artwork_date, 'YYYY-MM-DD') AS artwork_date
            FROM portfolio_items p
            WHERE p.tenant_id = %s AND p.student_id = %s
              AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL
              AND (p.artwork_date IS NULL OR p.artwork_date BETWEEN %s AND %s)
            ORDER BY p.artwork_date DESC NULLS LAST
            LIMIT 8
            """,
            (tenant_id, student_id, period_start, period_end),
        )

    return content


def create_draft(
    conn,
    tenant_id: str,
    student_id: str,
    *,
    period_start: date,
    period_end: date,
    teacher_user_id: str | None = None,
    term_id: str | None = None,
) -> dict[str, Any]:
    """Assemble a period into a draft for a teacher to finish."""

    content = assemble(conn, tenant_id, student_id, period_start=period_start, period_end=period_end)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO progress_reports
                (tenant_id, student_id, teacher_user_id, term_id,
                 period_start, period_end, content)
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            RETURNING id, status, period_start, period_end
            """,
            (tenant_id, student_id, teacher_user_id, term_id,
             period_start, period_end, json.dumps(content)),
        )
        return cur.fetchone()


def publish(
    conn, tenant_id: str, report_id: str, *, published_by_user_id: str
) -> dict[str, Any]:
    """Freeze and release a report to the family."""

    report = fetch_one(
        conn,
        "SELECT status, teacher_comment FROM progress_reports WHERE tenant_id = %s AND id = %s",
        (tenant_id, report_id),
    )
    if not report:
        raise ProgressReportError("Report not found.")
    if report["status"] == "published":
        raise ProgressReportError("This report has already been published.")
    if not (report["teacher_comment"] or "").strip():
        raise ProgressReportError(
            "A report needs the teacher's own comment before it goes to a family. "
            "The figures are the evidence; the comment is the point."
        )

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE progress_reports
               SET status = 'published', published_at = now(),
                   published_by_user_id = %s, updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status = 'draft'
            RETURNING id, status, published_at
            """,
            (published_by_user_id, tenant_id, report_id),
        )
        published = cur.fetchone()
    if not published:
        raise ProgressReportError("Report changed while it was being published.")
    return published


def overdue(conn, tenant_id: str, *, as_of: date | None = None) -> list[dict[str, Any]]:
    """Which reports are due and unwritten, and whose they are.

    This is what turns the sentence on a studio's website into something
    somebody can manage on a Monday morning.
    """

    when = as_of or date.today()
    return fetch_all(
        conn,
        """
        SELECT r.id, r.student_id, s.display_name, r.period_end,
               r.teacher_user_id, u.full_name AS teacher_name,
               (%s::date - r.period_end) AS days_overdue
        FROM progress_reports r
        JOIN students s ON s.tenant_id = r.tenant_id AND s.id = r.student_id
        LEFT JOIN users u ON u.id = r.teacher_user_id
        WHERE r.tenant_id = %s AND r.status = 'draft' AND r.period_end < %s::date
        ORDER BY r.period_end
        """,
        (when, tenant_id, when),
    )
