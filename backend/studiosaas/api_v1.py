"""StudioSaaS API v1 routes.

These routes are intentionally introduced beside the legacy endpoints. Tenant
APIs require PostgreSQL and explicit tenant resolution; they do not fall back to
the single-studio JSON database.
"""

import ipaddress
import json
import os
import re
import secrets
import time
import hashlib
import uuid as _uuid
from datetime import date as _date, timedelta as _timedelta
from pathlib import PurePath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import csv as _csv
import io as _io

from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
from werkzeug.utils import secure_filename

from .auth import (
    auth_required,
    hash_password as _auth_hash_password,
    permission_required,
    super_admin_required,
    tenant_admin_required,
    tenant_owner_required,
    verify_password as _auth_verify_password,
)
from .config import load_config
from .db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from .errors import api_error
from .lifecycle import (
    canonical_subscription_status,
    validate_registration_transition,
    validate_tenant_subscription_pair,
    validate_tenant_transition,
)
from .models import Role
from .presets import INDUSTRY_PRESETS, public_industry_presets
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
from .services import notifications as _notifications
from .services.student_access import (
    access_locked as _student_access_locked,
    clear_failed_access as _clear_student_access_failures,
    create_access_session as _create_student_access_session,
    find_student as _find_public_student,
    generate_access_code as _generate_student_access_code,
    lookup_fingerprint as _student_lookup_fingerprint,
    record_failed_access as _record_student_access_failure,
    resolve_access_session as _resolve_student_access_session,
    revoke_access_code as _revoke_student_access_code,
    revoke_access_session as _revoke_student_access_session,
    verify_access_code as _verify_student_access_code,
)
from .tenant_context import TenantResolutionError, resolve_tenant, slug_from_request
from .workspaces import WorkspaceError, ensure_tenant_workspace, validate_tenant_slug

api_v1 = Blueprint("studiosaas_api_v1", __name__)
# Simple in-memory rate limiter for public endpoints (per-IP, per-minute).
# Counters reset on process restart — acceptable for the local pilot; a
# shared store (Redis) replaces this at the production stage (P3-04).
_public_rate_limit: dict[str, list[float]] = {}


def _rate_limited(key: str, limit: int, *, window_seconds: int = 60) -> bool:
    """Apply a bounded in-memory sliding-window limit for one public action."""

    now = time.time()
    attempts = [stamp for stamp in _public_rate_limit.get(key, []) if now - stamp < window_seconds]
    limited = len(attempts) >= limit
    if not limited:
        attempts.append(now)
    _public_rate_limit[key] = attempts
    return limited


def _validated_timezone(value: str | None) -> str:
    """Return a valid IANA timezone name or raise a user-facing validation error."""

    timezone_name = str(value or "Australia/Melbourne").strip() or "Australia/Melbourne"
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError("Timezone must be a valid IANA name such as Australia/Melbourne.") from exc
    return timezone_name


def _tenant_timezone(conn, tenant_id: str) -> str:
    """Read and validate the business timezone for a tenant."""

    row = fetch_one(conn, "SELECT timezone FROM tenants WHERE id = %s", (tenant_id,))
    return _validated_timezone(row["timezone"] if row else None)


def _client_ip() -> str:
    """Real client IP for rate limiting and audit.

    Proxy headers (CF-Connecting-IP / X-Forwarded-For) are only trusted when
    the request arrives from localhost — i.e. through the local cloudflared
    tunnel. Direct LAN clients can't spoof their way past the rate limiter
    by sending fake headers. Mirrors server.py's _client_ip().
    """

    ra = request.remote_addr or "unknown"
    if ra in ("127.0.0.1", "::1", "localhost"):
        forwarded = (
            request.headers.get("CF-Connecting-IP")
            or request.headers.get("X-Forwarded-For")
            or ra
        )
        return forwarded.split(",")[0].strip() or ra
    return ra


def _student_cookie_secure() -> bool:
    """Return whether public student cookies must use HTTPS-only semantics."""

    if request.is_secure or os.environ.get("COOKIE_SECURE") == "1":
        return True
    if os.environ.get("STUDIOSAAS_ENV", "local").strip().lower() in {"pilot", "production"}:
        return True
    return bool(
        request.remote_addr in {"127.0.0.1", "::1"}
        and request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    )


def _student_cookie_name() -> str:
    """Use the hardened host cookie in HTTPS environments and a local name in dev."""

    return "__Host-studiosaas-student" if _student_cookie_secure() else "studiosaas_student"


def _student_cookie_token() -> str:
    """Read either supported cookie name to make HTTPS transitions explicit."""

    return str(
        request.cookies.get("__Host-studiosaas-student")
        or request.cookies.get("studiosaas_student")
        or ""
    )


def _login_rate_limited(email: str) -> bool:
    """Sliding-window limiter for login attempts.

    Two dimensions share the public limiter store: per client IP
    (30 attempts/minute across all accounts — high enough for local
    test suites, low enough to blunt spraying) and per IP+email
    (5 attempts/minute against a single account).
    """

    now = time.time()
    ip = _client_ip()
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


def _csv_response(filename: str, header: list, rows) -> Response:
    """Stream rows as a CSV attachment with a UTF-8 BOM (Excel-friendly)."""

    def generate():
        buf = _io.StringIO()
        writer = _csv.writer(buf)
        yield "\ufeff"  # UTF-8 BOM so Excel opens the file correctly
        writer.writerow(header)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for row in rows:
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    resp = Response(generate(), mimetype="text/csv")
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


def _start_session_policy(flask_session, payload) -> None:
    """Apply the session lifetime policy at login.

    Sessions are always cookie-persistent (Flask permanent) but expire on
    idleness, enforced by the idle guard in server.py: 24h by default,
    30 days when the client asks to be remembered.
    """

    flask_session.permanent = True
    flask_session["remember"] = bool(payload.get("rememberMe", payload.get("remember_me", False)))
    flask_session["last_seen"] = time.time()



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


TENANT_STATUSES = {
    "lead",
    "trial",
    "onboarding",
    "active",
    "past_due",
    "paused",
    "cancelled",
    "archived",
    "deleted",
}
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
        "fields": [
            {
                **dict(field),
                "type": field.get("type") or "text",
                "required": bool(field.get("required", False)),
                "options": list(field.get("options") or []),
            }
            for field in preset["fields"]
        ],
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
    default_fields = {field["key"]: field for field in default["fields"]}
    for field in fields[:8]:
        if not isinstance(field, dict):
            raise ValueError("Each registration field must be an object.")
        key = str(field.get("key") or "").strip()
        label = str(field.get("label") or "").strip()
        placeholder = str(field.get("placeholder") or "").strip()
        label_en = str(field.get("label_en") or field.get("labelEn") or label).strip()
        default_field = default_fields.get(key, {})
        label_zh = str(
            field.get("label_zh") or field.get("labelZh") or default_field.get("label_zh") or label
        ).strip()
        placeholder_en = str(field.get("placeholder_en") or field.get("placeholderEn") or placeholder).strip()
        placeholder_zh = str(
            field.get("placeholder_zh")
            or field.get("placeholderZh")
            or default_field.get("placeholder_zh")
            or placeholder
        ).strip()
        input_type = str(field.get("type") or "text").strip().lower()
        required = bool(field.get("required", False))
        options = field.get("options") or []
        if not re.match(r"^[A-Za-z][A-Za-z0-9_]{1,40}$", key):
            raise ValueError("Registration field keys must use letters, numbers, or underscores.")
        if not label:
            raise ValueError("Registration field labels are required.")
        if input_type not in {"text", "textarea", "select"}:
            raise ValueError("Registration field type must be text, textarea, or select.")
        if not isinstance(options, list):
            raise ValueError("Registration field options must be a list.")
        options = [str(item).strip()[:80] for item in options[:12] if str(item).strip()]
        if input_type == "select" and not options:
            raise ValueError("Select registration fields require at least one option.")
        normalized.append({
            "key": key,
            "label": (label_en or label)[:80],
            "label_en": (label_en or label)[:80],
            "label_zh": label_zh[:80],
            "placeholder": (placeholder_en or placeholder)[:140],
            "placeholder_en": (placeholder_en or placeholder)[:140],
            "placeholder_zh": placeholder_zh[:140],
            "type": input_type,
            "required": required,
            "options": options,
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
    aliases = {
        "portal_label": ("portal_label", "portalLabel"),
        "register_intro": ("register_intro", "registerIntro"),
    }
    for key, candidates in aliases.items():
        incoming = ""
        for candidate in candidates:
            incoming = str(value.get(candidate) or "").strip()
            if incoming:
                break
        incoming = incoming or default[key]
        default[key] = incoming[:180] or default[key]
    return default


def _normalize_localized_copy(value, category: str = "general") -> dict:
    """Validate the explicit Chinese/English public-copy bundle."""

    data = _coerce_json_object(value, field_name="localized_copy")
    preset = _preset_for(category)
    defaults = {
        "hero_title": preset["hero"]["title"],
        "hero_subtitle": preset["hero"]["subtitle"],
        "primary_cta": {"zh": "预约体验", "en": "Book a Trial"},
        "secondary_cta": {"zh": "查看课程", "en": "Explore Programs"},
        "registration_title": {"zh": preset["registration_title_zh"], "en": preset["registration_title"]},
        "registration_intro": {"zh": preset["register_intro_zh"], "en": preset["copy_pack"]["register_intro"]},
    }
    limits = {
        "hero_title": 120,
        "hero_subtitle": 240,
        "primary_cta": 80,
        "secondary_cta": 80,
        "registration_title": 120,
        "registration_intro": 300,
    }
    normalized: dict[str, dict[str, str]] = {}
    for key, limit in limits.items():
        pair = data.get(key) or data.get("".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])])) or defaults[key]
        if isinstance(pair, str):
            pair = {"zh": pair, "en": pair}
        if not isinstance(pair, dict):
            raise ValueError(f"localized_copy.{key} must contain zh/en text.")
        normalized[key] = {
            "zh": str(pair.get("zh") or defaults[key]["zh"]).strip()[:limit],
            "en": str(pair.get("en") or defaults[key]["en"]).strip()[:limit],
        }
    return normalized


def _coerce_json_object(value, *, field_name: str) -> dict:
    """Return ``value`` as a JSON object or raise a request validation error."""

    if value in (None, ""):
        return {}
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be valid JSON.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object.")
    return value


def _coerce_json_list(value, *, field_name: str) -> list:
    """Return ``value`` as a JSON list or raise a request validation error."""

    if value in (None, ""):
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{field_name} must be valid JSON.") from exc
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a JSON list.")
    return value


def _first_text(data: dict, *keys: str, default: str = "", limit: int = 180) -> str:
    """Read a short text value from a JSON object using snake/camel aliases."""

    for key in keys:
        value = data.get(key)
        if value is not None:
            text = str(value).strip()
            if text:
                return text[:limit]
    return default[:limit]


def _bool_from_json(data: dict, *keys: str, default: bool = True) -> bool:
    """Read a boolean-ish value from JSON settings."""

    value = None
    for key in keys:
        if key in data:
            value = data.get(key)
            break
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip().lower() not in {"0", "false", "no", "off"}
    return bool(value)


def _default_hero_profile(category: str, studio_name: str = "") -> dict:
    """Return default public hero copy for a tenant category."""

    preset = _preset_for(category)
    return {
        "eyebrow": preset["label"],
        "title": studio_name,
        "subtitle": preset["slogan"],
        "primary_cta_label": "Book a Trial",
        "secondary_cta_label": "Explore Courses",
        "show_student_login": True,
        "background_style": "soft",
        "hero_image_url": "",
    }


def _normalize_hero_profile(value, category: str, studio_name: str = "") -> dict:
    """Validate public landing-page hero settings."""

    data = _coerce_json_object(value, field_name="hero_profile")
    default = _default_hero_profile(category, studio_name)
    background_style = _first_text(
        data,
        "background_style",
        "backgroundStyle",
        default=default["background_style"],
        limit=24,
    ).lower()
    if background_style not in {"soft", "image", "minimal", "bold"}:
        raise ValueError("Hero background style must be one of: soft, image, minimal, bold.")
    hero_image_url = _first_text(data, "hero_image_url", "heroImageUrl", limit=500)
    if hero_image_url:
        _validate_logo_url(hero_image_url)
    return {
        "eyebrow": _first_text(data, "eyebrow", default=default["eyebrow"], limit=80),
        "title": _first_text(data, "title", default=default["title"], limit=100),
        "subtitle": _first_text(data, "subtitle", default=default["subtitle"], limit=240),
        "primary_cta_label": _first_text(data, "primary_cta_label", "primaryCtaLabel", default=default["primary_cta_label"], limit=40),
        "secondary_cta_label": _first_text(data, "secondary_cta_label", "secondaryCtaLabel", default=default["secondary_cta_label"], limit=40),
        "show_student_login": _bool_from_json(data, "show_student_login", "showStudentLogin", default=True),
        "background_style": background_style,
        "hero_image_url": hero_image_url,
    }


def _default_website_profile() -> dict:
    """Return default public section visibility and labels."""

    return {
        "show_principal": True,
        "show_courses": True,
        "show_gallery": True,
        "show_faq": True,
        "show_contact": True,
        "show_student_area": True,
        "courses_label": "Courses & Classes",
        "gallery_label": "Student Works",
        "faq_label": "Questions & Answers",
        "contact_label": "Contact",
    }


def _normalize_website_profile(value) -> dict:
    """Validate public section visibility and label settings."""

    data = _coerce_json_object(value, field_name="website_profile")
    default = _default_website_profile()
    profile = {
        key: _bool_from_json(
            data,
            key,
            "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])]),
            default=default[key],
        )
        for key in (
            "show_principal",
            "show_courses",
            "show_gallery",
            "show_faq",
            "show_contact",
            "show_student_area",
        )
    }
    for key in ("courses_label", "gallery_label", "faq_label", "contact_label"):
        profile[key] = _first_text(data, key, "".join([key.split("_")[0], "Label"]), default=default[key], limit=80)
    return profile


def _default_principal_profile(studio_name: str = "") -> dict:
    """Return default principal/about section content."""

    return {
        "show": True,
        "name": "",
        "title": "Founder & Principal",
        "bio": f"Meet the principal behind {studio_name or 'the studio'} and the teaching philosophy that shapes every class.",
        "quote": "Learn with care, confidence, and a rhythm that fits each student.",
        "image_url": "",
    }


def _normalize_principal_profile(value, studio_name: str = "") -> dict:
    """Validate public principal/about section settings."""

    data = _coerce_json_object(value, field_name="principal_profile")
    default = _default_principal_profile(studio_name)
    image_url = _first_text(data, "image_url", "imageUrl", limit=500)
    if image_url:
        _validate_logo_url(image_url)
    return {
        "show": _bool_from_json(data, "show", default=default["show"]),
        "name": _first_text(data, "name", default=default["name"], limit=100),
        "title": _first_text(data, "title", default=default["title"], limit=100),
        "bio": _first_text(data, "bio", default=default["bio"], limit=800),
        "quote": _first_text(data, "quote", default=default["quote"], limit=180),
        "image_url": image_url,
    }


def _default_faq_items(category: str) -> list[dict]:
    """Return default FAQ copy for public tenant pages."""

    preset = _preset_for(category)
    return [
        {
            "question": "Is there a trial class?",
            "answer": "Yes. Leave your details and the studio will contact you to arrange a suitable first session.",
        },
        {
            "question": "How do class packs work?",
            "answer": "Classes can be tracked as credits in the CMS, and families can check balances from the student area.",
        },
        {
            "question": f"Which {preset['label'].lower()} level should we choose?",
            "answer": "Start with your current experience and goals in the registration form. The studio will recommend the right class.",
        },
        {
            "question": "Can parents view progress?",
            "answer": "Yes. The public portal includes a student area for class balance and portfolio lookup when enabled.",
        },
    ]


def _normalize_faq_items(value, category: str) -> list[dict]:
    """Validate FAQ items shown on public tenant pages."""

    items = _coerce_json_list(value, field_name="faq_items")
    if not items:
        return _default_faq_items(category)
    normalized = []
    for item in items[:8]:
        if not isinstance(item, dict):
            raise ValueError("Each FAQ item must be an object.")
        question = _first_text(item, "question", limit=140)
        answer = _first_text(item, "answer", limit=500)
        if question and answer:
            normalized.append({"question": question, "answer": answer})
    if not normalized:
        raise ValueError("At least one FAQ item must include a question and answer.")
    return normalized


def _default_visual_theme(
    primary_color: str = "",
    secondary_color: str = "",
    category: str = "general",
) -> dict:
    """Return default public visual-theme options."""

    theme = dict(_preset_for(category)["theme"])
    if primary_color:
        theme["accent_color"] = primary_color
    if secondary_color:
        theme["secondary_accent_color"] = secondary_color
    return theme


