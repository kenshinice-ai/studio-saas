# 2026-08-23（Claude Opus 5）层 2 前两步落地 + 角色权限的事实与取舍

> Lee 本轮两件事：①「前台和 staff 的权限再仔细核实一下……能不能在管理员开新账号的
> 时候选择哪些权限呢」；②「继续做两页同批重构和排课页」，并点名整合方案 §四 的
> 三条（路由按 tab 作用域解析 `section`、设置页也用 `Tabs`/`TabPanel`、层 0 取舍
> 已随会面结束而失效）。
>
> 本轮**已落地并浏览器实测**：层 2 ①、层 2 ②、排课页生日横幅删除 + 工作台跨年 bug、
> **角色重定义（Lee 已拍板，见六）**。
> 本轮**未做**：排课页分段形态（设计有致命缺陷）、按账号勾权限（Lee 定为下一轮）。

## 一句话

设置页从「七个 `hidden` 面板同时挂载」变成「一次只渲染一个 `TabPanel`」，
顺手删掉 133 行死代码；`?section=` 现在按 tab 作用域解析并按角色收敛。
角色那边查清了一件事：**前台缺的从来不是「订课」权限，而是那一页本身进不去**。

---

## 一、层 2 ①：`?section=` 按 tab 作用域解析（已上线到本地，未发布）

`readCmsRoute`（`components.jsx:58`）以前直接返回 `params.get('section') || 'account'`
—— 没有白名单，也不知道谁登录了。新增 `CMS_ROUTE_SECTIONS` 一张表 + `readCmsSection`，
注册了 tab 才有 section，没注册的 tab 完全忽略这个参数。角色收敛放在
`cms-app.jsx` 的 effect 里（可见性只有 `SETTINGS_SECTIONS` 知道）。

**实测四角色 × 六条 URL（Chrome + CDP，真会话）**：

| URL | 改之前 | 改之后 |
|---|---|---|
| owner `?section=nonsense` | **整屏空白**（无标签选中、无面板渲染） | 落到账号页，URL 规范化成 `?view=settings` |
| manager `?section=integrations` | **集成面板照常渲染**，标签条里却没有它 | 落到账号页，URL 规范化 |
| owner `?section=integrations` | 正常 | 正常，URL 保持 |
| manager `?section=team` | 正常 | 正常，URL 保持 |
| `?view=students&section=integrations` | 忽略 | 忽略 |

### 两个坑，都是实测才现形的

1. **hook 不能写在 `cms-app.jsx:3098` 之下。** 那一行是
   `if (!loggedIn) return <LoginScreen/>`，另有 `:3072` `:3088` 两处提前 return。
   我第一版把 effect 放在 `SETTINGS_SECTIONS` 定义处（约 :3130），登录前后调用的
   hook 数量不同 → React #310「渲染的 hook 比上一次多」→ **整个 CMS 空白**。
   `SETTINGS_SECTIONS` 因此上移到 :337。
2. **`actorRole` 首帧是空字符串**（`cms-app.jsx:294`）。那一帧所有按角色开放的分区
   都判定为不可见，于是一个完全合法的 `?section=integrations` 会在会话回来之前
   就被收敛成 account、连 URL 一起改掉，角色到位也救不回来。effect 必须
   `if (tab !== 'settings' || !actorRole) return`。

> 两个都是「跑起来才知道」的：构建通过、全量测试通过、静态断言全绿。
> 第一次截图 3.6KB（空白页），正常是 45–55KB —— 这个差值是唯一的报警。

## 二、层 2 ②：设置页换 `Tabs`/`TabPanel`

原来 7 个面板都是 `<div role="tabpanel" hidden={...}>`，**只要忘了写 `hidden` 就会在
七个分区里同时出现** —— 这一页积了六块这样的共享内容。换成 `TabPanel`
（`components.jsx:268`，未激活直接 `return null`）之后这个失败模式结构性消失。

六块共享内容的去向（这份清单是本轮唯一的高风险项，逐块核对过）：

