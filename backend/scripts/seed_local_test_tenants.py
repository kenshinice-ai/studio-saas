#!/usr/bin/env python3
"""Seed deterministic StudioSaaS tenants for local isolation tests.

The fixture intentionally uses stable slugs and human-readable names while
letting PostgreSQL generate UUIDs.  It deletes and recreates only the two
isolation-test tenants, so repeated runs produce the same logical dataset
without disturbing demo tenants.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.auth import hash_password

TENANT_A = "isolation-alpha"
TENANT_B = "isolation-beta"
OWNER_A_EMAIL = "owner.alpha@studiosaas.local"
OWNER_B_EMAIL = "owner.beta@studiosaas.local"
SUPER_EMAIL = "admin@studiosaas.local"
PASSWORD = "admin123456"


def _ensure_media_schema(cur: Any) -> None:
    """Keep existing local databases compatible with canonical media assets."""

    cur.execute(
        """
        ALTER TABLE media_assets
        ADD COLUMN IF NOT EXISTS asset_type text NOT NULL DEFAULT 'portfolio'
        CHECK (asset_type IN ('student_photo', 'registration_photo', 'portfolio', 'homework', 'sheet_music', 'logo'))
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE students
                ADD CONSTRAINT students_student_photo_asset_id_fkey
                FOREIGN KEY (student_photo_asset_id) REFERENCES media_assets(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )


def _ensure_tenant_archival_schema(cur: Any) -> None:
    """Keep existing local databases compatible with safe tenant archival."""

    cur.execute("ALTER TABLE tenants DROP CONSTRAINT IF EXISTS tenants_status_check")
    cur.execute(
        """
        ALTER TABLE tenants
        ADD CONSTRAINT tenants_status_check
        CHECK (status IN ('trial', 'active', 'past_due', 'paused', 'cancelled', 'archived', 'deleted'))
        """
    )
    cur.execute(
        """
        ALTER TABLE tenants
        ADD COLUMN IF NOT EXISTS archived_at timestamptz,
        ADD COLUMN IF NOT EXISTS archived_by uuid REFERENCES users(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS archive_path text,
        ADD COLUMN IF NOT EXISTS deletion_requested_at timestamptz,
        ADD COLUMN IF NOT EXISTS deleted_at timestamptz
        """
    )
    cur.execute(
        """
        DO $$
        BEGIN
            ALTER TABLE tenants
                ADD CONSTRAINT tenants_archived_by_fkey
                FOREIGN KEY (archived_by) REFERENCES users(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN
            NULL;
        END $$;
        """
    )
    cur.execute("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_status_check")
    cur.execute(
        """
        ALTER TABLE subscriptions
        ADD CONSTRAINT subscriptions_status_check
        CHECK (status IN ('trialing', 'active', 'past_due', 'paused', 'cancelled', 'archived'))
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS tenant_archives (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid REFERENCES tenants(id) ON DELETE SET NULL,
            tenant_slug text NOT NULL,
            tenant_name text NOT NULL,
            archive_path text NOT NULL,
            db_snapshot_path text,
            media_archive_path text,
            workspace_archive_path text,
            created_by uuid REFERENCES users(id) ON DELETE SET NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )


def _upsert_user(cur: Any, *, email: str, full_name: str) -> str:
    """Create or activate a local test user and return its UUID."""

    cur.execute(
        """
        INSERT INTO users (email, password_hash, full_name, status)
        VALUES (%s, %s, %s, 'active')
        ON CONFLICT (email) DO UPDATE
        SET password_hash = EXCLUDED.password_hash,
            full_name = EXCLUDED.full_name,
            status = 'active',
            updated_at = now()
        RETURNING id
        """,
        (email, hash_password(PASSWORD), full_name),
    )
    return str(cur.fetchone()["id"])


def _create_tenant(cur: Any, *, slug: str, name: str) -> str:
    """Create one deterministic tenant and return its UUID."""

    cur.execute("DELETE FROM tenants WHERE slug = %s", (slug,))
    cur.execute(
        """
        INSERT INTO tenants (
            name, slug, status, plan_code, welcome_message,
            contact_phone, contact_email, address, settings
        )
        VALUES (%s, %s, 'active', 'studio', %s, %s, %s, %s, '{}'::jsonb)
        RETURNING id
        """,
        (
            name,
            slug,
            f"Welcome to {name}.",
            "0400000000",
            f"hello@{slug}.test",
            "100 Isolation Street",
        ),
    )
    tenant_id = str(cur.fetchone()["id"])
    cur.execute(
        """
        INSERT INTO subscriptions (tenant_id, plan_code, status)
        VALUES (%s, 'studio', 'active')
        ON CONFLICT (tenant_id) DO UPDATE
        SET plan_code = EXCLUDED.plan_code,
            status = EXCLUDED.status,
            updated_at = now()
        """,
        (tenant_id,),
    )
    cur.execute(
        """
        INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb)
        VALUES (%s, 0, 0, 0)
        ON CONFLICT (tenant_id) DO UPDATE
        SET student_count = 0,
            user_count = 0,
            storage_used_mb = 0,
            calculated_at = now()
        """,
        (tenant_id,),
    )
    return tenant_id


def _add_owner_membership(cur: Any, *, tenant_id: str, user_id: str, role: str = "owner") -> None:
    """Ensure an active tenant membership for a test user."""

    cur.execute(
        """
        INSERT INTO memberships (tenant_id, user_id, role, status)
        VALUES (%s, %s, %s, 'active')
        ON CONFLICT (tenant_id, user_id) DO UPDATE
        SET role = EXCLUDED.role,
            status = 'active'
        """,
        (tenant_id, user_id, role),
    )


def _add_student(
    cur: Any,
    *,
    tenant_id: str,
    first_name: str,
    last_name: str,
    mobile: str,
    balance: float,
    status: str = "active",
) -> str:
    """Create one student plus its default credit account."""

    display_name = f"{first_name} {last_name}".strip()
    cur.execute(
        """
        INSERT INTO students (
            tenant_id, first_name, last_name, display_name, status, mobile, email
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            tenant_id,
            first_name,
            last_name,
            display_name,
            status,
            mobile,
            f"{first_name.lower()}@example.test",
        ),
    )
    student_id = str(cur.fetchone()["id"])
    cur.execute(
        """
        INSERT INTO credit_accounts (tenant_id, student_id, balance)
        VALUES (%s, %s, %s)
        """,
        (tenant_id, student_id, balance),
    )
    return student_id


