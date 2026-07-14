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

    parsed = urlparse(url)
    return parsed._replace(path="/postgres").geturl()


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

    temp_db = f"{_db_name(url)}_restore_check_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    temp_url = urlparse(url)._replace(path=f"/{temp_db}").geturl()
    maintenance = _maintenance_url(url)
    try:
        _run(["psql", maintenance, "-v", "ON_ERROR_STOP=1", "-c", f"CREATE DATABASE {_quote_ident(temp_db)}"])
        _run(["pg_restore", "--no-owner", "--dbname", temp_url, str(dump_path)])
        versions = _schema_versions(temp_url)
        if not versions:
            raise SystemExit("Dry-run restore finished, but schema_migrations is empty.")
        print(json.dumps({"ok": True, "temporary_database": temp_db, "schema_migrations": versions}, indent=2))
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
    _run(["pg_restore", "--clean", "--if-exists", "--no-owner", "--dbname", url, str(dump_path)])
    versions = _schema_versions(url)
    print(json.dumps({"ok": True, "restored_database": db_name, "schema_migrations": versions}, indent=2))
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
