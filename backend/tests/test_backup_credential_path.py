"""The backup credential never travels in argv (OPS-04).

`docker compose exec -e VAR=<url>` puts whatever it is given on the command
line, and /proc/<pid>/cmdline is world-readable on the host: any local account
could read the database password out of `ps` for as long as a backup ran.
The password now moves through the environment, and the URL is assembled
inside backup_postgres.py where percent-encoding is a library call rather than
a hand-written shell loop.

These tests pin both halves — the shell no longer builds a URL, and the Python
assembles one that survives a hostile password.
"""

import importlib.util
import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CTL = REPOSITORY_ROOT / "deploy/aws/lightsail_ctl.sh"

# A password holding every character that breaks a naive URL splice.
HOSTILE = "p@ss:w/rd?#%&=x"


def _module():
    spec = importlib.util.spec_from_file_location(
        "backup_postgres", REPOSITORY_ROOT / "backend/scripts/backup_postgres.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("STUDIOSAAS_DATABASE_URL", "DATABASE_URL", "STUDIOSAAS_DB_PASSWORD",
                 "STUDIOSAAS_DB_USER", "STUDIOSAAS_DB_HOST", "STUDIOSAAS_DB_PORT",
                 "STUDIOSAAS_DB_NAME"):
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_a_hostile_password_survives_url_assembly(clean_env):
    clean_env.setenv("STUDIOSAAS_DB_PASSWORD", HOSTILE)
    parsed = urlparse(_module()._database_url())
    assert unquote(parsed.password) == HOSTILE, "the password did not survive encoding"
    assert parsed.username == "studiosaas"
    assert parsed.hostname == "db" and parsed.port == 5432
    assert parsed.path == "/studiosaas"


def test_an_explicit_url_still_wins(clean_env):
    """Local and CI callers pass a URL directly; that path is unchanged."""

    clean_env.setenv("STUDIOSAAS_DATABASE_URL", "postgresql://someone@localhost:5432/db")
    assert _module()._database_url() == "postgresql://someone@localhost:5432/db"


def test_no_credential_at_all_fails_loudly(clean_env):
    """Never a silent fallback to a default connection — this writes backups."""

    with pytest.raises(SystemExit) as raised:
        _module()._database_url()
    assert "STUDIOSAAS_DATABASE_URL" in str(raised.value)
    assert "STUDIOSAAS_DB_PASSWORD" in str(raised.value)


def test_an_empty_password_is_not_accepted_as_a_password(clean_env):
    clean_env.setenv("STUDIOSAAS_DB_PASSWORD", "")
    with pytest.raises(SystemExit):
        _module()._database_url()


def test_the_controller_hands_over_a_password_not_a_url():
    """The shell must not splice a URL, and must not pass a value in argv."""

    script = CTL.read_text(encoding="utf-8")
    assert "owner_db_url" not in script, (
        "owner_db_url is back — a URL in argv is the exposure this closed"
    )
    assert "owner_db_password()" in script
    # `-e VAR` with no `=value`: compose forwards the value from its own
    # environment, so it never becomes a command-line argument.
    assert script.count("-e STUDIOSAAS_DB_PASSWORD \\") == 2, (
        "both the backup and the restore rehearsal must forward it this way"
    )
    assert "-e STUDIOSAAS_DB_PASSWORD=" not in script, "that would be argv again"
    assert "-e STUDIOSAAS_DATABASE_URL=" not in script, "that would be argv again"
