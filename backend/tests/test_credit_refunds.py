"""E-01 document-adjusting credit refund integration coverage."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.services import credit_refunds, credit_settlements  # noqa: E402
from test_credit_settlements import requires_db  # noqa: E402


def test_refund_api_contract_is_tenant_scoped_and_permission_gated():
    source = (BACKEND_ROOT / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    start = source.index('@api_v1.route("/students/<student_id>/credit-refunds"')
    route_block = source[start : source.index('@api_v1.route("/attendance"', start)]
    assert '@permission_required("credits:read")' in route_block
    assert '@permission_required("credits:refund")' in route_block
    assert "payments:refund" in route_block
    assert "billing:issue" in route_block
    service = (BACKEND_ROOT / "studiosaas/services/credit_refunds.py").read_text(encoding="utf-8")
    assert "sourceCreditTransactionId" in service
    assert "credit_financial_links" in service


@pytest.fixture()
def settlement_tenant():
    from _cms_sources import owner_connection

    tenant_id = str(uuid.uuid4())
    slug = f"refund-{tenant_id[:8]}"
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Refund Test', %s, 'active', 'starter')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Refund', 'Refund Student')
                RETURNING id
                """,
                (tenant_id,),
            )
            student_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO billing_accounts (tenant_id, name, kind, payment_terms_days)
                VALUES (%s, 'Refund Family', 'family', 14)
                RETURNING id
                """,
                (tenant_id,),
            )
            account_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO tenant_billing_identity
                    (tenant_id, legal_name, trading_name, abn, gst_registered)
                VALUES (%s, 'Refund Studio Pty Ltd', 'Refund Studio',
                        '53 004 085 616', true)
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


def _paid_purchase(conn, tenant: dict, *, amount_cents: int = 55_000, credits: str = "10"):
    payload = {
        "requestId": str(uuid.uuid4()),
        "credits": credits,
        "amountCents": amount_cents,
        "paymentMethod": "bank_transfer",
        "billing": {
            "createInvoice": True,
            "billingAccountId": tenant["account_id"],
            "taxCodeId": tenant["tax_code_id"],
            "issueNow": True,
            "paymentReceived": True,
        },
    }
    return credit_settlements.create_credit_settlement(
        conn, tenant["tenant_id"], tenant["student_id"], payload
    )


@requires_db
def test_full_refund_reverses_credit_payment_invoice_and_bridge(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    t = settlement_tenant
    with owner_connection() as conn:
        purchase = _paid_purchase(conn, t)
        payload = {
            "requestId": str(uuid.uuid4()),
            "sourceCreditTransactionId": purchase["transactionId"],
            "credits": "10",
            "amountCents": 55_000,
            "paymentMethod": "bank_transfer",
            "reason": "课程取消",
            "billing": {"adjustDocuments": True},
        }
        refunded = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], payload
        )
        assert refunded["creditNoteNumber"].startswith("CN-")
        assert refunded["netRefundedCents"] == 50_000
        assert refunded["taxRefundedCents"] == 5_000
        replay = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], payload
        )
        assert replay["replayed"] is True
        assert replay["refundId"] == refunded["refundId"]
        conn.commit()

        payment = fetch_one(
            conn,
            "SELECT status, refunded_cents FROM payments WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], purchase["paymentId"]),
        )
        assert payment["status"] == "refunded"
        assert payment["refunded_cents"] == 55_000
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM payment_allocations WHERE tenant_id = %s AND payment_id = %s",
            (t["tenant_id"], purchase["paymentId"]),
        )["n"] == 0
        invoice_state = fetch_one(
            conn,
            "SELECT amount_credited_cents, balance_cents, status FROM invoices WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], purchase["invoiceId"]),
        )
        assert invoice_state["amount_credited_cents"] == 55_000
        assert invoice_state["balance_cents"] == 0
        assert invoice_state["status"] == "paid"
        assert fetch_one(
            conn,
            "SELECT balance::numeric AS balance FROM credit_accounts WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL",
            (t["tenant_id"], t["student_id"]),
        )["balance"] == 0
        bridge = fetch_one(
            conn,
            """
            SELECT l.related_credit_transaction_id, l.credit_note_id, l.refund_id,
                   cn.status, cn.supplier_snapshot, cn.recipient_snapshot
              FROM credit_financial_links l
              JOIN credit_notes cn ON cn.tenant_id = l.tenant_id AND cn.id = l.credit_note_id
             WHERE l.tenant_id = %s AND l.credit_transaction_id = %s
            """,
            (t["tenant_id"], refunded["refundTransactionId"]),
        )
        assert str(bridge["related_credit_transaction_id"]) == purchase["transactionId"]
        assert bridge["status"] == "issued"
        assert bridge["supplier_snapshot"] and bridge["recipient_snapshot"]


@requires_db
def test_partial_refunds_accumulate_exact_tax_and_reject_overage(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_all, fetch_one

    t = settlement_tenant
    with owner_connection() as conn:
        purchase = _paid_purchase(conn, t)
        first = {
            "requestId": str(uuid.uuid4()),
            "sourceCreditTransactionId": purchase["transactionId"],
            "credits": "2",
            "amountCents": 11_000,
            "paymentMethod": "bank_transfer",
            "reason": "部分退课一",
            "billing": {"adjustDocuments": True},
        }
        second = {
            **first,
            "requestId": str(uuid.uuid4()),
            "credits": "3",
            "amountCents": 16_500,
            "reason": "部分退课二",
        }
        a = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], first
        )
        b = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], second
        )
        assert a["taxRefundedCents"] == 1_000
        assert b["taxRefundedCents"] == 1_500
        third = {
            **first,
            "requestId": str(uuid.uuid4()),
            "credits": "5",
            "amountCents": 27_500,
            "reason": "最后一笔退课",
        }
        c = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], third
        )
        assert c["taxRefundedCents"] == 2_500
        conn.commit()
        totals = fetch_one(
            conn,
            "SELECT sum(total_cents) AS total, sum(tax_cents) AS tax FROM credit_notes WHERE tenant_id = %s",
            (t["tenant_id"],),
        )
        assert totals["total"] == 55_000
        assert totals["tax"] == 5_000
        rates = fetch_all(
            conn,
            "SELECT tax_rate_bp FROM credit_note_lines WHERE tenant_id = %s ORDER BY created_at, id",
            (t["tenant_id"],),
        )
        assert [row["tax_rate_bp"] for row in rates] == [1000, 1000, 1000]
        invoice_state = fetch_one(
            conn,
            "SELECT amount_credited_cents, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], purchase["invoiceId"]),
        )
        assert invoice_state["amount_credited_cents"] == 55_000
        assert invoice_state["balance_cents"] == 0

        over = {
            **first,
            "requestId": str(uuid.uuid4()),
            "credits": "6",
            "amountCents": 33_000,
            "reason": "超过剩余",
        }
        with pytest.raises(credit_refunds.CreditRefundError):
            credit_refunds.create_credit_refund(
                conn, t["tenant_id"], t["student_id"], over
            )
        conn.rollback()
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM credit_financial_links WHERE tenant_id = %s",
            (t["tenant_id"],),
        )["n"] == 4


@pytest.mark.parametrize(
    ("amount_cents", "remaining_net", "remaining_tax", "original_total", "original_net", "expected"),
    [
        (1, 1, 0, 1, 1, (1, 0)),  # non-GST one-cent line
        (100, 400, 35, 435, 400, (92, 8)),  # 8.75% custom tax rounding
    ],
)
def test_refund_tax_split_handles_non_gst_custom_rate_and_one_cent_rounding(
    amount_cents, remaining_net, remaining_tax, original_total, original_net, expected
):
    assert credit_refunds._refund_tax_split(
        amount_cents, remaining_net, remaining_tax, original_total, original_net
    ) == expected


@requires_db
def test_custom_tax_rate_reaches_credit_note_document(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_all, fetch_one
    from studiosaas.services.invoice_documents import build_credit_note_document

    t = settlement_tenant
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tax_codes SET rate_bp = 875 WHERE tenant_id = %s", (t["tenant_id"],))
        purchase = _paid_purchase(conn, t)
        refund = credit_refunds.create_credit_refund(
            conn,
            t["tenant_id"],
            t["student_id"],
            {
                "requestId": str(uuid.uuid4()),
                "sourceCreditTransactionId": purchase["transactionId"],
                "credits": "10",
                "amountCents": 55_000,
                "paymentMethod": "bank_transfer",
                "reason": "custom tax refund",
                "billing": {"adjustDocuments": True},
            },
        )
        note = fetch_one(
            conn,
            "SELECT id, status, number, subtotal_cents, tax_cents, total_cents, supplier_snapshot, recipient_snapshot FROM credit_notes WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], refund["creditNoteId"]),
        )
        lines = fetch_all(
            conn,
            "SELECT id, description, quantity, unit_price_cents, tax_rate_bp, tax_cents, total_cents FROM credit_note_lines WHERE tenant_id = %s AND credit_note_id = %s",
            (t["tenant_id"], refund["creditNoteId"]),
        )
        document = build_credit_note_document(note, lines)
        assert document["document"]["kind"] == "credit_note"
        assert document["lines"][0]["taxRateBp"] == 875
        assert document["totals"]["totalCents"] == 55_000
        assert document["totals"]["taxCents"] == refund["taxRefundedCents"]
        conn.commit()


@requires_db
def test_non_gst_one_cent_refund_document_is_zero_tax(settlement_tenant):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_all, fetch_one
    from studiosaas.services.invoice_documents import build_credit_note_document

    t = settlement_tenant
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE tax_codes SET rate_bp = 0 WHERE tenant_id = %s", (t["tenant_id"],))
        purchase = _paid_purchase(conn, t, amount_cents=1)
        refund = credit_refunds.create_credit_refund(
            conn,
            t["tenant_id"],
            t["student_id"],
            {
                "requestId": str(uuid.uuid4()),
                "sourceCreditTransactionId": purchase["transactionId"],
                "credits": "1",
                "amountCents": 1,
                "paymentMethod": "bank_transfer",
                "reason": "one cent no GST refund",
                "billing": {"adjustDocuments": True},
            },
        )
        note = fetch_one(
            conn,
            "SELECT id, status, number, subtotal_cents, tax_cents, total_cents, supplier_snapshot, recipient_snapshot FROM credit_notes WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], refund["creditNoteId"]),
        )
        lines = fetch_all(
            conn,
            "SELECT id, description, quantity, unit_price_cents, tax_rate_bp, tax_cents, total_cents FROM credit_note_lines WHERE tenant_id = %s AND credit_note_id = %s",
            (t["tenant_id"], refund["creditNoteId"]),
        )
        document = build_credit_note_document(note, lines)
        assert refund["taxRefundedCents"] == 0
        assert document["lines"][0]["taxRateBp"] == 0
        assert document["totals"] == {"subtotalCents": 1, "taxCents": 0, "totalCents": 1}
        conn.commit()


@requires_db
def test_unbridged_purchase_and_cross_tenant_source_are_business_errors(settlement_tenant):
    from _cms_sources import owner_connection

    t = settlement_tenant
    with owner_connection() as conn:
        free = credit_settlements.create_credit_settlement(
            conn,
            t["tenant_id"],
            t["student_id"],
            {
                "requestId": str(uuid.uuid4()),
                "credits": "1",
                "amountCents": 0,
                "billing": {"createInvoice": False},
            },
        )
        with pytest.raises(credit_refunds.CreditRefundError):
            credit_refunds.create_credit_refund(
                conn,
                t["tenant_id"],
                t["student_id"],
                {
                    "requestId": str(uuid.uuid4()),
                    "sourceCreditTransactionId": free["transactionId"],
                    "credits": "1",
                    "amountCents": 1,
                    "reason": "无桥接",
                    "billing": {"adjustDocuments": True},
                },
            )
        conn.rollback()
        with pytest.raises(credit_refunds.CreditRefundError):
            credit_refunds.create_credit_refund(
                conn,
                t["tenant_id"],
                str(uuid.uuid4()),
                {
                    "requestId": str(uuid.uuid4()),
                    "sourceCreditTransactionId": str(uuid.uuid4()),
                    "credits": "1",
                    "amountCents": 1,
                    "reason": "跨租户",
                    "billing": {"adjustDocuments": True},
                },
            )


@requires_db
def test_credits_only_refund_uses_the_same_source_and_is_idempotent(settlement_tenant):
    """The checkbox-off branch still uses the strict source-aware endpoint."""

    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    t = settlement_tenant
    with owner_connection() as conn:
        purchase = credit_settlements.create_credit_settlement(
            conn,
            t["tenant_id"],
            t["student_id"],
            {
                "requestId": str(uuid.uuid4()),
                "credits": "5",
                "amountCents": 0,
                "billing": {"createInvoice": False},
            },
        )
        payload = {
            "requestId": str(uuid.uuid4()),
            "sourceCreditTransactionId": purchase["transactionId"],
            "credits": "2",
            "amountCents": 0,
            "paymentMethod": "bank_transfer",
            "reason": "credits-only correction",
            "billing": {"adjustDocuments": False},
        }
        refunded = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], payload
        )
        replay = credit_refunds.create_credit_refund(
            conn, t["tenant_id"], t["student_id"], payload
        )
        assert replay["replayed"] is True
        assert replay["refundTransactionId"] == refunded["refundTransactionId"]
        assert refunded["invoiceId"] is None
        assert refunded["amountRefundedCents"] == 0
        source = fetch_one(
            conn,
            "SELECT source_credit_transaction_id FROM credit_transactions WHERE tenant_id = %s AND id = %s",
            (t["tenant_id"], refunded["refundTransactionId"]),
        )
        assert str(source["source_credit_transaction_id"]) == purchase["transactionId"]
        assert fetch_one(
            conn,
            "SELECT balance FROM credit_accounts WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL",
            (t["tenant_id"], t["student_id"]),
        )["balance"] == 3
        conn.commit()
