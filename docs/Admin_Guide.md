# Admin Guide

> **StudioSaaS Platform Administration**
> Last updated: 2026-07-02

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
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Initialize database:**
   ```bash
   psql "postgresql://<user>@localhost:5432/studiosaas" -f schema_v1.sql
   ```

5. **Start the server:**
   ```bash
   PORT=8899 CMS_DATA_DIR=/var/lib/studiosaas/cms \
   ../.venv/bin/python backend/server.py
   ```

6. **Verify health:**
   ```bash
   curl http://localhost:8899/v1/health
   ```

---

## Tenant Management

### Creating a New Tenant

Via **Super-Admin Dashboard** (`/<tenant_slug>/studio-admin`):

1. Click **"Add Tenant"**
2. Fill in:
   - **Name:** Display name (e.g., "Academy of Art")
   - **Slug:** URL identifier (e.g., "academy-of-art")
   - **Plan:** Starter, Pro, or Enterprise
   - **Brand Colours:** Primary and secondary colours (hex codes)
3. Click **"Create"**

Via **API:**

```bash
curl -X POST http://localhost:8899/v1/tenants \
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

### Deactivating a Tenant

1. Find the tenant in Super-Admin Dashboard
2. Click **"Deactivate"**
3. Confirm the action

> **Note:** Deactivated tenants are hidden from public CMS but data is preserved.

### Deleting a Tenant

> **Warning:** This is irreversible. Ensure backup is taken first.

1. Navigate to Super-Admin Dashboard
2. Find the tenant
3. Click **"Delete"**
4. Confirm by typing the tenant slug

---

## Super-Admin Dashboard

### URL Pattern

`/<tenant_slug>/studio-admin` (e.g., `/super-admin/studio-admin`)

### Features

| Feature | Description |
|---|---|
| Tenant List | All active tenants with plan, status, page count |
| Add Tenant | Create new tenant with branding |
| Edit Tenant | Modify tenant details |
| Deactivate | Hide tenant from public CMS |
| Activate | Restore deactivated tenant |
| Delete | Permanently remove tenant and data |
| Search | Filter tenants by name or slug |
| Sort | Click column headers to sort |

### Permissions

- Only users with `super_admin` role can access
- Regular tenants see only their own CMS

---

## Monitoring & Health

### Health Endpoint

```bash
curl http://localhost:8899/v1/health
```

**Expected Response:**

```json
{
  "status": "healthy",
  "database": "connected",
  "uptime_seconds": 3600,
  "version": "1.0.0"
}
```

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

**Manual backup:**

```bash
# Full database dump
pg_dump studiosaas > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
pg_dump studiosaas | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz
```

**Automated backup (cron):**

```bash
# Add to crontab: backup daily at 2 AM
0 2 * * * pg_dump studiosaas | gzip > /backups/studiosaas_$(date +\%Y\%m\%d).sql.gz
```

### CMS Data Backup

```bash
# Archive CMS uploads directory
tar -czf cms_backup_$(date +%Y%m%d_%H%M%S).tar.gz /var/lib/studiosaas/cms/
```

### Recovery Procedure

1. **Stop the server:**
   ```bash
   systemctl stop studiosaas
   # or kill the process
   ```

2. **Restore database:**
   ```bash
   psql studiosaas < backup_20260702_020000.sql
   ```

3. **Restore CMS data:**
   ```bash
   rm -rf /var/lib/studiosaas/cms/*
   tar -xzf cms_backup_20260702_020000.tar.gz -C /var/lib/studiosaas/cms/
   ```

4. **Restart the server:**
   ```bash
   systemctl start studiosaas
   # or
   ../.venv/bin/python backend/server.py
   ```

5. **Verify:**
   ```bash
   curl http://localhost:8899/v1/health
   ```

### Backup Retention

| Type | Frequency | Retention |
|---|---|---|
| Database | Daily | 30 days |
| CMS Data | Daily | 7 days |
| Full (DB + CMS) | Weekly | 90 days |

---

## User Support

### Common Issues

| Issue | Cause | Solution |
|---|---|---|
| "Tenant context is required" | Missing tenant slug in URL | Verify URL pattern: `/<slug>/cms` |
| 404 on CMS page | Tenant not activated | Activate tenant in super-admin |
| Images not uploading | `CMS_DATA_DIR` not writable | Check directory permissions |
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

1. Verify `TENANT_ROUTING_AND_STRUCTURE.md` URL patterns
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
