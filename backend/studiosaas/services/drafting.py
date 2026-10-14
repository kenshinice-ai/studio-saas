"""Claude drafts a message; a person reads it, edits it and sends it.

Lee, 2026-10-14: "只起草，人确认后再发". The plan is
docs/design/Claude_Drafting_Plan_2026-10-14.md. Three rules shape this module:

* **Claude never sends anything and never changes a record.** It returns
  text. Sending is the staff member's own act, from their own mail or SMS app.
* **Claude sees only the facts the message needs.** A first name, the numbers
  and dates the message is about, the studio's name and its own voice notes.
  Never a phone number, an email, an address or another student.
* **Nothing it may not know.** The prompt allows only the facts given; the
  reply has a ``missing`` list for anything it needed and did not get; and
  :func:`unbacked_figures` flags every number or date in the draft that does
  not appear in the facts, so the screen can show it next to the send button.

The prompt builders are pure functions of (kind, facts, voice, language). The
evaluation script calls the same functions with synthetic facts, so what is
evaluated is what ships.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from ..db import fetch_all, fetch_one

# ── kinds ────────────────────────────────────────────────────────────────

REPORT_COMMENT = "report_comment"
LOW_CREDITS = "low_credits"
MISSED_LESSONS = "missed_lessons"
OVERDUE_INVOICE = "overdue_invoice"
EXPIRING_MAKEUP = "expiring_makeup"
BOOKING_REPLY = "booking_reply"

KINDS = (REPORT_COMMENT, LOW_CREDITS, MISSED_LESSONS, OVERDUE_INVOICE, EXPIRING_MAKEUP, BOOKING_REPLY)

#: One line per kind: what the message is for. The general rules sit in
#: SYSTEM_PROMPT and are identical for every request, so they can be cached.
KIND_BRIEFS: dict[str, str] = {
    REPORT_COMMENT: (
        "Write the teacher's comment for a progress report, addressed to the family. "
        "One or two short paragraphs. Say what the student did and practised in this "
        "period, using the lesson notes; end with one concrete thing to work on next. "
        "No subject line."
    ),
    LOW_CREDITS: (
        "Tell the family the student has only a few lessons left on their balance and "
        "invite them to top up. Mention the packages only if they are given."
    ),
    MISSED_LESSONS: (
        "The student has missed several scheduled lessons in a row. Write a warm "
        "check-in that asks whether everything is all right and whether the current "
        "time still suits. Do not scold, do not mention money."
    ),
    OVERDUE_INVOICE: (
        "A polite reminder that an invoice is past its due date. Give the invoice "
        "number, the amount outstanding and how to pay, if given. Offer to help if "
        "there is a problem. No threats, no late fees."
    ),
    EXPIRING_MAKEUP: (
        "The student has a make-up lesson owed that expires soon. Invite the family "
        "to choose a time before it expires. Do not offer specific times unless they "
        "are given."
    ),
    BOOKING_REPLY: (
        "Reply to a family who asked for a place in a class on the public timetable. "
        "The decision field says what the studio decided: 'approved', 'declined' or "
        "'question'. For declined, be kind and mention other times only if given."
    ),
}

SYSTEM_PROMPT = """You draft short messages that staff at a small studio send to the families of their students. A staff member will read and edit your draft before anyone sees it.

Rules:
- Use only the facts in the request. Never invent a name, number, date, price, time, policy or promise.
- If the message needs a fact you were not given, put a short placeholder in square brackets in the text, such as [payment details], and list that fact in "missing".
- Never offer discounts, refunds, credits or exceptions.
- Write in the language the request asks for. Chinese: natural, polite written Chinese. English: plain Australian English.
- Sound like the studio, using its voice notes if given. Warm and brief: a message is at most about 120 English words or 200 Chinese characters.
- Address the family as the facts say. If no parent name is given, address the family of the student by the student's first name.
- Never guess a student's gender from their name: repeat the first name, or use "they" in English and "孩子" in Chinese.
- End with the studio's signature if given, otherwise the studio's name.
- Plain text only: no markdown, no emoji, no mention of AI.

