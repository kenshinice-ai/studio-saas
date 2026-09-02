# 工作室地址（slug）改名 · 设计方案

> 状态更正：**已在 v9.9.0 实现并发布。** `tenant_slug_aliases`、旧地址永久
> 301、墓碑 410、地址不复用、冷却期和 workspace 重生成均已落地。
> 本文主体保留为设计依据，修复前“没有 UPDATE 路径”的描述属于历史现状。
> 触发场景：Ruby's Studio 已在后台改名为 Mellow Pear Studio，但地址仍是 `/ruby-s-studio`。

---

## 0 · 一句话结论

**可以做，而且比想象的便宜——但绝不能用「原地改一个字段」的做法。**

正确形状是：**slug 只增不改**。旧地址永久保留为别名并 301 到新地址，
新地址成为当前地址。数据库里没有任何东西会因此断裂；真正需要照顾的是**外部世界**——
已经印出去的二维码、发出去的邮件、家长的收藏夹、搜索引擎的索引。

---

## 1 · 现状：slug 今天是「建了就永久固定」

全库检索确认：**没有任何一条代码路径 `UPDATE tenants.slug`。**
Super Admin 的租户编辑接口只改 name / status / plan_code / contact / address / settings。

`super-admin.html:4738` 的界面上已经有这个位置，只是禁用的：

```html
<label for="m_tenantSlug">Slug</label>
<input id="m_tenantSlug" value="…" disabled>
<small>Read-only after creation because it affects URLs, workspace paths, and media paths.</small>
```

> 附带修正：这句说明里「media paths」是**错的**。媒体表是
> `media_assets(tenant_id, storage_key)`，`UNIQUE (tenant_id, storage_key)`，
> 与 slug 无关；`/v1/public/<slug>/media/<id>` 里的 slug 只用于定位租户，asset id 稳定。
> 实现这个功能时顺手把这句改对。

## 2 · 耦合面盘点（做之前必须看的一张表）

| 依赖 slug 的地方 | 性质 | 改名后怎么办 |
|---|---|---|
| `tenants.slug` `NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$')` | 唯一约束，**没有任何外键引用它** | 更新 |
| 其他所有业务表 | 一律 `tenant_id uuid` | **无需改动** |
| `tenants/<slug>/` 目录、`tenant.json` | 磁盘目录名 | 复制 → 提交 → 重渲染 → 延后清理 |
| `settings.workspace_path` | 文本 `tenants/<slug>` | 同事务更新 |
| 路由 `/<slug>`、`/<slug>/{showcase,timetable,register,cms,studio-admin}` | 先查文件系统 | **必须在文件系统查找之前先查别名并 301** |
| `/s/<slug>/v1/...` 路径前缀 | `resolve_tenant()` 查 DB | 别名解析兜住 |
| `X-Tenant-Slug` 请求头 | `resolve_tenant()` 查 DB | 别名解析兜住（开着的后台标签页不会掉线） |
| 子域名 `<slug>.<base>` | 同上 | 同上 |
| `/v1/public/<slug>/media/<id>` | slug 仅用于定位租户 | 别名解析兜住 |
| `localStorage['pwe_lang_' + SLUG]` | 访客语言偏好 | 重置一次，可接受，写进文案 |
| `tenant_archives.tenant_slug` | **历史快照文本列** | **不回填、不重写** |
| `audit_logs` | 历史事实 | 不重写，只追加一条 `tenant.slug_changed` |
| sitemap / canonical / hreflang | 运行时按 slug 生成 | 自动跟随；旧 slug 只出 301，不进 sitemap |
| 已印刷的二维码 / 已发出的邮件 | 外部 | **靠 301 永久兜住——这是整个方案存在的理由** |

**结论：数据库侧几乎没有工作量，风险全在路由与文件系统的时序上。**

---

## 3 · 数据模型

### 3.1 别名表（新增，migration `0031_tenant_slug_aliases.sql`）

```sql
CREATE TABLE IF NOT EXISTS tenant_slug_aliases (
    slug        text PRIMARY KEY CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    tenant_id   uuid REFERENCES tenants(id) ON DELETE SET NULL,
    is_current  boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now(),
    retired_at  timestamptz
);

-- 一个租户在任一时刻只能有一个「当前」slug。
-- 与 class_bookings 的 idx_class_bookings_one_pending_per_phone 同一个惯用法。
CREATE UNIQUE INDEX IF NOT EXISTS idx_tenant_slug_aliases_one_current
    ON tenant_slug_aliases (tenant_id) WHERE is_current;

-- 幂等回填：现有每个租户写入一条 is_current 行。
INSERT INTO tenant_slug_aliases (slug, tenant_id, is_current)
SELECT slug, id, true FROM tenants
ON CONFLICT (slug) DO NOTHING;
```

