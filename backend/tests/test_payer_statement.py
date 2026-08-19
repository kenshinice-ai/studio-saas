"""E2 — the payer monthly statement.

A statement is an accounting document: opening balance, the month's movement,
closing balance, and the books must balance — ``closing == opening +
Σ(debit − credit)`` is asserted on every statement, not assumed. The lines
read issued-snapshot data (number, issue date, document totals), never the
live mutable rollups, so a statement re-printed later says the same thing.
"""

from __future__ import annotations

import sys
import uuid
from datetime import date
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


def test_statement_route_is_declared_and_permission_gated():
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas/api_v1").glob("*.py")))
    start = source.index('@api_v1.route("/billing/payers/<payer_id>/statement"')
    route = source[start : source.index("\n\n\n", start)]
    assert '@permission_required("billing:read")' in route


@pytest.fixture()
def statement_world():
    world = build_world(prefix="stmt", with_owner_user=True)
    yield world
    destroy_world(world)


def _issue_invoice(conn, tenant_id, account_id, *, cents, on):
    from studiosaas.services import billing

    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
            (tenant_id, account_id),
        )
        invoice_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO invoice_lines (tenant_id, invoice_id, description,
                                       unit_price_cents, tax_rate_bp, tax_cents, total_cents)
            VALUES (%s, %s, 'Tuition', %s, 0, 0, %s)
            """,
            (tenant_id, invoice_id, cents, cents),
        )
    issued = billing.issue_invoice(conn, tenant_id, invoice_id, issue_on=on)
    return invoice_id, issued["number"]


def _populate(world) -> dict:
    from _cms_sources import owner_connection

    tenant_id = world["tenant_id"]
    account_id = world["account_id"]
    with owner_connection() as conn:
        # May: prior-period activity that becomes June's opening balance.
        _issue_invoice(conn, tenant_id, account_id, cents=10_000, on=date(2026, 5, 10))
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (tenant_id, billing_account_id, method,
                                      amount_cents, received_at, note)
                VALUES (%s, %s, 'bank_transfer', 4000, '2026-05-20T10:00:00+10:00', 'May payment')
                RETURNING id
                """,
                (tenant_id, account_id),
            )
            may_payment_id = str(cur.fetchone()["id"])

        # June: the statement month.
        june_invoice_id, june_number = _issue_invoice(
            conn, tenant_id, account_id, cents=20_000, on=date(2026, 6, 5)
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (tenant_id, billing_account_id, method,
                                      amount_cents, received_at, note)
                VALUES (%s, %s, 'cash', 15000, '2026-06-12T10:00:00+10:00', 'June payment')
                """,
                (tenant_id, account_id),
            )
            cur.execute(
                """
                INSERT INTO credit_notes
                    (tenant_id, billing_account_id, invoice_id, number, status,
                     issue_date, issued_at, total_cents, reason,
                     supplier_snapshot, recipient_snapshot)
                VALUES (%s, %s, %s, 'CN-0100', 'issued', '2026-06-20',
                        '2026-06-20T10:00:00+10:00', 2000, 'goodwill credit',
                        '{"legalName": "World Studio Pty Ltd"}'::jsonb,
                        '{"displayName": "Bianchi Family"}'::jsonb)
                """,
                (tenant_id, account_id, june_invoice_id),
            )
            cur.execute(
                """
                INSERT INTO refunds (tenant_id, payment_id, amount_cents, status,
                                     reason, created_at)
                VALUES (%s, %s, 1000, 'succeeded', 'overcharge returned',
                        '2026-06-25T10:00:00+10:00')
                """,
                (tenant_id, may_payment_id),
            )
            # a June draft must never appear on a statement.
            cur.execute(
                "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s)",
                (tenant_id, account_id),
            )

        # July: out of period, must not leak into June.
        _issue_invoice(conn, tenant_id, account_id, cents=999, on=date(2026, 7, 1))
        conn.commit()
    return {"june_number": june_number}


@requires_db
def test_statement_balances_and_reads_snapshots(statement_world, client):
    expected = _populate(statement_world)
    login(client, statement_world)

    response = client.get(
        f"/s/{statement_world['slug']}/v1/billing/payers/{statement_world['account_id']}"
        "/statement?month=2026-06",
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()

    assert body["payer"] == {"id": statement_world["account_id"], "name": "Bianchi Family"}
    assert body["periodStart"] == "2026-06-01"
    assert body["periodEnd"] == "2026-06-30"
    assert body["openingBalanceCents"] == 6000

    lines = body["lines"]
    assert [line["kind"] for line in lines] == ["invoice", "payment", "credit_note", "refund"]
    assert lines[0]["number"] == expected["june_number"]
    assert lines[0]["debitCents"] == 20_000 and lines[0]["creditCents"] == 0
    assert lines[1]["number"] is None
    assert lines[1]["creditCents"] == 15_000
    assert lines[2]["number"] == "CN-0100"
    assert lines[2]["creditCents"] == 2000
    assert lines[3]["debitCents"] == 1000

    # 守恒：closing == opening + Σ(debit − credit), and the running balance
    # advances line by line by exactly the same arithmetic.
    running = body["openingBalanceCents"]
    for line in lines:
        running += line["debitCents"] - line["creditCents"]
        assert line["balanceCents"] == running
    assert body["closingBalanceCents"] == running == 10_000

    # Out-of-period and draft documents never leak in.
    assert all("999" not in str(line.get("debitCents")) for line in lines)
    assert len(lines) == 4


@requires_db
def test_statement_rejects_bad_month_and_unknown_payer(statement_world, client):
    login(client, statement_world)
    base = f"/s/{statement_world['slug']}/v1/billing/payers"

    bad = client.get(
        f"{base}/{statement_world['account_id']}/statement?month=June-2026",
        headers=API_HEADERS,
    )
    assert bad.status_code == 400

    missing = client.get(
        f"{base}/{uuid.uuid4()}/statement?month=2026-06", headers=API_HEADERS
    )
    assert missing.status_code == 404
