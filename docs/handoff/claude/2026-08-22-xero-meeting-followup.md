# 2026-08-22（Claude Fable 5）Sinobeats 会后 —— Xero 链路到底卡在哪

> 会上反馈：① Xero 连接不流畅，Demo Company 没收到新开的发票；② Xero 能否自动对账；
> ③ 界面问题记录即可，不是现在；④ 重点先把 Xero 链路跑通。
> 本文只管 ①②④。③ 已在 `docs/design/CMS_Settings_Restructure.md`、
> `CMS_Roster_Two_Jobs.md`、`CMS_Settings_and_Roster_Integrated_Plan.md` 三份里，原样不动。

## 一句话

**Demo Company 没收到发票，不是推送失败，是从来没有推送过。** 音乐租户的推送开关
从未打开（`push_enabled = false`），因为网关第四步「测试组织试跑」从未完成；会上
唯一一次「不流畅」是播种器伪造的 Xero 连接没有 token，`测试令牌自愈` 返回 409，
逼着现场重连。而且即使开关打开，音乐租户的发票也会**全部被拒**——它和美术样板
共用同一个 Demo Company，发票号 `INV-0001..6` 与美术的 `INV-0001..8` 撞号，
`_refuse_foreign_number` 会逐张拒绝。美术样板 → Demo Company 这条链**是通的**，
Demo Company 里能看到 `PWE INV-0005..0008`，状态 Paid，付款也推到了。

## 一、会上到底发生了什么（服务端日志，UTC+10 换算）

| 墨尔本时间 | 请求 | 含义 |
|---|---|---|
| 13:36 | `GET /integrations/xero` + `/queue` | 打开集成页 |
| 13:45 | `POST /integrations/xero/single-entry` 200 | 回答了第五步「单一入口」→ `ours_only` |
| 13:49 | `POST /integrations/xero/refresh-check` **409** | 「测试令牌自愈」失败：连接没有 token |
| 13:49 | `POST /connect-url` 200 → `GET /xero/callback` 302 | 现场重连，落到 **Demo Company (AU)** |
| 13:50–13:52 | 只有 GET 轮询 | **没有任何** `POST /gate`（试跑）或发票开具 |

之后队列表 `integration_sync_jobs` 里音乐租户 **0 条**作业，`xero_object_links` **0 条**。
Demo Company 当然什么都没有。

## 二、根因链（每一环都有证据）

### 1. 播种器伪造了一条「已连接」的 Xero 连接，没有 token

`reset_professional_demo.py:1018-1024` 往 `xero_connections` 写
`status='connected'` + `org_name="Let's Paint Studio (Demo Org)"`，**不写任何 token**。
于是集成页显示「已连接」，而 `xero_refresh_check`（`api_v1/xero.py:126-146`）调
`ensure_access_token` 必然抛 `XeroOAuthError` → 409 → 状态被写成 expired → 现场只能重连。

这就是「不流畅」的全部来源。同一段播种还把 `mapping_confirmed_at = now()` 直接写进
`xero_sync_settings`（`:1027`）而**不写任何映射行**——所以截图里第三步打着勾、
旁边却写「还差 tuition、bank」。`confirm_mapping`（`services/xero.py:235-247`）本来会
拒绝空映射，播种器绕过了它。

### 2. 网关第四步从未完成，开关打不开

`GateStatus.can_enable`（`services/xero.py:158-165`）要求 `demo_run_completed`。
它只由 `POST /integrations/xero/gate {step:"demo_run"}`（`api_v1/xero.py:265-271`）写入，
而且 X3 起这一步是**真动作**：`run_demo_cycle` 回填 → 排空 → 对账，报告 `clean`
才记完成。会上没人点过这一步。音乐租户 `demo_run_completed_at = NULL`、
`push_enabled = f`（实查）。

### 3. 就算打开了，音乐发票也会全部被拒：撞号

