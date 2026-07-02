# StudioSaaS Codex Upgrade Masterplan v2

版本：v2.0  
日期：2026-07-01  
用途：作为下一轮交给 Codex 执行的项目改善蓝图、验收清单与重构优先级说明。  
项目状态判断：基础功能已经搭好，当前重点应从“能跑起来”转向“可维护、可测试、可部署、可商业化”。

---

## 0. 当前结论

StudioSaaS 当前已经不再是单纯的 Let’s Paint CMS，而是一个正在成形的多租户创意教育工作室 SaaS。现有文档已经明确了：

- 产品方向：面向小型创意教育工作室的学生、课时、注册、作品集、品牌化家长入口管理系统。
- 技术方向：PostgreSQL + 多租户 `tenant_id` 隔离 + `/v1` API + tenant wrapper + legacy CMS bridge。
- 本地运行方向：本地 PostgreSQL、随机 demo seed、`localhost:8899`、tenant path routing。
- 当前修复方向：Studio Admin 设置同步、tenant branding、legacy CMS/Register wrapper、logo 上传校验、移动端表格滚动等。
- 关键遗留方向：旧 CMS iframe 内部仍有历史品牌文案、vendor placeholder、浏览器自动化测试缺失、上传清理、server-side colour contrast 等。

下一阶段不要盲目扩功能。先把系统压实成“可重复测试、可安全部署、可稳定迁移、可维护开发”的 MVP+ 版本。

---

## 1. 项目定位再确认

### 1.1 不做什么

当前阶段不应该优先做：

- 原生 iOS App。
- 复杂排课系统。
- 完整财务会计系统。
- Stripe 全自动订阅账单。
- AI 作品点评。
- 每个工作室一套定制代码。
- 复杂多校区企业版权限。

### 1.2 当前阶段应该做什么

当前阶段应该优先完成：

1. 租户隔离和路由稳定。
2. 旧 CMS 到新 SaaS API 的桥接稳定。
3. PostgreSQL 数据模型与迁移脚本稳定。
4. Studio Admin 设置真正同步到 CMS/Register。
5. Super Admin 能可靠创建、管理、暂停 tenant。
6. 核心功能有自动化测试。
7. 本地到 AWS 的部署路径清晰。
8. 儿童照片、家长信息、学生数据具备基础隐私与安全保护。
9. UI 能在 desktop、iPad、mobile 三种场景稳定使用。
10. 文档、脚本、启动器、环境变量、seed data 可被 Codex 与人类重复执行。

---

## 2. 当前架构逻辑检查

### 2.1 正确的部分

当前架构方向总体正确：

- `backend/` 作为 canonical runtime，是正确的。
- `legacy-root/` 保留作为 bridge，而不是直接删除旧 CMS，是务实的。
- tenant folder 作为 wrapper 和 URL workspace，而 PostgreSQL 作为数据源，是合理的过渡架构。
- `/s/<tenant_slug>/v1/*` 作为 tenant-scoped API，非常适合本地和云端统一。
- root `/register` 关闭，要求使用 tenant URL，是正确的多租户边界。
- `tenant_id` 强制隔离是 SaaS 商业化的关键。
- 本地 smoke test 已经有 73 checks passing，是好的起点。

### 2.2 当前主要风险

| 风险 | 影响 | 当前应对 |
|---|---|---|
| legacy iframe 仍含旧品牌和旧逻辑 | 客户看到 Let’s Paint 残留，商业化感弱 | 继续抽离 legacy UI，逐步迁移到新 frontend |
| tenant 隔离测试不够强 | A tenant 数据泄露到 B tenant | 增加 cross-tenant negative tests |
| 上传文件只做基础校验 | 儿童照片和品牌资产有安全风险 | 增加 MIME、size、extension、magic bytes、path traversal 测试 |
| vendor placeholder | 离线部署不完整，AWS hardening 不足 | 固定 vendor bundles 或改为现代 bundled frontend |
| 旧 JSON CMS 仍可能影响逻辑 | 未来维护复杂 | 所有旧 `/api/*` 必须桥接到 `/v1`，并逐步移除 JSON 写入 |
| Super Admin 支持模式未完整设计 | 平台方可能看到儿童数据 | 增加 support mode + audit log |
| 缺少 browser automation | UI 改动容易破坏 mobile/iPad | 增加 Playwright 或 Selenium smoke |
| 缺少备份恢复演练 | AWS 上线风险高 | 增加 backup / restore runbook |

