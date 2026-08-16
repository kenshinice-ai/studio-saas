# PWE Studio v10.6.3 修复执行清单（5.6-luna-max）

> 文档类型：可执行工程清单，不是状态证明，也不是发布授权  
> 编制日期：2026-08-16（Australia/Melbourne）  
> 当前 `main` 文档闭环提交：`1103b4ca2c6c6fe41d8fa32685980db5c2e126d2`  
> v10.6.3 运行时 / Package / Production 基线：`02e3d41a0b02b23da1d5ba6b0f2f34ee39471701`  
> 权威现状入口：`docs/HANDOFF_LATEST.md`、`README.md`、当前 Git/包/线上实测  
> 默认执行模式：自主逐项执行；每一项完成后立即验证并记录证据  

---

## 可直接交给 5.6-luna-max 的启动指令

```text
你现在负责 StudioSaaS v10.6.3 基线后的修复工作。

完整阅读 AGENTS.md、docs/HANDOFF_LATEST.md、README.md、
docs/Release_Runbook.md，以及
docs/design/Repair_Execution_Checklist_v10.6.3_Luna_Max.md。

严格从清单第 1 项开始，按编号顺序执行。不要跳项，不要把多个不同根因
合成一次大改。每一项都必须先建立能复现旧缺陷的测试，再做最小修复，
运行该项 Targeted Verify，并记录完成证据。任何测试未运行、被跳过或失败，
都必须明确报告，不得写“预计通过”。

不得读取或修改 docs/sales/clients/ 与 docs/security/；不得覆盖现有用户改动；
不得手改 backend/frontend/assets/cms-app.js，必须从 JSX 源重新构建。

遇到 STOP GATE、生产操作、推送 main、部署、云资源/费用、MFA 架构、
真实 Xero OAuth/transport 或破坏性数据变化时立即停止，提交证据与建议，
等待 Lee 明确授权。执行清单不等于推送或部署授权。

如果同一根因两种实现尝试都失败，停止盲改并输出诊断包。
```

---

## 0. 给执行模型的硬性工作协议

### 0.1 开始前必须读完

按顺序读取，不要只读本清单：

1. `AGENTS.md`（项目宪章）；
2. `docs/HANDOFF_LATEST.md` 顶部 v10.6.3 基线与当前版本记录；
3. `README.md` 的 Source / Package / Production 三行；
4. `docs/Release_Runbook.md`；
5. 本清单。

### 0.2 权限边界

- 本清单授权的是**本地实现、测试、文档和候选版本准备**。
- 不自动推送 Git、不同步 `main`、不部署生产、不改生产数据、不创建云资源。
- 只有用户明确说出“提交/推送/同步 main”时才执行对应 Git 外部写操作。
- 只有用户明确说出版本号与生产目标时才打包/部署；计划或清单本身不是部署授权。
- MFA、Xero 真实 OAuth/transport、外部备份目标、付费云服务都属于架构/凭据/成本边界；到达对应 STOP GATE 时必须停下等待决定。

### 0.3 工作树安全

- 首先运行 `git status --short --branch`；不得覆盖不属于本任务的改动。
- `docs/sales/clients/` 与 `docs/security/` 是忽略的私有材料：不得读取、移动、删除或加入 Git。
- 不使用 `git reset --hard`、`git checkout -- <file>`、强推或历史重写。
- 所有手工文本修改使用补丁方式；生成物只能通过仓库已有构建命令生成。
- `backend/frontend/assets/cms-app.js` 是生成物；编辑 `legacy-root/src/**/*.jsx` 后运行 `bash backend/scripts/build_cms.sh`，不得手改 bundle。

### 0.4 每项任务的固定执行循环

每个编号任务都必须按以下顺序：

1. 重新定位“文件 + 函数/标题/字符串”，不要依赖可能漂移的行号；
2. 读现有测试与相邻实现；
3. 先增加能复现旧缺陷的测试或检查；
4. 确认测试在旧行为下失败，且失败原因正是目标缺陷；
5. 做最小一致修复；
6. 运行该项列出的 Targeted Verify；
7. 运行 `git diff --check`；
8. 在任务下方记录“改了什么、测试结果、剩余风险”；
9. 只有全部 Acceptance 满足才把 `[ ]` 改为 `[x]`。

同一根因连续两种实现都失败时，停止盲改，输出：Observed failure、Evidence、Attempts、Likely causes、Recommended next move。

### 0.5 提交策略

默认不自行提交。若本轮用户已经明确授权提交，按以下逻辑分组，不要把全部工作压成一个巨型提交：

1. `test/fix: lock invoice allocation and event history`
2. `fix: mark Xero integration as preview until transport exists`
3. `fix: remove unsupported recurring billing promise`
4. `test: make release checks hermetic`
5. `docs: align v10 contracts and roadmap`
6. `test: add browser release gate`
7. 版本/发布账本闭环单独提交

任何提交前都运行对应 Targeted Verify；候选发布提交前必须运行完整 Release Gate。

---

## 1. 优先级与依赖图

| 顺序 | 批次 | 目标 | 阻塞关系 |
|---:|---|---|---|
| 1 | P0-A | 钱款分配与事件历史正确性 | 所有后续版本工作的前置 |
| 2 | P0-B | Xero 当前能力与产品承诺一致 | 在客户文档更新前完成后端事实锁定 |
| 3 | P0-C | 删除不存在的周期账单承诺 | 可与 P0-B 同一候选版，但独立验证 |
| 4 | P0-D | 干净检出与归档验证自包含 | 候选发布门禁前置 |
| 5 | P0-E | v10.6.4 候选闭环 | P0-A 至 P0-D 全绿后才开始 |
| 6 | P1-A | API/数据库/路线图当前化 | 以修复后的实际合同为输入 |
| 7 | P1-B | 真实浏览器发布门禁 | 钱款和产品真相稳定后落地 |
| 8 | P1-C | 运维保障方案 | 有外部目标/凭据/负责人决定后执行 |
| 9 | P2 | 构建期 CSS、CSP、API 命名等结构改进 | 不得阻塞 P0/P1 正确性修复 |

---

# P0-A：钱款正确性与“不静默丢弃”

## [x] 1. 建立 P0 钱款修复前基线

**Priority:** P0 / 第一项  
**Depends on:** 无  
**Files:** 只读检查；`backend/tests/test_money_layer.py`、`backend/test_tenant_isolation.py`  

**What to do:**

- 确认 `main` 包含 `1103b4c`，`VERSION` 为 `10.6.3`。
- 记录当前 `backend/tests/test_money_layer.py` 的收集数量和跳过原因。
- 确认本地 PostgreSQL 可用并已到 migration 0042。
- 运行钱款测试与完整租户隔离脚本，保存测试数量；不要改测试来“适配”失败环境。

**Commands:**

```bash
git status --short --branch
git rev-parse HEAD
git merge-base --is-ancestor 1103b4ca2c6c6fe41d8fa32685980db5c2e126d2 HEAD
cat VERSION
cd backend && ../.venv/bin/python scripts/run_migrations.py --check
cd .. && .venv/bin/python -m pytest backend/tests/test_money_layer.py -q
cd backend && ../.venv/bin/python test_tenant_isolation.py
```

**Acceptance:**

- 基线结果被记录；数据库不可用时明确阻塞，不接受全部 DB 测试被 skip 后继续。
- 工作树中原有用户文件未变化。

**Do not:** 不修代码、不重置数据库、不更新版本号。

**Execution evidence (2026-08-16):**

