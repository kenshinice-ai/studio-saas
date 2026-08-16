# PWE Studio v9.1.1 — 课程安排体验完善（2026-08-09）

## 当前发布状态

- 版本：`9.1.1`。
- 分支：`codex/v9.1.1-course-schedule-polish`，已同步到 `origin`。
- 当前状态：已打包、推送、部署并通过内部、公网、迁移、媒体与缓存验收。
- 生产运行的应用包来自 commit
  `4a048f1eecfaf7996d583e0e17358916e4a77f41`；其后的提交只记录发布结果。

## 本轮实际交付

1. 中文「每日排课」统一改为「课程安排」，英文统一为 `Class Schedule`；桌面和
   移动端导航、设置、手册、日历导出及截图契约同步更新。
2. 规划卡片按日期、周导航、出勤摘要、时段、添加学员、批量排课的任务顺序重排；
   桌面保持紧凑一行学员操作，移动端按任务自然换行且没有横向溢出。
3. 更多菜单新增学员、日期、时间、余额上下文，并把课程状态、提醒、`oneToOne`、
   撤销签到和移除排课分区呈现；固定课表来源明确提示应去固定课表调整。
4. PATCH 排课状态只接受 `scheduled` / `makeup`，拒绝无效状态和已取消记录，
   同时把状态变更写入审计元数据，避免界面能力绕过原有取消/恢复契约。
5. 浏览器截图脚本加入课程安排布局契约，持续检查页面命名、区块顺序、桌面/移动
   行布局、更多菜单上下文和横向溢出。

## CMS 真实浏览器验收

本地 PostgreSQL、合成展示租户、真登录和 Chrome：

- 桌面中英文排课页重新拍摄为 `1600 × 1000`；
- 移动中英文排课页按 `390 × 844` 视口拍摄为 2× 图 `780 × 1688`；
- 日期、周导航、摘要、时段、添加学员和批量区按任务顺序排列，无页面横向溢出；
- 44px 触控目标、紧凑桌面行、移动任务流、更多菜单和底部导航均进入真实浏览器；
- 截图只使用受保护的 `lets-paint-showcase` 合成数据，没有读取客户数据。

## 发布闭环

### Git 与发布包

- 分支：`codex/v9.1.1-course-schedule-polish`，已同步到 `origin`。
- 部署代码 commit：`4a048f1eecfaf7996d583e0e17358916e4a77f41`。
- SaaS：`dist/PWE-StudioSaaS-aws-9.1.1.tar.gz`；
  SHA-256：`a584518edcd6dbe81edede14f0b16fe5163308f9291f152996cd85b5d3db710d`。
- Edition：`dist/PWE-Studio-Edition-9.1.1.tar.gz`；
  SHA-256：`eb9db1a5abaf60d22da31c649f0148df4bed7cbb0b4725bcfca3cc0c3033ad45`。
- 两个包均通过 checksum、`BUILD_INFO`、入口文件、模式和敏感/内部路径排除检查。

### 本地 release gate

- 默认 pytest：`1934 passed, 7 skipped`；
- PostgreSQL 租户隔离/权限：`237 passed, 0 failed`；
- 独立 CMS smoke：`73 passed, 0 failed`；
- 课程安排/API 定向回归：`139 passed, 1 skipped`；
- migration `0027_medium_media_variant.sql` 与本地 86 个缺失中图完成回填，复核为 0；
- CMS source、tracked bundle 与 asset manifest 一致；JS、inline script、shell
  语法、术语和 Git whitespace 检查均通过。

### AWS 与线上验收

- 部署前生产为健康的 `9.1.0`；v9.1.1 一次部署成功，未触发回滚。
- 成功部署前备份：`studiosaas_studiosaas_20260809T044226Z.dump`（约 473 KB）及
  `pwestudio-volumes-20260809T044227Z.tar.gz`（约 66 MB）。
- `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.1.1`；当前容器
  `studiosaas:9.1.1`，应用与 PostgreSQL 均 healthy。
- 内部和公网 deep health：`appVersion=9.1.1`、`mode=saas`、`db=ok`、
  `tenants=6`、`themes.unreadable=0`；公网 HTTP → HTTPS 301、TLS 校验 `0`、
  HTTP/2。
- 最新 migration 为 `0027_medium_media_variant.sql`；生产共有 29 个 medium
  变体，`images_missing_medium=0`。
- `/`、中文手册、Studio 门户、公开课表、CMS 和 Release Notes 均返回最终 200。
- CMS 发出 `/assets/cms-app.js?v=9.1.1&h=0adf0808c802f2f3`，响应为一年
  immutable；线上与本地 bundle SHA-256 均为
  `0adf0808c802f2f320a07c3d5456c06be65125e85e48b41fecddb38f23ebd1c5`。
- 生产 medium JPEG 返回 checksum ETag；携带 `If-None-Match` 时返回 304。
- 当前应用日志显示 migration 最新、媒体回填 0 缺失、10 个 workspace 重建和
  Waitress 正常启动，无新异常。
- 回滚点保留为前一版本 `PWE-StudioSaaS-aws-9.1.0`。

---

