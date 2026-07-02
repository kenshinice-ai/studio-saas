# StudioSaaS Current Sprint

Version: v2.0
Date: 2026-07-02
Purpose: Active tasks, P0 priorities, verification commands, and go/no-go criteria for the current development cycle.

---

## 1. Sprint Overview

**Current Status:** Phase 1 — SaaS MVP (In Progress)
**Focus:** Stabilize tenant safety, fix critical bugs, add test coverage, prepare for pilot deployment.

**Key principle:** Do not add features before tenant isolation, upload security, auth roles, backup/restore, and browser smoke testing are solid.

---

## 2. P0 Critical Fixes (Highest Priority)

### P0-01 — Auth Login Bug

**File:** `backend/studiosaas/api_v1.py:1916-1921`
**Issue:** Login query does not select `password_hash`, but code reads `user["password_hash"]`. Runtime error on successful lookup.
**Impact:** `/v1/auth/login` cannot work. Studio Admin/Super Admin cannot be secured.
**Fix:** Include `password_hash` in SELECT query. Seed local admin user. Add rate limiting.
**Status:** ✅ Fixed (code-level), needs full testing.

### P0-02 — Route Protection

**Files:** `backend/studiosaas/auth.py`, `backend/studiosaas/api_v1.py`
**Issue:** Super Admin and Studio Admin mutations callable without role check.
**Impact:** Unauthenticated mutation of platform and tenant data.
**Fix:** Implement `require_login`, `require_platform_admin`, `require_tenant_role`. Protect all mutation routes.
**Status:** ⚠️ Partially wired.

### P0-03 — Credit Transaction Schema Mismatch

**Files:** `backend/db/schema_v1.sql`, `backend/studiosaas/api_v1.py`
**Issue:** API transaction names (`debit`, `adjustment_in`, `adjustment_out`) do not match schema CHECK values (`purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration`).
**Impact:** Runtime errors on credit operations.
**Fix:** Map API input to schema values. Update UI labels.
**Status:** ⚠️ Partially fixed.

### P0-04 — dict_row Runtime Errors

**Files:** `backend/studiosaas/api_v1.py` (lines ~1623, ~1737, ~1762, ~1834)
**Issue:** `cur.fetchone()[0]` and `row[0]` used on dict-row cursors.
**Impact:** Multiple POST endpoints crash at runtime.
**Fix:** Replace all tuple indexing with dict-key access.
**Status:** ⚠️ Partially fixed.

### P0-05 — Credit Account Unique/Conflict Bug

**Files:** `backend/db/schema_v1.sql`, `backend/studiosaas/api_v1.py`
**Issue:** `ON CONFLICT (tenant_id, student_id)` does not match actual unique constraint.
**Impact:** Upsert fails with constraint violation.
**Fix:** Use "General Class" course account model — always create/fetch a default course.
**Status:** ⚠️ Partially fixed.

### P0-06 — Portfolio DELETE Mapping

**File:** `backend/studiosaas/api_v1.py`
**Issue:** By-slug DELETE maps to `update_portfolio_item` instead of `delete_portfolio_item`.
**Impact:** Cannot delete portfolio items by tenant slug.
**Fix:** Separate PATCH and DELETE route mappings.
**Status:** ⚠️ Partially fixed.

### P0-07 — Public Endpoint Rate Limiting

**Files:** `backend/studiosaas/api_v1.py`
**Issue:** `balance-query` and `registrations` are public, not rate-limited in v1.
**Impact:** Potential abuse, no duplicate submission control.
**Fix:** Add IP rate limiting, duplicate detection, field length caps, audit logging.
**Status:** ❌ Not implemented.

### P0-08 — Secret Cleanup

**Files:** `.gitignore`, `backend/.api_secret`, `backend/.cms_password`
**Issue:** Runtime secrets and macOS metadata in repository.
**Impact:** Security risk if code is shared or deployed.
**Fix:** Add `.gitignore`, document secret regeneration.
**Status:** ⚠️ Partially addressed.

---

## 3. P1 Important Fixes

| ID | Issue | Priority | Status |
|---|---|---|---|
| P1-01 | Tenant isolation tests incomplete | High | ❌ |
| P1-02 | Missing migration runner | High | ❌ |
| P1-03 | Legacy branding residue (visible "Let's Paint" strings) | Medium | ⚠️ |
| P1-04 | No v1 media upload endpoint | Medium | ❌ |
| P1-05 | Super Admin support mode incomplete | Medium | ❌ |
| P1-06 | No browser automation tests | Medium | ❌ |
| P1-07 | No backup/restore runbook | Medium | ❌ |

