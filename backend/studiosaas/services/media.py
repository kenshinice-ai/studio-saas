"""Canonical tenant media upload and retrieval service."""

from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
from pathlib import PurePath
from typing import Any

from flask import current_app, send_from_directory
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..db import fetch_one


class MediaUploadError(ValueError):
    """Raised when an uploaded file fails validation or ownership checks."""


class MediaQuotaExceededError(MediaUploadError):
    """Raised when a tenant upload would exceed its plan storage limit."""


# S2 (LetsPaintCMS v4.4 U6): accept iPhone HEIC/HEIF and convert to JPEG
# server-side. Pillow is a guarded optional dependency — when missing,
# HEIC uploads fail with a clear message and thumbnails fall back to
# the original file.
try:
    from PIL import Image as _PILImage
    from PIL import ImageOps as _PILImageOps
    _HAS_PIL = True
except ImportError:  # pragma: no cover - depends on environment
    _HAS_PIL = False

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
HEIC_EXTENSIONS = {".heic", ".heif"}
DOCUMENT_EXTENSIONS = {".pdf"}

# Safe derivatives are generated at upload time. Public and student-facing
# routes request a derivative explicitly and never fall back to the original.
THUMB_MAX = 360
DISPLAY_MAX = 2000
MAX_IMAGE_PIXELS = 40_000_000
THUMB_SOURCE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MEDIA_UPLOAD_LIMITS = {
    "student_photo": (IMAGE_EXTENSIONS, 5 * 1024 * 1024),
    "registration_photo": (IMAGE_EXTENSIONS, 5 * 1024 * 1024),
    "portfolio": (IMAGE_EXTENSIONS, 10 * 1024 * 1024),
    "homework": (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS, 10 * 1024 * 1024),
    "sheet_music": (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS, 15 * 1024 * 1024),
    # Public logos are served through metadata-free raster derivatives. SVG is
    # deliberately excluded because an uploaded same-origin SVG can carry
    # active content and cannot use the safe JPEG derivative pipeline.
    "logo": ({".jpg", ".jpeg", ".png", ".webp"}, 5 * 1024 * 1024),
    "website_image": ({".jpg", ".jpeg", ".png", ".webp"}, 10 * 1024 * 1024),
}
MEDIA_MIME_TYPES = {
    ".jpg": {"image/jpeg"},
    ".jpeg": {"image/jpeg"},
    ".png": {"image/png"},
    ".gif": {"image/gif"},
    ".webp": {"image/webp"},
    ".pdf": {"application/pdf"},
    ".svg": {"image/svg+xml", "image/svg"},
    ".heic": {"image/heic", "image/heif", "image/heic-sequence"},
    ".heif": {"image/heic", "image/heif", "image/heif-sequence"},
}


def media_root() -> str:
    """Return the root directory for local media storage."""

    root = current_app.config.get("MEDIA_DIR")
    if root:
        return str(root)
    return os.path.join(current_app.root_path, "media")


def ensure_media_schema(conn: Any) -> None:
    """Keep older local databases compatible with canonical media columns."""

    with conn.cursor() as cur:
        cur.execute(
            """
            ALTER TABLE media_assets
            ADD COLUMN IF NOT EXISTS asset_type text NOT NULL DEFAULT 'portfolio'
            CHECK (asset_type IN ('student_photo', 'registration_photo', 'portfolio', 'homework', 'sheet_music', 'logo', 'website_image'))
            """
        )
        cur.execute(
            """
            DO $$
            BEGIN
                ALTER TABLE students
                    ADD CONSTRAINT students_student_photo_asset_id_fkey
                    FOREIGN KEY (student_photo_asset_id) REFERENCES media_assets(id) ON DELETE SET NULL;
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END $$;
            """
        )


