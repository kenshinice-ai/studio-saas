"""E3 — the manual "reminded" mark on an invoice.

Following up unpaid invoices stays a human activity by design (no automatic
outbound email/SMS exists on this path). What the product adds is memory:
`reminder_recorded` becomes part of the invoice's append-only event history,
with the operator and an optional note, idempotent under retries via the
same `financial_operation_requests` contract as every money mutation.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import (  # noqa: E402
    API_HEADERS,
    build_world,
    database_available,
    destroy_world,
    login,
)

requires_db = pytest.mark.skipif(
    not database_available(), reason="needs the local PostgreSQL money schema"
)


def test_reminder_route_is_declared_and_permission_gated():
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas/api_v1").glob("*.py")))
    start = source.index('@api_v1.route("/billing/invoices/<invoice_id>/reminders"')
    route = source[start : source.index("\n\n\n", start)]
    assert '@permission_required("billing:write")' in route
    assert "invoice_not_remindable" in route


def test_no_automatic_sending_exists_on_the_reminder_path():
    """标记≠发信: the reminder service must not touch any outbound channel."""

    service = (BACKEND_ROOT / "studiosaas/services/invoice_reminders.py").read_text(
        encoding="utf-8"
    )
    for forbidden in ("notification", "send_safely", "smtp", "sms"):
        assert forbidden not in service.lower(), forbidden


@pytest.fixture()
def reminder_world():
    world = build_world(prefix="rem", with_owner_user=True)
    yield world
    destroy_world(world)


def _issued_invoice(world) -> str:
    from _cms_sources import owner_connection
    from studiosaas.services import billing

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
                (world["tenant_id"], world["account_id"]),
            )
            invoice_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO invoice_lines (tenant_id, invoice_id, description,
                                           unit_price_cents, tax_rate_bp, tax_cents, total_cents)
                VALUES (%s, %s, 'Tuition', 10000, 0, 0, 10000)
                """,
                (world["tenant_id"], invoice_id),
            )
        billing.issue_invoice(conn, world["tenant_id"], invoice_id)
        conn.commit()
    return invoice_id


def _draft_invoice(world) -> str:
    from _cms_sources import owner_connection

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
                (world["tenant_id"], world["account_id"]),
            )
            invoice_id = str(cur.fetchone()["id"])
        conn.commit()
    return invoice_id


@requires_db
def test_reminder_is_recorded_idempotently_with_actor_and_note(reminder_world, client):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_all

    invoice_id = _issued_invoice(reminder_world)
    login(client, reminder_world)
    url = f"/s/{reminder_world['slug']}/v1/billing/invoices/{invoice_id}/reminders"
    request_id = str(uuid.uuid4())

    first = client.post(
        url, json={"requestId": request_id, "note": "微信提醒过家长"}, headers=API_HEADERS
    )
    assert first.status_code == 201, first.get_json()
    body = first.get_json()
    assert body["event"]["eventType"] == "reminder_recorded"
    assert body["event"]["note"] == "微信提醒过家长"
    assert body["replayed"] is False

    replay = client.post(
        url, json={"requestId": request_id, "note": "微信提醒过家长"}, headers=API_HEADERS
    )
    assert replay.status_code == 200
    assert replay.get_json()["replayed"] is True
    assert replay.get_json()["event"]["id"] == body["event"]["id"]

    changed = client.post(
        url, json={"requestId": request_id, "note": "different note"}, headers=API_HEADERS
    )
    assert changed.status_code == 409

    with owner_connection() as conn:
        events = fetch_all(
            conn,
            """
            SELECT event_type, actor_user_id, detail FROM invoice_events
            WHERE tenant_id = %s AND invoice_id = %s AND event_type = 'reminder_recorded'
            """,
            (reminder_world["tenant_id"], invoice_id),
        )
    assert len(events) == 1, "a replay must not append a second event"
    assert str(events[0]["actor_user_id"]) == reminder_world["owner_user_id"]
    assert events[0]["detail"]["note"] == "微信提醒过家长"

    # The invoice detail's event stream naturally includes the reminder.
    detail = client.get(
        f"/s/{reminder_world['slug']}/v1/billing/invoices/{invoice_id}",
        headers=API_HEADERS,
    ).get_json()
    event_types = [event["event_type"] for event in detail["events"]]
    assert "reminder_recorded" in event_types


@requires_db
def test_draft_and_void_invoices_are_not_remindable(reminder_world, client):
    from _cms_sources import owner_connection
    from studiosaas.services import billing

    login(client, reminder_world)
    slug = reminder_world["slug"]

    draft_id = _draft_invoice(reminder_world)
    draft = client.post(
        f"/s/{slug}/v1/billing/invoices/{draft_id}/reminders",
        json={"requestId": str(uuid.uuid4())},
        headers=API_HEADERS,
    )
    assert draft.status_code == 409
    assert draft.get_json()["error"] == "invoice_not_remindable"

    void_id = _issued_invoice(reminder_world)
    with owner_connection() as conn:
        billing.void_invoice(conn, reminder_world["tenant_id"], void_id, reason="test void")
        conn.commit()
    voided = client.post(
        f"/s/{slug}/v1/billing/invoices/{void_id}/reminders",
        json={"requestId": str(uuid.uuid4())},
        headers=API_HEADERS,
    )
    assert voided.status_code == 409
    assert voided.get_json()["error"] == "invoice_not_remindable"

    missing = client.post(
        f"/s/{slug}/v1/billing/invoices/{uuid.uuid4()}/reminders",
        json={"requestId": str(uuid.uuid4())},
        headers=API_HEADERS,
    )
    assert missing.status_code == 404


@requires_db
def test_reminder_note_is_bounded_and_request_id_required(reminder_world, client):
    invoice_id = _issued_invoice(reminder_world)
    login(client, reminder_world)
    url = f"/s/{reminder_world['slug']}/v1/billing/invoices/{invoice_id}/reminders"

    no_request_id = client.post(url, json={"note": "x"}, headers=API_HEADERS)
    assert no_request_id.status_code == 400

    too_long = client.post(
        url,
        json={"requestId": str(uuid.uuid4()), "note": "长" * 501},
        headers=API_HEADERS,
    )
    assert too_long.status_code == 400
