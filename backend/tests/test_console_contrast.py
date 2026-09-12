"""Every foreground the two consoles paint on their own background, measured.

`--warning` and `--on-warning-soft` are two tokens two lines apart. One is the
colour of a warning; the other is the colour of *text on a warning*. Studio
Admin used the first as text in three places — `.pill.pending`,
`.surface-health.warn`, `.badge.amber` — at 4.04:1, while using the correct one
in ten others. Super Admin got all of its right. Nothing could see the
difference, because the existing console gate
(`test_platform_console.py::test_every_documented_pair_measures`) only checks
pairs somebody thought to document, and nobody documents the ones they got
wrong.

So this resolves both sides of every rule in both consoles and divides. It is
the same machinery the manual uses; the palette comes from console-theme.css.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from _contrast import at_rule_block, colour_rules, composite, contrast, parse_colour, resolve_var

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
THEME = (REPOSITORY_ROOT / "backend/frontend/assets/console-theme.css").read_text(encoding="utf-8")
TOKENS = (REPOSITORY_ROOT / "backend/frontend/assets/ui-tokens.css").read_text(encoding="utf-8")

CONSOLES = {
    "studio-admin": REPOSITORY_ROOT / "backend/frontend/studio-admin.html",
    "super-admin": REPOSITORY_ROOT / "super-admin.html",
}

MINIMUM_RATIO = 4.5

# Selectors whose text is genuinely large (>= 18.66px bold or 24px regular),
# where WCAG 1.4.3 allows 3:1. Each needs the size that justifies it.
LARGE_TEXT = {
    ".stat .n": "2.058rem",
    ".kpi-value": "1.618rem",
}

# Pairs that are not text at all, or are painted over something this parser
# cannot see (a gradient, an image, a JS-set inline style).
NOT_A_TEXT_PAIR: set[tuple[str, str]] = set()


def _inline_css(page: Path) -> str:
    source = page.read_text(encoding="utf-8")
    blocks = []
    cursor = 0
    while True:
        start = source.find("<style", cursor)
        if start < 0:
            break
        opening = source.index(">", start) + 1
        end = source.index("</style>", opening)
        blocks.append(source[opening:end])
        cursor = end
    return "\n".join(blocks)


@pytest.mark.parametrize("console", sorted(CONSOLES))
def test_no_console_rule_paints_illegible_text(console: str) -> None:
    style = _inline_css(CONSOLES[console])
    base = at_rule_block(THEME, ":root")
    sources = (base, THEME, TOKENS)

    def value(expression: str) -> str | None:
        try:
            return resolve_var(expression, *sources)
        except (KeyError, ValueError):
            return None

    surface = value("var(--bg)") or value("var(--surface)") or "#ffffff"

    # A state rule usually restates only what changes. `.btn-warning:hover`
    # swapped the ground and said nothing about the text, so the pair only
    # exists once the base rule is folded in — and that pair was 3.11:1, a
    # control that becomes unreadable at the moment you point at it. Matching
    # rule-by-rule would never see it.
    painted: dict[str, dict[str, str]] = {}
    for _context, selector, declarations in colour_rules(style):
        for one in (part.strip() for part in selector.split(",")):
            painted.setdefault(one, {}).update(declarations)
    for selector, declarations in list(painted.items()):
        base = selector.split(":")[0]
        if base != selector and base in painted and "color" not in declarations:
            inherited = painted[base].get("color")
            if inherited:
                declarations["color"] = inherited

    checked, failures = 0, []
    for selector, declarations in painted.items():
        background = declarations.get("background-color") or declarations.get("background")
        foreground = declarations.get("color")
        if not background or not foreground:
            continue
        if (console, selector) in NOT_A_TEXT_PAIR:
            continue
        if background in {"transparent", "none", "inherit"}:
            continue
        resolved_bg, resolved_fg = value(background), value(foreground)
        if resolved_bg is None or resolved_fg is None:
            continue
        try:
            if parse_colour(resolved_bg)[3] < 1:
                resolved_bg = composite(resolved_bg, surface)
            ratio = contrast(resolved_fg, resolved_bg)
        except ValueError:
            continue
        checked += 1
        threshold = 3.0 if selector in LARGE_TEXT else MINIMUM_RATIO
        if ratio < threshold:
            failures.append(
                f"`{selector}` is {ratio}:1 ({resolved_fg} on {resolved_bg}), "
                f"needs {threshold} — {foreground} on {background}"
            )

    assert checked >= 20, (
        f"only {checked} pairs resolved in {console}; the parse is broken, not "
        f"the palette"
    )
    assert not failures, f"{console}:\n  " + "\n  ".join(failures)


def test_the_hover_state_is_measured_too() -> None:
    """`.btn-warning:hover` swapped the ground and kept the text: a control
    that becomes unreadable at the moment you point at it. The parser above
    treats `:hover` as its own selector, so this only asserts that it did."""

    style = _inline_css(CONSOLES["super-admin"])
    hovers = [selector for _c, selector, decls in colour_rules(style)
              if ":hover" in selector and ("background" in decls or "background-color" in decls)]
    assert len(hovers) >= 5, f"only {len(hovers)} hover rules found — the parse missed them"


RATIO_COMMENT = re.compile(
    r"color:\s*(var\(--[\w-]+\)|#[0-9a-fA-F]{3,8})\s*;?\s*/\*\s*([\d.]+):1\s+on\s+(--[\w-]+)")


@pytest.mark.parametrize("console", sorted(CONSOLES))
def test_a_ratio_written_in_a_comment_is_the_ratio(console: str) -> None:
    """Five of these were wrong at once, and three named tokens that had been
    deleted — `--amber-light`, `--green-light`, `--neutral-light`. A comment
    claiming 6.37:1 beside a pair measuring 4.52:1 is worse than no comment:
    the next person reads it instead of measuring, and the repository is full
    of people who did."""

    style = _inline_css(CONSOLES[console])
    base = at_rule_block(THEME, ":root")
    wrong = []
    for match in RATIO_COMMENT.finditer(style):
        foreground, claimed, background = match.group(1), float(match.group(2)), match.group(3)
        try:
            measured = contrast(resolve_var(foreground, base, THEME, TOKENS),
                                resolve_var(f"var({background})", base, THEME, TOKENS))
        except (KeyError, ValueError) as exc:
            wrong.append(f"`{foreground} on {background}` cannot be resolved: {exc}")
            continue
        if abs(measured - claimed) > 0.06:
            wrong.append(
                f"`{foreground}` on `{background}`: comment says {claimed}:1, "
                f"measures {measured}:1")
    assert not wrong, f"{console}:\n  " + "\n  ".join(wrong)
