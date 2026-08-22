# Studio CMS 设置页重构方案

> 本文主体由六维度并行审计 + 逐条对抗性验证生成（13 个 agent，64 条发现通过验证）。
> 下面三节「主 agent 补充」是我自己核出来、合成时不在上下文里的，单独标出。

## 主 agent 补充一：根因是一次没做完的迁移，不是排版失误

设置页这块代码是**双模**的（`cms-app.jsx:3706`）：`tab==='settings'` 时是整页带 tab，
否则是从用户菜单弹出的模态——模态里 `hidden` 恒为 false，七个分区**故意**叠成一条长滚动。

模态那一版是先有的。后来加整页 tab 时，只有被 `<div id="settings-{key}">` 包住的块跟着分了区，
**没被包的块原地不动**。在模态里它们是长滚动的一部分（正确），在整页里就出现在每个 tab 上。

这解释了为什么它「看起来像设计得不好」——它其实是一次没做完的迁移。
补完迁移（方案 A）和推倒重排（方案 B/C）代价差一个数量级，这一点应进入选型。

补充证据：`showSettings === true` 的每条路径都同时设了 `tab='settings'`
（`cms-app.jsx:124` 与 `:137-139`，初值 `:66`），所以模态形态今天**不可达**——
与正文第 22 条一致，且意味着删掉它是安全的。

## 主 agent 补充二：开票信息越权已实测复现，根因是权限粒度

正文第 1 条的判断正确，但根因需要修正：**不是「面板忘了包角色判断」，而是 `billing:read`
把两件事合并成了一个权限**——「处理发票」（前台确实需要）和「读取工作室自己的收款账户」
（前台不需要）。前端没包角色只是症状。

本地端到端实测（v10.12.0 代码，音乐 / 美术样板租户）：

| 角色 | GET /billing/identity | 银行信息 |
|---|---|---|
| owner | 200 | 是（应然） |
| manager | 200 | 是（可议） |
| **front_desk** | **200** | **BSB 083-004 / 账号 12 345 6789** |
| **staff** | **200** | **同上** |
| teacher | **403** | 否（正确） |

链条（逐环读码 + 实测）：

1. `GET /billing/identity` 只要 `billing:read` —— `api_v1/billing.py:1229`
2. `billing:read` 授予 FRONT_DESK（`auth.py:135`）与 STAFF（`auth.py:156`）
3. `FEATURE_BILLING` 在 `BASELINE_FEATURES` 里，**不分套餐一律放行** ——
   `services/entitlements.py:58-66`，所以套餐这一关形同虚设
4. 返回字段含 `bank_account_name` / `bank_bsb` / `bank_account_no`，未脱敏 ——
   `services/billing.py:151-156`
5. 前端面板无角色包裹、挂载即请求 —— `cms-app.jsx:4053`、`billing_identity.jsx:48`
6. `<input value={form[key]}>` 带值渲染，仅 `disabled` —— `billing_identity.jsx:102`

**影响面**：线上 `lets-paint-showcase` 有 1 个 front_desk、`music-studio-showcase` 有 1 个 staff
——这两个正是演示时会把账号交给客户点的租户。真实租户 `lets-paint-studio` 目前只有 owner，
所以是**潜伏**而非已发生泄露；但它招进第一个前台的那天就成立。

**修法应在后端**：`billing:read` 拆成 `billing:read`（发票）与 `billing:identity:read`
（主体 + 银行），后者只给 owner / manager；前端包角色只是补上第二道。
**只改前端不算修好** —— 面板隐藏了，接口照样返回。

## 主 agent 补充三：演示数据还有一条客户看得见的矛盾

正文第 20 条提到年龄公式，实测确认了它的对外后果：

「适龄 4–6」的启蒙班里坐着 **Chloe Zhang（10 岁）和 Jasmine Patel（7 岁）**，
周三、周六两个班次都是。而包里的学习报告写着 Chloe「六岁的第一个学期」。
文案说 6、数据库算出 10、课程写 4–6，三方互相矛盾，在 CMS 名单上直接可见。

