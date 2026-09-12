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
    # v10.19.0 — the L1 portal. These carry no inline JS at all, which is why
    # they were never listed; what they carry is six hand-written assets that
    # no `node --check` reached either. `_linked_assets` below covers both, so
    # a page is checked for the script it actually runs rather than for the
    # script that happens to be inline.
    REPOSITORY_ROOT / "product-home.html",
    REPOSITORY_ROOT / "pricing.html",
    REPOSITORY_ROOT / "manual.html",
    REPOSITORY_ROOT / "legacy-root/register.html",
]

LINKED = re.compile(r'<script\b[^>]*\bsrc\s*=\s*["\']([^"\']+)["\'][^>]*>', re.I)
MODULE = re.compile(r'\btype\s*=\s*["\']?module', re.I)

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


def _linked_assets(page: Path) -> list[tuple[Path, bool]]:
    """The local scripts this page loads, as (path, is_module).

    Only same-origin `/assets/...` and relative paths — a CDN URL is not ours
    to parse. This replaced a two-entry map naming the consoles' bundles by
    hand, which is why nothing ever checked marketing-shell.js, product-home.js,
    pricing.js, manual.js, customer-resources.js or portal-brand.js.
    """

    source = page.read_text(encoding="utf-8")
    found: list[tuple[Path, bool]] = []
    for match in re.finditer(r"<script\b([^>]*)>", source, re.I):
        attrs = match.group(1)
        src = LINKED.match(f"<script{attrs}>")
        if src is None:
            continue
        href = src.group(1).split("?")[0]
        if "//" in href:
            continue
        candidate = REPOSITORY_ROOT / href.lstrip("/")
        if not candidate.is_file():
            candidate = REPOSITORY_ROOT / "backend/frontend" / href.lstrip("/")
        if candidate.is_file():
            found.append((candidate, bool(MODULE.search(attrs))))
    return found


@pytest.mark.skipif(NODE is None, reason="node is not installed; inline scripts cannot be parsed")
@pytest.mark.parametrize("page", PAGES, ids=lambda p: f"{p.parent.name}-{p.name}")
def test_inline_script_parses(page: Path, tmp_path: Path) -> None:
    javascript = _inline_javascript(page)
    linked = _linked_assets(page)
    assert javascript.strip() or linked, (
        f"{page.name} has no script at all — did the extraction break?"
    )

    if javascript.strip():
        candidate = tmp_path / "inline.js"
        candidate.write_text(javascript, encoding="utf-8")
        result = subprocess.run([NODE, "--check", str(candidate)],
                                capture_output=True, text=True)
        assert result.returncode == 0, f"{page} inline script does not parse:\n{result.stderr}"

    for asset, is_module in linked:
        command = [NODE, "--check"]
        if is_module:
            command += ["--input-type=module"]
        result = subprocess.run(command + [str(asset)], capture_output=True, text=True)
        assert result.returncode == 0, (
            f"{page.name} loads {asset.name}, which does not parse:\n{result.stderr}"
        )


def test_the_timetable_helpers_are_declared_at_top_level() -> None:
    """Helpers stay callable and navigation has one authoritative owner.

    The former per-page ``setNavVisible`` helper duplicated the public-surface
    resolver and could disagree with the footer. Timetable now fetches the
    authoritative contract; the remaining callable helpers still have to stay
    at top level because nested declarations are invisible to event callbacks.

    Top level inside the page's one script block is four spaces of indent.
    """

    source = (REPOSITORY_ROOT / "tenant-template/timetable.html").read_text(encoding="utf-8")
    for helper in ("function setMobileNav(", "function applyLanguage("):
        assert f"\n    {helper}" in source, (
            f"{helper} is not declared at top level — a nested declaration is "
            "invisible to the callbacks that call it, and the failure is silent"
        )
    assert "publicSurface.fetch(API)" in source
    assert "setNavVisible" not in source
