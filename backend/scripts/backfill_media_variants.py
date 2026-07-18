#!/usr/bin/env python3
"""Generate privacy-safe display and thumbnail variants for existing media.

The script never modifies original files. It reports every asset that cannot be
decoded and exits non-zero when any requested derivative is missing, so a
deployment cannot silently expose or fall back to an original image.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path
from werkzeug.utils import secure_filename

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.db import connect, fetch_all  # noqa: E402
from studiosaas.services.media import (  # noqa: E402
    IMAGE_EXTENSIONS,
    MediaUploadError,
    _build_safe_variants,
    media_root,
    refresh_tenant_usage,
)


def run(*, dry_run: bool = False, tenant_id: str = "", check: bool = False) -> int:
    """Backfill missing derivatives and return a process exit status."""

    import server

    failures: list[str] = []
    generated = 0
    with server.app.app_context(), connect() as conn:
        filters = ["m.storage_provider = 'local'"]
        params: list[object] = []
        if tenant_id:
            filters.append("m.tenant_id = %s")
            params.append(tenant_id)
        rows = fetch_all(
            conn,
            f"""
            SELECT m.id, m.tenant_id, m.storage_key, m.mime_type,
                   bool_or(v.variant = 'display') AS has_display,
                   bool_or(v.variant = 'thumb') AS has_thumb
            FROM media_assets m
            LEFT JOIN media_variants v
              ON v.tenant_id = m.tenant_id AND v.media_asset_id = m.id
            WHERE {' AND '.join(filters)}
            GROUP BY m.id, m.tenant_id, m.storage_key, m.mime_type
            ORDER BY m.created_at, m.id
            """,
            tuple(params),
        )
        for row in rows:
            ext = Path(str(row["storage_key"])).suffix.lower()
            if ext not in IMAGE_EXTENSIONS:
                continue
            missing = [
                variant
                for variant, present in (
                    ("display", bool(row["has_display"])),
                    ("thumb", bool(row["has_thumb"])),
                )
                if not present
            ]
            if not missing:
                continue
            storage_parts = str(row["storage_key"]).split("/")
            if (
                len(storage_parts) < 2
                or any(part in {"", ".", ".."} for part in storage_parts)
                or any(secure_filename(part) != part for part in storage_parts)
            ):
                failures.append(f"{row['tenant_id']}/{row['id']}: invalid storage key")
                continue
            original = os.path.join(media_root(), *storage_parts)
            try:
                data = Path(original).read_bytes()
                variants = _build_safe_variants(data, ext)
            except (OSError, MediaUploadError) as exc:
                failures.append(f"{row['tenant_id']}/{row['id']}: {exc}")
                continue
            if dry_run:
                generated += len(missing)
                continue
            # Legacy imports may use shared two-part paths such as
            # ``fixtures/alpha.png``. Derivatives always move into a new
            # tenant-prefixed namespace so one tenant can never overwrite
            # another tenant's generated public file.
            directory_parts = [str(row["tenant_id"]), "backfill"]
            directory = os.path.join(media_root(), *directory_parts)
            os.makedirs(directory, exist_ok=True)
            written_paths: list[str] = []
            asset_generated = 0
            try:
                with conn.cursor() as cur:
                    for variant in missing:
                        payload, width, height = variants[variant]
                        filename = f"{row['id']}.{variant}.jpg"
                        path = os.path.join(directory, filename)
                        Path(path).write_bytes(payload)
                        written_paths.append(path)
                        storage_key = "/".join(directory_parts + [filename])
                        cur.execute(
                            """
                            INSERT INTO media_variants (
                                tenant_id, media_asset_id, variant, storage_key,
                                mime_type, byte_size, checksum_sha256, pixel_width,
                                pixel_height, metadata_sanitized
                            ) VALUES (%s, %s, %s, %s, 'image/jpeg', %s, %s, %s, %s, true)
                            ON CONFLICT (tenant_id, media_asset_id, variant) DO NOTHING
                            """,
                            (
                                row["tenant_id"],
                                row["id"],
                                variant,
                                storage_key,
                                len(payload),
                                hashlib.sha256(payload).hexdigest(),
                                width,
                                height,
                            ),
                        )
                        asset_generated += cur.rowcount
                refresh_tenant_usage(conn, str(row["tenant_id"]))
                conn.commit()
                generated += asset_generated
            except Exception as exc:
                conn.rollback()
                for path in written_paths:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                failures.append(f"{row['tenant_id']}/{row['id']}: {exc}")

    print(f"Generated variants: {generated}")
    if failures:
        print("Failed assets:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    if check and generated:
        print(
            f"ERROR: {generated} media variant(s) are missing. Run this script without --check.",
            file=sys.stderr,
        )
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true", help="Exit non-zero if any derivative is missing.")
    parser.add_argument("--tenant-id", default="")
    args = parser.parse_args()
    if args.check and args.dry_run:
        parser.error("--check already performs a read-only scan; do not combine it with --dry-run")
    return run(dry_run=args.dry_run or args.check, tenant_id=args.tenant_id, check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
