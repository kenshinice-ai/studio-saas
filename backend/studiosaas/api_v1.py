"""StudioSaaS API v1 routes.

These routes are intentionally introduced beside the legacy endpoints. Tenant
APIs require PostgreSQL and explicit tenant resolution; they do not fall back to
the single-studio JSON database.
"""

import json
import os
import re
import secrets
import time
import hashlib
import uuid as _uuid
from pathlib import PurePath

from flask import Blueprint, current_app, g, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from .auth import (
    auth_required,
    hash_password as _auth_hash_password,
    permission_required,
    super_admin_required,
    tenant_admin_required,
    verify_password as _auth_verify_password,
)
from .config import load_config
from .db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from .errors import api_error
from .services.media import (
    MediaQuotaExceededError,
    MediaUploadError,
    send_media_asset,
    store_media_asset,
)
from .services.tenant_archive import (
    TenantArchiveError,
    archive_tenant,
    permanently_delete_tenant,
    restore_tenant,
)
from .tenant_context import TenantResolutionError, resolve_tenant, slug_from_request
from .workspaces import WorkspaceError, ensure_tenant_workspace

api_v1 = Blueprint("studiosaas_api_v1", __name__)
# Simple in-memory rate limiter for public endpoints (per-IP, per-minute).
# Counters reset on process restart — acceptable for the local pilot; a
# shared store (Redis) replaces this at the production stage (P3-04).
_public_rate_limit: dict[str, list[float]] = {}


def _login_rate_limited(email: str) -> bool:
    """Sliding-window limiter for login attempts.

    Two dimensions share the public limiter store: per client IP
    (30 attempts/minute across all accounts — high enough for local
    test suites, low enough to blunt spraying) and per IP+email
    (5 attempts/minute against a single account).
    """

    now = time.time()
    ip = request.remote_addr or "unknown"
    limited = False
    for key, limit in (
        (f"login-ip:{ip}", 30),
        (f"login-email:{ip}:{email}", 5),
    ):
        attempts = [t for t in _public_rate_limit.get(key, []) if now - t < 60]
        if len(attempts) >= limit:
            limited = True
        else:
            attempts.append(now)
        _public_rate_limit[key] = attempts
    return limited


def _record_login(conn, user_id) -> None:
    """Stamp users.last_login_at on successful login (any surface)."""

    with conn.cursor() as cur:
        cur.execute(
            "UPDATE users SET last_login_at = now() WHERE id = %s",
            (user_id,),
        )



@api_v1.url_value_preprocessor
def pull_tenant_slug(endpoint, values):
    """Store `/s/<tenant_slug>/v1/...` slugs without passing them to views."""

    if endpoint and endpoint.startswith(f"{api_v1.name}.public_"):
        return
    if values and "path_tenant_slug" in values:
        g.path_tenant_slug = values.pop("path_tenant_slug")
    elif values and "tenant_slug" in values and endpoint and ".public_" not in endpoint:
        g.path_tenant_slug = values.pop("tenant_slug")


@api_v1.errorhandler(DatabaseUnavailableError)
def handle_database_unavailable(exc: DatabaseUnavailableError):
    """Return a clear setup error when PostgreSQL is not ready."""

    return api_error(str(exc), 503, error="database_unavailable")


@api_v1.errorhandler(TenantResolutionError)
def handle_tenant_error(exc: TenantResolutionError):
    """Return a clear tenant error instead of silently picking a default."""

    return api_error(str(exc), 400, error="tenant_resolution_failed")


TENANT_STATUSES = {"trial", "active", "past_due", "paused", "cancelled", "archived", "deleted"}
SUBSCRIPTION_STATUSES = {"trialing", "active", "past_due", "paused", "cancelled", "archived"}


def _json_payload() -> dict:
    """Return a JSON object payload or raise a request error response."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _ensure_default_credit_account(cur, tenant_id: str, student_id: str, balance: float | None = None) -> None:
    """Create or update the tenant-wide credit account where ``course_id`` is NULL."""

    if balance is None:
        cur.execute(
            """
            INSERT INTO credit_accounts (tenant_id, student_id)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            )
            """,
            (tenant_id, student_id, tenant_id, student_id),
        )
        return

    cur.execute(
        """
        UPDATE credit_accounts
        SET balance = %s, updated_at = now()
        WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
        """,
        (balance, tenant_id, student_id),
    )
    if cur.rowcount:
        return
    cur.execute(
        """
        INSERT INTO credit_accounts (tenant_id, student_id, balance)
        VALUES (%s, %s, %s)
        """,
        (tenant_id, student_id, balance),
    )


def _clean_text(payload: dict, key: str, default: str = "") -> str:
    """Read a trimmed text field from a request payload."""

    value = payload.get(key, default)
    return str(value if value is not None else "").strip()


INDUSTRY_PRESETS = {
    "art": {
        "label": "Art",
        "slogan": "You deserve to enjoy life more.",
        "registration_title": "Creative Preferences",
        "copy_pack": {
            "portal_label": "Student Art Portal",
            "register_intro": "Tell us about the student and their creative goals.",
        },
        "fields": [
            {"key": "artStyle", "label": "Preferred style", "placeholder": "Watercolour, sketching, acrylic"},
            {"key": "favArtist", "label": "Favourite artist", "placeholder": "Monet, Van Gogh, Yayoi Kusama"},
            {"key": "goals", "label": "Creative goals", "placeholder": "Relax, build technique, portfolio prep"},
        ],
    },
    "music": {
        "label": "Music",
        "slogan": "Every student deserves a rhythm of their own.",
        "registration_title": "Music Preferences",
        "copy_pack": {
            "portal_label": "Music Student Portal",
            "register_intro": "Tell us about the student and their music goals.",
        },
        "fields": [
            {"key": "instrument", "label": "Instrument", "placeholder": "Piano, guitar, violin, voice"},
            {"key": "level", "label": "Current level", "placeholder": "Beginner, AMEB Grade 2, self-taught"},
            {"key": "goals", "label": "Learning goals", "placeholder": "Exam prep, performance, confidence"},
        ],
    },
    "math": {
        "label": "Math",
        "slogan": "Build confidence through clear thinking.",
        "registration_title": "Learning Focus",
        "copy_pack": {
            "portal_label": "Math Learning Portal",
            "register_intro": "Tell us about the learner and the topics they need help with.",
        },
        "fields": [
            {"key": "yearLevel", "label": "Year level", "placeholder": "Year 5, Year 9, VCE"},
            {"key": "topics", "label": "Topic focus", "placeholder": "Algebra, fractions, problem solving"},
            {"key": "goals", "label": "Learning goals", "placeholder": "Catch up, extension, exam confidence"},
        ],
    },
    "dance": {
        "label": "Dance",
        "slogan": "Move with confidence, discipline, and joy.",
        "registration_title": "Dance Preferences",
        "copy_pack": {
            "portal_label": "Dance Student Portal",
            "register_intro": "Tell us about the dancer and their goals.",
        },
        "fields": [
            {"key": "danceStyle", "label": "Dance style", "placeholder": "Ballet, jazz, hip hop, contemporary"},
            {"key": "level", "label": "Current level", "placeholder": "Beginner, intermediate, exam stream"},
            {"key": "goals", "label": "Dance goals", "placeholder": "Fitness, performance, technique"},
        ],
    },
    "language": {
        "label": "Language",
        "slogan": "Grow a voice for the world.",
        "registration_title": "Language Goals",
        "copy_pack": {
            "portal_label": "Language Student Portal",
            "register_intro": "Tell us about the learner and their language goals.",
        },
        "fields": [
            {"key": "language", "label": "Language", "placeholder": "English, Mandarin, Japanese, French"},
            {"key": "level", "label": "Current level", "placeholder": "Beginner, conversational, exam prep"},
            {"key": "goals", "label": "Learning goals", "placeholder": "Speaking, school support, travel"},
        ],
    },
    "sports": {
        "label": "Sports",
        "slogan": "Train with purpose and grow with every session.",
        "registration_title": "Training Goals",
        "copy_pack": {
            "portal_label": "Sports Student Portal",
            "register_intro": "Tell us about the athlete and their training goals.",
        },
        "fields": [
            {"key": "sport", "label": "Sport", "placeholder": "Tennis, swimming, basketball, soccer"},
            {"key": "level", "label": "Current level", "placeholder": "Beginner, club, competition"},
            {"key": "goals", "label": "Training goals", "placeholder": "Fitness, technique, competition prep"},
        ],
    },
    "game": {
        "label": "Game",
        "slogan": "Play, think, and level up with purpose.",
        "registration_title": "Game Learning Goals",
        "copy_pack": {
            "portal_label": "Game Student Portal",
            "register_intro": "Tell us about the player and their learning goals.",
        },
        "fields": [
            {"key": "gameType", "label": "Game type", "placeholder": "Roblox, Minecraft, chess, coding games"},
            {"key": "level", "label": "Current level", "placeholder": "Beginner, casual, competitive"},
            {"key": "goals", "label": "Learning goals", "placeholder": "Strategy, coding, teamwork, confidence"},
        ],
    },
    "general": {
        "label": "General",
        "slogan": "Learn, grow, and feel confident.",
        "registration_title": "Student Preferences",
        "copy_pack": {
            "portal_label": "Student Portal",
            "register_intro": "Tell us about the student and their goals.",
        },
        "fields": [
            {"key": "interests", "label": "Interests", "placeholder": "What does the student enjoy?"},
            {"key": "experience", "label": "Experience", "placeholder": "Beginner, some experience, advanced"},
            {"key": "goals", "label": "Goals", "placeholder": "Confidence, skills, exam prep, fun"},
        ],
    },
}


def _preset_for(category: str) -> dict:
    """Return a supported industry preset, falling back to the general preset."""

    return INDUSTRY_PRESETS.get(category, INDUSTRY_PRESETS["general"])


def _normalize_category(value: str) -> str:
    """Validate a tenant industry category key."""

    category = str(value or "general").strip().lower()
    if category not in INDUSTRY_PRESETS:
        raise ValueError(f"Studio category must be one of: {', '.join(sorted(INDUSTRY_PRESETS))}.")
    return category


def _default_registration_profile(category: str) -> dict:
    """Return a fresh registration profile for the given industry category."""

    preset = _preset_for(category)
    return {
        "title": preset["registration_title"],
        "fields": [dict(field) for field in preset["fields"]],
    }


def _normalize_registration_profile(value, category: str) -> dict:
    """Validate configurable public-registration preference fields."""

    default = _default_registration_profile(category)
    if value in (None, ""):
        return default
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("registration_profile must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("registration_profile must be a JSON object.")
    title = str(value.get("title") or default["title"]).strip()[:80] or default["title"]
    fields = value.get("fields")
    if fields is None:
        fields = default["fields"]
    if not isinstance(fields, list):
        raise ValueError("registration_profile.fields must be a list.")
    normalized = []
    for field in fields[:8]:
        if not isinstance(field, dict):
            raise ValueError("Each registration field must be an object.")
        key = str(field.get("key") or "").strip()
        label = str(field.get("label") or "").strip()
        placeholder = str(field.get("placeholder") or "").strip()
        input_type = str(field.get("type") or "text").strip().lower()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]{1,40}$", key):
            raise ValueError("Registration field keys must use letters, numbers, or underscores.")
        if not label:
            raise ValueError("Registration field labels are required.")
        if input_type not in {"text", "textarea"}:
            raise ValueError("Registration field type must be text or textarea.")
        normalized.append({
            "key": key,
            "label": label[:80],
            "placeholder": placeholder[:140],
            "type": input_type,
        })
    if not normalized:
        raise ValueError("At least one registration field is required.")
    return {"title": title, "fields": normalized}


def _normalize_copy_pack(value, category: str) -> dict:
    """Validate tenant-specific public copy labels."""

    default = dict(_preset_for(category)["copy_pack"])
    if value in (None, ""):
        return default
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError("copy_pack must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError("copy_pack must be a JSON object.")
    for key in ("portal_label", "register_intro"):
        incoming = str(value.get(key) or default[key]).strip()
        default[key] = incoming[:180] or default[key]
    return default


def _plan_payload(payload: dict) -> dict:
    """Validate and normalize a plan write payload."""

    code = _clean_text(payload, "code").lower()
    if code and not re.match(r"^[a-z0-9][a-z0-9-]{1,62}$", code):
        raise ValueError("Plan code must be lowercase letters, numbers, or hyphens.")
    name = _clean_text(payload, "name")
    if not name:
        raise ValueError("Plan name is required.")
    try:
        monthly_price_aud = int(payload.get("monthlyPriceAud", payload.get("monthly_price_aud", 0)))
        student_limit = int(payload.get("studentLimit", payload.get("student_limit", 1)))
        user_limit = int(payload.get("userLimit", payload.get("user_limit", 1)))
        storage_limit_mb = int(payload.get("storageLimitMb", payload.get("storage_limit_mb", 1)))
    except (TypeError, ValueError) as exc:
        raise ValueError("Plan numeric limits must be valid integers.") from exc
    if monthly_price_aud < 0 or student_limit <= 0 or user_limit <= 0 or storage_limit_mb <= 0:
        raise ValueError("Plan limits must be positive, and monthly price cannot be negative.")
    features = payload.get("features", {})
    if not isinstance(features, dict):
        raise ValueError("Plan features must be a JSON object.")
    return {
        "code": code,
        "name": name,
        "monthly_price_aud": monthly_price_aud,
        "student_limit": student_limit,
        "user_limit": user_limit,
        "storage_limit_mb": storage_limit_mb,
        "features_json": json.dumps(features),
    }


def _tenant_write_payload(payload: dict, *, require_slug: bool) -> dict:
    """Validate and normalize tenant write payloads."""

    name = _clean_text(payload, "name")
    slug = _clean_text(payload, "slug").lower()
    plan_code = _clean_text(payload, "planCode", _clean_text(payload, "plan_code", "studio")).lower()
    status = _clean_text(payload, "status", "trial").lower()
    contact_phone = _clean_text(payload, "contactPhone", _clean_text(payload, "contact_phone", ""))
    contact_email = _clean_text(payload, "contactEmail", _clean_text(payload, "contact_email", "")).lower()
    address = _clean_text(payload, "address", "")
    category = _normalize_category(_clean_text(payload, "category", _clean_text(payload, "studioCategory", "general")))
    preset = _preset_for(category)
    slogan = _clean_text(payload, "slogan", preset["slogan"])
    registration_profile = _normalize_registration_profile(
        payload.get("registrationProfile", payload.get("registration_profile")),
        category,
    )
    copy_pack = _normalize_copy_pack(payload.get("copyPack", payload.get("copy_pack")), category)
    settings = {
        "category": category,
        "category_label": preset["label"],
        "slogan": slogan,
        "registration_profile": registration_profile,
        "copy_pack": copy_pack,
        "owner_name": _clean_text(payload, "ownerName", _clean_text(payload, "owner_name", "")),
        "owner_role": _clean_text(payload, "ownerRole", _clean_text(payload, "owner_role", "Owner")),
        "owner_phone": _clean_text(payload, "ownerPhone", _clean_text(payload, "owner_phone", "")),
        "owner_email": _clean_text(payload, "ownerEmail", _clean_text(payload, "owner_email", "")).lower(),
        "billing_email": _clean_text(payload, "billingEmail", _clean_text(payload, "billing_email", "")).lower(),
        "abn": _clean_text(payload, "abn", ""),
        "website": _clean_text(payload, "website", ""),
        "notes": _clean_text(payload, "notes", ""),
    }
    subscription_status = _clean_text(
        payload,
        "subscriptionStatus",
        _clean_text(payload, "subscription_status", "trialing"),
    ).lower()
    if not name:
        raise ValueError("Tenant name is required.")
    if require_slug and not re.match(r"^[a-z0-9][a-z0-9-]{1,62}$", slug):
        raise ValueError("Tenant slug must be lowercase letters, numbers, or hyphens.")
    if status not in TENANT_STATUSES:
        raise ValueError(f"Tenant status must be one of: {', '.join(sorted(TENANT_STATUSES))}.")
    if subscription_status not in SUBSCRIPTION_STATUSES:
        raise ValueError(
            f"Subscription status must be one of: {', '.join(sorted(SUBSCRIPTION_STATUSES))}."
        )
    for field_name, value in (
        ("contactEmail", contact_email),
        ("ownerEmail", settings["owner_email"]),
        ("billingEmail", settings["billing_email"]),
    ):
        if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
            raise ValueError(f"{field_name} must be a valid email address.")
    if settings["abn"] and not re.match(r"^[0-9 ]{11,14}$", settings["abn"]):
        raise ValueError("ABN must be 11 digits; spaces are allowed.")
    if settings["website"] and not re.match(r"^https?://\S+$", settings["website"], re.IGNORECASE):
        raise ValueError("Website must start with http:// or https://.")
    return {
        "name": name,
        "slug": slug,
        "status": status,
        "plan_code": plan_code,
        "contact_phone": contact_phone,
        "contact_email": contact_email,
        "address": address,
        "settings_json": json.dumps(settings),
        "subscription_status": subscription_status,
        "starts_at": payload.get("startsAt") or payload.get("starts_at"),
        "ends_at": payload.get("endsAt") or payload.get("ends_at"),
        "trial_ends_at": payload.get("trialEndsAt") or payload.get("trial_ends_at"),
        "current_period_ends_at": payload.get("currentPeriodEndsAt")
        or payload.get("current_period_ends_at"),
        "studio_admin": _studio_admin_write_payload(payload, name, slug, require_password=require_slug),
    }


def _audit(conn, *, tenant_id, action, resource_type, resource_id="", metadata=None):
    """Write a compact audit log row for local admin mutations."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, action, resource_type, resource_id, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (tenant_id, action, resource_type, str(resource_id or ""), json.dumps(metadata or {})),
        )


