# PWE Studio v9.8.10 — public shell and honest publication-status production closure

> 当前阶段：v9.8.10 已完成源码、验证、提交、推送、双模式打包、生产备份、部署和公网验收。本节记录本轮最终证据；后续文档闭环只更新发布账本，不改变已运行的 v9.8.10 包。

## v9.8.10 修复范围与验收

- Studio Admin 的发布复核改为读取服务端 `tenant_brand_versions` 状态，不再在浏览器深比较 `websiteProfile`；写入成功、公开投影待确认和确实无效分别使用结构化双语状态码。
- 官网、独立作品页、公开课表和报名页继续使用统一 `publicSurfaceContract`，升级到 contract v3，补充本地化导航/CTA 标签、公共 shell 结构和跨页面 hash 链接解析。
- 公开 Footer 移除工作人员 CMS 与 Studio Admin 链接；现有租户工作区已从 `tenant-template/` 重新生成，确保模板修复落到已存在的静态工作区。
- public-surface 标签在服务端和本地解析器中解析 `%WORK%` / `%WORKS%` / `%VENUE%` 行业词，避免把模板占位符显示给访客。
- 版本与双语用户手册入口更新到 v9.8.10；未改变租户数据模型、套餐额度或支付能力。

## v9.8.10 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 隔离分支 `codex/v9.8.10-public-shell` 已 push 到 `origin`；部署代码 commit `d8c11daa703c5080578931c723385e0ab79e87df`；`VERSION=9.8.10`。根工作区的其他用户改动未被修改或纳入。 |
| Local gates | `verify_local.sh` 在隔离 PostgreSQL 55432 与临时 venv 中全绿：Python/JS 编译、UI escaping、terminology、inline scripts、asset manifest、完整 pytest `1613 passed, 8 skipped`、CMS smoke `73 passed`、迁移 current、媒体衍生图 `0`、租户隔离 `237 passed, 0 failed`。公开表面本地 API 返回 contract v3，行业占位词已解析。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.10.tar.gz` SHA-256 `03cde6a4816308b5249ab270c12aee10b591b9140165d021dfd3963e04dcae1f`；Edition `dist/PWE-Studio-Edition-9.8.10.tar.gz` SHA-256 `d51d2cfd73c529465c8d58041bde8faf3f64bb42128faa96d3690514882074fa`。两个 `BUILD_INFO` 均为 v9.8.10 / commit `d8c11daa`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、版本和排除项校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.10`，镜像 `studiosaas:9.8.10`；容器 healthy；公网 deep health 为 `appVersion=9.8.10`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.08 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / recovery | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260812T104121Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260812T104122Z.tar.gz`；v9.8.9 与 v9.8.8 仍保留为回滚目录，`STUDIOSAAS_VERSION=9.8.10` 已固定。 |
| Public API | `https://pwestudio.online/v1/public/ruby-s-studio/surface` 返回 contract v3、`publishedVersion=45`，导航/footer/actions 共用本地化标签与统一 href；作品 API 首页返回 `pageSize=6`、`total=12`、`hasMore=true`，归档返回 `pageSize=12`、`hasMore=false`。 |
| Public routes / browser | 根站、双语手册、Ruby 首页/作品页/课表/报名、Studio Admin、Platform Admin 与双语 Release Notes 均返回 `200`。生产桌面截图 `/private/tmp/studiosaas-v9.8.10-ruby-home.png` 确认首屏、导航、首屏 CTA 与作品入口；390×844 截图 `/private/tmp/studiosaas-v9.8.10-ruby-showcase-mobile.png` 确认独立作品页移动布局、分类筛选和作品卡片。公开四个 Ruby 页面均不包含 `/cms` 或 `/studio-admin` Footer 链接。 |
| Logs | 部署后 app-only 日志显示迁移 current、`Generated variants: 0`、10 个租户工作区重生成以及健康的 `200` 请求；未发现部署后新的 `Traceback`、`Exception`、`Fatal` 或应用错误。 |

