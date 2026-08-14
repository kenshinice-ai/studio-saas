"""Per-family calendar feeds — the cheapest lesson reminder there is.

A studio replacing a product that bundled unlimited SMS is about to start paying
per message, and the largest slice of that traffic is the routine "your lesson
is tomorrow". A subscription feed removes that slice entirely: the family
subscribes once, the lessons live in their own phone calendar from then on,
reschedules sync, and the phone reminds them on whatever settings they already
prefer. It costs nothing per family and nothing per month.

**What it cannot do, by design.** Calendar clients poll on their own schedule
and Google can take hours. A feed is therefore an excellent channel for "your
lessons this term" and a useless one for "your lesson in two hours is
cancelled". That distinction is the reason the notification router keeps
same-day changes on SMS, and it belongs in a docstring rather than in a support
conversation six weeks after launch.

The feed URL *is* the credential, so the database stores a hash of the token
rather than the token, exactly as student access codes do. Revocation is a
timestamp, not a delete: a family that loses a phone can be cut off without
erasing the record that they were ever subscribed.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from ..calendar_export import CalendarDocument, CalendarEvent
from ..db import fetch_all, fetch_one


class SubscriptionError(RuntimeError):
    """A calendar subscription could not be created or resolved."""


def _hash(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create(
    conn,
    tenant_id: str,
    *,
    scope: str,
    billing_account_id: str | None = None,
    student_id: str | None = None,
    teacher_user_id: str | None = None,
    label: str = "",
    created_by_user_id: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Issue a subscription and return ``(raw_token, row)``.

    The raw token is returned exactly once — it is never stored and cannot be
    recovered. A family that loses the link gets a new subscription rather than
    a copy of the old one, which also means a lost link can be revoked
    independently of the replacement.
    """

    if scope not in {"family", "student", "teacher"}:
        raise SubscriptionError(f"Unknown subscription scope: {scope}")

    raw_token = secrets.token_urlsafe(32)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO calendar_subscriptions
                (tenant_id, scope, billing_account_id, student_id, teacher_user_id,
                 token_hash, label, created_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id, scope, label, created_at
            """,
            (tenant_id, scope, billing_account_id, student_id, teacher_user_id,
             _hash(raw_token), label, created_by_user_id),
        )
        row = cur.fetchone()
    return raw_token, row


def resolve(conn, raw_token: object) -> dict[str, Any] | None:
    """Find a live subscription by its token.

    Deliberately not tenant-scoped: the token arrives from a calendar client
    with no session and no tenant header, so it has to identify the tenant
    itself. That is safe because the token is 256 bits of entropy and is matched
    by hash — but it does mean every caller must read the tenant from the row it
    gets back and never from anything the request supplied.
    """

    token = str(raw_token or "").strip()
    if not token:
        return None
    return fetch_one(
        conn,
        """
        SELECT cs.id, cs.tenant_id, cs.scope, cs.billing_account_id,
               cs.student_id, cs.teacher_user_id, cs.label,
               t.name AS tenant_name, t.slug AS tenant_slug,
               t.timezone AS timezone_name, t.address
        FROM calendar_subscriptions cs
        JOIN tenants t ON t.id = cs.tenant_id
        WHERE cs.token_hash = %s AND cs.revoked_at IS NULL
        """,
        (_hash(token),),
    )


def revoke(conn, tenant_id: str, subscription_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE calendar_subscriptions SET revoked_at = now()
             WHERE tenant_id = %s AND id = %s AND revoked_at IS NULL
            """,
            (tenant_id, subscription_id),
        )


