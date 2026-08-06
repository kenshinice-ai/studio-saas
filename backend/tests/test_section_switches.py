"""A section switch has to reach the section, not only its nav link.

Two of the six were wired to `setNavVisible` alone: switching off 课程 or
作品墙 removed the menu entry and left the section on the page. The studio
watched it disappear from the nav and concluded it was off; a visitor
scrolling past still saw it. Nothing failed, so nothing said so.

The portal reveals its data-fed sections asynchronously — `resolveSection`
sets `data-resolved` once content arrives — and `/brand` (which carries the
switches) and `/programs` / `/public-gallery` (which carry the content) are
independent fetches. So the switch has to be enforced in BOTH places, or
whichever answers last wins. That race is what these assert.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
PORTAL = REPOSITORY_ROOT / "tenant-template/index.html"
ADMIN = REPOSITORY_ROOT / "backend/frontend/studio-admin.html"
API = REPOSITORY_ROOT / "backend/studiosaas/api_v1.py"

# switch -> (portal section id, admin control id, the expression that carries
# the flag to that section). The third element is the point: it names HOW each
# switch is enforced, so a switch that quietly loses its enforcement fails here
# rather than being re-derived by a regex that might guess right.
SWITCHES = {
    "show_principal": ("artist", "settingShowPrincipal",
                       "resolveSection('artist', hasPrincipal)"),
    "show_courses": ("courses", "settingShowCourses",
                     "state.sectionsOff.courses"),
    "show_gallery": ("gallery", "settingShowGallery",
                     "state.sectionsOff.gallery"),
    "show_faq": ("faq", "settingShowFaq",
                 "state.sectionsOff.faq"),
    "show_contact": ("contact", "settingShowContact",
                     "showSection('contact'"),
    "show_student_area": ("parent", "settingShowStudentArea",
                          "showSection('parent'"),
}

# Sections revealed by their render function once content arrives. These are
# the ones a switch can lose the race against.
DATA_FED = {"courses", "gallery", "faq"}


def _portal() -> str:
    return PORTAL.read_text(encoding="utf-8")


@pytest.mark.parametrize("flag", sorted(SWITCHES))
def test_every_switch_has_an_admin_control(flag: str) -> None:
    _, control, _ = SWITCHES[flag]
    assert f'id="{control}"' in ADMIN.read_text(encoding="utf-8"), (
        f"{flag} has no control in Studio Admin"
    )


@pytest.mark.parametrize("flag", sorted(SWITCHES))
def test_every_switch_is_validated_by_the_server(flag: str) -> None:
    source = API.read_text(encoding="utf-8")
    start = source.index("def _normalize_website_profile")
    end = source.index("\ndef ", start + 1)
    assert f'"{flag}"' in source[start:end], (
        f"{flag} is set in the admin but not validated by the server"
    )


@pytest.mark.parametrize("flag", sorted(SWITCHES))
def test_every_switch_reaches_its_section(flag: str) -> None:
    """Hiding the nav link is not hiding the section.

    Each switch must either call showSection/resolveSection for its own
    section id, or be recorded in `state.sectionsOff` for the render function
    to honour. A switch whose only effect is setNavVisible fails here.
    """

    section, _, mechanism = SWITCHES[flag]
    portal = _portal()

    assert mechanism in portal, (
        f"{flag} no longer reaches the #{section} section through "
        f"`{mechanism}`. If the mechanism changed, update this table; if it "
        f"is gone, the switch only controls navigation and the section stays "
        f"on the page when a studio switches it off."
    )
    # And the flag itself has to be read somewhere, or the mechanism above is
    # driven by something other than the switch.
    assert flag in portal, f"{flag} is never read by the portal"


@pytest.mark.parametrize("section", sorted(DATA_FED))
def test_a_data_fed_section_cannot_be_revealed_past_its_switch(section: str) -> None:
    """The race, pinned.

    `/brand` carries the switches and `/programs` carries the content, and
    either can answer first. The render function must consult the switch, or a
    slow /brand means the section is revealed and never taken back down.
    """

    portal = _portal()
    # Only the calls that can REVEAL matter; `resolveSection(id, false)` is a
    # teardown (an image failed, the section folds away) and carries no switch.
    reveals = [match.group(1).strip()
               for match in re.finditer(
                   rf"resolveSection\('{section}',\s*([^)]+)\)\s*;", portal)
               if match.group(1).strip() != "false"]
    assert reveals, f"no revealing resolveSection call found for {section}"
    for condition in reveals:
        assert f"state.sectionsOff.{section}" in condition, (
            f"renderer for {section} reveals it without checking its switch: "
            f"resolveSection('{section}', {condition})"
        )


def test_the_switch_record_exists_before_any_render_can_read_it() -> None:
    """`state.sectionsOff` is read by three renderers that may run before
    /brand answers. Declared empty up front so they read a defined object
    rather than throwing on undefined."""

    portal = _portal()
    declared = portal.index("sectionsOff:{}")
    first_read = portal.index("state.sectionsOff.")
    assert declared < first_read, (
        "state.sectionsOff is read before it is declared"
    )


def test_no_website_switch_is_orphaned_on_the_server() -> None:
    """A field the server stores and nothing can set is a feature nobody has.

    `show_about` is exactly that today — the portal renders an About section
    from it, the server validates it, and Studio Admin has no control. It is
    listed here so the gap is a recorded decision rather than a discovery, and
    so a SECOND one cannot appear silently.
    """

    source = API.read_text(encoding="utf-8")
    start = source.index("def _normalize_website_profile")
    end = source.index("\ndef ", start + 1)
    stored = set(re.findall(r'"(show_[a-z_]+)"', source[start:end]))

    known_orphans = {"show_about"}
    orphaned = {flag for flag in stored - set(SWITCHES) - known_orphans}
    assert not orphaned, (
        f"the server stores {sorted(orphaned)} but nothing in Studio Admin "
        f"can set it; add a control or stop storing it"
    )
