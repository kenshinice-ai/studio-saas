"""Unit tests for single-writer portable PostgreSQL handoff."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

import pytest

from scripts import portable_database_handoff as handoff


def test_acquire_and_release_require_exact_session(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lease = tmp_path / "active-session.json"
    acquire_args = argparse.Namespace(lease=str(lease), owner_pid=123)

    assert handoff.acquire(acquire_args) == 0
    session_id = capsys.readouterr().out.strip()
    payload = json.loads(lease.read_text(encoding="utf-8"))
    assert payload["session_id"] == session_id
    assert payload["owner_pid"] == 123

    with pytest.raises(SystemExit, match="different session"):
        handoff.release(
            argparse.Namespace(lease=str(lease), session_id="not-the-owner")
        )
    assert lease.exists()

    assert handoff.release(
        argparse.Namespace(lease=str(lease), session_id=session_id)
    ) == 0
    assert not lease.exists()


def test_acquire_refuses_existing_lease(tmp_path: Path) -> None:
    lease = tmp_path / "active-session.json"
    lease.write_text(
        json.dumps(
            {
                "session_id": "existing",
                "host": "other-mac",
                "user": "tester",
                "started_at": "2026-07-29T10:00:00Z",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit, match="active lease already exists"):
        handoff.acquire(argparse.Namespace(lease=str(lease), owner_pid=456))


def test_recovery_requires_explicit_confirmation(tmp_path: Path) -> None:
    lease = tmp_path / "active-session.json"
    lease.write_text("{}", encoding="utf-8")

    with pytest.raises(SystemExit, match="Refusing stale-lease recovery"):
        handoff.recover(argparse.Namespace(lease=str(lease), confirm=""))
    assert lease.exists()

    assert handoff.recover(
        argparse.Namespace(
            lease=str(lease),
            confirm=handoff.RECOVERY_CONFIRMATION,
        )
    ) == 0
    assert not lease.exists()


def test_snapshot_validation_rejects_tampered_dump(tmp_path: Path) -> None:
    snapshot = tmp_path / "studiosaas-portable.snapshot"
    dump_bytes = b"verified"
    manifest = {
        "snapshot": snapshot.name,
        "schema_migrations": ["0001"],
        "critical_counts": {"tenants": 1},
        "size_bytes": len(dump_bytes),
        "sha256": hashlib.sha256(dump_bytes).hexdigest(),
    }
    with zipfile.ZipFile(snapshot, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("database.dump", dump_bytes)
        archive.writestr("manifest.json", json.dumps(manifest))

    assert handoff._read_snapshot_manifest(snapshot) == manifest

    with zipfile.ZipFile(snapshot, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr("database.dump", b"tampered")
        archive.writestr("manifest.json", json.dumps(manifest))
    with pytest.raises(SystemExit, match="SHA-256"):
        handoff._read_snapshot_manifest(snapshot)


def test_restore_filters_only_known_cross_version_setting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dump_path = tmp_path / "database.dump"
    dump_path.write_bytes(b"custom dump")
    commands: list[list[str]] = []

    def fake_run(
        command: list[str],
        *,
        env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if command[0] == "pg_restore":
            sql_path = Path(command[command.index("--file") + 1])
            sql_path.write_text(
                "SET transaction_timeout = 0;\n"
                "SET statement_timeout = 0;\n"
                "SELECT 1;\n",
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(handoff, "_run", fake_run)

    handoff._restore_custom_dump(
        dump_path,
        database_url="postgresql://owner@db/studiosaas",
        password="secret",
        directory=tmp_path,
    )

    compatible_sql = (tmp_path / "restore-compatible.sql").read_text(
        encoding="utf-8"
    )
    assert "transaction_timeout" not in compatible_sql
    assert "SET statement_timeout = 0;" in compatible_sql
    assert "SELECT 1;" in compatible_sql
    assert commands[0][0] == "pg_restore"
    assert commands[1][:4] == [
        "psql",
        "postgresql://owner@db/studiosaas",
        "-v",
        "ON_ERROR_STOP=1",
    ]
