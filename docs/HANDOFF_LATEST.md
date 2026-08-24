# PWE Studio v10.14.0 — Handoff 索引（2026-08-16 起按 AI 分目录）

> 首标题始终点名当前版本 —— `test_release_ledger.py` 据此机器强制「索引不过期」；
> 每次发布随四层身份表一起更新。

> 本文件从 505KB 单文件瘦身为**索引 + 当前身份**。历史内容一字未改，按原顺序拆入
> `docs/handoff/`；拆分经字节保真校验（拼回 == 原文件 SHA-256）。
>
> **新惯例：按 AI 分目录写轮次文件，不再向本文件追加叙事。**
> - Claude（Fable）：`docs/handoff/claude/YYYY-MM-DD-主题.md`，一轮一文件。
> - codex 时代存档（只读）：`docs/handoff/codex/`，`index.md` 列全部 95 节。
> - 每轮结束只回本文件做两件事：更新下方「当前四层身份」表、更新「最新轮次」指针。
> - 其余纪律不变：Source / Package / Production / Backup 四层分别记录；docs-only
>   closure 不得写成已部署运行时代码；发布必经 STOP GATE。

## 当前四层身份（v10.14.0 candidate，2026-08-24）

| 层 | 精确事实 |
|---|---|
| Source | v10.14.0 品牌首页候选：Living Studio System 将 Portal / Register / Operations CMS / Studio Admin 串成一个空间故事；HTML 为事实层，浅/深海报 → Canvas → Three.js 渐进增强。候选提交与最终门禁待本轮记录。 |
| Package / SaaS | 待候选提交与完整门禁后构建 `dist/PWE-StudioSaaS-aws-10.14.0.tar.gz`。 |
| Package / Edition | 待同一干净提交构建 `dist/PWE-Studio-Edition-10.14.0.tar.gz`。 |
| Production | 发布前事实仍为 `pwestudio.online` = v10.13.0；deep health `db=ok`、`mode=saas`、`workspaces.stale=0`、`themes.unreadable=0`、5 个租户、磁盘 18.9%；`http -> 301`、`https -> 200 tls=0 proto=2`。 |
| Backup / migration | schema 仍至 `0047_xero_transport.sql`（本版零迁移）；v10.14.0 部署前备份由受保护控制器生成。 |

## 上一版四层身份（v10.12.3，2026-08-22）

| 层 | 精确事实 |
|---|---|
| Source | v10.12.3 发布提交 `474a4d8`（链：`822f136` 卫生+钱与权限 → `0d272cd` 结算租户可重置 → `38b7131` **CMS 登录修复** → `474a4d8` 发布账本） |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.12.3.tar.gz`，SHA-256 `11a5a141b15e7216f752a2ee6bf3c3869e7a65de81cf687981e6f1d548ef891c`（三方守卫全等） |
| Package / Edition | `dist/PWE-Studio-Edition-10.12.3.tar.gz`，SHA-256 `e0477d2d246d0e1e982cc47e47d8ed8f0e17b9552a974c161d4417a113b54c66` |
| Production | `pwestudio.online` = v10.12.3；deep health `db=ok`、`mode=saas`、`stale=0`。**CMS 登录已恢复**（自 v10.11.0 起对所有租户 404，线上实测：错口令 401 带人话、未知 slug 仍 404、家长预约 400 走校验不再 500）。两间样板租户已按新内容包重播种：开票主体各自独立（Paradise Production / Zhiyin Music Pty Ltd，ABN 均为校验位不合法号），单号 `INV-####` 与 `music-####`，生日铺满全年、14 天窗口各 1 人，启蒙班学员 6 岁与 5 岁落在适龄内；Xero 侧各 0 连接 0 网关状态、加购有效（不再伪造无 token 连接） |
| Backup / migration | v10.12.1 部署前 dump（deploy 自动产出）；schema 仍至 `0047_xero_transport.sql`（三个补丁版本零迁移） |

完整证据见 `docs/handoff/claude/2026-08-16-v10.8.0-round.md`（v10.8.0）与 codex/001（v10.7.1 历史）。

## 最新轮次

