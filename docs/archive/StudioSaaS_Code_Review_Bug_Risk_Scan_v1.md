# StudioSaaS Code-Level Review + Bug Risk Scan v1

日期：2026-07-01  
审查范围：用户上传的 `Archive.zip` 解压后的 StudioSaaS 项目。  
审查方式：静态代码审查、结构扫描、关键路径阅读、Python syntax compile。  
未完成项：未能完整运行 `backend/test_cms.py`，因为当前 sandbox 没有安装 Flask 依赖；`python3 -m py_compile` 已通过。

---

## 1. Executive Summary

项目方向是对的：你已经把原本单工作室 Let’s Paint CMS 拆出了 SaaS 形态，包括：

- `backend/` 作为 canonical runtime。
- `legacy-root/` 作为旧 CMS/Register bridge。
- `tenant-template/` + `tenants/<slug>/` 作为租户 wrapper。
- PostgreSQL schema v1。
- `/v1` API 和 `/s/<tenant_slug>/v1` tenant-scoped API。
- Super Admin、Studio Admin、CMS/Register 三层入口。

但目前代码还没有达到“可给真实客户安全试点”的程度。最大风险不是 UI，而是：

1. v1 API 管理端几乎没有真正接入权限校验。
2. v1 auth login 当前有明显 bug，登录流程不可用。
3. credit transaction 代码与 schema CHECK constraint 不一致。
4. `dict_row` cursor 被当成 tuple 使用，多个 POST endpoint 会运行时报错。
5. `credit_accounts` 的 `ON CONFLICT` 与数据库唯一约束不一致。
6. legacy bridge 的 `/legacy-cms/save` 可被 tenant context 调用，但没有 admin auth gate。
7. `public balance query` 没有限流、重复提交控制和强隐私保护。
8. 项目包里包含 `.api_secret` 和 `.cms_password`，上线前必须清理并加入 `.gitignore`。

结论：当前适合继续本地开发与 demo，但不建议直接 AWS 上线给真实试点客户。

---

## 2. What I Verified

### 2.1 File structure verified

核心文件存在：

```text
backend/server.py
backend/studiosaas/api_v1.py
backend/studiosaas/auth.py
backend/studiosaas/db.py
backend/studiosaas/tenant_context.py
backend/studiosaas/workspaces.py
backend/db/schema_v1.sql
backend/test_cms.py
super-admin.html
backend/frontend/studio-admin.html
legacy-root/index.html
legacy-root/register.html
tenant-template/index.html
tenant-template/register.html
tenants/lets-paint-studio/*
tenants/lets-play-piano/*
tenants/lets-play-game/*
start_studiosaas_local.sh
```

### 2.2 Syntax check