def _normalize_visual_theme(
    value,
    primary_color: str = "",
    secondary_color: str = "",
    category: str = "general",
) -> dict:
    """Validate public colour and light style settings."""

    data = _coerce_json_object(value, field_name="visual_theme")
    default = _default_visual_theme(primary_color, secondary_color, category)
    theme = {}
    for key in ("background_color", "panel_color", "text_color", "accent_color", "secondary_accent_color"):
        aliases = (key, "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])]))
        value_text = _first_text(data, *aliases, default=default[key], limit=16)
        _validate_hex_color(key.replace("_", " ").title(), value_text)
        theme[key] = value_text
    button_style = _first_text(data, "button_style", "buttonStyle", default=default["button_style"], limit=24).lower()
    font_mood = _first_text(data, "font_mood", "fontMood", default=default["font_mood"], limit=24).lower()
    if button_style not in {"soft", "sharp", "rounded"}:
        raise ValueError("Button style must be one of: soft, sharp, rounded.")
    if font_mood not in {"serif", "modern", "classic"}:
        raise ValueError("Font mood must be one of: serif, modern, classic.")
    theme["button_style"] = button_style
    theme["font_mood"] = font_mood
    return theme


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
    localized_copy = _normalize_localized_copy(
        payload.get("localizedCopy", payload.get("localized_copy")),
        category,
    )
    hero_profile = _normalize_hero_profile(
        payload.get("heroProfile", payload.get("hero_profile")),
        category,
        name,
    )
    website_profile = _normalize_website_profile(payload.get("websiteProfile", payload.get("website_profile")))
    principal_profile = _normalize_principal_profile(
        payload.get("principalProfile", payload.get("principal_profile")),
        name,
    )
    faq_items = _normalize_faq_items(payload.get("faqItems", payload.get("faq_items")), category)
    visual_theme = _normalize_visual_theme(
        payload.get("visualTheme", payload.get("visual_theme")),
        payload.get("primaryColor", payload.get("primary_color", "")),
        payload.get("secondaryColor", payload.get("secondary_color", "")),
        category,
    )
    settings = {
        "category": category,
        "category_label": preset["label"],
        "slogan": slogan,
        "registration_profile": registration_profile,
        "copy_pack": copy_pack,
        "localized_copy": localized_copy,
        "hero_profile": hero_profile,
        "website_profile": website_profile,
        "principal_profile": principal_profile,
        "faq_items": faq_items,
        "visual_theme": visual_theme,
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
    validate_tenant_subscription_pair(status, subscription_status)
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


def _support_tagged(metadata) -> dict:
    """Merge the active support-session marker into audit metadata (B4).

    Every audit row written while a platform admin is in support mode is
    tagged so tenant-facing actions taken on the customer's behalf are
    distinguishable from the studio's own activity.
    """

    data = dict(metadata or {})
    try:
        from flask import session as _fs
        support = _fs.get("support")
        if support:
            data["support_session"] = {
                "reason": support.get("reason", ""),
                "tenant_slug": support.get("slug", ""),
            }
    except RuntimeError:
        pass  # outside request context
    return data


def _audit(conn, *, tenant_id, action, resource_type, resource_id="", metadata=None):
    """Write a compact audit log row for local admin mutations."""

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, action, resource_type, resource_id, metadata)
            VALUES (%s, %s, %s, %s, %s::jsonb)
            """,
            (tenant_id, action, resource_type, str(resource_id or ""), json.dumps(_support_tagged(metadata))),
        )


def _audit_request(conn, *, tenant_id, action, resource_type, resource_id="", metadata=None):
    """Write an audit log row with request actor and IP when available."""

    actor = getattr(g, "actor", None)
    try:
        client_ip = str(ipaddress.ip_address(_client_ip()))
    except ValueError:
        client_ip = ""
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
                json.dumps(_support_tagged(metadata)),
                client_ip,
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
        raise ValueError("studioAdminPassword is required when creating a tenant.")

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
                if not password:
                    raise ValueError("A password is required when creating a Studio Admin account.")
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
                    (email, _hash_password(password), full_name),
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
    "website_image": ({".jpg", ".jpeg", ".png", ".webp"}, 10 * 1024 * 1024),
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
            (SELECT count(*) FROM students WHERE tenant_id = %s AND status <> 'archived') AS student_count,
            (
                SELECT count(*) FROM memberships
                WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'
            ) AS user_count,
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


def _student_capacity(conn, tenant_id: str) -> tuple[int, int]:
    """Return current non-archived students and the tenant plan limit."""

    with conn.cursor() as cur:
        # Serialize student creation per tenant so concurrent requests cannot
        # both pass the same plan-capacity check.
        cur.execute("SELECT id FROM tenants WHERE id = %s FOR UPDATE", (tenant_id,))
    row = fetch_one(
        conn,
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = t.id AND status <> 'archived') AS current_students,
            p.student_limit
        FROM tenants t
        JOIN plans p ON p.code = t.plan_code
        WHERE t.id = %s
        """,
        (tenant_id,),
    )
    if not row:
        raise ValueError("Tenant plan was not found.")
    return int(row["current_students"] or 0), int(row["student_limit"] or 0)


def _plan_feature_enabled(conn, tenant_id: str, feature: str) -> bool:
    """Return whether the tenant's current plan enables a named feature."""

    row = fetch_one(
        conn,
        """
        SELECT p.features
        FROM tenants t
        JOIN plans p ON p.code = t.plan_code
        WHERE t.id = %s
        """,
        (tenant_id,),
    )
    return bool(row and (row.get("features") or {}).get(feature, False))


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


def _send_media_asset(
    conn,
    *,
    tenant_id: str,
    media_asset_id: str,
    variant: str | None = None,
):
    """Serve one media asset after tenant ownership has been verified.

    ``?thumb=1`` serves the lazily generated list-view thumbnail (S3).
    """

    requested_variant = variant
    if requested_variant is None and str(request.args.get("thumb", "")).lower() in ("1", "true", "yes"):
        requested_variant = "thumb"
    try:
        return send_media_asset(
            conn,
            tenant_id=tenant_id,
            media_asset_id=media_asset_id,
            variant=requested_variant,
        )
    except MediaUploadError as exc:
        return _error(str(exc), 404)


def _parse_bool_arg(name: str) -> bool:
    """Return true for common truthy query-string values."""

    return request.args.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _public_visibility(value) -> str:
    """Map a public-gallery toggle to the persisted portfolio visibility."""

    if isinstance(value, bool):
        return "shared" if value else "private"
    return "shared" if str(value or "").strip().lower() in {"1", "true", "yes", "on", "shared"} else "private"


def _validate_portfolio_visibility(value: str) -> str:
    """Return a supported portfolio visibility value or raise a clear error."""

    visibility = str(value or "private").strip().lower()
    if visibility not in {"private", "shared"}:
        raise ValueError("visibility must be one of: private, shared.")
    return visibility


def _active_publication_consent(conn, *, tenant_id: str, student_id: str) -> dict | None:
    """Return the latest effective student-level publication consent event."""

    row = fetch_one(
        conn,
        """
        SELECT id, status, consent_by, relationship, consent_method,
               notice_version, note, created_at
        FROM student_publication_consent_events
        WHERE tenant_id = %s AND student_id = %s
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (tenant_id, student_id),
    )
    return row if row and row["status"] == "confirmed" else None


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

    return jsonify({"ok": True, "service": "PWE Studio SaaS API", "version": "v1"})


@api_v1.route("/industry-presets", methods=["GET"])
def industry_presets():
    """Return the shared onboarding, copy, and theme presets."""

    return jsonify({"presets": public_industry_presets()})


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
               t.settings->'localized_copy' AS localized_copy,
               t.settings->'hero_profile' AS hero_profile,
               t.settings->'website_profile' AS website_profile,
               t.settings->'principal_profile' AS principal_profile,
               t.settings->'faq_items' AS faq_items,
               t.settings->'visual_theme' AS visual_theme,
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


@api_v1.route("/team", methods=["GET"])
@tenant_admin_required
def list_tenant_team():
    """List tenant operational users without exposing password data."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT m.id, m.role, m.status, m.created_at,
                   u.id AS user_id, u.email, u.full_name, u.last_login_at
            FROM memberships m
            JOIN users u ON u.id = m.user_id
            WHERE m.tenant_id = %s
              AND m.role <> 'parent'
            ORDER BY CASE m.role
                WHEN 'owner' THEN 0 WHEN 'manager' THEN 1
                WHEN 'front_desk' THEN 2 WHEN 'teacher' THEN 3 ELSE 4 END,
                lower(u.full_name)
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"team": rows})


@api_v1.route("/team", methods=["POST"])
@tenant_owner_required
def create_tenant_team_member():
    """Create or activate a tenant operational account within the plan limit."""

    payload = _json_payload()
    email = _clean_text(payload, "email").lower()
    full_name = _clean_text(payload, "fullName", _clean_text(payload, "full_name"))
    role = _clean_text(payload, "role").lower()
    password = _clean_text(payload, "temporaryPassword", _clean_text(payload, "password"))
    allowed_roles = {"manager", "teacher", "front_desk", "staff"}
    if role not in allowed_roles:
        return _error(f"role must be one of: {', '.join(sorted(allowed_roles))}.")
    if not full_name:
        return _error("fullName is required.")
    try:
        _validate_optional_email("email", email)
    except ValueError as exc:
        return _error(str(exc))
    if not email:
        return _error("email is required.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT id, plan_code FROM tenants WHERE id = %s FOR UPDATE", (tenant.tenant_id,))
            plan_row = fetch_one(
                conn,
                "SELECT p.user_limit FROM tenants t JOIN plans p ON p.code = t.plan_code WHERE t.id = %s",
                (tenant.tenant_id,),
            )
            active_users = fetch_one(
                conn,
                "SELECT count(*) AS n FROM memberships WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'",
                (tenant.tenant_id,),
            )
            existing_user = fetch_one(conn, "SELECT id, status FROM users WHERE lower(email) = %s", (email,))
            existing_membership = None
            if existing_user:
                existing_membership = fetch_one(
                    conn,
                    "SELECT id, status FROM memberships WHERE tenant_id = %s AND user_id = %s",
                    (tenant.tenant_id, existing_user["id"]),
                )
                if existing_membership:
                    return _error("This email is already on the tenant team. Update the existing member instead.", 409)
                return _error(
                    "This email already belongs to another StudioSaaS account. Cross-tenant access cannot be added from tenant team management.",
                    409,
                )
            if int(active_users["n"] or 0) >= int(plan_row["user_limit"]):
                return _error(
                    f"User limit reached ({plan_row['user_limit']}). Upgrade the plan before adding another team member.",
                    403,
                )
            if len(password) < 8:
                return _error("temporaryPassword must be at least 8 characters for a new user.")
            cur.execute(
                """
                INSERT INTO users (email, password_hash, full_name, status)
                VALUES (%s, %s, %s, 'active') RETURNING id
                """,
                (email, _hash_password(password), full_name),
            )
            user_id = cur.fetchone()["id"]
            cur.execute(
                """
                INSERT INTO memberships (tenant_id, user_id, role, status)
                VALUES (%s, %s, %s, 'active')
                ON CONFLICT (tenant_id, user_id) DO UPDATE
                SET role = EXCLUDED.role, status = 'active'
                RETURNING id
                """,
                (tenant.tenant_id, user_id, role),
            )
            membership_id = cur.fetchone()["id"]
        _refresh_tenant_usage(conn, tenant.tenant_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="team.member_upserted",
            resource_type="membership",
            resource_id=membership_id,
            metadata={"role": role, "email": email},
        )
        conn.commit()
    return jsonify({"ok": True, "membershipId": membership_id}), 201


@api_v1.route("/team/<membership_id>", methods=["PATCH"])
@tenant_owner_required
def update_tenant_team_member(membership_id: str):
    """Change an operational member's role or active state."""

    try:
        parsed_id = str(_uuid.UUID(membership_id))
    except (ValueError, AttributeError):
        return _error("Invalid membership id.")
    payload = _json_payload()
    role = _clean_text(payload, "role").lower()
    status = _clean_text(payload, "status", "active").lower()
    if role not in {"manager", "teacher", "front_desk", "staff"}:
        return _error("Only operational team roles can be changed here.")
    if status not in {"active", "disabled"}:
        return _error("status must be active or disabled.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, status
                FROM memberships
                WHERE id = %s AND tenant_id = %s AND role <> 'owner'
                FOR UPDATE
                """,
                (parsed_id, tenant.tenant_id),
            )
            existing = cur.fetchone()
            if not existing:
                return _error("Operational team membership was not found.", 404)
            if status == "active" and existing["status"] != "active":
                plan_row = fetch_one(
                    conn,
                    "SELECT p.user_limit FROM tenants t JOIN plans p ON p.code = t.plan_code WHERE t.id = %s",
                    (tenant.tenant_id,),
                )
                active_users = fetch_one(
                    conn,
                    "SELECT count(*) AS n FROM memberships WHERE tenant_id = %s AND status = 'active' AND role <> 'parent'",
                    (tenant.tenant_id,),
                )
                if int(active_users["n"] or 0) >= int(plan_row["user_limit"]):
                    return _error(
                        f"User limit reached ({plan_row['user_limit']}). Upgrade the plan before reactivating this member.",
                        403,
                    )
            cur.execute(
                """
                UPDATE memberships
                SET role = %s, status = %s
                WHERE id = %s AND tenant_id = %s AND role <> 'owner'
                RETURNING id
                """,
                (role, status, parsed_id, tenant.tenant_id),
            )
            cur.fetchone()
        _refresh_tenant_usage(conn, tenant.tenant_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="team.member_updated",
            resource_type="membership",
            resource_id=parsed_id,
            metadata={"role": role, "status": status},
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/tenant/brand-workspace", methods=["GET"])
@tenant_owner_required
def get_brand_workspace():
    """Return the tenant brand draft and recent published versions."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        draft = fetch_one(
            conn,
            """
            SELECT payload, updated_at
            FROM tenant_brand_drafts
            WHERE tenant_id = %s
            """,
            (tenant.tenant_id,),
        )
        versions = fetch_all(
            conn,
            """
            SELECT v.id, v.version_number, v.published_at,
                   v.source_version_id, u.full_name AS published_by
            FROM tenant_brand_versions v
            LEFT JOIN users u ON u.id = v.published_by_user_id
            WHERE v.tenant_id = %s
            ORDER BY v.version_number DESC
            LIMIT 20
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"draft": draft, "versions": versions})


@api_v1.route("/tenant/brand-draft", methods=["PUT"])
@tenant_owner_required
def save_brand_draft():
    """Save an unpublished brand payload for later preview and publication."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    if not _clean_text(payload, "name"):
        return _error("Studio name is required.")
    encoded = json.dumps(payload)
    if len(encoded.encode("utf-8")) > 256_000:
        return _error("Brand draft is too large.", 413)
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_brand_drafts (tenant_id, payload, updated_by_user_id, updated_at)
                VALUES (%s, %s::jsonb, %s, now())
                ON CONFLICT (tenant_id) DO UPDATE
                SET payload = EXCLUDED.payload,
                    updated_by_user_id = EXCLUDED.updated_by_user_id,
                    updated_at = now()
                """,
                (tenant.tenant_id, encoded, getattr(g.actor, "user_id", None)),
            )
        _audit_request(conn, tenant_id=tenant.tenant_id, action="brand.draft_saved", resource_type="tenant_brand")
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/tenant/brand-versions/<version_id>/restore", methods=["POST"])
@tenant_owner_required
def restore_brand_version(version_id: str):
    """Restore one published version into the draft workspace without going live."""

    try:
        parsed_id = str(_uuid.UUID(version_id))
    except (ValueError, AttributeError):
        return _error("Invalid brand version id.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        version = fetch_one(
            conn,
            "SELECT id, payload FROM tenant_brand_versions WHERE id = %s AND tenant_id = %s",
            (parsed_id, tenant.tenant_id),
        )
        if not version:
            return _error("Brand version was not found.", 404)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tenant_brand_drafts (tenant_id, payload, updated_by_user_id, updated_at)
                VALUES (%s, %s::jsonb, %s, now())
                ON CONFLICT (tenant_id) DO UPDATE
                SET payload = EXCLUDED.payload,
                    updated_by_user_id = EXCLUDED.updated_by_user_id,
                    updated_at = now()
                """,
                (tenant.tenant_id, json.dumps(version["payload"]), getattr(g.actor, "user_id", None)),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="brand.version_restored_to_draft",
            resource_type="tenant_brand",
            resource_id=parsed_id,
        )
        conn.commit()
    return jsonify({"ok": True, "draft": version["payload"]})


