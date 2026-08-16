# v10.7.0 发票与资金联动统一执行清单

> 面向执行模型：`gpt-5.6-luna` / max reasoning
> 编制日期：2026-08-16（Australia/Melbourne）
> 状态：**单版本方案与执行清单；未授权实现、提交、打包或部署**
> 当前基线：`main == origin/main == 1043fe3f30e49c89358065a7ab07878f9f23e5cd`，`VERSION=10.6.4`
> 目标版本：**v10.7.0，一次开发、一次完整验收、一次 commit/package/deploy STOP GATE**

## 0. 执行规则

1. 严格按本文件顺序执行；一个任务未通过自己的验收，不进入下一任务。
2. 每开始一项先执行 `git status --short --branch`，保护与该项无关的用户改动。
3. 移动端课表修复、付款方双入口、发票快照、PDF/CSV、充值/退款联动作为一个完整 v10.7.0 发布；内部阶段只用于控制回归，不形成中间版本或中间部署。
4. 不把“选择学员”直接等同于“发票抬头”。学员是服务对象，`billing_account` 才是付款方/收件人。
5. 课时账本和钱款账本保持独立；只能通过明确、可审计的关联记录连接，禁止用备注文字猜关联。
6. 已开具发票不修改金额、行项目、付款方或历史抬头；更正使用贷记单，退款关联原付款。
7. 所有组合写入必须单事务、幂等、租户隔离。不要从前端连续调用多个现有接口来模拟原子操作。
8. Xero 在 OAuth、出站请求、任务消费和 demo organisation 验收全部完成前继续显示 `Preview`，不得把队列记录称为“已同步”。
9. v10.7.0 只有一个最终 STOP GATE；内部阶段完成后继续下一阶段。没有 Lee 对 v10.7.0 和生产主机的明确授权，不 commit/push/package/deploy。
10. Xero transport 不并入本次 v10.7.0：本次只把 snapshot、Document DTO、付款/贷记单关联和导出准备到可被 Xero adapter 安全消费；真实 OAuth/网络同步仍为后续 Beta。

## 1. 已核对的当前事实

| 项目 | 当前事实 | 证据位置 |
|---|---|---|
| Source | `main` 与 `origin/main` 都在 `1043fe3…`，工作树核对时干净 | Git；`VERSION` |
| Package | SaaS SHA-256 `d11296d32bf8132a26b87b80ab04b000b9e8869bc69501711fd92331141c319c`；Edition SHA-256 `c90da5ca9fff91af711463f1b429231eeeedba8df33bf88bb5155b31891cddc3` | `dist/*.sha256`；两个 archive 内的 `BUILD_INFO` 都指向 `1043fe3…` |
| Production | 线上 deep health 报告 `appVersion=10.6.4`、`db=ok`、6 tenants、theme/workspace 正常 | `https://pwestudio.online/v1/health?deep=1`，2026-08-16 只读核对 |
| 移动端课表 | 375×844 时 `body.scrollWidth=390`、document 约 389；菜单按钮右边界约 389.7 | `/lets-paint-showcase/timetable` 浏览器测量 |
| 溢出根因 | `.brand` 使用 `flex-shrink:0`，品牌内容约 338.7px，再加 gap、菜单按钮和容器 padding 后超过 375px | `tenant-template/timetable.html` |
| 发票付款方模型 | 已有 `billing_accounts`；一个付款方可关联 0..N 学员，机构可以完全不关联学员 | migration `0034_billing_accounts_and_invoices.sql` |
| 当前新建发票 UI | 只有固定 `select`，只能选择已经存在的 billing account；无学员搜索、无付款方内联创建 | `legacy-root/src/panels/billing.jsx::NewInvoiceDialog` |
| 当前“课时充值”发票行 | checkbox 只把 `source_kind` 写成 `package`；没有选择学员，也没有写 `sourceId`，不会创建课时流水 | `legacy-root/src/panels/billing.jsx::createInvoice` |
| 当前充值/退款 | 只调用 `/students/<id>/credit-transactions`；写课时余额和 `fee_aud_cents`，不会创建发票、付款、贷记单或钱款退款 | `legacy-root/src/cms-app.jsx::handleTopUp/handleRefund` |
| 发票历史身份 | issued invoice 的金额和 account id 被锁，但详情仍 JOIN 当前 billing account；供应方/付款方没有 issued snapshot | migration `0034`；`services/billing.py::issue_invoice`；invoice detail query |
| PDF/CSV | 有通用 CSV helper 和其他数据导出，但没有 invoice PDF、invoice summary CSV 或 line-level CSV endpoint | `backend/studiosaas/api_v1.py` |
| Xero | 数据表、闸门、对象映射和错误队列已存在；`TRANSPORT_AVAILABLE=False`，没有真实 OAuth/HTTP worker | `services/xero.py`；migration `0037_xero_integration.sql` |

