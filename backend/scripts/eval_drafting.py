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
* **Tone** (a sample): a grader grades each sampled draft 1-5 against a short
  rubric and never sees which model wrote it. Sonnet 5.5 grades, after a
  20-draft calibration against Opus 5.5 (the API planning session's advice).

Usage (from backend/):

    ../.venv/bin/python scripts/eval_drafting.py dry-run
    ../.venv/bin/python scripts/eval_drafting.py drafts      # one batch, all models, half price
    ../.venv/bin/python scripts/eval_drafting.py calibrate   # 20 drafts graded by Sonnet and Opus
    ../.venv/bin/python scripts/eval_drafting.py grades      # sampled drafts graded in a batch
    ../.venv/bin/python scripts/eval_drafting.py summary

Each step is resumable: a submitted batch id is kept in state.json.

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

#: Each synthetic studio has one trade, and its notes, classes and sign-off
#: match it. The first run mixed them (an art studio signing as a piano
#: school, drawing and scales in one term), and the models spent their
#: answers flagging the contradictions, which hid the differences between them.
STUDIOS = [
    {"name": "Harbour Art Studio", "trade": "art", "voices": ["", "Warm and relaxed. Sign off as 'The Harbour team'."]},
    {"name": "Brightkeys Piano", "trade": "piano", "voices": ["", "Friendly, first names only, no exclamation marks."]},
    {"name": "Moonlight Dance", "trade": "dance", "voices": ["", "Upbeat but brief. Sign off as 'Moonlight front desk'."]},
    {"name": "青禾画室", "trade": "art", "voices": ["", "简洁、礼貌，用「您」。落款：青禾画室前台"]},
    {"name": "乐知钢琴", "trade": "piano", "voices": ["", "亲切，称呼家长「您」。落款：乐知钢琴 · 小王"]},
    {"name": "Northside Pottery", "trade": "pottery", "voices": ["", "Plain and kind."]},
]
NOTES = {
    "art": {"en": ["Worked on shading with soft pencils.", "Finished the watercolour of the harbour.",
                   "Mixed secondary colours confidently.", "Rushed the background; we slowed down together."],
            "zh": ["练习了素描的明暗过渡。", "完成了港口水彩画。", "调色更有把握了。", "背景画得有点急，我们一起放慢了。"]},
    "piano": {"en": ["Learned the C major scale hands together.", "Timing in the second section is still uneven.",
                     "Practised the recital piece twice.", "Sight-read a new minuet well."],
              "zh": ["双手合练 C 大调音阶。", "第二段节奏还不稳。", "演奏会曲目练了两遍。", "新的小步舞曲视奏得不错。"]},
    "dance": {"en": ["Held the turns on balance.", "Remembered the whole routine.", "Arms still drop in the jump.",
                     "Very focused today; asked good questions."],
              "zh": ["转圈能稳住重心了。", "整段舞记住了。", "跳跃时手臂还会掉下来。", "今天很专注，提了好问题。"]},
    "pottery": {"en": ["Centred clay on the wheel for the first time.", "Trimmed the bowl foot neatly.",
                       "Walls came out uneven; practised pulling up.", "Glazed two cups."],
                "zh": ["第一次在拉坯机上把泥定中心。", "碗底修得很整齐。", "坯壁厚薄不均，练了提拉。", "给两个杯子上了釉。"]},
}
CLASSES = {"art": ["Kids Watercolour", "少儿素描"], "piano": ["Beginner Piano", "钢琴启蒙"],
           "dance": ["Junior Jazz", "少儿芭蕾"], "pottery": ["Wheel Basics", "拉坯入门"]}
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
            studio = rng.choice(STUDIOS)
            facts = {"studio": studio["name"]}
            voice = rng.choice(studio["voices"])
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
                facts |= {"contact_name": name, "class_name": CLASSES[studio["trade"]][1 if zh else 0],
                          "class_date": _date(rng, 2, 12), "start_time": rng.choice(["10:00", "16:30", "18:00"]),
                          "decision": ["approved", "declined", "question"][i % 3]}
                # The staff note the dialog now asks for (added after round two).
                if facts["decision"] == "question":
                    facts["staff_note"] = "问孩子几岁、以前有没有学过" if zh else "Ask the child's age and whether they have learned before."
                elif facts["decision"] == "declined":
                    facts["staff_note"] = "这节满了，可以改约同一周的周六上午十点" if zh else "That class is full; offer the Saturday 10:00 class the same week instead."
            elif kind == drafting.REPORT_COMMENT:
                notes = NOTES[studio["trade"]]["zh" if zh else "en"]
                k = 1 if i % 4 == 3 else rng.randint(2, 4)
                facts |= {"student_first_name": name, "period_start": "2026-09-01", "period_end": "2026-09-30",
                          "attendance": {"scheduled": 4, "attended": max(k, rng.choice([3, 4])), "cancelled": 0, "makeups": 0},
                          "lesson_notes": [{"date": f"2026-09-{d:02d}", "course": CLASSES[studio["trade"]][1 if zh else 0],
                                            "note": note}
                                           for d, note in zip(sorted(rng.sample(range(1, 30), k)), rng.sample(notes, k))],
                          # one note per lesson, never more notes than lessons attended
                          "works": []}
            out.append({"id": f"{kind}-{i:02d}", "kind": kind, "language": "zh" if zh else "en",
                        "voice": voice, "facts": facts, "withheld": withheld})
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


def grade_params(record: dict, draft: dict, grader: str) -> dict:
    payload = json.dumps({"situation": drafting.KIND_BRIEFS[record["kind"]], "facts": record["facts"],
                          "language": record["language"],
                          "draft": {"subject": draft["subject"], "body": draft["body"]}},
                         ensure_ascii=False, sort_keys=True)
    return {
        "model": grader, "max_tokens": 2000,
        "system": [{"type": "text", "text": GRADER_PROMPT}],
        "messages": [{"role": "user", "content": payload}],
        "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": GRADE_SCHEMA}},
    }


