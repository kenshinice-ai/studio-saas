"""Tenant resolution for StudioSaaS v1 requests."""

import re
import time
from typing import Any

from flask import Request, g

from .config import StudioSaaSConfig
from .db import fetch_all, fetch_one
from .models import TenantContext

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")


class TenantResolutionError(RuntimeError):
    """Raised when a request does not map to a known tenant."""


class TenantGoneError(RuntimeError):
    """Raised for an address that existed and belongs to no tenant now.

    Distinct from "never existed": a retired address of a deleted tenant is
    kept as a tombstone so it can never be reissued, and a visitor who follows
    a two-year-old QR code deserves 410 rather than 404.
    """


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


# Retired addresses and what each was superseded by. A studio may change its
# address once a year, so this map is tiny and usually empty; it is cached
# because the alternative is a query on every page view of every tenant site.
RETIRED_ADDRESS_TTL = 60
_retired_addresses: dict[str, Any] = {"map": {}, "at": 0.0}


def forget_retired_addresses() -> None:
    """Drop the cache after a rename, for this worker at least."""

    _retired_addresses["at"] = 0.0


def retired_address_map(connect: Any) -> dict[str, str]:
    """Slug → the address that replaced it, or '' when the tenant is gone."""

    now = time.time()
    if now - _retired_addresses["at"] < RETIRED_ADDRESS_TTL:
        return _retired_addresses["map"]
    try:
        with connect() as conn:
            rows = fetch_all(
                conn,
                """
                SELECT a.slug, COALESCE(t.slug, '') AS current_slug
                FROM tenant_slug_aliases a
                LEFT JOIN tenants t ON t.id = a.tenant_id
                WHERE a.is_current = false
                """,
                (),
            )
    except Exception:
        # Including the migration not having run yet: a missing table must not
        # take every tenant page down.
        return _retired_addresses["map"]
    _retired_addresses["map"] = {str(row["slug"]): str(row["current_slug"] or "") for row in rows}
    _retired_addresses["at"] = now
    return _retired_addresses["map"]


def canonical_slug_for(conn: Any, slug: str) -> str | None:
    """Return the address this one has been superseded by, if any.

    ``None`` means the slug is either current or unknown; an empty string
    means it is a tombstone — an address whose tenant no longer exists.
    """

    row = fetch_one(
        conn,
        """
        SELECT a.tenant_id, a.is_current, t.slug AS current_slug
        FROM tenant_slug_aliases a
        LEFT JOIN tenants t ON t.id = a.tenant_id
        WHERE a.slug = %s
        """,
        (slug,),
    )
    if not row:
        return None
    if not row["tenant_id"]:
        return ""
    if row["is_current"]:
        return None
    return str(row["current_slug"] or "")



def bind_tenant_session(conn: Any, tenant_id: str) -> None:
    """Tell the database which tenant this connection is acting for.

    Every tenant-scoped path in the product goes through :func:`resolve_tenant`
    — the 120 authenticated routes reach it via ``_tenant_context``, and the 18
    public ones call it directly. That makes this the one place the row-level
    security variable can be set and have it cover everything.

    ``SET`` rather than ``SET LOCAL`` on purpose. ``SET LOCAL`` dies with the
    transaction, and eleven routes commit and then keep querying; under LOCAL
    those would silently see nothing after their commit. There is no connection
    pool — ``connect()`` opens a connection per ``with`` block and closes it in
    a ``finally`` — so a session-level setting cannot outlive the request.

    That safety depends on there being no pool. If one is ever added, this has
    to become ``SET LOCAL`` plus a re-bind after commit, or the variable will
    ride a pooled connection into the next tenant's request. A test asserts the
    no-pool assumption so the two cannot drift apart silently.
    """

    with conn.cursor() as cur:
        cur.execute("SELECT set_config('studiosaas.tenant_id', %s, false)", (str(tenant_id),))


def bind_user_session(conn: Any, user_id: str) -> None:
    """Tell the database who is asking, for the one policy that needs it.

    Only ``memberships`` reads this. Logging in has to answer "which studios
    does this person belong to" before any tenant is known, so its policy also
    permits reading your own rows. Nothing else consults this variable.
    """

    with conn.cursor() as cur:
        cur.execute("SELECT set_config('studiosaas.user_id', %s, false)", (str(user_id),))


def resolve_tenant(conn: Any, slug: str, source: str) -> TenantContext:
    """Resolve a tenant slug to an active tenant context.

    A retired address resolves to the same tenant. An API call carrying an old
    ``X-Tenant-Slug`` — a Studio Admin tab that was already open when the
    address changed — keeps working rather than logging somebody out.

    Raises:
        TenantResolutionError: If the tenant does not exist or is unavailable.
        TenantGoneError: If the address existed and its tenant is gone.
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
        alias = fetch_one(
            conn,
            """
            SELECT a.tenant_id, t.slug, t.status
            FROM tenant_slug_aliases a
            LEFT JOIN tenants t ON t.id = a.tenant_id
            WHERE a.slug = %s AND a.is_current = false
            """,
            (slug,),
        )
        if alias and not alias["tenant_id"]:
            raise TenantGoneError(f"Address '{slug}' is no longer in use.")
        if not alias:
            raise TenantResolutionError(f"Tenant '{slug}' was not found.")
        if alias["status"] not in ("trial", "onboarding", "active", "past_due"):
            raise TenantResolutionError(f"Tenant '{slug}' is not active.")
        bind_tenant_session(conn, str(alias["tenant_id"]))
        return TenantContext(
            tenant_id=str(alias["tenant_id"]), slug=slug, source=source,
            canonical_slug=str(alias["slug"]),
        )
    if row["status"] not in ("trial", "onboarding", "active", "past_due"):
        raise TenantResolutionError(f"Tenant '{slug}' is not active.")
    bind_tenant_session(conn, str(row["id"]))
    return TenantContext(
        tenant_id=str(row["id"]), slug=row["slug"], source=source,
        canonical_slug=str(row["slug"]),
    )


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
