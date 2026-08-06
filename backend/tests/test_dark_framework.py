"""The surfaces a palette cannot reach, and who decides light or dark.

Every colour in this product is solved and asserted, and the tenant portal
still rendered wrong in dark mode, because three whole categories of surface
are not in the palette at all:

* **Native chrome.** Scrollbars, the `<select>` popup, checkbox and radio
  boxes, the autofill wash, the caret, the default `::placeholder`. None of
  them read a custom property; the only control is `color-scheme`, and it was
  declared on date inputs only. Measured on production at v8.3.1:
  `getComputedStyle(:root).colorScheme` was `normal` on a portal carrying a
  dark theme, with 11 text inputs, 2 selects, 2 checkboxes and a textarea on
  the page.
* **Literals.** The back-to-top button was `rgba(251,249,244,.9)` under
  `color: var(--ink)`. On the eight dark themes `--ink` is a light colour, so
  the arrow measured 1.26:1 against its own button — in the DOM, clickable,
  invisible.
* **Browser chrome.** `<meta name="theme-color">` was pinned to `#F4F0E8` and
  never updated, so a dark studio got a cream address bar over a #15120D page.

The fourth category is not a surface but a question: who chooses. Before
v8.4.0 the studio always did. `system` hands it to the visitor, and is only
offered where both palettes were published.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BRAND_SYSTEM = REPOSITORY_ROOT / "backend/frontend/assets/brand-system.css"
PORTAL = REPOSITORY_ROOT / "tenant-template/index.html"
REGISTER = REPOSITORY_ROOT / "tenant-template/register.html"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


# ── native chrome ───────────────────────────────────────────────────────────

def test_color_scheme_is_declared_on_the_root_and_follows_the_theme() -> None:
    css = _read(BRAND_SYSTEM)
    assert ":root { color-scheme: light; }" in css
    assert ':root[data-brand-scheme="dark"] { color-scheme: dark; }' in css


def test_color_scheme_is_not_scoped_to_date_inputs_any_more() -> None:
    """The old rule covered three input types and nothing else.

    It read as if dark mode was handled. It handled the date picker.
    """

    css = strip_comments(_read(BRAND_SYSTEM))
    scoped = re.findall(r"[^\n{]*color-scheme[^\n}]*", css)
    for rule in scoped:
        assert "input[type=" not in rule, f"color-scheme is still input-scoped: {rule.strip()}"


@pytest.mark.parametrize("selector", ["::selection", "::placeholder", "-webkit-autofill"])
def test_the_browser_drawn_surfaces_are_themed(selector: str) -> None:
    """Each of these is painted from a browser default unless told otherwise,
    and each of them lands on a theme surface."""

    assert selector in _read(BRAND_SYSTEM), f"{selector} is not themed"


def test_the_placeholder_opacity_is_reset() -> None:
    """Firefox dims placeholders to ~54%, which drops a 4.6:1 muted below 3."""

    css = _read(BRAND_SYSTEM)
    block = css[css.index(":where(input, textarea)::placeholder"):]
    assert "opacity: 1;" in block[:200]


# ── literals on a themed page ───────────────────────────────────────────────

@pytest.mark.parametrize("page", ["tenant-template/index.html", "tenant-template/register.html"])
def test_no_tenant_surface_paints_with_a_literal(page: str) -> None:
    """A fixed hex beside a themed value is the failure shape.

    `.totop` had `background: rgba(251,249,244,.9)` with `color: var(--ink)`,
    which is fine in the light themes it was written against and 1.26:1 in
    every dark one.
    """

    source = strip_comments(_read(REPOSITORY_ROOT / page))
    body = source[source.index("<style"):]
    literals = re.findall(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", body)
    assert not literals, f"{page} paints with literals: {sorted(set(literals))}"


def test_the_back_to_top_button_carries_the_theme() -> None:
    source = _read(PORTAL)
    rule = source[source.index(".totop{"):source.index("}", source.index(".totop{"))]
    assert "var(--panel)" in rule and "var(--ink)" in rule
    assert "251,249,244" not in rule


# ── the inverted band ───────────────────────────────────────────────────────

def test_the_inverted_band_redeclares_the_tokens_it_inverts() -> None:
    """`.parent` uses --ink as a SURFACE, so everything solved against the page
    is wrong inside it.

    Its own children were written as color-mix(--bg,--ink) pairs and were
    correct. Two global classes dropped into it were not: `.eyebrow` measured
    2.40:1 on a dark theme and `.arw` measured 1.84:1 dark / 2.02:1 light — so
    the arrow had never cleared 3:1 in either mode, in the section that asks a
    parent to sign in.
    """

    source = _read(PORTAL)
    block = source[source.index(".parent{"):source.index("}", source.index(".parent{"))]
    for token in ("--muted:", "--ink2:", "--line:", "--clay:"):
        assert token in block, f"{token} is not re-declared on the inverted band"


# ── browser chrome ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("page", [PORTAL, REGISTER])
def test_the_address_bar_colour_follows_the_theme(page: Path) -> None:
    source = _read(page)
    assert 'name="theme-color"' in source
    assert 'meta[name="theme-color"]' in source, "nothing updates it at runtime"
    assert "setAttribute('content', page)" in source or 'setAttribute("content", page)' in source


def test_the_pinned_address_bar_colour_is_gone() -> None:
    """#F4F0E8 was neither the current default nor any theme's page colour."""

    source = strip_comments(_read(PORTAL))
    assert "#F4F0E8" not in source


