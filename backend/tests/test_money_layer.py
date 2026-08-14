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

    from studiosaas.db import connect
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

    from studiosaas.db import connect
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

    from studiosaas.db import connect
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

    from studiosaas.db import connect
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

    from studiosaas.db import connect
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

    from studiosaas.db import connect
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