三个刻意的选择：

- **`slug` 是主键**——这张表是「这个平台上用过的每一个地址」的唯一注册表。
  新 slug 的唯一性检查只查这一张表，不必同时查两处。
- **`ON DELETE SET NULL`，不是 CASCADE / RESTRICT。** 租户被删除后，那一行留下来当墓碑，
  **slug 永不回收**。CASCADE 会把地址放回池子，下一个工作室拿到它就会继承上一家的二维码流量——
  那是个安全问题，不是整洁问题。RESTRICT 则会挡住既有的租户删除路径（`api_v1.py:7936` 的补偿删除）。
- **`retired_at` 只是记录**，判断当前与否一律看 `is_current`。

### 3.2 冷却字段（同一个 migration）

```sql
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS slug_changed_at timestamptz;
```

`NULL` = 从未改过。回填时**不要**填 `created_at`——那会让所有存量租户从今天起被锁一年。

---

## 4 · 解析与跳转

### 4.1 `resolve_tenant()`（`tenant_context.py`）

```
1. SELECT id, slug, status FROM tenants WHERE slug = %s
   命中 → 照旧返回（热路径，行为完全不变）
2. 未命中 → SELECT tenant_id, is_current FROM tenant_slug_aliases WHERE slug = %s
   - tenant_id IS NULL       → TenantGone（HTTP 410，与既有的 410 处理统一）
   - is_current = false      → 解析成功，并在 TenantContext 上带 canonical_slug
   - 无此行                  → 照旧 TenantResolutionError（404）
```

`TenantContext` 增加一个 `canonical_slug` 字段（等于当前 slug）。
**API 请求不做 301**——带旧 `X-Tenant-Slug` 的后台标签页应当继续正常工作，
一个 301 会连带影响它的 CSRF `Origin` 校验。API 只是「认得旧名字」。

### 4.2 页面路由（`server.py`）

这是整个方案里唯一容易做错的地方。

`serve_tenant_home()` 现在的顺序是：`validate_tenant_slug` → **看 `tenants/<slug>/index.html` 是否存在** → 返回文件。

改名之后旧目录会在磁盘上短暂共存（见 §5），如果保持这个顺序，
`/ruby-s-studio` 会**直接把旧文件发出去**，301 永远不触发。

所以必须插在最前面：

```
/<slug> 与 /<slug>/<page> 的每一个入口：
  1. 先查别名：slug 是一个 is_current=false 的别名？
     → 301 到 /<canonical_slug>/<同样的 path>，**保留 query string**
     → 是墓碑（tenant_id IS NULL）？ → 410
  2. 再走现有的文件系统逻辑
```

**301 不是 302。** 只有 301 会把搜索引擎累积的权重迁到新地址；
302 会让旧地址一直留在索引里，等于永远改不完。

---

## 5 · 改名事务：文件系统与数据库的时序

文件系统和 Postgres 无法放进同一个事务。所以顺序要排成
**「每一个失败点都是安全的」**，而不是「尽量不失败」。

| # | 动作 | 失败时的状态 |
|---|---|---|
| 1 | 校验（见 §6） | 什么都没动 |
| 2 | **复制** `tenants/<old>/` → `tenants/<new>/`（不是 move） | 删掉新目录；旧站完好 |
| 3 | 单个 DB 事务：`UPDATE tenants SET slug, slug_changed_at, settings.workspace_path`；旧别名 `is_current=false, retired_at=now()`；插入新别名 `is_current=true`；写 `audit_logs` 一条 `tenant.slug_changed` | 提交失败 → 删掉新目录；旧站完好 |
| 4 | 用 `ensure_tenant_workspace(root, new_slug, 当前 DB 里的 name)` 重渲染新目录 | 已提交，旧 slug 已 301 到新 slug，新目录内容是第 2 步的拷贝——**站是活的**，只是 `<title>` 暂时还是旧的；重跑第 4 步即可 |
| 5 | 清理旧目录（**延后，不在请求里做**） | 旧目录多留一阵没有任何害处：第 3 步之后它已经不被路由命中 |

第 4 步顺带解决了 [Public_Surface_UX_Audit_v9.8.10.md](Public_Surface_UX_Audit_v9.8.10.md) 的 P0-4：
**改名回写工作区和改地址回写工作区，是同一个动作。** 两件事应当共用一个函数，一起做、一起测。

