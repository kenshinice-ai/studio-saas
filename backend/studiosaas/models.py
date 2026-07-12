"""Typed constants and lightweight models for StudioSaaS v1."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    """Supported StudioSaaS roles.

    Must stay in sync with the ``memberships.role`` CHECK constraint in
    ``backend/db/schema_v1.sql``. A platform administrator is a
    ``super_admin`` membership whose ``tenant_id`` is NULL; per-tenant
    ``super_admin`` rows are also honoured for backward compatibility.
    """

    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    MANAGER = "manager"
    TEACHER = "teacher"
    FRONT_DESK = "front_desk"
    STAFF = "staff"
    PARENT = "parent"


class TenantStatus(StrEnum):
    """Tenant lifecycle states."""

    LEAD = "lead"
    TRIAL = "trial"
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TenantContext:
    """Resolved tenant identity for one request."""

    tenant_id: str
    slug: str
    source: str


@dataclass(frozen=True)
class ActorContext:
    """Authenticated actor identity for an API request."""

    user_id: str
    role: Role
    tenant_id: str | None = None
