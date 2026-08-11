#!/usr/bin/env python3
"""Fail when banned vocabulary reappears in a user-facing surface.

Terminology drifts one string at a time: someone writes 「排班」 next to a
button that already says 「排课」, or hard-codes 画室 into a template five
tenants share. `docs/Glossary.md` records the decision; this enforces it.

Usage:
    python backend/scripts/check_terminology.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SURFACES = [
    "tenant-template/index.html",
    "tenant-template/register.html",
    "tenant-template/showcase.html",
    "tenant-template/timetable.html",
    "legacy-root/src/cms-app.jsx",
    "backend/frontend/studio-admin.html",
    "super-admin.html",
]

# (pattern, human explanation). Patterns are matched against a comment-stripped
# copy of each file, so a rule may be discussed in a comment without tripping.
BANNED = [
    (r"排班", "Use 排课 (roster). See docs/Glossary.md."),
    (r"客户总数", "Students are 学员, not 客户. See docs/Glossary.md."),
    (r"商业洞察", "Use 经营统计 (Business Stats). See docs/Glossary.md."),
    (r"classes remaining", "One class may draw several credits — use 'credits remaining'."),
]

# Industry-specific nouns must not be hard-coded in the shared public template;
# %VENUE% / %WORK% resolve them per tenant.
INDUSTRY_BANNED = [
    (r"画室", "Hard-coded art-school venue noun — use %VENUE%."),
    (r"琴行", "Hard-coded music venue noun — use %VENUE%."),
]
INDUSTRY_SURFACES = ["tenant-template/index.html", "tenant-template/register.html", "tenant-template/showcase.html", "tenant-template/timetable.html"]


def strip_comments(text: str, suffix: str) -> str:
    """Remove comments so guidance about a banned word is not itself a hit."""

    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    if suffix in {".js", ".jsx", ".html"}:
        text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
        text = re.sub(r"^\s*//[^\n]*$", "", text, flags=re.M)
    return text


def check(path: Path, rules: list[tuple[str, str]]) -> list[str]:
    raw = path.read_text(encoding="utf-8")
    cleaned = strip_comments(raw, path.suffix)
    failures = []
    for pattern, reason in rules:
        for match in re.finditer(pattern, cleaned):
            line = cleaned.count("\n", 0, match.start()) + 1
            failures.append(
                f"{path.relative_to(PROJECT_ROOT)}:~{line}: '{match.group(0)}' — {reason}"
            )
    return failures


def main() -> int:
    failures: list[str] = []
    for name in SURFACES:
        path = PROJECT_ROOT / name
        if not path.is_file():
            continue
        rules = list(BANNED)
        if name in INDUSTRY_SURFACES:
            rules += INDUSTRY_BANNED
        failures.extend(check(path, rules))

    if failures:
        print("terminology check: FAILED", file=sys.stderr)
        for failure in failures:
            print("  " + failure, file=sys.stderr)
        print("\nSee docs/Glossary.md for the agreed word in each language.", file=sys.stderr)
        return 1

    print("terminology check: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
