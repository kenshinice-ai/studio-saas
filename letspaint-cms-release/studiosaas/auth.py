"""Role and permission checks for StudioSaaS v1."""

from functools import wraps
from typing import Callable, TypeVar

from flask import jsonify

from .models import ActorContext, Role

F = TypeVar("F", bound=Callable)


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
    },
    Role.STAFF: {
        "students:read",
        "students:write",
        "credits:write",
        "portfolio:write",
        "registrations:write",
    },
    Role.PARENT: {
        "student:self:read",
        "portfolio:self:read",
    },
}


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


def permission_required(permission: str) -> Callable[[F], F]:
    """Flask decorator placeholder for future authenticated StudioSaaS routes.

    The current phase defines permission boundaries. Full JWT/session-backed
    actor loading will be added when the v1 auth endpoints replace legacy auth.
    """

    def decorate(fn: F) -> F:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return jsonify(
                {
                    "error": "not_implemented",
                    "message": (
                        "StudioSaaS actor authentication is not wired yet. "
                        f"Required permission: {permission}."
                    ),
                }
            ), 501

        return wrapper  # type: ignore[return-value]

    return decorate
