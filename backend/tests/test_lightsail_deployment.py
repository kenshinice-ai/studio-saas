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


def test_tls_snippet_is_shared_and_has_no_dead_ocsp_config() -> None:
    """One TLS parameter set, included by both server blocks.

    A hardened apex next to a default-configured www block is a downgrade path
    hiding in plain sight, so the parameters live in one snippet.

    Stapling stays OFF: Let's Encrypt certificates carry no OCSP responder URL
    (their AIA holds only CA Issuers), so `ssl_stapling on` is accepted by nginx
    and then logged as ignored on every single reload — which trains an operator
    to stop reading reload output, where real errors appear.
    """

    snippet = _read("deploy/aws/nginx/pwestudio-tls.conf")
    tls = _read("deploy/aws/nginx/studiosaas.conf")

    assert "ssl_protocols TLSv1.2 TLSv1.3;" in snippet
    assert "ssl_session_tickets off;" in snippet
    assert "ssl_prefer_server_ciphers off;" in snippet
    # No CBC, no RSA key exchange, no 3DES in the TLS 1.2 list.
    for weak in ("AES128-SHA", "AES256-SHA", "DES-CBC3", "TLS_RSA_WITH"):
        assert weak not in snippet
    snippet_directives = [
        line.strip() for line in snippet.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any(line.startswith("ssl_stapling") for line in snippet_directives)
    # A snippet must not pull in another file; only comments may mention the word.
    assert not any(
        line.strip().startswith("include") for line in snippet.splitlines()
    )

    # Both 443 blocks share it, and neither pins its own protocol list.
    assert tls.count("include             /etc/nginx/snippets/pwestudio-tls.conf;") == 2
    assert "ssl_protocols" not in tls
    # Ubuntu 24.04 ships nginx 1.24: HTTP/2 is a listen parameter there, and the
    # 1.25+ standalone directive fails nginx -t. Comments may name it; only the
    # directives matter, so read past them.
    directives = [
        line.strip() for line in tls.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any(line.startswith("http2 ") for line in directives)
    assert sum(1 for line in directives if line == "listen 443 ssl http2;") == 2


def test_www_redirects_to_the_single_canonical_host() -> None:
    """www is a redirect, not a second origin serving the same pages."""

    tls = _read("deploy/aws/nginx/studiosaas.conf")

    assert "server_name www.pwestudio.online;" in tls
    assert "return 301 https://pwestudio.online$request_uri;" in tls
    # The redirect itself must happen over TLS, never by downgrading to http.
    assert "return 301 http://pwestudio.online" not in tls


def test_edge_owns_hsts_and_leaves_the_rest_to_the_application() -> None:
    """No duplicate security headers on the wire.

    backend/server.py already sends CSP, X-Frame-Options, Permissions-Policy,
    Referrer-Policy and X-Content-Type-Options on every response it generates.
    HSTS stays at the edge because it must also cover responses the application
    never produced — nginx's 502 while the container restarts is exactly when a
    downgrade must not be on offer.
    """

    tls = _read("deploy/aws/nginx/studiosaas.conf")

    assert "Strict-Transport-Security" in tls
    assert "add_header X-Content-Type-Options" not in tls
    assert "add_header Referrer-Policy" not in tls
    assert "add_header Content-Security-Policy" not in tls
    # A restart shows a branded page rather than nginx's stock 502.
    assert "error_page 502 503 504 /__maintenance.html;" in tls
    assert "internal;" in tls


def test_remote_operator_script_carries_no_credentials_and_cannot_destroy() -> None:
    """The laptop-side helper reaches the host and nothing more.

    Every command that touches production data is delegated to
    lightsail_ctl.sh on the instance, so a laptop is never the source of truth
    for a production procedure, and the two halves cannot drift.
    """

    remote = _read("deploy/aws/pwestudio_remote.sh")

    # Reaches the host only through an ssh_config alias — no key path, no
    # password, no database URL in the repository.
    assert "PWESTUDIO_SSH_HOST:-pwestudio" in remote
    for secret in ("BEGIN RSA", "BEGIN OPENSSH", ".pem\"", "LOCAL_DB_PASSWORD",
                   "STUDIOSAAS_SESSION_SECRET", "STUDIOSAAS_API_KEY"):
        assert secret not in remote
    # Destructive verbs stay on the instance, where the prompt has context.
    assert "down -v" not in remote
    assert "restore --confirm" not in remote
    assert "certbot delete" not in remote
    # A deploy backs up first, verifies deep health, and rolls back on failure.
    assert "lightsail_ctl.sh" in remote  # delegates to the on-instance script
    assert "ctl backup" in remote        # deploy takes a backup before switching
    assert "rolling back" in remote.lower()
    # A standalone tarball on the SaaS host would refuse to boot after the
    # symlink already moved, so the mode is checked before upload.
    assert "mode=saas" in remote


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
