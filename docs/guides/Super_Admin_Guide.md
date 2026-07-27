# 平台超管手册 · Super Admin

> 适用版本：StudioSaaS v7.7.8 · 界面：Super Admin 控制台（`/super-admin`）
> 其他角色手册见 [手册总览](README.md)

## 角色定位

Super Admin 是**平台方**（SaaS 运营者），不属于任何一家工作室。你负责：
开通/编辑/暂停/归档/删除租户（工作室）、维护套餐（Plans）与额度、查看
平台审计日志、以支持模式协助客户排障，以及数据库备份等运维工作。租户
内部的日常运营（学员、排课、财务）由各工作室自己的 Owner/Manager 负责——
你拥有技术上的完全访问权，但应只在支持场景下进入租户界面。

## 快速上手

1. 打开 `https://<平台域名>/super-admin`。
2. 在「Super Admin Login」输入邮箱、密码（可勾选「Remember me for 30 days」），
   点「Login」。**只有平台级 super_admin 账号**（不挂在任何租户下）能进入；
   其他账号会被登出并提示「Please log in with a Super Admin account.」。
3. 登录后顶部出现四个导航锚点：**Overview · Tenants · Plans · Audit Logs**，
   右上角有「Change Password」「Logout」「↻ Refresh」。
4. 界面语言：右上角有运行时注入的「中文 / English」切换（默认中文，记忆键
   `studiosaas_admin_language`，与 Studio Admin/CMS 共用）。**注意：无论界面
   什么语言，各种确认框都必须输入英文原文的 slug。**

## 一、Overview（商业总览）

八张 KPI 卡：Total Tenants、MRR (AUD)、Paid Tenants、Trial Tenants、
Onboarding、Past Due、Trials Ending in 7 Days、New in 30 Days。

- **Commercial Attention**：自动列出商业风险按钮，如
  「N · payment follow-up」「N · trials ending soon」
  「N · onboarding incomplete」。点任一按钮直接跳到 Tenants 列表并套用
  对应过滤。
- **30-Day Acquisition Funnel**：近 30 天报名转化一行汇总
  （报名数 · 转化数与转化率 · 来自官网 · 来自快速报名/投放）。

## 二、Tenants（租户管理）

### 列表与筛选

工具条：Search Tenants（按名称/slug/负责人邮箱等搜索）、Status 下拉
（lead / trial / onboarding / active / past_due / paused / cancelled /
archived）、Plan 下拉、Category 下拉、「Show test tenants」复选框（默认
隐藏测试租户）、「Clear Filters」。列表每页 10 条，底部「Previous / Next」。

表格 7 列：Studio（名称+slug+行业+管理员邮箱）、Plan、Status（状态 pill +
订阅状态 + 健康度徽标：Healthy / Needs setup / No admin login /
Payment issue / Paused / Archived）、Owner、Usage（学员数与存储用量/上限）、
Surfaces（Portal / CMS / Register / Admin 四个链接；归档或删除的租户链接
置灰。**Portal / Register 是公开页面直达链接；CMS / Admin 是租户内界面，
点击会先弹出支持模式对话框**，见下文第四节）、Actions（**View** 与
**More**）。

**View** 打开详情模态：状态摘要、Risk / Setup 风险清单（如
No owner assigned、Website not published、Storage near limit 等）、
6 项 Onboarding Checklist（Owner assigned → Studio Website published）、
学员/存储用量进度条、订阅期间、归档路径等。

### 开租户（+ Add Tenant）

1. Tenants 区块点「**+ Add Tenant**」。
2. 填写：
   - **Studio Name**（必填；Slug 由名称自动生成、只读，创建后不可改）;
   - **Plan**（下拉选套餐）;
   - **Studio Category**（行业预设，决定默认 slogan 与后续 Studio Admin 里的
     推荐文案/推荐主题；切换行业会覆盖已填的 Slogan）;
   - **Owner Name / Owner Email**;
   - **Temporary Admin Password**（至少 8 位，必填）——请通过安全渠道交给
     Owner，并要求首次登录后立即修改。
3. 点「Create Tenant」。系统自动填好：联系邮箱、账单邮箱、Studio Admin
   登录（= Owner 邮箱）、onboarding 状态、**30 天试用期**（状态
   onboarding + trialing）。
4. 建好后把 `/<slug>/studio-admin` 地址和临时密码交给 Owner，由 Owner 在
   Studio Admin 里完成品牌与主题配置——**开租户表单里没有主题选择**，
   主题在租户侧配置（行业预设只提供推荐）。

### 编辑租户（More → Edit Tenant）

