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

── What changed in v9.9.2 ─────────────────────────────────────────────────

Until now this script seeded the CMS side — courses, students, attendance,
enquiries — and left the PORTAL side to whoever typed into the console last.
That is exactly what the public page showed: works titled ``Test`` and
``fasd``, no principal, no room, no categories. A demonstration tenant whose
front page is unseeded is not a demonstration of anything.

So the seeder now owns both halves, and everything it says lives in
``showcase_content.py`` and ``seed-assets/showcase/manifest.json`` rather than
in literals scattered through this file. Three consequences worth knowing:

* images go in through ``store_media_asset`` — the same call the browser
  upload uses — so quotas, derivatives, checksums and metadata stripping are
  the real ones rather than a seed-only shortcut;
* showcase categories are DERIVED from the works that exist, so the portal can
  never render a filter button with nothing behind it;
* the tenant runs the ``studio`` plan, because the point of a showcase is to
  show what a studio of this size actually buys.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import shutil
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from flask import has_app_context
from werkzeug.datastructures import FileStorage

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))
if str(APP_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(APP_ROOT / "scripts"))

import showcase_content as content  # noqa: E402

from studiosaas.auth import hash_password  # noqa: E402
from studiosaas.config import is_standalone  # noqa: E402
from studiosaas.db import connect  # noqa: E402
from studiosaas.services.media import store_media_asset  # noqa: E402
from studiosaas.services.billing import (  # noqa: E402
    SNAPSHOT_SCHEMA_VERSION, recipient_snapshot, supplier_snapshot)
from studiosaas.services.student_access import generate_access_code  # noqa: E402
from studiosaas.workspaces import ensure_tenant_workspace  # noqa: E402

DEMO_PASSWORD_ENV = "STUDIOSAAS_SHARED_DEMO_PASSWORD"
SEED_ASSETS = APP_ROOT / "seed-assets"

#: The demonstration packs. Adding an industry is a row here plus its two files
#: — a content module and a manifest beside its images. No branch below knows
#: which industry it is seeding.
#:
#: The confirmation phrase names its own tenant on purpose: an operator who
#: typed RESET-LETS-PAINT-SHOWCASE while looking at the music studio should be
#: refused, not obeyed.
PACKS: dict[str, dict[str, str]] = {
    "art": {
        "module": "showcase_content",
        "assets": "showcase",
        "confirm": "RESET-LETS-PAINT-SHOWCASE",
        "credentials": "showcase-credentials.txt",
    },
    "music": {
        "module": "music_showcase_content",
        "assets": "music-showcase",
        "confirm": "RESET-MUSIC-STUDIO-SHOWCASE",
        "credentials": "music-showcase-credentials.txt",
    },
}
DEFAULT_PACK = "art"

# Rebound by _select_pack() before anything is written. They start on the art
# pack so that importing this module behaves exactly as it always did.
PACK = DEFAULT_PACK
SHOWCASE_SLUG = content.SLUG
SHOWCASE_NAME = content.NAME
CONFIRMATION = PACKS[DEFAULT_PACK]["confirm"]
MANIFEST = SEED_ASSETS / PACKS[DEFAULT_PACK]["assets"] / "manifest.json"
CREDENTIALS_NAME = PACKS[DEFAULT_PACK]["credentials"]


def _birthday(today: date, age_years: int, month_day: str) -> date:
    """某人今天 `age_years` 岁、生日是 MM-DD，求其出生日期。

    包里存的是「这个人在演示里几岁」而不是出生年份：存年份的夹具每过一个月
    就老一个月，迟早和他所报课程的 age_range 打架。只有月-日是固定的，
    这也正是让整份名册的生日铺满全年、而不是挤在播种当天的那一半。
    """

    month, day = (int(part) for part in month_day.split("-"))
    year = today.year - age_years
    if (month, day) > (today.month, today.day):
        # 今年的生日还没到，所以他是去年生日那天满的这个岁数。
        year -= 1
    return date(year, month, day)


def pack_for_slug(slug: str) -> str | None:
    """Which pack owns this tenant slug, or None if no demonstration pack does.

    Public because the Platform Admin reset button needs it: the tenant decides
    which pack runs, never the other way round.
    """

    for name, spec in PACKS.items():
        module = importlib.import_module(spec["module"])
        if getattr(module, "SLUG", None) == slug:
            return name
    return None


def confirmation_for_pack(name: str) -> str:
    """The exact phrase that authorises resetting this pack's studio."""

    if name not in PACKS:
        raise KeyError(name)
    return PACKS[name]["confirm"]


def _select_pack(name: str) -> None:
    """Point the module at one pack, once, before anything is written."""

    global PACK, content, SHOWCASE_SLUG, SHOWCASE_NAME, CONFIRMATION
    global MANIFEST, CREDENTIALS_NAME

    if name not in PACKS:
        raise SystemExit(f"Unknown demonstration pack: {name}. Known: {', '.join(PACKS)}")
    spec = PACKS[name]
    try:
        module = importlib.import_module(spec["module"])
    except ModuleNotFoundError as exc:
        raise SystemExit(
            f"Pack '{name}' has no content module: scripts/{spec['module']}.py is "
            f"missing ({exc}). A pack is that file plus "
            f"seed-assets/{spec['assets']}/manifest.json beside its images."
        ) from None
    required = ("SLUG", "NAME", "PLAN_CODE", "PAYERS", "INVOICE_PLAN",
                "ROOM_NAMES", "PROGRESS_REPORTS", "PAYMENT_NOTE",
                "BILLING_LINKS", "ATTENDANCE_COURSE_INDEX",
                "REGISTRATION_ANSWERS",
                "SEO_TAGLINE",
                "BILLING_IDENTITY", "INVOICE_PREFIX", "STUDENT_BIRTHDAYS",
                "CREDIT_PURCHASE", "TEACHER_PAY")
    missing = [n for n in required if not hasattr(module, n)]
    if missing:
        raise SystemExit(
            f"Pack '{name}' module {spec['module']} is missing: {', '.join(missing)}"
        )
    PACK = name
    content = module
    SHOWCASE_SLUG = module.SLUG
    SHOWCASE_NAME = module.NAME
    CONFIRMATION = spec["confirm"]
    MANIFEST = SEED_ASSETS / spec["assets"] / "manifest.json"
    CREDENTIALS_NAME = spec["credentials"]


# ── plumbing ───────────────────────────────────────────────────────────────


