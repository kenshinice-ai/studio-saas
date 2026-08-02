#!/usr/bin/env python3
"""Create or reset the isolated PWE Studio professional showcase tenant.

This script is intentionally narrower than ``seed_random_demo_data.py``:

* it can only touch ``lets-paint-showcase``;
* an existing tenant must carry ``settings.professional_demo = true``;
* it refuses to run in standalone/customer-edition mode;
* it uses fictional contact details and synthetic artwork bundled with the app;
* staff passwords use the configured stable local/Pilot demonstration password;
* the student access code remains separately rotated on each reset;
* credentials are written to a local ``0600`` file, never printed.

The command is destructive only inside the dedicated showcase tenant. It does
not read, update, or copy records from ``lets-paint-studio`` or any customer
tenant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.auth import hash_password
from studiosaas.config import is_standalone
from studiosaas.db import connect
from studiosaas.services.student_access import generate_access_code
from studiosaas.workspaces import ensure_tenant_workspace

SHOWCASE_SLUG = "lets-paint-showcase"
SHOWCASE_NAME = "Let's Paint Studio"
CONFIRMATION = "RESET-LETS-PAINT-SHOWCASE"
DEMO_PASSWORD_ENV = "STUDIOSAAS_SHARED_DEMO_PASSWORD"
ROLE_ACCOUNTS = (
    ("owner", "owner.showcase@pwe-studio.invalid", "Alex Morgan", "Owner"),
    ("manager", "manager.showcase@pwe-studio.invalid", "Jordan Lee", "Studio Manager"),
    ("teacher", "teacher.showcase@pwe-studio.invalid", "Taylor Chen", "Lead Teacher"),
    ("front_desk", "frontdesk.showcase@pwe-studio.invalid", "Casey Nguyen", "Front Desk"),
)
STUDENTS = (
    ("Amelia", "Hart", "Sophie Hart", "0400000101", "family+amelia@example.com", Decimal("8")),
    ("Noah", "Lin", "Grace Lin", "0400000102", "family+noah@example.com", Decimal("3")),
    ("Maya", "Patel", "Rina Patel", "0400000103", "family+maya@example.com", Decimal("12")),
    ("Leo", "Wilson", "Chris Wilson", "0400000104", "family+leo@example.com", Decimal("1")),
    ("Ruby", "Zhang", "Mei Zhang", "0400000105", "family+ruby@example.com", Decimal("6")),
    ("Oscar", "Brown", "Sam Brown", "0400000106", "family+oscar@example.com", Decimal("10")),
    ("Chloe", "Tran", "Linh Tran", "0400000107", "family+chloe@example.com", Decimal("4")),
    ("Ethan", "King", "Morgan King", "0400000108", "family+ethan@example.com", Decimal("2")),
    ("Zoe", "Martin", "Jamie Martin", "0400000109", "family+zoe@example.com", Decimal("9")),
    ("Aria", "Singh", "Priya Singh", "0400000110", "family+aria@example.com", Decimal("5")),
    ("Lucas", "Young", "Robin Young", "0400000111", "family+lucas@example.com", Decimal("7")),
    ("Mia", "Anderson", "Dana Anderson", "0400000112", "family+mia@example.com", Decimal("11")),
)
COURSES = (
    ("Foundation Painting", "Colour, composition and confident mark-making through guided projects.", "Visual Arts", "7–11", 75, 4500),
    ("Creative Drawing", "Observation, imagination and mixed-media drawing for developing artists.", "Drawing", "6–10", 60, 3800),
    ("Portfolio Studio", "A mentored pathway for self-directed work, refinement and presentation.", "Portfolio", "11–16", 90, 6200),
)
ARTWORKS = (
    ("showcase-botanical.png", "Wattle & Eucalyptus", "A warm botanical study exploring transparent layers and quiet contrast."),
    ("showcase-coast.png", "Southern Coast", "Palette-knife textures build distance, weather and a sense of place."),
    ("showcase-cockatoo.png", "Cockatoo Study", "Charcoal observation with restrained pastel accents and confident negative space."),
)


def _parse_args() -> argparse.Namespace:
    """Return explicit destructive confirmation and optional output path."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        required=True,
        help=f"Required exact safety phrase: {CONFIRMATION}",
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help="Override the protected local credential handoff path.",
    )
    return parser.parse_args()


