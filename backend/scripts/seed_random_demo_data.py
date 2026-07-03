#!/usr/bin/env python3
"""Seed StudioSaaS with relational demo data for local UI testing.

The script intentionally writes through the PostgreSQL v1 schema instead of
mocking responses. It exercises tenant, course, package, student, credit,
registration, media, portfolio, audit, subscription, and usage relationships.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from studiosaas.auth import hash_password
from studiosaas.workspaces import ensure_tenant_workspace


TENANTS = [
    ("lets-paint-studio", "Let's Paint Studio", "studio", "#312e81", "#6366f1", "Art"),
    ("lets-play-piano", "Let's Play Piano", "starter", "#14532d", "#22c55e", "Music"),
    ("lets-play-game", "Let's Play Game", "growth", "#7c2d12", "#f97316", "Game"),
]

PRESET_META = {
    "Art": {
        "category": "art",
        "slogan": "You deserve to enjoy life more.",
        "registration_profile": {
            "title": "Creative Preferences",
            "fields": [
                {"key": "artStyle", "label": "Preferred style", "placeholder": "Watercolour, sketching, acrylic", "type": "text"},
                {"key": "favArtist", "label": "Favourite artist", "placeholder": "Monet, Van Gogh, Yayoi Kusama", "type": "text"},
                {"key": "goals", "label": "Creative goals", "placeholder": "Relax, build technique, portfolio prep", "type": "text"},
            ],
        },
        "copy_pack": {"portal_label": "Student Art Portal", "register_intro": "Tell us about the student and their creative goals."},
    },
    "Music": {
        "category": "music",
        "slogan": "Every student deserves a rhythm of their own.",
        "registration_profile": {
            "title": "Music Preferences",
            "fields": [
                {"key": "instrument", "label": "Instrument", "placeholder": "Piano, guitar, violin, voice", "type": "text"},
                {"key": "level", "label": "Current level", "placeholder": "Beginner, AMEB Grade 2, self-taught", "type": "text"},
                {"key": "goals", "label": "Learning goals", "placeholder": "Exam prep, performance, confidence", "type": "text"},
            ],
        },
        "copy_pack": {"portal_label": "Music Student Portal", "register_intro": "Tell us about the student and their music goals."},
    },
    "Game": {
        "category": "game",
        "slogan": "Play, think, and level up with purpose.",
        "registration_profile": {
            "title": "Game Learning Goals",
            "fields": [
                {"key": "gameType", "label": "Game type", "placeholder": "Roblox, Minecraft, chess, coding games", "type": "text"},
                {"key": "level", "label": "Current level", "placeholder": "Beginner, casual, competitive", "type": "text"},
                {"key": "goals", "label": "Learning goals", "placeholder": "Strategy, coding, teamwork, confidence", "type": "text"},
            ],
        },
        "copy_pack": {"portal_label": "Game Student Portal", "register_intro": "Tell us about the player and their learning goals."},
    },
}

FIRST_NAMES = [
    "Ava", "Mia", "Lucas", "Leo", "Sophie", "Ethan", "Chloe", "Noah",
    "Olivia", "Henry", "Emily", "Jack", "Grace", "Liam", "Ruby", "Zoe",
]
LAST_NAMES = ["Wang", "Li", "Chen", "Smith", "Brown", "Nguyen", "Patel", "Wilson"]


def ensure_media_schema(conn) -> None:
    """Keep existing demo databases compatible with canonical media assets."""

    with conn.cursor() as cur:
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


def parse_args() -> argparse.Namespace:
    """Parse command-line options for deterministic local seeding."""

    parser = argparse.ArgumentParser(description="Seed random StudioSaaS demo data.")
    parser.add_argument("--students-per-tenant", type=int, default=18)
    parser.add_argument("--seed", type=int, default=20260630)
    parser.add_argument(
        "--only-slug",
        help=(
            "Seed one EXISTING tenant by slug. Keeps the tenant's branding and "
            "existing students/registrations (no demo reset); adds courses, "
            "packages, students, and registrations on top."
        ),
    )
    return parser.parse_args()


# Minimal valid 1x1 JPEG so seeded portfolio metadata has a real file behind
# it (share links and media routes then work end to end).
_PLACEHOLDER_JPEG = __import__("base64").b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRof"
    "Hh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAAB"
    "AAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
)


def _write_placeholder_media(storage_key: str) -> None:
    """Write a tiny JPEG to the local media root for a seeded storage key.

    Mirrors services.media.media_root() without requiring a Flask app
    context: STUDIOSAAS_MEDIA_DIR override, else backend/media.
    """

    root = os.environ.get("STUDIOSAAS_MEDIA_DIR") or str(Path(__file__).resolve().parents[1] / "media")
    parts = [part for part in storage_key.split("/") if part]
    path = Path(root).joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(_PLACEHOLDER_JPEG)


def seed_existing_tenant(conn, rng: random.Random, slug: str, students: int) -> None:
    """Seed demo data into an existing tenant without touching its branding.

    Unlike the configured demo tenants, this path never runs clear_demo_data,
    so manually created records survive re-runs (student upserts are keyed on
    (tenant_id, source_legacy_id) and stay idempotent).
    """

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name,
                   COALESCE(NULLIF(settings->>'category_label', ''),
                            initcap(COALESCE(NULLIF(settings->>'category', ''), 'studio'))) AS category_label
            FROM tenants
            WHERE slug = %s
            """,
            (slug,),
        )
        row = cur.fetchone()
    if not row:
        raise SystemExit(f"Tenant '{slug}' not found. Create it first (Super Admin), then re-run.")

    tenant_id = str(row["id"])
    name = row["name"]
    category_label = row["category_label"]

    ensure_studio_admin(conn, tenant_id, slug, name)
    courses = upsert_courses(conn, tenant_id, category_label)
    upsert_packages(conn, tenant_id, courses)
    for index in range(students):
        upsert_student(conn, rng, tenant_id, index, courses)
    seed_registrations(conn, rng, tenant_id)
    refresh_usage(conn, tenant_id)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, action, resource_type, resource_id, metadata)
            VALUES (%s, 'demo.seeded', 'tenant', %s, %s::jsonb)
            """,
            (tenant_id, tenant_id, '{"script":"seed_random_demo_data.py","mode":"only-slug"}'),
        )
    print(f"Seeded existing tenant '{slug}' ({name}) with {students} students, "
          f"{len(courses)} courses, packages, and registrations. Existing rows kept.")


def upsert_tenant(conn, slug: str, name: str, plan: str, primary: str, secondary: str, category: str) -> str:
    """Create or update a tenant and return its id."""

    workspace_path = ensure_tenant_workspace(PROJECT_ROOT, slug, name)
    preset = PRESET_META[category]
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenants (
                name, slug, status, plan_code, primary_color, secondary_color,
                welcome_message, contact_phone, contact_email, address, timezone, settings
            )
            VALUES (
                %s, %s, 'active', %s, %s, %s, %s, %s, %s, %s,
                'Australia/Melbourne',
                %s::jsonb
            )
            ON CONFLICT (slug) DO UPDATE
            SET name = EXCLUDED.name,
                status = 'active',
                plan_code = EXCLUDED.plan_code,
                primary_color = EXCLUDED.primary_color,
                secondary_color = EXCLUDED.secondary_color,
                welcome_message = EXCLUDED.welcome_message,
                contact_phone = EXCLUDED.contact_phone,
                contact_email = EXCLUDED.contact_email,
                address = EXCLUDED.address,
                settings = tenants.settings || EXCLUDED.settings,
                updated_at = now()
            RETURNING id
            """,
            (
                name,
                slug,
                plan,
                primary,
                secondary,
                f"Welcome to {name}. Book, learn, and grow with our {category.lower()} classes.",
                "0400 123 456",
                f"hello@{slug}.test",
                "12 Studio Lane, Melbourne VIC",
                json.dumps(
                    {
                        "workspace_path": workspace_path,
                        "logo_url": "/logo.png",
                        "category": preset["category"],
                        "category_label": category,
                        "slogan": preset["slogan"],
                        "registration_profile": preset["registration_profile"],
                        "copy_pack": preset["copy_pack"],
                        "owner_name": f"{name} Owner",
                        "owner_role": "Director",
                        "owner_phone": "0400 123 456",
                        "owner_email": f"owner@{slug}.test",
                        "studio_admin_email": f"owner@{slug}.test",
                        "studio_admin_name": f"{name} Owner",
                        "billing_email": f"accounts@{slug}.test",
                        "abn": "12 345 678 901",
                        "website": f"https://{slug}.example.test",
                    }
                ),
            ),
        )
        tenant_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO subscriptions (
                tenant_id, plan_code, status, starts_at, ends_at, trial_ends_at,
                current_period_ends_at
            )
            VALUES (%s, %s, 'active', now() - interval '14 days', NULL, NULL, now() + interval '16 days')
            ON CONFLICT (tenant_id) DO UPDATE
            SET plan_code = EXCLUDED.plan_code,
                status = EXCLUDED.status,
                current_period_ends_at = EXCLUDED.current_period_ends_at,
                updated_at = now()
            """,
            (tenant_id, plan),
        )
    return str(tenant_id)


def ensure_studio_admin(conn, tenant_id: str, slug: str, name: str) -> None:
    """Ensure each demo tenant has a working Studio Admin/CMS owner login."""

    email = f"owner@{slug}.test"
    full_name = f"{name} Owner"
    with conn.cursor() as cur:
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
            (email, hash_password("admin123456"), full_name),
        )
        user_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO memberships (tenant_id, user_id, role, status)
            VALUES (%s, %s, 'owner', 'active')
            ON CONFLICT (tenant_id, user_id) DO UPDATE
            SET role = 'owner', status = 'active'
            """,
            (tenant_id, user_id),
        )
        cur.execute(
            """
            UPDATE tenants
            SET settings = settings || %s::jsonb,
                updated_at = now()
            WHERE id = %s
            """,
            (
                json.dumps({
                    "studio_admin_user_id": str(user_id),
                    "studio_admin_email": email,
                    "studio_admin_name": full_name,
                }),
                tenant_id,
            ),
        )


