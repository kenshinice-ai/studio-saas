# Admin Guide

## PostgreSQL Backup And Restore

The SaaS database is PostgreSQL. Legacy CMS JSON backup/restore does not protect
the v1 multi-tenant tables.

Use the local runbook script from the project root:

```bash
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
  .venv/bin/python backend/scripts/backup_postgres.py backup
```

This creates a custom-format `pg_dump` plus a manifest under
`backups/postgres/`. The manifest records `schema_migrations` and critical
table counts so a restore can be checked against both schema and data totals.

Dry-run restore into a temporary sibling database:

```bash
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
  .venv/bin/python backend/scripts/backup_postgres.py restore-dry-run backups/postgres/<dump>.dump
```

Production restore is intentionally guarded:

```bash
STUDIOSAAS_DATABASE_URL=<target-postgres-url> \
  .venv/bin/python backend/scripts/backup_postgres.py restore <dump>.dump --confirm <database_name>
```

Retention defaults to the newest 14 dumps. Change with `backup --keep N`.

Checklist:

- Confirm `pg_dump`, `pg_restore`, `createdb`, `dropdb`, and `psql` are on `PATH`.
- Run `backup` before every migration batch.
- Run `restore-dry-run` before using a dump for a real restore.
- Confirm `schema_migrations` is non-empty after restore.
- Never run `restore` against a development or production database without the
  explicit `--confirm <database_name>` guard.

