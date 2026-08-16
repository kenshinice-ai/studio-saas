# PWE Studio v9.5.0 — CMS 信息架构最终交付（2026-08-09）

## 当前发布状态

- 版本：`9.5.0`。
- 分支：`codex/v9.3.0-cms-information-architecture`；源码、发布包与生产状态
  分开记录；已同步到 `origin/codex/v9.3.0-cms-information-architecture`。
- 部署代码 commit：`9a976215bab9d5b32b9792f36851078a4111ff4b`。
- 当前生产：`/opt/pwestudio/current` 指向
  `PWE-StudioSaaS-aws-9.5.0`，运行镜像为 `studiosaas:9.5.0`。

## 本轮实际交付

1. CMS 外壳改为稳定的顶部工具栏、分组左侧导航和按角色过滤的工作台；导航按「今日」、
   「教学运营」、「经营」、「记录」组织，系统设置成为完整页面。
2. 课程、作品、学员、待处理事项以及充值与退款各自拥有明确的功能工作区；课程和设置
   可通过 `?view=` / `?section=` 深链直接打开，通知点击也可以落到对应处理入口。
3. 表单补齐可读标签、帮助文案和 44px 操作目标；保留 PWE Brand 颜色、字体、黄金分割
   的 rail/content 比例与现有权限边界，Studio Admin 和公开门户仍是独立表面。
4. CMS 通知仍采用已批准的第一阶段方案：持久化记录、30 秒定时刷新、回到前台时刷新和
   弹窗提示。支付、银行转账展示、Gmail/SMTP、AWS SES、SMS、SSE、WebSocket 和浏览器
   Push 均未加入本轮。

## 验收与 handoff

- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 的完整门禁已通过
  （最终 release commit 前会再跑一次）。
- 全量 pytest：`1940 passed, 8 skipped`；租户隔离/权限：`237 passed, 0 failed`；
  独立 CMS smoke：`73 passed, 0 failed`。
- Chrome 使用 `lets-paint-showcase` 合成租户真登录验收了中英文桌面、移动排课、课程、
  作品、待处理、充值退款、设置深链和手册截图；没有读取客户数据。
- 截图工具、`manual.html` 引用和 `asset-manifest.json` 已同步，未跟踪的 `docs/sales/`
  路演资料保留在工作区且不纳入发布提交。

## 发布闭环与线上证据

- SaaS：`dist/PWE-StudioSaaS-aws-9.5.0.tar.gz`；SHA-256：
  `d9cd91c57467213ee81710d290b8a589c6910b4819568d136e2da9e59842802a`。
- Edition：`dist/PWE-Studio-Edition-9.5.0.tar.gz`；SHA-256：
  `90409a371521074252ceed90946198a5c4021319fcefb19fc55d665f74dfc97d`。
- 两个包的 `BUILD_INFO` 均为 `version=9.5.0`、commit
  `9a976215bab9d5b32b9792f36851078a4111ff4b`，分别为 `mode=saas` /
  `mode=standalone`；checksum、入口文件和内部/敏感路径排除检查通过。
- 部署控制器在切换前创建了逻辑备份
  `studiosaas_studiosaas_20260809T123630Z.dump`（约 481 KB）及卷归档
  `pwestudio-volumes-20260809T123632Z.tar.gz`（约 66 MB）。
- 内部与公网 deep health 均通过：`appVersion=9.5.0`、`db=ok`、`mode=saas`、
  `tenants=6`、`themes.unreadable=0`；当前 app/db 容器均 healthy，磁盘约 47 GB 可用。
- 生产 `schema_migrations` 最新为 `0028_cms_notifications.sql`；
  `backfill_media_variants.py --check` 返回 `Generated variants: 0`。
- `/`、`/zh/`、`/zh/manual/`、展示租户门户、报名页、CMS 和 Release Notes 均通过公网
  200；HTTP → HTTPS 为 `301`，HTTPS 为 `200`，TLS 校验为 `0`，HTTP/2。
- CMS shell 发出 `/assets/cms-app.js?v=9.5.0&h=e08ae1f2dc0dd4c9`；响应为一年
  `immutable`，公网响应 SHA-256 与本地发布提交中的 tracked bundle 均为
  `e08ae1f2dc0dd4c9634fb0228dcdcc06e3099465fcb0da568febd11f83e5f444`。
- 本地 Chrome 已使用合成 `lets-paint-showcase` 真登录验收中英文桌面/移动 CMS、课程、
  作品、待处理、充值退款、设置深链；公网关键路由完成 HTTP 验收。生产原始日志未拉回
  本地，以避免把潜在业务数据或凭据带出；因此日志正文不作为本次交付证据。

---

