"""The user manual: one language per URL, one palette, and printable.

The manual is the page a support reply links into, so its section anchors are
a contract — renaming one breaks every link already sent. It is also the
fourth page to carry the family colours, and the previous three drifted onto a
retired palette because each held its own copy of the hex.

The print stylesheet is the PDF. There is no second document, which means the
things that make a printed page usable — the contents removed, link targets
written out, sections starting on a fresh page, and nothing left hidden by the
on-screen filter — are only true if they are asserted.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANUAL = REPOSITORY_ROOT / "manual.html"
STYLE = REPOSITORY_ROOT / "backend/frontend/assets/manual.css"
SCRIPT = REPOSITORY_ROOT / "backend/frontend/assets/manual.js"
TOKENS = REPOSITORY_ROOT / "backend/frontend/assets/ui-tokens.css"
SERVER = REPOSITORY_ROOT / "backend/server.py"
GUIDES = REPOSITORY_ROOT / "docs/guides"

# Every section the manual promises, in the order it promises them. A support
# link is written as /manual/#refunds; renaming an anchor breaks it silently.
SECTIONS = [
    "start", "launch", "enrolment", "roster", "timetable", "money", "work",
    # v10.2.0: `invoicing` covers the money layer — issuing identity, invoices,
    # teacher pay and private lessons. Distinct from `money`, which is the
    # lesson-credit ledger; the two reconcile but are not the same book.
    "showcase", "families", "team", "invoicing", "insight", "platform", "help", "faq",
]


def _source() -> str:
    return MANUAL.read_text(encoding="utf-8")


def _style() -> str:
    return STYLE.read_text(encoding="utf-8")


def _strip_comments(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


# ── structure ────────────────────────────────────────────────────────────────

def test_every_section_exists_and_is_in_the_contents() -> None:
    """A contents entry pointing at nothing is worse than no contents."""

    source = _source()
    for anchor in SECTIONS:
        assert f'<section id="{anchor}">' in source, f"section #{anchor} is missing"
        assert f'href="#{anchor}"' in source, f"#{anchor} is not in the table of contents"

    listed = re.findall(r'<li><a href="#([a-z]+)">', source)
    assert listed == SECTIONS, f"contents order drifted: {listed}"


def test_the_manual_stops_short_of_the_platform_console() -> None:
    """Decided with the owner: this is a customer manual.

    Section 10 tells a studio what the platform can and cannot do inside their
    data, which is a trust statement. Instructions for operating the console
    stay in docs/guides/Super_Admin_Guide.md, which is internal.
    """

    source = _source()
    assert "/platform-admin" not in source
    assert 'Enter Support Mode' not in source
    assert (GUIDES / "Super_Admin_Guide.md").exists()


# ── language ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("language", ["en", "zh"])
def test_each_language_is_a_complete_document(language: str) -> None:
    from studiosaas.services.public_site import apply_language

    document = apply_language(_source(), language)
    body = re.sub(r"<!--.*?-->", "", document, flags=re.S)
    assert "data-lang" not in body, "authoring markers survived the filter"
    assert document.count("<h1") == 1
    assert document.count("<title") == 1
    # Controls the script requires must survive in exactly one copy, or the
    # page throws on load.
    for element in ('id="manualSearch"', 'id="noHits"', 'id="printButton"',
                    'id="tocButton"', 'id="toc"'):
        assert document.count(element) == 1, f"{element} appears {document.count(element)} times"
    assert document.count("<section id=") == len(SECTIONS)


def test_no_language_element_nests_the_same_tag() -> None:
    """The filter finds the end of a skipped subtree by counting one tag name.

    A `<span data-lang="zh">` wrapping another `<span>` would end the skip at
    the inner close tag and leak the rest of the Chinese subtree into the
    English page.
    """

    from html.parser import HTMLParser

    void = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}

    class _Nesting(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.stack: list[tuple[str, bool]] = []
            self.violations: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in void:
                return
            for open_tag, marked in self.stack:
                if open_tag == tag and marked:
                    self.violations.append(tag)
            self.stack.append((tag, any(name == "data-lang" for name, _ in attrs)))

        def handle_endtag(self, tag):
            for index in range(len(self.stack) - 1, -1, -1):
                if self.stack[index][0] == tag:
                    del self.stack[index:]
                    return

    checker = _Nesting()
    checker.feed(_source())
    checker.close()
    assert not checker.violations, set(checker.violations)


def test_the_hreflang_pair_is_reciprocal_and_the_switch_is_a_link() -> None:
    source = _source()
    for link in (
        '<link rel="alternate" hreflang="en-AU" href="https://pwestudio.online/manual/">',
        '<link rel="alternate" hreflang="zh-Hans" href="https://pwestudio.online/zh/manual/">',
        '<link rel="alternate" hreflang="x-default" href="https://pwestudio.online/manual/">',
    ):
        assert link in source
    assert 'href="/zh/manual/" hreflang="zh-Hans"' in source
    assert 'href="/manual/" hreflang="en-AU"' in source
    assert 'id="languageButton"' not in source


def test_the_server_routes_both_languages() -> None:
    source = SERVER.read_text(encoding="utf-8")
    for route in ("@app.route('/manual/')", "@app.route('/zh/manual/')",
                  "@app.route('/manual')", "@app.route('/zh/manual')"):
        assert route in source


# ── palette ──────────────────────────────────────────────────────────────────

def test_the_manual_declares_no_family_colour_of_its_own() -> None:
    """Three customer pages drifted onto a retired palette holding their own
    copies of the hex. This one reads ui-tokens.css and restates nothing."""

    style = _strip_comments(_style())
    family = re.findall(r"#(?:0e1729|16233d|22355a|f5b335|a16207|f7f5f2)", style, re.I)
    assert not family, f"manual.css restates family colours: {set(family)}"
    assert "--pwe-family-navy" in style and "--pwe-family-amber" in style
    assert '<link rel="stylesheet" href="/assets/ui-tokens.css' in _source()

    tokens = TOKENS.read_text(encoding="utf-8")
    for token in ("--pwe-family-navy", "--pwe-family-navy-raised",
                  "--pwe-family-amber", "--pwe-family-amber-text", "--pwe-warm-paper"):
        assert token in tokens, f"{token} is not defined in ui-tokens.css"


def test_the_bright_amber_is_not_the_accent_on_paper() -> None:
    """#F5B335 is 1.70:1 on Warm Paper. The light theme has to swap it."""

    style = _strip_comments(_style())
    light = style[style.index("@media (prefers-color-scheme: light)"):]
    light = light[: light.index("\n}\n", light.index("{")) + 3]
    assert "--accent: var(--pwe-family-amber-text)" in light
    assert "grid-template-columns" not in light, "the light theme forked the layout"


