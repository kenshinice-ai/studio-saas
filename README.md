# StudioSaaS

StudioSaaS is a multi-tenant SaaS refactor of the existing Let's Paint CMS.
The product is designed for small creative education studios that need student
management, credit tracking, registration, branded parent portals, and student
portfolio workflows.

## Current Status

- Legacy prototype checkpoint: `letspaint-cms-release/`
- Product blueprint: `StudioSaaS_MVP_Blueprint_v1.md`
- PostgreSQL schema v1: `letspaint-cms-release/db/schema_v1.sql`
- StudioSaaS API v1 foundation: `letspaint-cms-release/studiosaas/`
- Product root: `/Users/llmacbookpro/Documents/studiosaas/`
- Backend/runtime package: `letspaint-cms-release/`
- Platform dashboard at the project root:
  - `/`
  - `/super-admin`
- Archived legacy single-tenant shells: `legacy-root/`
- Tenant templates: `tenant-template/`
- Generated tenant folders: `tenants/<tenant_slug>/`
- Archived non-runtime references and clutter: `archive/`
- File-level fallback checkpoints: `checkpoints/`
- Tenant CMS routes:
  - `/lets-paint-studio`
  - `/lets-play-piano`
  - `/<tenant_slug>/studio-admin`
  - `/<tenant_slug>/register`
- Root `/register` is intentionally closed; registration belongs to each tenant.
- `/parent-portal` is temporarily removed from active routing.
- Routing and file layout: `TENANT_ROUTING_AND_STRUCTURE.md`

## Local Verification

```bash
cd letspaint-cms-release
python3 test_cms.py
```

The legacy smoke test remains the safety net while the SaaS layer is introduced.

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
