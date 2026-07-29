#!/usr/bin/env bash
# PWE Studio Edition installer — Ubuntu + Docker Compose path (DEPLOYMENT.md §1).
#
# One command from the unpacked delivery bundle root:
#
#   sudo bash standalone-edition/install.sh \
#       --domain studio.example.com \
#       --studio-name "Let's Paint Studio" \
#       --owner-email owner@example.com \
#       [--import-bundle <slug>-edition-bundle-<date>.tar.gz | --import-json students.json] \
#       [--expected-bundle-sha256 <trusted-sha256>] \
#       [--industry art|dance|game|general|language|math|music|sports] \
#       [--slug custom-slug] [--owner-name "Full Name"] [--force-reinstall] [--yes]
#
# Steps: docker check → secrets/.env (600) → compose up (auto-migrates, first
# boot with STUDIOSAAS_SKIP_STANDALONE_CHECKS=1) → create tenant+owner OR
# import bundle/JSON → drop the skip flag + restart → print certbot bootstrap
# commands and the DEPLOYMENT.md §4 acceptance checklist.
#
# Refuses to run twice against a non-empty install unless --force-reinstall.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.edition.yml"
ENV_FILE=""
BOOTSTRAP_NGINX_SRC="$REPO_ROOT/deploy/aws/nginx/studiosaas-bootstrap.conf"
HEALTH_URL="http://127.0.0.1:8899/v1/health?deep=1"
VALID_INDUSTRIES="art dance game general language math music sports"

DOMAIN=""
STUDIO_NAME=""
OWNER_EMAIL=""
OWNER_NAME=""
SLUG=""
INDUSTRY="general"
IMPORT_BUNDLE=""
EXPECTED_BUNDLE_SHA256=""
IMPORT_JSON=""
FORCE_REINSTALL=0
ASSUME_YES=0

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
warn() { printf '\033[1;33mWARN: %s\033[0m\n' "$*" >&2; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 1; }

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

sha256_file() {
  # Print the SHA-256 digest of one file with an explicit tool failure.
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "sha256sum or shasum is required to verify an import bundle"
  fi
}

confirm() {
  # confirm "question" — honours --yes for unattended runs.
  local prompt="$1" reply
  if [ "$ASSUME_YES" = "1" ]; then return 0; fi
  read -r -p "$prompt [y/N] " reply
  [ "$reply" = "y" ] || [ "$reply" = "Y" ]
}

while [ $# -gt 0 ]; do
  case "$1" in
    --domain)          DOMAIN="${2:-}"; shift 2 ;;
    --studio-name)     STUDIO_NAME="${2:-}"; shift 2 ;;
    --owner-email)     OWNER_EMAIL="${2:-}"; shift 2 ;;
    --owner-name)      OWNER_NAME="${2:-}"; shift 2 ;;
    --slug)            SLUG="${2:-}"; shift 2 ;;
    --industry)        INDUSTRY="${2:-}"; shift 2 ;;
    --import-bundle)   IMPORT_BUNDLE="${2:-}"; shift 2 ;;
    --expected-bundle-sha256) EXPECTED_BUNDLE_SHA256="${2:-}"; shift 2 ;;
    --import-json)     IMPORT_JSON="${2:-}"; shift 2 ;;
    --force-reinstall) FORCE_REINSTALL=1; shift ;;
    --yes)             ASSUME_YES=1; shift ;;
    -h|--help)         usage 0 ;;
    *)                 die "Unknown argument: $1 (see --help)" ;;
  esac
done

# ── 0. Validate arguments ────────────────────────────────────────────────────
[ -n "$DOMAIN" ]      || die "--domain is required (e.g. studio.example.com)"
[ -n "$STUDIO_NAME" ] || die "--studio-name is required"
[ -n "$OWNER_EMAIL" ] || die "--owner-email is required"
printf '%s' "$OWNER_EMAIL" | grep -Eq '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$' \
  || die "--owner-email is not a valid email address"
printf '%s' "$DOMAIN" | grep -Eq '^[a-zA-Z0-9.-]+$' || die "--domain looks invalid"
if [ -n "$IMPORT_BUNDLE" ] && [ -n "$IMPORT_JSON" ]; then
  die "--import-bundle and --import-json are mutually exclusive"
