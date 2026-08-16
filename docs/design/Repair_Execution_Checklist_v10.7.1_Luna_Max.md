# PWE Studio v10.7.1 第二轮修复执行清单（Luna-Max）

> 基线日期：2026-08-16（Australia/Melbourne）
>
> 执行模型：`gpt-5.6-luna-max`
>
> 基线：Source `main == origin/main == 1155bbd30f5f151f26fb44fbf89f47035100dc5a`；
> v10.7.0 运行时提交 `913c6f168052213535fbeae9da0197de9e655959`；
> Production `pwestudio.online` 深健康为 `appVersion=10.7.0`、`db=ok`。
>
> 本文件是下一轮实施清单，不是已完成声明。每一项必须以代码、数据库、测试和真实浏览器证据关闭。

## 0. 执行规则

1. 从当前 `main` 开始；先记录 `git status --short --branch`、`git rev-parse HEAD`、`VERSION`，不得覆盖无关用户修改。
2. 目标补丁版为 **v10.7.1**。不得修改或复用已经发布的 v10.7.0 包、hash、标签或运行时提交。
3. 先为每个已确认缺陷增加“修复前失败、修复后通过”的回归测试，再修改实现。
4. 不用 `overflow-x:hidden`、更早显示汉堡菜单、隐藏正式单据字段、解析备注字符串或吞掉重复请求来制造绿色结果。
5. 所有钱款、课时、付款方和来源关系都必须 tenant-scoped；跨租户 ID 在可信边界返回不可枚举的 404/业务错误。
6. 保持“不猜、不静默丢弃、不自动合并”：历史无法确认来源的退款保留 `NULL` 并列入审计报告；重复付款方只提示并要求显式例外，不自动合并。
7. `legacy-root/src` 是 CMS 源；`backend/frontend/assets/cms-app.js` 是构建产物。先改源，再运行项目现有构建脚本，禁止只改 bundle。
8. `tenant-template` 是公共页面权威模板；`tenants/*` 是生成工作区。先改模板/共享资产，再用现有 workspace 生成流程刷新，禁止逐租户手工补丁。
9. Xero 继续保持 `Preview`；本轮不接 OAuth、真实 transport、worker 或 webhook，也不得把队列记录称为“已同步”。
10. P0 全部通过后才做 P1。P1 完成后运行完整门禁并停在最终发布 STOP GATE；没有 Lee 的明确授权，不 commit、push、package 或 deploy。

## 1. 第二轮审计结论

### 1.1 已确认，不需要重做

- v10.7.0 已建立 `billing_accounts.kind=person|family|organisation`、学员与付款方 0/1/N 关系、issued supplier/recipient snapshots、InvoiceDocument、发票 CSV、充值/退款跨账本 bridge 和 request-id 表。
- 生产深健康正常；v10.7.0 package/runtime 不应被原地改写。
- 当前目标测试仍为绿色：本轮审计运行相关 public shell、payer、invoice、settlement/refund、document/export、CMS tests，结果 **84 passed, 6 skipped**。
- 上述绿色结果不覆盖下面的缺陷；尤其“无横向溢出”不等于“桌面导航模式正确”。

### 1.2 已复现缺陷与优先级