同源的还有生日：全部 12 名学员生日挤在 8/23–8/29，其中 6 人同为 08-23、3 人同为 08-24。
根因同为 `reset_professional_demo.py:573` 用 `today - timedelta(days=365 * N)` 推导，
365×N 必然落回今天附近。真实分布下 12 人名册在任意 14 天窗口只应有 ≈0.4 人，
也就是排课页那个「近 14 天生日（12 人）」横幅平时根本不该出现。

---


面向：Lee（产品负责人）
范围：`legacy-root/src/cms-app.jsx` 的设置页（`SETTINGS_SECTIONS`，:3069-3077）及其面板、i18n 词典、演示播种器
状态：全部论据已在源码中逐行核对；不确定处在文中明说

---

## 一、现在坏在哪

**这个页面有两类问题，必须分开处理。**

**第一类是确认的缺陷，与任何 IA 讨论无关。** 设置页的七个 tab 里，有五块内容根本没写在任何 tabpanel 里（cms-app.jsx:3739-3747 语言切换、:3749-3755 紫色横幅、:3872-4014 未到访预警+迁移卡片、:4044-4050 数据维护工具、:4070-4095 退出登录+快捷操作），所以它们在全部七个 tab 上同时渲染——这就是截图里看到的重复。同一个根因还有第二半：角色门只做在 tab 标签上，没做在面板上，于是 `billing-identity`(:4053)、`integrations`(:4058)、`workspace`(:4062) 三个面板对所有角色无条件渲染并发请求，front desk 和 staff 不需要知道任何 URL 参数，按 Ctrl+U 就能读到工作室的收款户名、BSB 和账号（billing_identity.jsx:99-107 带值渲染，只是 `disabled`）。此外 `?section=` 参数没有白名单（components.jsx:66，而同一个函数 :62 的 tab 就有），演示数据把美术工作室的开票主体印在了音乐租户的发票上（reset_professional_demo.py:687/:756），英文态下集成页整屏正文没有词条。

**第二类是设计弱点，是判断不是缺陷。** 七个 tab 是按「谁负责渲染」切的，不是按「操作者在做哪件事」切的：`workspace` 整格只有一条 URL 加一个复制按钮（:4062-4069），而 `integrations` 里装的是一个有失败项、需要逐张重放的工作队列（integrations.jsx:497-534）——那是每天要看的东西，不是设置。

**两类的处理次序不同。** 第一类无论选哪个方案都要修，且其中两条（无主片段泄漏、`?section=` 无白名单）必须同一批修——今天设置页之所以不白屏，正是因为泄漏内容顶在那儿；修好泄漏，一条过期链接就会变成一个七个面板全 hidden、没有任何 tab 高亮的空页。第二类才是下面要请你拍板的。

---

## 二、思路：重构的判断依据

不是任务清单，是六条用来判断「这块该放哪」的标准。

### 依据一：设置装一次性配置；有数量的东西不是设置

如果一块内容会产生「有 N 个在等我处理」，它属于工作区，不属于设置。

集成面板违反了这条：它有推送队列、积压计数、失败单列表和「修好了，重放」（integrations.jsx:497、:515、:522-531）。而 CMS 的待处理徽章 `pendingCount`（cms-app.jsx:3061）只算 `db.pending + bookings`，不含任何 Xero 项；`panels/billing.jsx` 里 grep `xero|queue` 只剩三处文案，没有队列 UI。也就是说：一张推送失败的真实发票在等，徽章是 0，唯一能看到它的路径是 owner 主动点进 设置 → 集成 → 往下翻。更糟的是这个 tab 的可见性是 `ownerRoles.includes(actorRole)`（:3074），manager 和 front desk——每天开票收款的两个角色——在 UI 上完全看不到它。

按这条依据：连接/断开 Xero、科目税率映射留在设置（一次性），队列/对账/重放搬去账单发票工作区。

### 依据二：可见性只能有一个来源

标签的可见性和面板的可见性今天各写一遍，于是必然分叉。`SETTINGS_SECTIONS`（:3069-3077）的第三个元素是唯一的真相，标签条（:3732）读了它，面板（:3756/3830/3853/4030/4053/4058/4062）没有。

这条依据同时决定三件事的修法：面板越权渲染、`aria-labelledby` 指向不存在的 id（:4053/:4058 指向被角色过滤掉的 `settings-tab-billing-identity`）、以及测试该断言什么。正确形状是从 `SETTINGS_SECTIONS` 派生一个 `sectionVisible(key)`，标签、面板挂载、URL 收敛三处都读它。

