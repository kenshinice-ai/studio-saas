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

## 待办（依赖顺序）

1. Lee 在 CMS 填开票信息（E6）→ 我建付款方「X4 Acceptance Test」+ $1+GST 测试单并开具。
2. 试跑（推 Demo Company）clean → 单一入口 ours_only → 断开 → 重连选 **PWE GROUP
   PTY LTD**（v10.10.2 保证选对）→ 开启推送 → 排队积压（即那张测试单）→ 定时器推送
   → 对账 0 差异 → PWE GROUP 界面肉眼可见。
3. 集成页标 Beta（真组织推送期间）；月度对账报告的取数路径即 reconciliation API。
4. 结算月开始：Lee 正常开票收款，队列自动推送；月末出对账报告，0 人工修账 = X4 出口。