折叠分区：Basic（名称/行业/套餐；Slug 与 Status 只读）、Owner & Contact
（含三个快捷按钮把 Owner 邮箱同步到联系/账单/登录邮箱）、Admin Login
（改登录邮箱、重置密码，或点「Generate link」生成**一次性 24 小时
密码设置链接**——生成新链接会作废旧链接）、Subscription（订阅起止日期、
账单邮箱）、Limits（学员/用户/存储上限**全部继承自套餐**、不可单独改）。

### 生命周期操作（More → Status / Danger Zone）

| 操作 | 按钮 | 确认要求 | 效果 |
|---|---|---|---|
| 暂停 | Pause | **输入完整 slug** | 状态与订阅都变 paused；公开页仍在，报名入口关闭 |
| 恢复运营 | Reactivate | **输入完整 slug** | 状态与订阅回 active |
| 归档 | Archive Tenant | **输入完整 slug** | 先写四份快照（数据库/工作区目录/媒体目录/订阅元数据）再关闭租户 API；成功提示会显示快照路径 |
| 从归档恢复 | Restore Tenant | 无确认框 | **恢复为 paused，不是 active**——还要再执行一次 Reactivate 才恢复运营 |
| 永久删除 | Permanent Delete | **输入 `DELETE <slug>`**（大小写敏感，前后端双重校验） | 仅归档后可用；删除在线记录，归档文件保留为审计证据，不可逆 |

> 确认输入不容错：必须与 slug 完全一致（英文原文），界面切换成中文也一样。

## 三、Plans（套餐管理）

表格列：Plan（名称 + code）、Price/Month（AUD）、Limits（学员/用户/存储 +
已启用权限）、Actions（Edit / Delete）。

- **Edit**：名称、月价、学员/用户/存储上限，及 5 个权限开关
  （Public registration、Student portfolio、Email templates、Data export、
  Priority support）+「Additional entitlements (JSON)」高级字段。
  **Code 创建后不可修改。**
- 套餐指派：在新建/编辑租户的 Plan 下拉里选；租户额度完全继承套餐。
- **已知限制**：「+ Add Plan」弹窗中 Code 字段是禁用且为空的，当前版本
  **无法通过 UI 新建带 code 的套餐**——新套餐请由后端/脚本预置，UI 只用于
  编辑现有套餐。另外「Delete Plan」只需一次点击确认（没有短语确认），
  删除前请自行核对没有租户还挂在该套餐上。

## 四、支持模式（Support Session）——租户访问的强制门槛

**平台 Super Admin 不能直接打开某个租户的 CMS 或 Studio Admin。**
任何租户内的接口在没有对应支持会话时都会返回 403：
「需要先开启支持模式（含原因）才能进入该工作室。 Start a support
session for this studio from the Super Admin console first.」
（错误码 `support_session_required`）。进入租户的唯一正规路径：

1. 租户行 → More → Support 分组 → 「**Enter Support Mode**」;
   或直接点 Surfaces 列的 **CMS / Admin** 快捷链接——这两个链接现在也会
   先弹出支持模式对话框（Portal / Register 是公开页面，仍是普通链接）。
2. 在「Reason」里填写客户请求或工单号（**必填**，会记入审计），点
   「Start Support Mode」。
3. 新标签页自动打开该租户的 Studio Admin，顶部出现琥珀色横幅
   「🛟 SUPPORT MODE — Acting inside <租户> — every action is audited.
   Reason: …」。
4. 办完点横幅右侧「Exit Support Mode」结束并跳回 Super Admin。

支持会话的规则：

- **按租户逐个开启**：会话只对开启时选定的那一家工作室有效；要看另一家，
  需要为那家再开一次（新会话替换旧会话）。
- **结束即关门**：Exit Support Mode（或会话被清除）后，再访问该租户的
  接口立刻回到 403。
- **全程留痕**：开启/结束分别写入 `support.session_started` /
  `support.session_ended` 审计事件（含 Reason）；期间的操作都记在该租户的
  审计日志里——租户 Owner 在自己的 Studio Admin「数据分析 → 操作审计」
  面板也能看到这些记录。
- 平台级路由（Overview / Tenants / Plans / Audit Logs 等 `/v1/admin/*`）
  不受影响，不需要支持会话。
- 运维应急开关：环境变量 `STUDIOSAAS_ENFORCE_SUPPORT_GATE=0` 可临时关闭
  强制门（仅限故障恢复场景，平时必须保持开启）。

## 五、Audit Logs（审计日志）

「Audit Logs」区块显示平台最近活动：Time / Tenant / Action / Resource
四列（如 `auth.login_failed`、`support.session_started`、租户状态变更等）。
当前版本无筛选、分页和导出；需要深入排查时直接查数据库 `audit_logs` 表。

## 六、备份与运维

**控制台里没有备份按钮**——备份走脚本（详见
[Admin_Guide](../Admin_Guide.md)），核心命令：

