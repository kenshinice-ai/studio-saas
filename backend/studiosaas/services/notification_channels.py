"""Channel-agnostic delivery: one interface, adapters behind it.

The existing :mod:`studiosaas.services.notifications` sends one kind of message
one way — an email, over SMTP, for a registration event. This module is the
layer above it: it decides *which* channels an event should travel on for a
given tenant, enforces the spend guard, records what happened, and hands the
actual sending to an adapter.

The routing defaults encode a finding rather than a preference. A studio moving
off a product with bundled unlimited SMS discovers that per-lesson reminders are
three quarters of their message volume and almost none of their value, because
a calendar subscription delivers the same information for free and on the
parent's own schedule. So reminders default to no channel at all — the calendar
feed carries them — and SMS is reserved for messages that must arrive and must
be evidenced.

Two things this module deliberately does not do:

* **Resell messaging.** The SMS account belongs to the tenant and is billed to
  the tenant. We hold credentials to send with, not credit to sell.
* **Send silently at scale.** Every bulk send is counted and costed before it
  goes, and a monthly quota stops one wrong click from spending a fortnight's
  budget.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence

from ..db import fetch_all, fetch_one


class ChannelError(RuntimeError):
    """Delivery was refused before anything was sent."""


class QuotaExceededError(ChannelError):
    """The tenant's monthly allowance for this channel is spent."""


#: Event keys the router knows about, with the default channels for each.
#:
#: ``lesson_reminder`` maps to nothing on purpose: the calendar subscription is
#: the channel, it costs nothing, and a studio that wants SMS reminders as well
#: can add them — having read the cost dashboard first.
DEFAULT_ROUTES: dict[str, tuple[str, ...]] = {
    "invoice_issued": ("sms", "email"),
    "invoice_overdue": ("sms",),
    "payment_received": ("email",),
    "lesson_cancelled": ("sms",),
    "lesson_rescheduled": ("sms",),
    "lesson_reminder": (),
    "low_lesson_balance": ("sms",),
    "progress_report_published": ("email",),
    "statement_ready": ("email",),
}

#: How long a single SMS segment is. Longer messages are split by the carrier
#: and billed per segment, so the estimate has to count segments, not messages —
#: otherwise a studio budgets for 300 and is charged for 600.
SMS_SEGMENT_CHARS = 160
SMS_SEGMENT_CHARS_UNICODE = 70


@dataclass(frozen=True)
class Recipient:
    address: str
    language: str = ""
    name: str = ""


@dataclass(frozen=True)
class SendEstimate:
    channel: str
    recipients: int
    segments: int
    cost_cents: int


