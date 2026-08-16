"""Atomic credit-settlement contracts and integration coverage."""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.services import credit_settlements  # noqa: E402


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection

        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM invoices LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 - a missing local DB means skip integration.
        return False


requires_db = pytest.mark.skipif(
    not _database_available(), reason="needs the local PostgreSQL money schema"
)


def test_gross_split_is_integer_exact_and_tax_rounds_half_up():
    assert credit_settlements._gross_split(55_000, 1000) == (50_000, 5_000)
    assert credit_settlements._gross_split(6, 1000) == (5, 1)
    with pytest.raises(credit_settlements.CreditSettlementError):
        credit_settlements._gross_split(5, 1000)
    with pytest.raises(credit_settlements.CreditSettlementError):
        credit_settlements._gross_split(1, 10000)


def test_settlement_contract_is_atomic_and_separate_from_legacy_endpoint():
    source = (BACKEND_ROOT / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    start = source.index('@api_v1.route("/students/<student_id>/credit-settlements"')
    route = source[start : source.index('@api_v1.route("/attendance"', start)]
    assert '@permission_required("credits:write")' in route
    assert "billing:write" in route and "billing:issue" in route
    assert "payments:write" in route
    assert "create_credit_settlement" in route
    service = (BACKEND_ROOT / "studiosaas/services/credit_settlements.py").read_text(
        encoding="utf-8"
    )
    for required in (
        "financial_operation_requests",
        "credit_financial_links",
        "payments.allocate",
        "billing.issue_invoice",
        "record_audit_event",
        "ON CONFLICT (tenant_id, request_id, operation_kind)",
    ):
        assert required in service


@pytest.fixture()
def settlement_tenant():
    from _cms_sources import owner_connection

    tenant_id = str(uuid.uuid4())
    slug = f"settle-{tenant_id[:8]}"
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Settlement Test', %s, 'active', 'starter')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Settlement', 'Settlement Student')
                RETURNING id
                """,
                (tenant_id,),
            )
            student_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO billing_accounts (tenant_id, name, kind, payment_terms_days)
                VALUES (%s, 'Settlement Family', 'family', 14)
                RETURNING id
                """,
                (tenant_id,),
            )
            account_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO tenant_billing_identity
                    (tenant_id, legal_name, trading_name, abn, gst_registered,
                     address_line1, suburb, state, postcode)
                VALUES (%s, 'Settlement Studio Pty Ltd', 'Settlement Studio',
                        '53 004 085 616', true,
                        '4 Fixture Lane', 'Carlton', 'VIC', '3053')
                """,
                (tenant_id,),
            )
            cur.execute(
                """
                INSERT INTO packages (tenant_id, name, credits, price_aud_cents)
                VALUES (%s, 'Ten Credit Package', 10, 55000)
                RETURNING id
                """,
                (tenant_id,),
            )
            package_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO tax_codes (tenant_id, code, name, rate_bp, is_default)
                VALUES (%s, 'GST', 'GST 10%%', 1000, true)
                RETURNING id
                """,
                (tenant_id,),
            )
            tax_code_id = str(cur.fetchone()["id"])
        conn.commit()

    yield {
        "tenant_id": tenant_id,
        "student_id": student_id,
        "account_id": account_id,
        "package_id": package_id,
        "tax_code_id": tax_code_id,
    }

    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


@requires_db
def test_settlement_covers_free_unpaid_paid_and_idempotent_paths(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_all, fetch_one

    t = settlement_tenant
    with owner_connection() as conn:
        free_payload = {
            "requestId": str(uuid.uuid4()),
            "credits": "1",
            "amountCents": 0,
            "paymentMethod": "cash",
            "note": "free make-good",
            "billing": {"createInvoice": False},
        }
        free = credit_settlements.create_credit_settlement(
            conn, t["tenant_id"], t["student_id"], free_payload
        )
        assert free["invoiceId"] is None and free["paymentId"] is None

        unpaid_payload = {
            "requestId": str(uuid.uuid4()),
            "credits": "10",
            "amountCents": 55_000,
            "paymentMethod": "bank_transfer",
            "packageId": t["package_id"],
            "billing": {
                "createInvoice": True,
                "billingAccountId": t["account_id"],
                "taxCodeId": t["tax_code_id"],
                "issueNow": True,
                "paymentReceived": False,
            },
        }
        unpaid = credit_settlements.create_credit_settlement(
            conn, t["tenant_id"], t["student_id"], unpaid_payload
        )
        assert unpaid["netCents"] == 50_000
        assert unpaid["taxCents"] == 5_000
        assert unpaid["paymentId"] is None

        paid_payload = {
            "requestId": str(uuid.uuid4()),
            "credits": "5",
            "amountCents": 27_500,
            "paymentMethod": "bank_transfer",
            "billing": {
                "createInvoice": True,
                "billingAccountId": t["account_id"],
                "taxCodeId": t["tax_code_id"],
                "issueNow": True,
                "paymentReceived": True,
            },
        }
        paid = credit_settlements.create_credit_settlement(
            conn, t["tenant_id"], t["student_id"], paid_payload
        )
        assert paid["paymentId"] and paid["allocationIds"]

        replay = credit_settlements.create_credit_settlement(
            conn, t["tenant_id"], t["student_id"], paid_payload
        )
        assert replay["replayed"] is True
        assert replay["transactionId"] == paid["transactionId"]

        changed = dict(paid_payload)
        changed["amountCents"] = 27_501
        with pytest.raises(credit_settlements.CreditSettlementConflict):
            credit_settlements.create_credit_settlement(
                conn, t["tenant_id"], t["student_id"], changed
            )

        conn.commit()
        invoice = fetch_one(
            conn,
            "SELECT status, total_cents, amount_paid_cents, balance_cents FROM invoices WHERE id = %s",
            (paid["invoiceId"],),
        )
        assert dict(invoice) == {
            "status": "paid",
            "total_cents": 27_500,
            "amount_paid_cents": 27_500,
            "balance_cents": 0,
        }
        link = fetch_one(
            conn,
            "SELECT payment_id, related_credit_transaction_id FROM credit_financial_links WHERE id = %s",
            (paid["financialLinkId"],),
        )
        assert str(link["payment_id"]) == paid["paymentId"]
        assert link["related_credit_transaction_id"] is None
        assert fetch_one(
            conn,
            "SELECT fee_aud_cents FROM credit_transactions WHERE id = %s",
            (unpaid["transactionId"],),
        )["fee_aud_cents"] == 0
        assert len(
            fetch_all(
                conn,
                "SELECT id FROM credit_transactions WHERE tenant_id = %s",
                (t["tenant_id"],),
            )
        ) == 3


@requires_db
def test_invalid_tenant_reference_rolls_back_all_settlement_writes(settlement_tenant):
    from _cms_sources import owner_connection

    t = settlement_tenant
    payload = {
        "requestId": str(uuid.uuid4()),
        "credits": "2",
        "amountCents": 1000,
        "billing": {
            "createInvoice": True,
            "billingAccountId": str(uuid.uuid4()),
            "issueNow": True,
        },
    }
    with owner_connection() as conn:
        with pytest.raises(credit_settlements.CreditSettlementError):
            credit_settlements.create_credit_settlement(
                conn, t["tenant_id"], t["student_id"], payload
            )
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT count(*) AS n FROM credit_transactions WHERE tenant_id = %s",
                (t["tenant_id"],),
            )
            assert cur.fetchone()["n"] == 0


