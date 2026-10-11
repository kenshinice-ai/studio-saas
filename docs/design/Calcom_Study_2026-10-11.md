# Cal.com 研究 · PWE Studio 该学什么、不该碰什么

> 考察日期 2026-10-11，对照 PWE Studio v10.20.10（`7bdf353`，schema 到 `0047`）。
> 读的是源码，不是宣传页：`calcom/cal.com` 当前 HEAD `54343aa`（2026-09-20），
> 以及拆分前的标签 `v6.2.0`（`1c193cc`，2026-03-01），只用来看已经被删掉的功能。
> cal.com 官网、定价页、博客从本环境打不开。凡是只从搜索摘要读到的，都标了「未核实」。
> 本文没有改任何代码。

---

## 一句话结论

**不要接 Cal.com 这个服务，也不要搬它的代码；要搬的是它的几个「机制」。**

PWE Studio 最缺的不是排课引擎，而是「让家长不用打电话」的那一圈：
占位、提醒、自助请假。这三件 Cal.com 都有成熟做法，而且都能落在我们已有的表上。
可用时段计算（slot engine）是 Cal.com 的核心，但对 PWE Studio 是第二梯队——
路线图明确写着「Complex scheduling system」现阶段不做。

动手之前，**先修自己的日历订阅源**：读代码发现它很可能一直返回 404，
而且日期会错一天（见第二节 P0）。

---

# 零 · calcom 现在是什么

| 事实 | 依据 |
|---|---|
| 2026-04 起，Cal.com 的生产代码**闭源**。公开仓库改名 **Cal.diy**，MIT 许可，README 写明「仅建议个人、非生产使用」，没有托管版 | 仓库根 `LICENSE`、`README.md`；博客「Cal.com is going closed source」（未核实：官网打不开，只读到搜索摘要） |
| 拆分前是 AGPLv3 + `ee/` 目录的商业许可（Open Core） | `v6.2.0:LICENSE`、`v6.2.0:packages/features/ee/LICENSE` |
| Cal.diy 删掉了 Workflows（提醒）、Routing Forms、SSO、Insights | 迁移 `20260305043434_remove_routing_forms`、`20260319000000_drop_workflow_tables` |
| 引擎还在，且是 MIT：可用时段、缓冲、限额、请假、节假日、座位、轮转分配、预约生命周期、webhook、tasker、Stripe 支付、嵌入 | 当前 HEAD 的 `packages/features/*`、`packages/embeds/*` |
| 「Platform」（给别的 SaaS 嵌预约用的托管用户 + React atoms）**2025-12-15 起不接受新的接入方**；atoms 进入维护模式 | API v2 文档摘要（未核实，同上） |
| 托管版价格：Teams 约 $12–16/人/月 | 第三方汇总（未核实） |

### 许可：什么能拿

| 来源 | 许可 | 对我们意味着什么 |
|---|---|---|
| Cal.diy 当前 HEAD 的全部目录 | MIT | 可以移植，保留版权与许可声明即可 |
| 拆分前标签的非 `ee/` 代码 | AGPLv3 | **不拿**。网络提供服务即触发开源义务 |
| 拆分前标签的 `ee/`（Workflows、managed event types、orgs、SSO） | Cal.com 商业许可 | **不拿，只读概念** |
| 「Cal.com」「Cal.diy」名称与 logo | 不在 MIT 内 | 界面里不出现 |

另一个风险：没找到 CLA，外部贡献从 AGPL 改成 MIT 的权属不完全清楚（推断，不是法律意见）。
我们是 Python + 原生 HTML，本来就要重写。**建议一律按概念重写，不逐行翻译**；
唯一值得「移植」的是它的测试用例——拿来当我们实现的对照答案。

---

# 一 · 对照：Cal.com 有的，PWE Studio 现在怎样

