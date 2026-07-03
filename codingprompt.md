# StudioSaaS Project Audit + Improvement Sprint Prompt (v2)

Version: v2.0
Date: 2026-07-03
Supersedes: codingprompt.md v1（v1 在 P0-01 中途截断，本文件为完整重写版）

你现在接手的是 StudioSaaS 多租户 creative studio CMS/SaaS 项目。
项目已经过多轮修改，当前目标不是盲目新增功能，而是做一次系统性审计、修复、整理和提升。
本文件是当前开发周期的**唯一任务清单来源**。产品与技术规范见 `docs/`。

---

## 0. 文档体系（单一事实来源）

| 文件 | 用途 |
|---|---|
| `README.md` | 项目入口、快速启动、规范速查 |
| `codingprompt.md`（本文件） | 按优先级排列的任务清单 P0 → P3 |
| `docs/Current_Sprint.md` | 本清单的状态跟踪表（同一编号体系） |
| `docs/StudioSaaS_Blueprint_v2.md` | 产品愿景、定位、商业模型 |
| `docs/Architecture.md` | 现状架构 + 目标架构（§7 Target Architecture） |
| `docs/Database.md` | schema、枚举值的规范来源 |
| `docs/API.md` | API 端点参考与路由保护表 |
| `docs/Development_Roadmap.md` | 阶段规划、目标技术栈的落位 |
| `docs/QA_Checklist.md` | 发布前检查清单 |
| `docs/Admin_Guide.md` | 平台运维手册 |
| `docs/Design_System.md` | UI token 与组件规范 |

**规则：文档与代码矛盾时，以代码实际行为为准，修复其一并同步另一者。**

---

## 1. 目标架构参照（StudioSaaS v2 架构总览图）

目标架构详见 `docs/Architecture.md` §7。要点：

- 分层：用户角色 → 前端门户（CMS / Register / Parent / Teacher / Studio Admin / Super Admin）→ API Gateway → 后端服务模块 → 数据层。
- 服务模块边界：Auth / Tenant / User / Student / Course / Package / Attendance / Payment / Credit / Portfolio / CRM / Notification / Report / AI / File。
- 关键业务流程：
  - 报名流：Public Register → Registration Created → Studio Review → Approve? → Yes: Create Student / No: Archive
  - 课时流：Student Buy Package → Payment Success → Add Credits → Use Credits → Attend Class

**采纳策略（重要）：**

1. 现阶段保持 **Flask 单体**，但内部代码按上述模块边界组织（modular monolith）。P2-01 的拆分以此为蓝图。
2. Pilot 阶段**明确不引入**：FastAPI 重写、微服务拆分、Redis、Elasticsearch、ClickHouse、消息队列、读副本、SQLAlchemy。这些是 Phase 3–5 的目标态（见 Roadmap）。
3. `media_assets.storage_provider` 字段已为 S3 预留，媒体服务抽象（P1-03）应保持该扩展点。
4. 架构图中的 ER 图是简化示意（例如 users 带 role 列）；**实际 schema 以 `backend/db/schema_v1.sql` 为准**（角色在 memberships 上）。

---

## 2. 忽略清单（不要报告为问题、不要恢复）

- 工作区中以下删除是**用户有意为之**：`docs/archive/`、`letspaint-cms-release/`、根级旧文档（LOCAL_DEPLOYMENT.md、StudioSaaS_MVP_Blueprint_v1.md、TENANT_ROUTING_AND_STRUCTURE.md 等）、checkpoints 旧 patch。P0-04 只需将其 commit 定格。
- `.venv/`、`__pycache__/`、`*.bak`、`.DS_Store` 等本地产物。

---

## 3. 工作规则

