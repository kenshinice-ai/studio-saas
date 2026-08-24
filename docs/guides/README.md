# StudioSaaS 使用手册总览

> 适用版本：PWE Studio v10.14.0 · 最后更新：2026-08-16
> 本目录是按角色划分的最终用户手册。开发/运维文档见 `docs/` 上层
> （[Architecture](../Architecture.md) · [Admin_Guide](../Admin_Guide.md) ·
> [Glossary](../Glossary.md)）。

## 一、六个界面

StudioSaaS 是多租户教培工作室 SaaS。每个工作室（租户）有独立的网址标识
（slug），系统共有六个界面：

| 界面 | 地址 | 给谁用 | 干什么 |
|---|---|---|---|
| **Super Admin** 平台管理 | `/platform-admin` | 平台方 | 开租户、套餐、生命周期、支持会话 |
| **Studio Admin** 工作室管理 | `/<slug>/studio-admin` | 租户 Owner | 品牌、配色主题、官网内容、报名表、家长话术、发布 |
| **CMS** 运营后台 | `/<slug>/cms` | 工作室员工 | 学员、排课、签到、课时、作品、报名审批 |
| **Timetable** 公开课表 | `/<slug>/timetable` | 访客 / 学员家长 | 浏览近期公开班次，并在开启后提交约课申请 |
| **Portal** 官网门户 | `/<slug>` | 访客 / 学员家长 | 浏览、在线报名、访问码自助查询 |
| **Register** 快速报名页 | `/<slug>/register` | 访客 | 独立的报名表单页（可单独转发） |

## 二、角色一览表

| 角色 | 登录界面 | 核心职责 | 手册 |
|---|---|---|---|
| **Super Admin** 平台超管 | Super Admin | 平台运营：租户/套餐/生命周期/审计/备份 | [Super_Admin_Guide.md](Super_Admin_Guide.md) |
| **Owner** 工作室主理人 | Studio Admin + CMS | 品牌与官网发布、团队账号、财务终审；CMS 全权限 | [Studio_Owner_Guide.md](Studio_Owner_Guide.md) |
| **Manager** 店长 | CMS | 日常运营全流程：档案/排课/签到/充值/退款/审批/统计 | [CMS_Manager_Guide.md](CMS_Manager_Guide.md) |
| **Teacher** 任课老师 | CMS | 当日排课与签到、学员作品集 | [Teacher_Guide.md](Teacher_Guide.md) |
| **Front Desk** 前台 | CMS | 报名审批、约课请求查看、建档、充值、访问码发放（不能签到、无财务报表） | [Front_Desk_Staff_Guide.md](Front_Desk_Staff_Guide.md) |
| **Staff**（legacy 通用员工） | CMS | 接近 Manager 但无退款/分享链接/统计/导出 | [Front_Desk_Staff_Guide.md](Front_Desk_Staff_Guide.md) |
| **学员 / 家长** | 不登录（访问码） | 浏览官网、在线报名、自助查询课时与作品 | [Student_Parent_Guide.md](Student_Parent_Guide.md) |

> **家长（parent）身份不能登录 CMS**：即使有账号，登录会被拒绝并提示
> 「家庭自助登录暂未开放，请联系工作室」。家庭自助查询走门户「学员专区」
> 的访问码方式。

## 三、权限矩阵（后端强制执行）