### 依据三：URL 是产品的一部分

设置页 URL 会被收藏、被粘进工单、被 owner 转发给 teacher。`syncCmsRoute`（:114）会主动把 `?section=` 写进地址栏，所以这是产品支持的能力，不是意外。

支持深链就必须做两件事：白名单回落（拼错的 section 回 `account`），以及角色收敛（当前角色看不到的 section 回落到可见列表首项，并用 `replaceState` 改写 URL，别污染后退栈）。今天两件都没做，而同文件里的三个兄弟 setter 都做了：`setTab`(:122) 有 `CMS_ROUTE_TABS.has()`，`setPendingTab`(:130) 有白名单，`:403` 有角色回落——只有 `setSettingsSection`(:136-141) 原样收下。

### 依据四：边界句只有一句，而且已经写在代码里了

`cms-app.jsx:3748` 的注释写着 "Public website and lead-capture settings live in Studio Admin"。这句话是对的，问题是产品自己违反它两处：团队成员的「可在公开课表显示姓名 / 对外显示名」在 CMS（:3777-3800），而公开课表本体在 studio-admin.html:2973；注册页 URL 在 CMS（:4062），而注册表单在 studio-admin.html:3040。

把这句话升级成执行标准——**对外的一切在 Studio Admin，对内的一切在 CMS**——然后逐条检查归属。凡是「设置在 A、后果在 B」的，跟着后果走。

### 依据五：租户级的值必须有服务端单一来源

「待续课提醒阈值」今天有三处定义：`renewTh`（:223，localStorage）、硬编码 2（:1122，喂给侧栏和底栏徽章）、文案里的「≤ 2」（dashboard.jsx:297）。唯一的编辑入口 `MaintSection`（components.jsx:969-977）被 `{!TENANT_SLUG && ...}`（:4044）关在外面，而 `TENANT_SLUG` 对每一个真实租户恒为非空（legacy-root/index.html:36 的路径正则永远命中）。结论是：**这个阈值在任何界面上都改不了**，徽章也不读它。

「未到访预警天数」（`lp_inactive_days`，:168）同样存 localStorage 且键名不带租户前缀——对照同文件 :3115 的 `lp_admin_email_${TENANT_SLUG}`，同一个文件里两种写法并存。平台管理员在同一浏览器开两个租户会共用一个阈值。

按这条依据：两个阈值都收进 `/operational-settings`（tenant.py:1051，已支持 manager），和默认上课时间同一个地方；localStorage 只作读取失败兜底且键名加前缀。这与 MEMORY 里「一套配色，多个界面」是同一形状。

### 依据六：演示内容必须由内容包驱动

播种器里不允许有租户可见的字面量。今天违反的至少五处：开票主体（reset_professional_demo.py:687-690 / :756-765，"Paradise Production Pty Ltd" / ABN 53 004 085 616 / Southbank 地址 / accounts@letspaint.example）、Xero 组织名（:1023 "Let's Paint Studio (Demo Org)"）、充值流水（:601 恒为 58500 分）、教师薪酬（:858/:867/:896-899）、出勤时间（:616/:635 恒为 18:30）。

判断标准很简单：**这个字符串会不会出现在租户或家长看得到的屏幕上？** 会，就必须来自 `*_showcase_content.py`。

---

## 三、方案（三选一，互斥）

三个方案是三种终局，不是三个阶段。第四节的 bug 无论选哪个都要修，不计入方案代价。

### 方案 A：保持七 tab，只做归属矫正

**改什么**
- 把五块无主内容各自归位：`:3872-3881`（未到访预警）并进 `settings-operational`（:3853 面板内）；删 `:3882-4005`（`{false && ...}` 死代码）与 `:4006-4013`（迁移公告卡片）；`:3739-3747` 语言块与 `:4070-4095` 退出登录/快捷操作定义成设置页的页眉/页脚区，明确放到所有面板之外并加分隔；`:3749-3755` 紫色横幅并入侧栏已有的「网站与品牌」按钮（:3571）。
- 面板挂载改条件渲染并共用 `sectionVisible(key)`。
- `?section=` 白名单 + 角色收敛。
- `MaintSection` 按能力拆开：阈值与 PWA 缓存清理对租户同样成立，移进 `settings-maintenance`；数据体检/每周邮件/本地备份保留 `!TENANT_SLUG`。
- tab 条数量、名称、URL 全部不变。

