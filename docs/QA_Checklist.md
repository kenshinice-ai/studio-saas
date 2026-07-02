# QA Checklist

> **StudioSaaS Quality Assurance Reference**
> Last updated: 2026-07-02

---

## Pre-Release Checklist

### 1. Backend

- [ ] `../.venv/bin/python backend/test_tenant_isolation.py` passes all tenant-isolation tests
- [ ] `../.venv/bin/python backend/test_cms.py` passes all CMS functional tests
- [ ] `curl http://localhost:8899/v1/health` returns 200 with expected fields
- [ ] All API routes return proper HTTP status codes (200, 201, 400, 401, 404, 500)
- [ ] Error responses include `error` and `message` keys
- [ ] Rate limiting headers present on public endpoints
- [ ] CORS configured for known tenant domains

### 2. Tenant Routing

- [ ] `/<tenant_slug>/cms` renders the correct tenant's CMS
- [ ] `/<tenant_slug>/cms/edit/<page_id>` loads the correct page
- [ ] Unknown tenant slug returns 404 (not a blank page)
- [ ] Super-admin `/studio-admin` lists all active tenants
- [ ] Tenant switching from super-admin dashboard works
- [ ] No cross-tenant data leakage (verified by isolation tests)

### 3. CMS Functionality

- [ ] Page editor loads existing pages correctly
- [ ] New page creation saves with valid slug
- [ ] Page deletion removes from CMS and front-end
- [ ] Image upload stores to `CMS_DATA_DIR` and returns valid URL
- [ ] Rich text editor preserves formatting on save/load
- [ ] Draft vs Published states toggle correctly
- [ ] Public CMS page reflects Published status

### 4. Frontend

- [ ] All tenant pages load within 2s on local network
- [ ] CSS custom properties (brand colours) render correctly per tenant
- [ ] Responsive breakpoints: mobile (<640px), tablet (640–1024px), desktop
- [ ] Navigation links resolve correctly after tenant switch
- [ ] 404 page displays for invalid URLs
- [ ] No console errors in browser DevTools

### 5. Database

- [ ] All tables have proper foreign key constraints
- [ ] Tenant-scoped queries use `tenant_id` filter
- [ ] Indexes exist on `tenant_id`, `slug`, `status` columns
- [ ] Migration scripts are idempotent (can run twice without error)
- [ ] Backup/restore procedure documented and tested

### 6. Security

- [ ] No hardcoded API keys or credentials in source
- [ ] `.env` file excluded from version control (in `.gitignore`)
- [ ] File uploads validated (type, size, extension)
- [ ] SQL injection prevention: parameterized queries only
- [ ] XSS prevention: output escaping on all dynamic content
- [ ] CSRF protection on state-changing POST endpoints
- [ ] Session tokens expire after inactivity

### 7. Performance

- [ ] CMS page load < 2s (local, no CDN)
- [ ] Image uploads < 5s for images under 5MB
- [ ] Database queries under 100ms for single-tenant lookups
- [ ] Static assets served with Cache-Control headers
- [ ] No N+1 query patterns in page rendering

### 8. Deployment Readiness

- [ ] `Dockerfile` builds without errors
- [ ] `docker-compose.yml` starts all services (`backend`, `postgres`)
- [ ] Environment variables documented in `.env.example`
- [ ] Health check endpoint responds to container orchestrator
- [ ] Log output structured (JSON format) for log aggregation
- [ ] Graceful shutdown handled (SIGTERM)

---

## Regression Matrix

| Feature | Tenant Isolation | CMS CRUD | Routing | Public Pages | Super Admin |
|---|---|---|---|---|---|
| Create Page | ✅ | ✅ | ✅ | ✅ | ✅ |
| Edit Page | ✅ | ✅ | ✅ | ✅ | ✅ |
| Delete Page | ✅ | ✅ | ✅ | ✅ | ✅ |
| Upload Image | ✅ | ✅ | ✅ | ✅ | ✅ |
| Tenant Switch | ✅ | ✅ | ✅ | — | ✅ |
| Brand Colours | ✅ | ✅ | ✅ | ✅ | ✅ |
| 404 Handling | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Quick Smoke Test (5 min)

1. Start server: `PORT=8899 CMS_DATA_DIR=/tmp/studiosaas_cms_data ../.venv/bin/python backend/server.py`
2. Hit health: `curl http://localhost:8899/v1/health`
3. Load CMS: Open `http://localhost:8899/lets-paint-studio/cms` in browser
4. Create page: Add a new page, publish it
5. Verify public: Open `http://localhost:8899/lets-paint-studio` — new page should appear
6. Run tests: `../.venv/bin/python backend/test_cms.py`

---

## Known Issues & Workarounds

| ID | Description | Status | Workaround |
|---|---|---|---|
| QA-001 | Image upload fails for files > 10MB | Open | Limit upload to 5MB |
| QA-002 | Safari history back button doesn't reload CMS edit | Open | Manual refresh required |
| QA-003 | Super-admin tenant list doesn't paginate | Open | Works for < 100 tenants |

---

## Test Data Management

### Reset to Clean State

```bash
# Drop and recreate test database
psql "postgresql:///studiosaas_local_test" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migrations
psql "postgresql:///studiosaas_local_test" -f schema_v1.sql

# Seed demo data
../.venv/bin/python scripts/seed_random_demo_data.py --students-per-tenant 24
```

### Create Specific Test Tenant

```bash
# Via API (running server locally)
curl -X POST http://localhost:8899/v1/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Tenant","slug":"test-tenant","plan_code":"starter"}'
```
