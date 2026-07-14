#!/usr/bin/env python3
"""Seed a local Super Admin user into the StudioSaaS PostgreSQL database.

Usage:
    python3 backend/scripts/seed_super_admin.py [--email ADMIN_EMAIL] [--password ADMIN_PASSWORD] [--name "Admin Name"] [--reset-password]

Defaults:
    email:    admin@studiosaas.local
    password: admin123456
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
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))


def seed_super_admin(
    email: str = "admin@studiosaas.local",
    password: str = "admin123456",
    full_name: str = "System Administrator",
    reset_password: bool = False,
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
    print(f"  password: {password}")


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
        default="admin123456",
        help="Admin password (default: admin123456)",
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
    args = parser.parse_args()

    seed_super_admin(
        email=args.email,
        password=args.password,
        full_name=args.name,
        reset_password=args.reset_password,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
