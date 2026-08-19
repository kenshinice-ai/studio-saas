"""X3 — the Xero transport: payloads, the drain, and the reconciliation.

What must hold, in the order the money moves:

* a pushed line carries OUR cents (quantity-1 trick), mapped to the
  accountant's chart, and a blank mapping is a named refusal;
* the drain is dependency-ordered, classifies failures (backoff vs
  dead-letter) and never sends the same document twice;
* the link is per-organisation: reconnecting to another org queues
  everything again for THAT ledger and never updates ghosts in the old one;
* the demo run is only "clean" when something was pushed AND the read-back
  reconciliation shows zero difference.

Every HTTP call is a recorded stub; nothing here talks to Xero.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import build_world, database_available, destroy_world  # noqa: E402
from _cms_sources import owner_connection  # noqa: E402

requires_db = pytest.mark.skipif(
    not database_available(), reason="needs the local PostgreSQL money schema"
)

MAPPINGS = {
    "tuition": {"item_kind": "tuition", "account_code": "200", "tax_type": "OUTPUT"},
    "bank": {"item_kind": "bank", "account_code": "090", "tax_type": ""},
}


# ── pure payload rules ───────────────────────────────────────────────────


def test_line_items_carry_exact_cents_and_mapped_accounts():
    from studiosaas.services import xero_transport as t

    dto = {"lines": [{
        "description": "Term tuition", "quantity": "1.00", "sourceKind": "tuition",
        "unitPriceCents": 10000, "netCents": 10000, "taxCents": 1000, "totalCents": 11000,
    }]}
    items = t._line_items(dto, MAPPINGS)
    assert items == [{
        "Description": "Term tuition", "Quantity": 1.0,
        "UnitAmount": 100.0, "LineAmount": 100.0, "TaxAmount": 10.0,
        "AccountCode": "200", "TaxType": "OUTPUT",
    }]


def test_non_unit_quantity_moves_into_the_description():
    from studiosaas.services import xero_transport as t

    dto = {"lines": [{
        "description": "Casual lessons", "quantity": "2.50", "sourceKind": "lesson",
        "unitPriceCents": 4000, "netCents": 10000, "taxCents": 1000, "totalCents": 11000,
    }]}
    items = t._line_items(dto, MAPPINGS)
    # lesson aliases to the tuition account; the human quantity survives in text.
    assert items[0]["AccountCode"] == "200"
    assert "2.50 × 40.00" in items[0]["Description"]
    assert items[0]["Quantity"] == 1.0
    assert items[0]["LineAmount"] == 100.0


def test_missing_mapping_is_a_named_refusal():
    from studiosaas.services import xero_transport as t

    with pytest.raises(t.TransportError) as exc:
        t._account_for(MAPPINGS, "goods")
    assert "goods" in str(exc.value)
    assert "科目与税率映射" in str(exc.value)


def test_validation_summary_flattens_xero_elements():
    from studiosaas.services import xero_transport as t

    detail = (
        '{"Elements": [{"ValidationErrors": ['
        '{"Message": "Account code 999 is not valid"},'
        '{"Message": "Account code 999 is not valid"}]}]}'
    )
    summary = t._validation_summary(400, detail)
    assert summary.count("Account code 999 is not valid") == 1


# ── a world with an issued invoice, a payment, and a fake connection ─────


@pytest.fixture()
def pushable_world():
    world = build_world(prefix="xtp")
    tenant_id = world["tenant_id"]
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO xero_connections
                    (tenant_id, org_id, org_name, status, refresh_token_encrypted)
                VALUES (%s, 'org-demo-1', 'Demo Company (AU)', 'connected', 'x')
                """,
                (tenant_id,),
            )
            for kind, code, tax in (("tuition", "200", "OUTPUT"), ("bank", "090", "")):
                cur.execute(
                    """
                    INSERT INTO xero_account_mappings (tenant_id, item_kind, account_code, tax_type)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (tenant_id, kind, code, tax),
                )
            cur.execute(
                "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
                (tenant_id, world["account_id"]),
            )
            invoice_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO invoice_lines
                    (tenant_id, invoice_id, description, unit_price_cents,
                     tax_rate_bp, tax_cents, total_cents, source_kind)
                VALUES (%s, %s, 'Term tuition', 10000, 1000, 1000, 11000, 'tuition')
                """,
                (tenant_id, invoice_id),
            )
        conn.commit()
        from studiosaas.services import billing

        billing.issue_invoice(conn, tenant_id, invoice_id)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (tenant_id, billing_account_id, method, amount_cents)
                VALUES (%s, %s, 'bank_transfer', 11000) RETURNING id
                """,
                (tenant_id, world["account_id"]),
            )
            payment_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO payment_allocations (tenant_id, payment_id, invoice_id, amount_cents)
                VALUES (%s, %s, %s, 11000) RETURNING id
                """,
                (tenant_id, payment_id, invoice_id),
            )
            allocation_id = str(cur.fetchone()["id"])
        conn.commit()
    world["invoice_id"] = invoice_id
    world["payment_id"] = payment_id
    world["allocation_id"] = allocation_id
    yield world
    destroy_world(world)


