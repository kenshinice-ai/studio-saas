"""The Xero transport (X3) — what actually crosses the wire, and when.

``xero.py`` owns the three switches and the queue model; ``xero_oauth.py``
owns the tokens. This module owns the last mile: turning a queued job into
an HTTP call against the Xero Accounting API, recording what came back, and
never creating the same document twice.

Design decisions that are load-bearing:

* **One direction.** Documents are pushed; nothing is imported back. When
  both sides can edit an invoice they eventually disagree, and the studio is
  left holding two versions of one number.

* **Exact amounts, not recomputed ones.** Every line is pushed with
  ``Quantity=1``, ``UnitAmount = net``, and an explicit ``TaxAmount``, with
  the human quantity kept in the description. Xero's own tax arithmetic
  rounds per-line at 2dp; ours rounds in cents at source. Letting Xero
  recompute is how a $605.00 statement reconciles to $604.99. The exit
  criterion for this whole stage is *zero* difference, so the payload
  carries the cents we mean.

* **The link is per-organisation.** ``xero_object_links.org_id`` records
  which ledger an id belongs to. After the studio reconnects from the Demo
  Company to the real org, every old link is invisible to the new org and
  documents are created fresh — updating a ghost in the demo ledger is
  exactly the bug the wizard exists to prevent.

* **Failures are classified, not retried blindly.** 429/5xx/network park
  the job with exponential backoff (the ``next_attempt_at`` column, so a
  restart forgets nothing). 4xx validation errors dead-letter immediately
  with Xero's own message — the fix is almost always a mapping the
  accountant needs to change, and retrying will not change the answer.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..db import fetch_all, fetch_one
from . import invoice_documents as _documents
from . import xero as _xero
from . import xero_oauth as _oauth

API_BASE = "https://api.xero.com/api.xro/2.0"
HTTP_TIMEOUT = 25
MAX_ATTEMPTS = 8
#: Kinds are drained in dependency order: an invoice must exist in Xero
#: before a payment or a credit-note allocation can land on it.
KIND_ORDER = {"invoice": 0, "credit_note": 1, "payment": 2}
#: Line kinds that post to another kind's account. ``lesson`` and ``manual``
#: lines are tuition revenue by declaration (stated in the mapping editor,
#: not silently assumed): a studio that needs them elsewhere edits the line
#: kind at source, not the ledger after the fact.
KIND_ALIASES = {"lesson": "tuition", "manual": "tuition"}


class TransportError(RuntimeError):
    """A push failed. ``retryable`` decides backoff versus dead-letter."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


class DependencyPending(TransportError):
    """The job needs another object pushed first; try again shortly."""

    def __init__(self, message: str):
        super().__init__(message, retryable=True)


# ── HTTP against api.xero.com ────────────────────────────────────────────