| Cal.com 能力 | PWE Studio 现状（2026-10-11 读代码） | 结论 |
|---|---|---|
| 公开预约页 | **有**：`/v1/public/<slug>/timetable` + `/timetable/book`，申请制，前台审批 | 保留申请制 |
| 选中时段即占位（`SelectedSlots`，默认 5 分钟） | **没有**：pending 不占座，审批时才复核容量 | **做**（第二节 1） |
| 提醒工作流（触发 + 提前量 + 渠道 + 模板变量） | 路由、配额、退订表都有（`0038`）；`dispatch()` **没有调用方**；SMS 适配器一律抛错；没有调度器 | **做**（第二节 2、3） |
| 客人凭链接自助取消/改期 | **没有**（「家长要改，打电话」，`Public_Timetable_And_Booking.md` §3.6） | **做**（第二节 4） |
| 座位制（一场多人，每人一张凭证） | 班次有 `capacity`；每个申请没有自己的管理凭证 | 随第二节 4 一起做 |
| 每周规则 + 日期覆盖 + 请假 → 可用时段 | `teacher_availability` 表存在，**无任何代码使用**；没有时段计算 | 第二梯队（第二节 6） |
| 缓冲、最短提前量、每日/周/月预约上限 | 私教系列只有老师撞时检查（`OVERLAPS`） | 随第二节 6 |
| 轮转分配（round-robin）、集体预约 | 不需要：老师是固定的 | 不做 |
| 循环预约 | **有**，且比 Cal.com 严：`lesson_series` + 例外 + 补课券 + 学期停课 | 我们更好 |
| ICS 订阅 | **有代码**，但只有 API、没界面，且有缺陷（见 P0） | **先修** |
| Google / Outlook 双向同步 | 没有 | 第三梯队 |
| 出站 webhook（HMAC 签名） | 没有 | 第三梯队 |
| 嵌入挂件（iframe + postMessage） | 没有；全站 `frame-ancestors 'none'` + `X-Frame-Options: DENY` | 第三梯队 |
| 定金、留卡、爽约费 | 只有记账表和 Stripe 签名校验函数，没有收款路由 | 不在本轮；设计原则「租户自己的商户号」不变 |
| 黑名单 / 举报 / 对垃圾预约假装成功 | 只有限流 + 反枚举 | 小件，可随第二节 1 |
| 预约审计（不挂外键的审计行） | 有通用 `audit_logs` | 可借鉴字段设计 |

---

# 二 · 建议做的，按顺序

## P0 · 先修日历订阅源（不是 Cal.com 的东西，但挡在所有日历功能前面）

读 `backend/studiosaas/services/calendar_subscriptions.py` 发现三处问题。**都是读代码得出的，没有在运行时复现。**

1. **很可能永远 404。** `resolve()` 在没有绑定租户的连接上按 token 查 `calendar_subscriptions`。
   这张表在 `0042` 里是 `FORCE ROW LEVEL SECURITY`，且不在 `EXEMPT` 名单里。
   以 `studiosaas_app` 角色运行时，查询应当返回零行。Xero 回调遇到过同样的问题，
   解法是 `0045` 给 `xero_oauth_states` 一条 `USING (true)` 策略。
2. **日期很可能错一天。** `build_document()` 第 211 行用 Python `date.weekday()`（周一 = 0），
   注释说「schema 也是周一 = 0」。但 `services/scheduling.py` 第 373 行写明
   `lesson_series.weekday` 跟 JS `getDay()`，**周日 = 0**。
3. **补课不出现在订阅里。** `kind='makeup'` 的例外从不生成事件。

没有测试真正请求过 `/v1/public/calendar/<token>.ics`，所以三处都没被发现。
修法：给 token 查找一条只读的窄策略（或一个 `SECURITY DEFINER` 函数只返回 `tenant_id`，再 `bind_tenant_session()`），
统一周日 = 0，补上 makeup，再加一条在受限角色下跑的端到端测试。

> 同样的代码在 pwe-clinic 里也有（fork 于 v10.20.1，已确认第 211 行相同）。

## 1 · 公开预约「限时占位」

**来源：** Cal.com `SelectedSlots` + `reserveSlot.handler.ts`；我们自己的
`Competitor_MyMusicStaff.md` #12「建议限时占位（如 48 小时自动释放）」与「如果只做三件」#3。

Cal.com 的做法是：访客点了时段，就写一行 5 分钟的占位（`releaseAt`），
用浏览器 cookie 里的 `uid` 认人；别人查时段时把这些行当作已占。
提交时再查一次，最后靠唯一键兜底，冲突返回 409。