> **StudioSaaS Platform Administration**
> Last updated: 2026-07-18

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Tenant Management](#tenant-management)
3. [Super-Admin Dashboard](#super-admin-dashboard)
4. [Monitoring & Health](#monitoring--health)
5. [Backup & Recovery](#backup--recovery)
6. [User Support](#user-support)
7. [Troubleshooting](#troubleshooting)
8. [Security](#security)

---

## Getting Started

### Prerequisites

- Access to the server hosting StudioSaaS
- PostgreSQL 18+ installed and running
- Python 3.11+ virtual environment with dependencies installed
- SSH access to the server

### Initial Setup

1. **Clone the repository:**
   ```bash
   git clone <repo-url> /opt/studiosaas
   cd /opt/studiosaas
   ```

2. **Create virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   export STUDIOSAAS_DATABASE_URL="postgresql://<user>@localhost:5432/studiosaas_local_test"
   export STUDIOSAAS_ENV="local"
   export PORT="8899"
   export STUDIOSAAS_API_KEY="at-least-32-random-characters"
   export STUDIOSAAS_SESSION_SECRET="different-at-least-32-random-characters"
   export STUDIOSAAS_MEDIA_DIR="/persistent/studiosaas/media"
   export CMS_DATA_DIR="/persistent/studiosaas/legacy-data"
   ```

4. **Initialize database:**
   ```bash
   createdb studiosaas_local_test
   cd backend
   ../.venv/bin/python scripts/run_migrations.py
   ../.venv/bin/python scripts/seed_super_admin.py
   ```

5. **Start the server:**
   ```bash
   ./start_studiosaas_local.sh
   # or: cd backend && python server.py
   ```

6. **Verify health:**
   ```bash
   curl http://localhost:8899/v1/health
   ```

---

## Tenant Management

### Creating a New Tenant

Via **Super-Admin Dashboard** (`/super-admin`):

1. Click **"Add Tenant"**
2. Fill in:
   - **Name:** Display name (e.g., "Academy of Art")
   - **Slug:** URL identifier (e.g., "academy-of-art") — reserved slugs are rejected
   - **Plan:** `starter`, `studio`, or `growth`
   - **Brand Colours:** Primary and secondary colours (hex codes)
3. Click **"Create"**

Via **API** (requires a super admin session cookie):

```bash
curl -X POST http://localhost:8899/v1/admin/tenants \
  -b /tmp/studiosaas.cookies \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Academy of Art",
    "slug": "academy-of-art",
    "plan_code": "starter",
    "primary_color": "#1E40AF",
    "secondary_color": "#F59E0B"
  }'
```

### Editing a Tenant

1. Navigate to Super-Admin Dashboard
2. Find the tenant in the list
3. Click **"Edit"**
4. Update fields as needed
5. Click **"Save"**

### Pausing / Resuming a Tenant

1. Find the tenant in Super-Admin Dashboard
2. Click **"Pause"** (or **"Resume"**)
3. Confirm the action

> **Note:** Paused tenants are hidden from public surfaces but data is preserved. Tenant lifecycle statuses: `trial`, `active`, `past_due`, `paused`, `cancelled` (see `docs/Database.md` §3).

### Deleting a Tenant

Direct tenant deletion is disabled. Archive first; a platform Super Admin may
then use the separately guarded permanent-delete workflow with the exact
confirmation phrase. The workflow creates database/media snapshots and audit
evidence before deletion. Studio owners cannot perform it.

---

## Super-Admin Dashboard

### URL Pattern

`/super-admin` (also served at `/`)

### Features

| Feature | Description |
|---|---|
| Tenant List | All tenants with plan, status, usage |
| Add Tenant | Create new tenant with branding and optional studio admin account |
| Edit Tenant | Modify tenant details, plan, subscription |
| Pause / Resume | Toggle tenant availability without data loss |
| Usage | Storage, student count, user count per tenant |
| Audit Logs | Platform activity trail |
| Search | Filter tenants by name or slug |

### 界面语言 / Interface Language

Super Admin 和每个租户的 Studio Admin 顶部均提供 **中文 / English**
切换。系统默认显示中文，并在当前浏览器保存上次选择；导航、表单、按钮、
状态、提示和确认信息会一起切换。该设置只影响界面文案，不会修改套餐代码、
工作室网址标识或数据库中的状态值。

### Permissions

- Only users with a `super_admin` membership can access
- Studio admins see only their own tenant surfaces

---

## Monitoring & Health

### Health Endpoint

```bash
curl http://localhost:8899/v1/health
```

**Expected Response:**

```json
{
  "ok": true,
  "service": "PWE Studio SaaS API",
  "version": "v1"
}
```

This endpoint confirms the web process, not database readiness. The mandatory
release check is `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`.

### Log Files

- **Location:** `backend/server.log` (or configured log path)
- **Format:** JSON structured logs
- **Rotation:** Configured via log manager (e.g., logrotate)

### Key Log Levels

| Level | When to Check |
|---|---|
| ERROR | Immediate investigation required |
| WARN | Review within 24 hours |
| INFO | Normal operation |
| DEBUG | Development/debugging only |

### Metrics to Monitor

- **Response time:** P50 < 200ms, P95 < 1s
- **Error rate:** < 1% of requests
- **Database connections:** Active pool < 80% max
- **Disk usage:** CMS data directory < 80% capacity
- **Memory usage:** Server process < 2GB

---

## Backup & Recovery

### Database Backup

**Canonical path (P0-3):** use `backend/scripts/backup_postgres.py` — it writes a
`pg_dump` custom-format dump plus a manifest recording `schema_migrations` and
critical table counts to
`backups/postgres/` (git-ignored), keeping the newest 14.

```bash
# One-click during the pilot (recommended before every public test session):
双击 BACKUP_STUDIOSAAS_NOW.command

# Same thing from a shell:
cd backend && STUDIOSAAS_DATABASE_URL=... ../.venv/bin/python scripts/backup_postgres.py backup --keep 14
```

**Restore drill** (run before relying on a backup):

```bash
cd backend && STUDIOSAAS_DATABASE_URL=... ../.venv/bin/python scripts/backup_postgres.py restore-dry-run ../backups/postgres/<dump>.dump
```

**Scheduled backup (optional):** the pilot deliberately runs on-demand, no
daemons. If the stack ever becomes long-running, ready-made LaunchAgent
templates live in `deploy/launchd/` (`bash deploy/install_launch_agents.sh`
installs daily-03:00 backup + persistent tunnel).

### Media And Legacy Data Backup

PostgreSQL stores media metadata, not file bytes. Back up the persistent
`STUDIOSAAS_MEDIA_DIR` and `CMS_DATA_DIR` alongside the database dump using the
host platform's snapshot or file-backup mechanism. Preserve directory
ownership and permissions. Do not expose either directory through a public
static-file server.

### Recovery Procedure

Use [Release_Runbook.md](Release_Runbook.md). It requires a successful
temporary restore drill before the confirmation-guarded real restore, avoids
provider-specific service commands, and requires reconciliation of writes
created after the backup timestamp.

### Backup Retention

| Type | Frequency | Retention |
|---|---|---|
| Database dump + manifest | Before every migration and at least daily when long-running | Newest 14 by default |
| Media and legacy data | At least daily when long-running | Match database retention window |
| Restore drill | Monthly and before emergency use | Record result with release evidence |

---

## User Support

### Common Issues

| Issue | Cause | Solution |
|---|---|---|
| "Tenant context is required" | Missing tenant slug in URL | Verify URL pattern: `/<slug>/cms` |
| 404 on CMS page | Tenant not activated | Activate tenant in super-admin |
| Images not uploading | `STUDIOSAAS_MEDIA_DIR` not writable or quota reached | Check explicit upload error, directory permissions, and tenant usage |
| Slow page loads | Large image files | Optimize images, use CDN |
| Brand colours wrong | Tenant `primary_color` not set | Update tenant via super-admin |

### Support Workflow

1. **Receive ticket** (email, dashboard, chat)
2. **Reproduce issue** on staging or local environment
3. **Check logs** for error patterns
4. **Apply fix** (configuration change, code update, data fix)
5. **Verify** with user
6. **Document** solution in knowledge base

### Escalation Path

| Level | Responsibility | Response Time |
|---|---|---|
| L1 | Help desk | 1 hour |
| L2 | Backend engineer | 4 hours |
| L3 | Architect / Vendor | 24 hours |

---

## Troubleshooting

### Server Won't Start

1. Check logs: `tail -100 backend/server.log`
2. Verify PostgreSQL is running: `psql "postgresql:///studiosaas" -c "SELECT 1"`
3. Check `.env` file exists and is valid
4. Ensure port 8899 is not in use: `lsof -iTCP:8899 -sTCP:LISTEN`

### Database Connection Errors

1. Verify PostgreSQL service: `brew services list | grep postgres`
2. Check credentials in `.env`: `DATABASE_URL`
3. Test connection: `psql "postgresql://<user>@localhost:5432/studiosaas"`
4. Ensure database exists: `\l` in psql

### Tenant Routing Issues

1. Verify URL patterns against `docs/Architecture.md` §2
2. Check tenant exists in database: `SELECT * FROM tenants WHERE slug = '<slug>'`
3. Confirm tenant status is `active`
4. Clear any URL cache (if using CDN)

### Performance Issues

1. Check database query times: Enable slow query log
2. Monitor server resources: `top`, `htop`, `vmstat`
3. Review CMS data directory size: `du -sh /var/lib/studiosaas/cms/`
4. Check for N+1 queries in logs

---

## Security

### Best Practices

- **Rotate API keys** every 90 days
- **Enable HTTPS** via reverse proxy (nginx, Caddy)
- **Restrict super-admin access** to known IP ranges
- **Regular security audits** of dependencies
- **Fail2ban** or similar for brute-force protection
- **Password storage:** use the provided seed/reset scripts so user passwords are
  stored with PBKDF2-HMAC-SHA256. Legacy unsalted SHA-256 user hashes are only
  accepted for a successful login and are upgraded immediately.

### Incident Response

1. **Identify** the security issue
2. **Contain** (disable affected service if critical)
3. **Investigate** logs and access patterns
4. **Remediate** (patch, rotate keys, revoke access)
5. **Notify** affected tenants (if data breach)
6. **Document** lessons learned

### Compliance Checklist

- [ ] Data encryption at rest (database)
- [ ] Data encryption in transit (HTTPS)
- [ ] Access logs retained for 90 days
- [ ] Regular penetration testing
- [ ] GDPR compliance for EU tenants
- [ ] Privacy policy published and accessible