两个样板租户连的是**同一个** Demo Company (AU)（`xero_connections` 实查），
一个 Xero 账号只有一个 Demo Company，这不可避免。而两个租户的单号序列都从
`INV-0001` 开始（`reset_professional_demo.py:818` 把前缀写死为 `'INV-'`）：

| 租户 | 发票号 |
|---|---|
| lets-paint-showcase | INV-0001 … INV-0008（已在 Demo Company） |
| music-studio-showcase | INV-0001 … INV-0006 |

`_refuse_foreign_number`（`xero_transport.py:303-325`）对「号已存在且不是我方链接」
**硬拒绝**——这是 X4 真账本上学来的、绝不能删的守卫（Xero POST 按单号 upsert，
会静默覆盖别人的单据）。所以音乐的六张会逐张失败。

`document_number_sequences.prefix` 是按租户的列，解法在数据层已经存在：
**音乐包自带前缀**（例如 `ZY-`），播种器从包读而不是写死。

### 4. 真账本上有一条死作业（顺带）

`lets-paint-studio`（PWE GROUP 真账本）有一条 `failed` 作业：对应本地 `INV-0001`，
8/19 10:47 推送时撞上真账本里多年前的 `INV-0001`（400：paid invoice…），
**这条作业早于撞号守卫（v10.10.3）**。本地那张发票随后已作废（`status=void`，
无链接、无分配）。排空器只取 `status='queued'`（`xero_transport.py:535`），
所以它会一直挂在集成页的失败列表里。按「重放」会走 `xero_transport.py:334-336`
的 `voided before it was ever pushed` → 标 skipped，**不会碰 Xero**。

## 三、Q2：Xero 能不能自动对账我们推过去的发票

### 我们推的是什么

- 发票：`ACCREC`、`Status: AUTHORISED`、`InvoiceNumber = 本地号`、
  `Reference = "PWE <号>"`、`LineAmountTypes: Exclusive`、联系人按付款人姓名建
  （`xero_transport.py:350-361`）
- 付款：`PUT /Payments`，挂到映射里的 **`bank`** 科目，
  `Reference = "PWE payment <id 前 8 位> (<方式>)"`（`:489-499`）

也就是说：发票到 Xero 时已经是「待付款」；付款到 Xero 时，发票变「已付」，
同时在那个银行科目里生成一条**银行交易**，等着和银行流水行匹配。

### Xero 那边

Demo Company 的对账页实看：右上有 **Auto-reconcile 开关**（默认 OFF），
横幅写「最近 30 天导入的 84 条流水里 24 条已自动对账」。开关打开后，
一条流水**只有唯一、高置信的匹配**（金额相等 + 日期接近 + 联系人/参考能对上）
时才自动对平；否则留在「Reconcile」列等人点 OK。

**实看 Demo Company 的 Business Bank Account → Account transactions**：我们推的七笔付款
（`PWE INV-0002/0004/0005/0006/0007/0008`，Payment Ref `PWE payment <id> (bank_transfer|cash)`）
**全部 Unreconciled**，与 Demo Company 自己的 `Auto-Reconciled` 条目并排。原因不是我们推错了，
而是 Demo Company 没有与这些付款对应的银行流水行——自动对账对的是「流水行 ↔ 账内交易」，
账内交易已经在，流水行不在。真账本上流水行来自银行 feed，那时这七笔才有东西可配。
对账页（Reconcile 那一栏）搜 `PWE` 搜的是流水行那一侧，所以搜不到，这也是正常的。

### 什么情况能自动对、什么情况不能

| 收款方式 | 银行流水长什么样 | 能否自动匹配 |
|---|---|---|
| 家长银行转账，备注写了发票号 | 一笔 = 一张发票，金额相等 | **能**，前提是我们的付款日期与到账日期相差不大 |
| 家长转账，备注只写孩子名字 | 金额相等但参考对不上 | 多半能（Xero 主要看金额+日期），偶尔要人点 |
| 部分付款 / 多张合付 | 金额与任一付款都不等 | 不能，要 Find & Match |
| **Square**（Sinobeats 现状） | 一笔入账 = 一天的多笔刷卡 **扣掉手续费** | **不能**。金额永远对不上单笔付款 |