class FakeXero:
    """Records every call; answers like the Accounting API's happy path."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.fail_with: Exception | None = None
        self.totals = {"invoice": 110.0, "payment": 110.0}

    def __call__(self, conn, tenant_id, org_id, method, path, payload=None):
        from studiosaas.services import xero_transport as t

        self.calls.append((method, path))
        if self.fail_with is not None:
            raise self.fail_with
        if path == "/Contacts":
            return {"Contacts": [{"ContactID": "c-" + org_id}]}
        if path == "/Invoices" and method == "POST":
            return {"Invoices": [{"InvoiceID": "inv-" + org_id}]}
        if path.startswith("/Invoices/") and method == "GET":
            return {"Invoices": [{"Total": self.totals["invoice"], "Status": "AUTHORISED"}]}
        if path == "/Payments" and method == "PUT":
            return {"Payments": [{"PaymentID": "pay-" + org_id}]}
        if path.startswith("/Payments/") and method == "GET":
            return {"Payments": [{"Amount": self.totals["payment"]}]}
        if path == "/CreditNotes" and method == "POST":
            return {"CreditNotes": [{"CreditNoteID": "cn-" + org_id, "Total": 0, "RemainingCredit": 0}]}
        raise t.TransportError(f"unexpected call {method} {path}")


@pytest.fixture()
def fake_api(monkeypatch):
    from studiosaas.services import xero_transport as t

    fake = FakeXero()
    monkeypatch.setattr(t, "_api", fake)
    return fake


# ── backfill and drain ───────────────────────────────────────────────────


@requires_db
def test_backfill_queues_only_unlinked_issued_documents(pushable_world):
    from studiosaas.services import xero_transport as t

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        first = t.backfill(conn, tenant_id)
        again = t.backfill(conn, tenant_id)
        conn.commit()
    assert first == {"invoice": 1, "credit_note": 0, "payment": 1, "total": 2}
    assert again["total"] == 0  # same org, same documents: nothing new


@requires_db
def test_drain_pushes_invoice_then_payment_and_records_org_links(pushable_world, fake_api):
    from studiosaas.services import xero_transport as t
    from studiosaas.db import fetch_all

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        t.backfill(conn, tenant_id)
        result = t.drain(conn, tenant_id)
        conn.commit()
        assert result["sent"] == 2 and result["failed"] == 0 and result["deferred"] == 0
        # Invoice strictly before payment — the payment needs the invoice's id.
        kinds = [job["kind"] for job in result["jobs"]]
        assert kinds == ["invoice", "payment"]
        links = fetch_all(
            conn,
            "SELECT local_kind, org_id FROM xero_object_links WHERE tenant_id = %s ORDER BY local_kind",
            (tenant_id,),
        )
        assert [(l["local_kind"], l["org_id"]) for l in links] == [
            ("billing_account", "org-demo-1"), ("invoice", "org-demo-1"), ("payment", "org-demo-1"),
        ]
        # A second drain finds nothing to do and makes no HTTP calls.
        before = len(fake_api.calls)
        second = t.drain(conn, tenant_id)
        conn.commit()
    assert second["processed"] == 0
    assert len(fake_api.calls) == before


@requires_db
def test_payment_alone_defers_until_its_invoice_has_landed(pushable_world, fake_api):
    from studiosaas.services import xero, xero_transport as t
    from studiosaas.db import fetch_one

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        with conn.cursor() as cur:
            key = xero.idempotency_key(tenant_id, "payment", pushable_world["allocation_id"], "org-demo-1")
            cur.execute(
                """
                INSERT INTO integration_sync_jobs
                    (tenant_id, integration, local_kind, local_id, idempotency_key)
                VALUES (%s, 'xero', 'payment', %s, %s)
                """,
                (tenant_id, pushable_world["allocation_id"], key),
            )
        result = t.drain(conn, tenant_id)
        conn.commit()
        assert result["deferred"] == 1 and result["failed"] == 0
        job = fetch_one(
            conn,
            "SELECT status, attempts, last_error FROM integration_sync_jobs WHERE tenant_id = %s",
            (tenant_id,),
        )
    assert job["status"] == "queued" and job["attempts"] == 1
    assert "invoice" in job["last_error"].lower()


@requires_db
def test_validation_failure_dead_letters_and_retryable_backs_off(pushable_world, fake_api):
    from studiosaas.services import xero_transport as t
    from studiosaas.db import fetch_one

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        t.backfill(conn, tenant_id)
        fake_api.fail_with = t.TransportError("Xero rejected the request (HTTP 400): Account code 999 is not valid")
        result = t.drain(conn, tenant_id, limit=1)
        assert result["failed"] == 1
        failed = fetch_one(
            conn,
            "SELECT status, last_error FROM integration_sync_jobs WHERE tenant_id = %s AND status = 'failed'",
            (tenant_id,),
        )
        assert failed and "Account code 999" in failed["last_error"]

        fake_api.fail_with = t.TransportError("Xero is unavailable (HTTP 503); will retry.", retryable=True)
        result = t.drain(conn, tenant_id, limit=1)
        assert result["deferred"] == 1
        deferred = fetch_one(
            conn,
            """
            SELECT status, next_attempt_at > now() AS parked
            FROM integration_sync_jobs WHERE tenant_id = %s AND status = 'queued'
            """,
            (tenant_id,),
        )
        conn.rollback()
    assert deferred["status"] == "queued" and deferred["parked"] is True


@requires_db
def test_reconnecting_to_another_org_queues_everything_for_that_ledger(pushable_world, fake_api):
    from studiosaas.services import xero_transport as t
    from studiosaas.db import fetch_all

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        t.backfill(conn, tenant_id)
        t.drain(conn, tenant_id)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE xero_connections SET org_id = 'org-real-2' WHERE tenant_id = %s",
                (tenant_id,),
            )
        queued = t.backfill(conn, tenant_id)
        assert queued["total"] == 2  # the new ledger has seen nothing yet
        result = t.drain(conn, tenant_id)
        conn.commit()
        assert result["sent"] == 2
        links = fetch_all(
            conn,
            "SELECT DISTINCT org_id FROM xero_object_links WHERE tenant_id = %s",
            (tenant_id,),
        )
        conn.rollback()
    assert {l["org_id"] for l in links} == {"org-real-2"}


# ── reconciliation and the demo cycle ────────────────────────────────────


@requires_db
def test_reconcile_is_zero_diff_then_sees_a_cent_move(pushable_world, fake_api):
    from studiosaas.services import xero_transport as t

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        t.backfill(conn, tenant_id)
        t.drain(conn, tenant_id)
        clean = t.reconcile(conn, tenant_id)
        assert (clean["checked"], clean["diffCount"]) == (2, 0)

        fake_api.totals["invoice"] = 109.99  # one cent walks off in the ledger
        dirty = t.reconcile(conn, tenant_id)
        conn.rollback()
    assert dirty["diffCount"] == 1
    assert dirty["diffs"][0]["field"] == "total"
    assert dirty["diffs"][0]["local"] == 110.0 and dirty["diffs"][0]["xero"] == 109.99


@requires_db
def test_demo_cycle_is_clean_only_when_pushed_and_reconciled(pushable_world, fake_api):
    from studiosaas.services import xero_transport as t

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        report = t.run_demo_cycle(conn, tenant_id)
        assert report["clean"] is True and report["pushed"] == 2
        # Running again pushes nothing new — and a run that pushed nothing
        # would prove nothing, so on an EMPTY queue clean must be False...
        idle = t.run_demo_cycle(conn, tenant_id)
        conn.rollback()
    assert idle["pushed"] == 0 and idle["clean"] is False


# ── the gate, walked exactly as the wizard walks it ──────────────────────


@requires_db
def test_enabling_push_through_the_walked_gate_survives_the_check_constraint(pushable_world):
    """Regression: v10.10.0 enabled the transport and the very first live
    enable_push hit the 0037 CHECK — the upsert's INSERT candidate row (push
    on, preconditions NULL) is constraint-checked by PostgreSQL even when ON
    CONFLICT would update. The gate must be walked with the real service
    functions, then flip on, against the real constraint."""

    from studiosaas.services import xero

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant_addons (tenant_id, addon_key, status) VALUES (%s, 'xero', 'active')",
                (tenant_id,),
            )
        xero.confirm_mapping(conn, tenant_id)
        xero.record_demo_run(conn, tenant_id)
        xero.answer_single_entry(conn, tenant_id, decision="ours_only")
        status = xero.set_push_enabled(conn, tenant_id, True)
        assert status.push_enabled is True
        # And off again — pausing must always be allowed.
        status = xero.set_push_enabled(conn, tenant_id, False)
        conn.rollback()
    assert status.push_enabled is False


# ── the enqueue hooks ────────────────────────────────────────────────────


@requires_db
def test_allocation_hook_enqueues_when_the_gate_is_open(pushable_world):
    from studiosaas.services import payments, xero
    from studiosaas.db import fetch_all, fetch_one

    tenant_id = pushable_world["tenant_id"]
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO tenant_addons (tenant_id, addon_key, status) VALUES (%s, 'xero', 'active')",
                (tenant_id,),
            )
            cur.execute(
                """
                INSERT INTO xero_sync_settings
                    (tenant_id, push_enabled, mapping_confirmed_at, demo_run_completed_at,
                     single_entry_decision)
                VALUES (%s, true, now(), now(), 'ours_only')
                """,
                (tenant_id,),
            )
            cur.execute(
                "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
                (tenant_id, pushable_world["account_id"]),
            )
            second_invoice = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO invoice_lines
                    (tenant_id, invoice_id, description, unit_price_cents,
                     tax_rate_bp, tax_cents, total_cents, source_kind)
                VALUES (%s, %s, 'More tuition', 5000, 1000, 500, 5500, 'tuition')
                """,
                (tenant_id, second_invoice),
            )
        from studiosaas.services import billing

        billing.issue_invoice(conn, tenant_id, second_invoice)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payments (tenant_id, billing_account_id, method, amount_cents)
                VALUES (%s, %s, 'cash', 5500) RETURNING id
                """,
                (tenant_id, pushable_world["account_id"]),
            )
            payment_id = str(cur.fetchone()["id"])
        payments.allocate(
            conn, tenant_id, payment_id,
            [payments.Allocation(invoice_id=second_invoice, amount_cents=5500)],
        )
        jobs = fetch_all(
            conn,
            "SELECT local_kind, idempotency_key FROM integration_sync_jobs WHERE tenant_id = %s",
            (tenant_id,),
        )
        conn.rollback()
    # The service-level hook fires on allocation (the invoice hook lives at
    # the API layer). The key carries the org, so a later reconnect requeues.
    assert [j["local_kind"] for j in jobs] == ["payment"]
