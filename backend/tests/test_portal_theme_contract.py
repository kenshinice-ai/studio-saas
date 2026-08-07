"""The public portal must read theme tokens, never pin its own colours.

Why this file exists: the registration success card carried
`background:var(--ink); color:#EFE9DD`. `--ink` is the tenant theme's
`text_color`, so under any of the seven dark theme-modes it resolves to a LIGHT
colour and that fixed text measured 1.06:1 — the card a family sees after
submitting an enrolment was invisible, and no test noticed because the light
themes it was designed against were fine.

A fixed hex beside a themed value is the failure shape, not the specific hex.
These tests forbid the shape.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = (
    REPOSITORY_ROOT / "tenant-template" / "index.html",
    REPOSITORY_ROOT / "tenant-template" / "register.html",
)

# `:root` in portal-theme.css is the one place allowed to state literal colours:
# it is the fallback palette used before /brand answers.
TOKEN_SOURCE = REPOSITORY_ROOT / "backend" / "frontend" / "assets" / "portal-theme.css"

DECLARATION = re.compile(
    r"(?<![-\w])(color|background|background-color|border-color|border-top-color"
    r"|border-bottom-color|border-left-color|border-right-color|outline-color)"
    r"\s*:\s*(#[0-9A-Fa-f]{3,8})",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# Text laid over a photograph is the one honest exception: behind it is a
# student's artwork under a dark scrim, not a theme surface, so there is no
# token that describes it. The exception is recognised by the scrim itself
# rather than allow-listed by hex value — remove the gradient or the shadow and
# the colour becomes an offender again.
SCRIM = re.compile(r"linear-gradient\([^)]*rgba\(|text-shadow\s*:\s*[^;']*rgba\(")


def _sits_on_media(source: str, position: int) -> bool:
    """Whether the declaration at `position` is inside a rule that draws a scrim."""

    start = max(source.rfind("{", 0, position), source.rfind("'", 0, position))
    end = source.find("}", position)
    quote_end = source.find("'", position)
    if quote_end != -1 and (end == -1 or quote_end < end):
        end = quote_end
    return bool(SCRIM.search(source[start if start != -1 else 0 : end if end != -1 else len(source)]))


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_template_pins_no_literal_colour(template: Path) -> None:
    """No colour declaration on a themed surface may name a literal hex.

    Every surface a tenant themes has to resolve through a custom property, or
    a studio that picks one of the eight palettes gets a page that is partly
    theirs and partly whatever looked right on the author's screen.
    """

    source = _read(template)
    offenders = sorted({
        match.group(0)
        for match in DECLARATION.finditer(source)
        if not _sits_on_media(source, match.start())
    })
    assert not offenders, (
        f"{template.name} pins literal colours: {offenders}. "
        "Use the theme custom properties (--ink, --bg, --muted, --warning, …); "
        "the fallback palette belongs in assets/portal-theme.css."
    )


def test_success_card_inverts_the_asserted_contrast_pair() -> None:
    """The success card must pair --ink with --bg, not with a chosen colour.

    palette_gen.py asserts `text_color` against `background_color` at 4.5:1 for
    all 15 theme-modes ('body / page'). Inverting that exact pair is the only
    ink-surface treatment that inherits the guarantee instead of re-deriving it.
    """

    portal = _read(REPOSITORY_ROOT / "tenant-template" / "index.html")
    card = re.search(r"\.result-card\{[^}]*\}", portal)
    assert card, "the .result-card rule disappeared"
    assert "background:var(--ink)" in card.group(0)
    assert "color:var(--bg)" in card.group(0)

    big = re.search(r"\.result-card \.big\{[^}]*\}", portal)
    assert big, "the .result-card .big rule disappeared"
    assert "color:var(--bg)" in big.group(0)


def test_generator_still_asserts_the_pair_the_card_relies_on() -> None:
    """Guard the assumption itself.

    If someone relaxes the generator's 'body / page' check, the success card
    silently loses its guarantee. Fail here instead, next to the reason.
    """

    generator = _read(REPOSITORY_ROOT / "docs" / "design" / "palette_gen.py")
    assert "('body / page',        'text_color',           'background_color', 4.5)" in generator, (
        "palette_gen.py no longer asserts text_color vs background_color at 4.5:1. "
        "tenant-template/index.html .result-card depends on that pair."
    )


def test_degraded_surface_band_uses_the_theme_semantic_colour() -> None:
    """The 'content failed to load' band must be themed, not a fixed yellow.

    It is position:fixed across the top of the page, so a light band on a dark
    theme is the most visible possible way to look broken.
    """

    portal = _read(REPOSITORY_ROOT / "tenant-template" / "index.html")
    assert "note.className='note brand-status'" in portal
    assert "note.dataset.tone='warning'" in portal
    band = re.search(r"\.surface-status \.note\{[^}]*\}", portal)
    assert band, "the .surface-status .note rule disappeared"
    assert "var(--warning)" in band.group(0)


def test_portal_theme_css_remains_the_single_fallback_palette() -> None:
    """The literals have to live somewhere; that somewhere is one file."""

    tokens = _read(TOKEN_SOURCE)
    assert ":root" in tokens
    assert "--ink" in tokens and "--bg" in tokens


@pytest.mark.parametrize("template", TEMPLATES, ids=lambda p: p.name)
def test_consent_checkbox_restores_a_visible_native_checked_state(template: Path) -> None:
    """A checked consent control must visibly draw its tick.

    The portal's general text-input rule uses ``appearance:none``.  A consent
    checkbox inherits that rule unless its narrow selector restores the native
    control, leaving a clickable but permanently empty-looking box.
    """

    source = _read(template)
    checkbox_rule = re.search(r"\.consent(?:-touch)? input\[type=\"checkbox\"\]\s*\{[^}]*\}", source)
    assert checkbox_rule, f"{template.name} has no dedicated consent checkbox rule"
    declaration = checkbox_rule.group(0)
    assert "appearance:auto" in declaration
    assert "-webkit-appearance:checkbox" in declaration
    assert "accent-color:var(--clay)" in declaration
    assert "padding:0" in declaration


# ── The publish chain ────────────────────────────────────────────────────────
# A studio edits its brand once, in Studio Admin, and publishes. Everything a
# family or a staff member then sees — the portal, the registration page and the
# CMS — has to reflect that one edit. The three surfaces each own a declarative
# map from the API's theme fields to CSS custom properties, and the way this
# breaks is not a crash: one map quietly carries fewer keys than the others, so
# the studio's choice lands on two surfaces out of three.
#
# That is exactly what had happened. The CMS map carried 10 of 21 fields —
# missing border_strong_color, the accent hover/pressed states, focus_ring_color,
# the disabled pair and the scrim — while a `background:#f1f5f9 !important`
# outranked whatever background did arrive. Every tenant's CMS looked the same.

# v8.9.0. The three public pages no longer carry a map each — portal, register
# and the new timetable page all call `/assets/portal-brand.js`.
#
# Two copies had already drifted (`accent_color` mapped to two variables in one
# and three in the other) and a third was about to be written, which is the
# moment the equality test below stopped being a safeguard and started being a
# reason to keep writing copies. The CMS keeps its own map: it is a different
# application with a different variable vocabulary, not a public surface.
SURFACES = {
    "public": (
        REPOSITORY_ROOT / "backend" / "frontend" / "assets" / "portal-brand.js",
        r"THEME_TOKENS\s*=\s*\{(.*?)\n\s*\};",
    ),
    "cms": (
        REPOSITORY_ROOT / "legacy-root" / "index.html",
        r"themeVars\s*=\s*\{(.*?)\n\s*\};",
    ),
}

# Every page that renders a tenant's palette in public. Each must LOAD the one
# module and must not re-declare the map — a page with its own copy is a page
# that will one day render half a theme with no error anywhere.
PUBLIC_PAGES = (
    REPOSITORY_ROOT / "tenant-template" / "index.html",
    REPOSITORY_ROOT / "tenant-template" / "register.html",
    REPOSITORY_ROOT / "tenant-template" / "timetable.html",
)

# The API field names that /v1/public/<slug>/brand reports under visualTheme.
# Sourced from backend/studiosaas/presets.py VISUAL_STYLE_PRESETS.
THEME_FIELDS = frozenset({
    "background_color", "background_alt_color", "panel_color",
    "text_color", "text_soft_color", "muted_text_color",
    "border_color", "border_strong_color",
    "accent_color", "accent_hover_color", "accent_pressed_color", "accent_text_color",
    "secondary_accent_color",
    "success_color", "warning_color", "danger_color",
    "focus_ring_color", "disabled_surface_color", "disabled_text_color",
    "scrim_color",
})


def _mapped_fields(surface: str) -> set[str]:
    path, pattern = SURFACES[surface]
    body = re.search(pattern, _read(path), re.S)
    assert body, f"the theme map in {path.name} could not be located"
    return set(re.findall(r"^\s*([a-z_]+):\s*\[", body.group(1), re.M))


@pytest.mark.parametrize("surface", sorted(SURFACES))
def test_surface_maps_every_theme_field(surface: str) -> None:
    """Each tenant surface must consume the whole theme, not a subset."""

    missing = THEME_FIELDS - _mapped_fields(surface)
    assert not missing, (
        f"the {surface} theme map is missing {sorted(missing)}. "
        "A studio that picks one of the eight palettes would get that surface "
        "only partly themed, and nothing would report an error."
    )


def test_the_two_surfaces_agree_field_for_field() -> None:
    """The public module and the CMS must map the identical field set.

    Equality rather than 'each is complete': if a new token is added to the
    presets, this fails on the first surface to adopt it, which is the moment
    the drift starts — not months later when someone notices a colour is off.
    """

    public, cms = (_mapped_fields(s) for s in ("public", "cms"))
    assert public == cms, (
        "theme maps have drifted apart:\n"
        f"  only in the public module: {sorted(public - cms)}\n"
        f"  only in the CMS:           {sorted(cms - public)}"
    )


@pytest.mark.parametrize("page", PUBLIC_PAGES, ids=lambda p: p.name)
def test_a_public_page_uses_the_shared_theme_module_and_owns_no_map(page: Path) -> None:
    """One source, three surfaces — enforced, not merely intended.

    Before v8.9.0 the portal and the register page each held a full copy of the
    token map. They had already diverged on `accent_color`, and neither test
    nor eye caught it, because a partly-applied theme looks like a design
    choice rather than a bug.

    So the rule is both halves: load the module, and declare no map. Either one
    alone lets a copy creep back in beside a call that still looks correct.
    """

    source = _read(page)
    assert "/assets/portal-brand.js" in source, (
        f"{page.name} does not load the shared theme module"
    )
    assert "applyVisualTheme" in source, (
        f"{page.name} loads the module but never applies the theme"
    )
    assert not re.search(r"THEME_TOKENS\s*=\s*\{", source), (
        f"{page.name} declares its own token map again — that is the drift "
        "this module exists to end"
    )


def test_cms_base_background_follows_the_tenant_theme() -> None:
    """The always-on CMS background must be the tenant's, not a fixed grey.

    The OS preference is now only a pre-brand token fallback. Once /brand has
    answered, the tenant role map owns the page in either colour scheme.
    """

    cms = _read(REPOSITORY_ROOT / "legacy-root" / "index.html")
    # Source order: the OS dark-mode block comes FIRST in this file, and the
    # always-on rule follows it. Match the always-on rule by what it is — a
    # top-level `body {` with a background — rather than by position, so that
    # reordering the stylesheet does not silently disarm the check.
    candidates = [
        match.group(0)
        for match in re.finditer(r"\n        body \{[^}]*background[^}]*\}", cms)
    ]
    assert candidates, "the always-on CMS body background rule disappeared"
    base = candidates[-1]
    assert "!important" not in base, (
        f"the always-on CMS body background is forced again ({base.strip()}); "
        "a tenant theme cannot win against !important and every studio's CMS "
        "looks identical."
    )
    assert "var(--bg" in base


def test_cms_dark_mode_has_one_token_owner() -> None:
    """OS dark mode may seed tokens but must not repaint Tailwind utilities."""

    cms = _read(REPOSITORY_ROOT / "legacy-root" / "index.html")
    assert "@media (prefers-color-scheme: dark)" in cms
    assert 'html:not([data-brand-scheme]) {' in cms
    assert 'html[data-brand-scheme="dark"] { color-scheme:dark; }' in cms
    assert 'html[data-brand-scheme="light"] { color-scheme:light; }' in cms
    assert ".bg-white { background:#1a1d27 !important; }" not in cms
    assert "background:#0e1016 !important" not in cms


# ── CMS Tailwind shade coverage ──────────────────────────────────────────────
# The CMS is a Tailwind app whose brand colours are indigo/purple utility
# classes. legacy-root/index.html re-points those at the tenant theme. The
# failure mode is not a crash and not an obviously wrong colour: the override
# list covers SOME shades. It covered 50/100/600/700, so a studio on the clay
# palette got a clay content area beside a `bg-indigo-900` sidebar — the
# unthemed slab is more conspicuous than no theming at all would have been.

CMS_SHELL = REPOSITORY_ROOT / "legacy-root" / "index.html"
CMS_APP = REPOSITORY_ROOT / "legacy-root" / "src" / "cms-app.jsx"
BRAND_UTILITY = re.compile(r"(?:bg|text|border|from|to|via)-(?:indigo|purple)-(\d{2,3})")


# Every Tailwind colour family the CMS could use. Listing them explicitly (as
# opposed to matching "any word") is deliberate: a typo like `bg-grey-50` should
# read as an unknown class, not silently pass as a covered family.
TAILWIND_FAMILIES = (
    "slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald"
    "|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose"
)
COLOUR_UTILITY = re.compile(
    rf"(bg|text|border|from|to|via|divide)-({TAILWIND_FAMILIES})-(\d{{2,3}})"
)
SHELL_OVERRIDE = re.compile(r'\[class\*="([a-zA-Z0-9\\/.-]+)"\]')


def test_the_cms_configures_tailwind_instead_of_patching_it() -> None:
    """The CMS runs the Tailwind Play CDN, which generates utilities in the
    browser from `tailwind.config`.

    Until v8.4.2 it instead carried 68 rules of `[class*="bg-indigo-"]`
    overrides chasing what the generator had already emitted. That layer
    reached 84 of the 154 colour utilities the app renders; the other 70
    painted fixed Tailwind values no theme could touch. Patching could never
    converge, because every new component brings new utilities.
    """

    shell = _read(CMS_SHELL)
    assert "tailwind.config = config" in shell, "the generator is not configured"
    # Every family the source renders must be mapped.
    source = (REPOSITORY_ROOT / "legacy-root/src/cms-app.jsx").read_text(encoding="utf-8")
    families = set(re.findall(
        r"\b(?:bg|text|border|from|to|via|ring|divide|placeholder)-"
        r"(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|"
        r"teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3}\b", source))
    block = shell[shell.index("const colours = {"):]
    block = block[:block.index("};")]
    missing = [f for f in families if not re.search(rf"\b{f}:", block)]
    assert not missing, f"families the CMS renders but the config never maps: {sorted(missing)}"


def test_the_neutral_ramp_inverts_and_the_role_ramps_do_not() -> None:
    """The distinction the override layer never made, and could not have.

    `bg-gray-50` is a surface and `text-gray-900` is ink, and those swap in
    dark. But `bg-red-600` is a red button in both modes, and `bg-indigo-700`
    — every filled action in this app, 保存 / 刷新 / 签到 / 退出登录 — is a deep
    brand slab carrying light text in both. A rule that flips everything breaks
    the buttons; a rule that flips nothing breaks the page.

    Measured in the browser at v8.4.2 with a dark theme applied: bg-gray-50
    luminance 0.011 against text-gray-900 at 0.808 (inverted), while
    bg-indigo-700 stayed a filled 0.378 and white-on-it measured 5.49:1.
    """

    shell = _read(CMS_SHELL)
    neutral = shell[shell.index("const neutral = {"):]
    neutral = neutral[:neutral.index("};")]
    # It inverts for free only if it is built from --bg and --ink, which swap.
    assert "'var(--bg2)'" in neutral and "'var(--ink)'" in neutral
    assert "--accent" not in neutral, "the neutral ramp must not carry a role colour"

    role = shell[shell.index("const role = (base) => ({"):]
    role = role[:role.index("});")]
    # A role's deep end is hover/pressed, which the generator already moves in
    # the mode-correct direction, so a filled button stays a filled button.
    assert "-hover" in role and "-pressed" in role
    assert "--bg" not in role and "--ink" not in role, (
        "a role ramp must not reach for the page or the ink; that is what flips"
    )


def test_white_serves_both_the_card_and_the_label_on_a_fill() -> None:
    """183 `-white` utilities, and one value for all of them.

    `bg-white` is a card and `text-white` is the label on a filled button.
    Tailwind cannot tell them apart — `colors.white` is one value — so this
    only works if --panel clears 4.5:1 on every accent. It does: worst is 5.10
    at arcade-lime dark, so no source change was needed.
    """

    from studiosaas.presets import VISUAL_STYLE_PRESETS, style_theme

    assert "white: 'var(--panel)'" in _read(CMS_SHELL)
    worst = min(
        _contrast(theme["panel_color"], theme["accent_color"])
        for key, preset in VISUAL_STYLE_PRESETS.items()
        for theme in (style_theme(key, mode) for mode in preset["modes"])
    )
    assert worst >= 4.5, f"--panel only reaches {worst:.2f}:1 on the worst accent"


def _contrast(a: str, b: str) -> float:
    def lum(value: str) -> float:
        value = value.lstrip("#")
        channels = [int(value[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    first, second = lum(a), lum(b)
    return (max(first, second) + 0.05) / (min(first, second) + 0.05)


# ── the fallback palette is a generated palette ─────────────────────────────

PORTAL_DEFAULT_TOKENS = {
    "--bg": "background_color", "--bg2": "background_alt_color",
    "--panel": "panel_color", "--surface": "panel_color",
    "--ink": "text_color", "--ink2": "text_soft_color", "--muted": "muted_text_color",
    "--line": "border_color", "--line-strong": "border_strong_color",
    "--clay": "accent_color", "--clay-hover": "accent_hover_color",
    "--clay-pressed": "accent_pressed_color", "--clay-d": "secondary_accent_color",
    "--on-accent": "accent_text_color",
    "--success": "success_color", "--warning": "warning_color", "--danger": "danger_color",
    "--focus-ring": "focus_ring_color",
    "--disabled-surface": "disabled_surface_color", "--disabled-text": "disabled_text_color",
}


def test_the_fallback_palette_matches_the_theme_it_claims_to_be() -> None:
    """portal-theme.css says its defaults are vintage-press light. Check it.

    The file has carried the instruction "keep the two in step" since it was
    written, and nothing enforced it. At v8.4.0 seven of the twenty-one had
    drifted, and two were not near-misses: --warning was #8D6426 where the
    generator produces #5B421F, --danger #B6483A against #76332A. Those are the
    colours every public page renders between first paint and the /brand
    response, and on a page whose theme never loads they are the final answer.

    This asserts the whole set rather than the seven, because the next drift
    will be in a different token.
    """

    from studiosaas.presets import DEFAULT_STYLE_ID, style_theme

    default = style_theme(DEFAULT_STYLE_ID, "light")
    css = TOKEN_SOURCE.read_text(encoding="utf-8")
    root = css[css.index(":root {"):css.index("\n}", css.index(":root {"))]
    declared = dict(re.findall(r"^\s*(--[\w-]+):\s*(#[0-9a-fA-F]{6})", root, re.M))
    drifted = []
    for name, key in PORTAL_DEFAULT_TOKENS.items():
        assert name in declared, f"{name} is no longer declared in portal-theme.css"
        if declared[name].upper() != default[key].upper():
            drifted.append(f"{name}: css={declared[name]} generated={default[key]}")
    assert not drifted, (
        f"portal-theme.css has drifted from {DEFAULT_STYLE_ID} light:\n  "
        + "\n  ".join(drifted)
    )