def _audit_request(conn, *, tenant_id, action, resource_type, resource_id="", metadata=None):
    """Write an audit log row with request actor and IP when available."""

    actor = getattr(g, "actor", None)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_logs (
                tenant_id, actor_user_id, action, resource_type, resource_id,
                metadata, ip_address
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, NULLIF(%s, '')::inet)
            """,
            (
                tenant_id,
                getattr(actor, "user_id", None),
                action,
                resource_type,
                str(resource_id or ""),
                json.dumps(metadata or {}),
                request.remote_addr or "",
            ),
        )


def _error(message: str, status: int = 400):
    """Return a consistent JSON error response."""

    return api_error(message, status)


def _media_error(exc: Exception):
    """Map media-service exceptions to API errors."""

    if isinstance(exc, MediaQuotaExceededError):
        return api_error(str(exc), 403, error="quota_exceeded")
    return _error(str(exc))


def _studio_admin_write_payload(
    payload: dict,
    tenant_name: str,
    tenant_slug: str,
    *,
    require_password: bool = False,
) -> dict:
    """Normalize tenant Studio Admin login settings from a Super Admin payload."""

    owner_email = _clean_text(payload, "ownerEmail", _clean_text(payload, "owner_email", "")).lower()
    owner_name = _clean_text(payload, "ownerName", _clean_text(payload, "owner_name", ""))
    email = _clean_text(
        payload,
        "studioAdminEmail",
        _clean_text(payload, "studio_admin_email", owner_email or f"admin@{tenant_slug}.local"),
    ).lower()
    full_name = _clean_text(
        payload,
        "studioAdminName",
        _clean_text(payload, "studio_admin_name", owner_name or f"{tenant_name} Admin"),
    )
    password = _clean_text(payload, "studioAdminPassword", _clean_text(payload, "studio_admin_password", ""))

    if not email:
        raise ValueError("studioAdminEmail is required.")
    _validate_optional_email("studioAdminEmail", email)
    if not full_name:
        raise ValueError("studioAdminName is required.")
    if password and len(password) < 8:
        raise ValueError("studioAdminPassword must be at least 8 characters.")
    if require_password and not password:
        password = "admin123456"

    return {"email": email, "full_name": full_name[:120], "password": password}


def _ensure_studio_admin_account(conn, tenant_id: str, admin: dict) -> str:
    """Create or update the owner login used by Studio Admin and tenant CMS."""

    email = admin["email"]
    full_name = admin["full_name"]
    password = admin.get("password") or ""
    current = fetch_one(
        conn,
        "SELECT settings->>'studio_admin_user_id' AS user_id FROM tenants WHERE id = %s",
        (tenant_id,),
    )
    user_id = current.get("user_id") if current else None

    with conn.cursor() as cur:
        if user_id:
            email_owner = fetch_one(conn, "SELECT id FROM users WHERE email = %s", (email,))
            if email_owner and str(email_owner["id"]) != str(user_id):
                user_id = str(email_owner["id"])
            elif password:
                cur.execute(
                    """
                    UPDATE users
                    SET email = %s, full_name = %s, password_hash = %s,
                        status = 'active', updated_at = now()
                    WHERE id = %s
                    """,
                    (email, full_name, _hash_password(password), user_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE users
                    SET email = %s, full_name = %s, status = 'active', updated_at = now()
                    WHERE id = %s
                    """,
                    (email, full_name, user_id),
                )

        if not user_id:
            existing_user = fetch_one(conn, "SELECT id FROM users WHERE email = %s", (email,))
            if existing_user:
                user_id = str(existing_user["id"])
                if password:
                    cur.execute(
                        """
                        UPDATE users
                        SET full_name = %s, password_hash = %s, status = 'active', updated_at = now()
                        WHERE id = %s
                        """,
                        (full_name, _hash_password(password), user_id),
                    )
                else:
                    cur.execute(
                        "UPDATE users SET full_name = %s, status = 'active', updated_at = now() WHERE id = %s",
                        (full_name, user_id),
                    )
            else:
                cur.execute(
                    """
                    INSERT INTO users (email, password_hash, full_name, status)
                    VALUES (%s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (email, _hash_password(password or "admin123456"), full_name),
                )
                user_id = str(cur.fetchone()["id"])

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
                    "studio_admin_user_id": user_id,
                    "studio_admin_email": email,
                    "studio_admin_name": full_name,
                }),
                tenant_id,
            ),
        )

    return user_id


def _validate_optional_email(label: str, value: str) -> None:
    """Validate optional email-like values before persisting settings."""

    if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        raise ValueError(f"{label} must be a valid email address.")


def _validate_hex_color(label: str, value: str) -> None:
    """Validate six-digit hex colors used by tenant themes."""

    if value and not re.match(r"^#[0-9a-fA-F]{6}$", value):
        raise ValueError(f"{label} must be a valid 6-digit hex color.")


def _validate_logo_url(value: str) -> None:
    """Validate local or remote logo URLs accepted by Studio Admin."""

    if value and not (value.startswith("/") or re.match(r"^https?://\S+$", value, re.IGNORECASE)):
        raise ValueError("Logo URL must start with /, http://, or https://.")


def _validate_logo_upload(file_storage, ext: str) -> None:
    """Validate tenant logo uploads by size and file signature before saving."""

    filename = file_storage.filename or ""
    safe_name = secure_filename(filename)
    if not safe_name or "/" in filename or "\\" in filename or PurePath(filename).name != filename:
        raise ValueError("Logo filename must not contain path separators.")

    content_type = str(file_storage.mimetype or "").lower()
    expected_mimes = {
        ".jpg": {"image/jpeg"},
        ".jpeg": {"image/jpeg"},
        ".png": {"image/png"},
        ".webp": {"image/webp"},
        ".svg": {"image/svg+xml", "image/svg"},
    }
    if content_type and content_type not in expected_mimes.get(ext, set()):
        raise ValueError("Logo MIME type does not match the selected image type.")

    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size > 5 * 1024 * 1024:
        raise ValueError("Logo file must be 5 MB or smaller.")

    header = stream.read(512)
    stream.seek(0)
    if ext in (".jpg", ".jpeg") and header.startswith(b"\xff\xd8\xff"):
        return
    if ext == ".png" and header.startswith(b"\x89PNG\r\n\x1a\n"):
        return
    if ext == ".webp" and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return
    if ext == ".svg":
        sample = header.lstrip().lower()
        if sample.startswith(b"<svg") or sample.startswith(b"<?xml") or b"<svg" in sample[:200]:
            return
    raise ValueError("Logo file content does not match the selected image type.")


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
DOCUMENT_EXTENSIONS = {".pdf"}
MEDIA_UPLOAD_LIMITS = {
    "student_photo": (IMAGE_EXTENSIONS, 5 * 1024 * 1024),
    "registration_photo": (IMAGE_EXTENSIONS, 5 * 1024 * 1024),
    "portfolio": (IMAGE_EXTENSIONS, 10 * 1024 * 1024),
    "homework": (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS, 10 * 1024 * 1024),
    "sheet_music": (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS, 15 * 1024 * 1024),
    "logo": ({".jpg", ".jpeg", ".png", ".webp", ".svg"}, 5 * 1024 * 1024),
}
MEDIA_MIME_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".svg": {"image/svg+xml", "image/svg"},
}


def _media_root() -> str:
    """Return the tenant media root used by the canonical backend runtime."""

    root = current_app.config.get("MEDIA_DIR")
    if root:
        return str(root)
    return os.path.join(current_app.root_path, "media")


def _ensure_media_schema(conn) -> None:
    """Keep existing local databases compatible with the canonical media model."""

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


def _refresh_tenant_usage(conn, tenant_id: str) -> None:
    """Recalculate tenant storage and student usage from canonical tables."""

    row = fetch_one(
        conn,
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = %s) AS student_count,
            (SELECT count(*) FROM memberships WHERE tenant_id = %s) AS user_count,
            (SELECT COALESCE(ceil(sum(byte_size) / 1048576.0), 0) FROM media_assets WHERE tenant_id = %s) AS storage_used_mb
        """,
        (tenant_id, tenant_id, tenant_id),
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb, calculated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE
            SET student_count = EXCLUDED.student_count,
                user_count = EXCLUDED.user_count,
                storage_used_mb = EXCLUDED.storage_used_mb,
                calculated_at = now()
            """,
            (
                tenant_id,
                row["student_count"] or 0,
                row["user_count"] or 0,
                row["storage_used_mb"] or 0,
            ),
        )


def _media_token(media_asset_id: str) -> str:
    """Return the legacy-compatible token stored by the old CMS data shape."""

    return f"media:{media_asset_id}"


def _media_id_from_token(value: str) -> str:
    """Extract a media asset id from a legacy-compatible media token."""

    text = str(value or "").strip()
    if text.startswith("media:"):
        return text.split(":", 1)[1].strip()
    return ""


def _detect_mime(ext: str) -> str:
    """Return the canonical MIME type persisted for a supported extension."""

    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".gif":
        return "image/gif"
    if ext == ".webp":
        return "image/webp"
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".svg":
        return "image/svg+xml"
    return "application/octet-stream"


def _validate_media_upload(file_storage, *, kind: str) -> tuple[str, bytes, str]:
    """Validate an uploaded tenant media file and return extension, bytes, and MIME."""

    filename = file_storage.filename or ""
    safe_name = secure_filename(filename)
    if not safe_name or "/" in filename or "\\" in filename or PurePath(filename).name != filename:
        raise ValueError("Filename must not contain path separators.")
    ext = os.path.splitext(safe_name)[1].lower()
    allowed_ext, max_bytes = MEDIA_UPLOAD_LIMITS.get(kind, MEDIA_UPLOAD_LIMITS["portfolio"])
    if ext not in allowed_ext:
        allowed = ", ".join(sorted(allowed_ext))
        raise ValueError(f"File type must be one of: {allowed}.")

    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size <= 0:
        raise ValueError("File is empty.")
    if size > max_bytes:
        raise ValueError(f"File must be {max_bytes // (1024 * 1024)} MB or smaller.")

    content_type = str(file_storage.mimetype or "").lower()
    if content_type and content_type != "application/octet-stream" and content_type not in MEDIA_MIME_TYPES.get(ext, set()):
        raise ValueError("MIME type does not match the selected file type.")

    data = stream.read()
    stream.seek(0)
    if ext in (".jpg", ".jpeg") and not data.startswith(b"\xff\xd8\xff"):
        raise ValueError("File content does not match the selected image type.")
    if ext == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("File content does not match the selected image type.")
    if ext == ".gif" and data[:6] not in (b"GIF87a", b"GIF89a"):
        raise ValueError("File content does not match the selected image type.")
    if ext == ".webp" and not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        raise ValueError("File content does not match the selected image type.")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise ValueError("File content does not match the selected PDF type.")
    if ext == ".svg":
        sample = data[:1024].lstrip().lower()
        if not (sample.startswith(b"<svg") or sample.startswith(b"<?xml") or b"<svg" in sample):
            raise ValueError("File content does not match the selected SVG type.")
    return ext, data, _detect_mime(ext)


def _store_media_asset(conn, *, tenant_id: str, file_storage, kind: str, owner_student_id: str | None = None) -> dict:
    """Persist one tenant media file and insert its media_assets row."""

    return store_media_asset(
        conn,
        tenant_id=tenant_id,
        file_storage=file_storage,
        kind=kind,
        owner_student_id=owner_student_id,
    )


def _send_media_asset(conn, *, tenant_id: str, media_asset_id: str):
    """Serve one media asset after tenant ownership has been verified."""

    try:
        return send_media_asset(conn, tenant_id=tenant_id, media_asset_id=media_asset_id)
    except MediaUploadError as exc:
        return _error(str(exc), 404)


def _parse_bool_arg(name: str) -> bool:
    """Return true for common truthy query-string values."""

    return request.args.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_pagination() -> tuple[int, int]:
    """Return bounded `(limit, offset)` values for list endpoints."""

    try:
        limit = int(request.args.get("limit", 500))
        offset = int(request.args.get("offset", 0))
    except (TypeError, ValueError) as exc:
        raise ValueError("limit and offset must be integers.") from exc
    if limit < 1 or limit > 500:
        raise ValueError("limit must be between 1 and 500.")
    if offset < 0:
        raise ValueError("offset must be 0 or greater.")
    return limit, offset


def _student_status(value: str, *, allow_archived: bool = True) -> str:
    """Validate normalized student status values."""

    status = str(value or "active").strip().lower()
    allowed = {"active", "inactive", "trial"}
    if allow_archived:
        allowed.add("archived")
    if status not in allowed:
        raise ValueError(f"Student status must be one of: {', '.join(sorted(allowed))}.")
    return status


def _non_negative_money_cents(payload: dict, key: str, *, fallback: int = 0) -> int:
    """Parse an AUD amount payload field into cents, rejecting negative values."""

    raw = payload.get(key)
    if raw in (None, ""):
        return fallback
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a valid number.") from exc
    if value < 0:
        raise ValueError(f"{key} cannot be negative.")
    return int(round(value * 100))


def _positive_int(payload: dict, key: str, *, fallback: int) -> int:
    """Parse a positive integer payload field."""

    raw = payload.get(key)
    if raw in (None, ""):
        return fallback
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a valid integer.") from exc
    if value <= 0:
        raise ValueError(f"{key} must be greater than 0.")
    return value


def _positive_float(payload: dict, key: str, *, fallback: float) -> float:
    """Parse a positive numeric payload field."""

    raw = payload.get(key)
    if raw in (None, ""):
        return fallback
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a valid number.") from exc
    if value <= 0:
        raise ValueError(f"{key} must be greater than 0.")
    return value


def _active_from_payload(payload: dict, *, fallback: bool = True) -> bool:
    """Parse active/inactive payload fields without truthy string mistakes."""

    if "isActive" in payload:
        value = payload.get("isActive")
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "active"}
        return bool(value)
    status = str(payload.get("status", "active" if fallback else "inactive")).strip().lower()
    return status not in {"inactive", "archived", "paused", "cancelled"}


def _ensure_registration_status_constraint(conn) -> None:
    """Keep registration review columns and states available for local DBs."""

    with conn.cursor() as cur:
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS updated_at timestamptz")
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS student_id uuid REFERENCES students(id) ON DELETE SET NULL")
        cur.execute("ALTER TABLE registrations ADD COLUMN IF NOT EXISTS review_note text NOT NULL DEFAULT ''")
        cur.execute(
            """
            ALTER TABLE registrations
            ADD COLUMN IF NOT EXISTS duplicate_of_registration_id uuid REFERENCES registrations(id) ON DELETE SET NULL
            """
        )
        cur.execute("ALTER TABLE registrations DROP CONSTRAINT IF EXISTS registrations_status_check")
        cur.execute(
            """
            ALTER TABLE registrations
            ADD CONSTRAINT registrations_status_check
            CHECK (status IN ('pending', 'approved', 'rejected', 'duplicate', 'contacted', 'archived'))
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_registrations_tenant_status_submitted
            ON registrations (tenant_id, status, submitted_at DESC)
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_registrations_tenant_student
            ON registrations (tenant_id, student_id)
            WHERE student_id IS NOT NULL
            """
        )
        cur.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_registrations_tenant_duplicate
            ON registrations (tenant_id, duplicate_of_registration_id)
            WHERE duplicate_of_registration_id IS NOT NULL
            """
        )


def _phone_digits(value: str) -> str:
    """Normalize phone-like values for duplicate detection."""

    return re.sub(r"[^0-9]", "", str(value or ""))


def _registration_display_name(first_name: str, last_name: str) -> str:
    """Build the canonical display name used when converting registrations."""

    return f"{first_name} {last_name}".strip()


