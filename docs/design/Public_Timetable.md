# 公开课表 · 方案（待确认，未实现）

指定老师 → 门户展示未来排课。以及两个小问题的难度评估。

---

## 0. 好消息：一半的东西已经在了

`class_schedules` 已经存在，而且已经有 CMS 界面（「每周课表」）在用：

```
class_schedules: tenant_id | course_id | label | weekday(0-6)
                 start_time | duration_minutes | capacity | is_active
class_schedule_students: schedule_id | student_id     ← 已报名人数
courses:  name | description | category | age_range | duration_minutes | price
memberships.role 已有 'teacher'；/tenant/team 接口已存在
tenants.timezone 已有（线上都是 Australia/Melbourne）
```

**你要的四样里有三样已经有字段**：时间、时长、容量（→ 还剩几位）。
线上现有 4 条课表记录，只有 1 个租户在用——**改动面很小，现在做正是时候**。

缺的是：**老师**、**公开与否**、**地点**，以及整条对外链路。

---

## 1. 缺的字段

```sql
ALTER TABLE class_schedules
  ADD COLUMN teacher_user_id uuid NULL REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN is_public       boolean NOT NULL DEFAULT false,
  ADD COLUMN room            text    NOT NULL DEFAULT '';
```

### 1.1 `is_public` 默认 false —— 这条不是保守，是必须

**不是每一堂课都该出现在公网上。** 一对一的时段、内部补课、试听位、
只对老学员开放的进阶班——把「已排的课」等同于「对外招生的课」，
第一个受害的就是那些本来不该被陌生人看到的安排。

所以：排课默认不公开，工作室**逐条**勾选要对外展示的。

### 1.2 老师上公网需要单独同意

```sql
ALTER TABLE memberships
  ADD COLUMN public_display_name        text    NOT NULL DEFAULT '',
  ADD COLUMN show_on_public_timetable   boolean NOT NULL DEFAULT false;
```

**一位老师的名字不该因为「他被排了一节课」就出现在公开互联网上。**
这是员工的个人信息，不是工作室的资产。默认不显示；由 Owner 在团队管理里
逐人打开，并且可以填一个**对外显示名**（很多老师对外用「Lucy 老师」而不是
身份证上的名字）。

关掉时课表照常显示，只是不带老师——不影响功能。

### 1.3 `course_id` 现在是空的，建议接上

表上有 `course_id`，但 **CMS 建课表时从来没写过它**（`INSERT` 里没有这一列），
所以每条课表只有一个前台随手打的 `label`。

对内无所谓，**对外不行**：公开课表想显示的课程描述、适龄段、时长，
都在 `courses` 里。建议 CMS 的课表编辑器加一个课程下拉：

- 选了课程 → 公开页显示课程名 + 适龄段（`label` 作为副标题，比如「周三班」）
- 没选 → 退回 `label`，功能不受影响

---

## 2. 必须一起做的一件事：请假 / 停课

**这一条如果不做，这个功能不该上线。**

`class_schedules` 是「每周几」的循环规则，没有「这一周三停课」的表达。
`daily_roster_entries` 有 `status='cancelled'`，但那是**按学员**的，不是按班的。

后果很具体：**某周停课，网站照旧显示，家长白跑一趟。**
一个改不了的公开课表，比没有课表更糟——它是一个兑现不了的承诺。

最小的表：

```sql
CREATE TABLE class_schedule_exceptions (
  schedule_id uuid NOT NULL REFERENCES class_schedules(id) ON DELETE CASCADE,
  tenant_id   uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  on_date     date NOT NULL,
  cancelled   boolean NOT NULL DEFAULT true,
  note        text    NOT NULL DEFAULT '',       -- 「公众假期」「老师培训」
  PRIMARY KEY (schedule_id, on_date)
);
```

CMS 里就是课表行上的一个「本周停课」按钮。公开页把那一天标成**停课**并显示
原因，而不是让它消失——**消失看起来像网站坏了，标注停课看起来像有人在管**。

---

## 3. 循环规则要投影成真实日期，且必须用租户时区

门户要的是「未来的排课」，不是「每周几」。所以服务端把 weekday 向前投影
2–4 周，产出**具体日期**。

**时区必须用 `tenants.timezone`，且在服务端算。**
一间墨尔本画室的「周一 16:00」，对一个在别处打开页面的家长，在浏览器里算
会算错一天。这个产品在日期上已经栽过一次（接口日期是 RFC 1123，不是 ISO），
这条不重犯。

「今天」也在服务端按租户时区判定——否则午夜前后的访客会看到不同的首日。

---

## 4. 接口

