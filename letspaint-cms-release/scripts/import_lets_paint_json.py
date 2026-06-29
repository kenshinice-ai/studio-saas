#!/usr/bin/env python3
"""Import a legacy Let's Paint `database.json` into StudioSaaS PostgreSQL.

Usage:
    STUDIOSAAS_DATABASE_URL=postgresql://... \
      python scripts/import_lets_paint_json.py database.json lets-paint-studio
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from studiosaas.db import connect
from studiosaas.migration import load_legacy_database, normalize_legacy_student


def main(argv: list[str]) -> int:
    """Run the legacy import."""

    if len(argv) != 3:
        print("Usage: import_lets_paint_json.py <database.json> <tenant_slug>", file=sys.stderr)
        return 2

    legacy_path = Path(argv[1])
    tenant_slug = argv[2]
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
                ("Let's Paint Studio", tenant_slug, "Imported from the original Let's Paint CMS."),
            )
            tenant_id = cur.fetchone()["id"]

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
                if inserted:
                    cur.execute(
                        """
                        INSERT INTO credit_accounts (tenant_id, student_id, balance)
                        VALUES (%s, %s, %s)
                        """,
                        (tenant_id, inserted["id"], student["balance"]),
                    )
                    cur.execute(
                        """
                        INSERT INTO credit_transactions (
                            tenant_id, student_id, transaction_type, amount,
                            balance_after, note
                        )
                        VALUES (%s, %s, 'migration', %s, %s, %s)
                        """,
                        (
                            tenant_id,
                            inserted["id"],
                            student["balance"],
                            student["balance"],
                            "Imported balance from legacy database.json.",
                        ),
                    )

        conn.commit()

    print(f"Imported {len(legacy['students'])} legacy students into tenant '{tenant_slug}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
