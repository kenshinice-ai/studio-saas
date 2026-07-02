# StudioSaaS Codex Executable Tasks v1

用途：把代码级审查结果拆成可直接交给 Codex 的任务。  
规则：一次只做一个任务；每个任务必须给出 changed files、tests run、remaining risks。

---

## Global Codex Rules

```text
You are working on StudioSaaS.
Do not redesign the whole project.
Keep backend/ as canonical runtime.
Keep legacy-root/ bridge working until new frontend fully replaces it.
Do not expose root /register.
Do not remove existing legacy smoke tests.
Every tenant-level API must resolve tenant from path/header/host, not request body.
Every mutation route must be authenticated unless explicitly public.
Every change must include or update tests.
Run syntax checks after each task.
```

Required final response from Codex after each task:

```text
Changed files:
Tests run:
Result:
Known risks:
Next recommended task:
```

---

# Task 0 — Repository Hygiene and Secret Cleanup

## Goal

Remove runtime secrets and macOS/generated junk from source control readiness.

## Files

```text
.gitignore
backend/.api_secret
backend/.cms_password
.DS_Store
__MACOSX/
backend/__pycache__/
```

## Instructions

1. Create `.gitignore` at project root.
2. Ignore:

```gitignore
__MACOSX/
.DS_Store
*.pyc
__pycache__/
.venv/
backend/.api_secret
backend/.cms_password
backend/.cms_config.json
backend/database.json
backend/backups/
backend/photos/
backend/portfolio/
backend/static/uploads/
checkpoints/*.tgz
```

3. Do not delete local runtime files automatically in user’s real working copy unless explicitly asked. Instead, document cleanup commands.
4. Add `SECURITY_LOCAL_SECRETS.md` explaining how to regenerate `.api_secret` and password.

## Acceptance

- `.gitignore` exists.
- Future zip/git export excludes secrets and generated files.
- Documentation explains secret regeneration.

## Test

```bash
git status --ignored
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py
```

---

# Task 1 — Fix v1 Auth Login and Seed Local Super Admin

## Goal

Make `/v1/auth/login`, `/v1/auth/logout`, `/v1/auth/me` actually usable.

## Files

```text
backend/studiosaas/api_v1.py
backend/scripts/seed_random_demo_data.py
backend/scripts/seed_local_test_tenants.py
backend/tests/test_auth.py
backend/db/schema_v1.sql or migration file
```

## Required fixes

1. Change login query to include `email` and `password_hash`:

```sql
SELECT id, email, full_name, status, password_hash FROM users WHERE email = %s
```

2. Use one canonical password hashing scheme.
3. Avoid silent SHA-256 fallback for new users; allow only for legacy local seed if clearly marked.
4. Seed local admin user:

```text
email: admin@studiosaas.local
password: change-me-local-only
role: super_admin
```

5. Return user and memberships correctly.
6. Add rate limiting to auth login.

## Acceptance

- Wrong password returns 401.
- Correct local admin password returns ok.
- `/v1/auth/me` returns user + membership/role.
- Password hash is never returned.

## Test

```bash
../.venv/bin/python -m pytest backend/tests/test_auth.py
```

---

# Task 2 — Add Route Protection for v1 Admin and Tenant Mutations

## Goal

Prevent unauthenticated mutation of platform and tenant data.

## Files

```text
backend/studiosaas/auth.py
backend/studiosaas/api_v1.py
backend/tests/test_authz.py
```

## Implement

Create helpers:

```python
load_actor_from_session()
require_login()
require_platform_admin()
require_tenant_role(*roles)
```

Protect:

```text
/v1/admin/*
/v1/plans POST/PATCH/DELETE
/v1/tenant PATCH
/v1/tenant/settings PATCH
/v1/tenant/logo POST
/v1/students POST/PATCH/archive
/v1/courses POST/PATCH/DELETE
/v1/packages POST/PATCH/DELETE
/v1/students/<id>/credit-transactions POST
/v1/portfolio POST/PATCH/DELETE
/v1/legacy-cms/save
```

Keep public:

```text
GET /v1/health
GET /v1/public/<slug>/brand
POST /v1/public/<slug>/registrations
POST /v1/public/<slug>/balance-query
```

## Acceptance

- Unauthenticated mutation returns 401.
- Wrong-tenant user returns 403.
- Super admin can access platform routes.
- Studio owner/admin can access own tenant routes.
- Public brand/register/balance still work.

## Test

```bash
../.venv/bin/python -m pytest backend/tests/test_authz.py
```

---

# Task 3 — Fix Credit Transaction Schema Mismatch

## Goal

Align transaction type vocabulary across schema, API, UI and tests.

## Files

```text
backend/db/schema_v1.sql or backend/db/migrations/0002_credit_transactions.sql
backend/studiosaas/api_v1.py
backend/frontend/studio-admin.html
backend/tests/test_credit_transactions.py
```

## Preferred model

Use schema values:

```text
purchase
consume
adjustment
refund
expire
migration
```

Map UI/API input:

```text
debit -> consume
adjustment_in -> adjustment with positive amount
adjustment_out -> adjustment with negative amount or adjustment with metadata.direction
```

## Acceptance

- Purchase increases balance.
- Consume decreases balance.
- Adjustment can increase/decrease balance.
- Refund decreases balance.
- Invalid type returns 400 before DB.
- No CHECK constraint failures.

## Test

```bash
../.venv/bin/python -m pytest backend/tests/test_credit_transactions.py
```

---

# Task 4 — Fix dict_row Indexing Runtime Errors

## Goal

Replace tuple indexing with dict keys for psycopg `dict_row` results.

## Files

```text
backend/studiosaas/api_v1.py
backend/tests/test_students.py
backend/tests/test_credit_transactions.py
backend/tests/test_portfolio.py
```

