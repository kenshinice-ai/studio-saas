# 工作室 Owner 手册（Studio Admin + CMS 全权限）

> 适用版本：StudioSaaS v8.0.1 · 界面：Studio Admin（`/<工作室网址标识>/studio-admin`）
> 与运营 CMS（`/<工作室网址标识>/cms`）
> 其他角色手册见 [手册总览](README.md)

## 角色定位

Owner 是租户（工作室）的最高负责人，拥有两个界面的全部权限：

- **Studio Admin**：管理对外形象——品牌与 Logo、配色主题、官网门户内容
  （主理人/课程板块标签/作品墙标签/FAQ/联系方式）、报名表自定义问题、
  家长话术模板、公开页面的发布。**只有 Owner（和平台 Super Admin）能登录
  这个界面**，Manager 会被拒绝。
- **运营 CMS**：日常运营的全部功能（等同 Manager，见
  [Manager 手册](CMS_Manager_Guide.md)），外加两项 Owner 专属能力：
  **团队成员管理**（新增/停用/改角色）和作为财务最终责任人的退款审批。

日常运营建议交给 Manager/前台，Owner 重点看：品牌与官网、团队账号、
经营统计和退款。

## 快速上手

1. 平台方（Super Admin）开通租户时会给你 Owner 邮箱和初始密码。
2. 打开 `https://<你的域名>/<工作室网址标识>/studio-admin`，在
   「Studio Admin Login」输入邮箱密码登录（可勾选「Remember me for 30 days」）。
   登录后立即点「Change Password」改掉初始密码（新密码至少 8 位）。
3. 顶部导航：**Website / Brand**（品牌工作台）、**Published Pages**
   （已发布页面）、**Quick Registration Form**（报名表）、**Open CMS**。
4. 界面右上角有「中文 / English」切换（记忆在本浏览器，存储键
   `studiosaas_admin_language`，与 CMS、Super Admin 共用）。它只改管理界面
   语言；预览区里另有一组「中文 / EN」按钮，那个切换的是**访客视角**的
   预览语言，两者互不影响。

> 如果用 Manager 账号登录 Studio Admin，会提示
> 「Studio Admin requires the owner role for <slug>. Open Studio CMS for
> operational access.」——品牌与公开内容是 Owner 边界。

## 一、品牌工作台（Website / Brand）

工作台分左右两栏：左侧是 8 个设置标签页，右侧是实时预览（可切换
Studio Website / Quick Registration 两种页面、中文/EN、Desktop/Mobile）。
底部常驻保存条：**Apply Category Preset · Open Website · Save Draft ·
Publish**，并显示「No unsaved changes / Unsaved changes / Draft saved —
not public」状态。

**草稿与发布是分开的**：Save Draft 只保存草稿，公开页面不变；Publish 才会
把内容推送到门户、报名页和 CMS。改错了不要慌——发布前一切都只在草稿里。

### 1. Brand（品牌基础，三步）

- **01 选择行业预设**：点行业卡片会把该行业的推荐文案、报名问题、FAQ 和
  推荐主题一次性应用到草稿（有「Undo」条可撤销）。已精心填写过内容后慎点，
  它会覆盖 slogan、首屏文案、报名问题和 FAQ。
- **02 选择配色主题**：见下文「主题系统」。
- **03 工作室信息**：Studio Name（发布必填）、Slogan 中/英、Logo URL 或
  「Upload Logo」直接上传、CMS Layout、Show Welcome、时区、电话/邮箱/地址、
  欢迎语中/英（「填一种语言就对所有人显示；两种都留空则隐藏欢迎横幅」）。
  **Plan（套餐）是灰色不可改的**——由平台 Super Admin 管理。

> **行内报错（v7.7.7）**：保存/发布时表单会逐字段校验并把错误显示在
> 对应输入框下方（红框 + 红字），不再只弹一条汇总提示。校验规则：
> Studio Name 必填；邮箱、电话、Logo URL（`/路径` 或 `https://` 地址）、
> 时区（IANA 名称如 `Australia/Melbourne`）、所有颜色（`#RRGGBB`）格式
> 必须正确。有错误时界面会自动跳回 Brand 标签页、展开相关折叠区并聚焦
> 第一个出错字段；开始输入即清除该字段的报错。

### 2. Hero（首屏）

