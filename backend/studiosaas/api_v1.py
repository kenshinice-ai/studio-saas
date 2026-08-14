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
import shutil
import sys
import threading
import time
import hashlib
import uuid as _uuid
from urllib.parse import quote
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
from pathlib import Path, PurePath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import csv as _csv
import io as _io

from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
from werkzeug.utils import secure_filename

from .auth import (
    PermissionDeniedError,
    auth_required,
    hash_password as _auth_hash_password,
    permission_required,
    require_permission,
    super_admin_required,
    tenant_admin_required,
    tenant_owner_required,
    verify_password as _auth_verify_password,
)
from .config import is_standalone, load_config, show_producer_credit, studiosaas_mode
from .calendar_export import (
    CalendarDocument,
    build_roster_document,
    build_schedule_document,
)
from .db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from .errors import api_error
from .lifecycle import (
    canonical_subscription_status,
    validate_subscription_dates,
    validate_registration_transition,
    validate_tenant_subscription_pair,
    validate_tenant_transition,
)
from .models import Role
from .services import billing as _billing
from .services import calendar_subscriptions as _calendar_subs
from .services import entitlements as _entitlements
from .services import notification_channels as _channels
from .services import payments as _payments
from .services import progress_reports as _progress
from .services import scheduling as _scheduling
from .services import reports as _reports
from .services import teaching_pay as _teaching_pay
from .services import xero as _xero
from . import palette
from . import video_embed
from .presets import (
    FREE_ACCENT_STYLE_ID,
    INDUSTRY_PRESETS,
    INDUSTRY_SECTION_COPY,
    VISUAL_STYLE_PRESETS,
    public_industry_presets,
    public_visual_style_presets,
    accent_hue_of_colour,
    resolve_style_id,
    style_theme,
)
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
from .services import cms_notifications as _cms_notifications
from .services import notifications as _notifications
from .services.subscription_settlement import (
    ACTIONABLE as SETTLEMENT_ACTIONABLE,
    SETTLEMENT_QUERY,
    settlement_report,
)
from .services.public_site import public_plan_rows
from .services.student_access import (
    access_lock_seconds_remaining as _student_access_lock_seconds,
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
from .tenant_context import (
    TenantGoneError,
    TenantResolutionError,
    canonical_slug_for,
    forget_retired_addresses,
    resolve_tenant,
    slug_from_request,
)
from .workspaces import (
    WorkspaceError,
    copy_tenant_workspace,
    discard_tenant_workspace,
    ensure_tenant_workspace,
    validate_tenant_slug,
)

api_v1 = Blueprint("studiosaas_api_v1", __name__)

# ── PWE Studio Edition (STUDIOSAAS_MODE=standalone): platform plane closed ────
# The platform control plane (/v1/admin/*) and plan mutations (/v1/plans
# writes) do not exist in the standalone edition. Paths are matched on
# request.path because the blueprint is mounted both at /v1 and at
# /s/<slug>/v1. GET /v1/plans stays reachable (a harmless read the Studio
# Admin UI uses to display the current plan).
_STANDALONE_CLOSED_PATH_RE = re.compile(r"^(?:/s/[^/]+)?/v1/admin(?:/|$)")
_STANDALONE_PLANS_PATH_RE = re.compile(r"^(?:/s/[^/]+)?/v1/plans(?:/|$)")


@api_v1.before_request
def _standalone_platform_plane_gate():
    """Return 404 for platform-plane routes when running standalone."""

    if not is_standalone():
        return None
    path = request.path
    if _STANDALONE_CLOSED_PATH_RE.match(path):
        return jsonify({"error": "not_found"}), 404
    if _STANDALONE_PLANS_PATH_RE.match(path) and request.method not in ("GET", "HEAD", "OPTIONS"):
        return jsonify({"error": "not_found"}), 404
    return None


# Simple in-memory rate limiter for public endpoints (per-IP, per-minute).
# Counters reset on process restart — acceptable for the local pilot; a
# shared store (Redis) replaces this at the production stage (P3-04).
# Access is serialised by _public_rate_limit_lock (waitress serves requests
# from a thread pool), and the store is pruned lazily — every
# _RATE_LIMIT_PRUNE_EVERY recorded checks, keys whose newest timestamp has
# left the window are dropped — so it cannot grow without bound.
_public_rate_limit: dict[str, list[float]] = {}
_public_rate_limit_lock = threading.Lock()
_RATE_LIMIT_MAX_WINDOW_SECONDS = 60  # the longest window any caller uses
_RATE_LIMIT_PRUNE_EVERY = 256
_rate_limit_calls_since_prune = 0

# The version of the privacy notice the public pages render. It is served to
# the portal and the register page through /brand and stored with each consent
# record, so the version a visitor agreed to always matches the text they saw.
# Bump this whenever the privacy copy in tenant-template/index.html changes.
PRIVACY_NOTICE_VERSION = "2026-07-12"
PUBLICATION_NOTICE_VERSION = "2026-07-18"


def _prune_rate_limit_store(now: float) -> None:
    """Lazily drop keys whose timestamps all expired. Caller must hold the lock."""

    global _rate_limit_calls_since_prune
    _rate_limit_calls_since_prune += 1
    if _rate_limit_calls_since_prune < _RATE_LIMIT_PRUNE_EVERY:
        return
    _rate_limit_calls_since_prune = 0
    stale = [
        key
        for key, stamps in _public_rate_limit.items()
        if not stamps or now - stamps[-1] >= _RATE_LIMIT_MAX_WINDOW_SECONDS
    ]
    for key in stale:
        del _public_rate_limit[key]


def _rate_limited(key: str, limit: int, *, window_seconds: int = 60) -> bool:
    """Apply a bounded in-memory sliding-window limit for one public action."""

    now = time.time()
    with _public_rate_limit_lock:
        attempts = [
            stamp for stamp in _public_rate_limit.get(key, []) if now - stamp < window_seconds
        ]
        limited = len(attempts) >= limit
        if not limited:
            attempts.append(now)
        if attempts:
            _public_rate_limit[key] = attempts
        else:
            _public_rate_limit.pop(key, None)
        _prune_rate_limit_store(now)
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
    with _public_rate_limit_lock:
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
        _prune_rate_limit_store(now)
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
    """Return a clear setup error when PostgreSQL is not ready.

    In pilot/production the driver detail (host, port, connection error) is
    internal topology and must not be echoed to clients; a fixed message is
    returned instead. Local development keeps the actionable detail, so the
    canonical body is built directly here rather than through api_error()
    (which blanks every >=500 message outside debug mode).
    """

    if os.environ.get("STUDIOSAAS_ENV", "local").strip().lower() in {"pilot", "production"}:
        message = "Database unavailable. Please try again later."
    else:
        message = str(exc) or "Database unavailable."
    return jsonify({"error": "database_unavailable", "message": message}), 503


@api_v1.errorhandler(TenantResolutionError)
def handle_tenant_error(exc: TenantResolutionError):
    """Return a clear tenant error instead of silently picking a default."""

    return api_error(str(exc), 400, error="tenant_resolution_failed")


@api_v1.errorhandler(TenantGoneError)
def handle_tenant_gone(exc: TenantGoneError):
    """An address that existed and no longer belongs to anyone.

    410 rather than 404 so a crawler drops it, and so nobody wonders whether
    it is a typo. Addresses are never reissued, so this answer is permanent.
    """

    return api_error(str(exc), 410, error="tenant_address_retired")


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
        # Batch 5: the form's own heading is bilingual like the copy around it.
        # It is the fallback the register page uses when a studio has not
        # overridden localized_copy.registration_title.
        "title": {"zh": preset["registration_title_zh"], "en": preset["registration_title"]},
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
    title = _localized_pair(value, "title", limit=80)
    if not (title["zh"] or title["en"]):
        title = dict(default["title"])
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


def _normalize_localized_copy(
    value,
    category: str = "general",
    legacy: dict[str, str] | None = None,
) -> dict:
    """Validate the explicit Chinese/English public-copy bundle.

    ``legacy`` carries the single-language value a tenant saved before a key
    joined this bundle (the ``welcome_message`` column, ``settings.slogan``,
    ``principal_profile.bio``). It seeds both languages, so an existing studio's
    own words survive instead of being replaced by an industry default.
    """

    data = _coerce_json_object(value, field_name="localized_copy")
    legacy_values = legacy or {}
    preset = _preset_for(category)
    # B1: section headings default per industry rather than shipping one set to
    # every tenant. A studio can still override any of them.
    sections = INDUSTRY_SECTION_COPY.get(category, INDUSTRY_SECTION_COPY["general"])
    defaults = {
        "hero_title": preset["hero"]["title"],
        "hero_subtitle": preset["hero"]["subtitle"],
        "primary_cta": {"zh": "预约体验", "en": "Book a Trial"},
        "secondary_cta": {"zh": "查看课程", "en": "Explore Programs"},
        "registration_title": {"zh": preset["registration_title_zh"], "en": preset["registration_title"]},
        "registration_intro": {"zh": preset["register_intro_zh"], "en": preset["copy_pack"]["register_intro"]},
        # Batch 5, class B: studio-identity copy. These lived as single-language
        # strings on the tenant row (`slogan`, `welcome_message`) or inside
        # website_profile / principal_profile, which is why a Chinese portal
        # showed 14 English fragments. They join the bundle that was already
        # bilingual, already normalised on read, and already preferred by the
        # public template — rather than growing a second mechanism beside it.
        #
        # The flat columns and JSON keys stay exactly as they were, so the CMS,
        # Super Admin and any tenant saved before this keep reading what they
        # read before; the pair here wins when it has a value.
        "slogan": {"zh": preset["slogan_zh"], "en": preset["slogan"]},
        "category_label": {"zh": preset["label_zh"], "en": preset["label"]},
        # No default text: a generated welcome/bio is the P0-2 mistake. Blank
        # means the portal hides the band instead of publishing filler.
        "welcome_message": {"zh": "", "en": ""},
        "principal_title": {"zh": "创办人 / 主理人", "en": "Founder & Principal"},
        "principal_bio": {"zh": "", "en": ""},
        "principal_quote": {"zh": "", "en": ""},
        # %WORK% / %WORKS% rather than 「作品」 / "Works": the gallery label is
        # shared by a piano, dance and games studio (Glossary rule 2).
        "courses_label": {"zh": "课程与班次", "en": "Courses & Classes"},
        "gallery_label": {"zh": "学员%WORK%", "en": "Student %WORKS%"},
        "faq_label": {"zh": "常见问题", "en": "Questions & Answers"},
        "contact_label": {"zh": "联系我们", "en": "Contact"},
        **sections,
    }
    limits = {
        "hero_title": 120,
        "hero_subtitle": 240,
        "primary_cta": 80,
        "secondary_cta": 80,
        "registration_title": 120,
        "registration_intro": 300,
        "courses_title": 120,
        "courses_lead": 240,
        "gallery_title": 120,
        "gallery_lead": 240,
        "faq_title": 120,
        "slogan": 180,
        "category_label": 80,
        "welcome_message": 240,
        "principal_title": 100,
        "principal_bio": 800,
        "principal_quote": 180,
        "courses_label": 80,
        "gallery_label": 80,
        "faq_label": 80,
        "contact_label": 80,
    }
    normalized: dict[str, dict[str, str]] = {}
    for key, limit in limits.items():
        camel = "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])])
        pair = data.get(key) or data.get(camel)
        if not pair:
            inherited = str(legacy_values.get(key) or "").strip()
            pair = {"zh": inherited, "en": inherited} if inherited else defaults[key]
        if isinstance(pair, str):
            pair = {"zh": pair, "en": pair}
        if not isinstance(pair, dict):
            raise ValueError(f"localized_copy.{key} must contain zh/en text.")
        zh = str(pair.get("zh") or "").strip()[:limit]
        en = str(pair.get("en") or "").strip()[:limit]
        # P1-7 applies to every key here: one filled language is used for both
        # rather than letting the other fall back to a template default.
        normalized[key] = {
            "zh": zh or en or str(defaults[key]["zh"]).strip()[:limit],
            "en": en or zh or str(defaults[key]["en"]).strip()[:limit],
        }
    return normalized


def _legacy_identity_copy(source: dict) -> dict[str, str]:
    """Collect the pre-bilingual values for the class-B studio-identity keys.

    A studio that wrote its slogan, welcome band, principal bio or section
    labels before those became ``{zh, en}`` still has one string. Reading it
    here means the portal shows the studio's own words in both languages rather
    than reverting to the industry default the day this ships.
    """

    website = source.get("website_profile") if isinstance(source.get("website_profile"), dict) else {}
    principal = source.get("principal_profile") if isinstance(source.get("principal_profile"), dict) else {}
    website_default = _default_website_profile()
    principal_default = _default_principal_profile()
    category = source.get("category") or "general"
    preset = _preset_for(category)

    def single(value, *, ignore: str = "") -> str:
        """Return a genuinely tenant-authored string, or "" to use the default.

        The old defaults were English-only literals that got written into every
        tenant's settings on save, so inheriting them verbatim would put
        "Courses & Classes" in the Chinese slot. A value that still equals its
        old default is not the studio's writing and is dropped.
        """

        if not isinstance(value, str):
            return ""
        text = value.strip()
        return "" if text == ignore.strip() else text

    return {
        "slogan": single(source.get("slogan"), ignore=preset["slogan"]),
        "category_label": single(source.get("category_label"), ignore=preset["label"]),
        "welcome_message": single(source.get("welcome_message")),
        "principal_title": single(principal.get("title"), ignore=principal_default["title"]),
        "principal_bio": single(principal.get("bio")),
        "principal_quote": single(principal.get("quote")),
        "courses_label": single(website.get("courses_label"), ignore=website_default["courses_label"]),
        "gallery_label": single(website.get("gallery_label"), ignore=website_default["gallery_label"]),
        "faq_label": single(website.get("faq_label"), ignore=website_default["faq_label"]),
        "contact_label": single(website.get("contact_label"), ignore=website_default["contact_label"]),
    }


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
        # ``auto`` preserves old tenants without guessing at save time. The
        # public-surface resolver chooses the first target that is actually
        # ready; an explicitly selected target never silently falls through.
        "secondary_cta_target": "auto",
        "secondary_cta_href": "",
        "show_student_login": True,
        "background_style": "soft",
        # The hero image's outline. Separate from background_style, which says
        # WHAT is in the hero; this says what shape it is cut to. Organic is
        # the default because it is the one mark that makes the page read as a
        # studio rather than a form, but it is a strong opinion and a studio
        # showing architectural or product work will want the rectangle.
        "hero_shape": "organic",
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
    hero_shape = _first_text(
        data, "hero_shape", "heroShape", default=default["hero_shape"], limit=16,
    ).lower()
    if hero_shape not in {"organic", "oval", "square"}:
        raise ValueError("Hero shape must be one of: organic, oval, square.")
    hero_image_url = _first_text(data, "hero_image_url", "heroImageUrl", limit=500)
    if hero_image_url:
        _validate_logo_url(hero_image_url)
    secondary_cta_target = _first_text(
        data,
        "secondary_cta_target",
        "secondaryCtaTarget",
        default=default["secondary_cta_target"],
        limit=20,
    ).lower()
    allowed_cta_targets = {
        "auto", "courses", "showcase", "timetable", "register", "external", "hidden",
    }
    if secondary_cta_target not in allowed_cta_targets:
        raise ValueError(
            "Secondary CTA target must be one of: auto, courses, showcase, "
            "timetable, register, external, hidden."
        )
    secondary_cta_href = _first_text(
        data, "secondary_cta_href", "secondaryCtaHref", limit=500,
    )
    if secondary_cta_target == "external":
        if not re.match(r"^https://\S+$", secondary_cta_href, re.IGNORECASE):
            raise ValueError("Secondary CTA external URL must start with https://.")
    return {
        "eyebrow": _first_text(data, "eyebrow", default=default["eyebrow"], limit=80),
        "title": _first_text(data, "title", default=default["title"], limit=100),
        "subtitle": _first_text(data, "subtitle", default=default["subtitle"], limit=240),
        "primary_cta_label": _first_text(data, "primary_cta_label", "primaryCtaLabel", default=default["primary_cta_label"], limit=40),
        "secondary_cta_label": _first_text(data, "secondary_cta_label", "secondaryCtaLabel", default=default["secondary_cta_label"], limit=40),
        "secondary_cta_target": secondary_cta_target,
        "secondary_cta_href": secondary_cta_href,
        "show_student_login": _bool_from_json(data, "show_student_login", "showStudentLogin", default=True),
        "background_style": background_style,
        "hero_shape": hero_shape,
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
        # Reclaimed from the hand-forked lets-paint-studio portal so every
        # tenant can have them without leaving the template behind.
        "seo_title": "",
        "seo_description": "",
        "show_about": False,
        "about_images": [],
        "about_image_alts": [],
        "about_eyebrow": {"zh": "", "en": ""},
        "about_title": {"zh": "", "en": ""},
        "about_body": {"zh": "", "en": ""},
        "about_items": [],
        # Off and empty. A studio publishes a portfolio by curating one, not
        # by existing — an empty board says less than no board.
        "show_showcase": False,
        "showcase_label": {"zh": "", "en": ""},
        "showcase_title": {"zh": "", "en": ""},
        "showcase_lead": {"zh": "", "en": ""},
        "showcase_categories": [],
        "showcase_items": [],
        # The public timetable lives on its own page, not in this scroll, so
        # this switch controls a LINK as much as a section. Off until a studio
        # has marked at least one class public — a timetable page reached from
        # the portal and showing nothing is worse than no link at all.
        "show_timetable": False,
        "timetable_weeks": TIMETABLE_DEFAULT_WEEKS,
        "timetable_fields": dict(TIMETABLE_FIELD_DEFAULTS),
        "timetable_label": {"zh": "", "en": ""},
        "timetable_lead": {"zh": "", "en": ""},
        "show_timetable_booking": False,
    }


def _localized_pair(data: dict, key: str, *, limit: int) -> dict:
    """Read a {"zh", "en"} pair, accepting a bare string for either language."""

    raw = data.get(key)
    if isinstance(raw, dict):
        zh = str(raw.get("zh") or "").strip()[:limit]
        en = str(raw.get("en") or "").strip()[:limit]
    else:
        zh = en = str(raw or "").strip()[:limit]
    if not zh and not en:
        return {"zh": "", "en": ""}
    return {"zh": zh or en, "en": en or zh}


# How many works a record may HOLD. Not how many the portal publishes — that
# is `plans.showcase_limit`, applied when the board is read.
#
# The distinction is the whole design and it is worth stating once, loudly:
#
#   A tenant that moves from growth (150) to starter (15) KEEPS ALL 150.
#
# v8.6.0 truncated here, at `[:SHOWCASE_ITEM_LIMIT]`. Had the cap become a
# per-plan number while this line stood, a studio that downgraded would have
# lost 135 works the next time it saved ANY setting — changing a phone number
# would have destroyed a portfolio, silently. Exactly the shape of the v8.5.4
# outage: a harmless-looking truncation operating on somebody else's data.
#
# So this ceiling is deliberately plan-INDEPENDENT and generous. It exists to
# bound a hostile request, nothing else.
SHOWCASE_STORAGE_CEILING = 500

# The fallback when a tenant's plan row cannot be read. Conservative on
# purpose, and never an exception — a missing plan must cost a studio some of
# its board for one request, never the whole page.
SHOWCASE_FALLBACK_LIMIT = 15

# Eight drawers is already more structure than a portfolio of this size wants;
# past that, filtering costs the visitor more than it saves them.
SHOWCASE_CATEGORY_LIMIT = 8

# How many works one page of the public board carries. The first screen of a
# portfolio is an argument, not an archive.
SHOWCASE_PAGE_SIZE = 12

# The home page is a doorway to the full portfolio, not a second archive.  It
# asks the same endpoint for a deliberately smaller, server-controlled preview
# so a tenant cannot accidentally turn the landing page into a 500-item feed.
SHOWCASE_PREVIEW_SIZE = 6

# ``featured_rank`` is stored inside each tenant's JSON-owned showcase record.
# It is deliberately bounded by the storage ceiling rather than the current
# plan: a downgrade hides excess works but must not erase their editorial
# order, so an upgrade can reveal the same selection again.
SHOWCASE_FEATURED_RANK_MAX = SHOWCASE_STORAGE_CEILING

# A work is retained independently of its publication state.  The state is
# deliberately small and explicit so a plan downgrade can hide a work without
# deleting it, and an upgrade can make it visible again without a restore.
SHOWCASE_PUBLICATION_STATES = frozenset({"active", "draft", "archived"})


def _normalize_showcase_publication_state(value) -> str:
    """Return a safe publication state for a stored showcase item.

    Older records predate publication states, so a missing value is treated as
    ``active`` for backwards compatibility.  An explicitly unknown value is
    kept private as ``draft`` rather than accidentally exposing it publicly.
    """

    raw = str(value or "").strip().lower()
    if not raw:
        return "active"
    return raw if raw in SHOWCASE_PUBLICATION_STATES else "draft"


def _normalize_showcase_featured_rank(value) -> int | None:
    """Return a safe one-based featured rank, or ``None`` when unranked.

    Ranks are an editorial hint, not a public entitlement.  Invalid values are
    ignored rather than allowed to affect the public ordering, and the write
    path compacts valid ranks so old records with gaps or duplicates remain
    deterministic without losing any work.
    """

    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, float) and not value.is_integer():
        return None
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= rank <= SHOWCASE_FEATURED_RANK_MAX:
        return rank
    return None


def _compact_showcase_featured_ranks(items: list[dict]) -> list[dict]:
    """Compact valid ranks in place while preserving the stored item order.

    The rank is tenant-global.  A category filter never creates a second rank
    space, which keeps the home preview and every category URL on one ordering
    contract.  Ties are resolved by the existing list order, then assigned
    contiguous values so a later admin save cannot create duplicate slots.
    """

    ranked = sorted(
        (
            (index, item)
            for index, item in enumerate(items)
            if item.get("featured_rank") is not None
        ),
        key=lambda pair: (pair[1]["featured_rank"], pair[0]),
    )
    ranked_ids = {id(item) for _, item in ranked}
    for position, (_index, item) in enumerate(ranked, start=1):
        item["featured_rank"] = position
    for item in items:
        if id(item) not in ranked_ids:
            item["featured_rank"] = None
    return items


def _ordered_showcase_items(items: list[dict]) -> list[dict]:
    """Return active works with ranked items first and stable legacy order."""

    return [
        item
        for _index, item in sorted(
            enumerate(items),
            key=lambda pair: (
                pair[1].get("featured_rank") is None,
                pair[1].get("featured_rank") or SHOWCASE_FEATURED_RANK_MAX + 1,
                pair[0],
            ),
        )
    ]

_SHOWCASE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,24}$")

# ── the public timetable ────────────────────────────────────────────────────
#
# How far ahead the page projects. Two weeks is enough for a parent to plan and
# short enough that the page stays a timetable rather than a year planner. It
# is also the ONLY boundary on how far ahead a class may be booked: a date the
# visitor cannot see is a date they cannot ask for, and a second, separate
# "booking horizon" setting would drift out of step with this one — and the
# person who discovers the drift is always the parent.
TIMETABLE_DEFAULT_WEEKS = 2
TIMETABLE_MAX_WEEKS = 4

# Which fields the page prints, as ONE structured object rather than six loose
# booleans. Three rules make it free without becoming unmanageable:
#
#   1. A missing key takes the default below, so adding a field later needs no
#      migration and no tenant is left with a half-configured record.
#   2. Rendering is a loop over this dict, not six branches. That is what keeps
#      64 combinations a single layout's 64 subsets instead of 64 layouts.
#   3. The switch is a CEILING and the content is a FLOOR — intersect them. A
#      field switched on with nothing in it prints nothing, never an empty
#      "Room:" label.
#
# `price` defaults off: a timetable is a schedule, and a studio that wants to
# talk about money on a public page has a courses section built for it.
TIMETABLE_FIELD_DEFAULTS = {
    "teacher": True,
    "room": True,
    "age_range": True,
    "duration": False,
    "capacity": True,
    "price": False,
}


def showcase_limit_for(conn, tenant_id: str) -> int:
    """How many works this tenant's plan publishes.

    Never raises and never returns 0. A tenant whose plan row is missing — a
    seed fixture, a plan renamed mid-flight, a join that came back empty —
    gets the entry-plan number rather than an exception, because this runs on
    a public page load and the alternative is a blank section.

    That rule is not a general preference; it is what `_stored_visual_theme`
    learned in v8.5.4, applied before the same thing can happen twice.
    """

    try:
        row = fetch_one(
            conn,
            "SELECT p.showcase_limit FROM tenants t "
            "LEFT JOIN plans p ON p.code = t.plan_code WHERE t.id = %s",
            (tenant_id,),
        )
    except Exception:
        current_app.logger.warning("showcase limit lookup failed", exc_info=True)
        return SHOWCASE_FALLBACK_LIMIT
    limit = (row or {}).get("showcase_limit")
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        return SHOWCASE_FALLBACK_LIMIT
    return limit if limit > 0 else SHOWCASE_FALLBACK_LIMIT


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
            "show_about",
            "show_showcase",
            "show_timetable",
            "show_timetable_booking",
        )
    }
    for key in ("courses_label", "gallery_label", "faq_label", "contact_label"):
        profile[key] = _first_text(data, key, "".join([key.split("_")[0], "Label"]), default=default[key], limit=80)
    # Per-tenant SEO overrides. The flagship tenant had a hand-edited <title>
    # in its forked workspace; this is the same capability as a brand field, so
    # the fork no longer has to exist to get it.
    profile["seo_title"] = _first_text(data, "seo_title", "seoTitle", default="", limit=120)
    profile["seo_description"] = _first_text(data, "seo_description", "seoDescription", default="", limit=200)
    # Optional "about the space" section. Public pages use manual image
    # selection so visitors are never forced through an autoplay carousel.
    images = data.get("about_images", data.get("aboutImages"))
    profile["about_images"] = [
        url for url in (str(item or "").strip()[:400] for item in (images if isinstance(images, list) else []))
        if url
    ][:6]
    raw_alts = data.get("about_image_alts", data.get("aboutImageAlts"))
    profile["about_image_alts"] = []
    for item in (raw_alts if isinstance(raw_alts, list) else [])[:len(profile["about_images"])]:
        if isinstance(item, dict):
            profile["about_image_alts"].append(_localized_pair({"alt": item}, "alt", limit=180))
            continue
        text = str(item or "").strip()[:180]
        profile["about_image_alts"].append({"zh": text, "en": text})
    while len(profile["about_image_alts"]) < len(profile["about_images"]):
        profile["about_image_alts"].append({"zh": "", "en": ""})
    for key in ("about_eyebrow", "about_title", "about_body"):
        camel = "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])])
        source = data if key in data else {key: data.get(camel)}
        profile[key] = _localized_pair(source, key, limit=600)
    items = data.get("about_items", data.get("aboutItems"))
    normalized_items = []
    for item in (items if isinstance(items, list) else [])[:6]:
        if not isinstance(item, dict):
            continue
        title = _localized_pair(item, "title", limit=80)
        body = _localized_pair(item, "body", limit=300)
        if title["zh"] or title["en"]:
            normalized_items.append({"title": title, "body": body})
    profile["about_items"] = normalized_items

    # The studio's OWN work — see docs/design/Showcase_Section.md. Separate
    # from the student gallery on purpose: different author, different consent
    # model, different question answered.
    for key in ("showcase_label", "showcase_title", "showcase_lead"):
        camel = "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])])
        source = data if key in data else {key: data.get(camel)}
        profile[key] = _localized_pair(source, key, limit=300)
    # Categories are drawers, and a drawer never owns what is in it: deleting
    # one leaves its works uncategorised rather than deleting them.
    #
    # The id is generated here and never derived from the label, because a
    # derived id means renaming 「油画」 to 「油画 / Oil」 silently detaches every
    # work filed under it.
    raw_categories = data.get("showcase_categories", data.get("showcaseCategories"))
    categories, seen_ids = [], set()
    for entry in (raw_categories if isinstance(raw_categories, list) else [])[:SHOWCASE_CATEGORY_LIMIT]:
        if not isinstance(entry, dict):
            continue
        label = _localized_pair(entry, "label", limit=60)
        if not (label["zh"] or label["en"]):
            continue
        ident = str(entry.get("id") or entry.get("categoryId") or "").strip()[:24]
        if not _SHOWCASE_ID_RE.match(ident) or ident in seen_ids:
            ident = secrets.token_hex(4)
        seen_ids.add(ident)
        categories.append({"id": ident, "label": label})
    profile["showcase_categories"] = categories

    showcase = data.get("showcase_items", data.get("showcaseItems"))
    curated = []
    for item in (showcase if isinstance(showcase, list) else [])[:SHOWCASE_STORAGE_CEILING]:
        if not isinstance(item, dict):
            continue
        image = str(item.get("image_url") or item.get("imageUrl") or "").strip()[:400]
        # Two ways in, because the owner pastes a link and the stored record
        # already holds the parsed halves. Either way the ID is re-validated:
        # a record is not more trustworthy than a submission just because it
        # is older.
        provider, video_id = video_embed.parse_video_url(
            item.get("video_url") or item.get("videoUrl") or "")
        if not provider:
            stored_provider = str(item.get("video_provider") or item.get("videoProvider") or "")
            stored_id = str(item.get("video_id") or item.get("videoId") or "")
            if video_embed.embed_url(stored_provider, stored_id):
                provider, video_id = stored_provider, stored_id
        # A tile with neither a picture nor a video is an empty box, not a
        # work. Dropped rather than rendered.
        if not image and not provider:
            continue
        # An id that names no category becomes "uncategorised" rather than a
        # dangling reference — the drawer may be gone, the work is not.
        category_id = str(item.get("category_id") or item.get("categoryId") or "").strip()[:24]
        if category_id not in seen_ids:
            category_id = ""
        curated.append({
            "image_url": image,
            "category_id": category_id,
            # ``None`` is meaningful: the owner has not selected this work for
            # editorial priority, so it follows the legacy list order.
            "featured_rank": _normalize_showcase_featured_rank(
                item.get("featured_rank") or item.get("featuredRank")
            ),
            # Missing state means a legacy work, which remains public. Invalid
            # explicit values are private until an operator fixes them.
            "publication_state": _normalize_showcase_publication_state(
                item.get("publication_state") or item.get("publicationState")
            ),
            "title": _localized_pair(item, "title", limit=120),
            "caption": _localized_pair(item, "caption", limit=300),
            "video_provider": provider,
            "video_id": video_id,
            # Derived, and derived HERE rather than in the page. The portal
            # never assembles a frame URL, so there is one place that decides
            # what a video link becomes and one place to audit. Recomputed on
            # every read as well as every write, so it cannot go stale.
            "video_embed_url": video_embed.embed_url(provider, video_id),
        })
    profile["showcase_items"] = _compact_showcase_featured_ranks(curated)

    # ── the public timetable page ───────────────────────────────────────────
    for key in ("timetable_label", "timetable_lead"):
        camel = "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])])
        source = data if key in data else {key: data.get(camel)}
        profile[key] = _localized_pair(source, key, limit=300)
    try:
        weeks = int(data.get("timetable_weeks", data.get("timetableWeeks", TIMETABLE_DEFAULT_WEEKS)))
    except (TypeError, ValueError):
        weeks = TIMETABLE_DEFAULT_WEEKS
    profile["timetable_weeks"] = min(max(weeks, 1), TIMETABLE_MAX_WEEKS)
    # A missing key takes the default rather than False. "Not mentioned" and
    # "switched off" are different answers, and reading the first as the second
    # would blank a studio's timetable the day this object gains a field.
    raw_fields = data.get("timetable_fields", data.get("timetableFields"))
    raw_fields = raw_fields if isinstance(raw_fields, dict) else {}
    profile["timetable_fields"] = {
        key: _bool_from_json(
            raw_fields, key,
            "".join([key.split("_")[0], *(p.capitalize() for p in key.split("_")[1:])]),
            default=default)
        for key, default in TIMETABLE_FIELD_DEFAULTS.items()
    }
    return profile


