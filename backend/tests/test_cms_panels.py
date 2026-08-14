"""Panels may only render components they can actually see.

`build_cms.sh --bundle` is what lets the CMS be more than one file, and it also
draws a line that did not exist before: each file is its own module scope. An
identifier defined in ``cms-app.jsx`` — ``Icon``, ``Kpi``, ``EmptyState`` — is
simply not there inside ``panels/*.jsx`` unless it is imported or passed.

The failure is not a missing icon. A JSX tag that resolves to ``undefined``
throws during render, React unmounts the tree, and the entire console goes
white. That happened once, to ``<Icon>`` in the student progress-report panel,
and the compiler said nothing: esbuild does not resolve JSX component names, and
every existing test greps the source for substrings that were all still present.

So the check has to look at what the JSX actually references and subtract what
the file can reach. Deriving both sides is the point — a hardcoded list of
banned names would go stale the first time somebody adds a component to
``cms-app.jsx``, which is exactly the class of guard that has already failed
this project four times.
"""

from __future__ import annotations

import re

from _cms_sources import CMS_SRC_DIR

#: Real globals: the page loads React and ReactDOM from /vendor before the
#: bundle, and index.html's only other contract is `<div id="root">`.
BROWSER_GLOBALS = {"React", "ReactDOM", "Fragment"}

#: `<Foo>` and `<Foo.Bar>` — the leading capital is what makes JSX treat a tag
#: as a component reference rather than an HTML element.
JSX_TAG = re.compile(r"<([A-Z][A-Za-z0-9_]*)")
IMPORTED = re.compile(r"import\s*\{([^}]*)\}\s*from|import\s+([A-Za-z0-9_]+)\s+from")
DECLARED = re.compile(r"(?:function|const|let|class)\s+([A-Z][A-Za-z0-9_]*)")


#: Comments in these files are prose about the code, and the prose talks about
#: components by name — the very comment explaining why `<Icon>` is unreachable
#: contains `<Icon>`. Scanning them would make the guard fail on its own
#: documentation, so strip them first.
COMMENT = re.compile(r"/\*.*?\*/|//[^\n]*", re.DOTALL)


def _code_only(text: str) -> str:
    return COMMENT.sub("", text)


def _reachable_names(text: str) -> set[str]:
    names = set(BROWSER_GLOBALS)
    for braced, default in IMPORTED.findall(text):
        for part in braced.split(","):
            name = part.split(" as ")[-1].strip()
            if name:
                names.add(name)
        if default:
            names.add(default)
    names.update(DECLARED.findall(text))
    # Destructured hooks and helpers: `const { useState } = React`.
    for block in re.findall(r"const\s*\{([^}]*)\}\s*=", text):
        names.update(part.split(":")[-1].strip() for part in block.split(",") if part.strip())
    return names


def test_panels_only_render_components_they_can_reach():
    panels = sorted((CMS_SRC_DIR / "panels").glob("*.jsx"))
    assert panels, "no panels found — did the source move?"

    unreachable: dict[str, set[str]] = {}
    for path in panels:
        text = _code_only(path.read_text(encoding="utf-8"))
        missing = set(JSX_TAG.findall(text)) - _reachable_names(text)
        if missing:
            unreachable[path.name] = missing

    assert not unreachable, (
        "These panels render components that do not exist in their module scope. "
        "esbuild will compile this and the browser will white-screen on first "
        "render. Import them, pass them as props, or write the markup directly: "
        f"{ {k: sorted(v) for k, v in unreachable.items()} }"
    )


def test_panels_stringify_request_bodies():
    """`v1Api` spreads its options into ``fetch`` — the body must be a string.

    ``fetch`` does not serialise a plain object; it stringifies it to
    ``"[object Object]"`` and sends that with a JSON content type. The server
    answers 400 "Request body must be a JSON object", which reads like a schema
    problem and is not one. Nothing in the request path can catch this: the JSX
    compiles, the call is made, and only the response is wrong.

    A helper that serialised for you would be the better fix, but changing
    ``v1Api``'s contract now would silently double-encode every existing caller
    that already stringifies. Policing the panels is the cheaper half.
    """

    offenders = []
    for path in sorted((CMS_SRC_DIR / "panels").glob("*.jsx")):
        text = _code_only(path.read_text(encoding="utf-8"))
        for line_no, line in enumerate(text.splitlines(), start=1):
            if re.search(r"\bbody:\s*[{\[]", line):
                offenders.append(f"{path.name}:{line_no}")

    assert not offenders, (
        "These calls pass an object as `body`; fetch will send the literal "
        f"string '[object Object]'. Wrap them in JSON.stringify: {offenders}"
    )


def test_every_pay_basis_has_a_human_name():
    """`per_hour` reached a teacher's pay sheet, printed as `per_hour`.

    The five bases are a database enum. A panel that renders the raw value is
    not broken in any way a test notices — it renders, it is even correct — it
    is simply English machine vocabulary on a document a person is meant to
    read and query. Missing one basis only shows up at the studio that happens
    to pay that way, which is the worst kind of gap to leave to chance.
    """

    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[1]
    service = (backend_root / "studiosaas/services/teaching_pay.py").read_text(encoding="utf-8")
    bases = set(re.search(r"RATE_BASES = \(([^)]*)\)", service).group(1).replace('"', "").split(", "))
    bases = {basis.strip() for basis in bases if basis.strip()}

    panel = (CMS_SRC_DIR / "panels" / "finance.jsx").read_text(encoding="utf-8")
    labelled = set(re.findall(r"^\s{2}(\w+):\s*'", panel, re.M))

    missing = sorted(bases - labelled)
    assert not missing, (
        f"These pay bases would print as their raw enum value on a pay sheet: {missing}"
    )


def test_no_panel_hardcodes_the_golden_grid_without_a_breakpoint():
    """φ splits a wide screen. On a phone it splits 375px into 143px.

    The panels each wrote `gridTemplateColumns: var(--ui-golden-columns-reverse)`
    as an inline style, which applies at every width — so the master/detail
    layout stayed two columns on a phone, where the secondary column is too
    narrow for a date input. It rendered, so nothing failed; it was simply
    unusable, and only visible by looking at the page at that width.

    `.ui-golden-split` in ui-tokens.css stacks by default and applies φ from
    768px up. One definition, so a new panel cannot forget the breakpoint.
    """

    offenders = []
    for path in sorted((CMS_SRC_DIR / "panels").glob("*.jsx")):
        text = _code_only(path.read_text(encoding="utf-8"))
        if "gridTemplateColumns: 'var(--ui-golden-columns" in text:
            offenders.append(path.name)

    assert not offenders, (
        "These panels apply the golden ratio at every width, including phone "
        f"widths where the secondary column collapses: {offenders}. "
        "Use className=\"ui-golden-split\"."
    )