**代价**：改动集中在 `cms-app.jsx` 单文件，一个 patch release 能收。不需要重定向表，所有历史链接继续有效。

**风险**：低。唯一的坑是七处 `hidden` 里那个 `tab==='settings' &&` 前件——它是给一个不可达的弹窗形态留的（:3711-3725，`showSettings && tab!=='settings'` 恒假，我把 `setShowSettings` 的全部 7 个写入点都追过），删掉前先确认没有回归依赖。

**适合什么情况**：只想让截图上的问题消失、这一轮不做产品判断。

**代价的另一面**：`workspace` 仍然独占七分之一（对 teacher 是仅有两个 tab 之一）；集成里的失败队列仍然只有 owner 能看见；侧栏那个叫「系统设置」的按钮仍然硬编码落在「账号与安全」（:3584）——owner 为了看 Xero 每次都要先经过自己的密码表单。也就是说依据一、四没有被执行。

### 方案 B：七 tab 收成三组，仍在 CMS 内（**推荐**）

**改什么**
- tab 变成三个：**我的账号** / **工作室** / **连接与数据**。
  - 我的账号 = 现 `account` + 界面语言 + 退出登录（全角色可见，永远至少有这一格）
  - 工作室 = 现 `team` + `operational`（吸收两个预警阈值）+ `billing-identity`
  - 连接与数据 = 现 `integrations`（只留连接状态、映射、一行队列摘要）+ `maintenance`
- 删掉 `workspace` tab：复制注册链接移到「待处理」页顶部（front desk 每天在那儿，其 `allowedTabs` :302 含 pending）和「新建学员」空态；健康状态那一份留给 Studio Admin 的发布区（studio-admin.html:3159），两边不再各留半份。
- 按依据一把推送队列/对账/重放整段搬进 `panels/billing.jsx`，failed 计数并入 `pendingCount` 或在账单侧栏项单独挂徽章；设置里只留一行状态摘要 + 「去账单发票处理 N 张」。
- 侧栏「系统设置」改为按角色选默认分区（owner/manager → 工作室，teacher/front desk → 我的账号）；用户菜单「账号与安全」继续深链到我的账号。
- 需要一张 `?section=` 旧值 → 新值的重定向表（7 → 3），走白名单同一份代码。
- 方案 A 的全部归属矫正包含在内。

**代价**：比 A 多一个文件（`panels/billing.jsx` 接收队列 UI）、一张重定向表、一轮 i18n 词条（三个新 tab 名 + 队列搬家后的上下文）。仍然是单 release 可交付。

**风险**：中低。两个具体风险点：(1) `setSettingsSection`(:136-141) 自带 `setTabState('settings')` 副作用，改成按角色决定默认分区后，默认值必须由同一个函数产出，否则会退回 `useState` 初值（:44 读 URL）；(2) `billing.jsx` 是 `panels/` 下的子组件，`setSettingsSection` 目前不在它的 props 里，队列搬过去要连带把跳回设置的能力传进去（`setTab('settings')` 只会落到 account，因为 :114 对 `'account'` 不写 section）。

**适合什么情况**：认可依据一和依据三，愿意在这一轮承担一次 URL 迁移，但不想动双后台边界。

**为什么推荐这个**：它是唯一同时执行了依据一（队列回工作区）、依据二（可见性单一来源）、依据三（URL 契约）而代价仍然限定在 CMS 内的方案。方案 A 把依据一留在原地——而依据一指向的是这个产品里唯一会卡住钱的东西：X4 真账本已经通电（LPS- 前缀推 PWE GROUP），一张推送失败的发票今天在产品里没有任何主动可见性。方案 C 的收益更大但前置条件今天不成立（见下）。

### 方案 C：设置页拆到两个后台

**改什么**：「我的」做成用户菜单里的账号抽屉（全角色，不占 tab）；「工作室配置」整体并入 Studio Admin 成为它的一个分区；CMS 从此只剩每天干活的地方。