def _default_principal_profile(studio_name: str = "") -> dict:
    """Return the empty principal/about section.

    `bio` and `quote` stay blank on purpose. They used to be generated filler
    ("Meet the principal behind X and the teaching philosophy that shapes every
    class."), which the portal then rendered to the public as though a real
    person had written it. The portal hides the whole section until a studio
    supplies a real bio, so an unfilled field costs nothing.
    """

    return {
        "show": True,
        "name": "",
        "title": "Founder & Principal",
        "bio": "",
        "quote": "",
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


# The messages staff copy out of the CMS and paste to families in WeChat.
# They were literals in cms-app.jsx that said the word "Studio" and ended with a
# 🎨 — so a piano parent received a message naming a studio that was not theirs,
# decorated with a paint palette. Studios edit them here; the CMS fills the
# placeholders.
MESSAGE_TEMPLATE_KEYS = ("checkin", "checkin_empty", "topup", "renewal", "birthday")
MESSAGE_TEMPLATE_PLACEHOLDERS = ("{student}", "{studio}", "{balance}", "{credits}", "{fee}", "{note}", "{venue}", "{work}")


def _default_message_templates() -> dict:
    """Return the default family-facing message templates (Chinese)."""

    return {
        "checkin": "{student} 今日已完成签到 ✓ 当前剩余 {balance} 课时。{studio} 感谢您的支持！",
        "checkin_empty": "{student} 今日已完成签到 ✓ 当前剩余 0 课时，已用完，欢迎联系老师续课～",
        "topup": "{student} 您好！已为您成功充值 {credits} 课时{fee}，当前账户共 {balance} 课时。感谢您对 {studio} 的信任！",
        "renewal": "{student} 家长您好！温馨提醒：您在 {studio} 的剩余课时为 {balance} 节{note}，为不影响后续上课安排，欢迎随时联系老师续课。",
        "birthday": "{student} 您好！{studio} 全体老师祝您生日快乐！愿您在新的一岁里灵感不断、收获满满～",
    }


def _normalize_message_templates(value) -> dict:
    """Validate the family-facing message templates."""

    data = _coerce_json_object(value, field_name="message_templates")
    default = _default_message_templates()
    return {
        key: (str(data.get(key) or "").strip()[:600] or default[key])
        for key in MESSAGE_TEMPLATE_KEYS
    }


def _default_faq_items(category: str) -> list[dict]:
    """Return default FAQ copy for public tenant pages.

    Questions and answers are {"zh": ..., "en": ...} pairs so the portal's
    language switch reaches the FAQ too. The %VENUE% / %WORK% tokens are
    replaced in the browser with the nouns this industry actually uses.
    """

    preset = _preset_for(category)
    label_en = preset["label"].lower()
    label_zh = preset["label_zh"]
    return [
        {
            "question": {"zh": "有体验课吗？", "en": "Is there a trial class?"},
            "answer": {
                "zh": "有的。通过报名表留下联系方式，%VENUE%会与您联系并安排合适的第一节课。",
                "en": "Yes. Leave your details on the registration form and the %VENUE% will be in touch to arrange a suitable first session.",
            },
        },
        {
            "question": {"zh": "课包与课时怎么算？", "en": "How do class packs work?"},
            "answer": {
                "zh": "课程以课包形式购买，每次上课按实际时长扣课时；余额与记录随时可在「学员专区」查询。",
                "en": "Classes are bought as packs and each session draws the credits it actually uses. Your balance and history are always visible in the student area.",
            },
        },
        {
            "question": {
                "zh": f"应该选择哪个{label_zh}水平？",
                "en": f"Which {label_en} level should we choose?",
            },
            "answer": {
                "zh": "在报名表里填写当前经验与目标即可，老师会推荐合适的班型。",
                "en": "Start with your current experience and goals in the registration form, and the teacher will recommend the right class.",
            },
        },
        {
            "question": {"zh": "家长能看到进度吗？", "en": "Can parents view progress?"},
            "answer": {
                "zh": "可以。开启「学员专区」后，用姓名、手机号与%VENUE%发放的访问码即可查看课时余额与%WORK%记录。",
                "en": "Yes. When the student area is enabled, the student's name, mobile and the access code issued by the %VENUE% show the credit balance and %WORK% records.",
            },
        },
    ]


def _localized_faq_text(item: dict, key: str, *, limit: int):
    """Return one FAQ field as a {"zh", "en"} pair.

    Accepts the legacy single-string shape and the localized object shape, so
    FAQs saved before the portal became bilingual keep working: a single string
    is used for both languages rather than falling back to template copy.
    """

    raw = item.get(key)
    if isinstance(raw, dict):
        zh = str(raw.get("zh") or "").strip()[:limit]
        en = str(raw.get("en") or "").strip()[:limit]
        if not zh and not en:
            return None
        return {"zh": zh or en, "en": en or zh}
    text = _first_text(item, key, limit=limit)
    if not text:
        return None
    return {"zh": text, "en": text}


def _normalize_faq_items(value, category: str) -> list[dict]:
    """Validate FAQ items shown on public tenant pages."""

    items = _coerce_json_list(value, field_name="faq_items")
    if not items:
        return _default_faq_items(category)
    normalized = []
    for item in items[:8]:
        if not isinstance(item, dict):
            raise ValueError("Each FAQ item must be an object.")
        question = _localized_faq_text(item, "question", limit=140)
        answer = _localized_faq_text(item, "answer", limit=500)
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
    """Return default public visual-theme options.

    The preset is returned whole. It used to have ``accent_color`` and
    ``secondary_accent_color`` replaced with the tenant's ``primary_color`` /
    ``secondary_color``, which is what made the CMS look like two products at
    once: each preset is solved as a set — across all 15 preset/modes the
    accent sits within 30 degrees of its own background, and 13 of them within
    6 — but the injected brand colour carried no such relationship. On
    ``lets-paint-showcase`` that turned a 3-degree pairing (clay accent on warm
    paper) into 160 degrees, near-complementary, while the other 19 tokens
    stayed warm.

    The substitution was also inconsistent with the path beside it:
    ``_normalize_visual_theme`` already returns ``style_theme(style_id)``
    untouched when a tenant has chosen a style, so only tenants *without* a
    stored theme were affected — exactly the ones that looked wrong.

    ``primary_color``/``secondary_color`` remain on the tenant record. They
    identify the studio in the platform console and are the intended input for
    deriving a full palette from the brand hue (the upgrade path recorded in
    the handoff); they are no longer spliced into a palette solved around a
    different hue. A studio whose brand is teal picks a teal-family preset,
    which is what the theme picker is for.
    """

    return dict(_preset_for(category)["theme"])


# Colour tokens a tenant may override. Splitting them by role keeps the
# validation honest: a scrim is not a hex value, and the derived states have a
# sensible fallback when an older record predates them.
_THEME_HEX_KEYS = (
    "background_color", "background_alt_color", "panel_color", "surface_hover_color",
    "text_color", "text_soft_color", "muted_text_color",
    "border_color", "border_strong_color",
    "accent_color", "accent_text_color", "accent_muted_text_color",
    "accent_hover_color", "accent_pressed_color",
    "accent_soft_color", "accent_on_soft_color", "accent_border_color",
    "secondary_accent_color",
    # Each role ships its loud form and its quiet form together. A tinted chip
    # with a label and a border is most of what a role is actually used for,
    # and shipping only the fill left every surface to invent its own tint.
    "success_color", "success_soft_color", "success_on_soft_color", "success_border_color",
    "warning_color", "warning_soft_color", "warning_on_soft_color", "warning_border_color",
    "danger_color", "danger_soft_color", "danger_on_soft_color", "danger_border_color",
    "info_color", "info_soft_color", "info_on_soft_color", "info_border_color",
    "focus_ring_color", "disabled_surface_color", "disabled_text_color",
)
_SCRIM_RE = re.compile(r"^rgba\(\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*\d{1,3}\s*,\s*(?:0|1|0?\.\d+)\s*\)$")


def _accent_hue(data: dict):
    """The studio's one colour knob, as a hue, or None to keep the default.

    Two ways in, because a studio thinks in colours and the stored record
    thinks in degrees: `accent_source` is a hex the owner picked (usually out
    of their logo) and only its HUE survives; `accent_hue` is the degrees a
    previously saved record already resolved to. Lightness and saturation are
    never taken from either — they are solved, which is what stops a studio
    from producing a page nobody can read. See Design_Constraints.md 1.4.
    """

    source = _first_text(data, "accent_source", "accentSource", limit=16)
    if source:
        _validate_hex_color("Accent source", source)
        return accent_hue_of_colour(source)
    raw = data.get("accent_hue", data.get("accentHue"))
    if raw in (None, ""):
        return None
    try:
        hue = float(raw)
    except (TypeError, ValueError):
        raise ValueError("Accent hue must be a number of degrees.") from None
    if hue != hue or hue in (float("inf"), float("-inf")):
        raise ValueError("Accent hue must be a number of degrees.")
    return hue % 360


def _normalize_visual_theme(
    value,
    primary_color: str = "",
    secondary_color: str = "",
    category: str = "general",
    strict: bool = True,
) -> dict:
    """Validate public colour and light style settings.

    `strict` is the difference between a WRITE and a READ, and it is not a
    convenience switch — see `_stored_visual_theme`. On a write an unusable
    value is the owner's to fix and must be reported. On a read the owner is
    not present, the value is already stored, and raising renders nothing.
    """

    data = _coerce_json_object(value, field_name="visual_theme")
    style_id = _first_text(data, "style_id", "styleId", limit=40).lower()
    if style_id:
        # Follows RETIRED_STYLE_ALIASES first: a record that says `studio`
        # asked for the free-accent palette, and answering it with the default
        # would silently repaint a studio that never changed anything.
        resolved = resolve_style_id(style_id)
        if not resolved and strict:
            raise ValueError("Visual style is not recognised.")
        style_id = resolved
    requested_scheme = _first_text(data, "color_scheme", "colorScheme", limit=16).lower()
    accent_hue = _accent_hue(data)
    if style_id:
        default = style_theme(style_id, requested_scheme or "light", accent_hue)
    else:
        default = _default_visual_theme(primary_color, secondary_color, category)
    theme = {}
    for key in _THEME_HEX_KEYS:
        aliases = (key, "".join([key.split("_")[0], *(part.capitalize() for part in key.split("_")[1:])]))
        # Records written before a token existed fall back to the preset value
        # rather than failing validation.
        fallback = default.get(key) or _default_visual_theme("", "", category).get(key, "")
        if not fallback:
            continue
        value_text = _first_text(data, *aliases, default=fallback, limit=16)
        _validate_hex_color(key.replace("_", " ").title(), value_text)
        theme[key] = value_text
    scrim = _first_text(data, "scrim_color", "scrimColor",
                        default=default.get("scrim_color", "rgba(0,0,0,0.5)"), limit=32)
    if not _SCRIM_RE.match(scrim):
        raise ValueError("Scrim colour must be an rgba() value.")
    theme["scrim_color"] = scrim
    button_style = _first_text(data, "button_style", "buttonStyle", default=default["button_style"], limit=24).lower()
    font_mood = _first_text(data, "font_mood", "fontMood", default=default["font_mood"], limit=24).lower()
    if button_style not in {"soft", "sharp", "rounded"}:
        raise ValueError("Button style must be one of: soft, sharp, rounded.")
    if font_mood not in {"serif", "modern", "classic"}:
        raise ValueError("Font mood must be one of: serif, modern, classic.")
    theme_mode = _first_text(data, "theme_mode", "themeMode", default="custom" if not style_id else "preset", limit=16).lower()
    if theme_mode not in {"preset", "custom"}:
        raise ValueError("Theme mode must be preset or custom.")
    color_scheme = requested_scheme or default.get("color_scheme", "light")
    if color_scheme not in {"light", "dark"}:
        raise ValueError("Color scheme must be light or dark.")
    if style_id and color_scheme not in VISUAL_STYLE_PRESETS[style_id]["modes"]:
        available = ", ".join(VISUAL_STYLE_PRESETS[style_id]["modes"])
        raise ValueError(
            f"The {VISUAL_STYLE_PRESETS[style_id]['label']} style is only available in: {available}."
        )
    theme["style_id"] = style_id or default.get("style_id", "")
    # Stored as degrees, not as the hex the owner picked: the hex is an
    # input, the hue is the decision, and re-solving from the hue is what
    # keeps a saved theme correct when the solver improves.
    if accent_hue is not None:
        theme["accent_hue"] = round(accent_hue % 360, 1)
    elif isinstance(default.get("accent_hue"), (int, float)):
        theme["accent_hue"] = round(float(default["accent_hue"]) % 360, 1)
    theme["theme_mode"] = theme_mode
    theme["color_scheme"] = color_scheme
    theme["button_style"] = button_style
    theme["font_mood"] = font_mood
    theme["scheme_preference"] = _scheme_preference(data, theme, default)
    return theme


def _stored_visual_theme(
    value,
    primary_color: str = "",
    secondary_color: str = "",
    category: str = "general",
) -> dict:
    """Re-normalise a STORED theme, and never raise doing it.

    A stored record is not user input. It was written by whichever release the
    owner last saved under, and it is read on every public page load by a
    visitor who cannot fix anything. So the only two acceptable outcomes here
    are the studio's theme and the default theme — never an exception.

    That distinction was missing until v8.5.4 and the read path simply called
    the write validator. When v8.5.2 renamed one style id, five of six live
    tenants started answering 500 for their whole brand payload: not just the
    colours, but every word and every image on the page, because the copy and
    the palette travel in the same response. The portals looked wiped.

    The alias in `RETIRED_STYLE_ALIASES` is what makes those tenants come back
    on their OWN palette. This is the net under it: any other stored value
    that a future release stops accepting costs that studio its theme for one
    page load, and costs it nothing else.
    """

    try:
        return _normalize_visual_theme(
            value, primary_color, secondary_color, category, strict=False
        )
    except (ValueError, TypeError):
        current_app.logger.warning(
            "visual_theme could not be normalised; serving the default theme",
            exc_info=True,
        )
        return _default_visual_theme(primary_color, secondary_color, category)


def _scheme_preference(data: dict, theme: dict, default: dict) -> str:
    """Who decides light or dark: the studio, or the visitor's device.

    Three values. ``light`` and ``dark`` pin the site to that mode — the
    behaviour every tenant had before v8.4.0, and still the default, because a
    studio's brand is the studio's decision. ``system`` follows the visitor's
    `prefers-color-scheme`, which is the one thing the studio genuinely cannot
    know: a parent opening the enrolment page at 11pm is a fact about the
    parent, not about the studio.

    ``system`` is only offered where it can be honoured. It needs BOTH modes
    published, so a style that ships one — arcade-lime is dark only, because
    its accent cannot reach readable contrast on a light page — cannot take it.
    Accepting it there would mean either a light page with a dark theme's
    tokens, or silently ignoring the setting; both are worse than saying no.
    """

    preference = _first_text(data, "scheme_preference", "schemePreference",
                             default=default.get("scheme_preference", ""), limit=16).lower()
    if not preference:
        return theme["color_scheme"]
    if preference not in {"light", "dark", "system"}:
        raise ValueError("Scheme preference must be light, dark, or system.")
    if preference == "system":
        style_id = theme.get("style_id", "")
        modes = VISUAL_STYLE_PRESETS[style_id]["modes"] if style_id in VISUAL_STYLE_PRESETS else ("light", "dark")
        if len(modes) < 2:
            label = VISUAL_STYLE_PRESETS[style_id]["label"] if style_id in VISUAL_STYLE_PRESETS else "This style"
            raise ValueError(
                f"{label} ships {modes[0]} only, so it cannot follow the visitor's device."
            )
    return preference


def _published_schemes(theme: object) -> dict:
    """Both palettes, when the site may be asked to render either.

    A page that follows the visitor's device has to hold the light tokens and
    the dark tokens at once — it cannot fetch the other one when the OS setting
    changes mid-visit, and a studio that publishes only the mode it happens to
    prefer would leave half its visitors on a palette solved for the other
    surface. So the scheme preference decides what is SENT, not just what is
    applied.
    """

    if not isinstance(theme, dict):
        return {}
    style_id = theme.get("style_id") or ""
    if theme.get("scheme_preference") != "system" or style_id not in VISUAL_STYLE_PRESETS:
        return {}
    hue = theme.get("accent_hue")
    hue = float(hue) if isinstance(hue, (int, float)) else None
    return {mode: style_theme(style_id, mode, hue)
            for mode in VISUAL_STYLE_PRESETS[style_id]["modes"]}


def _plan_payload(payload: dict, *, default_showcase_limit: int = 15) -> dict:
    """Validate and normalize a plan write payload.

    ``default_showcase_limit`` is used for PATCH requests that predate the
    showcase field.  It preserves the stored entitlement instead of silently
    resetting an existing plan to the entry-plan value.
    """

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
        # Defaults to the entry-plan number so a plan created without the field
        # publishes a real board rather than nothing.
        showcase_limit = int(payload.get(
            "showcaseLimit", payload.get("showcase_limit", default_showcase_limit)
        ))
    except (TypeError, ValueError) as exc:
        raise ValueError("Plan numeric limits must be valid integers.") from exc
    if (monthly_price_aud < 0 or student_limit <= 0 or user_limit <= 0
            or storage_limit_mb <= 0 or showcase_limit <= 0):
        raise ValueError("Plan limits must be positive, and monthly price cannot be negative.")
    features = payload.get("features", {})
    if not isinstance(features, dict):
        raise ValueError("Plan features must be a JSON object.")
    # Publication defaults to off. A plan reaching the public pricing page
    # because somebody created it is the failure migration 0023 closed; the
    # decision to sell one is separate from the decision to define it.
    is_public = bool(payload.get("isPublic", payload.get("is_public", False)))
    is_recommended = bool(payload.get("isRecommended", payload.get("is_recommended", False)))
    if is_recommended and not is_public:
        raise ValueError("A recommended plan must also be published.")
    return {
        "code": code,
        "name": name,
        "monthly_price_aud": monthly_price_aud,
        "student_limit": student_limit,
        "user_limit": user_limit,
        "storage_limit_mb": storage_limit_mb,
        "showcase_limit": showcase_limit,
        "features_json": json.dumps(features),
        "is_public": is_public,
        "is_recommended": is_recommended,
    }


def _plan_change_impact(
    current_plan: dict,
    target_plan: dict,
    *,
    usage: dict | None = None,
) -> dict:
    """Describe the safe, reviewable consequences of changing a plan.

    A plan change changes entitlements, not tenant-owned records.  Keeping
    this calculation on the API boundary gives the UI a server-authored
    confirmation payload and gives the audit row a durable explanation of why
    a tenant was asked to acknowledge the change.
    """

    def _features(plan: dict) -> dict:
        value = plan.get("features", plan.get("features_json", {}))
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (TypeError, ValueError):
                value = {}
        return value if isinstance(value, dict) else {}

    fields = (
        ("name", "plan_name"),
        ("monthly_price_aud", "monthly_price_aud"),
        ("student_limit", "student_limit"),
        ("user_limit", "user_limit"),
        ("storage_limit_mb", "storage_limit_mb"),
        ("showcase_limit", "showcase_limit"),
        ("is_public", "is_public"),
    )
    changed = []
    for key, label in fields:
        before = current_plan.get(key)
        after = target_plan.get(key)
        if before != after:
            changed.append({"field": label, "from": before, "to": after})

    current_features = _features(current_plan)
    target_features = _features(target_plan)
    feature_keys = sorted(set(current_features) | set(target_features))
    enabled_features = [key for key in feature_keys
                        if not current_features.get(key) and target_features.get(key)]
    disabled_features = [key for key in feature_keys
                         if current_features.get(key) and not target_features.get(key)]

    usage_over_new_limit = {}
    if usage:
        for usage_key, limit_key in (
            ("student_count", "student_limit"),
            ("user_count", "user_limit"),
            ("storage_used_mb", "storage_limit_mb"),
            ("showcase_active_count", "showcase_limit"),
        ):
            current = int(usage.get(usage_key) or 0)
            limit = int(target_plan.get(limit_key) or 0)
            if limit and current > limit:
                usage_over_new_limit[usage_key] = {"current": current, "limit": limit}

    return {
        "from": {
            "code": current_plan.get("code", ""),
            "name": current_plan.get("name", ""),
        },
        "to": {
            "code": target_plan.get("code", ""),
            "name": target_plan.get("name", ""),
        },
        "changed": changed,
        "enabled_features": enabled_features,
        "disabled_features": disabled_features,
        "usage_over_new_limit": usage_over_new_limit,
        "content_preserved": [
            "tenant_settings",
            "website_brand_and_showcase",
            "showcase_featured_ranks",
            "students_courses_and_registrations",
            "media_and_audit_history",
        ],
        "notification_required": True,
    }


def _clear_other_recommended(cur, plan: dict, code: str) -> None:
    """Recommendation is a radio, not a checkbox.

    A unique partial index guarantees at most one recommended plan. Without
    this the second plan an operator marks would fail on a constraint the UI
    never mentioned; here it simply moves the badge, which is what the click
    meant.
    """

    if not plan["is_recommended"]:
        return
    cur.execute(
        "UPDATE plans SET is_recommended = false WHERE is_recommended AND code <> %s",
        (code,),
    )


# A date the caller did not mention at all. Distinct from `None`, which is a
# caller saying "clear this".
KEEP = object()


def _subscription_date(payload: dict, *names: str):
    """A subscription date, distinguishing "not mentioned" from "clear it".

    These were read with `payload.get(a) or payload.get(b)`, so a key the
    caller never sent came back as `None` and the upsert wrote NULL over the
    stored value. The Super Admin form has never sent `trialEndsAt`, so every
    tenant save silently cleared `trial_ends_at` — the column the trial state
    and the expiring-trial counter are both read from.

    `or` was wrong for a second reason: an empty string is falsy, so
    `{"startsAt": ""}` fell through to the snake_case key instead of being
    read as a clear.
    """

    for name in names:
        if name in payload:
            value = payload[name]
            return value if value not in ("", None) else None
    return KEEP


def _tenant_write_payload(
    payload: dict,
    *,
    require_slug: bool,
    current_settings: dict | None = None,
) -> dict:
    """Validate a tenant write without erasing settings the caller cannot edit.

    The Platform Admin tenant form owns commercial and contact fields, not the
    studio's public website.  Its PATCH payload therefore omits nested brand
    records such as ``website_profile`` and ``principal_profile``.  Normalising
    an omitted record as a fresh default and merging it into ``tenants.settings``
    silently erased that content whenever an operator changed a plan.

    On update, seed only omitted fields from the locked tenant row.  Explicit
    values still win, while creation keeps the existing product defaults.
    """

    stored = dict(current_settings or {})
    if stored:
        payload = dict(payload)
        preserved_settings = {
            "category": "category",
            "slogan": "slogan",
            "registrationProfile": "registration_profile",
            "copyPack": "copy_pack",
            "messageTemplates": "message_templates",
            "localizedCopy": "localized_copy",
            "heroProfile": "hero_profile",
            "websiteProfile": "website_profile",
            "principalProfile": "principal_profile",
            "faqItems": "faq_items",
            "visualTheme": "visual_theme",
            "ownerName": "owner_name",
            "ownerRole": "owner_role",
            "ownerPhone": "owner_phone",
            "ownerEmail": "owner_email",
            "billingEmail": "billing_email",
            "abn": "abn",
            "website": "website",
            "notes": "notes",
            "studioAdminEmail": "studio_admin_email",
            "studioAdminName": "studio_admin_name",
        }
        for camel, snake in preserved_settings.items():
            if camel not in payload and snake not in payload and snake in stored:
                payload[snake] = stored[snake]

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
    message_templates = _normalize_message_templates(
        payload.get("messageTemplates", payload.get("message_templates"))
    )
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
        "message_templates": message_templates,
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
        "starts_at": _subscription_date(payload, "startsAt", "starts_at"),
        "ends_at": _subscription_date(payload, "endsAt", "ends_at"),
        "trial_ends_at": _subscription_date(payload, "trialEndsAt", "trial_ends_at"),
        "current_period_ends_at": _subscription_date(
            payload, "currentPeriodEndsAt", "current_period_ends_at"),
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
                # No new password: change the name and the address, leave the
                # credential alone. This branch is only reachable when
                # `password` is empty — `elif password` above consumed the
                # other case — so the `if not password: raise` that used to
                # stand here fired every single time and the UPDATE below it
                # was unreachable. The effect was that editing any tenant with
                # a Studio Admin login 500'd unless the operator retyped a
                # password, which is every ordinary edit. Live from 2026-07-10
                # to 2026-08-04.
                #
                # It failed safe, at least: the raise happens before the
                # subscription upsert and before the commit, so the whole
                # transaction rolled back and nothing was written. Twenty-five
                # days of saves that reported an error and changed nothing.
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
                # A brand-new login needs a credential. Without one this used
                # to insert `hash("")`, producing an account nobody can ever
                # sign in to — `/auth/login` refuses an empty password before
                # it verifies anything, so it was not a way in, it was a way
                # to have a row that looks like an account and is not one.
                # The onboarding checklist then ticked "Studio Admin login
                # configured" for it, which is the checklist lying.
                if not password:
                    raise ValueError(
                        "Set a password for the Studio Admin login, or send the owner a "
                        "password setup link instead of creating the account here."
                    )
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


# A duplicate of services.media.ensure_media_schema lived here with no callers
# and a stale CHECK constraint (it predated 'website_image'). Removed with the
# upload-path DDL fix so there is one definition to keep correct.


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

    if is_standalone():
        # Standalone edition has no plan capacity. Report unlimited headroom
        # without the per-tenant creation lock, which only exists to
        # serialise the capacity check.
        return 0, 2**31 - 1
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

    if is_standalone():
        # Standalone edition: every product feature is included in the buyout.
        return True
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

    ``?thumb=1`` remains compatible with older clients. New clients use the
    explicit ``?variant=thumb|medium|display`` contract.
    """

    requested_variant = variant
    query_variant = str(request.args.get("variant", "")).strip().lower()
    if query_variant:
        if query_variant not in {"thumb", "medium", "display"}:
            return _error("Media variant is invalid.", 400)
        requested_variant = query_variant
    elif requested_variant is None and str(request.args.get("thumb", "")).lower() in ("1", "true", "yes"):
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


def _workspace_for(slug: str, name: str, head: dict | None = None) -> str:
    """Create tenant workspace files and return the relative path."""

    try:
        return ensure_tenant_workspace(current_app.config["PROJECT_ROOT"], slug, name, head)
    except WorkspaceError as exc:
        raise ValueError(str(exc)) from exc


def _pick_pair(value: object) -> str:
    """Read one string out of a {"zh", "en"} pair, Chinese first."""

    if isinstance(value, dict):
        return str(value.get("zh") or value.get("en") or "").strip()
    return str(value or "").strip()


def _tenant_head(name: str, settings: dict) -> dict:
    """Compose the <head> title and description a crawler will be served.

    This mirrors ``applySeo`` in the portal exactly — SEO override, then hero
    subtitle, then slogan. The page has always computed these in the browser;
    a link unfurler or a search crawler that runs no scripts was reading the
    file, which said whatever the studio was called on the day it was created.
    """

    website = settings.get("website_profile") or {}
    hero = settings.get("hero_profile") or {}
    title = _pick_pair(website.get("seo_title"))
    description = (
        _pick_pair(website.get("seo_description"))
        or _pick_pair(hero.get("subtitle"))
        or _pick_pair(settings.get("slogan"))
    )
    return {"title": title or name, "description": description}


def _refresh_tenant_workspace(slug: str, name: str, settings: dict) -> None:
    """Re-render the public shell so it agrees with what was just published.

    Publishing used to leave these files untouched, so the only way a renamed
    studio could reach its own <title> was to create a new tenant. A failure
    here must not fail the publish that already committed: the page still
    renders the new name from /brand, only the served source lags.
    """

    try:
        _workspace_for(slug, name, _tenant_head(name, settings))
    except (ValueError, OSError) as exc:  # pragma: no cover - filesystem edge
        current_app.logger.warning("Tenant workspace refresh failed for %s: %s", slug, exc)


@api_v1.route("/health", methods=["GET"])
def health():
    """Health check for the StudioSaaS v1 surface.

    ``?deep=1`` also probes the database, so the container healthcheck stops
    reporting healthy while every real request would 500 (RDS outage). The
    shallow form stays constant-time for load balancers and uptime pings.
    """

    body = {
        "ok": True,
        "service": "PWE Studio Edition API" if is_standalone() else "PWE Studio SaaS API",
        "version": "v1",
        "appVersion": str(current_app.config["APP_VERSION"]),
        "mode": studiosaas_mode(),
        "showProducerCredit": show_producer_credit(),
    }
    if request.args.get("deep") == "1":
        # Measured BEFORE the database probe, so the 503 payload carries it: a
        # full volume is one of the likelier reasons PostgreSQL just stopped
        # answering, and an operator reading that response should not have to
        # ssh in to find out.
        #
        # Reported, never fatal. This payload drives the container healthcheck,
        # so failing it on a disk warning would restart a service that is
        # answering every request perfectly.
        #
        # Measured against the data directory, which is a volume on the host
        # root disk; the container's own "/" is an overlay and would report the
        # image size instead.
        try:
            probe = str(current_app.config.get("DATA_DIR") or current_app.root_path)
            usage = shutil.disk_usage(probe)
            percent = round(usage.used / usage.total * 100, 1) if usage.total else 0.0
            body["disk"] = {
                "percentUsed": percent,
                "freeGb": round(usage.free / 1024 ** 3, 2),
                "status": "critical" if percent >= 90 else "warn" if percent >= 80 else "ok",
            }
        except OSError:
            body["disk"] = {"status": "unknown"}
        try:
            with connect() as conn:
                fetch_one(conn, "SELECT 1 AS ok", ())
                body["themes"] = _theme_drift(conn)
                body["workspaces"] = _workspace_drift(conn)
            body["db"] = "ok"
        except Exception:
            body["ok"] = False
            body["db"] = "error"
            return jsonify(body), 503
    return jsonify(body)


def _theme_drift(conn) -> dict:
    """How many live tenants store a theme this release no longer accepts.

    "SELECT 1" proves the database answers. It does not prove this release can
    render the tenants inside it, and that is the failure that actually
    happened: v8.5.2 retired one style id, five of six portals began serving
    500 for their entire content payload, and deep health stayed green through
    the deploy and the automatic rollback window. The gate measured the
    building, not the tenants.

    Deliberately NOT fatal. Deep health drives the container healthcheck, and
    a stale row is not a reason to restart a service that is answering every
    request — especially now that `_stored_visual_theme` guarantees a readable
    page regardless. It is fatal to a DEPLOY instead: pwestudio_remote.sh
    requires `"unreadable":0` before it keeps a release. That puts the alarm
    where the change is, without holding a healthy container hostage.
    """

    rows = fetch_all(
        conn,
        "SELECT slug, COALESCE(settings->'visual_theme', '{}'::jsonb) AS visual_theme, "
        "       COALESCE(settings->>'category', 'general') AS category "
        "FROM tenants WHERE status <> 'deleted' AND archived_at IS NULL "
        "ORDER BY slug LIMIT 200",
        (),
    )
    unreadable = []
    for row in rows:
        if not row["visual_theme"]:
            continue
        try:
            _normalize_visual_theme(row["visual_theme"], "", "", row["category"], strict=True)
        except (ValueError, TypeError) as error:
            unreadable.append({"slug": row["slug"], "reason": str(error)[:120]})
    return {
        "tenants": len(rows),
        "unreadable": len(unreadable),
        "examples": unreadable[:5],
        "status": "drifted" if unreadable else "ok",
    }


def _workspace_drift(conn) -> dict:
    """How many live tenants are served a name they no longer call themselves.

    The public shell is materialised: `tenants/<slug>/index.html` carries the
    studio's name in <title>, in the social-preview tags and in the structured
    data. Nothing rewrote those files after creation, so a studio that renamed
    itself kept serving its old name to every crawler and link unfurler while
    the page itself — which asks /brand — looked correct to a human.

    Reported, never fatal, for the same reason as theme drift: a stale file is
    not a reason to restart a container that answers every request. It is a
    reason for a deploy to stop, and for this number to be visible.
    """

    rows = fetch_all(
        conn,
        "SELECT slug, name FROM tenants "
        "WHERE status <> 'deleted' AND archived_at IS NULL ORDER BY slug LIMIT 200",
        (),
    )
    root = Path(current_app.config["PROJECT_ROOT"]) / "tenants"
    stale = []
    for row in rows:
        meta_path = root / str(row["slug"]) / "tenant.json"
        if not meta_path.is_file():
            stale.append({"slug": row["slug"], "reason": "workspace missing"})
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            stale.append({"slug": row["slug"], "reason": str(error)[:120]})
            continue
        if str(meta.get("name") or "") != str(row["name"] or ""):
            stale.append({"slug": row["slug"], "reason": "name differs from the database"})
    return {
        "tenants": len(rows),
        "stale": len(stale),
        "examples": stale[:5],
        "status": "drifted" if stale else "ok",
    }


@api_v1.route("/industry-presets", methods=["GET"])
def industry_presets():
    """Return the shared onboarding, copy, and theme presets."""

    return jsonify({"presets": public_industry_presets(),
                    "styles": public_visual_style_presets()})


@api_v1.route("/theme-preview", methods=["GET"])
def theme_preview():
    """Solve the palette for a colour the owner is currently picking.

    The accent picker needs to show the real result while the owner drags a
    colour input, and the real result is whatever the solver says. Shipping a
    second solver to the browser to avoid the round trip would give this
    product three implementations of one algorithm; there are already two, and
    they are only safe because a parity test compares them token by token.

    Read-only, no tenant state, cheap: two `build` calls.
    """

    source = (request.args.get("accent") or "").strip()
    raw_hue = (request.args.get("hue") or "").strip()
    notes: list[str] = []

    if source:
        try:
            _validate_hex_color("Accent", source)
        except ValueError as error:
            return jsonify({"error": str(error)}), 400
        if palette.chroma(source) < palette.ACCENT_INPUT_MIN_CHROMA:
            notes.append("achromatic")
        hue = accent_hue_of_colour(source)
        if not notes and abs(palette.hsl_of(source)[0] - hue) > 0.5:
            notes.append("moved_out_of_status_band")
    elif raw_hue:
        try:
            hue = float(raw_hue) % 360
        except ValueError:
            return jsonify({"error": "Hue must be a number of degrees."}), 400
    else:
        hue = palette.DEFAULT_ACCENT_HUE

    return jsonify({
        "hue": round(hue, 1),
        "notes": notes,
        "themes": {mode: style_theme(FREE_ACCENT_STYLE_ID, mode, hue)
                   for mode in VISUAL_STYLE_PRESETS[FREE_ACCENT_STYLE_ID]["modes"]},
    })


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
               t.settings->'message_templates' AS message_templates,
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
                   m.public_display_name, m.show_on_public_timetable,
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
            if not is_standalone() and int(active_users["n"] or 0) >= int(plan_row["user_limit"]):
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
                SELECT id, status, public_display_name, show_on_public_timetable
                FROM memberships
                WHERE id = %s AND tenant_id = %s AND role <> 'owner'
                FOR UPDATE
                """,
                (parsed_id, tenant.tenant_id),
            )
            existing = cur.fetchone()
            if not existing:
                return _error("Operational team membership was not found.", 404)
            # Omitted means unchanged, not "revoke consent". A PATCH that only
            # meant to change a role must not quietly take a teacher's name off
            # the public timetable — or, worse, leave it on when the caller
            # believed it was sending the current state.
            public_name = str(
                payload.get("publicDisplayName",
                            payload.get("public_display_name",
                                        existing["public_display_name"])) or ""
            ).strip()[:80]
            show_publicly = _bool_from_json(
                payload, "showOnPublicTimetable", "show_on_public_timetable",
                default=bool(existing["show_on_public_timetable"]))
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
                if not is_standalone() and int(active_users["n"] or 0) >= int(plan_row["user_limit"]):
                    return _error(
                        f"User limit reached ({plan_row['user_limit']}). Upgrade the plan before reactivating this member.",
                        403,
                    )
            cur.execute(
                """
                UPDATE memberships
                SET role = %s, status = %s,
                    public_display_name = %s, show_on_public_timetable = %s
                WHERE id = %s AND tenant_id = %s AND role <> 'owner'
                RETURNING id
                """,
                (role, status, public_name, show_publicly, parsed_id, tenant.tenant_id),
            )
            cur.fetchone()
        _refresh_tenant_usage(conn, tenant.tenant_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="team.member_updated",
            resource_type="membership",
            resource_id=parsed_id,
            # The consent flag is recorded because it is a decision about a
            # person's name on the open internet, and "who turned this on and
            # when" is the only useful answer if they ever ask.
            metadata={"role": role, "status": status, "showOnPublicTimetable": show_publicly},
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
        # Sent rather than assumed. The console has to tell a studio how many
        # works its site publishes, and a number invented in the browser would
        # be a second opinion about somebody's plan.
        showcase_limit = showcase_limit_for(conn, tenant.tenant_id)
    return jsonify({"draft": draft, "versions": versions,
                    "limits": {"showcase": showcase_limit}})


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
@permission_required("tenant:update")

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
                legacy=_legacy_identity_copy(
                    {
                        **current_settings,
                        "category": category,
                        "welcome_message": current["welcome_message"],
                    }
                ),
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
            message_templates = _normalize_message_templates(
                payload.get("messageTemplates", current_settings.get("message_templates"))
            )
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
                "message_templates": message_templates,
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
    # After the commit, so a filesystem problem can never roll back a publish
    # that the version ledger has already recorded.
    _refresh_tenant_workspace(tenant.slug, _clean_text(payload, "name", current["name"]), current_settings)
    return jsonify({"tenant": row, "publishedVersion": next_version})


@api_v1.route("/tenant/brand/publication-status/<int:requested_version>", methods=["GET"])
@tenant_owner_required
def get_tenant_publication_status(requested_version: int):
    """Return server-proven publication state for one saved version.

    Publication writes are authoritative in the version ledger. The browser
    must not deep-compare a normalized public JSON projection and turn a
    harmless shape difference into ``fields: websiteProfile``.
    """

    if requested_version < 1:
        return _error("requested_version must be a positive integer.")
    with connect() as conn:
        tenant = _tenant_context(conn)
        latest = fetch_one(
            conn,
            """
            SELECT version_number, published_at, payload IS NOT NULL AS has_payload
            FROM tenant_brand_versions
            WHERE tenant_id = %s
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (tenant.tenant_id,),
        ) or {}
    published_version = int(latest.get("version_number") or 0)
    has_payload = bool(latest.get("has_payload"))
    if published_version < requested_version:
        state = "pending"
        version_state = "pending"
    elif not has_payload:
        state = "attention"
        version_state = "invalid"
    else:
        # A later publish supersedes an older request; current public content
        # is still valid and should not be reported as a failed publication.
        state = "ready"
        version_state = "ready" if published_version == requested_version else "superseded"
    return jsonify({
        "requestedVersion": requested_version,
        "publishedVersion": published_version or None,
        "publishedAt": latest.get("published_at"),
        "state": state,
        "checks": [
            {"key": "published_version", "state": version_state, "ok": state == "ready"},
            {"key": "stored_payload", "state": "ready" if has_payload else "invalid", "ok": has_payload},
        ],
    })


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
                "localizedCopy": _normalize_localized_copy(
                    row["localized_copy"] or {},
                    row["category"] or "general",
                    legacy=_legacy_identity_copy(row),
                ),
                "heroProfile": row["hero_profile"] or _default_hero_profile(row["category"] or "general", row["name"]),
                "websiteProfile": row["website_profile"] or _default_website_profile(),
                "principalProfile": row["principal_profile"] or _default_principal_profile(row["name"]),
                "faqItems": row["faq_items"] or _default_faq_items(row["category"] or "general"),
                "messageTemplates": _normalize_message_templates(row["message_templates"]),
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
@permission_required("courses:write")

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
@permission_required("courses:write")

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
@permission_required("credits:read")
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


def _cms_visible_notification_types() -> tuple[str, ...]:
    """Return notification types the current CMS actor may inspect."""

    types = ["registration.created"]
    actor = getattr(g, "actor", None)
    if actor is not None:
        try:
            require_permission(actor, "class_bookings:review")
        except PermissionDeniedError:
            pass
        else:
            types.append("class_booking.created")
    return tuple(types)


def _cms_notification_response(row: dict) -> dict:
    """Serialize a notification without exposing internal database fields."""

    created_at = row.get("created_at")
    return {
        "id": str(row["id"]),
        "sequence": int(row["sequence_no"]),
        "type": row["notification_type"],
        "title": row["title"],
        "summary": row["summary"],
        "resourceType": row["resource_type"],
        "resourceId": row["resource_id"],
        "targetTab": row["target_tab"],
        "targetSubtab": row["target_subtab"],
        "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or ""),
        "read": bool(row["is_read"]),
    }


@api_v1.route("/notifications", methods=["GET"])
@permission_required("registrations:read")
def list_cms_notifications():
    """List persistent CMS notifications and the current unread count."""

    raw_after = request.args.get("after")
    if raw_after in (None, ""):
        after_sequence = None
    else:
        try:
            after_sequence = int(raw_after)
        except (TypeError, ValueError):
            return _error("after must be a non-negative integer.")
        if after_sequence < 0:
            return _error("after must be a non-negative integer.")
    raw_limit = request.args.get("limit", str(_cms_notifications.DEFAULT_LIMIT))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return _error(f"limit must be between 1 and {_cms_notifications.MAX_LIMIT}.")
    if not 1 <= limit <= _cms_notifications.MAX_LIMIT:
        return _error(f"limit must be between 1 and {_cms_notifications.MAX_LIMIT}.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        result = _cms_notifications.list_for_user(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
            after_sequence=after_sequence,
            limit=limit,
        )
    return jsonify({
        "notifications": [_cms_notification_response(row) for row in result["notifications"]],
        "cursor": result["next_cursor"],
        "nextCursor": result["next_cursor"],
        "unreadCount": result["unread_count"],
    })


@api_v1.route("/notifications/read-all", methods=["POST"])
@permission_required("registrations:read")
def mark_all_cms_notifications_read():
    """Mark every visible CMS notification read for the current user."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        _cms_notifications.mark_all_read(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
        )
        conn.commit()
        unread_count = _cms_notifications.unread_count(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
        )
    return jsonify({"ok": True, "unreadCount": unread_count})


@api_v1.route("/notifications/<notification_id>/read", methods=["POST"])
@permission_required("registrations:read")
def mark_cms_notification_read(notification_id: str):
    """Mark one visible CMS notification read for the current user."""

    try:
        notification_id = str(_uuid.UUID(notification_id))
    except (ValueError, AttributeError):
        return _error("Notification not found.", 404)
    with connect() as conn:
        tenant = _tenant_context(conn)
        found = _cms_notifications.mark_read(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_id=notification_id,
            notification_types=_cms_visible_notification_types(),
        )
        if not found:
            return _error("Notification not found.", 404)
        conn.commit()
        unread_count = _cms_notifications.unread_count(
            conn,
            tenant_id=tenant.tenant_id,
            user_id=g.actor.user_id,
            notification_types=_cms_visible_notification_types(),
        )
    return jsonify({"ok": True, "unreadCount": unread_count})

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
            # FOR UPDATE: two concurrent approvals of the same registration
            # must serialize here, so the second sees the first's status and
            # fails the transition check instead of converting twice.
            cur.execute(
                """
                SELECT id, first_name, last_name, parent_name, mobile, email, message,
                       payload, student_id, status
                FROM registrations
                WHERE tenant_id = %s AND id = %s
                FOR UPDATE
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
    # Financial aggregates share the same boundary as the legacy projection:
    # roles without analytics:read (teacher / front_desk / staff) get the
    # operational counters only, never revenue or liability figures.
    # Fail closed: an absent actor strips financials rather than leaking them.
    actor = getattr(g, "actor", None)
    show_financials = False
    if actor is not None:
        try:
            require_permission(actor, "analytics:read")
            show_financials = True
        except PermissionDeniedError:
            show_financials = False
    if not show_financials:
        business = {
            "attended_total": business["attended_total"],
            "attended_month": business["attended_month"],
        }
    payload["business"] = business
    return jsonify({"dashboard": payload})


# A studio names its own sections, and those names are also its nav items. One
# studio's English course label is the full list of media it teaches — 74
# characters, 241 pixels, and with every section switched on the bar wrapped to
# a second line inside a header one line tall. The heading on the page keeps
# the whole sentence; only the entry in the bar is clipped.
NAV_LABEL_LIMIT = {"zh": 10, "en": 24}

# The call to action is tighter than the rest of the bar. It is a bordered pill
# sitting next to the language switch, so it has the least room and the most
# padding, and the field behind it is the one a studio is most likely to fill
# with a sentence: one studio's reads 「原创油画 × 私人定制」. The hero button
# still shows the whole thing — it reads that field directly, not this label.
CTA_LABEL_LIMIT = {"zh": 7, "en": 18}


def _clip_nav_label(value: str, language: str, limits: dict[str, int] | None = None) -> str:
    """Shorten a label to something a navigation bar can hold."""

    limit = (limits or NAV_LABEL_LIMIT).get(language, 24)
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _public_surface_entry(key: str, intent: bool, ready: bool, href: str,
                          *, reason: str = "no_content", next_action: str = "review_in_studio_admin",
                          surface: str | None = None, placement: str = "home",
                          navigation_eligible: bool = True, footer_eligible: bool = True,
                          content_ready: bool | None = None,
                          dependency_ready: bool | None = None,
                          published_version: int | None = None,
                          label: dict | None = None) -> dict:
    """Build the public navigation contract used by every tenant surface.

    ``intent`` is the owner's switch; ``ready`` is the smallest truthful
    content check for that route.  Keeping both values in the response lets
    Studio Admin explain why an entry is hidden instead of merely removing it.
    """

    effective_content_ready = bool(ready if content_ready is None else content_ready)
    effective_dependency_ready = bool(ready if dependency_ready is None else dependency_ready)
    effective_ready = bool(ready and effective_content_ready and effective_dependency_ready)
    visible = bool(intent and effective_ready)
    result = {
        "key": key,
        "intent": bool(intent),
        "ready": effective_ready,
        "contentReady": effective_content_ready,
        "dependencyReady": effective_dependency_ready,
        "visible": visible,
        "href": href,
        "surface": surface or key,
        "placement": placement,
        "navigationEligible": bool(navigation_eligible),
        "footerEligible": bool(footer_eligible),
        "reasonCode": "ready" if visible else (reason if intent else "disabled_by_owner"),
        "nextAction": "" if visible else next_action,
        "publishedVersion": published_version,
    }
    # Keep the helper backwards-compatible for internal callers that only
    # need readiness. Public shell entries opt into a localized label so every
    # page can render the same navigation copy without scraping the homepage.
    if label is not None:
        result["label"] = {
            "zh": str(label.get("zh") or label.get("en") or "").strip(),
            "en": str(label.get("en") or label.get("zh") or "").strip(),
        }
    return result


def _public_surface_actions(hero: dict, modules: dict[str, dict],
                            secondary_label: dict | None = None) -> dict[str, dict]:
    """Resolve hero actions against the same readiness contract as navigation.

    A button must never point at a hidden or empty section. ``auto`` exists only
    for pre-v9.8.9 tenants and selects the first ready public destination;
    explicit choices fail closed so Studio Admin can explain what to fix.
    """

    register = modules["register"]
    primary = {
        "key": "primary",
        "targetType": "register",
        "href": register["href"],
        "visible": bool(register["visible"]),
        "reasonCode": register["reasonCode"],
        "nextAction": register["nextAction"],
    }
    if register.get("label") is not None:
        primary["label"] = register["label"]
    requested = str(hero.get("secondary_cta_target") or "auto").strip().lower()
    if requested == "hidden":
        result = {
            "primary": primary,
            "secondary": {
                "key": "secondary", "targetType": "hidden", "href": "", "visible": False,
                "reasonCode": "disabled_by_owner", "nextAction": "choose_secondary_cta_target",
            },
        }
        if secondary_label is not None:
            result["secondary"]["label"] = secondary_label
        return result
    if requested == "external":
        href = str(hero.get("secondary_cta_href") or "").strip()
        if not re.match(r"^https://\S+$", href, re.IGNORECASE):
            href = ""
        result = {
            "primary": primary,
            "secondary": {
                "key": "secondary", "targetType": "external", "href": href,
                "visible": bool(href),
                "reasonCode": "ready" if href else "missing_external_url",
                "nextAction": "" if href else "add_secondary_cta_url",
            },
        }
        if secondary_label is not None:
            result["secondary"]["label"] = secondary_label
        return result

    candidates = ("courses", "showcase", "timetable", "register")
    target = requested
    if requested == "auto":
        target = next((key for key in candidates if modules[key]["visible"]), "register")
    module = modules.get(target, register)
    result = {
        "primary": primary,
        "secondary": {
            "key": "secondary", "targetType": target, "href": module["href"],
            "visible": bool(module["visible"]), "reasonCode": module["reasonCode"],
            "nextAction": module["nextAction"],
        },
    }
    if secondary_label is not None:
        result["secondary"]["label"] = secondary_label
    return result


@api_v1.route("/public/<tenant_slug>/surface", methods=["GET"])
def public_surface(tenant_slug: str):
    """Return one effective contract for public navigation and footer links.

    The endpoint intentionally reports readiness from published data, not from
    the admin editor. A link therefore appears only when its target can render
    useful content, while the ``reasonCode`` remains available to previews and
    support tooling.
    """

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        row = fetch_one(
            conn,
            """
            SELECT name, contact_phone, contact_email, address,
                   COALESCE(settings->>'category', 'general') AS category,
                   COALESCE(settings->'website_profile', '{}'::jsonb) AS website,
                   COALESCE(settings->'principal_profile', '{}'::jsonb) AS principal,
                   COALESCE(settings->'hero_profile', '{}'::jsonb) AS hero,
                   COALESCE(settings->'localized_copy', '{}'::jsonb) AS localized_copy,
                   COALESCE(settings->'faq_items', '[]'::jsonb) AS faq,
                   COALESCE(settings->'registration_profile', '{}'::jsonb) AS registration
            FROM tenants WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        profile = _normalize_website_profile((row or {}).get("website") or {})
        category = str((row or {}).get("category") or "general")
        localized_copy = _normalize_localized_copy(
            (row or {}).get("localized_copy") or {},
            category,
            legacy={
                "courses_label": profile.get("courses_label", ""),
                "gallery_label": profile.get("gallery_label", ""),
                "faq_label": profile.get("faq_label", ""),
                "contact_label": profile.get("contact_label", ""),
            },
        )
        principal = row.get("principal") or {}
        hero = row.get("hero") or {}
        faq = row.get("faq") or []
        registration = row.get("registration") or {}
        course_row = fetch_one(
            conn,
            "SELECT count(*) AS n FROM courses WHERE tenant_id = %s AND is_active",
            (tenant.tenant_id,),
        )
        gallery_row = fetch_one(
            conn,
            """
            SELECT count(*) AS n
            FROM portfolio_items p
            JOIN students s ON s.id = p.student_id AND s.tenant_id = p.tenant_id
            JOIN media_variants mv ON mv.tenant_id = p.tenant_id
              AND mv.media_asset_id = p.media_asset_id AND mv.variant = 'display'
            JOIN LATERAL (
                SELECT status
                FROM student_publication_consent_events e
                WHERE e.tenant_id = p.tenant_id AND e.student_id = p.student_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT 1
            ) consent ON consent.status = 'confirmed'
            WHERE p.tenant_id = %s AND p.visibility = 'shared'
              AND p.public_consent_at IS NOT NULL AND s.status <> 'archived'
            """,
            (tenant.tenant_id,),
        ) if _plan_feature_enabled(conn, tenant.tenant_id, "portfolio") else {"n": 0}
        timetable_ready = False
        if profile.get("show_timetable"):
            timezone_name = _tenant_timezone(conn, tenant.tenant_id)
            weeks = profile.get("timetable_weeks") or TIMETABLE_DEFAULT_WEEKS
            _today, occurrences = _timetable_occurrences(
                conn, tenant.tenant_id, weeks, timezone_name)
            timetable_ready = bool(occurrences)
        limit = showcase_limit_for(conn, tenant.tenant_id)
        published = fetch_one(
            conn,
            """
            SELECT version_number, published_at
            FROM tenant_brand_versions
            WHERE tenant_id = %s
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (tenant.tenant_id,),
        ) or {}

    active_items = [
        item for item in profile.get("showcase_items", [])
        if item.get("publication_state") == "active"
    ]
    showcase_ready = bool(_ordered_showcase_items(active_items)[:limit])
    contact_ready = bool(row.get("contact_phone") or row.get("contact_email") or row.get("address"))
    principal_ready = bool(str(principal.get("bio") or "").strip())
    about_ready = bool(
        _localized_pair(profile, "about_title", limit=600)["zh"]
        or _localized_pair(profile, "about_body", limit=600)["zh"]
        or profile.get("about_images")
        or profile.get("about_items")
    )
    published_version = published.get("version_number")
    preset = _preset_for(category)
    work_noun = preset.get("work_noun") or {"zh": "作品", "en": "work", "en_plural": "works"}
    venue_noun = preset.get("venue_noun") or {"zh": "工作室", "en": "studio"}

    def public_label_text(value, language: str) -> str:
        """Resolve industry placeholders before labels enter the public shell."""

        result = str(value or "").strip()
        if not result:
            return ""
        work = str(work_noun.get(language) or work_noun.get("zh") or "作品")
        works = str(
            (work_noun.get("en_plural") or work_noun.get("en") or work)
            if language == "en"
            else (work_noun.get("zh") or work)
        )
        venue = str(venue_noun.get(language) or venue_noun.get("zh") or "工作室")
        return (
            result.replace("%WORKS%", works)
            .replace("%WORK%", work)
            .replace("%VENUE%", venue)
        )

    def surface_label(value, fallback: dict[str, str], limit: int = 80,
                      limits: dict[str, int] | None = None) -> dict[str, str]:
        pair = _localized_pair({"value": value}, "value", limit=limit)
        return {
            "zh": _clip_nav_label(public_label_text(pair["zh"] or fallback["zh"], "zh"), "zh", limits),
            "en": _clip_nav_label(public_label_text(pair["en"] or fallback["en"], "en"), "en", limits),
        }

    labels = {
        "principal": {"zh": "主理人", "en": "Principal"},
        "showcase": surface_label(profile.get("showcase_label"), {"zh": "工作室作品", "en": "Selected Work"}),
        "courses": surface_label(localized_copy.get("courses_label"), {"zh": "课程与班次", "en": "Courses & Classes"}),
        "timetable": surface_label(profile.get("timetable_label"), {"zh": "课程安排", "en": "Timetable"}),
        "gallery": surface_label(localized_copy.get("gallery_label"), {"zh": "学员作品", "en": "Student Works"}),
        "faq": surface_label(localized_copy.get("faq_label"), {"zh": "常见问题", "en": "Questions & Answers"}),
        "student": {"zh": "学员专区", "en": "Student Login"},
        "register": surface_label(localized_copy.get("primary_cta"), {"zh": "预约体验", "en": "Book a Trial"},
                                  limits=CTA_LABEL_LIMIT),
    }
    secondary_label = surface_label(localized_copy.get("secondary_cta"), {"zh": "查看课程", "en": "Explore Programs"})
    modules = {
        "about": _public_surface_entry(
            "about", bool(profile.get("show_about", False)), about_ready,
            "#home:about", reason="missing_about_content", next_action="complete_space_profile",
            surface="home", placement="after_hero", navigation_eligible=False,
            footer_eligible=False, published_version=published_version,
        ),
        "principal": _public_surface_entry(
            "principal", bool(profile.get("show_principal", True)), principal_ready,
            "#home:artist", reason="missing_content", next_action="add_principal_bio", surface="home",
            placement="after_about", footer_eligible=False, published_version=published_version,
            label=labels["principal"],
        ),
        "showcase": _public_surface_entry(
            "showcase", bool(profile.get("show_showcase", False)), showcase_ready,
            f"/{tenant.slug}/showcase", reason="no_published_works", next_action="publish_showcase_work", surface="showcase",
            placement="after_principal", published_version=published_version, label=labels["showcase"],
        ),
        "courses": _public_surface_entry(
            "courses", bool(profile.get("show_courses", True)), int((course_row or {}).get("n") or 0) > 0,
            "#home:courses", reason="no_published_courses", next_action="publish_course", surface="home",
            placement="after_showcase", published_version=published_version, label=labels["courses"],
        ),
        "timetable": _public_surface_entry(
            "timetable", bool(profile.get("show_timetable", False)), timetable_ready,
            f"/{tenant.slug}/timetable", reason="no_upcoming_classes", next_action="publish_timetable", surface="timetable",
            placement="navigation", published_version=published_version, label=labels["timetable"],
        ),
        "gallery": _public_surface_entry(
            "gallery", bool(profile.get("show_gallery", True)), int((gallery_row or {}).get("n") or 0) > 0,
            "#home:gallery", reason="no_consented_student_work", next_action="share_student_work", surface="home",
            placement="after_courses", published_version=published_version, label=labels["gallery"],
        ),
        "faq": _public_surface_entry(
            "faq", bool(profile.get("show_faq", True)), bool(faq),
            "#home:faq", reason="no_faq_content", next_action="add_faq", surface="home",
            placement="after_gallery", published_version=published_version, label=labels["faq"],
        ),
        "contact": _public_surface_entry(
            "contact", bool(profile.get("show_contact", True)), contact_ready,
            "#home:contact", reason="missing_contact_details", next_action="add_contact_details", surface="home",
            placement="after_faq", navigation_eligible=False, footer_eligible=False,
            published_version=published_version,
        ),
        "student": _public_surface_entry(
            "student", bool(profile.get("show_student_area", hero.get("show_student_login", True))), True,
            "#my", surface="home", placement="utility", published_version=published_version, label=labels["student"],
        ),
        "register": _public_surface_entry(
            "register", True, bool(registration or row.get("name")), "#join",
            reason="registration_unavailable", next_action="complete_registration_profile", surface="register",
            placement="action", published_version=published_version, label=labels["register"],
        ),
    }
    navigation = [module for module in modules.values() if module["navigationEligible"]]
    footer = [module for module in modules.values() if module["footerEligible"]]
    actions = _public_surface_actions(hero, modules, secondary_label)
    return jsonify({"contract": {
        "version": 3,
        "contractVersion": 3,
        "generatedAt": _datetime.now(_timezone.utc).isoformat(),
        "publishedVersion": published_version,
        "publishedAt": published.get("published_at"),
        "modules": modules,
        "navigation": navigation,
        "footer": footer,
        "actions": actions,
        "shell": {"navigation": navigation, "footer": footer, "actions": actions},
    }})


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
                   settings->'message_templates' AS message_templates,
                   settings->'visual_theme' AS visual_theme,
                   COALESCE((settings->>'professional_demo')::boolean, false) AS demo_tenant
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        published = fetch_one(
            conn,
            """
            SELECT version_number, published_at
            FROM tenant_brand_versions
            WHERE tenant_id = %s
            ORDER BY version_number DESC
            LIMIT 1
            """,
            (tenant.tenant_id,),
        ) or {}
    category = row["category"] or "general"
    preset = _preset_for(category)
    row["category_label"] = row["category_label"] or preset["label"]
    row["slogan"] = row["slogan"] or preset["slogan"]
    row["registration_profile"] = row["registration_profile"] or _default_registration_profile(category)
    row["copy_pack"] = row["copy_pack"] or preset["copy_pack"]
    row["hero_profile"] = row["hero_profile"] or _default_hero_profile(category, row["name"])
    row["website_profile"] = row["website_profile"] or _default_website_profile()
    row["principal_profile"] = row["principal_profile"] or _default_principal_profile(row["name"])
    row["localized_copy"] = _normalize_localized_copy(
        row["localized_copy"] or {},
        category,
        legacy=_legacy_identity_copy(row),
    )
    row["faq_items"] = row["faq_items"] or _default_faq_items(category)
    row["message_templates"] = _normalize_message_templates(row["message_templates"])
    # A stored theme is whatever set of tokens existed on the day it was saved.
    # v8.4.0 added eighteen — the `info` role, the quiet form of every role,
    # `--surface-hover` and `--on-accent-muted` — so every tenant record written
    # before today is missing them.
    #
    # The page skips a token it is not sent, which means those eighteen would
    # fall through to portal-theme.css: a studio on recital-plum would get plum
    # surfaces and a vintage-press `--info` and `--success-soft`. Half a theme,
    # and no error anywhere.
    #
    # Re-normalising on read fills the gaps from the studio's OWN style rather
    # than from the default, and leaves every token the record does carry
    # exactly as stored. It is not a migration: the record is untouched until
    # the owner next saves.
    row["visual_theme"] = _stored_visual_theme(
        row["visual_theme"], row["primary_color"], row["secondary_color"], category
    ) if row["visual_theme"] else _default_visual_theme(
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
    row["messageTemplates"] = row["message_templates"]
    row["visualTheme"] = row["visual_theme"]
    row["visualThemes"] = _published_schemes(row["visual_theme"])
    # Industry nouns for the public template's %VENUE% / %WORK% tokens.
    row["venueNoun"] = dict(preset["venue_noun"])
    row["workNoun"] = dict(preset["work_noun"])
    # The portal and register page each hard-coded this string, so a consent
    # record could cite a version the visitor's page never rendered. One value,
    # served with the notice it refers to.
    row["privacyNoticeVersion"] = PRIVACY_NOTICE_VERSION
    # A demonstration tenant publishes synthetic work under an invented
    # person's name on a public URL. The portal says "these are Janet's own
    # paintings" — which is true of the fiction and false of the world, and a
    # visitor who arrives from a search engine has no way to tell. So the
    # tenant carries the fact into its own footer rather than relying on
    # everyone who links to it to explain.
    row["demoTenant"] = bool(row.get("demo_tenant"))
    row["demo_tenant"] = row["demoTenant"]
    row["publishedVersion"] = published.get("version_number")
    row["publishedAt"] = published.get("published_at")

    # The board itself is served by /public/<slug>/showcase, not from here.
    #
    # This response is the portal's critical path — every word, every image,
    # the principal's biography, the contact details — and in v8.5.4 one
    # unreadable field in it left five sites blank. A list with no fixed upper
    # bound is exactly what should not grow inside it.
    #
    # The SWITCH stays, because the page needs to know whether to reserve the
    # section before the board arrives. That is also the race this re-creates:
    # the switch is here and the content is elsewhere, so the portal must hold
    # the switch in `state.sectionsOff` and honour it in the renderer — the
    # v8.5.3 defect, designed around rather than rediscovered.
    for served_separately in ("showcase_items", "showcase_categories"):
        row["website_profile"].pop(served_separately, None)
    row["websiteProfile"] = row["website_profile"]
    return jsonify({"brand": row})


# ──────────────────────────────────────────────
# v8.9.0: the public timetable
#
# `class_schedules` stores a RULE — "every Wednesday at four". A visitor wants
# DATES. Turning one into the other is this endpoint's whole job, and it is
# done on the server for a reason that has already cost this product once:
# dates.
#
#   The studio's week is defined in `tenants.timezone`. A parent opening the
#   page from another timezone, or at 11pm on a Sunday, must see the studio's
#   days — not their device's. `/v1/...` dates are RFC 1123 elsewhere in this
#   API precisely because a client-side reinterpretation once silently shifted
#   them by a day. Here the projection, "today", and the week boundaries are
#   all computed against the tenant's zone before anything is serialised.
# ──────────────────────────────────────────────

def _timetable_occurrences(conn, tenant_id: str, weeks: int, timezone_name: str):
    """Project public weekly rules onto real dates, exceptions applied.

    Returns (today, [(date, schedule_row, exception_or_None)]) ordered by date
    then start time. Cancelled dates are INCLUDED and flagged, never dropped:
    a class that silently disappears for one week looks like a broken website,
    while one struck through and labelled 停课 · 公众假期 looks like a studio
    that is minding the shop.
    """

    import datetime as _dt

    today = _dt.datetime.now(ZoneInfo(timezone_name)).date()
    horizon = today + _timedelta(days=weeks * 7)
    rows = fetch_all(
        conn,
        """
        SELECT cs.id, cs.label, cs.weekday,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, cs.capacity, cs.room,
               c.name AS course_name, c.description AS course_description,
               c.age_range, c.price_aud_cents,
               COALESCE(NULLIF(m.public_display_name, ''), u.full_name) AS teacher_name,
               COALESCE(m.show_on_public_timetable, false) AS teacher_public,
               (SELECT count(*) FROM class_schedule_students css
                 WHERE css.schedule_id = cs.id) AS enrolled
        FROM class_schedules cs
        LEFT JOIN courses c ON c.id = cs.course_id
        LEFT JOIN users u ON u.id = cs.teacher_user_id
        LEFT JOIN memberships m
               ON m.user_id = cs.teacher_user_id AND m.tenant_id = cs.tenant_id
        WHERE cs.tenant_id = %s AND cs.is_active AND cs.is_public
        ORDER BY cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    exceptions = {
        (str(r["schedule_id"]), r["on_date"]): r
        for r in fetch_all(
            conn,
            "SELECT schedule_id, on_date, cancelled, note FROM class_schedule_exceptions "
            "WHERE tenant_id = %s AND on_date >= %s AND on_date < %s",
            (tenant_id, today, horizon),
        )
    }
    # Approved bookings hold seats; pending ones deliberately do not. See
    # `public_class_booking` — a request nobody has looked at yet must not
    # block a family who would actually turn up.
    booked: dict[tuple[str, object], int] = {}
    for r in fetch_all(
        conn,
        "SELECT schedule_id, on_date, count(*) AS n FROM class_bookings "
        "WHERE tenant_id = %s AND status = 'approved' AND on_date >= %s AND on_date < %s "
        "GROUP BY schedule_id, on_date",
        (tenant_id, today, horizon),
    ):
        booked[(str(r["schedule_id"]), r["on_date"])] = int(r["n"] or 0)

    out = []
    for offset in range((horizon - today).days):
        day = today + _timedelta(days=offset)
        # class_schedules.weekday follows JS getDay(): 0=Sunday..6=Saturday.
        weekday = day.isoweekday() % 7
        for row in rows:
            if int(row["weekday"]) != weekday:
                continue
            key = (str(row["id"]), day)
            out.append((day, row, exceptions.get(key), booked.get(key, 0)))
    return today, out


def _timetable_entry(day, row, exception, approved, fields, want_booking):
    """One class on one date, as the public page receives it.

    Two rules run through every line here:

    * **The switch is a ceiling, the content is a floor — intersect them.** A
      field turned on with nothing behind it prints nothing, so a studio never
      publishes an empty "Room:".
    * **No internal identifiers leave.** The occurrence is addressed by date
      and start time. Emitting the schedule uuid would turn a primary key into
      a public contract we could never rebuild the row without honouring.
    """

    cancelled = bool(exception and exception["cancelled"])
    capacity = int(row["capacity"] or 0)
    taken = int(row["enrolled"] or 0) + int(approved or 0)
    seats_left = max(0, capacity - taken)

    entry = {
        "date": day.isoformat(),
        "start": row["start_time"],
        "title": row["course_name"] or row["label"] or "",
        # The label becomes a subtitle only when it is not already the title —
        # "Wednesday group" under "Kids Oil Painting" is useful, under itself
        # it is noise.
        "subtitle": row["label"] if (row["course_name"] and row["label"]) else "",
        "cancelled": cancelled,
        "note": (exception["note"] if exception else "") or "",
    }
    if fields.get("teacher") and row["teacher_public"] and row["teacher_name"]:
        # AND, never OR. The layout preference and the person's consent are
        # different questions, and consent wins.
        entry["teacher"] = row["teacher_name"]
    if fields.get("room") and row["room"]:
        entry["room"] = row["room"]
    if fields.get("age_range") and row["age_range"]:
        entry["ageRange"] = row["age_range"]
    if fields.get("duration") and row["duration_minutes"]:
        entry["durationMinutes"] = int(row["duration_minutes"])
        entry["end"] = _end_of_class(row["start_time"], int(row["duration_minutes"]))
    if fields.get("price") and row["price_aud_cents"]:
        entry["priceAudCents"] = int(row["price_aud_cents"])
    if fields.get("capacity") and capacity > 0:
        entry["capacity"] = capacity
        entry["seatsLeft"] = seats_left
        # Proportional, not absolute. Capacity runs from 1 (one-to-one) to 30
        # (a big class), and "nearly full" at a fixed 3 is wrong at both ends.
        entry["nearlyFull"] = 0 < seats_left <= max(1, -(-capacity * 25 // 100))
    if want_booking and not cancelled:
        entry["bookable"] = True
    return entry


def _end_of_class(start: str, minutes: int) -> str:
    """HH:MM plus a duration, wrapping at midnight rather than overflowing."""

    try:
        hour, minute = (int(part) for part in str(start).split(":", 1))
    except (TypeError, ValueError):
        return ""
    total = (hour * 60 + minute + max(0, minutes)) % (24 * 60)
    return f"{total // 60:02d}:{total % 60:02d}"


@api_v1.route("/public/<tenant_slug>/timetable", methods=["GET"])
def public_timetable(tenant_slug: str):
    """Upcoming public classes for one studio, as dates rather than rules.

    Its own endpoint and its own page. `/brand` carries only the switch, for
    the same reason the showcase board does: `/brand` is the portal's critical
    path, and a list with no fixed upper bound does not belong in it.

    Never emits a student's name. `seatsLeft` is an aggregate — a count, not a
    roster — and the names behind it stay on the private side of this wall.
    """

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        row = fetch_one(
            conn,
            "SELECT name, COALESCE(settings->'website_profile', '{}'::jsonb) AS website "
            "FROM tenants WHERE id = %s",
            (tenant.tenant_id,),
        )
        profile = _normalize_website_profile((row or {}).get("website") or {})
        if not profile.get("show_timetable"):
            # Off is not an error and not a 404. The page renders its own
            # "nothing published yet" state rather than a failure.
            return jsonify({"enabled": False, "days": [], "timezone": "",
                            "weeks": 0, "booking": False})

        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        weeks = profile.get("timetable_weeks") or TIMETABLE_DEFAULT_WEEKS
        fields = profile.get("timetable_fields") or dict(TIMETABLE_FIELD_DEFAULTS)
        want_booking = bool(profile.get("show_timetable_booking"))
        today, occurrences = _timetable_occurrences(
            conn, tenant.tenant_id, weeks, timezone_name)

    days: list[dict] = []
    for day, schedule, exception, approved in occurrences:
        entry = _timetable_entry(day, schedule, exception, approved, fields, want_booking)
        if not days or days[-1]["date"] != entry["date"]:
            days.append({"date": entry["date"],
                         "weekday": day.isoweekday() % 7,
                         "classes": []})
        days[-1]["classes"].append(entry)

    return jsonify({
        "enabled": True,
        "timezone": timezone_name,
        "today": today.isoformat(),
        "weeks": weeks,
        "booking": want_booking,
        "fields": fields,
        "label": profile.get("timetable_label") or {"zh": "", "en": ""},
        "lead": profile.get("timetable_lead") or {"zh": "", "en": ""},
        "studio": (row or {}).get("name") or "",
        "days": days,
    })


@api_v1.route("/public/<tenant_slug>/timetable/book", methods=["POST"])
def public_class_booking(tenant_slug: str):
    """Ask for a place in one class, on one date, without an account.

    Three decisions carry this endpoint, and every one of them is about what
    the RESPONSE says rather than what the database stores.

    **1. The reply must not reveal whether this phone belongs to a student.**
    The server does match the name and phone against existing students — the
    CMS needs to know — but the body returned is byte-for-byte the same either
    way. Otherwise the form stops being a form: type a number, watch for a
    different answer, and you have a way to ask "is this person enrolled
    here?" about anyone. That is not a hypothetical; it is the same endpoint
    used slightly differently.

    **2. A pending request does not hold a seat.** Capacity is re-checked at
    approval, not here. A tap that nobody has looked at yet must not lock out
    a family who would actually turn up, and by approval time this moment's
    arithmetic is stale anyway.

    **3. But the parent is told where they stand.** A class showing "1 place
    left" that quietly collects five requests will disappoint four people. The
    reply says how many are already waiting, and hands the choice back.

    Booking is bounded by the same `timetable_weeks` the page projects: a date
    a visitor cannot see is a date they cannot ask for. Deliberately not a
    second setting — two horizons drift apart, and the person who finds the
    drift is always the parent.
    """

    from .services.student_access import find_student, normalize_phone

    payload = _json_payload()
    name = _clean_text(payload, "name", _clean_text(payload, "contactName"))[:80]
    phone_raw = _clean_text(payload, "phone", _clean_text(payload, "contactPhone"))[:40]
    phone = normalize_phone(phone_raw)
    message = _clean_text(payload, "message")[:300]
    start = _clean_text(payload, "start", _clean_text(payload, "startTime"))
    language = _clean_text(payload, "language")[:8]
    if not name or not phone:
        return _error("Please give a full name and a contact phone number.")
    if not re.match(r"^\d{2}:\d{2}$", start):
        return _error("Please choose a class from the timetable.")
    try:
        on_date = _roster_date(payload.get("date"))
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        # Same limiter shape as the balance lookup this borrows its identity
        # rule from — the form is only worth rate-limiting because it can be
        # asked repeatedly, which is exactly what decision 1 is about.
        if _rate_limited(f"booking:{tenant.tenant_id}:{_client_ip()}", 10):
            return _error("Too many requests. Please try again shortly.", 429)

        row = fetch_one(
            conn,
            "SELECT COALESCE(settings->'website_profile', '{}'::jsonb) AS website "
            "FROM tenants WHERE id = %s",
            (tenant.tenant_id,),
        )
        profile = _normalize_website_profile((row or {}).get("website") or {})
        if not (profile.get("show_timetable") and profile.get("show_timetable_booking")):
            return _error("This studio is not taking booking requests here.", 404)

        timezone_name = _tenant_timezone(conn, tenant.tenant_id)
        weeks = profile.get("timetable_weeks") or TIMETABLE_DEFAULT_WEEKS
        today, occurrences = _timetable_occurrences(
            conn, tenant.tenant_id, weeks, timezone_name)

        # Addressed by date and start time, never by uuid: the public page was
        # never given one. This also means an occurrence that is not currently
        # published simply cannot be booked.
        match = next(
            (item for item in occurrences
             if item[0] == on_date and item[1]["start_time"] == start),
            None,
        )
        if match is None:
            return _error(
                "That class is not on the published timetable. Please pick one from the list.",
                404,
            )
        _day, schedule, exception, approved = match
        if exception and exception["cancelled"]:
            return _error("That class is not running on this date.")

        capacity = int(schedule["capacity"] or 0)
        taken = int(schedule["enrolled"] or 0) + int(approved or 0)
        seats_left = max(0, capacity - taken)
        class_title = schedule["course_name"] or schedule["label"] or ""

        # Matching happens here and the result goes ONLY into the record. It
        # never reaches the branch that builds the response.
        #
        # "matched" is the service's word, and it is the ONLY status that means
        # one unambiguous person: "ambiguous" (two students share a name and a
        # number) and "missing" both have to fall through to the new-enquiry
        # path. Guessing between two families is worse than asking.
        lookup = find_student(conn, tenant_id=tenant.tenant_id, name=name, phone=phone)
        student_id = (lookup.student or {}).get("id") if lookup.status == "matched" else None

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO class_bookings
                    (tenant_id, schedule_id, on_date, student_id, contact_name,
                     contact_phone, message, privacy_notice_version, source_language, campaign)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (schedule_id, on_date, contact_phone)
                    WHERE status = 'pending' DO NOTHING
                RETURNING id
                """,
                (tenant.tenant_id, schedule["id"], on_date, student_id, name, phone,
                 message, PRIVACY_NOTICE_VERSION, language,
                 json.dumps(_campaign_from_payload(payload), ensure_ascii=False)),
            )
            created = cur.fetchone()
            cur.execute(
                "SELECT count(*) AS n FROM class_bookings "
                "WHERE schedule_id = %s AND on_date = %s AND status = 'pending'",
                (schedule["id"], on_date),
            )
            waiting = int((cur.fetchone() or {}).get("n") or 0)
        if created:
            _cms_notifications.create(
                conn,
                tenant_id=tenant.tenant_id,
                notification_type="class_booking.created",
                title="新约课申请",
                summary=f"{name} · {class_title or '课程'} · {on_date.isoformat()} {start}",
                resource_type="class_booking",
                resource_id=str(created["id"]),
                target_tab="pending",
                target_subtab="bookings",
                dedupe_key=f"class_booking:{created['id']}",
            )
        # The booking and its CMS notification must be durable before an SMTP
        # attempt, and a duplicate submission must never send a second alert.
        conn.commit()
        if created is not None:
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
            admin_email = (
                (tenant_row.get("studio_admin_email") or tenant_row.get("contact_email") or "").strip()
                if tenant_row else ""
            )
            if admin_email:
                _notifications.send_safely(
                    conn,
                    tenant_id=tenant.tenant_id,
                    template_key="class_booking_admin_alert",
                    to_email=admin_email,
                    context={
                        "booking_id": str(created["id"]),
                        "class_title": class_title or "—",
                        "class_date": on_date.isoformat(),
                        "start_time": start,
                        "contact_name": name,
                        "mobile": phone,
                        "message": message or "—",
                        "studio_name": tenant_row["name"] or tenant_slug,
                    },
                )
                conn.commit()

    return jsonify({
        "ok": True,
        # `duplicate` is not an error. A parent who is unsure the first tap
        # worked taps again; the honest answer is "we already have it", not a
        # red box and not a second row in somebody's queue.
        "duplicate": created is None,
        "seatsLeft": seats_left,
        "waiting": waiting,
        "date": on_date.isoformat(),
        "start": start,
        "title": class_title,
    })


def _campaign_from_payload(payload: dict) -> dict:
    """The UTM-ish fields a public form may carry, bounded and stringified."""

    raw = payload.get("campaign")
    if not isinstance(raw, dict):
        return {}
    return {
        str(key)[:40]: str(value or "")[:120]
        for key, value in list(raw.items())[:8]
        if str(key).strip()
    }


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
@permission_required("analytics:read")
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


@api_v1.route("/public/<tenant_slug>/showcase", methods=["GET"])
def public_showcase(tenant_slug: str):
    """The studio's own work, paginated, limited by the tenant's plan.

    Its own endpoint rather than a field on `/brand` for one reason: `/brand`
    is the critical path. Every word and every image of a portal arrives in
    that one response, and in v8.5.4 a single unreadable field in it took five
    sites blank. A list with no fixed upper bound does not belong there.

    **Publishing is limited here; storing is not limited anywhere.** A tenant
    that drops from growth (150) to starter (15) keeps all 150 works in its
    record — this endpoint serves the first 15. Upgrading restores the rest
    with no migration, because nothing was ever removed. A valid
    ``featured_rank`` is applied before that cap, so editorial intent survives
    a plan change without turning the rank into a second quota.

    The plan limit is applied BEFORE the category filter, not after. The other
    order would let a studio on the entry plan publish its whole archive by
    splitting it across drawers and linking each one. ``surface=home`` is a
    server-controlled six-item preview; all other requests use the twelve-item
    C-scheme page size.
    """

    with connect() as conn:
        try:
            tenant = resolve_tenant(conn, tenant_slug, "path")
        except TenantResolutionError:
            return _error("Unknown tenant.", 404)
        row = fetch_one(
            conn,
            "SELECT COALESCE(settings->'website_profile', '{}'::jsonb) AS website, "
            "       COALESCE(settings->>'category', 'general') AS category "
            "FROM tenants WHERE id = %s",
            (tenant.tenant_id,),
        )
        limit = showcase_limit_for(conn, tenant.tenant_id)

    profile = _normalize_website_profile((row or {}).get("website") or {})
    if not profile.get("show_showcase"):
        # Switched off is not an error, and not a 404 either: the section
        # simply has nothing to say.
        return jsonify({"enabled": False, "items": [], "categories": [],
                        "total": 0, "offset": 0, "hasMore": False})

    # Plan capacity applies only to active works.  Drafts and archived works
    # remain in the private workspace, so a downgrade never destroys them and
    # an upgrade can reveal them again after the owner marks them active.
    # Editorial rank is applied before the entitlement cap: the works the
    # owner deliberately selected are the ones that remain public when a plan
    # has fewer slots, while the displaced records stay stored and recoverable.
    active_items = [
        item for item in profile.get("showcase_items", [])
        if item.get("publication_state") == "active"
    ]
    published = _ordered_showcase_items(active_items)[:limit]
    categories = profile.get("showcase_categories", [])

    wanted = (request.args.get("category") or "").strip()[:24]
    if wanted and any(c["id"] == wanted for c in categories):
        visible = [item for item in published if item.get("category_id") == wanted]
    else:
        wanted, visible = "", published

    try:
        offset = max(0, int(request.args.get("offset") or 0))
    except (TypeError, ValueError):
        offset = 0
    surface = (request.args.get("surface") or "").strip().lower()
    page_size = SHOWCASE_PREVIEW_SIZE if surface == "home" else SHOWCASE_PAGE_SIZE
    page = visible[offset:offset + page_size]

    return jsonify({
        "enabled": True,
        "category": wanted,
        # Only the drawers that actually hold a published work. An empty
        # filter chip is a dead end the visitor has to discover by pressing it.
        "categories": [c for c in categories
                       if any(i.get("category_id") == c["id"] for i in published)],
        "items": page,
        "total": len(visible),
        "offset": offset,
        "pageSize": page_size,
        "nextOffset": offset + len(page),
        "hasMore": offset + len(page) < len(visible),
    })


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
    code = str(payload.get("accessCode") or payload.get("code") or "").strip()
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
        # Name+phone alone is an enrolment/balance oracle for anyone holding
        # (or guessing) a family's details. Once the studio issues a student
        # an access code, that code becomes required here too — same secret
        # as the private area. Codeless students keep the legacy behaviour so
        # studios can adopt codes at their own pace.
        if lookup.student:
            stored_hash = str(lookup.student.get("access_code_hash") or "")
            code_active = bool(stored_hash) and not lookup.student.get("access_code_revoked_at")
            if code_active and not _verify_student_access_code(lookup.student, code):
                fingerprint = _student_lookup_fingerprint(name, phone)
                _record_student_access_failure(
                    conn,
                    tenant_id=tenant.tenant_id,
                    lookup_hash=fingerprint,
                    ip_address=_client_ip(),
                )
                _audit_request(
                    conn,
                    tenant_id=tenant.tenant_id,
                    action="public.balance_lookup",
                    resource_type="student_lookup",
                    metadata={"matched": False, "access_code_required": True},
                )
                conn.commit()
                return jsonify({"match": False, "accessCodeRequired": True})
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


_DUMMY_ACCESS_HASH: list[str] = []


def _dummy_access_verify(code: str) -> None:
    """Burn the same PBKDF2 work as a real verification.

    Without this, a miss on (name, phone) returns immediately while a hit
    spends ~100ms hashing — a timing oracle for pair validity. The dummy
    hash is computed once, lazily, so import stays cheap.
    """

    if not _DUMMY_ACCESS_HASH:
        _DUMMY_ACCESS_HASH.append(_auth_hash_password("000000"))
    _auth_verify_password(code or "000000", _DUMMY_ACCESS_HASH[0])


@api_v1.route("/public/<tenant_slug>/student/unlock", methods=["POST"])
def public_student_unlock(tenant_slug: str):
    """Issue a one-hour HttpOnly student session after access-code verification."""

    # Flat per-IP ceiling on top of the per-identity DB lockout: the lockout
    # stops repeated guesses at ONE family but not one IP spraying many
    # identities at one guess each.
    if _rate_limited(f"student-unlock:{tenant_slug}:{_client_ip()}", 10):
        return _error("Too many attempts. Please wait a minute.", 429)

    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    code = str(payload.get("code") or "").strip()
    if not name or not phone or len(code) != 6 or not code.isdigit():
        return _error("Name, phone, and a six-digit access code are required.", 400)

    with connect() as conn:
        tenant = resolve_tenant(conn, tenant_slug, "path")
        fingerprint = _student_lookup_fingerprint(name, phone)
        lock_seconds = _student_access_lock_seconds(
            conn,
            tenant_id=tenant.tenant_id,
            lookup_hash=fingerprint,
            ip_address=_client_ip(),
        )
        if lock_seconds:
            # Retry-After lets the portal tell the family how long to wait
            # instead of an open-ended "please try again later".
            response = _error("Too many attempts. Please try again later.", 429)
            body, status = response if isinstance(response, tuple) else (response, 429)
            body.headers["Retry-After"] = str(lock_seconds)
            return body, status
        lookup = _find_public_student(
            conn, tenant_id=tenant.tenant_id, name=name, phone=phone
        )
        verified = bool(lookup.student) and _verify_student_access_code(lookup.student, code)
        if not lookup.student or not str((lookup.student or {}).get("access_code_hash") or ""):
            _dummy_access_verify(code)
        if not verified:
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
        response.headers["Cache-Control"] = "private, no-cache"
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

    if _rate_limited(f"registration-media:{_client_ip()}", 5):
        return _error("Too many uploads. Please wait a moment.", 429)

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
        response.headers["Cache-Control"] = "private, no-cache"
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
    if _rate_limited(_client_ip(), 5):
        return _error("Too many registration attempts. Please wait a moment.", 429)

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
        payload.get("privacyNoticeVersion")
        or payload.get("privacy_notice_version")
        or PRIVACY_NOTICE_VERSION
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
        source_label = {
            "portal": "门户",
            "qr": "二维码",
            "campaign": "活动页",
        }.get(source, "报名页")
        _cms_notifications.create(
            conn,
            tenant_id=tenant.tenant_id,
            notification_type="registration.created",
            title="新报名申请",
            summary=f"{first_name} {last_name}".strip() + f" · {source_label}",
            resource_type="registration",
            resource_id=str(registration_id),
            target_tab="pending",
            target_subtab="registrations",
            dedupe_key=f"registration:{registration_id}",
        )
        # Make the lead and its CMS notification durable before any SMTP work.
        # External delivery is best-effort and must never decide whether the
        # registration exists.
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
    tenant_settings = (settings_row["settings"] if settings_row else None) or {}
    legacy_state = tenant_settings.get("legacy_cms") or {}
    roster_rows = fetch_all(
        conn,
        """
        SELECT id, roster_date, student_id, source, status, note, created_at,
               to_char(class_time, 'HH24:MI') AS class_time, one_to_one
        FROM daily_roster_entries
        WHERE tenant_id = %s AND status <> 'cancelled'
        -- Slot order, unset last: the CMS renders the day straight from this.
        ORDER BY roster_date, class_time ASC NULLS LAST, created_at, id
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
            "classTime": row["class_time"],
            "oneToOne": bool(row["one_to_one"]),
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
        "operationalSettings": {
            # One tenant-owned default keeps every staff device consistent.
            # Existing roster rows retain their explicitly saved class_time.
            "defaultClassTime": tenant_settings.get("default_class_time") or "14:30",
        },
        # The stored rev is bumped by every aggregate save; falling back to
        # wall-clock keeps pre-rev tenants working (their first save records
        # one). The save endpoint compares the client's rev against this.
        "rev": int(legacy_state.get("rev") or time.time()),
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
    elif role is Role.PARENT or role is None:
        # Parents cannot obtain a staff session (login refuses them), but the
        # projection is a security boundary in its own right — fail closed.
        projected["students"] = []
        projected["pending"] = []
        projected["packages"] = []
        projected["logs"] = []
        projected["rosterEntries"] = []
        projected["groups"] = {}
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


@api_v1.route("/operational-settings", methods=["PATCH"])
@tenant_admin_required
def update_operational_settings():
    """Update tenant-wide day-to-day defaults used by the operational CMS.

    This is deliberately separate from the brand publishing route: changing a
    roster default must not create a brand version or republish the website.
    The value only seeds new controls; it never rewrites existing bookings.
    """

    try:
        payload = _json_payload()
        default_class_time = _class_time(
            payload.get("defaultClassTime", payload.get("default_class_time"))
        )
        if default_class_time is None:
            raise ValueError("defaultClassTime is required and must use HH:MM.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE tenants
                SET settings = jsonb_set(
                        COALESCE(settings, '{}'::jsonb),
                        '{default_class_time}',
                        to_jsonb(%s::text),
                        true
                    ),
                    updated_at = now()
                WHERE id = %s
                """,
                (default_class_time, tenant.tenant_id),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="operations.default_class_time_updated",
            resource_type="tenant_settings",
            metadata={"defaultClassTime": default_class_time},
        )
        conn.commit()
    return jsonify({"ok": True, "defaultClassTime": default_class_time})


@api_v1.route("/legacy-cms/save", methods=["POST"])
@permission_required("students:write")
def legacy_cms_save():
    """Persist a safe subset of old CMS JSON edits back to tenant tables.

    students:write is the gate because student upserts are what every caller
    of the aggregate save actually edits. The package catalogue is priced
    commercial configuration, so that section only applies for operations
    admins — a front-desk/staff save round-trips it untouched.
    """

    payload = request.get_json(silent=True) or {}
    students = payload.get("students") if isinstance(payload.get("students"), list) else []
    packages = payload.get("packages") if isinstance(payload.get("packages"), list) else []
    actor_role = getattr(getattr(g, "actor", None), "role", None)
    can_edit_packages = actor_role in {Role.SUPER_ADMIN, Role.OWNER, Role.MANAGER}
    if not can_edit_packages:
        packages = []
    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            # Optimistic concurrency, enforced server-side. The tenant-row
            # lock serializes concurrent aggregate saves; a save carrying a
            # rev older than the stored one is a stale tab and must not
            # last-writer-win over profile edits committed since it loaded.
            # (The CMS already handles this 409 by reloading.) force=true is
            # the operator's explicit override from the conflict dialog.
            cur.execute(
                "SELECT settings->'legacy_cms' AS legacy FROM tenants WHERE id = %s FOR UPDATE",
                (tenant.tenant_id,),
            )
            _locked = cur.fetchone()
            stored_rev = int(((_locked or {}).get("legacy") or {}).get("rev") or 0)
            client_rev_raw = payload.get("rev")
            try:
                client_rev = int(client_rev_raw) if client_rev_raw is not None else None
            except (TypeError, ValueError):
                client_rev = None
            force_save = bool(payload.get("force"))
            if stored_rev and client_rev is not None and client_rev < stored_rev and not force_save:
                return jsonify({
                    "status": "conflict",
                    "message": "Data changed on another device/tab since this page loaded.",
                    "rev": stored_rev,
                }), 409
            new_rev = max(int(time.time()), stored_rev + 1)
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
                        "rev": new_rev,
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
@auth_required
def upload_media_asset():
    """Upload one tenant media asset through the canonical v1 endpoint.

    Portfolio uploads follow portfolio:write so teachers/staff can use the
    canonical endpoint (they previously had to detour through the legacy CMS
    upload); every other kind (brand/site assets) stays owner/manager.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        f = request.files.get("file")
        if not f or not f.filename:
            return _error("No file provided.")
        kind = str(request.form.get("kind") or "portfolio").strip() or "portfolio"
        try:
            if kind == "portfolio":
                require_permission(g.actor, "portfolio:write")
            elif g.actor.role not in {Role.SUPER_ADMIN, Role.OWNER, Role.MANAGER}:
                raise PermissionDeniedError("Tenant owner/admin privileges required.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
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


@api_v1.route("/public/plans", methods=["GET"])
def public_plans():
    """Pricing for the marketing site — public fields only, no auth.

    The rows come from `services.public_site.public_plan_rows`, which is also
    what renders the home page's pricing cards. One query for both means the
    JSON an integrator reads and the numbers a visitor sees cannot disagree;
    the reason its columns are named rather than starred is documented there.

    Prices are public by definition — they are printed on the marketing page
    this feeds — so there is nothing here an anonymous caller should not see.
    """

    response = jsonify({"plans": public_plan_rows()})
    # Pricing changes rarely and this is on the critical path of the public
    # home page; a short shared cache keeps a traffic spike off PostgreSQL.
    response.headers["Cache-Control"] = "public, max-age=300"
    return response


@api_v1.route("/plans", methods=["GET"])
@permission_required("plans:read")
def list_plans():
    """List StudioSaaS subscription plans."""

    with connect() as conn:
        rows = fetch_all(
            conn,
            """
            SELECT code, name, monthly_price_aud, student_limit, user_limit,
                   storage_limit_mb, showcase_limit, features, is_public, is_recommended
            FROM plans
            ORDER BY monthly_price_aud
            """,
            (),
        )
    return jsonify({"plans": rows})


@api_v1.route("/plans", methods=["POST"])
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
            _clear_other_recommended(cur, plan, plan["code"])
            cur.execute(
                """
                INSERT INTO plans (
                    code, name, monthly_price_aud, student_limit,
                    user_limit, storage_limit_mb, showcase_limit, features,
                    is_public, is_recommended
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
                """,
                (
                    plan["code"],
                    plan["name"],
                    plan["monthly_price_aud"],
                    plan["student_limit"],
                    plan["user_limit"],
                    plan["storage_limit_mb"],
                    plan["showcase_limit"],
                    plan["features_json"],
                    plan["is_public"],
                    plan["is_recommended"],
                ),
            )
        _audit(conn, tenant_id=None, action="plan.created", resource_type="plan", resource_id=plan["code"])
        conn.commit()
    return jsonify({"ok": True, "code": plan["code"]}), 201


@api_v1.route("/plans/<code>", methods=["PATCH", "DELETE"])
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
        existing = fetch_one(
            conn,
            """
            SELECT code, name, monthly_price_aud, student_limit, user_limit,
                   storage_limit_mb, showcase_limit, features, is_public,
                   is_recommended
            FROM plans
            WHERE code = %s
            """,
            (code,),
        )
        if not existing:
            return _error("Plan was not found.", 404)
        try:
            payload = _json_payload()
            payload["code"] = code
            plan = _plan_payload(
                payload,
                default_showcase_limit=int(existing.get("showcase_limit") or SHOWCASE_FALLBACK_LIMIT),
            )
        except ValueError as exc:
            return _error(str(exc))
        in_use = fetch_one(
            conn,
            "SELECT count(*) AS n FROM tenants WHERE plan_code = %s",
            (code,),
        )
        affected_tenants = int((in_use or {}).get("n") or 0)
        plan_impact = _plan_change_impact(existing, plan)
        plan_impact_changed = bool(
            plan_impact["changed"]
            or plan_impact["enabled_features"]
            or plan_impact["disabled_features"]
        )
        if affected_tenants and plan_impact_changed:
            acknowledged = payload.get("confirmPlanChange") is True
            notification_acknowledged = payload.get("tenantNotificationAcknowledged") is True
            if not (acknowledged and notification_acknowledged):
                plan_impact["affected_tenants"] = affected_tenants
                return api_error(
                    "Review the plan impact and acknowledge tenant notification before saving.",
                    409,
                    error="plan_change_confirmation_required",
                    details=plan_impact,
                )
        with conn.cursor() as cur:
            _clear_other_recommended(cur, plan, code)
            cur.execute(
                """
                UPDATE plans
                SET name = %s,
                    monthly_price_aud = %s,
                    student_limit = %s,
                    user_limit = %s,
                    storage_limit_mb = %s,
                    showcase_limit = %s,
                    features = %s::jsonb,
                    is_public = %s,
                    is_recommended = %s
                WHERE code = %s
                """,
                (
                    plan["name"],
                    plan["monthly_price_aud"],
                    plan["student_limit"],
                    plan["user_limit"],
                    plan["storage_limit_mb"],
                    plan["showcase_limit"],
                    plan["features_json"],
                    plan["is_public"],
                    plan["is_recommended"],
                    code,
                ),
            )
        if affected_tenants and plan_impact_changed:
            plan_impact["affected_tenants"] = affected_tenants
        _audit(
            conn,
            tenant_id=None,
            action="plan.updated",
            resource_type="plan",
            resource_id=code,
            metadata=(
                {
                    "impact": plan_impact,
                    "tenant_notification_acknowledged": payload.get(
                        "tenantNotificationAcknowledged"
                    ) is True,
                }
                if affected_tenants and plan_impact_changed
                else None
            ),
        )
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
                   COALESCE(showcase.showcase_active_count, 0) AS showcase_active_count,
                   COALESCE(showcase.showcase_draft_count, 0) AS showcase_draft_count,
                   COALESCE(showcase.showcase_archived_count, 0) AS showcase_archived_count,
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
                   -- Drives the one-click reset in Platform Admin. Exposed as a
                   -- column rather than read from a settings blob in the browser
                   -- so the console cannot offer the action on a real studio
                   -- because of a typo in a JSON path.
                   COALESCE((t.settings->>'professional_demo')::boolean, false) AS is_demo,
                   EXISTS (
                       SELECT 1 FROM tenant_brand_versions bv WHERE bv.tenant_id = t.id
                   ) AS portal_published,
                   (COALESCE(t.settings->>'logo_url', '') <> '') AS logo_ready,
                   (COALESCE(t.settings->'hero_profile'->>'title', '') <> '') AS hero_ready,
                   (t.contact_email <> '' OR t.contact_phone <> '') AS contact_ready,
                   t.created_at, t.archived_at, t.archive_path, t.deletion_requested_at, t.deleted_at
            FROM tenants t
            LEFT JOIN tenant_usage u ON u.tenant_id = t.id
            LEFT JOIN LATERAL (
                SELECT
                    count(*) FILTER (WHERE COALESCE(item->>'publication_state', 'active') = 'active') AS showcase_active_count,
                    count(*) FILTER (WHERE item->>'publication_state' = 'draft') AS showcase_draft_count,
                    count(*) FILTER (WHERE item->>'publication_state' = 'archived') AS showcase_archived_count
                FROM jsonb_array_elements(
                    CASE
                        WHEN jsonb_typeof(t.settings->'website_profile'->'showcase_items') = 'array'
                        THEN t.settings->'website_profile'->'showcase_items'
                        ELSE '[]'::jsonb
                    END
                ) AS item
            ) showcase ON TRUE
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
    try:
        validate_subscription_dates(
            {name: (None if data[name] is KEEP else data[name])
             for name in ("starts_at", "ends_at", "trial_ends_at", "current_period_ends_at")},
            data["subscription_status"],
        )
    except ValueError as exc:
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
                    # There is nothing to keep on a row being created, so an
                    # unmentioned date is simply null here.
                    *(None if data[name] is KEEP else data[name] for name in (
                        "starts_at", "ends_at", "trial_ends_at", "current_period_ends_at")),
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
            payload = _json_payload()
        except ValueError as exc:
            return _error(str(exc))
        existing = fetch_one(
            conn,
            """
            SELECT slug, status, settings->>'workspace_path' AS workspace_path,
                   plan_code, settings
            FROM tenants
            WHERE id = %s
            FOR UPDATE
            """,
            (tenant_id,),
        )
        if not existing:
            return _error("Tenant was not found.", 404)
        try:
            data = _tenant_write_payload(
                payload,
                require_slug=False,
                current_settings=existing["settings"],
            )
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT code, name, monthly_price_aud, student_limit, user_limit,
                       storage_limit_mb, showcase_limit, features, is_public,
                       is_recommended
                FROM plans
                WHERE code IN (%s, %s)
                """,
                (existing["plan_code"], data["plan_code"]),
            )
            plan_rows = {row["code"]: row for row in cur.fetchall()}
            target_plan = plan_rows.get(data["plan_code"])
            if not target_plan:
                return _error(f"Plan '{data['plan_code']}' was not found.", 404)
            current_plan = plan_rows.get(existing["plan_code"])
            plan_changed = data["plan_code"] != existing["plan_code"]
            plan_impact = None
            if plan_changed:
                usage_row = fetch_one(
                    conn,
                    """
                    SELECT u.student_count, u.user_count, u.storage_used_mb,
                           COALESCE(showcase.showcase_active_count, 0) AS showcase_active_count
                    FROM tenants t
                    LEFT JOIN tenant_usage u ON u.tenant_id = t.id
                    LEFT JOIN LATERAL (
                        SELECT count(*) FILTER (WHERE COALESCE(item->>'publication_state', 'active') = 'active') AS showcase_active_count
                        FROM jsonb_array_elements(
                            CASE
                                WHEN jsonb_typeof(t.settings->'website_profile'->'showcase_items') = 'array'
                                THEN t.settings->'website_profile'->'showcase_items'
                                ELSE '[]'::jsonb
                            END
                        ) AS item
                    ) showcase ON TRUE
                    WHERE t.id = %s
                    """,
                    (tenant_id,),
                ) or {}
                plan_impact = _plan_change_impact(
                    current_plan or {"code": existing["plan_code"]},
                    target_plan,
                    usage=usage_row,
                )
                if not (
                    payload.get("confirmPlanChange") is True
                    and payload.get("tenantNotificationAcknowledged") is True
                ):
                    return api_error(
                        "Review the plan impact and acknowledge tenant notification before saving.",
                        409,
                        error="plan_change_confirmation_required",
                        details=plan_impact,
                    )
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
            try:
                _ensure_studio_admin_account(conn, tenant_id, data["studio_admin"])
            except ValueError as exc:
                # A rule the operator can act on, not a fault. It has to reach
                # them as its own sentence: this path spent twenty-five days
                # answering "Internal Server Error" to a fixable mistake.
                conn.rollback()
                return _error(str(exc))
            # A date the caller did not mention keeps whatever is stored; one
            # sent as null is cleared. Expressed as a per-column flag rather
            # than by building SQL, so the statement stays one readable
            # literal and the parameters stay bound.
            dates = ("starts_at", "ends_at", "trial_ends_at", "current_period_ends_at")
            keep = {name: data[name] is KEEP for name in dates}
            values = {name: (None if keep[name] else data[name]) for name in dates}
            # What the row will actually hold once this write lands — a kept
            # date is the stored one, so validating only the payload would
            # miss "new trial end, before the start date already on file".
            stored = fetch_one(
                conn,
                "SELECT starts_at, ends_at, trial_ends_at, current_period_ends_at "
                "FROM subscriptions WHERE tenant_id = %s",
                (tenant_id,),
            ) or {}
            effective = {
                name: (stored.get(name) if keep[name] else values[name])
                for name in dates
            }
            try:
                validate_subscription_dates(effective, data["subscription_status"])
            except ValueError as exc:
                conn.rollback()
                return _error(str(exc))
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
                    starts_at = CASE WHEN %s THEN subscriptions.starts_at
                                     ELSE EXCLUDED.starts_at END,
                    ends_at = CASE WHEN %s THEN subscriptions.ends_at
                                   ELSE EXCLUDED.ends_at END,
                    trial_ends_at = CASE WHEN %s THEN subscriptions.trial_ends_at
                                         ELSE EXCLUDED.trial_ends_at END,
                    current_period_ends_at = CASE WHEN %s THEN subscriptions.current_period_ends_at
                                                  ELSE EXCLUDED.current_period_ends_at END,
                    updated_at = now()
                """,
                (
                    tenant_id,
                    data["plan_code"],
                    data["subscription_status"],
                    values["starts_at"],
                    values["ends_at"],
                    values["trial_ends_at"],
                    values["current_period_ends_at"],
                    keep["starts_at"],
                    keep["ends_at"],
                    keep["trial_ends_at"],
                    keep["current_period_ends_at"],
                ),
            )
        _audit(conn, tenant_id=tenant_id, action="tenant.updated", resource_type="tenant", resource_id=tenant_id)
        if plan_changed and plan_impact is not None:
            _audit(
                conn,
                tenant_id=tenant_id,
                action="tenant.plan_changed",
                resource_type="subscription",
                resource_id=tenant_id,
                metadata={
                    "impact": plan_impact,
                    "tenant_notification_acknowledged": True,
                },
            )
        conn.commit()
    return jsonify({"ok": True})


# The reset phrase is the script's, verbatim. One phrase for both entry points
# means an operator who has run this from a terminal already knows it, and it
# cannot drift into two half-remembered variants.
DEMO_RESET_CONFIRMATION = "RESET-LETS-PAINT-SHOWCASE"


@api_v1.route("/admin/tenants/<tenant_id>/demo-reset", methods=["POST"])
@super_admin_required
def reset_demo_tenant(tenant_id: str):
    """Re-seed the demonstration tenant from its content module and manifest.

    Four gates, and the order matters — the cheapest refusal first:

      1. SaaS mode. A customer edition has no demonstration tenant.
      2. The tenant carries ``settings.professional_demo = true``. This is the
         gate that matters: everything below deletes students, schedules and
         media, and the only thing standing between that and a real studio is
         this flag. It is checked HERE as well as inside the script, because a
         guard you cannot see from the call site is a guard you will
         eventually route around.
      3. The confirmation phrase, typed by the operator.
      4. The demonstration password must be configured. Without it the reset
         cannot set the staff logins, and a half-reset tenant is worse than an
         untouched one.

    Synchronous on purpose. It takes a few seconds — the images go in through
    the real upload path — and an operator who pressed a button that says
    "reset" should be told what happened, not handed a job id.
    """

    if is_standalone():
        return _error("The demonstration tenant exists only in SaaS mode.", 400)

    payload = _json_payload()
    with connect() as conn:
        row = fetch_one(
            conn,
            "SELECT slug, COALESCE((settings->>'professional_demo')::boolean, false) AS is_demo "
            "FROM tenants WHERE id = %s",
            (tenant_id,),
        )
    if not row:
        return _error("Tenant was not found.", 404)
    if not row["is_demo"]:
        return _error(
            "This tenant is not a demonstration tenant. Reset is refused.", 400
        )
    if str(payload.get("confirm") or "").strip() != DEMO_RESET_CONFIRMATION:
        return _error(f"Type {DEMO_RESET_CONFIRMATION} to confirm.", 400)
    if len(os.environ.get("STUDIOSAAS_SHARED_DEMO_PASSWORD", "")) < 12:
        return _error(
            "STUDIOSAAS_SHARED_DEMO_PASSWORD is not configured on this instance, "
            "so the demonstration logins cannot be set. Add it to the environment "
            "and try again.",
            400,
        )

    # Imported here, not at module scope: the seeder pulls in Pillow and the
    # content module, and a web process that never resets a demo should not pay
    # for either at start-up.
    scripts = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from reset_professional_demo import _credentials_path, reset_showcase
    except Exception:
        current_app.logger.exception("demo reset seeder is unavailable")
        return _error("The demonstration seeder is not available in this build.", 500)

    started = time.monotonic()
    try:
        result = reset_showcase(_credentials_path(None))
    except Exception as exc:
        current_app.logger.exception("demo reset failed")
        return _error(f"Reset failed: {exc}", 500)
    seconds = round(time.monotonic() - started, 1)

    actor = getattr(g, "actor", None)
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    tenant_id, actor_user_id, action, resource_type, resource_id, metadata
                )
                VALUES (%s, %s, 'demo_tenant.reset', 'tenant', %s, %s::jsonb)
                """,
                (
                    tenant_id,
                    getattr(actor, "user_id", None),
                    tenant_id,
                    json.dumps({
                        "slug": row["slug"],
                        "seconds": seconds,
                        "studio_works": result.get("studio_works"),
                        "student_works": result.get("student_works"),
                        "students": result.get("students"),
                        "from": "platform_admin",
                    }),
                ),
            )
        conn.commit()

    # The credential file path is returned; its contents never are.
    return jsonify({
        "ok": True,
        "slug": row["slug"],
        "seconds": seconds,
        "students": result.get("students"),
        "studioWorks": result.get("studio_works"),
        "studentWorks": result.get("student_works"),
        "publicStudentWorks": result.get("student_works_public"),
        "roomPhotos": result.get("room_photos"),
        "categories": result.get("categories"),
        "credentialsFile": result.get("credentials_file"),
    })


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
    """Exit support mode. Allowed for any logged-in session that has one.

    Deliberately NOT @auth_required: clearing the support key must still work
    for a session whose membership was deactivated mid-support (or whose
    target tenant was archived) — otherwise the stuck banner can never be
    dismissed. The only mutation is popping the caller's own session key.
    """

    from flask import session as _fs
    if "user_id" not in _fs:
        return _error("Authentication required. Please log in.", 401)
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


@api_v1.route("/admin/subscriptions/settlement", methods=["GET"])
@super_admin_required
def subscription_settlement():
    """What the subscription dates say has already happened.

    Read-only, and that is the point. Nothing in this product read a
    subscription date and compared it to today until this existed: a trial
    could end, a billing period could lapse and a cancellation date could pass
    with the studio keeping every feature and the console showing green.

    Reporting first, deliberately. A studio losing access because a job ran
    overnight is a support incident and a broken promise; an operator seeing
    "three subscriptions passed a date" is a morning's work.
    """

    with connect() as conn:
        rows = fetch_all(conn, SETTLEMENT_QUERY, ())
    return jsonify(settlement_report([dict(row) for row in rows]))


@api_v1.route("/admin/subscriptions/settlement/apply", methods=["POST"])
@super_admin_required
def apply_subscription_settlement():
    """Perform the transitions that have exactly one defensible answer.

    Only findings the report marked `actionable` — a cancellation date that
    has passed, or a billing period that lapsed on an active subscription.
    A lapsed trial is never in that set: `trial -> past_due` is not a legal
    tenant transition, and "did they buy?" is a commercial question, not a
    scheduling one.

    Each move goes through the same `validate_tenant_transition` the manual
    route uses and writes its own audit row, so an automatic change is as
    traceable as an operator's. Re-running is safe: the findings are derived
    from current state, so a row that has been settled produces none.
    """

    payload = {}
    try:
        payload = _json_payload()
    except ValueError:
        pass
    # Default to a rehearsal. Applying is the argument you have to make.
    apply_changes = bool(payload.get("apply") is True)

    with connect() as conn:
        rows = fetch_all(conn, SETTLEMENT_QUERY, ())
        report = settlement_report([dict(row) for row in rows])
        planned = [f for f in report["findings"] if f["category"] == SETTLEMENT_ACTIONABLE and f["target"]]
        applied, skipped = [], []
        if apply_changes:
            with conn.cursor() as cur:
                for finding in planned:
                    tenant_status, subscription_status = finding["target"]
                    try:
                        validate_tenant_transition(finding["tenant_status"], tenant_status)
                        validate_tenant_subscription_pair(tenant_status, subscription_status)
                    except ValueError as exc:
                        skipped.append({**finding, "reason": str(exc)})
                        continue
                    cur.execute(
                        "UPDATE tenants SET status = %s, updated_at = now() WHERE id = %s",
                        (tenant_status, finding["tenant_id"]),
                    )
                    cur.execute(
                        "UPDATE subscriptions SET status = %s, updated_at = now() WHERE tenant_id = %s",
                        (subscription_status, finding["tenant_id"]),
                    )
                    _audit(
                        conn,
                        tenant_id=finding["tenant_id"],
                        action="subscription.settled",
                        resource_type="subscription",
                        resource_id=finding["tenant_id"],
                        metadata={
                            "finding": finding["kind"],
                            "days_past": finding["days"],
                            "from": [finding["tenant_status"], finding["subscription_status"]],
                            "to": [tenant_status, subscription_status],
                        },
                    )
                    applied.append(finding)
            conn.commit()
    return jsonify({
        "ok": True,
        "applied": apply_changes,
        "as_of": report["as_of"],
        "planned": planned,
        "changed": applied,
        "skipped": skipped,
        "counts": report["counts"],
    })


# A studio may change its public address once a year. The limit is a product
# rule with no override in the interface: an operator who genuinely must break
# it can set `slug_changed_at` directly, and making the exception leave the
# product is what stops the exception becoming the habit.
SLUG_CHANGE_COOLDOWN_DAYS = 365


def _slug_change_impact(current_slug: str, new_slug: str, next_allowed_at) -> dict:
    """What the operator is agreeing to, in the shape the plan editor uses."""

    return {
        "currentSlug": current_slug,
        "newSlug": new_slug,
        "nextAllowedAt": next_allowed_at,
        "keepsWorking": [
            "The old address redirects to the new one permanently, so printed QR codes do not need reprinting.",
            "Students, courses, work, schedules and media are untouched.",
            "Signed-in staff are not logged out.",
        ],
        "breaks": [
            "Search engines take a few weeks to show the new address.",
            "Visitors' saved language preference resets once.",
            "This studio cannot change its address again until the date above.",
        ],
    }


@api_v1.route("/admin/tenants/<tenant_id>/slug", methods=["PATCH"])
@super_admin_required
def update_tenant_slug(tenant_id: str):
    """Change one studio's public address, keeping the old one alive forever.

    Its own endpoint rather than a field on the tenant editor, because its
    blast radius is nothing like a contact email's: the address is on flyers,
    in QR codes and in search results. Mixing it into a form that is saved
    routinely is how it would eventually be changed by accident.
    """

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    new_slug = _clean_text(payload, "slug").lower()
    try:
        validate_tenant_slug(new_slug)
    except WorkspaceError as exc:
        return api_error(str(exc), 400, error="invalid_slug")

    with connect() as conn:
        tenant = fetch_one(
            conn,
            "SELECT id, name, slug, status, slug_changed_at, settings FROM tenants WHERE id = %s",
            (tenant_id,),
        )
        if not tenant:
            return api_error("Tenant not found.", 404, error="not_found")
        current_slug = str(tenant["slug"])
        if new_slug == current_slug:
            return api_error("That is already this studio's address.", 400, error="slug_unchanged")
        if tenant["status"] not in ("trial", "onboarding", "active", "past_due"):
            return api_error(
                "Only an active studio can change its address.", 409, error="tenant_not_active")
        # Every address ever issued is in this table, including the tombstones
        # of deleted studios. An address is never reissued: doing so would
        # redirect a closed studio's printed QR codes into somebody else's.
        taken = fetch_one(
            conn, "SELECT tenant_id FROM tenant_slug_aliases WHERE slug = %s", (new_slug,))
        if taken:
            return api_error(
                "That address has been used before and cannot be reissued.",
                409, error="slug_taken")

        changed_at = tenant["slug_changed_at"]
        next_allowed_at = (
            changed_at + _timedelta(days=SLUG_CHANGE_COOLDOWN_DAYS) if changed_at else None
        )
        if next_allowed_at and next_allowed_at > _datetime.now(_timezone.utc):
            return api_error(
                "This studio changed its address within the last year.",
                409,
                error="slug_change_cooldown",
                details=_slug_change_impact(current_slug, new_slug, next_allowed_at),
            )

        if not (payload.get("confirmSlugChange") is True
                and payload.get("tenantNotificationAcknowledged") is True):
            return api_error(
                "Review what changes and acknowledge tenant notification before saving.",
                409,
                error="slug_change_confirmation_required",
                details=_slug_change_impact(
                    current_slug, new_slug,
                    _datetime.now(_timezone.utc) + _timedelta(days=SLUG_CHANGE_COOLDOWN_DAYS)),
            )

        # The filesystem and Postgres cannot share a transaction, so the order
        # is chosen to make every failure point safe rather than to make
        # failure unlikely. Copy first: if the commit below fails, the copy is
        # removed and the studio's site never noticed.
        project_root = current_app.config["PROJECT_ROOT"]
        try:
            copy_tenant_workspace(project_root, current_slug, new_slug)
        except WorkspaceError as exc:
            return api_error(str(exc), 409, error="workspace_copy_failed")

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE tenant_slug_aliases
                    SET is_current = false, retired_at = now()
                    WHERE tenant_id = %s AND is_current
                    """,
                    (tenant_id,),
                )
                cur.execute(
                    """
                    INSERT INTO tenant_slug_aliases (slug, tenant_id, is_current)
                    VALUES (%s, %s, true)
                    """,
                    (new_slug, tenant_id),
                )
                settings = dict(tenant["settings"] or {})
                settings["workspace_path"] = f"tenants/{new_slug}"
                cur.execute(
                    """
                    UPDATE tenants
                    SET slug = %s, slug_changed_at = now(), settings = %s::jsonb, updated_at = now()
                    WHERE id = %s
                    """,
                    (new_slug, json.dumps(settings), tenant_id),
                )
            _audit_request(
                conn,
                tenant_id=tenant_id,
                action="tenant.slug_changed",
                resource_type="tenant",
                resource_id=tenant_id,
                metadata={"from": current_slug, "to": new_slug},
            )
            conn.commit()
        except Exception:
            conn.rollback()
            discard_tenant_workspace(project_root, new_slug)
            raise

    # After the commit. The copied files still carry the old slug in every
    # link, so this is what actually finishes the move — and if it fails, the
    # site is live at the new address with stale internal links rather than
    # not live at all.
    _refresh_tenant_workspace(new_slug, str(tenant["name"]), dict(tenant["settings"] or {}))
    # The old directory is deliberately left in place. It is the one
    # irreversible step, it is no longer routed to, and a later sweep removes
    # any workspace whose slug is a retired alias.
    forget_retired_addresses()
    return jsonify({
        "ok": True,
        "slug": new_slug,
        "previousSlug": current_slug,
        "nextAllowedAt": _datetime.now(_timezone.utc) + _timedelta(days=SLUG_CHANGE_COOLDOWN_DAYS),
    })


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
            SELECT a.id, a.action, a.resource_type, a.resource_id, a.metadata,
                   a.created_at, u.email AS actor_email, t.slug AS tenant_slug
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.actor_user_id
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


def _resolve_credit_movement(
    tx_type: str, legacy_type: str, amount: float, fee_cents: int
) -> tuple[str, float, int, bool]:
    """Map the client (transactionType, legacy_type) pair to the signed movement.

    Returns ``(schema_type, delta, fee_cents, requires_balance_check)``. The
    ledger stores the SIGNED movement so exports and the CMS log view are
    self-describing (adjustment_out / refund_out are negative).

    v7.6.0: a bare ``refund`` (no legacy_type) is normalised to the same
    semantics as the legacy ``refund_out`` alias — credits leave the account,
    the refunded money is a NEGATIVE fee so revenue sums net out, and the
    balance check applies. Before this a bare refund ADDED credits and kept
    the fee positive, the exact opposite of refund_out, silently polluting
    the cash_net roll-up. No shipped client ever sent it (the admin UI always
    sends refund_out), so there is no compatibility surface to preserve.
    """

    # Determine delta from the schema type first (legacy aliases override below).
    if tx_type in ("consume", "expire"):
        delta = -amount
    else:
        # purchase / adjustment / migration / refund keep the caller's sign
        # (for adjustment and migration the sign of amount is the direction).
        delta = amount

    requires_balance_check = False
    if legacy_type == "debit":
        tx_type = "consume"
    elif legacy_type == "adjustment_in":
        tx_type = "adjustment"
    elif legacy_type == "adjustment_out":
        tx_type = "adjustment"
        delta = -abs(delta)  # negative adjustment
    elif legacy_type == "refund_out" or (tx_type == "refund" and not legacy_type):
        # A2 (v5.3/v5.5 harvest): 退款退课 — credits leave the account and
        # the refunded money is a NEGATIVE fee so revenue sums net out.
        tx_type = "refund"
        delta = -abs(delta)
        fee_cents = -abs(fee_cents)
        requires_balance_check = True
    return tx_type, delta, fee_cents, requires_balance_check


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

        # Refunds move real money out (negative fee) and reduce reported
        # revenue, so they sit behind credits:refund (owner/manager) instead
        # of the routine credits:write held by front-desk and staff.
        if tx_type == "refund" or legacy_type == "refund_out":
            try:
                require_permission(g.actor, "credits:refund")
            except PermissionDeniedError:
                return _error("退款需要店长或负责人权限。 Refunds require an owner or manager.", 403)

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

        # Determine the signed movement (schema: purchase, consume, adjustment,
        # refund, expire, migration) and map legacy client aliases.
        tx_type, delta, fee_cents, requires_balance_check = _resolve_credit_movement(
            tx_type, legacy_type, amount, fee_cents
        )
        if requires_balance_check and abs(delta) > current_balance:
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


def _class_time(value) -> str | None:
    """Validate an HH:MM wall-clock slot, or None when it is not set.

    Empty string and None both mean "not set" — the roster is allowed to carry
    a student whose time nobody has decided yet, and that has to stay
    distinguishable from a guessed default.
    """

    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    parts = text.split(":")
    if len(parts) < 2 or len(parts) > 3:
        raise ValueError("classTime must be HH:MM.")
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError as exc:
        raise ValueError("classTime must be HH:MM.") from exc
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("classTime must be a real time between 00:00 and 23:59.")
    return f"{hour:02d}:{minute:02d}"


def _daily_roster_for_date(conn, tenant_id: str, roster_date: _date) -> dict:
    """Return explicit entries plus the recurring schedule preview for a date."""

    entries = fetch_all(
        conn,
        """
        SELECT dre.id, dre.student_id, s.display_name AS student_name,
               dre.source, dre.status, dre.note, dre.cancelled_at,
               to_char(dre.class_time, 'HH24:MI') AS class_time,
               dre.one_to_one,
               dre.created_at, dre.updated_at
        FROM daily_roster_entries dre
        JOIN students s
          ON s.tenant_id = dre.tenant_id AND s.id = dre.student_id
        WHERE dre.tenant_id = %s AND dre.roster_date = %s
        -- NULLS LAST keeps "time not set" at the bottom of the day rather than
        -- at the top, where it would read as the earliest slot.
        ORDER BY dre.status = 'cancelled', dre.class_time ASC NULLS LAST,
                 lower(s.display_name), dre.created_at
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
            "classTime": row["class_time"],
            "oneToOne": bool(row["one_to_one"]),
            "cancelledAt": row["cancelled_at"].isoformat() if row["cancelled_at"] else None,
            "createdAt": row["created_at"].isoformat(),
            "updatedAt": row["updated_at"].isoformat(),
        }
        normalized_entries.append(item)
        student_id = str(row["student_id"])
        if row["status"] == "cancelled":
            # An explicit cancellation overrides inherited weekly membership for
            # this date, while normalized_entries keeps the skipped explanation.
            effective.pop(student_id, None)
        else:
            effective[student_id] = {
                "studentId": str(row["student_id"]),
                "studentName": row["student_name"],
                "source": row["source"],
                "entryId": str(row["id"]),
                "status": row["status"],
                # The roster UI renders from effectiveStudents, so the slot has
                # to travel here too — carrying it only on `entries` is what
                # made the first version of this read back as null.
                "classTime": row["class_time"],
                "oneToOne": bool(row["one_to_one"]),
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
    try:
        class_time = _class_time(payload.get("classTime", payload.get("class_time")))
    except ValueError as exc:
        return _error(str(exc))
    one_to_one = bool(payload.get("oneToOne", payload.get("one_to_one", False)))

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
                        note, class_time, one_to_one, created_by_user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s::time, %s, %s)
                    ON CONFLICT (tenant_id, roster_date, student_id) DO UPDATE
                    SET source = EXCLUDED.source,
                        status = EXCLUDED.status,
                        status_before_cancel = NULL,
                        note = EXCLUDED.note,
                        -- Re-adding a student without naming a time must not
                        -- erase the slot someone already set for them.
                        class_time = COALESCE(EXCLUDED.class_time, daily_roster_entries.class_time),
                        one_to_one = EXCLUDED.one_to_one,
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
                        class_time,
                        one_to_one,
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
            metadata={
                "date": roster_date.isoformat(),
                "students": student_ids,
                "source": source,
                "classTime": class_time or "",
                "oneToOne": one_to_one,
            },
        )
        conn.commit()
        roster = _daily_roster_for_date(conn, tenant.tenant_id, roster_date)
    return jsonify({"ok": True, "entryIds": entry_ids, "roster": roster}), 201


@api_v1.route("/daily-roster/<entry_id>", methods=["PATCH"])
@permission_required("attendance:write")
def update_daily_roster_entry(entry_id: str):
    """Change one active roster entry's slot, status, or one-to-one flag.

    Separate from the add route because this is the correction path: the front
    desk moves a student from 10:00 to 17:00 without re-adding them, which
    would otherwise reset source and status.  Cancellation deliberately stays
    on the DELETE/undo pair so a status edit cannot bypass its audit trail.
    """

    payload = request.get_json(silent=True) or {}
    updates: list[str] = []
    params: list = []
    if "classTime" in payload or "class_time" in payload:
        try:
            class_time = _class_time(payload.get("classTime", payload.get("class_time")))
        except ValueError as exc:
            return _error(str(exc))
        updates.append("class_time = %s::time")
        params.append(class_time)
    if "oneToOne" in payload or "one_to_one" in payload:
        updates.append("one_to_one = %s")
        params.append(bool(payload.get("oneToOne", payload.get("one_to_one"))))
    if "status" in payload:
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"scheduled", "makeup"}:
            return _error("status must be scheduled or makeup.")
        updates.append("status = %s")
        params.append(status)
    if not updates:
        return _error("Provide classTime, oneToOne, or status.")

    try:
        entry_uuid = str(_uuid.UUID(str(entry_id)))
    except (ValueError, TypeError, AttributeError):
        return _error("entry_id must be a valid UUID.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            f"""
            UPDATE daily_roster_entries
               SET {', '.join(updates)}, updated_at = now()
             WHERE tenant_id = %s AND id = %s AND status <> 'cancelled'
            RETURNING roster_date, student_id,
                      to_char(class_time, 'HH24:MI') AS class_time, one_to_one,
                      status
            """,
            (*params, tenant.tenant_id, entry_uuid),
        )
        if not row:
            return _error("Roster entry was not found in this tenant.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="daily_roster.updated",
            resource_type="daily_roster",
            resource_id=entry_uuid,
            metadata={
                "date": row["roster_date"].isoformat(),
                "classTime": row["class_time"] or "",
                "oneToOne": bool(row["one_to_one"]),
                "status": row["status"],
            },
        )
        conn.commit()
        roster = _daily_roster_for_date(conn, tenant.tenant_id, row["roster_date"])
    return jsonify({"ok": True, "roster": roster})


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

def _optional_reference(payload, *keys: str) -> str | None:
    """Read an optional uuid reference, where empty deliberately means "none".

    "" and null are the same answer — a class with no teacher assigned yet —
    and both have to reach the database as NULL rather than as a string that
    fails a foreign key. Anything present but unparseable is a client bug, and
    saying so is better than storing None and calling it success.
    """

    for key in keys:
        if key in payload:
            raw = str(payload.get(key) or "").strip()
            if not raw:
                return None
            try:
                return str(_uuid.UUID(raw))
            except (ValueError, AttributeError):
                raise ValueError(f"{key} must be an id or empty.")
    return None


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
    # v8.8.0 — what a class needs before it can face the public.
    #
    # `is_public` defaults to FALSE on the way in as well as in the column. A
    # payload that forgets the field must not publish the class: the safe
    # reading of silence is "no".
    return {
        "label": label,
        "weekday": weekday,
        "start_time": start_time,
        "duration": duration,
        "capacity": capacity,
        "student_ids": student_ids,
        "course_id": _optional_reference(payload, "courseId", "course_id"),
        "teacher_user_id": _optional_reference(payload, "teacherUserId", "teacher_user_id"),
        "is_public": _bool_from_json(payload, "isPublic", "is_public", default=False),
        "room": _clean_text(payload, "room")[:80],
    }


def _assert_schedule_references(conn, tenant_id, fields) -> None:
    """Both references must belong to THIS tenant.

    A foreign key only proves the row exists somewhere. Without this check a
    tenant could name another studio's course or another studio's teacher on
    its own class, and — once v8.9.0 renders it — publish that name on its
    public page. The database cannot catch it; this is the only place that can.
    """

    course_id = fields.get("course_id")
    if course_id:
        found = fetch_one(
            conn,
            "SELECT id FROM courses WHERE tenant_id = %s AND id = %s",
            (tenant_id, course_id),
        )
        if not found:
            raise ValueError("That course does not belong to this studio.")
    teacher_id = fields.get("teacher_user_id")
    if teacher_id:
        found = fetch_one(
            conn,
            """
            SELECT user_id FROM memberships
            WHERE tenant_id = %s AND user_id = %s AND status = 'active' AND role <> 'parent'
            """,
            (tenant_id, teacher_id),
        )
        if not found:
            raise ValueError("That teacher is not an active member of this studio's team.")


def _replace_schedule_students(cur, tenant_id, schedule_id, student_ids) -> int:
    """Replace a schedule's roster; only same-tenant students are accepted."""

    cur.execute(
        "DELETE FROM class_schedule_students WHERE tenant_id = %s AND schedule_id = %s",
        (tenant_id, schedule_id),
    )
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
               c.name AS course_name, cs.course_id, c.age_range,
               cs.teacher_user_id, cs.is_public, cs.room,
               u.full_name AS teacher_name,
               COALESCE(NULLIF(m.public_display_name, ''), u.full_name) AS teacher_public_name,
               COALESCE(m.show_on_public_timetable, false) AS teacher_public
        FROM class_schedules cs
        LEFT JOIN courses c ON c.id = cs.course_id
        LEFT JOIN users u ON u.id = cs.teacher_user_id
        LEFT JOIN memberships m
               ON m.user_id = cs.teacher_user_id AND m.tenant_id = cs.tenant_id
        WHERE cs.tenant_id = %s AND cs.is_active
        ORDER BY cs.weekday, cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    # Cancellations from today onward. Past ones are history the CMS has no
    # room for and the public page will never reach.
    exceptions = fetch_all(
        conn,
        """
        SELECT schedule_id, to_char(on_date, 'YYYY-MM-DD') AS on_date, note
        FROM class_schedule_exceptions
        WHERE tenant_id = %s AND cancelled AND on_date >= (now() AT TIME ZONE 'UTC')::date - 1
        ORDER BY on_date
        """,
        (tenant_id,),
    )
    cancelled: dict[str, list[dict]] = {}
    for row in exceptions:
        cancelled.setdefault(str(row["schedule_id"]), []).append(
            {"date": row["on_date"], "note": row["note"]}
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
            "ageRange": r["age_range"] or "",
            "room": r["room"],
            "isPublic": bool(r["is_public"]),
            "teacherUserId": str(r["teacher_user_id"]) if r["teacher_user_id"] else None,
            # Two names, because they answer two questions. `teacherName` is
            # for the roster — the studio's own staff list, where the legal
            # name is the useful one. `teacherPublicName` is what the portal
            # would print, and `teacherIsPublic` is whether it may. The CMS
            # shows the second pair so an owner can see what a visitor sees
            # before anything is published.
            "teacherName": r["teacher_name"] or "",
            "teacherPublicName": r["teacher_public_name"] or "",
            "teacherIsPublic": bool(r["teacher_public"]),
            "cancellations": cancelled.get(str(r["id"]), []),
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


def _calendar_tenant_row(conn, tenant_id: str):
    """Read the tenant identity fields every calendar export needs."""

    return fetch_one(
        conn,
        """
        SELECT name, slug, timezone, address
        FROM tenants
        WHERE id = %s
        """,
        (tenant_id,),
    )


_CALENDAR_REVISION_RE = re.compile(r"^[0-9a-f]{64}$")


def _calendar_revision_error(document: CalendarDocument):
    """Validate that download is bound to the exact document previewed."""

    revision = str(request.args.get("revision") or "").strip()
    if not _CALENDAR_REVISION_RE.fullmatch(revision):
        return api_error(
            "revision must be a 64-character lowercase SHA-256 value.",
            400,
            error="invalid_calendar_revision",
        )
    if not secrets.compare_digest(revision, document.revision):
        return api_error(
            "Calendar data changed after preview. Preview it again before downloading.",
            409,
            error="calendar_revision_conflict",
        )
    return None


def _calendar_download_response(document: CalendarDocument):
    """Return one revision-checked CalendarDocument as a safe attachment."""

    revision_error = _calendar_revision_error(document)
    if revision_error is not None:
        return revision_error
    filename = document.filename
    if (
        not filename.endswith(".ics")
        or filename != PurePath(filename).name
        or any(ord(character) < 32 or ord(character) == 127 for character in filename)
        or any(character in filename for character in ('"', "'", "\\", "/", ";"))
    ):
        return api_error(
            "Calendar filename is not safe for download.",
            500,
            error="invalid_calendar_filename",
        )
    ascii_filename = filename.encode("ascii", "ignore").decode("ascii")
    if not ascii_filename or ascii_filename == ".ics":
        ascii_filename = "calendar.ics"
    response = Response(document.to_ics(), content_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = (
        f'attachment; filename="{ascii_filename}"; '
        f"filename*=UTF-8''{quote(filename, safe='')}"
    )
    response.headers["Cache-Control"] = "private, no-store"
    return response


def _schedule_calendar_document(conn, tenant_id: str) -> CalendarDocument | None:
    """Build the recurring class calendar. No roster or student data enters it."""

    tenant_row = _calendar_tenant_row(conn, tenant_id)
    if not tenant_row:
        return None
    schedules = fetch_all(
        conn,
        """
        SELECT cs.id, cs.label, cs.weekday,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               cs.duration_minutes, COALESCE(c.name, '') AS course_name
        FROM class_schedules cs
        LEFT JOIN courses c
          ON c.tenant_id = cs.tenant_id AND c.id = cs.course_id
        WHERE cs.tenant_id = %s AND cs.is_active
        ORDER BY cs.weekday, cs.start_time, lower(cs.label)
        """,
        (tenant_id,),
    )
    return build_schedule_document(
        tenant_name=tenant_row["name"],
        tenant_slug=tenant_row["slug"],
        timezone_name=_validated_timezone(tenant_row["timezone"]),
        location=tenant_row["address"] or "",
        schedules=schedules,
    )


def _roster_calendar_document(conn, tenant_id: str, roster_date: _date) -> CalendarDocument | None:
    """Build a one-day roster snapshot, student names included.

    The slot comes from the explicit roster entry when the front desk set one,
    and otherwise from the recurring schedule the student belongs to — both are
    recorded facts. A student with neither is reported as skipped rather than
    given an invented time, matching migration 0022.
    """

    tenant_row = _calendar_tenant_row(conn, tenant_id)
    if not tenant_row:
        return None
    roster = _daily_roster_for_date(conn, tenant_id, roster_date)
    slot_durations: dict[str, int] = {}
    schedule_by_id: dict[str, dict] = {}
    for schedule in roster["schedules"]:
        schedule_by_id[schedule["id"]] = schedule
        start = schedule.get("startTime")
        duration = schedule.get("durationMinutes")
        if start and duration:
            slot_durations.setdefault(start, int(duration))

    entries: list[dict] = []
    for student in roster["effectiveStudents"]:
        slot = student.get("classTime")
        if not slot:
            for schedule_id in student.get("scheduleIds") or []:
                candidate = schedule_by_id.get(schedule_id, {}).get("startTime")
                if candidate:
                    slot = candidate
                    break
        entries.append(
            {
                "studentId": student.get("studentId"),
                "studentName": student.get("studentName"),
                "classTime": slot,
                "oneToOne": bool(student.get("oneToOne")),
            }
        )
    # Cancelled students never reach effectiveStudents, but the dialog should be
    # able to say "2 cancelled" instead of quietly showing a shorter list.
    entries.extend(
        {
            "studentId": entry.get("studentId"),
            "studentName": entry.get("studentName"),
            "status": "cancelled",
        }
        for entry in roster["entries"]
        if entry.get("status") == "cancelled"
    )
    return build_roster_document(
        tenant_name=tenant_row["name"],
        tenant_slug=tenant_row["slug"],
        timezone_name=_validated_timezone(tenant_row["timezone"]),
        location=tenant_row["address"] or "",
        roster_date=roster_date,
        entries=entries,
        slot_durations=slot_durations,
    )


@api_v1.route("/class-schedules/calendar", methods=["GET"])
@auth_required
def preview_class_schedule_calendar():
    """Preview the recurring class calendar before downloading it.

    The preview is rendered from the same CalendarDocument the .ics route
    serializes, so the event count shown can never disagree with the file.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _schedule_calendar_document(conn, tenant.tenant_id)
    if document is None:
        return _error("Tenant not found.", 404)
    return jsonify({"calendar": document.to_preview()})


@api_v1.route("/class-schedules/calendar.ics", methods=["GET"])
@auth_required
def download_class_schedule_calendar():
    """Download a tenant schedule calendar without roster or student data."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _schedule_calendar_document(conn, tenant.tenant_id)
    if document is None:
        return _error("Tenant not found.", 404)
    return _calendar_download_response(document)


@api_v1.route("/daily-roster/calendar", methods=["GET"])
@permission_required("data:export")
def preview_daily_roster_calendar():
    """Preview one day's roster calendar, including the attending students.

    Gated on data:export rather than attendance:read: this file carries student
    names out of the system and into somebody's personal calendar, which is a
    narrower decision than being allowed to read the roster on screen.
    """

    try:
        roster_date = _roster_date(request.args.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _roster_calendar_document(conn, tenant.tenant_id, roster_date)
    if document is None:
        return _error("Tenant not found.", 404)
    return jsonify({"calendar": document.to_preview()})


@api_v1.route("/daily-roster/calendar.ics", methods=["GET"])
@permission_required("data:export")
def download_daily_roster_calendar():
    """Download one day's roster snapshot as an .ics file."""

    try:
        roster_date = _roster_date(request.args.get("date"))
    except ValueError as exc:
        return _error(str(exc))
    with connect() as conn:
        tenant = _tenant_context(conn)
        document = _roster_calendar_document(conn, tenant.tenant_id, roster_date)
    if document is None:
        return _error("Tenant not found.", 404)
    return _calendar_download_response(document)


@api_v1.route("/class-schedules", methods=["POST"])
@tenant_admin_required
def create_class_schedule():
    """Create a weekly class schedule (optionally with an initial roster)."""

    payload = _json_payload()
    try:
        fields = _schedule_payload_fields(payload)
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _assert_schedule_references(conn, tenant.tenant_id, fields)
        except ValueError as exc:
            return _error(str(exc))
        row = fetch_one(
            conn,
            """
            INSERT INTO class_schedules (tenant_id, label, weekday, start_time, duration_minutes,
                                         capacity, course_id, teacher_user_id, is_public, room)
            VALUES (%s, %s, %s, %s::time, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (tenant.tenant_id, fields["label"], fields["weekday"], fields["start_time"],
             fields["duration"], fields["capacity"], fields["course_id"],
             fields["teacher_user_id"], fields["is_public"], fields["room"]),
        )
        schedule_id = str(row["id"])
        with conn.cursor() as cur:
            added = _replace_schedule_students(cur, tenant.tenant_id, schedule_id, fields["student_ids"])
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.created",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": fields["label"], "weekday": fields["weekday"],
                      "startTime": fields["start_time"], "students": added,
                      "isPublic": fields["is_public"]},
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
                   duration_minutes, capacity, course_id, teacher_user_id, is_public, room
            FROM class_schedules
            WHERE tenant_id = %s AND id = %s AND is_active
            """,
            (tenant.tenant_id, schedule_id),
        )
        if not existing:
            return _error("Schedule not found.", 404)
        # PATCH means "change what I sent". Every field the caller omitted is
        # re-supplied from the stored row, including the four v8.8.0 ones —
        # rebuilding from the payload alone is how a save that meant to change
        # the capacity also unpublishes the class and forgets its teacher.
        merged = {
            "label": payload.get("label", existing["label"]),
            "weekday": payload.get("weekday", existing["weekday"]),
            "startTime": payload.get("startTime", payload.get("start_time", existing["start_time"])),
            "durationMinutes": payload.get("durationMinutes", payload.get("duration_minutes", existing["duration_minutes"])),
            "capacity": payload.get("capacity", existing["capacity"]),
            "studentIds": payload.get("studentIds", payload.get("student_ids")),
            "courseId": payload.get("courseId", payload.get("course_id", existing["course_id"])),
            "teacherUserId": payload.get(
                "teacherUserId", payload.get("teacher_user_id", existing["teacher_user_id"])),
            "isPublic": payload.get("isPublic", payload.get("is_public", existing["is_public"])),
            "room": payload.get("room", existing["room"]),
        }
        try:
            fields = _schedule_payload_fields(merged)
            _assert_schedule_references(conn, tenant.tenant_id, fields)
        except ValueError as exc:
            return _error(str(exc))
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE class_schedules
                SET label = %s, weekday = %s, start_time = %s::time,
                    duration_minutes = %s, capacity = %s, course_id = %s,
                    teacher_user_id = %s, is_public = %s, room = %s, updated_at = now()
                WHERE tenant_id = %s AND id = %s
                """,
                (fields["label"], fields["weekday"], fields["start_time"], fields["duration"],
                 fields["capacity"], fields["course_id"], fields["teacher_user_id"],
                 fields["is_public"], fields["room"], tenant.tenant_id, schedule_id),
            )
            if fields["student_ids"] is not None:
                _replace_schedule_students(cur, tenant.tenant_id, schedule_id, fields["student_ids"])
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.updated",
            resource_type="class_schedule",
            resource_id=schedule_id,
            metadata={"label": fields["label"], "weekday": fields["weekday"],
                      "isPublic": fields["is_public"]},
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
# v8.8.0: one-off cancellations of a recurring class
#
# `class_schedules` is a rule ("every Wednesday") with no way to say "not this
# Wednesday". Nothing else in the schema can: daily_roster_entries carries a
# 'cancelled' status but per STUDENT, which answers a different question.
#
# The public timetable cannot ship without this, and that is not a preference:
# a recurring class the studio cannot withdraw for one week is a promise made
# to a parent who then drives across town. A timetable that cannot be corrected
# is worse than no timetable.
# ──────────────────────────────────────────────

@api_v1.route("/class-schedules/<schedule_id>/cancellations", methods=["POST"])
@tenant_admin_required
def cancel_class_occurrence(schedule_id: str):
    """Mark one dated occurrence of a recurring class as not running."""

    payload = _json_payload()
    try:
        parsed_id = str(_uuid.UUID(schedule_id))
    except (ValueError, AttributeError):
        return _error("Invalid schedule id.")
    try:
        on_date = _roster_date(payload.get("date", payload.get("on_date")))
    except ValueError as exc:
        return _error(str(exc))
    note = _clean_text(payload, "note")[:120]

    with connect() as conn:
        tenant = _tenant_context(conn)
        schedule = fetch_one(
            conn,
            "SELECT id, label, weekday FROM class_schedules "
            "WHERE tenant_id = %s AND id = %s AND is_active",
            (tenant.tenant_id, parsed_id),
        )
        if not schedule:
            return _error("Schedule not found.", 404)
        # The date has to fall on the day this class actually runs, or the
        # cancellation is silently inert: it is stored, it looks saved, and the
        # class keeps appearing. Refusing is the only way the owner finds out.
        if on_date.isoweekday() % 7 != int(schedule["weekday"]):
            return _error("That date is not the weekday this class runs on.")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO class_schedule_exceptions
                    (schedule_id, tenant_id, on_date, cancelled, note, created_by_user_id)
                VALUES (%s, %s, %s, true, %s, %s)
                ON CONFLICT (schedule_id, on_date)
                DO UPDATE SET cancelled = true, note = EXCLUDED.note
                """,
                (parsed_id, tenant.tenant_id, on_date, note,
                 getattr(getattr(g, "actor", None), "user_id", None)),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.cancelled",
            resource_type="class_schedule",
            resource_id=parsed_id,
            metadata={"label": schedule["label"], "date": on_date.isoformat(), "note": note},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})


@api_v1.route("/class-schedules/<schedule_id>/cancellations/<on_date>", methods=["DELETE"])
@tenant_admin_required
def restore_class_occurrence(schedule_id: str, on_date: str):
    """Undo a cancellation — the class runs that day after all."""

    try:
        parsed_id = str(_uuid.UUID(schedule_id))
        parsed_date = _roster_date(on_date)
    except (ValueError, AttributeError):
        return _error("Invalid schedule id or date.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        row = fetch_one(
            conn,
            """
            DELETE FROM class_schedule_exceptions
            WHERE tenant_id = %s AND schedule_id = %s AND on_date = %s
            RETURNING on_date
            """,
            (tenant.tenant_id, parsed_id, parsed_date),
        )
        if not row:
            return _error("That date was not marked as cancelled.", 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="schedule.restored",
            resource_type="class_schedule",
            resource_id=parsed_id,
            metadata={"date": parsed_date.isoformat()},
        )
        conn.commit()
        schedules = _schedules_with_students(conn, tenant.tenant_id)
    return jsonify({"ok": True, "schedules": schedules})


# ──────────────────────────────────────────────
# v8.10.0: the booking queue, on the studio's side
#
# One inbox, two tabs. The CMS already has a 待审核 page for registrations, and
# this does NOT become a second place to look — the counts are reported apart
# because the two mean different things, but the front desk visits one screen.
# ──────────────────────────────────────────────

def _pending_bookings(conn, tenant_id: str, limit: int = 100) -> list[dict]:
    """Requests awaiting a decision, newest first, with what they are for."""

    rows = fetch_all(
        conn,
        """
        SELECT b.id, to_char(b.on_date, 'YYYY-MM-DD') AS on_date, b.contact_name,
               b.contact_phone, b.message, b.created_at, b.student_id,
               cs.label, cs.capacity,
               to_char(cs.start_time, 'HH24:MI') AS start_time,
               c.name AS course_name,
               s.display_name AS matched_student,
               (SELECT count(*) FROM class_schedule_students css
                 WHERE css.schedule_id = cs.id) AS enrolled,
               (SELECT count(*) FROM class_bookings ab
                 WHERE ab.schedule_id = b.schedule_id AND ab.on_date = b.on_date
                   AND ab.status = 'approved') AS approved
        FROM class_bookings b
        JOIN class_schedules cs ON cs.id = b.schedule_id
        LEFT JOIN courses c ON c.id = cs.course_id
        LEFT JOIN students s ON s.id = b.student_id
        WHERE b.tenant_id = %s AND b.status = 'pending'
        ORDER BY b.on_date, cs.start_time, b.created_at
        LIMIT %s
        """,
        (tenant_id, limit),
    )
    out = []
    for r in rows:
        capacity = int(r["capacity"] or 0)
        taken = int(r["enrolled"] or 0) + int(r["approved"] or 0)
        out.append({
            "id": str(r["id"]),
            "date": r["on_date"],
            "startTime": r["start_time"],
            "title": r["course_name"] or r["label"] or "",
            "contactName": r["contact_name"],
            "contactPhone": r["contact_phone"],
            "message": r["message"],
            # Whether this matched an existing student is shown HERE and only
            # here. The public form's reply is identical either way — see
            # `public_class_booking`.
            "matchedStudent": r["matched_student"] or "",
            "isExistingStudent": bool(r["student_id"]),
            "capacity": capacity,
            "seatsLeft": max(0, capacity - taken),
        })
    return out


@api_v1.route("/class-bookings", methods=["GET"])
@auth_required
def list_class_bookings():
    """Booking requests awaiting a decision."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        bookings = _pending_bookings(conn, tenant.tenant_id)
    return jsonify({"bookings": bookings, "pending": len(bookings)})


@api_v1.route("/class-bookings/<booking_id>", methods=["PATCH"])
@permission_required("class_bookings:review")
def review_class_booking(booking_id: str):
    """Approve or decline one request with reception-scoped authority.

    Owners, managers and Front Desk can decide the request. This permission
    does not grant course, capacity or schedule mutation; those remain on
    their existing routes and permissions.

    Capacity is checked HERE, not when the request arrived. The count taken at
    submission time has expired by now, and two parents asking for the same
    last place is the normal case — the first approval takes it, the second is
    told plainly rather than silently overbooked.
    """

    try:
        parsed_id = str(_uuid.UUID(booking_id))
    except (ValueError, AttributeError):
        return _error("Invalid booking id.")
    payload = _json_payload()
    decision = _clean_text(payload, "status").lower()
    note = _clean_text(payload, "note", _clean_text(payload, "reviewNote"))[:300]
    if decision not in {"approved", "declined"}:
        return _error("status must be approved or declined.")

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.schedule_id, b.on_date, b.student_id, b.contact_name,
                       b.contact_phone, b.message, b.source_language,
                       b.privacy_notice_version, b.campaign, cs.capacity, cs.label,
                       to_char(cs.start_time, 'HH24:MI') AS start_time
                FROM class_bookings b
                JOIN class_schedules cs ON cs.id = b.schedule_id
                WHERE b.id = %s AND b.tenant_id = %s AND b.status = 'pending'
                FOR UPDATE OF b
                """,
                (parsed_id, tenant.tenant_id),
            )
            booking = cur.fetchone()
            if not booking:
                return _error("Booking request not found, or already reviewed.", 404)

            registration_id = None
            if decision == "approved":
                cur.execute(
                    "SELECT (SELECT count(*) FROM class_schedule_students css "
                    "         WHERE css.schedule_id = %s) "
                    "     + (SELECT count(*) FROM class_bookings ab "
                    "         WHERE ab.schedule_id = %s AND ab.on_date = %s "
                    "           AND ab.status = 'approved') AS taken",
                    (booking["schedule_id"], booking["schedule_id"], booking["on_date"]),
                )
                taken = int((cur.fetchone() or {}).get("taken") or 0)
                if taken >= int(booking["capacity"] or 0):
                    return _error(
                        "That class is now full. Decline this request, or raise the "
                        "class capacity first.", 409)

                if booking["student_id"]:
                    # An existing student: this is a seat on a day's roster,
                    # and deliberately NOT a new enquiry.
                    cur.execute(
                        """
                        INSERT INTO daily_roster_entries (
                            tenant_id, roster_date, student_id, source, status,
                            note, class_time, created_by_user_id
                        ) VALUES (%s, %s, %s, 'booking', 'scheduled', %s, %s::time, %s)
                        ON CONFLICT (tenant_id, roster_date, student_id) DO UPDATE
                        SET status = 'scheduled',
                            status_before_cancel = NULL,
                            class_time = COALESCE(EXCLUDED.class_time,
                                                  daily_roster_entries.class_time),
                            cancelled_by_user_id = NULL,
                            cancelled_at = NULL
                        """,
                        (tenant.tenant_id, booking["on_date"], booking["student_id"],
                         booking["label"] or "", booking["start_time"],
                         getattr(getattr(g, "actor", None), "user_id", None)),
                    )
                else:
                    # Nobody we recognise: this IS a new enquiry, so it joins
                    # the registration funnel and is counted there — once.
                    parts = str(booking["contact_name"] or "").split(None, 1)
                    cur.execute(
                        """
                        INSERT INTO registrations (
                            tenant_id, status, first_name, last_name, parent_name,
                            mobile, message, source, source_path, source_language,
                            campaign, privacy_consent_at, privacy_notice_version
                        ) VALUES (%s, 'pending', %s, %s, %s, %s, %s, 'class_booking',
                                  %s, %s, %s::jsonb, now(), %s)
                        RETURNING id
                        """,
                        (tenant.tenant_id, parts[0][:80],
                         (parts[1][:80] if len(parts) > 1 else ""),
                         booking["contact_name"][:80], booking["contact_phone"],
                         booking["message"],
                         f"/timetable#{booking['on_date']}",
                         booking["source_language"],
                         json.dumps(booking["campaign"] or {}, ensure_ascii=False),
                         booking["privacy_notice_version"]),
                    )
                    registration_id = (cur.fetchone() or {}).get("id")

            cur.execute(
                """
                UPDATE class_bookings
                SET status = %s, review_note = %s, reviewed_at = now(),
                    reviewed_by_user_id = %s,
                    registration_id = COALESCE(%s, registration_id)
                WHERE id = %s AND tenant_id = %s
                """,
                (decision, note, getattr(getattr(g, "actor", None), "user_id", None),
                 registration_id, parsed_id, tenant.tenant_id),
            )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"booking.{decision}",
            resource_type="class_booking",
            resource_id=parsed_id,
            metadata={"date": str(booking["on_date"]), "start": booking["start_time"],
                      "existingStudent": bool(booking["student_id"])},
        )
        conn.commit()
        bookings = _pending_bookings(conn, tenant.tenant_id)
    return jsonify({"ok": True, "bookings": bookings, "pending": len(bookings)})


# ──────────────────────────────────────────────
# B2: durable portfolio share links (tenant admin + public viewer)
# ──────────────────────────────────────────────

SHARE_LINK_DEFAULT_DAYS = 30
SHARE_LINK_MAX_DAYS = 90


@api_v1.route("/students/<student_id>/share-links", methods=["GET"])
@permission_required("portfolio:share")
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
@permission_required("portfolio:share")
def create_share_link(student_id: str):
    """Create a durable share link for a student's portfolio.

    portfolio:share (owner/manager) rather than portfolio:write: the link is a
    publicly resolvable token exposing a named minor's photos, so minting one
    is an exposure decision, not routine portfolio upkeep.

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

    if _rate_limited(f"shared-portfolio:{_client_ip()}", 20):
        return _error("Too many requests. Please wait a moment.", 429)

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


@api_v1.route("/audit-logs", methods=["GET"])
@tenant_owner_required
def tenant_audit_logs():
    """Recent audit events for the resolved tenant, newest first.

    Closes the "owners are blind to staff-initiated refunds/exports/share
    links" gap from the v7.4.0 RBAC audit: the platform /admin/audit-logs
    view is super-admin-only, so tenant owners get their own scoped read.
    """

    try:
        limit = max(1, min(200, int(request.args.get("limit", 50))))
    except (TypeError, ValueError):
        limit = 50
    action_filter = str(request.args.get("action") or "").strip()

    with connect() as conn:
        tenant = _tenant_context(conn)
        params: list = [tenant.tenant_id]
        action_sql = ""
        if action_filter:
            action_sql = "AND a.action ILIKE %s"
            params.append(f"%{action_filter}%")
        params.append(limit)
        rows = fetch_all(
            conn,
            f"""
            SELECT a.id, a.action, a.resource_type, a.resource_id,
                   a.metadata, a.created_at, u.email AS actor_email
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.actor_user_id
            WHERE a.tenant_id = %s {action_sql}
            ORDER BY a.created_at DESC
            LIMIT %s
            """,
            tuple(params),
        )
    return jsonify({
        "auditLogs": [
            {
                "id": str(row["id"]),
                "action": row["action"],
                "resourceType": row["resource_type"],
                "resourceId": row["resource_id"],
                "actorEmail": row["actor_email"] or "",
                "metadata": row["metadata"] or {},
                "createdAt": (row["created_at"].isoformat() if row["created_at"] else ""),
            }
            for row in rows
        ],
    })


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

    def _signed_amount(row):
        # Historical rows mix conventions: check-in wrote `consume` with a
        # positive amount while the manual endpoint writes it negative. The
        # export normalizes so summing the Amount column reproduces balance
        # movement: consume/expire always negative, everything else as stored.
        amount = float(row["amount"] or 0)
        if row["transaction_type"] in ("consume", "expire"):
            return -abs(amount)
        return amount

    data = ([r["occurred_at"], r["student"], r["course"], r["transaction_type"],
             _signed_amount(r), r["balance_after"], r["note"]] for r in rows)
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
    """Return true only for genuine loopback connections.

    Uses ``request.remote_addr`` (the socket peer) — never the Host header,
    which any client can set freely. Behind a reverse proxy remote_addr is
    the proxy address, so this stays False for proxied/tunnelled traffic;
    that is intentional: the local-admin repair path gated by this function
    must only ever trigger for direct localhost development connections
    (cf. _client_ip(), which applies the same trust rule).
    """

    return (request.remote_addr or "") in {"127.0.0.1", "::1"}


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
        or not os.environ.get("STUDIOSAAS_ADMIN_PASSWORD", "")
        or password != os.environ["STUDIOSAAS_ADMIN_PASSWORD"]
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

        # The staff console is the only surface behind this login. A user whose
        # every active membership is `parent` holds no staff permission, yet a
        # session would still pass @auth_required on read routes — so refuse
        # the session outright until the family self-service surface exists.
        staff_membership = fetch_one(
            conn,
            """
            SELECT 1 FROM memberships
            WHERE user_id = %s AND status = 'active' AND role <> 'parent'
            LIMIT 1
            """,
            (user["id"],),
        )
        if not staff_membership:
            # Distinguish a parent-only account from one with no active
            # memberships at all (e.g. deactivated staff) — the message and
            # audit reason must not mislead support triage.
            parent_membership = fetch_one(
                conn,
                """
                SELECT 1 FROM memberships
                WHERE user_id = %s AND status = 'active' AND role = 'parent'
                LIMIT 1
                """,
                (user["id"],),
            )
            if parent_membership:
                reason = "parent_only_membership"
                message = "家庭自助登录暂未开放，请联系工作室。 Family self-service login is not available yet."
            else:
                reason = "no_active_membership"
                message = "该账号没有有效的工作人员身份，请联系管理员。 This account has no active staff membership."
            _audit_request(
                conn,
                tenant_id=None,
                action="auth.login_rejected",
                resource_type="user",
                resource_id=user["id"],
                metadata={"email": email, "reason": reason},
            )
            conn.commit()
            return _error(message, 403)

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
@permission_required("settings:write")
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
    if target not in {"hero", "principal", "about", "showcase"}:
        return _error("Website media target must be hero, principal, about, or showcase.")
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

        # Handle balance / creditHours change → signed adjustment through the
        # ledger. The account row is locked first so a concurrent check-in
        # cannot slip between the read and the overwrite (lost update), the
        # stored amount keeps its sign (a downward adjustment used to be
        # recorded as positive), and the row is created under the lock's
        # serialization when it does not exist yet.
        def _apply_absolute_balance(target_value: float) -> None:
            cur = conn.cursor()
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id)
            cur.execute(
                """
                SELECT COALESCE(balance, 0)::float AS balance
                FROM credit_accounts
                WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
                FOR UPDATE
                """,
                (tenant.tenant_id, student_id),
            )
            row = cur.fetchone()
            current = float(row["balance"]) if row else 0.0
            delta = target_value - current
            if abs(delta) <= 0.001:
                return
            cur.execute(
                """
                INSERT INTO credit_transactions (tenant_id, student_id, transaction_type, amount, balance_after)
                VALUES (%s, %s, 'adjustment', %s, %s)
                RETURNING id
                """,
                (tenant.tenant_id, student_id, delta, target_value),
            )
            _ensure_default_credit_account(cur, tenant.tenant_id, student_id, target_value)

        new_balance_raw = payload.get("balance")
        if new_balance_raw is not None:
            try:
                new_balance = float(new_balance_raw)
            except (TypeError, ValueError):
                return _error("Invalid balance value.")
            _apply_absolute_balance(new_balance)

        new_credit_raw = payload.get("creditHours")
        if new_credit_raw is not None:
            try:
                new_credit_val = float(new_credit_raw)
            except (TypeError, ValueError):
                return _error("Invalid credit hours value.")
            _apply_absolute_balance(new_credit_val)

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


# ══════════════════════════════════════════════════════════════════════════
# v10.0.0 — the money layer
#
# Every route below follows the same three steps the rest of this file does:
# resolve the tenant, check the actor may do this, write an audit row. The one
# addition is `_require_feature`, which asks whether the studio is entitled to
# the capability at all — a plan question rather than a permission question.
#
# The rule that governs all of them: an entitlement check may stand between a
# studio and *new* work, never between a studio and its own records. Reading an
# invoice, exporting a statement and downloading history stay available whatever
# happens to a subscription, because those are the studio's documents.
# ══════════════════════════════════════════════════════════════════════════


def _require_feature(conn, tenant_id: str, feature: str):
    """Assert the tenant is entitled to a capability, or raise a 402-shaped error.

    Returns the resolved entitlements so a caller that needs several checks
    resolves once.
    """

    entitlements = _entitlements.resolve(conn, tenant_id)
    if not entitlements.has(feature):
        raise _entitlements.FeatureUnavailableError(feature)
    return entitlements


def _feature_error(exc: "_entitlements.FeatureUnavailableError"):
    """Turn a missing entitlement into an answer a studio can act on."""

    label = _entitlements.FEATURE_LABELS.get(exc.feature, {})
    return api_error(
        str(exc),
        403,
        error="feature_not_available",
        details={
            "feature": exc.feature,
            "label": label,
            "addon": exc.feature in _entitlements.ADDON_FEATURES,
        },
    )


def _money_cents(payload: dict, key: str, *, required: bool = True) -> int:
    """Read an amount as integer cents, refusing anything that could round."""

    raw = payload.get(key)
    if raw is None or raw == "":
        if required:
            raise ValueError(f"{key} is required.")
        return 0
    if isinstance(raw, bool):
        raise ValueError(f"{key} must be a number of cents.")
    if isinstance(raw, float):
        # A float here is a caller who has already lost precision somewhere.
        raise ValueError(f"{key} must be an integer number of cents, not a decimal.")
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{key} must be an integer number of cents.")


def _iso_date(payload: dict, key: str, *, fallback=None):
    raw = str(payload.get(key) or "").strip()
    if not raw:
        return fallback
    try:
        return _date.fromisoformat(raw)
    except ValueError:
        raise ValueError(f"{key} must be an ISO date (YYYY-MM-DD).")


# ── entitlements ─────────────────────────────────────────────────────────


@api_v1.route("/entitlements", methods=["GET"])
@auth_required
def get_entitlements():
    """What this studio can currently do. Drives the console's disabled states."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        resolved = _entitlements.resolve(conn, tenant.tenant_id)
    return jsonify(resolved.as_payload())


@api_v1.route("/admin/tenants/<tenant_id>/addons", methods=["GET", "POST"])
@super_admin_required
def admin_tenant_addons(tenant_id: str):
    """Grant or list per-tenant add-ons. Platform side only.

    This is switch one of three for an add-on like Xero: whether the studio has
    it. Connecting it and pushing with it are the studio's own decisions and
    live on their own routes.
    """

    if request.method == "GET":
        with connect() as conn:
            rows = fetch_all(
                conn,
                """
                SELECT addon_key, status, granted_at, expires_at, note
                FROM tenant_addons WHERE tenant_id = %s ORDER BY addon_key
                """,
                (tenant_id,),
            )
        return jsonify({"addons": rows, "available": list(_entitlements.known_addon_keys())})

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    addon_key = _clean_text(payload, "addonKey")
    if addon_key not in set(_entitlements.known_addon_keys()):
        return _error(f"Unknown add-on: {addon_key or '(missing)'}")

    actor = getattr(g, "actor", None)
    with connect() as conn:
        _entitlements.grant(
            conn,
            tenant_id,
            addon_key,
            granted_by_user_id=getattr(actor, "user_id", None),
            note=_clean_text(payload, "note"),
        )
        _audit_request(
            conn,
            tenant_id=tenant_id,
            action="addon.granted",
            resource_type="tenant_addon",
            resource_id=addon_key,
        )
        conn.commit()
    return jsonify({"ok": True, "addonKey": addon_key}), 201


@api_v1.route("/admin/tenants/<tenant_id>/addons/<addon_key>", methods=["DELETE"])
@super_admin_required
def admin_revoke_addon(tenant_id: str, addon_key: str):
    """Withdraw an add-on. Suspends the grant; deletes nothing.

    The studio keeps every record the add-on produced, the connection it
    established and the errors it logged. Only new work stops.
    """

    with connect() as conn:
        _entitlements.revoke(conn, tenant_id, addon_key, note="revoked via platform console")
        _audit_request(
            conn,
            tenant_id=tenant_id,
            action="addon.revoked",
            resource_type="tenant_addon",
            resource_id=addon_key,
        )
        conn.commit()
    return jsonify({"ok": True})


# ── billing accounts ─────────────────────────────────────────────────────


@api_v1.route("/billing/accounts", methods=["GET", "POST"])
@permission_required("billing:read")
def billing_accounts():
    """The payers a studio invoices — families and organisations."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            # ``studentId`` answers a different question with the same rows:
            # "who pays for this child", asked from the student record. Doing it
            # here rather than in a new route keeps one definition of what an
            # account's balance means — a second endpoint would eventually
            # compute it slightly differently and the two screens would
            # disagree in front of a parent.
            student_id = (request.args.get("studentId") or "").strip()
            rows = fetch_all(
                conn,
                """
                SELECT a.id, a.name, a.kind, a.contact_name, a.email, a.mobile,
                       a.company_name, a.payment_terms_days, a.status,
                       COALESCE((SELECT SUM(i.balance_cents) FROM invoices i
                                  WHERE i.tenant_id = a.tenant_id
                                    AND i.billing_account_id = a.id
                                    AND i.status IN ('issued','part_paid')), 0) AS balance_cents,
                       COALESCE((SELECT count(*) FROM billing_account_members m
                                  WHERE m.billing_account_id = a.id), 0) AS student_count
                FROM billing_accounts a
                WHERE a.tenant_id = %s AND a.status = 'active'
                  AND (%s = '' OR EXISTS (
                        SELECT 1 FROM billing_account_members m
                         WHERE m.tenant_id = a.tenant_id
                           AND m.billing_account_id = a.id
                           AND m.student_id::text = %s))
                ORDER BY lower(a.name)
                """,
                (tenant.tenant_id, student_id, student_id),
            )
            return jsonify({"accounts": rows})

        require_permission(getattr(g, "actor", None), "billing:write")
        try:
            payload = _json_payload()
            name = _clean_text(payload, "name")
            if not name:
                raise ValueError("An account needs a name.")
        except (ValueError, PermissionDeniedError) as exc:
            return _error(str(exc), 403 if isinstance(exc, PermissionDeniedError) else 400)

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO billing_accounts
                    (tenant_id, name, kind, contact_name, email, mobile,
                     company_name, abn, billing_address, payment_terms_days, language)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, name, kind, payment_terms_days
                """,
                (
                    tenant.tenant_id,
                    name,
                    _clean_text(payload, "kind", "family") or "family",
                    _clean_text(payload, "contactName"),
                    _clean_text(payload, "email"),
                    _clean_text(payload, "mobile"),
                    _clean_text(payload, "companyName"),
                    _clean_text(payload, "abn"),
                    _clean_text(payload, "billingAddress"),
                    _positive_int(payload, "paymentTermsDays", fallback=14),
                    _clean_text(payload, "language"),
                ),
            )
            account = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_account.created",
            resource_type="billing_account",
            resource_id=account["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "account": account}), 201


@api_v1.route("/billing/accounts/<account_id>/members", methods=["POST", "DELETE"])
@permission_required("billing:write")
def billing_account_members(account_id: str):
    """Attach or detach a student from the payer who is billed for them."""

    try:
        payload = _json_payload()
        student_id = _clean_text(payload, "studentId")
        if not student_id:
            raise ValueError("studentId is required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            if request.method == "POST":
                # The composite foreign key refuses a student from another
                # tenant, so this cannot be made to cross a boundary even with
                # a guessed identifier.
                cur.execute(
                    """
                    INSERT INTO billing_account_members (tenant_id, billing_account_id, student_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (billing_account_id, student_id) DO NOTHING
                    """,
                    (tenant.tenant_id, account_id, student_id),
                )
            else:
                cur.execute(
                    """
                    DELETE FROM billing_account_members
                     WHERE tenant_id = %s AND billing_account_id = %s AND student_id = %s
                    """,
                    (tenant.tenant_id, account_id, student_id),
                )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_account.members_changed",
            resource_type="billing_account",
            resource_id=account_id,
            metadata={"studentId": student_id, "op": request.method},
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/billing/accounts/<account_id>/statement", methods=["GET"])
@permission_required("billing:read")
def billing_statement(account_id: str):
    """Everything that moved on one account, invoices and payments interleaved."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        statement = _billing.account_statement(conn, tenant.tenant_id, account_id)
    return jsonify(statement)


# ── tax codes ────────────────────────────────────────────────────────────


@api_v1.route("/billing/identity", methods=["GET", "PUT"])
@permission_required("billing:read")
def billing_identity_route():
    """Who this studio is, as it appears on the documents it issues."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            return jsonify({"identity": _billing.billing_identity(conn, tenant.tenant_id)})

        try:
            require_permission(getattr(g, "actor", None), "settings:write")
            payload = _json_payload()
            saved = _billing.save_billing_identity(conn, tenant.tenant_id, payload)
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, _billing.BillingError) as exc:
            conn.rollback()
            return _error(str(exc))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="billing_identity.updated",
            resource_type="tenant",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
    return jsonify({"ok": True, "identity": saved})


@api_v1.route("/billing/tax-codes", methods=["GET", "POST"])
@permission_required("billing:read")
def billing_tax_codes():
    """Tax codes, in basis points.

    Which code applies to tuition versus instrument hire is a question for the
    studio's accountant. The product stores the answer and applies it; it does
    not decide it.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "GET":
            rows = fetch_all(
                conn,
                """
                SELECT id, code, name, rate_bp, is_default, is_active
                FROM tax_codes WHERE tenant_id = %s ORDER BY is_default DESC, code
                """,
                (tenant.tenant_id,),
            )
            return jsonify({"taxCodes": rows})

        try:
            require_permission(getattr(g, "actor", None), "billing:write")
            payload = _json_payload()
            code = _clean_text(payload, "code")
            if not code:
                raise ValueError("A tax code needs a code.")
            rate_bp = int(payload.get("rateBp") or 0)
            if not 0 <= rate_bp <= 10000:
                raise ValueError("rateBp must be between 0 and 10000.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, TypeError) as exc:
            return _error(str(exc))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO tax_codes (tenant_id, code, name, rate_bp, is_default)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, code) DO UPDATE
                   SET name = EXCLUDED.name, rate_bp = EXCLUDED.rate_bp
                RETURNING id, code, name, rate_bp, is_default
                """,
                (
                    tenant.tenant_id,
                    code,
                    _clean_text(payload, "name"),
                    rate_bp,
                    bool(payload.get("isDefault")),
                ),
            )
            tax_code = cur.fetchone()
        conn.commit()
    return jsonify({"ok": True, "taxCode": tax_code}), 201


# ── invoices ─────────────────────────────────────────────────────────────


@api_v1.route("/billing/invoices", methods=["GET", "POST"])
@permission_required("billing:read")
def billing_invoices():
    """List invoices, or open a draft.

    A draft carries no number. Numbers are allocated at issue, gaplessly, so a
    draft that is abandoned never leaves a hole in the sequence for somebody to
    explain later.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_BILLING)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            status = (request.args.get("status") or "").strip()
            account_id = (request.args.get("accountId") or "").strip()
            rows = fetch_all(
                conn,
                """
                SELECT i.id, i.number, i.status, i.issue_date, i.due_date,
                       i.total_cents, i.amount_paid_cents, i.balance_cents,
                       a.name AS account_name, a.id AS billing_account_id,
                       (i.status IN ('issued','part_paid')
                        AND i.due_date IS NOT NULL
                        AND i.due_date < CURRENT_DATE) AS overdue
                FROM invoices i
                JOIN billing_accounts a
                  ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
                WHERE i.tenant_id = %s
                  AND (%s = '' OR i.status = %s)
                  AND (%s = '' OR i.billing_account_id::text = %s)
                ORDER BY COALESCE(i.issue_date, CURRENT_DATE) DESC, i.created_at DESC
                LIMIT 500
                """,
                (tenant.tenant_id, status, status, account_id, account_id),
            )
            return jsonify({"invoices": rows})

        try:
            require_permission(getattr(g, "actor", None), "billing:write")
            payload = _json_payload()
            account_id = _clean_text(payload, "billingAccountId")
            if not account_id:
                raise ValueError("billingAccountId is required.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except ValueError as exc:
            return _error(str(exc))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO invoices (tenant_id, billing_account_id, term_id, note, purchase_order_ref)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, status, total_cents
                """,
                (
                    tenant.tenant_id,
                    account_id,
                    payload.get("termId") or None,
                    _clean_text(payload, "note"),
                    _clean_text(payload, "purchaseOrderRef"),
                ),
            )
            invoice = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="invoice.drafted",
            resource_type="invoice",
            resource_id=invoice["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "invoice": invoice}), 201


@api_v1.route("/billing/invoices/<invoice_id>", methods=["GET"])
@permission_required("billing:read")
def billing_invoice_detail(invoice_id: str):
    """One invoice with its lines and its history."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        invoice = fetch_one(
            conn,
            """
            SELECT i.*, a.name AS account_name, a.email AS account_email
            FROM invoices i
            JOIN billing_accounts a
              ON a.tenant_id = i.tenant_id AND a.id = i.billing_account_id
            WHERE i.tenant_id = %s AND i.id = %s
            """,
            (tenant.tenant_id, invoice_id),
        )
        if not invoice:
            return _error("Invoice not found.", 404)
        lines = fetch_all(
            conn,
            """
            SELECT id, description, quantity::float AS quantity, unit_price_cents,
                   tax_rate_bp, tax_cents, total_cents, source_kind, student_id
            FROM invoice_lines
            WHERE tenant_id = %s AND invoice_id = %s ORDER BY sort_order, created_at
            """,
            (tenant.tenant_id, invoice_id),
        )
        events = fetch_all(
            conn,
            """
            SELECT event_type, detail, occurred_at
            FROM invoice_events WHERE tenant_id = %s AND invoice_id = %s
            ORDER BY occurred_at DESC LIMIT 50
            """,
            (tenant.tenant_id, invoice_id),
        )
    return jsonify({"invoice": invoice, "lines": lines, "events": events})


@api_v1.route("/billing/invoices/<invoice_id>/lines", methods=["POST"])
@permission_required("billing:write")
def billing_invoice_add_line(invoice_id: str):
    """Add a line to a draft. Refused once the invoice has been issued."""

    try:
        payload = _json_payload()
        description = _clean_text(payload, "description")
        if not description:
            raise ValueError("A line needs a description.")
        unit_price_cents = _money_cents(payload, "unitPriceCents")
        quantity = payload.get("quantity", 1)
        tax_rate_bp = int(payload.get("taxRateBp") or 0)
    except (ValueError, TypeError) as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            net, tax, total = _billing.line_amounts(quantity, unit_price_cents, tax_rate_bp)
        except _billing.BillingError as exc:
            return _error(str(exc))

        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO invoice_lines
                        (tenant_id, invoice_id, description, quantity, unit_price_cents,
                         tax_code_id, tax_rate_bp, tax_cents, total_cents,
                         source_kind, source_id, student_id, sort_order)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            COALESCE((SELECT MAX(sort_order) + 1 FROM invoice_lines
                                       WHERE invoice_id = %s), 0))
                    RETURNING id, description, total_cents
                    """,
                    (
                        tenant.tenant_id, invoice_id, description, quantity,
                        unit_price_cents, payload.get("taxCodeId") or None, tax_rate_bp,
                        tax, total, _clean_text(payload, "sourceKind", "manual") or "manual",
                        payload.get("sourceId") or None, payload.get("studentId") or None,
                        invoice_id,
                    ),
                )
                line = cur.fetchone()
            _billing.recalculate_totals(conn, tenant.tenant_id, invoice_id)
            conn.commit()
        except Exception as exc:  # noqa: BLE001 — surfaced as a 409, see below
            conn.rollback()
            # The immutability trigger raises here when the invoice has already
            # been issued. That is a conflict rather than a server fault, and
            # the message it carries is the one the studio needs to read.
            return _error(str(exc).strip().splitlines()[0], 409)
    return jsonify({"ok": True, "line": line}), 201


@api_v1.route("/billing/invoices/<invoice_id>/issue", methods=["POST"])
@permission_required("billing:issue")
def billing_issue_invoice(invoice_id: str):
    """Turn a draft into a numbered, immutable document."""

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            issued = _billing.issue_invoice(
                conn,
                tenant.tenant_id,
                invoice_id,
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _billing.BillingError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="invoice.issued",
            resource_type="invoice",
            resource_id=invoice_id,
            metadata={"number": issued["number"]},
        )
        # Queued rather than pushed inline: a slow accounting API must never be
        # what stands between a studio and issuing an invoice.
        _xero.enqueue(conn, tenant.tenant_id, local_kind="invoice", local_id=invoice_id)
        conn.commit()
    return jsonify({"ok": True, "invoice": issued})


@api_v1.route("/billing/invoices/<invoice_id>/void", methods=["POST"])
@permission_required("billing:issue")
def billing_void_invoice(invoice_id: str):
    """Void an issued invoice that has taken no money."""

    payload = request.get_json(silent=True) or {}
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        return _error("Voiding an invoice needs a reason.")

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _billing.void_invoice(
                conn, tenant.tenant_id, invoice_id,
                reason=reason, actor_user_id=getattr(actor, "user_id", None),
            )
        except _billing.BillingError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="invoice.voided",
            resource_type="invoice",
            resource_id=invoice_id,
            metadata={"reason": reason},
        )
        conn.commit()
    return jsonify({"ok": True})


# ── payments ─────────────────────────────────────────────────────────────


@api_v1.route("/billing/payments", methods=["POST"])
@permission_required("payments:write")
def billing_record_payment():
    """Record money arriving, and apply it to the oldest debt first.

    Oldest-first is the convention families and accountants both expect, and it
    keeps the ageing report honest. Anything left over stays on the account as
    credit, because an overpayment is still the family's money.
    """

    try:
        payload = _json_payload()
        account_id = _clean_text(payload, "billingAccountId")
        if not account_id:
            raise ValueError("billingAccountId is required.")
        amount_cents = _money_cents(payload, "amountCents")
        method = _clean_text(payload, "method", "bank_transfer") or "bank_transfer"
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            payment = _payments.record_payment(
                conn,
                tenant.tenant_id,
                billing_account_id=account_id,
                amount_cents=amount_cents,
                method=method,
                note=_clean_text(payload, "note"),
                idempotency_key=(
                    _clean_text(payload, "idempotencyKey")
                    or _payments.new_idempotency_key()
                ),
                recorded_by_user_id=getattr(actor, "user_id", None),
            )
            allocations = (
                _payments.auto_allocate(conn, tenant.tenant_id, payment["id"])
                if payload.get("autoAllocate", True)
                else []
            )
        except _payments.PaymentError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="payment.recorded",
            resource_type="payment",
            resource_id=payment["id"],
            metadata={"amountCents": amount_cents, "method": method},
        )
        conn.commit()
    return jsonify({"ok": True, "payment": payment, "allocations": allocations}), 201


