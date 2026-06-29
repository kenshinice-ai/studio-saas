"""StudioSaaS API v1 routes.

These routes are intentionally introduced beside the legacy endpoints. Tenant
APIs require PostgreSQL and explicit tenant resolution; they do not fall back to
the single-studio JSON database.
"""

from flask import Blueprint, jsonify, request

from .config import load_config
from .db import DatabaseUnavailableError, connect, fetch_all, fetch_one
from .tenant_context import TenantResolutionError, resolve_tenant, slug_from_request

api_v1 = Blueprint("studiosaas_api_v1", __name__, url_prefix="/v1")


@api_v1.errorhandler(DatabaseUnavailableError)
def handle_database_unavailable(exc: DatabaseUnavailableError):
    """Return a clear setup error when PostgreSQL is not ready."""

    return jsonify({"error": "database_unavailable", "message": str(exc)}), 503


@api_v1.errorhandler(TenantResolutionError)
def handle_tenant_error(exc: TenantResolutionError):
    """Return a clear tenant error instead of silently picking a default."""

    return jsonify({"error": "tenant_resolution_failed", "message": str(exc)}), 400


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
        cfg = load_config()
        slug, source = slug_from_request(request, cfg)
        tenant = resolve_tenant(conn, slug, source)
        rows = fetch_all(
            conn,
            """
            SELECT id, display_name, first_name, last_name, status, mobile, email,
                   tags, created_at, updated_at
            FROM students
            WHERE tenant_id = %s
            ORDER BY lower(display_name), created_at DESC
            LIMIT 500
            """,
            (tenant.tenant_id,),
        )
    return jsonify({"students": rows})


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


@api_v1.route("/admin/tenants", methods=["GET"])
def admin_tenants_placeholder():
    """Placeholder for Super Admin tenant listing.

    Full super-admin authentication will be wired after the v1 auth layer lands.
    """

    return jsonify(
        {
            "error": "not_implemented",
            "message": "Super Admin authentication is required before listing tenants.",
        }
    ), 501