**我们的版本不一样，因为我们是申请制、班次有容量：**

- 在 `class_bookings` 加 `hold_expires_at`。pending 申请占一个座位，到期自动释放。
  时长由租户设置（建议默认 48 小时，和对比文档一致）。
- `seatsLeft` 改为：容量 − 已报名 − 已批准 − **未过期的 pending**。
- 容量 > 1，不能用 `EXCLUDE` 约束。并发安全靠写入前锁住班次那一行（`SELECT … FOR UPDATE`），在同一事务里数座位。
- 过期释放不需要定时任务：读取时按 `hold_expires_at > now()` 过滤即可。定时任务只负责通知前台「某申请已过期」。
- 被拒、过期的申请仍然留在表里，状态改 `expired`，不删。

**顺带借鉴的反滥用做法（小）：**
- 租户级黑名单（电话 / 邮箱 → 举报或拦截）。参考 `packages/features/watchlist/`。
- 被拦截的人仍然看到「已提交」，不提示被拦。参考 Cal.com 的 decoy success。
  这和我们现在「无论电话是否匹配学员都返回同样内容」的反枚举原则一致。

## 2 · 一张通用的任务表（tasker）

**来源：** `packages/features/tasker/`：Postgres `Task` 表，`type` + `payload` + `scheduledAt` + `attempts/maxAttempts` + `referenceUid`，
`@@unique([referenceUid, type])` 让任务可以按业务引用去重和取消（`cancelWithReference`）。每分钟一个 cron 取一批执行。

**为什么要：** 提醒、占位过期通知、将来的 webhook 投递，都需要「某个时间点做某件事，可取消，可重试」。
我们已经有一个能用的样板：`integration_sync_jobs` + `next_attempt_at` 退避 + systemd 定时器（Xero）。
把它泛化成一张 `scheduled_tasks` 表，比每个功能各写一个 worker 好。

**比 Cal.com 做得更好的两点：**
- 取批次用 `FOR UPDATE SKIP LOCKED`。Cal.com 的 `getNextBatch` 是普通 `findMany`，两个 cron 重叠时会重复执行（推断，读代码所得）。
- 失败按指数退避，不是固定间隔。

**和现有约束的冲突：** `docs/Architecture.md` §7.4 写「Scheduler — Do not introduce during pilot」。
这里说的是一张表 + 一个 systemd 定时器，不是 Redis / Celery，但仍然**要 Lee 拍板**。
另外，Xero 定时器在 Oracle 主机上是否已重装，交接里没有记录（未核实）。

新表照例要：强制 RLS（或在 `EXEMPT` 写明理由）；登记 `tenant_archive.SNAPSHOT_TABLES`；对齐 Edition `IMPORT_ORDER`。

## 3 · 提醒

**来源：** 拆分前的 `ee/workflows`（**商业许可，只读概念**）。

值得学的概念：
- **一条提醒 = 触发点 + 提前量 + 渠道 + 模板。** 触发点：课前、课后、新预约、取消、改期、申请被批。
- **模板变量**：`{EVENT_DATE} {EVENT_TIME} {TIMEZONE} {CANCEL_URL} {RESCHEDULE_URL} …`，变量名本身也做多语言。
- **改期 = 取消旧提醒 + 为新时间重建。** Cal.com 靠 `referenceUid` 精确取消，不扫表。
- **两段式短信调度**：2 小时以内的交给服务商定时发送，更远的先存表、由 cron 在临近时交出去。
- **退订**（STOP 回复）有自己的表。我们已有 `notification_optouts`。

**落到我们这里：**
- 接上已有的 `notification_routes` / `notification_logs` / `email_templates`，让 `dispatch()` 第一次有调用方。
- **先只做邮件。** SMS 适配器现在一律抛错，是有意为之（「租户自己的短信账户，不转售」）。SMS 等租户自备服务商时再开。
- 把 `DEFAULT_ROUTES` 里 `lesson_reminder → none` 的理由（「订阅源会提醒」）重新审视：
  P0 修好之前，订阅源实际上提醒不了任何人。
