# StudioSaaS v7.5.0 项目审计报告（2026-07-27）

> 四个方向并行审计（UI/UX、后端逻辑、数据库/迁移、文档/版本一致性），
> 基线 commit f710bdc（v7.5.0）。全程只读，未改动任何产品文件。
> 结论汇总：**3 HIGH / 13 MED / 20 LOW**；v7.4+ 七条发布不变量全部成立，
> pytest 117 全绿，schema 与 SNAPSHOT_TABLES 两条清单零漂移。

## 0. 核验通过项（一行带过）

- 七条不变量全部 PASS：legacy 410（server.py:629-643）、parent-only 403
  （api_v1.py:8026-8063）、财务边界 fail-closed（:3272-3284、:2770、:6373）、
  CMS save() 布尔契约 21 调用点全检查、legacy-cms/save rev-409+force
  （:4866-4883）、CSRF 头双防线（server.py:167-215）、DB 超时 env 可调
  （db.py:44-46）。
- `backend/tests/` 117 passed；`check_terminology` OK；`check_ui_escaping` OK
  （但见 UI-6 盲区）；`check_inline_scripts` OK。
- schema_v1.sql vs 迁移链 0001–0019：真实 PG18 双库目录级比对 828 条目
  **零语义漂移**；SNAPSHOT_TABLES 覆盖全部 28 张租户表**零遗漏**。
- 13 处 FOR UPDATE 行锁全部核实与文档一致；连接管理无泄漏。
- 版本三处一致 7.5.0；API.md 抽查 8 端点+错误码表逐条吻合；Database.md 覆盖
  0019；Admin_Guide 权限矩阵与 auth.py 零漂移；guides 互链无死链;
  Blueprint 定价全文统一 AUD 299–999,无 799 残留。
- 租户面模板（tenant-template/index.html、register.html）是全项目 a11y 标杆。

## 1. HIGH（3 条,均在 Super/Studio Admin 前端）

| # | 问题 | 证据 |
|---|---|---|
| H1 | 超管**退出登录必抛 TypeError**：清理数组引用 `studentCount` 等 3 个不存在的 id，`$(id).textContent` 第二项即 null 崩溃，租户/审计数据残留隐藏 DOM，"Logged out." 永不显示 | super-admin.html:1541（统计卡实际 id 见 1105-1137） |
| H2 | 状态 pill 对比度：`.pill.active` 2.24:1、`.pill.past_due` 1.93:1（11px 字号要求 4.5:1）；而平台对租户主题强制 4.5:1 才许发布——对租户严、对自己松 | super-admin.html:571-579、23-27；对照 studio-admin.html:3808-3813 |
| H3 | Studio Admin **修改密码失败零反馈**：`changePassword()` 无 try/catch,401 时 unhandled rejection,弹窗不关、无提示,用户可能误以为已改成 | backend/frontend/studio-admin.html:2723-2734；对照 super-admin.html:1573-1575 有完整 catch+toast |

## 2. MED（13 条）

**后端（2）**
- B1 `_is_local_request()` 用可伪造的 **Host 头**判定本地请求，是
  `_repair_local_super_admin_login`（创建/重置平台 super_admin，默认密码在
  仓库内）的最后一道门。flag 误开 + 反代直传 Host 即沦陷。改用
  `remote_addr`（同文件 `_client_ip` :129-146 是正确写法）。
  — api_v1.py:7883-7887、:7904
- B2 auth.py:529 `handle_permission_denied` 用了 `jsonify` 但未导入——
  403 安全网一旦真正触发即 NameError→500。一行导入修复。

**数据库（3）**
- D1 0016 与 schema_v1.sql 保护 UNIQUE 约束的 DO 块捕获类型写错
  （`duplicate_object`，实际抛 `duplicate_table` 42P07），**实测不可重跑**
  （psql exit 3）。补 `WHEN duplicate_table`。
  — 0016_daily_roster_entries.sql:10-16、schema_v1.sql:528-534
- D2 run_migrations.py:57 / prune_event_tables.py:23 复用应用层 connect()，
  继承 30s statement timeout；prune 谓词裸 `created_at` 无索引全表扫——
  大库上最需要清理时最容易超时失败。脚本内 `SET statement_timeout=0`
  或 runbook 写明 env 覆盖。
