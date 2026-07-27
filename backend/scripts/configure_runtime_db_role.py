#!/usr/bin/env python3
"""Create or refresh the least-privilege PostgreSQL runtime role.

The container entrypoint runs migrations with
``STUDIOSAAS_MIGRATION_DATABASE_URL`` and then calls this script before
dropping that privileged URL from the server process environment.  The
application role receives CRUD access to the current schema, but not role,
database, or schema ownership.  Re-running the script is intentional: new
migrations may add tables or sequences that need grants.

This helper is opt-in.  SaaS deployments that manage roles outside the
application leave ``STUDIOSAAS_DB_RUNTIME_ROLE`` unset and skip it.
"""

from __future__ import annotations

import os
import re
import sys


ROLE_RE = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")


def main() -> int:
    """Ensure the configured runtime role exists and has bounded privileges."""

    role = os.environ.get("STUDIOSAAS_DB_RUNTIME_ROLE", "").strip()
    password = os.environ.get("STUDIOSAAS_DB_RUNTIME_PASSWORD", "")
    database_url = os.environ.get("STUDIOSAAS_MIGRATION_DATABASE_URL", "").strip()

    if not role:
        print("runtime DB role not requested; skipping")
        return 0
    if not ROLE_RE.fullmatch(role):
        print(f"ERROR: invalid STUDIOSAAS_DB_RUNTIME_ROLE: {role!r}", file=sys.stderr)
        return 2
    if len(password) < 32:
        print(
            "ERROR: STUDIOSAAS_DB_RUNTIME_PASSWORD must be at least 32 characters.",
            file=sys.stderr,
        )
        return 2
    if not database_url:
        print(
            "ERROR: STUDIOSAAS_MIGRATION_DATABASE_URL is required to configure "
            "the runtime role.",
            file=sys.stderr,
        )
        return 2

    try:
        import psycopg
        from psycopg import sql
    except ImportError as exc:
        print(f"ERROR: psycopg is required: {exc}", file=sys.stderr)
        return 2

    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database()")
            database_name = str(cur.fetchone()[0])
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
            if cur.fetchone():
                cur.execute(
                    sql.SQL("ALTER ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role),
                        sql.Literal(password),
                    ),
                )
            else:
                cur.execute(
                    sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                        sql.Identifier(role),
                        sql.Literal(password),
                    ),
                )

            role_id = sql.Identifier(role)
            cur.execute(
                sql.SQL(
                    "ALTER ROLE {} NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOREPLICATION NOBYPASSRLS"
                ).format(role_id)
            )
            cur.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(database_name), role_id
                )
            )
            cur.execute(
                sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role_id)
            )
            cur.execute(
                sql.SQL(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON ALL TABLES IN SCHEMA public TO {}"
                ).format(role_id)
            )
            cur.execute(
                sql.SQL(
                    "GRANT USAGE, SELECT, UPDATE "
                    "ON ALL SEQUENCES IN SCHEMA public TO {}"
                ).format(role_id)
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {}"
                ).format(role_id)
            )
            cur.execute(
                sql.SQL(
                    "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                    "GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO {}"
                ).format(role_id)
            )

    print(f"runtime DB role ready: {role}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