---

## 3. 下一阶段总目标：MVP+ Stabilisation

MVP+ 的定义不是加很多功能，而是让当前 MVP 能被 1-3 个真实试点工作室安全使用。

### 3.1 MVP+ 必须完成

- 本地启动脚本一键成功。
- schema 初始化、tenant seed、demo seed 可重复执行。
- 所有 tenant URL 可打开。
- Studio Admin 修改品牌、欢迎语、颜色、logo 后，CMS/Register 立即反映。
- legacy CMS 保存学生、课时、packages 后写入 PostgreSQL。
- Register 提交后进入正确 tenant 的 registrations。
- Parent balance query 只能查到本 tenant 数据。
- Super Admin 创建 tenant 后自动生成 workspace。
- tenant slug 不能与保留路径冲突。
- logo upload 拒绝伪造文件和过大文件。
- 所有核心 API 都有 tenant context。
- cross-tenant access 测试必须失败。
- 关键操作进入 audit log。
- AWS 前置文档完成，但不急于正式上线。

---

## 4. Codex 执行策略

### 4.1 开发原则

Codex 下一轮不要一次性大改。采用小步 commit：

1. 先跑本地启动与测试。
2. 每次只改一个模块。
3. 每次改完必须跑相关测试。
4. 改 legacy bridge 时同时验证 tenant wrapper。
5. 改 API 时同时更新 contract test。
6. 改 schema 时必须写 migration/backfill。
7. 不要为了美观破坏旧 CMS 可用性。
8. 不允许引入大依赖，除非写清楚原因。

### 4.2 Codex 每轮任务模板

```text
Task:
Improve StudioSaaS according to StudioSaaS_Codex_Upgrade_Masterplan_v2.md.

Rules:
1. Keep backend/ as the canonical runtime.
2. Preserve legacy-root/ bridge until replacement pages are complete.
3. Do not reintroduce root /register.
4. Every tenant-level API must resolve tenant context from path/header/host, not frontend-provided tenant_id.
5. Add or update tests for every behaviour change.
6. After changes, run:
   - python syntax checks
   - backend/test_cms.py
   - targeted tenant API checks
   - browser/page smoke checks where possible
7. Summarise changed files, tests run, and remaining risks.
```

---

## 5. Priority 1 — Tenant Isolation Hardening

### 5.1 Goal

彻底确认每个工作室的数据不会互相串。

### 5.2 Required work

Add a dedicated test file:

```text
backend/tests/test_tenant_isolation.py
```

Test cases:

- tenant A students cannot be read under tenant B context.
- tenant A registrations cannot appear in tenant B.
- tenant A packages/courses cannot appear in tenant B.
- tenant A balance query cannot find tenant B student.
- tenant A portfolio/media cannot be loaded under tenant B token.
- direct API calls with guessed IDs must return 404 or 403.
- frontend-supplied `tenant_id` must be ignored.
- path tenant context must override unsafe body tenant fields.

### 5.3 Acceptance criteria

```text
All cross-tenant negative tests pass.
No API endpoint accepts tenant_id from request body as source of truth.
All tenant-scoped queries include current tenant filter or verified repository helper.
```

---

## 6. Priority 2 — Authentication and Roles

### 6.1 Current issue

文档里已经规划了 Super Admin、Owner、Staff/Teacher、Parent/Student，但当前实现很可能仍处于轻量状态。商业 SaaS 至少需要清晰的 auth boundary。

### 6.2 MVP+ roles