def _credentials_path(explicit: Path | None) -> Path:
    """Resolve the protected credential handoff path."""

    if explicit:
        return explicit.expanduser().resolve()
    configured = os.environ.get("STUDIOSAAS_DEMO_CREDENTIALS_FILE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return Path.home() / ".studiosaas" / "showcase-credentials.txt"


def _write_safe_variant(source: Path, destination: Path, max_size: int) -> tuple[int, str, int, int]:
    """Write a metadata-free, size-bounded PNG derivative and return evidence."""

    try:
        with Image.open(source) as opened:
            image = ImageOps.exif_transpose(opened).convert("RGB")
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            destination.parent.mkdir(parents=True, exist_ok=True)
            image.save(destination, format="PNG", optimize=True)
            width, height = image.size
    except (OSError, ValueError) as exc:
        raise RuntimeError(f"Could not create safe showcase derivative from {source}.") from exc
    payload = destination.read_bytes()
    return len(payload), hashlib.sha256(payload).hexdigest(), width, height


def _refuse_unsafe_context(confirmation: str) -> None:
    """Enforce the mode and exact-target safety boundary."""

    if confirmation != CONFIRMATION:
        raise SystemExit(f"Refusing to reset. --confirm must be exactly: {CONFIRMATION}")
    if is_standalone():
        raise SystemExit(
            "Refusing to reset: STUDIOSAAS_MODE=standalone is a customer edition. "
            "The professional showcase exists only in SaaS mode."
        )


def _load_or_create_tenant(cur: Any) -> str:
    """Create the showcase tenant or validate its permanent safety marker."""

    cur.execute("SELECT id, settings FROM tenants WHERE slug = %s FOR UPDATE", (SHOWCASE_SLUG,))
    existing = cur.fetchone()
    if existing:
        settings = existing["settings"] if isinstance(existing["settings"], dict) else {}
        if settings.get("professional_demo") is not True:
            raise RuntimeError(
                f"Tenant '{SHOWCASE_SLUG}' exists without settings.professional_demo=true. "
                "Refusing to touch it."
            )
        tenant_id = str(existing["id"])
    else:
        cur.execute(
            """
            INSERT INTO tenants (
                name, slug, status, plan_code, primary_color, secondary_color,
                welcome_message, contact_phone, contact_email, address, timezone, settings
            )
            VALUES (
                %s, %s, 'active', 'growth', '#173f3a', '#d7a93d',
                %s, '0400 000 000', 'hello@pwe-studio.invalid',
                'Creative Quarter, Melbourne VIC', 'Australia/Melbourne', %s::jsonb
            )
            RETURNING id
            """,
            (
                SHOWCASE_NAME,
                SHOWCASE_SLUG,
                "A welcoming studio for curious artists, confident skills and work worth keeping.",
                json.dumps({"professional_demo": True}),
            ),
        )
        tenant_id = str(cur.fetchone()["id"])

    workspace_path = ensure_tenant_workspace(PROJECT_ROOT, SHOWCASE_SLUG, SHOWCASE_NAME)
    settings = {
        "professional_demo": True,
        "showcase_version": "8.1.0",
        "demo_data_policy": "fictional-records-and-synthetic-media-only",
        "workspace_path": workspace_path,
        "category": "art",
        "category_label": "Visual Arts",
        "slogan": "Make time to create. Keep the story of every step.",
        "registration_profile": {
            "title": "Creative goals",
            "fields": [
                {"key": "preferredMedium", "label": "Preferred medium", "placeholder": "Drawing, watercolour, acrylic or unsure", "type": "text"},
                {"key": "experience", "label": "Current experience", "placeholder": "New, developing or experienced", "type": "text"},
                {"key": "goals", "label": "What would you like to explore?", "placeholder": "Confidence, technique, portfolio or creative time", "type": "text"},
            ],
        },
        "copy_pack": {
            "portal_label": "Student & Family Studio",
            "register_intro": "Tell us about the student and the kind of creative experience you are looking for.",
        },
        "owner_name": "Alex Morgan",
        "owner_role": "Studio Director",
        "owner_phone": "0400 000 000",
        "owner_email": "owner.showcase@pwe-studio.invalid",
        "studio_admin_email": "owner.showcase@pwe-studio.invalid",
        "studio_admin_name": "Alex Morgan",
        "billing_email": "accounts@pwe-studio.invalid",
        "website": "https://showcase.pwe-studio.invalid",
    }
    cur.execute(
        """
        UPDATE tenants
        SET name = %s, status = 'active', plan_code = 'growth',
            primary_color = '#173f3a', secondary_color = '#d7a93d',
            welcome_message = %s, contact_phone = '0400 000 000',
            contact_email = 'hello@pwe-studio.invalid',
            address = 'Creative Quarter, Melbourne VIC',
            timezone = 'Australia/Melbourne', settings = %s::jsonb, updated_at = now()
        WHERE id = %s
        """,
        (
            SHOWCASE_NAME,
            "A welcoming studio for curious artists, confident skills and work worth keeping.",
            json.dumps(settings),
            tenant_id,
        ),
    )
    return tenant_id


def _clear_showcase(cur: Any, tenant_id: str) -> None:
    """Remove mutable showcase records while retaining the guarded tenant."""

    cur.execute("DELETE FROM registrations WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM class_schedules WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM students WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM media_assets WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM packages WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM courses WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM memberships WHERE tenant_id = %s", (tenant_id,))


def _seed_roles(cur: Any, tenant_id: str, password: str) -> list[dict[str, str]]:
    """Create the four demonstration roles with one stable Pilot password."""

    credentials: list[dict[str, str]] = []
    for role, email, full_name, label in ROLE_ACCOUNTS:
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
            (email, hash_password(password), full_name),
        )
        user_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO memberships (tenant_id, user_id, role, status)
            VALUES (%s, %s, %s, 'active')
            """,
            (tenant_id, user_id, role),
        )
        credentials.append({"role": label, "email": email, "password": password, "user_id": user_id})

    owner = credentials[0]
    cur.execute(
        """
        UPDATE tenants
        SET settings = settings || %s::jsonb, updated_at = now()
        WHERE id = %s
        """,
        (
            json.dumps(
                {
                    "studio_admin_user_id": owner["user_id"],
                    "studio_admin_email": owner["email"],
                    "studio_admin_name": "Alex Morgan",
                }
            ),
            tenant_id,
        ),
    )
    return credentials


def _seed_catalog(cur: Any, tenant_id: str) -> list[str]:
    """Create a credible visual-arts course and package catalogue."""

    course_ids: list[str] = []
    for name, description, category, age_range, duration, price_cents in COURSES:
        cur.execute(
            """
            INSERT INTO courses (
                tenant_id, name, description, category, age_range,
                duration_minutes, credit_unit, default_credit_debit,
                price_aud_cents, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'credits', 1, %s, true)
            RETURNING id
            """,
            (tenant_id, name, description, category, age_range, duration, price_cents),
        )
        course_ids.append(str(cur.fetchone()["id"]))

    packages = (
        (course_ids[0], "First Studio Visit", Decimal("1"), 2500, 30),
        (course_ids[0], "10-Class Studio Pack", Decimal("10"), 42000, 120),
        (course_ids[2], "Portfolio Term", Decimal("12"), 68000, 150),
    )
    for course_id, name, credits, price_cents, expiry in packages:
        cur.execute(
            """
            INSERT INTO packages (
                tenant_id, course_id, name, credits, price_aud_cents,
                expires_after_days, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, true)
            """,
            (tenant_id, course_id, name, credits, price_cents, expiry),
        )
    return course_ids


def _seed_students(cur: Any, tenant_id: str, course_ids: list[str], teacher_id: str) -> list[str]:
    """Create fictional students with balances, transactions and attendance."""

    student_ids: list[str] = []
    today = date.today()
    for index, (first, last, parent, mobile, email, balance) in enumerate(STUDENTS):
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status, birthday,
                enrolled_on, parent_name, mobile, email, tags, notes, source_legacy_id
            )
            VALUES (
                %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s,
                %s::text[], 'Fictional professional showcase record.', %s
            )
            RETURNING id
            """,
            (
                tenant_id,
                first,
                last,
                f"{first} {last}",
                today - timedelta(days=365 * (7 + index % 8) + index * 17),
                today - timedelta(days=38 + index * 8),
                parent,
                mobile,
                email,
                ["term-3", "showcase"],
                f"professional-showcase-{index + 1:03d}",
            ),
        )
        student_id = str(cur.fetchone()["id"])
        student_ids.append(student_id)
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id, balance, low_balance_threshold)
            VALUES (%s, %s, %s, 2)
            RETURNING id
            """,
            (tenant_id, student_id, balance),
        )
        account_id = str(cur.fetchone()["id"])
        purchased = balance + Decimal("4")
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, account_id, actor_user_id,
                transaction_type, amount, balance_after, fee_aud_cents,
                note, occurred_at
            )
            VALUES (%s, %s, %s, %s, 'purchase', %s, %s, 42000,
                    '10-class studio pack recorded by staff.',
                    now() - (%s * interval '1 day'))
            """,
            (tenant_id, student_id, account_id, teacher_id, purchased, purchased, 32 + index),
        )
        for attendance_index in range(4):
            class_date = today - timedelta(days=(attendance_index + 1) * 7 + index % 3)
            cur.execute(
                """
                INSERT INTO credit_transactions (
                    tenant_id, student_id, account_id, actor_user_id,
                    transaction_type, amount, balance_after, note, occurred_at
                )
                VALUES (%s, %s, %s, %s, 'consume', -1, %s,
                        'Class attendance.', %s::date + time '16:30')
                RETURNING id
                """,
                (
                    tenant_id,
                    student_id,
                    account_id,
                    teacher_id,
                    purchased - Decimal(attendance_index + 1),
                    class_date,
                ),
            )
            transaction_id = str(cur.fetchone()["id"])
            cur.execute(
                """
                INSERT INTO attendance_sessions (
                    tenant_id, student_id, course_id, actor_user_id,
                    credit_transaction_id, attended_at, class_date, note
                )
                VALUES (%s, %s, %s, %s, %s, %s::date + time '16:30', %s, 'Weekly class')
                """,
                (
                    tenant_id,
                    student_id,
                    course_ids[index % len(course_ids)],
                    teacher_id,
                    transaction_id,
                    class_date,
                    class_date,
                ),
            )
    return student_ids


