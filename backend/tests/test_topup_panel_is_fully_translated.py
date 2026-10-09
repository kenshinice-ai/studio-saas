"""Every static Chinese string on the top-up panel has an English entry.

Found by looking at the page in a browser before the v10.20.3 release. In
English the refund tab was half Chinese: the source notice, the sync checkbox,
the closing note, and the submit button `确认退款退课` on a money path. The
pack list also read `1 credits`.

None of it was a regression. The strings never had entries; they were invisible
because `cms-i18n.js` did not load at all from v10.16.0 to v10.20.1. When
v10.20.2 restored the dictionary, the strings with no entry were the ones left
standing. `test_i18n_dictionaries_execute.py` proves the dictionary runs; it
does not ask whether a panel is covered by it.

This test asks that for one panel: it runs each static Chinese string in the
top-up panel through the real `translateCore` and fails on any that comes back
still containing Chinese. One panel, not all of them — measured on 2026-10-09
the same extraction leaves up to 580 of 1,455 strings unresolved across the
other CMS sources. That number is an upper bound (it also catches audit labels
and printable-report text that take other paths) and it is recorded in
`docs/handoff/claude/2026-10-09-v10.20.3-topup-english.md`, not hidden by a
gate that only looks where the answer is zero.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from _cms_sources import cms_source_files

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DICTIONARY = REPOSITORY_ROOT / "backend/frontend/assets/cms-i18n.js"
NODE = shutil.which("node")
PANEL_NAME = "topup.jsx"

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
  // Code that happens to sit between a `>` and a `<` is not a string.
  const strings = [...found].filter(s => s && !/===|=>|&&|\n/.test(s));
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


def _panel() -> Path:
    matches = [path for path in cms_source_files() if path.name == PANEL_NAME]
    assert len(matches) == 1, f"expected one {PANEL_NAME} in the CMS sources, found {matches}"
    return matches[0]


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_the_topup_panel_leaves_no_chinese_on_an_english_screen() -> None:
    report = _node("coverage", str(_panel()))
    assert report["candidates"] >= 40, (
        f"only {report['candidates']} strings extracted from {PANEL_NAME} — "
        f"the extraction is broken, not the panel"
    )
    assert not report["untranslated"], (
        f"{PANEL_NAME} shows these in Chinese on an English screen:\n  "
        + "\n  ".join(report["untranslated"])
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
])
def test_money_path_strings_read_as_english(chinese: str, english: str) -> None:
    assert _node("probe", json.dumps([chinese]))[0] == english