# ── who decides ─────────────────────────────────────────────────────────────

def test_the_preference_is_validated_and_system_needs_both_modes() -> None:
    from studiosaas.api_v1 import _normalize_visual_theme

    both = _normalize_visual_theme({"style_id": "vintage-press", "scheme_preference": "system"})
    assert both["scheme_preference"] == "system"

    for value in ("light", "dark"):
        pinned = _normalize_visual_theme({"style_id": "vintage-press", "scheme_preference": value,
                                          "color_scheme": value})
        assert pinned["scheme_preference"] == value

    with pytest.raises(ValueError):
        _normalize_visual_theme({"style_id": "vintage-press", "scheme_preference": "auto"})


def test_a_single_mode_theme_cannot_follow_the_visitor() -> None:
    """arcade-lime is dark only — its accent turns olive on a light page.

    Accepting `system` there would mean either rendering a dark theme's tokens
    on a light surface, or ignoring the setting. Both are worse than refusing.
    """

    from studiosaas.api_v1 import _normalize_visual_theme

    with pytest.raises(ValueError, match="dark only"):
        _normalize_visual_theme({"style_id": "arcade-lime", "color_scheme": "dark",
                                 "scheme_preference": "system"})


def test_following_the_visitor_publishes_both_palettes() -> None:
    """The page cannot fetch the other palette when the OS setting changes
    mid-visit, so the preference decides what is SENT, not only what is
    applied."""

    from studiosaas.api_v1 import _normalize_visual_theme, _published_schemes

    following = _normalize_visual_theme({"style_id": "harbour-calm", "scheme_preference": "system"})
    published = _published_schemes(following)
    assert set(published) == {"light", "dark"}
    assert published["light"]["background_color"] != published["dark"]["background_color"]

    pinned = _normalize_visual_theme({"style_id": "harbour-calm", "scheme_preference": "light"})
    assert _published_schemes(pinned) == {}, "a pinned site should not ship a palette it never renders"


def test_the_default_is_still_the_studio_deciding() -> None:
    """A studio that never touches the control keeps the behaviour it had."""

    from studiosaas.api_v1 import _normalize_visual_theme

    for scheme in ("light", "dark"):
        theme = _normalize_visual_theme({"style_id": "vintage-press", "color_scheme": scheme})
        assert theme["scheme_preference"] == scheme


@pytest.mark.parametrize("page", [PORTAL, REGISTER])
def test_both_public_pages_honour_the_preference(page: Path) -> None:
    """A parent must not cross from a portal that followed their device into a
    registration page that did not."""

    source = _read(page)
    assert "prefers-color-scheme: dark" in source
    assert "visualThemes" in source
    for listener in ("addEventListener", "addListener"):
        assert listener in source, f"{page.name} does not react to a mid-visit change"


def test_the_console_offers_it_and_disables_it_where_it_cannot_work() -> None:
    console = _read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html")
    assert "Follow the visitor's device" in console
    assert "跟随访客设备" in console
    assert "activeSchemePreference" in console
    assert "schemePreference:" in console, "the preference is never sent on save"


# ── the hero photo ──────────────────────────────────────────────────────────