def _seed_schedules(cur: Any, tenant_id: str, course_ids: list[str], student_ids: list[str]) -> None:
    """Create three recurring weekly classes with realistic group rosters."""

    specs = (
        (course_ids[1], "Creative Drawing · Junior", 2, "16:00", 60, 10, student_ids[:6]),
        (course_ids[0], "Foundation Painting · Saturday", 6, "10:00", 75, 12, student_ids[4:12]),
        (course_ids[2], "Portfolio Studio · Teen", 4, "17:00", 90, 8, student_ids[7:12]),
    )
    for course_id, label, weekday, start_time, duration, capacity, roster in specs:
        cur.execute(
            """
            INSERT INTO class_schedules (
                tenant_id, course_id, label, weekday, start_time,
                duration_minutes, capacity, is_active
            )
            VALUES (%s, %s, %s, %s, %s::time, %s, %s, true)
            RETURNING id
            """,
            (tenant_id, course_id, label, weekday, start_time, duration, capacity),
        )
        schedule_id = str(cur.fetchone()["id"])
        for student_id in roster:
            cur.execute(
                """
                INSERT INTO class_schedule_students (schedule_id, student_id, tenant_id)
                VALUES (%s, %s, %s)
                """,
                (schedule_id, student_id, tenant_id),
            )


