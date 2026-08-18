/* Chinese/English UI switch shared by Studio Admin and Super Admin.
 * Business values and API enums stay in English; only user-facing copy changes.
 */
(function () {
  'use strict';

  const zh = Object.fromEntries([
    ['PWE Studio · Super Admin', 'PWE Studio · 平台管理'],
    ['Studio Admin', '工作室管理'],
    ['Super Admin Login', '平台管理员登录'], ['Studio Admin Login', '工作室管理员登录'],
    ['Super Admin', '平台管理'], ['Studio Admin', '工作室管理'],
    ['Super Admin sections', '平台管理页面'], ['Studio Admin sections', '工作室管理页面'],
    ['Login', '登录'], ['Logout', '退出登录'], ['Email', '邮箱'], ['Password', '密码'],
    ['Enter your password', '请输入密码'], ['Remember me for 30 days', '30 天内保持登录'],
    ['Current Password', '当前密码'], ['New Password', '新密码'], ['Confirm New Password', '确认新密码'],
    ['Change Password', '修改密码'], ['Update Password', '更新密码'], ['Not signed in', '尚未登录'],
    ['Last Login', '最近登录'], ['Login Status', '登录状态'],
    ['Overview', '总览'], ['Tenants', '工作室'], ['Plans', '套餐'], ['Audit Logs', '审计日志'],
    ['Starter', '入门版'], ['Growth', '成长版'],
    ['Analytics', '数据分析'], ['Brand', '品牌'], ['Hero', '首屏'], ['Registration', '报名'],
    ['Public Pages', '公开页面'], ['Preview / Publish', '预览与发布'], ['Website / Brand', '官网与品牌'],
    ['Brand & website', '品牌与官网'], ['Admissions', '招生入口'], ['Insights', '经营洞察'],
    ['Studio Admin workspaces', '工作室管理工作区'], ['Draft website preview', '官网草稿预览'],
    ['Preview source', '预览来源'], ['Published website preview', '已发布官网预览'],
    ['No unpublished changes.', '没有未发布的改动。'], ['https://…', 'https://…'],
    ['Go to field', '前往对应字段'],
    ['Brand foundation', '品牌基础'], ['Hero & actions', '首屏与行动按钮'], ['Website sections', '官网版块'],
    ['Selected work', '工作室作品'], ['Public timetable', '公开课表'], ['Registration form', '报名表'],
    ['Family messages', '家长话术'], ['Preview & publish', '草稿预览与发布'], ['Website analytics', '官网数据分析'],
    ['Timetable', '课程安排'], ['Selected Work', '工作室作品'],
    ['Manage tenants, plans, subscriptions, and platform analytics', '管理工作室、套餐、订阅与平台数据'],
    ['Manage studios, subscriptions, and safe operational state', '管理工作室、订阅与安全运营状态'],
    ['Platform Admin work areas', '平台管理工作区'], ['Workspace context', '工作区上下文'], ['Close inspector', '关闭详情'], ['Close editor', '关闭编辑器'], ['Close dialog', '关闭对话框'], ['Tenant detail sections', '工作室详情分区'],
    ['Main', '主要'], ['Customers', '客户'], ['Commercial', '商业'],
    ['Work areas', '工作区'], ['Close work areas', '关闭工作区'],
    ['Tenant lifecycle, recurring revenue, activation, and platform usage', '工作室生命周期、经常性收入、启用情况与平台用量'],
    ['Tenants & Subscriptions', '工作室与订阅'], ['Plans & Pricing', '套餐与定价'],
    ['Pricing and platform limits available to tenants', '面向工作室的价格与平台额度'],
    ['Commercial Overview', '经营总览'], ['Commercial Attention', '经营关注事项'],
    ['30-Day Acquisition Funnel', '近 30 天获客漏斗'], ['Recent platform activity', '近期平台活动'],
    /* Overview group headings — the console orders its blocks by what the
       operator does with them, so these labels carry that meaning and have to
       translate with the rest of the page. */
    /* Theme fine-tuning. These two write the theme's own accent tokens, so
       they are named after those tokens rather than after "brand colour",
       and they match the swatch labels in the preview beside them. */
    ['Accent', '强调色'],
    ['Buttons, links and selected states', '按钮、链接与选中状态'],
    ['Badges and small highlights only', '仅用于徽章与小面积点缀'],
    /* Studio Admin: disclosure summaries. Each fold hides settings a studio
       sets once, never a language half of a bilingual pair. */
    ['Studio details', '工作室资料'],
    ['Contact, welcome message, CMS layout', '联系方式、欢迎语、CMS 布局'],
    ['Section names', '版块名称'],
    ['Rename the public headings', '自定义公开页面的标题'],
    ['About the space', '空间介绍'],
    ['Headings, copy and up to six photos', '标题、正文，以及最多六张照片'],
    ['Search engines', '搜索引擎'],
    ['Override the public page title and description', '自定义公开页面的标题与描述'],
    ['Fine colour control', '精细颜色调整'],
    ['Optional — the theme already sets these', '选填 — 主题已自动配好'],
    ['On CMS and register pages', '显示在 CMS 与报名页'],
    ['Needs attention', '需要处理'],
    ['Lifecycle risks that imply an action today', '今天需要跟进的生命周期风险'],
    ['Business health', '经营概况'],
    ['Standing totals — no action implied', '当前存量数据，无需立即处理'],
    ['Registration conversion', '报名转化'],
    ['Release evidence →', '发布依据 →'],
    ['Recent platform activity and operator changes', '近期平台活动与管理员变更'],
    ['Total Tenants', '工作室总数'], ['Paid Tenants', '付费工作室'], ['Trial Tenants', '试用工作室'],
    ['Trials Ending in 7 Days', '7 天内到期试用'], ['MRR (AUD)', '月度经常性收入（澳元）'],
    ['New in 30 Days', '近 30 天新增'], ['Search Tenants', '搜索工作室'],
    ['All Categories', '全部类别'], ['All Plans', '全部套餐'], ['All Statuses', '全部状态'],
    ['Show test tenants', '显示测试工作室'], ['Clear Filters', '清除筛选'],
    // Overview counters double as tenant filters (v8.2.11).
    ['Filtering', '筛选中'], ['From overview', '来自总览'],
    ['Remove this filter', '移除此筛选'],
    ['Filter by action, tenant, or resource...', '按操作、工作室或对象筛选…'],
    ['No events match this filter.', '没有符合此筛选的事件。'],
    // Plan publication (v8.2.20): a plan row is not automatically an offer.
    ['Public', '公开'], ['Published', '已发布'], ['Not published', '未发布'],
    ['Public pricing page', '公开定价页'],
    ['Publish on pwestudio.online', '发布到 pwestudio.online'],
    ['Mark as the recommended plan', '设为主推套餐'],
        ['+ Add Tenant', '+ 新增工作室'], ['Add Tenant', '新增工作室'], ['Create Tenant', '创建工作室'],
    ['+ Add Plan', '+ 新增套餐'], ['Save Plan', '保存套餐'], ['Save Changes', '保存更改'],
    ['Add Plan', '新增套餐'], ['Edit plan', '编辑套餐'], ['Edit tenant', '编辑工作室'], ['View', '查看'], ['Inspect', '检查'], ['Edit', '编辑'],
    ['Delete plan', '删除套餐'], ['Delete', '删除'], ['Review', '查看处理'],
    ['Tenant workspace', '工作室工作区'], ['Plan workspace', '套餐工作区'],
    ['Editing', '编辑中'], ['Edit workspace', '编辑工作区'], ['Make changes and review their impact before saving.', '修改内容，并在保存前检查影响范围。'],
    ['Ready', '就绪'], ['Ready to edit', '可以编辑'], ['Save from the center workspace when the review is complete.', '完成检查后，请在中间工作区保存。'],
    ['Select an item', '选择一项'], ['Start with what needs attention.', '从需要处理的事项开始。'], ['Select a row to inspect its context.', '选择一行查看上下文。'],
    ['The workspace prioritises subscription risk, usage signals, and operator follow-up.', '工作台优先展示订阅风险、用量信号和待跟进事项。'],
    ['Choose a tenant to review status, subscription metadata, resource usage, and safe next actions.', '选择工作室查看状态、订阅资料、资源用量和安全下一步。'],
    ['Choose a plan to review its commercial limits and publication state.', '选择套餐查看商业额度和公开状态。'],
    ['Choose an event to inspect the actor, resource, reason, and captured metadata.', '选择事件查看操作者、对象、原因和记录的元数据。'],
    ['Current area', '当前工作区'], ['Decision guide', '决策参考'], ['Data state', '数据状态'], ['Attention items', '待处理事项'],
    ['Plan change review', '套餐变更检查'], ['Plan catalog change review', '套餐目录变更检查'],
    ['Will change', '将发生变化'], ['Will be preserved', '将继续保留'], ['Notify tenant', '需要通知工作室'], ['Notify tenants', '需要通知工作室'],
    ['This change affects every tenant currently using this plan.', '此变更会影响当前使用该套餐的所有工作室。'],
    ['Feature enabled', '新增功能'], ['Feature disabled', '停用功能'], ['Current usage is above the new limit', '当前用量高于新额度'],
    ['No additional change identified.', '暂未识别其他变化。'],
    ['Website, brand and showcase content', '官网、品牌与作品展示内容'],
    ['Students, courses, registrations and media', '学员、课程、报名与媒体资料'],
    ['Audit history and tenant settings', '审计历史与工作室设置'], ['Audit history', '审计历史'],
    ['Plan, price and effective date', '套餐、价格与生效日期'], ['New resource and showcase limits', '新的资源与作品展示额度'],
    ['Feature availability', '功能可用性'], ['New price, limits and feature availability', '新价格、额度与功能可用性'],
    ['Affected tenants', '受影响的工作室'],
    ['I reviewed the impact and will notify this tenant.', '我已检查影响，并会通知该工作室。'],
    ['I reviewed the impact and will notify all affected tenants.', '我已检查影响，并会通知所有受影响的工作室。'],
    ['The server will reject the plan change without this acknowledgement.', '未确认此项，服务器将拒绝套餐变更。'],
    ['The server will reject the plan update without this acknowledgement.', '未确认此项，服务器将拒绝套餐更新。'],
    ['Editing, lifecycle, support and archive actions stay in the center list so the right panel remains a quick read.', '编辑、生命周期、支持与归档操作统一放在中间列表，右侧只负责快速查看。'],
    ['Editing and deletion stay in the center list so the right panel remains a quick read.', '编辑与删除统一放在中间列表，右侧只负责快速查看。'],
    ['Tenant Inspector', '工作室详情'], ['Plan Inspector', '套餐详情'], ['Audit Event Inspector', '审计事件详情'],
    ['Current record', '当前记录'], ['Current configuration', '当前配置'], ['Safe next steps', '安全下一步'], ['Configuration', '配置'], ['Tenant allocation', '工作室额度'],
    ['Review before saving', '保存前检查'], ['Form state', '表单状态'], ['Tenants on plan', '使用此套餐的工作室'], ['Current status', '当前状态'], ['Validation errors', '校验错误'],
    ['Action context', '操作上下文'], ['High-frequency tenant actions', '高频工作室操作'], ['High-frequency plan actions', '高频套餐操作'],
    ['Manage', '管理'], ['Open', '打开'], ['What happens next', '下一步会发生什么'],
    ['Review before action', '操作前检查'], ['Explicit confirmation', '明确确认'], ['Action', '操作'], ['Plan usage', '套餐使用情况'],
    ['Filter tenants by this plan', '按此套餐筛选工作室'], ['View tenants on this plan', '查看使用此套餐的工作室'],
    ['Subscription & Plan', '订阅与套餐'], ['View Audit History', '查看审计历史'], ['Open Studio Website', '打开工作室官网'],
    ['Open Studio Admin', '打开工作室管理'], ['Open Quick Registration', '打开快速报名'],
    ['Enter Support Mode', '进入支持模式'], ['Pause tenant', '暂停工作室'],
    ['Reactivate tenant', '重新启用工作室'], ['Archive tenant', '归档工作室'], ['Restore tenant', '恢复工作室'],
    ['Permanent delete tenant', '永久删除工作室'], ['Delete Plan', '删除套餐'], ['View audit history', '查看审计历史'],
    ['Edit studio sections', '编辑工作室分区'], ['Basic info', '基础资料'], ['Limits & Works', '额度与作品'],
    ['No commercial plan change selected.', '未选择商业套餐变更。'], ['Needs adjustment', '需要调整'], ['Before save', '保存前'],
    ['No blocking adjustment identified.', '未发现阻止保存的问题。'], ['Plan impact', '套餐影响'], ['Content safety', '内容安全'],
    ['Communication checklist', '通知清单'], ['Current selection', '当前选择'], ['Review and acknowledge plan change', '检查并确认套餐变更'],
    ['Fix', '修正'], ['No additional change identified.', '暂未识别其他变化。'],
    ['This public surface opens in a new tab and does not require support mode.', '此公开页面会在新标签页打开，无需支持模式。'],
    ['This public registration surface opens in a new tab when the tenant is accepting registrations.', '工作室接受报名时，此公开报名页面会在新标签页打开。'],
    ['This tenant-scoped surface opens only after an audited support session starts.', '此工作室专属页面只有在启动带审计记录的支持会话后才会打开。'],
    ['CMS access is tenant-scoped. Start an audited support session before opening it.', 'CMS 访问属于工作室专属操作，请先启动带审计记录的支持会话。'],
    ['A reason is required and the session is written to the audit log.', '必须填写原因，支持会话会写入审计日志。'],
    ['The audit workspace keeps the operator, reason, target and metadata visible.', '审计工作区会显示操作者、原因、目标和元数据。'],
    ['Pausing keeps tenant content and public records; it changes operational availability.', '暂停会保留工作室内容和公开记录，但会改变运营可用状态。'],
    ['Reactivation restores the active operational and subscription state.', '重新启用会恢复正常运营和订阅状态。'],
    ['Archiving writes snapshots and removes the tenant from normal operations.', '归档会写入快照，并将工作室移出正常运营。'],
    ['Restore returns the tenant to a paused state. Archived evidence is retained.', '恢复会将工作室置于暂停状态，并保留归档证据。'],
    ['Permanent deletion is irreversible for live records. Archive evidence remains available for audit.', '永久删除无法恢复线上记录，但归档证据仍可用于审计。'],
    ['Review the requested action before continuing.', '继续之前请检查请求的操作。'],
    ['Published Showcase Works', '已发布作品数'], ['Draft and archived works remain stored when a plan changes.', '套餐变更时，草稿和已归档作品仍会保留。'],
    ['Showcase works', '作品数'],
    ['Resolve the highlighted fields before saving.', '请先修正已标出的字段，再保存。'], ['Workspace actions', '工作区操作'], ['Cancel editing', '取消编辑'],
    ['Tenant surfaces', '工作室入口'], ['Public and audited entry points', '公开入口与需审计入口'], ['Managed actions', '管理操作'], ['Audited lifecycle changes', '带审计记录的生命周期变更'], ['Requires explicit confirmation', '需要明确确认'],
    ['Restore tenant', '恢复工作室'], ['Reactivate tenant', '重新启用工作室'], ['Pause tenant', '暂停工作室'], ['Archive tenant', '归档工作室'], ['Permanent delete tenant', '永久删除工作室'],
    ['Permanent delete is available only after archiving.', '只有归档后才能永久删除。'], ['Move all tenants to another plan before deleting this plan.', '请先将所有工作室迁移到其他套餐，再删除此套餐。'], ['Review dependencies first', '请先检查依赖关系'],
    ['New plan', '新套餐'], ['New tenant', '新工作室'], ['Save failed', '保存失败'], ['Creating…', '创建中…'], ['Saving…', '保存中…'],
    ['New plans stay private until Publish is selected.', '选择公开前，新套餐不会显示在公开页面。'],
    ['Review affected tenants before saving limits.', '保存额度前请检查受影响的工作室。'],
    ['Define limits and publication state before creating a plan.', '创建套餐前先定义额度和公开状态。'],
    ['Update pricing, limits, entitlements, and publication state.', '更新价格、额度、功能权限和公开状态。'],
    ['Create a studio workspace and prepare its first admin access.', '创建工作室工作区并准备首次管理员访问。'],
    ['Update studio profile, contact, login and subscription metadata.', '更新工作室资料、联系方式、登录信息和订阅资料。'],
    ['Changes are saved to this tenant only after review.', '完成检查后才会保存对该工作室的更改。'],
    ['Lifecycle and danger actions remain in the selected tenant Inspector.', '生命周期和危险操作保留在当前工作室详情中。'],
    ['Tenant', '工作室'], ['Tenant Status', '工作室状态'], ['Subscription Status', '订阅状态'],
    ['Subscription', '订阅'], ['Subscription metadata', '订阅资料'], ['Subscription Start', '订阅开始'],
    ['Current Period Ends', '当前周期结束'], ['Cancellation / Expiry Date', '取消或到期日'],
    ['Changed together with tenant lifecycle state.', '此项会随工作室生命周期状态一起变更。'],
    ['Use More → Status for audited lifecycle actions.', '请使用“更多 → 状态”执行带审计记录的生命周期操作。'],
    ['Name', '名称'], ['Studio', '工作室'], ['Studio Name', '工作室名称'], ['Studio Category', '工作室类别'],
    ['Slug', '网址标识'], ['Code', '代码'], ['Status', '状态'], ['Plan', '套餐'],
    ['Price (AUD)', '价格（澳元）'], ['Price/Month', '月费'], ['Limits', '额度'], ['Entitlements', '功能权限'],
    ['Additional entitlements (JSON)', '其他功能权限（JSON）'],
    ['Only use this for feature flags not listed above.', '仅用于上方未列出的功能开关。'],
    ['Student Limit', '学员上限'], ['Admin User Limit', '管理员上限'], ['Storage Limit', '存储上限'],
    ['Showcase works published', '公开作品上限'],
    ['Media Upload Limit', '媒体上传上限'], ['Storage (MB)', '存储（MB）'], ['Students', '学员数'],
    ['Users', '用户数'], ['Usage', '用量'], ['Owner', '负责人'], ['Owner & Contact', '负责人和联系方式'],
    ['Owner Name', '负责人姓名'], ['Owner Email', '负责人邮箱'], ['Owner Phone', '负责人电话'],
    ['Owner Role', '负责人角色'], ['Contact Email', '联系邮箱'], ['Contact Phone', '联系电话'],
    ['Billing Email', '账单邮箱'], ['Address', '地址'], ['ABN', '澳洲商业号码'], ['Notes', '备注'],
    ['Slogan', '品牌标语'], ['Admin Login', '管理员登录'], ['Studio Admin Email', '工作室管理员邮箱'],
    ['Studio Admin Name', '工作室管理员姓名'], ['Temporary Admin Password', '临时管理员密码'],
    ['Use owner email for contact', '联系邮箱使用负责人邮箱'],
    ['Use owner email for billing', '账单邮箱使用负责人邮箱'],
    ['Use owner email for admin login', '管理员登录使用负责人邮箱'],
    ['Required for initial access. Share it through a secure channel, then ask the owner to change it.', '首次登录必填。请通过安全渠道发送，并要求负责人登录后修改。'],
    ['Leave blank to keep existing password.', '留空可保留现有密码。'],
    ['Password Setup Link', '密码设置链接'], ['Generate link', '生成链接'],
    ['Single use, expires in 24h. Generating a new link invalidates previous unused ones.', '仅可使用一次，24 小时后到期；生成新链接会让旧的未使用链接失效。'],
    ['Copy', '复制'], ['Actions', '操作'], ['Action', '操作'], ['Resource', '对象'], ['Time', '时间'],
    ['Details', '详情'], ['Audit Event Details', '审计事件详情'], ['Resource type', '对象类型'],
    ['Resource ID', '对象 ID'], ['Metadata', '元数据'], ['Support reason', '支持原因'],
    ['System', '系统'], ['No metadata captured.', '未记录元数据。'],
    ['Previous', '上一页'], ['Next', '下一页'], ['Page 1', '第 1 页'], ['More', '更多'],
    ['Close', '关闭'], ['Cancel', '取消'], ['Undo', '撤销'], ['Delete', '删除'], ['Archive', '归档'], ['Pause', '暂停'],
    ['Reactivate', '重新启用'], ['Reset Password', '重置密码'], ['Danger Zone', '危险操作区'],
    ['Archive Tenant', '归档工作室'], ['Permanent Delete', '永久删除'], ['Permanently delete', '永久删除'],
    ['Type tenant slug to confirm', '输入工作室网址标识以确认'], ['Reason', '原因'],
    ['Every support-mode action is audited against this reason.', '支持模式内的每项操作都会连同此原因写入审计记录。'],
    ['Start Support Mode', '进入支持模式'], ['Surfaces', '各使用入口'], ['Website', '官网'],
    ['Onboarding', '启用进度'], ['Basic', '基础版'],
    ['active', '正常'], ['paused', '已暂停'], ['archived', '已归档'], ['deleted', '已删除'],
    ['trial', '试用'], ['past_due', '逾期'], ['cancelled', '已取消'], ['lead', '潜在客户'],
    ['onboarding', '启用中'],
    /* v8.3.0 deleted the workbench hero and the duplicated section header from
       Studio Admin, and with them 'Brand Builder', 'Shape the public studio
       experience', the hero body copy and the 'Logo, colours, public copy…'
       subtitle. Their entries are gone too: a dictionary that keeps entries
       for strings the product no longer renders is a list of claims nobody
       checks. */
    ['Website modules', '官网版块'], ['FAQ & messages', '常见问题与话术'],
    ['Principal', '负责人'],
    /* Field labels that pair a name with the language of the field's own
       content. The hand-written pairs live further up; these three were
       added when the About and Selected work panels grew. */
    ['Eyebrow · 中文', '小标题 · 中文'], ['Eyebrow · English', '小标题 · English'],
    ['Lead · 中文', '引导语 · 中文'], ['Lead · English', '引导语 · English'],
    ['Description · 中文', '简介 · 中文'], ['Description · English', '简介 · English'],
    ['(direct)', '（直接访问）'],
    ['Brand foundation', '品牌基础'],
    ['Build the foundation in three clear steps: industry, visual theme, then studio details.', '按三个清晰步骤完成品牌基础：行业、视觉主题、工作室资料。'],
    ['Choose an industry foundation', '选择行业基础'],
    ['This sets the recommended copy, registration questions, and starting theme.', '用于设置推荐文案、报名问题与初始主题。'],
    ['Choose a colour theme', '选择颜色主题'],
    ['Start with one professionally balanced palette. You can fine-tune it without changing the industry content.', '先选择一套经过专业平衡的配色；后续微调不会改变行业内容。'],
    ['Theme', '主题'], ['The recommended theme is selected automatically.', '系统会自动选择推荐主题。'],
    ['Recommended', '推荐'], ['Selected', '已选择'], ['Custom', '自定义'],
    ['Fine-tune selected theme', '微调当前主题'],
    // The accent knob (v8.5.0). One palette, one colour the studio sets.
    ['Colour theme', '颜色主题'],
    ['Accent colour', '强调色'],
    ['Hero Shape', '首屏形状'],
    ['Artistic (organic)', '艺术（异形）'],
    ['Oval', '椭圆'],
    ['Rectangle', '方形'],
    ['Pick an accent colour', '选择强调色'],
    ['From logo', '从 Logo 取色'],
    ['Only the hue is used — the depth is solved so the button stays readable.',
     '只取色相，深浅由系统求解，按钮始终可读。'],
    ['Upload a logo first, then take the colour from it.', '先上传 Logo，再从它取色。'],
    ['That logo has no strong colour to take.', '这个 Logo 里没有足够的颜色可取。'],
    ['That logo could not be read.', '读不到这个 Logo。'],
    ['Add studio identity and contact details', '填写工作室品牌与联系方式'],
    ['These details appear across the public website, registration, and CMS.', '这些资料会统一显示在官网、报名页与 CMS 中。'],
    ['Main brand colour', '主品牌色'], ['Supporting brand colour', '辅助品牌色'],
    ['Primary accent and actions', '主要强调色与操作按钮'], ['Secondary actions and highlights', '辅助操作与高亮'],
    ['Muted Text', '弱化文字'], ['Border Color', '边框颜色'],
    // Batch 5: the new 中文 / English twin inputs and their help text.
    ['Slogan · 中文', '品牌标语 · 中文'], ['Slogan · English', '品牌标语 · English'],
    ['Welcome Message · 中文', '欢迎语 · 中文'], ['Welcome Message · English', '欢迎语 · English'],
    ['Fill in one language and it is shown to everyone. Leave both blank to hide the welcome band.',
     '只填一种语言时，两种语言都显示这一句；两者都留空则不显示欢迎条。'],
    ['Courses Label · 中文', '课程版块标题 · 中文'], ['Courses Label · English', '课程版块标题 · English'],
    ['Gallery Label · 中文', '作品版块标题 · 中文'], ['Gallery Label · English', '作品版块标题 · English'],
    ['FAQ Label · 中文', '常见问题版块标题 · 中文'], ['FAQ Label · English', '常见问题版块标题 · English'],
    ['Contact Label · 中文', '联系版块标题 · 中文'], ['Contact Label · English', '联系版块标题 · English'],
    ["%WORK% and %WORKS% are replaced with your industry's word for what a student produces, so the same label works for a piano, dance, or games studio.",
     '%WORK% 与 %WORKS% 会替换成你所在行业对学员成果的说法，因此同一个标题在琴行、舞蹈教室与游戏工作室都成立。'],
    ['Principal Title · 中文', '主理人头衔 · 中文'], ['Principal Title · English', '主理人头衔 · English'],
    ['Principal Quote · 中文', '主理人短句 · 中文'], ['Principal Quote · English', '主理人短句 · English'],
    ['Principal Bio · 中文', '主理人介绍 · 中文'], ['Principal Bio · English', '主理人介绍 · English'],
    ["A person's name is never translated.", '人名不做翻译。'],
    ['Leave either language blank and the other is shown to everyone. The section stays hidden until a bio exists.',
     '任一语言留空时，另一种语言对所有访客显示；没有介绍内容时整个版块不显示。'],
    ["Course names and work titles come from the CMS and are shown exactly as staff typed them — they do not follow the visitor's language. Only the section headings here do.",
     '课程名称与作品标题来自运营 CMS，按录入的语言原样显示，不随访客语言切换；只有这里的版块标题会切换。'],
    ['Button text and status colours are selected automatically for readable contrast.', '系统会自动选择按钮文字与状态颜色，确保清晰可读。'],
    // 2-1 / 2-2: the eight curated themes. Their Chinese names and descriptions
    // also ship on /v1/visual-style-presets as labelZh / descriptionZh, which is
    // what the brand builder reads; these entries cover the same strings when
    // they reach the DOM some other way (a toast, a cached response, Super
    // Admin's tenant table).
    ['Atelier Clay', '陶土工坊'], ['Vintage Press', '复古印刷'], ['Studio Ink', '黑白纸墨'],
    ['Harbour Calm', '静谧海港'], ['Cedar Grove', '雪松林'], ['Recital Plum', '独奏紫'],
    ['Rehearsal Rose', '排练玫瑰'], ['Arcade Lime', '街机青柠'],
    ['Warm clay on a paper surface, the way a gallery wall behaves — for studios where the work should lead.',
     '陶土的暖调落在纸质表面，像画廊的墙。适合让作品自己说话的工作室。'],
    ['The ink-and-paper restraint of an old print shop, for studios whose credibility rests on words and experience.',
     '老式印刷的墨与纸，克制的暖棕。适合靠文字与经验建立信任的工作室。'],
    ['Near-monochrome ink on paper, with a single slate-blue note marking what can be clicked.',
     '近乎黑白的纸与墨，只用一抹石板蓝标出可点击之处，内容始终是主角。'],
    ['Still-water blues in adjacent hues — clear, trustworthy, and quiet enough to read all day.',
     '静水一般的蓝，色相彼此相邻。清楚、可信，长时间阅读也不吵。'],
    ['Cedar green against ochre in a triadic balance — the palette of the outdoors and the training ground.',
     '雪松绿配赭石黄，三分色的平衡。属于户外与训练场的配色。'],
    ['Stage-curtain plum with a neighbouring violet, for recitals, graded exams and performance.',
     '舞台幕布般的紫，衬以邻近的蓝紫。适合演出、考级与表演路线。'],
    ['Rehearsal-room rose against a moss green: kinetic without shouting.',
     '排练厅的玫红，配一抹苔绿。有动势，但不刺眼。'],
    ['Arcade-screen lime, dark only: on a light page it turns olive and loses the reason it exists.',
     '街机屏幕上的荧光青柠，只做暗色——放到浅色底上会变成橄榄绿，失去存在的理由。'],
    // 4-3: colour relationships, now shown as the reason to pick one theme.
    ['Split-complementary', '分裂互补'], ['Analogous', '邻近色'], ['Triadic', '三分色'],
    ['Neutral / monochrome', '单色中性'],
    ['Colour relationship', '色相关系'],
    ['Light + dark', '明暗双模'], ['Dark only', '仅暗色'],
    ['Page', '页面'], ['Panel', '面板'], ['Accent', '强调色'], ['Support', '辅助色'],
    ['Control boundary', '控件边界'], ['Focus ring', '聚焦环'],
    ['Success', '成功'], ['Warning', '警示'], ['Danger', '危险'],
    ['Core identity, industry preset, colours, contact, and CMS shell presentation.', '设置核心品牌、行业预设、颜色、联系方式与 CMS 外观。'],
    ['Apply Category Preset', '应用行业预设'], ['Primary Color', '主品牌色'], ['Secondary Color', '辅助品牌色'],
    ['Accent Color', '强调色'], ['Page Background', '页面背景'], ['Panel Background', '面板背景'],
    ['Text Color', '文字颜色'], ['Main public accent', '公开页面主要强调色'], ['Font Mood', '字体风格'],
    ['Modern sans', '现代无衬线'], ['Serif / editorial', '衬线编辑风'], ['Button Style', '按钮样式'],
    ['Rounded', '圆角'], ['Sharp', '直角'], ['Soft', '柔和'], ['CMS Layout', 'CMS 布局'],
    ['Classic balanced', '经典均衡'], ['Compact', '紧凑'], ['Soft Art Board', '柔和画板'],
    ['Bold Contrast', '强对比'], ['Header Bar', '顶部栏'], ['Hero and calls to action', '首屏与行动按钮'],
    ['The first screen parents see on the portal.', '家长进入官网后首先看到的内容。'],
    ['Hero Eyebrow', '首屏眉题'], ['Hero Title · 中文', '首屏标题 · 中文'], ['Hero Title · English', '首屏标题 · English'],
    ['Hero Subtitle · 中文', '首屏副标题 · 中文'], ['Hero Subtitle · English', '首屏副标题 · English'],
    ['Hero Image URL', '首屏图片网址'], ['Hero Style', '首屏样式'], ['Minimal', '简约'],
    ['Image Background', '图片背景'], ['Primary CTA · 中文', '主要按钮 · 中文'],
    ['Primary CTA · English', '主要按钮 · English'], ['Secondary CTA · 中文', '次要按钮 · 中文'],
    ['Secondary CTA · English', '次要按钮 · English'], ['Upload Hero Image', '上传首屏图片'],
    ['Upload Logo', '上传 Logo'], ['Upload Principal Image', '上传主理人图片'],
    ['JPEG, PNG, or WebP; metadata is removed before public delivery.', '支持 JPEG、PNG 或 WebP；公开展示前会移除图片元数据。'],
    ['Uses the tenant media quota and safe public derivative.', '使用本工作室媒体额度，并生成安全公开副本。'],
    ['Website sections', '官网版块'],
    ['Control which public sections appear and the about/principal content.', '控制公开版块以及工作室和主理人介绍。'],
    ['Courses Section', '课程版块'], ['Gallery Section', '作品墙版块'], ['Student Area Section', '学员专区版块'],
    ['Principal Section', '主理人版块'], ['FAQ Section', '常见问答版块'], ['Courses Label', '课程标题'],
    ['Gallery Label', '作品墙标题'], ['Portal Label', '门户标题'], ['FAQ Label', '常见问答标题'],
    ['Principal Name', '主理人姓名'], ['Principal Title', '主理人头衔'], ['Principal Bio', '主理人简介'],
    ['Principal Quote', '主理人寄语'], ['Principal Image URL', '主理人图片网址'],
    ['About the Space Section', '空间介绍版块'],
    // Exact-phrase map: the ' · 中文' / ' · English' halves need their own
    // entries, the same as every other bilingual pair above.
    ['About Eyebrow · 中文', '空间小标题 · 中文'], ['About Eyebrow · English', '空间小标题 · English'],
    ['About Title · 中文', '空间标题 · 中文'], ['About Title · English', '空间标题 · English'],
    ['About Body · 中文', '空间介绍 · 中文'], ['About Body · English', '空间介绍 · English'],
    ['About Photos', '空间照片'], ['About Highlights', '空间亮点'],
    ['The Studio · Space', '画室 · 空间'],
    ['A warm, considered space', '一间温暖、有秩序的空间'],
    ['Public description of the space', '面向公众的空间介绍'],
    ['Optional. A highlight with no title is left out.', '选填。没有标题的亮点不会展示。'],
    ['Leave either language blank and the other is shown to everyone. The section stays hidden until a title or body exists.',
     '任一语言留空，另一种语言会展示给所有访客。标题和正文都为空时，该版块不会出现。'],
    ['Up to six, shown as a slow carousel. Each upload uses the tenant media quota and is served through the safe public derivative.',
     '最多六张，以缓慢轮播展示。每次上传都会占用媒体额度，并通过安全的公开副本对外提供。'],
    ['SEO Title', '搜索标题'], ['SEO Description', '搜索描述'],
    // Selected Work — the studio's own portfolio, not the students'.
    ['Selected Work', '工作室作品'], ['Selected Work Section', '工作室作品版块'],
    ['Selected work', '工作室作品'],
    ['Section Eyebrow · 中文', '版块眉题 · 中文'], ['Section Eyebrow · English', '版块眉题 · English'],
    ['Section Title · 中文', '版块标题 · 中文'], ['Section Title · English', '版块标题 · English'],
    ['Section Lead · 中文', '版块引导语 · 中文'], ['Section Lead · English', '版块引导语 · English'],
    ['Works', '作品'], ['Add a work', '添加作品'], ['Photo', '照片'], ['Replace photo', '更换照片'],
    ['Title · 中文', '标题 · 中文'], ['Title · English', '标题 · English'],
    ['Caption · 中文', '说明 · 中文'], ['Caption · English', '说明 · English'],
    ['Publication status', '公开状态'], ['Active', '公开'], ['Draft', '草稿'], ['Archived', '已归档'],
    ['Featured rank (optional)', '精选排序（选填）'],
    ['Lower numbers appear first; ranks 1–6 are the home preview.', '数字越小越靠前；1–6 会出现在首页精选中。'],
    ['Set an optional featured rank to choose the public order. Ranks 1–6 appear in the home preview; blank ranks follow the existing order. Your plan controls how many active works are public; the full showcase loads 12 at a time. Drafts and archived works stay here, and a work with neither a photo nor a video is not saved.', '可选设置精选排序，决定公开页顺序。1–6 会出现在首页精选中；留空则沿用现有顺序。套餐决定公开的 active 作品数量；完整作品页每次加载 12 件。草稿和已归档作品会保留在这里；既没有照片也没有视频的条目不会保存。'],
    ['Video link (optional)', '视频链接（选填）'],
    ['Lead', '主作品'], ['Order', '顺序'], ['Fallback', '备用顺序'], ['Featured', '精选'],
    ['Categories', '分类'], ['Add a category', '添加分类'], ['Remove category', '删除分类'],
    ['Add photos: drag files here, or press to choose', '添加照片：把文件拖到这里，或按此选择'],
    ['Drag photos here', '把照片拖到这里'],
    ['or press to choose several at once', '或点击一次选择多张'],
    ['Upload failed.', '上传失败。'], ['Upload cancelled.', '上传已取消。'],
    ['Category', '分类'], ['Uncategorised', '未分类'],
    ['Category · 中文', '分类名称 · 中文'], ['Category · English', '分类名称 · English'],
    ['Optional. Visitors get filter buttons once you have two or more. Deleting a category never deletes work — those pieces simply become uncategorised.',
     '选填。有两个及以上分类时，访客会看到筛选按钮。删除分类不会删除作品，那些作品只会变成未分类。'],
    ['Work from this studio', '出自这间工作室'],
    ['A short selection, chosen by the studio.', '一小组精选，由工作室自己挑选。'],
    ['The photo is shown on its own.', '只展示这张照片。'],
    ['Not a recognised link — only YouTube, Vimeo and Bilibili can be embedded.',
     '无法识别这个链接——只支持 YouTube、Vimeo 与哔哩哔哩。'],
    ['The first work is shown larger than the rest — put your strongest piece first. Your plan controls how many active works are public; this page loads 12 at a time. Drafts and archived works stay here, and a work with neither a photo nor a video is not saved.',
     '第一件作品会比其余的展示得更大——把最强的一件放在最前。套餐决定公开的 active 作品数量；本页每次加载 12 件。草稿和已归档作品会保留在这里；既没有照片也没有视频的条目不会保存。'],
    ['Your own work, not your students\'. This is the section that answers "how good is the person teaching here?" — the Student works section answers a different question and stays separate.',
     '这里放你自己的作品，不是学员的。它回答的是「教你的人水平如何」——学员作品墙回答的是另一个问题，两者分开。'],
    ['Videos are linked, never uploaded: paste a YouTube, Vimeo or Bilibili link and only the cover image uses your storage. Nothing is requested from those sites until a visitor presses play.',
     '视频只放链接，不上传：粘贴 YouTube、Vimeo 或哔哩哔哩的链接即可，只有封面图会占用你的存储额度。访客按下播放之前，不会向这些网站发出任何请求。'],
    ['Leave blank to use the studio name', '留空则使用工作室名称'],
    ['Leave blank to use the slogan', '留空则使用标语'],
    ['Show', '显示'], ['Hide', '隐藏'], ['Contact', '联系信息'], ['Contact Label', '联系区标题'],
    ['Welcome Message', '欢迎语'], ['Show Welcome', '显示欢迎语'], ['Show on CMS/Register', '在 CMS/报名页显示'],
    ['Welcome message appears on CMS and Register when enabled.', '启用后，欢迎语会显示在 CMS 与报名页。'],
    ['Registration form', '报名表'],
    ['Lead capture copy and questions shown on the portal and register page.', '设置官网和报名页显示的获客文案与问题。'],
    ['Registration Title · 中文', '报名标题 · 中文'], ['Registration Title · English', '报名标题 · English'],
    ['Registration Intro · 中文', '报名简介 · 中文'], ['Registration Intro · English', '报名简介 · English'],
    ['Questions', '报名问题'], ['Question', '问题'], ['Add Question', '新增问题'], ['Add Item', '新增项目'],
    ['Label · 中文', '标签 · 中文'], ['Label · English', '标签 · English'],
    ['Placeholder · 中文', '提示文字 · 中文'], ['Placeholder · English', '提示文字 · English'],
    /* The option labels of the registration field-type selector. The
       <option value> stays the stored enum (text / textarea / select);
       only what an operator reads changes, which is why the enum keeps
       its English while these three do not. */
    ['Short text', '单行文本'], ['Long text', '多行文本'], ['Dropdown', '下拉选择'],
    ['Type', '类型'], ['Required', '必填'], ['Optional', '选填'], ['Required / Options', '必填与选项'],
    ['Select options, comma separated', '下拉选项，用逗号分隔'],
    ['Remove', '移除'], ['Short text, long text, and select fields are supported.', '支持短文本、长文本和下拉选择字段。'],
    ['FAQ', '常见问答'], ['Questions shown near the bottom of the public portal.', '这些问题会显示在公开官网底部附近。'],
    ['Question (中文)', '问题（中文）'], ['Question (English)', '问题（英文）'],
    ['Answer (中文)', '答案（中文）'], ['Answer (English)', '答案（英文）'],
    ['Language', '语言'], ['Device', '设备'],
    ['Appearance', '明暗模式'], ['Light', '明亮'], ['Dark', '暗色'],
    ['The first thing a parent reads on your website, and the button they tap to book. Live on the portal as soon as you publish.',
     '家长打开官网后第一眼读到的内容，以及点击预约的按钮。发布后立即生效。'],
    ['Turn public sections on or off. A section with nothing written in it stays hidden rather than showing an empty block to visitors.',
     '控制公开版块的显示。没有填内容的版块会自动隐藏，不会给访客看到一块空白。'],
    ['What a family fills in to enquire. Every question here appears on both the portal form and the standalone register page, and lands in the CMS under Pending.',
     '家长咨询时要填的内容。这里的每个问题都会同时出现在官网表单和独立报名页，提交后进入 CMS 的「待审核」。'],
    ['Answers to what families ask before they book. Shown near the bottom of the portal in whichever language the visitor is reading.',
     '家长决定预约前最常问的问题。显示在官网底部，并跟随访客当前的语言。'],
    ['What your staff copy out of the CMS and send to a family. Placeholders are filled in per student: {student} {studio} {balance} {credits} {fee} {note}',
     '员工从 CMS 复制、发送给家长的文案。占位符会按学员自动替换：{student} {studio} {balance} {credits} {fee} {note}'],
    ['Light and dark are designed as a pair; both are checked for contrast.',
     '明暗为成对设计，两种模式都已通过对比度检查。'],
    ['Messages', '家长话术'], ['Family messages', '家长话术'],
    ['Owner-managed copy templates used by staff during admissions and daily follow-up. Staff copy them from the CMS; this page does not send email or SMS.',
     '负责人维护的招生与日常跟进话术。员工在 CMS 中复制使用；此页面不会发送邮件或短信。'],
    ['Placeholders are filled in per student: {student} {studio} {balance} {credits} {fee} {note}',
     '占位符会按学员自动替换：{student} {studio} {balance} {credits} {fee} {note}'],
    ['Copy staff paste to families from the CMS. Placeholders: {student} {studio} {balance} {credits} {fee} {note}',
     '员工在 CMS 中复制、发送给家长的文案。可用占位符：{student} {studio} {balance} {credits} {fee} {note}'],
    ['Reset to defaults', '恢复默认'], ['Check-in', '签到'],
    ['Check-in with no credits left', '签到（课时已用完）'],
    ['Credits purchased', '充值成功'], ['Renewal reminder', '续课提醒'],
    ['Birthday greeting', '生日祝福'],
    ['Public Timetable Page', '公开课表页面'], ['Accept booking requests', '接受约课申请'],
    ['Weeks to show', '显示周数'], ['Page Eyebrow · 中文', '页面眉题 · 中文'],
    ['Page Eyebrow · English', '页面眉题 · English'], ['Page Lead · 中文', '页面说明 · 中文'],
    ['Page Lead · English', '页面说明 · English'], ['What each class shows', '每节课显示内容'],
    ['Teacher', '老师'], ['Room', '教室'], ['Age range', '适龄段'], ['Finish time', '结束时间'],
    ['Places left', '剩余位置'], ['Price', '价格'],
    ['Draft preview — not public until Publish', '草稿预览 — 发布前不会公开'],
    ['Draft preview — compare with the published website before publishing', '草稿预览 — 发布前请与已发布官网对照'],
    ['Draft preview — publish needs attention', '草稿预览 — 发布需要处理'],
    ['Unsaved changes — saved draft is not public', '有未保存修改 — 已保存草稿不会公开'],
    ['Published content', '已发布内容'],
    ['Changes waiting to be saved', '有修改等待保存'],
    ['Publish failed — changes are not confirmed public', '发布失败 — 尚未确认公开'],
    ['Published, public pages still need verification', '已发布，公开页面仍在确认'],
    ['Publish verification failed after the write. Your saved content is safe; check the public pages and retry.', '写入成功后公开验证未完成，内容已安全保存；请检查公开页面后重试。'],
    ['Recheck public pages', '重新检查公开页面'],
    ['Public pages verified', '公开页面已确认'],
    ['Public surface unavailable', '公开表面暂时不可用'],
    ['Public surface returned invalid data', '公开表面返回了无效数据'],
    ['The public page is not ready yet.', '公开页面尚未准备好。'],
    ['Checking...', '正在检查…'],
    ['Public navigation', '公开导航'], ['Footer links', '页脚入口'],
    ['Publish needs attention', '发布需要处理'],
    ['The current editor values are a private draft. Publish when the public pages are ready.', '当前编辑内容是私有草稿，公开页面准备好后再发布。'],
    ['Save a draft to keep the work private, or publish after checking the preview.', '先保存草稿可保持私有；确认预览后再发布。'],
    ['The current editor values match the published tenant pages.', '当前编辑内容与已发布的工作室页面一致。'],
    ['Check the error, save the draft if needed, then publish again.', '请先处理错误；如有需要先保存草稿，再重新发布。'],
    ['Preview language', '预览语言'], ['Preview device', '预览设备'],
    ['Public navigation preview', '公开导航预览'],
    ['Add FAQ', '新增常见问答'], ['Answer', '答案'], ['Preview and publish', '预览与发布'],
    ['Theme Preview', '主题预览'], ['Desktop', '桌面'], ['Mobile', '手机'], ['Save Draft', '保存草稿'],
    ['Publish', '发布'], ['Publication history', '发布历史'],
    /* Found reading the Chinese manual against the Chinese UI: these two
     * stayed English, so the manual could not name them in Chinese. */
    ['Restore to Draft', '恢复为草稿'],
    ['Improve colour contrast before publishing:', '发布前请提高对比度：'],
    ['No published versions yet.', '尚无已发布版本。'],
    ['Restore a previous publication into the draft, review it in the preview, then publish when ready.', '可将历史版本恢复为草稿，预览确认后再发布。'],
    ['No unsaved changes', '没有未保存的更改'], ['Refresh', '刷新'],
    ['Open this tab to load analytics.', '打开此页签后加载分析数据。'],
    ['Public website analytics', '公开官网数据分析'],
    ['Anonymous aggregate traffic and registration conversion. No names, contact details, IP addresses, or student activity are stored.', '仅统计匿名汇总流量和报名转化；不保存姓名、联系方式、IP 地址或学员活动。'],
    ['Page views', '页面浏览量'], ['Anonymous sessions', '匿名访问次数'], ['CTA clicks', '行动按钮点击'],
    ['Registrations submitted', '已提交报名'], ['Campaign summary', '推广来源汇总'],
    ['30 days', '30 天'], ['7 days', '7 天'], ['90 days', '90 天'],
    ['Check the published website, operational CMS, alternate registration entry, and this brand workspace', '检查已发布官网、运营 CMS、独立报名入口与本品牌工作区'],
    ['Open Website', '打开官网'], ['Open CMS', '打开运营 CMS'], ['Open Quick Registration', '打开快速报名'],
    ['Open Studio Admin', '打开工作室管理'], ['Studio Website', '工作室官网'], ['Quick Registration', '快速报名'],
    ['CMS', '运营 CMS'], ['This website and brand workspace.', '当前官网与品牌管理工作区。'],
    ['The daily operations workspace for students, schedules, check-ins, payments, refunds, logs, and portfolio work.', '用于学员、排课、签到、收费退款、日志与作品管理的日常运营工作区。'],
    ['The tenant-specific lead capture page. Its labels, intro copy, and preferences are controlled above.', '本工作室专属获客报名页；标签、介绍和偏好问题由上方设置控制。'],
    ['Primary bilingual public experience with introduction, courses, work gallery, student area, and registration CTA.', '主要双语官网，包含介绍、课程、作品墙、学员专区与报名入口。'],
    ['Loading tenant...', '正在载入工作室…'], ['Not checked', '尚未检查'],
    ['Open real tenant pages after saving, or export operational data below.', '保存后可打开真实工作室页面；运营数据可在下方导出。'],
    ['Use the Studio Admin email and password configured in Super Admin.', '请使用平台管理中配置的工作室管理员邮箱和密码。'],
    ['Use the local Super Admin account to manage tenants, plans, and platform settings.', '请使用平台管理员账号管理工作室、套餐与平台设置。'],
    ['Managed by StudioSaaS Super Admin.', '由 StudioSaaS 平台管理员管理。'],
    ['Timezone', '时区'], ['Phone', '电话'], ['Given name *', '名字 *'], ['Mobile *', '手机号码 *'],
    ['Book a Trial', '预约体验'], ['Explore Courses', '查看课程'], ['Submit registration', '提交报名'],
    ['Tell us about the student and their goals.', '请告诉我们学员情况与学习目标。'],
    ['Published Pages', '已发布页面'], ['Quick Registration Form', '快速报名表'], ['Tenant slug', '工作室网址标识'],
    /* v8.3.0. applyAttributes() has always localised placeholder / title /
       aria-label; these 26 simply had no entry, so a console switched to
       Chinese still hinted in English inside every field on the page. Found by
       walking the rendered document rather than by reading the dictionary. */
    ['Account', '账户'],
    ['your-studio-slug', '你的工作室标识'],
    ['owner@studio.test', 'owner@studio.test'],
    ['studio@example.com', 'studio@example.com'],
    ['Website settings', '官网设置'],
    ['Analytics period', '统计周期'],
    ['Live website preview', '官网实时预览'],
    ['Close dialog', '关闭对话框'],
    ['Public brand slogan', '对外品牌标语'],
    ['Studio address', '工作室地址'],
    ['Welcome text shown above the website and register page', '显示在官网与报名页顶部的欢迎语'],
    ['Creative Studio', '创意工作室'],
    ['Public hero headline', '官网首屏主标题'],
    ['Short public value proposition', '一句话说明你的价值'],
    ['Courses & Classes', '课程与班级'],
    ['Student %WORKS%', '学员%WORKS%'],
    ['Questions & Answers', '常见问答'],
    ['Name shown on public page', '显示在公开页面的姓名'],
    ['Founder & Principal', '创始人 / 主理人'],
    ['Short signature line', '一句话签名'],
    ['Short public introduction', '简短的公开介绍'],
    ['Student portal label', '学员端名称'],
    ['Registration form title', '报名表标题'],
    ['Registration form intro text', '报名表引导语'],
    ['/site/hero.jpg or https://...', '/site/hero.jpg 或 https://…'],
    ['/site/principal.jpg or https://...', '/site/principal.jpg 或 https://…'],
    /* Written into the page by script rather than authored in the markup, so
       the attribute sweep above could not see them. `No unsaved changes` had an
       entry and `Unsaved changes` did not — the lookup is exact, so the save
       bar reverted to English the moment anything was edited. */
    ['Unsaved changes', '有未保存的更改'],
    ['Draft saved — not public', '草稿已保存 —— 尚未公开'],
    ['Saved draft loaded — not public', '已载入保存的草稿 —— 尚未公开'],
    ['Previous draft choices restored.', '已恢复上一次的草稿选择。'],
    ['Enter the studio URL slug to continue.', '请填写工作室网址标识后继续。'],
    ['No public portal events in this period.', '该时间段内没有官网访问记录。'],
    ['No studio selected. Open this console from your studio URL: /<your-studio-slug>/studio-admin.', '尚未选择工作室。请从你的工作室网址打开本控制台：/<工作室网址标识>/studio-admin。'],
    ['Studio owner', '工作室主理人'],
    ['Website and brand console', '官网与品牌管理'],
    ['Loading lifecycle risks…', '正在载入生命周期风险…'], ['Loading registration conversion…', '正在载入报名转化…'],
    ['Please log in with a Super Admin account.', '请使用平台管理员账号登录。'],
    ['Please log in to continue.', '请登录后继续。'], ['Email and password are required.', '请输入邮箱和密码。'],
    ['Logged in.', '登录成功。'], ['Logged out.', '已退出登录。'],
    ['Too many login attempts — please wait a minute and try again.', '登录尝试过多，请稍等一分钟后再试。'],
    ['Invalid email or password.', '邮箱或密码错误。'], ['New passwords do not match.', '两次输入的新密码不一致。'],
    ['Password updated.', '密码已更新。'], ['Current password is incorrect.', '当前密码不正确。'],
    ['A reason is required to enter support mode.', '进入支持模式前必须填写原因。'],
    ['Support mode is not available for this account.', '此账号暂不可使用支持模式。'],
    ['Plan code is required.', '必须填写套餐代码。'],
    ['Plan code must be lowercase letters, numbers, or hyphens.', '套餐代码只能使用小写字母、数字或连字符。'],
    ['Plan name is required.', '必须填写套餐名称。'],
    ['Monthly price must be a non-negative integer.', '月费必须是大于等于 0 的整数。'],
    ['Student limit must be a positive integer.', '学员额度必须是正整数。'],
    ['User limit must be a positive integer.', '用户额度必须是正整数。'],
    ['Storage limit must be positive.', '存储额度必须大于 0。'],
    ['Ready', '就绪'], ['Loading', '正在载入'], ['Partial load', '部分载入'],
    ['Error', '错误'], ['Not refreshed', '尚未刷新'], ['Retry', '重试'],
    ['Subscription past due', '订阅已逾期'], ['Subscription Past Due', '订阅已逾期'],
    ['Subscription record needs review.', '订阅记录需要检查。'], ['Usage approaching limit', '用量接近上限'],
    ['Support mode started — opening Studio Admin.', '支持模式已开始，正在打开工作室管理。'],
    ['Link copied to clipboard', '链接已复制到剪贴板'], ['Link copied', '链接已复制'],
    ['Name and slug are required.', '名称和网址标识为必填项。'], ['Tenant updated.', '工作室已更新。'],
    ['Tenant created.', '工作室已创建。'], ['Tenant paused.', '工作室已暂停。'],
    ['Tenant reactivated.', '工作室已重新启用。'], ['Tenant restored to paused status.', '工作室已恢复为暂停状态。'],
    ['Tenant permanently deleted. Archive evidence was retained.', '工作室已永久删除，归档证据已保留。'],
    ['Plan updated.', '套餐已更新。'], ['Plan created.', '套餐已创建。'], ['Plan deleted.', '套餐已删除。'],
    ['Tenant slug is required.', '必须提供工作室网址标识。'], ['Action failed.', '操作失败。'],
    ['Support mode ended.', '支持模式已结束。'], ['Logout failed', '退出登录失败'],
    ['At least one registration question is required.', '报名表至少需要保留一个问题。'],
    ['At least one FAQ item is required.', '至少需要保留一条常见问答。'],
    ['Draft saved. Public pages have not changed.', '草稿已保存，公开页面尚未改变。'],
    ['Saved, but public publish verification failed.', '内容已保存，但公开发布验证失败。'],
    ['Previous version restored to draft. Review it before publishing.', '历史版本已恢复为草稿，请检查后再发布。'],
    ['Logo uploaded. Save Draft or Publish when you are ready.', 'Logo 已上传，确认后请保存草稿或发布。'],
    ['Apply this preset? It will replace the current theme, hero, registration copy, questions, and FAQs in the editor. Nothing becomes public until you publish.', '确定应用此预设吗？它会替换编辑器中的主题、首屏、报名文案、问题与常见问答；在您点击发布前，公开页面不会改变。'],
    ['Category preset applied.', '行业预设已应用。'],
    ['Category selected. Use “Apply Category Preset” only if you want to replace the current editor content.', '已选择行业类别。仅在需要替换当前编辑内容时使用“应用行业预设”。'],
    ['Category changed without replacing your custom content.', '行业类别已更改，您的自定义内容未被替换。'],
    ['Auto-filled', '已自动填写'], ['Auto-generated from studio name.', '根据工作室名称自动生成。'],
    ['Read-only after creation because it affects URLs, workspace paths, and media paths.', '创建后不可修改，因为它会影响网址、工作区路径和媒体路径。'],
    ['Use the More actions menu for pause, archive, restore, and permanent delete so confirmation phrases stay explicit.', '请从“更多操作”菜单执行暂停、归档、恢复和永久删除，以确保确认信息清楚明确。'],
    ['Alternate focused registration page for QR codes, campaigns, and direct links.', '适用于二维码、推广活动和直达链接的独立报名页面。'],
    ['Archived files remain as audit evidence', '归档文件会作为审计证据保留'],
    ['Are you sure you want to delete plan', '确定要删除此套餐吗'],
    ['Contact Section', '联系信息版块'],
    ['Contact email, billing email, Studio Admin login, onboarding status, and first 30-day trial period.', '设置联系邮箱、账单邮箱、工作室管理员登录、启用状态与首个 30 天试用期。'],
    ['Contrast and buttons', '对比度与按钮'],
    ['Daily operations: students, payments, check-ins, rosters, and portfolio work.', '日常运营：学员、收费、签到、排课与作品管理。'],
    ['Database snapshot', '数据库快照'], ['Hero Welcome', '首屏欢迎语'], ['Logo URL', 'Logo 网址'],
    ['Media folder copy', '媒体文件夹副本'], ['Media records are removed by tenant deletion', '删除工作室时会移除媒体记录'],
    ['Past Due', '已逾期'], ['Student Login Link', '学员登录链接'], ['Tenant database records', '工作室数据库记录'],
    ['The public home page parents see first: courses, gallery, contact, student lookup, and enrolment entry.', '家长首先看到的公开主页，包含课程、作品墙、联系信息、学员查询和报名入口。'],
    ['This control panel for how the studio appears externally. Operational editing stays in the CMS.', '此控制台负责工作室对外展示；日常运营编辑仍在 CMS 中完成。'],
    ['Workspace folder copy', '工作区文件夹副本'], ['tenant', '工作室'],
    // v7.6.0 gap fill (audit U7): Super Admin health labels, tenant detail
    // labels, onboarding checklist, risks, and modal/section strings that were
    // still English in the Chinese UI.
    ['Healthy', '状态良好'], ['Needs setup', '待完善设置'],
    ['Test fixture', '测试数据'], ['TEST FIXTURE', '测试数据'],
    ['No admin login', '无管理员登录'], ['Needs owner', '待指定负责人'],
    ['Paused', '已暂停'], ['Archived', '已归档'],
    ['Onboarding Checklist', '启用清单'], ['Risk / Setup', '风险与待办'],
    ['Quick Links', '快捷链接'], ['Health', '健康状态'],
    /* Tenant detail tabs. The view was one flat wall of cards with seven
       fields rendered twice; it is five tabs and a standing status bar now. */
    ['Subscription & Billing', '订阅与账单'], ['Contacts', '联系人'],
    ['Operations', '运维'], ['Subscription Period', '订阅周期'],
    ['Team Users', '团队账号'],
    /* Date rows. Written as label + number + unit so the dictionary has whole
       words to match — an interpolated "3 days left" matches nothing. */
    ['Trial ends', '试用结束'], ['Current period ends', '当前周期结束'],
    ['Cancellation / expiry', '取消或到期'],
    /* `Start` was the one date label that never got an entry, so the detail
       view showed it in English underneath four Chinese siblings. */
    ['Start', '开始'],
    /* Three readings, not two. A deadline that has passed is overdue; a start
       date that has passed is simply history, and colouring it red told the
       operator that every healthy studio needed attention. */
    ['days left', '天后到期'], ['days overdue', '天前已逾期'], ['days ago', '天前'],
    ['is before', '早于'],
    /* The settlement. Nothing in this product compared a subscription date to
       today until v8.2.30; these are the words for what it found. */
    ['Dates Passed', '已过期日期'],
    ['Subscription dates that have passed', '已经过期的订阅日期'],
    ['No subscription has passed a date it should not have.', '没有订阅超过它不该超过的日期。'],
    ['Nothing here has been changed. Applying moves only the rows marked Automatic; a lapsed trial is always a decision for a person.',
     '这里的内容都还没有被改动。执行只会移动标记为「可自动处理」的行；试用到期永远由人来决定。'],
    ['Automatic', '可自动处理'], ['Decide', '待决定'], ['Data', '数据问题'],
    ['The cancellation date has passed and the subscription is still open.', '取消日期已过，订阅仍处于开启状态。'],
    ['The billing period ended and the subscription is still marked active.', '计费周期已结束，订阅仍标记为正常。'],
    ['The trial ended. Convert the studio, extend the trial, or close it.', '试用已结束。请转为正式、延长试用，或关闭。'],
    ['Marked as trialing with no trial end date, so nothing can tell when it lapses.', '标记为试用中却没有试用结束日，因此无法判断何时到期。'],
    ['Applying…', '执行中…'],
    ['Subscription dates are unavailable. Refresh and try again.', '订阅日期数据不可用，请刷新后重试。'],
    ['Subscription start', '订阅开始'], ['Trial end', '试用结束'],
    ['Current period end', '当前周期结束'], ['Cancellation / expiry', '取消或到期'],
    ['A trialing subscription needs a trial end date.', '试用中的订阅必须填写试用结束日。'],
    ['A cancelled subscription needs a cancellation date.', '已取消的订阅必须填写取消日期。'],
    /* Derived status: shown as a badge with the audited route beside it,
       rather than as a disabled text box the operator cannot type into. */
    ['Follows the tenant lifecycle state above.', '跟随上方的工作室生命周期状态。'],
    ['Lifecycle changes are audited and happen in their own flow.', '生命周期变更有审计记录，在独立流程中进行。'],
    ['Change tenant status', '更改工作室状态'],
    ['Trial Ends', '试用结束日'],
    /* Date quick-set chips and validation. */
    ['Today', '今天'], ['+1 month', '+1 个月'], ['+1 year', '+1 年'], ['Clear', '清除'],
    ['Check the subscription dates.', '请检查订阅日期。'],
    ['Trial end is before the subscription start.', '试用结束早于订阅开始。'],
    ['Current period end is before the subscription start.', '当前周期结束早于订阅开始。'],
    ['Cancellation / expiry is before the subscription start.', '取消或到期日早于订阅开始。'],
    ['Saving…', '保存中…'],
    /* Plan editor: entitlements grouped by who feels them, publication first. */
    ['What the studio can publish', '工作室可以公开什么'],
    ['What the studio can send and take away', '工作室可以发送和带走什么'],
    ['What we commit to', '我们承诺什么'],
    ['Families can apply from the studio website without being invited.', '家长可以直接在工作室官网报名，无需邀请。'],
    ['Student work can be published with recorded guardian consent.', '在留痕的监护人授权下，学员作品可以公开展示。'],
    ['Reusable message templates in the operations CMS.', '运营 CMS 中可复用的消息模板。'],
    ['Students, credits and attendance can be exported as a spreadsheet.', '学员、课时与出勤可导出为表格。'],
    ['Ahead of the standard queue. This is a commitment we have to staff.', '优先于常规队列。这是需要我方投入人力的承诺。'],
    ['Flags not listed above', '上面没列出的开关'],
    ['none', '无'], ['set', '项已设置'],
    ['Must be a JSON object, for example {"beta_reports": true}', '必须是 JSON 对象，例如 {"beta_reports": true}'],
    ['Additional entitlements must be a JSON object.', '附加功能权限必须是 JSON 对象。'],
    ['Off by default. A plan exists as soon as it is created; it is for sale only when somebody says so.',
     '默认关闭。套餐创建后即存在，但只有明确发布后才对外销售。'],
    ['Only one plan carries the badge; ticking it here clears it elsewhere.', '推荐徽章只能有一个；在此勾选会清除其他套餐的标记。'],
    ['Not shown on the public pricing page.', '不会出现在公开定价页。'],
    ['Team users', '团队账号'],
    ['Storage (GB)', '存储（GB）'],
    ['Not configured', '未配置'],
    ['Pause, archive, restore and permanent delete live in the More actions menu, where each one asks for its own confirmation phrase.',
     '暂停、归档、恢复与永久删除都在「更多操作」菜单里，每一项都会单独要求输入确认短语。'],
    ['More actions', '更多操作'],
    ['Student Usage', '学员用量'], ['Storage Usage', '存储用量'],
    ['Workspace', '工作区'], ['Archive Path', '归档路径'], ['Created', '创建时间'],
    ['Billing', '账单'], ['Storage', '存储'],
    ['Owner assigned', '已指定负责人'], ['Studio Admin login configured', '已配置工作室管理员登录'],
    ['Owner has signed in', '负责人已登录'], ['Logo configured', '已配置 Logo'],
    ['Hero and contact ready', '首屏与联系信息已就绪'], ['Studio Website published', '工作室官网已发布'],
    ['No owner assigned', '未指定负责人'], ['Billing email missing', '缺少账单邮箱'],
    ['Website not published', '官网尚未发布'], ['Brand setup incomplete', '品牌设置未完成'],
    ['Owner has not signed in', '负责人尚未登录'], ['Subscription expired', '订阅已到期'],
    ['Storage near limit', '存储接近上限'], ['Student limit near limit', '学员数接近上限'],
    ['Surfaces disabled', '入口已停用'], ['Register paused', '报名已暂停'],
    ['Disabled', '已停用'], ['Limited', '受限'], ['Enabled', '已启用'],
    ['Tenant:', '工作室：'], ['Subscription:', '订阅：'], ['Access:', '访问：'],
    ['View', '查看'], ['View Details', '查看详情'], ['Edit Tenant', '编辑工作室'],
    ['Manage', '管理'], ['Open', '打开'], ['Support Mode', '支持模式'],
    ['Enter Support Mode', '进入支持模式'], ['Restore Tenant', '恢复工作室'],
    ['Pause Tenant', '暂停工作室'], ['Reactivate Tenant', '重新启用工作室'],
    ['Permanent Delete Tenant', '永久删除工作室'],
    ['Permanent Delete is available only after the tenant is archived.', '永久删除仅在工作室归档后可用。'],
    ['Archived or deleted tenants cannot be opened.', '已归档或已删除的工作室无法打开。'],
    ['Archived or deleted tenants cannot be supported.', '已归档或已删除的工作室无法进入支持模式。'],
    ['Registration is unavailable for paused, archived, or deleted tenants.', '已暂停、已归档或已删除的工作室不可报名。'],
    ['Studio Admin login is not configured.', '尚未配置工作室管理员登录。'],
    ['Open Studio Website', '打开工作室官网'], ['Portal', '官网'], ['Register', '报名'], ['Admin', '管理'],
    ['Add Plan', '新增套餐'], ['Edit Plan', '编辑套餐'], ['Delete Plan', '删除套餐'],
    ['? Public tenant pages stay present, but the tenant will be marked paused for operations and billing review.',
     '？公开页面会保留，但该工作室将被标记为暂停，用于运营与账单审查。'],
    ['? This restores active tenant status and subscription state.', '？这会恢复工作室的正常状态与订阅状态。'],
    ['? Tenant APIs become unavailable after snapshots are written.', '？快照写入后，该工作室的 API 将不可用。'],
    ['? This is irreversible for live tenant records.', '？此操作对在线工作室记录不可逆。'],
    ['No tenants match the current filters.', '没有符合当前筛选条件的工作室。'],
    ['No plans configured.', '尚未配置套餐。'], ['No audit logs yet.', '尚无审计日志。'],
    ['No immediate commercial risks.', '暂无需要立即关注的经营风险。'],
    ['Generating…', '正在生成…'], ['Logging in…', '正在登录…'],
    ['One-time link appears here', '一次性链接会显示在这里'],
    ['At least 8 characters', '至少 8 个字符'],
    ['Describe the customer request or incident reference', '请描述客户请求或事件编号'],
    ['Name, slug, owner, admin...', '名称、网址标识、负责人、管理员…'],
    ['Leave blank to keep existing password', '留空可保留现有密码'],
    ['Studio Owner', '工作室负责人'], ['Exit Support Mode', '退出支持模式'],
    // v7.6.0 dashboard revamp: attention alert rows and funnel widget now
    // render count badges and labels as separate nodes, so the labels are
    // plain dictionary keys instead of dynamic strings.
    ['payment follow-up', '付款跟进'], ['trials ending soon', '试用即将到期'],
    ['onboarding incomplete', '启用未完成'],
    ['Studio Websites', '工作室官网'],
    ['Quick Registration or campaigns', '快速报名或推广'],
    // Round 2 (2026-07-27, live-walkthrough fixes): plans table quota lines,
    // plan row actions, tenant detail quick links, support-gated navigation,
    // and audit timestamp formatting.
    ['Edit', '编辑'], ['trialing', '试用中'],
    ['Studio CMS', '运营 CMS'], ['Brand Workspace', '品牌工作区'],
    ['Studio Admin Login', '工作室管理员登录'],
    ['Public registration', '公开报名'], ['Student portfolio', '学员作品集'],
    ['Email templates', '邮件模板'], ['Data export', '数据导出'],
    ['Priority support', '优先支持'],
    ['No enabled entitlements', '未启用任何功能权限'],
    ['Open Portal', '打开官网'], ['Open Register', '打开报名'],
    ['Open-ended', '未设结束日'],
    ['Opens via Support Mode (audited).', '通过支持模式打开（操作会记入审计）。'],
    ['This page requires an active support session. It will open in a new tab after support mode starts.',
     '打开此页面需要有效的支持会话；支持模式开始后会在新标签页中打开。'],
    ['Support mode started — opening the tenant workspace.', '支持模式已开始，正在打开该工作室的页面。'],
    // Brand form inline validation (per-field errors shown under the input).
    ['Studio name is required.', '请填写工作室名称。'],
    ['Enter a valid email address, like studio@example.com.', '请输入有效的邮箱地址，例如 studio@example.com。'],
    ['Enter a valid phone number.', '请输入有效的电话号码。'],
    ['Enter a valid logo URL: a tenant asset path or a full https:// address.', 'Logo 网址无效：请使用租户资产路径或完整的 https:// 地址。'],
    ['Unknown timezone. Use an IANA name like Australia/Melbourne.', '时区无效：请使用 IANA 时区名称，例如 Australia/Melbourne。'],
    ['Enter a colour in #RRGGBB format.', '颜色格式应为 #RRGGBB。'],
    // Owner audit trail panel (Studio Admin analytics tab).
    ['Audit Trail', '操作审计'],
    ['Owner actions recorded for this studio: publishes, edits, exports, and support-mode activity.',
     '记录本工作室的管理操作：发布、修改、导出与支持模式活动。'],
    ['Filter by action', '按操作筛选'],
    ['Filter audit records by action', '按操作筛选审计记录'],
    ['Actor', '操作人'],
    ['Loading audit records…', '正在载入审计记录…'],
    ['No audit records yet.', '暂无审计记录'],
    ['Open this tab to load the audit trail.', '打开此页签后加载审计记录。'],
    /* v9.9.0. The table is the whole mechanism: a string that is not in
       it renders in English no matter what the switch says, and until now
       nothing checked. `test_admin_i18n_coverage.py` does. */
    ["Show the space and experience on the website", "在官网上显示「空间与体验」"],
    ["Show the principal on the website", "在官网上显示「主理人」"],
    ["Show selected work on the website", "在官网上显示「工作室作品」"],
    ["Show courses on the website", "在官网上显示「课程」"],
    ["Show the public timetable on the website", "在官网上显示「公开课表」"],
    ["Show student work on the website", "在官网上显示「学员作品」"],
    ["Show the FAQ on the website", "在官网上显示「常见问题」"],
    ["Show contact details on the website", "在官网上显示「联系方式」"],
    ["Show the student area on the website", "在官网上显示「学员专区」"],
    ["Shown on the website from", "是否在官网上显示，在"],
    ["The page is shown on the website from", "这个页面是否在官网上显示，在"],
    [". One switch, one place — two controls for one setting is one of them being wrong.", "里设置。一个开关只放一处——同一个设置有两个开关，就一定有一个是错的。"],
    [". Whether it takes requests is a separate decision, and it lives here.", "里设置。是否接受约课申请是另一个决定，放在这里。"],
    ["Principal", "主理人"],
    ["Who teaches here. This is the section that answers \"who am I trusting with my child\", so it is worth writing properly — and the section stays hidden until there is a biography to show.", "这里由谁来教。家长看这一段是在问「我要把孩子交给谁」，值得认真写——没有简介之前，这个版块不会公开。"],
    ["Eyebrow · English", "眉标题 · English"],
    ["Lead · English", "引导语 · English"],
    ["Description · English", "正文 · English"],
    ["Rename the public headings and their nav entries", "自定义公开页面的标题与导航文字"],
    ["Each name is both the heading on the public page and the entry in the navigation bar. The heading keeps whatever you write; the navigation entry is shortened past about 10 Chinese characters or 24 English ones, because the bar is one line tall.", "每个名称同时是公开页面上的版块标题和导航栏里的文字。标题保留你写的全部内容；导航文字超过约 10 个汉字或 24 个英文字符会被截断，因为导航条只有一行高。"],
    ["Changes since published", "与已发布版本的差异"],
    ["Public readiness", "公开就绪情况"],
    ["Publication state", "发布状态"],
    ["Checking public surfaces…", "正在检查公开页面…"],
    ["Checking…", "检查中…"],
    ["The write succeeded. Recheck the public pages; your saved content is safe while verification catches up.", "写入已经成功。请重新检查公开页面；在确认完成之前，你保存的内容是安全的。"],
    ["The preview on the right is private until you publish.", "右侧预览在发布之前只有你能看到。"],
    ["Preset applied to this draft.", "预设已应用到当前草稿。"],
    ["Live", "线上"],
    ["Source", "来源"],
    ["Footer", "页脚"],
    ["Space &amp; experience", "空间与体验"],
    ["Space & experience", "空间与体验"],
    ["This public module follows the welcome message and appears before the principal. Use it for the place, atmosphere, process, or online experience—not for the principal biography.", "这个公开版块排在欢迎语之后、主理人之前。用来介绍场地、氛围、上课流程或线上体验——不要写主理人简介。"],
    ["Add a title, description, photo, or highlight before this module can appear publicly.", "先填一个标题、一段正文、一张照片或一条亮点，这个版块才能公开。"],
    ["Photos", "照片"],
    ["Photo panel", "照片区"],
    ["Highlights", "亮点"],
    ["Three are recommended; all six stored highlights remain editable and are preserved on save.", "建议写三条；已保存的六条都可以继续编辑，保存时不会被删掉。"],
    ["Up to six. Drag-free move buttons set the lead order; the public page changes images only when a visitor chooses a thumbnail. Remove unlinks a photo from this module; it does not permanently delete the media file.", "最多六张。用移动按钮排序，不需要拖拽；公开页面只在访客点击缩略图时才换图。移除只是把照片从这个版块解除关联，不会真的删除文件。"],
    ["One filled language is used for both until you add the translation.", "只填一种语言时，两边都用它，直到你补上翻译。"],
    ["Secondary CTA destination", "次要按钮的去向"],
    ["Automatic · first ready destination", "自动 · 第一个已就绪的去处"],
    ["External link", "外部链接"],
    ["External destination URL", "外部链接地址"],
    ["Hide secondary action", "隐藏次要按钮"],
    ["Required only when External link is selected.", "只有选「外部链接」时才需要填。"],
    ["An explicit destination is hidden until its public content is ready; it never redirects somewhere else silently.", "指定的去处在其公开内容就绪之前会被隐藏；它不会悄悄跳到别处。"],
    ["Follow the visitor's device", "跟随访客设备"],
    ["Courses", "课程"],
    ["1 week", "1 周"],
    ["2 weeks", "2 周"],
    ["3 weeks", "3 周"],
    ["4 weeks", "4 周"],
    ["Upcoming statement", "即将开课"],
    ["Upcoming classes on their own page at", "接下来的公开课有自己的页面："],
    [", linked from the portal. A page rather than another band on the home page: a family reading a timetable is comparing rows against a calendar, which wants width and its own URL to share.", "，从官网导航进入。做成独立页面而不是首页上的又一条版块，是因为家长看课表时要一行行对着自己的日历比，这需要宽度，也需要一个能分享的网址。"],
    ["Only classes you have ticked", "只有你在 CMS 里勾选了"],
    ["“Show on the public timetable”", "「在公开课表上显示」"],
    ["in the CMS appear here — and only for as many weeks as you choose below. Nothing is published by simply being scheduled.", "的课才会出现在这里——而且只显示下面选定的周数。排了课并不等于公开。"],
    ["Booking asks only for a full name and a phone number — no account, no password. Requests arrive in the CMS under Pending and take a seat only once you approve them, so a request nobody has looked at never blocks a family who would actually turn up.", "约课只要姓名和手机号——不用注册，不用密码。申请会进入 CMS 的「待审核」，批准的那一刻才占座位，所以没人处理的申请不会挡住真的会来的家庭。"],
    ["Also the booking window: a date a visitor cannot see is a date they cannot ask for. Deliberately one number rather than two — two would drift apart, and a parent would be the one to find out.", "这同时也是约课的时间窗：访客看不到的日期就约不了。这里故意只有一个数字而不是两个——两个迟早会对不上，而最先发现的会是家长。"],
    ["Switched off hides a field; switched on shows it", "关掉就隐藏这一项；打开则在"],
    ["when there is something to show", "有内容时"],
    [". A class with no room recorded never prints an empty “Room”.", "才显示。没有填地点的课不会印出一个空的「地点」。"],
    ["A teacher’s name additionally needs that teacher’s own consent, set per person in the CMS under Settings → Team. Switching “Teacher” on here does not name anyone who has not agreed.", "公开老师姓名还需要老师本人同意，在 CMS 的「设置 → 团队」里逐人设置。在这里打开「老师」不会写出任何没有同意的人的名字。"],
    ["Studio URL slug", "工作室网址标识"],
    ["Use the slug from /<studio-slug>/studio-admin. Tenant-specific links lock this field.", "填 /<工作室标识>/studio-admin 里的那一段。从工作室专属链接进入时，这一项会被锁定。"],
    ["Loading attention queue…", "正在载入待处理事项…"],
    ["Make a decision from the workspace.", "在工作区里做决定。"],
    ["Select an attention item, tenant, plan, or audit event to inspect its state and next action.", "选择一条待处理事项、工作室、套餐或审计记录，查看它的状态和下一步。"],

    /* v9.9.5 — the strings the gate could not see until it learned to read
       template literals. Everything below is built by JavaScript at runtime;
       the runtime always translated it, nothing ever checked the words were
       here. */
    ["Basic info", "基础资料"],
    ["Owner & Contact", "负责人与联系方式"],
    ["Admin Login", "管理员登录"],
    ["Subscription & Plan", "订阅与套餐"],
    ["Limits & Works", "额度与作品"],
    ["Inherited from plan", "随套餐继承"],
    ["The studio's public address. It is on flyers and in QR codes, so it is changed on its own, not saved with this form.", "工作室的公开网址。它印在传单和二维码上，所以单独修改，不随这张表一起保存。"],
    ["Change public address", "修改公开网址"],
    ["Active works visible on the public showcase. Drafts and archived works remain stored.", "在公开作品墙上展示的作品数。草稿和已归档的作品仍然保留。"],
    ["The first 30-day trial is generated on create.", "首次 30 天试用在创建时自动生成。"],
    ["Change address", "修改网址"],
    ["New public address", "新的公开网址"],
    ["Lowercase letters, numbers and hyphens.", "只能用小写字母、数字和连字符。"],
    ["Type the current address to confirm", "输入当前网址以确认"],
    ["What changes", "会发生什么"],
    ["Keeps working", "不受影响"],
    ["The old address redirects to the new one permanently — printed QR codes do not need reprinting.", "旧网址会永久跳转到新网址——已经印好的二维码不用重印。"],
    ["Search engines take a few weeks to show the new address.", "搜索引擎通常要几周才会显示新网址。"],
    ["Visitors' saved language preference resets once.", "访客保存的语言偏好会重置一次。"],
    ["Signed-in staff are not logged out.", "已登录的员工不会被退出。"],
    ["Students, courses, work, schedules and media are untouched.", "学员、课程、作品、排课和媒体都不受影响。"],
    ["This studio cannot change its address again for a year.", "这间工作室一年之内不能再次修改网址。"],
    ["I have told this studio", "我已经通知过这间工作室"],
    ["Reset demonstration data", "重置演示数据"],
    ["Rebuild", "重建"],
    ["from the bundled demonstration content.", "，使用随程序打包的演示内容。"],
    ["Students, schedules, bookings and enquiries are deleted and re-created", "学员、排课、约课与报名咨询会被删除后重新生成"],
    ["Uploaded media for this tenant is deleted and re-uploaded from the manifest", "这间工作室已上传的媒体会被删除，并按清单重新上传"],
    ["Staff logins are reset to the shared demonstration password", "员工登录密码会重置为统一的演示密码"],
    ["The student access code is rotated", "学员访问码会重新生成"],
    ["No other tenant is read or written. This takes a few seconds.", "不会读写任何其他工作室。这个过程需要几秒钟。"],
    ["Type the confirmation phrase", "输入确认短语"],
    ["Stored in megabytes;", "以 MB 计；"],
    ["MB today.", "MB。"],
    ["Discard unsaved changes?", "放弃未保存的修改？"]
  ]);

  const originalText = new WeakMap();
  const renderedText = new WeakMap();
  const originalAttributes = new WeakMap();
  let language = localStorage.getItem('studiosaas_admin_language') === 'en' ? 'en' : 'zh';
  let observer;

  function translate(value) {
    const clean = String(value || '').replace(/\s+/g, ' ').trim();
    if (!clean || language === 'en') return clean;
    if (zh[clean]) return zh[clean];
    const rules = [
      // Super Admin dynamic strings (audit U7). Specific patterns come first
      // so the generic verb rules below cannot swallow them.
      [/^Page (\d+) of (\d+) · (\d+) tenants$/i, '第 $1 / $2 页 · 共 $3 个工作室'],
      [/^Page (\d+) of (\d+)$/i, '第 $1 / $2 页'],
      [/^(\d+) of (\d+) events$/i, '$1 / $2 条事件'],
      [/^Type (.+) to confirm\.?$/i, '请输入 $1 以确认。'],
      [/^Signed in: (.+)$/i, '已登录：$1'],
      /* studio-admin.html writes `Signed in as <email>`; the rule above
         was written for wording the page never produced, so the status
         line stayed English no matter which language was chosen. */
      [/^Signed in as (.+)$/i, '已登录：$1'],
      /* The six About highlights are generated as `Highlight 3 Body · 中文`,
         so a dictionary would need 24 entries to say one thing. The language
         marker stays English on purpose — it names the language of the
         content, exactly as the hand-written pairs above it do. */
      [/^Highlight (\d+) (Title|Body) · (中文|English)$/,
       (_m, index, part, lang) =>
         `亮点 ${index} ${part === 'Title' ? '标题' : '正文'} · ${lang}`],
      [/^(\d+) views · (\d+) registrations$/i, '$1 次浏览 · $2 次报名'],
      [/^View (.+)$/, '查看 $1'],
      [/^Last refreshed: (.+)$/i, '最近刷新：$1'],
      [/^Support (.+)$/i, '支持：$1'],
      [/^(.+) Details$/, '$1 · 详情'],
      [/^(.+) Actions$/, '$1 · 操作'],
      [/^(\d+) registrations$/i, '$1 次报名'],
      [/^(\d+) converted \((\d+)%\)$/i, '$1 次转化（$2%）'],
      [/^(\d+) \/ (\d+) students · (.+)$/i, '$1 / $2 名学员 · $3'],
      [/^(\d+) students · (.+)$/i, '$1 名学员 · $2'],
      [/^(\d+) students$/i, '$1 名学员'],
      [/^(\d+) users$/i, '$1 个用户'],
      [/^Students (\d+)% · (.+)$/i, '学员 $1% · $2'],
      [/^Storage (\d+)% · (.+)$/i, '存储 $1% · $2'],
      [/^Team users (\d+)% · (.+)$/i, '团队账号 $1% · $2'],
      [/^(.+) · no admin login$/i, '$1 · 无管理员登录'],
      [/^Inherited from (.+) plan\.$/i, '继承自「$1」套餐。'],
      [/^Tenant archived\. Snapshot: (.+)$/i, '工作室已归档。快照：$1'],
      [/^Final snapshot path: (.+)$/i, '最终快照路径：$1'],
      [/^Link created for (.+) \(expires in 24h\)$/i, '已为 $1 生成链接（24 小时后到期）'],
      [/^Failed to load data: (.+)$/i, '数据载入失败：$1'],
      [/^Loading…?$/i, '载入中…'],
      [/^Loading (.+)…$/i, '正在载入 $1…'],
      [/^No (.+) yet\.$/i, '尚无$1。'],
      [/^Open (.+)$/i, '打开 $1'],
      [/^Edit (.+)$/i, '编辑 $1'],
      [/^Save (.+)$/i, '保存 $1'],
      [/^Delete (.+)$/i, '删除 $1'],
      [/^Archive (.+)$/i, '归档 $1'],
      [/^Restore (.+)$/i, '恢复 $1'],
      [/^Failed to load (.+)$/i, '载入失败：$1']
    ];
    for (const [pattern, replacement] of rules) {
      if (pattern.test(clean)) return clean.replace(pattern, replacement);
    }
    return clean;
  }

  function isIgnored(node) {
    if (!node.parentElement) return true;
    if (/^(SCRIPT|STYLE|CODE|PRE|TEXTAREA)$/.test(node.parentElement.tagName)) return true;
    /* data-no-translate marks text that is already in its final language: the
       language switch itself, and content the page localised on its own. The
       industry cards print the Chinese name with the English one beneath it, and
       without this the dictionary turned "Language" into 语言 — so the card read
       「语言 / 语言」. */
    return Boolean(node.parentElement.closest('[data-admin-language-switch],[data-no-translate]'));
  }

  function applyText(node) {
    if (isIgnored(node)) return;
    const current = node.nodeValue;
    if (!originalText.has(node) || (renderedText.has(node) && current !== renderedText.get(node))) {
      originalText.set(node, current);
    }
    const source = originalText.get(node);
    const clean = String(source).replace(/\s+/g, ' ').trim();
    const leading = (String(source).match(/^\s*/) || [''])[0];
    const trailing = (String(source).match(/\s*$/) || [''])[0];
    const next = language === 'zh' && clean ? `${leading}${translate(clean)}${trailing}` : source;
    if (current !== next) {
      renderedText.set(node, next);
      node.nodeValue = next;
    } else {
      renderedText.set(node, current);
    }
  }

  /* An English-half field's placeholder is a sample of the CONTENT, not a
     label on the interface — so it must stay English even when the console is
     in Chinese. Until v8.7.0 it did not: "Founder & Principal" under
     「主理人头衔 · English」 rendered as 「创始人 / 主理人」, and every other
     `*En` field the same. The one job a placeholder has is to show what to
     type, and it was showing the wrong language to type in.

     Keyed on the id suffix rather than on a hand-applied attribute, because a
     hand-applied attribute is a thing to forget on the next bilingual pair.
     The `settingXxxEn` / `xxxEn<index>` convention is already load-bearing
     elsewhere in this console. `data-i18n-lock` stays as an escape hatch for
     anything that cannot follow it.

     `title` and `aria-label` are NOT locked: those really are interface
     chrome and should follow the console language. */
  const CONTENT_SAMPLE_FIELD = /En\d*$/;
  function keepsItsOwnLanguage(element, attr) {
    if (attr !== 'placeholder') return false;
    return element.hasAttribute('data-i18n-lock')
      || CONTENT_SAMPLE_FIELD.test(element.id || '');
  }

  function applyAttributes(element) {
    if (!originalAttributes.has(element)) originalAttributes.set(element, {});
    const originals = originalAttributes.get(element);
    for (const attr of ['placeholder', 'title', 'aria-label']) {
      if (!element.hasAttribute(attr)) continue;
      if (keepsItsOwnLanguage(element, attr)) continue;
      const current = element.getAttribute(attr);
      if (!(attr in originals) || current !== (element.dataset[`i18nRendered${attr.replace('-', '')}`] || originals[attr])) originals[attr] = current;
      const next = language === 'zh' ? translate(originals[attr]) : originals[attr];
      if (current !== next) element.setAttribute(attr, next);
      element.dataset[`i18nRendered${attr.replace('-', '')}`] = next;
    }
  }

  function localise(root) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) return applyText(root);
    if (![Node.ELEMENT_NODE, Node.DOCUMENT_NODE, Node.DOCUMENT_FRAGMENT_NODE].includes(root.nodeType)) return;
    if (root.nodeType === Node.ELEMENT_NODE) applyAttributes(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) applyText(node);
    if (root.querySelectorAll) root.querySelectorAll('[placeholder],[title],[aria-label]').forEach(applyAttributes);
  }

  function updateSwitch() {
    document.querySelectorAll('[data-admin-language]').forEach((button) => {
      const active = button.dataset.adminLanguage === language;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function setLanguage(next) {
    language = next === 'en' ? 'en' : 'zh';
    localStorage.setItem('studiosaas_admin_language', language);
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    localise(document);
    updateSwitch();
    document.dispatchEvent(new CustomEvent('studiosaas:admin-language', {detail: {language}}));
  }

  function installSwitch() {
    if (document.querySelector('[data-admin-language-switch]')) return;
    const holder = document.createElement('div');
    holder.dataset.adminLanguageSwitch = '';
    holder.className = 'admin-language-switch';
    holder.setAttribute('role', 'group');
    holder.setAttribute('aria-label', 'Language / 语言');
    holder.innerHTML = '<button type="button" data-admin-language="zh">中文</button><button type="button" data-admin-language="en">English</button>';
    const host = document.querySelector('.header-actions') || document.body;
    host.insertBefore(holder, host.firstChild);
    holder.addEventListener('click', (event) => {
      const button = event.target.closest('[data-admin-language]');
      if (button) setLanguage(button.dataset.adminLanguage);
    });
    updateSwitch();
  }

  /* Two fixed values survived the move to tokens and both are contrast pairs:
   * the selected label was `#fff` on var(--brand), which holds only while the
   * brand stays dark — on the eight dark theme-modes the accent is bright and
   * a white label measures 2.08:1. --on-accent is the token solved against the
   * accent for exactly this (5.83:1 at worst). The focus ring read --brand,
   * which is solved as a TEXT colour against the page; --focus-ring is the one
   * solved to clear 3:1 against every surface it can land on (3.86:1 on
   * --panel, 3.55:1 on --bg at worst).
   *
   * v8.4.0: and then the hardcoded FALLBACKS bit, which is the more
   * interesting half. This rule said `var(--brand, #3b82f6)`. When the
   * consoles stopped declaring --brand and started declaring --accent, the
   * token resolved to nothing and CSS did what it is supposed to do: it used
   * the fallback. So the language switch went on painting itself Tailwind
   * blue-500 in the middle of a navy-and-warm-paper console, silently, with
   * every contrast assertion still green — because the assertions read the
   * stylesheet, and this string lives in a JavaScript file.
   *
   * A fallback is a hardcoded colour with a longer fuse. These now point at
   * the token one layer up rather than at a literal, so a missing token
   * degrades to another token and finally to a neutral that belongs to no
   * palette in particular. */
  function installStyles() {
    const style = document.createElement('style');
    style.textContent = '.admin-language-switch{display:inline-flex;align-items:center;gap:3px;padding:5px;border:1px solid var(--line,var(--ui-border));border-radius:999px;background:var(--panel,var(--ui-surface));white-space:nowrap}.admin-language-switch button{border:0;background:transparent;color:var(--muted,var(--ui-muted));padding:6px 10px;border-radius:999px;font:inherit;font-size:13px;font-weight:800;cursor:pointer;min-height:44px}.admin-language-switch button.active{background:var(--accent,var(--brand-accent));color:var(--on-accent,var(--brand-on-accent))}.admin-language-switch button:focus-visible{outline:2px solid var(--focus-ring,var(--accent,var(--brand-accent)));outline-offset:2px}';
    document.head.appendChild(style);
  }

  function wrapDialogs() {
    const nativeAlert = window.alert.bind(window);
    const nativeConfirm = window.confirm.bind(window);
    const nativePrompt = window.prompt.bind(window);
    window.alert = (message) => nativeAlert(language === 'zh' ? translate(message) : message);
    window.confirm = (message) => nativeConfirm(language === 'zh' ? translate(message) : message);
    window.prompt = (message, value) => nativePrompt(language === 'zh' ? translate(message) : message, value);
  }

  function start() {
    installStyles();
    installSwitch();
    wrapDialogs();
    setLanguage(language);
    observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        if (mutation.type === 'characterData') {
          if (renderedText.get(mutation.target) === mutation.target.nodeValue) continue;
          applyText(mutation.target);
        }
        /* A mounted element keeps its identity while the console rewrites
           its label — the tenant rows re-announce `View <tenant>` on every
           refresh. Without this branch those values were localised once, at
           insertion, and every later one stayed English for screen readers. */
        if (mutation.type === 'attributes') applyAttributes(mutation.target);
        mutation.addedNodes.forEach(localise);
      }
      updateSwitch();
    });
    observer.observe(document.body, {
      subtree: true, childList: true, characterData: true,
      /* Filtered on purpose: applyAttributes stamps its result in a data-
         attribute, and an unfiltered watch would call itself back forever. */
      attributes: true, attributeFilter: ['placeholder', 'title', 'aria-label'],
    });
  }

  window.AdminI18n = {get language() { return language; }, setLanguage, translate: (value) => language === 'zh' ? translate(value) : value, localise};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
