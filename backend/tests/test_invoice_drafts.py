"""P1-01 aggregate invoice-draft command contract."""

from pathlib import Path
import uuid

import pytest

from _cms_sources import CMS_SRC_DIR, cms_source_text
from studiosaas.services import invoice_drafts
from test_credit_settlements import requires_db, settlement_tenant


ROOT = Path(__file__).resolve().parents[1]
API_SOURCE = "\n".join(p.read_text(encoding="utf-8") for p in sorted((ROOT / "studiosaas/api_v1").glob("*.py")))


def test_invoice_draft_aggregate_command_is_strict_atomic_and_idempotent():
    service = (ROOT / "studiosaas/services/invoice_drafts.py").read_text(encoding="utf-8")
    assert "invoice_draft_create" in service
    assert "_operation_start" in service
    assert "allowPossibleDuplicate" in service
    assert "possibleDuplicates" in service
    assert "record_audit_event" in service
    assert "recalculate_totals" in service
    assert "billing.line_amounts" in service
    assert "rollback" not in service  # caller owns the transaction boundary

    route_start = API_SOURCE.index('@api_v1.route("/billing/invoice-drafts"')
    route = API_SOURCE[route_start:API_SOURCE.index('@api_v1.route("/billing/invoices",', route_start)]
    assert 'methods=["POST"]' in route
    assert "create_invoice_draft" in route
    assert "InvoiceDraftConflict" in route
    assert "return jsonify" in route


def test_cms_new_invoice_uses_one_aggregate_request_and_reuses_request_id():
    panel = (CMS_SRC_DIR / "panels" / "billing.jsx").read_text(encoding="utf-8")
    app = cms_source_text()
    dialog = panel[panel.index("function NewInvoiceDialog"):]
    assert "/billing/invoice-drafts" in panel
    assert "nextInvoiceDraftRequestId" in dialog
    assert "requestId" in dialog
    assert "payer: payerState.accountId" not in dialog
    assert "for (const line of form.lines)" not in panel
    assert "/billing/accounts" not in dialog
    assert "allowPossibleDuplicate" in dialog or "possibleDuplicates" in app


def test_invoice_draft_failure_is_designed_to_roll_back_all_domain_rows():
    service = (ROOT / "studiosaas/services/invoice_drafts.py").read_text(encoding="utf-8")
    assert "with conn.cursor()" in service
    assert "INSERT INTO billing_accounts" in service
    assert "INSERT INTO billing_account_members" in service
    assert "INSERT INTO invoices" in service
    assert "INSERT INTO invoice_lines" in service
    assert "_finish_operation" in service


@requires_db
def test_aggregate_invoice_draft_replay_returns_the_same_ids(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    t = settlement_tenant
    payload = {
        "requestId": str(uuid.uuid4()),
        "payer": {"accountId": t["account_id"]},
        "invoice": {"note": "aggregate draft", "purchaseOrderRef": "PO-7"},
        "lines": [
            {
                "description": "Term 1",
                "quantity": "1.00",
                "unitPriceCents": 10000,
                "taxRateBp": 1000,
                "sourceKind": "manual",
                "studentId": t["student_id"],
            },
            {
                "description": "Materials",
                "quantity": "2.00",
                "unitPriceCents": 500,
                "taxRateBp": 0,
                "sourceKind": "goods",
            },
        ],
    }
    with owner_connection() as conn:
        first = invoice_drafts.create_invoice_draft(conn, t["tenant_id"], payload)
        conn.commit()
        replay = invoice_drafts.create_invoice_draft(conn, t["tenant_id"], payload)
        assert replay["replayed"] is True
        assert replay["invoiceId"] == first["invoiceId"]
        assert replay["lineIds"] == first["lineIds"]
        assert replay["payer"]["accountId"] == t["account_id"]
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM invoices WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], first["invoiceId"]),
        )["n"] == 1
        conn.commit()


@requires_db
def test_aggregate_duplicate_gate_requires_explicit_allow_and_records_review(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    t = settlement_tenant
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE billing_accounts SET email = %s WHERE tenant_id = %s AND id = %s",
                ("same@example.com", t["tenant_id"], t["account_id"]),
            )
        conn.commit()
        base = {
            "payer": {
                "create": {
                    "kind": "person", "name": "Same Contact", "email": "same@example.com",
                },
                "linkedStudentIds": [],
            },
            "invoice": {},
            "lines": [{"description": "Duplicate check", "unitPriceCents": 1000, "taxRateBp": 0}],
        }
        blocked = {**base, "requestId": str(uuid.uuid4())}
        with pytest.raises(invoice_drafts.InvoiceDraftConflict) as exc_info:
            invoice_drafts.create_invoice_draft(conn, t["tenant_id"], blocked)
        assert exc_info.value.details["possibleDuplicates"]
        conn.rollback()
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM billing_accounts WHERE tenant_id = %s AND name = %s",
            (t["tenant_id"], "Same Contact"),
        )["n"] == 0

        allowed = {**base, "requestId": str(uuid.uuid4()), "allowPossibleDuplicate": True}
        created = invoice_drafts.create_invoice_draft(conn, t["tenant_id"], allowed)
        assert created["payer"]["created"] is True
        assert created["payer"]["possibleDuplicates"]
        conn.commit()


@requires_db
def test_aggregate_audit_failure_leaves_no_payer_or_invoice(settlement_tenant, monkeypatch):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    t = settlement_tenant
    payload = {
        "requestId": str(uuid.uuid4()),
        "payer": {"create": {"kind": "organisation", "companyName": "Atomic Failure Pty Ltd"}},
        "invoice": {},
        "lines": [{"description": "Must not persist", "unitPriceCents": 1000, "taxRateBp": 0}],
    }

    def fail_audit(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(invoice_drafts, "record_audit_event", fail_audit)
    with owner_connection() as conn:
        before = fetch_one(
            conn,
            "SELECT count(*) AS n FROM invoices WHERE tenant_id = %s",
            (t["tenant_id"],),
        )["n"]
        with pytest.raises(RuntimeError, match="injected audit failure"):
            invoice_drafts.create_invoice_draft(conn, t["tenant_id"], payload)
        conn.rollback()
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM billing_accounts WHERE tenant_id = %s AND company_name = %s",
            (t["tenant_id"], "Atomic Failure Pty Ltd"),
        )["n"] == 0
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM invoices WHERE tenant_id = %s",
            (t["tenant_id"],),
        )["n"] == before
