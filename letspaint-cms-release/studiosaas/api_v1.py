"""StudioSaaS API v1 routes.

These routes are intentionally introduced beside the legacy endpoints. Tenant
APIs require PostgreSQL and explicit tenant resolution; they do not fall back to
the single-studio JSON database.
"""

from flask import Blueprint, g, jsonify, request

from .config import load_config
from .db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from .tenant_context import TenantResolutionError, resolve_tenant, slug_from_request

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
        SELECT id, name, slug, status, plan_code, primary_color, secondary_color,
               welcome_message, contact_phone, contact_email, address, timezone
        FROM tenants
        WHERE id = %s
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
                   contact_phone, contact_email, address
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
                   t.created_at
            FROM tenants t
            LEFT JOIN tenant_usage u ON u.tenant_id = t.id
            ORDER BY t.created_at DESC
            """,
            (),
        )
    return jsonify({"tenants": rows})


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