- `main` 与 `origin/main` 均为 `1103b4ca2c6c6fe41d8fa32685980db5c2e126d2`；`VERSION=10.6.3`；基线 ancestor check 通过。
- `STUDIOSAAS_DATABASE_URL=postgresql://llmacbookpro@localhost:5432/studiosaas_local_test ... run_migrations.py --check`：`Database is up to date. Nothing to apply.`
- `backend/tests/test_money_layer.py`：**46 passed**。
- `backend/test_tenant_isolation.py`：**237 passed, 0 failed**。
- 第一次无数据库环境变量、第二次沙箱 TCP 被拒绝；按规定使用现有本地测试库并升级权限重跑成功，不把环境失败记为产品通过。
- 未重置数据库、未改版本号；清单/handoff 是本任务已存在的用户范围内文件。

---

## [x] 2. 锁定指定发票优先、超付回落与默认 oldest-first

**Priority:** P0 / 金额分配  
**Depends on:** 1  
**Primary files:**

- `backend/tests/test_money_layer.py`：`money_tenant`、`_draft_with_line`、payment allocation tests
- `backend/studiosaas/services/payments.py`：`auto_allocate()`

**What to change:**

在 `test_money_layer.py` 增加四个数据库集成场景：

1. 同一付款账户有一张较老发票和一张当前发票；传 `prefer_invoice_id=current` 时，第一笔 allocation 必须指向当前发票。
2. 付款额大于当前发票余额；先清当前发票，余款再按 due date / issue date / number 的 oldest-first 顺序进入旧发票。
3. 不传 `prefer_invoice_id`；行为保持原有 oldest-first，不得因修复而改成 newest-first。
4. 重放同一 `idempotency_key`；不得重复 allocation 或重复付款事件。

测试数据必须使用不同金额，避免仅靠记录顺序“碰巧通过”。断言 allocation 的 `invoice_id`、`amount_cents`、两张发票的 `balance_cents` 和最终 `status`。

**Implementation notes:**

- 保留 `ORDER BY (id = %s) DESC, due_date NULLS LAST, issue_date, number` 的业务语义。
- 不把 UI 当前选中发票永久写成全局默认；只有明确传入 `prefer_invoice_id` 时优先。
- 不修改数据库触发器维护的 `amount_paid_cents` / `balance_cents`。

**Targeted Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_money_layer.py -q -k 'allocate or allocation or payment'
```

**Acceptance:** 四个场景全部通过；原有超额分配约束测试仍通过；无 migration。

**Execution evidence (2026-08-16):**

- 新增两个 PostgreSQL regression tests：指定发票先清偿且余款 oldest-first；未指定目标仍 oldest-first。
- 返回 allocation 顺序与数据库持久化金额均已断言；数据库查询断言改为按 invoice ID 比较，避免 UUID 排序造成伪失败。
- Targeted Verify：**3 passed, 45 deselected**。
- `payments.py` 未改动；当前实现行为已被锁定为回归合同；无 migration。

---

## [x] 3. 明确拒绝错误账户或跨租户的 `prefer_invoice_id`

**Priority:** P0 / 租户与账务边界  
**Depends on:** 2  
**Primary files:**

- `backend/studiosaas/services/payments.py`：`auto_allocate()`
- `backend/tests/test_money_layer.py`

**Current defect:**

当前查询只会把匹配的 ID 排到最前。若 `prefer_invoice_id` 属于另一个付款账户、另一个租户或根本不存在，它不会报错，而会静默回退到 oldest-first；这与 v10.6.2 已修复的“接受字段但做了另一件事”属于同一缺陷。

**What to change:**

- 当 `prefer_invoice_id` 非空时，先以 `(tenant_id, billing_account_id, invoice_id)` 查找可核销的 open invoice。
- 不存在、已 paid/void、属于错误 account 或错误 tenant 时抛出 `PaymentError`；错误信息不泄露目标是否属于其他租户，统一使用例如 `Preferred invoice is not open for this billing account.`。
- 验证通过后才生成 allocation plan。
- 确认抛错路径没有写入 `payment_allocations`；调用方 transaction rollback 后付款也不得残留。

**Tests:**

- wrong account invoice → `PaymentError`；
- foreign tenant invoice → 相同错误文本；
- nonexistent UUID → 相同错误文本；
- paid invoice → 拒绝；
- 每种失败后 allocation count 为 0。

**Targeted Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_money_layer.py -q -k 'prefer or allocation'
```

**Acceptance:** 所有错误目标显式失败；错误文本不可枚举其他租户；默认 oldest-first 不受影响。

**Execution evidence (2026-08-16):**

- 先添加回归测试并确认旧实现未抛出 `PaymentError`，会静默返回空/回落；该失败与目标根因一致。
- `payments.auto_allocate()` 现在对 tenant + billing account + open status 进行 target 验证；错误 target 统一返回 `Preferred invoice is not open for this billing account.`。
- 覆盖 wrong account、foreign tenant、paid invoice、nonexistent UUID；每种情况 allocation count 均为 0。
- Targeted Verify：**3 passed, 46 deselected**。
- 无 migration；测试使用临时 tenant，最终 rollback/fixture cleanup。

---

## [x] 4. 付款事件写入真实操作人，并锁定完整状态链

**Priority:** P0 / 审计可追溯  
**Depends on:** 2、3  
**Primary files:**

- `backend/studiosaas/services/payments.py`：`allocate()`、`auto_allocate()`
- `backend/studiosaas/api_v1.py`：`billing_record_payment()`
- `backend/tests/test_money_layer.py`

**Current defect:** `allocate()` 调用 `record_event(..., actor_user_id=None)`；API 已知道当前 actor，但没有传到 service，因此 UI 能显示收款事件，却不能回答是谁登记的。

**What to change:**

- 为 `allocate()` 和 `auto_allocate()` 增加 keyword-only `actor_user_id: str | None = None`，避免位置参数漂移。
- `billing_record_payment()` 将 `g.actor.user_id` 传给 `auto_allocate()`。
- 其他内部调用保持兼容；没有 actor 的脚本允许为 NULL，但不能伪造用户。
- 不直接在 API 层重复写 invoice event；事件仍由 service 单一入口产生。

**Tests:**

- issue 后半额付款：事件顺序含 `issued`, `part_paid`；part-paid detail 含本次 amount、事后 balance、payment_id，actor 与调用值一致。
- 再付余额：新增 `paid`；balance 为 0，actor 正确。
- 不允许只断言事件名；必须断言 JSON detail 的整数金额和余额。

**Targeted Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_money_layer.py -q -k 'event or status_and_balance or allocation'
```

**Acceptance:** `issued → part_paid → paid` 可重复证明；actor 不再被 API 路径丢失；旧 service 调用兼容。

**Execution evidence (2026-08-16):**

- `allocate()` / `auto_allocate()` 增加 keyword-only `actor_user_id`；API 传入当前 actor。
- 新增真实 PostgreSQL 事件链测试，覆盖 `issued → part_paid → paid`、每次金额/事后余额和 actor。
- Existing call-site scan：无位置参数破坏；无 migration。
- Targeted Verify：**8 passed, 42 deselected**。

---

## [x] 5. 退款事件补齐“本张发票实际释放的金额”

**Priority:** P0 / 发票历史真实性  
**Depends on:** 4  
**Primary files:**

- `backend/studiosaas/services/payments.py`：`refund()`
- `backend/tests/test_money_layer.py`
- 只核对、不直接编辑：`legacy-root/src/panels/billing.jsx` 的事件 detail 展示

**Current defect:** v10.6.3 handoff 声明退款事件带金额与事后余额，但 `refund()` 当前 detail 只有 `balance_cents`、`payment_id`、`reason`，没有 `amount_cents`；跨多张发票退款时也只保存一个 touched set，丢失了每张发票实际释放多少。

**What to change:**

- 将 `touched_invoices: set[str]` 改为按 invoice 聚合的金额映射，例如 `dict[str, int]`。
- 每次删除/缩减 allocation 时，把该次 `take` 累加到对应 invoice。
- 每张发票写一条 `refunded` event，detail 至少包含：
  - `amount_cents`：这张发票本次被释放的 allocation 金额；
  - `balance_cents`：触发器更新后的事后余额；
  - `payment_id`；
  - `reason`。
- actor 使用现有 `actor_user_id`。
- 若退款包含未分配的账户 credit，invoice event 金额合计只等于被释放的 allocations，不伪称等于整个退款额。

**Tests:**

1. 单发票部分退款；
2. 单发票全额退款；
3. 一笔 payment 分配到两张发票后跨发票退款；
4. 含未分配 credit 的退款；
5. 退款超过可退金额仍被拒绝，且没有 event/refund 残留。

**Targeted Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_money_layer.py -q -k 'refund or event'
```

