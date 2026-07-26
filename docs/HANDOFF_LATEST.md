# StudioSaaS 交接文档（持续更新）

> 本文件在**每轮改动开始时和完成时**都更新（用户 2026-07-26 明确要求），
> 始终反映最新状态。历史交接见 `docs/HANDOFF_2026-07-26.md`（v7.3.x 时期）。
> 最后更新：2026-07-26（v7.5.0 文档与 UX 审计轮 · **已完成，全量验证通过**）

---

## ✅ v7.5.0 文档与 UX 审计轮（2026-07-26，本轮已完成）

版本号已三处统一升 **v7.5.0**（VERSION / server.py APP_VERSION / README），
`verify_local.sh` 全量验证通过（含 196 tenant-isolation，All checks passed）。
**未提交**：改动全部在工作树上；AWS 打包（build_aws_bundle.sh 需干净 git 树）
待 commit 后进行。本轮明细：

1. ✅ **UI/UX 审计完成**：HANDOFF_2026-07-26 §2 批次 1–6 共 14 条**全部已落地**
   （逐条核对有 file:line 证据）。skill 数据为新版（84 styles/192 palettes），
   但项目内 `.claude/skills/ui-ux-pro-max/SKILL.md` 文案是旧数字，且与用户级
   副本存在 scripts/threejs.csv 漂移。新发现 14 条改进建议（a11y/触控/emoji
   残留/字号），已转入修复。
2. ✅ **文档偏差审计完成**：README 枚举表 5 处硬伤（角色/租户状态/注册状态
   仍是 0001 时代快照）；codingprompt.md / Current_Sprint.md /
   Architecture.md / Design_System.md 严重过时；API.md 缺 rev-409 与
   409/410 错误码；Database.md 停在 0017；Admin_Guide 缺 v7.4.0 角色矩阵。
   Glossary / Release_Runbook / Product_Surface_Model / HANDOFF_LATEST
   核实为最新。真实权限矩阵已从 auth.py ROLE_PERMISSIONS 摘录存证。
3. ✅ **`docs/guides/` 六份角色手册完成**（总览 / Super Admin / Studio Owner /
   Manager / Teacher / 学员家长），全部事实点经代码核实，互链可达。
   撰写中发现并已如实处理：隐私声明版本无编辑 UI（联系平台方）；
   Studio Admin 无 SEO 面板（模板能力）；Restore 恢复为 paused 需再
   Reactivate。**两个由此发现的真 bug 已由主会话修复**：
   ① Super Admin「+ Add Plan」Code 字段 disabled 且空 → 无法创建任何套餐。
   已修：创建模式解锁 Code 输入（placeholder + pattern），savePlanModal
   增加 trim/lowercase 与 `^[a-z0-9][a-z0-9-]{1,62}$` 客户端校验（与后端
   `_plan_payload` 规则一致）；编辑模式 Code 仍锁定。
   ② studio-admin `settingsPayload()` `colorScheme` 键重复——第二个键
   （取预设**首个模式**）覆盖用户选择；且 success/warning/danger 也取自
   首个模式（暗色草稿会存明亮版状态色）。已修：styleTheme 改为按
   `schemes[activeColorScheme]` 解析；colorScheme 在 preset 模式用
   `activeColorScheme`，custom 模式按背景亮度推导。
   另：studio-admin 登录密码框零信息 placeholder 已删（与 Super Admin 一致）。
4. **修复执行中**（五个 agent 并行，按文件边界互不重叠）：
   - ✅ 文档更新 A 完成：README 升 v7.5.0 + 枚举表对齐 Database.md +
     新增 §4.15；codingprompt / Current_Sprint 存档化；Roadmap 补三条
     未决项；Blueprint 三处 token 表述修正 + 三份历史快照加存档头；
     check_terminology 通过。Blueprint 定价已按用户决定统一为
     **AUD 299–999**（2026-07-26，§6 L180 已改齐 §1）
   - 文档更新 B：API/Database/Architecture/Deployment/Admin_Guide（补角色
     矩阵节）/ Design_System（整份按 8 主题 21token 体系重写）/ QA_Checklist
   - ✅ Admin 界面修复完成（super-admin.html + studio-admin.html）：
     reduced-motion、:focus-visible（button/a/[role=tab]，用 --brand）、
     btn-sm min-height 40px、支持横幅 emoji→SVG + `--support-banner` token、
     9px chip→11px、两页登录行内报错（role=alert + aria-invalid + 聚焦，
     并消除 studio-admin 登录的 unhandled rejection）、装饰符号 aria-hidden。
     inline-script + ui-escaping 检查通过，浏览器实测渲染正常
   - ✅ CMS 修复完成：emoji 图标清零（新增 plus/close/ellipsis path，
     源文件+bundle grep 均 0）；登录/邮件设置补可见 label；9 处图标钮
     aria-label（cms-i18n.js 同步补词条）；套餐编辑/删除钮 min-h 40px；
     reduced-motion 守卫进 legacy-root/index.html；顺手修复待审核页
     「拒绝」按钮重复 className 导致样式丢失的既有 bug。
     build_cms + inline-script + terminology 三项全过
   - ✅ skill 同步完成：scripts（core/search/design_system + 新增
     validate_data.py、tests/）、threejs.csv、references/ 均以用户级为准；
     SKILL.md 采新版为底并保留中文使用指引与本项目图标偏好
     （Phosphor 优先）两节；数据量文案修正为 84/192/74/98/22；
     validate_data + 16 unittest 全过
   - 本轮**不做**：studio-admin 61 处 raw hex 全量 token 化（已记入 roadmap）
5. ✅ 版本已三处统一 **v7.5.0**；Blueprint setup fee 统一 **AUD 299–999**
   （用户拍板）；`verify_local.sh` 全量通过（2026-07-26）

---

## 0. 当前状态一览

- **版本**：v7.5.0（VERSION / server.py APP_VERSION / README 三处一致；
  v7.4.0=RBAC/a11y/AWS 套件，v7.4.1=数据库与复审稳定性修复，
  v7.5.0=文档全量刷新 + UI/UX 修复批次 + docs/guides 角色手册，**未提交**）
- **打包产物**：`dist/PWE-StudioSaaS-aws-7.4.1.tar.gz`（sha256 已验证；
  7.5.0 包待 commit 后打——build_aws_bundle.sh 需干净 git 树）
- **分支**：`codex/studiosaas-v7.3.1`，上游同名
- **验证基线**：117 pytest + 73 smoke + 196 tenant-isolation 全绿
- **AWS 部署包**：`bash deploy/aws/build_aws_bundle.sh <ver>` →
  `dist/PWE-StudioSaaS-aws-<ver>.tar.gz`（含 BUILD_INFO；需干净 git 树）
- **迁移**：0001–0019；`schema_v1.sql` 已与迁移链**零漂移**（实测比对列/约束/索引）

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

## 2. 深度复核轮（本轮）修复清单

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
  （两个清单在 0015–0017 时期都漂移过，本轮才补上）。
- `tenants/<slug>/` 是生成目录，别手改；改模板后跑 regenerate。
- Edit 工具对 `\uXXXX` 字面量匹配不了（presets.py / index.html），用脚本替换。
- 浏览器会缓存 `/v1/industry-presets`，排查样式问题先排除缓存。
- CSRF：v1 写请求需要 `X-Requested-With: StudioSaaS` 头（值不是 XMLHttpRequest）。