| 块 | 处置 |
|---|---|
| 手机端语言切换 | 留在所有面板外（真·共享） |
| Studio Admin 入口 | 留在所有面板外（真·共享） |
| 未到访预警天数 | **并入 `operational`**（以前七个分区各出现一次） |
| 「课程目录与充值套餐已移到对应工作区」 | **删除** —— 它说「设置只保留账号、团队、运营默认和数据维护」，而现在有七个分区，这句话本身已经是假的 |
| `MaintSection` 数据维护工具 | **并入 `maintenance`**。它只有 `id` 没有 `role="tabpanel"`，所以历次盘点都少数一个 |
| 退出登录 + 手机端快捷操作 | 留在所有面板外（真·共享） |

顺带删掉的死代码：

- **弹窗分支**（`{showSettings && (` 里那条 `fixed inset-0` 覆盖层）。`showSettings`
  只在 `tab==='settings'` 时为真（`:124`/`:139`/`:150` 三处），所以那条分支不可达；
  与它配套的 `useModalFocus(Boolean(showSettings && tab !== 'settings') …)` 同理。
- **`{false && <>…</>}` 里 133 行**课程/套餐旧界面。

**实测 4 角色 × 8 section = 32 例全通过**，断言是「恰好渲染 1 个 tabpanel，且它就是
选中的那个」：

- teacher / front_desk 以前是**标签 2 个、面板 4 个** —— 开票信息与集成会照常挂载
  **并发请求**；现在恰好 1 个。
- 全量测试 `2840 passed, 87 skipped`。

### 两条测试被这次改动照出来了

1. `test_cms_ui_contract.py` 断言设置页是「有名字的键盘弹窗」。它不再是弹窗了 ——
   改成断言 `id="settings-page-title"` 且 **不再**声明 `aria-labelledby="settings-dialog-title"`。
2. `test_timetable_fields.py:332` 断言 `'+ 添加课程'` 在源码里。**这条以前只被那 133 行
   死代码满足**：活着的按钮写的是 `<Icon name="plus" …/>添加课程`。死代码删掉的
   那一刻它才现形 —— 又一次「静态测试看不见行为」。已改为断言活着的那个。

## 三、排课页：生日横幅删除 + 工作台一个跨年 bug

删掉 `scheduling.jsx` 的「近 14 天生日」横幅（22 行）—— 工作台本来就有本周/本月两行，
删掉不丢信息。这是 Lee 最早那句「生日提醒可以不在课程安排这里」。

删的时候发现工作台那份**算错**：

```js
const bd = new Date(now.getFullYear(), 月-1, 日);   // ← 永远是「今年的那一天」
return bd >= now && bd <= weekEnd;
```

12 月 29 号看 1 月 3 号的生日，`new Date(今年,0,3)` 落在过去 → 这个人**在跨年那一周
整周消失**；而 `本月生日` 按日历月匹配，也接不住他。改成逐日向前扫（就是刚删掉的
横幅用的算法，两份实现里算得对的那一份）。

> `now.setHours(0,0,0,0)` 已经在 `:166`，所以「今天过生日的人被排除」**不是** bug ——
> 我一开始判断错了，以这句为准。

## 四、角色权限：查清的事实（不含推断）

### 4.1 前台缺的不是「订课」权限

| 事实 | 证据 |
|---|---|
| front_desk **已经有** `scheduling:write` | `auth.py:141`。可建/改一对一循环课、停课、补课（`scheduling.py:1638/1699/1765/1870`） |
| front_desk **已经有** `class_bookings:review` | 批准预约会写排课行 |
| 但 `roleTabs.front_desk` **不含 `roster`** | `cms-app.jsx:302`；实测 front_desk 打开 `?view=roster` **被弹回工作台** |
| 所以 `canWriteScheduling` 里的 `front_desk` **是死代码** | 它只在 `cms-app.jsx:3738` 与 `scheduling.jsx:84` 被消费，两处都在 `tab==='roster'` 里 |

**后端早就给了，前端把承载它的整页藏了。**

### 4.2 前台已经能扣课时，走的是记录更差的那条路

| 路径 | 权限 | 写不写 `attendance_sessions` | 账本行有没有操作人 |
|---|---|---|---|
| `POST /attendance/check-in` | `attendance:write`（前台**没有**） | 写 | **写** `actor_user_id`（`students.py:1489`） |
| `POST /students/<id>/credit-transactions` type=consume | `credits:write`（前台**有**） | 不写 | **不写**（`students.py:1168` 的列清单里没有这一列） |

本地账本实测：`consume` 97 行全部有操作人，`adjustment` 全部没有。

