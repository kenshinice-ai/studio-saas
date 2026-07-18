"""No-port privacy and student-session contract tests."""

from __future__ import annotations

import io

import pytest
from PIL import Image
from werkzeug.datastructures import FileStorage

from studiosaas.auth import hash_password
from studiosaas.services import student_access
from studiosaas.services.media import (
    DISPLAY_MAX,
    THUMB_MAX,
    MediaUploadError,
    _build_safe_variants,
    validate_media_upload,
)


def test_single_name_lookup_never_matches_last_name(monkeypatch):
    captured = {}

    def fake_fetch_all(_conn, sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    monkeypatch.setattr(student_access, "fetch_all", fake_fetch_all)
    result = student_access.find_student(
        object(), tenant_id="tenant", name="Lee", phone="0412 345 678"
    )
    assert result.status == "missing"
    assert "first_name" in captured["sql"]
    assert "lower(trim(last_name))" not in captured["sql"]
    assert captured["params"][-1] == "lee"


def test_ambiguous_lookup_never_selects_first_row(monkeypatch):
    monkeypatch.setattr(
        student_access,
        "fetch_all",
        lambda *_args, **_kwargs: [{"id": "one"}, {"id": "two"}],
    )
    result = student_access.find_student(
        object(), tenant_id="tenant", name="Alex", phone="0400000000"
    )
    assert result.status == "ambiguous"
    assert result.student is None


def test_access_code_hash_is_verified_without_plaintext_storage():
    stored = hash_password("123456")
    assert "123456" not in stored
    assert student_access.verify_access_code(
        {"access_code_hash": stored, "access_code_revoked_at": None}, "123456"
    )
    assert not student_access.verify_access_code(
        {"access_code_hash": stored, "access_code_revoked_at": None}, "654321"
    )


def test_lookup_fingerprint_does_not_contain_personal_data():
    fingerprint = student_access.lookup_fingerprint("Alex Lee", "+61 412 345 678")
    assert len(fingerprint) == 64
    assert "alex" not in fingerprint
    assert "0412" not in fingerprint


def test_media_derivatives_are_bounded_and_strip_exif():
    source = Image.new("RGB", (2400, 1200), "red")
    exif = Image.Exif()
    exif[0x0110] = "private-camera"
    raw = io.BytesIO()
    source.save(raw, format="JPEG", quality=90, exif=exif)

    variants = _build_safe_variants(raw.getvalue(), ".jpg")
    for variant, limit in (("display", DISPLAY_MAX), ("thumb", THUMB_MAX)):
        payload, width, height = variants[variant]
        decoded = Image.open(io.BytesIO(payload))
        assert max(width, height) <= limit
        assert decoded.getexif().get(0x0110) is None


def test_same_origin_svg_logo_upload_is_rejected():
    upload = FileStorage(
        stream=io.BytesIO(b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
        filename="logo.svg",
        content_type="image/svg+xml",
    )
    with pytest.raises(MediaUploadError, match="File type"):
        validate_media_upload(upload, kind="logo")


def test_retired_portfolio_token_route_returns_410_without_database(client):
    response = client.post("/v1/public/demo/portfolio-token", json={})
    assert response.status_code == 410
    assert response.get_json()["error"] == "student_session_required"


def test_security_headers_are_present(client):
    response = client.get("/v1/health")
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_hsts_only_trusts_https_proxy_header_from_loopback(client):
    untrusted = client.get(
        "/v1/health",
        headers={"X-Forwarded-Proto": "https"},
        environ_base={"REMOTE_ADDR": "203.0.113.9"},
    )
    assert "Strict-Transport-Security" not in untrusted.headers

    trusted = client.get(
        "/v1/health",
        headers={"X-Forwarded-Proto": "https"},
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert trusted.headers["Strict-Transport-Security"].startswith("max-age=31536000")


def test_client_ip_proxy_headers_are_only_trusted_from_loopback(app):
    import importlib

    api_module = importlib.import_module("studiosaas.api_v1")

    headers = {
        "CF-Connecting-IP": "198.51.100.7",
        "X-Forwarded-For": "198.51.100.8",
    }
    with app.test_request_context(
        "/v1/health", headers=headers, environ_base={"REMOTE_ADDR": "203.0.113.9"}
    ):
        assert api_module._client_ip() == "203.0.113.9"

    with app.test_request_context(
        "/v1/health", headers=headers, environ_base={"REMOTE_ADDR": "127.0.0.1"}
    ):
        assert api_module._client_ip() == "198.51.100.7"


def test_cross_site_public_write_is_rejected_before_database(client):
    response = client.post(
        "/v1/public/demo/student/unlock",
        json={"name": "Alex", "phone": "0400000000", "code": "123456"},
        headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "forbidden"