def _add_course_package(cur: Any, *, tenant_id: str, label: str) -> tuple[str, str]:
    """Create one active course and one active package for a tenant."""

    cur.execute(
        """
        INSERT INTO courses (
            tenant_id, name, description, category, duration_minutes,
            credit_unit, default_credit_debit, price_aud_cents, is_active
        )
        VALUES (%s, %s, %s, 'Isolation', 60, 'credits', 1, 1000, true)
        RETURNING id
        """,
        (tenant_id, f"{label} Course", f"{label} course fixture"),
    )
    course_id = str(cur.fetchone()["id"])
    cur.execute(
        """
        INSERT INTO packages (tenant_id, course_id, name, credits, price_aud_cents, is_active)
        VALUES (%s, %s, %s, 5, 5000, true)
        RETURNING id
        """,
        (tenant_id, course_id, f"{label} Package"),
    )
    package_id = str(cur.fetchone()["id"])
    return course_id, package_id


def _add_registration(cur: Any, *, tenant_id: str, first_name: str, mobile: str) -> str:
    """Create one pending public registration fixture."""

    cur.execute(
        """
        INSERT INTO registrations (tenant_id, status, first_name, last_name, mobile, payload)
        VALUES (%s, 'pending', %s, 'Applicant', %s, %s::jsonb)
        RETURNING id
        """,
        (tenant_id, first_name, mobile, '{"fixture": true}'),
    )
    return str(cur.fetchone()["id"])


