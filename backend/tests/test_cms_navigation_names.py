"""One page, one name — and an English word for every one of them.

Two hand-written maps used to name the same screens: ``NAV_GROUPS`` for the
sidebar and ``cmsPageTitle`` for the header. They drifted, as duplicated lists
in this codebase always have — the sidebar said 课程 / 学员 / 作品 while the
page called itself 课程目录 / 学员档案 / 作品管理, so the same screen answered
to two different names depending on where the operator looked.

``cmsPageTitle`` is now derived from ``NAV``. What this file guards is the part
derivation cannot fix: that every label a person actually reads has an English
entry. An unlisted string falls through to Chinese, which is not a crash and
not a blank — it is an English console with Chinese words in it, and nothing
fails when it happens.
"""

from __future__ import annotations

import re
from pathlib import Path

from _cms_sources import cms_source_text

I18N = Path(__file__).resolve().parents[1] / "frontend/assets/cms-i18n.js"

#: `{k:'billing',i:'money',l:'账单与发票',s:'账单'}` — the long label is what
#: the sidebar renders and, now, what the header renders too.
NAV_ITEM = re.compile(r"\{k:'(\w+)',\s*i:'\w+',\s*l:'([^']+)',\s*s:'([^']+)'")
#: Group headings: `{key:'teaching', label:'教学运营', items:[`
NAV_GROUP = re.compile(r"\{key:'\w+',\s*label:'([^']+)'")
EXTRAS = re.compile(r"CMS_PAGE_TITLE_EXTRAS = \{([^}]*)\}")
DICT_ENTRY = re.compile(r"\['([^']+)',\s*'[^']+'\]")


def _nav_groups_block(source: str) -> str:
    """Just the NAV_GROUPS literal.

    Scoped deliberately: `{key:…, label:…}` is a common shape in this file and
    an unscoped scan pulled in three student-profile section headings that have
    nothing to do with navigation. A guard that reports strings the reader
    cannot find in the sidebar teaches people to ignore it.
    """

    start = source.index("const NAV_GROUPS = [")
    end = source.index("const NAV = NAV_GROUPS", start)
    return source[start:end]


def _navigation_strings() -> set[str]:
    source = _nav_groups_block(cms_source_text())
    names: set[str] = set()
    for _key, long_label, short_label in NAV_ITEM.findall(source):
        names.add(long_label)
        names.add(short_label)
    names.update(NAV_GROUP.findall(source))
    extras = EXTRAS.search(cms_source_text())
    if extras:
        names.update(re.findall(r"'([^']+)'", extras.group(1)))
    return names


def test_the_sidebar_and_the_header_cannot_disagree():
    """`cmsPageTitle` must be derived, not a second list to keep in step."""

    source = cms_source_text()
    assert "NAV.find(item => item.k === tab)" in source, (
        "cmsPageTitle no longer reads its names from NAV. Two lists naming the "
        "same screens is exactly what produced 课程 in the sidebar and 课程目录 "
        "in the header."
    )


def test_every_navigation_label_has_an_english_word():
    dictionary = set(DICT_ENTRY.findall(I18N.read_text(encoding="utf-8")))
    missing = sorted(name for name in _navigation_strings() if name not in dictionary)
    assert not missing, (
        "These navigation labels fall through to Chinese in the English console. "
        f"Add them to cms-i18n.js: {missing}"
    )


def test_settings_sections_are_tabs_not_scroll_anchors():
    """The old pills declared `role="tablist"` and called `scrollIntoView`.

    Every section rendered at once and the pill only scrolled, so the highlight
    and the visible content could disagree — they did, in the screenshot that
    started this change. A screen reader was told there was a tab list and then
    found no tabpanel to go with it. Nothing failed, because a wrong ARIA role
    is not an error, it is a false statement.
    """

    source = cms_source_text()
    assert "SETTINGS_SECTIONS = [" in source, (
        "The tab strip and the panels must read one list. Two hand-written "
        "copies of the same sections is the bug this file already guards for "
        "the sidebar and the page header."
    )
    assert 'role="tabpanel"' in source, "sections must be real tabpanels"
    assert "scrollIntoView" not in source.split("SETTINGS_SECTIONS")[1][:4000], (
        "a settings tab scrolled instead of switching — that is the anchor "
        "behaviour this replaced"
    )
