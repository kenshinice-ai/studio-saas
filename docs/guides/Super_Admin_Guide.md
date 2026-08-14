# 平台超管手册 · Super Admin

> 适用版本：PWE Studio v10.1.1 · 界面：Super Admin 控制台（`/platform-admin`）
> 其他角色手册见 [手册总览](README.md)

## 角色定位

Super Admin 是**平台方**（SaaS 运营者），不属于任何一家工作室。你负责：
开通/编辑/暂停/归档/删除租户（工作室）、维护套餐（Plans）与额度、查看
平台审计日志、以支持模式协助客户排障，以及数据库备份等运维工作。租户
内部的日常运营（学员、排课、财务）由各工作室自己的 Owner/Manager 负责——
你拥有技术上的完全访问权，但应只在支持场景下进入租户界面。

## 快速上手

1. 直接使用系统登录时打开 `https://<平台域名>/platform-admin`。`/super-admin`
   保留为可由 Cloudflare Access 保护的双重验证别名；出现 Cloudflare 登录跳转
   表示请求尚未到达 StudioSaaS，不是系统自动换链接。
2. 在「Super Admin Login」输入邮箱、密码（可勾选「Remember me for 30 days」），
   点「Login」。**只有平台级 super_admin 账号**（不挂在任何租户下）能进入；
   其他账号会被登出并提示「Please log in with a Super Admin account.」。
3. 登录后顶部出现四个工作区入口：**Overview · Tenants · Plans · Audit Logs**；
   一次只显示当前工作区，地址仍可用 `#overview`、`#tenants`、`#plans`、`#audit`
   直达。右上角有「Change Password」「Logout」「↻ Refresh」，工作区状态栏会
   显示载入/就绪/部分载入、重试和最近刷新时间。
4. 界面语言：右上角有运行时注入的「中文 / English」切换（默认中文，记忆键
   `studiosaas_admin_language`，与 Studio Admin/CMS 共用）。**注意：无论界面
   什么语言，各种确认框都必须输入英文原文的 slug。**

## 一、Overview（商业总览）

八张 KPI 卡：Total Tenants、MRR (AUD)、Paid Tenants、Trial Tenants、
Onboarding、Subscription Past Due、Trials Ending in 7 Days、New in 30 Days。

**其中七张是筛选按钮（v8.2.11）。** 点任何一张（MRR 除外）会直接把下方
Tenants 列表筛成它统计的那批工作室，卡片上出现「Filtering 筛选中」标记，
列表顶部出现一枚可关闭的筛选条（「From overview 来自总览」）。**MRR 不是
按钮**——它是一个金额合计，点它没有任何一组行可以展示。

> **这里有个容易看错的地方。** 大多数计数器统计的是**订阅状态**
> （`subscriptions.status`），而工具条上的 Status 下拉筛的是**租户状态**
> （`tenants.status`）。两者共用 active / past_due / trial 这几个词。所以
> 「Paid Tenants 3」和 Status 下拉选 active 得到的**不是同一批**——本地实测
> 后者会列出 5 家。要看某张卡对应的确切名单，请点卡片本身，不要手动去下拉
> 里选一个看起来同名的值。

- **30-Day Acquisition Funnel**：近 30 天报名转化一行汇总
  （报名数 · 转化数与转化率 · 来自官网 · 来自快速报名/投放）。

> 旧版手册里的 **Commercial Attention** 卡片已在 v8.2.11 移除——它列的三个
> 数字与正上方的计数器完全重复，而计数器现在自己就是筛选入口。

## 二、Tenants（租户管理）

### 列表与筛选

工具条：Search Tenants（按名称/slug/负责人邮箱等搜索）、Status 下拉
（lead / trial / onboarding / active / past_due / paused / cancelled /
archived）、Plan 下拉、Category 下拉、「Show test tenants」复选框（默认
隐藏测试租户）、「Clear Filters」。列表每页 10 条，底部「Previous / Next」。

表格 7 列：Studio（名称+slug+行业+管理员邮箱）、Plan、Status（状态 pill +
订阅状态 + 健康度徽标：Healthy / Needs setup / No admin login /
Subscription past due / Paused / Archived）、Owner、Usage（学员数与存储用量/上限）、
Surfaces（Portal / CMS / Register / Admin 四个链接；归档或删除的租户链接
置灰。**Portal / Register 是公开页面直达链接；CMS / Admin 是租户内界面，
点击会先弹出支持模式对话框**，见下文第四节）、Actions（**View** 与
**More**）。

**View** 打开响应式详情抽屉（移动端占满屏幕）：状态摘要、Risk / Setup 风险清单（如
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

