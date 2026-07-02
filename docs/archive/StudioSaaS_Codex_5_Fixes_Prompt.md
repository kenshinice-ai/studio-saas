# StudioSaaS Codex CLI Prompt — 5 Focused Fixes

You are working on the StudioSaaS codebase. Keep scope tight. Make only the 5 changes below, then run the verification commands. Do not redesign the whole system.

## Context

The project is a Flask-based multi-tenant SaaS refactor of the legacy Let's Paint CMS.

Canonical runtime:
- `backend/server.py`
- `backend/studiosaas/`
- `backend/db/schema_v1.sql`
- tenant pages in `tenants/<tenant_slug>/`
- legacy bridge pages in `legacy-root/`

Current intended routes:
- root platform: `/`, `/super-admin`
- tenant CMS: `/<tenant_slug>/cms`
- tenant register: `/<tenant_slug>/register`
- v1 API: `/v1/...`
- tenant-prefixed API: `/s/<tenant_slug>/v1/...`

## Fix 1 — Repair v1 auth/session and tenant membership checks

Problem:
- `backend/studiosaas/auth.py` has confusing tenant resolution inside `auth_required()` and resets the resolved tenant id to `None`, so tenant-scoped auth can fall back to any active membership.
- Super-admin routes are protected only by `@auth_required`, not a role/permission check.
- The tenant admin UI may need `credentials: 'include'` consistently for Flask session cookies.

Required changes:
1. Refactor `auth_required()` and `permission_required()` so they resolve the requested tenant slug into a real tenant id when present.
2. Do not allow an owner/staff member from tenant A to mutate tenant B by changing `X-Tenant-Slug`.
3. Allow `super_admin` to access all tenants.
4. Add explicit permission decorators to super-admin mutation/listing routes in `backend/studiosaas/api_v1.py`:
   - `/admin/tenants`
   - `/admin/usage`
   - `/admin/audit-logs`
   - `/plans` writes
5. Ensure `backend/frontend/studio-admin.html` API calls include `credentials: 'include'`.

Acceptance criteria:
- Unauthenticated protected v1 routes return 401.
- Non-member access to another tenant returns 403.
- Super admin can list and mutate tenants.
- Tenant owner can mutate only their own tenant.

## Fix 2 — Make legacy bridge auth work cleanly with tenant-prefixed save

Problem:
- `legacy-root/index.html` rewrites `/api/data` and `/api/save` to `/s/<tenant_slug>/v1/legacy-cms/...`.
- `/legacy-cms/save` is protected by v1 `@auth_required`, but the legacy login uses `/api/login` and its old session/password flow, not `/v1/auth/login`.
- This can make the tenant CMS look like it loads but fail when saving.

Required changes:
1. Decide on one supported compatibility path:
   - either make the legacy bridge login use `/v1/auth/login`, or
   - provide a safe compatibility adapter that accepts the existing legacy session only for the resolved tenant and only for legacy CMS save.
2. Do not remove the existing legacy smoke-test endpoints.
3. Add a clear user-facing save error in `legacy-root/index.html` when tenant save returns 401/403.
4. Keep `/api/save` legacy single-studio behaviour intact for the old smoke test.

Acceptance criteria:
- `/<tenant_slug>/cms` can load tenant data and save a small edit through `/s/<tenant_slug>/v1/legacy-cms/save`.
- Saving without a valid session fails with 401/403.
- Legacy `/api/data` and `/api/save` smoke-test path still works.

## Fix 3 — Fix public registration, balance query, and tests route mismatch

Problem:
- Public endpoints currently live at `/v1/public/<tenant_slug>/registrations` and `/v1/public/<tenant_slug>/balance-query`.
- `backend/test_tenant_isolation.py` calls a wrong path/method for balance, e.g. `GET /s/test-tenant-a/v1/public/test-tenant-a/balance`.
- `legacy-root/register.html` rewrites old `/api/register` and `/api/balance` to the newer public endpoints.

Required changes:
1. Update `backend/test_tenant_isolation.py` to use the real public endpoints:
   - `POST /v1/public/<tenant_slug>/registrations`
   - `POST /v1/public/<tenant_slug>/balance-query`
2. Add tests that prove tenant A cannot find tenant B's student by name/mobile.
3. Keep `legacy-root/register.html` fetch rewrite aligned to the canonical endpoints.
4. Improve returned JSON consistency for public registration and balance query, using `ok` plus existing compatibility fields where needed.

Acceptance criteria:
- Public register page can submit to the selected tenant.
- Balance lookup only returns a student from the same tenant.
- The isolation test no longer uses a non-existent route.

## Fix 4 — Harden local verification and dependency setup

Problem:
- `pytest -q backend` fails in a clean environment when Flask is missing and `test_cms.py` exits during pytest collection.
- `README.md` says the smoke test expects 73 checks, but the current test strategy now includes both legacy and tenant isolation checks.

Required changes:
1. Add `backend/pytest.ini` or root `pytest.ini` to prevent script-style smoke tests from being collected as normal pytest modules, or convert them into safe pytest tests without import-time side effects.
2. Add a simple `backend/scripts/verify_local.sh` that:
   - checks Python version,
   - installs/validates `backend/requirements.txt` in the active venv,
   - runs `python -m py_compile backend/server.py backend/studiosaas/*.py`,
   - runs `python backend/test_cms.py`,
   - optionally runs `python backend/test_tenant_isolation.py` only when PostgreSQL env/config is available.
3. Update `README.md` local verification section to use this script.

Acceptance criteria:
- `python -m py_compile backend/server.py backend/studiosaas/*.py` passes.
- `pytest -q` no longer accidentally starts servers at import time.
- A developer has one reliable command to verify local changes.

## Fix 5 — Clean project artefacts and protect secrets from packaging

Problem:
- The archive contains `__MACOSX`, `.DS_Store`, `__pycache__`, backup HTML files, `.api_secret`, `.cms_password`, and checkpoint artefacts.
- These are not appropriate for production packaging or Codex handoff.

Required changes:
1. Add/update `.gitignore` for:
   - `__MACOSX/`
   - `.DS_Store`
   - `__pycache__/`
   - `*.pyc`
   - `*.bak*`
   - `.api_secret`
   - `.cms_password`
   - local database/backups/photos where applicable
   - `checkpoints/` unless intentionally tracked
2. Add `scripts/package_clean.sh` or `backend/scripts/package_clean.sh` to create a clean zip excluding secrets, caches, Mac metadata, and backups.
3. Update `README.md` with a short “safe handoff package” command.
4. Do not delete required runtime assets such as logos, icons, tenant templates, or vendor JS files.

Acceptance criteria:
- Clean package excludes secrets and cache/backup artefacts.
- Runtime still starts locally after packaging.
- Tenant pages and vendor assets are still present.

## Verification commands

Run these after changes:

```bash
python -m py_compile backend/server.py backend/studiosaas/*.py
bash backend/scripts/verify_local.sh
```

If PostgreSQL is configured and seeded:

```bash
python backend/scripts/seed_super_admin.py
python backend/scripts/seed_local_test_tenants.py
python backend/test_tenant_isolation.py
```

## Final response required from Codex

Return only:
1. files changed,
2. summary of each of the 5 fixes,
3. verification results,
4. any remaining blockers.