Answer with JSON: "subject" (an email subject line, or "" when none fits), "body" (the message), "missing" (a list of facts you needed and did not have, or [])."""

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "subject": {"type": "string"},
        "body": {"type": "string"},
        "missing": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["subject", "body", "missing"],
    "additionalProperties": False,
}

LANGUAGES = ("zh", "en")


class DraftingError(RuntimeError):
    """A draft could not be produced. ``code`` is shown to staff as a reason."""

    def __init__(self, code: str, message: str = ""):
        super().__init__(message or code)
        self.code = code


class RecordNotFound(DraftingError):
    def __init__(self):
        super().__init__("not_found", "That record does not exist.")


# ── the request ──────────────────────────────────────────────────────────

def build_request(kind: str, facts: dict[str, Any], *, voice: str, language: str) -> dict[str, Any]:
    """The system prompt and user message for one draft. Pure; no I/O."""

    if kind not in KIND_BRIEFS:
        raise DraftingError("unknown_kind", f"Unknown draft kind: {kind}")
    if language not in LANGUAGES:
        raise DraftingError("unknown_language", f"Unknown language: {language}")
    payload = {
        "task": KIND_BRIEFS[kind],
        "language": "Chinese" if language == "zh" else "English",
        "studio_voice": voice or "",
        "facts": facts,
    }
    return {
        "system": SYSTEM_PROMPT,
        # sort_keys keeps identical facts byte-identical, which keeps the
        # cached prefix and the evaluation reproducible.
        "user": json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
    }


@dataclass
class Draft:
    subject: str
    body: str
    missing: list[str]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    unbacked: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "subject": self.subject, "body": self.body, "missing": self.missing,
            "unbacked": self.unbacked, "model": self.model,
        }


def parse_reply(text: str, *, model: str) -> Draft:
    """Turn the model's JSON text into a Draft, refusing anything malformed."""

    try:
        data = json.loads(text)
    except (TypeError, ValueError) as exc:
        raise DraftingError("bad_reply", "The draft came back in an unexpected shape.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("body"), str) or not data["body"].strip():
        raise DraftingError("bad_reply", "The draft came back empty.")
    missing = data.get("missing") if isinstance(data.get("missing"), list) else []
    return Draft(
        subject=str(data.get("subject") or "").strip(),
        body=data["body"].strip(),
        missing=[str(item) for item in missing if str(item).strip()],
        model=model,
    )


# ── checking the draft against the facts ─────────────────────────────────

_FIGURE = re.compile(r"\d[\d,.:/-]*\d|\d")


def _figures(text: str) -> set[str]:
    return {match.group(0).rstrip(".,") for match in _FIGURE.finditer(text)}


def _fact_strings(value: Any) -> set[str]:
    out: set[str] = set()
    if isinstance(value, dict):
        for item in value.values():
            out |= _fact_strings(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            out |= _fact_strings(item)
    elif value is not None:
        out.add(str(value))
    return out


def _variants(fact: str) -> set[str]:
    """Ways a fact can legitimately appear in prose."""

    forms = {fact}
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", fact):
        y, m, d = fact.split("-")
        forms |= {f"{d}/{m}/{y}", f"{int(d)}/{int(m)}/{y}", f"{d}/{m}", f"{int(d)}/{int(m)}",
                  f"{int(m)}月{int(d)}日", str(int(d)), str(int(m)), y}
    if re.fullmatch(r"-?\d+(\.\d+)?", fact):
        number = float(fact)
        forms |= {f"{number:,.2f}", f"{number:.2f}", f"{number:,.0f}", f"{number:.0f}"}
        if number == int(number):
            forms.add(str(int(number)))
    return forms


def unbacked_figures(body: str, facts: dict[str, Any]) -> list[str]:
    """Numbers and dates in the draft that the facts do not contain.

    Deliberately strict: a false alarm costs the staff member a glance, a
    missed invented amount costs the studio a family's trust.
    """

    known: set[str] = set()
    for fact in _fact_strings(facts):
        for form in _variants(fact):
            known |= _figures(form) | {form}
    # Small counting words ("1 more", "2 lessons") are part of language, not facts.
    return sorted(figure for figure in _figures(body) if figure not in known and figure not in {"1", "2"})


# ── the call ─────────────────────────────────────────────────────────────

#: Models that take the server-side refusal fallback (Claude API docs, 2026-10).
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}


def request_params(request: dict[str, Any], *, model: str, effort: str = "low",
                   max_tokens: int = 4000, cache: bool = True) -> dict[str, Any]:
    """Messages API parameters for one draft, shared by the live call and the
    evaluation's batches. ``cache=False`` drops the breakpoint: inside a batch
    requests cannot read each other's cache, so a breakpoint only pays for writes."""

    system: dict[str, Any] = {"type": "text", "text": request["system"]}
    if cache:
        system["cache_control"] = {"type": "ephemeral"}
    return {
        "model": model,
        "max_tokens": max_tokens,
        "system": [system],
        "messages": [{"role": "user", "content": request["user"]}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA}},
    }


