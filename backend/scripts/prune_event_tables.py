#!/usr/bin/env python3
"""Prune unbounded event tables (DB-audit finding: no retention anywhere).

audit_logs and public_analytics_events grow without limit. This script deletes
rows older than a retention window, in batches so it never holds long locks.
Audit rows are compliance-relevant — the default keeps 2 years, and tenant
archive snapshots taken before pruning retain their own copy.

    python scripts/prune_event_tables.py --dry-run
    python scripts/prune_event_tables.py --audit-days 730 --analytics-days 365

Schedule monthly (cron on EC2 / launchd locally). Uses STUDIOSAAS_DATABASE_URL.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studiosaas.db import connect  # noqa: E402

BATCH = 10_000

TABLES = {
    "audit_logs": ("created_at", "audit_days"),
    "public_analytics_events": ("occurred_at", "analytics_days"),
}


def prune(table: str, column: str, days: int, dry_run: bool) -> int:
    total = 0
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"SELECT count(*) AS n FROM {table} WHERE {column} < now() - make_interval(days => %s)",
                (days,),
            )
            pending = int(cur.fetchone()["n"])
        if dry_run or not pending:
            return pending if dry_run else 0
        while True:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    DELETE FROM {table}
                    WHERE ctid IN (
                        SELECT ctid FROM {table}
                        WHERE {column} < now() - make_interval(days => %s)
                        LIMIT {BATCH}
                    )
                    """,
                    (days,),
                )
                deleted = cur.rowcount
            conn.commit()
            total += deleted
            if deleted < BATCH:
                break
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-days", type=int, default=730)
    parser.add_argument("--analytics-days", type=int, default=365)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    days_by_key = {"audit_days": args.audit_days, "analytics_days": args.analytics_days}
    for table, (column, key) in TABLES.items():
        days = days_by_key[key]
        if days <= 0:
            print(f"{table}: retention disabled (days={days}), skipped")
            continue
        n = prune(table, column, days, args.dry_run)
        verb = "would delete" if args.dry_run else "deleted"
        print(f"{table}: {verb} {n} rows older than {days} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
