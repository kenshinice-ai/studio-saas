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

Sentences built in a template literal (`${name} 已签到`) have no static form.
`_assembled_sentences.js` re-derives each one from the source, fills its holes
with placeholders, and the second test below runs the result through the
dictionary the same way. The ones on a money path are also probed with real
values.

What neither test sees: text the app builds by concatenating a variable in
front of a quoted string (`name + ' 已签到'`), and what only appears after a
click. Those are found by walking the CMS in English in a browser.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from _cms_english_exemptions import EXEMPT, EXEMPT_ASSEMBLED
from _cms_sources import cms_source_files

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DICTIONARY = REPOSITORY_ROOT / "backend/frontend/assets/cms-i18n.js"
NODE = shutil.which("node")
ASSEMBLED_LIB = Path(__file__).resolve().parent / "_assembled_sentences.js"

ASSEMBLED_RUNNER = r"""
const fs = require('fs'), vm = require('vm');
const [dictionary, lib, ...files] = process.argv.slice(1);
const { extract, sample, CJK } = require(lib);
const calls = [];
const window = { StudioI18n: { mount(config) { calls.push(config); } } };
vm.runInContext(fs.readFileSync(dictionary, 'utf8'), vm.createContext({
  window, document: { body: {}, querySelector() { return null; } },
  console: { error() {}, warn() {}, log() {} } }));
const translate = calls[0].translateCore;
// A hole may be a name, a count or a year; a sentence is covered when any
// plausible filling comes out without Chinese. The third filling is the key.
const FILLS = [() => '7', () => 'Zed', n => (n % 2 ? '7' : 'Zed'), n => (n % 2 ? 'Zed' : '7'), () => '2026'];
let total = 0; const uncovered = {};
for (const file of files) {
  for (const sentence of extract(fs.readFileSync(file, 'utf8'))) {
    total++;
    const samples = FILLS.map(fill => sample(sentence.parts, fill));
    if (!samples.some(text => !CJK.test(String(translate(text))))) uncovered[samples[2]] = file.split('/').pop();
  }
}
process.stdout.write(JSON.stringify({ total, uncovered }));
"""

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


def _assembled() -> dict:
    result = subprocess.run(
        [NODE, "-e", ASSEMBLED_RUNNER, str(DICTIONARY), str(ASSEMBLED_LIB),
         *[str(path) for path in cms_source_files()]],
        capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-800:]
    return json.loads(result.stdout)


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_no_assembled_sentence_comes_out_chinese_without_a_reason() -> None:
    report = _assembled()
    assert report["total"] >= 200, (
        f"only {report['total']} assembled sentences found in the CMS sources — "
        "the extraction is broken, not the CMS"
    )
    unexplained = {s: f for s, f in report["uncovered"].items() if s not in EXEMPT_ASSEMBLED}
    assert not unexplained, (
        "these sentences are assembled from a template and still come out Chinese. "
        "Add a row to `assembled` in cms-i18n.js, or give the reason in "
        "_cms_english_exemptions.py:\n  "
        + "\n  ".join(f"{s!r}   [{f}]" for s, f in sorted(unexplained.items()))
    )
    stale = sorted(set(EXEMPT_ASSEMBLED) - set(report["uncovered"]))
    assert not stale, (
        "these assembled sentences are exempt but are now translated or gone — "
        "remove them from EXEMPT_ASSEMBLED:\n  " + "\n  ".join(stale)
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
    ("确认 Holly Chen 从原充值 INV-0003 退 2 课时、退款 $130.00（现金），同时开具贷记单并登记付款退款？",
     "Remove 2 credits and refund $130.00 (Cash) for Holly Chen, from original top-up INV-0003, "
     "and also issue a credit note and record the payment refund?"),
    ("Holly Chen 签到 ✓ 剩余 1 课时", "Holly Chen checked in ✓ 1 credit left"),
    ("发出 3 张，1 张失败：timeout", "Issued 3 invoices; 1 failed: timeout"),
    # Hand-written rules: the placeholder sample cannot reach these.
    ("Holly Chen 已归档", "Holly Chen archived"),
    ("已暂停", "Paused"),
    ("10月", "Oct"),
    ("45 分钟 · 默认", "45 min · default"),
    ("共 3 条申请", "3 requests"),
    ("工作室停课：不计费，老师照付课酬。", "Cancelled by the studio: not charged, teacher still paid."),
    ("提前 24 小时以上算按时请假，发补课额度；临时请假照常计费。",
     "Leave with at least 24 hours' notice counts as on time and earns a make-up credit; late leave is still charged."),
    # A short template must not swallow ordinary words or a tenant's data.
    ("每月", "每月"),
    ("素描集", "素描集"),
    ("小张", "小张"),
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
