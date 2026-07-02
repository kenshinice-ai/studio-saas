# StudioSaaS

StudioSaaS is a multi-tenant SaaS refactor of the existing Let's Paint CMS.
The product is designed for small creative education studios that need student
management, credit tracking, registration, branded parent portals, and student
portfolio workflows.

## Current Status

- Backend runtime: `backend/`
- Product blueprint: `StudioSaaS_MVP_Blueprint_v1.md`
- PostgreSQL schema v1: `backend/db/schema_v1.sql`
- StudioSaaS API v1 foundation: `backend/studiosaas/`
- Product root: `/Users/llmacbookpro/Documents/studiosaas/`
- Backend/runtime package: `backend/`
- Runtime legacy bridge shells: `legacy-root/`
- Platform dashboard at the project root:
  - `/`
  - `/super-admin`
- Tenant templates: `tenant-template/`
- Generated tenant folders: `tenants/<tenant_slug>/`
- Archived non-runtime references: `archive/`
- File-level fallback checkpoints: `checkpoints/`
- Random relational UI seed script: `backend/scripts/seed_random_demo_data.py`
- Local startup shortcut: `start_studiosaas_local.sh`
- Tenant CMS routes:
  - `/lets-paint-studio`
  - `/lets-play-piano`
  - `/lets-play-game`
  - `/<tenant_slug>/studio-admin`
  - `/<tenant_slug>/register`
- Root `/register` is intentionally closed; registration belongs to each tenant.
- Routing and file layout: `TENANT_ROUTING_AND_STRUCTURE.md`
- Latest Studio Admin/CMS sync fixes: `STUDIOSAAS_FIX_SYNC_CHECKLIST.md`

## Directory Strategy

`backend/` is now the canonical runtime directory. The previous
`letspaint-cms-release/` tree has been superseded by the root-level product
layout plus `backend/`.

`legacy-root/` remains a runtime bridge, not an archive. The tenant wrappers use
it to host the old CMS/Register UI while request interception routes data into
tenant-scoped PostgreSQL APIs.

## Local Verification

### Quick verification (recommended)

```bash
bash backend/scripts/verify_local.sh
```

This script checks Python version, validates `requirements.txt`, runs
`py_compile` on all source files, executes the legacy smoke test, and
optionally runs tenant isolation tests when PostgreSQL is available.

### Legacy smoke test (direct)

```bash
cd backend
../.venv/bin/python test_cms.py
```

The legacy smoke test remains the safety net while the SaaS layer is introduced.
Current expected result: 73 checks passing, 0 failing.

## Git Checkpoints

The current Codex sandbox can edit project files but cannot write inside
`.git/`, so `git add` and `git commit` fail when Git tries to create
`.git/index.lock`. This is a filesystem permission boundary, not a stale lock
file.

Until `.git/` write access is available, fallback checkpoints are stored as
patch and status files in `checkpoints/`.

## AWS Direction

The planned production direction is Flask/Waitress on AWS, PostgreSQL on RDS,
and uploaded media on S3. Early deployments can continue from the current
Lightsail workflow while data is migrated toward the v1 schema.
