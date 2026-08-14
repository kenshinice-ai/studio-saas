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

# ── RLS 下的夹具约定（v10.3.0） ─────────────────────────────────────
#
# 夹具要造世界：建租户、建学员、塞发票。造世界是属主的活，不是应用的活 ——
# 生产里也是这么分的（迁移与后台脚本用属主，Web 应用用受限角色）。
#
# 所以夹具用 STUDIOSAAS_OWNER_DATABASE_URL（没设就退回主连接串），
# 而被测的应用代码继续用 STUDIOSAAS_DATABASE_URL。两者指向同一个库、
# 不同的角色，这正是要验证的那种配置。
import contextlib
import os as _os


@contextlib.contextmanager
def owner_connection():
    """A connection that may create the world. Fixtures only, never app code."""

    from studiosaas.db import connect

    app_url = _os.environ.get("STUDIOSAAS_DATABASE_URL")
    owner_url = _os.environ.get("STUDIOSAAS_OWNER_DATABASE_URL")
    if owner_url:
        _os.environ["STUDIOSAAS_DATABASE_URL"] = owner_url
    try:
        with connect() as conn:
            yield conn
    finally:
        if owner_url and app_url is not None:
            _os.environ["STUDIOSAAS_DATABASE_URL"] = app_url
