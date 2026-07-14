#!/usr/bin/env python3
"""Static check: template-literal interpolations inside innerHTML assignments
must go through esc() (or be explicitly marked safe).

Heuristic, not a parser: it finds `.innerHTML =` / `.innerHTML +=` assignments
whose value is a template literal, extracts every `${...}` interpolation, and
flags expressions that do not match the safe-list. Suppress a false positive
by making the expression start with `/*safe*/`.

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
    "tenant-template/studio-admin.html",
]

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


def template_after_assignment(src: str, idx: int) -> tuple[str, int] | None:
    """Return (template_body, line_no) if the assignment at idx uses a backtick."""

    m = re.compile(r"\.innerHTML\s*\+?=\s*").match(src, idx)
    if not m:
        return None
    k = m.end()
    if k >= len(src) or src[k] != "`":
        return None
    end = k + 1
    while end < len(src):
        if src[end] == "`" and src[end - 1] != "\\":
            break
        end += 1
    line = src.count("\n", 0, idx) + 1
    return src[k + 1 : end], line


def main() -> int:
    violations = []
    for rel in FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\.innerHTML", src):
            found = template_after_assignment(src, m.start())
            if not found:
                continue
            template, line = found
            for expr in interpolations(template):
                if not SAFE_EXPR.match(expr):
                    snippet = expr.strip().replace("\n", " ")[:70]
                    violations.append(f"{rel}:{line}  ${{{snippet}}}")

    if violations:
        print("UNESCAPED innerHTML interpolations (wrap in esc(...) or prefix /*safe*/):")
        for v in violations:
            print(f"  {v}")
        return 1
    print("ui-escaping check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
