"""api_v1._shared — mechanically split from api_v1.py (v10.11.0). Pure move."""
import ipaddress
import json
import os
import re
import secrets
import threading
import time
import hashlib
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
from pathlib import Path, PurePath
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
from werkzeug.utils import secure_filename
from ..auth import (
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
from ..config import is_standalone, load_config, show_producer_credit, studiosaas_mode
from ..db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from ..errors import api_error
from ..netaddr import client_ip_from
from ..services import entitlements as _entitlements
from .. import video_embed
from ..presets import (
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
from ..services.media import (
    MediaQuotaExceededError,
    MediaUploadError,
    send_media_asset,
    store_media_asset,
)
from ..tenant_context import (
    bind_user_session as _bind_user_session,
    bind_tenant_session as _bind_tenant_session,
    TenantGoneError,
    TenantResolutionError,
    canonical_slug_for,
    forget_retired_addresses,
    resolve_tenant,
    slug_from_request,
)
from ..workspaces import (
    WorkspaceError,
    copy_tenant_workspace,
    discard_tenant_workspace,
    ensure_tenant_workspace,
    validate_tenant_slug,
)
import os as _os


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

    The trust decision lives in studiosaas/netaddr.py so this module and the
    legacy app cannot drift — a peer trusted by one and not the other would let
    an attacker pick whichever entry point believed them.
    """

    return client_ip_from(request.remote_addr, request.headers)





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




def _json_payload() -> dict:
    """Return a JSON object payload or raise a request error response."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload




def _strict_boolean(payload: dict, key: str, *, default: bool) -> bool:
    """Read a JSON boolean without treating strings such as ``\"false\"`` as true."""

    if key not in payload:
        return default
    value = payload[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean.")
    return value




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
    # These two are BILINGUAL PAIRS, and reading them with _first_text was a
    # silent corruption: that helper ends in `str(value)`, so a {"zh": …,
    # "en": …} arrived as the literal text `{'en': "…", 'zh': "…"}` — a Python
    # repr — and `limit` then truncated the repr mid-string. The value went
    # straight into <title>, og:title and the meta description, so a studio saw
    # a dict in its browser tab, in its bookmarks, in Google's result and in
    # every WhatsApp/WeChat share card.
    #
    # Both readers already handled the pair (`_pick_pair` server-side,
    # `pickLocalized` in the portal), which is why this looked like a rendering
    # bug for as long as nobody compared the stored shape to the written one.
    # Only tenants that actually FILLED these fields were affected — doing the
    # right thing was the trigger.
    # _localized_pair reads a single key; _first_text accepted the camelCase
    # alias too. Dropping that alias would be the payload-rebuild defect all
    # over again — the console posts one spelling, the reader looks for the
    # other, and the field is wiped on every save. So resolve the alias first.
    profile["seo_title"] = _localized_pair(
        {"seo_title": data.get("seo_title", data.get("seoTitle"))}, "seo_title", limit=120
    )
    profile["seo_description"] = _localized_pair(
        {"seo_description": data.get("seo_description", data.get("seoDescription"))},
        "seo_description", limit=200,
    )
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
    """Write an audit log row with request actor and IP when available.

    `audit_logs` is tenant-scoped, and this helper is called from routes that
    never resolve a tenant from a slug — ending a support session, platform
    administration, the public forms. Those have no tenant variable bound, so
    the insert would be refused by the row-level security policy.

    It does not need resolving: the caller passes the tenant in. Binding it
    here means every audit write from every route works, rather than 40-odd
    call sites each remembering to do it.
    """

    if tenant_id:
        _bind_tenant_session(conn, str(tenant_id))
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





def _cacheable_json(payload: dict, *, max_age: int, immutable: bool = False):
    """Answer with an ETag so a repeat visitor gets 304 instead of the body.

    Measured on production before this existed: /v1/industry-presets returned
    88,625 bytes to an unauthenticated caller with no Cache-Control, no ETag and
    no rate limit — eight rapid requests, eight full bodies. /brand was 42,288
    bytes on the same terms, and every visitor to a studio's home page fetched
    all of it again. Neither changes more than a few times a week.

    The ETag is over the serialised body, so it moves exactly when the answer
    does; correctness never depends on the max-age being tuned right.
    """

    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    etag = '"' + hashlib.sha256(body.encode("utf-8")).hexdigest()[:32] + '"'
    if request.headers.get("If-None-Match", "") == etag:
        response = make_response("", 304)
    else:
        response = make_response(body, 200)
        response.headers["Content-Type"] = "application/json"
    response.headers["ETag"] = etag
    directive = f"public, max-age={max_age}"
    if immutable:
        directive += ", immutable"
    else:
        directive += f", stale-while-revalidate={max_age * 4}"
    response.headers["Cache-Control"] = directive
    # These answers do not vary by who is asking, and Vary: Cookie would stop
    # every shared cache from ever reusing them.
    response.headers.pop("Vary", None)
    return response




def _tenant_context(conn):
    """Resolve the tenant for a tenant-scoped request."""

    cfg = load_config()
    slug, source = slug_from_request(request, cfg)
    return resolve_tenant(conn, slug, source)




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




def _hash_password(password: str) -> str:
    """Hash a password using the canonical v1 PBKDF2 auth format."""

    return _auth_hash_password(password)




def _verify_password(password: str, expected_hash: str) -> bool:
    """Verify a password hash without mutating the database."""

    ok, _needs_upgrade = _auth_verify_password(password, expected_hash)
    return ok



# one level deeper since the api_v1 package split — same target as before
UPLOAD_DIR = _os.path.join(_os.path.dirname(__file__), "..", "..", "static", "uploads")

_os.makedirs(UPLOAD_DIR, exist_ok=True)



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