| 权限 | Owner | Manager | Teacher | Front Desk | Staff |
|---|---|---|---|---|---|
| 学员查看 students:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| 学员建档/编辑 students:write | ✅ | ✅ | ❌ | ✅ | ❌ |
| 课程与课包维护 courses:write | ✅ | ✅ | ❌ | ❌ | ❌ |
| 课时查看 credits:read | ✅ | ✅ | ❌ | ✅ | ❌ |
| 充值 credits:write | ✅ | ✅ | ❌ | ✅ | ❌ |
| **退款 credits:refund** | ✅ | ✅ | ❌ | ❌ | ❌ |
| 课表查看 scheduling:read | ✅ | ✅ | ✅ | ✅ | ✅ |
| 排课 scheduling:write | ✅ | ✅ | ❌ | ✅ | ❌ |
| **请假规则 scheduling:policy:write** | ✅ | ✅ | ❌ | ❌ | ❌ |
| 签到 attendance:write | ✅ | ✅ | ✅ | ✅ | ✅ |
| 作品查看 portfolio:read | ✅ | ✅ | ✅ | ❌ | ✅ |
| 作品集编辑 portfolio:write | ✅ | ✅ | ✅ | ❌ | ✅ |
| **作品分享 portfolio:share** | ✅ | ✅ | ❌ | ❌ | ❌ |
| 报名审批 registrations:write | ✅ | ✅ | ❌ | ✅ | ❌ |
| **约课请求审核 class_bookings:review** | ✅ | ✅ | ❌ | ✅ | ❌ |
| 账单查看 billing:read | ✅ | ✅ | ❌ | ✅ | ❌ |
| 开票 billing:write / billing:issue | ✅ | ✅ | ❌ | ✅ | ❌ |
| 登记收款 payments:write | ✅ | ✅ | ❌ | ✅ | ❌ |
| **退款 payments:refund** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **老师课酬 payroll:read / payroll:write** | ✅ | ✅ | ❌ | ❌ | ❌ |
| 本人课时与金额 payroll:self:read | ❌ | ❌ | ✅ | ❌ | ❌ |
| **经营报表 reports:read** | ✅ | ✅ | ❌ | ❌ | ❌ |
| **接入 Xero / 支付 integrations:manage** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **经营统计 analytics:read** | ✅ | ✅ | ❌ | ❌ | ❌ |
| 数据导出 data:export | ✅ | ✅ | ❌ | ❌ | ❌ |
| 品牌/官网 settings:write | ✅ | ❌ | ❌ | ❌ | ❌ |
| 团队成员管理 | ✅ | 仅查看 | ❌ | ❌ | ❌ |

> 本表逐行核对自后端 `backend/studiosaas/auth.py` 的 `ROLE_PERMISSIONS`，
> 不是界面观察的结果——界面藏起来的按钮和后端拒绝的请求是两回事，本产品
> 用的是后者。**前台（Front Desk）连作品都读不到**（没有 `portfolio:read`），
> 不只是不能编辑。
>
> **v10.13 起的三处改动**：
> 1. **前台可以签到**。它一直就能通过课时台账直接扣课时（`credits:write`），
>    只是那条路不写考勤行、也不记是为哪一节课扣的。给它 `attendance:write`
>    不是放宽，是把同一个动作挪到记得清楚的那条路上。退款（`credits:refund`
>    / `payments:refund`）仍然不给。
> 2. **Staff 重新定义为「助教 Assistant」= Teacher 减去署名权**，即
>    `ROLE_PERMISSIONS[STAFF] ⊂ ROLE_PERMISSIONS[TEACHER]`（有测试锁着）。
>    以前的 staff 和 teacher 在**两个方向**上都不一样：它能改学员档案、能
>    充值扣课时、能通过 `billing:read` 看到工作室的收款账户，却看不到自己
>    正在协助的课表。助教与老师的差别只剩两把钥匙：不写学习报告
>    （`progress_reports:write`）、没有本人课酬（`payroll:self:read`）。
> 3. **请假规则从 `scheduling:write` 里拆了出来**（`scheduling:policy:write`，
>    仅 Owner / Manager）。排一节课和改写「临时请假老师照不照付课酬」不是同
>    一种权限：后者决定课酬与家长账单。前台一直持有 `scheduling:write`，
>    只是 v10.13 之前它没有任何一页能走到那张表单——边界是靠导航守的，不是
>    靠权限。这一版给了前台课程安排页，于是必须把它改成靠权限。