第 5 步的清理规则：删除 `tenants/<dir>/`，当且仅当 `<dir>` 在别名表里且 `is_current = false`。
放进启动时的 `regenerate_tenant_workspaces.py`，或者一个独立的清理脚本。
**绝不在改名请求里同步删除**——那是整条链上唯一不可逆的一步。

---

## 6 · 校验规则（全部为硬规则，不可绕过）

| # | 规则 | 失败时 |
|---|---|---|
| 1 | 新 slug 匹配 `^[a-z0-9][a-z0-9-]{1,62}$` | 400 `invalid_slug` |
| 2 | 不在 `RESERVED_SLUGS`（复用 `validate_tenant_slug()`） | 400 `reserved_slug` |
| 3 | 不等于**任何**已注册 slug——查 `tenant_slug_aliases` 主键，含墓碑 | 409 `slug_taken` |
| 4 | 新 slug ≠ 旧 slug | 400 `slug_unchanged` |
| 5 | **冷却期**：`slug_changed_at IS NULL` 或 `now() - slug_changed_at >= interval '365 days'` | 409 `slug_change_cooldown`，`details.nextAllowedAt` 给出解锁日期 |
| 6 | 租户状态 ∈ `{trial, onboarding, active, past_due}` | 409 `tenant_not_active` |
| 7 | 双钥确认（见 §7） | 409 `slug_change_confirmation_required` |

**关于冷却期**：一年一次是产品规则，不设 UI 覆盖开关。
需要紧急处理时，平台运维直接改 `slug_changed_at` 即可——
**这是刻意的**：让例外必须离开产品界面，例外就不会变成惯例。

---

## 7 · Platform Admin（Super Admin）界面与确认流程

**只有 Super Admin 能改，店主不能自助。** slug 是对外身份，一次误操作影响所有已发出去的物料。
放在平台侧、走工单，是正确的边界。

### 7.1 复用既有的两套惯例，不发明新的

代码库里已经有两个成熟的确认模式，改名同时用上：

1. **双钥 + 影响预览**（来自套餐变更，`api_v1.py:8028`）
   ```
   缺少 confirmSlugChange 或 tenantNotificationAcknowledged
     → 409 error="slug_change_confirmation_required"
        details = { currentSlug, newSlug, urlsAffected[], nextAllowedAt,
                    keepsWorking[], breaks[] }
   ```
2. **输入 slug 二次确认**（来自租户状态变更，`super-admin.html:5107`）
   对话框里必须原样键入**当前**slug 才能提交。
   > 键入**当前**而不是新的：这一步要确认的是「你知道自己在动哪一个工作室」，
   > 不是「你会不会打字」。

### 7.2 界面

`super-admin.html` 的 Basic 折叠里，`m_tenantSlug` 从 `disabled` 改成只读 + 一个「更改地址」按钮，
打开独立对话框（不要做成随租户表单一起保存的普通字段——它和 name/contact 不是一个量级）。

对话框内容（中英双语，走 `admin-i18n.js`）：

```
更改公开地址 / Change public address

当前   pwestudio.online/ruby-s-studio
新地址 pwestudio.online/[            ]     ← 实时校验 §6 的 1–4 条

仍然有效 / Keeps working
  · 旧地址会永久自动跳转到新地址，已印刷的二维码不需要更换
  · 所有学员、课程、作品、排课、媒体文件完全不受影响
  · 已登录的后台不会掉线

会发生变化 / What changes
  · 搜索引擎需要几周时间把结果换成新地址
  · 访客的语言偏好会重置一次
  · 本工作室在 2027-08-12 之前无法再次更改地址

[ 输入当前地址 ruby-s-studio 以确认 ]
☐ 已通知该工作室
                              [取消]  [更改地址]
```

改名成功后，Studio Admin 顶部常驻一条提示（30 天后自动消失）：

> 你的网站地址已更改为 `pwestudio.online/mellow-pear-studio`。
> 旧地址仍然可用并会自动跳转，印刷品可以不换；新印的请使用新地址。

---

## 8 · 接口

```
PATCH /v1/admin/tenants/<tenant_id>/slug        （super_admin 专属）
  { "slug": "mellow-pear-studio",
    "confirmSlugChange": true,
    "tenantNotificationAcknowledged": true }

200  { "ok": true, "slug": "...", "previousSlug": "...",
       "nextAllowedAt": "Wed, 12 Aug 2027 00:00:00 GMT" }
```

