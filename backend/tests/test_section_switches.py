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
API = REPOSITORY_ROOT / "backend/studiosaas/api_v1"

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
    # The seventh. It was the orphan this file recorded in v8.5.3 — stored,
    # validated and rendered, with no control anywhere — and it is now a
    # switch like the rest.
    "show_about": ("about", "settingShowAbout",
                   "resolveSection('about', false)"),
    # The eighth. The studio's own portfolio — see Showcase_Section.md.
    "show_showcase": ("showcase", "settingShowShowcase",
                      "resolveSection('showcase', false)"),
}

# v8.9.0. Switches that do NOT govern a band on the portal, and so cannot be
# checked by the rules above.
#
# The public timetable is its own page. Turning it off is therefore not "hide a
# section" but "there is no page" — and that is a stronger guarantee than any
# switch in the table above can make, because the SERVER refuses. A section
# switch only stops markup being revealed; here the data never leaves.
#
# So these get the assertion that actually matters for them: the public
# endpoint must return `enabled: False` rather than the classes.
PAGE_SWITCHES = {
    "show_timetable": ("settingShowTimetable", "public_timetable"),
    # A sub-switch of the same page: the timetable can be published without
    # accepting requests, and a studio that has not decided yet should not be
    # collecting phone numbers by default.
    "show_timetable_booking": ("settingShowTimetableBooking", "public_class_booking"),
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
    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(API.glob("*.py")))
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

    `show_about` was exactly that: the portal rendered a whole About section
    from it — bilingual heading, body, a six-image carousel — the server
    validated it, and Studio Admin had no control, so no studio ever saw it.
    Worse than invisible: because `_normalize_website_profile` rebuilds the
    profile from the payload alone, every Save from a page that did not send
    those fields erased them.

    The list of known orphans is now empty, and stays empty.
    """

    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(API.glob("*.py")))
    start = source.index("def _normalize_website_profile")
    end = source.index("\ndef ", start + 1)
    stored = set(re.findall(r'"(show_[a-z_]+)"', source[start:end]))

    orphaned = {flag for flag in stored - set(SWITCHES) - set(PAGE_SWITCHES)}
    assert not orphaned, (
        f"the server stores {sorted(orphaned)} but nothing in Studio Admin "
        f"can set it; add a control or stop storing it"
    )


@pytest.mark.parametrize("flag", sorted(PAGE_SWITCHES))
def test_every_page_switch_has_an_admin_control(flag: str) -> None:
    control, _ = PAGE_SWITCHES[flag]
    assert f'id="{control}"' in ADMIN.read_text(encoding="utf-8"), (
        f"{flag} has no control in Studio Admin"
    )


@pytest.mark.parametrize("flag", sorted(PAGE_SWITCHES))
def test_a_page_switch_is_enforced_by_the_server_not_by_hiding_a_link(flag: str) -> None:
    """Removing the link is not removing the page.

    A visitor who has the URL — bookmarked it, was sent it, found it in a
    search result — reaches the page whatever the portal's navigation shows.
    So the endpoint behind it has to read the switch itself and refuse, and
    that is what this pins.

    It is a stronger promise than any section switch can make: a hidden
    section is markup the browser was told not to reveal, while this is data
    that never left the building.
    """

    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(API.glob("*.py")))
    _, endpoint = PAGE_SWITCHES[flag]
    start = source.index(f"def {endpoint}(")
    body = source[start:source.index("\n@api_v1.route", start)]
    assert f'profile.get("{flag}")' in body, (
        f"{endpoint}() never reads {flag}; the switch would only hide a link"
    )
    assert ('"enabled": False' in body) or ("404" in body), (
        f"{endpoint}() reads {flag} but still serves its payload when it is off"
    )


def test_the_admin_sends_every_field_the_server_stores() -> None:
    """A Save must not be able to erase a field it has no control for.

    `_normalize_website_profile` rebuilds the profile from the payload alone —
    it does not merge with what is stored. So any key the server keeps and
    Studio Admin omits is deleted on the studio's next Save, silently, whether
    or not that studio ever opened the tab.

    That is how the About copy and the flagship tenant's reclaimed SEO title
    were lost: seven fields were stored, rendered, and never sent back.

    Written against the SERVER's list rather than a list kept here, so adding
    a field to the profile without adding it to the payload fails immediately
    instead of the next time somebody clicks Save.
    """

    source = "\n".join(p.read_text(encoding="utf-8") for p in sorted(API.glob("*.py")))
    start = source.index("def _normalize_website_profile")
    end = source.index("\ndef ", start + 1)
    body = source[start:end]

    # Three ways the function writes a key, all of them counted. The loops
    # matter most: `about_eyebrow`, `about_title` and `about_body` are only
    # ever named inside one, so reading just the first loop would have made
    # this test pass while three of the lost fields went unchecked.
    stored = set(re.findall(r'profile\["([a-z_]+)"\]', body))
    stored |= set(re.findall(r'"(show_[a-z_]+)"', body))
    for group in re.findall(r'for key in \(\s*("[a-z_",\s]+")\s*\)', body):
        stored |= set(re.findall(r'"([a-z_]+)"', group))

    admin = ADMIN.read_text(encoding="utf-8")
    payload = admin[admin.index("websiteProfile: {"):]
    payload = payload[:payload.index("\n        },")]

    def camel(snake: str) -> str:
        head, *rest = snake.split("_")
        return head + "".join(part.capitalize() for part in rest)

    missing = sorted(key for key in stored if f"{camel(key)}:" not in payload)
    assert not missing, (
        "Studio Admin's websiteProfile payload omits "
        f"{missing}; _normalize_website_profile will erase them on the next Save"
    )