@api_v1.route("/tenant", methods=["PATCH"])
@tenant_owner_required

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
            FOR UPDATE
            """,
            (tenant.tenant_id,),
        )
        current_settings = dict(current["settings"] or {})
        # Subscription plans are owned by Super Admin. Tenant owners can view
        # their plan but cannot change commercial entitlements from Studio Admin.
        plan_code = current["plan_code"]
        logo_url = _clean_text(payload, "logoUrl", current["logo_url"] or "")
        primary_color = _clean_text(payload, "primaryColor", current["primary_color"])
        secondary_color = _clean_text(payload, "secondaryColor", current["secondary_color"])
        contact_email = _clean_text(payload, "contactEmail", _clean_text(payload, "email", current["contact_email"])).lower()
        cms_layout = _clean_text(payload, "cmsLayout", current_settings.get("cms_layout", "bar")).lower()
        try:
            category = _normalize_category(_clean_text(payload, "category", current_settings.get("category", "general")))
            preset = _preset_for(category)
            slogan = _clean_text(payload, "slogan", current_settings.get("slogan", preset["slogan"]))
            registration_profile = _normalize_registration_profile(
                payload.get("registrationProfile", current_settings.get("registration_profile")),
                category,
            )
            copy_pack = _normalize_copy_pack(payload.get("copyPack", current_settings.get("copy_pack")), category)
            localized_copy = _normalize_localized_copy(
                payload.get("localizedCopy", current_settings.get("localized_copy")),
                category,
            )
            hero_profile = _normalize_hero_profile(
                payload.get("heroProfile", current_settings.get("hero_profile")),
                category,
                _clean_text(payload, "name", current["name"]),
            )
            website_profile = _normalize_website_profile(payload.get("websiteProfile", current_settings.get("website_profile")))
            principal_profile = _normalize_principal_profile(
                payload.get("principalProfile", current_settings.get("principal_profile")),
                _clean_text(payload, "name", current["name"]),
            )
            faq_items = _normalize_faq_items(payload.get("faqItems", current_settings.get("faq_items")), category)
            visual_theme = _normalize_visual_theme(
                payload.get("visualTheme", current_settings.get("visual_theme")),
                primary_color,
                secondary_color,
                category,
            )
        except ValueError as exc:
            return _error(str(exc))
        show_welcome = payload.get("showWelcome", current_settings.get("show_welcome", "true"))
        if isinstance(show_welcome, str):
            show_welcome = show_welcome.strip().lower() != "false"
        else:
            show_welcome = bool(show_welcome)
        timezone_name = _clean_text(payload, "timezone", current["timezone"])
        try:
            _validate_logo_url(logo_url)
            _validate_hex_color("Primary color", primary_color)
            _validate_hex_color("Secondary color", secondary_color)
            _validate_optional_email("Contact email", contact_email)
            timezone_name = _validated_timezone(timezone_name)
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
                "localized_copy": localized_copy,
                "hero_profile": hero_profile,
                "website_profile": website_profile,
                "principal_profile": principal_profile,
                "faq_items": faq_items,
                "visual_theme": visual_theme,
            }
        )
        with conn.cursor() as cur:
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
                    timezone_name,
                    json.dumps(current_settings),
                    tenant.tenant_id,
                ),
            )
            cur.execute(
                """
                SELECT COALESCE(max(version_number), 0) + 1 AS next_version
                FROM tenant_brand_versions
                WHERE tenant_id = %s
                """,
                (tenant.tenant_id,),
            )
            next_version = int(cur.fetchone()["next_version"])
            cur.execute(
                """
                INSERT INTO tenant_brand_versions (
                    tenant_id, version_number, payload, published_by_user_id
                )
                VALUES (%s, %s, %s::jsonb, %s)
                """,
                (tenant.tenant_id, next_version, json.dumps(payload), getattr(g.actor, "user_id", None)),
            )
            cur.execute("DELETE FROM tenant_brand_drafts WHERE tenant_id = %s", (tenant.tenant_id,))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="brand.published",
            resource_type="tenant_brand",
            metadata={"version": next_version},
        )
        conn.commit()
        row = _tenant_response(conn)
    return jsonify({"tenant": row, "publishedVersion": next_version})


@api_v1.route("/tenant/brand", methods=["GET"])
@auth_required
def get_tenant_brand():
    """Return published branding used by Studio Admin and public surfaces."""

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
                "localizedCopy": row["localized_copy"] or _normalize_localized_copy({}, row["category"] or "general"),
                "heroProfile": row["hero_profile"] or _default_hero_profile(row["category"] or "general", row["name"]),
                "websiteProfile": row["website_profile"] or _default_website_profile(),
                "principalProfile": row["principal_profile"] or _default_principal_profile(row["name"]),
                "faqItems": row["faq_items"] or _default_faq_items(row["category"] or "general"),
                "visualTheme": row["visual_theme"] or _default_visual_theme(
                    row["primary_color"], row["secondary_color"], row["category"] or "general"
                ),
            }
        }
    )


@api_v1.route("/students", methods=["GET"])
@permission_required("students:read")
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
                   s.mobile, s.email, s.enrolled_on, s.tags, s.created_at, s.updated_at,
                   COALESCE(ca.balance, 0)::float AS balance,
                   count(*) OVER ()::int AS _total
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
    total = int(rows[0]["_total"]) if rows else 0
    for row in rows:
        row.pop("_total", None)
    return jsonify({"students": rows, "total": total, "limit": limit, "offset": offset})


@api_v1.route("/students/<student_id>", methods=["GET"])
@permission_required("students:read")
def get_student(student_id: str):
    """Return one student with credit summary for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            SELECT s.id, s.display_name, s.first_name, s.last_name, s.status,
                   s.birthday, s.enrolled_on, s.parent_name, s.mobile, s.email, s.wechat,
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
@permission_required("credits:read")
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
@permission_required("registrations:read")
def list_registrations():
    """List recent public registration submissions for the resolved tenant."""

    try:
        limit, offset = _parse_pagination()
    except ValueError as exc:
        return _error(str(exc))
    status = request.args.get("status", "").strip().lower()
    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, status, first_name, last_name, parent_name, mobile,
                   email, message, submitted_at, updated_at, reviewed_at,
                   reviewed_by_user_id, student_id, duplicate_of_registration_id,
                   review_note, source, source_path, source_language, campaign,
                   assigned_user_id, first_contacted_at, next_follow_up_at,
                   converted_at, loss_reason, privacy_consent_at,
                   privacy_notice_version,
                   count(*) OVER ()::int AS _total
            FROM registrations
            WHERE tenant_id = %s
              AND (%s = '' OR status = %s)
            ORDER BY submitted_at DESC
            LIMIT %s OFFSET %s
            """,
            (tenant.tenant_id, status, status, limit, offset),
        )
    total = int(rows[0]["_total"]) if rows else 0
    for row in rows:
        row.pop("_total", None)
    return jsonify({"registrations": rows, "total": total, "limit": limit, "offset": offset})

@api_v1.route("/registrations/<registration_id>", methods=["PATCH"])
@permission_required("registrations:write")

def update_registration_status(registration_id: str):
    """Advance a registration through follow-up, conversion, or closure."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()
        new_status = _clean_text(payload, "status", "").lower().strip()
        convert_to_student = bool(payload.get("convertToStudent", payload.get("convert_to_student", False)))
        review_note = _clean_text(payload, "reviewNote", _clean_text(payload, "decisionReason", ""))[:500]
        next_follow_up = _clean_text(payload, "nextFollowUpAt", _clean_text(payload, "next_follow_up_at", ""))
        follow_up_supplied = "nextFollowUpAt" in payload or "next_follow_up_at" in payload
        loss_reason = _clean_text(payload, "lossReason", _clean_text(payload, "loss_reason", ""))[:500]

        allowed_statuses = {
            "pending", "contacted", "trial_booked", "waiting", "approved",
            "converted", "rejected", "duplicate", "lost", "archived",
        }
        if new_status not in allowed_statuses:
            return _error(f"status must be one of: {', '.join(sorted(allowed_statuses))}.")
        if new_status in {"rejected", "lost", "archived"} and not (review_note or loss_reason):
            return _error("A review note or loss reason is required when closing a registration.")

        with conn.cursor() as cur:
            created_student_id = None
            linked_student_id = None
            cur.execute(
                """
                SELECT id, first_name, last_name, parent_name, mobile, email, message,
                       payload, student_id, status
                FROM registrations
                WHERE tenant_id = %s AND id = %s
                """,
                (tenant.tenant_id, registration_id),
            )
            reg = cur.fetchone()
            if not reg:
                return _error("Registration not found.", 404)
            try:
                validate_registration_transition(str(reg["status"]), new_status)
            except ValueError as exc:
                return _error(str(exc), 409)

            if convert_to_student or new_status in {"approved", "converted"}:
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
                    current_students, student_limit = _student_capacity(conn, tenant.tenant_id)
                    if current_students >= student_limit:
                        return _error(
                            f"Student limit reached ({student_limit}). Upgrade the plan before converting this registration.",
                            403,
                        )
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

            registration_publication = (
                (reg.get("payload") or {}).get("publicationConsent")
                if isinstance(reg.get("payload"), dict)
                else None
            )
            if linked_student_id and isinstance(registration_publication, dict) and registration_publication.get("confirmed"):
                cur.execute(
                    """
                    INSERT INTO student_publication_consent_events (
                        tenant_id, student_id, status, consent_by, relationship,
                        consent_method, notice_version, note, actor_user_id,
                        source_registration_id
                    ) VALUES (%s, %s, 'confirmed', %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, source_registration_id)
                    WHERE source_registration_id IS NOT NULL DO NOTHING
                    """,
                    (
                        tenant.tenant_id,
                        linked_student_id,
                        str(registration_publication.get("consentBy") or "")[:120],
                        str(registration_publication.get("relationship") or "")[:60],
                        str(registration_publication.get("method") or "registration_form")[:60],
                        str(registration_publication.get("noticeVersion") or "")[:40],
                        str(registration_publication.get("note") or "")[:500],
                        getattr(getattr(g, "actor", None), "user_id", None),
                        registration_id,
                    ),
                )

            actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
            cur.execute(
                """
                UPDATE registrations
                SET status = %s,
                    student_id = COALESCE(%s, student_id),
                    reviewed_by_user_id = %s,
                    reviewed_at = CASE WHEN %s <> 'pending' THEN now() ELSE reviewed_at END,
                    review_note = CASE WHEN %s <> '' THEN %s ELSE review_note END,
                    assigned_user_id = CASE
                        WHEN %s IN ('contacted', 'trial_booked', 'waiting')
                            THEN COALESCE(assigned_user_id, %s)
                        ELSE assigned_user_id
                    END,
                    first_contacted_at = CASE
                        WHEN %s = 'contacted' THEN COALESCE(first_contacted_at, now())
                        ELSE first_contacted_at
                    END,
                    next_follow_up_at = CASE
                        WHEN %s IN ('approved', 'converted', 'rejected', 'duplicate', 'lost', 'archived')
                            THEN NULL
                        WHEN %s THEN NULLIF(%s, '')::timestamptz
                        ELSE next_follow_up_at
                    END,
                    converted_at = CASE
                        WHEN %s IN ('approved', 'converted') AND %s::uuid IS NOT NULL
                            THEN COALESCE(converted_at, now())
                        ELSE converted_at
                    END,
                    loss_reason = CASE WHEN %s <> '' THEN %s ELSE loss_reason END,
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
                    new_status,
                    actor_user_id,
                    new_status,
                    new_status,
                    follow_up_supplied,
                    next_follow_up,
                    new_status,
                    linked_student_id,
                    loss_reason,
                    loss_reason,
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
        if new_status in ("approved", "rejected") and reg.get("email"):
            tenant_row = fetch_one(conn, "SELECT name FROM tenants WHERE id = %s", (tenant.tenant_id,))
            _notifications.send_safely(
                conn,
                tenant_id=tenant.tenant_id,
                template_key=f"registration_{new_status}",
                to_email=reg["email"],
                context={
                    "parent_name": reg["parent_name"] or "there",
                    "student_name": f"{reg['first_name']} {reg['last_name']}".strip(),
                    "studio_name": tenant_row["name"] if tenant_row else "",
                    "review_note_line": f"\n\nNote from the studio: {review_note}" if (new_status == "rejected" and review_note) else "",
                },
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
@permission_required("portfolio:read")
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
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        row = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM students WHERE tenant_id = %s) AS students,
                (SELECT count(*) FROM students WHERE tenant_id = %s AND status = 'active') AS active_students,
                (SELECT count(*) FROM registrations WHERE tenant_id = %s AND status = 'pending') AS pending_registrations,
                (SELECT count(*) FROM portfolio_items WHERE tenant_id = %s) AS portfolio_items,
                (SELECT count(*) FROM credit_accounts WHERE tenant_id = %s AND course_id IS NULL AND balance <= low_balance_threshold) AS low_balance,
                (SELECT count(*) FROM attendance_sessions
                  WHERE tenant_id = %s AND reversed_at IS NULL
                    AND COALESCE(class_date, (attended_at AT TIME ZONE %s)::date)
                        = (now() AT TIME ZONE %s)::date) AS today_checkins
            """,
            (
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
                timezone_name,
                timezone_name,
            ),
        )
        # A3 (v5.3 harvest): 经营真账（估算）— split cash received from
        # revenue actually earned, and surface the prepaid liability.
        # avg price = net top-up money / net top-up credits (refund rows are
        # stored signed, so plain sums net out automatically).
        biz = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM attendance_sessions
                  WHERE tenant_id = %s AND reversed_at IS NULL) AS attended_total,
                (SELECT count(*) FROM attendance_sessions
                  WHERE tenant_id = %s AND reversed_at IS NULL
                    AND date_trunc('month', COALESCE(class_date, (attended_at AT TIME ZONE %s)::date))
                        = date_trunc('month', (now() AT TIME ZONE %s)::date)) AS attended_month,
                (SELECT COALESCE(sum(fee_aud_cents), 0) FROM credit_transactions
                  WHERE tenant_id = %s AND transaction_type IN ('purchase', 'refund')) AS cash_net_cents,
                (SELECT COALESCE(sum(amount), 0)::float FROM credit_transactions
                  WHERE tenant_id = %s AND transaction_type IN ('purchase', 'refund')
                    AND fee_aud_cents <> 0) AS paid_credits_net,
                (SELECT COALESCE(sum(balance), 0)::float FROM credit_accounts
                  WHERE tenant_id = %s AND course_id IS NULL) AS outstanding_credits
            """,
            (
                tenant.tenant_id,
                tenant.tenant_id,
                timezone_name,
                timezone_name,
                tenant.tenant_id,
                tenant.tenant_id,
                tenant.tenant_id,
            ),
        )
        cash_net = (biz["cash_net_cents"] or 0) / 100.0
        paid_credits = float(biz["paid_credits_net"] or 0)
        avg_price = round(cash_net / paid_credits, 2) if paid_credits > 0 else 0.0
        business = {
            "attended_total": int(biz["attended_total"] or 0),
            "attended_month": int(biz["attended_month"] or 0),
            "avg_price": avg_price,
            "earned_revenue": round((biz["attended_total"] or 0) * avg_price, 2),
            "prepaid_liability": round(float(biz["outstanding_credits"] or 0) * avg_price, 2),
            "cash_net": round(cash_net, 2),
        }
    payload = dict(row or {})
    payload["business"] = business
    return jsonify({"dashboard": payload})


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
                   settings->'copy_pack' AS copy_pack,
                   settings->'localized_copy' AS localized_copy,
                   settings->'hero_profile' AS hero_profile,
                   settings->'website_profile' AS website_profile,
                   settings->'principal_profile' AS principal_profile,
                   settings->'faq_items' AS faq_items,
                   settings->'visual_theme' AS visual_theme
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
    row["localized_copy"] = row["localized_copy"] or _normalize_localized_copy({}, category)
    row["hero_profile"] = row["hero_profile"] or _default_hero_profile(category, row["name"])
    row["website_profile"] = row["website_profile"] or _default_website_profile()
    row["principal_profile"] = row["principal_profile"] or _default_principal_profile(row["name"])
    row["faq_items"] = row["faq_items"] or _default_faq_items(category)
    row["visual_theme"] = row["visual_theme"] or _default_visual_theme(
        row["primary_color"], row["secondary_color"], category
    )
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
    row["localizedCopy"] = row["localized_copy"]
    row["heroProfile"] = row["hero_profile"]
    row["websiteProfile"] = row["website_profile"]
    row["principalProfile"] = row["principal_profile"]
    row["faqItems"] = row["faq_items"]
    row["visualTheme"] = row["visual_theme"]
    return jsonify({"brand": row})


_PUBLIC_ANALYTICS_EVENTS = {
    "page_view",
    "cta_click",
    "registration_started",
    "registration_submitted",
}


def _analytics_text_map(value: object, *, keys: set[str], limit: int) -> dict[str, str]:
    """Return only allowlisted, bounded strings for an analytics JSON field."""

    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, str] = {}
    for key in keys:
        item = str(value.get(key) or "").strip()[:limit]
        if item:
            cleaned[key] = item
    return cleaned


@api_v1.route("/public/<tenant_slug>/analytics", methods=["POST"])
def public_record_analytics(tenant_slug: str):
    """Record one anonymous, allowlisted portal conversion event.

    The supplied browser token is salted and hashed before persistence. The
    table never receives an IP address, user agent, student identifier, name,
    phone, email, or raw token.
    """

    if _rate_limited(f"analytics:{tenant_slug}:{_client_ip()}", 60):
        return _error("Too many analytics events.", 429)
    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    event_name = str(payload.get("event") or "").strip()
    if event_name not in _PUBLIC_ANALYTICS_EVENTS:
        return _error("Unsupported analytics event.")
    browser_token = str(payload.get("sessionId") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,80}", browser_token):
        return _error("A valid anonymous session ID is required.")
    path = str(payload.get("path") or "").strip()[:200]
    if path and (not path.startswith("/") or "\n" in path or "\r" in path):
        return _error("Analytics path is invalid.")
    campaign = _analytics_text_map(
        payload.get("campaign"),
        keys={"source", "medium", "campaign"},
        limit=80,
    )
    metadata = _analytics_text_map(payload.get("metadata"), keys={"label"}, limit=80)
    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        secret = str(current_app.config.get("SECRET_KEY") or current_app.secret_key or "")
        session_hash = hashlib.sha256(
            f"{secret}:{tenant.tenant_id}:{browser_token}".encode("utf-8")
        ).hexdigest()
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO public_analytics_events (
                    tenant_id, event_name, path, session_hash, campaign, metadata
                )
                VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb)
                """,
                (
                    tenant.tenant_id,
                    event_name,
                    path,
                    session_hash,
                    json.dumps(campaign),
                    json.dumps(metadata),
                ),
            )
    return jsonify({"ok": True}), 202


@api_v1.route("/tenant/analytics", methods=["GET"])
@tenant_admin_required
def tenant_public_analytics():
    """Return aggregate-only public portal metrics for the active tenant."""

    try:
        days = int(request.args.get("days", "30"))
    except ValueError:
        return _error("Analytics days must be an integer.")
    if days not in {7, 30, 90}:
        return _error("Analytics days must be 7, 30, or 90.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        totals = fetch_one(
            conn,
            """
            SELECT count(*) AS events,
                   count(DISTINCT session_hash) AS anonymous_sessions,
                   count(*) FILTER (WHERE event_name = 'page_view') AS page_views,
                   count(*) FILTER (WHERE event_name = 'cta_click') AS cta_clicks,
                   count(*) FILTER (WHERE event_name = 'registration_started') AS registration_started,
                   count(*) FILTER (WHERE event_name = 'registration_submitted') AS registration_submitted
            FROM public_analytics_events
            WHERE tenant_id = %s
              AND occurred_at >= now() - make_interval(days => %s)
            """,
            (tenant.tenant_id, days),
        ) or {}
        daily = fetch_all(
            conn,
            """
            SELECT occurred_at::date AS day, event_name, count(*) AS count
            FROM public_analytics_events
            WHERE tenant_id = %s
              AND occurred_at >= now() - make_interval(days => %s)
            GROUP BY occurred_at::date, event_name
            ORDER BY occurred_at::date, event_name
            """,
            (tenant.tenant_id, days),
        )
        campaigns = fetch_all(
            conn,
            """
            SELECT COALESCE(NULLIF(campaign->>'campaign', ''), '(direct)') AS campaign,
                   count(*) FILTER (WHERE event_name = 'page_view') AS page_views,
                   count(*) FILTER (WHERE event_name = 'registration_submitted') AS registrations
            FROM public_analytics_events
            WHERE tenant_id = %s
              AND occurred_at >= now() - make_interval(days => %s)
            GROUP BY COALESCE(NULLIF(campaign->>'campaign', ''), '(direct)')
            ORDER BY registrations DESC, page_views DESC
            LIMIT 20
            """,
            (tenant.tenant_id, days),
        )
    summary = {key: int(value or 0) for key, value in totals.items()}
    return jsonify({"days": days, "summary": summary, "daily": daily, "campaigns": campaigns})