def draft_from_message(message, *, model: str) -> Draft:
    """Turn a Messages API response (live or from a batch) into a Draft."""

    if message.stop_reason == "refusal":
        raise DraftingError("declined", "This one could not be drafted. Please write it yourself.")
    if message.stop_reason == "max_tokens":
        raise DraftingError("too_long", "The draft ran too long.")
    text = next((block.text for block in message.content if block.type == "text"), "")
    draft = parse_reply(text, model=getattr(message, "model", None) or model)
    usage = message.usage
    draft.input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    draft.output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    draft.cache_read_tokens = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    return draft


def call_model(client, request: dict[str, Any], *, model: str, effort: str = "low",
               max_tokens: int = 4000) -> Draft:
    """Ask Claude for one draft. ``client`` is an ``anthropic.Anthropic``.

    Errors become :class:`DraftingError` with a code the screen can explain;
    the caller decides what to log. Retries are the SDK's own (two by default).
    """

    import anthropic

    params = request_params(request, model=model, effort=effort, max_tokens=max_tokens)
    try:
        if model in _FALLBACK_MODELS:
            response = client.beta.messages.create(
                betas=["server-side-fallback-2026-07-01"], fallbacks="default", **params,
            )
        else:
            response = client.messages.create(**params)
    except anthropic.RateLimitError as exc:
        raise DraftingError("busy", "Too many drafts at once. Try again in a minute.") from exc
    except anthropic.APITimeoutError as exc:
        raise DraftingError("timeout", "The draft took too long.") from exc
    except anthropic.APIConnectionError as exc:
        raise DraftingError("unreachable", "The drafting service could not be reached.") from exc
    except anthropic.APIStatusError as exc:
        # A spent credit balance arrives here too; the screen says to write by hand.
        raise DraftingError("service_error", f"The drafting service answered {exc.status_code}.") from exc
    return draft_from_message(response, model=model)


#: US dollars per million tokens (input, output, cache-read multiplier). Prices
#: from the Claude API price list cached 2026-10-06; cache-read multipliers as
#: checked by the API planning session 2026-10-11. Only used to log an
#: estimate; the invoice from Anthropic is the truth.
PRICES = {
    "claude-opus-5-5": (4.00, 20.00, 0.05),
    "claude-sonnet-5-5": (2.00, 10.00, 0.05),
    "claude-haiku-5-5": (0.10, 0.50, 0.10),
}


def estimated_cost_micros(draft: Draft, *, batch: bool = False) -> int:
    """Estimated cost in millionths of a US dollar. Batches cost half."""

    rate_in, rate_out, cache_read = PRICES.get(draft.model, PRICES["claude-opus-5-5"])
    dollars = (max(0, draft.input_tokens) * rate_in
               + draft.cache_read_tokens * rate_in * cache_read
               + draft.output_tokens * rate_out) / 1_000_000
    if batch:
        dollars /= 2
    return round(dollars * 1_000_000)


# ── facts from the database ──────────────────────────────────────────────

def _first_name(row: dict[str, Any]) -> str:
    return (row.get("first_name") or (row.get("display_name") or "").split(" ")[0] or "").strip()