**Lee 的「反正是有 log 的」成立，但要说准**：两条路都会写一行 `audit_logs`（带操作人和
IP）；只是 `audit_logs` 是 `@tenant_owner_required`（`platform.py:1649`）——**只有 owner
读得到**；而 CMS 给员工看的课时流水接口（`students.py:1029`）**任何一条都不返回操作人**。

**还有一条更硬的，已独立复核**：`PATCH /students/<id>`（`students.py:1758`，
`@permission_required("students:write")` —— owner / manager / **front_desk / staff** 都有）
带 `balance` 字段可以把任意学员的课时余额改成任意值，而：

- 它写的账本行列清单是 `(tenant_id, student_id, transaction_type, amount, balance_after)`
  —— **没有 `actor_user_id`**；
- `balance` **不会进入 `updates` 字典**，而 `_audit_request` 在 `if updates:` 里面 ——
  所以一个只带 `balance` 的 PATCH **连 audit 行都不写**。

这是三条改课时的路径里唯一**零归属**的一条。CMS 界面不发这种请求（grep 为 0），
所以它是接口面的洞不是界面路径 —— 但「反正是有 log 的」这个前提，只有堵上它之后
才对全部三条路径都成立。**建议随角色改动一起堵。**

### 4.3 staff 和 teacher 的差异，两个方向都有，而且不自洽

- teacher 有、staff 没有：`scheduling:read`、`progress_reports:write`
- staff 有、teacher 没有：`students:write`、`credits:read/write`、`registrations:read/write`、`billing:read`

也就是说：**staff 能给学员充课时、扣课时、看工作室银行账号，teacher 不能。**

## 五、Lee 的四个决定（2026-08-23 拍板）

| # | 问题 | 决定 |
|---|---|---|
| 1 | staff 是不是助教 | **是** |
| 2 | 前台拿整个 `attendance:write` 还是更窄的 key | **整个拿** |
| 3 | 要不要守卫强制课时扣减只走签到 | **不要，两条路都留着**（签到 + 调整），保留灵活性 |
| 4 | 每周课表是否从 `@tenant_admin_required` 改成权限判定 | **先理顺角色，之后再谈** |

「按账号勾权限」定为下一轮：存储（`memberships.permissions`）和判定点
（`require_permission`）都已就位，但 18 条路由根本不查权限表，勾了也是假的。

## 六、角色重定义（已实现）

### 6.1 后端

- `FRONT_DESK` **+`attendance:write`**。退款类（`credits:refund` / `payments:refund`）
  与课酬仍然不给，测试锁着。
- `STAFF` 重写为**助教**：`{students:read, scheduling:read, attendance:read,
  attendance:write, portfolio:read, portfolio:write, plans:read,
  progress_reports:read}`。恰好是 `TEACHER` 减去 `progress_reports:write`
  与 `payroll:self:read` —— 有一条测试断言 `STAFF ⊂ TEACHER` 且差集恰为这两个。
- `_project_legacy_data_for_role`（`tenant.py:1004`）的 TEACHER 分支加上 STAFF。
  **这是权限模型的另一半**：只改 `ROLE_PERMISSIONS` 而不改这里，助教仍会拿到
  套餐表、报名箱和带金额的完整日志 —— 比它协助的老师还多。

### 6.2 归属（Lee 决定两条路都留，所以两条都要记得住是谁）

| 位置 | 之前 | 现在 |
|---|---|---|
| `students.py` 手工课时调整 | 账本行**无操作人** | 写 `actor_user_id` |
| `students.py` `PATCH /students/<id>` 的 balance | 账本行无操作人，**且完全不写 audit 行**（`balance` 不进 `updates`，而 `_audit_request` 在 `if updates:` 里） | 写 `actor_user_id`，并在真正发生变动的地方补一条 `credit.adjusted` |

**没有**加强制守卫：手工调整仍然可用，只是从此记得住是谁做的。

### 6.3 前端

`roleTabs`：前台 +`roster`；助教改成与 teacher 完全相同的一组。
`canWriteAttendance` +front_desk；`canWriteStudents` / `canWriteCredits` /
`canReviewBookings` / `canViewCmsNotifications` 各去掉 staff。
团队成员那个下拉从「Staff (legacy)」改成「Assistant 助教」，旁边那句角色说明
本来就没提 staff、且把签到只算给 Teacher，一并重写。