1. 严格按 P0 → P1 → P2 → P3 顺序执行，禁止跳级做视觉优化。
2. 每完成一项，运行该项的验证命令，并报告：**改动文件 / 验证结果 / 风险 / 下一步**。
3. 不做一次性大重写。大文件渐进拆分，每步可回退。
4. 每个 P0 项完成后，同步更新 `docs/Current_Sprint.md` 的状态表。
5. 涉及 schema 变更的项必须走迁移文件（P0-03 之后），禁止直接改 `schema_v1.sql` 后手工同步数据库。

---

## 4. 已核实现状快照（2026-07-03 代码级审计）

> **进度更新（2026-07-03 晚）：P0-01 至 P0-07 已全部完成并验证**，逐项状态见 `docs/Current_Sprint.md` §3。下一个任务从 P1-02 开始（P1-01 文档同步已完成）。本节以下描述保留为当时的审计记录。

以下结论逐项核实过，**旧文档中与此矛盾的状态标注一律以本节为准**：

✅ 已完成 / 已存在：
- 公共端点限流已实现（注册 5 次/分、余额查询 10 次/分、上传 5 次/分，进程内存实现，`api_v1.py` `_public_rate_limit`）
- dict_row 元组索引 bug 已清零（grep 无 `fetchone()[0]` / `row[0]`）
- portfolio DELETE 已有独立路由（`api_v1.py:3473`）
- credit_accounts 已用 `ON CONFLICT (tenant_id, student_id, course_id)`（`api_v1.py:2482`）
- 根 `.gitignore` 已存在且覆盖较全
- `python3 -m py_compile` 全量通过
- HTML 界面中 "Let's Paint" 品牌残留已清零（仅剩 `sw.js`）

❌ 已确认的问题（对应下方任务）：
- 角色枚举三处不一致 + seed 更新不存在的列（P0-01）
- pytest 未安装、pytest.ini 重复键、tests/ 目录不存在（P0-02）
- 迁移 runner 不存在（P0-03）
- checkpoints patch 仍被 git 跟踪、根目录杂物、删除未提交（P0-04）
- `/v1/auth/login` 无限流（P0-05）
- 约 114 条路由仅 8 处保护装饰器，覆盖未经审计（P0-06）
- 状态/可见性枚举跨层不一致（P0-07）
- `attendance_sessions` 已接入正式 API；签到/撤销与 credit ledger 可追踪（P1-05）

---

# P0 — 数据一致性与安全（必须先做）

## P0-01 — 统一角色模型

**问题：** 角色定义在 schema、Python、seed 脚本三处互相矛盾。

**证据：**
- `backend/db/schema_v1.sql:52` — `memberships.role CHECK (role IN ('super_admin','owner','staff','parent'))`；`users` 表**没有 role 列**。
- `backend/studiosaas/models.py` — Role 枚举含 `platform_super_admin` 和 `admin`，两者永远无法写入数据库。
- `backend/studiosaas/auth.py:177` — 查询 `role IN ('platform_super_admin','super_admin')`，前者是死条件。
- `backend/scripts/seed_super_admin.py:93` — `ON CONFLICT ... SET updated_at = now()`，但 memberships 表**没有 updated_at 列**。
- seed 采用"给每个已存在租户逐条插 super_admin membership"的模型：新建租户后平台管理员不会自动获得权限。

**修复（第一步让代码迁就 schema，扩枚举留待 P0-03 迁移就绪后）：**
1. Role 枚举收敛到 schema 现有 4 值，或保留 6 值但显式区分"DB 合法子集"。
2. 删除 auth.py 中 `platform_super_admin` 死查询分支。
3. 修复 seed_super_admin.py 的 `updated_at` 引用。
4. 决策平台管理员表示法（二选一，写入 Database.md 决策记录）：
   - A（推荐）：`memberships.tenant_id IS NULL` 表示平台级角色（需迁移放开约束逻辑，排 P0-03 后）；
   - B：维持 per-tenant 模型，但在创建租户流程中自动为平台管理员补 membership。
5. 同步 `docs/Database.md`、`README.md` 的角色描述。

**验证：** `py_compile` 通过；重建数据库 → 全部 seed 脚本无报错 → super admin 登录 curl 成功；`pytest -q`（P0-02 后）。

