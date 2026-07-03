# StudioSaaS Current Sprint

Version: v3.0
Date: 2026-07-03
Purpose: Status tracking for the prioritised task list in `codingprompt.md` (same numbering), verification commands, credentials, and go/no-go criteria.

> Task definitions (problem/evidence/fix/verify) live in `codingprompt.md`. This file tracks **status only**. Update it after each completed task.

---

## 1. Sprint Overview

**Current Status:** Phase 1 — SaaS MVP (In Progress)
**Focus:** Data consistency (roles/enums), test infrastructure, migration runner, auth hardening — before any visual polish.

**Key principle:** Do not add features before tenant isolation, upload security, auth roles, backup/restore, and browser smoke testing are solid.

---

## 2. Verified Fixed (2026-07-03 code-level audit)

These items from earlier sprint docs are confirmed done — do not re-fix:

| Legacy ID (v2 doc) | Item | Evidence |
|---|---|---|
| P0-01 (old) | Auth login `password_hash` SELECT bug | Fixed per code; runtime re-test pending under new P0-06 audit |
| P0-04 (old) | dict_row tuple-indexing crashes | No `fetchone()[0]` / `row[0]` remain in `api_v1.py` |
| P0-05 (old) | Credit account ON CONFLICT mismatch | `ON CONFLICT (tenant_id, student_id, course_id)` at `api_v1.py:2482` |
| P0-06 (old) | Portfolio DELETE mapped to update | Separate DELETE route at `api_v1.py:3473` |
| P0-07 (old) | Public endpoint rate limiting | Implemented in-memory: registrations 5/min, balance-query 10/min, uploads 5/min |
| P1-03 (old) | Visible "Let's Paint" branding in HTML | Zero matches in HTML surfaces; only `sw.js` remains (new P2-02) |

---

## 3. Active Task Status (numbering = codingprompt.md v2)

### P0 — Data consistency and security

| ID | Task | Status |
|---|---|---|
| P0-01 | Unify role model — enum matches CHECK; platform admin = `tenant_id IS NULL` membership; seed fixed | ✅ Done 2026-07-03 |
| P0-02 | Fix pytest — requirements-dev, clean pytest.ini, `backend/tests/` (20 tests) | ✅ Done 2026-07-03 |
| P0-03 | Migration runner — `migrations/0001+0002`, `schema_migrations`, `run_migrations.py` (`--baseline`, `--dry-run`) | ✅ Done 2026-07-03 |
| P0-04 | Repo hygiene — deletions committed, `backend/` now tracked (was never in git!), checkpoints ignored | ✅ Done 2026-07-03 |
| P0-05 | Login rate limiting (5/min per IP+email, 30/min per IP) + legacy-login failure audit | ✅ Done 2026-07-03 |
| P0-06 | Route audit (146 routes): mutations were safe; 12 unauthenticated tenant GET reads fixed | ✅ Done 2026-07-03 |
| P0-07 | Enum alignment verified; `archived`/`trialing` decisions recorded in Database.md §3 | ✅ Done 2026-07-03 |

### P1 — Engineering quality and business loops

| ID | Task | Status |
|---|---|---|
| P1-01 | Documentation sync | ✅ Done 2026-07-03 (this refresh) |
| P1-02 | Tenant isolation negative test matrix | ✅ Done 2026-07-03 (`test_tenant_isolation.py`, 63+ checks) |
| P1-03 | v1 media upload endpoint + central media service | ✅ Done 2026-07-03 |
| P1-04 | Registration review → student conversion loop | ✅ Done 2026-07-03 (duplicate detection, student link, review notes, audit) |
| P1-05 | Credits closed loop + attendance | ✅ Done 2026-07-03 |
| P1-06 | Playwright browser smoke tests | ❌ |
| P1-07 | Backup/restore script + runbook | ✅ Done 2026-07-03 |

### P2 — Structure and UI (after P0 is green)

| ID | Task | Status |
|---|---|---|
| P2-01 | Split `api_v1.py` (4040 lines) along target-architecture module boundaries | ❌ |
| P2-02 | Multi-tenant PWA/sw.js (last "Let's Paint" residue) | ❌ |
| P2-03 | Replace runtime Babel/Tailwind vendor JS with prebuilt assets | ❌ |
| P2-04 | Super Admin platform cockpit | ❌ |
| P2-05 | Studio Admin workflow reorganisation | ❌ |
| P2-06 | Shared design tokens from `docs/Design_System.md` | ❌ |

### P3 — Platform and deployment

| ID | Task | Status |
|---|---|---|
| P3-01 | Config layering + secure cookies + structured logging | ❌ |
| P3-02 | Docker + Nginx + GitHub Actions CI | ❌ |
| P3-03 | S3/MinIO media storage branch | ❌ |
| P3-04 | Long-term data infra (Redis/replicas/ES/ClickHouse/MQ) — explicitly deferred | ⏸ Deferred |
| P3-05 | Extension services (Payment/CRM/Notification/Report/AI) — pilot-feedback driven | ⏸ Deferred |

---

## 4. Verification Commands

### Full verification

```bash
bash backend/scripts/verify_local.sh
```

### Syntax check

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py
```

### Script-style smoke tests

```bash
cd backend && ../.venv/bin/python test_cms.py
# Expected: 72 checks passing, 0 failing
cd backend && ../.venv/bin/python test_tenant_isolation.py
```

### Pytest (after P0-02 lands)

```bash
cd backend && ../.venv/bin/python -m pytest -q
```

### API health check

```bash
curl -sS http://localhost:8899/v1/health
```

### Auth test (local)

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

### Tenant mutation without auth (must fail)

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

### Page open tests

```bash
# All should return 200
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/cms
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/studio-admin
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/register
# /register should return 404
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/register
```

---

## 5. Default Credentials (Local)

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

Password storage: seed/reset scripts write PBKDF2-HMAC-SHA256 hashes. Legacy unsalted SHA-256 user hashes are verified only to complete a successful login, then upgraded in place.

### Studio Admin (Demo Tenants)

| Tenant | Email | Password |
|---|---|---|
| `lets-paint-studio` | `owner@lets-paint-studio.test` | `admin123456` |
| `lets-play-piano` | `owner@lets-play-piano.test` | `admin123456` |
| `lets-play-game` | `owner@lets-play-game.test` | `admin123456` |

---

## 6. Core Files To Recheck After Future Changes

- `backend/studiosaas/api_v1.py`
- `backend/studiosaas/auth.py`
- `backend/studiosaas/models.py`
- `backend/db/schema_v1.sql`
- `backend/frontend/studio-admin.html`
- `super-admin.html`
- `tenant-template/*.html`
- `legacy-root/index.html`, `legacy-root/register.html`

---

## 7. Go/No-Go Criteria

| Milestone | Verdict | Condition |
|---|---|---|
| Local demo | **GO** | Dependency install + smoke tests pass |
| Internal testing | **GO** (2026-07-03) | P0-01…P0-07 all done and verified |
| External pilot | **NO-GO** | Until all P0 verified + P1-07 backup runbook |
| AWS staging | **NO-GO** | All P0 + P1-07 backup runbook + P3-01 config layering |

---

## 8. Historical Records

Earlier sprint documents (`docs/archive/`, Codex prompt files) were intentionally deleted in the 2026-07-03 documentation refactor. Git history before commit `1ff243d` retains them if ever needed.
