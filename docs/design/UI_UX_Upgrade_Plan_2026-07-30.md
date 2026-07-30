# UI/UX 升级方案 — 门户 / CMS / 报名

> 日期：2026-07-30 · 适用版本：v8.1.0 · 状态：**P0 的 1/2/3/4/6 已落地（v8.1.0），其余仍是方案**
>
> 落地情况（2026-07-31 更新，逐项对照第 8 节清单）：
>
> | # | 状态 | 依据 |
> |---|---|---|
> | 1 `.result-card` 硬编码色换 token | ✅ 已落地 | `tenant-template/index.html:270,543` + 6 个已生成租户工作区；`backend/tests/test_portal_theme_contract.py` |
> | 2 `.surface-status` 改语义色 | ✅ 已落地 | `tenant-template/index.html:263` |
> | 3 焦点环换 amber-text | 🟡 **只做了一半** | `product-home.html:56,62` 已改；`backend/frontend/cms-entry.html:66` 未动 |
> | 4 深色表单边框 .28 → .42 | ✅ 已落地 | `product-home.html:171` |
> | 5 product-home 接入 `ui-tokens.css` | ⬜ 未落地 | — |
> | 6 CMS 接入 21 个主题 token + 删冷灰底 | ✅ 已落地 | `legacy-root/index.html:62,334` |
> | 7 CMS 语义色替换 8 个 Tailwind 档位 | ⬜ 未落地 | — |
> | 8 `text-gray-400` 128 处 | ⬜ 未落地 | — |
> | 9 disabled 换表面+文字色 | ⬜ 未落地 | — |
> | 29 CMS 两套深色合一 | ⬜ 未落地 | 由 `test_portal_theme_contract.py::test_the_second_cms_dark_system_is_still_recorded_as_open` 盯住，做完时该测试会失败并强制同步本文件与 handoff |
>
> P1/P2 各项除上表列出者外，均未落地。本文件其余部分保持方案原文，
> 不因已落地而改写——诊断与实测数值是这些改动的依据，需要留痕。
>
> 参考系统：LetsPaintCMS v7.3.7（单店，已在真实画室运营）
> 本轮只出方案。所有结论都标注了证据来源（`文件:行号`）或实测数值。
> 对比度均按 WCAG 2.1 相对亮度公式计算，`docs/design/palette_gen.py`
> 的 `ratio()` 是同一套算法。

---

## 1. 执行摘要

五条改动，按"现在做"的理由排序。

### 1.1 把 CMS 接入 token 系统（P0）

**判据**：`legacy-root/src/cms-app.jsx` 全文 5055 行，`var(--` 只出现 **8 次**
（且 7 次是 `--accent`、2 次 `--accent-dark`，都不是仓库里定义过的 token）。
其余全部是 Tailwind 原子类：`text-gray-400` **128 处**、`text-gray-500` 106 处、
`bg-indigo-600` 34 处、`bg-indigo-700` 33 处。

`text-gray-400` = `#9ca3af`，实测：

| 底色 | 对比度 | 结论 |
|---|---:|---|
| `bg-white` | 2.54:1 | 不足 4.5:1 |
| `bg-gray-50` | 2.43:1 | 不足 |
| `bg-gray-100` | 2.31:1 | 不足 |

**为什么现在做**：这 128 处不是"看起来淡"，是 128 处不满足 AA 的文字，而
`docs/Design_System.md:111-127` 已经把"焦点可见 / 触控 44px / reduced-motion /
disabled 不靠 opacity"写成发布检查项。CMS 是唯一没被这套检查覆盖的高频界面，
每天有人用它录课时和签到。

### 1.2 让 CMS 真正显示租户主题（P0）

`legacy-root/index.html:297` 是 `body { background:#f1f5f9 !important }`
（Tailwind slate-100，冷灰蓝）。它压过任何租户主题背景。同时 `index.html:56`
的 `themeVars` 只映射了 21 个主题 token 中的 **10 个**，缺 `background_alt_color`、
`text_soft_color`、`border_strong_color`、`accent_hover_color`、
`accent_pressed_color`、`focus_ring_color`、`disabled_surface_color`、
`disabled_text_color`、`scrim_color`。

对照 `tenant-template/register.html:364-386`，那里的 `THEME_TOKENS` 映射了全部
21 个，并且注释写得很清楚：

> "Same declarative map as the portal, so the two surfaces can never apply a
> different subset of the theme again."

**为什么现在做**：门户和报名页已经进了这个契约，CMS 没进。`Brand_Identity.md:133`
写的是"Tenant studio — primary identity in **Studio Admin, CMS,** Portal and
Register"。现在租户选了 8 套主题里的任何一套，CMS 都长一个样。

### 1.3 修掉门户成功卡在深色主题下的隐形 bug（P0，最高优先）

`tenant-template/index.html:265`：

```css
.result-card{ ... background:var(--ink); color:#EFE9DD; ... }
```

`--ink` 由租户主题的 `text_color` 下发（`index.html:56` themeVars 之外，门户自己
的 THEME_TOKENS 也映射 `text_color → --ink`）。在浅色主题下 `--ink = #221E1A`，
`#EFE9DD` 对它 **13.69:1**，正常。在深色主题下 `--ink = #F1F0EE`（vintage-press
dark），`#EFE9DD` 对它 **1.06:1** —— 完全看不见。

同一段的 `.result-card .big`（那个 56px 的 ✓）是 `#EAD9C7`，深色下 **1.21:1**。
`index.html:538` 的"返回首页"按钮 `color:#EFE9DD`，同样 1.06:1。

15 个 theme-mode 里有 **7 个是 dark**，而 `arcade-lime` **只有 dark**
（`docs/Design_System.md:67`）。也就是说任何游戏类租户 100% 命中。

**参考系统已经踩过并修好了这个坑**，`refcms/portal.html:410-413` 留着注释：

> "the Living Gallery light surface must also replace the legacy dark-card text
> colours. Keeping colour and surface in one rule prevents a future
> background-only override from recreating the unreadable state."

`refcms/docs/CMS_DESIGN_SYSTEM.md:66` 把它写成规范：
「门户成功卡改变背景表面时必须在同一规则中同步声明文字颜色」。

**为什么现在做**：这是转化漏斗最后一步。家长点了"提交预约"，看到的是一张空白卡。
而修法只有一行：把 `color:#EFE9DD` 换成 `color:var(--bg)`。

### 1.4 补上 palette_gen.py 漏掉的一组断言（P1）

`palette_gen.py:174` 把 success / warning / danger 解到 `bg`：

```python
sem[role] = solve(blended, ss, bg, TARGETS['semantic'], darker=not dark)
```

但 `CHECKS`（`palette_gen.py:231-233`）也只检查 `/ page`。而门户有多个区块跑在
`--bg2` 上（`index.html:187` `.gallery`、`:416` `#courses`、`:457` `#faq`、
`:269` `footer`）。

我实测了全部 15 个 theme-mode × 3 个语义色对 `background_alt_color` 的对比度：
**45/45 全部低于 4.5:1**（浅色约 4.06–4.19，深色约 2.86–3.34）。

把 `solve(..., bg, ...)` 改成 `solve(..., worst, ...)`（`worst` 已经是 `bg2`，
见 `palette_gen.py:123` 与 `:141`）之后，实测位移很小且两边都过：

| 主题 | success 原值 → 新值 | 对 bg | 对 bg2 |
|---|---|---:|---:|
| vintage-press light | `#2F7951` → `#2D734C` | 5.00 | 4.50 |
| vintage-press dark | `#378E5E` → `#43AE74` | 6.71 | 4.53 |
| atelier-clay light | `#2E774F` → `#2C714B` | 5.04 | 4.50 |

**为什么现在做**：这是**改生成器**而不是改应用层。生成器是 15 个主题的唯一来源，
改一行 + 加 3 条 CHECKS（390 → 435 断言），比在应用层逐个躲开 `--bg2` 区块可靠。
目前这是**潜在风险**而非全面失效 —— 门户当前把语义色主要用在 `.form-card`
（`--panel`，5.19:1，通过）和学员区余额提示上；我不夸大成"线上已坏"。

### 1.5 字号级数补两个缺口，间距级数不动（P1）

现有 `--ui-type-*` 是 `13 / 16 / 21 / 34 / 55`。相邻比值：
13→16 = 1.23、16→21 = 1.31、21→34 = **1.62**、34→55 = **1.62**。
大端是 φ，小端不是，而且 **21 到 34 之间没有台阶**。

`Brand_Identity.md:85-87` 要求的是 28–36/700 display、20/600 heading、
15–16/400 body、11–12/600 label —— 现有 token 覆盖不了 11–12，也覆盖不了 24–28。

后果直接可测：CMS 里 `font-bold` **394 处**、`font-semibold` **0 处**。
只有 400 和 700 两档字重，加上字号缺档，唯一能造层级的手段就是加粗，于是
到处加粗，加粗就不再表示层级。同时出现 `text-[11px]` 21 处、`text-[10px]` 11 处、
`text-[9px]` 3 处 —— 这些是绕过 token 的临时逃逸。

**为什么现在做**：这是**纯新增、零破坏**的改动（见 §4.2），做完之后 §1.1 的
CMS 迁移才有可用的落点。顺序反了就得迁两次。

---

## 2. 参考系统学到了什么

### 2.1 他们做对的事

**A. 先写决策文档，再改代码。**
`refcms/docs/CMS_PLAN_B_BRAND_UI_EXECUTION_PLAN.md` 27KB，含基线量化
（§2）、设计原则（§3）、token 表（§4）、组件规格（§7）、逐页改动 + 每页验收判据
（§9）、风险表（§15）、明确不做的事（§16）。它先量化现状再动手，
`§2` 直接列出"约 167 个 button / font-bold 约 448 处 / text-xs 约 257 处 /
静态按钮样式约 43 种其中 42 种只出现一次"。

**B. 一个强调色。** `refcms/docs/DESIGN_SYSTEM.md:32`：
「整站只用**一个强调色**(陶土 clay)，克制使用」，节奏靠深墨底区块而不是新颜色。
`§8` 把"霓虹色、高饱和撞色"列为禁止事项。

**C. 后台不复制门户动效。** `CMS_PLAN_B §3.1`：
「门户负责表达艺术感，CMS 负责快速完成工作；品牌感主要来自色彩、字体、留白、
边框和图标，不来自复杂动效」。`§16` 明确"不在 CMS 内复制门户的视差、磁吸、
滚动叙事或大型水彩动画"。

**D. 每个视觉区块只允许一个实心主按钮。** `CMS_PLAN_B §3.3`。这条在
`§9.2`（工作台）落成可验收的判据：「主操作不超过一个实心按钮」。

**E. 验收判据是可测的，不是形容词。** `§9.2`：
「进入首页 3 秒内可识别今日课程、待审核、待续课和本月签到」。
`§9.4`：「列表在手机上不横向溢出；按钮不超过两种视觉层级」。

**F. 拉丁排版设置不套在 CJK 上。** 他们的门户 `refcms/portal.html:65`
`.eyebrow{letter-spacing:.32em;text-transform:uppercase}` 是全局的 ——
这一条其实**我们做得比他们好**，`tenant-template/index.html:66-67` 把宽字距和
大写限定在 `html[lang="en"]`，并写了理由（`:64-65`）。

**G. 报名页把选填字段折叠。** `refcms/register.html:72-75` 的
`.reg-optional summary` 用 `<details>` 收起"艺术偏好"那一组，`+/−` 标记，
44px 触控。必填在上，选填收起。

**H. 收集说明写在采集处。** `refcms/register.html:279` 把
「收集说明 / Collection Notice」直接印在勾选框上方，并链到隐私政策与条款。

**I. 语义色只表达状态。** `CMS_PLAN_B §1.1-3`：
「成功、警告、危险颜色只表达状态，不再用于装饰或区分模块」，
「紫色和粉色不再作为普通按钮色」。

**J. 焦点/触控/reduced-motion 是契约，有脚本守。**
`CMS_PLAN_B §14.1` 列了 11 条自动化检查，包括
「操作按钮不再使用未批准的功能色」「导航使用统一 SVG 图标」。

