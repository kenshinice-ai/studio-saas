"""The Xero connection, and the three switches that are not one switch.

Products collapse "has bought it", "is connected to it" and "is pushing to it"
into a single toggle, and then three ordinary events break each other:

* the add-on lapses — new pushes must stop while the connection, the id
  mappings, the error queue and the exports all stay exactly where they were;
* the studio changes accountant — reconnect and re-confirm the mapping, with
  the entitlement untouched;
* year-end close — pause pushing for a fortnight without disturbing either.

So entitlement lives in ``tenant_addons`` and is resolved by
:mod:`studiosaas.services.entitlements`; the connection lives in
``xero_connections``; and pushing is a third state in ``xero_sync_settings``.

The third one is a gate rather than a checkbox. It cannot be opened until the
account mapping exists, a full cycle has run against a Xero demo organisation,
and the studio has answered the question that actually breaks ledgers: is
something else — a payment provider's own connector, most often — already
syncing the same receipts into the same Xero organisation? Two feeds writing
the same money produce two sets of records in the live ledger, and cleaning
that up costs more than the manual entry it replaced.

That gate is a CHECK constraint (migration 0037), not a rule in this file. A
service can be bypassed by a script; the constraint cannot.

Direction is one-way: documents are pushed, payment status is read back. There
is deliberately no two-way edit sync. When both sides can edit the same invoice
they eventually disagree, and the studio is left holding two versions of one
number with no way to tell which is true.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from ..db import fetch_all, fetch_one
from . import entitlements


# The schema and gate are deliberately shipped ahead of the provider client.
# Keep this false until OAuth, token refresh, HTTP retries, worker delivery,
# and provider-response handling have been implemented and accepted together.
TRANSPORT_AVAILABLE = False
INTEGRATION_STAGE = "live" if TRANSPORT_AVAILABLE else "preview"


class XeroError(RuntimeError):
    """A Xero operation was refused, with a reason a studio can act on."""


#: Every kind of line that needs somewhere to land in the chart of accounts.
MAPPABLE_ITEM_KINDS = (
    "tuition", "package", "rental", "goods", "ticket", "engagement",
    "opening_balance", "teacher_payable", "bank", "clearing",
)

#: The subset that must be mapped before the gate will open. A studio that
#: never sells tickets should not be blocked on mapping ticket revenue.
REQUIRED_ITEM_KINDS = ("tuition", "bank")


@dataclass(frozen=True)
class GateStatus:
    """Why the push switch is, or is not, available."""

    entitled: bool
    connected: bool
    mapping_confirmed: bool
    demo_run_completed: bool
    single_entry_answered: bool
    push_enabled: bool
    transport_available: bool = TRANSPORT_AVAILABLE

    @property
    def can_enable(self) -> bool:
        return (
            self.entitled
            and self.connected
            and self.mapping_confirmed
            and self.demo_run_completed
            and self.single_entry_answered
            and self.transport_available
        )

    def blockers(self) -> list[str]:
        """What is still missing, in the order the wizard asks for it."""

        missing: list[str] = []
        if not self.entitled:
            missing.append("addon_not_active")
        if not self.connected:
            missing.append("not_connected")
        if not self.mapping_confirmed:
            missing.append("mapping_not_confirmed")
        if not self.demo_run_completed:
            missing.append("demo_run_not_completed")
        if not self.single_entry_answered:
            missing.append("single_entry_not_answered")
        if not self.transport_available:
            missing.append("transport_not_available")
        return missing


def gate_status(conn, tenant_id: str) -> GateStatus:
    """Resolve all three switches at once, for the wizard and for the API."""

    entitled = entitlements.resolve(conn, tenant_id).has(entitlements.FEATURE_XERO)
    connection = fetch_one(
        conn,
        "SELECT status FROM xero_connections WHERE tenant_id = %s",
        (tenant_id,),
    )
    settings = fetch_one(
        conn,
        """
        SELECT push_enabled, mapping_confirmed_at, demo_run_completed_at,
               single_entry_decision
        FROM xero_sync_settings WHERE tenant_id = %s
        """,
        (tenant_id,),
    ) or {}

    return GateStatus(
        entitled=entitled,
        connected=bool(connection and connection["status"] == "connected"),
        mapping_confirmed=bool(settings.get("mapping_confirmed_at")),
        demo_run_completed=bool(settings.get("demo_run_completed_at")),
        single_entry_answered=(
            settings.get("single_entry_decision", "not_answered") != "not_answered"
        ),
        push_enabled=bool(settings.get("push_enabled")),
        transport_available=TRANSPORT_AVAILABLE,
    )


def missing_required_mappings(conn, tenant_id: str) -> list[str]:
    """Which of the must-have account mappings are still blank."""

    rows = fetch_all(
        conn,
        """
        SELECT item_kind FROM xero_account_mappings
        WHERE tenant_id = %s AND length(account_code) > 0
        """,
        (tenant_id,),
    )
    present = {row["item_kind"] for row in rows}
    return [kind for kind in REQUIRED_ITEM_KINDS if kind not in present]


def confirm_mapping(conn, tenant_id: str) -> None:
    """Mark the chart-of-accounts mapping as signed off.

    Refuses while a required mapping is blank. The studio's accountant owns
    these values; the product's only job is to make it impossible to start
    pushing before somebody has actually supplied them.
    """

    missing = missing_required_mappings(conn, tenant_id)
    if missing:
        raise XeroError(
            "These account mappings are still blank: " + ", ".join(missing)
        )
    _upsert_settings(conn, tenant_id, mapping_confirmed_at="now()")


def record_demo_run(conn, tenant_id: str) -> None:
    """Record that a full cycle completed against a Xero demo organisation."""

    _upsert_settings(conn, tenant_id, demo_run_completed_at="now()")


def answer_single_entry(
    conn, tenant_id: str, *, decision: str, clearing_account_code: str = ""
) -> None:
    """Record how the studio resolved the duplicate-feed question.

    ``ours_only`` — the other connector was switched off, and this system is the
    single entry point. ``clearing_account`` — both remain, and our receipts are
    routed through a clearing account so they cannot double-count against the
    bank.
    """

    if decision not in {"ours_only", "clearing_account"}:
        raise XeroError("Answer must be 'ours_only' or 'clearing_account'.")
    if decision == "clearing_account" and not clearing_account_code.strip():
        raise XeroError(
            "Routing through a clearing account needs the account code to route to."
        )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO xero_sync_settings (tenant_id, single_entry_decision, clearing_account_code)
            VALUES (%s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE
               SET single_entry_decision = EXCLUDED.single_entry_decision,
                   clearing_account_code = EXCLUDED.clearing_account_code,
                   updated_at = now()
            """,
            (tenant_id, decision, clearing_account_code.strip()),
        )


