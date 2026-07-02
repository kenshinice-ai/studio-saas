# StudioSaaS

A multi-tenant SaaS platform for creative studios (painting, music, gaming). Built with **Python/FastAPI**, **PostgreSQL**, and static HTML/CSS/JS.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Documentation](#documentation)
- [Project Structure](#project-structure)
- [Default Credentials](#default-credentials)
- [Verification](#verification)
- [Roadmap](#roadmap)

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (Homebrew on macOS)
- Virtual environment (`.venv/`)

### Setup

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt

# 3. Ensure local Postgres is running
brew services start postgresql   # or: pg_ctl start

# 4. Create database (if not exists)
createdb studiosaas_local_test

# 5. Run schema migrations
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
  python scripts/run_migrations.py

# 6. Seed demo data (tenants, super admin, sample content)
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
  python scripts/seed_random_demo_data.py --students-per-tenant 24

# 7. Start the server
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
  STUDIOSAAS_DATA_DIR=/tmp/studiosaas_cms_data \
  PORT=8899 python backend/server.py
```

### Verify

```bash
# Health check
curl -sS http://localhost:8899/v1/health

# Pages (all 200)
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/cms
curl -sS -o /dev/null -w "%{http_code}" http://localhost:8899/lets-paint-studio/register
```

---

## Architecture

See [docs/Architecture.md](docs/Architecture.md) for full system diagrams, component descriptions, and data flow.

**Key components:**

- **`backend/server.py`** — FastAPI application entry point
- **`backend/studiosaas/api_v1.py`** — All API routes (v1)
- **`backend/studiosaas/auth.py`** — Authentication, session management, role checks
- **`backend/db/schema_v1.sql`** — Database schema definition
- **`super-admin.html`** — Platform-level admin interface
- **`tenant-template/`** — Base template replicated per tenant
- **`tenants/<slug>/`** — Tenant-specific static pages (CMS, register)
- **`legacy-root/`** — Legacy root pages (migration residue)

---

## Documentation

All project documentation lives in [docs/](docs/):

| Document | Purpose |
|---|---|
| [README.md](#readme) (this file) | Project overview and quick start |
| [docs/StudioSaaS_Blueprint_v2.md](docs/StudioSaaS_Blueprint_v2.md) | Product vision, features, and business model |
| [docs/Architecture.md](docs/Architecture.md) | System architecture and component diagrams |
| [docs/Development_Roadmap.md](docs/Development_Roadmap.md) | Phased development plan (P0–P2) |
| [docs/Current_Sprint.md](docs/Current_Sprint.md) | Active sprint tasks and blockers |
| [docs/Design_System.md](docs/Design_System.md) | Brand colors, typography, UI components |
| [docs/QA_Checklist.md](docs/QA_Checklist.md) | Pre-release verification checklist |
| [docs/API.md](docs/API.md) | Complete API reference |
| [docs/Database.md](docs/Database.md) | Schema reference and migration guide |
| [docs/Admin_Guide.md](docs/Admin_Guide.md) | Super admin and tenant admin operations |

---

## Project Structure

```
studiosaas/
├── README.md                    # This file
├── docs/                        # Documentation (single source of truth)
│   ├── Architecture.md
│   ├── API.md
│   ├── Admin_Guide.md
│   ├── Current_Sprint.md
│   ├── Database.md
│   ├── Design_System.md
│   ├── Development_Roadmap.md
│   ├── QA_Checklist.md
│   └── StudioSaaS_Blueprint_v2.md
├── docs/archive/                # Archived historical docs
├── backend/
│   ├── server.py                # FastAPI entry point
│   ├── studiosaas/
│   │   ├── api_v1.py            # All API routes
│   │   └── auth.py              # Auth & role checks
│   ├── db/
│   │   └── schema_v1.sql        # Database schema
│   └── scripts/                 # Migration & seed scripts
├── super-admin.html             # Platform admin UI
├── tenant-template/             # Per-tenant base template
│   ├── index.html
│   └── register.html
├── tenants/                     # Tenant-specific pages
│   ├── lets-paint-studio/
│   ├── lets-play-piano/
│   └── lets-play-game/
└── legacy-root/                 # Legacy root pages
```

---

## Default Credentials (Local)

### Super Admin

| Field | Value |
|---|---|
| Email | `admin@studiosaas.local` |
| Password | `admin123456` |

Reset command:

```bash
cd backend
STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test \
  python scripts/seed_super_admin.py --reset-password \
    --email admin@studiosaas.local --password admin123456
```

### Studio Admin (Demo Tenants)

| Tenant | Email | Password |
|---|---|---|
| `lets-paint-studio` | `owner@lets-paint-studio.test` | `admin123456` |
| `lets-play-piano` | `owner@lets-play-piano.test` | `admin123456` |
| `lets-play-game` | `owner@lets-play-game.test` | `admin123456` |

---

## Verification

```bash
# Full verification script
bash backend/scripts/verify_local.sh

# Syntax check
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py

# Legacy CMS smoke test (expected: 73 passing)
cd backend && ../.venv/bin/python test_cms.py

# API health
curl -sS http://localhost:8899/v1/health

# Auth flow test (see docs/Admin_Guide.md for full sequence)
```

---

## Roadmap

See [docs/Development_Roadmap.md](docs/Development_Roadmap.md) for the full phased plan including:

- **P0** — Critical fixes (route protection, schema mismatches, runtime errors)
- **P1** — Important fixes (tenant isolation, migrations, media upload)
- **P2** — Improvements (code splitting, test suite, documentation)

---

## Archived Documentation

Historical documents, fix records, and sprint retrospectives are archived in [docs/archive/](docs/archive/). These are preserved for reference but are not the single source of truth.
