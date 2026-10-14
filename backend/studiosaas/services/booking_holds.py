"""A booking request keeps its place for a while.

Until v10.21 a pending request on the public timetable held nothing: capacity
was counted only at approval. That was safe — a request nobody looked at could
not lock out a family who would actually come — but a parent who had asked had
no idea whether the place was theirs, and could lose it to someone who asked
an hour later and was approved first.

Lee decided on 2026-10-14 to hold the place for a fixed time, 48 hours by
default, set per tenant. The rules:

* A request holds a place only if a place is free when it arrives. A full
  class still takes requests; they simply hold nothing.
* One phone holds at most one place per tenant at a time. The form needs no
  account, so without this one person could fill a class with requests.
* A hold that has expired stops counting the moment it expires. Nothing has
  to run at that moment: every count asks ``hold_expires_at > now()``.
* The request itself stays pending after its hold lapses. Somebody can still
  approve it — if there is room by then.

Every count that decides a seat — the public page, the request, the approval —
uses :data:`SEAT_TAKEN` and locks the class row first, so two requests for the
last place cannot both take it.
"""

from __future__ import annotations

from typing import Any

from ..db import fetch_one

DEFAULT_HOLD_HOURS = 48
MAX_HOLD_HOURS = 168

#: A booking that takes a seat: approved, or pending with a hold still running.
#: Written for a table aliased or unaliased as ``class_bookings``.
SEAT_TAKEN = "(status = 'approved' OR (status = 'pending' AND hold_expires_at > now()))"


def clamp_hours(value: Any) -> int:
    """A stored or submitted setting, made safe. Junk falls back to the default."""

    try:
        hours = int(value)
    except (TypeError, ValueError):
        return DEFAULT_HOLD_HOURS
    return max(0, min(MAX_HOLD_HOURS, hours))


def hold_hours(conn, tenant_id: str) -> int:
    """How long this tenant holds a place. 0 means requests hold nothing."""

    row = fetch_one(
        conn,
        "SELECT settings->'booking_hold_hours' AS hours FROM tenants WHERE id = %s",
        (tenant_id,),
    )
    if not row or row["hours"] is None:
        return DEFAULT_HOLD_HOURS
    return clamp_hours(row["hours"])


def lock_class(cur, schedule_id: str) -> None:
    """Serialise every seat decision for one class.

    Capacity is a count, not a row, so no unique index can protect the last
    place. Locking the class row makes the count and the write that follows it
    one step for everyone deciding about this class.
    """

    cur.execute("SELECT 1 FROM class_schedules WHERE id = %s FOR UPDATE", (schedule_id,))


def seats_taken(cur, schedule_id: str, on_date, *, exclude_booking_id: str | None = None) -> int:
    """Enrolled students plus bookings that take a seat on this date."""

    cur.execute(
        f"""
        SELECT (SELECT count(*) FROM class_schedule_students css
                 WHERE css.schedule_id = %s)
             + (SELECT count(*) FROM class_bookings
                 WHERE schedule_id = %s AND on_date = %s
                   AND (%s::uuid IS NULL OR id <> %s::uuid)
                   AND {SEAT_TAKEN}) AS taken
        """,
        (schedule_id, schedule_id, on_date, exclude_booking_id, exclude_booking_id),
    )
    return int((cur.fetchone() or {}).get("taken") or 0)


def phone_holds_a_place(cur, tenant_id: str, phone: str) -> bool:
    """Whether this phone already holds a place anywhere in this tenant."""

    cur.execute(
        """
        SELECT 1 FROM class_bookings
         WHERE tenant_id = %s AND contact_phone = %s
           AND status = 'pending' AND hold_expires_at > now()
         LIMIT 1
        """,
        (tenant_id, phone),
    )
    return cur.fetchone() is not None
