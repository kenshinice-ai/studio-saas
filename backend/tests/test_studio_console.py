"""Studio Admin: the chrome budget, the touch floor, and bilingual coverage.

Three things v8.3.0 changed about this page, each of which was measured before
it was changed and each of which regresses silently if nothing holds it:

* **Space.** The header, the section header and a workbench hero each took a
  band of their own and together put the first editable control 574px down a
  900px screen — and 906px down an 844px phone. Two of those layers are gone
  and the third is one row.
* **Touch.** 94 controls measured under 44x44. Two rules in the page's own
  override block (`button { min-height: 38px }`,
  `input, select, textarea { min-height: 42px }`) sat below the base rules and
  beat them, which is why raising the base alone would not have worked.
* **Language.** `applyAttributes()` in admin-i18n.js has always localised
  placeholder / title / aria-label. 26 of them simply had no dictionary entry,
  so a console switched to Chinese still hinted in English inside every field.
  Nothing had ever walked the rendered page to find that out.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONSOLE = REPOSITORY_ROOT / "backend" / "frontend" / "studio-admin.html"
DICTIONARY = REPOSITORY_ROOT / "backend" / "frontend" / "assets" / "admin-i18n.js"


def console() -> str:
    return CONSOLE.read_text(encoding="utf-8")


def script_source() -> str:
    """Only the code that runs.

    v8.2.30 shipped a block of JavaScript above the doctype where it rendered
    as text, and the test written for that change passed because it searched
    the whole file. Behaviour is asserted against `<script>` contents here.
    """

    return "\n".join(re.findall(r"<script>(.*?)</script>", console(), re.S))


def style_source() -> str:
    return "\n".join(re.findall(r"<style>(.*?)</style>", console(), re.S))


# ── the page still starts where a page starts ────────────────────────────────

def test_nothing_precedes_the_doctype() -> None:
    assert console().startswith("<!DOCTYPE html>")


@pytest.mark.parametrize("name", [
    "syncHeaderOffset", "setSettingsDirty", "switchWorkbenchTab", "setAuthState",
])
def test_each_function_is_defined_once_and_inside_the_script(name: str) -> None:
    whole = console().count(f"function {name}(")
    running = script_source().count(f"function {name}(")
    assert running == 1, f"{name} is defined {running} times inside <script>"
    assert whole == running, f"{name} also appears outside <script>"


# ── space ────────────────────────────────────────────────────────────────────

def test_the_workbench_hero_is_gone() -> None:
    """137px of marketing copy inside a tool, restating the tabs beneath it."""

    markup = console()
    for remnant in ('class="workbench-hero"', 'class="workbench-title"',
                    'class="workbench-kicker"', 'id="workbenchStatus"'):
        assert remnant not in markup, f"{remnant} is back"


def test_the_settings_section_does_not_repeat_the_nav_label() -> None:
    """`官网与品牌` used to appear as nav item, section header and page title.

    The section header for #section-settings is the one that duplicated the
    active nav item. Public Pages keeps its own, because nothing else names it.
    """

    markup = console()
    settings = markup[markup.index('<section id="section-settings"'):
                      markup.index('<section id="section-public-surfaces"')]
    assert 'class="section-header"' not in settings
    assert 'class="section-header"' in markup, "Public Pages lost its header too"


def test_draft_state_is_reported_in_exactly_one_place() -> None:
    """Two readouts of one fact, in two wordings, is two things to keep in step."""

    assert script_source().count("$('saveBarStatus')") >= 1
    assert "workbenchStatus" not in script_source()


def test_the_header_is_one_row_carrying_brand_nav_and_account() -> None:
    markup = console()
    header = markup[markup.index('<header class="header">'):markup.index("</header>")]
    assert header.count('<div class="header-top">') == 1
    for part in ('class="brand"', 'id="studioNav"', 'class="header-actions"',
                 'id="headerMenu"'):
        assert part in header, f"{part} is not in the header row"


def test_the_header_no_longer_duplicates_links_the_nav_already_has() -> None:
    """`Open CMS` was a header button, a nav link and a Public Pages card."""

    markup = console()
    header = markup[markup.index('<header class="header">'):markup.index("</header>")]
    assert 'id="openCmsBtn"' not in header
    assert 'id="openRegisterBtn"' not in header
    assert 'id="openCmsLink"' in header, "the nav link is the one that stays"


def test_the_sticky_offset_is_measured_rather_than_hardcoded() -> None:
    """The old `top: 136px` was the two stacked bands' height, written by hand."""

    styles = style_source()
    assert "top: 136px" not in styles
    assert "var(--header-h" in styles
    assert "syncHeaderOffset" in script_source()


def test_signing_in_remeasures_the_header() -> None:
    """Revealing the nav is the one moment the header changes height by a lot.

    A ResizeObserver catches it on the next rendered frame, and a background
    tab renders no frames, so setAuthState measures directly.
    """

    source = script_source()
    auth = source[source.index("function setAuthState("):]
    auth = auth[:auth.index("\n    }")]
    assert "syncHeaderOffset()" in auth


