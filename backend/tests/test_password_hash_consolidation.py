"""One password-hash implementation, all historical formats verifiable.

Until v10.11.0 the repository carried PBKDF2 twice: `auth.py` for the v1 user
table and `server.py _hash_pw/_verify_pw` for the legacy CMS password file.
Same storage format, two code paths — and two DIFFERENT legacy fallbacks:
`auth` verified bare ``sha256(pw)`` while the CMS file used
``sha256('lps-cms:' + pw)``. A naive consolidation would have silently locked
out every legacy CMS password file, which is why these tests exist before the
consolidation and must keep passing after it.
"""

import hashlib
from pathlib import Path

from studiosaas.auth import hash_password, verify_password

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SERVER = REPOSITORY_ROOT / "backend/server.py"


def test_pbkdf2_roundtrip():
    stored = hash_password("correct horse")
    assert stored.startswith("pbkdf2$600000$")
    ok, needs_upgrade = verify_password("correct horse", stored)
    assert ok and not needs_upgrade
    ok, _ = verify_password("wrong horse", stored)
    assert not ok


def test_legacy_bare_sha256_still_verifies_and_flags_upgrade():
    stored = hashlib.sha256("old-v1-password".encode("utf-8")).hexdigest()
    ok, needs_upgrade = verify_password("old-v1-password", stored)
    assert ok and needs_upgrade
    ok, _ = verify_password("not-it", stored)
    assert not ok


def test_legacy_cms_prefixed_sha256_still_verifies_and_flags_upgrade():
    """The legacy CMS password file format: sha256('lps-cms:' + password).

    This is the case a naive consolidation breaks. An operator with an old
    password file must still be able to log in — and be upgraded to PBKDF2.
    """

    stored = hashlib.sha256("lps-cms:studio-password".encode("utf-8")).hexdigest()
    ok, needs_upgrade = verify_password("studio-password", stored)
    assert ok and needs_upgrade
    ok, _ = verify_password("studio-password-wrong", stored)
    assert not ok


def test_garbage_hash_fails_closed():
    for stored in ("", "not-a-hash", "pbkdf2$notanumber$zz$zz", None):
        ok, needs_upgrade = verify_password("anything", stored)
        assert not ok and not needs_upgrade


def test_server_delegates_instead_of_reimplementing():
    """server.py must not carry its own PBKDF2 any more."""

    source = SERVER.read_text(encoding="utf-8")
    assert "pbkdf2_hmac" not in source, (
        "server.py grew its own PBKDF2 again — auth.hash_password/"
        "verify_password is the single implementation"
    )
    assert "from studiosaas.auth import" in source
    assert "_hash_pw = hash_password" in source
    assert "_verify_pw = verify_password" in source