### 6.4 实测（本地，真会话）

| 检查 | 结果 |
|---|---|
| 前台 `GET /attendance` | 200（原先 403） |
| 前台 `POST /attendance/check-in` | **201**，Ana Bianchi 12 → 11 |
| 该账本行的操作人 | `consume \| frontdesk.showcase@…`（不再是空） |
| 前台 `POST /attendance/<id>/void` | 200，余额回到 12，退课时行同样具名 |
| 助教 `GET /billing/identity` | **403**（原先 200） |
| 助教 / 前台 `?view=roster` 渲染 | 两者都出得来（前台原先被弹回工作台） |
| 助教导航 | 与 teacher 完全一致（无账单、无充值、无待处理） |
| 全量测试 | `2841 passed, 87 skipped` |

> 演示数据已复原（那次签到已撤销，余额 12.0）。账本上留下 consume + refund
> 两行，互相抵消且都具名 —— 我没有删账本行。

### 6.5 文档

`docs/guides/README.md` 的权限矩阵是**机器校验**的（`test_user_guides.py`
逐格比对 `ROLE_PERMISSIONS`），六格翻转 + 新增 `scheduling:read/write` 两行。
`Front_Desk_Staff_Guide.md` 是对客手册，原文写着「前台**不做签到**」「Staff
能力接近 Manager」，已按新定义重写角色定位、导航清单、第五节和 FAQ，
并新增一条「签到 vs 手工调整有什么区别」。

## 七、code-review 的四条 —— 全部已修

| # | 问题 | 修法 |
|---|---|---|
| 1 | **`canWriteAttendance` 根本没传进 `RosterSection`**：排课页所有会扣课时的控件只由 `busy` 把关。今天不出事纯属巧合——能进这一页的五个角色恰好都有那把钥匙 | 传下去，并给 13 处写控件逐个加判断（加学员、套用模板、批量签到 ×2、单人签到、行内改时间、课程状态、1对1 标记、撤销签到、移出当日、空状态 CTA）。只读角色看到的是静态时间与「待上课」 |
| 2 | `bdayWithin` 用精确月日前扫，**2 月 29 日的孩子平年永远进不了「本周生日」**（旧代码靠 JS 日期溢出误打误撞接住） | 平年按 3 月 1 日过，与旧行为一致 |
| 3 | `readCmsSection` 是导出的，用调用方给的 `tab` 索引对象字面量，传 `'constructor'` 会绕过判空再抛 TypeError | 表改用 `Object.create(null)`，并加 `Array.isArray(scope.allowed)` |
| 4 | 一次 PATCH 同时带 `balance` 和 `creditHours` 会写两条调整 + 两条 audit，且后者静默覆盖前者 | 两者是**同一个量**的两个名字，且没有任何客户端发 `creditHours`。解析成一次移动；两个都给且不相等时**明确报错**，不再按书写顺序碰运气 |

**新增两条不变量测试**（都能抓住第 1 条的复发）：

- `test_every_role_that_can_open_the_roster_can_write_attendance`：解析
  `cms-app.jsx` 的 `roleTabs`，凡是能进 roster 的角色必须持有
  `attendance:write`。实测解析到 7 个角色、7 个含 roster，不是空跑。
- `test_the_roster_panel_is_handed_the_attendance_gate`：`RosterSection`
  的挂载点必须收到 `canWriteAttendance`——「一个没人往下传的 gate 不是 gate」。

顺带：前台的工作台「今日重点」补上「查看今日课程」入口——本轮刚给了它这一页，
它的快捷区却还没有链接过去。

**实测**（加完判断后重量一次，确认没把有权限的人也挡住）：
front_desk / teacher / manager 三个角色在排课页各看到 **5 个签到按钮 + 添加学员块
+ 批量签到**，控制台 0 错误；助教（音乐租户）当天没有排课，`addStudentBlock=true`
证明判断放行，按钮为 0 是因为那天空着。全量 `2841 passed`。

## 八、排课页拆分：阶段一（甲·重排）已实施

见 `docs/design/CMS_Roster_Split_Plan.md`。**它推翻了源文档的诊断**：

- 源文档把「排课挤掉签到」归因于固定课表那 213 行。**实测那块是 `<details>`，
  折叠状态只有 62px**；一对一 46px。「折叠大块」这条路已经走完了。