### 2.2 他们做错的、我们不要抄的

**A. 门户第二层 CSS 把第一层几乎全覆盖了。**
`refcms/portal.html:276-439` 是标着 `v6.9 Living Gallery` 的一整段，
用后出现的规则重写前面 `:53-274` 定义好的 `.btn`、`.tile`、`.course`、
`.form-card`、`.hero-art`。例如 `.hero-art` 在 `:109` 定义为
`border:1px solid var(--line)`，到 `:313` 又变成 `border:0` 加一个
`border-radius:42% 58% 48% 52%/34% 42% 58% 66%` 的有机形状。
两套值同时存在，读代码的人无法判断哪个生效。**这是技术债，不是设计层级。**

**B. `--radius` 从 2px 一路加到 36px，然后又回到 999px。**
`:81` `--radius:2px`，`:278` 新增 `--radius-xs:10px … --radius-xl:36px`，
`:294-295` 又把 `.navcta` 设成 `border-radius:999px`。同一页面 6 档圆角。

**C. 装饰性动效超出他们自己写的规范。**
`DESIGN_SYSTEM.md:121` 说「动画必须慢、轻、自然，不用于炫技」，但
`portal.html:338-342` 有一条 36 秒无限循环的横向滚动字幕
（`animation:manifesto 36s linear infinite`），`:431` 有一个自定义
`.cursor-brush` 跟随鼠标（`mix-blend-mode:multiply`）。
`:311` 的 `@keyframes inkLine` 在 0.7s 延迟后播放。这些都不该抄。

**D. `text-shadow` 当可读性方案。** `:320`
`.hero-art .frame-tag{text-shadow:0 1px 14px rgba(251,249,244,.75)}` ——
文字压在照片上靠阴影撑对比度，而不是给一个实底。他们后来自己在 `:321` 加了
`background:rgba(251,249,244,.68)` 补救，两种手段叠着。

**E. 报名页 `font-bold` 用在 12–14px 的表单标签上。**
`refcms/register.html:145` `class="block text-sm font-semibold reg-muted mb-1"`，
但 tab 按钮 `:119` 是 `text-sm font-bold`。他们自己的
`CMS_PLAN_B §5.3` 写「移除大多数 font-bold，改用 400/500/600」，门户侧没执行。

**F. `✓` 和 `×` 用字符而不是 SVG。**
`refcms/portal.html:193` `.glb-x` 里是 `×`，`register.html:458` 是
`class="text-white text-2xl font-bold"` 的 `×`。他们在 CMS 里换了 SVG
（`CMS_PLAN_B §6.3`），门户和报名页没换。**我们的 `register.html:171` 有同样的
问题**（见 §3.3）。

### 2.3 哪些结论对我们不适用

| 他们的做法 | 为什么我们不能直接抄 |
|---|---|
| 硬编码陶土 `#A65A43` 作为唯一强调色 | 我们有 8 套视觉主题 × 明暗 = 15 个 theme-mode，`accent_color` 由 `palette_gen.py` 按目标对比度反解。任何"唯一强调色"的建议在我们这里必须表述为"每个 theme-mode 内唯一"。 |
| `--cms-*` 一套写死的浅/深色 token（`CMS_PLAN_B §4.1/4.2`） | 他们只有一家店。我们的 CMS token 必须从 `/brand` 下发的 21 个语义 token 生成，且要在 15 个 theme-mode 下全部成立。 |
| 门户加载 Google Fonts（`portal.html:50-52`） | 我们的 `portal-theme.css:85-91` 已经明确决定 CJK 走系统栈（"so mainland visitors never wait on fonts.googleapis.com"）。这是我们更对的地方，不要回退。 |
| Emoji 保留在生日/空状态（`CMS_PLAN_B §6.3`） | 我们的基线是 **CMS 零 emoji**（`Design_System.md:106`，理由是跨平台字形不一致 + 读屏会念描述）。不放松。 |
| 单店的"画室"叙事、创始人个人品牌 | 我们的 `tenant-template` 受 `check_terminology.py` 约束，`画室`/`琴行` 属 `INDUSTRY_BANNED`，必须走 `%VENUE%` / `%WORK%` 占位（`check_terminology.py:44-48`）。 |
| 门户 `section{padding:110px 0}` 之类的裸数值 | 我们已经 token 化（`index.html:134` `padding:var(--space-phi-2xl) 0`）。 |
| "不修改门户与独立报名页视觉"（`CMS_PLAN_B §12.1`） | 他们的门户和报名页是两套独立 `:root`（`refcms/register.html:21-39` vs `portal.html:54-58`），风格明显不同。我们在 `portal-theme.css:1-19` 把这件事修好了并写了理由。**这是我们已经领先的地方。** |

---

## 3. 三个面的现状诊断

### 3.1 门户网站 — 产品主站 `product-home.html`（385 行）

#### D1. 不加载 `ui-tokens.css`，自己手写了一套间距级数

`product-home.html:11-43` 是一段自有 `<style>`，`:33-38`：

```css
--space-1: .5rem;  --space-2: .875rem; --space-3: 1.375rem;
--space-4: 2.25rem; --space-5: 3.625rem; --space-6: 5.875rem;
```

换算：8 / 14 / 22 / 36 / 58 / 94px。而 `ui-tokens.css:13-19` 是
5 / 8 / 13 / 21 / 34 / 55 / 89px。**每一档都差 1–5px**，两套都自称黄金比例。
页面 `<head>` 里没有任何 `<link rel="stylesheet" href="/assets/ui-tokens.css">`
（只有 `:10` 的 `product-home.js`）。

判据：`grep -c 'ui-tokens.css' product-home.html` = 0。

#### D2. 字体栈声明了 `Inter`，但没有 CJK 字族，也没加载 Inter

`:39`：

```css
font-family: Inter, ui-sans-serif, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
```

`Brand_Identity.md:79-83` 规定的产品 UI 字体栈是
`-apple-system, …, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif`。

两个具体问题：
1. 全文没有 `@font-face` 也没有 fonts.googleapis 链接 → `Inter` 在大多数机器上
   直接落空，声明它等于什么都没声明。
2. 栈里**一个 CJK 字族都没有**。而这个页面有 `data-lang="zh"` 的中文版本
   （`:229`、`:231`、`:254` …），中文字形完全交给浏览器兜底。

#### D3. 负字距套在中文标题上

`:82` `h1{font-size:clamp(3rem,7vw,6.6rem); line-height:.96; letter-spacing:-.065em}`。

`:229` 的中文 h1 是「让管理退到幕后，让创作站上台前。」，13 个汉字。
在 6.6rem = 105.6px 下，`-.065em` = 每字之间收 6.86px。CJK 是等宽方块字，
本来没有可压缩的侧边空隙，负字距直接让笔画贴上。`line-height:.96` 在
两行中文下会切掉部分竖笔。

同类问题：`:114` `h2{letter-spacing:-.05em}`、`:147` `.price{letter-spacing:-.05em}`。

#### D4. 表单输入框边框 2.51:1，不满足 WCAG 1.4.11

`:157` `input,textarea,select{border:1px solid rgba(255,255,255,.28)}`，
表单容器是 `:155` `background:rgba(255,255,255,.06)` 叠在
`--family-navy #0e1729` 上。

实测：容器合成色 `#1C2536`；边框合成色 `#5C626E`；
**边框对容器 2.51:1**，边框对输入框自身填充色 `#16233D` **2.55:1**。
1.4.11 要求非文字的 UI 组件边界 ≥ 3:1。

#### D5. 焦点环在浅色区块只有 1.70:1

`:50` `:focus-visible{outline:3px solid var(--family-amber); outline-offset:3px}`。

实测：

| 焦点环落在 | 对比度 | 需要 |
|---|---:|---|
| Family Navy `#0e1729`（hero / support 区） | 9.70:1 | 3:1 ✓ |
| Warm Paper `#f7f5f2`（roles / industries 区） | **1.70:1** | 3:1 ✗ |
| White `#ffffff`（`.role`、`.plan` 卡片） | **1.85:1** | 3:1 ✗ |

页面一半以上的可聚焦元素（5 个 `.role` 链接、3 个 `.plan` 的 CTA、footer
5 个链接）都在浅底上。`Design_System.md:112-116` 把"焦点可见"列为 v7.5.0
已完成的整治项 —— 这个页面是例外。

顺带：`backend/frontend/cms-entry.html:68` 有同类问题，
`outline:3px solid rgba(245,179,53,.55)` 叠在白卡上。

#### D6. `.kicker` 只有 4.52:1，余量 0.02

`:113` `.kicker{color:var(--family-amber-text)}` = `#a16207`，在 Warm Paper
上实测 **4.52:1**。合规，但离 4.5 只有 0.02。任何背景微调就破线。
`Brand_Identity.md:68` 把 `#A16207` 定义为"Accessible amber text on light
surfaces"，这个"accessible"只在 Warm Paper 这一个背景上成立。

#### D7. `--line` 作为唯一分隔线只有 1.34:1

`:27` `--line: rgba(14,23,41,.14)`，合成到 Warm Paper 上是 `#D6D6D6`，
对比 **1.34:1**。`:131` `.flow` 用它当 6 格流程的 1px 网格线
（`gap:1px; background:var(--line)`）—— 那 5 条竖线基本看不见。

`:28` `--line-strong: rgba(14,23,41,.34)` = 合成 `#A8AAAE`，**2.14:1**，
名字叫 strong 但仍不到 3:1。而 `portal-theme.css:43` 的
`--line-strong: #8D7F70` 是被生成器解到 **3.40:1** 的。
**同名 token 在两个文件里含义不同。**

#### D8. 用 magic margin 假装对齐

`:134` `.flow h3{margin:2.8rem 0 .45rem}`、
`:139` `.industry h3{margin:3.5rem 0 .5rem}`、
`:149` `.plan ul{min-height:160px}`。

这些是用固定上边距把标题推到卡片中部、用 `min-height` 把三张卡凑齐高。
中英文长度不同（`:319-323` 五张 industry 卡的中英文行数不一致），一旦换语言
或加一行，对齐就散。

#### D9. 12 栅格表达不了 φ

`:116-127` `.role-grid{grid-template-columns:repeat(12,1fr)}`，
`.role{span 4}`、`.role-owner{span 8}` → 8:4 = **2.0**，不是 1.618。

#### D10. `.section-head > p` 没有 measure 上限，在 900px 断点后铺满

`:112` `.section-head{grid-template-columns:1.618fr 1fr}`，
`:115` `.section-head > p{margin:0;color:var(--ink-soft);line-height:1.7}` ——
没有 `max-width`。

- 桌面（shell 1180px，gap 36px）：次列 ≈ 437px，16px 下约 55 字符，正常。
- `:172` `@media (max-width:900px){.section-head{grid-template-columns:1fr}}`
  之后：整段拉到 shell 全宽 = `min(1180px, 100% - 40px)`，在 900px 视口下是
  860px，16px 下约 **100+ 字符/行**。

`ui-tokens.css:12` 有 `--ui-reading-measure: 55ch`，这个页面没用。

### 3.2 门户网站 — 租户模板 `tenant-template/index.html`（1663 行）

这个文件整体状态**明显好于** `product-home.html`：加载了三个 token 文件
（`:52-54`）、用 `var(--golden-columns)`（`:92`、`:147`、`:158`、`:215`）、
用 `var(--space-phi-*)`（`:63`、`:92`、`:134`）、CJK 排版设置有语言作用域
（`:64-67`）、画廊 tile 是真 `<button>` 所以灯箱键盘可达（`:196-198`）。
下面是剩下的问题。

#### D11. 【严重】`.result-card` 在 7 个 dark theme-mode 下文字隐形

见 §1.3。证据 `:265-266`、`:538`。实测 1.06:1 / 1.21:1 / 1.06:1。

同类但较轻：`:442` `<p class="eyebrow" style="color:#9d9484">` 落在
`.parent{background:var(--ink)}` 上，浅色 5.52:1、**深色 2.63:1**。