- D3 media_variants 存在与 UNIQUE 约束逐列相同的重复索引（0019 刚为
  credit_accounts 修过的同类问题，0015 这处漏掉）。可仿 0019 出 0020。
  — 0015:76-77、schema_v1.sql:519-520

**UI/UX（7）**
- U1 三个危险操作确认按钮（租户状态/归档/永久删除）`disabled=true` 后无
  try/finally，API 失败即死锁。— super-admin.html:2081、2153、2184
- U2 "Restore to Draft" 失败静默（无 .catch）。— studio-admin.html:3895-3908
- U3 转义盲区：`check_ui_escaping.py` 扫不到先存变量再进 `openModal()` 的
  模板串；实际漏网 4 处未 esc 插值（super-admin.html:1366、1881、2704;
  studio-admin.html:2772）。当前数据源可信、可利用性低，但检查器给出
  虚假绿灯，建议扩展检查器。
- U4 legacy 面 emoji 残留（v7.5.0 号称清零）：legacy-root/register.html 16 处
  （仍由 `/_legacy/register` 无条件对外，server.py:803-805）；
  shared-portfolio.html:102 `'💬 '`（家长可见公开页）。
- U5 legacy-root/register.html:120 第三方 CDN 兜底（违反 index.html:112 自家
  注释）；:5 `maximum-scale=1.0` 禁缩放（WCAG 1.4.4）。
- U6 shared-portfolio.html 灯箱键盘不可达、无 Escape/焦点管理、整页硬编码
  英文——与门户模板已修复模式直接冲突。— :43、:83-86
- U7 Super Admin 中文态词条缺口（Healthy/Needs setup/Payment issue/
  Onboarding Checklist 等 + 动态串），中英混排。— admin-i18n.js 无对应键

**文档（1）**
- DOC1 六份角色手册"适用版本"仍标 v7.4.1（实为 v7.5.0 交付物）——
  docs/guides/*.md 各 :3，六处系统性漂移。

## 3. LOW（20 条，卫生类，不阻塞发布）

- 后端：/s/<slug>/v1/public/* 不在 CSRF 豁免内（意图不一致）；内存限流器
  无界增长非线程安全（已知 P3-04）；原生 `refund` 类型语义与 `refund_out`
  相反（正 delta+正 fee，污染 cash_net 口径，前端未用）；503 回显 DB 连接
  错误细节。
- 数据库：backup_postgres.py `--keep 0` 删光含新备份；bootstrap 库缺
  schema_migrations 时 backup 直接失败无提示；schema_v1.sql 缺 PG16+ 头部
  标注（:582 用 pg_input_is_valid）；tenant_brand_versions 仅差 DESC 的冗余
  索引（0012:34-35）；0001 被追溯编辑（0018 重叠，建议冻结已应用迁移）；
  db.py env 非法值抛裸 ValueError；归档 users.json 含跨租户用户
  password_hash（建议列裁剪，tenant_archive.py:24）。
- UI：`var(--success)` 未定义（super-admin.html:2316）；死代码
  `checkTenantSurfaceLinks`/`setSurfaceMiniStatus`/`progressBar`/`.btn-success`；
  预览切换钮无 aria-pressed（studio-admin.html:2203）；slug 兜底硬编码真实
  租户（:4042）；触控目标 30-38px 三处；分页行复用 .toolbar 栅格布局怪异
  （:1215）；CSS `content:'✎'` 违反 SVG-only 约定（:516）；legacy register
  动态字段 label 无 for/id。
- 文档：HANDOFF_LATEST 顶部"未提交"过程性残留与末尾"已 push"矛盾
  （本轮已顺手修正）。

## 4. 建议的下一轮（按性价比排序）

1. **一小时内可清完的点修**：H1、H3、B2（各一行~十行）；B1（改
   remote_addr）；U1/U2（try/finally + catch）；DOC1（六处版本号）。
2. **0020 迁移 + 脚本硬化**：D1 异常类型、D3/L 冗余索引、D2 超时与
   prune 索引、backup keep 校验——性质同 v7.4.1 stability pass。
3. **legacy 面对齐 v7.5.0 标准**：U4/U5/U6 集中一批处理（emoji、CDN、
   缩放、分享页 a11y+i18n）。
4. **检查器补盲区**（U3）+ H2 pill 对比度换色。
5. 与既有 roadmap 合并：61 处 raw hex、品牌表单行内报错、media token
   hex 化（本轮确认暴露面已被会话鉴权覆盖，不紧急）。
