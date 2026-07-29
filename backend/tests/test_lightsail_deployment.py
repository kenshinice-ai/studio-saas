"""Static contracts for the pwestudio.online Lightsail release kit."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(relative_path: str) -> str:
    """Return one release file as UTF-8 text."""

    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_lightsail_uses_direct_tls_and_local_only_application_port() -> None:
    """The public domain terminates at nginx; app and DB ports stay private."""

    bootstrap = _read("deploy/aws/nginx/studiosaas-bootstrap.conf")
    tls = _read("deploy/aws/nginx/studiosaas.conf")
    compose = _read("deploy/aws/docker-compose.yml")

    assert "server_name pwestudio.online;" in bootstrap
    assert "server_name pwestudio.online;" in tls
    assert "/etc/letsencrypt/live/pwestudio.online/" in tls
    assert "studiosaas.cc.cd" not in bootstrap + tls
    assert '"127.0.0.1:8899:8899"' in compose
    assert "5432:5432" not in compose


def test_lightsail_single_node_preserves_roles_backups_and_volumes() -> None:
    """Single-node production keeps bounded DB access and stable data paths."""

    override = _read("deploy/aws/docker-compose.lightsail.yml")
    control = _read("deploy/aws/lightsail_ctl.sh")
    env_example = _read("deploy/aws/lightsail.env.example")

    assert "STUDIOSAAS_MIGRATION_DATABASE_URL" in override
    assert "STUDIOSAAS_DB_RUNTIME_ROLE: studiosaas_app" in override
    assert "STUDIOSAAS_BACKUP_DIR" in override
    assert "PROJECT_NAME=" in control
    assert "--profile local-db" in control
    assert "down -v" not in control
    assert "pwestudio-volumes-" in control
    assert "_studiosaas-media:/media:ro" in control
    assert "STUDIOSAAS_PUBLIC_BASE_DOMAIN=pwestudio.online" in env_example


def test_private_keys_are_excluded_from_git() -> None:
    """Lightsail PEM credentials must never enter a release commit."""

    assert "*.pem" in _read(".gitignore").splitlines()
