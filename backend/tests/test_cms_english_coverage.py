"""Every static Chinese string in the CMS has an English entry, or a reason.

Found by looking at the top-up page in a browser before the v10.20.3 release.
In English the refund tab was half Chinese, including the submit button
`确认退款退课` on a money path, and the pack list read `1 credits`. None of it
was a regression: the strings never had entries, and they were invisible
because `cms-i18n.js` did not load at all from v10.16.0 to v10.20.1.
`test_i18n_dictionaries_execute.py` proves the dictionary runs; it does not ask
whether a screen is covered by it.

This test asks that for every CMS source file. It runs each static Chinese
string through the real `translateCore` and fails on any that comes back still
containing Chinese, unless `_cms_english_exemptions.py` gives a reason for it.
It was one panel on 2026-10-09 morning (57 strings); the same day the other
568 were drafted, reviewed and added, so the gate now covers all of them.

What it cannot see: sentences built in a template literal (`${name} 已签到`).
Those have no static form to extract. The assembled sentences that sit on a
money path are probed by hand below; the rest are a known gap, recorded in
`docs/handoff/claude/2026-10-09-cms-english-coverage.md`.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from _cms_english_exemptions import EXEMPT
from _cms_sources import cms_source_files

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DICTIONARY = REPOSITORY_ROOT / "backend/frontend/assets/cms-i18n.js"
NODE = shutil.which("node")

RUNNER = r"""
const fs = require('fs'), vm = require('vm');
const [dictionary, mode, payload] = process.argv.slice(1);
const calls = [];
const window = { StudioI18n: { mount(config) { calls.push(config); } } };
const context = vm.createContext({
  window,
  document: { body: { appendChild() {}, insertBefore() {}, firstChild: null },
              querySelector() { return null; } },
  console: { error() {}, warn() {}, log() {} },
});
vm.runInContext(fs.readFileSync(dictionary, 'utf8'), context);
const translate = calls[0].translateCore;
const CJK = /[一-鿿]/;

if (mode === 'probe') {
  process.stdout.write(JSON.stringify(JSON.parse(payload).map(s => translate(s))));
} else {
  let source = fs.readFileSync(payload, 'utf8')
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
    .replace(/\/\*[\s\S]*?\*\//g, '')
    .replace(/^\s*\/\/.*$/gm, '');
  const found = new Set();
  for (const m of source.matchAll(/>([^<>{}]*[一-鿿][^<>{}]*)</g)) found.add(m[1].trim());
  for (const m of source.matchAll(/(['"])((?:(?!\1)[^\\\n]){1,200})\1/g))
    if (CJK.test(m[2])) found.add(m[2].trim());
  // Code that happens to sit between a `>` and a `<` is not a string, and
  // neither is a slice of a template literal caught between two quotes.
  const strings = [...found].filter(s => s && !/===|=>|&&|\n|\$\{|^[})]/.test(s));
  process.stdout.write(JSON.stringify({
    candidates: strings.length,
    untranslated: strings.filter(s => CJK.test(String(translate(s)))),
  }));
}
"""


def _node(*arguments: str) -> object:
    result = subprocess.run([NODE, "-e", RUNNER, str(DICTIONARY), *arguments],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-800:]
    return json.loads(result.stdout)


def _coverage() -> tuple[int, dict[str, list[str]]]:
    """(candidates, {untranslated string: [files it is in]}) across the CMS."""

    candidates = 0
    untranslated: dict[str, list[str]] = {}
    for path in cms_source_files():
        report = _node("coverage", str(path))
        candidates += report["candidates"]
        for string in report["untranslated"]:
            untranslated.setdefault(string, []).append(path.name)
    return candidates, untranslated


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_no_cms_screen_shows_chinese_on_an_english_screen_without_a_reason() -> None:
    candidates, untranslated = _coverage()
    assert candidates >= 1200, (
        f"only {candidates} strings extracted from the CMS sources — "
        "the extraction is broken, not the CMS"
    )
    unexplained = {s: files for s, files in untranslated.items() if s not in EXEMPT}
    assert not unexplained, (
        "these show in Chinese on an English screen. Add an entry to cms-i18n.js "
        "(and rebuild the asset manifest), or give the reason in "
        "_cms_english_exemptions.py:\n  "
        + "\n  ".join(f"{s}   [{', '.join(files)}]" for s, files in sorted(unexplained.items()))
    )


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_every_exemption_is_still_needed() -> None:
    """A reason that no longer applies is a hole in the gate, not a record."""

    _, untranslated = _coverage()
    stale = sorted(set(EXEMPT) - set(untranslated))
    assert not stale, (
        "these are exempt but are no longer untranslated static strings — "
        "remove them from _cms_english_exemptions.py:\n  " + "\n  ".join(stale)
    )


@pytest.mark.skipif(NODE is None, reason="node not installed")
@pytest.mark.parametrize("chinese, english", [
    # The unit agrees with the number. `1 credits` was on every single-credit pack.
    ("1 课时 · AUD 65.00", "1 credit · AUD 65.00"),
    ("10 课时 · AUD 405.00", "10 credits · AUD 405.00"),
    ("1 课时", "1 credit"),
    ("-1 课时", "-1 credit"),
    ("0 课时", "0 credits"),
    ("2 课时", "2 credits"),
    # The refund path's own controls.
    ("确认退款退课", "Confirm refund"),
    ("先选择原充值", "Choose the original top-up first"),
    ("同步处理原发票与付款", "Also adjust the original invoice and payment"),
    # Sentences the app assembles. No static string exists for these, so the
    # coverage test above cannot see them; the confirmation before a top-up is
    # the one a mistake costs money on.
    ("确认 Holly Chen 充值 10 课时，gross $405.00（预计税额 $36.82），付款方：Chen Family；开票并登记已收款（现金）？",
     "Top up 10 credits for Holly Chen: gross $405.00 (estimated tax $36.82), payer: Chen Family. "
     "Issue the invoice and record the payment as received (Cash)?"),
    ("确认 Holly Chen 充值 1 课时，gross $65.00（预计税额 $5.91），付款方：Chen Family；开票但暂不登记收款？",
     "Top up 1 credit for Holly Chen: gross $65.00 (estimated tax $5.91), payer: Chen Family. "
     "Issue the invoice without recording a payment yet?"),
    ("Holly Chen 充值 10 课时，已开票并登记收款", "Holly Chen: 10 credits added, invoice issued and payment recorded"),
    ("已记录：不计费、不计课酬、已发一次补课额度", "Recorded: not charged, not counted for pay, one make-up credit issued"),
    # The two fallbacks: a known label before a colon, and a ` · ` list.
    ("加载失败：Network error", "Could not load: Network error"),
    ("未填写手机 · 14:30", "No mobile number · 14:30"),
    ("适龄 6–9 · 60 分钟 · 未标价", "Ages 6–9 · 60 min · No price set"),
    # A fallback must leave alone what it does not know: a family message
    # with a colon in it, and a list of nothing but data.
    ("提醒：您的上课时间是 10/10", "提醒：您的上课时间是 10/10"),
    ("0412 345 678 · 14:30 · Holly", "0412 345 678 · 14:30 · Holly"),
])
def test_money_path_strings_read_as_english(chinese: str, english: str) -> None:
    assert _node("probe", json.dumps([chinese]))[0] == english
