# PWE Studio v9.8.6 — 在线手册课表与约课发布闭环

> 当前阶段：v9.8.6 已完成双语在线手册的公开课表与约课章节、配套后台/手机截图、版本升级、完整门禁、双模式打包、分支 push、生产部署和公网验收。生产运行部署代码 commit `21d2cc70bcd116250fca4780bec164a855b45258`；本节以下为本轮最终证据。文档闭环提交只更新发布记录，不改变已运行的 v9.8.6 包。

## v9.8.6 修复范围与验收

- 在线用户手册新增独立的「公开课表与约课」章节，说明品牌工作台中的课表开关、班次公开、1–4 周显示范围、约课申请开关、字段显示和老师姓名授权。
- 说明约课申请与正式占位的边界：访客提交后进入 CMS 待处理列表，只有批准时才核对容量；拒绝或撤回不会占用名额。
- 补齐四张中英文配对截图，覆盖 Studio Admin 公开课表设置与移动端约课申请弹窗；截图使用合成 `lets-paint-showcase` 捕获租户，不写入客户记录。
- `VERSION` 与应用版本更新为 `9.8.6`；未新增数据库迁移，也未修改客户业务数据。

## v9.8.6 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已 push 到 `origin`；部署代码 commit `21d2cc70bcd116250fca4780bec164a855b45258`；`VERSION=9.8.6`；随后提交的文档闭环只更新 README、handoff 与 Release Notes，不改变运行代码。未跟踪的 `docs/sales/` 路演资料未纳入发布。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `2283 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；`git diff --check` 和发布资产检查通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.6.tar.gz` SHA-256 `bd532a34d79ef74717218cde59a69d9b9f1fac7978ee6a52fb2509abc568536e`；Edition `dist/PWE-Studio-Edition-9.8.6.tar.gz` SHA-256 `f0c70727457ead7616958f2d051020c2cfe32f679289ff5cc2f16018a5c5df6b`。两个包的 `BUILD_INFO` 均对应 commit `21d2cc7`，模式分别为 `saas` / `standalone`，并通过 checksum、入口和排除项校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.6`，镜像 `studiosaas:9.8.6`；容器 healthy；公网 deep health 为 `appVersion=9.8.6`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.35 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 部署前后已生成逻辑库备份 `studiosaas_studiosaas_20260811T064145Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260811T064146Z.tar.gz`。生产已应用至 `0029_showcase_plan_values_and_states.sql`；启动日志为 `Database is up to date`，安全媒体衍生图为 `Generated variants: 0`。 |
| Public routes | 根站、`/zh/manual/`、`/manual/`、`/lets-paint-showcase`、`/lets-paint-showcase/timetable`、CMS、Studio Admin、register，以及中英文 Release Notes 均返回 `200`。 |
| Assets / logs | 中文手册课表截图 URL 为 `/assets/manual/04-timetable.zh.webp?v=9.8.6&h=6157b883c9c46d13`；本地与公网 SHA-256 均为 `6157b883c9c46d13a5eef10888f1cf739f5c3aa26db748856216a272ded70999`，缓存为 `public, max-age=31536000, immutable`，条件请求返回 `304`。应用容器自部署以来没有 `Traceback`、`Exception`、`Fatal` 或 `Error` 关键字，启动与手册/课表请求均为健康响应。 |

后续如需再改运行代码，应从 v9.8.6 新版本号继续，不复用已发布的 `9.8.6` 包标签；v9.8.5 仍保留为回滚基线。

---