**代价（已核实，不是估计）**：
- 源语言相反：`admin-i18n.js:977` 是 `targetLanguage:'zh'`，`cms-i18n.js:891` 是 `targetLanguage:'en'`。开票信息、团队这些中文源文案要反向搬进英文词典。
- 技术栈不同：Studio Admin 是原生 JS（studio-admin.html 3279 行 + assets/studio-admin.js 4227 行，另一套设计体系），而 `BillingIdentityPanel` / `IntegrationsPanel` 是 React。要么重写，要么在 Studio Admin 里挂 React 运行时。
- 权限模型不同：Studio Admin 用 `tenant_admin_required`（auth.py:635-660，只放行 super/owner/manager），CMS 用 `canManageOperations` + `settings:write`。合并要先统一。

**风险**：高。这是三件基础设施（i18n 源语言、设计体系、权限模型）的统一，不是一次页面重构。

**适合什么情况**：把「owner 配一间新店要在两个后台之间往返四到五次」当成本轮要解决的首要问题。

**我的判断**：定为 v11 方向，前置条件是先统一两个后台的源语言与设计体系。本轮做 B。

**这里必须标注不确定**：「七 tab 的切分本身是错的」「没有任何两个分区是操作者会来回切的」「改密码是最高频入口」这些是产品判断，代码里没有使用数据能证实或证伪。方案 C 声称的「往返从 4-5 次降到 1 次」同样没有埋点支撑。如果你手上有 Studio Admin ↔ CMS 的跳转数据，它会直接改变 B 和 C 的排序。

---

## 四、先修的 bug（与方案无关）

按严重度排序。每条一句话修法，不是补丁。

### High

1. **开票信息面板对所有角色渲染，银行 BSB 与账号上屏**
   `cms-app.jsx:4053`（面板无角色包裹）+ `backend/studiosaas/api_v1/billing.py:1230`（GET 只要 `billing:read`，front_desk/staff 都有：auth.py:135/:156）
   修：面板包进 `canManageOperations`；**同时**后端把 `bank_account_name/bank_bsb/bank_account_no` 三字段按 `settings:write` 裁剪——单靠前端隐藏不算修好（`billing_identity.jsx:99-107` 是带值渲染 + `disabled`，Ctrl+U 可读）。注意此路径只在已开通开票的租户上成立（billing.py:1238 的 `_require_feature`），也就是 X4 真账本通电的那批。

2. **五块无主内容在全部七个 tab 渲染**
   `cms-app.jsx:3739-3747` / `:3749-3755` / `:3872-4014` / `:4044-4050` / `:4070-4095`
   修：各自归位（见方案 A 第一条）。修的时候五块要一次改完，漏一块等于没修。

3. **`?section=` 无白名单、无角色收敛**
   `legacy-root/src/components.jsx:66`（对照同函数 :62 的 tab 有白名单）
   修：导出 `CMS_SETTINGS_SECTIONS` key 集合，`has()` 不中回落 `'account'`；再加一层角色收敛并 `replaceState`。**必须与第 2 条同一批上线**，否则修好泄漏当天，老书签就变白屏。

4. **集成面板同样无角色包裹，manager/front desk/staff 可只读整个 Xero 状态**
   `cms-app.jsx:4058` + `backend/studiosaas/api_v1/xero.py:36`
   修：面板包进 `ownerRoles.includes(actorRole)`；后端 GET 改 `integrations:manage`（同文件 :88 的 connect-url 已经这么写了——同一块功能读写两把钥匙）。

5. **Manager 能填满开票表单、按钮可点、后端必 403**
   `cms-app.jsx:3073`（tab 门是 `canManageOperations`）+ `billing.py:1246`（PUT 另需 `settings:write`，MANAGER 没有）
   修：二选一，别折中。推荐把 :3073 与 :4056 都改成 `ownerRoles`，给 manager 只读态 + 一句「开票主体由 Owner 维护」。另一条路（给 MANAGER 加 `settings:write`）是商业决策，因为该权限还管着 misc.py:458 和 tenant.py:1605。

