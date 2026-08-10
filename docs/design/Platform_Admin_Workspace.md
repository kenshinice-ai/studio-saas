# Platform Admin 三栏工作台 · 方案评审与修订（对照 v8.10.3）

评的是那张渲染稿和它附带的 P0/P1/P2。**方向我同意**，但在动工之前有一批东西必须先改，否则会照着一个不存在的产品建外壳。

你已经自己抓到一个（`Payment failed` → `Subscription past due`）。**同一类问题还有九个。**

---

## 一、先对账：渲染稿里有多少是真的

逐项拿代码核过（`api_v1.py` 的 `/admin/*`、`schema_v1.sql`、`tenant_usage`）：

| 渲染稿元素 | 真实性 | 依据 |
|---|---|---|
| Total / Active Tenants | ✅ | `/admin/usage` → `tenants`、`paid_tenants` |
| MRR **(USD)** | ⚠️ **币种错** | 字段是 `mrr_aud`，全系统计价都是 AUD（`monthly_price_aud`、setup fee AUD 299–999） |
| Storage Used **1.24 TB / 62% of 2 TB** | ⚠️ **分母虚构** | `storage_used_mb` 是真的；但**平台级总配额不存在**，配额只按租户（`plans.storage_limit_mb`） |
| System Status Healthy | ⚠️ 无来源 | 有 `/v1/health?deep=1`，渲染稿没说取自哪 |
| **Payment failed** | ❌ **你已指出** | 无在线支付。真实字段是 `past_due_tenants` |
| Usage limit reached | ✅ | `tenant_usage` vs `plans.*_limit` 可算 |
| **Invitation pending / 5 invitations** | ❌ **邀请系统不存在** | 全库 `invitation` 命中 **0**。只有 `password-setup-link`（发一次性设密链接），是另一回事 |
| Plan expiring soon | ⚠️ **语义错** | 真实字段是 `trials_ending_7d` —— **试用到期**，不是「套餐到期」。订阅到期是另一组日期 |
| 左栏 **Announcements 公告** | ❌ 不存在 | 命中 0 |
| 左栏 **Tenant Groups 分组管理** | ❌ 不存在 | 命中 0 |
| 左栏 **Invitations 邀请管理** | ❌ 不存在 | 命中 0 |
| 左栏 **Invoices 发票管理** | ❌ 不存在 | 命中 0。结算是**手动**的（`/admin/subscriptions/settlement`），刻意如此（自动化=商业决策） |
| 右栏 **Bandwidth 412 GB / 1 TB** | ❌ **完全虚构** | 全库唯一命中是 `video_embed.py` 里一句注释「zero bandwidth served」。**系统不测带宽** |
| 右栏 **Projects 18 / 50** | ❌ **完全虚构** | 命中全是行业预设文案里编程班的「项目」一词，不是平台指标 |
| **Impersonate login 以租户身份登录** | ❌ **概念错，且危险** | 无 impersonate。有的是 `support-session` —— **带审计、有原因、进出留痕**的支持模式，两者不是一回事 |
| Reset tenant admin password | ⚠️ 措辞错 | 实际是**发一条设密链接**，平台方看不到也设不了密码 |
| Pause / Delete tenant | ✅ | `/status` PATCH、`archive`、`permanent` |

**六个导航项里四个指向不存在的功能；右栏三条用量里两条是虚构指标。**

> 这不是渲染稿的错 —— 它本来就是视觉方向稿。但**如果照它建 shell，你要么发一批点不动的死导航，要么被迫承诺去做四个从没排期的子系统**（邀请、公告、分组、发票）。

### 右栏用量条：真实的是四条，不是三条

`tenant_usage` 只记 `student_count` / `user_count` / `storage_used_mb`；配额侧有 `student_limit` / `user_limit` / `storage_limit_mb`，v8.7.0 起还有 `showcase_limit`。

所以 Inspector 应该显示：**学员 · 员工 · 存储 · 作品发布上限**（四条真的），而不是 Storage / Bandwidth / Projects（一真两假）。

`showcase_limit` 尤其值得放进去 —— **它是套餐差异化的卖点**（15/60/150），而平台方目前在任何界面上都看不到某个租户用了多少。

---

## 二、三栏 shell 这个方向，我同意；但有两个前提

### 前提 1：先想清楚它是为多少租户设计的

