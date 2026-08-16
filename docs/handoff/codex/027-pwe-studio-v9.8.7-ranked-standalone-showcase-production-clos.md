# PWE Studio v9.8.7 — ranked standalone showcase production closure

> 同步说明：Platform Admin 的历史优化清单与三栏工作台评审已随 `origin/main` 合并，完整方案保存在 [docs/design/Platform_Admin_Workspace.md](docs/design/Platform_Admin_Workspace.md)。本 handoff 继续只记录已发生的发布事实；方案文档不替代生产证据。

> 当前阶段：v9.8.7 已完成 `featured_rank` 数据契约、首页精选预览、独立 `/showcase` 作品归档、分类 URL、C 方案分页、统一导航/footer、后台排序编辑、套餐变更内容保留、双语手册更新、完整门禁、双模式打包、分支 push、生产迁移、备份、部署和公网浏览器验收。生产运行部署代码 commit `4e1894f12a31935701f3982757bd8fe0f441e0d0`；本节以下为本轮最终证据。文档闭环提交只更新发布记录，不改变已运行的 v9.8.7 包。

## v9.8.7 修复范围与验收

- 作品记录支持可选的租户全局 `featured_rank`（1–500）；数字越小越靠前，首页使用前 6 个排序位置，未排序作品沿用稳定的原有顺序。所有 Active / draft / archived 记录都保留排序值，套餐切换不会删除作品或重排已保存数据。
- 首页只请求最多 6 件公开作品；独立 `/<slug>/showcase` 归档默认每次返回 12 件，按全局排序后再执行分类过滤，继续通过 offset 的 C 方案分页和可见的「加载更多」兜底；分类筛选可分享为独立 URL。
- 公开页、课表、报名页与首页共享导航和 footer 入口；standalone showcase 使用可访问的键盘 lightbox、Escape、前后导航、焦点恢复、懒加载、移动端菜单和 reduced-motion 支持。
- Studio Admin 新增 Featured rank 输入、预览顺序和双语说明；在线用户手册、Studio Owner/CMS/Admin 指南、customer Release Notes 同步说明首页 6 件、归档 12 件、分类 URL、套餐额度和 Starter / 入门版、Studio / 工作室版、Growth / 成长版命名。
- 新增 `0030_showcase_featured_rank.sql`，以幂等 JSONB backfill 为旧作品补充 `featured_rank: null`，不覆盖现有内容或状态。

## v9.8.7 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已 push 到 `origin`；部署代码 commit `4e1894f12a31935701f3982757bd8fe0f441e0d0`；`VERSION=9.8.7`；本节之后的文档闭环只更新 README、handoff 与 Release Notes，不改变运行代码。未跟踪的 `docs/sales/` 路演资料未纳入发布。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `2291 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；`git diff --check`、UI escaping、terminology、inline-script、asset manifest 和双包校验均通过。首次无提升权限的本地 gate 只受到端口绑定/数据库可达环境限制，提升权限复跑后全绿，不作为产品回归。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.7.tar.gz` SHA-256 `8181b9324ef4f66297cacb9b9d440c4ecec458f34151d887965ff850c07392c1`；Edition `dist/PWE-Studio-Edition-9.8.7.tar.gz` SHA-256 `16473b8d4ad17c57e3603cef34915aca00b6e8a2c87305b146240ce8d1d64403`。两个包的 `BUILD_INFO` 均为 v9.8.7 / commit `4e1894f12a31935701f3982757bd8fe0f441e0d0`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、`mode` 和排除项检查。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.7`，镜像 `studiosaas:9.8.7`；容器 healthy；公网 deep health 为 `appVersion=9.8.7`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；部署后磁盘可用约 `46.25 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260811T083534Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260811T083535Z.tar.gz`。生产启动日志确认 `0030_showcase_featured_rank.sql` 已应用，`Generated variants: 0`，运行数据库角色配置与租户工作区重生成完成。 |
| Public API | Ruby Studio `https://pwestudio.online/v1/public/ruby-s-studio/showcase?surface=home&offset=0` 返回 `total=12`、`pageSize=6`、`nextOffset=6`、`hasMore=true`；默认归档返回 `pageSize=12`、`total=12`；分类 `76703d2c` 返回 `total=9`、`items=9`；`offset=12` 返回空页且 `hasMore=false`。排序字段随条目返回，当前未设置的生产条目为 `featured_rank=null`，稳定 fallback 顺序保持不变。 |
| Public routes / browser | 根站、`/zh/manual/`、`/manual/`、`/ruby-s-studio`、`/ruby-s-studio/showcase`、timetable、register、CMS、Studio Admin、Platform Admin 和双语 Release Notes 均返回 `200`。真实生产 390×844 CDP 视口确认 `documentWidth=390`、移动菜单 44×44 可见、12 个归档卡片无横向溢出；点击首件打开 lightbox，图片存在、计数为 `1 / 12`、body scroll lock 生效，点击关闭后 dialog 关闭且焦点/滚动状态恢复。截图保存在 `/private/tmp/studiosaas-showcase-v987-prod-390.png`。 |
| Logs | v9.8.7 app-only 容器日志从启动、迁移、工作区重生成到健康检查均为正常输出，未出现部署后新的 `Traceback`、`Exception`、`Fatal` 或 `Error`；历史数据库探索日志未作为本轮应用错误。 |

后续如需再改运行代码，应从 v9.8.7 新版本号继续，不复用已发布的 `9.8.7` 包标签；v9.8.6 保留为回滚基线。

