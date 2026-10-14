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
from datetime import date, datetime, time, timedelta
from typing import Any

from ..calendar_export import CalendarDocument, CalendarEvent
from ..db import fetch_all, fetch_one
from ..tenant_context import bind_tenant_session
from . import scheduling


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
    """Find a live subscription by its token, and bind ``conn`` to its tenant.

    The token arrives from a calendar client with no session and no tenant
    header, so it has to identify the tenant itself. ``calendar_subscriptions``
    is under forced row-level security, which hides every row from a
    connection that has no tenant yet — so the first step asks the one database
    function that may look across tenants (migration 0048) for the owner of
    this token hash, and nothing else. The connection is then bound to that
    tenant, and the subscription and every lesson after it are read under the
    ordinary tenant policy.

    Binding is a side effect on purpose: everything the feed reads next must be
    that tenant's, and the tenant must come from the row, never from anything
    the request supplied. Callers pass a connection used for nothing else.
    """

    token = str(raw_token or "").strip()
    if not token:
        return None
    token_hash = _hash(token)
    owner = fetch_one(
        conn,
        "SELECT calendar_subscription_tenant(%s) AS tenant_id",
        (token_hash,),
    )
    if not owner or not owner["tenant_id"]:
        return None
    tenant_id = str(owner["tenant_id"])
    bind_tenant_session(conn, tenant_id)
    return fetch_one(
        conn,
        """
        SELECT cs.id, cs.tenant_id, cs.scope, cs.billing_account_id,
               cs.student_id, cs.teacher_user_id, cs.label,
               t.name AS tenant_name, t.slug AS tenant_slug,
               t.timezone AS timezone_name, t.address
        FROM calendar_subscriptions cs
        JOIN tenants t ON t.id = cs.tenant_id
        WHERE cs.tenant_id = %s AND cs.token_hash = %s AND cs.revoked_at IS NULL
        """,
        (tenant_id, token_hash),
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


def _student_ids(conn, tenant_id: str, subscription: dict[str, Any]) -> set[str] | None:
    """The students a subscription covers, or ``None`` for a teacher's feed."""

    if subscription["scope"] == "teacher":
        return None
    if subscription["scope"] == "student":
        return {str(subscription["student_id"])}
    rows = fetch_all(
        conn,
        """
        SELECT student_id FROM billing_account_members
         WHERE tenant_id = %s AND billing_account_id = %s
        """,
        (tenant_id, subscription["billing_account_id"]),
    )
    return {str(row["student_id"]) for row in rows}


def build_document(
    conn,
    subscription: dict[str, Any],
    *,
    weeks_ahead: int = 26,
    today: date | None = None,
    generated_at: datetime | None = None,
) -> CalendarDocument:
    """Turn a subscription's lessons into dated calendar events.

    The lessons come from :func:`scheduling.occurrences` — the same expansion
    the CMS calendar shows — rather than from a second walk over the series
    here. This module used to keep its own, and it drifted three ways: it read
    ``weekday`` as Monday = 0 while the schema stores Sunday = 0, so every
    lesson landed a day late; it never saw make-up lessons, which by definition
    fall on a day the series does not run; and it applied pause windows to
    series that were not paused. One expansion, one set of rules.

    Cancelled dates are exported as cancelled events rather than omitted. A
    lesson that silently disappears from a parent's calendar looks like a bug in
    the calendar; one that says "cancelled" says what the studio meant.
    """

    tenant_id = str(subscription["tenant_id"])
    start = today or date.today()
    end = start + timedelta(weeks=weeks_ahead)

    teacher_user_id = (
        str(subscription["teacher_user_id"]) if subscription["scope"] == "teacher" else None
    )
    students = _student_ids(conn, tenant_id, subscription)
    rows = scheduling.occurrences(
        conn, tenant_id, start=start, end=end, teacher_user_id=teacher_user_id,
    )
    if students is not None:
        rows = [row for row in rows if str(row["student_id"]) in students]

    course_names = {
        str(row["id"]): row["course_name"]
        for row in fetch_all(
            conn,
            """
            SELECT ls.id, COALESCE(c.name, '') AS course_name
            FROM lesson_series ls
            LEFT JOIN courses c ON c.id = ls.course_id
            WHERE ls.tenant_id = %s
            """,
            (tenant_id,),
        )
    }

    events: list[CalendarEvent] = []
    for row in rows:
        kind = row["exception_kind"]
        on_date = date.fromisoformat(row["on_date"])
        start_time = row["start_time"]
        if kind == "rescheduled" and row["moved_to_date"]:
            # The lesson now happens on the new date. The uid stays the one of
            # the date it was moved from, so a calendar app moves the event it
            # already holds instead of adding a second one.
            on_date = date.fromisoformat(row["moved_to_date"])
            start_time = row["moved_to_start_time"] or start_time
        cancelled = kind in {"cancelled_by_student", "cancelled_by_studio"}

        course_name = course_names.get(str(row["series_id"]), "")
        summary = f"{row['student_name']} · {course_name}".strip(" ·")
        if kind == "makeup":
            summary = f"Make-up · {summary}"
        if cancelled:
            summary = f"CANCELLED · {summary}"

        starts = datetime.combine(on_date, time.fromisoformat(start_time))
        duration = int(row["duration_minutes"])
        events.append(
            CalendarEvent(
                uid=f"lesson-{row['series_id']}-{row['on_date']}",
                summary=summary,
                description=course_name,
                location=row["room"] or (subscription.get("address") or ""),
                starts_local=starts,
                ends_local=starts + timedelta(minutes=duration),
                duration_minutes=duration,
                duration_source="lesson_series",
                one_to_one=True,
            )
        )

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
