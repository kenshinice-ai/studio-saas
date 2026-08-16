"""Invariants for the v10.0.0 money layer.

Split deliberately into two halves.

The **static** half runs everywhere and guards the decisions that are easy to
undo by accident: which role may read what, which arithmetic is used for tax,
what a channel costs to send on, and that no route was quietly left ungated.

The **integration** half needs a real PostgreSQL and is skipped without one. It
exists because the most important guarantees in this layer are enforced by
triggers and constraints, and a test suite that never reaches the database
cannot see any of them. An invoice that is supposed to be immutable is not
tested by asserting that the code does not try to change it — it is tested by
trying to change it and being refused.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import date, time, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.auth import ROLE_PERMISSIONS  # noqa: E402
from studiosaas.models import Role  # noqa: E402
from studiosaas.services import billing, entitlements, notification_channels  # noqa: E402
from studiosaas.services import teaching_pay, xero  # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# Static
# ══════════════════════════════════════════════════════════════════════


def test_a_teacher_can_never_read_what_a_family_owes():
    """Separation of duties, asserted rather than assumed.

    A teacher needs their own hours and their own students. Giving them any
    billing key would also give them every family's balance, which is neither
    their business nor something a studio would expect a scheduling change to
    have granted.
    """

    teacher = ROLE_PERMISSIONS[Role.TEACHER]
    forbidden = {key for key in teacher if key.startswith(("billing:", "payments:"))}
    assert not forbidden, f"teacher role leaked billing keys: {sorted(forbidden)}"
    assert "payroll:self:read" in teacher
    assert "payroll:read" not in teacher, "that key reads every teacher's pay, not just their own"


def test_only_the_owner_may_connect_a_merchant_or_accounting_account():
    """`integrations:manage` holds live credentials for someone else's money."""

    assert "integrations:manage" in ROLE_PERMISSIONS[Role.OWNER]
    for role in (Role.MANAGER, Role.FRONT_DESK, Role.STAFF, Role.TEACHER):
        assert "integrations:manage" not in ROLE_PERMISSIONS[role], role


def test_front_desk_can_take_money_but_not_send_it_back():
    """Refunds move money outward and want a second pair of eyes."""

    front_desk = ROLE_PERMISSIONS[Role.FRONT_DESK]
    assert {"billing:issue", "payments:write"} <= front_desk
    assert "payments:refund" not in front_desk
    assert "payroll:write" not in front_desk


def test_tax_is_rounded_half_up_not_to_even():
    """Python rounds halves to even; invoices do not.

    ``round(0.5)`` is ``0``. An invoice line of $0.05 at 10% GST is one cent of
    tax, not zero, and a system that disagrees with the accountant by a cent
    costs more to explain than it did to compute.
    """

    assert billing.line_amounts(1, 5, 1000) == (5, 1, 6)
    assert billing.line_amounts(1, 15, 1000) == (15, 2, 17)


def test_tax_rounds_once_on_the_line_not_per_unit():
    """3 × $33.33 at 10% is $9.999 of tax → $10.00, not 3 × $0.33."""

    net, tax, total = billing.line_amounts(3, 3333, 1000)
    assert (net, tax, total) == (9999, 1000, 10999)


def test_quantities_accept_decimals_without_going_through_float():
    net, tax, total = billing.line_amounts(Decimal("2.5"), 4000, 0)
    assert (net, tax, total) == (10000, 0, 10000)


def test_line_amounts_rejects_nonsense():
    for bad in (0, -1):
        with pytest.raises(billing.BillingError):
            billing.line_amounts(bad, 1000, 0)
    with pytest.raises(billing.BillingError):
        billing.line_amounts(1, 1000, 10001)


def test_lesson_reminders_default_to_no_paid_channel():
    """The calendar feed carries them, for nothing.

    Reminders are roughly three quarters of a studio's message volume and the
    part a subscription replaces entirely. Defaulting them to SMS would hand
    every new tenant a bill they did not need to pay.
    """

    assert notification_channels.DEFAULT_ROUTES["lesson_reminder"] == ()
    assert "sms" in notification_channels.DEFAULT_ROUTES["lesson_cancelled"], (
        "a same-day cancellation cannot go by calendar feed: clients poll on "
        "their own schedule and may not see it for hours"
    )
    assert "sms" in notification_channels.DEFAULT_ROUTES["invoice_overdue"]


def test_chinese_messages_are_costed_as_ucs2_segments():
    """A bilingual studio hits the 70-character limit on every Chinese message.

    Counting them at the GSM-7 length of 160 would under-estimate the bill by
    more than half, which is exactly the surprise this layer exists to avoid.
    """

    ascii_body = "A" * 200
    chinese_body = "课" * 80
    assert notification_channels.segments_for(ascii_body) == 2
    assert notification_channels.segments_for(chinese_body) == 2
    assert notification_channels.segments_for("课") == 1
    assert notification_channels.segments_for("") == 0


def test_the_money_chain_is_available_on_every_tier():
    """Scheduling, invoicing and being paid are one job, not three features.

    An entry-tier tenant is a single teacher whose entire business is that
    chain. Selling one link separately does not make a cheaper product, it
    makes a broken one.
    """

    for feature in (
        entitlements.FEATURE_BILLING,
        entitlements.FEATURE_ONLINE_PAYMENTS,
        entitlements.FEATURE_RECURRING_LESSONS,
        entitlements.FEATURE_CALENDAR_SUBSCRIPTIONS,
    ):
        assert feature in entitlements.BASELINE_FEATURES, feature


def test_xero_is_an_addon_and_not_bundled_into_any_tier():
    assert entitlements.FEATURE_XERO in entitlements.ADDON_FEATURES
    assert entitlements.FEATURE_XERO not in entitlements.BASELINE_FEATURES


def test_standalone_is_entitled_to_everything(monkeypatch):
    """There is nobody to bill and no upsell to protect."""

    monkeypatch.setenv("STUDIOSAAS_MODE", "standalone")
    resolved = entitlements.resolve(conn=None, tenant_id="irrelevant")
    assert resolved.standalone
    assert resolved.has(entitlements.FEATURE_XERO)
    assert resolved.has(entitlements.FEATURE_REPORTS)


def test_plan_features_survive_a_corrupt_stored_value():
    """A read path may never take a console down over a stored value."""

    assert entitlements._plan_features({"features": "not json"}) == set()
    assert entitlements._plan_features({"features": None}) == set()
    assert entitlements._plan_features(None) == set()
    assert entitlements._plan_features({"features": {"a": True, "b": False}}) == {"a"}


def test_employee_wages_may_not_be_pushed_as_a_payable_bill():
    """Posting wages as a bill bypasses the payroll accounts and misstates the books."""

    assert xero.payable_export_kind("contractor") == "bill"
    assert xero.payable_export_kind("employee") == "summary_only"
    with pytest.raises(xero.XeroError):
        # Unset must refuse rather than guess: a wrong guess is discovered at
        # year end, by an accountant, in somebody else's ledger.
        xero.payable_export_kind("unset")


def test_xero_gate_lists_every_blocker_not_just_the_first():
    """The wizard shows what is left, so a studio can work the list."""

    status = xero.GateStatus(
        entitled=False, connected=False, mapping_confirmed=False,
        demo_run_completed=False, single_entry_answered=False, push_enabled=False,
        transport_available=False,
    )
    assert not status.can_enable
    assert status.blockers() == [
        "addon_not_active", "not_connected", "mapping_not_confirmed",
        "demo_run_not_completed", "single_entry_not_answered", "transport_not_available",
    ]

    ready = xero.GateStatus(
        entitled=True, connected=True, mapping_confirmed=True,
        demo_run_completed=True, single_entry_answered=True, push_enabled=False,
        transport_available=True,
    )
    assert ready.can_enable and ready.blockers() == []