def _seed_registrations(cur: Any, tenant_id: str, manager_id: str) -> None:
    """Create a small enquiry pipeline covering the main sales states."""

    records = (
        ("pending", "Isla", "Moore", "Avery Moore", "0400000201", "family+isla@example.com", "Interested in a Saturday trial.", None),
        ("contacted", "Finn", "Davis", "Riley Davis", "0400000202", "family+finn@example.com", "Would like drawing and confidence building.", 3),
        ("trial_booked", "Lily", "Thomas", "Sky Thomas", "0400000203", "family+lily@example.com", "Trial arranged for the junior drawing class.", 5),
        ("waiting", "Max", "Walker", "Harper Walker", "0400000204", "family+max@example.com", "Waiting for a weekday portfolio place.", 8),
        ("converted", "Evie", "Hall", "Quinn Hall", "0400000205", "family+evie@example.com", "Joined the term program.", None),
    )
    for index, (status, first, last, parent, mobile, email, message, follow_up_days) in enumerate(records):
        cur.execute(
            """
            INSERT INTO registrations (
                tenant_id, status, first_name, last_name, parent_name, mobile,
                email, message, payload, reviewed_by_user_id, reviewed_at,
                review_note, submitted_at, updated_at, source, source_path,
                source_language, next_follow_up_at, converted_at,
                privacy_consent_at, privacy_notice_version
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s,
                %s::jsonb, %s, CASE WHEN %s = 'pending' THEN NULL ELSE now() END,
                %s, now() - (%s * interval '1 day'), now(), 'public_portal',
                %s, 'en',
                CASE
                    WHEN %s::integer IS NULL THEN NULL
                    ELSE now() + (%s::integer * interval '1 day')
                END,
                CASE WHEN %s = 'converted' THEN now() - interval '2 days' ELSE NULL END,
                now() - (%s * interval '1 day'), '2026-07'
            )
            """,
            (
                tenant_id,
                status,
                first,
                last,
                parent,
                mobile,
                email,
                message,
                json.dumps({"preferredMedium": "Drawing and painting", "experience": "Developing", "goals": "Confidence and technique"}),
                manager_id,
                status,
                "Showcase follow-up recorded." if status != "pending" else "",
                index + 1,
                f"/{SHOWCASE_SLUG}/register",
                follow_up_days,
                follow_up_days or 0,
                status,
                index + 1,
            ),
        )


