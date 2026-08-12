# 公开表面与 Studio Admin 链路审计 · 对照 v9.8.10

> 状态：**方案，未改任何代码。** 证据全部来自 v9.8.10 运行分支 `codex/v9.8.10-public-shell`
> （commit `d8c11da`）的源码，以及 2026-08-12 对生产 `https://pwestudio.online` 的实测。
> 未登录 Studio Admin（不处理明文密码），后台结论来自源码与已下发的静态 HTML，
> **未验证实际交互**；移动端菜单只验证了存在性，未走完开合。

---

## 0 · 版本现状（先对齐，这条影响所有排期）

| | 版本 | 说明 |
|---|---|---|
| 生产 | **9.8.10** | deep health：`appVersion=9.8.10`、`db=ok`、`mode=saas`、`tenants=6` |
| `main` | 9.8.8 | **落后生产 4 个提交**，且是严格祖先（`rev-list --left-right --count` = `0 4`），可直接 fast-forward |
| 运行代码 | `codex/v9.8.10-public-shell` | 未合回 `main` |

v9.8.9 / v9.8.10 的骨架是一份**公开表面契约** `/v1/public/<slug>/surface`（contract v3）：
导航、页脚、CTA 的可见性由服务端按 `intent`（店主想不想要）× `contentReady` × `dependencyReady`
合成，页面只负责渲染，并给出 `reasonCode` 与 `nextAction`。方向是对的。

**本轮发现的导航问题，全部出在这份契约落到 DOM 的最后一步**，不在契约本身。

---

# P0-1 · 首页带任何 query 时，站内导航退化成整页刷新，并吞掉 query

`backend/frontend/assets/public-surface.js` 的 `hrefForPage()` **无条件**给 hash 链接加租户前缀，
在租户首页上也加：

```js
const hrefForPage = (href) => {
  const value = text(href);
  if (!value || !value.startsWith('#') || !tenantSlug) return value;
  return `/${encodeURIComponent(tenantSlug)}${value}`;   // ← 首页也被改写，且不带 search
};
```

生产实测 `https://pwestudio.online/ruby-s-studio?lang=en`：

```
navFaq.href = https://pwestudio.online/ruby-s-studio#home:faq
sameDoc     = false          ← pathname 相同但 search 不同，浏览器判定为跨文档导航
```

后果三条：

1. **整页重载**——重新拉 `/brand`、`/surface`、`/programs`、`/gallery`，而不是 `applyRoute()` 里那次 30ms 平滑滚动。
2. **`?lang=en` 被抹掉**——与「一 URL 一语言」的既有约定冲突（localStorage 还在，所以现象是「地址栏语言没了但页面还是英文」，更难排查）。
3. **`?utm_*` 被抹掉**——广告来的访客点一次导航，归因就断了。

无 query 时（`/ruby-s-studio` → `/ruby-s-studio#home:faq`）是纯 fragment 变化，正常。
**所以这个 bug 只对「带参数进站的访客」生效——也就是所有投放来的人。**

**方案**

- `hrefForPage()` 只在「当前不在租户首页」时加前缀；加前缀时拼上 `location.search`。
- 判断是否在首页，用 `body.dataset.tenantSlug` 与 `location.pathname` 精确比较（含尾斜杠两种形态），
  **不要**用 `pathname.split('/').filter(Boolean).pop()`——见 P2-7，同一个写法已经在别处出错。
- 加断言：契约里任一 `href` 以 `#` 开头时，渲染后的 `a.href` 必须与 `location` 满足「同文档」条件，
  或者当前页确实不是首页。

---

# P0-2 · 四个公开页不是同一套导航和页脚

按 `id` 覆盖实测（`grep 'id="(nav|mnav|foot)[A-Za-z]*"'`）：

| | 首页 index | 作品页 showcase | 课表页 timetable | 报名页 register |
|---|---|---|---|---|
| 顶部导航 `nav*` | ✓ | ✓ | ✓ | **✗ 完全没有** |
| 移动菜单 `mnav*` | ✓ | ✓ | ✓ | **✗ 完全没有** |
| 页脚 FAQ `footFaq` | ✓ | ✗ | ✗ | ✗ |
| 页脚联系方式 `footContact` | ✗ | ✓ | ✓ | ✗ |
| 页脚 `footTimetable` | ✓ | ✓ | **✗** | ✓ |
| 店名节点 id | `footName` | `footName` | `footName` | **`footerTenantName`** |