def refresh_tenant_usage(conn: Any, tenant_id: str) -> None:
    """Recalculate tenant usage counters from canonical tables."""

    row = fetch_one(
        conn,
        """
        SELECT
            (SELECT count(*) FROM students WHERE tenant_id = %s) AS student_count,
            (SELECT count(*) FROM memberships WHERE tenant_id = %s) AS user_count,
            CEIL((
                (SELECT COALESCE(sum(byte_size), 0) FROM media_assets WHERE tenant_id = %s)
                + (SELECT COALESCE(sum(byte_size), 0) FROM media_variants WHERE tenant_id = %s)
            ) / 1048576.0) AS storage_used_mb
        """,
        (tenant_id, tenant_id, tenant_id, tenant_id),
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb, calculated_at)
            VALUES (%s, %s, %s, %s, now())
            ON CONFLICT (tenant_id) DO UPDATE
            SET student_count = EXCLUDED.student_count,
                user_count = EXCLUDED.user_count,
                storage_used_mb = EXCLUDED.storage_used_mb,
                calculated_at = now()
            """,
            (
                tenant_id,
                row["student_count"] or 0,
                row["user_count"] or 0,
                row["storage_used_mb"] or 0,
            ),
        )


def detect_mime(ext: str) -> str:
    """Return the canonical MIME type for a supported file extension."""

    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".gif":
        return "image/gif"
    if ext == ".webp":
        return "image/webp"
    if ext == ".pdf":
        return "application/pdf"
    if ext == ".svg":
        return "image/svg+xml"
    if ext in HEIC_EXTENSIONS:
        return "image/heic"
    return "application/octet-stream"


def validate_media_upload(file_storage: FileStorage, *, kind: str) -> tuple[str, bytes, str]:
    """Validate an upload and return extension, bytes, and MIME type."""

    filename = file_storage.filename or ""
    safe_name = secure_filename(filename)
    if not safe_name or "/" in filename or "\\" in filename or PurePath(filename).name != filename:
        raise MediaUploadError("Filename must not contain path separators.")
    ext = os.path.splitext(safe_name)[1].lower()
    allowed_ext, max_bytes = MEDIA_UPLOAD_LIMITS.get(kind, MEDIA_UPLOAD_LIMITS["portfolio"])
    if ext not in allowed_ext:
        allowed = ", ".join(sorted(allowed_ext))
        raise MediaUploadError(f"File type must be one of: {allowed}.")

    stream = file_storage.stream
    stream.seek(0, 2)
    size = stream.tell()
    stream.seek(0)
    if size <= 0:
        raise MediaUploadError("File is empty.")
    if size > max_bytes:
        raise MediaUploadError(f"File must be {max_bytes // (1024 * 1024)} MB or smaller.")

    content_type = str(file_storage.mimetype or "").lower()
    if content_type and content_type != "application/octet-stream" and content_type not in MEDIA_MIME_TYPES.get(ext, set()):
        raise MediaUploadError("MIME type does not match the selected file type.")

    data = stream.read()
    stream.seek(0)
    if ext in (".jpg", ".jpeg") and not data.startswith(b"\xff\xd8\xff"):
        raise MediaUploadError("File content does not match the selected image type.")
    if ext == ".png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise MediaUploadError("File content does not match the selected image type.")
    if ext == ".gif" and data[:6] not in (b"GIF87a", b"GIF89a"):
        raise MediaUploadError("File content does not match the selected image type.")
    if ext == ".webp" and not (data.startswith(b"RIFF") and data[8:12] == b"WEBP"):
        raise MediaUploadError("File content does not match the selected image type.")
    if ext == ".pdf" and not data.startswith(b"%PDF-"):
        raise MediaUploadError("File content does not match the selected PDF type.")
    if ext == ".svg":
        sample = data[:1024].lstrip().lower()
        if not (sample.startswith(b"<svg") or sample.startswith(b"<?xml") or b"<svg" in sample):
            raise MediaUploadError("File content does not match the selected SVG type.")
    if ext in HEIC_EXTENSIONS and data[4:8] != b"ftyp":
        raise MediaUploadError("File content does not match the selected image type.")
    return ext, data, detect_mime(ext)


def _open_raster(data: bytes, ext: str):
    """Decode a bounded raster upload or raise a clear privacy-safe error."""

    if not _HAS_PIL:
        raise MediaUploadError("Image processing is unavailable on this server.")
    if ext in HEIC_EXTENSIONS:
        try:
            from pillow_heif import register_heif_opener

            register_heif_opener()
        except ImportError as exc:
            raise MediaUploadError(
                "HEIC photos cannot be processed on this server. Please upload JPG or PNG."
            ) from exc
    try:
        image = _PILImage.open(io.BytesIO(data))
        width, height = image.size
        if width <= 0 or height <= 0 or width * height > MAX_IMAGE_PIXELS:
            raise MediaUploadError("Image dimensions are too large to process safely.")
        image.load()
        return _PILImageOps.exif_transpose(image)
    except MediaUploadError:
        raise
    except Exception as exc:
        raise MediaUploadError("Image content could not be decoded safely.") from exc


def _jpeg_bytes(image, max_edge: int, quality: int) -> tuple[bytes, int, int]:
    """Return a metadata-free RGB JPEG derivative and its pixel dimensions."""

    converted = image.copy()
    converted.thumbnail((max_edge, max_edge), _PILImage.Resampling.LANCZOS)
    if converted.mode in {"RGBA", "LA"}:
        background = _PILImage.new("RGB", converted.size, "white")
        alpha = converted.getchannel("A")
        background.paste(converted.convert("RGB"), mask=alpha)
        converted = background
    elif converted.mode != "RGB":
        converted = converted.convert("RGB")
    out = io.BytesIO()
    converted.save(out, format="JPEG", quality=quality, optimize=True)
    return out.getvalue(), converted.width, converted.height


def _build_safe_variants(data: bytes, ext: str) -> dict[str, tuple[bytes, int, int]]:
    """Build display and thumbnail derivatives without copying source metadata."""

    image = _open_raster(data, ext)
    display = _jpeg_bytes(image, DISPLAY_MAX, 88)
    thumb = _jpeg_bytes(image, THUMB_MAX, 84)
    return {"display": display, "thumb": thumb}


def _enforce_tenant_quota(conn: Any, *, tenant_id: str, incoming_bytes: int) -> None:
    """Reject uploads that would exceed the tenant's plan storage limit."""

    row = fetch_one(
        conn,
        """
        SELECT (
                   COALESCE(sum(m.byte_size), 0)
                   + COALESCE((
                       SELECT sum(v.byte_size)
                       FROM media_variants v
                       WHERE v.tenant_id = t.id
                   ), 0)
               )::bigint AS used_bytes,
               p.storage_limit_mb
        FROM tenants t
        LEFT JOIN media_assets m ON m.tenant_id = t.id
        LEFT JOIN plans p ON p.code = t.plan_code
        WHERE t.id = %s
        GROUP BY t.id, p.storage_limit_mb
        """,
        (tenant_id,),
    )
    if not row or row["storage_limit_mb"] is None:
        return
    limit_bytes = int(row["storage_limit_mb"]) * 1024 * 1024
    if int(row["used_bytes"] or 0) + incoming_bytes > limit_bytes:
        raise MediaQuotaExceededError("Tenant storage quota would be exceeded.")