def test_uploading_a_hero_photo_selects_the_style_that_shows_it() -> None:
    """Upload succeeded, Save succeeded, Publish succeeded, no photo.

    `uploadWebsiteImage` filled the URL field and stopped, while Hero Style
    three fields below still said Soft Art Board — and the public page only
    adds `body.hero-image` when the style is `image`, so `.hero-art img` stayed
    display:none. Measured on production: all six tenants had an empty
    hero_image_url, which is what that dead end produces.
    """

    console = _read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html")
    block = console[console.index("async function uploadWebsiteImage("):]
    block = block[:block.index("\n    }")]
    assert "$('settingHeroStyle').value = 'image'" in block
    assert "target === 'hero'" in block, "the principal image must not change the hero style"


def test_the_hero_style_option_says_what_it_does() -> None:
    """It was labelled "Image Background", which promises a full-bleed hero.

    It fills the 4:5 panel beside the headline.
    """

    console = _read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html")
    assert '<option value="image">Photo panel</option>' in console
    assert "Image Background" not in console


def test_the_public_page_still_needs_both_the_url_and_the_style() -> None:
    """The page's own rule is unchanged; what changed is that the console can
    no longer leave an owner on the wrong side of it."""

    portal = _read(PORTAL)
    assert "heroStyle === 'image'" in portal
    assert "body.hero-image .hero-art img{display:block}" in portal


# ── the surfaces that read a solved palette, and the ones that do not ───────

# Every surface here has been converted to a token vocabulary, and this list is
# the guard: a new literal in any of them fails.
#
# It is a list rather than a glob because the rest of the product is honestly
# not done. `legacy-root/index.html` + `cms-app.js` (the operations CMS) still
# carry ~74 literals between them, and `product-home.html`, `manual.css` and
# `customer-resources.css` carry ~76 more. The marketing and documentation
# pages are arguably a separate identity; the CMS is not, and is the next
# surface to convert. Naming them here is the point — a glob that silently
# excluded them would read as coverage.
TOKENISED_SURFACES = [
    "backend/frontend/studio-admin.html",
    "super-admin.html",
    "backend/frontend/setup-password.html",
    "backend/frontend/shared-portfolio.html",
    "tenant-template/index.html",
    "tenant-template/register.html",
    "backend/frontend/assets/portal-theme.css",
    "backend/frontend/assets/console-theme.css",
    "backend/frontend/assets/brand-system.css",
    # v8.4.1: the operations CMS. Its dark set was hand-built and INVERTED —
    # the panel sat darker than the band under it, the v8.3.0 defect surviving
    # in a palette nobody regenerated — and --line-strong measured 1.95:1 on
    # the panel against WCAG 1.4.11's 3.0.
    "legacy-root/index.html",
    "legacy-root/register.html",
    "backend/frontend/cms-entry.html",
    "backend/frontend/assets/cms-app.js",
]

# What a converted surface may still state literally, and why.
ALLOWED = {
    # The preview subtree declares the TENANT palette inside a console; pinned
    # to style_theme() by test_platform_console.py.
    # The consoles are light only, so their address-bar colour is a constant
    # rather than something applyVisualTheme() rewrites.
    "backend/frontend/studio-admin.html": ("preview-device", "FALLBACK_THEME",
                                           "ON_FILL_", "theme-color"),
    "super-admin.html": ("theme-color",),
    "backend/frontend/setup-password.html": ("theme-color",),
    # These two ARE the palettes. They are generated / asserted against the
    # generator, which is what makes them the one place a literal belongs.
    "backend/frontend/assets/portal-theme.css": ("*",),
    "backend/frontend/assets/console-theme.css": ("*",),
    # Last-resort fallbacks in the var() chains, realigned to the default style
    # in v8.4.0 after they were found to be a palette from a product that no
    # longer exists (#a65a43 clay, #f4f0e8 paper).
    "backend/frontend/assets/brand-system.css": ("--brand-", "--ui-"),
    # The default the address bar shows before /brand answers.
    "tenant-template/index.html": ("theme-color",),
    "tenant-template/register.html": ("theme-color",),
    # The pre-/brand palette, pinned to the default style below.
    # JS fallbacks for a /brand response that has not arrived, pinned below.
    "legacy-root/index.html": ("theme-color", "brand.primaryColor",
                               "brand.secondaryColor", "visual.textColor"),
    "legacy-root/register.html": ("theme-color", "brand.primaryColor",
                                  "brand.secondaryColor", "visual.textColor"),
    "backend/frontend/cms-entry.html": ("theme-color",),
    # The printed report keeps a fixed warm palette: it is ink on paper, there
    # is no viewer theme to follow, and it already takes the studio's accent
    # through the :root it injects.
    "backend/frontend/assets/cms-app.js": ("safeReportColor",),
}