def _find_matching_student(cur, *, tenant_id: str, first_name: str, last_name: str, mobile: str):
    """Return an active same-tenant student that appears to match a registration."""

    display_name = _registration_display_name(first_name, last_name)
    cur.execute(
        """
        SELECT id, display_name
        FROM students
        WHERE tenant_id = %s
          AND status <> 'archived'
          AND regexp_replace(mobile, '[^0-9]', '', 'g') = %s
          AND (
                lower(display_name) = lower(%s)
             OR (lower(first_name) = lower(%s) AND lower(last_name) = lower(%s))
          )
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (tenant_id, _phone_digits(mobile), display_name, first_name, last_name),
    )
    return cur.fetchone()


def _find_pending_registration(cur, *, tenant_id: str, first_name: str, last_name: str, mobile: str):
    """Return an existing pending/contacted registration for the same tenant/person."""

    cur.execute(
        """
        SELECT id
        FROM registrations
        WHERE tenant_id = %s
          AND status IN ('pending', 'contacted')
          AND regexp_replace(mobile, '[^0-9]', '', 'g') = %s
          AND lower(first_name) = lower(%s)
          AND lower(last_name) = lower(%s)
        ORDER BY submitted_at DESC
        LIMIT 1
        """,
        (tenant_id, _phone_digits(mobile), first_name, last_name),
    )
    return cur.fetchone()


def _workspace_for(slug: str, name: str) -> str:
    """Create tenant workspace files and return the relative path."""

    try:
        return ensure_tenant_workspace(current_app.config["PROJECT_ROOT"], slug, name)
    except WorkspaceError as exc:
        raise ValueError(str(exc)) from exc


@api_v1.route("/health", methods=["GET"])
def health():
    """Health check for the StudioSaaS v1 surface."""

    return jsonify({"ok": True, "service": "StudioSaaS API", "version": "v1"})


def _tenant_response(conn):
    cfg = load_config()
    slug, source = slug_from_request(request, cfg)
    tenant = resolve_tenant(conn, slug, source)
    row = fetch_one(
        conn,
        """
        SELECT t.id, t.name, t.slug, t.status, t.plan_code, t.primary_color,
               t.secondary_color, t.welcome_message, t.contact_phone,
               t.contact_email, t.address, t.timezone,
               t.settings->>'logo_url' AS logo_url,
               t.settings->>'cms_layout' AS cms_layout,
               t.settings->>'show_welcome' AS show_welcome,
               COALESCE(t.settings->>'category', 'general') AS category,
               t.settings->>'category_label' AS category_label,
               t.settings->>'slogan' AS slogan,
               t.settings->'registration_profile' AS registration_profile,
               t.settings->'copy_pack' AS copy_pack,
               s.status AS subscription_status, s.starts_at, s.ends_at,
               s.trial_ends_at, s.current_period_ends_at
        FROM tenants t
        LEFT JOIN subscriptions s ON s.tenant_id = t.id
        WHERE t.id = %s
        """,
        (tenant.tenant_id,),
    )
    return row


def _tenant_context(conn):
    """Resolve the tenant for a tenant-scoped request."""

    cfg = load_config()
    slug, source = slug_from_request(request, cfg)
    return resolve_tenant(conn, slug, source)


@api_v1.route("/tenant", methods=["GET"])
@auth_required
def get_tenant():
    """Return the current tenant's public and operational settings."""

    with connect() as conn:
        row = _tenant_response(conn)
    return jsonify({"tenant": row, "settings": row})


@api_v1.route("/tenant", methods=["PATCH"])
@tenant_admin_required

def update_tenant():
    """Update current tenant branding, contact details, and plan metadata."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        current = fetch_one(
            conn,
            """
            SELECT name, plan_code, primary_color, secondary_color, welcome_message,
                   contact_phone, contact_email, address, timezone,
                   settings,
                   settings->>'logo_url' AS logo_url
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        current_settings = dict(current["settings"] or {})
        plan_code = _clean_text(payload, "planCode", current["plan_code"]).lower()
        logo_url = _clean_text(payload, "logoUrl", current["logo_url"] or "")
        primary_color = _clean_text(payload, "primaryColor", current["primary_color"])
        secondary_color = _clean_text(payload, "secondaryColor", current["secondary_color"])
        contact_email = _clean_text(payload, "contactEmail", _clean_text(payload, "email", current["contact_email"])).lower()
        cms_layout = _clean_text(payload, "cmsLayout", current_settings.get("cms_layout", "bar")).lower()
        category = _normalize_category(_clean_text(payload, "category", current_settings.get("category", "general")))
        preset = _preset_for(category)
        slogan = _clean_text(payload, "slogan", current_settings.get("slogan", preset["slogan"]))
        registration_profile = _normalize_registration_profile(
            payload.get("registrationProfile", current_settings.get("registration_profile")),
            category,
        )
        copy_pack = _normalize_copy_pack(payload.get("copyPack", current_settings.get("copy_pack")), category)
        show_welcome = payload.get("showWelcome", current_settings.get("show_welcome", "true"))
        if isinstance(show_welcome, str):
            show_welcome = show_welcome.strip().lower() != "false"
        else:
            show_welcome = bool(show_welcome)
        try:
            _validate_logo_url(logo_url)
            _validate_hex_color("Primary color", primary_color)
            _validate_hex_color("Secondary color", secondary_color)
            _validate_optional_email("Contact email", contact_email)
            if cms_layout not in {"bar", "hero", "compact"}:
                raise ValueError("CMS layout must be one of: bar, hero, compact.")
        except ValueError as exc:
            return _error(str(exc))
        current_settings.update(
            {
                "logo_url": logo_url,
                "logoUrl": logo_url,
                "cms_layout": cms_layout,
                "cmsLayout": cms_layout,
                "show_welcome": show_welcome,
                "showWelcome": show_welcome,
                "category": category,
                "category_label": preset["label"],
                "slogan": slogan,
                "registration_profile": registration_profile,
                "copy_pack": copy_pack,
            }
        )
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM plans WHERE code = %s", (plan_code,))
            if not cur.fetchone():
                return _error(f"Plan '{plan_code}' was not found.", 404)
            cur.execute(
                """
                UPDATE tenants
                SET name = %s,
                    plan_code = %s,
                    primary_color = %s,
                    secondary_color = %s,
                    welcome_message = %s,
                    contact_phone = %s,
                    contact_email = %s,
                    address = %s,
                    timezone = %s,
                    settings = %s::jsonb,
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    _clean_text(payload, "name", current["name"]),
                    plan_code,
                    primary_color,
                    secondary_color,
                    _clean_text(payload, "welcomeMessage", _clean_text(payload, "welcome", current["welcome_message"])),
                    _clean_text(payload, "contactPhone", _clean_text(payload, "phone", current["contact_phone"])),
                    contact_email,
                    _clean_text(payload, "address", current["address"]),
                    _clean_text(payload, "timezone", current["timezone"]),
                    json.dumps(current_settings),
                    tenant.tenant_id,
                ),
            )
            cur.execute(
                """
                INSERT INTO subscriptions (tenant_id, plan_code, status, starts_at, ends_at)
                VALUES (%s, %s, 'active', now(), NULL)
                ON CONFLICT (tenant_id) DO UPDATE
                SET plan_code = EXCLUDED.plan_code,
                    updated_at = now()
                """,
                (tenant.tenant_id, plan_code),
            )
        _audit(conn, tenant_id=tenant.tenant_id, action="tenant.updated", resource_type="tenant")
        conn.commit()
        row = _tenant_response(conn)
    return jsonify({"tenant": row})


@api_v1.route("/tenant/brand", methods=["GET"])
@auth_required
def get_tenant_brand():
    """Return branding used by Studio Admin and Parent Portal."""

    with connect() as conn:
        row = _tenant_response(conn)
    return jsonify(
        {
            "brand": {
                "name": row["name"],
                "slug": row["slug"],
                "primaryColor": row["primary_color"],
                "secondaryColor": row["secondary_color"],
                "welcomeMessage": row["welcome_message"],
                "contactPhone": row["contact_phone"],
                "contactEmail": row["contact_email"],
                "address": row["address"],
                "logoUrl": row["logo_url"],
                "cmsLayout": row["cms_layout"] or "bar",
                "showWelcome": row["show_welcome"] != "false",
                "category": row["category"] or "general",
                "categoryLabel": row["category_label"] or _preset_for(row["category"] or "general")["label"],
                "slogan": row["slogan"] or _preset_for(row["category"] or "general")["slogan"],
                "registrationProfile": row["registration_profile"] or _default_registration_profile(row["category"] or "general"),
                "copyPack": row["copy_pack"] or _preset_for(row["category"] or "general")["copy_pack"],
            }
        }
    )


@api_v1.route("/students", methods=["GET"])
@auth_required
def list_students():
    """List students for the resolved tenant."""

    try:
        limit, offset = _parse_pagination()
    except ValueError as exc:
        return _error(str(exc))
    include_archived = _parse_bool_arg("includeArchived")
    search = request.args.get("search", "").strip().lower()
    status = request.args.get("status", "").strip().lower()
    low_balance = _parse_bool_arg("low_balance") or _parse_bool_arg("lowBalance")
    if status:
        try:
            _student_status(status)
        except ValueError as exc:
            return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT s.id, s.display_name, s.first_name, s.last_name, s.status,
                   s.mobile, s.email, s.tags, s.created_at, s.updated_at,
                   COALESCE(ca.balance, 0)::float AS balance
            FROM students
            s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s
              AND (%s OR s.status <> 'archived')
              AND (%s = '' OR s.status = %s)
              AND (%s = '' OR lower(s.display_name) LIKE %s OR regexp_replace(s.mobile, '[^0-9]', '', 'g') LIKE %s)
              AND (%s = false OR COALESCE(ca.balance, 0) <= COALESCE(ca.low_balance_threshold, 2))
            ORDER BY lower(display_name), created_at DESC
            LIMIT %s OFFSET %s
            """,
            (
                tenant.tenant_id,
                include_archived,
                status,
                status,
                search,
                f"%{search}%",
                f"%{''.join(ch for ch in search if ch.isdigit()) or search}%",
                low_balance,
                limit,
                offset,
            ),
        )
    return jsonify({"students": rows})


@api_v1.route("/students/<student_id>", methods=["GET"])
@auth_required
def get_student(student_id: str):
    """Return one student with credit summary for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            SELECT s.id, s.display_name, s.first_name, s.last_name, s.status,
                   s.birthday, s.parent_name, s.mobile, s.email, s.wechat,
                   s.tags, s.notes, COALESCE(ca.balance, 0)::float AS balance
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s AND s.id = %s
            """,
            (tenant.tenant_id, student_id),
        )
    if not row:
        return jsonify({"error": "not_found", "message": "Student was not found."}), 404
    return jsonify({"student": row})


@api_v1.route("/students/<student_id>/credits", methods=["GET"])
@auth_required
def get_student_credits(student_id: str):
    """Return balance account and recent credit transactions for one student."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        account = fetch_one(
            conn,
            """
            SELECT id, balance::float AS balance,
                   low_balance_threshold::float AS low_balance_threshold,
                   updated_at
            FROM credit_accounts
            WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (tenant.tenant_id, student_id),
        )
        transactions = fetch_all(
            conn,
            """
            SELECT id, transaction_type, amount::float AS amount,
                   balance_after::float AS balance_after, fee_aud_cents,
                   note, occurred_at
            FROM credit_transactions
            WHERE tenant_id = %s AND student_id = %s
            ORDER BY occurred_at DESC
            LIMIT 50
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"account": account, "transactions": transactions})


@api_v1.route("/courses", methods=["GET"])
@auth_required
def list_courses():
    """List courses for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, name, description, category, age_range,
                   duration_minutes, credit_unit,
                   default_credit_debit::float AS default_credit_debit,
                   price_aud_cents, is_active
            FROM courses
            WHERE tenant_id = %s
            ORDER BY is_active DESC, lower(name)
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"courses": rows})


@api_v1.route("/courses", methods=["POST"])
@tenant_admin_required

def create_course():
    """Create a course for the resolved tenant."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    try:
        name = _clean_text(payload, "name")
        if not name:
            raise ValueError("Course name is required.")
        duration_minutes = _positive_int(payload, "durationMinutes", fallback=60)
        default_credit_debit = _positive_float(payload, "defaultCreditDebit", fallback=1)
        price_aud_cents = _non_negative_money_cents(payload, "priceAud")
        is_active = _active_from_payload(payload)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO courses (
                    tenant_id, name, description, category, age_range,
                    duration_minutes, credit_unit, default_credit_debit,
                    price_aud_cents, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, description, category, age_range,
                          duration_minutes, credit_unit,
                          default_credit_debit::float AS default_credit_debit,
                          price_aud_cents, is_active
                """,
                (
                    tenant.tenant_id,
                    name,
                    _clean_text(payload, "description"),
                    _clean_text(payload, "category"),
                    _clean_text(payload, "ageRange"),
                    duration_minutes,
                    _clean_text(payload, "creditUnit", "credits"),
                    default_credit_debit,
                    price_aud_cents,
                    is_active,
                ),
            )
            course = cur.fetchone()
            course_id = course["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="course.created", resource_type="course", resource_id=course_id)
        conn.commit()
    return jsonify({"ok": True, "id": course_id, "course": course}), 201


@api_v1.route("/courses/<course_id>", methods=["PATCH", "DELETE"])
@tenant_admin_required

def mutate_course(course_id: str):
    """Update or delete a course for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE courses
                    SET is_active = false, updated_at = now()
                    WHERE tenant_id = %s AND id = %s
                    RETURNING id, name, description, category, age_range,
                              duration_minutes, credit_unit,
                              default_credit_debit::float AS default_credit_debit,
                              price_aud_cents, is_active
                    """,
                    (tenant.tenant_id, course_id),
                )
                course = cur.fetchone()
                if not course:
                    return _error("Course was not found.", 404)
            _audit(conn, tenant_id=tenant.tenant_id, action="course.archived", resource_type="course", resource_id=course_id)
            conn.commit()
            return jsonify({"ok": True, "id": course_id, "course": course})
        try:
            payload = _json_payload()
            duration_minutes = _positive_int(payload, "durationMinutes", fallback=60)
            default_credit_debit = _positive_float(payload, "defaultCreditDebit", fallback=1)
            price_aud_cents = _non_negative_money_cents(payload, "priceAud")
            is_active = _active_from_payload(payload)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE courses
                SET name = COALESCE(NULLIF(%s, ''), name),
                    description = %s,
                    category = %s,
                    age_range = %s,
                    duration_minutes = %s,
                    credit_unit = %s,
                    default_credit_debit = %s,
                    price_aud_cents = %s,
                    is_active = %s,
                    updated_at = now()
                WHERE tenant_id = %s AND id = %s
                RETURNING id, name, description, category, age_range,
                          duration_minutes, credit_unit,
                          default_credit_debit::float AS default_credit_debit,
                          price_aud_cents, is_active
                """,
                (
                    _clean_text(payload, "name"),
                    _clean_text(payload, "description"),
                    _clean_text(payload, "category"),
                    _clean_text(payload, "ageRange"),
                    duration_minutes,
                    _clean_text(payload, "creditUnit", "credits"),
                    default_credit_debit,
                    price_aud_cents,
                    is_active,
                    tenant.tenant_id,
                    course_id,
                ),
            )
            course = cur.fetchone()
            if not course:
                return _error("Course was not found.", 404)
        _audit(conn, tenant_id=tenant.tenant_id, action="course.updated", resource_type="course", resource_id=course_id)
        conn.commit()
    return jsonify({"ok": True, "id": course_id, "course": course})


@api_v1.route("/packages", methods=["GET"])
@auth_required
def list_packages():
    """List course packages for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, name, credits::float AS credits, price_aud_cents,
                   expires_after_days, is_active
            FROM packages
            WHERE tenant_id = %s
            ORDER BY is_active DESC, price_aud_cents, lower(name)
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"packages": rows})


@api_v1.route("/packages", methods=["POST"])
@tenant_admin_required