- 真正的元凶是**「添加学员」块**：桌面 135px、**手机 270px**，
  和班组模板一起夹在概览条与学员名单之间。
- 实测第一行学员：**桌面 top 898（首屏 900）——一行都看不见；手机 top 1124
  （首屏 844）——在屏外 280px**。
- 只做重排（甲）预测：桌面 ≈566、手机 ≈657，**两边都进首屏**。
- 乙在甲之上只多买 **60–110px**，但买到三件别的：对 teacher/助教
  整个排课半边是只读的、排课拿到自己的 URL、概览条才有条件真正吸顶。

**结论：乙不是甲的替代，是甲之后的下一步，而甲是乙的必经工序**
（要分标签，先得逐块判定归属）。建议 甲 → 量一次 → 乙。

清单共 19 步，已把评审判出的两条硬伤写进步骤：概览条吸顶的原设计
**不生效**（sticky 在父级内容盒里，做成最后一个子元素等于无处可吸），
单店模式下「排课设置」**整块是空的**。另有容器查询断点平移 32px、
日期导航搬出卡片会丢背景两条。

## 九、阶段一 · 甲：已重排，实测进首屏

清单前八步全部完成。页面顺序现在是：

```
错误横幅 → 日期/周视图/概览条/时段安排（planner 卡）
        → 学员名单
        → 添加学员 + 班组模板（新的 .cms-roster-tools 卡）
        → 一对一循环课
        → 固定课表
```

**第一行学员的 top（同一台机器、同一租户）**

| | 重排前 | 重排后 | 首屏 |
|---|---|---|---|
| 桌面 1440×900 | 898 | **542** | 900 ✅ |
| 手机 390×844 | 1124 | **634** | 844 ✅ |
| 窄机 360×780 | — | **689** | 780 ✅ |
| 极窄 320×700 | — | 705 | 700 ❌ 差 5px |

桌面首屏从 **0 行学员**变成 **5 行**。320px 是唯一没进的档，差 5px；
现有断点体系下限是 639px，手册截图矩阵也没有这一档，**没有为它动手**。
真要救，下一个杠杆是时段安排面板（桌面 136px / 手机 400px），但那属于
阶段二的分区判定。

**一处非 JSX 的改动**：`.cms-roster-add-fields` 的窄屏栅格写在
`@container roster-planner` 里。add 块搬出 planner 卡后这条会失效
（手机上三列栅格撑破卡片），所以新卡 `.cms-roster-tools` **复用同一个
容器名**、同样的 `p-4`——容器查询按内容盒算，断点落点因此不变。
`legacy-root/index.html:619`。

**两条新守卫**

- `ROSTER_UI_CONTRACT` 加 `addOutsidePlanner` 与 `firstRowInFold`
  （`rect.top < innerHeight`）。后者就是这次重排的目的，量出来而不是看出来。
  两张手册图重截时都通过了。
- `test_the_roster_edits_sit_below_the_list_they_edit`：纯源码顺序守卫。
  契约只在截图时跑，CI 里没有浏览器。六个标记在文件里唯一且严格递增
  （84 / 222 / 316 / 322 / 378 / 390 行）。

## 十、顺手修掉的零散缺陷（排课 #4–#8 + 截图脚本）

| 缺陷 | 表现 | 修法 |
|---|---|---|
| 排课 #4 | 日报标题写死「今日上课」，选了下周二也照写，粘进群里没人看得出选的哪天 | 标题跟着 `rDate===todayISO()` 走 |
| 排课 #5 | 「转为每周班次」把编辑器开在折叠的固定课表里，看起来毫无反应 | `#rosterSchedules` 展开 + 滚动到位 |
| 排课 #6 | 「保存当前为模板」只存 `db.rosters[rDate]`，漏掉全部课表学员 | 改用 `dayIds` 并集；`applyGroup` 的去重也改用并集 |
| 排课 #7 | 手机「当日操作」菜单点完不关，盖住刚改的那一行 | 容器上统一关闭，顺带覆盖了五个手写关闭器漏掉的 `sms:` 链接 |
| 排课 #8 | 「≤360px 周视图重叠」 | **不复现**，没有改。320px 下 7 格高度一律 68px、`scrollWidth ≤ innerWidth`；已被现有 `@media (max-width:639px)` 修掉 |

