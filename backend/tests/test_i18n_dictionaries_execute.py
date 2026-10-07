"""The two dictionary files must run to the end, not just parse.

From v10.16.0 to v10.20.1 the CMS had no English and no language switch, and
every gate was green. `cms-i18n.js` had lost a comma between two dictionary
pairs: `['a', 'b'] ['c', 'd']` is an index expression, not two entries, so one
element became `undefined` and `Object.fromEntries` threw while the file was
loading. The IIFE stopped before it reached `StudioI18n.mount()`.

Nothing caught it because nothing executed the file. `node --check` (here and
in `test_inline_scripts_parse.py`) only proves it parses, and it did.
`check_i18n_dictionaries.py` reads the pairs as text and looks for duplicate
keys, so a missing comma is invisible to it.

This test executes each dictionary in a sandbox with a stub `StudioI18n` and
asserts the file reaches `mount()` with a working `translateCore`. Any error
thrown while the dictionary is built fails it.

Skipped rather than failed when node is absent, as in
`test_inline_scripts_parse.py`; `verify_local.sh` already refuses a release gate
on a machine without node.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ASSETS = REPOSITORY_ROOT / "backend/frontend/assets"
NODE = shutil.which("node")

# (file, globalName passed to mount, a source string, its expected translation)
DICTIONARIES = [
    ("cms-i18n.js", "CmsI18n", "工作台", "Dashboard"),
    ("admin-i18n.js", "AdminI18n", "Login", "登录"),
]

# Runs one file in a fresh context. `window.StudioI18n.mount` only records its
# argument; the real runtime (i18n-runtime.js) is not under test here. A thrown
# error escapes runInContext, so node exits non-zero with the stack on stderr.
RUNNER = r"""
const fs = require('fs');
const vm = require('vm');
const [file, probe] = process.argv.slice(1);
const calls = [];
const errors = [];
const document = {
  body: { appendChild() {}, insertBefore() {}, firstChild: null },
  querySelector() { return null; },
};
const window = { StudioI18n: { mount(config) { calls.push(config); } } };
const context = vm.createContext({
  window, document,
  console: { error: (...a) => errors.push(a.join(' ')), warn() {}, log() {} },
});
vm.runInContext(fs.readFileSync(file, 'utf8'), context, { filename: file });
const config = calls[0] || {};
process.stdout.write(JSON.stringify({
  mountCalls: calls.length,
  globalName: config.globalName || null,
  translated: typeof config.translateCore === 'function'
    ? config.translateCore(probe) : null,
  consoleErrors: errors,
}));
"""


@pytest.mark.skipif(NODE is None, reason="node not installed")
@pytest.mark.parametrize(
    ("filename", "global_name", "probe", "expected"),
    DICTIONARIES,
    ids=[entry[0] for entry in DICTIONARIES],
)
def test_dictionary_file_runs_to_mount(filename, global_name, probe, expected):
    path = ASSETS / filename
    completed = subprocess.run(
        [NODE, "-e", RUNNER, str(path), probe],
        capture_output=True, text=True, timeout=60,
    )
    assert completed.returncode == 0, (
        f"{filename} threw while loading, so StudioI18n.mount() was never "
        f"reached and the language switch is gone:\n{completed.stderr.strip()}"
    )
    result = json.loads(completed.stdout)
    assert result["consoleErrors"] == [], result["consoleErrors"]
    assert result["mountCalls"] == 1, (
        f"{filename} loaded but called StudioI18n.mount() "
        f"{result['mountCalls']} times; expected once"
    )
    assert result["globalName"] == global_name
    assert result["translated"] == expected, (
        f"{filename}: translateCore({probe!r}) returned {result['translated']!r}, "
        f"expected {expected!r}; the dictionary did not load"
    )
