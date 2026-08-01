"""Unit contract for ROLE_PERMISSIONS — the v7.4.0 role-boundary audit.

Integration coverage lives in test_tenant_isolation.py; these assertions pin
the permission *model* itself so a later edit cannot silently reopen a
boundary the audit closed.
"""

import pytest

from studiosaas.auth import ROLE_PERMISSIONS, PermissionDeniedError, require_permission
from studiosaas.models import ActorContext, Role


def _actor(role: Role) -> ActorContext:
    return ActorContext(user_id="u", role=role, tenant_id="t")


def test_refunds_are_owner_manager_only():
    for role in (Role.OWNER, Role.MANAGER):
        require_permission(_actor(role), "credits:refund")
    for role in (Role.FRONT_DESK, Role.STAFF, Role.TEACHER, Role.PARENT):
        with pytest.raises(PermissionDeniedError):
            require_permission(_actor(role), "credits:refund")


def test_share_links_are_owner_manager_only():
    for role in (Role.OWNER, Role.MANAGER):
        require_permission(_actor(role), "portfolio:share")
    for role in (Role.TEACHER, Role.STAFF, Role.FRONT_DESK, Role.PARENT):
        with pytest.raises(PermissionDeniedError):
            require_permission(_actor(role), "portfolio:share")


def test_financial_boundary_matches_projection():
    """Roles the legacy projection strips financials from must not hold
    analytics:read, and vice versa."""
    for role in (Role.OWNER, Role.MANAGER):
        require_permission(_actor(role), "analytics:read")
    for role in (Role.TEACHER, Role.FRONT_DESK, Role.STAFF, Role.PARENT):
        with pytest.raises(PermissionDeniedError):
            require_permission(_actor(role), "analytics:read")


def test_teacher_operational_set():
    """Teacher: attendance + portfolio work, no student/credit mutation."""
    teacher = ROLE_PERMISSIONS[Role.TEACHER]
    assert "attendance:write" in teacher
    assert "portfolio:write" in teacher
    for denied in ("students:write", "credits:read", "credits:write", "data:export"):
        assert denied not in teacher


def test_front_desk_has_no_attendance_write():
    assert "attendance:write" not in ROLE_PERMISSIONS[Role.FRONT_DESK]


def test_student_named_calendar_export_uses_data_export_boundary():
    for role in (Role.OWNER, Role.MANAGER):
        require_permission(_actor(role), "data:export")
    for role in (Role.TEACHER, Role.STAFF, Role.FRONT_DESK, Role.PARENT):
        with pytest.raises(PermissionDeniedError):
            require_permission(_actor(role), "data:export")


def test_parent_holds_only_reserved_self_permissions():
    assert ROLE_PERMISSIONS[Role.PARENT] == {"student:self:read", "portfolio:self:read"}


def test_every_role_in_model_has_a_permission_entry():
    for role in Role:
        assert role in ROLE_PERMISSIONS, f"{role} missing from ROLE_PERMISSIONS"
