#!/usr/bin/env python3
"""Safely hand a local PostgreSQL database between iCloud-synced Macs.

This helper deliberately supports a single active writer.  It never syncs a
live PostgreSQL data directory.  Instead, a launcher acquires an iCloud-synced
lease, restores the last verified custom-format dump into the local database,
and publishes a new verified dump before releasing the lease on shutdown.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import sys
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

try:
    from .backup_postgres import (
        _critical_counts,
        _database_url,
        _db_name,
        _run,
        _schema_versions,
        _split_password,
    )
except ImportError:
    from backup_postgres import (  # type: ignore[no-redef]
        _critical_counts,
        _database_url,
        _db_name,
        _run,
        _schema_versions,
        _split_password,
    )


RECOVERY_CONFIRMATION = "OTHER-DEVICE-IS-STOPPED"
UNSUPPORTED_RESTORE_SETTINGS = {
    "SET transaction_timeout = 0;\n",
}


def _utc_timestamp() -> str:
    """Return a stable, human-readable UTC timestamp."""

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sha256(path: Path) -> str:
    """Return the SHA-256 digest of a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path, label: str) -> dict[str, object]:
    """Load a JSON object or fail with a precise handoff error."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"{label} not found: {path}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"{label} is invalid: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{label} must contain a JSON object: {path}")
    return payload


def _write_private_json(path: Path, payload: dict[str, object]) -> None:
    """Write owner-only JSON atomically in the destination directory."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(0o600)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _lease_details(path: Path) -> str:
    """Return concise existing-lease details without exposing credentials."""

    try:
        lease = _load_json(path, "Portable database lease")
    except SystemExit as exc:
        return str(exc)
    return (
        f"host={lease.get('host', 'unknown')}, "
        f"user={lease.get('user', 'unknown')}, "
        f"started_at={lease.get('started_at', 'unknown')}"
    )