def upsert_courses(conn, tenant_id: str, category: str) -> list[dict]:
    """Create a small course catalog and return course rows."""

    if category == "Art":
        course_names = ["Foundation Painting", "Creative Drawing", "Portfolio Workshop"]
    elif category == "Music":
        course_names = ["Junior Piano", "Theory Lab", "Performance Workshop"]
    else:
        course_names = ["Game Design Lab", "Creative Coding", "Prototype Workshop"]
    with conn.cursor() as cur:
        for index, name in enumerate(course_names):
            cur.execute(
                """
                INSERT INTO courses (
                    tenant_id, name, description, category, age_range,
                    duration_minutes, credit_unit, default_credit_debit, price_aud_cents
                )
                VALUES (%s, %s, %s, %s, %s, %s, 'credits', %s, %s)
                ON CONFLICT (tenant_id, name) DO UPDATE
                SET description = EXCLUDED.description,
                    category = EXCLUDED.category,
                    age_range = EXCLUDED.age_range,
                    duration_minutes = EXCLUDED.duration_minutes,
                    default_credit_debit = EXCLUDED.default_credit_debit,
                    price_aud_cents = EXCLUDED.price_aud_cents,
                    is_active = true,
                    updated_at = now()
                """,
                (
                    tenant_id,
                    name,
                    f"Demo {category.lower()} course for StudioSaaS testing.",
                    category,
                    "5-12" if index < 2 else "10+",
                    60 if index < 2 else 90,
                    Decimal("1.00") if index < 2 else Decimal("1.50"),
                    4500 if index < 2 else 6800,
                ),
            )
    return fetch_all(conn, "SELECT * FROM courses WHERE tenant_id = %s ORDER BY name", (tenant_id,))


