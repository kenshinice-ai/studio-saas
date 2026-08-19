# 2026-08-19 Xero X4 轮（开轮）—— 真实账本 Beta 月

> 目标（Full_System_Audit_Plan Batch F X4）：Lee 的真实工作室租户 `lets-paint-studio`
> 单向推送接真 Xero 组织 **PWE GROUP PTY LTD**，跑一个完整结算月；出口 = 一个自然月
> 0 人工修账。非目标不变：双向、付款回导、X4 起点前历史回填（本租户账务面为零，
> 天然无此问题）。

## 租户甄别（关键纪律）

生产 6 租户中真实档案是 **`lets-paint-studio`**（active，44 名学员，0 张发票、
0 付款方、无开票信息）——**不是** `lets-paint-showcase`（合成演示数据，绝不允许
推入真实账本）。showcase 保持 Demo Company 推送开启不动，作为长期 soak。

## Lee 拍板（2026-08-19 会话，AskUserQuestion 记录）

1. 开票信息：法定名称 PWE GROUP PTY LTD；ABN/地址 **Lee 自己在 CMS 填**（E6 门，
   填好前无法开票）。Xero Organisation details 里有现成值可照抄。
2. 收款账户：**ANZ AU LETS PAINT**，授权我在 Xero 里给它加 code **090**（已完成，
   见下）。
3. 单一入口：**没有**其他系统向 PWE GROUP 写销售单据 → `ours_only`（银行 feed
   只是流水对账，不算通道）。
4. 首单：由我建**小额测试性质真单**（$1 学费 + GST）走试跑；随后正常业务单据照常。

## 已完成（本轮）

- `xero` 加购授予 `lets-paint-studio`（super-admin API，audit note 记 X4 beta）。
- 平台账号进真租户 CMS 走**带原因的审计支持会话**（支持门按设计拦截后走正门）。
- 真租户连接 **Demo Company (AU)**（向导规矩：先演示账套试跑，后切真账本）。
- 映射保存：tuition→200/OUTPUT、bank→090（Demo 与真账套代码一致，切换后免改）。
- **PWE GROUP 科目表核对**（Lee 登录的 Xero 只读翻阅）：200 Sales / GST on Income
  存在 ✔；两个银行账户原本都无 code——已按授权给 **ANZ AU LETS PAINT 设 code 090** ✔
  （Business Account - ANZ 未动）。
- **v10.10.2**：`finish_connect` 不再取 `orgs[0]`——同一 Xero 用户多组织并存时，
  按本次授权事件匹配（access token `authentication_event_id` ↔ 连接行
  `authEventId`），无匹配回退最新连接。这是切真组织前的硬前置（否则重连 PWE GROUP
  可能静默连回 Demo Company）。回归测试
  `test_finish_connect_selects_the_org_this_consent_granted`。

## 接入完成（2026-08-19 关账，v10.10.3）

- 开票信息：Lee 自填后我修两处——法定名称笔误「PWE GROU」→ PWE GROUP PTY LTD、
  勾 GST 注册（其 200 Sales 用 GST on Income 且有真实 GST 流水，事实即已注册；
  ABN 55606664546 校验位验证通过）。E6 门放行，INV-0001（$1.10 测试单）开具。
- **同号冲突现场发现（→ v10.10.3）**：试跑把真租户 INV-0001 推向 Demo Company 时，
  Xero 报「不能改已付发票」——**Xero 的 POST 按单号 upsert**，同号会静默更新
  别人的现存单据。查 PWE GROUP：已有 36 张真实已付 INV-0026…0051。若无守卫，
  推送将改写真账本。v10.10.3 上创建路径按单号预查（`GET /Invoices/{number}`），
  号已存在且非本工作室链接 → 立即死信带可操作原因；测试
  `test_a_number_the_org_already_holds_is_refused_not_overwritten`。
- 单号系列：真租户序列改用独立前缀 **LPS-INV- / LPS-CN-**（`document_number_sequences`
  数据变更，next_value 连续不断号）；INV-0001 作废（原因记档），重开
  **LPS-INV-0002**。前缀在正式开票前仍可按 Lee 意愿更换。
- 组织切换：断开 Demo Company → 重连授权页选 **PWE GROUP PTY LTD** →
  卡片显示已连接 PWE GROUP PTY LTD——v10.10.2 的 authEventId 匹配在多组织下
  实测选对（此前 orgs[0] 会看 Xero 排序脸色）。
- 向导收口（全部对真账套）：映射确认 ✔ → **试跑 clean（排队 1 / 推送 1 / 失败 0 /
  对账差异 0）** ✔ → 单一入口 ours_only ✔ → **推送开启（blockers=[]）** ✔。
- **肉眼证据**：PWE GROUP 发票列表首行 `LPS-INV-0002 · Ref "PWE LPS-INV-0002" ·
  X4 Acceptance Test · 19 Aug 2026 · Due 1.10 · Awaiting Payment`，
  与 36 张历史 INV-#### 序列并存互不干扰（37 items）。
- 发布链：v10.10.3 提交 `dae3fd4`；SaaS SHA-256 `9db6217b…6d631`、Edition
  `948073bc…59154`；部署前 dump `…105709Z.dump`；deep health appVersion=10.10.3。

## 结算月（进行时）

- Lee 正常开票收款：新单据经 allocate/issue 钩子自动入列，`xero-push.timer`
  每 5 分钟推送；失败进集成页错误队列（原因几乎总是映射）。
- 月度对账 = `GET /integrations/xero/reconciliation`（逐张读回按分比对）。
- X4 出口：一个自然月 0 人工修账。届时出对账报告，集成页转正（X5 按套餐开放门已在）。
- 备忘：集成页 Beta 徽标未做（纯文案，随下轮 UI 顺带）；showcase 仍连 Demo Company
  推送开启作长期 soak；LPS-INV-0002 为 $1.10 真实应收，Lee 可收款或作废，两条路
  都会被队列/对账如实跟进。
