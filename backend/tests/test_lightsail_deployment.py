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

    # The issued certificate covers the apex and www, so both server blocks
    # must answer for both names or www lands on the default vhost.
    assert "server_name pwestudio.online www.pwestudio.online;" in bootstrap
    assert "server_name pwestudio.online www.pwestudio.online;" in tls
    assert "/etc/letsencrypt/live/pwestudio.online/" in tls
    # ACME HTTP-01 has to be answered by nginx from the webroot. Proxying it to
    # the application would make renewal depend on application health, i.e. the
    # certificate would expire during exactly the outage you need it least.
    assert ".well-known/acme-challenge/" in bootstrap
    assert ".well-known/acme-challenge/" in tls
    assert "Strict-Transport-Security" in tls
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
    # The dump script lives at backend/scripts/ inside the image (WORKDIR /app).
    # `scripts/backup_postgres.py` silently never existed, so every daily
    # backup failed while the cron log was the only witness.
    assert "backend/scripts/backup_postgres.py" in control
    assert "python scripts/backup_postgres.py" not in control
    # The bind-mounted backup directory must be writable by the image user and
    # readable by the operator, asserted on every run rather than at install.
    assert "ensure_backup_dir_writable" in control
    # A backup nobody has restored is a hope. The rehearsal is a first-class
    # command so the quarterly drill is one word.
    assert "restore-dry-run" in control


def test_image_pins_postgres_client_to_the_server_major_version() -> None:
    """pg_restore must match the server, or every rehearsal fails.

    An unpinned postgresql-client resolves to 17 on this base image while the
    server is postgres:16-alpine. A 17 pg_restore emits `SET
    transaction_timeout = 0` — a PG17-only GUC — and PG16 rejects it, so the
    dump looked healthy and the restore never worked.
    """

    dockerfile = _read("deploy/aws/Dockerfile")
    compose = _read("deploy/aws/docker-compose.yml")

    assert "ARG PG_MAJOR=16" in dockerfile
    assert 'postgresql-client-${PG_MAJOR}' in dockerfile
    # The bare package name would silently float to the next major.
    assert "install -y --no-install-recommends curl postgresql-client " not in dockerfile
    assert "postgres:16-alpine" in compose


def test_private_keys_are_excluded_from_git() -> None:
    """Lightsail PEM credentials must never enter a release commit."""

    assert "*.pem" in _read(".gitignore").splitlines()


def test_bundle_builder_disables_macos_appledouble_metadata() -> None:
    """Linux release archives must not contain macOS `._*` pseudo-files."""

    builder = _read("deploy/aws/build_aws_bundle.sh")
    verifier = _read("deploy/aws/verify_release_bundles.sh")

    assert "export COPYFILE_DISABLE=1" in builder
    assert '"/._"' in verifier