反向的一个：`:538` `border-color:#4a463c` 在深色 `--ink` 上 8.26:1 正常，
在**浅色** `--ink` 上 1.76:1 —— 按钮描边看不见。同一行的两个硬编码值
一个在浅色坏、一个在深色坏。

#### D12. `.surface-status` 是一条硬编码的浅色带，压在任何主题上

`:263`：

```css
.surface-status .note{ ... background:#FDF3D5; color:#6b4f00; ... }
```

文字对底 6.91:1（本身没问题），但这是一整条浅黄色带钉在页面顶部
（`:262` `position:fixed; top:74px`）。在 dark 主题下页面是 `#15120D`，
这条带子对页面 16.86:1 —— 一块刺眼的浅色异物。而且它就是"降级提示"，
本该用 `--warning` / `--warning-soft`，token 里有。

#### D13. 报名/预约表单的 label 是 12px，且英文版被转成大写宽字距

`:242-243`：

```css
.fld label{font-size:12px; ...}
html[lang="en"] .fld label{letter-spacing:.14em; text-transform:uppercase; color:var(--muted); font-weight:400}
```

三个叠加的可读性成本：12px + 全大写 + 0.14em 字距 + 从 `--ink2`(8.93:1)
降到 `--muted`(5.14:1)。全大写取消了词形轮廓，是逐字母识读；宽字距进一步
削弱词内聚合。

参考系统的表单标签是 `text-sm font-semibold` = 14px/600
（`refcms/register.html:145`），他们的 CMS 规范是 13px/500
（`CMS_PLAN_B §7.7`）。我们是三者里最小的。

#### D14. `--bg2` 区块上的语义色低于 AA（潜在）

见 §1.4。`.gallery`（`:187`）、`#courses`（`:416`）、`#faq`（`:457`）、
`footer`（`:269`）都是 `--bg2`。当前门户没有把 success/warning/danger 直接放在
这些区块里，所以是**潜在**而非既有失效。但生成器没有这条断言，下一个人加一个
badge 就会踩到。

#### D15. `.course p{min-height:44px}` 借用了触控尺寸做排版对齐

`:182`。44px 是触控目标的最小值（`--tap-min`），用在一段非交互文字上做等高，
语义错位，且和 `product-home.html` 的 `min-height:160px` 是同一类 magic number。

### 3.3 报名 `tenant-template/register.html`（535 行）

同样，这个文件基础很好：全部 21 个主题 token 都映射（`:364-386`）、
字段级错误 + `aria-invalid` + `aria-describedby` + 焦点落到第一个错误字段
（`:299-320`）、蜜罐（`:156`）、隐私说明用 `<dialog>` 且带版本号（`:195-207`）、
切语言时保留已填内容（`:327-331`）。下面是剩下的问题。

#### D16. 表单卡宽 ~695px，输入框跟着拉满

`:50` `main{width:min(1180px,100%); grid-template-columns:var(--golden-columns-reverse); gap:var(--space-phi-xl)}`
→ 卡片占 1.618fr。(1180 − 55) × 0.618 ≈ **695px**。
`:64` `input,textarea,select{width:100%}` → 一个手机号输入框 695px 宽。

对照：参考系统是 `max-w-lg` = 512px（`refcms/register.html:133`），
他们的门户表单卡是 `max-width:560px`（`refcms/portal.html:228`），
我们自己的门户 `.form-card` 也是 `max-width:560px`（`index.html:240`）。
**只有独立报名页没有这个上限。**

#### D17. 姓/名用了 φ 分栏，违反自家写下的规则

`:148-151` `.row{grid-template-columns:var(--golden-columns-reverse)}`
用在「姓氏 / 名字」上 → 38.2% / 61.8%。

`docs/Design_System.md:48-50` 写得很明确：

> "Use the ratio only when one region is genuinely primary. Tables, repeated
> KPI cards, **mobile forms and peer controls stay equal-width** when equal
> importance is the clearer interaction model."

姓和名是 peer 字段。这是黄金比例被当装饰用的一处。

#### D18. 只在提交时校验

`:449` 的 `submit` 监听里调 `failFirst(checks)`（`:457-467`）。全文没有
`blur` 监听。`ui-ux-pro-max` 的 `ux` 域 Forms/Inline Validation 条目：
Do「validate on blur for most fields」，Don't「validate only on submit」。

具体成本：一个家长填完 8 个字段点提交，才被告知第 2 个字段格式不对，
然后焦点跳回去。blur 校验能把这个反馈提前 6 个字段。

#### D19. 没有渐进披露，且最高摩擦的字段紧贴提交按钮

字段顺序（`:148-168`）：
姓氏 → 名字\* → 手机\* → 邮箱 → 自定义字段 → 补充说明 → 隐私同意\* →
**作品公开同意（选填）** → 提交。

`:162` 勾上「作品公开同意」会展开 `:163-166` 两个**新的必填**字段
（授权人姓名、与学员关系），就在提交按钮上方。转化视角：一个已经准备提交的人，
在最后一步被追加两个必填项。

参考系统把选填组收进 `<details>`（`refcms/register.html:72-75`），
必填在上、选填折叠。

#### D20. 成功标记是字符 `✓` 而不是内联 SVG

`:171` `<div class="mark" aria-hidden="true">✓</div>`。
`aria-hidden` 处理了读屏，但 U+2713 的字形依赖字体，且这与
`Design_System.md:106`「No emoji as icons ... Inline SVG Icon component」
的精神不一致。参考系统在同一位置用了 SVG（`refcms/register.html:319`）。

#### D21. `.intro` 是 sticky，但内容比表单短很多

`:52` `.intro{position:sticky; top:104px}`。左栏只有 eyebrow + h1 + 一段
lead，表单栏长得多。滚动时左栏会先跟随、然后停住，产生一次视觉"脱钩"。

### 3.4 CMS 管理 `legacy-root/src/cms-app.jsx`（5055 行）+ `legacy-root/index.html`（368 行）

#### D22. 我们的 CMS 基线，几乎逐项等于参考系统 2026-07-14 记录的问题状态

这是本次调研最有价值的一条。`CMS_PLAN_B §2` 是他们改造前的量化基线，
我用同样的口径量了我们的：

| 指标 | 他们（改造前） | 我们（现在） |
|---|---:|---:|
| `<button>` | ~167 | **165** |
| `font-bold` | ~448 | **394** |
| `font-semibold` | — | **0** |
| `text-xs` | ~257 | **248** |
| `text-sm` | ~232 | **231** |
| `rounded-xl` | 233 | **242** |
| 混用色系 | indigo/green/emerald/sky/purple/teal/pink/amber/orange/red | gray 659、indigo 329、red 106、amber 68、green 47、emerald 35、purple 34、pink 30、blue 26、orange 21、teal 4、rose 3（**11 个色系**） |

**`CMS_PLAN_B` 那份 27KB 的文档，本质上就是我们 CMS 现状的诊断书。**
这不是巧合 —— 两边同源。差别是他们已经做完了那 5 个 Phase，我们没做。

#### D23. indigo 不是设计选择，是 `--tenant-primary` 的载体

`legacy-root/index.html:323-332` 用类名字符串匹配来注入租户色：

```css
[class*="bg-indigo-600"], [class*="bg-indigo-700"], .tab-active { background-color:var(--tenant-primary) !important; }
[class*="bg-indigo-50"],  [class*="bg-indigo-100"] { background-color:var(--tenant-primary-soft) !important; }
[class*="text-indigo-400"] … [class*="text-indigo-800"] { color:var(--tenant-primary) !important; }
[class*="border-indigo-"] { border-color:var(--tenant-primary-border) !important; }
```

而 `--tenant-primary-soft` 的计算方式是 `:53`
`root.style.setProperty('--tenant-primary-soft', \`${primary}14\`)` ——
**把主色拼上 `14` 当 8% alpha**。于是"浅底 + 同色文字"这一对从来没被解过对比度。

实测（底色 `#f1f5f9`）：

| 主题 accent | soft（8%）合成 | accent on soft | 结论 |
|---|---|---:|---|
| vintage-press `#835D33` | `#E8E9E9` | 4.82:1 | 侥幸通过 |
| harbour-calm `#2E6892` | `#E2EAF1` | 4.92:1 | 通过 |
| studio-ink `#2C2A29` | `#E2E5E9` | 11.30:1 | 通过 |
| **arcade-lime `#A8D93A`** | `#EBF3EA` | **1.47:1** | 失效 |

`arcade-lime` 是 dark-only 主题（`Design_System.md:67`），它的 accent 是为
深底解出来的。放进 CMS 的固定浅底 + 8% 拼色逻辑里必然崩。

另一个后果：indigo 的语义被抽空了。329 处 indigo 里既有主按钮、也有选中态、
也有信息底 —— 全部被同一个 `!important` 规则染成同一个色。

#### D24. `body` 背景写死冷灰，租户主题进不来

`legacy-root/index.html:297` `body{background:#f1f5f9 !important}`，
外加 `:361` `<body class="bg-gray-100 text-gray-800">`。
`#f1f5f9` 是 Tailwind slate-100。品牌画布是 Warm Paper `#f7f5f2`。
租户的 `background_color` 虽然被写进了 `--brand-paper`（`:56` themeVars），
但 CMS 里没有任何规则消费 `--brand-paper`。

#### D25. 21 个主题 token 只应用 10 个

见 §1.2。`legacy-root/index.html:56` 的 `themeVars` 字面量：

```
background_color, panel_color, text_color, muted_text_color, border_color,
accent_text_color, secondary_text_color, success_color, warning_color, danger_color
```

缺的 9 个里，`focus_ring_color`、`disabled_surface_color`、
`disabled_text_color`、`border_strong_color` 正是 `Design_System.md:111-127`
列为 v7.5.0 整治成果的四项。

#### D26. 两套互不相干的深色模式

`legacy-root/index.html:151-238` 是 88 行 `@media (prefers-color-scheme: dark)`
的 Tailwind 类名重映射，由**访问者操作系统**触发。
租户自己选的 theme-mode（15 个里的一个）由 `root.dataset.brandScheme`（`:59`）
标记，跟它完全无关。

一个 `vintage-press light` 的租户，员工在深色系统上打开 CMS，看到的是
`#0e1016` 冷黑，不是 vintage-press dark 的 `#15120D` 暖黑。

**给这段深色映射一句公道话**：它本身调得不错。实测
`.text-gray-400/500 → #8b93a5` 在 `.bg-white → #1a1d27` 上 5.46:1，
`.text-amber-* → #efc471` 在 `.bg-amber-50 → #382e18` 上 8.14:1，
`.text-green-*` 8.74:1，`.text-red-*` 7.78:1。问题不是质量，是它是第 16 套主题。

#### D27. 四种（含 studio-admin 五种）圆角系统

| 文件 | 控件 | 卡片 |
|---|---|---|
| `portal-theme.css:81-82` | 2px | 4px |
| `ui-tokens.css:42-43` | 8px | 13px |
| `brand-system.css:31-32` | 10px | 18px |
| `legacy-root/index.html:294-295` | 8px | 16px |
| `backend/frontend/studio-admin.html:77-79` | 8px | 12 / 16px |

一个家长的路径：门户（2/4px）→ 报名（2/4px）—— 一致，好。
一个员工的路径：CMS（8/16px）→ Studio Admin（8/12/16px）—— 接近。
但两条路径之间差了 4 倍，而它们是同一个品牌。

#### D28. PIN 锁屏的焦点环和状态点是硬编码 indigo

`legacy-root/index.html:257-261`：

```css
.pin-dot { background:#e5e7eb; }
.pin-dot.on { background:#6366f1; }
.pin-input { border:2px solid #e5e7eb; }
.pin-input:focus { border-color:#6366f1; box-shadow:0 0 0 3px rgba(99,102,241,.15); }
```

实测：`.pin-input` 静止态边框 `#e5e7eb` 对白底 **1.24:1**（1.4.11 需 3:1，失效）；
`.pin-dot.on` 对轨道 3.61:1（通过）；focus 边框 4.47:1（通过）。
但三个值都是 indigo-500/gray-200 字面量，不是 `--focus-ring`。