def test_xero_transport_blocks_enable_even_when_every_gate_step_is_complete(monkeypatch):
    status = xero.GateStatus(
        entitled=True, connected=True, mapping_confirmed=True,
        demo_run_completed=True, single_entry_answered=True, push_enabled=False,
        transport_available=False,
    )
    assert status.blockers() == ["transport_not_available"]
    assert not status.can_enable

    monkeypatch.setattr(xero, "gate_status", lambda conn, tenant_id: status)
    with pytest.raises(xero.XeroError, match="transport_not_available"):
        xero.set_push_enabled(object(), "tenant", True)


def test_xero_enqueue_never_creates_a_job_when_history_says_push_enabled(monkeypatch):
    status = xero.GateStatus(
        entitled=True, connected=True, mapping_confirmed=True,
        demo_run_completed=True, single_entry_answered=True, push_enabled=True,
        transport_available=False,
    )
    monkeypatch.setattr(xero, "gate_status", lambda conn, tenant_id: status)

    class NoWriteConnection:
        def cursor(self):
            raise AssertionError("transport-unavailable enqueue must not open a write cursor")

    assert xero.enqueue(NoWriteConnection(), "tenant", local_kind="invoice", local_id="invoice") is None


def test_xero_disable_remains_safe_when_transport_is_unavailable(monkeypatch):
    status = xero.GateStatus(
        entitled=True, connected=True, mapping_confirmed=True,
        demo_run_completed=True, single_entry_answered=True, push_enabled=False,
        transport_available=False,
    )
    writes = []
    monkeypatch.setattr(xero, "_upsert_settings", lambda conn, tenant_id, **columns: writes.append(columns))
    monkeypatch.setattr(xero, "gate_status", lambda conn, tenant_id: status)

    assert xero.set_push_enabled(object(), "tenant", False) is status
    assert writes == [{"push_enabled": "false"}]


def test_pay_bases_cover_the_five_ways_studios_actually_pay():
    assert set(teaching_pay.RATE_BASES) == {
        "per_lesson", "per_hour", "per_head", "percent_of_tuition", "per_session",
    }


def test_per_hour_pay_rounds_half_up():
    rate = teaching_pay.Rate(basis="per_hour", amount_cents=6000, percent_bp=None)
    assert teaching_pay.session_amount(rate, duration_minutes=45) == 4500
    assert teaching_pay.session_amount(rate, duration_minutes=50) == 5000  # 50.0 exactly
    assert teaching_pay.session_amount(rate, duration_minutes=25) == 2500


def test_percent_of_tuition_pay_uses_basis_points():
    rate = teaching_pay.Rate(basis="percent_of_tuition", amount_cents=None, percent_bp=6000)
    assert teaching_pay.session_amount(rate, tuition_basis_cents=10000) == 6000


def test_manual_payment_methods_exclude_card_and_direct_debit():
    """Those arrive from a provider.

    Letting somebody type one in creates a payment with no counterpart in any
    merchant account, which reconciles to nothing and is discovered a month
    later by whoever is matching the bank statement.
    """

    from studiosaas.services import payments

    assert "card" not in payments.MANUAL_METHODS
    assert "direct_debit" not in payments.MANUAL_METHODS
    assert set(payments.MANUAL_METHODS) == {"bank_transfer", "cash", "other"}


def test_every_money_route_declares_a_permission():
    """No route in this layer may rely on `auth_required` alone by accident.

    The two that do are deliberate and named here, so adding a third is a
    decision somebody has to make in this file rather than an omission.
    """

    import re

    source = (BACKEND_ROOT / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    marker = source.index("v10.0.0 — the money layer")
    section = source[marker:]

    intentionally_auth_only = {
        # Resolves the caller's own entitlements; every authenticated role may
        # ask what the studio can do.
        "get_entitlements",
        # A teacher reads their own timesheet; the "their own" half is enforced
        # inside the handler because it is a property of the request.
        "teaching_timesheet",
        # A teacher confirms their own period, or a manager confirms it for
        # them — checked in the handler for the same reason.
        "teaching_confirm_period",
    }
    public_by_design = {"public_calendar_feed"}

    for match in re.finditer(
        r"@api_v1\.route\((.*?)\)\n((?:@\w+.*\n)*)def (\w+)", section
    ):
        decorators, name = match.group(2), match.group(3)
        if name in public_by_design or name in intentionally_auth_only:
            continue
        assert (
            "permission_required" in decorators or "super_admin_required" in decorators
        ), f"{name} is reachable with a session but no permission check"


# ══════════════════════════════════════════════════════════════════════
# Integration — needs PostgreSQL
# ══════════════════════════════════════════════════════════════════════


def _database_available() -> bool:
    try:
        from _cms_sources import owner_connection as connect  # 夹具造世界用属主

        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM invoices LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 — any failure means "no usable database"
        return False


requires_db = pytest.mark.skipif(
    not _database_available(),
    reason="needs a PostgreSQL with migrations through 0038 applied",
)


@pytest.fixture()
def money_tenant():
    """A throwaway tenant with one payer and one student, torn down after."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    tenant_id = str(uuid.uuid4())
    slug = f"t{tenant_id[:8]}"
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Money Test', %s, 'active', 'starter')
                """,
                (tenant_id, slug),
            )
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Test', 'Test Student') RETURNING id
                """,
                (tenant_id,),
            )
            student_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO billing_accounts (tenant_id, name, payment_terms_days)
                VALUES (%s, 'Test Family', 14) RETURNING id
                """,
                (tenant_id,),
            )
            account_id = cur.fetchone()["id"]
            # 真实工作室在开票之前一定填过开票信息 —— v10.1.1 起
            # issuing_blockers() 会拒绝没有 ABN 的 GST 发票。夹具不填，
            # 就比真实租户简单，于是测的是一个不存在的工作室。
            cur.execute(
                """
                INSERT INTO tenant_billing_identity
                    (tenant_id, legal_name, trading_name, abn, gst_registered,
                        address_line1, suburb, state, postcode)
                VALUES (%s, 'Fixture Studio Pty Ltd', 'Fixture Studio',
                        '53 004 085 616', true,
                        '1 Fixture Lane', 'Carlton', 'VIC', '3053')
                ON CONFLICT (tenant_id) DO NOTHING
                """,
                (tenant_id,),
            )
        conn.commit()

    yield {"tenant_id": tenant_id, "student_id": str(student_id), "account_id": str(account_id)}

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
        conn.commit()


def _draft_with_line(conn, tenant_id, account_id, *, cents=10000, tax_bp=1000):
    net, tax, total = billing.line_amounts(1, cents, tax_bp)
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
            (tenant_id, account_id),
        )
        invoice_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO invoice_lines (tenant_id, invoice_id, description, unit_price_cents,
                                       tax_rate_bp, tax_cents, total_cents)
            VALUES (%s, %s, 'Term tuition', %s, %s, %s, %s)
            """,
            (tenant_id, invoice_id, cents, tax_bp, tax, total),
        )
    return str(invoice_id)


@requires_db
def test_issued_invoice_figures_cannot_be_changed(money_tenant):
    """Enforced by trigger, so no code path can forget it."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    with connect() as conn:
        invoice_id = _draft_with_line(conn, money_tenant["tenant_id"], money_tenant["account_id"])
        billing.issue_invoice(conn, money_tenant["tenant_id"], invoice_id)
        conn.commit()

        with pytest.raises(Exception) as caught:
            with conn.cursor() as cur:
                cur.execute("UPDATE invoices SET total_cents = 1 WHERE id = %s", (invoice_id,))
        conn.rollback()
        assert "immutable" in str(caught.value).lower()


