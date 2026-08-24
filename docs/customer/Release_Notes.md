# PWE Studio — Release Notes and Acceptance Evidence

## v10.14.0 — 产品首页成为一个相连的工作室系统

产品首页围绕 **Living Studio System** 重建：品牌门户、快速报名、运营 CMS、
品牌工作台不再只是四张功能卡，而是围绕同一个工作室核心相连的四个界面。

页面仍以语义 HTML 为事实层，浅色 / 深色空间海报先显示；移动端与减弱动效路径
使用 Canvas，合适的桌面浏览器再加载自托管 Three.js。WebGL、脚本或网络失败时，
完整文案、CTA 与四个普通链接仍可使用。本版不改变租户主题、数据模型、权限或 API。

## v10.13.0 — 前台可以签到，助教的权限收窄了，排课页先给你看名单

**前台现在可以签到扣课时。** 前台本来就能给学员充值、退款、改余额，却不能做
最轻的那一件——学员站在柜台前签到。这不是安全设计，是漏的：每一笔课时变动都
记名记时，能改余额的人挡在签到之外只会让人绕道去手工改数字，而手工改数字比
签到更难查。

**「Staff」改名「助教」，权限收成老师的真子集。** 原来的 staff 能改学员档案、
能看能改课时余额、能审报名、能看账单——比老师权限还大。现在助教能做的每一件事
老师都能做，老师比助教多的只有两项：写学习报告、看自己的课酬。**如果你把某人
设成了 Staff 并指望他改学员档案或调课时，请把他改成经理或老师。**

**课程安排页先给你看今天上课的人。** 以前一打开这一页，先看到的是「添加学员」
表单、班组模板、固定课表，学员名单被挤到屏幕外——桌面上一行都看不见，手机上
在屏幕下方 280 像素处。现在名单紧跟在日期和当日概览之后；添加学员、班组模板
移到名单**下面**，一对一循环课与固定课表移到页尾。桌面首屏现在能看到五行学员。

**请假规则改成只有 Owner / Manager 能动。** 「一对一循环课」里的请假规则决定
临时请假老师照不照付课酬、工作室停课家长照不照付费——它是课酬和账单的口径，
不是排课操作。此前它和「排一节课」共用同一把钥匙（`scheduling:write`），
前台也持有；只是前台没有任何一页能走到那张表单，所以从没出过事。这一版给了
前台课程安排页，那条路就通了，因此把它拆成单独的权限。前台仍然能约课、能改
时间、能开一对一循环课，只是看得到、改不了请假规则。

**手工改课时现在看得到是谁改的。** 账本一直记着操作人，但操作日志的查询从来
没把这一列读出来——于是签到和手工调整在日志里都是无名的。现在两者都显示
「操作人」。

其它修正：

- **复制日报的标题跟着你选的日期走**。以前不管选哪天都写「今日上课」，粘进
  群里没人看得出说的是哪一天。
- **「保存当前为模板」不再漏掉固定课表排进来的学员**。以前它只存手工加进去的
  人，所以在一个学员全部来自固定班次的日子里，它会说「当前日期没有排课可保存」
  ——尽管屏幕上明明列着十个人。
- **「转为每周班次」不再像是没反应**。它打开的编辑器在折叠着的「固定课表」里，
  现在会自动展开并滚动过去。
- **手机上的「当日操作」菜单点完会关**，不再盖住刚刚改过的那一行。
- **修改学员余额会记名**。以前在学员档案里直接改课时余额，账本上留下的那一笔
  没有操作人，操作日志里也没有对应记录；签到扣课时则一直是记名的。现在两条路
  都记名、都进日志。两条路都保留——签到用于上课，手动调整用于补录和更正。
- **工作台的生日提醒不再漏掉跨年的那一周**。12 月底看未来 14 天，1 月初过生日
  的学员整周不出现。

Acceptance evidence: `docs/handoff/claude/2026-08-23-two-page-refactor-and-roles.md`.

## v10.12.3 — 修复：CMS 登录与家长预约（自 v10.11.0 起）

- **CMS 登录失败**：v10.11.0 的一次内部代码整理改动了一个模块引用，登录接口
  因此对**所有工作室**返回「找不到」。已登录的浏览器会话不受影响，所以直到
  会话过期、需要重新登录时才会遇到。**已修复。**
- **公开课程表的预约表单提交报错**：同一次改动导致家长在公开课程表上点「预约」
  提交时报服务器错误。**已修复。**
- 登录框此前只显示内部错误代码（例如 `not_found`），现在显示可读的说明。

给两条路径都补了自动检查，同类改动不会再无声通过。

## v10.12.2 — 记过结算的样板工作室可以重置了

- 样板演示工作室一旦真的记过一次结算（在「充值与退款」里把课时挂到某笔收款上），
  「重置演示租户」就会失败并回滚，而且此后永远失败。原因是重置漏清了两张引用
  收款记录的表。两张都已补上。此项只影响样板演示工作室，不影响任何真实工作室的数据。

## v10.12.1 — 签到不再悄悄扣课时，演示数据各归各家

- **批量签到会说清扣的是哪一天**：确认框以前固定写「今日」，读的却是你当前选中的
  日期 —— 排下周三的课时顺手点一下，扣的是那一天的课时。现在日期写在第一句。
