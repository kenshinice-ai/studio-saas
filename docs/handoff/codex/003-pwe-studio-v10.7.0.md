# PWE Studio v10.7.0 — 已提交、已打包、已部署、已验收

> 更新时间：2026-08-16（Australia/Melbourne）
>
> 依据清单逐项执行完成 A–F；Lee 已授权并完成
> **commit → package → push → sync main → production deploy → browser acceptance**。
> 逐项执行文件是
> `docs/design/Invoice_Operations_Execution_Checklist_v10.6.4_Luna_Max.md`。
>
> F-01 证据包：`docs/design/Invoice_Operations_Acceptance_Evidence_v10.7.0.md`。

## Source / Package / Production 分层

| 层 | 当前事实 | 证据 |
|---|---|---|
| Source | **v10.7.0 已提交并推送** | `main`/`origin/main` = `913c6f168052213535fbeae9da0197de9e655959`；`VERSION=10.7.0`。 |
| Package / SaaS | **v10.7.0 已构建并校验** | `PWE-StudioSaaS-aws-10.7.0.tar.gz`；SHA-256 `5c31847b3583889ac5613f4d73915f08ef65282632a07cd7acccaaba07441b22`；`BUILD_INFO` mode `saas`，commit `913c6f1…`。 |
| Package / Edition | **v10.7.0 已构建并校验** | `PWE-Studio-Edition-10.7.0.tar.gz`；SHA-256 `1bc04e0c0bab5960d05936a096ed26607651827363b1dc2c0341c195e11d9a3e`；`BUILD_INFO` mode `standalone`，commit `913c6f1…`。 |
| Production | **v10.7.0 已部署并验证** | `pwestudio.online`：`appVersion=10.7.0`、`mode=saas`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`；current/BUILD_INFO 指向 `913c6f1…`。 |

## v10.7.0 已完成内容

- 公共页面：portal/showcase/timetable/index shell 收缩契约、320–1440px 中英无横向溢出、键盘菜单回归；清理旧“课时充值发票行”伪联动。
- 付款方与发票：`billing_accounts.kind=person|family|organisation`、学员 0/1/N 付款方解析、重复提示、tenant-scoped atomic link、issued supplier/recipient snapshot 与 immutability。
- 文档与导出：InvoiceDocument DTO、整数分/Decimal quantity、summary/lines UTF-8 BOM CSV、公式注入保护；PDF renderer spike 未通过，因此仅提供诚实的“打印 / 存为 PDF”。
- 充值与退款：单一 migration 0043、bridge/idempotency、`credit-settlements` 与 `credit-refunds` 原子服务/API/UI；贷记金额累计回原发票 `amount_credited_cents`，invoice detail 暴露 credit notes，账本/付款/贷记单/余额一致。
- Xero：仍为 Preview；没有 OAuth、provider transport、worker 或 webhook，不把入队称为已同步。

## v10.7.0 验收证据

- 浏览器真实流程：Ana Bianchi top-up → `INV-0006` paid → explicit-source refund → `CN-0002` issued、payment `refunded`、invoice `Credited $110 / Balance $0`、credit balance 回滚；`375/768/1024/1440` billing/refund shell 无溢出，light/dark/中英与 public shell 回归已核对。
- 目标测试：invoice/document/export、settlement/refund、CMS source/bundle contracts **36 passed**；全套 pytest **2664 passed, 7 skipped**。
- 完整 gate：`verify_local.sh` **all checks passed**；legacy CMS smoke **73/73**；tenant isolation + Edition checks **254/254**；migration、媒体衍生物、CMS bundle/manifest、Python/JS/shell/terminology 全绿。
- 数据库：migration 0043 已在本地 PostgreSQL upgrade 库执行且幂等；浏览器 fixture 仅使用本地测试租户，未触及生产数据。
- 发布证据：SaaS/Edition v10.7.0 包 hash、`BUILD_INFO`、生产备份、migration、深健康、路由、bundle hash/immutable cache、media ETag/304 与浏览器验收均已记录。

## 发布闭环

Lee 已明确授权 v10.7.0 与 `pwestudio.online`，并完成
`commit → package → push → sync main → production deploy → browser acceptance`。
生产控制器已在切换前创建 PostgreSQL/volume 备份，应用 migration
`0043_invoice_and_credit_settlements.sql`，重生成 10 个 tenant workspace，
并通过内部/公网深健康与 stored-theme readability。后续同一发布标签不得
重写或复用；若需后续变更，应创建新的版本号。

## 当前决策账本

| 主题 | 上一版方案 | 当前决定 | 状态 | 置信度 |
|---|---|---|---|---|
| 发布边界 | v10.6.5 → v10.7.0 → v10.7.1 三次发布 | 合并为一次 v10.7.0 | **Superseded** | 高：三部分共享 payer/snapshot/document/settlement 合同 |
| 数据迁移 | 0043 snapshots、0044 bridge/idempotency | 单一 0043 同时建立全部不变量 | **Superseded** | 高：没有中间生产版本需要兼容 |
| 执行门禁 | 每个小版本各自 STOP GATE | A–E 为内部 targeted gate，F 为唯一发布 STOP GATE | **Superseded** | 高：保留质量控制但减少重复发布链 |
| Xero transport | v10.8.0 Beta 独立实现 | 仍为后续独立 Beta，v10.7.0 只准备可靠输入合同 | **Unchanged** | 高：仍缺 OAuth、真实 transport、worker 与 demo org 验收 |