（Super Admin 拥有全部权限 `*`，但 v7.7.7 起进入任一租户的 CMS/Studio
Admin **必须先在 Super Admin 控制台开启支持模式**（填写原因、全程审计），
否则接口返回 403 `support_session_required`。credits:refund 与
portfolio:share 是 v7.4.0 新增的独立权限，仅 Owner/Manager；分享链接的
**撤销**走 portfolio:write，Teacher/Staff 也可以撤。学员专区访问码的
生成/更换/停用属于学员资料维护（students:write）——**前台可以发放**。
Owner 另有专属的「操作审计」面板：Studio Admin → 数据分析。）

> 历史说明（v8.10.3）曾写：**没有修改 CMS**：约课卡片的批准/婉拒按钮仍只对 Owner/Manager 显示。
> v9.3.0 已完成对应 CMS 入口：Front Desk 可以在「待处理 → 约课」审核请求，
> 但课程、容量与时间表维护仍只属于 Owner/Manager。

对应 CMS 导航标签页：

> v9.3.0 信息架构：导航按「今日 / 教学运营 / 经营 / 记录」分组；课程目录、
> 套餐管理和作品入口分别归属课程、充值与退款、作品工作区。设置只保留账号、
> 团队、运营默认和数据维护。下面的旧标签名称仍保留在历史说明中，便于老员工
> 对照；实际界面以当前分组名称为准。
>
> v10.1.1 起，侧栏与页面标题用同一个名字（`cmsPageTitle` 由 `NAV` 推导）。
> 在此之前两处各写一份，于是同一个页面在侧栏叫「课程」、在标题里叫
> 「课程目录」。当前名称是：课程目录、学员档案、作品管理、账单发票、
> 课酬与报表。

| 标签页 | Owner/Manager | Teacher | Front Desk | Staff |
|---|---|---|---|---|
| 工作台 | ✅ | ✅ | ✅ | ✅ |
| 课程安排 | ✅ | ✅ | ❌ | ✅ |
| 课程目录 | ✅ | ✅ | ❌ | ✅ |
| 课程 | ✅ | ✅ | ❌ | ✅ |
| 学员档案 | ✅ | ✅（只读+作品） | ✅ | ✅ |
| 学员 | ✅ | ✅（只读+作品） | ✅ | ✅ |
| 作品管理 | ✅ | ✅ | ❌ | ✅ |
| 作品 | ✅ | ✅ | ❌ | ✅ |
| 待审核 | ✅ | ❌ | ✅ | ✅ |
| 待处理 | ✅ | ❌ | ✅ | ✅ |
| 账单发票 | ✅ | ❌ | ✅ | ✅ |
| 账单 | ✅ | ❌ | ✅ | ✅ |
| 充值结算 | ✅ | ❌ | ✅ | ✅ |
| 课酬与报表 | ✅ | ❌ | ❌ | ❌ |
| 财务（课酬与报表） | ✅ | ❌ | ❌ | ❌ |
| 充值与退款 | ✅ | ❌ | ✅ | ✅ |
| 操作日志 | ✅ | ✅ | ✅ | ✅ |
| 经营统计 | ✅ | ❌ | ❌ | ❌ |

## 三点五、v8.1.0 之后变了什么（手册使用者请先看这段）

如果你手上是 v8.1.0 的旧版手册或打印件，以下几处已经不同：