## 2. 最终产品模型

### 2.1 发票收件人不是“固定人群”

新建发票的“开给谁”改成两条入口，但最终都解析为一个 tenant-scoped `billing_account_id`：

1. **已有学员**
   - 搜索并选择学员；
   - 查询该学员已关联的付款方；
   - 只有一个时默认选中但仍显示名称；
   - 没有付款方时，展示“创建付款方”表单，并从学员/监护人资料预填，保存前必须人工复核；
   - 有多个付款方时必须明确选择，禁止自动猜测或合并。
2. **其他个人或机构**
   - 先搜索现有付款方，避免重复；
   - 可新建“个人”或“机构”；
   - 个人需要姓名，机构需要机构名称；联系人、邮箱、电话、账单地址、ABN、PO reference、付款期限和语言按类型显示；
   - 可选关联 0..N 学员，默认不强迫关联。

`billing_accounts.kind` 的迁移策略：新增 `person`，保留已有 `family` 与 `organisation`。界面把旧 `family` 显示为“个人/家庭”，不批量重写历史数据；新建自定义个人使用 `person`。

### 2.2 开票与收款是两个决定

充值页不要只加一个含义模糊的 checkbox。目标控件为：

- `同时创建发票`：默认关闭；只有具备 `billing:write` + `billing:issue` 时可用；
- 开启后显示付款方选择、税码、发票备注，并出现第二个选项：
  - `款项已经收到，同时登记付款`：充值页默认开启，因为当前主按钮语义是“确认收款并入账”；
  - 关闭时：创建并开具未付款发票，但仍可发放课时，代表 studio 允许 on-account 销售；
- 免费充课或金额为 0 时关闭发票与付款联动，除非未来另行定义零金额文档合同；
- 未勾选创建发票时，保持现有课时账本行为，不虚构发票或付款。

输入金额继续代表**实际成交总额/实收总额（含税）**。如果税码是 GST 10%，服务端从 gross amount 反算 net + tax，必须保证 `net + tax == amountCents`；不能把当前实收金额直接当作未税单价再加 10%。

### 2.3 退款联动不是“负发票”

退款页目标控件为 `同步处理原发票与付款`，只在系统能找到以下完整链路时启用：

`原充值流水 → 关联发票行 → 已开具发票 → 付款分配 → 原付款`

勾选后同一事务内：

1. 新增负向课时流水；
2. 创建并开具贷记单，引用原发票；
3. 对原付款登记 refund，并把贷记单关联到 refund；
4. 写 invoice event、audit log 和跨账本关联；
5. 支持部分退课/部分退款，但累计不得超过原充值剩余课时、原行金额或原付款可退余额。

找不到完整链路时，checkbox 必须禁用并解释原因；操作员仍可执行现有“只退课时/记录现金净额”的流程。已付款发票不得直接 void；未付款且确实取消的发票可走现有 void 规则，但不由充值退款页面自动猜测。

### 2.4 两本账之间只建桥，不合并

新增 migration 建议使用 `credit_financial_links`，而不是继续借用自由文本备注：

- `tenant_id`
- `credit_transaction_id`（唯一；purchase 或 refund 流水）
- `related_credit_transaction_id`（退款时指向原 purchase）
- `invoice_id`
- `invoice_line_id`
- `payment_id`（未收款时可空）
- `credit_note_id`（purchase 时为空）
- `refund_id`（purchase 时为空）
- `created_at`

所有 FK 都必须 tenant-scoped；增加 CHECK 保证 purchase/refund 对应字段组合合法。不要删除 `invoice_lines.source_kind/source_id`：它们继续表达收入类别/业务来源，Xero 映射仍可使用 `package`；桥表表达跨账本法律/资金关系。

### 2.5 issued snapshot 是 PDF、CSV、Xero 的共同前置条件

在 `invoices` 增加 `supplier_snapshot jsonb` 与 `recipient_snapshot jsonb`；在开具事务中，从 `tenant_billing_identity` 和 `billing_accounts` 生成快照，再改变 status。开具后触发器锁定快照。

快照至少包含：

- 供应方：legal/trading name、ABN、GST 状态、地址、邮箱、电话、网站、付款说明/银行展示字段；
- 收件人：显示名称、kind、联系人、company name、ABN、邮箱、电话、账单地址、PO reference、语言；
- 快照 schema version。

草稿可显示 live data；issued/part_paid/paid/void 的 API、PDF、CSV 与 Xero payload 一律读取 snapshot。贷记单优先继承原发票快照；独立贷记单同样要冻结自己的快照。

### 2.6 PDF 与 CSV

先构建唯一的 `InvoiceDocument` DTO，网页详情、PDF、CSV 和 Xero adapter 都从这个 DTO 读取，禁止四套金额/地址格式化逻辑。

