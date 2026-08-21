"""api_v1.platform — mechanically split from api_v1.py (v10.11.0). Pure move."""
import json
import os
import re
import secrets
import sys
import time
import hashlib
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
from ..errors import api_error
from ..lifecycle import (
    canonical_subscription_status,
    validate_subscription_dates,
    validate_registration_transition,
    validate_tenant_subscription_pair,
    validate_tenant_transition,
)
from ..services import entitlements as _entitlements
from ..services.tenant_archive import (
    TenantArchiveError,
    archive_tenant,
    permanently_delete_tenant,
    restore_tenant,
)
from ..services.subscription_settlement import (
    ACTIONABLE as SETTLEMENT_ACTIONABLE,
    SETTLEMENT_QUERY,
    settlement_report,
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
from ._shared import (
    _audit,
    _audit_request,
    _clean_text,
    _error,
    _hash_password,
    _json_payload,
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
    _parse_pagination,
    _plan_change_impact,
    _preset_for,
    _refresh_tenant_workspace,
    _tenant_context,
    _validate_optional_email,
    _workspace_for,
    api_v1,
)



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
#: Kept for callers that still import it; the phrase actually required is the
#: one belonging to the tenant being reset (see reset_demo_tenant).
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
    # one dirname deeper since the api_v1 package split — same target as before
    scripts = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    try:
        from reset_professional_demo import (
            _credentials_path, confirmation_for_pack, pack_for_slug, reset_showcase,
        )
    except Exception:
        current_app.logger.exception("demo reset seeder is unavailable")
        return _error("The demonstration seeder is not available in this build.", 500)

    # The tenant chooses the pack. A demonstration tenant that no pack claims is
    # a flag someone set by hand, and rebuilding it as some other studio is the
    # one outcome worse than refusing.
    pack = pack_for_slug(row["slug"])
    if pack is None:
        return _error(
            f"No demonstration pack owns '{row['slug']}'. Reset is refused.", 400
        )
    required = confirmation_for_pack(pack)
    if str(payload.get("confirm") or "").strip() != required:
        return _error(f"Type {required} to confirm.", 400)

    started = time.monotonic()
    try:
        result = reset_showcase(_credentials_path(None), pack=pack)
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


