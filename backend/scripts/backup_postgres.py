#!/usr/bin/env python3
"""Backup and dry-run restore helpers for the StudioSaaS PostgreSQL database."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import re


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "backups" / "postgres"


def _database_url() -> str:
    """Return the configured PostgreSQL URL or fail clearly."""

    url = (os.environ.get("STUDIOSAAS_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        raise SystemExit("Set STUDIOSAAS_DATABASE_URL before running this script.")
    return url


def _run(cmd: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run a PostgreSQL command and fail with its stderr on error."""

    missing = shutil.which(cmd[0])
    if not missing:
        raise SystemExit(f"Required command not found on PATH: {cmd[0]}")
    result = subprocess.run(cmd, text=True, capture_output=True, env=env or os.environ.copy(), check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or f"{cmd[0]} failed")
    return result


def _db_name(url: str) -> str:
    """Extract the database name from a PostgreSQL URL."""

    parsed = urlparse(url)
    name = parsed.path.lstrip("/")
    if not name:
        raise SystemExit("Database URL must include a database name.")
    return name


def _maintenance_url(url: str) -> str:
    """Return a sibling URL connected to the postgres maintenance database."""

    return _database_sibling_url(url, "postgres")


def _database_sibling_url(url: str, database_name: str) -> str:
    """Replace only the database path, preserving local triple-slash URLs."""

    parsed = urlparse(url)
    if parsed.scheme and not parsed.netloc:
        suffix = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme}:///{database_name}{suffix}"
    return parsed._replace(path=f"/{database_name}").geturl()


def _quote_ident(name: str) -> str:
    """Return a safely quoted PostgreSQL identifier."""

    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
        raise SystemExit(f"Unsafe database identifier: {name}")
    return f'"{name}"'


def _schema_versions(url: str) -> list[str]:
    """Read applied schema migration versions from a database."""

    result = _run([
        "psql",
        url,
        "-At",
        "-c",
        "SELECT version FROM schema_migrations ORDER BY version",
    ])
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _critical_counts(url: str) -> dict[str, int]:
    """Return small integrity totals used to verify a restored backup."""

    tables = ("tenants", "users", "students", "registrations", "media_assets", "audit_logs")
    counts: dict[str, int] = {}
    for table in tables:
        result = _run(["psql", url, "-At", "-c", f"SELECT count(*) FROM {table}"])
        counts[table] = int(result.stdout.strip() or 0)
    return counts


def _dump_manifest(dump_path: Path) -> dict[str, object]:
    """Load and validate the companion manifest for a custom-format dump."""

    manifest_path = dump_path.with_suffix(".manifest.json")
    if not manifest_path.is_file():
        raise SystemExit(f"Backup manifest not found: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Backup manifest is invalid: {exc}") from exc
    if manifest.get("dump") != dump_path.name:
        raise SystemExit("Backup manifest does not match the selected dump.")
    if not isinstance(manifest.get("schema_migrations"), list):
        raise SystemExit("Backup manifest has no schema migration inventory.")
    if "critical_counts" in manifest and not isinstance(manifest.get("critical_counts"), dict):
        raise SystemExit("Backup manifest has invalid critical table counts.")
    if "critical_counts" not in manifest:
        print(
            "WARNING: legacy backup manifest has no critical table counts; "
            "restore verification will compare migrations only.",
            file=sys.stderr,
        )
    return manifest