6. **演示开票主体张冠李戴，且 ABN 校验位通过**
   `backend/scripts/reset_professional_demo.py:687-690` 与 `:756-765`
   修：整块 identity 搬进内容包（两个包已有 `IDENTITY["billing_email"]`，showcase_content.py:62 / music_showcase_content.py:97，播种器 :326 已经在用，:689/:762 又硬写了一遍）；ABN 换成校验位**不通过**的号——`53 004 085 616` 实测同时通过 ABN 和 ACN 两套校验算法，和一个真实分配的号在肉眼与 ABR 查询里没有区别；同文件 :858 的 `61 111 222 333` 是正确写法，照抄它。

7. **错的开票主体已冻结进 4 张已开具发票**
   `reset_professional_demo.py:800-811` 写快照，`services/invoice_documents.py:106-113` 对任何非 draft 单据优先读快照
   修：**改设置页救不回来**。修完第 6 条后必须 `--pack music --confirm RESET-MUSIC-STUDIO-SHOWCASE` 完整重跑；handoff 里写明「改设置页不改历史单据」。

8. **Xero 组织名是播种器字面量**
   `reset_professional_demo.py:1023`（"Let's Paint Studio (Demo Org)"，且 `ON CONFLICT DO UPDATE`，每次重跑再写一遍）
   修：搬进内容包（或由 `NAME` 派生），加进 `_select_pack` 的 required 元组（:150-154）。顺带把 :1012 那条中文单语的 addon 备注一起包化。

9. **集成页在英文下正文全中文**
   `backend/frontend/assets/cms-i18n.js:149-172` 那组词条服务的是永久关闭的 preview 分支（`services/xero.py:47` `TRANSPORT_AVAILABLE = True` → `integrations.jsx:240` `preview` 恒 false）
   修：按 live 分支重过词条（单向推送段、连接卡、Step 1-5 正文、映射编辑器、试跑、队列、对账）。数量型短语必须由源码整句发出再加正则规则，不能靠拆字。

10. **「未到访预警天数」四个按钮在英文下读成 `60days`**
    `cms-app.jsx:3878` 结尾 `>{d}天</button>` → 编译后是两个 Text 节点（cms-app.js:9950-9951），`天→days` 命中但无空格
    修：改成单个模板串 `{`${d} 天`}`，rules 加 `[/^(\d+)\s*天$/, '$1 days']`。别在源码补空格——中文下会多一个空格。

11. **开票面板三条 GST/ABN 拦截提示在英文下是中文**
    `panels/billing_identity.jsx:77` / `:89` / `:94`（同面板 :70-73 的长说明反而有词条）
    修：三条整句进 `cms-i18n.js` 的 Settings 段；`加载失败：` 前缀加规则。这是合规路径上的静默——0040 的 CHECK 约束会真的拦住开具。

12. **紫色横幅说明文字 2.50:1**
    `cms-app.jsx:3753` `text-indigo-400`（=`--accent` 与 `--accent-soft` 70/30 混合，本就不是前景色）；11px normal text 门槛 4.5:1
    修：改 `text-indigo-700`（=`var(--accent)`）；在 role() 的 400 档标注「仅用于填充/边框」。

13. **手机端唯一填色主按钮 2.83:1**
    `cms-app.jsx:4083`（`bg-indigo-600` 无任何 `text-*`，经 preflight 的 `a{color:inherit}` 一路继承到 `--ink`）
    修：加 `text-white`（在本仓库 `white` 是 `var(--panel)` 的别名，是生成器断言过的 on-accent 配对，改后 6.03:1）。深色主题下现状会变成浅字压浅底，只会更糟。

14. **待续课阈值三处定义、徽章不读它、编辑器在租户版不渲染**
    `cms-app.jsx:223`（localStorage）/ `:1122`（硬编码 2，喂 :3546 侧栏与 :4132 底栏徽章）/ `dashboard.jsx:297`（文案「≤ 2」）；编辑器 `components.jsx:969-977` 被 `cms-app.jsx:4044` 的 `!TENANT_SLUG` 关掉
    修：收进 `/operational-settings`（tenant.py:1051）；`:1122` 改读同一个值；`lp_inactive_days` 键名加 `TENANT_SLUG` 前缀。

### Medium

