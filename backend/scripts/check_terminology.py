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

_FIXED_SURFACES = [
    "tenant-template/index.html",
    "tenant-template/register.html",
    "tenant-template/showcase.html",
    "tenant-template/timetable.html",
    "backend/frontend/studio-admin.html",
    "backend/frontend/assets/studio-admin.js",
    "backend/frontend/assets/super-admin.js",
    "super-admin.html",
]

# The two translation dictionaries carry the other half of every screen: the
# English the CMS shows and the Chinese the consoles show. Neither appears in
# any file above, so a banned word could live here for months while this check
# passed (it did, until 2026-10-09). They are checked under the same rules.
_DICTIONARY_SURFACES = [
    "backend/frontend/assets/cms-i18n.js",
    "backend/frontend/assets/admin-i18n.js",
]


def _cms_surfaces() -> list[str]:
    """Every JSX file that compiles into the CMS bundle.

    Derived rather than listed. This entry was `legacy-root/src/cms-app.jsx`
    while the CMS was a single file, and it would have kept passing — checking
    a file that no longer held the code — the moment any panel moved into a
    sibling module. The same shape of bug has already shipped twice in this
    repository from a hardcoded inventory; ask the directory instead.
    """

    src = PROJECT_ROOT / "legacy-root" / "src"
    return [
        str(path.relative_to(PROJECT_ROOT))
        for path in sorted(src.rglob("*.jsx"))
    ]


SURFACES = _FIXED_SURFACES + _DICTIONARY_SURFACES + _cms_surfaces()

# (pattern, human explanation). Patterns are matched against a comment-stripped
# copy of each file, so a rule may be discussed in a comment without tripping.
BANNED = [
    (r"排班", "Use 排课 (roster). See docs/Glossary.md."),
    (r"客户总数", "Students are 学员, not 客户. See docs/Glossary.md."),
    (r"商业洞察|经营洞察",
     "No 洞察: the CMS figures screen is 经营统计 (Business Stats); the Studio Admin "
     "group that holds website analytics is 数据分析 (Analytics). See docs/Glossary.md."),
    (r"classes remaining", "One class may draw several credits — use 'credits remaining'."),
    # Added 2026-10-09 when the dictionaries were brought onto the Glossary.
    # Each names a phrase that was on screen, not the bare word: 套餐 is still
    # right for the SaaS plan, and "portal" for the tenant portal's own name.
    (r"套餐管理|添加套餐|套餐快选|Quick pack|[Aa]dd package",
     "A pack of prepaid credits is 课包 / credit pack; 套餐 is the SaaS plan. See docs/Glossary.md."),
    (r"退课节数|均价/课(?!时)", "节 and 课 are not credit units — use 课时 (credit). See docs/Glossary.md."),
    (r"门户网站|Portal site|Open Portal|on the portal",
     "The public site is 官网 / website; 'Portal' names only the tenant portal surface. See docs/Glossary.md."),
    # Added 2026-10-09 with Lee's ruling on the industry nouns. 画室 and 画艺 are
    # wrong for a piano, dance or games tenant on every surface, staff ones
    # included: a placeholder that says 「画室 · 空间」 tells a piano teacher what
    # to type. 作品 is different — see INDUSTRY_BANNED below.
    (r"画室|画艺", "Art-school noun in shared code — use %VENUE%, or wording that fits every industry."),
]

# Industry-specific nouns must not be hard-coded where families read them;
# %VENUE% / %WORK% resolve them per tenant.
#
# 作品 is banned here and only here (Lee, 2026-10-09). Staff screens — the CMS,
# Studio Admin, Super Admin and their two dictionaries — keep 作品 / Portfolio /
# Works: there it names a feature and a data concept, and one fixed word serves
# staff better than a noun that changes with the tenant's industry. A piano
# family reading 「工作室作品」 on the public site is the case the token exists for.
#
# The one legal spelling is the bare quoted literal — `'作品'` — which is the
# default the resolver falls back to when /brand has not answered.
INDUSTRY_BANNED = [
    (r"琴行", "Hard-coded music venue noun — use %VENUE%."),
    (r"""(?<!['"])作品""", "Hard-coded work noun on a public page — use %WORK% / %WORKS%."),
]


def _industry_surfaces() -> list[str]:
    """Every public template, shell partials included, plus the shared script
    that writes their navigation labels.

    Derived for the same reason `_cms_surfaces` is. This was a list of four
    pages while the three `_shell-*-links.html` partials — which carry the
    navigation label every one of those pages shows — sat outside it.
    """

    templates = PROJECT_ROOT / "tenant-template"
    return [
        str(path.relative_to(PROJECT_ROOT)) for path in sorted(templates.glob("*.html"))
    ] + ["backend/frontend/assets/public-surface.js"]


INDUSTRY_SURFACES = _industry_surfaces()


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
    for name in dict.fromkeys(SURFACES + INDUSTRY_SURFACES):
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