@api_v1.route("/billing/payments/<payment_id>/refund", methods=["POST"])
@permission_required("payments:refund")
def billing_refund_payment(payment_id: str):
    """Send money back, releasing the newest allocations first."""

    try:
        payload = _json_payload()
        amount_cents = _money_cents(payload, "amountCents")
    except ValueError as exc:
        return _error(str(exc))

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            refunded = _payments.refund(
                conn,
                tenant.tenant_id,
                payment_id,
                amount_cents=amount_cents,
                reason=_clean_text(payload, "reason"),
                actor_user_id=getattr(actor, "user_id", None),
            )
        except _payments.PaymentError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="payment.refunded",
            resource_type="payment",
            resource_id=payment_id,
            metadata={"amountCents": amount_cents},
        )
        conn.commit()
    return jsonify({"ok": True, "refund": refunded})


# ── teaching hours and pay ───────────────────────────────────────────────


@api_v1.route("/teaching/rates", methods=["GET", "POST"])
@permission_required("payroll:read")
def teaching_rates():
    """Pay rates, effective-dated, on five different bases."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_TEACHER_PAYABLES)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            rows = fetch_all(
                conn,
                """
                SELECT r.id, r.teacher_user_id, u.full_name, r.course_id, c.name AS course_name,
                       r.basis, r.amount_cents, r.percent_bp, r.effective_from, r.effective_to
                FROM teacher_pay_rates r
                JOIN users u ON u.id = r.teacher_user_id
                LEFT JOIN courses c ON c.id = r.course_id
                WHERE r.tenant_id = %s
                ORDER BY u.full_name, r.effective_from DESC
                """,
                (tenant.tenant_id,),
            )
            return jsonify({"rates": rows})

        try:
            require_permission(getattr(g, "actor", None), "payroll:write")
            payload = _json_payload()
            teacher_user_id = _clean_text(payload, "teacherUserId")
            basis = _clean_text(payload, "basis")
            if not teacher_user_id or basis not in _teaching_pay.RATE_BASES:
                raise ValueError("teacherUserId and a valid basis are required.")
            amount_cents = (
                None if basis == "percent_of_tuition"
                else _money_cents(payload, "amountCents")
            )
            percent_bp = int(payload.get("percentBp") or 0) if basis == "percent_of_tuition" else None
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, TypeError) as exc:
            return _error(str(exc))

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO teacher_pay_rates
                    (tenant_id, teacher_user_id, course_id, basis, amount_cents,
                     percent_bp, effective_from, note)
                VALUES (%s, %s, %s, %s, %s, %s, COALESCE(%s, CURRENT_DATE), %s)
                RETURNING id, basis, amount_cents, percent_bp, effective_from
                """,
                (
                    tenant.tenant_id, teacher_user_id, payload.get("courseId") or None,
                    basis, amount_cents, percent_bp,
                    _iso_date(payload, "effectiveFrom"), _clean_text(payload, "note"),
                ),
            )
            rate = cur.fetchone()
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="pay_rate.created",
            resource_type="teacher_pay_rate",
            resource_id=rate["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "rate": rate}), 201


@api_v1.route("/teaching/summary", methods=["GET"])
@permission_required("payroll:read")
def teaching_summary():
    """Every teacher's totals for a period — the payables list.

    Deliberately not `/reports/teacher-cost`. That one carries the margin
    against tuition billed and is a management report, gated on
    `management_reports`; this is the list a studio works through to pay
    people, so it belongs to `teacher_payables` and is available a tier lower.
    Serving the payroll screen from the report endpoint would have made paying
    teachers require the reporting plan, which is not what anybody bought.

    Read-only: it never opens a pay period. Opening one is a decision, and a
    screen that creates rows just by being looked at cannot be trusted.
    """

    try:
        default_start, default_end = _reports.default_period()
        start = _iso_date(request.args, "from") or default_start
        end = _iso_date(request.args, "to") or default_end
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_TEACHER_PAYABLES)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        rows = fetch_all(
            conn,
            """
            SELECT s.teacher_user_id, u.full_name,
                   COALESCE(e.engagement, 'unset') AS engagement,
                   COUNT(*)                                                     AS sessions,
                   COUNT(*) FILTER (WHERE NOT s.counts_for_pay)                 AS unpaid_sessions,
                   COALESCE(SUM(s.duration_minutes) FILTER (WHERE s.counts_for_pay), 0) AS paid_minutes,
                   COALESCE(SUM(s.amount_cents) FILTER (WHERE s.counts_for_pay), 0)     AS cost_cents
            FROM teaching_sessions s
            JOIN users u ON u.id = s.teacher_user_id
            LEFT JOIN teacher_engagements e
                   ON e.tenant_id = s.tenant_id AND e.teacher_user_id = s.teacher_user_id
            WHERE s.tenant_id = %s AND s.occurred_on BETWEEN %s AND %s
            GROUP BY s.teacher_user_id, u.full_name, e.engagement
            ORDER BY cost_cents DESC
            """,
            (tenant.tenant_id, start, end),
        )
    return jsonify({"from": start.isoformat(), "to": end.isoformat(), "teachers": rows})