| Role | Scope | Required access |
|---|---|---|
| platform_super_admin | platform | manage tenants, plans, usage, support mode |
| studio_owner | tenant | all tenant settings and data |
| studio_admin | tenant | students, courses, registrations, portfolio |
| teacher | tenant | assigned students, upload portfolio, consume credits |
| parent | student/guardian | own child data only |

### 6.3 Required work

- Confirm whether current login/session exists and how it is stored.
- Add session/token expiry.
- Add password hashing if not already implemented.
- Add role guard helper:
  ```python
  require_role(user, tenant_id, allowed_roles)
  ```
- Add audit logs for:
  - login success/failure
  - tenant created/paused
  - student archived
  - credit adjustment
  - logo upload
  - support mode access

### 6.4 Acceptance criteria

- Super Admin route cannot be accessed by Studio Admin.
- Studio Admin cannot access other tenant.
- Teacher cannot change billing/plan/tenant owner settings.
- Parent cannot access admin API.
- Audit log records actor, tenant, action, entity, timestamp, IP where available.

---

## 7. Priority 3 — Replace Legacy Branding Residue

### 7.1 Goal

旧 CMS iframe 内不应该明显显示 “Let’s Paint” 硬编码内容，至少要能由 tenant brand 替换。

### 7.2 Required work

Search and replace hard-coded strings in:

```text
legacy-root/index.html
legacy-root/register.html
tenant-template/index.html
tenant-template/register.html
tenants/*/index.html
tenants/*/register.html
```

Look for:

```text
Let's Paint
LetsPaint
Let’s Paint
Art Studio
default studio names
hard-coded phone/email/address
/register
```

### 7.3 Approach

- Do not blindly replace all text with one tenant name.
- Use public brand data from:
  ```text
  GET /v1/public/<tenant_slug>/brand
  ```
- For generated tenant wrappers, ensure safe escaping for apostrophes and special characters.
- Keep readable fallback labels but make them generic:
  - “Studio”
  - “Your Studio”
  - “Student Portal”
  - “Registration”

### 7.4 Acceptance criteria

- `lets-paint-studio`, `lets-play-piano`, `lets-play-game` display their own names.
- Studio names with apostrophes do not break JavaScript.
- Register link always uses `/<tenant_slug>/register`.
- No root `/register` appears in tenant-facing CTA.

---

## 8. Priority 4 — Modernise Frontend Boundary

### 8.1 Current transition state

当前 frontend 是：

- `super-admin.html`
- `backend/frontend/studio-admin.html`
- `tenant-template/*.html`
- `legacy-root/*.html`
- generated tenant pages

This is acceptable for MVP transition, but it will become hard to maintain.

### 8.2 Recommended next step

Do not immediately migrate to full Next.js unless needed. First create a cleaner static frontend structure:

```text
frontend/
  shared/
    api-client.js
    tenant-brand.js
    ui-utils.js
    validation.js
  pages/
    super-admin.html
    studio-admin.html
    tenant-cms-wrapper.html
    tenant-register-wrapper.html
```

Then let backend serve built/copied assets.

### 8.3 Required work

- Extract repeated tenant brand application JS into a shared file.
- Extract contrast checker into shared utility.
- Extract iframe resize logic into shared utility.
- Replace placeholder vendor files or remove dependency on them.
- Add frontend smoke tests to ensure critical elements exist.

### 8.4 Acceptance criteria

- Branding logic exists once, not duplicated across 4+ HTML files.
- Generated tenant wrappers use shared scripts where possible.
- Vendor JS 404 does not occur offline.
- Mobile table overflow remains contained.

---

## 9. Priority 5 — Media Upload and Storage

### 9.1 MVP+ upload requirements

Because this product may store children’s artwork and photos, upload handling must be stricter than a normal internal CMS.

### 9.2 Required work