另：`:12` `<meta name="theme-color" content="#312e81">` 是 indigo-900；
`:44-45` 租户色兜底默认值是 `'#312e81'` 和 `'#6366f1'`。
品牌是 Family Navy `#0E1729`。

#### D29. disabled 靠 opacity

`legacy-root/index.html:320` `button:disabled{opacity:.55}`。

`Design_System.md:117-118`：「Disabled states: disabled controls use
`disabled_surface_color` / `disabled_text_color` **rather than opacity alone**」。

实测：gray-800 文字在 0.55 不透明度下合成 `#848991`，对白底 **3.52:1**；
白字在 indigo-600 上 0.55 → `#B0ACF3`，对底 **3.01:1**。数字上不算灾难，
但这是明文违反自家规范，而且 opacity 会连图标、边框、阴影一起变淡，
无法表达"可读但不可用"。

#### D30. 所有 button 和 a 都 hover 上浮，包括表格行

`legacy-root/index.html:319`：

```css
button:hover, a:hover, [role="button"]:hover { transform:translateY(-1px); box-shadow:var(--shadow-sm); }
```

参考系统的规范（`refcms/docs/CMS_DESIGN_SYSTEM.md:49`）：
「Hover：控件上浮 1px，可交互卡片上浮 2px；**导航和表格行不位移**，
触控端使用按压反馈」。

我们对 5055 行里的每个 `<a>` 都上浮，包括学员列表行、日志分页、侧边导航。
（`:348` 在 reduced-motion 下关掉了，这点是对的。）

#### D31. 40px 触控目标 38 处

`min-h-[40px]` **38 处** vs `min-h-[44px]` **42 处**。
`Design_System.md:117` 说的是 44px 最小、CMS 用 `min-h-[44px]`。
40px 出现在紧凑工具条按钮上（如 `cms-app.jsx:3378-3381` 工作台快捷操作、
`:3378` 那一组是 `text-xs font-bold min-h-[44px]`，但另有 38 处是 40px）。

参考系统的 `CMS_PLAN_B §11.1` 允许"紧凑工具栏最低 36px 且保留足够间距"——
可以有例外，但要写明是哪些、为什么，而不是散落。

#### D32. 5 个纯图标按钮，0 个有 `aria-label`

`grep -cE '<button[^>]*>\s*<Icon' cms-app.jsx` = 5，其中含 `aria-label` = 0。
全文 `aria-label` 24 处 / 165 个 button。

`Icon` 组件本身是对的（`cms-app.jsx:529-539`）：内联 SVG、`aria-hidden="true"`、
`focusable="false"`、`currentColor`、`strokeWidth 1.6`、49 个图标。
正因为图标对读屏隐藏，纯图标按钮就成了无名按钮。

#### D33. 没有任何基础组件，165 个按钮各写各的

`cms-app.jsx` 里 `^(const|function) [A-Z]` 的定义共 14 个：
`TenantBrandLogo`、`PINScreen`、`BarChart`、`EmptyState`、`BalBadge`、
`Toast`、`ConfirmDialog`、`StudentPicker`、`PhotoAvatar`、`Icon`、
`PhotoUploader`、`MaintSection`、`LoginScreen`、`App`。

**没有 `Button`、`IconButton`、`Badge`、`FormField`、`Tabs`、
`SegmentedControl`、`Accordion`。** 参考系统的 `CMS_PLAN_B §7` 正是先建这 7 个。

#### D34. 语义色用了 Tailwind 默认档位，多个不足 4.5:1

实测（白底）：

| 类 | 值 | 对白 | 结论 |
|---|---|---:|---|
| `text-green-600` | `#16a34a` | 3.30:1 | ✗ |
| `text-emerald-600` | `#059669` | 3.77:1 | ✗ |
| `text-amber-600` | `#d97706` | 3.19:1 | ✗ |
| `text-orange-600` | `#ea580c` | 3.56:1 | ✗ |
| `text-teal-600` | `#0d9488` | 3.74:1 | ✗ |
| `text-red-600` | `#dc2626` | 4.83:1 | ✓ |
| `text-amber-700` | `#b45309` | 5.02:1 | ✓ |
| `text-purple-600` | `#9333ea` | 5.38:1 | ✓ |

对照生成器解出来的 vintage-press light：success `#2F7951` 5.00:1、
warning `#8D6426` 5.04:1、danger `#B6483A` 5.01:1（对 `--bg`），
三个都在 5.0 附近而不是 3.2–3.8。**这是"解过"和"挑过"的差别。**

#### D35. 主按钮色不是品牌色

`bg-indigo-600` `#4f46e5`，白字 6.29:1；`bg-indigo-700` 7.90:1。
Family Navy `#0e1729` 白字 **17.90:1**。
77 处主按钮表面（indigo-600 34 + indigo-700 33 + indigo-800 10）。

#### D36. 边框全部不足 1.4.11

`border-gray-100` 1.10:1（62 处）、`border-gray-200` 1.24:1（57 处）、
`border-gray-300` 1.47:1（60 处），对白底。共 179 处。
其中 `border-gray-300` 常用在输入框上（`legacy-root/index.html:305`
`input{border-color:var(--line) !important}` 且 `:290` `--line:#e2e8f0` = 1.24:1）。

#### D37. 值得保留的部分（不要在改造中弄坏）

- `Icon` 组件与 49 个图标映射（`cms-app.jsx:479-539`）——**零 emoji 已达成**。
- 工作台 KPI 卡点击即跳到**已筛选**的列表：`cms-app.jsx:3386-3391`，
  例如「全部剩余课时」→ `setSortBy('bal-desc'); setFilterBy('active'); setTab('students')`。
  一次点击到目标状态，路径长度 1。这是好设计，参考系统没有。
- 待办卡直达筛选：`:3461` `setFilterBy('zero')`、`:3471` `'low'`、
  `:3481` `'tag-risk'`。
- `⌘K` 全局搜索（`:1181`），且 `Escape` 关闭（`:3027`）。
- 移动端安全区处理完整（`legacy-root/index.html:266-273`）。
- `prefers-reduced-motion` 有作用域说明，且刻意保留了 `.sp` spinner
  （`:340-350`，理由写在注释里："it conveys busy"）。
- 深色映射的对比度调得不错（见 D26）。
- 打印样式（`:353-358`）。

---

## 4. 设计系统层的统一方案

### 4.1 间距级数：不动

`ui-tokens.css:13-19` 的 5 / 8 / 13 / 21 / 34 / 55 / 89 是 Fibonacci，
相邻比值收敛到 φ（21/13 = 1.615、34/21 = 1.619、55/34 = 1.618、89/55 = 1.618）。
已经在 `portal-theme.css:102-107`、`brand-system.css:26-30` 建立了别名，
门户和报名页在用。**保持原样。**

唯一要做的是**让 `product-home.html` 用它**（D1）。对应关系：

| 现有自有 token | 值 | 替换为 | 值 | 差 |
|---|---:|---|---:|---:|
| `--space-1` | 8px | `--ui-space-2` | 8px | 0 |
| `--space-2` | 14px | `--ui-space-3` | 13px | −1 |
| `--space-3` | 22px | `--ui-space-4` | 21px | −1 |
| `--space-4` | 36px | `--ui-space-5` | 34px | −2 |
| `--space-5` | 58px | `--ui-space-6` | 55px | −3 |
| `--space-6` | 94px | `--ui-space-7` | 89px | −5 |

最大位移 5px，在 89px 的级距上是 5.6%。视觉上不可察，但换来一个来源。

### 4.2 字号级数：新增三档，φ 与 √φ 双层

现有 `--ui-type-*`：`13 / 16 / 21 / 34 / 55`。
问题见 D3/§1.5：小端不是 φ，21 与 34 之间断档，缺 11–12。

**提案（纯新增，现有五个值一个都不改）：**

| Token | 值 | 用途 | 相邻比 | 与前隔一档之比 |
|---|---:|---|---:|---:|
| `--ui-type-2xs` | **11px** | 状态 badge、eyebrow（仅大写拉丁） | — | — |
| `--ui-type-xs` | 13px | caption、表格次要列、时间 | 1.18 | — |
| `--ui-type-sm` | 16px | 正文、输入框、按钮 | 1.23 | 1.45 |
| `--ui-type-md` | 21px | 区块标题 | 1.31 | **1.62** |
| `--ui-type-ml` | **26px** | 卡片大标题、KPI 数值 | 1.24 | **1.63** |
| `--ui-type-lg` | 34px | 页面标题 | 1.31 | **1.62** |
| `--ui-type-xl2` | **43px** | 次级 display | 1.26 | **1.65** |
| `--ui-type-xl` | 55px | hero display | 1.28 | **1.62** |

设计逻辑：**相邻是 √φ ≈ 1.272，隔一档是 φ ≈ 1.618。**
- 16 → 26 = 1.625
- 21 → 34 = 1.619
- 26 → 43 = 1.654
- 34 → 55 = 1.618

好处：需要"明显跳一级"时用隔档（φ），需要"细分层级"时用相邻（√φ）。
CMS 的 394 个 `font-bold` 之所以存在，就是因为只有 φ 一层可用、
细分只能靠字重。

**字重同时补齐**：现在 CMS 只有 400（29 处 `font-normal`）+ 700（394 处），
`font-medium` 10 处、`font-semibold` 0 处。
参考 `CMS_PLAN_B §5.2` 与 `Brand_Identity.md:85-87`，定四档：

| 层级 | 字号 / 行高 | 字重 |
|---|---|---:|
| Page title | 34 / 41px | 600 |
| Section title | 21 / 29px | 600 |
| Card title | 16 / 24px | 600 |
| Body | 16 / 27px（1.7） | 400 |
| Button | 16 / 21px | 600 |
| Label | 13 / 18px | 500 |
| Caption | 13 / 21px | 400 |
| Micro badge | 11 / 16px | 600 |
| Metric | 26–34px | 600 |

`text-[10px]`（11 处）与 `text-[9px]`（3 处）全部上调到 11px。

### 4.3 measure：拆成中英两个 token

现在只有 `--ui-reading-measure: 55ch`（`ui-tokens.css:12`）。
`ch` 是当前字体 "0" 的宽度。

- **拉丁**：16px 无衬线下 1ch ≈ 8.2px → 55ch ≈ 451px。因为小写字母平均比 "0" 窄，
  实际约 75–80 字符/行，**已经在 65–75 的上界之外**。
- **CJK**：汉字是全宽方块，16px 下 1 字 = 16px → 451px 只有约 **28 字/行**，
  低于 30–40 字的常规区间。

一个 token 服务不了两种文字系统。提案：

```css
:root {
  --ui-measure-latin: 66ch;   /* ≈ 68–72 拉丁字符 */
  --ui-measure-cjk: 34em;     /* = 34 汉字 @16px = 544px */
  --ui-reading-measure: var(--ui-measure-latin);  /* 保留旧名，默认拉丁 */
}
html[lang^="zh"] { --ui-reading-measure: var(--ui-measure-cjk); }
```

旧名保留 → `portal-theme.css:23`、`brand-system.css:23` 的
`--brand-reading-measure` 引用不用改。这与 `index.html:64-67` 已经建立的
"拉丁排版设置按 `html[lang]` 作用域"模式一致。

### 4.4 栅格：用 13 列表达 φ

12 无法整分成 1.618:1。13 可以：**8 + 5 = 13**，8/5 = 1.6，
是 φ 的 Fibonacci 逼近（误差 1.1%）。

```css
--ui-grid-phi: repeat(13, minmax(0, 1fr));   /* 主 span 8 / 次 span 5 */
```

`product-home.html:116-127` 的 `.role-grid` 从 12 改 13：
`.role-owner{span 8}`、`.role{span 5}` → 第一行 8+5 = 13。
剩下 4 张卡走 `span 5` / 自动换行，或用等宽（它们是 peer，等宽更诚实 ——
见 `Design_System.md:48-50`）。

**φ 的使用边界（写进规范）**：
- 用：hero 文案 vs 视觉、表单 vs 说明、dashboard 主区 vs KPI 列。
- 不用：表格列、重复 KPI 卡、姓/名这类 peer 字段、移动端（< 900px 全部单列）。
  这条已经写在 `Design_System.md:48-51`，D17 是违反它的实例。