@api_v1.route("/teaching/timesheet", methods=["GET"])
@auth_required
def teaching_timesheet():
    """Scheduled against actual, for one teacher over one period.

    A teacher may read their own and only their own. The check is here rather
    than in the permission table because "their own" is a property of the
    request, not of the role.
    """

    actor = getattr(g, "actor", None)
    requested = (request.args.get("teacherUserId") or "").strip()
    actor_id = str(getattr(actor, "user_id", "") or "")
    is_teacher_only = getattr(actor, "role", None) == Role.TEACHER

    if is_teacher_only and requested and requested != actor_id:
        return _error("A teacher may only read their own hours.", 403)
    teacher_user_id = requested or actor_id
    if not teacher_user_id:
        return _error("teacherUserId is required.")

    try:
        start = _iso_date(request.args, "from") or _date.today().replace(day=1)
        end = _iso_date(request.args, "to") or _date.today()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        if not is_teacher_only:
            try:
                require_permission(actor, "payroll:read")
            except PermissionDeniedError as exc:
                return _error(str(exc), 403)
        summary = _teaching_pay.variance(conn, tenant.tenant_id, teacher_user_id, start, end)
        sessions = fetch_all(
            conn,
            """
            SELECT s.occurred_on,
                   -- `time` is not JSON serializable and Flask's encoder does not
                   -- special-case it the way it does date and datetime, so the
                   -- cast happens here rather than being remembered downstream.
                   to_char(s.start_time, 'HH24:MI') AS start_time,
                   s.duration_minutes, s.student_count,
                   s.counts_for_pay, s.rate_basis, s.amount_cents, s.locked_at,
                   c.name AS course_name
            FROM teaching_sessions s
            LEFT JOIN courses c ON c.id = s.course_id
            WHERE s.tenant_id = %s AND s.teacher_user_id = %s
              AND s.occurred_on BETWEEN %s AND %s
            ORDER BY s.occurred_on DESC, s.start_time NULLS LAST
            """,
            (tenant.tenant_id, teacher_user_id, start, end),
        )
    return jsonify({"summary": summary, "sessions": sessions})