def _public_portfolio_copy(value: object) -> str:
    """Remove obvious contact details and seeded full-name titles from public copy."""

    text = str(value or "").strip()[:500]
    if re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|(?:\+?\d[\s().-]*){8,}", text):
        return ""
    if re.match(r"^.+['’]s\s+Demo\s+Work$", text, re.IGNORECASE):
        return "Student artwork"
    return text


@api_v1.route("/public/<tenant_slug>/gallery", methods=["GET"])
def public_gallery(tenant_slug: str):
    """Return public-gallery portfolio items explicitly shared by a tenant."""

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return jsonify({"items": [], "featureEnabled": False})
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.title, p.description, p.artwork_date, p.created_at
            FROM portfolio_items p
            JOIN media_assets m ON m.id = p.media_asset_id AND m.tenant_id = p.tenant_id
            JOIN media_variants mv
              ON mv.tenant_id = p.tenant_id
             AND mv.media_asset_id = p.media_asset_id
             AND mv.variant = 'display'
            JOIN students s ON s.id = p.student_id AND s.tenant_id = p.tenant_id
            JOIN LATERAL (
                SELECT status
                FROM student_publication_consent_events e
                WHERE e.tenant_id = p.tenant_id AND e.student_id = p.student_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
            ) consent ON consent.status = 'confirmed'
            WHERE p.tenant_id = %s
              AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL
              AND s.status <> 'archived'
            ORDER BY COALESCE(p.artwork_date, p.created_at::date) DESC, p.created_at DESC
            LIMIT 24
            """,
            (tenant.tenant_id,),
        )
    items = [
        {
            "id": str(row["id"]),
            "title": _public_portfolio_copy(row["title"]),
            "comment": _public_portfolio_copy(row["description"]),
            "date": str(row["artwork_date"] or row["created_at"].date()),
            "mediaUrl": f"/v1/public/{tenant_slug}/gallery/{row['id']}/media",
        }
        for row in rows
    ]
    return jsonify({"items": items})


@api_v1.route("/public/<tenant_slug>/gallery/<portfolio_item_id>/media", methods=["GET"])
def public_gallery_media(tenant_slug: str, portfolio_item_id: str):
    """Serve media for a public-gallery item without exposing private portfolios."""

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 404)
        row = fetch_one(
            conn,
            """
            SELECT p.media_asset_id
            FROM portfolio_items p
            JOIN students s ON s.id = p.student_id AND s.tenant_id = p.tenant_id
            JOIN media_variants mv
              ON mv.tenant_id = p.tenant_id
             AND mv.media_asset_id = p.media_asset_id
             AND mv.variant = 'display'
            JOIN LATERAL (
                SELECT status
                FROM student_publication_consent_events e
                WHERE e.tenant_id = p.tenant_id AND e.student_id = p.student_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
            ) consent ON consent.status = 'confirmed'
            WHERE p.tenant_id = %s
              AND p.id::text = %s
              AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL
              AND s.status <> 'archived'
            LIMIT 1
            """,
            (tenant.tenant_id, portfolio_item_id),
        )
        if not row:
            return _error("Portfolio item was not found.", 404)
        response = _send_media_asset(
            conn,
            tenant_id=tenant.tenant_id,
            media_asset_id=str(row["media_asset_id"]),
            variant="display",
        )
        if isinstance(response, tuple):
            return response
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response


@api_v1.route("/public/<tenant_slug>/balance-query", methods=["POST"])
def public_balance_query(tenant_slug: str):
    """Return low-sensitivity balance data after an exact, unambiguous match."""

    client_key = f"balance-query:{tenant_slug}:{_client_ip()}"
    if _rate_limited(client_key, 10):
        return _error("Too many balance queries. Please wait a moment.", 429)

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    if not name or not phone:
        return jsonify({"match": False, "error": "name_and_phone_required"}), 400
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        lookup = _find_public_student(
            conn,
            tenant_id=tenant.tenant_id,
            name=name,
            phone=phone,
        )
        row = None
        if lookup.student:
            row = fetch_one(
                conn,
                """
                SELECT s.display_name, COALESCE(ca.balance, 0)::float AS balance
                FROM students s
                LEFT JOIN credit_accounts ca
                  ON ca.tenant_id = s.tenant_id
                 AND ca.student_id = s.id
                 AND ca.course_id IS NULL
                WHERE s.tenant_id = %s AND s.id = %s
                """,
                (tenant.tenant_id, lookup.student["id"]),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="public.balance_lookup",
            resource_type="student_lookup",
            metadata={"matched": bool(row), "ambiguous": lookup.status == "ambiguous"},
        )
        conn.commit()
        if not row:
            return jsonify({"match": False, "ambiguous": lookup.status == "ambiguous"})
        return jsonify(
            {
                "match": True,
                "name": row["display_name"],
                "balance": row["balance"],
            }
        )


@api_v1.route("/students/<student_id>/access-code", methods=["POST", "DELETE"])
@permission_required("students:write")
def manage_student_access_code(student_id: str):
    """Generate, rotate, or revoke one student's private-area access code."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            if not _revoke_student_access_code(
                conn, tenant_id=tenant.tenant_id, student_id=student_id
            ):
                return _error("Student was not found.", 404)
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="student_access.revoked",
                resource_type="student",
                resource_id=student_id,
            )
            conn.commit()
            return jsonify({"ok": True, "hasAccessCode": False})

        try:
            code, updated_at = _generate_student_access_code(
                conn, tenant_id=tenant.tenant_id, student_id=student_id
            )
        except ValueError as exc:
            return _error(str(exc), 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="student_access.generated",
            resource_type="student",
            resource_id=student_id,
            metadata={"plaintext_stored": False},
        )
        conn.commit()
    return jsonify(
        {
            "ok": True,
            "code": code,
            "hasAccessCode": True,
            "updatedAt": updated_at,
        }
    )


@api_v1.route("/students/<student_id>/publication-consent", methods=["PUT", "DELETE"])
@permission_required("portfolio:write")
def manage_student_publication_consent(student_id: str):
    """Append a publication-consent confirmation or withdrawal event."""

    payload = request.get_json(silent=True) or {}
    status = "withdrawn" if request.method == "DELETE" else "confirmed"
    consent_by = _clean_text(payload, "consentBy", _clean_text(payload, "consent_by"))[:120]
    relationship = _clean_text(payload, "relationship")[:60]
    consent_method = _clean_text(
        payload, "consentMethod", _clean_text(payload, "consent_method")
    )[:60]
    notice_version = _clean_text(
        payload, "noticeVersion", _clean_text(payload, "notice_version", "2026-07-18")
    )[:40]
    note = _clean_text(payload, "note")[:500]
    if status == "confirmed" and not (consent_by and relationship and consent_method):
        return _error("Consent person, relationship, and method are required.")
    if status == "withdrawn" and not note:
        return _error("A withdrawal note is required.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        student = fetch_one(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student was not found.", 404)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO student_publication_consent_events (
                    tenant_id, student_id, status, consent_by, relationship,
                    consent_method, notice_version, note, actor_user_id
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    status,
                    consent_by,
                    relationship,
                    consent_method,
                    notice_version,
                    note,
                    getattr(g.actor, "user_id", None),
                ),
            )
            event = cur.fetchone()
            unpublished = 0
            if status == "withdrawn":
                cur.execute(
                    """
                    UPDATE portfolio_items
                    SET visibility = 'private', updated_at = now()
                    WHERE tenant_id = %s AND student_id = %s AND visibility = 'shared'
                    """,
                    (tenant.tenant_id, student_id),
                )
                unpublished = cur.rowcount
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"publication_consent.{status}",
            resource_type="student",
            resource_id=student_id,
            metadata={
                "event_id": str(event["id"]),
                "notice_version": notice_version,
                "unpublished_items": unpublished,
            },
        )
        conn.commit()
    return jsonify(
        {
            "ok": True,
            "consent": {
                "id": str(event["id"]),
                "status": status,
                "consentBy": consent_by,
                "relationship": relationship,
                "consentMethod": consent_method,
                "noticeVersion": notice_version,
                "createdAt": event["created_at"].isoformat(),
            },
            "unpublishedItems": unpublished,
        }
    )


