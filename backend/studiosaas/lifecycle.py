"""Canonical lifecycle rules for tenants, subscriptions, and registrations.

Keeping these transitions outside the HTTP routes prevents the UI, API, and
background jobs from inventing incompatible status combinations.
"""

from __future__ import annotations


TENANT_TRANSITIONS: dict[str, frozenset[str]] = {
    "lead": frozenset({"trial", "cancelled"}),
    "trial": frozenset({"onboarding", "active", "cancelled"}),
    "onboarding": frozenset({"trial", "active", "paused", "cancelled"}),
    "active": frozenset({"past_due", "paused", "cancelled"}),
    "past_due": frozenset({"active", "paused", "cancelled"}),
    "paused": frozenset({"active", "cancelled"}),
    "cancelled": frozenset({"paused"}),
    # Archive/restore and permanent deletion have dedicated, audited services.
    "archived": frozenset(),
    "deleted": frozenset(),
}

REGISTRATION_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending": frozenset({
        "contacted", "trial_booked", "waiting", "approved", "converted",
        "rejected", "duplicate", "lost", "archived",
    }),
    "contacted": frozenset({
        "pending", "trial_booked", "waiting", "approved", "converted",
        "rejected", "lost", "archived",
    }),
    "trial_booked": frozenset({
        "contacted", "waiting", "approved", "converted", "lost", "archived",
    }),
    "waiting": frozenset({
        "contacted", "trial_booked", "approved", "converted", "lost", "archived",
    }),
    "approved": frozenset({"converted", "archived"}),
    "converted": frozenset({"archived"}),
    "rejected": frozenset({"pending", "contacted", "archived"}),
    "duplicate": frozenset({"pending", "archived"}),
    "lost": frozenset({"pending", "contacted", "archived"}),
    "archived": frozenset({"pending"}),
}

TENANT_SUBSCRIPTION_STATUSES: dict[str, frozenset[str]] = {
    "lead": frozenset({"trialing", "paused", "cancelled"}),
    "trial": frozenset({"trialing"}),
    "onboarding": frozenset({"trialing", "active"}),
    "active": frozenset({"active"}),
    "past_due": frozenset({"past_due"}),
    "paused": frozenset({"paused"}),
    "cancelled": frozenset({"cancelled"}),
    "archived": frozenset({"archived"}),
    "deleted": frozenset({"archived"}),
}


def validate_tenant_transition(current: str, target: str) -> None:
    """Raise when a tenant lifecycle transition is not an allowed action."""

    if current == target:
        return
    allowed = TENANT_TRANSITIONS.get(current)
    if allowed is None or target not in allowed:
        choices = ", ".join(sorted(allowed or ())) or "none"
        raise ValueError(
            f"Tenant cannot move from '{current}' to '{target}'. Allowed next states: {choices}."
        )


def validate_registration_transition(current: str, target: str) -> None:
    """Raise when a registration jumps outside the follow-up state machine."""

    if current == target:
        return
    allowed = REGISTRATION_TRANSITIONS.get(current)
    if allowed is None or target not in allowed:
        choices = ", ".join(sorted(allowed or ())) or "none"
        raise ValueError(
            f"Registration cannot move from '{current}' to '{target}'. Allowed next states: {choices}."
        )


def validate_tenant_subscription_pair(tenant_status: str, subscription_status: str) -> None:
    """Reject commercial states that cannot be true at the same time."""

    allowed = TENANT_SUBSCRIPTION_STATUSES.get(tenant_status)
    if allowed is None or subscription_status not in allowed:
        choices = ", ".join(sorted(allowed or ())) or "none"
        raise ValueError(
            f"Subscription status '{subscription_status}' is incompatible with tenant status "
            f"'{tenant_status}'. Allowed subscription states: {choices}."
        )


def canonical_subscription_status(tenant_status: str, *, current: str = "") -> str:
    """Return the safest subscription state for a tenant lifecycle state."""

    allowed = TENANT_SUBSCRIPTION_STATUSES.get(tenant_status)
    if not allowed:
        raise ValueError(f"Unknown tenant lifecycle state: {tenant_status}.")
    if current in allowed:
        return current
    preference = {
        "lead": "trialing",
        "trial": "trialing",
        "onboarding": "trialing",
        "active": "active",
        "past_due": "past_due",
        "paused": "paused",
        "cancelled": "cancelled",
        "archived": "archived",
        "deleted": "archived",
    }
    return preference[tenant_status]


# ── subscription dates ──────────────────────────────────────────────────────
#
# The four dates were free text with no relationship to each other or to the
# status beside them. A subscription could be stored as trialing with no trial
# end, as cancelled with no cancellation date, or with a cancellation that
# falls before the period it cancels. None of those describe anything that
# could happen, and each of them would be read later as if it did.
#
# Ordered as they occur. The pair rules below are all "A must not be after B".
SUBSCRIPTION_DATE_ORDER = ("starts_at", "trial_ends_at", "current_period_ends_at", "ends_at")

DATE_LABELS = {
    "starts_at": "Subscription start",
    "trial_ends_at": "Trial end",
    "current_period_ends_at": "Current period end",
    "ends_at": "Cancellation / expiry",
}

# Statuses that are meaningless without a particular date.
DATE_REQUIRED_BY_STATUS = {
    "trialing": ("trial_ends_at", "A trialing subscription needs a trial end date."),
    "cancelled": ("ends_at", "A cancelled subscription needs a cancellation date."),
}


def _as_date(value):
    """A `date` from whatever the caller has — string, datetime, date, None."""

    if value in (None, ""):
        return None
    if hasattr(value, "date") and not isinstance(value, str):
        return value.date() if hasattr(value, "hour") else value
    text = str(value)[:10]
    try:
        year, month, day = (int(part) for part in text.split("-"))
    except ValueError:
        return None
    import datetime

    try:
        return datetime.date(year, month, day)
    except ValueError:
        return None


def validate_subscription_dates(dates: dict, subscription_status: str = "") -> None:
    """Raise when the four dates cannot describe one real subscription.

    `dates` maps the column names above to anything `_as_date` understands;
    a key that is missing or unparseable is simply not checked, because a
    caller that did not mention a date is not asserting anything about it.
    """

    parsed = {name: _as_date(dates.get(name)) for name in SUBSCRIPTION_DATE_ORDER}

    # Every date must fall on or after every date that precedes it.
    for index, earlier in enumerate(SUBSCRIPTION_DATE_ORDER):
        for later in SUBSCRIPTION_DATE_ORDER[index + 1:]:
            first, second = parsed[earlier], parsed[later]
            if first and second and second < first:
                raise ValueError(
                    f"{DATE_LABELS[later]} ({second}) is before "
                    f"{DATE_LABELS[earlier].lower()} ({first})."
                )

    required = DATE_REQUIRED_BY_STATUS.get(subscription_status)
    if required and not parsed.get(required[0]):
        raise ValueError(required[1])


# A date that has passed is only worth flagging when the thing it ends is
# supposed to still be running. A start date in the past is the ordinary case
# — it is what "this subscription has begun" looks like — and colouring it as
# overdue was telling operators that every healthy studio had a problem.
SUBSCRIPTION_DEADLINES = frozenset({"trial_ends_at", "current_period_ends_at", "ends_at"})