@api_v1.route("/teaching/periods", methods=["POST"])
@permission_required("payroll:write")
def teaching_open_period():
    """Open a pay period and roll its sessions into it."""

    try:
        payload = _json_payload()
        teacher_user_id = _clean_text(payload, "teacherUserId")
        start = _iso_date(payload, "periodStart")
        end = _iso_date(payload, "periodEnd")
        if not teacher_user_id or not start or not end:
            raise ValueError("teacherUserId, periodStart and periodEnd are required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        period = _teaching_pay.open_period(
            conn, tenant.tenant_id, teacher_user_id, period_start=start, period_end=end
        )
        try:
            totals = _teaching_pay.recalculate_period(conn, tenant.tenant_id, period["id"])
        except _teaching_pay.PayError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        conn.commit()
    return jsonify({"ok": True, "period": totals})


@api_v1.route("/teaching/periods/<period_id>/confirm", methods=["POST"])
@auth_required
def teaching_confirm_period(period_id: str):
    """The teacher's own acknowledgement of their hours.

    Deliberately the teacher's action. A disagreement about hours is cheap to
    settle before anybody is paid and expensive afterwards.
    """

    actor = getattr(g, "actor", None)
    with connect() as conn:
        tenant = _tenant_context(conn)
        period = fetch_one(
            conn,
            "SELECT teacher_user_id FROM teacher_pay_periods WHERE tenant_id = %s AND id = %s",
            (tenant.tenant_id, period_id),
        )
        if not period:
            return _error("Pay period not found.", 404)

        actor_id = str(getattr(actor, "user_id", "") or "")
        if str(period["teacher_user_id"]) != actor_id:
            try:
                require_permission(actor, "payroll:write")
            except PermissionDeniedError:
                return _error("Only this teacher, or a manager, may confirm this period.", 403)

        try:
            confirmed = _teaching_pay.confirm_period(
                conn, tenant.tenant_id, period_id, confirmed_by_user_id=actor_id
            )
        except _teaching_pay.PayError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="pay_period.confirmed",
            resource_type="teacher_pay_period",
            resource_id=period_id,
        )
        conn.commit()
    return jsonify({"ok": True, "period": confirmed})


