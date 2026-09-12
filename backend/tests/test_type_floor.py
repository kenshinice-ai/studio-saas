"""Nothing in the back office renders below 11px.

The shape language sheet sets 11px as the floor and the back office had 41
declarations underneath it — 31 in the CMS as Tailwind arbitrary values
(`text-[10px]`), 10 in the two consoles as literal `font-size`. Measured in
production on 2026-09-12: 16 rendered elements below the floor on 课程安排
alone, 7 on 账单发票, 6 on 工作台.

10px is not a style choice at that size, it is the point where a Chinese
character stops resolving its strokes. The consoles and the CMS are read all
day by people who are also doing something else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FLOOR_PX = 11

SOURCES = [
    *sorted((REPOSITORY_ROOT / "legacy-root/src").rglob("*.jsx")),
    REPOSITORY_ROOT / "backend/frontend/studio-admin.html",
    REPOSITORY_ROOT / "super-admin.html",
    REPOSITORY_ROOT / "legacy-root/index.html",
]

# Tailwind arbitrary sizes, and plain CSS declarations.
ARBITRARY = re.compile(r"text-\[(\d+(?:\.\d+)?)px\]")
DECLARED = re.compile(r"font-size:\s*(\d+(?:\.\d+)?)px")


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_no_back_office_text_is_declared_below_the_floor(source: Path) -> None:
    text = source.read_text(encoding="utf-8")
    body = re.sub(r"/\*.*?\*/", "", re.sub(r"<!--.*?-->", "", text, flags=re.S), flags=re.S)

    offenders = []
    for line_number, line in enumerate(body.splitlines(), 1):
        for pattern in (ARBITRARY, DECLARED):
            for match in pattern.finditer(line):
                if float(match.group(1)) < FLOOR_PX:
                    offenders.append(f"{source.name}:{line_number} {match.group(0)}")
    assert not offenders, (
        f"below the {FLOOR_PX}px floor:\n  " + "\n  ".join(offenders[:12])
    )


def test_the_floor_is_actually_being_looked_for() -> None:
    """A regex that stops matching turns every file above green."""

    corpus = "\n".join(s.read_text(encoding="utf-8") for s in SOURCES)
    assert len(ARBITRARY.findall(corpus)) >= 20, (
        "no Tailwind arbitrary text sizes found at all — the pattern is wrong, "
        "not the code"
    )
    assert len(DECLARED.findall(corpus)) >= 20, (
        "no font-size declarations found at all — the pattern is wrong"
    )
