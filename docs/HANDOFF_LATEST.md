# PWE Studio v10.11.1 — Handoff 索引（2026-08-16 起按 AI 分目录）

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

## 当前四层身份（v10.11.1，2026-08-20）

| 层 | 精确事实 |
|---|---|
| Source | v10.11.1 发布提交 `4ff7efe`（链：`49555c9` Beta 徽标+双语标签 → `daf0203` 演示页不实声明 → `291f853` 冒烟进门禁 → `b69a363` prune_dist → `6a1b95a` OPS-03 nginx → `eb9ef05` OPS-04 首版 → `65622a6` 发布账本 → `4ff7efe` **OPS-04 改正**） |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.11.1.tar.gz`，SHA-256 `292993ef8025738ddd6ab2767e950c653ee16a167a25930d8212bfbfecdbf5ed`（BUILD_INFO commit=4ff7efe，三方守卫全等） |
| Package / Edition | `dist/PWE-Studio-Edition-10.11.1.tar.gz`，SHA-256 `35f42cd561b656af79051deda35d76b838d48a03f469bd922c15c05310cab019` |
| Production | `pwestudio.online` = v10.11.1；deep health `db=ok`、`mode=saas`、`stale=0`；四个公开演示页已换成「数据由运营手动重置」（线上实测 nightly 残留 0）；集成页 Beta 徽标已在线上 bundle；`xero-push` tick 干净（`tenants=6 gate-closed=4 jobs=0 tenant-errors=0`）；**真租户 `lets-paint-studio` 推送开启 → PWE GROUP PTY LTD（X4 结算月进行时）**；showcase → Demo Company soak 不变 |
| Backup / migration | v10.11.1 部署前 dump `studiosaas_studiosaas_20260820T063742Z.dump` + manifest（**经改正后的凭据路径产出，这本身就是 OPS-04 的验收**）；schema 仍至 `0047_xero_transport.sql`（本轮零迁移） |

完整证据见 `docs/handoff/claude/2026-08-16-v10.8.0-round.md`（v10.8.0）与 codex/001（v10.7.1 历史）。

## 最新轮次

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
