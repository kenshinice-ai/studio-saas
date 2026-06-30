"""StudioSaaS API v1 routes.

These routes are intentionally introduced beside the legacy endpoints. Tenant
APIs require PostgreSQL and explicit tenant resolution; they do not fall back to
the single-studio JSON database.
"""

import json
import re

from flask import Blueprint, current_app, g, jsonify, request

from .config import load_config
from .db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from .tenant_context import TenantResolutionError, resolve_tenant, slug_from_request
from .workspaces import WorkspaceError, ensure_tenant_workspace

api_v1 = Blueprint("studiosaas_api_v1", __name__)
api_v1_by_slug = Blueprint("studiosaas_api_v1_by_slug", __name__)


@api_v1.url_value_preprocessor
def pull_tenant_slug(endpoint, values):
    """Store `/s/<tenant_slug>/v1/...` slugs without passing them to views."""

    if values and "tenant_slug" in values:
        g.path_tenant_slug = values.pop("tenant_slug")


@api_v1_by_slug.url_value_preprocessor
def pull_slug_route_tenant(endpoint, values):
    """Store slug-prefix route values without passing them to views."""

    if values and "tenant_slug" in values:
        g.path_tenant_slug = values.pop("tenant_slug")


@api_v1.errorhandler(DatabaseUnavailableError)
def handle_database_unavailable(exc: DatabaseUnavailableError):
    """Return a clear setup error when PostgreSQL is not ready."""

    return jsonify({"error": "database_unavailable", "message": str(exc)}), 503


@api_v1.errorhandler(TenantResolutionError)
def handle_tenant_error(exc: TenantResolutionError):
    """Return a clear tenant error instead of silently picking a default."""

    return jsonify({"error": "tenant_resolution_failed", "message": str(exc)}), 400


api_v1_by_slug.register_error_handler(
    DatabaseUnavailableError,
    handle_database_unavailable,
)
api_v1_by_slug.register_error_handler(
    TenantResolutionError,
    handle_tenant_error,
)

TENANT_STATUSES = {"trial", "active", "past_due", "paused", "cancelled"}
SUBSCRIPTION_STATUSES = {"trialing", "active", "past_due", "paused", "cancelled"}


def _json_payload() -> dict:
    """Return a JSON object payload or raise a request error response."""

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")
    return payload


def _clean_text(payload: dict, key: str, default: str = "") -> str:
    """Read a trimmed text field from a request payload."""

    value = payload.get(key, default)
    return str(value if value is not None else "").strip()


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
    return {
        "name": name,
        "slug": slug,
        "status": status,
        "plan_code": plan_code,
        "subscription_status": subscription_status,
        "starts_at": payload.get("startsAt") or payload.get("starts_at"),
        "ends_at": payload.get("endsAt") or payload.get("ends_at"),
        "trial_ends_at": payload.get("trialEndsAt") or payload.get("trial_ends_at"),
        "current_period_ends_at": payload.get("currentPeriodEndsAt")
        or payload.get("current_period_ends_at"),
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


def _error(message: str, status: int = 400):
    """Return a consistent JSON error response."""

    return jsonify({"error": "invalid_request", "message": message}), status


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
def get_tenant():
    """Return the current tenant's public and operational settings."""

    with connect() as conn:
        row = _tenant_response(conn)
    return jsonify({"tenant": row})


@api_v1.route("/tenant", methods=["PATCH"])
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
                   settings->>'logo_url' AS logo_url
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
        plan_code = _clean_text(payload, "planCode", current["plan_code"]).lower()
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
                    settings = jsonb_set(settings, '{logo_url}', to_jsonb(%s::text), true),
                    updated_at = now()
                WHERE id = %s
                """,
                (
                    _clean_text(payload, "name", current["name"]),
                    plan_code,
                    _clean_text(payload, "primaryColor", current["primary_color"]),
                    _clean_text(payload, "secondaryColor", current["secondary_color"]),
                    _clean_text(payload, "welcomeMessage", current["welcome_message"]),
                    _clean_text(payload, "contactPhone", current["contact_phone"]),
                    _clean_text(payload, "contactEmail", current["contact_email"]),
                    _clean_text(payload, "address", current["address"]),
                    _clean_text(payload, "timezone", current["timezone"]),
                    _clean_text(payload, "logoUrl", current["logo_url"] or ""),
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
            }
        }
    )


@api_v1.route("/students", methods=["GET"])
def list_students():
    """List students for the resolved tenant."""

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
            LEFT JOIN credit_accounts ca ON ca.student_id = s.id
            WHERE s.tenant_id = %s
            ORDER BY lower(display_name), created_at DESC
            LIMIT 500
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"students": rows})


@api_v1.route("/students/<student_id>", methods=["GET"])
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
            LEFT JOIN credit_accounts ca ON ca.student_id = s.id
            WHERE s.tenant_id = %s AND s.id = %s
            """,
            (tenant.tenant_id, student_id),
        )
    if not row:
        return jsonify({"error": "not_found", "message": "Student was not found."}), 404
    return jsonify({"student": row})


