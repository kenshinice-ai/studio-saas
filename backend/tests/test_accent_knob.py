"""The studio's one colour knob.

There is a single palette since 2026-08-06 and a studio changes exactly one
thing about it: the accent hue, normally taken out of its own logo. What makes
that safe to expose as a free colour picker is that only the HUE survives —
the lightness and the saturation are solved by the product. These tests pin
that split, because the day someone "simplifies" it by storing the picked hex
directly is the day a studio can publish an unreadable button.

See docs/design/Design_Constraints.md section 1.4.
"""
from __future__ import annotations

import importlib

import pytest

from studiosaas.palette import (
    ACCENT_INPUT_MIN_CHROMA,
    ACCENT_MIN_SEMANTIC_GAP,
    DEFAULT_ACCENT_HUE,
    SEMANTIC,
    accent_hue_from,
    build,
    chroma,
    hue_gap,
    ratio,
    studio_theme,
)
from studiosaas.presets import DEFAULT_STYLE_ID, style_theme


def _normalize(payload: dict) -> dict:
    module = importlib.import_module("studiosaas.api_v1")
    return module._normalize_visual_theme(payload)


# ── the hue survives, nothing else does ─────────────────────────────────────

@pytest.mark.parametrize("logo", ["#39FF14", "#FF00AA", "#00E5FF", "#FFF200"])
def test_a_loud_logo_becomes_a_usable_accent(logo: str) -> None:
    """Neon in, readable out.

    A studio picking its logo colour is picking a hue. Taking its lightness
    too is how a site ends up with a fluorescent call to action at 1.4:1.
    """

    hue = accent_hue_from(logo)
    theme = build(studio_theme(hue), False)
    accent = theme["accent_color"]

    assert ratio(accent, theme["background_color"]) >= 4.5
    assert ratio(theme["accent_text_color"], accent) >= 4.5
    # The hue is kept — that is the part a person recognises as "my colour".
    assert hue_gap(accent_hue_from(accent), hue) < 6


def test_an_achromatic_logo_does_not_produce_a_grey_button() -> None:
    """Below the chroma floor there is no hue worth keeping."""

    for grey in ("#808080", "#FFFFFF", "#000000", "#1C1C1E"):
        assert chroma(grey) < ACCENT_INPUT_MIN_CHROMA
        assert accent_hue_from(grey) == DEFAULT_ACCENT_HUE


@pytest.mark.parametrize("role", list(SEMANTIC))
def test_a_brand_hue_is_pushed_off_a_status_hue(role: str) -> None:
    """A brand colour that reads as a status is not a brand colour.

    Measured against the status's ACTUAL hue rather than the whole band that
    would still read as that status. The band was the first rule and it was
    wrong in a way the swatch shelf exposed: the product's own default accent
    is hue 26, deliberately 10 degrees off warning, and the band rule would
    have pushed an owner who picked that exact colour off it.

    Pushed to the nearer side rather than silently replaced, so a studio whose
    logo really is red still gets the reddest brand hue available.
    """

    from studiosaas.palette import hexof

    sem_hue = SEMANTIC[role][0]
    resolved = accent_hue_from(hexof(sem_hue, 0.62, 0.48))
    assert hue_gap(resolved, sem_hue) >= ACCENT_MIN_SEMANTIC_GAP - 0.01, (
        f"a {role}-coloured logo resolved to {resolved}, still on the status hue")


def test_the_default_accent_survives_its_own_picker() -> None:
    """An owner who picks the product's own default must keep it.

    This is exactly what the band rule got wrong, so it is asserted rather
    than remembered.
    """

    default_accent = style_theme(DEFAULT_STYLE_ID, "light")["accent_color"]
    assert hue_gap(accent_hue_from(default_accent), DEFAULT_ACCENT_HUE) < 1


# ── the solved palette keeps every rule the default one has ─────────────────

@pytest.mark.parametrize("hue", [0, 40, 96, 140, 200, 260, 310, 350])
@pytest.mark.parametrize("dark", [False, True])
def test_any_accent_hue_still_separates_the_brand_chip_from_every_status(
        hue: int, dark: bool) -> None:
    """The chip separation is what lets the accent be analogous to the paper.

    `build` raises if it is not met, so this is really asserting that the knob
    cannot reach a hue where the guarantee breaks.
    """

    theme = build(studio_theme(hue), dark)
    for role in ("success", "warning", "danger", "info"):
        assert ratio(theme["accent_soft_color"], theme[f"{role}_soft_color"]) >= 1.14