def create_package():
    """Create a package for the resolved tenant."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    try:
        name = _clean_text(payload, "name")
        if not name:
            raise ValueError("Package name is required.")
        credits = _positive_float(payload, "credits", fallback=1)
        price_aud_cents = _non_negative_money_cents(payload, "priceAud")
        expires_after_days = payload.get("expiresAfterDays") or None
        if expires_after_days not in (None, ""):
            expires_after_days = _positive_int(payload, "expiresAfterDays", fallback=30)
        is_active = _active_from_payload(payload)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO packages (
                    tenant_id, name, credits, price_aud_cents,
                    expires_after_days, is_active
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, name, credits::float AS credits, price_aud_cents,
                          expires_after_days, is_active
                """,
                (
                    tenant.tenant_id,
                    name,
                    credits,
                    price_aud_cents,
                    expires_after_days,
                    is_active,
                ),
            )
            package = cur.fetchone()
            package_id = package["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="package.created", resource_type="package", resource_id=package_id)
        conn.commit()
    return jsonify({"ok": True, "id": package_id, "package": package}), 201


@api_v1.route("/packages/<package_id>", methods=["PATCH", "DELETE"])
@tenant_admin_required

def mutate_package(package_id: str):
    """Update or delete a package for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE packages
                    SET is_active = false
                    WHERE tenant_id = %s AND id = %s
                    RETURNING id, name, credits::float AS credits, price_aud_cents,
                              expires_after_days, is_active
                    """,
                    (tenant.tenant_id, package_id),
                )
                package = cur.fetchone()
                if not package:
                    return _error("Package was not found.", 404)
            _audit(conn, tenant_id=tenant.tenant_id, action="package.archived", resource_type="package", resource_id=package_id)
            conn.commit()
            return jsonify({"ok": True, "id": package_id, "package": package})
        try:
            payload = _json_payload()
            credits = _positive_float(payload, "credits", fallback=1)
            price_aud_cents = _non_negative_money_cents(payload, "priceAud")
            expires_after_days = payload.get("expiresAfterDays") or None
            if expires_after_days not in (None, ""):
                expires_after_days = _positive_int(payload, "expiresAfterDays", fallback=30)
            is_active = _active_from_payload(payload)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE packages
                SET name = COALESCE(NULLIF(%s, ''), name),
                    credits = %s,
                    price_aud_cents = %s,
                    expires_after_days = %s,
                    is_active = %s
                WHERE tenant_id = %s AND id = %s
                RETURNING id, name, credits::float AS credits, price_aud_cents,
                          expires_after_days, is_active
                """,
                (
                    _clean_text(payload, "name"),
                    credits,
                    price_aud_cents,
                    expires_after_days,
                    is_active,
                    tenant.tenant_id,
                    package_id,
                ),
            )
            package = cur.fetchone()
            if not package:
                return _error("Package was not found.", 404)
        _audit(conn, tenant_id=tenant.tenant_id, action="package.updated", resource_type="package", resource_id=package_id)
        conn.commit()
    return jsonify({"ok": True, "id": package_id, "package": package})


@api_v1.route("/registrations", methods=["GET"])
@auth_required
def list_registrations():
    """List recent public registration submissions for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, status, first_name, last_name, parent_name, mobile,
                   email, message, submitted_at, updated_at, reviewed_at,
                   reviewed_by_user_id, student_id, duplicate_of_registration_id,
                   review_note
            FROM registrations
            WHERE tenant_id = %s
            ORDER BY submitted_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"registrations": rows})

@api_v1.route("/registrations/<registration_id>", methods=["PATCH"])
@tenant_admin_required

def update_registration_status(registration_id: str):
    """Update the status of a registration (approve/reject/archive)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()
        new_status = _clean_text(payload, "status", "").lower().strip()
        convert_to_student = bool(payload.get("convertToStudent", payload.get("convert_to_student", False)))
        review_note = _clean_text(payload, "reviewNote", _clean_text(payload, "decisionReason", ""))[:500]

        if new_status not in ("pending", "contacted", "approved", "rejected", "duplicate", "archived"):
            return _error("status must be one of: pending, contacted, approved, rejected, duplicate, archived.")
        if new_status in {"rejected", "archived"} and not review_note:
            return _error("reviewNote is required when rejecting or archiving a registration.")

        with conn.cursor() as cur:
            _ensure_registration_status_constraint(conn)
            created_student_id = None
            linked_student_id = None
            cur.execute(
                """
                SELECT id, first_name, last_name, parent_name, mobile, email, message,
                       payload, student_id
                FROM registrations
                WHERE tenant_id = %s AND id = %s
                """,
                (tenant.tenant_id, registration_id),
            )
            reg = cur.fetchone()
            if not reg:
                return _error("Registration not found.", 404)

            if convert_to_student or new_status == "approved":
                display_name = f"{reg['first_name']} {reg['last_name']}".strip()
                existing_student = _find_matching_student(
                    cur,
                    tenant_id=tenant.tenant_id,
                    first_name=reg["first_name"],
                    last_name=reg["last_name"],
                    mobile=reg["mobile"],
                )
                if existing_student:
                    created_student_id = str(existing_student["id"])
                    linked_student_id = created_student_id
                else:
                    cur.execute(
                        """
                        INSERT INTO students (
                            tenant_id, first_name, last_name, display_name, status,
                            parent_name, mobile, email, notes, tags
                        )
                        VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, ARRAY[]::text[])
                        RETURNING id
                        """,
                        (
                            tenant.tenant_id,
                            reg["first_name"],
                            reg["last_name"],
                            display_name,
                            reg["parent_name"],
                            reg["mobile"],
                            reg["email"],
                            reg["message"],
                        ),
                    )
                    created_student_id = str(cur.fetchone()["id"])
                    linked_student_id = created_student_id
                    _ensure_default_credit_account(cur, tenant.tenant_id, created_student_id)
            elif reg.get("student_id"):
                linked_student_id = str(reg["student_id"])

            actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
            cur.execute(
                """
                UPDATE registrations
                SET status = %s,
                    student_id = COALESCE(%s, student_id),
                    reviewed_by_user_id = %s,
                    reviewed_at = CASE WHEN %s <> 'pending' THEN now() ELSE reviewed_at END,
                    review_note = CASE WHEN %s <> '' THEN %s ELSE review_note END,
                    updated_at = now()
                WHERE tenant_id = %s AND id = %s
                RETURNING id, status, student_id, review_note
                """,
                (
                    new_status,
                    linked_student_id,
                    actor_user_id,
                    new_status,
                    review_note,
                    review_note,
                    tenant.tenant_id,
                    registration_id,
                ),
            )
            updated = cur.fetchone()

        if not updated:
            return _error("Registration not found.", 404)

        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"registration.{new_status}",
            resource_type="registration",
            resource_id=registration_id,
            metadata={"student_id": linked_student_id, "review_note": review_note},
        )
        conn.commit()

    response = {
        "ok": True,
        "registration": {
            "id": updated["id"],
            "status": updated["status"],
            "student_id": str(updated["student_id"]) if updated.get("student_id") else None,
            "review_note": updated["review_note"],
        },
    }
    if created_student_id:
        response["student_id"] = created_student_id
    return jsonify(response)


@api_v1.route("/portfolio", methods=["GET"])
@auth_required
def list_portfolio():
    """List recent portfolio items for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.title, p.description, p.artwork_date, p.visibility,
                   p.created_at, s.display_name AS student_name,
                   m.storage_key, m.mime_type
            FROM portfolio_items p
            JOIN students s ON s.id = p.student_id
            JOIN media_assets m ON m.id = p.media_asset_id
            WHERE p.tenant_id = %s
            ORDER BY p.created_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"portfolio": rows})


@api_v1.route("/dashboard", methods=["GET"])
@auth_required
def tenant_dashboard():
    """Return dashboard metrics for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM students WHERE tenant_id = %s) AS students,
                (SELECT count(*) FROM students WHERE tenant_id = %s AND status = 'active') AS active_students,
                (SELECT count(*) FROM registrations WHERE tenant_id = %s AND status = 'pending') AS pending_registrations,
                (SELECT count(*) FROM portfolio_items WHERE tenant_id = %s) AS portfolio_items,
                (SELECT count(*) FROM credit_accounts WHERE tenant_id = %s AND course_id IS NULL AND balance <= low_balance_threshold) AS low_balance
            """,
            (
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
            ),
        )
    return jsonify({"dashboard": row})


@api_v1.route("/public/<tenant_slug>/brand", methods=["GET"])
def public_brand(tenant_slug: str):
    """Return public brand settings for registration and parent views."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        row = fetch_one(
            conn,
            """
            SELECT name, slug, primary_color, secondary_color, welcome_message,
                   contact_phone, contact_email, address,
                   settings->>'logo_url' AS logo_url,
                   settings->>'cms_layout' AS cms_layout,
                   settings->>'show_welcome' AS show_welcome,
                   COALESCE(settings->>'category', 'general') AS category,
                   settings->>'category_label' AS category_label,
                   settings->>'slogan' AS slogan,
                   settings->'registration_profile' AS registration_profile,
                   settings->'copy_pack' AS copy_pack
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
    category = row["category"] or "general"
    preset = _preset_for(category)
    row["category_label"] = row["category_label"] or preset["label"]
    row["slogan"] = row["slogan"] or preset["slogan"]
    row["registration_profile"] = row["registration_profile"] or _default_registration_profile(category)
    row["copy_pack"] = row["copy_pack"] or preset["copy_pack"]
    row["primaryColor"] = row["primary_color"]
    row["secondaryColor"] = row["secondary_color"]
    row["welcomeMessage"] = row["welcome_message"]
    row["contactPhone"] = row["contact_phone"]
    row["contactEmail"] = row["contact_email"]
    row["logoUrl"] = row["logo_url"]
    row["cmsLayout"] = row["cms_layout"]
    row["showWelcome"] = row["show_welcome"]
    row["categoryLabel"] = row["category_label"]
    row["registrationProfile"] = row["registration_profile"]
    row["copyPack"] = row["copy_pack"]
    return jsonify({"brand": row})


@api_v1.route("/public/<tenant_slug>/balance-query", methods=["POST"])
def public_balance_query(tenant_slug: str):
    """Lookup a student's balance for the public parent portal."""

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip().lower()
    phone = "".join(ch for ch in str(payload.get("phone") or "") if ch.isdigit())
    if not name or not phone:
        return jsonify({"match": False, "error": "name_and_phone_required"}), 400
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        row = fetch_one(
            conn,
            """
            SELECT s.display_name, COALESCE(ca.balance, 0)::float AS balance
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s
              AND s.status <> 'archived'
              AND regexp_replace(s.mobile, '[^0-9]', '', 'g') = %s
              AND (
                lower(s.display_name) = %s
                OR lower(s.first_name) = %s
                OR lower(s.last_name) = %s
              )
            ORDER BY lower(s.display_name)
            LIMIT 1
            """,
            (tenant.tenant_id, phone, name, name, name),
        )
    if not row:
        return jsonify({"match": False})
    return jsonify(
        {
            "match": True,
            "name": row["display_name"],
            "balance": row["balance"],
            "total_checkins": 0,
        }
    )


@api_v1.route("/public/<tenant_slug>/registration-media", methods=["POST"])
def public_registration_media_upload(tenant_slug: str):
    """Upload a tenant-scoped registration photo before the registration is submitted."""

    client_key = f"registration-media:{request.remote_addr or 'unknown'}"
    now = time.time()
    _public_rate_limit[client_key] = [t for t in _public_rate_limit.get(client_key, []) if now - t < 60]
    if len(_public_rate_limit[client_key]) >= 5:
        return _error("Too many uploads. Please wait a moment.", 429)
    _public_rate_limit[client_key].append(now)

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        try:
            media = _store_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                file_storage=f,
                kind="registration_photo",
            )
        except MediaUploadError as exc:
            return _media_error(exc)
        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action="registration_photo.uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={"byte_size": media["byte_size"]},
        )
    media_id = str(media["id"])
    return jsonify(
        {
            "ok": True,
            "mediaAssetId": media_id,
            "filename": _media_token(media_id),
            "url": f"/v1/public/{tenant_slug}/media/{media_id}",
        }
    )