- **未来日期的签到要当面确认**：为一节还没上的课扣课时，以前不会有任何提示。
  超出可签到范围的日期，按钮会变灰并说明原因。
- **「已签到」不再看错**：一间每月流水较多的工作室，四十多天前的签到记录会掉出
  界面读取的窗口，于是显示成「待上课」——再按一次批量签到就会重复扣课时。
  现在直接读那一天的考勤记录，没有这个窗口。
- **批量签到失败会说明原因**：以前只列出失败的学员姓名。
- **生日祝福用工作室自己的文案**：工作台的生日祝福（含一键发送的短信正文）此前
  写死了一句面向绘画教室的话术，音乐、舞蹈等工作室的家长会收到不合适的祝福。
  现在走「消息模板」设置里的生日模板。
- **开票信息由 Owner 维护**：此前经理也能填写开票主体表单，但保存时会被拒绝。
  现在经理看到的是只读视图，不会再填一遍白填。
- 样板演示工作室的数据修正：两间样板此前共用同一套开票主体与单据编号，学员年龄
  与所报课程的适龄范围对不上，生日集中在同一周。已各自独立并修正。

## v10.12.0 — 音乐行业样板工作室，以及演示重置的按租户分化

- **新增一间音乐样板工作室**：`music-studio-showcase`（知音音乐 Zhiyin Music，
  墨尔本 Glen Waverley）。中西乐器并行的教学结构——钢琴、小提琴、声乐与古筝、
  二胡、琵琶；一对一、四到六人的小组、乐理与考级、启蒙班与少年乐团。12 名学员、
  9 门课程、7 个公开班次、完整的账务与学习报告，全部为虚构的合成数据。
  面向音乐培训机构演示时可直接使用，不必再拿绘画工作室的样板去讲乐器教学。
- **样板工作室现在按「行业内容包」生成**：演示数据的生成器过去只认识一间绘画
  工作室——房间名、付款人、发票行、学习报告的措辞都写死在生成器里。现在这些都
  属于各自的行业包，新增一个行业是新增一个内容文件，不需要改动生成器。绘画
  样板的输出逐字未变。
- **「重置演示租户」按钮修正**：平台管理里的重置按钮此前无论在哪个演示租户上
  按下，都会重建绘画样板——审计记录写的却是被按下的那一个。现在由租户决定重建
  哪一份内容，没有内容包认领的租户一律拒绝重置，确认短语也各自点名自己的租户。
- **各样板的凭据文件分开存放**：两间样板工作室此前会把交接凭据写进同一个文件，
  后重置的一间会覆盖先前那一间。

## v10.11.1 — 演示站点文案纠正、集成页 Beta 标记与运维加固

- **演示站点不再声称「数据每晚重置」**：四个公开页（门户 / 作品集 / 报名 / 课表）
  的页脚一直写着数据每晚自动重置，但那个定时器从未存在——演示数据一直是由运营
  手动重置的。措辞改为「数据由运营手动重置」，与实际做法一致。
- **集成页标记 Beta**：Xero 单向推送正在用一个完整结算月的真实账目验证，页面
  现在明说这一点，并提示期间照常核对 Xero 里的单据。
- **两处中英标签对齐**：同一组双语字段的中文半边与英文半边此前译法不一致
  （小标题/眉标题、简介/正文），已统一。
- **控制台冒烟进入发布门禁**：两个管理控制台的浏览器冒烟检查现在由发布门禁自动
  运行（自起实例；无 Chrome 时显式跳过而非静默略过）。
- **运维加固**：数据库备份的口令不再经命令行传递（此前在主机进程列表里可见）；
  线上 nginx 配置收编进仓库作为基准，连同一处此前仓库毫无记录的站点配置片段。

## v10.11.0 — 代码结构大重构：拆单体、合重复，行为零变化

面向未来维护性的一轮纯重构，对外行为与界面完全不变，全部改动经机器等价验证：

- **后端 API 单体拆分**：15,926 行的 api_v1.py 按业务域拆为 13 个文件的包
  （公开页 / 认证 / 学员 / 排课 / 账务 / 教学 / Xero / 媒体 / 租户 / 平台等），
  拆分前后 191 条路由逐条机器比对全等、394 个顶层符号 AST 指纹全等。
- **CMS 前端拆分**：7,606 行的单组件应用拆出 7 个面板文件与通用组件库
  （工作台 / 排课 / 学员 / 充值 / 报表 / 作品 / 学员档案弹窗），
  用 48 张手册截图流水线逐屏实拍验证渲染无变化。
- **中英切换引擎合一**：CMS 与两个控制台此前各带一份同构的翻译引擎，同类缺陷
  修过两轮。现在只有一个引擎（词典仍各自维护），并新增门禁：词典重复键直接红
  ——首跑即抓出 52 个存量重复键并已清理（保持线上渲染不变）。引擎按约定
  fail-open：万一异常，页面保持原文可用，绝不白屏。
- **密码哈希合一**：两份 PBKDF2 实现收敛为一份，两种历史遗留格式均可验证并
  自动升级；回归测试先行。