- PDF：提供 `GET /billing/invoices/<invoice_id>/pdf`，响应 `application/pdf` 和 attachment filename；支持英文、中文、长机构名、多行地址、无 ABN、GST/非 GST、部分付款与 paid 状态。
- CSV A（summary）：一张发票一行，包含 number/status/recipient/issue/due/subtotal/tax/total/paid/credited/balance/currency。
- CSV B（line level）：一条 invoice line 一行，包含发票字段、recipient、description/qty/net/tax/total/source/student。
- CSV 使用 UTF-8 BOM、明确时区/日期格式、整数分转十进制字符串；只导出当前租户；权限为 `data:export` + `billing:read`。
- PDF renderer 在实现前做独立兼容性 spike：同一 fixture 必须在 SaaS archive 与 Edition archive 都能生成并打开，中文字体必须内嵌且许可可随包分发。未通过前只允许提供“打印/另存为 PDF”，不得把它命名为直接下载 PDF。

### 2.7 Xero 同步边界

方向固定为：**StudioSaaS 是业务单据主记录；单据向 Xero 推送；Xero 的付款/状态可受控读回；不做两边任意编辑同一张发票。**

最小 scope 使用 Xero 当前 granular scopes：`offline_access`、invoice、payment、contact 和 settings 所需的最小读写 scope；不要继续按旧 broad `accounting.transactions` 新建实现。OAuth `state` 必须防 CSRF，token 必须加密存储，日志不得出现 access/refresh token。

同步顺序：Contact → Invoice → Payment；退款顺序：Credit Note → Refund/Payment adjustment。所有 mutate request 都带 Xero `Idempotency-Key`，但本地 `xero_object_links` 仍是长期幂等权威，因为提供方 idempotency 缓存不是永久数据库。

任务由 outbox/worker 消费，不阻塞开票请求；按 tenant 串行或限制并发，处理 429 `Retry-After`、短暂 5xx、token refresh、永久 validation error、dead letter 和人工 replay。Webhook 只做签名校验、快速 2xx、落库和异步读取；不在 webhook 请求里执行大同步。

实现时以 Xero 官方文档为准：

- OAuth/scopes：<https://developer.xero.com/documentation/guides/oauth2/scopes/>
- Authorization code flow：<https://developer.xero.com/documentation/guides/oauth2/auth-flow/>
- Idempotency：<https://developer.xero.com/documentation/guides/idempotent-requests/idempotency/>
- Rate limits：<https://developer.xero.com/documentation/best-practices/api-call-efficiencies/rate-limits>
- Webhooks：<https://developer.xero.com/documentation/guides/webhooks/overview/>

## 3. 单版本交付边界

| 发布 | 一次性交付范围 | 数据库 | 明确排除 |
|---|---|---|---|
| **v10.7.0** | 课表移动端溢出；发票 UI 真相；付款方双入口；`person` 类型；issued snapshots；InvoiceDocument；PDF/CSV；充值/退款与发票、付款、贷记单的原子幂等联动 | **单一 migration 0043**：recipient snapshots + credit financial links + operation idempotency | Xero OAuth/transport、provider worker/webhook、双向任意编辑 |
| 后续 Xero Beta | OAuth、worker、push/read-back、webhook、demo organisation 验收 | 下一可用 migration 编号，以 v10.7.0 合并后的实际序号为准 | 不自动打开 live push，不以连接/入队冒充同步 |

### 为什么现在合并更优

1. 付款方选择、issued snapshot、PDF/CSV 和充值退款联动共享同一个 `billing_account`、InvoiceDocument 和税额合同，拆版本会产生短暂的半成品状态。
2. 当前误导性的“课时充值发票行”不需要先做临时 UI 再重做；可以直接被真实的原子 settlement 流程替换。
3. 单一 migration 0043 能一次建立 snapshot、桥表和幂等约束，避免 0043/0044 之间存在数据库已升级但 UI/服务尚未连通的窗口。
4. 课表溢出风险独立且很小，放在统一分支第一阶段修复并锁测试，不需要为它单独走完整发布链。
5. 统一并不意味着无门禁：以下各阶段必须独立通过 targeted checks，但只有阶段 F 形成版本发布证据和 STOP GATE。

## 4. 逐条执行清单

### 阶段 A — 公共页面小修与旧伪联动清场

#### A-01 复现并锁定 public timetable 溢出

文件：

- `tenant-template/timetable.html`
- `tenant-template/showcase.html`
- `tenant-template/index.html`
- `backend/tests/test_public_shell.py`
- `backend/tests/test_public_timetable.py`

步骤：