| ID | 优先级 | 当前事实 | 风险 |
|---|---:|---|---|
| NAV-01 | P0 | 生产 `/lets-paint-showcase/showcase` 与 `/timetable` 在 1440px 仍为 `brand-name-hidden nav-tight`，桌面链接 `display:none`，只显示汉堡；timetable 从 901 到 1920px 均如此 | 桌面导航被错误降级；第一轮只验了无 overflow |
| NAV-02 | P0 | home 已把 `.navrow` 扩到 1600px，showcase/timetable 仍各自复制 1180px 旧合同；1226px 的 home 也仍会整体折叠 | 同一公共产品壳在页面间漂移；用户截图可复现 |
| CR-01 | P0 | 未勾选发票的充值 UI 仍调用旧 `/credit-transactions`，没有 `requestId` 幂等；新 settlement service 明明支持 `createInvoice=false` 却未被使用 | 网络重试/重复点击可能重复充值 |
| CR-02 | P0 | 未勾选“同步处理原发票与付款”的退款仍走旧接口，只把原充值 ID 写进 `note`；`refundable_purchases()` 只累计 bridge 中的退款 | 同一笔原充值可被重复选择，来源剩余额度计算不可信 |
| CR-03 | P0 | 贷记单行把原 10% 税率按退款占比再次缩放；例如 10% GST 的退款行可写成约 91bp，虽然 tax/total cents 恰好平衡 | CSV/Xero/单据税率元数据错误；现有测试未断言税率 |
| DOC-01 | P0 | “打印 / 存为 PDF”打印整个 CMS 详情区域；没有供应方完整抬头/ABN/地址、收件方完整资料、issue/due 元数据，却包含内部事件历史 | 不能作为合格客户发票或 PDF fallback |
| PAYER-01 | P0 | 学员没有付款方时，UI 说“保存前人工复核”，但只显示预填摘要，没有可编辑付款方字段；提交会隐式创建并在开具时冻结 | 错误法律收件人可能进入 issued snapshot |
| INV-01 | P1 | 手工发票创建是“创建 payer → 创建 draft → 逐行 POST”；任一步失败后重试可能留下重复 payer、重复/半成品草稿 | 数据质量与恢复体验差；没有 aggregate idempotency |
| PAYER-02 | P1 | API 在付款方已经创建后才返回 `possibleDuplicates`，两个 UI 调用方均忽略该字段 | 强重复提示太晚且不可见 |
| DOC-02 | P1 | 现有 CSV 只覆盖 invoice summary/lines；没有客户可用的 credit-note document/export，且 fully credited 仍只显示底层 `paid` 状态 | 对账和 Xero 前置合同仍不完整 |

## 2. P0-01 公共导航：恢复真正的桌面模式

### 目标

让 portal、showcase、timetable 使用一个导航布局合同。汉堡菜单只在移动端或真实空间不足时出现；不能因为页面复制了旧的 1180px 上限而在所有桌面宽度永久折叠。

### 主要文件

- `backend/frontend/assets/public-surface.js`：`fitNavigation()`、`queueFitNavigation()`、`settleNavigation()`。
- `tenant-template/index.html`
- `tenant-template/showcase.html`
- `tenant-template/timetable.html`
- 建议新增 `backend/frontend/assets/public-shell.css`，承载三页共享 nav/mobile-nav 样式。
- `backend/studiosaas/workspaces.py`：仅当共享资产/模板刷新需要调整生成逻辑时修改。
- `backend/tests/test_public_shell.py`
- `backend/tests/test_showcase_tenant.py`
- 生成输出：`tenants/*/index.html`、`showcase.html`、`timetable.html`；只通过现有生成流程刷新。

### 实施步骤

- [ ] 新增浏览器回归，先在修复前证明：lets-paint-showcase English 的 showcase/timetable 在 `1226/1366/1440/1920` 出现 `nav-tight`，而 1440 home 为 full nav。
- [ ] 把三页的 `.navrow/.brand/.brand img/.navlinks/.langtog/.menu-btn/#mnav` 基础规则移入一个共享资产；模板只保留页面特有样式。
- [ ] 删除或禁止三页重新声明冲突的 nav 宽度、logo cap、gap、断点。静态测试必须断言共享资产存在且页面没有重写关键选择器。
- [ ] 统一桌面容器上限，至少与当前 home 的 `max-width:1600px` 一致；不要让 showcase/timetable 停在 1180px。
- [ ] 给测量状态机增加四级退化顺序：`full` → `brand-name-hidden` → `nav-compact` → `nav-tight`。
- [ ] `nav-compact` 只压缩非关键空间：wordmark 最大宽度、nav gap、非 CTA 横向留白；不降低 44px 触控目标、不把标签换成只有图标、不隐藏当前页或主要 CTA。
- [ ] 每进入一个测量 rung 前都先清除旧输出 class，再读取该 rung 的自然尺寸；状态切换后重新计算 gap/logo/links 的 need，不能复用上一 rung 的旧值。
- [ ] 保留当前有界的 load/font/contract settling 与 resize 监听；不要用监听自身输出的 `ResizeObserver` 形成反馈循环。
- [ ] 移动菜单打开时锁定 `aria-expanded=true`；点击链接或 Escape 关闭，Escape 后焦点回菜单按钮；从移动扩回桌面时强制关闭 `#mnav` 并重置 `aria-expanded=false`。
- [ ] 语言切换、字体完成加载、contract 使某些链接显隐后都重新 settle；不能只在首次 load 测量。
- [ ] 运行 workspace 生成，检查 lets-paint-studio 与 lets-paint-showcase 的三个页面 diff；不手改生成输出。

