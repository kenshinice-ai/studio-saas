# StudioSaaS 交接文档（持续更新）

> 本文件在**每轮改动开始时和完成时**都更新（用户 2026-07-26 明确要求），
> 始终反映最新状态。历史交接见 `docs/HANDOFF_2026-07-26.md`（v7.3.x 时期）。
> 最后更新：2026-07-27（v7.6.0 修复与 UI 升级轮 · **已完成**）

---

## ✅ v7.6.0 修复与 UI 升级轮（2026-07-27，本轮已完成）

针对 v7.5.0 全量审计（`docs/Project_Audit_2026-07-27.md`）的修复轮：
四个修复 agent 并行（后端 / 数据库 / Super Admin UI / legacy 面），
文档 agent 收尾。改动**已提交并推送，main 与 codex/studiosaas-v7.3.1
已对齐本提交**。

- **修复统计**：审计 **3 HIGH / 13 MED / 20 LOW 全部清零**，另加
  Super Admin 控制台专业化改版（KPI 卡、漏斗可视化、告警组件、表格
  筛选、顶部按钮组；新增 `--line-strong`/`--row-hover`/`--head-bg` 等
  token）。要点：`_is_local_request` 改 remote_addr 判定；限流器加锁
  +惰性清理；裸 `refund` 归一为 refund_out 语义；503 在 pilot/production
  固定文案；新迁移 **0020**（删两个冗余索引）；0016/schema_v1 DO 块
  可重跑修复；`connect()` 支持超时覆盖（维护脚本传 0）；归档裁掉
  `users.password_hash`；super-admin logout 崩溃修复 + pill 对比度达标
  （4.84–6.92:1）+ 29 处转义盲区清零 + admin-i18n 补 ~75 键；
  shared-portfolio 灯箱键盘可达 + 最小双语；legacy register emoji 16 处
  清零、删 CDN 兜底与 maximum-scale。逐项明细见 README §4.16。
- **验证基线**：**131 pytest** 全绿（新增
  `tests/test_v760_backend_fixes.py`）；check_terminology /
  check_inline_script / check_ui_escaping（扩展版）三件套通过；
  0020 与 0016/schema_v1 重跑在真实 PostgreSQL 实测通过；
  四个界面浏览器实测。
- **版本三处统一 v7.6.0**（VERSION / server.py APP_VERSION / README）；
  guides 六份手册"适用版本"7.4.1 → 7.6.0（审计 DOC1）；API/Database/
  Roadmap/QA_Checklist/Deployment 同步（503 文案、refund 同义、超时
  新机制、迁移 0020、测试数 131）。
- **遗留（roadmap 在案）**：61 处 raw hex token 化、super_admin 支持
  会话强制门、Owner 审计日志入口、品牌表单行内报错、media token
  hex 化、P3-04 Redis 限流。

---

## 历史轮次（压缩记录）

- **v7.5.0 全量项目审计轮（2026-07-27，已完成）**：四方向只读审计
  （UI/UX、后端、数据库、文档），基线 f710bdc；健康面七条不变量全
  PASS、schema 零漂移；产出 3H/13M/20L 发现清单
  （`docs/Project_Audit_2026-07-27.md`），全部已在 v7.6.0 轮修复。
- **v7.5.0 文档与 UX 审计轮（2026-07-26，已完成，ef8b1f8 + f710bdc 已
  push）**：文档全量刷新（README 枚举表 / API / Database / Architecture /
  Design_System / Admin_Guide 角色矩阵）、UI/UX 修复批次（reduced-motion /
  focus-visible / 触控 40px / CMS emoji 清零 / 登录行内报错）、
  `docs/guides/` 六份角色手册新增、ui-ux-pro-max skill 同步；
  Blueprint setup fee 定价统一 **AUD 299–999**（用户拍板，勿改回）；
  `verify_local.sh` 全量通过，AWS 打包产物 sha256 校验 OK。

---

## 0. 当前状态一览

- **版本**：v7.6.0（VERSION / server.py APP_VERSION / README 三处一致；
  v7.4.0=RBAC/a11y/AWS 套件，v7.4.1=数据库与复审稳定性修复，
  v7.5.0=文档全量刷新 + UI/UX 修复批次 + docs/guides 角色手册，
  v7.6.0=审计 3H/13M/20L 全量修复 + Super Admin UI 专业化改版）
- **提交状态**：v7.6.0 改动**已提交并推送，main 与
  `codex/studiosaas-v7.3.1` 已对齐本提交**（发布提交为
  "feat: release StudioSaaS v7.6.0" 单提交，随本轮 push 到远端）；
  v7.5.0 及之前为 ef8b1f8 + f710bdc
- **打包产物**：`dist/PWE-StudioSaaS-aws-7.5.0.tar.gz`（3.3M，sha256 校验
  OK，含 BUILD_INFO）；v7.6.0 提交后需重新打包
- **验证基线**：**131 pytest** + 73 smoke + 196 tenant-isolation 全绿
  （smoke/isolation 为 v7.5.0 基线；131 pytest 为本轮实测）
- **AWS 部署包**：`bash deploy/aws/build_aws_bundle.sh <ver>` →
  `dist/PWE-StudioSaaS-aws-<ver>.tar.gz`（含 BUILD_INFO；需干净 git 树）
- **迁移**：0001–0020；`schema_v1.sql` 已与迁移链**零漂移**（实测比对列/约束/索引；
  0020 只删冗余索引，无新表）