@api_v1.route("/teaching/periods/<period_id>/summary", methods=["GET"])
@permission_required("payroll:read")
def teaching_period_summary(period_id: str):
    """Everything needed to hand a period to whoever runs payroll."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            summary = _teaching_pay.payable_summary(conn, tenant.tenant_id, period_id)
        except _teaching_pay.PayError as exc:
            return _error(str(exc), 404)

        engagement = summary["period"]["engagement"]
        try:
            summary["exportKind"] = _xero.payable_export_kind(engagement)
            summary["exportBlocked"] = ""
        except _xero.XeroError as exc:
            # Not an error for the caller: the summary is still correct and
            # readable. It only means the accounting export cannot proceed
            # until somebody records how this teacher is engaged.
            summary["exportKind"] = None
            summary["exportBlocked"] = str(exc)
    return jsonify(summary)


# ── Xero: the three switches ─────────────────────────────────────────────


@api_v1.route("/integrations/xero", methods=["GET"])
@permission_required("billing:read")
def xero_status():
    """All three switches at once, plus what is still blocking the third."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        status = _xero.gate_status(conn, tenant.tenant_id)
        mappings = fetch_all(
            conn,
            """
            SELECT item_kind, account_code, tax_type
            FROM xero_account_mappings WHERE tenant_id = %s ORDER BY item_kind
            """,
            (tenant.tenant_id,),
        )
        settings = fetch_one(
            conn,
            """
            SELECT push_enabled, single_entry_decision, clearing_account_code,
                   mapping_confirmed_at, demo_run_completed_at, last_pushed_at
            FROM xero_sync_settings WHERE tenant_id = %s
            """,
            (tenant.tenant_id,),
        )
        missing = _xero.missing_required_mappings(conn, tenant.tenant_id)
    return jsonify(
        {
            "entitled": status.entitled,
            "connected": status.connected,
            "pushEnabled": status.push_enabled,
            "canEnablePush": status.can_enable,
            "blockers": status.blockers(),
            "missingMappings": missing,
            "mappableKinds": list(_xero.MAPPABLE_ITEM_KINDS),
            "requiredKinds": list(_xero.REQUIRED_ITEM_KINDS),
            "mappings": mappings,
            "settings": settings or {},
        }
    )