- 第一批事件：课程取消（`lesson_cancelled`）、申请已批准（目前批准后家长收不到任何消息）、课前 24 小时提醒。
- 时间计算用 `tenants.timezone`，不用主机时钟。`api_v1/scheduling.py:1811` 的 `hours_of_notice()` 现在默认用 `datetime.now()`，在 UTC 主机上可能算错（未核实）。

## 4 · 家长凭链接自助请假 / 取消

**来源：** `apps/web/app/api/cancel/route.ts`、`handleCancelBooking.ts`；我们的对比文档 #17。

Cal.com 的做法：
- 每个预约有一个**高熵 uid**，它本身就是取消/改期链接的凭证。代码注释明说不用自增 id，因为可猜。
- 取消接口要 CSRF token，并按用户或哈希后的 IP 限流（每分钟 10 次）。
- 规则由事件类型决定：`disableCancelling`、`minimumRescheduleNotice`、是否必须填原因。
- 座位制下，每个参加者有自己的 `seatReferenceUid`，只取消自己那一座。

**落到我们这里：**
- 私教：链接打开后显示这一次课；提交请假时走已有的 `resolve_absence()`，
  按 `scheduling_policies.notice_hours` 决定是否发补课券、是否收费。规则已经写好，只差一个入口。
- 班课：每个 `class_bookings` / 名单行发一个只管自己的凭证。
- 凭证只存哈希（和 `calendar_subscriptions` 一样），可吊销，有有效期。
- 查找凭证同样会撞上 P0 的 RLS 问题，要用同一个解法。
- 截止时间之后，链接只显示「请联系 %VENUE%」，不提供按钮。

## 5 · 工程做法（几乎零成本）

| Cal.com 的做法 | 文件 | 我们怎么用 |
|---|---|---|
| `specs/<功能>/` 每个功能一个目录：`design.md`、`implementation.md`（带日期的进展）、`decisions.md`（ADR 格式）、`future-work.md` | `SPEC-WORKFLOW.md`、`specs/_templates` | `docs/design/` 已经很接近；可以统一加一份 `decisions.md` 记录取舍 |
| 权限迁移对照表：每个旧角色判断 → `resource.action` 权限串，附文件和行号 | `PERMISSIONS.md` | `ROLE_PERMISSIONS` 已是权限串；一张「接口 → 权限」表能让审计更快 |
| 禁止 where 为空的批量更新/删除 | `packages/prisma/extensions/disallow-undefined-delete-update-many.ts` | 我们没有 ORM，可以在测试里扫 SQL：`UPDATE`/`DELETE` 必须带 `tenant_id` 条件 |
| 一条规则一张卡，带影响等级 | `agents/rules/*.md` | AGENTS.md 已经很长；可以拆出单题规则卡 |
| 声明式预约场景夹具 | `packages/testing/src/lib/bookingScenario/` | 做第二节 6 时照着建 |

## 6 · 第二梯队：老师可用时间 + 试听自助选时段

**只有在 Lee 决定开放「试听自助选时段」时才做。** 路线图 §9 和 Blueprint §2.2 都把复杂排课列为现阶段不做。

如果要做，Cal.com 的管线是最值得学的部分（全部 MIT）：

1. **选日程**：事件自己的日程 → 用户默认日程。时区跟日程走。
2. **建时间段**（`packages/features/schedules/lib/date-ranges.ts` 的 `buildDateRanges`）：
   - 每周规则按日程时区逐日展开，处理夏令时。
   - **某天有日期覆盖，就整天替换每周规则**；覆盖为零长度表示「这天不开」。
   - 请假、节假日同样按天整体清空。
3. **扣忙碌时间**：已有预约向两侧扩展缓冲——旧预约的「前缓冲 + 新事件的后缓冲」、「后缓冲 + 新事件的前缓冲」。
   达到每日/周/月上限的整个周期也当作忙碌。然后用一次排序扫描 `subtract()`。
4. **切时段**（`slots.ts`）：步长 = `slotInterval` 或时长；起点 = max(时间段开始, 现在 + 最短提前量)；
   起点对齐到能整除步长的 60/30/20/15/10/5 分钟。