## 1. v7.4.0 做了什么（详见 README §4.14）

三条主线，全部已提交并验证：

1. **RBAC 全量审计修复** — 旧版 `/api/*` 在 pilot/production 410 关闭；
   parent-only 用户拒绝登录；财务边界（analytics:read / credits:read）落到
   /dashboard 与 /packages；新权限 `credits:refund`、`portfolio:share`
   （owner/manager）；legacy-cms/save 放行 students:write（套餐段仍限管理层）；
   CMS save() 布尔契约（22 个调用点全检查）；teacher 获得 roster 标签页。
2. **可访问性整改** — 两控制台 label/for 全覆盖、模态焦点还原+捕获、
   ARIA tab 键盘契约、门户画廊/灯箱键盘可达、自定义报名字段逐字段报错、
   aria-label 随语言切换、Super Admin 图标 SVG 化。
3. **AWS 部署套件** — `deploy/aws/`（Dockerfile/entrypoint/compose/nginx/
   systemd/打包脚本），Docker 端到端彩排通过（自动迁移→健康→旧接口 410）。

## 2. 深度复核轮（v7.4.1）修复清单

### 数据库稳定性审计（9 项，全部已修）

| 严重度 | 修复 | 位置 |
|---|---|---|
| HIGH | 归档快照补齐 0015–0017 六表（发布同意事件=法律证据） | `services/tenant_archive.py` SNAPSHOT_TABLES |
| MED | DB 超时：connect 5s / statement 30s / lock 10s（env 可调 `STUDIOSAAS_DB_*`） | `studiosaas/db.py` |
| MED | 旧档案编辑余额路径：FOR UPDATE + 带符号增量 + creditHours 记增量 | api_v1.py `_apply_absolute_balance` |
| MED | schema_v1.sql 补 0015–0017 + 0011 索引，零漂移 | `db/schema_v1.sql` 尾部 |
| MED | legacy-cms/save 服务端 rev 冲突检查（租户行锁 + 409 conflict + force 覆盖） | api_v1.py legacy_cms_save 开头 |
| MED | backup_postgres.py 补 `import sys` | scripts |
| L-M | 账本 CSV 导出归一化 consume/expire 符号 | export_credit_ledger_csv |
| L-M | 注册审批 FOR UPDATE（防并发双转化） | registration status 路由 |
| LOW | 迁移 0019：portfolio/notification 索引 + 删重复唯一索引；0016 标注 PG16+；`prune_event_tables.py` 保留脚本；compose 归档卷 | db/migrations、scripts、deploy/aws |

### 变更逻辑复审（6 项 CONFIRMED，全部已处理）

1. 登录拒绝消息区分「仅 parent」vs「无有效成员」（消息+审计 reason 都不再误导）
2. `end_support_session` 恢复宽松鉴权（防支持横幅卡死），注释说明为何不用 @auth_required
3. 删除死代码 `canSharePortfolio`（CMS 无分享 UI；后端权限已生效）
4. ConfirmDialog：Escape/遮罩点击对 acknowledge 对话框会先跑 onConfirm（reload 类通知不再丢）
5. dashboard 财务投影改 fail-closed（actor 缺失时剥离而非泄漏）
6. rev guard —— 已在数据库轮实现服务端强制（复审时是纯客户端）

复审同时确认：退款门无绕过（legacy_type 检查先于映射）、装饰器替换角色集完全等价、
media/upload kind 分发穷尽、schedule DELETE 双调用方安全、CMS save 22 个调用点全检查。

## 3. 已知未决 / 设计决策（有据可查，暂不做）

- **支持会话是 UI 提示，不是强制门**：super_admin 无需开支持会话即可进入租户
  路由（审计 §3.9）。改动涉及超管工具链，记入 roadmap。
- **租户 Owner 无自有审计日志入口**（审计 §3.10）→ roadmap。
- **v1 save 无 shrink guard**：v1 save 不删除学生（absence≠delete），rev guard
  已挡 stale 覆盖，故不需要 server.py 式的缩水防护。
- **账本历史符号不回写**：consume 正负混存是历史事实，导出层归一化；不做
  数据迁移改写账本历史。
- `programs[]` / `gallery[].title` 单语存储（产品决策，见 Glossary）。

## 4. 常用命令（与上一份一致，补充两条）

```bash
# 全量验证（发布门槛）
STUDIOSAAS_DATABASE_URL=postgresql://$USER@localhost:5432/studiosaas_local_test \
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh

# CMS 改完必须重建；模板改完必须重生成
bash backend/scripts/build_cms.sh
.venv/bin/python backend/scripts/regenerate_tenant_workspaces.py

# 新增：事件表保留清理（建议每月 cron）
python backend/scripts/prune_event_tables.py --dry-run

# 新增：AWS 打包
bash deploy/aws/build_aws_bundle.sh <version>
```

## 5. 下一个会话注意

- 改任何迁移时：**同步 `db/schema_v1.sql` 和 `tenant_archive.py SNAPSHOT_TABLES`**
  （两个清单在 0015–0017 时期都漂移过，v7.4.1 轮才补上）。
- `tenants/<slug>/` 是生成目录，别手改；改模板后跑 regenerate。
- Edit 工具对 `\uXXXX` 字面量匹配不了（presets.py / index.html），用脚本替换。
- 浏览器会缓存 `/v1/industry-presets`，排查样式问题先排除缓存。
- CSRF：v1 写请求需要 `X-Requested-With: StudioSaaS` 头（值不是 XMLHttpRequest）。