### 明确验收

- [ ] lets-paint-showcase English：`1226/1366/1440/1920` 的 portal/showcase/timetable 都显示桌面链接，汉堡隐藏；允许 1226 使用 `nav-compact`。
- [ ] `1024` 若完整导航无法在不截断主要语义的情况下容纳，可以使用汉堡；`375/768` 必须使用汉堡。
- [ ] Chinese 与 English、logo-only、无 logo、长品牌名、8 个公开入口全部验证。
- [ ] 走一遍 `1440 → 375 → 1440` 与 `375 → 1440`，最终 class/display 与新加载 1440 完全一致，无 sticky `nav-tight`。
- [ ] 每个宽度断言：`documentElement.scrollWidth == clientWidth`、logo/按钮 rect 在 viewport 内、没有两行 CTA、没有 console error。
- [ ] 测试必须断言“桌面 links visible + menu hidden”，不能再只断言“没有 overflow”。

## 3. P0-02 充值与退款：所有业务分支统一进入幂等服务

### 目标

Checkbox 只决定是否创建/调整钱款单据，不决定是否绕过可靠的 command service。无发票充值、只退课退款也必须有 request id、明确来源、tenant-scoped 锁和可重放结果。

### 主要文件

- 新 migration：`backend/db/migrations/0044_credit_refund_sources.sql`
- `backend/studiosaas/services/credit_settlements.py`
- `backend/studiosaas/services/credit_refunds.py`
- `backend/studiosaas/api_v1.py`
- `legacy-root/src/cms-app.jsx`
- `backend/tests/test_credit_settlements.py`
- `backend/tests/test_credit_refunds.py`
- `backend/tests/test_money_layer.py`
- `backend/tests/test_cms_panels.py`
- `backend/studiosaas/services/tenant_archive.py`
- `standalone-edition/tools/import_tenant_bundle.py`
- `docs/API.md`、`docs/Database.md`

### 3.1 migration 0044：建立所有退款的来源关系

- [ ] 给 `credit_transactions` 增加 nullable `source_credit_transaction_id`。
- [ ] 使用 `(tenant_id, source_credit_transaction_id) → credit_transactions(tenant_id,id)` composite FK，`ON DELETE RESTRICT`；增加 `(tenant_id, source_credit_transaction_id)` index。
- [ ] DB trigger/check 保证：只有 `transaction_type='refund'` 可以有 source；source 必须是同 tenant、同 student 的 `purchase`；不能 self-reference。
- [ ] 允许同一 purchase 有多个 partial refunds，不加错误的 unique source 约束。
- [ ] 从现有 `credit_financial_links.related_credit_transaction_id` 确定性回填已联动退款。
- [ ] 不解析历史 `note` 中的 UUID 来猜来源；输出未链接历史 refund 的 tenant/record count，保留 `NULL`。
- [ ] archive/export/restore、Edition schema/manifest 与 RLS/tenant isolation 检查加入新列/关系。
- [ ] fresh install、10.7.0 upgrade、重复执行 migration、Edition restore 四条路径通过。

### 3.2 所有充值统一 `/credit-settlements`

- [ ] CMS top-up 无论 checkbox 是否勾选，都调用 `/students/<id>/credit-settlements`。
- [ ] 未开票分支发送 `billing.createInvoice=false`，不发送 account/tax/issue/payment 字段；金额可为 0（赠课）或正数。
- [ ] 相同表单签名复用同一 `requestId`；改变学员、课时、金额、套餐、方式、备注或 billing choice 后生成新 ID。
- [ ] 删除 top-up UI 对旧 `/credit-transactions` purchase 分支的调用；旧 endpoint 只保留兼容/调整用途，不删除公共 API。
- [ ] 断言同 requestId/same payload 返回同一 transaction；same requestId/different payload 返回 409；网络响应丢失后的重试不重复充值。
- [ ] 断言 Decimal 课时、package credits、signed `fee_aud_cents`、余额与 audit 一致，完全不使用旧 float 路径。