fi
[ -z "$EXPECTED_BUNDLE_SHA256" ] || [ -n "$IMPORT_BUNDLE" ] \
  || die "--expected-bundle-sha256 requires --import-bundle"
[ -z "$IMPORT_BUNDLE" ] || [ -n "$EXPECTED_BUNDLE_SHA256" ] \
  || die "--import-bundle requires --expected-bundle-sha256 from the platform export record"
if [ -n "$EXPECTED_BUNDLE_SHA256" ]; then
  printf '%s' "$EXPECTED_BUNDLE_SHA256" | grep -Eq '^[0-9a-fA-F]{64}$' \
    || die "--expected-bundle-sha256 must be exactly 64 hexadecimal characters"
  EXPECTED_BUNDLE_SHA256="$(printf '%s' "$EXPECTED_BUNDLE_SHA256" | tr '[:upper:]' '[:lower:]')"
fi
[ -z "$IMPORT_BUNDLE" ] || [ -f "$IMPORT_BUNDLE" ] || die "bundle not found: $IMPORT_BUNDLE"
[ -z "$IMPORT_JSON" ]   || [ -f "$IMPORT_JSON" ]   || die "JSON file not found: $IMPORT_JSON"
case " $VALID_INDUSTRIES " in
  *" $INDUSTRY "*) ;;
  *) die "--industry must be one of: $VALID_INDUSTRIES" ;;
esac
[ -f "$COMPOSE_FILE" ] || die "compose file missing: $COMPOSE_FILE (run from the unpacked bundle)"
command -v openssl >/dev/null || die "openssl is required (apt-get install -y openssl)"

if [ -z "$SLUG" ]; then
  SLUG="$(printf '%s' "$STUDIO_NAME" | tr '[:upper:]' '[:lower:]' \
          | sed -e 's/[^a-z0-9]\{1,\}/-/g' -e 's/^-\{1,\}//' -e 's/-\{1,\}$//' | cut -c1-63)"
fi
printf '%s' "$SLUG" | grep -Eq '^[a-z0-9][a-z0-9-]{1,62}$' \
  || die "derived slug '$SLUG' is invalid — pass an explicit --slug (lowercase letters/digits/hyphens)"
PROJECT_NAME="studio-$SLUG"
CONFIG_DIR="${PWE_STUDIO_CONFIG_DIR:-/etc/pwe-studio}"
STATE_ROOT="${PWE_STUDIO_STATE_ROOT:-/var/lib/pwe-studio}"
INSTALL_ROOT="${PWE_STUDIO_INSTALL_ROOT:-/opt/pwe-studio}"
ENV_FILE="$CONFIG_DIR/$SLUG.env"
STATE_DIR="$STATE_ROOT/$SLUG"
BACKUP_DIR="$STATE_DIR/backups"
CURRENT_LINK="$INSTALL_ROOT/$SLUG/current"
WRAPPER="/usr/local/bin/pwe-studio-$SLUG"
OPERATOR_USER="${SUDO_USER:-$(id -un)}"

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  command -v sudo >/dev/null || die "run as root or install sudo"
  SUDO="sudo"
fi

# ── 1. Docker + compose plugin ───────────────────────────────────────────────
say "Checking Docker"
if ! command -v docker >/dev/null; then
  confirm "Docker is not installed. Install docker.io + compose plugin via apt now?" \
    || die "Docker is required. Install it and re-run."
  $SUDO apt-get update
  $SUDO apt-get install -y docker.io docker-compose-v2 || \
    $SUDO apt-get install -y docker.io docker-compose-plugin
  $SUDO systemctl enable --now docker
fi
docker compose version >/dev/null 2>&1 || {
  confirm "Docker Compose v2 plugin is missing. Install via apt now?" \
    || die "docker compose v2 is required."
  $SUDO apt-get update
  $SUDO apt-get install -y docker-compose-v2 || $SUDO apt-get install -y docker-compose-plugin
}
docker compose version >/dev/null 2>&1 || die "docker compose still unavailable after install"

dc() { docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }

# The installation itself runs as root, but the named delivery operator needs
# repeatable access to Docker and the root-owned Edition environment file for
# the documented `pwe-studio-<slug>` wrapper. Docker-group membership is already
# root-equivalent; granting the env file to that same group does not widen the
# host trust boundary.
if [ "$OPERATOR_USER" != "root" ]; then
  id "$OPERATOR_USER" >/dev/null 2>&1 || die "operator user does not exist: $OPERATOR_USER"
  getent group docker >/dev/null 2>&1 || groupadd docker
  usermod -aG docker "$OPERATOR_USER"
fi

# ── 2. Refuse accidental reinstall ───────────────────────────────────────────
EXISTING_VOLUME="$(docker volume ls -q --filter "name=${PROJECT_NAME}_studiosaas-pgdata" || true)"
if [ -f "$ENV_FILE" ] || [ -n "$EXISTING_VOLUME" ]; then
  if [ "$FORCE_REINSTALL" != "1" ]; then
    die "Existing install detected (.env or volume ${PROJECT_NAME}_studiosaas-pgdata).
       Re-running would destroy customer data. Pass --force-reinstall ONLY for a
       deliberate wipe, or run upgrades with standalone-edition/upgrade.sh."
  fi
  say "FORCE REINSTALL requested — this DESTROYS all data for $PROJECT_NAME"
  if [ "$ASSUME_YES" != "1" ]; then
    read -r -p "Type exactly 'REINSTALL $SLUG' to continue: " phrase
    [ "$phrase" = "REINSTALL $SLUG" ] || die "confirmation phrase mismatch — aborted"
  fi
  if [ -f "$ENV_FILE" ]; then dc down -v --remove-orphans || true; fi
  docker volume ls -q --filter "name=${PROJECT_NAME}_" | xargs -r docker volume rm || true
  rm -f "$ENV_FILE"
fi

# ── 3. Stable release/config/state layout + secrets ─────────────────────────
mkdir -p "$CONFIG_DIR" "$STATE_DIR/logs" "$BACKUP_DIR/postgres" "$(dirname "$CURRENT_LINK")"
ln -sfn "$REPO_ROOT" "$CURRENT_LINK"

say "Generating secrets and writing $ENV_FILE"
SESSION_SECRET="$(openssl rand -hex 32)"
API_KEY="$(openssl rand -hex 32)"
DB_PASSWORD="$(openssl rand -hex 24)"
APP_DB_PASSWORD="$(openssl rand -hex 24)"
OWNER_PASSWORD="$(openssl rand -base64 15 | tr '+/' 'Aa')"
APP_VERSION="$(cat "$REPO_ROOT/VERSION" 2>/dev/null || echo latest)"

umask 077
cat > "$ENV_FILE" <<EOF
# PWE Studio Edition — generated by install.sh $(date -u +%Y-%m-%dT%H:%M:%SZ).
COMPOSE_PROJECT_NAME=$PROJECT_NAME
STUDIOSAAS_VERSION=$APP_VERSION
STUDIOSAAS_ENV=production
STUDIOSAAS_MODE=standalone
STUDIOSAAS_SHOW_PRODUCER_CREDIT=1
# First boot only — flipped to 0 after the tenant exists.
STUDIOSAAS_SKIP_STANDALONE_CHECKS=1
# Database owner: migrations/role grants only. The server process uses the
# separate runtime role below.
EDITION_DB_PASSWORD=$DB_PASSWORD
EDITION_APP_DB_PASSWORD=$APP_DB_PASSWORD
STUDIOSAAS_MIGRATION_DATABASE_URL=postgresql://studiosaas:$DB_PASSWORD@db:5432/studiosaas
STUDIOSAAS_DATABASE_URL=postgresql://studiosaas_app:$APP_DB_PASSWORD@db:5432/studiosaas
STUDIOSAAS_DB_RUNTIME_ROLE=studiosaas_app
EDITION_BACKUP_DIR=$BACKUP_DIR
STUDIOSAAS_SESSION_SECRET=$SESSION_SECRET
STUDIOSAAS_API_KEY=$API_KEY
STUDIOSAAS_PUBLIC_BASE_DOMAIN=$DOMAIN
STUDIOSAAS_SEED_SUPER_ADMIN=0
STUDIOSAAS_EMAIL_BACKEND=console
EOF
if getent group docker >/dev/null 2>&1; then
  chown root:docker "$ENV_FILE"
  chmod 640 "$ENV_FILE"
else
  chown root:root "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi

cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec docker compose -p "$PROJECT_NAME" --env-file "$ENV_FILE" \\
  -f "$CURRENT_LINK/standalone-edition/docker-compose.edition.yml" "\$@"
EOF
chown root:root "$WRAPPER"
chmod 755 "$WRAPPER"

# ── 4. First boot (entrypoint waits for db + applies migrations) ─────────────
# The backup directory is a host bind mount so `dc up -d --build` (the update
# step) cannot destroy the dump history. It must exist and be writable by the
# image user (uid 10001) before the container starts, or PostgreSQL dumps fail
# silently at 02:30 and nobody finds out until a restore is needed.
say "Preparing stable host backup directory ($BACKUP_DIR)"
if getent group docker >/dev/null 2>&1; then
  chown -R 10001:docker "$BACKUP_DIR"
  chmod 750 "$BACKUP_DIR"
else
  chown -R 10001:10001 "$BACKUP_DIR"
  chmod 700 "$BACKUP_DIR"
fi

say "Building and starting containers (first boot, standalone checks skipped)"
dc up -d --build

say "Waiting for $HEALTH_URL"
HEALTH_OK=0
for i in $(seq 1 60); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then HEALTH_OK=1; break; fi
  sleep 3
done
if [ "$HEALTH_OK" != "1" ]; then
  dc logs --tail 50 app || true
  die "app did not become healthy within 180s — see logs above"
fi

# ── 5. Data path: fresh create / --import-json / --import-bundle ─────────────
if [ -n "$IMPORT_BUNDLE" ]; then
  ACTUAL_BUNDLE_SHA256="$(sha256_file "$IMPORT_BUNDLE")"
  [ "$ACTUAL_BUNDLE_SHA256" = "$EXPECTED_BUNDLE_SHA256" ] || die \
    "bundle SHA-256 mismatch: expected $EXPECTED_BUNDLE_SHA256, got $ACTUAL_BUNDLE_SHA256"
  printf '%s  %s\n' "$EXPECTED_BUNDLE_SHA256" "$(basename "$IMPORT_BUNDLE")" \
    > "$STATE_DIR/import-bundle.sha256"
  chmod 600 "$STATE_DIR/import-bundle.sha256"
  say "Importing platform export bundle: $IMPORT_BUNDLE"
  dc cp "$IMPORT_BUNDLE" app:/tmp/edition-bundle.tar.gz
  dc exec -T app python standalone-edition/tools/import_tenant_bundle.py \
      /tmp/edition-bundle.tar.gz --confirm-fresh-db --media-dir /media \
      --expected-sha256 "$EXPECTED_BUNDLE_SHA256"
  dc exec -T app rm -f /tmp/edition-bundle.tar.gz
  say "Bundle import complete — owner passwords were reset; issue new ones at handover:"
  echo "  dc exec app python scripts/rotate_pilot_credentials.py --help"
else
  say "Creating tenant '$STUDIO_NAME' ($SLUG) + owner $OWNER_EMAIL"
  # Mirrors the Super Admin create_tenant route (api_v1) via its own helpers,
  # patterned on seed_local_test_tenants.py — no HTTP, straight to the DB.
  dc exec -T \
      -e EDITION_STUDIO_NAME="$STUDIO_NAME" \
      -e EDITION_SLUG="$SLUG" \
      -e EDITION_INDUSTRY="$INDUSTRY" \
      -e EDITION_OWNER_EMAIL="$OWNER_EMAIL" \
      -e EDITION_OWNER_NAME="${OWNER_NAME:-$STUDIO_NAME Owner}" \
      -e EDITION_OWNER_PASSWORD="$OWNER_PASSWORD" \
      app python - <<'PY'
import json, os, sys
sys.path.insert(0, "/app/backend")
from studiosaas.db import connect, fetch_one
from studiosaas.api_v1 import _tenant_write_payload, _ensure_studio_admin_account