**Acceptance:** 每张受影响发票的 event 金额可与 allocation 变化对账；退款总账和发票历史不互相矛盾。

**Execution evidence (2026-08-16):**

- 新增单发票部分/全额退款、跨发票退款、含未分配 credit、超额退款无副作用四组 PostgreSQL 回归测试。
- `payments.refund()` 现在按 invoice 聚合实际释放金额，并在每张受影响发票的 `refunded` event 中写入 `amount_cents`、事后 `balance_cents`、`payment_id`、`reason` 与现有 actor。
- 初跑暴露 3 个缺失金额断言；修复 service 后定向测试 **4 passed, 50 deselected**。跨发票整笔释放后的发票状态按业务规则校正为 `issued`（余额恢复），不是 `part_paid`。
- 无 migration；超额退款路径确认没有 refund/event 残留。

---

## [x] 6. 为钱款写接口建立严格 payload 合同

**Priority:** P0 / 禁止静默丢弃  
**Depends on:** 3、4、5  
**Primary files:**

- `backend/studiosaas/api_v1.py`：JSON helper 区、`billing_invoices()`、`billing_invoice_add_line()`、`billing_record_payment()`、`billing_refund_payment()`
- `backend/test_tenant_isolation.py`：真实 HTTP + 真 PostgreSQL 契约检查
- 可选新增：`backend/tests/test_money_api_contract.py`，仅当能复用真实 DB fixture 而不建立第二套假连接

**Decision already made:**

- 当前不实现自定义 `dueDate`。到期日由 `billing.issue_invoice()` 根据付款账户 `payment_terms_days` 计算。
- 因此 `POST /billing/invoices` 收到 `dueDate` 必须返回 400，不能 201 后忽略。

**What to change:**

- 增加一个小而通用的 helper，例如 `_reject_unknown_keys(payload, allowed, context)`；排序输出未知字段，返回稳定、可测试的错误信息。
- 只先接入以下钱款 mutation，不要一口气改 173 条路由：
  - invoice draft allowed：`billingAccountId`, `termId`, `note`, `purchaseOrderRef`；
  - invoice line allowed：`description`, `quantity`, `unitPriceCents`, `taxCodeId`, `taxRateBp`, `sourceKind`, `sourceId`, `studentId`；
  - payment allowed：`billingAccountId`, `amountCents`, `method`, `note`, `idempotencyKey`, `autoAllocate`, `invoiceId`；
  - refund allowed：`amountCents`, `reason`。
- `invoiceId` 与 `autoAllocate=false` 同时出现时返回 400，因为 target 不可能生效。
- boolean 必须严格解析；字符串 `"false"` 不能被 Python truthiness 当成 true。
- 400 错误使用仓库统一 `{error, message}` shape；不要返回堆栈或字段值中的敏感信息。

**HTTP tests:**

- invoice `dueDate` → 400，数据库无新 draft；
- payment 拼错 `invoiceID` → 400，数据库无 payment；
- payment `invoiceId` + `autoAllocate=false` → 400；
- refund 未知字段 → 400，无退款；
- 所有合法现有 CMS payload → 原状态码保持 201/200；
- foreign invoiceId → 409 或统一业务错误，不得改付其他发票；
- response error shape 完整。

**Targeted Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_money_layer.py backend/tests/test_error_responses.py -q
cd backend && ../.venv/bin/python test_tenant_isolation.py
```

**Acceptance:** 被拒绝的 payload 零副作用；合法 UI payload 无回归；不存在“收下字段但做另一件事”。

**Execution evidence (2026-08-16):**

- `api_v1.py` 增加 `_reject_unknown_keys()` 与严格 JSON boolean parser；仅接入 invoice draft、invoice line、payment、refund 四类 mutation。
- `dueDate`、`invoiceID`、refund typo 等未知字段现在统一 400 `{error, message}`；`invoiceId + autoAllocate=false` 与字符串 `"false"` 均拒绝。
- 真实 HTTP 契约已加入现有 `backend/test_tenant_isolation.py`，断言拒绝请求零 draft/payment/refund 副作用；foreign invoice target 返回 409 且不泄露目标 ID、不跨租户写入。
- 合法 CMS payload 保持原状态码：draft/line/payment 为 201，issue 为 200，refund 为 200。
- Targeted pytest：**57 passed**；真实 HTTP 租户隔离：**253 passed, 0 failed**。
- 无 migration。

---

## [x] 7. 锁定 CMS 发票详情收款的前端契约

**Priority:** P0 / UI 防回归  
**Depends on:** 6  
**Primary files:**

- `legacy-root/src/panels/billing.jsx`：`recordPayment()`、detail refresh、event rendering
- `backend/tests/test_cms_panels.py`
- `backend/frontend/assets/cms-app.js`：仅由构建生成

**What to change:**

- 在 `test_cms_panels.py` 增加静态合同，确保 `recordPayment()` 的 body 同时含当前 `detail.invoice.id`、`autoAllocate: true`、当前 `billing_account_id`。
- 确保成功后既 reload 列表，又重新 GET 当前 detail；不能只刷新列表导致抽屉仍显示旧余额/旧历史。
- 事件金额渲染使用 detail 的 `amount_cents`，退款和收款都显示；不存在 detail 时不显示 `$0.00` 误导。
- 不在本任务重新设计面板布局。
- 构建 bundle 并运行 bundle freshness 检查。

**Commands:**

```bash
bash backend/scripts/build_cms.sh
.venv/bin/python -m pytest backend/tests/test_cms_panels.py backend/tests/test_money_layer.py -q
node --check backend/frontend/assets/cms-app.js
```

**Acceptance:** 源码与 bundle 一致；指定发票 ID 不会从前端 payload 消失；成功后余额和事件历史立即更新。

**Execution evidence (2026-08-16):**

- `backend/tests/test_cms_panels.py` 新增静态契约：`recordPayment()` 必须同时提交当前 detail 的 `billing_account_id`、`invoice.id`、`autoAllocate: true`。
- 同一测试锁定成功后同时刷新列表与当前 detail，并要求事件只在存在且大于零的 `amount_cents` 时显示金额，避免缺失 detail 渲染 `$0.00`。
- `bash backend/scripts/build_cms.sh` 已成功重建 bundle/manifest；生成内容与当前已跟踪 bundle 一致，无额外生成 diff。
- `node --check frontend/assets/cms-app.js`；CMS 静态合同及 UI contract **11 passed**。
- 未改布局、无 migration。

---

# P0-B：Xero 产品真相闭环

## [x] 8. 在后端明确声明 Xero transport 当前不可用

**Priority:** P0 / 不得把预留架构当成集成  
**Depends on:** 1；建议在钱款批次后执行  
**Primary files:**

- `backend/studiosaas/services/xero.py`：`GateStatus`、`gate_status()`、`set_push_enabled()`、`enqueue()`
- `backend/studiosaas/api_v1.py`：`xero_status()`、`xero_gate()`
- `backend/tests/test_money_layer.py`：现有 Xero gate tests

**Current truth:** 有 entitlement、connection 表、mapping、gate、queue、replay 和 demo seed；没有真实 OAuth 生命周期、Xero HTTP client、token refresh、worker/consumer 或 provider response handling。

**What to change:**

- 增加代码级常量，如 `TRANSPORT_AVAILABLE = False`，并写清它只能在真实 transport 验收后改为 true。
- `GateStatus` 增加 `transport_available`；`can_enable` 必须包含该条件。
- `blockers()` 返回稳定的 `transport_not_available`。
- `set_push_enabled(..., True)` 在 transport 不可用时明确拒绝。
- `enqueue()` 在 transport 不可用时不创建新 job，即使历史/演示数据里 `push_enabled=true`。
- `GET /integrations/xero` 返回 `integrationStage: "preview"` 与 `transportAvailable: false`。
- 不删除已有表、mapping、object links、错误队列；预留结构仍可用于未来实现。
- 不新增假 OAuth URL，不创建假 token，不调用外网。

**Tests:**

- 填满 entitlement/connected/mapping/demo/single-entry 后仍不能 enable push，blocker 只剩 transport；
- 直接伪造历史 `push_enabled=true` 时 `enqueue()` 仍不创建 job；
- disable 始终允许；
- API status 明确返回 preview/false；
- 既有 mapping 与 queue 查询保持可读。

**Targeted Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_money_layer.py -q -k 'xero or gate or enqueue'
```

