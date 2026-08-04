"""What the subscription dates mean once they have passed.

Until now, nothing. The four dates on a subscription were a memo: a trial
could end and the studio kept every feature, a billing period could lapse and
nothing moved, and `ends_at` — the cancellation date — could go by without the
subscription being cancelled. There was no scheduled job, no expiry check, and
no code path anywhere that read a date and compared it to today. For a product
that is sold by subscription, that is the centre of the thing being unenforced.

This module is the smallest honest version of enforcement.

**It reports. It does not cut anybody off.** A studio losing access because a
job ran at 3am is a support incident and a trust problem, and the right first
step is that an operator can see, on one screen, which subscriptions have
passed a date and what the system believes should happen. Applying a
transition is a separate, explicit call.

**It obeys the existing state machine.** `lifecycle.TENANT_TRANSITIONS` and
`TENANT_SUBSCRIPTION_STATUSES` already encode which moves are legal, and this
does not get to invent new ones. That has a consequence worth stating: a
lapsed trial cannot be moved to `past_due`, because `trial → past_due` is not
an allowed tenant transition. So a lapsed trial is reported and left for a
person, which is also the right answer commercially — it is a sales decision,
not a billing one.

**It is idempotent.** Findings are computed from the row's current state, so a
row that has already been settled produces nothing on the next run.
"""

from __future__ import annotations

import datetime
from typing import Any

from ..lifecycle import (
    TENANT_SUBSCRIPTION_STATUSES,
    TENANT_TRANSITIONS,
    _as_date,
)

# Findings that carry a transition the system is willing to perform on its
# own, versus findings that exist so a person decides. The difference is not
# how serious they are — a lapsed trial may matter more — it is whether there
# is exactly one defensible next state.
ACTIONABLE = "actionable"
REVIEW = "review"
DATA = "data"


def _finding(kind: str, category: str, summary: str, *, tenant=None,
             days: int | None = None, target: tuple[str, str] | None = None) -> dict[str, Any]:
    return {
        "kind": kind,
        "category": category,
        "summary": summary,
        "tenant_id": str(tenant["tenant_id"]) if tenant and tenant.get("tenant_id") else None,
        "tenant_name": (tenant or {}).get("name") or "",
        "slug": (tenant or {}).get("slug") or "",
        "days": days,
        "tenant_status": (tenant or {}).get("tenant_status") or "",
        "subscription_status": (tenant or {}).get("subscription_status") or "",
        # (tenant status, subscription status) this row should move to, or None
        # when the answer is a person's to give.
        "target": list(target) if target else None,
    }


def _days_past(value, today: datetime.date) -> int | None:
    parsed = _as_date(value)
    if parsed is None:
        return None
    return (today - parsed).days


def _transition_allowed(current_tenant: str, target_tenant: str, target_subscription: str) -> bool:
    """Both halves of the move have to be legal, or it is not offered."""

    if current_tenant == target_tenant:
        return target_subscription in TENANT_SUBSCRIPTION_STATUSES.get(target_tenant, frozenset())
    allowed = TENANT_TRANSITIONS.get(current_tenant, frozenset())
    if target_tenant not in allowed:
        return False
    return target_subscription in TENANT_SUBSCRIPTION_STATUSES.get(target_tenant, frozenset())


# Rows in these states are already at rest; a date that has passed says nothing
# new about them.
SETTLED = frozenset({"cancelled", "archived", "deleted"})


def findings_for(row: dict[str, Any], today: datetime.date) -> list[dict[str, Any]]:
    """Everything today says about one subscription row."""

    tenant_status = str(row.get("tenant_status") or "")
    subscription_status = str(row.get("subscription_status") or "")
    if tenant_status in SETTLED:
        return []

    found: list[dict[str, Any]] = []

    # 1 · The cancellation date is the strongest signal: somebody already
    #     decided this subscription ends, and the date has come.
    ended = _days_past(row.get("ends_at"), today)
    if ended is not None and ended >= 0 and subscription_status not in SETTLED:
        target = ("cancelled", "cancelled")
        found.append(_finding(
            "ended",
            ACTIONABLE if _transition_allowed(tenant_status, *target) else REVIEW,
            "The cancellation date has passed and the subscription is still open.",
            tenant=row, days=ended,
            target=target if _transition_allowed(tenant_status, *target) else None,
        ))
        return found      # nothing below adds anything once it has ended

    # 2 · A billing period that lapsed. `active → past_due` is a legal move and
    #     has exactly one meaning, so it is the one thing offered for apply.
    if subscription_status == "active":
        lapsed = _days_past(row.get("current_period_ends_at"), today)
        if lapsed is not None and lapsed > 0:
            target = ("past_due", "past_due")
            found.append(_finding(
                "period_lapsed",
                ACTIONABLE if _transition_allowed(tenant_status, *target) else REVIEW,
                "The billing period ended and the subscription is still marked active.",
                tenant=row, days=lapsed,
                target=target if _transition_allowed(tenant_status, *target) else None,
            ))

    # 3 · A trial that ran out. Deliberately NOT actionable: `trial → past_due`
    #     is not a legal transition, and the real question — did they buy? — is
    #     a person's to answer.
    if subscription_status == "trialing":
        lapsed = _days_past(row.get("trial_ends_at"), today)
        if lapsed is not None and lapsed > 0:
            found.append(_finding(
                "trial_lapsed", REVIEW,
                "The trial ended. Convert the studio, extend the trial, or close it.",
                tenant=row, days=lapsed,
            ))
        elif row.get("trial_ends_at") in (None, ""):
            found.append(_finding(
                "trial_without_end", DATA,
                "Marked as trialing with no trial end date, so nothing can tell when it lapses.",
                tenant=row,
            ))

    return found


def settlement_report(rows: list[dict[str, Any]], today: datetime.date | None = None) -> dict[str, Any]:
    """The whole picture, ordered by how overdue each row is."""

    today = today or datetime.date.today()
    findings: list[dict[str, Any]] = []
    for row in rows:
        findings.extend(findings_for(row, today))
    findings.sort(key=lambda f: (-(f["days"] or 0), f["tenant_name"]))
    return {
        "as_of": today.isoformat(),
        "findings": findings,
        "counts": {
            category: sum(1 for f in findings if f["category"] == category)
            for category in (ACTIONABLE, REVIEW, DATA)
        },
    }


SETTLEMENT_QUERY = """
    SELECT t.id AS tenant_id, t.name, t.slug, t.status AS tenant_status,
           s.status AS subscription_status, s.starts_at, s.ends_at,
           s.trial_ends_at, s.current_period_ends_at
    FROM subscriptions s
    JOIN tenants t ON t.id = s.tenant_id
    WHERE t.status NOT IN ('archived', 'deleted')
      AND COALESCE(t.settings->>'test_fixture', 'false') <> 'true'
"""
