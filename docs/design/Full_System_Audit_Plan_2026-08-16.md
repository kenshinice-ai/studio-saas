# 2026-08-16 全面体检与下一轮方案（基线 v10.7.1，rev2）

> **历史状态说明（2026-08-23）：**本文以 v10.7.1 为审计基线，后续多批工作
> 已推进至 v10.13.0。它仍是审计证据与决策来源，但当前完成/未完成状态必须
> 以 `docs/HANDOFF_LATEST.md`、`docs/README.md` 和最新专项清单为准。

> 性质：**只审计、只设计方案**。本轮没有修改运行时代码，没有 commit / package / deploy；
> 唯一的执行动作是 handoff 文档拆分（Lee 指示，docs-only，见 §5）。
> 方法：仓库以 main `501c741`（v10.7.1）为基准逐文件复核；线上以 `pwestudio.online`
> 真实浏览器逐界面复核（官网、定价、showcase 三个公开页、studio-admin、CMS、super-admin，
> 多档宽度）。handoff 只作线索，结论均另行取证。
>
> rev2（同日）：按 Lee 反馈修订——演示租户手动 reset 定性为既定决策；异地备份/告警
> 改为「方案就绪、暂缓执行」；新增账务与学员档案产品优化（Batch E）与 Xero 对接路线图
>（Batch F）；handoff 拆分方案落地并确立按 AI 分写的新惯例。

---

## 0. 一句话结论

v10.7.1 声称关闭的八项（P0-01..P0-05、P1-01..P1-03）**在代码层全部真实关闭**，
账务域这一轮没有新账要还；本次体检发现的问题换了域——集中在四类：
**① 品牌区（logo/标题）渲染合同不统一；② 错误状态 UX（403 文案、失败后仍可编辑）；
③ 运维单点（备份同机、无告警、nginx 游离）——方案就绪、按 Lee 决定暂缓执行；
④ 流程债（版本台账手改、HANDOFF 巨石、打包双轨）。**

## 1. 体检证据

### 1.1 handoff 说法 vs 复核事实

| 说法 | 复核结果 |
|---|---|
| v10.7.1 八项全部 completed | **属实**。逐项有实现与测试：public-shell.css + `public-surface.js` 四级退化状态机；migration 0044 + `credit_refunds.py:299-346` source 上限双检查；税率直接继承 `invoice_lines.tax_rate_bp`（`credit_refunds.py:566-579`）；`InvoicePrintableDocument`（`billing.jsx:100-117`）；`invoice_drafts.py` aggregate command（幂等 + payer 预检）；ledger CSV UNION 四类单据 |
| v10.7.0 审计的桌面导航整体折叠（NAV-01） | **线上不复现**。showcase 与 timetable 在 1440px 桌面导航完整显示 |
| `package_release.sh` 会被拒 | **比记忆更糟**：没有任何代码拒它，且 `docs/Deployment.md:150-152` 仍在教用它 |
| 演示租户 nightly reset 从未运行 | 属实（launchd/systemd/cron 均无定时器）。**rev2 定性：手动 reset 是既定决策，不装定时器**；剩余动作只是把这一点写进销售/演示文档（OPS-05） |
| pem 私钥安全 | 未入 git（`.gitignore:22`），但躺在 iCloud 同步的公开仓库工作目录根部、权限 644 |
| git 同步 | main == origin/main，工作树干净；dist/achieve/backups 均未被追踪 |

### 1.2 线上新发现（本轮实测）