def _parse_args() -> argparse.Namespace:
    """Return explicit destructive confirmation and optional output path."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pack",
        default=DEFAULT_PACK,
        choices=sorted(PACKS),
        help="Which demonstration studio to reset.",
    )
    parser.add_argument(
        "--confirm",
        required=True,
        help="Required exact safety phrase; each pack has its own, naming its tenant.",
    )
    parser.add_argument(
        "--credentials-file",
        type=Path,
        help="Override the protected local credential handoff path.",
    )
    return parser.parse_args()


def _credentials_path(explicit: Path | None) -> Path:
    """Resolve the protected credential handoff path for the ACTIVE pack.

    The environment variable names a location, and the pack names the file
    inside it. It was written when one demonstration studio existed and so it
    named a file outright — which, with two packs, means resetting the music
    studio writes its credentials over the art studio's file. Production sets
    it to `/data/showcase-credentials.txt`, so taking the directory from it and
    the filename from the pack leaves the art path byte-for-byte what it was
    and gives music its own sibling.

    An explicit `--credentials-file` still wins outright: that one is a person
    naming a path for this run.
    """

    if explicit:
        return explicit.expanduser().resolve()
    configured = os.environ.get("STUDIOSAAS_DEMO_CREDENTIALS_FILE", "").strip()
    if configured:
        return Path(configured).expanduser().resolve().parent / CREDENTIALS_NAME
    return Path.home() / ".studiosaas" / CREDENTIALS_NAME


def _refuse_unsafe_context(confirmation: str) -> None:
    """Enforce the mode and exact-target safety boundary."""

    if confirmation != CONFIRMATION:
        raise SystemExit(f"Refusing to reset. --confirm must be exactly: {CONFIRMATION}")
    if is_standalone():
        raise SystemExit(
            "Refusing to reset: STUDIOSAAS_MODE=standalone is a customer edition. "
            "The professional showcase exists only in SaaS mode."
        )


def _app_version() -> str:
    """The shipping version, read rather than typed."""

    return (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()


def _manifest() -> dict:
    """The artwork manifest, or a clear failure naming the missing file."""

    if not MANIFEST.is_file():
        raise RuntimeError(
            f"Demonstration manifest is missing for pack '{PACK}': {MANIFEST}"
        )
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _upload(conn: Any, tenant_id: str, relative_path: str, kind: str) -> str:
    """Put one bundled seed image through the real upload path and return its id.

    Deliberately ``store_media_asset`` rather than hand-written INSERTs. A seed
    that writes its own rows is a seed that can produce a tenant the product
    could not have produced — different derivative sizes, no quota accounting,
    a checksum nobody computed the same way — and the first time the demo
    behaves unlike the product, the demo is what gets believed.
    """

    source = SEED_ASSETS / relative_path
    if not source.is_file():
        raise RuntimeError(f"Required seed image is missing: {source}")
    payload = source.read_bytes()
    stored = store_media_asset(
        conn,
        tenant_id=tenant_id,
        file_storage=FileStorage(stream=io.BytesIO(payload), filename=source.name),
        kind=kind,
    )
    return str(stored["id"])


def _public_media_url(media_id: str) -> str:
    """The address the portal will ask for. Built once, here."""

    return f"/v1/public/{SHOWCASE_SLUG}/media/{media_id}"


# ── the tenant record ──────────────────────────────────────────────────────


def _settings(manifest: dict, media: dict) -> dict:
    """Assemble everything the portal reads, from the content module.

    This is the object the previous version of this script did not write. Every
    key here corresponds to something a visitor sees; a missing one is a
    section that the public-surface contract switches off for lack of content.
    """

    return {
        "professional_demo": True,
        "showcase_version": _app_version(),
        "demo_data_policy": "fictional-records-and-synthetic-media-only",
        "category": content.IDENTITY["category"],
        "slogan": content.SLOGAN["zh"],
        "localized_copy": content.LOCALIZED_COPY,
        "registration_profile": content.REGISTRATION_PROFILE,
        "copy_pack": content.COPY_PACK,
        "visual_theme": content.VISUAL_THEME,
        "faq_items": [
            {"question": item["question"], "answer": item["answer"]}
            for item in content.FAQ
        ],
        "hero_profile": {
            "eyebrow": content.IDENTITY["address"],
            "title": content.SLOGAN["en"],
            "subtitle": content.LOCALIZED_COPY["hero_subtitle"]["en"],
            "primary_cta_label": content.LOCALIZED_COPY["primary_cta"]["en"],
            "secondary_cta_label": content.LOCALIZED_COPY["secondary_cta"]["en"],
            # Named, not `auto`. The second button is the one that sends a
            # visitor to the studio's own work, and letting the resolver guess
            # means the most important link on the page moves when an unrelated
            # section is switched on.
            "secondary_cta_target": "showcase",
            "show_student_login": True,
            # `image` only when there IS one. Choosing the style that shows a
            # photo and then not supplying the photo is how a hero ends up as
            # an empty organic blob — the failure this pairing exists to stop.
            "background_style": "image" if media.get("hero") else "soft",
            "hero_shape": "organic",
            "hero_image_url": media.get("hero", ""),
        },
        "principal_profile": {**content.PRINCIPAL, "image_url": media.get("principal", "")},
        "owner_name": content.PRINCIPAL["name"],
        "owner_role": content.PRINCIPAL["title"],
        "owner_phone": content.IDENTITY["contact_phone"],
        "owner_email": content.ROLE_ACCOUNTS[0][1],
        "studio_admin_email": content.ROLE_ACCOUNTS[0][1],
        "studio_admin_name": content.PRINCIPAL["name"],
        "billing_email": content.IDENTITY["billing_email"],
        "website": content.IDENTITY["website"],
    }


def _website_profile(
    categories: list[dict], works: list[dict], has_students: bool, room: list[dict]
) -> dict:
    """Section visibility and content for the public pages.

    ``show_gallery`` follows whether student work actually exists. The contract
    would hide an empty section anyway, but leaving the switch on and the
    section empty means the Studio Admin shows a studio a green switch beside
    the words "nothing published" — which is the exact contradiction v9.9.1 was
    spent fixing.
    """

    return {
        "show_principal": True,
        "show_courses": True,
        "show_gallery": has_students,
        "show_faq": True,
        "show_contact": True,
        "show_student_area": True,
        "courses_label": content.LOCALIZED_COPY["courses_label"]["en"],
        "gallery_label": content.LOCALIZED_COPY["gallery_label"]["en"],
        "faq_label": content.LOCALIZED_COPY["faq_label"]["en"],
        "contact_label": content.LOCALIZED_COPY["contact_label"]["en"],
        "seo_title": {
            "zh": f"{SHOWCASE_NAME} · {content.SEO_TAGLINE['zh']}",
            "en": f"{SHOWCASE_NAME} — {content.SEO_TAGLINE['en']}",
        },
        "seo_description": content.LOCALIZED_COPY["hero_subtitle"],
        "show_about": True,
        # Six is the server's ceiling and the section is built for manual
        # selection, not an autoplay carousel — a visitor decides which wall
        # of the room they want to look at.
        "about_images": [item["url"] for item in room],
        "about_image_alts": [item["alt"] for item in room],
        "about_eyebrow": content.ABOUT["eyebrow"],
        "about_title": content.ABOUT["title"],
        "about_body": content.ABOUT["body"],
        "about_items": content.ABOUT["items"],
        "show_showcase": bool(works),
        "showcase_label": content.SHOWCASE_SECTION["label"],
        "showcase_title": content.SHOWCASE_SECTION["title"],
        "showcase_lead": content.SHOWCASE_SECTION["lead"],
        "showcase_categories": categories,
        "showcase_items": works,
        "show_timetable": True,
        "timetable_weeks": 2,
        "timetable_fields": {
            "teacher": True,
            "room": True,
            "age_range": True,
            "duration": True,
            "capacity": True,
            # A timetable is a schedule. Money has a section of its own.
            "price": False,
        },
        "timetable_label": content.TIMETABLE_SECTION["label"],
        "timetable_lead": content.TIMETABLE_SECTION["lead"],
        "show_timetable_booking": True,
    }


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
        return str(existing["id"])
    cur.execute(
        """
        INSERT INTO tenants (
            name, slug, status, plan_code, primary_color, secondary_color,
            welcome_message, contact_phone, contact_email, address, timezone, settings
        )
        VALUES (%s, %s, 'active', %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        RETURNING id
        """,
        (
            SHOWCASE_NAME,
            SHOWCASE_SLUG,
            content.PLAN_CODE,
            content.IDENTITY["primary_color"],
            content.IDENTITY["secondary_color"],
            content.LOCALIZED_COPY["welcome_message"]["en"],
            content.IDENTITY["contact_phone"],
            content.IDENTITY["contact_email"],
            content.IDENTITY["address"],
            content.IDENTITY["timezone"],
            json.dumps({"professional_demo": True}),
        ),
    )
    return str(cur.fetchone()["id"])


def _publish_tenant(cur: Any, tenant_id: str, settings: dict) -> None:
    """Write the assembled settings and refresh the filesystem workspace."""

    head = {
        "title": settings["website_profile"]["seo_title"]["en"],
        "description": settings["website_profile"]["seo_description"]["en"],
    }
    workspace_path = ensure_tenant_workspace(PROJECT_ROOT, SHOWCASE_SLUG, SHOWCASE_NAME, head=head)
    settings = {**settings, "workspace_path": workspace_path}
    cur.execute(
        """
        UPDATE tenants
        SET name = %s, status = 'active', plan_code = %s,
            primary_color = %s, secondary_color = %s,
            welcome_message = %s, contact_phone = %s, contact_email = %s,
            address = %s, timezone = %s, settings = %s::jsonb, updated_at = now()
        WHERE id = %s
        """,
        (
            SHOWCASE_NAME,
            content.PLAN_CODE,
            content.IDENTITY["primary_color"],
            content.IDENTITY["secondary_color"],
            content.LOCALIZED_COPY["welcome_message"]["en"],
            content.IDENTITY["contact_phone"],
            content.IDENTITY["contact_email"],
            content.IDENTITY["address"],
            content.IDENTITY["timezone"],
            json.dumps(settings),
            tenant_id,
        ),
    )


def _clear_showcase(cur: Any, tenant_id: str) -> None:
    """Remove mutable showcase records while retaining the guarded tenant."""

    # 重置是销毁重建，不是编辑，所以和彻底删除租户走同一条声明。没有它，
    # 上一次演示留下的已开具发票会让整个重置失败 —— 而失败发生在清理阶段，
    # 也就是演示租户被清空之后、重新填满之前。
    cur.execute("SET LOCAL studiosaas.purging = 'on'")
    # v10.1.1：钱这一层的表也要清。漏掉任何一张，每次重置就在上一批演示
    # 发票上再叠一批，几周之后演示租户的应收账款是个越滚越大的假数字。
    # 顺序按外键倒着来：分配 → 收款 → 行 → 单据。
    for table in ("payment_allocations", "refunds", "payments", "credit_note_lines",
                  "credit_notes", "invoice_lines", "invoices",
                  "billing_account_members", "billing_accounts",
                  "document_number_sequences", "tenant_billing_identity",
                  "teaching_sessions", "teacher_pay_adjustments", "teacher_pay_periods",
                  "teacher_pay_rates", "teacher_engagements",
                  "makeup_credits", "lesson_exceptions", "lesson_series",
                  "term_closures", "terms", "scheduling_policies",
                  "progress_reports", "progress_report_settings",
                  # 集成侧的痕迹也要清。发票在上面几行已经删了，而
                  # xero_object_links / integration_sync_jobs 是按 local_id
                  # 指向它们的——不清就会留下一批指向不存在单据的链接和
                  # 永远排不出去的作业。映射与网关进度同理：它们是针对
                  # 那一批单据验过的，单据没了，结论也就不成立了。
                  "xero_object_links", "integration_sync_jobs",
                  "xero_account_mappings", "xero_sync_settings",
                  "xero_connections", "tenant_addons"):
        cur.execute(f"DELETE FROM {table} WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM class_bookings WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM class_schedule_exceptions WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM registrations WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM class_schedules WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM students WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM media_assets WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM packages WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM courses WHERE tenant_id = %s", (tenant_id,))
    cur.execute("DELETE FROM memberships WHERE tenant_id = %s", (tenant_id,))
    # Media rows are gone; the files they named have to go with them, or every
    # reset leaves another 12 MB of orphans behind on the disk it is measuring.
    media_root = Path(os.environ.get("STUDIOSAAS_MEDIA_DIR") or APP_ROOT / "media")
    for stale in (media_root / str(tenant_id), media_root / "showcase" / SHOWCASE_SLUG):
        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)


# ── people ─────────────────────────────────────────────────────────────────


def _seed_roles(cur: Any, tenant_id: str, password: str) -> list[dict[str, str]]:
    """Create the four demonstration roles with one stable Pilot password.

    Two of the four consent to appear on the public timetable. That ratio is
    the demonstration: a seed where everybody is public shows nothing about a
    switch whose entire design is that it defaults to off.
    """

    credentials: list[dict[str, str]] = []
    for role, email, full_name, label, public_name, on_timetable in content.ROLE_ACCOUNTS:
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
            INSERT INTO memberships (
                tenant_id, user_id, role, status,
                public_display_name, show_on_public_timetable
            )
            VALUES (%s, %s, %s, 'active', %s, %s)
            """,
            (tenant_id, user_id, role, public_name, on_timetable),
        )
        credentials.append({
            "role": label, "email": email, "password": password,
            "user_id": user_id, "key": role,
        })
    return credentials