---

## 4. P2 Improvements (Nice to Have)

- Split `api_v1.py` (2200+ lines) into modular route files
- Add behavior-based test suite (`tests/`)
- Add migration runner with `schema_migrations` table
- Improve README for new developers/Codex
- Replace vendor JS placeholders with pinned bundles
- Server-side color contrast validation
- Upload cleanup for replaced logos

---

## 5. Verification Commands

### Full Verification

```bash
bash backend/scripts/verify_local.sh
```

### Syntax Check

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py
```

### Legacy Smoke Test

```bash
cd backend && ../.venv/bin/python test_cms.py
# Expected: 73 checks passing, 0 failing
```

### API Health Check

```bash
curl -sS http://localhost:8899/v1/health
```

### Auth Test (Local)

```bash
# Login
curl -i -c /tmp/studiosaas.cookies \
  -H 'Content-Type: application/json' \
  -X POST http://localhost:8899/v1/auth/login \
  -d '{"email":"admin@studiosaas.local","password":"admin123456"}'

# Check session
curl -i -b /tmp/studiosaas.cookies http://localhost:8899/v1/auth/me

# Logout
curl -i -b /tmp/studiosaas.cookies -X POST http://localhost:8899/v1/auth/logout
```

### Tenant Mutation Without Auth (Must Fail)

```bash
curl -i -X POST http://localhost:8899/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad Tenant","slug":"bad-tenant","planCode":"starter"}'
# Expected: 401

curl -i -X PATCH http://localhost:8899/s/lets-paint-studio/v1/tenant \
  -H 'Content-Type: application/json' \
  -d '{"name":"Hacked"}'
# Expected: 401 or 403
```

### Page Open Tests

```bash
# All should return 200
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/cms
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/register
# /register should return 404
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/register
```

---

## 6. Default Credentials (Local)

### Super Admin

| Field | Value |
|---|---|
| Email | `admin@studiosaas.local` |
| Password | `admin123456` |

Reset command:

```bash
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
../.venv/bin/python scripts/seed_super_admin.py --reset-password \
  --email admin@studiosaas.local --password admin123456
```

### Studio Admin (Demo Tenants)

| Tenant | Email | Password |
|---|---|---|
| `lets-paint-studio` | `owner@lets-paint-studio.test` | `admin123456` |
| `lets-play-piano` | `owner@lets-play-piano.test` | `admin123456` |
| `lets-play-game` | `owner@lets-play-game.test` | `admin123456` |

---

## 7. Core Files To Recheck After Future Changes

- `backend/studiosaas/api_v1.py`
- `backend/studiosaas/auth.py`
- `backend/frontend/studio-admin.html`
- `super-admin.html`
- `tenant-template/index.html`
- `tenant-template/register.html`
- `legacy-root/index.html`
- `legacy-root/register.html`

---

## 8. Go/No-Go Criteria

### Local Demo: GO (after dependency install and smoke tests pass)

### Internal Testing: CONDITIONAL GO (after P0-01, P0-02, P0-03, P0-04, P0-05)

### External Pilot: NO-GO (until all P0 fixes verified)

### AWS Staging: NO-GO (P0 fixes + `.gitignore` cleanup + backup/restore runbook)

---

## 9. Next Recommended Tasks (Ordered)

1. Complete route protection for all mutation endpoints
2. Add tenant isolation test suite (cross-tenant negative tests)
3. Add migration runner with `schema_migrations` table
4. Replace legacy branding residue in CMS/Register surfaces
5. Add v1 media upload endpoint
6. Add browser smoke test script (Playwright/Selenium)
7. Improve Super Admin tenant lifecycle (pause/resume, plan change)
8. Improve registration workflow (pending approval → student linkage)
9. Add backup/export script and runbook
10. Prepare AWS staging runbook

---

## 10. Archived Sprint Records

Historical fix records and task lists are preserved in `docs/archive/`:

- `STUDIOSAAS_FIX_SYNC_CHECKLIST.md` — executed fixes and remaining improvements
- `StudioSaaS_Codex_5_Fixes_Prompt.md` — 5 focused fix prompt
- `StudioSaaS_Codex_Executable_Tasks_v1.md` — 12 executable tasks (Task 0–12)
- `StudioSaaS_Codex_P0_Fix_Prompt.md` — P0 fix prompt for next Codex session
- `StudioSaaS_Codex_Upgrade_Masterplan_v2.md` — upgrade masterplan with next 10 tasks