### 4.5 与现有 token 文件的对接

改动只发生在两个地方，不新增文件：

| 文件 | 改什么 | 破坏性 |
|---|---|---|
| `ui-tokens.css` | 新增 `--ui-type-2xs/ml/xl2`、`--ui-measure-latin/cjk`、`--ui-grid-phi`；`--ui-reading-measure` 变成 `var()` 引用 | 无（现有 5 个 type 值与 7 个 space 值不动） |
| `docs/design/palette_gen.py` | `sem[role]` 的 `bg` → `worst`；`CHECKS` 加 3 条 `semantic / alt` | 15 个主题的 45 个语义色 hex 位移（见 §1.4 表），需重跑 `--emit-presets` 并跑 `migrate_visual_themes.py` |
| `portal-theme.css` / `brand-system.css` | 只需别名，不需新值 | 无 |

**明确回答"改生成器还是改应用层"**：
- 语义色对 `--bg2`（§1.4）→ **改生成器**。它是 15 个主题的唯一来源，
  应用层躲不干净。
- 字号 / measure / 栅格 → **改 `ui-tokens.css`**，与生成器无关（生成器只产颜色）。
- 门户 `.result-card` 的硬编码（§1.3）→ **只改应用层**，一行，不动生成器。
- CMS 的 indigo 劫持（D23）→ **只改应用层**，但要改的是消费方式，不是值。

---

## 5. 门户网站升级方案

### 5.1 产品主站 `product-home.html`

#### P0-A 接入 token，删掉自有间距级数

`<head>` 加 `<link rel="stylesheet" href="/assets/ui-tokens.css">`，
删掉 `:33-38` 的 `--space-1..6`，按 §4.1 的对应表替换 42 处引用。

验收：`grep -c 'ui-tokens.css' product-home.html` ≥ 1；
`grep -c '\-\-space-[1-6]' product-home.html` = 0；
`test_product_home_brand.py` 继续通过。

#### P0-B 焦点环换成 amber-text，并给深色区块单独覆写

现在（`:50`）：

```css
:focus-visible { outline: 3px solid var(--family-amber); }
```

提案：

```css
:focus-visible { outline: 3px solid var(--family-amber-text); outline-offset: 3px; }
.hero :focus-visible, .support :focus-visible, .role-owner:focus-visible,
.industry:first-child :focus-visible { outline-color: var(--family-amber); }
```

实测结果：

| 焦点环落点 | 现在 | 改后 | 需要 |
|---|---:|---:|---|
| Warm Paper | 1.70 ✗ | **4.52** ✓ | 3:1 |
| White 卡片 | 1.85 ✗ | **4.92** ✓ | 3:1 |
| Family Navy | 9.70 ✓ | 9.70 ✓ | 3:1 |

这个改法我在本轮的 `customer-resources` 页面上已经**实测验证过**：
键盘 Tab 后 `getComputedStyle` 返回 `rgb(161, 98, 7) solid 3px offset 3px`，
`:focus-visible` 匹配为 `true`。

同步修 `backend/frontend/cms-entry.html:68`
（`rgba(245,179,53,.55)` → `var(--pwe-family-amber-text)`）。

#### P0-C 表单输入框边框提到 3:1

`:157` `border:1px solid rgba(255,255,255,.28)`（2.51:1）
→ `rgba(255,255,255,.42)`。

实测：合成 `#7A7F89`，对容器 `#1C2536` **3.72:1**，对填充 `#16233D` 3.78:1。
两者都过 3:1，且不至于亮得像激活态（激活态用 amber 边框区分）。

#### P1-A 中文标题去掉负字距和 sub-1.0 行高

```css
html[lang="en"] h1 { letter-spacing: -.065em; line-height: .96; }
html[lang="zh"] h1 { letter-spacing: 0;       line-height: 1.15; }
```

同样处理 `:114` `h2{-.05em}`、`:147` `.price{-.05em}`。
这与 `tenant-template/index.html:64-67` 已有的语言作用域模式一致。

验收：中文 h1 在 375 / 768 / 1440px 下换行不切笔画；
`letter-spacing` 在 `html[lang="zh"]` 下计算值为 `normal`。

#### P1-B 字体栈补 CJK，删掉 Inter

`:39` 改为 `Brand_Identity.md:79-83` 的原文栈。
若确实要 Inter，就真的加载它（本地 WOFF2 子集，不引 CDN ——
`portal-theme.css:85-86` 已经为此定过调）；否则去掉。

#### P1-C `--line` / `--line-strong` 与 portal-theme 对齐语义

现在两个文件里同名不同义（D7）。提案：

```css
--line:        rgba(14,23,41,.14);  /* 装饰分隔，1.34:1，不承担组件边界 */
--line-strong: #64748b;             /* 交互边界，slate-500，对 paper 4.37:1 */
```

`.flow`（`:131`）的网格线从 `--line` 换成 `#cbd5e1`（1.48:1 → 仍是装饰，
但可见）；同时给每格加 `.number` 的 amber-text 序号作为 ≥3:1 的识别元素。

> 注：`#64748b` 对 Warm Paper 实测 **4.37:1**，对白卡 4.76:1。
> 作为边界（需 3:1）两边都过；但**不能拿它当浅底上的小字**，
> 那需要 4.5:1 而它在 paper 上差 0.13。这个陷阱我在本轮 CSS 里
> 已经写进注释（`customer-resources.css:26-27`）。

#### P1-D `.section-head > p` 加 measure

```css
.section-head > p { max-width: var(--ui-reading-measure); }
```

配 §4.3 的中英双 token，中文段落上限 34 字/行，英文 66ch。
消除 900px 断点后 100+ 字符/行的问题（D10）。

#### P2-A 用 grid 代替 magic margin

`.flow article`、`.industry`、`.plan` 改成
`display:grid; grid-template-rows: auto 1fr auto`，删掉
`:134` `margin:2.8rem`、`:139` `margin:3.5rem`、`:149` `min-height:160px`。
中英文长度差异不再影响对齐。

#### P2-B `.role-grid` 换 13 列（§4.4）

### 5.2 租户公开门户 `tenant-template/index.html`

> `tenants/<slug>/` 是生成产物，不改。所有改动落在模板。

#### P0-D 【最高优先】`.result-card` 一行修好

`:265-266`：

```css
/* before */ .result-card{ background:var(--ink); color:#EFE9DD }
             .result-card .big{ color:#EAD9C7 }
/* after  */ .result-card{ background:var(--ink); color:var(--bg) }
             .result-card .big{ color:var(--clay) }
```

`:538` 的内联 `style="border-color:#4a463c;color:#EFE9DD"` →
`style="border-color:color-mix(in srgb,var(--bg) 30%,var(--ink));color:var(--bg)"`。

`:442` 的 `style="color:#9d9484"` → `color:color-mix(in srgb,var(--bg) 66%,var(--ink))`
（这是 `:223` `.p-card .l p` 已经在用的写法，同一区块内保持一致）。

**为什么用 `var(--bg)` 而不是白色**：`.parent`（`:214`）已经建立了
`background:var(--ink); color:var(--bg)` 的反转模式，在 15 个 theme-mode 下
都成立，因为 ink/bg 是生成器解出来的一对。硬编码任何一端都会在另一半 mode 下坏。

验收判据（可自动化）：对 15 个 theme-mode 各自计算
`.result-card` 文字 / 背景，全部 ≥ 4.5:1。目前 7 个 dark mode 是 1.06:1。

#### P0-E `.surface-status` 用 warning token

`:263`：

```css
/* before */ background:#FDF3D5; color:#6b4f00;
/* after  */ background:color-mix(in srgb, var(--warning) 12%, var(--panel));
             color:var(--ink);
             border-left:3px solid var(--warning);
```

这与 `brand-system.css:98-108` 已有的 `.brand-status` 模式相同
（左侧 3px 语义色 + 12% 混色底 + `--brand-ink` 文字）。复用它更好：
把 `.surface-status .note` 直接改成 `class="brand-status" data-tone="warning"`。

#### P1-E 表单 label 提到 13px/500，去掉英文全大写

`:242-243`：

```css
/* before */ .fld label{font-size:12px}
             html[lang="en"] .fld label{letter-spacing:.14em;text-transform:uppercase;color:var(--muted);font-weight:400}
/* after  */ .fld label{font-size:var(--ui-type-xs,13px);font-weight:500;color:var(--ink2)}
             html[lang="en"] .fld label{letter-spacing:.02em}
```

保留 eyebrow 的大写宽字距（那是装饰性标签，不是输入标签），
但表单 label 不做全大写。理由：全大写取消词形轮廓，把词识别降级为字母识读；
表单是"填完就走"的场景，识别成本最不该加在这里。
`--ink2` 对 `--panel` 实测 10.05:1（原 `--muted` 是 5.78:1）。

#### P1-F `.course p` 的 `min-height:44px` 换 grid

`:182`。同 P2-A。

#### P2-C 参考系统的质感手法，哪些可以借

参考系统靠**真实摄影 + 极低透明度纹理**建立质感，不靠渐变：

- `refcms/site/` 有 62 个资产，每张都有 `-640.webp` / `-960.webp` / `.jpg`
  三档（如 `g1-640.webp`、`g1-960.webp`、`g1.jpg`），
  规范写在 `DESIGN_SYSTEM.md:91`：「长边 ≤ 1500px、JPEG q82–88、每张数百 KB 内」。
- `watercolour-texture-v1.webp` 用法（`portal.html:282`）：
  `linear-gradient(rgba(244,240,232,.94), rgba(244,240,232,.94)), url(...)`
  —— 94% 不透明的同色遮罩压在纹理上，只留 6% 的纸感。
- 统一暖调滤镜（`:153`）：`filter:saturate(.9) brightness(1.02) contrast(.97) sepia(.05)`，
  让不同来源的照片看起来出自同一空间。
- 人像 4:5 竖构图、作品墙 1:1 `cover`（`DESIGN_SYSTEM.md:92`）。

**可以借**：三档响应式 webp、统一滤镜、固定长宽比。
`tenant-template/index.html:118-121`、`:148`、`:159-162` 已经用了
`aspect-ratio:4/5` 和 1:1，方向一致。

**不能照搬**：我们的纹理必须由租户主题着色（`color-mix` 混 `--bg`），
不能像他们那样固定 `rgba(244,240,232,.94)` —— 那在 7 个 dark mode 下会
盖出一块浅色。且纹理图本身要中性灰度，靠混色上色。

**不要借**：36s 循环字幕（`:338-342`）、`.cursor-brush`（`:431`）、
有机形状 `border-radius`（`:313`）。理由见 §2.2。

---

## 6. CMS 管理升级方案

目标不是"变好看"，是**降低每天重复几十次的操作的认知成本**。
方向沿用 `CMS_PLAN_B §3.1`：品牌感来自色彩、字体、留白、边框、图标，
不来自动效；高频表单、表格、金额、日期优先保证扫描效率。

### 6.1 阶段一：建立组件与 token 桥，不做全局替换

这是 `CMS_PLAN_B §12.3` 的策略，值得照抄：
「先建立组件和变量，不先全局替换颜色；逐页面迁移，每完成一页立即构建和
运行契约检查；不进行大规模字符串替换」。

#### C0-A 把 21 个主题 token 全部接进来

`legacy-root/index.html:56` 的 `themeVars` 从 10 项补到 21 项，
直接抄 `tenant-template/register.html:364-386` 的 `THEME_TOKENS` 字面量
（同一份声明式映射，两个文件将来可以提到 `ui-common.js` 共享）。

#### C0-B 删掉 `body{background:#f1f5f9 !important}`

`legacy-root/index.html:297` → `background:var(--brand-paper)`。
`:361` `<body class="bg-gray-100 text-gray-800">` 的两个类去掉。

#### C0-C 建一层 CMS 语义变量，桥接到租户主题

新增 `--cms-*`，全部从 `--brand-*` / 主题 token 派生，**不含任何字面 hex**：

