"""E1 — the unified student timeline.

The product promise is a single answer to "这孩子这半年发生了什么": every
registration, approval, top-up, deduction, refund, invoice, payment, credit
note and published report, newest first, with nothing swallowed. A source
that cannot be read is *named* in ``omittedSources`` rather than silently
dropped — the empty list is the healthy state and the assertion.
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


def test_timeline_route_is_declared_and_permission_gated():
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted((BACKEND_ROOT / "studiosaas/api_v1").glob("*.py")))
    start = source.index('@api_v1.route("/students/<student_id>/timeline"')
    route = source[start : source.index("\n\n\n", start)]
    assert '@permission_required("students:read")' in route
    # Money and report sources are permission-scoped inside the handler, and
    # what a role may not see is named, never silently dropped.
    for required in ("credits:read", "billing:read", "progress_reports:read",
                     "registrations:read", "omittedSources"):
        assert required in route


@pytest.fixture()
def timeline_world():
    world = build_world(prefix="tl", with_owner_user=True)
    yield world
    destroy_world(world)


def _populate(world) -> dict:
    """One event per source, all through the real write paths where they exist."""

    from _cms_sources import owner_connection
    from studiosaas.services import credit_settlements

    counts = {}
    with owner_connection() as conn:
        with conn.cursor() as cur:
            # registration submitted, then approved and linked to the student.
            cur.execute(
                """
                INSERT INTO registrations
                    (tenant_id, status, first_name, last_name, mobile, email,
                     student_id, submitted_at, reviewed_at)
                VALUES (%s, 'approved', 'Ana', 'Bianchi', '0400 111 103',
                        'ana@example.test', %s,
                        now() - interval '7 days', now() - interval '6 days')
                RETURNING id
                """,
                (world["tenant_id"], world["student_id"]),
            )
        # purchase + invoice + payment through the atomic settlement service.
        settlement = credit_settlements.create_credit_settlement(
            conn,
            world["tenant_id"],
            world["student_id"],
            {
                "requestId": str(uuid.uuid4()),
                "credits": "10",
                "amountCents": 55_000,
                "paymentMethod": "bank_transfer",
                "packageId": world["package_id"],
                "billing": {
                    "createInvoice": True,
                    "billingAccountId": world["account_id"],
                    "taxCodeId": world["tax_code_id"],
                    "issueNow": True,
                    "paymentReceived": True,
                },
            },
        )
        with conn.cursor() as cur:
            # a consumption (deduction) and an issued credit note + report.
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (tenant_id, student_id, transaction_type, amount, balance_after,
                     occurred_at)
                VALUES (%s, %s, 'consume', -1, 9, now() - interval '1 day')
                """,
                (world["tenant_id"], world["student_id"]),
            )
            cur.execute(
                """
                INSERT INTO credit_notes
                    (tenant_id, billing_account_id, invoice_id, number, status,
                     issue_date, issued_at, total_cents, reason,
                     supplier_snapshot, recipient_snapshot)
                VALUES (%s, %s, %s, 'CN-0001', 'issued', CURRENT_DATE,
                        now() - interval '1 hour', 5500, 'partial correction',
                        '{"legalName": "World Studio Pty Ltd"}'::jsonb,
                        '{"displayName": "Bianchi Family"}'::jsonb)
                """,
                (world["tenant_id"], world["account_id"], settlement["invoiceId"]),
            )
            cur.execute(
                """
                INSERT INTO progress_reports
                    (tenant_id, student_id, period_start, period_end, status,
                     published_at)
                VALUES (%s, %s, CURRENT_DATE - 30, CURRENT_DATE, 'published',
                        now() - interval '2 hours')
                """,
                (world["tenant_id"], world["student_id"]),
            )
        conn.commit()
    # registration + approval + topup + deduction + invoice + payment
    # + credit_note + report
    counts["expected_entries"] = 8
    counts["invoice_id"] = settlement["invoiceId"]
    return counts


