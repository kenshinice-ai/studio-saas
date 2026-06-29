"""Tenant resolution for StudioSaaS v1 requests."""

import re
from typing import Any

from flask import Request, g

from .config import StudioSaaSConfig
from .db import fetch_one
from .models import TenantContext

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


class TenantResolutionError(RuntimeError):
    """Raised when a request does not map to a known tenant."""


def slug_from_request(req: Request, cfg: StudioSaaSConfig) -> tuple[str, str]:
    """Extract a tenant slug from path, header, or subdomain.

    Resolution order:
        1. `/s/<tenant_slug>/...` path prefix.
        2. `X-Tenant-Slug` header.
        3. Host subdomain when STUDIOSAAS_PUBLIC_BASE_DOMAIN is configured.

    Raises:
        TenantResolutionError: If no valid tenant slug is present.
    """

    path_slug = getattr(g, "path_tenant_slug", "")
    if path_slug:
        if not SLUG_RE.match(path_slug):
            raise TenantResolutionError("Invalid tenant slug in path.")
        return path_slug, "path"

    path_match = re.match(r"^/s/([a-z0-9][a-z0-9-]{1,62})(?:/|$)", req.path or "")
    if path_match:
        return path_match.group(1), "path"

    header_slug = (req.headers.get("X-Tenant-Slug") or "").strip().lower()
    if header_slug:
        if not SLUG_RE.match(header_slug):
            raise TenantResolutionError("Invalid X-Tenant-Slug header.")
        return header_slug, "header"

    host = (req.host or "").split(":")[0].lower()
    base = cfg.public_base_domain.lower().strip()
    if base and host.endswith("." + base):
        subdomain = host[: -(len(base) + 1)]
        if "." not in subdomain and SLUG_RE.match(subdomain):
            return subdomain, "subdomain"

    raise TenantResolutionError(
        "Tenant context is required. Use /s/<tenant_slug>, X-Tenant-Slug, "
        "or a configured tenant subdomain."
    )


def resolve_tenant(conn: Any, slug: str, source: str) -> TenantContext:
    """Resolve a tenant slug to an active tenant context.

    Raises:
        TenantResolutionError: If the tenant does not exist or is unavailable.
    """

    row = fetch_one(
        conn,
        """
        SELECT id, slug, status
        FROM tenants
        WHERE slug = %s
        """,
        (slug,),
    )
    if not row:
        raise TenantResolutionError(f"Tenant '{slug}' was not found.")
    if row["status"] not in ("trial", "active", "past_due"):
        raise TenantResolutionError(f"Tenant '{slug}' is not active.")
    return TenantContext(tenant_id=str(row["id"]), slug=row["slug"], source=source)


def set_current_tenant(ctx: TenantContext) -> None:
    """Store the resolved tenant on Flask's request context."""

    g.tenant = ctx


def current_tenant() -> TenantContext:
    """Return the tenant for the current request.

    Raises:
        TenantResolutionError: If middleware did not set a tenant.
    """

    tenant = getattr(g, "tenant", None)
    if not tenant:
        raise TenantResolutionError("Tenant has not been resolved for this request.")
    return tenant