三个具体后果：

- **FAQ 只在首页页脚出现。** 「常见问题」恰恰是犹豫中的家长在其他页面最想找的东西。
- **作品页在自己页面上保留自己的页脚链接，课表页却把自己的删了**——两条相反的规则，没有依据。
  更糟的是课表页那条链接**根本没有 id**，于是「公开课表」开关永远关不掉它。
- **报名页没有顶部导航栏**（它有页脚导航和一条「← 返回工作室网站」）。这是单任务页面的合理取舍，
  但它的店名节点 id 是 `footerTenantName`，与其他三页的 `footName` 不同——同一个东西两个名字。

> 更正：本文初稿写的是「报名页没有任何导航可以去别处」，不准确——它有一组页脚链接。
> 缺的是顶部导航栏，以及页脚里的 FAQ。

另外 `public-surface.js` 的加载遮罩 CSS 里列了 `#footPrincipal`（四个页面都不存在），
`apply()` 的 ids 映射里有 `heroRegister`（index.html 里不存在）。两个死 id 说明这份清单
是手抄的，没有与模板对账。

**方案（已实施）**

- 把**条目清单**提成一份公共片段（`tenant-template/_shell-nav-links.html`、`_shell-mnav-links.html`、
  `_shell-footer-links.html`），页面里只留 `<!--@shell:nav-links-->` 之类的标记，
  由 `ensure_tenant_workspace()` 在生成工作区时拼接。
  **页面外壳（`<nav>` 包裹层、品牌链接、语言开关、菜单按钮）保持各页自有** ——
  它们的 CSS 类名与语言开关属性不同，统一它们的收益远小于同时改四个线上页面的风险。
  真正会漂移的是条目清单，现在它只有一份。
- 店名 id 统一为 `footName`；`aria-current` 不再写死在标记里，改由运行时按当前路径判定
  （共享清单里的条目不可能知道自己在哪一页）。
- 加测试：四个页面**渲染后**的 `foot*` 契约条目集合必须完全相同、`nav*`/`mnav*` 在三个带导航的页面上必须相同、
  模板里不许再手写这些 id、`public-surface.js` 驱动的每个 id 必须存在于某个渲染后的页面。

---

# P0-3 · 导航标签没有长度约束，而且和「版块标题」共用同一个字段

契约里 `courses` 的标签取自 `localized_copy.courses_label`，
`register` 的标签取自 `localized_copy.primary_cta`。这两个字段**同时**喂：

- 首页版块的小标题 / hero 按钮
- 顶部导航项 / 移动菜单项 / 页脚链接

Studio Admin 的「Section names」折叠里，**没有任何提示说这也是导航文字**，没有字数计数，没有导航预览。

Ruby 工作室的真实数据（`/v1/public/ruby-s-studio/surface`）：

```
courses   zh='艺术形式'
          en='Oil Painting, Acrylic Painting, Oil Soft Pastel, Acrylic Marker, Watercolour'
register  zh='原创油画 × 私人定制'   en='Original Personalised Oil Painting'
showcase  zh='Artworks Showcase'   en='Artworks Showcase'
```

1280px 实测：

| 导航项 | 宽度 |
|---|---|
| Principal | 54px |
| Artworks Showcase | 123px |
| Questions & Answers | 134px |
| **Original Personalised Oil Painting**（CTA） | **213px** |

把她关掉的版块全部临时打开后测：`.navlinks` 宽 **1008px**、高 **76px**——
导航条本身只有 75px，**已经换行溢出**。其中 courses 一项占 241px。

同时 `#navPrimaryCta` 的计算样式是 `padding: 4px 0px`——**横向 padding 为 0**，
1px 边框直接压着字形（宽 78.4px vs 文字 76px）。短标签就已经难看，长标签必然炸。

**方案（已实施）**