5. **多人**：固定参与者取交集，轮转参与者取并集。

我们的对应：`teacher_availability`（已有表）+ `term_closures`（节假日）+ `lesson_series` 展开结果（忙碌）。
时间一律在 `zoneinfo` 下按租户时区计算，覆盖存「本地日期 + 本地时间」。
Cal.com 的代码注释承认它在覆盖上有时区补丁（「As of 2024-02-20, there are mismatches…」），我们从第一天避开。

估算：核心约 300–400 行 Python，测试比代码多。把 `date-ranges.test.ts`、`slots` 测试、`getAggregatedAvailability.test.ts` 的用例翻成 pytest，当对照答案。

## 7 · 第三梯队：等有真实需求再说

| 功能 | Cal.com 做法 | 我们的障碍 |
|---|---|---|
| Google / Outlook 同步 | 选定日历表 + watch 通道 + 续订 cron + sync token 镜像表；查忙碌优先读镜像，否则实时查 | Edition 的 OAuth 回调固定在 `pwestudio.online`，和 Xero 一样会 404；需要先解决 Edition 回调 |
| 出站 webhook | `X-Cal-Signature-256` = HMAC-SHA256(body)；版本头；SSRF 防护；经 tasker 投递重试 | 签名里**加时间戳**防重放（Cal.com 没加）；依赖第二节 2 |
| 嵌入挂件 | 一个小 loader + iframe + 带命名空间的 postMessage；主题用 CSS 变量传入 | 全站 `frame-ancestors 'none'`。要给 `/embed/*` 单独放开，并按租户登记允许的来源域名 |
| 在线定金 / 爽约费 | Stripe Connect；`HOLD` = SetupIntent 留卡，事后 off_session 扣款；退款策略 NEVER/ALWAYS/DAYS | 设计原则是租户自己的商户号 + 托管页面，平台不做收单方；目前没有任何收款路由 |

---

# 三 · 不建议做的

| 选项 | 为什么不 |
|---|---|
| 把托管版 Cal.com 接成排课核心 | 每位老师要一个 Cal.com 账号和席位；租户数据出了我们的 RLS 边界；没有课时、补课券、学期概念；Platform 不接受新的接入方，atoms 只给 React |
| 自部署 Cal.diy | README 自己写「非生产」；Node/Next/Prisma 栈和我们完全不同；没有团队和提醒 |
| Routing forms（按表单答案分流） | 已被删除；旧代码 AGPL；报名流程目前不需要分流 |
| 轮转 / 集体分配 | 老师固定，没有「任意一位老师」的场景 |
| Managed event types（总部模板下发） | 是商业许可功能；PWE Studio 没有连锁租户 |
| AI 电话提醒、WhatsApp 模板 | 远超当前阶段 |

**Cal.com 不如我们的地方，别学反了：**
- **租户隔离靠应用层**：迁移里没有一条 `CREATE POLICY`。我们的强制 RLS 更强。
- **防重复预约只防「完全相同的起止时间 + 同一主持人」**：唯一键是 `uuidv5(start.end.userId)`。
  时间部分重叠的并发请求，只靠提交前的复查。
- **凭证用 AES-256-CBC，没有 MAC**（`packages/lib/crypto.ts`）。我们的 Xero token 用 Fernet（带认证），保持。
- **循环预约只检查第一次是否有空**（`numSlotsToCheckForAvailability = 1`）。我们的 `create_series()` 应继续逐次检查。

---

# 四 · 新功能会撞上的现有约束

| 约束 | 出处 | 影响 |
|---|---|---|
| 「Complex scheduling」现阶段不做 | `Development_Roadmap.md` §9 | 第二节 6 需要 Lee 决定 |
| 试点期不引入调度器 | `Architecture.md` §7.4 | 第二节 2 需要 Lee 决定 |
| 凭 token 的公开查找都会撞 RLS | `0042`、`test_tenant_isolation_by_construction.py::EXEMPT` | P0、第二节 1、4 共用一个解法 |
| Edition 的 OAuth 回调固定 | `server.py` `/xero/callback` | Google/Outlook 同步要先解决 |
| 全站禁止被嵌入 | `server.py:907-913` | 嵌入挂件要单独路由 |
| 平台不做收单方 | 支付设计 | 定金必须走租户自己的商户号 |
| 界面新词先进术语表 | `docs/Glossary.md`、`check_terminology.py` | 「占位」「请假链接」「提醒」等要先定词 |
| 每张新租户表：RLS、归档清单、Edition 导入顺序 | `test_health.py` 等 | 每个新表都要过 |
| 发布走九步，第 4 步本地检查全绿 | `docs/Release_Runbook.md` | 照常 |

