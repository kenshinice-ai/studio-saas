# PWE Studio v10.11.0 — Handoff 索引（2026-08-16 起按 AI 分目录）

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

## 当前四层身份（v10.10.3，2026-08-19）

| 层 | 精确事实 |
|---|---|
| Source | v10.10.3 发布提交 `dae3fd4`（同日链：`4fd0ee1` v10.9.4 → `e158997` v10.10.0 → `e5aaefd` v10.10.1 → `338b9b5` v10.10.2 → `dae3fd4` v10.10.3 同号守卫） |
| Package / SaaS | `dist/PWE-StudioSaaS-aws-10.10.3.tar.gz`，SHA-256 `9db6217b94448680c29b7fbdc29f168a59264fc142774679ec94de3fa756d631` |
| Package / Edition | `dist/PWE-Studio-Edition-10.10.3.tar.gz`，SHA-256 `948073bc17b62980c36974b4f13c24be8b00d3cfd0c3b231e4496edd06559154` |
| Production | `pwestudio.online` = v10.10.3；deep health `db=ok`、`mode=saas`；**真租户 `lets-paint-studio` 推送已开启 → PWE GROUP PTY LTD（真账本，X4 结算月进行时；LPS- 单号前缀；首单 LPS-INV-0002 已在账本可见，对账 0 差异）**；showcase → Demo Company 推送开启作 soak；`xero-push.timer` 每 5 分钟 drain |
| Backup / migration | v10.10.3 部署前 dump `studiosaas_studiosaas_20260819T105709Z.dump` + manifest；schema 至 `0047_xero_transport.sql` |

完整证据见 `docs/handoff/claude/2026-08-16-v10.8.0-round.md`（v10.8.0）与 codex/001（v10.7.1 历史）。

## 最新轮次

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
