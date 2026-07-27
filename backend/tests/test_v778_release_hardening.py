"""Regression tests for the v7.7.8 delivery and Edition hardening."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import secrets
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_script(name: str, relative_path: str):
    """Import one repository script without turning script folders into packages."""

    spec = importlib.util.spec_from_file_location(name, PROJECT_ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


import_bundle = _load_script(
    "v778_import_tenant_bundle",
    "standalone-edition/tools/import_tenant_bundle.py",
)
configure_role = _load_script(
    "v778_configure_runtime_db_role",
    "backend/scripts/configure_runtime_db_role.py",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_bundle_inventory_hashes_database_and_media(tmp_path):
    """A valid v2 manifest covers both database JSON and media payloads."""

    db_file = tmp_path / "db" / "tenant.json"
    media_file = tmp_path / "media" / "tenant" / "photo.webp"
    db_file.parent.mkdir(parents=True)
    media_file.parent.mkdir(parents=True)
    db_file.write_text(json.dumps({"id": "tenant"}), encoding="utf-8")
    media_file.write_bytes(b"safe-display-derivative")
    manifest = {
        "files": {
            "db/tenant.json": _sha(db_file),
            "media/tenant/photo.webp": _sha(media_file),
        }
    }

    import_bundle._verify_file_hashes(tmp_path, manifest)


def test_bundle_inventory_rejects_tampered_media(tmp_path):
    media_file = tmp_path / "media" / "photo.webp"
    media_file.parent.mkdir(parents=True)
    media_file.write_bytes(b"original")
    manifest = {"files": {"media/photo.webp": _sha(media_file)}}
    media_file.write_bytes(b"tampered")

    with pytest.raises(import_bundle.ImportError_, match="Checksum mismatch"):
        import_bundle._verify_file_hashes(tmp_path, manifest)


def test_bundle_inventory_rejects_undeclared_payload(tmp_path):
    db_file = tmp_path / "db" / "tenant.json"
    extra = tmp_path / "media" / "undeclared.webp"
    db_file.parent.mkdir(parents=True)
    extra.parent.mkdir(parents=True)
    db_file.write_text("{}", encoding="utf-8")
    extra.write_bytes(b"extra")
    manifest = {"files": {"db/tenant.json": _sha(db_file)}}

    with pytest.raises(import_bundle.ImportError_, match="unexpected"):
        import_bundle._verify_file_hashes(tmp_path, manifest)


def test_import_refuses_untrusted_bundle_sha_before_extract(tmp_path):
    bundle = tmp_path / "bundle.tar.gz"
    bundle.write_bytes(b"not-even-a-tarball")

    with pytest.raises(SystemExit, match="does not match the trusted export record"):
        import_bundle.main(
            [str(bundle), "--expected-sha256", "0" * 64]
        )


def test_runtime_role_rejects_invalid_identifier(monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_DB_RUNTIME_ROLE", "bad-role;drop")
    monkeypatch.setenv("STUDIOSAAS_DB_RUNTIME_PASSWORD", "x" * 48)
    monkeypatch.setenv(
        "STUDIOSAAS_MIGRATION_DATABASE_URL",
        "postgresql://unused/unused",
    )

    assert configure_role.main() == 2


def test_runtime_role_requires_strong_password(monkeypatch):
    monkeypatch.setenv("STUDIOSAAS_DB_RUNTIME_ROLE", "studiosaas_app")
    monkeypatch.setenv("STUDIOSAAS_DB_RUNTIME_PASSWORD", "short")
    monkeypatch.setenv(
        "STUDIOSAAS_MIGRATION_DATABASE_URL",
        "postgresql://unused/unused",
    )

    assert configure_role.main() == 2


def test_runtime_role_has_crud_but_no_platform_admin_power(monkeypatch):
    """The configured app role can use tables without owning the database."""

    database_url = os.environ.get("STUDIOSAAS_DATABASE_URL", "").strip()
    if not database_url:
        pytest.skip("PostgreSQL integration URL is not configured")
    try:
        import psycopg
        from psycopg import sql
    except ImportError:
        pytest.skip("psycopg is not installed")

    role = f"v778_app_{secrets.token_hex(6)}"
    password = secrets.token_hex(24)
    role_created = False
    try:
        with psycopg.connect(database_url, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT rolsuper FROM pg_roles WHERE rolname = current_user")
                row = cur.fetchone()
                if not row or not row[0]:
                    pytest.skip("integration database user is not a role administrator")

        monkeypatch.setenv("STUDIOSAAS_DB_RUNTIME_ROLE", role)
        monkeypatch.setenv("STUDIOSAAS_DB_RUNTIME_PASSWORD", password)
        monkeypatch.setenv("STUDIOSAAS_MIGRATION_DATABASE_URL", database_url)
        assert configure_role.main() == 0
        role_created = True

        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT rolsuper, rolcreatedb, rolcreaterole
                    FROM pg_roles WHERE rolname = %s
                    """,
                    (role,),
                )
                assert cur.fetchone() == (False, False, False)
                cur.execute(
                    "SELECT has_table_privilege(%s, 'tenants', 'SELECT')",
                    (role,),
                )
                assert cur.fetchone()[0] is True
                cur.execute(
                    "SELECT has_schema_privilege(%s, 'public', 'CREATE')",
                    (role,),
                )
                assert cur.fetchone()[0] is False
    finally:
        if role_created:
            try:
                with psycopg.connect(database_url, autocommit=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            sql.SQL("DROP OWNED BY {}").format(sql.Identifier(role))
                        )
                        cur.execute(
                            sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role))
                        )
            except Exception as exc:
                pytest.fail(f"failed to remove temporary runtime role {role}: {exc}")
