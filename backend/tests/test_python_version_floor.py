"""The source must parse on the interpreter production actually runs.

v8.2.28 was written on Python 3.14 and deployed to a `python:3.11-slim`
container. One line used a backslash inside an f-string expression — legal
from 3.12, a `SyntaxError` before it (PEP 701). It compiled on the development
machine, 652 tests passed, the bundle built, and the container could not
import `server`. Deep health failed and the deploy rolled itself back, which
is the system working; but nothing before that point could have caught it,
because every check ran on the wrong interpreter.

Two checks, because one is not enough:

`ast.parse(feature_version=...)` rejects grammar newer than the version given
— match statements, `except*`, PEP 695 generics, and so on. It does **not**
catch the f-string case: `feature_version` constrains the parser, not the
tokenizer, and a 3.12+ tokenizer reads PEP 701 f-strings before the parser is
consulted. That was measured, not assumed, so the second check exists.

The f-string check walks the AST for expressions interpolated into an
f-string and looks at the source text of each. Narrow on purpose: it is the
one construct where the interpreter running the tests silently accepts
something the interpreter running production rejects.

Neither is a substitute for building on the target image. They are what can
be asserted without one.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = REPOSITORY_ROOT / "deploy/aws/Dockerfile"

# Directories that never reach the image, or are not ours to hold to this line.
EXCLUDED = ("/vendor/", "/node_modules/", "/.venv/", "/venv/", "/dist/",
            "/__pycache__/", "/checkpoints/", "/backups/")

# The release that made backslashes legal inside f-string expressions.
PEP_701 = (3, 12)


def production_python_version() -> tuple[int, int]:
    """(major, minor) from the base image the production Dockerfile pins."""

    match = re.search(
        r"^FROM python:(\d+)\.(\d+)", DOCKERFILE.read_text(encoding="utf-8"), re.M)
    assert match, "the production Dockerfile no longer pins a python:<major>.<minor> base image"
    return int(match.group(1)), int(match.group(2))


def python_sources() -> list[Path]:
    return sorted(
        path for path in REPOSITORY_ROOT.rglob("*.py")
        if not any(part in f"/{path.relative_to(REPOSITORY_ROOT)}/" for part in EXCLUDED)
    )


SOURCES = python_sources()


def test_the_floor_is_below_the_interpreter_running_the_tests() -> None:
    """Otherwise these checks prove nothing — they would be no-ops."""

    import sys

    floor = production_python_version()
    assert floor <= sys.version_info[:2], (
        f"tests run on {sys.version_info.major}.{sys.version_info.minor}, "
        f"older than the production floor {floor[0]}.{floor[1]}"
    )


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_every_module_parses_on_the_production_interpreter(source: Path) -> None:
    floor = production_python_version()
    try:
        ast.parse(source.read_text(encoding="utf-8"), filename=str(source), feature_version=floor)
    except SyntaxError as error:
        pytest.fail(
            f"{source.relative_to(REPOSITORY_ROOT)}:{error.lineno} does not parse on "
            f"Python {floor[0]}.{floor[1]}, which the production image runs: {error.msg}"
        )


def _backslashes_in_fstring_expressions(text: str) -> list[tuple[int, str]]:
    """(line, source) for every interpolated expression containing a backslash."""

    found = []
    for node in ast.walk(ast.parse(text)):
        if not isinstance(node, ast.JoinedStr):
            continue
        for part in node.values:
            if not isinstance(part, ast.FormattedValue):
                continue
            segment = ast.get_source_segment(text, part.value) or ""
            if "\\" in segment:
                found.append((part.value.lineno, segment))
    return found


@pytest.mark.parametrize("source", SOURCES, ids=lambda p: p.name)
def test_no_backslash_inside_an_fstring_expression(source: Path) -> None:
    if production_python_version() >= PEP_701:
        pytest.skip("the production interpreter accepts PEP 701 f-strings")
    text = source.read_text(encoding="utf-8")
    offenders = _backslashes_in_fstring_expressions(text)
    assert not offenders, "\n".join(
        f"{source.relative_to(REPOSITORY_ROOT)}:{line} — {segment}"
        for line, segment in offenders
    ) + "\n\nA backslash inside an f-string expression is a SyntaxError before "
    "Python 3.12. Bind the value to a name on the line above instead."


def test_the_fstring_check_catches_the_line_that_caused_this() -> None:
    """The check that has to work is the one nobody exercises until it fires.

    This is the exact expression from `public_site._jsonld_script` as it was
    written and deployed, kept here so the detector cannot quietly stop
    detecting it.
    """

    offending = 'def f(body):\n    return f"<s>{body.replace(chr(60), \'<\\\\/\')}</s>"\n'
    assert _backslashes_in_fstring_expressions(offending)
    # And the same line with the escape lifted out is clean.
    fixed = 'def f(body):\n    body = body.replace(chr(60), "<\\\\/")\n    return f"<s>{body}</s>"\n'
    assert not _backslashes_in_fstring_expressions(fixed)