@api_v1.route("/students/<student_id>/credits", methods=["GET"])
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
            WHERE tenant_id = %s AND student_id = %s
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
def create_course():
    """Create a course for the resolved tenant."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    name = _clean_text(payload, "name")
    if not name:
        return _error("Course name is required.")
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
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    name,
                    _clean_text(payload, "description"),
                    _clean_text(payload, "category"),
                    _clean_text(payload, "ageRange"),
                    int(payload.get("durationMinutes") or 60),
                    _clean_text(payload, "creditUnit", "credits"),
                    float(payload.get("defaultCreditDebit") or 1),
                    int(round(float(payload.get("priceAud") or 0) * 100)),
                    bool(payload.get("isActive", True)),
                ),
            )
            course_id = cur.fetchone()["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="course.created", resource_type="course", resource_id=course_id)
        conn.commit()
    return jsonify({"ok": True, "id": course_id}), 201


@api_v1.route("/courses/<course_id>", methods=["PATCH", "DELETE"])
def mutate_course(course_id: str):
    """Update or delete a course for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            with conn.cursor() as cur:
                cur.execute("DELETE FROM courses WHERE tenant_id = %s AND id = %s", (tenant.tenant_id, course_id))
                if cur.rowcount == 0:
                    return _error("Course was not found.", 404)
            _audit(conn, tenant_id=tenant.tenant_id, action="course.deleted", resource_type="course", resource_id=course_id)
            conn.commit()
            return jsonify({"ok": True})
        try:
            payload = _json_payload()
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
                """,
                (
                    _clean_text(payload, "name"),
                    _clean_text(payload, "description"),
                    _clean_text(payload, "category"),
                    _clean_text(payload, "ageRange"),
                    int(payload.get("durationMinutes") or 60),
                    _clean_text(payload, "creditUnit", "credits"),
                    float(payload.get("defaultCreditDebit") or 1),
                    int(round(float(payload.get("priceAud") or 0) * 100)),
                    bool(payload.get("isActive", True)),
                    tenant.tenant_id,
                    course_id,
                ),
            )
            if cur.rowcount == 0:
                return _error("Course was not found.", 404)
        _audit(conn, tenant_id=tenant.tenant_id, action="course.updated", resource_type="course", resource_id=course_id)
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/packages", methods=["GET"])
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
def create_package():
    """Create a package for the resolved tenant."""

    try:
        payload = _json_payload()
    except ValueError as exc:
        return _error(str(exc))
    name = _clean_text(payload, "name")
    if not name:
        return _error("Package name is required.")
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
                RETURNING id
                """,
                (
                    tenant.tenant_id,
                    name,
                    float(payload.get("credits") or 1),
                    int(round(float(payload.get("priceAud") or 0) * 100)),
                    payload.get("expiresAfterDays") or None,
                    bool(payload.get("isActive", True)),
                ),
            )
            package_id = cur.fetchone()["id"]
        _audit(conn, tenant_id=tenant.tenant_id, action="package.created", resource_type="package", resource_id=package_id)
        conn.commit()
    return jsonify({"ok": True, "id": package_id}), 201


@api_v1.route("/packages/<package_id>", methods=["PATCH", "DELETE"])
def mutate_package(package_id: str):
    """Update or delete a package for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        if request.method == "DELETE":
            with conn.cursor() as cur:
                cur.execute("DELETE FROM packages WHERE tenant_id = %s AND id = %s", (tenant.tenant_id, package_id))
                if cur.rowcount == 0:
                    return _error("Package was not found.", 404)
            _audit(conn, tenant_id=tenant.tenant_id, action="package.deleted", resource_type="package", resource_id=package_id)
            conn.commit()
            return jsonify({"ok": True})
        try:
            payload = _json_payload()
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
                """,
                (
                    _clean_text(payload, "name"),
                    float(payload.get("credits") or 1),
                    int(round(float(payload.get("priceAud") or 0) * 100)),
                    payload.get("expiresAfterDays") or None,
                    bool(payload.get("isActive", True)),
                    tenant.tenant_id,
                    package_id,
                ),
            )
            if cur.rowcount == 0:
                return _error("Package was not found.", 404)
        _audit(conn, tenant_id=tenant.tenant_id, action="package.updated", resource_type="package", resource_id=package_id)
        conn.commit()
    return jsonify({"ok": True})