@requires_db
def test_issued_invoice_identity_snapshot_survives_live_edits(money_tenant):
    """Issued documents keep the names and addresses that were actually sent."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.db import fetch_one

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        invoice_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=1000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, invoice_id)
        before = fetch_one(
            conn,
            """
            SELECT supplier_snapshot, recipient_snapshot, snapshot_schema_version
            FROM invoices WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, invoice_id),
        )
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE billing_accounts SET name = 'Renamed Family', email = 'new@example.test' "
                "WHERE tenant_id = %s AND id = %s",
                (tenant_id, money_tenant["account_id"]),
            )
            cur.execute(
                "UPDATE tenant_billing_identity SET legal_name = 'New Legal Pty Ltd', "
                "trading_name = 'New Trading' WHERE tenant_id = %s",
                (tenant_id,),
            )
        conn.commit()

        after = fetch_one(
            conn,
            """
            SELECT supplier_snapshot, recipient_snapshot, snapshot_schema_version
            FROM invoices WHERE tenant_id = %s AND id = %s
            """,
            (tenant_id, invoice_id),
        )
        assert after == before

        new_invoice_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=1000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, new_invoice_id)
        newer = fetch_one(
            conn,
            "SELECT supplier_snapshot, recipient_snapshot FROM invoices WHERE id = %s",
            (new_invoice_id,),
        )
        assert newer["supplier_snapshot"]["legalName"] == "New Legal Pty Ltd"
        assert newer["recipient_snapshot"]["displayName"] == "Renamed Family"


def test_0043_declares_the_single_snapshot_bridge_and_idempotency_contract():
    """The forward migration cannot silently lose one of the v10.7.0 invariants."""

    migration = (
        BACKEND_ROOT / "db/migrations/0043_invoice_and_credit_settlements.sql"
    ).read_text(encoding="utf-8")
    for required in (
        "kind IN ('person', 'family', 'organisation')",
        "supplier_snapshot",
        "recipient_snapshot",
        "credit_financial_links",
        "financial_operation_requests",
        "UNIQUE (tenant_id, request_id, operation_kind)",
        "assert_issued_invoice_is_immutable",
        "assert_credit_financial_link_is_legal",
        "ROW LEVEL SECURITY",
    ):
        assert required in migration


def test_0044_declares_source_credit_transaction_provenance_and_safe_backfill():
    """Every refund must name its purchase source in the ledger itself."""

    migration_path = BACKEND_ROOT / "db/migrations/0044_credit_refund_source.sql"
    assert migration_path.is_file()
    migration = migration_path.read_text(encoding="utf-8")
    for required in (
        "source_credit_transaction_id",
        "FOREIGN KEY (tenant_id, source_credit_transaction_id)",
        "ON DELETE RESTRICT",
        "credit_transactions_source_credit_transaction_idx",
        "related_credit_transaction_id",
        "unresolved",
        "transaction_type = 'refund'",
        "transaction_type = 'purchase'",
        "source_credit_transaction_id <> id",
    ):
        assert required in migration


def test_billing_account_api_has_two_recipient_paths_without_auto_merge():
    """The payer API exposes search/parse/create contracts, not a second model."""

    source = (BACKEND_ROOT / "studiosaas/api_v1.py").read_text(encoding="utf-8")
    start = source.index('def billing_accounts():')
    end = source.index('@api_v1.route("/billing/accounts/<account_id>/members"', start)
    route = source[start:end]
    for required in (
        "request.args.get(\"q\")",
        "request.args.get(\"kind\")",
        "request.args.get(\"studentId\")",
        "LIMIT %s OFFSET %s",
        "possibleDuplicates",
        "requiresReview",
        "_reject_unknown_keys",
        "student_id",
        "billing_account_members",
        "person, family, or organisation",
    ):
        assert required in route
    assert "ON CONFLICT (billing_account_id, student_id) DO NOTHING" in route
    assert "自动合并" not in route


@requires_db
def test_credit_financial_link_is_unique_legal_and_tenant_scoped(money_tenant):
    """A purchase bridge is one-to-one and cannot borrow another tenant's row."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.db import fetch_one

    tenant_id = money_tenant["tenant_id"]
    foreign_tenant_id = str(uuid.uuid4())
    with connect() as conn:
        invoice_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=1000, tax_bp=0
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM invoice_lines WHERE tenant_id = %s AND invoice_id = %s",
                (tenant_id, invoice_id),
            )
            line_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (tenant_id, student_id, transaction_type, amount, fee_aud_cents)
                VALUES (%s, %s, 'purchase', 10, 1000) RETURNING id
                """,
                (tenant_id, money_tenant["student_id"]),
            )
            purchase_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO credit_financial_links
                    (tenant_id, credit_transaction_id, invoice_id, invoice_line_id)
                VALUES (%s, %s, %s, %s)
                """,
                (tenant_id, purchase_id, invoice_id, line_id),
            )
        conn.commit()

        with pytest.raises(Exception):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO credit_financial_links
                        (tenant_id, credit_transaction_id, invoice_id, invoice_line_id)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (tenant_id, purchase_id, invoice_id, line_id),
                )
        conn.rollback()
        assert fetch_one(
            conn,
            "SELECT count(*) AS n FROM credit_financial_links WHERE tenant_id = %s",
            (tenant_id,),
        )["n"] == 1

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO tenants (id, name, slug, status, plan_code)
                    VALUES (%s, 'Foreign Bridge Test', %s, 'active', 'starter')
                    """,
                    (foreign_tenant_id, f"foreign-bridge-{foreign_tenant_id[:8]}"),
                )
                cur.execute(
                    """
                    INSERT INTO students (tenant_id, first_name, display_name)
                    VALUES (%s, 'Foreign', 'Foreign Student') RETURNING id
                    """,
                    (foreign_tenant_id,),
                )
                foreign_student_id = cur.fetchone()["id"]
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (tenant_id, student_id, transaction_type, amount)
                    VALUES (%s, %s, 'purchase', 1) RETURNING id
                    """,
                    (foreign_tenant_id, foreign_student_id),
                )
                foreign_purchase_id = cur.fetchone()["id"]
            conn.commit()

            with pytest.raises(Exception):
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO credit_financial_links
                            (tenant_id, credit_transaction_id, invoice_id, invoice_line_id)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (tenant_id, foreign_purchase_id, invoice_id, line_id),
                    )
            conn.rollback()
        finally:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenants WHERE id = %s", (foreign_tenant_id,))
            conn.commit()


@requires_db
def test_financial_operation_request_rejects_payload_reuse(money_tenant):
    """Retries may read one result, never reinterpret a key with new input."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.db import fetch_one

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        request_id = f"request-{uuid.uuid4()}"
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO financial_operation_requests
                    (tenant_id, request_id, operation_kind, payload_hash, status)
                VALUES (%s, %s, 'credit_settlement', 'hash-a', 'succeeded')
                RETURNING id
                """,
                (tenant_id, request_id),
            )
            operation_id = cur.fetchone()["id"]
        conn.commit()

        with pytest.raises(Exception):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO financial_operation_requests
                        (tenant_id, request_id, operation_kind, payload_hash)
                    VALUES (%s, %s, 'credit_settlement', 'hash-b')
                    """,
                    (tenant_id, request_id),
                )
        conn.rollback()

        with pytest.raises(Exception):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE financial_operation_requests SET payload_hash = 'hash-b' WHERE id = %s",
                    (operation_id,),
                )
        conn.rollback()
        assert fetch_one(
            conn,
            "SELECT payload_hash FROM financial_operation_requests WHERE id = %s",
            (operation_id,),
        )["payload_hash"] == "hash-a"


