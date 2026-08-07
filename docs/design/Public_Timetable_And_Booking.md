# 公开课表 + 免注册约课 · 定案（未实现）

第三轮。前两轮：`Public_Timetable.md`、`Public_Timetable_Round_2.md`。
**本文是要执行的那一份**，前两轮里被本文推翻的以本文为准。

已拍板：满了用灰、显示开关要留自由度、停课表要做。

---

## 1. 免注册约课 —— 地基已经在了

先说结论：**这个功能的两半，系统里都已经有了。**

### 1.1 免注册认人：已存在

`services/student_access.py:find_student()` 已经在用**姓名 + 手机号**认人，
而且规则比想象中严谨：

- 单字名只匹配 `first_name`，多字名匹配完整显示名；
- **明确排除只用姓氏匹配**；
- 必须**唯一命中**，同名同姓两条记录一律视为不匹配；
- `public_balance_query` 已按 IP 限流（10 次）。

「学员专区」查课时余额走的就是这条路。**约课用同一条，不发明第二种身份。**

### 1.2 待审核队列：已存在

`registrations` 表已经有 `status` / `reviewed_by_user_id` / `review_note` /
`duplicate_of_registration_id` / `assigned_user_id` / `campaign` / `source`，
CMS 也已经有「待审核」页（你截图里正是 4 项）。

---

## 2. 但约课不能塞进 registrations —— 它是两件事

| | 新家长约体验课 | 老学员约某一节课 |
|---|---|---|
| 他是谁 | 系统里还没有 | `students` 里已有，有课时余额 |
| 批准后发生什么 | **创建学员** | **占一个座位**（`daily_roster_entries`） |
| 该不该计入「新报名」 | 是 | **否** |

把老学员约课记成一条 `registration`，会让「本月新报名」这个数字永远虚高——
而那是工作室用来判断投放有没有效果的数字。**一个被污染的经营指标，
比没有这个指标更糟。**

所以新开一张表：

```sql
CREATE TABLE class_bookings (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  schedule_id         uuid NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
  on_date             date NOT NULL,
  -- 二选一：命中老学员，或牵出一条新报名。两个都空 = 未识别的新访客
  student_id          uuid NULL REFERENCES students(id) ON DELETE SET NULL,
  registration_id     uuid NULL REFERENCES registrations(id) ON DELETE SET NULL,
  -- 永远保留家长填的原文，即使后来匹配上了别的记录
  contact_name        text NOT NULL,
  contact_phone       text NOT NULL,
  message             text NOT NULL DEFAULT '',
  status              text NOT NULL DEFAULT 'pending',
  review_note         text NOT NULL DEFAULT '',
  reviewed_by_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at         timestamptz NULL,
  privacy_notice_version text NOT NULL DEFAULT '',
  source_language     text NOT NULL DEFAULT '',
  campaign            jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at          timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT class_bookings_status_check
    CHECK (status IN ('pending','approved','declined','cancelled'))
);
CREATE INDEX idx_class_bookings_pending
  ON class_bookings (tenant_id, on_date, created_at) WHERE status = 'pending';
```

**CMS 只有一个收件箱**：「待审核」页同时列报名与约课，分两个标签，
顶部计数分开写（`新报名 4 · 约课 2`）。前台不该有两个地方要看。

---

## 3. 约课的关键决定

### 3.1 待确认的请求**不占座**

否则一个随手点的请求会挡住一个真要来的人，工作室还得去追。

- 公开页 `seatsLeft = capacity − 已批准`
- **容量在「批准」那一刻再校验一次**，不是在提交时。两个人同时约最后一个
  位置，先批的成功，后批的会收到「已满」并可改约——这是唯一诚实的做法，
  因为提交时的判断到批准时早就过期了。

### 3.2 但要如实告诉家长排在第几个

一个显示「还有 1 位」的班收到 5 个请求，4 个人会被拒——那是很差的体验。

所以提交后直接说：**「目前还有 1 个位置，已有 3 人在等待确认」**。
诚实，而且把选择权交回给他。比默默排队或直接挡住都好。

### 3.3 提交结果**不能泄露这个手机号是不是学员**

服务端会拿姓名+手机去匹配老学员——**但返回给页面的内容必须完全一样**，
不论有没有匹配上。

否则这个表单就变成了一个查询接口：输入一个号码，看回应有没有差别，
就能判断某人是不是这家机构的学员。**这不是理论风险，这是同一个表单的
另一种用法。** 匹配只发生在服务端，结果只出现在 CMS 里。

同样沿用 `_rate_limited`。

### 3.4 隐私同意照旧记录

跟报名表一样记 `PRIVACY_NOTICE_VERSION`。收姓名和手机号就要有这一步。

### 3.5 批准之后

- 命中老学员 → 写一条 `daily_roster_entries`（`source='booking'`，
  需要在现有 CHECK 里加这个值）
- 未命中 → 同时创建一条 `registration`，走既有的报名审批链路，
  并把 `registration_id` 回填到本条 booking
- 两种都写 `audit_logs`

