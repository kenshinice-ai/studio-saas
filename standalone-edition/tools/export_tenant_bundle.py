#!/usr/bin/env python3
"""Export one tenant as a PWE Studio Edition delivery bundle (read-only).

Platform-side half of the SaaS → Edition migration path (DATABASE.md §2 路径 1).
Unlike ``tenant_archive.archive_tenant`` this NEVER mutates the platform
database: no status change, no ``tenant_archives`` row, no audit row. It only
reads the same per-table snapshot set (``SNAPSHOT_TABLES``) and packs it —
together with a verification manifest and (optionally) the media tree — into
``<slug>-edition-bundle-<YYYYMMDD>.tar.gz`` for ``import_tenant_bundle.py``.

Usage:
    python standalone-edition/tools/export_tenant_bundle.py \
        --tenant-slug lets-paint-studio --output-dir /tmp/out [--include-media]

Requires STUDIOSAAS_DATABASE_URL (see studiosaas.db).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# The tools ship inside standalone-edition/tools/; the application modules live
# in <repo>/backend. Mirror the backend/scripts/*.py bootstrap with one extra
# parent hop: repo_root/standalone-edition/tools/x.py -> repo_root/backend.
REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from studiosaas.db import connect, fetch_all, fetch_one  # noqa: E402
# Single source of truth for the table inventory — do NOT copy the list here.
from studiosaas.services.tenant_archive import (  # noqa: E402
    SNAPSHOT_COLUMNS,
    SNAPSHOT_TABLES,
    _json_default,
)

BUNDLE_FORMAT = "pwe-studio-edition-bundle"
BUNDLE_FORMAT_VERSION = 1


def _sha256_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    """Write one pretty JSON snapshot file (same style as tenant_archive)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        encoding="utf-8",
    )


def _resolve_media_root(cli_value: str | None) -> Path:
    """Resolve the canonical media root the same way the app does."""

    import os

    if cli_value:
        return Path(cli_value).expanduser().resolve()
    env_value = os.environ.get("STUDIOSAAS_MEDIA_DIR", "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (BACKEND_ROOT / "media").resolve()


def _load_tenant(conn: Any, slug: str) -> dict[str, Any]:
    """Load the source tenant row or fail with a clear message."""

    tenant = fetch_one(
        conn,
        "SELECT id, slug, name, status, plan_code FROM tenants WHERE slug = %s",
        (slug,),
    )
    if not tenant:
        raise SystemExit(f"ERROR: tenant not found: {slug}")
    if tenant["status"] == "deleted":
        raise SystemExit(f"ERROR: tenant {slug} is deleted; nothing to export.")
    return tenant


def _snapshot_tables(conn: Any, tenant_id: str, db_dir: Path) -> dict[str, dict[str, Any]]:
    """Export every SNAPSHOT_TABLES entry to JSON and return per-file stats."""

    tables: dict[str, dict[str, Any]] = {}
    for filename, table, predicate in SNAPSHOT_TABLES:
        columns = SNAPSHOT_COLUMNS.get(table, "*")
        rows = fetch_all(conn, f"SELECT {columns} FROM {table} WHERE {predicate}", (tenant_id,))
        # Belt-and-braces: platform memberships (tenant_id IS NULL) can never
        # match the tenant predicate, but an Edition bundle must provably not
        # carry them, so filter defensively anyway.
        if table == "memberships":
            rows = [row for row in rows if row.get("tenant_id") is not None]
        if filename == "tenant.json":
            _write_json(db_dir / filename, rows[0] if rows else {})
        else:
            _write_json(db_dir / filename, rows)
        tables[filename] = {"table": table, "rows": len(rows)}
    return tables


def _copy_media(conn: Any, tenant_id: str, media_root: Path, target: Path) -> dict[str, Any]:
    """Copy the tenant media tree plus referenced storage keys into the bundle."""

    copied = 0
    total_bytes = 0

    def _copy_tree(source: Path, destination: Path) -> None:
        nonlocal copied, total_bytes
        for item in sorted(source.rglob("*")):
            if not item.is_file():
                continue
            rel = item.relative_to(source)
            dest_file = destination / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_file)
            copied += 1
            total_bytes += item.stat().st_size

    tenant_tree = media_root / str(tenant_id)
    if tenant_tree.is_dir():
        _copy_tree(tenant_tree, target / str(tenant_id))

    # Same defensive sweep as tenant_archive._copy_media: storage keys that
    # live outside media/<tenant_id>/ still belong to the tenant.
    rows = fetch_all(conn, "SELECT storage_key FROM media_assets WHERE tenant_id = %s", (tenant_id,))
    for row in rows:
        storage_key = str(row.get("storage_key") or "")
        if not storage_key or ".." in Path(storage_key).parts:
            continue
        source = media_root / storage_key
        dest_file = target / storage_key
        if source.is_file() and not dest_file.exists():
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, dest_file)
            copied += 1
            total_bytes += source.stat().st_size

    return {"included": True, "file_count": copied, "total_bytes": total_bytes}


