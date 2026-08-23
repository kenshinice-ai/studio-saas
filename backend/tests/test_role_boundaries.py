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


def test_front_desk_can_check_people_in():
    """The counter runs the day, and the audited path is the one it gets.

    This assertion used to read `not in`. Withholding `attendance:write` never
    stopped the front desk taking a credit off a balance — it holds
    `credits:write`, so it could always POST a `consume` transaction. That
    route writes no `attendance_sessions` row and ties the movement to no class
    date, so the deduction the front desk actually made was the one nobody
    could reconstruct. Granting check-in moves the same act onto the path that
    records what it was for.
    """

    assert "attendance:write" in ROLE_PERMISSIONS[Role.FRONT_DESK]
    # Still not the counter's to make: refunds and teacher pay both move money
    # in a direction that wants a second pair of eyes.
    for denied in ("credits:refund", "payments:refund", "payroll:read", "payroll:write"):
        assert denied not in ROLE_PERMISSIONS[Role.FRONT_DESK]


def test_assistant_is_a_strict_subset_of_teacher():
    """助教 is the teacher's role minus authorship — never more, in any key.

    The old `staff` set differed from teacher in BOTH directions: it could
    write a student record, top up and deduct a balance, and read the studio's
    bank details through `billing:read`, while not being allowed to see the
    timetable it was assisting with. That is not a junior teacher, it is a
    fifth unrelated role, and it is why no one could say what `staff` meant.
    """

    staff = ROLE_PERMISSIONS[Role.STAFF]
    teacher = ROLE_PERMISSIONS[Role.TEACHER]
    assert staff < teacher, f"staff holds keys teacher does not: {sorted(staff - teacher)}"
    # The two that make it an assistant rather than the teacher of record.
    assert teacher - staff == {"progress_reports:write", "payroll:self:read"}
    # Money, enrolment and the studio's own details are all out.
    for denied in ("students:write", "credits:read", "credits:write", "billing:read",
                   "registrations:read", "registrations:write", "data:export"):
        assert denied not in staff


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


def _cms_role_tabs() -> dict[str, list[str]]:
    """Parse `roleTabs` out of cms-app.jsx — the navigation half of the model."""

    import re
    from _cms_sources import cms_source_text

    source = cms_source_text()
    block = source[source.index("const roleTabs = {"):]
    block = block[:block.index("};")]
    tabs: dict[str, list[str]] = {}
    for role, listing in re.findall(r"(\w+):\s*\[([^\]]*)\]", block):
        tabs[role] = re.findall(r"'([a-z_]+)'", listing)
    return tabs


def test_every_role_that_can_open_the_roster_can_write_attendance():
    """The roster page is a money surface, and navigation is not a permission.

    Every write control on that page — check-in, batch check-in, seating a
    walk-in, undoing a check-in, moving someone off the day — calls a route
    gated on `attendance:write`. Until v10.13 none of them had a permission
    gate in the UI at all; they were reachable by anyone `roleTabs` let onto
    the page, and the only reason no dead button ever shipped is that the five
    roles listed there happened to hold the key.

    This asserts the coincidence is actually an invariant, so the next person
    who adds a role to `roleTabs.roster` finds out here rather than from a
    studio whose front desk gets a 403 on a Saturday morning.
    """

    role_tabs = _cms_role_tabs()
    assert role_tabs, "roleTabs could not be parsed out of the CMS source"
    # These two are the platform super admin's aliases; they hold "*".
    platform = {"platform_super_admin", "super_admin"}
    for role_name, tabs in role_tabs.items():
        if "roster" not in tabs or role_name in platform:
            continue
        role = Role(role_name)
        assert "attendance:write" in ROLE_PERMISSIONS[role], (
            f"roleTabs lets {role_name} onto the roster page, but the backend "
            f"will 403 every write control there"
        )


def test_the_roster_panel_is_handed_the_attendance_gate():
    """A gate nobody passes down is not a gate.

    `canWriteAttendance` existed for three releases while `RosterSection` was
    never given it, so the page's controls fell back to `busy` alone.
    """

    from _cms_sources import cms_source_text

    source = cms_source_text()
    mount = source[source.index("tab==='roster' && <RosterSection"):]
    mount = mount[:mount.index("/>}")]
    assert "canWriteAttendance" in mount, (
        "RosterSection must receive canWriteAttendance — every write control "
        "on that page calls an attendance:write route"
    )
