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
