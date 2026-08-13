"""Negative auth-boundary tests (no database required).

``auth_required`` rejects sessionless requests before touching the
database, so these run without PostgreSQL. Full membership/cross-tenant
coverage lives in test_tenant_isolation.py (script-style, needs a DB).
"""

import pytest
from flask import g

from studiosaas.auth import _tenant_resolution_error_response
from studiosaas.tenant_context import TenantResolutionError

SENSITIVE_READS = [
    "/s/demo/v1/tenant",
    "/s/demo/v1/tenant/brand",
    "/s/demo/v1/tenant/brand/publication-status/1",
    "/s/demo/v1/tenant/brand-workspace",
    "/s/demo/v1/tenant/analytics?days=30",
    "/s/demo/v1/team",
    "/s/demo/v1/students",
    "/s/demo/v1/registrations",
    "/s/demo/v1/courses",
    "/s/demo/v1/packages",
    "/s/demo/v1/portfolio",
    "/s/demo/v1/attendance",
    "/s/demo/v1/daily-roster?date=2026-07-18",
    "/s/demo/v1/daily-roster/preview?from=2026-07-18&days=7",
    "/s/demo/v1/class-schedules/calendar",
    "/s/demo/v1/class-schedules/calendar.ics?revision=0000000000000000000000000000000000000000000000000000000000000000",
    "/s/demo/v1/daily-roster/calendar?date=2026-07-18",
    "/s/demo/v1/daily-roster/calendar.ics?date=2026-07-18&revision=0000000000000000000000000000000000000000000000000000000000000000",
    "/s/demo/v1/dashboard",
    "/s/demo/v1/legacy-cms/data",
    "/s/demo/v1/export/students.csv",
    "/s/demo/v1/export/registrations.csv",
    "/s/demo/v1/export/credit-ledger.csv",
    "/s/demo/v1/export/revenue.csv",
]


@pytest.mark.parametrize("path", SENSITIVE_READS)
def test_tenant_reads_require_auth(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize(
    "path",
    [
        "/s/lets-paint-studio/v1/tenant",
        "/s/lets-paint-studio/v1/dashboard",
        "/s/lets-paint-studio/v1/students",
    ],
)
def test_studio_admin_slug_routes_reach_auth_layer(client, path):
    """Studio Admin slug API routes must not fall through to Flask 404."""

    response = client.get(path)
    assert response.status_code == 401


MUTATIONS = [
    ("POST", "/v1/admin/tenants"),
    ("PATCH", "/s/demo/v1/tenant"),
    ("PATCH", "/s/demo/v1/operational-settings"),
    ("PUT", "/s/demo/v1/tenant/brand-draft"),
    ("POST", "/s/demo/v1/tenant/website-media"),
    ("POST", "/s/demo/v1/tenant/brand-versions/00000000-0000-0000-0000-000000000000/restore"),
    ("POST", "/s/demo/v1/team"),
    ("PATCH", "/s/demo/v1/team/00000000-0000-0000-0000-000000000000"),
    ("POST", "/s/demo/v1/students"),
    ("POST", "/s/demo/v1/courses"),
    ("POST", "/s/demo/v1/packages"),
    ("DELETE", "/s/demo/v1/portfolio/00000000-0000-0000-0000-000000000000"),
    ("POST", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/credit-transactions"),
    ("POST", "/s/demo/v1/media/upload"),
    ("POST", "/s/demo/v1/attendance/check-in"),
    ("POST", "/s/demo/v1/attendance/00000000-0000-0000-0000-000000000000/void"),
    ("POST", "/s/demo/v1/daily-roster"),
    ("PATCH", "/s/demo/v1/daily-roster/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/s/demo/v1/daily-roster/00000000-0000-0000-0000-000000000000"),
    ("POST", "/s/demo/v1/daily-roster/00000000-0000-0000-0000-000000000000/undo"),
    ("POST", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/access-code"),
    ("DELETE", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/access-code"),
    ("PUT", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/publication-consent"),
    ("DELETE", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/publication-consent"),
    # Rebuilds a whole tenant from seed material. Platform-level and
    # destructive, so it belongs on this list more than most.
    ("POST", "/v1/admin/tenants/00000000-0000-0000-0000-000000000000/demo-reset"),
]


@pytest.mark.parametrize("method,path", MUTATIONS)
def test_mutations_require_auth(client, method, path):
    response = client.open(path, method=method, json={})
    assert response.status_code in (401, 403)


FAKE_USER = "00000000-0000-0000-0000-000000000000"


def test_csrf_header_required_for_cookie_authed_mutations(client):
    """A session without the custom header must be rejected before auth."""

    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.post("/s/demo/v1/students", json={})
    assert response.status_code == 403
    assert "CSRF" in ((response.get_json() or {}).get("message") or "")


def test_csrf_header_lets_authed_mutations_reach_auth_layer(client, monkeypatch):
    """With the header present the request passes the CSRF guard.

    Depending on whether a test database URL is configured, the request may
    then stop at auth/role checks or at tenant/database availability.
    """

    monkeypatch.setenv(
        "STUDIOSAAS_DATABASE_URL",
        "postgresql://localhost/studiosaas_csrf_boundary_test",
    )
    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.post(
        "/s/demo/v1/students",
        json={},
        headers={"X-Requested-With": "StudioSaaS"},
    )
    assert response.status_code in (401, 403, 503)
    assert "CSRF" not in ((response.get_json() or {}).get("message") or "")


def test_csrf_guard_exempts_sessionless_public_requests(client):
    """Public callers without cookies are not affected by the guard."""

    response = client.post("/v1/public/demo/registrations", json={})
    # 404/400/429 depending on tenant resolution — but never the CSRF 403
    assert "CSRF" not in ((response.get_json() or {}).get("message") or "")
    assert response.status_code == 400
    assert "Privacy consent" in ((response.get_json() or {}).get("message") or "")


PUBLIC_SURFACES = [
    "/v1/health",
]


@pytest.mark.parametrize("path", PUBLIC_SURFACES)
def test_public_surfaces_stay_open(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize(
    ("message", "expected_status", "expected_error"),
    [
        ("Tenant 'missing-studio' was not found.", 404, "tenant_not_found"),
        ("Tenant 'paused-studio' is not active.", 403, "tenant_inactive"),
        ("Invalid tenant slug in path.", 400, "tenant_resolution_failed"),
    ],
)
def test_tenant_resolution_errors_keep_the_actual_cause(
    app, message, expected_status, expected_error
):
    """Tenant auth failures must not collapse into a misleading active-state error."""

    with app.test_request_context("/s/example/v1/tenant"):
        g.tenant_resolution_error = TenantResolutionError(message)
        response, status = _tenant_resolution_error_response()
        assert status == expected_status
        payload = response.get_json()
        assert payload["error"] == expected_error
        assert payload["message"] == message
