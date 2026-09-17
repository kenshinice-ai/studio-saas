"""The path that actually reaches production, run rather than read.

`deploy/oracle/pwestudio_arm.sh` shipped v10.20.1 with two guards and no test.
`test_deploy_target_guard.py` closes on "a guard nobody asserts is a guard
somebody deletes while tidying" — and asserts only the Lightsail script, the
one that no longer serves anybody.

These tests execute the script. `ssh` and `curl` are replaced on PATH by shims
that answer the way the box and the public edge do and write down every remote
command, so what is asserted is what the script *did*, in order:

  * a target that is not the serving machine is refused before anything moves;
  * a release that carries migrations is refused unless a backup was declared
    for that exact commit — the script takes none of its own;
  * a deploy the public edge does not report is a failure, and is rolled back.

Nothing here touches the network: `git fetch` is swallowed by a shim as well.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
ARM = REPOSITORY_ROOT / "deploy/oracle/pwestudio_arm.sh"
RELEASE = REPOSITORY_ROOT / "backend/scripts/release.sh"
MIGRATIONS = "backend/db/migrations"

SSH_SHIM = r"""#!/usr/bin/env bash
# Stand-in for the box. Everything after the host alias is the remote command.
while [ $# -gt 0 ]; do
  case "$1" in -o) shift 2 ;; *) break ;; esac
done
shift
command="$*"
printf '%s\n' "$command" >> "$SHIM_LOG"
case "$command" in
  *"127.0.0.1:8899/v1/health"*) printf '%s\n' "$SHIM_BOX_HEALTH" ;;
  *"checkout --quiet --detach"*)
    sed -n 's/.*checkout --quiet --detach \([0-9a-f]\{40\}\).*/\1/p' <<<"$command" | tail -1 > "$SHIM_STATE/commit"
    [[ "$command" == *"rev-parse HEAD"* ]] && cat "$SHIM_STATE/commit"
    ;;
  *"rev-parse HEAD"*) cat "$SHIM_STATE/commit" ;;
  *"sed -n 's/^STUDIOSAAS_VERSION=//p'"*) echo "$SHIM_PINNED_VERSION" ;;