@api_v1.route("/public/<tenant_slug>/student/unlock", methods=["POST"])
def public_student_unlock(tenant_slug: str):
    """Issue a one-hour HttpOnly student session after access-code verification."""

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    code = str(payload.get("code") or "").strip()
    if not name or not phone or len(code) != 6 or not code.isdigit():
        return _error("Name, phone, and a six-digit access code are required.", 400)

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        fingerprint = _student_lookup_fingerprint(name, phone)
        if _student_access_locked(
            conn,
            tenant_id=tenant.tenant_id,
            lookup_hash=fingerprint,
            ip_address=_client_ip(),
        ):
            return _error("Too many attempts. Please try again later.", 429)
        lookup = _find_public_student(
            conn, tenant_id=tenant.tenant_id, name=name, phone=phone
        )
        if not lookup.student or not _verify_student_access_code(lookup.student, code):
            _record_student_access_failure(
                conn,
                tenant_id=tenant.tenant_id,
                lookup_hash=fingerprint,
                ip_address=_client_ip(),
            )
            _audit(
                conn,
                tenant_id=tenant.tenant_id,
                action="student_access.failed",
                resource_type="student_access",
                metadata={"ambiguous": lookup.status == "ambiguous"},
            )
            conn.commit()
            return _error("The login details could not be verified.", 401)

        _clear_student_access_failures(
            conn,
            tenant_id=tenant.tenant_id,
            lookup_hash=fingerprint,
            ip_address=_client_ip(),
        )
        raw_token, expires_at = _create_student_access_session(
            conn,
            tenant_id=tenant.tenant_id,
            student_id=str(lookup.student["id"]),
            ip_address=_client_ip(),
        )
        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action="student_access.unlocked",
            resource_type="student",
            resource_id=str(lookup.student["id"]),
        )
        conn.commit()

    response = make_response(
        jsonify(
            {
                "ok": True,
                "name": lookup.student["display_name"],
                "expiresAt": expires_at,
            }
        )
    )
    response.set_cookie(
        _student_cookie_name(),
        raw_token,
        max_age=3600,
        secure=_student_cookie_secure(),
        httponly=True,
        samesite="Lax",
        path="/",
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@api_v1.route("/public/<tenant_slug>/student/private", methods=["GET"])
def public_student_private(tenant_slug: str):
    """Return private records for the student bound to the HttpOnly session."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        access = _resolve_student_access_session(
            conn, tenant_id=tenant.tenant_id, raw_token=_student_cookie_token()
        )
        if not access:
            return _error("Student access is required.", 401)
        student_id = str(access["student_id"])
        summary = fetch_one(
            conn,
            """
            SELECT s.display_name, COALESCE(ca.balance, 0)::float AS balance
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id
             AND ca.student_id = s.id
             AND ca.course_id IS NULL
            WHERE s.tenant_id = %s AND s.id = %s
            """,
            (tenant.tenant_id, student_id),
        )
        attendance = fetch_all(
            conn,
            """
            SELECT a.class_date::text AS date,
                   CASE WHEN a.reversed_at IS NULL THEN 'attended' ELSE 'voided' END AS status,
                   COALESCE(c.name, '') AS course,
                   a.note
            FROM attendance_sessions a
            LEFT JOIN courses c ON c.tenant_id = a.tenant_id AND c.id = a.course_id
            WHERE a.tenant_id = %s AND a.student_id = %s
            ORDER BY a.class_date DESC, a.attended_at DESC
            LIMIT 50
            """,
            (tenant.tenant_id, student_id),
        )
        portfolio = fetch_all(
            conn,
            """
            SELECT p.id, p.media_asset_id, p.title, p.description,
                   COALESCE(p.artwork_date, p.created_at::date)::text AS date
            FROM portfolio_items p
            JOIN media_variants mv
              ON mv.tenant_id = p.tenant_id
             AND mv.media_asset_id = p.media_asset_id
             AND mv.variant = 'display'
            WHERE p.tenant_id = %s AND p.student_id = %s
            ORDER BY COALESCE(p.artwork_date, p.created_at::date) DESC, p.created_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id, student_id),
        )
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        next_class = fetch_one(
            conn,
            """
            SELECT cs.label AS course, to_char(cs.start_time, 'HH24:MI') AS time,
                   ((now() AT TIME ZONE %s)::date
                     + ((cs.weekday - extract(dow FROM (now() AT TIME ZONE %s)::date)::int + 7) %% 7)
                   )::text AS date
            FROM class_schedules cs
            JOIN class_schedule_students css
              ON css.tenant_id = cs.tenant_id AND css.schedule_id = cs.id
            WHERE cs.tenant_id = %s AND css.student_id = %s AND cs.is_active
            ORDER BY ((cs.weekday - extract(dow FROM (now() AT TIME ZONE %s)::date)::int + 7) %% 7),
                     cs.start_time
            LIMIT 1
            """,
            (timezone_name, timezone_name, tenant.tenant_id, student_id, timezone_name),
        )
    response = jsonify(
        {
            "ok": True,
            "student": {
                "name": summary["display_name"],
                "balance": summary["balance"],
            },
            "nextClass": next_class,
            "attendance": attendance,
            "portfolio": [
                {
                    "id": str(row["id"]),
                    "title": row["title"] or "",
                    "comment": row["description"] or "",
                    "date": row["date"],
                    "mediaUrl": f"/v1/public/{tenant_slug}/student/media/{row['media_asset_id']}",
                }
                for row in portfolio
            ],
        }
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@api_v1.route("/public/<tenant_slug>/student/media/<media_asset_id>", methods=["GET"])
def public_student_media(tenant_slug: str, media_asset_id: str):
    """Serve a safe display derivative owned by the unlocked student."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        access = _resolve_student_access_session(
            conn, tenant_id=tenant.tenant_id, raw_token=_student_cookie_token()
        )
        if not access:
            return _error("Media asset was not found.", 404)
        owned = fetch_one(
            conn,
            """
            SELECT 1 FROM media_assets
            WHERE tenant_id = %s AND id = %s AND owner_student_id = %s
            """,
            (tenant.tenant_id, media_asset_id, access["student_id"]),
        )
        if not owned:
            return _error("Media asset was not found.", 404)
        response = _send_media_asset(
            conn,
            tenant_id=tenant.tenant_id,
            media_asset_id=media_asset_id,
            variant="display",
        )
        if isinstance(response, tuple):
            return response
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response


@api_v1.route("/public/<tenant_slug>/student/logout", methods=["POST"])
def public_student_logout(tenant_slug: str):
    """Revoke the current private session and clear both cookie variants."""

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        _revoke_student_access_session(
            conn, tenant_id=tenant.tenant_id, raw_token=_student_cookie_token()
        )
        conn.commit()
    response = make_response(jsonify({"ok": True}))
    for cookie_name in ("__Host-studiosaas-student", "studiosaas_student"):
        response.delete_cookie(
            cookie_name,
            path="/",
            secure=cookie_name.startswith("__Host-"),
            httponly=True,
            samesite="Lax",
        )
    response.headers["Cache-Control"] = "private, no-store"
    return response


@api_v1.route("/public/<tenant_slug>/registration-media", methods=["POST"])
def public_registration_media_upload(tenant_slug: str):
    """Upload a tenant-scoped registration photo before the registration is submitted."""

    client_key = f"registration-media:{_client_ip()}"
    now = time.time()
    _public_rate_limit[client_key] = [t for t in _public_rate_limit.get(client_key, []) if now - t < 60]
    if len(_public_rate_limit[client_key]) >= 5:
        return _error("Too many uploads. Please wait a moment.", 429)
    _public_rate_limit[client_key].append(now)

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        if not _plan_feature_enabled(conn, tenant.tenant_id, "public_registration"):
            return _error("Public registration is not available for this studio plan.", 403)
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
    """Reject the retired URL-token flow in favour of HttpOnly student sessions."""

    return api_error(
        "This private portfolio flow has been retired. Use the student access-code session.",
        410,
        error="student_session_required",
    )


@api_v1.route("/public/<tenant_slug>/media/<media_asset_id>", methods=["GET"])
def public_media_asset(tenant_slug: str, media_asset_id: str):
    """Serve safe public brand media or token-protected portfolio media."""

    raw_token = request.args.get("token", "")
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        asset = fetch_one(
            conn,
            "SELECT asset_type, mime_type FROM media_assets WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, media_asset_id),
        )
        if not asset:
            return _error("Media asset was not found.", 404)
        if asset["asset_type"] in {"logo", "website_image"}:
            if str(asset["mime_type"] or "").startswith("image/svg"):
                return _error("Media asset was not found.", 404)
            return _send_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                media_asset_id=media_asset_id,
                variant="display",
            )
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Media asset was not found.", 404)
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
        response = _send_media_asset(
            conn,
            tenant_id=tenant.tenant_id,
            media_asset_id=media_asset_id,
            variant="display",
        )
        if isinstance(response, tuple):
            return response
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response


@api_v1.route("/public/<tenant_slug>/programs", methods=["GET"])
def public_programs(tenant_slug: str):
    """Public course catalogue for the tenant landing page (B5)."""

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        rows = fetch_all(
            conn,
            """
            SELECT name, description, category, age_range, duration_minutes,
                   price_aud_cents
            FROM courses
            WHERE tenant_id = %s AND is_active
            ORDER BY category, name
            LIMIT 50
            """,
            (tenant.tenant_id,),
        )
    programs = [
        {
            "name": row["name"],
            "description": row["description"] or "",
            "category": row["category"] or "",
            "ageRange": row["age_range"] or "",
            "durationMinutes": row["duration_minutes"],
            "priceAud": (row["price_aud_cents"] or 0) / 100.0,
        }
        for row in rows
    ]
    return jsonify({"ok": True, "programs": programs})


@api_v1.route("/public/<tenant_slug>/registrations", methods=["POST"])
def public_create_registration(tenant_slug: str):
    """Create a public registration for a tenant-backed register page.

    Rate-limited to 5 requests per minute per client IP to prevent spam.
    """

    # Simple rate limiting: 5 requests per minute per IP
    client_ip = _client_ip()
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
    # S4 (LetsPaintCMS v6.6.5): honeypot — the registration form renders a
    # hidden `website` field humans never see. Bots that fill it get a
    # silent fake success: nothing is stored, no signal is leaked.
    if str(payload.get("website") or "").strip():
        return jsonify({"ok": True, "success": True, "message": "Registration received."})

    consent_value = payload.get(
        "privacyConsent",
        payload.get("privacy_consent", payload.get("consent", False)),
    )
    privacy_consent = consent_value is True or str(consent_value).strip().lower() in {"1", "true", "yes", "on"}
    if not privacy_consent:
        return _error("Privacy consent is required before submitting registration.", 400)
    privacy_notice_version = str(
        payload.get("privacyNoticeVersion") or payload.get("privacy_notice_version") or "2026-07-12"
    ).strip()[:40]
    publication_raw = payload.get("publicationConsent", payload.get("publication_consent"))
    publication_consent = None
    if isinstance(publication_raw, dict) and bool(publication_raw.get("confirmed")):
        publication_consent = {
            "confirmed": True,
            "consentBy": str(publication_raw.get("consentBy") or publication_raw.get("consent_by") or "").strip()[:120],
            "relationship": str(publication_raw.get("relationship") or "").strip()[:60],
            "method": str(publication_raw.get("method") or "registration_form").strip()[:60],
            "noticeVersion": str(publication_raw.get("noticeVersion") or privacy_notice_version).strip()[:40],
            "note": str(publication_raw.get("note") or "Optional artwork publication consent recorded at registration.").strip()[:500],
        }
        if not publication_consent["consentBy"] or not publication_consent["relationship"]:
            return _error("Publication consent requires the consenting person and relationship.")
        payload["publicationConsent"] = publication_consent

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
    source = str(payload.get("source") or "standalone_register").strip().lower()[:40]
    if source not in {"portal", "standalone_register", "qr", "campaign"}:
        source = "standalone_register"
    source_path = str(payload.get("sourcePath") or payload.get("source_path") or request.referrer or "").strip()[:500]
    source_language = str(payload.get("language") or payload.get("sourceLanguage") or "").strip().lower()[:10]
    if source_language not in {"zh", "en", "zh-cn", "en-au"}:
        source_language = ""
    campaign = {
        key: str(payload.get(key) or "").strip()[:120]
        for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term")
        if str(payload.get(key) or "").strip()
    }
    if not first_name or not mobile:
        return _error("firstName and mobile are required.")
    try:
        _validate_optional_email("email", email)
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        plan = fetch_one(
            conn,
            """
            SELECT p.features
            FROM tenants t
            JOIN plans p ON p.code = t.plan_code
            WHERE t.id = %s
            """,
            (tenant.tenant_id,),
        )
        if not plan or not bool((plan.get("features") or {}).get("public_registration", False)):
            return _error("Public registration is not available for this studio plan.", 403)
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
                        duplicate_of_registration_id, review_note,
                        source, source_path, source_language, campaign,
                        privacy_consent_at, privacy_notice_version
                    )
                    VALUES (
                        %s, 'duplicate', %s, %s, %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s, %s, %s, %s::jsonb, now(), %s
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
                        source,
                        source_path,
                        source_language,
                        json.dumps(campaign),
                        privacy_notice_version,
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
                        "privacy_notice_version": privacy_notice_version,
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
                    mobile, email, message, payload,
                    source, source_path, source_language, campaign,
                    privacy_consent_at, privacy_notice_version
                )
                VALUES (%s, 'pending', %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s::jsonb, now(), %s)
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
                    source,
                    source_path,
                    source_language,
                    json.dumps(campaign),
                    privacy_notice_version,
                ),
            )
            registration_id = cur.fetchone()["id"]
        _audit(
            conn,
            tenant_id=tenant.tenant_id,
            action="registration.created",
            resource_type="registration",
            resource_id=registration_id,
            metadata={
                "source": source,
                "language": source_language,
                "campaign": campaign,
                "privacy_notice_version": privacy_notice_version,
            },
        )
        # Make the lead durable before any SMTP work. Notification delivery is
        # best-effort and must never decide whether the registration exists.
        conn.commit()
        tenant_row = fetch_one(
            conn,
            """
            SELECT name, contact_email,
                   settings->>'studio_admin_email' AS studio_admin_email
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        studio_name = tenant_row["name"] if tenant_row else tenant_slug
        if email:
            _notifications.send_safely(
                conn,
                tenant_id=tenant.tenant_id,
                template_key="registration_received",
                to_email=email,
                context={
                    "parent_name": parent_name or "there",
                    "student_name": f"{first_name} {last_name}".strip(),
                    "studio_name": studio_name,
                },
            )
        admin_email = (
            (tenant_row.get("studio_admin_email") or tenant_row.get("contact_email") or "").strip()
            if tenant_row else ""
        )
        if admin_email:
            _notifications.send_safely(
                conn,
                tenant_id=tenant.tenant_id,
                template_key="registration_admin_alert",
                to_email=admin_email,
                context={
                    "registration_id": str(registration_id),
                    "student_name": f"{first_name} {last_name}".strip(),
                    "contact_name": parent_name or f"{first_name} {last_name}".strip(),
                    "mobile": mobile or "—",
                    "email": email or "—",
                    "studio_name": studio_name,
                },
            )
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


# The CMS UI filters logs by these Chinese action labels (e.g. rosterDone
# counts '上课签到' rows) — map ledger transaction types back to them so the
# CMS's history, stats, and undo lookups work off credit_transactions.
LEGACY_ACTION_BY_TYPE = {
    "consume": "上课签到",
    "purchase": "充值购课",
    "refund": "撤销签到",
    "adjustment": "调整课时",
    "migration": "期初导入",
    "expire": "课时过期",
}


def _sanitize_legacy_board(value, key_limit: int = 500, id_limit: int = 200) -> dict:
    """Sanitize CMS roster/group boards ({label: [student ids]}) for storage."""

    result: dict[str, list[str]] = {}
    if isinstance(value, dict):
        for key, ids in list(value.items())[:key_limit]:
            if isinstance(ids, list):
                result[str(key)[:60]] = [str(item)[:64] for item in ids[:id_limit]]
    return result


def _legacy_log_change(tx_type: str, amount: float):
    """Format a ledger amount the way legacy CMS logs express it."""

    value = float(amount or 0)
    if tx_type in ("purchase", "refund", "migration") and value >= 0:
        return f"+{value:g}"
    if tx_type in ("consume", "expire"):
        return -abs(value)
    return value  # adjustment / 退款退课: stored signed


def _legacy_log_action(tx_type: str, amount: float) -> str:
    """Map a ledger row to the CMS's Chinese action label."""

    if tx_type == "refund" and float(amount or 0) < 0:
        return "退款退课"  # A2: negative refund = 退课, not undo-check-in
    return LEGACY_ACTION_BY_TYPE.get(tx_type, tx_type)


def _legacy_data_for_tenant(conn, tenant_id: str) -> dict:
    """Build the legacy CMS JSON shape from tenant-scoped PostgreSQL rows."""

    students = fetch_all(
        conn,
        """
        SELECT s.id, s.first_name, s.last_name, s.display_name, s.status,
               s.birthday, s.enrolled_on, s.parent_name, s.mobile, s.email, s.wechat,
               s.tags, s.notes, s.created_at, s.student_photo_asset_id,
               (s.access_code_hash <> '' AND s.access_code_revoked_at IS NULL) AS has_access_code,
               s.access_code_updated_at,
               consent.status AS publication_consent_status,
               consent.consent_by AS publication_consent_by,
               consent.relationship AS publication_consent_relationship,
               consent.consent_method AS publication_consent_method,
               consent.notice_version AS publication_notice_version,
               consent.created_at AS publication_consent_at,
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
        LEFT JOIN LATERAL (
            SELECT e.status, e.consent_by, e.relationship, e.consent_method,
                   e.notice_version, e.created_at
            FROM student_publication_consent_events e
            WHERE e.tenant_id = s.tenant_id AND e.student_id = s.id
            ORDER BY e.created_at DESC, e.id DESC
            LIMIT 1
        ) consent ON true
        WHERE s.tenant_id = %s
        ORDER BY lower(s.display_name)
        """,
        (tenant_id,),
    )
    portfolio_rows = fetch_all(
        conn,
        """
        SELECT p.id, p.student_id, p.media_asset_id, p.title, p.description,
               p.artwork_date, p.visibility, p.public_consent_at, p.created_at
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
                "title": row["title"] or "",
                "public": row["visibility"] == "shared" and row["public_consent_at"] is not None,
                "visibility": row["visibility"],
                "publicConsentAt": row["public_consent_at"].isoformat() if row["public_consent_at"] else None,
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
    # Legacy-undo semantics: a voided check-in disappears from the CMS log
    # view (the full ledger keeps both rows — see CSV export). The reversal
    # refund row is hidden for the same reason.
    timezone_name = _tenant_timezone(conn, tenant_id)
    logs = fetch_all(
        conn,
        """
        SELECT ct.id, ct.student_id, s.display_name AS student_name,
               ct.transaction_type, ct.amount::float AS amount,
               ct.fee_aud_cents, ct.note,
               to_char(COALESCE(att.class_date,
                                (ct.occurred_at AT TIME ZONE %s)::date),
                       'DD/MM/YYYY') ||
               to_char(ct.occurred_at AT TIME ZONE %s,
                       ', HH24:MI:SS') AS occurred_display,
               att.id AS attendance_id
        FROM credit_transactions ct
        JOIN students s ON s.id = ct.student_id
        LEFT JOIN attendance_sessions att
          ON att.tenant_id = ct.tenant_id AND att.credit_transaction_id = ct.id
        LEFT JOIN attendance_sessions rev
          ON rev.tenant_id = ct.tenant_id AND rev.reversal_credit_transaction_id = ct.id
        WHERE ct.tenant_id = %s
          AND (att.id IS NULL OR att.reversed_at IS NULL)
          AND rev.id IS NULL
        ORDER BY ct.occurred_at DESC
        LIMIT 500
        """,
        (timezone_name, timezone_name, tenant_id),
    )
    settings_row = fetch_one(conn, "SELECT settings FROM tenants WHERE id = %s", (tenant_id,))
    legacy_state = ((settings_row["settings"] if settings_row else None) or {}).get("legacy_cms") or {}
    roster_rows = fetch_all(
        conn,
        """
        SELECT id, roster_date, student_id, source, status, note, created_at
        FROM daily_roster_entries
        WHERE tenant_id = %s AND status <> 'cancelled'
        ORDER BY roster_date, created_at, id
        """,
        (tenant_id,),
    )
    rosters: dict[str, list[str]] = {}
    roster_entries: dict[str, dict[str, dict]] = {}
    for row in roster_rows:
        date_key = row["roster_date"].isoformat()
        student_key = str(row["student_id"])
        rosters.setdefault(date_key, []).append(student_key)
        roster_entries.setdefault(date_key, {})[student_key] = {
            "id": str(row["id"]),
            "source": row["source"],
            "status": row["status"],
            "note": row["note"],
            "createdAt": row["created_at"].isoformat(),
        }
    pending = fetch_all(
        conn,
        """
        SELECT id, status, first_name, last_name, mobile, email, message,
               submitted_at, source, source_language, assigned_user_id,
               first_contacted_at, next_follow_up_at
        FROM registrations
        WHERE tenant_id = %s
          AND status IN ('pending', 'contacted', 'trial_booked', 'waiting')
        ORDER BY submitted_at DESC
        LIMIT 100
        """,
        (tenant_id,),
    )
    return {
        "students": [
            {
                "id": str(row["id"]),
                "status": row["status"],
                "firstName": row["first_name"],
                "lastName": row["last_name"],
                "name": row["display_name"],
                "mobile": row["mobile"],
                "email": row["email"],
                "wechat": row["wechat"],
                "birthday": str(row["birthday"] or ""),
                "enrollmentDate": str(row["enrolled_on"] or ""),
                "balance": row["balance"],
                "archived": row["status"] == "archived",
                "notes": row["notes"],
                "tags": row["tags"] or [],
                "photo": _media_token(str(row["student_photo_asset_id"])) if row["student_photo_asset_id"] else "",
                "portfolio": portfolio_by_student.get(str(row["id"]), []),
                "hasAccessCode": bool(row["has_access_code"]),
                "accessCodeUpdatedAt": (
                    row["access_code_updated_at"].isoformat()
                    if row["access_code_updated_at"] else None
                ),
                "publicationConsent": (
                    {
                        "status": row["publication_consent_status"],
                        "by": row["publication_consent_by"],
                        "relationship": row["publication_consent_relationship"],
                        "method": row["publication_consent_method"],
                        "noticeVersion": row["publication_notice_version"],
                        "at": row["publication_consent_at"].isoformat(),
                    }
                    if row["publication_consent_status"] else None
                ),
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
                "action": _legacy_log_action(row["transaction_type"], row["amount"]),
                "change": _legacy_log_change(row["transaction_type"], row["amount"]),
                "feePaid": round((row["fee_aud_cents"] or 0) / 100, 2),
                "note": row["note"],
                "date": row["occurred_display"],
                "attendanceId": str(row["attendance_id"]) if row["attendance_id"] else None,
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
                "source": row["source"],
                "sourceLanguage": row["source_language"],
                "firstContactedAt": str(row["first_contacted_at"] or ""),
                "nextFollowUpAt": str(row["next_follow_up_at"] or ""),
            }
            for row in pending
        ],
        "rosters": rosters,
        "rosterEntries": roster_entries,
        "groups": legacy_state.get("groups") or {},
        "rev": int(time.time()),
    }


def _project_legacy_data_for_role(data: dict, role: Role | None) -> dict:
    """Return the aggregate CMS payload permitted for one operational role."""

    projected = {**data}
    if role is Role.TEACHER:
        projected["packages"] = []
        projected["pending"] = []
        projected["logs"] = [
            {**row, "feePaid": 0}
            for row in data.get("logs", [])
            if row.get("action") in {"上课签到", "撤销签到"}
        ]
    elif role is Role.FRONT_DESK:
        projected["students"] = [
            {**student, "portfolio": []}
            for student in data.get("students", [])
        ]
    return projected


@api_v1.route("/legacy-cms/data", methods=["GET"])
@auth_required
def legacy_cms_data():
    """Return a role-projected tenant JSON shape for the CMS UI.

    The legacy CMS consumes a single aggregate payload.  Projection here is
    therefore a security boundary, not merely a visual preference: teachers
    must not receive acquisition or financial history, and front-desk users
    must not receive private portfolio records.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        data = _legacy_data_for_tenant(conn, tenant.tenant_id)
    role = getattr(getattr(g, "actor", None), "role", None)
    return jsonify(_project_legacy_data_for_role(data, role))


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
                    str(student.get("enrollmentDate") or ""),
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
                            enrolled_on = NULLIF(%s, '')::date,
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
                            birthday, enrolled_on, parent_name, mobile, email, wechat, notes, source_legacy_id
                        )
                        VALUES (%s, %s, %s, %s, %s, NULLIF(%s, '')::date,
                                COALESCE(NULLIF(%s, '')::date, CURRENT_DATE),
                                %s, %s, %s, %s, %s, NULLIF(%s, ''))
                        ON CONFLICT (tenant_id, source_legacy_id)
                        WHERE source_legacy_id IS NOT NULL AND source_legacy_id <> ''
                        DO UPDATE
                        SET first_name = EXCLUDED.first_name,
                            last_name = EXCLUDED.last_name,
                            display_name = EXCLUDED.display_name,
                            status = EXCLUDED.status,
                            birthday = EXCLUDED.birthday,
                            enrolled_on = EXCLUDED.enrolled_on,
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
                # Balances move only through the ledger (v1 attendance and
                # credit endpoints). The whole-save payload's balance is
                # ignored for existing students to stop stale-tab overwrites;
                # brand-new students get their initial balance as a
                # 'migration' transaction so the ledger stays complete.
                cur.execute(
                    """
                    SELECT id FROM credit_accounts
                    WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                    """,
                    (tenant.tenant_id, student_id),
                )
                if not cur.fetchone():
                    initial_balance = float(student.get("balance") or 0)
                    cur.execute(
                        """
                        INSERT INTO credit_accounts (tenant_id, student_id, course_id, balance, low_balance_threshold)
                        VALUES (%s, %s, NULL, %s, 2)
                        """,
                        (tenant.tenant_id, student_id, initial_balance),
                    )
                    if initial_balance:
                        cur.execute(
                            """
                            INSERT INTO credit_transactions (
                                tenant_id, student_id, actor_user_id,
                                transaction_type, amount, balance_after, note
                            )
                            VALUES (%s, %s, %s, 'migration', %s, %s, '期初余额（CMS 创建）')
                            """,
                            (
                                tenant.tenant_id,
                                student_id,
                                getattr(getattr(g, "actor", None), "user_id", None),
                                initial_balance,
                                initial_balance,
                            ),
                        )
            # Group templates remain low-risk CMS preferences. Daily rosters
            # are intentionally excluded here: daily_roster_entries is the
            # canonical PostgreSQL source and cannot be overwritten by a stale
            # aggregate save from another browser tab.
            cur.execute(
                """
                UPDATE tenants
                SET settings = jsonb_set(COALESCE(settings, '{}'::jsonb), '{legacy_cms}', %s::jsonb, true),
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    json.dumps({
                        "groups": _sanitize_legacy_board(payload.get("groups")),
                    }),
                    tenant.tenant_id,
                ),
            )
        _audit(conn, tenant_id=tenant.tenant_id, action="legacy_cms.saved", resource_type="legacy_cms")
        conn.commit()
        data = _legacy_data_for_tenant(conn, tenant.tenant_id)
    return jsonify({"status": "success", "rev": data["rev"], "data": data})


@api_v1.route("/media/<media_asset_id>", methods=["GET"])
@permission_required("students:read")
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
        if kind == "portfolio" and not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
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
@permission_required("students:write")
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
@permission_required("portfolio:write")
def legacy_cms_portfolio_upload():
    """Upload and attach one portfolio image using the legacy CMS response shape."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        student_id = str(request.form.get("studentId") or "").strip()
        note = str(request.form.get("note") or "").strip()[:500]
        title = str(request.form.get("title") or "").strip()[:120]   # B4
        date_str = str(request.form.get("date") or "").strip()
        visibility = _public_visibility(request.form.get("public"))
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
        if visibility == "shared" and not _active_publication_consent(
            conn, tenant_id=tenant.tenant_id, student_id=student_id
        ):
            return _error(
                "An active student publication consent record is required before publishing.",
                400,
            )
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
                    artwork_date, visibility, public_consent_at,
                    public_consent_by_user_id, public_consent_note
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s,
                        CASE WHEN %s = 'shared' THEN now() ELSE NULL END,
                        CASE WHEN %s = 'shared' THEN %s ELSE NULL END,
                        CASE WHEN %s = 'shared' THEN 'Confirmed in CMS before public publishing' ELSE '' END)
                RETURNING id, created_at
                """,
                (
                    tenant.tenant_id, student_id, media["id"], title, note,
                    artwork_date_val, visibility, visibility, visibility,
                    getattr(g.actor, "user_id", None), visibility,
                ),
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
                "title": title,
                "public": visibility == "shared",
                "visibility": visibility,
                "mediaUrl": f"/s/{tenant.slug}/v1/media/{media_id}",
            },
        }
    )


@api_v1.route("/legacy-cms/portfolio/<student_id>/<portfolio_item_id>", methods=["DELETE"])
@permission_required("portfolio:write")
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
@permission_required("portfolio:write")
def legacy_cms_portfolio_update(student_id: str, portfolio_item_id: str):
    """Update one portfolio note/date through the legacy CMS bridge."""

    payload = request.get_json(silent=True) or {}
    note = str(payload.get("note") or "").strip()[:500]
    title_raw = payload.get("title")
    title = None if title_raw is None else str(title_raw).strip()[:120]   # B4
    visibility = _public_visibility(payload.get("public")) if "public" in payload else None
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
        if visibility == "shared" and not _active_publication_consent(
            conn, tenant_id=tenant.tenant_id, student_id=student_id
        ):
            return _error(
                "An active student publication consent record is required before publishing.",
                400,
            )
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE portfolio_items
                SET title = COALESCE(%s, title),
                    description = %s,
                    visibility = COALESCE(%s, visibility),
                    public_consent_at = CASE WHEN %s = 'shared' THEN now() ELSE public_consent_at END,
                    public_consent_by_user_id = CASE WHEN %s = 'shared' THEN %s ELSE public_consent_by_user_id END,
                    public_consent_note = CASE WHEN %s = 'shared' THEN 'Confirmed in CMS before public publishing' ELSE public_consent_note END,
                    artwork_date = COALESCE(%s, artwork_date),
                    updated_at = now()
                WHERE tenant_id = %s AND student_id = %s AND id = %s
                RETURNING id
                """,
                (
                    title, note, visibility, visibility, visibility,
                    getattr(g.actor, "user_id", None), visibility, artwork_date_val,
                    tenant.tenant_id, student_id, portfolio_item_id,
                ),
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
                   (COALESCE(t.settings->>'test_fixture', 'false') = 'true') AS is_test,
                   EXISTS (
                       SELECT 1 FROM tenant_brand_versions bv WHERE bv.tenant_id = t.id
                   ) AS portal_published,
                   (COALESCE(t.settings->>'logo_url', '') <> '') AS logo_ready,
                   (COALESCE(t.settings->'hero_profile'->>'title', '') <> '') AS hero_ready,
                   (t.contact_email <> '' OR t.contact_phone <> '') AS contact_ready,
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
        validate_tenant_slug(data["slug"])
    except ValueError as exc:
        return _error(str(exc))
    except WorkspaceError as exc:
        return _error(str(exc))
    workspace_path = f"tenants/{data['slug']}"
    tenant_settings = json.loads(data["settings_json"])
    tenant_settings["workspace_path"] = workspace_path
    data["settings_json"] = json.dumps(tenant_settings)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM plans WHERE code = %s", (data["plan_code"],))
            if not cur.fetchone():
                return _error(f"Plan '{data['plan_code']}' was not found.", 404)
            cur.execute("SELECT 1 FROM tenants WHERE slug = %s", (data["slug"],))
            if cur.fetchone():
                return _error(f"Tenant slug '{data['slug']}' already exists.", 409)
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
    try:
        _workspace_for(data["slug"], data["name"])
    except ValueError as exc:
        # Compensate for a filesystem failure so the commercial control plane
        # never exposes a tenant whose public workspace was only half-created.
        with connect() as cleanup_conn:
            with cleanup_conn.cursor() as cur:
                cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
            cleanup_conn.commit()
        return _error(f"Tenant creation was rolled back: {exc}", 500)
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
            existing = fetch_one(
                conn,
                "SELECT slug, status, settings->>'workspace_path' AS workspace_path FROM tenants WHERE id = %s",
                (tenant_id,),
            )
            if not existing:
                return _error("Tenant was not found.", 404)
            try:
                validate_tenant_transition(str(existing["status"]), data["status"])
            except ValueError as exc:
                return _error(str(exc), 409)
            workspace_path = existing.get("workspace_path") or f"tenants/{existing['slug']}"
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


# ──────────────────────────────────────────────
# B4: Support Mode — platform admin acts inside a tenant, fully audited
# ──────────────────────────────────────────────

@api_v1.route("/admin/tenants/<tenant_id>/support-session", methods=["POST"])
@super_admin_required
def start_support_session(tenant_id: str):
    """Enter support mode for one tenant. Reason is mandatory and audited."""

    payload = _json_payload()
    reason = _clean_text(payload, "reason")[:300]
    if not reason:
        return _error("A reason is required to enter support mode.")

    with connect() as conn:
        tenant = fetch_one(
            conn,
            "SELECT id, slug, name FROM tenants WHERE id = %s",
            (tenant_id,),
        )
        if not tenant:
            return _error("Tenant not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant["id"],
            action="support.session_started",
            resource_type="tenant",
            resource_id=str(tenant["id"]),
            metadata={"reason": reason},
        )
        conn.commit()

    from flask import session as _fs
    _fs["support"] = {
        "tenant_id": str(tenant["id"]),
        "slug": tenant["slug"],
        "tenant_name": tenant["name"],
        "reason": reason,
        "started": time.time(),
    }
    return jsonify({"ok": True, "url": f"/{tenant['slug']}/studio-admin", "slug": tenant["slug"]})


@api_v1.route("/admin/support-session/end", methods=["POST"])
def end_support_session():
    """Exit support mode. Allowed for any logged-in session that has one."""

    from flask import session as _fs
    if "user_id" not in _fs:
        return _error("Authentication required.", 401)
    support = _fs.pop("support", None)
    if not support:
        return jsonify({"ok": True, "ended": False})
    with connect() as conn:
        _audit_request(
            conn,
            tenant_id=support.get("tenant_id"),
            action="support.session_ended",
            resource_type="tenant",
            resource_id=str(support.get("tenant_id") or ""),
            metadata={"reason": support.get("reason", "")},
        )
        conn.commit()
    return jsonify({"ok": True, "ended": True})


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
    requested_subscription_status = _clean_text(
        payload,
        "subscriptionStatus",
        _clean_text(payload, "subscription_status", ""),
    ).lower()
    if status not in TENANT_STATUSES:
        return _error(f"Tenant status must be one of: {', '.join(sorted(TENANT_STATUSES))}.")
    subscription_status = requested_subscription_status or canonical_subscription_status(status)
    if subscription_status not in SUBSCRIPTION_STATUSES:
        return _error(
            f"Subscription status must be one of: {', '.join(sorted(SUBSCRIPTION_STATUSES))}."
        )

    with connect() as conn:
        current = fetch_one(
            conn,
            """
            SELECT t.status, s.status AS subscription_status
            FROM tenants t
            LEFT JOIN subscriptions s ON s.tenant_id = t.id
            WHERE t.id = %s
            """,
            (tenant_id,),
        )
        if not current:
            return _error("Tenant was not found.", 404)
        try:
            validate_tenant_transition(str(current["status"]), status)
            validate_tenant_subscription_pair(status, subscription_status)
        except ValueError as exc:
            return _error(str(exc), 409)
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
    """Return platform usage and commercial lifecycle metrics."""

    with connect() as conn:
        row = fetch_one(
            conn,
            """
            WITH real_tenants AS (
                SELECT id, status, created_at
                FROM tenants
                WHERE COALESCE(settings->>'test_fixture', 'false') <> 'true'
            )
            SELECT
                (SELECT count(*) FROM real_tenants WHERE status NOT IN ('archived', 'deleted')) AS tenants,
                (
                    SELECT count(*) FROM subscriptions s JOIN real_tenants t ON t.id = s.tenant_id
                    WHERE s.status = 'active' AND t.status NOT IN ('archived', 'deleted')
                ) AS paid_tenants,
                (
                    SELECT count(*) FROM subscriptions s JOIN real_tenants t ON t.id = s.tenant_id
                    WHERE s.status = 'trialing' AND t.status NOT IN ('archived', 'deleted')
                ) AS trial_tenants,
                (SELECT count(*) FROM real_tenants WHERE status = 'onboarding') AS onboarding_tenants,
                (
                    SELECT count(*) FROM subscriptions s JOIN real_tenants t ON t.id = s.tenant_id
                    WHERE s.status = 'past_due' AND t.status NOT IN ('archived', 'deleted')
                ) AS past_due_tenants,
                (SELECT count(*) FROM real_tenants WHERE created_at >= now() - interval '30 days') AS new_tenants_30d,
                (
                    SELECT COALESCE(sum(p.monthly_price_aud), 0)
                    FROM subscriptions s
                    JOIN plans p ON p.code = s.plan_code
                    JOIN real_tenants t ON t.id = s.tenant_id
                    WHERE s.status = 'active' AND t.status NOT IN ('archived', 'deleted')
                ) AS mrr_aud,
                (
                    SELECT count(*)
                    FROM subscriptions s
                    JOIN real_tenants t ON t.id = s.tenant_id
                    WHERE s.status = 'trialing'
                      AND t.status NOT IN ('archived', 'deleted')
                      AND s.trial_ends_at >= now()
                      AND s.trial_ends_at <= now() + interval '7 days'
                ) AS trials_ending_7d,
                (
                    SELECT count(*) FROM registrations r JOIN real_tenants t ON t.id = r.tenant_id
                    WHERE r.submitted_at >= now() - interval '30 days'
                ) AS registrations_30d,
                (
                    SELECT count(*) FROM registrations r JOIN real_tenants t ON t.id = r.tenant_id
                    WHERE r.submitted_at >= now() - interval '30 days'
                      AND r.status IN ('approved', 'converted')
                ) AS converted_registrations_30d,
                (
                    SELECT count(*) FROM registrations r JOIN real_tenants t ON t.id = r.tenant_id
                    WHERE r.submitted_at >= now() - interval '30 days' AND r.source = 'portal'
                ) AS portal_registrations_30d,
                (
                    SELECT count(*) FROM registrations r JOIN real_tenants t ON t.id = r.tenant_id
                    WHERE r.submitted_at >= now() - interval '30 days' AND r.source <> 'portal'
                ) AS alternate_registrations_30d,
                (SELECT count(*) FROM students s JOIN real_tenants t ON t.id = s.tenant_id) AS students,
                (SELECT count(*) FROM portfolio_items p JOIN real_tenants t ON t.id = p.tenant_id) AS portfolio_items,
                (
                    SELECT COALESCE(sum(u.storage_used_mb), 0)
                    FROM tenant_usage u JOIN real_tenants t ON t.id = u.tenant_id
                ) AS storage_used_mb
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
@permission_required("students:write")

def create_student():
    """Create a new student and an empty credit account for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        current_students, student_limit = _student_capacity(conn, tenant.tenant_id)
        if current_students >= student_limit:
            return _error(
                f"Student limit reached ({student_limit}). Ask the StudioSaaS administrator to upgrade the plan.",
                403,
            )

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
        enrolled_on_str = _clean_text(
            payload, "enrollmentDate", _clean_text(payload, "enrolledOn")
        )
        tags_raw = payload.get("tags", [])
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",") if t.strip()]
        elif not isinstance(tags_raw, list):
            tags_raw = []
        notes = _clean_text(payload, "notes")

        try:
            birthday_val = None
            if birthday_str:
                birthday_val = _date.fromisoformat(birthday_str)
            enrolled_on_val = _date.today()
            if enrolled_on_str:
                enrolled_on_val = _date.fromisoformat(enrolled_on_str)
                if enrolled_on_val > _date.today():
                    return _error("enrollmentDate cannot be in the future.")
        except (ValueError, TypeError):
            return _error("birthday and enrollmentDate must be ISO-8601 dates (YYYY-MM-DD).")

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO students (
                tenant_id, first_name, last_name, display_name, status,
                birthday, enrolled_on, parent_name, mobile, email, wechat, tags, notes
            ) VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s, %s::text[], %s)
            RETURNING id
            """,
            (
                tenant.tenant_id, first_name, last_name, display_name,
                birthday_val, enrolled_on_val, parent_name, mobile, email, wechat, tags_raw, notes,
            ),
        )
        student_id = str(cur.fetchone()["id"])

        _ensure_default_credit_account(cur, tenant.tenant_id, student_id)

        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="student.created",
            resource_type="student",
            resource_id=student_id,
            metadata={"display_name": display_name},
        )

    return jsonify({"ok": True, "studentId": student_id}), 201


@api_v1.route("/students/<student_id>/archive", methods=["POST"])
@permission_required("students:write")

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
@permission_required("credits:read")
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
@permission_required("credits:write")

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

        legacy_type = _clean_text(payload, "legacy_type", "")

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
        if legacy_type == "debit":
            tx_type = "consume"
        elif legacy_type == "adjustment_in":
            tx_type = "adjustment"
        elif legacy_type == "adjustment_out":
            tx_type = "adjustment"
            delta = -abs(delta)  # negative adjustment
        elif legacy_type == "refund_out":
            # A2 (v5.3/v5.5 harvest): 退款退课 — credits leave the account and
            # the refunded money is a NEGATIVE fee so revenue sums net out.
            tx_type = "refund"
            delta = -abs(delta)
            fee_cents = -abs(fee_cents)
            if abs(delta) > current_balance:
                return _error("退课节数不能超过剩余课时。", 400)

        new_balance = current_balance + delta

        # The ledger stores the SIGNED movement so exports and the CMS log
        # view are self-describing (adjustment_out / refund_out are negative).
        cur.execute(
            """
            INSERT INTO credit_transactions (
                tenant_id, student_id, transaction_type, amount, balance_after, fee_aud_cents, note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, student_id, tx_type, delta, new_balance, fee_cents, note),
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
@permission_required("attendance:read")
def list_attendance_sessions():
    """List attendance sessions for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        student_id = request.args.get("studentId", "").strip()
        date_value = request.args.get("date", "").strip()
        limit, offset = _parse_pagination()
        filters = ["a.tenant_id = %s"]
        params: list[object] = [tenant.tenant_id]
        if student_id:
            filters.append("a.student_id = %s")
            params.append(student_id)
        if date_value:
            # A1: filter on the class date (make-up check-ins belong to
            # the day the class happened, not the day it was recorded).
            filters.append("COALESCE(a.class_date, (a.attended_at AT TIME ZONE %s)::date) = %s::date")
            params.extend([timezone_name, date_value])
        params.extend([limit, offset])
        rows = fetch_all(
            conn,
            f"""
            SELECT a.id, a.student_id, s.display_name AS student_name,
                   a.course_id, c.name AS course_name,
                   a.credit_transaction_id, a.reversal_credit_transaction_id,
                   a.attended_at, a.reversed_at, a.note, a.class_date::text AS class_date,
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
@permission_required("attendance:write")
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
    # A1 (v4.6 R1): the check-in is accounted on the class date. Defaults to
    # today (Melbourne); accepts back-dated make-ups up to 90 days and at
    # most tomorrow (pre-logging an evening class across midnight).
    class_date = _clean_text(payload, "classDate", _clean_text(payload, "class_date"))
    parsed_class_date = None
    if class_date:
        import datetime as _dt
        try:
            parsed_class_date = _dt.date.fromisoformat(class_date)
        except ValueError:
            return _error("classDate must look like YYYY-MM-DD.")
    else:
        class_date = None

    with connect() as conn:
        tenant = _tenant_context(conn)
        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        if parsed_class_date is not None:
            import datetime as _dt
            today = _dt.datetime.now(ZoneInfo(timezone_name)).date()
            if parsed_class_date > today + _dt.timedelta(days=1) or parsed_class_date < today - _dt.timedelta(days=90):
                return _error("classDate must be within the past 90 days (or tomorrow at most).")
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
                    credit_transaction_id, note, class_date
                )
                VALUES (%s, %s, %s, %s, %s, %s,
                        COALESCE(%s::date, (now() AT TIME ZONE %s)::date))
                RETURNING id, attended_at, class_date
                """,
                (
                    tenant.tenant_id,
                    student_id,
                    course_id,
                    getattr(g.actor, "user_id", None),
                    tx_id,
                    note,
                    class_date,
                    timezone_name,
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
            "classDate": str(session_row["class_date"]),
        }
    ), 201


# ──────────────────────────────────────────────
# P1: canonical daily roster + recurring schedule preview
# ──────────────────────────────────────────────

def _roster_date(value: object) -> _date:
    """Parse one ISO roster date or raise a user-facing validation error."""

    try:
        return _date.fromisoformat(str(value or ""))
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc


def _daily_roster_for_date(conn, tenant_id: str, roster_date: _date) -> dict:
    """Return explicit entries plus the recurring schedule preview for a date."""

    entries = fetch_all(
        conn,
        """
        SELECT dre.id, dre.student_id, s.display_name AS student_name,
               dre.source, dre.status, dre.note, dre.cancelled_at,
               dre.created_at, dre.updated_at
        FROM daily_roster_entries dre
        JOIN students s
          ON s.tenant_id = dre.tenant_id AND s.id = dre.student_id
        WHERE dre.tenant_id = %s AND dre.roster_date = %s
        ORDER BY dre.status = 'cancelled', lower(s.display_name), dre.created_at
        """,
        (tenant_id, roster_date),
    )
    weekday = roster_date.isoweekday() % 7
    schedule_rows = fetch_all(
        conn,
        """
        SELECT cs.id AS schedule_id, cs.label,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, cs.capacity, cs.course_id,
               c.name AS course_name, s.id AS student_id,
               s.display_name AS student_name
        FROM class_schedules cs
        LEFT JOIN courses c
          ON c.tenant_id = cs.tenant_id AND c.id = cs.course_id
        LEFT JOIN class_schedule_students css
          ON css.tenant_id = cs.tenant_id AND css.schedule_id = cs.id
        LEFT JOIN students s
          ON s.tenant_id = css.tenant_id AND s.id = css.student_id
         AND s.status <> 'archived'
        WHERE cs.tenant_id = %s AND cs.weekday = %s AND cs.is_active
        ORDER BY cs.start_time, lower(cs.label), lower(s.display_name)
        """,
        (tenant_id, weekday),
    )
    schedules_by_id: dict[str, dict] = {}
    for row in schedule_rows:
        schedule_id = str(row["schedule_id"])
        schedule = schedules_by_id.setdefault(
            schedule_id,
            {
                "id": schedule_id,
                "label": row["label"],
                "startTime": row["start_time"],
                "durationMinutes": row["duration_minutes"],
                "capacity": row["capacity"],
                "courseId": str(row["course_id"]) if row["course_id"] else None,
                "courseName": row["course_name"],
                "students": [],
            },
        )
        if row["student_id"]:
            schedule["students"].append(
                {"id": str(row["student_id"]), "name": row["student_name"]}
            )

    effective: dict[str, dict] = {}
    for schedule in schedules_by_id.values():
        for student in schedule["students"]:
            effective.setdefault(
                student["id"],
                {
                    "studentId": student["id"],
                    "studentName": student["name"],
                    "source": "schedule",
                    "scheduleIds": [],
                },
            )["scheduleIds"].append(schedule["id"])
    normalized_entries = []
    for row in entries:
        item = {
            "id": str(row["id"]),
            "studentId": str(row["student_id"]),
            "studentName": row["student_name"],
            "source": row["source"],
            "status": row["status"],
            "note": row["note"],
            "cancelledAt": row["cancelled_at"].isoformat() if row["cancelled_at"] else None,
            "createdAt": row["created_at"].isoformat(),
            "updatedAt": row["updated_at"].isoformat(),
        }
        normalized_entries.append(item)
        if row["status"] != "cancelled":
            effective[str(row["student_id"])] = {
                "studentId": str(row["student_id"]),
                "studentName": row["student_name"],
                "source": row["source"],
                "entryId": str(row["id"]),
                "status": row["status"],
                "scheduleIds": effective.get(str(row["student_id"]), {}).get("scheduleIds", []),
            }
    return {
        "date": roster_date.isoformat(),
        "entries": normalized_entries,
        "schedules": list(schedules_by_id.values()),
        "effectiveStudents": list(effective.values()),
    }


@api_v1.route("/daily-roster", methods=["GET"])
@auth_required
def get_daily_roster():
    """Return one normalized daily roster with recurring schedule preview."""

    try:
        roster_date = _roster_date(request.args.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _daily_roster_for_date(conn, tenant.tenant_id, roster_date)
    return jsonify({"roster": payload})


@api_v1.route("/daily-roster/preview", methods=["GET"])
@auth_required
def preview_daily_rosters():
    """Preview recurring and explicit rosters for a bounded date range."""

    try:
        start = _roster_date(request.args.get("from"))
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError) as exc:
        return _error("from must use YYYY-MM-DD and days must be an integer.")
    if not 1 <= days <= 31:
        return _error("days must be between 1 and 31.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        rosters = [
            _daily_roster_for_date(conn, tenant.tenant_id, start + _timedelta(days=offset))
            for offset in range(days)
        ]
    return jsonify({"rosters": rosters})


@api_v1.route("/daily-roster", methods=["POST"])
@permission_required("attendance:write")
def add_daily_roster_entries():
    """Add or restore explicit students on one tenant's daily roster."""

    payload = request.get_json(silent=True) or {}
    try:
        roster_date = _roster_date(payload.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    raw_ids = payload.get("studentIds")
    if raw_ids is None:
        raw_ids = [payload.get("studentId")]
    if not isinstance(raw_ids, list) or not raw_ids or len(raw_ids) > 200:
        return _error("studentIds must contain between 1 and 200 students.")
    student_ids: list[str] = []
    try:
        for value in raw_ids:
            student_id = str(_uuid.UUID(str(value)))
            if student_id not in student_ids:
                student_ids.append(student_id)
    except (ValueError, TypeError, AttributeError) as exc:
        return _error("Every studentId must be a valid UUID.")
    source = str(payload.get("source") or "manual").strip().lower()
    status = str(payload.get("status") or "scheduled").strip().lower()
    note = str(payload.get("note") or "").strip()[:500]
    if source not in {"manual", "group", "profile", "import"}:
        return _error("source must be manual, group, profile, or import.")
    if status not in {"scheduled", "makeup"}:
        return _error("status must be scheduled or makeup.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        students = fetch_all(
            conn,
            """
            SELECT id FROM students
            WHERE tenant_id = %s AND id = ANY(%s::uuid[]) AND status <> 'archived'
            """,
            (tenant.tenant_id, student_ids),
        )
        found_ids = {str(row["id"]) for row in students}
        missing = [student_id for student_id in student_ids if student_id not in found_ids]
        if missing:
            return _error("One or more students were not found in this tenant.", 404)
        actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
        entry_ids: list[str] = []
        with conn.cursor() as cur:
            for student_id in student_ids:
                cur.execute(
                    """
                    INSERT INTO daily_roster_entries (
                        tenant_id, roster_date, student_id, source, status,
                        note, created_by_user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, roster_date, student_id) DO UPDATE
                    SET source = EXCLUDED.source,
                        status = EXCLUDED.status,
                        status_before_cancel = NULL,
                        note = EXCLUDED.note,
                        cancelled_by_user_id = NULL,
                        cancelled_at = NULL,
                        updated_at = now()
                    RETURNING id
                    """,
                    (
                        tenant.tenant_id,
                        roster_date,
                        student_id,
                        source,
                        status,
                        note,
                        actor_user_id,
                    ),
                )
                entry_ids.append(str(cur.fetchone()["id"]))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.added",
            resource_type="daily_roster",
            resource_id=entry_ids[0] if len(entry_ids) == 1 else "",
            metadata={"date": roster_date.isoformat(), "students": student_ids, "source": source},
        )
        conn.commit()
        roster = _daily_roster_for_date(conn, tenant.tenant_id, roster_date)
    return jsonify({"ok": True, "entryIds": entry_ids, "roster": roster}), 201