def _prune_backups(directory: Path, keep: int) -> None:
    """Keep only the newest custom dumps and manifests."""

    dumps = sorted(directory.glob("studiosaas_*.dump"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_dump in dumps[keep:]:
        old_dump.unlink(missing_ok=True)
        old_dump.with_suffix(".manifest.json").unlink(missing_ok=True)


def backup(args: argparse.Namespace) -> int:
    """Create a pg_dump custom-format backup and manifest."""

    url = _database_url()
    backup_dir = Path(args.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dump_path = backup_dir / f"studiosaas_{_db_name(url)}_{timestamp}.dump"
    manifest_path = dump_path.with_suffix(".manifest.json")

    _run(["pg_dump", "--format=custom", "--no-owner", "--file", str(dump_path), url])
    manifest = {
        "created_at": timestamp,
        "database": _db_name(url),
        "dump": dump_path.name,
        "schema_migrations": _schema_versions(url),
        "critical_counts": _critical_counts(url),
        "size_bytes": dump_path.stat().st_size,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _prune_backups(backup_dir, args.keep)
    print(json.dumps({"ok": True, "dump": str(dump_path), "manifest": str(manifest_path)}, indent=2))
    return 0


def restore_dry_run(args: argparse.Namespace) -> int:
    """Restore a dump into a temporary sibling database and verify migrations."""

    url = _database_url()
    dump_path = Path(args.dump).expanduser().resolve()
    if not dump_path.exists():
        raise SystemExit(f"Dump file not found: {dump_path}")
    manifest = _dump_manifest(dump_path)

    temp_db = f"{_db_name(url)}_restore_check_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    temp_url = _database_sibling_url(url, temp_db)
    maintenance = _maintenance_url(url)
    try:
        _run(["psql", maintenance, "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {_quote_ident(temp_db)}"])
        _run(["pg_restore", "--no-owner", "--dbname", temp_url, str(dump_path)])
        versions = _schema_versions(temp_url)
        counts = _critical_counts(temp_url)
        if versions != manifest["schema_migrations"]:
            raise SystemExit("Dry-run restore migration inventory does not match the backup manifest.")
        if manifest.get("critical_counts") is not None and counts != manifest["critical_counts"]:
            raise SystemExit("Dry-run restore critical table counts do not match the backup manifest.")
        print(json.dumps({"ok": True, "temporary_database": temp_db, "schema_migrations": versions, "critical_counts": counts}, indent=2))
    finally:
        _run(["psql", maintenance, "-v", "ON_ERROR_STOP=1", "-c", f"DROP DATABASE IF EXISTS {_quote_ident(temp_db)}"])
    return 0


def restore(args: argparse.Namespace) -> int:
    """Restore a dump into the configured database after explicit confirmation."""

    url = _database_url()
    db_name = _db_name(url)
    if args.confirm != db_name:
        raise SystemExit(f"Refusing restore. Re-run with --confirm {db_name}")
    dump_path = Path(args.dump).expanduser().resolve()
    if not dump_path.exists():
        raise SystemExit(f"Dump file not found: {dump_path}")
    manifest = _dump_manifest(dump_path)
    _run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", url, str(dump_path)])
    versions = _schema_versions(url)
    counts = _critical_counts(url)
    if versions != manifest["schema_migrations"] or (
        manifest.get("critical_counts") is not None and counts != manifest["critical_counts"]
    ):
        raise SystemExit("Restore completed, but verification does not match the backup manifest.")
    print(json.dumps({"ok": True, "restored_database": db_name, "schema_migrations": versions, "critical_counts": counts}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    backup_cmd = sub.add_parser("backup", help="Create a pg_dump backup")
    backup_cmd.add_argument("--backup-dir", default=str(DEFAULT_BACKUP_DIR))
    backup_cmd.add_argument("--keep", type=int, default=14)
    backup_cmd.set_defaults(func=backup)

    dry_cmd = sub.add_parser("restore-dry-run", help="Restore into a temporary database and verify migrations")
    dry_cmd.add_argument("dump")
    dry_cmd.set_defaults(func=restore_dry_run)

    restore_cmd = sub.add_parser("restore", help="Restore into STUDIOSAAS_DATABASE_URL after explicit confirmation")
    restore_cmd.add_argument("dump")
    restore_cmd.add_argument("--confirm", default="")
    restore_cmd.set_defaults(func=restore)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Script entrypoint."""

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