def parse_grade(message) -> int:
    text = next((b.text for b in message.content if b.type == "text"), "{}")
    return int(json.loads(text).get("score", 0))


# ── bookkeeping ─────────────────────────────────────────────────────────

SHORT = {"claude-opus-5-5": "opus", "claude-sonnet-5-5": "sonnet", "claude-haiku-5-5": "haiku"}
LONG = {v: k for k, v in SHORT.items()}


class Ledger:
    """Usage per (phase, model), priced from usage as the API session asked."""

    def __init__(self, path: Path):
        self.path = path
        self.rows = json.loads(path.read_text()) if path.exists() else []

    def add(self, phase: str, model: str, usage, *, batch: bool) -> None:
        self.rows.append({
            "phase": phase, "model": model, "batch": batch,
            "input": int(getattr(usage, "input_tokens", 0) or 0),
            "cache_write": int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
            "cache_read": int(getattr(usage, "cache_read_input_tokens", 0) or 0),
            "output": int(getattr(usage, "output_tokens", 0) or 0),
        })
        self.path.write_text(json.dumps(self.rows))

    def cost(self, row: dict) -> float:
        rate_in, rate_out, read = drafting.PRICES[row["model"]]
        dollars = (row["input"] * rate_in + row["cache_write"] * rate_in * 1.25
                   + row["cache_read"] * rate_in * read + row["output"] * rate_out) / 1_000_000
        return dollars / 2 if row["batch"] else dollars

    def total(self) -> float:
        return sum(self.cost(r) for r in self.rows)

    def table(self) -> list[str]:
        keys: dict[tuple, dict] = {}
        for r in self.rows:
            k = keys.setdefault((r["phase"], r["model"], r["batch"]),
                                {"n": 0, "input": 0, "cache_write": 0, "cache_read": 0, "output": 0, "cost": 0.0})
            k["n"] += 1
            for f in ("input", "cache_write", "cache_read", "output"):
                k[f] += r[f]
            k["cost"] += self.cost(r)
        lines = ["| phase | model | batch | requests | uncached in | cache write | cache read | output | US$ |",
                 "|---|---|---|---|---|---|---|---|---|"]
        for (phase, model, batch), k in sorted(keys.items()):
            lines.append(f"| {phase} | {model} | {'yes' if batch else 'no'} | {k['n']} | {k['input']} | "
                         f"{k['cache_write']} | {k['cache_read']} | {k['output']} | {k['cost']:.3f} |")
        lines.append(f"| **total** | | | {len(self.rows)} | | | | | **{self.total():.3f}** |")
        return lines


