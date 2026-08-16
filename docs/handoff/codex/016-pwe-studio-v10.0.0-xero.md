# PWE Studio v10.0.0 — 钱这一层：发票、收款、Xero、老师课酬、家庭日历、成长报告

> 主版本号跳到 10 的原因：这是产品第一次能回答「这个家庭欠多少钱」和
> 「这位老师这个月该拿多少」。在此之前，系统把「掏钱之后」做得很扎实
> （学员、作品、同意链、门户），而**掏钱本身整条链是空的**。
>
> 40 张新表、9 个新服务模块、34 条新路由、38 项新测试。
> 全量测试 2551 通过 / 6 跳过。全部迁移与不变量已在真 PostgreSQL 上验证。

## 0 · 先读这一条：修掉了两个既有的静默故障

这两个都不是本轮引入的，是被新写的守卫**顺带抓出来的存量问题**。

### 独立版导入工具此前跑不起来

`import_tenant_bundle.py` 用严格相等校验 `IMPORT_ORDER` 与
`tenant_archive.SNAPSHOT_TABLES`，而清单里的 `cms_notifications.json` 与
`cms_notification_reads.json` **从来没有加进导入顺序**。任何一次交付导入都会在
读第一行数据之前 `SystemExit`。已修，并加了 `test_standalone_import_order_matches_the_archive_manifest`
让它在 CI 里暴露，而不是在客户切换日的服务器上。

### 归档会静默丢掉三张表

`class_bookings`、`class_schedule_exceptions`、`tenant_slug_aliases` 带
`tenant_id` 却不在归档清单里。其中 **`class_bookings` 存着家长姓名、电话和
`privacy_notice_version`** —— 归档一个租户，个人数据和同意证据一起消失。

原来的守卫抓不到，因为它拿一份硬编码集合去比对另一份硬编码元组：
**只挡删除，不挡遗漏**。现在 `required` 从 SQL 文件派生（所有带 `tenant_id`
的表），必须出现在清单或写明理由的 `SNAPSHOT_EXCLUSIONS` 里。
新增迁移时忘了加表 = 构建失败。

改完立刻兑现：它一次抓出本轮全部 40 张新表。

## 1 · 边界（合同与产品定义都按这个写）

| 做 | 不做 |
|---|---|
| 算出每位老师该拿多少、依据哪几节课 | PAYG 代扣、养老金、STP 申报 |
| 出可签收的应付清单、同步 Xero | 跑批审批、RCTI、银行付款文件 |
| 记录收款、核销到发票、退款 | 经手资金、接触卡数据、Stripe Connect |
| 单向推送 Xero + 付款状态回读 | 双向编辑同步 |

**雇员老师的工资不能作为应付账单推进 Xero** —— 会绕开薪资科目造成错账。
`xero.payable_export_kind()` 在用工性质未记录时**拒绝而不是猜**。

## 2 · Xero 是三个开关，不是一个

| | 开关 1 · 权利 | 开关 2 · 连接 | 开关 3 · 推送 |
|---|---|---|---|
| 谁能动 | 平台 Super Admin | 租户 owner | 租户 owner/manager |
| 存哪 | `tenant_addons` | `xero_connections` | `xero_sync_settings` |
| 独立版 | 不存在（恒开） | 有 | 有 |

分开的理由是三个真实场景会互相误伤：加购到期只关 1（连接、映射、错误队列、
导出全留）；换会计动 2；年末封账动 3。

**开关 3 是一道闸，不是勾选框。** 前置条件写成了 CHECK 约束
`xero_push_requires_preconditions`：映射已确认 + 测试组织跑通 + 单一入口问题
已回答（选清算账户还必须填账户号）。服务能被脚本绕过，约束不能。

那个「单一入口」问题问的是：租户的 Square 是否已经在往同一个 Xero 组织同步？
两条通道写同一笔钱 = 生产账套里两套记录。这是 Sinobeats 那一单发现的坑，
现在产品在开关那一刻就问。

## 3 · 数据库不变量（都在真库验证过）

