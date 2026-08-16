# PWE Studio v9.8.9 — Studio Admin public surface and Edition production closure

> 当前阶段：v9.8.9 已完成代码与文档范围冻结、Studio Admin 公开表面修复、统一公开契约、空间与体验模块、Draft / Live 预览、版本化发布验证，以及 standalone Edition 完整部署方案并入；已完成本地完整门禁、Git 推送、双模式打包、生产备份、部署和公网浏览器验收。

## v9.8.9 候选范围

- Studio Admin 将保存、发布写入和公开验证拆成明确状态，使用结构化错误码与持久错误摘要，避免网站已更新却显示英文误报；外部 CTA 只接受 HTTPS。
- 首页、作品页、课表、报名、导航与 Footer 共用 `publicSurfaceContract` v2，输出 owner intent、内容/依赖就绪度、可见性、原因码、下一步和发布版本。
- 空间与体验模块支持 6 条亮点、最多 6 张有序照片和中英文替代文本；公开页不自动轮播，无图片时使用约 1.618:1 的正文布局。
- Studio Admin 提供 Draft / Live 预览、有效公开状态、导航/Footer 映射、未就绪原因和下一步；发布后按 `publishedVersion` 核对 `/brand`、`/surface` 以及实际启用的独立页面。
- 已将任务 `019ff42b-93f5-7293-a263-9c4eafd300e2` 的 standalone 部署文档并入，并统一到 v9.8.9，包括客户前置条件、Docker Compose、TLS、PostgreSQL 16、账号/密钥、迁移、备份恢复、验收、回滚与职责边界。

## 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 隔离分支 `codex/v9.8.9-studio-admin-publish` 已 push；部署代码 commit `2411ec6fc52334dcf65884060a6fc9a5f50fab0f`；`VERSION=9.8.9`。根工作区的其他用户改动未被修改或纳入。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 STUDIOSAAS_MEDIA_DIR=/private/tmp/studiosaas-media-gate.zlytk0 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `1612 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；PostgreSQL 迁移、安全媒体衍生图、Python/JS 编译、inline scripts、CMS bundle、asset manifest、shell parse 与 `git diff --check` 均通过。Standalone 与公开表面定向测试为 `92 passed, 1 skipped`。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.9.tar.gz` SHA-256 `c6aee22bd60321d33cccfb793dc4ddbf082ff8240e8904b340ef172368c64675`；Edition `dist/PWE-Studio-Edition-9.8.9.tar.gz` SHA-256 `9bd1d37f374f86e2977081893b9c9243fac49818b1f734195800740ccfa57b0d`。两个 `BUILD_INFO` 均为 v9.8.9 / commit `2411ec6`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、版本和排除项校验。Edition 包包含本轮并入的完整 standalone 部署方案。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.9`，镜像 `studiosaas:9.8.9`；容器 healthy；公网 deep health 为 `appVersion=9.8.9`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.1 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Public API | `/v1/public/ruby-s-studio/surface` 返回 contract v2、`publishedVersion=45`，showcase intent / ready / visible 均为 true，导航、Footer 与次要 CTA 均指向 `/ruby-s-studio/showcase`。作品归档返回 12 件、3 个分类；分类 `76703d2c` 返回 9 件。 |
| Browser | 真实生产桌面 1280px 确认首页在权威契约返回后显示 Principal、Selected Work、FAQ 与报名入口，首页精选 6 件并显示 View all work。独立作品页显示 12 件；灯箱图片加载成功、计数 `1 / 12`、body scroll lock 生效。390×844 分类 URL 保持筛选并显示 9 件，文档宽度等于视口 390px，移动菜单为 44×44。根站、双语手册、Ruby 首页/作品页、Studio Admin、Platform Admin 与 canonical 双语 Release Notes 均返回 200。 |
| Recovery | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260812T092107Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260812T092108Z.tar.gz`；v9.8.8 运行包继续作为回滚基线。 |
| Logs / known ops note | 当前 app 日志为健康的 200/202/304 请求，未发现新的 Traceback、Exception、Fatal 或 ERROR；并发作品媒体加载期间 Waitress queue depth 短暂达到 5，健康检查持续绿色。独立 `disk` 命令打印 20% 使用率和约 47G 可用但返回 1；deep health 的磁盘状态为 `ok`，该运维命令的退出码应在下一轮单独修正。Release Notes 在 1280px 时，旧 v9.8.8 的 64 位 SHA 文本导致约 21px 横向溢出；公开核心首页与作品页验收不受影响，CSS 换行应作为下一小版本修复。 |