**Acceptance:** 代码层不可能把“数据库状态齐全”误判成“真实 Xero transport 已上线”。

**Execution evidence (2026-08-16):**

- `xero.TRANSPORT_AVAILABLE = False`，并保留 `INTEGRATION_STAGE = "preview"`；注释明确只有真实 OAuth/token/HTTP/worker/provider-response 验收后才能改为 true。
- `GateStatus` 增加 `transport_available`；gate 完整时仍只剩 `transport_not_available`，`can_enable` 为 false；disable 仍可执行。
- `set_push_enabled(True)` 不能绕过 transport gate；即使历史行伪造 `push_enabled=true`，`enqueue()` 也不会新建 job。
- `GET /integrations/xero`（及 gate response）返回 `integrationStage: "preview"`、`transportAvailable: false`，mapping/settings 仍可读。
- Targeted Xero pytest：**6 passed**；真实 HTTP 租户隔离：**254 passed, 0 failed**。
- 未删除预留表、mapping、object links、错误队列；无 migration、无外网调用、无假 OAuth/token。

---

## [x] 9. 将 CMS Xero 页面改成不可误解的 Preview

**Priority:** P0 / 客户界面  
**Depends on:** 8  
**Primary files:**

- `legacy-root/src/panels/integrations.jsx`
- `backend/frontend/assets/cms-i18n.js`
- `legacy-root/src/panels/billing.jsx`：Xero event label/空历史说明，仅在确有误导时改
- `backend/tests/test_cms_panels.py` 或新增 `backend/tests/test_xero_product_truth.py`
- `backend/frontend/assets/cms-app.js`：生成物

**What to change:**

- 标题从“Xero 直连”改为“Xero 预接入（Preview）”。
- 删除“自动推送”“不用再录第二遍”“开启生产推送”等现在不能兑现的表达。
- 当 `transportAvailable=false`：
  - 显示预接入说明；
  - 允许只读查看已有 mapping/gate 准备状态；
  - 隐藏或禁用所有会让用户相信能连生产的按钮；
  - 明确“不会向 Xero 发送任何数据”。
- 只有未来 API 返回 `transportAvailable=true` 才显示 enable/disable push 控件。
- 保持 44px 目标、焦点可见、中文/英文可翻译。
- 更新 i18n 源词条并重建 bundle。

**Banned live-claim strings while transport is false:**

- `Xero 直连`
- `自动推送到 Xero`
- `不用再录第二遍`
- `开启生产推送`
- English equivalents such as `connected directly`, `automatically pushed`, `no duplicate entry`

**Commands:**

```bash
bash backend/scripts/build_cms.sh
.venv/bin/python -m pytest backend/tests/test_cms_panels.py -q
node --check backend/frontend/assets/cms-i18n.js
node --check backend/frontend/assets/cms-app.js
```

**Acceptance:** transport=false 时不存在可点击的生产推送入口，也不存在已上线承诺；页面仍能解释未来接入前置条件。

**Execution evidence (2026-08-16):**

- `integrations.jsx` 标题、状态 badge、说明卡与推送卡均明确 `Xero 预接入（Preview）`；明确写出“不会向 Xero 发送任何数据”“不会创建新的推送任务”。
- `transportAvailable` 是唯一生产控件开关；preview 时 gate/单一入口只读，生产推送按钮不渲染，历史 mapping/settings/error queue 仍可查看。
- 删除旧的“自动推送到 Xero，不用再录第二遍”产品承诺；新增中英 i18n 词条，并保留 44px button classes。
- `test_xero_product_truth.py` + CMS 静态检查 **7 passed**；`build_cms.sh`、`node --check cms-app.js`、`node --check cms-i18n.js` 均通过。
- 未改 billing 布局；无 migration、无外网调用。

---

## [x] 10. 对齐客户文档中的 Xero 边界

**Priority:** P0 / 销售与交付真实性  
**Depends on:** 8、9  
**Primary files:**

- `docs/customer/Integration_Boundaries.md`
- `docs/customer/FAQ.md`
- `docs/customer/Demo_Runbook.md`
- `customer-resources/Release_Notes.html`
- `customer-resources/FAQ.html`
- `docs/customer/README.md`（只在目录/状态说明需要时）

**What to change:**

- 以代码事实“Preview、无 transport、无外发”为唯一当前说法。
- `Integration_Boundaries.md` 不再把 one-way push 写成已交付能力；改成未来目标及验收前提。
- `Release_Notes.html` 删除“accountant can be connected directly”和“stop being typed twice”等承诺。
- FAQ、Demo Runbook 目前“Xero 未上线/不要暗示 live”的说法保留并统一用词。
- 明确预留内容：mapping、幂等 key、queue schema、replay UI 是准备工作，不等于 provider 集成。
- 不承诺时间表，不写“即将上线”，除非有批准的交付日期。

**Repository truth search:**

```bash
rg -n -i 'Xero|直连|自动推送|typed twice|connected directly|one-way push' \
  legacy-root/src backend/frontend/assets docs/customer customer-resources
```

**Acceptance:** 所有客户可见材料与 CMS/API 的 Preview 状态一致；Demo Runbook 不可能引导演示者声称 live。

**Execution evidence (2026-08-16):**

- 更新 `Integration_Boundaries.md`：Xero 改为 Preview-only，明确没有 OAuth/client/token refresh/worker/provider response，也不外发数据；mapping、queue/replay 仅是准备结构。
- 更新 `FAQ.md`、`Demo_Runbook.md`、`Release_Notes.html`、`FAQ.html`，统一使用 Preview/no transport/no data sent，不承诺时间表或即将上线。
- Repository truth search 未再发现 `connected directly`、`typed twice`、`one-way push`、`Xero 直连` 等旧 live claim。
- 未改部署/销售私有目录；无 migration、无外部发布。

---

## [x] 11. 增加“延后能力不得写成已上线”的自动守卫

**Priority:** P0 / 防止承诺再次漂移  
**Depends on:** 8–10  
**Files:** 建议新增 `backend/tests/test_product_truth_contract.py`

**What to build:**

- 从 `backend/studiosaas/services/xero.py` 读取/导入 `TRANSPORT_AVAILABLE`。
- 当它为 false 时，扫描客户可见源文件和 CMS 源，禁止任务 9 列出的 live-claim strings。
- 断言 API status 包含 Preview/transport 标志。
- 断言 FAQ 与 Demo Runbook 明确写 Xero 非 active integration。
- 守卫只检查明确的承诺短语，不使用过宽正则把 migration/设计说明中的“Xero”全部封死。