- **控制台脚本外置 + 浏览器冒烟**：两个控制台约 4,200 行内联脚本各自外置为
  版本化资产（页面瘦身为纯标记），并新增真浏览器冒烟检查（零 JS 错误、登录
  错误提示必须渲染）。冒烟首跑即抓出一个真实缺陷：工作室管理台登录失败时
  只有 3 秒气泡、无持久错误提示（平台控制台一直是对的）——已修复对齐。

验证：完整 pytest 2,817 项通过；三界面真浏览器实测（语言切换双向、跨界面记忆）；
两台控制台冒烟全绿。

## v10.10.3 — 同号冲突守卫：绝不覆盖账本里别人的单据

X4 真账本接入现场发现：Xero 的创建接口按单号 upsert——推送一张 INV-0001 到已有
同号发票的组织，Xero 会**更新那张现存发票**（可能是别的系统的、可能已付款）。
真实账本里已有多年的 INV-#### 序列，这不是理论风险。本版本在创建路径先按单号
查询目标组织：号已存在且不属于本工作室的推送记录 → 立即死信并给出可操作的原因
（为工作室配置独立单号前缀，或连接专用组织），绝不静默改写。配套地，真租户的
单号序列已改用独立前缀（LPS-INV- / LPS-CN-），与账本旧序列永不相撞。

## v10.10.2 — 多组织时连接选对组织（X4 前置）

同一个 Xero 用户可以为不同工作室授权不同组织（演示账套 + 真实账套）。此前回调
取 `/connections` 列表的第一行——单组织时代恒正确，多组织并存后取到哪个取决于
Xero 的排序。现在按**本次授权事件**精确匹配（access token 的
`authentication_event_id` ↔ 连接行的 `authEventId`），点了哪个组织的 Allow 就连
哪个组织；无法匹配时回退到最新的连接（最近一次人的决定），绝不静默取第一行。

## v10.10.1 — 「开启推送」过闸修复

v10.10.0 生产验收走到最后一步「开启推送」时发现：合闸用的 upsert 在 PostgreSQL 下
必然触发 0037 的门约束——INSERT 候选行（推送开、前置条件全空）会先于 ON CONFLICT
被 CHECK 评估，即使实际会走 UPDATE 分支。此路径在 transport 关闭的时代不可达，
首次真实过闸即暴露。修复：合闸改为纯 UPDATE（前置条件本就存在于行内，gate 校验
刚刚读过它们）；暂停推送路径不变。新增回归测试用真实服务函数走完整向导后合闸。

## v10.10.0 — Xero 单向推送（X3）：队列、对账与向导闭环

Xero 从「只连接」变为可用的单向推送。已开具的发票、贷记单与收款按队列推入工作室
自己的 Xero 组织：金额按本地分值原样推送（不让 Xero 重算税）、以本地单号入账、
收款按分配拆到对应发票。推送前必须走完向导四步——连接组织、会计确认科目与税率映射
（tuition 与 bank 必填；lesson/manual 行按 tuition 科目入账）、对 Demo Company
完成一次真实试跑（推送全部积压单据并逐张读回对账，0 差异才算过）、回答「是否已有
其他通道在同步」。开关未开时不发送任何数据；暂停推送不影响连接、映射与历史记录。

失败的推送带 Xero 原文原因列在集成页，修好映射后一键重放（沿用同一幂等键，不会在
Xero 产生第二张）；429/服务不可用自动退避重试。队列由服务器每 5 分钟自动处理，
集成页也可「立即推送」与「逐张对账」。方向严格单向：不做双向同步，不从 Xero 回改
任何本地单据；退款与已推送后的收款释放暂不同步（会在对账报告中显形）。

验证：新增 12 项 transport 测试（金额精确性、幂等、依赖排序、失败分类、换组织重推、
对账）；完整 pytest 2857 通过；生产验收对 Xero Demo Company (AU) 完成（证据见最新
handoff）。

## v10.9.4 — Xero 首个成功连接：scope 终稿

v10.9.3 的 scope 集在授权页仍被拒（`access_denied: Requested wrong apps scopes`）。
线上逐组二分定位：`app.connections` 与 `accounting.settings.read` 虽出现在应用
配置清单里，但 authorize 端点对本类应用不放行；其余全部可用。本版本把 scope 定稿为
`openid profile email accounting.invoices accounting.payments accounting.contacts
offline_access`——组织查询实测无需 `app.connections`，推送所需权限一次授权到位。

验收（2026-08-19，Xero Demo Company (AU)）：连接 ✔（授权→回调→卡片显示
「已连接 Xero · Demo Company (AU)」，组织名来自 /connections）；取消分支 ✔；
令牌自愈 ✔（refresh-check 200，状态保持已连接）；断开→重新连接随本版本收口。

## v10.9.3 — Xero 授权按新版 scope 规范接入 + 界面语言纯净度修复

Xero：2026 年 3 月之后在 Xero 创建的应用只接受新版细粒度 scope，旧的宽 scope
`accounting.transactions` 会在授权页直接被拒（invalid_scope）。连接流程改为请求
细粒度最小集（invoices、payments、contacts、settings 只读、connections），一次授权
覆盖后续单据推送所需权限，届时无需重新授权。连接本身仍不推送任何单据数据。