```bash
# 一键备份（试点期推荐每次公开测试前执行）
双击 BACKUP_STUDIOSAAS_NOW.command

# 或命令行：pg_dump 自定义格式 + 清单（保留最近 14 份）
cd backend && STUDIOSAAS_DATABASE_URL=... \
  ../.venv/bin/python scripts/backup_postgres.py backup --keep 14

# 恢复演练（在临时库中验证 dump 可用）
... scripts/backup_postgres.py restore-dry-run <dump>.dump

# 真实恢复（需要 --confirm <数据库名> 守护）
... scripts/backup_postgres.py restore <dump>.dump --confirm <database_name>
```

其他运维要点：

- 媒体文件与 legacy 数据（`STUDIOSAAS_MEDIA_DIR`、`CMS_DATA_DIR`）不在
  pg_dump 里，需要随数据库一起做文件级备份;
- 事件表清理建议每月跑
  `python backend/scripts/prune_event_tables.py --dry-run`（确认后去掉
  `--dry-run`）;
- 发布门槛验证：`STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`;
- 租户「Archive」操作本身就是一次完整快照（数据库 + 工作区 + 媒体 +
  订阅元数据），可作为下线前的最后留档;
- 头部「↻ Refresh」并发刷新 usage / plans / tenants / audit-logs 四个接口。

## 常见问题（FAQ）

**Q1：登录提示「Please log in with a Super Admin account.」？**
你的账号不是平台级 super_admin（挂在某个租户下的 super_admin 不算）。
用 `seed_super_admin.py` 种子的平台账号登录。

**Q2：Owner 忘了 Studio Admin 密码怎么办？**
More → Edit Tenant → Admin Login：直接在「Reset Password」设新密码，或点
「Generate link」生成一次性 24 小时密码设置链接发给对方（更安全）。

**Q3：租户想换套餐？**
Edit Tenant → Basic → Plan 下拉选择后 Save Changes。学员/用户/存储上限
随套餐自动变化。

**Q4：Archive 和 Permanent Delete 有什么区别？**
Archive 是可逆下线：先写四份快照，租户 API 关闭，之后可 Restore（恢复为
paused）。Permanent Delete 只对已归档租户可用，删除在线记录、不可逆，
但归档文件保留作审计证据。

**Q5：Restore 之后客户说还是用不了？**
Restore 只把租户从 archived 恢复到 **paused**。还需要 More → Status →
Reactivate（再输一次 slug）才回到 active。

**Q6：中文界面下确认框输入中文名可以吗？**
不行。确认输入必须是英文原文 slug（或 `DELETE <slug>`），大小写敏感。

**Q7：不开支持模式直接进租户后台会怎样？**
会被后端拒绝：租户内的所有接口返回 403 `support_session_required`
（「需要先开启支持模式（含原因）才能进入该工作室」）。这是 v7.7.7 起的
强制权限门，不再只是流程约束。从租户行的 Enter Support Mode（或 CMS /
Admin 快捷链接弹出的对话框）填写 Reason 开启会话后即可进入；会话只对
该租户有效，Exit 后访问权立即收回。

**Q8：客户会知道我进过他们的后台吗？**
会。支持会话的开启/结束和期间的操作都写入该租户的审计日志，租户 Owner
在 Studio Admin 的「数据分析 → 操作审计」面板可以看到（含你填写的
Reason）。这是产品的透明性承诺，请把 Reason 写得可以给客户看。

## 权限边界表（Super Admin）

| 功能 | Super Admin | 说明 |
|---|---|---|
| 开租户 / 编辑 / 生命周期 / 永久删除 | ✅ | 永久删除需先归档 + 短语确认 |
| 套餐编辑与指派 | ✅ | UI 暂不能新建带 code 的套餐 |
| 平台审计日志 | ✅ | 无筛选/导出 |
| 直接打开租户 Studio Admin / CMS | ❌ | 403 `support_session_required`——必须先开支持会话 |
| 支持模式进入租户 Studio Admin / CMS | ✅ | 必填 Reason、按租户逐个开启、全程审计 |
| 租户内所有 API（权限 `*`，支持会话内） | ✅ | 仅限支持场景使用；操作对租户 Owner 可见 |
| 数据库备份 / 恢复 | ✅（脚本） | 控制台无入口，见 Admin_Guide |
| 替租户日常运营 | ⚠️ 不建议 | 属 Owner/Manager 职责 |

---
相关手册：[Owner 手册](Studio_Owner_Guide.md) · [Manager 手册](CMS_Manager_Guide.md) · [Teacher 手册](Teacher_Guide.md) · [前台/员工手册](Front_Desk_Staff_Guide.md) · [学员/家长手册](Student_Parent_Guide.md) · [手册总览](README.md) · 角色权限矩阵见 [Admin_Guide](../Admin_Guide.md)
