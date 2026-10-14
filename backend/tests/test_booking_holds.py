"""A booking request keeps a free place for a while (Lee, 2026-10-14).

These go through the public routes with the application's own database role,
because the counts run under row-level security and take a row lock — both of
which a superuser connection would quietly skip.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT hold_expires_at FROM class_bookings LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 — any failure means "no usable database"
        return False


requires_db = pytest.mark.skipif(
    not _database_available(),
    reason="needs a PostgreSQL with migrations through 0049 applied",
)


def _next_weekday(anchor: date, weekday_js: int) -> date:
    for step in range(8):
        day = anchor + timedelta(days=step)
        if (day.weekday() + 1) % 7 == weekday_js:
            return day
    raise AssertionError("unreachable")


def _make_world(capacity: int, hold_hours: int | None = None):
    from _cms_sources import owner_connection as connect

    tenant_id = str(uuid.uuid4())
    slug = f"h{tenant_id[:8]}"
    # Tomorrow or later, inside the two weeks the page publishes.
    day = date.today() + timedelta(days=2)
    weekday = (day.weekday() + 1) % 7
    settings = {"website_profile": {"show_timetable": True, "show_timetable_booking": True,
                                    "timetable_weeks": 2, "timetable_fields": {"capacity": True}}}
    if hold_hours is not None:
        settings["booking_hold_hours"] = hold_hours
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code, timezone, settings)
                VALUES (%s, 'Hold Test', %s, 'active', 'starter', 'Australia/Melbourne', %s::jsonb)
                """,
                (tenant_id, slug, json.dumps(settings)),
            )
            cur.execute(
                """
                INSERT INTO class_schedules (tenant_id, label, weekday, start_time, capacity,
                                             is_active, is_public)
                VALUES (%s, 'Saturday group', %s, '10:00', %s, true, true) RETURNING id
                """,
                (tenant_id, weekday, capacity),
            )
            schedule_id = str(cur.fetchone()["id"])
        conn.commit()
    return {"tenant_id": tenant_id, "slug": slug, "date": day, "schedule_id": schedule_id}


def _drop_world(world) -> None:
    from _cms_sources import owner_connection as connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (world["tenant_id"],))
        conn.commit()


@pytest.fixture()
def world():
    made = _make_world(capacity=2)
    yield made
    _drop_world(made)


@pytest.fixture()
def runtime_role():
    from studiosaas.db import connect, fetch_one

    with connect() as conn:
        row = fetch_one(
            conn, "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user", ()
        )
    if not row or row["rolsuper"] or row["rolbypassrls"]:
        pytest.skip("needs the runtime role; this connection bypasses row-level security")


def _book(app, world, phone: str, name: str = "Ada Parent"):
    return app.test_client().post(
        f"/v1/public/{world['slug']}/timetable/book",
        json={"name": name, "phone": phone, "date": world["date"].isoformat(), "start": "10:00"},
    )


def _seats_left(app, world) -> int:
    data = app.test_client().get(f"/v1/public/{world['slug']}/timetable").get_json()
    for day in data["days"]:
        for item in day["classes"]:
            if item["date"] == world["date"].isoformat() and item["start"] == "10:00":
                return item["seatsLeft"]
    raise AssertionError(f"class not on the timetable: {data}")