def segments_for(body: str) -> int:
    """How many billable segments a message body will become.

    Any character outside the GSM-7 range forces the whole message into UCS-2,
    which more than halves the segment length. A bilingual studio hits this on
    every Chinese message, so counting it is not an edge case here — it is the
    common case.
    """

    if not body:
        return 0
    unicode_needed = any(ord(char) > 127 for char in body)
    size = SMS_SEGMENT_CHARS_UNICODE if unicode_needed else SMS_SEGMENT_CHARS
    return max(1, -(-len(body) // size))


def channel_config(conn, tenant_id: str, channel: str) -> dict[str, Any] | None:
    row = fetch_one(
        conn,
        """
        SELECT channel, provider, sender_identity, config, is_active,
               monthly_quota, quota_alert_at, unit_cost_cents
        FROM notification_channels
        WHERE tenant_id = %s AND channel = %s
        """,
        (tenant_id, channel),
    )
    if row and isinstance(row.get("config"), str):
        try:
            row["config"] = json.loads(row["config"])
        except (TypeError, ValueError):
            row["config"] = {}
    return row


def routes_for(conn, tenant_id: str, event_key: str) -> tuple[str, ...]:
    """Which channels this tenant sends this event on."""

    row = fetch_one(
        conn,
        """
        SELECT channels, is_active FROM notification_routes
        WHERE tenant_id = %s AND event_key = %s
        """,
        (tenant_id, event_key),
    )
    if row is None:
        return DEFAULT_ROUTES.get(event_key, ())
    if not row["is_active"]:
        return ()
    return tuple(row["channels"] or ())


def month_usage(conn, tenant_id: str, channel: str) -> dict[str, int]:
    """Messages sent and cents spent this calendar month."""

    row = fetch_one(
        conn,
        """
        SELECT COUNT(*) AS sent, COALESCE(SUM(cost_cents), 0) AS cost_cents
        FROM notification_logs
        WHERE tenant_id = %s AND channel = %s AND status = 'sent'
          AND created_at >= date_trunc('month', now())
        """,
        (tenant_id, channel),
    ) or {}
    return {"sent": int(row.get("sent") or 0), "costCents": int(row.get("cost_cents") or 0)}


def estimate(
    conn, tenant_id: str, *, channel: str, body: str, recipients: Sequence[Recipient]
) -> SendEstimate:
    """What a bulk send will cost, before it goes.

    Shown to whoever pressed the button. The number that matters to a studio is
    not "300 messages" but "$21", and they should see it while they can still
    change their mind.
    """

    config = channel_config(conn, tenant_id, channel) or {}
    unit = int(config.get("unit_cost_cents") or 0)
    per_message = segments_for(body) if channel == "sms" else 1
    total_segments = per_message * len(recipients)
    return SendEstimate(
        channel=channel,
        recipients=len(recipients),
        segments=total_segments,
        cost_cents=total_segments * unit,
    )


def assert_within_quota(conn, tenant_id: str, channel: str, additional: int) -> None:
    """Refuse a send that would cross the tenant's own ceiling."""

    config = channel_config(conn, tenant_id, channel)
    if not config or config.get("monthly_quota") is None:
        return
    used = month_usage(conn, tenant_id, channel)["sent"]
    quota = int(config["monthly_quota"])
    if used + additional > quota:
        raise QuotaExceededError(
            f"This send would put {channel} at {used + additional} messages this month, "
            f"past the studio's ceiling of {quota}. Raise the ceiling or send fewer."
        )


def is_opted_out(conn, tenant_id: str, channel: str, recipient: str) -> bool:
    return (
        fetch_one(
            conn,
            """
            SELECT 1 AS x FROM notification_optouts
            WHERE tenant_id = %s AND channel = %s AND recipient = %s
            """,
            (tenant_id, channel, recipient),
        )
        is not None
    )


def opt_out(conn, tenant_id: str, channel: str, recipient: str, reason: str = "") -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notification_optouts (tenant_id, channel, recipient, reason)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (tenant_id, channel, recipient) DO NOTHING
            """,
            (tenant_id, channel, recipient, reason),
        )


def log(
    conn,
    tenant_id: str,
    *,
    channel: str,
    recipient: str,
    event_key: str,
    status: str,
    subject: str = "",
    body_preview: str = "",
    language: str = "",
    cost_cents: int = 0,
    provider_message_id: str = "",
    error_message: str = "",
    related_kind: str = "",
    related_id: str | None = None,
) -> None:
    """Record one delivery attempt.

    Every message traces to who it went to, what produced it, when, and what it
    cost. That is what turns an unexplained provider invoice into a line-item a
    studio can check.
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO notification_logs
                (tenant_id, channel, recipient, subject, status, provider_message_id,
                 error_message, event_key, language, body_preview, cost_cents,
                 attempts, sent_at, related_kind, related_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1,
                    CASE WHEN %s = 'sent' THEN now() ELSE NULL END, %s, %s)
            """,
            (tenant_id, channel, recipient, subject, status, provider_message_id,
             error_message, event_key, language, body_preview[:280], cost_cents,
             status, related_kind, related_id),
        )


# ── adapters ─────────────────────────────────────────────────────────────
#
# Each adapter turns one rendered message into one provider call. They are kept
# deliberately thin: everything that is a policy — routing, quota, opt-out,
# logging — happens above, so adding a provider never means re-implementing any
# of it, and a studio can change provider without changing behaviour.


class ChannelAdapter:
    """One way of getting a message to somebody."""

    channel = ""

    def send(self, config: dict[str, Any], recipient: Recipient, subject: str, body: str) -> str:
        raise NotImplementedError


class EmailAdapter(ChannelAdapter):
    """Delivers over the existing SMTP path.

    Reuses :func:`studiosaas.services.notifications._deliver` rather than
    opening a second way to send email, so sending domain, credentials and
    failure behaviour stay in one place.
    """

    channel = "email"

    def send(self, config: dict[str, Any], recipient: Recipient, subject: str, body: str) -> str:
        from .notifications import _deliver  # local import: optional dependency path

        return _deliver(subject, body, recipient.address)


class SmsAdapter(ChannelAdapter):
    """Delivers through the tenant's own SMS provider.

    The provider call itself is intentionally not implemented here: it needs the
    tenant's account, and no message should be sent from a shared one. Until a
    tenant configures theirs, this raises rather than pretending to have sent —
    a notification the studio believes went out and did not is worse than one
    that visibly failed.
    """

    channel = "sms"

    def send(self, config: dict[str, Any], recipient: Recipient, subject: str, body: str) -> str:
        provider = (config.get("provider") or "").strip()
        if not provider:
            raise ChannelError(
                "No SMS provider is configured for this studio. Connect one in "
                "Settings → Notifications; the account and its charges stay with you."
            )
        raise ChannelError(
            f"The {provider} SMS adapter is configured but not enabled in this build."
        )


ADAPTERS: dict[str, ChannelAdapter] = {
    EmailAdapter.channel: EmailAdapter(),
    SmsAdapter.channel: SmsAdapter(),
}


def dispatch(
    conn,
    tenant_id: str,
    *,
    event_key: str,
    recipient: Recipient,
    subject: str,
    body: str,
    related_kind: str = "",
    related_id: str | None = None,
) -> list[str]:
    """Send one event to one recipient on whichever channels apply.

    Returns the channels that accepted the message. A channel that is inactive,
    opted out of, over quota or missing configuration is skipped and logged
    rather than raised, because one unreachable channel should not stop the
    others — a family that has opted out of SMS should still get the email.
    """

    delivered: list[str] = []
    for channel in routes_for(conn, tenant_id, event_key):
        config = channel_config(conn, tenant_id, channel)
        if not config or not config.get("is_active"):
            continue
        if is_opted_out(conn, tenant_id, channel, recipient.address):
            log(conn, tenant_id, channel=channel, recipient=recipient.address,
                event_key=event_key, status="failed", error_message="opted_out",
                related_kind=related_kind, related_id=related_id)
            continue

        cost = segments_for(body) * int(config.get("unit_cost_cents") or 0) if channel == "sms" else 0
        try:
            assert_within_quota(conn, tenant_id, channel, 1)
            provider_id = ADAPTERS[channel].send(config, recipient, subject, body)
        except (ChannelError, KeyError, RuntimeError) as exc:
            log(conn, tenant_id, channel=channel, recipient=recipient.address,
                event_key=event_key, status="failed", subject=subject,
                body_preview=body, language=recipient.language,
                error_message=str(exc)[:400], related_kind=related_kind,
                related_id=related_id)
            continue

        log(conn, tenant_id, channel=channel, recipient=recipient.address,
            event_key=event_key, status="sent", subject=subject, body_preview=body,
            language=recipient.language, cost_cents=cost,
            provider_message_id=provider_id or "", related_kind=related_kind,
            related_id=related_id)
        delivered.append(channel)
    return delivered