def upsert_packages(conn, tenant_id: str, courses: list[dict]) -> None:
    """Create packages linked to real course ids."""

    package_specs = [("Trial Pack", Decimal("3"), 9900, 30), ("Term Pack", Decimal("10"), 32000, 120), ("Portfolio Pack", Decimal("20"), 60000, 180)]
    with conn.cursor() as cur:
        for index, (name, credits, price, expires) in enumerate(package_specs):
            course = courses[index % len(courses)]
            cur.execute(
                """
                INSERT INTO packages (tenant_id, course_id, name, credits, price_aud_cents, expires_after_days, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, true)
                ON CONFLICT (tenant_id, name) DO UPDATE
                SET course_id = EXCLUDED.course_id,
                    credits = EXCLUDED.credits,
                    price_aud_cents = EXCLUDED.price_aud_cents,
                    expires_after_days = EXCLUDED.expires_after_days,
                    is_active = true
                """,
                (tenant_id, course["id"], name, credits, price, expires),
            )


def clear_demo_data(conn, tenant_id: str) -> None:
    """Reset local demo rows for a tenant while keeping accounts and products."""

    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM registrations
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        cur.execute(
            """
            DELETE FROM students
            WHERE tenant_id = %s
            """,
            (tenant_id,),
        )
        cur.execute(
            """
            DELETE FROM media_assets
            WHERE tenant_id = %s AND asset_type <> 'logo'
            """,
            (tenant_id,),
        )