Passed:

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py backend/test_cms.py
```

### 2.3 Smoke test attempt

Attempted:

```bash
cd backend
python3 test_cms.py
```

Result:

```text
ModuleNotFoundError: No module named 'flask'
```

This is an environment dependency issue in the review sandbox, not proof that the code test fails on your Mac. On your machine, run it inside `.venv`:

```bash
cd /Users/llmacbookpro/Documents/studiosaas/backend
../.venv/bin/python test_cms.py
```

---

## 3. Architecture Assessment

### 3.1 Strong points

| Area | Assessment |
|---|---|
| Direction | Correct transition from single CMS to multi-tenant SaaS. |
| Routing | `/<tenant_slug>`, `/<tenant_slug>/register`, `/s/<slug>/v1/*` is a practical bridge strategy. |
| Data model | PostgreSQL schema has most required entities: tenants, plans, students, courses, packages, credits, registrations, media, portfolio, audit. |
| Local dev | `start_studiosaas_local.sh` is useful and close to one-click local bootstrap. |
| Legacy safety | Existing `server.py` has many mature legacy protections: rate limiting, PBKDF2 migration, magic-byte checks, static allowlist, backup guard. |
| Workspace generation | `workspaces.py` has reserved slug validation and safe tenant folder generation. |

### 3.2 Weak points

| Area | Issue |
|---|---|
| Auth | `auth.py` is mostly a placeholder; v1 route protection is not wired. |
| Admin API | Super Admin and Studio Admin mutations appear callable without role check. |
| DB integrity | Some app-level assumptions are not enforced by schema constraints. |
| Runtime bugs | Several v1 POST endpoints use tuple indexing on dict rows. |
| Credit logic | API transaction names do not match schema CHECK values. |
| Privacy | Parent balance query is public, not rate-limited in v1, and returns balance from an arbitrary account row. |
| Legacy residue | `legacy-root/index.html` still has many visible “Let’s Paint” strings. |
| Repository hygiene | `.api_secret`, `.cms_password`, `.DS_Store`, `__MACOSX`, `__pycache__` included. |

---

## 4. Critical Bugs and Risks

## P0-01 — v1 Auth Login is broken

File:

```text
backend/studiosaas/api_v1.py:1916-1921
```

Observed issue:

```python
SELECT id, full_name, status FROM users WHERE email = %s
...
expected_hash = user["password_hash"]
```

The query does not select `password_hash`, but the code reads `user["password_hash"]`. This will raise a runtime error on successful user lookup.

Impact:

- `/v1/auth/login` cannot work reliably.
- Studio Admin/Super Admin cannot be secured through the new auth layer yet.

Fix:

```sql
SELECT id, email, full_name, status, password_hash FROM users WHERE email = %s
```

Also seed at least one local Super Admin user.

---

## P0-02 — v1 Admin and tenant mutation APIs are not protected

Files:

```text
backend/studiosaas/api_v1.py
backend/studiosaas/auth.py
```

Examples:

```text
PATCH /v1/tenant
POST /v1/courses
PATCH /v1/courses/<course_id>
POST /v1/packages
POST /v1/students
POST /v1/students/<student_id>/credit-transactions
POST /v1/admin/tenants
PATCH /v1/admin/tenants/<tenant_id>
POST /v1/tenant/logo
POST /v1/legacy-cms/save
```

`auth.py` says the permission decorator is a placeholder and returns `501` if used. The actual API functions do not use it.

Impact:

- Anyone who can reach local/staging API and knows a tenant slug/header could mutate tenant data.
- Super Admin tenant creation/update/delete endpoints are exposed.
- This is the biggest blocker before any real pilot.

Fix:

- Implement session-backed `load_actor()`.
- Add `@require_platform_admin` to `/v1/admin/*` and `/v1/plans*` mutations.
- Add `@require_tenant_role("owner", "studio_admin")` to tenant settings, students, courses, packages, credits, portfolio, legacy save.
- Keep only public brand, public registration, and public balance as unauthenticated.

---

## P0-03 — Credit transaction values do not match schema

Schema:

```text
backend/db/schema_v1.sql
```

Allowed values:

```sql
('purchase', 'consume', 'adjustment', 'refund', 'expire', 'migration')
```

Code inserts:

```text
backend/studiosaas/api_v1.py:1696
purchase, debit, adjustment_in, adjustment_out, refund
```

And:

```text
backend/studiosaas/api_v1.py:2121
adjustment_in / adjustment_out
```

Impact:

- Credit transaction POST and student balance update will violate database CHECK constraint.
- Studio Admin balance updates may fail at runtime.

Fix options:

Preferred:

```text
purchase -> purchase
consume/debit -> consume
adjustment_in / adjustment_out -> adjustment with signed amount
refund -> refund
expire -> expire
migration -> migration
```

Or expand schema CHECK, but keep one canonical vocabulary across code, schema, UI, docs.

---

## P0-04 — `dict_row` cursor is being indexed like tuple

The DB connection uses:

```text
psycopg.rows.dict_row
```

So `cur.fetchone()` returns a dict-like row. But code uses tuple indexing:

```text
backend/studiosaas/api_v1.py:1623  cur.fetchone()[0]
backend/studiosaas/api_v1.py:1737  row[0]
backend/studiosaas/api_v1.py:1762  cur.fetchone()[0]
backend/studiosaas/api_v1.py:1834  cur.fetchone()[0]
```

Impact:

- Student creation, credit transaction creation, portfolio creation likely fail at runtime.

Fix:

Use aliases:

```sql
RETURNING id
```

Then:

```python
row = cur.fetchone()
student_id = str(row["id"])
```

For balance:

```python
current_balance = float(row["balance"]) if row else 0.0
```

---

## P0-05 — `ON CONFLICT (tenant_id, student_id)` does not match schema

Schema defines:

```sql
UNIQUE (tenant_id, student_id, course_id)
```

But code uses:

```text
backend/studiosaas/api_v1.py:1768
ON CONFLICT (tenant_id, student_id) DO UPDATE

backend/studiosaas/api_v1.py:2136
ON CONFLICT (tenant_id, student_id) DO UPDATE
```

There is no unique constraint on `(tenant_id, student_id)`. PostgreSQL will reject this.

Also, because `course_id` is nullable, `UNIQUE (tenant_id, student_id, course_id)` still allows multiple NULL course rows in PostgreSQL.

Impact:

- Credit account upsert can fail.
- A student can accidentally end up with multiple default credit accounts.
- Balance query may return arbitrary account row.

Fix:

Choose one model:

### Option A — One default account per student for MVP

Add partial unique index:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_accounts_tenant_student_default
ON credit_accounts(tenant_id, student_id)
WHERE course_id IS NULL;
```

Then use:

```sql
ON CONFLICT (tenant_id, student_id) WHERE course_id IS NULL DO UPDATE ...
```

### Option B — Course-specific balance only

Always require `course_id`, including legacy General Class, and never create NULL-course accounts.

For MVP, Option B is cleaner because legacy already creates `General Class`.

---

## P0-06 — Wrong DELETE binding for by-slug portfolio route

File:

```text
backend/studiosaas/api_v1.py:2205
```

Current mapping:

```python
("/portfolio/<portfolio_item_id>", update_portfolio_item, ["PATCH", "DELETE"])
```

There is a separate `delete_portfolio_item()` function, but by-slug DELETE is incorrectly mapped to update.

Impact:

- `DELETE /s/<slug>/v1/portfolio/<id>` will call the update function and likely require JSON payload instead of deleting.

Fix:

Split mapping:

```python
("/portfolio/<portfolio_item_id>", update_portfolio_item, ["PATCH"]),
("/portfolio/<portfolio_item_id>", delete_portfolio_item, ["DELETE"]),
```

---

## P0-07 — v1 public endpoints lack rate limiting and duplicate protection

Files:

```text
backend/studiosaas/api_v1.py:830-909
```

Issues:

- `public_balance_query` has no rate limiting.
- `public_create_registration` has no rate limiting.
- `public_create_registration` has no duplicate detection.
- Registration message/payload lengths are not capped.

The legacy endpoints in `server.py` have better protections, but the new v1 public surface does not yet inherit them.

Impact:

- Name + phone enumeration risk.
- Registration flooding risk.
- Oversized JSON payloads can bloat DB.

Fix:

Port legacy rate-limit helpers or create v1 middleware:

```text
balance query: 10/min/IP
registration: 5/min/IP
payload max length caps
pending duplicate check by normalised name + phone
```

---

## P0-08 — Secrets and generated system files included in archive

Found:

```text
backend/.api_secret
backend/.cms_password
.DS_Store
__MACOSX/
backend/__pycache__/
```

Impact:

- If these are committed or shared, local session signing/API key/password hash leaks.
- Poor deployment hygiene.

Fix:

Create `.gitignore` immediately:

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

Regenerate local secrets after cleanup.

---

## P1 Issues

### P1-01 — `public_balance_query` joins credit accounts without tenant/account rule

File:

```text
backend/studiosaas/api_v1.py:844-847
```

Current:

```sql
LEFT JOIN credit_accounts ca ON ca.student_id = s.id
WHERE s.tenant_id = %s
```

Better:

```sql
LEFT JOIN credit_accounts ca
  ON ca.tenant_id = s.tenant_id
 AND ca.student_id = s.id
```

Also decide whether to return:

- one default account balance, or
- sum of active course balances, or
- list of balances by course.

---

### P1-02 — Cross-tenant integrity is mostly app-level, not DB-level

Schema has `tenant_id` on most tables, but foreign keys do not enforce that related records belong to the same tenant.

Examples:

```text
packages.course_id -> courses.id
credit_accounts.student_id -> students.id
credit_accounts.course_id -> courses.id
portfolio_items.student_id -> students.id
portfolio_items.media_asset_id -> media_assets.id
```

Because UUIDs are globally unique this is low probability, but for SaaS data safety, add composite unique keys and composite FKs or enforce via service-layer helper.

---

### P1-03 — Hard delete used for courses, packages, portfolio

Files:

```text
backend/studiosaas/api_v1.py:585
backend/studiosaas/api_v1.py:698
backend/studiosaas/api_v1.py:1888
```

Current code hard deletes courses/packages/portfolio items. For auditability and customer recovery, prefer soft delete/status flags:

```text
courses.is_active = false
packages.is_active = false
portfolio_items.visibility = private OR deleted_at timestamp
```

---

### P1-04 — Legacy CMS save has no optimistic locking or shrink guard

Legacy `/api/save` has mature `rev` and shrink guards. v1 `/legacy-cms/save` accepts posted students/packages and writes them back without equivalent protection.

Impact:

- If two admins use legacy CMS wrapper concurrently, last write wins.
- Accidental mass archive/update risk.

Fix:

- Add `rev` check or server-side audit snapshot.
- Add shrink guard for large student count drops.
- Require authenticated tenant admin.

---

### P1-05 — v1 portfolio has no media upload endpoint

`create_portfolio_item()` requires `mediaAssetId`, but there is no clear v1 media upload endpoint for portfolio assets.

Impact:

- New Studio Admin cannot fully replace legacy portfolio upload.

Fix:

Add:

```text
POST /s/<slug>/v1/media/upload
GET  /s/<slug>/v1/media/<asset_id>
```

with tenant quota, magic-byte validation, metadata insert, and private/public-token access rules.

---

### P1-06 — Legacy branding residue remains high

Examples found in:

```text
legacy-root/index.html
legacy-root/register.html
```

Visible strings include:

```text
Let's Paint CMS
Let's Paint
LetsPaint_Students
Let's Paint 感谢您的支持
Let's Paint 全体老师祝您生日快乐
```

Impact:

- Non-Let’s Paint tenants will still feel like reskinned legacy Let’s Paint.

Fix:

Extract `studioBrand.name` and `studioBrand.shortName` from public brand payload and replace user-facing strings.

---

## 5. P2 Improvements

### P2-01 — Split `api_v1.py`

`backend/studiosaas/api_v1.py` is 2,200+ lines. It should be split before it becomes unmaintainable.

Recommended structure:

```text
backend/studiosaas/routes/
  health.py
  tenant.py
  public.py
  students.py
  courses.py
  packages.py
  credits.py
  portfolio.py
  media.py
  super_admin.py
  legacy_bridge.py
  auth.py
backend/studiosaas/services/
  tenant_service.py
  credit_service.py
  registration_service.py
  media_service.py
  auth_service.py
```

### P2-02 — Add tests by behaviour, not by file

Recommended test folders:

```text
backend/tests/
  test_auth.py
  test_tenant_isolation.py
  test_credit_transactions.py
  test_public_endpoints.py
  test_media_uploads.py
  test_super_admin.py
  test_legacy_bridge.py
```

### P2-03 — Add migration runner

Current `schema_v1.sql` is both schema bootstrap and incremental alter script. Add migrations:

```text
backend/db/migrations/
  0001_schema_v1.sql
  0002_credit_account_constraints.sql
  0003_auth_seed_and_roles.sql
  0004_tenant_presentation_backfill.sql
```

### P2-04 — Improve README for new developer/Codex

Add:

- install dependencies
- local DB setup
- run local app
- run tests
- reset demo DB
- generate tenant
- common failure fixes

---

## 6. Recommended Immediate Fix Order

Do not let Codex fix everything at once. Use this order:

```text
1. Repository hygiene and .gitignore
2. v1 auth login bug + seed super admin
3. route protection decorators for admin/studio mutations
4. credit transaction schema/code alignment
5. dict_row indexing fixes
6. credit account unique/upsert fix
7. by-slug portfolio DELETE mapping fix
8. v1 public rate limit + duplicate registration check
9. tenant isolation tests
10. legacy branding residue cleanup
```

---

## 7. Minimal Must-Pass Test List After P0 Fixes

```bash
cd /Users/llmacbookpro/Documents/studiosaas
./start_studiosaas_local.sh
```

In another terminal:

```bash
cd /Users/llmacbookpro/Documents/studiosaas/backend
../.venv/bin/python test_cms.py
../.venv/bin/python -m pytest tests
```

Manual API checks:

```bash
# Public OK
curl -sS http://localhost:8899/v1/health
curl -sS http://localhost:8899/v1/public/lets-paint-studio/brand

# Admin mutation without login must fail
curl -i -X POST http://localhost:8899/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad Tenant","slug":"bad-tenant","planCode":"starter"}'

# Tenant mutation without login must fail
curl -i -X PATCH http://localhost:8899/s/lets-paint-studio/v1/tenant \
  -H 'Content-Type: application/json' \
  -d '{"name":"Hacked"}'
```

Expected:

```text
401 or 403 for unauthenticated mutation routes.
```

---

## 8. Go/No-Go Recommendation

### Local demo

Go, after running dependency install and smoke tests.

### Internal family/team testing

Conditional go, after fixing P0-03, P0-04, P0-05 if you plan to use v1 Studio Admin for real data.

### External pilot customer

No-go until these are fixed:

- P0-01 Auth login bug
- P0-02 Route protection
- P0-03 Credit schema mismatch
- P0-04 dict_row runtime errors
- P0-05 credit account conflict bug
- P0-07 public endpoint rate limiting
- P0-08 secret cleanup

### AWS deployment

No-go for production. Staging only after P0 fixes and `.gitignore` cleanup.

---

## 9. Suggested Product Strategy After Code Fixes

Once P0/P1 are stable, the project should become a polished pilot product:

```text
Super Admin: create tenant, plan, pause/resume, usage, audit
Studio Admin: students, credits, registrations, branding, portfolio
Public Parent: registration, balance query, portfolio token
Legacy CMS: bridge only, gradually retired
```

The commercial edge should stay focused:

```text
Creative education studio SaaS
+ student/credit management
+ portfolio and parent portal
+ branded registration
+ semi-service setup model
```
