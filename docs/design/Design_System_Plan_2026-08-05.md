# 前端设计体系重构方案 — 2026-08-05

起点版本 v8.3.1。本文是方案，不是改动记录。所有数字都是本机源码统计或生产实测，
标注了出处；没有出处的判断写成"推测"。

---

## 一、现状：不是一套配色，是四套

读完全部前端（8 个 HTML 界面 + 8 个 CSS/JS 资源 + 3 个租户模板）后的统计：

| 界面 | 自定义 token | 消费 token | 散落 hex | 深色 |
|---|---|---|---|---|
| `portal-theme.css` → 租户官网 + 报名页 | 46 | — | 7 | ✅ 8 套 × 明暗，生成并校验 |
| `studio-admin.html` | 52 | 76 | 81 | ❌ 无 |
| `super-admin.html` | 49 | 55 | 61 | ❌ 无 |
| `legacy-root/index.html`（运营 CMS 外壳） | 26 | — | 34 | 1 处死钩子 |
| `cms-app.js` | — | — | 34 | ❌ 无 |
| 其余 7 个界面（产品首页 / 手册 / 合规页 / 作品页 / 设密码 / CMS 入口 / 报名旧壳） | — | — | 73 | 仅产品首页有 |
| **散落 hex 合计** | | | **330** | |

### 1.1 八个名字，三种含义

`--bg` `--ink` `--line` `--line-strong` `--muted` `--surface` `--brand` `--radius`
被三套体系**同时定义**，值不同、含义也不同。

这就是深色一直修不好的结构原因：**没有一个"它"可以翻转。**
`studio-admin` 里那三个 `--preview-paper*` 补丁就是这个冲突留下的疤——控制台要在
自己的页面里画一个租户官网的样子，两套 `--bg` 撞在一起，只能另起名字。

### 1.2 控制台是 Tailwind 默认色板压在暖纸上

`studio-admin.html` 的 45 个纯 hex token 里，**33 个是 Tailwind 默认色板的原值**
（脚本比对，见 §六复现命令）：`#3b82f6` blue-500、`#64748b` slate-500、
`#e2e8f0` slate-200、`#10b981` emerald-500……

而它的页面底色是 `--bg: #f7f5f2`——暖纸，色相约 30°。
Slate 灰阶的色相是 215°。**冷灰阶铺在暖纸上**，这在浅色模式下就已经不对，
只是不刺眼所以一直没人指出来。

对比 `super-admin.html`：底色同样 `#f7f5f2`，但灰阶是 `--muted: #6b6358`（色相 34°，
暖），强调色 `--accent: #a16207` 深琥珀，主色 `--brand: #0e1729` 藏青——
它是按平台设计体系做的。

**所以两个控制台只对齐了纸，没对齐墨。**

---

## 二、深色为什么"还是很奇怪"——四个原因，8.3.1 只修掉一个

1. ~~生成器把层次倒置（八套 dark 的 bg2 比 panel 还亮）~~ — **v8.3.1 已修**
2. **`color-scheme` 从未声明。** 生产实测租户官网 `getComputedStyle(:root).colorScheme === "normal"`。
   这一页上有 2 个 `<select>`、2 个 checkbox、11 个文本输入、1 个 textarea。
   深色主题下它们的原生外观、下拉弹层、滚动条、自动填充底色**全部是浅色**。
   `brand-system.css` 只给 date/time 输入设了 `color-scheme`（第 64/70 行），别的没管。
3. **散落 hex 不响应模式。** 生产实测：把 vintage-press dark 的 22 个 token 注入官网后，
   回到顶部按钮 `.totop` 的背景仍是写死的 `rgba(251,249,244,.9)`，文字是 `--ink`
   （深色下 `#E1DFDC`）——**对比度 1.26:1**。WCAG 要 4.5:1。那个 ↑ 在每一套深色主题下
   都是看不见的。
4. **`<meta name="theme-color">` 写死 `#F4F0E8`**，`applyVisualTheme` 从不更新它。
   深色租户在手机上，浏览器地址栏还是米色。

> **教训沿用**：26 项对比度断言在 (1) 上全绿了很久。断言什么，就只保证什么。
> (2)(3)(4) 同样是现有断言表达不了的类别——它们不是"某两个颜色的比值"，
> 而是"某个东西根本没参与主题"。

---

## 三、首屏照片：上传成功、发布成功、照片不显示

生产实测六个租户，`heroProfile.hero_image_url` **全为空**。控制台**是有上传的**
（`uploadWebsiteImage('hero', …)`，`studio-admin.html:4509`）。链条断在三处：

