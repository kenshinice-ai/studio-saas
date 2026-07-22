"""Tests for protected launcher credential persistence."""

from __future__ import annotations

import stat
from pathlib import Path

from scripts.seed_super_admin import seed_super_admin, sync_pilot_credential


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


def test_fixed_launcher_credential_is_the_seed_default() -> None:
    defaults = seed_super_admin.__defaults__
    assert defaults is not None
    assert defaults[0] == "admin@studiosaas.local"
    assert defaults[1] == "StudioSaaS@LetsPaint2026!"


def test_online_launcher_resets_and_protects_the_fixed_login() -> None:
    project_root = Path(__file__).resolve().parents[2]
    launcher = (project_root / "START_STUDIOSAAS_ONLINE.command").read_text(encoding="utf-8")
    assert 'ADMIN_EMAIL="admin@studiosaas.local"' in launcher
    assert 'STUDIOSAAS_ADMIN_PASSWORD:-StudioSaaS@LetsPaint2026!' in launcher
    assert "--reset-password" in launcher
    assert "--credential-file" in launcher
    assert "--no-print-password" in launcher
