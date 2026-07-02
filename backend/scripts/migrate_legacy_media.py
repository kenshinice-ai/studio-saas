#!/usr/bin/env python3
"""Migrate legacy CMS photo and portfolio files into tenant media_assets.

The script is intentionally narrow: it imports the old JSON-backed media
references for one tenant, writes canonical v1 media rows, links student photos
and portfolio items, and optionally removes the successfully imported old files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import uuid
from datetime import date
from pathlib import Path, PurePath
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = APP_ROOT.parent
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from studiosaas.db import DatabaseUnavailableError, connect, fetch_one

IMAGE_MIME_BY_EXT = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def parse_args() -> argparse.Namespace:
    """Parse migration options."""

    parser = argparse.ArgumentParser(description="Migrate legacy CMS media into StudioSaaS v1.")
    parser.add_argument("--tenant-slug", required=True, help="Tenant slug that owns the legacy JSON data.")
    parser.add_argument("--legacy-db", default=str(APP_ROOT / "database.json"), help="Path to legacy database.json.")
    parser.add_argument("--photos-dir", default=str(APP_ROOT / "photos"), help="Legacy photos directory.")
    parser.add_argument("--portfolio-dir", default=str(APP_ROOT / "portfolio"), help="Legacy portfolio directory.")
    parser.add_argument("--media-dir", default=str(APP_ROOT / "media"), help="Canonical media output directory.")
    parser.add_argument("--delete-files", action="store_true", help="Delete old files after a successful import.")
    parser.add_argument("--dry-run", action="store_true", help="Report actions without writing database/files.")
    return parser.parse_args()


def load_legacy_db(path: Path) -> dict[str, Any]:
    """Load and validate a legacy JSON database."""

    if not path.exists():
        return {"students": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("students"), list):
        raise ValueError("legacy database must contain a students list")
    return payload


def safe_legacy_file(base_dir: Path, *parts: str) -> Path | None:
    """Return a legacy file path only when every segment is path-safe."""

    clean_parts = []
    for part in parts:
        text = str(part or "").strip()
        if not text or PurePath(text).name != text or "/" in text or "\\" in text:
            return None
        clean_parts.append(text)
    path = base_dir.joinpath(*clean_parts)
    try:
        path.resolve().relative_to(base_dir.resolve())
    except ValueError:
        return None
    return path if path.is_file() else None


def file_mime(path: Path) -> str:
    """Return a conservative MIME type from a supported media extension."""

    return IMAGE_MIME_BY_EXT.get(path.suffix.lower(), "application/octet-stream")


def ensure_media_schema(conn) -> None:
    """Add canonical media columns/constraints to older local databases."""

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


def find_student(conn, tenant_id: str, legacy_student: dict[str, Any]) -> str | None:
    """Find the v1 student matching one legacy student record."""

    legacy_id = str(legacy_student.get("id") or "").strip()
    if legacy_id:
        row = fetch_one(
            conn,
            "SELECT id FROM students WHERE tenant_id = %s AND source_legacy_id = %s",
            (tenant_id, legacy_id),
        )
        if row:
            return str(row["id"])
    display = str(legacy_student.get("name") or "").strip()
    mobile = re.sub(r"[^0-9]", "", str(legacy_student.get("mobile") or ""))
    if not display or not mobile:
        return None
    row = fetch_one(
        conn,
        """
        SELECT id FROM students
        WHERE tenant_id = %s
          AND lower(display_name) = lower(%s)
          AND regexp_replace(mobile, '[^0-9]', '', 'g') = %s
        LIMIT 1
        """,
        (tenant_id, display, mobile),
    )
    return str(row["id"]) if row else None


def import_media(conn, *, tenant_id: str, student_id: str, asset_type: str, path: Path, media_dir: Path, dry_run: bool) -> str:
    """Copy one legacy file into canonical media storage and return media asset id."""

    data = path.read_bytes()
    checksum = hashlib.sha256(data).hexdigest()
    existing = fetch_one(
        conn,
        """
        SELECT id FROM media_assets
        WHERE tenant_id = %s
          AND owner_student_id = %s
          AND asset_type = %s
          AND original_filename = %s
          AND checksum_sha256 = %s
        LIMIT 1
        """,
        (tenant_id, student_id, asset_type, path.name, checksum),
    )
    if existing:
        return str(existing["id"])
    media_id = str(uuid.uuid4())
    ext = path.suffix.lower()
    storage_key = f"{tenant_id}/{asset_type}/{media_id}{ext}"
    output = media_dir / tenant_id / asset_type / f"{media_id}{ext}"
    if dry_run:
        return media_id
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, output)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO media_assets (
                id, tenant_id, owner_student_id, asset_type, storage_provider, storage_key,
                original_filename, mime_type, byte_size, checksum_sha256, visibility
            )
            VALUES (%s, %s, %s, %s, 'local', %s, %s, %s, %s, %s, 'private')
            RETURNING id
            """,
            (
                media_id,
                tenant_id,
                student_id,
                asset_type,
                storage_key,
                path.name,
                file_mime(path),
                path.stat().st_size,
                checksum,
            ),
        )
    return media_id


