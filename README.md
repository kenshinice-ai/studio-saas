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
- Platform dashboard:
  - `/`
  - `/super-admin`
- Tenant CMS routes:
  - `/lets-paint-studio`
  - `/lets-play-piano`
  - `/<tenant_slug>/studio-admin`
  - `/<tenant_slug>/register`
- Routing and file layout: `TENANT_ROUTING_AND_STRUCTURE.md`

## Local Verification

```bash
cd letspaint-cms-release
python3 test_cms.py
```

The legacy smoke test remains the safety net while the SaaS layer is introduced.

## AWS Direction

The planned production direction is Flask/Waitress on AWS, PostgreSQL on RDS,
and uploaded media on S3. Early deployments can continue from the current
Lightsail workflow while data is migrated toward the v1 schema.
