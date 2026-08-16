# PWE Studio v9.8.8 — truthful public surface verification production closure

> 当前阶段：v9.8.8 已完成发布写入与公开验证解耦、统一 `publicSurfaceContract`、亮色 Studio Admin 工作台、导航/Footer 可见性解析、结构化双语错误、手册同步、完整门禁、双模式打包、main 同步、最终生产备份、部署和公网浏览器验收。本节记录运行包的最终证据；本次修改之后的 handoff 文案只更新发布账本，不改变已运行的包。

## v9.8.8 修复范围与验收

- Studio Admin 写入成功后不再因公开投影短暂延迟而误报失败；状态改为「已发布，公开页面仍在确认」，提供结构化重试和双语错误码。
- 官网、独立 `/showcase`、公开课表和报名页共用一套公开表面契约；导航与 Footer 只展示同时满足 owner intent 和真实公开内容的入口，预览区显示未就绪原因与下一步。
- Studio Admin 采用信息色亮色选中态与 `1.618fr / 1fr` 编辑器/预览比例，保持现有 Vanilla HTML/CSS 栈，并覆盖键盘焦点、reduced-motion 和移动端触摸目标。
- 作品数据、`featured_rank`、套餐切换保留规则和首页 6 / 归档 12 / 分类 URL 逻辑继续沿用 v9.8.7；本轮没有新增数据迁移。

## v9.8.8 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 运行代码 commit `4b436e1e2df0717b7efb01d5e7d4021a6cc23860`；`VERSION=9.8.8`；`main` 与候选分支均已 push。后续本 handoff 更新为 docs-only 发布账本，不改变运行代码。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `2292 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；Python/JS 编译、UI escaping、terminology、inline assets、asset manifest 和 `git diff --check` 均通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.8.tar.gz` SHA-256 `1d6fc1760993864c681c8f9cb5e58eac303acdb65573ba98978181f226ee3da7`；Edition `dist/PWE-Studio-Edition-9.8.8.tar.gz` SHA-256 `0a75bf66059da97dc91b450933bd2a44e48200b7dda17030b62baa22ec1cd3b6`。两个 `BUILD_INFO` 均为 v9.8.8、commit `4b436e1e2df0717b7efb01d5e7d4021a6cc23860`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、版本和排除项校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.8`，镜像 `studiosaas:9.8.8`；容器 healthy；公网 deep health 为 `appVersion=9.8.8`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.06 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / recovery | 最终切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260811T121335Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260811T121336Z.tar.gz`；回滚目录 `PWE-StudioSaaS-aws-9.8.7` 与前一运行包归档仍保留。 |
| Public API | Ruby Studio 首页作品接口返回 `pageSize=6`、`total=12`、`nextOffset=6`、`hasMore=true`；归档返回 `pageSize=12`；分类 `76703d2c` 返回 `total=9`；`offset=12` 返回空页且 `hasMore=false`。`/v1/public/ruby-s-studio/surface` 返回版本化 navigation/footer/modules 契约。 |
| Public routes / browser | 根站、双语手册、`/ruby-s-studio`、`/ruby-s-studio/showcase`、timetable、register、CMS、Studio Admin、Platform Admin 和双语 Release Notes 均返回 `200`。Codex In-app Browser 在默认 `1280px` 与 `375px` 视口确认无横向溢出；移动菜单可见且触摸目标为 `44px`；点击首件打开 lightbox，图片存在、计数为 `1 / 12`、关闭后 dialog 消失；分类 URL `?category=76703d2c&lang=en` 保持筛选。 |
| Logs | 部署后 app-only 日志包含正常的 `200/304` 静态资源、公开 API 和媒体响应；未出现新的 `Traceback`、`Exception`、`Fatal` 或 `ERROR`。高峰浏览期间出现 Waitress queue depth `1–4` 的非致命 warning，健康检查仍为绿色，列为后续容量监测项。 |

后续运行代码应从 v9.8.9 开始；v9.8.7 和 v9.8.6 保留为回滚基线。

