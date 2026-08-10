# Platform Admin 逐屏审计、状态矩阵与执行 handoff

日期：2026-08-10  
审计对象：`/platform-admin`（源码页面：`super-admin.html`）  
审计基线：v9.6.1，当前分支 `codex/v9.3.0-cms-information-architecture`，审计时 HEAD `2a59854`
实现/发布状态：v9.7.0 已完成 P0 shell、持久化工作区状态、租户/审计 detail drawer、Support Mode 字段级反馈、Plans 字段级校验，并已部署到 `pwestudio.online`；本文件的 P2 项仍保持后续队列。

最终发布证据：release commit `ade9f90b32e46d6aeb0a681d7574bf44e9d3f5ab`；SaaS 包 SHA-256 `fda3ca5cddeef8588d8515fbdb8b1511f9f825cc4114fe23a864653450045e42`；Edition 包 SHA-256 `6bf1697a886affc25de200bb442642e923e6be86d48ebbe15007889e32e253e4`；生产 deep health `appVersion=9.7.0`、`db=ok`、`mode=saas`、`tenants=6`、`themes.unreadable=0`；公网关键路由和版本化 `admin-i18n.js` 已独立验收。

## 1. 当前事实与边界

### 1.1 版本、路由和部署事实

| 项目 | 当前事实 | 证据 |
|---|---|---|
| 源码版本 | `9.7.0`，release commit `ade9f90b32e46d6aeb0a681d7574bf44e9d3f5ab` | `VERSION`、发布 `BUILD_INFO` |
| 平台管理直达入口 | `/platform-admin`，应用登录 | `docs/Product_Surface_Model.md`、`backend/server.py` |
| 兼容入口 | `/super-admin`，可由 Cloudflare Access 保护 | `docs/Product_Surface_Model.md` |
| 生产页面 | `https://pwestudio.online/platform-admin` 返回 `200`；`/v1/health?deep=1` 为 `appVersion=9.7.0` | 2026-08-10 部署后公网检查 |
| 当前页面模型 | 单一 active workspace，四个 workspace 由 hash 深链切换，非当前 workspace 不占据视觉内容流 | `super-admin.html` 的 `#overview/#tenants/#plans/#audit` 与发布后 Browser 检查 |
| 后端 API | usage、plans、tenants、audit logs、subscription settlement 均已存在 | `super-admin.html:4555` 附近、`backend/studiosaas/api_v1.py` |
| 支付范围 | 本轮不新增在线支付、银行转账、Gmail/SMTP、SES 或付款凭证流程 | 已确认的产品边界 |
| 权限边界 | 平台管理员管理租户生命周期、套餐、订阅、用量、审计；进入租户 CMS/Admin 必须走可审计 Support Mode | `docs/Product_Surface_Model.md` |

### 1.2 真实审计样本

为避免把生产数据写入审计，使用本机 `studiosaas_local_test` 数据库和临时平台管理员账号完成真实登录；未对生产数据、生产账号或租户内容执行写操作。审计页面当时呈现：

- 5 个非测试工作室、4 个套餐、100 条审计事件。
- 总览：Past Due 1、Dates Passed 2、MRR AUD 497、付费工作室 3、试用工作室 1。
- 真实打开了详情、编辑、Support Mode 原因表单、套餐表单和删除确认；未提交创建、保存、删除、归档、暂停或 Support Mode。
- 真实验证了英文、中文、桌面约 1280×720 和移动 390×844。

## 2. 结论先行

当前 Platform Admin 的数据和权限基础是可复用的，问题主要集中在“工作台如何呈现”和“状态如何交接”：