界面：CMS 英文界面与两个管理控制台（Studio Admin / Super Admin）修复三类同源缺陷
——量词短语整句渲染（不再出现 `(12 )` 之类碎片）、字典重复键互相覆盖、翻译观察器
不监听属性导致 placeholder/title 只翻译一次。报名表字段类型下拉不再把枚举当标签。

对齐：套餐学员上限迁移 `0046` 使各环境与线上一致（50/250/500）；在线手册 48 张截图
按 v10.9.2 单一基线整套重拍，路演材料同步。

验证：Xero OAuth 7 项测试通过；完整 pytest + 真 Postgres 验证随发布链执行；
连接演练对 Xero Demo Company 完成（证据见最新 handoff）。

## v10.9.1 — Xero 环境透传修复

v10.9.0 的集成页在服务器已写好凭据的情况下仍显示「未配置」：容器环境块是 allow-list，四个 XERO 变量没有列入 docker-compose.yml，值写进 production.env 也到不了进程。本版本只补这一处透传（凭据本身不动）。

## v10.9.0 — Xero 连接（X2）

工作室现在可以在「系统设置 → 集成」里连接自己的 Xero 组织：OAuth2 授权码 + PKCE 流程，令牌在服务器上加密存储，访问令牌到期自动续期，失效则显示「已过期，需要重新授权」而不是无声失败；可随时断开（同时向 Xero 撤销授权并清除本地令牌）。连接本身**不向 Xero 推送任何单据数据**——推送仍在后续阶段的门后。服务器凭据由运营方通过 `deploy/aws/set_xero_env.sh` 配置，密钥不进入代码库。建议先用 Xero Demo Company 完成连接演练。

验证：新增 7 项 OAuth 流程测试（PKCE verifier 不出服务器、令牌加密落库、握手一次性、刷新自愈、死令牌可见、未配置时诚实报错）；完整 pytest 2758 通过。

## v10.8.0 — 账务工作台、学员时间线与品牌/导航修复

财务方面：学员详情新增「学员时间线」，把报名、充值、扣课、发票、收款、贷记与成长报告合成一条只读流水；付款方新增「月结单」（期初/流水/期末，可打印）；发票可「记录提醒」（只入历史，不发送任何消息）；工作台新增应收卡片与低课时一键续费；报名审批在建档前给出疑似重复档案的显式选择（并入或新建，绝不自动合并）；开具发票前会检查开票信息完整度（名称、地址、ABN），缺失时拒绝并指引补齐。打印通道现在一次只打印所选单据（发票、贷记单、月结单互不串印）。

界面方面：公开页品牌区统一为「有 logo 只显示 logo、无 logo 显示完整店名」，语言切换后导航重新测量（不再出现整排省略号）；带锚点的链接冷加载后能正确定位；CMS 与 Studio Admin 在无权限时给出明确的权限说明而非误导性的连接错误，Studio Admin 载入失败时进入阻断态以防误存。租户隐私说明扩写为对齐澳大利亚隐私原则（APP）的十节详版（未成年人、存储与保留、披露、投诉渠道等），版本 2026-08-16。

本版本已提交、SaaS 与 Edition 归档包 checksum 验证、部署生产并完成浏览器验收；精确的运行时 commit、归档 hash、备份与深健康证据见最新 handoff。Xero 仍为 Preview（不发送数据）。

## v10.7.1 — invoice print repair and money-contract closure

This release is committed, packaged, pushed to `main`, deployed through the
guarded production controller, and browser-checked. Production reports
`appVersion=10.7.1`, `db=ok`, and `mode=saas`; exact source/package/backup
evidence is kept in `docs/HANDOFF_LATEST.md`.

The release completes the v10.7.1 repair checklist around tenant-scoped
credit-refund sources, stable credit-note tax-rate snapshots, payer review,
aggregate invoice drafts, accounting exports, and the customer-document print
fallback. In particular, the browser print CSS now keeps the issued
`InvoiceDocument` visible instead of hiding it behind the CMS root, and the
generated browser PDF title identifies the selected document (for example
`Tax Invoice · INV-0007`). Xero remains Preview-only; no OAuth, transport,
worker, or webhook is included.

## v10.7.0 — invoice operations and explicit credit settlement

This source candidate has passed the internal A–F checklist gates in the
working tree, including PostgreSQL-backed money/tenant checks and a real local
browser top-up/refund flow. It adds payer dual-entry resolution, issued
supplier/recipient snapshots, the shared InvoiceDocument DTO, audited summary
and line CSV exports, and print/save-as-PDF fallback after the portable PDF
renderer compatibility spike did not pass.

Credit top-ups that opt into billing now run as one idempotent transaction:
credit purchase, optional invoice, gross-to-net/tax split, optional payment,
allocation, bridge and audit either all commit or all roll back. Refunds require
an explicit purchase source and, when the full bridge and permissions exist,
create a credit note, payment refund, negative credit movement and legal bridge
in one transaction. Invoice detail now exposes the linked credit notes and
credited totals; CSV and print views therefore remain reconcilable.