> **归档与永久删除到 v8.2.10 才真正可用。** 在此之前两者在生产环境
> **从未成功过一次**：归档目录所在的挂载卷不可写，接口直接返回服务器错误，
> 而永久删除又要求「必须先归档」，于是整条路径都走不通。现在归档会先写四份
> 快照再关闭租户，成功提示里会显示快照路径——**看到路径才算归档成功**，
> 请记下它。

## 三、Plans（套餐管理）

表格列：Plan（名称 + code）、Price/Month（AUD）、Limits（学员/用户/存储/公开作品 +
已启用权限）、Actions（Edit / Delete）。

表格现在多一列 **Public**，显示「Published 已发布 / Not published 未发布」，
主推套餐另带一枚「Recommended 主推」徽章。

- **Edit**：名称、月价、学员/用户/存储/公开作品上限，5 个权限开关
  （Public registration、Student portfolio、Email templates、Data export、
  Priority support）+「Additional entitlements (JSON)」高级字段，以及
  **Public pricing page 公开定价页**分组下的两个勾选：
  - **Publish on pwestudio.online 发布到 pwestudio.online**;
  - **Mark as the recommended plan 设为主推套餐**（勾上会自动清除其他套餐的
    主推标记——数据库上有唯一约束，主推只能有一个）。
  **Code 创建后不可修改。**
- **Save Plan** 会在发送请求前检查 Code、Name、月价和额度，并把错误显示在
  对应字段下方；不会只用短暂 toast 隐藏表单问题。
- **「+ Add Plan」现在可以填 Code 了**（旧手册写的「Code 字段禁用、无法通过
  UI 新建套餐」已过时）。
- 套餐指派：在新建/编辑租户的 Plan 下拉里选；租户额度完全继承套餐。

> **新建的套餐默认「不公开」（v8.2.20）。** 这是刻意的：在此之前
> `plans` 表里**每一行**都会自动出现在 `pwestudio.online` 的定价栏上，
> 一个为测试建的 A$1 套餐就这样进了公开定价页，还因为「主推」当时是按
> 中位价推断的，把主推徽章从 Studio 挤到了 Starter。现在「定义一个套餐」
> 和「决定卖它」是两个动作，后者要你主动勾。
>
> 改完记得去 `https://pwestudio.online/` 和 `/zh/` 各看一眼——那两页的价格
> 和额度就是从这张表直接渲染的，页面里没有任何写死的数字。

- 「Delete Plan」只需一次点击确认（没有短语确认），删除前请自行核对没有
  租户还挂在该套餐上。

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
   「Start Support Mode」。留空时不会发送请求，输入框会获得 `aria-invalid`
   和字段级错误提示并重新获得焦点；网络/权限错误会留在当前表单中。
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

**v8.2.11 起有了搜索和分页**（旧手册写的「无筛选、无分页」已过时）：

- 顶部搜索框「Filter by action, tenant, or resource...」按动作、工作室或
  对象过滤;
- 每页 15 条，底部 Previous / Next，页码与总数都会显示;
- 接口一次返回 100 条，页面不再把它们一次性铺开——这一页曾经是控制台里
  最长的一段。

仍然**没有导出**；需要更深的排查请直接查数据库 `audit_logs` 表。

> **保留期限：审计记录两年**（见下一节）。要留更久请定期导出。

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
- **事件表保留策略已经在跑（v8.2.12）**，不再是"建议每月手动执行"。
  `/etc/cron.d/pwestudio-prune` 每月 1 号 04:15 UTC 执行
  `bash deploy/aws/lightsail_ctl.sh prune`。默认保留窗口：

  | 表 | 保留 | 说明 |
  |---|---|---|
  | `audit_logs` | 730 天 | 上线 31 天时就已是最大的表（4,413 行） |
  | `public_analytics_events` | 365 天 | 官网匿名流量 |
  | `notification_logs` | 365 天 | 通知发送记录 |
  | `student_access_sessions` / `student_access_attempts` | 30 天 | 家长自助查询会话 |

  `student_publication_consent_events`（作品公开同意与撤回）**刻意不在清理
  范围内**——那是法律证据，永不删除。
  手动执行前先跑 `bash deploy/aws/lightsail_ctl.sh prune --dry-run` 看会删多少;
- 磁盘水位：`bash deploy/aws/pwestudio_remote.sh disk`（超过警戒线时非零退出）；
  部署会自己清理旧发布目录、旧镜像和构建缓存;
- 发布门槛验证：`STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh`;
- 租户「Archive」操作本身就是一次完整快照（数据库 + 工作区 + 媒体 +
  订阅元数据），可作为下线前的最后留档;
- 头部「↻ Refresh」并发刷新 usage / plans / tenants / audit-logs 四个接口。


## 更改工作室的公开地址 / Changing a studio's public address