## P0-02 — 修复 pytest 基础设施

**问题：** `pytest -q` 完全不可用。

**证据：**
- `.venv` 中未安装 pytest；`backend/requirements.txt` 不含 pytest。
- `backend/pytest.ini` 存在**重复的 `norecursedirs` 键**（configparser 报 DuplicateOptionError）。
- `testpaths = tests` 指向不存在的 `backend/tests/`。

**修复：**
1. 新增 `backend/requirements-dev.txt`（pytest，版本上限约束风格与 requirements.txt 一致）。
2. 去重 pytest.ini。
3. 创建 `backend/tests/`，放最小可运行用例（如 `/v1/health` 的 app test client 用例），保持 `test_cms.py` / `test_tenant_isolation.py` 脚本式运行不被收集。

**验证：** `cd backend && ../.venv/bin/python -m pytest -q` 绿色通过。

## P0-03 — 迁移运行器

**问题：** 无迁移机制；README 曾引用不存在的 `scripts/run_migrations.py`。

**修复（按 docs/Database.md §5 已有设计实现）：**
1. `backend/db/migrations/0001_schema_v1.sql` 作为基线。
2. `schema_migrations (version text PRIMARY KEY, applied_at timestamptz)` 表。
3. `backend/scripts/run_migrations.py`：按序应用、跳过已应用、可重复运行、`--dry-run`。
4. 对已存在的本地库提供基线标记方式（把 0001 标记为已应用而不重跑）。

**验证：** 空库连续跑两遍无错且结果一致；现有库标记基线后跑一遍无副作用。

## P0-04 — 仓库卫生收尾

**问题：** 有意删除未提交定格；被跟踪与未跟踪的杂物混在工作区。

**证据：**
- `git ls-files` 仍跟踪 `checkpoints/*.patch|*.status`（.gitignore 只忽略 `checkpoints/*.tgz`）。
- 根目录：`studiosaas.zip`（3.4MB）、`studiosaas plan.png`（1.6MB）、`super-admin.html.backup`；`backend/studiosaas/*.bak*`。
- `docs/archive/`、`letspaint-cms-release/` 等删除停在工作区（用户确认有意，见 §2）。

**修复：**
1. commit 定格全部有意删除（单独一个 commit，信息注明 doc/legacy cleanup）。
2. `.gitignore` 改为忽略整个 `checkpoints/`，`git rm --cached` 已跟踪的 patch/status。
3. 移除或忽略根目录 zip/backup/bak 杂物（`studiosaas plan.png` 若需保留设计参考，移入 `docs/assets/`）。

**验证：** `git status` 干净；`git ls-files | grep -E "(\.bak|checkpoints/|\.zip)"` 无输出。

## P0-05 — 登录限流与失败审计

**问题：** 公共端点已限流，但 `/v1/auth/login` 与 `/s/<slug>/v1/auth/legacy-login` 无任何限流；失败登录不落审计。README §16 明确要求。

**修复：**
1. 复用 `_public_rate_limit` 机制，对 login 做 IP + email 双维度限流（如 5 次/分/IP，10 次/时/email）。
2. 失败登录写 `audit_logs`（action=`auth.login_failed`，不记录明文密码）。
3. 在代码注释中说明内存限流的重启清零特性（pilot 可接受；生产换 Redis 时替换，见 P3-04）。

**验证：** 连续错误密码 curl 触发 429；audit_logs 出现失败记录；正确凭据仍可登录。

## P0-06 — 路由保护全量审计

**问题：** `api_v1.py` + `server.py` 约 114 条路由，仅 8 处使用保护装饰器，其余依赖函数内手工检查——覆盖与否无人能证明。