def store_media_asset(
    conn: Any,
    *,
    tenant_id: str,
    file_storage: FileStorage,
    kind: str,
    owner_student_id: str | None = None,
    storage_provider: str = "local",
) -> dict[str, Any]:
    """Persist one tenant media file and insert its ``media_assets`` row."""

    ensure_media_schema(conn)
    if kind not in MEDIA_UPLOAD_LIMITS:
        raise MediaUploadError("Unsupported media kind.")
    if storage_provider not in {"local", "s3"}:
        raise MediaUploadError("Unsupported storage provider.")
    if storage_provider == "s3":
        raise MediaUploadError("S3 media storage is not configured for this deployment.")
    if owner_student_id:
        student = fetch_one(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND id = %s",
            (tenant_id, owner_student_id),
        )
        if not student:
            raise MediaUploadError("Student was not found for this tenant.")

    ext, data, mime_type = validate_media_upload(file_storage, kind=kind)
    variants: dict[str, tuple[bytes, int, int]] = {}
    if ext in IMAGE_EXTENSIONS:
        variants = _build_safe_variants(data, ext)
    incoming_bytes = len(data) + sum(len(item[0]) for item in variants.values())
    _enforce_tenant_quota(conn, tenant_id=tenant_id, incoming_bytes=incoming_bytes)

    media_id = str(uuid.uuid4())
    tenant_part = str(tenant_id)
    safe_kind = re.sub(r"[^a-z0-9_-]", "_", kind.lower())
    storage_key = f"{tenant_part}/{safe_kind}/{media_id}{ext}"
    full_path = os.path.join(media_root(), tenant_part, safe_kind, f"{media_id}{ext}")
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as fh:
        fh.write(data)

    variant_paths: dict[str, tuple[str, str, bytes, int, int]] = {}
    for variant, (variant_data, width, height) in variants.items():
        variant_filename = f"{media_id}.{variant}.jpg"
        variant_key = f"{tenant_part}/{safe_kind}/{variant_filename}"
        variant_path = os.path.join(media_root(), tenant_part, safe_kind, variant_filename)
        with open(variant_path, "wb") as fh:
            fh.write(variant_data)
        variant_paths[variant] = (variant_key, variant_path, variant_data, width, height)

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO media_assets (
                    id, tenant_id, owner_student_id, asset_type, storage_provider, storage_key,
                    original_filename, mime_type, byte_size, checksum_sha256, visibility
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'private')
                RETURNING id, storage_provider, storage_key, mime_type, byte_size
                """,
                (
                    media_id,
                    tenant_id,
                    owner_student_id,
                    safe_kind,
                    storage_provider,
                    storage_key,
                    secure_filename(file_storage.filename or ""),
                    mime_type,
                    len(data),
                    hashlib.sha256(data).hexdigest(),
                ),
            )
            row = cur.fetchone()
            for variant, (variant_key, _variant_path, variant_data, width, height) in variant_paths.items():
                cur.execute(
                    """
                    INSERT INTO media_variants (
                        tenant_id, media_asset_id, variant, storage_key, mime_type,
                        byte_size, checksum_sha256, pixel_width, pixel_height,
                        metadata_sanitized
                    ) VALUES (%s, %s, %s, %s, 'image/jpeg', %s, %s, %s, %s, true)
                    """,
                    (
                        tenant_id,
                        media_id,
                        variant,
                        variant_key,
                        len(variant_data),
                        hashlib.sha256(variant_data).hexdigest(),
                        width,
                        height,
                    ),
                )
            refresh_tenant_usage(conn, tenant_id)
    except Exception:
        for path in [full_path, *(item[1] for item in variant_paths.values())]:
            try:
                os.remove(path)
            except OSError:
                pass
        raise
    return row


def send_media_asset(
    conn: Any,
    *,
    tenant_id: str,
    media_asset_id: str,
    variant: str | None = None,
):
    """Serve one media asset after tenant ownership has been verified.

    ``variant`` may be ``display`` or ``thumb``. A requested derivative must
    exist; public callers never receive the private original as a fallback.
    """

    if variant:
        if variant not in {"display", "thumb"}:
            raise MediaUploadError("Media variant is invalid.")
        row = fetch_one(
            conn,
            """
            SELECT storage_key, mime_type
            FROM media_variants
            WHERE tenant_id = %s AND media_asset_id = %s AND variant = %s
            """,
            (tenant_id, media_asset_id, variant),
        )
    else:
        row = fetch_one(
            conn,
            """
            SELECT storage_key, mime_type
            FROM media_assets
            WHERE tenant_id = %s AND id = %s AND storage_provider = 'local'
            """,
            (tenant_id, media_asset_id),
        )
    if not row:
        raise MediaUploadError("Media asset was not found.")
    storage_key = str(row["storage_key"] or "")
    safe_parts = [secure_filename(part) for part in storage_key.split("/") if part]
    if len(safe_parts) < 3:
        raise MediaUploadError("Media asset path is invalid.")
    directory = os.path.join(media_root(), *safe_parts[:-1])
    filename = safe_parts[-1]
    return send_from_directory(directory, filename)