Release evidence: commit `913c6f168052213535fbeae9da0197de9e655959` is on
`main`/`origin/main`; the SaaS and Edition packages were checksum-verified and
production `pwestudio.online` now reports `appVersion=10.7.0`, `db=ok`, six
tenants, zero unreadable themes and zero stale workspaces. The deployment
created PostgreSQL/volume backups and applied migration
`0043_invoice_and_credit_settlements.sql`. Xero OAuth/transport remains a
later Preview/Beta project.

## v10.6.4 candidate — money contracts, truthful integrations, and release gates

This is a source candidate prepared from the v10.6.3 baseline. It has not been
committed, packaged, pushed, or deployed; the verified SaaS and Edition packages
and production runtime remain v10.6.3.

The candidate makes invoice allocation explicit when a staff member records a
payment from an invoice detail view, rejects an invoice target from the wrong
account or tenant instead of silently falling back, and records payment/refund
amounts, balances, and the acting user in invoice history. The payment and
refund endpoints now reject unknown or contradictory fields rather than
accepting a field and doing something else.

Xero is labelled **Preview** until OAuth, outbound transport, and an observable
worker exist. Preview mappings and queues do not send data or create new push
jobs. The billing empty state now describes the capability that exists today:
staff create and review drafts before issuing them; no recurring invoice
generator is implied.

The candidate also adds clean-checkout and archive runtime smoke checks. Local
release evidence is PostgreSQL-backed: targeted contracts 140 passed with one
non-P0 skip, full pytest 2619 passed with seven skips, legacy smoke 73/73, and
tenant isolation 254/254. No migration was added or applied.

## v9.8.8 — truthful public surfaces and safe publish verification

Studio Admin now keeps the write result and the public verification result
separate. A successful save that is still waiting for `/brand`, `/showcase` or
`/timetable` to settle is shown as **Published, public pages still need
verification** rather than a false failure; the saved content stays clean and
the owner can retry verification from the same panel. Structured error codes
and bilingual copy replace the old raw verification warning.

The portal, standalone showcase, timetable and register page now share one
public-surface contract. Navigation and Footer entries require both owner intent
and real published content, while the Studio Admin preview shows the same
ready / unavailable states and next action. The light workbench rail uses the
information tint for selection, keeps the 1.618 editor/preview split, and
retains keyboard, focus, reduced-motion and 44px touch-target rules.

Public navigation checks consent revocation and timetable occurrences using the
same server-side rules as the destination pages, so an empty or stale link is
not advertised. No tenant records are deleted or migrated by this change.

### Deployment acceptance

Production is running `PWE-StudioSaaS-aws-9.8.8` from commit
`4b436e1e2df0717b7efb01d5e7d4021a6cc23860`. The SaaS package SHA-256 is
`1d6fc1760993864c681c8f9cb5e58eac303acdb65573ba98978181f226ee3da7`; the
Edition package SHA-256 is
`0a75bf66059da97dc91b450933bd2a44e48200b7dda17030b62baa22ec1cd3b6`.

The guarded switch created logical backup
`studiosaas_studiosaas_20260811T121335Z.dump` with its manifest and volume
archive `pwestudio-volumes-20260811T121336Z.tar.gz`; v9.8.7 remains available
as the rollback release. Deep health reports `appVersion=9.8.8`, `db=ok`,
`mode=saas`, six tenants, and `themes.unreadable=0`. Public route checks all
returned `200`. The live showcase API reports home `pageSize=6`, archive
`pageSize=12`, category filtering, and a valid empty page after the final
offset. The production browser check passed at 1280px and 375px with no
horizontal overflow; the lightbox opened `1 / 12` and closed cleanly. No fresh
application `Traceback`, `Exception`, `Fatal`, or `ERROR` entries were found
after deployment.

## v9.8.7 — ranked showcase archive and content-safe publishing

The public showcase now has one tenant-wide `featured_rank` order. Lower
numbers appear first, ranks `1–6` define the home-page preview, and an empty
rank keeps the work in the stable fallback order. The same order is used for
the independent `/<slug>/showcase` archive and its category-filtered views.

The home page loads at most six selected works. The archive loads twelve
matching works per page and continues with C-scheme offset pagination or the
visible “Load more / 加载更多” action, including when a category is selected.
Each work remains addressable through the shared navigation/footer shell, and
the lightbox supports keyboard focus, Escape, previous/next and reduced-motion
preferences.

Studio Admin can edit an optional rank (1–500) and shows the resulting home
order before publishing. Plan changes preserve all saved showcase records and
ranks; only the number of Active works eligible for public publication follows
the plan. The bilingual online manual, Studio Owner guide, and admin copy use
the same Starter / 入门版, Studio / 工作室版, and Growth / 成长版 terminology.

### Deployment acceptance

Production is running `PWE-StudioSaaS-aws-9.8.7` from deployable commit
`4e1894f12a31935701f3982757bd8fe0f441e0d0`. The SaaS package SHA-256 is
`8181b9324ef4f66297cacb9b9d440c4ecec458f34151d887965ff850c07392c1`; the
Edition package SHA-256 is
`16473b8d4ad17c57e3603cef34915aca00b6e8a2c87305b146240ce8d1d64403`.

