# 2026-08-17 · v10.9.2 — 手册第 10 章截图修复与文案校准（Claude）

> 范围刻意最小：手册资产 + 文案 + 两处脚本修复。运行时代码未改
> （`APP_VERSION` 标签除外）。

## 起因

线上 `/zh/manual/` 第 10 章「开票」的 `09-billing-identity` 截图是坏的：
设置页滑入动画拍到一半——侧栏卡在视口中间、搜索提示碎片悬在右上角、
右侧一大块空白。中英两张坏法相同。其余三张（billing / finance /
private-lessons）完好。

## 修了什么

1. **重拍第 10 章全部四组截图**（v10.9.2 环境、重新播种的演示租户）。
2. **捕捉脚本加了「动画结束」守卫**（`capture_manual_shots.py`）：
   截图前轮询 `document.getAnimations()`，有限时长的动画未结束就等（上限 10s），
   无限循环动画（同步小圆点之类）排除。固定 sleep 赛不过慢的首帧，问页面本身才赛得过。
3. **播种器在 HEAD 上是坏的，已修**：0043 迁移要求非草稿发票必须带
   supplier/recipient 快照，迁移回填了存量行，但 `reset_professional_demo.py`
   直接 SQL 开票、没写快照——`invoices_issued_snapshots_check` 直接拒绝，
   播种在发票一步崩掉。修法：种子改用产品自己的
   `supplier_snapshot()` / `recipient_snapshot()`（`services/billing.py`），
   不另造第二份快照形状。
4. **文案两处事实修正**：
   - 开票信息图注原说「Owner 与 Manager 可见」。实际 `PUT /billing/identity`
     要 `settings:write`，只有 Owner 持有；Manager 是 `billing:read` 只读。
     图注改为「Manager 看得到；能保存的只有 Owner」。
   - 第 11–14 章眉题编号错位（14/11/12/13 → 11/12/13/14）：
     第 10 章插入时目录改对了、眉题没跟上。
5. 英文 CMS 设置页半翻译（五个标签、迁移提示、说明行仍是中文）在英文截图里
   可见——**产品 i18n 欠账，不属于本轮**，已单开任务（有 v9.9.3
   「中文后台是中文的」先例可循）。

## 验证

- `test_manual.py` 33 passed；完整 pytest 见下方门禁行。
- 本地 `/zh/manual/#invoicing`：四图加载、眉题 10–14、图注为修正后文本。
- 权限口径逐条对过 `ROLE_PERMISSIONS`：前台可开票/收款 ✓、退款要
  `payments:refund`（Manager+）✓、请假记录要 `scheduling:write`（前台有）✓、
  GST→ABN 数据库约束存在 ✓。

## 四层身份（2026-08-17 发布闭环）

| 层 | 事实 |
|---|---|
| Source | 发布提交 `3e725fd`，分支 `claude/online-manual-content-improvement-03b8f9`；`VERSION=10.9.2`。门禁全绿（app 连接走 `studiosaas_leastpriv`，fixture 走 `STUDIOSAAS_OWNER_DATABASE_URL`，迁移走 `STUDIOSAAS_MIGRATION_DATABASE_URL`）：pytest `1949 passed`、legacy smoke `73 passed`、租户隔离 `254 passed, 0 failed`。 |
| Package | SaaS `PWE-StudioSaaS-aws-10.9.2.tar.gz` SHA-256 `e3cca0f1cf233bf5ceb1d8158b7dd33a2eec1578604767aba5675da966948f92`；Edition `PWE-Studio-Edition-10.9.2.tar.gz` SHA-256 `cd9353bee7a71cce49b976012e059ad42d8234e0c52a61526b37ad4c98f2ac83`；均通过 checksum / BUILD_INFO / entrypoint / exclusion / smoke。 |
| Production | `pwestudio.online` deep health `appVersion=10.9.2`、`db=ok`、`mode=saas`、`workspaces.stale=0`；第 10 章四组截图线上字节与本地 SHA-256 逐一相同；修正后的图注与眉题编号（11/12/13/14）已上线。 |
| Backup | 部署前逻辑库备份 `studiosaas_studiosaas_20260817T103221Z.dump` + manifest。 |

> 口径备注：deep health 的 `themes.tenants=4` 只统计 active+onboarding；
> 库里 6 个租户一个不少（2 active / 2 onboarding / 1 archived / 1 paused）。
> 上一轮 handoff 写的「tenants=6」按当时口径，两者都对，别当回归追。
