"""Subscriptions: the save that never saved, and the dates that meant nothing.

Three defects, one of them twenty-five days old and none of them findable from
the code alone.

**Every edit of an existing studio returned 500 and wrote nothing.** In
`_ensure_studio_admin_account`, `elif password:` consumed the has-a-password
case, so the `else` below it was reachable only when the password was empty —
and it opened with `if not password: raise`. The condition was always true, the
raise always fired, and the `UPDATE` beneath it was unreachable code. Live from
2026-07-10 to 2026-08-04.

It failed safe by accident: the raise happens before the subscription upsert
and before the commit, so the transaction rolled back whole. Twenty-five days
of saves that showed an error and changed nothing — which is also why the
date-clearing defect fixed in v8.2.29 never destroyed production data. Two bugs
cancelling out is not a safety property, so both are asserted here.

**A business rule arrived as "Internal Server Error".** The `try/except
ValueError` around the payload did not extend to the work inside the
transaction, so a fixable mistake reached the operator as a fault with no
information.

**The four subscription dates meant nothing.** No code anywhere compared one to
today. A trial could end, a billing period could lapse and a cancellation date
could pass with the studio keeping every feature and the console showing green.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pytest

from studiosaas.lifecycle import (
    TENANT_SUBSCRIPTION_STATUSES,
    TENANT_TRANSITIONS,
    validate_subscription_dates,
)
from studiosaas.services.subscription_settlement import (
    ACTIONABLE,
    DATA,
    REVIEW,
    findings_for,
    settlement_report,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
API = REPOSITORY_ROOT / "backend/studiosaas/api_v1.py"
CONSOLE = REPOSITORY_ROOT / "super-admin.html"


def console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def console_script() -> str:
    """Only the JavaScript that actually runs.

    A scripted edit once left a replacement above `<!DOCTYPE html>` while the
    function it replaced kept running, and the test passed because the string
    was somewhere in the file. Reading the script rather than the file is what
    makes these assertions about behaviour.
    """

    import re

    return "\n".join(re.findall(r"<script>(.*?)</script>", CONSOLE.read_text(encoding="utf-8"), re.S))
TODAY = datetime.date(2026, 8, 4)


# ── the save that never saved ───────────────────────────────────────────────

def test_no_password_updates_the_login_instead_of_raising() -> None:
    """The branch that always raised, asserted at the source.

    A behavioural test needs a database; what has to be true regardless is
    that the unreachable `UPDATE` is reachable and the raise that guarded it
    is gone from that branch.
    """

    source = API.read_text(encoding="utf-8")
    start = source.index("def _ensure_studio_admin_account(")
    end = source.index("\ndef ", start + 1)
    body = source[start:end]
    existing = body[body.index("            else:"):body.index("        if not user_id:")]
    assert "A password is required when creating a Studio Admin account." not in existing, (
        "the always-true raise is back in the has-an-account branch"
    )
    assert "UPDATE users" in existing and "password_hash" not in existing, (
        "with no new password this branch must update the name and address only"
    )


def test_a_new_login_still_demands_a_credential() -> None:
    """The other half: `hash("")` produced an account nobody can sign in to.

    `/auth/login` refuses an empty password before it verifies anything, so it
    was never a way in — it was a row that looks like an account and is not
    one, which the onboarding checklist then ticked as configured.
    """

    source = API.read_text(encoding="utf-8")
    creation = source[source.index("        if not user_id:"):source.index("INSERT INTO memberships")]
    assert "Set a password for the Studio Admin login" in creation


def test_a_business_rule_does_not_arrive_as_a_fault() -> None:
    source = API.read_text(encoding="utf-8")
    patch = source[source.index("def mutate_tenant("):source.index("def archive_tenant_route(")]
    assert "_ensure_studio_admin_account(conn, tenant_id, data[\"studio_admin\"])" in patch
    # Wrapped, rolled back, and answered as a 400 carrying its own sentence.
    admin_call = patch[patch.index("_ensure_studio_admin_account"):]
    assert "except ValueError as exc:" in admin_call[:400]
    assert "conn.rollback()" in admin_call[:400]


def test_a_five_hundred_can_be_found_in_the_log() -> None:
    """"Internal Server Error" leaves the operator with nothing to report."""

    errors = (REPOSITORY_ROOT / "backend/studiosaas/errors.py").read_text(encoding="utf-8")
    assert "secrets.token_hex" in errors
    assert "Quote reference" in errors


# ── date rules ──────────────────────────────────────────────────────────────

VALID = {
    "starts_at": "2026-08-01",
    "trial_ends_at": "2026-08-15",
    "current_period_ends_at": "2026-09-01",
    "ends_at": "2026-12-01",
}


def test_a_coherent_subscription_passes() -> None:
    validate_subscription_dates(VALID, "active")


@pytest.mark.parametrize(
    ("override", "fragment"),
    [
        ({"trial_ends_at": "2026-07-01"}, "before subscription start"),
        ({"current_period_ends_at": "2026-08-10"}, "before trial end"),
        # The owner's screenshot: a cancellation dated before the period it
        # cancels. Checking each date against the start alone let it through.
        ({"ends_at": "2026-08-20"}, "before current period end"),
    ],
)
def test_a_date_out_of_order_is_refused(override: dict, fragment: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        validate_subscription_dates({**VALID, **override})


@pytest.mark.parametrize(
    ("status", "missing"),
    [("trialing", "trial_ends_at"), ("cancelled", "ends_at")],
)
def test_a_status_that_names_a_date_must_have_it(status: str, missing: str) -> None:
    dates = {**VALID, missing: None}
    with pytest.raises(ValueError):
        validate_subscription_dates(dates, status)


def test_an_unmentioned_date_asserts_nothing() -> None:
    """A caller that did not send a date is not making a claim about it."""

    validate_subscription_dates({"starts_at": "2026-08-01"}, "active")
    validate_subscription_dates({}, "")


def test_both_write_paths_validate() -> None:
    source = API.read_text(encoding="utf-8")
    # Once as the import, once in create, once in update.
    assert source.count("validate_subscription_dates(") == 2, (
        "create and update must both validate, not just one of them"
    )
    create = source[source.index("def create_tenant("):source.index("def mutate_tenant(")]
    update = source[source.index("def mutate_tenant("):source.index("def archive_tenant_route(")]
    assert "validate_subscription_dates(" in create
    assert "validate_subscription_dates(" in update


# ── settlement ──────────────────────────────────────────────────────────────

def _row(**overrides):
    base = dict(tenant_id="t", name="A Studio", slug="a",
                tenant_status="active", subscription_status="active")
    return {**base, **overrides}


def test_a_healthy_subscription_produces_nothing() -> None:
    assert findings_for(_row(current_period_ends_at="2026-12-01"), TODAY) == []


def test_a_lapsed_period_is_offered_for_apply() -> None:
    found = findings_for(_row(current_period_ends_at="2026-07-01"), TODAY)
    assert [f["kind"] for f in found] == ["period_lapsed"]
    assert found[0]["category"] == ACTIONABLE
    assert found[0]["target"] == ["past_due", "past_due"]
    assert found[0]["days"] == 34


def test_a_lapsed_trial_is_never_applied_automatically() -> None:
    """`trial -> past_due` is not a legal transition, and "did they buy?" is a
    commercial question rather than a scheduling one. Both reasons point the
    same way, so the settlement reports it and stops."""

    found = findings_for(
        _row(tenant_status="trial", subscription_status="trialing",
             trial_ends_at="2026-07-20"), TODAY)
    assert [f["kind"] for f in found] == ["trial_lapsed"]
    assert found[0]["category"] == REVIEW
    assert found[0]["target"] is None
    assert "past_due" not in TENANT_TRANSITIONS["trial"], (
        "the matrix changed; revisit whether a lapsed trial can now be applied"
    )


def test_a_passed_cancellation_date_supersedes_everything_else() -> None:
    found = findings_for(
        _row(ends_at="2026-08-01", current_period_ends_at="2026-01-01"), TODAY)
    assert [f["kind"] for f in found] == ["ended"]
    assert found[0]["target"] == ["cancelled", "cancelled"]


def test_a_trial_with_no_end_date_is_a_data_finding() -> None:
    found = findings_for(
        _row(tenant_status="trial", subscription_status="trialing", trial_ends_at=None), TODAY)
    assert [f["category"] for f in found] == [DATA]


def test_rows_already_at_rest_are_left_alone() -> None:
    for status in ("cancelled", "archived", "deleted"):
        assert findings_for(_row(tenant_status=status, ends_at="2020-01-01"), TODAY) == []


def test_the_settlement_is_idempotent() -> None:
    """Findings come from current state, so a settled row yields none."""

    before = _row(current_period_ends_at="2026-07-01")
    assert findings_for(before, TODAY)
    after = {**before, "tenant_status": "past_due", "subscription_status": "past_due"}
    assert findings_for(after, TODAY) == []


def test_every_offered_transition_is_legal() -> None:
    """The settlement does not get to invent moves the state machine forbids."""

    rows = [
        _row(tenant_id="1", current_period_ends_at="2026-07-01"),
        _row(tenant_id="2", ends_at="2026-08-01"),
        _row(tenant_id="3", tenant_status="trial", subscription_status="trialing",
             trial_ends_at="2026-07-01"),
        _row(tenant_id="4", tenant_status="paused", subscription_status="paused",
             ends_at="2026-07-01"),
    ]
    for finding in settlement_report(rows, TODAY)["findings"]:
        if not finding["target"]:
            continue
        tenant_target, subscription_target = finding["target"]
        current = finding["tenant_status"]
        assert current == tenant_target or tenant_target in TENANT_TRANSITIONS[current], (
            f"{current} → {tenant_target} is not an allowed tenant transition"
        )
        assert subscription_target in TENANT_SUBSCRIPTION_STATUSES[tenant_target]


def test_applying_is_the_argument_you_have_to_make(client) -> None:
    """The endpoint rehearses unless explicitly told otherwise."""

    source = API.read_text(encoding="utf-8")
    route = source[source.index("def apply_subscription_settlement("):
                   source.index("def update_tenant_status(")]
    assert 'payload.get("apply") is True' in route, "applying must be opt-in"
    assert "action=\"subscription.settled\"" in route, "an automatic change must be audited"


def test_the_console_shows_what_the_dates_say() -> None:
    """A count nobody sees until they open a menu is a count nobody sees."""

    source = console_script()
    assert "settlementCount" in console()  # the card is markup
    assert "function openSettlement(" in source
    assert "/admin/subscriptions/settlement" in source


# ── the reading of a date ───────────────────────────────────────────────────

def test_only_a_deadline_can_be_overdue() -> None:
    """A subscription start in the past is what "this has begun" looks like.

    Marking it red said every healthy studio needed attention, on three
    different screens.
    """

    source = console_script()
    assert "appendDateRow(item, 'Start', t.starts_at, { deadline: false })" in source
    assert "function dateRelativeBadge(days, deadline)" in source
    assert "'days overdue'" in source and "'days ago'" in source


def test_the_client_checks_every_pair_not_just_the_start() -> None:
    source = console_script()
    assert "SUBSCRIPTION_DATE_FIELDS" in source
    assert "SUBSCRIPTION_DATE_FIELDS.slice(index + 1)" in source


def test_the_validation_message_is_built_from_translatable_parts() -> None:
    """An interpolated "Trial end is before subscription start." matches
    nothing in the dictionary; label + "is before" + label composes in both
    languages."""

    source = console_script()
    assert "problems.push([laterLabel, 'is before', earlierLabel])" in source
    dictionary = (REPOSITORY_ROOT / "backend/frontend/assets/admin-i18n.js").read_text(encoding="utf-8")
    for entry in ("['is before',", "['Subscription start',", "['Trial end',",
                  "['Current period end',", "['days overdue',", "['Start',"):
        assert entry in dictionary, f"admin-i18n.js is missing {entry}"