@api_v1.route("/daily-roster/<entry_id>", methods=["DELETE"])
@permission_required("attendance:write")
def cancel_daily_roster_entry(entry_id: str):
    """Cancel an explicit roster entry without deleting its audit history."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        actor_user_id = getattr(getattr(g, "actor", None), "user_id", None)
        row = fetch_one(
            conn,
            """
            UPDATE daily_roster_entries
            SET status_before_cancel = status,
                status = 'cancelled',
                cancelled_by_user_id = %s,
                cancelled_at = now(),
                updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status <> 'cancelled'
            RETURNING id, roster_date, student_id
            """,
            (actor_user_id, tenant.tenant_id, entry_id),
        )
        if not row:
            existing = fetch_one(
                conn,
                "SELECT status FROM daily_roster_entries WHERE tenant_id = %s AND id = %s",
                (tenant.tenant_id, entry_id),
            )
            return _error("Roster entry is already cancelled.", 409) if existing else _error("Roster entry was not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.cancelled",
            resource_type="daily_roster",
            resource_id=entry_id,
            metadata={"date": str(row["roster_date"]), "student_id": str(row["student_id"])},
        )
        conn.commit()
    return jsonify({"ok": True, "entryId": entry_id, "date": str(row["roster_date"])})


@api_v1.route("/daily-roster/<entry_id>/undo", methods=["POST"])
@permission_required("attendance:write")
def undo_daily_roster_cancellation(entry_id: str):
    """Restore one cancelled daily roster entry by exact entry id."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            UPDATE daily_roster_entries
            SET status = COALESCE(status_before_cancel, 'scheduled'),
                status_before_cancel = NULL,
                cancelled_by_user_id = NULL,
                cancelled_at = NULL,
                updated_at = now()
            WHERE tenant_id = %s AND id = %s AND status = 'cancelled'
            RETURNING id, roster_date, student_id, status
            """,
            (tenant.tenant_id, entry_id),
        )
        if not row:
            existing = fetch_one(
                conn,
                "SELECT status FROM daily_roster_entries WHERE tenant_id = %s AND id = %s",
                (tenant.tenant_id, entry_id),
            )
            return _error("Roster entry is not cancelled.", 409) if existing else _error("Roster entry was not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.restored",
            resource_type="daily_roster",
            resource_id=entry_id,
            metadata={"date": str(row["roster_date"]), "student_id": str(row["student_id"])},
        )
        conn.commit()
    return jsonify({"ok": True, "entryId": entry_id, "date": str(row["roster_date"]), "status": row["status"]})


# ──────────────────────────────────────────────
# A1: recurring weekly class schedules (排课)
# weekday: 0=Sunday .. 6=Saturday (JS Date.getDay() convention)
# ──────────────────────────────────────────────

def _schedule_payload_fields(payload):
    """Validate and normalize class-schedule fields from a JSON payload."""

    label = _clean_text(payload, "label")[:80]
    try:
        weekday = int(payload.get("weekday"))
    except (TypeError, ValueError):
        raise ValueError("weekday must be an integer 0-6 (0=Sunday).")
    if not 0 <= weekday <= 6:
        raise ValueError("weekday must be an integer 0-6 (0=Sunday).")
    start_time = _clean_text(payload, "startTime", _clean_text(payload, "start_time", "16:00"))
    if not re.match(r"^\d{2}:\d{2}$", start_time):
        raise ValueError("startTime must look like HH:MM.")
    try:
        duration = int(payload.get("durationMinutes", payload.get("duration_minutes", 60)))
        capacity = int(payload.get("capacity", 10))
    except (TypeError, ValueError):
        raise ValueError("durationMinutes and capacity must be integers.")
    if duration <= 0 or capacity <= 0:
        raise ValueError("durationMinutes and capacity must be positive.")
    student_ids = payload.get("studentIds", payload.get("student_ids"))
    if student_ids is not None and not isinstance(student_ids, list):
        raise ValueError("studentIds must be a list of student ids.")
    return label, weekday, start_time, duration, capacity, student_ids


def _replace_schedule_students(cur, tenant_id, schedule_id, student_ids) -> int:
    """Replace a schedule's roster; only same-tenant students are accepted."""

    cur.execute("DELETE FROM class_schedule_students WHERE schedule_id = %s", (schedule_id,))
    count = 0
    for raw in (student_ids or [])[:200]:
        cur.execute(
            """
            INSERT INTO class_schedule_students (schedule_id, student_id, tenant_id)
            SELECT %s, s.id, s.tenant_id FROM students s
            WHERE s.tenant_id = %s AND s.id = %s AND s.status <> 'archived'
            ON CONFLICT DO NOTHING
            """,
            (schedule_id, tenant_id, str(raw)),
        )
        count += cur.rowcount
    return count