@api_v1.route("/public/<tenant_slug>/portfolio-token", methods=["POST"])
def public_portfolio_token(tenant_slug: str):
    """Return a short-lived token and tenant-scoped portfolio metadata."""

    client_key = f"portfolio-token:{request.remote_addr or 'unknown'}"
    now = time.time()
    _public_rate_limit[client_key] = [t for t in _public_rate_limit.get(client_key, []) if now - t < 60]
    if len(_public_rate_limit[client_key]) >= 10:
        return _error("Too many queries. Please wait a moment.", 429)
    _public_rate_limit[client_key].append(now)

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip().lower()
    phone = "".join(ch for ch in str(payload.get("phone") or "") if ch.isdigit())
    if not name or not phone:
        return jsonify({"ok": False}), 400
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        student = fetch_one(
            conn,
            """
            SELECT id
            FROM students
            WHERE tenant_id = %s
              AND status <> 'archived'
              AND regexp_replace(mobile, '[^0-9]', '', 'g') = %s
              AND (
                lower(display_name) = %s
                OR lower(first_name) = %s
                OR lower(last_name) = %s
              )
            ORDER BY lower(display_name)
            LIMIT 1
            """,
            (tenant.tenant_id, phone, name, name, name),
        )
        if not student:
            return jsonify({"ok": False})
        raw_token = hashlib.sha256(f"{_uuid.uuid4()}:{time.time()}".encode("utf-8")).hexdigest()
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO share_tokens (tenant_id, student_id, token_hash, scope, expires_at)
                VALUES (%s, %s, %s, 'student_portfolio', now() + interval '1 hour')
                """,
                (tenant.tenant_id, student["id"], token_hash),
            )
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.media_asset_id, p.description, p.artwork_date, p.created_at
            FROM portfolio_items p
            JOIN media_assets m ON m.id = p.media_asset_id AND m.tenant_id = p.tenant_id
            WHERE p.tenant_id = %s AND p.student_id = %s
            ORDER BY p.created_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id, student["id"]),
        )
    portfolio = [
        {
            "id": str(row["id"]),
            "filename": _media_token(str(row["media_asset_id"])),
            "mediaUrl": f"/v1/public/{tenant_slug}/media/{row['media_asset_id']}?token={raw_token}",
            "date": str(row["artwork_date"] or row["created_at"].date()),
            "note": row["description"] or "",
        }
        for row in rows
    ]
    return jsonify({"ok": True, "sid": str(student["id"]), "token": raw_token, "portfolio": portfolio})


@api_v1.route("/public/<tenant_slug>/media/<media_asset_id>", methods=["GET"])
def public_media_asset(tenant_slug: str, media_asset_id: str):
    """Serve token-protected tenant media for public student portfolio views."""

    raw_token = request.args.get("token", "")
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        asset = fetch_one(
            conn,
            "SELECT asset_type FROM media_assets WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, media_asset_id),
        )
        if not asset:
            return _error("Media asset was not found.", 404)
        if asset["asset_type"] == "logo":
            return _send_media_asset(conn, tenant_id=tenant.tenant_id, media_asset_id=media_asset_id)
        if not raw_token:
            return _error("Media token is required.", 401)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        allowed = fetch_one(
            conn,
            """
            SELECT 1
            FROM share_tokens st
            JOIN media_assets m
              ON m.tenant_id = st.tenant_id
             AND m.owner_student_id = st.student_id
            WHERE st.tenant_id = %s
              AND st.token_hash = %s
              AND st.scope = 'student_portfolio'
              AND st.expires_at > now()
              AND st.revoked_at IS NULL
              AND m.id = %s
            LIMIT 1
            """,
            (tenant.tenant_id, token_hash, media_asset_id),
        )
        if not allowed:
            return _error("Media asset was not found.", 404)
        return _send_media_asset(conn, tenant_id=tenant.tenant_id, media_asset_id=media_asset_id)


@api_v1.route("/public/<tenant_slug>/registrations", methods=["POST"])
def public_create_registration(tenant_slug: str):
    """Create a public registration for a tenant-backed register page.

    Rate-limited to 5 requests per minute per client IP to prevent spam.
    """

    # Simple rate limiting: 5 requests per minute per IP
    client_ip = request.remote_addr or "unknown"
    now = time.time()
    if client_ip not in _public_rate_limit:
        _public_rate_limit[client_ip] = []
    # Prune entries older than 60 seconds
    _public_rate_limit[client_ip] = [
        t for t in _public_rate_limit[client_ip] if now - t < 60
    ]
    if len(_public_rate_limit[client_ip]) >= 5:
        return _error("Too many registration attempts. Please wait a moment.", 429)
    _public_rate_limit[client_ip].append(now)

    payload = request.get_json(silent=True) or {}
    first_name = str(
        payload.get("firstName")
        or payload.get("first_name")
        or payload.get("studentFirstName")
        or payload.get("student_first_name")
        or ""
    ).strip()[:80]
    last_name = str(
        payload.get("lastName")
        or payload.get("last_name")
        or payload.get("studentLastName")
        or payload.get("student_last_name")
        or ""
    ).strip()[:80]
    parent_name = str(payload.get("parentName") or payload.get("parent_name") or "").strip()[:120]
    mobile = re.sub(r"[^0-9+]", "", str(payload.get("mobile") or payload.get("phone") or ""))[:40]
    email = str(payload.get("email") or "").strip().lower()[:120]
    message = str(payload.get("message") or payload.get("notes") or "").strip()[:500]
    if not first_name or not mobile:
        return _error("firstName and mobile are required.")
    try:
        _validate_optional_email("email", email)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        _ensure_registration_status_constraint(conn)
        with conn.cursor() as cur:
            existing_student = _find_matching_student(
                cur,
                tenant_id=tenant.tenant_id,
                first_name=first_name,
                last_name=last_name,
                mobile=mobile,
            )
            duplicate_registration = None
            if not existing_student:
                duplicate_registration = _find_pending_registration(
                    cur,
                    tenant_id=tenant.tenant_id,
                    first_name=first_name,
                    last_name=last_name,
                    mobile=mobile,
                )
            if existing_student or duplicate_registration:
                duplicate_kind = "student" if existing_student else "pending"
                review_note = (
                    "Matched existing active student."
                    if existing_student
                    else "Matched an existing pending registration."
                )
                cur.execute(
                    """
                    INSERT INTO registrations (
                        tenant_id, status, first_name, last_name, parent_name,
                        mobile, email, message, payload, student_id,
                        duplicate_of_registration_id, review_note
                    )
                    VALUES (
                        %s, 'duplicate', %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        tenant.tenant_id,
                        first_name,
                        last_name,
                        parent_name,
                        mobile,
                        email,
                        message,
                        json.dumps(payload),
                        str(existing_student["id"]) if existing_student else None,
                        str(duplicate_registration["id"]) if duplicate_registration else None,
                        review_note,
                    ),
                )
                registration_id = cur.fetchone()["id"]
                _audit(
                    conn,
                    tenant_id=tenant.tenant_id,
                    action="registration.duplicate_detected",
                    resource_type="registration",
                    resource_id=registration_id,
                    metadata={
                        "duplicate": duplicate_kind,
                        "student_id": str(existing_student["id"]) if existing_student else None,
                        "duplicate_of_registration_id": str(duplicate_registration["id"]) if duplicate_registration else None,
                    },
                )
                conn.commit()
                return jsonify(
                    {
                        "ok": False,
                        "success": False,
                        "duplicate": duplicate_kind,
                        "registration_id": registration_id,
                        "id": registration_id,
                        "student_id": str(existing_student["id"]) if existing_student else None,
                        "duplicate_of_registration_id": str(duplicate_registration["id"]) if duplicate_registration else None,
                        "error": (
                            "This student already exists. Please use the balance/portfolio lookup."
                            if existing_student
                            else "This registration is already waiting for review."
                        ),
                    }
                )
            cur.execute(
                """
                INSERT INTO registrations (
                    tenant_id, status, first_name, last_name, parent_name,
                    mobile, email, message, payload
                )
                VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    first_name,
                    last_name,
                    parent_name,
                    mobile,
                    email,
                    message,
                    json.dumps(payload),
                ),
            )
            registration_id = cur.fetchone()["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="registration.created", resource_type="registration", resource_id=registration_id)
        conn.commit()
    return jsonify({
        "ok": True,
        "success": True,
        "registration_id": registration_id,
        "id": registration_id,
        "message": "Registration received. The studio will contact you soon.",
    })


def _legacy_name_parts(display_name: str) -> tuple[str, str]:
    """Split a legacy display name into first and last fields."""

    parts = str(display_name or "").strip().split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _legacy_data_for_tenant(conn, tenant_id: str) -> dict:
    """Build the legacy CMS JSON shape from tenant-scoped PostgreSQL rows."""

    students = fetch_all(
        conn,
        """
        SELECT s.id, s.first_name, s.last_name, s.display_name, s.status,
               s.birthday, s.parent_name, s.mobile, s.email, s.wechat,
               s.tags, s.notes, s.created_at, s.student_photo_asset_id,
               COALESCE(ca.balance, 0)::float AS balance
        FROM students s
        LEFT JOIN LATERAL (
            SELECT balance
            FROM credit_accounts ca
            WHERE ca.tenant_id = s.tenant_id
              AND ca.student_id = s.id
              AND ca.course_id IS NULL
            ORDER BY ca.updated_at DESC
            LIMIT 1
        ) ca ON true
        WHERE s.tenant_id = %s
        ORDER BY lower(s.display_name)
        """,
        (tenant_id,),
    )
    portfolio_rows = fetch_all(
        conn,
        """
        SELECT p.id, p.student_id, p.media_asset_id, p.description, p.artwork_date,
               p.created_at
        FROM portfolio_items p
        JOIN media_assets m ON m.id = p.media_asset_id AND m.tenant_id = p.tenant_id
        WHERE p.tenant_id = %s
        ORDER BY p.created_at DESC
        """,
        (tenant_id,),
    )
    portfolio_by_student: dict[str, list[dict]] = {}
    for row in portfolio_rows:
        student_key = str(row["student_id"])
        portfolio_by_student.setdefault(student_key, []).append(
            {
                "id": str(row["id"]),
                "filename": _media_token(str(row["media_asset_id"])),
                "date": str(row["artwork_date"] or row["created_at"].date()),
                "note": row["description"] or "",
            }
        )
    packages = fetch_all(
        conn,
        """
        SELECT id, name, credits::float AS credits, price_aud_cents
        FROM packages
        WHERE tenant_id = %s AND is_active = true
        ORDER BY price_aud_cents, lower(name)
        """,
        (tenant_id,),
    )
    logs = fetch_all(
        conn,
        """
        SELECT ct.id, ct.student_id, s.display_name AS student_name,
               ct.transaction_type, ct.amount::float AS amount,
               ct.fee_aud_cents, ct.note, ct.occurred_at
        FROM credit_transactions ct
        JOIN students s ON s.id = ct.student_id
        WHERE ct.tenant_id = %s
        ORDER BY ct.occurred_at DESC
        LIMIT 500
        """,
        (tenant_id,),
    )
    pending = fetch_all(
        conn,
        """
        SELECT id, first_name, last_name, mobile, email, message, submitted_at
        FROM registrations
        WHERE tenant_id = %s AND status = 'pending'
        ORDER BY submitted_at DESC
        LIMIT 100
        """,
        (tenant_id,),
    )
    return {
        "students": [
            {
                "id": str(row["id"]),
                "firstName": row["first_name"],
                "lastName": row["last_name"],
                "name": row["display_name"],
                "mobile": row["mobile"],
                "email": row["email"],
                "wechat": row["wechat"],
                "birthday": str(row["birthday"] or ""),
                "balance": row["balance"],
                "archived": row["status"] == "archived",
                "notes": row["notes"],
                "tags": row["tags"] or [],
                "photo": _media_token(str(row["student_photo_asset_id"])) if row["student_photo_asset_id"] else "",
                "portfolio": portfolio_by_student.get(str(row["id"]), []),
                "createdAt": str(row["created_at"]),
            }
            for row in students
        ],
        "packages": [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "credits": row["credits"],
                "price": round((row["price_aud_cents"] or 0) / 100, 2),
            }
            for row in packages
        ],
        "logs": [
            {
                "id": str(row["id"]),
                "studentId": str(row["student_id"]),
                "studentName": row["student_name"],
                "action": row["transaction_type"],
                "change": row["amount"],
                "fee": round((row["fee_aud_cents"] or 0) / 100, 2),
                "note": row["note"],
                "date": str(row["occurred_at"]),
            }
            for row in logs
        ],
        "pending": [
            {
                "id": str(row["id"]),
                "firstName": row["first_name"],
                "lastName": row["last_name"],
                "mobile": row["mobile"],
                "email": row["email"],
                "message": row["message"],
                "submittedAt": str(row["submitted_at"]),
            }
            for row in pending
        ],
        "rosters": {},
        "rev": int(time.time()),
    }


@api_v1.route("/legacy-cms/data", methods=["GET"])
@auth_required
def legacy_cms_data():
    """Return a tenant-backed JSON shape compatible with the old CMS UI."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        data = _legacy_data_for_tenant(conn, tenant.tenant_id)
    return jsonify(data)


@api_v1.route("/legacy-cms/save", methods=["POST"])
@tenant_admin_required

def legacy_cms_save():
    """Persist a safe subset of old CMS JSON edits back to tenant tables."""

    payload = request.get_json(silent=True) or {}
    students = payload.get("students") if isinstance(payload.get("students"), list) else []
    packages = payload.get("packages") if isinstance(payload.get("packages"), list) else []
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO courses (
                    tenant_id, name, description, category, duration_minutes,
                    credit_unit, default_credit_debit, price_aud_cents, is_active
                )
                VALUES (%s, 'General Class', 'Default course for legacy CMS balances.',
                        'General', 60, 'credits', 1, 0, true)
                ON CONFLICT (tenant_id, name) DO UPDATE
                SET is_active = true,
                    updated_at = now()
                RETURNING id
                """,
                (tenant.tenant_id,),
            )
            default_course_id = cur.fetchone()["id"]
            seen_package_ids = []
            for package in packages:
                name = str(package.get("name") or "").strip()
                if not name:
                    continue
                credits = float(package.get("credits") or 1)
                price_cents = int(round(float(package.get("price") or 0) * 100))
                package_id = str(package.get("id") or "")
                if re.match(r"^[0-9a-fA-F-]{36}$", package_id):
                    cur.execute(
                        """
                        UPDATE packages
                        SET name = %s, credits = %s, price_aud_cents = %s, is_active = true
                        WHERE tenant_id = %s AND id = %s
                        RETURNING id
                        """,
                        (name, credits, price_cents, tenant.tenant_id, package_id),
                    )
                    updated = cur.fetchone()
                    if updated:
                        seen_package_ids.append(updated["id"])
                        continue
                cur.execute(
                    """
                    INSERT INTO packages (tenant_id, name, credits, price_aud_cents, is_active)
                    VALUES (%s, %s, %s, %s, true)
                    ON CONFLICT (tenant_id, name) DO UPDATE
                    SET credits = EXCLUDED.credits,
                        price_aud_cents = EXCLUDED.price_aud_cents,
                        is_active = true
                    RETURNING id
                    """,
                    (tenant.tenant_id, name, credits, price_cents),
                )
                seen_package_ids.append(cur.fetchone()["id"])
            if seen_package_ids:
                cur.execute(
                    "UPDATE packages SET is_active = false WHERE tenant_id = %s AND NOT (id = ANY(%s))",
                    (tenant.tenant_id, seen_package_ids),
                )

            for student in students:
                display_name = str(student.get("name") or "").strip()
                if not display_name:
                    continue
                first_name = str(student.get("firstName") or "").strip()
                last_name = str(student.get("lastName") or "").strip()
                if not first_name:
                    first_name, last_name = _legacy_name_parts(display_name)
                source_id = str(student.get("id") or "")
                student_values = (
                    first_name,
                    last_name,
                    display_name,
                    "archived" if student.get("archived") else "active",
                    str(student.get("birthday") or ""),
                    str(student.get("parentName") or ""),
                    str(student.get("mobile") or ""),
                    str(student.get("email") or ""),
                    str(student.get("wechat") or ""),
                    str(student.get("notes") or ""),
                )
                existing = None
                if re.match(r"^[0-9a-fA-F-]{36}$", source_id):
                    cur.execute(
                        """
                        UPDATE students
                        SET first_name = %s,
                            last_name = %s,
                            display_name = %s,
                            status = %s,
                            birthday = NULLIF(%s, '')::date,
                            parent_name = %s,
                            mobile = %s,
                            email = %s,
                            wechat = %s,
                            notes = %s,
                            updated_at = now()
                        WHERE tenant_id = %s AND id = %s
                        RETURNING id
                        """,
                        (*student_values, tenant.tenant_id, source_id),
                    )
                    existing = cur.fetchone()
                if existing:
                    student_id = existing["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO students (
                            tenant_id, first_name, last_name, display_name, status,
                            birthday, parent_name, mobile, email, wechat, notes, source_legacy_id
                        )
                        VALUES (%s, %s, %s, %s, %s, NULLIF(%s, '')::date, %s, %s, %s, %s, %s, NULLIF(%s, ''))
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
                            wechat = EXCLUDED.wechat,
                            notes = EXCLUDED.notes,
                            updated_at = now()
                        RETURNING id
                        """,
                        (tenant.tenant_id, *student_values, source_id),
                    )
                    student_id = cur.fetchone()["id"]
                photo_asset_id = _media_id_from_token(student.get("photo"))
                if photo_asset_id:
                    cur.execute(
                        """
                        UPDATE media_assets
                        SET owner_student_id = %s
                        WHERE tenant_id = %s
                          AND id = %s
                          AND (owner_student_id IS NULL OR owner_student_id = %s)
                        RETURNING id
                        """,
                        (student_id, tenant.tenant_id, photo_asset_id, student_id),
                    )
                    if cur.fetchone():
                        cur.execute(
                            """
                            UPDATE students
                            SET student_photo_asset_id = %s,
                                updated_at = now()
                            WHERE tenant_id = %s AND id = %s
                            """,
                            (photo_asset_id, tenant.tenant_id, student_id),
                        )
                balance = float(student.get("balance") or 0)
                cur.execute(
                    """
                    INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance, low_balance_threshold)
                    VALUES (%s, %s, %s, %s, 2)
                    ON CONFLICT (tenant_id, student_id, course_id) DO UPDATE
                    SET balance = EXCLUDED.balance,
                        updated_at = now()
                    """,
                    (tenant.tenant_id, student_id, default_course_id, balance),
                )
        _audit(conn, tenant_id=tenant.tenant_id, action="legacy_cms.saved", resource_type="legacy_cms")
        conn.commit()
        data = _legacy_data_for_tenant(conn, tenant.tenant_id)
    return jsonify({"status": "success", "rev": data["rev"], "data": data})


@api_v1.route("/media/<media_asset_id>", methods=["GET"])
@tenant_admin_required
def get_media_asset(media_asset_id: str):
    """Serve one tenant-owned media asset for authenticated studio admins."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        return _send_media_asset(conn, tenant_id=tenant.tenant_id, media_asset_id=media_asset_id)


@api_v1.route("/media/upload", methods=["POST"])
@tenant_admin_required
def upload_media_asset():
    """Upload one tenant media asset through the canonical v1 endpoint."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        kind = str(request.form.get("kind") or "portfolio").strip() or "portfolio"
        owner_student_id = str(
            request.form.get("studentId")
            or request.form.get("ownerStudentId")
            or ""
        ).strip() or None
        storage_provider = str(request.form.get("storageProvider") or "local").strip().lower() or "local"
        try:
            media = store_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                file_storage=f,
                kind=kind,
                owner_student_id=owner_student_id,
                storage_provider=storage_provider,
            )
        except MediaUploadError as exc:
            return _media_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="media.uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={
                "kind": kind,
                "byte_size": media["byte_size"],
                "storage_provider": media["storage_provider"],
            },
        )
    media_id = str(media["id"])
    return jsonify(
        {
            "ok": True,
            "mediaAssetId": media_id,
            "filename": _media_token(media_id),
            "url": f"/s/{tenant.slug}/v1/media/{media_id}",
            "mimeType": media["mime_type"],
            "byteSize": media["byte_size"],
            "storageProvider": media["storage_provider"],
        }
    ), 201


@api_v1.route("/legacy-cms/media/upload", methods=["POST"])
@tenant_admin_required
def legacy_cms_media_upload():
    """Upload a tenant-scoped student photo for the legacy CMS UI."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        kind = str(request.form.get("kind") or "student_photo").strip() or "student_photo"
        if kind not in MEDIA_UPLOAD_LIMITS:
            kind = "student_photo"
        try:
            media = _store_media_asset(conn, tenant_id=tenant.tenant_id, file_storage=f, kind=kind)
        except MediaUploadError as exc:
            return _media_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="media.uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={"kind": kind, "byte_size": media["byte_size"]},
        )
    media_id = str(media["id"])
    return jsonify(
        {
            "ok": True,
            "mediaAssetId": media_id,
            "filename": _media_token(media_id),
            "url": f"/s/{tenant.slug}/v1/media/{media_id}",
        }
    )


@api_v1.route("/legacy-cms/portfolio/upload", methods=["POST"])
@tenant_admin_required
def legacy_cms_portfolio_upload():
    """Upload and attach one portfolio image using the legacy CMS response shape."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        student_id = str(request.form.get("studentId") or "").strip()
        note = str(request.form.get("note") or "").strip()[:500]
        date_str = str(request.form.get("date") or "").strip()
        if not student_id:
            return _error("studentId is required.")
        student = fetch_one(
            conn,
            "SELECT id, status FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)
        if student["status"] == "archived":
            return _error("Archived students cannot receive portfolio uploads.", 403)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        try:
            media = _store_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                file_storage=f,
                kind="portfolio",
                owner_student_id=student_id,
            )
        except MediaUploadError as exc:
            return _media_error(exc)
        artwork_date_val = None
        if date_str:
            try:
                from datetime import date as _date

                artwork_date_val = _date.fromisoformat(date_str)
            except (TypeError, ValueError):
                return _error("date must be ISO-8601 date (YYYY-MM-DD).")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO portfolio_items (
                    tenant_id, student_id, media_asset_id, title, description,
                    artwork_date, visibility
                )
                VALUES (%s, %s, %s, '', %s, %s, 'private')
                RETURNING id, created_at
                """,
                (tenant.tenant_id, student_id, media["id"], note, artwork_date_val),
            )
            item = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.uploaded",
            resource_type="portfolio_item",
            resource_id=item["id"],
            metadata={"student_id": student_id, "media_asset_id": str(media["id"])},
        )
    media_id = str(media["id"])
    return jsonify(
        {
            "ok": True,
            "item": {
                "id": str(item["id"]),
                "filename": _media_token(media_id),
                "date": date_str or str(item["created_at"].date()),
                "note": note,
                "mediaUrl": f"/s/{tenant.slug}/v1/media/{media_id}",
            },
        }
    )


@api_v1.route("/legacy-cms/portfolio/<student_id>/<portfolio_item_id>", methods=["DELETE"])
@tenant_admin_required
def legacy_cms_portfolio_delete(student_id: str, portfolio_item_id: str):
    """Delete one tenant portfolio item through the legacy CMS bridge."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM portfolio_items
                WHERE tenant_id = %s AND student_id = %s AND id = %s
                RETURNING id
                """,
                (tenant.tenant_id, student_id, portfolio_item_id),
            )
            if not cur.fetchone():
                return _error("Portfolio item was not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.deleted",
            resource_type="portfolio_item",
            resource_id=portfolio_item_id,
            metadata={"student_id": student_id},
        )
    return jsonify({"ok": True})


@api_v1.route("/legacy-cms/portfolio/<student_id>/<portfolio_item_id>", methods=["PATCH"])
@tenant_admin_required
def legacy_cms_portfolio_update(student_id: str, portfolio_item_id: str):
    """Update one portfolio note/date through the legacy CMS bridge."""

    payload = request.get_json(silent=True) or {}
    note = str(payload.get("note") or "").strip()[:500]
    date_str = str(payload.get("date") or "").strip()
    artwork_date_val = None
    if date_str:
        try:
            from datetime import date as _date

            artwork_date_val = _date.fromisoformat(date_str)
        except (TypeError, ValueError):
            return _error("date must be ISO-8601 date (YYYY-MM-DD).")
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE portfolio_items
                SET description = %s,
                    artwork_date = COALESCE(%s, artwork_date),
                    updated_at = now()
                WHERE tenant_id = %s AND student_id = %s AND id = %s
                RETURNING id
                """,
                (note, artwork_date_val, tenant.tenant_id, student_id, portfolio_item_id),
            )
            if not cur.fetchone():
                return _error("Portfolio item was not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.updated",
            resource_type="portfolio_item",
            resource_id=portfolio_item_id,
            metadata={"student_id": student_id},
        )
    return jsonify({"ok": True})


