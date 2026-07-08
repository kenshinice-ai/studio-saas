"""Canonical tenant media upload and retrieval service."""

from __future__ import annotations

import hashlib
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
    _HAS_PIL = True
except ImportError:  # pragma: no cover - depends on environment
    _HAS_PIL = False

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".heif"}
HEIC_EXTENSIONS = {".heic", ".heif"}
DOCUMENT_EXTENSIONS = {".pdf"}

# S3 (v4.4 U3): lazy thumbnails for list views. 360px longest side.
THUMB_MAX = 360
THUMB_SUFFIX = ".thumb.jpg"
THUMB_SOURCE_MIMES = {"image/jpeg", "image/png", "image/webp"}
MEDIA_UPLOAD_LIMITS = {
    "student_photo": (IMAGE_EXTENSIONS, 5 * 1024 * 1024),
    "registration_photo": (IMAGE_EXTENSIONS, 5 * 1024 * 1024),
    "portfolio": (IMAGE_EXTENSIONS, 10 * 1024 * 1024),
    "homework": (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS, 10 * 1024 * 1024),
    "sheet_music": (IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS, 15 * 1024 * 1024),
    "logo": ({".jpg", ".jpeg", ".png", ".webp", ".svg"}, 5 * 1024 * 1024),
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
            CHECK (asset_type IN ('student_photo', 'registration_photo', 'portfolio', 'homework', 'sheet_music', 'logo'))
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
            (SELECT COALESCE(ceil(sum(byte_size) / 1048576.0), 0) FROM media_assets WHERE tenant_id = %s) AS storage_used_mb
        """,
        (tenant_id, tenant_id, tenant_id),
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


def convert_heic_to_jpeg(data: bytes) -> bytes | None:
    """Convert HEIC/HEIF bytes to JPEG; returns None on any failure.

    Never raises — callers decide how to report. Deliberately avoids any
    per-pixel expansion (see the v5.2.2 OOM incident in the reference CMS).
    """

    if not _HAS_PIL:
        return None
    try:
        import io as _io

        from pillow_heif import register_heif_opener
        register_heif_opener()
        image = _PILImage.open(_io.BytesIO(data))
        image = image.convert("RGB")
        out = _io.BytesIO()
        image.save(out, format="JPEG", quality=90)
        return out.getvalue()
    except Exception:
        return None


def _enforce_tenant_quota(conn: Any, *, tenant_id: str, incoming_bytes: int) -> None:
    """Reject uploads that would exceed the tenant's plan storage limit."""

    row = fetch_one(
        conn,
        """
        SELECT COALESCE(sum(m.byte_size), 0)::bigint AS used_bytes,
               p.storage_limit_mb
        FROM tenants t
        LEFT JOIN media_assets m ON m.tenant_id = t.id
        LEFT JOIN plans p ON p.code = t.plan_code
        WHERE t.id = %s
        GROUP BY p.storage_limit_mb
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
    if ext in HEIC_EXTENSIONS:
        converted = convert_heic_to_jpeg(data)
        if converted is None:
            raise MediaUploadError(
                "HEIC photos could not be converted on this server. Please upload JPG or PNG."
            )
        data, ext, mime_type = converted, ".jpg", "image/jpeg"
    _enforce_tenant_quota(conn, tenant_id=tenant_id, incoming_bytes=len(data))

    media_id = str(uuid.uuid4())
    tenant_part = str(tenant_id)
    safe_kind = re.sub(r"[^a-z0-9_-]", "_", kind.lower())
    storage_key = f"{tenant_part}/{safe_kind}/{media_id}{ext}"
    full_path = os.path.join(media_root(), tenant_part, safe_kind, f"{media_id}{ext}")
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "wb") as fh:
        fh.write(data)

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
            refresh_tenant_usage(conn, tenant_id)
    except Exception:
        try:
            os.remove(full_path)
        except OSError:
            pass
        raise
    return row


def _ensure_thumbnail(full_path: str) -> str | None:
    """Lazily create ``<file>.thumb.jpg`` (longest side THUMB_MAX).

    Returns the thumbnail filename or None when unavailable — callers
    fall back to the original file, never error.
    """

    if not _HAS_PIL or not os.path.isfile(full_path):
        return None
    thumb_path = full_path + THUMB_SUFFIX
    if os.path.isfile(thumb_path):
        return os.path.basename(thumb_path)
    try:
        image = _PILImage.open(full_path)
        image.thumbnail((THUMB_MAX, THUMB_MAX))
        image.convert("RGB").save(thumb_path, format="JPEG", quality=85)
        return os.path.basename(thumb_path)
    except Exception:
        return None


def send_media_asset(conn: Any, *, tenant_id: str, media_asset_id: str, thumb: bool = False):
    """Serve one media asset after tenant ownership has been verified.

    ``thumb=True`` serves a lazily generated 360px thumbnail for raster
    images (S3); anything else falls back to the original file.
    """

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
    if thumb and str(row["mime_type"] or "") in THUMB_SOURCE_MIMES:
        thumb_name = _ensure_thumbnail(os.path.join(directory, filename))
        if thumb_name:
            filename = thumb_name
    return send_from_directory(directory, filename)