# Blocks that ARE a palette, per file. Each is pinned to style_theme()
# elsewhere; line-level matching cannot exempt them because they declare one
# token per line and no line names the block it sits in.
PINNED_BLOCKS = {
    "backend/frontend/studio-admin.html": [("    .preview-device {", "\n    }"),
                                           ("const FALLBACK_THEME = {", "};")],
    "legacy-root/index.html": [("        :root {", "\n        }"),
                               ("html:not([data-brand-scheme]) {", "\n            }")],
    "legacy-root/register.html": [("  :root {", "\n  }")],
    # The printed report keeps a fixed warm palette: it is ink on paper, there
    # is no viewer theme to follow, and it already takes the studio's accent
    # through the :root it injects.
    "backend/frontend/assets/cms-app.js": [("<style>", "</style>")],
}


def _without_pinned_blocks(page: str, source: str) -> str:
    for opener, closer in PINNED_BLOCKS.get(page, ()):
        while opener in source:
            head = source.index(opener)
            tail = source.index(closer, head) + len(closer)
            source = source[:head] + source[tail:]
    return source


@pytest.mark.parametrize("page", TOKENISED_SURFACES)
def test_a_converted_surface_stays_converted(page: str) -> None:
    allowed = ALLOWED.get(page, ())
    if "*" in allowed:
        pytest.skip("this file IS a palette; it is checked against the generator instead")
    source = _without_pinned_blocks(page, strip_comments(_read(REPOSITORY_ROOT / page)))
    offending = []
    for line in source.splitlines():
        if not re.search(r"(?<![\w-])#[0-9a-fA-F]{3,8}\b|rgba?\(\s*\d", line):
            continue
        if any(token in line for token in allowed):
            continue
        # Tailwind's gradient machinery needs a fully transparent stop.
        # `rgb(255 255 255 / 0)` paints nothing; it is not a colour choice.
        if "--tw-gradient-to:rgb(255 255 255 / 0)" in line:
            continue
        offending.append(line.strip()[:90])
    assert not offending, f"{page} has new literals:\n  " + "\n  ".join(offending[:8])


@pytest.mark.parametrize("page", ["legacy-root/index.html", "legacy-root/register.html"])
def test_the_cms_javascript_fallbacks_are_the_default_style(page: str) -> None:
    """The colours the CMS shows before /brand answers.

    register.html carried a NINTH palette here — Tailwind indigo #312e81 and
    #6366f1 — so a studio whose brand request was slow or failed saw its
    registration page in somebody else's colours.
    """

    from studiosaas.presets import DEFAULT_STYLE_ID, style_theme

    default = style_theme(DEFAULT_STYLE_ID, "light")
    source = _read(REPOSITORY_ROOT / page)
    found = re.findall(r"(brand\.primaryColor|brand\.secondaryColor|visual\.textColor)"
                       r"\s*\|\|\s*'(#[0-9a-fA-F]{6})'", source)
    assert found, f"{page} no longer has the fallbacks this pins"
    expected = {"brand.primaryColor": default["accent_color"],
                "brand.secondaryColor": default["secondary_accent_color"],
                "visual.textColor": default["text_color"]}
    for name, value in found:
        assert value.upper() == expected[name].upper(), (
            f"{page}: {name} falls back to {value}, not {DEFAULT_STYLE_ID} light's {expected[name]}"
        )