# ── touch targets ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("selector", ["button", "input, select, textarea"])
def test_no_override_lowers_a_control_below_the_touch_target(selector: str) -> None:
    """Both floors lived in the override block, where they beat the base rules.

    The selector is anchored to the start of its line so `.preview-button` —
    a span drawn inside the mock of the tenant's own site, not a control —
    does not match `button`.
    """

    pattern = rf"^\s*{re.escape(selector)}\s*\{{([^}}]*)\}}"
    rules = re.findall(pattern, style_source(), re.M)
    assert rules, f"no bare `{selector}` rule found; has the selector been renamed?"
    for rule in rules:
        for value in re.findall(r"min-height:\s*(\d+)px", rule):
            assert int(value) >= 44, (
                f"`{selector}` sets min-height: {value}px, under the 44px target"
            )


def test_the_touch_target_comes_from_the_shared_token() -> None:
    styles = style_source()
    assert styles.count("var(--ui-touch-target") >= 8, (
        "controls are being sized with literals instead of the token"
    )


# ── mobile ───────────────────────────────────────────────────────────────────

def test_the_phone_pins_the_tab_strip_and_the_publish_bar() -> None:
    """Before v8.3.0 a phone pinned nothing: `.header` and `.save-bar` were
    both `position: static`, so the tab being edited under and the Publish
    button both scrolled away."""

    styles = style_source()
    mobile = styles[styles.index("@media (max-width: 768px)"):]
    tabs = mobile[mobile.index(".studio-tabs {"):]
    assert "position: sticky" in tabs[:tabs.index("}")]
    save = mobile[mobile.index(".save-bar {"):]
    save_rule = save[:save.index("}")]
    assert "position: sticky" in save_rule
    assert "env(safe-area-inset-bottom" in save_rule, "the bar sits under the home bar"


def test_the_settings_panel_can_host_a_sticky_child_on_a_phone() -> None:
    """`overflow: hidden` makes an ancestor a scroll container, and a sticky
    child of one never sticks to the viewport."""

    styles = style_source()
    mobile = styles[styles.index("@media (max-width: 768px)"):]
    assert ".settings-panel { overflow: visible; }" in mobile


# ── bilingual coverage ───────────────────────────────────────────────────────

# Values that are deliberately identical in both languages: worked examples of
# an email address or a URL, which a Chinese reader types verbatim.
UNTRANSLATED_BY_DESIGN = {
    "owner@studio.test",
    "studio@example.com",
    "https://...",
}


def dictionary_keys() -> set[str]:
    text = DICTIONARY.read_text(encoding="utf-8")
    table = text[text.index("const zh = Object.fromEntries(["):]
    table = table[:table.index("\n  ]);")]
    # Strip comments first: several entries are explained in prose that also
    # contains quoted English, which would otherwise register as an entry.
    table = re.sub(r"/\*.*?\*/", "", table, flags=re.S)
    return set(re.findall(r"\['((?:[^'\\]|\\.)*)',", table))


def authored_attribute_values() -> set[str]:
    found = set()
    for attribute in ("placeholder", "aria-label", "title"):
        for value in re.findall(rf'{attribute}="([^"]+)"', console()):
            if not re.search(r"[A-Za-z]{3}", value):
                continue
            if re.search(r"[一-鿿]", value):
                continue
            # Template literals are assembled at runtime out of values that
            # are already localised; there is no authored English to translate.
            if "${" in value or "__" in value or value.startswith("{{"):
                continue
            found.add(value)
    return found


def test_every_authored_hint_has_a_chinese_translation() -> None:
    """A field labelled in Chinese that hints in English is half-translated.

    This walks the markup rather than the dictionary, so the failure mode it
    catches is the one that happened: adding a placeholder and not adding its
    entry. The dictionary cannot report what it was never told about.
    """

    known = dictionary_keys() | UNTRANSLATED_BY_DESIGN
    missing = sorted(value for value in authored_attribute_values() if value not in known)
    assert not missing, (
        "these placeholder / aria-label / title values have no Chinese entry in "
        f"admin-i18n.js: {missing}"
    )


def runtime_message_strings() -> set[str]:
    """English sentences the script writes into the page at runtime.

    Scoped to the three calls that put words in front of a person — assigning
    `.textContent`, raising a toast, and setting the login error — rather than
    to every string literal in the file, most of which are selectors and API
    paths. Multi-word only, for the same reason.
    """

    found = set()
    for line in script_source().splitlines():
        if not any(call in line for call in
                   (".textContent", "showToast(", "setLoginError(")):
            continue
        for value in re.findall(r"'([^'\\]{4,})'", line):
            if re.search(r"[A-Za-z]{3}", value) and " " in value:
                found.add(value)
    return found


def test_every_runtime_message_has_a_chinese_translation() -> None:
    """`No unsaved changes` was translated and `Unsaved changes` was not.

    The lookup is exact, so the save bar reverted to English the moment
    anything was edited — a state the attribute sweep cannot reach, because
    the string is never in the markup.
    """

    known = dictionary_keys()
    missing = sorted(value for value in runtime_message_strings()
                     if not re.search(r"[一-鿿]", value) and value not in known)
    assert not missing, (
        f"these runtime messages have no Chinese entry in admin-i18n.js: {missing}"
    )


def test_the_dictionary_does_not_translate_strings_the_page_no_longer_has() -> None:
    """Entries for deleted copy are claims nobody checks."""

    markup = console()
    for gone in ("Brand Builder", "Shape the public studio experience"):
        assert f"['{gone}'," not in DICTIONARY.read_text(encoding="utf-8"), (
            f"'{gone}' was removed from the page but kept in the dictionary"
        )
        assert f">{gone}<" not in markup