@api_v1.route("/plans", methods=["GET"])
@auth_required
@permission_required("plans:read")
def list_plans():
    """List StudioSaaS subscription plans."""

    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT code, name, monthly_price_aud, student_limit, user_limit,
                   storage_limit_mb, features
            FROM plans
            ORDER BY monthly_price_aud
            """,
            (),
        )
    return jsonify({"plans": rows})


@api_v1.route("/plans", methods=["POST"])
@auth_required
@super_admin_required
def create_plan():
    """Create a subscription plan from Super Admin."""

    try:
        plan = _plan_payload(_json_payload())
        if not plan["code"]:
            raise ValueError("Plan code is required.")
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO plans (
                    code, name, monthly_price_aud, student_limit,
                    user_limit, storage_limit_mb, features
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                """,
                (
                    plan["code"],
                    plan["name"],
                    plan["monthly_price_aud"],
                    plan["student_limit"],
                    plan["user_limit"],
                    plan["storage_limit_mb"],
                    plan["features_json"],
                ),
            )
        _audit(conn, tenant_id=None, action="plan.created", resource_type="plan", resource_id=plan["code"])
        conn.commit()
    return jsonify({"ok": True, "code": plan["code"]}), 201


@api_v1.route("/plans/<code>", methods=["PATCH", "DELETE"])
@auth_required
@super_admin_required
def mutate_plan(code: str):
    """Update or delete a subscription plan from Super Admin."""

    code = code.lower()
    with connect() as conn:
        if request.method == "DELETE":
            in_use = fetch_one(conn, "SELECT count(*) AS n FROM tenants WHERE plan_code = %s", (code,))
            if in_use and in_use["n"]:
                return _error("Plan is in use by tenants and cannot be deleted.", 409)
            with conn.cursor() as cur:
                cur.execute("DELETE FROM plans WHERE code = %s", (code,))
                if cur.rowcount == 0:
                    return _error("Plan was not found.", 404)
            _audit(conn, tenant_id=None, action="plan.deleted", resource_type="plan", resource_id=code)
            conn.commit()
            return jsonify({"ok": True})
        try:
            payload = _json_payload()
            payload["code"] = code
            plan = _plan_payload(payload)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE plans
                SET name = %s,
                    monthly_price_aud = %s,
                    student_limit = %s,
                    user_limit = %s,
                    storage_limit_mb = %s,
                    features = %s::jsonb
                WHERE code = %s
                """,
                (
                    plan["name"],
                    plan["monthly_price_aud"],
                    plan["student_limit"],
                    plan["user_limit"],
                    plan["storage_limit_mb"],
                    plan["features_json"],
                    code,
                ),
            )
            if cur.rowcount == 0:
                return _error("Plan was not found.", 404)
        _audit(conn, tenant_id=None, action="plan.updated", resource_type="plan", resource_id=code)
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/admin/tenants", methods=["GET"])
@super_admin_required

def admin_tenants():
    """List tenants for the local Super Admin prototype."""

    try:
        limit, offset = _parse_pagination()
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT t.id, t.name, t.slug, t.status, t.plan_code,
                   COALESCE(u.student_count, 0) AS student_count,
                   COALESCE(u.user_count, 0) AS user_count,
                   COALESCE(u.storage_used_mb, 0) AS storage_used_mb,
                   s.status AS subscription_status,
                   s.starts_at, s.ends_at, s.trial_ends_at,
                   s.current_period_ends_at,
                   t.contact_phone, t.contact_email, t.address,
                   t.settings->>'owner_name' AS owner_name,
                   t.settings->>'owner_role' AS owner_role,
                   t.settings->>'owner_phone' AS owner_phone,
                   t.settings->>'owner_email' AS owner_email,
                   t.settings->>'billing_email' AS billing_email,
                   t.settings->>'abn' AS abn,
                   t.settings->>'website' AS website,
                   t.settings->>'notes' AS notes,
                   t.settings->>'studio_admin_email' AS studio_admin_email,
                   t.settings->>'studio_admin_name' AS studio_admin_name,
                   au.last_login_at AS studio_admin_last_login,
                   COALESCE(t.settings->>'category', 'general') AS category,
                   t.settings->>'slogan' AS slogan,
                   t.settings->>'workspace_path' AS workspace_path,
                   t.created_at, t.archived_at, t.archive_path, t.deletion_requested_at, t.deleted_at
            FROM tenants t
            LEFT JOIN tenant_usage u ON u.tenant_id = t.id
            LEFT JOIN subscriptions s ON s.tenant_id = t.id
            LEFT JOIN users au ON lower(au.email) = lower(t.settings->>'studio_admin_email')
            ORDER BY t.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        total = fetch_one(conn, "SELECT count(*) AS n FROM tenants", ())
    return jsonify({"tenants": rows, "limit": limit, "offset": offset, "total": int(total["n"] if total else 0)})


@api_v1.route("/admin/tenants", methods=["POST"])
@super_admin_required

def create_tenant():
    """Create a tenant and subscription from Super Admin."""

    try:
        data = _tenant_write_payload(_json_payload(), require_slug=True)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM plans WHERE code = %s", (data["plan_code"],))
            if not cur.fetchone():
                return _error(f"Plan '{data['plan_code']}' was not found.", 404)
            cur.execute("SELECT 1 FROM tenants WHERE slug = %s", (data["slug"],))
            if cur.fetchone():
                return _error(f"Tenant slug '{data['slug']}' already exists.", 409)
            try:
                workspace_path = _workspace_for(data["slug"], data["name"])
            except ValueError as exc:
                return _error(str(exc))
            cur.execute(
                """
                INSERT INTO tenants (
                    name, slug, status, plan_code, welcome_message,
                    contact_phone, contact_email, address, settings
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id
                """,
                (
                    data["name"],
                    data["slug"],
                    data["status"],
                    data["plan_code"],
                    f"Welcome to {data['name']}.",
                    data["contact_phone"],
                    data["contact_email"],
                    data["address"],
                    data["settings_json"],
                ),
            )
            tenant_id = cur.fetchone()["id"]
            cur.execute(
                """
                UPDATE tenants
                SET settings = jsonb_set(settings, '{workspace_path}', to_jsonb(%s::text), true)
                WHERE id = %s
                """,
                (workspace_path, tenant_id),
            )
            _ensure_studio_admin_account(conn, tenant_id, data["studio_admin"])
            cur.execute(
                """
                INSERT INTO subscriptions (
                    tenant_id, plan_code, status, starts_at, ends_at,
                    trial_ends_at, current_period_ends_at
                )
                VALUES (%s, %s, %s, COALESCE(%s::timestamptz, now()), %s, %s, %s)
                """,
                (
                    tenant_id,
                    data["plan_code"],
                    data["subscription_status"],
                    data["starts_at"],
                    data["ends_at"],
                    data["trial_ends_at"],
                    data["current_period_ends_at"],
                ),
            )
            cur.execute(
                """
                INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb)
                VALUES (%s, 0, 0, 0)
                """,
                (tenant_id,),
            )
            cur.execute(
                """
                INSERT INTO courses (tenant_id, name, description, category, credit_unit)
                VALUES (%s, 'General Class', 'Default course created with tenant.', 'General', 'credits')
                """,
                (tenant_id,),
            )
        _audit(conn, tenant_id=tenant_id, action="tenant.created", resource_type="tenant", resource_id=tenant_id)
        conn.commit()
    return jsonify({"ok": True, "id": tenant_id}), 201


@api_v1.route("/admin/tenants/<tenant_id>", methods=["PATCH", "DELETE"])
@super_admin_required

def mutate_tenant(tenant_id: str):
    """Update or delete a tenant from Super Admin."""

    with connect() as conn:
        if request.method == "DELETE":
            return _error(
                "Direct tenant deletion is disabled. Archive first, then use /admin/tenants/<id>/permanent.",
                405,
            )
        try:
            data = _tenant_write_payload(_json_payload(), require_slug=False)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM plans WHERE code = %s", (data["plan_code"],))
            if not cur.fetchone():
                return _error(f"Plan '{data['plan_code']}' was not found.", 404)
            existing = fetch_one(conn, "SELECT slug FROM tenants WHERE id = %s", (tenant_id,))
            if not existing:
                return _error("Tenant was not found.", 404)
            try:
                workspace_path = _workspace_for(existing["slug"], data["name"])
            except ValueError as exc:
                return _error(str(exc))
            cur.execute(
                """
                UPDATE tenants
                SET name = %s,
                    status = %s,
                    plan_code = %s,
                    contact_phone = %s,
                    contact_email = %s,
                    address = %s,
                    settings = jsonb_set(settings || %s::jsonb, '{workspace_path}', to_jsonb(%s::text), true),
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    data["name"],
                    data["status"],
                    data["plan_code"],
                    data["contact_phone"],
                    data["contact_email"],
                    data["address"],
                    data["settings_json"],
                    workspace_path,
                    tenant_id,
                ),
            )
            if cur.rowcount == 0:
                return _error("Tenant was not found.", 404)
            _ensure_studio_admin_account(conn, tenant_id, data["studio_admin"])
            cur.execute(
                """
                INSERT INTO subscriptions (
                    tenant_id, plan_code, status, starts_at, ends_at,
                    trial_ends_at, current_period_ends_at
                )
                VALUES (%s, %s, %s, COALESCE(%s::timestamptz, now()), %s, %s, %s)
                ON CONFLICT (tenant_id) DO UPDATE
                SET plan_code = EXCLUDED.plan_code,
                    status = EXCLUDED.status,
                    starts_at = EXCLUDED.starts_at,
                    ends_at = EXCLUDED.ends_at,
                    trial_ends_at = EXCLUDED.trial_ends_at,
                    current_period_ends_at = EXCLUDED.current_period_ends_at,
                    updated_at = now()
                """,
                (
                    tenant_id,
                    data["plan_code"],
                    data["subscription_status"],
                    data["starts_at"],
                    data["ends_at"],
                    data["trial_ends_at"],
                    data["current_period_ends_at"],
                ),
            )
        _audit(conn, tenant_id=tenant_id, action="tenant.updated", resource_type="tenant", resource_id=tenant_id)
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/admin/tenants/<tenant_id>/archive", methods=["POST"])
@super_admin_required
def archive_tenant_route(tenant_id: str):
    """Archive tenant data and mark the tenant unavailable."""

    actor = getattr(g, "actor", None)
    with connect() as conn:
        try:
            result = archive_tenant(conn, tenant_id, getattr(actor, "user_id", None))
        except TenantArchiveError as exc:
            return _error(str(exc), 400)
        conn.commit()
    return jsonify({"ok": True, **result})


@api_v1.route("/admin/tenants/<tenant_id>/restore", methods=["POST"])
@super_admin_required
def restore_tenant_route(tenant_id: str):
    """Restore an archived tenant to paused state."""

    actor = getattr(g, "actor", None)
    with connect() as conn:
        try:
            result = restore_tenant(conn, tenant_id, getattr(actor, "user_id", None))
        except TenantArchiveError as exc:
            return _error(str(exc), 400)
        conn.commit()
    return jsonify({"ok": True, **result})


@api_v1.route("/admin/tenants/<tenant_id>/permanent", methods=["DELETE"])
@super_admin_required
def permanently_delete_tenant_route(tenant_id: str):
    """Permanently delete an archived tenant after explicit confirmation."""

    actor = getattr(g, "actor", None)
    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        try:
            result = permanently_delete_tenant(
                conn,
                tenant_id,
                getattr(actor, "user_id", None),
                str(payload.get("confirmationPhrase") or payload.get("confirmation_phrase") or ""),
            )
        except TenantArchiveError as exc:
            return _error(str(exc), 400)
        conn.commit()
    return jsonify({"ok": True, **result})


PASSWORD_SETUP_TOKEN_TTL_HOURS = 24


@api_v1.route("/admin/tenants/<tenant_id>/password-setup-link", methods=["POST"])
@super_admin_required
def admin_create_password_setup_link(tenant_id: str):
    """Generate a one-time password-setup link for a tenant's studio admin.

    The raw token is returned once and never stored; only its SHA-256 hash
    is persisted. Tokens expire after PASSWORD_SETUP_TOKEN_TTL_HOURS and
    are single-use.
    """

    payload = _json_payload()
    with connect() as conn:
        tenant = fetch_one(
            conn,
            """
            SELECT id, slug, name, settings->>'studio_admin_email' AS studio_admin_email
            FROM tenants WHERE id = %s
            """,
            (tenant_id,),
        )
        if not tenant:
            return _error("Tenant not found.", 404)

        email = _clean_text(payload, "email", tenant["studio_admin_email"] or "").lower().strip()
        if not email:
            return _error("No studio admin email configured for this tenant. Set one first.")

        user = fetch_one(
            conn,
            """
            SELECT u.id, u.email FROM users u
            JOIN memberships m ON m.user_id = u.id AND m.tenant_id = %s AND m.status = 'active'
            WHERE lower(u.email) = %s
            """,
            (tenant["id"], email),
        )
        if not user:
            return _error("No active membership for that email on this tenant.", 404)

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with conn.cursor() as cur:
            # Invalidate any previous unused links for this user first.
            cur.execute(
                "DELETE FROM password_setup_tokens WHERE user_id = %s AND used_at IS NULL",
                (user["id"],),
            )
            cur.execute(
                """
                INSERT INTO password_setup_tokens (user_id, tenant_id, token_hash, created_by, expires_at)
                VALUES (%s, %s, %s, %s, now() + make_interval(hours => %s))
                RETURNING expires_at
                """,
                (user["id"], tenant["id"], token_hash, g.actor.user_id, PASSWORD_SETUP_TOKEN_TTL_HOURS),
            )
            expires_at = cur.fetchone()["expires_at"]
        _audit_request(
            conn,
            tenant_id=tenant["id"],
            action="auth.password_setup_link_created",
            resource_type="user",
            resource_id=user["id"],
            metadata={"email": email},
        )
        conn.commit()

    return jsonify({
        "ok": True,
        "url": f"/setup-password?token={raw_token}",
        "email": email,
        "expiresAt": expires_at.isoformat(),
    })


@api_v1.route("/auth/setup-password", methods=["POST"])
def auth_setup_password():
    """Complete a one-time password-setup link. Public, rate-limited."""

    payload = _json_payload()
    raw_token = _clean_text(payload, "token")
    password = _clean_text(payload, "password")
    if not raw_token or not password:
        return _error("token and password are required.")
    if len(password) < 8:
        return _error("Password must be at least 8 characters.")
    if _login_rate_limited(f"setup:{raw_token[:8]}"):
        return _error("Too many attempts. Please wait a minute.", 429)

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with connect() as conn:
        row = fetch_one(
            conn,
            """
            SELECT pst.id, pst.user_id, pst.tenant_id, pst.used_at,
                   (pst.expires_at < now()) AS expired,
                   u.email
            FROM password_setup_tokens pst
            JOIN users u ON u.id = pst.user_id
            WHERE pst.token_hash = %s
            """,
            (token_hash,),
        )
        if not row or row["used_at"] is not None or row["expired"]:
            return _error("This link is invalid or has expired. Ask your platform admin for a new one.", 410)

        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, status = 'active', updated_at = now() WHERE id = %s",
                (_auth_hash_password(password), row["user_id"]),
            )
            cur.execute(
                "UPDATE password_setup_tokens SET used_at = now() WHERE id = %s",
                (row["id"],),
            )
        _audit_request(
            conn,
            tenant_id=row["tenant_id"],
            action="auth.password_setup_completed",
            resource_type="user",
            resource_id=row["user_id"],
            metadata={"email": row["email"]},
        )
        conn.commit()

    return jsonify({"ok": True, "email": row["email"]})


