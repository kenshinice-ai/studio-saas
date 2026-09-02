# Platform Admin 逐屏设计 handoff

版本：v1.0
日期：2026-08-10
前置合同：[`Platform_Admin_Workbench_Interaction_Contract_2026-08-10.md`](Platform_Admin_Workbench_Interaction_Contract_2026-08-10.md)
状态：历史设计入口；三栏工作台、Today/Tenants/Plans/Audit 与 Inspector 已在
v9.7.0–v9.8.5 分阶段落地。本文保留逐屏规格，不再表示“尚未实现”。

## 1. 设计目标

本阶段不重新讨论三栏工作台是否成立，而是把冻结的合同落到每一屏：

```text
顶部：全局控制
左侧：工作区定位
中间：当前任务
右侧：上下文判断与下一步
```

所有屏幕共享同一套 shell、Inspector、状态条、焦点和响应式规则。屏幕之间只变化中心内容和 Inspector schema，不重新发明导航。

## 2. Screen 00 — 全局 Shell / 登录后外壳

### 目标

让平台管理员在任何工作区都知道：我在哪里、数据何时刷新、当前账号是谁、右侧上下文是否打开。

### 结构

```text
┌─────────────────────────────────────────────────────────────────────┐
│ PWE Studio · Platform Admin        Refresh · 语言 · Account          │
├───────────────┬──────────────────────────────────┬──────────────────┤
│ Work-area rail │ Workspace header + data state    │ Inspector         │
│                 │ Main task surface               │ Context / detail  │
└───────────────┴──────────────────────────────────┴──────────────────┘
```

### 必须表现

- 当前 workspace 使用 active 状态和 `aria-current`。
- 当前数据状态与最后刷新时间在中心标题附近持久可见。
- Refresh 不清空上一次成功内容。
- 未登录只展示登录壳，不预渲染带租户数据的 Inspector。
- 移动端先打开工作区抽屉，再进入中心内容；页面不横向滚动。

### 不做

- 不在顶部重复 Today、Tenants、Plans、Audit。
- 不在全局栏放租户级操作。

## 3. Screen 01 — Today / 工作台

### 目标

管理员打开后第一眼知道“现在有什么需要处理”，而不是先读一排没有动作的 KPI。

### 中间区域

```text
Today / 工作台                         Ready · Last refreshed
说明：平台运营概览，聚焦需要处理的事项

┌─ Needs attention ──────────────────────────────┐
│ Subscription past due      [Review]             │
│ Usage approaching limit    [Review]             │
│ Trial/setup/dates           [View]               │
└─────────────────────────────────────────────────┘

┌─ Business snapshot ────────────────────────────┐
│ Tenants │ MRR (AUD) │ Paid/Trial │ Storage     │
└─────────────────────────────────────────────────┘

┌─ Recent activity ───────────────────────────────┐
│ time · actor · tenant · action · details         │
└─────────────────────────────────────────────────┘
```

### Inspector 状态

- 初始：`Workspace context`，显示平台刷新状态和空态说明。
- 点击 Subscription past due：切换为对应 `Tenant Inspector`，顶部先显示逾期风险。
- 点击 Usage approaching limit：显示具体租户、已用/上限和查看租户入口。
- 点击 Business snapshot：只导航到相关筛选，不把总计金额伪装成可编辑对象。

### 优先级

1. Subscription past due
2. Usage approaching limit
3. 已有 API 支持的 trial/setup/dates 状态
4. 未来真正接入后再加入 Invitation pending

## 4. Screen 02 — Tenants / 工作室

### 目标

用“筛选 → 选择 → 判断 → 处理”替代当前多入口并列的动作堆叠。

### 中间区域

```text
Tenants / 工作室                         [Create tenant]
[Search] [Status] [Plan] [Industry] [Test data] [Clear]
Active filters · 24 tenants

┌─────────────────────────────────────────────────┐
│ Studio │ Plan │ Status │ Owner │ Usage │ Action │
│ Artify │ Pro  │ Active │ ...   │ ...   │ View   │
│ Pixel  │ ...  │ ...    │ ...   │ ...   │ View   │
└─────────────────────────────────────────────────┘
```

### Inspector 状态

- 未选中：`Tenant context` + 选择提示。
- 选中：Tenant identity → attention → subscription → usage → safe actions → Support Mode。
- 需要复杂编辑：从 Inspector 进入完整 `Edit Tenant` workspace，而不是在右侧无限增长。
- 关闭 Inspector：恢复租户行焦点；浏览器后退可回到原筛选状态。

### 动作层级

```text
View details       默认
Open tenant surface 次级，明确是否需要 Support Mode
Edit tenant        管理动作
Archive/Delete     Danger Zone，独立确认
```

