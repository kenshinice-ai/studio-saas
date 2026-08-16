# PWE Studio v10.7.1 — released repair and production handoff

> 更新时间：2026-08-16（Australia/Melbourne）
>
> v10.7.1 已按
> `docs/design/Repair_Execution_Checklist_v10.7.1_Luna_Max.md` 完成
> commit → package → push/sync main → production deploy → browser acceptance。
> Source、Runtime、Package、Production 仍按四层分别记录；后续 docs-only
> closure 不会被误写成已部署运行时代码。

## 本次修复

- 附件 `Downloads/Let's Paint Studio CMS.pdf` 的实际证据是 2 页空白纸张，只有浏览器标题 `Let's Paint Studio CMS`、URL 和页码；对应 `INV-0007` 的客户单据没有进入打印输出。
- 根因：`body.invoice-print-mode #root *` 的 `#root` ID 选择器优先级高于客户文档的可见性恢复规则，导致 `.invoice-customer-document` 及其内容仍为 `visibility:hidden`。
- 修复：`legacy-root/index.html` 改为在 `#root > *` 边界隐藏 CMS 外壳，让客户快照文档的显式 `visibility:visible` 生效。
- 修复：`legacy-root/src/panels/billing.jsx` 为发票/贷记单共用打印入口，临时把浏览器文档标题设为 `Tax Invoice · INV-0007`（或 `Credit Note · CN-…`），打印结束后恢复 CMS 标题；不读取 live payer，继续只打印 issued `detail.document` snapshot。
- 已重新构建 `backend/frontend/assets/cms-app.js` 与 `asset-manifest.json`；公共 workspace 生成输出保持同步。
- 逐项证据记录在 `docs/design/Repair_Execution_Acceptance_Evidence_v10.7.1.md`；该文件
  明确区分 source/runtime/package/production，并保留 N-payer 与 credits-only 浏览器覆盖限制。

## 发布闭环（v10.7.1）

- SaaS/Edition 包均通过 checksum、`BUILD_INFO`、entrypoint exclusion 和 archive smoke gates；最终 artifact、部署 commit、备份与生产深健康的精确值见本文件下方的四层表格与发布证据。
- production `pwestudio.online` 已切换至 v10.7.1；内部/公开 deep health 均为 `db=ok`、`mode=saas`、`themes.unreadable=0`、`workspaces.stale=0`，主题/工作区健康计数为 `4`。
- 生产数据库仍有 6 个租户记录：`lets-paint-showcase`、`lets-paint-studio` active，`n-piano-studio`、`ruby-s-studio` onboarding，`hong-s-studio` archived，`jjl-s-studio` paused。归档、恢复再暂停均有你的审计操作记录，不是部署丢数；`0044_credit_refund_source.sql` 已在生产核对。
- 公开页面、CMS shell、桌面/移动导航、immutable CMS bundle hash、ETag 304、以及本地真实 `INV-0007` customer print flow 已验收；生产 CMS 只做未登录 shell 验收，未使用生产凭据或写入生产财务数据。

## 四层精确身份（v10.7.1）

| 层 | 精确事实 | 证据 |
|---|---|---|
| Source | v10.7.1 运行时代码与发布台账已提交并推送；当前工作树仅包含本次事实闭环文档 | `main == origin/main`；运行时 commit 为 `9b7dfdcc12b33a8e448dc59270bab17dfd5d748b`。 |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.7.1.tar.gz` | SHA-256 `a087abe657fa1b8c0490ff1e430b0f3a21b0c535cdba5993ebf3798ea6c14215`；`BUILD_INFO` mode `saas`、commit `9b7dfdcc…`、built_at `2026-08-16T12:40:44Z`。 |
| Package / Edition | `dist/PWE-Studio-Edition-10.7.1.tar.gz` | SHA-256 `e4b9dc3da0be6e1f18f2eda4636323b1d81ce3a0749fe49165dcf269c31f87b1`；`BUILD_INFO` mode `standalone`、commit `9b7dfdcc…`、built_at `2026-08-16T12:40:45Z`。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-10.7.1`; image `studiosaas:10.7.1` healthy | `appVersion=10.7.1`、`db=ok`、`mode=saas`、`themes.tenants=4`、`themes.unreadable=0`、`workspaces.tenants=4`、`workspaces.stale=0`、约 `43.26 GB` free；production `BUILD_INFO` 同上。 |
| Backup / migration | 最终切换前备份已生成 | dump `studiosaas_studiosaas_20260816T124139Z.dump` + manifest；volume `pwestudio-volumes-20260816T124140Z.tar.gz`；schema `0044_credit_refund_source.sql` current。 |
| Public asset | CMS bundle bytes match the committed local asset | `/assets/cms-app.js?v=10.7.1&h=1ff09a1e8aadd7a0`；SHA-256 `1ff09a1e8aadd7a0c9b40a80e7d3ad9fa6a882237c656daf19251ae57cb9a209`；`immutable` cache and conditional `304` verified. |

The first two deployment attempts stopped before switching `current`: the first
hit the production backup role/RLS boundary, and the second exposed that the
controller itself had to be staged before the backup. Commits `5de3bab` and
`b77e0ed` fixed those release-controller causes; the final v10.7.1 deployment
completed with the owner-role backup and candidate-controller staging gates.

## INV-0007 当前核对

- 本地 PostgreSQL issued snapshot：`INV-0007`、`paid`、收件人 `Ana Bianchi`、行项目 `test`、`$1,999.00 + GST $199.90 = $2,198.90`。
- 真实 CMS 浏览器重新打开 `INV-0007`：文档标题 `Tax Invoice`、单号、日期、supplier/recipient、行项目、付款、余额均正确；打印 CSS 已加载 `body.invoice-print-mode #root > *` 与客户文档可见性规则。
- 该 PDF 是修复前产物；未覆盖用户附件，也未修改 issued `INV-0007` 数据。

## 验证

- 先失败后修复：打印 CSS specificity 回归先失败，修复后 `backend/tests/test_cms_panels.py` 相关 4 项通过。
- 相关测试：`36 passed, 9 skipped`。
- 完整 pytest（双角色 PostgreSQL）：`2694 passed, 7 skipped`。
- `backend/scripts/verify_local.sh`：`All checks passed`；tenant isolation `254 passed, 0 failed`；legacy smoke `73/73`。
- `git diff --check`：通过。

## 发布边界

- v10.7.0 production/package 事实保持历史基线，不重写、不复用。
- v10.7.1 的 Xero 仍是 Preview；本轮没有 OAuth、provider transport、worker 或 webhook。
- 浏览器未在生产环境登录并保存新的金融 PDF；本地真实 `INV-0007` 已完成 DOM/CSS/标题/清理生命周期验证。N-payer 多候选和 credits-only 新退款交易继续由 PostgreSQL 合同覆盖，未凭空制造生产金融数据。