1. **上传只写 URL 输入框，不动 Hero Style 下拉框。**
   `uploadWebsiteImage()` 设 `$(urlInputId).value` 后就 `setSettingsDirty(true)` 了
   （4516–4517 行），`settingHeroStyle` 仍是默认的 `soft`。
2. **官网只在 `heroStyle === 'image'` 时显示照片。**
   `tenant-template/index.html:1277` `classList.toggle('hero-image', heroStyle === 'image' && …)`；
   CSS 第 122–123 行 `.hero-art img{display:none}` / `body.hero-image .hero-art img{display:block}`。
3. **控制台预览从不画照片。** `studio-admin.html:2575` 的 `.preview-art` 是个空 `<div>`。
   所以店主上传后，预览里没有、线上也没有，**没有任何反馈告诉他缺了一步**。

附带两个：
- 下拉框写 "Image Background"（暗示满幅），实际只填右侧 4:5 的画板。标签与行为不符。
- 没照片时那块画板是 414×517 的渐变色块（1440 宽实测），是首屏最大的单个元素，
  而且什么都不说。

---

## 四、方案

按用户给的顺序：读组件 → 生成可配置预览页 → 出规范 → 用规范重构 →
先明暗框架 → 再填行业 → 再把明暗行业关联起来。

### P0 · 首屏照片（独立，先出）

小、独立、用户已经在用，不该等大重构。

- 上传成功后若 `settingHeroStyle` 仍是 `soft`，自动切到 `image` 并 toast 说明；
  店主想要渐变板可以再切回去。
- `.preview-art` 接上真实图片（P1 之后它会变成 iframe，此处先补最小实现）。
- 下拉选项文案改成与行为一致：`Image Background` → `Photo panel`；
  真正的满幅背景作为第五个选项另做，或者不做。
- 无照片时的 4:5 渐变板：给它一句 `frame-tag` 之外的说明，或在窄屏隐藏
  （现在 `body.hero-minimal` 已经能隐藏，只是没人选）。
- 测试：断言"上传 → style 变 image"，断言官网在 `hero_image_url` 非空且 style=soft 时
  **不**静默吞掉照片（要么显示要么在控制台可见地提示）。

### P1 · 设计实验室 `docs/design/lab.html`

一个自包含静态页，三种模式：**浅色 / 深色 / 调色**。

**必须是生成的，不能手写。** 现有的 `docs/design/theme-proposal.html`（1009 行，
手写）就是反例：它停在 8.3.0 之前的配色，现在展示的是已经被推翻的深色。
所以：

```
docs/design/build_lab.py   读 presets.py + portal-theme.css + 组件清单 → 写 lab.html
backend/tests/test_design_lab.py   重新生成，断言与仓库里的文件零差异
```

**组件清单**（从三个界面的 199 / 182 / 109 个类名归并，约 49 个）：

| 组 | 组件 |
|---|---|
| 容器 8 | page / band / card / panel / modal+scrim / disclosure / sticky toolbar / save bar |
| 导航 6 | header、nav-bar、tabs（studio/preview/device 三种）、footer、skip link、面包屑 |
| 表单 11 | text、textarea、select、date、time、color、file、checkbox、radio、switch、range |
| 表单反馈 3 | label+helper、行内错误、必填标记 |
| 动作 6 | primary、secondary、outline、danger、icon-only、link-as-action |
| 反馈 7 | toast ×4 语气、行内状态、进度条、空状态、骨架屏、badge/pill、stat tile |
| 数据 5 | 表头/行/hover/斑马、列表行、分页、图表占位、等宽数字 |
| 内容 6 | hero（4 种 style）、课程卡、作品瓦片、FAQ、主理人、brandband |

每个组件在 15 个 theme-mode（8 套 × 明暗，arcade-lime 仅暗）下各画一遍，
下面直接印出它用到的 token 和实测对比度。

**"调色"模式的关键设计：滑杆调的是生成器的输入，不是输出的 hex。**
即 `hue / sat / sec_off / sec_sat` 四个主题参数，加上表面亮度常数
（浅色 `.935 / .888 / .992`、深色 `.068 / .102 / .150`）。
拖动时实时重跑 26 项对比度断言 + 2 项层次断言，红/绿当场显示。
右下角 "复制 THEMES 条目" 按钮吐出可直接粘回 `palette_gen.py` 的五行。

这样闭环是：**在浏览器里调 → 粘回生成器 → 重新生成 presets → 测试守住**，
而不是在浏览器里调出一套第五个手写调色板。