def _api(
    conn,
    tenant_id: str,
    org_id: str,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        token = _oauth.ensure_access_token(conn, tenant_id)
    except _oauth.XeroOAuthError as exc:
        # A dead refresh token is not retryable by a worker — it needs a
        # human to reconnect, and the connection card already says so.
        raise TransportError(f"Xero connection unusable: {exc}") from exc
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"{API_BASE}{path}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Xero-tenant-id": org_id,
            "Accept": "application/json",
            **({"Content-Type": "application/json"} if body else {}),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as resp:
            text = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        if exc.code in (429,) or exc.code >= 500:
            raise TransportError(
                f"Xero is unavailable (HTTP {exc.code}); will retry.", retryable=True
            ) from exc
        if exc.code == 404:
            raise TransportError("not_found", retryable=False) from exc
        raise TransportError(_validation_summary(exc.code, detail)) from exc
    except urllib.error.URLError as exc:
        raise TransportError(f"Could not reach Xero: {exc.reason}", retryable=True) from exc
    try:
        return json.loads(text)
    except ValueError as exc:
        raise TransportError("Xero returned a non-JSON response.", retryable=True) from exc


def _validation_summary(code: int, detail: str) -> str:
    """Xero's validation errors, flattened to the sentence a studio can act on."""

    try:
        parsed = json.loads(detail)
    except ValueError:
        return f"Xero rejected the request (HTTP {code}): {detail[:200]}"
    messages: list[str] = []
    for element in parsed.get("Elements", []) or []:
        for err in element.get("ValidationErrors", []) or []:
            message = str(err.get("Message") or "").strip()
            if message and message not in messages:
                messages.append(message)
    if not messages and parsed.get("Message"):
        messages.append(str(parsed["Message"]))
    joined = "; ".join(messages[:4]) or detail[:200]
    return f"Xero rejected the request (HTTP {code}): {joined}"


def _org_id(conn, tenant_id: str) -> str:
    row = fetch_one(
        conn,
        "SELECT org_id, status FROM xero_connections WHERE tenant_id = %s",
        (tenant_id,),
    )
    if not row or row["status"] != "connected" or not row["org_id"]:
        raise TransportError("This studio is not connected to a Xero organisation.")
    return row["org_id"]


# ── mappings and money ───────────────────────────────────────────────────


def _mappings(conn, tenant_id: str) -> dict[str, dict[str, str]]:
    rows = fetch_all(
        conn,
        "SELECT item_kind, account_code, tax_type FROM xero_account_mappings WHERE tenant_id = %s",
        (tenant_id,),
    )
    return {row["item_kind"]: row for row in rows}


def _account_for(mappings: dict[str, dict[str, str]], source_kind: str) -> dict[str, str]:
    kind = KIND_ALIASES.get(source_kind, source_kind)
    row = mappings.get(kind)
    if not row or not str(row.get("account_code") or "").strip():
        raise TransportError(
            f"No account mapping for line kind '{kind}'. "
            "Fill it in under 集成 → 科目与税率映射, then replay this document."
        )
    return row


def _money(cents: int) -> float:
    # Xero's JSON amounts are decimal at 2dp; cents/100 at 2dp is exact.
    return round(int(cents) / 100.0, 2)


def _line_items(dto: dict[str, Any], mappings: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for line in dto["lines"]:
        mapping = _account_for(mappings, str(line.get("sourceKind") or "manual"))
        quantity = str(line.get("quantity") or "1")
        description = str(line.get("description") or "").strip() or "Line"
        if quantity not in ("1", "1.0", "1.00"):
            unit = _money(int(line.get("unitPriceCents") or 0))
            description = f"{description} ({quantity} × {unit:.2f})"
        item = {
            # Quantity 1 + explicit amounts: Xero must not re-derive our cents.
            "Description": description,
            "Quantity": 1.0,
            "UnitAmount": _money(int(line["netCents"])),
            "LineAmount": _money(int(line["netCents"])),
            "TaxAmount": _money(int(line["taxCents"])),
            "AccountCode": str(mapping["account_code"]).strip(),
        }
        tax_type = str(mapping.get("tax_type") or "").strip()
        if tax_type:
            item["TaxType"] = tax_type
        items.append(item)
    return items


# ── contacts ─────────────────────────────────────────────────────────────


def _link(conn, tenant_id: str, org_id: str, local_kind: str, local_id: str) -> str | None:
    row = fetch_one(
        conn,
        """
        SELECT xero_id FROM xero_object_links
        WHERE tenant_id = %s AND local_kind = %s AND local_id = %s AND org_id = %s
        """,
        (tenant_id, local_kind, local_id, org_id),
    )
    return row["xero_id"] if row else None


def _record_link(
    conn, tenant_id: str, org_id: str, local_kind: str, local_id: str, xero_kind: str, xero_id: str
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO xero_object_links
                (tenant_id, local_kind, local_id, xero_kind, xero_id, org_id)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id, local_kind, local_id) DO UPDATE
               SET xero_kind = EXCLUDED.xero_kind,
                   xero_id = EXCLUDED.xero_id,
                   org_id = EXCLUDED.org_id,
                   updated_at = now()
            """,
            (tenant_id, local_kind, local_id, xero_kind, xero_id, org_id),
        )


def _ensure_contact(
    conn, tenant_id: str, org_id: str, account_id: str, display_name: str, email: str
) -> str:
    """Create or update the Xero contact for a billing account; return its id."""

    existing = _link(conn, tenant_id, org_id, "billing_account", account_id)
    name = display_name.strip() or f"Account {account_id[:8]}"
    contact: dict[str, Any] = {
        "Name": name,
        # ContactNumber is Xero's client-key field: our stable id, so a
        # renamed payer updates one contact instead of spawning another.
        "ContactNumber": account_id,
    }
    if email.strip():
        contact["EmailAddress"] = email.strip()
    if existing:
        contact["ContactID"] = existing
    try:
        result = _api(conn, tenant_id, org_id, "POST", "/Contacts", {"Contacts": [contact]})
    except TransportError as exc:
        if str(exc) == "not_found" and existing:
            # The stored id belongs to a contact this org no longer has
            # (demo ledger reset, most likely). Create it fresh.
            contact.pop("ContactID", None)
            result = _api(conn, tenant_id, org_id, "POST", "/Contacts", {"Contacts": [contact]})
        elif "name" in str(exc).lower() and "already" in str(exc).lower() and not existing:
            # Same human name, different payer. Disambiguate deterministically.
            contact["Name"] = f"{name} · {account_id[:8]}"
            result = _api(conn, tenant_id, org_id, "POST", "/Contacts", {"Contacts": [contact]})
        else:
            raise
    contacts = result.get("Contacts") or []
    if not contacts or not contacts[0].get("ContactID"):
        raise TransportError("Xero's contact response carried no ContactID.")
    xero_id = str(contacts[0]["ContactID"])
    _record_link(conn, tenant_id, org_id, "billing_account", account_id, "Contact", xero_id)
    return xero_id


# ── documents ────────────────────────────────────────────────────────────


def _load_invoice_dto(conn, tenant_id: str, invoice_id: str) -> tuple[dict[str, Any], str]:
    invoice = fetch_one(
        conn,
        "SELECT * FROM invoices WHERE tenant_id = %s AND id = %s",
        (tenant_id, invoice_id),
    )
    if not invoice:
        raise TransportError("This invoice no longer exists locally.")
    if not invoice.get("number"):
        raise TransportError("Only issued (numbered) invoices can be pushed.")
    lines = fetch_all(
        conn,
        "SELECT * FROM invoice_lines WHERE tenant_id = %s AND invoice_id = %s ORDER BY created_at, id",
        (tenant_id, invoice_id),
    )
    dto = _documents.build_invoice_document(invoice, lines)
    return dto, str(invoice["billing_account_id"])


def _refuse_foreign_number(conn, tenant_id: str, org_id: str, path: str, number: str) -> None:
    """Refuse to create a document whose number the org already holds.

    Xero's POST endpoints upsert by document number: creating "INV-0001" in
    an organisation that already has one silently UPDATES the existing
    document — someone else's, possibly paid, possibly another system's.
    X4 discovered this live: the real ledger already carried years of
    INV-#### documents. A number that exists but is not OUR link is
    therefore a hard, human-actionable refusal, never an update.
    """

    try:
        _api(conn, tenant_id, org_id, "GET", f"{path}/{urllib.parse.quote(number)}")
    except TransportError as exc:
        if str(exc) == "not_found":
            return  # the number is free — safe to create
        raise
    raise TransportError(
        f"Document number '{number}' already exists in the connected Xero "
        "organisation and does not belong to this studio's pushes. Pushing "
        "would overwrite it. Ask the operator for a distinct document-number "
        "prefix for this studio, or connect a dedicated organisation."
    )


def push_invoice(conn, tenant_id: str, org_id: str, invoice_id: str) -> dict[str, Any]:
    dto, account_id = _load_invoice_dto(conn, tenant_id, invoice_id)
    meta = dto["document"]
    status = str(meta.get("status") or "")
    existing = _link(conn, tenant_id, org_id, "invoice", invoice_id)

    if status == "void":
        if not existing:
            return {"skipped": "voided before it was ever pushed"}
        _api(conn, tenant_id, org_id, "POST", "/Invoices", {
            "Invoices": [{"InvoiceID": existing, "Status": "VOIDED"}],
        })
        return {"xeroId": existing, "status": "VOIDED"}

    if not existing:
        _refuse_foreign_number(conn, tenant_id, org_id, "/Invoices", str(meta.get("number")))
    contact_id = _ensure_contact(
        conn, tenant_id, org_id, account_id,
        str(dto["recipient"].get("displayName") or ""),
        str(dto["recipient"].get("email") or ""),
    )
    mappings = _mappings(conn, tenant_id)
    payload: dict[str, Any] = {
        "Type": "ACCREC",
        "Contact": {"ContactID": contact_id},
        "InvoiceNumber": str(meta.get("number")),
        "Reference": f"PWE {meta.get('number')}",
        "Date": meta.get("issueDate") or None,
        "DueDate": meta.get("dueDate") or meta.get("issueDate") or None,
        "LineAmountTypes": "Exclusive",
        "LineItems": _line_items(dto, mappings),
        "Status": "AUTHORISED",
        "CurrencyCode": str(meta.get("currency") or "AUD"),
    }
    if existing:
        payload["InvoiceID"] = existing
    try:
        result = _api(conn, tenant_id, org_id, "POST", "/Invoices", {"Invoices": [payload]})
    except TransportError as exc:
        if str(exc) == "not_found" and existing:
            payload.pop("InvoiceID", None)
            result = _api(conn, tenant_id, org_id, "POST", "/Invoices", {"Invoices": [payload]})
        else:
            raise
    rows = result.get("Invoices") or []
    if not rows or not rows[0].get("InvoiceID"):
        raise TransportError("Xero's invoice response carried no InvoiceID.")
    xero_id = str(rows[0]["InvoiceID"])
    _record_link(conn, tenant_id, org_id, "invoice", invoice_id, "Invoice", xero_id)
    return {"xeroId": xero_id, "number": meta.get("number"), "totalCents": dto["totals"]["totalCents"]}


def push_credit_note(conn, tenant_id: str, org_id: str, credit_note_id: str) -> dict[str, Any]:
    note = fetch_one(
        conn,
        "SELECT * FROM credit_notes WHERE tenant_id = %s AND id = %s",
        (tenant_id, credit_note_id),
    )
    if not note:
        raise TransportError("This credit note no longer exists locally.")
    if note["status"] != "issued" or not note.get("number"):
        raise TransportError("Only issued (numbered) credit notes can be pushed.")
    lines = fetch_all(
        conn,
        "SELECT * FROM credit_note_lines WHERE tenant_id = %s AND credit_note_id = %s ORDER BY created_at, id",
        (tenant_id, credit_note_id),
    )
    dto = _documents.build_credit_note_document(note, lines)
    contact_id = _ensure_contact(
        conn, tenant_id, org_id, str(note["billing_account_id"]),
        str(dto["recipient"].get("displayName") or ""),
        str(dto["recipient"].get("email") or ""),
    )
    mappings = _mappings(conn, tenant_id)
    existing = _link(conn, tenant_id, org_id, "credit_note", credit_note_id)
    if not existing:
        _refuse_foreign_number(conn, tenant_id, org_id, "/CreditNotes", str(note["number"]))
    payload: dict[str, Any] = {
        "Type": "ACCRECCREDIT",
        "Contact": {"ContactID": contact_id},
        "CreditNoteNumber": str(note["number"]),
        "Reference": f"PWE {note['number']}",
        "Date": dto["document"].get("issueDate") or None,
        "LineAmountTypes": "Exclusive",
        "LineItems": _line_items(dto, mappings),
        "Status": "AUTHORISED",
    }
    if existing:
        payload["CreditNoteID"] = existing
    try:
        result = _api(conn, tenant_id, org_id, "POST", "/CreditNotes", {"CreditNotes": [payload]})
    except TransportError as exc:
        if str(exc) == "not_found" and existing:
            payload.pop("CreditNoteID", None)
            result = _api(conn, tenant_id, org_id, "POST", "/CreditNotes", {"CreditNotes": [payload]})
        else:
            raise
    rows = result.get("CreditNotes") or []
    if not rows or not rows[0].get("CreditNoteID"):
        raise TransportError("Xero's credit-note response carried no CreditNoteID.")
    xero_id = str(rows[0]["CreditNoteID"])
    _record_link(conn, tenant_id, org_id, "credit_note", credit_note_id, "CreditNote", xero_id)

    # A credit note that settles a specific invoice is allocated to it, so the
    # invoice's balance in Xero matches the studio's ledger. Already-allocated
    # is fine: Xero refuses over-allocation and we surface anything else.
    if note.get("invoice_id") and note["total_cents"]:
        invoice_xero = _link(conn, tenant_id, org_id, "invoice", str(note["invoice_id"]))
        if not invoice_xero:
            raise DependencyPending("The credited invoice has not reached Xero yet.")
        already = _money_allocated(result)
        if already <= 0:
            try:
                _api(conn, tenant_id, org_id, "PUT", f"/CreditNotes/{xero_id}/Allocations", {
                    "Allocations": [{
                        "Amount": _money(int(note["total_cents"])),
                        "Invoice": {"InvoiceID": invoice_xero},
                    }],
                })
            except TransportError as exc:
                if "amount" not in str(exc).lower() or "remaining" not in str(exc).lower():
                    raise
    return {"xeroId": xero_id, "number": note["number"], "totalCents": int(note["total_cents"])}


def _money_allocated(credit_note_response: dict[str, Any]) -> float:
    rows = credit_note_response.get("CreditNotes") or [{}]
    try:
        total = float(rows[0].get("Total") or 0)
        remaining = float(rows[0].get("RemainingCredit", total))
    except (TypeError, ValueError):
        return 0.0
    return round(total - remaining, 2)


def push_payment(conn, tenant_id: str, org_id: str, allocation_id: str) -> dict[str, Any]:
    """One Xero Payment per allocation — the allocation IS the unit of money
    that touched an invoice, and a split payment is two of them."""

    row = fetch_one(
        conn,
        """
        SELECT pa.id, pa.invoice_id, pa.amount_cents,
               p.received_at, p.method, p.status AS payment_status, p.id AS payment_id
        FROM payment_allocations pa
        JOIN payments p ON p.tenant_id = pa.tenant_id AND p.id = pa.payment_id
        WHERE pa.tenant_id = %s AND pa.id = %s
        """,
        (tenant_id, allocation_id),
    )
    if not row:
        raise TransportError("This payment allocation no longer exists locally.")
    if row["payment_status"] not in ("succeeded", "refunded"):
        raise TransportError("Only succeeded payments are pushed.")
    existing = _link(conn, tenant_id, org_id, "payment", allocation_id)
    if existing:
        return {"xeroId": existing, "alreadyPushed": True}
    invoice_xero = _link(conn, tenant_id, org_id, "invoice", str(row["invoice_id"]))
    if not invoice_xero:
        raise DependencyPending("The paid invoice has not reached Xero yet.")
    mappings = _mappings(conn, tenant_id)
    bank = _account_for(mappings, "bank")
    payload = {
        "Payments": [{
            "Invoice": {"InvoiceID": invoice_xero},
            "Account": {"Code": str(bank["account_code"]).strip()},
            "Date": row["received_at"].date().isoformat() if row["received_at"] else None,
            "Amount": _money(int(row["amount_cents"])),
            "Reference": f"PWE payment {str(row['payment_id'])[:8]} ({row['method']})",
        }],
    }
    result = _api(conn, tenant_id, org_id, "PUT", "/Payments", payload)
    rows = result.get("Payments") or []
    if not rows or not rows[0].get("PaymentID"):
        raise TransportError("Xero's payment response carried no PaymentID.")
    xero_id = str(rows[0]["PaymentID"])
    _record_link(conn, tenant_id, org_id, "payment", allocation_id, "Payment", xero_id)
    return {"xeroId": xero_id, "amountCents": int(row["amount_cents"])}


# ── the drain ────────────────────────────────────────────────────────────


def push_job(conn, tenant_id: str, org_id: str, local_kind: str, local_id: str) -> dict[str, Any]:
    if local_kind == "invoice":
        return push_invoice(conn, tenant_id, org_id, local_id)
    if local_kind == "credit_note":
        return push_credit_note(conn, tenant_id, org_id, local_id)
    if local_kind == "payment":
        return push_payment(conn, tenant_id, org_id, local_id)
    raise TransportError(f"Unknown job kind: {local_kind}")


def drain(conn, tenant_id: str, *, limit: int = 25) -> dict[str, Any]:
    """Process due queued jobs for one tenant, dependency-ordered.

    Returns counts and per-job outcomes. Never raises for an individual
    job — each failure is recorded on its row, classified, and the drain
    moves on; the connection-level failure (no org) fails fast instead.
    """

    org_id = _org_id(conn, tenant_id)
    jobs = fetch_all(
        conn,
        """
        SELECT id, local_kind, local_id, attempts
        FROM integration_sync_jobs
        WHERE tenant_id = %s AND status = 'queued' AND next_attempt_at <= now()
        ORDER BY CASE local_kind
                     WHEN 'invoice' THEN 0
                     WHEN 'credit_note' THEN 1
                     WHEN 'payment' THEN 2
                     ELSE 3 END,
                 queued_at
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    outcomes: list[dict[str, Any]] = []
    sent = failed = deferred = 0
    for job in jobs:
        job_id = str(job["id"])
        attempts = int(job["attempts"]) + 1
        try:
            result = push_job(conn, tenant_id, org_id, job["local_kind"], str(job["local_id"]))
        except TransportError as exc:
            if exc.retryable and attempts < MAX_ATTEMPTS:
                # Exponential backoff written into the row: 1, 2, 4 … minutes.
                delay_minutes = min(2 ** (attempts - 1), 60)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE integration_sync_jobs
                           SET attempts = %s, last_attempt_at = now(),
                               next_attempt_at = now() + %s * interval '1 minute',
                               last_error = %s
                         WHERE tenant_id = %s AND id = %s
                        """,
                        (attempts, delay_minutes, str(exc)[:500], tenant_id, job_id),
                    )
                deferred += 1
                outcomes.append({"id": job_id, "kind": job["local_kind"], "outcome": "deferred", "error": str(exc)})
            else:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE integration_sync_jobs
                           SET status = 'failed', attempts = %s,
                               last_attempt_at = now(), last_error = %s
                         WHERE tenant_id = %s AND id = %s
                        """,
                        (attempts, str(exc)[:500], tenant_id, job_id),
                    )
                failed += 1
                outcomes.append({"id": job_id, "kind": job["local_kind"], "outcome": "failed", "error": str(exc)})
            continue
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE integration_sync_jobs
                   SET status = 'sent', attempts = %s, last_error = '',
                       last_attempt_at = now(), completed_at = now()
                 WHERE tenant_id = %s AND id = %s
                """,
                (attempts, tenant_id, job_id),
            )
            cur.execute(
                """
                INSERT INTO xero_sync_settings (tenant_id, last_pushed_at)
                VALUES (%s, now())
                ON CONFLICT (tenant_id) DO UPDATE
                   SET last_pushed_at = now(), updated_at = now()
                """,
                (tenant_id,),
            )
        sent += 1
        outcomes.append({"id": job_id, "kind": job["local_kind"], "outcome": "sent", **{
            k: v for k, v in result.items() if k in ("xeroId", "number")
        }})
    return {"processed": len(jobs), "sent": sent, "failed": failed, "deferred": deferred, "jobs": outcomes}


# ── backfill ─────────────────────────────────────────────────────────────


def backfill(conn, tenant_id: str) -> dict[str, int]:
    """Queue every issued document the CURRENT org has never received.

    Deliberately ignores the push switch: the wizard's demo run needs the
    backlog pushed *before* the switch may legally be turned on, and a
    studio that pauses for year-end uses the same path to catch up after.
    The idempotency key carries the org id, so reconnecting to a different
    organisation queues everything again — for that ledger, it IS new.
    """

    org_id = _org_id(conn, tenant_id)

    def _insert(cur, kind: str, local_id: str) -> int:
        key = _xero.idempotency_key(tenant_id, kind, str(local_id), org_id)
        cur.execute(
            """
            INSERT INTO integration_sync_jobs
                (tenant_id, integration, local_kind, local_id, idempotency_key)
            VALUES (%s, 'xero', %s, %s, %s)
            ON CONFLICT (tenant_id, integration, idempotency_key) DO NOTHING
            RETURNING id
            """,
            (tenant_id, kind, local_id, key),
        )
        return 1 if cur.fetchone() else 0

    counts = {"invoice": 0, "credit_note": 0, "payment": 0}
    invoices = fetch_all(
        conn,
        """
        SELECT i.id FROM invoices i
        LEFT JOIN xero_object_links l
          ON l.tenant_id = i.tenant_id AND l.local_kind = 'invoice'
         AND l.local_id = i.id AND l.org_id = %s
        WHERE i.tenant_id = %s AND i.status IN ('issued', 'part_paid', 'paid')
          AND l.local_id IS NULL
        ORDER BY i.issue_date, i.number
        """,
        (org_id, tenant_id),
    )
    notes = fetch_all(
        conn,
        """
        SELECT n.id FROM credit_notes n
        LEFT JOIN xero_object_links l
          ON l.tenant_id = n.tenant_id AND l.local_kind = 'credit_note'
         AND l.local_id = n.id AND l.org_id = %s
        WHERE n.tenant_id = %s AND n.status = 'issued' AND l.local_id IS NULL
        ORDER BY n.issue_date, n.number
        """,
        (org_id, tenant_id),
    )
    allocations = fetch_all(
        conn,
        """
        SELECT pa.id FROM payment_allocations pa
        JOIN payments p ON p.tenant_id = pa.tenant_id AND p.id = pa.payment_id
        JOIN invoices i ON i.tenant_id = pa.tenant_id AND i.id = pa.invoice_id
        LEFT JOIN xero_object_links l
          ON l.tenant_id = pa.tenant_id AND l.local_kind = 'payment'
         AND l.local_id = pa.id AND l.org_id = %s
        WHERE pa.tenant_id = %s AND p.status IN ('succeeded', 'refunded')
          AND i.status IN ('issued', 'part_paid', 'paid')
          AND l.local_id IS NULL
        ORDER BY p.received_at
        """,
        (org_id, tenant_id),
    )
    with conn.cursor() as cur:
        for row in invoices:
            counts["invoice"] += _insert(cur, "invoice", str(row["id"]))
        for row in notes:
            counts["credit_note"] += _insert(cur, "credit_note", str(row["id"]))
        for row in allocations:
            counts["payment"] += _insert(cur, "payment", str(row["id"]))
    counts["total"] = sum(counts.values())
    return counts


# ── reconciliation ───────────────────────────────────────────────────────


def reconcile(conn, tenant_id: str) -> dict[str, Any]:
    """Read every pushed document back and compare the numbers that matter.

    The X3 exit criterion is zero difference. Anything listed here is a bug
    in the transport or a hand-edit in the ledger — both are things the
    studio must see, not things a summary should average away.
    """

    org_id = _org_id(conn, tenant_id)
    links = fetch_all(
        conn,
        """
        SELECT local_kind, local_id, xero_id FROM xero_object_links
        WHERE tenant_id = %s AND org_id = %s AND local_kind IN ('invoice', 'credit_note', 'payment')
        ORDER BY local_kind, pushed_at
        """,
        (tenant_id, org_id),
    )
    diffs: list[dict[str, Any]] = []
    checked = 0
    for link in links:
        kind, local_id, xero_id = link["local_kind"], str(link["local_id"]), link["xero_id"]
        try:
            if kind == "invoice":
                local = fetch_one(
                    conn,
                    "SELECT number, status, total_cents FROM invoices WHERE tenant_id = %s AND id = %s",
                    (tenant_id, local_id),
                )
                remote = (_api(conn, tenant_id, org_id, "GET", f"/Invoices/{xero_id}").get("Invoices") or [{}])[0]
                _compare(diffs, kind, local["number"], "total",
                         _money(int(local["total_cents"])), float(remote.get("Total") or 0))
                if local["status"] == "void" and str(remote.get("Status")) != "VOIDED":
                    diffs.append({"kind": kind, "number": local["number"], "field": "status",
                                  "local": "void", "xero": str(remote.get("Status"))})
            elif kind == "credit_note":
                local = fetch_one(
                    conn,
                    "SELECT number, total_cents FROM credit_notes WHERE tenant_id = %s AND id = %s",
                    (tenant_id, local_id),
                )
                remote = (_api(conn, tenant_id, org_id, "GET", f"/CreditNotes/{xero_id}").get("CreditNotes") or [{}])[0]
                _compare(diffs, kind, local["number"], "total",
                         _money(int(local["total_cents"])), float(remote.get("Total") or 0))
            else:
                local = fetch_one(
                    conn,
                    "SELECT amount_cents FROM payment_allocations WHERE tenant_id = %s AND id = %s",
                    (tenant_id, local_id),
                )
                remote = (_api(conn, tenant_id, org_id, "GET", f"/Payments/{xero_id}").get("Payments") or [{}])[0]
                _compare(diffs, kind, xero_id[:8], "amount",
                         _money(int(local["amount_cents"])), float(remote.get("Amount") or 0))
            checked += 1
        except TransportError as exc:
            diffs.append({"kind": kind, "number": local_id[:8], "field": "fetch",
                          "local": "exists", "xero": str(exc)[:200]})
    return {"checked": checked, "diffCount": len(diffs), "diffs": diffs}


def _compare(diffs: list, kind: str, number: Any, field: str, local: float, remote: float) -> None:
    if abs(local - remote) >= 0.005:
        diffs.append({"kind": kind, "number": number, "field": field,
                      "local": local, "xero": remote})


# ── the wizard's demo run ────────────────────────────────────────────────


def run_demo_cycle(conn, tenant_id: str) -> dict[str, Any]:
    """Backfill → drain → reconcile, as one reportable act.

    This is what 「测试组织试跑」actually does now. The caller records the
    demo run as completed only when at least one document went across AND
    the reconciliation shows zero difference — a run that pushed nothing
    proves nothing.
    """

    queued = backfill(conn, tenant_id)
    first = drain(conn, tenant_id, limit=50)
    # Payments defer until their invoice's link exists; one immediate second
    # pass clears those without waiting a scheduler tick.
    second = drain(conn, tenant_id, limit=50) if first["deferred"] else {
        "processed": 0, "sent": 0, "failed": 0, "deferred": 0, "jobs": []}
    report = reconcile(conn, tenant_id)
    sent = first["sent"] + second["sent"]
    clean = sent > 0 and report["diffCount"] == 0 and \
        first["failed"] + second["failed"] + second["deferred"] == 0
    return {
        "queued": queued,
        "pushed": sent,
        "failed": first["failed"] + second["failed"],
        "deferred": second["deferred"],
        "jobs": first["jobs"] + second["jobs"],
        "reconciliation": report,
        "clean": clean,
    }