15. **403 被翻译成「这个工作室尚未开通开票功能」——把没权限说成没买**
    `billing_identity.jsx:44` 与 `billing.jsx:245`（逐字相同），`integrations.jsx:73-78` 的 403 落到「Xero 预接入（Preview）」卡片
    修：机器码早就到了前端（`components.jsx:88` `err.code = d.error`），两个面板一次都没读。按 `feature_not_available` 分流；`setState(null)` 拆成 `notEntitled` / `notPermitted` / `loadFailed` 三个显式状态。这句假话连英文版都跟着说（cms-i18n.js:144）。

16. **开票 409 的 toast 没有跳转按钮**
    `panels/billing.jsx:784`（`showToast` 支持第三参 action，:736 与 :2843 都在用）
    修：补 `{label:'去填开票信息', onClick:()=>setSettingsSection('billing-identity')}`；无权角色改文案不给按钮。这是产品里唯一一条真正卡钱的跨页依赖，而寻路资源今天投在了迁移公告（:4010-4011）上。

17. **Studio Admin 四个入口两套门**
    `cms-app.jsx:3571`/`:3639`/`:4082` 只判 `TENANT_SLUG`，只有 `:3749` 判 owner。teacher 点进去会撞上 studio-admin.js:3841-3862 的 `setLoadBlockedState`，屏幕上出现一句「请先在 Super Admin 开启支持会话」，直接把老师送去找平台方；manager 更糟，表单能编辑，按保存才被 `tenant:update` 打回。
    修：抽 `canOpenStudioAdmin` 常量，四处统一。

18. **结构测试只断言 `role="tabpanel"` 字符串存在**
    `backend/tests/test_cms_navigation_names.py:97`
    修：从源码解出 `SETTINGS_SECTIONS` 七个 key，逐个断言 `id="settings-{key}"` + `role="tabpanel"` + `aria-labelledby`；再断言每个角色下 `[role=tabpanel]` 数量等于 `[role=tab]`。这条测试的 docstring（:82-88）写的正是它没覆盖到的失败模式——无主片段和孤儿 div 就是这么过 CI 的。

19. **退出登录同屏两个，一灰一红，确认文案不同**
    `cms-app.jsx:4071`（走 `requestLogout`，:3010「确认退出登录？」）与 `:4092-4093`（内联第二份，「…下次进入需重新输入密码。」）
    修：删设置正文里的两个，desktop 保留侧栏 + 用户菜单，mobile 移进底部导航；文案统一走 `requestLogout`，但要把长文案挪进去，别把长的删掉。

20. **充值流水恒为 $585 / 教师薪酬整块字面量 / 学员年龄靠 index 公式**
    `reset_professional_demo.py:601`（音乐包价目表里没有 58500，12 × 585 = $7,020 出现在 CMS 首页累计收款）；`:858`/`:867`/`:896-899`（16:00/90 分钟/6 人，而 Hannah 在 SCHEDULES 里三个班全是 60 分钟）；`:573-574`（Chloe 算出 11 岁，包里写「六岁」；她和 8 岁的 Jasmine 都被排进 age_range 4–6 的启蒙小组）
    修：三组数据各加一个内容包结构（`CREDIT_PURCHASE` / `TEACHER_PAY` / STUDENTS 元组加 `age_years`、`enrolled_days_ago`），并在 `test_showcase_tenant.py:532` 补一条「年龄必须落在所选课程 age_range 内」的断言。

### Low（同批顺手）

21. `aria-labelledby` 指向被角色过滤掉的 id（`cms-app.jsx:4053`/`:4058`）——随第 1、4 条一起消失。
22. 不可达的弹窗分支（`:3711-3725`、`:164` 的 `useModalFocus`）——删掉后七处 `hidden` 简化为 `settingsSection!==key`。
23. 六个 tabpanel 各自带一条 `border-t`（:3756/3853/4030/4053/4058/4062），只有 account（:3830）没有——摘掉，交给容器。
24. `platform_super_admin` 是数据库存不下的角色（schema_v1.sql:88 的 CHECK 无此值），前端九处分支永假——删掉，需要区分平台身份就让 `/v1/auth/me` 返回布尔值。
25. 表单 `focus:ring-*` 是死代码（被 index.html:558-560 的 `!important` 压住），且一页混用 400/500 两个色阶，生成器解出的 `--focus-ring` 表单不用。
26. 集成里的 `window.prompt('清算账户科目号')`（integrations.jsx:374）永远不会被翻译（cms-i18n.js:899 `wrapNativeDialogs: false`）——换成 CMS 自己的对话框（:496-501 已有）。
27. 零散漏词条：`['界面语言']`、`['启用','Activate']`（停用有、启用没有，同一个权限开关两种语言）、`['链接已复制']`、`['查看公开网站']`、`['连接中']`（词典 :82 收的是不存在的「连接中...」）、`['更新中...']`、`['保存中…']`、`['网站与品牌 · Studio Admin']`（整串，别去放宽 AFFIX）。

