"""E6 — the invoice-profile completeness gate at issue time.

Drafting stays free: a studio may sketch invoices before it has finished its
settings. *Issuing* is the moment a document leaves the studio, so name,
street address and ABN must all be present, and a miss is a structured 409
(`invoice_profile_incomplete` with the missing field names) rather than a
prose error the CMS would have to parse. The gate lives in the service, so
the direct issue route and the settlement `issueNow` path cannot diverge.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.services import billing  # noqa: E402

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


def test_profile_missing_is_computed_from_stored_identity_fields():
    blank = billing._blank_billing_identity()
    assert billing.invoice_profile_missing(blank) == ["name", "address", "abn"]

    named = dict(blank, trading_name="Studio")
    assert billing.invoice_profile_missing(named) == ["address", "abn"]

    complete = dict(
        blank, legal_name="Studio Pty Ltd", address_line1="1 Example St",
        abn="53 004 085 616",
    )
    assert billing.invoice_profile_missing(complete) == []

    whitespace = dict(blank, legal_name="  ", address_line1=" ", abn="\t")
    assert billing.invoice_profile_missing(whitespace) == ["name", "address", "abn"]


def test_gate_error_shape_is_declared_in_both_issue_paths():
    source = (BACKEND_ROOT / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    assert source.count("invoice_profile_incomplete") >= 2, (
        "both the issue route and the settlement route must map the gate"
    )


@pytest.fixture()
def incomplete_world():
    world = build_world(prefix="gate", with_owner_user=True, identity_address=False)
    yield world
    destroy_world(world)


def _draft_with_line(world) -> str:
    from _cms_sources import owner_connection

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
        conn.commit()
    return invoice_id


@requires_db
def test_drafting_is_never_blocked_but_issue_is(incomplete_world, client):
    login(client, incomplete_world)
    slug = incomplete_world["slug"]

    # Draft creation passes the gate untouched — both the simple route and
    # the aggregate draft command.
    draft = client.post(
        f"/s/{slug}/v1/billing/invoices",
        json={"billingAccountId": incomplete_world["account_id"]},
        headers=API_HEADERS,
    )
    assert draft.status_code == 201, draft.get_json()

    aggregate = client.post(
        f"/s/{slug}/v1/billing/invoice-drafts",
        json={
            "requestId": str(uuid.uuid4()),
            "payer": {"accountId": incomplete_world["account_id"]},
            "lines": [{"description": "Tuition", "unitPriceCents": 10000}],
        },
        headers=API_HEADERS,
    )
    assert aggregate.status_code == 201, aggregate.get_json()

    invoice_id = _draft_with_line(incomplete_world)
    issue = client.post(
        f"/s/{slug}/v1/billing/invoices/{invoice_id}/issue",
        json={},
        headers=API_HEADERS,
    )
    assert issue.status_code == 409, issue.get_json()
    body = issue.get_json()
    assert body["error"] == "invoice_profile_incomplete"
    assert body["missing"] == ["address"]


@requires_db
def test_settlement_issue_now_passes_the_same_gate(incomplete_world, client):
    login(client, incomplete_world)
    slug = incomplete_world["slug"]

    blocked = client.post(
        f"/s/{slug}/v1/students/{incomplete_world['student_id']}/credit-settlements",
        json={
            "requestId": str(uuid.uuid4()),
            "credits": "10",
            "amountCents": 55_000,
            "packageId": incomplete_world["package_id"],
            "billing": {
                "createInvoice": True,
                "billingAccountId": incomplete_world["account_id"],
                "issueNow": True,
            },
        },
        headers=API_HEADERS,
    )
    assert blocked.status_code == 409, blocked.get_json()
    body = blocked.get_json()
    assert body["error"] == "invoice_profile_incomplete"
    assert body["missing"] == ["address"]

    # A credits-only top-up has no document to gate.
    free = client.post(
        f"/s/{slug}/v1/students/{incomplete_world['student_id']}/credit-settlements",
        json={
            "requestId": str(uuid.uuid4()),
            "credits": "1",
            "amountCents": 0,
            "billing": {"createInvoice": False},
        },
        headers=API_HEADERS,
    )
    assert free.status_code == 201, free.get_json()


@requires_db
def test_completing_the_profile_reopens_issue(incomplete_world, client):
    from _cms_sources import owner_connection

    invoice_id = _draft_with_line(incomplete_world)
    login(client, incomplete_world)
    url = f"/s/{incomplete_world['slug']}/v1/billing/invoices/{invoice_id}/issue"

    assert client.post(url, json={}, headers=API_HEADERS).status_code == 409

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tenant_billing_identity SET address_line1 = '12 Sturt Street' "
                "WHERE tenant_id = %s",
                (incomplete_world["tenant_id"],),
            )
        conn.commit()

    reopened = client.post(url, json={}, headers=API_HEADERS)
    assert reopened.status_code == 200, reopened.get_json()
    assert reopened.get_json()["invoice"]["number"]