首屏眉题、标题中/英、副标题中/英、首屏图片（URL 或上传，仅 JPEG/PNG/WebP，
公开发布前会去除元数据）、Hero Style（Soft Art Board / Image Background /
Minimal / Bold Contrast）、主按钮文字中/英（默认「预约体验 / Book a Trial」）、
次按钮文字中/英、学员登录链接显示开关。

### 3. Website（官网板块）

- 六个板块开关（Show/Hide）：主理人、课程、作品墙、FAQ、联系方式、学员专区。
  **没写内容的板块即使开着也不会显示空壳**。
- 板块标题中/英：课程、作品墙、FAQ、联系方式四组标签。作品墙标签里的
  `%WORK%` / `%WORKS%` 占位符会按行业自动替换成「作品/曲目/练习」等词。
- 主理人：姓名（人名不翻译）、头衔中/英、照片、语录中/英、简介中/英。
  **简介为空时整个主理人板块和导航链接都会隐藏。**
- 界面上有明确提示：**「课程名与作品标题来自 CMS，按员工录入原样显示，
  不随访客语言切换；只有这里的板块标题才是双语的。」**——课程数据本身
  （名称/描述/分类）在 CMS 维护，不在 Studio Admin。

### 4. Registration（报名表）

- 门户标签、报名标题中/英、报名引导语中/英。
- **自定义问题**：点「Add Question」新增，每题可填英文/中文标签、英文/中文
  占位提示、类型（text 短文本 / textarea 长文本 / select 下拉，下拉选项用
  逗号分隔填写）、Optional/Required。至少保留 1 题；英文标签留空的题保存时
  会被丢弃。题目顺序即添加顺序（没有拖拽排序）。门户报名表最多渲染 8 个
  自定义问题。
- 这些问题同时出现在门户报名表和独立报名页，提交后进入 CMS 的「待审核」。

### 5. FAQ

「Add FAQ」添加问答，每条有问题中/英、答案中/英和「Remove」。最多 6 条、
至少 1 条；只填一种语言时另一种语言自动沿用。

### 6. Messages（家长话术）

CMS 里员工一键复制发给家长的五种话术模板：签到、课时用完、购课成功、
续课提醒、生日祝福。占位符 `{student} {studio} {balance} {credits} {fee}
{note}` 会按学员自动填充。「Reset to defaults」可恢复默认模板。

### 7. Analytics（数据分析）

**官网数据**：匿名聚合的官网流量与转化——页面浏览、匿名会话、CTA 点击、
报名提交，可选 7/30/90 天，并有 Campaign（UTM）汇总。不存姓名、联系
方式、IP。这是官网访客数据；经营/财务统计在 CMS 的「经营统计」。

**操作审计（Audit Trail）——Owner 专属**：同一标签页下方的审计面板，
展示本工作室最近的操作记录：时间 / 操作人（邮箱）/ 动作 / 资源四列，
默认最近 50 条，顶部可按动作关键词过滤（如输入 `refund`、`export`、
`share`、`support`），点「Refresh」刷新。数据来自
`GET /s/<slug>/v1/audit-logs`，**仅 Owner 可读**（Manager 及其他角色
调用会被拒绝；平台 Super Admin 需处于支持模式）。典型用法：

- 复核**退款**：谁在什么时候给哪个学员办了退款退课;
- 复核**数据导出**：学员 CSV / 日志 CSV 何时被谁导出过;
- 复核**作品分享链接**：员工何时为哪个学员创建了对外链接
  （`portfolio.share_link_created`）;
- 查看平台方的**支持会话**：`support.session_started` /
  `support.session_ended`（含平台方填写的原因）——平台 Super Admin 只有
  开启支持模式才能进入你的工作室，进出都会记录在这里。

### 8. Preview / Publish（预览与发布）

- 四个入口卡片：Open Website / Open Quick Registration / Open CMS /
  Open Studio Admin。
- **Publication history 发布历史**：每次 Publish 生成一个版本，可
  「Restore to Draft」把旧版本恢复到草稿、预览确认后再发布——这就是回滚。

### 发布的质量门槛

点 Publish 时系统会检查并拦截：

1. Studio Name 必填;
2. 公开内容完整性：首屏标题、报名标题、报名引导语、电话或邮箱、（开启
   主理人板块时）主理人姓名——缺什么提示什么；占位文案（如「主理人姓名」）
   也会被拒绝;
