# 2026-08-19 Xero X3 轮 —— 外发 transport（v10.10.0）

> 前置：X2 已在 v10.9.4 关账（连接/自愈/断开重连三点验收 ✔，scope 终稿）。
> 本轮按 Full_System_Audit_Plan Batch F X3 行：队列消费、幂等、退避重试、死信可重推、
> systemd timer（不引 Redis/Celery）；出口 = sandbox 全量单据类型往返对账 0 差异。

## 交付面

- **迁移 `0047_xero_transport.sql`**：`integration_sync_jobs` 加 `next_attempt_at`（退避住在行里，
  重启丢不了）与 `last_attempt_at`；`xero_object_links` 加 `org_id`——**链接只在一个组织内有意义**，
  从 Demo Company 换到正式账套后旧 id 全部失效，带 org 的链接让重连后重新建档而不是去改
  demo 账本里的幽灵单据。
- **`services/xero_transport.py`**（新）：
  - 金额规则：每行 `Quantity=1`、`UnitAmount=net`、显式 `TaxAmount`，真实数量进描述
    ——Xero 自己的按行 2dp 税额重算会把 $605.00 对成 $604.99，我们推的是自己 cents 的原值。
  - Contact 以 `ContactNumber=billing_account_id` 为客户键 upsert；同名冲突确定性加后缀；
    404（demo 账本被重置）自动降级为新建。
  - invoice：ACCREC / AUTHORISED / `InvoiceNumber=本地号`；void → VOIDED（有收款时 Xero 拒绝
    → 死信给人看）。credit_note：ACCRECCREDIT + 对其 invoice 的 Allocation。payment：
    **以 allocation 为推送单位**（拆到多张发票的一笔收款 = 多个 Xero Payment），入账账户走
    `bank` 映射。
  - 失败分类：429/5xx/网络 → `next_attempt_at` 指数退避（1,2,4…分钟，封顶 60）；4xx 校验
    → 立即死信带 Xero 原文；依赖未就绪（付款先于发票）→ 短退避。上限 8 次后死信。
  - `backfill`：把当前 org 没见过的已开具单据全部入队（幂等键含 org）；**故意无视推送开关**
    ——试跑发生在开关合法打开之前，年末暂停后的补推也走它。
  - `reconcile`：逐张 GET 读回，按分比对 total/amount/void 状态；出口标准就是它报 0 差异。
  - `run_demo_cycle` = backfill → drain → drain（清依赖延迟）→ reconcile；
    `pushed>0 且 0 差异 且无失败` 才算 clean。
- **`xero.py`**：`TRANSPORT_AVAILABLE = True`（stage=live）；enqueue 幂等键默认带当前 org。
- **入队钩子**：发票开具（API 层，原有）；作废（新，revision='void'）；
  `payments.allocate()`（服务层唯一 INSERT 点，覆盖所有收款路径）；
  `credit_refunds` 贷记单开具处。钩子在 gate 关闭时是 no-op。
- **API**：`POST /integrations/xero/push-now`（请求内有界 drain，两遍清依赖）、
  `POST /integrations/xero/backfill`、`GET /integrations/xero/reconciliation`（逐张真读回）、
  `GET /integrations/xero/queue`；gate 的 `demo_run` 从「记时间戳」换成真跑
  `run_demo_cycle`，clean 才落 `demo_run_completed_at`。
- **worker**：`backend/scripts/xero_push_worker.py`（遍历租户→绑 RLS→gate 开才 drain，
  每行打印即观测面）；`deploy/aws/xero-push.service|.timer`（5 分钟，oneshot 防重叠）；
  `lightsail_ctl.sh` 新增 `exec-app`；`install_xero_push_timer.sh` 操作员一键装（systemd
  单元与 nginx 一样在包外，装/更新都走这个脚本）。
- **UI（integrations.jsx）**：映射编辑器（tuition/bank 必填；lesson/manual 按 tuition 入账
  ——声明的规则不是静默兜底）+「会计已确认」；「测试组织试跑」真按钮带报告；推送队列卡
  （计数、失败带原因一键重放、排队积压、立即推送、逐张对账）。
- **产品真话契约更新**：`test_product_truth_contract` / `test_xero_product_truth` 断言翻到
  live；FAQ 与 Demo_Runbook 从「Preview、不发数据」改为「门后单向推送、开关未开不发数据、
  演示只对 Demo Company」。BANNED_LIVE_CLAIMS 列表在 transport 存在时自动豁免（原设计）。

## 明确非目标（X4 起）

双向同步、付款从 Xero 回导、退款/已推送后的收款释放同步（会在对账报告里显形，X4 真账月
处理）、历史数据策略不变。

## 测试

`test_xero_transport.py` 12 项（金额精确性、映射缺失命名拒绝、backfill 幂等、
drain 依赖排序+org 链接、付款依赖延迟、校验死信 vs 退避、换 org 重推、对账 0 差异/1 分钱、
demo cycle clean 判定、allocate 钩子）。全量 pytest 2857 passed / 7 skipped。

## 发布与验收证据

- v10.10.0 部署 ✔（deep health appVersion=10.10.0、迁移 0047 应用）；
  systemd timer 安装并首跑 ✔（`xero-push: tenants=6 gate-closed=6 jobs=0 tenant-errors=0`）。
- 生产 showcase 向导实走：映射 tuition/package=200/OUTPUT、bank=090 保存 → 会计确认 →
  **第一次试跑：排队 15 / 推送 13 / 失败 1 / 对账差异 0**——失败的一张正是设计要抓的：
  「No account mapping for line kind 'engagement'」，其收款按依赖正确延后；
  补 engagement 映射 → 「修好了，重放」 → 立即推送 → 已推 15。
- 为拿单次 clean 试跑，经 API 开具 INV-0008（$22.00，Chen 一家）→ 再试跑：
  **排队 1 / 推送 1 / 失败 0 / 对账差异 0 → 试跑通过**，demo_run 落账。
- 单一入口答 ours_only → 「开启推送」→ **500**：`xero_push_requires_preconditions`
  CHECK 违反。根因：`_upsert_settings` 的 INSERT 候选行（push=true、前置全 NULL）
  在 PG 里先于 ON CONFLICT 被 CHECK 评估——transport 关闭时代不可达的缺陷，
  首次真实过闸暴露。**v10.10.1** 修复：合闸改纯 UPDATE；回归测试
  `test_enabling_push_through_the_walked_gate_survives_the_check_constraint`
  用真实服务函数走完整向导对真约束验证（13 项 transport 测试全过）。
- v10.10.1 部署与开闸后验收（推送开启、新单据自动入列、Xero 界面肉眼可见）见下补。
