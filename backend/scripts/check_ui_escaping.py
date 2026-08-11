#!/usr/bin/env python3
"""Static check: template-literal interpolations that end up in innerHTML
must go through esc() (or be explicitly marked safe).

Heuristic, not a parser. Three sources of HTML-bound template literals are
scanned (v7.6.0 closes the audit U3 blind spot — previously only the first
one was covered):

1. `.innerHTML =` / `.innerHTML +=` assignments whose value is a template
   literal;
2. template literals passed to `openModal(...)` as the body/footer arguments
   (the first argument is the title, which openModal assigns via textContent
   and is therefore not scanned);
3. template literals assigned to a variable (`const html = `...``,
   `body += `...``) when that variable later flows into a sink — an
   `.innerHTML` assignment or an `openModal(...)` call.

Nested template literals are followed: for an interpolation like
`${items.map(i => `...`).join('')}` the nested template's own
interpolations are checked instead of blindly flagging the outer
expression.

Every `${...}` interpolation found is flagged unless it matches the
safe-list. Suppress a false positive by making the expression start with
`/*safe*/`.

Exit code 1 when violations are found. Wired into verify_local.sh.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FILES = [
    "super-admin.html",
    "backend/frontend/studio-admin.html",
    "backend/frontend/setup-password.html",
    "legacy-root/index.html",
    "legacy-root/register.html",
    "tenant-template/index.html",
    "tenant-template/register.html",
    "tenant-template/showcase.html",
    "tenant-template/timetable.html",
    "tenant-template/studio-admin.html",
]

# name -> index of the first argument that reaches innerHTML. openModal's
# signature is (title, bodyHtml, footerHtml); the title goes to textContent.
SINK_CALLS = {"openModal": 1}

SAFE_EXPR = re.compile(
    r"^\s*(?:"
    r"/\*safe\*/"          # explicit suppression
    r"|esc\("               # escaped (shared helper)
    r"|escHtml\("           # escaped (legacy register's local helper)
    r"|Number\("            # numeric coercion
    r"|Math\."              # numeric
    r"|encodeURIComponent\("  # URL-encoded
    r"|JSON\.stringify\("   # JSON (quoted output)
    r"|new Date\("          # date formatting
    r")"
)


def interpolations(template: str):
    """Yield the expression text of each ${...} with balanced braces."""

    i = 0
    while True:
        start = template.find("${", i)
        if start == -1:
            return
        depth = 1
        j = start + 2
        while j < len(template) and depth:
            if template[j] == "{":
                depth += 1
            elif template[j] == "}":
                depth -= 1
            j += 1
        yield template[start + 2 : j - 1]
        i = j


def template_at(src: str, k: int) -> tuple[str, int] | None:
    """Return (template_body, index_past_closing_backtick) for the backtick at k.

    Understands nesting: backticks opened inside a ${...} expression do not
    terminate the outer template, so `a${x.map(i => `b`)}c` is one body.
    """

    if k >= len(src) or src[k] != "`":
        return None
    stack: list[list] = [["tpl"]]
    i = k + 1
    while i < len(src):
        frame = stack[-1]
        c = src[i]
        if frame[0] == "tpl":
            if c == "\\":
                i += 2
                continue
            if c == "`":
                stack.pop()
                if not stack:
                    return src[k + 1 : i], i + 1
            elif c == "$" and src[i + 1 : i + 2] == "{":
                stack.append(["expr", 1])
                i += 1
        else:  # inside a ${...} expression
            if c in "\"'":
                quote = c
                i += 1
                while i < len(src) and src[i] != quote:
                    if src[i] == "\\":
                        i += 1
                    i += 1
            elif c == "`":
                stack.append(["tpl"])
            elif c == "{":
                frame[1] += 1
            elif c == "}":
                frame[1] -= 1
                if frame[1] == 0:
                    stack.pop()
        i += 1
    return src[k + 1 :], len(src)


def template_after_assignment(src: str, idx: int) -> tuple[str, int] | None:
    """Return (template_body, line_no) if the assignment at idx uses a backtick."""

    m = re.compile(r"\.innerHTML\s*\+?=\s*").match(src, idx)
    if not m:
        return None
    found = template_at(src, m.end())
    if not found:
        return None
    template, _end = found
    line = src.count("\n", 0, idx) + 1
    return template, line


def call_span(src: str, open_paren: int) -> int:
    """Index just past the parenthesis matching src[open_paren]."""

    depth = 0
    i = open_paren
    while i < len(src):
        c = src[i]
        if c == "`":
            found = template_at(src, i)
            i = found[1] if found else len(src)
            continue
        if c in "\"'":
            quote = c
            i += 1
            while i < len(src) and src[i] != quote:
                if src[i] == "\\":
                    i += 1
                i += 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def split_top_level_args(args_text: str) -> list[tuple[str, int]]:
    """Split a call argument list on top-level commas -> [(text, offset)]."""

    parts: list[tuple[str, int]] = []
    depth = 0
    i = 0
    start = 0
    while i < len(args_text):
        c = args_text[i]
        if c == "`":
            found = template_at(args_text, i)
            i = found[1] if found else len(args_text)
            continue
        if c in "\"'":
            quote = c
            i += 1
            while i < len(args_text) and args_text[i] != quote:
                if args_text[i] == "\\":
                    i += 1
                i += 1
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append((args_text[start:i], start))
            start = i + 1
        i += 1
    parts.append((args_text[start:], start))
    return parts


def sink_call_html_args(src: str):
    """Yield (arg_text, arg_offset_in_src, call_name) for HTML-bound args."""

    for name, first_html_arg in SINK_CALLS.items():
        for m in re.finditer(rf"\b{name}\s*\(", src):
            open_paren = m.end() - 1
            end = call_span(src, open_paren)
            args_text = src[open_paren + 1 : end - 1]
            for arg_text, offset in split_top_level_args(args_text)[first_html_arg:]:
                yield arg_text, open_paren + 1 + offset, name


def templates_in(text: str, offset: int, src: str):
    """Yield (template_body, line_no) for backtick templates inside text."""

    i = 0
    while True:
        k = text.find("`", i)
        if k == -1:
            return
        found = template_at(text, k)
        if not found:
            return
        template, after = found
        yield template, src.count("\n", 0, offset + k) + 1
        i = after


# `const html = `...``, `let row = `...``, `body += `...`` — property accesses
# (`.innerHTML = `...``) are excluded by the lookbehind and handled above.
VAR_TEMPLATE_ASSIGN = re.compile(
    r"(?:\b(?:const|let|var)\s+)?(?<![.\w$])([A-Za-z_$][\w$]*)\s*\+?=\s*(?=`)"
)

IDENT = re.compile(r"[A-Za-z_$][\w$]*")


def template_variables(src: str) -> dict[str, list[tuple[str, int]]]:
    """Map variable name -> [(template_body, line_no)] for template assignments."""

    out: dict[str, list[tuple[str, int]]] = {}
    for m in VAR_TEMPLATE_ASSIGN.finditer(src):
        name = m.group(1)
        found = template_at(src, m.end())
        if not found:
            continue
        template, _end = found
        line = src.count("\n", 0, m.start()) + 1
        out.setdefault(name, []).append((template, line))
    return out


def sink_variable_names(src: str) -> set[str]:
    """Names referenced by an innerHTML assignment RHS or a sink-call HTML arg."""

    names: set[str] = set()
    # `el.innerHTML = html;` / `el.innerHTML = prefix + html`
    for m in re.finditer(r"\.innerHTML\s*\+?=\s*([^;\n]+)", src):
        names.update(IDENT.findall(m.group(1)))
    # `openModal(title, html, footer)` — identifiers in the HTML-bound args
    for arg_text, _offset, _name in sink_call_html_args(src):
        names.update(IDENT.findall(arg_text))
    return names


def check_template(rel: str, template: str, line: int, violations: list, note: str = "") -> None:
    for expr in interpolations(template):
        if SAFE_EXPR.match(expr):
            continue
        if "`" in expr:
            # Composition such as `${items.map(i => `...${esc(i.name)}...`)}`:
            # the HTML actually produced is the nested template, so judge its
            # interpolations instead of the outer expression.
            nested_found = False
            j = 0
            while True:
                b = expr.find("`", j)
                if b == -1:
                    break
                found = template_at(expr, b)
                if not found:
                    break
                nested, after = found
                nested_found = True
                check_template(rel, nested, line, violations, note)
                j = after
            if nested_found:
                continue
        snippet = expr.strip().replace("\n", " ")[:70]
        suffix = f"  ({note})" if note else ""
        violations.append(f"{rel}:{line}  ${{{snippet}}}{suffix}")


def main() -> int:
    violations: list[str] = []
    for rel in FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")

        # 1. Direct innerHTML template assignments.
        for m in re.finditer(r"\.innerHTML", src):
            found = template_after_assignment(src, m.start())
            if not found:
                continue
            template, line = found
            check_template(rel, template, line, violations)

        # 2. Template literals passed directly to sink calls (openModal
        #    body/footer — the title argument goes to textContent).
        for arg_text, offset, name in sink_call_html_args(src):
            for template, line in templates_in(arg_text, offset, src):
                check_template(rel, template, line, violations, note=f"via {name}")

        # 3. Template literals stored in variables that reach a sink.
        assigned = template_variables(src)
        sink_names = sink_variable_names(src)
        for name in sorted(assigned.keys() & sink_names):
            for template, line in assigned[name]:
                check_template(
                    rel, template, line, violations, note=f"var {name} flows to innerHTML"
                )

    if violations:
        print("UNESCAPED innerHTML interpolations (wrap in esc(...) or prefix /*safe*/):")
        for v in violations:
            print(f"  {v}")
        return 1
    print("ui-escaping check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