def acquire(args: argparse.Namespace) -> int:
    """Acquire an exclusive portable-database lease and print its session ID."""

    lease_path = Path(args.lease).expanduser().resolve()
    lease_path.parent.mkdir(parents=True, exist_ok=True)
    session_id = str(uuid.uuid4())
    lease = {
        "schema_version": 1,
        "session_id": session_id,
        "host": socket.gethostname(),
        "user": os.environ.get("USER") or "unknown",
        "owner_pid": args.owner_pid,
        "started_at": _utc_timestamp(),
    }
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(lease_path, flags, 0o600)
    except FileExistsError as exc:
        raise SystemExit(
            "Portable database is not available for handoff: an active lease "
            f"already exists ({_lease_details(lease_path)}). Stop StudioSaaS on "
            "the other Mac and wait for iCloud to finish syncing. If that Mac "
            f"crashed, run recovery with --confirm {RECOVERY_CONFIRMATION}."
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(lease, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        lease_path.unlink(missing_ok=True)
        raise
    print(session_id)
    return 0


def release(args: argparse.Namespace) -> int:
    """Release a lease only when the caller owns the exact session."""

    lease_path = Path(args.lease).expanduser().resolve()
    lease = _load_json(lease_path, "Portable database lease")
    if lease.get("session_id") != args.session_id:
        raise SystemExit(
            "Refusing to release a portable database lease owned by a "
            "different session."
        )
    lease_path.unlink()
    print(json.dumps({"ok": True, "released": str(lease_path)}))
    return 0


def recover(args: argparse.Namespace) -> int:
    """Remove a stale lease after explicit confirmation of single-writer safety."""

    if args.confirm != RECOVERY_CONFIRMATION:
        raise SystemExit(
            "Refusing stale-lease recovery. First verify StudioSaaS is stopped "
            f"on the other Mac, then pass --confirm {RECOVERY_CONFIRMATION}."
        )
    lease_path = Path(args.lease).expanduser().resolve()
    previous = _lease_details(lease_path) if lease_path.exists() else "no lease"
    lease_path.unlink(missing_ok=True)
    print(json.dumps({"ok": True, "recovered": str(lease_path), "previous": previous}))
    return 0


def _snapshot_path(snapshot_value: str) -> Path:
    """Return the canonical atomic snapshot archive path."""

    return Path(snapshot_value).expanduser().resolve()


def _read_snapshot_manifest(
    snapshot_path: Path,
    *,
    expected_snapshot_name: str | None = None,
) -> dict[str, object]:
    """Validate one atomic snapshot archive and return its manifest.

    ``expected_snapshot_name`` is used only while validating a completed
    temporary archive immediately before its atomic rename.
    """

    if not snapshot_path.is_file():
        raise SystemExit(f"Portable database snapshot not found: {snapshot_path}")
    try:
        with zipfile.ZipFile(snapshot_path, "r") as archive:
            if set(archive.namelist()) != {"database.dump", "manifest.json"}:
                raise SystemExit(
                    "Portable database snapshot must contain only database.dump "
                    "and manifest.json."
                )
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise SystemExit(
                    f"Portable database manifest is invalid: {exc}"
                ) from exc
            if not isinstance(manifest, dict):
                raise SystemExit("Portable database manifest must be a JSON object.")
            dump_info = archive.getinfo("database.dump")
            digest = hashlib.sha256()
            with archive.open("database.dump", "r") as dump_handle:
                for chunk in iter(lambda: dump_handle.read(1024 * 1024), b""):
                    digest.update(chunk)
    except (OSError, zipfile.BadZipFile) as exc:
        raise SystemExit(f"Portable database snapshot is invalid: {exc}") from exc

    expected_name = expected_snapshot_name or snapshot_path.name
    if manifest.get("snapshot") != expected_name:
        raise SystemExit("Portable database manifest does not match the snapshot filename.")
    if not isinstance(manifest.get("schema_migrations"), list):
        raise SystemExit("Portable database manifest has no migration inventory.")
    if not isinstance(manifest.get("critical_counts"), dict):
        raise SystemExit("Portable database manifest has no critical table counts.")
    expected_size = manifest.get("size_bytes")
    if expected_size != dump_info.file_size:
        raise SystemExit("Portable database dump size does not match its manifest.")
    expected_digest = manifest.get("sha256")
    if not isinstance(expected_digest, str) or digest.hexdigest() != expected_digest:
        raise SystemExit("Portable database dump SHA-256 does not match its manifest.")
    return manifest


def _extract_verified_dump(snapshot_path: Path, directory: Path) -> Path:
    """Extract the already validated dump member to a private temporary path."""

    destination = directory / "database.dump"
    with zipfile.ZipFile(snapshot_path, "r") as archive:
        with archive.open("database.dump", "r") as source:
            with destination.open("wb") as target:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    target.write(chunk)
    destination.chmod(0o600)
    return destination


def _restore_custom_dump(
    dump_path: Path,
    *,
    database_url: str,
    password: str | None,
    directory: Path,
) -> None:
    """Restore a custom dump across supported PostgreSQL server versions.

    Newer ``pg_dump`` clients can add session settings that do not exist on an
    older target server.  Generate SQL first and remove only explicitly known,
    semantics-free session settings.  The SQL restore itself remains strict:
    ``ON_ERROR_STOP`` rejects every other incompatibility or data error.
    """

    restore_sql = directory / "restore.sql"
    compatible_sql = directory / "restore-compatible.sql"
    _run(
        [
            "pg_restore",
            "--clean",
            "--if-exists",
            "--no-owner",
            "--file",
            str(restore_sql),
            str(dump_path),
        ]
    )
    with restore_sql.open("r", encoding="utf-8") as source:
        with compatible_sql.open("w", encoding="utf-8") as destination:
            for line in source:
                if line not in UNSUPPORTED_RESTORE_SETTINGS:
                    destination.write(line)
    compatible_sql.chmod(0o600)

    restore_env = os.environ.copy()
    if password:
        restore_env["PGPASSWORD"] = password
    _run(
        [
            "psql",
            database_url,
            "-v",
            "ON_ERROR_STOP=1",
            "--file",
            str(compatible_sql),
        ],
        env=restore_env,
    )


def export_snapshot(args: argparse.Namespace) -> int:
    """Publish one verified snapshot archive using a single atomic replacement."""

    url = _database_url()
    snapshot_path = _snapshot_path(args.snapshot)
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_dump = snapshot_path.with_name(
        f".{snapshot_path.name}.{uuid.uuid4().hex}.dump.tmp"
    )
    temporary_snapshot = snapshot_path.with_name(
        f".{snapshot_path.name}.{uuid.uuid4().hex}.tmp"
    )
    argv_url, password = _split_password(url)
    dump_env = os.environ.copy()
    if password:
        dump_env["PGPASSWORD"] = password
    try:
        _run(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--file",
                str(temporary_dump),
                argv_url,
            ],
            env=dump_env,
        )
        temporary_dump.chmod(0o600)
        manifest = {
            "schema_version": 1,
            "created_at": _utc_timestamp(),
            "source_host": socket.gethostname(),
            "database": _db_name(url),
            "snapshot": snapshot_path.name,
            "schema_migrations": _schema_versions(url),
            "critical_counts": _critical_counts(url),
            "size_bytes": temporary_dump.stat().st_size,
            "sha256": _sha256(temporary_dump),
        }
        with zipfile.ZipFile(
            temporary_snapshot,
            "w",
            compression=zipfile.ZIP_STORED,
        ) as archive:
            archive.write(temporary_dump, arcname="database.dump")
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, indent=2) + "\n",
            )
        temporary_snapshot.chmod(0o600)
        _read_snapshot_manifest(
            temporary_snapshot,
            expected_snapshot_name=snapshot_path.name,
        )
        os.replace(temporary_snapshot, snapshot_path)
        _read_snapshot_manifest(snapshot_path)
    finally:
        temporary_dump.unlink(missing_ok=True)
        temporary_snapshot.unlink(missing_ok=True)
    print(
        json.dumps(
            {
                "ok": True,
                "snapshot": str(snapshot_path),
                "sha256": manifest["sha256"],
                "critical_counts": manifest["critical_counts"],
            },
            indent=2,
        )
    )
    return 0