@requires_db
def test_issued_invoice_lines_cannot_be_changed(money_tenant):
    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    with connect() as conn:
        invoice_id = _draft_with_line(conn, money_tenant["tenant_id"], money_tenant["account_id"])
        billing.issue_invoice(conn, money_tenant["tenant_id"], invoice_id)
        conn.commit()

        with pytest.raises(Exception):
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE invoice_lines SET unit_price_cents = 1 WHERE invoice_id = %s",
                    (invoice_id,),
                )
        conn.rollback()


@requires_db
def test_invoice_numbers_do_not_skip_when_a_transaction_rolls_back(money_tenant):
    """A gap in the sequence is a question nobody can answer later."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        first = billing.next_document_number(conn, tenant_id)
        conn.commit()
        billing.next_document_number(conn, tenant_id)  # burned by the rollback below
        conn.rollback()
        second = billing.next_document_number(conn, tenant_id)
        conn.commit()

    assert int(second.split("-")[1]) == int(first.split("-")[1]) + 1


@requires_db
def test_a_payment_cannot_be_allocated_beyond_its_value(money_tenant):
    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        invoice_id = _draft_with_line(conn, tenant_id, money_tenant["account_id"], cents=50000)
        billing.issue_invoice(conn, tenant_id, invoice_id)
        payment = payments.record_payment(
            conn, tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=1000, method="cash",
            idempotency_key=payments.new_idempotency_key(),
        )
        conn.commit()

        with pytest.raises(Exception) as caught:
            payments.allocate(
                conn, tenant_id, payment["id"],
                [payments.Allocation(invoice_id=invoice_id, amount_cents=99999)],
            )
        conn.rollback()
        assert "exceed" in str(caught.value).lower()


@requires_db
def test_allocation_keeps_the_invoice_status_and_balance_true(money_tenant):
    """The paid total is derived by trigger; nothing writes it by hand."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        invoice_id = _draft_with_line(conn, tenant_id, money_tenant["account_id"], cents=10000)
        issued = billing.issue_invoice(conn, tenant_id, invoice_id)
        total = int(issued["total_cents"])

        half = payments.record_payment(
            conn, tenant_id, billing_account_id=money_tenant["account_id"],
            amount_cents=total // 2, method="cash",
            idempotency_key=payments.new_idempotency_key(),
        )
        payments.auto_allocate(conn, tenant_id, half["id"])
        conn.commit()

        from studiosaas.db import fetch_one

        row = fetch_one(conn, "SELECT status, balance_cents FROM invoices WHERE id = %s", (invoice_id,))
        assert row["status"] == "part_paid"
        assert int(row["balance_cents"]) == total - total // 2

        rest = payments.record_payment(
            conn, tenant_id, billing_account_id=money_tenant["account_id"],
            amount_cents=total - total // 2, method="cash",
            idempotency_key=payments.new_idempotency_key(),
        )
        payments.auto_allocate(conn, tenant_id, rest["id"])
        conn.commit()

        row = fetch_one(conn, "SELECT status, balance_cents FROM invoices WHERE id = %s", (invoice_id,))
        assert row["status"] == "paid"
        assert int(row["balance_cents"]) == 0


@requires_db
def test_preferred_invoice_is_paid_before_older_debt_and_overpayment_falls_back(
    money_tenant,
):
    """A detail-panel payment names its target, then keeps oldest-first for the rest."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        older_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=10000, tax_bp=0
        )
        target_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=4000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, older_id)
        billing.issue_invoice(conn, tenant_id, target_id)

        payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=9000,
            method="bank_transfer",
            idempotency_key=payments.new_idempotency_key(),
        )
        allocations = payments.auto_allocate(
            conn, tenant_id, payment["id"], prefer_invoice_id=target_id
        )
        conn.commit()

        assert [(str(row["invoice_id"]), int(row["amount_cents"])) for row in allocations] == [
            (target_id, 4000),
            (older_id, 5000),
        ]

        from studiosaas.db import fetch_all, fetch_one

        rows = fetch_all(
            conn,
            """
            SELECT invoice_id, amount_cents
            FROM payment_allocations
            WHERE tenant_id = %s AND payment_id = %s
            ORDER BY created_at, id
            """,
            (tenant_id, payment["id"]),
        )
        assert {
            str(row["invoice_id"]): int(row["amount_cents"])
            for row in rows
        } == {
            target_id: 4000,
            older_id: 5000,
        }
        target = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, target_id),
        )
        older = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, older_id),
        )
        assert (target["status"], int(target["balance_cents"])) == ("paid", 0)
        assert (older["status"], int(older["balance_cents"])) == ("part_paid", 5000)


@requires_db
def test_auto_allocate_without_preference_keeps_oldest_first(money_tenant):
    """The explicit target override must not change the default ageing policy."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        older_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=6000, tax_bp=0
        )
        newer_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=6000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, older_id)
        billing.issue_invoice(conn, tenant_id, newer_id)
        payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=6000,
            method="cash",
            idempotency_key=payments.new_idempotency_key(),
        )

        allocations = payments.auto_allocate(conn, tenant_id, payment["id"])
        conn.commit()

        assert [(str(row["invoice_id"]), int(row["amount_cents"])) for row in allocations] == [
            (older_id, 6000)
        ]

        from studiosaas.db import fetch_one

        older = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, older_id),
        )
        newer = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, newer_id),
        )
        assert (older["status"], int(older["balance_cents"])) == ("paid", 0)
        assert (newer["status"], int(newer["balance_cents"])) == ("issued", 6000)