- [ ] 保存修复前 375×844 测量：viewport、`body/document.scrollWidth`、`.brand`、`.menu-btn`、`.navrow` rect。
- [ ] 对比 portal/showcase/timetable 三个 shell 的品牌 flex contract；确认是否只修 timetable，还是把相同不变量落到共享 shell 测试。
- [ ] timetable `.brand` 改为允许收缩（至少 `min-width:0; flex:1 1 auto`），菜单按钮保持 `flex:0 0 var(--tap-min)`；品牌图/名称必须在可用宽度内 ellipsis，而不是把菜单推出 viewport。
- [ ] 不用 `overflow-x:hidden` 掩盖根因；该写法会让不可见按钮继续存在。
- [ ] 添加静态 contract test，防止 timetable 再回到 `flex-shrink:0` 且无 `min-width:0`。
- [ ] 浏览器验证 320、375、390、768、1024、1440；中英两种语言；长品牌名与 logo-only；菜单可键盘打开、Escape 关闭并归还焦点。

验收：所有宽度 `document.documentElement.scrollWidth <= clientWidth`；44×44 菜单目标完整可见；无标题/卡片新溢出。

#### A-02 移除旧“课时充值发票行”伪联动

文件：

- `legacy-root/src/panels/billing.jsx`
- `backend/tests/test_cms_panels.py`
- 由现有脚本生成的 `backend/frontend/assets/cms-app.js`

步骤：

- [ ] 删除当前“这一行是课时充值（与充值与退款对应）”checkbox；统一版不保留即将被真实 settlement 取代的临时控件。
- [ ] 手工发票如果仍需收入分类，改用明确的 `line kind` 选择器；它只表达 `source_kind=package`，不得声明会改变学员课时。
- [ ] 手工发票的可选学员归属必须是显式 StudentPicker；无选择时发送 `null`，不发送空值伪装关联成功。
- [ ] 真实充值联动只从阶段 D 的 `credit-settlements` endpoint 建立 bridge，手工 invoice line 不得自行制造 bridge。
- [ ] 添加静态 UI truth test：只有代码同时具备 settlement endpoint、bridge 写入和 UI 控件时，才允许出现“同时创建发票/同步处理原发票与付款”文案。

验收：UI 不声称不存在的跨账本联动；手工草稿/开具流程保持可用；后续真实联动只有一个入口。

#### A-03 阶段 A 内部门禁（不中止、不发布）

- [ ] targeted：`test_public_shell.py test_public_timetable.py test_cms_panels.py`。
- [ ] `bash backend/scripts/build_cms.sh` 后确认源与 bundle 同步。
- [ ] `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`。
- [ ] 记录 `git diff --check`、`git status`、测试数字和浏览器矩阵。
- [ ] 记录阶段 A 证据后继续阶段 B；不改 VERSION、不 commit、不打包、不部署。

### 阶段 B/C — 统一数据库、付款方与发票文档基础

#### B-01 单一 migration 0043：付款方、snapshot、bridge 与幂等

文件：

- 新增 `backend/db/migrations/0043_invoice_and_credit_settlements.sql`
- `backend/studiosaas/services/billing.py`
- `backend/tests/test_money_layer.py`
- `backend/tests/test_tenant_isolation_by_construction.py`
- `backend/studiosaas/services/tenant_archive.py`

步骤：

- [ ] 扩展 `billing_accounts.kind` 为 `person|family|organisation`；不重写历史 `family`。
- [ ] 给 invoices 加 supplier/recipient snapshot 与 schema version；为 credit notes 加等价快照或明确继承列。
- [ ] 创建 `credit_financial_links`，包含 purchase/refund credit transaction、related purchase、invoice/line/payment/credit note/refund 的 tenant-scoped FK。
- [ ] 创建 `financial_operation_requests` 或等价幂等表，唯一键 `(tenant_id, request_id, operation_kind)`，保存 payload hash 与结果 IDs。
- [ ] DB CHECK 约束 purchase/refund 的合法字段组合；`credit_transaction_id` 唯一；相同 request id 不得代表不同 payload。
- [ ] 更新 issued immutability trigger，issued 后 snapshot 不可改。
- [ ] `issue_invoice()` 在同一事务里生成完整快照、分配号码、写日期、改变状态和 event。
- [ ] issued invoice detail/list 不再从 live account name/address 作为权威；草稿仍可显示 live preview。
- [ ] 测试：开具后修改 billing account 和 tenant billing identity，旧发票 DTO 保持不变；新发票使用新资料。
- [ ] 测试 tenant A 不能在快照、account lookup、bridge 或 idempotency result 中引用 tenant B。
- [ ] archive/Edition manifest 与覆盖测试加入两个新 tenant-owned 表。

验收：历史单据身份稳定；跨账本基础与幂等约束一次建成；migration forward-only；RLS/composite FK/archive 检查通过。

#### B-02 API：付款方搜索、创建与学员解析

文件：

- `backend/studiosaas/api_v1.py`
- 可选新建 `backend/studiosaas/services/billing_accounts.py`
- `backend/tests/test_money_layer.py`
- `backend/test_tenant_isolation.py`
- `docs/API.md`