1. **最重要的问题不是颜色，而是页面仍然是四个工作区的长画布。** 点击导航后只是滚动到 section；总览、工作室、套餐、审计同时存在于 DOM 和视觉层级中，平台管理员需要靠滚动理解当前上下文。
2. **锚点与 sticky header 没有安全偏移。** 真实点击 Plans、Audit Logs、移动端 Overview 后，section 标题或第一行内容会被固定 header 覆盖；这是可复现的可用性问题。
3. **总览已经有“需要处理”和“经营概况”的语义分组，这是可保留的好方向。** 但它仍主要是 KPI 卡片，没有把待处理对象、下一步动作和数据更新时间放在第一屏。
4. **工作室行的信息密度合理，但动作被拆成 View、More、CMS、Admin 等多个入口。** 详情、编辑、打开租户表面和 Support Mode 的关系需要重新编排，避免把高风险动作与普通打开动作放在同一层级。
5. **详情/操作/编辑都依赖弹窗。** 详情 tab 在手机上会横向截断，操作弹窗在桌面和手机都需要内部滚动；Support Mode 空原因提交没有观察到清晰的内联校验反馈。
6. **套餐与审计的数据功能基本够用。** 套餐已经明确区分“已发布/未发布”和“推荐”；审计已经有搜索、数量和分页。下一步应改善定位、详情和异常状态，而不是重新发明后端模型。
7. **`past_due` 的产品文案要谨慎。** 当前 UI 写“Payment issue / 付款异常”，但本产品本轮没有在线支付网关。应表达为“订阅逾期/Subscription past due”或“订阅状态需复核”，不能暗示系统已经确认了一笔支付失败。

## 3. 逐屏审计

### 3.1 全局外壳与登录

| 观察 | 可取之处 | 问题/风险 | 结论 |
|---|---|---|---|
| 平台品牌 | 使用 PWE Studio、Family Navy、Warm Paper、SVG 图标，和既有品牌一致 | 移动端 header 高度约 242px，操作按钮换行后首屏可用内容显著减少 | 保留品牌，压缩移动 header |
| 语言 | 中英文按钮清楚；动态 KPI、分页、筛选 chip 会随切换重新本地化 | 套餐代码、行业名称等业务数据保持英文是合理的，但需要明确哪些是数据、哪些是界面文案 | 保留运行时 i18n，补齐新结构的语义 key |
| 登录 | 必填、401、429、加载中、密码显示/隐藏均有处理；非平台 super admin 会退出并提示 | 没有在本轮发现 P0 登录阻断 | 保持权限流程，不在 UI 重构中改变认证 |
| 全局刷新 | Refresh 有 loading spinner；数据请求使用 `Promise.allSettled`，套餐、usage、settlement、audit 可部分失败 | 部分失败主要通过短 toast 告知，没有在对应工作区留下持久状态；租户 API 失败会使主刷新进入总错误 | P1：增加工作区级状态条和“上次成功刷新时间” |
| 导航 | 四个职责名称清楚，键盘可达 | 现在是长页锚点导航，不是独立工作区；sticky header 遮挡锚点目标 | P0：保留四项职责，改为单一 active workspace/可深链状态 |

### 3.2 Overview / 总览

#### 当前信息结构

```text
Commercial Overview
├─ Needs attention：Past Due / Trials Ending / Onboarding / Dates Passed
├─ Business health：Tenants / MRR / Paid / Trial / New in 30 Days
└─ 折叠的 30-Day Acquisition Funnel
   ↓ 同一页面继续出现 Tenants、Plans、Audit Logs
```

#### 审计结果

- “Needs attention” 在“Business health”之前，且总览卡片可点击跳转到工作室筛选；这是当前最值得保留的交互逻辑。
- MRR 是非按钮，避免把金额总计误当成可筛选租户集合；测试已经锁定这一语义。
- `Past Due`、`Paid`、`Trial` 等卡片的筛选字段与后端 subscription status 对齐，不能改成 tenant status。
- Acquisition Funnel 默认折叠，优先级正确；展开后数据显示为报名次数、转化次数、转化率、入口来源。
- 首屏没有明显的更新时间、数据来源和“当前没有待处理项”的工作流结果；卡片为零时仍占用同样视觉重量。
- 真实移动截图显示 Overview 锚点把 section 顶部放到了 sticky header 下方，第一排卡片被遮住。

#### 目标结构

```text
Today / Overview
├─ Header：当前数据时间 + Refresh + partial-status
├─ Needs attention queue（对象、原因、下一步）
├─ Business health（次级统计，不抢 action hierarchy）
└─ Optional insights（获客漏斗、趋势；默认折叠）
```

`Needs attention` 不应只是四个数字。第一阶段可继续使用现有接口，在卡片下增加“查看工作室”入口；若后端暂时只提供计数，则必须明确这是计数入口，不伪装成完整队列。

### 3.3 Tenants / 工作室列表

#### 已有优点