Migration `0030_showcase_featured_rank.sql` applied during the guarded switch;
the pre-switch logical backup is
`studiosaas_studiosaas_20260811T083534Z.dump` with manifest and the volume
archive is `pwestudio-volumes-20260811T083535Z.tar.gz`. Deep health reports
`appVersion=9.8.7`, `db=ok`, `mode=saas`, six readable tenants and
`themes.unreadable=0`. Public route checks and the production 390×844 browser
acceptance passed: the archive renders 12 works without horizontal overflow,
the mobile menu is available, and the lightbox opens and closes correctly.

## v9.8.6 — online manual: timetable and booking

The bilingual online manual now has a dedicated chapter for the public
timetable at `/<slug>/timetable` and its optional booking request flow. It
explains the two independent publication switches, the 1–4 week display and
booking window, field visibility, teacher-name consent, and the rule that a
booking request does not reserve a seat before approval.

The manual also adds four paired desktop/mobile screenshots from the synthetic
`lets-paint-showcase` capture tenant: Studio Admin timetable settings and the
mobile booking request dialog. This is a documentation-focused release; it
does not add a data migration or change stored customer records.

### Deployment acceptance

- Production: `pwestudio.online` is running `PWE-StudioSaaS-aws-9.8.6` with
  `appVersion=9.8.6`, `db=ok`, `mode=saas`, `tenants=6`, and
  `themes.unreadable=0`.
- The deployable commit is `21d2cc70bcd116250fca4780bec164a855b45258`.
- The Chinese manual, public timetable, CMS, Studio Admin, register page, and
  bilingual Release Notes returned `200`; the representative timetable
  screenshot returned `304` on a matching ETag request.

## v9.6.1 — Studio Admin workspace polish

This small release keeps the v9.6.0 information architecture and gives the
Studio Admin workbench a more useful canvas. On wide screens the shell uses the
available width like the CMS, while the navigation rail stays compact and the
editor/preview pair keeps its approximately `1.618:1` working ratio. Tablet
layouts stack the preview before the working area becomes cramped; mobile stays
single-column without horizontal overflow.

The preview now starts in the active admin shell language, so the surrounding
controls, draft notice and save status do not unexpectedly disagree with the
preview. The preview language buttons remain available for an explicit,
independent bilingual comparison.

This is a presentation and language-alignment release only. It does not change
the data model, permissions, publishing contract, payments, bank-transfer
display, persistent CMS notifications or external messaging providers.

Production acceptance: v9.6.1 is deployed at `https://pwestudio.online` from
candidate commit `e46a3e3f4a407e8b2ac34ce8e230165c37150ea1`. The SaaS archive
SHA-256 is `f1465b393fefb83e962bac41402fff150430c3fcd3e9b7252911d985840aabb4`;
the Edition archive SHA-256 is
`3d881f7e3324b5acacc4aa89feadd23a278e5cd2cc412f0474d6c13b8deb7e0e`.
Deep health reports `appVersion=9.6.1`, `db=ok`, six readable tenants and
`themes.unreadable=0`.

## v9.6.0 — Studio Admin navigation and publication clarity

Studio Admin now groups the public-brand workbench into Brand & Website,
Admissions, Publish and Insights. Registration and public timetable controls
are together under Admissions; family message templates remain in Studio Admin
under the same group and remain compatible with the existing CMS copy workflow.

The release also repairs dirty-state coverage for timezone, timetable and family
message fields, makes Registration shortcuts and workbench views deep-linkable,
completes timetable translation, reserves safe space for the sticky save bar and
labels the right-hand panel as a private draft preview. Publication status now
distinguishes unsaved changes, saved private drafts and published content.

Online payments, bank-transfer configuration, Gmail/SMTP, AWS SES, SMS, SSE,
WebSocket and browser push remain deferred.

Production acceptance: v9.6.0 is deployed at `https://pwestudio.online` from
candidate commit `f9007855dcaa10298bd522c82e7397d2afba0638`. The SaaS archive
SHA-256 is `38da495f81146d48878350fd07a8dfce25b6c30ff67782f3f4cc3d990790cdde`;
the Edition archive SHA-256 is
`88416f04de9cf7ab88fa61a409e094e282d4ed9701218757d39b9b44db51d2a2`.
Deep health reports `appVersion=9.6.0`, `db=ok`, six readable tenants and
`themes.unreadable=0`.

## v9.5.0 — CMS information architecture and operational workspaces

The CMS now has one stable working model for operators: a top app bar for
high-frequency controls, grouped navigation, a role-specific workbench and
deep-linkable routes. Daily work is grouped into Today, Teaching & Operations,
Business and Records; System Settings is a full page with anchored sections.

Courses, works, students, pending requests and recharge/refund operations now
have dedicated functional workspaces. The same permissions remain enforced by
role, and the UI does not expose Studio Admin or the public portal as if they
were CMS workspaces. The layout keeps a wide content measure beside a compact
navigation rail, uses the existing PWE Brand tokens, and preserves 44px touch
targets on mobile.

Persistent CMS notifications remain in-app only: new registrations and
class-booking requests are stored with the request, shown in the notification
center, refreshed every 30 seconds and surfaced with a popup prompt. Online
payments, bank-transfer configuration, Gmail/SMTP, AWS SES, SMS, SSE,
WebSocket and browser push remain deferred.