- Enforce max upload size per file.
- Enforce tenant storage quota.
- Validate extension, MIME, and file signature.
- Generate safe storage keys, never trust original filename.
- Strip dangerous path segments.
- Store metadata in database.
- Log uploader and tenant.
- Support logo cleanup when replaced.
- Add image thumbnail/compression pipeline later.

### 9.3 Local storage structure

For local MVP:

```text
backend/storage/
  tenants/
    <tenant_id>/
      logos/
      media/
      thumbnails/
```

For AWS later:

```text
s3://studiosaas-prod/
  tenants/<tenant_id>/logos/
  tenants/<tenant_id>/media/
  tenants/<tenant_id>/thumbs/
```

### 9.4 Acceptance criteria

- Fake `.png` file rejected.
- Oversized image rejected.
- Upload path traversal rejected.
- Tenant A cannot retrieve Tenant B uploaded asset.
- Replacing logo does not leave unlimited orphan files.

---

## 10. Priority 6 — Database Migration and Backfill Discipline

### 10.1 Current issue

Docs mention adding `cms_layout` and `show_welcome`, plus backfill for tenants that lack settings. This must become a repeatable migration.

### 10.2 Required work

Create:

```text
backend/db/migrations/
  0001_schema_v1.sql
  0002_tenant_presentation_settings.sql
  0003_audit_support_mode.sql
```

Or, if not using a migration framework yet, create a simple migration runner:

```text
backend/scripts/run_migrations.py
```

### 10.3 Required backfills

- tenants missing `settings.cms_layout` -> `bar`
- tenants missing `settings.show_welcome` -> `true`
- tenants missing `welcome_message` -> generic welcome copy
- tenants missing workspace_path -> regenerate or repair workspace
- old logo_url paths -> normalise to public asset route

### 10.4 Acceptance criteria

- Running migrations twice is safe.
- Fresh database and existing local database both end in same expected schema.
- Migration status is visible in a table, for example:
  ```text
  schema_migrations
  ```

---

## 11. Priority 7 — Browser Smoke Testing

### 11.1 Current gap

Current notes say Chrome screenshot/layout automation could not complete in the sandbox. That is fine, but the repo should still contain browser smoke test logic for local Mac execution.

### 11.2 Recommended tool

Use Playwright if acceptable. If avoiding Node dependencies, use Python Selenium, but Playwright is usually easier for stable screenshots.

### 11.3 Test pages

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

### 11.4 Checks

- HTTP 200.
- No console errors for critical JS.
- No root `/register` CTA.
- tenant name visible.
- logo area visible.
- welcome area respects show/hide.
- mobile viewport has no horizontal overflow.
- tables scroll inside container.
- registration form visible without iframe height clipping.

### 11.5 Acceptance criteria

```text
npm run test:browser
# or
python backend/tests/browser_smoke.py
```

Produces pass/fail summary and screenshots in:

```text
checkpoints/browser-smoke/<date>/
```

---

## 12. Priority 8 — Super Admin Commercial Readiness

### 12.1 Required fields

Tenant creation should include:

- studio name
- slug
- owner name
- owner email
- phone
- country
- timezone
- plan
- status
- trial end date
- storage limit
- student limit
- staff limit

### 12.2 Super Admin actions

- create tenant
- pause tenant
- resume tenant
- change plan
- view usage
- regenerate workspace
- enter support mode
- export tenant data
- trigger backup
- view audit logs

### 12.3 Support mode

Support mode must:

- require explicit click/confirmation
- record reason
- create audit log
- show visible banner
- time out automatically
- default to metadata view rather than full student detail where possible

### 12.4 Acceptance criteria

- Super Admin cannot silently browse tenant student data without audit.
- Paused tenant cannot access Studio Admin, but public page may show paused message.
- Trial/past_due status is visible.

---

## 13. Priority 9 — Studio Admin Workflow Improvements

### 13.1 Dashboard

Add practical dashboard cards:

- Active students
- Low balance students
- Pending registrations
- Recent uploads
- Recent credit changes
- Storage used
- Current plan

### 13.2 Student detail