- **2026-08-23（Claude Opus 5）层 2 前两步落地 + 角色权限的事实与取舍**（**已发布 v10.13.0**）：
  `docs/handoff/claude/2026-08-23-two-page-refactor-and-roles.md`
  —— 层 2 ①`?section=` 按 tab 作用域解析并按角色收敛；层 2 ②设置页七个
  `hidden` 面板换成 `Tabs`/`TabPanel`，六块共享内容各归其位，删掉不可达的
  弹窗分支与 133 行 `{false && …}` 死代码；排课页删掉重复的生日横幅，并修掉
  工作台生日**跨年那一周整周漏人**的算法。实测 4 角色 × 8 section = 32 例、
  全量 `2840 passed`。两个只有跑起来才会现形的坑：hook 写在
  `cms-app.jsx:3098` 的 `if (!loggedIn) return` 之下会触发 React #310 整页空白；
  `actorRole` 首帧为空会把合法的 `?section=` 提前收敛掉。
  同一轮内接着定了角色（前台整拿 `attendance:write`、staff=助教收成 teacher
  的真子集）、按 `/code-review` 的四条判定全修，并**落地了排课页重排**：
  第一行学员的 top 桌面 898→**542**（首屏 900）、手机 1124→**634**（首屏 844），
  桌面首屏从 0 行学员变成 5 行；顺手修掉排课 #4/#5/#6/#7 与截图脚本
  `next_class_date()` 往后找日期导致**手册最忙的一页每个按钮都是灰的**。
  排课 #8「≤360px 周视图重叠」实测**不复现**，未改。
  已复核 `PATCH /students/<id>` 只带 `balance` 时**既无 `actor_user_id`
  也无 audit 行**（已修）。排课页阶段二（页内标签）尚未开始，清单见
  `docs/design/CMS_Roster_Split_Plan.md` 第 9–19 步。
  **发布前又跑了一轮对抗式复查（该文「十一」节），推送前拦下一个越权**：
  给前台 roster 标签页，把 `canWriteScheduling` 里那条我自己判定为「死代码」的
  `front_desk` 激活了，于是前台能改「请假规则」——课酬与账单口径——而同一版
  明确不给它 `payroll:read`。新增 `scheduling:policy:write`（仅 Owner/Manager）
  修掉。同轮还修：`GET /class-bookings` 一直无权限判断却返回每个约课家庭的
  姓名与手机（改判 `class_bookings:review`，teacher 实测 403）；本轮新加的
  `firstRowInFold` 断言**在 bug 上也通过**（898 < 900）；改中文把 i18n 字典键
  改成了孤儿，英文界面回退成中文；课时流水的 `actor_user_id` 存了但日志查询
  没 select（60/60 现在带操作人）。全量 `2848 passed`，门禁 `All checks passed`。
- **2026-08-22（Claude Opus 5）v10.12.3 —— CMS 登录自 v10.11.0 起就是坏的**：
  `docs/handoff/claude/2026-08-22-hygiene-and-money-paths.md`（「四·六」节）
  —— 拆包（`cfab504`）把 `api_v1.py` 变成包，两处**函数体内**的单点相对导入
  含义随之改变：`auth.py` 的 `from .tenant_context import`（CMS 登录）与
  `public.py` 的 `from .services.student_access import`（家长预约）。
  前者的 `ModuleNotFoundError` 被 `except Exception` 收成 404「Unknown tenant」，
  **对每个租户、每次登录**；两天没人发现，因为大家都还揣着有效会话——直到
  重播种把会话清掉。后者每次提交 500。两处改回包根，except 收窄到真正表示
  「无此租户」的两个异常，登录框改显示 `message` 而非机器码 `not_found`。
  新增 AST 静态测试（函数体内导入靠 import 模块测不到；用文件系统而非
  `find_spec`，否则一处坏会让同包全部误报）。全量 `2840 passed`。

