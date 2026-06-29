"""Typed constants and lightweight models for StudioSaaS v1."""

from dataclasses import dataclass
from enum import StrEnum


class Role(StrEnum):
    """Supported StudioSaaS roles."""

    SUPER_ADMIN = "super_admin"
    OWNER = "owner"
    STAFF = "staff"
    PARENT = "parent"


class TenantStatus(StrEnum):
    """Tenant lifecycle states."""

    TRIAL = "trial"
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