- 搜索、租户状态、套餐、行业、测试租户开关和 Clear Filters 都有明确标签。
- 总览 KPI 跳转后会在工作室区显示 `From overview` chip，并保留独立清除入口；这是良好的可解释筛选链路。
- 桌面表格展示 Studio、Plan、Status、Owner、Usage、Surfaces、Actions；移动端通过 CSS 把表格单元格转成带字段名的卡片，未依赖强制全页横向滚动。
- 用量同时显示学生数和存储，能支持平台运营快速判断是否接近套餐限制。

#### 需要改善

- 当前工作室区在总览下方，点击导航只是滚动；过滤器、标题、结果表不是一个独立工作区。
- 桌面实测租户表格内部 `scrollWidth` 约 1246px、可视宽约 1166px，存在约 80px 的局部横向滚动；这在 1280px 视口仍然发生。
- 一个租户同时暴露 Portal、CMS、Register、Admin，再加 View、More；普通查看、公开表面、受保护表面、改变状态的动作层级不够明显。
- 行内文案“Payment issue/付款异常”超出当前支付产品范围；应改为订阅状态文案。
- 当前没有可见的排序、批量动作、列偏好；本轮不必全部加入，但应把“筛选→查看→处理”作为核心路径。
- 无结果能正确显示 `No tenants match the current filters.`，但需要更清楚地提供“清除筛选”以及当前筛选摘要。

#### 目标结构

```text
Tenants
├─ 工作区标题 + 新建工作室
├─ 筛选栏（搜索、状态、套餐、行业、测试数据）
├─ 当前筛选摘要 + 结果数量
├─ 工作室列表（主要动作：View；次要动作：Open surface）
└─ Tenant detail drawer/full-screen detail
   ├─ Overview
   ├─ Subscription & limits
   ├─ Contacts
   ├─ Usage
   └─ Operations / Support Mode
```

移动端采用 full-screen detail，桌面采用右侧 drawer 或宽 detail workspace；不要把所有管理行为继续塞进一个居中的大弹窗。

### 3.4 Tenant detail / 详情、编辑与 Support Mode

#### 观察到的状态

- View Details 打开带 Overview、Subscription & Billing、Contacts、Usage、Operations 的详情界面。
- Overview 有 Health、Plan、Students、Storage、Risk/Setup、Onboarding Checklist、Quick Links，内容可用于平台运营判断。
- More 打开 Actions 界面，分成 Manage、Open、Support Mode、Status、Danger Zone；分组语义清楚。
- Edit Tenant 表单已按 Basic、Owner & Contact、Admin Login、Subscription、Limits 等折叠区组织，slug 为只读，生命周期改变被引导到 More actions；这比一个无边界表单更安全。
- Support Mode 明确要求 reason，并说明每个动作会被审计；后端 Support Mode gate 与产品权限模型一致。

#### 需要改善

- 详情 tab 在 390px 上横向截断，Contacts 只能看到一部分；可滚动但不够可发现。
- 操作弹窗的内容高度超过桌面首屏，Support Mode 区域在首次截图中位于折叠/滚动区域下方；高风险动作不应因为弹窗滚动而“藏起来”。
- Support Mode 空 reason 点击 Start 后没有观察到清晰的内联错误、字段 `aria-invalid` 或焦点回到输入框；这是安全操作的 P1 可用性问题。
- 编辑表单的保存/取消是 modal footer 动作，表单很长；需要持续显示 dirty 状态、失败位置和保存结果。
- View、More、Edit Tenant、Open CMS/Admin 的关系应改成：查看是默认路径，编辑是管理路径，CMS/Admin 是受 Support Mode 保护的外部表面，Danger Zone 永远单独确认。

### 3.5 Plans / 套餐

#### 已有优点

- 列表清楚展示价格、学生/用户/存储额度、entitlements、Published/Not published、Recommended。
- 新增/编辑表单把公开定价和 entitlements 分组，并明确“创建存在”和“公开售卖”是两个状态。
- 当前没有把支付网关、付款方式或交易状态塞入套餐管理；符合本轮暂停在线支付的边界。
- 删除有独立确认弹窗，没有直接一键删除。

#### 需要改善