- **2026-08-22（Claude Opus 5）v10.12.2 —— 记过结算的演示租户重置不了**：
  同上一条 handoff 的「四·五」节。`_clear_showcase` 漏清两张引用钱层的表：
  `credit_financial_links`（RESTRICT）与 `financial_operation_requests`
  （SET NULL 但被 BEFORE UPDATE 触发器拒绝，报出来是「幂等键不能配不同的载荷」）。
  **既有缺口**，只在租户真的走过一次结算后才有行，所以只播种的本地永远测不出来；
  v10.12.1 上线后第一次线上重播种就炸了。走真实结算接口复现并验证（手造行会被
  `assert_credit_financial_link_is_legal` 挡下）；第一次只修一张，重跑才炸出第二张。
  全量 `2839 passed`。

- **2026-08-22（Claude Opus 5）会面卫生 + 钱与权限 —— v10.12.1**：
  `docs/handoff/claude/2026-08-22-hygiene-and-money-paths.md`
  —— 播种器里最后十处美术字面量与 index 算术搬进内容包（开票主体、ABN、单号前缀
  `music-`、生日与年龄、充值手续费、教师薪酬），并停止伪造无 token 的 Xero 连接与
  「映射已确认」。签到路径三修：已签到改按日期查考勤（原先全局 `LIMIT 500` 会导致
  四十天前的记录掉窗、批量签到二次扣课时）、未来日期当面确认、批量确认框点名日期、
  失败给原因。工作台四处写死的「画艺大进」改走租户模板（其中两处在 `sms:` body 里）。
  **并降级了我自己两轮前报错的一条**：front_desk 读到银行账号不是越权 —— 同样的字段
  经 `GET /billing/invoices/<id>`（`billing:read`）本来就到他手里，因为收款账户印在
  每张发票上；真正成立的只是开票面板把 `canManage` 传成了 owner+manager。
  全量 `2838 passed`；门禁 All checks passed。

- **2026-08-22（Claude Fable 5）Sinobeats 会后 —— Xero 链路诊断，只读不动**：
  `docs/handoff/claude/2026-08-22-xero-meeting-followup.md`
  —— Demo Company 没收到发票是**从未推送**：音乐租户 `push_enabled=false`、试跑从未
  完成、队列 0 条；「不流畅」是播种器伪造的无 token 连接让 `refresh-check` 409。
  即便开关打开，音乐 `INV-0001..6` 会与美术样板撞号（同一个 Demo Company）被守卫
  逐张拒绝 → 音乐包要自带单号前缀。Q2：发票与付款都到 Xero，但付款在 Demo Company
  里全部 Unreconciled（无流水行可配）；**`clearing_account` 选项传输层从未实现**，
  而 Sinobeats 用 Square，这是它的必经路径。真账本有一条死作业（本地已作废，重放即
  skipped）。UI 三份方案原样未动。

- **2026-08-21（Claude Opus 5）音乐样板租户 —— 播种器泛化成「行业内容包」**：
  `docs/handoff/claude/2026-08-21-music-showcase-pack.md`
  —— `reset_professional_demo.py` 改为按包播种（`--pack art|music`），每个包自带
  确认短语；**修掉「重置演示租户」按钮永远重建美术租户的地雷**（租户决定包，无包
  认领即拒绝）。九组文案/数据从播种器搬进包模块，其中 `BILLING_LINKS`／
  `ATTENDANCE_COURSE_INDEX`／`REGISTRATION_ANSWERS` 原本是**写死的索引算术**，
  在音乐名册上会安静产出自相矛盾的演示。新增音乐包 `music-studio-showcase`
  （知音音乐，growth，12 学员／9 课／22 个素材），装配时另修 logo 被切断、
  manifest 学员索引错位、「两台钢琴」标题与正文矛盾、凭空多出第五个房间。
  以及两个包把凭据写进同一个文件（环境变量改为给目录、包给文件名）。
  美术包输出逐字未变；全量 `2832 passed`。**上线须先手工给线上租户打
  `settings.professional_demo=true`，否则播种器会（正确地）拒绝。**

