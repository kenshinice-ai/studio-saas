#!/usr/bin/env python3
"""Evaluate Claude drafting on synthetic records, before any model is chosen.

Lee, 2026-10-14: "先评测". The plan is docs/design/Claude_Drafting_Plan_2026-10-14.md.

Every record is synthetic: invented first names, invented studios, invented
amounts. No tenant, family or student data is read or sent.

What is measured, per model:

* **Scripted checks** (every draft): an amount or date that is not in the
  facts; the wrong language; too long; a forbidden promise (discount, refund,
  free lesson); a fact that was missing on purpose and was neither listed in
  ``missing`` nor left as a [placeholder].
* **Tone** (a sample): Claude Opus 5.5 grades each sampled draft 1-5 against a
  short rubric. The grader never sees which model wrote the draft.

Usage (from backend/):

    ../.venv/bin/python scripts/eval_drafting.py --dry-run
    ../.venv/bin/python scripts/eval_drafting.py --models claude-haiku-5-5 --per-kind 5 --max-usd 1
    ../.venv/bin/python scripts/eval_drafting.py --max-usd 15

The key comes from the environment the API session names; this script never
prints it or writes it anywhere. Results go to outputs/drafting-eval-<stamp>/,
which git ignores.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.services import drafting  # noqa: E402

MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
GRADER = "claude-opus-5-5"
TODAY = date(2026, 10, 14)

FIRST_EN = ["Ava", "Leo", "Mia", "Noah", "Isla", "Jack", "Ruby", "Oscar", "Zoe", "Liam"]
FIRST_ZH = ["小雨", "子轩", "欣怡", "浩然", "思琪", "一鸣", "若曦", "俊杰", "雨桐", "梓涵"]
PARENT_EN = ["Ms Chen", "Mr Patel", "Sarah", "", "Mrs Nguyen", ""]
PARENT_ZH = ["陈女士", "王先生", "李妈妈", "", "张爸爸", ""]
STUDIOS = ["Harbour Art Studio", "Brightkeys Piano", "Moonlight Dance", "青禾画室", "乐知钢琴", "Northside Pottery"]
VOICES = ["", "Warm and relaxed. Sign off as 'The Harbour team'.", "简洁、礼貌，用「您」。落款：乐知钢琴前台",
          "Friendly, first names only, no exclamation marks."]
NOTES_EN = ["Worked on shading with soft pencils.", "Learned the C major scale hands together.",
            "Struggled with timing in the second section.", "Finished the watercolour of the harbour.",
            "Very focused today; asked good questions.", "Practised the recital piece twice."]
NOTES_ZH = ["练习了素描的明暗过渡。", "双手合练 C 大调音阶。", "第二段节奏还不稳。",
            "完成了港口水彩画。", "今天很专注，提了好问题。", "演奏会曲目练了两遍。"]
FORBIDDEN = re.compile(r"discount|refund|free lesson|waive|折扣|优惠|退款|免费|减免", re.I)


def _date(rng: random.Random, lo: int, hi: int) -> str:
    return (TODAY + timedelta(days=rng.randint(lo, hi))).isoformat()


def synthetic_records(per_kind: int, seed: int = 20261014) -> list[dict]:
    """Deterministic synthetic cases. Roughly one in four leaves a fact out on purpose."""

    rng = random.Random(seed)
    out = []
    for kind in drafting.KINDS:
        for i in range(per_kind):
            zh = i % 2 == 1
            name = rng.choice(FIRST_ZH if zh else FIRST_EN)
            facts = {"studio": rng.choice(STUDIOS)}
            withheld = None
            if kind == drafting.LOW_CREDITS:
                facts |= {"student_first_name": name, "parent_name": rng.choice(PARENT_ZH if zh else PARENT_EN),
                          "lessons_left": rng.choice([0, 1, 2]), "last_attended": _date(rng, -12, -1),
                          "packages": [{"name": "10 lessons", "lessons": 10, "price_aud": "450.00"},
                                       {"name": "20 lessons", "lessons": 20, "price_aud": "860.00"}]}
                if i % 4 == 3:
                    facts["packages"] = []
                    withheld = "packages"
            elif kind == drafting.MISSED_LESSONS:
                facts |= {"student_first_name": name, "parent_name": rng.choice(PARENT_ZH if zh else PARENT_EN),
                          "missed_in_a_row": rng.choice([3, 4, 5, 6]), "last_attended": _date(rng, -60, -21)}
            elif kind == drafting.OVERDUE_INVOICE:
                due = _date(rng, -40, -3)
                facts |= {"payer_name": rng.choice(PARENT_ZH if zh else PARENT_EN) or name,
                          "invoice_number": f"INV-{rng.randint(100, 999):04d}",
                          "amount_outstanding_aud": f"{rng.choice([90, 180, 245.5, 420]):.2f}",
                          "invoice_total_aud": "450.00", "due_date": due,
                          "days_overdue": (TODAY - date.fromisoformat(due)).days,
                          "how_to_pay": {"account_name": facts["studio"], "bsb": "062-000",
                                         "account_number": f"{rng.randint(10_000_000, 99_999_999)}"}}
                if i % 4 == 3:
                    facts["how_to_pay"] = {}
                    withheld = "how_to_pay"
            elif kind == drafting.EXPIRING_MAKEUP:
                facts |= {"student_first_name": name, "parent_name": rng.choice(PARENT_ZH if zh else PARENT_EN),
                          "makeup_expires_on": _date(rng, 3, 14), "missed_lesson_on": _date(rng, -50, -20),
                          "last_attended": _date(rng, -10, -1)}
            elif kind == drafting.BOOKING_REPLY:
                facts |= {"contact_name": name, "class_name": rng.choice(["Kids Watercolour", "Beginner Piano", "少儿素描"]),
                          "class_date": _date(rng, 2, 12), "start_time": rng.choice(["10:00", "16:30", "18:00"]),
                          "decision": ["approved", "declined", "question"][i % 3]}
            elif kind == drafting.REPORT_COMMENT:
                notes = NOTES_ZH if zh else NOTES_EN
                k = 1 if i % 4 == 3 else rng.randint(3, 6)
                facts |= {"student_first_name": name, "period_start": "2026-09-01", "period_end": "2026-09-30",
                          "attendance": {"scheduled": 4, "attended": rng.choice([2, 3, 4]), "cancelled": 0, "makeups": 0},
                          "lesson_notes": [{"date": f"2026-09-{d:02d}", "course": "Lesson", "note": rng.choice(notes)}
                                           for d in sorted(rng.sample(range(1, 30), k))],
                          "works": []}
            out.append({"id": f"{kind}-{i:02d}", "kind": kind, "language": "zh" if zh else "en",
                        "voice": rng.choice(VOICES), "facts": facts, "withheld": withheld})
    return out


# ── scripted checks ─────────────────────────────────────────────────────

def _cjk_share(text: str) -> float:
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return 0.0
    return sum(1 for c in letters if "一" <= c <= "鿿") / len(letters)


def scripted_checks(record: dict, draft: drafting.Draft) -> dict:
    body = draft.body
    share = _cjk_share(body)
    limit = 260 if record["language"] == "zh" else 900  # characters; generous on purpose
    if record["kind"] == drafting.REPORT_COMMENT:
        limit *= 2
    checks = {
        "unbacked": drafting.unbacked_figures(body, record["facts"]),
        "wrong_language": (share < 0.5) if record["language"] == "zh" else (share > 0.05),
        "too_long": len(body) > limit,
        "forbidden_promise": bool(FORBIDDEN.search(body)),
        "studio_named": record["facts"]["studio"] in body or bool(record["voice"]),
    }
    if record["withheld"]:
        checks["missing_admitted"] = bool(draft.missing) or "[" in body
    return checks


# ── tone grading ────────────────────────────────────────────────────────

GRADER_PROMPT = """You review a draft message that a small studio's staff will send to a student's family. Grade it from 1 to 5:

5 = could be sent as is: warm, clear, correct for the situation, sounds like a person at the studio.
4 = good, needs a small edit.
3 = usable but needs real editing (tone off, too long, unclear ask).
2 = mostly wrong for the situation.
1 = would harm the relationship or misstates the situation.

Judge against the facts given. Answer with JSON: "score" (1-5) and "reason" (one sentence)."""

GRADE_SCHEMA = {
    "type": "object",
    "properties": {"score": {"type": "integer"}, "reason": {"type": "string"}},
    "required": ["score", "reason"],
    "additionalProperties": False,
}


def grade(client, record: dict, draft: drafting.Draft) -> dict:
    payload = json.dumps({"situation": drafting.KIND_BRIEFS[record["kind"]], "facts": record["facts"],
                          "language": record["language"], "draft": {"subject": draft.subject, "body": draft.body}},
                         ensure_ascii=False, sort_keys=True)
    response = client.beta.messages.create(
        model=GRADER, max_tokens=1000, betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        system=[{"type": "text", "text": GRADER_PROMPT, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": payload}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": GRADE_SCHEMA}},
    )
    text = next((b.text for b in response.content if b.type == "text"), "{}")
    data = json.loads(text)
    usage = response.usage
    return {"score": int(data.get("score", 0)), "reason": data.get("reason", ""),
            "input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens,
            "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0}


# ── run ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--per-kind", type=int, default=40)
    parser.add_argument("--grade-per-kind", type=int, default=14,
                        help="drafts per kind per model sent to the tone grader")
    parser.add_argument("--max-usd", type=float, default=15.0, help="stop before estimated spend passes this")
    parser.add_argument("--dry-run", action="store_true", help="build every request, call nothing")
    args = parser.parse_args()

    records = synthetic_records(args.per_kind)
    if args.dry_run:
        sizes = [len(drafting.build_request(r["kind"], r["facts"], voice=r["voice"], language=r["language"])["user"])
                 for r in records]
        print(f"{len(records)} records × {len(args.models)} models; user message {min(sizes)}–{max(sizes)} characters")
        print(f"system prompt {len(drafting.SYSTEM_PROMPT)} characters; no API call made")
        return 0

    import anthropic

    client = anthropic.Anthropic(timeout=60.0)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    out_dir = APP_ROOT.parent / "outputs" / f"drafting-eval-{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    results = out_dir / "results.jsonl"

    spent_micros = 0
    rng = random.Random(7)
    to_grade = {(r["id"]) for kind in drafting.KINDS
                for r in rng.sample([x for x in records if x["kind"] == kind],
                                    min(args.grade_per_kind, args.per_kind))}
    summary: dict[str, dict] = {m: {"n": 0, "errors": 0, "unbacked": 0, "wrong_language": 0, "too_long": 0,
                                    "forbidden_promise": 0, "missing_not_admitted": 0, "withheld": 0,
                                    "scores": [], "in": 0, "out": 0, "cache": 0, "seconds": 0.0}
                                for m in args.models}
    with results.open("w", encoding="utf-8") as fh:
        for record in records:
            request = drafting.build_request(record["kind"], record["facts"], voice=record["voice"],
                                             language=record["language"])
            for model in args.models:
                if spent_micros / 1_000_000 > args.max_usd:
                    print(f"stopping: estimated spend passed US${args.max_usd}")
                    break
                row = {"id": record["id"], "kind": record["kind"], "language": record["language"], "model": model}
                s = summary[model]
                started = time.monotonic()
                try:
                    draft = drafting.call_model(client, request, model=model)
                except drafting.DraftingError as exc:
                    s["errors"] += 1
                    row["error"] = exc.code
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                    continue
                s["seconds"] += time.monotonic() - started
                spent_micros += drafting.estimated_cost_micros(draft)
                s["n"] += 1
                s["in"] += draft.input_tokens
                s["out"] += draft.output_tokens
                s["cache"] += draft.cache_read_tokens
                checks = scripted_checks(record, draft)
                s["unbacked"] += bool(checks["unbacked"])
                for key in ("wrong_language", "too_long", "forbidden_promise"):
                    s[key] += bool(checks[key])
                if record["withheld"]:
                    s["withheld"] += 1
                    s["missing_not_admitted"] += not checks["missing_admitted"]
                row |= {"draft": draft.as_dict(), "checks": checks,
                        "tokens": [draft.input_tokens, draft.output_tokens, draft.cache_read_tokens]}
                if record["id"] in to_grade:
                    graded = grade(client, record, draft)
                    spent_micros += drafting.estimated_cost_micros(drafting.Draft(
                        subject="", body="", missing=[], model=GRADER, input_tokens=graded["input_tokens"],
                        output_tokens=graded["output_tokens"], cache_read_tokens=graded["cache_read_tokens"]))
                    s["scores"].append(graded["score"])
                    row["grade"] = graded
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{record['id']}: estimated spend so far US${spent_micros / 1_000_000:.2f}", flush=True)

    lines = ["| model | drafts | errors | invented figure | wrong language | too long | forbidden promise | "
             "withheld fact not admitted | tone mean (n) | avg seconds | tokens in / out / cached |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for model, s in summary.items():
        mean = (sum(s["scores"]) / len(s["scores"])) if s["scores"] else 0
        lines.append(
            f"| {model} | {s['n']} | {s['errors']} | {s['unbacked']} | {s['wrong_language']} | {s['too_long']} | "
            f"{s['forbidden_promise']} | {s['missing_not_admitted']}/{s['withheld']} | {mean:.2f} ({len(s['scores'])}) | "
            f"{(s['seconds'] / s['n']) if s['n'] else 0:.1f} | {s['in']} / {s['out']} / {s['cache']} |")
    lines.append("")
    lines.append(f"Estimated spend: US${spent_micros / 1_000_000:.2f} (price list cached 2026-10-06).")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nresults: {results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
