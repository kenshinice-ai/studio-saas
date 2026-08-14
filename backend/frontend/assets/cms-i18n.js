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
    ['工作台', 'Dashboard'], ['今日', 'Today'], ['待处理', 'Pending'],
    ['教学运营', 'Teaching & operations'], ['经营', 'Business'], ['记录', 'Records'],
    ['课程安排', 'Class Schedule'], ['课程', 'Courses'], ['课程目录', 'Course catalogue'],
    ['学员', 'Students'], ['学员档案', 'Students'], ['作品', 'Works'], ['作品管理', 'Portfolio'],
    /* v10.1 的经营两页。侧栏说的是这一页管什么，不是它属于哪一类 ——
       「账单」和「财务」都太像分类名，两个都点开才知道差别。 */
    ['账单', 'Billing'], ['账单发票', 'Billing & invoices'], ['结算', 'Settle'],
    ['开票信息', 'Invoice details'], ['法定主体名称', 'Legal entity name'],
    ['经营名称', 'Trading name'], ['已注册 GST', 'Registered for GST'],
    ['保存开票信息', 'Save invoice details'], ['新建发票', 'New invoice'],
    ['存为草稿', 'Save as draft'], ['再加一行', 'Add another line'],
    ['付款方', 'Payer'], ['付款说明', 'Payment instructions'],
    ['数量', 'Quantity'], ['单价（含税前）', 'Unit price (ex tax)'], ['税率', 'Tax rate'],
    ['不计税', 'No tax'], ['地址第一行', 'Address line 1'], ['地址第二行', 'Address line 2'],
    ['区/市', 'Suburb'], ['州', 'State'], ['邮编', 'Postcode'],
    ['开票邮箱', 'Invoice email'], ['开票电话', 'Invoice phone'],
    ['收款户名', 'Account name'], ['银行账号', 'Account number'],
    ['财务', 'Finance'], ['课酬与报表', 'Teacher pay & reports'],
    ['待审核', 'Pending'], ['充值结算', 'Credits'], ['充值与退款', 'Recharge & refunds'],
    ['操作日志', 'Activity Log'], ['经营统计', 'Business Stats'], ['排课', 'Roster'], ['课表', 'Schedule'], ['档案', 'Students'],
    ['审核', 'Review'], ['充值', 'Top-up'], ['日志', 'Log'], ['统计', 'Stats'],
    ['设置', 'Settings'], ['系统设置', 'System settings'], ['刷新', 'Refresh'], ['刷新数据', 'Refresh data'],
    ['已连接', 'Connected'], ['连接中...', 'Connecting…'], ['连接失败', 'Connection failed'],
    ['重新连接', 'Reconnect'], ['重试', 'Retry'], ['备份导出', 'Export backup'],
    ['退出登录', 'Log out'], ['全局搜索', 'Global search'], ['回到顶部', 'Back to top'],

    /* ── Shell strings that had been falling through to Chinese ── */
    ['搜索学员、手机号或功能', 'Search students, phone numbers or features'],
    ['已同步', 'Synced'], ['打开通知', 'Open notifications'],
    ['CMS 主导航', 'CMS navigation'], ['返回工作台', 'Back to Dashboard'],
    ['刷新 CMS 数据', 'Refresh CMS data'], ['搜索', 'Search'],

    /* ── Student list chips and profile tabs ── */
    ['概览', 'Overview'], ['资料', 'Details'], ['记录', 'Records'], ['专区', 'Portal'],
    ['专区已就绪', 'Portal ready'], ['缺手机号', 'No phone number'],
    ['专区未启用', 'Portal not enabled'], ['私人内容受阻', 'Private items blocked'],
    ['作品已公开', 'Works published'], ['公开授权有效', 'Consent valid'],
    ['缺公开授权', 'Consent missing'], ['充值记录', 'Top-up history'],
    ['加入今日排课', "Add to today's roster"],

    /* ── Billing workspace (v10.1) ── */
    ['已开票', 'Invoiced'], ['已收到', 'Received'], ['逾期', 'Overdue'],
    ['1 张 · 含 GST', '1 invoice · incl. GST'], ['1 个家庭', '1 family'],
    ['1 个暂停中', '1 paused'], ['1 次有变更', '1 changed'], ['1 份', '1 report'],
    ['共 1 人', '1 student'], ['1 项等待处理', '1 waiting'],
    ['待发草稿', 'Drafts to send'], ['没有待发的', 'None waiting'],
    ['暂无已开具发票', 'No issued invoices yet'], ['发票', 'Invoices'],
    ['已付清', 'Paid'], ['部分付款', 'Part paid'], ['已开具', 'Issued'],
    ['已作废', 'Void'], ['勾选后可批量发出', 'Tick to issue in bulk'],
    ['选择左边的一张发票查看明细。', 'Select an invoice on the left to see its detail.'],
    ['还没有发票。周期账单会自动生成草稿，前台复核后批量发出。',
     'No invoices yet. Recurring billing drafts them; the front desk reviews and issues in bulk.'],
    ['登记收款', 'Record payment'], ['开具', 'Issue'], ['作废', 'Void'],
    ['正在加载账单…', 'Loading billing…'],
    ['这个工作室尚未开通开票功能。', 'This studio is not entitled to invoicing.'],
    ['只看这个账单账户', 'Filtered to one billing account'], ['显示全部', 'Show all'],
    ['账单账户', 'Billing account'], ['未结', 'Outstanding'],

    /* ── Finance workspace (v10.1) ── */
    ['课酬', 'Teacher pay'], ['报表', 'Reports'], ['老师', 'Teacher'],
    ['小时', 'hours'], ['承包', 'Contractor'], ['雇员', 'Employee'],
    ['选择一位老师，查看本期课时明细。', "Select a teacher to see this period's sessions."],
    ['本期还没有归集到课时。课时来自点名记录，点完名这里就会有数。',
     'No sessions collected for this period yet. They come from check-in, so numbers appear once you take the roll.'],

    /* ── Recurring private lessons (v10.1.0) ── */
    ['一对一循环课与补课额度', 'Recurring private lessons & make-up credits'],
    ['循环课', 'Recurring lessons'], ['未来两周', 'Next two weeks'],
    ['待补课', 'Make-ups owed'], ['没有欠着的', 'None owed'],
    ['补课额度', 'Make-up credits'], ['请假规则', 'Absence rules'],
    ['排一节循环课', 'Add a recurring lesson'], ['请假 / 停课', 'Absence / closure'],
    ['学员请假', 'Student cancelled'], ['工作室停课', 'Studio closed'],
    ['计费', 'Charged'], ['不计费', 'Not charged'],
    ['算课酬', 'Teacher paid'], ['不算课酬', 'Teacher not paid'],
    ['安排补课', 'Book make-up'], ['已过期', 'Expired'], ['不过期', 'Never expires'],
    ['进行中', 'Active'], ['暂停', 'Pause'], ['结束', 'End'], ['恢复', 'Resume'],
    ['确认记录', 'Confirm'], ['保存规则', 'Save rules'], ['排课', 'Schedule'],
    ['星期', 'Weekday'], ['开始时间', 'Start time'], ['时长（分钟）', 'Length (minutes)'],
    ['起始日期', 'Start date'], ['请选择', 'Select…'],
    ['未来两周没有一对一课程。排课后会自动展开到这里，节假日与暂停会自动跳过。',
     'No private lessons in the next two weeks. Once scheduled they appear here automatically, skipping closures and pauses.'],
    ['还没有一对一循环课。排一节后，它每周自动出现，不用每周手动加。',
     'No recurring private lessons yet. Add one and it repeats weekly — no need to re-enter it.'],
    ['没有欠着的补课。提前请假产生的额度会出现在这里。',
     'No make-ups owed. Credits earned by cancelling in time appear here.'],
    ['每周同一时间自动出现，节假日与暂停会自动跳过。',
     'Repeats weekly at the same time, skipping closures and pauses.'],
    ['这一下决定三件事：还收不收钱、老师算不算课酬、要不要补一次课。',
     'This decides three things: is the family still charged, is the teacher still paid, and is a make-up owed.'],
    ['提前多少小时算按时请假', 'Hours of notice that count as in time'],
    ['补课额度多少天后过期（留空＝不过期）', 'Days until a make-up credit expires (blank = never)'],
    ['按时请假发一次补课额度', 'Notice in time earns a make-up credit'],
    ['临时请假照常计费', 'Late cancellation is still charged'],
    ['临时请假老师照付课酬', 'Late cancellation still pays the teacher'],
    ['工作室停课照常计费', 'Studio closure is still charged'],
    ['正在加载一对一课程…', 'Loading private lessons…'],
    ['这个工作室尚未开通一对一循环课。', 'This studio is not entitled to recurring private lessons.'],

    /* ── Progress reports (v10.1) ── */
    ['成长报告', 'Progress reports'], ['周期起', 'Period from'], ['周期止', 'Period to'],
    ['整理这一段', 'Assemble this period'], ['草稿', 'Draft'], ['已发布', 'Published'],
    ['保存草稿', 'Save draft'], ['发布给家长', 'Publish to family'],
    ['老师评语 · 已冻结', "Teacher's comment · frozen"],
    ['应到', 'Scheduled'], ['已到', 'Attended'], ['出勤率', 'Attendance'],
    ['去写', 'Write it'], ['逾期未写', 'Overdue'],
    ['写完评语才能发布 —— 后端也是这么拦的。',
     'A comment is required before publishing — the server enforces this too.'],
    ['上面的数字是证据，这段话才是报告本身。写给家长看。',
     'The figures above are the evidence; this paragraph is the report. Write it for the family.'],
    ['还没有报告。选好周期点「整理这一段」，出勤、课堂笔记会自动填进草稿，你只需要写评语。',
     'No reports yet. Pick a period and press Assemble — attendance and lesson notes fill the draft, so you only write the comment.'],

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
    ['固定课表', 'Recurring schedule'],
    ['创建每周自动排课班次', 'Create recurring weekly classes'],
    ['○ 仅内部可见', '○ Internal only'], ['停课', 'Cancelled'],
    ['前一天', 'Previous day'], ['后一天', 'Next day'],
    ['本周课程日期', 'Class dates this week'], ['选择课程日期', 'Choose class date'],
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
    ['课程安排默认时间', 'Class schedule default time'],
    ['加入课程安排', 'Add to schedule'], ['请先选择学员', 'Choose a student first'],
    ['课程状态', 'Class status'], ['待上课', 'Scheduled'], ['补课', 'Make-up'],
    ['签到并扣 1 课时', 'Check in and deduct 1 credit'],
    ['批量签到并扣课时', 'Check in all and deduct credits'],
    ['余额不足', 'Insufficient credits'], ['续费提醒', 'Renewal reminder'],
    ['发短信提醒', 'Send SMS reminder'], ['标记为 1 对 1', 'Mark as one-to-one'],
    ['改为普通班课', 'Change to group class'], ['撤销本日签到', 'Undo today’s check-in'],
    ['时间未设置', 'Time not set'],
    ['移出本日课程安排', 'Remove from this date'],
    ['来自固定课表，需在上方班次中调整', 'From the recurring schedule — edit the class above'],

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
    /* Walkthrough 2026-07-26: the meta line under each pending card. React
       renders each JSX expression as its own text node, so the prefixes and
       the status labels are looked up separately. */
    ['提交时间:', 'Submitted:'], ['· 来源:', '· Source:'], ['· 状态:', '· Status:'],
    ['门户网站', 'Portal site'], ['快速报名', 'Quick sign-up'],
    ['跟进中', 'Following up'], ['已批准', 'Approved'], ['已建档', 'Converted'],
    ['已拒绝', 'Rejected'], ['重复申请', 'Duplicate'], ['已流失', 'Lost'],
    ['已归档', 'Archived'],
    ['疑似重复', 'Possible duplicate'],
    ['另有一条待审核申请使用相同手机号', 'Another pending registration shares this mobile number'],

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

    /* ── Found by the manual's screenshot run (v8.2.20) ──
     * Capturing every CMS screen in English put the gaps on a contact sheet:
     * the roster alone showed 22 Chinese strings in English mode. These are
     * the ones with a self-contained meaning. Number-adjacent fragments
     * (`人`, `次`, `笔`, `条`, `分钟`) are left alone deliberately — React
     * splits them into their own text nodes, so translating them in isolation
     * would reorder the phrase they belong to rather than translate it. */
    ['网站与品牌', 'Website & brand'], ['公开网站', 'Public website'],
    ['固定课表 ICS', 'Weekly timetable ICS'],
    ['班组模板与批量工具', 'Group templates and bulk tools'],
    ['今天还没有排课', 'Nothing scheduled for this day yet'],
    ['可以在上方「每周课表」建一个固定班次，之后每到这一天会自动排入；也可以直接在下方添加学员。',
     'Add a recurring class under Weekly schedule above and it will appear on this day automatically — or add students directly below.'],
    ['1 对 1（同时段还有其他人时会提示冲突）',
     'One-to-one (you will be warned if anyone else is booked at the same time)'],
    ['选择学员', 'Choose a student'], ['确认收款并入账', 'Confirm payment and post it'],
    ['加入排课', 'Add to roster'],
    ['规律上课学员', 'Students attending regularly'],
    ['人的平均上课间隔。间隔变长 = 出勤率下降的早期信号',
     'Average gap between classes. A widening gap is an early sign of falling attendance.'],
    ['本月', 'This month'], ['近30天', 'Last 30 days'], ['本年', 'This year'],
    ['月度', 'Monthly'], ['年度', 'Yearly'],
    ['周一', 'Mon'], ['周二', 'Tue'], ['周三', 'Wed'], ['周四', 'Thu'],
    ['周五', 'Fri'], ['周六', 'Sat'], ['周日', 'Sun'],
    ['时段安排', 'By class time'], ['已签', 'Checked in'], ['未签', 'Not checked in'],
    ['低余额', 'Low balance'], ['搜索并选择学员…', 'Search and choose a student…'],
    ['搜索并选择学员...', 'Search and choose a student…'],

    /* ── Second sweep, from scripts/audit_cms_translation.py (v8.2.21) ──
     * The first sweep translated what a screenshot showed. Running the audit
     * across every tab, including attributes, found 66 more — most of them
     * `aria-label`s and placeholders, which never appear in a screenshot and
     * are exactly what a screen-reader user hears. */
    ['全局搜索 ⌘K', 'Global search ⌘K'], ['搜索', 'Search'],
    ['搜索学员姓名...', 'Search a student’s name…'],
    ['选择学员查看详情...', 'Choose a student to see details…'],
    ['如 节假日赠课、补偿调课...', 'e.g. holiday bonus credits, make-up class'],
    ['全部学员', 'All students'], ['快速充值', 'Quick top-up'],
    ['查看排课', 'View roster'], ['发消息', 'Message'],
    ['发送祝福短信', 'Send the birthday message'],
    ['签到', 'Check in'], ['上课时间', 'Class time'],
    ['导出当日 ICS', 'Export today’s roster (ICS)'],
    ['导出所有固定班次，不包含学员姓名',
     'Exports the recurring classes only — no student names'],
    ['来自每周课表', 'From the weekly timetable'],
    ['从未上课', 'Never attended'], ['已上课', 'Attended'],
    ['人次', 'attendances'], ['已上课人次', 'Attendances'],
    ['已赚收入(估)', 'Earned revenue (est.)'],
    ['预收未耗(负债)', 'Prepaid and unused (liability)'],
    ['净现金收入', 'Net cash received'],
    ['充值 − 退款', 'Top-ups − refunds'],
    ['剩余课时 × 均价', 'Credits remaining × average price'],
    ['人次 × 加权均价', 'Attendances × weighted average price'],
    ['课时预警 —', 'Low credits —'], ['长期未到访 —', 'Not seen for a while —'],
    ['名学员余额 ≤ 2 课时', 'students have 2 credits or fewer'],
    ['名学员有余额但超过', 'students still hold credits but have not attended for'],
    ['天未上课', 'days'],
    ['位学员等待审核，点击前往处理', 'waiting for review — tap to open'],
    ['本周生日 ·', 'Birthday this week ·'], ['最后 1 课时 ·', 'Last credit ·'],
    /* Fragments React renders as their own text nodes, next to a number the
     * app puts in a sibling. Chinese and English both place the measure word
     * after the count, so a straight substitution keeps the phrase in order —
     * `6/10 人 · 60 分钟` becomes `6/10 students · 60 min`. */
    ['人', 'students'], ['人 ·', 'students ·'], ['人）', ')'], ['（课表', '(timetable'],
    ['班）', 'classes)'], ['课 ·', 'classes ·'], ['课时 · $', 'credits · $'],
    ['分钟', 'min'], ['条', 'entries'], ['次', 'sessions'], ['笔', 'transactions'],
    ['·今', '· today'], ['近 14 天生日（', 'Birthdays in the next 14 days ('],
    ['待审核注册 (', 'Pending registrations ('],

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
      [/^共\s*(\d+)\s*人$/, '$1 students'],
      [/^\((\d+)\s*份\)$/, '($1)'],
      [/^(\d+)\s*张\s*·\s*含\s*GST$/, '$1 invoices · incl. GST'],
      [/^(\d+)%\s*已收$/, '$1% collected'],
      [/^(\d+)\s*个家庭$/, '$1 families'],
      [/^(\d+)\s*个暂停中$/, '$1 paused'],
      [/^(\d+)\s*次有变更$/, '$1 changed'],
      [/^(\d+)\s*次已过期$/, '$1 expired'],
      [/^(\d+)\s*份$/, '$1 reports'],
      [/^(\d+)\s*项等待处理$/, '$1 waiting'],
      [/^·\s*到期\s*(.+)$/, '· due $1'],
      [/^(.+)\s*前有效$/, 'valid until $1'],
      [/^(\d{2}\/\d{2}\/\d{4})\s*请假产生$/, 'earned $1'],
      [/^剩余\s*(-?\d+)\s*课时$/, '$1 credits remaining'],
      [/^(-?\d+)\s*课时$/, '$1 credits'],
      [/^(-?\d+)\s*节$/, '$1 classes'],
      [/^(\d+)\s*人$/, '$1 students'],
      [/^(\d+)\s*个每周班次$/, '$1 weekly classes'],
      [/^周一\s+(.+)，(\d+)\s*人$/, 'Mon $1, $2 students'],
      [/^周二\s+(.+)，(\d+)\s*人$/, 'Tue $1, $2 students'],
      [/^周三\s+(.+)，(\d+)\s*人$/, 'Wed $1, $2 students'],
      [/^周四\s+(.+)，(\d+)\s*人$/, 'Thu $1, $2 students'],
      [/^周五\s+(.+)，(\d+)\s*人$/, 'Fri $1, $2 students'],
      [/^周六\s+(.+)，(\d+)\s*人$/, 'Sat $1, $2 students'],
      [/^周日\s+(.+)，(\d+)\s*人$/, 'Sun $1, $2 students'],
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
      [/^选择本页\s*(\d+)\s*人$/, 'Select all $1 on this page'],
      /* `选择 Amelia Hart` — the aria-label on a student card. One rule
       * instead of one entry per student, and it keeps working for names the
       * dictionary has never seen. */
      [/^选择\s+(.+)$/, 'Select $1'],
      [/^(\d{2}\/\d{2})\s*\((\d+)天后\)$/, '$1 (in $2 days)'],
      [/^(\d{2}\/\d{2})\s*\(明天\)$/, '$1 (tomorrow)'],
      [/^(\d+)\s*次$/, '$1 sessions'],
      [/^本月\s*(\d+)\s*次$/, '$1 this month'],
      [/^(\d+)\s*笔$/, '$1 transactions'],
      [/^(\d+)\s*条$/, '$1 entries'],
      [/^·\s*加权均价\s*\$([\d.]+)\/课时$/, '· $$$1 average per credit'],
      [/^(\d+)\s*分钟$/, '$1 min'],
      /* `{y}年` in the year picker — React renders the number and the
       * character as separate nodes, so the year arrives here alone. */
      [/^年$/, ''],
      [/^(\d{4})\s*年$/, '$1'],
      [/^(\d{2}\/\d{2}\/\d{4})\s*·\s*(.+?)\s*·\s*余额\s*(-?\d+)$/, '$1 · $2 · $3 credits']
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

  /* The switch is the one control that is on screen on every page of the CMS,
   * so it was also the one control that stayed Tailwind-indigo on a themed
   * page. Every colour below is a theme token with the pre-theme palette as
   * the fallback, and each is chosen for a measured pair rather than by eye
   * (worst case across the 15 theme-modes in backend/studiosaas/presets.py):
   *
   *   resting label   --muted on --panel            5.56:1   (was 3.06:1 once
   *                                                  the panel followed a theme)
   *   selected label  --on-accent on --accent       5.83:1   (a fixed #fff on
   *                                                  a bright dark-theme accent
   *                                                  measured 2.08:1)
   *   focus ring      --focus-ring on --panel       3.86:1, on --bg 3.55:1
   *                   (--accent is not usable here: the ring has to clear 3:1
   *                    against the surface, and the accent is solved against
   *                    the page for TEXT contrast, not as a ring)
   *   hairline        --line on --panel             1.34:1   (visible-divider
   *                                                  floor is 1.18)
   *
   * Position: 21px is the --ui-space-4 step of the golden ladder the rest of
   * the CMS uses. On phones a floating switch covered whichever roster control
   * happened to scroll beneath it, so the same two 44px controls live inside
   * Settings instead. Toasts still outrank the desktop switch (z-index 999 vs
   * 90), which is the correct order for transient feedback. */
  function installStyles() {
    const style = document.createElement('style');
    /* v8.4.0: the fallbacks are tokens too. A `var(--accent, #4f46e5)` keeps
       working after --accent is renamed away — it just paints indigo forever,
       silently, on whatever palette replaced it. The same rule in
       admin-i18n.js did exactly that when the consoles moved off --brand. */
    style.textContent = '.cms-language-switch{position:fixed;right:21px;bottom:21px;z-index:90;'
      + 'display:inline-flex;gap:3px;padding:5px;border:1px solid var(--line,var(--ui-border));border-radius:999px;'
      + 'background:var(--panel,var(--ui-surface));box-shadow:var(--shadow-lg,0 4px 14px color-mix(in srgb, var(--ink,var(--ui-text)) 12%, transparent));'
      + 'margin-bottom:env(safe-area-inset-bottom,0px)}'
      + '.cms-language-switch button{border:0;background:transparent;color:var(--muted,var(--ui-muted));'
      + 'min-width:44px;min-height:44px;padding:6px 12px;border-radius:999px;font:inherit;'
      + 'font-size:13px;font-weight:700;cursor:pointer;transition:background-color .15s ease,color .15s ease}'
      + '.cms-language-switch button.active{background:var(--accent,var(--brand-accent));color:var(--on-accent,var(--brand-on-accent))}'
      + '.cms-language-switch button:focus-visible{outline:2px solid var(--focus-ring,var(--accent,var(--brand-accent)));outline-offset:2px}'
      /* On phones the same controls live inside Settings. A floating 96px
         pill inevitably covered roster controls while the page scrolled. */
      + '@media (max-width:767px){.cms-language-switch{display:none}}'
      + '@media (prefers-reduced-motion:reduce){.cms-language-switch button{transition:none}}'
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