Production acceptance: v9.5.0 is deployed at `https://pwestudio.online` from
commit `9a976215bab9d5b32b9792f36851078a4111ff4b`. The SaaS archive SHA-256 is
`d9cd91c57467213ee81710d290b8a589c6910b4819568d136e2da9e59842802a`; the
Edition archive SHA-256 is
`90409a371521074252ceed90946198a5c4021319fcefb19fc55d665f74dfc97d`. Public
deep health reports `db=ok` and all six stored tenant themes readable.

## v9.2.0 — persistent CMS notifications

The CMS now keeps an in-app notification history for new public registrations
and class-booking requests. Each event is written in the same database
transaction as the request, so the notification cannot claim success for a
request that was not saved, and duplicate submissions do not create duplicate
alerts. Staff with registration visibility see a bell, unread count and
notification list; booking notifications are limited to roles that can review
bookings.

The first delivery uses a simple 30-second refresh, an immediate refresh when
the browser becomes visible again, a popup prompt for new events and per-user
read state. Online payments, bank-transfer configuration, Gmail/SMTP, AWS SES,
SMS, SSE and WebSocket push remain deferred.

## v9.1.1 — Course Schedule terminology and operator polish

The CMS workspace formerly named Daily Roster is now Course Schedule. Its date
and week navigation, attendance summary, time groups, add-student controls and
batch tools form one top-to-bottom planning flow. Wide layouts keep each student
on one compact row, while mobile retains the same task order without horizontal
overflow.

Each student's more-actions menu now opens with their date, time and credit
balance, identifies recurring-schedule entries, and groups status, reminder,
one-to-one, undo and removal actions. Scheduled and make-up states can be saved
directly without removing and re-adding the student.

## v9.1.0 — faster daily scheduling and safer delivery

v9.1.0 reshapes the daily roster around the work performed at the front desk:
date navigation, week occupancy, attendance summary, time groups, batch tools
and student rows now form one compact planner. Each row has one clear check-in
and credit-deduction action, while reminders, one-to-one marking, date-bound
undo and removal live in a deliberate overflow menu. Only an explicit
`oneToOne` flag raises a same-time conflict; ordinary group classes remain
valid. Birthday and recurring-schedule tools stay available but collapsed so
they no longer push today's work below the fold.

The dashboard now turns student-portal and publication readiness into actionable
filters. Thirty-day activity is keyed by immutable student ID; a historical
name-only event is used only when the name identifies exactly one student.
Public timetable bookings notify the studio admin only after a new request is
durably committed, and duplicate submissions never send a second alert.

Image delivery now creates 360px, 960px and 2000px metadata-free derivatives
and publishes responsive candidates. Existing media is covered by an explicit
backfill. Authorized private media uses checksum ETags with `private,
no-cache`, so a repeat request can return 304 only after session, ownership and
consent checks. Shared frontend assets likewise carry both release and content
hashes; a missing or stale manifest fails the build/runtime contract instead of
silently caching mismatched JavaScript.

## v9.0.0 — one Brand contract and a safe CMS migration baseline

v9.0.0 establishes one product-wide contract rather than introducing a
breaking data migration. The source, package and deployed production status are
reported separately; `docs/design/Brand_Identity.md` is the canonical Brand
document; public product surfaces share the same bilingual system type,
touch-target and layout rules; and Front Desk has a narrow backend permission
to review class-booking requests without gaining course, capacity or schedule
authority.

Inside the operational CMS, the release repairs malformed touch, active and
disabled selectors and migrates only `EmptyState` to semantic theme tokens.
The component's props and callbacks are unchanged. A real Chromium acceptance
at 390px verified no horizontal overflow, a 44px action target and a visible
2px keyboard focus ring. This is the reference pattern for later CMS migration,
not authorization for a broad rewrite.

## v8.1.0 — Production deployment and tenant theme publication

Release status: production deployed to `https://pwestudio.online` on
2026-07-30 (AWS Lightsail, Sydney). Monitoring, a contractual SLA,
privileged-account MFA and off-instance backup copies remain deferred and are
disclosed as deferred.

The customer-facing version of this record is
`customer-resources/Release_Notes.html`. Engineering detail and measured
evidence live in `docs/HANDOFF_LATEST.md`.

## What v8.1.0 changes

### Production hosting (was deferred in v8.0.1)

- `https://pwestudio.online` runs on an AWS Lightsail instance (Ubuntu 24.04,
  2 vCPU / 1.9 GB, `ap-southeast-2`). nginx terminates TLS with a Let's Encrypt
  certificate covering the apex and `www`; `www` 301s to the apex; HTTP 301s to
  HTTPS; HSTS is set for one year. The application listens on loopback only.
- Daily PostgreSQL logical dump plus media-volume archive under cron; the
  restore rehearsal runs and passes.
- **Cloudflare Tunnel is no longer the production path.** It is retained for
  local development only and must not be reintroduced for this hostname.
- Edge hardening: one shared TLS snippet included by both 443 blocks, duplicate
  security headers removed, a branded maintenance page for 502/503/504, and
  **OCSP stapling deliberately left off** — the Let's Encrypt certificate no
  longer carries an OCSP responder URL, so enabling it produces a permanent
  ignored-directive warning on every reload and nothing else.

### Tenant theme publication (the release's main product fix)