**求解器双实现的风险**：滑杆要实时求解，就得把 `palette_gen.build()` 移植成 JS
（约 120 行）。风险是两份实现漂移。对策与 presets↔生成器的漂移测试同款：
`test_lab_solver_parity.py` 用 `node`（本机 v26.3.1）跑 JS 求解器，对 15 个
theme-mode 加一格 hue×sat 合成网格，逐 token 比对 Python 的输出，不一致即失败。
本机没有 node 时 skip 并打印原因。

### P2 · 设计规范 `docs/design/Design_System.md`

**同样是生成的**（`build_spec.py`），从 token 文件 + 组件清单 + 实测对比度表生成，
测试断言重新生成零差异。手写规范三个月后必然与代码不符——`theme-proposal.html`
已经演示过一次了。

内容：

1. **颜色**：三层表面 / 四级文字 / 两级边界 / 强调三态 / 语义四色 / 交互四态。
   每一条写清"它被解算against哪个面"，因为这正是 8.3.0 之前出错的地方。
2. **层次规则**（8.3.1 新增，规范里要写成第一原则）：
   *决定明暗互换时必须守住的是"远近顺序"，不是"亮度差值"。*
   卡片永远是最近的面；交替带永远不越过卡片；深色下带子相对页面的步长
   不得超过浅色步长的 1.6 倍。
3. **排版**：φ 字阶 13/16/21/34/55、行高、55ch 阅读宽度、中英混排（拉丁展示字体 +
   CJK 系统栈，不走 fonts.googleapis.com）。
4. **间距**：Fibonacci 5/8/13/21/34/55/89；61.8/38.2 分栏。
5. **形状 / 阴影 / 动效**：入 233ms、出 144ms、`prefers-reduced-motion`。
6. **触控**：44×44 底线，以及"必须 44px 的是浏览器派发点击的那个盒子"
   （伪元素不接受命中测试——8.3.0 踩过）。
7. **明暗配对规则**：每套主题的两个模式是一个整体，单独改一个模式不算改完。
8. **每个组件的 token 契约**：这个组件允许消费哪些角色 token，禁止写死 hex。

### P3 · 一套 token 词汇（不做大改名）

评估过全局改名（`--sf-page` / `--tx-body` 之类），**不推荐**：改名要动 330 处，
收益只是避免撞名，而撞名真正伤到的只有一个地方——控制台里那个租户预览面板。

推荐的做法：

1. **`portal-theme.css` 的语义就是全产品的语义。** 两个控制台改成消费它，
   `studio-admin` 那 33 个 Tailwind 原值退役，灰阶换成暖的（与 super-admin 一致）。
2. **控制台预览面板改成 `<iframe srcdoc>`。** 这一步同时解决四件事：
   - 两套 `--bg` 从此在两个 document 里，撞名不可能再发生，`--preview-paper*` 三个补丁删掉；
   - 32 个 `preview-*` 类名（手写的租户官网仿制品，会漂移）删掉；
   - 预览可以真的渲染深色，店主终于能在控制台里看见深色长什么样；
   - 首屏照片在预览里自然就显示了（P0 的第 3 条随之消失）。
3. **控制台专属角色**（表头底色、行 hover、审计日志语气）加 `--ad-` 前缀，
   数量控制在 10 个以内，且每个都要在规范里写明为什么租户词汇不够用。
4. **散落 hex 归零**：330 → 0，加静态测试守住（与现有 `test_frontend_xss_static.py`
   同一模式，扫源码而不是扫渲染结果）。

### P4 · 明暗框架

1. **`color-scheme` 上 `:root`**，跟随 `data-brand-scheme`。一行，修掉整类原生控件问题。
2. **补齐主题从未覆盖的表面**：滚动条、`::selection`、`::placeholder`、autofill、
   `<select>` 弹层、checkbox/radio、`input[type=color]` 的取色器按钮、
   `<meta name="theme-color">`（要在 `applyVisualTheme` 里跟着改）。
3. **两个控制台各出一套深色**，走 `palette_gen.py` 同一条流水线——
   控制台不是特例，它只是又一个 spec。
4. **测试**：把"注入某个 dark 主题后扫描整页，任何可见元素的
   前景/背景对比度 < 4.5（文本）或 < 3（非文本边界）即失败"做成实测型测试。
   这正是 `.totop` 1.26:1 逃掉的那类缺陷——它不在任何一对断言里，
   因为它的背景根本不是 token。

### P5 · 行业 × 明暗