# Small text, per WCAG 1.4.3. Nothing on this page is large enough to claim 3:1
# — the smallest thing here is the 10px step numeral, the largest is body copy.
MINIMUM_RATIO = 4.5


def test_every_foreground_on_its_own_background_is_legible_in_all_three_themes() -> None:
    """The substring test above passed while the numbered bullets sat at 3.64:1.

    It could not have caught them: `--accent: var(--pwe-family-amber-text)` is
    the *correct* light-theme swap, and asserting that it is present says
    nothing about what is painted on top of it. `.steps > li::before` set
    `background: var(--accent)` with navy text, so the very substitution the
    assertion demanded is what made the bullets illegible — and print was
    worse at 2.05:1, because `--accent: #6b4200` there.

    So this resolves both sides of every rule that declares a background and a
    colour, in each of the three themes the stylesheet defines, and divides.
    """

    from _contrast import (at_rule_block, colour_rules, composite, contrast,
                           parse_colour, resolve_var)

    style = _strip_comments(_style())
    tokens = TOKENS.read_text(encoding="utf-8")
    base = at_rule_block(style, ":root")

    LIGHT = "@media (prefers-color-scheme: light)"
    PRINT = "@media print"
    scopes = {
        "dark (default)": (base, tokens),
        "light": (at_rule_block(style, LIGHT), base, tokens),
        "print": (at_rule_block(style, PRINT), base, tokens),
    }
    # A rule inside one theme's block is only painted in that theme.
    applies_in = {"": set(scopes), LIGHT: {"light"}, PRINT: {"print"}}

    checked: list[str] = []
    failures: list[str] = []
    for theme, sources in scopes.items():
        def value(expression: str) -> str | None:
            try:
                return resolve_var(expression, *sources)
            except (KeyError, ValueError):
                return None

        # Cascade within the theme: a base rule and the print block's override
        # of the same selector are one painted result, not two.
        painted: dict[str, dict[str, str]] = {}
        for context, selector, declarations in colour_rules(style):
            if theme not in applies_in.get(context, set(scopes)):
                continue
            painted.setdefault(selector, {}).update(declarations)

        for selector, declarations in painted.items():
            background = declarations.get("background-color") or declarations.get("background")
            foreground = declarations.get("color")
            if not background or not foreground:
                continue
            if foreground == "inherit":
                foreground = "var(--ink)"
            if background in {"transparent", "none"}:
                background = "var(--surface)"
            resolved_bg, resolved_fg = value(background), value(foreground)
            if resolved_bg is None or resolved_fg is None:
                continue
            # A translucent background is not a colour until you say what is
            # behind it. `contrast()` flattens a translucent foreground; the
            # background has to be flattened onto the page surface here.
            try:
                if parse_colour(resolved_bg)[3] < 1:
                    behind = value("var(--surface)")
                    if behind is None:
                        continue
                    resolved_bg = composite(resolved_bg, behind)
            except ValueError:
                continue
            try:
                ratio = contrast(resolved_fg, resolved_bg)
            except ValueError:
                continue
            checked.append(f"{theme} {selector}")
            if ratio < MINIMUM_RATIO:
                failures.append(
                    f"{theme}: `{selector}` is {ratio}:1 "
                    f"({resolved_fg} on {resolved_bg}), needs {MINIMUM_RATIO}"
                )

    # A resolver that silently stops resolving turns this whole test green, so
    # the count is asserted too: 7 unscoped rules x 3 themes, plus 2 in print.
    assert len(checked) >= 18, (
        f"only {len(checked)} pairs resolved — the var() resolution is broken, "
        f"not the palette: {checked}"
    )
    assert not failures, "\n".join(failures)