## 5. Screen 03 — Tenant Inspector / 租户详情

这是 Tenants 和 Today 共用的标准模板，不是独立一级导航。

### 结构顺序

```text
Tenant identity + lifecycle state
↓
Current attention / risk
↓
Subscription
↓
Resource usage（只显示已有字段）
↓
Safe actions
↓
Support Mode（reason + audited）
```

### 支持的状态

- `loading`：保留租户标题，但不显示旧租户详情。
- `ready`：显示完整摘要和下一步动作。
- `partial`：单个区域显示 unavailable + Retry，其余区域可读。
- `error`：说明失败来源，保留关闭和返回。
- `support-confirming`：reason 输入、字段错误、确认按钮和取消。
- `support-active`：显示 session scope、reason、退出入口。

### 视觉规则

- 风险卡片在最上方，但不使用大面积高饱和红色。
- Support Mode 使用弱红色边框/浅底，并与普通 Actions 有明显分隔。
- 不使用“支持模式开关”作为即时授权暗示。

## 6. Screen 04 — Plans & Pricing / 套餐与定价

### 目标

让平台管理员比较套餐目录、限制和公开状态；不把它变成支付网关页面。

### 中间区域

```text
Plans & Pricing / 套餐与定价                   [Add plan]
[Published] [Recommended] [Search]

┌─────────────────────────────────────────────────┐
│ Plan │ Monthly │ Students │ Users │ Storage │ State │
│ ...  │ ...     │ ...      │ ...   │ ...     │ ...   │
└─────────────────────────────────────────────────┘
```

### Inspector 状态

- 选中套餐：价格、学生/用户/存储限制、entitlements、Published/Recommended。
- 编辑：复杂表单进入完整 workspace；右侧只显示保存状态和错误摘要。
- 删除：先显示依赖/使用情况，再确认；不能只显示“是否删除”。
- `Subscription settlement` 只有在已有接口能提供独立可读结果时，作为二级视图出现。

### 不做

- 不添加付款方式、支付失败、银行卡、付款凭证或在线支付按钮。
- 不用 `Billing Records` 暗示存在完整发票系统。

## 7. Screen 05 — Audit Logs / 审计日志

### 目标

从“技术日志列表”升级为“谁在何时以什么身份对什么对象做了什么”。

### 中间区域

```text
Audit Logs / 审计日志
[Search] [Action] [Tenant] [Resource type] [Date]

┌─────────────────────────────────────────────────┐
│ Time │ Actor │ Tenant │ Action │ Resource │ View │
└─────────────────────────────────────────────────┘
```

### Inspector 状态

- 选中事件：时间、操作者、租户、action、resource、metadata。
- Support Mode 事件：显示 support session 和 reason 关联。
- 无结果：区分“没有日志”和“当前筛选无匹配”。
- API 失败：显示最后成功时间和 Retry，不伪装成空日志。
- 审计 Inspector 只读，不提供编辑、删除或危险动作。

## 8. 跨屏状态与验收矩阵

| 屏幕 | 默认状态 | 选中状态 | 错误/恢复 | 移动端 |
|---|---|---|---|---|
| Shell | 未刷新/登录壳 | 当前 workspace | session/refresh error | 抽屉导航 |
| Today | Workspace context | Tenant Inspector | partial card + Retry | Inspector sheet |
| Tenants | Tenant context | Tenant Inspector | list retry / filter empty | 列表卡片 |
| Plans | Plan context | Plan Inspector | 表单字段错误 | 表单 full-screen |
| Audit | Audit context | Audit Inspector | query retry / no match | 事件卡片 |

每一屏至少绘制：

- Desktop：1440 / 1280
- Tablet：1024 / 768
- Mobile：390
- `loading`、`empty`、`error`、`selected`、`submitting`

## 9. 设计交接产物

下一阶段逐屏设计完成后，必须交接以下内容：

1. 每屏桌面/平板/移动结构图。
2. Center 与 Inspector 的组件边界和字段来源表。
3. 路由、选中对象、Inspector 打开状态和浏览器 back 行为表。
4. Support Mode reason、confirming、active、exit 的状态图。
5. 中英文文案 key、数据字段和不可翻译业务数据表。
6. 键盘、焦点、44px 目标、对比度、无横向滚动验收清单。
7. 明确 P0/P1/P2 以及不纳入本阶段的功能。

## 10. 下一步顺序

```text
1. Today + Needs attention + Workspace context
2. Tenants + Tenant Inspector
3. Support Mode detail flow
4. Plans & Pricing + Plan Inspector
5. Audit Logs + Audit Inspector
6. Login / Refresh / Partial / Error / Mobile sheet
```

本 handoff 结束后才进入视觉细化和代码实现评审；本文件本身不授权修改 `super-admin.html` 或 API。