步骤：

- [ ] `GET /billing/accounts` 增加 `q`、`kind`、`studentId`、分页；默认只返回 active。
- [ ] 搜索覆盖 name/contact/company/email/mobile/ABN，全部 tenant-scoped。
- [ ] `POST /billing/accounts` 使用 `_reject_unknown_keys`；kind 非法返回 400，不把 DB constraint error 变成 500。
- [ ] 新建个人/机构的字段验证分开；email/phone 允许空，但格式错误时给可操作提示。
- [ ] 返回“可能重复”的建议，不自动合并；ABN 完全匹配、归一化 email/phone 可做强提示。
- [ ] 学员路径只返回已关联 payer；没有 payer 时返回可安全预填的 parent/contact 字段，但不自动保存。
- [ ] 新建 payer + link student 提供一个原子 endpoint 或服务方法，避免 account 建成但 member link 失败。
- [ ] 权限：读取 `billing:read`；创建/link `billing:write`；不扩大 staff 的钱款写权限。

验收：学员 0/1/N 个 payer、自定义个人、自定义机构、重复提示、跨租户 ID 全覆盖。

#### B-03 UI：统一 BillingAccountPicker

文件：

- `legacy-root/src/panels/billing.jsx`
- 可在同目录新增 `billing-account-picker.jsx`，但先检查当前 build 是否支持多入口模块
- `backend/tests/test_cms_panels.py`
- `backend/frontend/assets/cms-app.js`（生成物）

步骤：

- [ ] NewInvoiceDialog 增加 `已有学员` / `其他个人或机构` 两个模式。
- [ ] 学员模式复用现有 StudentPicker 交互；显示 payer 0/1/N 状态并要求明确确认。
- [ ] 自定义模式先搜索已有 payer，再显示“新建个人/机构”。
- [ ] 机构字段条件显示；ABN、PO reference、账单地址和 payment terms 可编辑。
- [ ] 创建 payer 失败时保留发票行与备注输入；切换模式也保留非破坏性输入。
- [ ] 首个错误获得焦点并用 `aria-describedby` 关联；所有目标 >=44px；375px 单列，768px 起才并列。
- [ ] 发票行的可选学员只是报告归属；不得改课时余额，不称为充值联动。

验收：两条入口都能生成同一 `billingAccountId`；关闭/重开 dialog 不制造重复 payer；中英文、键盘、375/768/1440 通过。

#### C-01 InvoiceDocument DTO

文件：

- 新增 `backend/studiosaas/services/invoice_documents.py`
- `backend/studiosaas/api_v1.py`
- `backend/tests/test_invoice_documents.py`

步骤：

- [ ] DTO 统一输出 supplier、recipient、document metadata、lines、totals、payment summary、status label。
- [ ] draft 读取 live preview；issued 系列只读 snapshot。
- [ ] 金额全部整数分进入 DTO，格式化只发生在 renderer/export 边界。
- [ ] line net 不依赖 `total-tax` 之外的浮点计算；quantity 用 Decimal string。
- [ ] 贷记单复用同一 document primitives，不复制税额算法。

验收：JSON fixture 覆盖中文、机构、无税、GST、部分付款、paid、void、长文本与四舍五入边界。

#### C-02 CSV 导出

文件：

- `backend/studiosaas/api_v1.py`
- `backend/studiosaas/services/invoice_documents.py`
- `backend/tests/test_invoice_exports.py`
- `legacy-root/src/panels/billing.jsx`

步骤：

- [ ] 增加 `/billing/invoices/export.csv?view=summary|lines&status=&from=&to=&accountId=`。
- [ ] 严格验证过滤字段和日期；最大范围/分页策略写入 API 文档。
- [ ] 使用现有 `_csv_response`，UTF-8 BOM；公式注入防护：以 `= + - @` 开头的用户文本转义。
- [ ] issued 数据从 snapshot；draft 可以选择排除或明确标记 `DRAFT`，默认 summary 包含、会计导出默认排除。
- [ ] UI 提供“发票汇总 CSV”与“行项目 CSV”，并显示当前过滤范围。
- [ ] 权限同时要求 `billing:read` 与 `data:export`；无 feature entitlement 时仍允许读取/导出历史单据。

验收：Excel/Numbers 正确打开中文；总计与 UI/数据库完全一致；跨租户无泄漏；恶意名称不能变公式。

#### C-03 PDF 下载与兼容性闸门

文件：

- 新增 `backend/studiosaas/services/invoice_pdf.py`
- `backend/studiosaas/api_v1.py`
- `backend/tests/test_invoice_pdf.py`
- `legacy-root/src/panels/billing.jsx`
- `backend/requirements.txt`、构建脚本和许可证清单（仅在 renderer 通过 spike 后）