| 不变量 | 怎么保证 | 验证 |
|---|---|---|
| 已开具发票不可改 | 触发器 `trg_invoices_immutable` + 行项触发器 | 改金额/改行项都被拒 |
| 编号不跳号 | 计数器行 `UPDATE...RETURNING`，不用 sequence | 回滚后 INV-0003 被重用 |
| 核销不超额 | 触发器 `assert_allocation_within_payment` | 5000 分的款核销 9999 被拒 |
| 已付金额永不手写 | 触发器从核销重算并推导状态 | 半付→part_paid，付清→paid，balance 归零 |
| 幂等 | `UNIQUE (tenant_id, idempotency_key)` | 同键重放返回同一行 |
| 跨租户不可表达 | 复合外键 `(tenant_id, id)` | 挂别家学生被外键拒 |
| 已确认课酬冻结 | 触发器 + 服务层明确报错 | 见下 |

**金额一律整数分。** 税额用 `Decimal` + `ROUND_HALF_UP`，不用 `round()`
—— 后者是银行家舍入，`round(0.5) == 0`，0.05 元 10% 的税会算成 0。

**「逾期」是推导的，不存储。** 存状态就需要夜间任务维护，而且两次运行之间是错的。

## 4 · 本轮修掉的一个自己写出来的 bug

`teaching_pay.upsert_session` 里 `DO UPDATE ... WHERE locked_at IS NULL`
在课时已锁定时**静默跳过写入**并返回 `None`。数据是安全的，但调用方不知道
自己的修改没生效 —— 确认后重跑采集器会悄悄丢弃更正。已改为明确抛
`PayError`，提示改用调整项。测试 `test_a_confirmed_pay_period_refuses_silent_corrections` 守住。

## 5 · 套餐（价格未动）

money chain 全档可用。分层改为按规模与团队：Starter 是一个人的完整生意；
Studio 有团队所以要课酬与短信；Growth 有人看数所以要报表。Xero 是任意档加购。

> **红线**：套餐可以关功能入口，永远不得阻断或删除财务写入。
> 降级后已开发票仍可查、可导出、可打印。发票是法律文件，不是配额资源。

`plans.features` 此前**只用于套餐变更预览，从不执行门禁**。现在有了
`entitlements.resolve()`（plan ∪ addon ∪ standalone 全开）和路由级
`_require_feature`。

## 6 · 短信：先把量降下来

按 250 学员估算，全量提醒约 1,400 条/月（$500–840/年），只发必达消息约
330 条/月（$120–200/年）。所以 `DEFAULT_ROUTES["lesson_reminder"] = ()`
—— 课前提醒交给**家庭日历订阅**（一次订阅永久免费）。

**但日历替代不了当天的临时取消**：客户端按自己的节奏拉取，Google 可能隔数
小时。所以 `lesson_cancelled` 默认走短信。这条写进了 docstring 和测试，
不能靠上线后的支持对话来解释。

中文短信按 UCS-2 70 字一段计费，`segments_for()` 已处理 —— 按 160 字算会把
双语工作室的账单低估一半。

## 7 · 已上线（2026-08-14）

`pwestudio.online` 跑的是 v10.0.0。七个迁移在生产库上逐条 `applied`，
从 `0032_tenant_addons` 到 `0038_channels_calendar_and_progress_reports`。
深度健康 `appVersion=10.0.0 db=ok mode=saas tenants=6 themes.unreadable=0
workspaces.stale=0`，磁盘余 44.3 GB。预部署备份
`studiosaas_studiosaas_20260814T031503Z.dump`。

**验证方式值得记一下**：五条鉴权路由返回 `401` 而非 `404`，说明路由在线；
公开日历订阅对无效令牌返回 `404` 而非 `500`，说明
`calendar_subscriptions` 表**存在且可查**——这一条才是迁移真落地的证据，
版本号本身只能证明代码换了。下次验 schema 变更用同样的办法：
找一条会真正查新表的无鉴权路由，看它是 404 还是 500。

## 8 · 遗留与下一步

- **Stripe / Square 适配器只有骨架**：`payment_providers` 表、幂等回执处理、
  签名校验（`verify_stripe_signature`，用 `compare_digest`）都在，
  真正的 provider 调用未接。手工登记收款完全可用。
- **SMS 适配器同理**：路由、配额、成本看板、退订都在，provider 调用未接，
  且**故意抛错而不是假装发送** —— 用户以为发出去了其实没发，比明显失败更糟。
- `docs/design/Money_Layer_Plan_2026-08-14.md` 是这批的完整方案与待拍板项，
  界面方案与渲染图在 `docs/design/mockups/money-layer-ui.html`。

## 8 · v10.1 界面（在 v10.0.0 之后、尚未部署）