def _seed_artwork(cur: Any, tenant_id: str, student_ids: list[str], owner_id: str) -> None:
    """Copy synthetic artwork into the media store and create safe derivatives."""

    # Not frontend/assets: that directory is served at /assets/<name>, and these
    # three files are seed material no page ever references — 9.2 MB of demo
    # artwork that anyone could download from the public origin.
    source_dir = APP_ROOT / "seed-assets"
    media_root = Path(os.environ.get("STUDIOSAAS_MEDIA_DIR") or APP_ROOT / "media")
    showcase_root = media_root / "showcase" / SHOWCASE_SLUG
    if showcase_root.exists():
        shutil.rmtree(showcase_root)
    showcase_root.mkdir(parents=True, exist_ok=True)

    for index, (filename, title, description) in enumerate(ARTWORKS):
        source = source_dir / filename
        if not source.is_file():
            raise RuntimeError(f"Required synthetic showcase asset is missing: {source}")
        payload = source.read_bytes()
        checksum = hashlib.sha256(payload).hexdigest()
        original_key = f"showcase/{SHOWCASE_SLUG}/original-{filename}"
        display_key = f"showcase/{SHOWCASE_SLUG}/display-{filename}"
        thumb_key = f"showcase/{SHOWCASE_SLUG}/thumb-{filename}"
        original_path = media_root / original_key
        original_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, original_path)
        display_size, display_checksum, display_width, display_height = _write_safe_variant(
            source, media_root / display_key, 1600
        )
        thumb_size, thumb_checksum, thumb_width, thumb_height = _write_safe_variant(
            source, media_root / thumb_key, 480
        )
        student_id = student_ids[index]
        cur.execute(
            """
            INSERT INTO media_assets (
                tenant_id, owner_student_id, asset_type, storage_provider,
                storage_key, original_filename, mime_type, byte_size,
                checksum_sha256, visibility
            )
            VALUES (%s, %s, 'portfolio', 'local', %s, %s, 'image/png', %s, %s, 'private')
            RETURNING id
            """,
            (tenant_id, student_id, original_key, filename, len(payload), checksum),
        )
        media_id = str(cur.fetchone()["id"])
        variants = (
            ("display", display_key, display_size, display_checksum, display_width, display_height),
            ("thumb", thumb_key, thumb_size, thumb_checksum, thumb_width, thumb_height),
        )
        for variant, key, variant_size, variant_checksum, width, height in variants:
            cur.execute(
                """
                INSERT INTO media_variants (
                    tenant_id, media_asset_id, variant, storage_key, mime_type,
                    byte_size, checksum_sha256, pixel_width, pixel_height,
                    metadata_sanitized
                )
                VALUES (%s, %s, %s, %s, 'image/png', %s, %s, %s, %s, true)
                """,
                (tenant_id, media_id, variant, key, variant_size, variant_checksum, width, height),
            )
        cur.execute(
            """
            INSERT INTO portfolio_items (
                tenant_id, student_id, media_asset_id, title, description,
                artwork_date, visibility, public_consent_at,
                public_consent_by_user_id, public_consent_note
            )
            VALUES (
                %s, %s, %s, %s, %s, CURRENT_DATE - (%s * interval '14 days'),
                'shared', now(), %s, 'Fictional showcase student; synthetic artwork approved for the demo.'
            )
            """,
            (tenant_id, student_id, media_id, title, description, index + 1, owner_id),
        )