def upsert_student(conn, rng: random.Random, tenant_id: str, index: int, courses: list[dict]) -> None:
    """Create one student plus related account, transactions, attendance, and portfolio data."""

    first = rng.choice(FIRST_NAMES)
    last = rng.choice(LAST_NAMES)
    display = f"{first} {last}"
    legacy_id = f"demo-{index:03d}"
    mobile = f"04{rng.randint(10_000_000, 99_999_999)}"
    balance = Decimal(str(rng.choice([0, 1, 2, 3, 5, 8, 12, 16])))
    status = rng.choices(["active", "trial", "inactive"], weights=[72, 18, 10], k=1)[0]
    course = rng.choice(courses)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status, birthday,
                parent_name, mobile, email, tags, notes, source_legacy_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::text[], %s, %s)
            ON CONFLICT (tenant_id, source_legacy_id)
            WHERE source_legacy_id IS NOT NULL AND source_legacy_id <> ''
            DO UPDATE
            SET first_name = EXCLUDED.first_name,
                last_name = EXCLUDED.last_name,
                display_name = EXCLUDED.display_name,
                status = EXCLUDED.status,
                birthday = EXCLUDED.birthday,
                parent_name = EXCLUDED.parent_name,
                mobile = EXCLUDED.mobile,
                email = EXCLUDED.email,
                tags = EXCLUDED.tags,
                notes = EXCLUDED.notes,
                updated_at = now()
            RETURNING id
            """,
            (
                tenant_id,
                first,
                last,
                display,
                status,
                date(2014 + rng.randint(0, 7), rng.randint(1, 12), rng.randint(1, 26)),
                f"{rng.choice(FIRST_NAMES)} Parent",
                mobile,
                f"{first.lower()}.{last.lower()}.{index}@example.test",
                ["demo", status],
                "Randomized local test student.",
                legacy_id,
            ),
        )
        student_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance, low_balance_threshold)
            VALUES (%s, %s, %s, %s, 2)
            ON CONFLICT (tenant_id, student_id, course_id) DO UPDATE
            SET balance = EXCLUDED.balance,
                updated_at = now()
            RETURNING id
            """,
            (tenant_id, student_id, course["id"], balance),
        )
        account_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, account_id, transaction_type, amount,
                balance_after, fee_aud_cents, note, occurred_at
            )
            VALUES (%s, %s, %s, 'purchase', %s, %s, %s, 'Demo package purchase', %s)
            RETURNING id
            """,
            (
                tenant_id,
                student_id,
                account_id,
                balance + Decimal("4"),
                balance,
                int((balance + Decimal("4")) * 3200),
                datetime.now(timezone.utc) - timedelta(days=rng.randint(5, 60)),
            ),
        )
        transaction_id = cur.fetchone()["id"]
        cur.execute(
            """
            INSERT INTO attendance_sessions (tenant_id, student_id, course_id, credit_transaction_id, attended_at, note)
            VALUES (%s, %s, %s, %s, %s, 'Demo attended session')
            """,
            (
                tenant_id,
                student_id,
                course["id"],
                transaction_id,
                datetime.now(timezone.utc) - timedelta(days=rng.randint(1, 20)),
            ),
        )
        storage_key = f"demo/{tenant_id}/{legacy_id}.jpg"
        cur.execute(
            """
            INSERT INTO media_assets (
                tenant_id, owner_student_id, asset_type, storage_key, original_filename,
                mime_type, byte_size, visibility
            )
            VALUES (%s, %s, 'portfolio', %s, %s, 'image/jpeg', %s, 'public_token')
            ON CONFLICT (tenant_id, storage_key) DO UPDATE
            SET owner_student_id = EXCLUDED.owner_student_id,
                asset_type = EXCLUDED.asset_type,
                byte_size = EXCLUDED.byte_size
            RETURNING id
            """,
            (tenant_id, student_id, storage_key, f"{legacy_id}.jpg", rng.randint(80_000, 650_000)),
        )
        media_id = cur.fetchone()["id"]
        _write_placeholder_media(storage_key)
        cur.execute(
            """
            INSERT INTO portfolio_items (
                tenant_id, student_id, media_asset_id, title, description,
                artwork_date, visibility
            )
            VALUES (%s, %s, %s, %s, 'Generated demo portfolio item.', %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                tenant_id,
                student_id,
                media_id,
                f"{display}'s Demo Work",
                date.today() - timedelta(days=rng.randint(1, 90)),
                rng.choice(["private", "shared"]),
            ),
        )