@requires_db
def test_preferred_invoice_rejects_wrong_account_and_cross_tenant_targets(
    money_tenant,
):
    """A named target must fail closed instead of silently paying another debt."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    foreign_tenant_id = str(uuid.uuid4())
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Foreign Money Test', %s, 'active', 'starter')
                """,
                (foreign_tenant_id, f"foreign-{foreign_tenant_id[:8]}"),
            )
            cur.execute(
                """
                INSERT INTO tenant_billing_identity
                    (tenant_id, legal_name, trading_name, abn, gst_registered,
                     address_line1, suburb, state, postcode)
                VALUES (%s, 'Foreign Fixture Pty Ltd', 'Foreign Fixture',
                        '53 004 085 616', true,
                        '2 Fixture Lane', 'Carlton', 'VIC', '3053')
                """,
                (foreign_tenant_id,),
            )
            cur.execute(
                """
                INSERT INTO billing_accounts (tenant_id, name, payment_terms_days)
                VALUES (%s, 'Foreign Family', 14) RETURNING id
                """,
                (foreign_tenant_id,),
            )
            foreign_account_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO billing_accounts (tenant_id, name, payment_terms_days)
                VALUES (%s, 'Wrong Account Family', 14) RETURNING id
                """,
                (tenant_id,),
            )
            wrong_account_id = str(cur.fetchone()["id"])
        conn.commit()

        wrong_account_invoice = _draft_with_line(
            conn, tenant_id, wrong_account_id, cents=1000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, wrong_account_invoice)
        foreign_invoice = _draft_with_line(
            conn, foreign_tenant_id, foreign_account_id, cents=1000, tax_bp=0
        )
        billing.issue_invoice(conn, foreign_tenant_id, foreign_invoice)
        paid_invoice = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=500, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, paid_invoice)
        paid_payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=500,
            method="cash",
            idempotency_key=payments.new_idempotency_key(),
        )
        payments.auto_allocate(conn, tenant_id, paid_payment["id"])
        conn.commit()

        for target_id in (
            wrong_account_invoice,
            foreign_invoice,
            paid_invoice,
            str(uuid.uuid4()),
        ):
            payment = payments.record_payment(
                conn,
                tenant_id,
                billing_account_id=money_tenant["account_id"],
                amount_cents=1000,
                method="cash",
                idempotency_key=payments.new_idempotency_key(),
            )
            with pytest.raises(payments.PaymentError, match="not open for this billing account"):
                payments.auto_allocate(
                    conn, tenant_id, payment["id"], prefer_invoice_id=target_id
                )

            from studiosaas.db import fetch_one

            allocation_count = fetch_one(
                conn,
                "SELECT count(*) AS n FROM payment_allocations WHERE payment_id = %s",
                (payment["id"],),
            )
            assert int(allocation_count["n"]) == 0

        conn.rollback()


@requires_db
def test_payment_events_capture_actor_and_status_chain(money_tenant):
    """The invoice history says who recorded each money state transition."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    actor_id = str(uuid.uuid4())
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (id, email, password_hash, full_name)
                VALUES (%s, %s, 'test-hash', 'Money Operator')
                """,
                (actor_id, f"money-operator-{actor_id[:8]}@example.test"),
            )
        conn.commit()
        try:
            invoice_id = _draft_with_line(
                conn, tenant_id, money_tenant["account_id"], cents=10000, tax_bp=0
            )
            billing.issue_invoice(
                conn, tenant_id, invoice_id, actor_user_id=actor_id
            )

            payment = payments.record_payment(
                conn,
                tenant_id,
                billing_account_id=money_tenant["account_id"],
                amount_cents=5000,
                method="cash",
                idempotency_key=payments.new_idempotency_key(),
                recorded_by_user_id=actor_id,
            )
            payments.auto_allocate(
                conn,
                tenant_id,
                payment["id"],
                actor_user_id=actor_id,
            )
            conn.commit()

            from studiosaas.db import fetch_all

            events = fetch_all(
                conn,
                """
                SELECT event_type, actor_user_id, detail
                FROM invoice_events
                WHERE tenant_id = %s AND invoice_id = %s
                ORDER BY occurred_at,
                    CASE event_type
                        WHEN 'issued' THEN 0
                        WHEN 'part_paid' THEN 1
                        WHEN 'paid' THEN 2
                        ELSE 3
                    END,
                    id
                """,
                (tenant_id, invoice_id),
            )
            assert [row["event_type"] for row in events] == ["issued", "part_paid"]
            assert [str(row["actor_user_id"]) for row in events] == [actor_id, actor_id]
            assert events[1]["detail"] == {
                "amount_cents": 5000,
                "balance_cents": 5000,
                "payment_id": str(payment["id"]),
            }

            remainder = payments.record_payment(
                conn,
                tenant_id,
                billing_account_id=money_tenant["account_id"],
                amount_cents=5000,
                method="cash",
                idempotency_key=payments.new_idempotency_key(),
                recorded_by_user_id=actor_id,
            )
            payments.auto_allocate(
                conn,
                tenant_id,
                remainder["id"],
                actor_user_id=actor_id,
            )
            conn.commit()
            events = fetch_all(
                conn,
                """
                SELECT event_type, actor_user_id, detail
                FROM invoice_events
                WHERE tenant_id = %s AND invoice_id = %s
                ORDER BY occurred_at,
                    CASE event_type
                        WHEN 'issued' THEN 0
                        WHEN 'part_paid' THEN 1
                        WHEN 'paid' THEN 2
                        ELSE 3
                    END,
                    id
                """,
                (tenant_id, invoice_id),
            )
            assert [row["event_type"] for row in events] == [
                "issued", "part_paid", "paid"
            ]
            assert str(events[2]["actor_user_id"]) == actor_id
            assert events[2]["detail"]["amount_cents"] == 5000
            assert events[2]["detail"]["balance_cents"] == 0
        finally:
            conn.rollback()
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (actor_id,))
            conn.commit()


@requires_db
def test_refund_history_records_partial_and_full_release_amounts(money_tenant):
    """Refund events carry the allocation released by that refund."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        invoice_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=10000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, invoice_id)
        payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=10000,
            method="bank_transfer",
            idempotency_key=payments.new_idempotency_key(),
        )
        payments.auto_allocate(conn, tenant_id, payment["id"])
        conn.commit()

        payments.refund(
            conn,
            tenant_id,
            payment["id"],
            amount_cents=2500,
            reason="First partial refund",
        )
        conn.commit()

        from studiosaas.db import fetch_all, fetch_one

        events = fetch_all(
            conn,
            """
            SELECT event_type, detail
            FROM invoice_events
            WHERE tenant_id = %s AND invoice_id = %s AND event_type = 'refunded'
            ORDER BY occurred_at, id
            """,
            (tenant_id, invoice_id),
        )
        assert events[0]["detail"] == {
            "amount_cents": 2500,
            "balance_cents": 2500,
            "payment_id": str(payment["id"]),
            "reason": "First partial refund",
        }

        payments.refund(
            conn,
            tenant_id,
            payment["id"],
            amount_cents=7500,
            reason="Final refund",
        )
        conn.commit()
        events = fetch_all(
            conn,
            """
            SELECT event_type, detail
            FROM invoice_events
            WHERE tenant_id = %s AND invoice_id = %s AND event_type = 'refunded'
            ORDER BY occurred_at, id
            """,
            (tenant_id, invoice_id),
        )
        assert [event["detail"]["amount_cents"] for event in events] == [2500, 7500]
        assert events[-1]["detail"]["balance_cents"] == 10000
        state = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, invoice_id),
        )
        assert (state["status"], int(state["balance_cents"])) == ("issued", 10000)