@api_v1.route("/admin/tenants/<tenant_id>/status", methods=["PATCH"])
@super_admin_required
def update_tenant_status(tenant_id: str):
    """Update only tenant and subscription status from Super Admin.

    This keeps quick pause/reactivate actions from rewriting owner, billing, or
    Studio Admin login settings through the broader tenant edit payload.
    """

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    status = _clean_text(payload, "status").lower()
    subscription_status = _clean_text(
        payload,
        "subscriptionStatus",
        _clean_text(payload, "subscription_status", status),
    ).lower()
    if status not in TENANT_STATUSES:
        return _error(f"Tenant status must be one of: {', '.join(sorted(TENANT_STATUSES))}.")
    if subscription_status not in SUBSCRIPTION_STATUSES:
        return _error(
            f"Subscription status must be one of: {', '.join(sorted(SUBSCRIPTION_STATUSES))}."
        )

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants
                SET status = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (status, tenant_id),
            )
            if cur.rowcount == 0:
                return _error("Tenant was not found.", 404)
            cur.execute(
                """
                UPDATE subscriptions
                SET status = %s,
                    updated_at = now()
                WHERE tenant_id = %s
                """,
                (subscription_status, tenant_id),
            )
        _audit(
            conn,
            tenant_id=tenant_id,
            action="tenant.status_updated",
            resource_type="tenant",
            resource_id=tenant_id,
            metadata={"status": status, "subscription_status": subscription_status},
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/admin/usage", methods=["GET"])
@super_admin_required

def admin_usage():
    """Return aggregate usage for the local Super Admin prototype."""

    with connect() as conn:
        row = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM tenants WHERE status NOT IN ('archived', 'deleted')) AS tenants,
                (SELECT count(*) FROM students) AS students,
                (SELECT count(*) FROM portfolio_items) AS portfolio_items,
                (SELECT COALESCE(sum(storage_used_mb), 0) FROM tenant_usage) AS storage_used_mb
            """,
            (),
        )
    return jsonify({"usage": row})


@api_v1.route("/admin/audit-logs", methods=["GET"])
@super_admin_required

def admin_audit_logs():
    """Return recent audit log rows for the local Super Admin prototype."""

    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT a.id, a.action, a.resource_type, a.resource_id, a.created_at,
                   t.slug AS tenant_slug
            FROM audit_logs a
            LEFT JOIN tenants t ON t.id = a.tenant_id
            ORDER BY a.created_at DESC
            LIMIT 100
            """,
            (),
        )
    return jsonify({"auditLogs": rows})




# ──────────────────────────────────────────────
# P0: Student creation + archive
# ──────────────────────────────────────────────

@api_v1.route("/students", methods=["POST"])
@tenant_admin_required

def create_student():
    """Create a new student and an empty credit account for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        display_name = _clean_text(payload, "displayName", _clean_text(payload, "display_name", _clean_text(payload, "name")))
        first_name = _clean_text(payload, "firstName", _clean_text(payload, "first_name", display_name.split()[0] if display_name else ""))
        if not display_name:
            return _error("display_name is required.")
        if not first_name:
            return _error("first_name is required.")

        last_name = _clean_text(payload, "lastName", _clean_text(payload, "last_name", ""))
        parent_name = _clean_text(payload, "parentName", _clean_text(payload, "parent_name", ""))
        mobile = _clean_text(payload, "mobile")
        email = _clean_text(payload, "email")
        wechat = _clean_text(payload, "wechat")
        birthday_str = _clean_text(payload, "birthday")
        tags_raw = payload.get("tags", [])
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif not isinstance(tags_raw, list):
            tags_raw = []
        notes = _clean_text(payload, "notes")

        try:
            birthday_val = None
            if birthday_str:
                from datetime import date as _date
                birthday_val = _date.fromisoformat(birthday_str)
        except (ValueError, TypeError):
            return _error("birthday must be ISO-8601 date (YYYY-MM-DD).")

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status,
                birthday, parent_name, mobile, email, wechat, tags, notes
            ) VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s::text[], %s)
            RETURNING id
            """,
            (
                tenant.tenant_id, first_name, last_name, display_name,
                birthday_val, parent_name, mobile, email, wechat, tags_raw, notes,
            ),
        )
        student_id = str(cur.fetchone()["id"])

        _ensure_default_credit_account(cur, tenant.tenant_id, student_id)

    return jsonify({"ok": True, "studentId": student_id}), 201


@api_v1.route("/students/<student_id>/archive", methods=["POST"])
@tenant_admin_required

def archive_student(student_id: str):
    """Soft-delete (archive) a student for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE students
            SET status = 'archived', updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status != 'archived'
            RETURNING id, display_name
            """,
            (tenant.tenant_id, student_id),
        )
        if not cur.fetchone():
            return _error("Student was not found or already archived.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="student.archived",
            resource_type="student",
            resource_id=student_id,
        )

    return jsonify({"ok": True})


# ──────────────────────────────────────────────
# P0: Credit transactions CRUD
# ──────────────────────────────────────────────

@api_v1.route("/students/<student_id>/credit-transactions", methods=["GET"])
@auth_required
def list_credit_transactions(student_id: str):
    """List all credit transactions for one student in the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, transaction_type, amount::float AS amount,
                   balance_after::float AS balance_after, fee_aud_cents,
                   note, occurred_at
            FROM credit_transactions
            WHERE tenant_id = %s AND student_id = %s
            ORDER BY occurred_at DESC
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"transactions": rows})


@api_v1.route("/students/<student_id>/credit-transactions", methods=["POST"])
@tenant_admin_required

def create_credit_transaction(student_id: str):
    """Create a credit transaction (purchase / debit / adjustment / refund)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        tx_type = _clean_text(payload, "transactionType", _clean_text(payload, "transaction_type"))
        amount_raw = payload.get("amount")
        note = _clean_text(payload, "note")
        fee_cents_raw = payload.get("feeAudCents", payload.get("fee_aud_cents", 0))

        if tx_type not in ("purchase", "consume", "adjustment", "refund", "expire", "migration"):
            return _error("transaction_type must be one of: purchase, consume, adjustment, refund, expire, migration.")

        try:
            amount = float(amount_raw)
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return _error("amount must be a positive number.")

        try:
            fee_cents = int(fee_cents_raw)
            if fee_cents < 0:
                raise ValueError
        except (TypeError, ValueError):
            return _error("fee_aud_cents must be a non-negative integer.")

        # Verify student belongs to tenant
        student = fetch_one(
            conn, "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)

        cur = conn.cursor()
        _ensure_default_credit_account(cur, tenant.tenant_id, student_id)

        # Calculate new balance
        cur.execute(
            "SELECT COALESCE(balance, 0)::numeric AS balance FROM credit_accounts WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL FOR UPDATE",
            (tenant.tenant_id, student_id),
        )
        row = cur.fetchone()
        current_balance = float(row["balance"]) if row else 0.0

        # Determine delta based on type (schema: purchase, consume, adjustment, refund, expire, migration)
        if tx_type == "purchase":
            delta = amount
        elif tx_type == "consume":
            delta = -amount
        elif tx_type == "adjustment":
            delta = amount  # sign of amount determines direction
        elif tx_type == "refund":
            delta = amount  # refund adds credits back
        elif tx_type == "expire":
            delta = -amount  # expiring credits reduces balance
        elif tx_type == "migration":
            delta = amount  # migration sign depends on source/dest
        else:
            delta = amount  # fallback

        # Map legacy client types to schema types
        legacy_type = _clean_text(payload, "legacy_type", "")
        if legacy_type == "debit":
            tx_type = "consume"
        elif legacy_type == "adjustment_in":
            tx_type = "adjustment"
        elif legacy_type == "adjustment_out":
            tx_type = "adjustment"
            delta = -abs(delta)  # negative adjustment

        new_balance = current_balance + delta

        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, transaction_type, amount, balance_after, fee_aud_cents, note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, student_id, tx_type, amount, new_balance, fee_cents, note),
        )
        tx_id = str(cur.fetchone()["id"])

        _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="credit.adjusted",
            resource_type="credit_transaction",
            resource_id=tx_id,
            metadata={"student_id": student_id, "transaction_type": tx_type},
        )

    return jsonify({"ok": True, "transactionId": tx_id, "newBalance": new_balance}), 201


@api_v1.route("/attendance", methods=["GET"])
@auth_required
def list_attendance_sessions():
    """List attendance sessions for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        student_id = request.args.get("studentId", "").strip()
        date_value = request.args.get("date", "").strip()
        limit, offset = _parse_pagination()
        filters = ["a.tenant_id = %s"]
        params: list[object] = [tenant.tenant_id]
        if student_id:
            filters.append("a.student_id = %s")
            params.append(student_id)
        if date_value:
            filters.append("a.attended_at::date = %s::date")
            params.append(date_value)
        params.extend([limit, offset])
        rows = fetch_all(
            conn,
            f"""
            SELECT a.id, a.student_id, s.display_name AS student_name,
                   a.course_id, c.name AS course_name,
                   a.credit_transaction_id, a.reversal_credit_transaction_id,
                   a.attended_at, a.reversed_at, a.note,
                   ct.amount::float AS consumed_credits,
                   rt.amount::float AS refunded_credits
            FROM attendance_sessions a
            JOIN students s ON s.tenant_id = a.tenant_id AND s.id = a.student_id
            LEFT JOIN courses c ON c.tenant_id = a.tenant_id AND c.id = a.course_id
            LEFT JOIN credit_transactions ct
              ON ct.tenant_id = a.tenant_id
             AND ct.id = a.credit_transaction_id
            LEFT JOIN credit_transactions rt
              ON rt.tenant_id = a.tenant_id
             AND rt.id = a.reversal_credit_transaction_id
            WHERE {" AND ".join(filters)}
            ORDER BY a.attended_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )
    return jsonify({"attendance": rows})


@api_v1.route("/attendance/check-in", methods=["POST"])
@tenant_admin_required
def check_in_attendance():
    """Record one attendance session and consume credits atomically."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    student_id = _clean_text(payload, "studentId", _clean_text(payload, "student_id"))
    course_id = _clean_text(payload, "courseId", _clean_text(payload, "course_id")) or None
    note = _clean_text(payload, "note")[:500]
    if not student_id:
        return _error("studentId is required.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status, display_name
                FROM students
                WHERE tenant_id = %s AND id = %s
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            student = cur.fetchone()
            if not student:
                return _error("Student was not found.", 404)
            if student["status"] == "archived":
                return _error("Archived students cannot be checked in.", 403)

            debit = 1.0
            if course_id:
                cur.execute(
                    """
                    SELECT default_credit_debit::float AS debit
                    FROM courses
                    WHERE tenant_id = %s AND id = %s AND is_active = true
                    """,
                    (tenant.tenant_id, course_id),
                )
                course = cur.fetchone()
                if not course:
                    return _error("Course was not found.", 404)
                debit = float(course["debit"] or 1)
            else:
                try:
                    debit = float(payload.get("credits", payload.get("amount", 1)))
                except (TypeError, ValueError):
                    return _error("credits must be a positive number.")
            if debit <= 0:
                return _error("credits must be a positive number.")

            _ensure_default_credit_account(cur, tenant.tenant_id, student_id)
            cur.execute(
                """
                SELECT id, COALESCE(balance, 0)::numeric AS balance
                FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            account = cur.fetchone()
            current_balance = float(account["balance"]) if account else 0.0
            if current_balance < debit:
                return api_error("Insufficient credit balance for check-in.", 409)
            new_balance = current_balance - debit

            cur.execute(
                """
                INSERT INTO credit_transactions (
                    tenant_id, student_id, account_id, actor_user_id,
                    transaction_type, amount, balance_after, note
                )
                VALUES (%s, %s, %s, %s, 'consume', %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    account["id"] if account else None,
                    getattr(g.actor, "user_id", None),
                    debit,
                    new_balance,
                    note or "Attendance check-in",
                ),
            )
            tx_id = str(cur.fetchone()["id"])
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)
            cur.execute(
                """
                INSERT INTO attendance_sessions (
                    tenant_id, student_id, course_id, actor_user_id,
                    credit_transaction_id, note
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, attended_at
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    course_id,
                    getattr(g.actor, "user_id", None),
                    tx_id,
                    note,
                ),
            )
            session_row = cur.fetchone()
            session_id = str(session_row["id"])
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="attendance.checked_in",
                resource_type="attendance_session",
                resource_id=session_id,
                metadata={"student_id": student_id, "credit_transaction_id": tx_id, "credits": debit},
            )

    return jsonify(
        {
            "ok": True,
            "attendanceSessionId": session_id,
            "creditTransactionId": tx_id,
            "newBalance": new_balance,
            "creditsConsumed": debit,
        }
    ), 201


@api_v1.route("/attendance/<attendance_id>/void", methods=["POST"])
@tenant_admin_required
def void_attendance_session(attendance_id: str):
    """Void one attendance session and refund the consumed credits."""

    try:
        payload = _json_payload()
    except ValueError:
        payload = {}
    note = _clean_text(payload, "note")[:500]

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.student_id, a.credit_transaction_id, a.reversed_at,
                       ct.amount::float AS consumed_credits
                FROM attendance_sessions a
                JOIN credit_transactions ct
                  ON ct.tenant_id = a.tenant_id
                 AND ct.id = a.credit_transaction_id
                WHERE a.tenant_id = %s AND a.id = %s
                FOR UPDATE
                """,
                (tenant.tenant_id, attendance_id),
            )
            session_row = cur.fetchone()
            if not session_row:
                return _error("Attendance session was not found.", 404)
            if session_row["reversed_at"]:
                return api_error("Attendance session has already been voided.", 409)

            student_id = str(session_row["student_id"])
            refund_amount = float(session_row["consumed_credits"] or 0)
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id)
            cur.execute(
                """
                SELECT id, COALESCE(balance, 0)::numeric AS balance
                FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            account = cur.fetchone()
            current_balance = float(account["balance"]) if account else 0.0
            new_balance = current_balance + refund_amount
            cur.execute(
                """
                INSERT INTO credit_transactions (
                    tenant_id, student_id, account_id, actor_user_id,
                    transaction_type, amount, balance_after, note
                )
                VALUES (%s, %s, %s, %s, 'refund', %s, %s, %s)
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    account["id"] if account else None,
                    getattr(g.actor, "user_id", None),
                    refund_amount,
                    new_balance,
                    note or "Attendance void refund",
                ),
            )
            refund_tx_id = str(cur.fetchone()["id"])
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)
            cur.execute(
                """
                UPDATE attendance_sessions
                SET reversed_at = now(),
                    reversed_by_user_id = %s,
                    reversal_credit_transaction_id = %s,
                    note = CASE WHEN %s::text = '' THEN note ELSE concat_ws(E'\n', note, %s::text) END
                WHERE tenant_id = %s AND id = %s
                """,
                (
                    getattr(g.actor, "user_id", None),
                    refund_tx_id,
                    note,
                    f"Void: {note}",
                    tenant.tenant_id,
                    attendance_id,
                ),
            )
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="attendance.voided",
                resource_type="attendance_session",
                resource_id=attendance_id,
                metadata={"student_id": student_id, "refund_transaction_id": refund_tx_id, "credits": refund_amount},
            )

    return jsonify(
        {
            "ok": True,
            "attendanceSessionId": attendance_id,
            "refundTransactionId": refund_tx_id,
            "newBalance": new_balance,
            "creditsRefunded": refund_amount,
        }
    )


# ──────────────────────────────────────────────
# P0: Portfolio CRUD
# ──────────────────────────────────────────────

@api_v1.route("/portfolio", methods=["POST"])
@tenant_admin_required

def create_portfolio_item():
    """Create a portfolio item linked to a media asset and student."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        student_id = _clean_text(payload, "studentId")
        media_asset_id = _clean_text(payload, "mediaAssetId")
        title = _clean_text(payload, "title", "")
        description = _clean_text(payload, "description", "")
        visibility = _clean_text(payload, "visibility", "private")

        if not student_id:
            return _error("studentId is required.")
        if not media_asset_id:
            return _error("mediaAssetId is required.")

        # Verify ownership
        student = fetch_one(
            conn, "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)

        media = fetch_one(
            conn, "SELECT id FROM media_assets WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, media_asset_id),
        )
        if not media:
            return _error("Media asset was not found.", 404)

        artwork_date_str = _clean_text(payload, "artworkDate")
        try:
            from datetime import date as _date
            artwork_date_val = None
            if artwork_date_str:
                artwork_date_val = _date.fromisoformat(artwork_date_str)
        except (ValueError, TypeError):
            return _error("artwork_date must be ISO-8601 date (YYYY-MM-DD).")

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO portfolio_items (
                tenant_id, student_id, media_asset_id, title, description,
                artwork_date, visibility
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, student_id, media_asset_id, title, description, artwork_date_val, visibility),
        )
        item_id = str(cur.fetchone()["id"])
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.uploaded",
            resource_type="portfolio_item",
            resource_id=item_id,
            metadata={"student_id": student_id, "media_asset_id": media_asset_id},
        )

    return jsonify({"ok": True, "portfolioItemId": item_id}), 201


