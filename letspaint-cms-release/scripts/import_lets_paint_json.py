#!/usr/bin/env python3
"""Import a legacy Let's Paint `database.json` into StudioSaaS PostgreSQL.

Usage:
    STUDIOSAAS_DATABASE_URL=postgresql://... \
      python scripts/import_lets_paint_json.py database.json lets-paint-studio "Let's Paint Studio"
"""

from __future__ import annotations

import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import connect
from studiosaas.migration import (
    legacy_log_change,
    legacy_log_type,
    load_legacy_database,
    normalize_legacy_package,
    normalize_legacy_registration,
    normalize_legacy_student,
)
from studiosaas.workspaces import ensure_tenant_workspace


def main(argv: list[str]) -> int:
    """Run the legacy import."""

    if len(argv) not in (3, 4):
        print(
            "Usage: import_lets_paint_json.py <database.json> <tenant_slug> [tenant_name]",
            file=sys.stderr,
        )
        return 2

    legacy_path = Path(argv[1])
    tenant_slug = argv[2]
    tenant_name = argv[3] if len(argv) == 4 else "Let's Paint Studio"
    legacy = load_legacy_database(legacy_path)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenants (name, slug, status, plan_code, welcome_message)
                VALUES (%s, %s, 'trial', 'studio', %s)
                ON CONFLICT (slug) DO UPDATE
                SET name = EXCLUDED.name,
                    updated_at = now()
                RETURNING id
                """,
                (tenant_name, tenant_slug, "Imported from the original Let's Paint CMS."),
            )
            tenant_id = cur.fetchone()["id"]
            workspace_path = ensure_tenant_workspace(PROJECT_ROOT, tenant_slug, tenant_name)
            cur.execute(
                """
                UPDATE tenants
                SET settings = jsonb_set(settings, '{workspace_path}', to_jsonb(%s::text), true)
                WHERE id = %s
                """,
                (workspace_path, tenant_id),
            )
            cur.execute(
                """
                INSERT INTO subscriptions (tenant_id, plan_code, status, starts_at, ends_at)
                VALUES (%s, 'studio', 'trialing', now(), NULL)
                ON CONFLICT (tenant_id) DO UPDATE
                SET plan_code = EXCLUDED.plan_code,
                    status = EXCLUDED.status,
                    updated_at = now()
                """,
                (tenant_id,),
            )

            cur.execute(
                """
                INSERT INTO courses (
                    tenant_id, name, description, category, age_range,
                    duration_minutes, credit_unit, default_credit_debit,
                    price_aud_cents, is_active
                )
                VALUES (%s, 'General Studio Class', 'Default imported course.', 'Art', '', 60, 'credits', 1, 0, true)
                ON CONFLICT (tenant_id, name) DO UPDATE
                SET is_active = true
                RETURNING id
                """,
                (tenant_id,),
            )
            default_course_id = cur.fetchone()["id"]

            package_count = 0
            for raw_package in legacy.get("packages", []):
                package = normalize_legacy_package(raw_package)
                cur.execute(
                    """
                    INSERT INTO packages (
                        tenant_id, course_id, name, credits, price_aud_cents,
                        expires_after_days, is_active
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, true)
                    ON CONFLICT (tenant_id, name) DO UPDATE
                    SET credits = EXCLUDED.credits,
                        price_aud_cents = EXCLUDED.price_aud_cents,
                        expires_after_days = EXCLUDED.expires_after_days,
                        is_active = true
                    """,
                    (
                        tenant_id,
                        default_course_id,
                        package["name"],
                        package["credits"],
                        package["price_aud_cents"],
                        package["expires_after_days"],
                    ),
                )
                package_count += 1

            inserted_students = 0
            for raw_student in legacy["students"]:
                student = normalize_legacy_student(raw_student)
                cur.execute(
                    """
                    INSERT INTO students (
                        tenant_id, first_name, last_name, display_name, status, birthday,
                        parent_name, mobile, email, wechat, notes, source_legacy_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id
                    """,
                    (
                        tenant_id,
                        student["first_name"],
                        student["last_name"],
                        student["display_name"],
                        student["status"],
                        student["birthday"],
                        student["parent_name"],
                        student["mobile"],
                        student["email"],
                        student["wechat"],
                        student["notes"],
                        student["source_legacy_id"],
                    ),
                )
                inserted = cur.fetchone()
                student_id = inserted["id"] if inserted else None
                if not student_id and student["source_legacy_id"]:
                    cur.execute(
                        """
                        SELECT id
                        FROM students
                        WHERE tenant_id = %s AND source_legacy_id = %s
                        """,
                        (tenant_id, student["source_legacy_id"]),
                    )
                    existing = cur.fetchone()
                    student_id = existing["id"] if existing else None

                if student_id:
                    inserted_students += 1 if inserted else 0
                    cur.execute(
                        """
                        INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (tenant_id, student_id, course_id) DO UPDATE
                        SET balance = EXCLUDED.balance,
                            updated_at = now()
                        """,
                        (tenant_id, student_id, default_course_id, student["balance"]),
                    )
                    migration_note = (
                        "Imported balance from legacy database.json "
                        f"student:{student['source_legacy_id']}."
                    )
                    cur.execute(
                        """
                        INSERT INTO credit_transactions (
                            tenant_id, student_id, transaction_type, amount,
                            balance_after, note
                        )
                        SELECT %s, %s, 'migration', %s, %s, %s
                        WHERE NOT EXISTS (
                            SELECT 1 FROM credit_transactions
                            WHERE tenant_id = %s AND student_id = %s AND note = %s
                        )
                        """,
                        (
                            tenant_id,
                            student_id,
                            student["balance"],
                            student["balance"],
                            migration_note,
                            tenant_id,
                            student_id,
                            migration_note,
                        ),
                    )

            registration_count = 0
            for raw_registration in legacy.get("pending", []):
                registration = normalize_legacy_registration(raw_registration)
                cur.execute(
                    """
                    INSERT INTO registrations (
                        tenant_id, status, first_name, last_name, parent_name,
                        mobile, email, message, payload
                    )
                    SELECT %s, 'pending', %s, %s, %s, %s, %s, %s, %s::jsonb
                    WHERE NOT EXISTS (
                        SELECT 1 FROM registrations
                        WHERE tenant_id = %s
                          AND payload->>'legacy_id' = %s
                    )
                    """,
                    (
                        tenant_id,
                        registration["first_name"],
                        registration["last_name"],
                        registration["parent_name"],
                        registration["mobile"],
                        registration["email"],
                        registration["message"],
                        registration["payload_json"],
                        tenant_id,
                        registration["legacy_id"],
                    ),
                )
                registration_count += cur.rowcount

            attendance_count = 0
            for raw_log in legacy.get("logs", []):
                log_type = legacy_log_type(raw_log)
                change = legacy_log_change(raw_log)
                if log_type not in {"consume", "purchase", "adjustment"}:
                    continue
                legacy_student_id = str(raw_log.get("studentId") or "").strip()
                if not legacy_student_id:
                    continue
                cur.execute(
                    """
                    SELECT id
                    FROM students
                    WHERE tenant_id = %s AND source_legacy_id = %s
                    """,
                    (tenant_id, legacy_student_id),
                )
                row = cur.fetchone()
                if not row:
                    continue
                student_id = row["id"]
                legacy_log_id = str(raw_log.get("id") or "").strip()
                note = f"Imported legacy log:{legacy_log_id} action:{raw_log.get('action', '')}"
                cur.execute(
                    """
                    INSERT INTO credit_transactions (
                        tenant_id, student_id, transaction_type, amount, note
                    )
                    SELECT %s, %s, %s, %s, %s
                    WHERE NOT EXISTS (
                        SELECT 1 FROM credit_transactions
                        WHERE tenant_id = %s AND note = %s
                    )
                    RETURNING id
                    """,
                    (tenant_id, student_id, log_type, change, note, tenant_id, note),
                )
                tx = cur.fetchone()
                if tx and log_type == "consume":
                    cur.execute(
                        """
                        INSERT INTO attendance_sessions (
                            tenant_id, student_id, course_id, credit_transaction_id, note
                        )
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (tenant_id, student_id, default_course_id, tx["id"], note),
                    )
                    attendance_count += 1

            cur.execute(
                """
                INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb)
                VALUES (
                    %s,
                    (SELECT count(*) FROM students WHERE tenant_id = %s),
                    (SELECT count(*) FROM memberships WHERE tenant_id = %s),
                    0
                )
                ON CONFLICT (tenant_id) DO UPDATE
                SET student_count = EXCLUDED.student_count,
                    user_count = EXCLUDED.user_count,
                    calculated_at = now()
                """,
                (tenant_id, tenant_id, tenant_id),
            )

        conn.commit()

    print(
        f"Imported tenant '{tenant_slug}': "
        f"{inserted_students} new students, {package_count} packages, "
        f"{registration_count} registrations, {attendance_count} attendances."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
