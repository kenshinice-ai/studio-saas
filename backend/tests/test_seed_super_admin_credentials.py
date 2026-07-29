"""Tests for protected launcher credential persistence."""

from __future__ import annotations

import stat
from pathlib import Path

from scripts.set_local_demo_passwords import _legacy_cms_hash, _write_private_file
from scripts.seed_super_admin import seed_super_admin, sync_pilot_credential
from studiosaas.auth import verify_password


def test_sync_pilot_credential_preserves_other_entries(tmp_path) -> None:
    credential_file = tmp_path / "pilot-credentials.txt"
    credential_file.write_text(
        "# protected\nowner@example.com\towner-secret\nlegacy-cms\tlegacy-secret\n",
        encoding="utf-8",
    )

    sync_pilot_credential(
        credential_file,
        "admin@studiosaas.local",
        "first-secret",
    )
    sync_pilot_credential(
        credential_file,
        "admin@studiosaas.local",
        "updated-secret",
    )

    content = credential_file.read_text(encoding="utf-8")
    assert "owner@example.com\towner-secret" in content
    assert "legacy-cms\tlegacy-secret" in content
    assert content.count("admin@studiosaas.local\tupdated-secret") == 1
    assert "first-secret" not in content
    assert stat.S_IMODE(credential_file.stat().st_mode) == 0o600


def test_seed_has_no_fixed_privileged_password_default() -> None:
    defaults = seed_super_admin.__defaults__
    assert defaults is not None
    assert defaults[0] == "admin@studiosaas.local"
    assert defaults[1] is None


def test_online_launcher_is_portable_and_never_resets_passwords() -> None:
    project_root = Path(__file__).resolve().parents[2]
    launcher = (project_root / "START_STUDIOSAAS_ONLINE.command").read_text(encoding="utf-8")
    startup_common = (project_root / "scripts/startup_common.sh").read_text(encoding="utf-8")
    assert 'ADMIN_EMAIL="admin@studiosaas.local"' in launcher
    assert 'RUNTIME_DIR="$PROJECT_ROOT/.runtime"' in launcher
    assert 'RUNTIME_ENV="$RUNTIME_DIR/online.env"' in launcher
    assert 'LOG_DIR="$RUNTIME_DIR/logs"' in launcher
    assert 'DATA_DIR="$RUNTIME_DIR/cms-data"' in launcher
    assert 'CF_CREDENTIALS="$CLOUDFLARE_DIR/tunnel-credentials.json"' in launcher
    assert 'CMS_DATA_DIR="$DATA_DIR"' in launcher
    assert "$HOME/.studiosaas" not in launcher
    assert "$HOME/.cloudflared" not in launcher
    assert "--reset-password" not in launcher
    assert "STUDIOSAAS_ADMIN_PASSWORD" not in launcher
    assert "--no-print-password" in launcher
    assert "STUDIOSAAS_SHARED_DEMO_PASSWORD" not in launcher
    assert 'DATABASE_MODE="${STUDIOSAAS_DATABASE_MODE:-standard}"' in launcher
    assert 'PORTABLE_DB_SNAPSHOT="$PORTABLE_DB_DIR/studiosaas-portable.snapshot"' in launcher
    assert "portable_database_handoff.py" in launcher
    assert "Publishing verified portable database snapshot" in launcher
    assert 'python3 -m venv --clear "$project_root/.venv"' in startup_common


def test_demo_reset_uses_configured_stable_password() -> None:
    project_root = Path(__file__).resolve().parents[2]
    reset_script = (
        project_root / "backend/scripts/reset_professional_demo.py"
    ).read_text(encoding="utf-8")
    reset_launcher = (project_root / "RESET_DEMO_TENANT.command").read_text(encoding="utf-8")
    assert 'DEMO_PASSWORD_ENV = "STUDIOSAAS_SHARED_DEMO_PASSWORD"' in reset_script
    assert "secrets.token_urlsafe" not in reset_script
    assert 'RUNTIME_ENV="$SCRIPT_DIR/.runtime/online.env"' in reset_launcher
    assert '.runtime/credentials/showcase-credentials.txt' in reset_launcher


def test_shared_demo_password_helpers_use_pbkdf2_and_owner_only_files(tmp_path) -> None:
    password = "test-only-shared-password"
    stored = _legacy_cms_hash(password)
    assert verify_password(password, stored)[0] is True
    assert verify_password("wrong-password", stored)[0] is False

    protected = tmp_path / "credentials" / "pilot-credentials.txt"
    _write_private_file(protected, "protected\n")
    assert protected.read_text(encoding="utf-8") == "protected\n"
    assert stat.S_IMODE(protected.stat().st_mode) == 0o600