### 3.3 `/credit-refunds` 同时支持两个 checkbox 分支

- [ ] `billing.adjustDocuments=false` 不再返回“use legacy endpoint”；同一 service 处理 credits-only refund。
- [ ] 两个分支都必须传 `sourceCreditTransactionId`、`requestId`、credits、amount、reason，锁定 source purchase 与 credit account。
- [ ] credits-only 可支持 `$0`（赠课退回）；document-adjusting 必须金额大于 0 且有完整 invoice/payment bridge。
- [ ] 创建 refund credit transaction 时写 `source_credit_transaction_id`；document-adjusting 分支同时保留 `credit_financial_links`。
- [ ] `refundable_purchases()` 从所有 source-linked refund transactions 累计 refunded credits/amount，而不是只看 financial bridge。
- [ ] `availableCredits` 以该 source purchase 为上限；不能借学生其他 purchase 的余额重复退款。
- [ ] 仍检查学生当前总余额，防止已消耗课时被退款；source limit 与 current balance 两道检查都要保留。
- [ ] credits-only 权限只要求 `credits:refund`；联动单据额外要求 `payments:refund` 与 `billing:issue`，不能因为统一 endpoint 扩权。
- [ ] UI 两个分支都调用 `/credit-refunds`；删除把 source UUID 拼进 note 的伪关联。
- [ ] 成功后刷新 source list；fully refunded source 隐藏或明确 disabled，不可再次选择。

### 3.4 回归矩阵

- [ ] purchase：免费、付费未开票、开票未收款、开票已收款。
- [ ] refund：credits-only `$0`、credits-only 正金额、document full、document partial、多次 partial、最后一笔 rounding remainder。
- [ ] 同 source 先 credits-only 再尝试 document refund，以及相反顺序；累计 credits/amount 不能超过原 purchase。
- [ ] same/different request payload、并发两个 request、事务中途异常 rollback。
- [ ] 跨 tenant source、跨 student source、refund→refund source、self source 全部失败且不泄漏记录存在性。
- [ ] 每个失败分支断言 credit balance、transaction count、invoice/payment/credit-note/bridge count 均未变化。

## 4. P0-03 贷记单税率与文档一致性

### 主要文件

- `backend/studiosaas/services/credit_refunds.py`
- `backend/studiosaas/services/invoice_documents.py`
- `backend/tests/test_credit_refunds.py`
- `backend/tests/test_invoice_documents.py`

### 实施步骤

- [ ] 修复 `INSERT INTO credit_note_lines ... SELECT`：`tax_rate_bp` 继承原 invoice line 的税率，不得乘以退款比例。
- [ ] partial refund 只按比例拆 `net_cents/tax_cents`，最后一笔吸收 rounding remainder；税率仍是原税码的 0/1000/其他 bp。
- [ ] 若 schema 支持 `tax_code_id`，同时继承原 tax code；若不支持，文档说明本轮只保留 rate snapshot，不虚构 mapping。
- [ ] 测试 10% GST 的 full/20% partial/30% partial/最后 50%：每张 credit-note line `tax_rate_bp=1000`，累计 net/tax/total 等于原行。
- [ ] 增加非 GST、非 10% 自定义税率、1-cent rounding fixture。
- [ ] 用 `build_credit_note_document()` 对退款结果做端到端断言，不只查询 credit note header totals。

## 5. P0-04 合格的“打印 / 存为 PDF”客户单据

### 目标

在 server-side PDF renderer 尚未满足 SaaS/Edition/CJK 发行条件时，提供诚实且完整的浏览器打印单据。它必须是客户发票，不是 CMS 内部详情截图。

### 主要文件