def refresh_usage(conn, tenant_id: str) -> None:
    """Refresh tenant usage counters after migration."""

    usage = fetch_one(
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
            (tenant_id, usage["student_count"] or 0, usage["user_count"] or 0, usage["storage_used_mb"] or 0),
        )


def main() -> int:
    """Run the legacy media import."""

    args = parse_args()
    legacy_db = load_legacy_db(Path(args.legacy_db))
    photos_dir = Path(args.photos_dir)
    portfolio_dir = Path(args.portfolio_dir)
    media_dir = Path(args.media_dir)
    imported = 0
    removed = 0
    skipped = 0
    old_files: list[Path] = []

    try:
        with connect() as conn:
            ensure_media_schema(conn)
            tenant = fetch_one(conn, "SELECT id FROM tenants WHERE slug = %s", (args.tenant_slug,))
            if not tenant:
                raise ValueError(f"Tenant '{args.tenant_slug}' was not found.")
            tenant_id = str(tenant["id"])
            for legacy_student in legacy_db.get("students", []):
                student_id = find_student(conn, tenant_id, legacy_student)
                if not student_id:
                    skipped += 1
                    continue
                photo_file = safe_legacy_file(photos_dir, legacy_student.get("photo", ""))
                if photo_file:
                    media_id = import_media(
                        conn,
                        tenant_id=tenant_id,
                        student_id=student_id,
                        asset_type="student_photo",
                        path=photo_file,
                        media_dir=media_dir,
                        dry_run=args.dry_run,
                    )
                    if not args.dry_run:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                UPDATE students
                                SET student_photo_asset_id = %s, updated_at = now()
                                WHERE tenant_id = %s AND id = %s
                                """,
                                (media_id, tenant_id, student_id),
                            )
                    imported += 1
                    old_files.append(photo_file)
                for item in legacy_student.get("portfolio") or []:
                    portfolio_file = safe_legacy_file(
                        portfolio_dir,
                        str(legacy_student.get("id") or ""),
                        item.get("filename", ""),
                    )
                    if not portfolio_file:
                        continue
                    media_id = import_media(
                        conn,
                        tenant_id=tenant_id,
                        student_id=student_id,
                        asset_type="portfolio",
                        path=portfolio_file,
                        media_dir=media_dir,
                        dry_run=args.dry_run,
                    )
                    if not args.dry_run:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                INSERT INTO portfolio_items (
                                    tenant_id, student_id, media_asset_id, title, description,
                                    artwork_date, visibility
                                )
                                SELECT %s, %s, %s, '', %s, %s, 'private'
                                WHERE NOT EXISTS (
                                    SELECT 1 FROM portfolio_items
                                    WHERE tenant_id = %s AND student_id = %s AND media_asset_id = %s
                                )
                                """,
                                (
                                    tenant_id,
                                    student_id,
                                    media_id,
                                    str(item.get("note") or "")[:500],
                                    item.get("date") or date.today().isoformat(),
                                    tenant_id,
                                    student_id,
                                    media_id,
                                ),
                            )
                    imported += 1
                    old_files.append(portfolio_file)
            if not args.dry_run:
                refresh_usage(conn, tenant_id)
                conn.commit()
    except (DatabaseUnavailableError, ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"Legacy media migration failed: {exc}", file=sys.stderr)
        return 1

    if args.delete_files and not args.dry_run:
        for path in sorted(set(old_files)):
            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                pass
    print(f"Imported {imported} media reference(s), skipped {skipped} student(s), removed {removed} old file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
