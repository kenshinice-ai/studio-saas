"""Every `var(--token)` a page reads must be a token something it loads defines.

`pricing.css` consumed `--muted` six times. Neither stylesheet the pricing page
loads defines it, so all six declarations were invalid-at-computed-value: the
browser threw them away and the text inherited whatever was above it. The whole
secondary type tier was missing from the page and nothing anywhere said so —
not the build, not a test, not the browser console, which reports nothing for
this. A misspelt token is silent by design; `var()` has a fallback slot exactly
so that the no-fallback case can mean "this must exist".

This walks each public page's own `<link rel=stylesheet>` set, which is also
how it catches the other half of the problem: `product-home.html` does not load
`ui-tokens.css` at all — `marketing.css` re-declares the family palette under
different names — so a token added to ui-tokens.css reaches the manual and the
customer resources and silently does not reach the product home page.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

PAGES = {
    "product-home.html": REPOSITORY_ROOT / "product-home.html",
    "pricing.html": REPOSITORY_ROOT / "pricing.html",
    "manual.html": REPOSITORY_ROOT / "manual.html",
    "customer-resources/Release_Notes.html":
        REPOSITORY_ROOT / "customer-resources/Release_Notes.html",
}

LINK = re.compile(r'<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"')
DEFINE = re.compile(r"(--[A-Za-z0-9_-]+)\s*:")
# `var(--x)` with no comma — a fallback means the author already said what
# happens when it is missing, which is a different (and fine) situation.
CONSUME_NO_FALLBACK = re.compile(r"var\(\s*(--[A-Za-z0-9_-]+)\s*\)")

# Set by the browser or by script at runtime, so no stylesheet declares them.
RUNTIME_TOKENS = {
    "--tw-gradient-to", "--tw-gradient-from", "--tw-gradient-stops",
    "--tw-border-spacing-x", "--tw-border-spacing-y",
}


def _sheets_for(page: Path) -> list[Path]:
    source = page.read_text(encoding="utf-8")
    found = []
    for href in LINK.findall(source):
        if "//" in href:
            continue
        candidate = REPOSITORY_ROOT / "backend/frontend" / href.split("?")[0].lstrip("/")
        if candidate.is_file():
            found.append(candidate)
    return found


@pytest.mark.parametrize("name", sorted(PAGES))
def test_every_token_a_page_reads_is_defined_somewhere_it_loads(name: str) -> None:
    page = PAGES[name]
    sheets = _sheets_for(page)
    assert sheets, f"{name} links no local stylesheet — the href parse is broken"

    defined: set[str] = set(RUNTIME_TOKENS)
    consumed: dict[str, str] = {}
    for source, label in [(page.read_text(encoding="utf-8"), name)] + [
            (sheet.read_text(encoding="utf-8"), sheet.name) for sheet in sheets]:
        stripped = re.sub(r"/\*.*?\*/", "", source, flags=re.S)
        defined.update(DEFINE.findall(stripped))
        for token in CONSUME_NO_FALLBACK.findall(stripped):
            consumed.setdefault(token, label)

    missing = sorted(
        f"{token} (read in {where})"
        for token, where in consumed.items() if token not in defined
    )
    assert not missing, (
        f"{name} reads tokens nothing it loads defines, so those declarations "
        f"are dropped and the text inherits:\n  " + "\n  ".join(missing)
    )