- 点击 Plans 后，`Plans & Pricing` 标题和新增按钮在 sticky header 下被部分遮挡，降低了页面定位和主动作可见性。
- 表格的 Limits 和 entitlements 信息较长，桌面横向密度偏高，移动端需要卡片化或明确折叠层级。
- 删除确认只表达“是否删除”，没有在确认前说明是否仍有租户订阅使用该套餐；如果后端已有保护，界面应说明保护结果。
- 表单字段的 required 属性主要依赖 JavaScript 逻辑；空表单提交时未观察到明确的字段级错误展示，应补齐。

### 3.6 Audit Logs / 审计日志

#### 已有优点

- 搜索 action、tenant、resource；有总事件数、有分页，默认只显示 15 条。
- 搜索有结果、无结果两种状态均可观察；无结果文案清楚。
- 资源 UUID 会截断但保留完整 title，避免整列被 UUID 撑宽。
- 时间按本地化格式渲染，中文/英文切换会重绘动态标签。

#### 需要改善

- 点击 Audit Logs 后标题和搜索框被 sticky header 遮住，与其他锚点同源。
- 目前审计行没有 detail drawer；管理员无法在不复制 UUID 的情况下查看完整 payload、操作者、Support Mode 关联原因或前后值。
- action、resource type、tenant 和时间范围仍只能靠一个全文搜索框；数据量增长后定位成本会快速上升。
- 审计日志应强调“不可逆记录”和“谁在何时以何身份做了什么”，而不是只展示技术 action 名称。

## 4. 状态矩阵（实现前合同）

状态命名原则：`loading` 不等于空，`empty` 不等于失败，`partial` 不等于整页不可用；高风险操作必须同时有 `confirming`、`submitting`、`success` 和 `error`。

| 工作区 | Loading | Ready | Empty / no match | Error / partial | 操作状态与恢复 | 权限/审计 |
|---|---|---|---|---|---|---|
| Login | 登录按钮 disabled，文案 `Logging in…`，字段保留 | 成功后进入 Today，并显示当前账号 | 不适用 | 401 内联错误并聚焦密码；429 告知等待；session check 失败保留登录入口 | 显示/隐藏密码；网络失败可重试 | 仅平台级 `super_admin`；不改变现有认证 |
| Today | 卡片使用 skeleton 或明确 loading，而不是长时间 `-` | 待处理队列、经营概况、更新时间、Refresh | 待处理为 0 时显示“当前无需处理”，漏斗无数据时说明原因 | usage、settlement、plans、audit 可各自显示 partial；tenant 核心失败才阻断列表 | KPI → Tenants 保留筛选 chip；Dates Passed → settlement decision list | 统计不暴露租户敏感内容；金额标明是 plan/subscription MRR |
| Tenants | 筛选可用但结果区显示 loading；刷新不清空上次成功数据 | 结果数、筛选摘要、列表、每行健康状态 | 无工作室与筛选无结果分开；都给 Clear Filters/Back to all | tenant API 失败提供工作区级错误和 Retry；plans 失败不清空租户列表 | search/filter 只重绘列表；View 打开详情；外部 surface 经过 Support Mode | 查看平台元数据；CMS/Admin 需要 Support Mode；状态/删除需确认并写审计 |
| Tenant detail | detail loading 不能露出旧租户数据 | Overview / subscription / contacts / usage / operations | 缺数据字段显示 Not configured，而不是空白 | 单 tab 可失败并 Retry；保留租户标题和安全上下文 | drawer/full-screen；tab 可用键盘；关闭恢复原行焦点 | 不显示未授权学员数据；Support Mode reason 必填、提交中禁用、成功后可打开新 tab |
| Tenant edit | 保存按钮 loading，表单锁定但可取消 | dirty/clean 明确，字段分区可折叠 | 不适用 | 字段级校验；API error 显示在表单顶部并定位字段 | Cancel 明确丢弃；成功 toast + 列表刷新；失败保留输入 | 生命周期/危险动作不混入普通 Save；所有写操作审计 |
| Support Mode | Start button loading，reason 保留 | 成功提示 session scope、过期/退出入口、打开目标 surface | 空 reason 不提交，输入框 `aria-invalid`、inline error、focus 返回 | 403/409/网络失败留在表单并给 Retry；不打开半授权页面 | reason 最少一个可读说明；success 后新 tab；失败不改变当前页 | 每个租户动作附着 support session + reason；不可绕过 |
| Plans | 表格/表单 loading；保留上次目录直到新数据成功 | price、limits、entitlements、publication state 可比较 | 无套餐提供 Add Plan 与说明 | plans API 失败不影响 Today/Tenants；单个保存失败保留表单 | Add/Edit: validate → submitting → success/error；Delete: dependency check → confirm → success/error | 不包含支付交易逻辑；公开状态变更可审计 |
| Audit | 表格 skeleton，搜索框可保留 | 结果数、时间、tenant、action、resource；分页 | 无日志与无匹配分开 | API 失败显示 Retry 和最后成功时间，不伪装为空日志 | search debounce；分页保留 query；row → detail drawer | 只读、不可改写/删除；展示操作者和 Support Mode 关联 |