def _ledger_totals(conn: Any, tenant_id: str) -> dict[str, str]:
    """Compute the ledger totals the importer must reproduce exactly."""

    balances = fetch_one(
        conn,
        "SELECT COALESCE(sum(balance), 0) AS total FROM credit_accounts WHERE tenant_id = %s",
        (tenant_id,),
    )
    amounts = fetch_one(
        conn,
        "SELECT COALESCE(sum(amount), 0) AS total FROM credit_transactions WHERE tenant_id = %s",
        (tenant_id,),
    )
    return {
        "credit_accounts_balance_total": str(balances["total"]),
        "credit_transactions_amount_total": str(amounts["total"]),
    }


def _schema_versions(conn: Any) -> list[str]:
    """Return applied schema_migrations versions in order."""

    rows = fetch_all(conn, "SELECT version FROM schema_migrations ORDER BY version", ())
    return [row["version"] for row in rows]


def _app_version() -> str:
    """Read the repository VERSION marker when present."""

    version_file = REPO_ROOT / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"


def main(argv: list[str] | None = None) -> int:
    """Export one tenant into a verifiable Edition delivery bundle."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-slug", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--include-media", action="store_true")
    parser.add_argument(
        "--media-dir",
        default="",
        help="Canonical media root (default: $STUDIOSAAS_MEDIA_DIR or backend/media).",
    )
    args = parser.parse_args(argv)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    date_tag = datetime.now(timezone.utc).strftime("%Y%m%d")
    bundle_name = f"{args.tenant_slug}-edition-bundle-{date_tag}"
    staging = output_dir / bundle_name
    if staging.exists():
        raise SystemExit(f"ERROR: staging directory already exists: {staging}")
    tarball = output_dir / f"{bundle_name}.tar.gz"
    if tarball.exists():
        raise SystemExit(f"ERROR: bundle already exists: {tarball}")

    with connect() as conn:
        tenant = _load_tenant(conn, args.tenant_slug)
        tenant_id = str(tenant["id"])
        if tenant["status"] != "active":
            print(f"WARN: tenant status is '{tenant['status']}' (not active); exporting anyway.")

        db_dir = staging / "db"
        tables = _snapshot_tables(conn, tenant_id, db_dir)
        ledger = _ledger_totals(conn, tenant_id)
        versions = _schema_versions(conn)

        media_info: dict[str, Any] = {"included": False, "file_count": 0, "total_bytes": 0}
        if args.include_media:
            media_root = _resolve_media_root(args.media_dir or None)
            if not media_root.is_dir():
                print(f"WARN: media root not found ({media_root}); bundle will have no media.")
            media_info = _copy_media(conn, tenant_id, media_root, staging / "media")

    files = {
        f"db/{path.name}": _sha256_file(path)
        for path in sorted(db_dir.iterdir())
        if path.is_file()
    }

    manifest = {
        "format": BUNDLE_FORMAT,
        "format_version": BUNDLE_FORMAT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "generator": "export_tenant_bundle.py",
        "source_app_version": _app_version(),
        "tenant": {
            "id": tenant_id,
            "slug": tenant["slug"],
            "name": tenant["name"],
            "status": tenant["status"],
            "plan_code": tenant["plan_code"],
        },
        "schema_migrations": versions,
        "tables": tables,
        "ledger": ledger,
        "media": media_info,
        "files": files,
        "notes": {
            # users.json is column-trimmed by SNAPSHOT_COLUMNS: password_hash
            # never leaves the platform. The importer must issue new passwords.
            "users_password_hash_excluded": True,
            "platform_memberships_excluded": True,
        },
    }
    _write_json(staging / "manifest.json", manifest)

    with tarfile.open(tarball, "w:gz") as tar:
        tar.add(staging, arcname=bundle_name)
    shutil.rmtree(staging)

    print(f"Bundle written: {tarball}")
    print(f"Bundle sha256:  {_sha256_file(tarball)}")
    print(f"Tenant:         {tenant['name']} ({tenant['slug']}) id={tenant_id}")
    print(f"Tables:         {len(tables)} files, {sum(t['rows'] for t in tables.values())} rows")
    print(
        "Ledger:         accounts balance "
        f"{ledger['credit_accounts_balance_total']}, "
        f"transactions amount {ledger['credit_transactions_amount_total']}"
    )
    if media_info["included"]:
        print(f"Media:          {media_info['file_count']} files, {media_info['total_bytes']} bytes")
    else:
        print("Media:          not included (re-run with --include-media)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
