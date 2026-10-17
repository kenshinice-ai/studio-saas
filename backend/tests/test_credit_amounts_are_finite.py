"""A credit amount is a finite positive number, on every route that moves one.

``float()`` accepts "nan" and "inf", and NaN compares false with everything:
it passes ``amount <= 0`` and ``balance < amount`` alike. Stored as a balance,
it would make every later balance check on that student pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import API_HEADERS, build_world, destroy_world, login  # noqa: E402
from test_credit_settlements import requires_db  # noqa: E402


@pytest.fixture()
def world():
    w = build_world(prefix="finite", with_owner_user=True)
    try:
        yield w
    finally:
        destroy_world(w)


def _default_balance(world: dict):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    with owner_connection() as conn:
        row = fetch_one(
            conn,
            """
            SELECT balance::text AS balance FROM credit_accounts
            WHERE tenant_id = %s AND student_id = %s AND course_id IS NULL
            """,
            (world["tenant_id"], world["student_id"]),
        )
    return row["balance"] if row else None


@requires_db
@pytest.mark.parametrize("value", ["nan", "inf", "-inf"])
def test_a_credit_transaction_refuses_a_non_finite_amount(app, world, value):
    client = app.test_client()
    login(client, world)
    response = client.post(
        f"/s/{world['slug']}/v1/students/{world['student_id']}/credit-transactions",
        json={"transactionType": "purchase", "amount": value},
        headers=API_HEADERS,
    )

    assert response.status_code == 400, response.get_data(as_text=True)
    assert _default_balance(world) in (None, "0", "0.00")


@requires_db
@pytest.mark.parametrize("value", ["nan", "inf"])
def test_check_in_refuses_a_non_finite_credit_amount(app, world, value):
    client = app.test_client()
    login(client, world)
    response = client.post(
        f"/s/{world['slug']}/v1/attendance/check-in",
        json={"studentId": world["student_id"], "credits": value},
        headers=API_HEADERS,
    )

    assert response.status_code == 400, response.get_data(as_text=True)