1. **在契约里截断导航标签**，不新增字段：`NAV_LABEL_LIMIT`（中文 10 字 / 英文 24 字）
   同时存在于 `api_v1.py` 与 `public-surface.js`，并由一条 parity 测试比对两边结果。
   截断只作用于**导航与页脚条目**——页面上的版块标题走 `/brand`，一个字不动。
   之所以不拆成 `nav_label` 新字段：那需要数据迁移 + 后台新界面 + 契约变更，
   而店主真正的问题是「不知道这个字段还会出现在导航里」，那是文案问题。
2. **Studio Admin 的「Section names」折叠里写清楚了这件事**：这些名字同时是版块标题和导航条目，
   标题保留全文、导航条目会被截断。
3. **`.navlinks a.navcta` 提高优先级**并加 `nowrap` + 省略号；`.navlinks a` 统一 `max-width:16ch` + 省略号。

**未做**：导航项过多时收进「更多 ▾」。截断之后单项宽度已经受控，
剩下的是项目数问题（最多 8 项），留待观察真实租户是否会撞到。

---

# P0-4 · 改名不生效：Studio Admin 链路上最要命的一条

Ruby 已经在后台把店名改成了 **Mellow Pear Studio**。生产返回的原始 HTML：

```html
<title>Ruby‘s Studio</title>
<meta name="description" content="Ruby‘s Studio — 课程报名、学员课时与记录查询。">
```

而 `/v1/public/ruby-s-studio/brand` 返回 `name: "Mellow Pear Studio"`。

**根因是一条链断了：**

- `tenants/<slug>/` 是**物化的静态文件**，`{{TENANT_NAME}}` 在建租户那一刻被烤进
  `<title>`、`<meta description>`、页脚、`TENANT_NAME_JSON`。
- `backend/scripts/regenerate_tenant_workspaces.py` 的 docstring 白纸黑字：
  > Uses each workspace's tenant.json for slug/name; **the database is not touched.**
- `ensure_tenant_workspace()` 全库只有**一个调用点**：`api_v1.py:7930`，建租户。
  `PATCH /tenant`（改名走这条）**从不重写工作区**。
- `tenant.json` 也只在同一时刻写一次，之后永远是旧名。

于是：改名后 JS 会把页面上**可见**的店名修好（`footName`、`document.title` 都被 `/brand` 覆盖），
但**修不好 head 的原始内容**。Google、微信 / WhatsApp 链接预览、RSS、任何不执行 JS 的抓取器，
**永远显示旧店名**。

这与 v9.8.9 / v9.8.10「让发布变得诚实」的主题正面冲突：最该诚实的那一层没有被覆盖。

**方案**

1. **立刻**：`PATCH /tenant` 改名成功后调用 `_workspace_for(slug, new_name)`，并重写 `tenant.json`。
2. **更稳**：`<title>` / `<meta description>` 改为 `serve_tenant_home` 时从 DB 注入，
   物化文件只放结构、不放会变的内容。顺带修掉 `seo_title` 为空时的兜底——
   现在的兜底是一句通用模板文案，不是店主的 slogan。
3. **加断言**：`tenants/<slug>/tenant.json` 的 `name` 必须等于 DB 的 `tenants.name`，
   进 deep health 或 `verify_local.sh`。这类「存了 ≠ 显示了」的问题，只有数据自检能抓住。

> 这一条与 slug 改名共用同一套机制。详见 [Tenant_Slug_Rename.md](Tenant_Slug_Rename.md)。

---

# P1 · Studio Admin 的文案与信息架构

## P1-1 「发布」一个词，两个意思（全后台最危险的措辞）

- 「空间与体验」页的开关标签叫 **`Publish Space & Experience`**
- 底部保存栏的按钮也叫 **`Publish`**

前者只把 `show_about` 写进**草稿**，后者才把草稿推上线。
店主打开那个开关、以为发布了、离开——**什么都没发生**。

**方案**：所有版块开关统一为「在官网上显示 XXX / Show XXX on the website」；
`Publish` 只保留给保存栏那一个按钮。

## P1-2 同一种控件，五种写法

| 位置 | 标签写法 |
|---|---|
| Website sections | `Principal Section` / `Courses Section` / `Gallery Section` …（名词 + Section） |
| Selected work | `Selected Work Section` |
| Public timetable | `Public Timetable Page`（Page 不是 Section） |
| 同上 | `Accept booking requests`（句式，动词开头） |
| Space & experience | `Publish Space & Experience`（动词 + 模块名） |