def _write_credentials(path: Path, credentials: list[dict[str, str]], student_code: str) -> None:
    """Write the presenter handoff with owner-only filesystem permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "PWE Studio v8.1.0 · Professional Showcase",
        f"Tenant: {SHOWCASE_NAME}",
        f"Portal: /{SHOWCASE_SLUG}",
        f"CMS: /{SHOWCASE_SLUG}/cms",
        f"Studio Admin: /{SHOWCASE_SLUG}/studio-admin",
        "",
        "Staff accounts (stable local/Pilot demonstration password):",
    ]
    for item in credentials:
        lines.extend((f"- {item['role']}", f"  Email: {item['email']}", f"  Password: {item['password']}"))
    lines.extend(
        (
            "",
            "Student & family showcase:",
            f"- Student name: {STUDENTS[0][0]} {STUDENTS[0][1]}",
            f"- Access code: {student_code}",
            "",
            "Safety: fictional records and synthetic media only. Do not publish this file.",
        )
    )
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    os.chmod(path, 0o600)


def reset_showcase(credentials_file: Path) -> dict[str, Any]:
    """Reset the showcase in one transaction and return non-secret evidence."""

    password = os.environ.get(DEMO_PASSWORD_ENV, "")
    if len(password) < 12:
        raise RuntimeError(
            f"{DEMO_PASSWORD_ENV} must provide the stable demonstration password "
            "with at least 12 characters."
        )
    with connect(statement_timeout_ms=0, lock_timeout_ms=0) as conn:
        with conn.cursor() as cur:
            tenant_id = _load_or_create_tenant(cur)
            _clear_showcase(cur, tenant_id)
            credentials = _seed_roles(cur, tenant_id, password)
            course_ids = _seed_catalog(cur, tenant_id)
            teacher_id = next(item["user_id"] for item in credentials if item["role"] == "Lead Teacher")
            manager_id = next(item["user_id"] for item in credentials if item["role"] == "Studio Manager")
            owner_id = next(item["user_id"] for item in credentials if item["role"] == "Owner")
            student_ids = _seed_students(cur, tenant_id, course_ids, teacher_id)
            _seed_schedules(cur, tenant_id, course_ids, student_ids)
            _seed_registrations(cur, tenant_id, manager_id)
            _seed_artwork(cur, tenant_id, student_ids, owner_id)
            student_code, _ = generate_access_code(conn, tenant_id=tenant_id, student_id=student_ids[0])
            cur.execute(
                """
                INSERT INTO subscriptions (tenant_id, plan_code, status, starts_at, current_period_ends_at)
                VALUES (%s, 'growth', 'active', now(), now() + interval '1 year')
                ON CONFLICT (tenant_id) DO UPDATE
                SET plan_code = 'growth', status = 'active',
                    current_period_ends_at = EXCLUDED.current_period_ends_at,
                    updated_at = now()
                """,
                (tenant_id,),
            )
            cur.execute(
                """
                INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb)
                VALUES (%s, %s, %s, 12)
                ON CONFLICT (tenant_id) DO UPDATE
                SET student_count = EXCLUDED.student_count,
                    user_count = EXCLUDED.user_count,
                    storage_used_mb = EXCLUDED.storage_used_mb,
                    calculated_at = now()
                """,
                (tenant_id, len(student_ids), len(credentials)),
            )
            cur.execute(
                """
                INSERT INTO audit_logs (
                    tenant_id, actor_user_id, action, resource_type, resource_id, metadata
                )
                VALUES (%s, %s, 'professional_showcase.reset', 'tenant', %s, %s::jsonb)
                """,
                (
                    tenant_id,
                    owner_id,
                    tenant_id,
                    json.dumps(
                        {
                            "version": "8.1.0",
                            "students": len(student_ids),
                            "schedules": 3,
                            "synthetic_artworks": len(ARTWORKS),
                        }
                    ),
                ),
            )
        conn.commit()
    _write_credentials(credentials_file, credentials, student_code)
    return {
        "tenant_id": tenant_id,
        "students": len(student_ids),
        "roles": len(credentials),
        "schedules": 3,
        "artworks": len(ARTWORKS),
        "credentials_file": str(credentials_file),
    }


def main() -> int:
    """Run the guarded reset and print only non-secret acceptance evidence."""

    args = _parse_args()
    _refuse_unsafe_context(args.confirm)
    credentials_file = _credentials_path(args.credentials_file)
    result = reset_showcase(credentials_file)
    print(f"Professional showcase ready: /{SHOWCASE_SLUG}")
    print(
        "Created "
        f"{result['students']} students, {result['roles']} roles, "
        f"{result['schedules']} schedules and {result['artworks']} synthetic artworks."
    )
    print(f"Protected presenter credentials: {result['credentials_file']} (mode 0600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