def restore_snapshot(args: argparse.Namespace) -> int:
    """Replace the local target database with the last verified snapshot."""

    url = _database_url()
    snapshot_path = _snapshot_path(args.snapshot)
    manifest = _read_snapshot_manifest(snapshot_path)
    argv_url, password = _split_password(url)
    with tempfile.TemporaryDirectory(
        prefix="studiosaas-portable-restore-",
        dir=snapshot_path.parent,
    ) as temporary_directory:
        dump_path = _extract_verified_dump(
            snapshot_path,
            Path(temporary_directory),
        )
        _restore_custom_dump(
            dump_path,
            database_url=argv_url,
            password=password,
            directory=Path(temporary_directory),
        )
    versions = _schema_versions(url)
    counts = _critical_counts(url)
    if versions != manifest["schema_migrations"]:
        raise SystemExit(
            "Portable database restore migration inventory does not match the snapshot."
        )
    if counts != manifest["critical_counts"]:
        raise SystemExit(
            "Portable database restore critical table counts do not match the snapshot."
        )
    print(
        json.dumps(
            {
                "ok": True,
                "restored_database": _db_name(url),
                "schema_migrations": versions,
                "critical_counts": counts,
            },
            indent=2,
        )
    )
    return 0


def inspect_snapshot(args: argparse.Namespace) -> int:
    """Validate and print non-secret snapshot metadata."""

    snapshot_path = _snapshot_path(args.snapshot)
    manifest = _read_snapshot_manifest(snapshot_path)
    print(json.dumps({"ok": True, **manifest}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit portable handoff command interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    acquire_parser = subcommands.add_parser("acquire")
    acquire_parser.add_argument("--lease", required=True)
    acquire_parser.add_argument("--owner-pid", required=True, type=int)
    acquire_parser.set_defaults(func=acquire)

    release_parser = subcommands.add_parser("release")
    release_parser.add_argument("--lease", required=True)
    release_parser.add_argument("--session-id", required=True)
    release_parser.set_defaults(func=release)

    recover_parser = subcommands.add_parser("recover")
    recover_parser.add_argument("--lease", required=True)
    recover_parser.add_argument("--confirm", default="")
    recover_parser.set_defaults(func=recover)

    for name, function in (
        ("export", export_snapshot),
        ("restore", restore_snapshot),
        ("inspect", inspect_snapshot),
    ):
        command_parser = subcommands.add_parser(name)
        command_parser.add_argument("--snapshot", required=True)
        command_parser.set_defaults(func=function)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the selected handoff command."""

    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