def set_push_enabled(conn, tenant_id: str, enabled: bool) -> GateStatus:
    """Open or close the third switch.

    Turning it on runs the gate first so the caller gets a list of what is
    missing rather than a constraint violation. Turning it off is always
    allowed and always safe — that is the point of it being separate from the
    other two.
    """

    if enabled:
        status = gate_status(conn, tenant_id)
        if not status.can_enable:
            raise XeroError(
                "Xero pushing cannot be enabled yet: " + ", ".join(status.blockers())
            )
    _upsert_settings(conn, tenant_id, push_enabled="true" if enabled else "false")
    return gate_status(conn, tenant_id)


def _upsert_settings(conn, tenant_id: str, **columns: str) -> None:
    """Write settings columns whose values are SQL literals, not parameters.

    Only called with literals this module controls (``now()``, ``true``,
    ``false``); nothing here ever interpolates caller input.
    """

    assignments = ", ".join(f"{name} = {value}" for name, value in columns.items())
    inserted = ", ".join(columns)
    values = ", ".join(columns.values())
    with conn.cursor() as cur:
        cur.execute(
            f"""
            INSERT INTO xero_sync_settings (tenant_id, {inserted})
            VALUES (%s, {values})
            ON CONFLICT (tenant_id) DO UPDATE
               SET {assignments}, updated_at = now()
            """,
            (tenant_id,),
        )


