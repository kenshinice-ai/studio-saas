# PWE Studio v10.7.1 修复验收证据

> 状态：v10.7.1 已发布并完成生产/浏览器验收；本文件保留限制与四层真相。
>
> 基线：v10.7.0 的提交、归档包、hash 或生产证据不改写；v10.7.1 的
> source/runtime/package/production 以 `docs/HANDOFF_LATEST.md` 的发布闭环为准。

## 1. 执行边界

本证据文件严格对应
`docs/design/Repair_Execution_Checklist_v10.7.1_Luna_Max.md`。P0/P1 修复、
本地门禁、commit、push/sync main、SaaS/Edition package、production deploy
和浏览器验收均已完成。v10.7.0 的 package 不被复用；v10.7.1 的最终 artifact
hash、BUILD_INFO、备份和生产运行时身份在 handoff 闭环中单独记录。

## 2. INV-0007 客户 PDF 修复

### 修复前证据

用户提供的 `/Users/llmacbookpro/Downloads/Let's Paint Studio CMS.pdf` 是 2 页
A4 空白输出，只包含浏览器标题 `Let's Paint Studio CMS`、本地 CMS URL 和页码。
本地数据库中的 issued `INV-0007` 并非空单据：收件人是 Ana Bianchi，行项目为
`test`，金额为 `$1,999.00 + GST $199.90 = $2,198.90`，状态为 `paid`。

### Root cause

`legacy-root/index.html` 原来的 `body.invoice-print-mode #root *` 使用了带 ID 的
选择器，其 specificity 高于客户单据的可见性恢复规则，导致
`.invoice-customer-document` 也保持 `visibility:hidden`。所以浏览器打印输出空白，
不是 `InvoiceDocument` 数据缺失或金额计算错误。

### 修复

- `legacy-root/index.html`：打印时只隐藏 `#root` 的直接 CMS 外壳，保留客户单据
  根节点显式可见；保留 A4 margin、跨页表头、CJK/system font、黑白可读规则。
- `legacy-root/src/panels/billing.jsx`：发票与贷记单共用客户打印入口，数据只读
  `detail.document` / `creditNoteDetail.document`；临时设置浏览器标题，例如
  `Tax Invoice · INV-0007`，`afterprint` 后恢复 CMS 标题。
- 重新运行 `bash backend/scripts/build_cms.sh`，同步
  `backend/frontend/assets/cms-app.js`、`asset-manifest.json`；公共模板通过
  workspace generator 刷新，没有逐租户手改。

### 浏览器证据

- 本地 CMS：`http://localhost:8899/lets-paint-showcase/cms?lang=en&view=billing`
- 账户：本地 owner 会话；对象：`INV-0007`；语言 English。
- 真实 DOM 文档标题为 `Tax Invoice`，内容包含单号、issue/due date、supplier、
  recipient、`test` 行、税额、total、paid 和 balance；内部 event history、actor、
  request ID、bridge ID、操作按钮不在 `.invoice-customer-document`。
- 运行时样式表确认打印隐藏选择器为
  `body.invoice-print-mode #root > *`，客户根节点可见性规则正常生效。
- 点击“打印 / 存为 PDF”后浏览器标题短暂使用单据标题，打印清理完成后恢复
  `Let's Paint Studio CMS`。附件 PDF 保留为修复前证据，未覆盖、未修改。

## 3. 清单完成矩阵

| 项目 | 状态 | 证据 |
|---|---|---|
| P0-01 公共导航 | completed | 共享 public-shell CSS、四级导航状态机、模板/工作区生成输出；公共矩阵已覆盖 375/768/1024/1226/1366/1440/1920 的 overflow 与桌面语义断言。 |
| P0-02 充值/退款幂等与来源 | completed | migration `0044_credit_refund_source.sql`、统一 settlement/refund service、tenant+student source 约束、requestId 重放/冲突/跨租户测试。 |
| P0-03 贷记单税率 | completed | 原始 invoice line tax-rate snapshot 继承；full/partial/custom/rounding fixture 与 `InvoiceDocument` 端到端断言。 |
| P0-04 客户打印单据 | completed | 本文第 2 节；客户根节点隔离、snapshot-only、标题/字段/内部历史回归。 |
| P0-05 付款方 0/1/N | completed | 0 payer 可编辑并显式创建、1 payer snapshot 提示、N payer 明选、自定义 person/org 先搜索后创建。 |
| P1-01 invoice draft aggregate | completed | tenant-scoped `invoice_draft_create` requestId、unknown-field reject、payer duplicate preflight、事务回滚测试。 |
| P1-02 accounting readability/export | completed | credited/fully-credited 状态派生、invoice/credit-note/payment/refund CSV contract、公式注入保护。 |
| P1-03 Xero 前置合同 | completed | DTO/product-truth tests；transport/OAuth/worker/webhook 仍为 Preview，不称为已同步。 |

## 4. 精确验证结果

```text
backend/tests/test_cms_panels.py（打印相关）: 4 passed
相关 money/invoice/CMS/Xero 测试: 36 passed, 9 skipped
全套 PostgreSQL pytest: 2694 passed, 7 skipped
legacy CMS smoke: 73/73
tenant isolation: 254 passed, 0 failed
backend/scripts/verify_local.sh: All checks passed
git diff --check: passed
```

本地全套 pytest 使用双角色连接：
`studiosaas_app` 运行应用路径，`llmacbookpro` 运行 owner/migration 路径；
没有把仅 SQLite 或无 RLS 的结果当作隔离证据。

## 5. 已知未关闭的验收限制

- 当前本地 showcase 数据没有真实 N-payer 学员，因此 N-payer 的浏览器“多候选
  明选”由静态/集成合同覆盖；未为验收凭空创建金融或付款方记录。
- 当前可见 credits-only 来源均已全额退款或不可安全重放；没有在浏览器提交新的
  退款金融交易。credits-only/document-adjusting 的 source limit、权限和 rollback
  由 PostgreSQL 测试覆盖；生产验收必须使用明确授权的测试来源并保存 DB before/after。
- 浏览器控制器不能直接把系统打印预览写回用户附件路径；本轮验证了打印 DOM/CSS、
  文档标题和清理生命周期。正式发布后仍需在目标浏览器保存一次 PDF，搜索文字、
  中文字体、页数和换页。

## 6. 四层真相与发布闭环

| 层 | v10.7.1 当前事实 |
|---|---|
| Source HEAD | v10.7.1 repair implementation and release docs are committed and pushed to `main`; exact closure commit is in the latest handoff. |
| Runtime | `APP_VERSION=10.7.1` and production `BUILD_INFO` identify the deployed release commit; this is not inferred from `VERSION`. |
| Package | SaaS/Edition v10.7.1 archives passed checksum, `BUILD_INFO`, exclusion and smoke gates; exact hashes are in the latest handoff. |
| Production | `pwestudio.online` runs v10.7.1 with `db=ok`, `mode=saas`, `themes.tenants=4`, `themes.unreadable=0`, `workspaces.tenants=4`, `workspaces.stale=0`; the database still has six tenant rows, with archived/paused status changes audited to the user. |

生产部署还额外验证了 HTTP→HTTPS、公开关键路由、CMS immutable bundle hash/ETag 304、
桌面/移动导航与公开 portal；本地真实 `INV-0007` 打印文档验证了客户单据内容、
`Tax Invoice · INV-0007` 标题和 afterprint 清理。