@requires_db
def test_timeline_merges_every_source_without_swallowing(timeline_world, client):
    expected = _populate(timeline_world)
    login(client, timeline_world)

    response = client.get(
        f"/s/{timeline_world['slug']}/v1/students/{timeline_world['student_id']}/timeline",
        headers=API_HEADERS,
    )
    assert response.status_code == 200, response.get_json()
    body = response.get_json()

    assert body["omittedSources"] == []
    assert body["hasMore"] is False
    entries = body["entries"]
    assert len(entries) == expected["expected_entries"]

    kinds = [entry["kind"] for entry in entries]
    for kind in ("registration", "approval", "topup", "deduction",
                 "invoice", "payment", "credit_note", "report"):
        assert kind in kinds, f"missing {kind} in {kinds}"

    # Newest first, ISO 8601 timestamps (not RFC 1123).
    stamps = [entry["ts"] for entry in entries]
    assert stamps == sorted(stamps, reverse=True)
    assert all("T" in stamp for stamp in stamps)

    # Money events deep-link to the invoice.
    by_kind = {entry["kind"]: entry for entry in entries}
    assert by_kind["invoice"]["invoiceId"] == expected["invoice_id"]
    assert by_kind["payment"]["invoiceId"] == expected["invoice_id"]
    assert by_kind["invoice"]["amountCents"] == 55_000
    assert by_kind["payment"]["amountCents"] == 55_000
    assert by_kind["topup"]["credits"] == 10
    assert by_kind["deduction"]["credits"] == -1
    # Every entry carries the full contract shape.
    for entry in entries:
        assert set(entry) == {"ts", "kind", "title", "credits", "amountCents",
                              "invoiceId", "note"}


@requires_db
def test_timeline_pages_backwards_with_before(timeline_world, client):
    _populate(timeline_world)
    login(client, timeline_world)
    base = f"/s/{timeline_world['slug']}/v1/students/{timeline_world['student_id']}/timeline"

    first = client.get(f"{base}?limit=3", headers=API_HEADERS).get_json()
    assert len(first["entries"]) == 3
    assert first["hasMore"] is True

    cursor = first["entries"][-1]["ts"]
    from urllib.parse import quote

    second = client.get(
        f"{base}?limit=50&before={quote(cursor)}", headers=API_HEADERS
    ).get_json()
    seen_first = {(e["ts"], e["kind"]) for e in first["entries"]}
    seen_second = {(e["ts"], e["kind"]) for e in second["entries"]}
    assert not (seen_first & seen_second), "before-pagination returned duplicates"
    assert all(e["ts"] < cursor for e in second["entries"])


@requires_db
def test_a_failing_source_is_named_not_swallowed(timeline_world, monkeypatch):
    """One broken source must cost exactly that source, and say so."""

    from _cms_sources import owner_connection
    from studiosaas.services import student_timeline

    _populate(timeline_world)

    def broken(conn, tenant_id, student_id, before, cap):
        raise RuntimeError("simulated source failure")

    monkeypatch.setitem(student_timeline.SOURCE_FETCHERS, "reports", broken)
    with owner_connection() as conn:
        result = student_timeline.student_timeline(
            conn, timeline_world["tenant_id"], timeline_world["student_id"]
        )
    assert result["omittedSources"] == ["reports"]
    kinds = {entry["kind"] for entry in result["entries"]}
    assert "report" not in kinds
    assert {"registration", "topup", "invoice", "payment"} <= kinds


@requires_db
def test_timeline_is_read_only(timeline_world):
    """The timeline may never write — not even an audit row."""

    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one
    from studiosaas.services import student_timeline

    _populate(timeline_world)
    tables = ("credit_transactions", "invoices", "payments", "credit_notes",
              "registrations", "progress_reports", "audit_logs")
    with owner_connection() as conn:
        before = {
            table: fetch_one(
                conn, f"SELECT count(*) AS n FROM {table} WHERE tenant_id = %s",  # noqa: S608
                (timeline_world["tenant_id"],),
            )["n"]
            for table in tables
        }
        student_timeline.student_timeline(
            conn, timeline_world["tenant_id"], timeline_world["student_id"]
        )
        conn.commit()
        after = {
            table: fetch_one(
                conn, f"SELECT count(*) AS n FROM {table} WHERE tenant_id = %s",  # noqa: S608
                (timeline_world["tenant_id"],),
            )["n"]
            for table in tables
        }
    assert before == after