| # | 现象 | 位置 | 定性 |
|---|---|---|---|
| L1 | timetable 页头 **logo 图与文字标题同时渲染**，文字截断成「Let's…」；同租户 index/showcase 页只渲染文字。同一 tenant 三页三种品牌形态 | `/lets-paint-showcase/timetable` 1440px | P1，即用户报告的 logo/title 问题主形态 |
| L2 | CMS 侧栏品牌区：logo + 文字「Let's Pain…」截断；studio-admin 头部 logo 被 28×28 方框压成 **约 7px 高的墨点**（宽横比 logo + `object-fit:contain`，`backend/frontend/studio-admin.html:94-99`） | CMS / studio-admin | P1，同一根因：品牌合同不适配宽 logo |
| L3 | lets-paint-studio 的 CMS 在支持门禁 403 时显示「**连接失败，请确认终端正在运行 python3 server.py**」 | `legacy-root/src/cms-app.jsx:3988-3997`，load 失败不分 401/403/网络 | P1，单机版文案泄进生产；「静默兜底就是缺陷」类 |
| L4 | studio-admin 租户数据载入失败（403）后**仍渲染成可编辑的默认表单**，而非阻断态；此时保存/发布按钮均在 | `/lets-paint-studio/studio-admin`（无支持会话时） | P1，有把默认值误存覆盖真数据的风险面 |
| L5 | studio-admin 头部在 1024px 换行成两行，语言/刷新/账户按钮压进内容区 | studio-admin 1024px | P2 |
| L6 | 管理端三处品牌区在 1440/1024/390 均未量到字面「重叠」；公共页历史上确有 logo 压住首个导航链接的事故（已修，注释留档 `tenants/lets-paint-showcase/index.html:95-114`）。用户看到的「重叠」若非 L1/L2 形态，需先排除旧缓存再逐宽度量 | — | 结论依据「量渲染结果，别量代码」 |
| L7 | super-admin 待处理 4 项：JJL's Studio 订阅 2026-08-16 22:31 到期、showcase 团队账号 4/5（80%）、ruby-s / n-piano 两条 onboarding follow-up | super-admin 工作台 | 运营动作，非代码 |
| L8 | 定价页 /pricing 三档 $49/$99/$189 由已发布套餐驱动，与「页面不写死价格」不变量一致；官网/公开页/健康均正常 | — | 通过 |
| L9 | **英文导航全体省略号**（Lee 截图实证：宽屏下 Principal→「Princi…」、Timetable→「Timeta…」乃至品牌全部截断）。冷加载 `?lang=en` 与本轮手动切换未必复现，说明是状态机**滞留态**：四级退化钳位（`public-surface.js:386-440`）挂上后，某条路径（最可疑是中→EN 切换时标签变长）没有从 `resetStates` 重新测量。另：即使 EN 状态正常时，品牌文字在 1870px 仍截为「Let's Pai…」（同 L1） | showcase 首页 EN | P1，NAV-01 家族残留 |

### 1.3 未实现清单（真实状态，防「假需求」回流）

| 项 | 状态 | 处置 |
|---|---|---|
| 服务端 PDF | 不存在任何 /pdf 端点；「打印/存为 PDF」=浏览器打印（故意，checklist §5 明文不做假端点） | 先关掉「真机保存 PDF 验收」尾巴，再决策 renderer（PROD-01） |
| Xero transport | `TRANSPORT_AVAILABLE=False` 硬编码（`xero.py:44-48`）；UI 诚实标注 Preview·不发数据 | **rev2：正式规划对接路线图（Batch F）** |
| SMS 发送 | 无租户 provider 时显式抛错（`notification_channels.py:268,285-300`） | 维持诚实 stub |
| S3 媒体 / SES 邮件 | 开关在、实现无（`media.py:412-415`；全仓库无 boto3） | Phase 3 原计划，不提前 |
| Redis 限流 | 进程内 dict + Lock（`api_v1.py:164-175`）；单实例够用，pilot 期禁 Redis 是 README 政策 | 维持 |
| 异地备份副本 | 无。备份与生产同一台 Lightsail（`Release_Runbook.md:239-240` 自认） | **方案就绪、暂缓执行（OPS-01，见触发条件）** |
| 监控/告警 | 只有 cron 邮件与磁盘阈值退出码 | 同上（OPS-02） |
| 演示租户 nightly reset | 定时器从未存在 | **已定性：手动 reset 即决策**（OPS-05 只补文档） |
| 公开页冷加载 #anchor 落点偏移 | handoff 线索级记载，本轮未复核 | 下一轮顺手验证（UI-04） |

---

## 2. 下一轮执行方案

