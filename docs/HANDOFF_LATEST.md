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

# PWE Studio v9.9.6 — 手册对齐 v9.9.5 产品事实、全套截图重拍、路演 deck 同步

> 当前阶段：文档与素材发布。**运行代码未改**（仅 `VERSION` / `APP_VERSION` 标签）。
> 本轮修掉手册里一处已经不成立的断言、补上一个从未被拍过的公开页面、
> 把 20 组截图全部按 v9.9.5 重拍，并同步销售路演 deck。

## 关于「为什么要推版本号」——发布提交里那句话是错的

提交信息里写着「同版本号重拍等于没拍，读者拿到的还是旧图」。**这不是这套缓存的工作方式。**
`_stamp_asset_versions` 同时写 `?v=` 和 `?h=<内容摘要>`，
`_cache_versioned_asset` 只在**两者都匹配**时才发 `immutable` ——
所以字节变了，`h` 就变了，URL 就变了，跟版本号无关。

推版本号是**发布账本**的要求（`test_release_ledger.py`），这个理由本身就够；
但它不是把新图送到读者手里的必要条件。已在线上核实：
`/assets/manual/02-showcase-page.zh.webp?v=9.9.6&h=d18162fbec7e0197`
返回 `public, max-age=31536000, immutable`；去掉 `h` 则返回 `no-cache`。

**教训和上一轮同一个形状**：写进文档的机制说明，也要像断言一样只写真的。

## 一处主动说错的话

第 00 章写着 slug「开通时确定、之后不可更改」。v9.9.0（`86dc30c`）已经允许更换：
`PATCH /v1/admin/tenants/<id>/slug`，`@super_admin_required`，365 天冷却，
旧地址进 `tenant_slug_aliases` 永久 301，且**任何地址都不会被重新分配**
（已删除租户留墓碑答 410）。已改写为真话，并在第 11 章「平台方」和常见问题里
各补一条 —— 这是客户签约前会问的问题，之前手册给的是「不行」。

## 截图：20 组全部重拍（v9.5.0 / v9.6.1 / v9.8.5 三个基线混在一起）

重拍前的实际状态：CMS 系列停在 v9.5.0、Studio Admin 系列停在 v9.6.1、
作品系列停在 v9.8.5。而 Studio Admin 在这之后改了 1165 行、公开外壳被重写。
最直观的一处：工作台左栏当时是 10 个面板，现在是 12 个，手册的标注也写着「十个」。

- 本地 `lets-paint-showcase` 用 `reset_professional_demo.py` 重新播种到 v9.9.2+ 形态
  （15 件工作室作品 / 8 件学员作品 / 6 张空间照片），再跑 `capture_manual_shots.py`。
- **新增 `02-showcase-page`**：作品页从 v9.8.10 起就有独立网址 `/<slug>/showcase`，
  手册此前只有文字没有图。首页是 6 件的引子，独立页每次 12 件。
- **删掉了 `TIMETABLE_PUBLIC_SEED`**：公开课表的截图原本走一份手写 fixture 桩，
  因为 v9.9.2 之前演示租户没有课表数据。现在播种器自己拥有这一半，
  fixture 成了第二事实来源 —— 而且已经漂移：在 v9.9.5 它一个约课按钮都渲染不出来，
  直接让这张截图失败。现在和其他所有截图一样，拍真实页面。
- 截图集 2.50 MB（预算 3 MB），`build_asset_manifest.py` 已重建。

## 路演 deck（`docs/sales/PWE_Studio_Roadshow_Bilingual.pptx`）

13 张产品截图里有 12 张是手册截图的旧副本（按图像签名逐张比对确认），已全部换成新的。
另外两处：

- 第 3 页「Showcase / 作品归档 · Archive + filters」原本放的是首页作品条，
  现在放真正的独立归档页 —— 标题说的就是它。
- 第 5 页那张待审核截图是 **v9.5.0 之前**的深色侧边栏 CMS，早已不存在；
  换成现在的「新报名 / 约课」双标签队列。
- 版本标签 v9.8.8 → v9.9.6（第 1、8 页），第 4 页补一条「你的公开网址，换了也不会丢」。
- 套餐页（第 9 页）逐项对过 `plans` 表：$49/$99/$199、100/500/1000 学员、
  15/60/150 作品、2/10/50 GB、Studio 推荐 —— 全部正确，未改。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | 发布提交 `e92dcadf89ab62b87681f14c5afa550b56c93abf`，分支 `claude/online-manual-content-improvement-03b8f9`；`VERSION=9.9.6`。门禁全绿：`verify_local.sh` 全部通过、pytest `1755 passed, 12 skipped`、legacy CMS smoke `73 passed`、租户隔离 `237 passed, 0 failed`。 |
| Package | SaaS `PWE-StudioSaaS-aws-9.9.6.tar.gz` SHA-256 `ce2672d4a739583e00bc92d20b903bdb12e62fd1f8c0000539934e35c2388ce8`；Edition `PWE-Studio-Edition-9.9.6.tar.gz` SHA-256 `c766d654a30ac1a3c30af90de3a3c6c4c31723cf6464799b3682e1be28269665`。两个包的 `BUILD_INFO` 均为 9.9.6，模式 `saas` / `standalone`，均通过发布包校验。 |
| Backup | 部署前逻辑库备份 `studiosaas_studiosaas_20260813T101614Z.dump`，manifest 同时存在。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.6`，镜像 `studiosaas:9.9.6`，容器 healthy；内网与公网 deep health 均为 `appVersion=9.9.6`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`；磁盘可用约 `44.74 GB`。 |
| Public routes | 根站、中英文手册、pricing、Release Notes、租户门户 / timetable / showcase / register / CMS / Studio Admin、platform-admin 共 12 条全部 `200`（HTTP/2）。 |
| Assets | 四组代表性手册截图的线上字节与本地 SHA-256 逐一相同（`01-brand-workbench`、`02-showcase-page`、`04-booking`、`07-settings`）；带 `h` 的 URL 返回 immutable，条件请求返回 `304`。 |
| Content | 线上手册中英文都已是改正后的那句（「它并非永远不能改」/「It is not permanent」）；`FAQPage` 结构化数据 13 条问答，含新增的网址更换那条；`dateModified=2026-08-13`。 |

## 待办

- 第 03 章仍缺：指定老师 · 地点 · **停课**（停课在公开课表上是「划掉」不是「消失」）。
- 空间介绍 About（v8.5.4）在第 01 章仍未提。
- `canReviewBookings` 含 `staff`，而 `ROLE_PERMISSIONS[Role.STAFF]` 没有
  `class_bookings:review` —— Staff 看得见「批准 / 婉拒」，按下去 server 拒绝。
  与本轮无关，手册没有写这个 bug。

---

# PWE Studio v9.9.5 — 那排 tab 从来没有被接上过

> 当前阶段：**已部署上线**。生产 `appVersion=9.9.5`。
> 审计与方案见 `docs/design/Platform_Admin_Audit_2026-08-13.md`。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `8cfc54a`；`VERSION=9.9.5`。 |
| Local gates | `verify_local.sh` **All checks passed**；pytest `1812 passed, 5 skipped`。 |
| Package | `PWE-StudioSaaS-aws-9.9.5.tar.gz`，SHA-256 `edf1152cfc99a8600c7f28e32488350bbed450eaf93ec741df422a8e1c3126d1`；部署前备份 `…20260813T080947Z.dump`。 |
| Production | deep health `appVersion=9.9.5`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`。 |
| 线上控制台 | 七项抽查全过：渲染 tablist、`wireEditorTabs` 存在、**editTenant 确实接线**、旧的失效 nav 已消失、错误计数、保存跳转、编辑器里没有手风琴。 |
| 线上词典 | 新词条已生效（基础资料 / 负责人与联系方式 / 随套餐继承 / 重置演示数据 / 放弃未保存的修改？ …）。 |

## 一 · 根因：接线接在了错的编辑器上

不是 CSS 挡住，不是事件冒泡，是**监听器从来没被绑上**：

| 行号 | 事实 |
|---|---|
| `editTenant()` 内 | 渲染出 `<nav class="editor-section-nav">` 和五个按钮 |
| `editTenant()` 内 | 调用 `openWorkspaceEditor()` 挂进 DOM |
| **整个 `editTenant()`** | **没有一次 `wireEditorSectionNav()`** |
| `addPlan()` 内 | 唯一的调用点——而套餐编辑器根本没有这条 tab 条 |

手风琴还能用，是因为 `<details>` 是浏览器原生的、不需要 JS。
**这正是它一整个版本没被发现的原因**：表单照常可用，tab 只是失效的装饰。

而且旧测试 `assert "function wireEditorSectionNav" in html` 只问「这个函数存在吗」，
所以那段时间它一直是绿的。现在改成问「editTenant 有没有接上它渲染的 tablist」。

## 二 · 按方案 B 重做：真 tab

复用**文件里已有的** tab 组件（租户详情面板在用），不新造第三套导航：
`role="tablist"` / `role="tab"` / `aria-controls` / `aria-selected`、
roving tabindex、←→/Home/End 切换。

分页会藏起内容，所以配套做了三件事——这是方案 B 的前提，不是附加功能：

1. **每个 tab 上有错误计数**。数的是该面板内的 `[aria-invalid="true"]`
   加上可见的 `[role="alert"]`。
2. **每个 tab 上有改动圆点**。原本 `markEditedSections()` 已经在按段追踪，
   现在把结果显示到 tab 上。
3. **保存失败自动跳到出问题的那个 tab**。
   「检查订阅日期」这句话在订阅页被藏起来时是一条死路。

### 线上真实 DOM 验证（不是只看代码）

用 fixture 直接驱动 `editTenant()`，在真实页面里断言：

| 动作 | 结果 |
|---|---|
| 打开 | 5 个 tab、5 个面板，只有 `basic` 可见，tabindex `[0,-1,-1,-1,-1]` |
| 点「订阅与套餐」 | 选中并只显示该面板 |
| ← → / Home | 正确移动，**任何时刻只有一个面板可见** |
| 在隐藏的「负责人」页改字段 | 该 tab 出现改动圆点，**当前页不动** |
| 制造非法日期 | 「订阅」tab 出现 `error:1`，当前仍在 `basic` |
| 点保存 | **自动跳到 `subscription`** 并显示该面板 |

## 三 · i18n 门禁有个盲区，而且新代码一直在往里加

门禁**确实覆盖** `super-admin.html` 且是绿的，但它把 `<script>` 当作不透明——
而这个控制台的编辑器几乎全由模板字符串拼出（`editTenant()` 一个函数 148 行模板）。

量出来：script 里可见界面文案 98 条，**11 条不在词典里**，
其中四条是上一版我自己加的重置对话框。

修法：给提取器写了一个**处理嵌套的扫描器**（正则会把
`${/*safe*/editorPanelLead('Basic', )}` 当成英文文案报出来），
把模板字符串里的 HTML 片段喂进同一个提取器。

打开之后暴露 33 条，处理如下：

- **不该翻译的**用语义标记排除：示例值（`Northside Art Studio`、`mellow-pear-studio`、
  `e.g. studio-pro`）加 `data-i18n-lock`；要照着敲的短语放进 `<code>`；URL 路径由提取器跳过。
- **真正缺的 35 条**补进 `admin-i18n.js`。

## 四 · 拼接的句子翻译不了

词典按**整句**查表，`Inherited from ${plan} plan.` 永远查不到。
拆成 `<span>Inherited from plan</span> · {套餐名}` —— 词是词，专名是专名。

确认短语同理：`Type RESET-... to confirm` 被拆成「Type」+ 字面量 +「to confirm」三段，
改成标签「输入确认短语」+ 独立一行 `<code>`。

`window.confirm('Discard unsaved changes?')` **不用改代码**——
`admin-i18n.js` 早就包装了 `window.confirm`，缺的只是词条，已补。

## 五 · 状态

- 本地全量 **1812 passed, 5 skipped**；`verify_local.sh` 全绿。
- 新增 `backend/tests/test_platform_admin_editor.py`（9 条）。
- 两条旧测试按新结构更新，都写清了为什么改。
- 尚未打包部署。

---

# PWE Studio v9.9.4 — 三处修正：会变的表头、炸掉的按钮、借来的房子

> 当前阶段：**已部署上线并重种**。生产 `appVersion=9.9.4`。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `9.9.4` 提交；`verify_local.sh` **All checks passed**；`1801 passed, 5 skipped`。 |
| Production | deep health `appVersion=9.9.4`、`db=ok`、`tenants=6`、`workspaces.stale=0`；部署前备份 `…20260813T061647Z.dump`。 |
| **重置按钮（线上实测）** | 真实租户 `lets-paint-studio` → **400 拒绝**；错误短语 → **400**；正确 → **200，7.2 秒**，15 件主理人作品 / 8 件学员作品（7 件公开）/ 12 名学员 / 6 张空间照。 |
| 文案 | 线上已是「一间朝南的后院画室 / A garden studio facing south」、三条亮点新文案、Caulfield North。 |

## 一 · 「有时对有时不对」是语言差

同一个页面，有时正常、有时店名旁边一排被截断的标签。真因不是随机：

| 语言 | 导航需要 | 隐藏店名后可用 | 结果 |
|---|---|---|---|
| 中文 | 726px | 878px | 只隐藏店名，导航全显示 |
| 英文 | 926px | 878px | 收进菜单 |

**两种语言的正确答案本来就不同**，而语言是首屏之后由客户端切换的。
v9.9.3 只测量一次，哪次先跑就定死哪个——这就是那个「有时」。

除了语言，还有两件事会在首屏之后改变答案：网页字体到达（每个标签宽度都变）、
契约把占位标签换成店主自己的文字。所以现在改为**有界结算**：
`fonts.ready`、`load`，外加 120 / 400 / 1200ms 三次补测。

**故意不用 ResizeObserver**：这个函数会改变它自己测量的布局，
观察自己的输出在慢机器上就是个循环。固定、有界、可预测的时间表更安全。

实测：1440px 下六次采样全部一致，零溢出零截断；
中文全导航 + 隐藏店名，英文折叠 —— 和你两张截图各自的正确形态都对上了。

## 二 · 重置按钮 500

生产日志里的堆栈很直接：

```
File "/app/backend/scripts/reset_professional_demo.py", line 939, in reset_showcase
    import server
AssertionError: The setup method 'register_error_handler' can no longer be
called on the blueprint 'studiosaas_api_v1'.
```

`reset_showcase()` 需要一个 Flask 应用上下文（`store_media_asset` 从
`current_app.config` 读媒体根目录），命令行下靠 `import server` 自己造一个。
但从接口调用时**进程里已经有应用了**，再 import 一次等于在活着的进程里
重新执行 server.py，把已挂载的蓝图又注册一遍。

改成先问 `has_app_context()`：有就复用，没有才造。
两条路径都实测过：接口 200（1.9 秒），命令行照常。

**这个 500 在本地复现不出来**——本地测试脚本自己就没有上下文，走的是命令行那条路。
只有从 Platform Admin 真的按一次才会炸。

## 三 · 房子是借来的

「1960 年代旧车间、五米层高、南墙一整排窗」是照 Brunswick 仓库区写的。
Caulfield North 是梧桐和砖房。改成：

> 画室在一栋 1920 年代砖房的后院，原本是马厩改的车库，屋顶掀高了，
> 南墙换成一整面玻璃。门口有两棵梧桐，风大的时候能听见。

主理人故事同步改（「邻居敲门问能不能一起」），三条亮点的语气也提了一档：
「八张画架，不多放」→「八张画架，不加第九张」；
「画完了可以放着」→「没干的画留下来……走的时候不必迁就一张还没想好的画」。
朝南没动——南半球画室要的就是南边那道恒定的冷光。

## 四 · 状态

- 本地全量 **1801 passed, 5 skipped**；`test_showcase_tenant.py` 增至 38 条。
- 尚未打包部署。上线后要重跑一次重置，文案才会生效（地址在数据库里，不在代码里）。

---

# PWE Studio v9.9.3 — 头部、锚点，和一个只对演示租户可见的按钮

> 当前阶段：**已部署上线并重种**。生产 `appVersion=9.9.3`。
> 四条都由真实截图或真实点击报出，全部量过再改。

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `256aa6c`；`VERSION=9.9.3`。 |
| Local gates | `verify_local.sh` **All checks passed**；pytest `1797 passed, 5 skipped`。 |
| Package | `PWE-StudioSaaS-aws-9.9.3.tar.gz`；部署前备份 `…20260813T054808Z.dump`。 |
| Production | deep health `appVersion=9.9.3`、`db=ok`、`tenants=6`、`themes.unreadable=0`、**`workspaces.stale=0`**。 |
| 演示密钥 | compose 透传**已生效**：容器内 `STUDIOSAAS_SHARED_DEMO_PASSWORD` 已就位（48 字符），`STUDIOSAAS_DEMO_CREDENTIALS_FILE=/data/showcase-credentials.txt`。再不需要 `docker exec -e`。 |
| 重种 | 线上已重跑：15 件主理人作品、8 件学员作品（7 件公开）、12 名学员、7 节公开课。地址已变为 **Caulfield North**，七个版块全部 `ready`。 |
| Public | 六条路由 200；timetable / register 的新 description 已生效。 |

**注意**：地址存在数据库里，不在代码里。改 `showcase_content.py` 只决定「下次重种写什么」——
线上要生效必须重跑重置。这一版是手动跑的；下次可以直接用 Platform Admin 的按钮。


## 一 · logo 压在导航上（真因不是响应式）

截图里「Let's Paint」紧接着一个「L..」——量出来是：`.brand` 盒子只有 124px，
里面的 logo 是 281px，**图片溢出自己的容器 157px** 压在第一个导航项上，
店名被压成 0 宽所以只剩一个字母加省略号。

再往下量才是真因：`.navrow` 的 `max-width` 是 **1180px**，不管屏幕多宽都封顶。
品牌区 419 + 导航 926 = 1345 > 1138 可用 —— **它永远放不下**，跟视口无关。
之前当响应式问题查是走错了方向。

改成**测量驱动的降级阶梯**（`public-surface.js` 里一份实现，四个页面共用）：

1. 先扔掉重复的店名 —— logo 本身就写着 "Let's Paint"，`<img alt>` 仍带着它；
2. 还放不下，导航整体收进菜单键。

断点只作为**地板**（900px），不再当作判据：导航有几项是**每个租户不同的事实**，
按最满的租户定死断点，等于让只开三个版块的租户在笔记本上也顶个汉堡。
实测：满配租户（9 项）折叠；隐藏 3 个版块的普通租户**店名和完整导航都保留**。
菜单面板里语言切换仍在，折叠不丢功能。

## 二 · 跨页 `#` 锚点点了没反应

`/lets-paint-showcase#home:artist` 从别的页面点进来只回首页不定位，
点点别处又好了 —— 这个「第二次就好」正是线索。

`applyRoute` 在脚本执行时就跑，30ms 后 `scrollIntoView`；
那时契约还没返回，版块还是 `display:none`，而**对隐藏元素滚动是空操作**。
点别处触发 `hashchange` 时版块已经显示，所以第二次成功。

改成记住锚点、在**版块变可见的那一刻**重试（`resolveSection` 里），
带 8 秒上限，并且无锚点导航会清掉待定锚点——
晚到的版块不能把已经在读别处的人拽回去。

## 三 · 地址改为 Caulfield North

内容模块、文档、handoff 全量替换并重种。
一处留着没动：主理人故事里的「1960 年代旧车间、五米层高」原本是照 Brunswick
仓库区写的，Caulfield North 是林荫住宅带。车站附近有轻工业，说得通。

## 四 · Platform Admin 的一键重置

`POST /v1/admin/tenants/<id>/demo-reset`，`@super_admin_required`，四道守卫：
SaaS 模式 → 租户带 `professional_demo=true` → 确认短语 → 密钥已配置。
短语和命令行脚本**是同一个**，只要记一次。

**放在哪**：租户操作菜单里单独一组「Demonstration」，
而且**只在服务端标记为演示租户时才渲染**——不是灰掉，是根本不出现。
一个操作员如果能在真实画室的菜单里看见「Reset demonstration data」，
就离误点只差一次手滑，而确认框拦不住习惯。

实测四条路径：错短语 400、非演示租户 400、不存在 404、正确 200（1.9 秒重建）。
接口返回凭据文件的**路径**，从不返回内容。

## 五 · 顺手补的两个小洞

- `timetable` 和 `register` **完全没有 meta description** —— 转发到聊天软件里
  只有一条光秃秃的网址。补上了。
- `public-surface.js` 现在在无浏览器环境里也能安全加载（契约测试用 node 跑它，
  `apply()` 调用 `requestAnimationFrame` 一度打挂了九条测试）。

## 六 · 查过但不是 bug 的

灯箱 Escape 关不掉——**是自动化的锅**。对照实验：一个全新的、没有任何应用代码的
原生 `<dialog>`，在同样的合成按键下也不关闭、`cancel` 也不触发。
合成按键不算「用户激活」，走不到 CloseWatcher。灯箱的 `cancel` 接线是对的。

## 七 · 状态

- 本地全量 **1791 passed, 5 skipped**；`test_showcase_tenant.py` 增至 34 条。
- 术语、转义、内联脚本、版本账本全绿。
- **模板改了 → 所有租户工作区必须重新生成**，否则 deep health 的 `workspaces.stale` 会报。
- 上一版（v9.9.2）已上线；这一版尚未打包。

---

# PWE Studio v9.9.2 — 定价页，和一间真的画室

> 当前阶段：**已部署上线，演示租户已重种完毕**。生产 `appVersion=9.9.2`。

这一版有两件事：上一轮做完但没发的**定价页**，以及把 `lets-paint-showcase`
从测试租户改造成**真样板 + 演示租户**。改造过程中挖出四个产品缺陷，都在下面。

## 一 · 定价页（上一轮遗留）

`/pricing` 与 `/zh/pricing`，一 URL 一语言、hreflang 互指、尾斜杠 301。
计算器读服务端已渲进页面的 `data-plans`，**不发第二次请求**——
两个数据源就是同一个套餐出现两个价格的原因。
推荐同时看学员数和登录名额，并说出**是哪条约束决定的**（「Starter 只有 1 个登录名额」）。
掏钱前 FAQ 八条，其中两条不许含糊：降级只影响**发布**、绝不删数据；没有任何抽成。

顺带把页头做成了真共享：445 行样式抽成 `marketing.css`，
导航/移动菜单/吸顶/reveal/页脚年份抽成 `marketing-shell.js`。
原来的 `product-home.js` 在找不到咨询表单时会直接抛错——
对有表单的那一页是对的，对任何复用这个页头的页面都是错的。

## 二 · Let's Paint 样板租户

方案与全部决策记在 `docs/design/Showcase_Tenant_Build.md`。

**改造前**：三件作品标题是 `Test`、`fasd` 和两个空字符串，没有分类、没有主理人、
没有「空间与体验」，logo 在暖纸背景上看不见。
原因很具体——seeder 只种 CMS 侧（课程、学员、签到），
**门户侧留给最后一个在控制台里打字的人**。

**改造后**（`backend/scripts/reset_professional_demo.py` 现在两侧都管）：

| | |
|---|---|
| 身份 | 墨尔本 Caulfield North，成人小班，主理人 **Janet M**，第 7 年 |
| 文案 | 全部双语，写在 `backend/scripts/showcase_content.py`——文案是数据，不是散在 seeder 里的字面量 |
| 主理人作品 | 15 件（13 active / 1 draft / 1 archived），三个抽屉，`featured_rank` 1–6 |
| 学员作品 | 8 件署名到 8 位学员，**其中 1 件同意已撤回**，公开 7 件 |
| 空间 | 6 张照片 + alt，手动切换不自动轮播 |
| 套餐 | **studio 档**（作品上限 60）。`lets-paint-studio` 是真实租户，全程未碰 |
| 图片 | 28 张生成图，75 MB PNG → **8.2 MB WebP**（部署包是 `git archive HEAD`，每次发布都要背着走） |

**「人像」这个抽屉不存在**，因为还没有人像作品。
分类由 manifest 里**实际已发布的作品**推导，不由那张分类表推导——
一个点下去空空如也的筛选按钮，比没有这个按钮更糟。

## 三 · 改造中挖出的四个产品缺陷（都已修，都带回归测试）

**1. 任何租户都不可能拥有一张透明 logo。**
公开品牌图片一律走 `display` 变体，而 `_build_safe_variants()` 只产 JPEG，
`_jpeg_bytes()` 把 RGBA 压到白底。传 PNG 也会被拍成白方块。
修法：源图带 alpha 时变体输出 PNG，`media_variants.mime_type` 跟随实际格式而不是写死。
**这修的是每一个租户。**

**2. 学员作品有两道同意门，seeder 只开了一道。**
公开画廊要求学员有一条最新为 `confirmed` 的 `student_publication_consent_events`，
**并且**作品是 `shared` 且带 `public_consent_at`。
只写后者 → 画廊永远空着、契约报 `no_consented_student_work`——
看起来像产品有 bug，其实是记录没建。

**3. 宽 logo 会把店名挤出手机屏幕。**
`.brand img{height:34px;width:auto}` 不设上限。8:1 的手写体 wordmark
在 375px 手机上占 281px，店名折成三行压在汉堡按钮下面。
两个方向都封顶 + `object-fit:contain`，店名允许省略号。

**4. 分类推导依赖列表顺序。**（我自己写的，改成两趟遍历。）

## 四 · 演示披露

四个公开页面页脚新增一行（双语，默认隐藏）：
「演示站点：画室、人物与作品均为虚构，数据每晚重置。」
由 `/brand` 的 `demoTenant` 驱动，读**租户记录**而不是 slug——
绑在名字上的标记，改名当天就不成立了。

这不是装饰。页面用虚构人物的名义、在公开地址上展示合成作品，
还写着「下面这些是 Janet 自己的画」。

## 五 · 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | `origin/main` = `34b6733`；`VERSION=9.9.2`；`RELEASE_DATE=2026-08-13`。 |
| Local gates | `verify_local.sh` **All checks passed**；pytest `1790 passed, 5 skipped`；legacy CMS smoke `73/73`；租户隔离 `237/237`；术语、转义、版本账本全绿。 |
| Package | `PWE-StudioSaaS-aws-9.9.2.tar.gz` 24 MB，SHA-256 `66a452e7ec55cf012b0c28a5a1b807892cc18559021e46071de4961f1eddb213`；`BUILD_INFO` commit `34b6733`。 |
| Backup | 部署前 `studiosaas_studiosaas_20260813T032433Z.dump`。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.2`，镜像 `studiosaas:9.9.2`；deep health `appVersion=9.9.2`、`db=ok`、`tenants=6`、`themes.unreadable=0`、**`workspaces.stale=0`**；磁盘 45.44 GB 空闲。回滚目录保留 9.9.1。 |
| Public | 七条路由全部 200（含 `/pricing`、`/zh/pricing`）；`/brand` 返回 `demoTenant=true`；四个页面都带 `demoNotice`；`index/showcase/timetable` 的 logo 上限已生效（`register` 本来就是 42×42 方框，不需要）。 |

## 六 · 状态

- 本地全量：**1790 passed, 5 skipped**（v9.9.1 时是 1754）。
- 新增 `backend/tests/test_showcase_tenant.py`（29 条）、
  `test_pricing_page.py`（10 条）、媒体透明度回归。
- **模板改了 → 所有租户工作区必须重新生成**（`regenerate_tenant_workspaces.py`），
  否则 deep health 的 `workspaces.stale` 会报。
- **尚未打包部署。** 发布前按 `docs/Release_Runbook.md` 的九步走，
  先跑 `backend/scripts/release_preflight.sh`。

## 七 · 已确认：标记是对的，但重置从来没跑过

上线时逐条查了：

- `settings.professional_demo` = **`true`** ✅ —— 脚本不会拒绝执行。
- `plan_code` = **`studio`** ✅。
- **没有 cron，没有 systemd timer** ❌ —— 每晚重置**从未运行过**。
- 容器里**没有** `STUDIOSAAS_SHARED_DEMO_PASSWORD`，
  `/opt/pwestudio/shared/production.env` 里也没有 ❌。

第四条解释了前面所有事：重置脚本要求这个密钥（≥12 字符）才肯跑，
而它在生产环境根本不存在——所以脚本**一次都没能执行**，
那三件 `Test` / `fasd` 只能是人手敲进去的。

## 八 · 演示密钥已配置，租户已重种（2026-08-13）

密钥**在服务器上生成**：`openssl rand -hex 24`（48 字符，十六进制——
env 文件没有引号语义，值里出现 `/` 或 `+` 迟早出事），
追加进 `/opt/pwestudio/shared/production.env`（0600，改前留了 `.bak-` 备份）。
值从未打印、从未作为命令行参数出现（`argv` 可以被 `ps` 读到），从未离开实例。

重种时密码走 **stdin** 进容器，不走 `docker exec -e`，理由同上。
凭据写在 `/data/showcase-credentials.txt`（0600）——`/data` 是 named volume，
下次发布不会把它带走。

**要看演示账号密码，在服务器上：**

```bash
sudo docker exec pwestudio-app-1 cat /data/showcase-credentials.txt
```

### 重种结果（线上实测）

| | |
|---|---|
| 数据库 | `works=15`、`students=12`、`public_classes=7`、`student_works=8` |
| 契约 | 七个版块**全部 `ready`**（`gallery` 从 `no_consented_student_work` 变成 `ready`） |
| 作品墙 | 公开 13 件，每页 12，`hasMore=true`；三个抽屉；精选 1–6 顺序正确 |
| 图片 | 画作 `image/jpeg` 524 KB；**logo `image/png`、RGBA、角落 alpha=0** |

最后一行是这个产品**第一次**真的服务出一张透明 logo。

### 为什么以前 env 文件里写了也没用

`docker-compose.yml` 的 `environment:` 是一张**白名单**——
不在里面的键，无论 `production.env` 写得多认真都到不了容器。
这一版把 `STUDIOSAAS_SHARED_DEMO_PASSWORD` 和
`STUDIOSAAS_DEMO_CREDENTIALS_FILE` 加了进去，
所以**下一次发布之后**定时器可以直接调脚本，不必再用 `docker exec -e`。

### 定时器还没装——先决定一件事

`lets-paint-showcase` 现在**既是给客户看的样板，又是演示租户**。
定时器一开，任何人在控制台里为了让样板更好看做的调整，当晚就会被抹掉；
样板的唯一持久编辑入口就变成 `showcase_content.py` 和 `manifest.json`。
接受这一点再装，别反过来。

## 九 · 已知缺口（未修，已记）

1. `courses.name / description / category` 是单语言字段，中英门户渲染同一个字符串。
   这一轮按 `油画基础 Foundation Oil` 双语并置写。
2. 公开课程卡片按 `ORDER BY category, name` 排——店主无法控制顺序，
   于是入门班可能排在最后。已开背景任务。

---

# PWE Studio v9.9.1 — v9.9.0 的两处修正

> 当前阶段：v9.9.1 已完成源码、完整门禁、双模式打包、生产备份、部署与公网验收。两处都由真实控制台的截图报出。

## 修复内容

**一 · 草稿向自己的记录问错了问题。**「工作室作品」开关显示「还没有已发布的作品」，
而工作室的官网正在展示两件作品，**并且上传区上方的计数写着 `2/60 件 active 作品`**——
同一个界面自相矛盾，这就是线索：计数读的是编辑器自己的记录，
草稿契约读的却是 `collectShowcaseItems()`，而那个函数在送往服务端的路上已经把字段映射成 camelCase。
于是过滤条件里的 `image_url` 和 `publication_state` 在每一条上都是 `undefined`，
`showcaseHasContent()` 对每一件作品都返回 false。公开页面自始至终是对的，因为它读的是服务端契约。

这个错答案从草稿契约引入时就存在；是 v9.9.0 把原因显示到开关旁边，才让它暴露出来。

**二 · 长标签被截断了两次。** `16ch` 约等于 8em，比契约已经允许的 10 个汉字还窄，
于是浏览器又剪了一次服务端已经剪过的文字——省略号套省略号，行动按钮顶到自己的边框。
现在只有契约裁剪，CSS 退回成兜底（`13em` / `11em`，都宽于契约允许的长度）。
行动按钮拿到比其他条目更紧的额度（`CTA_LABEL_LIMIT` 中文 7 / 英文 18）：
它空间最小、内边距最大，而它背后那个字段最容易被店主填成一句话。
首屏按钮直接读那个字段，仍然显示全文。

## v9.9.1 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `claude/ui-ux-pro-max-audit-073a82`；部署代码 commit `aeda04e98b9faaa062c1938285a1b10cc008bd9b`；`VERSION=9.9.1`。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` **全部通过**；pytest `1726 passed, 5 skipped`；legacy CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`。 |
| Package | SaaS SHA-256 `f62c355b6e89fde18632314945ac6058d702bd9b5dd2010825f2a8763a6c83db`；Edition SHA-256 `b7fc586677f9c5686b00384e3ec8fb8cad4b922fc64ba60a4de56917dc9f2f19`。两个 `BUILD_INFO` 均为 v9.9.1。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.1`，镜像 `studiosaas:9.9.1`；deep health `appVersion=9.9.1`、`db=ok`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`；磁盘 `45.93 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS `0`、HTTP/2。回滚目录保留 `9.9.0` 与 `9.8.10`。 |
| Public evidence | 线上契约的导航标签现在只被裁剪一次：`原创油画 ×…` / `Original Personal…`（行动按钮，更紧的额度）、`Artworks…`（版块条目）。八条公开路由全部 `200`。 |

## 回归测试

- `test_public_shell.py`：行动按钮的额度、服务端与浏览器的 parity、CSS `max-width` 必须以 `em` 计并且不小于 `11em`（`16ch` 正是这条会拦住的写法）。
- `test_studio_admin_vocabulary.py`：草稿契约不许再读 `collectShowcaseItems()` 的输出。

---

# PWE Studio v9.9.0 — 导航、店名、公开地址：六批修复的生产闭环

> 当前阶段：v9.9.0 已完成源码、完整门禁、双模式打包、生产备份、部署、公网验收，以及存量租户工作区的一次性刷新。
> 本节记录本轮最终证据；后续文档闭环只更新发布账本，不改变已运行的 v9.9.0 包。

## v9.9.0 修复范围

按 [docs/design/Public_Surface_UX_Audit_v9.8.10.md](design/Public_Surface_UX_Audit_v9.8.10.md)
与 [docs/design/Tenant_Slug_Rename.md](design/Tenant_Slug_Rename.md) 的六个批次执行，全部是**已经在坏**的东西，不是缺的功能。

**一 · 导航。** hash 链接在每个页面都被改写成「租户首页 + 锚点」，**包括首页自己**——
在首页上，只要访客带着任何 query 进来，改写结果与当前 URL 的差异就不止 fragment，
于是每一次导航点击都是整页重载，并且顺手丢掉 `?lang=` 和所有 `utm_*`。
课表页从未在 `<body>` 上声明自己的 slug，它依赖的那次改写在那里等于没做。
首页的契约失败分支既不到 `apply()` 也不走本地兜底，导航会在加载遮罩下隐身到页面生命周期结束——
而它显示的提示写着「页面已按当前内容安全显示」。
另外修掉：两个死 id、`aria-current` 在首页恒真的判断、`.navlinks a` 把 CTA 的 `padding` 压成 `4px 0`。

**二 · 改名。** `tenants/<slug>/` 是物化的，店名在创建那一刻写进 `<title>`、社交预览标签和结构化数据，
之后没有任何东西重写它。发布现在会重渲染工作区（在 commit 之后，文件系统故障不能回滚已入账的发布），
head 文案由服务端按 portal 在浏览器里用的同一优先级组合。
deep health 新增 `workspaces` 块——它在这次部署完成的**同一分钟**就报出了 `ruby-s-studio`。

**三 · 公共 shell。** 四个公开页各自维护一份 header/footer 条目清单，已经漂移了三处。
条目改为三个共享片段，在生成工作区时拼接；页面外壳（`<nav>` 包裹层、品牌链接、语言开关）保持各页自有，
因为统一它们要改四个线上页面而访客看不到任何差别。导航标签在契约里截断
（`NAV_LABEL_LIMIT` 中文 10 / 英文 24，两个实现之间有 parity 测试），页面上的版块标题一个字不动。

**四 · Studio Admin。**「发布」有两个意思，其中一个只是存草稿。九个「是否公开」开关散在四个面板。
契约的 reasonCode 以标识符形态打给店主看。三个字段有四个名字。主理人没有自己的面板。

**五 · 中文。** 68 条可见英文串没有译文，包括发布仍在确认时显示的那一句。
新增覆盖门禁，按运行时真正遍历的规则扫描。

**六 · 公开地址。** 新增 `tenant_slug_aliases`（migration `0031`）：平台发放过的每一个地址都在册，
旧地址永久 301，地址**永不回收**（`ON DELETE SET NULL` 留墓碑，返回 410）。
每租户一年一次，仅 Platform Admin，双钥确认 + 键入当前地址。
301 的判断发生在文件系统查找之前——旧目录故意留到后续清理，顺序反了就会把访客送回工作室的过去。

未改动：套餐额度、支付能力、租户数据模型。

## v9.9.0 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `claude/ui-ux-pro-max-audit-073a82`；部署代码 commit `c13d5587e4fb9b7da6424233484d310f97d3931b`；`VERSION=9.9.0`、`APP_VERSION=9.9.0`、`RELEASE_DATE=2026-08-12`。本分支已从 `codex/v9.8.10-public-shell` fast-forward，六批改动在其之上。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` **全部通过**；pytest `1721 passed, 5 skipped`；legacy CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；Python/JS 编译、UI escaping、terminology、inline scripts、CMS bundle、asset manifest、迁移 current、媒体衍生图均通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.9.0.tar.gz` SHA-256 `b02854a87e18b4629eb9f46062121ec844fdc8e101cef23a46c74582738a210a`；Edition `dist/PWE-Studio-Edition-9.9.0.tar.gz` SHA-256 `689463e8705bfc91f6118d4454fe59614edb226cfb6368999fc822312ec4b0ff`。两个 `BUILD_INFO` 均为 v9.9.0，模式分别 `saas` / `standalone`，通过 checksum、入口、版本与排除项校验。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.0`，镜像 `studiosaas:9.9.0`；容器 healthy；公网 deep health `appVersion=9.9.0`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`、**`workspaces.stale=0`**；磁盘可用约 `45.96 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260812T123256Z.dump` 与 manifest，卷归档 `pwestudio-volumes-20260812T123257Z.tar.gz`。`0031_tenant_slug_aliases.sql` 已在启动时应用。回滚目录保留 `PWE-StudioSaaS-aws-9.8.10` 与 `9.8.9`。 |
| 存量刷新 | 部署后 deep health 立刻报出 `workspaces.stale=1`（`ruby-s-studio`：文件里是 `Ruby's Studio`，数据库里是 `Mellow Pear Studio`）。用 `refresh_tenant_workspaces_from_db.py --only-slug ruby-s-studio` 重渲染，随后 `stale=0`。**该脚本写于打包之后，不在 9.9.0 运行包内**，本次是把文件拷进容器执行的；它已提交到仓库，下一个版本起随包发布。 |
| Public routes | 根站、`/zh/manual/`、`/ruby-s-studio`、`/showcase`、`/timetable`、`/register`、`/lets-paint-showcase`、`/lets-paint-showcase/timetable`、`/platform-admin`、`/ruby-s-studio/studio-admin` 全部 `200`。 |
| Public evidence | `/ruby-s-studio` 的**服务端原始 HTML** 现在是 `<title>Mellow Pear Studio</title>`，description 为工作室自己的 slogan（此前是旧店名与通用模板句）。契约里长标签已截断：`Oil Painting, Acrylic P…`（原 74 字符 / 241px）、`Original Personalised O…`、`原创油画 × 私人…`。四个公开页的 `foot*` 契约条目集合完全一致。线上 `public-surface.js` 与仓库逐字节相同，在其上复核：首页带 `?lang=en&utm_source=wechat` 时 `navFaq` 解析为 `/ruby-s-studio?lang=en&utm_source=wechat#home:faq`——同文档跳转，query 不再丢失。 |

## 未做与已知项

- **导航项过多时的「更多 ▾」降级没有做。** 截断之后单项宽度已受控，剩下的是项目数问题（最多 8 项），留待观察真实租户。
- **公共 shell 只统一了条目清单，没有统一页面外壳。** `<nav>` 包裹层、品牌链接、语言开关属性（`data-set-lang` vs `data-language`）仍各页自有；这是权衡，不是遗漏——会漂移的是清单。
- **Studio Admin 未做登录后的实际交互验证。** 本轮不处理明文密码，后台结论来自源码、静态门禁与下发的 HTML。
- **旧工作区目录的清理 sweep 尚未实现。** 改名后旧目录会留在卷上；它不再被路由命中（301 在文件系统查找之前），但目前没有自动删除。首次真实改名之前应补上。
- **前台是否能批准约课**：`review_class_booking` 仍是 `@tenant_admin_required`，前台持有 `registrations:write`。这条设计问题从 v8.10.0 起就记在这里，仍未拍板。

---

# PWE Studio v9.8.10 — public shell and honest publication-status production closure

> 当前阶段：v9.8.10 已完成源码、验证、提交、推送、双模式打包、生产备份、部署和公网验收。本节记录本轮最终证据；后续文档闭环只更新发布账本，不改变已运行的 v9.8.10 包。

## v9.8.10 修复范围与验收

- Studio Admin 的发布复核改为读取服务端 `tenant_brand_versions` 状态，不再在浏览器深比较 `websiteProfile`；写入成功、公开投影待确认和确实无效分别使用结构化双语状态码。
- 官网、独立作品页、公开课表和报名页继续使用统一 `publicSurfaceContract`，升级到 contract v3，补充本地化导航/CTA 标签、公共 shell 结构和跨页面 hash 链接解析。
- 公开 Footer 移除工作人员 CMS 与 Studio Admin 链接；现有租户工作区已从 `tenant-template/` 重新生成，确保模板修复落到已存在的静态工作区。
- public-surface 标签在服务端和本地解析器中解析 `%WORK%` / `%WORKS%` / `%VENUE%` 行业词，避免把模板占位符显示给访客。
- 版本与双语用户手册入口更新到 v9.8.10；未改变租户数据模型、套餐额度或支付能力。

## v9.8.10 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 隔离分支 `codex/v9.8.10-public-shell` 已 push 到 `origin`；部署代码 commit `d8c11daa703c5080578931c723385e0ab79e87df`；`VERSION=9.8.10`。根工作区的其他用户改动未被修改或纳入。 |
| Local gates | `verify_local.sh` 在隔离 PostgreSQL 55432 与临时 venv 中全绿：Python/JS 编译、UI escaping、terminology、inline scripts、asset manifest、完整 pytest `1613 passed, 8 skipped`、CMS smoke `73 passed`、迁移 current、媒体衍生图 `0`、租户隔离 `237 passed, 0 failed`。公开表面本地 API 返回 contract v3，行业占位词已解析。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.10.tar.gz` SHA-256 `03cde6a4816308b5249ab270c12aee10b591b9140165d021dfd3963e04dcae1f`；Edition `dist/PWE-Studio-Edition-9.8.10.tar.gz` SHA-256 `d51d2cfd73c529465c8d58041bde8faf3f64bb42128faa96d3690514882074fa`。两个 `BUILD_INFO` 均为 v9.8.10 / commit `d8c11daa`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、版本和排除项校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.10`，镜像 `studiosaas:9.8.10`；容器 healthy；公网 deep health 为 `appVersion=9.8.10`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.08 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / recovery | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260812T104121Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260812T104122Z.tar.gz`；v9.8.9 与 v9.8.8 仍保留为回滚目录，`STUDIOSAAS_VERSION=9.8.10` 已固定。 |
| Public API | `https://pwestudio.online/v1/public/ruby-s-studio/surface` 返回 contract v3、`publishedVersion=45`，导航/footer/actions 共用本地化标签与统一 href；作品 API 首页返回 `pageSize=6`、`total=12`、`hasMore=true`，归档返回 `pageSize=12`、`hasMore=false`。 |
| Public routes / browser | 根站、双语手册、Ruby 首页/作品页/课表/报名、Studio Admin、Platform Admin 与双语 Release Notes 均返回 `200`。生产桌面截图 `/private/tmp/studiosaas-v9.8.10-ruby-home.png` 确认首屏、导航、首屏 CTA 与作品入口；390×844 截图 `/private/tmp/studiosaas-v9.8.10-ruby-showcase-mobile.png` 确认独立作品页移动布局、分类筛选和作品卡片。公开四个 Ruby 页面均不包含 `/cms` 或 `/studio-admin` Footer 链接。 |
| Logs | 部署后 app-only 日志显示迁移 current、`Generated variants: 0`、10 个租户工作区重生成以及健康的 `200` 请求；未发现部署后新的 `Traceback`、`Exception`、`Fatal` 或应用错误。 |

# PWE Studio v9.8.9 — Studio Admin public surface and Edition production closure

> 当前阶段：v9.8.9 已完成代码与文档范围冻结、Studio Admin 公开表面修复、统一公开契约、空间与体验模块、Draft / Live 预览、版本化发布验证，以及 standalone Edition 完整部署方案并入；已完成本地完整门禁、Git 推送、双模式打包、生产备份、部署和公网浏览器验收。

## v9.8.9 候选范围

- Studio Admin 将保存、发布写入和公开验证拆成明确状态，使用结构化错误码与持久错误摘要，避免网站已更新却显示英文误报；外部 CTA 只接受 HTTPS。
- 首页、作品页、课表、报名、导航与 Footer 共用 `publicSurfaceContract` v2，输出 owner intent、内容/依赖就绪度、可见性、原因码、下一步和发布版本。
- 空间与体验模块支持 6 条亮点、最多 6 张有序照片和中英文替代文本；公开页不自动轮播，无图片时使用约 1.618:1 的正文布局。
- Studio Admin 提供 Draft / Live 预览、有效公开状态、导航/Footer 映射、未就绪原因和下一步；发布后按 `publishedVersion` 核对 `/brand`、`/surface` 以及实际启用的独立页面。
- 已将任务 `019ff42b-93f5-7293-a263-9c4eafd300e2` 的 standalone 部署文档并入，并统一到 v9.8.9，包括客户前置条件、Docker Compose、TLS、PostgreSQL 16、账号/密钥、迁移、备份恢复、验收、回滚与职责边界。

## 最终发布证据（2026-08-12）

| 层级 | 已验证事实 |
|---|---|
| Source | 隔离分支 `codex/v9.8.9-studio-admin-publish` 已 push；部署代码 commit `2411ec6fc52334dcf65884060a6fc9a5f50fab0f`；`VERSION=9.8.9`。根工作区的其他用户改动未被修改或纳入。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 STUDIOSAAS_MEDIA_DIR=/private/tmp/studiosaas-media-gate.zlytk0 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `1612 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；PostgreSQL 迁移、安全媒体衍生图、Python/JS 编译、inline scripts、CMS bundle、asset manifest、shell parse 与 `git diff --check` 均通过。Standalone 与公开表面定向测试为 `92 passed, 1 skipped`。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.9.tar.gz` SHA-256 `c6aee22bd60321d33cccfb793dc4ddbf082ff8240e8904b340ef172368c64675`；Edition `dist/PWE-Studio-Edition-9.8.9.tar.gz` SHA-256 `9bd1d37f374f86e2977081893b9c9243fac49818b1f734195800740ccfa57b0d`。两个 `BUILD_INFO` 均为 v9.8.9 / commit `2411ec6`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、版本和排除项校验。Edition 包包含本轮并入的完整 standalone 部署方案。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.9`，镜像 `studiosaas:9.8.9`；容器 healthy；公网 deep health 为 `appVersion=9.8.9`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.1 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Public API | `/v1/public/ruby-s-studio/surface` 返回 contract v2、`publishedVersion=45`，showcase intent / ready / visible 均为 true，导航、Footer 与次要 CTA 均指向 `/ruby-s-studio/showcase`。作品归档返回 12 件、3 个分类；分类 `76703d2c` 返回 9 件。 |
| Browser | 真实生产桌面 1280px 确认首页在权威契约返回后显示 Principal、Selected Work、FAQ 与报名入口，首页精选 6 件并显示 View all work。独立作品页显示 12 件；灯箱图片加载成功、计数 `1 / 12`、body scroll lock 生效。390×844 分类 URL 保持筛选并显示 9 件，文档宽度等于视口 390px，移动菜单为 44×44。根站、双语手册、Ruby 首页/作品页、Studio Admin、Platform Admin 与 canonical 双语 Release Notes 均返回 200。 |
| Recovery | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260812T092107Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260812T092108Z.tar.gz`；v9.8.8 运行包继续作为回滚基线。 |
| Logs / known ops note | 当前 app 日志为健康的 200/202/304 请求，未发现新的 Traceback、Exception、Fatal 或 ERROR；并发作品媒体加载期间 Waitress queue depth 短暂达到 5，健康检查持续绿色。独立 `disk` 命令打印 20% 使用率和约 47G 可用但返回 1；deep health 的磁盘状态为 `ok`，该运维命令的退出码应在下一轮单独修正。Release Notes 在 1280px 时，旧 v9.8.8 的 64 位 SHA 文本导致约 21px 横向溢出；公开核心首页与作品页验收不受影响，CSS 换行应作为下一小版本修复。 |

# PWE Studio v9.8.8 — truthful public surface verification production closure

> 当前阶段：v9.8.8 已完成发布写入与公开验证解耦、统一 `publicSurfaceContract`、亮色 Studio Admin 工作台、导航/Footer 可见性解析、结构化双语错误、手册同步、完整门禁、双模式打包、main 同步、最终生产备份、部署和公网浏览器验收。本节记录运行包的最终证据；本次修改之后的 handoff 文案只更新发布账本，不改变已运行的包。

## v9.8.8 修复范围与验收

- Studio Admin 写入成功后不再因公开投影短暂延迟而误报失败；状态改为「已发布，公开页面仍在确认」，提供结构化重试和双语错误码。
- 官网、独立 `/showcase`、公开课表和报名页共用一套公开表面契约；导航与 Footer 只展示同时满足 owner intent 和真实公开内容的入口，预览区显示未就绪原因与下一步。
- Studio Admin 采用信息色亮色选中态与 `1.618fr / 1fr` 编辑器/预览比例，保持现有 Vanilla HTML/CSS 栈，并覆盖键盘焦点、reduced-motion 和移动端触摸目标。
- 作品数据、`featured_rank`、套餐切换保留规则和首页 6 / 归档 12 / 分类 URL 逻辑继续沿用 v9.8.7；本轮没有新增数据迁移。

## v9.8.8 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 运行代码 commit `4b436e1e2df0717b7efb01d5e7d4021a6cc23860`；`VERSION=9.8.8`；`main` 与候选分支均已 push。后续本 handoff 更新为 docs-only 发布账本，不改变运行代码。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `2292 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；Python/JS 编译、UI escaping、terminology、inline assets、asset manifest 和 `git diff --check` 均通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.8.tar.gz` SHA-256 `1d6fc1760993864c681c8f9cb5e58eac303acdb65573ba98978181f226ee3da7`；Edition `dist/PWE-Studio-Edition-9.8.8.tar.gz` SHA-256 `0a75bf66059da97dc91b450933bd2a44e48200b7dda17030b62baa22ec1cd3b6`。两个 `BUILD_INFO` 均为 v9.8.8、commit `4b436e1e2df0717b7efb01d5e7d4021a6cc23860`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、版本和排除项校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.8`，镜像 `studiosaas:9.8.8`；容器 healthy；公网 deep health 为 `appVersion=9.8.8`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.06 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / recovery | 最终切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260811T121335Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260811T121336Z.tar.gz`；回滚目录 `PWE-StudioSaaS-aws-9.8.7` 与前一运行包归档仍保留。 |
| Public API | Ruby Studio 首页作品接口返回 `pageSize=6`、`total=12`、`nextOffset=6`、`hasMore=true`；归档返回 `pageSize=12`；分类 `76703d2c` 返回 `total=9`；`offset=12` 返回空页且 `hasMore=false`。`/v1/public/ruby-s-studio/surface` 返回版本化 navigation/footer/modules 契约。 |
| Public routes / browser | 根站、双语手册、`/ruby-s-studio`、`/ruby-s-studio/showcase`、timetable、register、CMS、Studio Admin、Platform Admin 和双语 Release Notes 均返回 `200`。Codex In-app Browser 在默认 `1280px` 与 `375px` 视口确认无横向溢出；移动菜单可见且触摸目标为 `44px`；点击首件打开 lightbox，图片存在、计数为 `1 / 12`、关闭后 dialog 消失；分类 URL `?category=76703d2c&lang=en` 保持筛选。 |
| Logs | 部署后 app-only 日志包含正常的 `200/304` 静态资源、公开 API 和媒体响应；未出现新的 `Traceback`、`Exception`、`Fatal` 或 `ERROR`。高峰浏览期间出现 Waitress queue depth `1–4` 的非致命 warning，健康检查仍为绿色，列为后续容量监测项。 |

后续运行代码应从 v9.8.9 开始；v9.8.7 和 v9.8.6 保留为回滚基线。

# PWE Studio v9.8.7 — ranked standalone showcase production closure

> 同步说明：Platform Admin 的历史优化清单与三栏工作台评审已随 `origin/main` 合并，完整方案保存在 [docs/design/Platform_Admin_Workspace.md](docs/design/Platform_Admin_Workspace.md)。本 handoff 继续只记录已发生的发布事实；方案文档不替代生产证据。

> 当前阶段：v9.8.7 已完成 `featured_rank` 数据契约、首页精选预览、独立 `/showcase` 作品归档、分类 URL、C 方案分页、统一导航/footer、后台排序编辑、套餐变更内容保留、双语手册更新、完整门禁、双模式打包、分支 push、生产迁移、备份、部署和公网浏览器验收。生产运行部署代码 commit `4e1894f12a31935701f3982757bd8fe0f441e0d0`；本节以下为本轮最终证据。文档闭环提交只更新发布记录，不改变已运行的 v9.8.7 包。

## v9.8.7 修复范围与验收

- 作品记录支持可选的租户全局 `featured_rank`（1–500）；数字越小越靠前，首页使用前 6 个排序位置，未排序作品沿用稳定的原有顺序。所有 Active / draft / archived 记录都保留排序值，套餐切换不会删除作品或重排已保存数据。
- 首页只请求最多 6 件公开作品；独立 `/<slug>/showcase` 归档默认每次返回 12 件，按全局排序后再执行分类过滤，继续通过 offset 的 C 方案分页和可见的「加载更多」兜底；分类筛选可分享为独立 URL。
- 公开页、课表、报名页与首页共享导航和 footer 入口；standalone showcase 使用可访问的键盘 lightbox、Escape、前后导航、焦点恢复、懒加载、移动端菜单和 reduced-motion 支持。
- Studio Admin 新增 Featured rank 输入、预览顺序和双语说明；在线用户手册、Studio Owner/CMS/Admin 指南、customer Release Notes 同步说明首页 6 件、归档 12 件、分类 URL、套餐额度和 Starter / 入门版、Studio / 工作室版、Growth / 成长版命名。
- 新增 `0030_showcase_featured_rank.sql`，以幂等 JSONB backfill 为旧作品补充 `featured_rank: null`，不覆盖现有内容或状态。

## v9.8.7 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已 push 到 `origin`；部署代码 commit `4e1894f12a31935701f3982757bd8fe0f441e0d0`；`VERSION=9.8.7`；本节之后的文档闭环只更新 README、handoff 与 Release Notes，不改变运行代码。未跟踪的 `docs/sales/` 路演资料未纳入发布。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `2291 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；`git diff --check`、UI escaping、terminology、inline-script、asset manifest 和双包校验均通过。首次无提升权限的本地 gate 只受到端口绑定/数据库可达环境限制，提升权限复跑后全绿，不作为产品回归。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.7.tar.gz` SHA-256 `8181b9324ef4f66297cacb9b9d440c4ecec458f34151d887965ff850c07392c1`；Edition `dist/PWE-Studio-Edition-9.8.7.tar.gz` SHA-256 `16473b8d4ad17c57e3603cef34915aca00b6e8a2c87305b146240ce8d1d64403`。两个包的 `BUILD_INFO` 均为 v9.8.7 / commit `4e1894f12a31935701f3982757bd8fe0f441e0d0`，模式分别为 `saas` / `standalone`，并通过 checksum、入口、`mode` 和排除项检查。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.7`，镜像 `studiosaas:9.8.7`；容器 healthy；公网 deep health 为 `appVersion=9.8.7`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；部署后磁盘可用约 `46.25 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 切换前自动生成逻辑库备份 `studiosaas_studiosaas_20260811T083534Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260811T083535Z.tar.gz`。生产启动日志确认 `0030_showcase_featured_rank.sql` 已应用，`Generated variants: 0`，运行数据库角色配置与租户工作区重生成完成。 |
| Public API | Ruby Studio `https://pwestudio.online/v1/public/ruby-s-studio/showcase?surface=home&offset=0` 返回 `total=12`、`pageSize=6`、`nextOffset=6`、`hasMore=true`；默认归档返回 `pageSize=12`、`total=12`；分类 `76703d2c` 返回 `total=9`、`items=9`；`offset=12` 返回空页且 `hasMore=false`。排序字段随条目返回，当前未设置的生产条目为 `featured_rank=null`，稳定 fallback 顺序保持不变。 |
| Public routes / browser | 根站、`/zh/manual/`、`/manual/`、`/ruby-s-studio`、`/ruby-s-studio/showcase`、timetable、register、CMS、Studio Admin、Platform Admin 和双语 Release Notes 均返回 `200`。真实生产 390×844 CDP 视口确认 `documentWidth=390`、移动菜单 44×44 可见、12 个归档卡片无横向溢出；点击首件打开 lightbox，图片存在、计数为 `1 / 12`、body scroll lock 生效，点击关闭后 dialog 关闭且焦点/滚动状态恢复。截图保存在 `/private/tmp/studiosaas-showcase-v987-prod-390.png`。 |
| Logs | v9.8.7 app-only 容器日志从启动、迁移、工作区重生成到健康检查均为正常输出，未出现部署后新的 `Traceback`、`Exception`、`Fatal` 或 `Error`；历史数据库探索日志未作为本轮应用错误。 |

后续如需再改运行代码，应从 v9.8.7 新版本号继续，不复用已发布的 `9.8.7` 包标签；v9.8.6 保留为回滚基线。

# PWE Studio v9.8.6 — 在线手册课表与约课发布闭环

> 当前阶段：v9.8.6 已完成双语在线手册的公开课表与约课章节、配套后台/手机截图、版本升级、完整门禁、双模式打包、分支 push、生产部署和公网验收。生产运行部署代码 commit `21d2cc70bcd116250fca4780bec164a855b45258`；本节以下为本轮最终证据。文档闭环提交只更新发布记录，不改变已运行的 v9.8.6 包。

## v9.8.6 修复范围与验收

- 在线用户手册新增独立的「公开课表与约课」章节，说明品牌工作台中的课表开关、班次公开、1–4 周显示范围、约课申请开关、字段显示和老师姓名授权。
- 说明约课申请与正式占位的边界：访客提交后进入 CMS 待处理列表，只有批准时才核对容量；拒绝或撤回不会占用名额。
- 补齐四张中英文配对截图，覆盖 Studio Admin 公开课表设置与移动端约课申请弹窗；截图使用合成 `lets-paint-showcase` 捕获租户，不写入客户记录。
- `VERSION` 与应用版本更新为 `9.8.6`；未新增数据库迁移，也未修改客户业务数据。

## v9.8.6 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已 push 到 `origin`；部署代码 commit `21d2cc70bcd116250fca4780bec164a855b45258`；`VERSION=9.8.6`；随后提交的文档闭环只更新 README、handoff 与 Release Notes，不改变运行代码。未跟踪的 `docs/sales/` 路演资料未纳入发布。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过；完整 pytest `2283 passed, 8 skipped`；CMS smoke `73 passed`；租户隔离 `237 passed, 0 failed`；`git diff --check` 和发布资产检查通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.6.tar.gz` SHA-256 `bd532a34d79ef74717218cde59a69d9b9f1fac7978ee6a52fb2509abc568536e`；Edition `dist/PWE-Studio-Edition-9.8.6.tar.gz` SHA-256 `f0c70727457ead7616958f2d051020c2cfe32f679289ff5cc2f16018a5c5df6b`。两个包的 `BUILD_INFO` 均对应 commit `21d2cc7`，模式分别为 `saas` / `standalone`，并通过 checksum、入口和排除项校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.6`，镜像 `studiosaas:9.8.6`；容器 healthy；公网 deep health 为 `appVersion=9.8.6`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.35 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 部署前后已生成逻辑库备份 `studiosaas_studiosaas_20260811T064145Z.dump` 与 manifest，以及卷归档 `pwestudio-volumes-20260811T064146Z.tar.gz`。生产已应用至 `0029_showcase_plan_values_and_states.sql`；启动日志为 `Database is up to date`，安全媒体衍生图为 `Generated variants: 0`。 |
| Public routes | 根站、`/zh/manual/`、`/manual/`、`/lets-paint-showcase`、`/lets-paint-showcase/timetable`、CMS、Studio Admin、register，以及中英文 Release Notes 均返回 `200`。 |
| Assets / logs | 中文手册课表截图 URL 为 `/assets/manual/04-timetable.zh.webp?v=9.8.6&h=6157b883c9c46d13`；本地与公网 SHA-256 均为 `6157b883c9c46d13a5eef10888f1cf739f5c3aa26db748856216a272ded70999`，缓存为 `public, max-age=31536000, immutable`，条件请求返回 `304`。应用容器自部署以来没有 `Traceback`、`Exception`、`Fatal` 或 `Error` 关键字，启动与手册/课表请求均为健康响应。 |

后续如需再改运行代码，应从 v9.8.6 新版本号继续，不复用已发布的 `9.8.6` 包标签；v9.8.5 仍保留为回滚基线。

---

# PWE Studio v9.8.5 — 作品展示手册与 Platform Admin 操作上下文发布闭环

> 当前阶段：v9.8.5 已完成工作室作品展示手册的中英文重写、套餐关联作品规则与媒体链接说明、手册截图资源、移动端导航修复，以及 Platform Admin 高频操作上下文与套餐/租户编辑影响预览；已完成完整门禁、双模式打包、分支推送、生产部署和公网验收。生产运行部署代码 commit `bcd4f1ba6ed2dcd2073a1a09b0ed5cf907f8a9ab`；本节记录本轮最终证据。

## v9.8.5 修复范围与验收

- 用户手册的 Studio Showcase 章节改为中英文一致的操作说明，明确工作室作品与学员作品边界，并补充图片上传、YouTube / Vimeo / Bilibili 视频链接识别与识别失败提示。
- 手册固定记录 v9.8.x 作品额度规则：Starter `15`、Studio `60`、Growth `150`；最多保存 `500` 条、每页 `12` 条、最多 `8` 个分类。分页大小不再被描述为总量上限。
- 更新前台与后台截图为本地合成示例，补齐中英文、桌面/移动端手册资源，并修复移动端固定导航遮挡标题的问题；截图不冒充生产租户数据。
- Platform Admin 的 `Actions/操作` 保持高频租户与套餐命令；行点击仍打开快速查看，选择具体操作后才在右侧显示影响、保留内容、通知对象和下一步确认。工作室编辑与套餐编辑均展示保存前影响审查，API 继续执行双重确认。

## v9.8.5 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已推送到 `origin`；`VERSION=9.8.5`；部署代码 commit `bcd4f1ba6ed2dcd2073a1a09b0ed5cf907f8a9ab`。本轮包含另一任务已完成的用户手册更新；未跟踪的 `docs/sales/` 资料未纳入发布。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 通过；完整 pytest `1986 passed, 8 skipped`；租户隔离 `237 passed, 0 failed`；`git diff --check`、inline-script 检查和 asset manifest 检查均通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.5.tar.gz` SHA-256 `1bc99fd90d5e40fddbc598e5fd01aa589b1eecedaff9dd27d92c2f566cdbef9d`；Edition `dist/PWE-Studio-Edition-9.8.5.tar.gz` SHA-256 `68409b931c76b8aef72cc66e391a6f954303cda4239ef64bc32a72876b4de4b3`。两个包的 `BUILD_INFO` 均对应 commit `bcd4f1b`，模式分别为 `saas` / `standalone`，并通过发布包校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.5`，镜像 `studiosaas:9.8.5`；容器 healthy；公网 deep health 为 `appVersion=9.8.5`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用约 `46.44 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Backup / migration | 部署前后均有逻辑库与卷备份；本轮最新逻辑库备份为 `studiosaas_studiosaas_20260811T053608Z.dump`，卷归档为 `pwestudio-volumes-20260811T053609Z.tar.gz`，manifest 同时存在。启动日志显示数据库已是最新，迁移包含 `0029_showcase_plan_values_and_states.sql`；媒体衍生图检查为 `Generated variants: 0`。 |
| Public routes | 根站、中文手册、展示门户、timetable、CMS、Studio Admin、register、双语 Release Notes 与 Platform Admin 均返回 `200`。用户提到的 Ruby Studio 公共作品 API 返回 `total=12`、`3` 个分类且全部为 `active`；`lets-paint-showcase` 示例租户 API 当前为 `total=0`，因此手册中的作品截图明确为本地合成示例，不将示例误写成生产租户作品。 |
| Assets / media | 生产 CMS immutable JavaScript 与本地 SHA-256 一致，条件请求返回 `304`；中英文手册 WebP 资源均以 immutable 缓存返回且与本地 SHA-256 一致；代表性公开品牌媒体返回 `200 image/jpeg`，带 ETag 的条件请求返回 `304`。 |
| Logs / browser | 部署后的 app-only 日志当前请求均为健康的 `200/304`，未出现当前 Traceback / Exception / Fatal / Error；本地隔离数据库完成 Platform Admin 桌面与 390×844 移动端验收，无横向溢出，并确认行点击快速查看、`操作` 集中动作和套餐影响审查路径。未使用生产凭据或执行生产写操作。 |

本次部署已包含用户手册更新文件和生成的中英文截图资源；未包含用户另行保留的 `docs/sales/` 路演资料。后续文档闭环提交只更新 README、handoff 与 Release Notes，不改变运行代码，也不重新打包。

# PWE Studio v9.8.4 — 套餐变更安全与 Platform Admin 交互闭环

> 当前阶段：v9.8.4 已完成套餐升级/降级的影响预览与双重确认、内容保留保护、Platform Admin 快速查看与集中操作、中英文套餐命名规范，并已完成完整门禁、双模式打包、分支推送、生产部署和公网验收。生产运行部署代码 commit `c0e344aa82a4a2358c0052123ba7b6dd633fb057`；本节以下为本次闭环证据。

## v9.8.4 修复范围与验收

- 套餐变更在保存前读取服务端影响摘要，明确列出会变化的价格/额度/功能、继续保留的网站与业务内容，以及必须通知工作室的事项；未勾选“已检查影响并会通知”时，API 以结构化 `409` 拒绝保存。
- 套餐更新在租户行锁内合并商业字段，保留未提交的品牌、官网、首屏、FAQ、作品、主题、消息模板、学员、课程、报名、媒体和审计数据；接受的变更写入审计记录。
- Platform Admin 的工作室与套餐行点击直接打开只读 Inspector；编辑、生命周期、支持、归档和删除统一收进中间列表的 `操作`，右侧只负责快速查看。
- 套餐名称统一为 Starter / 入门版、Studio / 工作室版、Growth / 成长版；API code 保持 `starter` / `studio` / `growth` 不变。

## v9.8.4 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery` 已推送到 `origin`；部署代码 commit `c0e344aa82a4a2358c0052123ba7b6dd633fb057`；`VERSION=9.8.4`。部署后文档闭环提交只更新 README 与 handoff，不改变运行代码。 |
| Local gates | `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 全部通过：完整 pytest `1982 passed, 8 skipped`、CMS smoke `73 passed`、PostgreSQL 迁移与安全媒体衍生图检查、租户隔离 `237 passed`；`git diff --check` 通过。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.4.tar.gz` SHA-256 `b323ac360b4f13386b6a76d591ac90f773371777aaa340b355176642a60f76ae`；Edition `dist/PWE-Studio-Edition-9.8.4.tar.gz` SHA-256 `b9317a92374f58e17b681206029704f8493a59d046704d32a68a722c04b506c1`。两个包通过 checksum、`BUILD_INFO`、入口和排除项检查，均对应 commit `c0e344aa82a4a2358c0052123ba7b6dd633fb057`，模式分别为 `saas` / `standalone`。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.4`，镜像 `studiosaas:9.8.4`；容器 healthy；公网 deep health 为 `appVersion=9.8.4`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；磁盘可用 `46.62 GB`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Migration / recovery | 生产启动已应用 `0029_showcase_plan_values_and_states.sql`；生产媒体安全检查为 `Generated variants: 0`；套餐变更不会删除 Ruby Studio 或其他租户的作品/品牌/业务数据。 |
| Backup | 部署切换自动生成 `/data/backups/postgres/studiosaas_studiosaas_20260811T035703Z.dump` 与对应 manifest，以及 `/data/backups/volumes/pwestudio-volumes-20260811T035705Z.tar.gz`。 |
| Public edge / media | 根站、中文手册、Ruby Studio 门户 / timetable / CMS / Studio Admin、双语 Release Notes、Platform Admin 均返回 `200`；版本化 `ui-common.js` 与 `admin-i18n.js` 的本地/生产 SHA-256 一致且带 immutable 缓存；代表性 Ruby 媒体返回 `200 image/jpeg`，带 ETag 的条件请求返回 `304`。 |
| Logs | 生产 app-only 日志的当前请求均为健康的 `200/304`；未出现当前 Traceback / Exception / Fatal / Error。旧探索命令产生的数据库日志未作为当前应用错误引用。 |
| Browser | 应用内 Browser 未使用生产凭据、未执行生产写操作；本地仅使用隔离测试数据库完成真实登录验收：桌面确认租户/套餐行点击为 Quick view、`操作` 打开集中动作，套餐编辑显示“将发生变化/将继续保留/需要通知工作室”和强制勾选；390×844 手机视口确认 Platform Admin 无横向溢出（`scrollWidth=clientWidth=390`），并完成 viewport reset。 |

本次未修改或打包未跟踪的 `docs/sales/` 路演资料已保留，不纳入提交或发布包。

---

# PWE Studio v9.8.3 — 套餐关联作品发布与生产部署闭环

> 当前阶段：v9.8.3 已完成套餐关联的作品发布额度、active/draft/archived 状态、Super Admin 套餐字段和兼容性保护，并从已部署 v9.8.2 基线完成完整门禁、双模式打包、生产部署与公网验收。生产运行 commit `97b041495800edd1b41dc742c399587fed289ad7`；本节以下为本次闭环证据。

## v9.8.3 修复范围与验收

- starter / studio / growth 的 active 作品额度固定为 `15 / 60 / 150`；公开接口每页仍返回最多 12 件，这只是分页大小，不再是总量限制。
- 作品记录统一保留 `active` / `draft` / `archived` 发布状态；套餐下调只减少公开 active 数，不删除作品，超出当前额度的新上传自动进入 draft。
- Studio Admin 显示套餐额度与三类作品计数，允许逐件切换发布状态；Super Admin 套餐表单可读取、校验并保存 `showcaseLimit`。
- 缺省旧记录按 active 兼容；PATCH 套餐请求省略 `showcaseLimit` 时保留现有值，避免旧调用方将额度静默改回默认值。

## v9.8.3 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery`；部署代码 commit `97b041495800edd1b41dc742c399587fed289ad7`；`VERSION=9.8.3`。未推送 Git 远端。 |
| Local gates | 完整 pytest `1964 passed, 8 skipped`；`backend/scripts/verify_local.sh` 全部通过（含 CMS smoke `73 passed`、租户隔离 `237 passed`、迁移与生成资产检查）；`git diff --check` 通过。 |
| Package | SaaS SHA-256 `08b47e4bfce26bb69a7329d3bb40d6cd8f2cac55e9a148d51e430b15d249b44e`；Edition SHA-256 `9169cdc3d77a54fdcf76fd857589d69d7e7fc1688db06a9646ed5d365eaa4244`。两个包的 `BUILD_INFO` 均为 v9.8.3 / commit `97b041495800edd1b41dc742c399587fed289ad7`，模式分别为 `saas` / `standalone`，并通过发布包校验。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.3`，镜像 `studiosaas:9.8.3`；容器 healthy；公网 deep health 为 `appVersion=9.8.3`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Migration / quota | 生产启动已应用 `0029_showcase_plan_values_and_states.sql`；生产数据库确认 `growth=150`、`starter=15`、`studio=60`。 |
| Content recovery | 生产数据库确认 Ruby Studio 当前套餐为 `growth`，保留 `12` 件作品与 `4` 个分类；公开 showcase 返回 `total=12`、`items=12`、`hasMore=false`，全部为 `active`。未执行删除或覆盖作品数据。 |
| Backup | 部署自动备份：`studiosaas_studiosaas_20260811T030431Z.dump` / `studiosaas_studiosaas_20260811T030431Z.manifest.json`；卷归档 `pwestudio-volumes-20260811T030432Z.tar.gz`。 |
| Public edge / media | 根站、中文手册、Ruby Studio 门户 / timetable / CMS、Release Notes 均返回 `200`；版本化 `ui-common.js` 的 `h=` 与内容 SHA-256 前缀一致并带 immutable 缓存；代表性 Ruby 媒体返回 `200 image/jpeg`，带 ETag 的条件请求返回 `304`。 |
| Logs | 部署后应用日志持续返回健康检查、公开套餐、showcase、门户和媒体请求；最近日志未出现 Traceback / Exception / Fatal / Error 关键字。 |

本次未修改或打包未跟踪的 `docs/sales/` 路演资料。部署包对应部署代码 commit；本次文档闭环提交只更新 README 与 handoff，不改变运行代码，也不重新打包。

---

# PWE Studio v9.8.2 — Ruby Studio 内容恢复与作品灯箱 hotfix

> 当前阶段：v9.8.2 已从生产 v9.8.1 的精确 commit 基线完成修复、完整门禁、双模式打包、生产部署、Ruby Studio 内容恢复与公网浏览器验收。生产运行 commit `25d782c994b7c0de36c73c1e4f4472ed50f5f1f5`；本节以下为本次闭环证据。

## v9.8.2 修复范围与验收

- 套餐/联系人等 Platform Admin 更新在行锁内读取现有 `settings`；请求未携带的官网、主理人、首屏、FAQ、作品、视觉主题和消息模板必须原样保留。
- 作品灯箱使用固定居中的 viewport 容器、`minmax(0,1fr)` 媒体轨道和 `object-fit: contain`；横版/竖版图都不得溢出到底部信息栏或偏向单侧。
- 恢复只取 Ruby Studio 已发布 v44 的品牌内容，保留刚切换的 `growth` 套餐；写入前创建新逻辑/卷备份，写入后核对 12 件作品、媒体可读性和公开页面。
- 完整 pytest、CMS smoke、PostgreSQL 租户隔离、生成资产、双模式发布包、桌面/手机浏览器、生产 deep health、日志与回滚点均须通过。

## v9.8.2 最终发布证据（2026-08-11）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.8.2-showcase-content-recovery`；`VERSION=9.8.2`；部署候选 commit `25d782c994b7c0de36c73c1e4f4472ed50f5f1f5`。未推送 Git 远端，避免在发布目标未确认时替用户决定仓库归属。 |
| Local gates | 完整 pytest `1960 passed, 8 skipped`；完整发布门禁 `All checks passed`；CMS smoke `73 passed`；PostgreSQL 租户隔离 `237 passed`；发布后追加结构断言再次通过完整 pytest；`git diff --check` 通过。 |
| Package | SaaS SHA-256 `f11c7f9bceba0ea8bac3e5ae752af49e8cb969845bc8c84eca2e39fba73760c5`；Edition SHA-256 `661869d273b0b3684494b767c112bbbb55bc30f7b63522923542dd1290249530`。两个包的 `BUILD_INFO` 均为 v9.8.2 / commit `25d782c994b7c0de36c73c1e4f4472ed50f5f1f5`，模式分别为 `saas` / `standalone`，并通过 checksum、入口与排除项检查。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.2`，镜像 `studiosaas:9.8.2`；内部和公网 deep health 均为 `appVersion=9.8.2`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；HTTP→HTTPS `301`，HTTPS `200`、TLS 校验 `0`、HTTP/2。 |
| Recovery | 切换套餐造成的覆盖发生于 `2026-08-11 01:38:57 UTC`。恢复前 dry-run 确认 v44 含 12 件作品且目标套餐为 `growth`；恢复后产生关联版本 v45 和 `brand.version_recovered` 审计。数据库确认 12 件作品、4 个分类、作品展示开启、主理人资料存在，并且 tenant/subscription 套餐均仍为 `growth`。 |
| Backup | 部署自动备份：`studiosaas_studiosaas_20260811T020647Z.dump` / `pwestudio-volumes-20260811T020648Z.tar.gz`；恢复前再备份：`studiosaas_studiosaas_20260811T021148Z.dump` / `pwestudio-volumes-20260811T021149Z.tar.gz`，manifest 均存在。 |
| Browser / media | 公网 Ruby Studio 已显示作品区；实际 1500×2000 图片在 1440×1000 视口内以 `object-fit: contain` 完整居中，未进入底部信息/操作栏，弹窗计数为 `1 / 12`；浏览器控制台错误为 0。生产媒体接口对 12 件作品均返回 200，媒体衍生图检查 `Generated variants: 0`。本地另以 390×844 手机视口验证全屏灯箱、标题/说明、前后与关闭按钮可用且无横向溢出。 |

本次未修改或打包未跟踪的 `docs/sales/` 路演资料。发布包已部署；本闭环文档提交仅记录生产证据，不改变运行代码，也不重新打包。

---

# PWE Studio v9.8.0 — Platform Admin 三栏工作台发布 handoff

> 当前阶段：v9.8.0 已完成三栏工作台、Today Needs attention、Tenant/Plan/Audit Inspector 和移动端抽屉实现，并已通过完整门禁、干净双模式打包、提交同步、生产部署和公网验收。生产已由 v9.7.0 切换为 v9.8.0。历史发布证据保留在本节下方。

## 下一阶段设计入口

- [三栏工作台交互合同](design/Platform_Admin_Workbench_Interaction_Contract_2026-08-10.md)：冻结顶部栏、左侧工作区、中间工作流、右侧 Inspector、状态、权限、品牌和 P0/P1/P2 边界。
- [逐屏设计 handoff](design/Platform_Admin_Screen_Design_Handoff_2026-08-10.md)：Today、Tenants、Tenant Inspector、Plans、Audit、移动端和交接产物顺序。
- [前一阶段逐屏审计与状态矩阵](design/Platform_Admin_Audit_2026-08-10.md)：记录 v9.7.0 的 current-truth、真实审计和已完成发布证据。

本阶段设计原则：左边找地方，中间做事情，右边做判断；Attention 是 Today 内的快捷入口，不是第二套 Dashboard；Support Mode 必须使用 reason 和审计流程；未接入的数据、支付状态和未来页面不得提前进入一级导航。

## v9.8.0 最终发布证据（2026-08-10）

| 层级 | 已验证事实 |
|---|---|
| Source | 分支 `codex/v9.3.0-cms-information-architecture`；`VERSION=9.8.0`；部署候选 commit `906d18549475ac35b2cabd24c31a7944b83cfc31`；已推送至 `origin`。 |
| Package | SaaS `dist/PWE-StudioSaaS-aws-9.8.0.tar.gz`，SHA-256 `af814ad66036a8c8686f3c94394fa1b1e63d2cc4fb9bb11d5878d7c8670bc29b`；Edition `dist/PWE-Studio-Edition-9.8.0.tar.gz`，SHA-256 `30731b98b66276024f1fbbefe75f0fc93e7832d0388aeac1ae9b8a44439aa6e8`。两个包均通过 checksum、`BUILD_INFO`、入口文件和排除项检查；构建时间 `2026-08-10T03:52:57Z`，模式分别为 `saas` / `standalone`。 |
| Production | `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.8.0`，运行镜像为 `studiosaas:9.8.0`；deep health 为 `appVersion=9.8.0`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；容器 healthy，磁盘可用约 `46.83 GB`。 |
| Backup | 切换前逻辑备份 `/data/backups/postgres/studiosaas_studiosaas_20260810T035741Z.dump` 与 manifest `/data/backups/postgres/studiosaas_studiosaas_20260810T035741Z.manifest.json`；卷归档 `pwestudio-volumes-20260810T035742Z.tar.gz`。 |
| Migration / media | 最新迁移为 `0028_cms_notifications.sql`；启动日志显示数据库无需新增迁移、10 个工作室重新生成；生产媒体覆盖为 `29` 个图片资源，medium/display/thumb 缺失均为 `0`；当前应用日志错误关键词计数为 `0`。 |
| Public edge | `https://pwestudio.online` deep health 与 `/platform-admin`、`/super-admin`、根站、中文站、手册、展示租户门户/报名/CMS/Studio Admin、双语 Release Notes/FAQ 均返回 `200`；HTTP → HTTPS 为 `301`，HTTPS TLS 校验为 `0`、HTTP/2；Platform Admin 版本化 asset hash 与本地一致，缓存头为 immutable；代表性公开媒体请求支持 ETag，`If-None-Match` 返回 `304`。 |
| Browser | 公网应用内 Browser 已打开 `/platform-admin#overview`，确认生产双语登录壳和未登录边界；未使用生产凭据、未执行生产写操作；浏览器控制台错误数为 `0`。本地验收仍覆盖桌面三栏、Needs attention、Tenant/Plan/Audit Inspector、移动端 Inspector 抽屉、无横向溢出和 Support Mode 空 reason 字段级拦截。 |
| Local gates | 完整门禁 `All checks passed`；CMS smoke `73 passed, 0 failed`；租户隔离 `237 passed, 0 failed`；Platform Admin/UI 定向门禁 `146 passed, 1 skipped`；`node backend/scripts/check_inline_scripts.mjs` 与 `git diff --check` 均通过。 |

未跟踪的 `docs/sales/` 路演资料已保留，未纳入提交或发布包。支付、银行转账设置、Gmail/SMTP、AWS SES、短信、SSE、WebSocket 和浏览器 Push 仍不在本版本。

## v9.8.0 本轮实际交付

- Platform Admin 采用顶部全局栏、左侧工作区导航、中间工作区、右侧 Inspector；保持 Studio Admin 的工作台关系，但只保留当前真实能力。
- Today 以 Needs attention 为入口，使用现有租户、订阅、试用日期和资源使用量数据，按优先级生成一条租户一条待处理记录；Attention 是 Today 内的快捷入口。
- Tenant Inspector 按状态 → 风险 → 订阅 → 资源使用 → 安全操作组织；Plan Inspector 和 Audit Event Inspector 复用同一右侧职责。
- Support Mode 在 Inspector 底部单独呈现，仍通过已有 reason 字段和审计流程进入，不改认证/RBAC，不新增支付、银行转账、Gmail/SMTP、SES、SSE、WebSocket 或 Push。
- 响应式行为：桌面保持三栏；中等宽度右侧转为抽屉；手机 Inspector 变为全屏工作表且无横向溢出。
- 未加入 Groups、Invitations、Announcements、System Health、Security、Settings 等尚不存在或尚未纳入本轮的一级导航。
- `past_due` 统一按订阅生命周期表达，不把它写成已接入在线支付后的“支付失败”。

## 当前实现前合同

```text
Today → Needs attention + business health + refresh evidence
Tenants → filters + list + tenant detail + Support Mode context
Plans & Pricing → catalog + limits + publication state (no gateway)
Audit Logs → search + pagination + governance detail
```

执行顺序：完成实现与浏览器验收，跑完整门禁，提交候选，生成干净 SaaS/Edition 包，推送分支，经预部署检查后部署，完成公网验收，再以文档闭环提交 handoff。

---

# PWE Studio v9.6.1 — Studio Admin 执行 handoff

> 状态：历史版本交接记录；当前 Platform Admin 交接入口见文件顶部。版本：`9.6.1`。

## 当前事实

- 源码分支：`codex/v9.3.0-cms-information-architecture`；`VERSION` 已更新为 `9.6.1`；部署候选 commit：`e46a3e3f4a407e8b2ac34ce8e230165c37150ea1`。
- 文档闭环 commit：`cf5303c`（仅更新 handoff、Release Notes 和生产证据；未重新打包或重新部署）；生产仍运行上面的部署候选 commit。
- 当前生产：`https://pwestudio.online`；`/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.6.1`，运行镜像为 `studiosaas:9.6.1`。
- Studio Admin 负责品牌、官网、报名入口、公开课表、草稿、预览与发布；CMS 负责日常运营。
- 家长话术不迁移数据、不新建发送系统，仍保留在 Studio Admin，入口归入「招生入口」子菜单；CMS 继续复制使用。
- 支付、银行转账信息、Gmail/SMTP、AWS SES、短信、SSE、WebSocket、浏览器 Push 均不在本版本。

## 已执行的交付队列

### P0：功能可信度

补齐时区、公开课表、家长话术等字段的 dirty tracking；修复 Registration 快捷入口；补齐课表中英文映射；保留 sticky 保存条安全空间；统一 `?view=` 深链、首次载入与前进/后退行为。

### P1：信息架构与发布中心

用四组工作流替代十个平铺标签：

```text
品牌与官网：品牌基础 / 首屏与行动按钮 / 官网版块 / 工作室作品 / 常见问答
招生入口：报名表 / 公开课表 / 家长话术
发布中心：草稿预览与发布 / 历史版本 / 页面健康
经营洞察：官网数据分析
```

预览明确标为私有草稿；保存条区分未保存、草稿未公开和已发布状态；桌面工作台使用可用宽度，编辑区/预览区维持约 `1.618:1`，平板在拥挤前堆叠预览，移动端改为单列且不依赖横向滚动。预览默认跟随后台语言，但保留独立的中英文对照按钮。

### P2：交接与回归

同步 Studio Admin、Owner 手册、在线用户手册文字与截图、手册截图脚本、Release Notes、版本号和生成资产；完成中英文/桌面移动/键盘/权限/租户隔离/打包/部署验收。`docs/sales/` 既有未跟踪路演资料保留且不纳入提交与发布包。

## 交接验收标准

- `?view=register`、`?view=messages`、`?view=advanced` 能直接打开对应工作区。
- 家长话术继续读取旧 `messageTemplates` 数据并进入现有发布载荷；没有第二个编辑器或发送服务。
- 草稿、预览、已发布官网三者文案不混淆；发布失败有明确恢复路径。
- 本地、双模式发布包和生产 `APP_VERSION` / `BUILD_INFO` / deep health 均为 `9.6.1`。

## 发布与验证证据

- SaaS 包：`dist/PWE-StudioSaaS-aws-9.6.1.tar.gz`；SHA-256：`f1465b393fefb83e962bac41402fff150430c3fcd3e9b7252911d985840aabb4`。
- Edition 包：`dist/PWE-Studio-Edition-9.6.1.tar.gz`；SHA-256：`3d881f7e3324b5acacc4aa89feadd23a278e5cd2cc412f0474d6c13b8deb7e0e`。
- 两个包的 `BUILD_INFO` 均为 `version=9.6.1`、部署候选 commit `e46a3e3f4a407e8b2ac34ce8e230165c37150ea1`，模式分别为 `saas` / `standalone`，构建时间为 `2026-08-10T01:16:13Z`。
- 本次部署前备份：`studiosaas_studiosaas_20260810T011745Z.dump`、`pwestudio-volumes-20260810T011746Z.tar.gz`；逻辑备份 manifest 同时生成。
- 公网 deep health：`appVersion=9.6.1`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；容器 healthy，磁盘可用约 `47.01 GB`。
- 公网 `/`、`/zh/`、`/zh/manual/`、展示租户门户、报名页、CMS、Studio Admin、双语 Release Notes 和中英文 Studio Admin 截图资源均返回 `200`；HTTP → HTTPS 为 `301`，TLS 校验为 `0`，HTTP/2。
- 本地完整门禁：`1945 passed, 8 skipped`；CMS smoke：`73 passed, 0 failed`；租户隔离：`237 passed, 0 failed`；生产部署后最近 5 分钟 app/db 错误关键词计数均为 `0`。
- 浏览器验收覆盖 Studio Admin 2000px 桌面、1024px 平板和 390px 移动布局：宽屏无大块空白，编辑/预览约 `1.618:1`，平板提前堆叠，移动端无横向溢出；后台语言会同步初始预览语言，手动切换后保持独立对照。公网手册为 `zh-Hans`，Studio Admin 未登录入口无控制台错误。

---

# PWE Studio v9.5.0 — CMS 信息架构最终交付（2026-08-09）

## 当前发布状态

- 版本：`9.5.0`。
- 分支：`codex/v9.3.0-cms-information-architecture`；源码、发布包与生产状态
  分开记录；已同步到 `origin/codex/v9.3.0-cms-information-architecture`。
- 部署代码 commit：`9a976215bab9d5b32b9792f36851078a4111ff4b`。
- 当前生产：`/opt/pwestudio/current` 指向
  `PWE-StudioSaaS-aws-9.5.0`，运行镜像为 `studiosaas:9.5.0`。

## 本轮实际交付

1. CMS 外壳改为稳定的顶部工具栏、分组左侧导航和按角色过滤的工作台；导航按「今日」、
   「教学运营」、「经营」、「记录」组织，系统设置成为完整页面。
2. 课程、作品、学员、待处理事项以及充值与退款各自拥有明确的功能工作区；课程和设置
   可通过 `?view=` / `?section=` 深链直接打开，通知点击也可以落到对应处理入口。
3. 表单补齐可读标签、帮助文案和 44px 操作目标；保留 PWE Brand 颜色、字体、黄金分割
   的 rail/content 比例与现有权限边界，Studio Admin 和公开门户仍是独立表面。
4. CMS 通知仍采用已批准的第一阶段方案：持久化记录、30 秒定时刷新、回到前台时刷新和
   弹窗提示。支付、银行转账展示、Gmail/SMTP、AWS SES、SMS、SSE、WebSocket 和浏览器
   Push 均未加入本轮。

## 验收与 handoff

- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh` 的完整门禁已通过
  （最终 release commit 前会再跑一次）。
- 全量 pytest：`1940 passed, 8 skipped`；租户隔离/权限：`237 passed, 0 failed`；
  独立 CMS smoke：`73 passed, 0 failed`。
- Chrome 使用 `lets-paint-showcase` 合成租户真登录验收了中英文桌面、移动排课、课程、
  作品、待处理、充值退款、设置深链和手册截图；没有读取客户数据。
- 截图工具、`manual.html` 引用和 `asset-manifest.json` 已同步，未跟踪的 `docs/sales/`
  路演资料保留在工作区且不纳入发布提交。

## 发布闭环与线上证据

- SaaS：`dist/PWE-StudioSaaS-aws-9.5.0.tar.gz`；SHA-256：
  `d9cd91c57467213ee81710d290b8a589c6910b4819568d136e2da9e59842802a`。
- Edition：`dist/PWE-Studio-Edition-9.5.0.tar.gz`；SHA-256：
  `90409a371521074252ceed90946198a5c4021319fcefb19fc55d665f74dfc97d`。
- 两个包的 `BUILD_INFO` 均为 `version=9.5.0`、commit
  `9a976215bab9d5b32b9792f36851078a4111ff4b`，分别为 `mode=saas` /
  `mode=standalone`；checksum、入口文件和内部/敏感路径排除检查通过。
- 部署控制器在切换前创建了逻辑备份
  `studiosaas_studiosaas_20260809T123630Z.dump`（约 481 KB）及卷归档
  `pwestudio-volumes-20260809T123632Z.tar.gz`（约 66 MB）。
- 内部与公网 deep health 均通过：`appVersion=9.5.0`、`db=ok`、`mode=saas`、
  `tenants=6`、`themes.unreadable=0`；当前 app/db 容器均 healthy，磁盘约 47 GB 可用。
- 生产 `schema_migrations` 最新为 `0028_cms_notifications.sql`；
  `backfill_media_variants.py --check` 返回 `Generated variants: 0`。
- `/`、`/zh/`、`/zh/manual/`、展示租户门户、报名页、CMS 和 Release Notes 均通过公网
  200；HTTP → HTTPS 为 `301`，HTTPS 为 `200`，TLS 校验为 `0`，HTTP/2。
- CMS shell 发出 `/assets/cms-app.js?v=9.5.0&h=e08ae1f2dc0dd4c9`；响应为一年
  `immutable`，公网响应 SHA-256 与本地发布提交中的 tracked bundle 均为
  `e08ae1f2dc0dd4c9634fb0228dcdcc06e3099465fcb0da568febd11f83e5f444`。
- 本地 Chrome 已使用合成 `lets-paint-showcase` 真登录验收中英文桌面/移动 CMS、课程、
  作品、待处理、充值退款、设置深链；公网关键路由完成 HTTP 验收。生产原始日志未拉回
  本地，以避免把潜在业务数据或凭据带出；因此日志正文不作为本次交付证据。

---

# PWE Studio v9.2.0 — 持久化 CMS 通知（2026-08-09）

## 当前发布状态

- 版本：`9.2.0`。
- 分支：`codex/v9.2.0-cms-notifications`，已同步到
  `origin/codex/v9.2.0-cms-notifications`。
- 部署代码 commit：`438e58275c9f1351fe5d57353a6112eb9df0cb24`。
- 当前生产：`/opt/pwestudio/current` 指向
  `PWE-StudioSaaS-aws-9.2.0`，运行镜像为 `studiosaas:9.2.0`。
- 本文件和 README 的最终发布记录会在部署验收后另提交；该闭环文档提交不改变
  已部署代码和发布包。

## 本轮实际交付

1. 公开报名成功和公开课表约课成功后，在同一数据库事务内生成租户隔离的 CMS
   持久化通知；重复提交不会重复生成通知。
2. 通知按用户保存已读状态，具备未读数量、列表、全部标记已读和逐条标记已读的
   API/UI 契约；约课通知只展示给具备约课审核权限的运营人员。
3. 第一阶段采用 30 秒定时刷新，并在浏览器重新可见时立即刷新；新通知通过
   CMS 弹窗提示。没有引入 SSE、WebSocket、浏览器 Push 或外部消息服务。
4. 本轮支付范围保持暂停：在线支付、银行转账设置、Gmail/SMTP、AWS SES 和短信
   均未实现。

## Git 与发布包

- SaaS：`dist/PWE-StudioSaaS-aws-9.2.0.tar.gz`；SHA-256：
  `627b593d1ad9bfe8a0b59b1c52017893d6dcea8c28a6363fdd48219695bcc3a0`。
- Edition：`dist/PWE-Studio-Edition-9.2.0.tar.gz`；SHA-256：
  `f4609d7a979450737aa7908780cf625cdc2cd830c5b1483d77d1334376297ded`。
- 两个包的 `BUILD_INFO` 均为 `version=9.2.0`，分别为 `mode=saas` /
  `mode=standalone`，并指向部署 commit；checksum、入口文件、模式和内部/敏感
  路径排除检查通过。
- 构建时临时隔离并原位恢复了既有未跟踪的 `docs/sales/` 资料；它们没有进入
  commit 或任何发布包。

## 本地 release gate

- 全量 pytest：`1940 passed, 8 skipped`。
- PostgreSQL 租户隔离/权限：`237 passed, 0 failed`。
- 独立 CMS smoke：`73 passed, 0 failed`。
- 本地 migration `0028_cms_notifications.sql` 已应用并通过当前检查；CMS source、
  tracked bundle 与 asset manifest 一致，JS、inline script、shell、术语和
  whitespace 检查均通过。

## AWS 与线上验收

- 部署前生产为健康的 `9.1.1`；控制器在切换前创建了新的逻辑备份
  `studiosaas_studiosaas_20260809T085116Z.dump`（约 474 KB）及卷归档
  `pwestudio-volumes-20260809T085117Z.tar.gz`（约 66 MB）。
- 当前 release 标识来自生产 `BUILD_INFO`：
  `version=9.2.0`、`mode=saas`、`commit=438e58275c9f1351fe5d57353a6112eb9df0cb24`。
- 内部与公网 deep health 均通过：`appVersion=9.2.0`、`db=ok`、
  `mode=saas`、`tenants=6`、`themes.unreadable=0`；公网 HTTP → HTTPS 为
  `301`，HTTPS 为 `200`，TLS 校验为 `0`，HTTP/2。
- 生产 `schema_migrations` 最新为 `0028_cms_notifications.sql`；只读查询确认
  `cms_notifications` 与 `cms_notification_reads` 均存在。
- `/`、`/zh/manual/`、Studio 门户、快速报名、公开课表、CMS 和 Release Notes
  均返回 `200`。
- CMS shell 发出
  `/assets/cms-app.js?v=9.2.0&h=a4207ecb33f6d2d4`；响应为一年
  `immutable`，线上正文 SHA-256 与本地 tracked bundle 均为
  `a4207ecb33f6d2d4b3a51459ad4f6547b5fd42769402a077b541657228158237`。
- 当前应用与数据库容器均 `healthy`，重启次数为 `0`；部署后最近 30 秒在服务器
  端汇总的 app/db 错误关键词和 db fatal/panic 计数均为 `0`。没有把原始生产日志
  拉回本地。
- 两个公开图库当前均为空，因而没有真实生产 JPEG 可用于本轮 `ETag`/`304` 样本
  验收；这属于无样本记录，不是媒体回归失败。
- 部署控制器保留前一版本作为回滚点，并在健康门禁通过后清理过旧 release/image
  产物；未删除生产数据库或持久化卷。

---

# PWE Studio v9.1.1 — 课程安排体验完善（2026-08-09）

## 当前发布状态

- 版本：`9.1.1`。
- 分支：`codex/v9.1.1-course-schedule-polish`，已同步到 `origin`。
- 当前状态：已打包、推送、部署并通过内部、公网、迁移、媒体与缓存验收。
- 生产运行的应用包来自 commit
  `4a048f1eecfaf7996d583e0e17358916e4a77f41`；其后的提交只记录发布结果。

## 本轮实际交付

1. 中文「每日排课」统一改为「课程安排」，英文统一为 `Class Schedule`；桌面和
   移动端导航、设置、手册、日历导出及截图契约同步更新。
2. 规划卡片按日期、周导航、出勤摘要、时段、添加学员、批量排课的任务顺序重排；
   桌面保持紧凑一行学员操作，移动端按任务自然换行且没有横向溢出。
3. 更多菜单新增学员、日期、时间、余额上下文，并把课程状态、提醒、`oneToOne`、
   撤销签到和移除排课分区呈现；固定课表来源明确提示应去固定课表调整。
4. PATCH 排课状态只接受 `scheduled` / `makeup`，拒绝无效状态和已取消记录，
   同时把状态变更写入审计元数据，避免界面能力绕过原有取消/恢复契约。
5. 浏览器截图脚本加入课程安排布局契约，持续检查页面命名、区块顺序、桌面/移动
   行布局、更多菜单上下文和横向溢出。

## CMS 真实浏览器验收

本地 PostgreSQL、合成展示租户、真登录和 Chrome：

- 桌面中英文排课页重新拍摄为 `1600 × 1000`；
- 移动中英文排课页按 `390 × 844` 视口拍摄为 2× 图 `780 × 1688`；
- 日期、周导航、摘要、时段、添加学员和批量区按任务顺序排列，无页面横向溢出；
- 44px 触控目标、紧凑桌面行、移动任务流、更多菜单和底部导航均进入真实浏览器；
- 截图只使用受保护的 `lets-paint-showcase` 合成数据，没有读取客户数据。

## 发布闭环

### Git 与发布包

- 分支：`codex/v9.1.1-course-schedule-polish`，已同步到 `origin`。
- 部署代码 commit：`4a048f1eecfaf7996d583e0e17358916e4a77f41`。
- SaaS：`dist/PWE-StudioSaaS-aws-9.1.1.tar.gz`；
  SHA-256：`a584518edcd6dbe81edede14f0b16fe5163308f9291f152996cd85b5d3db710d`。
- Edition：`dist/PWE-Studio-Edition-9.1.1.tar.gz`；
  SHA-256：`eb9db1a5abaf60d22da31c649f0148df4bed7cbb0b4725bcfca3cc0c3033ad45`。
- 两个包均通过 checksum、`BUILD_INFO`、入口文件、模式和敏感/内部路径排除检查。

### 本地 release gate

- 默认 pytest：`1934 passed, 7 skipped`；
- PostgreSQL 租户隔离/权限：`237 passed, 0 failed`；
- 独立 CMS smoke：`73 passed, 0 failed`；
- 课程安排/API 定向回归：`139 passed, 1 skipped`；
- migration `0027_medium_media_variant.sql` 与本地 86 个缺失中图完成回填，复核为 0；
- CMS source、tracked bundle 与 asset manifest 一致；JS、inline script、shell
  语法、术语和 Git whitespace 检查均通过。

### AWS 与线上验收

- 部署前生产为健康的 `9.1.0`；v9.1.1 一次部署成功，未触发回滚。
- 成功部署前备份：`studiosaas_studiosaas_20260809T044226Z.dump`（约 473 KB）及
  `pwestudio-volumes-20260809T044227Z.tar.gz`（约 66 MB）。
- `/opt/pwestudio/current` 指向 `PWE-StudioSaaS-aws-9.1.1`；当前容器
  `studiosaas:9.1.1`，应用与 PostgreSQL 均 healthy。
- 内部和公网 deep health：`appVersion=9.1.1`、`mode=saas`、`db=ok`、
  `tenants=6`、`themes.unreadable=0`；公网 HTTP → HTTPS 301、TLS 校验 `0`、
  HTTP/2。
- 最新 migration 为 `0027_medium_media_variant.sql`；生产共有 29 个 medium
  变体，`images_missing_medium=0`。
- `/`、中文手册、Studio 门户、公开课表、CMS 和 Release Notes 均返回最终 200。
- CMS 发出 `/assets/cms-app.js?v=9.1.1&h=0adf0808c802f2f3`，响应为一年
  immutable；线上与本地 bundle SHA-256 均为
  `0adf0808c802f2f320a07c3d5456c06be65125e85e48b41fecddb38f23ebd1c5`。
- 生产 medium JPEG 返回 checksum ETag；携带 `If-None-Match` 时返回 304。
- 当前应用日志显示 migration 最新、媒体回填 0 缺失、10 个 workspace 重建和
  Waitress 正常启动，无新异常。
- 回滚点保留为前一版本 `PWE-StudioSaaS-aws-9.1.0`。

---

# 📖 手册审计 · 只出方案未改内容（2026-08-08，对照 v8.10.3）

全文见 `docs/design/Manual_Improvement_Plan.md`。**这一轮只盘点、没改手册内容。**

## 盘的是两层，不是一份

- **线上手册** `/zh/manual`（`manual.html`，752 行中英同页 + 11 组截图 × 2 语言）
  —— 客户看的那一份，也是搜索引擎和 AI 抓的那一份。
- **角色手册** `docs/guides/*.md`（7 本）—— 线上手册的**素材层**。

两边不同步时**先错的一定是线上手册**，因为它是唯一一份客户会主动去读的。

## 一句话结论

**线上手册描述的产品，有三块是不存在的，有两块是客户正在付钱买、却查不到的。**

## P0（三条）

1. **配色说法已作废 —— 唯一一处「主动说错」。** 手册写「系统共八套主题」，
   而 v8.5.x 起真正的模型是**一套配色 + 自由强调色（可从 Logo 取色）**，
   八张卡是**起点不是全集**。`自定义` / `取色` / `Logo` 在手册里出现 **0 次**。
   > 其余问题是「查不到」，这一条是「查到了，是错的」——
   > 一个老板会以为自己只能在八张卡里选，而「用我自己的品牌色」
   > 恰恰是他最想做的第一件事。
2. **公开课表 + 免注册约课完全没写**（v8.9.0 / v8.10.0）。手册有一整章
   「家长这一侧」，而这是 v8.5 之后**唯一一个家长会直接接触**的新功能。
3. **工作室作品完全没写**（v8.6.0 / v8.7.0）。**定价页正在按它卖钱**
   （15 / 60 / 150 件），手册里这个功能不存在。

## P1 / P2 / P3

- **P1**：排课章节缺关联课程/老师/地点/公开开关/停课；团队章节缺老师署名开关；
  官网章节缺空间介绍；全书缺「课程」这个对象；FAQ 缺三个必被问到的问题。
- **P2 截图**：`02-portal`（导航多了「课程安排」）和 `02-pending`（现在两个标签）
  **画面与文字已对不上**；另缺 4 组新截图。
  **必须走 `capture_manual_shots.py`，不要手工截** —— 手工那一步就是下次被跳过的
  那一步，这套脚本存在的理由就是它。
  深色变亮**不影响截图**：手册已写明统一用浅色，那句话仍然成立。
- **P3 角色手册**：总览 README 八个特性覆盖 **0**；Owner 缺课程管理；
  Teacher 缺余位/候补；Super Admin 缺 `showcase_limit`。

## ⚠️ 一个要拍板的设计问题（文档解决不了）

**前台能看见约课申请，但批不了。**
`review_class_booking` 是 `@tenant_admin_required`（仅 Owner/Manager），
而前台有 `registrations:write`（**能批报名**）。
处理来客咨询的正是前台，约课就是来客咨询的一种，他却只能看不能动。

我倾向**给前台批约课的权限**，与他已有的「批报名」对齐 ——
两件事在前台眼里是同一件事。**这一条不定，前台手册没法写准。**

## 建议顺序

四个批次约 14 小时，可拆两次发布。**先做批次一**（P0 三条，约 6h）：
理由不是工作量，而是 P0-1 是唯一一处会让人**做错决定**的地方，
P0-2 / P0-3 是**客户正在付钱却查不到**的两块。

## 一条机制上的欠账

`docs/guides/` 曾在 v8.1.0 停了九个版本 —— 这件事写在
`capture_manual_shots.py` 的注释里，也是那套自动截图存在的原因。
现在**版本号是自动断言的**（`test_user_guides.py` 逼着每次发布都改），
**但内容没有任何东西在盯**。这一轮的欠账正是这么来的：
版本号一路涨到 v8.10.3，内容停在 v8.5。

值得考虑：**新增 `website_profile` 的 `show_*` 开关时，线上手册里必须出现它的
名字** —— 和 `test_section_switches.py` 拦住「孤儿开关」是同一种做法，
那条测试已经证明有效。

---

# 🔧 v8.10.3 — 一个下拉框指向了谁也填不了的列表（2026-08-08）

Owner 报的两件事，都是真的。

## 1. 授课老师下拉要先打开一次「设置」才有内容

`loadTeam()` 的**唯一调用者是设置弹窗**（`useEffect([showSettings])`）。
排课编辑器的「授课老师」也依赖 `team`，于是没开过设置就是空的 ——
**东西没坏，是数据根本还没取**。但对使用者来说，一个空的下拉和一个坏的
下拉没有区别。

**一个被两块界面依赖的列表，不能由其中一块负责加载。** 现在登录后即加载，
设置弹窗打开时再刷新一次。

## 2. 「关联课程」下拉里永远只有「不关联课程」

**这是我的疏漏。** `courses` 表和它完整的 CRUD 从 A1 就有，v8.8.0 我给排课
加了「关联课程」下拉 —— 但**从来没有人建过课程的界面**，我也没查。
一个指向谁也写不了的列表的控件，不是「功能不全」，它读起来就是「坏了」。

新增「设置 → 课程管理」：名称、简介、适龄段、时长、价格（后四项选填）。

- **移除是归档不是删除**：已经关联它的班次、按它记过的账都还在引用它。
  确认框会告诉你**目前有几个班次正在用它**，并说明那些班次不受影响。
- **从需要它的地方通向它**：排课编辑器的下拉旁边有链接 ——
  没有课程时写「去添加课程 →」，有课程时写「管理课程」，点了直接打开设置
  并滚到那一块。没有这一行，空下拉只会让人以为坏了。

## 验证方式（这次做对了）

起本地 Postgres + 真登录，在浏览器里走完整条路：
未开过设置 → 老师下拉已有三个人 → 点「去添加课程 →」→ 建课程 →
回排课编辑器 → 下拉里出现「儿童油画基础」，提示语变成「管理课程」。
控制台只有一条 401（登录前的 owner-only 审计接口，符合预期）。

**`.claude/launch.json` 这次是追加一个配置、验证完删掉**，
不是覆盖 —— 上一版我覆盖了你的配置，已经还原。

---

# 🔴 v8.10.1 — 一个未定义的名字，让 Studio Admin 看起来坏了四种样子（2026-08-08）

**v8.10.0 的回归，Owner 报障后 30 分钟内修复。**

## 症状（Owner 看到的）

- `Can't find variable: TENANT_SLUG` / 「载入失败：Studio Admin」
- 配色不对、主题消失、选不中
- 发布前的对比度警告：**Body text on page 1.0:1**（最低 4.5:1）

## 病因（一行）

```js
$('timetableUrlHint').textContent = `/${TENANT_SLUG}/timetable`;   // ← 不存在
```

`TENANT_SLUG` 是 **tenant-template 的约定**：index / register / timetable
由服务端按租户渲染，把字面量替换进去。**Studio Admin 是一个静态文件服务所有
租户**，slug 从表单读，函数叫 `currentTenantSlug()`。我把一个文件的习惯抄进了
另一个文件。

## 为什么一行会变成四种故障

**ReferenceError 不会在页面上显示成一个错误，它会中止所在函数的剩余部分。**
那一行正好落在「把租户设置应用到表单」的中间，于是**它之后的每一条语句都没
执行**：配色没应用、主题选择器没填充、作品板块没渲染。

对比度报 1.0:1 不是配色算错了 —— 是**根本没有配色**，检查器量的是没上色的
默认值。四个看起来毫不相干的故障，同一个原因。

## 防线

`test_studio_admin_never_borrows_the_tenant_template_globals`：
Studio Admin 的内联脚本里不许出现 `TENANT_SLUG` / `TENANT_NAME`。

**没有写「禁止一切未声明全局变量」的通用检查**，虽然那才是长期正解。
第一版写出来有四个误报（模板字符串、SVG 标记、散文都能造出像样的假阳性），
而**一个会被误报、然后靠加白名单绕过的检查，比没有检查更糟** ——
它教会所有人往白名单里加名字。这一条留作待办。

## 这次真正的教训

`docs/guides/*` 的 v8.10.0 那一版我做了 35 条断言、还起了真 Postgres 走了
整条约课链路 —— **但没有在浏览器里打开过一次 Studio Admin**。
真库验证覆盖了服务端，浏览器侧一行 JS 的引用错误在它的盲区里。

**下次改这三个静态页面（studio-admin / super-admin / legacy-root）中的任何
一个，发布前必须真的打开它一次。** 没有捷径：这些文件不编译、不进测试运行时。

---

# PWE Studio v8.10.0 — 课表有了自己的一页，位置可以不注册就申请（2026-08-08）

v8.9.0 + v8.10.0 一次发。方案见 `docs/design/Public_Timetable_And_Booking.md`，
两个待定问题按你的决定落地（提前天数 = 展示周数；重复提交返回「已经收到了」）。

## A — 课表是**独立页面**，不是首页上的又一个板块

`tenant-template/timetable.html`，路由 `/<slug>/timetable`，
门户导航按 `show_timetable` 出入口。

理由不是工程量，是**家长读课表时在拿一行行时间对着自己的日历比** ——
那需要宽度，也需要一个能单独转发给另一半的网址。首页板块两样都给不了。

**页面壳不设防，接口才设防。** 关掉开关时 `/timetable` **照常返回 200**，
由 `/v1/public/<slug>/timetable` 回 `enabled:false`，页面自己说「还没有公开
的课程安排」。壳如果也 404，等于**惩罚一个点了工作室上周自己发出去的链接
的人**。而且这比板块开关更强：数据根本没离开机房，不是「藏起来的 markup」。

## B — 顺手消掉一处真实的重复：`portal-brand.js`

主题 token 表**本来就有两份**（index.html 和 register.html 各一份内联），
而且**已经漂移了** —— 一份把 `accent_color` 映射到两个变量，另一份三个。
课表页本来要写第三份。

抽成 `/assets/portal-brand.js`，三个公开页面都用它。
测试也跟着改了形：原来的「三份要逐字段相等」变成
**「每个公开页面必须加载这个模块，且不许自己再声明一份」** ——
后者是前者想表达的东西，前者只是当时能写出来的近似。

CMS 保留自己那份：它是另一个应用、另一套变量词汇，不是公开面。

## C — 投影在服务端，按 `tenants.timezone`

规则说「每周三」，访客要的是日期。转换这件事**必须在服务端做**：
`new Date('2026-08-12')` 是 UTC 午夜，在墨尔本是 11 号晚上。
**这个产品在日期上栽过一次（RFC 1123 vs ISO），不给第二次机会。**
页面里连一个 `new Date(` 都没有（有断言盯着），日期一律当文本切开。

**内部 uuid 不出公开接口**，对外用「日期 + 开始时间」定位。
放出去就成了一个我们再也不能重建那行记录的承诺。

## D — 显示开关：一个结构对象，三条规则

`website_profile.timetable_fields`（teacher / room / age_range / duration /
capacity / price）。

1. **缺的键取推荐默认，不是 false。**「没提到」和「关掉了」是两个答案，
   把前者读成后者，会在这个对象加字段的那天把所有租户的课表清空。
2. **渲染是一个循环。** 所以 64 种组合是**一种版式的 64 个子集**，
   不是 64 种版式 —— 这正是上一轮担心的东西，用数据结构消掉了。
3. **开关是上限、内容是下限，取交集。** 开着但没填地点 → 不出现空的「地点」。

**老师那一项是 AND**：字段开关开着 **且** 这位老师本人勾了同意。
个人同意不是版式偏好，它压过版式偏好。

## E — 余位芯片

绿「还有 N 位」/ 琥珀「快满了 · 还有 N 位」/ **灰「已满 · 可加候补」**。

- **必须带文字**（WCAG 1.4.1）：色觉障碍、黑白打印、读屏都要读得出三种状态。
- **满了用灰不用红**：卖完是成绩不是故障；红色留给真的出错的场合。
- **阈值按比例**：`快满 = 剩余 ≤ max(1, ⌈容量×25%⌉)`。容量从 1 到 30 都有，
  绝对阈值两头都错。
- 不做实心填充；一屏那一个饱和填充留给「预约」按钮。

## F — 免注册约课（`class_bookings`，迁移 0026）

**三条决定，全都是关于「回应说什么」，不是关于「存什么」：**

**1. 回应不能泄露这个号码是不是学员。** 服务端确实拿姓名+手机去比对
（CMS 需要知道），但**返回给页面的内容逐字节相同**。否则这个表单就变成
「这个人是不是你们的学员」的查询接口 —— 换个号码看回应有没有差别就行。
断言直接检查 return 体里不许出现 student/lookup/matched 之类的键。

**2. 待确认的申请不占座。** 容量在**批准那一刻**才复核。
一个还没人看过的申请不该挡住一个真会来的家庭，而且提交时的算术到批准时
早就过期了。

**3. 但如实告诉家长排在哪。** 回应带「还剩几位」和「已有几份在等」。
一个写着「还有 1 位」却安静收下五份申请的班，会让四个人失望。

**提前天数 = `timetable_weeks`**，不设第二个配置：
**课表上看不到的日期，本来就没有「约」这个动作可言**；两个数字迟早不一致，
而发现不一致的一定是家长。

**重复提交**：`(schedule_id, on_date, contact_phone) WHERE status='pending'`
上一条**部分唯一索引**，`ON CONFLICT DO NOTHING`，返回 `duplicate:true` +
「已经收到了，请等待」。放在数据库而不是 check-then-insert，是因为
**两次同时提交时那句话才真的成立**。这不是错误提示：家长重复点通常是
不确定第一次成没成功，**该给的是确认，不是拒绝**。

## G — 为什么不塞进 `registrations`

新家长约体验课（批准后**建学员**）和老学员约某节课（批准后**占座位**）
是两件事。混在一起会让「本月新报名」永远虚高 ——
**而那是工作室判断投放有没有效果的数字。一个被污染的经营指标比没有更糟，
因为它仍然被相信。**

CMS 里**仍然只有一个收件箱**：「待审核」分两个标签、计数分开写、
导航角标是两者之和（它回答的是「有没有事等我处理」这一个问题）。

批准后：命中老学员 → `daily_roster_entries`（`source='booking'`）；
未命中 → 建一条 `registration`（`source='class_booking'`）并回填 id。

## H — 静态测试抓不到的那个 bug

**`find_student()` 返回的状态字符串是 `"matched"`，我写的是 `"found"`。**

什么都没报错：那个比较**永远不成立**，于是每一条申请 —— 包括来自一个
读了三年的家庭 —— 都被当成全新报名。这个文件里所有静态断言照样通过，
因为代码形状是对的，只有常量是错的。

**是在本地起了一个真 Postgres、把 0001→0026 全跑一遍、再走完整条链路
才发现的。** 现在钉在测试里（并且断言那个常量是 `StudentLookup` 真能产生的值）。

线上验证记录（本地真库）：
- 六个迁移文件全部干净应用，含 0025 / 0026;
- `/timetable` 200，按墨尔本时区投影到 2026-08-11，老师显示为对外名
  「Lucy 老师」，`seatsLeft 3/3`;
- 同一号码两次提交 → 第二次 `duplicate:true`，**库里只有一行**;
- 命中学员与未命中学员的回应 **键完全相同**，库里 `matched` 分别是 True/False;
- 批准老学员 → `daily_roster_entries(source='booking')`，**没有建 registration**;
- 批准新访客 → `registrations(source='class_booking')` + 回填;
- 容量 3：第三次批准成功，第四、五次 **409「这节课已满」**;
- 满员后仍可提交（候补），芯片 `seatsLeft 0`。

## 测试

`backend/tests/test_public_timetable.py`（35 条）+ 改写的
`test_portal_theme_contract.py` / `test_dark_framework.py` /
`test_section_switches.py`（新增 `PAGE_SWITCHES`：页面级开关**由服务端拒绝**，
不是靠藏链接）。**1557 passed, 7 skipped.**

## 发布证据（2026-08-13）

| 层级 | 已验证事实 |
|---|---|
| Source | 发布提交 `e92dcadf89ab62b87681f14c5afa550b56c93abf`，分支 `claude/online-manual-content-improvement-03b8f9`；`VERSION=9.9.6`。门禁全绿：`verify_local.sh` 全部通过、pytest `1755 passed, 12 skipped`、legacy CMS smoke `73 passed`、租户隔离 `237 passed, 0 failed`。 |
| Package | SaaS `PWE-StudioSaaS-aws-9.9.6.tar.gz` SHA-256 `ce2672d4a739583e00bc92d20b903bdb12e62fd1f8c0000539934e35c2388ce8`；Edition `PWE-Studio-Edition-9.9.6.tar.gz` SHA-256 `c766d654a30ac1a3c30af90de3a3c6c4c31723cf6464799b3682e1be28269665`。两个包的 `BUILD_INFO` 均为 9.9.6，模式 `saas` / `standalone`，均通过发布包校验。 |
| Backup | 部署前逻辑库备份 `studiosaas_studiosaas_20260813T101614Z.dump`，manifest 同时存在。 |
| Production | `/opt/pwestudio/current` → `PWE-StudioSaaS-aws-9.9.6`，镜像 `studiosaas:9.9.6`，容器 healthy；内网与公网 deep health 均为 `appVersion=9.9.6`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`、`workspaces.stale=0`；磁盘可用约 `44.74 GB`。 |
| Public routes | 根站、中英文手册、pricing、Release Notes、租户门户 / timetable / showcase / register / CMS / Studio Admin、platform-admin 共 12 条全部 `200`（HTTP/2）。 |
| Assets | 四组代表性手册截图的线上字节与本地 SHA-256 逐一相同（`01-brand-workbench`、`02-showcase-page`、`04-booking`、`07-settings`）；带 `h` 的 URL 返回 immutable，条件请求返回 `304`。 |
| Content | 线上手册中英文都已是改正后的那句（「它并非永远不能改」/「It is not permanent」）；`FAQPage` 结构化数据 13 条问答，含新增的网址更换那条；`dateModified=2026-08-13`。 |

## 待办 / 已知

- **约课不发通知邮件**（v1 有意）。CMS 工作台「今日待办」会显示待处理数，
  跟报名一致。邮件是另一条链路，等有人要再说。
- **没有自助取消/改期入口**。家长要改打电话；这一版先把「能约上」做对。
- 线上目前 4 条 class_schedules 全部 `is_public=false`，
  所以**部署后公网依然什么都不变**，直到工作室自己勾选并打开开关。

---

# PWE Studio v8.8.0 — the dark page stops being a void, and a class learns who teaches it (2026-08-07)

方案见 `docs/design/Public_Timetable_And_Booking.md`，决定见本文下一节。
**这一版对公网零影响**：字段和后台先落地，门户板块在 v8.9.0。
先发它的理由不只是风险小 —— **真实数据先长出来，下一版就有真东西验收版式**。

## A — 深色变亮：不是改一个数，是让求解器重新解一遍

纸的 HSL 亮度从 `.068` 提到 `.118`。九套主题的页面感知明度 **L\* 从 4.6–7.3
升到 9.7–15.1**。参照物：Material 的深色基准 `#121212` 是 L\* 5.5 ——
**这个产品此前坐在「任何人推荐的最暗值」之下**，有几套比它更接近纯黑。
「过暗」是准确的测量结果，不是口味。

改完自动倒下三处，每一处都是真问题：

**① 强调色只解了一个面。** `accent` 一直只对着 `on_dark`（按钮上的深色字）
解到 7.6，它作为**面板上的链接**从来没被解过 —— 页面够暗的时候碰巧达标。
纸一抬就不是巧合了：arcade-lime 掉到 **4.37:1**，低于链接需要的 4.5。
现在两个面都解，取更亮的那个（两个约束同向）。

**② 状态芯片的彩度下限是个绝对值。** 22 / 32 够用，是因为它们要盖过的是
一张近白纸（彩度 ~5）和一张近黑纸（~8）。HSL 里彩度随亮度长 ——
arcade-lime 的深色纸从 8 长到 22，正好顶到下限，info 芯片解出来 23。
**比它所在的纸只多一个单位彩度的芯片不是芯片，是污渍。**
下限改成 `max(绝对值, 纸的彩度 + 10)`，用距离表达，以后改任何表面都跑不掉。

**③ 品牌芯片和状态芯片会撞。** 两者的区隔一直靠 1.52 与 1.22 这两个常数之
间的空隙，而**被抬过彩度的芯片会冲过自己的步长**（饱和度 1.0 的琥珀，无论
亮度都无法贴近一张蓝卡到 1.22），冲的方向正好朝着强调色。所以品牌芯片改成
**最后构建、需要多深就多深**，每次加 0.02 直到与四个状态芯片都拉开。
原来的断言留着当兜底。

浅色模式 **0 个 token 变化**，深色 314 个。生成物同步重出：`presets.py`、
`solver.js`（手写的 JS 镜像，逐行对照）、`lab.html`、`Design_System.md`、
CMS 那套手写深色回退（`legacy-root/index.html`）。

**新增两条断言**（`test_dark_framework.py`）：纸的 L\* 必须落在 **9–18**，
以及页 < 带 < 卡的次序不许再被打破（v8.3.0 修过一次的那个）。
对比度断言说不出「这页是不是纯黑」—— 一张纯黑的页面能通过全部对比度检查。

## B — 排课的字段（迁移 0025）

| 加在哪 | 列 | 默认 | 为什么 |
|---|---|---|---|
| `class_schedules` | `teacher_user_id` | NULL | **ON DELETE SET NULL 不是 CASCADE**：老师离职不能删掉他带过的班 |
| | `is_public` | **false** | 见下 |
| | `room` | `''` | 选填 |
| 新表 | `class_schedule_exceptions` | — | 停课，见下 |
| `memberships` | `public_display_name` | `''` | 对外可以叫「Lucy 老师」 |
| | `show_on_public_timetable` | **false** | 见下 |

**`is_public` 默认 false 不是保守，是必须。**「已经排的课」和「对外招生的
课」是两批，差集恰好是最敏感的那部分：一对一时段、内部补课、给某个家庭留的
试听位、只对老学员开的进阶班。默认 true 会在板块上线那一刻**追溯性地**把它
们全部公开 —— 为那些排课建立时根本没人被问过的安排。

**老师的名字要他本人同意，不是这节课同意。** 被排了一节课不等于同意把姓名
放到公开互联网上。开关按人、默认关，班次级的开关**压不过它**。
`teacherPublicName` 存在，是因为「公开法定姓名」的诚实替代不是「什么都不
公开」—— 很多老师对外就是用「Lucy 老师」。

**停课必须和字段同一版发。** `class_schedules` 说的是「每周三」，没有任何
方式说「这个周三不上」（`daily_roster_entries.status='cancelled'` 是**按
学员**的，答的是另一个问题）。少了它，公开课表就是一个**收不回的承诺**：
公众假期停业那周，网站照旧写着周三 16:00，家长开车穿城白跑一趟。
**一个改不了的课表比没有课表更糟。**
停课那天是**划掉并写原因**，不是让它消失 —— 消失看起来像网站坏了。

停课日期**必须落在这个班次实际上课的那一天**，否则服务端拒绝。写错周几的
停课会被存下来、看起来保存成功、而班次照常出现 —— 拒绝是 Owner 唯一能及时
发现的途径。

## C — 冲突判定：从「时间」改成「同一位老师」

CMS 原来的 `schedOverlap()` 只比 weekday + 时间。加了老师之后它同时
**太松**（同一位老师被排到两个同时段的班 —— 真冲突，不报）和
**太紧**（两位老师、两间教室、同一时间 —— 完全正常，每次都报）。
一间有两位老师的工作室，每排一节课都要点一次「仍要保存」，很快就学会无视 ——
**一个总是误报的警告等于没有警告。**

新规则 `schedClash()`：时间重叠 **且**（同一位老师 **或** 两边都没指定老师）。
两边都没老师时退回旧行为：无从判断，宁可提醒。

## D — 两个越权的口子，数据库拦不住

`_assert_schedule_references()`：课程和老师**都必须属于本租户**。
外键只证明这行存在于某处，不证明它是谁的 —— 没有这道检查，一个租户可以在
自己的班次上写另一家的课程和另一家的老师，等 v8.9.0 一上线就把那个名字发到
自己的公开页上。

`update_class_schedule` 的 **PATCH 从库里补齐四个新字段**。
`_schedule_payload_fields` 是从 payload 重建的 —— 不先合并存量，一次只想改
容量的编辑会顺手把班次取消公开、忘掉老师，而且不出声，因为两个新字段的默认
恰好是「关」和「无」。**这是 v8.5.4 那个坑（`payload-rebuild-erases-fields`）
换了一张表。**

`/team` PATCH 同理：**没发就是不变**。它同时也是「改角色」那个调用 ——
缺键读成 false 会让改一次角色就把某人的名字从公开课表撤下来，读成 true 会
把它放上去。两个都是没人做过的决定。

## E — CMS

- 班次编辑器：**关联课程**下拉（`course_id` 有列但 CMS 从没写过，所以每条
  班次只有一个前台随手打的 label —— 对内无所谓，对外不行，课程简介和适龄段
  都在 `courses` 里）、**授课老师**下拉（含 Owner ——
  很多工作室就是主理人自己在上课）、**地点**、**公开开关**。三项都是选填：
  内部工具上的必填字段只会被填成「-」。
- 班次卡片直接写**「● 已公开」/「○ 仅内部可见」**。没有这一行，回答
  「陌生人能看到哪些」只能逐个打开编辑器 —— 而这恰恰是最不该靠回忆的事。
- 勾了公开、但指定的老师没同意署名时，**当场提示**（照常发布，只是不带
  姓名）。总比 Owner 在线上页面才发现名字不见了强。
- 停课：卡片上一个「停课」按钮，默认日期已填好下一次上课日，可写原因，
  已停课的日期列在卡片上并可一键「恢复」。
- 团队管理：只对 manager / teacher 出现「可在公开课表显示姓名」+ 对外显示名。
  前台不会被排课，给他一个这样的开关只是多一个要理解的东西。

## F — 发布后核对时发现的一件事：**改生成器 ≠ 改线上**

每个租户**自己存着一份解好的 token**。改 `presets.py` 或改求解器，
**在那些副本被重写之前，租户看到的东西一点都不会变**。

这一版实际上不需要刷新（核对结果见下），但核对过程中发现现有的刷新工具
**今天跑会毁数据**：

- `migrate_visual_themes.py` 用 `style_theme(style_id, scheme)` 整体替换。
  v8.5.x 之后大多数租户坐在自由强调色上、各有各的 `accent_hue`，而这个参数
  **没有被传** —— 今天跑一次，五家工作室会被统一刷成默认强调色，还叫「迁移」。
- 新写的 `backend/scripts/refresh_stored_themes.py` 走**请求路径同一条解法**
  （带上租户自己的 `accent_hue`），并且**只替换 `*_color`**。
  第一次对生产 dry-run 就暴露了另一半问题：`style_theme()` 也返回
  `button_style` / `font_mood` / `style_id` 的**默认值**，整体 merge 会把
  六家里四家的 `button_style rounded→soft`、`font_mood classic→serif`
  改掉 —— **颜色是算出来的，可以重算；这三个是租户的答案。**
  两条不变量已加断言（`test_stored_theme_tolerance.py`）。

**生产核对结果：六个租户目前全部是浅色**
（`tenants.settings.visual_theme` 与已发布的 brand payload 都是 light，
`--scheme dark` 匹配 0 个）。所以深色变亮**当下对公网零影响**，
也没有需要刷新的存量 —— 唯一的差异是一个租户的 hex 大小写
（`#835d33` → `#835D33`），不值得为它写一次库。
以后有租户切到深色时，是在运行中的服务端重新解的，直接拿到新值。

## 测试

`backend/tests/test_timetable_fields.py`（20 条）+ `test_dark_framework.py`
新增 2 条 + `test_stored_theme_tolerance.py` 新增 2 条。
**1511 passed, 7 skipped.**

其中一条是编译产物新鲜度：浏览器跑的是 `cms-app.js`，不是 `.jsx`。
改了源码忘记 `backend/scripts/build_cms.sh`，上面每一条断言都会通过，
而 CMS 一点没变。

## 这一版**没有**做的（v8.9.0 再做，理由写清楚）

`website_profile` 上的三个字段 —— `show_timetable`、`timetable_weeks`、
`timetable_fields` —— **故意没加**，尽管它们属于「后台词条」。

因为 `_normalize_website_profile` **从 payload 单独重建**，不与存量合并。
往里加一个 studio-admin 不发送的键，等于**每次保存都把它清回默认**（v8.5.4
的七个字段就是这么丢的）。而要让 studio-admin 发送它，就得给它一个界面 ——
那就意味着在门户还不渲染课表的时候，先摆出一个「公开课表」开关。
**一个打开之后公网上什么都不会发生的开关，是对 Owner 说的一句假话。**

所以这三个字段和门户板块、和它们的界面，在 v8.9.0 同一次落地。间隔约 1.5 天。

## 下一步

- **v8.9.0**：公开课表接口（服务端按 `tenants.timezone` 投影）+ 门户板块 +
  余位芯片 + `timetable_fields` + 上面那三个字段的 studio-admin 界面。
- **v8.10.0**：免注册约课。两个待定问题**已定**，见下一节。

---

# 📐 v8.9.0 – v8.10.0 设计（已于 2026-08-08 全部实现，见最上方）

**这一节不是发布记录，是施工图。** 全文见
`docs/design/Public_Timetable_And_Booking.md`（前两轮 `Public_Timetable.md`、
`Public_Timetable_Round_2.md` 中被推翻的部分以定案文档为准）。

> **三个版本都已实现并发布**：v8.8.0（深色变亮 + 排课后台字段 + 停课表）、
> v8.9.0（公开课表接口 + 独立页面 + 余位芯片）、v8.10.0（免注册约课）。
> 这一节保留为**决定的来源**，不是待办清单。执行中改变的地方只有一处：
> 门户板块做成了**独立页面**（理由见最上方 §A），不是首页上的一个 section。

下面每一条都是**已经拍板的决定**，执行时不要重开。

## 已拍板

| 议题 | 决定 |
|---|---|
| 深色过暗 | 修。纸的 L\* 现在只有 7（`#15120D` / `#14120F` / `#121111`），接近纯黑 |
| 「已满」用什么色 | **灰**，不用红 |
| 门户字段显示 | **要留自由度**（不同机构要求不同，现在留比以后改好） |
| 停课表 | **做** |
| 免注册约课 | 做。姓名 + 手机号，不开账号 |
| CMS 首屏一瞬无色 | **搁置**（把可缓存的静态外壳变成按租户渲染，代价不值） |

## 调查结论：地基已经在了，别重造

- `class_schedules` 已存在且 CMS 已有「每周课表」界面：weekday / start_time /
  duration / **capacity** / course_id / is_active。`class_schedule_students`
  给出已报人数。**你要的四样里三样已有字段。**
- **`course_id` 有列但 CMS 建课表时从没写过** → 只有一个前台随手打的 label。
  对内无所谓，对外不行：公开课表要的描述和适龄段都在 `courses` 里。
- `services/student_access.py:find_student()` 已经在用**姓名+手机**认人，
  且规则严谨：单字名只匹配 first_name、**明确排除只用姓氏**、必须唯一命中、
  已按 IP 限流。**约课用这一条，不发明第二种身份。**
- `registrations` 已有完整审批链路（status / review_note / duplicate_of /
  assigned_user_id / campaign），CMS 已有「待审核」页。
- 线上只有 4 条 class_schedules、1 个租户在用——**改动面很小，现在做正是时候。**

## 三个必须记住的判断

**1. 约课不能塞进 `registrations`。** 新家长约体验课（批准后建学员）和老学员
约某节课（批准后占座位）是两件事。混在一起会让「本月新报名」永远虚高，
而那是工作室判断投放效果的数字——**一个被污染的经营指标比没有更糟**。
新开 `class_bookings` 表，CMS 里仍然只有一个收件箱，分两个标签、计数分开。

**2. 提交结果不能泄露这个手机号是不是学员。** 服务端会拿姓名+手机去匹配，
但**返回给页面的内容必须完全一样**，不论匹配与否。否则这个表单就成了查询
接口：换个号码看回应有没有差别，就能判断某人是不是这家的学员。
**这不是理论风险，是同一个表单的另一种用法。**

**3. 待确认的请求不占座；容量在「批准」那一刻才校验。** 提交时的判断到批准
时早就过期了。但要如实告诉家长「还有 1 个位置，已有 3 人在等待确认」——
诚实，并把选择权交回去。

## 设计要点（执行时照抄）

- **显示开关做成一个结构对象** `website_profile.timetable_fields`，不是六个
  散布尔。缺的键取推荐默认（以后加字段不用迁移）；渲染是一个循环不是六个
  分支（所以 64 种组合是一种版式的子集，不是 64 种版式）；**开关是上限、
  内容是下限，取交集**——开着但没填地点就不出现空的「地点：」。
- **老师那一项是 AND**：字段开关开着 **且** 这位老师在团队管理里勾了
  「可在公开课表显示」。`memberships` 加 `public_display_name` +
  `show_on_public_timetable`，**默认关**——一位老师的名字不该因为「他被排了
  一节课」就上公网。个人同意永远压过版式偏好。
- **余位芯片**：绿「还有 N 位」/ 琥珀「快满了」/ **灰「已满 · 可加候补」**。
  必须带文字（颜色是第二信号，WCAG 1.4.1）；**不做实心填充**（§1.1，那一个
  饱和填充留给「预约体验」）；阈值按比例 `快满 = 剩余 ≤ max(1, ⌈容量×25%⌉)`
  ——容量从 1 到 30 都有，绝对阈值必然出错。
- **`is_public` 默认 false**：一对一时段、内部补课、试听位不该出现在公网。
- **停课那一天划掉并写原因，不是让它消失**——消失看起来像网站坏了。
- **内部 uuid 不进公开接口**，对外用「日期 + 开始时间」定位。放出去就成了
  一个我们不能重建这条记录的承诺。
- **冲突判定改成「同老师 + 时间重叠」**。现在只比时间，加老师后同时太松
  （同一老师撞课不报）又太紧（两位老师同时段误报）——**一个总是误报的警告
  等于没有警告**。
- **时区用 `tenants.timezone` 且在服务端算**，「今天」也是。浏览器算会差一天。
  这个产品在日期上栽过一次（RFC 1123）。
- **深色变亮不是改一个数就完**：纸抬到 L\* 12–14 后对比度会往下走，要让求解器
  重新解墨和线。好在 1080 条断言会自动红，不靠眼睛判断。

## 切分（v8.8.0 对外零影响，可以放心先发）

| 版本 | 内容 | 对外 | 估时 |
|---|---|---|---|
| v8.8.0 | 深色变亮 · 后台全部字段 · 停课表 · 冲突判定 · 老师公开开关 | **无** | ~2 天 |
| v8.9.0 | 公开课表接口 + 门户板块 + 余位芯片 + timetable_fields | 有 | ~1.5 天 |
| v8.10.0 | 免注册约课（公开表单 + class_bookings + CMS 审批 + 落到排课） | 有 | ~2 天 |

先发 v8.8.0 的好处不只是风险小：**真实数据先长出来，后两版就有真东西验收
版式**，不用靠假数据判断。

## 两个已经定了（2026-08-07 拍板，v8.10.0 照做）

1. **约课限制提前天数：要限制，范围 = `timetable_weeks`。**
   后台既然已经能选展示几周，那个数字就是唯一诚实的边界 —— **课表上看不到的
   日期，本来就没有「约」这个动作可言**。不另设第二个天数配置：两个数字迟早
   会不一致，而不一致的那次一定是家长先发现的。
2. **同一手机号 + 同一节课重复提交：返回「已经收到了，请等待」，不新建。**
   同一 `(schedule_id, on_date, contact_phone)` 已有 pending 就直接这样回，
   不是错误提示。家长重复点通常是因为**不确定第一次成不成功** ——
   这时该给的是确认，不是拒绝。CMS 那边也不会多出一行要处理的重复请求。

---

# PWE Studio v8.7.0 — the portfolio grows with the plan, and opens properly (2026-08-07)

Plans: `docs/design/Showcase_Round_2.md`, `docs/design/Showcase_Plan_Limits.md`.
Owner's decisions, settled before any code: **15 / 60 / 150**, **no unlimited
tier at all**, categories **not** plan-limited, and on downgrade keep
everything / publish what the plan allows / say so plainly.

Six pieces: A placeholders, B plan limit, C categories + own endpoint,
D upload, E lightbox, F release.

## A — every English-half field showed a Chinese placeholder

Product-wide and pre-existing, visible in the owner's screenshot: 「版块眉题 ·
English」 offered 「工作室作品」 as its example. `applyAttributes()` localised
`placeholder`, so `Founder & Principal`, `Courses & Classes` and the rest all
rendered Chinese under an English label.

**A placeholder has one job — show what to type — and it was showing the wrong
language to type in.**

Locked by id suffix (`/En\d*$/`), not by a hand-applied attribute: an
attribute is a thing to forget on the next bilingual pair. `title` and
`aria-label` still localise; those are interface chrome. Verified in the
browser in both console languages.

## B — `plans.showcase_limit`, 15 / 60 / 150

A column with a CHECK, matching this table's convention (numeric ceilings are
columns; `features` holds booleans). No unlimited tier, so no per-tenant
override, no `-1`/NULL sentinel, and no `if limit is None` branches anywhere.

**The load-bearing part is what did NOT change.** v8.6.0 truncated in
`_normalize_website_profile` at `[:SHOWCASE_ITEM_LIMIT]`. Had that survived
contact with a per-plan cap, a studio moving growth → starter would have lost
135 works **the next time it saved anything at all** — changing a phone number
would have destroyed a portfolio, silently. The same shape as the v8.5.4
outage: an innocuous truncation operating on someone else's data.

Now: `SHOWCASE_STORAGE_CEILING = 500`, plan-independent, purely to bound a
hostile request. Publishing is limited on read. `test_the_write_path_does_not_
cap_by_plan` asserts 200 works survive normalisation.

Wired through the plan editor, the public pricing cards and `pricing.md` —
omitting the pricing page would have left the thing being sold invisible on
the page that sells it.

## C — categories, and the board on its own endpoint

- Category ids are **server-generated, never derived from the label**, so a
  rename cannot detach the works under it. Deleting a drawer never deletes
  what is in it.
- `GET /v1/public/<slug>/showcase?category=&offset=`, 12 a page.
- **The plan limit is applied before the category filter.** The other order
  lets an entry-plan studio publish its archive one drawer at a time —
  measured: 10 works in one category under a 15-work plan.
- `showcase_limit_for()` never raises; a missing plan row costs part of a
  board for one request, never the page.

**The board left `/brand` deliberately.** That response carries every word and
image of a portal, and v8.5.4 proved what one unreadable field in it costs.

**Which re-creates the v8.5.3 race on purpose**, with the fix designed in
rather than discovered. Measured in the browser:

| order | result |
|---|---|
| board first, switch unknown | 3 tiles, nav shown |
| then switch arrives OFF | **0 tiles, nav hidden, section unresolved** |
| switch ON, board empty | hidden |
| switch ON, board has works | shown |

Caught during that check: the filter chips live outside the grid and survived
the teardown, leaving a row of filters above a hidden section. Fixed.

## D — upload

Was: one file input per card, one file at a time, no compression.

**Client-side downscale is the biggest single win here and it is not about our
bandwidth.** A 24MP phone photo is ~8MB against a 10MB per-file limit, so a
studio photographing its own work was one portrait away from a rejection it
could not explain. Measured in the browser: a 4000×3000 JPEG becomes 2400×1800
at **24.5% of its size**.

`imageOrientation: 'from-image'` is load-bearing — canvas does not apply EXIF
rotation, and without it every portrait phone photo ships lying on its side.
Verified with a hand-built JPEG carrying EXIF Orientation 6.

Two guards worth keeping: a re-encode that comes out **larger** is discarded
(a flat PNG easily does), and `createImageBitmap` failing falls back to the
original file rather than blocking the upload.

Also: one dropzone, multi-select, drag and drop, optimistic cards with local
previews, real per-file progress (XHR — `fetch` cannot report upload
progress, and an unmeasured progress bar is a lie), concurrency 2, per-file
failure. And **uploads patch one card instead of rebuilding the list**, so
finishing an upload no longer destroys a caption being typed three cards down.

## E — lightbox

Native `<dialog>` + `showModal()`: focus trap, Escape and inertness come free.
No `showModal` → the old behaviour is kept. **There is no half version of
this; a lightbox you cannot close is worse than none.**

**The back button closes it.** On a phone, back is how people dismiss anything
covering the screen — before this, tapping it to leave a photograph would have
taken the visitor off the studio's site entirely. This is the most commonly
missed part of a lightbox and the most damaging.

Measured on a clean page load:

```
opened from tile 2 -> open, focus inside, "2 / 4", body locked, gutter stable
Escape             -> closed, focus back on that tile, history state clean
back button        -> closed AND still on the same page
play               -> 0 iframes before, 1 nocookie iframe inside after
close              -> 0 iframes anywhere (the video actually stops)
Esc x3             -> no history leak, length stable
```

Arrows and swipe move; swipe-down dismisses; only n±1 preload; the scroll lock
uses `scrollbar-gutter: stable` so opening does not jolt the page sideways.

`test_dark_framework` caught `&#8592;` / `&#10005;` reading as hex colour
literals — a false positive that pointed at a real rule (icons are SVG, not
characters). Replaced with inline SVG, which also stops them rendering at the
mercy of whatever font resolves them.

## Gate

- **1483 passed, 7 skipped**; palette checker **1080 assertions, 0 failures**
- migration `0024_plan_showcase_limit.sql` applied; starter 15 / studio 60 /
  growth 150 confirmed in production

## Still open

- No filters beyond categories, and no per-work deep links — both deliberate,
  see `Showcase_Round_2.md` §5.
- The CMS shell still has no accent tokens until `/brand` answers, so
  `bg-indigo-*` is unpainted on first paint outside the chrome layer.
- No endpoint reports media usage, so the console shows the publish count and
  the resize rule instead of a storage figure. Inventing a number there would
  have been worse than saying nothing.

---

# PWE Studio v8.6.0 — the studio can finally show its own work (2026-08-07)

Plan written first: `docs/design/Showcase_Section.md`. Read that for the
reasoning; this records what shipped and what the browser said about it.

## Why it is not the student gallery

A portal could prove what students had made and not what the studio can do.
The principal section was a portrait and a paragraph — a claim, not evidence.

The two are separate sections because they differ in every dimension that
matters: author, consent model, provenance, and the question they answer.
Merging them would give "作品" two meanings on one page and put a commercial
portfolio under the same heading as student practice.

Reading order is the argument, and it is asserted:

```
about（空间） → artist（主理人） → showcase（成果） → courses → gallery（学员）
这是空间 → 这是教你的人 → 这是他的作品 → 这是课程 → 这是学员学成的样子
```

## Video: linked, whitelisted, and not requested until asked

`backend/studiosaas/video_embed.py`. Three providers, and the parse is the
security boundary rather than a rewrite: only a recognised provider and an id
matching `[A-Za-z0-9_-]` survive it, and the frame URL is built from OUR
template. **Nothing a studio types can reach the DOM.** Vimeo private hashes
are dropped on purpose — we do not republish a link its owner kept unlisted.

`frame-src` was ABSENT from the CSP, which means it fell back to
`default-src 'self'`. Every embed would have been blocked with no error
anywhere — the third time this exact failure mode has appeared in two
releases (the webfont, then the fonts directory, now this). The origins now
come from `video_embed.EMBED_ORIGINS`, so a provider added without a policy
entry is impossible, and the test reads the header off a **real response**
rather than off the source.

Click-to-play, not a bare embed: a YouTube iframe is several hundred KB of
third-party JavaScript per tile, spent before anyone asked to watch — and
spent by the visitor's phone. Verified in the browser: **0 third-party
requests before the click, 1 iframe after**, `youtube-nocookie`, no `allow`
attribute (a frame that can autoplay can autoplay again on re-render).

## Golden ratio: where it is, and where it deliberately is not

φ is in the **column split** — `--ui-golden-columns`, 61.8 / 38.2 — and
nowhere else. That was a correction forced by measurement, not a preference:

> With columns of 1.618k and k, a 1.618:1 lead tile is exactly k tall while
> the two stacked squares beside it are 2k + gap. **They cannot both be
> golden.** The first attempt claimed they matched and left a 447px hole under
> the lead at 1440px — measured, not guessed.

So the lead fills its two-row span instead and comes out portrait, which is
the better crop for a painting anyway. Measured after the fix at 1440px:
lead top = second top, lead bottom = third bottom, **0px on both**.

Two grids rather than one clever one: the lead block, then an equal grid for
tiles four and up. A `grid-column: 1 / -1` override would have silently fought
the φ template.

## The play button was invisible on exactly the art a studio posts

The first version relied on a scrim over the photograph. Measured:

| photograph behind it | glyph contrast |
|---|---|
| near-white | **1.22:1** |
| mid grey | 4.47:1 (still under AA) |
| black | 17.35:1 |

A light painting is not an edge case in an art studio, it is the common case.
The glyph now carries its own opaque ink disc: **16.27:1 on every image**,
54×54, a real `<button>` with an `aria-label` and a focus ring. Its separator
is localised too — a full-width colon inside an English label reads as a typo
to a screen reader, not as a style.

No shadow on it: `test_shape_language` caught an invented `box-shadow` and was
right to. The product has two elevations and neither is for a 54px control.

## Studio Admin

Its own tab. Twelve items × (photo + two bilingual texts + a link) would have
doubled the length of the Website tab. Reorder, remove, a `Lead` badge on the
first because it genuinely renders larger, and the video link is described the
moment it is typed rather than at Save.

The browser's provider check is **feedback only** — the raw link is what gets
submitted, and the server is the only thing that decides what a link becomes.
A second parser in the trust path would be a parser the attacker controls.

Publish verification compares what both sides can answer (photo, title,
whether a video is attached): the payload carries a raw link, the brand comes
back with a parsed provider and id, so comparing the link would fail every
publish that contained one.

## Local tenant workspaces

Production is the source of truth. Four local directories — `dance-dance`,
`lets-play-game`, `lets-play-piano`, `ruby-studio` — were stale generated
copies of tenants that no longer exist; git history is the archive. Kept:
`lets-paint-studio` (live) and `lets-paint-showcase` (required by the
standalone bundle, excluded from the SaaS one — `verify_release_bundles.sh`
asserts both).

`test_tenant_surfaces.py` had that set typed into it as a tuple. It now reads
the directory, so archiving a workspace is a one-step change instead of a red
suite, and a workspace that stops rendering still fails.

## Gate

- **1461 passed, 7 skipped**; palette checker **1080 assertions, 0 failures**
- CSP on the wire: `frame-src 'self' https://player.bilibili.com
  https://player.vimeo.com https://www.youtube-nocookie.com`
- 1440px: column split 0.607 (gap accounts for the rest of .618), lead/second
  and lead/third aligned to 0px, three equal tiles below, no horizontal
  overflow. 430px: single column, 4:5 lead, no overflow.
- Click-to-play: 0 third-party requests before, correct nocookie src after,
  no CSP refusal in the console.

## Not done

- No lightbox. Focus trap, Esc, back-button and mobile gestures all have to be
  right or it is worse than nothing; this release makes the board good first.
- No filters or categories — pointless under twelve items.
- The CMS shell still has no accent tokens until `/brand` answers, so
  `bg-indigo-*` is unpainted on first paint outside the chrome layer.

---

# PWE Studio v8.5.4 — five portals had been serving 500 for their whole content payload (2026-08-07)

Started as "find the text and images this one tenant wrote". Nothing had been
lost. **Five of six live portals had been blank since v8.5.2, and every check
we own said the release was healthy.**

## The outage

`GET /v1/public/ruby-s-studio/brand` → 500. The page itself was 200, which is
why it looked like missing content rather than an outage: a portal's copy,
images, principal bio and contact details all travel in that one response.

Production log:

```
ValueError: Visual style is not recognised.
```

v8.5.2 renamed the single-palette style id `studio` → `custom`. Nothing
migrated the rows:

```
hong-s-studio  | studio | hue=195.0     lets-paint-showcase | atelier-clay
jjl-s-studio   | studio | hue=25.0      lets-paint-studio   | studio | hue=17.0
n-piano-studio | studio | hue=286.2     ruby-s-studio       | studio | hue=341.8
```

And the READ path was the WRITE validator. `api_v1.py` re-normalised the
stored theme on every brand read to fill in tokens added since the record was
written — reasonable — but `_normalize_visual_theme` **raises** on an id it
does not know, because on a write that is the correct behaviour.

**Renaming a key is a data migration whether or not anyone runs one.** A
stored record is written by whichever release the owner last saved under, and
the read path meets all of them.

### Nothing was lost

Every field the tenant wrote is intact and was intact throughout — 2189 bytes
of `localized_copy`, a 556-byte bilingual `principal_profile`, `faq_items`,
`registration_profile`, `hero_profile`, and all 10 media assets (logo and hero
both still serve 200). Replayed against the fix, `ruby-s-studio` resolves to
`custom` at hue 341.8 with accent `#883850` — the rose it picked.

### Three parts, because the bug needed all three to be missing

1. **`presets.RETIRED_STYLE_ALIASES` + `resolve_style_id()`.** `studio` →
   `custom`, forever. Cheaper than a migration and strictly safer: a migration
   only repairs the rows that existed when it ran, this also catches a record
   restored from an older backup. Entries are never removed.

2. **`_stored_visual_theme()` on the read path**, with
   `_normalize_visual_theme(..., strict=False)` under it. The invariant, stated
   once: **a stored theme has two possible outcomes — the studio's theme or the
   default theme — and never an exception.** A stored record is not user input;
   there is no owner present to tell, and raising renders nothing.
   `test_stored_theme_tolerance.py` fires eleven shapes of bad stored value at
   it, including the real rows.

3. **The deploy gate now asks about the data.** `/v1/health?deep=1` reports
   `themes.unreadable` — how many live tenants store a theme this release
   cannot read — and `pwestudio_remote.sh deploy` refuses to keep a release
   unless it is 0. `SELECT 1` proved the database answered; it never proved
   this release could render the tenants inside it. Deliberately **not** a 503:
   deep health drives the container healthcheck, and a stale row is no reason
   to restart a service that is answering every request.

## About was an orphan, and Save was deleting it

`show_about` plus seven sibling fields were stored, validated, and fully
rendered by the portal — bilingual eyebrow/title/body, a numbered highlight
list, a six-image carousel — with **no control anywhere in Studio Admin**.

Worse than invisible. `_normalize_website_profile` rebuilds the profile from
the payload alone; it does not merge. So **every Save from that page erased
all seven**, which is also why the flagship tenant's reclaimed `seo_title`
never survived its first Save Draft.

Added: the seventh switch, an About disclosure (bilingual copy, up to six
uploaded photos via a new `target=about`, three highlight slots), an SEO
disclosure, and all of it in the save payload *and* the publish verification.

`test_the_admin_sends_every_field_the_server_stores` reads the **server's**
field list out of `_normalize_website_profile` and checks each one appears in
the admin payload, so the next omission fails in CI rather than at somebody's
Save. Verified by deleting a field and watching it go red.

## The empty hero was a shaped void

`background_style: image` with no image uploaded rendered the decorative
gradient inside the chosen hero shape — a large blob exactly where a
photograph obviously belongs. It collapses to the one-column `hero-minimal`
now, and so does an image that fails to load, because "did not load" and "is
not there" are the same thing to a visitor. `soft` is untouched: that is a
studio choosing the gradient on purpose.

## The CMS was two full slabs of accent before a single button

`bg-indigo-900` on the sidebar, the mobile tab bar and the mobile top bar. The
Tailwind config maps `indigo` → `role('accent')`, so `-900` is
`--accent-pressed`: **the largest surfaces in the app were the studio's accent,
at full saturation, permanently.** Design_Constraints §1.1 allows one per
screen.

Replaced with a `.cms-chrome` token layer. The accent is not deleted, it is
spent where it means something: the active tab, and the one link out to Studio
Admin.

Two things here were **measured in the browser, and both changed the design**:

- The active item was going to sit on `--bg2`. Against `--bg2` the
  `--accent-soft` chip is **1.00:1 with +6 chroma — invisible**, the same trap
  §1.3 documents for the status chips. On `--panel` it is 1.25:1 and +21
  chroma, and its border goes 1.66 → 2.07:1. The rail is `--panel`.
- On the CMS shell the **entire accent family is undefined** until `/brand`
  answers and the runtime sets it. A bare `var(--accent-soft)` computes to an
  invalid value, the declaration drops, and the current tab has **no indicator
  at all** — worst precisely when `/brand` fails, which is what this release
  is fixing. Every accent token in the chrome now carries a neutral fallback.
  The fallbacks are **tokens, never literals**, so colour still has one source.

Final measurements, both before and after `/brand` answers: idle text 10.05:1,
active text on chip 9.61:1 (14.46 on the fallback), inset border present in
both, mobile tab rule 7.55:1 (16.27 fallback).

## The display face had never once loaded

`tenant-template` linked `fonts.googleapis.com` while this site's own CSP
(`server.py`: `default-src 'self'`, `font-src 'self' data:`) blocked both the
stylesheet and the font file. So `"Cormorant Garamond"` never resolved —
**every portal has been rendering Georgia since the CSP shipped**, while still
paying for two requests per page load that could not succeed. The template
comment describing the intent had been true of the intent and false of the
code.

Self-hosted instead (approved: 4 × woff2, ~142 KB, SIL OFL 1.1, licence
shipped at `/assets/fonts/OFL.txt`). It is a variable font, so 300–700 costs
one file per subset, and `unicode-range` means a CJK-only page fetches
neither. This also delivers what the comment always claimed: mainland visitors
no longer wait on Google.

Two traps avoided, both worth keeping:

- The preload URL and the `@font-face` `src:` must be **byte-identical**. A
  `?v=` on one and not the other is two URLs, and the face downloads twice on
  first paint. Neither carries one.
- Which means the font cannot be cache-busted by version — so
  `_cache_versioned_asset` sends `font/*` as immutable unconditionally. Safe
  because the face, style and unicode subset are in the filename: a different
  cut is a different file, not new bytes at the same URL.

Verified in the browser: `latin normal` reports `loaded`, the other three
subsets stay `unloaded` (correct — nothing on the page needs them), and the
same string renders 408.3px in Cormorant vs 484.9px in Georgia, which is proof
it is being *used* and not merely fetched.

## One more thing the screenshot found

With the portal rendering again, `ruby-s-studio` still showed the decorative
gradient blob — while holding a hero photograph it had uploaded. Cause: before
v8.4.0, uploading a hero image filled `hero_image_url` and did not move
`background_style` off `soft`, and the portal only reveals `.hero-art img`
under `body.hero-image`. Upload succeeded, Save succeeded, Publish succeeded,
and the photograph was never on the site. v8.4.0 closed the dead end for new
uploads but repaired none of the existing records, and **a studio has no way
to discover this**: nothing is broken, there is just a shape where their
painting should be.

`backend/scripts/show_uploaded_hero_images.py` reports and repairs it (dry-run
by default). Exactly one tenant was affected across all six; backed up, then
applied to `ruby-s-studio`. Her painting is now the hero. Reversible from
Studio Admin in one click, and the photograph was never at risk either way.

## Gate

- **1423 passed, 7 skipped**
- palette checker: 18 theme-modes × 60 pairs = **1080 assertions, 0 failures**
- 6 tenant workspaces regenerated from the template; no Google Fonts link left
  in any portal
- `/assets/fonts/*.woff2` → 200, `font/woff2`, `immutable`

## Still open

- The CMS shell has no accent tokens until `/brand` answers, so every
  `bg-indigo-*` is unpainted on first paint. Pre-existing, now survivable
  everywhere the chrome touches, but the flash is still there for the rest.
- `tenants/ruby-studio/` exists locally while the live slug is `ruby-s-studio`
  — the local workspace set and production have drifted.

---

# PWE Studio v8.5.3 — two section switches only reached the navigation (deployed 2026-08-06)

Audit prompted by a direct question: do the six section switches in Studio
Admin correspond one-to-one with the portal's sections? Two did not.

## The finding

| switch | portal section | how it was enforced | verdict |
|---|---|---|---|
| `show_principal` | `#artist` | `resolveSection('artist', hasPrincipal)` | OK |
| `show_courses` | `#courses` | **`setNavVisible` only** | **BROKEN** |
| `show_gallery` | `#gallery` | **`setNavVisible` only** | **BROKEN** |
| `show_faq` | `#faq` | nav + `renderFaq` skipped, so it stayed empty | OK, indirectly |
| `show_contact` | `#contact` | `showSection` | OK |
| `show_student_area` | `#parent` | `showSection`, OR'd with `show_student_login` | OK, two owners |

Switching off 课程 or 作品墙 removed the menu entry and left the section on the
page. **The studio saw it disappear from the navigation and concluded it was
off; a visitor scrolling past still saw it.** Nothing failed, so nothing said
so — the same shape of defect as the industry/palette weld in v8.5.2.

## Why it needed fixing in two places

`#courses`, `#gallery` and `#faq` are `data-awaits-data` sections: hidden until
their render function calls `resolveSection(id, true)` once content arrives.
The switches ride on `/brand`; the content rides on `/programs` and
`/public-gallery`. **Those are independent fetches and either can answer
first.** Hiding the section when `/brand` lands is not enough — a slow `/brand`
means the content already revealed it, and a fast one means the render reveals
it afterwards.

So the switch is recorded in `state.sectionsOff` when `/brand` answers, applied
immediately to whatever is already on the page, AND consulted by each render
function. Neither order can win.

## Verified against the adverse order, not by reading

A probe driving the real portal runtime with a stubbed network — `/programs`
answering at 0 ms, `/brand` at 250 ms, which is the order that produced the
bug:

```
contentArrivedFirst: 2          <- two course cards rendered before /brand
switchesOff: {courses:true, gallery:true, faq:false}
principal ON  -> artist   true
courses  OFF -> courses   false  <- hidden despite content having arrived
gallery  OFF -> gallery   false
faq      ON  -> faq       true
contact  ON  -> contact   true
student  ON  -> parent    true
```

Three false starts getting there, each worth remembering: the external assets
404 under `file://` and took the page script down before the code under test
ran (fixed by inlining the real `ui-common.js` / `public-register.js` /
`public-analytics.js` rather than stubbing them); the stub was anchored on a
string that does not exist in this template and was **silently never inserted**;
and the payload used `principal` where the portal reads `principalProfile`,
which looked exactly like a seventh broken switch.

## `show_about` — a whole section with no way to reach it

`_normalize_website_profile` validates and stores `show_about`, and the portal
has a complete `renderAbout()` with a bilingual title, body and a six-image
slideshow. **Studio Admin has no control for any of it** — zero occurrences of
any about field. It defaults to `false`, so no tenant has ever seen it.

Not fixed here, because building an image-uploading editor is a feature and
this release is a correspondence fix. Recorded as a task, and pinned in
`test_section_switches.py` as a `known_orphans` entry so a SECOND one cannot
appear without failing.

## Tests

`backend/tests/test_section_switches.py`, 23 assertions. The load-bearing one:

```python
SWITCHES = {
    "show_courses": ("courses", "settingShowCourses", "state.sectionsOff.courses"),
    ...
}
```

Each switch names the expression that carries it to its section, so losing the
enforcement fails here rather than being re-derived by a regex that might guess
right. Plus: every switch has an admin control, every switch is validated
server-side, every data-fed section's revealing `resolveSection` consults its
switch, `state.sectionsOff` is declared before any render can read it, and no
NEW orphan appears on the server.

Two of my own assertions were wrong first and were corrected rather than
relaxed: the mechanism check guessed at `showSection('artist'` when principal
routes through `hasPrincipal`, and the reveal check matched
`resolveSection('gallery', false)` — a teardown for a failed image, not a
reveal.

## Numbers

* 1387 passed, 7 skipped.
* Palette checker: 18 theme-modes × 60 pairs = 1080 assertions, 0 failures.

## Carried forward

The empty-hero fallback (Design_Constraints section 5), the CMS rendering the
accent as a filled sidebar (section 1.1 at scale), Cormorant Garamond blocked
by the site's own CSP, and now the orphaned About section.

---

# PWE Studio v8.5.2 — the eight themes come back, and the industry stops repainting (deployed 2026-08-06)

This release reverses an architectural decision I made two releases earlier.
Recording why, because the reversal is more instructive than either state.

## What was actually wrong, and what I mistook it for

v8.5.0 found a genuine defect: because each theme's PAPER carried its own hue,
whichever semantic role shared that hue stopped being visible. Five of the
seven light themes had one — cedar-grove's success sat 4 degrees off its own
page, harbour-calm's info 9, vintage-press's warning 3. **A green theme could
not show "saved".** That measurement was correct.

The conclusion drawn from it was not. I removed the eight named palettes and
shipped one palette with an accent dial, on the reasoning that a system which
cannot safely vary its paper should not vary it. The owner opened Studio Admin
the next morning and said:

> "颜色主题消失了? 到哪里去选颜色主题 所有的门户页面都是统一成一个颜色了?"

Two separate things were true in that message. The portals had NOT become one
colour — every tenant kept its own hue through the migration. But **the ability
to choose a mood had gone**, and the right-hand preview showed the same fixed
description for every industry, because there was only one thing left to
describe.

The actual defect was two lines in `applyCategoryPreset()`:

```js
const theme = preset.visualTheme || {};
setVisualThemeFields(theme, preset.recommendedStyleId || ...);
```

Selecting an industry card wrote that industry's recommended palette over
whatever the studio had already chosen. **That** is what needed severing —
and it sat directly beneath a comment promising the two were independent.

## Why the restoration is safe

The eight themes come back on their ORIGINAL hues, unchanged. All 1080 colour
assertions pass, because the repair that made them safe was made in the
generator during the single-palette detour and survives it:

* `CHROMA_FLOOR` / `CHROMA_FLOOR_NEAR` — a semantic chip is mixed for CONTRAST,
  and contrast says nothing about colour. Every chip now has a floor on how
  much colour it carries, raised further when its hue sits within 20 degrees
  of the paper's. This is what makes vintage-press's paper (hue 32, four
  degrees off warning's 36) safe: the chip is floored to chroma 32 rather than
  whatever a contrast-only mix happened to produce.
* The neutral ramp is derived by CHROMA rather than by tapering the paper's own
  saturation, so a card never goes chalk-white for sharing a hue with a status.
* `accent_is_fixed` is back on for all eight — the curated accents are fixed at
  build time, so a semantic near one of them is pushed to a lightness that
  cannot be mistaken for it. It is off ONLY for the free-accent theme, where
  the accent is a live tenant input and coupling a semantic to it would make
  "saved" a function of somebody's logo.

**The variety was never the bug. The generator was too weak to carry it.**

## The shape now

| | |
|---|---|
| Curated themes | 8, each a complete palette with its own paper, ink, accent, support, mood line and harmony label |
| Free accent | 1 (`custom`), the only style `style_theme(..., accent_hue=)` honours |
| Industry | recommends one via a badge; writes copy, forms and the operating template, **never** a palette |
| Semantic hues | identical in all nine themes, so "saved" is recognisable in any tenant's admin |

`FREE_ACCENT_STYLE_ID` is the seam. `style_theme()` ignores `accent_hue` for
any curated theme — otherwise the picker would silently turn Recital Plum into
something that is no longer Recital Plum while still calling itself that.

## The admin

The dial and its seven-swatch shelf are gone, replaced by a nine-card grid.
Each card renders in the palette it IS — its own paper as the card background,
its ink as the title, and a three-stripe band of accent / support / control
boundary. A dropdown of nine names told an owner nothing about the mood they
were choosing, which is the entire reason these are named.

The colour picker is now revealed only when the Custom card is selected. An
always-visible colour input is what made eight curated themes read as
decoration around a dial.

## Tests added

`backend/tests/test_theme_choice.py` pins both halves, because the boundary has
now been crossed in both directions:

* the eight moods exist, are named and described in both languages, and their
  papers have not converged (≥6 distinct);
* every semantic chip carries at least 8 more chroma than the paper it sits on,
  in every theme and both modes — the defect that was blamed on having eight
  themes, asserted directly;
* no semantic collapses into its own theme's accent (30 degrees or 1.55);
* the semantic hues are identical across all nine themes (±2, for 8-bit
  quantisation rather than drift);
* **`applyCategoryPreset` does not call `setVisualThemeFields` or write any
  colour field** — the wiring bug, pinned in the file where it lived;
* `accent_hue` is honoured for `custom` and ignored for the curated eight.

## Two test flaws found by the new tests, corrected rather than relaxed

1. The semantic-hue check read a 1-degree spread on warning (35 vs 36). That is
   8-bit quantisation — the solver works at the exact hue and the hex reads
   back a degree either side once each channel rounds to a byte. Tolerance is
   now ±2, with the reason written down so it is not later widened for drift.
2. The `applyCategoryPreset` scan matched **my own comment** explaining why the
   call was removed. Comments are stripped before the check, which is what lets
   the note stay where the mistake was made.

## Numbers

* 1362 passed, 7 skipped.
* Palette checker: 18 theme-modes × 60 pairs = 1080 assertions, 0 failures.

## Carried forward, unchanged

Still open from v8.5.1: the empty-hero fallback (Design_Constraints section 5 —
no photo should mean `hero-minimal`, not a large blank organic shape), the CMS
rendering the accent as a filled sidebar (section 1.1 at scale, needs the
component layer), and Cormorant Garamond blocked by the site's own CSP.

---

# PWE Studio v8.5.1 — the colour choice had stopped looking like a choice (deployed 2026-08-06)

Four things, all from the first look at v8.5.0 in the actual console.

## The report, and what was actually wrong

> "颜色主题消失了? 到哪里去选颜色主题 所有的门户页面都是统一成一个颜色了?"

The portals had NOT become one colour — the seven tenants each kept their own
hue through the migration, and the three screenshots in that message prove it
(a wine Mellow Pear, a plum CMS, a terracotta Let's Paint). But an owner opened
Studio Admin, read "选择颜色主题", and saw one empty swatch. **The choice was
intact and the interface said it was gone**, which for a setup step is the same
thing.

The wrong fix is putting eight palettes back. The right one is making the
choice visible: a shelf of seven starting colours above the free picker. They
are seven starting points on ONE palette, not seven palettes — turning to any
of them moves the accent and nothing else, which `test_the_paper_and_the_ink
_never_move` already asserts.

## What the shelf exposed

The knob policed itself with `SEMANTIC_BANDS` — the regions a hue has to sit
inside to READ as a status. Wrong instrument: the product's own default accent
is hue 26, deliberately 10 degrees off warning, and the band rule (warning
26-50) would have pushed an owner who picked that exact colour off it. **The
default accent could not survive its own picker.**

Replaced with `ACCENT_MIN_SEMANTIC_GAP = 8` measured against the status's
ACTUAL hue. The bands stay for placing the semantics and for the docs, and
`test_the_default_accent_survives_its_own_picker` now asserts the thing that
was wrong rather than leaving it to memory.

## Also in this release

* **The industry cards lost their colour.** Each carried an accent dot and a
  three-swatch bar saying "this industry comes with this palette", which stopped
  being true in v8.5.0. Eight cards showing the same three swatches was noise
  pretending to be information.
* **Hero shape is a setting**: `organic` (default), `oval`, `square`. The
  organic edge is the one mark that makes the page read as a studio rather than
  a form, and it is also a strong opinion — a studio showing architectural or
  product work wants the rectangle. `test_the_organic_shape_belongs_to_the_hero
  _and_nothing_else` keeps it scoped to `body.hero-organic .hero-art`.
* **E — the type scale**, 23 sizes down to 8. Mapped by SEMANTIC LEVEL, not by
  rounding: 12px labels and 13.5px nav links are both the small-text tier, which
  is 13. Rounding would have sent 12 to 11, and 11 is reserved for wide-tracked
  uppercase labels. Verified the way section 2.2 demands — measured computed
  font-size in a browser over every visible element, **0 off-scale** — because
  grepping `font-size:` misses the `font:` shorthand and anything falling to a
  browser default.
* **A2 — the secondary is no longer a fill.** `secondary_text_color` is gone
  from the generator, both solvers, the CSS name map, four surfaces and five
  tests. Three places actually filled with it and are now tints:
  `brand-system.css` `.brand-action-secondary`, `cms-entry.html`'s button, and
  `super-admin.html`'s edited-section dot (which never used the token — an 8px
  marker is not the slab section 1.1 is about). A "text on the secondary fill"
  colour describes a component that must not exist; emitting it is what let
  three surfaces quietly build one.

## A test that was wrong, and how it showed

`test_no_font_shorthand_hides_a_size` flagged `font: inherit` on both public
pages. That is **valid** CSS — `font` takes the global keywords as a whole
value. The invalid form, and the one the reference project actually lost a size
to, is `font: 13px inherit`: a shorthand cannot take `inherit` as the family, so
the whole declaration is dropped and the element falls to 13.333px. The test now
flags only a shorthand carrying a px size.

## Numbers

* 1172 passed, 5 skipped.
* Palette checker: 3 theme-modes x 60 pairs = 180 assertions, 0 failures.
  (61 -> 60: the retired `on-2nd / 2nd` pair.)

## Still open

* **The empty hero.** A tenant with no hero photo renders a large, nearly blank
  organic shape. Design_Constraints section 5 already says the right behaviour
  — no photo means `hero-minimal`, never a CSS gradient pretending to be one —
  and it is still not implemented. Most visible cosmetic issue on production.
* **The CMS renders the accent as a filled sidebar and a filled hero card**,
  which is section 1.1 violated at scale on the one surface where the rule was
  never applied. Visible in the v8.5.0 screenshots as a fully purple sidebar.
  This is the CMS component-layer work, not a colour fix.
* **Cormorant Garamond is blocked by the site's own CSP** (`server.py:840`), so
  the Latin display face has been falling back to a system serif for several
  releases. Task chip open.

---

# PWE Studio v8.5.0 — eight industry palettes became one, and the accent became a knob (deployed 2026-08-06)

The trigger was a comparison, not a bug report. The reference project
(`LetspaintCMS`, `portal.html`, live at letspaintstudio.com) is the page this
product is meant to look like, and reading it side by side inverted what I
thought the problem was.

## The measurement that started it

| | Letspaint portal | PWE tenant (before) |
|---|---|---|
| palettes | **1** | 15 theme-modes |
| colour tokens | **10** | 43 |
| hard-coded hexes in the page | **59** | **4** |
| accents on screen at once | **1** | 6 |
| dark-mode code | **0 lines** | the whole framework |

By every mechanical measure PWE was cleaner, and it looked worse. Letspaint's
59 loose hexes are gradient stops for placeholder art in one narrow warm band —
they never carry text, never invert, never mean "danger". They cannot drift
because they are paint, not system. PWE's 43 tokens had to be simultaneously
correct across 15 palettes, so every one of them was a compromise.

**A palette is not a design.** The product had built a colour *engine* and
called it a design system. What was missing was the layer above it, which is
now written down by hand in `docs/design/Design_Constraints.md` — the file the
generated `Design_System.md` structurally cannot contain, because a generator
describes what exists and never what is forbidden.

## The defect nobody had measured

Because the PAPER carried the industry hue, whichever semantic role shared that
hue stopped being visible. **Five of the seven light themes had one:**

| theme | role lost | hue gap to paper |
|---|---|---|
| cedar-grove (green) | **success** | 4 deg |
| vintage-press (warm brown) | **warning** | 3 deg |
| studio-ink | **danger** | 5 deg |
| harbour-calm (blue) | **info** | 9 deg |
| atelier-clay | **danger** | 13 deg |

A green theme could not show "saved". Anchoring the paper removed four of the
five outright.

## What shipped

**One palette, one knob.** 28 of the 43 tokens are now constants — the paper,
the ink, the hairlines, and all four semantics. A studio sets the accent HUE
and nothing else; lightness and saturation stay the product's, solved for the
contrast targets. That is what makes a free colour picker safe to expose: a
neon logo becomes a deep pine, never an unreadable button.

```
paper   #F4F1EA   band #ECE7DA   card #FBF9F5
ink     #221F1A   13.30:1 on the band
accent  #704B2E   deep bronze, hue 26, solved to 6.2:1
support #576D49   moss, decorative only, never a fill
```

**The accent is analogous to the paper (16 deg), against the arithmetic.**
Placing it to maximise distance from the four status hues gives hue 276, a
violet. Measured, that is the better answer. Looked at, it is a brand colour on
a beige page. The reference site is analogous too (paper 40, clay 13). The cost
is paid in the admin surfaces — bronze sits 10 deg from warning — and what
makes it survivable is two rules that must not be removed:

1. **Design_Constraints 1.1**: a semantic role is never a solid fill, only a
   tinted chip. The accent is the only thing that fills. They are told apart by
   SHAPE first, hue second.
2. **1.3.1**: the accent's own chip is solved DEEPER than any status chip
   (`ACCENT_SOFT_STEP 1.52` vs `SOFT_STEP 1.22`), asserted at every hue the
   knob can reach. Without it the accent chip `#F2E0D2` and the warning chip
   `#EEE1CE` measured 9 deg apart at **1.00:1** — the same chip twice.

Remove either and the default accent has to change.

## Five things found while executing, none of them planned

1. **The solver moved into the package** — `backend/studiosaas/palette.py`. The
   knob has to solve AT REQUEST TIME and the deploy bundle has no reason to
   ship `docs/`. `palette_gen.py` now loads it by path (not as
   `studiosaas.palette`, which would run the package `__init__` and pull in
   Flask) and keeps only the assertions and the two emitters.

2. **Every semantic chip was invisible, not just the same-hue one.**
   `SOFT_STEP` mixes to a CONTRAST target, and contrast says nothing about
   colour: all four chips measured chroma 11-17 against paper's 10, success at
   **+1**. Fixed with a chroma floor (22, or 32 when the role shares the paper
   hue). Note the metric: **HSL saturation is useless near white** — the panel
   `#FEFEFD` reports S=0.333 — so this measures max-minus-min instead.
   Hue optimisation, tried properly as a constrained placement problem, buys
   **0 degrees**; the bottleneck is warning against warm paper and does not
   involve the accent at all.

3. **The neutral ramp was being drained of warmth.** `panel` came out `#FEFEFD`
   (chroma 1) — a white slab on warm paper — and `line` `#DDDBD7` (chroma 6), a
   grey line on a warm page. Cause: saturation tapers (`s*.72`, `s*.28`)
   written when the paper hue was arbitrary and the taper protected against a
   visibly blue card. With one anchored paper it protects nothing. Now derived
   by CHROMA as a ratio of the paper's, and the ramp matches the reference
   token for token.

4. **An anchor is a light-mode identity.** `ink = anchored(...) or ink` applied
   unconditionally, so dark solved near-black body text onto a near-black page
   at 1.14:1. Latent until now because the only anchored theme was the
   light-only console.

5. **The semantics were being dragged by the accent.** `solve_semantic` nudged
   each hue 4% toward the accent and pulled saturation 60% of the way to it —
   a feature across eight themes, and with a free knob it means a tenant's logo
   decides what "saved" looks like. Removed, and the semantics came out
   *better*: warning went from `#453318` (near-black, dragged dark by the
   low-saturation bronze) back to a real amber `#8E6426`.

## A check I retired, and why

"a semantic's solid form must stay 30 deg or 1.55 from the accent" is gone from
both the checker and `test_visual_theme_coherence`, replaced by chip-against-chip
separation. Two reasons, both in the code comments: the solid form it guarded
no longer exists (1.1), and satisfying it would require re-solving the
semantics against the accent — which is the exact defect the single palette
exists to remove. The replacement is asserted inside `build`, so it holds at
every hue the knob reaches rather than only at the default. The console keeps
the old check, because its accent is pinned.

## Also in this release

* **The accent picker** (`studio-admin.html`): swatch + hex + "From logo",
  which reads the dominant colour off the uploaded logo by hue-bucketing
  (averaging turns any two-colour mark into mud). Live preview goes through
  `GET /v1/theme-preview` — a round trip on purpose, because shipping a solver
  to the browser would make three implementations of one algorithm and the two
  that exist are only safe because a parity test compares them token by token.
  The guard messages say what was done: achromatic input, or a hue moved out of
  a status band.
* **The shape language** (`portal-theme.css`): the public site used two hard
  corners, `--radius: 2px` and `--radius-card: 4px`. Now a five-step soft scale
  (10/14/20/28/36 + pill) and exactly two elevation tokens, with one organic
  radius on the hero. No colour changed. Measured against the reference, this
  was the largest single NON-colour difference between the two products.
* **A JS/Python parity bug**, 6e-14 wide: `((h/6)%1+1)%1` corrects JavaScript's
  negative modulus unconditionally and costs a mantissa bit on values that were
  already fine. Pure blue read 239.99999999999994 in JS against 240.0 in
  Python, which became a whole step of red once a channel sat on a rounding
  boundary. Second time that parity test has earned its keep.

## Migration

`backend/scripts/migrate_to_one_palette.py --dry-run` first. It keeps each
tenant's existing accent HUE and re-solves everything else; an achromatic or
missing accent falls to the default bronze. `--reset-all` puts everyone on the
default. Unlike the v8.2 migration it replaces `custom` themes too — they were
tuned against a palette that no longer exists — with `--keep-custom` to opt out.

## Numbers

* 1165 passed, 5 skipped.
* Palette checker: 3 theme-modes x 61 pairs = 183 assertions, 0 failures.
  (It was 976 across 16 theme-modes; the drop is the point, and every remaining
  assertion covers a surface a tenant can actually reach.)
* New: `test_accent_knob.py` (36), `test_shape_language.py` (7).

## Not done, deliberately

* **E — the type scale.** `tenant-template/index.html` carries **23 font
  sizes, 13 of them between 11 and 19px**. The closed set in
  Design_Constraints 2.1 is eight. Needs measured computed font-size in a
  browser, not a grep — `font:` shorthand and unstyled controls both hide.
* **A2 — secondary as a solid fill.** 1.1 says the generator should not emit
  `secondary_text_color` at all. Three surfaces still fill with it:
  `super-admin.html:1450`, `backend/frontend/cms-entry.html:79`,
  `brand-system.css:114`. Converting them is UI work, not generator work.
* **Dark mode's future** (Design_Constraints 9). It is now a tractable design
  task rather than an unsolvable optimisation — one hand-tuned dark paper
  instead of seven generated ones — but nobody has decided whether to do it.
  Worth knowing: the reference page, the best-looking in this family, has
  **zero** dark-mode code. It did not solve the problem; it declined it.
* **The CMS component layer.** Counted this round: the reference CMS has **72**
  `.cms-*` semantic component classes, this one has **8**, and all eight are
  layout containers. Their 44px touch target is declared **6 times**; ours is
  written at **96** call sites. v8.4.2 perfected the patch layer when the
  destination was supposed to be components. That is the real CMS answer and it
  is a large piece of work.

---

# PWE Studio v8.4.2 — the CMS was patching the generator instead of configuring it (deployed 2026-08-05)

The CMS colour problem has been open since the theme system existed. This is
why, and it is a category error rather than a list of missed values.

## What the CMS actually is

`legacy-root/src/cms-app.jsx` (5723 lines) -> esbuild -> `assets/cms-app.js`.
The shell loads the **Tailwind Play CDN**, which generates utilities in the
browser from `tailwind.config`. The app renders **1422 colour-utility
occurrences, 154 distinct, across 12 colour families** — and 703 of those 1422
are `gray`.

The shell carried **68 rules** of `[class*="bg-indigo-"]` overrides chasing what
the generator had already emitted. That layer reached **84 of the 154**; the
other **70 painted fixed Tailwind values no theme could touch**.

Patching could not converge. Every new component brings new utilities, so the
patch layer grows forever and is always behind.

## The distinction it never made

>   THE NEUTRAL RAMP INVERTS WITH THE MODE. THE ROLE RAMPS DO NOT.

`bg-gray-50` is a surface and `text-gray-900` is ink, and those swap in dark.
But `bg-red-600` is a red button in both modes, and `bg-indigo-700` — every
filled action in this app, 保存 / 刷新 / 签到 / 退出登录 — is a deep brand slab
carrying light text in both.

A rule that flips everything breaks the buttons. A rule that flips nothing
breaks the page. The override layer had no way to express "flip these, hold
those", so it could only ever be half right.

The config expresses it directly: the neutral ramp is built from `--bg` and
`--ink`, which already swap, so it inverts for free. Role ramps end at
hover/pressed, which the generator already moves in the mode-correct direction.

Measured with a dark theme applied:

```
bg-gray-50      lum 0.011   |  text-gray-900  lum 0.808   inverted
bg-indigo-700   lum 0.378   |  white on it    5.49:1      held
```

## Three attempts to install the config, two of which failed

Worth recording, because the documented Play CDN pattern does not hold for this
vendored build:

1. `<script src>` then `tailwind.config = ...` — the build installs
   `window.tailwind` AFTER the tag returns, so the assignment landed on a
   placeholder that was then replaced. `config` read back `{}` and every
   utility stayed stock Tailwind.
2. Defining `window.tailwind` through a getter/setter first — the build installs
   its own property descriptor, discarding ours.
3. Assigning once the object really exists. Works, and was proved at the console
   before being written into the page: `bg-indigo-700` went from stock `#4338CA`
   to `var(--accent)` and the JIT regenerated every affected rule.

A fourth failure was mine: the scripted edit that moved the block spliced out
its middle, and the page threw `SyntaxError: Unexpected token '}'`. The console
said so immediately; I had been reading computed styles for two rounds without
looking at it.

## The chain, because missing a link here is the whole story

* `cms-app.js` is a **build artefact**. The v8.4.1 chart-colour fix went into
  the artefact, not `cms-app.jsx`, and the next build silently reverted it.
  Fixed at source and rebuilt.
* The shell's `themeVars` map predates v8.4.0 and stopped at the loud tokens, so
  every quiet form the config references would have resolved to nothing. It now
  carries 40.
* The portal and register maps were then behind the CMS, which
  `test_the_three_surfaces_agree_field_for_field` caught on the spot — the point
  of asserting equality rather than completeness. All three carry 40.
* Six `bg-red-500/80`-style alpha modifiers cannot apply to a `var()` colour;
  they compile to an invalid value and the fill silently disappears. Rewritten
  at source.
* `bg-blue-50` marked "长期未到访 — 有余额但超过 90 天未上课" with the info role,
  so it rendered green on a green theme and green on a rose one. It is a
  warning: money sitting unused and a student drifting.

## What `white` cost, which was nothing

183 `-white` utilities, and Tailwind cannot tell `bg-white` (a card) from
`text-white` (a label on a filled button) — `colors.white` is one value. It
works only if `--panel` clears 4.5:1 on every accent, and it does: worst 5.10 at
arcade-lime dark. No source change needed.

---

# PWE Studio v8.4.1 — the CMS had the inversion too, and dark cards did not lift (deployed 2026-08-05)

Three things reported against v8.4.0, all confirmed by measurement first.

## "Follow the visitor's device" could not be selected

Reproduced in the browser: choosing it snapped the control back to the previous
mode, and `settingsPayload()` would have SAVED that mode.

`setVisualThemeFields()` is handed two different kinds of thing — a SAVED
record, which carries the owner's preference, and a GENERATED style palette,
which cannot, because a palette is a set of colours and has no opinion about
who picks the mode. Choosing `system` set the preference, then
`applyVisualStyle()` called `setVisualThemeFields(style.schemes[mode])`, the
lookup found no `scheme_preference`, and it was overwritten with the mode.

Now only a real preference replaces it, and `system` survives a palette that
cannot carry one. A single-mode style still drops it, because that is a setting
the server rejects on save.

## Dark cards did not lift off the page

Reported as the dark portal looking flat. Measured in OKLab across the eight
themes:

```
                page->band    band->card
light mode          3.67          8.13
dark mode           3.94          5.33     <- 1.53x flatter
```

v8.3.0 fixed the ORDER of the dark surfaces. This is the same class of mistake
one level down: the AMOUNT. The panel was a flat HSL `.150`, and HSL lightness
is badly non-uniform — the same numeric step buys much less separation near
black than near white, so a gap chosen to look like light mode's did not.

The dark panel is now solved to the perceived lift light mode already achieves,
which lands each theme between `.168` and `.182` rather than on one shared
constant, because how far `.150` gets you depends on the hue.

```
band->card lift: 5.33 -> 8.29   (light mode: 8.13)
```

This is the first thing in the generator measured in OKLab rather than sRGB
luminance, and it is worth saying why the whole solver did not move: WCAG
contrast is defined in sRGB and has to be computed there. OKLab answers a
different question — how far apart two things LOOK — which is exactly the
question a contrast ratio cannot answer and the one that was being got wrong.

## The operations CMS

Converted, and it was carrying the v8.3.0 defect the whole time:

```
CMS hand-built dark set
  bg    #0e1016     band  #20242f     panel #1a1d27
  panel is the nearest surface?  NO - INVERTED
  band->card 1.08 the WRONG WAY - the card sat darker than the surface under it
  --line-strong on panel 1.95:1  (WCAG 1.4.11 floor: 3.0)
```

That release fixed the ordering in the eight tenant themes and could not reach
this one, because it is a separate hand-written palette nobody regenerated.

`legacy-root/register.html` had a NINTH palette — Tailwind indigo `#312e81` /
`#6366f1` on cold slate — so a studio whose `/brand` request was slow or failed
showed its registration page in somebody else's colours. `cms-entry.html` had a
tenth, including the bright Family Amber the console retired in v8.4.0.

All now load on the default style. The CMS analytics charts drew a fixed
Tailwind indigo and emerald over a themed page; they read `--info` and
`--success`. The CMS address bar follows the theme like the portal's.

**Deliberately left fixed:** the printed report in `cms-app.js` keeps its own
warm palette. It is ink on paper, there is no viewer theme to follow, and it
already takes the studio's accent through the `:root` it injects.

`TOKENISED_SURFACES` now names 13 files rather than 9.

## Still not done

`product-home.html`, `manual.css` and `customer-resources.css` — roughly 76
literals. The marketing and documentation pages are arguably a separate
identity from the product, which is the argument for leaving them; they are
named here rather than globbed away so the choice stays visible.

---

# PWE Studio v8.4.0 — seven palettes became one, and dark mode reached the surfaces a palette cannot (deployed 2026-08-05)

The brief was "fix the colour problems, and the hero photo while you're at it".
Reading the whole front end first changed what the problem was.

## What was actually wrong: not one palette, seven

| Surface | Own colours | Loose literals | Dark |
|---|---|---|---|
| `portal-theme.css` → tenant portal + register | 46 | 7 | ✅ 8 themes × 2, generated and checked |
| `studio-admin.html` | 45 | 81 | ❌ none |
| `super-admin.html` | 49 | 61 | ❌ none |
| `legacy-root/index.html` + `cms-app.js` (the CMS) | 26 | 68 | one dead hook |
| `setup-password.html` | 9 | 16 | ❌ none |
| `shared-portfolio.html` | 7 | 13 | ❌ none |
| marketing / manual / compliance | — | 84 | partial |

Eight token names — `--bg` `--ink` `--line` `--line-strong` `--muted`
`--surface` `--brand` `--radius` — were declared by three of these at once,
with different values and different meanings.

**That is the structural reason dark mode could never be switched on: there was
no single thing to switch.**

Two findings inside that, both measured rather than read:

* **`studio-admin` was a stock framework palette on warm paper.** 33 of its 45
  colour values were verbatim Tailwind defaults — `#3b82f6` blue-500, a slate
  grey ramp at hue 215 (`#64748b`, `#94a3b8`, `#cbd5e1`, `#e2e8f0`) — sitting
  on `#f7f5f2`, hue 36. Cold furniture on warm ground. Wrong in *light* mode,
  which is why nobody had reported it. `super-admin` had the warm ramp and the
  right navy, so the two consoles had matching paper and mismatched ink.
* **`portal-theme.css` had drifted from the generator it claims to mirror.**
  Its own comment says "keep the two in step"; nothing enforced it, and 7 of
  21 defaults had moved. Two were not near-misses: `--warning` `#8D6426`
  against a generated `#5B421F`, `--danger` `#B6483A` against `#76332A`. Those
  are the colours every public page renders before `/brand` answers.

## Why this was an extension, not a rebuild

The console was genuinely rebuilt: 45 hand-declared values deleted, replaced by
one generated stylesheet. The eight studio themes were not, because they were
already generated — the right move there was to add the axes the generator was
missing.

The evidence that this was the right call is a number: after adding hue
splitting, anchors, a fourth semantic role, quiet forms for every role,
`--on-accent-muted` and three new assertion families, **all 15 tenant
theme-modes came out byte-identical — 0 drift across 330 tokens.** A structure
that survives that much addition unchanged is not the thing that was broken.

## What the generator gained

`docs/design/palette_gen.py`, 976 assertions on every build (was 525):

* **Hue splitting.** A spec may declare `ink_hue` / `accent_hue` / `sec_hue`
  separately from the paper hue. The eight studio themes derive everything from
  one hue — that is what makes each read as a single decision. The console is
  the deliberate exception: warm paper, navy ink, one deep amber marker.
* **Anchors.** `#F7F5F2` / `#0E1729` / `#A16207` are the platform's identity
  and are already on production, so the console spec pins those three and
  solves the other thirty-six around them. Three declared values with 61
  assertions is a different thing from forty-five with none.
* **A fourth semantic role, `info`.** It was already in the product, unnamed:
  eight hand-picked purple/violet/sky values doing the "notice that is neither
  good nor bad" job.
* **Quiet forms.** Every role now ships `--x-soft` / `--on-x-soft` /
  `--x-border` as *measured distances* (tint 1.22 from the panel, border 1.45
  from the tint), replacing fourteen hand-picked `-light` / `-soft` / `-line` /
  `-wash` / `-deep` variants with four different naming schemes.
* **`--on-accent-muted`.** Secondary ink for an accent-filled region. Its
  absence is why the console's header subtitle and three nav links used
  `--disabled-text` — solved to 3:1 against a *light* disabled surface — and
  measured 3.4:1 and 3.6:1 on the navy header.
* **`CEILINGS`.** Upper bounds, because "too loud" is as wrong as "too faint",
  and the v8.3.0 alt-band failure was the former.

## Dark mode: the three categories a palette cannot reach

Every colour was solved and asserted, and the dark tenant page still rendered
wrong, because these are not colours in the palette:

1. **Native chrome.** `color-scheme` was declared on date inputs only.
   Measured on production at v8.3.1: `getComputedStyle(:root).colorScheme` was
   `normal` on a portal carrying a dark theme — 11 text inputs, 2 selects, 2
   checkboxes, a textarea and the scrollbar all drawing light chrome on a
   `#15120D` page. None of them reads a custom property.
2. **Literals.** `.totop` was `rgba(251,249,244,.9)` under `color: var(--ink)`.
   On the eight dark themes `--ink` is light, so the arrow measured **1.26:1**
   against its own button — in the DOM, clickable, invisible.
3. **Browser chrome.** `<meta name="theme-color">` pinned to `#F4F0E8`, never
   updated. A dark studio got a cream address bar over a near-black page.

And a fourth that is not a surface but a scope: **an inverted band inverts its
whole vocabulary.** The portal's `.parent` section uses `--ink` as a
*background*. Its own children were written as `color-mix(--bg, --ink)` pairs
and were correct; two global classes dropped inside were not. `.eyebrow`
measured 2.40:1 dark, and `.arw` measured 1.84:1 dark / **2.02:1 light** — so
the arrow in the section that asks a parent to sign in had never cleared 3:1 in
either mode.

## A fallback is a hardcoded colour with a longer fuse

`admin-i18n.js` injects the language switch from a JavaScript string, and the
rule said `var(--brand, #3b82f6)`. When the consoles moved from `--brand` to
`--accent` the token stopped resolving and CSS did exactly what it should: it
used the fallback. The switch went on painting itself Tailwind blue-500 in the
middle of a navy console — white on it measures 3.68:1, below the floor — with
every stylesheet assertion still green, because the rule lives in a `.js` file.

The same shape appeared in `cms-i18n.js` (`var(--accent, #4f46e5)`) and in
`brand-system.css`, whose last-resort chain still ended in `#a65a43` clay and
`#f4f0e8` paper — a palette from a product that no longer exists. All now chain
to another token.

## Who decides light or dark

The studio, by default. A studio may hand the choice to the visitor
(`scheme_preference: system`), which the API refuses — and the console disables
— for a theme that ships one mode: `arcade-lime` is dark only because its
accent turns olive on a light page. Following the visitor publishes **both**
palettes, because the page cannot fetch the other one when the OS setting
changes mid-visit.

**The consoles are light only.** Decided 2026-08-05: they are worked in
daylight against warm paper, and a second mode would double the surface area of
every console change for a use nobody asked for.

## The hero photo

Six tenants, `hero_image_url` empty on all of them. Upload existed. The chain
broke in three places: `uploadWebsiteImage()` filled the URL field and stopped
while Hero Style three fields below still said "Soft Art Board"; the public
page only adds `body.hero-image` when the style is `image`; and the console
preview never drew the photo, so there was no feedback at any point. Upload
succeeded, Save succeeded, Publish succeeded, no photo.

Uploading now selects the style that shows it. The dropdown said "Image
Background", which promises a full-bleed hero and delivers a 4:5 panel — it
says "Photo panel".

## The lab and the spec, generated

`docs/design/theme-proposal.html` is 1009 hand-written lines showing eight
themes in light and dark, and since v8.3.0 the dark half has been wrong — it
still shows the inverted surfaces that release replaced. Nothing failed. It now
carries a SUPERSEDED banner and a test asserting it.

Replaced by two generated artefacts, both regenerated and diffed by
`test_design_lab.py`:

* **`docs/design/lab.html`** — 16 theme-modes × 47 components, 41 assertions
  live per theme, and a **Tune** mode whose sliders move the generator's
  *inputs* and re-solve through `docs/design/solver.js`. Never a hex: a lab
  that lets you nudge a hex is a fifth hand-built palette inside a week, which
  is precisely what the proposal became. A "copy THEMES entry" button prints
  the pasteable spec, which closes the loop back to `palette_gen.py`.
* **`docs/design/Design_System.md`** — the token table, the worst measured
  value of every asserted pair across every theme-mode, the scales, and the
  rules with the defect each one exists to prevent.

The JS solver is a second implementation of one algorithm, so
`test_design_lab.py` runs it under node against the Python: 688 tokens across
the shipped themes plus a 36-point hue × saturation grid, token for token. It
earned its keep on the first run — one disagreement, and the JavaScript was
right: `disabled_text_color` was reading the *paper* hue in Python while every
other text token read the ink family. Invisible until a theme split the two.

## Measured, on the running pages

```
studio-admin   135 text nodes, 0 contrast failures  (2 real before: --line-strong
               as chip text 3.67:1, --muted on a --line background 4.01:1)
super-admin     89 text nodes, 0 contrast failures  (4 real before, all
               --disabled-text on the navy header at 3.4–3.6:1)
tenant portal   15 theme-modes swept, 0 failures, every reading stable
language switch 3.68:1 Tailwind blue → 17.90:1 navy
.totop          1.26:1 → 15.78:1
colorScheme     normal → light / dark, following the theme
ink family hue  220 / 221 / 220 (navy)      paper family hue 36 / 38 / 35 (warm)
```

## Two ways I measured wrong before I measured right

Both worth knowing, because both produce confident, false numbers.

* **`color-mix()` computes to `color(srgb 1 1 1 / 0.92)`** — 0–1 floats, not
  0–255. A probe reading `[\d.]+` treats white as `rgb(1,1,1)`, near-black, and
  reports 11 contrast failures on a console that has none. A gradient is also a
  surface: reading only `backgroundColor` walks straight past a navy header and
  calls white-on-navy 1.08:1.
* **Setting many custom properties and reading computed styles in the same
  synchronous block gives stale values.** Two `requestAnimationFrame` waits
  were not enough for a deep `var()` chain; 220ms was. The tell is that the
  same element fails in light on one pass and dark on the next. Read twice — a
  differing pair is a race, not a defect.

## Honestly not done

`legacy-root/index.html` + `cms-app.js` (the operations CMS) still carry ~74
literals, and `product-home.html` / `manual.css` / `customer-resources.css`
~76 more. The marketing and documentation pages are arguably a separate
identity; **the CMS is not, and is the next surface to convert.**
`TOKENISED_SURFACES` in `test_dark_framework.py` names the nine that are done
rather than globbing, so this gap is visible instead of implied.

## The change worth considering next

**HSL → OKLCH.** The solver binary-searches lightness in HSL to hit a measured
WCAG ratio, and HSL's L is perceptually uneven — every `min(s * .30, .20)` cap
in the file is compensating for it. In OKLCH "muted is one step lighter than
body" is a constant rather than a search, and the tint and hover steps become
genuinely uniform across hues.

Deliberately **not** done here: it moves the values of all 16 theme-modes, and
doing it in the same release as the console rewrite would leave any regression
unattributable. The lab is the tool that makes it safe — 16 theme-modes side by
side with the assertions live — and it now exists.

---

# PWE Studio v8.3.1 — the console gave back half a screen, and eight dark themes were upside down (deployed 2026-08-04)

> Shipped as 8.3.0, corrected twice, released as **8.3.1**. The second
> correction had to carry a new version number rather than redeploy 8.3.0,
> and that is worth understanding before the next in-place fix:
>
> Versioned assets are served `public, max-age=31536000, immutable` when
> `?v=` matches `APP_VERSION`. Redeploying under the same version leaves the
> URL `/assets/admin-i18n.js?v=8.3.0` unchanged, so **every browser that
> loaded the console during the first 8.3.0 keeps the first 8.3.0 dictionary
> for a year.** Measured on production: the versioned URL still answered
> without the new entries while an unversioned fetch of the same file had
> them. A corrected asset needs a new version, not a redeploy.

Five things, all on one page and its data, done together because they are one
page: the space the Website & Brand console spent on itself, the dark palettes
it publishes, the industry copy it starts a studio with, the phone, and the
half of the interface that stayed English when you switched to Chinese.

Each was measured before it was changed. The numbers below are from the running
page, not from reading the CSS.

## P0 — the console spent 574px of a 900px screen before the first control

Measured at 1440x900, top of `.brand-step`:

| layer | desktop | phone 390x844 |
|---|---|---|
| header-top (brand + 7 buttons) | 102 | 304 |
| nav-bar | 57 | 59 |
| section header `官网与品牌` | 55 | 97 |
| workbench hero `打造工作室的公开品牌体验` | 137 | 205 |
| studio-tabs | 57 | 57 |
| panel heading `品牌基础` | 61 | 81 |
| **to the first control** | **574** | **906** |

The same label appeared four times on the way down: nav item `官网与品牌` →
section header `官网与品牌` → hero `打造工作室的公开品牌体验` → tab `品牌` →
panel heading `品牌基础`. Draft state was published twice, in two wordings:
`workbenchStatus` said `已保存` while `saveBarStatus` said `没有未保存的更改`.
`Open CMS` existed three times at once — a header button, a nav link, and a
Public Pages card with a URL and a health check.

**What changed.** The hero and the settings section header are deleted. The
header is one row carrying brand, nav and account; identity, tenant slug,
password change and sign-out moved into a `<details>` account menu, and the two
header buttons that duplicated the nav are gone. One draft readout, in the save
bar. `--header-h` is measured by `syncHeaderOffset()` instead of the
hand-written `top: 136px`, because a wrapping row has no constant height.

**After: the first control is at 249px, and 85% of the viewport is live when
scrolled (was 75%).** φ is untouched — a layer was removed, no ratio retuned.

## P1 — all eight dark themes stacked their surfaces upside down

`palette_gen.py` built the dark surfaces by mirroring the light lightnesses
around mid-grey. Light puts the alternating band 0.047 *below* the page, so
dark put it 0.124 *above*. The distance survived; the meaning inverted. In a
dark UI lighter reads as nearer, so the band came out as the brightest surface
on the page — brighter than the cards resting on it, which then read as holes.

```
theme            mode    panel/bg  alt/bg  panel/alt  order (dim → bright)
atelier-clay     light       1.15    1.12       1.28  alt < bg < panel
atelier-clay     dark        1.17    1.43       1.23  bg < panel < alt   ← 8/8
```

The band's step off the page measured **1.39–1.61 in dark against 1.10–1.13 in
light.** On the tenant portal `--bg2` paints two full sections (790px, 733px)
and the footer.

**Why 26 contrast assertions per theme-mode were all green.** They check
legibility. Muted text on the band measured 4.60–4.65 in both modes — the
palettes were accessible and wrong at the same time. **Contrast cannot express
which surface should look nearer.**

**What changed.** The dark branch keeps its page dark and lifts the band
slightly, panel above both: `bg .068 → bg2 .102 → panel .150`, and `worst` (the
lightest surface a text token can land on) is the panel now, not the band. All
eight re-solved; `presets.py` verified token-for-token against the generator,
zero drift. Two new rules in `layer_faults()`: the panel is the nearest surface
in both modes, and the band's step is within 1.6× of the light-mode step.

**`test_the_rule_rejects_the_pre_v830_surfaces` rebuilds each dark theme with
the three lightnesses that shipped and asserts all eight are rejected.** Without
it the rule could later be relaxed into something that passes on both.

Also deleted: the `@media (prefers-color-scheme: dark)` block in
`brand-system.css`. It never took effect — `/brand` writes 34 tokens inline on
`:root`, and inline beats a stylesheet, so it was overridden on exactly the
pages it was for; on the admin surfaces all 62 fields measured `#0E1729` on
`#FFFFFF` with the OS in dark. Dead, but a trap: any page later styling itself
from `--brand-paper` without inlining would have had paper and ink flipped by
the visitor's OS while its accents stayed solved for light. **A studio's theme
decides light or dark. The visitor's OS does not get a vote.**

## P2 — the card promised one headline, the site published another

`slogan` is what the industry card renders. `hero.title` is what the published
site renders. Two hand-written strings per industry, and **in Chinese five of
the eight had drifted**:

| | card (`slogan_zh`) | published (`hero.title.zh`) |
|---|---|---|
| 艺术 | 大胆创作，让成长看得见。 | 让创意被看见，让成长有作品。 |
| 音乐 | …让每次练习都**算数**。 | …让每次练习都**有回应**。 |
| 数学 | 理解方法，建立长久的信心。 | 理解方法，建立信心，稳步进阶。 |
| 舞蹈 | 自信地舞动，在训练中成长。 | 在节奏中表达，在训练中成长。 |
| 游戏与编程 | 在**玩**中思考、创造与升级。 | 在**游戏**中思考、创造与协作。 |

In English `slogan == hero.title` for all eight, so the fork was invisible to
anyone reading the source in English.

`hero.title` is **derived** from the slogan now, and a literal `title` back in
the preset dicts fails a test — correcting five strings would have left the
fork open.

**Register page copy.** `tenant-template/register.html` falls back to
`告诉我们学员的情况` / "Tell us about the student" under an eyebrow that already
says Quick Registration. The Chinese presets followed that voice; the English
ones were noun labels ("Creative Preferences", "Music Goals") that read as a
form section and never mention registering. All eight English headings rewritten
to match. Both languages' leads rewritten so they name the questions and the
outcome instead of restarting the heading: `告诉我们…` / "Tell us about…" ×8
became `三个关于创作形式、经验与目标的问题，之后画室会推荐合适的课程与时间。`
and its seven siblings. `Game` → `Games & Coding` (the English label had dropped
编程, half the offer); `Math` → `Maths`, matching the product's own spelling.

## P3 — the phone pinned nothing

**94 controls under 44×44** (nav-link 38, studio-tab 36, header buttons 43), the
first field 906px down, and `.header` **and** `.save-bar` both
`position: static` in the mobile block — the tab you were editing under and the
Publish button both scrolled away.

Two rules were doing most of the damage, and both sat in the page's own
override block where they beat the base rules: `button { min-height: 38px }`
and `input, select, textarea { min-height: 42px }`. Raising the base alone would
have changed nothing.

**After, at 390×844: 0 undersized controls across all eight tabs, no horizontal
overflow, first control at 320px.** The tab strip and the publish bar are
sticky, the bar padded with `env(safe-area-inset-bottom)`. `.settings-panel`
had to lose `overflow: hidden` first — it makes an ancestor a scroll container,
and a sticky child of one never sticks to the viewport.

## P4 — the console spoke Chinese and hinted in English

`applyAttributes()` in `admin-i18n.js` has always localised `placeholder`,
`title` and `aria-label`. **26 of them had no dictionary entry**, so every field
on a Chinese console still hinted in English. Found by walking the rendered
document; the dictionary cannot report what it was never told about.

Down to 3, all deliberate: `owner@studio.test`, `studio@example.com`,
`https://...` — worked examples a Chinese reader types verbatim. Entries for
copy this release deleted (`Brand Builder`, `Shape the public studio
experience`, `Saved`) were removed rather than left behind.

Visible text was already clean: the only untranslated strings are the language
switch, the tenant slug, the eight English industry sub-labels (bilingual by
design) and the producer credit.

## Two things the first cut of this release got wrong

Both were caught by measuring the deployed page rather than by reading the code,
and both are recorded because the reasoning that produced them was wrong, not
just the output.

**The switch had a hit area that did not exist.** The first attempt kept the
26px track as the control and laid a transparent 44px `::before` over it. The
comment said that extended the target. It does not: Chrome does not hit-test a
form control's pseudo-element as the control. Probed on the deployed page, the
hit area came back **1px** tall against a 44px `::before`. The control is 46x44
now and the *track* is the pseudo-element, which measures 45px of hit area.
**The box that has to be 44px is the box the browser dispatches the click to.**

**`No unsaved changes` was translated and `Unsaved changes` was not.** The
lookup is exact, so the save bar reverted to English the moment anything was
edited. The attribute sweep could not have found it — the string is written by
script and never appears in the markup. Nine runtime messages were missing;
`test_every_runtime_message_has_a_chinese_translation` now scans the three calls
that put words in front of a person (`.textContent`, `showToast`,
`setLoginError`) and fails on all nine against the first cut.

A related caution for anyone measuring this page: `getBoundingClientRect()` and
`offsetParent` both report a live box for an element clipped inside a closed
`<details>`, so a sweep that trusts them counts controls nobody can see. The
first pass at proving the touch targets did exactly that.

## Verification

**1170 tests pass** (was 1147), 3 skipped. Three checkers pass. Three new files:

- `test_theme_layering.py` (39) — layering in both modes, presets↔generator
  parity, and the reconstruction check above.
- `test_preset_copy.py` (51) — the fork, the derivation, register-page voice,
  bilingual completeness.
- `test_studio_console.py` (20) — chrome budget, the 44px floor, the sticky
  phone rules, and every authored hint and runtime message having a Chinese
  entry.

**Every one of these was run against the v8.2.31 files before being trusted.**
`test_studio_console.py`: **16 of 20 fail** on the previous release. The layering
rule: **8 of 8** dark palettes rejected. The copy rules: 5/8 forks, 8/8 headings,
8/8 leads, 1/1 label. A test that passes on the code it was written to reject is
not a test — that is the v8.2.30 lesson, and it is applied here rather than
recited.

## Not done, and why

- `seed_random_demo_data.py` and `reset_professional_demo.py` keep their own
  bespoke `copy_pack` strings. They are demo fixtures representing a studio that
  has written its own copy, which is the path those fields exist to support.
  Left alone deliberately, not overlooked.
- Whether the subscription settlement should ever run unattended is still the
  owner's call, unchanged from v8.2.30.
- `/sitemap.xml` still needs submitting to Google Search Console.
- The showcase password pasted into a chat transcript still needs rotating.

---

# PWE Studio v8.2.31 — sixty-five lines of my own JavaScript, above the doctype (deployed 2026-08-04)

The owner opened the console and found a wall of source code across the top of
the page. It was mine, it went out in v8.2.30, and it was visible on
production for about twenty minutes.

## What happened

The v8.2.30 edit that replaced `validateSubscriptionDates` was scripted:

```python
old = t[t.index("/* The four dates have to describe a period…"):
        t.index("/* A subscription date field.")]
t = t.replace(old, new, 1)
```

`dateField`'s comment sits **earlier** in the file than
`validateSubscriptionDates`, so `end < start`, so the slice was `""` — and
`str.replace("", new, 1)` inserts at position 0. Sixty-five lines of
JavaScript landed above `<!DOCTYPE html>`, where the browser rendered them as
text, and the function they were meant to replace stayed exactly where it was
and kept running.

So the release had two faults at once: source code printed across the console,
and the pairwise date validation it was supposed to ship **never ran**. The
start-only check was still the live one.

## Why nothing caught it

The test written for that change:

```python
assert "SUBSCRIPTION_DATE_FIELDS.slice(index + 1)" in source
```

`source` was the file. The string was in the file. It was above the doctype,
outside the script, doing nothing — and the assertion passed. **A test that
cannot tell running code from a decorative string is not testing the thing it
names.**

Three checkers passed too. The inline-script checker parses what is inside
`<script>`; it has no opinion about what is outside one.

## The fix, and the guard

The block is removed and the corrected function installed where the old one
actually lived — one definition, inside the script. Then:

* `script_source()` in the tests extracts only `<script>` contents, and every
  assertion about JavaScript behaviour reads from it rather than from the file.
* `test_nothing_precedes_the_doctype`.
* `test_each_function_is_defined_once_and_inside_the_script`, parametrised
  over the seven functions this work touched — two definitions means one is
  dead, and the dead one is the one you were reading when you decided the
  behaviour was correct.

Both new tests were run against a reconstruction of the exact accident and
both fail on it.

## Verified on the running page

```text
document starts with <!DOCTYPE html>        yes
source visible to a reader (innerText)      no
stray text nodes under <body>               none
validateSubscriptionDates definitions       1, inside <script>
cancellation 2028 vs period ending 2029     refused: 「取消或到期 早于 当前周期结束」
the offending field                         aria-invalid="true"
```

That last row is the case from the owner's screenshot, and it is the check
that v8.2.30 was supposed to deliver and did not.

## The lesson worth keeping

Two scripted edits in this session have now gone wrong in the same family of
way — a `str.replace` whose anchor did not mean what I assumed. `replace("")`
is the sharp one: it silently prepends instead of failing. Anchored slice
edits need `assert end > start` before they are used, and any test written for
an edit to a page must assert against the code that runs.

---

# PWE Studio v8.2.30 — the save that never saved, and dates that meant nothing (deployed 2026-08-04)

The owner reported that editing any existing studio showed "Internal Server
Error". It did, and had since **10 July** — twenty-five days. The cause is not
in anything the last two releases touched.

## Every edit of an existing studio 500'd and wrote nothing

```python
if user_id:                       # this studio already has a Studio Admin
    if email_owner and ...:       # a different user owns that address
        user_id = ...
    elif password:                # a new password was typed
        UPDATE users SET ... password_hash ...
    else:                         # reachable ONLY when password is empty
        if not password:          # ← therefore always true
            raise ValueError(...) # ← therefore always fires
        UPDATE users SET email, full_name ...   # ← unreachable
```

`elif password` had already consumed the truthy case, so the `else` was the
empty-password branch and its first line was a guard against an empty
password. The `UPDATE` beneath it — clearly the intended behaviour, change the
name and address and leave the credential alone — could never run. The raise
was a copy of the create-path guard that landed in the wrong branch
(`17b4497`, 2026-07-10).

**It failed safe, by accident.** The raise happens before the subscription
upsert and before `commit()`, so the whole transaction rolled back. Twenty-five
days of saves that reported an error and changed nothing. Production data
confirms it — all four trialing subscriptions still hold every date:

```text
status      rows  starts_at  trial_ends_at  current_period_ends_at
active        2       2            0                  2
trialing      4       4            4                  4
```

Which also means the date-clearing defect fixed in v8.2.29 never reached the
data: this bug was standing in front of it. **Two defects cancelling out is not
a safety property**, and both are asserted now.

## A business rule arriving as a fault

The route's `try/except ValueError` wrapped only `_tenant_write_payload`, not
the work inside the transaction. So "you need to set a password" reached the
operator as **Internal Server Error** — a sentence they can act on, delivered
as one they cannot. The transaction body is wrapped now and answers 400 with
its own message.

Unhandled 500s carry a short reference (`secrets.token_hex(3)`) logged beside
the traceback. Hiding internals is right; leaving the person at the screen with
nothing to quote is not.

## The other half of that branch

With no password and no existing account, the code did
`INSERT INTO users (password_hash = hash(""))`. `/auth/login` refuses an empty
password before verifying anything, so this was never a way in — it was a row
that **looks** like an account and is not one, which the onboarding checklist
then ticked as "Studio Admin login configured". The checklist was lying. It
now refuses and points at the password-setup link flow that already exists.

## The dates meant nothing

Nothing in this product read a subscription date and compared it to today. No
scheduled job, no expiry check, no code path anywhere. A trial could end, a
billing period could lapse and `ends_at` — the cancellation date — could pass,
with the studio keeping every feature and the console showing green. For a
product sold by subscription that is the centre of the thing, unenforced.

**Three additions, in order of how much they touch:**

1. **`validate_subscription_dates`** in `lifecycle.py`, beside the rules that
   were already there. Every pair in order, not each date against the start —
   the owner's screenshot showed a cancellation dated 2028 against a period
   ending 2029, which a start-only check accepts. Plus: `trialing` must have a
   trial end, `cancelled` must have a cancellation date. Both write paths call
   it. A date the caller did not mention is not checked, because not
   mentioning something is not a claim about it.

2. **`services/subscription_settlement.py`** — what the dates say has already
   happened. It **reports**; it does not cut anybody off. A studio losing
   access because a job ran overnight is a support incident and a broken
   promise. And it obeys the existing state machine rather than inventing
   moves: a lapsed trial is **never** applied automatically, because
   `trial → past_due` is not a legal transition *and* "did they buy?" is a
   commercial question. Two reasons, same answer. Applying is opt-in
   (`{"apply": true}`), goes through the same `validate_tenant_transition` the
   manual route uses, and writes its own audit row. Idempotent by
   construction — findings come from current state.

3. **A "Dates Passed" card** on the overview, loading with everything else.
   A count nobody sees until they open a menu is a count nobody sees.

## What the screenshots showed, fixed

* **`Sta2026-08-03`** — label and value overlapping, and «试用结束» wrapping one
  character per line. The row was a flex with `flex: 1` on the label, so in a
  200px card it squeezed to nothing. It is a container-query grid now.
* **A red "1 天前已过" on the subscription start date.** My error from v8.2.29:
  any past date read as overdue. **Only a deadline can be overdue** — a start
  in the past is what "this has begun" looks like, and colouring it red said
  every healthy studio needed attention.
* **`Start` untranslated**, the one date label that never got an entry.
* Danger Zone was a fold hiding one sentence that pointed elsewhere; it is
  that sentence plus the door.
* A fold holding an unsaved change now carries an amber dot.

## Verified

1046 tests pass; three checkers pass. Against a real database, every rule
end to end:

```text
ordinary edit, no password        200   (was 500 for 25 days)
period end before the start       400   names both dates
cancellation before period end    400   names both dates
trialing with no trial end        409   refused by the transition matrix first
a coherent set                    200
```

## Still to do by hand

* Submit `/sitemap.xml` to Search Console (from v8.2.28).
* Rotate the showcase password that was pasted into chat.
* **Decide whether the settlement should ever run unattended.** It is manual
  by design today. Automating it means agreeing what a lapsed trial is worth,
  which is a commercial decision, not an engineering one.

---

# PWE Studio v8.2.29 — the platform console, and two ways it was losing data (deployed 2026-08-04)

A UI/UX pass over `/platform-admin` that started as five batches of design
work and turned up two silent data-loss defects on the way in. Both had been
live for weeks. Neither is visible from the code alone; the first was found by
reading a screenshot of the running modal against the API's actual output.

## The subscription dates were being wiped on every save

```text
API      jsonify(datetime)        → "Wed, 29 Jul 2026 00:00:00 GMT"   (RFC 1123)
page     String(v).slice(0, 10)   → "Wed, 29 Ju"                      (assumes ISO)
input    <input type="date" value="Wed, 29 Ju">  → invalid, renders EMPTY
save     $('m_startsAt').value || null            → null
database starts_at = EXCLUDED.starts_at           → NULL
```

Open a studio, change a phone number, press Save: all four subscription dates
gone. The `Wed, 29 Ju` visible in the detail modal was the same bug wearing
its other face — one defect, two symptoms, and the ugly one was the harmless
one.

`dateOnly` now parses and reads **UTC** components. Deliberately UTC: these
are calendar dates and the server sends GMT midnight, so taking local parts
would walk every date backwards by a day for any operator west of Greenwich,
once per save.

## And a second, independent path cleared the trial end

The form never sent `trialEndsAt`. The server read all four dates with
`payload.get(...)`, where an absent key and an explicit null are the same
thing, so **every tenant save wrote NULL over `trial_ends_at`** — the column
the trial state and the expiring-trial counter are both read from.

Two fixes, because either alone would leave the hole open for the next caller:
the form sends the full set, and `_subscription_date` returns a `KEEP`
sentinel for a key nobody mentioned, which the upsert honours per column with
`CASE WHEN %s THEN subscriptions.<col> ELSE EXCLUDED.<col> END`. An explicit
null still clears. `or`-chaining was wrong twice over — an empty string is
falsy, so a deliberate clear fell through to the snake_case key.

## The detail view rendered seven fields twice

`tenant-summary` and `detail-grid` were both being appended, overlapping on
studio, status, subscription, plan, category, student usage, storage and owner
email. It is five tabs now — Overview, Subscription & Billing, Contacts,
Usage, Operations — with a status bar **outside** the tab strip, because
health and quota are the two readings you want no matter which tab answers
your question. Arrow keys, Home and End drive the tablist.

Tabs rather than folds for the detail view, folds for the edit form: one is a
reading surface where the operator already knows which kind of question they
have, the other is a sequence of things to fill in. The folds now carry a
reading of their own contents, so a collapsed form is still scannable.

The same modal printed `20 MB / 50 GB` in one block and `20 / 51200` in
another. Every quota figure goes through `quotaParts` now.

## Light, and finally the family identity

The console sat on Family Warm Paper `#F7F5F2` with cold blue-tinted slate for
every neutral above it and a generic Tailwind blue as the brand. Warm ground
under cold furniture is the disharmony an operator feels before they can name
it.

Light on purpose — this is read for hours. Navy became ink rather than a
surface; amber is the single accent, and on a light ground that means the
**dark** amber, because Family Amber measures 1.70:1 on paper and can only be
a fill with navy on it (9.70:1). Purple is gone: it coloured one KPI stripe
and named a meaning nobody could say out loud.

The token block was the easy half. The test found **eighteen raw cold hex
values** still hard-coded in components — the drift the check exists to catch,
caught on its first run.

* **Spacing** 4/8/12/16/24 → **5/8/13/21/34/55**, the same Fibonacci generator
  as the marketing site and the manual, taken at its low end.
* **Type** twelve ad-hoc sizes → **13 / 17 / 21 / 27 / 34**, each step
  φ^(1/2). Two of those land on Fibonacci integers, which is what happens when
  both come from the same ratio. `--f-min: 12px` is deliberately off the
  ladder — the rung below 13 is 10.2px and this console is read in Chinese.
  That also retires the 11px that was in use, below the floor already.
* **61.8 / 38.2** on the Overview tab.

## Plan editor

Storage is edited in **GB** (51200 was not a number anyone could check).
Entitlements are grouped by who feels them, each with a line saying what it
turns on. The publish controls moved to the **top** with a live preview of the
row a visitor would read — they are the only controls on the page that change
the public website on save. Saving a limit now warns which studios would be
over it immediately. The JSON escape hatch stays, because a flag added
tomorrow has to be reachable, but it validates as you type instead of throwing
after the operator has left the field.

## Verified

1018 tests pass; all three checkers pass. On the running page, with a
synthetic tenant: 0 contrast failures, 0 text under 12px except the 10px
Latin-only producer credit its own brand spec caps, 0 touch targets under
32px, and every new string translating. The header's white-on-navy measures
6.10:1 at its worst stop.

Two things worth remembering:

* The first version of the contrast probe reported three failures in the
  header. All three were false: it walked for `background-color` and the
  header paints a `linear-gradient`, which is a background *image*. Measured
  against both gradient stops directly, everything passes.
* The immutable asset caching added in v8.2.28 means editing an asset without
  bumping the version leaves the browser holding it for a year. Correct in
  production, where a release always changes `?v=`; during development it
  needs a forced revalidation.

## Still to do by hand

* Submit `/sitemap.xml` to Search Console (from v8.2.28).
* Rotate the showcase password that was pasted into chat.

---

# PWE Studio v8.2.28 — what the site was telling machines about itself (deployed 2026-08-04)

The marketing skills from `coreyhaines31/marketingskills` were installed and
their `seo-audit`, `ai-seo` and `copywriting` frameworks run against
production. The audit found three real defects, all of which had been live for
weeks and none of which was visible from a browser.

## The three defects, and why nobody saw them

**Every `.webp` was served as `application/octet-stream`** — including the one
named by `og:image`. Browsers sniff the bytes and render the image anyway,
which is exactly why the pages looked correct; social crawlers do not sniff,
so a link shared to LinkedIn, X, WhatsApp or WeChat showed a card with no
picture, and Google Images could not index a single manual screenshot.

The cause: `send_from_directory` takes its Content-Type from `mimetypes`,
whose table is the interpreter's built-ins plus `/etc/mime.types` — a file
`python:3.11-slim` does not ship. The types are registered by the application
now, so the answer is a property of this codebase rather than of whichever
base image it runs on. Asserted per extension.

**Every static asset was sent `no-cache`.** The manual re-downloaded 502 KB of
screenshots on every single view, paid directly on the largest contentful
paint. Every asset URL already carried `?v=<APP_VERSION>`, so the URLs were
already safe to cache forever — the header just never said so. A URL naming
the running release now gets a year and `immutable`; a stale one revalidates.

**There was no `robots.txt` and no `sitemap.xml`.** Both 404ed. Nine addresses
were discoverable only by following links, the hreflang set existed in the
markup alone with nothing corroborating it, and the Search Console submission
that has been on the to-do list had nothing to submit.

## What else the audit turned up

* **The manual had no structured data at all** — the most citable thing the
  site publishes (3,800 words, first-hand, specific) and nothing marked its
  seven questions as questions or gave it a date.
* **Four customer documents served both languages from one URL** behind a DOM
  toggle, with no canonical and no hreflang — the arrangement the home page
  and the manual were moved off two releases ago. The Chinese half of the
  terms, the privacy policy and the service FAQ had no address that could be
  indexed, linked or pointed at.
* **`"User Manual | PWE Studio"`** was a 24-character title in front of those
  3,800 words, targeting nothing.
* **The FAQ, terms and privacy pages asserted product facts against `v8.2.2`**
  — six releases stale, on a live page, with nothing checking it.
* **A nested duplicate `<picture>`** in the nav brand mark, from an earlier
  edit.

## The rule that keeps the FAQ markup honest

`FAQPage` has exactly one failure mode: markup that does not match the visible
answer. A hand-maintained copy in Python agrees with the page only until the
next edit to the page, so there is no copy — `faq_pairs()` parses the
questions back out of the document that is about to be sent. That reorders
`_serve_product_home`: cards, then filter, then structured data, because the
structured data now reads the filtered document. The placeholder survives
filtering because it is a comment.

The same extractor serves the manual (`<h4>` + `<p>`, scoped to `#faq`), the
home page and the service FAQ (`<summary>` + `<p>`), which is why all three
got markup for the price of one.

## Machine-readable files

`/pricing.md` and `/llms.txt`, generated from the same plan rows as the
pricing cards. An agent shortlisting tools for a studio owner reads what it
can parse and silently skips what it cannot — the buyer never learns there was
a third option. This product's numbers are public, enforced and already
generated; the only thing missing was an address a parser could reach them at.
`SETUP_FEE_AUD` now holds the 299–999 range so the page prose and the markdown
file are asserted against one number instead of three.

## Copy

The page reads well — specific, customer's own words, no buzzwords — so the
changes are few and structural:

* **The scope exclusions moved off the conversion path.** Six clauses of
  what-is-not-included sat between the price and the button, the last thing a
  buyer read before deciding. They are an FAQ answer now, verbatim: the
  content was right, the position was wrong. The test that guards them was
  rewritten to tell a move from a deletion.
* **A new FAQ section** before the final call to action, splitting 61.8/38.2
  like the hero — answers in one column, the standing invitation in the other.
  There is no trial and no money-back guarantee to offer, so the risk reversal
  is the only honest one available: everything a buyer would want is already
  public, including what has not been built. Inventing a guarantee would have
  been easier and worse.
* **`Discuss Starter` → `Start with Starter`.** The old verb asked the reader
  to do the thing they were trying to avoid.
* Descriptions brought inside the space a result actually gives them — the
  English ones were losing their last clause at 195 characters, the Chinese
  ones were using half of theirs at 64.

## The deploy failed first, and what that was worth

The first attempt built, uploaded, switched and rolled itself back. One line
in `_jsonld_script` put a **backslash inside an f-string expression** — legal
from Python 3.12 (PEP 701), a `SyntaxError` before it. Development runs 3.14;
the production image is `python:3.11-slim`. The container could not import
`server` at all, deep health failed, and the deploy reverted to v8.2.23 with
the site healthy throughout. The rollback did exactly its job on a defect that
652 passing tests, three checkers and a successful bundle build could not see,
because every one of them ran on the wrong interpreter.

Two checks now run against the floor the Dockerfile pins
(`test_python_version_floor.py`):

* `ast.parse(feature_version=...)` over all 144 modules — rejects grammar
  newer than the target: match statements, `except*`, PEP 695 generics.
* a walk of every expression interpolated into an f-string, looking for a
  backslash.

**The second exists because the first does not catch this.** `feature_version`
constrains the parser, not the tokenizer, and a 3.12+ tokenizer reads PEP 701
f-strings before the parser is consulted. The first version of the test
claimed a guarantee it did not provide; that was caught by trying it against
the offending line rather than assuming. A self-test now pins the detector to
the exact expression that caused the rollback, and it was run against the
committed `e3a9262` source to confirm it fires there and is clean after the
fix.

Neither replaces building on the target image. They are what can be asserted
without one, and the honest ceiling of this check is worth remembering the
next time something passes locally and dies on the instance.

## Verified

940 tests pass; all three static checkers pass. `check_manual_print.py` still
reports 18 and 15 pages, so the print work from v8.2.23 is intact. The FAQ
section measures 61.8/38.2 exactly, `align-items: start`, summary rows 71px
against a 44px minimum, and contrast in both themes: 16.45:1 summary, 6.96:1
answer, 4.52:1 links and marker in light — the amber that was drawn for it.

Confirmed on production after the deploy (`8.2.28-7962ff39bb54`):

```text
/robots.txt /sitemap.xml /pricing.md /llms.txt        200
all 14 sitemap URLs                                   200
og:image                                              image/webp
/assets/manual/*.webp?v=8.2.28   public, max-age=31536000, immutable
/            SoftwareApplication, Organization, FAQPage(6)
/manual/     TechArticle, Organization, BreadcrumbList, FAQPage(7)
FAQ.html     Organization, BreadcrumbList, FAQPage(13)
manual print 18 / 15 pages, unchanged
```

## Still to do by hand

* Submit `/sitemap.xml` to Search Console. There is finally something to
  submit; the nine addresses no longer need to be inspected one at a time.
* Rotate the showcase password that was pasted into chat.
* The sister site still advertises 1500 students / 100 GB against the
  database's 1000 / 50. It is built from `02 WEBSITE/src/build.py`, which is
  not reachable from this repository.

---

# PWE Studio v8.2.22–v8.2.23 — the print output, fixed against real PDFs (deployed 2026-08-04)

The owner printed both languages. Two defects the stylesheet and the screen
both hid, plus a third found while verifying the fix.

```text
                        before        after
English                 28 pages      18
Chinese                 25 pages      15
text over the footer    every full    none
                        page
```

## What was wrong, and what it cost to learn

**The running footer does not work in Chrome.** Two attempts, both measured:
`position: fixed; bottom: 0` anchors to the *text column*, so it printed on
the last lines of every full page; `bottom: -20mm` with a reserved `@page`
band landed at the *top of the next page*. A true running footer needs the
document wrapped in a table with `<tfoot>`. Abandoned, with the reasoning in
`manual.css` and a test that fails if `position: fixed` returns to the print
block — so nobody spends those two attempts again.

The browser's own print dialogue already stamps **URL, date and page number**
on every page. Only the version is beyond it, so version and licence are a
**colophon at the top of page 1**.

**`break-before: page` per section** was most of the white space — twelve
forced breaks plus figures that cannot split. Removed; figures capped at
118mm in print (58mm for phone captures).

**The date was stamped only by the Print button** (v8.2.23). Most people press
Ctrl+P, which never reaches it, so those copies printed a dash. Moved to
`beforeprint`, which covers every path.

## The tool

`backend/scripts/check_manual_print.py` renders both languages through
headless Chrome `Page.printToPDF` and reports page counts. Its first run
reproduced the owner's 28/25 exactly, which is what turned this from guessing
into measurement. Run it after touching the print block.

## Verified on production

Rendered `https://pwestudio.online/manual/` and `/zh/manual/` to PDF after
deploying: 18 and 15 pages, colophon present with v8.2.23, no overprinting.

## Still to do by hand

* Submit `/manual/` and `/zh/manual/` to Search Console.
* Rotate the showcase password that was pasted into chat.

549 tests pass.

---

# PWE Studio — the manual printed, and what that showed (2026-08-03)

The owner printed both languages. Two defects that neither the CSS nor the
screen could reveal, and a tool so the next change is measured instead of
guessed.

## What the paper showed

1. **Body text printed on top of the running footer.** Page 8 English, page 4
   Chinese — the last two lines of a full page overprinted the footer rule and
   its text, unreadable.
2. **Half the document was white space.** 28 pages English / 25 Chinese for
   3,800 words, including a page carrying two lines and nothing else.

## The tool

`backend/scripts/check_manual_print.py` renders both languages through
headless Chrome's `Page.printToPDF` with `preferCSSPageSize`, and reports page
counts. Its first run reproduced 28/25 exactly, which is what made the rest of
this a measurement rather than a series of guesses.

## The running footer does not work in Chrome, and is gone

Two attempts, both against real PDFs:

* `position: fixed; bottom: 0` — Chrome anchors it to the **text column**, not
  the paper, so it sits on the last line of every full page.
* `bottom: -20mm` with a reserved `@page` band — it landed at the **top of the
  next page**, over the first lines.

A true running footer in Chrome needs the whole document wrapped in a table
with a `<tfoot>`. That is a large change to buy a line of small print, and the
browser's own print dialogue already stamps **the URL, the date and a page
number on every page** — two of the three things the footer was for. What it
cannot know is the version, so that is now a **colophon at the top of page 1**,
with the rights notice, on the page a reader keeps.

Recorded in the stylesheet and asserted, so the next person does not spend the
same two attempts finding out.

## Pages

`break-before: page` per section is gone — twelve forced breaks plus figures
that cannot split is most of a ream. Figures are capped at 118mm in print
(58mm for phone captures); on screen they still fill the reading column.

```text
            before   after
English       28      18
Chinese       25      15
```

549 tests pass.

---

# PWE Studio v8.2.21 — the manual is live (deployed 2026-08-03)

`PWE-StudioSaaS-aws-8.2.21-3c11e55b556e`. Logical dump taken first
(`studiosaas_studiosaas_20260804T012835Z.dump`). Deep health passed from the
instance and the public edge.

## Measured live

```text
                      /manual/                     /zh/manual/
<html lang>           en                           zh-Hans
canonical             …online/manual/              …online/zh/manual/
hreflang              3 (reciprocal)               3 (identical set)
<h1> / sections       1 / 12                       1 / 12
figures / images      11 / 11                      11 / 11
data-lang left        none                         none
version stamped       yes                          yes
rights notice         yes                          yes
print footer          yes                          yes
```

`/manual` and `/zh/manual` 301 to the trailing-slash form. **Every referenced
screenshot fetched and returned 200** — the earlier blank frames were a server
process older than the `/assets/<dir>/<file>` route, not the images.

Unchanged and still 200: `/`, `/zh/`, `/v1/public/plans`, `/platform-admin`,
`/customer-resources/FAQ.html`, the showcase portal and its CMS. Both home
pages link the manual in their own language.

## Still to do by hand

* **Submit `/manual/` and `/zh/manual/` to Search Console.** Two more new
  addresses with no history, same as `/zh/` last release.
* Send the welcome pack to the next studio onboarded (`Welcome_Pack.md`,
  checklist Phase 2) — and the temporary password separately.

## Not done

Phase D's remaining item: **printing has not been exercised on paper.** The
stylesheet is asserted (contents removed, `@page` band, page breaks, link
targets written out, `[hidden]` forced visible) and the rules parse in the
browser, but nobody has produced an actual PDF and read it. That is the one
claim in this work I have not verified end to end.

548 tests pass. main and tag `v8.2.21` pushed.

---

# PWE Studio — read-through of both languages, then deploy (2026-08-03)

Read end to end in English and Chinese. Seven corrections, and one of them was
only findable by reading the Chinese *against the Chinese interface*.

## What was wrong

1. **"Five screens" over a table of four.** The fifth is the platform console,
   which the owner and I decided to keep out of a customer manual — the
   heading predated that decision. Both languages.
2. **The Chinese manual named English buttons.** `Save Draft` and `Publish`
   *are* translated in Studio Admin (保存草稿 / 发布), so a Chinese reader was
   being told to press something that is not on their screen. Six places.
3. **Two Studio Admin strings genuinely stay English** — `Restore to Draft`
   and `Improve colour contrast before publishing:` were missing from
   `admin-i18n.js`. Added, and the manual now names them in Chinese too. Same
   class of bug as the CMS sweep, found the same way.
4. **The register screenshot sat between two sentences about the pending
   queue.** Both visitor-facing surfaces now come first, then the queue they
   feed. (Moving it duplicated the figure on the first attempt — 12 figures
   instead of 11 — because the regex had already captured the indent I was
   also matching on. Caught by counting.)
5. **The ICS warning appeared twice**, near-verbatim, a screen apart. The
   pitfall keeps the explanation; the callout points at it.
6. **A callout repeated §01 word for word** about empty sections.
7. **The English access-code pitfall read as though the parent were entering
   their own child.** Rewritten in both languages, with the order of checks
   made explicit.

## What the read confirmed

* No stray English UI labels left in the Chinese manual. What stays Latin is
  deliberate: `PWE Studio`, `Portal`, `Register`, `CMS`, `Studio Admin`,
  `slug`, `ICS`, `CSV` — product and surface names, which the interface does
  not translate either.
* Every counted claim still matches the code: 30 log actions, 45 status
  colours, 30 megapixels, two-year audit retention, over 200 isolation checks.
* English 3,824 words; Chinese 7,579 characters.

548 tests pass.

---

# PWE Studio — the welcome pack (2026-08-03)

`docs/customer/Welcome_Pack.md`: the handover email, both languages, ready to
copy. Four addresses, change-your-password first, the manual deep-linked to
the four sections a new studio needs in week one, the import templates, and
what the platform can and cannot do inside their data.

**It is deliberately two messages.** The welcome email carries links and no
secrets; the temporary password goes by a channel the studio already uses. An
email thread is forwarded, quoted and kept for years, and a credential in one
outlives every reason it existed. That is the only part of the pack written as
a rule rather than a suggestion, and it is asserted — a well-meaning
"PS — your password is…" fails a test.

`test_welcome_pack.py` resolves **every link in the template against the
running app** (27 of them). A renamed route now fails a test instead of a
customer's first click. It also checks the placeholders all look like
placeholders, that both languages stand alone, and that the pack never
describes the manual as gated — it is public, and saying otherwise would be a
claim we cannot keep.

Onboarding checklist Phase 2 now has two lines: send the pack, send the
password separately.

548 tests pass. Still not deployed.

---

# PWE Studio — the manual reserves rights, and stays public (2026-08-03)

Decided with the owner after separating two things that were being conflated.

## Reserving rights ≠ hiding the link

**Reserving rights is a copyright statement**, and copyright does not depend on
a page being hard to find. So the manual now carries one, on screen and on
every printed page:

> © 2026 PWE GROUP PTY LTD · ABN 55 606 664 546. All rights reserved. Provided
> for the use of PWE Studio subscribing studios and their staff. It may be
> printed and shared inside your studio; it may not be republished, resold, or
> used to operate a competing service without written permission.

**Hiding the link is obscurity**, which reserves nothing — the first customer
who forwards the URL ends that — and costs three things worth more:

* Support can deep-link `/manual/#money` to someone who is not signed in,
  which is most people asking a question.
* It qualifies a prospect. Refund gating and minors' consent are among the
  strongest reasons to buy, and a prospect who reads them first is better
  informed.
* It answers the search rather than leaving it to a forum.

Set at `--f-sm`, not `--f-xs` — a licence nobody can read is not one anyone
agreed to. Delivery is a **step in `Onboarding_Checklist.md` Phase 2**: send
the link with the owner's credentials, deep-linked to the sections matching
their roles. Recorded there as a courtesy and an onboarding step, explicitly
**not** an access control, so nobody describes it to a customer as one.

## Print footer, not a watermark

Same reasoning applied to paper. A full-page watermark sits on top of the body
text and the screenshots — on a document whose design brief was measured
contrast and whose screenshots exist to be studied — costs toner on a page
meant for a front desk, and on a public document a confidentiality mark would
be a false claim. The running footer names version, print date and current
URL, which is what a copy found in a drawer two years from now actually needs.
A watermark remains right for a DRAFT or customer-specific copy; neither
exists yet.

520 tests pass. Still not deployed.

---

# PWE Studio — the English CMS, the roster panel, and a print footer (2026-08-03)

## The English CMS was 66 strings short

`backend/scripts/audit_cms_translation.py` is new and is the point of this
round. Untranslated UI has shipped from here four times and the mechanism is
always the same: **nothing fails.** A missing entry renders the source
Chinese, the page works, the tests pass, and only a reader who does not read
Chinese finds out. The manual's screenshot run is what finally surfaced it —
capturing every screen in English put the gaps on one contact sheet.

So the contact sheet is a command. It signs in, walks every tab, and reports
every Chinese text node **and attribute** still showing in English mode.

```text
before   66 distinct strings
after     0   (3 intentional: 中, 中文, "Language / 语言")
```

Most of them were **`aria-label`s and placeholders** — `全局搜索 ⌘K`,
`搜索学员姓名...`, `选择 <student name>` — which never appear in a screenshot
and are exactly what a screen-reader user hears. Fixed with ~45 dictionary
entries plus 9 pattern rules (`^选择\s+(.+)$` → `Select $1` covers every
student card with one rule, and keeps working for names nobody has entered
yet). Exits non-zero when anything is found, so it can gate a release.

The number-adjacent fragments I had documented as unfixable are fixed:
Chinese and English both put the measure word after the count, so
`6/10 人 · 60 分钟` → `6/10 students · 60 min` is a straight substitution. The
earlier note was too cautious.

## The roster panel never lined up

`items-end` on the two-column grid. The columns end at different heights — the
left trails a helper line, the right a 44px checkbox — so bottom-alignment
pushed the right column's label and its controls a row higher than the left's.
`items-start` puts both labels on one baseline and both control rows on
another; the unequal tails hang below, which is what they should do. The left
column's controls also lacked the `min-h-[50px]` the right column had.

Measured after: labels both at y=414, control rows both at y=434.

## Printing: a running footer, not a watermark

Discussed rather than assumed. A full-page watermark sits on top of the body
text and the screenshots — on a document whose whole design brief was measured
contrast, and whose screenshots exist to be looked at closely. It also costs
toner on a page meant to be printed for a front desk, and on a **public**
document a confidentiality mark would be a false claim.

What the worry actually is — a printout being read two years later — is
answered by a running footer: version, print date, and where the current one
lives, repeated on every page via a fixed element with `@page` reserving the
band. The date is stamped by the print button, because CSS cannot produce one
and page-load would go stale on a tab left open overnight.

**A watermark is still the right tool for a DRAFT or customer-specific copy.**
Not built, because this document is neither.

## Also

* Two bugs in my own additions, both caught by the tests I had written: the
  footer nested a `<span>` inside a `data-lang` `<span>`, which is the one
  rule the language filter needs; and the print handler used an undeclared
  `root`, which would have thrown on the first click.
* All 22 screenshots re-captured against the fixed CMS.
* Production has **no manual yet** — `/manual/` and `/zh/manual/` are 404
  there. The broken images seen earlier were a server that predated the
  `/assets/<dir>/<file>` route fix; nginx has no `/assets` block, so the
  subdirectory reaches Flask in production too.

519 tests pass. Not deployed.

---

# PWE Studio — user manual phase C: screenshots, and two bugs they exposed (2026-08-03)

22 images (11 screens × 2 languages), 0.94 MB, wired into `/manual/` with
callouts. **Every screen is captured twice** — a Chinese screenshot in the
English manual reads as a different install, not a different language.

## The shot list runs

`backend/scripts/capture_manual_shots.py` + `docs/design/manual_shots.md`.
Chrome's `--screenshot` flag cannot carry a session and half these screens are
behind a login, so the script signs in over HTTP, hands the cookie to a
headless Chrome over the DevTools Protocol, clicks the tab **by its visible
label**, and captures. A renamed tab therefore fails the capture loudly rather
than photographing the wrong screen. The ~60 lines of WebSocket framing are
there because CDP is JSON-over-WS and this repository has no WS dependency.

Source is `lets-paint-showcase`, whose records are synthetic by construction.
No screenshot can contain a real student. Credentials are read from the 0600
file `reset_professional_demo.py` writes — never an argument, never printed.

## Two bugs the run exposed

**1 · The English CMS is incomplete.** Capturing every screen in English put
the gaps on a contact sheet: **22 Chinese strings on the roster alone**. The
self-contained ones are now in `cms-i18n.js` (+30 entries: `网站与品牌`,
`固定课表 ICS`, weekday abbreviations, the empty-roster hint, `已签`/`未签`,
the stats hints…). **Known gap, not fixed:** number-adjacent fragments — `人`,
`次`, `笔`, `条`, `分钟` — which React splits into their own text nodes.
Translating those in isolation would reorder the phrase rather than translate
it; the dictionary needs pattern support first.

**2 · `/assets/<path>` flattened every path to a basename**, so
`/assets/manual/03-roster.en.webp` 404'd — and the symptom was a blank column,
not a broken route. Fixed with an allowlist of subdirectory names
(`ASSET_SUBDIRECTORIES = {'manual'}`) rather than a traversal check: `..` is
not the only way out of a directory, and a fixed set of names cannot be talked
into anything. The leaf is still reduced to a basename.

Two smaller ones: the roster shot would have been an **empty state** because
today has no class (`class_schedules.weekday` is 1 = Monday, Python's is 0 —
off by one, and it still produced a plausible screenshot); and
`reset_professional_demo.py` had **v8.1.0 typed into its credentials header**,
now read from VERSION.

## What is asserted

`test_manual.py` grew to 24 cases: every referenced image exists, every screen
has both languages, alt text is present (word count for English, character
count for Chinese — ten Chinese characters carry what four English words do),
explicit dimensions and lazy loading, the set stays under 3 MB with **no
unreferenced images shipping publicly** (v8.2.18's 9.2 MB of orphaned demo art
was in the sibling directory), every captured shot appears in the spec, the
callouts are DOM text rather than pixels, and the assets route serves
`manual/` and refuses everything else.

## Left for the reader to judge

* Screenshots are one theme in light mode; the manual says so at the top —
  "the colours will not match, the positions will".
* Phone captures are constrained to 400px. Stretching a 390px screen to the
  article width would show text at twice the size it is on the device.
* Not deployed. 518 tests pass.

---

# PWE Studio — user manual, phases A and B done; screenshots next (2026-08-03)

Medium decided and recorded in `docs/design/User_Manual_Plan_2026-08-03.md`:
**one HTML document, an `@media print` stylesheet for the PDF.** Not two
artefacts. A PDF is a second copy of facts that move every release, and this
project has been bitten by that pattern three times already.

## A — `docs/guides/` refreshed to v8.2.20, and now tested

1,327 lines of accurate, backend-aligned content sitting on a **v8.1.0
baseline through nine releases**. Every claim was re-checked against code.

Wrong and now fixed:

* Super Admin guide said the audit log had **no search or pagination** —
  v8.2.11 added both.
* It said a plan **could not be created from the console** because the code
  field was disabled — v8.2.20 made it editable.
* It documented a **Commercial Attention** card that v8.2.11 deleted.
* The permission matrix had **no `courses:write` row at all**, and stated the
  front desk's portfolio boundary as "no write" when the backend gives it
  **no read either** — that decides what a receptionist sees of a child's photos.
* The Owner guide described the theme preview as nine flat swatches; v8.2.7–9
  split it into six theme colours and three status colours solved per theme,
  which is the whole change.

Added: 30 audit action types with readable summaries, the 30-megapixel image
ceiling (and that uploads worked at all only from v8.2.6), archive/delete
becoming usable in v8.2.10, retention windows, and plans no longer publishing
themselves.

**`backend/tests/test_user_guides.py` is the point.** These drifted because
nothing checked them — no page 500s, no test goes red, and the reader cannot
tell. It parses the permission matrix out of `README.md` and compares it with
`ROLE_PERMISSIONS` row by row, checks every counted claim against its source
(audit actions, status colours, theme list, pixel ceiling, retention windows,
CMS tabs), and asserts the three superseded claims cannot come back.

## B — the manual shell, readable now, screenshots pending

`manual.html` + `/assets/manual.css` + `/assets/manual.js`, served at
**`/manual/` (en) and `/zh/manual/` (zh)** through the same `apply_language`
the home page uses. Twelve sections ordered by a studio's week rather than by
the menu, each as *what to do → screenshot → what people get wrong*.

* **Screenshot slots are in place** with captions and `.ui-shot` framing;
  the images themselves are phase C. Callout numbers will be **DOM text, not
  pixels** — so they translate, get read out, and follow the theme.
* **`manual.css` restates no family hex.** It reads `--pwe-family-*` from
  `ui-tokens.css`. This is the fourth page to carry the palette and the
  previous three drifted onto a retired one by each holding a copy.
* **φ where it works**: `--measure: 61.8ch` for the reading column, Fibonacci
  vertical rhythm, φ^(k/2) type. The contents sidebar is sized by its content
  — 38.2% would be a 440px navigation column, which is φ as decoration.
* **Print is the PDF**: contents and search removed, `@page` margins, sections
  break to a fresh page, link targets printed after the text, and `[hidden]`
  forced visible so a filtered screen cannot print a manual with sections
  missing. The print button clears the filter first.
* **Section 09 stops at "what the platform can and cannot do"** — no console
  instructions. Asserted: the manual contains no `/platform-admin`.

Measured: no contrast pair below 4.5:1 in either theme, no horizontal overflow
at 390px, contents collapse and every bar control is 44×44 (it was 41×43 —
fixed), wide tables scroll inside their own box.

## C — next: screenshots

Capture against the local instance and the `lets-paint-showcase` tenant (its
data is synthetic by design, which is why it exists). Write
`docs/design/manual_shots.md` first — path, role, viewport and required page
state per shot — so the set can be retaken on a later release instead of
re-derived. Budget ~30 images, 2–3.5 MB, all lazy-loaded; state in the manual
that a studio on another theme sees different colours in the same places.

Not deployed. 510 tests pass.

---

# PWE Studio v8.2.20 — the home page rebuilt, split by language, priced from the database (deployed 2026-08-03)

## Shipped and live

**1. The page.** `product-home.html` rebuilt on the Paradise design language:
Family Navy end to end, Family Amber as the single accent, φ^(k/2) type,
Fibonacci spacing, 61.8/38.2 splits, 17px root. Seven sections in the order the
owner chose — hero · pain · surfaces · templates · trust · pricing · launch ·
contact. The copy names the operator's day (三个月的群记录, 晚上核 Excel,
抽屉里的收据) instead of describing the software; the English is written to
carry that voice, not translated word for word.

**2. Light and dark, from the system.** Authored dark, re-skinned onto Warm
Paper under `prefers-color-scheme: light`. Both themes are the *same rules*
driven by five surface tokens plus `--accent`, so the layout cannot fork.
Measured, both themes, every text role: worst case 4.52:1 (the light-mode
eyebrow at 13.4px), nothing below AA. The brand mark switches with the theme
via `<picture>` — `pwe-mark-dark.svg` on navy, per Brand_Identity §7.

**3. One language per URL.** `/` is English, `/zh/` is Chinese, `/zh` 301s to
`/zh/`. Reciprocal `hreflang` (en-AU · zh-Hans · x-default) identical on both,
paired canonicals, `Content-Language`, one `<h1>` and one `<title>` each.

  Both languages are still authored in **one file** — the translations cannot
  drift apart — and `services/public_site.filter_language` removes the other
  one server-side. It is an `HTMLParser`, not a regex: start tags are re-emitted
  from `get_starttag_text()`, so a document with nothing to strip comes out
  byte for byte identical, which is asserted. The `data-lang` marker is stripped
  from surviving tags too. **The one rule the markup must keep:** a `data-lang`
  element may not contain another element of the same tag name, because skipping
  counts that tag. A test walks the real page and enforces it.

**4. Pricing is rendered from the plan table**, server-side — cards *and* the
JSON-LD `AggregateOffer`, from the same rows `/v1/public/plans` returns. Not a
client fetch: structured data and prices belong in the HTML, and there is no
empty state without JavaScript. A database outage costs the pricing grid only;
the section falls back to a contact line and the rest of the page is static.
A test asserts **no plan limit or price appears literally in the page** — that
is the property that makes the earlier drift impossible, stated as a check.

## What the rebuild found — a plan row was automatically an offer

Rendering the page against the local database put **`Isolation No Portfolio`,
A$1, on the public pricing grid** beside the real three, and moved the
"Recommended" badge onto Starter — because the badge was inferred from the
median price and a fourth row shifted the median. Production happened to be
clean; nothing was keeping it that way, and `/v1/public/plans` had been serving
the unfiltered table since v8.2.19.

Migration `0023_public_plan_publication.sql`:

* `is_public boolean NOT NULL DEFAULT false` — **false on purpose**. A plan
  created tomorrow is invisible until somebody decides to sell it. Publishing
  is now the deliberate act; the old behaviour was the accident. Backfilled
  true for `starter`/`studio`/`growth` — written as an explicit list, because
  the reason this migration exists is that "what exists" and "what is sold"
  had already diverged.
* `is_recommended` + a unique partial index, so at most one plan wears the
  badge. Setting it in the console clears the others (a radio, not a
  constraint violation the UI never mentioned).
* Console: a **Public** column in the plans table and two checkboxes in the
  add/edit dialog, with the Chinese strings added to `admin-i18n.js`.

## Deployed and verified

`PWE-StudioSaaS-aws-8.2.20-26f609fa9e33`, 2026-08-03. Logical dump taken first
(`studiosaas_studiosaas_20260803T020035Z.dump`). Deep health passed from the
instance and from the public edge; the deploy pruned the v8.2.17 release
directory, the v8.2.19 bundle and the v8.2.17 image behind itself. Disk 16.2%,
47.8 GB free.

**Migration 0023 applied itself.** `deploy/aws/entrypoint.sh` runs
`run_migrations.py` on every container start, before the app serves — checked
in the script rather than assumed, because without it the pricing section
would have 500'd on `is_public`.

Measured live, both languages:

```text
                    /                          /zh/
<html lang>         en                         zh-Hans
Content-Language    en                         zh-Hans
<title>             Studio Management Soft…    工作室管理系统 · 报名、排课…
canonical           https://pwestudio.online/  https://pwestudio.online/zh/
hreflang            en-AU · zh-Hans · x-default (identical on both)
<h1>                1                          1
data-lang left      none                       none
plans               49 / 99 / 199, badge on Studio (both)
JSON-LD offers      AggregateOffer AUD 49–199, offerCount 3 (both)
bytes               44,520                     40,070
```

`/zh` 301s to `/zh/`. `/v1/public/plans`, `/platform-admin`,
`/customer-resources/FAQ.html` and `/lets-paint-showcase` all still 200.

The only CJK remaining on the English page is `中文` (the switch link, carrying
`lang="zh-Hans"`) and `天域文创出品` in the producer credit — the studio's
Chinese name is part of the signature, not translatable copy (Brand_Identity
§10).

**Still to do by hand: submit both URLs to Search Console.** `/zh/` is a new
address with no history, and the hreflang pair only helps once both are known.

`zh` and `en` are now reserved tenant slugs.

## Still open

1. **The Paradise page's plan limits are still wrong at source** (1500 / 100 GB
   against a database that caps at 1000 / 50 GB). `02 WEBSITE/src/build.py`,
   then `python3 build.py --sub`. Not reachable from this repo. Now that
   `/v1/public/plans` is public and filtered, that page could read it instead
   of restating it.
2. **`customer-resources/*.html` still toggle language in the DOM** and read
   `pwe-public-language` from localStorage. The home page sets that key from
   its URL so the footer links stay in the reader's language, but those five
   pages have not been split. They have no SEO ambition; splitting them is the
   consistent finish, not an urgent one.
3. **No web font.** Latin headings fall back to Georgia rather than Playfair
   Display. Deliberate — the front door should not make a render-blocking
   third-party request — but self-hosting Playfair is the upgrade if the
   Latin display type matters more than the ~100 KB.
4. **The 6-step operating flow was dropped** (咨询→跟进→排课→签到→作品→洞察).
   It restated the surface cards as verbs and the reference page is tight for
   exactly that reason. Say so if it should come back.

---

# PWE Studio v8.2.19 — pricing endpoint and credit shipped; page port ready to execute (2026-08-02)

## Shipped

* **`/v1/public/plans`** — no auth, public fields only, `Cache-Control: 300`.
  Live and returning the three real plans. The query names its columns and
  omits `features`: that column carries entitlement flags edited from the
  platform console by someone thinking about billing, not about a public page.
* **Producer credit is a link.** `A Paradise Production · 天域文创出品` →
  `/paradise-production/`, and `Brand_Identity.md §10` changed with it.
  **Tenant footers deliberately unchanged**: `Powered by Paradise Production`
  is white-label attribution on somebody else's site, often in English, and the
  line a commercial agreement may remove — 出品 would overclaim there, and an
  outbound link on a customer's page is not ours to add.

## The plan numbers disagree, and the database wins

Confirmed by the owner: the database is authoritative.

```text
                 database (authoritative)        paradise page (wrong)
starter          100 students /  1 user /  2 GB  100 / 2 /   5 GB
studio           500 students /  5 users / 10 GB 500 / 8 /  30 GB
growth          1000 students / 20 users / 50 GB 1500 / 20 / 100 GB
```

Prices agree (A$49 / 99 / 199) and the Setup fee A$299–999 matches. Only the
limits drifted — which is exactly the failure a hardcoded marketing page
produces, and exactly what the new endpoint prevents on our side. **The
Paradise page needs its limits corrected at source** (`02 WEBSITE/src/build.py`
in the PARADISE PRODUCTION folder, then `python3 build.py --sub`).

## Copy to port — the owner's preferred version, verbatim

Source: `https://paradise-production.pages.dev/pwe-studio`. Pricing excluded
(that comes from the endpoint now). Seven sections:

```text
HERO      把时间还给创作
          官网获客 · 在线报名 · 课时账本 · 品牌门面 —— 琐事交给系统，你回到教室与作品。
          创意工作室的一体化操作系统，面向美术 / 音乐 / 舞蹈工作室与培训机构。

PAIN      你的才华，不该耗在台账和聊天记录里
          开工作室是因为热爱创作与教学。没有人是为了对账、催费、翻聊天记录才创业的。
          · 被打断的排练 —— 「还剩几节课？」一句询问，要翻三个月的群记录才答得上。
          · 深夜的对账表 —— 白天上课，晚上核 Excel，吃掉的是备课和新作品的时间。
          · 经不起丢的纸条 —— 收据在抽屉、承诺在口头，家长的信任不该系在一张纸上。
          · 看不见的作品墙 —— 作品攒了一屋子，线上无处可看，新学员只能靠转介绍。

SURFACES  台前是你的品牌，幕后是一个系统
          · 门户 Portal / 快速报名 Register / 运营 CMS / 品牌工作台
          + 另有平台侧 Super Admin……平台方不接触学员敏感数据，进店必须走留痕的支持模式。

TRUST     钱和信任，写进系统，不写在人情里
          · 账本不可篡改 · 权限写死在后端 · 未成年人隐私

PRICING   透明定价，随工作室一起成长      ← data from /v1/public/plans

ONBOARD   从签约到开幕，只需四步
          1 品牌配置 · 2 数据导入 · 3 团队培训 · 4 正式上线
          四步全部包含在一次性 Setup 服务费内。机构不需要懂技术。

CTA       管理退到幕后，作品站上台前。
          预约一次 30 分钟演示：用你工作室的名字、作品和课程，现场生成一个可预览的门户。
```

**Why this copy is better than what the home page has now**, in one line: it
names the operator's day (三个月的群记录、晚上核 Excel、抽屉里的收据) instead of
describing the software's features. The current page opens with "Put
administration behind the scenes" — a claim; this one opens with a grievance
the reader already has.

## What is left, in order

1. **Port the copy and the dark/amber/φ design into `product-home.html`**, with
   the pricing section reading `/v1/public/plans`.
2. **`/` + `/en/` split with hreflang.** Do it after 1, so the split happens
   once on the final markup. Today one URL serves both languages with no
   hreflang and a self-referential canonical — 69 `data-lang="zh"` nodes and a
   duplicated `<h1>` in the English DOM.
3. **Correct the Paradise page's plan limits** at source; the page is generated
   from `02 WEBSITE/src/build.py`, not editable from this repo.

Both projects already share the token system — `--navy #0E1729`,
`--amber #F5B335`, `--amber-d #A16207` (light-surface safe) — so this is
applying an identity both sides already own, not inventing one.

---

# PWE Studio — marketing page work, scoped not started (2026-08-02)

v8.2.18 shipped the operational items (disk headroom in deep health, build
context tightened). The page work below is **measured and planned, not begun**.

## The two pages, measured

```text
                    /  (product-home.html)        /paradise-production/pwe-studio
language            <html lang="en"> AND 69       <html lang="zh">, monolingual
                    data-lang="zh" nodes
<h1>                rendered twice, once per      once
                    language, in one DOM
hreflang            none                          /en/ sibling
structured data     none                          JSON-LD SoftwareApplication
                                                  + AggregateOffer
pricing data        hardcoded $99 in the HTML     hardcoded A$49/99/199
lives in            this repo                     /var/www/paradise-production,
                                                  nginx static, generated elsewhere
```

The SEO problem is real and measurable: one URL serves both languages with no
hreflang and a self-referential canonical, so each language dilutes the other.

## Three facts that block a naive implementation

1. **`/v1/plans` is auth-gated** (`@permission_required("plans:read")`, returns
   401 publicly). "Pricing from the database" needs a *new public* endpoint
   exposing only public fields — code, name, price, the three limits — and not
   the entitlements JSON that plan rows also carry.
2. **The Paradise site is not in this repo.** It is static files under
   `/var/www/paradise-production` served by an nginx `^~` block, generated for
   the Cloudflare Pages convention. Its plan numbers cannot be corrected from
   here; its source lives somewhere else.
3. **A `/` + `/en/` split changes URLs.** It needs routes, paired canonical and
   hreflang, and the language toggle stops being a DOM switch and becomes
   navigation — which also removes the duplicate-DOM weight from every page
   load.

## Proposed sequence — three releases, smallest risk first

* **A — public plans endpoint, pricing reads it.** No visual change. Makes the
  home page and any future page agree with the database instead of with a
  hardcoded number that has already drifted once.
* **B — port the Paradise design language.** Deep navy sections, amber accent
  and spark motif, the recommended pill, φ spacing, and the JSON-LD the
  Paradise page carries and the home page does not. This is the large one and
  it is a design review, not a mechanical port.
* **C — `/` + `/en/` with hreflang.** The SEO fix. Best done after B so the
  split happens once, on the final markup.

## Open questions

* The canonical producer credit is `Powered by Paradise Production · 天域文创`
  (Brand_Identity.md §10). The proposed link text
  `A PARADISE PRODUCTION · 天域文创出品` is different wording — link the
  existing line, or change the brand spec?
* Where does the Paradise site's source live? Its plan numbers need correcting
  and this repo cannot reach them.

---

# PWE Studio v8.2.17 — the deploy cleans up after itself (2026-08-02)

## Result

```text
                      before          after
disk                  9.4 GB          8.3 GB      of 58 GB
docker images         21 / 1.91 GB    6 / 994 MB
release directories   18 / 340 MB     3 / 57 MB
uploaded bundles      23 / 295 MB     1 / 14 MB
build cache           1.67 GB         1.49 GB     converging on a 1 GiB cap
/opt/pwestudio        1.47 GB         952 MB
```

`prune-artifacts` runs automatically at the end of every successful deploy, so
this stays true without anyone remembering.

## Why there were 19 image tags with 2 in use

This is the tail of an earlier fix, and worth understanding before changing it.

`docker-compose.yml` tags the image `studiosaas:${STUDIOSAAS_VERSION}`. Nothing
used to update that variable, so **every release overwrote the same tag**:
deploying 8.1.0 produced an image labelled `studiosaas:8.0.1` running an app
that reported 8.1.0. `docker images` lied to whoever was diagnosing an incident,
and the tag was useless as a rollback point.

The fix pinned the version per release — correct, and it turned one
overwritten tag into one new tag per deploy with nothing ever removing them.
**Retention is the half that was missing, not the tagging.** Keeping 3 gives an
instant `compose up` fallback without a rebuild; the automated rollback path
does not need them at all, because it re-points `current` and runs
`compose up --build` from the release directory.

## Why the build cache was 1.7 GB, and why `prune -a` is the wrong tool

`docker builder du --verbose` on the largest entry:

```text
Description:  mount / from exec /bin/sh -c pip install -r deploy/aws/requirements.lock
Size:         96.05MB
Usage count:  23
Last used:    7 minutes ago
```

That entry is why a deploy takes a minute instead of five, and `builder prune
-a` deletes it. It would also slow the rollback path, which rebuilds.

The rest is per-build layers: the Dockerfile does `COPY deploy/aws/requirements.lock`
→ `RUN pip install` → `COPY . .`, so the pip layer is stable and everything
after `COPY . .` is rebuilt on every deploy — about 30 MB a build, retained
forever.

**An age filter was tried first and reclaimed 0 B.** `until=336h` finds nothing
on an instance whose entire history is four days old. Cache pressure here is a
function of deploy count, not of time. The cap is a size with least-recently-
used eviction, which keeps the hot pip layer and drops the stale per-build
layers; the first run evicted 303 MB, all of it last accessed 2–3 days ago.

The flag was renamed between engine versions — `--keep-storage` on Docker ≤ 28,
`--max-used-space` on 29+, and this host runs 29.6.2. The script probes rather
than pins, because pinning the wrong one prunes nothing while printing what
looks like success.

## Two small bugs the first live run exposed

* `*.tar.gz` left every `.sha256` sibling behind. The match now covers both and
  is scoped to `PWE-Studio*`, so a portable snapshot or a one-off export parked
  in `incoming/` is never touched.
* A stray `hello-world:latest` image is still on the host from some early
  smoke test. Harmless (25 kB) and deliberately not auto-removed — the prune
  only ever touches `studiosaas:*` tags.

## Ordering that matters

`prune-artifacts` runs **only after the new release reports healthy**, so it can
never race the rollback branch for the directory that branch needs. And the
current release is protected **by name, not by position**: it is usually the
newest, but a rollback makes it older than the release it replaced, and a
`ls -1t | tail` rule would then delete the running release.

## Knobs

```text
PWESTUDIO_KEEP_RELEASES          3            current + rollback target + spare
PWESTUDIO_KEEP_IMAGES            3
PWESTUDIO_BUILD_CACHE_MAX_BYTES  1073741824   1 GiB
```

## Future work, in the order it will matter

1. **Nothing watches disk.** Every retention rule now exists, but if one breaks
   the first symptom is a full volume. A `df` threshold in the deep-health
   payload, or a cron that alerts past 80%, is the cheap next step.
2. **Backups are on the same disk as the data.** `backups/` is 881 MB of the
   8.3 GB used, and an instance loss takes both. README_AWS.md §9.2 already
   recommends S3 or EBS snapshots; neither is set up.
3. **The build could be smaller.** `COPY . .` copies the whole tree including
   `docs/`, `customer-resources/` and tests. A tighter `.dockerignore` would cut
   both image size and the per-build cache layer.
4. **`hello-world` and the 8.0.1 checksum stray** suggest the instance has never
   had a from-scratch inventory. Worth one pass now that retention exists.

---

# PWE Studio v8.2.14 — orphan accounts disabled; server storage audited (2026-08-02)

## Orphan accounts

Six accounts had no membership at all — leftovers from `isolation-alpha`,
`isolation-beta` and `lets-play-game`. They could authenticate and reach
nothing. All six are now `status='disabled'`, which is reversible; the rows are
still there.

```text
active   11  every one with a real role
disabled  6  frontdesk@isolation-alpha.test  owner.alpha@studiosaas.local
             owner.beta@studiosaas.local     owner@lets-play-game.test
             teacher@isolation-alpha.test    tenant-admin.alpha@studiosaas.local
```

**A bug shipped and fixed in the same session.** `--disable-orphans` ran inside
`rotate()` and then fell through into the rotation, so asking for the tidy-up
would have silently changed every password in the database. Disabling orphans
is maintenance; rotating is incident response. `--skip-rotation` separates them,
and the production run used it.

## Server storage — measured, nothing cleaned yet

```text
disk                     9.4G used of 58G (17%)
memory                   1.9G total, 668M used, 1.2G available
containers               app 57 MB, db 45 MB — 3% each, idle CPU

reclaimable                                          size
  docker build cache     57 entries, 0 active        1.67 GB
  docker images          17 of 19 studiosaas tags    1.05 GB
  shared/incoming        23 release tarballs         295 MB
  releases/              18 unpacked dirs            283 MB (keeping 3)
  /var/cache/apt                                     110 MB
                                                     ------
                                                     ~3.4 GB

not reclaimable
  backups/volumes        39 tarballs, 7-day window   831 MB
  backups/postgres       14 dumps, 30-day window     5.9 MB
  docker volumes         live data                    95 MB
```

## The structural finding: the deploy path has no retention for its own output

`deploy` calls `ctl backup` first, so backups are covered — but everything the
deploy itself produces accumulates forever. Per release:

```text
shared/incoming/<bundle>.tar.gz     14 MB   never deleted
releases/<name>/                    19 MB   never deleted
studiosaas:<version> image          ~50 MB unique, never pruned
build cache                         grows,  never pruned
```

That is ~33 MB of permanently retained cruft per deploy before images, and
today alone had 13 deploys. It is the same class of gap as the postgres dumps
in v8.2.12: retention exists for the thing labelled "backup" and for nothing
else. The fix belongs in `pwestudio_remote.sh deploy` / `lightsail_ctl.sh`,
keeping the current release plus two for rollback and pruning the rest.

---

# PWE Studio v8.2.13 — release evidence, a second platform admin, and a retracted finding (2026-08-02)

## A correction first: the "16 exposed accounts" finding was wrong

The previous handoff carried a SECURITY section claiming 16 production accounts
still accepted the seed password `admin123456`, including the only platform
super-admin. **That was a bug in the checking script, not a finding.** It has
been removed from this document and from memory.

```python
# studiosaas.auth.verify_password returns a TUPLE:
def verify_password(password, expected_hash) -> tuple[bool, bool]:   # (ok, needs_upgrade)

if verify_password(seed, row["password_hash"]):   # (False, False) is TRUTHY
```

Every account matched because every non-empty tuple is truthy. Re-run with
`verify_password(...)[0]`:

```text
seed admin123456 : 0 of 16
no match         : 16 of 16
```

Nothing was rotated — the bulk credential change was blocked by a permission
prompt before it ran — so no damage was done. The lesson is the ordinary one:
a security claim that says *everything* is affected is far more likely to be a
bug in the check than a real finding, and should be re-derived a second way
before it is written down. The user disputing it ("I log in with that password
every day") was the signal that found it.

## Actual account state on production

```text
admin@studiosaas.local        System Administrator   super_admin @ PLATFORM
lee.liu.melbourne@gmail.com   Lee Liu                super_admin @ PLATFORM   (new)
dance@dancedance.com                                 owner       @ dance-dance
mengqi.wu9364@gmail.com                              owner       @ ruby-s-studio
owner@dance-dance.test                               owner       @ dance-dance
owner@lets-paint-studio.test                         owner       @ lets-paint-studio
owner@lets-play-piano.test                           owner       @ lets-play-piano
owner.showcase@pwe-studio.invalid                    owner       @ lets-paint-showcase
manager.showcase@pwe-studio.invalid                  manager     @ lets-paint-showcase
frontdesk.showcase@pwe-studio.invalid                front_desk  @ lets-paint-showcase
teacher.showcase@pwe-studio.invalid                  teacher     @ lets-paint-showcase
frontdesk@isolation-alpha.test                       (no membership)
teacher@isolation-alpha.test                         (no membership)
tenant-admin.alpha@studiosaas.local                  (no membership)
owner.alpha@studiosaas.local                         (no membership)
owner.beta@studiosaas.local                          (no membership)
owner@lets-play-game.test                            (no membership)
```

All hashes are pbkdf2. The six membership-less rows are leftovers from deleted
tenants — they can authenticate but reach nothing. Disabling them is a
tidiness item, not an exposure: `rotate_pilot_credentials.py --disable-orphans`.

## The one real credential defect found

`rotate_pilot_credentials.py` selected `role IN ('super_admin', 'owner',
'staff')`. The role vocabulary in production is **super_admin / owner / manager
/ front_desk / teacher** — there is no `staff` role at all. A rotation run
against this database would have silently skipped every manager, front-desk and
teacher login and reported success. Now selects every active membership
whatever the role, and gained `--exclude`, `--disable-orphans` and `--dry-run`.

## isolation-alpha permanently deleted

Archived first, then deleted with the `DELETE isolation-alpha` confirmation
phrase. The archive survives the delete by design, and now carries the final
snapshot too:

```text
/app/backend/archives/tenants/isolation-alpha-20260802-082317
  db/                       31 JSON snapshots
  final-delete-snapshot/    31 JSON snapshots
  media/
```

Its four users are now membership-less rows in the list above.

## Release evidence no longer goes stale by design

The page sat at v8.1.0 while production ran v8.2.11, and the cause was the
filename. `Release_Notes_v8.1.0.html` carried the version, so keeping it current
meant renaming a file, editing an allowlist, a link, a CSS comment and three
tests — every release. The step that gets skipped is the one nothing checks.

* The file is now `Release_Notes.html`. No version in the URL, nothing to rename.
* Every versioned name ever published still 301s to it.
* Content extended with a "Since v8.1.0" section covering v8.2.3 → v8.2.13 in
  customer-readable terms.
* `test_release_notes_track_the_shipped_version` asserts the page mentions
  whatever `VERSION` says, so the next release cannot quietly leave it behind.

## Second platform super-admin

`lee.liu.melbourne@gmail.com`, platform-level `super_admin` (tenant_id IS NULL,
so it covers tenants created later). Generated password, never printed, at
`/data/credentials/platform-admins.txt` (0600) on the `studiosaas-data` volume:

```bash
ssh pwestudio "cd /opt/pwestudio/current && docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml --profile local-db exec -T app cat /data/credentials/platform-admins.txt"
```

`seed_super_admin.py` gained `--random-password`, which generates the value,
suppresses printing and writes it to the 0600 file — because passing a secret
through `STUDIOSAAS_ADMIN_PASSWORD` puts it in the process list on a shared
host. To set a password of your own choosing instead:

```bash
ssh pwestudio
cd /opt/pwestudio/current
read -rs -p 'new password: ' PW && export STUDIOSAAS_ADMIN_PASSWORD="$PW"
docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env \
  -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml \
  --profile local-db exec -T -e STUDIOSAAS_ADMIN_PASSWORD app \
  python backend/scripts/seed_super_admin.py --email <address> \
  --reset-password --no-print-password
unset STUDIOSAAS_ADMIN_PASSWORD
```

`read -rs` keeps it off the terminal and out of shell history.

---

# PWE Studio v8.2.12 — retention for everything that only grew (2026-08-02)

**Shipped.** Audited every store on the box that accumulates. Four had no
ceiling; the notable part is that the retention *policy* already existed and had
simply never been connected to anything.

## What was measured

```text
store                          cap                    state
docker app container log       10 MB x 5              capped
docker db container log        none                   UNCAPPED  -> fixed
volume tarballs                find -mtime +7         capped (743 MB on disk)
postgres dumps                 none                   UNCAPPED  -> fixed (30d)
audit_logs                     script exists, 730d    NEVER SCHEDULED -> fixed
public_analytics_events        script exists, 365d    NEVER SCHEDULED -> fixed
notification_logs              none                   not in the script -> added
student_access_sessions        none                   not in the script -> added
student_access_attempts        none                   not in the script -> added
/var/log/pwestudio-*.log       no logrotate entry     -> documented
```

`audit_logs` is already the **largest table in the database** — 4,413 rows in
31 days (~142/day, 1.3 MB of a 13 MB database) across six pre-launch tenants,
and the rate scales with tenant count.

## The interesting failure: a policy nobody called

`prune_event_tables.py` shipped with the retention window in its docstring and
the instruction "Schedule monthly", and was then never scheduled. The only cron
entry on the instance is the backup. Two years of default retention means
nothing would have gone wrong for two years, by which point nobody would
remember to look.

It is now a first-class command so a schedule has something stable to call:

```bash
bash deploy/aws/lightsail_ctl.sh prune --dry-run   # on the box
bash deploy/aws/pwestudio_remote.sh prune          # from a laptop
```

That indirection is not decoration — README_AWS.md §9 already records that a
cron line pointing straight at a path inside the image is exactly how the daily
backup silently failed for weeks (`scripts/` vs `backend/scripts/`).

## Three tables added to the policy

The original pass covered the two that grow with *operator* actions and missed
the three that grow with *traffic*: a row per message sent, a row per student
login, a row per rate-limit window.

```text
notification_logs         created_at        365 days
student_access_sessions   expires_at         30 days   (dead once expired)
student_access_attempts   updated_at         30 days   (lockout long past)
```

**`student_publication_consent_events` is deliberately excluded and must stay
that way.** It is legal proof of consent, and a tenant archive snapshot is the
only other copy.

Verified against the local database with a one-day window, which is the only
way to prove the column names resolve — every table returned rows
(6096/44/6/3/0). Production dry run: 0 rows to delete, as expected for a
one-month-old database.

## Installed on the instance

Both files are in place; the code change alone would have changed nothing.

```text
/etc/cron.d/pwestudio-prune      15 4 1 * *  (after the 03:15 backup, so a dump exists first)
/etc/logrotate.d/pwestudio       monthly, rotate 6, compress
```

`logrotate -d` validates the config; `cron.d` now holds `pwestudio-backup` and
`pwestudio-prune`. A backup run after the change completed clean with the new
dump-retention step, and both containers report `max-size 10m / max-file 5`.

## isolation-alpha archived

A local isolation-test tenant seeded into **production** on 2026-07-29 —
`settings.test_fixture = true`, four users on `@isolation-alpha.test` and
`@studiosaas.local`, all data synthetic. Archived, not permanently deleted:
archiving is reversible (`/v1/admin/tenants/<id>/restore`) and writes the
snapshot, while permanent delete is irreversible and the product asks for a
typed `DELETE isolation-alpha` for that reason. Finish it in the console when
you want the records gone.

```text
/app/backend/archives/tenants/isolation-alpha-20260802-082317
  db/    31 JSON snapshots
  media/
  352K total
```

That is also the **first end-to-end proof of the v8.2.10 archive fix** — before
it, this call died with `PermissionError` on the retention volume.

`archived_by` is NULL on purpose: no console operator did this.

---

# PWE Studio v8.2.11 — overview counters became filters (2026-08-02)

**Shipped.** The platform console printed eight numbers an operator could read
but not act on: seeing "Paid Tenants 3" meant scrolling to the tenants table and
reconstructing the filter by hand. Seven of the eight now filter that table
directly.

## The trap this could easily have walked into

Most counters are defined by the **subscription** status:

```sql
paid_tenants  = subscriptions.status = 'active'
trial_tenants = subscriptions.status = 'trialing'
past_due      = subscriptions.status = 'past_due'
```

The Status select in the tenants toolbar filters `tenants.status`. **Two
different fields that share the same vocabulary** — active, trial, past_due.
Wiring a counter to that select is the obvious implementation, it runs without
error, and it is wrong: on the local fixture every tenant carries
`tenants.status = 'active'`, so "Paid Tenants 3" would have listed **5 rows**.
Measured in the browser, both ways:

```text
card says 3  ->  metric filter shows 3 rows   (t.subscription_status === 'active')
card says 3  ->  status select shows 5 rows   (t.status === 'active')
```

So `METRIC_FILTERS` in `super-admin.html` carries one predicate per counter,
each mirroring the SQL in `/v1/admin/usage`, including the
`NOT IN ('archived','deleted')` clause. All seven verified card-value ==
row-count in the browser.

**MRR is deliberately not a button.** It totals money, not tenants; no set of
rows follows from clicking it.

## Two things removed rather than added

* **The "Commercial Attention" card is gone.** It rendered the same three
  metrics as the counters immediately above it, filtered to non-zero — it only
  existed because those counters were not clickable. Removing it took a whole
  card, ~54 lines of JS and ~70 lines of CSS off the page.
* **Hover feedback moved to `button.stat-card`.** It used to sit on every card,
  promising an interaction five of them did not have.

## Applied filters are now visible

Clicking a counter used to set an invisible predicate and jump to a table that
silently disagreed with every control above it — and typing one character into
search wiped it. Now: a dismissible chip under the toolbar, `aria-pressed` on
the counter, a "Filtering" marker so the state is not colour-only (1.4.1), and
the filter composes with search/plan/category instead of being erased by them.
Clicking the pressed counter again releases it.

## Audit log

100 rows rendered flat, with a UUID in every fourth cell and no way to search.
Now 15 per page with prev/next, a filter box, an `n of m events` count, and the
resource column truncated with the full value in `title`.

## Contrast and target sizes, measured not assumed

```text
"Filtering" marker   --brand 3.68:1 on the card -> FAIL at 11px
                     --brand-dark 5.17:1        -> pass
pressed border       3.68:1  (non-text, needs 3.0)   pass
chip border          3.38:1                          pass
chip close button    24x44 -> 44x44 via ::after      pass (2.5.5)
counters             248x59 desktop, 167x71 mobile   pass
```

On mobile the two-up grid leaves ~167px per card and the marker broke the label
across mid-word lines; `.stat-head` wraps there so it drops to its own line.

## A pre-existing i18n bug fixed on the way

Labels written by script after load were past the dictionary pass that runs at
load, so `Page 1 of 7 · 5 tenants` reverted to English after any filter change.
`relabel()` re-localises the specific node. Deliberately per-node, not a subtree
walk: the dictionary translates any text it recognises, and a studio actually
named "Overview" would have become 总览 inside the tenants table.

## Guards

`backend/tests/test_platform_admin_overview.py` — 9 cases. The important two
assert that subscription-scoped counters read `t.subscription_status` and that
lifecycle counters exclude archived/deleted; verified by rewriting the `paid`
predicate to `t.status === 'active'`, which failed both. Suite: 434 passed.

---

# PWE Studio v8.2.10 — tenant archive and permanent delete repaired (2026-08-02)

**Shipped.** Archiving a studio returned "Internal Server Error" from the
platform console, three toasts deep, *after* the operator had typed the slug to
confirm. Permanent delete was unreachable behind it (it only accepts archived
tenants). Neither had ever worked in production.

## Root cause: a volume Docker had to invent a mountpoint for

```text
PermissionError: [Errno 13] Permission denied: '/app/backend/archives/tenants'

in the container:  drwxr-xr-x  0:0      /app/backend/archives     <-- root
                   drwxr-xr-x  10001    /app/tenants
                   drwxr-xr-x  10001    /data
                   drwxr-x---  10001    /media
```

Two correct decisions that fail together, the same shape as the v8.2.6 upload
bug:

* `backend/archives` is excluded by **both** `.gitignore` and `.dockerignore` —
  archives are mutable legal-retention data (they carry the only surviving copy
  of publication-consent evidence) and must never ride inside an image.
* `docker-compose.yml` mounts a named volume at `/app/backend/archives` so they
  survive image replacement.

So the path does not exist in the image. **Docker seeds a named volume from the
image path it covers and inherits that path's ownership — but when the path is
absent it creates the mountpoint root-owned.** The app runs as uid 10001. The
Dockerfile's `chown -R ... /app` runs at build time and cannot reach a volume
that is mounted at run time.

## The fix

`deploy/aws/Dockerfile` now creates `/app/backend/archives/tenants` before the
chown, so the volume seeds as 10001.

**Deploying was enough here, and the reason is worth knowing.** Docker seeds a
named volume from the image path whenever the volume is *empty*, not only at
first creation — and this volume had always been empty, because the feature it
existed for had never once succeeded. So recreating the container on v8.2.10
copied in the new directory with its ownership. Verified in the container after
deploy:

```text
drwxr-xr-x 3 10001 10001  /app/backend/archives
archive root OK: /app/backend/archives/tenants     # _ensure_archive_base(), as the app user
```

Had a single archive ever been written, the volume would not have been empty,
nothing would have been re-seeded, and the repair would have needed a one-time
`exec -u 0 app chown -R 10001:10001 /app/backend/archives`. Keep that in mind
for any other volume mounted over a path absent from the image.

## Why the symptom was a bare 500

`archive_tenant` began snapshotting immediately and hit the permission error
mid-way. `_ensure_archive_base()` now runs first and raises `TenantArchiveError`
— which the route already maps to a 400 with the message — naming the path and
pointing at the mount rather than the code. `permanently_delete_tenant` calls it
too: that final snapshot is the only surviving copy of the tenant's
publication-consent evidence, so it must refuse rather than delete with nowhere
to write the proof.

`_archive_root()` also hardcoded `current_app.root_path / "archives"`, ignoring
configuration that the media path beside it already honoured. It now reads
`ARCHIVE_DIR` (`STUDIOSAAS_ARCHIVE_DIR`), so the retention volume can move
without a code change.

## Guards

`backend/tests/test_tenant_archive_storage.py` — 4 cases, including the
production failure reproduced with a read-only parent, asserting the error names
the path and mentions the volume. Suite: 425 passed.

---

# PWE Studio v8.2.9 — status colours solved per theme (2026-08-02)

**Shipped.** Option D below was executed: all 45 semantic values regenerated,
the theme picker's grouping corrected, 88 new assertions added. The analysis
that led here is kept intact underneath, because the measurements are the
reason the constants are what they are.

## What changed

`docs/design/palette_gen.py` is the source of truth; `presets.py` is emitted
from it. The semantic block used to solve lightness against the page and
nothing else. It now solves saturation *and* lightness against every surface
the role lands on:

```text
constraint                                        floor
role as text on the page                          4.6
solid fill on --bg2 and on --panel                3.0
--on-accent label on that solid fill              4.5
color-mix(role 61.8%, text) on --bg2 / --panel    4.5
distance from the accent          hue >= 30 deg OR contrast >= 1.55

result: 45/45 solved, 0 unsolvable, 525 generator assertions pass
```

Saturation is pulled 60% from the role's anchor toward that theme's accent,
floored at 32%. **The floor is the one judgement call in the file:** without it
`studio-ink` (accent saturation 4%) drags danger to `#92625C` at S=23, which
stops reading as danger. At 32% it lands on `#9B5950` — muted, still red.

Two defects the fixed-saturation design had been hiding:

* `arcade-lime/dark` shipped **all three** fills under the 3:1 non-text floor
  (worst 2.89 on `--bg2`). Earlier passes measured this and set it aside
  because semantic *text* is compensated; a solid *badge* is not.
* Six values sat inside 30 degrees of their own accent with no lightness
  separation — `vintage-press` warning at 5 deg, `cedar-grove` success at 4
  deg. A warning badge indistinguishable from a button is a worse failure than
  a clashing one. These are the six that move a lot (11-16 lightness points);
  hue never moves, so green still means success.

## Deploy step that is easy to miss

Editing `presets.py` changes **nothing a tenant sees** — every tenant carries
its own resolved copy of the tokens in `settings.visual_theme`. The refresh
path is:

```bash
.venv/bin/python backend/scripts/migrate_visual_themes.py --dry-run
```

then without `--dry-run`. It is idempotent, and it skips `theme_mode=custom`
tenants by design — a studio that hand-tuned its colours chose those values.
Any colour input in studio-admin flips the tenant to `custom`, so this is safe.

**Production state: the refresh has now been run (2026-08-02).** 5 preset
tenants migrated, verified 0 mismatches against the v8.2.9 presets:

```text
dance-dance          rehearsal-rose light   #2E774D #8A622F #722F29   matches
lets-paint-showcase  harbour-calm   dark    #348D67 #997B30 #C85C5D   matches
lets-paint-studio    atelier-clay   light   #2D784E #5A411D #753129   matches
lets-play-piano      recital-plum   light   #32765C #8B6133 #AE4944   matches
ruby-s-studio        rehearsal-rose light   #2E774D #8A622F #722F29   matches
isolation-alpha      vintage-press  light   theme_mode=custom, skipped
```

Confirmed on the live site, `harbour-calm/dark` being the interesting case
because it sits closest to the constraints the solver targeted:

```text
fills on --bg2      3.17 / 3.22 / 3.17   (needs 3.0)
--on-accent labels  4.61 / 4.68 / 4.60   (needs 4.5)
```

**`isolation-alpha` was left alone on purpose, and it is worth knowing why.**
Its `theme_mode` is `custom` and the values are genuinely hand-picked, not a
stale preset snapshot — `accent_color #224466` is a blue that appears in no
preset, alongside `secondary_accent_color #663322`. `--include-custom` would
discard both. Check what a custom theme actually holds before reaching for that
flag; a tenant whose custom values happen to equal an old preset is a stale
snapshot and safe to refresh, one that differs is somebody's decision.

Backup taken first: `studiosaas_studiosaas_20260802T080141Z.dump`.

The command, for the next regeneration:

```bash
ssh pwestudio "cd /opt/pwestudio/current && docker compose -p pwestudio --env-file /opt/pwestudio/shared/production.env -f deploy/aws/docker-compose.yml -f deploy/aws/docker-compose.lightsail.yml --profile local-db exec -T app python backend/scripts/migrate_visual_themes.py"
```

Note the compose invocation: `lightsail_ctl.sh` composes *both* files with
`-p pwestudio --profile local-db`, and running a bare
`docker compose -f docker-compose.lightsail.yml` instead fails with
"service db has neither an image nor a build context".

## Guards added

`backend/tests/test_visual_theme_coherence.py` now asserts the five surface
constraints and the accent-distance rule per (preset, mode, role) — 88 cases.
Verified by reverting `cedar-grove` success and `arcade-lime` success to their
v8.2.8 values: both guards fired (2.89 < 3.0, and 4 deg at 1.11 contrast).

## Theme picker

The second swatch row was labelled "status colours, same in every theme" —
true in v8.2.8, false now. It reads "status colours, tuned to this theme" and
the row survives because status answers a different question than surface and
brand colour, not because the chips look alike.

---

# Analysis that produced option D (2026-08-02)

Running release at the time of writing was v8.2.8.

## Contrast is not the problem — that part is already solved

Measured across all 15 preset/modes, on the three surfaces the CMS actually
places semantic colour on:

```text
raw semantic vs page bg      ~4.6      (just over AA)
raw semantic vs panel        3.7-4.0   under AA
raw semantic vs bg2          2.86-3.34 well under AA
```

That looks alarming, but the CMS already compensates: semantic **text** goes
through `color-mix(semantic 61.8%, text-anchor)`, which lands the worst case at
**5.07**. Solid semantic **fills** carry `--on-accent` text, worst case
**4.56**. Both clear AA in every preset and mode. Semantic marks also carry
text, not colour alone, so WCAG 1.4.1 is satisfied.

So the strangeness reported is **not** legibility. It is harmony, and it has
two measurable causes.

## Cause 1 — saturation is fixed while the themes are not

Every preset ships the same semantic saturation:

```text
success  S=44    warning  S=58    danger  S=52     (identical in all 15)
accent   S ranges from 4 to 66
```

`studio-ink` is a deliberately neutral style — its accent saturation is **4
(light) / 7 (dark)**. Dropping a 58-saturation orange warning onto that screen
is why it reads as pasted in from another product. At the other end,
`arcade-lime/dark` has an accent at **66**, which makes a 44-saturation green
look washed out and weak. Dark modes show it most because their surfaces are
low-chroma, so a fixed-saturation mark has nothing to hide behind.

## Cause 2 — in 10 of 15 preset/modes a semantic hue merges with the accent

```text
vintage-press  light/dark   warning  4 deg from accent   (brown on brown)
cedar-grove    light/dark   success  4 deg               (green on green)
studio-ink     dark         warning  6 deg
atelier-clay   light/dark   danger  10 deg               (red on clay)
rehearsal-rose light/dark   success 23 deg
```

At 4 degrees a warning badge is the same colour as an ordinary button. The
semantic signal is gone — the opposite failure from the one the screenshots
show, and it is the more serious of the two.

## Option A+ — align saturation, then re-solve lightness (verified)

Pull each semantic colour's saturation toward the theme's accent, keep its
hue, then search lightness until both constraints hold again.

A naive version of this **fails**: adjusting saturation while holding HSL
lightness drops the worst solid fill to **3.88**, under AA, because HSL
lightness is not perceived luminance. With the lightness re-solve:

```text
unsolvable cases                0 of 15
worst text-on-fill              4.54   (AA needs 4.5)
worst fill-on-darkest-surface   3.02   (non-text needs 3.0)

studio-ink/light   success  #2F7850 -> #3D6C52   S 44 -> 28
arcade-lime/dark   success  #389164 -> #26A163   S 44 -> 62
```

Hue never moves, so green keeps meaning success. This addresses cause 1 and
leaves cause 2 untouched.

## Option B — separate merged hues by lightness, not by hue

For the 10 merged cases, pushing the hue is the wrong instrument: rotating
`cedar-grove`'s success away from green to clear its green accent would make
success stop looking like success. The workable axis is a minimum **lightness**
gap between the semantic fill and the accent, so a warning badge on a brown
theme is a distinctly lighter or darker brown-orange than the buttons around
it. Needs design work and a contrast re-check; not yet modelled.

## Option C — leave it

Defensible: nothing is illegible, nothing is inaccessible. The cost is that
low-chroma themes keep looking like they have a foreign badge set, which is
exactly the report.

## Option D — one shot: solve A+ and B together for all 45 values

B is now modelled, so the combined solve can be measured. One constrained
search per (preset, mode, role), hue fixed, saturation pulled 60% toward that
theme's accent with a floor, lightness solved for the nearest value that
satisfies all four constraints at once:

```text
C1 fill vs --bg2 and vs --panel        >= 3.0
C2 --on-accent text on the solid fill  >= 4.5
C3 mixed semantic text on bg2/panel    >= 4.5
C4 distance from accent: hue >= 30 deg OR contrast(semantic, accent) >= 1.55

45 of 45 solved, 0 unsolvable
worst fill-on-surface 3.00 | worst text-on-fill 4.50 | worst semantic text 5.07
42 of 45 values move
```

Two findings the earlier pass did not have:

1. **Three shipped values already fail C1.** `arcade-lime/dark` success,
   warning and danger are all under 3:1 against `--bg2`/`--panel`. The earlier
   pass measured 2.86 and set it aside because semantic marks carry text —
   true for text, but a *solid* badge fill on that theme is a real 1.4.11
   failure. This is a defect, not a preference.
2. **Six shipped values fail C4**, and the solver clears them by darkening
   11-16 lightness points (`vintage-press/light` warning `#8D6426 -> #5C441F`,
   `cedar-grove/light` success `#2F7957 -> #24513C`). That is a large visual
   move; it is the price of keeping the hue where it belongs.

**The saturation floor is the one design dial.** With no floor, `studio-ink`
(accent saturation 4) pulls danger to `#92625C` at S=23, which stops reading
as danger. `S_FLOOR = 0.32` keeps it at `#9D5A51` — muted but still red — and
the solve stays complete at the same contrast floors. Use 0.32.

**Recommendation: Option D, not A+ then B.** Both fixes rewrite the same 45
values in the same table; splitting them means generating and re-verifying that
table twice for one shipped result. **Coupling to watch:** D makes semantic
colours per-theme, so the v8.2.8 theme-picker grouping labelled
"status colours, identical across themes" becomes false and must move back in
with the themed swatches.

Model script: `scratchpad/semantic_model.py` (regenerate rather than hand-edit
the 45 values).

# PWE Studio v8.2.8 — Historical Handoff

## Colour roles bound to surface area — options 1, 2 and 3 applied (2026-08-02)

**All three are implemented and released.** The diagnosis is kept because the
defect was a naming error twice over, and that pattern will recur.

### What changed

**1 — Large surfaces stay in the accent family.** A derived `--accent-deep`
(`color-mix(accent 70%, ink)`) now terminates the two large gradients. The
preset's second hue was renamed `--accent-dark` -> `--accent-secondary` across
its 8 remaining uses, all of which are small marks (text, borders, badges),
which is what a split-complementary hue is for.

**2 — The picker shows what actually changes.** Six themed swatches, then a
labelled row "状态色 · 所有主题一致 / Status colours · same in every theme"
carrying success, warning and danger. They are still visible, but no longer
imply the theme failed to apply.

**3 — The brand-colour concept is retired from the UI.** The two inputs
labelled "Main brand colour" / "Supporting brand colour" always wrote the
theme's `accent_color` and `secondary_accent_color`; they are now labelled
Accent / Support, matching the swatches beside them, with Support marked
"Badges and small highlights only". They already sat inside "Fine-tune selected
theme", so the structure the question asked for — one preset system plus an
advanced override — was in place; only the naming misrepresented it.

### Verified

```text
dance-dance, rose theme (accent #A23F5D):
  before  command bar  ink -> #336D44  (green, 156 deg from accent)
  after   command bar  ink -> color-mix(#A23F5D 70%, #20181A)  (deep rose)
picker: 2 rows, 6 themed + 3 shared chips, note translated in both languages
inputs: 强调色 / 辅助色 and Accent / Support, both languages
pytest 333, legacy smoke 73/73, tenant isolation 228/228, escaping/inline/terminology OK
```

`--accent-secondary` and the tenant record's `primary_color` / `secondary_color`
columns still exist; the columns identify a studio in the platform console and
feed nothing that renders. Option 4 (tinting semantics toward the theme) stays
on the shelf — with 1 and 2 done, the remaining semantic colours read as
deliberate small marks rather than as strays.

## The reported symptom has two separate causes

### 1. A misleading token name put a complementary colour on a large surface

The command bar renders `from-indigo-900 to-indigo-700`. The shell maps
`from-indigo-9` to `--ink` and `to-indigo-` to `--tenant-secondary`. Measured
live on `dance-dance`:

```text
command bar  linear-gradient(to right bottom, rgb(32,24,26), rgb(51,109,68))
                                              --ink #20181A   #336D44  green
theme accent #A23F5D  (rose)
```

A rose studio gets a green command bar. The same mechanism produced the purple
bar on the green theme in the other screenshot.

`--tenant-secondary` is fed by `secondary_accent_color`, which every preset
defines as a **deliberately distant** second hue:

```text
preset            accent -> secondary
vintage-press       169 deg apart
lets-play-game      170 deg apart
studio-ink          164 deg apart
rehearsal-rose      156 deg apart
atelier-clay        150 deg apart
harbour-calm         34 deg apart
recital-plum         46 deg apart
```

That is correct *as a palette*: a split-complementary second hue is what you
want for a small accent, a chart series, a badge. It is wrong as **half of a
large gradient**, because at that size a near-complementary pairing reads as
two products rather than one.

The reason it ended up there is a naming defect. The theme map assigns:

```js
secondary_accent_color: ['--accent-dark', '--brand-accent-strong'],
```

`--accent-dark` reads as "the dark variant of accent" — same hue, lower
lightness. It actually holds the complementary second hue. On `dance-dance`,
`--accent-dark` is `#336D44` (green) while `--accent` is `#A23F5D` (rose).
Anyone reaching for `--accent-dark` to darken a large surface gets a hue
inversion instead, and the name gives no warning.

Verified by experiment: repointing that one variable to a true dark accent
(`color-mix(--accent 70%, --ink)`) turns the command bar rose and the whole
screen resolves to one family, with only the amber count badge and the green
connection dot left as small semantic marks — which is what those should be.

### 2. Semantic colours barely move between themes, and the picker advertises it

Across the 7 presets, hex values all differ, but hues cluster:

```text
success  145-158 deg   (7 distinct hex, 13 deg of spread)
warning   32-43  deg   (7 distinct hex, 11 deg of spread)
danger   360-12  deg   (7 distinct hex, 12 deg of spread)
```

Holding semantics steady is **correct** — green must keep meaning success
whatever the studio picked, and the CMS uses them on small marks where standing
apart is the point. The problem is not the colours; it is that the theme picker
displays all nine tokens as equal swatches, so three of the nine look identical
between "独奏紫" and "排练玫瑰" and the picker appears not to have applied.

## On "do we need two colour systems?"

The instinct is right, and v8.2.7 already retired `primary_color` from
rendering. But dropping to one source would **not** have fixed this: the green
command bar came from the preset's own `secondary_accent_color`, not from a
brand colour. The missing rule is not "how many sources" — it is **which roles
may occupy large surfaces**.

## Options considered

**1 — Give large surfaces an accent-family colour (root fix).** Introduce a
real `--accent-dark` (derived: `color-mix(in srgb, var(--accent) 70%,
var(--ink))`) and move `secondary_accent_color` to a correctly named
`--accent-secondary`, used only for small marks. Repoint the `to-indigo-`
gradient rule at the new dark accent. Verified above; ~3 CSS rules plus the
theme-map key. Removes the class of bug, not just this instance.

**2 — Make the picker show what actually changes.** Lead with the four tokens
that carry the theme (page, panel, accent, secondary) and group success /
warning / danger under a labelled "shared across all themes" row. Costs
nothing, and answers the "did it apply?" question the screenshots raise.

**3 — Finish the data-model convergence.** Retire `secondary_color` from
rendering as `primary_color` already is, leaving presets as the single source
and the existing fine-colour disclosure as the advanced override. Do this
*after* 1, or the same complementary hue simply arrives from the preset.

**4 — Tint semantics toward the theme.** `color-mix(success 85%, accent)` so a
green still reads as success but belongs to the palette. Only worth doing if 1
and 2 leave the screens still feeling mixed; it costs a contrast re-check of
every semantic pair in both modes, and over-mixing damages the signal.

**Chosen: 1 + 2 + 3, all applied in v8.2.8.** 1 is the actual defect and is
already proven; 2 fixes the perception the screenshots are really about; 3 is
the tidy-up the question asks for and is safe once 1 lands. 4 stays on the
shelf.

# PWE Studio v8.2.7 — Historical Handoff

## CMS colour coherence — Option B applied (2026-08-01)

**Option B is implemented and released. Option C is retained below as the
upgrade path.** The diagnosis is kept in full because it explains why B is
sufficient and what C would add.

### What changed

`_default_visual_theme()` returns the preset whole. The two lines that
substituted `accent_color` / `secondary_accent_color` with the tenant's
`primary_color` / `secondary_color` are gone.

This also removes an inconsistency between two adjacent paths: a tenant that
had chosen a style already got `style_theme(style_id)` untouched, so only
tenants *without* a stored theme were being overwritten — which is exactly the
set that looked wrong. Measured before and after, background-to-accent hue
separation:

```text
tenant                 before   after
lets-paint-showcase     160deg    3deg     (stored no theme -> was overwritten)
lets-paint-studio         3deg    3deg     (stored #955037, already coherent)
dance-dance               2deg    2deg
lets-play-piano           1deg    1deg
lets-play-game            0deg    0deg
```

Every tenant now sits inside the range the presets were designed for. No data
migration was needed: tenants with a stored theme already held preset values.

### Known cost of Option B

`primary_color` no longer reaches any rendered surface. It stays on the tenant
record, identifies the studio in the platform console, and is the intended
input for Option C. A studio whose brand colour is teal now picks a
teal-family preset rather than injecting teal into a clay palette — the theme
picker is the supported route, and it ships 8 styles × light/dark.

If a studio's exact brand hex must appear in the product, that is Option C, not
a reinstatement of the override.

### Option C — upgrade path, not scheduled

Derive all 21 tokens from `primary_color` instead of substituting one, so a
tenant gets a literal brand colour *and* a coherent palette. Requirements:

- solve every foreground/background pair for contrast in both light and dark —
  the presets encode this by hand today, and `backend/scripts/palette_gen.py`
  asserts each generated pair against page and panel;
- keep semantic success/warning/danger distinguishable from the brand hue when
  the brand is itself green, amber or red;
- `docs/design/palette_gen.py` exists as a design-time tool and would need to
  become runtime-safe (deterministic, no I/O, bounded).

Until then, B holds: presets stay whole, and the brand colour lives where it
faces customers by preset choice rather than by injection.

## It is not "too many changes", and the role mapping is not miscategorised

The CMS looks incoherent because **two colour sources are fighting inside one
screen**, and one of them overwrites the other at its most visible point.

`_default_visual_theme()` (`api_v1.py:1047`) does this:

```python
theme = dict(_preset_for(category)["theme"])   # 21 designed tokens
if primary_color:
    theme["accent_color"] = primary_color      # replaced with an arbitrary brand colour
if secondary_color:
    theme["secondary_accent_color"] = secondary_color
```

The presets are good. Every one declares a harmony and holds to it — measured
across all 15 preset/mode combinations, the hue distance between
`background_color` and `accent_color` is:

```text
0–6 deg   13 of 15 presets      (analogous: the accent belongs to the surface)
20 deg    studio-ink light      (a deliberately neutral/monochrome preset)
30 deg    studio-ink dark       — the largest separation any preset ships
```

`lets-paint-showcase` runs `atelier-clay`, whose designed pair is
`bg #F3ECEA` (hue 13) with `accent #955037` (hue 16) — **3 degrees apart**. But
its `primary_color` is `#173f3a`, so the accent that actually renders is hue
**173**:

```text
designed separation      3 deg   warm clay accent on warm paper
rendered separation    160 deg   cold teal accent on warm paper
```

160° is near-complementary — the single highest-tension relationship on the
colour wheel — and it is **5× the largest separation any preset ships**. The
other 19 tokens (surface, panel, text, border, success/warning/danger, focus
ring) stay warm, so every primary button, the selected nav item, the sidebar
and the command bar read as belonging to a different product than the page
they sit on. The focus ring compounds it: `atelier-clay` ships
`#BA6445` (warm), which now surrounds teal controls.

So: the Tailwind role map is working, the presets are well made, and nothing
was over-edited. One line injects an unconstrained hue into a palette that was
solved as a whole.

## Why the two consoles look different today

| | Studio Admin | Studio CMS |
|---|---|---|
| Palette | fixed `:root` — paper `#f7f5f2`, ink `#0e1729`, brand `#3b82f6` | full 21-token tenant theme |
| Applies tenant theme | no (`setTenantTheme` not called) | yes |
| Audience | owner, occasional configuration | staff, all day |

Studio Admin is calm because it never varies. That is the comparison worth
making, but it is not automatically the answer for the CMS.

## Options considered

**A — Give the CMS a fixed palette like Studio Admin.** Removes the conflict by
removing the variable. Predictable, one palette to maintain, and the ~1,400
mapped utilities keep working (they would resolve against fixed tokens). Cost:
a studio never sees itself in the tool it uses most, and the eight themes plus
the whole theme picker become dead weight for this surface.

**B — Stop overwriting the preset accent (recommended).** Delete the two
override lines and let `primary_color` govern the public surfaces (portal,
register, website) where the brand actually faces customers, while the CMS
renders the preset as designed. One-line-scale change, removes the conflict at
its source, keeps 15 coherent looks, and the theme picker stays meaningful.
Cost: a studio whose brand is teal picks a teal-family preset instead of
injecting teal into a clay one — which is what the picker is for.

**C — Regenerate the whole palette from `primary_color`.** True brand theming
with harmony preserved: derive all 21 tokens from the brand hue rather than
substituting one. `docs/design/palette_gen.py` already exists but is a design
tool, not runtime. Cost: real work — every derived pair needs its contrast
re-solved across light and dark, which is what the presets encode by hand
today. Right long-term answer if brand fidelity in the CMS matters.

**D — Constrain `primary_color` to the preset's own palette.** Cheap and
guarantees harmony, but it turns the brand colour into a pick-list and will
frustrate a studio with an existing brand.

**Chosen: B, applied in v8.2.7. C retained above as the upgrade path.** B is small, reversible, and fixes
the reported symptom at its cause today; A discards working machinery to solve
a problem B solves with two lines; C is the only option that keeps literal
brand colour *and* harmony, so it is the upgrade path — not the first move.
Whichever is chosen, the CMS and Studio Admin do not have to match: they have
different audiences, and a daily workspace carrying the studio's own colours is
a feature, provided the colours agree with each other.

Note: the `color` domain of the design database returned no match for this
query; the guidance used here is `color-semantic` and `destructive-emphasis`
from the shared UX rules (Material / Apple HIG), plus the hue measurements
above.

# PWE Studio v8.2.6 — Historical Handoff

**All findings below are fixed and released.** The diagnosis is kept in full
because the P0 was a two-component failure that neither component owned, and
that shape will recur.

## Verification for v8.2.6

```text
pytest: 316 passed (309 + 7 new in test_media_upload_privileges.py)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Least-privilege role rehearsal (role owning nothing, as in production):
  old code path -> InsufficientPrivilege: must be owner of table media_assets
  new code path -> ensure_media_schema() completes, no DDL issued
Upload round-trip: owner 200, super-admin without session 403 (actionable),
  super-admin with session 200
Image resources, 24 MP source (6000x4000):
  before  decoded 6000x4000, peak RSS +139 MB, 0.22s
  after   decoded 3000x2000, peak RSS  +17 MB, 0.14s
  81 MP bomb rejected as a 400, not an OOM
Browser: preview language now drives previewSections (中文 主理人/课程与班次
  <-> Principal/Courses & Classes); CTA pair switches; 3 disclosures hiding 21
  fields, all collapsed, all summaries translated; theme-picker and
  settings-shell both measure exactly 1.618; 0 overflow; no console errors
```

The regression test was checked by reverting the guard: it fails, then passes
again once restored. `media derivative backfill is incomplete` remains the
known worktree artifact (`media/` is git-ignored, so originals live only in the
primary checkout).

## What was wrong, and why it took a production log to find

## P0 (fixed) — every media upload in production returned 500

Production log, reproduced three times today (06:00, 06:37, 11:51 UTC):

```text
psycopg.errors.InsufficientPrivilege: must be owner of table media_assets
POST /s/lets-paint-showcase/v1/tenant/logo 500
```

`store_media_asset()` calls `ensure_media_schema()` as its **first statement**,
and that helper runs `ALTER TABLE media_assets ADD COLUMN IF NOT EXISTS …`.
`ALTER TABLE` requires table ownership, and PostgreSQL checks the privilege
*before* evaluating `IF NOT EXISTS` — so the statement fails even though the
column has existed since `0001_schema_v1.sql` and `0017` already widened its
CHECK constraint. The production role is the least-privilege role introduced in
v7.7.7; it holds DML rights but does not own the table.

`store_media_asset()` is the only entry point for media, so this breaks
**logo, hero/principal images, student photos, registration photos and
portfolio uploads alike** — not only the logo.

It is not caused by the super-admin account: an owner account fails identically
in production, and locally (where the role owns the schema) both accounts
succeed.

**Fix:** stop issuing DDL on the upload path. Probe
`information_schema.columns` first and only attempt the `ALTER` when the column
is genuinely absent, so a correctly migrated database — every deployed one —
executes no DDL and needs no ownership. The helper's stated purpose is
compatibility for *older local* databases, which that preserves. Do not grant
table ownership to the application role; that would undo v7.7.7 for a code
path that should not need it.

## P1 (fixed) — super-admin support gate was correct but undiscoverable

A super-admin with no active support session gets
`403 support_session_required` with an actionable bilingual message, and
`api()` surfaces `data.message`, so the message does reach the user. After
starting a session from the Super Admin console the same upload returns 200.
The boundary works and should stay.

What is missing is the route to it: Studio Admin never tells a super-admin that
a session is required, nor offers a way to start one. **Fix:** on 403
`support_session_required`, show the reason with a link back to the tenant's
Super Admin entry. Every super-admin action on a tenant is already written to
`audit_logs` with the support-session marker merged in (`api_v1.py:1278`), so
the logging the user asked about already exists — it needs surfacing, not
building.

## P1 (fixed) — preview language switch covered 6 of 11 nodes

Measured by snapshotting every `[id^="preview"]` node in both languages:
only `previewRegisterTitle` and `previewRegisterIntro` actually changed for
this tenant. Two separate causes:

1. **Not wired.** `renderPreviewSections()` reads only the Chinese label
   fields (`settingCoursesLabel`, `settingGalleryLabel`, `settingFaqLabel`,
   `settingContactLabel`) and ignores the `*LabelEn` inputs that sit right
   beside them in the form. It also hardcodes English strings — `Principal`,
   `Student Area`, `Program cards`, `Student works` — which stay English in
   Chinese mode. `previewHeroEyebrow` has only a single-language input.
2. **Data, not code.** For `lets-paint-showcase`, `localizedCopy.heroTitle` is
   `{en: "Let's Paint Studio", zh: "Let's Paint Studio"}` and `coursesLabel` is
   `{en: "Courses & Classes", zh: "Courses & Classes"}` — both languages hold
   the same string, so a correctly wired switch still shows no visible change.
   This is why the switch reads as broken even where it works.

**Fix:** route every bilingual field in the preview through `localizedValue`,
move the hardcoded section nouns into the i18n dictionary, and mark fields
whose English is empty or identical to the Chinese so the operator can see
what still needs translating rather than guessing the switch is broken.

## P2 (fixed) — dead duplicate of the schema helper

`api_v1.py:1582 _ensure_media_schema` has no callers and its CHECK constraint
is missing `website_image`, so it is both dead and stale. Delete with the P0
fix.

## P2 (fixed) — tab density, and where disclosure belongs

Field counts per tab, measured in the running page:

| Tab | form-groups | inputs | disclosures today |
|---|---:|---:|---:|
| 报名 register | 23 | 29 | 0 |
| 品牌 brand | 22 | 26 | 2 |
| 官网 website | 18 | 23 | 0 |
| 首屏 hero | 12 | 13 | 0 |
| 常见问答 faq | 8 | 16 | 0 |
| 家长话术 messages | 5 | 5 | 0 |
| 数据分析 analytics | 0 | 2 | 0 |
| 预览与发布 advanced | 0 | 0 | 0 |

Three tabs carry 23–29 inputs in one flat column. The split that works here is
**what a studio must set to go live** versus **what it will only ever revisit**
— not "basic versus advanced", which invites hiding things people need.

- **brand**: keep studio name, logo, theme preset and the two brand colours
  open. Fold contact details (phone/email/address), the bilingual slogan pair,
  CMS layout + welcome message, and timezone. Plan is read-only and belongs
  with them.
- **register**: the tab already has two headings — 报名表 and 报名问题. The
  question editor is a repeating list that only changes when the studio
  rethinks its intake; fold it and leave the form's own copy open.
- **website**: the six switches are the tab's real subject and stay open. The
  per-section label pairs (courses/gallery/faq/contact, each 中文+English) fold
  behind one "版块名称" disclosure — six inputs that exist only to rename
  headings.
- **hero**: 13 inputs is tolerable; fold nothing. Do **not** fold the English
  half of a bilingual pair anywhere — that reads as "optional" and is exactly
  the habit that produced the untranslated `localizedCopy` above.

Reuse the `.disclosure` component added to this page in v8.2.4 (44px summary,
chevron, focus ring, `prefers-reduced-motion` handled) rather than introducing
a second pattern, and add each new summary string to `admin-i18n.js` — an
English summary on a Chinese page is the defect this page hit twice already.

Sequencing note: this and the preview-language fix touch the same panels, so
they should land in one round to avoid two passes over the same markup.

## P2 (fixed) — golden ratio applied unevenly

`.settings-shell` already uses `minmax(0, 1.618fr) minmax(360px, 1fr)`, the
proportion used across the CMS profile sheet and the product-home hero.
`.content-grid` (line 656) uses `1.5fr : 1fr` and `.theme-picker` (line 1121)
uses `.9fr : 1.1fr` — the second inverts the emphasis, giving the swatch grid
more room than the picker controls. Aligning both to 1.618 : 1 would make the
brand workspace internally consistent with the rest of the product.

# PWE Studio v8.2.5 — Historical Handoff

## Platform console on mobile, product-home contrast — packaged (2026-08-01)

**Baseline:** v8.2.4. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### Platform console was built for a desktop and only tolerated on a phone

Measured at 375×812 before the change: the page did not overflow horizontally,
but `@media (max-width: 768px)` forced `.stats-grid` to a single column, so the
eight counters cost roughly 350px of extra scrolling and the phone showed three
numbers and nothing else. The tenant table is seven columns and 1040px wide;
scrolled sideways at 375px it squeezed status pills into vertical stacks of
single characters — unreadable, not merely cramped. Nav links measured 42px
against the 44px touch minimum.

- Counters are two-up on phones (375px leaves 343px of content width), single
  column only below 360px.
- The tenant table becomes **one card per row** on phones, each cell carrying
  its column name. The label is a real text node, not a `::before`/`attr()`
  pair, so the i18n dictionary — which walks text nodes — translates it;
  verified rendering as 工作室 / 套餐 in Chinese.
- Remaining sideways-scrolling tables (audit, plans) get a faded edge so a
  column cut at the screen boundary does not read as missing data.
- Nav links now 46px; the signed-in address is hidden on phones (reference
  information that was taking a full line above the buttons that act).

Desktop was re-verified after the change: table renders as `table`, `<thead>`
visible, `.cell-label` hidden, counters back to three columns.

### Product home carried a real contrast failure, not just a styling nit

The "Backed by Let's Paint Studio" card is a dark navy panel that never set a
text colour, so its heading inherited `--ink` (Family Navy) from the page and
measured **1.14:1 against its own background**. It was legible only where the
translucent panel happened to sit over a pale part of the artwork behind it.
White measures 14.6:1; the supporting line moved to .78 alpha for 7.3:1.
`.privacy-note` measured 4.37:1 against its panel, just under AA for 12.5px
text, and moved to `--slate-600` at 6.4:1 — it carries a privacy instruction,
so it is the last line that should be hard to read.

A scripted contrast sweep across every text node on the page (compositing alpha
against the nearest opaque ancestor) now reports **zero failures** at both
1280px and 375px.

Mobile hero: `h1` was `clamp(3rem, 16vw, 4.3rem)`, which resolves to 60px at
375px — barely below the desktop setting — so "administration" filled a line by
itself and the headline ran six lines and ~700px before the reader reached the
supporting copy. At 9.5vw it sets ~36px and holds three lines, which brings the
lede and **both calls to action onto the first screen**.

### Verification

```text
pytest: 309 passed
Browser (local, Chrome):
  platform console @375: 0 horizontal overflow, counters 2-up (166.5px each),
    nav 46px, tenant table 1081px -> 307px card layout, labels translated
  platform console @1280: table/thead/counters unchanged from v8.2.4
  product home @1280 and @375: 0 contrast failures across all text nodes
  product home @375: 0 overflow, no undersized targets, headline 6 -> 3 lines
```

# PWE Studio v8.2.4 — Historical Handoff

## Theme completeness, console information architecture, SEO — packaged (2026-08-01)

**Baseline:** v8.2.3. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### The Tailwind debt was measured, not guessed

The CMS carries 1,422 Tailwind colour utility uses across 154 distinct
utilities, remapped to tenant tokens by role (danger/success/structure) in the
shell stylesheet. Scripted coverage analysis against the `[class*=]` mapping
table found **148 of 154 already re-pointed** — the architecture works. The
entire gap was `ring-*`, which Tailwind implements through its own
`--tw-ring-color` and which the role map never claimed: all 65 focus rings drew
Tailwind indigo, so a clay or forest studio got an indigo halo on every focused
input, and on a dark theme an indigo ring against a dark panel can fall under
the 3:1 WCAG 1.4.11 requires of a focus indicator. The tenant palette had
shipped `focus_ring_color` all along.

`ring-*` is now mapped by family — not by the six utilities in use today — so a
ring added later is themed on arrival. Coverage is now 1,421/1,422; the
remaining `placeholder-gray-400` is already handled by the shell's generic
`::placeholder` rule. **No tenant rebuild was needed**: the problem lived in one
shared stylesheet, not in tenant data, so deleting and recreating the six
workspaces would have carried risk for zero benefit.

### Platform console reordered as a work surface

Overview presented eight counters in one undifferentiated grid, giving "Past
Due" (chase an invoice) the same weight as "Total Tenants" (a standing fact),
and put the list naming the at-risk tenants *below* all eight. It is now
ordered by what the operator does with each block: **Needs attention** (Past
Due / Trials Ending / Onboarding, with Commercial Attention directly beneath) →
**Business health** (five standing totals) → **30-Day Acquisition Funnel**,
last and collapsed by default. All ids unchanged; the JS addresses them by id,
so no data path moved.

### Studio Admin controls simplified without losing customisation

- Six "Show / Hide" dropdowns — two taps and a popup each to set a boolean —
  are one switch list. State is carried by knob position as well as colour, so
  it survives a colour-blind reading. Same six settings, same ids.
- The eight visibility controls moved from `<select>.value` to
  `.checked` via `toggleOn()` / `setToggle()` helpers; 24 call sites converted,
  zero `.value` references left. `change` listeners were untouched (checkboxes
  fire it too).
- Five fine colour inputs are collapsed behind a disclosure. Every field stays
  present and editable — the theme picker above already produces a complete,
  contrast-checked palette, so this is refinement, not setup.

### Product home

Release-evidence link removed from the public footer and placed inside
`/platform-admin` (it is an internal delivery record, and the public link had
gone stale — still pointing at the v8.1.0 notes two releases later).
Reachability for both audiences is now asserted by tests rather than assumed.

SEO: the title led with the brand and a tagline, so the page ranked for nothing
but its own name. It now leads with what a studio owner searches for, under 60
characters, plus canonical, keywords and Open Graph/Twitter cards so a shared
link renders as a titled card instead of a bare URL.

### Verification

```text
pytest: 309 passed (2 new reachability tests)
Legacy CMS smoke: 73/73 · Tenant isolation: 228/228
Tailwind coverage: 148/154 -> 153/154 distinct (1,421/1,422 uses)
Browser (local, Chrome):
  platform console order: Needs attention -> Commercial Attention ->
    Business health -> funnel (collapsed); funnel still loads on expand
  Studio Admin switches: all 8 load from server state as checkboxes
  round-trip: Gallery off -> Save Draft -> websiteProfile.showGallery=false
    in DB, other seven unchanged -> reload shows off -> restored to on
  switch geometry 46x26, on=brand accent knob right, off=grey knob left
  both consoles verified in Chinese and English; no console errors
```

Two defects were found by browser verification and fixed before release: the
new group headings were not in the i18n dictionary (English text on a Chinese
page), and the switch resolved `--accent`/`--panel`/`--focus-ring`, none of
which Studio Admin defines — it uses `--brand-accent` — so the track rendered
transparent and 42px tall under the global `input` rule.

# PWE Studio v8.2.3 — Historical Handoff

## Audit remediation round — packaged (2026-08-01)

**Baseline:** v8.2.2, commit `dc06b8c`. **Branch:** `claude/ui-ux-pro-max-audit-073a82`.

### Release hygiene repaired first

`main` had been left at v8.0.1 while v8.2.0/8.2.1/8.2.2 shipped from
`codex/v8.2.1-ics-p0`, and the tag series stopped at `v8.0.1`. Anyone starting
from `main` would have silently reverted the ICS and consent-checkbox repairs.
`main` was fast-forwarded to `dc06b8c` (no divergence — 23 commits ahead, 0
behind) and the missing annotated tags `v8.2.0`, `v8.2.1`, `v8.2.2` were
created on their release commits. Keep releasing onto `main` from here.

### What v8.2.3 fixes

**Operations log was structurally incomplete.** In SaaS mode the CMS log is
synthesised from the credit ledger, so it could only ever show check-ins,
top-ups, adjustments and refunds. Archiving, renaming, roster changes,
portfolio and consent edits were sent inside `save()`, which persists students
and packages and drops everything else — those operations were recorded in
`audit_logs` server-side but no CMS surface read that table. The log page now
merges `/v1/audit-logs` into the ledger rows under a whitelist that excludes
platform noise (`auth.*`, `support.*`, `tenant.*`) and the three actions the
ledger already covers, so nothing appears twice. Each merged row names the
actor. The endpoint is owner-scoped; other roles get 403 and keep the
ledger-only view rather than an error they cannot act on.

**Roster entries had no time.** "加入今日排课" from a student profile and
班组模板套用 both called the roster endpoint without `classTime`, so the entry
stored `class_time` NULL and the day grouped the student under 时间未设置 —
while the roster page's own add box has always defaulted to the studio's
configured time. Both paths now send a time: the weekly schedule's slot when
one already places that student, otherwise the studio default.

**Assets could be served from a previous release.** `/assets/cms-app.js` and
its siblings live at stable paths, so a browser, PWA or CDN edge holding an
older copy runs last release's JavaScript against the current API — which is
what the reported "编辑后无页面" turned out to be, and it survives a reload.
Every HTML shell now carries an `__APP_VERSION__` placeholder on each JS/CSS
URL, stamped at serve time from `APP_VERSION`, so the version can never drift
from the running release. All eight HTML-serving routes were moved onto the
stamper; browser verification caught one route
(`/<slug>/studio-admin`) still leaking the raw placeholder, now fixed. The six
generated tenant workspaces were regenerated so they carry it too.

**Polish:** the dashboard's 长期未到访 list printed the `daysSince` sentinel
as "9999天前" and now reads 从未上课; the student-card roster button said
去排课 when the student was already on today's roster and 排课 when they were
not (backwards on both) and now matches the profile sheet's 查看排课/加入排课;
the ledger's importer note ("Core opening balance import source:…") is shown
as 数据迁移期初余额; the balance field in the edit form no longer uses a
tinted fill that read as disabled.

**Not changed:** the CMS carries ~1,389 Tailwind colour utilities remapped to
tenant themes by the shell stylesheet. It is architectural debt, not a defect —
every tenant theme verified correct in this round — so it was left alone per
the "fix it if it breaks" instruction. An earlier audit note claiming the CMS
sidebar buttons lacked accessible names was a misread of the browser tool's
output; the buttons carry visible text and `Icon` is already `aria-hidden`.

### Verification

```text
pytest: 307 passed
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
UI escaping, terminology, inline scripts, CMS bundle freshness: pass
Browser (local, v8.2.3, Chrome):
  operations log 43 -> 45 rows; the profile-path roster add that was
    previously invisible now appears with its actor
  roster add via profile -> class_time 14:30 in daily_roster_entries
    (the pre-fix entry on the same day remains NULL, shown side by side
    as 14:30 / 时间未设置)
  student cards: 23 加入排课 + 1 查看排课, matching roster state
  长期未到访: 12 rows read 从未上课, zero "9999"
  front-desk role -> /v1/audit-logs 403, log page degrades to ledger view
  all 9 HTML surfaces: zero unsubstituted placeholders, assets stamped v8.2.3
  no console errors
```

`media derivative backfill is incomplete` is the one non-passing gate line. It
is a worktree artifact: `backend/media/` is git-ignored, so the original files
live only in the primary checkout and no derivative can be generated from an
absent original. It is unrelated to this round's changes.

# PWE Studio v8.2.2 — Historical Handoff

## P0 public-registration consent visibility hotfix — deployed (2026-08-01)

**Current production truth:** branch `codex/v8.2.1-ics-p0`, packaged application
commit `976385874c085d30379f8ffc475ca4cb20a2e235`, active Lightsail release
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.2`, image
`studiosaas:8.2.2`. Internal and public deep health report
`appVersion=8.2.2`, `db=ok`, `mode=saas`. This release retains the complete
v8.2.1 ICS endpoint-kind repair and adds the public registration fix below.

### Root cause and repair

The Studio Portal wraps its mandatory privacy checkbox in `.fld`. The shared
`.fld input` rule intentionally sets `appearance:none` for text inputs and
selects, but it also matched this checkbox. Chrome changed the checked value
while continuing to draw an empty box, and the existing validation error stayed
visible. Visitors therefore had no credible feedback that their click worked
and reasonably believed the form could not proceed.

v8.2.2 restores the native checkbox control on both public registration
surfaces, retains the tenant accent colour, resets inherited text-input padding,
and keeps the whole consent label as the 44px-or-larger touch target. Once the
mandatory box is checked, its field error and ARIA invalid state clear
immediately. Generated tenant workspaces were refreshed from the authoritative
templates so existing and future tenants receive the same repair.

### Acceptance evidence

```text
Focused portal/theme/workspace tests: 32 passed
Full pytest suite: 305 passed, 2 skipped
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
Local browser, Studio Portal:
  checkbox click -> accessibility state [checked]
  native visible tick rendered in the tenant theme
  validation error shown when unchecked and cleared immediately when checked
Local browser, Quick Registration:
  checkbox click -> accessibility state [checked]
Production browser, Studio Portal:
  checkbox click -> accessibility state [checked] and visible tenant-colour tick
  unchecked validation error -> checked -> error cleared immediately
Production browser, daily roster ICS retained from v8.2.1:
  preview 2 events (1 class + 1 explicit 1-to-1)
  GET daily-roster/calendar.ics 200
  downloaded 1469-byte vCalendar, 2 VEVENT, Melbourne TZ
No registration was submitted and no production roster data was changed during
browser acceptance.
```

Release artifacts:

```text
PWE-StudioSaaS-aws-8.2.2.tar.gz
  sha256 2d5a2fd2d3e487be656e6027599c21a071a12347a8a361fe0763431d86930917
PWE-Studio-Edition-8.2.2.tar.gz
  sha256 6945cfe7b5fa50fd2fa7f06d59b0dab3dc1868364e95ae0db3144888da44201a
```

Both bundles passed checksum, BUILD_INFO, entrypoint and exclusion checks. The
deployment controller created a PostgreSQL logical dump and media-volume archive
at 06:15 UTC before switching from retained v8.2.1 to v8.2.2. HTTP redirects to
HTTPS, TLS verification is 0, the public edge returns HTTP/2 200, and both
containers are healthy.

# PWE Studio v8.2.1 — Historical P0 ICS handoff

## P0 ICS endpoint-kind hotfix — deployed (2026-08-01)

**Current production truth:** branch `codex/v8.2.1-ics-p0`, application commit
`1cada917d05c09e50fd5fc4b7f658baf274de517`, active Lightsail release
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.1`, image
`studiosaas:8.2.1`. Internal and public deep health report
`appVersion=8.2.1`, `db=ok`, `mode=saas`.

### Root cause and repair

Production access logs proved the selected-day button first requested
`/daily-roster/calendar`, then incorrectly downloaded
`/class-schedules/calendar.ics` and received 409. The browser merged
`{kind, ...calendar}`: the server-owned document kind `daily-roster`
overwrote the UI endpoint selector `roster`, so the download branch fell into
the weekly-schedule endpoint. Its automatic conflict refresh then replaced the
correct daily preview with the tenant's empty fixed schedule, producing the
reported zero-event dialog.

v8.2.1 keeps the two concepts separate:

- server document kinds remain `daily-roster` and `weekly-schedules`;
- UI routing uses a separate `downloadKind` constrained by one explicit
  preview/download endpoint contract;
- the browser rejects a preview whose server kind does not match the requested
  export instead of silently selecting another endpoint;
- the same `downloadKind` is retained during revision-conflict refresh.

### Acceptance evidence

```text
Focused ICS/API/UI/resource suite: 126 passed
Full pytest suite: 303 passed, 2 skipped
Legacy CMS smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS

Local browser, populated fixed schedule:
  preview 3 events -> GET class-schedules/calendar.ics 200
  downloaded file 1975 bytes, 3 VEVENT, weekly RRULE, Melbourne TZ, valid VCALENDAR
Local browser, selected day:
  preview 1 group event -> GET daily-roster/calendar.ics 200
  downloaded file 1144 bytes, 1 VEVENT, Melbourne TZ, valid VCALENDAR
Production browser, selected 2026-08-01 roster:
  preview 2 events (1 class + 1 explicit 1-to-1)
  GET daily-roster/calendar.ics 200
  downloaded lets-paint-studio-roster-2026-08-01 (1).ics
  1469 bytes, 2 VEVENT, Melbourne TZ, valid VCALENDAR
```

The production tenant currently has no saved fixed classes. Therefore
`固定课表 ICS` is correctly disabled there rather than producing an empty
file; its populated-data browser path was accepted against the isolated local
PostgreSQL tenant. No production schedule or roster data was added, removed or
changed during this hotfix.

Release artifacts:

```text
PWE-StudioSaaS-aws-8.2.1.tar.gz
  sha256 fdeff388c2367ba0a9219cd95cbaeac2635306941f84326040c3b4f4694fbbe3
PWE-Studio-Edition-8.2.1.tar.gz
  sha256 5d97eb8d2796be9a0d8ffa8fbaa7f440256cc50036fe99f838885913e112d4d6
cms-app.js local/live
  sha256 b03371eac4ed321b9bc4a53cf9e97548e337386e18419997c5866fa9190e20f9
```

The deployment controller created fresh logical and media-volume backups at
05:57 UTC before switching from retained v8.2.0 to v8.2.1. HTTP redirects to
HTTPS, TLS verification passes, the public edge returns HTTP/2 200, and the CMS
asset is `no-cache`, so a normal page refresh retrieves the repaired bundle.

# PWE Studio v8.2.0 — Historical release handoff

## Active release — daily roster convergence and lighter product home (2026-08-01)

**Current repository truth:** branch `codex/v8.0.1-aws-production`, version
sources set to **8.2.0**. Application commit
`ccc3b9cba3063d74382b83f6d628c4ad5d2546e0` was packaged and deployed to
Lightsail on 2026-08-01. The active release is
`/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.2.0` and the running image is
`studiosaas:8.2.0`.

The post-v8.1.1 user acceptance screenshots exposed a context bug rather than
an ICS serializer bug: the top button previewed an empty recurring schedule
while the visible Lucas 12:30 row belonged to the selected day's private
roster. v8.2.0 makes those two products explicit:

- **Fixed schedule ICS** stays in the weekly-schedule card, contains no student
  identities and is disabled when there are no fixed classes.
- **Export selected day ICS** stays with the selected roster, appears only when
  the day has effective students, requires `data:export`, warns that it contains
  student names and never includes guardian names.
- Same-time ordinary entries remain one group event; only explicit 1-to-1
  entries split and conflict. A 409 revision mismatch now refreshes inside the
  modal and requires confirmation again without a page-level red toast.
- Tenant-wide `defaultClassTime` is stored in PostgreSQL settings, initially
  **14:30**, editable by Owner/Manager in CMS Settings, and seeds new manual,
  template and fixed-class controls without rewriting existing bookings.
- The selected-day planner uses the 38.2/61.8 date/action hierarchy; batch
  templates start folded, inherited schedule times render correctly, reminders
  include the effective time and mobile has no floating language control over
  roster actions.

The product homepage now follows the same golden hierarchy: Warm Paper owns
61.8% of the desktop hero and Navy is a 38.2% artwork anchor. Owner/industry
cards are light, and the support section limits Navy to the 38.2% copy panel.
Mobile uses a light story followed by a contained Navy artwork panel. Mail and
Messages remain device-native; no acquisition automation was introduced.

Behavioural comparison and retained PWE security advantages are recorded in
`docs/Daily_Roster_ICS_Drift_2026-08-01.md`.

### Current verification evidence

```text
Focused roster/calendar/security tests: 82 passed
Full pytest suite: 302 passed, 2 skipped
Legacy smoke: 73/73
Tenant isolation/privacy: 228/228
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
Desktop roster: 1440px client = 1440px scroll; default 14:30; empty fixed ICS disabled
Mobile roster: 375px client = 375px scroll; templates folded; language overlay absent
Desktop home: CSS hero split resolves to Warm Paper 0–61.8%, Navy from 61.8%
Mobile home: 375px client = 375px scroll; Warm Paper hero; contained Navy artwork panel
Live home: desktop 1440=1440, mobile 375=375, theme #F7F5F2, version 8.2.0
Internal/public deep health: appVersion=8.2.0, db=ok, mode=saas
Public routes: home, product, CMS, Studio Admin, register, FAQ, privacy, terms, support = 200
Unauthenticated tenant-scoped operational-settings write: 401
```

Release artifacts and deployment identity:

```text
PWE-StudioSaaS-aws-8.2.0.tar.gz
  sha256 b8a8b68f99bc99ffa8aabcc7d6ae468f6713834d5e00158f378eb828c3b7fb13
PWE-Studio-Edition-8.2.0.tar.gz
  sha256 beaade6016388c75701eac3fb36de54544266e0ed7045c6a93f0a870172d135d
cms-app.js local/live
  sha256 c732f9a5830b93165d10c0858b8acb36141b66f6b960a066d78cf41e00889caa
cms-i18n.js local/live
  sha256 122bc3580cc3f1c537195ce5ddc41d3ce6fd3776c7c545addab389d38e6ea4c1
```

The deploy controller created fresh pre-mutation logical and media-volume
backups and retained the validated v8.1.1 release for rollback. The daily
same-instance backup cron last completed successfully at 03:15. Off-instance
or local backup remains an explicit future task and is not called disaster
recovery.

The authenticated roster/calendar behaviour is covered by route, permission,
revision, grouping and serializer tests plus local browser acceptance. Live
assets and the tenant-scoped authentication boundary were verified without
using or disclosing a production operator credential. The only delivery item
outside the running service is Git push: the configured remote must be
explicitly confirmed as owner-controlled before the nine local commits are
published.

# PWE Studio v8.1.1 — Deployed production record

## v8.1.1 release acceptance (2026-08-01)

**Historical truth:** repair commit `282e384` was packaged and deployed to
Lightsail. Internal and public deep health reported `appVersion=8.1.1`,
`db=ok`, `mode=saas`; the public CMS asset matched the local SHA-256. The later
v8.2.0 section above supersedes this release for current work.

### Completed in the v8.1.1 candidate

- **ICS end to end:** canonical revision-bound preview/download, deterministic
  filenames, all-day semantics, 409 refresh/reconfirmation, explicit private
  daily-roster warning, `data:export` enforcement and modal keyboard handling.
  Weekly schedule ICS contains no identities; daily roster ICS may contain
  student names and never guardian names.
- **PIN decision:** removed the reversible Base64/localStorage PIN. It was not
  authentication and had an unsafe mobile recovery path. CMS now relies on the
  server session and provides an explicit server logout.
- **One CMS visual system:** all Tailwind colour families resolve by role to
  the tenant's 21 semantic tokens; OS dark preference is only a pre-brand
  fallback. Once `/brand` resolves, `data-brand-scheme` is the sole theme owner.
- **Golden-ratio core:** shared 61.8/38.2 hierarchy and
  `5/8/13/21/34/55/89` spacing remain canonical. Shared interaction tokens now
  include 44px touch targets, 46px controls, 8px gaps and 8/13/21px radii.
- **CMS/mobile accessibility:** 36/40px target classes removed, primary modals
  trap and restore focus, portfolio thumbnails are keyboard actions, image alt
  text is present, and nested portfolio dialogs no longer compete.
- **Registration:** required identity/contact/privacy fields stay visible;
  optional details, message and publication consent use progressive disclosure.
  Mobile gets a compact header, safe-area sticky submit and touch-sized labels.
- **Deployment rollback:** controller captures and validates the previous
  version before mutation, treats internal/public health separately, restores
  both symlink and version, and fails explicitly if rollback restart or health
  verification fails.
- **Legal/support:** public Support Policy added and linked from Terms/FAQ;
  privacy text now distinguishes weekly schedule and daily roster ICS. Internal
  product/legal consistency review is complete in
  `docs/customer/Legal_Review_2026-08-01.md`; Australian lawyer sign-off and the
  listed commercial particulars remain mandatory before first signature.

### Deliberately deferred

- Main-site acquisition automation: unchanged. Actions continue to open the
  user's own Mail or Messages client; no delivery claim is made.
- Off-instance/local backup copy: deferred by owner decision. Lightsail's daily
  same-instance backup and restore evidence remain; do not call that disaster
  recovery.
- MFA, monitoring, backup-failure alerting, on-call ownership and contractual
  SLA remain disclosed live-service gaps.

### Verification completed so far

```text
Focused legal/UI/deployment suite: 124 passed, 1 skipped
Post-document UI contract suite:   91 passed
Legacy smoke:                      73 passed
Tenant isolation/privacy:          225 passed
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh: PASS
```

# PWE Studio v8.1.0 — Deployed production record

Current version: **8.1.0** (`VERSION`, `backend/server.py` `APP_VERSION`,
`deploy/aws/lightsail.env.example`)
Working branch: `codex/v8.0.1-aws-production`
Baseline: tag `v8.0.0`, commit `abc01ce6e4f281056c3c22fa665e42d7811e0688`
Prior release branch: `codex/v8.0.1-product-home-brand-release`
Post-release corrective branch: `codex/super-admin-tunnel-chain-fix`

**Section order is newest first for §10, then the 2026-07-29/30 record in
§0–§9.** §0 is the production truth and stays the first thing an operator reads
after §10.

## 10. Post-launch P0 fixes and the 8.1.0 version bump (2026-07-31)

Everything below shipped after `pwestudio.online` went live (§0). The version
moved 8.0.1 → **8.1.0** because the release now contains a production
deployment, a customer-visible defect fix and a commercial quota change — not a
patch-level correction.

**Read §7.5 with this section.** §7.5 records the v8.1.0 deploy itself and the
two defects that deploy exposed (an image tag naming the wrong version; the
renamed release-notes URL 404ing). This section records the version bump, the
product fixes it carries and the documentation sweep that made the repository's
prose match the deployed reality. §7.5 is the current runtime truth; §0 is the
2026-07-30 measurement it superseded in part.

### 10.1 Version bump — the four files that define it

| File | Change |
|---|---|
| `VERSION` | `8.0.1` → `8.1.0` |
| `backend/server.py` `APP_VERSION` | `8.0.1` → `8.1.0` (this is what deep health reports) |
| `deploy/aws/lightsail.env.example` | `STUDIOSAAS_VERSION=8.1.0` |
| `README.md` | `Current release: **v8.1.0**` |

Version assertions that had to move with it, all now green:
`backend/tests/test_health.py:14`, `backend/tests/test_tunnel_parity.py:14,25,44`,
`backend/tests/test_product_home_brand.py:57`,
`backend/tests/test_standalone_mode.py:113`.

The customer release-evidence pages were renamed with `git mv`, so history
follows:

```
customer-resources/Release_Notes_v8.0.1.html -> Release_Notes_v8.1.0.html
docs/customer/Release_Notes_v8.0.1.md        -> Release_Notes_v8.1.0.md
```

Seven referencing sites were updated: `product-home.html:393`,
`backend/server.py:991` (the served allow-list), `customer-resources/FAQ.html:127`,
`customer-resources/Privacy_Policy.html:190,191,200`,
`customer-resources/Terms_of_Service.html:44,45,153`,
`backend/frontend/assets/customer-resources.css:5`, `docs/customer/README.md:11`,
plus the three test files above and
`backend/tests/test_customer_resources_brand.py:7,60,225`.

§8.1 below still names the old filename. That is deliberate: it is a historical
statement about what the file was called at the time, not a live pointer.

### 10.2 The registration success card was invisible on seven themes

`tenant-template/index.html:270` (and the six generated tenant workspaces) read:

```css
.result-card{ background:var(--ink); color:#EFE9DD; }
```

`--ink` is the tenant theme's `text_color`. Under a light theme-mode that pairs
a fixed cream on a dark surface — 13.69:1, fine. Under the **seven dark
theme-modes `--ink` is itself the light text colour**, so the same fixed cream
sat on a near-identical surface at **1.06:1**. The 56px `✓` measured 1.21:1 and
the "back to home" control at `:543` had the same fault.

This is the confirmation a parent sees immediately after submitting a
registration — the single highest-consequence surface in the funnel, and it was
blank on nearly half the palettes a studio can choose.

Fix: `color:var(--bg)` against `background:var(--ink)`. That exact pair is the
`('body / page', 'text_color', 'background_color', 4.5)` row of `CHECKS` in
`docs/design/palette_gen.py:221`, so the generator already refuses to emit a
theme where it falls below 4.5:1 — the card can no longer fail silently for any
of the 15 theme-modes, including ones added later.

`tenant-template/index.html:263` — the degraded-content band was a fixed
`#FDF3D5` / `#6b4f00` pair, i.e. a light warm strip pinned across the top of
every dark theme. It now carries `brand-status` with `data-tone="warning"` and
takes the theme's own warning semantic (`brand-system.css:98`).
`:447` dropped a hard-coded `#9d9484` eyebrow for `var(--muted)`.

### 10.3 Every studio's CMS looked the same

Two independent causes, both in `legacy-root/index.html`:

1. `:62` mapped **10 of the 21 theme tokens**. `border_strong_color`, the accent
   hover/pressed states, `focus_ring_color`, the disabled pair and `scrim_color`
   were simply not applied, so a studio that picked one of the eight palettes
   got a CMS that was only partly theirs.
2. `:334` was `body { background:#f1f5f9 !important }` — Tailwind slate-100, a
   cold blue-grey that outranked any tenant theme by `!important`.

Both fixed. The map at `:62` is now the same declarative table the registration
page uses at `tenant-template/register.html:365`, covering all 21 fields, and
the body background is `var(--bg, #f1f5f9)` — the old value survives only as a
fallback until `/brand` answers.

### 10.4 Focus and control boundaries on the product gateway

| Surface | Before | After |
|---|---|---|
| `product-home.html:56` focus ring on light surfaces | Family Amber `#F5B335` on Warm Paper — **1.70:1** | accessible amber `--family-amber-text` — **4.52:1** |
| `product-home.html:62` focus ring on navy sections | — | Family Amber retained — **9.70:1** |
| `product-home.html:171` dark-section form border | `rgba(255,255,255,.28)` → composites to `#576173` — **2.51:1** | `.42` — **3.90:1** |

WCAG 1.4.11 asks 3:1 of a non-text indicator, so the old focus ring failed by a
wide margin on exactly the surface a keyboard user needs it.

### 10.5 What the new test file guards

`backend/tests/test_portal_theme_contract.py` — 12 tests, new:

- no colour declaration on a themed surface may name a literal hex, checked
  across `tenant-template/` and every generated workspace (scrim rules are the
  one documented exception);
- the success card must pair `--ink` with `--bg`, not with a chosen colour;
- **the generator still asserts that pair** — if someone deletes the
  `body / page` row from `palette_gen.py` `CHECKS`, the card's guarantee
  evaporates silently, so the test guards the assumption and not only the code;
- the degraded band must use the theme's warning semantic;
- `portal-theme.css` remains the single place fallback literals may live;
- each of portal, registration and CMS must map **every** theme field, and the
  three must agree field for field;
- the CMS base background must follow the tenant theme;
- the second CMS dark system is asserted to still be *recorded as open*, so the
  known gap cannot quietly fade out of the plan document.

### 10.6 Deliberately NOT done in this round

| Item | Where it is tracked |
|---|---|
| Uptime monitoring, backup-failure alerting, on-call ownership, contractual SLA | §0 "Not yet done"; disclosed on the FAQ and release-evidence pages |
| MFA for privileged accounts | §0; disclosed as an open gap **on a live service** |
| Off-instance copy of database and media backups | §0; backups exist and restore, but live on the same instance |
| Managed AWS services (RDS, S3, SES) | §0 |
| CMS's two dark systems not merged | `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` **item 29**, `legacy-root/index.html:151-238` |
| 128 `text-gray-400` occurrences below AA (2.31:1 at worst) | same document **item 8**, `legacy-root/src/cms-app.jsx` |
| 8 Tailwind semantic-colour steps not on the semantic scale | same document **item 7** |

Items 7, 8 and 29 are CMS-internal: they affect staff-facing screens, not the
parent- or student-facing surfaces fixed in §10.2.

Migration 0021 **is** applied to production — §9.2 describes it as pending, but
the v8.1.0 deploy in §7.5 carried it in. The instance reports 21 migrations and
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

## 0. AWS production is LIVE (2026-07-30)

`https://pwestudio.online` serves v8.0.1 from AWS Lightsail. **The Cloudflare
Tunnel is no longer the production path** and must not be reintroduced for this
hostname: the tunnel existed because the runtime had no public IP. With a static
Lightsail IP and Route 53 delegation, a tunnel would add a third-party hop, a
second credential to rotate, and would compete with certbot HTTP-01 for the
same hostname.

| Item | Truth |
|---|---|
| Instance | Lightsail `PWESTUDIO`, Ubuntu 24.04 x86_64, 2 vCPU / 1.9 GB / 58 GB, Sydney Zone A |
| Static IP | `13.237.190.58` |
| DNS | Route 53; `pwestudio.online` and `www.pwestudio.online` both A → the static IP |
| Edge | host nginx terminates TLS; app listens on `127.0.0.1:8899` only; 80 → 443; HSTS `max-age=31536000; includeSubDomains` |
| Certificate | Let's Encrypt, SAN = apex + www, lineage `pwestudio.online`, expires 2026-10-28, `certbot.timer` active |
| Runtime | Compose project `pwestudio`: `studiosaas:8.0.1` (commit `cdd204e`) + `postgres:16-alpine`, both healthy |
| Database | 6 tenants / 15 users / 65 students / 37 registrations / 81 media assets / 4276 audit rows; 20 migrations |
| Least privilege | migrations use the owner role inside entrypoint only; runtime uses `studiosaas_app` |
| Backups | `/etc/cron.d/pwestudio-backup` 03:15 UTC → logical dump + volume tarball; restore rehearsal passes |
| Release layout | `/opt/pwestudio/releases/PWE-StudioSaaS-aws-8.0.1-cdd204e`, `current` symlink, env at `/opt/pwestudio/shared/production.env` (600) |
| Canonical host | `www` 301s to the apex over TLS; one origin, no duplicate content |
| Operator entry | `ssh pwestudio` (see §0.2) and `bash deploy/aws/pwestudio_remote.sh <cmd>` |
| Not yet done | RDS, S3, SES, MFA for privileged accounts, off-box backup copy, uptime monitoring |

**Superseded in part by §7.5.** The version, commit, migration count and release
path in this table are what was measured on 2026-07-30. The v8.1.0 deploy has
since landed: the instance runs `studiosaas:8.1.0`, commit `30da029`+, with 21
migrations applied and the revised plan quotas live. Everything else in this
table — instance, IP, DNS, edge, certificate, least privilege, backups,
canonical host, operator entry and the "not yet done" row — is unchanged and
still current. This section is left as the 2026-07-30 measurement rather than
rewritten, so the two deploys stay separately auditable; §7.5 is the current
runtime truth.

### 0.1 "Not Secure" in Chrome was a client-side cache, not a server fault

Measured from outside on 2026-07-30 after the edge went up:

```
http://pwestudio.online/   -> 301 -> https://pwestudio.online/   (1 redirect)
ssl_verify_result = 0      certificate chain = 4 certs, Verification: OK
homepage absolute http:// references = 0   (CSP is default-src 'self', so
                                            mixed content is structurally
                                            impossible, not merely absent)
```

Chrome had cached the HTTP 200 from before TLS existed and kept loading over
HTTP without re-following the new 301. Visiting `https://` once takes the HSTS
header, after which the browser refuses HTTP for a year. Nothing to fix
server-side. If it recurs on a device: hard-reload, or clear the site's data.

Optional permanent hardening not done: submitting the domain to the HSTS
preload list would make browsers refuse HTTP even before a first visit. It is a
one-way door — the domain must then always serve HTTPS — so it is a decision to
take deliberately, not a side effect of a deployment round.

### 0.2 Operating the instance

Access is an `ssh_config` alias; the key is **not** in the repository or in
iCloud. The private key was moved out of the synced project folder — iCloud
cannot hold mode 600, and a synced private key is a copy you do not control:

```
~/.ssh/pwestudio-lightsail.pem        mode 600   (byte-identical to the
                                                  Lightsail default key)
~/.ssh/config      Host pwestudio -> 13.237.190.58, user ubuntu
```

`deploy/aws/pwestudio_remote.sh` is the laptop-side half. It holds no
credentials and delegates everything that touches production data to
`lightsail_ctl.sh` on the instance, so a laptop is never the source of truth
for a production procedure:

```bash
bash deploy/aws/pwestudio_remote.sh status     # containers + deep health
bash deploy/aws/pwestudio_remote.sh health     # public HTTPS, DNS, cert, redirect
bash deploy/aws/pwestudio_remote.sh backups    # what is on disk, and the cron log
bash deploy/aws/pwestudio_remote.sh backup     # dump + volume tarball, now
bash deploy/aws/pwestudio_remote.sh drill      # rehearse a restore (safe)
bash deploy/aws/pwestudio_remote.sh certs      # expiry + renew timer
bash deploy/aws/pwestudio_remote.sh deploy dist/PWE-StudioSaaS-aws-<ver>.tar.gz
bash deploy/aws/pwestudio_remote.sh ssh
```

`deploy` refuses a `mode=standalone` tarball before uploading it, backs up
first, and **rolls the `current` symlink back automatically if deep health
fails**. Commands that remove a volume, drop a database, or perform a real
restore are deliberately absent — those live on the instance where the operator
reads the confirmation prompt in context.

### 0.3 Edge hardening (2026-07-30, second pass)

- **One shared TLS snippet** (`deploy/aws/nginx/pwestudio-tls.conf`, installed to
  `/etc/nginx/snippets/`) included by both 443 blocks. A hardened apex beside a
  default-configured `www` block is a downgrade path hiding in plain sight.
  TLS 1.2 is limited to forward-secret AEAD suites; no CBC, no RSA key exchange,
  no 3DES. Session cache on, tickets off.
- **OCSP stapling is deliberately OFF.** Every hardening guide says to enable it;
  it is now dead configuration for Let's Encrypt. The certificate's AIA carries
  only `CA Issuers - URI:http://ye1.i.lencr.org/` and no OCSP responder URL, so
  nginx accepts `ssl_stapling on` and then logs `"ssl_stapling" ignored` on
  every reload — a permanent warning that trains an operator to stop reading
  reload output, which is where real errors appear. Re-check after any renewal:
  `openssl s_client ... | openssl x509 -noout -ocsp_uri` should print nothing.
- **No duplicate security headers.** `backend/server.py:777-796` already sends a
  complete CSP, X-Frame-Options, Permissions-Policy, Referrer-Policy and
  X-Content-Type-Options. nginx was repeating two of them. HSTS stays at the
  edge on purpose: it must also cover responses the application never produced,
  and nginx's 502 while the container restarts is exactly when a downgrade must
  not be on offer.
- **Branded maintenance page** for 502/503/504 (`/var/www/pwestudio/__maintenance.html`,
  `internal`, no-store, `Retry-After: 30`). An upgrade restarts the container for
  a few seconds; nginx's stock "502 Bad Gateway" reads like the studio's website
  is broken rather than briefly updating.
- **nginx 1.24 constraint**: HTTP/2 is a `listen` parameter on Ubuntu 24.04. The
  1.25+ `http2 on;` directive fails `nginx -t` — caught by the config test
  before reload, so the live site was never affected.

Nine contract tests in `backend/tests/test_lightsail_deployment.py` hold all of
the above, including that the operator script carries no credentials and cannot
destroy anything.

### Four defects this deployment round found and fixed

All four looked fine from the outside and would have surfaced only during an
incident:

1. **Daily backups had never once succeeded.** `lightsail_ctl.sh` invoked
   `scripts/backup_postgres.py`, but the script is at `backend/scripts/` inside
   the image (WORKDIR `/app`). Nothing read the cron output.
2. **Even with the right path, the dump could not be written.** The bind-mounted
   backup directory was `ubuntu:ubuntu 0755` while the container runs as uid
   10001 → `Permission denied`. Now owner uid 10001, group the operator, mode
   2750, asserted on every run so a human can also list backups without sudo.
3. **The restore rehearsal could never pass.** The image installed an unpinned
   `postgresql-client`, resolving to 17, against a PostgreSQL 16 server; a 17
   `pg_restore` emits `SET transaction_timeout = 0`, a PG17-only GUC, which
   PG16 rejects. The client is now pinned to `postgresql-client-16` from PGDG.
   Dumps produced by the 17 client were deleted — a 16 client cannot read them,
   so keeping them would hand an operator an unusable backup mid-incident.
4. **The media volume was empty.** The database referenced 81 media assets and
   160 derivatives; the volume held only Linux's stock `/media/{cdrom,floppy,usb}`
   from the image layer. Every brand logo returned 404. The 2032-file media tree
   was extracted with uid 10001 ownership, and `backfill_media_variants.py` was
   fixed to verify that a derivative's **file** exists rather than only its row
   — it previously reported "Generated variants: 0" while 126 files were missing.

## 1. Historical delivery boundary (pre-2026-07-30)

v8.0.1 was first shipped as a verified local release and customer-demonstration
package, before the AWS deployment above.

| Area | Truth at the time |
|---|---|
| SaaS runtime | Local Waitress + PostgreSQL behind the controlled `studiosaas-v8-controlled` Cloudflare Tunnel |
| Public product URL | `https://studiosaas.cc.cd` reported v8.0.1 from the same runtime as `http://127.0.0.1:8901` |
| Role entry contract | `/platform-admin` = platform control plane; `/studio-admin` = neutral tenant-admin login; `/cms` = neutral tenant-operations login |
| AWS/RDS/S3/SES | Not purchased or deployed *(Lightsail now deployed; RDS/S3/SES still not)* |
| Production backups/restore/monitoring/SLA | Deferred *(backups + restore rehearsal now live; monitoring/SLA still deferred)* |
| Online payment, provider SMS/email, custom domains | Deferred |
| Multi-campus | One campus = one tenant/subscription; future organisation aggregation is deferred |

Do not describe local testing, a source bundle or Cloudflare invitation access
as production acceptance. Production acceptance is `https://pwestudio.online`
answering deep health with `appVersion=8.0.1`, `mode=saas`, `db=ok` — see §0.

## 2. What v8.0.1 delivers

### P0 — customer-safe demonstration and commercial readiness

- SaaS `/` is a bilingual product gateway with a clear product story, five
  role entrances, sales journey, plans, migration downloads and support CTA.
- v8.0.1 brings that gateway onto the canonical PWE family palette: Family
  Navy `#0E1729`, Family Amber `#F5B335`, accessible amber text `#A16207` and
  Warm Paper `#F7F5F2`. Retired forest, sage and coral values are rejected by
  a dedicated regression test.
- The gateway now follows the approved sales story—administration behind the
  scenes, creativity in front—uses Let’s Paint Studio as the demonstration
  proof, identifies Studio at AUD 99/month as the recommended plan and
  discloses the AUD 299–999 setup range.
- `lets-paint-showcase` is the only professional demonstration tenant. It uses
  fictional people/contact records and synthetic artwork.
- `RESET_DEMO_TENANT.command` and
  `backend/scripts/reset_professional_demo.py`:
  - refuse standalone mode;
  - require the exact phrase `RESET-LETS-PAINT-SHOWCASE`;
  - can only touch the permanently marked `lets-paint-showcase` tenant;
  - keep four staff roles on the configured stable local/Pilot password and
    rotate the separate student code on every reset;
  - write credentials to `.runtime/credentials/showcase-credentials.txt` as
    mode `0600`, never to stdout.
- `docs/customer/` contains a customer-readable delivery index, pricing and
  package boundaries, service agreement draft, onboarding checklist, FAQ,
  migration guide, support policy, integration boundary, multi-campus policy,
  security/privacy/compliance disclosure, demonstration runbook and release
  evidence.
- Security/compliance material explicitly discloses the pre-production state,
  privileged MFA gap, backup gate and incident-response boundary.

### P1 — connected operating experience

- Studio Admin remains the website/brand workspace and CMS remains daily
  operations; both now provide stable reciprocal navigation.
- Onboarding is documented from commercial discovery through tenant creation,
  brand publishing, operational rehearsal, migration and acceptance.
- Reviewed CSV and five-sheet XLSX templates define the supported migration
  shape. Arbitrary historic spreadsheets require assessment and may require
  separately quoted clean-up.
- Family private access shows balance, next class, attendance and portfolio,
  then opens tenant-addressed device Messages/Mail actions for schedule or
  absence enquiries.
- Active recurring schedules download as a tenant-timezone ICS file with stable
  UIDs and weekly recurrence. The export contains no roster/student data.
- Teacher mobile mode prioritises three steps: today's roster, student lookup
  and artwork upload. Non-financial roles see attendance KPIs, not revenue
  labels with zeroed values.
- Product-home Support & Feedback opens the device Mail/Messages application;
  there is no claim of automated delivery, delivery log or retry.

### P2 — sales story and deliberate extension points

- The demonstration runbook follows Let’s Paint Studio from enquiry → trial →
  enrolment → recurring schedule → attendance/credit → artwork → family view →
  owner report.
- Eight industry presets now include three bilingual starter courses,
  registration focus, report focus and a demonstration story in addition to
  industry terminology and visual themes.
- v8.0.1 supports CSV/XLSX export/import templates, ICS and device-native
  messaging. Stripe, Xero, Google/Outlook APIs, provider SMS/email and webhooks
  remain explicit extension points.
- Organisation-level multi-campus aggregation is not modelled prematurely;
  campus tenants remain isolated for permissions, billing and operations.

## 3. Demonstration data evidence

The guarded reset was run twice successfully.

| Tenant | Students | Courses | Packages | Schedules | Memberships | Credit balance |
|---|---:|---:|---:|---:|---:|---:|
| `lets-paint-showcase` | 12 | 3 | 3 | 3 | 4 | 78 |
| `lets-paint-studio` | 43 | 3 | 5 | 0 | 1 | 165 |

`lets-paint-studio` retained its pre-reset counts and balance. The showcase
also contains five enquiry states, three private portfolio works and six
metadata-sanitised display/thumbnail variants.

## 4. Verification evidence

### Repository and database gates

- `backend/tests`: **182 passed, 2 skipped**.
- Legacy CMS smoke: **73 passed, 0 failed**.
- PostgreSQL tenant isolation/privacy/Edition suite: **216 passed, 0 failed**.
- Migration check: current.
- Media derivative check: current.
- Python compile, inline scripts, shared JS, CMS source/build consistency, UI
  escaping, terminology and release/Edition shell syntax: passed.
- `STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`: passed.

### Browser acceptance

Real Chrome, no page errors and no HTTP 5xx:

| Surface | Viewport | Result |
|---|---:|---|
| Product home | 375×812 | no overflow; 44px actions; skip link; language switch; reduced motion; 125% text |
| Product home | 812×375 | no overflow |
| Product home | 768×1024 | no overflow |
| Product home | 1024×768 | no overflow |
| Product home | 1440×900 | no overflow |
| Studio Admin | 1024×900 | 8 industry cards + 8 operational starter-course summaries |
| Owner CMS | 768×1024 | no overflow; authenticated ICS download |
| Teacher CMS | 375×812 | three-step flow; no financial label; no schedule mutation |
| Family private area | 375×812 | balance 8, four attendance rows, one private work, native contact actions |

The post-release tunnel correction was also accepted in the in-app browser
against the public hostname. `/platform-admin` remained on the direct
application login, `/studio-admin` required an explicit slug without browser
storage fallback, `/cms` exposed an explicit tenant selector, and
`/lets-paint-showcase/studio-admin` locked the correct slug. The showcase CMS
rendered the Let's Paint Studio login and no tested page had horizontal
overflow.

Product-home display images are 760×760 WebP with intrinsic dimensions and
total **229,582 bytes** in the browser. Five role entrances render at every
tested viewport; local page load during the acceptance run was approximately
0.56 seconds.

The v8.0.1 product-home pass also verified the computed Navy hero, Warm Paper
canvas, accessible amber text, bilingual sales copy, every visible 44px target,
125% text and reduced-motion behavior. Measured contrast includes 17.90:1 for
white on Navy and 4.52:1 for amber text on Warm Paper.

The ICS response contains three recurring events, `TZID=Australia/Melbourne`,
stable weekly recurrence and no tested student name, mobile or family email.

### Migration artifacts

- `customer-resources/PWE_Studio_Data_Import_Template.csv`
- `customer-resources/PWE_Studio_Data_Import_Template.xlsx`

The XLSX contains Instructions, Students, Courses, Packages and Field Guide
sheets. All five sheets were rendered and visually inspected; ZIP integrity
and spreadsheet error-token scans passed.

## 5. Cloudflare operating truth (LOCAL DEVELOPMENT ONLY as of 2026-07-30)

> **The tunnel is no longer the production path.** `https://pwestudio.online`
> serves production from Lightsail with nginx terminating TLS (§0). Everything
> below now describes the *local* runtime and the `studiosaas.cc.cd` demo
> hostname only. Do not point production DNS at a tunnel, and do not treat
> tunnel parity as production acceptance.
>
> Why no tunnel in production: the tunnel existed because the runtime lived on a
> home Mac with no public IP. A Lightsail static IP plus Route 53 removes that
> constraint, so a tunnel would add a third-party hop and a second credential to
> rotate in front of production, for nothing.


`START_STUDIOSAAS_ONLINE.command` now:

- pins `STUDIOSAAS_MODE=saas`;
- defaults the application runtime to port `8901`;
- reads the expected application version from `VERSION`;
- supports an explicit public base domain;
- resolves environment, logs, CMS data, PID files and Tunnel credentials from
  the project-local, Git-ignored `.runtime/` directory;
- never reads `~/.studiosaas`, `~/.cloudflared` or `/private/tmp` for runtime
  files and never resets application passwords during startup;
- uses the explicit project-local Tunnel credential JSON and configured Tunnel
  name instead of selecting an arbitrary credential;
- waits for local and public health;
- runs `backend/scripts/verify_tunnel_parity.py` against deep health;
- refuses to call the tunnel accepted when version, mode, database or release
  identity differs.

Current observation on 2026-07-29:

- local and public deep health agree on
  `appVersion=8.0.1`, `mode=saas`, `db=ok`;
- DNS for `studiosaas.cc.cd` points to the controlled
  `studiosaas-v8-controlled` tunnel, whose ingress targets
  `http://localhost:8901`;
- the public platform-admin API returned all six local tenants;
- `lets-paint-showcase` owner authentication, tenant API and brand workspace
  all returned the exact showcase tenant;
- `/super-admin` remains a Cloudflare Access-protected compatibility alias;
  `/platform-admin` is the direct application-login route;
- the old tunnel was left intact but is no longer the hostname route, preserving
  rollback without allowing two runtimes to answer the same hostname.
- moving a runtime-complete copy to a path containing spaces and starting from
  that new location passed local health, public health and release parity; the
  15-user password-hash fingerprint was unchanged across restart.

The previous split-brain state is therefore resolved. Do not change the DNS
route back to the historical tunnel or start a second connector with a
different ingress for this hostname.

## 6. Packages and release closure

The clean-commit package gate passed for both delivery modes:

```bash
bash deploy/aws/verify_release_bundles.sh
```

Verified outputs:

- `dist/PWE-StudioSaaS-aws-8.0.1.tar.gz`
- `dist/PWE-Studio-Edition-8.0.1.tar.gz`
- matching `.sha256` sidecars.

The SaaS package includes the product gateway, customer resources,
professional showcase workspace/assets and guarded reset. The Edition package
excludes the showcase workspace and reset command while retaining the shared
runtime and customer/operator documentation. Both archives passed SHA-256,
entrypoint, forbidden-content and `BUILD_INFO` checks. The `.sha256` sidecars
generated from the final tagged commit are the authoritative hashes.

## 7. Operator commands

Production commands are in §0.2. The list below is the **local development**
set; running the tunnel parity check against production is meaningless because
production does not use a tunnel.

```bash
# Local service
bash START_STUDIOSAAS_LOCAL.command

# Guarded professional showcase reset
./RESET_DEMO_TENANT.command

# PostgreSQL-required release gate
STUDIOSAAS_REQUIRE_POSTGRES=1 \
STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
bash backend/scripts/verify_local.sh

# Tunnel split-brain/version parity
.venv/bin/python backend/scripts/verify_tunnel_parity.py \
  --local-base-url http://localhost:8901 \
  --public-base-url https://studiosaas.cc.cd \
  --expected-app-version 8.1.0 \
  --expected-mode saas

# Clean-commit SaaS + Edition bundles
bash deploy/aws/verify_release_bundles.sh
```

Presenter credentials are intentionally excluded from Git, bundles, docs and
this handoff. Read the protected local file only when presenting.

## 7.5 v8.1.0 deployed — and the two defects the deploy itself exposed

`https://pwestudio.online` runs **v8.1.0**, image `studiosaas:8.1.0`,
commit `30da029`+, 21 migrations applied, plan quotas live at
`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`.

Neither defect below was caught by a test. Both were caught by reading the
deploy output and probing the live edge afterwards, which is the argument for
doing that every time rather than trusting a green suite.

### The image tag named the wrong version

`docker-compose.yml` tags `studiosaas:${STUDIOSAAS_VERSION}`, and that variable
lives in `/opt/pwestudio/shared/production.env` — the file that deliberately
survives a release because it holds the secrets. Nothing updated it. Deploying
8.1.0 therefore built:

```
studiosaas:8.0.1     <- the tag
appVersion 8.1.0     <- what is actually inside it
```

Two consequences, both only felt during an incident: `docker images` lies to
whoever is diagnosing, and the tag stops being a rollback point because every
release overwrites the same one.

`pwestudio_remote.sh deploy` now reads the version out of the **bundle's own
BUILD_INFO** — not the laptop's `VERSION` file, which can already be ahead of
what is being deployed — and pins it before the rebuild.

### Renaming the release notes killed its public URL

`/customer-resources/Release_Notes_v8.0.1.html` returned 404 the moment the
file became `v8.1.0`. That URL is in sent mail, in the sales deck footer, and
in whatever a prospect bookmarked.

Any superseded versioned name now 301s to the current one. The pattern is
version-shaped (`Release_Notes_v\d+\.\d+\.\d+\.html`), so the next release
does not need this touched, and the traversal guard still runs first — the
redirect can only ever land on the allow-listed current file.

Verified live:

```
/customer-resources/Release_Notes_v8.0.1.html
  -> 301 https://pwestudio.online/customer-resources/Release_Notes_v8.1.0.html
```

### What v8.1.0 fixed in the product

The release's own reason for existing: **a studio's brand choice did not reach
every surface it was supposed to reach.**

- The CMS mapped 10 of 21 theme fields and forced its own background with
  `!important`. Every studio's CMS looked identical regardless of which of the
  eight palettes they chose. Portal, register and CMS now map the same 21
  fields, and a test asserts the three are equal **field for field** rather
  than each merely complete — so adding a token later fails on the first
  surface to adopt it, which is when drift begins.
- The registration success card paired a fixed `#EFE9DD` against
  `background:var(--ink)`. `--ink` is the tenant's `text_color`, so under the
  seven dark theme-modes it is LIGHT and that text measured **1.06:1** — the
  card a family sees after submitting an enrolment was invisible. It now pairs
  `--ink` with `--bg`, which `palette_gen.py:221` already asserts at 4.5:1 for
  all 15 theme-modes, and a second test guards that assertion itself.
- Focus ring was Family Amber at **1.70:1** on Warm Paper, under the 3:1 that
  WCAG 1.4.11 requires. Swapped to the accessible amber (4.52:1); the five
  navy-backed surfaces keep the bright amber at 9.70:1.

### Still open, deliberately

The CMS carries a second dark system in its `prefers-color-scheme` block that
still uses `!important`. Merging the two is item #29 of
`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`. A partial merge would leave
Tailwind surfaces dark while the page background followed a light tenant theme
— worse than either system alone. `test_portal_theme_contract.py` records the
gap so it cannot fade into the file, and fails when someone finishes it.

Also open from the same plan: items #7 and #8, the ~128 `text-gray-400` uses in
the CMS that measure 2.31–2.54:1. Monitoring, an SLA, privileged-account MFA
and off-box media backup remain absent and remain disclosed as absent.

---

## 7.6 Roster slots, and the CMS colour audit (2026-07-30, after the v8.1.0 deploy)

### Roster slots — migration 0022

The roster answered "who is coming today" but not "when". A studio running a
13:30 group and a 17:00 one-to-one saw one flat list, so the front desk could
not tell whether a student was due now or in four hours, and a one-to-one booked
into an occupied hour surfaced when both families arrived.

`daily_roster_entries` gains `class_time time` (NULLABLE) and
`one_to_one boolean`.

**`class_time` is nullable on purpose.** Every existing row predates the column
and there is no honest value to backfill; inventing 09:00 for 43 imported
students would look like data rather than the absence of it. The UI groups those
rows under 「时间未设置」 and sorts them last, keeping the gap visible.

**`time`, not `timestamptz`.** This is a wall-clock slot in the studio's own
timezone ("the 17:00 class"), not an instant. An instant moves when the offset
changes, which is exactly wrong for a recurring lesson.

Two semantics worth knowing:

- `POST /daily-roster` COALESCEs the slot, so re-adding a student without naming
  a time cannot erase one already set.
- `PATCH /daily-roster/<id>` is the correction path. Moving a student from 10:00
  to 17:00 must not reset their source and status the way re-adding would.

Nine isolation checks cover the round trip, the COALESCE, cross-tenant refusal,
and that `25:00` / `10:75` / `noon` / `10` are rejected while `""` remains a
legitimate way to say the slot is not decided.

The CMS shows a slot panel grouping the day by time, and flags what the flat
list hid: **a one-to-one sharing its slot with anyone else.** Rows carry an
inline time control, so a correction sits next to where the problem is visible.

### The CMS colour audit

`legacy-root/index.html` re-points Tailwind utility colours at the tenant theme.
It covered indigo and purple, shades 50/100/600/700 — correct for the shades
that existed when it was written, and silently rotten as the app grew.

Measured: **cms-app.jsx carries 1,322 colour utilities across 149
family+shade combinations in 12 families.** Two families were covered.

So a studio on the clay palette saw a green 「网站与品牌」 button, a blue
「长期未到访」 panel, green row actions, pink birthday chips, a purple-to-pink
report gradient and a stock-blue language switch. The CMS read as four products
stacked together — and the previous release, which themed the content area, made
it *more* conspicuous rather than less.

All 149 combinations now resolve to the theme, **mapped by role rather than by
hue**:

| Tailwind | Role | Resolves to |
|---|---|---|
| gray / slate / zinc / neutral / stone | structure | `--bg2`, `--line`, `--muted`, `--ink2`, `--ink` by shade band |
| green / emerald / teal / lime | success | `--success` |
| amber / yellow / orange | warning | `--warning` |
| red / rose | danger | `--danger` |
| blue / sky / cyan / pink / fuchsia | informational | `--accent-dark` |
| indigo / violet / purple | primary | `--accent` |

Role, not hue, because the role is what survives a palette change; and because
`palette_gen.py` already solves `--success` / `--warning` / `--danger` against
both page and panel for every theme-mode, routing through them inherits that
contrast instead of re-deriving it by eye. Soft fills use `color-mix` against
`--panel`, so they stay light under a light theme and dark under a dark one
rather than becoming a pale slab on a dark page.

Dark chrome (sidebar, mobile bar, login backdrop) maps to `--ink` with `--bg` as
the foreground — the inversion `palette_gen.py:221` guarantees at 4.5:1 — because
a fixed `text-white` is only readable while the surface stays dark.

`--brand` is now defined as `--accent`: the shared admin language switch reads
it, and with it undefined the switch fell back to stock blue `#3b82f6`.

**The test derives the required list from cms-app.jsx** rather than restating
it, so a newly-used shade fails the build at the moment it is introduced. That
matters more than this audit: the old rules were right when written and rotted
without a single failure.

### Also fixed

`backend/frontend/cms-entry.html` focus ring was `rgba(245,179,53,.55)`, which
composites to **1.40:1** on white — the translucency made it worse than the
solid amber, itself already too light for an indicator that WCAG 1.4.11 requires
at 3:1. Now the accessible amber at 4.92:1.

### Open

- The ICS export is **spec-invalid**: `DTSTART;TZID=Australia/Melbourne` with no
  `VTIMEZONE` component (`grep -c VTIMEZONE` = 0). RFC 5545 §3.6.5 requires the
  referenced timezone to be defined in the same calendar object; `X-WR-TIMEZONE`
  is an Apple extension and does not substitute. Apple leans on local time,
  Google is inconsistent, Outlook may refuse the import — so a class lands at
  the wrong moment in a family's calendar, silently, and `RRULE:FREQ=WEEKLY`
  repeats it weekly. Being fixed in a separate stream together with the download
  dialog and the preview API shape.
- Still not done from `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`: per-day
  counts on the week strip, the inline status menu, the day's roster change log,
  item #29 (merging the two CMS dark systems), items #7/#8 (CMS-internal
  readability).

---

## 7.7 Calendar export: spec-invalid, and downloading as JSON

Two separate defects. Both are fixed; the second is the one the studio actually
hit.

### The file was spec-invalid

`DTSTART;TZID=Australia/Melbourne:...` with **no `VTIMEZONE` component** —
`grep -c VTIMEZONE` returned 0. RFC 5545 §3.6.5 requires the referenced timezone
to be defined in the same calendar object; `X-WR-TIMEZONE` is an Apple extension
and does not substitute. Apple leans on local time, Google is inconsistent,
Outlook may refuse the import — so a class lands at the wrong moment in a
family's calendar, silently, and `RRULE:FREQ=WEEKLY` repeats that weekly.

`VTIMEZONE` is now derived from `zoneinfo`, not hard-coded, so a tenant in
Shanghai or London gets its own rules and abbreviations. Verified by parsing the
output back:

```
8月  DTSTART;TZID=Australia/Melbourne:20260805T160000  AEST +10:00 -> 06:00Z
11月 DTSTART;TZID=Australia/Melbourne:20261104T160000  AEDT +11:00 -> 05:00Z
```

The same "Wednesday 16:00" resolving to different UTC instants either side of
the transition is the proof the TZID is now honoured. Line folding was checked
at 75 **octets** against Chinese course names (3 bytes per character): 0 lines
over.

### The download was JSON

The control was `<a href="…calendar.ics" download>`. A plain navigation carries
no `X-Requested-With` header and is not a fetch, so the authenticated endpoint
answered **401 with a JSON body — and the browser saved that JSON as the
calendar file.** That is the garbled download the studio reported; it had
nothing to do with the ICS format.

Downloading from an authenticated endpoint requires a credentialed fetch and a
blob. The client now also refuses to hand the visitor a `.ics` whose
`Content-Type` is not a calendar, so this exact failure cannot recur silently.

### The dialog

Preview then download, both rendered from the **same `CalendarDocument`** the
`.ics` is serialized from, so the counts on screen cannot disagree with the file
that arrives. Shows event/class/one-to-one counts, each event with duration and
time range, the timezone with its abbreviations read from `zoneinfo`, anything
skipped and why, and Apple/Google import guidance.

Two honesty details: the dialog warns when a file **contains student names**
(it leaves the system and lives in someone's calendar), and it only claims the
file is a snapshot when `subscribable` is actually false.

Four endpoints: preview + `.ics` for the recurring schedule (no student data,
subscribable) and for a dated roster (student names, snapshot).

### The empty calendar and the wrong filename (2026-07-31)

The studio downloaded `~/Downloads/weekly-classes.ics`: 639 bytes, a valid
`VCALENDAR` with a correct `VTIMEZONE` — and **zero `VEVENT`s**. The dialog was
equally blank. Two independent causes, neither of them the ICS format:

1. **Every roster row predates migration 0022's `class_time` column.** The
   roster builder refused to invent a slot (correct — see the migration's own
   reasoning) and *skipped* those rows, so a studio that had not yet set any
   slot exported nothing. They are now exported as **all-day events**
   (`DTSTART;VALUE=DATE` / `DTEND;VALUE=DATE` on the next day, per RFC 5545),
   which asserts "expected today" and nothing about when. `skipped` is now only
   cancellations, reported by name. `test_roster_with_no_slots_set_still_
   exports_every_student` pins the whole path.
2. **The recurring-schedule export was genuinely empty** — Let's Paint Studio
   keeps no `class_schedules` rows, it works from the daily roster. That file
   was truthful; the *dialog* was the defect, saying nothing and still offering
   a download. The download button is now disabled at zero events and the empty
   state names the next action ("在「每周课表」新增班次后，这里就会有内容").

The filename was wrong because the client invented one. The server has always
put the correct name on the `CalendarDocument` (`<slug>-roster-<date>.ics`,
`<slug>-weekly-classes.ics`) and exposes it as `preview.filename`; `downloadIcs`
now uses that, falling back to `Content-Disposition` and only then to a literal.
A roster export saved as `weekly-classes.ics` was the visible symptom.

Skip reasons were also being rendered as raw machine codes (`no-class-time`);
they are now mapped to studio-facing Chinese with the student's name.

### CMS readability pass — the colour map was right, the contrast was not (2026-07-31, v8.1.1)

§7.6 mapped all 1,322 Tailwind colour utilities onto theme tokens by role. That
answered *which token does this colour come from*. It did not answer *can you
still read the text once both ends follow the theme* — a value can be perfectly
on-brand and invisible. Replaying every (text token x background token) pair the
CMS can produce against the 15 theme-modes in `backend/studiosaas/presets.py`
gave **197 failures in 645 pairs**. After this pass: **0 in 660**.

Every number below is the worst case across all 15 theme-modes, computed with
the same WCAG relative-luminance formula as `docs/design/palette_gen.py::ratio`,
and spot-checked against `getComputedStyle` in a real browser on both
`atelier-clay/light` and `arcade-lime/dark` (the model and the browser agree to
within 0.05).

| what | before | after | worst theme-mode |
|---|---:|---:|---|
| body text on a card (`bg-white` + `text-gray-900`) | **1.02** | **13.25** | arcade-lime/dark |
| soft text on a card | 1.40 | 9.67 | arcade-lime/dark |
| muted text on a card | 2.44 | 5.56 | arcade-lime/dark |
| white label on an accent fill | 2.08 | 5.83 | studio-ink/dark |
| label on a disabled primary button | 1.25 | 3.00 | rehearsal-rose/light |
| semantic text on its own soft fill | 3.15 | 5.57 | arcade-lime/dark |
| semantic text on `--bg2` | 2.86 | 5.00 | arcade-lime/dark |
| semantic text on `--panel` | 3.72 | 6.39 | arcade-lime/dark |
| `--muted` on the `bg-gray-200` chip | 4.17 | 4.56 | studio-ink/dark |
| the faintest text tier (`text-gray-300`) | 3.03 | 5.56 | all 15 |
| secondary accent text on `--bg2` | 4.44 | 4.72 | arcade-lime/dark |
| selected profile tab | 1.00 | 5.17 | atelier-clay/light |
| `--ink` on the page under OS dark + a light tenant theme | 1.16 | 14.57 | atelier-clay/light |

Four root causes, three of which are the same bug wearing different clothes —
`[class*="bg-red-50"]` is a substring test, so it also matches `bg-red-500` and
`active:bg-red-50`:

1. **`bg-white` (99 uses) and `text-white` (73) were never re-pointed.** They are
   not `<family>-<shade>` utilities, so the audit regex that produced the §7.6
   map never saw them. Under the eight dark theme-modes a card stayed `#ffffff`
   while its text became `--ink` — near-white on white, **1.02:1**. `bg-white`
   now resolves to `var(--panel)`; `bg-white/NN` is deliberately excluded because
   those sit on a `bg-black` scrim over a photograph.
2. **The `-500` solids were being caught by the `-50` soft fills.** The refund
   button, the low-balance badge and the portfolio delete button rendered as a
   12% tint under a white label. The 500s are now restated after the soft fills
   and each is paired with the on-colour the generator asserts.
3. **A `disabled:` / `active:` / `after:` prefix is invisible to `[class*=]`.**
   `disabled:bg-gray-300` sits on seven primary buttons (create class, join
   today's roster, save, top up) — they wore the disabled chip *at rest* under a
   white label, **1.25:1**. The disabled fill now binds to the real `:disabled`
   pseudo-class with the `--disabled-surface` / `--disabled-text` pair (3.00:1 —
   legible, deliberately under AA so it still *reads* as unavailable, which is
   also why it no longer needs the blanket opacity). A single guard keyed on the
   `:` that only a variant prefix can contain now stands down for `:hover` /
   `:active` / `:disabled` and nowhere else. Only those three prefixes are used
   with `bg-` in the whole file (126 `active:`, 7 `disabled:`, 4 `hover:`), so
   the guard cannot catch a responsive variant.
4. **Two dark systems were both in charge.** The `@media (prefers-color-scheme:
   dark)` block predates the role map and the role map outranks almost all of it
   by source order. *Almost*: `html`/`body`, the row hover and the input
   placeholder had no later counterpart, so under OS dark + a **light** tenant
   theme those three stayed dark while everything else followed the light theme.
   Rather than merge the two systems (plan item #29, still open), the outcome is
   scoped: once `/brand` answers, `data-brand-scheme` is on `<html>` and the
   tenant theme owns those three. Before it answers the OS block still prevents a
   white flash, which is the case it was written for.

**Semantic text now mixes toward an anchor rather than being used raw.**
`palette_gen.py:174` solves `--success`/`--warning`/`--danger` against the
**page** only, and `CHECKS` (`:231-233`) only asserts that. The CMS also puts
that text on `--panel`, on `--bg2` and on the role's own soft fill. The fix is
one ratio that works in both modes: `color-mix(in srgb, var(--ROLE) 61.8%,
var(--text-anchor))`, where `--text-anchor` is `--ink` on content surfaces and
flips to `--bg` inside the inverted chrome (sidebar, mobile top bar, bottom nav)
— declared as an inherited custom property, so a semantic colour dropped into the
sidebar later cannot darken itself into the surface. Measured in-browser on the
`#211B19` chrome: warning 6.16, success 6.06, muted 8.49. **68% is the exact AA
boundary; 61.8% is the golden section and buys 0.5 of margin for six points of
chroma.** The brand accents get the same treatment at a far lighter dose (94%),
enough to clear the single remaining miss without a perceptible hue change.

**The faintest text tier was deleted, not adjusted.** `text-gray-300` was
`color-mix(--muted 70%, --panel)` and measured 3.03:1 on `--panel` in *all 15*
theme-modes — necessarily, because `--muted` is already solved to sit on the AA
floor, so anything fainter is by construction below it. It now collapses into
`--muted`; hierarchy at that level has to come from size and weight.

#### Student profile: five tabs, three actions outside them

Grouped by *the question being answered*, not by field type: **概览** (who do I
call, when were they last here — what the front desk needs in five seconds),
**资料** (is the record correct), **记录** (what happened), **作品集** (what have
they made, and may we publish it), **专区** (can the parent log in — a different
audience). The publication-consent panel lives with the portfolio because consent
only ever means "may this piece go public"; splitting the two is what made the
old single column a wall of unrelated panels.

Three actions stay **outside** the tabs, in a sticky bar below the scroll:
加入今日排课 (performed many times a day), 快速充值 (what you reach for the moment
the balance badge reads low) and 编辑 (a mode switch that has to work from
whichever tab you are on). They used to be the *last* thing in the scroll, below
a portfolio grid and a consent panel. 归档学员 moved to the end of 资料 — a
lifecycle decision taken a few times a year that was sitting one thumb-width
below 生成成长报告. 生成成长报告 moved into 作品集, because it is assembled from
the portfolio.

The tabs implement the full WAI-ARIA tab pattern, not just `role="tab"`: roving
tabindex (exactly one tab stop), Left/Right with wrap, Home/End,
`aria-controls`/`aria-labelledby` both ways, `role="tabpanel"`. Verified by
driving the keyboard in a real browser. Same contract as
`backend/frontend/studio-admin.html`, so the two admin surfaces behave
identically. Targets are 44px and the strip scrolls rather than wrapping — a
wrapped tablist puts two rows of targets under a thumb aiming for one.

The selected-tab indicator is a real child element. Written as
`after:bg-indigo-600` it read to the override layer as `bg-indigo-600` and filled
the **button** with the accent under accent-coloured text: **1.00:1**. This was
caught in the browser, not in the model — the model does not know about variant
prefixes. It is the reason cause 3 above got a general guard rather than a
one-line patch.

#### Golden ratio, concretely

Every number comes from the φ ladder already in `assets/ui-tokens.css`
(5 · 8 · 13 · 21 · 34 · 55 · 89, each step ≈1.618x the last), so the sheet is
measured against the same scale as the dashboard:

- profile sheet width **34rem** (544px), height cap **89dvh**
- panel padding **21px** (`--ui-space-4`), row gap **13px**, action gap **8px**
- action bar columns **1.618fr : 1fr** — the primary action takes the golden
  major share, the secondary the minor; a lone action spans both rather than
  leaving a 38.2% hole
- semantic text mix **61.8% / 38.2%** role-to-anchor (AA boundary is 68%)
- row-hover fill **38.2%** of `--line` into `--panel`
- language switch inset **21px**, label **13px**

#### The two named controls

**中英切换 (bottom-right).** The control named in the brief was
`admin-i18n.js`, which reads `--brand`; the switch the CMS actually shows is
`cms-i18n.js`, and it was **fully hardcoded** — `#fff`, `#e2e8f0`, `#64748b`,
`#4f46e5`. Both are fixed. Every colour is now a token with the pre-theme palette
as fallback: surface `--panel`, hairline `--line` (1.34:1, floor 1.18), resting
label `--muted` on `--panel` **5.56:1** (the hardcoded `#64748b` measured
**3.06:1** once the panel followed a theme), selected label `--on-accent` on
`--accent` **5.83:1** (a fixed `#fff` on a bright dark-theme accent measured
2.08:1). The focus ring moved from `--brand`/`--accent` to **`--focus-ring`** —
`--accent` is solved as a *text* colour against the page, `--focus-ring` is the
one solved to clear 3:1 against every surface it can land on: measured 4.13 on
`--panel`, 3.60 on `--bg`, 3.22 on `--bg2`. Positionally it was sitting **on top
of the mobile bottom nav**; it now docks above it at the same 88px offset
`.toast-bottom` already uses, so the two agree about where the bottom of the page
is. Toasts still cover it briefly (z-index 999 vs 90), which is the correct order.

**左侧「网站与品牌」.** It was `bg-emerald-50/700`. Green was picked when the CMS
had no palette; once every colour maps by role it made an **outbound navigation
link read as a success state**. It and 公开网站 are a *pair of links out of the
CMS*, so the difference between them has to be hierarchy, not hue: editing the
brand is the accented action (`--tenant-primary` + `--on-accent`), viewing the
live site is the quiet read-only peer and keeps the chrome inset that 刷新 / 设置
already use. That contrast survives a palette change; green-vs-blue did not. The
same judgement is applied to the mobile settings sheet, where the list already
reads *filled = do it, soft accent = secondary, neutral = read-only, danger =
destructive* — 网站与品牌 takes the single filled slot.

#### Still open after this pass

- **Plan item #29 — merge the two CMS dark systems.** Scoped, not solved. The
  `@media (prefers-color-scheme: dark)` block still carries ~60 hardcoded hexes
  for Tailwind surfaces. They are now unreachable on a themed page, i.e. dead
  weight that will mislead the next reader. `test_the_second_cms_dark_system_is_
  still_recorded_as_open` still guards it. **Risk: low** (dead code), **cleanup
  cost: a day**, because the whole Tailwind dark table has to be re-derived.
- **Pressed-state feedback is still flattened for ~53 of the 133 `active:bg-*`
  utilities.** The rest state is now correct everywhere, and `active:bg-gray-*`
  and `active:bg-indigo-*` were given explicit pressed fills, but families like
  `active:bg-amber-100` map to the same token as their resting fill, so the press
  is invisible on those. **Risk: low** — a missing affordance, not a contrast
  failure. The global `button:active` transform still fires.
- **The contrast audit is not a test.** The 660-pair sweep was run from a
  scratch script; nothing in `backend/tests/` will fail if someone re-introduces
  a `bg-white` or relaxes a mix ratio. `test_portal_theme_contract.py` still only
  checks that a *mapping exists*, not that it is *readable*. **Risk: medium —
  this is the most likely way the pass regresses.** Porting the sweep into
  `test_portal_theme_contract.py` is the highest-value follow-up.
- **`disabled:opacity-40/50` is still used on ~10 buttons.** Only the
  `disabled:bg-gray-*` path was moved onto the token pair; the opacity-only
  buttons still signal unavailability with transparency, which is the pattern
  `docs/Design_System.md:111-127` rules out. **Risk: low.**
- **Hardcoded hexes remain outside the override layer**: `.sl::-webkit-scrollbar-
  thumb` (`#c7d2fe`), `.pin-dot` / `.pin-input` (`#e5e7eb`, `#6366f1`), and
  `.img-skel`'s shimmer gradient. All are small, none carry text, none were
  measured. **Risk: low, cosmetic.**
- **The edit form inside the profile sheet was not restructured.** It is still
  one long column; only the read view was tabbed. **Risk: none** — it is a form,
  and a form is legitimately linear — but it is now visibly inconsistent with the
  read view beside it.
- **Not verified against a logged-in CMS.** Authenticating was out of scope, so
  the tab structure was verified by mounting the component in the real page and
  driving it, and the colour work by measuring `getComputedStyle` on synthesised
  class combinations. The *assembled* profile sheet with real student data has
  not been seen on screen. **Risk: medium for the tab layout specifically** — the
  contrast numbers do not depend on it, but a layout mistake inside a panel would
  not have been caught.

---

## 8. Customer-facing compliance pages and brand repair (2026-07-30)

### 8.1 What was wrong

The product gateway footer links two pages that the brand migration missed
entirely. `customer-resources/FAQ.html` and `Release_Notes_v8.0.1.html` still
declared the **retired** palette inline — forest `#15312e` on `#f7f3eb`, a sage
`#dce9df` note band, a `#d7a93d` focus ring.

Root cause of the miss: `backend/tests/test_product_home_brand.py:7` only ever
loaded `product-home.html`. Nothing in `customer-resources/` was inside the
regression net, so the two pages kept an obsolete palette without a single test
failing.

The FAQ was also **factually wrong after today's launch**. It answered "Is this
already a production AWS deployment?" with "No. The current service runs locally
… exposed through Cloudflare Tunnel. AWS hosting, production backups, restore
testing … are pending." All of that is stale as of §0.

### 8.2 What changed

- Both pages re-based on the canonical tokens through a shared
  `backend/frontend/assets/customer-resources.{css,js}`, so the next brand
  change touches one file rather than four.
- FAQ and release notes rewritten against the facts in §0. Deliberately **not**
  over-corrected: monitoring, an SLA, privileged-account MFA and off-box media
  backup are still absent and are still disclosed as absent.
- Two new compliance pages, bilingual on the same `data-lang` mechanism as the
  gateway:
  - `customer-resources/Privacy_Policy.html`
  - `customer-resources/Terms_of_Service.html`
- `product-home.html` footer links both; `backend/server.py` allow-lists both.

### 8.3 Legal identity (owner-supplied, 2026-07-30)

```
PWE GROUP PTY LTD
ABN 55 606 664 546        ACN 606 664 546
Caulfield North, Melbourne, Victoria, Australia
lee.liu.melbourne@gmail.com      Privacy contact: Lee L
Governing law: Victoria, Australia
```

The ABN checksum verifies (weighted sum 534, `534 mod 89 = 0`) and the ACN it
implies verifies independently (check digit 6). **Format and checksum only —
registration status was not looked up**, so neither page asserts more than the
identity itself.

### 8.4 Still open before these pages are relied on

| | Item | Note |
|---|---|---|
| 🟠 | Deliverable postal address | Suburb-level only. A privacy policy normally needs an address that can receive a written access/correction request. Nothing was invented. |
| 🟠 | Domain mailbox | `pwestudio.online` has **no MX record** — `info@` cannot receive mail, which is why the owner's Gmail is published instead. Move to `privacy@pwestudio.online` once MX exists. |
| 🔴 | Australian legal review | Two sections carry `Needs legal review` on the page itself: retention of children's teaching records, and how a deletion request interacts with record-keeping duties. The studios teach children; this is not a wording preference. |
| 🟠 | Liability and insurance | `Terms_of_Service.html:126` marks the cap, indirect-loss exclusion and insurance requirements as intentionally unresolved. |

Both pages carry a draft qualifier at the top, matching how
`docs/customer/Service_Agreement_Draft.md` positions itself.

### 8.5 The regression net that was missing

`backend/tests/test_customer_resources_brand.py` (new, 17 tests) now covers
**every** page in `customer-resources/`, not one hand-picked file:

- retired palette values fail the build; canonical tokens must be present
- no page may declare its own palette instead of reading the shared asset
- bilingual `data-lang` coverage, no leftover `{{PLACEHOLDER}}`
- legal entity present on the compliance pages, draft qualifier present
- the privacy policy must cover children and publication consent, must disclose
  the open gaps, and **must not promise a response deadline** while the
  contact channel is a personal mailbox
- the FAQ must state the live deployment, not the retired boundary
- Family Amber `#F5B335` may never be used as text on a light surface — that is
  what the accessible `#A16207` exists for
- the gateway footer must link every page, and `server.py` must allow-list every
  page shipped

Verification: **242 pytest** (was 206) + terminology, escaping and inline-script
checks all green.

### 8.6 UI/UX upgrade plan

`docs/design/UI_UX_Upgrade_Plan_2026-07-30.md` (1,593 lines) — analysis only,
no code changed by it. Highest-priority finding, which is a live defect rather
than a polish item: `tenant-template/index.html:265` `.result-card` hard-codes
`color:#EFE9DD` against `background:var(--ink)`. Under a light theme that is
13.69:1; under a dark theme `--ink` becomes the light text colour and the
registration success card renders at **1.06:1 — invisible**. The 56px check mark
sits at 1.21:1 and the "back to home" control at :538 has the same problem.

---

## 9. Commercial plan quota revision (2026-07-30, owner decision)

Quotas only. **Prices, plan codes, plan names and feature flags are unchanged**
(Starter 49 / Studio 99 / Growth 199 AUD per month; one-off Setup fee AUD
299–999 also unchanged).

| Plan | AUD/month | Students | Team users | Storage | `storage_limit_mb` |
|---|---:|---:|---:|---:|---:|
| Starter | 49 (unchanged) | 100 (unchanged) | 2 → **1** | 5 GB → **2 GB** | 5120 → **2048** |
| Studio | 99 (unchanged) | 500 (unchanged) | 8 → **5** | 30 GB → **10 GB** | 30720 → **10240** |
| Growth | 199 (unchanged) | 1500 → **1000** | **20 (unchanged)** | 100 GB → **50 GB** | 102400 → **51200** |

`growth.user_limit` stays at **20**: the owner revised only Growth's storage
allowance and student ceiling and did not specify a team-account figure, so the
existing value was preserved rather than invented.

### 9.1 Files changed

Database / seeds:

- `backend/db/migrations/0021_plan_quota_revision.sql` — **new**, idempotent
  quota UPDATEs scoped by plan code (the pending production change, see §8.2).
- `backend/db/schema_v1.sql` and `backend/db/migrations/0001_schema_v1.sql` —
  baseline `INSERT INTO plans` seed rows carry the new quotas, so a fresh
  bootstrap is already correct and 0021 is a no-op there. Both stay in sync per
  the migration discipline.
- `backend/scripts/seed_local_test_tenants.py` — the isolation-fixture `studio`
  plan row now seeds `5, 10240`.
- `backend/test_tenant_isolation.py` — the storage-quota check restores
  `studio.storage_limit_mb` to `10240` instead of `30720` after temporarily
  forcing it to 1 MB.

No new tables, so `backend/studiosaas/services/tenant_archive.py`
`SNAPSHOT_TABLES` is **verified unchanged** — `plans` is a platform-global
table and was never a tenant-scoped snapshot member.

Customer-facing surfaces:

- `product-home.html` — the three public pricing cards, both `en` and `zh`
  spans (Starter "1 team user / 1 个团队账号" is singular).
- `docs/customer/Pricing_and_Package_Boundaries.md` — subscription catalogue.
- `docs/StudioSaaS_Blueprint_v2.md` — plan table.
- `docs/sales/PWE_Studio_销售介绍.pptx` (**current deck**, referenced by
  `README.md` and `docs/sales/talk_track.md`) and
  `docs/sales/PWE_StudioSaaS_销售介绍.pptx` (superseded earlier copy still in
  the repo) — slide 11 pricing table only. Both decks were rewritten
  part-by-part so that `ppt/slides/slide11.xml` is the **only** changed entry
  of 97; `scripts/office/validate.py --original` passes and a LibreOffice
  render of slide 11 before/after shows identical layout with no overflow.

Migration-inventory references bumped 0020 → 0021: `docs/Database.md` (with a
new 0021 paragraph), `docs/Architecture.md`, `docs/Development_Roadmap.md`,
`README.md`.

### 9.2 Production change — APPLIED 2026-07-30 (was: SQL only, not applied)

> **Superseded.** This section was written before the v8.1.0 deploy. Migration
> `0021` is now applied in production: 21 migrations recorded, quotas read
> `starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`. The
> procedure below is kept because it documents the two application paths and
> the reasoning; the "not applied" framing no longer describes reality. See
> §7.5 for the deploy that applied it.

`pwestudio.online` still holds the old catalogue. Editing the repository seed
does not touch a running database. Two ways in, neither performed here:

1. **Preferred — normal deploy.** `deploy/aws/entrypoint.sh` runs
   `scripts/run_migrations.py` with the owner role on every container start, so
   0021 applies by itself with the next
   `bash deploy/aws/pwestudio_remote.sh deploy <tarball>` once the bundle
   contains it. `schema_migrations` gains
   `0021_plan_quota_revision.sql` and the instance moves from 20 to 21 applied
   migrations (the §0 table still records the measured 20).
2. **Quota-only, without a redeploy.** Run the migration body by hand as the
   owner role, then insert the ledger row so the next deploy does not re-run it:

```sql
BEGIN;

UPDATE plans SET user_limit = 1, storage_limit_mb = 2048
 WHERE code = 'starter' AND (user_limit <> 1 OR storage_limit_mb <> 2048);

UPDATE plans SET user_limit = 5, storage_limit_mb = 10240
 WHERE code = 'studio' AND (user_limit <> 5 OR storage_limit_mb <> 10240);

UPDATE plans SET student_limit = 1000, storage_limit_mb = 51200
 WHERE code = 'growth' AND (student_limit <> 1000 OR storage_limit_mb <> 51200);

INSERT INTO schema_migrations (version)
VALUES ('0021_plan_quota_revision.sql')
ON CONFLICT DO NOTHING;

COMMIT;
```

Verify afterwards:

```sql
SELECT code, monthly_price_aud, student_limit, user_limit, storage_limit_mb
  FROM plans WHERE code IN ('starter','studio','growth')
 ORDER BY monthly_price_aud;
-- expect: starter 49/100/1/2048, studio 99/500/5/10240, growth 199/1000/20/51200
```

### 9.3 Safety review of the reduction

1. **Over-quota behaviour is refuse-to-add, never delete.** Three enforcement
   points, all admission control on a *new* record:
   `api_v1._student_capacity` + its two call sites (student create, registration
   conversion) return 403 when `current >= student_limit`; the team
   create/reactivate paths return 403 when active non-`parent` memberships
   `>= user_limit`; `services/media._assert_storage_quota` raises
   `MediaQuotaExceededError` before an upload is written. Nothing archives,
   truncates or deletes existing students, members or media, so a tenant found
   above a lowered ceiling keeps all of its data and simply cannot grow until
   the plan is upgraded.
2. **`lets-play-piano` sits exactly at the new Starter ceiling** (1 of 1 team
   accounts). It keeps working; it cannot add a second account. The refusal
   text is explicit rather than a bare 403 body:
   `User limit reached (1). Upgrade the plan before adding another team member.`
   — plan name, the actual number and the required remedy. The student-side
   equivalents read `Student limit reached (N). Ask the StudioSaaS
   administrator to upgrade the plan.` and `… Upgrade the plan before
   converting this registration.`
3. **`isolation-no-portfolio` (price 1) exists in the production `plans`
   table.** It is the `backend/test_tenant_isolation.py` fixture plan
   (`500 / 8 / 1024 MB`, portfolio flag off) that leaked into the production
   database — reported, deliberately **not** deleted and deliberately **not**
   re-quoted by 0021, which is scoped to the three real plan codes. Cleaning it
   up is a separate decision because a tenant row may still reference it.

Known cosmetic non-issue, **not changed**: `super-admin.html
formatStorageMb()` prints one decimal below 10240 MB, so the Starter quota
renders as "2.0 GB" where the pricing page says "2 GB" (previously "5.0 GB"
vs "5 GB" — same pre-existing behaviour, not a regression). The decimal is
load-bearing for *used*-storage display, so the formatter was left alone. The
"Add Plan" form defaults (`149 / 800 / 12 / 51200`) describe a hypothetical new
custom plan, not Starter/Studio/Growth, and were also left alone.
## Appendix — v9.6.0 Studio Admin execution baseline

> 状态：执行基线（先交付 handoff，再进入 P0/P1/P2）；目标版本：`9.6.0`。
> 本 handoff 以当前源码、当前测试与生产状态为准；旧版本记录继续保留在本文档下方。

## 1. 当前事实与范围边界

- 当前源码分支：`codex/v9.3.0-cms-information-architecture`；生产已验证版本：`9.5.0`。
- 当前生产目标：`https://pwestudio.online`，部署方式使用仓库内的
  `deploy/aws/pwestudio_remote.sh` 控制器；发布前后必须分别验证 Source、Package、Production。
- Studio Admin 负责租户品牌、官网内容、报名入口、公开课表、预览、草稿和发布。
- CMS 负责学员、排课、签到、课时、报名审核和日常运营。
- 家长话术本轮**不迁移数据、不新建发送系统**：仍留在 Studio Admin，编辑入口移动到
  「招生入口」子菜单；实际复制和使用场景继续由 CMS 消费。
- 支付、银行转账信息、Gmail/SMTP、AWS SES、短信、SSE、WebSocket、浏览器 Push 均不在本版本。

## 2. 目标信息架构

Studio Admin 顶部只保留租户身份、查看官网、打开 CMS、语言和账户；工作台内部改为分组导航：

```text
品牌与官网
├── 品牌基础
├── 首屏与行动按钮
├── 官网版块
├── 工作室作品
└── 常见问答

招生入口
├── 报名表
├── 公开课表
└── 家长话术

发布中心
├── 草稿预览与发布
├── 历史版本
└── 页面健康

经营洞察
└── 官网数据分析
```

- 内部面板继续使用稳定的 `data-workbench-tab` 标识；新入口必须支持 URL deep link。
- 桌面保留编辑区与预览区约 `1.618:1` 的黄金分割；移动端转为单列，不依赖横向滚动标签。
- 家长话术仍进入现有 `messageTemplates` 载荷，保持旧租户数据兼容；本轮只做导航归类、说明和使用边界。

## 3. 执行队列

### P0：功能可信度

1. 补齐所有公开字段、课表开关、时区和家长话术输入的 dirty tracking，确保离开页面保护真实有效。
2. 修复顶部 Quick Registration 入口，使其能够打开隐藏的报名面板并保留当前草稿状态。
3. 为 Timetable 及相关字段补齐中英文映射，禁止中文界面残留英文主标签。
4. 修复 sticky 保存条的底部安全空间和遮挡关系。
5. 统一 workbench tab 的 URL 参数、浏览器前进/后退与首次载入行为。

### P1：信息架构与发布中心

1. 用分组侧栏替换十个平铺标签，家长话术放到「招生入口」子菜单。
2. 顶部低频操作收进账户菜单，减少跨层级重复入口。
3. 预览明确标注为草稿预览；“打开官网”明确表示已发布页面。
4. 发布中心展示「已发布 / 有未保存修改 / 草稿未发布 / 发布失败」四种状态。
5. 页面健康、历史版本和发布动作保持 Owner-only 权限边界。

### P2：交接质量与回归

1. 更新 Studio Admin、Owner、手册总览和 Release Notes 的当前版本说明。
2. 建立中英文、桌面/移动、键盘、脏状态、deep link、权限和租户隔离验收矩阵。
3. 构建生成资产，执行 PostgreSQL 完整门禁、浏览器验收、双模式打包和 checksum。
4. 只提交本版本相关的 tracked 文件；保留现有未跟踪的 `docs/sales/` 路演资料，不纳入提交与发布包。

## 4. 验收定义

- 任何可编辑字段改变后，状态都显示「有未保存修改」，刷新/离开会提示，保存后恢复干净。
- `?view=register`、`?view=messages`、`?view=advanced` 等关键入口可直接打开对应面板。
- 中文界面不会把 `Timetable` 作为主标签显示；英文界面仍保留自然英文。
- 桌面导航不再平铺十项；移动端无主内容横向滚动，主要按钮和输入框至少 44px。
- 家长话术仍可读取旧数据、恢复默认并进入现有发布载荷；没有第二个编辑器或新的发送服务。
- 草稿、预览、已发布官网三者在文案上不混淆；发布失败有明确恢复路径。
- 本地、包内和生产的 `APP_VERSION` / `BUILD_INFO` / deep health 均为 `9.6.0`。

## 5. 不在本轮解决的问题

- 家长话术独立迁移到 CMS、独立 API、Manager 自定义权限。
- 邮件、短信、Gmail/SMTP、AWS SES、在线支付和银行转账。
- SSE、WebSocket、浏览器 Push 或外部通知服务。
