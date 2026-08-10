# Platform Admin 三栏工作台交互合同

版本：v1.0（设计冻结候选）
日期：2026-08-10
适用版本：PWE Studio v9.7.0 及后续 Platform Admin 重构
状态：只读设计 handoff；本文件不授权本轮修改代码

## 1. 合同目的

本合同把 Platform Admin 从“几个可切换的工作区”进一步收敛成一套可复用的工作台交互模型：

> 左边找地方，中间做事情，右边做判断。

它借鉴 Studio Admin 的外壳关系，但不复制租户品牌编辑器的业务导航。Platform Admin 仍然是平台级商业、租户和审计控制面；认证、RBAC、Support Mode 审计边界和已有 API 不因视觉重构改变。

## 2. 当前真相与边界

| 项目 | 已确认事实 | 本合同的处理 |
|---|---|---|
| 当前版本 | `VERSION=9.7.0`，生产已部署 | 设计稿以 v9.7.0 现有行为为基线 |
| 当前入口 | `/platform-admin`，`/super-admin` 为兼容入口 | 保留入口，不新增认证入口 |
| 当前工作区 | Overview、Tenants、Plans、Audit Logs | 视觉名称收敛为 Today、Tenants、Plans & Pricing、Audit Logs；保留 `#overview` 兼容深链 |
| 已有能力 | usage、plans、tenants、audit logs、subscription settlement、Support Mode | 只把已有数据与动作放进 Inspector；不凭空增加数据字段 |
| 支付范围 | 未接入在线支付、银行转账、付款凭证 | `past_due` 只表达订阅生命周期；不使用 Payment failed |
| 已有实现 | active workspace、刷新状态、Tenant detail、Audit detail、Support Mode 字段校验、Plans 字段校验 | 作为下一版三栏布局的行为基础，不推翻重做 |
| 未跟踪文件 | `docs/sales/` 路演资料属于用户现有文件 | 不纳入本设计提交或后续发布包 |

## 3. 冻结后的信息架构

### 3.1 顶部全局栏

顶部只承载跨工作区的全局控制，不重复左侧工作区导航：

```text
PWE Studio · Platform Admin      [当前版本/刷新状态] [中文 | English] [Refresh] [Account]
```

保留：品牌、当前产品面、语言、Refresh、账号。
暂不加入：公告、系统设置、Security、独立 Help 中心、租户级快捷动作。

### 3.2 左侧工作区导航

左侧是“找地方”的稳定目录，一级入口控制在当前真实能力范围内：

```text
MAIN / 主要
  Today / 工作台
  Needs attention · N       ← Today 内的快捷定位，不是独立工作区

CUSTOMERS / 客户
  Tenants / 工作室

COMMERCIAL / 商业
  Plans & Pricing / 套餐与定价

OPERATIONS / 运营
  Audit Logs / 审计日志
```

以下项目暂不进入一级导航：Groups、Invitations、Announcements、System Health、Security、Settings、Billing Records。只有当对应数据、权限、空态、错误态和写操作合同完整后，才可以新增导航入口。

`Admin Actions` 并列入 Audit Logs 的筛选或事件类型，不再形成重复的一级页面。`Subscription settlement` 作为 Plans 或 Tenant Inspector 的二级内容；除非形成独立的筛选、详情、写操作和权限合同，否则不增加一级入口。

### 3.3 中间工作区

中间是“做事情”的主区域，承担筛选、列表、表格、表单和工作流结果：

```text
工作区标题 + 当前数据状态/最后刷新时间
主任务模块
次级概览或活动
工作流分页/筛选/恢复动作
```

中间区域不放长篇设置，也不把危险操作与普通列表动作混在同一层。

### 3.4 右侧 Inspector

右侧是“做判断”的上下文面板。它不是普通弹窗，也不是随机展示一个租户：

```text
无选中对象：Workspace context / 工作区上下文
选中租户：Tenant Inspector / 租户详情
选中套餐：Plan Inspector / 套餐详情
选中审计事件：Audit Inspector / 审计详情
```

选中状态必须来自用户当前点击的 Attention item、租户行、套餐行或审计行；初始页面不得展示无法解释来源的默认租户。

## 4. Inspector 内容合同

### 4.1 固定顺序

所有 Inspector 按以下顺序组织：

```text
1. 对象身份与生命周期状态
2. 当前异常/风险
3. Subscription / 套餐与订阅
4. Resource usage / 已有用量字段
5. Safe actions / 普通安全操作
6. Support Mode / 高风险支持操作
```

### 4.2 数据字段边界

只显示当前 API 能提供且有清晰定义的字段：

- 租户名称、slug、状态、负责人
- 套餐、订阅状态、续期日期（如已有）
- 学员数、用户数、存储用量及套餐限制（如已有）
- 审计时间、操作者、资源、metadata

不得在没有数据来源时展示 bandwidth、projects、invoices、payment failed 等字段或文案。

### 4.3 动作分层

```text
Safe actions
  View tenant details
  Open tenant workspace
  View audit history

Managed actions
  Edit tenant
  Manage subscription
  Adjust supported limits

Support Mode
  Enter Support Mode → 填写 reason → 二次确认 → 写入审计
```

Support Mode 不使用看起来可以即时生效的普通 Toggle。未填写 reason 时不提交、不创建半授权状态；成功后明确显示 session scope、审计原因和退出入口。