def _seed_students(cur: Any, tenant_id: str, course_ids: list[str], teacher_id: str) -> list[str]:
    """Create fictional students with balances, transactions and attendance."""

    student_ids: list[str] = []
    today = date.today()
    for index, (first, last, parent, mobile, email, balance) in enumerate(content.STUDENTS):
        is_child = index >= content.ADULT_COUNT
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
                # 生日来自内容包，不再由 index 推。`today - 365 * N` 必然
                # 落回今天附近，会让整份名册的生日挤在同一周；而按 index 算
                # 出来的年龄也保证不了学员落在他所排课程的 age_range 内。
                _birthday(today, *content.STUDENT_BIRTHDAYS[index]),
                today - timedelta(days=38 + index * 8),
                parent,
                mobile,
                email,
                ["term-3", "kids" if is_child else "adults"],
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
            VALUES (%s, %s, %s, %s, 'purchase', %s, %s, %s,
                    %s,
                    now() - (%s * interval '1 day'))
            """,
            (tenant_id, student_id, account_id, teacher_id, purchased, purchased,
             content.CREDIT_PURCHASE["fee_cents"], content.CREDIT_PURCHASE["note"],
             32 + index),
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
                        'Class attendance.', %s::date + time '18:30')
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
                VALUES (%s, %s, %s, %s, %s, %s::date + time '18:30', %s, 'Weekly class')
                """,
                (
                    tenant_id,
                    student_id,
                    course_ids[content.ATTENDANCE_COURSE_INDEX[index]],
                    teacher_id,
                    transaction_id,
                    class_date,
                    class_date,
                ),
            )
    return student_ids


