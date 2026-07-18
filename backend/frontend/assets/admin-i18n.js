/* Chinese/English UI switch shared by Studio Admin and Super Admin.
 * Business values and API enums stay in English; only user-facing copy changes.
 */
(function () {
  'use strict';

  const zh = Object.fromEntries([
    ['PWE Studio SaaS · Super Admin', 'PWE Studio SaaS · 平台管理'],
    ['PWE Studio SaaS · Studio Admin', 'PWE Studio SaaS · 工作室管理'],
    ['Super Admin Login', '平台管理员登录'], ['Studio Admin Login', '工作室管理员登录'],
    ['Super Admin', '平台管理'], ['Studio Admin', '工作室管理'],
    ['Super Admin sections', '平台管理页面'], ['Studio Admin sections', '工作室管理页面'],
    ['Login', '登录'], ['Logout', '退出登录'], ['Email', '邮箱'], ['Password', '密码'],
    ['Enter your password', '请输入密码'], ['Remember me for 30 days', '30 天内保持登录'],
    ['Current Password', '当前密码'], ['New Password', '新密码'], ['Confirm New Password', '确认新密码'],
    ['Change Password', '修改密码'], ['Update Password', '更新密码'], ['Not signed in', '尚未登录'],
    ['Last Login', '最近登录'], ['Login Status', '登录状态'],
    ['Overview', '总览'], ['Tenants', '工作室'], ['Plans', '套餐'], ['Audit Logs', '审计日志'],
    ['Analytics', '数据分析'], ['Brand', '品牌'], ['Hero', '首屏'], ['Registration', '报名'],
    ['Public Pages', '公开页面'], ['Preview / Publish', '预览与发布'], ['Website / Brand', '官网与品牌'],
    ['Manage tenants, plans, subscriptions, and platform analytics', '管理工作室、套餐、订阅与平台数据'],
    ['Manage studios, subscriptions, and safe operational state', '管理工作室、订阅与安全运营状态'],
    ['Tenant lifecycle, recurring revenue, activation, and platform usage', '工作室生命周期、经常性收入、启用情况与平台用量'],
    ['Tenants & Subscriptions', '工作室与订阅'], ['Plans & Pricing', '套餐与定价'],
    ['Pricing and platform limits available to tenants', '面向工作室的价格与平台额度'],
    ['Commercial Overview', '经营总览'], ['Commercial Attention', '经营关注事项'],
    ['30-Day Acquisition Funnel', '近 30 天获客漏斗'], ['Recent platform activity', '近期平台活动'],
    ['Recent platform activity and operator changes', '近期平台活动与管理员变更'],
    ['Total Tenants', '工作室总数'], ['Paid Tenants', '付费工作室'], ['Trial Tenants', '试用工作室'],
    ['Trials Ending in 7 Days', '7 天内到期试用'], ['MRR (AUD)', '月度经常性收入（澳元）'],
    ['New in 30 Days', '近 30 天新增'], ['Search Tenants', '搜索工作室'],
    ['All Categories', '全部类别'], ['All Plans', '全部套餐'], ['All Statuses', '全部状态'],
    ['Show test tenants', '显示测试工作室'], ['Clear Filters', '清除筛选'],
    ['+ Add Tenant', '+ 新增工作室'], ['Add Tenant', '新增工作室'], ['Create Tenant', '创建工作室'],
    ['+ Add Plan', '+ 新增套餐'], ['Save Plan', '保存套餐'], ['Save Changes', '保存更改'],
    ['Tenant', '工作室'], ['Tenant Status', '工作室状态'], ['Subscription Status', '订阅状态'],
    ['Subscription', '订阅'], ['Subscription metadata', '订阅资料'], ['Subscription Start', '订阅开始'],
    ['Current Period Ends', '当前周期结束'], ['Cancellation / Expiry Date', '取消或到期日'],
    ['Changed together with tenant lifecycle state.', '此项会随工作室生命周期状态一起变更。'],
    ['Use More → Status for audited lifecycle actions.', '请使用“更多 → 状态”执行带审计记录的生命周期操作。'],
    ['Name', '名称'], ['Studio', '工作室'], ['Studio Name', '工作室名称'], ['Studio Category', '工作室类别'],
    ['Category', '类别'], ['Slug', '网址标识'], ['Code', '代码'], ['Status', '状态'], ['Plan', '套餐'],
    ['Price (AUD)', '价格（澳元）'], ['Price/Month', '月费'], ['Limits', '额度'], ['Entitlements', '功能权限'],
    ['Additional entitlements (JSON)', '其他功能权限（JSON）'],
    ['Only use this for feature flags not listed above.', '仅用于上方未列出的功能开关。'],
    ['Student Limit', '学员上限'], ['Admin User Limit', '管理员上限'], ['Storage Limit', '存储上限'],
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
    ['Previous', '上一页'], ['Next', '下一页'], ['Page 1', '第 1 页'], ['More', '更多'],
    ['Close', '关闭'], ['Cancel', '取消'], ['Delete', '删除'], ['Archive', '归档'], ['Pause', '暂停'],
    ['Reactivate', '重新启用'], ['Reset Password', '重置密码'], ['Danger Zone', '危险操作区'],
    ['Archive Tenant', '归档工作室'], ['Permanent Delete', '永久删除'], ['Permanently delete', '永久删除'],
    ['Type tenant slug to confirm', '输入工作室网址标识以确认'], ['Reason', '原因'],
    ['Every support-mode action is audited against this reason.', '支持模式内的每项操作都会连同此原因写入审计记录。'],
    ['Start Support Mode', '进入支持模式'], ['Surfaces', '各使用入口'], ['Website', '官网'],
    ['Onboarding', '启用进度'], ['Basic', '基础版'],
    ['active', '正常'], ['paused', '已暂停'], ['archived', '已归档'], ['deleted', '已删除'],
    ['trial', '试用'], ['past_due', '逾期'], ['cancelled', '已取消'], ['lead', '潜在客户'],
    ['onboarding', '启用中'],
    ['Shape the public studio experience', '打造工作室的公开品牌体验'],
    ['Logo, colours, public copy, registration fields, and parent-facing presentation', '管理 Logo、颜色、公开文案、报名字段与家长端展示'],
    ['Edit brand, hero, website sections, registration questions, and FAQs with a live preview before publishing to the tenant portal and register page.', '编辑品牌、首屏、官网版块、报名问题与常见问答；发布前可实时预览。'],
    ['Brand Builder', '品牌设计'], ['Brand foundation', '品牌基础'],
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
    ['Type', '类型'], ['Required', '必填'], ['Optional', '选填'], ['Required / Options', '必填与选项'],
    ['Remove', '移除'], ['Short text, long text, and select fields are supported.', '支持短文本、长文本和下拉选择字段。'],
    ['FAQ', '常见问答'], ['Questions shown near the bottom of the public portal.', '这些问题会显示在公开官网底部附近。'],
    ['Add FAQ', '新增常见问答'], ['Answer', '答案'], ['Preview and publish', '预览与发布'],
    ['Theme Preview', '主题预览'], ['Desktop', '桌面'], ['Mobile', '手机'], ['Save Draft', '保存草稿'],
    ['Publish', '发布'], ['Publication history', '发布历史'],
    ['No published versions yet.', '尚无已发布版本。'],
    ['Restore a previous publication into the draft, review it in the preview, then publish when ready.', '可将历史版本恢复为草稿，预览确认后再发布。'],
    ['No unsaved changes', '没有未保存的更改'], ['Saved', '已保存'], ['Refresh', '刷新'],
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
    ['Loading lifecycle risks…', '正在载入生命周期风险…'], ['Loading registration conversion…', '正在载入报名转化…'],
    ['Please log in with a Super Admin account.', '请使用平台管理员账号登录。'],
    ['Please log in to continue.', '请登录后继续。'], ['Email and password are required.', '请输入邮箱和密码。'],
    ['Logged in.', '登录成功。'], ['Logged out.', '已退出登录。'],
    ['Too many login attempts — please wait a minute and try again.', '登录尝试过多，请稍等一分钟后再试。'],
    ['Invalid email or password.', '邮箱或密码错误。'], ['New passwords do not match.', '两次输入的新密码不一致。'],
    ['Password updated.', '密码已更新。'], ['Current password is incorrect.', '当前密码不正确。'],
    ['A reason is required to enter support mode.', '进入支持模式前必须填写原因。'],
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
    ['Workspace folder copy', '工作区文件夹副本'], ['tenant', '工作室']
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
    return !node.parentElement || /^(SCRIPT|STYLE|CODE|PRE|TEXTAREA)$/.test(node.parentElement.tagName) || node.parentElement.closest('[data-admin-language-switch]');
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

  function applyAttributes(element) {
    if (!originalAttributes.has(element)) originalAttributes.set(element, {});
    const originals = originalAttributes.get(element);
    for (const attr of ['placeholder', 'title', 'aria-label']) {
      if (!element.hasAttribute(attr)) continue;
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

  function installStyles() {
    const style = document.createElement('style');
    style.textContent = '.admin-language-switch{display:inline-flex;align-items:center;gap:2px;padding:3px;border:1px solid var(--line,#e2e8f0);border-radius:999px;background:var(--surface,#fff);white-space:nowrap}.admin-language-switch button{border:0;background:transparent;color:var(--muted,#64748b);padding:6px 10px;border-radius:999px;font:inherit;font-size:12px;font-weight:800;cursor:pointer;min-height:30px}.admin-language-switch button.active{background:var(--brand,#3b82f6);color:#fff}.admin-language-switch button:focus-visible{outline:2px solid var(--brand,#3b82f6);outline-offset:2px}';
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
        mutation.addedNodes.forEach(localise);
      }
      updateSwitch();
    });
    observer.observe(document.body, {subtree: true, childList: true, characterData: true});
  }

  window.AdminI18n = {get language() { return language; }, setLanguage, translate: (value) => language === 'zh' ? translate(value) : value, localise};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once: true});
  else start();
})();