Improve student detail into tabs:

- Profile
- Guardians
- Credits
- Attendance
- Portfolio
- Notes
- Audit/history

### 13.3 Credits

Credit adjustments must never directly edit balance without transaction.

Actions:

- Add purchase
- Consume lesson
- Manual adjustment
- Refund
- Expire

Each action must include:

- amount
- note
- operator
- timestamp
- balance_after

### 13.4 Registrations

Registration queue should support:

- pending
- approved
- rejected
- duplicate warning
- convert to student
- link to existing student

### 13.5 Acceptance criteria

- Studio Admin can process a new registration into a student without manual database work.
- Credit history is immutable or append-only.
- Low balance card uses tenant-specific unit label.

---

## 14. Priority 10 — Deployment Readiness

### 14.1 Local to AWS mapping

| Local | AWS target |
|---|---|
| PostgreSQL local | RDS PostgreSQL |
| local media folders | S3 |
| waitress/server.py | Lightsail service or ECS |
| env vars | SSM Parameter Store / Secrets Manager |
| localhost tenant path | Route 53 / CloudFront / ALB |
| local backup scripts | RDS snapshot + S3 lifecycle |
| local SMTP | SES |

### 14.2 AWS MVP deployment order

1. Keep local stable.
2. Create staging environment first.
3. Deploy database to RDS.
4. Deploy app to Lightsail or ECS.
5. Move media to S3.
6. Add domain and HTTPS.
7. Add SES email.
8. Add backup schedule.
9. Add monitoring and logs.
10. Only then onboard pilot tenant.

### 14.3 Required AWS documents

Create:

```text
AWS_DEPLOYMENT_RUNBOOK.md
AWS_ENVIRONMENT_VARIABLES.md
AWS_BACKUP_AND_RESTORE.md
AWS_SECURITY_BASELINE.md
```

### 14.4 Acceptance criteria

- Staging deploy can be recreated from documentation.
- No secrets committed to repo.
- Health endpoint works.
- One test tenant works end-to-end on staging.
- Backup and restore tested at least once.

---

## 15. Test Matrix

### 15.1 Local command checklist

```bash
cd /Users/llmacbookpro/Documents/studiosaas
./start_studiosaas_local.sh
```

Then run:

```bash
cd backend
../.venv/bin/python test_cms.py
```

Add:

```bash
../.venv/bin/python -m pytest backend/tests
```

Optional browser:

```bash
npm run test:browser
```

### 15.2 API smoke checklist

```bash
curl -sS http://localhost:8899/v1/health

curl -sS   -H 'X-Tenant-Slug: lets-paint-studio'   http://localhost:8899/v1/tenant/brand

curl -sS   http://localhost:8899/s/lets-paint-studio/v1/tenant/brand

curl -sS   -H 'Host: lets-paint-studio.localhost:8899'   http://localhost:8899/v1/tenant/brand

curl -sS   -H 'X-Tenant-Slug: lets-paint-studio'   http://localhost:8899/v1/students
```

### 15.3 Must-pass scenarios

| Scenario | Expected |
|---|---|
| Open `/register` | 404 or JSON hint |
| Open `/<tenant_slug>/register` | tenant register page |
| Save Studio Admin colours | CMS/Register update |
| Upload fake logo | rejected |
| Upload valid logo | saved and visible |
| Tenant A requests Tenant B student ID | 403/404 |
| Register new student | appears in correct tenant |
| Query balance with wrong tenant | no result |
| Pause tenant | access restricted |
| Run seed twice | no duplicate corruption |

---

## 16. File-by-file Improvement Notes

### 16.1 `backend/server.py`

Need to check:

- route ordering
- root `/register` handling
- tenant slug route conflicts
- static asset serving
- iframe route mapping
- health endpoint
- logging
- error handling

Recommended improvement:

- split large server file into modules if it is becoming too large:
  ```text
  backend/studiosaas/app.py
  backend/studiosaas/routes_public.py
  backend/studiosaas/routes_tenant.py
  backend/studiosaas/routes_admin.py
  backend/studiosaas/routes_legacy.py
  backend/studiosaas/storage.py
  backend/studiosaas/auth.py
  ```

### 16.2 `backend/studiosaas/api_v1.py`

Need to check:

- every query has tenant context
- old `/v1/tenant/settings` delegates to `/v1/tenant`
- validation errors are consistent
- public brand payload is safe and complete
- credit transaction is append-only

### 16.3 `backend/frontend/studio-admin.html`

Need to check:

- settings patch reads back public brand immediately
- low contrast warning
- mobile layout
- logo upload UX
- no duplicate code copied from wrappers

### 16.4 `super-admin.html`

Need to check:

- create tenant form validation
- reserved slug list
- status display
- plan assignment
- tenant workspace repair button
- audit log visibility

### 16.5 `legacy-root/index.html`

Need to check:

- `/api/data` rewrite
- `/api/save` rewrite
- tenant slug detection
- registration link generation
- old hard-coded brand strings
- iframe height and title handling

### 16.6 `legacy-root/register.html`

Need to check:

- `/api/register` rewrite
- `/api/balance` rewrite
- tenant slug detection
- brand applier
- form validation
- duplicate handling

### 16.7 `tenant-template/index.html` and `tenant-template/register.html`

Need to check:

- safe JS escaping
- tenant placeholders
- shared brand script
- no root registration URL
- mobile viewport
- iframe resizing

### 16.8 `backend/db/schema_v1.sql`

Need to check:

- indexes on `tenant_id`
- foreign keys include tenant-related consistency where possible
- `created_at`, `updated_at`
- soft delete fields
- audit logs
- usage table
- migration compatibility

Recommended indexes:

```sql
create index if not exists idx_students_tenant_status on students(tenant_id, status);
create index if not exists idx_courses_tenant_status on courses(tenant_id, status);
create index if not exists idx_credit_accounts_tenant_student on credit_accounts(tenant_id, student_id);
create index if not exists idx_credit_transactions_tenant_student on credit_transactions(tenant_id, student_id, created_at desc);
create index if not exists idx_registrations_tenant_status on registrations(tenant_id, status);
create index if not exists idx_media_assets_tenant_student on media_assets(tenant_id, student_id);
create index if not exists idx_audit_logs_tenant_created on audit_logs(tenant_id, created_at desc);
```

---

## 17. Recommended New Documents

Create these files in project root:

```text
PROJECT_STATUS.md
NEXT_CODEX_TASKS.md
API_CONTRACT_v1.md
DATA_PRIVACY_AND_CHILD_SAFETY.md
TESTING_STRATEGY.md
AWS_DEPLOYMENT_RUNBOOK.md
BACKUP_RESTORE_RUNBOOK.md
SECURITY_CHECKLIST.md
```

### 17.1 `PROJECT_STATUS.md`

Should contain:

- current working version
- local run command
- current pass/fail tests
- known risks
- next 10 tasks
- do-not-touch files

### 17.2 `NEXT_CODEX_TASKS.md`

Should contain:

- strict task order
- each task acceptance criteria
- test command
- rollback note

### 17.3 `DATA_PRIVACY_AND_CHILD_SAFETY.md`

Should contain:

- data collected
- parent consent
- image privacy
- deletion/export process
- support mode rule
- staff access rule
- incident response draft

---

## 18. Immediate Next 10 Codex Tasks

### Task 1 — Add tenant isolation tests

Files likely touched:

```text
backend/tests/test_tenant_isolation.py
backend/studiosaas/api_v1.py
backend/studiosaas/db.py
```

Acceptance:

```text
Tenant A cannot access Tenant B students, registrations, courses, packages, balances, media.
```

### Task 2 — Add migration/backfill runner

Files likely touched:

```text
backend/scripts/run_migrations.py
backend/db/migrations/*.sql
backend/db/schema_v1.sql
```

