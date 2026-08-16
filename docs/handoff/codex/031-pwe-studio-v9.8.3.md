# PWE Studio v9.8.3 — 套餐关联作品发布与生产部署闭环

> 当前阶段：v9.8.3 已完成套餐关联的作品发布额度、active/draft/archived 状态、Super Admin 套餐字段和兼容性保护，并从已部署 v9.8.2 基线完成完整门禁、双模式打包、生产部署与公网验收。生产运行 commit `97b041495800edd1b41dc742c399587fed289ad7`；本节以下为本次闭环证据。

## v9.8.3 修复范围与验收

- starter / studio / growth 的 active 作品额度固定为 `15 / 60 / 150`；公开接口每页仍返回最多 12 件，这只是分页大小，不再是总量限制。
- 作品记录统一保留 `active` / `draft` / `archived` 发布状态；套餐下调只减少公开 active 数，不删除作品，超出当前额度的新上传自动进入 draft。
- Studio Admin 显示套餐额度与三类作品计数，允许逐件切换发布状态；Super Admin 套餐表单可读取、校验并保存 `showcaseLimit`。
- 缺省旧记录按 active 兼容；PATCH 套餐请求省略 `showcaseLimit` 时保留现有值，避免旧调用方将额度静默改回默认值。

## v9.8.3 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery`；部署代码 commit `97b041495800edd1b41dc742c399587fed289ad7`；`VERSION=9.8.3`。未推送 Git 远端。 |
| Local gates | 完整 pytest `1964 passed, 8 skipped`；`backend/scripts/verify_local.sh` 全部通过（含 CMS smoke `73 passed`、租户隔离 `237 passed`、迁移与生成资产检查）；`git diff --check` 通过。 |
| Package | SaaS SHA-256 `08b47e4bfce26bb69a7329d3bb40d6cd8f2cac55e9a148d51e430b15d249b44e`；Edition SHA-256 `9169cdc3d77a54fdcf76fd857589d69d7e7fc1688db06a9646ed5d365eaa4244`。两个包的 `BUILD_INFO` 均为 v9.8.3 / commit `97b041495800edd1b41dc742c399587fed289ad7`，模式分别为 `saas` / `standalone`，并通过发布包校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.3`，镜像 `studiosaas:9.8.3`；容器 healthy；公网 deep health 为 `appVersion=9.8.3`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Migration / quota | 生产启动已应用 `0029_showcase_plan_values_and_states.sql`；生产数据库确认 `growth=150`、`starter=15`、`studio=60`。 |
| Content recovery | 生产数据库确认 Ruby Studio 当前套餐为 `growth`，保留 `12` 件作品与 `4` 个分类；公开 showcase 返回 `total=12`、`items=12`、`hasMore=false`，全部为 `active`。未执行删除或覆盖作品数据。 |
| Backup | 部署自动备份：`studiosaas_studiosaas_20260811T030431Z.dump` / `studiosaas_studiosaas_20260811T030431Z.manifest.json`；卷归档 `pwestudio-volumes-20260811T030432Z.tar.gz`。 |
| Public edge / media | 根站、中文手册、Ruby Studio 门户 / timetable / CMS、Release Notes 均返回 `200`；版本化 `ui-common.js` 的 `h=` 与内容 SHA-256 前缀一致并带 immutable 缓存；代表性 Ruby 媒体返回 `200 image/jpeg`，带 ETag 的条件请求返回 `304`。 |
| Logs | 部署后应用日志持续返回健康检查、公开套餐、showcase、门户和媒体请求；最近日志未出现 Traceback / Exception / Fatal / Error 关键字。 |

本次未修改或打包未跟踪的 `docs/sales/` 路演资料。部署包对应部署代码 commit；本次文档闭环提交只更新 README 与 handoff，不改变运行代码，也不重新打包。

---