渲染稿画的是 **128 个租户**。**线上真实数字是 6。**

三栏 + 常驻 Inspector 是**高频分诊**的形态 —— 它省的是「点进详情、看一眼、退回列表」的往返，只有当你一小时要看几十个租户时才划算。6 个租户时，右栏那 380px 更多是在占地方。

**这不是叫你别做。** 是两件事：

1. **按增长做，但别为增长牺牲当下**：Inspector 默认**折叠**，选中租户时展开；宽屏（≥1440px）才默认展开。你的 P2 里「Inspector 固定/取消固定」应该提到 **P0** —— 它不是锦上添花，它是让这套 shell 在 6 个租户时也不别扭的那个开关。
2. **P2 的「多选比较」「批量操作」现在没有需求**。6 个租户不需要批量。建议把它们从路线图上**摘掉**，等真到 50+ 再说 —— 现在写进 P2 只会变成永远排不上的技术债。

### 前提 2：Inspector 会换目标，破坏性操作不能跟着换

**这是我对这张稿子最要紧的一条意见。**

渲染稿把 **Support Mode 开关**和 **Reset password / Pause tenant / Delete tenant** 放在同一张红框卡片里，而这张卡片在右栏 —— **右栏是「选中什么就显示什么」的**。

于是有这样一条路径：

> 为租户 A 打开 Support Mode → 中栏点了另一行 / 键盘换了选中项 → **右栏静默换成租户 B，Delete tenant 现在指向 B**，而红框、开关、按钮位置一模一样。

**一个会自己换目标的删除按钮，是这套布局特有的新风险 —— 旧的单页控制台没有这个问题。**

三条修正，建议全部进 P0：

- **选中项变化时，Support Mode 一律关闭**，并给一句可见提示（「已切换到 X，支持模式已关闭」）。开着的支持模式属于**一次会话**，不属于面板。
- **破坏性操作不放 Inspector**。Inspector 只放「看」和低风险动作（查看详情、管理订阅、调配额）。Pause / Delete / 发设密链接**走确认对话框**，对话框**标题里带租户名和 slug**，让它自己说清楚打算对谁动手。
- **确认框要求键入 slug**（Delete 已经该这样）。名字可以看错，slug 是唯一的。

### 顺带：`Impersonate login` 这个词不能用

代码里没有 impersonate，有的是 **support session**：要填原因、进出都写 `support.session_started` / `support.session_ended`、**租户 Owner 在自己的审计面板里看得见**。

「以租户身份登录」听起来像悄悄变成对方 —— 而这个产品刻意选择了相反的设计。文案应为 **`Start support session / 开始支持会话`**，并在按钮下方注明「需要填写原因，租户可见」。

---

## 三、关于双语标签

渲染稿里每个标签都是「Attention Queue 关注队列」这样中英并列 —— **但右上角同时还有 EN/中文 切换器**，而 `super-admin.html` 现在就有语言切换（`studiosaas_admin_language`，与 CMS、Studio Admin 共用一个键）。

两者是矛盾的：**有了切换器，并列就是把每个标签的视觉长度翻倍**，而这是全产品密度最高的一屏。

建议：**导航与标签跟随切换器**（单语），**只有破坏性操作的确认文案保持双语**——那是唯一「读错了代价很大、值得占两倍宽度」的地方。

---

## 四、修订后的 P0 / P1 / P2

### P0（外壳与安全边界）

1. **三栏 shell**：顶部全局栏（身份 / 语言 / 刷新 / 支持模式状态）· 左栏工作区导航 · 中栏主内容 · 右栏 Inspector
2. **中栏与右栏各自独立滚动**，顶部栏不滚
3. **Inspector 的开 / 关 / 返回 / 焦点恢复**：关闭后焦点回到触发它的那一行（不是回到 body）
4. ⭐ **Inspector 可折叠 / 固定**，`<1440px` 默认折叠 —— 从 P2 提上来
5. ⭐ **选中项变化即关闭 Support Mode**，并提示
6. ⭐ **破坏性操作移出 Inspector**，改为带租户名 + slug 的确认对话框；删除要求键入 slug
7. **保留现有 hash 深链、权限与 Support Mode 边界**（现有 `location.hash = 'tenants'` 那套要继续可用，且 Inspector 的选中项也要进 hash，否则右栏刷新即丢）
8. ⭐ **左栏只放真实存在的工作区**：Overview · Attention · Tenants · Plans · Subscriptions · Usage · Audit · Security。**删掉 Announcements / Tenant Groups / Invitations / Invoices**