# ── pushing ──────────────────────────────────────────────────────────────


def idempotency_key(tenant_id: str, local_kind: str, local_id: str, revision: str = "") -> str:
    """A stable key for one document's push.

    Derived from what is being pushed rather than from when, so a retry an hour
    later produces the same key and cannot create a second document in the
    customer's ledger.
    """

    digest = hashlib.sha256(
        f"{tenant_id}|{local_kind}|{local_id}|{revision}".encode("utf-8")
    ).hexdigest()
    return f"{local_kind}_{digest[:32]}"


def enqueue(
    conn, tenant_id: str, *, local_kind: str, local_id: str, revision: str = ""
) -> dict[str, Any] | None:
    """Queue a document for pushing, once.

    Returns ``None`` when the document is already queued or sent — that is not
    an error, it is the idempotency working. Callers should treat it as success.

    Queueing is skipped entirely when the push switch is off, but the document
    is not lost: it will be picked up by a backfill when pushing resumes, which
    is what makes pausing for year-end a safe thing to do.
    """

    status = gate_status(conn, tenant_id)
    if not status.push_enabled or not status.transport_available:
        return None

    key = idempotency_key(tenant_id, local_kind, local_id, revision)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO integration_sync_jobs
                (tenant_id, integration, local_kind, local_id, idempotency_key)
            VALUES (%s, 'xero', %s, %s, %s)
            ON CONFLICT (tenant_id, integration, idempotency_key) DO NOTHING
            RETURNING id, status
            """,
            (tenant_id, local_kind, local_id, key),
        )
        return cur.fetchone()


def record_link(
    conn, tenant_id: str, *, local_kind: str, local_id: str, xero_kind: str, xero_id: str
) -> None:
    """Remember which Xero object a local record became.

    The two-way uniqueness is what makes a replay safe: a second push finds the
    link and updates the existing document instead of creating a twin.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO xero_object_links (tenant_id, local_kind, local_id, xero_kind, xero_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, local_kind, local_id) DO UPDATE
               SET xero_kind = EXCLUDED.xero_kind,
                   xero_id = EXCLUDED.xero_id,
                   updated_at = now()
            """,
            (tenant_id, local_kind, local_id, xero_kind, xero_id),
        )


def error_queue(conn, tenant_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
    """What did not reach Xero, and why.

    Surfaced to the studio rather than to us: the fixes are almost always a
    mapping the accountant needs to correct, and waiting on a support ticket to
    learn that is a poor use of everyone's week.
    """

    return fetch_all(
        conn,
        """
        SELECT id, local_kind, local_id, status, attempts, last_error, queued_at
        FROM integration_sync_jobs
        WHERE tenant_id = %s AND status = 'failed'
        ORDER BY queued_at DESC
        LIMIT %s
        """,
        (tenant_id, limit),
    )


def replay(conn, tenant_id: str, job_id: str) -> None:
    """Put a failed job back in the queue, keeping its idempotency key.

    Keeping the key is the whole point: whatever partial state the failed
    attempt left in Xero is found and completed rather than duplicated.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE integration_sync_jobs
               SET status = 'queued', last_error = '', completed_at = NULL
             WHERE tenant_id = %s AND id = %s AND status = 'failed'
            """,
            (tenant_id, job_id),
        )


def payable_export_kind(engagement: str) -> str:
    """How a teacher's total may enter Xero, given how they are engaged.

    A contractor's total becomes an accounts-payable bill. An employee's must
    not: wages posted as a bill bypass the payroll accounts and misstate the
    books. When nobody has recorded the engagement, this refuses rather than
    choosing — a wrong guess here is discovered at year end, by an accountant,
    in somebody else's ledger.
    """

    if engagement == "contractor":
        return "bill"
    if engagement == "employee":
        return "summary_only"
    raise XeroError(
        "This teacher's engagement type is not recorded. Set employee or "
        "contractor before exporting: it decides whether the amount may be "
        "posted as a payable bill."
    )
