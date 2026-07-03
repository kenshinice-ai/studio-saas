"""Role and permission checks for StudioSaaS v1.

This module provides authentication and authorization decorators for the
StudioSaaS v1 API.  It reads the Flask session populated by ``auth_login``
and resolves the actor's role from the ``memberships`` table.
"""

import hashlib
import secrets
from functools import wraps
from typing import Any, Callable, TypeVar

from flask import Flask, current_app, g, request

from .errors import api_error
from .models import ActorContext, Role
from .db import DatabaseUnavailableError, fetch_one

F = TypeVar("F", bound=Callable[..., Any])


class PermissionDeniedError(RuntimeError):
    """Raised when an actor lacks permission for an operation."""


ROLE_PERMISSIONS: dict[Role, set[str]] = {
    Role.SUPER_ADMIN: {"*"},
    Role.OWNER: {
        "tenant:read",
        "tenant:update",
        "students:read",
        "students:write",
        "credits:write",
        "portfolio:write",
        "registrations:write",
        "settings:write",
        "plans:read",
    },
    Role.STAFF: {
        "students:read",
        "students:write",
        "credits:write",
        "portfolio:write",
        "registrations:write",
        "plans:read",
    },
    Role.PARENT: {
        "student:self:read",
        "portfolio:self:read",
    },
}

PBKDF2_ITERATIONS = 600_000


def hash_password(password: str) -> str:
    """Hash a login password with PBKDF2-HMAC-SHA256 and a random salt.

    The database representation is ``pbkdf2$<iterations>$<salt_hex>$<hash_hex>``.
    It matches the canonical local CMS helper format while giving every v1
    account its own salt.
    """

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def is_legacy_sha256_hash(value: str) -> bool:
    """Return true for the old unsalted v1 SHA-256 password hash format."""

    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text.lower())


def verify_password(password: str, expected_hash: str) -> tuple[bool, bool]:
    """Verify a login password and report whether the stored hash is legacy.

    Returns:
        ``(ok, needs_upgrade)`` where ``needs_upgrade`` is true only after a
        successful verification against an older hash format. Callers should
        rewrite that stored hash with :func:`hash_password`.
    """

    stored = str(expected_hash or "")
    if stored.startswith("pbkdf2$"):
        try:
            _, iterations, salt_hex, digest_hex = stored.split("$", 3)
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iterations),
            )
        except (TypeError, ValueError):
            return False, False
        return secrets.compare_digest(digest.hex(), digest_hex), False

    if stored.startswith("$2b$") or stored.startswith("$2a$") or stored.startswith("$2y$"):
        try:
            import bcrypt as _bcrypt
        except ImportError:
            return False, False
        return bool(_bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))), True

    if is_legacy_sha256_hash(stored):
        legacy_digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return secrets.compare_digest(legacy_digest, stored), True

    return False, False


def require_permission(actor: ActorContext, permission: str) -> None:
    """Validate that an actor has a named permission.

    Raises:
        PermissionDeniedError: If the actor does not have permission.
    """

    allowed = ROLE_PERMISSIONS.get(actor.role, set())
    if "*" in allowed or permission in allowed:
        return
    raise PermissionDeniedError(
        f"Role '{actor.role.value}' does not have permission '{permission}'."
    )


