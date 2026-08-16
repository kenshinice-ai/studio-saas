# v10.7.0 发票运营验收证据（源码候选）

> 日期：2026-08-16（Australia/Melbourne）
>
> 这是 `Invoice_Operations_Execution_Checklist_v10.6.4_Luna_Max.md` 的 F-01
> 证据包。它记录的是当前工作树，不是发布、打包或生产部署证明。

## 发布边界

- `VERSION` / `APP_VERSION`：`10.7.0`（工作树，未 commit）。
- `main == origin/main` 基线：`1043fe3f30e49c89358065a7ab07878f9f23e5cd`（v10.6.4）。
- 最后已验证 SaaS/Edition 包与生产运行时：v10.6.4；v10.7.0 尚无 commit、package hash、push 或 production health。
- Xero 仍为 Preview；本轮没有 OAuth、provider transport、worker 或 webhook。

## 阶段结果

| 阶段 | 结果 | 关键证据 |
|---|---|---|
| A | PASS | public portal/showcase/timetable/index 320/375/390/768/1024/1440 无横向溢出；旧课时充值伪联动已清除。 |
| B/C | PASS | migration 0043 已应用且幂等；payer 0/1/N、自定义 person/organisation、snapshots、InvoiceDocument、CSV、PDF spike/fallback 通过。 |
| D | PASS | `credit-settlements` 四组合、gross 税额整数分、原子 rollback、request-id replay 通过。 |
| E | PASS | explicit-source full/partial/multiple/overage/no-bridge/cross-tenant/idempotency 与角色边界通过。 |
| F | PASS（STOP GATE） | 完整门禁与真实浏览器流程通过；等待授权后才能形成发布物。 |

## 自动化门禁

```text
targeted invoice/document/export/settlement/refund/CMS contracts: 36 passed
full pytest: 2664 passed, 7 skipped
verify_local.sh: all checks passed
legacy CMS smoke: 73 passed, 0 failed
tenant isolation + Edition checks: 254 passed, 0 failed
git diff --check: PASS
Python compile / inline HTML scripts / JS parse / bundle + manifest: PASS
release ledger: 12 passed
```

PDF compatibility spike did not find a parity-safe renderer plus distributable
CJK font/dependency contract for both SaaS and Edition archives. The UI therefore
uses the explicitly named `打印 / 存为 PDF` fallback and exposes no `/pdf`
download endpoint.

## 浏览器证据（本地 owner session）

- Billing detail and top-up/refund shell: `375`, `768`, `1024`, `1440`; every
  measurement had `documentElement.scrollWidth == clientWidth`.
- Public portal, showcase and timetable: `320`, `375`, `390`, `768`, `1024`,
  `1440`; every route had no horizontal overflow. Earlier A coverage also
  checked English/Chinese and the menu keyboard path.
- Real flow on the synthetic local `lets-paint-showcase` tenant:
  1. top-up Ana Bianchi for 1 credit / gross `$110`, payer explicitly selected,
     invoice and payment enabled → `INV-0006`;
  2. refund the selected `INV-0006` source for 1 credit / `$110`, sync checkbox
     enabled by complete bridge and role → `CN-0002` and a refund;
  3. invoice detail showed `已贷记 −$110`, `余额 $0`, linked credit note,
     payment `refunded`, and `充值已结算` / `已贷记` events; the credit balance
     returned to its pre-top-up value.
- CSV summary and line buttons were exercised in the browser; the endpoint is
  tenant/permission gated, UTF-8 BOM, formula-safe, and the summary exposes the
  credited cents used by the invoice detail.
- Temporary browser fixture data is local-only; no production tenant or
  production database was touched.

## STOP GATE

Stop here. Do not commit, package, push, sync main, deploy production, or call
the public/prod browser acceptance chain until Lee explicitly authorizes the
v10.7.0 release and names the production host.