工作室改了名字，网址不会跟着变——网址印在传单和二维码上，不能说换就换。需要改时由平台管理员操作：

1. 打开「工作室与订阅」，选中这家工作室，展开 **Basic**。
2. 点 **Change public address**。
3. 填新地址（小写字母、数字、连字符）。
4. **原样输入当前地址**确认。这一步确认的是「你知道在动哪一家」，不是「你会不会打字」。
5. 勾选「已通知这家工作室」，点「更改地址」。

改完之后：

- **旧地址永久 301 跳到新地址**，已经印出去的二维码不用换。
- 学员、课程、作品、排课、媒体文件完全不受影响；已登录的员工不会掉线。
- 搜索引擎需要几周时间更新；访客的语言偏好会重置一次。
- **这家工作室一年之内不能再改**。这是产品规则，界面里没有绕过的开关。

**地址永不回收。** 已经用过的地址——包括已删除工作室的——不能再分配给别人，
否则那家工作室印出去的二维码会把人导到别人的生意上。已删除工作室的旧地址返回 410。

## 常见问题（FAQ）

**Q1：登录提示「Please log in with a Super Admin account.」？**
你的账号不是平台级 super_admin（挂在某个租户下的 super_admin 不算）。
用 `seed_super_admin.py` 种子的平台账号登录。

**Q2：Owner 忘了 Studio Admin 密码怎么办？**
More → Edit Tenant → Admin Login：直接在「Reset Password」设新密码，或点
「Generate link」生成一次性 24 小时密码设置链接发给对方（更安全）。

**Q3：租户想换套餐？**
Edit Tenant → Basic → Plan 下拉选择后 Save Changes。学员/用户/存储/公开作品上限
随套餐自动变化；内置套餐的公开作品额度是 starter 15、studio 60、growth 150。

**Q4：Archive 和 Permanent Delete 有什么区别？**
Archive 是可逆下线：先写四份快照，租户 API 关闭，之后可 Restore（恢复为
paused）。Permanent Delete 只对已归档租户可用，删除在线记录、不可逆，
但归档文件保留作审计证据。

**Q5：Restore 之后客户说还是用不了？**
Restore 只把租户从 archived 恢复到 **paused**。还需要 More → Status →
Reactivate（再输一次 slug）才回到 active。

**Q6：中文界面下确认框输入中文名可以吗？**
不行。确认输入必须是英文原文 slug（或 `DELETE <slug>`），大小写敏感。

**Q6b：新建了套餐，为什么官网定价页上没有它？**
因为新套餐默认**不公开**（v8.2.20）。Plans → Edit → Public pricing page →
勾「Publish on pwestudio.online」。这是刻意的默认值：在此之前每一行套餐都
会自动上公开页，一个 A$1 的测试套餐就是这样进去的。

**Q6c：点了总览的计数卡，列出来的数量和卡上的数字对不上？**
如果你点的是卡片本身，两者一定一致。对不上通常是手动去 Status 下拉里选了
一个同名的值——那个下拉筛的是**租户状态**，而多数计数卡统计的是**订阅
状态**，两套状态共用同样的词。要看某张卡的确切名单，点卡片。

**Q6d：归档提示成功，但我不确定快照写了没有？**
成功提示里会带快照路径，**没有路径就不算成功**。归档在 v8.2.10 之前于
生产环境从未成功过一次（挂载卷不可写），所以这条提示值得每次都看一眼。

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
| 套餐新建 / 编辑 / 指派 / 发布 | ✅ | v8.2.20 起可从 UI 新建；发布到公开定价页是单独的勾选，默认关 |
| 平台审计日志 | ✅ | 有搜索与分页，仍无导出；保留 730 天 |
| 直接打开租户 Studio Admin / CMS | ❌ | 403 `support_session_required`——必须先开支持会话 |
| 支持模式进入租户 Studio Admin / CMS | ✅ | 必填 Reason、按租户逐个开启、全程审计 |
| 租户内所有 API（权限 `*`，支持会话内） | ✅ | 仅限支持场景使用；操作对租户 Owner 可见 |
| 数据库备份 / 恢复 | ✅（脚本） | 控制台无入口，见 Admin_Guide |
| 替租户日常运营 | ⚠️ 不建议 | 属 Owner/Manager 职责 |

---
相关手册：[Owner 手册](Studio_Owner_Guide.md) · [Manager 手册](CMS_Manager_Guide.md) · [Teacher 手册](Teacher_Guide.md) · [前台/员工手册](Front_Desk_Staff_Guide.md) · [学员/家长手册](Student_Parent_Guide.md) · [手册总览](README.md) · 角色权限矩阵见 [Admin_Guide](../Admin_Guide.md)
