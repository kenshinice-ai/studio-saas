#!/usr/bin/env python3
"""Rotate every active StudioSaaS login to a unique password.

The credential file is written with mode 0600 and is intentionally outside the
repository by default. Existing sessions remain valid; restart the application
after rotation when an immediate global sign-in reset is required.

This used to select `role IN ('super_admin', 'owner', 'staff')`, which reads
like "everyone who matters" and is not: the role vocabulary in production is
super_admin / owner / manager / front_desk / teacher, so a rotation run against
a real database left every manager, front-desk and teacher login untouched.
It now takes every active account with an active membership, whatever the role.

Accounts with no membership at all are not rotated — a login that belongs to no
tenant should be disabled, not given a fresh password. --disable-orphans does
that, reversibly (status='disabled'), rather than deleting the row.

    python backend/scripts/rotate_pilot_credentials.py --dry-run
    python backend/scripts/rotate_pilot_credentials.py --exclude ops@example.com
    python backend/scripts/rotate_pilot_credentials.py --disable-orphans
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


def _legacy_cms_hash(password: str) -> str:
    """Return a hash compatible with the legacy CMS password file."""

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def _write_private_file(path: Path, content: str) -> None:
    """Write a UTF-8 file with owner-only permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o600)


def rotate(
    output_path: Path,
    cms_password_path: Path,
    exclude: set[str] | None = None,
    disable_orphans: bool = False,
    dry_run: bool = False,
) -> int:
    """Rotate database accounts and the separate legacy CMS password."""

    from studiosaas.auth import hash_password
    from studiosaas.db import connect

    exclude = {e.strip().lower() for e in (exclude or set()) if e.strip()}

    with connect() as conn:
        with conn.cursor() as cur:
            if disable_orphans:
                cur.execute(
                    """
                    UPDATE users SET status = 'disabled', updated_at = now()
                    WHERE status = 'active'
                      AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = users.id)
                    RETURNING lower(email) AS email
                    """
                    if not dry_run else
                    """
                    SELECT lower(email) AS email FROM users
                    WHERE status = 'active'
                      AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = users.id)
                    ORDER BY lower(email)
                    """
                )
                orphans = [row["email"] for row in cur.fetchall()]
                verb = "would disable" if dry_run else "disabled"
                print(f"{verb} {len(orphans)} membership-less account(s):")
                for email in orphans:
                    print(f"  {email}")
            cur.execute(
                """
                SELECT DISTINCT u.id, lower(u.email) AS email
                FROM users u
                JOIN memberships m ON m.user_id = u.id
                WHERE u.status = 'active'
                  AND m.status = 'active'
                ORDER BY lower(u.email)
                """
            )
            accounts = [a for a in cur.fetchall() if a["email"] not in exclude]
            for skipped in sorted(exclude):
                print(f"excluded by request: {skipped}")
            if not accounts:
                raise RuntimeError("No active accounts were found.")
            if dry_run:
                print(f"would rotate {len(accounts)} account(s):")
                for a in accounts:
                    print(f"  {a['email']}")
                return len(accounts)
            credentials: list[tuple[str, str]] = []
            for account in accounts:
                password = secrets.token_urlsafe(18)
                cur.execute(
                    "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                    (hash_password(password), account["id"]),
                )
                credentials.append((account["email"], password))
        conn.commit()

    legacy_cms_password = secrets.token_urlsafe(18)
    _write_private_file(cms_password_path, _legacy_cms_hash(legacy_cms_password))
    credential_lines = [
        "# StudioSaaS privileged pilot credentials",
        "# Generated by rotate_pilot_credentials.py; do not commit.",
        *(f"{email}\t{password}" for email, password in credentials),
        f"legacy-cms\t{legacy_cms_password}",
    ]
    _write_private_file(output_path, "\n".join(credential_lines) + "\n")
    print(f"Rotated {len(credentials)} privileged account(s).")
    print(f"Rotated the legacy CMS password at {cms_password_path}.")
    print(f"Credentials written to {output_path} with mode 0600.")
    return len(credentials)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".studiosaas" / "pilot-credentials.txt",
        help="Protected credential output path.",
    )
    cms_data_dir = Path(os.environ.get("CMS_DATA_DIR", "").strip() or APP_ROOT)
    if not cms_data_dir.is_absolute():
        cms_data_dir = APP_ROOT / cms_data_dir
    parser.add_argument(
        "--cms-password-file",
        type=Path,
        default=cms_data_dir / ".cms_password",
        help="Legacy CMS password hash file used by the deployed server.",
    )
    parser.add_argument("--exclude", action="append", default=[],
                        help="Email to leave untouched. Repeatable.")
    parser.add_argument("--disable-orphans", action="store_true",
                        help="Set status='disabled' on accounts with no membership.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report what would change and write nothing.")
    args = parser.parse_args()
    rotate(
        args.output.expanduser().resolve(),
        args.cms_password_file.expanduser().resolve(),
        exclude=set(args.exclude),
        disable_orphans=args.disable_orphans,
        dry_run=args.dry_run,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