## 5. 推荐的信息架构与视觉执行规则

### 5.1 工作区模型

```text
Platform Admin
├─ Today / 总览             # 今天先处理什么、平台经营健康
├─ Tenants / 工作室         # 找到、查看、处理租户
├─ Plans & Pricing / 套餐   # 套餐目录、额度、公开状态
└─ Audit Logs / 审计日志    # 治理与追溯
```

- 导航继续使用四项，不在本轮增加 System Settings、Health、Backups 等一级入口。
- 从“长页锚点”改为“单一 active workspace”。第一阶段可以继续使用 hash 深链以减少后端变更，但非当前 workspace 不应占据视觉内容流。
- URL 至少保持 `#overview`、`#tenants`、`#plans`、`#audit` 可访问；刷新、前进后退和直接打开必须还原 workspace。
- Support Mode 不是第五个一级导航；它只在租户详情的 Operations context 出现，并在打开目标表面时显示明确的支持态 banner。

### 5.2 布局和 Brand 约束

- 页面使用 PWE 的 Family Navy `#0E1729`、Warm Paper `#F7F5F2`、Accessible Amber `#A16207` 和既有 console tokens；不要引入新的冷灰或独立蓝紫体系。
- 间距只使用既有 Fibonacci 梯度 `5/8/13/21/34/55/89`；表单、按钮和表格行沿用 44px 最小触控目标。
- 黄金分割只用于“真正的主/次关系”：Today 的 attention queue 与 secondary business health 可以使用 `61.8fr 38.2fr`；租户表格列、套餐额度和审计列是同级数据，不强行黄金分割。
- 桌面建议内容最大宽度约 1424px，左右 padding 在 1280px 时使用 34px 级别；不要用留白掩盖低信息密度，也不要让表格撑破工作区。
- 1024px 以下收起 golden split；768px 以下列表改为卡片/详情 full-screen；390px 必须保证 header、导航、筛选、详情 tab 和底部操作都可发现。
- 所有锚点目标设置与 sticky header 等高的 `scroll-margin-top`；这是本轮必须验证的几何规则。
- 对话框只用于短确认和短表单；租户详情、编辑和审计详情优先 drawer/full-screen workspace。弹窗必须有可靠的 `aria-labelledby`、焦点回收、内部滚动和 footer 安全区。

### 5.3 文案规则

| 当前文案 | 建议 | 原因 |
|---|---|---|
| Payment issue / 付款异常 | Subscription past due / 订阅已逾期 | 当前没有在线支付失败事实 |
| Needs setup | Setup incomplete / 设置未完成 | 更准确地说明下一步 |
| Open CMS / 打开 CMS | Open CMS with Support Mode / 通过支持模式打开 CMS | 明确权限边界 |
| Audit Logs | Audit trail / 审计记录（可保留既有名称） | 强化治理语义，但不强制改 API 名称 |

业务数据（套餐代码、工作室名、行业名称）不得被 i18n 脚本误翻译；界面标签、状态、帮助和错误必须有中英文 key。

## 6. P0 / P1 / P2 handoff

### P0 — 进入实现前必须锁定

1. **IA shell：** 四个一级工作区变为单一 active workspace，保留 hash/deep-link 合同；当前 section 不再只是长页滚动目标。
2. **Sticky/anchor geometry：** 修复四个工作区的遮挡；桌面、1024、390 均验证标题、主要动作和第一条内容在 header 下方完整可见。
3. **Action hierarchy：** View 为默认路径；More 只承载管理/危险动作；CMS/Admin 必须显式标注 Support Mode；不把高风险操作放在普通打开动作同层。
4. **安全状态：** Support Mode reason 必填且有字段级反馈；进入、失败、退出都可理解且保持审计边界；不改变后端 RBAC。
5. **支付边界：** 不实现在线支付、银行转账设置、付款凭证、Gmail/SMTP、AWS SES；`past_due` 文案不得暗示已接入支付网关。