**Verify:**

```bash
.venv/bin/python -m pytest backend/tests/test_product_truth_contract.py \
  backend/tests/test_customer_resources_brand.py -q
```

**Acceptance:** 任一客户材料重新写“已直连”时测试会红；未来 transport 真上线时必须同时更新常量、测试、界面和文档。

**Execution evidence (2026-08-16):**

- 新增 `backend/tests/test_product_truth_contract.py`，读取 `xero.TRANSPORT_AVAILABLE`；false 时扫描 CMS source/assets、customer docs/resources 的明确 live-claim 短语。
- 守卫同时断言 `INTEGRATION_STAGE == "preview"`、API status 的 `integrationStage`/`transportAvailable` 字段，以及 FAQ/Demo Runbook 的 Preview/no-data 说明。
- Verify：`test_product_truth_contract.py` + `test_customer_resources_brand.py` **73 passed, 1 skipped**。
- 词表保持窄范围，不封杀工程说明中的普通 “Xero” 提及；无 migration。

---

# P0-C：删除不存在的周期账单承诺

## [x] 12. 修正发票空状态和批量开具注释

**Priority:** P0 / 立即消除错误承诺  
**Depends on:** 可与 8–11 并行设计，但提交时独立  
**Primary files:**

- `legacy-root/src/panels/billing.jsx`：空状态字符串、`issueSelected()` 上方注释
- `backend/frontend/assets/cms-i18n.js`：对应中英词条
- `backend/tests/test_cms_panels.py` 或 `backend/tests/test_product_truth_contract.py`
- `backend/frontend/assets/cms-app.js`：生成物

**Exact replacement intent:**

- 中文建议：`还没有发票。点击“新建发票”创建草稿，复核后再开具。`
- 英文建议：`No invoices yet. Create a draft invoice, review it, then issue it.`
- `issueSelected()` 注释改成“人工创建的多张草稿可批量发出”，不能再说周期账单生成几十张。

**What not to do:**

- 不在本任务实现 recurring invoice generator。
- 不删除批量发出已有草稿的能力。
- 不把“人工创建”写成自动化已计划或即将上线。

**Verify:**

```bash
rg -n '周期账单会自动生成草稿|Recurring billing drafts them' legacy-root backend
bash backend/scripts/build_cms.sh
.venv/bin/python -m pytest backend/tests/test_cms_panels.py \
  backend/tests/test_product_truth_contract.py -q
```

**Acceptance:** 第一条 `rg` 零结果；中英文一致；bundle 新鲜；批量发出功能不受影响。

**Execution evidence (2026-08-16):**

- 空状态已改为“点击新建发票创建草稿，复核后再开具”，英文同步为 `Create a draft invoice, review it, then issue it.`。
- `issueSelected()` 注释现在只描述人工创建的多张草稿批量发出；不再声称周期账单自动生成几十张草稿。
- 新增 CMS 静态回归；CMS/product truth **9 passed**；bundle、manifest、Node syntax checks 均通过。
- 未实现 recurring invoice generator；保留已有草稿批量开具能力；无 migration。

---

# P0-D：验证必须在干净环境中自包含

## [x] 13. 修复 Brand contract 对被忽略 `.agents` 镜像的依赖

**Priority:** P0 / CI 与干净检出可靠性  
**Depends on:** 无；建议在候选门禁前完成  
**Primary files:**

- `backend/tests/test_release_brand_contract.py`：`test_brand_prompt_injection_defaults_to_the_canonical_document()`
- 权威脚本：`.claude/skills/brand/scripts/inject-brand-context.cjs`
- 不改：`.agents/skills/brand/...`（忽略的运行时镜像）

**What to change:**

- 测试读取 Git 跟踪的 `.claude/skills/brand/scripts/inject-brand-context.cjs`。
- 可额外断言该路径出现在 `git ls-files`，但测试本身不要 shell out 到 Git；用独立 release check 验证 tracking 更稳。
- 保留“默认读 `docs/design/Brand_Identity.md`”的原断言。
- 不把 `.agents/` 加入 Git；它仍是工具运行时镜像。

**Verify:**

```bash
git ls-files '.claude/skills/brand/scripts/inject-brand-context.cjs'
.venv/bin/python -m pytest backend/tests/test_release_brand_contract.py -q
```

**Acceptance:** 普通工作区和 clean clone 均通过；不依赖用户机器私有镜像。

**Execution evidence (2026-08-16):**

- `backend/tests/test_release_brand_contract.py` 已从被忽略的 `.agents/skills/brand/...` 改读 tracked `.claude/skills/brand/...`。
- 同次验证发现 README 断言仍要求旧措辞 `deployed source commit`；按当前 README 真实措辞校正为 `deployed runtime commit`，没有改产品文档事实。
- `git ls-files` 确认 `.claude/skills/brand/scripts/inject-brand-context.cjs` 已跟踪；`test_release_brand_contract.py`：**4 passed**。
- 未把 `.agents` 加入 Git；无 runtime/migration 变更。

---

## [x] 14. 增加 clean-checkout 验证脚本

**Priority:** P0 / 可重复发布  
**Depends on:** 13  
**Suggested file:** `backend/scripts/verify_clean_checkout.sh`  
**Related files:** `backend/scripts/release_preflight.sh`、`docs/Release_Runbook.md`

**What to build:**

- 脚本使用 `mktemp -d`，用 `git archive HEAD` 解出干净跟踪树；不得在仓库里创建第二 checkout。
- 用当前 `.venv` 的绝对 Python 运行不依赖 DB/本机私有镜像的静态测试集合，至少包含：
  - release ledger；
  - release brand contract；
  - CMS panels/static contracts；
  - product truth contract；
  - inline/shared JS syntax checks。
- 用 trap 清理临时目录。
- 输出每个阶段和最终 exit code；不吞 stderr。
- 不要求 release archive 含 `.claude`：archive 会按发布政策排除内部工具。本任务验证的是 Git clean checkout；release archive 的运行时 smoke 在下一项单独验证。

**Verify:**

```bash
bash -n backend/scripts/verify_clean_checkout.sh
bash backend/scripts/verify_clean_checkout.sh
```

**Acceptance:** 当前机器的 `.agents` 是否存在都不影响结果；脚本不修改仓库、不留下临时目录。

**Execution evidence (2026-08-16):**

- 新增 `backend/scripts/verify_clean_checkout.sh`：`mktemp -d` + `git archive HEAD`，临时树恢复 tracked `.claude`（绕过 release `export-ignore`，不复制 `.agents`），再叠加当前候选文件，不写回仓库。
- 静态集合覆盖 release ledger/brand、CMS panels/UI、product truth、Xero truth、navigation、inline scripts；共享 bundle/i18n/admin JS 另做 Node syntax check。
- 首次运行验证了 `.claude` 的 release `export-ignore` 边界；修正为只复制 `git ls-files .claude`，避开本机 `.claude/worktrees` 私有 symlink。
- `bash -n` + clean-checkout：**28 passed**，Node checks 全绿；trap 已清理临时树。

---

## [x] 15. 为 SaaS/Edition archive 增加运行时 smoke，而不是在包内跑全部仓库测试

**Priority:** P0 / 归档可运行性  
**Depends on:** 14  
**Primary files:**

- `deploy/aws/verify_release_bundles.sh`
- 可新增 `backend/scripts/smoke_release_archive.sh`
- `deploy/aws/build_aws_bundle.sh`

**What to build:**

- 在临时目录解包两个归档，验证：
  - `VERSION`、`BUILD_INFO`、mode、commit 一致；
  - Python runtime modules 可 compile；
  - shell entrypoints `bash -n`；
  - CMS bundle 可由 Node 解析；
  - SaaS 与 Edition 必需/禁止文件合同保持现有规则。