@api_v1.route("/integrations/xero/mappings", methods=["PUT"])
@permission_required("integrations:manage")
def xero_put_mappings():
    """Store the chart-of-accounts mapping the studio's accountant supplied."""

    try:
        payload = _json_payload()
        mappings = payload.get("mappings")
        if not isinstance(mappings, list):
            raise ValueError("mappings must be a list.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_XERO)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        with conn.cursor() as cur:
            for item in mappings:
                kind = str(item.get("itemKind") or "").strip()
                if kind not in _xero.MAPPABLE_ITEM_KINDS:
                    conn.rollback()
                    return _error(f"Unknown mapping kind: {kind}")
                cur.execute(
                    """
                    INSERT INTO xero_account_mappings (tenant_id, item_kind, account_code, tax_type)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (tenant_id, item_kind) DO UPDATE
                       SET account_code = EXCLUDED.account_code,
                           tax_type = EXCLUDED.tax_type,
                           updated_at = now()
                    """,
                    (
                        tenant.tenant_id, kind,
                        str(item.get("accountCode") or "").strip(),
                        str(item.get("taxType") or "").strip(),
                    ),
                )
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="xero.mappings_updated",
            resource_type="xero_account_mappings",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/integrations/xero/single-entry", methods=["POST"])
@permission_required("integrations:manage")
def xero_single_entry():
    """Record how the studio resolved the duplicate-feed question.

    Asked before pushing is allowed, because the alternative is discovering the
    answer as two sets of records in a live accounting ledger.
    """

    try:
        payload = _json_payload()
        decision = _clean_text(payload, "decision")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _xero.answer_single_entry(
                conn, tenant.tenant_id,
                decision=decision,
                clearing_account_code=_clean_text(payload, "clearingAccountCode"),
            )
        except _xero.XeroError as exc:
            conn.rollback()
            return _error(str(exc))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="xero.single_entry_answered",
            resource_type="xero_sync_settings",
            resource_id=tenant.tenant_id,
            metadata={"decision": decision},
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/integrations/xero/gate", methods=["POST"])
@permission_required("integrations:manage")
def xero_gate():
    """Advance the wizard: confirm mapping, record the demo run, or push.

    One route for three steps because they are one workflow, and because the
    gate has to be evaluated identically whichever step is being attempted.
    """

    try:
        payload = _json_payload()
        step = _clean_text(payload, "step")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_XERO)
            if step == "confirm_mapping":
                _xero.confirm_mapping(conn, tenant.tenant_id)
            elif step == "demo_run":
                _xero.record_demo_run(conn, tenant.tenant_id)
            elif step == "enable_push":
                _xero.set_push_enabled(conn, tenant.tenant_id, True)
            elif step == "disable_push":
                _xero.set_push_enabled(conn, tenant.tenant_id, False)
            else:
                return _error(f"Unknown step: {step}")
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        except _xero.XeroError as exc:
            conn.rollback()
            return _error(str(exc), 409)

        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"xero.{step}",
            resource_type="xero_sync_settings",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
        status = _xero.gate_status(conn, tenant.tenant_id)
    return jsonify(
        {
            "ok": True,
            "pushEnabled": status.push_enabled,
            "canEnablePush": status.can_enable,
            "blockers": status.blockers(),
        }
    )