按既有纪律：不猜、不静默丢弃；每项以代码 + 测试 + 真实浏览器证据关闭；
P0 全过才做 P1；全部完成后停在 STOP GATE，等 Lee 明确授权再 commit/package/deploy。

### Batch A — 对外可见缺陷（建议为 v10.7.2 的主体）

**UI-01 品牌区统一合同（修 L1/L2/L5）**
- 根因：各面对 logo 的假设不一致——public 页 `.brand img` 高度合同 + 显示/隐藏名字的状态机、CMS/studio-admin 是 28px 方框 + ellipsis 文本，都没考虑「宽横比、自带店名」的 logo。
- 方案：
  1. 定义唯一 brand lockup 规则并写进 `docs/Design_System.md`：logo 按**高度**定尺寸（如 admin 28px / public 40px），`width:auto; max-width:~140px`；名字文本**要么完整显示要么整体隐藏**，禁止截断到语义丢失。
  2. 增加租户级品牌选项「logo 已含店名」（studio-admin 品牌基础步骤里一个开关，默认关）：开启时凡 logo 可显示处即隐藏文字名——这是对 Let's Paint 这类手写字 logo 的正解，比任何自动测量都诚实。
  3. 三个公开页对「logo 是否替代名字」必须同一行为；管理端（CMS 侧栏、studio-admin 头部、super-admin）套用同一规则；studio-admin 1024px 换行布局顺手收口（L5）。
- 验收：showcase（有宽 logo）与 lets-paint-studio（无 logo）两租户 × {index, showcase, timetable, cms, studio-admin} × {1920, 1440, 1226, 1024, 390} 截图矩阵；断言为**语义断言**（名字可读或整体隐藏、logo 高度达标），不是 scrollWidth==clientWidth。

**UI-05 导航状态机：语言切换必须重跑测量（修 L9）**
- 根因方向：`public-surface.js` 的 settle 过程只挂在 load/font/resize 上；语言切换重写 nav 标签（中文短→英文长）后钳位类沿用旧测量，宽屏也全员省略号。
- 方案：语言切换（及任何改写 nav 文案的路径）后强制 `resetStates` → 重新逐 rung 测量；测量等 `document.fonts.ready`，避免在字体交换中途量出错误宽度。
- 验收（补 v10.7.1 缺口）：{1226, 1366, 1440, 1920} × {冷加载 zh, 冷加载 en, zh→en, en→zh, resize 往返} 矩阵；**语义断言 = 每个 nav 链接与品牌名不得处于省略号截断态**（逐元素 `scrollWidth <= clientWidth`）。

**UI-02 CMS 连接守卫分流（修 L3）**
- load 失败按状态分流：401 → LoginScreen；403（`support_session_required`/权限）→ 专用「无权访问 / 需要支持会话」界面，附去 super-admin 开支持会话的指引；网络/5xx → 重试界面。
- SaaS 模式彻底删除「python3 server.py」文案（standalone 版按 `TENANT_SLUG` 有无区分保留）。
- 验收：无支持会话访问 `/lets-paint-studio/cms` 显示权限态而非连接失败；测试断言三类状态各自 UI。

**UI-03 studio-admin 载入失败即阻断（修 L4）**
- 载入失败渲染阻断态（错误 + 重试 + 支持会话指引），隐藏/禁用整个编辑区与「保存草稿/发布」。
- 验收：403 场景下不存在可交互的保存/发布按钮。

**UI-04 锚点冷加载偏移（验证项）**
- 真机复核；真则修（异步块 reserve 高度或 load 后 re-scroll），假则在 handoff 撤条。

### Batch B — 运维（rev2：方案就绪、暂缓执行）

> Lee 决定（2026-08-16）：当前全部为内测租户、无真实付费客户，OPS-01/02 **只备方案不执行**。
> **触发条件（写死）：第一个真实付费租户签约上线前，OPS-01/02 必须先行完成**；或 Lee 提前指令。
> OPS-03/04/06 属低风险卫生，可随任意代码轮捎带执行（仍需 Lee 授权 commit）。