def touch(conn, subscription_id: str) -> None:
    """Record a fetch, so a studio can see which families actually subscribed."""

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE calendar_subscriptions
               SET last_fetched_at = now(), fetch_count = fetch_count + 1
             WHERE id = %s
            """,
            (subscription_id,),
        )


def build_document(
    conn,
    subscription: dict[str, Any],
    *,
    weeks_ahead: int = 26,
    today: date | None = None,
    generated_at: datetime | None = None,
) -> CalendarDocument:
    """Expand a subscription's recurring lessons into dated calendar events.

    Cancelled dates are exported as cancelled events rather than omitted. A
    lesson that silently disappears from a parent's calendar looks like a bug in
    the calendar; one that says "cancelled" says what the studio meant.
    """

    tenant_id = str(subscription["tenant_id"])
    start = today or date.today()
    end = start + timedelta(weeks=weeks_ahead)

    if subscription["scope"] == "family":
        where, params = (
            """
            ls.student_id IN (
                SELECT student_id FROM billing_account_members
                 WHERE tenant_id = %s AND billing_account_id = %s
            )
            """,
            (tenant_id, subscription["billing_account_id"]),
        )
    elif subscription["scope"] == "student":
        where, params = "ls.student_id = %s", (subscription["student_id"],)
    else:
        where, params = "ls.teacher_user_id = %s", (subscription["teacher_user_id"],)

    series_rows = fetch_all(
        conn,
        f"""
        SELECT ls.id, ls.weekday, ls.start_time, ls.duration_minutes, ls.room,
               ls.starts_on, ls.ends_on, ls.status, ls.paused_from, ls.paused_to,
               s.display_name AS student_name,
               COALESCE(c.name, '') AS course_name
        FROM lesson_series ls
        JOIN students s ON s.tenant_id = ls.tenant_id AND s.id = ls.student_id
        LEFT JOIN courses c ON c.id = ls.course_id
        WHERE ls.tenant_id = %s AND ls.status <> 'ended' AND ({where})
        ORDER BY ls.weekday, ls.start_time
        """,
        (tenant_id, *params),
    )

    exception_rows = fetch_all(
        conn,
        """
        SELECT series_id, on_date, kind, moved_to_date, moved_to_start_time
        FROM lesson_exceptions
        WHERE tenant_id = %s AND on_date BETWEEN %s AND %s
        """,
        (tenant_id, start, end),
    )
    exceptions: dict[tuple[str, date], dict[str, Any]] = {
        (str(row["series_id"]), row["on_date"]): row for row in exception_rows
    }

    closures = {
        row["on_date"]
        for row in fetch_all(
            conn,
            "SELECT on_date FROM term_closures WHERE tenant_id = %s AND on_date BETWEEN %s AND %s",
            (tenant_id, start, end),
        )
    }

    events: list[CalendarEvent] = []
    for series in series_rows:
        cursor_date = max(start, series["starts_on"])
        # Python's Monday is 0 and so is the schema's; no conversion needed, and
        # saying so here stops somebody "fixing" it later.
        offset = (int(series["weekday"]) - cursor_date.weekday()) % 7
        cursor_date = cursor_date + timedelta(days=offset)
        last = min(end, series["ends_on"] or end)

        while cursor_date <= last:
            skip = cursor_date in closures
            paused = (
                series["paused_from"]
                and series["paused_to"]
                and series["paused_from"] <= cursor_date <= series["paused_to"]
            )
            exception = exceptions.get((str(series["id"]), cursor_date))

            if not skip and not paused:
                on_date = cursor_date
                start_time = series["start_time"]
                summary = f"{series['student_name']} · {series['course_name']}".strip(" ·")
                cancelled = False

                if exception:
                    if exception["kind"] in {"cancelled_by_student", "cancelled_by_studio"}:
                        cancelled = True
                    elif exception["kind"] == "rescheduled" and exception["moved_to_date"]:
                        on_date = exception["moved_to_date"]
                        start_time = exception["moved_to_start_time"] or start_time

                starts = datetime.combine(on_date, start_time)
                events.append(
                    CalendarEvent(
                        uid=f"lesson-{series['id']}-{cursor_date.isoformat()}",
                        summary=("CANCELLED · " if cancelled else "") + summary,
                        description=series["course_name"],
                        location=series["room"] or (subscription.get("address") or ""),
                        starts_local=starts,
                        ends_local=starts + timedelta(minutes=int(series["duration_minutes"])),
                        duration_minutes=int(series["duration_minutes"]),
                        duration_source="lesson_series",
                        one_to_one=True,
                    )
                )
            cursor_date += timedelta(days=7)

    events.sort(key=lambda event: event.starts_local)
    label = subscription.get("label") or subscription["tenant_name"]
    return CalendarDocument(
        kind="family_subscription",
        calendar_name=f"{subscription['tenant_name']} · {label}",
        timezone_name=subscription["timezone_name"] or "Australia/Melbourne",
        location=subscription.get("address") or "",
        filename=f"{subscription['tenant_slug']}-lessons.ics",
        events=tuple(events),
        generated_at=generated_at or datetime.now(),
        includes_student_names=True,
        subscribable=True,
    )
