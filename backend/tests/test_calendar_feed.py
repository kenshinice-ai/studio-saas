"""The family calendar feed, requested the way a phone requests it.

From v10.0.0 the release notes told customers a family could subscribe to
their child's lessons. Until this test existed nothing ever requested
``/v1/public/calendar/<token>.ics``, and the feed was broken three ways:

1. Under the runtime role it could not find any subscription. The token lookup
   ran before the connection knew its tenant, and forced row-level security
   (migration 0042) hides every row from such a connection. Valid tokens got
   the same 404 as forged ones.
2. Every lesson landed one day late: the feed read ``weekday`` as Monday = 0,
   the schema stores Sunday = 0.
3. Make-up lessons never appeared.

So these tests go through the HTTP route with the application's own database
role, and they skip — rather than pass — on a connection that ignores
row-level security, because there the first defect cannot be seen.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT calendar_subscription_tenant('')")
        return True
    except Exception:  # noqa: BLE001 — any failure means "no usable database"
        return False


requires_db = pytest.mark.skipif(
    not _database_available(),
    reason="needs a PostgreSQL with migrations through 0048 applied",
)


def _runtime_role_obeys_rls() -> bool:
    from studiosaas.db import connect, fetch_one

    with connect() as conn:
        row = fetch_one(
            conn,
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user",
            (),
        )
    return bool(row) and not row["rolsuper"] and not row["rolbypassrls"]


def _next_weekday(anchor: date, weekday_js: int) -> date:
    """The next date on or after `anchor` whose JS getDay() is `weekday_js`."""

    for step in range(8):
        day = anchor + timedelta(days=step)
        if (day.weekday() + 1) % 7 == weekday_js:
            return day
    raise AssertionError("unreachable")


def _starts(day: date, hhmm: str = "160000") -> str:
    return f"{day:%Y%m%d}T{hhmm}"


@pytest.fixture()
def family_world():
    """A tenant, a family with one child on a Tuesday 16:00 lesson, and a
    second child in another family on the same Tuesday at 17:00."""

    from _cms_sources import owner_connection as connect
    from studiosaas.services import calendar_subscriptions, scheduling

    tenant_id = str(uuid.uuid4())
    slug = f"f{tenant_id[:8]}"
    starts_on = date.today() + timedelta(days=7)
    tuesday = _next_weekday(starts_on, 2)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code, timezone)
                VALUES (%s, 'Feed Test', %s, 'active', 'starter', 'Australia/Melbourne')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Priya', 'Priya Raman') RETURNING id
                """,
                (tenant_id,),
            )
            student_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Tom', 'Tom Other') RETURNING id
                """,
                (tenant_id,),
            )
            other_student_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO billing_accounts (id, tenant_id, name)
                VALUES (gen_random_uuid(), %s, 'Raman family') RETURNING id
                """,
                (tenant_id,),
            )
            account_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO billing_account_members (tenant_id, billing_account_id, student_id)
                VALUES (%s, %s, %s)
                """,
                (tenant_id, account_id, student_id),
            )
            cur.execute(
                """
                INSERT INTO users (id, email, full_name, password_hash)
                VALUES (gen_random_uuid(), %s, 'Marika Lund', 'x') RETURNING id
                """,
                (f"teacher-{slug}@example.invalid",),
            )
            teacher_id = str(cur.fetchone()["id"])
        series = scheduling.create_series(
            conn, tenant_id,
            student_id=student_id, weekday=2, start_time="16:00",
            duration_minutes=30, starts_on=starts_on, teacher_user_id=teacher_id,
            room="Main room",
        )
        scheduling.create_series(
            conn, tenant_id,
            student_id=other_student_id, weekday=2, start_time="17:00",
            duration_minutes=30, starts_on=starts_on, teacher_user_id=teacher_id,
            room="Main room",
        )
        token, subscription = calendar_subscriptions.create(
            conn, tenant_id, scope="family", billing_account_id=account_id,
            label="Raman family",
        )
        conn.commit()

    yield {
        "tenant_id": tenant_id,
        "series_id": str(series["id"]),
        "subscription_id": str(subscription["id"]),
        "token": token,
        "tuesday": tuesday,
    }

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
            cur.execute("DELETE FROM users WHERE id = %s", (teacher_id,))
        conn.commit()


def _feed(app, token: str):
    return app.test_client().get(f"/v1/public/calendar/{token}.ics")


@pytest.fixture()
def runtime_role():
    if not _runtime_role_obeys_rls():
        pytest.skip(
            "STUDIOSAAS_DATABASE_URL connects as a role that bypasses row-level "
            "security; the token lookup can only be tested under the runtime role"
        )


@requires_db
def test_a_valid_token_returns_the_familys_lessons(app, runtime_role, family_world):
    response = _feed(app, family_world["token"])

    assert response.status_code == 200, (
        "A valid token got the 'not found' answer. Under forced row-level "
        "security the lookup must go through calendar_subscription_tenant()."
    )
    assert response.content_type == "text/calendar; charset=utf-8"
    body = response.get_data(as_text=True)
    assert "Priya Raman" in body
    assert "Tom Other" not in body, "A family feed must carry only that family's children"


@requires_db
def test_lessons_fall_on_the_day_they_are_taught(app, runtime_role, family_world):
    """weekday = 2 is Tuesday (JS getDay, the schema's convention)."""

    body = _feed(app, family_world["token"]).get_data(as_text=True)
    tuesday = family_world["tuesday"]

    assert _starts(tuesday) in body, "The Tuesday lesson is missing from its Tuesday"
    assert _starts(tuesday + timedelta(days=1)) not in body, (
        "The lesson landed on Wednesday: weekday was read as Monday = 0"
    )


@requires_db
def test_a_cancellation_and_its_make_up_both_show(app, runtime_role, family_world):
    from _cms_sources import owner_connection as connect
    from studiosaas.services import scheduling

    tuesday = family_world["tuesday"]
    friday = _next_weekday(tuesday + timedelta(days=1), 5)
    with connect() as conn:
        result = scheduling.cancel_occurrence(
            conn, family_world["tenant_id"], family_world["series_id"],
            on_date=tuesday, cancelled_by=scheduling.CANCELLED_BY_STUDENT,
            hours_notice=72.0, reason="family away",
        )
        scheduling.consume_credit(
            conn, family_world["tenant_id"], result["makeupCreditId"], on_date=friday,
        )
        conn.commit()

    body = _feed(app, family_world["token"]).get_data(as_text=True)

    assert "CANCELLED · Priya Raman" in body
    assert _starts(friday) in body, "The make-up lesson on Friday is not in the feed"
    assert "Make-up · Priya Raman" in body


@requires_db
def test_revoked_and_unknown_tokens_get_the_same_answer(app, runtime_role, family_world):
    from _cms_sources import owner_connection as connect
    from studiosaas.services import calendar_subscriptions

    unknown = _feed(app, "not-a-real-token")
    with connect() as conn:
        calendar_subscriptions.revoke(
            conn, family_world["tenant_id"], family_world["subscription_id"],
        )
        conn.commit()
    revoked = _feed(app, family_world["token"])

    assert unknown.status_code == revoked.status_code == 404
    assert unknown.get_data() == revoked.get_data()


@requires_db
def test_the_lookup_does_not_leave_the_connection_in_platform_scope(runtime_role, family_world):
    """The function switches platform scope on for its own duration only."""

    from studiosaas.db import connect, fetch_one
    from studiosaas.services import calendar_subscriptions

    with connect() as conn:
        found = calendar_subscriptions.resolve(conn, family_world["token"])
        scope = fetch_one(
            conn,
            "SELECT current_setting('studiosaas.platform', true) AS platform,"
            "       current_setting('studiosaas.tenant_id', true) AS tenant_id",
            (),
        )

    assert found and str(found["tenant_id"]) == family_world["tenant_id"]
    assert scope["platform"] != "on"
    assert scope["tenant_id"] == family_world["tenant_id"]


@requires_db
def test_an_unbound_connection_still_sees_no_subscriptions(runtime_role, family_world):
    """The fix is a function, not an exemption: the table itself stays closed."""

    from studiosaas.db import connect, fetch_one

    with connect() as conn:
        row = fetch_one(conn, "SELECT count(*) AS n FROM calendar_subscriptions", ())

    assert row["n"] == 0