**OPS-01（P0，暂缓）异地备份副本** — 方案已定稿备用：
- rclone 每日把最新 dump + volume 包推对象存储（S3/B2/R2 任一，成本 <$5/月），keep-N=14，副本带 SHA-256 清单；恢复路径写进 Runbook；装配估时半天。

**OPS-02（P1，暂缓）备份失败与 uptime 告警** — 方案已定稿备用：
- 「备份产物年龄 > 26h 即告警」cron + 外部 uptime 探测（UptimeRobot 级）盯 `/` 与深健康；每周 dump restore dry-run。历史教训：cron 备份曾静默失败数周（`lightsail_ctl.sh:118-121` 注释自认）。

**OPS-03（P1）nginx 配置收编** — 把线上 `pwestudio.conf` 原文抓回仓库（`deploy/aws/nginx/live/`）作 canonical 基线；此后先改仓库再逐行上机。消灭「不要整体覆盖」口口相传（HANDOFF 旧档:486-495）。

**OPS-04（P1）备份 owner-URL 拼接加固** — `lightsail_ctl.sh:122-128` 的 sed 抠密码拼 URL 改为 `backup_postgres.py` 读 env + urlencode。

**OPS-05（P2，已定性）演示租户 reset** — 手动 reset 即决策；唯一动作：在销售/演示材料与 `docs/Admin_Guide.md` 写明「演示数据由运营手动重置（RESET_DEMO_TENANT.command）」，防后人再当缺陷报。

**OPS-06（P2）本机卫生** — pem 移 `~/.ssh/pwestudio-lightsail.pem`（`pwestudio_remote.sh:16` 本来就期望它）chmod 600；dist/ keep-N 清理（1.6GB 别再喂 iCloud）。

### Batch C — 发布链路去手工化（rev2 强化）

**REL-01（P1）一键 release 编排（升级版，吸收原 REL-01/03）**
- 不止 bump 脚本：做 `backend/scripts/release.sh <ver>`，把 Runbook 步骤 2→8 串成一条命令、三个确认点：
  1. `bump`：一次改齐 VERSION / server.py / guides 页脚 / README / release notes 骨架 / Edition docs（消灭「7 处手改」）→ 自动重跑 preflight；
  2. `verify+build`：verify_local → 提示 commit →（确认点①）→ build_aws_bundle + verify_release_bundles；
  3. `deploy`：**三方 commit 比对护栏**（bundle BUILD_INFO == 本地 HEAD == origin/main，不一致即拒——把 Runbook:71-75「step 6 后不得再加东西」变成机器强制）→（确认点②）→ pwestudio_remote deploy →（确认点③）deep health 摘要。
- 每步只是调既有脚本，不重写任何 gate；失败即停在原步骤语义上。人的角色从「按 9 步操作」变成「做 3 次决定」。

**REL-02（P1）打包双轨清理** — `package_release.sh` 开头硬提示并 exit（git 史留档）；`docs/Deployment.md:150-152` 标注「历史留痕，现行流程见 Release_Runbook」。

**REL-04（P2）esbuild 锁定** — package.json + npx 固定版本，替换「全局安装 + 两处字符串一致」（`build_cms.sh:29-31`）。

**REL-05 handoff 拆分** — **本轮已执行**，见 §5。

**REL-06（P2，新）UI 验收矩阵脚本化**
- Batch A 两个截图矩阵（UI-01/UI-05）总计上百个组合，手工点不完也留不下可复跑证据。做一个 Playwright 薄壳 `backend/scripts/ui_matrix.py`：读一份 YAML（页面 × 宽度 × 语言 × 动作序列），产截图 + 逐元素语义断言 JSON。
- 与「静态测试看不见错常量」记忆一致：这是把「真实浏览器验收」变成可复跑资产，而不是替代它；先只覆盖 nav/brand 断言，不贪大。

### Batch D — 产品尾巴

- **PROD-01（P1）** 真机「存为 PDF」验收：目标浏览器保存一次 INV 文档，验证可搜索文字/中文字体/分页（acceptance evidence §5 承认的最后尾巴）；通过后再决策 server-side PDF 是否立项。
- **运营（非代码）**：处理 super-admin 4 条待办（JJL 订阅到期、showcase 团队账号 80%、两条 onboarding 跟进）。