### 4.4 Pinned Inspector

`Pinned Inspector` 作为 P2 扩展保留设计槽位，但 v1 不要求实现固定、对比或跨页面保留租户。v1 只要求 Inspector 可打开、关闭、返回，并在关闭后恢复中间区域原有焦点。

## 5. 路由与状态合同

### 5.1 深链

新视觉名称不改变既有深链合同：

```text
#overview  → Today（兼容旧链接）
#tenants   → Tenants
#plans     → Plans & Pricing
#audit     → Audit Logs
```

选中上下文的 URL 参数只有在下一阶段确定字段命名后才加入；不得用不可恢复的纯内存状态替代浏览器前进/后退。

### 5.2 工作区状态

| 状态 | 中间区域 | Inspector |
|---|---|---|
| `not-refreshed` | 显示首次进入提示 | Workspace context |
| `loading` | 保留上次成功内容，局部 loading | 对应对象 loading，不展示旧对象冒充新对象 |
| `ready` | 正常列表/卡片/表单 | 当前上下文可操作 |
| `empty` | 区分无数据与无匹配，提供恢复入口 | 说明下一步，不显示空白面板 |
| `partial` | 失败模块保留在原位置并标记 | 显示失败来源、最后成功时间、Retry |
| `error` | 保留工作区标题和安全上下文 | 说明恢复方式，不伪装成 empty |
| `confirming` | 当前对象仍可识别 | 危险动作单独确认 |
| `submitting` | 锁定相关输入，保留用户内容 | 禁止重复提交，显示进行中 |
| `success` | 列表/状态刷新，保留定位 | 显示结果与下一步 |
| `mobile-sheet` | 中间区域全宽 | Inspector 变为可关闭的全屏 sheet |

## 6. 布局与品牌合同

### 6.1 桌面比例

```text
Top bar: 64px 左右
Left rail: 220–236px
Center : Inspector ≈ 1.618 : 0.618
间距：8 / 13 / 21 / 34px
控件最小目标：44px
```

左 rail 固定宽度；黄金分割只用于中间阅读区与右侧上下文区，不用于每个卡片、表格列或按钮。

### 6.2 Brand

- 继续使用 Family Navy、Warm Paper、Accessible Amber 与现有 console tokens。
- 状态颜色必须同时有文字和图标，不依赖颜色单独表达风险。
- `past_due` 使用订阅生命周期文案：`Subscription past due / 订阅已逾期`。
- 使用现有 SVG 图标，不用 emoji 替代操作图标。
- 保留可见 focus ring、44px 触控目标、4.5:1 文本对比度。

### 6.3 响应式

| 视口 | 结构 |
|---|---|
| `≥1280px` | 顶部栏 + 左 rail + 中间 workspace + 右 Inspector |
| `1024–1279px` | 左 rail 保留，Inspector 可折叠 |
| `768–1023px` | Inspector 转右侧 drawer |
| `<768px` | 左 rail 转导航抽屉，Inspector 转 full-screen sheet |
| `390px` | 禁止页面级横向滚动；关键动作、关闭、返回和错误均可发现 |

## 7. P0 / P1 / P2 冻结边界

### P0：工作台骨架

1. 三栏 shell 与四个真实工作区。
2. 顶部、左 rail、中间、Inspector 的职责分离。
3. Today 默认无随机租户，Inspector 由真实选中事件驱动。
4. Inspector 打开、关闭、返回、焦点恢复和移动端 sheet。
5. 保留 Hash 深链、RBAC、租户隔离、Support Mode 审计边界。

### P1：标准化工作流

1. Today、Tenants、Plans、Audit 复用 Inspector 模板。
2. 统一 loading、empty、partial、error、retry、confirming、submitting、success。
3. Tenants 先完成 Tenant Inspector，再扩展复杂编辑 workspace。
4. Support Mode 使用 reason 流程，不使用普通 Toggle。
5. 完成中英文、键盘、焦点、390/768/1024/1280/1440 验收。

### P2：运营效率扩展

1. Pinned Inspector、固定租户和租户比较。
2. 保存筛选视图、排序、列偏好和批量低风险操作。
3. 审计导出、时间范围和前后值对比。
4. Groups、Invitations、Announcements、System Health、Security、Settings 等新能力。

## 8. 设计冻结判定

本合同冻结后，后续逐屏设计不得改变以下原则，除非重新开一个决策记录：

- 不恢复“所有工作区继续堆在一个长页面”的信息结构。
- 不把 Attention 变成没有独立数据合同的第二套 Dashboard。
- 不把 Support Mode 做成无 reason 的开关。
- 不把未接入的数据字段、支付状态或未来页面伪装成当前功能。
- 不把右侧 Inspector 变成长表单垃圾桶。

## 9. 下一阶段输入

下一阶段以本合同为唯一交互基础，按以下顺序完成逐屏设计：

1. Today + Needs attention + Workspace context
2. Tenants + Tenant Inspector + Support Mode
3. Plans & Pricing + Plan Inspector
4. Audit Logs + Audit Inspector
5. Login、全局刷新、partial/error、移动端 sheet 和键盘路径

每一屏必须输出桌面、平板、移动三套结构图，以及 loading、empty、error、selected、submitting 五类状态，不进入代码实现。