def seed_registrations(conn, rng: random.Random, tenant_id: str) -> None:
    """Create pending registration rows for workflow testing."""

    with conn.cursor() as cur:
        for index in range(4):
            first = rng.choice(FIRST_NAMES)
            last = rng.choice(LAST_NAMES)
            cur.execute(
                """
                INSERT INTO registrations (
                    tenant_id, status, first_name, last_name, parent_name,
                    mobile, email, message, payload, submitted_at
                )
                VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    tenant_id,
                    first,
                    last,
                    f"{rng.choice(FIRST_NAMES)} Parent",
                    f"04{rng.randint(10_000_000, 99_999_999)}",
                    f"new.{first.lower()}.{last.lower()}.{index}@example.test",
                    "Interested in a trial class.",
                    '{"source":"random_demo_seed"}',
                    datetime.now(timezone.utc) - timedelta(days=rng.randint(0, 10)),
                ),
            )


def refresh_usage(conn, tenant_id: str) -> None:
    """Recalculate tenant usage counters from relational data."""

    usage = fetch_one(
        conn,
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = %s) AS students,
            (SELECT COALESCE(ceil(sum(byte_size) / 1048576.0), 0) FROM media_assets WHERE tenant_id = %s) AS storage_mb
        """,
        (tenant_id, tenant_id),
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb, calculated_at)
            VALUES (%s, %s, 2, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE
            SET student_count = EXCLUDED.student_count,
                user_count = EXCLUDED.user_count,
                storage_used_mb = EXCLUDED.storage_used_mb,
                calculated_at = now()
            """,
            (tenant_id, usage["students"], usage["storage_mb"]),
        )


def main() -> int:
    """Seed all configured demo tenants."""

    args = parse_args()
    rng = random.Random(args.seed)
    try:
        with connect() as conn:
            ensure_media_schema(conn)
            if args.only_slug:
                seed_existing_tenant(conn, rng, args.only_slug.strip().lower(), args.students_per_tenant)
                conn.commit()
                return 0
            for slug, name, plan, primary, secondary, category in TENANTS:
                tenant_id = upsert_tenant(conn, slug, name, plan, primary, secondary, category)
                ensure_studio_admin(conn, tenant_id, slug, name)
                courses = upsert_courses(conn, tenant_id, category)
                upsert_packages(conn, tenant_id, courses)
                clear_demo_data(conn, tenant_id)
                for index in range(args.students_per_tenant):
                    upsert_student(conn, rng, tenant_id, index, courses)
                seed_registrations(conn, rng, tenant_id)
                refresh_usage(conn, tenant_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO audit_logs (tenant_id, action, resource_type, resource_id, metadata)
                        VALUES (%s, 'demo.seeded', 'tenant', %s, %s::jsonb)
                        """,
                        (tenant_id, tenant_id, '{"script":"seed_random_demo_data.py"}'),
                    )
            conn.commit()
    except DatabaseUnavailableError as exc:
        print(f"Database unavailable: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Demo seed failed: {exc}", file=sys.stderr)
        return 1
    print(f"Seeded {len(TENANTS)} tenants with {args.students_per_tenant} students each.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