Square 是会上这家客户的收款方式，所以这一行是重点。

### 产品现在的缺口：`clearing_account` 这个选项是空的

第五步「单一入口」有两个答案：`ours_only` 和 `clearing_account`
（`services/xero.py:254-282`，后者要求填 `clearing_account_code`）。
但传输层**从不读它**——`xero_transport.py` 里 `_account_for` 只对行科目和
`"bank"` 调用（`:186`、`:489`），`clearing` 映射和 `clearing_account_code`
在推送路径上零引用。也就是说，选了「走清算账户」的工作室，付款照样推进银行科目。

对 Square 用户正确的做法是：付款推进一个 **Square 清算科目**，Xero 那边用
Square 的银行 feed（或每日结算入账）与清算科目做转账匹配，手续费单独记费用。
这是一个传输层改动（付款 `Account.Code` 按 `single_entry_decision` 选），
加一条「清算科目必须是 Xero 里 `EnablePaymentsToAccount` 的科目」的校验。

### 给客户的口径

「发票和收款都会自动到 Xero；银行对账那一步，转账收款 Xero 能自动对平大部分，
Square 收款要走清算账户——我们会把这个配好，你们会计看到的是每天一笔结算入账
对一笔清算转账，而不是几十笔小额。」**不要**承诺「全自动对账」。

### 真账本上的注意事项

- 真账本 Auto-reconcile 先别开，等 X4 这个结算月看过匹配率再说。
- Demo Company **每 28 天重置**，`xero_object_links` 会悬空；传输层遇 `not_found`
  会去掉 `InvoiceID` 重建（`:365-369`），守卫仍在，是安全的，但 soak 数据会清零。

## 四、修什么、按什么顺序

| # | 事 | 改哪里 | 大小 |
|---|---|---|---|
| 1 | **音乐包自带单号前缀**，播种器从包读；重播种 | `music_showcase_content.py` 加 `INVOICE_PREFIX`；`reset_professional_demo.py:818`；`_select_pack` required 元组 | 小 |
| 2 | **播种器不再伪造 Xero 连接、不再预写 `mapping_confirmed_at`**；演示的「已加购」保留，连接留给人工点 | `reset_professional_demo.py:1018-1030` | 小 |
| 3 | 真账本那条死作业：按「重放」让它变 skipped；并让排空器对本地 `void` 的 `failed` 作业自动 skipped | 集成页按钮 / `xero_transport.py:535` 附近 | 小 |
| 4 | **传输层实现 `clearing_account`**：付款科目按决定选；校验科目可收款 | `xero_transport.py:489`、`services/xero.py` | 中 |
| 5 | 音乐租户走完网关：映射 `tuition` + `bank` → 确认映射 → **试跑** → 开推送 | 集成页操作，无代码 | 人工 |
| 6 | 集成页「已连接」徽标改为**先过一次 `refresh-check` 再显示**，避免再出现「显示已连接、一点就 409」 | `integrations.jsx` | 小 |

1–3 一个补丁（v10.12.1，与会面卫生补丁合并）；4 单独一个（它改的是真账本的付款路径，
要先在 Demo Company 跑一个周期）；5 在 1–2 上线并重播种之后由人操作；6 随 4。

## 五、要 Lee 拍板的

1. 音乐包前缀用什么（建议 `ZY-`，三字母以内、不与任何客户真实前缀撞）。
2. 真账本那条死作业我来按重放吗（安全：本地已作废，传输层直接 skipped，不碰 Xero）。
3. `clearing_account` 现在实现，还是等 Sinobeats 签约后再做——它是这家客户的必经路径。

## 六、本轮没动的

- 没有在生产按任何按钮、没有改 Xero 任何数据、没有重播种。
- 没有碰三份 UI 方案。
