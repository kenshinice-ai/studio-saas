# QA Checklist

> **StudioSaaS Quality Assurance Reference**
> Last updated: 2026-07-10

---

## Pre-Release Checklist

### 1. Backend

- [ ] `cd backend && ../.venv/bin/python test_tenant_isolation.py` passes all tenant-isolation tests
- [ ] `cd backend && ../.venv/bin/python test_cms.py` passes all CMS functional tests (expected: 72 checks)
- [ ] `cd backend && ../.venv/bin/python -m pytest -q` passes (after P0-02 lands)
- [ ] `curl http://localhost:8899/v1/health` returns 200 with expected fields
- [ ] All API routes return proper HTTP status codes (200, 201, 400, 401, 403, 404, 429, 500)
- [ ] Error responses include `error` and `message` keys
- [ ] Public endpoints return 429 when rate limits are exceeded (registrations 5/min, balance-query 10/min per tenant/IP, uploads 5/min)
- [ ] Login rate limiting active and failed logins audited

### 2. Tenant Routing and Isolation

- [ ] `/<tenant_slug>` renders the public portal and `/<tenant_slug>/cms` renders the correct tenant CMS shell
- [ ] `/<tenant_slug>/register` renders the tenant's registration page
- [ ] `/<tenant_slug>/studio-admin` renders the tenant's admin dashboard
- [ ] `/s/<tenant_slug>/v1/tenant`, `/dashboard`, and `/students` return 401 before login, not 404
- [ ] Root `/register` returns 404 (registration belongs to tenants)
- [ ] `/<tenant_slug>/manifest-student.json` uses tenant-scoped `start_url` and `scope`; root `/manifest-student.json` does not point to `/register`
- [ ] `/<tenant_slug>/manifest-cms.json` starts at `/<tenant_slug>/cms` and uses tenant scope
- [ ] Unknown tenant slug returns 404 (not a blank page)
- [ ] Reserved slugs (`api`, `v1`, `register`, `super-admin`, `studio-admin`, `vendor`) rejected on tenant creation
- [ ] Unauthenticated mutation requests return 401/403 (see Current_Sprint §4 curl checks)
- [ ] Tenant A session cannot read or write tenant B data (isolation tests)
- [ ] `X-Tenant-Slug` header spoofing cannot cross tenant boundaries

### 3. Studio Admin Website/Brand Console

- [ ] Studio admin login works per tenant; wrong-tenant login is rejected
- [ ] Archived/deleted tenants cannot access tenant-scoped Studio Admin APIs
- [ ] Website / Brand is the default visible section
- [ ] Operational modules are not exposed as primary Studio Admin navigation
- [ ] Studio Admin links distinguish Studio Website, Studio CMS, Quick Registration, and the Studio Admin brand workspace
- [ ] Brand settings (logo, colors, welcome, slogan, registration profile) sync to Portal/CMS/Register surfaces
- [ ] Save Draft leaves `/v1/public/<slug>/brand` unchanged
- [ ] Publish creates a numbered brand version and clears the draft
- [ ] Restore Version creates a draft and does not publish until the owner confirms
- [ ] Studio Admin shows the current plan as read-only and cannot change tenant entitlements
- [ ] Studio Admin HTML contains no hidden students, attendance, courses, packages, registration-review, or portfolio CRUD sections
- [ ] Logo upload validates type/size and replaces preview reliably
- [ ] Logo asset upload alone does not alter the public brand; only Publish makes the new logo live

### 3.1 CMS Daily Operations

- [ ] Student create/update/archive round-trips correctly in CMS
- [ ] Course and package changes persist and list correctly in CMS
- [ ] Credit transactions map correctly (`debit`→`consume`, `adjustment_in/out`→`adjustment`)
- [ ] Insufficient balance is blocked with a clear error
- [ ] Pending registrations appear in the CMS review queue
- [ ] Duplicate registration attempts are visible and linked to the existing student or pending registration
- [ ] Approving a registration creates/links a student and stores the review decision
- [ ] Rejecting/archiving a registration stores a review note and writes audit history
- [ ] Portal and Quick Registration submissions show their source and language in the CMS queue
- [ ] CMS can mark a lead contacted, trial booked, or waiting and store a next follow-up date
- [ ] Conversion is blocked clearly when the plan student limit has been reached

### 4. Public Surfaces

- [ ] Registration form submits, deduplicates, and shows a clear success state
- [ ] Balance query returns only the matching family's data
- [ ] Tenant brand payload (`/v1/public/<slug>/brand`) contains no private data
- [ ] All tenant pages load within 2s on local network
- [ ] CSS custom properties (brand colours) render correctly per tenant
- [ ] Responsive breakpoints: mobile (<640px), tablet (640–1024px), desktop
- [ ] No console errors in browser DevTools
- [ ] Generated tenant pages pass `node backend/scripts/check_inline_scripts.mjs`, including names with apostrophes and HTML punctuation