def run_batch(client, requests: list, state: dict, key: str, state_path: Path, label: str):
    """Submit once (resumable by batch id), wait for it to end, return results by custom_id."""

    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    if key not in state:
        batch = client.messages.batches.create(requests=[
            Request(custom_id=cid, params=MessageCreateParamsNonStreaming(**params)) for cid, params in requests
        ])
        state[key] = batch.id
        state_path.write_text(json.dumps(state, indent=2))
        print(f"{label}: submitted {len(requests)} requests as {batch.id}", flush=True)
    while True:
        batch = client.messages.batches.retrieve(state[key])
        counts = batch.request_counts
        print(f"{label}: {batch.processing_status} · processing {counts.processing} · "
              f"succeeded {counts.succeeded} · errored {counts.errored}", flush=True)
        if batch.processing_status == "ended":
            break
        time.sleep(30)
    return {r.custom_id: r.result for r in client.messages.batches.results(state[key])}


# ── run ─────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("step", choices=["dry-run", "drafts", "calibrate", "grades", "summary"])
    parser.add_argument("--models", nargs="+", default=list(MODELS))
    parser.add_argument("--per-kind", type=int, default=40)
    parser.add_argument("--grade-per-kind", type=int, default=14)
    parser.add_argument("--grader", default="claude-sonnet-5-5")
    parser.add_argument("--out", default=str(APP_ROOT.parent / "outputs" / "drafting-eval-2026-10-14b"))
    parser.add_argument("--max-usd", type=float, default=15.0)
    parser.add_argument("--kinds", nargs="+", default=list(drafting.KINDS))
    args = parser.parse_args()

    records = [r for r in synthetic_records(args.per_kind) if r["kind"] in args.kinds]
    by_id = {r["id"]: r for r in records}
    if args.step == "dry-run":
        sizes = [len(drafting.build_request(r["kind"], r["facts"], voice=r["voice"], language=r["language"])["user"])
                 for r in records]
        print(f"{len(records)} records × {len(args.models)} models; user message {min(sizes)}–{max(sizes)} characters")
        print(f"system prompt {len(drafting.SYSTEM_PROMPT)} characters; no API call made")
        return 0

    import anthropic

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    ledger = Ledger(out / "ledger.json")
    if ledger.total() > args.max_usd:
        print(f"stopping: spent US${ledger.total():.2f}, cap US${args.max_usd}")
        return 1
    client = anthropic.Anthropic(max_retries=5, timeout=120.0)
    drafts_path = out / "drafts.jsonl"

    if args.step == "drafts":
        requests = []
        for record in records:
            request = drafting.build_request(record["kind"], record["facts"], voice=record["voice"],
                                             language=record["language"])
            for model in args.models:
                requests.append((f"{SHORT[model]}__{record['id']}",
                                 drafting.request_params(request, model=model, cache=False)))
        results = run_batch(client, requests, state, "drafts_batch", state_path, "drafts")
        with drafts_path.open("w", encoding="utf-8") as fh:
            for cid, result in sorted(results.items()):
                short, rid = cid.split("__", 1)
                model, record = LONG[short], by_id[rid]
                row = {"id": rid, "kind": record["kind"], "language": record["language"], "model": model}
                if result.type != "succeeded":
                    row["error"] = result.type
                else:
                    message = result.message
                    ledger.add("draft", model, message.usage, batch=True)
                    try:
                        draft = drafting.draft_from_message(message, model=model)
                        row["draft"] = draft.as_dict()
                        row["checks"] = scripted_checks(record, draft)
                    except drafting.DraftingError as exc:
                        row["error"] = exc.code
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"drafts written to {drafts_path}; spent so far US${ledger.total():.3f}")
        return 0

    drafts = [json.loads(line) for line in drafts_path.read_text(encoding="utf-8").splitlines()] \
        if drafts_path.exists() else []
    good = [d for d in drafts if "draft" in d]

    if args.step == "calibrate":
        rng = random.Random(11)
        sample = rng.sample(good, min(20, len(good)))
        rows = []
        for d in sample:
            scores = {}
            for grader in ("claude-sonnet-5-5", "claude-opus-5-5"):
                message = client.messages.create(**grade_params(by_id[d["id"]], d["draft"], grader))
                ledger.add("calibrate", grader, message.usage, batch=False)
                scores[grader] = parse_grade(message)
            rows.append({"id": d["id"], "model": d["model"], **scores})
        same = sum(1 for r in rows if r["claude-sonnet-5-5"] == r["claude-opus-5-5"])
        near = sum(1 for r in rows if abs(r["claude-sonnet-5-5"] - r["claude-opus-5-5"]) <= 1)
        (out / "calibration.json").write_text(json.dumps(rows, indent=2))
        print(f"calibration: {len(rows)} drafts · identical {same} · within one point {near}")
        print(f"spent so far US${ledger.total():.3f}")
        return 0

    if args.step == "grades":
        rng = random.Random(7)
        chosen = []
        for model in args.models:
            for kind in args.kinds:
                pool = [d for d in good if d["model"] == model and d["kind"] == kind]
                chosen += rng.sample(pool, min(args.grade_per_kind, len(pool)))
        requests = [(f"g__{SHORT[d['model']]}__{d['id']}", grade_params(by_id[d["id"]], d["draft"], args.grader))
                    for d in chosen]
        results = run_batch(client, requests, state, "grades_batch", state_path, "grades")
        grades = {}
        for cid, result in results.items():
            _, short, rid = cid.split("__", 2)
            if result.type == "succeeded":
                ledger.add("grade", args.grader, result.message.usage, batch=True)
                grades[f"{LONG[short]}|{rid}"] = parse_grade(result.message)
        (out / "grades.json").write_text(json.dumps(grades, indent=2))
        print(f"{len(grades)} grades; spent so far US${ledger.total():.3f}")
        return 0

    # summary
    grades = json.loads((out / "grades.json").read_text()) if (out / "grades.json").exists() else {}
    lines = ["| model | drafts | errors | invented figure | wrong language | too long | forbidden promise | "
             "withheld fact not admitted | tone mean (n) | share scoring 4–5 | output tokens per draft |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for model in args.models:
        mine = [d for d in drafts if d["model"] == model]
        ok = [d for d in mine if "draft" in d]
        withheld = [d for d in ok if "missing_admitted" in d["checks"]]
        scores = [v for k, v in grades.items() if k.startswith(model + "|")]
        out_tokens = [r["output"] for r in ledger.rows if r["phase"] == "draft" and r["model"] == model]
        lines.append(
            f"| {model} | {len(ok)} | {len(mine) - len(ok)} | {sum(bool(d['checks']['unbacked']) for d in ok)} | "
            f"{sum(d['checks']['wrong_language'] for d in ok)} | {sum(d['checks']['too_long'] for d in ok)} | "
            f"{sum(d['checks']['forbidden_promise'] for d in ok)} | "
            f"{sum(not d['checks']['missing_admitted'] for d in withheld)}/{len(withheld)} | "
            f"{(sum(scores) / len(scores)) if scores else 0:.2f} ({len(scores)}) | "
            f"{(sum(1 for s in scores if s >= 4) / len(scores) * 100) if scores else 0:.0f}% | "
            f"{(sum(out_tokens) / len(out_tokens)) if out_tokens else 0:.0f} |")
    lines += ["", "Spend by usage (batch at half price; cache reads per the API session's 2026-10-11 rates):", ""]
    lines += ledger.table()
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
