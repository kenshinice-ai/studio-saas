"""The Platform Admin tenant editor: tabs that are actually connected.

The strip of section buttons above the tenant form did nothing at all. Not a
styling problem and not an event-bubbling problem — `editTenant()` rendered the
markup and never called the function that attaches the listeners. The only call
sat in `addPlan()`, an editor with no such strip.

Nobody noticed for a release because the accordions underneath still worked:
`<details>` needs no JavaScript, so the form stayed usable and the tabs were
simply inert decoration.

These tests pin the shape that failure had, because the shape is what makes it
invisible: markup that renders, and a handler that is never reached.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONSOLE = (PROJECT_ROOT / "super-admin.html").read_text(encoding="utf-8")

TAB_KEYS = ("basic", "contacts", "admin", "subscription", "limits")


def _function_body(name: str) -> str:
    """The source of one top-level function in the console."""

    start = CONSOLE.index(f"function {name}(")
    tail = CONSOLE[start:]
    end = re.search(r"\n    (?:async )?function ", tail[1:])
    return tail[: end.start() + 1] if end else tail


def test_the_editor_wires_the_tabs_it_renders() -> None:
    """The exact defect: markup without its handler.

    `editTenant` builds the tablist, so `editTenant` has to connect it. A
    tablist wired from somewhere else is a tablist that stops working the day
    that somewhere else changes.
    """

    body = _function_body("editTenant")
    assert 'class="editor-tabs" role="tablist"' in body, "the editor renders no tablist"
    assert "wireEditorTabs(" in body, (
        "editTenant renders a tablist and never wires it — this is the v9.9.4 bug"
    )
    # And the call that used to live in the wrong editor is gone.
    assert "wireEditorSectionNav" not in CONSOLE


def test_every_tab_has_a_panel_and_every_panel_a_tab() -> None:
    """A tab pointing at nothing is a dead click; a panel with no tab is lost."""

    for key in TAB_KEYS:
        assert f"editorTabButton('{key}'" in CONSOLE, f"no tab for {key}"
        assert f'data-editor-panel="{key}"' in CONSOLE, f"no panel for {key}"
    panels = re.findall(r'data-editor-panel="([a-z]+)"', CONSOLE)
    assert sorted(panels) == sorted(TAB_KEYS), panels


def test_the_panels_are_panels_and_not_accordions() -> None:
    """Two navigation models on one form is what produced a dead one."""

    body = _function_body("editTenant")
    assert "<details" not in body, "the tenant editor still contains an accordion"
    assert body.count('role="tabpanel"') == len(TAB_KEYS)


def test_the_tablist_carries_the_semantics_a_keyboard_user_needs() -> None:
    """Roving tabindex and arrow keys, the same as the tenant detail view."""

    button = _function_body("editorTabButton")
    for attribute in ('role="tab"', "aria-controls=", "aria-selected=", "tabindex="):
        assert attribute in button, attribute
    wiring = _function_body("wireEditorTabs")
    for key in ("ArrowRight", "ArrowLeft", "Home", "End"):
        assert key in wiring, f"{key} does not move between tabs"
    select = _function_body("selectEditorTab")
    assert "tab.tabIndex = on ? 0 : -1" in select, "roving tabindex is missing"
    assert "panel.hidden = !on" in select, "selecting a tab must hide the others"


@pytest.mark.parametrize(
    "refusal",
    [
        "Name and slug are required.",
        "Review the plan impact and acknowledge tenant notification before saving.",
        "Check the subscription dates.",
    ],
)
def test_every_save_refusal_moves_the_operator_to_the_problem(refusal: str) -> None:
    """A tabbed form can put the error on a page nobody is looking at.

    "Check the subscription dates" is a dead end when the subscription tab is
    hidden, so each refusal selects the tab holding the field before it
    complains.
    """

    body = _function_body("saveTenantModal")
    assert refusal in body
    before = body[: body.index(refusal)]
    assert "revealEditorProblem(" in before, (
        f"the refusal {refusal!r} does not reveal the field it is about"
    )


def test_a_tab_says_what_it_is_hiding() -> None:
    """Splitting a form across tabs owes the operator a count and a dot."""

    flags = _function_body("refreshEditorTabFlags")
    assert '[aria-invalid="true"]' in flags, "invalid fields are not counted per tab"
    assert '[role="alert"]' in flags, "a visible alert on a hidden tab must show too"
    assert '[data-edited="true"]' in flags, "changed fields are not marked per tab"
    # And the count is refreshed where those two states change.
    assert "refreshEditorTabFlags()" in _function_body("markEditedSections")
    assert "refreshEditorTabFlags()" in _function_body("validateSubscriptionDates")


def test_a_sentence_built_around_a_value_is_not_left_for_the_dictionary() -> None:
    """`admin-i18n` matches whole strings, so "Inherited from X plan." never hits.

    Splitting the words from the value is what makes the words translatable at
    all — the plan name is a proper noun and stays as the operator typed it.
    """

    assert "Inherited from ${" not in CONSOLE
    assert "<span>Inherited from plan</span>" in CONSOLE
