#!/usr/bin/env python3
"""Set one shared password for every local/Pilot application account.

This is an explicit demonstration-environment maintenance command, not a
startup hook. It updates all StudioSaaS ``users`` rows and the separate legacy
CMS password file in one operator-invoked action. Normal application restarts
must never call this script or change the stored password hashes.

The command refuses production and standalone/customer-edition environments.
The password is accepted only through ``STUDIOSAAS_SHARED_DEMO_PASSWORD`` so it
does not appear in process arguments.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import secrets
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

PBKDF2_ITERATIONS = 600_000
CONFIRMATION = "SET-ALL-LOCAL-APPLICATION-PASSWORDS"


def _legacy_cms_hash(password: str) -> str:
    """Return a fresh PBKDF2 hash compatible with the legacy CMS."""

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _write_private_file(path: Path, content: str) -> None:
    """Atomically write an owner-only UTF-8 file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def set_shared_password(
    *,
    password: str,
    cms_password_path: Path,
    credentials_path: Path,
) -> int:
    """Update every application user and persist protected local handoff files."""

    from studiosaas.auth import hash_password
    from studiosaas.db import connect

    if len(password) < 12:
        raise ValueError("The shared demonstration password must contain at least 12 characters.")

    password_hash = hash_password(password)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, lower(email) AS email FROM users ORDER BY lower(email)")
            accounts = cur.fetchall()
            if not accounts:
                raise RuntimeError("No StudioSaaS application accounts were found.")
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s, updated_at = now()
                """,
                (password_hash,),
            )
        conn.commit()

    _write_private_file(cms_password_path, _legacy_cms_hash(password))
    lines = [
        "# StudioSaaS local/Pilot shared application credentials",
        "# Demonstration only. Do not commit or use for AWS production.",
        *(f"{account['email']}\t{password}" for account in accounts),
        f"legacy-cms\t{password}",
    ]
    _write_private_file(credentials_path, "\n".join(lines) + "\n")
    return len(accounts)


def main() -> int:
    """Validate the local boundary and perform the explicit password migration."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm", required=True)
    parser.add_argument("--cms-password-file", required=True, type=Path)
    parser.add_argument("--credentials-file", required=True, type=Path)
    args = parser.parse_args()

    if args.confirm != CONFIRMATION:
        raise SystemExit(f"Refusing password migration. --confirm must be exactly: {CONFIRMATION}")
    environment = os.environ.get("STUDIOSAAS_ENV", "local").strip().lower()
    mode = os.environ.get("STUDIOSAAS_MODE", "saas").strip().lower()
    if environment not in {"local", "pilot"}:
        raise SystemExit("Refusing shared passwords outside local/Pilot environments.")
    if mode == "standalone":
        raise SystemExit("Refusing to change a customer Edition from the SaaS demo password tool.")
    password = os.environ.get("STUDIOSAAS_SHARED_DEMO_PASSWORD", "")
    if not password:
        raise SystemExit("STUDIOSAAS_SHARED_DEMO_PASSWORD is required.")

    count = set_shared_password(
        password=password,
        cms_password_path=args.cms_password_file.expanduser().resolve(),
        credentials_path=args.credentials_file.expanduser().resolve(),
    )
    print(f"Updated {count} StudioSaaS application account(s).")
    print("Updated the legacy CMS password.")
    print("Normal service restarts do not invoke this command or change passwords.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
