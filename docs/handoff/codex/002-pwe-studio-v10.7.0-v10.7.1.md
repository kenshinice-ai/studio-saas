# PWE Studio v10.7.0 — 第二轮审计完成，v10.7.1 待执行

> 审计时间：2026-08-16（Australia/Melbourne）
>
> 下一轮 Luna-Max 权威执行文件：
> `docs/design/Repair_Execution_Checklist_v10.7.1_Luna_Max.md`。
>
> 本轮只审计并更新方案/handoff；没有修改运行时代码，没有 commit、package、push 或 deploy。

## 当前真相

| 层 | 当前事实 | 证据 |
|---|---|---|
| Source | `main == origin/main == 1155bbd30f5f151f26fb44fbf89f47035100dc5a`，worktree 在本轮文档修改前 clean | `1155bbd` 是 v10.7.0 release ledger 的 docs-only closure commit；运行时 release commit 是 `913c6f1…`。 |
| Package / SaaS | 已发布的 v10.7.0 包保持不变 | `PWE-StudioSaaS-aws-10.7.0.tar.gz`；SHA-256 `5c31847b3583889ac5613f4d73915f08ef65282632a07cd7acccaaba07441b22`；`BUILD_INFO` 指向 `913c6f1…`。 |
| Package / Edition | 已发布的 v10.7.0 包保持不变 | `PWE-Studio-Edition-10.7.0.tar.gz`；SHA-256 `1bc04e0c0bab5960d05936a096ed26607651827363b1dc2c0341c195e11d9a3e`；`BUILD_INFO` 指向 `913c6f1…`。 |
| Production | 仍运行 v10.7.0，深健康正常 | 2026-08-16 复核：`appVersion=10.7.0`、`mode=saas`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`。 |
| 第二轮 targeted audit | 现有测试通过，但没有覆盖本轮发现的语义缺陷 | public shell、payer、invoice、settlement/refund、document/export、CMS tests：`84 passed, 6 skipped`。 |

## 审计结论

### P0 — 导航验收结论需要纠正

- 用户截图中的问题已在生产复现，不是截图偶发：lets-paint-showcase 的 `/showcase` 与 `/timetable` 在 **1440px** 都是 `brand-name-hidden nav-tight`，桌面 `.navlinks` 为 `display:none`，只显示 hamburger。
- timetable 新加载在 `901/1024/1226/1440/1920` 均整体折叠；`1440 → 375 → 1440` 也回到相同错误状态，因此不是单纯 sticky resize class。
- 同一宽度的 portal home 在 1440px 能显示桌面 links；代码证据是 home 已把 nav row 扩到 1600px，而 showcase/timetable 仍复制 1180px 上限和不同 logo/gap 合同。
- v10.7.0 原验收只断言 `scrollWidth == clientWidth`。这个断言证明“没有横向溢出”，不证明“桌面导航正确显示”；其 public A/F PASS 不再作为 NAV-01 的关闭证据。

### P0 — 充值/退款仍有两条旧接口旁路

- 未勾选发票的 top-up 仍调用旧 `/credit-transactions`，绕过 v10.7.0 已实现的 `credit-settlements` request-id 幂等服务。
- 未勾选同步单据的退款也调用旧 endpoint，只在 note 中拼入原充值 UUID；`refundable_purchases()` 只累计 financial bridge 的退款，所以 credits-only refund 不会减少该 source 的可退额度。
- v10.7.1 应新增 tenant-scoped refund source relation，并让 checkbox 两侧都走同一 idempotent command；旧 endpoint 仅保留兼容/普通调整用途。

### P0 — 贷记单税率与 PDF fallback 不完整

- `credit_refunds.py` 当前按退款占比再次缩放 `tax_rate_bp`；10% GST 的 partial/full refund line 可写成错误 bp。现有测试只检查 tax cents/header totals，没有检查 line tax rate。
- “打印 / 存为 PDF”当前打印 CMS 详情卡，缺供应方完整抬头、ABN、地址、收件方完整身份和 issue/due metadata，却包含内部事件历史。它不能作为合格的客户发票输出。
- v10.7.1 应从 `detail.document` 渲染独立 customer document；server PDF 仍须等 SaaS/Edition/CJK renderer gate 通过后再实现，不得冒充下载能力。

### P0/P1 — 付款方与手工发票继续收口

- 0 payer 学员路径声称“人工复核”，实际没有可编辑预填表单，提交会隐式创建 payer；这必须在 issued snapshot 冻结前修复。
- 手工发票仍是 create payer → create draft → per-line POST，多步失败/重试会留下重复 payer 或半成品草稿；下一步用 tenant-scoped aggregate/idempotent command 收口。
- `possibleDuplicates` 当前在 payer 已创建后才返回，且两个 UI 调用方都忽略；下一轮改为创建前候选提示与显式例外，不自动合并。

## 下一轮顺序

1. **P0-01** 统一 public nav CSS/状态机，增加 1226/1366/1440/1920 桌面语义断言。
2. **P0-02** migration 0044 + 所有 top-up/refund 分支统一幂等服务 + 显式 refund source。
3. **P0-03** 修复 credit-note line 税率并增加 Document DTO 端到端测试。
4. **P0-04** 建立独立客户打印发票；当前仍诚实命名“打印 / 存为 PDF”。
5. **P0-05** 完成 payer 0/1/N 可编辑/可确认状态。
6. **P1** 手工 invoice aggregate command、重复保护、credit-note 导出与 fully-credited 可读性。
7. 完整门禁后停在 **v10.7.1 唯一发布 STOP GATE**，等待 Lee 明确授权 commit/package/push/deploy。

## 本轮边界

- v10.7.0 source/package/production 继续作为稳定基线，不原地重写。
- Xero 继续是 Preview；本轮只补可靠 source/document/tax 输入合同，不实现真实 transport。
- 下方原 v10.7.0 发布记录保留为历史证据；其中“无横向溢出”不能再被解读为 NAV-01 已通过。

---