payload = {
    "name": os.environ["EDITION_STUDIO_NAME"],
    "slug": os.environ["EDITION_SLUG"],
    "status": "active",
    "planCode": "edition",
    "category": os.environ.get("EDITION_INDUSTRY", "general"),
    "subscriptionStatus": "active",
    "contactEmail": os.environ["EDITION_OWNER_EMAIL"],
    "ownerEmail": os.environ["EDITION_OWNER_EMAIL"],
    "ownerName": os.environ["EDITION_OWNER_NAME"],
    "studioAdminPassword": os.environ["EDITION_OWNER_PASSWORD"],
}
data = _tenant_write_payload(payload, require_slug=True)
settings = json.loads(data["settings_json"])
settings["workspace_path"] = f"tenants/{data['slug']}"
settings["demo_seed_locked"] = True  # Edition: whole DB is real data (DATABASE.md §4)

with connect() as conn:
    row = fetch_one(conn, "SELECT count(*) AS n FROM tenants", ())
    if int(row["n"]) != 0:
        raise SystemExit("REFUSED: database already has a tenant — Edition allows exactly one.")
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO plans (code, name, monthly_price_aud, student_limit,
                               user_limit, storage_limit_mb, features)
            VALUES ('edition', 'PWE Studio Edition (Unlimited)', 0, 1000000,
                    1000000, 1048576, '{}'::jsonb)
            ON CONFLICT (code) DO NOTHING
            """
        )
        cur.execute(
            """
            INSERT INTO tenants (name, slug, status, plan_code, welcome_message,
                                 contact_phone, contact_email, address, settings)
            VALUES (%s, %s, 'active', 'edition', %s, %s, %s, %s, %s::jsonb)
            RETURNING id
            """,
            (
                data["name"], data["slug"], f"Welcome to {data['name']}.",
                data["contact_phone"], data["contact_email"], data["address"],
                json.dumps(settings),
            ),
        )
        tenant_id = str(cur.fetchone()["id"])
        _ensure_studio_admin_account(conn, tenant_id, data["studio_admin"])
        cur.execute(
            "INSERT INTO subscriptions (tenant_id, plan_code, status) VALUES (%s, 'edition', 'active')",
            (tenant_id,),
        )
        cur.execute(
            "INSERT INTO tenant_usage (tenant_id, student_count, user_count, storage_used_mb) VALUES (%s, 0, 0, 0)",
            (tenant_id,),
        )
        cur.execute(
            """
            INSERT INTO courses (tenant_id, name, description, category, credit_unit)
            VALUES (%s, 'General Class', 'Default course created with tenant.', 'General', 'credits')
            """,
            (tenant_id,),
        )
        cur.execute(
            """
            INSERT INTO audit_logs (tenant_id, actor_user_id, action, resource_type, resource_id, metadata)
            VALUES (%s, NULL, 'tenant.created', 'tenant', %s, '{"installer": "edition"}'::jsonb)
            """,
            (tenant_id, tenant_id),
        )
    conn.commit()
print(f"tenant created: {data['slug']} id={tenant_id}")
PY

  if [ -n "$IMPORT_JSON" ]; then
    say "Importing students JSON into $SLUG"
    dc cp "$IMPORT_JSON" app:/tmp/students-import.json
    # Preview first so the reconciliation shows in the install log.
    dc exec -T app python scripts/import_lets_paint_json.py /tmp/students-import.json \
        --tenant-slug "$SLUG"
    dc exec -T app python scripts/import_lets_paint_json.py /tmp/students-import.json \
        --tenant-slug "$SLUG" --apply --reset-all-students --confirm-tenant "$SLUG"
    dc exec -T app rm -f /tmp/students-import.json
  fi
fi

say "Regenerating tenant portal workspace"
dc exec -T app python scripts/regenerate_tenant_workspaces.py

# ── 6. Drop the first-boot skip flag and restart in full standalone mode ─────
say "Enabling standalone startup checks (STUDIOSAAS_SKIP_STANDALONE_CHECKS=0)"
sed -i.bak 's/^STUDIOSAAS_SKIP_STANDALONE_CHECKS=1$/STUDIOSAAS_SKIP_STANDALONE_CHECKS=0/' "$ENV_FILE"
rm -f "$ENV_FILE.bak"
dc up -d app

say "Re-checking health after restart"
HEALTH_OK=0
for i in $(seq 1 40); do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then HEALTH_OK=1; break; fi
  sleep 3
done
[ "$HEALTH_OK" = "1" ] || { dc logs --tail 50 app || true; \
  die "app failed standalone startup checks — fix data, then: dc up -d app"; }

# ── 7. Root-owned database backup schedule ──────────────────────────────────
# Use /etc/cron.d rather than the invoking user's crontab. This avoids the
# previous silent failure where the documented non-root cron could read neither
# Docker's socket nor the root-owned Edition environment file.
CRON_FILE="/etc/cron.d/pwe-studio-$SLUG-backup"
say "Installing root-owned daily PostgreSQL backup schedule ($CRON_FILE)"
cat > "$CRON_FILE" <<EOF
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * root $WRAPPER exec -T app python scripts/backup_postgres.py backup --keep 14 >> $STATE_DIR/logs/postgres-backup.log 2>&1
EOF
chown root:root "$CRON_FILE"
chmod 644 "$CRON_FILE"

say "Creating and verifying the first PostgreSQL backup"
dc exec -T app python scripts/backup_postgres.py backup --keep 14
find "$BACKUP_DIR/postgres" -maxdepth 1 -type f -name '*.dump' -print -quit | grep -q . \
  || die "first PostgreSQL backup did not appear in $BACKUP_DIR/postgres"

# ── 8. TLS: print the exact two-step certbot bootstrap (do NOT run blind) ────
say "TLS setup — run these two steps yourself (DEPLOYMENT.md §1, reuses deploy/aws/nginx)"
cat <<EOF
  # Step 1 — HTTP-only bootstrap vhost (avoids the certbot chicken-and-egg):
  sudo apt-get install -y nginx certbot python3-certbot-nginx
  sudo sed 's/server_name .*;/server_name $DOMAIN;/' \\
      "$BOOTSTRAP_NGINX_SRC" \\
      | sudo tee /etc/nginx/sites-available/$SLUG.conf >/dev/null
  sudo ln -sf /etc/nginx/sites-available/$SLUG.conf /etc/nginx/sites-enabled/$SLUG.conf
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t && sudo systemctl reload nginx

  # Step 2 — mint the certificate (certbot rewrites the server block + renews via timer):
  sudo certbot --nginx -d $DOMAIN
  systemctl list-timers | grep certbot   # renewal timer must be active
EOF

# ── 9. Acceptance checklist (DEPLOYMENT.md §4) with the real domain ──────────
say "Delivery-day acceptance checklist — walk every line (DEPLOYMENT.md §4)"
cat <<EOF
  [ ] https://$DOMAIN/ 直达门户（根路径不再是 super-admin）
  [ ] https://$DOMAIN/super-admin 与 /v1/admin/* 全部 404/关闭
  [ ] owner 登录 CMS/Studio Admin；角色账号按名单建好
  [ ] 数据迁移计数与账本总额与源对账单一致（manifest 校验）
  [ ] 手机 4G 提交测试报名 → CMS 待审出现 → 拒绝闭环
  [ ] 备份 cron 已跑出第一份 dump（0600）+ 恢复 dry-run 通过
      （dc exec app python scripts/backup_postgres.py backup）
  [ ] TLS 证书自动续期 timer 生效；https://$DOMAIN/v1/health?deep=1 返回 db ok
  [ ] 交接：owner 密码由客户当场改掉；服务器凭据移交记录签字
EOF

say "Install complete"
echo   "  Project:      $PROJECT_NAME  (compose file: $COMPOSE_FILE)"
echo   "  Env file:     $ENV_FILE (root:docker 0640 where available; back it up securely)"
echo   "  Operations:   $WRAPPER <ps|logs|restart|exec ...>"
echo   "  Current code: $CURRENT_LINK -> $REPO_ROOT"
echo   "  DB backups:   $BACKUP_DIR/postgres (media backup remains deferred in v7.8.1)"
if [ -z "$IMPORT_BUNDLE" ]; then
  echo "  Owner login:  $OWNER_EMAIL"
  echo "  Temp password: $OWNER_PASSWORD"
  echo "  → The owner MUST change this password during handover (checklist last line)."
else
  echo "  Owner logins came from the bundle with unusable passwords —"
  echo "  reset them now and hand over new credentials."
fi
echo   "  Manage stack: $WRAPPER ..."
if [ "$OPERATOR_USER" != "root" ]; then
  echo "  IMPORTANT: $OPERATOR_USER was added to the docker group."
  echo "  Log out and back in once before using $WRAPPER without sudo."
fi