### P1（内容与状态）

1. Today / Tenants / Plans / Audit 分别接入 Inspector
2. 统一 loading / empty / partial / error / retry / success
   - ⭐ 补一条渲染稿没有的：**partial** —— `/admin/usage` 是一条大 SQL，某个子查询慢或失败时，**已拿到的数字要照常显示，拿不到的那格单独标注**，不能整块转圈
3. 中英文 · 键盘 · 焦点 · 移动端 sheet 验收
4. 复杂编辑仍进完整 workspace，不把长表单塞右栏
5. ⭐ **Attention Queue 的行 → Inspector 的映射要先定**：渲染稿的行是「3 个租户付款失败」，**而 Inspector 一次只装一个租户**。建议：多租户告警点击后进入**中栏的筛选列表**（而不是右栏），单租户告警才直接填 Inspector
6. ⭐ **Inspector 用量条改成四条真的**：学员 / 员工 / 存储 / 作品发布上限

### P2（真到了那个规模再说）

1. 保存筛选视图
2. 审计事件前后值对比 —— **建议提到 P1**：`/admin/audit-logs` 已有 metadata，这是平台方复核退款和配额调整时最想要的东西，成本也低
3. 系统健康与备份 freshness —— **建议提到 P1**：数据已经在 `/v1/health?deep=1`（含 `themes.unreadable`、磁盘），把它接上比新建任何东西都便宜，而且它是**唯一能提前发现故障**的一格
4. ~~多选比较租户或套餐~~ —— **摘掉**，6 个租户没有这个问题
5. ~~批量低风险操作~~ —— **摘掉**，同上

---

## 五、必须改的文案（含中英）

| 渲染稿 | 改成 | 为什么 |
|---|---|---|
| `Payment failed / 付款失败` | **`Subscription past due / 订阅已逾期`** | 无在线支付，不能暗示接了支付系统（你已指出） |
| `MRR (USD)` | **`MRR (AUD)`** | 全系统计价是 AUD |
| `Storage Used · 62% of 2 TB` | **`Storage used / 存储用量`**，只给绝对值 + 环比 | 平台级总配额不存在，别造一个分母 |
| `Plan expiring soon / 套餐即将到期` | **`Trials ending / 试用即将结束`** | 字段是 `trials_ending_7d`，说的是试用 |
| `Impersonate login / 以租户身份登录` | **`Start support session / 开始支持会话`** | 不是冒名登录；要填原因、租户可见 |
| `Reset tenant admin password / 重置管理员密码` | **`Send password setup link / 发送设密链接`** | 平台方设不了也看不到密码 |
| `Bandwidth` · `Projects` | **删除** | 不存在的指标 |

---

## 六、验收标准（可执行的那种）

外壳做完之后，这几条要能当场演示：

1. **键盘**：`Tab` 能从中栏进入 Inspector；`Esc` 关闭 Inspector 且焦点回到原来那一行
2. **深链**：带 Inspector 选中项的 URL 复制到新标签页打开，**右栏是同一个租户**
3. **换目标即解除武装**：打开 Support Mode，切换选中租户，**Support Mode 必须已关闭**并有提示
4. **破坏性操作说清对象**：删除确认框里能读到租户名 + slug，且要求键入 slug
5. **partial**：把 `/admin/usage` 的某一个子查询做成超时，**其余数字照常显示**
6. **移动端**：≤768px 时 Inspector 变 sheet，背后中栏不滚动
7. **无虚构数据**：全屏搜索 `Bandwidth`、`Projects`、`Invoice`、`Invitation` —— **零命中**

---

## 附：来源说明

上面「渲染稿 vs 真实」的每一行都对过 `backend/studiosaas/api_v1.py`、`backend/db/schema_v1.sql` 与 `tenant_usage`，不是印象。

布局与交互建议来自代码事实 + 通用可用性规则（深链、焦点可见、空状态）。我查过 `ui-ux-pro-max` 的规则库，**「三栏 inspector 控制台」这个具体形态在库里没有匹配条目**（返回 0 条）—— 所以第二、四节的判断是我的，不是数据库给的，据此取舍。
