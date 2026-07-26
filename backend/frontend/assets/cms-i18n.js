/* Chinese/English UI switch for the CMS.
 *
 * The CMS was the only one of the four surfaces with no i18n at all: the portal
 * and register page are bilingual, Studio Admin and Super Admin run through
 * admin-i18n.js, and the CMS was Chinese-only. A studio owner uses the CMS and
 * Studio Admin on the same day, so they had to read both languages — and an
 * owner who reads neither could not use one of the two.
 *
 * This is admin-i18n.js run in the other direction: the source strings in
 * cms-app.jsx are Chinese, so the dictionary maps zh → en and a MutationObserver
 * localises React's output as it renders. Doing it here rather than threading a
 * T() through 4,600 lines of JSX keeps one translation table to maintain and
 * leaves the component tree untouched.
 *
 * The language choice is shared with the other surfaces through the same
 * `studiosaas_admin_language` key, so switching in Studio Admin and opening the
 * CMS keeps the language the operator picked.
 *
 * Business values and API enums stay as they are; only user-facing copy moves.
 * An unlisted string falls through to Chinese rather than to an empty box.
 */
(function () {
  'use strict';

  const en = Object.fromEntries([
    /* ── Navigation and shell ── */
    ['工作台', 'Dashboard'], ['每日排课', 'Daily Roster'], ['学员档案', 'Students'],
    ['待审核', 'Pending'], ['充值结算', 'Credits'], ['操作日志', 'Activity Log'],
    ['经营统计', 'Business Stats'], ['排课', 'Roster'], ['档案', 'Students'],
    ['审核', 'Review'], ['充值', 'Top-up'], ['日志', 'Log'], ['统计', 'Stats'],
    ['设置', 'Settings'], ['刷新', 'Refresh'], ['刷新数据', 'Refresh data'],
    ['已连接', 'Connected'], ['连接中...', 'Connecting…'], ['连接失败', 'Connection failed'],
    ['重新连接', 'Reconnect'], ['重试', 'Retry'], ['备份导出', 'Export backup'],
    ['退出登录', 'Log out'], ['全局搜索', 'Global search'], ['回到顶部', 'Back to top'],

    /* ── Login and session ── */
    ['请输入 Studio CMS 账号', 'Sign in to the Studio CMS'],
    ['管理员邮箱', 'Admin email'], ['密码', 'Password'], ['进入系统 →', 'Sign in →'],
    ['登录中…', 'Signing in…'], ['邮箱或密码错误', 'Incorrect email or password'],
    ['清除', 'Clear'], ['清除选择', 'Clear selection'],
    ['上一页', 'Previous'], ['下一页', 'Next'],
    ['复制续课提醒', 'Copy renewal reminders'], ['批量归档', 'Archive selected'],
    ['所选学员均已归档', 'Every selected student is already archived'],

    /* ── Student form ── */
    ['First Name (名) *', 'First name *'], ['Last Name (姓)', 'Last name'],
    ['First Name 不能为空', 'First name is required'],
    ['照片 Photo', 'Photo'], ['如 wechat_id', 'e.g. wechat_id'],
    ['归档学员', 'Archive student'], ['恢复学员', 'Restore student'],
    ['（已用完）', ' (none left)'],
    ['确认归档', 'Confirm archive'], ['确认恢复', 'Confirm restore'],
    ['移入归档库', 'Moved to the archive'], ['从归档库恢复', 'Restored from the archive'],
    ['批量移入归档库', 'Bulk archived'],

    /* ── Reports ── */
    ['完成作品', 'Pieces completed'], ['生日', 'Birthday'],
    ['祝', 'Happy birthday to'],
    ['生日快乐！愿新的一年里画艺大进，心想事成！',
     'Happy birthday — wishing you a year of progress and everything you hope for.'],
    ['经营真账（估算）', 'Live revenue (estimated)'],
    ['经营月报（近 6 个月）', 'Monthly report (last 6 months)'],
    ['近 6 个月上课足迹', 'Attendance, last 6 months'],
    ['转为每周班次', 'Make it a weekly class'],

    /* ── Maintenance ── */
    ['服务器还在运行旧版本', 'The server is still running an older version'],
    ['1. 用新版 server.py 覆盖 CMS 目录里的旧文件',
     '1. Replace the old server.py in the CMS directory with the new one'],
    ['2. 终端运行 ./cms.sh restart', '2. Run ./cms.sh restart in your terminal'],
    ['3. 刷新本页面', '3. Reload this page'],
    ['需要 Gmail「应用专用密码」，获取方法见《邮件设置教程》文档',
     'Requires a Gmail app-specific password — see the email setup guide.'],
    ['收件邮箱', 'Recipient email'], ['发件 Gmail 地址', 'Sender Gmail address'],
    ['Gmail 应用专用密码', 'Gmail app-specific password'],
    ['已保存，留空不变', 'Saved — leave blank to keep it'],
    ['16 位应用专用密码', '16-character app password'],

    /* ── Common actions ── */
    ['确认', 'Confirm'], ['取消', 'Cancel'], ['保存', 'Save'], ['删除', 'Delete'],
    ['编辑', 'Edit'], ['复制', 'Copy'], ['归档', 'Archive'], ['移出', 'Remove'],
    ['详情', 'Details'], ['更多', 'More'], ['加入', 'Add'], ['选择', 'Choose'],
    ['更换', 'Replace'], ['撤回', 'Withdraw'], ['继续', 'Continue'],
    ['知道了 / OK', 'Got it / OK'], ['上传中...', 'Uploading…'], ['加载中…', 'Loading…'],
    ['暂无数据', 'No data yet'], ['无记录', 'No records'], ['无匹配', 'No match'],
    ['查看 →', 'View →'], ['处理 →', 'Handle →'], ['全部 →', 'All →'],
    ['+ 添加套餐', '+ Add pack'], ['新建', 'New'], ['新建学员', 'New student'],
    ['新建学员档案', 'New student record'], ['新增班次', 'Add class'],
    ['关闭', 'Close'],
    ['添加学员', 'Add student'], ['添加团队成员', 'Add team member'],

    /* ── Fields ── */
    ['姓名', 'Name'], ['学员', 'Student'], ['电话', 'Phone'], ['邮箱', 'Email'],
    ['微信', 'WeChat'], ['微信号', 'WeChat ID'], ['备注', 'Notes'],
    ['入学日期', 'Join date'], ['选填', 'optional'], ['选填 / Optional', 'Optional'],
    ['自定义', 'Custom'], ['未设置', 'Not set'], ['未记录', 'Not recorded'],
    ['当前余额', 'Current balance'], ['课时余额', 'Credit balance'], ['剩余课时', 'Credits remaining'],
    ['初始课时', 'Starting credits'], ['初始课时数', 'Starting credits'],
    ['课时数 *', 'Credits *'], ['实收金额 (AUD) *', 'Amount received (AUD) *'],
    ['付款方式', 'Payment method'], ['现金', 'Cash'], ['银行转账', 'Bank transfer'],
    ['其他', 'Other'], ['人', ''], ['至', 'to'], ['时间', 'Time'], ['操作', 'Action'],
    ['变动', 'Change'], ['月份', 'Month'], ['营收', 'Revenue'], ['消课', 'Credits used'],
    ['充值次数', 'Top-ups'], ['周期', 'Period'], ['合计:', 'Total:'], ['筛选:', 'Filter:'],
    ['均价/课', 'Avg / class'], ['均价/课:', 'Avg / class:'], ['消课:', 'Used:'],
    ['拍照', 'Take photo'], ['图片加载失败', 'Image failed to load'],

    /* ── Dashboard ── */
    ['学员总数', 'Total students'], ['全部剩余课时', 'Outstanding credits'],
    ['已签到', 'Checked in'], ['低课时', 'Low credits'], ['总营收', 'Total revenue'],
    ['项', ' pending'],
    ['TODAY · 今日指挥台', 'TODAY · Command deck'],
    ['先处理最需要行动的事项', 'Start with what needs action first'],
    ['今日排课', "Today's roster"], ['审核报名', 'Review registrations'],
    ['今日待办', 'To do today'],
    ['有待审核的注册申请', 'Registrations are waiting for review'],
    ['最近操作', 'Recent activity'], ['应到', 'Expected'], ['✓ 已签', '✓ Checked in'],
    ['余额告急', 'Low balance'], ['催费', 'Send reminder'],

    /* ── Roster ── */
    ['每周课表', 'Weekly schedule'],
    ['固定班次按周几自动排入当日名单', 'Recurring classes are added to the day roster automatically'],
    ['还没有固定班次。例如「周三 16:00 素描班」——保存后每周三会自动出现在当日排课里。',
     'No recurring classes yet. Add one — for example "Wed 16:00" — and it will appear on that weekday automatically.'],
    ['班次名称', 'Class name'], ['周几', 'Weekday'], ['开始时间', 'Start time'],
    ['容量', 'Capacity'], ['加入班次', 'Join class'], ['课程日期', 'Class date'],
    ['今天', 'Today'], ['班组模板', 'Group templates'],
    ['-- 选择模板 --', '-- Choose a template --'], ['-- 选择学员 --', '-- Choose a student --'],
    ['套用到当前日期', 'Apply to this date'], ['保存当前为模板', 'Save as template'],
    ['日报', 'Daily report'],
    ['批量提醒', 'Bulk reminder'], ['批量签到/消课', 'Bulk check-in'],
    ['上课签到', 'Check in'], ['今日暂无排课', 'Nothing scheduled today'],
    ['保存班组模板', 'Save group template'], ['模板名称', 'Template name'],
    ['保存模板', 'Save template'], ['删除模板', 'Delete template'],
    ['当前日期没有排课可保存', 'There is no roster on this date to save'],
    ['模板学员均已在当前排课中', 'Every student in the template is already on this roster'],
    ['请选择学员', 'Please choose a student'],

    /* ── Students ── */
    ['学员档案', 'Students'], ['活跃', 'Active'], ['低频', 'Infrequent'],
    ['流失风险', 'At risk'], ['CSV', 'CSV'],
    ['搜索姓名 / 电话 / 微信 / 邮箱…（回车打开唯一匹配）',
     'Search name / phone / WeChat / email… (Enter opens a single match)'],
    ['搜索学员', 'Search students'], ['精确筛选学员…', 'Filter students…'],
    ['或输入关键字搜索…', 'Or search by keyword…'],
    ['搜索学员姓名、电话、微信号...', 'Search student name, phone or WeChat…'],
    ['输入姓名、手机号或微信号搜索', 'Search by name, mobile or WeChat ID'],
    ['未找到匹配学员', 'No matching student'], ['无匹配学员', 'No matching student'],
    ['试试调整搜索词或筛选条件', 'Try a different search term or filter'],
    ['全部', 'All'], ['有余额', 'Has credits'], ['已清零', 'Zero'], ['归档库', 'Archived'],
    ['名 A→Z', 'First name A→Z'], ['名 Z→A', 'First name Z→A'],
    ['姓 A→Z', 'Last name A→Z'], ['姓 Z→A', 'Last name Z→A'],
    ['课时 高→低', 'Credits high→low'], ['课时 低→高', 'Credits low→high'],
    ['最近活跃', 'Recently active'], ['最近上课', 'Last class'], ['上课记录', 'Class history'],
    ['确认建档', 'Create record'], ['继续建档', 'Create anyway'],
    ['复制全部提醒话术', 'Copy all reminder messages'],
    ['点击复制生日祝福话术', 'Click to copy the birthday message'],
    ['复制祝福 →', 'Copy greeting →'], ['祝福语已复制', 'Greeting copied'],
    ['学员个人分析', 'Student analysis'],
    ['选择一名学员查看个人数据', 'Choose a student to see their data'],

    /* ── Pending registrations ── */
    ['暂无待审核申请', 'No registrations waiting'],
    ['学员通过注册页面提交后会显示在这里', 'Submissions from the registration page appear here'],
    ['留言', 'Message'], ['下次跟进', 'Next follow-up'], ['已联系', 'Contacted'],
    ['已约试听', 'Trial booked'], ['继续跟进', 'Keep following up'],
    ['拒绝', 'Reject'], ['批准建档', 'Approve'], ['确认拒绝', 'Confirm rejection'],
    ['拒绝原因（将随通知邮件发送给家长，可留空）',
     'Reason for rejection (sent to the family by email; may be left blank)'],
    ['可留空', 'Optional'], ['新生注册', 'New registration'], ['批准注册', 'Registration approved'],
    ['管理员拒绝注册申请', 'Rejected by an administrator'],

    /* ── Credits and refunds ── */
    ['充值 & 结算', 'Credits & settlement'], ['充值购课', 'Buy credits'],
    ['退款退课', 'Refund'], ['退课节数 *', 'Credits to remove *'],
    ['退款金额 (AUD) *', 'Refund amount (AUD) *'], ['退款方式', 'Refund method'],
    ['退款原因 *', 'Reason for refund *'], ['套餐快选', 'Quick pack'],
    ['当前角色无退款权限', 'Your role cannot issue refunds'],
    ['充值套餐管理', 'Credit packs'], ['课时资产池', 'Outstanding credits'],
    ['常规课程消耗', 'Regular class'], ['管理员撤销', 'Reversed by administrator'],
    ['管理端校准', 'Adjusted by administrator'],
    ['退款金额将以负数计入营收（净额自动核减）；退课节数直接从剩余课时扣减。此操作会记入账本与操作日志。',
     'The refund is recorded as negative revenue and the credits come straight off the balance. Both the ledger and the activity log record it.'],

    /* ── Logs and stats ── */
    ['全部操作', 'All actions'], ['日期范围', 'Date range'], ['所有年份', 'All years'],
    ['自定义范围', 'Custom range'], ['建档学员', 'Students on file'],
    ['历史总营收', 'Total revenue'], ['累计消课', 'Credits used'], ['全局数据', 'All time'],
    ['近 12 个月营收 (AUD)', 'Revenue, last 12 months (AUD)'],
    ['近 12 个月消课次数', 'Credits used, last 12 months'],
    ['付款方式分布', 'Payment methods'], ['经营月报（近 6 个月）', 'Monthly report (last 6 months)'],
    ['导出 CSV', 'Export CSV'], ['新学员', 'New students'],
    ['课包销量排行（历史累计）', 'Pack sales (all time)'], ['暂无充值记录', 'No top-ups yet'],
    ['消课节奏（近 180 天）', 'Usage pace (last 180 days)'], ['天/次', 'days per class'],
    ['财务明细报表', 'Financial detail'], ['入账流水', 'Receipts'],
    ['暂无记录', 'No records yet'], ['签到与充值后这里会出现流水', 'Check-ins and top-ups appear here'],

    /* ── Student area and consent ── */
    ['学员专区', 'Student area'], ['专区', 'Area'],
    ['姓名、手机与独立 6 位访问码验证；访问码不会保存明文。',
     'Verified by name, mobile and a 6-digit access code. The code is never stored in plain text.'],
    ['请先补充学员手机号码，再生成访问码。', 'Add the student\'s mobile number before issuing an access code.'],
    ['仅显示一次，请立即安全交给家长或成年学员',
     'Shown once only — pass it to the family or adult student through a secure channel now'],
    ['高级操作', 'Advanced'],
    ['停用后，当前访问码和所有已登录会话会立即失效。',
     'Disabling immediately invalidates the access code and every signed-in session.'],
    ['停用学员专区', 'Disable student area'],
    ['官网作品公开授权', 'Public display consent'],
    ['授权与撤回均追加为不可覆盖的审计记录。',
     'Both consent and withdrawal are appended as immutable audit records.'],
    ['授权人：', 'Consent given by:'], ['与学员关系 *', 'Relationship to student *'],
    ['监护人', 'Guardian'], ['本人', 'Self'], ['其他授权人', 'Other authorised person'],
    ['授权方式 *', 'How consent was given *'], ['书面确认', 'In writing'],
    ['电子确认', 'Electronically'], ['当面确认', 'In person'], ['记录授权', 'Record consent'],
    ['撤回并下架', 'Withdraw and unpublish'],
    ['确认后，该学员当前所有官网公开作品会立即下架，私人作品仍保留。',
     'Everything this student has on the public site is unpublished immediately. Private records are kept.'],
    ['家长可见', 'Visible to family'], ['展示到官网作品墙', 'Show on the public gallery'],
    ['老师评语', "Teacher's note"], ['老师寄语', 'A note from the teacher'],

    /* ── Reports ── */
    ['学员成长报告 · Growth Report', 'Growth report'],
    ['复制成长寄语', 'Copy the growth note'], ['保存为 PDF / 打印', 'Save as PDF / print'],
    ['累计上课', 'Classes attended'], ['陪伴天数', 'Days with us'],

    /* ── Settings ── */
    ['系统设置', 'Settings'],
    ['打开 Studio Admin 管理公开门户、注册表字段、品牌文案和页面展示',
     'Open Studio Admin to manage the public site, registration fields, brand copy and page layout'],
    ['网站、Logo、配色与注册表设置 →', 'Website, logo, colours and registration form →'],
    ['团队与权限', 'Team & permissions'],
    ['Owner管理团队；Manager负责日常运营，Teacher负责签到与作品，Front Desk负责报名、学员与课时。',
     'Owner manages the team. Manager runs daily operations, Teacher handles check-ins and work, Front Desk covers registrations, students and credits.'],
    ['当前角色可查看团队；只有 Owner 可以新增、停用或更改成员角色。',
     'Your role can view the team. Only an Owner can add, disable or change members.'],
    ['修改登录密码', 'Change password'], ['启用屏幕锁（PIN）', 'Screen lock (PIN)'],
    ['关闭时「锁定」= 退出登录', 'With this off, "Lock" signs you out'],
    ['修改 PIN 码', 'Change PIN'], ['更新 PIN', 'Update PIN'],
    ['未到访预警天数', 'Inactivity warning (days)'],
    ['排课数据清理', 'Roster cleanup'], ['90天前旧排课', 'Rosters older than 90 days'],
    ['学员注册页面', 'Registration page'], ['快捷操作', 'Quick actions'],
    ['待续课提醒阈值（剩余 ≤N 节）', 'Renewal reminder threshold (≤N credits)'],
    ['影响学员页「低余额」筛选和每周邮件中的待续课名单',
     'Drives the "low balance" filter and the renewal list in the weekly email'],
    ['数据体检', 'Data health check'], ['体检失败，请重试', 'Health check failed, please retry'],
    ['主屏幕 App / PWA 缓存', 'Home-screen app / PWA cache'],
    ['用于更新主屏幕图标、Service Worker 或修复旧页面缓存。',
     'Use this to refresh the home-screen icon, the service worker, or a stale page cache.'],
    ['每周汇总邮件（周一 10:00）', 'Weekly summary email (Mon 10:00)'],
    ['每周一自动发送', 'Sent automatically every Monday'],
    ['保存配置', 'Save configuration'], ['发送测试邮件', 'Send test email'],
    ['备份与恢复', 'Backup & restore'], ['查看备份列表', 'View backups'],
    ['暂无备份', 'No backups'], ['恢复前存档', 'Pre-restore snapshot'],
    ['恢复此备份（双重确认）', 'Restore this backup'],
    ['该备份文件已损坏，不可恢复', 'This backup file is corrupted and cannot be restored'],
    ['覆盖当前数据', 'Overwrite current data'],
    ['当前数据会先自动另存为 pre_restore 备份（可再恢复回来），然后被该备份覆盖。',
     'Your current data is saved as a pre_restore backup first (so it can be restored again), then overwritten by this one.'],

    /* ── PIN and auth ── */
    ['首次使用，请设置 4 位 PIN 码', 'First run — set a 4-digit PIN'],
    ['再次输入确认 PIN', 'Enter the PIN again to confirm'],
    ['输入 PIN 码解锁', 'Enter your PIN to unlock'],
    ['PIN 不正确，请重试', 'Incorrect PIN, please try again'],
    ['两次输入不一致，请重新设置', 'The two entries do not match — please set it again'],
    ['忘记 PIN？', 'Forgot your PIN?'],
    ['确认退出登录？下次进入需重新输入密码。',
     'Sign out? You will need your password to get back in.'],
    ['登录已过期，请重新登录', 'Your session expired — please sign in again'],

    /* ── Portfolio ── */
    ['上传', 'Upload'], ['作品', 'Work'], ['作品集', 'Portfolio'],
    ['编辑作品信息', 'Edit work details'], ['作品日期', 'Date'], ['作品标题', 'Title'],
    /* Operational data is never translated — see docs/Glossary.md → Bilingual
       scope. The hint tells the person typing, so nobody files it as a bug. */
    ['按录入的语言原样显示，不随官网语言切换。', 'Shown exactly as typed; it does not follow the website language.'],
    ['还没有作品，点击「上传」添加第一张', 'Nothing here yet — use Upload to add the first one'],
    ['照片不能超过 5MB', 'Photos must be under 5 MB'],
    ['上传失败，请重试', 'Upload failed, please try again'],
    ['复制失败，请长按选择', 'Copy failed — press and hold to select'],
    ['永久删除', 'Delete permanently'],
    ['修改将记入日志', 'Changes are written to the activity log'],
    ['可补录系统启用前的真实入学日期', 'You can backfill a join date from before this system was in use'],

    /* ── Errors ── */
    ['删除失败', 'Delete failed'], ['更新失败', 'Update failed'], ['恢复失败', 'Restore failed'],
    ['发送失败', 'Send failed'], ['保存失败', 'Save failed'],
    ['缓存清理失败，请关闭 App 后重新打开。',
     'Cache clearing failed. Close the app and open it again.'],
    ['PWA 缓存已清理，页面将刷新。若主屏幕 App 图标仍未更新，请删除后重新添加。',
     'The PWA cache is cleared and the page will reload. If the home-screen icon is still stale, remove it and add it again.'],
    ['请确认终端正在运行', 'Check that this is running in your terminal']
  ]);

  /* Prefixes that carry no meaning of their own (icons and status glyphs the
   * app puts in front of a label). They are stripped before lookup and put
   * back afterwards, so one dictionary entry covers both forms. */
  const AFFIX = /^([\s -　←-⇿①-➿️\u{1F000}-\u{1FAFF}✓✕✅❌⚠️➕⬇️🔓🔄🟢]*)(.*?)([\s -　←-⇿①-➿️\u{1F000}-\u{1FAFF}]*)$/u;

  const originalText = new WeakMap();
  const renderedText = new WeakMap();
  const originalAttributes = new WeakMap();
  let language = localStorage.getItem('studiosaas_admin_language') === 'en' ? 'en' : 'zh';
  let observer;

  function translate(value) {
    const clean = String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
    if (!clean || language === 'zh') return clean;
    if (en[clean]) return en[clean];
    const parts = clean.match(AFFIX);
    if (parts && parts[2] && parts[2] !== clean) {
      const core = parts[2].trim();
      if (en[core]) return `${parts[1]}${en[core]}${parts[3]}`;
    }
    /* "学员档案 (30)" — translate the heading, keep the count. */
    const counted = clean.match(/^(.+?)\s*\((\d+)\)$/);
    if (counted && en[counted[1].trim()]) return `${en[counted[1].trim()]} (${counted[2]})`;

    /* Shapes the dictionary would otherwise need one entry per value for. */
    const rules = [
      [/^剩余\s*(-?\d+)\s*课时$/, '$1 credits remaining'],
      [/^(-?\d+)\s*课时$/, '$1 credits'],
      [/^(-?\d+)\s*节$/, '$1 classes'],
      [/^(\d+)\s*人$/, '$1 students'],
      [/^(\d+)\s*人次$/, '$1 attendances'],
      [/^(\d+)\s*项$/, '$1 pending'],
      [/^已上课\s*(\d+)\s*人次\s*·\s*加权均价\s*\$([\d.]+)\/课时$/,
       '$1 attendances · $$$2 average per credit'],
      [/^(\d+)\s*天前$/, '$1 days ago'],
      [/^共\s*(\d+)\s*条$/, '$1 records'],
      [/^低余额≤(\d+)$/, 'Low balance ≤$1'],
      [/^第\s*(\d+)\s*页$/, 'Page $1'],
      [/^第\s*(\d+)\s*\/\s*(\d+)\s*页$/, 'Page $1 of $2'],
      [/^已选择\s*(\d+)\s*人$/, '$1 selected'],
      [/^选择本页\s*(\d+)\s*人$/, 'Select all $1 on this page']
    ];
    for (const [pattern, replacement] of rules) {
      if (pattern.test(clean)) return clean.replace(pattern, replacement);
    }
    /* Unlisted copy stays Chinese. A missing translation should read oddly,
     * not disappear. */
    return clean;
  }

  function isIgnored(node) {
    return !node.parentElement
      || /^(SCRIPT|STYLE|CODE|PRE|TEXTAREA)$/.test(node.parentElement.tagName)
      || node.parentElement.closest('[data-cms-language-switch]');
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
    const next = language === 'en' && clean ? `${leading}${translate(clean)}${trailing}` : source;
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
      const key = `i18nRendered${attr.replace('-', '')}`;
      const current = element.getAttribute(attr);
      if (!(attr in originals) || current !== (element.dataset[key] || originals[attr])) originals[attr] = current;
      const next = language === 'en' ? translate(originals[attr]) : originals[attr];
      if (current !== next) element.setAttribute(attr, next);
      element.dataset[key] = next;
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
    document.querySelectorAll('[data-cms-language]').forEach((button) => {
      const active = button.dataset.cmsLanguage === language;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function setLanguage(next) {
    language = next === 'en' ? 'en' : 'zh';
    /* Shared with Studio Admin and Super Admin so one choice covers the day. */
    localStorage.setItem('studiosaas_admin_language', language);
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    localise(document);
    updateSwitch();
    document.dispatchEvent(new CustomEvent('studiosaas:cms-language', { detail: { language } }));
  }

  function installSwitch() {
    if (document.querySelector('[data-cms-language-switch]')) return;
    const holder = document.createElement('div');
    holder.dataset.cmsLanguageSwitch = '';
    holder.className = 'cms-language-switch';
    holder.setAttribute('role', 'group');
    holder.setAttribute('aria-label', 'Language / 语言');
    holder.innerHTML = '<button type="button" data-cms-language="zh">中</button>'
                     + '<button type="button" data-cms-language="en">EN</button>';
    document.body.appendChild(holder);
    holder.addEventListener('click', (event) => {
      const button = event.target.closest('[data-cms-language]');
      if (button) setLanguage(button.dataset.cmsLanguage);
    });
    updateSwitch();
  }

  function installStyles() {
    const style = document.createElement('style');
    style.textContent = '.cms-language-switch{position:fixed;right:16px;bottom:16px;z-index:90;'
      + 'display:inline-flex;gap:2px;padding:3px;border:1px solid #e2e8f0;border-radius:999px;'
      + 'background:#fff;box-shadow:0 4px 14px rgba(15,23,42,.12);'
      + 'margin-bottom:env(safe-area-inset-bottom,0px)}'
      + '.cms-language-switch button{border:0;background:transparent;color:#64748b;'
      + 'min-width:44px;min-height:40px;padding:6px 12px;border-radius:999px;font:inherit;'
      + 'font-size:12px;font-weight:700;cursor:pointer}'
      + '.cms-language-switch button.active{background:#4f46e5;color:#fff}'
      + '.cms-language-switch button:focus-visible{outline:2px solid #4f46e5;outline-offset:2px}'
      + '@media print{.cms-language-switch{display:none}}';
    document.head.appendChild(style);
  }

  function start() {
    installStyles();
    installSwitch();
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
    observer.observe(document.body, { subtree: true, childList: true, characterData: true });
  }

  window.CmsI18n = {
    get language() { return language; },
    setLanguage,
    translate: (value) => (language === 'en' ? translate(value) : value),
    localise
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, { once: true });
  else start();
})();
