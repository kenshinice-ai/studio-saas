"""Static XSS guardrails for high-risk admin render paths."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_studio_admin_high_risk_tables_do_not_render_user_rows_with_inner_html():
    html = (ROOT / "backend" / "frontend" / "studio-admin.html").read_text(encoding="utf-8")
    forbidden = [
        "$('studentsBody').innerHTML = students.map",
        "$('coursesBody').innerHTML = sorted.map",
        "$('packagesBody').innerHTML = sorted.map",
        "$('registrationsBody').innerHTML = registrations.map",
        "$('attendanceBody').innerHTML = attendanceItems.map",
        "$('portfolioBody').innerHTML = portfolioItems.map",
        "onclick=\"editStudent('${s.id}')\"",
        "onclick=\"updateRegistrationStatus('${r.id}'",
    ]
    for marker in forbidden:
        assert marker not in html


def test_super_admin_tenant_tables_do_not_render_user_rows_with_inner_html():
    html = (ROOT / "super-admin.html").read_text(encoding="utf-8")
    forbidden = [
        "$('tenantsBody').innerHTML = visible.map",
        "$('plansBody').innerHTML = plans.map",
        "$('auditBody').innerHTML = audit.auditLogs.length",
        "onclick=\"selectTenant('${t.id}')\"",
        "onclick=\"editPlan('${p.code}')\"",
    ]
    for marker in forbidden:
        assert marker not in html
