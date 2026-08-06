"""Surfaces have to stack the same way in both modes, not merely contrast.

Every dark palette that shipped before v8.3.0 passed all 26 contrast pairs
`palette_gen.py` asserts, and every one of them was arranged wrong. The dark
surfaces had been produced by mirroring the light lightnesses around mid-grey:
light put the alternating band 0.047 *below* the page, so dark put it 0.124
*above*. That kept the gap and inverted its meaning — in a dark UI lighter
reads as nearer, so the band came out brighter than the cards resting on it,
and its step away from the page measured 1.39-1.61 against light mode's
1.10-1.13.

Contrast is a statement about legibility. It cannot express which surface is
meant to read as nearer, which is why the existing checks were all green. The
tests here are about arrangement:

* `panel` is the most prominent surface in both modes;
* the alternating band's step away from the page is the same order of
  magnitude in both modes.

They are run against the shipped presets, and `test_the_rule_rejects_the_pre_v830_surfaces`
runs them against a reconstruction of the palette that shipped, so a rule that
stopped catching the defect it was written for fails here rather than passing
quietly.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from studiosaas.presets import VISUAL_STYLE_PRESETS

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPOSITORY_ROOT / "docs" / "design" / "palette_gen.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("palette_gen", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


palette_gen = _load_generator()


def _luminance(value: str) -> float:
    raw = value.lstrip("#")
    channels = []
    for index in (0, 2, 4):
        channel = int(raw[index:index + 2], 16) / 255
        channels.append(channel / 12.92 if channel <= 0.03928
                        else ((channel + 0.055) / 1.055) ** 2.4)
    red, green, blue = channels
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _ratio(first: str, second: str) -> float:
    high, low = sorted((_luminance(first), _luminance(second)), reverse=True)
    return (high + 0.05) / (low + 0.05)


THEME_MODES = [
    (key, mode)
    for key, style in VISUAL_STYLE_PRESETS.items()
    for mode in style["modes"]
]


@pytest.mark.parametrize("key,mode", THEME_MODES)
def test_the_panel_is_the_nearest_surface(key: str, mode: str) -> None:
    """A card is never out-shouted by the band it sits on."""

    theme = VISUAL_STYLE_PRESETS[key]["themes"][mode]
    panel = _luminance(theme["panel_color"])
    assert panel > _luminance(theme["background_color"]), (
        f"{key} {mode}: the card is not lighter than the page"
    )
    assert panel > _luminance(theme["background_alt_color"]), (
        f"{key} {mode}: the alternating band is brighter than the card on it"
    )


@pytest.mark.parametrize(
    "key",
    [key for key, style in VISUAL_STYLE_PRESETS.items() if style["modes"] == ["light", "dark"]],
)
def test_the_alt_band_does_not_shout_louder_in_dark_mode(key: str) -> None:
    """The band is a change of surface in both modes, not a slab of light."""

    themes = VISUAL_STYLE_PRESETS[key]["themes"]
    steps = {
        mode: _ratio(theme["background_alt_color"], theme["background_color"])
        for mode, theme in themes.items()
    }
    assert steps["dark"] <= steps["light"] * palette_gen.LAYER_STEP_TOLERANCE, (
        f"{key}: the band steps {steps['dark']:.2f} off the page in dark mode "
        f"against {steps['light']:.2f} in light"
    )


def test_the_rule_rejects_the_pre_v830_surfaces() -> None:
    """The check has to fail on the arrangement it was written to catch.

    Rebuilds every dark theme with the three lightnesses that shipped through
    v8.2.31 and asserts `layer_faults` rejects all of them. Without this, a
    later edit could relax the rule into something that passes on both the
    fixed palette and the broken one.

    Counted rather than hard-coded: this said "== 8" until the eight industry
    palettes became one on 2026-08-06, which made a test about a layering rule
    fail for a reason that had nothing to do with layering.
    """

    rejected = 0
    darkening = [
        theme for theme in palette_gen.THEMES
        if "dark" in theme.get("modes", palette_gen.MODES_DEFAULT)
    ]
    for spec in darkening:
        built = palette_gen.build(spec, True)
        hue, saturation = spec["hue"], spec["sat"]
        built["background_color"] = palette_gen.hexof(hue, min(saturation * .52, .38), .068)
        built["panel_color"] = palette_gen.hexof(hue, min(saturation * .44, .32), .132)
        built["background_alt_color"] = palette_gen.hexof(hue, min(saturation * .40, .28), .192)
        rejected += bool(palette_gen.layer_faults(spec, built))

    assert darkening, "no dark theme left to test the layering rule against"
    assert rejected == len(darkening), (
        f"only {rejected} of {len(darkening)} pre-v8.3.0 dark palettes are rejected; "
        "the layering rule no longer catches the defect it exists for"
    )


@pytest.mark.parametrize("key,mode", THEME_MODES)
def test_the_shipped_presets_match_the_generator(key: str, mode: str) -> None:
    """presets.py is generated output, so it may not be hand-edited apart.

    Without this, re-solving a palette and forgetting to copy one token back
    leaves the running product and its checker disagreeing — and the checker
    passes, because it checks what it generated rather than what shipped.
    """

    spec = next(theme for theme in palette_gen.THEMES if theme["key"] == key)
    built = palette_gen.build(spec, mode == "dark")
    shipped = VISUAL_STYLE_PRESETS[key]["themes"][mode]
    drifted = {token: (shipped.get(token), want)
               for token, want in built.items() if shipped.get(token) != want}
    assert not drifted, f"{key} {mode} has drifted from palette_gen.py: {drifted}"


def test_no_stylesheet_flips_brand_surfaces_on_the_visitors_os_setting() -> None:
    """A studio's theme decides light or dark; the visitor's OS does not.

    brand-system.css carried a `prefers-color-scheme: dark` block that
    reassigned --brand-paper / --brand-ink / --brand-line. It was overridden
    everywhere it mattered — /brand writes those tokens inline on :root — so it
    changed nothing, but any page that later styled itself from those tokens
    without inlining them would have had its paper and ink flipped while its
    accents stayed solved for light.
    """

    stylesheet = (REPOSITORY_ROOT / "backend" / "frontend" / "assets"
                  / "brand-system.css").read_text(encoding="utf-8")
    rules = "\n".join(
        line for line in stylesheet.splitlines()
        if not line.lstrip().startswith(("*", "/*"))
    )
    assert "prefers-color-scheme" not in rules
    for token in ("--brand-paper", "--brand-ink", "--brand-line"):
        assert f"{token}: #" not in rules, (
            f"{token} is assigned a literal colour outside :root's fallback chain"
        )