- **2026-08-20（Claude Fable）v10.11.1 运维卫生轮 —— A/B 两档清单一次做完**：
  `docs/handoff/claude/2026-08-20-ops-hygiene-round.md`
  —— 集成页 Beta 徽标（含移除触发条件）；两组双语标签对齐；**演示页「数据每晚
  重置」不实声明纠正**（定时器从未存在，手动重置是既定决策；模板改动随部署经
  entrypoint 的 regenerate 生效）；控制台冒烟进入发布门禁（自起实例、无 Chrome
  显式跳过）；`prune_dist.py` 释放 1.20 GB（dist 1.3G→178M）；**OPS-03** 线上
  nginx 收编（发现仓库零记录的 paradise-production 片段）；**OPS-04** 备份口令
  离开 argv（此前 `/proc/*/cmdline` 全局可读）。另：仓库根一份 0644 私钥在
  iCloud 里——核实从未进过 git，与 `~/.ssh` 正本逐字节相同，已移出。

- **2026-08-20（Claude Fable）v10.11.0 结构重构轮 —— P1–P4 全案一步到位**：
  `docs/handoff/claude/2026-08-20-structure-refactor.md`
  —— api_v1.py 15,926 行拆为 11 域包（url_map 191 条 + AST 394 符号机器等价）；
  cms-app.jsx 拆出 components.jsx + 7 panel（48 张截图流水线实拍验证）；
  i18n 引擎合一（fail-open）+ 重复键门禁（首跑清 52 个存量重复）；
  PBKDF2 合一（双 legacy 格式兼容，测试先行）；两控制台 4,200 行内联脚本
  外置为版本化资产 + 新增真浏览器冒烟（首跑抓出 studio-admin 登录静默失败
  并修复）。行为零变化；发布证据见下方四层身份表。

- **2026-08-19（Claude Fable）X4 接入完成 + v10.10.2/v10.10.3 —— 真实账本推送开启**：
  `docs/handoff/claude/2026-08-19-xero-x4-real-ledger.md`
  —— 真租户 `lets-paint-studio` 全向导对真账套走通：连 PWE GROUP PTY LTD
  （v10.10.2 按授权事件选组织实测生效）、试跑 clean、推送开启；
  首单 **LPS-INV-0002** 在真账本肉眼可见、对账 0 差异。
  途中现场抓到 **Xero POST 按单号 upsert 会改写账本现存单据** → v10.10.3
  同号冲突守卫（创建前按号预查，撞号死信）+ 真租户单号改 LPS- 前缀。
  结算月进行时；X4 出口 = 一个自然月 0 人工修账。

- **2026-08-19（Claude Fable）v10.10.0 + v10.10.1 —— Xero X3 外发 transport 与过闸修复**：
  `docs/handoff/claude/2026-08-19-xero-x3-transport.md`
  —— 队列消费真上线：迁移 0047（退避住行里 + 链接带 org）；`xero_transport.py`
  （精确分值推送、Contact 客户键 upsert、invoice/credit_note/payment(按 allocation)、
  失败分类退避/死信、backfill、逐张对账、demo cycle）；三处入队钩子；
  push-now/backfill/reconciliation/queue 四条 API；gate 的 demo_run 变真跑；
  systemd timer + `lightsail_ctl exec-app` + 安装脚本；集成页映射编辑器与队列操作面；
  产品真话契约与 FAQ/Demo_Runbook 翻到「门后单向推送」。
  测试 12 项新增，全量 2857 通过。四层身份表随部署闭环更新。

- **2026-08-19（Claude Fable）v10.9.3+v10.9.4 —— Xero 连接打通（invalid_scope →
  wrong apps scopes → 首个成功连接）**：
  `docs/handoff/claude/2026-08-17-xero-x2-round.md`（2026-08-19 更正节）
  —— v10.9.3：`invalid_scope` 根因是 Xero scope 换代（2026-03-02 后创建的应用只拿
  细粒度 scope），改细粒度集并携带四轮压队修复（0046 套餐上限、字段类型下拉、
  CMS 与 admin i18n、手册截图/路演材料）一并发布。
  v10.9.4：细粒度集仍被拒（`Requested wrong apps scopes`），线上二分定位
  `app.connections` 与 `accounting.settings.read` 不被 authorize 放行，终稿
  `openid profile email accounting.invoices accounting.payments accounting.contacts
  offline_access`；Demo Company (AU) 连接 ✔ / 取消 ✔ / 自愈 ✔，断开重连随 v10.9.4 收口。
  四层身份表随部署闭环更新。