```
GET /v1/public/<slug>/timetable?weeks=2
```

```jsonc
{
  "enabled": true,
  "timezone": "Australia/Melbourne",
  "showCapacity": true,
  "days": [
    { "date": "2026-08-10", "weekday": 1, "classes": [
      { "title": {"zh":"儿童油画基础","en":"Kids Oil Painting"},
        "subtitle": "周一班", "ageRange": "6-9",
        "teacher": "Lucy 老师",          // 省略即未公开
        "start": "16:00", "end": "17:00",
        "room": "A 教室",
        "capacity": 10, "seatsLeft": 3,  // showCapacity 关闭时两者都省略
        "cancelled": false, "note": "" }
    ]}
  ]
}
```

**只出现聚合数字，永远不出现学员姓名。** `seatsLeft = capacity - 已报人数`，
这是聚合值，不是个人信息；而 `class_schedule_students` 里的名字一个都不
往外送。

`showCapacity` 是 `website_profile` 上的一个开关：**一个班只剩 2 人时，
「还有 8 个位置」传达的不是稀缺，是冷清。** 让工作室自己决定要不要露。

与 `/showcase` 同构：独立接口、不进 `/brand`，开关在 `/brand`——
**所以又是 v8.5.3 那个竞态，同样从第一行就走 `state.sectionsOff`。**

---

## 5. 门户板块

位置：**课程之后，学员作品之前**。

> 课程说「你能学什么」→ **课表说「什么时候能来」** → 学员作品说「学成什么样」

课表是「课程」这句话的落地，紧跟着它才成立。

- 按**日期**分组，不按星期几——访客要的是「这周」。
- 每天一列 / 移动端一段；每节课一行：时间 · 课程名 · 老师 · 地点 · 余位。
- 停课的那一节保留位置，划掉并注明原因。
- 「预约体验」按钮就在旁边——**这是这个板块唯一的转化点，也是做它的理由**。
- 没有任何公开排课时整块隐藏。

---

## 6. 工程量

| 项 | 估时 |
|---|---|
| 迁移（3 列 + 例外表 + memberships 2 列） | 1h |
| CMS 课表编辑器：老师下拉、课程下拉、公开开关、地点、停课 | 5h |
| 团队管理：老师对外显示名 + 公开开关 | 1.5h |
| 公开接口 + 时区投影 | 3h |
| 门户板块 + 样式 + 竞态处理 | 3h |
| Studio Admin：板块开关、余位开关、板块标题 | 2h |
| 测试（时区、停课、不公开的课不出现、无姓名泄漏、竞态） | 3h |
| 文档 / 发布 | 2h |
| **合计** | **约 2.5 天** |

---

## 7. 两个小问题的难度（你说了可以搁置）

### 7.1 CMS 首屏一瞬间无色 —— **建议搁置**

原因是 accent 系列在 `/brand` 应答前未定义。真正的修法是**服务端在下发
CMS 外壳时就把该租户已解出的配色变量内联进去**（跟 `__APP_VERSION__` 一样
在服务时替换）。

技术上不难，**但它把一个可缓存的静态外壳变成按租户渲染的响应**——缓存策略
要跟着改。为了一次几十毫秒的闪动付这个代价不值。

你的判断是对的：**感官上确实还好，搁置。**

### 7.2 深色模式过暗 —— **建议做，很便宜**

实测当前值：

| 主题 | 纸 | 面板 |
|---|---|---|
| vintage-press | `#15120D` | `#2E271F` |
| custom | `#14120F` | `#2C2921` |
| studio-ink | `#121111` | `#282727` |

纸的感知明度 L\* 只有 **7 左右**——这不是「深色」，是接近纯黑。截图里那种
「过暗」是准确的感受，不是错觉。

修法是**改生成器里深色锚点的一个数字**（把纸抬到 L\* 12–14 左右，面板与
线条按现有关系自动跟着走），然后重新生成九套主题的深色。

**便宜的原因是：改完自动有 1080 条对比度断言重跑。** 不是靠眼睛确认。
估时 **半天**，含重新验证与截图对比。

建议：**这一条随课表那一版一起发**，不单独占一次发布。

---

## 8. 需要你拍板

1. **投影几周**？我建议 **2 周**（够家长安排，也不会让页面变成年历）。
2. **余位默认露不露**？我建议**默认不露**，工作室自己打开——理由见 §4。
3. **停课表要不要做**？我的立场是**必须做**（§2），否则这个功能会让家长
   白跑。如果你想砍掉，那我建议连公开课表一起先不做。
4. **深色变亮**要不要跟这版一起发？（我建议要，半天）
