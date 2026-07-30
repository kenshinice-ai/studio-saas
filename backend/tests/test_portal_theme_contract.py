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

SURFACES = {
    "portal": (
        REPOSITORY_ROOT / "tenant-template" / "index.html",
        r"THEME_TOKENS\s*=\s*\{(.*?)\n\s*\};",
    ),
    "register": (
        REPOSITORY_ROOT / "tenant-template" / "register.html",
        r"THEME_TOKENS\s*=\s*\{(.*?)\n\s*\};",
    ),
    "cms": (
        REPOSITORY_ROOT / "legacy-root" / "index.html",
        r"themeVars\s*=\s*\{(.*?)\n\s*\};",
    ),
}

# The API field names that /v1/public/<slug>/brand reports under visualTheme.
# Sourced from backend/studiosaas/presets.py VISUAL_STYLE_PRESETS.
THEME_FIELDS = frozenset({
    "background_color", "background_alt_color", "panel_color",
    "text_color", "text_soft_color", "muted_text_color",
    "border_color", "border_strong_color",
    "accent_color", "accent_hover_color", "accent_pressed_color", "accent_text_color",
    "secondary_accent_color", "secondary_text_color",
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


def test_the_three_surfaces_agree_field_for_field() -> None:
    """Portal, register and CMS must map the identical field set.

    Equality rather than 'each is complete': if a new token is added to the
    presets, this fails on the first surface to adopt it, which is the moment
    the drift starts — not months later when someone notices a colour is off.
    """

    portal, register, cms = (_mapped_fields(s) for s in ("portal", "register", "cms"))
    assert portal == register == cms, (
        "theme maps have drifted apart:\n"
        f"  only in portal:   {sorted(portal - register - cms)}\n"
        f"  only in register: {sorted(register - portal - cms)}\n"
        f"  only in cms:      {sorted(cms - portal - register)}"
    )


def test_cms_base_background_follows_the_tenant_theme() -> None:
    """The always-on CMS background must be the tenant's, not a fixed grey.

    Scope note: this covers the base rule only. A second, separate dark system
    still lives in the `@media (prefers-color-scheme: dark)` block further down
    the same file, and it does use `!important`. Merging the two dark systems is
    plan item #29 in docs/design/UI_UX_Upgrade_Plan_2026-07-30.md and is not
    attempted here — a partial merge would leave Tailwind surfaces dark while
    the page background followed a light tenant theme, which is worse than
    either system alone. The test is written to fail if the BASE rule regresses,
    and deliberately not to assert anything about the media block, so it does
    not quietly start passing when #29 lands.
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


def test_the_second_cms_dark_system_is_still_recorded_as_open() -> None:
    """Keep the known gap visible instead of letting it fade into the file.

    If someone removes the OS dark block, or finishes #29, this fails and forces
    the plan and the handoff to be updated rather than drifting out of date.
    """

    cms = _read(REPOSITORY_ROOT / "legacy-root" / "index.html")
    assert "@media (prefers-color-scheme: dark)" in cms
    assert "background:#0e1016 !important" in cms, (
        "the OS dark-mode block changed. Plan item #29 (merge the two CMS dark "
        "systems) may now be done or partly done — update the plan, the handoff "
        "and this test together."
    )


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


def test_every_brand_shade_the_cms_uses_is_re_pointed_at_the_theme() -> None:
    """Whatever shades the app uses, the shell must override all of them."""

    used = set(BRAND_UTILITY.findall(_read(CMS_APP)))
    shell = _read(CMS_SHELL)
    uncovered = sorted(
        shade for shade in used
        if not re.search(rf'\[class\*="(?:bg|text|border|from|to|via)-(?:indigo|purple)-{shade[0]}', shell)
    )
    assert not uncovered, (
        f"cms-app.jsx uses indigo/purple shades {uncovered} that "
        "legacy-root/index.html never re-points at the tenant theme. Those "
        "surfaces stay Tailwind-coloured while the rest of the CMS follows the "
        "studio's palette."
    )


def test_dark_cms_chrome_inverts_the_asserted_pair() -> None:
    """The sidebar cannot rely on a fixed `text-white`.

    `bg-indigo-900 text-white` is only readable while the surface stays dark.
    Once the surface follows the tenant theme it has to bring its foreground
    with it, and --ink/--bg is the pair the generator already guarantees.
    """

    shell = _read(CMS_SHELL)
    assert 'background-color:var(--ink) !important' in shell
    assert "color:var(--bg) !important" in shell
    # The pill inset must be expressed relative to the page colour, not by
    # assuming darker means deeper — that assumption inverts under a dark theme.
    assert "color-mix(in srgb, var(--ink) 86%, var(--bg))" in shell