def _studio(conn, tenant_id: str) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        SELECT t.name, COALESCE(NULLIF(bi.trading_name, ''), t.name) AS trading_name,
               bi.bank_account_name, bi.bank_bsb, bi.bank_account_no, bi.payment_note
        FROM tenants t
        LEFT JOIN tenant_billing_identity bi ON bi.tenant_id = t.id
        WHERE t.id = %s
        """,
        (tenant_id,),
    ) or {}
    return row


def _student(conn, tenant_id: str, student_id: str) -> dict[str, Any]:
    row = fetch_one(
        conn,
        """
        SELECT s.id, s.first_name, s.display_name, s.parent_name, s.mobile, s.email,
               COALESCE(ca.balance, 0)::float AS balance
        FROM students s
        LEFT JOIN credit_accounts ca
          ON ca.tenant_id = s.tenant_id AND ca.student_id = s.id AND ca.course_id IS NULL
        WHERE s.tenant_id = %s AND s.id = %s
        """,
        (tenant_id, student_id),
    )
    if not row:
        raise RecordNotFound()
    return row


def _last_attended(conn, tenant_id: str, student_id: str) -> str | None:
    row = fetch_one(
        conn,
        """
        SELECT max(COALESCE(class_date, attended_at::date)) AS last
        FROM attendance_sessions
        WHERE tenant_id = %s AND student_id = %s AND reversed_at IS NULL
        """,
        (tenant_id, student_id),
    )
    return row["last"].isoformat() if row and row["last"] else None


@dataclass
class Gathered:
    """What one draft is built from, and who it would go to.

    ``facts`` go to Claude. ``recipient`` never does: it only fills the
    mailto:/sms: link on the staff member's screen.
    """

    facts: dict[str, Any]
    recipient: dict[str, str]


def gather(conn, tenant_id: str, kind: str, record_id: str, *, today: date,
           decision: str = "") -> Gathered:
    """Read the facts for one draft, under the caller's tenant binding."""

    studio = _studio(conn, tenant_id)
    base = {"studio": studio.get("trading_name") or studio.get("name") or ""}

    if kind in (LOW_CREDITS, MISSED_LESSONS, EXPIRING_MAKEUP):
        if kind == EXPIRING_MAKEUP:
            credit = fetch_one(
                conn,
                """
                SELECT student_id, to_char(expires_on, 'YYYY-MM-DD') AS expires_on,
                       to_char(earned_from_date, 'YYYY-MM-DD') AS missed_on
                FROM makeup_credits
                WHERE tenant_id = %s AND id = %s AND status = 'available'
                """,
                (tenant_id, record_id),
            )
            if not credit:
                raise RecordNotFound()
            student = _student(conn, tenant_id, str(credit["student_id"]))
        else:
            credit = None
            student = _student(conn, tenant_id, record_id)
        facts = {
            **base,
            "student_first_name": _first_name(student),
            "parent_name": student.get("parent_name") or "",
            "last_attended": _last_attended(conn, tenant_id, str(student["id"])),
        }
        if kind == LOW_CREDITS:
            facts["lessons_left"] = student["balance"]
            facts["packages"] = [
                {"name": row["name"], "lessons": row["credits"],
                 "price_aud": f"{int(row['price_aud_cents']) / 100:.2f}"}
                for row in fetch_all(
                    conn,
                    "SELECT name, credits, price_aud_cents FROM packages "
                    "WHERE tenant_id = %s AND is_active ORDER BY credits LIMIT 4",
                    (tenant_id,),
                )
            ]
        elif kind == MISSED_LESSONS:
            from .missed_lessons import missed_streaks

            row = next((r for r in missed_streaks(conn, tenant_id, today=today, streak=1)
                        if r["studentId"] == str(student["id"])), None)
            facts["missed_in_a_row"] = row["missed"] if row else 0
        else:
            facts["makeup_expires_on"] = credit["expires_on"]
            facts["missed_lesson_on"] = credit["missed_on"]
        return Gathered(facts, {"email": student.get("email") or "", "mobile": student.get("mobile") or ""})

    if kind == OVERDUE_INVOICE:
        invoice = fetch_one(
            conn,
            """
            SELECT i.number, i.total_cents, i.balance_cents, i.currency,
                   to_char(i.due_date, 'YYYY-MM-DD') AS due_date,
                   ba.name AS payer, ba.contact_name, ba.email, ba.mobile
            FROM invoices i
            JOIN billing_accounts ba ON ba.tenant_id = i.tenant_id AND ba.id = i.billing_account_id
            WHERE i.tenant_id = %s AND i.id = %s AND i.status NOT IN ('draft', 'void')
            """,
            (tenant_id, record_id),
        )
        if not invoice:
            raise RecordNotFound()
        how_to_pay = {}
        if studio.get("bank_account_no"):
            how_to_pay = {"account_name": studio.get("bank_account_name") or "",
                          "bsb": studio.get("bank_bsb") or "",
                          "account_number": studio.get("bank_account_no") or ""}
        if studio.get("payment_note"):
            how_to_pay["note"] = studio["payment_note"]
        facts = {
            **base,
            "payer_name": invoice["contact_name"] or invoice["payer"] or "",
            "invoice_number": invoice["number"] or "",
            "amount_outstanding_aud": f"{int(invoice['balance_cents']) / 100:.2f}",
            "invoice_total_aud": f"{int(invoice['total_cents']) / 100:.2f}",
            "due_date": invoice["due_date"],
            "days_overdue": (today - date.fromisoformat(invoice["due_date"])).days if invoice["due_date"] else None,
            "how_to_pay": how_to_pay,
        }
        return Gathered(facts, {"email": invoice["email"] or "", "mobile": invoice["mobile"] or ""})

    if kind == BOOKING_REPLY:
        booking = fetch_one(
            conn,
            """
            SELECT b.contact_name, b.contact_phone, to_char(b.on_date, 'YYYY-MM-DD') AS on_date,
                   to_char(cs.start_time, 'HH24:MI') AS start_time,
                   COALESCE(c.name, cs.label) AS class_name
            FROM class_bookings b
            JOIN class_schedules cs ON cs.id = b.schedule_id
            LEFT JOIN courses c ON c.id = cs.course_id
            WHERE b.tenant_id = %s AND b.id = %s
            """,
            (tenant_id, record_id),
        )
        if not booking:
            raise RecordNotFound()
        if decision not in ("approved", "declined", "question"):
            raise DraftingError("needs_decision", "Say whether the request is approved, declined or a question.")
        facts = {
            **base,
            "contact_name": (booking["contact_name"] or "").split(" ")[0],
            "class_name": booking["class_name"] or "",
            "class_date": booking["on_date"],
            "start_time": booking["start_time"],
            "decision": decision,
        }
        return Gathered(facts, {"email": "", "mobile": booking["contact_phone"] or ""})

    if kind == REPORT_COMMENT:
        report = fetch_one(
            conn,
            """
            SELECT r.student_id, r.content, to_char(r.period_start, 'YYYY-MM-DD') AS period_start,
                   to_char(r.period_end, 'YYYY-MM-DD') AS period_end
            FROM progress_reports r
            WHERE r.tenant_id = %s AND r.id = %s
            """,
            (tenant_id, record_id),
        )
        if not report:
            raise RecordNotFound()
        student = _student(conn, tenant_id, str(report["student_id"]))
        content = report["content"] or {}
        facts = {
            **base,
            "student_first_name": _first_name(student),
            "period_start": report["period_start"],
            "period_end": report["period_end"],
            "attendance": content.get("attendance"),
            # Notes are the teacher's own words about each lesson; cap them so
            # a busy term cannot turn into a very long, very expensive prompt.
            "lesson_notes": [
                {"date": item.get("class_date"), "course": item.get("course_name"), "note": (item.get("note") or "")[:400]}
                for item in (content.get("lessons") or [])[-20:]
            ],
            "works": [item.get("title") for item in (content.get("media") or []) if item.get("title")],
        }
        return Gathered(facts, {"email": "", "mobile": ""})

    raise DraftingError("unknown_kind", f"Unknown draft kind: {kind}")
