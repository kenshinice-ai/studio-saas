# PWE Studio SaaS

Current release: **v7.3.1**

PWE Studio SaaS (repo: studiosaas) is a multi-tenant Creative Studio Operating System for art schools, music studios, tutoring centres, creative academies, kids' activity providers, and small education businesses.

It provides a lightweight SaaS-style platform for managing:

- tenant websites and public registration forms
- studio admin dashboards
- students, registrations, courses, packages
- credit (clock-hour) balances with ledger-style transactions
- portfolio media and branding settings
- platform-level tenant management

**Status:** public pilot stage. Runs locally (waitress + PostgreSQL) and is exposed on demand via Cloudflare Tunnel at `https://studiosaas.cc.cd`. The public URL is only expected to be online while the Stage 1 launcher is running. Deployment towards AWS is documented in `docs/Deployment.md`.

Canonical product responsibilities and names are defined in `docs/Product_Surface_Model.md`: Super Admin is the commercial control plane, Studio Admin is the tenant brand/publication workspace, Studio CMS owns daily operations, the Studio Portal is the primary public acquisition experience, and Quick Registration is an alternate tenant-scoped entry.

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
| Studio Owner / Admin | One tenant studio | `/<tenant-slug>/cms` (daily operations) + `/<tenant-slug>/studio-admin` (website/brand/lead-capture settings) |
| Public Parent / Student | Visitors | `/<tenant-slug>` (portal), `/<tenant-slug>/register` |

**Every tenant gets four surfaces** (created from `tenant-template/`, branded via `/v1/public/<slug>/brand`):

| Surface | URL | Purpose |
|---|---|---|
| Portal (门户) | `/<slug>` | Public site: courses, gallery, FAQ, contact, in-page enrolment + private student area (name + mobile + studio-issued 6-digit access code) |
| CMS | `/<slug>/cms` | Staff daily surface: students, roster, check-ins, credits, payments/refunds, logs, analytics, portfolio, and registration review |
| Studio Admin | `/<slug>/studio-admin` | Website/brand console: logo, colours, bilingual public copy, registration fields, preview, draft, publish, and version restore (alias: `/<slug>/cms/studio-admin` redirects here) |
| Register | `/<slug>/register` | Standalone public registration form |

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
    ├── db/schema_v1.sql          # Historical bootstrap schema; ordered migrations are canonical (through 0017)
    ├── studiosaas/
    │   ├── api_v1.py             # All API routes (~5700 lines — split planned, v7 P2-1)
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
The launcher checks Homebrew/PostgreSQL/Python dependencies, creates the local
database when needed, applies ordered migrations, and waits for `/v1/health`.
It does **not** seed demo students unless `STUDIOSAAS_SEED_DEMO=1` is explicitly
set.

### 4.6 Pilot credentials

The local and on-demand public launchers enforce the agreed pilot Super Admin
login (`admin@studiosaas.local`) on every start and keep the matching local
credential record in `~/.studiosaas/pilot-credentials.txt` with mode `0600`.
Set `STUDIOSAAS_ADMIN_PASSWORD` to override the launcher password without
editing the scripts. This fixed pilot credential is not a production policy:
before a permanent deployment, rotate every privileged account with
`backend/scripts/rotate_pilot_credentials.py` and protect the admin routes with
a second access layer.

### 4.7 v7.2.1 shared product improvements

- Public registrations are committed before best-effort applicant and studio-admin email notifications.
- Student profiles support an editable real enrolment date; older records remain unset and reports fall back to trustworthy activity history.
- Registration success pages use an accessible received/next-step/contact flow.
- Portal, Quick Registration, Studio Admin and CMS surfaces share `brand-system.css` semantic typography, colour, date/time and status-output tokens while retaining tenant-configurable accent colours.

### 4.8 v7.3.0 curated brand styles

- Industry presets now apply a recommended visual style together with industry copy and registration questions, with one-click undo before publishing.
- Seven curated styles cover monochrome, editorial, modern, artistic, friendly, bold, and neon-dark directions.
- Each style defines semantic page, panel, text, muted, border, action, and status colours; automatic button text and publish-time contrast checks keep every bundled palette at WCAG AA.
- Tenants can change visual style independently from industry, then fine-tune advanced colours in an explicit Custom state.

### 4.9 v7.3.1 brand-builder usability

- Brand setup now follows three clear steps: industry foundation, colour theme, and studio identity.
- Industry choices remain visual cards, while the seven colour themes use a compact selector with a large live palette preview.
- Manual colour and typography controls stay collapsed until needed, reducing visual noise without removing flexibility.
- Chinese/English labels and mobile navigation were refined and verified at desktop and 390px widths.

---

## 5. Environment Variables

```bash
export STUDIOSAAS_DATABASE_URL="postgresql://localhost/studiosaas_local_test"
export STUDIOSAAS_ENV="local"
export PORT="8899"
export STUDIOSAAS_API_KEY="independent-random-secret-at-least-32-characters"
export STUDIOSAAS_SESSION_SECRET="different-random-secret-at-least-32-characters"
export STUDIOSAAS_MEDIA_DIR="./media"
export CMS_DATA_DIR="/private/tmp/studiosaas_cms_data"
```

Production must not rely on local secret files (`backend/.api_secret`, `backend/.session_secret`, `backend/.cms_password` are local-only and git-ignored). Production startup requires independent API and session secrets and rejects equal values. See `docs/Release_Runbook.md` for the complete release configuration and gate.

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

# Reproducible source package (requires a clean committed tree)
bash scripts/package_release.sh

# Full local verification
bash backend/scripts/verify_local.sh

# Release gate: PostgreSQL checks may not be skipped
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh
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
| `docs/Release_Runbook.md` | Provider-neutral migration, media backfill, release, rollback, and recovery gate |
| `docs/Deployment.md` | Deployment: local → Cloudflare Tunnel (`studiosaas.cc.cd`) → AWS |
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

---

## 11. License

Copyright 2026 Lee Liu.

Licensed under the [Apache License, Version 2.0](LICENSE). See [NOTICE](NOTICE)
for attribution information.