def _schedules_with_students(conn, tenant_id) -> list[dict]:
    rows = fetch_all(
        conn,
        """
        SELECT cs.id, cs.label, cs.weekday,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, cs.capacity, cs.is_active,
               c.name AS course_name, cs.course_id
        FROM class_schedules cs
        LEFT JOIN courses c ON c.id = cs.course_id
        WHERE cs.tenant_id = %s AND cs.is_active
        ORDER BY cs.weekday, cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    members = fetch_all(
        conn,
        """
        SELECT css.schedule_id, s.id, s.display_name AS name
        FROM class_schedule_students css
        JOIN students s ON s.id = css.student_id
        WHERE css.tenant_id = %s AND s.status <> 'archived'
        ORDER BY lower(s.display_name)
        """,
        (tenant_id,),
    )
    by_schedule: dict[str, list[dict]] = {}
    for m in members:
        by_schedule.setdefault(str(m["schedule_id"]), []).append({"id": str(m["id"]), "name": m["name"]})
    return [
        {
            "id": str(r["id"]),
            "label": r["label"],
            "weekday": r["weekday"],
            "startTime": r["start_time"],
            "durationMinutes": r["duration_minutes"],
            "capacity": r["capacity"],
            "courseId": str(r["course_id"]) if r["course_id"] else None,
            "courseName": r["course_name"],
            "students": by_schedule.get(str(r["id"]), []),
        }
        for r in rows
    ]


@api_v1.route("/class-schedules", methods=["GET"])
@auth_required
def list_class_schedules():
    """List active weekly class schedules with their student rosters."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"schedules": schedules})


@api_v1.route("/class-schedules", methods=["POST"])
@tenant_admin_required
def create_class_schedule():
    """Create a weekly class schedule (optionally with an initial roster)."""

    payload = _json_payload()
    try:
        label, weekday, start_time, duration, capacity, student_ids = _schedule_payload_fields(payload)
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            INSERT INTO class_schedules (tenant_id, label, weekday, start_time, duration_minutes, capacity)
            VALUES (%s, %s, %s, %s::time, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, label, weekday, start_time, duration, capacity),
        )
        schedule_id = str(row["id"])
        with conn.cursor() as cur:
            added = _replace_schedule_students(cur, tenant.tenant_id, schedule_id, student_ids)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.created",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": label, "weekday": weekday, "startTime": start_time, "students": added},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "scheduleId": schedule_id, "schedules": schedules}), 201


@api_v1.route("/class-schedules/<schedule_id>", methods=["PATCH"])
@tenant_admin_required
def update_class_schedule(schedule_id: str):
    """Update a schedule's fields and/or replace its student roster."""

    payload = _json_payload()
    with connect() as conn:
        tenant = _tenant_context(conn)
        existing = fetch_one(
            conn,
            """
            SELECT id, label, weekday, to_char(start_time, 'HH24:MI') AS start_time,
                   duration_minutes, capacity
            FROM class_schedules
            WHERE tenant_id = %s AND id = %s AND is_active
            """,
            (tenant.tenant_id, schedule_id),
        )
        if not existing:
            return _error("Schedule not found.", 404)
        merged = {
            "label": payload.get("label", existing["label"]),
            "weekday": payload.get("weekday", existing["weekday"]),
            "startTime": payload.get("startTime", payload.get("start_time", existing["start_time"])),
            "durationMinutes": payload.get("durationMinutes", payload.get("duration_minutes", existing["duration_minutes"])),
            "capacity": payload.get("capacity", existing["capacity"]),
            "studentIds": payload.get("studentIds", payload.get("student_ids")),
        }
        try:
            label, weekday, start_time, duration, capacity, student_ids = _schedule_payload_fields(merged)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE class_schedules
                SET label = %s, weekday = %s, start_time = %s::time,
                    duration_minutes = %s, capacity = %s, updated_at = now()
                WHERE tenant_id = %s AND id = %s
                """,
                (label, weekday, start_time, duration, capacity, tenant.tenant_id, schedule_id),
            )
            if student_ids is not None:
                _replace_schedule_students(cur, tenant.tenant_id, schedule_id, student_ids)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.updated",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": label, "weekday": weekday},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})


@api_v1.route("/class-schedules/<schedule_id>", methods=["DELETE"])
@tenant_admin_required
def delete_class_schedule(schedule_id: str):
    """Deactivate a schedule (kept for history; roster links cascade later)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            UPDATE class_schedules SET is_active = false, updated_at = now()
            WHERE tenant_id = %s AND id = %s AND is_active
            RETURNING label, weekday
            """,
            (tenant.tenant_id, schedule_id),
        )
        if not row:
            return _error("Schedule not found.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.deleted",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": row["label"], "weekday": row["weekday"]},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})


# ──────────────────────────────────────────────
# B2: durable portfolio share links (tenant admin + public viewer)
# ──────────────────────────────────────────────

SHARE_LINK_DEFAULT_DAYS = 30
SHARE_LINK_MAX_DAYS = 90


@api_v1.route("/students/<student_id>/share-links", methods=["GET"])
@permission_required("portfolio:write")
def list_share_links(student_id: str):
    """List portfolio share links for one student (newest first)."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, created_at, expires_at, revoked_at,
                   (expires_at > now() AND revoked_at IS NULL) AS active
            FROM share_tokens
            WHERE tenant_id = %s AND student_id = %s AND scope = 'student_portfolio'
            ORDER BY created_at DESC
            LIMIT 20
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"shareLinks": rows})