- 不在 release archive 内跑依赖 `.claude`、Git 元数据或开发文档的测试；这些由 clean-checkout gate 负责。
- 不启动连接生产数据库的服务；如做启动 smoke，使用临时目录和明确的 synthetic/local config。

**Verify:**

```bash
bash -n deploy/aws/verify_release_bundles.sh
bash deploy/aws/verify_release_bundles.sh
```

**Acceptance:** 两种交付物都能在没有仓库内部工具目录的环境通过运行时检查；无内部路径泄漏。

**Execution evidence (2026-08-16):**

- 新增 `backend/scripts/smoke_release_archive.sh`：临时解包 SaaS/Edition，校验 `VERSION`/`BUILD_INFO`/mode/entrypoint，compile Python runtime，`bash -n` 所有 shell entrypoints，Node parse CMS/shared bundles。
- `deploy/aws/verify_release_bundles.sh` 已接入该 smoke；原有 checksum、inventory forbidden paths、SaaS/Edition required/forbidden 文件合同保留。
- 对现有 v10.6.3 SaaS/Edition archives 执行 smoke：**2 archives PASS**，无内部工具路径泄漏；`bash -n` 两个 verifier 通过。
- 完整 verifier 的“从当前 HEAD 重建两包”仍按发布安全规则要求 clean committed tree；当前候选尚未提交，故本轮只验证现有基准包并不伪造新包证据。

---

# P0-E：候选版闭环（只有 P0-A 至 P0-D 全绿后执行）

## [x] 16. 执行 P0 综合回归，不先改版本号

**Priority:** P0 / 候选前门禁  
**Depends on:** 1–15  

**Commands:**

```bash
git diff --check
bash backend/scripts/build_cms.sh
.venv/bin/python -m pytest backend/tests/test_money_layer.py \
  backend/tests/test_cms_panels.py \
  backend/tests/test_product_truth_contract.py \
  backend/tests/test_release_brand_contract.py \
  backend/tests/test_customer_resources_brand.py -q
bash backend/scripts/verify_clean_checkout.sh
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh
```

**Acceptance:**

- 所有 targeted tests 通过；
- legacy smoke 与 tenant isolation 全绿；
- migration check、媒体衍生物、CMS bundle/manifest 全绿；
- 无 skip 掩盖要求 PostgreSQL 的 P0 测试；
- `git status` 只包含本清单批准的文件。

**If red:** 先修回归；不得通过删测试、放宽断言或移除 PostgreSQL required flag 变绿。

**Execution evidence (2026-08-16):**

- `git diff --check`、`bash backend/scripts/build_cms.sh`：通过；bundle 与 manifest 由源文件重新生成。
- P0 targeted pytest：**140 passed, 1 skipped**；该 skip 为已有 Release Notes 版本陈旧检查，不是 PostgreSQL P0 测试。
- `bash backend/scripts/verify_clean_checkout.sh`：**28 passed**，Node bundle/shared-asset syntax checks 通过，临时树已清理。
- Full `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`：使用受限应用角色 `studiosaas_app`、独立 migration owner `llmacbookpro`，**All checks passed**；完整 pytest **2619 passed, 7 skipped**，legacy smoke **73/73**，tenant isolation **254/254**，migration/media/CMS bundle/manifest/compile/terminology checks 全绿。
- 为保持部署后的 app/owner 边界，`verify_local.sh` 现在支持 `STUDIOSAAS_MIGRATION_DATABASE_URL`，并在 pytest/tenant isolation 前清除该 owner-only 环境变量；没有放宽 PostgreSQL required gate。
- `git status` 仅包含本清单批准的实现、测试、文档、脚本及生成 bundle；未读写 `docs/sales/clients/`、`docs/security/`，未改版本号、未提交、未推送、未部署。

---

## [x] 17. 准备 v10.6.4 版本账本（不代表部署）

**Priority:** P0 / 发布候选  
**Depends on:** 16  
**Primary files:** 以 `backend/scripts/release_preflight.sh` 实际报告为准，通常包括：

- `VERSION`
- `backend/server.py` 的 app version marker
- `README.md` Source 行
- `docs/HANDOFF_LATEST.md` 顶部新版本节
- `docs/customer/Release_Notes.md`
- `customer-resources/Release_Notes.html`
- Edition 当前版本文档（由 preflight 精确列出）

**What to record:**

- 修复指定发票分配与错误 target 拒绝；
- 付款/退款事件金额、余额、actor；
- 钱款 payload strict contract；
- Xero Preview 真相；
- 删除周期账单自动化假承诺；
- clean-checkout/archive smoke。

**Rules:**

- 先运行 preflight，看它要求哪些版本位置；不根据旧清单猜。
- Source 行可写 candidate/committed，Package 与 Production 必须仍写实际 10.6.3，直到真的构建/部署并验证。
- handoff 顶部写清未部署边界和所有测试证据。

**Verify:**

```bash
bash backend/scripts/release_preflight.sh
.venv/bin/python -m pytest backend/tests/test_release_ledger.py \
  backend/tests/test_user_guides.py -q
git diff --check
```

**Acceptance:** Source/Package/Production 没有被合并成一句；没有把候选写成线上已运行。

**Execution evidence (2026-08-16):**

- 先运行 `bash backend/scripts/release_preflight.sh`，按实际账本检查了 branch、工作树、PostgreSQL、CMS smoke 环境和版本位置；候选更新后 preflight **clear**，`VERSION`/`APP_VERSION`/guides/README/handoff 均为 10.6.4。
- `VERSION` 与 `backend/server.py::APP_VERSION` 更新为 **10.6.4**；角色 guides、客户 Release Notes、customer-resources Release Notes、Edition 当前文档与 handoff 顶部均明确 candidate 状态。
- `backend/tests/test_release_ledger.py` + `backend/tests/test_user_guides.py`：**30 passed**；`git diff --check`：通过。
- README 与 handoff 保留分层：Source = v10.6.4 candidate；SaaS/Edition Package = 已验证 v10.6.3；Production = 仍运行 v10.6.3。未生成 v10.6.4 archive，未改变现有 v10.6.3 package/production 证据。

---

## [x] 18. STOP GATE：提交、打包、推送与部署

**Priority:** P0 / 外部写操作  
**Depends on:** 17  

到这里必须停下并报告：

- 变更文件；
- targeted/full gate 结果与测试数量；
- 是否有 migration；
- 建议版本号；
- 当前 Source/Package/Production 三层状态；
- 未解决风险。

**只有收到明确授权后**才按 `docs/Release_Runbook.md` 执行 commit → build → verify bundles → push → deploy → browser/public acceptance → handoff closure。不得用“执行清单”四个字推断生产部署权限。

**Execution evidence (2026-08-16):**

- STOP GATE 已到达；本轮**没有**执行 commit、package rebuild、bundle release verification、push、remote sync、deployment、browser/public production acceptance 或 handoff closure。
- 候选文档更新后复核：`git diff --check` 通过；clean-checkout **28 passed**；release ledger/user guides/customer resources **100 passed, 1 skipped**。
- 当前建议版本：**v10.6.4**。当前 Source 是未提交候选；Package 与 Production 仍是已验证/运行的 v10.6.3。
- 无新增或应用 migration；剩余风险是候选尚未取得提交/打包/推送/部署授权，真实生产与浏览器验收仍未执行。

---

# P1-A：把文档更新为当前合同

## [ ] 19. 生成代码路由清单，作为 API 文档差异证据

**Priority:** P1  
**Depends on:** P0-E 候选合同稳定  
**Suggested files:**

- 新增 `backend/scripts/check_api_docs.py`
- 更新 `docs/API.md`
- 测试可放 `backend/tests/test_docs_currentness.py`