# ── the money layer ────────────────────────────────────────────────────────
#
# The showcase exists to be walked through with a prospect, and until v10.1.1
# every money screen in it was empty. An empty invoice list does not read as
# "you have not billed anyone yet" — it reads as "this part is not finished".
#
# So the seed puts a term's worth of plausible history in: invoices in every
# state a studio actually sees, a teacher's pay period mid-flight, a private
# lesson with a real cancellation behind it, and progress reports both
# published and overdue. Dates are relative to the reset, so the demo is never
# showing last year.


def _seed_money_layer(
    cur: Any, tenant_id: str, student_ids: list[str], by_role: dict[str, str]
) -> dict[str, int]:
    """Billing, teacher pay, private lessons and reports, ready to show."""

    today = date.today()
    owner_id, teacher_id = by_role["owner"], by_role["teacher"]

    # ── who is issuing ────────────────────────────────────────────────
    # Without this the demo cannot issue a single invoice: billing.issue_invoice
    # refuses a GST document with no supplier ABN. Seeding it is not decoration,
    # it is the precondition.
    cur.execute(
        """
        INSERT INTO tenant_billing_identity
            (tenant_id, legal_name, trading_name, abn, gst_registered,
             address_line1, suburb, state, postcode,
             contact_email, contact_phone,
             bank_account_name, bank_bsb, bank_account_no, payment_note)
        VALUES (%s, %s, %s, %s, true, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id) DO UPDATE SET
            legal_name = EXCLUDED.legal_name, abn = EXCLUDED.abn,
            gst_registered = EXCLUDED.gst_registered, updated_at = now()
        """,
        (tenant_id,
         content.BILLING_IDENTITY["legal_name"],
         content.BILLING_IDENTITY["trading_name"],
         content.BILLING_IDENTITY["abn"],
         content.BILLING_IDENTITY["address_line1"],
         content.BILLING_IDENTITY["suburb"],
         content.BILLING_IDENTITY["state"],
         content.BILLING_IDENTITY["postcode"],
         content.BILLING_IDENTITY["contact_email"],
         content.BILLING_IDENTITY["contact_phone"],
         content.BILLING_IDENTITY["bank_account_name"],
         content.BILLING_IDENTITY["bank_bsb"],
         content.BILLING_IDENTITY["bank_account_no"],
         content.PAYMENT_NOTE),
    )

    # ── the payers ────────────────────────────────────────────────────
    # A family with two children on one invoice is the case that makes the
    # payer/student split worth explaining, so the demo has one.
    payers = content.PAYERS
    account_ids: list[str] = []
    for name, kind, contact, email, mobile, terms in payers:
        cur.execute(
            """
            INSERT INTO billing_accounts
                (tenant_id, name, kind, contact_name, email, mobile, payment_terms_days)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (tenant_id, name, kind, contact, email, mobile, terms),
        )
        account_ids.append(str(cur.fetchone()["id"]))

    # Which students share an account is a fact about the pack's roster, not
    # about billing: the seeder cannot know that two of these surnames are
    # siblings. Putting a pair of them on one account is what makes "one
    # invoice, two children" demonstrable, so every pack is expected to have one.
    for account_index, student_index in content.BILLING_LINKS:
        if student_index < len(student_ids):
            cur.execute(
                """
                INSERT INTO billing_account_members (tenant_id, billing_account_id, student_id)
                VALUES (%s, %s, %s) ON CONFLICT DO NOTHING
                """,
                (tenant_id, account_ids[account_index], student_ids[student_index]),
            )

    # ── the invoices ──────────────────────────────────────────────────
    # Every state a studio meets: paid, part paid, overdue, and a draft still
    # waiting for the front desk. A list showing only one state teaches nothing
    # about what the screen does.
    def _line(invoice_id: str, description: str, qty: str, unit_cents: int,
              tax_bp: int, kind: str, student_id: str | None = None) -> int:
        net = int(Decimal(qty) * Decimal(unit_cents))
        tax = int((Decimal(net) * Decimal(tax_bp) / Decimal(10000)).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP))
        cur.execute(
            """
            INSERT INTO invoice_lines
                (tenant_id, invoice_id, description, quantity, unit_price_cents,
                 tax_rate_bp, tax_cents, total_cents, source_kind, student_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (tenant_id, invoice_id, description, Decimal(qty), unit_cents,
             tax_bp, tax, net + tax, kind, student_id),
        )
        return net + tax

    def _document_number(sequence: list[int]) -> str:
        sequence[0] += 1
        return f"{content.INVOICE_PREFIX}{sequence[0]:04d}"

    # 0043 forbids a non-draft document with empty snapshots — the same rule
    # the real issue route enforces. Built with the SAME functions it uses, so
    # this seeder can never define a second snapshot shape. The dict mirrors
    # the identity INSERT above; reading it back would also work, but the
    # cursor here is mid-transaction and the values are these by construction.
    supplier = supplier_snapshot({
        "configured": True,
        **content.BILLING_IDENTITY,
        "payment_note": content.PAYMENT_NOTE,
    })
    recipients = [
        recipient_snapshot({
            "name": name, "kind": kind, "contact_name": contact,
            "email": email, "mobile": mobile, "payment_terms_days": terms,
        })
        for name, kind, contact, email, mobile, terms in payers
    ]

    counter = [0]
    invoices: list[tuple[str, int, str]] = []   # (id, total, status)
    plan = content.INVOICE_PLAN
    for account_index, days_ago, status, lines in plan:
        cur.execute(
            "INSERT INTO invoices (tenant_id, billing_account_id) VALUES (%s, %s) RETURNING id",
            (tenant_id, account_ids[account_index]),
        )
        invoice_id = str(cur.fetchone()["id"])
        total = sum(_line(invoice_id, *line) for line in lines)
        subtotal = int(Decimal(total) / Decimal("1.1"))
        if status == "draft":
            cur.execute(
                "UPDATE invoices SET subtotal_cents = %s, tax_cents = %s, total_cents = %s "
                "WHERE id = %s",
                (subtotal, total - subtotal, total, invoice_id),
            )
        else:
            issued_on = today - timedelta(days=days_ago)
            terms = payers[account_index][5]
            cur.execute(
                """
                UPDATE invoices
                   SET status = 'issued', number = %s, issue_date = %s, due_date = %s,
                       issued_at = now(), issued_by_user_id = %s,
                       subtotal_cents = %s, tax_cents = %s, total_cents = %s,
                       supplier_snapshot = %s::jsonb, recipient_snapshot = %s::jsonb,
                       snapshot_schema_version = %s
                 WHERE id = %s
                """,
                (_document_number(counter), issued_on, issued_on + timedelta(days=terms),
                 owner_id, subtotal, total - subtotal, total,
                 json.dumps(supplier, ensure_ascii=False),
                 json.dumps(recipients[account_index], ensure_ascii=False),
                 SNAPSHOT_SCHEMA_VERSION, invoice_id),
            )
        invoices.append((invoice_id, total, status))

    # The counter row has to agree with the numbers already handed out, or the
    # first invoice a visitor issues collides with a seeded one.
    cur.execute(
        """
        INSERT INTO document_number_sequences (tenant_id, kind, prefix, next_value)
        VALUES (%s, 'invoice', %s, %s)
        ON CONFLICT (tenant_id, kind) DO UPDATE SET next_value = EXCLUDED.next_value
        """,
        (tenant_id, content.INVOICE_PREFIX, counter[0] + 1),
    )

    # ── the money that arrived ────────────────────────────────────────
    # Allocations drive the invoice status through triggers, so the demo's
    # "paid" and "part paid" rows are true rather than typed in.
    for index, (invoice_id, total, status) in enumerate(invoices):
        if status not in {"paid", "part_paid"}:
            continue
        amount = total if status == "paid" else total // 2
        cur.execute(
            """
            INSERT INTO payments
                (tenant_id, billing_account_id, amount_cents, method, received_at,
                 note, recorded_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
            """,
            (tenant_id, account_ids[0 if index == 0 else 1], amount,
             "bank_transfer" if index == 0 else "card",
             today - timedelta(days=7 * (index + 1)),
             f"演示收款 DEMO-{index + 1:03d}", owner_id),
        )
        payment_id = str(cur.fetchone()["id"])
        cur.execute(
            """
            INSERT INTO payment_allocations
                (tenant_id, payment_id, invoice_id, amount_cents)
            VALUES (%s, %s, %s, %s)
            """,
            (tenant_id, payment_id, invoice_id, amount),
        )

    # ── what teaching costs ───────────────────────────────────────────
    cur.execute(
        """
        INSERT INTO teacher_engagements (tenant_id, teacher_user_id, engagement, abn)
        VALUES (%s, %s, 'contractor', %s)
        ON CONFLICT (tenant_id, teacher_user_id) DO NOTHING
        """,
        (tenant_id, teacher_id, content.TEACHER_PAY["abn"]),
    )
    cur.execute(
        """
        INSERT INTO teacher_pay_rates
            (tenant_id, teacher_user_id, basis, amount_cents, effective_from)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        """,
        (tenant_id, teacher_id, content.TEACHER_PAY["rate_basis"],
         content.TEACHER_PAY["rate_cents"], today - timedelta(days=180)),
    )
    period_start = today.replace(day=1)
    cur.execute(
        """
        INSERT INTO teacher_pay_periods
            (tenant_id, teacher_user_id, period_start, period_end, status)
        VALUES (%s, %s, %s, %s, 'open')
        RETURNING id
        """,
        (tenant_id, teacher_id, period_start,
         (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)),
    )
    row = cur.fetchone()
    period_id = str(row["id"]) if row else None
    sessions = 0
    for offset in range(1, 13):
        occurred = period_start + timedelta(days=offset * 2)
        if occurred > today:
            break
        cur.execute(
            """
            INSERT INTO teaching_sessions
                (tenant_id, teacher_user_id, period_id, occurred_on, start_time,
                 duration_minutes, student_count, source, rate_basis, rate_amount_cents,
                 amount_cents, tuition_basis_cents, counts_for_pay, note)
            VALUES (%s, %s, %s, %s, %s::time, %s, %s, 'roster', %s, %s,
                    %s, %s, true, %s)
            """,
            (tenant_id, teacher_id, period_id, occurred,
             content.TEACHER_PAY["session"]["start_time"],
             content.TEACHER_PAY["session"]["duration_minutes"],
             content.TEACHER_PAY["session"]["student_count"],
             content.TEACHER_PAY["rate_basis"],
             content.TEACHER_PAY["rate_cents"],
             content.TEACHER_PAY["session"]["amount_cents"],
             content.TEACHER_PAY["session"]["tuition_basis_cents"],
             content.TEACHER_PAY["session"]["note"]),
        )
        sessions += 1

    # ── the private lesson, and one real absence ──────────────────────
    cur.execute(
        """
        INSERT INTO scheduling_policies
            (tenant_id, notice_hours, makeup_credit_on_notice, makeup_expiry_days)
        VALUES (%s, 24, true, 90)
        ON CONFLICT (tenant_id) DO NOTHING
        """,
        (tenant_id,),
    )
    series_ids: list[str] = []
    for index, (weekday, start_time, student_index) in enumerate(
        ((2, "16:00", 0), (4, "17:30", 3))
    ):
        if student_index >= len(student_ids):
            continue
        cur.execute(
            """
            INSERT INTO lesson_series
                (tenant_id, student_id, teacher_user_id, weekday, start_time,
                 duration_minutes, room, starts_on, created_by_user_id, note)
            VALUES (%s, %s, %s, %s, %s::time, 30, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant_id, student_ids[student_index], teacher_id, weekday, start_time,
             content.ROOM_NAMES[index % len(content.ROOM_NAMES)],
             today - timedelta(days=60), owner_id, "一对一"),
        )
        series_ids.append(str(cur.fetchone()["id"]))

    credits = 0
    if series_ids:
        # A cancellation with enough notice: not charged, teacher not paid, and
        # a make-up owed. Showing the three answers together is the point of the
        # screen, so the demo has to contain a case where they differ.
        absent_on = today - timedelta(days=(today.weekday() - 2) % 7 or 7)
        cur.execute(
            """
            INSERT INTO lesson_exceptions
                (tenant_id, series_id, on_date, kind, chargeable, counts_for_pay,
                 reason, created_by_user_id)
            VALUES (%s, %s, %s, 'cancelled_by_student', false, false, %s, %s)
            ON CONFLICT (series_id, on_date) DO NOTHING
            RETURNING id
            """,
            (tenant_id, series_ids[0], absent_on, "家长提前三天来电请假", owner_id),
        )
        exception = cur.fetchone()
        if exception:
            cur.execute(
                """
                INSERT INTO makeup_credits
                    (tenant_id, student_id, earned_from_date, earned_from_exception_id,
                     expires_on, reason, created_by_user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (tenant_id, student_ids[0], absent_on, exception["id"],
                 absent_on + timedelta(days=90), "按时请假", owner_id),
            )
            cur.execute(
                "UPDATE lesson_exceptions SET makeup_credit_id = %s WHERE id = %s",
                (cur.fetchone()["id"], exception["id"]),
            )
            credits = 1

    # ── progress reports ──────────────────────────────────────────────
    # Two published so the family-facing side is visible, two overdue so the
    # Pending worklist has something in it. An empty worklist looks like a
    # feature that does not work.
    reports = 0
    for index, student_id in enumerate(student_ids[:4]):
        published = index < 2
        period_end = today - timedelta(days=40 if published else 25)
        report = content.PROGRESS_REPORTS[index % len(content.PROGRESS_REPORTS)]
        report_body = json.dumps({
            "periodStart": (period_end - timedelta(days=60)).isoformat(),
            "periodEnd": period_end.isoformat(),
            "attendance": {"scheduled": 8, "attended": 7, "cancelled": 1,
                           "makeups": 0, "ratePercent": 88},
            "lessons": [
                {"class_date": (period_end - timedelta(days=d)).isoformat(),
                 "note": note, "course_name": report["course_name"]}
                for d, note in report["lessons"]
            ],
        })
        cur.execute(
            """
            INSERT INTO progress_reports
                (tenant_id, student_id, teacher_user_id, period_start, period_end,
                 content, teacher_comment, status, published_at, published_by_user_id)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            """,
            (tenant_id, student_id, teacher_id,
             period_end - timedelta(days=60), period_end, report_body,
             report["comment"] if published else "",
             "published" if published else "draft",
             (period_end + timedelta(days=3)) if published else None,
             owner_id if published else None),
        )
        reports += 1

    # ── Xero：只种「已加购」，其余留给真人点 ────────────────────────────
    # 上一版还种了一条 status='connected' 的连接和一个 mapping_confirmed_at。
    # 两条都是假的：连接**没有 token**，所以集成页显示「已连接」而「测试令牌
    # 自愈」必然 409（会面现场就是这样，只能当着客户重连）；而「映射已确认」
    # 旁边同时列着「还差 tuition、bank」，因为一行映射也没种。
    #
    # `confirm_mapping()` 本来就会拒绝空映射，播种器等于绕过了自己的守卫。
    # 现在只种加购：向导显示「已加购 ✓ / 未连接」，是真的，而且连接是一次
    # 真正能成功的点击。
    cur.execute(
        """
        INSERT INTO tenant_addons (tenant_id, addon_key, status, note)
        VALUES (%s, 'xero', 'active', %s)
        ON CONFLICT (tenant_id, addon_key) DO UPDATE SET status = 'active'
        """,
        (tenant_id, "演示：已加购 Xero 直连（连接与映射由操作者本人完成）"),
    )

    return {
        "billing_accounts": len(account_ids),
        "invoices": len(invoices),
        "teaching_sessions": sessions,
        "lesson_series": len(series_ids),
        "makeup_credits": credits,
        "progress_reports": reports,
    }


# ── the catalogue and the week ─────────────────────────────────────────────


def _seed_catalog(cur: Any, tenant_id: str) -> list[str]:
    """Create the course and package catalogue."""

    course_ids: list[str] = []
    for name, description, category, age_range, duration, price_cents in content.COURSES:
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

    for course_index, name, credits, price_cents, expiry in content.PACKAGES:
        cur.execute(
            """
            INSERT INTO packages (
                tenant_id, course_id, name, credits, price_aud_cents,
                expires_after_days, is_active
            )
            VALUES (%s, %s, %s, %s, %s, %s, true)
            """,
            (tenant_id, course_ids[course_index], name, credits, price_cents, expiry),
        )
    return course_ids


def _seed_schedules(
    cur: Any,
    tenant_id: str,
    course_ids: list[str],
    student_ids: list[str],
    teachers: dict[str, str],
) -> list[str]:
    """Create the weekly classes, all public, with teachers and rooms."""

    schedule_ids: list[str] = []
    for course_index, label, weekday, start, duration, capacity, room, teacher_key, roster in content.SCHEDULES:
        cur.execute(
            """
            INSERT INTO class_schedules (
                tenant_id, course_id, label, weekday, start_time,
                duration_minutes, capacity, room, teacher_user_id,
                is_public, is_active
            )
            VALUES (%s, %s, %s, %s, %s::time, %s, %s, %s, %s, true, true)
            RETURNING id
            """,
            (
                tenant_id, course_ids[course_index], label, weekday, start,
                duration, capacity, room, teachers[teacher_key],
            ),
        )
        schedule_id = str(cur.fetchone()["id"])
        schedule_ids.append(schedule_id)
        start_index, end_index = roster
        for student_id in student_ids[start_index:end_index]:
            cur.execute(
                """
                INSERT INTO class_schedule_students (schedule_id, student_id, tenant_id)
                VALUES (%s, %s, %s)
                """,
                (schedule_id, student_id, tenant_id),
            )
    return schedule_ids


def _next_occurrence(weekday: int, minimum_days: int) -> date:
    """The first date at least ``minimum_days`` away that falls on ``weekday``.

    class_schedules.weekday follows JS getDay(): 0=Sunday..6=Saturday, and
    ``isoweekday() % 7`` is the same convention. A booking whose date is not
    actually an occurrence of its class is a row the public page will never
    show and the CMS cannot approve.
    """

    candidate = date.today() + timedelta(days=minimum_days)
    while candidate.isoweekday() % 7 != weekday:
        candidate += timedelta(days=1)
    return candidate


def _seed_schedule_exceptions(cur: Any, tenant_id: str, schedule_ids: list[str], owner_id: str) -> None:
    """Cancel two upcoming classes.

    A timetable that has never been corrected does not demonstrate that it can
    be — and the ability to withdraw a published time is the difference between
    a timetable and a promise.
    """

    for schedule_index, minimum_days, note in content.SCHEDULE_EXCEPTIONS:
        weekday = content.SCHEDULES[schedule_index][2]
        cur.execute(
            """
            INSERT INTO class_schedule_exceptions (
                schedule_id, tenant_id, on_date, cancelled, note, created_by_user_id
            )
            VALUES (%s, %s, %s, true, %s, %s)
            ON CONFLICT (schedule_id, on_date) DO NOTHING
            """,
            (
                schedule_ids[schedule_index],
                tenant_id,
                _next_occurrence(weekday, minimum_days),
                note,
                owner_id,
            ),
        )


def _seed_bookings(cur: Any, tenant_id: str, schedule_ids: list[str]) -> None:
    """Three pending class requests, one per class a visitor would ask about."""

    for schedule_index, minimum_days, name, phone, message in content.BOOKINGS:
        weekday = content.SCHEDULES[schedule_index][2]
        cur.execute(
            """
            INSERT INTO class_bookings (
                tenant_id, schedule_id, on_date, contact_name, contact_phone,
                message, status, privacy_notice_version, source_language
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'pending', '2026-07', 'zh')
            ON CONFLICT DO NOTHING
            """,
            (
                tenant_id,
                schedule_ids[schedule_index],
                _next_occurrence(weekday, minimum_days),
                name,
                phone,
                message,
            ),
        )


def _seed_registrations(cur: Any, tenant_id: str, manager_id: str) -> None:
    """Create a small enquiry pipeline covering the main sales states."""

    for index, record in enumerate(content.REGISTRATIONS):
        status, first, last, parent, mobile, email, message, follow_up_days = record
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
                json.dumps({
                    **content.REGISTRATION_ANSWERS[
                        index % len(content.REGISTRATION_ANSWERS)
                    ],
                }),
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


# ── the pictures ───────────────────────────────────────────────────────────


def _seed_studio_works(conn: Any, tenant_id: str, manifest: dict) -> tuple[list[dict], list[dict]]:
    """Upload the studio's own work and return (categories, showcase items).

    Categories are built from the works that exist rather than from the
    manifest's dictionary of available ones. A category with no work in it
    renders a filter button that opens onto an empty grid, and there is no
    amount of care at the call site that prevents that as reliably as never
    creating the drawer in the first place.
    """

    labels = manifest.get("categories") or {}
    works = manifest.get("studio_works") or []

    # Two passes, and the order matters more than it looks. Deciding which
    # drawers exist WHILE building the items makes the result depend on the
    # order of the list: a draft filed under a category whose first published
    # work comes later would silently lose its category, and moving two lines
    # in the manifest would change what the console shows.
    used = [
        category
        for category in dict.fromkeys(
            str(work.get("category") or "") for work in works
            if str(work.get("state") or "active") == "active"
        )
        if category and category in labels
    ]

    items: list[dict] = []
    for work in works:
        media_id = _upload(conn, tenant_id, work["file"], "website_image")
        category = str(work.get("category") or "")
        state = str(work.get("state") or "active")
        items.append({
            "image_url": _public_media_url(media_id),
            # An unpublished work keeps its category on the record, but it is
            # never what OPENS a drawer: a draft filed under 人像 must not put
            # a 人像 filter on the public page.
            "category_id": category if category in used else "",
            "featured_rank": work.get("rank"),
            "publication_state": state,
            "title": work.get("title") or {"zh": "", "en": ""},
            "caption": work.get("caption") or {"zh": "", "en": ""},
            "video_provider": "",
            "video_id": "",
        })
    categories = [{"id": key, "label": labels[key]} for key in used]
    return categories, items


def _seed_room_photos(conn: Any, tenant_id: str, manifest: dict) -> list[dict]:
    """Upload the photographs of the room and return url/alt pairs.

    Alt text comes from the manifest rather than being generated from the
    filename, because "room-03" is not a description and an alt attribute that
    describes nothing is the accessibility equivalent of leaving it blank.
    """

    photos: list[dict] = []
    for photo in (manifest.get("room_photos") or [])[:6]:
        media_id = _upload(conn, tenant_id, photo["file"], "website_image")
        photos.append({
            "url": _public_media_url(media_id),
            "alt": photo.get("alt") or {"zh": "", "en": ""},
        })
    return photos


def _record_consent(cur: Any, tenant_id: str, student_id: str, actor_id: str, status: str) -> None:
    """Append one publication-consent event for a student.

    Consent is an append-only LOG, not a boolean on the student row, and the
    public page reads the latest event. Withdrawing therefore adds a row
    rather than editing one, so a studio can always answer "when was this
    agreed, and by whom" — which is the question that matters when a parent
    rings up about a photograph of their child's painting.
    """

    cur.execute(
        """
        INSERT INTO student_publication_consent_events (
            tenant_id, student_id, status, consent_by, relationship,
            consent_method, notice_version, note, actor_user_id, created_at
        )
        VALUES (%s, %s, %s, %s, %s, 'in_person', '2026-07', %s, %s,
                now() - (%s * interval '1 day'))
        """,
        (
            tenant_id, student_id, status,
            "Student" if status == "confirmed" else "Parent",
            "self" if status == "confirmed" else "parent",
            "Fictional showcase record."
            if status == "confirmed"
            else "Consent withdrawn at the family's request; the work stays on the record.",
            actor_id,
            30 if status == "confirmed" else 3,
        ),
    )


def _seed_student_works(
    conn: Any, tenant_id: str, manifest: dict, student_ids: list[str], owner_id: str
) -> tuple[int, int]:
    """Publish student work and return (works, publicly visible works).

    TWO gates have to be open before a piece reaches the public page:

        the STUDENT has a current `confirmed` publication-consent event, and
        the WORK is `shared` with a `public_consent_at` timestamp.

    Seeding only the second one — which this script did until v9.9.2 — leaves
    the gallery permanently empty with `no_consented_student_work`, and the
    tenant looks like it has a bug rather than a missing consent record.

    One student's consent is deliberately WITHDRAWN. A demonstration where
    consent has only ever been granted proves nothing about what happens when
    it is taken back, and taking it back is the promise the FAQ makes on the
    public page.
    """

    works = manifest.get("student_works") or []
    for index, work in enumerate(works):
        media_id = _upload(conn, tenant_id, work["file"], "portfolio")
        # The manifest names WHICH student, by index into the same roster the
        # CMS was seeded from. Round-robin would have credited work to whoever
        # happened to sort first, and a public page crediting the wrong person
        # is the one mistake this feature cannot make.
        student_id = student_ids[int(work.get("student", index)) % len(student_ids)]
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE media_assets SET owner_student_id = %s WHERE tenant_id = %s AND id = %s",
                (student_id, tenant_id, media_id),
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
                    'shared', now(), %s,
                    'Fictional showcase student; synthetic artwork approved for the demo.'
                )
                """,
                (
                    tenant_id,
                    student_id,
                    media_id,
                    (work.get("title") or {}).get("en", ""),
                    (work.get("caption") or {}).get("en", ""),
                    index + 1,
                    owner_id,
                ),
            )
            _record_consent(cur, tenant_id, student_id, owner_id, "confirmed")
            if str(work.get("consent") or "confirmed") == "withdrawn":
                # Confirmed first, then withdrawn: the log has to read like the
                # history it is, or the CMS shows a withdrawal with nothing
                # before it.
                _record_consent(cur, tenant_id, student_id, owner_id, "withdrawn")
    visible = sum(
        1 for work in works if str(work.get("consent") or "confirmed") == "confirmed"
    )
    return len(works), visible


# ── the presenter handoff ──────────────────────────────────────────────────


def _write_credentials(path: Path, credentials: list[dict[str, str]], student_code: str) -> None:
    """Write the presenter handoff with owner-only filesystem permissions."""

    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"PWE Studio v{_app_version()} · Professional Showcase",
        f"Tenant: {SHOWCASE_NAME} ({content.PLAN_CODE} plan)",
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
            f"- Student name: {content.STUDENTS[0][0]} {content.STUDENTS[0][1]}",
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


def _use_owner_connection() -> None:
    """重置是造世界，造世界是属主的活。

    这个脚本建租户、建角色成员、清空又重填 20 多张租户表。v10.3.0 起那些表
    都受行级安全约束，而应用角色在没有租户上下文时一行都写不进去 —— 它本来
    就不该能，这正是隔离的意思。

    生产的 compose 早就把两个连接串分开了（迁移用属主、应用用受限），这里只是
    把这个脚本归到它本来属于的那一类。没配 MIGRATION URL 的环境（比如本地）
    保持原样。

    同样的道理已经用在 test_tenant_isolation.py 的种子步骤和 pytest 的夹具上：
    造世界用属主，跑断言用受限。
    """

    owner = os.environ.get("STUDIOSAAS_MIGRATION_DATABASE_URL")
    if owner:
        os.environ["STUDIOSAAS_DATABASE_URL"] = owner


def _application_context():
    """An app context to run in — the existing one if we are already inside it.

    `store_media_asset` reads the media root from `current_app.config`, exactly
    as it does for a browser upload, so this needs a Flask application and not
    only a database.

    From the command line there is none, so one is created. From the Platform
    Admin endpoint there already is, and `import server` would re-execute
    server.py inside the running process — re-registering a blueprint Flask has
    already mounted, which fails with

        AssertionError: The setup method 'register_error_handler' can no longer
        be called on the blueprint 'studiosaas_api_v1'.

    and turns a working reset into a 500 that only ever appears in production.
    Asking whether a context exists is the difference between the two callers.
    """

    if has_app_context():
        return contextlib.nullcontext()
    # Imported here rather than at module scope so `--help` and the safety
    # guards still work on a machine where the app cannot start at all.
    import server

    return server.app.app_context()


def reset_showcase(credentials_file: Path, pack: str = DEFAULT_PACK) -> dict[str, Any]:
    """Reset one demonstration studio in a transaction, and return evidence.

    `pack` is resolved here rather than inherited, so a process that reset the
    art studio earlier cannot seed its content into the music one.
    """

    _select_pack(pack)
    password = os.environ.get(DEMO_PASSWORD_ENV, "")
    if len(password) < 12:
        raise RuntimeError(
            f"{DEMO_PASSWORD_ENV} must provide the stable demonstration password "
            "with at least 12 characters."
        )
    manifest = _manifest()
    _use_owner_connection()
    with _application_context(), connect(statement_timeout_ms=0, lock_timeout_ms=0) as conn:
        with conn.cursor() as cur:
            tenant_id = _load_or_create_tenant(cur)
            _clear_showcase(cur, tenant_id)
            credentials = _seed_roles(cur, tenant_id, password)
            by_role = {item["key"]: item["user_id"] for item in credentials}
            owner_id, teacher_id, manager_id = (
                by_role["owner"], by_role["teacher"], by_role["manager"],
            )
            course_ids = _seed_catalog(cur, tenant_id)
            student_ids = _seed_students(cur, tenant_id, course_ids, teacher_id)
            schedule_ids = _seed_schedules(cur, tenant_id, course_ids, student_ids, by_role)
            _seed_schedule_exceptions(cur, tenant_id, schedule_ids, owner_id)
            _seed_bookings(cur, tenant_id, schedule_ids)
            _seed_registrations(cur, tenant_id, manager_id)
            money = _seed_money_layer(cur, tenant_id, student_ids, by_role)

        # Media goes through the product's own upload path, which opens its own
        # cursors on this connection and stays inside this transaction.
        media = {
            "logo": _public_media_url(_upload(conn, tenant_id, manifest["logo"]["light"], "logo")),
        }
        for key, kind in (("hero", "website_image"), ("principal", "website_image")):
            relative = manifest.get("hero" if key == "hero" else "principal_portrait") or ""
            media[key] = _public_media_url(_upload(conn, tenant_id, relative, kind)) if relative else ""
        room = _seed_room_photos(conn, tenant_id, manifest)
        categories, works = _seed_studio_works(conn, tenant_id, manifest)
        student_work_count, public_student_works = _seed_student_works(
            conn, tenant_id, manifest, student_ids, owner_id
        )

        settings = _settings(manifest, media)
        settings["logo_url"] = media["logo"]
        settings["website_profile"] = _website_profile(
            categories, works, has_students=public_student_works > 0, room=room
        )
        with conn.cursor() as cur:
            _publish_tenant(cur, tenant_id, settings)
            cur.execute(
                """
                INSERT INTO subscriptions (tenant_id, plan_code, status, starts_at, current_period_ends_at)
                VALUES (%s, %s, 'active', now(), now() + interval '1 year')
                ON CONFLICT (tenant_id) DO UPDATE
                SET plan_code = EXCLUDED.plan_code, status = 'active',
                    current_period_ends_at = EXCLUDED.current_period_ends_at,
                    updated_at = now()
                """,
                (tenant_id, content.PLAN_CODE),
            )
            cur.execute(
                """
                INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb)
                VALUES (%s, %s, %s, 12)
                ON CONFLICT (tenant_id) DO UPDATE
                SET student_count = EXCLUDED.student_count,
                    user_count = EXCLUDED.user_count,
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
                    json.dumps({
                        "version": _app_version(),
                        "plan": content.PLAN_CODE,
                        "students": len(student_ids),
                        "schedules": len(schedule_ids),
                        "studio_works": len(works),
                        "student_works": student_work_count,
                        "student_works_public": public_student_works,
                        "room_photos": len(room),
                        "categories": [item["id"] for item in categories],
                    }),
                ),
            )
        student_code, _ = generate_access_code(conn, tenant_id=tenant_id, student_id=student_ids[0])
        conn.commit()
    _write_credentials(credentials_file, credentials, student_code)
    return {
        "tenant_id": tenant_id,
        "students": len(student_ids),
        "roles": len(credentials),
        "schedules": len(schedule_ids),
        "studio_works": len(works),
        "student_works": student_work_count,
        "student_works_public": public_student_works,
        "room_photos": len(room),
        "categories": [item["id"] for item in categories],
        "credentials_file": str(credentials_file),
        **money,
    }


