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
