"""A stored theme must always render. It is not user input.

On 2026-08-06 the single-palette style id was renamed from `studio` to
`custom`. Nothing migrated the rows, and the READ path was the WRITE
validator, which rejects an unknown id. So `GET /v1/public/<slug>/brand`
answered 500 for five of six live tenants — and because a portal's copy,
images, principal bio and contact details travel in that same response, five
studios' websites went blank. Not the colours: everything.

Every check in the deploy gate was green throughout, including the automatic
rollback window, because they all asked whether the server was up.

Three separate guarantees are asserted here, because the bug needed all three
to be missing:

  1. a retired id resolves to the palette it was renamed FROM, so an affected
     studio comes back on its own colours rather than on the default;
  2. the read path never raises, whatever a past release wrote;
  3. the write path still does, so an owner posting a typo hears about it.
"""
from __future__ import annotations

import pytest

import sys
from pathlib import Path

import studiosaas.api_v1  # noqa: F401  (registers the module in sys.modules)

# `from studiosaas import api_v1` binds the BLUEPRINT of that name, not the
# module — the package re-exports it. Reach for the module explicitly.
api_v1 = sys.modules["studiosaas.api_v1"]

from studiosaas.presets import (  # noqa: E402
    DEFAULT_STYLE_ID,
    FREE_ACCENT_STYLE_ID,
    RETIRED_STYLE_ALIASES,
    VISUAL_STYLE_PRESETS,
    resolve_style_id,
    style_theme,
)


def test_the_retired_id_that_caused_the_outage_is_aliased():
    """`studio` was the whole of v8.5.0-v8.5.1. It must never be unknown."""

    assert RETIRED_STYLE_ALIASES["studio"] == FREE_ACCENT_STYLE_ID
    assert resolve_style_id("studio") == FREE_ACCENT_STYLE_ID


def test_every_alias_points_at_a_style_that_exists():
    """An alias to a second retired id is a slower version of the same bug."""

    for retired, target in RETIRED_STYLE_ALIASES.items():
        assert retired not in VISUAL_STYLE_PRESETS, (
            f"{retired!r} is a live style id; listing it as retired makes "
            "resolve_style_id lie about which palette it returns"
        )
        assert target in VISUAL_STYLE_PRESETS, (
            f"{retired!r} points at {target!r}, which does not exist"
        )


def test_an_aliased_tenant_keeps_its_own_accent_not_the_default():
    """Falling back to vintage-press would repaint a studio that never asked.

    ruby-s-studio stored hue 341.8 — a rose it chose. Resolving through the
    alias has to carry that hue into the free-accent palette; resolving to the
    default would hand it the product's bronze and look like a redesign.
    """

    rose = style_theme("studio", "light", 341.8)
    assert rose["style_id"] == FREE_ACCENT_STYLE_ID
    assert rose["accent_hue"] == pytest.approx(341.8, abs=0.05)
    assert rose["accent_color"] != style_theme(DEFAULT_STYLE_ID, "light")["accent_color"]


def test_unknown_id_is_rejected_on_write():
    """Strict is the default: a POST with a typo is the owner's to fix."""

    with pytest.raises(ValueError, match="not recognised"):
        api_v1._normalize_visual_theme({"style_id": "no-such-style"})


def test_unknown_id_is_survived_on_read():
    """The read path has no owner to tell and no page to fall back to."""

    theme = api_v1._normalize_visual_theme(
        {"style_id": "no-such-style"}, strict=False
    )
    assert theme["background_color"]
    assert theme["text_color"]


@pytest.mark.parametrize(
    "stored",
    [
        {"style_id": "studio", "accent_hue": 341.8},          # the real rows
        {"style_id": "gone-in-a-future-release"},
        {"style_id": "custom", "color_scheme": "chartreuse"},
        {"style_id": "custom", "button_style": "retired"},
        {"style_id": "custom", "font_mood": "retired"},
        {"style_id": "custom", "accent_hue": "not-a-number"},
        {"style_id": "custom", "scrim_color": "rgb(0,0,0)"},
        {"style_id": "custom", "accent_color": "chartreuse"},
        {"accent_hue": float("nan")},
        {"style_id": 12345},
        "not an object at all",
    ],
)
def test_no_stored_value_can_take_a_portal_down(app, stored):
    """The guarantee, stated once: two outcomes, never an exception.

    Each row is something a past release wrote or a future one might stop
    accepting. Whichever it is, a visitor gets a readable page.
    """

    with app.app_context():
        theme = api_v1._stored_visual_theme(stored, "", "", "art")

    assert theme["background_color"].startswith("#")
    assert theme["text_color"].startswith("#")
    assert theme["accent_color"].startswith("#")


def test_the_read_path_uses_the_tolerant_wrapper():
    """Guards the wiring, not just the wrapper.

    `_stored_visual_theme` existing is worth nothing if the brand serialiser
    still calls the strict validator — which is exactly the state that
    shipped. Checked against the source because there is no cheaper way to
    prove which function that one line calls.
    """

    import inspect

    # Anchored on the assignment rather than on an enclosing function name, so
    # renaming the serialiser cannot turn this into a test that passes by
    # finding nothing.
    source = inspect.getsource(api_v1)
    assert 'row["visual_theme"] = _stored_visual_theme(' in source, (
        "the brand read path must call _stored_visual_theme; calling the "
        "strict validator there is the v8.5.2 outage verbatim"
    )
    assert 'row["visual_theme"] = _normalize_visual_theme(' not in source


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


# ── v8.8.0: refreshing a stored theme must not overwrite what the studio chose ──

def test_the_refresh_script_only_replaces_solved_colours() -> None:
    """A stored theme holds two different kinds of value.

    Colours are DERIVED — recomputing them from the generator is the whole
    point of a refresh. `button_style`, `font_mood` and `style_id` are
    ANSWERS: the studio picked them, and `style_theme()` returns its own
    defaults for all three. A wholesale merge therefore resets a studio's
    button shape and typeface every time anyone regenerates a palette.

    Measured on production before this line existed: four of six tenants would
    have moved `button_style rounded→soft` and `font_mood classic→serif`,
    inside a script whose stated job was to change nothing but colour.
    """

    source = (REPOSITORY_ROOT / "backend/scripts/refresh_stored_themes.py").read_text(
        encoding="utf-8"
    )
    assert 'k.endswith("_color") or k == "color_scheme"' in source, (
        "the refresh merges every key the solver returns — it will clobber "
        "button_style and font_mood"
    )
    # The unrestricted form may appear in the comment that explains why it is
    # wrong; what must not exist is the assignment.
    assert "merged = {**stored, **fresh}" not in source


def test_the_refresh_script_carries_the_tenants_own_accent_hue() -> None:
    """Since v8.5.x most tenants sit on the free-accent style.

    `style_theme(style_id, scheme)` without the third argument solves the
    DEFAULT accent, so a refresh that forgets it repaints every studio in one
    colour. That is precisely what `migrate_visual_themes.py` would do today,
    which is why this narrower script exists.
    """

    source = (REPOSITORY_ROOT / "backend/scripts/refresh_stored_themes.py").read_text(
        encoding="utf-8"
    )
    assert "style_theme(style_id, scheme, hue)" in source
    assert 'theme.get("accent_hue")' in source
