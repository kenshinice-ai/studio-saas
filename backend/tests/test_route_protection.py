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
    "/s/demo/v1/dashboard",
    "/s/demo/v1/legacy-cms/data",
]


@pytest.mark.parametrize("path", SENSITIVE_READS)
def test_tenant_reads_require_auth(client, path):
    assert client.get(path).status_code == 401


MUTATIONS = [
    ("POST", "/v1/admin/tenants"),
    ("PATCH", "/s/demo/v1/tenant"),
    ("POST", "/s/demo/v1/students"),
    ("POST", "/s/demo/v1/courses"),
    ("POST", "/s/demo/v1/packages"),
    ("DELETE", "/s/demo/v1/portfolio/00000000-0000-0000-0000-000000000000"),
    ("POST", "/s/demo/v1/students/00000000-0000-0000-0000-000000000000/credit-transactions"),
]


@pytest.mark.parametrize("method,path", MUTATIONS)
def test_mutations_require_auth(client, method, path):
    response = client.open(path, method=method, json={})
    assert response.status_code in (401, 403)


PUBLIC_SURFACES = [
    "/v1/health",
]


@pytest.mark.parametrize("path", PUBLIC_SURFACES)
def test_public_surfaces_stay_open(client, path):
    assert client.get(path).status_code == 200
