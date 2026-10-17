"""The legacy CMS photo uploader stores student photos and nothing else.

Its one caller (``PhotoUploader`` in legacy-root/src/components.jsx) never
sends a kind. Brand media has its own owner-only routes (``/tenant/logo``,
``/tenant/website-media``), so a ``kind`` on this route is ignored.
"""

from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from _billing_world import API_HEADERS, WORLD_PASSWORD, build_world, destroy_world  # noqa: E402
from test_credit_settlements import requires_db  # noqa: E402


@pytest.fixture()
def front_desk_world():
    from _cms_sources import owner_connection
    from studiosaas.auth import hash_password

    world = build_world(prefix="photo-kind")
    email = f"front-desk-{uuid.uuid4().hex[:8]}@example.test"
    with owner_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (email, password_hash, full_name) VALUES (%s, %s, 'Front Desk') RETURNING id",
                (email, hash_password(WORLD_PASSWORD)),
            )
            user_id = str(cur.fetchone()["id"])
            cur.execute(
                "INSERT INTO memberships (tenant_id, user_id, role, status) VALUES (%s, %s, 'front_desk', 'active')",
                (world["tenant_id"], user_id),
            )
        conn.commit()
    world.update(front_desk_email=email, front_desk_user_id=user_id)
    try:
        yield world
    finally:
        destroy_world(world)
        with owner_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()


def _png() -> bytes:
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), (40, 120, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


@requires_db
@pytest.mark.parametrize("requested", ["logo", "website_image", "portfolio"])
def test_a_requested_kind_is_stored_as_a_student_photo(app, front_desk_world, tmp_path, monkeypatch, requested):
    from _cms_sources import owner_connection
    from studiosaas.db import fetch_one

    monkeypatch.setitem(app.config, "MEDIA_DIR", str(tmp_path))
    client = app.test_client()
    signed_in = client.post(
        "/v1/auth/login",
        json={"email": front_desk_world["front_desk_email"], "password": WORLD_PASSWORD},
        headers=API_HEADERS,
    )
    assert signed_in.status_code == 200, signed_in.get_json()

    uploaded = client.post(
        f"/s/{front_desk_world['slug']}/v1/legacy-cms/media/upload",
        data={"kind": requested, "file": (io.BytesIO(_png()), "photo.png", "image/png")},
        content_type="multipart/form-data",
        headers=API_HEADERS,
    )
    assert uploaded.status_code == 200, uploaded.get_json()

    with owner_connection() as conn:
        row = fetch_one(
            conn,
            "SELECT asset_type FROM media_assets WHERE tenant_id = %s AND id = %s",
            (front_desk_world["tenant_id"], uploaded.get_json()["mediaAssetId"]),
        )
    assert row["asset_type"] == "student_photo"