esac
exit 0
"""

CURL_SHIM = r"""#!/usr/bin/env bash
# Stand-in for the public edge.
printf '%s\n' "$SHIM_PUBLIC_HEALTH"
"""

GIT_SHIM = r"""#!/usr/bin/env bash
# The script fetches origin before it trusts origin/main. Not in a test.
[ "${1:-}" = "fetch" ] && exit 0
exec "$REAL_GIT" "$@"
"""


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPOSITORY_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _health(version: str, disk: float) -> str:
    return json.dumps(
        {"appVersion": version, "disk": {"percentUsed": disk}, "themes": {"unreadable": 0}}
    )


@pytest.fixture(scope="module")
def migrating_release() -> tuple[str, str]:
    """(commit before, commit that changes the schema), both on origin/main."""

    try:
        _git("rev-parse", "--verify", "--quiet", "origin/main")
        after = _git("log", "-1", "--format=%H", "origin/main", "--", MIGRATIONS)
        before = _git("rev-parse", "--verify", "--quiet", f"{after}^")
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("needs git history with origin/main (a release bundle has neither)")
    if not after or not before:
        pytest.skip("no commit on origin/main touches the migrations directory")
    return before, after


class Box:
    def __init__(self, tmp_path: Path, *, on_commit: str, pinned: str) -> None:
        self.bin = tmp_path / "bin"
        self.state = tmp_path / "state"
        self.bin.mkdir()
        self.state.mkdir()
        self.log = tmp_path / "remote.log"
        self.log.write_text("", encoding="utf-8")
        (self.state / "commit").write_text(on_commit + "\n", encoding="utf-8")
        self.pinned = pinned
        for name, body in (("ssh", SSH_SHIM), ("curl", CURL_SHIM), ("git", GIT_SHIM)):
            shim = self.bin / name
            shim.write_text(body, encoding="utf-8")
            shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def deploy(
        self, commit: str, *, box: str, public: str, backup_for: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = {
            **os.environ,
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "REAL_GIT": shutil.which("git") or "git",
            "SHIM_LOG": str(self.log),
            "SHIM_STATE": str(self.state),
            "SHIM_BOX_HEALTH": box,
            "SHIM_PUBLIC_HEALTH": public,
            "SHIM_PINNED_VERSION": self.pinned,
        }
        env.pop("PWESTUDIO_ARM_BACKUP_TAKEN_FOR", None)
        if backup_for is not None:
            env["PWESTUDIO_ARM_BACKUP_TAKEN_FOR"] = backup_for
        return subprocess.run(
            ["bash", str(ARM), "deploy", commit],
            cwd=REPOSITORY_ROOT, env=env, capture_output=True, text=True, timeout=120,
        )

    def remote_commands(self) -> str:
        return self.log.read_text(encoding="utf-8")

    def moved_anything(self) -> bool:
        return bool(re.search(r"checkout|docker build|docker compose|sed -i", self.remote_commands()))


def _version_at(commit: str) -> str:
    return _git("show", f"{commit}:VERSION").strip()


def test_a_box_that_is_not_the_serving_machine_is_refused_before_anything_moves(
    tmp_path: Path, migrating_release: tuple[str, str]
) -> None:
    before, _ = migrating_release
    box = Box(tmp_path, on_commit=before, pinned="0.0.0")
    version = _version_at(before)

    result = box.deploy(before, box=_health(version, 18.2), public=_health(version, 6.5))

    assert result.returncode != 0, result.stdout
    assert "different machines" in result.stderr
    assert not box.moved_anything(), box.remote_commands()


def test_a_migrating_release_is_refused_without_a_backup_declared_for_it(
    tmp_path: Path, migrating_release: tuple[str, str]
) -> None:
    before, after = migrating_release
    box = Box(tmp_path, on_commit=before, pinned="0.0.0")
    health = _health(_version_at(before), 6.5)

    undeclared = box.deploy(after, box=health, public=health)
    assert undeclared.returncode != 0, undeclared.stdout
    assert "refusing to migrate production" in undeclared.stderr
    assert MIGRATIONS in undeclared.stdout, "the operator is not shown which files change the schema"

    # A declaration left over from some other release is not a declaration.
    stale = box.deploy(after, box=health, public=health, backup_for=before)
    assert stale.returncode != 0, stale.stdout
    assert "refusing to migrate production" in stale.stderr

    assert not box.moved_anything(), box.remote_commands()


def test_a_declared_backup_lets_the_release_through_and_the_edge_must_confirm_it(
    tmp_path: Path, migrating_release: tuple[str, str]
) -> None:
    before, after = migrating_release
    box = Box(tmp_path, on_commit=before, pinned="0.0.0")
    shipped = _version_at(after)

    result = box.deploy(
        after,
        box=_health(shipped, 6.5),
        public=_health(shipped, 6.5),
        backup_for=after,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Deployed: {after[:12]} as v{shipped}" in result.stdout
    commands = box.remote_commands()
    assert commands.index("checkout --quiet --detach") < commands.index("docker build") \
        < commands.index("up -d"), commands
    assert "--profile local-db" in commands, (
        "compose declines to parse the project without it — the first real deploy failed on exactly this"
    )


def test_a_deploy_the_public_edge_does_not_report_is_rolled_back(
    tmp_path: Path, migrating_release: tuple[str, str]
) -> None:
    """Returning 200 is not evidence. The retained Lightsail box returns 200."""

    before, after = migrating_release
    box = Box(tmp_path, on_commit=before, pinned="9.9.9")
    shipped = _version_at(after)

    result = box.deploy(
        after,
        box=_health(shipped, 6.5),
        public=_health("9.9.9", 6.5),
        backup_for=after,
    )

    assert result.returncode != 0, result.stdout
    assert "WRONG TARGET" in result.stdout
    assert (box.state / "commit").read_text(encoding="utf-8").strip() == before, (
        "the checkout was not restored to what was serving before"
    )
    assert "STUDIOSAAS_VERSION=9.9.9/" in box.remote_commands(), "the pinned version was not restored"


def _code(script: Path) -> str:
    """Shell with comments removed: an assertion that reads a comment passes
    for a line nobody executes."""

    return "\n".join(
        line for line in script.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("#")
    )


def test_the_release_orchestration_deploys_to_the_host_that_serves() -> None:
    code = _code(RELEASE)
    assert 'deploy/oracle/pwestudio_arm.sh deploy "$(git rev-parse HEAD)"' in code
    assert "deploy/oracle/pwestudio_arm.sh health" in code
    assert "pwestudio_remote.sh deploy" not in code, (
        "release.sh deploys to the retained Lightsail instance again — its guard will "
        "refuse, and the next person will be tempted to fix the guard"
    )