- `legacy-root/src/panels/billing.jsx`
- `legacy-root/index.html`
- `backend/studiosaas/services/invoice_documents.py`
- `backend/studiosaas/api_v1.py`：invoice detail/document DTO；仅在字段缺失时调整。
- `backend/tests/test_cms_panels.py`
- `backend/tests/test_invoice_documents.py`
- `backend/tests/test_invoice_exports.py`

### 实施步骤

- [ ] 新增专用 `InvoicePrintableDocument`（或等价组件），数据只来自 `detail.document`；issued 单据不得回读 live payer/tenant identity。
- [ ] 标题按 supplier snapshot 的 GST 状态显示 `Tax Invoice` 或 `Invoice`；显示号码、状态、issue date、due date、currency。
- [ ] supplier 区包含 legal/trading name、ABN、完整地址、email/phone/website；只显示 snapshot 中确实存在的字段。
- [ ] recipient 区包含 display/company/contact name、ABN、billing address、email/mobile、PO reference。
- [ ] 行项目包含 description、quantity、unit price、net、tax rate/tax、gross；使用 integer cents/Decimal string，不在 UI 重新计算法律金额。
- [ ] totals 包含 subtotal、GST/tax、total、paid、credited、balance；显示 note、payment note 与 bank/remittance 信息（有值才显示）。
- [ ] 客户打印区不得包含内部 event history、actor、request ID、bridge ID、审计日志、操作按钮或 CMS 导航。
- [ ] 独立 `.invoice-customer-document` 作为唯一 print-visible 根；不要继续让整个 `.invoice-printable` 的内部卡片都可见。
- [ ] A4 print CSS：`@page`、12–16mm margins、CJK/system font、表头跨页、行不截断、长机构名/地址换行、黑白打印可读、颜色不是唯一状态信号。
- [ ] draft 若允许预览，必须有明显 `DRAFT / 草稿` watermark 且无正式号码；当前按钮继续只对 issued 系列开放也可。
- [ ] 按钮继续命名“打印 / 存为 PDF”，不得写“下载 PDF”；不要增加假的 `/pdf` endpoint。

### 明确验收

- [ ] fixtures：个人、机构、无 ABN、GST、非 GST、中英混排、长地址、多页行项目、paid、part-paid、credited/fully credited。
- [ ] DOM contract 断言所有法定/业务字段来自 `detail.document`，内部 history 不在 customer document 内。
- [ ] 浏览器打开打印预览或等价 print-emulation；保存结果可搜索文字、中文无方框、页数与换页合理。
- [ ] 打印金额逐项与 API DTO、summary CSV、line CSV 对比一致。

## 6. P0-05 付款方 0/1/N 的真实可编辑状态

### 主要文件

- `legacy-root/src/panels/billing.jsx`：`BillingAccountPicker`、`NewInvoiceDialog`。
- `legacy-root/src/cms-app.jsx`：top-up 内复用的 picker。
- `backend/studiosaas/api_v1.py`：billing account search/create，仅在需要支持预检合同时修改。
- `backend/tests/test_cms_panels.py`
- `backend/tests/test_money_layer.py`

### 实施步骤

- [ ] 学员 0 payer：把 student suggestion 填进可编辑 payer form；姓名、类型、email/mobile、地址、language、payment terms 在创建前可修正。
- [ ] 不再因为 suggestion 有 name 就静默生成 `createPayload`；必须由操作员按“创建并使用此付款方”明确确认。
- [ ] 学员 1 payer：可以默认选中，但清楚显示将冻结到发票的名称/类型/联系方式，并允许改选“其他个人或机构”。
- [ ] 学员 N payer：保持无默认值，必须显式选择；显示每个 payer 的 kind、email/mobile/organisation，避免同名误选。
- [ ] custom 模式先搜索后创建；切换 student/custom 不丢 invoice lines、note、credits/amount 等上层表单状态。
- [ ] 错误焦点落在首个 actionable field，并用 `aria-describedby`；所有控件 >=44px，375px 单列。
- [ ] custom 关联 0..N 学员不要依赖难用的原生 `multiple` 长列表；复用 StudentPicker + 已选 chips/删除按钮。
- [ ] 中英文 UI 文案都明确“学员是服务对象，付款方是法律收件人”。