---

# 五 · 建议顺序与待 Lee 决定的事

| 顺序 | 内容 | 依赖 | 粗估 |
|---|---|---|---|
| 1 | P0 修订阅源 + 受限角色下的端到端测试 | 无 | 1–2 天 |
| 2 | 限时占位 + 黑名单 | 无 | 3–5 天 |
| 3 | 任务表 + 定时器 | **Lee：是否允许** | 2–3 天 |
| 4 | 邮件提醒（取消、批准、课前） | 3 | 1 周 |
| 5 | 自助请假链接 | 1 的 RLS 解法 | 1 周 |
| 6 | 老师可用时间 + 试听自助选时段 | **Lee：是否开放** | 2–3 周 |
| 7 | 日历同步 / webhook / 嵌入 / 在线定金 | 有租户提出 | — |

粗估是推断，没有拆任务验证。

**待 Lee 决定：**
1. 是否允许一张通用任务表 + systemd 定时器（突破 §7.4「试点期不引入调度器」的字面）。
2. pending 申请占座多久（建议 48 小时），满座时是否接受候补申请。
3. 是否开放家长自助请假；截止时间是否直接沿用 `scheduling_policies.notice_hours`。
4. 是否开放试听自助选时段（决定第二节 6 做不做）。

---

# 附录 A · Cal.com 关键文件索引

路径相对 `calcom/cal.com`（HEAD `54343aa`）。

| 主题 | 文件 |
|---|---|
| 数据模型 | `packages/prisma/schema.prisma` |
| 时段入口 | `packages/trpc/server/routers/viewer/slots/util.ts`（`_getAvailableSlots`） |
| 单人可用时间 | `packages/features/availability/lib/getUserAvailability.ts` |
| 时间段构建、相减 | `packages/features/schedules/lib/date-ranges.ts` |
| 切时段 | `packages/features/schedules/lib/slots.ts` |
| 多人聚合 | `packages/features/availability/lib/getAggregatedAvailability/` |
| 忙碌时间与缓冲 | `packages/features/busyTimes/services/getBusyTimes.ts` |
| 预约上限 | `packages/features/busyTimes/lib/getBusyTimesFromLimits.ts` |
| 预约窗口 | `packages/lib/isOutOfBounds.tsx` |
| 占位 | `packages/trpc/server/routers/viewer/slots/reserveSlot.handler.ts`；`MINUTES_TO_BOOK` 在 `packages/lib/constants.ts:137` |
| 防重复键 | `packages/prisma/extensions/booking-idempotency-key.ts` |
| 建预约 | `packages/features/bookings/lib/service/RegularBookingService.ts` |
| 取消 | `apps/web/app/api/cancel/route.ts`、`handleCancelBooking.ts` |
| 轮转分配 | `packages/features/bookings/lib/getLuckyUser.ts` |
| 任务表 | `packages/features/tasker/` |
| webhook 签名 | `packages/features/webhooks/lib/sendPayload.ts` |
| 嵌入 | `packages/embeds/embed-snippet`、`embed-core` |
| 黑名单 | `packages/features/watchlist/` |
| 提醒（已删，商业许可） | `v6.2.0:packages/features/ee/workflows/` |

# 附录 B · 未核实事项

- 闭源的日期与原因：只读到搜索摘要和二手报道，cal.com 博客打不开。
- 托管版价格、API 是否随付费档开放：只有第三方汇总。
- P0 三处缺陷：读代码所得，没有在运行时复现。
- Cal.diy README 说团队功能已删，但 `Team`、`Host`、轮转代码仍在；哪些界面还能用，没有验证。