**外加一条源文档没列的**：`capture_manual_shots.py` 的 `next_class_date()`
向**后**找上课日。种子课在周二/四/六，所以在周日/一/三/五跑截图会落在
today+2；而签到窗口是 `[today-90, today+1]`，于是手册里最忙的一页
**每个签到按钮都是灰的**，概览条上还挂着「这一天还没到，不能签到扣课时」。
改成 `recent_class_date()` 往回找——上一个上课日永远在窗口内。
旧的 03-roster 手册图里**一个学员都没有**（整屏是一对一、生日横幅、固定课表、
添加学员），新图是 4 行学员 + 可点的「签到并扣 1 课时」+ 低余额行的续费提醒。

**#5 / #6 是在浏览器里跑通的，不是读代码断言的。** 2026-08-22 那天
`/v1/daily-roster` 的 `entries` 是**空数组**、10 人全部来自两个固定班次。
修之前「保存当前为模板」在这一天会弹「当前日期没有排课可保存」且什么都不存；
修之后存进 `PROBE-TEMP-DELETE-ME（10 人）`。随后选中它点「转为每周班次」，
`#rosterSchedules` 的 `open` 变 true、`inView` true、编辑器 9 个字段就位。
**探针建的模板已删除**，选项列表回到只剩占位项。

全量 `2843 passed, 87 skipped`。

## 十一、发布前对抗式复查：一个越权、一处隐私、四个假守卫

`/code-review` 是在排课重排**之前**跑的，所以重排 + 五处缺陷修复那一批没被审过。
提交之后、推送之前跑了一轮六视角对抗复查。**验证阶段撞上月度额度上限**
（84 个 agent 里 73 个报错），所以 `confirmed: []` 是「一个都没验」，不是
「一个都不真」——六个发现者跑完了，26 条候选我逐条自己查。

### 越权（阻断发布）

**前台可以改课酬口径。** 链条是我自己接上的：

```
roleTabs.front_desk 加了 'roster'        ← 本轮
  → 排课页渲染 PrivateLessonsPanel canWrite={canWriteScheduling}
  → canWriteScheduling 含 front_desk     ← 一直如此
  → 「请假规则」表单可写
  → PUT /scheduling/policy 只要 scheduling:write ← 前台持有
  → 200
```

前台可以关掉「临时请假老师照付课酬」，把老师那节课的课酬清零——而这一版
**同时**明确不给前台 `payroll:read`，它连自己改了什么都看不到。

我在上一份 handoff 里写过「`canWriteScheduling` 里的 front_desk 是死代码，
因为 roleTabs 没给它那一页」。然后我给了它那一页，没有回头重查这句话。
**权限的死代码是由导航表宣布死亡的，导航表一改它就活了。**

修法：新增 `scheduling:policy:write`（仅 Owner/Manager），PUT 改判这把钥匙，
前端 `PolicyEditor` 收 `canWritePolicy={canManageOperations}`。前台保留
`scheduling:write`（约课、改时间、开循环课），只是看得到、改不了规则。

### 隐私

**`GET /class-bookings` 一直没有权限判断**（`@auth_required`），而它返回每个
待处理约课请求的 `contactName` / `contactPhone` / `message`，并且
`loadSchedules()` 对**所有角色**在每次排课页加载时都调它。旁边那条 PATCH
一直判 `class_bookings:review`。

这是旧洞，但**本轮把它变成了承重的**：助教被拿掉 `registrations:read`、
并被加进「清空 pending」的投影分支，于是产品开始声称一条 API 并不执行的边界。
改判 `class_bookings:review`。实测 manager 200 / front_desk 200 / **teacher 403**。
手机「更多」上那个点不开的角标数字也跟着消失了。

### 四个假守卫（其中两个是我这轮新加的）

1. **`firstRowInFold` 用 `top < innerHeight`** —— 重排前桌面是 898，首屏 900，
   `898 < 900` 为真。**这条断言在 bug 上也通过**。改成要求整行的 `bottom`
   高于「可读首屏」（减掉底部固定导航实测的 53px）。
2. **`noOverflow` 量的是 documentElement** —— CMS 滚的是
   `main.overflow-y-auto`，`overflow-y:auto` 让 `overflow-x` 也成为滚动区，
   于是 `documentElement.scrollWidth` 永远等于 `clientWidth`。这条断言对任何
   排课内容都不可能失败。改成问真正滚动的那个容器。