3. **对比度门槛**：正文/次要文字/按钮文字共六项对比度必须 ≥ 4.5:1，
   不达标会列出具体项并阻止发布。

发布成功提示「Version n published to Portal, Quick Register, and CMS.」

## 二、主题系统（8 套主题 × 明暗）

- **Theme** 下拉：8 套专业配色主题（陶土工坊、复古印刷、黑白纸墨、静谧海港、
  雪松林、独奏紫、排练玫瑰、街机青柠），排序为「行业推荐 → 明暗双模 →
  仅单模式」，推荐主题带「— Recommended / 推荐」后缀。
- **Appearance**：Light / Dark。明暗是成对设计、都过了对比度校验；个别主题
  只提供一种模式（如街机青柠仅暗色），不提供的模式会置灰并标注
  「(not offered) / 此主题不提供」。
- 选择主题下方有预览卡：主题名、推荐/已选择/自定义徽章、色相关系、以及
  9 个色板（页面/面板/强调色/辅助色/控件边界/聚焦环/成功/警示/危险）。
- **Fine-tune selected theme（微调）**：主品牌色、辅助色、按钮风格
  （Soft/Sharp/Rounded）、字体气质，以及高级颜色（页面背景/面板背景/文字/
  次要文字/边框）。动过任何颜色后主题变为「Custom 自定义」；按钮文字和
  状态色始终由系统自动配到可读对比度。
- 切换主题立即生效在草稿和预览上，「发布前不会影响公开页面」。

## 三、隐私声明版本

访客在报名时必须勾选隐私同意，系统会把**当时生效的隐私声明版本号**
（门户「隐私说明」页底部的「本说明版本：…」）与同意记录一起存档；作品
公开授权同样记录版本。该版本号由系统随品牌接口（`/brand`）下发，
**目前 Studio Admin 界面中没有编辑隐私声明版本的入口**——需要变更声明
文本或版本时，请联系平台方处理。

## 四、CMS 里的 Owner 专属功能

CMS 的日常操作（排课签到、学员档案、充值退款、报名审批、经营统计）与
Manager 完全相同，请直接看 [Manager 手册](CMS_Manager_Guide.md)。以下是
只有 Owner 能做的：

### 团队成员管理（系统设置 → 团队与权限）

1. 在 CMS 点侧栏齿轮打开「系统设置」。
2. 「团队与权限」区显示所有成员（姓名、邮箱、角色、状态）。角色分工提示：
   「Owner管理团队；Manager负责日常运营，Teacher负责签到与作品，Front Desk
   负责报名、学员与课时。」
3. **添加成员**：填姓名、邮箱、角色（Manager / Teacher / Front Desk /
   Staff (legacy)）、临时密码（至少 8 位），点「添加团队成员」。**请通过
   安全渠道把临时密码发给对方**，并让对方首次登录后立即改密码。
4. **停用/启用**：每个非 Owner 成员右侧有「停用」「启用」按钮。停用后该
   账号立即无法登录。
5. 成员数量受套餐上限约束，达到上限时无法再添加（需平台方升级套餐）。
6. Owner 自己的角色不能被降级或停用；也不能通过此界面新增第二个 Owner。

### 财务边界

- **退款退课**（credits:refund）：充值结算页的「退款退课」模式，仅
  Owner/Manager 可见。流程见 Manager 手册第五节。
- **经营统计 / 经营真账**（analytics:read）：Owner/Manager 可见全部财务
  字段；Teacher/Front Desk 的账号连数据都不会下发。
- **作品分享链接**（portfolio:share）：**创建**仅 Owner/Manager——链接是
  对外可访问的学员作品页，有效期 1–90 天（默认 30 天），原始链接只显示
  一次。**撤销**已有链接放得更宽（任何能编辑作品集的角色，含 Teacher/
  Staff），以便随时切断外泄的链接。每次创建都会写入操作审计
  （`portfolio.share_link_created`）。
- CMS 系统设置顶部的「网站、Logo、配色与注册表设置 →」链接（跳转
  Studio Admin）只有 Owner 能看到。

## 常见问题（FAQ）

**Q1：点了 Save Draft 网站怎么没变？**
Save Draft 只存草稿，官网不变。确认无误后点 Publish 才会发布。