@requires_db
def test_refund_history_records_each_invoice_amount_when_refund_spans_allocations(
    money_tenant,
):
    """A cross-invoice refund reports each invoice's actual released amount."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        older_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=4000, tax_bp=0
        )
        newer_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=6000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, older_id)
        billing.issue_invoice(conn, tenant_id, newer_id)
        payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=10000,
            method="bank_transfer",
            idempotency_key=payments.new_idempotency_key(),
        )
        payments.allocate(
            conn,
            tenant_id,
            payment["id"],
            [payments.Allocation(invoice_id=older_id, amount_cents=4000)],
        )
        conn.commit()
        payments.allocate(
            conn,
            tenant_id,
            payment["id"],
            [payments.Allocation(invoice_id=newer_id, amount_cents=6000)],
        )
        conn.commit()

        payments.refund(
            conn,
            tenant_id,
            payment["id"],
            amount_cents=8000,
            reason="Cross-invoice refund",
        )
        conn.commit()

        from studiosaas.db import fetch_all, fetch_one

        refunded = fetch_all(
            conn,
            """
            SELECT invoice_id, detail
            FROM invoice_events
            WHERE tenant_id = %s AND event_type = 'refunded'
            ORDER BY invoice_id
            """,
            (tenant_id,),
        )
        assert {
            str(event["invoice_id"]): event["detail"]["amount_cents"]
            for event in refunded
        } == {newer_id: 6000, older_id: 2000}
        older = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, older_id),
        )
        newer = fetch_one(
            conn,
            "SELECT status, balance_cents FROM invoices WHERE tenant_id = %s AND id = %s",
            (tenant_id, newer_id),
        )
        assert (older["status"], int(older["balance_cents"])) == ("part_paid", 2000)
        assert (newer["status"], int(newer["balance_cents"])) == ("issued", 6000)


@requires_db
def test_refund_history_does_not_fabricate_invoice_amount_for_unallocated_credit(
    money_tenant,
):
    """An account-credit refund has no invoice event for its unallocated part."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        invoice_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=4000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, invoice_id)
        payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=10000,
            method="bank_transfer",
            idempotency_key=payments.new_idempotency_key(),
        )
        payments.auto_allocate(conn, tenant_id, payment["id"])
        conn.commit()

        payments.refund(
            conn,
            tenant_id,
            payment["id"],
            amount_cents=5000,
            reason="Credit refund",
        )
        conn.commit()

        from studiosaas.db import fetch_all

        events = fetch_all(
            conn,
            """
            SELECT detail
            FROM invoice_events
            WHERE tenant_id = %s AND invoice_id = %s AND event_type = 'refunded'
            """,
            (tenant_id, invoice_id),
        )
        assert len(events) == 1
        assert events[0]["detail"]["amount_cents"] == 4000


@requires_db
def test_refund_over_available_amount_has_no_refund_or_history_side_effect(
    money_tenant,
):
    """An invalid refund is rejected before either ledger table is changed."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        invoice_id = _draft_with_line(
            conn, tenant_id, money_tenant["account_id"], cents=1000, tax_bp=0
        )
        billing.issue_invoice(conn, tenant_id, invoice_id)
        payment = payments.record_payment(
            conn,
            tenant_id,
            billing_account_id=money_tenant["account_id"],
            amount_cents=1000,
            method="cash",
            idempotency_key=payments.new_idempotency_key(),
        )
        conn.commit()

        with pytest.raises(payments.PaymentError, match="Refundable amount is 1000 cents"):
            payments.refund(conn, tenant_id, payment["id"], amount_cents=1001)
        conn.rollback()

        from studiosaas.db import fetch_one

        refund_count = fetch_one(
            conn,
            "SELECT count(*) AS n FROM refunds WHERE tenant_id = %s AND payment_id = %s",
            (tenant_id, payment["id"]),
        )
        event_count = fetch_one(
            conn,
            "SELECT count(*) AS n FROM invoice_events WHERE tenant_id = %s AND invoice_id = %s AND event_type = 'refunded'",
            (tenant_id, invoice_id),
        )
        assert int(refund_count["n"]) == 0
        assert int(event_count["n"]) == 0


@requires_db
def test_replaying_a_payment_with_the_same_key_does_not_double_post(money_tenant):
    """A retried request and a redelivered webhook look identical. They must be."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import payments

    tenant_id = money_tenant["tenant_id"]
    key = payments.new_idempotency_key()
    with connect() as conn:
        first = payments.record_payment(
            conn, tenant_id, billing_account_id=money_tenant["account_id"],
            amount_cents=5000, method="bank_transfer", idempotency_key=key,
        )
        conn.commit()
        second = payments.record_payment(
            conn, tenant_id, billing_account_id=money_tenant["account_id"],
            amount_cents=5000, method="bank_transfer", idempotency_key=key,
        )
        conn.commit()

    assert str(first["id"]) == str(second["id"])


@requires_db
def test_a_billing_account_cannot_hold_another_tenants_student(money_tenant):
    """The composite foreign key makes it unrepresentable, not merely unwise."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    other_tenant = str(uuid.uuid4())
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (id, name, slug, status, plan_code)
                VALUES (%s, 'Other', %s, 'active', 'starter')
                """,
                (other_tenant, f"o{other_tenant[:8]}"),
            )
            cur.execute(
                """
                INSERT INTO students (tenant_id, first_name, display_name)
                VALUES (%s, 'Theirs', 'Theirs') RETURNING id
                """,
                (other_tenant,),
            )
            foreign_student = cur.fetchone()["id"]
        conn.commit()

        with pytest.raises(Exception):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing_account_members (tenant_id, billing_account_id, student_id)
                    VALUES (%s, %s, %s)
                    """,
                    (money_tenant["tenant_id"], money_tenant["account_id"], foreign_student),
                )
        conn.rollback()

        with conn.cursor() as cur:
            cur.execute("DELETE FROM tenants WHERE id = %s", (other_tenant,))
        conn.commit()


@requires_db
def test_xero_push_cannot_be_enabled_before_the_gate_is_satisfied(money_tenant):
    """The gate is a CHECK constraint: a script cannot open it either."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        with pytest.raises(Exception) as caught:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO xero_sync_settings (tenant_id, push_enabled) VALUES (%s, true)",
                    (tenant_id,),
                )
        conn.rollback()
        assert "xero_push_requires_preconditions" in str(caught.value)


@requires_db
def test_clearing_account_choice_requires_an_account_code(money_tenant):
    """Choosing the safe option without configuring it is the unsafe option."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    with connect() as conn:
        with pytest.raises(Exception):
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO xero_sync_settings
                        (tenant_id, push_enabled, mapping_confirmed_at, demo_run_completed_at,
                         single_entry_decision, clearing_account_code)
                    VALUES (%s, true, now(), now(), 'clearing_account', '')
                    """,
                    (money_tenant["tenant_id"],),
                )
        conn.rollback()


@requires_db
def test_a_confirmed_pay_period_refuses_silent_corrections(money_tenant):
    """Not merely ignored — refused, with a reason.

    The earlier version of this path declined the write and returned nothing,
    which is safe and invisible at the same time: a re-run of the collector
    after confirmation discarded the correction and told nobody.
    """

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主

    tenant_id = money_tenant["tenant_id"]
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name)
                VALUES (%s, 'x', 'Test Teacher') RETURNING id
                """,
                (f"teacher-{uuid.uuid4()}@example.test",),
            )
            teacher_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO teacher_pay_rates (tenant_id, teacher_user_id, basis, amount_cents, effective_from)
                VALUES (%s, %s, 'per_lesson', 5000, CURRENT_DATE - 30)
                """,
                (tenant_id, teacher_id),
            )
        conn.commit()

        taught_on = date.today() - timedelta(days=1)
        teaching_pay.upsert_session(
            conn, tenant_id, teacher_user_id=teacher_id, occurred_on=taught_on, source="roster"
        )
        period = teaching_pay.open_period(
            conn, tenant_id, teacher_id,
            period_start=taught_on - timedelta(days=7), period_end=taught_on + timedelta(days=7),
        )
        teaching_pay.recalculate_period(conn, tenant_id, period["id"])
        teaching_pay.confirm_period(conn, tenant_id, period["id"], confirmed_by_user_id=teacher_id)
        conn.commit()

        with pytest.raises(teaching_pay.PayError) as caught:
            teaching_pay.upsert_session(
                conn, tenant_id, teacher_user_id=teacher_id, occurred_on=taught_on,
                duration_minutes=90, source="roster",
            )
        conn.rollback()
        assert "adjustment" in str(caught.value).lower()

        with conn.cursor() as cur:
            cur.execute("DELETE FROM users WHERE id = %s", (teacher_id,))
        conn.commit()


