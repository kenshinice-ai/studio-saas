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

