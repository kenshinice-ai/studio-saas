"""The CMS source — however many files it ends up being spread across.

Every contract test in this directory used to read one hardcoded path,
``legacy-root/src/cms-app.jsx``. That was correct while the CMS was one 6,800
line file, and it becomes silently wrong the moment any of it moves into a
sibling module: the assertions keep passing, against a file that no longer
contains the code they were written to police.

That failure mode has already cost this project twice — an archive manifest
that dropped three tenant-scoped tables, and an Edition importer that could not
run — both times because a guard compared one hardcoded list against another
instead of asking the filesystem. This module is the same fix applied before
the damage rather than after: ask the directory, not a constant.

Concatenating the files is safe for what these tests do. They grep for a
substring that must be present, or assert one is absent; both get *stricter*
as files are added, never looser.
"""

from __future__ import annotations

from pathlib import Path

#: Everything esbuild bundles into ``cms-app.js`` lives under here.
CMS_SRC_DIR = Path(__file__).resolve().parents[2] / "legacy-root" / "src"


def cms_source_files() -> list[Path]:
    """Every JSX file that compiles into the CMS bundle, in a stable order."""

    return sorted(CMS_SRC_DIR.rglob("*.jsx"))


def cms_source_text() -> str:
    """The whole CMS source as one string, for contract assertions.

    Files are separated by a newline so a construct at the end of one file and
    another at the start of the next cannot accidentally form a third that
    matches — or fails to match — a pattern.
    """

    return "\n".join(path.read_text(encoding="utf-8") for path in cms_source_files())
