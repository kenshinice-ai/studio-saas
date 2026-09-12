# 2026-09-12 · 品牌对齐 R1：先补网，再改样式（v10.19.0）

> 状态：**已发布、已部署**（2026-09-12）。`pwestudio.online` = v10.19.0，
> 提交 `6f1b186` 在 `origin/main`，两个包已构建。四层身份与部署后验收见
> `docs/HANDOFF_LATEST.md`。
> 上游依据：`23-PWE Studio SaaS 风格与内容对齐·变更单.md`（v2.4）+ 本会话的只读核查。
> 核查结论页：<https://claude.ai/code/artifact/c6ef01d2-8e68-4c69-90f6-251f209226e5>

## 为什么是这个顺序

变更单把 L1（对外门户）排在第一个做，并当成最便宜的一层。核查下来它是**门禁最弱的
一层**：

| 守卫 | L1 门户 | L2 租户站 | L3 后台 |
|---|---|---|---|
| 浏览器矩阵 | **0 / 13** | 4 / 13 | 9 / 13 |
| 颜色字面量守卫 | **无** | 有 | 有 |
| 内联脚本语法检查 | **无** | 有 | 有 |

所以这一版的第一个提交是门禁，不是样式。改样式之前先让网能接住东西——**并且先把每
一张网弄红一次**，用的是新造的缺陷，不是它刚修好的那个。

## 五个提交

### 1 · `f55c05a` 门禁

**给 L1 补三张网**

- `ui_matrix.yaml`：13 → 22 页，新增 `/studio`、`/zh/studio/`、`/pricing`、
  `/zh/pricing`、`/manual/`、`/zh/manual/`、两份法律文件、注册页。营销壳的导航叫
  `.nav`/`.nav-links`（不是公开壳的 `.navrow`/`.navlinks`），逐页覆盖选择器。
- 颜色字面量守卫：`marketing.css`、`pricing.css`、`manual.css`、
  `customer-resources.css` 与八个门户 HTML 进入 `TOKENISED_SURFACES`。旧注释估计
  「~76 处字面量」，**实测是 10 处**，已全部 token 化（`--wash-accent`、
  `--art-frame`、`--shadow-btn`、`--shot-bar`、`--cr-band-copy`、`--cr-band-line`）。
  `product-home.css` 明确留在外面，附**实数 30** 与理由（空间感首屏的渐变与阴影）。
- `verify_local.sh` 原本点名检查 7 个前端资源，此后新增的 11 个从未被检查——包括门户
  加载的每一个脚本。改成 glob + 下限。`check_inline_scripts.mjs` 增加四个门户根；
  `test_inline_scripts_parse.py` 改为从每页自己的 `<script src>` 推导，替掉两条写死
  的映射。

**五个「不可能变红」的门禁**

| 门禁 | 病因 | 修法 |
|---|---|---|
| `test_manual.py` | 断言浅色块里出现字符串 `--accent: var(--pwe-family-amber-text)`。那个替换是**对的**，而它正是编号圆点变成 3.64:1 的原因——圆点把 navy 画在 accent **上面** | 改成量：解析每条同时声明 background 与 color 的规则，在三个主题下各解析一次再相除 |
| `test_health.py` | 把 `sw.js` 的 `CACHE_VERSION` 钉成字面量：忘记升级它永远绿，正确升级的那一刻变红 | 值改成 `v` + VERSION，无自由标签；`release.sh` 的 bump 账本负责改写；断言改成校验推导 |
| `test_public_site.py` | `RESERVED_SLUGS` 与三个硬编码集合做 `<=`，只能发现删除。缺口当时就在：`/public-assets/<path>` 符合 slug 形状、被本应用路由、未保留 | 从路由表推导，双向比较，加解析下限与「过期豁免」检查——`SNAPSHOT_TABLES` 已有的形状 |
| `test_public_surface_recovery.py` | 模板与产物只比**函数名**，标记、CSS、文案、函数体全都看不见 | 走生成器自己的代码路径重渲染，逐字节比对。用一次纯 CSS 改动验证过：旧断言照样通过 |
| `ui_matrix.py` | 没有任何门禁调用它 | 本版未改（它需要真服务器与凭据）；见「未做」 |

新增共享 `backend/tests/_contrast.py`——对比度公式此前有**六份拷贝**，其中一份用错了
sRGB 阈值（0.04045 而非 0.03928）。

### 2 · `931d1b0` P0 四条

1. **四个线上客户站可能整片空白。** `tenant-template/index.html` 的
   `.reveal{opacity:0}` 没有 `.js` 门控，而 `revealAll()` 是顶层调用，前面压着约
   1,570 行**无 try 包裹**的顶层语句，第一句就读 `document.body.dataset` 与
   `window.StudioSaaS.esc`。任一处抛错 → 30 个内容块里 29 个永远不显示。营销页
   2026-07 就修过并有测试钉着；四个客户站赖以生成的模板没有。
   开关放在 reveal 接线处而不是脚本顶部：抛错的代价是没有淡入，不是没有页面。
