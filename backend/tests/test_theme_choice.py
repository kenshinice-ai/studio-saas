"""A studio chooses its own mood; an industry only recommends one.

This exists because the boundary has now been crossed in both directions.

First `applyCategoryPreset()` in Studio Admin called `setVisualThemeFields()`
with the industry's recommended theme, so clicking an industry card silently
repainted a studio that had already picked its colours. Then the fix for that
went too far and deleted the eight named themes outright, leaving one palette
and a colour dial — which removed the choice rather than un-welding it, and
was reported within a day as "颜色主题消失了".

So both halves are asserted: the eight moods exist and stay distinct, and
nothing in the industry path writes one.
"""
from __future__ import annotations

import re
from _console_sources import console_page_source
from pathlib import Path

import pytest

from studiosaas.palette import SEMANTIC, hue_gap, hsl_of, ratio
from studiosaas.presets import (
    DEFAULT_STYLE_ID,
    FREE_ACCENT_STYLE_ID,
    INDUSTRY_PRESETS,
    INDUSTRY_STYLE_RECOMMENDATIONS,
    VISUAL_STYLE_PRESETS,
    style_theme,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ADMIN = REPOSITORY_ROOT / "backend/frontend/studio-admin.html"

CURATED = [key for key in VISUAL_STYLE_PRESETS if key != FREE_ACCENT_STYLE_ID]


# ── the moods exist, and they are moods ─────────────────────────────────────

def test_eight_named_themes_plus_the_free_accent_one() -> None:
    assert len(CURATED) == 8, f"expected eight curated moods, found {CURATED}"
    assert FREE_ACCENT_STYLE_ID in VISUAL_STYLE_PRESETS


@pytest.mark.parametrize("key", CURATED)
def test_every_curated_theme_is_named_and_described(key: str) -> None:
    """A dial has no name. These do, in both languages, plus a mood line —
    that is the difference between choosing a theme and turning a knob."""

    preset = VISUAL_STYLE_PRESETS[key]
    for field in ("label", "label_zh", "description", "description_zh",
                  "mood", "harmony"):
        assert preset.get(field), f"{key} has no {field}"


def test_the_curated_papers_are_actually_different() -> None:
    """Eight themes that share a paper are one theme with eight accents.

    The 2026-08-06 collapse was justified by the paper carrying a hue that
    hid a semantic; the repair was to floor the semantic chips' chroma, not
    to make every paper identical. This checks the repair kept the variety.
    """

    papers = {VISUAL_STYLE_PRESETS[key]["themes"]["light"]["background_color"]
              for key in CURATED
              if "light" in VISUAL_STYLE_PRESETS[key]["themes"]}
    assert len(papers) >= 6, f"the curated papers have converged: {sorted(papers)}"


@pytest.mark.parametrize("key", CURATED)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_every_semantic_chip_stays_visible_on_its_own_paper(key: str, mode: str) -> None:
    """The defect that was blamed on having eight themes.

    A green theme could not show "saved" because the paper's hue matched
    success's and the chip was mixed for CONTRAST only, which says nothing
    about colour. Now floored by chroma, so a chip reads as a chip however
    close its hue sits to the page it is on.
    """

    themes = VISUAL_STYLE_PRESETS[key]["themes"]
    if mode not in themes:
        pytest.skip(f"{key} does not ship {mode}")
    theme = themes[mode]

    def chroma(value: str) -> int:
        raw = value.lstrip("#")
        channels = [int(raw[i:i + 2], 16) for i in (0, 2, 4)]
        return max(channels) - min(channels)

    paper_chroma = chroma(theme["background_color"])
    for role in SEMANTIC:
        chip = theme[f"{role}_soft_color"]
        assert chroma(chip) >= paper_chroma + 8, (
            f"{key}/{mode}: the {role} chip {chip} carries no more colour than "
            f"the paper it sits on — it reads as dirty paper, not as a status"
        )


@pytest.mark.parametrize("key", CURATED)
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_no_semantic_collapses_into_its_own_themes_accent(key: str, mode: str) -> None:
    """A warning badge that looks like a button has stopped being a warning.

    Only meaningful for a CURATED accent, which is fixed at design time. The
    free-accent theme is protected differently (see test_accent_knob), because
    coupling a semantic to a live tenant hue is what makes "saved" a function
    of somebody's logo.
    """

    themes = VISUAL_STYLE_PRESETS[key]["themes"]
    if mode not in themes:
        pytest.skip(f"{key} does not ship {mode}")
    theme = themes[mode]
    accent = theme["accent_color"]
    for role in SEMANTIC:
        colour = theme[f"{role}_color"]
        gap = hue_gap(hsl_of(colour)[0], hsl_of(accent)[0])
        weight = ratio(colour, accent)
        assert gap >= 30 or weight >= 1.55, (
            f"{key}/{mode}: {role} sits {gap:.0f} degrees from the accent at "
            f"only {weight:.2f} contrast"
        )


def test_the_status_hues_are_the_same_in_every_theme() -> None:
    """An owner has to recognise "saved" in any tenant's admin panel.

    The pre-2026-08-06 generator nudged each semantic hue 4% toward the
    theme's accent, which made the four roles slightly different colours in
    every palette. Their depth may vary per theme; their hue may not.
    """

    # Two degrees of tolerance, for 8-bit quantisation rather than for drift:
    # the solver works at the exact hue, but the hex it lands on reads back a
    # degree either side once each channel is rounded to a byte. Anything
    # larger is the 4%-toward-the-accent nudge coming back.
    for role, (want_hue, _) in SEMANTIC.items():
        hues = {
            round(hsl_of(VISUAL_STYLE_PRESETS[key]["themes"][mode][f"{role}_color"])[0])
            for key in VISUAL_STYLE_PRESETS
            for mode in VISUAL_STYLE_PRESETS[key]["themes"]
        }
        assert max(hues) - min(hues) <= 2, f"{role} has drifted per theme: {sorted(hues)}"
        for hue in hues:
            assert hue_gap(hue, want_hue) <= 2, f"{role} sits at {hue}, not {want_hue}"


# ── the industry recommends, and only recommends ────────────────────────────

def test_every_industry_recommends_a_theme_that_exists() -> None:
    for industry, style_id in INDUSTRY_STYLE_RECOMMENDATIONS.items():
        assert style_id in VISUAL_STYLE_PRESETS, f"{industry} recommends {style_id}"
        assert INDUSTRY_PRESETS[industry]["recommended_style_id"] == style_id


def test_the_recommendations_are_not_all_the_same_theme() -> None:
    """A recommendation every industry shares is not a recommendation."""

    assert len(set(INDUSTRY_STYLE_RECOMMENDATIONS.values())) >= 5


def test_applying_an_industry_preset_does_not_write_a_palette() -> None:
    """The wiring bug, pinned in the file where it lived.

    `applyCategoryPreset()` sets copy, registration questions, FAQ and the
    operating template. If it ever calls `setVisualThemeFields` again, a
    studio that has chosen its colours loses them to a click on an industry
    card — which is exactly what happened and what this catches.
    """

    source = console_page_source(ADMIN)
    start = source.index("function applyCategoryPreset(")
    end = source.index("\n    function ", start + 1)
    # Comments explaining why the call is gone are not the call. Stripping
    # them is what lets the note stay where the mistake was made.
    body = re.sub(r"/\*.*?\*/", "", source[start:end], flags=re.S)

    assert "setVisualThemeFields" not in body, (
        "applyCategoryPreset writes a visual theme again; an industry "
        "recommends a theme, it does not apply one"
    )
    for field in ("settingPrimaryColor", "settingSecondaryColor",
                  "settingThemeBackground", "settingThemePanel"):
        assert field not in body, f"applyCategoryPreset writes {field}"


def test_the_free_accent_theme_is_the_only_one_the_knob_can_reach() -> None:
    """`accent_hue` on a curated theme must be ignored, not honoured.

    Otherwise the picker silently turns Recital Plum into something that is
    no longer Recital Plum while still calling itself that.
    """

    curated = style_theme(DEFAULT_STYLE_ID, "light")
    turned = style_theme(DEFAULT_STYLE_ID, "light", accent_hue=200)
    assert turned["accent_color"] == curated["accent_color"]
    assert "accent_hue" not in turned

    free = style_theme(FREE_ACCENT_STYLE_ID, "light", accent_hue=200)
    assert free["accent_hue"] == 200
    assert free["accent_color"] != style_theme(FREE_ACCENT_STYLE_ID, "light")["accent_color"]


def test_the_admin_only_reveals_the_picker_for_the_custom_card() -> None:
    """An always-visible colour input is what made eight curated themes read
    as decoration around a dial."""

    source = console_page_source(ADMIN)
    assert 'id="accentPickerWrap"' in source
    assert re.search(r"accentPickerWrap'\)[^\n]*\n[^\n]*hidden = activeVisualStyle !== FREE_ACCENT_STYLE_ID",
                     source), "the picker is not gated on the Custom card"