```css
:root {
  --cms-page:          var(--brand-paper);
  --cms-surface:       var(--brand-paper-raised);
  --cms-surface-soft:  var(--bg2, color-mix(in srgb, var(--brand-paper) 92%, var(--brand-ink)));
  --cms-ink:           var(--brand-ink);
  --cms-ink-soft:      var(--ink2, var(--brand-ink-soft));
  --cms-ink-muted:     var(--brand-ink-soft);
  --cms-line:          var(--brand-line);
  --cms-line-strong:   var(--line-strong);      /* 生成器解到 ≥3:1 */
  --cms-primary:       var(--brand-ink);        /* 主按钮 = 深墨/navy，非 accent */
  --cms-accent:        var(--brand-accent);     /* 选中、当前栏目、焦点 */
  --cms-accent-hover:  var(--clay-hover);
  --cms-accent-pressed:var(--clay-pressed);
  --cms-focus:         var(--focus-ring);       /* 生成器解到 ≥3.2:1 */
  --cms-success:       var(--brand-success);
  --cms-warning:       var(--brand-warning);
  --cms-danger:        var(--brand-danger);
  --cms-disabled-bg:   var(--disabled-surface);
  --cms-disabled-ink:  var(--disabled-text);
  --cms-radius-control: 10px;   /* = brand-system.css:31，统一到品牌值 */
  --cms-radius-card:    18px;   /* = brand-system.css:32 */
}
```

主按钮用 `--brand-ink` 而不是 `--brand-accent`，理由同
`CMS_PLAN_B §3.2`：「深墨：常规主操作；陶土：当前栏目、焦点、选中、品牌强调」。
实测支持这个选择：Family Navy 白字 17.90:1 vs indigo-600 6.29:1；
而 accent 在 8 个主题里饱和度差异很大（`#2C2A29` 到 `#A8D93A`），
拿它当主按钮底色会让 studio-ink 和 arcade-lime 的 CMS 观感完全不同。

圆角统一到 `brand-system.css` 的 10/18px，解决 D27 的五套系统里 CMS 这一套。

#### C0-D 建 7 个基础组件（`CMS_PLAN_B §7` 的规格可直接用）

| 组件 | 规格要点 |
|---|---|
| `Button` | variants: `primary` / `secondary` / `accent` / `ghost` / `danger` / `dangerSolid`；sizes: `sm` 36 / `md` 44 / `lg` 50px；支持 `loading`（宽度不跳）、`disabled`（用 `--cms-disabled-*` 不用 opacity）、左右图标；图标与文字间距 8px |
| `IconButton` | 44px，**强制 `aria-label`**（TS/PropTypes 层面必填，解决 D32） |
| `Badge` | `neutral/accent/success/warning/danger/info`，浅底深字，**始终含文本** |
| `FormField` | label 13/500、输入高 ≥44px、focus 2px `--cms-focus` ring、错误在字段下方、选填说明用 caption 字重 |
| `Tabs` | `role=tablist/tab` + `aria-selected` + 键盘左右切换 |
| `SegmentedControl` | `aria-pressed`；用于充值/退款、时间范围、主题 |
| `Accordion` | 统一 chevron + 展开旋转 90°，替换散落的 `<summary>` |

`Button` 落地后，165 个手写按钮才有地方迁。

### 6.2 阶段二：日常高频操作的效率与信息密度

#### C1-A 每个视觉区块只留一个实心主按钮

`cms-app.jsx:3378-3381` 现在是四个并排：
「今日排课」`bg-white text-indigo-800`、「新建学员」`bg-indigo-600`、
「审核报名」`bg-indigo-600`、「充值结算」`bg-indigo-600` —— 三个实心同色。

改：按当日最可能的下一步定一个 primary（工作台上是「去排课」），
其余降为 secondary。判据同 `CMS_PLAN_B §9.2`：
「主操作不超过一个实心按钮」。

#### C1-B 信息密度：`--density 8` 的间距级数用在表格与列表

`ui-ux-pro-max` 的 `--density` 8–10 档给的是 8–32px 级距。
映射到我们的 Fibonacci：表格行内边距用 `--ui-space-2`(8) / `--ui-space-3`(13)，
卡片间距 `--ui-space-3`(13)，区块间距 `--ui-space-4`(21)。
`legacy-root/index.html:129-134` 的 `.cms-kpi-grid` 已经这么做了
（`gap:var(--ui-space-3,13px)`，移动端降到 `--ui-space-2`）—— 这个模式对，
向表格和学员列表推广。

**门户是 `--density 3`（24–96px，用 `--ui-space-5..7`），CMS 是 `--density 8`。**
同一套 token，不同取档 —— 这是 token 系统该有的用法，也是"品牌一致但密度不同"
的实现方式（`refcms/docs/CMS_DESIGN_SYSTEM.md:51`：
「移动与桌面共用颜色、组件和语义，仅布局密度不同」）。

#### C1-C 字重从两档变四档，删掉大部分 `font-bold`

394 处 `font-bold` → 按 §4.2 的表分流到 500 / 600。
优先处理表格与日志：`CMS_PLAN_B §9.9` 的判据是
「表格文字恢复 400/500 字重」。一张全是粗体的表格，
粗体不再指示任何东西。

#### C1-D 表格行与导航不再 hover 位移

`legacy-root/index.html:319` 的全局 `transform:translateY(-1px)` 收窄作用域：

```css
button:hover, [role="button"]:hover { transform:translateY(-1px); }
.hover-row:hover, nav a:hover, aside a:hover, table a:hover { transform:none; }
```

理由与参考系统一致（`CMS_DESIGN_SYSTEM.md:49`）。一行 20 个单元格的表格，
整行上浮 1px 会让眼睛重新定位。

#### C1-E disabled 换成表面 + 文字色

`:320` `button:disabled{opacity:.55}` →

```css
button:disabled { background:var(--cms-disabled-bg); color:var(--cms-disabled-ink); border-color:var(--cms-line); cursor:not-allowed; }
```

生成器已经把这两个值解到约 3:1 且与 `--ink` 差 ≥1.6 倍
（`palette_gen.py:196-197`、`:253`）。

#### C1-F 触控目标统一 44px，例外要显式

38 处 `min-h-[40px]` → 44px；若某个紧凑工具条确实需要 36–40px，
在同一处注释写明是哪个工具条、为什么，并保证相邻间距 ≥8px
（`CMS_PLAN_B §11.1` 的做法）。

#### C1-G PIN 锁屏与 theme-color 换品牌值

`:257-261` 的 `#6366f1` / `#e5e7eb` → `var(--cms-accent)` / `var(--cms-line-strong)`；
`.pin-input` 静止边框从 1.24:1 提到 `--cms-line-strong`（生成器 ≥3:1）；
`:12` `theme-color` `#312e81` → `#0e1729`；
`:44-45` 的兜底 `'#312e81'` / `'#6366f1'` → Family Navy / Family Navy Raised。

#### C1-H 解除 indigo 劫持

`:323-332` 的 `[class*="bg-indigo-*"]` 全套删除，改为：
迁移过的页面用 `Button` / `Badge` 组件（消费 `--cms-*`），
未迁移的页面暂时保留原 Tailwind 类。这样劫持规则消失后不会一次性崩掉全部界面，
迁移可以逐页做。

关键收益：`--tenant-primary-soft: ${primary}14` 这种未解对比度的拼色消失，
`arcade-lime` 的 1.47:1 问题随之消失（D23）。

#### C1-I 两套深色模式合一

`:151-238` 的 88 行 `prefers-color-scheme` 映射，在所有页面迁到 `--cms-*` 之后
可以整段删除 —— 深色由租户 theme-mode 的 `color_scheme` 决定，
`root.dataset.brandScheme` 已经在标记（`:59`）。

过渡期策略：`prefers-color-scheme: dark` 且租户主题是 light 时，
**尊重租户主题**（品牌优先），但在设置里提供"跟随系统"开关，
选中后切到该主题的 dark mode（8 个主题里 7 个有 dark；`arcade-lime` 恒 dark）。

#### C1-J 语义色用生成器的值

D34 那 8 个 Tailwind 档位全部替换为 `--cms-success/warning/danger`。
实测差别：`text-green-600` 3.30:1 → vintage-press `--success` 5.00:1。

#### C1-K 保留并保护 D37 列出的部分

特别是：`Icon` 组件与零 emoji、KPI 卡一键直达筛选列表、`⌘K`、
移动端安全区、reduced-motion 的作用域说明、打印样式。
**改造过程中任何一项退化都算失败。**

### 6.3 操作路径长度（改造不得变长）

现有值得保护的路径（实测自 `cms-app.jsx`）：

| 任务 | 点击数 | 证据 |
|---|---:|---|
| 工作台 → 低余额学员列表 | 1 | `:3471` `setFilterBy('low'); setTab('students')` |
| 工作台 → 待审核 | 1 | `:3451` |
| 任意页 → 搜索某学员 | 1（`⌘K`） | `:1181` |
| 工作台 → 今日排课 | 1 | `:3352` `setRDate(todayISO()); setTab('roster')` |
| 学员档案 → 充值 | 1 | `:4926` `setTuStu(selS.id); setTab('topup')` |

参考系统的判据（`CMS_PLAN_B §9.6`）：
「学员访问码、授权、排课、充值入口仍可在两步内到达」。我们目前是一步，
更好。**验收时逐条重测，任何一条从 1 变 2 就是回退。**

---

## 7. 报名升级方案（转化视角）

### 7.1 字段顺序与渐进披露

现有顺序（`register.html:148-168`）的问题见 D19：最高摩擦的"作品公开同意"
及其两个衍生必填字段，紧贴提交按钮。

提案顺序：

```
第 1 组｜必填，永远可见（3 个字段）
  名字*     ← 单独一行，不与姓氏分栏（见 7.2）
  姓氏
  手机号*
第 2 组｜隐私同意，必填（1 个勾选 + 说明链接）
  [必填] 我同意…  + 「阅读隐私说明 →」
  ── 提交按钮 ──  ← 到这里就可以提交
第 3 组｜选填，<details> 折叠
  邮箱 / 自定义字段 / 补充说明
第 4 组｜作品公开同意，<details> 折叠，明确标「选填」
  勾选 → 展开授权人姓名* + 与学员关系*
```

关键变化：**提交按钮上移到必填组之后**。一个只想留电话的家长，
看到的是 3 个字段 + 1 个勾选 + 提交。

参考依据：`refcms/register.html:72-75` 的 `.reg-optional` 用 `<details>` 折叠选填组。
`ui-ux-pro-max` 的 `ux` 域 Forms/Progressive disclosure：
Don't「Overwhelm upfront」。

**风险与取舍**：把邮箱移到选填折叠区会降低邮箱采集率。这是有意的取舍 ——
`register.html:152` 的手机号是必填且工作室实际用它联系
（`refcms/register.html:169` 的 helper 文案「老师会用此号码联系您」印证了这个
业务事实）。如果业务方认为邮箱必须高采集，就把它留在第 1 组，
但那时要接受表单长度 +1。**这一条需要业务方拍板，不由设计单方面决定。**

### 7.2 姓/名不用 φ 分栏

`:148` `.row{grid-template-columns:var(--golden-columns-reverse)}` → `1fr 1fr`。
理由：`Design_System.md:48-50` 自家规则，peer 字段等宽。
移动端 `:111` 已经是 `1fr`，桌面跟上。

### 7.3 表单卡加 measure 上限

`:60` `.card` 加 `max-width: 34rem`（544px）。
现在是 695px（D16）。544px 与 `--ui-measure-cjk`（34em）同值，
也与我们门户 `.form-card` 的 560px、参考系统的 512/560px 同量级。

`:50` 的 `main` 保持 φ 分栏（intro vs card 确实是主次关系，φ 用得对），
只是卡片内部不再拉满。

### 7.4 blur 校验

在 `:449` 的 submit 之外，给必填字段加 `blur` 监听，复用现有的
`failFirst` 基础设施（`:299-320` 已经写好了 `aria-invalid` +
`aria-describedby` + 焦点管理）：

