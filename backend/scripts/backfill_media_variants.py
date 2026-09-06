#!/usr/bin/env python3
"""Generate privacy-safe display, medium and thumbnail variants for existing media.

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
    detect_mime,
    media_root,
    refresh_tenant_usage,
)

# 造世界的脚本用属主连接：v10.3.0 起租户表受 RLS 约束，应用角色在没有租户
# 上下文时写不进去 —— 而这些脚本的工作正是建出那个上下文本身。
try:
    from studiosaas.db import use_owner_connection as _use_owner
    _use_owner()
except Exception:
    pass


def run(*, dry_run: bool = False, tenant_id: str = "", check: bool = False) -> int:
    """Backfill missing derivatives and return a process exit status."""

    import server

    # Four conditions, reported under four names. They used to share one bucket
    # called "Failed assets", and verify_local.sh summarised that bucket as
    # "media derivative backfill is incomplete" — naming the one of the four
    # that had zero instances while 40 rows failed for a different reason
    # entirely. A gate that says the wrong cause costs more than one that says
    # nothing.
    invalid_keys: list[str] = []
    absent_originals: list[str] = []
    unreadable: list[str] = []
    undecodable: list[str] = []
    failures: list[str] = []   # write failures from the generation path below
    generated = 0
    root_label = "<unresolved>"
    with server.app.app_context(), connect() as conn:
        # media_root() needs the app context, and the report is printed after
        # the block closes — so read it here, once.
        root_label = media_root()
        filters = ["m.storage_provider = 'local'"]
        params: list[object] = []
        if tenant_id:
            filters.append("m.tenant_id = %s")
            params.append(tenant_id)
        rows = fetch_all(
            conn,
            f"""
            SELECT m.id, m.tenant_id, m.storage_key, m.mime_type,
                   max(CASE WHEN v.variant = 'display' THEN v.storage_key END) AS display_key,
                   max(CASE WHEN v.variant = 'medium' THEN v.storage_key END) AS medium_key,
                   max(CASE WHEN v.variant = 'thumb' THEN v.storage_key END) AS thumb_key
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
            # A variant counts as present only when its ROW and its FILE both
            # exist. Checking the row alone made this script blind to the most
            # likely production inconsistency: a database restored from a dump
            # alongside a media tree that is incomplete or was copied from a
            # different install. The rows were there, the derivatives were not,
            # and every brand logo served 404 while this script reported
            # "Generated variants: 0".
            missing: list[str] = []
            stale_rows: list[str] = []
            for variant, key in (
                ("display", row["display_key"]),
                ("medium", row["medium_key"]),
                ("thumb", row["thumb_key"]),
            ):
                if not key:
                    missing.append(variant)
                    continue
                if not Path(os.path.join(media_root(), *str(key).split("/"))).is_file():
                    missing.append(variant)
                    # The row describes a file that is gone; its byte_size and
                    # checksum no longer describe anything. Replace it rather
                    # than leaving a record that cannot be verified.
                    stale_rows.append(variant)
            storage_parts = str(row["storage_key"]).split("/")
            if (
                len(storage_parts) < 2
                or any(part in {"", ".", ".."} for part in storage_parts)
                or any(secure_filename(part) != part for part in storage_parts)
            ):
                invalid_keys.append(
                    f"{row['tenant_id']}/{row['id']}: {row['storage_key']}"
                )
                continue
            original = os.path.join(media_root(), *storage_parts)
            # The original is checked BEFORE the derivative early-return. A row
            # whose three derivatives are all present but whose original is gone
            # is a real defect — the download and re-crop paths 404 — and this
            # script could not see it at all, because `if not missing: continue`
            # came first.
            if not Path(original).is_file():
                absent_originals.append(
                    f"{row['tenant_id']}/{row['id']}: {row['storage_key']}"
                )
                continue
            if not missing:
                continue
            try:
                data = Path(original).read_bytes()
                variants = _build_safe_variants(data, ext)
            except OSError as exc:
                unreadable.append(f"{row['tenant_id']}/{row['id']}: {exc}")
                continue
            except MediaUploadError as exc:
                undecodable.append(f"{row['tenant_id']}/{row['id']}: {exc}")
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
                    if stale_rows:
                        cur.execute(
                            """
                            DELETE FROM media_variants
                            WHERE tenant_id = %s AND media_asset_id = %s
                              AND variant = ANY(%s)
                            """,
                            (row["tenant_id"], row["id"], stale_rows),
                        )
                    for variant in missing:
                        payload, width, height, variant_ext = variants[variant]
                        filename = f"{row['id']}.{variant}{variant_ext}"
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
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, true)
                            ON CONFLICT (tenant_id, media_asset_id, variant) DO NOTHING
                            """,
                            (
                                row["tenant_id"],
                                row["id"],
                                variant,
                                storage_key,
                                detect_mime(variant_ext),
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

    # Name the directory that was measured. backend/media is untracked runtime
    # data, so a git worktree gets whatever happens to be there while the
    # database is shared — and the checker then reports the wrong tree's
    # contents as a defect. Saying which root it read makes that legible at a
    # glance instead of after an hour.
    print(f"Media root: {root_label}")
    print(f"Generated variants: {generated}")
    problems = 0
    for label, bucket, hint in (
        ("ORIGINAL FILE ABSENT", absent_originals,
         "the database row points at a file this media root does not contain. "
         "Either the media tree belongs to a different install, or it was "
         "written by another checkout. Derivatives cannot be built from nothing."),
        ("ORIGINAL UNREADABLE", unreadable,
         "the file exists but could not be read (permissions, truncation)."),
        ("ORIGINAL UNDECODABLE", undecodable,
         "the file exists and reads, but is not a decodable image."),
        ("INVALID STORAGE KEY", invalid_keys,
         "the stored path is not a safe tenant-scoped key; refusing to touch it."),
        ("WRITE FAILED", failures,
         "generation was attempted and rolled back."),
    ):
        if not bucket:
            continue
        problems += len(bucket)
        print(f"\n{label} ({len(bucket)}) — {hint}", file=sys.stderr)
        for item in bucket:
            print(f"- {item}", file=sys.stderr)
    if problems:
        return 1
    if check and generated:
        print(
            f"ERROR: {generated} DERIVATIVE(s) are missing while their originals "
            "are present. Run this script without --check to build them.",
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
