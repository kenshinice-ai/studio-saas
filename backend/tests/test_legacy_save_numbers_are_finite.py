"""The legacy CMS save refuses NaN and infinity in a credit pack or a balance.

`float()` accepts "nan" and "inf". NaN passes every comparison the save might
make, so a pack could be stored with NaN credits or a new student opened with
a NaN balance. The 2026-10-18 security audit fixed the same parse in two
student routes and named these two places as left over; this closes them.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import API_HEADERS, build_world, database_available, destroy_world, login  # noqa: E402
from _cms_sources import owner_connection  # noqa: E402

requires_db = pytest.mark.skipif(not database_available(), reason="needs the local PostgreSQL schema")


@pytest.fixture()
def world():
    built = build_world(prefix="fin", with_owner_user=True)
    yield built
    destroy_world(built)
    # Each case signs in once. The login limiter allows 30 attempts a minute
    # per address for the whole suite, so give back what these cases used
    # rather than starve whichever test signs in next.
    import importlib

    store = importlib.import_module("studiosaas.api_v1")._public_rate_limit
    for key in [k for k in store if k.startswith("login-")]:
        store.pop(key, None)


def _save(client, world, payload):
    return client.post(f"/s/{world['slug']}/v1/legacy-cms/save", json=payload, headers=API_HEADERS)


@requires_db
@pytest.mark.parametrize("credits, price", [("nan", 100), ("inf", 100), (10, "nan"), (10, "-inf")])
def test_a_credit_pack_with_a_non_finite_number_is_refused(client, world, credits, price):
    login(client, world)
    response = _save(client, world, {"packages": [{"name": "Finite check", "credits": credits, "price": price}]})
    assert response.status_code == 400
    with owner_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM packages WHERE tenant_id = %s AND name = %s",
                    (world["tenant_id"], "Finite check"))
        assert cur.fetchone()["n"] == 0


@requires_db
@pytest.mark.parametrize("balance", ["nan", "inf", "-inf"])
def test_a_student_with_a_non_finite_balance_is_refused(client, world, balance):
    login(client, world)
    response = _save(client, world, {"students": [{"name": "Finite Check", "balance": balance}]})
    assert response.status_code == 400
    assert "finite" in response.get_json()["message"]
