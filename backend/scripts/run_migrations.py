#!/usr/bin/env python3
"""Apply pending SQL migrations from backend/db/migrations/ in order.

Usage:
    python scripts/run_migrations.py               # apply pending migrations
    python scripts/run_migrations.py --dry-run     # list pending, change nothing
    python scripts/run_migrations.py --baseline 0001_schema_v1.sql
        # mark this version (and everything before it) as applied without
        # executing — use once on databases bootstrapped from schema_v1.sql

Behaviour:
- Tracks applied versions in the ``schema_migrations`` table.
- Applies each migration file inside its own transaction.
- Safe to re-run: already-applied versions are skipped.

Connection comes from STUDIOSAAS_DATABASE_URL (see studiosaas.db).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

MIGRATIONS_DIR = APP_ROOT / "db" / "migrations"

ENSURE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def _migration_files() -> list[Path]:
    if not MIGRATIONS_DIR.is_dir():
        print(f"ERROR: migrations directory not found: {MIGRATIONS_DIR}", file=sys.stderr)
        sys.exit(1)
    return sorted(MIGRATIONS_DIR.glob("*.sql"))


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(ENSURE_TABLE_SQL)
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}
    return set()


def run(dry_run: bool = False, baseline: str | None = None) -> int:
    try:
        from studiosaas.db import connect
    except ImportError as exc:
        print(f"ERROR: cannot import studiosaas.db — {exc}", file=sys.stderr)
        return 1

    files = _migration_files()
    if not files:
        print("No migration files found.")
        return 0

    if baseline is not None and baseline not in {f.name for f in files}:
        print(f"ERROR: baseline version '{baseline}' does not match any migration file.", file=sys.stderr)
        return 1

    with connect() as conn:
        applied = _applied_versions(conn)
        conn.commit()

        if baseline is not None:
            with conn.cursor() as cur:
                for path in files:
                    if path.name in applied:
                        continue
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s) ON CONFLICT DO NOTHING",
                        (path.name,),
                    )
                    print(f"baselined  {path.name}")
                    if path.name == baseline:
                        break
            conn.commit()
            applied = _applied_versions(conn)
            conn.commit()

        pending = [path for path in files if path.name not in applied]
        if not pending:
            print("Database is up to date. Nothing to apply.")
            return 0

        for path in pending:
            if dry_run:
                print(f"pending    {path.name}")
                continue
            sql = path.read_text(encoding="utf-8")
            try:
                with conn.cursor() as cur:
                    cur.execute(sql)
                    cur.execute(
                        "INSERT INTO schema_migrations (version) VALUES (%s)",
                        (path.name,),
                    )
                conn.commit()
            except Exception as exc:
                conn.rollback()
                print(f"FAILED     {path.name}: {exc}", file=sys.stderr)
                return 1
            print(f"applied    {path.name}")

        if dry_run:
            print(f"{len(pending)} migration(s) pending. Run without --dry-run to apply.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply StudioSaaS SQL migrations in order.")
    parser.add_argument("--dry-run", action="store_true", help="List pending migrations without applying.")
    parser.add_argument(
        "--baseline",
        metavar="VERSION",
        help="Mark VERSION and all earlier migrations as applied without executing.",
    )
    args = parser.parse_args()
    return run(dry_run=args.dry_run, baseline=args.baseline)


if __name__ == "__main__":
    raise SystemExit(main())
