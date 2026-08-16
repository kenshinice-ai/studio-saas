"""E3 (v10.8.0) — recording that an invoice has been chased, by hand.

Following up money is deliberately a human activity in this product: the
studio calls or messages the family themselves, in their own words, through
their own relationship. What was missing is memory — three weeks later
nobody could say whether anyone had already asked. This service appends a
``reminder_recorded`` event to the invoice's existing append-only history,
carrying the operator and an optional free-text mark. It deliberately has no
outbound path of any kind.

Idempotency reuses the ``financial_operation_requests`` contract every money
mutation uses: a replayed ``requestId`` returns the original event, and the
same ``requestId`` with different content is refused.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from ..db import fetch_one
from .credit_settlements import (
    CreditSettlementConflict,
    _finish_operation,
    _operation_start,
    payload_hash,
)

OPERATION_KIND = "invoice_reminder"
NOTE_LIMIT = 500


class InvoiceReminderError(RuntimeError):
    """A reminder request was invalid."""


class InvoiceReminderNotFound(InvoiceReminderError):
    """The invoice does not exist in this tenant."""


class InvoiceNotRemindable(InvoiceReminderError):
    """Drafts and voided invoices have nothing to chase."""


class InvoiceReminderConflict(InvoiceReminderError):
    """The requestId is bound to a different or in-flight reminder."""


def record_reminder(
    conn,
    tenant_id: str,
    invoice_id: str,
    payload: Mapping[str, Any],
    *,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    """Append one ``reminder_recorded`` event, exactly once per requestId."""

    if not isinstance(payload, Mapping):
        raise InvoiceReminderError("A JSON object is required.")
    unknown = sorted(set(payload) - {"requestId", "note"})
    if unknown:
        raise InvoiceReminderError(f"Unknown reminder field(s): {', '.join(unknown)}")

    raw_request_id = str(payload.get("requestId") or "").strip()
    if not raw_request_id:
        raise InvoiceReminderError("requestId is required.")
    try:
        request_id = str(uuid.UUID(raw_request_id))
    except (ValueError, AttributeError, TypeError) as exc:
        raise InvoiceReminderError("requestId must be a UUID.") from exc

    raw_note = payload.get("note")
    if raw_note is None:
        note = ""
    elif isinstance(raw_note, str):
        note = raw_note.strip()
    else:
        raise InvoiceReminderError("note must be text.")
    if len(note) > NOTE_LIMIT:
        # Refused rather than truncated: silently dropping half an operator's
        # mark is the kind of quiet data loss this codebase treats as a defect.
        raise InvoiceReminderError(f"note must be at most {NOTE_LIMIT} characters.")

    digest = payload_hash({"requestId": request_id, "invoiceId": str(invoice_id), "note": note})
    try:
        operation, replayed = _operation_start(
            conn, tenant_id, request_id, OPERATION_KIND, digest
        )
    except CreditSettlementConflict as exc:
        raise InvoiceReminderConflict(str(exc)) from exc
    if replayed:
        return operation

    invoice = fetch_one(
        conn,
        "SELECT id, status, number FROM invoices WHERE tenant_id = %s AND id = %s FOR UPDATE",
        (tenant_id, invoice_id),
    )
    if not invoice:
        raise InvoiceReminderNotFound("Invoice not found.")
    if invoice["status"] in ("draft", "void"):
        raise InvoiceNotRemindable(
            "只有已签发的发票才能标记提醒。 Only an issued invoice can be marked as reminded."
        )

    detail = {"note": note, "request_id": request_id}
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO invoice_events (tenant_id, invoice_id, event_type, actor_user_id, detail)
            VALUES (%s, %s, 'reminder_recorded', %s, %s::jsonb)
            RETURNING id, occurred_at
            """,
            (tenant_id, invoice_id, actor_user_id, json.dumps(detail, ensure_ascii=False)),
        )
        event = cur.fetchone()

    result = {
        "requestId": request_id,
        "invoiceId": str(invoice_id),
        "event": {
            "id": str(event["id"]),
            "eventType": "reminder_recorded",
            "note": note,
            "occurredAt": event["occurred_at"].isoformat(),
            "actorUserId": str(actor_user_id) if actor_user_id else None,
        },
        "replayed": False,
    }
    _finish_operation(conn, tenant_id, request_id, OPERATION_KIND, result)
    return result