**修复：**
1. 生成"路由 × 预期权限 × 实际检查方式"审计表（可写临时脚本遍历 `app.url_map`）。
2. 对缺口路由补装饰器（`super_admin_required` / tenant 角色检查），公共端点显式标注 `# public by design`。
3. 审计结果落入 `docs/API.md` §12 路由保护表。
4. `test_tenant_isolation.py` 补充负向用例：未认证 mutation 全部 401/403；租户 A session 访问租户 B 资源 403。

**验证：** 未认证 POST/PATCH/DELETE curl 逐条 401/403；隔离测试通过。

## P0-07 — 状态与可见性枚举对齐

**问题：** 同一概念在 schema、代码、UI、文档间取值不一致。

**证据：**
- `tenants.status` CHECK 无 `archived`（README v1 推荐 6 态含 archived）。
- `subscriptions.status` 用 `trialing`，`tenants.status` 用 `trial`。
- `media_assets.visibility` 仅 `('private','public_token')`，文档曾推荐 5 值。

**修复：**
1. 先在 `docs/Database.md` 建立"规范枚举表"，**如实记录现状 CHECK 值**为当前规范。
2. 需要扩值的（archived、public 等）经 P0-03 迁移文件添加，逐个而非一次性。
3. 核对 `super-admin.html` / studio-admin 下拉选项与 CHECK 值一致。

**验证：** grep schema/代码/HTML 三方枚举一致；创建-暂停-恢复租户全流程 UI 操作无约束报错。

---

# P1 — 工程质量与核心业务闭环

## P1-01 — 文档同步 ✅（2026-07-03 已完成一轮）