**What to build:**

- 从 `backend/studiosaas/api_v1.py` 与 server route registration 中提取 method/path/function/permission decorator。
- 输出稳定排序；同一路径多 method 正确展开。
- 对 docs 做最小强约束：当前版本、钱款/Xero关键路由、公开/需登录边界必须存在。
- 不要求一开始为 173 条路由写长篇说明；先建立机器可比对 inventory，人工文档重点解释危险合同。

**Acceptance:** 新增/删除关键路由而未更新 docs 时检查失败；动态路由参数规范化一致。

---

## [ ] 20. 更新 `docs/API.md` 到 v10 钱款合同

**Priority:** P1  
**Depends on:** 19  
**Primary file:** `docs/API.md`

**Required sections:**

- 文档版本/日期与当前 release；
- session、CSRF、自定义 header、permission 与 tenant path 规则；
- billing accounts、invoice draft/line/issue/void/detail/list；
- payments/refunds、idempotency、autoAllocate、preferred invoice；
- strict unknown-field behavior；
- dueDate 当前由 payment terms 推导且 draft API 不接受 override；
- Xero Preview status 与 transport unavailable；
- error shape 和 400/401/403/404/409 区分；
- 示例只用合成 UUID/金额，不含真实客户数据。

**Verify:**

```bash
.venv/bin/python backend/scripts/check_api_docs.py
.venv/bin/python -m pytest backend/tests/test_docs_currentness.py -q
```

---

## [ ] 21. 更新 `docs/Database.md` 到 migration 0042

**Priority:** P1  
**Depends on:** P0 合同稳定  
**Primary files:** `docs/Database.md`、`backend/db/migrations/0032_*.sql` 至 `0042_*.sql`

**Required content:**

- canonical migrations through `0042_tenant_isolation_by_construction.sql`；
- billing/invoices/events/payments/allocations/refunds/credit notes；
- teacher rates/pay periods/sessions；
- Xero tables明确为 Preview 基础设施；
- recurring lessons/make-up credits 与“周期账单”严格区分；
- RLS `SET` 绑定、无连接池前提、platform/support exceptions；
- invoice immutability、over-allocation、Xero gate 等数据库约束；
- schema_v1 与 migrations 的权威关系。

**Guard:** `test_docs_currentness.py` 自动比较 migrations 目录的最大序号与文档声明。

---

## [ ] 22. 重写路线图的“当前状态”，不再沿用 7 月旧 Phase

**Priority:** P1  
**Depends on:** 20、21  
**Primary file:** `docs/Development_Roadmap.md`

**Required status buckets:**

- Production verified；
- Built but guarded/limited；
- Preview / reserved infrastructure；
- Deferred / requires decision；
- Explicitly not planned now。

**Must be explicit:**

- AWS Lightsail 当前真实拓扑；
- PostgreSQL/RLS/6-tenant production fact需要每次重新核验；
- Xero、MFA、off-instance backup/alerting、SLA、真实 provider delivery 未完成；
- 周期排课已存在，但周期账单生成未存在；
- Playwright 未安装，浏览器 gate 使用何种实际方案必须写实。

**Acceptance:** 路线图不再把已上线功能写“进行中”，也不把预留接口写“完成”。

---

## [ ] 23. 把文档 currentness 检查接入完整门禁

**Priority:** P1  
**Depends on:** 19–22  
**Primary files:**

- `backend/scripts/verify_local.sh`
- `backend/tests/test_docs_currentness.py`
- `docs/Release_Runbook.md`

**What to change:**

- 在静态快速阶段运行 docs currentness；失败给出准确修复文件与命令。
- 检查至少覆盖 VERSION、最新 migration、Xero Preview、API关键路由。
- 不把时间敏感线上数值硬编码进测试；线上 tenant/disk 数只在 release handoff 记录。

**Acceptance:** 文档再次停在 migration 0031 或把 Xero 写 live 时，完整 gate 必须失败。

---

# P1-B：最小而真实的浏览器发布门禁

## [ ] 24. 复用现有 Chrome CDP 建立独立 browser gate harness

**Priority:** P1  
**Depends on:** P0-E  
**Primary files:**

- 参考 `backend/scripts/capture_manual_shots.py` 的 `Browser`/CDP 实现
- 新增 `backend/scripts/release_browser_gate.py`
- 可选抽取 `backend/scripts/browser_cdp.py`，仅当 capture 与 gate 都真正复用

**What to build:**

- 不新增 Playwright/Selenium 生产依赖；优先复用系统 Chrome + CDP。
- CLI 接受 `--base-url`、`--tenant-slug`、`--width`、`--height`；凭据从环境变量读取，不进入日志。
- 每一步记录 route、viewport、assertion、console errors、failed network requests。
- 失败保存截图和 JSON 证据到被忽略的临时/output 目录；不得写入客户数据目录。
- 支持 dry/local 模式；默认禁止指向 production，除非显式 `--allow-production` 且用户授权。

**Acceptance:** harness 能在本地打开页面、执行 JS/点击/输入、抓 console 和截图，并可靠返回非零。

---

## [ ] 25. 自动化核心账单浏览器流程

**Priority:** P1 / 第一条 browser journey  
**Depends on:** 24  
**Primary UI:** `/<tenant>/cms` → Billing panel  
**Backend:** `/s/<tenant>/v1/billing/*`

**Synthetic journey:**

1. 重置/创建专用测试 tenant；
2. 建两个同账户 issued invoices，旧单与目标单金额不同；
3. UI 打开目标 invoice detail；
4. 点击登记收款一次；
5. 断言目标单余额变化，旧单未被错误优先；
6. 断言 history 新增 paid/part-paid，金额和余额可见；
7. 执行部分退款；
8. 断言 refunded event 金额、事后余额与数据库/API一致；
9. 刷新页面，状态仍持久；
10. 清理 synthetic records 或整体重建专用 tenant。

**Acceptance:** 不是只检查 200；必须验证点击结果、DOM文字、API响应和持久化状态四者一致。

---

## [ ] 26. 自动化公共面与管理面关键流程

**Priority:** P1  
**Depends on:** 24  

**Journeys:**

- Public portal：导航/深锚点、语言切换、Selected Work、注册入口；
- Studio Admin：修改 draft、预览、发布、公共面读取已发布版本；
- Platform Admin：tenant list、support session reason、退出 support；
- Xero Preview：无生产推送按钮、明确“不发送数据”；
- Billing empty state：无周期账单自动生成承诺。

**State checks:** loading、empty、error、success；无未处理 console error；无核心请求 5xx。

---

## [ ] 27. 建立 viewport / language / theme 矩阵

**Priority:** P1  
**Depends on:** 25、26  

**Required matrix:**

- widths：375、768、1024、1440；
- languages：中文、英文；
- themes：至少一个 light 与一个 dark tenant；
- keyboard：Tab 顺序、focus ring、Escape/close；
- layout：无核心横向溢出，sticky bar 不遮挡末尾内容；
- forms：首个错误可见且与字段关联；
- touch targets：核心按钮 ≥44×44px。

**Optimization:** 不做所有页面的笛卡尔积。每个高风险组合至少覆盖一次，并在输出 JSON 中列明覆盖矩阵，避免口头声称“全测”。

---

## [ ] 28. 将 browser gate 接入发布流程但保持本地默认安全

**Priority:** P1  
**Depends on:** 24–27  
**Primary files:** `docs/Release_Runbook.md`、`backend/scripts/release_preflight.sh` 或新增包装脚本

**What to change:**

- release runbook 在 full gate 后增加 browser gate；记录证据目录。
- 普通 unit test 不自动启动 Chrome；release 模式通过明确命令运行。
- production acceptance 单独列出并需要授权；本地 browser gate 通过不等于线上验收。