2. **三份服务中的法律文件把私人 Gmail 当公开联系人**，包括隐私政策的数据泄露报告行；
   `/pricing.md` 又用第三个地址 `hello@pwestudio.online`，而该域名**没有 MX**。
   统一为 `info@pwestudio.site`（Cloudflare Email Routing，角色地址而非个人）。
   旧测试把 Gmail 钉成 `CONTACT_EMAIL`，且只覆盖两份文件——漏掉的正是告诉工作室
   「往哪里报泄露」的支持政策。
3. **错误页是一行未加工的 JSON。** 改 `errorhandler(404)` 没用：`/nope` 走的是租户
   catch-all 里的显式 `api_error`，全仓 48 处。内容协商放进 `api_error`，48 个出口
   一起继承。判据 `Sec-Fetch-Dest: document`，`Accept` 兜底，API 前缀恒为 JSON。
   `backend/frontend/error.html` 自带样式（它也回答从未落到任何租户的请求，一个依赖
   `/assets` 的错误页在 `/assets` 出问题时打不开），双语按地址决定语序，路径转义。
   房子站接不了这一条：`/` 是租户 catch-all，房子一认领根，所有
   `pwestudio.online/<slug>` 都进不去。
   顺带：`/customer-resources/` 自己就是 404——`<path:filename>` 不匹配空段，
   `server.py:1547` 那条 301 永远到不了。
4. **唯一的转化动作打开一封没有收件人的邮件。** `mailto:?subject=` 与 `sms:?&body=`
   都没有收件人。而 textarea 允许 1500 字，中文编码后约 13,500 字节，是邮件窗口
   静默不弹的临界点的十倍。`maxlength` 表达不了这个限制（英文 1 字节/字符，中文 9）。
   改成量出来再截断，并在正文里用读者的语言写明截断。

### 3 · `3097750` P1 七条 —— 以及门禁多找出的十七条

| # | 结果 |
|---|---|
| 05 | 手册编号圆点 3.64:1（打印 2.05:1）→ 16.45:1 / 21:1；搜索高亮改 38% 淡色底，13.4:1 / 6.9:1 |
| 06 | 审计说 3 处「警示色当文字」。写了实测门禁后是 **20 处**（Studio Admin 12、Super Admin 8，success/warning/danger/accent 四族全中，4.03–4.08:1）。**另有 6 处 hover 态**逐条规则永远看不见——`:hover` 只改底色、文字色从基础规则继承，两个控制台的每个淡色按钮在指上去那一刻变成 3.1:1。新增五个 `--on-<role>-border` token，门禁改为把基础规则折进状态规则。**五条比值注释是错的**，其中三条引用的 token 早已不存在 |
| 07 | CMS 启动转圈自 2026-07 起是静止的。`legacy-root/index.html` 自己的块是对的，杀死它的是 `ui-tokens.css` 与 `brand-system.css` 里 `*` 上的 `animation-iteration-count: 1`。改成 `.sp` / `[role=progressbar]` / `[data-motion=essential]` 用透明度脉冲替代旋转 |
| 08 | `showcase.html` 与 `timetable.html` 用 `transition:none!important`（连同 `animation:none`）——**移除属性**，不是归零时长。十个文件（含租户副本） |
| 09 | CMS 全局学员搜索框、`TabPanel`（`tabIndex={0}` 且去掉 outline）；两处基线 `:focus-visible` 选择器都不含 `summary` 与 `[tabindex]` |
| 10 | `--control-line` 浅色 `rgba(14,23,41,.34)` 实测 **2.14:1**，注释写着 3.90。`.55` 才是 3.90。三个消费者跟着修，其中输入框边框的注释本来就点名引用了 WCAG 1.4.11 |
| 11 | 28 处毛玻璃零兜底：`prefers-contrast`、`prefers-reduced-transparency`、`@supports` 全仓各 0 次。一个 `--glass-opacity` 契约，三重守卫 |

**更正审计自己的一条**：blanket `transition-duration:.01ms` **不会**删掉颜色反馈——
`transition-property` 还在，颜色照样落地，只是瞬时，而瞬时正是减少动态该有的行为。
坏掉的只有动画那一半。

### 4 · `14b387d` L1 门户观感

- **A（已定）主按钮改墨底纸字。** `.btn` 原是琥珀实底：能读（9.70:1），但让琥珀成了
  **每一个**按钮的颜色——首页三个 + nav CTA + 推荐徽章，一个站五处琥珀作地。一处标记
  五件事等于什么都没标。现在是 `background: var(--ink); color: var(--surface)`，一条
  声明在三种底上都对（夜 16.45、纸 16.45、琥珀带里自动变成藏青底琥珀字 9.70）。
- **12 全站唯一的琥珀作地要新建。** `#contact` 此前是 band-2。`.band-amber` 重定义
  同样那五个表面 token，整段（含表单）自动换肤，没有第二份规则。它**不跟随深浅色**——
  是全页唯一的暖色，这就是它的作用。推荐徽章改为描边胶囊：琥珀当标记，不当底。