### Batch E — 账务 / 学员档案 / 历史记录产品优化（rev2 新增，设计稿）

> 原则：全部建立在已有能力之上（发票中心、ledger UNION 查询、settlements 幂等、payer 账户），
> 不引入自动扣款/自动催收——「结算故意保持手动」是商业决策，不动。
> 建议排期：E1/E2 随 v10.8.0，E3/E4 视反馈；每项落地前单独出交互稿。

**E1（P1）学员统一时间线**
- 现状：学员详情「记录」页是三段折叠（成长报告 / 充值记录 / 上课记录），账务事件另散在发票中心；前台想回答「这孩子这半年发生了什么」要开四个地方。
- 方案：学员详情新增单一时间线视图，按时间倒序合并：报名/审批、充值（含套餐名）、扣课、发票开具/收款/贷记/退款、成长报告发布。后端**复用 ledger UNION 查询**（`api_v1.py` invoices/export ledger 视图）加 per-student 过滤，不新造数据面；每条账务事件深链到发票中心对应单据。
- 验收：时间线条目数 == 各来源之和（不吞、不重）；每条可跳转；只读，无写入路径。

**E2（P1）付款方月结单（Statement）**
- 现状：payer 账户只有「未结 $X」一个数；一家多娃（如 Raman 一家）没有对账视图；这也是 Xero 对账的前置能力。
- 方案：payer 维度「月结单」视图 + 打印（复用 `InvoicePrintableDocument` 的打印壳）：期初余额、当期发票/收款/贷记/退款流水、期末余额。数据全部来自既有 ledger，快照语义与发票文档一致（读 issued snapshot，不读 live）。
- 验收：任一 payer 的月结单期末余额 == 账户当前未结（同期截止）；打印输出走 UI-01 之后的品牌抬头与 P0-04 的打印通道。

**E3（P2）逾期/未收工作流（手动优先）**
- 现状：发票中心已有 逾期/未收 分桶，但工作台「今日重点」看不见钱的事，跟进无记录。
- 方案：工作台加「未收合计 / 逾期 N 张」卡（复用分桶统计）；发票详情加「已提醒」手动标记 + 备注（记入既有事件历史）。**不做自动发信**（SES 未建，且催收话术是老师与家长的关系活）。
- 验收：标记进事件历史且导出可见；无任何自动外发路径。

**E4（P2）低课时 → 续费闭环**
- 现状：工作台已统计「低课时 2 人」，但从名单到充值要人肉转场、重选学员。
- 方案：低课时卡片每人一键「去充值」：预选学员 + 预填上次套餐，落到既有充值表单（含「同时创建发票」勾选）；仍由人确认提交，幂等由 credit-settlements 保证。
- 验收：从卡片到完成结算 ≤3 次点击；未确认前无任何写入。

**E5（P2）审批建档的重复候选前置**
- 现状：手工发票流已有 payer 创建前重复预检 + 显式例外（P1-01 落地），但报名审批「批准建档」仍可能造出重复学员/payer。
- 方案：把同一预检（姓名/手机/邮箱模糊匹配）搬到审批面板：批准前显示「疑似已有档案：Ana Bianchi（0400…103）」候选，提供「合并到既有档案 / 确认新建」显式选择；不自动合并（既有纪律）。
- 验收：候选提示先于任何写入；选择记入审计日志。

**E6（P2）开票信息完整度门**
- 现状：设置有「开票信息」页，但首张发票开具前无人校验 ABN/地址/抬头是否齐全，单据质量靠运气（与 PROD-01 的 PDF 质量验收同一条线）。
- 方案：签发（issue）动作前检查开票信息完整度，缺则给出去补齐的链接；draft 不拦。
- 验收：开票信息不全时 issue 被软阻断且提示可达设置页。

### Batch F — Xero 对接路线图（rev2 新增，立项规划）