def _holds(world) -> list:
    from _cms_sources import owner_connection as connect

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT contact_phone, hold_expires_at,
                       hold_expires_at - created_at AS held_for
                FROM class_bookings WHERE tenant_id = %s ORDER BY created_at
                """,
                (world["tenant_id"],),
            )
            return cur.fetchall()


@requires_db
def test_a_request_for_a_free_place_holds_it_for_48_hours(app, runtime_role, world):
    assert _seats_left(app, world) == 2

    response = _book(app, world, "0400 000 001")

    assert response.status_code == 200
    assert response.get_json()["holdHours"] == 48
    rows = _holds(world)
    assert rows[0]["hold_expires_at"] is not None
    assert timedelta(hours=47, minutes=59) < rows[0]["held_for"] <= timedelta(hours=48, seconds=5)
    assert _seats_left(app, world) == 1, "The held place is still shown as free"


@requires_db
def test_one_phone_holds_one_place(app, runtime_role, world):
    _book(app, world, "0400 000 002")
    from _cms_sources import owner_connection as connect

    # A second class on another date in the same tenant.
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE class_schedules SET capacity = 5 WHERE id = %s", (world["schedule_id"],)
            )
        conn.commit()
    second = dict(world, date=world["date"] + timedelta(days=7))
    response = _book(app, second, "0400 000 002")

    assert response.status_code == 200
    held = [row for row in _holds(world) if row["hold_expires_at"] is not None]
    assert len(held) == 1, "One phone filled two places"


@requires_db
def test_a_full_class_still_takes_requests_but_they_hold_nothing(app, runtime_role, world):
    _book(app, world, "0400 000 003")
    _book(app, world, "0400 000 004")
    assert _seats_left(app, world) == 0

    response = _book(app, world, "0400 000 005")

    assert response.status_code == 200
    assert response.get_json()["seatsLeft"] == 0
    assert _holds(world)[-1]["hold_expires_at"] is None


@requires_db
def test_an_expired_hold_stops_counting_by_itself(app, runtime_role, world):
    from _cms_sources import owner_connection as connect

    _book(app, world, "0400 000 006")
    assert _seats_left(app, world) == 1
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE class_bookings SET hold_expires_at = now() - interval '1 minute' "
                "WHERE tenant_id = %s",
                (world["tenant_id"],),
            )
        conn.commit()

    assert _seats_left(app, world) == 2


@requires_db
def test_a_tenant_can_turn_holds_off(app, runtime_role):
    made = _make_world(capacity=2, hold_hours=0)
    try:
        response = _book(app, made, "0400 000 007")
        assert response.get_json()["holdHours"] == 0
        assert _holds(made)[0]["hold_expires_at"] is None
        assert _seats_left(app, made) == 2
    finally:
        _drop_world(made)


@requires_db
def test_the_reply_does_not_say_whether_this_request_got_a_hold(app, runtime_role, world):
    """Same body for the first request from a phone and for its second one."""

    _book(app, world, "0400 000 008")
    first = _book(app, dict(world, date=world["date"] + timedelta(days=7)), "0400 000 009").get_json()
    again = _book(app, dict(world, date=world["date"] + timedelta(days=7)), "0400 000 008").get_json()

    for key in ("holdHours",):
        assert first[key] == again[key]
    assert "held" not in again and "holdExpiresAt" not in again


@requires_db
def test_approval_respects_someone_elses_hold(app, runtime_role, monkeypatch):
    """Capacity 1: A holds the place, B does not. B cannot be approved; A can."""

    import importlib

    from studiosaas.tenant_context import bind_tenant_session

    routes = importlib.import_module("studiosaas.api_v1.scheduling")

    made = _make_world(capacity=1)
    try:
        _book(app, made, "0400 000 010", name="Ada Holder")
        _book(app, made, "0400 000 011", name="Ben Later")
        from _cms_sources import owner_connection as connect

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, contact_name FROM class_bookings WHERE tenant_id = %s",
                    (made["tenant_id"],),
                )
                ids = {row["contact_name"]: str(row["id"]) for row in cur.fetchall()}

        def tenant_context(conn):
            bind_tenant_session(conn, made["tenant_id"])
            return SimpleNamespace(tenant_id=made["tenant_id"])

        monkeypatch.setattr(routes, "_tenant_context", tenant_context)
        monkeypatch.setattr(routes, "_audit_request", lambda *a, **k: None)

        with app.test_request_context(json={"status": "approved"}):
            blocked = routes.review_class_booking.__wrapped__(ids["Ben Later"])
        with app.test_request_context(json={"status": "approved"}):
            allowed = routes.review_class_booking.__wrapped__(ids["Ada Holder"])

        def status(result):
            return result[1] if isinstance(result, tuple) else result.status_code

        assert status(blocked) == 409, "Approved over someone else's live hold"
        assert status(allowed) == 200, "The holder could not take the place it holds"
    finally:
        _drop_world(made)
