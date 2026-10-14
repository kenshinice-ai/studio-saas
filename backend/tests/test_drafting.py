"""Claude drafting: the request, the reply, and the check against the facts.

No test here calls the real API. A fake client stands in for
``anthropic.Anthropic`` so the error paths can be exercised on purpose.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.services import drafting  # noqa: E402

FACTS = {
    "studio": "Harbour Art Studio",
    "payer_name": "Mei",
    "invoice_number": "INV-0042",
    "amount_outstanding_aud": "180.00",
    "due_date": "2026-09-30",
    "days_overdue": 14,
    "how_to_pay": {"bsb": "062-000", "account_number": "12345678"},
}


# ── the request ──────────────────────────────────────────────────────────

def test_the_request_carries_the_facts_and_nothing_else_about_the_family():
    request = drafting.build_request(drafting.OVERDUE_INVOICE, FACTS, voice="Friendly.", language="en")
    payload = json.loads(request["user"])

    assert payload["facts"] == FACTS
    assert payload["language"] == "English"
    assert request["system"] == drafting.SYSTEM_PROMPT


def test_the_same_facts_make_the_same_bytes():
    """Stable bytes keep the cache warm and the evaluation reproducible."""

    reordered = dict(reversed(list(FACTS.items())))
    a = drafting.build_request(drafting.OVERDUE_INVOICE, FACTS, voice="", language="zh")
    b = drafting.build_request(drafting.OVERDUE_INVOICE, reordered, voice="", language="zh")

    assert a == b


def test_the_system_prompt_does_not_change_per_request():
    """Anything per-request in the system prompt would defeat the cache."""

    first = drafting.build_request(drafting.LOW_CREDITS, {"studio": "A"}, voice="x", language="en")
    second = drafting.build_request(drafting.MISSED_LESSONS, {"studio": "B"}, voice="y", language="zh")

    assert first["system"] == second["system"]


@pytest.mark.parametrize("kind", drafting.KINDS)
def test_every_kind_has_a_brief(kind):
    assert drafting.KIND_BRIEFS[kind]


def test_unknown_kind_and_language_are_refused():
    with pytest.raises(drafting.DraftingError):
        drafting.build_request("poem", {}, voice="", language="en")
    with pytest.raises(drafting.DraftingError):
        drafting.build_request(drafting.LOW_CREDITS, {}, voice="", language="fr")


# ── the reply ────────────────────────────────────────────────────────────

def test_a_reply_becomes_a_draft():
    draft = drafting.parse_reply(
        json.dumps({"subject": " Invoice ", "body": " Hi Mei ", "missing": ["payment link", ""]}),
        model="m",
    )

    assert (draft.subject, draft.body, draft.missing) == ("Invoice", "Hi Mei", ["payment link"])


@pytest.mark.parametrize("text", ["not json", "[]", json.dumps({"subject": "x", "body": "  ", "missing": []})])
def test_a_malformed_or_empty_reply_is_refused(text):
    with pytest.raises(drafting.DraftingError) as caught:
        drafting.parse_reply(text, model="m")
    assert caught.value.code == "bad_reply"


# ── checking the figures ─────────────────────────────────────────────────

def test_figures_from_the_facts_pass_in_their_usual_forms():
    body = "Invoice INV-0042 for $180.00 was due on 30/09/2026 (14 days ago). BSB 062-000, account 12345678."

    assert drafting.unbacked_figures(body, FACTS) == []


def test_an_invented_amount_or_date_is_flagged():
    body = "Please pay $200 by 15/10/2026."

    assert set(drafting.unbacked_figures(body, FACTS)) == {"200", "15/10/2026"}


def test_chinese_dates_from_the_facts_pass():
    assert drafting.unbacked_figures("发票已于9月30日到期。", FACTS) == []


# ── the call ─────────────────────────────────────────────────────────────

class _FakeMessages:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = []

    def create(self, **params):
        self.calls.append(params)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def _client(outcome):
    messages = _FakeMessages(outcome)
    return SimpleNamespace(messages=messages, beta=SimpleNamespace(messages=messages)), messages


def _response(body="Hi", stop_reason="end_turn"):
    text = json.dumps({"subject": "", "body": body, "missing": []})
    return SimpleNamespace(
        stop_reason=stop_reason,
        model="claude-haiku-5-5",
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=900, output_tokens=120, cache_read_input_tokens=600),
    )


def test_a_call_returns_the_draft_and_its_token_counts():
    client, messages = _client(_response("Hi Mei"))
    request = drafting.build_request(drafting.OVERDUE_INVOICE, FACTS, voice="", language="en")

    draft = drafting.call_model(client, request, model="claude-haiku-5-5")

    assert draft.body == "Hi Mei"
    assert (draft.input_tokens, draft.output_tokens, draft.cache_read_tokens) == (900, 120, 600)
    params = messages.calls[0]
    assert params["output_config"]["format"]["schema"] == drafting.OUTPUT_SCHEMA
    assert params["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert "fallbacks" not in params, "Haiku takes no server-side fallback"


def test_opus_and_sonnet_ask_for_the_server_side_fallback():
    client, messages = _client(_response())
    request = drafting.build_request(drafting.LOW_CREDITS, {"studio": "A"}, voice="", language="en")

    drafting.call_model(client, request, model="claude-sonnet-5-5")

    assert messages.calls[0]["fallbacks"] == "default"
    assert messages.calls[0]["betas"] == ["server-side-fallback-2026-07-01"]


@pytest.mark.parametrize("stop_reason, code", [("refusal", "declined"), ("max_tokens", "too_long")])
def test_a_refusal_or_a_cut_off_is_explained(stop_reason, code):
    client, _ = _client(_response(stop_reason=stop_reason))
    request = drafting.build_request(drafting.LOW_CREDITS, {"studio": "A"}, voice="", language="en")

    with pytest.raises(drafting.DraftingError) as caught:
        drafting.call_model(client, request, model="claude-haiku-5-5")
    assert caught.value.code == code


def test_api_errors_become_reasons_staff_can_read():
    anthropic = pytest.importorskip("anthropic")
    import httpx2

    request_obj = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    cases = [
        (anthropic.RateLimitError("slow down", response=httpx2.Response(429, request=request_obj), body=None), "busy"),
        (anthropic.APIConnectionError(request=request_obj), "unreachable"),
        (anthropic.InternalServerError("boom", response=httpx2.Response(500, request=request_obj), body=None), "service_error"),
    ]
    request = drafting.build_request(drafting.LOW_CREDITS, {"studio": "A"}, voice="", language="en")
    for error, code in cases:
        client, _ = _client(error)
        with pytest.raises(drafting.DraftingError) as caught:
            drafting.call_model(client, request, model="claude-haiku-5-5")
        assert caught.value.code == code


def test_the_cost_estimate_uses_the_price_list():
    draft = drafting.Draft(subject="", body="x", missing=[], model="claude-opus-5-5",
                           input_tokens=1500, output_tokens=300)

    assert drafting.estimated_cost_micros(draft) == 12_000  # US$0.012


def test_a_24_hour_time_may_be_written_the_12_hour_way():
    """Evaluation 2026-10-14: every flagged figure in 720 drafts was this."""

    facts = {"start_time": "16:30", "other": "18:00"}
    assert drafting.unbacked_figures("Class at 4:30 pm, or 4.30pm, then 6pm or 6:00 pm.", facts) == []
    assert drafting.unbacked_figures("Class at 5:30 pm.", facts) == ["5:30"]


def test_chinese_times_pass_and_a_worked_out_date_does_not():
    """Evaluation 2026-10-14, booking replies: "下午4点30分" is 16:30; a date the
    model worked out itself ("the Saturday of that week") is not in the facts
    and must be checked by a person."""

    facts = {"class_date": "2026-10-14", "start_time": "16:30"}
    assert drafting.unbacked_figures("10月14日下午4点30分上课。", facts) == []
    assert drafting.unbacked_figures("可以改约周六（10月17日）。", facts) == ["17"]
