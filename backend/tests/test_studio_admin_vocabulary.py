"""Studio Admin says one thing one way.

The console had two meanings for "publish": a switch called `Publish Space &
Experience`, which only wrote a draft, and the button in the save bar, which
actually put the draft on the internet. An owner who used the first and left
was entitled to think they had used the second.

It also had five grammars for one control, four names for three fields, three
spellings of one module, and nine "is this public" switches spread over four
panels — so there was nowhere to see what the public site contained.
"""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ADMIN = (PROJECT_ROOT / "backend/frontend/studio-admin.html").read_text(encoding="utf-8")

SECTION_SWITCHES = (
    "settingShowAbout",
    "settingShowPrincipal",
    "settingShowShowcase",
    "settingShowCourses",
    "settingShowTimetable",
    "settingShowGallery",
    "settingShowFaq",
    "settingShowContact",
    "settingShowStudentArea",
)


def test_publish_means_one_thing():
    """`Publish` belongs to the button that puts a draft on the internet."""

    assert "Publish Space &amp; Experience" not in ADMIN
    assert 'id="publishSettingsBtn" class="btn-primary">Publish<' in ADMIN
    for switch in SECTION_SWITCHES:
        label = re.search(rf'<label class="switch-label" for="{switch}">([^<]+)</label>', ADMIN)
        assert label, f"{switch} has no switch label"
        assert label.group(1).startswith("Show "), f"{switch} is labelled {label.group(1)!r}"
        assert "on the website" in label.group(1), switch


def test_one_place_shows_what_the_public_site_contains():
    """Three of the nine switches used to live in their own panels."""

    panel = ADMIN.split('data-workbench-panel="website"', 1)[1].split('data-workbench-panel="principal"', 1)[0]
    for switch in SECTION_SWITCHES:
        assert f'for="{switch}"' in panel, f"{switch} is not in the one list"
        assert ADMIN.count(f'id="{switch}"') == 1, f"{switch} has two controls"


def test_a_module_panel_points_at_its_switch_instead_of_repeating_it():
    """Two controls bound to one setting is one of them being wrong."""

    for switch in ("settingShowAbout", "settingShowShowcase", "settingShowTimetable", "settingShowPrincipal"):
        assert f'data-goto-switch="{switch}"' in ADMIN, switch
    assert "switchWorkbenchTab('website')" in ADMIN


def test_the_principal_has_a_panel_like_every_other_module():
    """Nine fields about one person lived in the tab that holds the switches."""

    assert 'data-workbench-tab="principal"' in ADMIN
    assert 'data-workbench-panel="principal"' in ADMIN
    assert "'principal', 'showcase'" in ADMIN  # registered in WORKBENCH_TABS
    panel = ADMIN.split('data-workbench-panel="principal"', 1)[1].split('data-workbench-panel="about"', 1)[0]
    for field in ("settingPrincipalName", "settingPrincipalBio", "settingPrincipalQuoteEn"):
        assert f'id="{field}"' in panel, field


def test_three_fields_have_one_set_of_names():
    """Section Eyebrow / Page Eyebrow / Eyebrow were the same field."""

    for retired in ("Section Eyebrow", "Page Eyebrow", "Section Title", "Section Lead", "Page Lead"):
        assert retired not in ADMIN, retired
    for kept in ("Eyebrow · 中文", "Title · 中文", "Lead · 中文"):
        assert kept in ADMIN, kept


def test_a_module_is_spelled_the_same_way_in_its_tab_and_its_heading():
    """`Preview & publish` had a panel headed `Preview and publish`."""

    assert "Preview and publish" not in ADMIN
    assert "Space and experience" not in ADMIN
    for label in ("Preview &amp; publish", "Space &amp; experience"):
        assert ADMIN.count(label) >= 2, label


def test_the_switch_says_why_a_section_the_owner_wants_is_not_public():
    """`no_consented_student_work` is not a fault; it is a consent not given.

    The contract already knew. It was printed as a bare identifier on a
    different tab, so the switch itself looked broken.
    """

    for module in ("about", "principal", "showcase", "courses", "timetable",
                   "gallery", "faq", "contact", "student"):
        assert f'data-surface-state="{module}"' in ADMIN, module
    assert "function renderSurfaceSwitchStates(" in ADMIN
    assert "no_consented_student_work" in ADMIN
    assert "还没有学员同意公开作品" in ADMIN
    # The raw identifier must not reach the owner any more.
    assert "${module.key} · ${module.reasonCode}" not in ADMIN