CMS 界面已经做了四处，全部在浏览器里对真实租户验证过，不是编译通过就算：

| 位置 | 内容 | 状态 |
|---|---|---|
| 经营 → **账单** | 账单账户、发票主从、开具、登记收款、批量发出 | ✅ 端到端验证（INV-0001 $660 → 已付清） |
| 经营 → **财务** | 老师课酬四个数、按档拦住的三张报表 | ✅ 端到端验证 |
| 设置 → **集成** | Xero 三步向导，闸门列出还差什么 | ✅ 验证 |
| 待处理 → **成长报告** | 逾期未写清单 + 跳学员档案 | ✅ 验证 |
| 学员档案 → **记录** | 成长报告撰写、发布、冻结 | ✅ 端到端验证（草稿 → 评语 → 已发布） |
| 学员档案 → **概览** | 账单账户归属 + 未结金额，点进筛过的账单 | ✅ 验证 |

**这一步抓到一个 v10.0.0 已上线的 500**：`progress_reports.assemble()` 把
psycopg 的 `date` 直接塞进 `json.dumps`，任何有课堂笔记的工作室点「整理这一段」
必崩。日期改成在 SQL 里 `to_char` 转字符串，测试进了 `test_money_layer.py`
的集成一半（要真 Postgres 才看得见 —— 空租户序列化得好好的，这个坑只埋在
用得最多的租户里）。

**新增两条面板守卫**（`tests/test_cms_panels.py`），两条都是先抓到真错才写的：
- 面板只能渲染自己作用域里够得着的组件。`--bundle` 之后 `cms-app.jsx` 的
  `Icon` 在面板里是未定义标识符，而 JSX 里一个 undefined 组件不是少个图标，
  是整棵 React 树抛错白屏。esbuild 不解析组件名，其他测试 grep 的字符串又
  全都还在。
- 面板传给 `v1Api` 的 body 必须 `JSON.stringify`。`v1Api` 把 options 直接
  透传给 fetch，对象会被转成字面量 `"[object Object]"`，服务端回 400
  「Request body must be a JSON object」—— 看起来像 schema 问题，其实不是。

**拆分已经开了口子**：`build_cms.sh` 加了 `--bundle`，新面板写在
`legacy-root/src/panels/`，主文件只加 import 和一个分支。拆之前先做了
一件更要紧的事 —— 让 16 个按文件名读 CMS 源的测试与脚本改为读整个目录，
否则新面板会带着「全绿但零覆盖」上线（守卫第一次跑就抓到我两个错）。

| 课程安排 → **一对一循环课** | 循环课、请假归因、补课额度、请假规则 | ✅ 端到端验证 |

界面这四处到此做完，第 5 步收尾。

## 9 · 一对一循环课（`services/scheduling.py` + 10 条路由）

0033 落的三张表终于有了决定逻辑与界面。整层只有一个真正的判断：

    一节课没上，谁还付钱、谁还拿钱、家长欠不欠一次补课。

这是三个答案不是一个。`resolve_absence()` 刻意做成对 policy 字典的纯函数 ——
它错了不抛异常，只是悄悄向家长收一笔工作室自己停课的钱，所以它必须能在没有
数据库的情况下被穷举测试。10 条静态用例覆盖了归因、边界（正好 24 小时算按时）、
未记录提前量（当作没提前，否则每条漏记的请假都变成退款）、以及「收费」与
「算课酬」必须分别作答。

界面把服务端算出的三个答案原样念回操作的人，不合成一句「已取消」—— 合成了
就等于把 `lesson_exceptions` 存在的理由丢掉。浏览器里验过：学员提前请假 =
不计费/不算课酬/发额度；工作室停课 = 不计费/**照付课酬**/不发额度；撤销把
额度改成 `cancelled` 而不是删除。

**做的过程中修了一个自己写的真 bug**：`occurrences()` 先按 `status='active'`
过滤，导致 `paused_from`/`paused_to` 那个窗口永远走不到 —— 「暂停八月下旬」
在实现上等于「永久停课」。集成测试现在断言暂停期外的周次必须还在。

**部署提醒**：v10.1 含迁移 `0039_plan_features_for_the_money_layer.sql`。
没有它，`teacher_payables` 与 `management_reports` 对每个租户永远是「没有」——
权利解析器是对的，套餐表从来不知道这两个键存在。这是打开界面才发现的，
测试全绿，因为测试要么跑 standalone 全开、要么自己直接授权。

---

