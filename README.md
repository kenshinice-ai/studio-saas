# StudioSaaS

StudioSaaS is a multi-tenant Creative Studio Operating System for art schools, music studios, tutoring centres, creative academies, kids' activity providers, and small education businesses.

It provides a lightweight SaaS-style platform for managing:

- tenant websites and public registration forms
- studio admin dashboards
- students, registrations, courses, packages
- credit (clock-hour) balances with ledger-style transactions
- portfolio media and branding settings
- platform-level tenant management

**Status:** local-first pilot stage. Runs locally for development and pilot testing, with a deployment path towards AWS (managed PostgreSQL, S3 media, production WSGI).

---

## 1. Stack

### Current (canonical)

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, Flask, Waitress |
| Database | PostgreSQL 16+ (local), psycopg 3 |
| Frontend | Vanilla HTML/CSS/JS, static tenant templates |
| Auth | Session-based, role-based access control |
| Media | Local file storage (`storage_provider` field reserved for S3) |

This project does **not** currently use FastAPI, SQLAlchemy, Redis, or any microservice infrastructure.

### Target (v2 vision)

A target architecture (modular services: Auth/Tenant/Student/Course/Credit/Attendance/Portfolio/File/Notification/Report; Redis, S3, message queue, read replicas) is documented in `docs/Architecture.md` §7. **Adoption policy:** the current Flask monolith is organised along those module boundaries (modular monolith); heavier infrastructure is deferred to Roadmap Phase 3–5. Do not introduce it during the pilot.

---

## 2. User Levels and URLs

| Level | Who | Main surface |
|---|---|---|
| Platform Operator | SaaS owner | `/super-admin` (also `/`) |
| Studio Owner / Admin | One tenant studio | `/<tenant-slug>/studio-admin` (tenant backend for managing Studio CMS data, registrations, students, credits, portfolio, and branding) |
| Public Parent / Student | Visitors | `/<tenant-slug>`, `/<tenant-slug>/register` |

Local URLs (default port 8899):

```
http://localhost:8899/super-admin
http://localhost:8899/lets-paint-studio
http://localhost:8899/lets-paint-studio/register
http://localhost:8899/lets-paint-studio/studio-admin
http://localhost:8899/s/lets-paint-studio/v1/tenant     # tenant-scoped API
http://localhost:8899/v1/health
```

Root `/register` is intentionally closed (404) — registration belongs to tenants.

---

## 3. Project Structure

```
.
├── README.md                     # This file
├── codingprompt.md               # Prioritised task list P0→P3 (current sprint source of truth)
├── START_STUDIOSAAS_LOCAL.command / start_studiosaas_local.sh
├── super-admin.html              # Platform dashboard
├── tenant-template/              # Template copied into tenants/<slug>/ on creation
├── tenants/<slug>/               # Generated tenant workspaces
├── legacy-root/                  # Tenant CMS — the core daily surface (src/cms-app.jsx + build)
├── docs/                         # Product, architecture, API, DB, QA, ops docs
└── backend/                      # Canonical runtime
    ├── server.py                 # Flask application (~1560 lines)
    ├── requirements.txt
    ├── pytest.ini
    ├── db/schema_v1.sql          # Full schema (18 tables)
    ├── studiosaas/
    │   ├── api_v1.py             # All API routes (~4040 lines — split planned, P2-01)
    │   ├── auth.py               # Auth helpers and decorators
    │   ├── models.py             # Role/TenantStatus enums, contexts
    │   ├── db.py / tenant_context.py / workspaces.py / audit.py / config.py / migration.py
    ├── scripts/                  # Seed, import, verify scripts
    ├── frontend/studio-admin.html
    ├── test_cms.py               # Script-style smoke test (run with python, not pytest)
    └── test_tenant_isolation.py  # Script-style isolation test
```

---

## 4. Local Development Setup

### 4.1 Requirements

- Python 3.11+, PostgreSQL 16+ (Homebrew: 16/18 both fine), pip
- macOS, Linux, or WSL-compatible shell

### 4.2 Virtual environment

The venv lives at the **project root** (`.venv/`), not inside `backend/`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 4.3 Database bootstrap

Local database name used throughout docs and scripts: `studiosaas_local_test`.

```bash
createdb -h localhost -p 5432 studiosaas_local_test
export STUDIOSAAS_DATABASE_URL="postgresql://$(whoami)@localhost:5432/studiosaas_local_test"

psql "$STUDIOSAAS_DATABASE_URL" -v ON_ERROR_STOP=1 -f backend/db/schema_v1.sql
```

Preferred bootstrap (migration runner, applies `backend/db/migrations/` in order):

```bash
cd backend && python scripts/run_migrations.py
# existing databases bootstrapped from schema_v1.sql: baseline once first
#   python scripts/run_migrations.py --baseline 0001_schema_v1.sql
```

### 4.4 Seed local data

