"""api_v1.tenant — mechanically split from api_v1.py (v10.11.0). Pure move."""
import json
import re
import time
import uuid as _uuid
from datetime import date as _date, datetime as _datetime, timedelta as _timedelta, timezone as _timezone
from flask import Blueprint, Response, current_app, g, jsonify, make_response, request, send_from_directory
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
from ..models import Role
from .. import palette
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
import uuid as _uuid
from ._shared import (
    MEDIA_UPLOAD_LIMITS,
    _active_publication_consent,
    _audit,
    _audit_request,
    _cacheable_json,
    _class_time,
    _clean_text,
    _client_ip,
    _default_faq_items,
    _default_hero_profile,
    _default_principal_profile,
    _default_registration_profile,
    _default_visual_theme,
    _default_website_profile,
    _error,
    _json_payload,
    _legacy_identity_copy,
    _media_error,
    _media_token,
    _normalize_category,
    _normalize_copy_pack,
    _normalize_faq_items,
    _normalize_hero_profile,
    _normalize_localized_copy,
    _normalize_message_templates,
    _normalize_principal_profile,
    _normalize_registration_profile,
    _normalize_visual_theme,
    _normalize_website_profile,
    _plan_feature_enabled,
    _preset_for,
    _rate_limited,
    _refresh_tenant_workspace,
    _store_media_asset,
    _tenant_context,
    _tenant_timezone,
    _validate_hex_color,
    _validate_logo_url,
    _validate_optional_email,
    _validated_timezone,
    api_v1,
    showcase_limit_for,
)



def _media_id_from_token(value: str) -> str:
    """Extract a media asset id from a legacy-compatible media token."""

    text = str(value or "").strip()
    if text.startswith("media:"):
        return text.split(":", 1)[1].strip()
    return ""




def _public_visibility(value) -> str:
    """Map a public-gallery toggle to the persisted portfolio visibility."""

    if isinstance(value, bool):
        return "shared" if value else "private"
    return "shared" if str(value or "").strip().lower() in {"1", "true", "yes", "on", "shared"} else "private"




@api_v1.route("/industry-presets", methods=["GET"])
def industry_presets():
    """Return the shared onboarding, copy, and theme presets.

    Public, unauthenticated, 88KB, and identical for every caller — which made
    it the cheapest amplifier on the surface. It is now conditional, and shares
    the public rate limiter so a flood costs the sender something too.
    """

    if _rate_limited(f"presets:{_client_ip()}", 60):
        return _error("Too many requests. Please slow down.", 429)
    return _cacheable_json(
        {"presets": public_industry_presets(), "styles": public_visual_style_presets()},
        max_age=900,
    )




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




@api_v1.route("/tenant", methods=["GET"])
@auth_required
def get_tenant():
    """Return the current tenant's public and operational settings."""

    with connect() as conn:
        row = _tenant_response(conn)
    return jsonify({"tenant": row, "settings": row})




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
               ct.fee_aud_cents, ct.note, actor.email AS actor_email,
               to_char(COALESCE(att.class_date,
                                (ct.occurred_at AT TIME ZONE %s)::date),
                       'DD/MM/YYYY') ||
               to_char(ct.occurred_at AT TIME ZONE %s,
                       ', HH24:MI:SS') AS occurred_display,
               att.id AS attendance_id
        FROM credit_transactions ct
        JOIN students s ON s.id = ct.student_id
        -- v10.13: the ledger has carried actor_user_id on check-ins for some
        -- time and now carries it on manual adjustments too, but this query
        -- never selected it — so the operations log rendered 操作人 for
        -- audit-derived rows and left it blank for every movement of credit.
        -- Stored is not shown. LEFT JOIN because rows written before the
        -- column was populated legitimately have no actor.
        LEFT JOIN users actor ON actor.id = ct.actor_user_id
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
                "actorEmail": row["actor_email"] or "",
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
    # 助教 sees exactly what the teacher sees. ROLE_PERMISSIONS makes STAFF a
    # strict subset of TEACHER, and this projection is the other half of the
    # role model — leaving STAFF out of this branch would hand an assistant
    # the package list, the enquiry inbox and every log row with the fee on
    # it, which is strictly MORE than the teacher they assist gets.
    if role is Role.TEACHER or role is Role.STAFF:
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