---

## 五、不建议做的事

1. **不要放宽 `cms-i18n.js:721` 的 AFFIX 字符类去解决「网站与品牌 · Studio Admin」。** 把 ASCII 纳入前后缀，会让 `已连接 Xero · Zhiyin Music` 这类现在靠 rules 命中的串改走 AFFIX 分支，结果不可控。加整串词条。

2. **不要靠在源码里补空格修「90天」。** 中文下会多出一个不该有的空格。词典注释里已经写明了正确做法（模板串 + 正则）。

3. **不要为「Manager 填不了开票信息」直接给 MANAGER 加 `settings:write`。** 那个权限还管着 misc.py:458 和 tenant.py:1605 两个端点，是商业决策不是修 bug。默认走「收窄到 owner + 只读态」。

4. **不要把 `:root { --brand: var(--accent) }` 被悬空选择器吃掉（index.html:1110）当线上缺陷排。** 规则从未生效是真的，但它生效了也不改变任何一个像素：`brand-system.css:8` 的链条第一层 `--tenant-primary` 是常驻声明（index.html:517-519），永远走不到 `var(--brand)`；注释指的那个 stock blue 消费者早在 v8.4.0 就修好了（admin-i18n.js:968）。当死变量清理，不当缺陷。

5. **不要保留弹窗形态的兼容分支。** `showSettings && tab!=='settings'` 恒假（7 个写入点全追过），所以「所有面板同时可见」没有任何合法场景。留着它会让下一个人以为面板越界是一种形态而不敢改。

6. **不要只改前端就宣布权限问题修好。** 第 1、4 条的后端门（billing.py:1230、xero.py:36）不动的话，隐藏的只是 UI，数据仍然对 `billing:read` 开放。

7. **不要指望改设置页能修好已开具发票上的错误主体。** 快照是正确行为（invoice_documents.py:106-113），必须重跑播种。

8. **不要先给 tab 条加渐隐遮罩解决 375px 溢出。** 这条我只算了没量：按 text-xs + 全角字宽估到约 540px 内容对 343px 可用宽度，方向几乎不会错，但按本仓库「量渲染结果，别量代码」的纪律，应在浏览器里读一次 `scrollWidth` 再定级。真正 100% 确证、且与视口宽度无关的是「切换/深链后不把选中 tab 滚进视口」（`setSettingsSection` :136-141 没有 `scrollIntoView`）——先修这个。

9. **不要在本轮启动方案 C。** 它的前置条件（两个后台的源语言、设计体系、权限模型统一）本身就是三件独立工程。

10. **不要把「Paradise Production 出现在租户界面」当品牌架构违规来立案。** `01 BRAND ASSETS/BRAND_ARCHITECTURE.md:47-49` 管的是标志和位置，不是名字；同文件还把「Powered by Paradise Production」定为租户页脚规范。而且这个名字本来就是产品自己文案里的示例值（cms-i18n.js:680-681、billing_identity.jsx:18、0040 migration:23）。第 6 条只立在两点上：一个双校验通过的税号被印在演示税务发票上，以及两个租户共用同一个开票主体。

---

## 建议的落地顺序

一个 release：第四节 High 段的 1-5（结构与权限，必须同批）+ 12、13（对比度）→ 方案 B 的 IA 改动 → 6、7、8（演示数据，含一次完整重跑）→ 9-11（i18n）。Medium 与 Low 跟在其后。

上线前需要你先拍板的只有一件：**方案 A / B / C 选哪个**。我的推荐是 B，理由在方案 B 的「为什么推荐」一段——它是唯一让那张推送失败的发票获得主动可见性、而代价仍限定在 CMS 内的选项。