### P1 — 核心工作区可用性

1. Today 增加持久化的更新时间、partial 状态和待处理对象入口；保留 KPI→Tenants 筛选链路。
2. Tenants 改为工作室列表 + detail drawer/full-screen；把订阅、用量、联系人、Operations 分组；移动端不依赖 tab 截断。
3. 补齐列表/表单/Support/刷新失败的 loading、empty、error、retry、submitting、success 状态；错误不能只存在于短 toast。
4. Plans 增加字段级校验和删除前依赖/使用情况提示；保持 publication state 与支付逻辑解耦。
5. Audit 增加 row detail drawer、操作者/支持会话上下文；筛选至少支持 action、tenant、resource type 或时间范围中的高价值组合。
6. 中英文动态文案、状态文案、移动端 390/768/1024/1440 逐断点回归；所有新按钮保留 44px 触控目标和键盘路径。

### P2 — 运营效率与后续演进

1. 保存筛选视图、排序/列偏好、批量低风险操作。
2. 审计导出、时间范围、事件详情前后值对比。
3. 顶部轻量 system health/backup freshness 状态；不在本轮把它扩成独立运维系统。
4. 支持会话剩余时间、最近支持租户和一键安全退出。
5. 当平台规模需要时，再评估真正的事件推送；当前不为重构引入 SSE、WebSocket 或浏览器 Push。

## 7. 实施顺序与验收门

### Checkpoint A — 文档与测试合同

- 提交本审计文档与 handoff 更新。
- 新增静态 IA/state contract 测试，先锁定四工作区、hash、权限文案、无支付范围、i18n key 和响应式结构。
- `git diff --check`、现有 platform console tests、inline script parse tests 通过。

### Checkpoint B — P0 shell

- 完成 active workspace、anchor offset、全局 header/nav 和 action hierarchy。
- 先不改变 API，不迁移数据，不改变认证和 Support Mode 后端合同。
- 通过桌面、平板、手机截图和键盘回归。

### Checkpoint C — P1 workspace states

- 按状态矩阵逐项实现 Today、Tenants detail、Plans、Audit 的加载/空/错误/提交/成功状态。
- 每个高风险操作记录 audit evidence；不提交真实生产变更作为视觉验收手段。

### Checkpoint D — Release handoff

- 更新 `VERSION`、Release Notes、用户/管理员指南和最新 handoff。
- 清洁构建 SaaS/Edition 包，保留未跟踪 `docs/sales/` 路演资料，不纳入提交和发布包。
- 完成本地完整门禁、生产部署、deep health、路由、双语和公网浏览器验收后，才可以声称版本完成。

## 8. 验收清单

- [x] `/platform-admin#overview|tenants|plans|audit` 直接打开正确工作区，不出现上一工作区视觉内容。
- [x] sticky header 不遮挡任何工作区标题、筛选栏、主要动作或首条数据。
- [x] Today 的 KPI 与后端字段定义一致；MRR 不可点击为租户筛选；past_due 不写成支付网关失败。
- [x] Tenants 筛选、无结果、清除筛选、分页、View、More、Support Mode 和外部表面路径可解释。
- [x] Support Mode 空原因不会提交；403/网络失败可重试；成功后目标表面能识别支持态和审计原因。
- [x] Tenant detail 在 390px 不出现不可发现的横向 tab 截断；编辑 footer、关闭、dirty/error 状态可操作。
- [x] Plans 的新增、编辑、公开状态、推荐状态、空表单错误、删除依赖提示均可见。
- [x] Audit 的搜索、无匹配、分页、detail drawer 和操作者/支持会话上下文可见。
- [x] 中文和英文动态标签完整；业务数据不被错误翻译。
- [x] 390/768/1024/1440 通过布局、键盘、焦点、44px 触控目标、无页面级横向溢出验收。
- [x] 现有 RBAC、租户隔离、API 合同、生产部署和未跟踪销售资料边界不被破坏。

P2 仍未纳入本版本：保存筛选视图、排序/列偏好、审计导出/前后值对比、系统健康/备份 freshness 面板和真正的事件推送。
