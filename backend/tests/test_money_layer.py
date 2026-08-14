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
from datetime import date, timedelta
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
    )
    assert not status.can_enable
    assert status.blockers() == [
        "addon_not_active", "not_connected", "mapping_not_confirmed",
        "demo_run_not_completed", "single_entry_not_answered",
    ]

    ready = xero.GateStatus(
        entitled=True, connected=True, mapping_confirmed=True,
        demo_run_completed=True, single_entry_answered=True, push_enabled=False,
    )
    assert ready.can_enable and ready.blockers() == []


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
        from studiosaas.db import connect

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

    from studiosaas.db import connect

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

    from studiosaas.db import connect

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
def test_issued_invoice_lines_cannot_be_changed(money_tenant):
    from studiosaas.db import connect

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

    from studiosaas.db import connect

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
    from studiosaas.db import connect
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

    from studiosaas.db import connect
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
def test_replaying_a_payment_with_the_same_key_does_not_double_post(money_tenant):
    """A retried request and a redelivered webhook look identical. They must be."""

    from studiosaas.db import connect
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

    from studiosaas.db import connect

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

    from studiosaas.db import connect

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

    from studiosaas.db import connect

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

    from studiosaas.db import connect

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