1. **8 套行业主题保持现状**（生成 + 校验 + 层次断言），补上 P4 新增的表面 token。
2. **控制台只取强调色，不取表面。**
   推荐：控制台自己的浅/深两套用平台身份（暖纸 + 藏青 + 深琥珀），
   行业主题只染强调色，让店主认得出这是谁的控制台。
   *理由*：一个染成 arcade-lime 的管理后台不好用；而且平台控制台设计体系
   是已经定过的决策。
3. **明暗关联**：目前 `style_theme(style_id, scheme)` 两个轴是独立选的。
   要"关联"，就是让店主选一次主题、两个模式一起发布，然后决定切换权归谁——
   见 §五的待决问题。
4. `arcade-lime` 只有暗色，任何"跟随访客"的选项都必须对它禁用。

---

## 五、两个需要你拍板的问题

**Q1｜深色由谁决定？**
现在是店主定死（`brand-system.css` 的注释写着"访客的操作系统没有投票权"）。
选项：(a) 保持店主定死；(b) 店主可选"跟随访客系统"；(c) 官网右上角给访客一个开关。
(b)(c) 都要求两个模式都发布，也就是 P5 的"关联"必须先做完。
**我的建议是 (b)**：默认仍由店主定，想开的店主可以开——工作室的品牌是店主的，
但"我在夜里看手机"是访客的事实。

**Q2｜控制台要不要行业配色？**
上面 P5.2 我建议"只染强调色"。如果你要的是控制台整套跟着行业走，
方案不变，只是 P5 的工作量从 1 套 ×2 变成 8 套 ×2，且要给
arcade-lime 这种高饱和主题单独定一条"控制台变体"的降饱和规则。

---

## 六、版本阶梯与验收

| 版本 | 内容 | 可验收的数字 |
|---|---|---|
| **v8.3.2** | P0 首屏照片 | 上传后 style 自动为 image；六个租户任一上传后线上可见 |
| **v8.4.0** | P1 实验室 + P2 规范 + P3 词汇统一 | 散落 hex 330 → 0；`preview-*` 类 32 → 0；lab/spec 重新生成零差异 |
| **v8.5.0** | P4 明暗框架 | `colorScheme` 全站 ≠ normal；深色实测扫描 0 项低于阈值（`.totop` 从 1.26 → ≥4.5） |
| **v8.6.0** | P5 行业 × 明暗 | 15 theme-mode 在 49 个组件上全绿；控制台明暗两套通过同一条流水线 |

每一版都遵守既有纪律：
- 新测试**先拿旧代码跑一遍**，确认它会失败，再信它（v8.2.30 的教训）；
- 静态资源改了就进版本号，同版本重新部署到不了浏览器（v8.3.1 的教训）；
- 用 `deploy/aws/build_aws_bundle.sh` 打包；
- 改动开始和完成都更新 `docs/HANDOFF_LATEST.md`。

### 复现本文数字

```bash
# 四套调色板与散落 hex
for f in backend/frontend/studio-admin.html super-admin.html \
         backend/frontend/assets/cms-app.js legacy-root/index.html \
         tenant-template/index.html; do
  printf "%-45s defines:%3d hex:%3d\n" "$f" \
    "$(grep -cE '^\s*--[a-z0-9-]+:' "$f")" \
    "$(grep -oE '#[0-9a-fA-F]{3,8}\b' "$f" | wc -l)"
done
```

`.totop` 的 1.26:1、`colorScheme === "normal"`、六个租户 `hero_image_url` 全空，
都是在 `https://pwestudio.online/lets-paint-showcase/` 上注入 vintage-press dark
的 22 个 token 后用 `getComputedStyle` 实测的，不是读代码推出来的。

---

## 七、`/ui-ux-pro-max` 的使用说明（诚实记录）

本轮向该技能查了 `--domain ux "dark mode surface elevation contrast tokens"`
和 `--domain color "design tokens semantic color system"`。

- `ux` 域返回 2 条，都是"正文对比度 4.5:1"这一类通用条目，本项目 26 项断言早已覆盖，
  **对深色层次问题没有增量**。
- `color` 域返回的是成品色板（Design System / LMS / 室内设计等），是"选一套配色"的工具，
  而本项目的配色是**按主题参数解算出来的**，不适用。

真正用上的仍然是 `references/pro-rules.md` 的 Light/Dark 表和 44px 触控条目。
黄金分割与色彩和谐已经在 `ui-tokens.css`（φ 字阶、Fibonacci 间距、61.8/38.2）
和 `palette_gen.py`（split-complementary / analogous / triadic 按主题标注）里落地，
本方案不改这两条，只是让它们覆盖到目前没覆盖的控制台。