def main() -> int:
    """Run the guarded reset and print only non-secret acceptance evidence."""

    args = _parse_args()
    # Select first, then guard, then seed — in that order. Guarding before the
    # pack is resolved compares the typed phrase against whichever pack happened
    # to be bound at import, so `--pack music --confirm <the art phrase>` passed
    # the check and then rebuilt the art studio: a flag that lies is worse than
    # no flag. The same ordering mistake, one layer down, is what made the
    # Platform Admin reset button reset the wrong tenant.
    _select_pack(args.pack)
    _refuse_unsafe_context(args.confirm)
    credentials_file = _credentials_path(args.credentials_file)
    result = reset_showcase(credentials_file, pack=args.pack)
    print(f"Professional showcase ready: /{SHOWCASE_SLUG} ({content.PLAN_CODE} plan)")
    print(
        "Created "
        f"{result['students']} students, {result['roles']} roles, "
        f"{result['schedules']} public classes, "
        f"{result['studio_works']} studio works, "
        f"{result['student_works']} student works "
        f"({result['student_works_public']} with current consent) and "
        f"{result['room_photos']} photographs of the room."
    )
    print(
        "Money layer: "
        f"{result['billing_accounts']} payers, {result['invoices']} invoices, "
        f"{result['teaching_sessions']} teaching sessions, "
        f"{result['lesson_series']} private lessons, "
        f"{result['makeup_credits']} make-up credits, "
        f"{result['progress_reports']} progress reports. Xero add-on active, gate unsatisfied."
    )
    print(f"Showcase categories: {', '.join(result['categories']) or '(none)'}")
    print(f"Protected presenter credentials: {result['credentials_file']} (mode 0600)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