**独立端点，不要塞进 `PATCH /v1/admin/tenants/<id>`。**
理由与 UI 同：它的影响面和 contact_email 不在一个量级，混在一次保存里迟早会被误触。

日期一律 RFC 1123，与全站一致——`slice(0,10)` 会让日期框静默变空。

---

## 9 · 测试清单

| # | 断言 |
|---|---|
| 1 | 旧 slug 的页面路由返回 **301**，Location 指向新 slug，**path 与 query 完整保留** |
| 2 | 旧 slug 命中 301 的判断发生在文件系统查找**之前**（旧目录仍存在时也必须 301） |
| 3 | 旧 slug 的 `X-Tenant-Slug` 与 `/s/<old>/v1/...` 仍能正常调用 API，**不产生 301** |
| 4 | 改名后 `tenants/<new>/tenant.json` 的 `name` 与 `slug` 均等于 DB 当前值 |
| 5 | 改名后 `<title>` 与 `meta description` 是**当前**店名（覆盖 P0-4） |
| 6 | 别名永不回收：拿一个退役 slug 去建新租户 → 409 |
| 7 | 租户被删除后其所有 slug 变墓碑，再次申请 → 409；访问 → **410** |
| 8 | 一年内第二次改名 → 409 `slug_change_cooldown`，`nextAllowedAt` 正确 |
| 9 | 缺任一把钥匙 → 409 `slug_change_confirmation_required`，`details` 完整 |
| 10 | 非 super_admin 调用 → 403 |
| 11 | `tenant_archives.tenant_slug` 与 `audit_logs` **未被重写** |
| 12 | 第 2 步复制成功但第 3 步提交失败 → 新目录被清除，旧站可访问 |
| 13 | 清理只删 `is_current = false` 的目录，不删当前目录 |
| 14 | 学员 / 课程 / 作品 / 排课 / 媒体计数改名前后完全一致 |

第 12 条要用真 Postgres 跑——静态测试看不见一个错误的时序。

---

## 10 · 文档同步

| 文件 | 要写什么 |
|---|---|
| `docs/Database.md` | `tenant_slug_aliases` 表、`tenants.slug_changed_at`、「slug 只增不改」的不变量 |
| `docs/API.md` | `PATCH /v1/admin/tenants/<id>/slug`、7 个错误码、301/410 行为 |
| `docs/Architecture.md` | 别名解析在请求链上的位置（**在文件系统之前**） |
| `docs/guides/Super_Admin_Guide.md` | 操作步骤、一年一次的规则、双钥确认、事后通知工作室 |
| `docs/guides/Studio_Owner_Guide.md` | 「我想换地址怎么办」→ 联系平台；旧地址会永久跳转 |
| `manual.html`（中英同页） | 常见问题加一条：「改了店名，网址会跟着变吗？」 |
| `customer-resources/Release_Notes.html` | 双语发布说明 |
| `super-admin.html:4738` | 把「affects … media paths」这句错的说明改对 |

---

## 11 · 实施顺序

| 步 | 内容 | 可独立发布 |
|---|---|---|
| 1 | migration `0031` + 回填 + `Database.md` | ✓（纯加表，无行为变化） |
| 2 | `resolve_tenant()` 别名解析 + 页面路由 301/410 + 测试 1/2/3/7 | ✓（此时还没有第二个 slug，等于空跑，但把最难的一段先上线并观察） |
| 3 | 改名事务 + 工作区重渲染（**与 P0-4 的改名回写合并做**）+ 测试 4/5/12/13/14 | ✓ |
| 4 | 端点 + 校验 + 冷却 + 双钥 + 测试 6/8/9/10/11 | ✓ |
| 5 | Platform Admin 对话框 + Studio Admin 提示条 + 双语文案 + 文档 | ✓ |

第 2 步先上、且在没有任何别名的情况下先跑一段时间，是这个方案里最值钱的一条安排：
**把「路由顺序」这个唯一会静默出错的地方，放在没有真实流量依赖它的时候上线。**

---

## 12 · 明确不做的事

- **不让店主自助改地址。** 对外身份，平台侧操作。
- **不回收任何 slug。** 包括已删除租户的。
- **不用 302。** 只有 301 迁移搜索权重。
- **不重写历史**：`tenant_archives`、`audit_logs`、已发出的邮件正文，一律保持原样。
- **不做「多个当前地址」。** 一个工作室在任一时刻只有一个正式地址，其余全是跳转。
  部分唯一索引在数据库层面保证这一点，不靠代码自觉。