**Q2：发布被「Improve colour contrast before publishing」拦住了？**
你微调的颜色对比度低于 4.5:1。改回推荐主题，或在「Fine-tune」里调整
文字/背景色直到警告消失。

**Q3：发布错了怎么回滚？**
Preview / Publish 标签页 → Publication history → 在想恢复的版本上点
「Restore to Draft」→ 预览确认 → Publish。

**Q4：想换套餐 / 升级成员上限？**
Plan 字段由平台 Super Admin 管理，Owner 界面里是只读的。联系平台方。

**Q5：Manager 说他登录不了 Studio Admin？**
正常。品牌、配色、门户内容、报名表是 Owner 边界，Manager 请用 CMS。

**Q6：怎么给课程加英文名？**
不支持。课程名/描述与作品标题是 CMS 运营数据，只存单语、按录入原样显示
（产品决策，见 `docs/Glossary.md`）。板块标题（如「课程与班次 / Courses &
Classes」）才是双语的，在 Website 标签页设置。

**Q7：应用行业预设后我的文案被覆盖了！**
预设会覆盖 slogan、首屏、报名问题和 FAQ。立即点出现的「Undo」条可以
恢复；如果已经离开，用 Publication history 恢复上一个发布版本（未发布过
的草稿改动无法找回）。

**Q8：换了 Logo/图片，网站上还是旧的？**
上传成功后还需要 Save Draft / Publish；浏览器也可能有缓存，强制刷新
（Shift+刷新）再看。

**Q9：保存时输入框下面出现红字报错？**
v7.7.7 起表单错误直接标在出错字段下方：Studio Name 必填，邮箱/电话/
Logo URL/时区/颜色要符合格式（提示里写明了期望格式）。按提示改完，
输入时红字自动消失，再保存即可。

**Q10：怎么知道员工有没有动过退款、导出、分享链接？**
Studio Admin →「数据分析」→ 操作审计（Audit Trail）面板。按动作关键词
过滤（`refund` / `export` / `share`），每条记录有时间、操作人邮箱和
资源。这个面板只有 Owner 能看。

**Q11：平台方（Super Admin）能随便进我的后台吗？**
不能。平台超管必须先开启「支持模式」并填写原因才能进入你的工作室，
否则接口直接拒绝（403）。支持会话的开始/结束和期间操作都会记录在你的
操作审计里（`support.session_started` 含原因），你可以随时复核。

**Q12：作品分享链接和访问码有什么区别？**
访问码是家长长期自助查询的凭证（6 位数字，姓名+手机号+访问码登录）；
分享链接是临时的对外展示页（如发给亲友、用于招生），有效期 1–90 天、
到期自动失效、可随时撤销。创建分享链接仅 Owner/Manager。

## 权限边界表（Owner）

| 功能 | Owner | 说明 |
|---|---|---|
| Studio Admin 登录 | ✅ | 仅 Owner 与平台 Super Admin |
| 品牌 / 主题 / 门户内容 / 报名表 / 发布 | ✅ | tenant:update + settings:write |
| CMS 全部日常运营 | ✅ | 与 Manager 相同 |
| 退款退课 | ✅ | credits:refund |
| 经营统计（含财务） | ✅ | analytics:read |
| 作品分享链接 | ✅ | portfolio:share |
| 团队成员新增 / 停用 / 改角色 | ✅ | **仅 Owner** |
| 数据导出（学员 CSV、日志 CSV） | ✅ | data:export |
| 本工作室操作审计（Audit Trail） | ✅ | **仅 Owner**——Studio Admin「数据分析」标签页 |
| 修改自己的套餐（Plan） | ❌ | 由平台 Super Admin 管理 |
| 开新租户 / 租户生命周期 | ❌ | 平台 Super Admin 专属 |
| 平台级审计日志（跨租户） | ❌ | 平台 Super Admin 专属；本店记录看上面的操作审计 |

---
相关手册：[Manager 手册](CMS_Manager_Guide.md) · [Teacher 手册](Teacher_Guide.md) · [前台/员工手册](Front_Desk_Staff_Guide.md) · [Super Admin 手册](Super_Admin_Guide.md) · [学员/家长手册](Student_Parent_Guide.md) · [手册总览](README.md) · 角色权限矩阵见 [Admin_Guide](../Admin_Guide.md)