步骤：

- [ ] 先做 renderer spike：同一 invoice fixture 在本地、SaaS archive、Edition archive 生成；检查依赖体积和系统库。
- [ ] 中文字体必须有明确许可证并随包内嵌；不依赖中国大陆不可用的远程 font CDN。
- [ ] 通过后实现 binary endpoint；文件名清洗为 `Invoice-<number>.pdf`，draft 使用稳定非敏感名称。
- [ ] 设置 `Content-Disposition: attachment`、`Cache-Control: private, no-store`、正确 content length/type。
- [ ] PDF 只从 InvoiceDocument DTO 渲染；不要查询 live billing account 绕过 snapshot。
- [ ] 视觉覆盖 1 页、跨页、多行地址、长中英文、无 logo/logo、GST、paid/part-paid/void watermark。
- [ ] 如果 spike 任一发行模式失败：发布“打印/另存为 PDF”而非“下载 PDF”，真实 endpoint 延后，不静默降级。

验收：PDF 可打开、可复制文字、中文无方框、金额与 CSV/API 一致；未经授权的用户和跨租户 ID 返回不可枚举的 404/403。

#### C-04 阶段 B/C 内部门禁（不中止、不发布）

- [ ] targeted money/invoice/API/UI/export tests。
- [ ] migration 0043 fresh DB、upgrade DB、Edition restore 三条路径。
- [ ] tenant archive/export/restore 保留新 snapshot 字段/表。
- [ ] 全套 PostgreSQL gate、CMS source/bundle、terminology、JS parse、release ledger。
- [ ] 浏览器完成两种 recipient、三种 payer 数量、PDF/CSV、light/dark、中英、375/768/1024/1440。
- [ ] 保存证据后继续阶段 D；不改 VERSION、不 commit、不打包、不部署。

### 阶段 D/E — 充值、退款与钱款单据原子联动

#### D-01 验收 migration 0043 的 bridge 与幂等基础

文件：

- `backend/db/migrations/0043_invoice_and_credit_settlements.sql`
- `backend/tests/test_money_layer.py`
- `backend/tests/test_tenant_isolation_by_construction.py`
- `backend/studiosaas/services/tenant_archive.py`

步骤：

- [ ] 用 service-level fixtures 验证 `credit_financial_links` 可完整表达 purchase 与 refund 两种链路。
- [ ] 验证 `credit_transaction_id` 唯一；原充值不能被两个 invoice line 重复开票。
- [ ] 验证 refund link 必须有 `related_credit_transaction_id`，且原记录为 purchase、当前记录为 refund。
- [ ] 验证相同 request id + 不同 payload 返回 409；相同 payload 重试可读取原结果。
- [ ] 验证 fresh install、10.6.4 upgrade、Edition restore 后 schema 形状完全一致。

验收：DB 约束本身拒绝跨 tenant、重复 link、非法字段组合和 idempotency key 复用。

#### D-02 服务：create_credit_settlement

文件：

- 新增 `backend/studiosaas/services/credit_settlements.py`
- 复用 `services/billing.py`、`services/payments.py`
- `backend/tests/test_credit_settlements.py`

建议请求合同：

```json
{
  "requestId": "uuid",
  "credits": "10",
  "amountCents": 55000,
  "paymentMethod": "bank_transfer",
  "packageId": null,
  "note": "",
  "billing": {
    "createInvoice": true,
    "billingAccountId": "uuid",
    "taxCodeId": "uuid",
    "issueNow": true,
    "paymentReceived": true
  }
}
```

步骤：

- [ ] 验证 student/account/package/tax code 全属当前 tenant。
- [ ] 检查权限交集：基础 top-up 要 `credits:write`；发票还要 `billing:write`/`billing:issue`；登记付款还要 `payments:write`。
- [ ] 锁定 credit account；创建 purchase credit transaction。
- [ ] 若 createInvoice：创建 draft、从 gross 反算 net/tax、加 package line、issue、写 snapshot。
- [ ] 若 paymentReceived：创建 payment，并只优先分配到本次 invoice；不得先偿还旧 invoice。
- [ ] 写 bridge、events、audit；最后一次 commit。
- [ ] 任一步失败全部 rollback，包括课时余额；不得留下“有课时无发票”或“有付款无课时”。
- [ ] 响应返回 transaction/invoice/payment/allocation IDs 与新余额，便于 UI 展示和重试恢复。

验收：四组合覆盖：无发票、有发票未付款、有发票已付款、免费充课；双击/超时重试不重复；税额总和精确。

#### D-03 API 与 UI：充值联动

文件：

- `backend/studiosaas/api_v1.py`
- `legacy-root/src/cms-app.jsx`
- `legacy-root/src/panels/billing.jsx`（复用 payer picker）
- `backend/tests/test_cms_panels.py`
- `backend/test_tenant_isolation.py`