@pytest.mark.parametrize("hue", [0, 96, 200, 310])
def test_the_paper_and_the_ink_never_move(hue: int) -> None:
    """Turning the knob repaints the accent and nothing else.

    This is the whole point of collapsing the eight industry palettes: the
    paper carried the industry hue, and whichever semantic shared it stopped
    being visible.
    """

    default = build(studio_theme(), False)
    turned = build(studio_theme(hue), False)
    for token in ("background_color", "background_alt_color", "panel_color",
                  "text_color", "text_soft_color", "muted_text_color",
                  "border_color", "border_strong_color",
                  "success_color", "warning_color", "danger_color", "info_color"):
        assert turned[token] == default[token], f"{token} moved with the accent"


# ── the API surface ─────────────────────────────────────────────────────────

def test_a_picked_colour_is_stored_as_degrees_not_as_the_hex() -> None:
    """The hex is an input; the hue is the decision.

    Storing the hex would freeze a studio's palette against the solver it was
    saved under, so an improvement to the solver would never reach it.
    """

    theme = _normalize({"style_id": DEFAULT_STYLE_ID, "accent_source": "#39FF14"})
    assert "accent_hue" in theme
    assert theme["accent_hue"] == pytest.approx(accent_hue_from("#39FF14"), abs=0.1)
    assert theme["accent_color"] != "#39FF14"
    assert ratio(theme["accent_color"], theme["background_color"]) >= 4.5


def test_a_saved_hue_round_trips() -> None:
    once = _normalize({"style_id": DEFAULT_STYLE_ID, "accent_source": "#1F6FEB"})
    twice = _normalize({"style_id": DEFAULT_STYLE_ID, "accent_hue": once["accent_hue"]})
    assert twice["accent_color"] == once["accent_color"]


def test_a_nonsense_hue_is_refused() -> None:
    for bad in ("teal", None, "", float("nan")):
        payload = {"style_id": DEFAULT_STYLE_ID, "accent_hue": bad}
        if bad in (None, ""):
            # No knob supplied at all is not an error; it means "keep default".
            assert _normalize(payload)["accent_color"] == \
                style_theme(DEFAULT_STYLE_ID, "light")["accent_color"]
        else:
            with pytest.raises(ValueError):
                _normalize(payload)


def test_following_the_visitor_publishes_both_solved_palettes() -> None:
    """A site that follows the device must ship both modes of ITS accent."""

    module = importlib.import_module("studiosaas.api_v1")
    theme = _normalize({"style_id": DEFAULT_STYLE_ID, "accent_source": "#1F6FEB",
                        "scheme_preference": "system"})
    published = module._published_schemes(theme)
    assert set(published) == {"light", "dark"}
    default_light = style_theme(DEFAULT_STYLE_ID, "light")["accent_color"]
    assert published["light"]["accent_color"] != default_light, (
        "the published palette fell back to the default accent")
    assert published["light"]["accent_color"] != published["dark"]["accent_color"]


# ── the picker's preview endpoint ───────────────────────────────────────────

def test_the_preview_endpoint_solves_what_the_picker_will_save(client) -> None:
    """The admin shows the real result while the owner drags a colour input.

    It round-trips to the server on purpose: shipping a solver to the browser
    to save the hop would make three implementations of one algorithm, and the
    two that exist are only safe because a parity test compares them token by
    token.
    """

    response = client.get("/v1/theme-preview?accent=%2339FF14")
    assert response.status_code == 200
    body = response.get_json()
    assert body["hue"] == pytest.approx(accent_hue_from("#39FF14"), abs=0.1)
    assert set(body["themes"]) == {"light", "dark"}
    saved = _normalize({"style_id": DEFAULT_STYLE_ID, "accent_source": "#39FF14"})
    assert body["themes"]["light"]["accent_color"] == saved["accent_color"], (
        "the preview and the save path disagree")


def test_the_preview_says_when_it_moved_the_colour(client) -> None:
    """A silent substitution is how an owner loses trust in the picker."""

    from studiosaas.palette import hexof

    assert client.get("/v1/theme-preview?accent=%23808080").get_json()["notes"] == ["achromatic"]
    # Dead on the danger hue, so it must be moved and must say so.
    on_danger = hexof(SEMANTIC["danger"][0], 0.62, 0.48).replace("#", "%23")
    assert "moved_out_of_status_band" in \
        client.get(f"/v1/theme-preview?accent={on_danger}").get_json()["notes"]
    assert client.get("/v1/theme-preview?accent=%2339FF14").get_json()["notes"] == []


def test_the_preview_refuses_nonsense(client) -> None:
    assert client.get("/v1/theme-preview?accent=notacolour").status_code == 400
    assert client.get("/v1/theme-preview?hue=teal").status_code == 400