| 变更 | 影响哪本手册 |
|---|---|
| **操作日志补全**（v8.2.3）：30 类操作全部有中文名称与可读摘要，不再出现 uuid 串 | Manager · Teacher · 前台 |
| **图片上传修复**（v8.2.6）：此前生产环境所有上传都失败；现已恢复，单张超过 3000 万像素会被拒绝 | Owner · Manager · Teacher |
| **主题状态色按主题求解**（v8.2.7–9）：主题预览的色板拆成「主题色 6 个」+「状态色 3 个 · 已按本主题调校」两组 | Owner |
| **工作室归档 / 永久删除可用**（v8.2.10）：此前在生产环境从未成功过 | Super Admin |
| **平台控制台重排**（v8.2.11）：总览计数器变成筛选按钮，`Commercial Attention` 卡片已移除 | Super Admin |
| **审计日志加了搜索与分页**（v8.2.11–12）：旧手册写的「无筛选、无分页」已过时 | Super Admin |
| **数据保留策略上线**（v8.2.12）：审计 730 天、分析 365 天、通知 365 天、访问会话 30 天，每月自动执行 | Super Admin |
| **套餐要显式发布**（v8.2.20）：新建套餐默认**不**出现在公开定价页，需在控制台勾选 | Super Admin |
| **产品官网重做 + 语言拆分**（v8.2.20）：`pwestudio.online/` 英文、`/zh/` 中文。这是平台自己的官网，与工作室门户无关 | — |
| **公开课表与约课队列**（v8.10.0–3）：Front Desk 的约课审核后端权限已独立；CMS 操作按钮留给单独的谨慎改造任务 | Owner · Manager · 前台 |

## 四、通用概念

- **租户（工作室）**：一家入驻的教培机构。数据完全隔离；网址标识（slug）
  创建后不可更改。生命周期状态：lead → trial/onboarding → active →
  （past_due / paused / cancelled）→ archived → deleted。
- **课时（credit）**：预付的教学时间单位。充值购入、签到扣减、可退款；
  一节课可能扣多于 1 个课时，所以对家长显示的是「剩余课时」而非
  「还能上几节」。「课包」是课时的售卖组合；「套餐（plan）」一词专指
  SaaS 订阅档位（术语规范见 [Glossary](../Glossary.md)）。
- **访问码**：学员/家长的自助查询凭证——6 位数字，由工作室在 CMS 里生成
  后当面交给家长。查询=学员姓名 + 登记手机号 + 访问码，**没有账号密码**。
  明文只在生成时显示一次；可随时更换或停用。
- **草稿 vs 发布**：Studio Admin 里 Save Draft 只存草稿，Publish 才更新
  公开页面，且每次发布留版本可回滚。
- **双语切换**：
  - 员工端（Super Admin / Studio Admin / CMS）：右上角「中文/English」，
    整个浏览器一份记忆（`studiosaas_admin_language`），默认中文;
  - 访客端（Portal / Register）：「中 / EN」按钮，按工作室分别记忆
    （`pwe_lang_<slug>`），首次跟随浏览器语言，可用 `?lang=en` 分享;
  - **课程名、作品标题、地址、电话、人名不翻译**——运营数据按录入原样
    显示，这是产品决策而非缺陷。
- **公开授权（publication consent）**：学员作品默认私密；只有家长/本人
  签署公开授权后作品才能上官网作品墙，且可随时撤回。报名时的隐私同意
  会连同当时的隐私声明版本号一起存档。

## 五、快速找答案

- 想改官网颜色/文案/报名问题 → [Owner 手册](Studio_Owner_Guide.md)
- 想办充值、退款、审批报名 → [Manager 手册](CMS_Manager_Guide.md)
- 前台审批报名、查看约课请求、发访问码、看到「疑似重复」角标 →
  [前台/员工手册](Front_Desk_Staff_Guide.md)
- 想给学员签到、传作品 → [Teacher 手册](Teacher_Guide.md)
- 家长问「还剩几节课怎么查」 → [学员/家长手册](Student_Parent_Guide.md)
- 要开新工作室、暂停租户、支持模式、备份 → [Super Admin 手册](Super_Admin_Guide.md)
- 想复核员工的退款/导出/分享链接操作 → [Owner 手册](Studio_Owner_Guide.md)
  「数据分析 → 操作审计」
- 开发者视角的权限矩阵与运维文档 → [Admin_Guide](../Admin_Guide.md)