步骤：

- [ ] 新增 `POST /students/<student_id>/credit-settlements`，严格字段合同；旧 credit-transactions endpoint 保留用于非联动和兼容。
- [ ] 充值表单增加两个分层 checkbox；复用 BillingAccountPicker，不复制另一套 payer 表单。
- [ ] 根据角色隐藏/禁用联动，不降低现有 top-up 权限。
- [ ] 确认弹窗完整显示：学员、课时、gross、税额、付款方、是否开票、是否已收款、付款方式。
- [ ] 页面为每次提交生成稳定 requestId；失败重试复用，修改输入后生成新 id。
- [ ] 成功 toast 提供“查看发票”入口；未开票时不出现发票措辞。

验收：网络中断重试、双击、权限不足、payer 跨租户、invalid tax、0 金额、375px 全覆盖。

#### E-01 服务/API/UI：退款联动

建议请求合同：

```json
{
  "requestId": "uuid",
  "sourceCreditTransactionId": "uuid",
  "credits": "2",
  "amountCents": 11000,
  "paymentMethod": "bank_transfer",
  "reason": "课程取消",
  "billing": { "adjustDocuments": true }
}
```

步骤：

- [ ] 退款 UI 先让用户选择一笔可退的原充值，不再仅凭学员和自由输入猜来源。
- [ ] 显示原充值剩余可退课时、金额、发票号、付款状态与已有退款。
- [ ] 只有完整 bridge 且当前角色同时有 `credits:refund`、`payments:refund`、`billing:issue` 时启用同步 checkbox。
- [ ] 服务锁定原 purchase/link/payment；计算累计退款上限。
- [ ] 同事务创建负 credit transaction、贷记单、refund、bridge、events、audit。
- [ ] partial refund 的税额按原行比例/余数规则计算，最后一笔吸收 rounding remainder，累计不得超过原税额。
- [ ] 不可退款时给业务错误，不泄漏其他 tenant 的 ID/金额。
- [ ] 未勾选时继续走现有 credits-only refund，但 UI 明确“不会改变发票或付款记录”。

验收：全额、部分、多次部分、超额、已退完、无 bridge、跨 tenant、重复 request id、角色边界全部通过。

#### F-01 v10.7.0 单版本综合验收与唯一 STOP GATE

- [ ] 对每个业务操作做数据库前后快照，验证两本账和 bridge 一致。
- [ ] 运行完整 money-layer、tenant isolation、archive/restore、CMS smoke 和 PostgreSQL gate。
- [ ] 浏览器走真实 top-up/refund 流程，不只验证 HTTP 200。
- [ ] 验证 invoice PDF/CSV 能看到联动结果；退款后贷记单、付款退款与余额一致。
- [ ] 回归阶段 A 的 public timetable，确保 320–1440px 无横向溢出。
- [ ] 统一把 VERSION、APP_VERSION、role guides、release notes、README 与 handoff 准备为 v10.7.0；生成物必须重建。
- [ ] 形成一个完整证据包：migration、targeted/full tests、SaaS/Edition runtime smoke、浏览器矩阵、source/package/production 待办。
- [ ] **在这里停止**；等待 Lee 明确授权 v10.7.0 commit → package → push → production deploy。

### 后续独立项目 — Xero Beta（不属于本次 v10.7.0）

#### P3-00 外部前提与决策门

- [ ] Lee/产品明确 Xero app 类型、目标市场和是否申请认证；普通 OAuth app 当前连接数量限制需要纳入商业计划。
- [ ] 建立 Xero demo organisation；准备独立开发/测试凭据，不使用生产租户试跑。
- [ ] 确认 redirect URI、webhook HTTPS endpoint、数据处理/隐私文本和 token 加密主密钥来源。
- [ ] 由租户会计确认 revenue/bank/clearing/tax mapping；产品不替客户编造科目或税务判断。
- [ ] 回答 single-entry gate：Square/Stripe 或其他连接器是否已经推送同一笔收款。

未满足以上条件，不修改 `TRANSPORT_AVAILABLE`。

#### P3-01 OAuth 与连接生命周期

文件：

- 新增 `backend/studiosaas/integrations/xero_client.py`
- `backend/studiosaas/services/xero.py`
- `backend/studiosaas/api_v1.py`
- migration `0044_xero_transport.sql`（若 v10.7.0 最终仍只占用 0043；执行前以仓库实际 next migration 为准）
- `backend/tests/test_xero_transport.py`

步骤：

- [ ] connect route 生成一次性 state，绑定 tenant/user/expiry/return path；callback 验证后交换 token。
- [ ] 请求最小 granular scopes 和 `offline_access`；列出授权 organisations，让用户明确选择，禁止默认猜第一个。
- [ ] access/refresh token 应用层加密；refresh token rotation 原子更新；日志和 audit 只记录连接状态/organisation id。
- [ ] reconnect/revoke/expired/error 状态完整；断连不删 object links、history、exports 或 errors。
- [ ] 只有 owner 的 `integrations:manage` 能连接/断开；manager 只看同步状态和错误。

