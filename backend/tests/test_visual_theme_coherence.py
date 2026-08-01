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
