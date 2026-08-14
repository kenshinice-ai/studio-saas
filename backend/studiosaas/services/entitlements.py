"""Which capabilities a tenant is entitled to, resolved in one place.

Two shapes of entitlement exist and they are stored separately on purpose:

* **bundled by plan** — ``plans.features``, shared by every tenant on that tier;
* **bought per tenant** — ``tenant_addons``, available on any tier.

Keeping the second out of ``plans.features`` is what makes "available on any
tier" mean what it says. Plans are shared rows: granting one studio the Xero
connection by editing its plan would either grant it to every other studio on
that tier, or force the studio onto a tier it did not want. The union is
computed here and nowhere else, so there is a single answer to "can this tenant
do this" and a single place to change how it is reached.

Standalone deployments answer yes to everything. There is no platform to bill
and no upsell to protect — the customer bought the software.

One rule governs every gate in this module, and it is the reason the resolver
returns a *reason* rather than a bare boolean: **losing an entitlement closes
the door to new work, never to existing records.** A lapsed Xero add-on stops
new pushes and leaves the connection, the id mappings, the error queue and the
CSV export exactly where they were. An invoice is a legal document, not a quota
resource, so no entitlement check may ever stand between a studio and its own
financial history.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable

from ..config import is_standalone
from ..db import fetch_all, fetch_one


# ── the catalogue ────────────────────────────────────────────────────────
#
# Keys are the vocabulary the rest of the codebase gates on. Adding one here
# without adding it to a plan or an add-on makes it unavailable everywhere,
# which is the safe direction to fail.

FEATURE_BILLING = "billing"
FEATURE_ONLINE_PAYMENTS = "online_payments"
FEATURE_CALENDAR_SUBSCRIPTIONS = "calendar_subscriptions"
FEATURE_PROGRESS_REPORTS = "progress_reports"
FEATURE_RECURRING_LESSONS = "recurring_lessons"
FEATURE_TEACHER_PAYABLES = "teacher_payables"
FEATURE_SMS = "sms_notifications"
FEATURE_REPORTS = "management_reports"
FEATURE_XERO = "xero"

#: Capabilities every paying tenant has, whatever their tier. The money chain
#: is deliberately in here rather than sold by tier: an entry-tier studio is a
#: single teacher whose whole business is scheduling a lesson, invoicing it and
#: being paid for it. Cutting one link of that out is not a smaller product,
#: it is a broken one. Tiers differ by scale and by team, below.
BASELINE_FEATURES: frozenset[str] = frozenset(
    {
        FEATURE_BILLING,
        FEATURE_ONLINE_PAYMENTS,
        FEATURE_CALENDAR_SUBSCRIPTIONS,
        FEATURE_PROGRESS_REPORTS,
        FEATURE_RECURRING_LESSONS,
    }
)

#: Sold as per-tenant add-ons rather than bundled into any tier.
ADDON_FEATURES: frozenset[str] = frozenset({FEATURE_XERO})

#: Human-readable labels for the console and for API error details.
FEATURE_LABELS: dict[str, dict[str, str]] = {
    FEATURE_BILLING: {"zh": "开票与对账单", "en": "Invoicing and statements"},
    FEATURE_ONLINE_PAYMENTS: {"zh": "在线收款", "en": "Online payments"},
    FEATURE_CALENDAR_SUBSCRIPTIONS: {"zh": "家庭日历订阅", "en": "Family calendar subscriptions"},
    FEATURE_PROGRESS_REPORTS: {"zh": "学生成长报告", "en": "Student progress reports"},
    FEATURE_RECURRING_LESSONS: {"zh": "一对一循环课", "en": "Recurring private lessons"},
    FEATURE_TEACHER_PAYABLES: {"zh": "老师课时与应付清单", "en": "Teacher hours and payables"},
    FEATURE_SMS: {"zh": "短信通道", "en": "SMS channel"},
    FEATURE_REPORTS: {"zh": "经营报表", "en": "Management reports"},
    FEATURE_XERO: {"zh": "Xero 直连", "en": "Xero integration"},
}


class FeatureUnavailableError(RuntimeError):
    """Raised when a tenant reaches a capability it is not entitled to.

    Carries the feature key so the API layer can answer with something a studio
    can act on — "this is an add-on, here is how to get it" — rather than a
    bare 403 that reads like a bug.
    """

    def __init__(self, feature: str, *, reason: str = "") -> None:
        self.feature = feature
        self.reason = reason or "not_entitled"
        label = FEATURE_LABELS.get(feature, {}).get("en", feature)
        super().__init__(f"This studio is not entitled to {label}.")


@dataclass(frozen=True)
class Entitlements:
    """The resolved answer for one tenant, cheap to pass around."""

    features: frozenset[str]
    addons: frozenset[str]
    standalone: bool

    def has(self, feature: str) -> bool:
        return self.standalone or feature in self.features

    def require(self, feature: str) -> None:
        if not self.has(feature):
            raise FeatureUnavailableError(feature)

    def as_payload(self) -> dict[str, Any]:
        """Shape used by the console so the UI can grey things out honestly."""

        known = sorted(FEATURE_LABELS)
        return {
            "standalone": self.standalone,
            "features": {key: self.has(key) for key in known},
            "addons": sorted(self.addons),
        }


def _plan_features(row: dict[str, Any] | None) -> set[str]:
    """Read ``plans.features``, tolerating both jsonb and text representations.

    Existing rows have been written by more than one code path over the life of
    the table. A read path that raises on the shape it did not expect would take
    a studio's whole console down over a stored value, so anything unparseable
    degrades to "no extra features" rather than to an exception.
    """

    if not row:
        return set()
    raw = row.get("features")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError):
            return set()
    if not isinstance(raw, dict):
        return set()
    return {str(key) for key, value in raw.items() if value is True}


def resolve(conn, tenant_id: str) -> Entitlements:
    """Resolve the effective entitlements for one tenant.

    Args:
        conn: An open database connection.
        tenant_id: The tenant being asked about.

    Returns:
        The union of baseline capabilities, whatever the plan bundles, and any
        active add-ons. In standalone mode every capability is available and the
        database is not consulted for add-ons at all.
    """

    if is_standalone():
        return Entitlements(
            features=frozenset(FEATURE_LABELS),
            addons=frozenset(ADDON_FEATURES),
            standalone=True,
        )

    plan_row = fetch_one(
        conn,
        """
        SELECT p.features
        FROM tenants t
        JOIN plans p ON p.code = t.plan_code
        WHERE t.id = %s
        """,
        (tenant_id,),
    )

    addon_rows = fetch_all(
        conn,
        """
        SELECT addon_key
        FROM tenant_addons
        WHERE tenant_id = %s
          AND status = 'active'
          AND (expires_at IS NULL OR expires_at > now())
        """,
        (tenant_id,),
    )
    addons = {str(row["addon_key"]) for row in addon_rows}

    features = set(BASELINE_FEATURES) | _plan_features(plan_row) | addons
    return Entitlements(
        features=frozenset(features),
        addons=frozenset(addons),
        standalone=False,
    )


def require(conn, tenant_id: str, feature: str) -> Entitlements:
    """Resolve and assert in one call, for routes that gate on a single key."""

    entitlements = resolve(conn, tenant_id)
    entitlements.require(feature)
    return entitlements


def grant(
    conn,
    tenant_id: str,
    addon_key: str,
    *,
    granted_by_user_id: str | None = None,
    expires_at: Any = None,
    note: str = "",
) -> None:
    """Give a tenant an add-on. Platform-side only.

    Re-granting a suspended or expired add-on reactivates the same row rather
    than writing a second one, so the grant history stays one line per add-on
    and the audit trail reads as a sequence of decisions about one thing.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenant_addons
                (tenant_id, addon_key, status, granted_by_user_id, expires_at, note)
            VALUES (%s, %s, 'active', %s, %s, %s)
            ON CONFLICT (tenant_id, addon_key) DO UPDATE
               SET status = 'active',
                   granted_at = now(),
                   granted_by_user_id = EXCLUDED.granted_by_user_id,
                   expires_at = EXCLUDED.expires_at,
                   note = EXCLUDED.note,
                   updated_at = now()
            """,
            (tenant_id, addon_key, granted_by_user_id, expires_at, note),
        )


def revoke(conn, tenant_id: str, addon_key: str, *, note: str = "") -> None:
    """Withdraw an add-on without deleting anything.

    Suspending rather than deleting is the whole point: the tenant keeps every
    record the add-on produced, the connection it established and the errors it
    logged. Only new work stops. Re-granting later picks up where it left off
    instead of starting from an empty mapping table.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE tenant_addons
               SET status = 'suspended', note = %s, updated_at = now()
             WHERE tenant_id = %s AND addon_key = %s
            """,
            (note, tenant_id, addon_key),
        )


def known_addon_keys() -> Iterable[str]:
    """Add-on keys the platform console is allowed to offer."""

    return sorted(ADDON_FEATURES)
