"""The card an owner picks and the page it publishes have to say one thing.

`slogan` is what the industry card renders in Studio Admin. `hero.title` is
what the published site renders. Through v8.2.31 those were two hand-written
strings per industry, and in Chinese five of the eight had drifted: a studio
choosing 艺术 read 「大胆创作，让成长看得见。」 on the card and shipped
「让创意被看见，让成长有作品。」 to the public site. In English the two happened
to be identical everywhere, so nobody reading the file in English could see it.

`hero.title` is derived from the slogan now, so the fork cannot come back by
hand. The rest of the checks here are the copy rules the presets were breaking:

* the two languages of one field do the same job (both an invitation, not a
  noun label in English and a sentence in Chinese);
* the register lead names what will actually be asked instead of repeating the
  heading above it;
* nothing is left in one language only.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from studiosaas.presets import (
    INDUSTRY_PRESETS,
    INDUSTRY_SECTION_COPY,
    public_industry_presets,
)

INDUSTRIES = sorted(INDUSTRY_PRESETS)
HAS_CJK = re.compile(r"[一-鿿]")
PRESETS_SOURCE = Path(__file__).resolve().parents[1] / "studiosaas" / "presets.py"


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_the_card_and_the_published_hero_say_the_same_thing(industry: str) -> None:
    preset = INDUSTRY_PRESETS[industry]
    assert preset["hero"]["title"]["zh"] == preset["slogan_zh"]
    assert preset["hero"]["title"]["en"] == preset["slogan"]


def test_the_hero_title_is_derived_and_not_written() -> None:
    """A literal `title` back in the source is the fork growing back.

    The derivation at the bottom of presets.py overwrites whatever a literal
    says, so a hand-written one would be dead rather than wrong — which is
    worse, because the next reader would believe it.
    """

    text = PRESETS_SOURCE.read_text(encoding="utf-8")
    start = text.index("INDUSTRY_PRESETS: dict[str, dict] = {")
    literals = text[start:text.index("def _operational_template(", start)]
    assert '"title":' not in literals, (
        "an industry preset writes hero.title literally; it is derived from the slogan"
    )


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_both_languages_of_a_field_are_present_and_different(industry: str) -> None:
    preset = INDUSTRY_PRESETS[industry]
    pairs = {
        "slogan": (preset["slogan"], preset["slogan_zh"]),
        "registration_title": (preset["registration_title"], preset["registration_title_zh"]),
        "register_intro": (preset["copy_pack"]["register_intro"], preset["register_intro_zh"]),
        "hero_subtitle": (preset["hero"]["subtitle"]["en"], preset["hero"]["subtitle"]["zh"]),
    }
    for field, (english, chinese) in pairs.items():
        assert english.strip(), f"{industry}.{field} has no English"
        assert chinese.strip(), f"{industry}.{field} has no Chinese"
        assert HAS_CJK.search(chinese), f"{industry}.{field} zh is not Chinese"
        assert not HAS_CJK.search(english), f"{industry}.{field} en contains Chinese"


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_the_registration_heading_invites_in_both_languages(industry: str) -> None:
    """The register page's own default heading is an invitation, so presets match it.

    tenant-template/register.html falls back to 「告诉我们学员的情况」 /
    "Tell us about the student" — a sentence, under an eyebrow that already
    says "Quick Registration". The Chinese presets followed that voice and the
    English ones did not: they were noun labels ("Creative Preferences",
    "Music Goals"), which read as a form section rather than an invitation and
    never mention registering at all.
    """

    preset = INDUSTRY_PRESETS[industry]
    assert preset["registration_title"].lower().startswith("tell us"), (
        f"{industry}: the English heading is not an invitation"
    )
    assert preset["registration_title_zh"].startswith("告诉我们"), (
        f"{industry}: the Chinese heading is not an invitation"
    )


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_the_register_lead_does_not_repeat_its_own_heading(industry: str) -> None:
    """Heading invites, lead says what will be asked and what comes back."""

    preset = INDUSTRY_PRESETS[industry]
    english = preset["copy_pack"]["register_intro"]
    chinese = preset["register_intro_zh"]
    assert not english.lower().startswith("tell us"), (
        f"{industry}: the English lead restarts the heading"
    )
    assert not chinese.startswith("告诉我们"), (
        f"{industry}: the Chinese lead restarts the heading"
    )
    # Specificity over vagueness: the lead has to promise something concrete.
    assert any(word in english.lower() for word in
               ("class", "time", "teacher", "plan", "squad", "project", "session")), (
        f"{industry}: the English lead names no outcome"
    )


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_the_english_label_carries_what_the_chinese_label_carries(industry: str) -> None:
    """`Game` for 游戏与编程 dropped coding, which is half of what is sold."""

    preset = INDUSTRY_PRESETS[industry]
    if industry == "game":
        assert "cod" in preset["label"].lower()
        assert "编程" in preset["label_zh"]


def test_the_public_shape_carries_the_derived_hero_title() -> None:
    """The admin surfaces read public_industry_presets(), not the raw dict."""

    public = public_industry_presets()
    for industry, preset in INDUSTRY_PRESETS.items():
        localized = public[industry]["localizedCopy"]
        assert localized["hero_title"]["zh"] == preset["slogan_zh"]
        assert localized["hero_title"]["en"] == preset["slogan"]
        assert public[industry]["sloganZh"] == localized["hero_title"]["zh"]
        assert public[industry]["slogan"] == localized["hero_title"]["en"]


def test_the_console_placeholder_matches_the_general_preset() -> None:
    """Studio Admin ships a literal `general` preset for the pre-fetch moment.

    It is a second copy of strings that live in presets.py, which is how copy
    forks start. Pinned here so it is updated with the preset or fails loudly.
    """

    console = (Path(__file__).resolve().parents[1] / "frontend"
               / "studio-admin.html").read_text(encoding="utf-8")
    block = console[console.index("let INDUSTRY_PRESETS = {"):]
    block = block[:block.index("let VISUAL_STYLE_PRESETS")]
    general = INDUSTRY_PRESETS["general"]
    for value in (
        general["slogan"],
        general["slogan_zh"],
        general["registration_title"],
        general["registration_title_zh"],
        general["copy_pack"]["register_intro"],
        general["register_intro_zh"],
    ):
        assert value in block, f"the console placeholder has drifted: {value!r} is missing"


@pytest.mark.parametrize("industry", INDUSTRIES)
def test_section_copy_is_bilingual_for_every_industry(industry: str) -> None:
    copy = INDUSTRY_SECTION_COPY.get(industry, INDUSTRY_SECTION_COPY["general"])
    for field, pair in copy.items():
        assert set(pair) >= {"zh", "en"}, f"{industry}.{field} is not bilingual"
        assert HAS_CJK.search(pair["zh"]), f"{industry}.{field} zh is not Chinese"
        assert pair["en"].strip(), f"{industry}.{field} has no English"