### 验收

- [ ] 本地真实浏览器走完：0 payer 建新、1 payer 默认、N payer 明选、自定义 person、自定义 organisation、同名 payer。
- [ ] 在 issue 前修改 payer，issued snapshot 使用最终确认值；issue 后修改 live payer，旧单据保持不变。
- [ ] 取消 dialog 不创建 payer；表单验证失败不创建 payer。

## 7. P1-01 手工发票 aggregate command 与重复保护

### 目标

把“选/建付款方 + 建 draft + 多行”变成一次 tenant-scoped、idempotent transaction。现有细粒度 routes 保持兼容，但 CMS 新建流程只走 aggregate command。

### 建议合同

`POST /billing/invoice-drafts`

```json
{
  "requestId": "uuid",
  "payer": {"accountId": "uuid"},
  "invoice": {"note": "", "purchaseOrderRef": ""},
  "lines": [
    {"description": "", "quantity": "1.00", "unitPriceCents": 10000,
     "taxRateBp": 1000, "sourceKind": "manual", "studentId": null}
  ]
}
```

`payer` 必须是 `{accountId}` 或 `{create:{...}, linkedStudentIds:[...]}` 二选一；不得同时发送。

### 主要文件

- 建议新增 `backend/studiosaas/services/invoice_drafts.py`
- `backend/studiosaas/api_v1.py`
- migration 0044 或下一 migration：仅在 `financial_operation_requests.operation_kind='invoice_draft_create'` 已够用之外确有 schema 需要时增加；不要为新 endpoint 重复建幂等表。
- `legacy-root/src/panels/billing.jsx`
- `backend/tests/test_money_layer.py`
- 建议新增 `backend/tests/test_invoice_drafts.py`
- `backend/tests/test_cms_panels.py`
- `docs/API.md`

### 实施步骤

- [ ] 在服务入口严格 reject unknown fields；先验证所有 payer/student/tax/line 数据，再写任何记录。
- [ ] 同事务创建可选 payer、member links、invoice draft 与所有 lines；任一行失败全部 rollback。
- [ ] 使用 `(tenant, requestId, invoice_draft_create)` 幂等；same payload replay 返回相同 payer/invoice/line IDs，不同 payload 409。
- [ ] payer 强重复预检在创建前完成：ABN exact、normalized email/mobile 返回候选；默认阻止并返回可操作 409。
- [ ] 只有操作员显式勾选/提交 `allowPossibleDuplicate=true` 才继续；记录 actor、候选 IDs 与原因，不自动合并。
- [ ] CMS retry 保持同 requestId；修改任意法律/金额字段后生成新 requestId。
- [ ] 异常测试在第 2 行插入前/后、payer member link、audit、response loss 处注入失败，确认没有半成品。

## 8. P1-02 账务可读性与导出补齐

- [ ] 从 `total/paid/credited/balance` 派生 UI 状态“部分贷记 / 已全额贷记”；不篡改底层 payment `paid/refunded` 事实。
- [ ] invoice list/KPI 的“已收到”和余额统计明确如何处理 credited/refunded，增加回归测试，避免把已退款仍算净收款。
- [ ] 提供 credit-note detail/document export，复用 `InvoiceDocument` primitives；不要复制金额算法。
- [ ] CSV 明确区分 invoices、credit notes、payments、refunds；导出范围与权限可见，公式注入保护覆盖所有用户文本列。
- [ ] 退款金额默认按原 purchase 的未退比例自动建议；允许人工改金额时显示有效单价/偏差警告并要求理由，不替用户猜税务决定。
- [ ] 为 payer 增加独立查看/编辑入口；issued 历史继续读 snapshot，不因 live record 更改而漂移。

## 9. P1-03 Xero 前置合同，不做 transport

- [ ] Xero mapper fixture 使用本轮修正后的 invoice/credit-note Document DTO 与原始 tax rate；不得从 CMS 文本或 live payer 重建。
- [ ] 增加 product-truth test：`TRANSPORT_AVAILABLE=False` 时所有 UI/文档只能显示 Preview/准备导出，不出现“已同步”。
- [ ] 为未来 Contact → Invoice → Payment → Credit Note/Refund 明确 local object/revision/hash 输入合同。
- [ ] 不创建 OAuth app、token schema、worker、webhook 或生产连接；这些继续留在独立 Xero Beta 项目。

