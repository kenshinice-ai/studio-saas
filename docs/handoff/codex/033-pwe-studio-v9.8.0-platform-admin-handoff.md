# PWE Studio v9.8.0 — Platform Admin 三栏工作台发布 handoff

> 当前阶段：v9.8.0 已完成三栏工作台、Today Needs attention、Tenant/Plan/Audit Inspector 和移动端抽屉实现，并已通过完整门禁、干净双模式打包、提交同步、生产部署和公网验收。生产已由 v9.7.0 切换为 v9.8.0。历史发布证据保留在本节下方。

## 下一阶段设计入口

- [三栏工作台交互合同](design/Platform_Admin_Workbench_Interaction_Contract_2026-08-10.md)：冻结顶部栏、左侧工作区、中间工作流、右侧 Inspector、状态、权限、品牌和 P0/P1/P2 边界。
- [逐屏设计 handoff](design/Platform_Admin_Screen_Design_Handoff_2026-08-10.md)：Today、Tenants、Tenant Inspector、Plans、Audit、移动端和交接产物顺序。
- [前一阶段逐屏审计与状态矩阵](design/Platform_Admin_Audit_2026-08-10.md)：记录 v9.7.0 的 current-truth、真实审计和已完成发布证据。

本阶段设计原则：左边找地方，中间做事情，右边做判断；Attention 是 Today 内的快捷入口，不是第二套 Dashboard；Support Mode 必须使用 reason 和审计流程；未接入的数据、支付状态和未来页面不得提前进入一级导航。

## v9.8.0 最终发布证据（2026-08-10）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.3.0-cms-information-architecture`；`VERSION=9.8.0`；部署候选 commit `906d18549475ac35b2cabd24c31a7944b83cfc31`；已推送至 `origin`。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.0.tar.gz`，SHA-256 `af814ad66036a8c8686f3c94394fa1b1e63d2cc4fb9bb11d5878d7c8670bc29b`；Edition `dist/PWE-Studio-Edition-9.8.0.tar.gz`，SHA-256 `30731b98b66276024f1fbbefe75f0fc93e7832d0388aeac1ae9b8a44439aa6e8`。两个包均通过 checksum、`BUILD_INFO`、入口文件和排除项检查；构建时间 `2026-08-10T03:52:57Z`，模式分别为 `saas` / `standalone`。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.0`，运行镜像为 `studiosaas:9.8.0`；deep health 为 `appVersion=9.8.0`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；容器 healthy，磁盘可用约 `46.83 GB`。 |
| Backup | 切换前逻辑备份 `/data/backups/postgres/studiosaas_studiosaas_20260810T035741Z.dump` 与 manifest `/data/backups/postgres/studiosaas_studiosaas_20260810T035741Z.manifest.json`；卷归档 `pwestudio-volumes-20260810T035742Z.tar.gz`。 |
| Migration / media | 最新迁移为 `0028_cms_notifications.sql`；启动日志显示数据库无需新增迁移、10 个工作室重新生成；生产媒体覆盖为 `29` 个图片资源，medium/display/thumb 缺失均为 `0`；当前应用日志错误关键词计数为 `0`。 |
| Public edge | `https://pwestudio.online` deep health 与 `/platform-admin`、`/super-admin`、根站、中文站、手册、展示租户门户/报名/CMS/Studio Admin、双语 Release Notes/FAQ 均返回 `200`；HTTP → HTTPS 为 `301`，HTTPS TLS 校验为 `0`、HTTP/2；Platform Admin 版本化 asset hash 与本地一致，缓存头为 immutable；代表性公开媒体请求支持 ETag，`If-None-Match` 返回 `304`。 |
| Browser | 公网应用内 Browser 已打开 `/platform-admin#overview`，确认生产双语登录壳和未登录边界；未使用生产凭据、未执行生产写操作；浏览器控制台错误数为 `0`。本地验收仍覆盖桌面三栏、Needs attention、Tenant/Plan/Audit Inspector、移动端 Inspector 抽屉、无横向溢出和 Support Mode 空 reason 字段级拦截。 |
| Local gates | 完整门禁 `All checks passed`；CMS smoke `73 passed, 0 failed`；租户隔离 `237 passed, 0 failed`；Platform Admin/UI 定向门禁 `146 passed, 1 skipped`；`node backend/scripts/check_inline_scripts.mjs` 与 `git diff --check` 均通过。 |

未跟踪的 `docs/sales/` 路演资料已保留，未纳入提交或发布包。支付、银行转账设置、Gmail/SMTP、AWS SES、短信、SSE、WebSocket 和浏览器 Push 仍不在本版本。

## v9.8.0 本轮实际交付

- Platform Admin 采用顶部全局栏、左侧工作区导航、中间工作区、右侧 Inspector；保持 Studio Admin 的工作台关系，但只保留当前真实能力。
- Today 以 Needs attention 为入口，使用现有租户、订阅、试用日期和资源使用量数据，按优先级生成一条租户一条待处理记录；Attention 是 Today 内的快捷入口。
- Tenant Inspector 按状态 → 风险 → 订阅 → 资源使用 → 安全操作组织；Plan Inspector 和 Audit Event Inspector 复用同一右侧职责。
- Support Mode 在 Inspector 底部单独呈现，仍通过已有 reason 字段和审计流程进入，不改认证/RBAC，不新增支付、银行转账、Gmail/SMTP、SES、SSE、WebSocket 或 Push。
- 响应式行为：桌面保持三栏；中等宽度右侧转为抽屉；手机 Inspector 变为全屏工作表且无横向溢出。
- 未加入 Groups、Invitations、Announcements、System Health、Security、Settings 等尚不存在或尚未纳入本轮的一级导航。
- `past_due` 统一按订阅生命周期表达，不把它写成已接入在线支付后的“支付失败”。

## 当前实现前合同

```text
Today → Needs attention + business health + refresh evidence
Tenants → filters + list + tenant detail + Support Mode context
Plans & Pricing → catalog + limits + publication state (no gateway)
Audit Logs → search + pagination + governance detail
```

执行顺序：完成实现与浏览器验收，跑完整门禁，提交候选，生成干净 SaaS/Edition 包，推送分支，经预部署检查后部署，完成公网验收，再以文档闭环提交 handoff。

---

