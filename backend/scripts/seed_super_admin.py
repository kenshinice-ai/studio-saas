#!/usr/bin/env python3
"""Seed a local Super Admin user into the StudioSaaS PostgreSQL database.

Usage:
    python3 backend/scripts/seed_super_admin.py [--email ADMIN_EMAIL] [--password ADMIN_PASSWORD] [--name "Admin Name"] [--reset-password]

Defaults:
    email:    admin@studiosaas.local
    password: StudioSaaS@LetsPaint2026!
    name:     System Administrator

This script:
1. Creates a user record with the canonical PBKDF2 password hash.
2. Ensures a platform-level super_admin membership (tenant_id IS NULL),
   which grants access to every tenant — including ones created later.
3. Prints the created user ID for reference.

Security note: This is a LOCAL seed script only. Do not use in production.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def seed_super_admin(
    email: str = "admin@studiosaas.local",
    password: str = "StudioSaaS@LetsPaint2026!",
    full_name: str = "System Administrator",
    reset_password: bool = False,
    show_password: bool = True,
) -> None:
    """Create a super admin user and membership in the local database."""

    try:
        from studiosaas.auth import hash_password
        from studiosaas.db import connect
    except ImportError as exc:
        print(f"ERROR: Cannot import studiosaas.db — {exc}", file=sys.stderr)
        print("Make sure PostgreSQL and psycopg are installed.", file=sys.stderr)
        sys.exit(1)

    pw_hash = hash_password(password)

    with connect() as conn:
        cur = conn.cursor()

        cur.execute(
            "SELECT id, email, status FROM users WHERE email = %s",
            (email,),
        )
        existing = cur.fetchone()
        if existing:
            user_id = str(existing["id"])
            if reset_password:
                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s, full_name = %s, status = 'active', updated_at = now()
                    WHERE id = %s
                    """,
                    (pw_hash, full_name, user_id),
                )
                print(f"Updated user and reset password: {email} (id={user_id})")
            else:
                cur.execute("UPDATE users SET status = 'active', updated_at = now() WHERE id = %s", (user_id,))
                print(f"User already exists: {email} (id={user_id}); password unchanged")
        else:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, status)
                VALUES (%s, %s, %s, 'active')
                RETURNING id
                """,
                (email, pw_hash, full_name),
            )
            user_id = str(cur.fetchone()["id"])
            print(f"Created user: {email} (id={user_id})")

        # Platform membership: tenant_id IS NULL grants access to all tenants.
        # UNIQUE (tenant_id, user_id) does not cover NULL rows, so upsert
        # manually: update first, insert only when no platform row exists.
        cur.execute(
            """
            UPDATE memberships
            SET role = 'super_admin', status = 'active'
            WHERE user_id = %s AND tenant_id IS NULL
            """,
            (user_id,),
        )
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role, status)
                VALUES (NULL, %s, 'super_admin', 'active')
                """,
                (user_id,),
            )
            print("Created platform super_admin membership (all tenants).")
        else:
            print("Refreshed platform super_admin membership (all tenants).")

        conn.commit()

    print("\nSeed complete. Login with:")
    print(f"  email:    {email}")
    if show_password:
        print(f"  password: {password}")
    else:
        print("  password: [hidden]")


def sync_pilot_credential(path: Path, email: str, password: str) -> None:
    """Atomically persist one login while preserving other protected entries."""

    credential_path = path.expanduser().resolve()
    credential_path.parent.mkdir(parents=True, exist_ok=True)
    existing_lines = (
        credential_path.read_text(encoding="utf-8").splitlines()
        if credential_path.exists()
        else [
            "# StudioSaaS privileged pilot credentials",
            "# Managed by seed_super_admin.py; do not commit.",
        ]
    )
    replacement = f"{email.lower()}\t{password}"
    updated_lines: list[str] = []
    replaced = False
    for line in existing_lines:
        account = line.split("\t", 1)[0].strip().lower()
        if account == email.lower():
            if not replaced:
                updated_lines.append(replacement)
                replaced = True
            continue
        updated_lines.append(line)
    if not replaced:
        updated_lines.append(replacement)

    temporary_path = credential_path.with_name(f".{credential_path.name}.tmp")
    fd = os.open(temporary_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(updated_lines) + "\n")
        os.replace(temporary_path, credential_path)
        os.chmod(credential_path, 0o600)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed a local Super Admin user into StudioSaaS."
    )
    parser.add_argument(
        "--email",
        default="admin@studiosaas.local",
        help="Admin email address (default: admin@studiosaas.local)",
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("STUDIOSAAS_ADMIN_PASSWORD", "StudioSaaS@LetsPaint2026!"),
        help="Admin password (defaults to the fixed StudioSaaS launcher credential)",
    )
    parser.add_argument(
        "--name",
        default="System Administrator",
        help="Admin display name (default: System Administrator)",
    )
    parser.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset password for an existing admin user.",
    )
    parser.add_argument(
        "--credential-file",
        type=Path,
        help="Also persist this login in an owner-only launcher credential file.",
    )
    parser.add_argument(
        "--no-print-password",
        action="store_true",
        help="Hide the password from command output.",
    )
    args = parser.parse_args()

    seed_super_admin(
        email=args.email,
        password=args.password,
        full_name=args.name,
        reset_password=args.reset_password,
        show_password=not args.no_print_password,
    )
    if args.credential_file:
        sync_pilot_credential(args.credential_file, args.email, args.password)
        print(f"Credential file updated with mode 0600: {args.credential_file.expanduser().resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