3. **`recent_class_date()` 里手写的 `{2,4,6}`** —— 播种器教五天
   （周二三四六日）。改成 `from showcase_content import SCHEDULES` 推导。
4. **`09-private-lessons` 没有 prepare 步骤** —— 它拍 `?view=roster` 的视口顶部，
   而一对一那块原本恰好在顶部。重排把它挪到页尾，这张图会变成「标题写一对一、
   画面是当天名单」。补了展开 + 滚动的 prepare。

### 收紧的断言立刻抓到一个真问题

`03-roster-mobile` 截图**失败**了。量出来：**中文过、英文不过**。
英文的概览条折成两行（69px vs 42px）、星期标签更高（83px vs 68px），
第一行学员的底边落在 810，可读首屏是 791。

> 只截一种语言，就只量了一半的产品。

修法（`@media (max-width:430px)`）：可见的「课程日期」标签转为仅读屏可见
（左右箭头 +「今天」+ 日期框本来就不含糊），概览条 / 时段面板 / 星期条收紧间距。
英文 810 → 778，中文 740 → 712，两边都进可读首屏。

另外把**时段安排折叠**了：它把当天每个人的名字在名单**上方**再印一遍，
十人的周六在手机上要 400px。只有「1 对 1 时间冲突」是下面名单说不出来的，
所以有冲突时自动展开。

### i18n：改中文=改字典键

字典是按中文原文做键的。我改了三句、加了两句，于是：

| 中文串 | 状态 |
|---|---|
| `来自固定课表，需在上方班次中调整` | 键成孤儿 → 英文界面**回退成中文**（回归） |
| `可以在上方「每周课表」建一个固定班次…` | 同上 |
| `调整这一天的名单`（新） | 无条目 |
| `今日上课` / `上课名单`（新） | 无条目 |
| `${groups.length} 个时段`（新） | 需要走正则表 |

全部补齐。顺带补了 `当日操作`、`复制日报`、`操作人：`。
`audit_cms_translation.py`：排课页 15 → 13（剩下的是双语种子数据），全站 27 → 25。

### 「存了 ≠ 显示了」

本轮给课时流水补上了 `actor_user_id`，但 `_legacy_data_for_tenant` 的
logs 查询**从来没 select 这一列**——而操作日志的渲染早就有
`操作人：{l.actorEmail}`，只是永远拿不到值。补一个 `LEFT JOIN users`。
实测：60 条流水 **60 条带操作人**，签到和手工调整都有。

### 其它

- `PATCH /students/<id>` 传 `{"balance": "nan"}`：`float()` 收下，
  `abs(delta) <= 0.001` 因为 NaN 比较恒假而不拦，最后写进账本。加 `math.isfinite`。
- `applyGroup` 改用 `dayIds` 并集是**我改错了**：课表来的学员没有
  `daily_roster_entries` 行，而 `entry.id` 正是行内改时间 / 标补课 / 标 1 对 1 /
  移出当日的开关。`addToRoster` 已经对 `dayIds.includes` 提前返回，所以套模板
  是最后一条能给他们建行的路。已改回手工名单。`saveGroup` 用并集是对的，保留。
- 客户手册的权限表、`docs/Admin_Guide.md` 的矩阵与结论段、前台手册的
  权限边界表全部停在改动前；前台手册第五节标题写「Front Desk 与 Staff 都可以」，
  三行之后写「Front Desk 没有这个标签页」；两个问答都编号 Q7。全部改正。
- `manual.html` 与 `Teacher_Guide.md` 还在讲已删除的排课页生日横幅；
  生日提醒现在在工作台，窗口 8 天（横幅是 14 天）。文档改为指向工作台。

新增测试 4 条：请假规则权限、策略路由判的是哪把钥匙、约课列表与审批同权、
非有限数的余额被拒。全量 `2848 passed`；门禁 `All checks passed`。

## 十二、本轮仍未做的

- 阶段二 · 乙（页内标签），清单第 9–19 步。
- 按账号勾权限（Lee 定为下一轮）。
- 每周课表的权限模型（`@tenant_admin_required` → permission），Lee 定为
  「先理顺角色，之后再讨论」。
- 320×700 差的那 5px。
- 未跑 `verify_local.sh` 发布门禁；**改动尚未提交、未发布**。