字段词汇同样分裂：

| 面板 | 三个字段的叫法 |
|---|---|
| Selected work | `Section Eyebrow` / `Section Title` / `Section Lead` |
| Public timetable | `Page Eyebrow` / `Page Lead`（没有 Title） |
| Space & experience | `Eyebrow` / `Title` / `Description` |
| Website sections | `Courses Label` / `Gallery Label` / `FAQ Label` |

模块名本身有三个：`Space & experience`（tab）、`Space and experience`（h3）、
`About the space`（折叠标题，中文「空间介绍」）。
同理 `Preview & publish`（tab）vs `Preview and publish`（h3）——`&` 版有中文，`and` 版没有。

**方案**：定一份术语表并全后台执行——

| 概念 | 英文 | 中文 |
|---|---|---|
| 眉标题 | Eyebrow | 眉标题 |
| 标题 | Title | 标题 |
| 引导语 | Lead | 引导语 |
| 名称（导航/版块名） | Label | 名称 |
| 显示开关 | Show X on the website | 在官网上显示 X |

`&` 与 `and` 二选一（建议 `&`，短），交给 `backend/scripts/check_terminology.py` 拦住。

## P1-3 九个「要不要公开」的开关散在四个 tab

`Website sections` 面板的注释自称是「一份官网上有什么的清单」，但只装了 6 个开关；
`showcase`、`timetable`、`about` 三个各自躲在自己的 tab 里。
**没有任何一个地方能一眼看完官网上到底开了什么。**

同一个 `Website sections` 面板里，却塞了 **9 个 Principal 内容字段**
（姓名 / 头衔 / 头像 URL / 上传 / 引言 × 2 / 简介 × 2）。
FAQ、空间、作品、课表都有独立 tab，主理人没有。

**方案**

- `Website sections` 收敛成纯粹的「官网结构」总览：9 个开关，每个开关旁边直接显示契约返回的
  `reasonCode` / `nextAction`。这两个字段服务端**已经在返回**，前台完全没用——
  「你勾了但还看不到，因为还没有已同意的学员作品」这句话，现在得让店主自己猜。
- Principal 独立成 tab，与其他内容模块对齐。

## P1-4 中文缺 19%，而且缺在最要紧的地方

`backend/frontend/assets/admin-i18n.js` 是一张 **1014 条「英文原文 → 中文」查找表**，
运行时按文本精确匹配替换。实测：

- Studio Admin 可见英文串 **293 条唯一**，其中 **57 条（19%）不在表里**——切中文照样是英文。
- 漏的不是边角：
  `Changes since published`、`Public readiness`、`Publication state`、
  `Checking public surfaces…`、`Live`、`Footer`、`Photos`、`Highlights`、
  `1 week` / `2 weeks` / `3 weeks` / `4 weeks`、`Description · English`、
  `Preset applied to this draft.`、整段约课说明
  （"Booking asks only for a full name and a phone number…"）。
- 发布状态机 23 条文案漏了 6 条，**其中包括 pending 状态的解释句**：
  > The write succeeded. Recheck the public pages; your saved content is safe while verification catches up.

  「写入成功了、公开页面还在确认」正是店主最慌的那一刻，那句话是英文的。

**根本问题是这套机制不会报警**：任何一次新增英文文案，默认就是漏译，没有门禁盯着。
这与已经证明有效的 `test_section_switches.py`（拦孤儿开关）是同一类问题。

**方案**

1. 补齐现有 57 条 + 6 条状态文案。
2. 加测试：扫 `studio-admin.html` / `super-admin.html` 的可见文本节点与
   `placeholder|title|aria-label`，任何一条不在 zh 表里即失败。先补齐再开门禁。

---

# P2 · 视觉与交互