@requires_db
def test_purchase_and_refund_bridges_enforce_the_legal_shape(settlement_tenant):
    """A refund bridge must point to its purchase and live money records."""

    from _cms_sources import owner_connection

    t = settlement_tenant
    payload = {
        "requestId": str(uuid.uuid4()),
        "credits": "5",
        "amountCents": 27_500,
        "paymentMethod": "bank_transfer",
        "billing": {
            "createInvoice": True,
            "billingAccountId": t["account_id"],
            "taxCodeId": t["tax_code_id"],
            "issueNow": True,
            "paymentReceived": True,
        },
    }
    with owner_connection() as conn:
        purchase = credit_settlements.create_credit_settlement(
            conn, t["tenant_id"], t["student_id"], payload
        )
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO credit_notes
                    (tenant_id, billing_account_id, invoice_id, reason)
                VALUES (%s, %s, %s, 'D-01 bridge test')
                RETURNING id
                """,
                (t["tenant_id"], t["account_id"], purchase["invoiceId"]),
            )
            credit_note_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                SELECT id, account_id, balance_after
                FROM credit_transactions
                WHERE tenant_id = %s AND id = %s
                """,
                (t["tenant_id"], purchase["transactionId"]),
            )
            purchase_tx = cur.fetchone()
            refund_balance = Decimal(str(purchase_tx["balance_after"])) - Decimal("2")
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (tenant_id, student_id, account_id, transaction_type,
                     amount, balance_after, fee_aud_cents, note)
                VALUES (%s, %s, %s, 'refund', -2, %s, -11000, 'D-01 bridge test')
                RETURNING id
                """,
                (
                    t["tenant_id"], t["student_id"], purchase_tx["account_id"],
                    refund_balance,
                ),
            )
            refund_tx_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO refunds
                    (tenant_id, payment_id, credit_note_id, amount_cents, reason)
                VALUES (%s, %s, %s, 11000, 'D-01 bridge test')
                RETURNING id
                """,
                (
                    t["tenant_id"], purchase["paymentId"], credit_note_id,
                ),
            )
            refund_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO credit_financial_links
                    (tenant_id, credit_transaction_id, related_credit_transaction_id,
                     invoice_id, invoice_line_id, payment_id, credit_note_id, refund_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    t["tenant_id"], refund_tx_id, purchase["transactionId"],
                    purchase["invoiceId"], purchase["invoiceLineId"],
                    purchase["paymentId"], credit_note_id, refund_id,
                ),
            )
            assert cur.fetchone()["id"]

            cur.execute("SAVEPOINT invalid_refund_bridge")
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (tenant_id, student_id, account_id, transaction_type,
                     amount, balance_after, fee_aud_cents, note)
                VALUES (%s, %s, %s, 'refund', -1, %s, -5500, 'invalid bridge')
                RETURNING id
                """,
                (
                    t["tenant_id"], t["student_id"], purchase_tx["account_id"],
                    refund_balance - Decimal("1"),
                ),
            )
            invalid_refund_id = str(cur.fetchone()["id"])
            with pytest.raises(Exception):
                cur.execute(
                    """
                    INSERT INTO credit_financial_links
                        (tenant_id, credit_transaction_id, related_credit_transaction_id,
                         invoice_id, invoice_line_id, payment_id, credit_note_id, refund_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        t["tenant_id"], invalid_refund_id, invalid_refund_id,
                        purchase["invoiceId"], purchase["invoiceLineId"],
                        purchase["paymentId"], credit_note_id, refund_id,
                    ),
                )
            cur.execute("ROLLBACK TO SAVEPOINT invalid_refund_bridge")
        conn.commit()