## Replace

```text
cur.fetchone()[0]
row[0]
```

with:

```python
row = cur.fetchone()
row["id"]
row["balance"]
```

Known locations:

```text
api_v1.py:1623
api_v1.py:1737
api_v1.py:1762
api_v1.py:1834
```

## Acceptance

- Create student succeeds.
- Create credit transaction succeeds.
- Create portfolio item succeeds.

---

# Task 5 — Fix Credit Account Uniqueness and Upsert

## Goal

Make credit account model deterministic.

## Decision required

Choose one:

### Option A — default account per student

Add partial unique index for `course_id IS NULL`.

### Option B — General Class course account only

Always create/fetch a default `General Class` course and use `(tenant_id, student_id, course_id)`.

Recommended: Option B.

## Files

```text
backend/db/schema_v1.sql or migration
backend/studiosaas/api_v1.py
backend/tests/test_credit_accounts.py
```

## Acceptance

- No `ON CONFLICT` error.
- One student cannot accidentally get multiple default balance rows.
- Balance query returns deterministic balance.

---

# Task 6 — Fix By-Slug Portfolio DELETE Mapping

## Goal

Ensure `/s/<slug>/v1/portfolio/<id>` DELETE calls `delete_portfolio_item`.

## File

```text
backend/studiosaas/api_v1.py
```

## Fix

Change mapping from:

```python
("/portfolio/<portfolio_item_id>", update_portfolio_item, ["PATCH", "DELETE"])
```

to:

```python
("/portfolio/<portfolio_item_id>", update_portfolio_item, ["PATCH"]),
("/portfolio/<portfolio_item_id>", delete_portfolio_item, ["DELETE"]),
```

## Acceptance

- Base DELETE works.
- By-slug DELETE works.
- PATCH still works.

---

# Task 7 — Harden v1 Public Registration and Balance Query

## Goal

Bring v1 public endpoints up to the same safety level as legacy public endpoints.

## Files

```text
backend/studiosaas/api_v1.py
backend/tests/test_public_endpoints.py
```

## Add

- IP rate limit for balance query.
- IP rate limit for registration.
- Normalised duplicate detection by name + phone.
- Field length caps.
- JSON payload size guard.
- Audit log for accepted registrations.

## Acceptance

- Missing name/phone returns 400 or match false.
- Repeated balance queries trigger 429.
- Repeated registrations trigger 429.
- Duplicate pending registration detected.
- Existing student duplicate detected where safe.

---

# Task 8 — Add Tenant Isolation Test Suite

## Goal

Prove A tenant cannot read/write B tenant data.

## Files

```text
backend/tests/test_tenant_isolation.py
```

## Cases

- Student ID from tenant A requested under tenant B returns 404/403.
- Registration from A never appears in B.
- Course/package from A cannot be patched under B.
- Balance query under wrong tenant returns no match.
- Portfolio/media from A cannot be accessed under B.
- Body-supplied `tenant_id` is ignored.

## Acceptance

All tests pass.

---

# Task 9 — Add v1 Media Upload Endpoint

## Goal

Allow new Studio Admin to create portfolio assets without relying on legacy upload.

## Files

```text
backend/studiosaas/api_v1.py
backend/studiosaas/storage.py
backend/tests/test_media_upload.py
```

## Endpoint

```text
POST /s/<slug>/v1/media/upload
```

## Requirements

- Auth required.
- Tenant quota enforced.
- Extension/MIME/magic bytes validated.
- Storage key generated server-side.
- Metadata inserted into `media_assets`.
- Asset retrieval uses tenant scoped route or signed public token.

## Acceptance

- Valid image upload creates media asset.
- Fake image rejected.
- Oversized image rejected.
- Tenant A cannot read Tenant B media.

---

# Task 10 — Legacy Branding Residue Cleanup

## Goal

Make non-Let’s Paint tenants feel native, not reskinned.

## Files

```text
legacy-root/index.html
legacy-root/register.html
tenant-template/index.html
tenant-template/register.html
```

## Replace visible hard-coded strings

Examples:

```text
Let's Paint CMS
Let's Paint
LetsPaint_Students
Let's Paint 感谢您的支持
Let's Paint 全体老师祝您生日快乐
```

Use:

```javascript
window.STUDIOSAAS_BRAND.name
window.STUDIOSAAS_BRAND.shortName || 'Studio'
```

## Acceptance

- `lets-play-piano` page does not visibly say Let’s Paint.
- Download filenames use tenant slug/name.
- SMS/report templates use tenant name.
- Apostrophes in tenant names do not break JS.

---

# Task 11 — Migration Runner

## Goal

Stop treating `schema_v1.sql` as both full bootstrap and patch history.

## Files

```text
backend/scripts/run_migrations.py
backend/db/migrations/*.sql
backend/db/schema_v1.sql
```

## Add

```sql
CREATE TABLE IF NOT EXISTS schema_migrations (
  version text PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);
```

## Acceptance

- Fresh DB bootstrap works.
- Existing DB migration works.
- Re-running is safe.

---

# Task 12 — Browser Smoke Test

## Goal

Catch UI regressions on tenant pages.

## Files

```text
backend/tests/browser_smoke.py
TESTING_STRATEGY.md
```

## Pages

```text
/
/super-admin
/studio-admin
/lets-paint-studio
/lets-paint-studio/register
/lets-paint-studio/studio-admin
/lets-play-piano
/lets-play-piano/register
```

## Acceptance

- Pages return 200.
- No root `/register` CTA.
- Tenant name visible.
- Registration form visible.
- Mobile viewport has no severe horizontal overflow.

---

# Suggested First Codex Prompt

Use `StudioSaaS_Codex_P0_Fix_Prompt.md` first.
