"""A visual theme is solved as a set; nothing may substitute one token into it.

The CMS looked like two products at once because `_default_visual_theme()`
replaced the preset's `accent_color` with the tenant's `primary_color`. Each
preset places its accent within 30 degrees of its own background (13 of 15
within 6); an injected brand hue carries no such relationship, and on
`lets-paint-showcase` it produced a 160-degree, near-complementary pairing
against 19 tokens that stayed warm.
"""

from __future__ import annotations

import colorsys

import pytest

from studiosaas.api_v1 import _default_visual_theme
from studiosaas.presets import VISUAL_STYLE_PRESETS

# The widest separation any shipped preset uses (studio-ink dark, a
# deliberately neutral style). Anything beyond this is not a designed pairing.
MAX_DESIGNED_SEPARATION_DEG = 30


def _hue(value: str) -> int:
    raw = value.lstrip("#")
    r, g, b = (int(raw[i:i + 2], 16) / 255 for i in (0, 2, 4))
    hue, _light, _sat = colorsys.rgb_to_hls(r, g, b)
    return round(hue * 360)


def _separation(first: str, second: str) -> int:
    delta = abs(_hue(first) - _hue(second)) % 360
    return min(delta, 360 - delta)


def test_brand_colour_does_not_replace_the_preset_accent() -> None:
    """A tenant hue must not be spliced into a palette solved around another."""

    neutral = _default_visual_theme("", "", "art")
    branded = _default_visual_theme("#173f3a", "#d7a93d", "art")
    assert branded["accent_color"] == neutral["accent_color"]
    assert branded["secondary_accent_color"] == neutral["secondary_accent_color"]


def test_default_theme_stays_within_designed_hue_range() -> None:
    """The returned accent belongs to the surface it sits on."""

    for category in ("art", "music", "dance", "general"):
        theme = _default_visual_theme("#173f3a", "#960096", category)
        separation = _separation(theme["background_color"], theme["accent_color"])
        assert separation <= MAX_DESIGNED_SEPARATION_DEG, (
            f"{category}: accent sits {separation} degrees from its background"
        )


@pytest.mark.parametrize(
    "style_id,mode",
    [(sid, mode) for sid, preset in VISUAL_STYLE_PRESETS.items()
     for mode in preset.get("themes", {})],
)
def test_every_shipped_preset_is_internally_coherent(style_id: str, mode: str) -> None:
    """Guards the presets themselves, which are the thing being preserved."""

    theme = VISUAL_STYLE_PRESETS[style_id]["themes"][mode]
    if "background_color" not in theme:
        pytest.skip("mode carries no surface colours")
    separation = _separation(theme["background_color"], theme["accent_color"])
    assert separation <= MAX_DESIGNED_SEPARATION_DEG, (
        f"{style_id}/{mode}: accent sits {separation} degrees from its background"
    )


# ── semantic roles ───────────────────────────────────────────────────────────
#
# success/warning/danger are not one colour used one way. Each is a solid badge
# fill, a label sitting on that fill, and the mixed text form the CMS renders
# (`color-mix(in srgb, var(--success) 61.8%, var(--text-anchor))`). Solving only
# against the page — what the generator did before v8.2.9 — shipped three
# arcade-lime/dark fills under the 3:1 non-text floor, and let vintage-press put
# its warning 5 degrees from its own accent, where a warning badge is
# indistinguishable from a button.

SEMANTIC_ROLES = ("success_color", "warning_color", "danger_color")
SEMANTIC_TEXT_MIX = 0.618
# The brand's tinted chip against each status chip. This replaced a hue/contrast
# floor on the SOLID forms when the eight industry palettes became one — see the
# test below for why the old form could not survive a free accent knob.
MIN_CHIP_SEPARATION = 1.14


def _relative_luminance(value: str) -> float:
    raw = value.lstrip("#")
    channels = []
    for i in (0, 2, 4):
        c = int(raw[i:i + 2], 16) / 255
        channels.append(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(first: str, second: str) -> float:
    high, low = sorted((_relative_luminance(first), _relative_luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def _mix(first: str, second: str, portion: float) -> str:
    a, b = first.lstrip("#"), second.lstrip("#")
    return "#%02X%02X%02X" % tuple(
        round(int(a[i:i + 2], 16) * portion + int(b[i:i + 2], 16) * (1 - portion))
        for i in (0, 2, 4)
    )


@pytest.mark.parametrize(
    "style_id,mode,role",
    [(sid, mode, role) for sid, preset in VISUAL_STYLE_PRESETS.items()
     for mode in preset.get("themes", {}) for role in SEMANTIC_ROLES],
)
def test_semantic_role_survives_every_surface_it_lands_on(
    style_id: str, mode: str, role: str
) -> None:
    theme = VISUAL_STYLE_PRESETS[style_id]["themes"][mode]
    if "background_color" not in theme:
        pytest.skip("mode carries no surface colours")
    colour = theme[role]
    where = f"{style_id}/{mode} {role}"

    for surface in ("background_alt_color", "panel_color"):
        fill = _contrast(colour, theme[surface])
        assert fill >= 3.0, f"{where}: solid fill is {fill:.2f} on {surface}, needs 3.0"

    label = _contrast(theme["accent_text_color"], colour)
    assert label >= 4.5, f"{where}: label on the fill is {label:.2f}, needs 4.5"

    mixed = _mix(colour, theme["text_color"], SEMANTIC_TEXT_MIX)
    for surface in ("background_alt_color", "panel_color"):
        text = _contrast(mixed, theme[surface])
        assert text >= 4.5, f"{where}: semantic text is {text:.2f} on {surface}, needs 4.5"


@pytest.mark.parametrize(
    "style_id,mode,role",
    [(sid, mode, role) for sid, preset in VISUAL_STYLE_PRESETS.items()
     for mode in preset.get("themes", {}) for role in SEMANTIC_ROLES],
)
def test_semantic_role_never_collapses_into_the_accent(
    style_id: str, mode: str, role: str
) -> None:
    """A warning that looks like a button has stopped being a warning.

    Asserted on the CHIP rather than on the solid fill since 2026-08-06, and
    the substitution is deliberate:

    * the solid fill it used to check no longer exists. Design_Constraints
      section 1.1 gives a semantic role a tinted chip, a label on it and a
      border; the accent is the only role that fills.
    * the old form could only be met by re-solving the semantics against the
      accent, and the accent is now a free tenant input. That would make
      "saved" a function of somebody's logo, which is the whole defect the
      single palette exists to remove.

    The chip pair is what is actually on screen together, and it is asserted
    inside `palette.build`, so it holds at every hue the knob can reach rather
    than only at the default one.
    """

    theme = VISUAL_STYLE_PRESETS[style_id]["themes"][mode]
    if "background_color" not in theme:
        pytest.skip("mode carries no surface colours")
    chip = theme[role.replace("_color", "_soft_color")]
    weight = _contrast(chip, theme["accent_soft_color"])
    assert weight >= MIN_CHIP_SEPARATION, (
        f"{style_id}/{mode}: the {role} chip {chip} and the accent chip "
        f"{theme['accent_soft_color']} are {weight:.2f}:1 apart — on a row "
        f"showing both they are one colour"
    )
