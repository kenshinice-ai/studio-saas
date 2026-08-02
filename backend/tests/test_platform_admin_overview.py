"""The overview counters are filter controls, and they must stay honest.

Two things are easy to break here and neither shows up as an error.

The first is the definition. Most of these counters are defined by the
SUBSCRIPTION status (`subscriptions.status = 'active'`), while the Status
select in the tenants toolbar filters the TENANT status (`tenants.status`).
The two share several of the same words — active, past_due, trial — so wiring
a counter to that select looks right, runs fine, and shows a different number
of rows than the number printed on the card. Locally, "Paid Tenants 3" would
have listed 5.

The second is the language. New UI strings written straight into the page have
shipped untranslated three times in this project, because nothing fails when a
string is missing from the dictionary — the Chinese console just renders that
one label in English.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPER_ADMIN = PROJECT_ROOT / "super-admin.html"
I18N = PROJECT_ROOT / "backend/frontend/assets/admin-i18n.js"

# Every counter that names a set of tenants, and the field its predicate must
# read to agree with /v1/admin/usage.
SUBSCRIPTION_SCOPED = ("paid", "trial", "past_due", "trial_ending")
TENANT_SCOPED = ("all", "onboarding", "new_30d")


def _metric_block(metric: str) -> str:
    """The METRIC_FILTERS entry for one metric, up to the next entry."""

    html = SUPER_ADMIN.read_text(encoding="utf-8")
    start = html.index(f"      {metric}:")
    rest = html[start + 1:]
    end = re.search(r"\n      [a-z_]+: +\{|\n    \};", rest)
    return rest[: end.start()] if end else rest


def test_every_actionable_counter_is_a_button() -> None:
    """A div with a click handler is not reachable by keyboard."""

    html = SUPER_ADMIN.read_text(encoding="utf-8")
    for metric in SUBSCRIPTION_SCOPED + TENANT_SCOPED:
        assert f'<button type="button" class="stat-card' in html
        assert f'data-metric="{metric}"' in html, f"{metric} counter is missing"
        marker = html.index(f'data-metric="{metric}"')
        opening = html.rindex("<", 0, marker)
        assert html[opening:marker].startswith("<button"), (
            f"the {metric} counter is not a <button>, so it is not keyboard-reachable"
        )


def test_mrr_is_not_a_filter() -> None:
    """A currency total names no set of rows, so a click has nothing to show."""

    html = SUPER_ADMIN.read_text(encoding="utf-8")
    marker = html.index('id="mrrCount"')
    card_start = html.rindex('class="stat-card', 0, marker)
    opening = html.rindex("<", 0, card_start)
    assert html[opening:card_start].startswith("<div"), (
        "MRR became a filter button; it totals money, not tenants"
    )


def test_subscription_scoped_counters_do_not_read_the_tenant_status() -> None:
    """The trap: tenants.status and subscriptions.status share their vocabulary."""

    for metric in SUBSCRIPTION_SCOPED:
        block = _metric_block(metric)
        assert "t.subscription_status" in block, (
            f"{metric} mirrors a subscriptions.status count in /v1/admin/usage, "
            "so its predicate must read t.subscription_status"
        )


def test_lifecycle_counters_exclude_archived_and_deleted() -> None:
    """/v1/admin/usage counts `status NOT IN ('archived', 'deleted')`."""

    for metric in ("all", "paid", "trial", "past_due"):
        block = _metric_block(metric)
        assert "'archived', 'deleted'" in block, (
            f"{metric} would count archived or deleted tenants the server does not"
        )


def test_new_ui_strings_are_translated() -> None:
    """Every string added for this surface has a Chinese counterpart."""

    dictionary = I18N.read_text(encoding="utf-8")
    for phrase in (
        "Filtering",
        "From overview",
        "Remove this filter",
        "Filter by action, tenant, or resource...",
        "No events match this filter.",
    ):
        assert f"'{phrase}'" in dictionary, f"{phrase!r} is missing from admin-i18n.js"


def test_dynamic_labels_have_translation_rules() -> None:
    """`Page 1 of 7` and `7 of 100 events` carry numbers, so they need patterns."""

    dictionary = I18N.read_text(encoding="utf-8")
    assert r"^Page (\d+) of (\d+)$" in dictionary
    assert r"^(\d+) of (\d+) events$" in dictionary


def test_labels_rewritten_by_script_are_re_localised() -> None:
    """A label set after load is past the dictionary pass that ran at load."""

    html = SUPER_ADMIN.read_text(encoding="utf-8")
    assert "const relabel = (el, value) =>" in html
    for label in ("tenantPageLabel", "auditPageLabel", "auditCountLabel", "metricFilterLabel"):
        assert f"relabel($('{label}')" in html, (
            f"{label} is written directly and will stay in English after a re-render"
        )


def test_audit_log_is_paginated() -> None:
    """The endpoint returns 100 rows; the table must not render all of them."""

    html = SUPER_ADMIN.read_text(encoding="utf-8")
    assert "const auditPageSize = 15;" in html
    assert 'id="auditPrevBtn"' in html and 'id="auditNextBtn"' in html
    assert 'id="auditSearch"' in html
    assert "auditPage * auditPageSize" in html


def test_the_duplicated_attention_card_is_gone() -> None:
    """It listed the same three metrics as the counters directly above it."""

    html = SUPER_ADMIN.read_text(encoding="utf-8")
    assert "commercialAttention" not in html
    assert "renderCommercialAttention" not in html
