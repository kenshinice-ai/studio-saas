#!/usr/bin/env python3
"""Import only deterministic current student data into an existing tenant.

The default mode is read-only. A destructive import requires all three flags:
``--apply``, ``--reset-all-students``, and an exact ``--confirm-tenant`` value.
Historical logs, attendance, packages, rosters, media, access codes, privacy
history, and uncertain extension fields are intentionally excluded.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import connect
from studiosaas.migration import load_core_students


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest used to bind preview and apply runs."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decimal_total(students: list[dict[str, Any]]) -> Decimal:
    """Return the exact total opening balance for the import report."""

    return sum((student["balance"] for student in students), start=Decimal("0"))


def _tenant_snapshot(cur: Any, tenant_slug: str) -> dict[str, Any]:
    """Resolve exactly one existing target tenant and its current counts."""

    cur.execute(
        """
        SELECT id, name, slug, status
        FROM tenants
        WHERE slug = %s
        """,
        (tenant_slug,),
    )
    tenant = cur.fetchone()
    if not tenant:
        raise RuntimeError(
            f"Target tenant does not exist: {tenant_slug}. Refusing to create it implicitly."
        )
    cur.execute(
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = %s)::int AS students,
            (SELECT count(*) FROM students)::int AS all_tenant_students,
            (SELECT COALESCE(sum(balance), 0) FROM credit_accounts
              WHERE tenant_id = %s AND course_id IS NULL) AS target_balance
        """,
        (tenant["id"], tenant["id"]),
    )
    counts = cur.fetchone()
    return {**tenant, **counts}


def _delete_all_students(cur: Any) -> int:
    """Delete every demo student; foreign-key cascades remove linked demo data."""

    cur.execute("DELETE FROM students")
    return cur.rowcount


def _insert_core_students(
    cur: Any,
    tenant_id: str,
    students: list[dict[str, Any]],
    source_digest: str,
) -> int:
    """Insert core students, default accounts, and one opening-balance audit row."""

    inserted = 0
    for student in students:
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status, birthday,
                mobile, email, wechat, notes, source_legacy_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                tenant_id,
                student["first_name"],
                student["last_name"],
                student["display_name"],
                student["status"],
                student["birthday"],
                student["mobile"],
                student["email"],
                student["wechat"],
                student["notes"],
                student["source_legacy_id"],
            ),
        )
        student_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance)
            VALUES (%s, %s, NULL, %s)
            RETURNING id
            """,
            (tenant_id, student_id, student["balance"]),
        )
        account_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, account_id, transaction_type,
                amount, balance_after, note
            )
            VALUES (%s, %s, %s, 'migration', %s, %s, %s)
            """,
            (
                tenant_id,
                student_id,
                account_id,
                student["balance"],
                student["balance"],
                "Core opening balance import "
                f"source:{source_digest[:12]} student:{student['source_legacy_id']}",
            ),
        )
        inserted += 1
    return inserted


def _update_usage(cur: Any) -> None:
    """Refresh student totals for every tenant after the global demo reset."""

    cur.execute(
        """
        INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb)
        SELECT
            t.id,
            (SELECT count(*) FROM students s
              WHERE s.tenant_id = t.id AND s.status <> 'archived'),
            (SELECT count(*) FROM memberships m
              WHERE m.tenant_id = t.id AND m.status = 'active' AND m.role <> 'parent'),
            COALESCE(existing.storage_used_mb, 0)
        FROM tenants t
        LEFT JOIN tenant_usage existing ON existing.tenant_id = t.id
        ON CONFLICT (tenant_id) DO UPDATE
        SET student_count = EXCLUDED.student_count,
            user_count = EXCLUDED.user_count,
            calculated_at = now()
        """
    )


def build_parser() -> argparse.ArgumentParser:
    """Build the strict import command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--tenant-slug", default="lets-paint-studio")
    parser.add_argument("--expected-sha256", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--reset-all-students", action="store_true")
    parser.add_argument("--confirm-tenant", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Preview or atomically apply the core student import."""

    args = build_parser().parse_args(argv)
    source = args.source.expanduser().resolve()
    source_digest = _sha256(source)
    if args.expected_sha256 and args.expected_sha256.lower() != source_digest:
        raise SystemExit(
            f"Source SHA-256 mismatch: expected {args.expected_sha256}, got {source_digest}"
        )
    students = load_core_students(source)

    with connect() as conn:
        with conn.cursor() as cur:
            tenant = _tenant_snapshot(cur, args.tenant_slug)
            report = {
                "mode": "apply" if args.apply else "dry-run",
                "source": str(source),
                "source_sha256": source_digest,
                "target_tenant": {
                    "id": str(tenant["id"]),
                    "name": tenant["name"],
                    "slug": tenant["slug"],
                    "status": tenant["status"],
                },
                "before": {
                    "target_students": tenant["students"],
                    "all_tenant_students": tenant["all_tenant_students"],
                    "target_balance": str(tenant["target_balance"]),
                },
                "import": {
                    "students": len(students),
                    "opening_balance": str(_decimal_total(students)),
                },
                "excluded": [
                    "logs", "attendance", "rosters", "packages", "pending",
                    "media", "portfolio", "access_codes", "privacy_history",
                    "creative_profile",
                ],
            }
            if not args.apply:
                conn.rollback()
                print(json.dumps(report, ensure_ascii=False, indent=2))
                return 0

            if not args.reset_all_students:
                raise SystemExit("Apply requires --reset-all-students.")
            if args.confirm_tenant != args.tenant_slug:
                raise SystemExit(
                    f"Apply requires --confirm-tenant {args.tenant_slug}."
                )

            deleted = _delete_all_students(cur)
            inserted = _insert_core_students(
                cur, str(tenant["id"]), students, source_digest
            )
            _update_usage(cur)
            conn.commit()
            report["result"] = {"deleted_demo_students": deleted, "inserted": inserted}
            print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