@requires_db
def test_a_report_draft_survives_a_student_who_has_lesson_notes(money_tenant):
    """The assembled content has to be storable as jsonb, dates included.

    ``assemble`` returns rows straight from psycopg, which hands back ``date``
    objects; ``json.dumps`` refuses them, and the whole route 500s. Nothing
    about that is visible without a database and without a student who actually
    has notes — an empty studio serialises fine, so the bug hides in exactly the
    tenants that use the feature most.
    """

    import json

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import progress_reports

    tenant_id = money_tenant["tenant_id"]
    student_id = money_tenant["student_id"]
    start, end = date(2026, 7, 1), date(2026, 7, 31)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO attendance_sessions
                    (tenant_id, student_id, class_date, note)
                VALUES (%s, %s, %s, 'Worked on colour mixing.')
                """,
                (tenant_id, student_id, date(2026, 7, 15)),
            )
            cur.execute(
                """
                INSERT INTO daily_roster_entries
                    (tenant_id, student_id, roster_date, status)
                VALUES (%s, %s, %s, 'scheduled')
                """,
                (tenant_id, student_id, date(2026, 7, 15)),
            )
        conn.commit()

        content = progress_reports.assemble(
            conn, tenant_id, student_id, period_start=start, period_end=end
        )
        # The assertion is the round-trip, not the shape: this is the exact call
        # create_draft makes, and it is where the route died.
        json.dumps(content)
        assert content["lessons"][0]["class_date"] == "2026-07-15"

        draft = progress_reports.create_draft(
            conn, tenant_id, student_id, period_start=start, period_end=end
        )
        conn.commit()
        assert draft["status"] == "draft"


# ══════════════════════════════════════════════════════════════════════
# Cancellation policy — who pays, who gets paid, who is owed a make-up
# ══════════════════════════════════════════════════════════════════════
#
# These live with the money invariants rather than in a scheduling file
# because that is what they are. `resolve_absence` is a pure function over a
# policy dict precisely so it can be tested exhaustively here, without a
# database: a wrong answer does not raise, it bills a family for a lesson the
# studio cancelled and nobody notices until they ring up.


def _policy(**overrides):
    from studiosaas.services.scheduling import DEFAULT_POLICY

    return {**DEFAULT_POLICY, **overrides}


def test_a_studio_cancellation_never_costs_the_teacher_their_fee():
    """The studio made the call. Docking the teacher for it loses the teacher."""

    from studiosaas.services import scheduling

    for chargeable in (True, False):
        outcome = scheduling.resolve_absence(
            _policy(studio_cancel_chargeable=chargeable),
            cancelled_by=scheduling.CANCELLED_BY_STUDIO,
            hours_notice=0.0,
        )
        assert outcome["counts_for_pay"] is True


def test_a_studio_cancellation_ignores_notice_entirely():
    """Otherwise a studio closing an hour before could charge the family.

    The studio gave itself whatever notice it liked; measuring it against the
    family's notice window is the wrong question.
    """

    from studiosaas.services import scheduling

    late = scheduling.resolve_absence(
        _policy(), cancelled_by=scheduling.CANCELLED_BY_STUDIO, hours_notice=0.25
    )
    early = scheduling.resolve_absence(
        _policy(), cancelled_by=scheduling.CANCELLED_BY_STUDIO, hours_notice=500.0
    )
    assert late == early
    assert late["chargeable"] is False


def test_a_studio_cancellation_only_owes_a_credit_if_it_charged():
    """A credit for a lesson nobody paid for is a second free lesson."""

    from studiosaas.services import scheduling

    free = scheduling.resolve_absence(
        _policy(studio_cancel_chargeable=False),
        cancelled_by=scheduling.CANCELLED_BY_STUDIO, hours_notice=None,
    )
    charged = scheduling.resolve_absence(
        _policy(studio_cancel_chargeable=True),
        cancelled_by=scheduling.CANCELLED_BY_STUDIO, hours_notice=None,
    )
    assert free["grants_credit"] is False
    assert charged["grants_credit"] is True


def test_notice_given_in_time_charges_nobody_and_pays_nobody():
    from studiosaas.services import scheduling

    outcome = scheduling.resolve_absence(
        _policy(notice_hours=24), cancelled_by=scheduling.CANCELLED_BY_STUDENT,
        hours_notice=25.0,
    )
    assert outcome == {"chargeable": False, "counts_for_pay": False, "grants_credit": True}


def test_the_notice_window_is_inclusive_at_its_boundary():
    """Exactly 24 hours is 24 hours' notice. Off-by-one here is somebody's money."""

    from studiosaas.services import scheduling

    on_the_line = scheduling.resolve_absence(
        _policy(notice_hours=24), cancelled_by=scheduling.CANCELLED_BY_STUDENT,
        hours_notice=24.0,
    )
    a_minute_late = scheduling.resolve_absence(
        _policy(notice_hours=24), cancelled_by=scheduling.CANCELLED_BY_STUDENT,
        hours_notice=23.98,
    )
    assert on_the_line["chargeable"] is False
    assert a_minute_late["chargeable"] is True


def test_a_late_cancellation_never_earns_a_make_up():
    """That is the entire purpose of having a notice window."""

    from studiosaas.services import scheduling

    outcome = scheduling.resolve_absence(
        _policy(notice_hours=24, makeup_credit_on_notice=True),
        cancelled_by=scheduling.CANCELLED_BY_STUDENT, hours_notice=2.0,
    )
    assert outcome["grants_credit"] is False
    assert outcome["chargeable"] is True
    assert outcome["counts_for_pay"] is True


def test_an_unrecorded_notice_time_counts_as_no_notice():
    """A no-show entered the next morning must not become a free lesson.

    None means nobody wrote down when the call came in — the safe reading is
    that it did not come in at all, because the opposite reading turns every
    unrecorded absence into a refund.
    """

    from studiosaas.services import scheduling

    outcome = scheduling.resolve_absence(
        _policy(notice_hours=24), cancelled_by=scheduling.CANCELLED_BY_STUDENT,
        hours_notice=None,
    )
    assert outcome["chargeable"] is True
    assert outcome["grants_credit"] is False


def test_charging_and_paying_are_answered_separately():
    """One boolean for both is the bug lesson_exceptions exists to prevent."""

    from studiosaas.services import scheduling

    outcome = scheduling.resolve_absence(
        _policy(late_absence_chargeable=True, late_absence_pays_teacher=False),
        cancelled_by=scheduling.CANCELLED_BY_STUDENT, hours_notice=1.0,
    )
    assert outcome["chargeable"] is True
    assert outcome["counts_for_pay"] is False


def test_an_absence_must_be_attributed_to_somebody():
    from studiosaas.services import scheduling

    with pytest.raises(scheduling.SchedulingError):
        scheduling.resolve_absence(
            _policy(), cancelled_by="weather", hours_notice=48.0
        )


def test_notice_is_negative_when_the_call_comes_after_the_lesson():
    """A no-show is recorded the next morning more often than not."""

    from datetime import datetime as _dt

    from studiosaas.services import scheduling

    hours = scheduling.hours_of_notice(
        lesson_on=date(2026, 8, 10), lesson_at=time(16, 0),
        decided_at=_dt(2026, 8, 11, 9, 0),
    )
    assert hours < 0
    assert scheduling.resolve_absence(
        _policy(), cancelled_by=scheduling.CANCELLED_BY_STUDENT, hours_notice=hours
    )["chargeable"] is True


@requires_db
def test_occurrences_skip_closures_and_pauses_but_keep_cancellations(money_tenant):
    """Three ways a lesson can not happen, and only one of them is an absence.

    A term closure removes the lesson: nobody decided anything, so it produces
    no row and must not appear in a family's history as "cancelled". A pause
    does the same for a stretch of weeks. A cancellation is a decision, and it
    stays visible with the two money answers attached to it.
    """

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import scheduling

    tenant_id = money_tenant["tenant_id"]
    student_id = money_tenant["student_id"]

    with connect() as conn:
        # Four consecutive Mondays in August 2026: 3rd, 10th, 17th, 24th.
        series = scheduling.create_series(
            conn, tenant_id, student_id=student_id,
            weekday=1, start_time="16:00", duration_minutes=30,
            starts_on=date(2026, 8, 1), ends_on=date(2026, 8, 31),
        )
        conn.commit()
        series_id = str(series["id"])

        window = {"start": date(2026, 8, 1), "end": date(2026, 8, 31)}
        assert [o["on_date"] for o in scheduling.occurrences(conn, tenant_id, **window)] == [
            "2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31",
        ]

        scheduling.set_closure(conn, tenant_id, on_date=date(2026, 8, 10), label="Public holiday")
        conn.commit()
        after_closure = [o["on_date"] for o in scheduling.occurrences(conn, tenant_id, **window)]
        assert "2026-08-10" not in after_closure

        scheduling.cancel_occurrence(
            conn, tenant_id, series_id, on_date=date(2026, 8, 17),
            cancelled_by=scheduling.CANCELLED_BY_STUDENT, hours_notice=1.0,
        )
        conn.commit()
        cancelled = next(
            o for o in scheduling.occurrences(conn, tenant_id, **window)
            if o["on_date"] == "2026-08-17"
        )
        # Still on the calendar, and carrying what was decided about it.
        assert cancelled["exception_kind"] == "cancelled_by_student"
        assert cancelled["chargeable"] is True

        # A family away for the last stretch of the month. The earlier weeks
        # must survive: "pause August" meaning "stop forever" is the failure
        # this window exists to prevent.
        scheduling.set_series_status(
            conn, tenant_id, series_id, status="paused",
            paused_from=date(2026, 8, 20), paused_to=date(2026, 8, 31),
        )
        conn.commit()
        during_pause = [o["on_date"] for o in scheduling.occurrences(conn, tenant_id, **window)]
        assert "2026-08-24" not in during_pause and "2026-08-31" not in during_pause
        assert "2026-08-03" in during_pause and "2026-08-17" in during_pause

        # An indefinite pause has no start date, and swallows everything.
        scheduling.set_series_status(conn, tenant_id, series_id, status="paused")
        conn.commit()
        assert scheduling.occurrences(conn, tenant_id, **window) == []

        # Ending it is the only thing that removes it from the calendar for good.
        scheduling.set_series_status(conn, tenant_id, series_id, status="ended")
        conn.commit()
        assert scheduling.occurrences(conn, tenant_id, **window) == []


@requires_db
def test_a_make_up_credit_cannot_be_spent_twice(money_tenant):
    """Two screens, one credit. Check-then-write lets both through."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import scheduling

    tenant_id = money_tenant["tenant_id"]
    student_id = money_tenant["student_id"]

    with connect() as conn:
        series = scheduling.create_series(
            conn, tenant_id, student_id=student_id,
            weekday=1, start_time="16:00", duration_minutes=30,
            starts_on=date(2026, 9, 1),
        )
        conn.commit()
        outcome = scheduling.cancel_occurrence(
            conn, tenant_id, str(series["id"]), on_date=date(2026, 9, 7),
            cancelled_by=scheduling.CANCELLED_BY_STUDENT, hours_notice=48.0,
        )
        conn.commit()
        assert outcome["grants_credit"] is True
        credit_id = outcome["makeupCreditId"]

        scheduling.consume_credit(conn, tenant_id, credit_id, on_date=date(2026, 9, 12))
        conn.commit()
        with pytest.raises(scheduling.SchedulingError):
            scheduling.consume_credit(conn, tenant_id, credit_id, on_date=date(2026, 9, 19))
        conn.rollback()