def _resolve_actor(user_id: str, tenant_id: str | None = None) -> ActorContext | None:
    """Resolve an ActorContext from the database given a user_id.

    Args:
        user_id: The user's ID from the session.
        tenant_id: Optional tenant ID to scope the membership check.

    When ``tenant_id`` is provided:
    - A super_admin is allowed access to any tenant.
    - Non-super-admin users must have an active membership in the
      requested tenant; access is denied otherwise.

    When ``tenant_id`` is *not* provided (e.g. platform-level routes),
    the user's first active membership is returned.

    Returns None if the user has no qualifying membership.
    """

    try:
        from .db import connect as db_connect
    except ImportError:
        return None

    with db_connect() as conn:
        if tenant_id:
            # Tenant-scoped resolution:
            # 1) Super admins can access every tenant, even if they also have
            #    a lower role on the target tenant. The canonical platform
            #    membership has tenant_id IS NULL; per-tenant super_admin rows
            #    are honoured for backward compatibility.
            super_admin = fetch_one(
                conn,
                """
                SELECT role FROM memberships
                WHERE user_id = %s
                  AND role = 'super_admin'
                  AND status = 'active'
                ORDER BY CASE WHEN tenant_id IS NULL THEN 0 ELSE 1 END
                LIMIT 1
                """,
                (user_id,),
            )
            if super_admin:
                return ActorContext(
                    user_id=user_id,
                    role=Role(super_admin["role"]),
                    tenant_id=tenant_id,
                )

            # 2) Check if user has an active membership in this specific tenant.
            member = fetch_one(
                conn,
                """
                SELECT role FROM memberships
                WHERE user_id = %s AND tenant_id = %s AND status = 'active'
                """,
                (user_id, tenant_id),
            )
            if member:
                return ActorContext(
                    user_id=user_id,
                    role=Role(member["role"]),
                    tenant_id=tenant_id,
                )

            # No qualifying membership for this tenant
            return None

        # Platform-level: find the highest-privilege active membership,
        # preferring the platform (tenant_id IS NULL) row within a role.
        member = fetch_one(
            conn,
            """
            SELECT role, tenant_id FROM memberships
            WHERE user_id = %s AND status = 'active'
            ORDER BY
                CASE role
                    WHEN 'super_admin' THEN 0
                    WHEN 'owner' THEN 1
                    WHEN 'staff' THEN 2
                    ELSE 3
                END,
                CASE WHEN tenant_id IS NULL THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (user_id,),
        )
        if member:
            return ActorContext(
                user_id=user_id,
                role=Role(member["role"]),
                tenant_id=member.get("tenant_id"),
            )

    return None


def _request_tenant_id() -> str | None:
    """Resolve the request tenant id from path, header, or subdomain when present."""

    try:
        from .config import load_config
        from .db import connect as db_connect
        from .tenant_context import TenantResolutionError, resolve_tenant, slug_from_request

        slug, source = slug_from_request(request, load_config())
        with db_connect() as conn:
            tenant = resolve_tenant(conn, slug, source)
        return str(tenant.tenant_id)
    except TenantResolutionError:
        return None


def auth_required(fn: F) -> F:
    """Flask decorator that requires a logged-in session.

    Reads ``flask.session["user_id"]`` set by ``auth_login``, resolves
    the actor's role from the database, and attaches ``g.actor`` for
    downstream permission checks.

    Unauthenticated requests receive a 401 JSON response.
    Tenant-scoped routes enforce that the user has a membership in the
    target tenant (or is a super_admin).
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> tuple:
        from flask import session as flask_session

        user_id = flask_session.get("user_id")
        if not user_id:
            return api_error("Authentication required. Please log in.", 401)

        actor = _resolve_actor(user_id, _request_tenant_id())
        if not actor:
            return api_error("User has no active membership.", 403)

        g.actor = actor
        return fn(*args, **kwargs)  # type: ignore[return-value]

    return wrapper  # type: ignore[return-value]


def permission_required(permission: str) -> Callable[[F], F]:
    """Flask decorator that requires both authentication and a permission.

    Combines ``auth_required`` with a permission check.  Routes protected
    by this decorator will:

    1. Require a valid session (401 if missing).
    2. Resolve the actor's role from the database.
    3. Check that the role has the named permission (403 if missing).

    Usage::

        @api_v1.route("/admin/tenants", methods=["GET"])
        @permission_required("tenant:read")
        def admin_tenants():
            ...
    """

    def decorate(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> tuple:
            from flask import session as flask_session

            user_id = flask_session.get("user_id")
            if not user_id:
                return api_error("Authentication required. Please log in.", 401)

            actor = _resolve_actor(user_id, _request_tenant_id())
            if not actor:
                return api_error("User has no active membership.", 403)

            # Check permission
            try:
                require_permission(actor, permission)
            except PermissionDeniedError as exc:
                return api_error(str(exc), 403)

            g.actor = actor
            return fn(*args, **kwargs)  # type: ignore[return-value]

        return wrapper  # type: ignore[return-value]

    return decorate


def super_admin_required(fn: F) -> F:
    """Flask decorator that requires a super_admin role.

    Acts as ``auth_required`` plus an explicit role check.  Non-super-admin
    users receive a 403 response even if they have an active membership.
    Platform routes do not carry tenant context, so tenant resolution is
    optional and only narrows the actor when a path tenant is present.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> tuple:
        from flask import session as flask_session

        user_id = flask_session.get("user_id")
        if not user_id:
            return api_error("Authentication required. Please log in.", 401)

        actor = _resolve_actor(user_id, _request_tenant_id())
        if not actor:
            return api_error("User has no active membership.", 403)

        if actor.role is not Role.SUPER_ADMIN:
            return api_error("Super-admin privileges required.", 403)

        g.actor = actor
        return fn(*args, **kwargs)  # type: ignore[return-value]

    return wrapper  # type: ignore[return-value]


def tenant_admin_required(fn: F) -> F:
    """Flask decorator that requires owner/admin rights for a tenant.

    Tenant mutation endpoints must be protected by more than a valid login.
    This decorator resolves the request tenant first, then allows only tenant
    owners/admins or platform super admins to continue.
    """

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> tuple:
        from flask import session as flask_session

        user_id = flask_session.get("user_id")
        if not user_id:
            return api_error("Authentication required. Please log in.", 401)

        actor = _resolve_actor(user_id, _request_tenant_id())
        if not actor:
            return api_error("User has no active membership.", 403)

        if actor.role not in {Role.SUPER_ADMIN, Role.OWNER}:
            return api_error("Tenant owner/admin privileges required.", 403)

        g.actor = actor
        return fn(*args, **kwargs)  # type: ignore[return-value]

    return wrapper  # type: ignore[return-value]


def init_auth_blueprints(app: Flask) -> None:
    """Register auth error handlers on the API blueprints.

    Call this once during app startup so that ``PermissionDeniedError``
    is converted to a 403 JSON response.
    """

    from .api_v1 import api_v1

    @app.errorhandler(PermissionDeniedError)
    def handle_permission_denied(exc: PermissionDeniedError):
        return jsonify({
            "error": "forbidden",
            "message": str(exc),
        }), 403

    api_v1.register_error_handler(
        PermissionDeniedError,
        handle_permission_denied,
    )