```bash
cd backend
python scripts/seed_super_admin.py
python scripts/seed_local_test_tenants.py
python scripts/seed_random_demo_data.py --students-per-tenant 24   # optional
```

### 4.5 Start the server

```bash
./start_studiosaas_local.sh          # from project root
# or
cd backend && python server.py
```

Server runs at `http://localhost:8899`.

### 4.6 Default local credentials

| Account | Email | Password |
|---|---|---|
| Super Admin | `admin@studiosaas.local` | `admin123456` |
| Studio owner (per demo tenant) | `owner@<slug>.test` | `admin123456` |

---

## 5. Environment Variables

```bash
export STUDIOSAAS_DATABASE_URL="postgresql://localhost/studiosaas_local_test"
export STUDIOSAAS_ENV="local"
export STUDIOSAAS_PORT="8899"
export STUDIOSAAS_SECRET_KEY="local-dev-secret-change-me"
export STUDIOSAAS_MEDIA_ROOT="./media"
```

Production must not rely on local secret files (`backend/.api_secret`, `backend/.cms_password` are local-only and git-ignored).

---

## 6. Canonical Enums (as enforced by the database today)

These are the values the schema actually CHECKs. Code, seeds, UI, and docs must match them. Extensions (e.g. `archived` tenant status, richer media visibility) go through migration files — see `codingprompt.md` P0-01/P0-07.

| Concept | Where | Values |
|---|---|---|
| Membership role | `memberships.role` | `super_admin`, `owner`, `staff`, `parent` |
| Tenant status | `tenants.status` | `trial`, `active`, `past_due`, `paused`, `cancelled` |
| Subscription status | `subscriptions.status` | `trialing`, `active`, `past_due`, `paused`, `cancelled` |
| Credit transaction | `credit_transactions.transaction_type` | `purchase`, `consume`, `adjustment`, `refund`, `expire`, `migration` |
| Registration status | `registrations.status` | `pending`, `approved`, `rejected`, `duplicate`, `contacted`, `archived` |
| Media visibility | `media_assets.visibility` | `private`, `public_token` |

**Note:** `users` has **no role column** — roles live on `memberships` (user × tenant). A platform administrator is a `super_admin` membership with `tenant_id IS NULL`, which grants access to every tenant including ones created later (P0-01, done 2026-07-03).

---

## 7. Testing and Verification

```bash
# Syntax check (from project root)
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py

# Unit/boundary tests (install dev deps first: pip install -r backend/requirements-dev.txt)
cd backend && ../.venv/bin/python -m pytest -q

# Script-style smoke tests (run with python, NOT pytest)
cd backend
../.venv/bin/python test_cms.py                 # expected: 72 checks passing
../.venv/bin/python test_tenant_isolation.py

# Full local verification
bash backend/scripts/verify_local.sh
```

Manual checks with the server running:

```bash
curl -sS http://localhost:8899/v1/health
curl -i -X POST http://localhost:8899/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad","slug":"bad","planCode":"starter"}'   # must be 401/403
```

---

## 8. Security Baseline

- All admin mutation routes require authentication; tenant routes enforce membership; platform routes require super admin.
- Public endpoints and login endpoints are IP/email rate-limited in memory for the local pilot; failed logins are audited.
- Uploads validate extension/MIME/size; media is tenant-scoped; no path traversal.
- Passwords: PBKDF2-HMAC-SHA256; legacy unsalted SHA-256 hashes are accepted once on successful login, then upgraded in place.
- Secrets are never committed; see `.gitignore`.
- Cross-tenant access must always fail — covered by `test_tenant_isolation.py`.

---

## 9. Documentation Index

| Document | Content |
|---|---|
| `codingprompt.md` | **Prioritised task list P0→P3 — start here for what to work on** |
| `docs/Current_Sprint.md` | Status tracking for the task list, verification commands, credentials |
| `docs/StudioSaaS_Blueprint_v2.md` | Product vision, market, pricing, MVP acceptance criteria |
| `docs/Architecture.md` | Current architecture + target architecture (v2 vision) |
| `docs/API.md` | Endpoint reference, auth model, route protection |
| `docs/Database.md` | Schema reference, canonical enums, migration strategy |
| `docs/Development_Roadmap.md` | Phases 0–5, target-stack adoption mapping |
| `docs/QA_Checklist.md` | Pre-release checklist |
| `docs/Admin_Guide.md` | Platform ops: setup, backup, troubleshooting |
| `docs/Design_System.md` | UI tokens and component standards |

---

## 10. Project Philosophy

**Clarity creates trust.**

- For studio owners, daily operations get simpler.
- For parents, registration feels clear and reassuring.
- For platform operators, tenant management stays controlled and auditable.
- For developers, the codebase gets easier to understand after every sprint.

The product grows from a working local CMS → stable multi-tenant pilot platform → polished creative studio SaaS, without losing data integrity, tenant isolation, or operational clarity.

Do not add payments, complex billing, or enterprise features before pilot data safety and tenant isolation are stable.