> 现状盘点：`xero.py` 455 行 preview 已含三层门（加购权利、渠道冲突问答、mapping 就绪）、
> InvoiceDocument DTO mapper、外发队列模型；缺的只是 transport 及其运维面。
> 总原则：**单向 PWE→Xero**（PWE 是课时/发票事实源），不做双向同步、不做付款回导；
> 每阶段独立可停，前一阶段是后一阶段的硬门。

| 阶段 | 内容 | 硬前置 / 出口条件 |
|---|---|---|
| X0 合同层（已完成） | gates、DTO mapper、queue 模型、UI 预览与「不发数据」承诺 | 已在 v10.7.1 |
| X1 账务真值补齐 | E2 月结单 + E6 开票信息门 + PROD-01 PDF 验收——保证推给 Xero 的每张单据在 PWE 侧已是合格客户单据；把 UI 里「是否已有渠道（如 Square）在同步 Xero」问答落成租户级配置位 | 出口：任一租户能产出抬头齐全、快照一致的单据流 |
| X2 transport MVP | Xero OAuth2（auth code + PKCE）连接流：集成页「连接 Xero」→ 回调 → per-tenant token 加密存储（复用现有 secrets 处理惯例）+ 自动 refresh；先只做 **demo company sandbox**；连接状态/断开在集成页可见 | 硬门：Lee 注册 Xero developer app；出口：sandbox 租户连接、断开、token 过期自愈三条通过 |
| X3 外发 worker | 队列消费：issued invoice / payment / credit note 推送；幂等 = 发票号 + Xero reference 双键；重试退避；死信在集成页可见并可手动重推。**不引 Redis/Celery**：单实例下用 systemd timer 定时跑管理命令消费队列（与 pilot 架构政策一致） | 出口：sandbox 全量单据类型往返对账 0 差异 |
| X4 Beta（单租户真账） | Let's Paint Studio 自己的账本接真 Xero 组织，单向推送跑一个完整结算月；出对账报告（PWE ledger vs Xero）；期间集成页标 Beta | 出口：一个自然月 0 人工修账 |
| X5 GA | 按套餐开放（加购权利门已在）；文档 + 客户指引 | 触发：第一个付费租户有真实需求 |

- 明确非目标：双向同步、付款从 Xero 回导、历史数据回填（X4 起点前的历史单据只入对账报告，不补推）。
- 建议节奏：X1 并入 v10.8.0（它本来就是 Batch E 的 E2/E6）；X2 起需要 Lee 的 Xero developer 账号，单独排轮。

---

## 3. 版本与执行顺序建议（rev2）

1. **Batch A（UI-01/02/03/05 + UI-04 验证）→ v10.7.2**：对外可见缺陷一轮关闭，走完整 Runbook。
2. **Batch E 的 E1/E2 + F 的 X1 + PROD-01 → v10.8.0**：账务可读性与单据质量一轮做齐（互为前置）。
3. **Batch C（REL-01/02/04/06）** 随上述两轮捎带；REL-05 本轮已完成。
4. **Batch F X2 起** 单独排轮，等 Xero developer 账号就绪。
5. **Batch B**：OPS-03/04/06 捎带执行；OPS-01/02 保持就绪，**第一个付费租户上线前强制先行**。

## 4. STOP GATE

本文件是方案，不是完成声明。任何 commit / package / push / deploy 均需 Lee 明确授权后按
`docs/Release_Runbook.md` 执行；届时每项以「先失败后修复」的测试与真实浏览器证据逐条关闭。

## 5. handoff 新惯例（本轮已执行的唯一动作）

- `docs/HANDOFF_LATEST.md` 瘦身为**索引 + 当前四层身份**；历史 95 节按原文原样、原顺序拆入
  `docs/handoff/codex/`（`index.md` 列目录）；本轮起 Claude 的记录写 `docs/handoff/claude/`。
- 惯例：**每个 AI 只写自己目录下的轮次文件**（`YYYY-MM-DD-主题.md`，一轮一文件），
  并在 `HANDOFF_LATEST.md` 更新指针与四层身份表；不再向单文件追加叙事。
- 拆分以字节保真校验（拼回 == 原文件 SHA-256 一致）后才替换。