### 3.6 不做的

- **不发通知邮件**（v1）。CMS 工作台的「今日待办」已经会显示待处理数，
  跟报名一样。邮件是另一条链路，等有人要再说。
- **不做取消/改期的自助入口**。家长要改，打电话——这一版先把"能约上"做对。

---

## 4. 显示开关：给自由度，但只给一个结构

你要留自由度，我同意留，但**不用六个散落的布尔**：

```jsonc
// website_profile.timetable_fields
{ "teacher": true, "room": true, "age_range": true,
  "duration": false, "capacity": true, "price": false }
```

三条规则让它既自由又不会炸：

1. **缺的键取推荐默认值。** 以后加字段不用迁移，老租户自动拿到新默认。
2. **渲染是一个循环，不是六个分支。** 所以 64 种组合不是 64 种版式，
   是一种版式的 64 个子集——这正是我上一轮担心的东西，用数据结构消掉。
3. **仍然「有内容才显示」。** 开关开着但没填地点 → 不出现空的「地点：」。
   开关是上限，内容是下限，**取交集**。

### 老师那一项是 AND，不是 OR

`timetable_fields.teacher` 开着 **且** 这位老师在团队管理里勾了
「可在公开课表显示」，才显示。**任何一个关着都不显示。**

个人同意永远压过版式偏好——这不是可配置项，这是顺序。

---

## 5. 余位芯片（已定）

| 状态 | 芯片 | 文案 |
|---|---|---|
| 有位 | `success-soft` 绿 | 还有 N 位 |
| 快满 | `warning-soft` 琥珀 | 快满了 · 还有 N 位 |
| 已满 | **中性 `--muted` + 线框** | 已满 · 可加候补 |

- **必须带文字**，颜色是第二信号（WCAG 1.4.1）。
- **不做实心填充**（§1.1）；一屏那一个饱和填充留给「预约体验」。
- 阈值按比例：**快满 = 剩余 ≤ max(1, ⌈容量 × 25%⌉)**。容量从 1 到 30 都有，
  绝对阈值必然出错。
- `timetable_fields.capacity` 关闭时三种芯片都不出现。

---

## 6. 停课（已定）

```sql
CREATE TABLE class_schedule_exceptions (
  schedule_id uuid NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  on_date     date NOT NULL,
  cancelled   boolean NOT NULL DEFAULT true,
  note        text NOT NULL DEFAULT '',
  PRIMARY KEY (schedule_id, on_date)
);
```

公开页把那一天**划掉并写明原因**，不是让它消失——
**消失看起来像网站坏了，标注停课看起来像有人在管。**
停课的那一节不接受约课。

---

## 7. 其余已定的字段

```sql
ALTER TABLE class_schedules
  ADD COLUMN teacher_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN is_public       boolean NOT NULL DEFAULT false,   -- §不是每堂课都该公开
  ADD COLUMN room            text    NOT NULL DEFAULT '';
ALTER TABLE memberships
  ADD COLUMN public_display_name      text    NOT NULL DEFAULT '',
  ADD COLUMN show_on_public_timetable boolean NOT NULL DEFAULT false;
```

- `course_id` 已有列但 CMS 从没写过 → 加课程下拉，没选退回 `label`。
- `website_profile.timetable_weeks`（1–4，默认 2）。
- **内部 uuid 不进公开接口**；对外用「日期 + 开始时间」定位。
- **冲突判定改成「同老师 + 时间重叠」**。现在只比时间，加了老师之后
  同时太松（同一老师撞课不报）又太紧（两位老师同时段误报）——
  **一个总是误报的警告等于没有警告。**

---

## 8. 时区

投影用 `tenants.timezone`，**在服务端算**，「今天」也在服务端按租户时区定。
浏览器算会算错一天。这个产品在日期上栽过一次（RFC 1123），不重犯。

---

## 9. 版本切分

| 版本 | 内容 | 对外影响 | 估时 |
|---|---|---|---|
| **v8.8.0** | 深色变亮 · 后台全部字段 · 停课表 · 冲突判定改按老师 · 老师公开开关 | **无** | ~2 天 |
| **v8.9.0** | 公开课表接口 + 门户板块 + 余位芯片 + `timetable_fields` | 有 | ~1.5 天 |
| **v8.10.0** | 免注册约课（公开表单 + `class_bookings` + CMS 审批 + 批准落到排课） | 有 | ~2 天 |

**v8.8.0 完全没有对外影响**——字段加完公网什么都不变，可以放心先发、先用，
让真实数据长出来，后两版就有真东西验收版式。

深色变亮放 v8.8.0 是因为它和后台字段互不相干，**不值得单独占一次发布**。

---

## 10. 还没定的

1. 约课要不要**限制提前天数**（比如只能约未来 14 天内）？我倾向要，
   否则会收到三个月后的请求。默认 = `timetable_weeks` 的范围。
2. 一个手机号**同一节课重复提交**怎么办？我倾向：同一 `(schedule_id, on_date,
   contact_phone)` 已有 pending 就直接返回"已经收到了"，不新建。