- **2026-08-19（Claude Fable）两处漂移按线上对齐**：
  `docs/handoff/claude/2026-08-19-two-drifts-aligned.md`
  —— 套餐学员上限 100/500/1000 → 50/250/500（新增 `0046`；只改基线种子无效，
  因为 `0021` 会把 growth 抬回 1000，实测新库才发现），价格只改基线不进迁移；
  报名字段类型下拉不再把枚举当标签（value 仍是 text/textarea/select）。未部署。

- **2026-08-19（Claude Fable）admin-i18n.js 审计（Studio Admin / Super Admin）**：
  `docs/handoff/claude/2026-08-19-admin-i18n-audit.md`
  —— 与 CMS 同三类缺陷：13 个重复键（`Support` 被「支持」覆盖掉配色角色「辅助色」）、
  About 的 24 个生成式字段名读作「Highlight 3 Body · 中文」、observer 不监听属性。
  另修一条为页面从未产出的措辞而写的规则（`Signed in: ` vs 实际的 `Signed in as `）。
  未改 JSX，未升版本号，未部署。

- **2026-08-18（Claude Fable）CMS 英文界面三处修复**：
  `docs/handoff/claude/2026-08-18-cms-i18n-measure-words.md`
  —— 量词短语改为整句渲染（碎片条目 `['人）', ')']` 靠删字蒙混，渲染成 `(12 )`）；
  字典 10 个重复键（`已作废` 曾被动作词覆盖成 `Void`）；observer 不监听属性，
  导致 placeholder/title/aria-label 只在挂载时翻译过一次。界面文案残留中文
  214→0（余下 34 处是租户数据）；未升版本号，未部署。

- **2026-08-18（Claude Fable）销售材料对齐 v10.9 + 手册截图整套刷新**：
  `docs/handoff/claude/2026-08-18-roadshow-deck-refresh.md`
  —— deck 定价页对齐线上 plans 表（$189/50/250/500/席位）并新增「账务与 Xero」页（10→11 页），
  13 张截图全部换本地实拍；朋友圈软广告 v10.9 包重制；播种器发票快照缺陷与 v10.9.2 轮
  独立撞出同一修法，以已发布的 v10.9.2 版本为准。第三轮修掉 `capture_manual_shots.py`
  两处缺陷（中文侧写成短标签「学员」；`OPEN_FIRST_STUDENT` 死匹配且调用处静默丢弃结果，
  05-portfolio 一直拍成学员列表而非手册说的作品集区块），手册 48 张按单一 v10.9.2 基线
  整套重拍（33 张实质变化），`asset-manifest.json` 已重建。未升版本号，随下次发布上线。

- **2026-08-17（Claude Fable）v10.9.2 手册第 10 章截图修复轮**：
  `docs/handoff/claude/2026-08-17-manual-invoicing-screenshots.md`
  —— docs+assets 最小发布；播种器与捕捉脚本各修一处。

- **2026-08-17（Claude Fable）v10.9.0 Xero X2 轮**：`docs/handoff/claude/2026-08-17-xero-x2-round.md`
  —— OAuth 连接流（发布证据随部署闭环）。

- **2026-08-17（Claude Fable）v10.8.0 执行轮**：`docs/handoff/claude/2026-08-16-v10.8.0-round.md`
  —— Batch A–F 全量实现（发布证据在该文件随部署闭环）。

- **2026-08-16（Claude Fable）全面体检与下一轮方案（docs-only）**：
  `docs/handoff/claude/2026-08-16-full-system-audit.md`；
  权威方案：`docs/design/Full_System_Audit_Plan_2026-08-16.md`（rev2，含 Batch A 界面缺陷、
  Batch E 账务/学员优化、Batch F Xero 路线图、OPS 暂缓决定与触发条件）。
- **v10.7.1 发布轮（codex）**：`docs/handoff/codex/001-…`（发票打印修复与发布闭环）。

## 历史存档

- `docs/handoff/codex/index.md` — codex 时代全部 95 节（v7.x → v10.7.1），原文原序。