@api_v1.route("/students/<student_id>/share-links", methods=["POST"])
@permission_required("portfolio:write")
def create_share_link(student_id: str):
    """Create a durable share link for a student's portfolio.

    The raw token is returned once; only its SHA-256 hash is stored. The
    existing public media route honours these tokens (scope, expiry,
    revocation are all enforced there too).
    """

    payload = _json_payload()
    try:
        days = int(payload.get("days", SHARE_LINK_DEFAULT_DAYS))
    except (TypeError, ValueError):
        return _error("days must be an integer.")
    days = max(1, min(SHARE_LINK_MAX_DAYS, days))

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        student = fetch_one(
            conn,
            "SELECT id, display_name FROM students WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, student_id),
        )
        if not student:
            return _error("Student not found.", 404)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        row = fetch_one(
            conn,
            """
            INSERT INTO share_tokens (tenant_id, student_id, token_hash, scope, expires_at)
            VALUES (%s, %s, %s, 'student_portfolio', now() + make_interval(days => %s))
            RETURNING id, expires_at
            """,
            (tenant.tenant_id, student_id, token_hash, days),
        )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.share_link_created",
            resource_type="student",
            resource_id=student_id,
            metadata={"days": days, "share_token_id": str(row["id"])},
        )
        conn.commit()

    return jsonify({
        "ok": True,
        "id": str(row["id"]),
        "url": f"/shared/portfolio?token={raw_token}",
        "expiresAt": row["expires_at"].isoformat(),
    })


@api_v1.route("/share-links/<link_id>/revoke", methods=["POST"])
@permission_required("portfolio:write")
def revoke_share_link(link_id: str):
    """Revoke one share link; the public viewer and media URLs stop working."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            UPDATE share_tokens SET revoked_at = now()
            WHERE id = %s AND tenant_id = %s AND scope = 'student_portfolio' AND revoked_at IS NULL
            RETURNING student_id
            """,
            (link_id, tenant.tenant_id),
        )
        if not row:
            return _error("Share link not found or already revoked.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="portfolio.share_link_revoked",
            resource_type="student",
            resource_id=str(row["student_id"]),
            metadata={"share_token_id": link_id},
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/public/portfolio/<raw_token>", methods=["GET"])
def public_shared_portfolio(raw_token: str):
    """Public JSON for the shared portfolio viewer page. Rate-limited."""

    now = time.time()
    client_key = f"shared-portfolio:{_client_ip()}"
    _public_rate_limit[client_key] = [t for t in _public_rate_limit.get(client_key, []) if now - t < 60]
    if len(_public_rate_limit[client_key]) >= 20:
        return _error("Too many requests. Please wait a moment.", 429)
    _public_rate_limit[client_key].append(now)

    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    with connect() as conn:
        link = fetch_one(
            conn,
            """
            SELECT st.tenant_id, st.student_id, st.expires_at,
                   t.slug AS tenant_slug, t.name AS tenant_name,
                   t.primary_color, t.secondary_color,
                   t.settings->>'logo_url' AS logo_url,
                   s.display_name AS student_name
            FROM share_tokens st
            JOIN tenants t ON t.id = st.tenant_id
            JOIN students s ON s.id = st.student_id
            WHERE st.token_hash = %s
              AND st.scope = 'student_portfolio'
              AND st.expires_at > now()
              AND st.revoked_at IS NULL
            """,
            (token_hash,),
        )
        if not link:
            return _error("This link is invalid, expired, or has been revoked.", 410)
        if not _plan_feature_enabled(conn, link["tenant_id"], "portfolio"):
            return _error("This portfolio is not available for the current studio plan.", 410)
        rows = fetch_all(
            conn,
            """
            SELECT p.id, p.media_asset_id, p.title, p.description, p.artwork_date, p.created_at
            FROM portfolio_items p
            JOIN media_assets m ON m.id = p.media_asset_id AND m.tenant_id = p.tenant_id
            WHERE p.tenant_id = %s AND p.student_id = %s
            ORDER BY p.created_at DESC
            LIMIT 200
            """,
            (link["tenant_id"], link["student_id"]),
        )

    slug = link["tenant_slug"]
    items = [
        {
            "id": str(row["id"]),
            "mediaUrl": f"/v1/public/{slug}/media/{row['media_asset_id']}?token={raw_token}",
            "date": str(row["artwork_date"] or row["created_at"].date()),
            "note": row["description"] or "",
            "title": row["title"] or "",
        }
        for row in rows
    ]
    return jsonify({
        "ok": True,
        "studio": {
            "name": link["tenant_name"],
            "primaryColor": link["primary_color"],
            "secondaryColor": link["secondary_color"],
            "logoUrl": link["logo_url"],
        },
        "student": link["student_name"],
        "expiresAt": link["expires_at"].isoformat(),
        "items": items,
    })


# ──────────────────────────────────────────────
# B1: CSV data export (tenant admin)
# ──────────────────────────────────────────────

def _export_audit(conn, tenant, export_type: str, row_count: int) -> None:
    _audit_request(
        conn,
        tenant_id=tenant.tenant_id,
        action="data.exported",
        resource_type="export",
        metadata={"type": export_type, "rows": row_count},
    )
    conn.commit()


@api_v1.route("/export/students.csv", methods=["GET"])
@permission_required("data:export")
def export_students_csv():
    """Download all students (with balances) as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT s.display_name, s.first_name, s.last_name, s.status,
                   s.parent_name, s.mobile, s.email,
                   COALESCE(ca.balance, 0)::float AS balance,
                   s.created_at
            FROM students s
            LEFT JOIN credit_accounts ca
              ON ca.tenant_id = s.tenant_id AND ca.student_id = s.id AND ca.course_id IS NULL
            WHERE s.tenant_id = %s
            ORDER BY lower(s.display_name)
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "students", len(rows))
    header = ["Name", "First Name", "Last Name", "Status", "Parent", "Mobile", "Email", "Balance", "Created At"]
    data = ([r["display_name"], r["first_name"], r["last_name"], r["status"], r["parent_name"],
             r["mobile"], r["email"], r["balance"], r["created_at"]] for r in rows)
    return _csv_response(f"{tenant.slug}-students.csv", header, data)


@api_v1.route("/export/registrations.csv", methods=["GET"])
@permission_required("data:export")
def export_registrations_csv():
    """Download all registrations as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT status, first_name, last_name, parent_name, mobile, email,
                   message, review_note, privacy_consent_at,
                   privacy_notice_version, submitted_at, reviewed_at
            FROM registrations
            WHERE tenant_id = %s
            ORDER BY submitted_at DESC
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "registrations", len(rows))
    header = ["Status", "First Name", "Last Name", "Parent", "Mobile", "Email",
              "Message", "Review Note", "Privacy Consent At", "Privacy Notice Version",
              "Submitted At", "Reviewed At"]
    data = ([r["status"], r["first_name"], r["last_name"], r["parent_name"], r["mobile"], r["email"],
             r["message"], r["review_note"], r["privacy_consent_at"], r["privacy_notice_version"],
             r["submitted_at"], r["reviewed_at"]] for r in rows)
    return _csv_response(f"{tenant.slug}-registrations.csv", header, data)


@api_v1.route("/export/credit-ledger.csv", methods=["GET"])
@permission_required("data:export")
def export_credit_ledger_csv():
    """Download the full credit transaction ledger as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT ct.occurred_at, s.display_name AS student, c.name AS course,
                   ct.transaction_type, ct.amount::float AS amount,
                   ct.balance_after::float AS balance_after, ct.note
            FROM credit_transactions ct
            LEFT JOIN students s ON s.id = ct.student_id
            LEFT JOIN credit_accounts ca ON ca.id = ct.account_id
            LEFT JOIN courses c ON c.id = ca.course_id
            WHERE ct.tenant_id = %s
            ORDER BY ct.occurred_at DESC
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "credit-ledger", len(rows))
    header = ["Occurred At", "Student", "Course", "Type", "Amount", "Balance After", "Note"]
    data = ([r["occurred_at"], r["student"], r["course"], r["transaction_type"],
             r["amount"], r["balance_after"], r["note"]] for r in rows)
    return _csv_response(f"{tenant.slug}-credit-ledger.csv", header, data)


@api_v1.route("/export/revenue.csv", methods=["GET"])
@permission_required("data:export")
def export_revenue_csv():
    """Download monthly net revenue and activity totals as CSV."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "data_export"):
            return _error("Data export is not enabled for this studio plan.", 403)
        rows = fetch_all(
            conn,
            """
            SELECT to_char(date_trunc('month', occurred_at), 'YYYY-MM') AS period,
                   round(COALESCE(sum(fee_aud_cents), 0) / 100.0, 2) AS net_revenue_aud,
                   count(*) FILTER (WHERE transaction_type = 'purchase') AS purchases,
                   count(*) FILTER (WHERE transaction_type = 'consume') AS checkins
            FROM credit_transactions
            WHERE tenant_id = %s
            GROUP BY date_trunc('month', occurred_at)
            ORDER BY date_trunc('month', occurred_at) DESC
            """,
            (tenant.tenant_id,),
        )
        _export_audit(conn, tenant, "revenue", len(rows))
    header = ["Period", "Net Revenue (AUD)", "Purchases", "Check-ins"]
    data = ([r["period"], r["net_revenue_aud"], r["purchases"], r["checkins"]] for r in rows)
    return _csv_response(f"{tenant.slug}-revenue.csv", header, data)


@api_v1.route("/attendance/<attendance_id>/void", methods=["POST"])
@permission_required("attendance:write")
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
@permission_required("portfolio:write")

def create_portfolio_item():
    """Create a portfolio item linked to a media asset and student."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        payload = _json_payload()

        student_id = _clean_text(payload, "studentId")
        media_asset_id = _clean_text(payload, "mediaAssetId")
        title = _clean_text(payload, "title", "")
        description = _clean_text(payload, "description", "")
        try:
            visibility = _validate_portfolio_visibility(_clean_text(payload, "visibility", "private"))
        except ValueError as exc:
            return _error(str(exc))
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
        if visibility == "shared" and not _active_publication_consent(
            conn, tenant_id=tenant.tenant_id, student_id=student_id
        ):
            return _error(
                "An active student publication consent record is required before publishing.",
                400,
            )

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
                artwork_date, visibility, public_consent_at,
                public_consent_by_user_id, public_consent_note
            ) VALUES (%s, %s, %s, %s, %s, %s, %s,
                      CASE WHEN %s = 'shared' THEN now() ELSE NULL END,
                      CASE WHEN %s = 'shared' THEN %s ELSE NULL END,
                      CASE WHEN %s = 'shared' THEN 'Confirmed before public publishing' ELSE '' END)
            RETURNING id
            """,
            (
                tenant.tenant_id, student_id, media_asset_id, title, description,
                artwork_date_val, visibility, visibility, visibility,
                getattr(g.actor, "user_id", None), visibility,
            ),
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
@permission_required("portfolio:write")

def update_portfolio_item(portfolio_item_id: str):
    """Update a portfolio item's metadata for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        payload = _json_payload()

        title = _clean_text(payload, "title")
        description = _clean_text(payload, "description")
        try:
            visibility = _validate_portfolio_visibility(_clean_text(payload, "visibility")) if "visibility" in payload else ""
        except ValueError as exc:
            return _error(str(exc))
        if visibility == "shared" and not _plan_feature_enabled(conn, tenant.tenant_id, "portfolio"):
            return _error("Portfolio is not enabled for this studio plan.", 403)
        artwork_date_str = _clean_text(payload, "artworkDate")

        try:
            from datetime import date as _date
            artwork_date_val = None
            if artwork_date_str:
                artwork_date_val = _date.fromisoformat(artwork_date_str)
        except (ValueError, TypeError):
            return _error("artwork_date must be ISO-8601 date (YYYY-MM-DD).")

        existing_item = fetch_one(
            conn,
            "SELECT student_id FROM portfolio_items WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, portfolio_item_id),
        )
        if not existing_item:
            return _error("Portfolio item was not found.", 404)
        if visibility == "shared" and not _active_publication_consent(
            conn,
            tenant_id=tenant.tenant_id,
            student_id=str(existing_item["student_id"]),
        ):
            return _error(
                "An active student publication consent record is required before publishing.",
                400,
            )

        cur = conn.cursor()
        cur.execute(
            """
            UPDATE portfolio_items
            SET title = COALESCE(NULLIF(%s, ''), title),
                description = COALESCE(NULLIF(%s, ''), description),
                visibility = COALESCE(NULLIF(%s, ''), visibility),
                public_consent_at = CASE WHEN %s = 'shared' THEN now() ELSE public_consent_at END,
                public_consent_by_user_id = CASE WHEN %s = 'shared' THEN %s ELSE public_consent_by_user_id END,
                public_consent_note = CASE WHEN %s = 'shared' THEN 'Confirmed before public publishing' ELSE public_consent_note END,
                artwork_date = COALESCE(%s, artwork_date),
                updated_at = now()
            WHERE tenant_id = %s AND id = %s
            RETURNING id
            """,
            (
                title, description, visibility, visibility, visibility,
                getattr(g.actor, "user_id", None), visibility, artwork_date_val,
                tenant.tenant_id, portfolio_item_id,
            ),
        )
        if not cur.fetchone():
            return _error("Portfolio item was not found.", 404)

    return jsonify({"ok": True})


@api_v1.route("/portfolio/<portfolio_item_id>", methods=["DELETE"])
@permission_required("portfolio:write")

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
        or password != os.environ.get(
            "STUDIOSAAS_ADMIN_PASSWORD", "StudioSaaS@LetsPaint2026!"
        )
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
    _start_session_policy(_flask_session, payload)

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
                    (m.tenant_id = %s AND m.role IN ('owner', 'manager', 'teacher', 'front_desk', 'staff', 'super_admin'))
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
    _start_session_policy(_flask_session, payload)

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

    from flask import session as _fs
    return jsonify({
        "ok": True,
        "userId": user["id"],
        "email": user["email"],
        "name": user["full_name"],
        "user": dict(user),
        "memberships": memberships,
        "support": _fs.get("support"),
    })




# ──────────────────────────────────────────────
# P2: Studio Admin ↔ Legacy CMS sync endpoints
# ──────────────────────────────────────────────

import os as _os
import uuid as _uuid

UPLOAD_DIR = _os.path.join(_os.path.dirname(__file__), "..", "static", "uploads")
_os.makedirs(UPLOAD_DIR, exist_ok=True)


@api_v1.route("/tenant/settings", methods=["PATCH"])
@tenant_owner_required

def update_tenant_settings():
    """Compatibility alias for old clients; writes through the canonical tenant route."""

    return update_tenant()


@api_v1.route("/tenant/logo", methods=["POST"])
@tenant_owner_required

def upload_tenant_logo():
    """Upload a logo asset without publishing it to the tenant brand.

    The returned URL is placed into the Studio Admin editor. Save Draft or
    Publish remains a separate explicit action, matching every other field.
    """

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

        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="brand.logo_asset_uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={"logo_url": logo_url, "media_asset_id": str(media["id"])},
        )

    return jsonify({"ok": True, "url": logo_url})


@api_v1.route("/tenant/website-media", methods=["POST"])
@tenant_owner_required
def upload_tenant_website_media():
    """Upload a safe public hero or principal image without publishing it."""

    target = str(request.form.get("target") or "").strip()
    if target not in {"hero", "principal"}:
        return _error("Website media target must be hero or principal.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        try:
            media = _store_media_asset(
                conn,
                tenant_id=tenant.tenant_id,
                file_storage=f,
                kind="website_image",
            )
        except MediaUploadError as exc:
            return _media_error(exc)
        media_url = f"/v1/public/{tenant.slug}/media/{media['id']}"
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="brand.website_media_uploaded",
            resource_type="media_asset",
            resource_id=media["id"],
            metadata={"target": target, "media_url": media_url},
        )
    return jsonify({"ok": True, "target": target, "url": media_url}), 201


@api_v1.route("/students/<student_id>", methods=["PATCH"])
@permission_required("students:write")

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
        if "enrollmentDate" in payload or "enrolledOn" in payload:
            enrolled_on_str = _clean_text(
                payload, "enrollmentDate", _clean_text(payload, "enrolledOn")
            )
            try:
                enrolled_on_val = _date.fromisoformat(enrolled_on_str) if enrolled_on_str else None
            except (ValueError, TypeError):
                return _error("enrollmentDate must be an ISO-8601 date (YYYY-MM-DD).")
            if enrolled_on_val and enrolled_on_val > _date.today():
                return _error("enrollmentDate cannot be in the future.")
            updates["enrolled_on"] = enrolled_on_val

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
            _audit_request(
                conn,
                tenant_id=tenant.tenant_id,
                action="student.updated",
                resource_type="student",
                resource_id=student_id,
                metadata={"fields": sorted(updates.keys())},
            )

    return jsonify({"ok": True})