@requires_db
def test_an_expired_credit_is_expired_the_moment_the_date_passes(money_tenant):
    """Derived at read time, so no nightly job can leave it stale."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import scheduling

    tenant_id = money_tenant["tenant_id"]
    student_id = money_tenant["student_id"]

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO makeup_credits
                    (tenant_id, student_id, earned_from_date, expires_on)
                VALUES (%s, %s, %s, %s) RETURNING id
                """,
                (tenant_id, student_id, date(2026, 1, 1), date.today() - timedelta(days=1)),
            )
            credit_id = str(cur.fetchone()["id"])
        conn.commit()

        row = next(c for c in scheduling.credits(conn, tenant_id) if str(c["id"]) == credit_id)
        # The stored status is untouched; the answer is still correct.
        assert row["status"] == "available"
        assert row["is_expired"] is True

        with pytest.raises(scheduling.SchedulingError):
            scheduling.consume_credit(conn, tenant_id, credit_id, on_date=date.today())
        conn.rollback()


@requires_db
def test_undoing_a_cancellation_cancels_the_credit_it_granted(money_tenant):
    """Never a delete: a family's balance may not change without a trace."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import scheduling

    tenant_id = money_tenant["tenant_id"]
    student_id = money_tenant["student_id"]

    with connect() as conn:
        series = scheduling.create_series(
            conn, tenant_id, student_id=student_id,
            weekday=1, start_time="16:00", duration_minutes=30,
            starts_on=date(2026, 10, 1),
        )
        conn.commit()
        outcome = scheduling.cancel_occurrence(
            conn, tenant_id, str(series["id"]), on_date=date(2026, 10, 5),
            cancelled_by=scheduling.CANCELLED_BY_STUDENT, hours_notice=48.0,
        )
        conn.commit()

        scheduling.undo_occurrence(conn, tenant_id, outcome["exceptionId"])
        conn.commit()

        credit = next(
            c for c in scheduling.credits(conn, tenant_id, include_spent=True)
            if str(c["id"]) == outcome["makeupCreditId"]
        )
        assert credit["status"] == "cancelled"


@requires_db
def test_a_teacher_cannot_be_booked_into_two_lessons_at_once(money_tenant):
    """Overlap, not equality — 4:15 and 4:30 collide for a 30-minute lesson."""

    from _cms_sources import owner_connection as connect  # 夹具造世界用属主
    from studiosaas.services import scheduling

    tenant_id = money_tenant["tenant_id"]
    student_id = money_tenant["student_id"]

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name)
                VALUES (%s, 'x', 'Test Teacher') RETURNING id
                """,
                (f"teacher-{uuid.uuid4()}@example.invalid",),
            )
            teacher_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO students (id, tenant_id, first_name, display_name)
                VALUES (gen_random_uuid(), %s, 'Second', 'Second Student') RETURNING id
                """,
                (tenant_id,),
            )
            other_student = str(cur.fetchone()["id"])
        conn.commit()

        scheduling.create_series(
            conn, tenant_id, student_id=student_id, teacher_user_id=teacher_id,
            weekday=2, start_time="16:15", duration_minutes=30,
            starts_on=date(2026, 11, 1),
        )
        conn.commit()

        with pytest.raises(scheduling.SchedulingError, match="already has"):
            scheduling.create_series(
                conn, tenant_id, student_id=other_student, teacher_user_id=teacher_id,
                weekday=2, start_time="16:30", duration_minutes=30,
                starts_on=date(2026, 11, 1),
            )
        conn.rollback()