- **13 买的那一刻没有主动作。** `#plans` 注入三个一模一样的 ghost。推荐档现在拿主按钮，
  与它上面的徽章说法一致。
- **14（B 已定：Georgia 留）** 字重 500 → 600、字距 −0.035em → −0.018em。
- **15 手写的月费。** 定价页两条 meta description 写着「monthly plans from AUD 49」，
  49 是 Starter 的价，从这页其余部分渲染所依据的那张表里抄出来的。旧守卫只禁 `$49`
  写法且只读 product-home。
- **16 一整个次级文字层从未渲染。** `pricing.css` 六次读 `--muted`，两张表都不定义它。
  新门禁 `test_tokens_resolve.py` 按页走它自己的 `<link>` 集合。
- **21（E 已定）showcase 就是 showcase。** Let's Paint Studio 是真的，跑在自己的独立
  部署上；`/lets-paint-showcase` 是本部署上的演示租户。产品页不再说「已在生产环境运行」。

### 5 · `7828858` L2 与收尾

- **18** 手册与五份客户文档都没有 `PWE · 天域出品`，而 `BRAND_ARCHITECTURE.md` 点名
  要求。第三种措辞 `Powered by PWE · 天域` 也在野（密码设置页）。守卫走
  `git ls-files` 而不是 `grep -r`：这台机器的 grep 是 ugrep 包装器，静默遵守
  `.gitignore`，一条写成「扫一遍仓库找品牌残留」的门禁从一开始就看不见生成的租户产物。
- **17** `.progress-fill.green` 画的是 `var(--info)`。
- **23** 审计说「15 个 JS 注入的 img 缺宽高」。只有一个槽位的盒子是固定的（注册页
  42px），已声明。导航锁定的前提不成立：`.brand img` 是 `height:40px; width:auto`，
  因为工作室上传任意比例；**重排的原因不是图片解码，是文字名换成 Logo 那一下**
  （`.brand.has-logo .bn`），宽高属性防不住。CSS 能做的只有把槽位兜底成正方形；剩下
  那部分需要 Logo 的真实尺寸，而 `/v1/public/<slug>` 返回的是
  `settings->>'logo_url'`，一个裸 URL，记录上没有地方读宽高。那是数据改动，不是样式
  改动，本版只记录。

## 本机门禁

```
bash backend/scripts/verify_local.sh   →  All checks passed ✅
pytest                                  →  2367 passed, 135 skipped
tenant isolation                        →  254 passed, 0 failed
```

三个生成步骤都跑过：`build_cms.sh`、`build_asset_manifest.py`、
`regenerate_tenant_workspaces.py`（4 个工作区）。

## 浏览器实测（本机 1024 与 375，浅色与深色）

| 量的东西 | 结果 |
|---|---|
| 主按钮 | `rgb(14,23,41)` 底 / `rgb(247,245,242)` 字 |
| 次按钮描边 | `rgba(14,23,41,0.55)` = 3.90:1 |
| 推荐徽章 | 透明底，`#a16207` 字与描边 |
| 收尾带 | `rgb(245,179,53)` 底、藏青字 |
| h1 | 600 / −0.018em / Georgia |
| 深色定价页 | 推荐档按钮实底 `rgb(247,245,242)`，另两个仍是 ghost；`.calc-note` 解析为 `rgba(255,255,255,0.55)`（此前无效） |
| `<html class>` | `js`（P0-01 的开关确实合上） |
| 404 | `/nope` 英文在前、标题 `Address not found`；`/zh/nope` 中文在前 |

## 未做，以及为什么

- **把 `ui_matrix.py` 接进门禁。** 它要真服务器 + 真凭据；接进 `verify_local.sh` 会让
  本机闸依赖网络与一份 0600 凭据文件。本版把它的**覆盖面**补齐（13 → 22 页），接线
  留给单独一轮。
- **P2-19 中英句读 18 对、P2-20 胶囊里的箭头。** 前者是 18 次文案判断，后者按本项目的
  i18n 规则等于一次键迁移（词典里的箭头是键）。都不适合塞进这一版。
- **P2-22 CMS 31 处 9–10px 字号、控制台字号收敛。** L3，属 R2。
- **间距与圆角统一。** 自成一个项目：七套间距梯、十一套圆角梯、约 1,905 处手写调用，
  外加 2,975 个会随 `theme.spacing` 静默改值的 Tailwind 工具类。
- **`product-home.css` 的 30 处颜色字面量。** 见上，理由已写进守卫的注释里。

## 给下一轮的话

这一版新增了七个能量、会红的门禁。它们已经在本轮里找出十七条没人报过的缺陷，其中
六条（hover 态）是任何逐条规则的检查都看不见的。**改样式之前先看它们红不红**——
`gates-go-blind-quietly` 那条记忆里的三种失明形状，这一轮又见到两种。