@api_v1.route("/portfolio/<portfolio_item_id>", methods=["PATCH"])
@tenant_admin_required

def update_portfolio_item(portfolio_item_id: str):
    """Update a portfolio item's metadata for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        title = _clean_text(payload, "title")
        description = _clean_text(payload, "description")
        visibility = _clean_text(payload, "visibility")
        artwork_date_str = _clean_text(payload, "artworkDate")

        try:
            from datetime import date as _date
            artwork_date_val = None
            if artwork_date_str:
                artwork_date_val = _date.fromisoformat(artwork_date_str)
        except (ValueError, TypeError):
            return _error("artwork_date must be ISO-8601 date (YYYY-MM-DD).")

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE portfolio_items
            SET title = COALESCE(NULLIF(%s, ''), title),
                description = COALESCE(NULLIF(%s, ''), description),
                visibility = COALESCE(NULLIF(%s, ''), visibility),
                artwork_date = COALESCE(%s, artwork_date),
                updated_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING id
            """,
            (title, description, visibility, artwork_date_val, tenant.tenant_id, portfolio_item_id),
        )
        if not cur.fetchone():
            return _error("Portfolio item was not found.", 404)

    return jsonify({"ok": True})


@api_v1.route("/portfolio/<portfolio_item_id>", methods=["DELETE"])
@tenant_admin_required

def delete_portfolio_item(portfolio_item_id: str):
    """Delete a portfolio item for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM portfolio_items WHERE tenant_id = %s AND id = %s RETURNING id",
            (tenant.tenant_id, portfolio_item_id),
        )
        if not cur.fetchone():
            return _error("Portfolio item was not found.", 404)

    return jsonify({"ok": True})


def _hash_password(password: str) -> str:
    """Hash a password using the canonical v1 PBKDF2 auth format."""

    return _auth_hash_password(password)


def _verify_password(password: str, expected_hash: str) -> bool:
    """Verify a password hash without mutating the database."""

    ok, _needs_upgrade = _auth_verify_password(password, expected_hash)
    return ok


def _verify_and_upgrade_password(conn, user: dict, password: str) -> bool:
    """Verify a user's password and upgrade legacy hashes after success."""

    ok, needs_upgrade = _auth_verify_password(password, user.get("password_hash", ""))
    if not ok:
        return False
    if needs_upgrade:
        new_hash = _hash_password(password)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (new_hash, user["id"]),
            )
        user["password_hash"] = new_hash
    return True


def _is_local_request() -> bool:
    """Return true when the request is made from the local development host."""

    host = (request.host or "").split(":", 1)[0].strip().lower()
    return host in {"localhost", "127.0.0.1", "::1"}


def _repair_local_super_admin_login(conn, email: str, password: str) -> dict | None:
    """Repair the documented local Super Admin login when the dev DB is stale.

    This deliberately only runs for the documented localhost-only development
    credentials. It fixes the common local failure mode where an older database
    still has `admin@studiosaas.local` with an unknown password hash or missing
    `super_admin` memberships.
    """

    repair_enabled = os.environ.get("STUDIOSAAS_ENABLE_LOCAL_ADMIN_REPAIR", "").strip().lower()
    if (
        repair_enabled not in {"1", "true", "yes", "on"}
        or email != "admin@studiosaas.local"
        or password != "admin123456"
        or not _is_local_request()
    ):
        return None

    password_hash = _hash_password(password)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE lower(email) = %s",
            (email,),
        )
        row = cur.fetchone()
        if row:
            user_id = row["id"]
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s,
                    full_name = COALESCE(NULLIF(full_name, ''), 'System Administrator'),
                    status = 'active',
                    updated_at = now()
                WHERE id = %s
                """,
                (password_hash, user_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, status)
                VALUES (%s, %s, 'System Administrator', 'active')
                RETURNING id
                """,
                (email, password_hash),
            )
            user_id = cur.fetchone()["id"]

        # Ensure the canonical platform membership (tenant_id IS NULL).
        # UNIQUE (tenant_id, user_id) does not cover NULL rows, so upsert
        # manually: update first, insert only when no platform row exists.
        cur.execute(
            """
            UPDATE memberships
            SET role = 'super_admin', status = 'active'
            WHERE user_id = %s AND tenant_id IS NULL
            """,
            (user_id,),
        )
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role, status)
                VALUES (NULL, %s, 'super_admin', 'active')
                """,
                (user_id,),
            )

    conn.commit()
    return fetch_one(
        conn,
        "SELECT id, email, full_name, status, password_hash FROM users WHERE id = %s",
        (user_id,),
    )


# ──────────────────────────────────────────────
# P0: Auth endpoints (login / logout / me)
# ──────────────────────────────────────────────

@api_v1.route("/auth/login", methods=["POST"])
def auth_login():
    """Authenticate a user by email + password and return session token."""

    payload = _json_payload()
    email = _clean_text(payload, "email").lower().strip()
    password = _clean_text(payload, "password")

    if not email or not password:
        return _error("email and password are required.")

    if _login_rate_limited(email):
        return _error("Too many login attempts. Please wait a minute.", 429)

    with connect() as conn:
        user = fetch_one(
            conn,
            """
            SELECT id, email, full_name, status, password_hash FROM users WHERE email = %s
            """,
            (email,),
        )
        if not user or user["status"] != "active":
            user = _repair_local_super_admin_login(conn, email, password)
            if not user or user["status"] != "active":
                _audit_request(
                    conn,
                    tenant_id=None,
                    action="auth.login_failed",
                    resource_type="user",
                    metadata={"email": email, "reason": "not_found_or_inactive"},
                )
                conn.commit()
                return _error("Invalid email or password.", 401)

        if not _verify_and_upgrade_password(conn, user, password):
            user = _repair_local_super_admin_login(conn, email, password)
            if not user or not _verify_and_upgrade_password(conn, user, password):
                _audit_request(
                    conn,
                    tenant_id=None,
                    action="auth.login_failed",
                    resource_type="user",
                    resource_id=user["id"] if user else "",
                    metadata={"email": email, "reason": "bad_password"},
                )
                conn.commit()
                return _error("Invalid email or password.", 401)

        _record_login(conn, user["id"])
        conn.commit()

    # Generate session token
    token = str(_uuid.uuid4())
    # Store in session (Flask session cookie) — caller must send cookie back
    from flask import session as _flask_session
    _flask_session["user_id"] = user["id"]
    _flask_session["token"] = token

    return jsonify({
        "ok": True,
        "userId": user["id"],
        "email": user["email"],
        "name": user["full_name"],
        "token": token,
    })



@api_v1.route("/auth/legacy-login", methods=["POST"])
def auth_legacy_login():
    """Compatibility adapter for legacy CMS password-based login.

    Accepts an email + password, resolves the tenant from the path slug,
    verifies that the user owns/administers that tenant, and logs them in
    via the v1 session.
    """

    payload = _json_payload()
    email = _clean_text(payload, "email").lower().strip()
    password = _clean_text(payload, "password")
    if not email or not password:
        return _error("Email and password are required.", 400)

    if _login_rate_limited(email):
        return _error("Too many login attempts. Please wait a minute.", 429)

    # Resolve tenant from path slug (set by url_value_preprocessor)
    path_slug = getattr(g, "path_tenant_slug", None)
    if not path_slug:
        return _error("Tenant context required for legacy login.", 400)

    with connect() as conn:
        try:
            from .tenant_context import resolve_tenant
            tenant = resolve_tenant(conn, path_slug, "path")
        except Exception:
            return _error("Unknown tenant.", 404)

        user = fetch_one(
            conn,
            """
            SELECT u.id, u.full_name, u.status, u.password_hash
            FROM users u
            JOIN memberships m ON m.user_id = u.id
            WHERE lower(u.email) = %s
              AND m.status = 'active'
              AND u.status = 'active'
              AND (
                    (m.tenant_id = %s AND m.role IN ('owner', 'super_admin'))
                 OR (m.tenant_id IS NULL AND m.role = 'super_admin')
              )
            LIMIT 1
            """,
            (email, tenant.tenant_id),
        )

        if not user:
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="auth.login_failed",
                resource_type="user",
                metadata={"email": email, "reason": "no_tenant_admin", "surface": "legacy-login"},
            )
            conn.commit()
            return _error("No admin user found for this tenant.", 403)
        if not _verify_and_upgrade_password(conn, user, password):
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="auth.login_failed",
                resource_type="user",
                resource_id=user["id"],
                metadata={"email": email, "reason": "bad_password", "surface": "legacy-login"},
            )
            conn.commit()
            return _error("Invalid password.", 401)

        _record_login(conn, user["id"])
        conn.commit()

    # Generate session token and store in Flask session
    token = str(_uuid.uuid4())
    from flask import session as _flask_session
    _flask_session["user_id"] = user["id"]
    _flask_session["token"] = token

    return jsonify({
        "ok": True,
        "userId": user["id"],
        "name": user["full_name"],
        "token": token,
    })


@api_v1.route("/auth/logout", methods=["POST"])
@auth_required
def auth_logout():
    """Invalidate the current session."""

    from flask import session as _flask_session
    _flask_session.clear()
    return jsonify({"ok": True})


@api_v1.route("/auth/change-password", methods=["POST"])
@auth_required
def auth_change_password():
    """Change the current v1 user's password after verifying the old password."""

    from flask import session as _flask_session

    payload = _json_payload()
    old_password = _clean_text(payload, "oldPassword", _clean_text(payload, "old_password"))
    new_password = _clean_text(payload, "newPassword", _clean_text(payload, "new_password"))
    user_id = _flask_session.get("user_id")

    if not old_password or not new_password:
        return _error("oldPassword and newPassword are required.")
    if len(new_password) < 8:
        return _error("newPassword must be at least 8 characters.")
    if old_password == new_password:
        return _error("newPassword must be different from oldPassword.")

    with connect() as conn:
        user = fetch_one(
            conn,
            "SELECT id, password_hash, status FROM users WHERE id = %s",
            (user_id,),
        )
        if not user or user["status"] != "active":
            return _error("Invalid session.", 401)
        if not _verify_and_upgrade_password(conn, user, old_password):
            return _error("Invalid oldPassword.", 401)
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash = %s, updated_at = now() WHERE id = %s",
                (_hash_password(new_password), user_id),
            )
        conn.commit()

    return jsonify({"ok": True})


@api_v1.route("/auth/me", methods=["GET"])
def auth_me():
    """Return the authenticated user's profile and memberships."""

    from flask import session as _flask_session
    user_id = _flask_session.get("user_id")
    if not user_id:
        return _error("Authentication required. Please log in.", 401)

    with connect() as conn:
        user = fetch_one(
            conn, "SELECT id, email, full_name, status FROM users WHERE id = %s", (user_id,),
        )
        if not user or user["status"] != "active":
            return _error("Authentication required. Please log in.", 401)

        # LEFT JOIN keeps the platform membership (tenant_id IS NULL),
        # which the Super Admin UI uses to gate access.
        memberships = fetch_all(
            conn,
            """
            SELECT m.id, t.slug AS tenant_slug, t.name AS tenant_name,
                   m.role, m.status AS membership_status
            FROM memberships m
            LEFT JOIN tenants t ON t.id = m.tenant_id
            WHERE m.user_id = %s AND m.status = 'active'
            ORDER BY t.name NULLS FIRST
            """,
            (user_id,),
        )

    return jsonify({
        "ok": True,
        "userId": user["id"],
        "email": user["email"],
        "name": user["full_name"],
        "user": dict(user),
        "memberships": memberships,
    })




# ──────────────────────────────────────────────
# P2: Studio Admin ↔ Legacy CMS sync endpoints
# ──────────────────────────────────────────────

import os as _os
import uuid as _uuid

UPLOAD_DIR = _os.path.join(_os.path.dirname(__file__), "..", "static", "uploads")
_os.makedirs(UPLOAD_DIR, exist_ok=True)


@api_v1.route("/tenant/settings", methods=["PATCH"])
@tenant_admin_required

def update_tenant_settings():
    """Compatibility alias for old clients; writes through the canonical tenant route."""

    return update_tenant()


@api_v1.route("/tenant/logo", methods=["POST"])
@tenant_admin_required

def upload_tenant_logo():
    """Upload a logo file for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")

        try:
            media = _store_media_asset(conn, tenant_id=tenant.tenant_id, file_storage=f, kind="logo")
        except MediaUploadError as exc:
            return _media_error(exc)

        logo_url = f"/v1/public/{tenant.slug}/media/{media['id']}"

        # Save to tenant settings
        cur = conn.cursor()
        cur.execute("SELECT settings FROM tenants WHERE id = %s", (tenant.tenant_id,),)
        row = cur.fetchone()
        current_settings = dict(row["settings"]) if isinstance(row["settings"], dict) else {}
        current_settings["logoUrl"] = logo_url
        current_settings["logo_url"] = logo_url

        cur.execute(
            """
            UPDATE tenants
            SET settings = %s::jsonb,
                updated_at = now()
            WHERE id = %s
            """,
            (json.dumps(current_settings), tenant.tenant_id),
        )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="tenant.logo_uploaded",
            resource_type="tenant",
            resource_id=tenant.tenant_id,
	            metadata={"logo_url": logo_url, "media_asset_id": str(media["id"])},
        )

    return jsonify({"ok": True, "url": logo_url})


@api_v1.route("/students/<student_id>", methods=["PATCH"])
@tenant_admin_required

def update_student(student_id: str):
    """Update a student record and sync balance/credit_hours to legacy CMS."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        # Verify ownership
        existing = fetch_one(
            conn, "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not existing:
            return _error("Student was not found.", 404)

        updates = {}
        display_name = _clean_text(payload, "displayName", _clean_text(payload, "name"))
        if "displayName" in payload or "name" in payload:
            if not display_name:
                return _error("displayName is required.")
            updates["display_name"] = display_name
            if "firstName" not in payload and "first_name" not in payload:
                updates["first_name"] = display_name.split()[0]
        if "firstName" in payload or "first_name" in payload:
            first_name = _clean_text(payload, "firstName", _clean_text(payload, "first_name"))
            if not first_name:
                return _error("firstName is required.")
            updates["first_name"] = first_name
        if "lastName" in payload or "last_name" in payload:
            updates["last_name"] = _clean_text(payload, "lastName", _clean_text(payload, "last_name", ""))
        if "email" in payload:
            email = _clean_text(payload, "email").lower()
            try:
                _validate_optional_email("email", email)
            except ValueError as exc:
                return _error(str(exc))
            updates["email"] = email
        if "mobile" in payload or "phone" in payload:
            updates["mobile"] = _clean_text(payload, "mobile", _clean_text(payload, "phone", ""))
        if "status" in payload:
            try:
                updates["status"] = _student_status(_clean_text(payload, "status"))
            except ValueError as exc:
                return _error(str(exc))

        # Handle balance change → create credit transaction
        old_balance = fetch_one(
            conn,
            """
            SELECT COALESCE(balance, 0)::float AS balance
            FROM credit_accounts
            WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            """,
            (tenant.tenant_id, student_id),
        )
        old_bal_val = float(old_balance["balance"]) if old_balance else 0.0

        new_balance_raw = payload.get("balance")
        if new_balance_raw is not None:
            try:
                new_balance = float(new_balance_raw)
            except (TypeError, ValueError):
                return _error("Invalid balance value.")

            delta = new_balance - old_bal_val
            if abs(delta) > 0.001:
                tx_type = "adjustment"  # schema type; sign of amount determines direction
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO credit_transactions (tenant_id, student_id, transaction_type, amount, balance_after)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (tenant.tenant_id, student_id, tx_type, abs(delta), new_balance),
                )
                _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_balance)

        # Handle credit_hours change → keep the default credit account in sync.
        new_credit_raw = payload.get("creditHours")
        if new_credit_raw is not None:
            try:
                new_credit_val = float(new_credit_raw)
            except (TypeError, ValueError):
                return _error("Invalid credit hours value.")

            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO credit_transactions (tenant_id, student_id, transaction_type, amount, balance_after)
                VALUES (%s, %s, 'adjustment', %s, %s)
                RETURNING id
                """,
                (tenant.tenant_id, student_id, new_credit_val, new_credit_val),
            )
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, new_credit_val)

        # Build SQL UPDATE
        if updates:
            set_clause = ", ".join(f"{col} = %s" for col in updates.keys())
            params = list(updates.values()) + [tenant.tenant_id, student_id]
            cur = conn.cursor()
            cur.execute(
                f"UPDATE students SET {set_clause}, updated_at = now() WHERE tenant_id = %s AND id = %s",
                params,
            )

    return jsonify({"ok": True})