验收：state 重放、过期、错误 tenant、token refresh 并发、revoke、secret redaction 全测试。

#### P3-02 adapter 与 payload mapping

- [ ] billing account → Xero Contact；建立 link 后不再按模糊 email 自动换绑。
- [ ] issued invoice → Xero Invoice；draft 不推；使用 snapshot、稳定 invoice number、line/tax/account mapping。
- [ ] payment → Xero Payment；只有 invoice push 成功和 bank/clearing mapping 完成后推。
- [ ] credit note/refund → Xero Credit Note/Payment adjustment；顺序依赖显式建模。
- [ ] 本地 revision/hash 进入 job；payload 变化时新 revision，不重用已失效的 provider idempotency key。
- [ ] provider validation error 保存可读摘要和 correlation id，不保存 token/整份敏感响应。

验收：golden payload fixtures、金额/税码/联系人/长文本/partial payment/credit note 与 demo org 对照通过。

#### P3-03 worker、限流、错误队列与 replay

- [ ] worker claim job 使用数据库锁，避免两个进程同时发送。
- [ ] 每 tenant 最大并发不超过 Xero 限制；读取 rate-limit headers；429 尊重 `Retry-After`。
- [ ] timeout/连接错误/部分 5xx 指数退避；validation 4xx 进入 failed 等人工修复；达到上限进入 dead letter。
- [ ] POST/PUT/PATCH 发送 `Idempotency-Key`；失败后先 GET/object link 核对，再决定新 key，避免 6 分钟缓存窗口后重复创建。
- [ ] replay endpoint 只重放同一 local object/revision；记录 actor 和原因。
- [ ] 开票请求只 enqueue，不等待 Xero；Xero 故障不能阻止 studio 开票。

验收：模拟 429、timeout、500、invalid mapping、token expiry、worker crash-after-send、重复 webhook，无重复 Xero 对象。

#### P3-04 webhook 与受控 read-back

- [ ] 验证 raw body 的 `x-xero-signature`；非法返回 401；合法请求 5 秒内 2xx。
- [ ] webhook 只存 event envelope/sequence/resource id 并 enqueue fetch；不信任 payload 作为完整账务数据。
- [ ] 按 Xero tenant id 解析本地 tenant；未知 organisation 不泄漏连接信息。
- [ ] Invoice/Contact/Credit Note update 触发 read-back；只同步允许的状态/付款字段，不覆盖本地 immutable document content。
- [ ] 防乱序、重复和 sequence gap；gap 触发 scoped reconciliation。

验收：签名、重复、乱序、未知 tenant、禁用 webhook、24 小时重试场景可观察。

#### P3-05 demo run、live gate 与产品真相

- [ ] demo org 完整跑通 Contact → Invoice → Payment → Credit Note/Refund → read-back。
- [ ] 对比 StudioSaaS PDF/CSV、数据库与 Xero UI：号码、gross/net/tax、余额、联系人一致。
- [ ] `demo_run_completed_at` 只由真实 transport 成功写入，不能由按钮直接设置。
- [ ] mapping 与 single-entry 决策完成后，才允许 owner 打开 push。
- [ ] transport 真正存在并通过上述验收后再把 `TRANSPORT_AVAILABLE=True`；同步更新 UI、客户文档与 product-truth tests。
- [ ] 先对一个明确授权的试点 tenant Beta，不全局开启。

验收：试点可暂停、断连、重连、修 mapping、重放失败任务；无重复记账；审计可追溯。

## 5. 明确不做

- 不把学员表直接塞进 invoices 取代 billing accounts。
- 不自动合并同名个人/机构。
- 不在充值页用多次 API 调用拼成“看似成功”的组合事务。
- 不把现有 `fee_aud_cents` 当成正式 payment allocation 的替代品。
- 不修改 issued invoice 来表达退款。
- 不让 Xero 回写覆盖本地已开具单据的金额/抬头/行项目。
- 不把“已入队”“已连接”或“demo data”显示成“已同步”。
- 不在 PDF 中从 live payer/tenant profile 重新读取已开具发票身份。
- 不因 Xero add-on 到期删除连接、映射、错误、对象 link 或历史导出。

## 6. 每个任务的完成回报格式

执行模型每完成一项，只报告以下内容：

1. `Task ID / status`；
2. 实际修改文件；
3. 数据/API/UI 合同变化；
4. 精确测试命令与结果；
5. tenant/theme/language/viewport 覆盖；
6. 新发现的矛盾或风险；
7. 下一项；
8. 是否到 STOP GATE。

不得用“应该可以”“看起来正常”代替验证结果。