| # | 问题 | 证据 |
|---|---|---|
| P2-1 | 导航 CTA 边框贴字 | 计算样式 `padding: 4px 0px`；宽 78.4px vs 文字 76px |
| P2-2 | 语言开关（中 / EN，各 44×44）紧贴 CTA，中间无间距 | 1280px 截图 |
| P2-3 | hero 次要 CTA「Explore Programs」是独立下划线 + 小字，读起来像禁用态而非可点的第二选择；高 44px vs 主按钮 52px | 实测 |
| P2-4 | `%WORK%` / `%WORKS%` 模板占位符出现在 Studio Admin 的 placeholder 里给店主看（`学员%WORK%`、`Student %WORKS%`） | 源码 |
| P2-5 | 导航默认标签两处不一致：模板写 `FAQ` / `Courses`，契约写 `Questions & Answers` / `Courses & Classes`。契约赢，导航项凭空变长 | 实测 |
| P2-6 | 死 id：遮罩 CSS 里的 `#footPrincipal`（四页都无）、ids 映射里的 `heroRegister`（index.html 无） | 源码 |
| P2-7 | `apply()` 清理 `aria-current` 用 `pathname.split('/').filter(Boolean).pop()` 做包含判断——在租户首页上这个值就是 slug，而所有 href 都以 `/slug` 开头，判断恒真 | 源码 |

## P2-8 首页的契约失败分支不完整（「感觉失效」的直接来源）

`public-surface.js` 在加载时注入一段 CSS，把所有导航节点 `visibility:hidden`，
由 `apply()` → `clearLoading()` 解除。

- `showcase.html` / `timetable.html`：`.catch` 里设 `surfaceSettled = true` 并调 `refreshPublicSurfaceContract()` 走本地兜底。✓
- `register.html`：`.catch` 里直接调 `clearLoading()`。✓
- **`index.html`：`.catch` 里只弹了一条提示条，既不 `clearLoading()` 也不本地兜底。**
  提示语却写着「页面已按当前内容安全显示」——此刻导航是隐形的。

而且首页**没有 `surfaceSettled` 门闩**（另外两页都有）：`/brand` 先返回时会先用本地推算渲一版导航，
权威契约到了再改一版。**导航项闪一下、变一变**——这大概率就是肉眼看到的「失效」。

**方案**：首页对齐另外两页——`.catch` 里 `surfaceSettled = true` + 本地兜底 + `clearLoading()`；
加 `surfaceSettled` 门闩，权威契约到达前不渲染导航（遮罩本来就在，不会闪白）。

---

# 建议批次

| 批次 | 内容 | 对外可见的变化 | 估时 |
|---|---|---|---|
| **一** | P0-1 hash 前缀 + query 保留；P2-8 首页 catch 分支与门闩；P2-1 CTA padding + nowrap；P2-6/P2-7 死 id 与 `aria-current` | 导航不再整页刷新、不再吞 UTM、不再闪变 | ~4h |
| **二** | P0-4 改名回写工作区 + title/description 服务端注入 + `tenant.json` 一致性断言 | 分享链接、搜索结果、标签页显示真实店名 | ~4h |
| **三** | P0-2 公共 shell 统一（四页一套 header/footer，报名页补导航）；P0-3 导航标签拆字段 + 长度约束 + 降级 | 站内一致；长标签不再炸导航 | ~8h |
| **四** | P1-1 / P1-2 / P1-3 术语与信息架构统一；把 `reasonCode`/`nextAction` 显示出来 | 后台不再有两个「发布」 | ~6h |
| **五** | P1-4 补 57+6 条中文 + i18n 覆盖门禁 | 中文界面真的是中文 | ~4h |
| **六** | slug 改名能力，见 [Tenant_Slug_Rename.md](Tenant_Slug_Rename.md) | 工作室可以改地址而不丢老二维码 | ~10h |

一到三是「现在就在坏」，四五是「一直在慢慢坏」，六是新能力。
建议一、二先走一个小版本发出去——这两批全部是回归修复，风险最低、见效最快。

---

# 一条要记住的机制

这一轮找到的三个问题——死 id、四个页面的页脚分叉、19% 漏译——**根源是同一个**：
一份清单被手抄成了多份，然后没有任何东西对账。

`test_section_switches.py` 已经证明「拦孤儿开关」这种断言有效。
这一轮应该照抄它的形状，补三条：

1. 四个模板的 nav / footer id 集合必须相等。
2. `public-surface.js` 里出现的每个 id，必须至少在一个模板里存在。
3. 后台每一条可见英文串，必须在 `admin-i18n.js` 里有中文。

三条都是几十行的静态断言，但它们拦住的是这一轮花了大半天才手工找出来的东西。