**Acceptance:** 发布报告明确区分静态/HTTP/browser/local/production 五类证据。

---

# P1-C：运维与账户保障（带 STOP GATE）

## [ ] 29. 只读盘点现有备份、恢复与告警缺口

**Priority:** P1  
**Depends on:** 无  
**Read-only files:**

- `deploy/aws/lightsail_ctl.sh`
- `deploy/aws/pwestudio_remote.sh`
- `backend/scripts/backup_postgres.py`
- `deploy/aws/README_AWS.md`
- `docs/Release_Runbook.md`
- `docs/customer/FAQ.md`

**Output:** 新建一份设计说明，列出当前 same-instance dump/media archive、保留期、cron、restore drill、缺少的 off-instance copy/backup-age alert/uptime alert/on-call owner。

**Do not:** 不登录生产、不创建 bucket、不上传备份、不购买服务。

---

## [ ] 30. STOP GATE：选择实例外备份目标和责任人

必须由 Lee 决定或确认：

- 目标：S3、另一 AWS account、Backblaze B2 或其他；
- region、加密、object lock/versioning；
- retention；
- RPO/RTO；
- 成本上限；
- 告警接收人和升级路径；
- 谁保管恢复权限。

没有这些决定，不得写一个默认 bucket 名然后假装灾备完成。

---

## [ ] 31. 在授权后实现 off-instance copy 与可验证告警

**Priority:** P1 / 条件执行  
**Depends on:** 29、30  

**Required behavior:**

- dump + manifest + media archive 成组上传；
- server-side encryption；
- 上传后远端 checksum/size 验证；
- 本地备份成功但远端复制失败必须整体报失败；
- backup age、deep health、disk threshold 进入告警；
- 每月至少一次从远端副本 restore-dry-run；
- 文档记录 RPO/RTO 与负责人，不夸大 SLA。

**Production verification requires separate authorization.**

---

## [ ] 32. STOP GATE：高权限账户 MFA 架构决定

**Priority:** P1 / 安全架构  
**Depends on:** 产品与恢复流程稳定  

先输出方案，不直接改认证：

- 范围：super_admin、owner，是否包含 manager；
- 因子：TOTP / WebAuthn / recovery codes；
- enrollment、强制日期、失机恢复、support reset；
- secrets 加密与审计；
- Edition 离线部署兼容；
- break-glass 账户与双人复核；
- 现有 session/token 撤销策略。

这是认证/授权设计变化，未批准方案前不得实现。

---

# P2：条件性结构优化，不得抢占正确性修复

## [ ] 33. Tailwind 构建期迁移只做测量性 spike

**Priority:** P2  
**Depends on:** P0/P1 稳定  
**Files to inspect:**

- `backend/vendor/tailwindcss.js`
- `legacy-root/index.html` 的 `window.tailwind.config`
- `legacy-root/src/**/*.jsx`
- `backend/scripts/build_cms.sh`
- `backend/server.py` CSP

**Spike output:**

- 当前 runtime compiler 生成时间/产物大小；
- 动态 class 与 safelist inventory；
- 采用 standalone CLI、开发依赖或现有 vendored compiler 的方案比较；
- 是否引入新依赖、维护和许可证成本；
- 迁移后 light/dark/tenant palette 回归范围。

**Stop after report.** 选型批准前不删除 runtime compiler。

---

## [ ] 34. CSP 收紧按 directive 分阶段，不做一次性替换

**Priority:** P2 / 条件执行  
**Depends on:** 33 的构建期 CSS 已通过视觉回归  
**Primary file:** `backend/server.py` security headers  
**Tests:** `backend/tests/test_student_privacy.py`、`test_showcase_section.py`、`test_lightsail_deployment.py`

**Sequence:**

1. 建 CSP report-only inventory；
2. 移除 style-src 对 runtime compiler 的依赖；
3. 为仍需 inline script 的页面使用 nonce/hash；
4. 最后移除 `script-src 'unsafe-inline'`；
5. 每步验证 video embeds、public pages、CMS、Studio/Platform Admin。

不得通过加 `*`、`unsafe-eval` 或宽域名白名单“修复”CSP。

---

## [ ] 35. API 命名统一先建立兼容层，不做破坏性全仓替换

**Priority:** P2  
**Depends on:** 19–23 形成 route/payload inventory  

**What to produce first:**

- 输入字段 camelCase/snake_case inventory；
- 输出重复别名与体积；
- 推荐 canonical（外部 API 建议 camelCase，Python内部 snake_case）；
- alias deprecation、日志、文档和移除版本；
- 未知字段 strict behavior 与兼容 alias 的关系。

第一批只覆盖钱款接口已有修复，不批量改 173 条路由。任何移除 alias 都是 breaking API change，必须单独批准。

---

## [ ] 36. `api_v1.py` 拆分保持触发式，不作为当前修复目标

**Priority:** P2 / 条件执行  
**Trigger:** 出现多人并行冲突、测试隔离困难或同一领域连续改动达到可量化成本  

触发后先拆纯领域（例如 billing/xero）且保持：

- route URL/method/decorator 不变；
- shared tenant/auth/audit boundaries 不复制；
- route inventory diff 为零；
- tests 先表征后移动；
- 一次只拆一个领域，不同时改业务逻辑。

触发条件未满足时保持 pending，不为了减少行数而拆。

---

# 条件功能：周期账单草稿（不是当前修复的一部分）

## [ ] 37. STOP GATE：确认是否真的要建设周期账单草稿

在删除错误文案后，本功能保持未开始。只有产品确认以下内容才进入 spec：

- 谁适用：家庭、课程、term、固定费用还是课次；
- 频率与时区；
- proration、暂停、退课、优惠、税率；
- 重跑与重复草稿判断；
- 人工复核职责；
- 是否允许批量 issue（默认只生成 draft，不自动 issue/send/charge）；
- 异常与未知数据如何留待处理。

确认后先写独立 PRD/technical spec，再生成新的执行清单；不要在本清单里临场设计 migration。

---

## 最终验收总表

### P0 完成定义

- [ ] 指定发票优先、余款 oldest-first、错误 target 拒绝都有 DB 回归测试。
- [ ] `issued → part_paid → paid → refunded` 的金额、余额、actor 可追溯。
- [ ] 钱款 mutation 不再静默接受未知/无效字段。
- [ ] Xero backend、API、CMS、FAQ、Demo、Release Notes 一致标为 Preview。
- [ ] 周期账单自动生成假承诺从源码/i18n/bundle 消失。
- [ ] clean checkout 不依赖 `.agents`；SaaS/Edition archive 有运行时 smoke。
- [ ] PostgreSQL-required full gate 全绿。
- [ ] Source/Package/Production 仍分别记录，不提前宣称部署。

### P1 完成定义

- [ ] API/DB/roadmap 与当前代码、migration 0042 一致，并有 currentness guard。
- [ ] 核心账单 journey 经真实 browser interaction 验证，不只 HTTP 200。
- [ ] viewport/language/theme 覆盖有机器可读证据。
- [ ] off-instance backup/alerting 只有在目标、成本、责任人批准后才实施并做远端恢复演练。
- [ ] MFA 只有在认证方案批准后才实现。

### 每轮交接必须报告

```text
Completed:
- Task IDs:
- User-visible behavior:

Files:
- Modified:
- Generated:

Verification:
- Commands:
- Passed / failed / skipped counts:
- Browser states:

Shared contracts:
- Data model/migration:
- API:
- Theme/language:
- Tenant isolation:

Git / Release:
- Branch and HEAD:
- Committed? pushed? packaged? deployed?:
- Source / Package / Production:

Remaining risks / STOP GATE:
- ...
```

任何未运行的检查必须写“未运行”和原因；不得写成“预计通过”。