@api_v1.route("/registrations", methods=["GET"])
def list_registrations():
    """List recent public registration submissions for the resolved tenant."""

    with connect() as conn:
        tenant = _tenant_context(conn)
        rows = fetch_all(
            conn,
            """
            SELECT id, status, first_name, last_name, parent_name, mobile,
                   email, message, submitted_at
            FROM registrations
            WHERE tenant_id = %s
            ORDER BY submitted_at DESC
            LIMIT 100
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"registrations": rows})


@api_v1.route("/portfolio", methods=["GET"])
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
                (SELECT count(*) FROM credit_accounts WHERE tenant_id = %s AND balance <= low_balance_threshold) AS low_balance
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
                   settings->>'logo_url' AS logo_url
            FROM tenants
            WHERE id = %s
            """,
            (tenant.tenant_id,),
        )
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
            LEFT JOIN credit_accounts ca ON ca.student_id = s.id
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
    return jsonify({"match": True, "student": row})


@api_v1.route("/plans", methods=["GET"])
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
def admin_tenants():
    """List tenants for the local Super Admin prototype."""

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
                   t.settings->>'workspace_path' AS workspace_path,
                   t.created_at
            FROM tenants t
            LEFT JOIN tenant_usage u ON u.tenant_id = t.id
            LEFT JOIN subscriptions s ON s.tenant_id = t.id
            ORDER BY t.created_at DESC
            """,
            (),
        )
    return jsonify({"tenants": rows})


@api_v1.route("/admin/tenants", methods=["POST"])
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
                INSERT INTO tenants (name, slug, status, plan_code, welcome_message)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    data["name"],
                    data["slug"],
                    data["status"],
                    data["plan_code"],
                    f"Welcome to {data['name']}.",
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
def mutate_tenant(tenant_id: str):
    """Update or delete a tenant from Super Admin."""

    with connect() as conn:
        if request.method == "DELETE":
            existing = fetch_one(conn, "SELECT name FROM tenants WHERE id = %s", (tenant_id,))
            if not existing:
                return _error("Tenant was not found.", 404)
            _audit(
                conn,
                tenant_id=tenant_id,
                action="tenant.deleted",
                resource_type="tenant",
                resource_id=tenant_id,
                metadata={"name": existing["name"]},
            )
            with conn.cursor() as cur:
                cur.execute("DELETE FROM tenants WHERE id = %s", (tenant_id,))
            conn.commit()
            return jsonify({"ok": True})
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
                    settings = jsonb_set(settings, '{workspace_path}', to_jsonb(%s::text), true),
                    updated_at = now()
                WHERE id = %s
                """,
                (data["name"], data["status"], data["plan_code"], workspace_path, tenant_id),
            )
            if cur.rowcount == 0:
                return _error("Tenant was not found.", 404)
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


@api_v1.route("/admin/usage", methods=["GET"])
def admin_usage():
    """Return aggregate usage for the local Super Admin prototype."""

    with connect() as conn:
        row = fetch_one(
            conn,
            """
            SELECT
                (SELECT count(*) FROM tenants) AS tenants,
                (SELECT count(*) FROM students) AS students,
                (SELECT count(*) FROM portfolio_items) AS portfolio_items,
                (SELECT COALESCE(sum(storage_used_mb), 0) FROM tenant_usage) AS storage_used_mb
            """,
            (),
        )
    return jsonify({"usage": row})


@api_v1.route("/admin/audit-logs", methods=["GET"])
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


for rule, view_func in (
    ("/health", health),
    ("/tenant", get_tenant),
    ("/tenant/brand", get_tenant_brand),
    ("/dashboard", tenant_dashboard),
    ("/students", list_students),
    ("/students/<student_id>", get_student),
    ("/students/<student_id>/credits", get_student_credits),
    ("/courses", list_courses),
    ("/packages", list_packages),
    ("/registrations", list_registrations),
    ("/portfolio", list_portfolio),
):
    api_v1_by_slug.add_url_rule(rule, view_func=view_func, methods=["GET"])

for rule, view_func, methods in (
    ("/tenant", update_tenant, ["PATCH"]),
    ("/courses", create_course, ["POST"]),
    ("/courses/<course_id>", mutate_course, ["PATCH", "DELETE"]),
    ("/packages", create_package, ["POST"]),
    ("/packages/<package_id>", mutate_package, ["PATCH", "DELETE"]),
):
    api_v1_by_slug.add_url_rule(rule, view_func=view_func, methods=methods)
