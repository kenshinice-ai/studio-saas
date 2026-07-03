"""Negative auth-boundary tests (no database required).

``auth_required`` rejects sessionless requests before touching the
database, so these run without PostgreSQL. Full membership/cross-tenant
coverage lives in test_tenant_isolation.py (script-style, needs a DB).
"""

import pytest

SENSITIVE_READS = [
    "/s/demo/v1/tenant",
    "/s/demo/v1/tenant/brand",
    "/s/demo/v1/students",
    "/s/demo/v1/registrations",
    "/s/demo/v1/courses",
    "/s/demo/v1/packages",
    "/s/demo/v1/portfolio",
    "/s/demo/v1/attendance",
    "/s/demo/v1/dashboard",
    "/s/demo/v1/legacy-cms/data",
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
    ("POST", "/s/demo/v1/students"),
    ("POST", "/s/demo/v1/courses"),
    ("POST", "/s/demo/v1/packages"),
    ("DELETE", "/s/demo/v1/portfolio/00000000-0000-0000-0000-000000000000"),
    ("POST", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/credit-transactions"),
    ("POST", "/s/demo/v1/media/upload"),
    ("POST", "/s/demo/v1/attendance/check-in"),
    ("POST", "/s/demo/v1/attendance/00000000-0000-0000-0000-000000000000/void"),
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


def test_csrf_header_lets_authed_mutations_reach_auth_layer(client):
    """With the header present the request passes the guard (auth still applies)."""

    with client.session_transaction() as sess:
        sess["user_id"] = FAKE_USER
    response = client.post(
        "/s/demo/v1/students",
        json={},
        headers={"X-Requested-With": "StudioSaaS"},
    )
    assert response.status_code in (401, 403)
    assert "CSRF" not in ((response.get_json() or {}).get("message") or "")


def test_csrf_guard_exempts_sessionless_public_requests(client):
    """Public callers without cookies are not affected by the guard."""

    response = client.post("/v1/public/demo/registrations", json={})
    # 404/400/429 depending on tenant resolution — but never the CSRF 403
    assert "CSRF" not in ((response.get_json() or {}).get("message") or "")


PUBLIC_SURFACES = [
    "/v1/health",
]


@pytest.mark.parametrize("path", PUBLIC_SURFACES)
def test_public_surfaces_stay_open(client, path):
    assert client.get(path).status_code == 200