## 10. 验证顺序

### 10.1 每个 P0 完成后

- [ ] 运行对应 targeted pytest；记录 exact passed/skipped，不用“all green”代替数字。
- [ ] `git diff --check`。
- [ ] 涉及 CMS 时运行现有 `backend/scripts/build_cms.sh`，然后验证 source/bundle/manifest。
- [ ] 涉及公共模板时刷新合成 tenant workspace，验证 source 与 generated output 一致。
- [ ] 涉及 migration 时在 fresh/upgrade/Edition restore 数据库运行并记录 schema/invariant 查询。

### 10.2 综合本地验收

- [ ] `.venv/bin/pytest` 全套。
- [ ] `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`。
- [ ] legacy CMS smoke、tenant isolation、Edition checks、terminology、Python compile、inline HTML scripts、JS parse、bundle/manifest 全部运行。
- [ ] 浏览器 public matrix：375/768/1024/1226/1366/1440/1920，中英、明暗代表主题、3 个 public routes、移动菜单键盘路径。
- [ ] 浏览器 billing matrix：375/768/1024/1440；payer 0/1/N、自定义 person/org、invoice draft/issue/print/CSV、top-up checkbox 四组合、refund checkbox 两组合。
- [ ] 每个钱款流程保存 DB before/after：credit transactions/account balance、invoice/line/payment/allocation、credit note/refund、source relation、financial bridge、operation request、audit。
- [ ] 浏览器检查 console error、横向 overflow、focus/error recovery、retry replay 与刷新后的持久状态。

## 11. v10.7.1 唯一发布 STOP GATE

- [ ] P0/P1 范围与 deferred 项写入新的 acceptance evidence，不覆盖 v10.7.0 历史证据。
- [ ] 将 `VERSION`、`APP_VERSION`、README、API/Database、Release Notes、role guides 与 `docs/HANDOFF_LATEST.md` 准备为 v10.7.1；不能提前写“已部署”。
- [ ] 生成 SaaS/Edition archives，在解包目录运行 smoke；记录 SHA-256 与 `BUILD_INFO`。
- [ ] 明确列出 source HEAD、runtime commit、package hash、production version 四层，不混为一条。
- [ ] **到此停止，等待 Lee 明确授权 commit → push/sync main → package → production deploy。**
- [ ] 获授权后：生产备份 → migration 0044 → deploy → workspace regeneration → internal/public deep health → browser acceptance → release ledger closure。
- [ ] 部署后重新验证 NAV-01、credits-only retry/source limit、credit-note tax rate、customer print document；HTTP 200 不能替代这些交互验收。

## 12. 本轮明确不做

- 不重写主题生成器、CMS 框架或整套 billing 架构。
- 不删除旧 `/credit-transactions` 兼容 endpoint；只让新的 top-up/refund UI 不再绕过可靠服务。
- 不从历史备注猜测或自动合并 source/payer。
- 不把浏览器打印 fallback 冒充 server PDF download。
- 不实现 Xero OAuth/transport/worker/webhook。
- 不在 P0 中加入周期账单、自动扣款、自动发送发票或任意双向会计同步。

## 13. Luna-Max 每项回报格式

每完成一个编号，按以下格式回报，不要只勾 checkbox：

1. **状态**：completed / blocked / deferred。
2. **Root cause**：一至三句，说明为什么旧实现会失败。
3. **Files**：逐一列出修改文件与函数/区域。
4. **Data contract**：migration/API/tenant/permission/idempotency 是否变化。
5. **Tests**：先失败的回归名、修复后 exact passed/skipped。
6. **Browser**：URL、viewport、language/theme、操作步骤、DOM/visual 结果。
7. **Generated artifacts**：source/bundle/workspace/manifest 是否同步。
8. **Remaining risk**：只写真实未关闭风险。
9. **Git**：`git status --short`；未到 STOP GATE 不提交。