Acceptance:

```text
Fresh DB and existing DB both migrate successfully. Re-running is safe.
```

### Task 3 — Replace legacy brand residue

Files likely touched:

```text
legacy-root/index.html
legacy-root/register.html
tenant-template/index.html
tenant-template/register.html
```

Acceptance:

```text
No visible hard-coded Let’s Paint copy in non-Let’s Paint tenants.
```

### Task 4 — Extract shared frontend brand helper

Files likely touched:

```text
backend/vendor/tenant-brand.js
tenant-template/*.html
legacy-root/*.html
backend/frontend/studio-admin.html
```

Acceptance:

```text
Brand application logic is shared and tested.
```

### Task 5 — Harden upload storage

Files likely touched:

```text
backend/studiosaas/storage.py
backend/studiosaas/api_v1.py
backend/tests/test_upload_security.py
```

Acceptance:

```text
Fake image, oversized file, path traversal are rejected.
```

### Task 6 — Add browser smoke test script

Files likely touched:

```text
backend/tests/browser_smoke.py
package.json or requirements.txt
```

Acceptance:

```text
Critical pages return 200 and no major mobile overflow.
```

### Task 7 — Improve Super Admin tenant lifecycle

Files likely touched:

```text
super-admin.html
backend/studiosaas/api_v1.py
backend/studiosaas/tenants.py
```

Acceptance:

```text
Create, pause, resume, change plan, regenerate workspace.
```

### Task 8 — Improve registration workflow

Files likely touched:

```text
backend/studiosaas/api_v1.py
backend/frontend/studio-admin.html
legacy-root/register.html
```

Acceptance:

```text
Pending registration can be approved into student or linked to existing student.
```

### Task 9 — Add backup/export script

Files likely touched:

```text
backend/scripts/export_tenant.py
backend/scripts/backup_local.py
BACKUP_RESTORE_RUNBOOK.md
```

Acceptance:

```text
Single tenant export produces clean JSON/CSV/media manifest.
```

### Task 10 — Prepare AWS staging runbook

Files likely touched:

```text
AWS_DEPLOYMENT_RUNBOOK.md
AWS_ENVIRONMENT_VARIABLES.md
AWS_SECURITY_BASELINE.md
```

Acceptance:

```text
Staging deploy steps are clear enough to recreate environment.
```

---

## 19. What I still need to inspect for a deeper code-level review

To move from document-level review to real code-level review, provide these files/folders, preferably zipped:

```text
backend/server.py
backend/studiosaas/
backend/db/schema_v1.sql
backend/scripts/
backend/test_cms.py
backend/requirements.txt
super-admin.html
backend/frontend/studio-admin.html
legacy-root/index.html
legacy-root/register.html
tenant-template/index.html
tenant-template/register.html
tenants/lets-paint-studio/tenant.json
tenants/lets-play-piano/tenant.json
start_studiosaas_local.sh
START_STUDIOSAAS_LOCAL.command
README.md
package.json if present
```

Also useful:

```text
backend/testdata/legacy_database_sample.json
sample generated demo data
screenshots of Super Admin, Studio Admin, CMS, Register pages
latest Terminal output from ./start_studiosaas_local.sh
latest test output from backend/test_cms.py
```

Do not provide real children’s private data. If exporting actual Let’s Paint data, de-identify names, phone, emails, addresses, notes, and images first.

---

## 20. Final Strategic Recommendation

StudioSaaS should now move in this order:

```text
Stabilise tenant safety
→ remove visible legacy residue
→ improve Studio Admin workflow
→ add test coverage
→ document local/AWS operations
→ pilot with one real tenant
→ then commercial packaging
```

The biggest mistake would be to keep adding features before tenant isolation, upload security, auth roles, backup/restore, and browser smoke testing are solid.

The strongest opportunity is that this system already comes from a real operating studio, so the product logic is grounded. The next value jump comes from trust: safe data separation, polished tenant branding, clean workflows, and repeatable deployment.
