"""A deploy that reaches nobody must fail, not succeed.

2026-09-17 production moved from AWS Lightsail to an Oracle ARM box behind
Cloudflare and Caddy — and the old machine kept running. `~/.ssh/config` still
resolves `pwestudio`, the alias `pwestudio_remote.sh` defaults to, to the old
one. Nothing in the release path noticed:

  1. the bundle deploys to the old box and comes up healthy;
  2. the public-edge check curls https://pwestudio.online and gets 200 —
     from the OTHER machine;
  3. the script exits 0 and the release reports success.

Production would be untouched and every automated check green. The three-way
commit guard cannot see it either: it compares commits, not machines.

Two boxes running the same release are identical in everything the app reports
about itself, so the guard has two halves that fail for different reasons:

  * before the upload, a machine-state comparison (disk) — cheap, heuristic,
    and it fires before anything has moved;
  * after the deploy, an exact assertion that the public edge reports the
    version just built — that version exists nowhere else, so a mismatch is
    unambiguous and no future migration can slip past it.

This file exists because a guard nobody asserts is a guard somebody deletes
while tidying.
"""

from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
REMOTE = REPOSITORY_ROOT / "deploy/aws/pwestudio_remote.sh"


def _script() -> str:
    return REMOTE.read_text(encoding="utf-8")


def test_the_pre_deploy_check_runs_before_anything_is_uploaded() -> None:
    script = _script()
    assert "assert_box_serves_public_url()" in script, "the guard function is gone"

    deploy = script[script.index("\n  deploy)"):]
    call = deploy.index("assert_box_serves_public_url")
    upload = deploy.index("scp -q")
    assert call < upload, (
        "the machine check runs after the upload; it exists so the failure "
        "arrives before anything has moved"
    )


def test_the_public_edge_must_report_the_version_just_deployed() -> None:
    """The exact half. Returning 200 is not evidence: any healthy machine
    serving that domain returns 200, including one nobody deployed to."""

    script = _script()
    edge = script[script.index("verifying from the public edge"):]
    edge = edge[: edge.index("THEME DRIFT")]

    assert "appVersion" in edge, "the edge check no longer reads the served version"
    assert re.search(r'\[\s*"\$edge_version"\s*!=\s*"\$version"\s*\]', edge), (
        "the edge check no longer compares the served version with the one "
        "just built"
    )
    assert "deployed=false" in edge, (
        "a version mismatch no longer fails the deploy"
    )


def test_the_check_is_runnable_on_its_own() -> None:
    """An operator has to be able to ask "am I pointed at the right box?"
    without deploying to find out."""

    script = _script()
    assert "\n  verify-target)" in script
    assert "verify-target" in script[: script.index("set -euo pipefail")], (
        "verify-target is not in the usage header, so nobody will find it"
    )


def test_the_guard_compares_machines_not_versions() -> None:
    """The two boxes ran the same release on the day of the migration, so a
    version comparison would have passed. Disk is the discriminator."""

    script = _script()
    guard = script[script.index("assert_box_serves_public_url()"):]
    guard = guard[: guard.index("\nusage()")]
    assert "percentUsed" in guard, (
        "the pre-deploy check no longer compares machine state; two boxes on "
        "the same release are indistinguishable by anything else"
    )
    assert "127.0.0.1:8899" in guard, "it no longer asks the box about itself"