```
input.addEventListener('blur', () => 单字段校验 → 复用 has-error / aria-invalid)
input.addEventListener('input', () => 该字段已有错误时立即清除)
```

第二条同样重要：错误一旦显示，用户开始改就该消失，否则会一边打字一边看着
红色提示，产生"我改了它还说我错"的挫败。

**不做**：邮箱/手机的实时格式校验在用户还没打完时就报错。blur 才报。

### 7.5 `✓` 换 SVG

`:171` `<div class="mark" aria-hidden="true">✓</div>` → 内联 SVG check
（`cms-app.jsx:479-527` 的 `ICON_PATHS.check` 可直接复用路径数据）。

### 7.6 移动端

现状已不错：`:107-114` 的 760px 断点把 grid 收成单列、`.row` 收成单列、
`.done-actions` 收成单列，`brand-system.css:110-112` 保证输入框 ≥16px 不触发
iOS 缩放，`--tap-min:44px` 已用在按钮和语言切换上。

补三项：
1. `:52` `.intro{position:sticky}` 在移动端已经 `static`（`:110`），保持。
   桌面端建议改为 `position:static` 或给 `.intro` 一个最小高度 ——
   短内容 sticky 会脱钩（D21）。
2. 提交按钮在移动端加 `position:sticky; bottom:0` 的容器（带
   `env(safe-area-inset-bottom)`），长表单滚动时始终可达。
   参考 `legacy-root/index.html:266-273` 已有的安全区处理写法。
3. 错误摘要：`failFirst` 已经把焦点送到第一个错误字段（`:318`），
   移动端再补一个 `scrollIntoView({block:'center'})`，因为虚拟键盘会遮住下半屏。

### 7.7 转化路径完整性检查

家长的完整路径：门户 hero「预约体验」（`index.html:359`）→ `#join` 门户内表单，
**或** 产品主站 → 租户门户 → 独立报名页。两个表单：
- 门户内 `#join`（`index.html:520-540`）
- 独立页 `register.html`

两者已经共用 `public-register.js` 的一份实现（`register.html:445-448` 的注释
说明了这是 P1-2 修好的）。**§7 的所有改动必须同时落到两处**，
否则又会分叉 —— 这正是 `portal-theme.css:1-9` 记录过的历史问题。

---

## 8. 分批执行清单

图例：**Gen** = 影响 `palette_gen.py` / 需重跑 presets 与租户迁移；
**Build** = 需 `bash backend/scripts/build_cms.sh`；
**Tpl** = 改 `tenant-template/`，需重新生成 `tenants/<slug>/`。

### P0 — 可读性与品牌正确性（合计约 2 天）

| # | 改动 | 文件 | 标记 | 工作量 | 验收判据 |
|---|---|---|---|---:|---|
| 1 | `.result-card` / `:538` / `:442` 硬编码色换 token | `tenant-template/index.html:265,266,442,538` | Tpl | 0.5h | 15 个 theme-mode 下成功卡文字/底 ≥4.5:1（现 7 个是 1.06:1）；加一条自动化断言 |
| 2 | `.surface-status` 改用 `.brand-status[data-tone=warning]` | `tenant-template/index.html:262-264` | Tpl | 0.5h | 15 个 theme-mode 下降级提示带子不出现浅色异物；文字 ≥4.5:1 |
| 3 | 焦点环换 amber-text + 深色区覆写 | `product-home.html:50`；`backend/frontend/cms-entry.html:68` | — | 1h | Tab 遍历全页，`getComputedStyle` 的 outline 对相邻底色 ≥3:1；实测值写入注释 |
| 4 | 深色表单输入框边框 .28 → .42 | `product-home.html:157` | — | 0.5h | 边框对容器 ≥3:1（现 2.51:1） |
| 5 | 接入 `ui-tokens.css`，删自有 `--space-*` | `product-home.html:11-43` | — | 3h | `grep -c 'ui-tokens.css'` ≥1；`grep -c '\-\-space-[1-6]'` = 0；视觉 diff ≤5px |
| 6 | CMS 接入 21 个主题 token；删 `body` 冷灰底 | `legacy-root/index.html:56,297,361` | — | 2h | 8 个主题各截图，CMS 页面底色 = 该主题 `background_color`；21 个 token 全部出现在映射里 |
| 7 | CMS 语义色替换 D34 的 8 个 Tailwind 档位 | `legacy-root/src/cms-app.jsx` | Build | 4h | 无 `text-(green\|emerald\|amber\|orange\|teal)-600`；语义色对底 ≥4.5:1 |
| 8 | `text-gray-400` 128 处 → `--cms-ink-muted` | `legacy-root/src/cms-app.jsx` | Build | 4h | 无 `text-gray-400`；最弱文字对最难底色 ≥4.5:1（现 2.31:1） |
| 9 | disabled 换表面+文字色 | `legacy-root/index.html:320` | — | 0.5h | disabled 不含 `opacity`；文字对底约 3:1 且与正常态差 ≥1.6× |

### P1 — 系统层与结构（合计约 3.5 天）

| # | 改动 | 文件 | 标记 | 工作量 | 验收判据 |
|---|---|---|---|---:|---|
| 10 | 字号级数新增 `2xs/ml/xl2`；measure 拆中英；加 `--ui-grid-phi` | `backend/frontend/assets/ui-tokens.css` | — | 1.5h | 5 个原有 type 值与 7 个 space 值不变；`--ui-reading-measure` 在 `html[lang^=zh]` 下解析为 34em |
| 11 | `palette_gen.py` 语义色解到 `worst`；`CHECKS` 加 3 条 | `docs/design/palette_gen.py:174,231-233` | **Gen** | 2h | 断言 390 → 435，FAILURES: 0；`--emit-presets` 重出 `presets.py`；`migrate_visual_themes.py --dry-run` 差异只在 45 个语义 hex |
| 12 | 中文标题去负字距 / sub-1.0 行高 | `product-home.html:82,114,147` | — | 1h | `html[lang=zh]` 下 `letter-spacing` 计算值 normal；375/768/1440px 中文 h1 不切笔画 |
| 13 | 字体栈补 CJK，删未加载的 Inter | `product-home.html:39` | — | 0.5h | 字体栈 = `Brand_Identity.md:79-83` 原文；无 `Inter` 或已本地加载 |
| 14 | `--line-strong` 语义对齐 + `.flow` 分隔线可见 | `product-home.html:27-28,131` | — | 1h | 交互边界 ≥3:1；`.flow` 每格有 amber-text 序号作识别元素 |
| 15 | `.section-head > p` 加 measure | `product-home.html:115` | — | 0.5h | 900px 视口下 ≤75 拉丁字符 / ≤34 汉字每行 |
| 16 | 门户表单 label 13/500，英文不全大写 | `tenant-template/index.html:242-243` | Tpl | 1h | label ≥13px、字重 500、颜色 `--ink2`（10.05:1） |
| 17 | 报名页表单卡 `max-width:34rem` | `tenant-template/register.html:60` | Tpl | 0.5h | 输入框实测宽度 ≤544px（现 ~695px） |
| 18 | 姓/名改等宽 | `tenant-template/register.html:148` | Tpl | 0.5h | `.row` 桌面 `1fr 1fr` |
| 19 | 报名 blur 校验 + 输入即清错 | `tenant-template/register.html`；`tenant-template/index.html`（`#join`） | Tpl | 3h | 每个必填字段 blur 后即报错；`input` 时清错；**两处表单行为一致** |
| 20 | 报名字段重排 + 选填折叠 + 提交上移 | 同上两处 | Tpl | 4h | 首屏必填字段 ≤3 个 + 1 勾选 + 提交；作品公开同意在折叠区 |
| 21 | CMS 建 7 个基础组件 | `legacy-root/src/cms-app.jsx` | Build | 8h | `Button/IconButton/Badge/FormField/Tabs/SegmentedControl/Accordion` 存在；`IconButton` 缺 `aria-label` 时构建期报错 |
| 22 | CMS 触控 40px → 44px | `legacy-root/src/cms-app.jsx` | Build | 2h | `min-h-[40px]` = 0，或每处例外有注释说明 |
| 23 | CMS 表格/导航 hover 不位移 | `legacy-root/index.html:319` | — | 0.5h | `.hover-row`、`nav a`、`table a` 的 hover `transform` = none |
| 24 | PIN 与 theme-color 换品牌值 | `legacy-root/index.html:12,44-45,257-261` | — | 1h | 无 `#6366f1` / `#312e81`；`.pin-input` 静止边框 ≥3:1 |

### P2 — 体验打磨（合计约 3 天）

| # | 改动 | 文件 | 标记 | 工作量 | 验收判据 |
|---|---|---|---|---:|---|
| 25 | magic margin / min-height 换 grid | `product-home.html:134,139,149`；`tenant-template/index.html:182` | Tpl | 3h | 无 `min-height` 用于文字等高；中英切换后卡片底部对齐 |
| 26 | `.role-grid` 12 → 13 列 | `product-home.html:116-127` | — | 1h | 主/次卡宽比 8:5（1.6，φ 误差 1.1%） |
| 27 | CMS 165 个按钮迁到 `Button` | `legacy-root/src/cms-app.jsx` | Build | 12h | 逐页迁移；每页迁完立即 build + 跑契约；`font-bold` < 100 |
| 28 | CMS 解除 indigo 劫持 | `legacy-root/index.html:323-332` | — | 2h | 无 `[class*="bg-indigo-`；`arcade-lime` 租户的 CMS accent-on-soft ≥4.5:1（现 1.47:1） |
| 29 | CMS 两套深色合一 | `legacy-root/index.html:151-238` | — | 4h | 88 行映射删除；深色由 theme-mode 决定；设置里有"跟随系统"开关 |
| 30 | CMS 字重四档化 | `legacy-root/src/cms-app.jsx` | Build | 6h | `font-semibold` > 0；表格/日志文字 400–500；`text-[10px]`/`[9px]` = 0 |
| 31 | 报名 `✓` 换 SVG | `tenant-template/register.html:171` | Tpl | 0.5h | 无字符 `✓`；用 `ICON_PATHS.check` 路径 |
| 32 | 报名移动端 sticky 提交 + 错误 scrollIntoView | `tenant-template/register.html` | Tpl | 2h | 375px 下提交按钮始终可达且不被安全区遮挡 |
| 33 | 门户纹理质感（可选） | `tenant-template/index.html` | Tpl | 4h | 纹理图中性灰度，靠 `color-mix(--bg)` 上色；15 个 theme-mode 都不出现异色块 |
| 34 | `.intro` sticky 改 static 或补最小高度 | `tenant-template/register.html:52` | Tpl | 0.5h | 滚动时无"脱钩"跳动 |

### 执行顺序的硬约束

1. **#10（字号 token）必须在 #21、#27、#30 之前** —— 否则 CMS 要迁两次。
2. **#11（生成器）必须在 #7、#8 之前** —— 语义色的目标值由它决定。
3. **#6（21 token 接入）必须在 #28（解除劫持）之前** —— 先有替代，再拆旧路。
4. **#21（组件）必须在 #27（按钮迁移）之前**。
5. #11 之后必须跑 `migrate_visual_themes.py`，且 `--dry-run` 先看差异。
6. 每次改 `cms-app.jsx` 都要 `bash backend/scripts/build_cms.sh`；
   `backend/scripts/verify_local.sh:160` 会检查源码是否比产物新。
7. 每次改 `tenant-template/` 之后重新生成租户产物，并跑
   `python3 backend/scripts/check_terminology.py`（`%VENUE%` / `%WORK%` 契约）。

### 建议的两个中间确认点

沿用 `CMS_PLAN_B §13` 的做法：
- **确认点 1**：P0 全部完成后。重点看 15 个 theme-mode 的门户成功卡、
  焦点环、CMS 底色。
- **确认点 2**：#21 组件建完、迁完 2–3 页 CMS 后。重点看排课与学员列表的
  扫描效率有没有下降、§6.3 的 5 条路径长度有没有变长。

---

## 9. 风险与不做的事

### 9.1 风险表

