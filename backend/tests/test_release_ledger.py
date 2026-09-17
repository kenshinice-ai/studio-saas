"""One version, named everywhere it is named — and a handoff that keeps up.

A release label lives in `VERSION`, in `server.py`, in seven role guides, in
the README's three rows, in the customer release notes and in the Edition
delivery documents. Updating it is a checklist, and the entry that gets
skipped is the one nothing checks.

The evidence that this was already happening: merging a branch based on v9.8.8
into the v9.9.1 line produced eight conflicting files, and every conflict was
a version label. Not one of them was a content difference.

The handoff has the same problem for a different reason. It is the ledger the
next session reads first, so a handoff whose top section names an older
release is worse than no handoff — it is a confident wrong answer.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
GUIDES = sorted((PROJECT_ROOT / "docs/guides").glob("*.md"))


def test_the_running_code_names_the_released_version() -> None:
    """`VERSION` is the source of truth; APP_VERSION is what the API reports."""

    server = (PROJECT_ROOT / "backend/server.py").read_text(encoding="utf-8")
    declared = re.search(r"^APP_VERSION\s*=\s*'([^']+)'", server, re.M)
    assert declared, "server.py declares no APP_VERSION"
    assert declared.group(1) == VERSION, (
        f"server.py reports {declared.group(1)} while VERSION says {VERSION}. "
        "Deep health would then disagree with the tarball name."
    )
    release_date = re.search(r"^RELEASE_DATE\s*=\s*'(\d{4}-\d{2}-\d{2})'", server, re.M)
    assert release_date, "server.py declares no RELEASE_DATE"


@pytest.mark.parametrize("guide", GUIDES, ids=lambda path: path.name)
def test_every_role_guide_declares_the_version_it_describes(guide: Path) -> None:
    """A guide that names an older release is describing a product that moved."""

    head = guide.read_text(encoding="utf-8")[:400]
    assert f"v{VERSION}" in head, (
        f"{guide.name} does not name v{VERSION} in its header."
    )


def test_the_handoff_opens_on_the_current_release() -> None:
    """The ledger the next session reads first has to be the current one.

    Not "mentions somewhere" — the FIRST heading. A handoff whose newest entry
    is an older release reads as authoritative and is wrong.
    """

    handoff = (PROJECT_ROOT / "docs/HANDOFF_LATEST.md").read_text(encoding="utf-8")
    first_heading = next(
        (line for line in handoff.splitlines() if line.startswith("# ")), ""
    )
    assert f"v{VERSION}" in first_heading, (
        f"docs/HANDOFF_LATEST.md opens with {first_heading!r}, which does not name "
        f"v{VERSION}. Add this release's section above the previous one."
    )


def test_the_customer_release_notes_mention_this_release() -> None:
    """The page a studio owner reads must not fall behind what they are running."""

    notes = (PROJECT_ROOT / "customer-resources/Release_Notes.html").read_text(encoding="utf-8")
    assert VERSION in notes, (
        f"Release_Notes.html does not mention v{VERSION}."
    )


def test_the_edition_delivery_documents_name_one_version() -> None:
    """A delivery engineer follows these literally, including the tarball name.

    Two of them naming different versions is how a customer receives a package
    whose checksum does not match the command they were told to run.
    """

    edition = sorted((PROJECT_ROOT / "standalone-edition").glob("*.md"))
    labelled = {}
    for document in edition:
        found = set(re.findall(r"PWE-Studio-Edition-(\d+\.\d+\.\d+)", document.read_text(encoding="utf-8")))
        if found:
            labelled[document.name] = found
    for name, versions in labelled.items():
        assert versions == {VERSION}, (
            f"{name} names Edition package version(s) {sorted(versions)} while VERSION "
            f"says {VERSION}."
        )


def test_no_test_fixture_workspace_is_tracked() -> None:
    """`test_tenant_isolation.py` writes workspaces; they are not tenants.

    One of them was staged into a release commit and only caught by reading
    `git status` closely. The bundle is `git archive HEAD`, so what ships is
    what is TRACKED — which is also why this asks git rather than the
    filesystem. The directories reappear after every isolation run and that is
    fine; being committed is not.
    """

    import subprocess

    tracked = subprocess.run(
        ["git", "ls-files", "tenants/isolation-*", "tenants/test-*"],
        cwd=PROJECT_ROOT, text=True, capture_output=True,
    ).stdout.split()
    assert not tracked, (
        f"test fixture workspaces are tracked and would ship: {tracked[:5]}"
    )


def test_every_runtime_dependency_is_pinned_in_the_production_lock() -> None:
    """backend/requirements.txt is the dev contract; deploy/aws/requirements.lock
    is what production images actually install. The v10.9.0 first deploy failed
    exactly here: cryptography added to requirements.txt but not the lock, so
    the container built fine and crashed on import. Names must stay in sync."""

    import re

    def names(path: Path) -> set[str]:
        found = set()
        for line in (PROJECT_ROOT / path).read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            found.add(re.split(r"[\[<>=!~]", line)[0].strip().lower().replace("-", "_"))
        return found

    dev = names("backend/requirements.txt")
    lock = names("deploy/aws/requirements.lock")
    missing = dev - lock
    assert not missing, (
        f"deploy/aws/requirements.lock is missing pins for {sorted(missing)} — "
        "production installs the lock, so this dependency would not exist in the image."
    )


# ── the README's three rows ──────────────────────────────────────────────────
#
# This module's own docstring has always claimed to cover "the README's three
# rows". It did not, and the rows are where the drift actually happened:
# `release.sh bump` ran `replace_all README.md "$OLD" "$NEW"` over the whole
# file, which advanced whichever rows carried the outgoing version and froze
# the rest. By v10.20.0 the table read
#
#     Source     | v10.20.0 candidate on branch release/10.20.0-pwe-house, not pushed
#     Package    | not built
#     Production | still v10.17.0
#
# with a STOP GATE sentence about nginx belonging to v10.18.0 — every row
# false, on a released version, and looking freshly updated because a number in
# it had just been rewritten. Nothing checked any of it.

def _readme_status_table() -> str:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    start = readme.index("| Layer | Verified state | Evidence |")
    return readme[start:readme.index("\n\n", start)]


def test_the_readme_source_row_names_this_release() -> None:
    table = _readme_status_table()
    source_row = next(line for line in table.splitlines() if line.startswith("| Source |"))
    assert VERSION in source_row, (
        f"README's Source row does not name {VERSION}:\n  {source_row.strip()}"
    )


def test_the_readme_and_the_handoff_agree_about_production() -> None:
    """Two ledgers that disagree mean one of them is stale, and the reader has
    no way to tell which. A static test cannot verify what production actually
    serves — but it can refuse to let the two documents contradict each other.
    """

    import re

    table = _readme_status_table()
    readme_row = next(line for line in table.splitlines() if line.startswith("| Production |"))
    readme_versions = set(re.findall(r"\bv?(\d+\.\d+\.\d+)\b", readme_row))

    handoff = (PROJECT_ROOT / "docs/HANDOFF_LATEST.md").read_text(encoding="utf-8")
    current = handoff[handoff.index("## 当前四层身份"):]
    current = current[: current.index("## 上一版四层身份")]
    production_row = next(
        line for line in current.splitlines() if line.startswith("| Production |")
    )
    handoff_versions = set(re.findall(r"\bv?(\d+\.\d+\.\d+)\b", production_row))

    assert readme_versions, f"README's Production row names no version:\n  {readme_row.strip()}"
    assert handoff_versions, f"the handoff's Production row names no version"
    assert readme_versions & handoff_versions, (
        "README and HANDOFF_LATEST disagree about what production is serving.\n"
        f"  README : {sorted(readme_versions)}\n"
        f"  handoff: {sorted(handoff_versions)}\n"
        "One of them was not written at step 9."
    )


def test_bump_does_not_rewrite_the_readme_by_substitution() -> None:
    """The rows are claims about reality; sed cannot check one, and a blind
    substitution is what made them look current while being wrong."""

    import re

    # Strip comments first. The comment that replaced this call quotes the old
    # line verbatim to explain it, and an assertion that reads comments is the
    # same defect in the other direction — here it fails on prose, elsewhere it
    # has passed on prose.
    release = (PROJECT_ROOT / "backend/scripts/release.sh").read_text(encoding="utf-8")
    release = re.sub(r"^[^\S\n]*#.*$", "", release, flags=re.M)
    assert 'replace_all README.md' not in release, (
        "bump rewrites README.md by substitution again — that is how "
        "'Source: v10.20.0 candidate' ended up above 'Production: still v10.17.0'"
    )
