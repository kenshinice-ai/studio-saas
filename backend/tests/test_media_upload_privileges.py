"""The upload path must not require table ownership, and must bound its work.

Production runs as the least-privilege role introduced in v7.7.7. That role
holds DML rights and owns nothing, so any DDL on the upload path fails with
``must be owner of table media_assets`` — which is exactly what took every
media upload (logo, hero, student photo, portfolio) to a 500.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MEDIA_SERVICE = REPOSITORY_ROOT / "backend/studiosaas/services/media.py"
API_V1 = REPOSITORY_ROOT / "backend/studiosaas/api_v1.py"


def _service_source() -> str:
    return MEDIA_SERVICE.read_text(encoding="utf-8")


def test_ddl_is_guarded_by_a_catalogue_probe() -> None:
    """ALTER TABLE may only run after the object is shown to be missing.

    PostgreSQL checks table ownership *before* it evaluates IF NOT EXISTS, so
    an unconditional ALTER fails on a correctly migrated database whose role
    is not the owner.
    """

    source = _service_source()
    probe = source.index("information_schema.columns")
    alter = source.index("ALTER TABLE media_assets")
    assert probe < alter, "the column probe must precede the ALTER it guards"

    constraint_probe = source.index("information_schema.table_constraints")
    constraint_alter = source.index("students_student_photo_asset_id_fkey\n")
    assert constraint_probe < constraint_alter


def test_no_unconditional_ddl_remains_on_the_upload_path() -> None:
    """Every ALTER in the media service sits inside an `if cur.fetchone() is None`."""

    source = _service_source()
    for match in re.finditer(r"^\s*ALTER TABLE", source, re.MULTILINE):
        preceding = source[:match.start()]
        assert "if cur.fetchone() is None:" in preceding[-400:], (
            "an ALTER TABLE is not guarded by a catalogue probe"
        )


def test_stale_duplicate_helper_is_gone() -> None:
    """One definition of the schema guard, so only one can drift."""

    assert "def _ensure_media_schema" not in API_V1.read_text(encoding="utf-8")


def test_decode_ceiling_is_enforced_by_pillow_too() -> None:
    """Pillow's own bomb guard defaults to ~89 MP and only warns."""

    pytest.importorskip("PIL")
    from PIL import Image

    from studiosaas.services import media

    assert Image.MAX_IMAGE_PIXELS == media.MAX_IMAGE_PIXELS
    assert media.MAX_IMAGE_PIXELS <= 30_000_000


def test_oversized_image_is_rejected_not_decoded() -> None:
    """A decompression bomb must raise a clean error, not exhaust memory."""

    pytest.importorskip("PIL")
    from PIL import Image

    from studiosaas.services.media import MediaUploadError, _build_safe_variants

    original = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        buffer = io.BytesIO()
        Image.new("L", (9000, 9000)).save(buffer, format="PNG")
    finally:
        Image.MAX_IMAGE_PIXELS = original

    with pytest.raises(MediaUploadError):
        _build_safe_variants(buffer.getvalue(), ".png")


def test_thumbnail_is_derived_from_the_display_raster() -> None:
    """Building both derivatives from the source held two full copies at once."""

    pytest.importorskip("PIL")
    from PIL import Image

    from studiosaas.services.media import DISPLAY_MAX, MEDIUM_MAX, THUMB_MAX, _build_safe_variants

    buffer = io.BytesIO()
    Image.new("RGB", (4000, 3000), (90, 120, 150)).save(buffer, format="JPEG", quality=88)
    variants = _build_safe_variants(buffer.getvalue(), ".jpg")

    display_bytes, display_w, display_h = variants["display"]
    _, medium_w, medium_h = variants["medium"]
    _, thumb_w, thumb_h = variants["thumb"]
    assert max(display_w, display_h) <= DISPLAY_MAX
    assert max(medium_w, medium_h) <= MEDIUM_MAX
    assert max(thumb_w, thumb_h) <= THUMB_MAX
    assert display_bytes.startswith(b"\xff\xd8\xff"), "derivatives are metadata-free JPEG"


def test_jpeg_decoding_uses_draft_scaling() -> None:
    """draft() lets the decoder downscale during decompression.

    Without it a 24 MP photo materialises at full size: measured at +139 MB
    peak RSS versus +17 MB with it, on a host with 1.9 GB and eight threads.
    """

    assert 'image.draft("RGB", (DISPLAY_MAX, DISPLAY_MAX))' in _service_source()


def test_checksum_etag_can_return_304_after_the_caller_authorizes(
    app, tmp_path, monkeypatch
) -> None:
    """The derivative checksum is stable; conditional handling needs no file guess."""

    from studiosaas.services import media

    checksum = "a" * 64
    payload = b"safe-medium-derivative"
    path = tmp_path / "tenant" / "portfolio" / "asset.medium.jpg"
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    app.config["MEDIA_DIR"] = str(tmp_path)
    monkeypatch.setattr(
        media,
        "fetch_one",
        lambda *_args, **_kwargs: {
            "storage_key": "tenant/portfolio/asset.medium.jpg",
            "mime_type": "image/jpeg",
            "checksum_sha256": checksum,
        },
    )

    with app.test_request_context(
        "/media/asset?variant=medium", headers={"If-None-Match": f'"{checksum}"'}
    ):
        response = media.send_media_asset(
            object(), tenant_id="tenant", media_asset_id="asset", variant="medium"
        )

    assert response.status_code == 304
    assert response.headers["ETag"] == f'"{checksum}"'