### 5. Database

- [ ] All tables have proper foreign key constraints
- [ ] Tenant-scoped queries use `tenant_id` filter
- [ ] Indexes exist on `tenant_id`, `slug`, `status` columns
- [ ] Enum values in code/UI match schema CHECK constraints (see Database.md §3)
- [ ] Migration runner is idempotent — safe to run twice (after P0-03 lands)
- [ ] Backup/restore procedure documented and tested (after P1-07 lands)

### 6. Security

- [ ] No hardcoded API keys or credentials in source
- [ ] Privileged pilot passwords are unique, rotated, and stored only in the protected local credential file
- [ ] `.env`, `backend/.api_secret`, `backend/.cms_password` excluded from version control
- [ ] File uploads validated (type, size, extension, magic bytes)
- [ ] SQL injection prevention: parameterized queries only
- [ ] XSS prevention: no unsafe `innerHTML` for user-generated content
- [ ] Admin table/list renderers use `textContent`/DOM nodes for tenant, student, registration, attendance, and portfolio data
- [ ] Session cookies HttpOnly; Secure/SameSite in production config
- [ ] Failed logins audited
- [ ] Sensitive admin actions write to `audit_logs`
- [ ] Tenant deletion flow uses archive -> explicit permanent delete; direct tenant DELETE is rejected
- [ ] Tenant archive writes `tenant_archives` row and JSON snapshots before status changes
- [ ] Super Admin tenant details hide Archive Path for active tenants and show it for archived tenants
- [ ] Super Admin hides test fixture tenants by default; "Show test tenants" reveals them with a badge
- [ ] Super Admin quick links disable correctly for paused/archived/deleted tenants and missing admin login
- [ ] Public gallery returns only items with recorded publication consent

### 7. Performance

- [ ] CMS page load < 2s (local, no CDN)
- [ ] Image uploads < 5s for images under 5MB
- [ ] Database queries under 100ms for single-tenant lookups
- [ ] Static assets served with Cache-Control headers
- [ ] No N+1 query patterns in list endpoints

### 8. Deployment Readiness (Phase 3 — not yet applicable)

These items activate once P3-02 lands; they are **not** blockers for local pilot:

- [ ] `Dockerfile` builds without errors
- [ ] `docker-compose.yml` starts `backend` + `postgres`
- [ ] Environment variables documented in `.env.example`
- [ ] Structured (JSON) log output for aggregation
- [ ] Graceful shutdown handled (SIGTERM)

---

## Quick Smoke Test (5 min)

1. Start server: `./start_studiosaas_local.sh`
2. Hit health: `curl http://localhost:8899/v1/health`
3. Open Super Admin: `http://localhost:8899/super-admin`, log in as `admin@studiosaas.local`
4. Open a tenant: `http://localhost:8899/lets-paint-studio` and `/lets-paint-studio/studio-admin`
5. Submit a registration on `/lets-paint-studio/register`, confirm it appears in the admin pending queue
6. Run tests: `cd backend && ../.venv/bin/python test_cms.py`

---

## Known Issues & Workarounds

| ID | Description | Status | Workaround |
|---|---|---|---|
| QA-001 | `pytest -q` broken (dep + config) | ✅ Fixed 2026-07-03 (P0-02) | — |
| QA-002 | Rate limits reset on server restart (in-memory) | Accepted for pilot | Redis-backed limiter at P3-04 |
| QA-003 | Super-admin tenant list pagination | ✅ Fixed 2026-07-03 | Client-side page controls added |
| QA-004 | Attendance check-in flow | ✅ Fixed 2026-07-03 | Attendance API and CMS daily workflow added |

---

## Test Data Management

### Reset to Clean State

```bash
dropdb -h localhost -p 5432 --if-exists studiosaas_local_test
createdb -h localhost -p 5432 studiosaas_local_test
psql -h localhost -p 5432 -d studiosaas_local_test \
  -v ON_ERROR_STOP=1 -f backend/db/schema_v1.sql

cd backend
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_super_admin.py
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_local_test_tenants.py
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_random_demo_data.py --students-per-tenant 24
```

### Create Specific Test Tenant

```bash
# Via API (requires super admin session cookie)
curl -X POST http://localhost:8899/v1/admin/tenants \
  -b /tmp/studiosaas.cookies \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Tenant","slug":"test-tenant","plan_code":"starter"}'
```