def test_the_cms_dark_fallback_is_not_inverted() -> None:
    """The CMS carried its own dark set and it had the v8.3.0 defect.

    #1a1d27 panel on a #20242f band: the card sat DARKER than the surface under
    it, so it read as a hole. That release fixed the ordering in the eight
    tenant themes and could not reach this one, because this is a separate
    hand-written palette. Measured before: band→card 1.08 the wrong way, and
    --line-strong at 1.95:1 on the panel against a 3.0 floor.
    """

    from studiosaas.presets import DEFAULT_STYLE_ID, style_theme

    dark = style_theme(DEFAULT_STYLE_ID, "dark")
    source = _read(REPOSITORY_ROOT / "legacy-root/index.html")
    block = source[source.index("html:not([data-brand-scheme]) {"):]
    block = block[:block.index("}")]
    declared = dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})", block))
    for name, key in (("--bg", "background_color"), ("--bg2", "background_alt_color"),
                      ("--panel", "panel_color"), ("--ink", "text_color"),
                      ("--muted", "muted_text_color"), ("--line", "border_color"),
                      ("--line-strong", "border_strong_color")):
        assert declared.get(name, "").upper() == dark[key].upper(), (
            f"{name} is {declared.get(name)}, not {DEFAULT_STYLE_ID} dark's {dark[key]}"
        )
    body = strip_comments(source).lower()
    for retired in ("#1a1d27", "#20242f", "#0e1016", "#454c5c"):
        assert retired not in body, f"the inverted value {retired} is back"


def test_the_studio_admin_exemption_is_exactly_two_blocks() -> None:
    """The exemption is narrow on purpose. Both blocks are pinned to
    style_theme() by test_platform_console.py; a third would not be."""

    source = strip_comments(_read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html"))
    assert source.count("    .preview-device {") == 1
    assert source.count("const FALLBACK_THEME = {") == 1


# ── themes stored before the tokens existed ─────────────────────────────────

def test_a_theme_stored_before_v840_is_completed_from_its_own_style() -> None:
    """A record written last week has 26 tokens. The palette has 44.

    The page skips a token it is not sent, so the eighteen added in v8.4.0
    would fall through to portal-theme.css — a studio on recital-plum would
    render plum surfaces with a vintage-press `--info` and `--success-soft`.
    Half a theme, no error, and only visible if you knew both palettes by eye.

    Completion has to come from the studio's OWN style, not the default, and
    must not disturb a single token the record does carry.
    """

    from studiosaas.api_v1 import _normalize_visual_theme
    from studiosaas.presets import style_theme

    stored = style_theme("recital-plum", "dark")
    legacy = {k: v for k, v in stored.items()
              if not any(k.endswith(s) for s in ("_soft_color", "_on_soft_color", "_border_color"))
              and k not in ("info_color", "surface_hover_color", "accent_muted_text_color")}
    assert len(legacy) < len(stored), "the fixture is not actually missing anything"

    completed = _normalize_visual_theme(legacy, category="music")

    for key, value in legacy.items():
        if key in ("scheme_preference",):
            continue
        assert completed[key] == value, f"{key} was changed while filling gaps"
    for key in ("info_color", "surface_hover_color", "accent_muted_text_color",
                "success_soft_color", "accent_on_soft_color"):
        assert completed.get(key), f"{key} is still missing"
        assert completed[key] == stored[key], (
            f"{key} was filled from the default style, not from recital-plum dark"
        )


def test_choosing_follow_the_visitor_is_not_overwritten_by_the_palette() -> None:
    """Reported as "follow-the-visitor cannot be selected", and it could not.

    `setVisualThemeFields` is handed two different kinds of thing: a SAVED
    record, which carries the owner's preference, and a GENERATED style
    palette, which cannot — a palette is a set of colours and has no opinion
    about who picks the mode.

    Choosing `system` set the preference, then applyVisualStyle() called
    setVisualThemeFields(style.schemes[mode]), the lookup found no
    scheme_preference, and it was overwritten with the mode. Measured in the
    browser: the control snapped back to `dark` and settingsPayload() would
    have saved `dark`.
    """

    source = _read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html")
    block = source[source.index("const preference = themeValue(theme, 'scheme_preference'"):]
    block = block[:block.index("themeMode = themeValue")]
    # The preference may only be replaced by a real one, or when it is not the
    # one value a palette cannot carry.
    assert "if (['light', 'dark', 'system'].includes(preference)) {" in block
    assert "} else if (activeSchemePreference !== 'system') {" in block
    assert "activeSchemePreference = activeColorScheme;" in block


def test_a_single_mode_style_still_drops_the_preference_it_cannot_honour() -> None:
    """The guard above must not preserve `system` onto a theme that ships one
    mode — that would leave a setting the server rejects on save."""

    source = _read(REPOSITORY_ROOT / "backend/frontend/studio-admin.html")
    block = source[source.index("function applyVisualStyle("):]
    block = block[:block.index("function ", 40)]
    assert "if (activeSchemePreference === 'system' && modes.length < 2) activeSchemePreference = nextScheme;" in block
