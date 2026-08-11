"""Every hand-written inline script must at least parse.

These pages are the product's blind spot. `cms-app.jsx` goes through esbuild,
which refuses to emit a file it cannot parse. But `tenant-template/*.html`,
`studio-admin.html`, `super-admin.html` and `legacy-root/index.html` carry
their JavaScript inline: nothing compiles them, and no test runtime executes
them. A broken one is discovered by a person opening the page.

v8.10.1 was exactly that — an undefined name in studio-admin.html that aborted
the rest of its function and looked, to the owner, like four unrelated faults.

`node --check` cannot catch an undefined name. It catches the other half:
a stray brace, an unclosed template literal, a duplicate `const` — the errors
that take a whole page down rather than one function, and that are otherwise
found the same expensive way.

Skipped rather than failed when node is absent, because a machine without it
should not be told its code is broken.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")

PAGES = [
    REPOSITORY_ROOT / "tenant-template/index.html",
    REPOSITORY_ROOT / "tenant-template/register.html",
    REPOSITORY_ROOT / "tenant-template/timetable.html",
    REPOSITORY_ROOT / "tenant-template/showcase.html",
    REPOSITORY_ROOT / "backend/frontend/studio-admin.html",
    REPOSITORY_ROOT / "super-admin.html",
    REPOSITORY_ROOT / "legacy-root/index.html",
]

# `<script>` with no type, or an explicitly JavaScript one. A
# `type="application/ld+json"` block is data and would fail a JS parse for a
# reason that is not a defect.
SCRIPT = re.compile(
    r"<script(?![^>]*\bsrc=)([^>]*)>(.*?)</script>", re.S | re.I)
JS_TYPE = re.compile(r'type\s*=\s*["\']?(?:text/javascript|module|application/javascript)', re.I)
HAS_TYPE = re.compile(r"\btype\s*=", re.I)


def _inline_javascript(page: Path) -> str:
    source = page.read_text(encoding="utf-8")
    # The template placeholders are substituted at workspace-generation time;
    # parsing them raw would fail on `{{TENANT_NAME_JSON}}` alone.
    source = source.replace("{{TENANT_SLUG}}", "demo-studio")
    source = source.replace("{{TENANT_NAME_JSON}}", json.dumps("Demo Studio"))
    source = source.replace("{{TENANT_NAME}}", "Demo Studio")
    source = source.replace("__APP_VERSION__", "0.0.0")
    blocks = [
        body for attrs, body in SCRIPT.findall(source)
        if not HAS_TYPE.search(attrs) or JS_TYPE.search(attrs)
    ]
    return "\n;\n".join(blocks)


@pytest.mark.skipif(NODE is None, reason="node is not installed; inline scripts cannot be parsed")
@pytest.mark.parametrize("page", PAGES, ids=lambda p: f"{p.parent.name}-{p.name}")
def test_inline_script_parses(page: Path, tmp_path: Path) -> None:
    javascript = _inline_javascript(page)
    assert javascript.strip(), f"{page.name} has no inline script — did the extraction break?"
    candidate = tmp_path / "inline.js"
    candidate.write_text(javascript, encoding="utf-8")
    result = subprocess.run([NODE, "--check", str(candidate)], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"{page} does not parse:\n{result.stderr}"
    )


def test_the_timetable_helpers_are_declared_at_top_level() -> None:
    """Where a function is declared decides whether the page works.

    While writing the v8.10.1 navigation, an edit put `setNavVisible` inside
    `applyLanguage()`. It parses. It is also invisible to the /brand callback
    that calls it — a ReferenceError which, like the one before it, would have
    aborted that callback and taken the theme down with it.

    Top level inside the page's one script block is four spaces of indent.
    """

    source = (REPOSITORY_ROOT / "tenant-template/timetable.html").read_text(encoding="utf-8")
    for helper in ("function setNavVisible(", "function setMobileNav(", "function applyLanguage("):
        assert f"\n    {helper}" in source, (
            f"{helper} is not declared at top level — a nested declaration is "
            "invisible to the callbacks that call it, and the failure is silent"
        )