@api_v1.route("/integrations/xero/errors", methods=["GET"])
@permission_required("billing:read")
def xero_errors():
    """What did not reach Xero, and why. The studio's queue, not ours."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = _xero.error_queue(conn, tenant.tenant_id)
    return jsonify({"errors": rows})


@api_v1.route("/integrations/xero/errors/<job_id>/replay", methods=["POST"])
@permission_required("integrations:manage")
def xero_replay(job_id: str):
    """Requeue a failed push, keeping its idempotency key so it cannot duplicate."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        _xero.replay(conn, tenant.tenant_id, job_id)
        conn.commit()
    return jsonify({"ok": True})


# ── calendar subscriptions ───────────────────────────────────────────────


@api_v1.route("/calendar/subscriptions", methods=["GET", "POST"])
@permission_required("students:read")
def calendar_subscriptions_route():
    """Issue a family's calendar feed, or list the ones already issued.

    The raw token is returned once, at creation, and never again. A family that
    loses the link gets a new subscription, which also means the lost one can be
    revoked on its own.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(
                conn, tenant.tenant_id, _entitlements.FEATURE_CALENDAR_SUBSCRIPTIONS
            )
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            rows = fetch_all(
                conn,
                """
                SELECT id, scope, label, billing_account_id, student_id, teacher_user_id,
                       created_at, last_fetched_at, fetch_count
                FROM calendar_subscriptions
                WHERE tenant_id = %s AND revoked_at IS NULL
                ORDER BY created_at DESC
                """,
                (tenant.tenant_id,),
            )
            return jsonify({"subscriptions": rows})

        try:
            payload = _json_payload()
            scope = _clean_text(payload, "scope", "family") or "family"
            raw_token, row = _calendar_subs.create(
                conn,
                tenant.tenant_id,
                scope=scope,
                billing_account_id=payload.get("billingAccountId") or None,
                student_id=payload.get("studentId") or None,
                teacher_user_id=payload.get("teacherUserId") or None,
                label=_clean_text(payload, "label"),
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except (ValueError, _calendar_subs.SubscriptionError) as exc:
            conn.rollback()
            return _error(str(exc))
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="calendar_subscription.created",
            resource_type="calendar_subscription",
            resource_id=row["id"],
        )
        conn.commit()

    return jsonify(
        {
            "ok": True,
            "subscription": row,
            # Shown once. The studio hands it to the family; we cannot show it
            # again because only its hash was kept.
            "feedPath": f"/v1/public/calendar/{raw_token}.ics",
        }
    ), 201


@api_v1.route("/calendar/subscriptions/<subscription_id>", methods=["DELETE"])
@permission_required("students:write")
def calendar_subscription_revoke(subscription_id: str):
    """Cut off a feed without erasing the record that it existed."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        _calendar_subs.revoke(conn, tenant.tenant_id, subscription_id)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="calendar_subscription.revoked",
            resource_type="calendar_subscription",
            resource_id=subscription_id,
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/public/calendar/<token>.ics", methods=["GET"])
def public_calendar_feed(token: str):
    """The family's calendar feed.

    Unauthenticated by necessity: a calendar client subscribes with a URL and
    has no session to present. The token is 256 bits, matched by hash, and the
    tenant is read from the row it resolves to — never from anything the request
    supplied, which is what stops a token from one studio being pointed at
    another's data.
    """

    with connect() as conn:
        subscription = _calendar_subs.resolve(conn, token)
        if not subscription:
            # Deliberately the same answer as a revoked or malformed token: a
            # different one would let somebody probe for valid tokens.
            return _error("Calendar not found.", 404)
        document = _calendar_subs.build_document(conn, subscription)
        _calendar_subs.touch(conn, subscription["id"])
        conn.commit()

    response = Response(document.to_ics(), content_type="text/calendar; charset=utf-8")
    response.headers["Content-Disposition"] = f'inline; filename="{document.filename}"'
    # Calendar clients poll on their own schedule; a short cache keeps a
    # re-subscribing client from hammering the feed without making a
    # reschedule wait noticeably longer than the client's own poll interval.
    response.headers["Cache-Control"] = "private, max-age=900"
    return response


# ── recurring private lessons ────────────────────────────────────────────


def _scheduling_error(exc: Exception, status: int = 400):
    """A refused scheduling action is something a studio can fix, not a fault."""

    return _error(str(exc), status)


@api_v1.route("/scheduling/policy", methods=["GET", "PUT"])
@permission_required("scheduling:read")
def scheduling_policy():
    """The four decisions that turn an absence into money."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            return jsonify({"policy": _scheduling.policy(conn, tenant.tenant_id)})

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            saved = _scheduling.save_policy(conn, tenant.tenant_id, payload)
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="scheduling_policy.updated",
            resource_type="scheduling_policy",
            resource_id=tenant.tenant_id,
        )
        conn.commit()
    return jsonify({"ok": True, "policy": saved})


@api_v1.route("/scheduling/series", methods=["GET", "POST"])
@permission_required("scheduling:read")
def scheduling_series():
    """Weekly one-to-one lessons."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)

        if request.method == "GET":
            rows = _scheduling.list_series(
                conn, tenant.tenant_id,
                student_id=(request.args.get("studentId") or "").strip() or None,
            )
            return jsonify({"series": rows})

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            student_id = _clean_text(payload, "studentId")
            start_time = _clean_text(payload, "startTime")
            starts_on = _iso_date(payload, "startsOn")
            if not student_id or not start_time or not starts_on:
                raise ValueError("studentId, startTime and startsOn are required.")
            created = _scheduling.create_series(
                conn,
                tenant.tenant_id,
                student_id=student_id,
                weekday=int(payload.get("weekday", 0)),
                start_time=start_time,
                duration_minutes=_positive_int(payload, "durationMinutes", fallback=30),
                starts_on=starts_on,
                ends_on=_iso_date(payload, "endsOn"),
                teacher_user_id=_clean_text(payload, "teacherUserId") or None,
                course_id=_clean_text(payload, "courseId") or None,
                room=_clean_text(payload, "room"),
                price_aud_cents=payload.get("priceAudCents"),
                note=_clean_text(payload, "note"),
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, TypeError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="lesson_series.created",
            resource_type="lesson_series",
            resource_id=created["id"],
        )
        conn.commit()
    return jsonify({"ok": True, "series": created}), 201


@api_v1.route("/scheduling/series/<series_id>", methods=["PATCH"])
@permission_required("scheduling:write")
def scheduling_series_status(series_id: str):
    """Pause, resume or end a series. Never a delete — see the service."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            updated = _scheduling.set_series_status(
                conn, tenant.tenant_id, series_id,
                status=_clean_text(payload, "status"),
                paused_from=_iso_date(payload, "pausedFrom"),
                paused_to=_iso_date(payload, "pausedTo"),
            )
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action=f"lesson_series.{updated['status']}",
            resource_type="lesson_series",
            resource_id=series_id,
        )
        conn.commit()
    return jsonify({"ok": True, "series": updated})


@api_v1.route("/scheduling/occurrences", methods=["GET"])
@permission_required("scheduling:read")
def scheduling_occurrences():
    """Every private lesson due in a date range, deviations applied."""

    try:
        args = request.args
        start = _iso_date(dict(args), "start", fallback=_date.today())
        end = _iso_date(dict(args), "end", fallback=start + _timedelta(days=13))
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        try:
            rows = _scheduling.occurrences(
                conn, tenant.tenant_id, start=start, end=end,
                series_id=(args.get("seriesId") or "").strip() or None,
                teacher_user_id=(args.get("teacherUserId") or "").strip() or None,
            )
        except _scheduling.SchedulingError as exc:
            return _scheduling_error(exc)
    return jsonify({"start": start.isoformat(), "end": end.isoformat(), "occurrences": rows})


@api_v1.route("/scheduling/occurrences/cancel", methods=["POST"])
@permission_required("scheduling:write")
def scheduling_cancel_occurrence():
    """Record an absence, and the make-up credit it may owe."""

    try:
        payload = _json_payload()
        series_id = _clean_text(payload, "seriesId")
        on_date = _iso_date(payload, "onDate")
        cancelled_by = _clean_text(payload, "cancelledBy")
        if not series_id or not on_date:
            raise ValueError("seriesId and onDate are required.")
    except ValueError as exc:
        return _error(str(exc))

    # Notice is computed here rather than trusted from the browser: a client
    # clock that is a day slow would turn a late cancellation into a free one.
    hours = payload.get("hoursNotice")
    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        if hours is None:
            row = fetch_one(
                conn,
                "SELECT start_time FROM lesson_series WHERE tenant_id = %s AND id = %s",
                (tenant.tenant_id, series_id),
            )
            if row:
                hours = _scheduling.hours_of_notice(
                    lesson_on=on_date, lesson_at=row["start_time"]
                )
        try:
            outcome = _scheduling.cancel_occurrence(
                conn, tenant.tenant_id, series_id,
                on_date=on_date,
                cancelled_by=cancelled_by,
                hours_notice=None if hours is None else float(hours),
                reason=_clean_text(payload, "reason"),
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except (ValueError, TypeError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc, 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="lesson.cancelled",
            resource_type="lesson_exception",
            resource_id=outcome["exceptionId"],
        )
        conn.commit()
    return jsonify({"ok": True, **outcome}), 201


@api_v1.route("/scheduling/exceptions/<exception_id>", methods=["DELETE"])
@permission_required("scheduling:write")
def scheduling_undo_exception(exception_id: str):
    """Undo a recorded change; any credit it granted is cancelled, not deleted."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _scheduling.undo_occurrence(conn, tenant.tenant_id, exception_id)
        except _scheduling.SchedulingError as exc:
            conn.rollback()
            return _scheduling_error(exc, 404)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="lesson.change_undone",
            resource_type="lesson_exception",
            resource_id=exception_id,
        )
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/scheduling/credits", methods=["GET"])
@permission_required("scheduling:read")
def scheduling_credits():
    """Make-up credits owed, with expiry derived at read time."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_RECURRING_LESSONS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        rows = _scheduling.credits(
            conn, tenant.tenant_id,
            student_id=(request.args.get("studentId") or "").strip() or None,
            include_spent=(request.args.get("includeSpent") or "") == "1",
        )
    return jsonify({"credits": rows})


@api_v1.route("/scheduling/credits/<credit_id>/consume", methods=["POST"])
@permission_required("scheduling:write")
def scheduling_consume_credit(credit_id: str):
    """Book a make-up against a credit."""

    try:
        payload = _json_payload()
        on_date = _iso_date(payload, "onDate")
        if not on_date:
            raise ValueError("onDate is required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            booked = _scheduling.consume_credit(
                conn, tenant.tenant_id, credit_id,
                on_date=on_date,
                series_id=_clean_text(payload, "seriesId") or None,
                start_time=_clean_text(payload, "startTime") or None,
                teacher_user_id=_clean_text(payload, "teacherUserId") or None,
                created_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc, 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="makeup_credit.consumed",
            resource_type="makeup_credit",
            resource_id=credit_id,
        )
        conn.commit()
    return jsonify({"ok": True, **booked})


@api_v1.route("/scheduling/terms", methods=["GET", "POST"])
@permission_required("scheduling:read")
def scheduling_terms():
    """The calendar spine billing periods and report cadence both hang off."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "GET":
            return jsonify({"terms": _scheduling.terms(conn, tenant.tenant_id)})

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            starts_on = _iso_date(payload, "startsOn")
            ends_on = _iso_date(payload, "endsOn")
            if not starts_on or not ends_on:
                raise ValueError("startsOn and endsOn are required.")
            created = _scheduling.create_term(
                conn, tenant.tenant_id,
                name=_clean_text(payload, "name"),
                starts_on=starts_on, ends_on=ends_on,
            )
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except (ValueError, _scheduling.SchedulingError) as exc:
            conn.rollback()
            return _scheduling_error(exc, 409)
        conn.commit()
    return jsonify({"ok": True, "term": created}), 201


@api_v1.route("/scheduling/closures", methods=["GET", "POST", "DELETE"])
@permission_required("scheduling:read")
def scheduling_closures():
    """Dates when nothing runs. A closure removes lessons; it does not cancel them."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "GET":
            try:
                args = dict(request.args)
                start = _iso_date(args, "start", fallback=_date.today())
                end = _iso_date(args, "end", fallback=start + _timedelta(days=180))
            except ValueError as exc:
                return _error(str(exc))
            return jsonify({
                "closures": _scheduling.closures(conn, tenant.tenant_id, start=start, end=end)
            })

        try:
            require_permission(getattr(g, "actor", None), "scheduling:write")
            payload = _json_payload()
            on_date = _iso_date(payload, "onDate")
            if not on_date:
                raise ValueError("onDate is required.")
        except PermissionDeniedError as exc:
            return _error(str(exc), 403)
        except ValueError as exc:
            return _error(str(exc))

        if request.method == "DELETE":
            _scheduling.clear_closure(conn, tenant.tenant_id, on_date=on_date)
        else:
            _scheduling.set_closure(
                conn, tenant.tenant_id, on_date=on_date, label=_clean_text(payload, "label")
            )
        conn.commit()
    return jsonify({"ok": True})


# ── progress reports ─────────────────────────────────────────────────────


@api_v1.route("/progress-reports", methods=["POST"])
@permission_required("progress_reports:write")
def progress_report_create():
    """Assemble a period into a draft for a teacher to finish."""

    try:
        payload = _json_payload()
        student_id = _clean_text(payload, "studentId")
        start = _iso_date(payload, "periodStart")
        end = _iso_date(payload, "periodEnd")
        if not student_id or not start or not end:
            raise ValueError("studentId, periodStart and periodEnd are required.")
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_PROGRESS_REPORTS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        report = _progress.create_draft(
            conn,
            tenant.tenant_id,
            student_id,
            period_start=start,
            period_end=end,
            teacher_user_id=getattr(getattr(g, "actor", None), "user_id", None),
        )
        conn.commit()
    return jsonify({"ok": True, "report": report}), 201


@api_v1.route("/progress-reports/<report_id>", methods=["PATCH"])
@permission_required("progress_reports:write")
def progress_report_update(report_id: str):
    """Edit the teacher's comment on a draft."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE progress_reports
                   SET teacher_comment = %s, updated_at = now()
                 WHERE tenant_id = %s AND id = %s AND status = 'draft'
                RETURNING id, status
                """,
                (_clean_text(payload, "teacherComment"), tenant.tenant_id, report_id),
            )
            updated = cur.fetchone()
        if not updated:
            conn.rollback()
            return _error("Only a draft report can be edited.", 409)
        conn.commit()
    return jsonify({"ok": True, "report": updated})


@api_v1.route("/progress-reports/<report_id>/publish", methods=["POST"])
@permission_required("progress_reports:publish")
def progress_report_publish(report_id: str):
    """Freeze a report and release it to the family."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            published = _progress.publish(
                conn, tenant.tenant_id, report_id,
                published_by_user_id=getattr(getattr(g, "actor", None), "user_id", None),
            )
        except _progress.ProgressReportError as exc:
            conn.rollback()
            return _error(str(exc), 409)
        _audit_request(
            conn,
            tenant_id=tenant.tenant_id,
            action="progress_report.published",
            resource_type="progress_report",
            resource_id=report_id,
        )
        conn.commit()
    return jsonify({"ok": True, "report": published})


@api_v1.route("/students/<student_id>/progress-reports", methods=["GET"])
@permission_required("progress_reports:read")
def student_progress_reports(student_id: str):
    """Every report for one student, newest period first.

    Returns the assembled ``content`` alongside the comment because the teacher
    writes *while looking at* the attendance and lesson notes the draft was
    built from. Fetching the evidence in a second call would let the screen
    render a comment box next to an empty panel, which is how reports end up
    saying "good progress this term" and nothing else.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_PROGRESS_REPORTS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        rows = fetch_all(
            conn,
            """
            SELECT r.id, r.status, r.period_start, r.period_end, r.teacher_comment,
                   r.content, r.published_at, r.teacher_user_id, u.full_name AS teacher_name
            FROM progress_reports r
            LEFT JOIN users u ON u.id = r.teacher_user_id
            WHERE r.tenant_id = %s AND r.student_id = %s
            ORDER BY r.period_end DESC, r.created_at DESC
            LIMIT 24
            """,
            (tenant.tenant_id, student_id),
        )
    return jsonify({"reports": rows})


@api_v1.route("/progress-reports/overdue", methods=["GET"])
@permission_required("progress_reports:read")
def progress_reports_overdue():
    """Which reports are due and unwritten, and whose they are."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = _progress.overdue(conn, tenant.tenant_id)
    return jsonify({"overdue": rows})


# ── management reports ───────────────────────────────────────────────────


@api_v1.route("/reports/<report_name>", methods=["GET"])
@permission_required("reports:read")
def management_report(report_name: str):
    """Four reports, each drillable to the rows behind every figure."""

    builders = {
        "revenue": lambda conn, tid, start, end: _reports.revenue(conn, tid, start=start, end=end),
        "receivables": lambda conn, tid, start, end: _reports.receivables(conn, tid, as_of=end),
        "teacher-cost": lambda conn, tid, start, end: _reports.teacher_cost(conn, tid, start=start, end=end),
        "attendance": lambda conn, tid, start, end: _reports.attendance(conn, tid, start=start, end=end),
    }
    builder = builders.get(report_name)
    if builder is None:
        return _error(f"Unknown report: {report_name}", 404)

    try:
        default_start, default_end = _reports.default_period()
        start = _iso_date(request.args, "from") or default_start
        end = _iso_date(request.args, "to") or default_end
    except ValueError as exc:
        return _error(str(exc))

    with connect() as conn:
        tenant = _tenant_context(conn)
        try:
            _require_feature(conn, tenant.tenant_id, _entitlements.FEATURE_REPORTS)
        except _entitlements.FeatureUnavailableError as exc:
            return _feature_error(exc)
        data = builder(conn, tenant.tenant_id, start, end)
    return jsonify({"report": report_name, "from": start.isoformat(), "to": end.isoformat(), **data})


@api_v1.route("/notifications/usage", methods=["GET"])
@permission_required("settings:write")
def notification_usage():
    """This month's message volume and spend, per channel.

    The number a studio needs is not "412 messages" but "$29", and they need it
    before the provider's invoice rather than after.
    """

    with connect() as conn:
        tenant = _tenant_context(conn)
        usage = {
            channel: _channels.month_usage(conn, tenant.tenant_id, channel)
            for channel in ("email", "sms")
        }
        routes = fetch_all(
            conn,
            "SELECT event_key, channels, is_active FROM notification_routes WHERE tenant_id = %s",
            (tenant.tenant_id,),
        )
    return jsonify(
        {
            "usage": usage,
            "routes": routes,
            "defaultRoutes": {
                key: list(value) for key, value in _channels.DEFAULT_ROUTES.items()
            },
        }
    )
