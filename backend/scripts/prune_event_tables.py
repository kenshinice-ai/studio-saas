#!/usr/bin/env python3
"""Prune unbounded event tables (DB-audit finding: no retention anywhere).

Five tables here grow with usage and nothing ever deletes from them. This
script removes rows past a retention window, in batches so it never holds a
long lock. Audit rows are compliance-relevant — the default keeps 2 years, and
a tenant archive snapshot taken before pruning keeps its own copy regardless.

    python backend/scripts/prune_event_tables.py --dry-run
    python backend/scripts/prune_event_tables.py --audit-days 730

Schedule monthly. On the Lightsail host go through the control script rather
than calling this path directly — see deploy/aws/README_AWS.md §9.1b:

    bash deploy/aws/lightsail_ctl.sh prune --dry-run

NOT pruned, deliberately: student_publication_consent_events is legal proof of
consent and a tenant archive snapshot is the only other copy. It has no
retention window and must not get one here.
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studiosaas.db import connect  # noqa: E402

BATCH = 10_000

# table -> (timestamp column, retention key)
#
# The last three were missing and are the ones that grow with *traffic* rather
# than with operator actions: a notification row per message sent, a session
# row per student login, an attempt row per rate-limit window. They were left
# out of the original pass and so had no ceiling at all.
TABLES = {
    "audit_logs": ("created_at", "audit_days"),
    "public_analytics_events": ("occurred_at", "analytics_days"),
    "notification_logs": ("created_at", "notification_days"),
    # Sessions are dead once expired; keep a short tail for incident review.
    "student_access_sessions": ("expires_at", "session_days"),
    # Rate-limit windows are meaningless once the lockout is long past.
    "student_access_attempts": ("updated_at", "session_days"),
}


def prune(table: str, column: str, days: int, dry_run: bool) -> int:
    total = 0
    # The retention predicate scans an unindexed timestamp column, so on a
    # large table even the count can exceed the application's 30s statement
    # cap — lift the session caps; batching below keeps each lock short.
    with connect(statement_timeout_ms=0, lock_timeout_ms=0) as conn:
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
    parser.add_argument("--notification-days", type=int, default=365)
    parser.add_argument("--session-days", type=int, default=30,
                        help="Expired student sessions and rate-limit windows. 0 disables.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    days_by_key = {
        "audit_days": args.audit_days,
        "analytics_days": args.analytics_days,
        "notification_days": args.notification_days,
        "session_days": args.session_days,
    }
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
