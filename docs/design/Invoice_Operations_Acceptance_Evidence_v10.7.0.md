# v10.7.0 发票运营验收与发布证据

> 日期：2026-08-16（Australia/Melbourne）
>
> 这是 `Invoice_Operations_Execution_Checklist_v10.6.4_Luna_Max.md` 的 F-01
> 证据包及其发布闭环记录，包含本地门禁、归档校验、生产部署与公网验收。

## 发布边界

- `VERSION` / `APP_VERSION`：`10.7.0`。
- `main == origin/main`：`913c6f168052213535fbeae9da0197de9e655959`。
- SaaS SHA-256：`5c31847b3583889ac5613f4d73915f08ef65282632a07cd7acccaaba07441b22`。
- Edition SHA-256：`1bc04e0c0bab5960d05936a096ed26607651827363b1dc2c0341c195e11d9a3e`。
- 生产：`pwestudio.online` 深健康 `appVersion=10.7.0`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`。
- 发布前备份：`studiosaas_studiosaas_20260816T093518Z.dump` 与
  `pwestudio-volumes-20260816T093519Z.tar.gz`。
- Xero 仍为 Preview；本轮没有 OAuth、provider transport、worker 或 webhook。

## 阶段结果

| 阶段 | 结果 | 关键证据 |
|---|---|---|
| A | PASS | public portal/showcase/timetable/index 320/375/390/768/1024/1440 无横向溢出；旧课时充值伪联动已清除。 |
| B/C | PASS | migration 0043 已应用且幂等；payer 0/1/N、自定义 person/organisation、snapshots、InvoiceDocument、CSV、PDF spike/fallback 通过。 |
| D | PASS | `credit-settlements` 四组合、gross 税额整数分、原子 rollback、request-id replay 通过。 |
| E | PASS | explicit-source full/partial/multiple/overage/no-bridge/cross-tenant/idempotency 与角色边界通过。 |
| F | PASS | 完整门禁与真实浏览器流程通过；发布闭环已完成。 |

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

## 生产验收

- Controller：SaaS `BUILD_INFO`、备份、migration、workspace regeneration、内部/公网深健康与主题可读性全部通过。
- 公网路由：`/`、`/zh/manual/`、tenant portal、timetable、CMS、Release Notes 均返回 `200`。
- CMS：`/assets/cms-app.js?v=10.7.0&h=7973c49a0d53ca40` 返回 immutable 缓存；响应 SHA-256 与 committed asset manifest 一致。
- Media：代表性 `?variant=medium` 返回 JPEG、checksum ETag；带 `If-None-Match` 返回 `304`。
- 浏览器：生产 portal/timetable/CMS 发票页在 375/768/1024/1440 宽度无横向溢出；移动 CMS 与发票列表真实渲染通过；菜单 Escape 后焦点回到按钮。

## 发布闭环

Lee 已明确授权 commit、package、push、sync main、production deploy 与
browser acceptance；以上证据均已记录。后续若变更同一发布标签，应创建新的
版本号，不重写 `913c6f1` 或复用已发布的 v10.7.0 归档。