README.md、codingprompt.md（本文件）、docs/* 已按代码实况刷新。后续规则：每个 P0 项完成即更新 `docs/Current_Sprint.md`。

## P1-02 — 租户隔离负向测试矩阵

现有 `test_tenant_isolation.py` 为脚本式。纳入 pytest（P0-02 后），补全矩阵：租户 A 的 session 对租户 B 的 students / registrations / credits / portfolio / media 的读写全部 403；`X-Tenant-Slug` header 伪造不能越权。

## P1-03 — v1 媒体上传端点 + 集中媒体服务（架构图 File Service）

✅ Done 2026-07-03. 已实现 `POST /s/<slug>/v1/media/upload`，扩展名/MIME/magic byte/大小/路径穿越/租户配额校验集中到 `backend/studiosaas/services/media.py`；legacy 上传路径调用同一服务，保留 `storage_provider` 的 S3 扩展点。

## P1-04 — 注册审核 → 学生转化闭环（架构图流程 5a）

✅ Done 2026-07-03. `registrations.status` 已有 `pending/approved/rejected/duplicate/contacted/archived`；Studio Admin 支持待审队列、Approve 创建/关联 student、Reject/Archive 带 review note、重复报名标记为 duplicate，转化和决策动作写 audit_logs。

## P1-05 — 课时闭环 + 考勤（架构图流程 5b）

✅ Done 2026-07-03. 已实现：购买/加课时 → `purchase` 交易加课时 → 上课记录 attendance session 并产生 `consume` 交易 → 余额不足保护 → 撤销签到产生 `refund` 交易。`attendance_sessions.credit_transaction_id` / `reversal_credit_transaction_id` 可追踪账本来源。

## P1-06 — Playwright 浏览器冒烟测试

四条主链路：super admin 登录建租户；studio admin 登录建学生记课时；公共页提交注册；注册转化为学生。产出 `backend/tests/e2e/` 或独立 `e2e/` 目录 + 运行文档。

## P1-07 — 备份/恢复脚本与 runbook

✅ Done 2026-07-03. 新增 `backend/scripts/backup_postgres.py` 和 `docs/Admin_Guide.md` PostgreSQL backup/restore runbook；脚本支持 `pg_dump`、restore dry-run、保留策略、`schema_migrations` 校验。

---

# P2 — 结构演进与 UI（P0 全绿后）

## P2-01 — 按目标架构模块边界拆分 api_v1.py

`api_v1.py` 现为 **4040 行**（文档旧值 2200 已过时）。按架构图模块边界渐进拆分：

```
backend/studiosaas/routes/     # auth, admin_tenants, tenant, students, courses,
                               # packages, credits, attendance, registrations,
                               # portfolio, media, public, legacy_bridge
backend/studiosaas/services/   # 业务逻辑（media service 自 P1-03 起已存在）
```

每搬一个模块跑一次全量验证。禁止一次性重写。

## P2-02 — PWA / sw.js 多租户化

`sw.js` 仍是 "Let's Paint CMS" 命名（lpcms 缓存前缀），缓存平台级 `/logo.png` 等。多租户下 manifest 与图标应按租户分发；这是最后一处品牌残留。

## P2-03 — vendor 构建产物化

`backend/vendor/` 含 `babel.min.js` + `tailwindcss.js`（浏览器运行时编译）。替换为预构建产物或最小打包流程，pilot 可容忍、商用前必须完成。

## P2-04 — Super Admin 平台驾驶舱

按架构图与 README §13：Platform Overview / Tenant Management / Plan Management / Usage / Audit Logs / Support Mode / Settings。危险操作二次确认；support mode 可见且全程落审计。

## P2-05 — Studio Admin 工作流重组

按架构图与 README §14：Dashboard / Students / Registrations / Courses / Packages / Credits / Portfolio / Website / Settings。待审注册易找、余额直观、课时史读起来像账本。

## P2-06 — 共享 Design Tokens 落地

`docs/Design_System.md` 的 token 表落为共享 CSS（custom properties），super-admin / studio-admin / tenant-template 引用同一份，替代各页面内联重复样式。

---

# P3 — 平台化与部署准备

## P3-01 — 配置分层与生产安全基线

`STUDIOSAAS_ENV` 驱动 local/staging/production 配置分离；secure cookies（Secure/HttpOnly/SameSite）；结构化日志 + request id；secrets 全部走环境变量。

## P3-02 — Docker + Nginx + CI（架构图 Infra 列）

Dockerfile + docker-compose（backend + postgres）；Nginx 反代模板；GitHub Actions 跑 py_compile + pytest + 冒烟。

## P3-03 — 媒体存储 S3/MinIO 抽象

基于 P1-03 的 media service 实现 `storage_provider='s3'` 分支，本地 MinIO 验证后接 AWS S3。

## P3-04 — 远期数据基建（明确 pilot 不做）

Redis（缓存/限流/会话）、读副本、Elasticsearch、ClickHouse、消息队列、Scheduler——仅当 pilot 数据量或功能需要时按 Roadmap Phase 5 评估。**在此之前任何人不得以架构图为由提前引入。**

## P3-05 — 扩展服务（挂起）

Payment（Stripe）、CRM、Notification（SES）、Report、AI Service——由 pilot 客户反馈驱动，进入 Roadmap Phase 3+ 再立项。

---

## 验证命令合集

```bash
# 语法
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/scripts/*.py

# 单测（P0-02 之后）
cd backend && ../.venv/bin/python -m pytest -q

# 脚本式冒烟
cd backend && ../.venv/bin/python test_cms.py
cd backend && ../.venv/bin/python test_tenant_isolation.py

# 全量本地验证
bash backend/scripts/verify_local.sh

# 手动检查（服务运行中）
curl -sS http://localhost:8899/v1/health
curl -i  http://localhost:8899/s/lets-paint-studio/v1/tenant
curl -i  http://localhost:8899/lets-paint-studio/register
curl -i  http://localhost:8899/super-admin

# 未认证 mutation 必须 401/403
curl -i -X POST http://localhost:8899/v1/admin/tenants \
  -H 'Content-Type: application/json' \
  -d '{"name":"Bad Tenant","slug":"bad-tenant","planCode":"starter"}'
```

## 提交规范

- 每个 P 任务独立 commit，信息格式：`fix(P0-01): unify role model across schema/code/seeds`。
- commit 前跑完上方验证命令合集。
- schema 变更必须附迁移文件（P0-03 之后）。
