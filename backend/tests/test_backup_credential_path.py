"""The backup credential never travels in argv (OPS-04).

`docker compose exec -e VAR=<url>` puts whatever it is given on the command
line, and /proc/<pid>/cmdline is world-readable on the host: any local account
could read the database password out of `ps` for as long as a backup ran. The
URL is still assembled in the controller, but it is handed over through the
environment (`-e VAR` with no `=value`, which tells compose to take the value
from its own environment).

The container-side contract is deliberately UNCHANGED — backup_postgres.py
still reads STUDIOSAAS_DATABASE_URL and nothing else. That is not laziness,
it is the fix to the first attempt at this change, which introduced a new
STUDIOSAAS_DB_PASSWORD contract and stopped the v10.11.1 deploy dead at its
own pre-deploy backup:

    pg_dump: error: query failed: ERROR:  query would be affected by
    row-level security policy for table "credit_financial_links"

Why: pwestudio_remote.sh stages the CANDIDATE controller and takes the
pre-deploy backup with it while the PREVIOUS release's image is still running.
So a controller/script contract change always meets last release's script, and
breaks the one backup that protects the deploy. (The guard held — the deploy
refused to switch and production stayed on the old version — but the backup a
deploy depends on must not be the thing that discovers a version skew.)

Verified live on 2026-08-20 before the redeploy: the backup produced a real
dump, and a sentinel probe found the value in zero process command lines.
"""

import re
import subprocess
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CTL = REPOSITORY_ROOT / "deploy/aws/lightsail_ctl.sh"
BACKUP_SCRIPT = REPOSITORY_ROOT / "backend/scripts/backup_postgres.py"

# A password holding every character that breaks a naive URL splice.
HOSTILE = "p@ss:w/rd?#%&=x"


def _directives(text: str) -> str:
    """Only the lines that run. Comments name the old form on purpose."""

    return "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    )


def test_the_credential_is_forwarded_by_name_never_by_value():
    script = _directives(CTL.read_text(encoding="utf-8"))
    # `-e VAR` with no `=`: compose reads the value from its own environment.
    assert script.count("-e STUDIOSAAS_DATABASE_URL \\") == 2, (
        "both the backup and the restore rehearsal must forward it this way"
    )
    assert '-e STUDIOSAAS_DATABASE_URL="' not in script, "that is argv again"
    assert "-e STUDIOSAAS_DATABASE_URL=" not in script, "that is argv again"
    # And the value is put in the environment for exactly one command.
    assert script.count('STUDIOSAAS_DATABASE_URL="$(owner_db_url)" \\') == 2


def test_the_container_contract_is_unchanged():
    """The pre-deploy backup pairs a new controller with the running image.

    If this file starts requiring an environment variable the previous
    release's copy of the script does not know about, the next deploy's
    pre-deploy backup fails. Changing this contract is possible, but it takes
    two releases: teach the script first, switch the controller after.
    """

    source = BACKUP_SCRIPT.read_text(encoding="utf-8")
    assert "STUDIOSAAS_DATABASE_URL" in source
    assert "STUDIOSAAS_DB_PASSWORD" not in source, (
        "a new controller-to-script contract breaks the pre-deploy backup of "
        "the release that introduces it — see this module's docstring"
    )


def test_the_shell_encoder_survives_a_hostile_password():
    """The encoding is the controller's job, so test the controller's encoder.

    Extracted and run rather than eyeballed: a password containing @ : / ? # %
    silently corrupted the URL under the old sed splice, and 'it looks right'
    is what let that ship.
    """

    script = CTL.read_text(encoding="utf-8")
    match = re.search(r"^urlencode\(\) \{.*?^\}", script, re.S | re.M)
    assert match, "urlencode() is gone — the controller no longer encodes the password"
    program = match.group(0) + f'\nurlencode "{HOSTILE}"\n'
    result = subprocess.run(["bash", "-c", program], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout == "p%40ss%3Aw%2Frd%3F%23%25%26%3Dx", result.stdout


def test_the_owner_url_is_assembled_from_the_encoded_password():
    script = CTL.read_text(encoding="utf-8")
    assert "owner_db_url()" in script
    assert "postgresql://studiosaas:%s@db:5432/studiosaas" in script
    assert '"$(urlencode "$pw")"' in script
    assert "sed 's#^#postgresql://studiosaas:#" not in script  # the raw splice must not come back