| 风险 | 控制 |
|---|---|
| #11 改生成器导致 45 个语义 hex 位移，已有租户视觉变化 | `migrate_visual_themes.py --dry-run` 先出差异；它默认不动手调主题（`Design_System.md:136-137`）；位移量实测 ≤0.1 亮度档，见 §1.4 表 |
| CMS 逐页迁移期间新旧两套颜色并存 | 这是 `CMS_PLAN_B §12.3` 的明确策略。#28 放在 P2 就是为了让劫持规则活到最后一页迁完 |
| 全局字符串替换改变状态含义 | 不做全局替换。165 个按钮逐页迁，每页迁完 build + 跑契约 |
| 报名字段重排降低邮箱采集率 | §7.1 已标为需业务方拍板；不由设计单方面决定 |
| a11y 基线倒退 | 每条验收判据都是可测的（对比度数值 / grep 计数 / 键盘遍历），不接受"看起来可以" |
| 改 `tenant-template` 忘了重新生成租户产物 | 加进 P0 的 checklist；已有 `check_terminology.py` 覆盖模板，但不覆盖产物是否同步 —— 这一条建议补一个测试 |
| CMS bundle 忘了重建 | `verify_local.sh:160` 已经会失败并提示命令 |

### 9.2 明确不做

**A. 不给 CMS 加水彩纹理、视差、磁吸、滚动叙事。**
`CMS_PLAN_B §16` 与 `§3.1` 都写了。CMS 是每天进十次的工作界面，
装饰性动效的成本是累积的。

**B. 不改 Family Amber `#F5B335` 的值，也不把它用在浅底文字上。**
实测它在 Warm Paper 上 1.70:1。仓库为此专门有 `#A16207`
（`Brand_Identity.md:68`）。amber 只用在 Family Navy 底上（9.70:1）。

**C. 不引入 forest / sage / coral 系。**
`test_product_home_brand.py:28-38` 明确拒绝。本轮我已经把
`customer-resources/` 也纳入同一张网
（`backend/tests/test_customer_resources_brand.py`）。

**D. 不引入外部字体 CDN。**
`portal-theme.css:85-86` 定过调：CJK 走系统栈，"so mainland visitors never
wait on fonts.googleapis.com"。参考系统在这一点上比我们差
（`refcms/portal.html:50-52` 加载 Google Fonts）。

**E. 不给 CMS 引入 emoji，哪怕参考系统在生日/空状态保留了。**
`Design_System.md:106` 的理由是跨平台字形不一致 + 读屏念描述。
参考系统的 `CMS_PLAN_B §6.3` 放宽了这一条，我们不跟。

**F. 不把黄金比例用在表格列、重复 KPI 卡、peer 表单字段上。**
`Design_System.md:48-50` 自家规则。D17 是违反它的实例，
本方案 #18 是修它，不是推广它。φ 不是"到处 1.618"，
是"有真正主次关系时才 1.618"。

**G. 不做 CMS 框架迁移。**
`CMS_PLAN_B §12.1`：「保持现有 React + 本地 Tailwind 运行方式；
不迁移框架，不引入远程 CDN」。本方案全部改动都在
`cms-app.jsx` + `legacy-root/index.html` + 三个 CSS token 文件之内。

**H. 不动业务逻辑。**
排课、签到、扣课时、退款、访问码、发布同意的规则一行不改。
组件只包装视觉与交互状态，不改事件函数和数据流
（`CMS_PLAN_B §15` 的同名控制措施）。

**I. 不重新设计 Studio Admin。**
`backend/frontend/studio-admin.html`（4518 行）不在用户点名的三个面里。
但它有两个和 CMS 同源的问题值得单独记一笔，供后续排期：
`:25-60` 自己声明 `--ink/--muted/--line/--surface`，与
`brand-system.css:12-16` 的输入 token 同名冲突；
`:77-79` 是第五套圆角（8/12/16px）。它的品牌色本身是对的
（Warm Paper + Family Navy + Console Blue），比 CMS 好得多。

**J. 不追求"所有主题看起来一样好"。**
`arcade-lime` 是刻意的 dark-only 霓虹主题
（`palette_gen.py:96-98` 的注释："on a light page it turns olive and
loses the reason it exists"）。方案要保证它**可用且合规**，
不要求它和 studio-ink 一样克制。

---

## 附录 A · 本方案引用的实测数值汇总

所有数值用 WCAG 2.1 相对亮度公式计算，与 `palette_gen.py` 的 `ratio()` 同源。

### A.1 PWE 品牌色对

| 前景 | 背景 | 对比度 |
|---|---|---:|
| Family Navy `#0E1729` | Warm Paper `#F7F5F2` | 16.45:1 |
| White | Family Navy | 17.90:1 |
| Family Amber `#F5B335` | Family Navy | 9.70:1 |
| Family Amber | Warm Paper | **1.70:1** |
| Amber Text `#A16207` | Warm Paper | 4.52:1 |
| Amber Text | White | 4.92:1 |
| Slate-600 `#475569` | Warm Paper | 6.96:1 |
| Slate-500 `#64748B` | Warm Paper | **4.37:1** |
| Slate-500 | White | 4.76:1 |

### A.2 `product-home.html`

| 项 | 值 |
|---|---:|
| `.lede` `rgba(255,255,255,.78)` / navy | 11.13:1 |
| `.privacy-note` `.55` / navy（12.5px） | 6.11:1 |
| `input` 边框 `.28` / 表单容器 | **2.51:1** |
| 焦点环 amber / Warm Paper | **1.70:1** |
| 焦点环 amber / White 卡 | **1.85:1** |
| `.kicker` amber-text / Warm Paper | 4.52:1 |
| `--line` / Warm Paper | **1.34:1** |
| `--line-strong` / Warm Paper | **2.14:1** |

### A.3 `tenant-template/index.html`（跨 theme-mode）

| 项 | 浅色 | 深色 |
|---|---:|---:|
| `.result-card` `#EFE9DD` / `var(--ink)` | 13.69:1 | **1.06:1** |
| `.result-card .big` `#EAD9C7` / `var(--ink)` | 12.02:1 | **1.21:1** |
| `:538` 按钮 `#EFE9DD` / `var(--ink)` | 13.69:1 | **1.06:1** |
| `:538` 边框 `#4a463c` / `var(--ink)` | **1.76:1** | 8.26:1 |
| `:442` eyebrow `#9d9484` / `var(--ink)` | 5.52:1 | **2.63:1** |

### A.4 `portal-theme.css` 默认（vintage-press light）—— 与生成器一致

| Token | / `--bg` | / `--bg2` | / `--panel` |
|---|---:|---:|---:|
| `--ink` `#221E1A` | 14.46 | 13.01 | 16.27 |
| `--ink2` `#46403A` | 8.93 | 8.03 | 10.05 |
| `--muted` `#6C635A` | 5.14 | 4.62 | 5.78 |
| `--clay` `#835D33` | 5.13 | 4.61 | 5.77 |
| `--success` `#2F7951` | 4.62 | **4.15** | 5.19 |
| `--warning` `#8D6426` | 4.61 | **4.14** | 5.18 |
| `--danger` `#B6483A` | 4.61 | **4.15** | 5.19 |
| `--line-strong` `#8D7F70` | 3.40 | — | 3.82 |
| `--focus-ring` `#B1793E` | 3.23 | — | 3.64 |

`--bg2` 一列的三个语义色是 §1.4 / #11 要修的。

### A.5 CMS

| 项 | 值 |
|---|---:|
| `text-gray-400` / white | **2.54:1** |
| `text-gray-400` / gray-100 | **2.31:1** |
| `text-gray-500` / gray-100 | **4.39:1** |
| `text-green-600` / white | **3.30:1** |
| `text-emerald-600` / white | **3.77:1** |
| `text-amber-600` / white | **3.19:1** |
| `text-orange-600` / white | **3.56:1** |
| `text-teal-600` / white | **3.74:1** |
| `border-gray-200` / white | **1.24:1** |
| `border-gray-300` / white | **1.47:1** |
| white / `bg-indigo-600` | 6.29:1 |
| `.pin-input` 静止边框 `#e5e7eb` / white | **1.24:1** |
| disabled `opacity:.55` 合成 / white | 3.52:1 |
| `--tenant-primary-soft`（8% 拼色）+ accent，arcade-lime | **1.47:1** |
| 深色映射 `#8b93a5` / `#1a1d27` | 5.46:1 |
| 深色映射 `#efc471` / `#382e18` | 8.14:1 |

### A.6 计数

| 指标 | 值 | 文件 |
|---|---:|---|
| `var(--` 出现次数 | 8 | `cms-app.jsx` |
| `<button>` | 165 | `cms-app.jsx` |
| 可复用组件定义 | 14（无 Button/Badge/FormField） | `cms-app.jsx` |
| `font-bold` / `font-semibold` | 394 / **0** | `cms-app.jsx` |
| `text-xs` / `text-sm` | 248 / 231 | `cms-app.jsx` |
| `text-[11px]` / `[10px]` / `[9px]` | 21 / 11 / 3 | `cms-app.jsx` |
| `rounded-xl` / `rounded-2xl` | 242 / 61 | `cms-app.jsx` |
| `min-h-[40px]` / `[44px]` | 38 / 42 | `cms-app.jsx` |
| 纯图标按钮 / 其中有 `aria-label` | 5 / **0** | `cms-app.jsx` |
| indigo 类使用 | 329 | `cms-app.jsx` |
| 使用的 Tailwind 色系数 | 11 | `cms-app.jsx` |
| 主题 token 映射数（CMS / 报名页） | **10** / 21 | `legacy-root/index.html:56` / `register.html:364` |
| 圆角系统套数 | 5 | 见 D27 |
| 语义色对 `--bg2` 不足 4.5:1 的对数 | **45 / 45** | `palette_gen.py` 全 15 theme-mode |

---

## 附录 B · 本轮使用的 `ui-ux-pro-max` 依据

| 域 | 条目 | 用在 |
|---|---|---|
| `ux` / Accessibility | Contrast 4.5:1、Error Messages（`role=alert`）、Form Labels | §3 全部对比度诊断、§7.4 |
| `ux` / Typography | Line Height 1.5–1.75、Line Length 65–75、Font Size Scale、Heading Clarity、Contrast Readability | §4.2、§4.3、D13 |
| `ux` / Forms | Inline Validation（blur 而非仅 submit）、Error Placement、Input Labels、Submit Feedback | §7.1、§7.4、D18 |
| `ux` / Feedback | Progress Indicators、Error Recovery | §7.1 |
| `ux` / Touch & Interaction | 最小 44×44、8px 间距、避免仅 hover | C1-F、§7.6 |
| `ux` / Animation | 150–300ms、动效需传达意义、reduced-motion | C1-D、§9.2-A |
| `--density` 拨杆 | 低 3（24–96px）/ 高 8（8–32px） | §6.2 C1-B（门户 vs CMS 同 token 不同取档） |
| `--motion` 拨杆 | Subtle（300–400ms、y 位移 8–16px） | §9.2-A 的"不加视差/磁吸"论据 |
| `product` / LMS · Educational App | Flat + Accessible & Ethical；日历/出勤/成绩类配色（calm base + 状态色） | §6.1 C0-C 的"主按钮用 ink 而非 accent" |
| Pre-Delivery Checklist | 无 emoji 作图标、focus 可见、light mode 4.5:1、reduced-motion、375/768/1024/1440 响应式 | §8 全部验收判据 |

**一处刻意不采纳**：`--design-system` 对 "multi-tenant SaaS CMS admin" 的检索
返回 **Dark Mode (OLED)** 风格（`Light ✗ No | Dark ✓ Only`）与
Fira Code / Fira Sans 字体对。不采纳，因为：
(a) 我们的 15 个 theme-mode 里 8 个是 light，dark-only 会否掉一半;
(b) 等宽字体作标题与 `Brand_Identity.md:79-83` 的双语系统栈冲突，
且中文没有对应的等宽衬线;
(c) `#EC4899`（accent pink）与 `Design_System.md` 的生成器契约冲突。
按技能自己的指引（"If results look off-topic, pass `--domain` explicitly"），
我改用 `--domain product` / `--domain ux` 的具体条目，见上表。