- The registration success card paired fixed light text with `--ink`. Under the
  seven dark theme-modes `--ink` *is* the light text colour, so that card
  measured **1.06:1 — a parent who submitted a registration saw an invisible
  confirmation**. It now uses `var(--bg)` against `var(--ink)`, a pair
  `backend/scripts/palette_gen.py:221` already asserts at ≥4.5:1, which covers
  all 15 theme-modes.
- The portal's degraded-content band moved from a fixed warm yellow to the
  theme's own warning colour, so it is no longer a light foreign strip across
  every dark theme.
- The CMS mapped **10 of the 21 theme tokens** and then applied
  `body { background:#f1f5f9 !important }` over the result, so every studio's
  CMS looked identical. Portal, registration and CMS now map the same complete
  21-token set, with a test asserting the three agree field for field.
- Product homepage focus ring: Family Amber measured **1.70:1** against Warm
  Paper, below the 3:1 WCAG 1.4.11 requires of a non-text indicator. It now uses
  the accessible amber at **4.52:1**; the bright amber is retained on navy
  sections where it measures 9.70:1.
- Dark-section form borders moved from `rgba(255,255,255,.28)` (2.51:1) to
  `.42` (3.90:1).
- `backend/tests/test_portal_theme_contract.py` (12 tests, new) holds all of the
  above.

### Commercial plan quotas (owner decision, 2026-07-30)

Prices, plan codes, plan names and feature flags are unchanged.

| Plan | AUD/month | Students | Team users | Storage |
|---|---:|---:|---:|---:|
| Starter | 49 (unchanged) | 100 (unchanged) | 2 → **1** | 5 GB → **2 GB** |
| Studio | 99 (unchanged) | 500 (unchanged) | 8 → **5** | 30 GB → **10 GB** |
| Growth | 199 (unchanged) | 1500 → **1000** | 20 (unchanged) | 100 GB → **50 GB** |

Applied by migration `0021_plan_quota_revision.sql`, live in production. Over-quota behaviour is
admission control on new records only: a tenant found above a lowered ceiling
keeps all of its data and simply cannot add more until the plan is upgraded.

### Compliance and brand

- `customer-resources/Privacy_Policy.html` and `Terms_of_Service.html` are new
  and published (PWE GROUP PTY LTD, ABN 55 606 664 546). Both carry a draft
  qualifier pending Australian legal review.
- The FAQ and these release notes no longer claim "AWS not yet deployed"; they
  state the live position and the gaps that remain on a live service.
- Both pages were migrated off the retired forest/sage palette onto the brand
  tokens through a shared stylesheet.

## Explicitly not delivered

- Uptime monitoring, backup-failure alerting, on-call ownership, a contractual
  SLA;
- multi-factor authentication for privileged accounts — now an open gap on a
  live service, and the highest-priority security item;
- off-instance backup copies (backups exist and restore, but live on the same
  instance);
- managed AWS services (RDS, S3, SES);
- automated messaging provider, online payments, accounting sync;
- per-studio custom domains;
- organisation-level multi-campus aggregation — one campus remains one tenant;
- inside the CMS only: the second, older dark-appearance mechanism is not yet
  merged into the theme one, and the `text-gray-400`-class secondary labels do
  not yet meet AA. Both are recorded as items 29, 7 and 8 in
  `docs/design/UI_UX_Upgrade_Plan_2026-07-30.md`. Neither affects a
  parent-facing or student-facing surface.

## Acceptance matrix

| Gate | Required evidence | Status |
|---|---|---|
| Unit/backend | full local PostgreSQL verification gate | Complete |
| Theme publication | portal/registration/CMS map the identical complete token set | Complete: `test_portal_theme_contract.py` |
| Public-surface contrast | text and focus indicators meet the standard across all 15 theme-modes | Complete; the CMS items above remain open |
| Calendar privacy | ICS structure/timezone and no student data | Complete |
| Demo reset | guard refusal plus successful isolated reset | Complete |
| Frontend build | CMS source compiled to deployed bundle | Complete |
| Responsive UI | 375, 768, 1024 and 1440 px browser checks | Complete |
| Templates | CSV + 5-sheet XLSX, all sheets rendered and inspected | Complete |
| Packages | SaaS + Edition bundle build and content inspection | Complete |
| Deployment | public HTTPS, DNS, certificate, redirect, deep health, data counts | Passed 2026-07-30 |
| Recovery | database and media restore rehearsal from a real backup artefact | Passed on-instance; off-instance copy open |
| Privileged MFA | second factor enforced for every privileged account | Open |
| Monitoring and SLA | uptime and backup-failure alerting, on-call roster, signed target | Open |

v8.1.0 is deployed: the instance runs `studiosaas:8.1.0` with 21 migrations
applied and the revised plan quotas live
(`starter 100/1/2048 · studio 500/5/10240 · growth 1000/20/51200`). See
`docs/HANDOFF_LATEST.md` §7.5. (§9.2 of that document describes migration 0021
as pending; it was written before the deploy and is superseded by §7.5.)

## Customer acceptance

Customer representative: `[ ]`
Demonstrated version/hash: `[ ]`
Demonstration date: `[ ]`
Accepted scope: `[ ]`
Open exceptions: `[ ]`
Signature: `[ ]`