def _add_media(cur: Any, *, tenant_id: str, student_id: str, label: str) -> str:
    """Create one media asset for portfolio isolation tests."""

    cur.execute(
        """
        INSERT INTO media_assets (
            tenant_id, owner_student_id, asset_type, storage_key, original_filename,
            mime_type, byte_size, checksum_sha256, visibility
        )
        VALUES (%s, %s, 'portfolio', %s, %s, 'image/png', 68, %s, 'private')
        RETURNING id
        """,
        (tenant_id, student_id, f"fixtures/{label}.png", f"{label}.png", f"sha256-{label}"),
    )
    return str(cur.fetchone()["id"])


def seed() -> dict[str, Any]:
    """Seed deterministic tenants and return the created fixture IDs."""

    from studiosaas.db import connect

    with connect() as conn:
        with conn.cursor() as cur:
            _ensure_media_schema(cur)
            _ensure_tenant_archival_schema(cur)
            cur.execute(
                """
                INSERT INTO plans (
                    code, name, monthly_price_aud, student_limit, user_limit,
                    storage_limit_mb, features
                )
                VALUES ('studio', 'Studio', 99, 500, 8, 30720, '{}'::jsonb)
                ON CONFLICT (code) DO NOTHING
                """
            )
            owner_a = _upsert_user(cur, email=OWNER_A_EMAIL, full_name="Isolation Alpha Owner")
            owner_b = _upsert_user(cur, email=OWNER_B_EMAIL, full_name="Isolation Beta Owner")
            super_admin = _upsert_user(cur, email=SUPER_EMAIL, full_name="System Administrator")

            tenant_a = _create_tenant(cur, slug=TENANT_A, name="Isolation Alpha Studio")
            tenant_b = _create_tenant(cur, slug=TENANT_B, name="Isolation Beta Studio")

            _add_owner_membership(cur, tenant_id=tenant_a, user_id=owner_a)
            _add_owner_membership(cur, tenant_id=tenant_b, user_id=owner_b)
            _add_owner_membership(cur, tenant_id=tenant_a, user_id=super_admin, role="super_admin")
            _add_owner_membership(cur, tenant_id=tenant_b, user_id=super_admin, role="super_admin")

            student_a = _add_student(
                cur,
                tenant_id=tenant_a,
                first_name="Alpha",
                last_name="Student",
                mobile="0400000001",
                balance=11,
            )
            archived_a = _add_student(
                cur,
                tenant_id=tenant_a,
                first_name="Alpha",
                last_name="Archived",
                mobile="0400000099",
                balance=99,
                status="archived",
            )
            student_b = _add_student(
                cur,
                tenant_id=tenant_b,
                first_name="Beta",
                last_name="Student",
                mobile="0400000002",
                balance=22,
            )

            course_a, package_a = _add_course_package(cur, tenant_id=tenant_a, label="Alpha")
            course_b, package_b = _add_course_package(cur, tenant_id=tenant_b, label="Beta")
            registration_a = _add_registration(cur, tenant_id=tenant_a, first_name="Alpha", mobile="0411111111")
            registration_b = _add_registration(cur, tenant_id=tenant_b, first_name="Beta", mobile="0422222222")
            media_a = _add_media(cur, tenant_id=tenant_a, student_id=student_a, label="alpha")
            media_b = _add_media(cur, tenant_id=tenant_b, student_id=student_b, label="beta")

        conn.commit()

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "student_a": student_a,
        "archived_a": archived_a,
        "student_b": student_b,
        "course_a": course_a,
        "course_b": course_b,
        "package_a": package_a,
        "package_b": package_b,
        "registration_a": registration_a,
        "registration_b": registration_b,
        "media_a": media_a,
        "media_b": media_b,
        "owner_a_email": OWNER_A_EMAIL,
        "owner_b_email": OWNER_B_EMAIL,
        "super_email": SUPER_EMAIL,
        "password": PASSWORD,
    }


def main() -> int:
    """Seed all local isolation tenants."""

    fixtures = seed()
    print(f"Seeded local isolation tenants: {TENANT_A}, {TENANT_B}")
    print(f"Tenant A student: {fixtures['student_a']}")
    print(f"Tenant B student: {fixtures['student_b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
