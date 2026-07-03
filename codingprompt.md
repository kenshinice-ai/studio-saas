# StudioSaaS Improvement Sprint Prompt (v3)

Version: v3.0
Date: 2026-07-03
Supersedes: codingprompt.md v2（P0-01…P0-07 已全部完成；v2 全文见 git 历史 commit 81ec23f。媒体上传、考勤闭环、注册审核、租户归档、备份脚本已在后续提交中落地）

你接手的是 StudioSaaS 多租户 creative studio SaaS。本文件是**当前开发周期的唯一任务清单**，基于 2026-07-03 晚的全量代码复审（每条任务附证据）。产品与技术规范见 `docs/`，状态跟踪见 `docs/Current_Sprint.md`。

## 工作规则

1. 按 A → B → C 顺序执行；同级内按编号顺序。
2. 每完成一项：跑验证命令，报告【改动文件 / 验证结果 / 风险 / 下一步】，独立 commit（格式 `fix(A2): ...`）。
3. 不做一次性大重写；大文件渐进拆分。
4. schema 变更必须走 `backend/db/migrations/`（已有 0001–0005 + `scripts/run_migrations.py`）。
5. 工作区中历史删除（docs/archive、letspaint-cms-release）是有意的，不要恢复。
6. Pilot 阶段禁止引入：FastAPI 重写、微服务、Redis、ES、ClickHouse、消息队列（见 docs/Architecture.md §7 采纳策略）。

## 验证命令合集

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/studiosaas/services/*.py backend/scripts/*.py
cd backend && ../.venv/bin/python -m pytest -q            # 当前 34 tests
cd backend && ../.venv/bin/python test_cms.py             # 72 checks
cd backend && ../.venv/bin/python test_tenant_isolation.py
# 手动: /super-admin, /<slug>, /<slug>/register, /<slug>/studio-admin, /v1/health
```

---

# A 级 — 正确性 / 安全 / 卫生（先做）

## A1 — 提交在途工作，定生成目录的 git 策略

**问题：** 工作区不干净，在途改动有丢失风险。
**证据：** `super-admin.html` 有 +461/-99 未提交（租户风险评估、测试租户过滤、归档 UI 等成型功能）；`docs/QA_Checklist.md` 已改未提交；`tenants/dance-dance/` 未跟踪。
**修复：**
1. 审查并提交 super-admin.html 与 QA_Checklist.md 的在途改动（分逻辑 commit）。
2. 决策 `tenants/<slug>/` 生成工作区的策略：要么一律跟踪（把 dance-dance 加入），要么整体 gitignore + 文档声明"运行时生成"；两者选一并写入 docs/Architecture.md §3.1。
**验证：** `git status` 干净；决策记入文档。

## A2 — Studio Admin 登录管理补后端（last_login + 密码设置链接）

**问题：** Super Admin 的"租户编辑"弹窗里两个字段是硬编码占位，功能根本不存在。
**证据：** `super-admin.html` Edit 弹窗：`<input value="Not tracked yet" disabled>`（Last Login）、`<input value="Not supported by backend yet" disabled>`（Password Setup Link）；`grep last_login backend/` = 0 处。
**修复：**
1. 迁移 0006：`users.last_login_at timestamptz`；登录成功时更新（standard + legacy-login 两处）。
2. `/v1/admin/tenants/<id>` 响应带 `studio_admin_last_login`；UI 显示真实值。
3. 密码设置链接：一次性 token（复用 share_tokens 模式或新表 `password_setup_tokens`，含 expires_at、used_at），Super Admin 生成 → 复制链接 → 新页面 `/setup-password?token=` 设置密码；token 单次有效、24h 过期、全程审计。
**验证：** 登录后 last_login 更新；setup 链接完整走通且二次使用被拒；pytest 补用例。

## A3 — 学生列表服务端分页与排序

**问题：** 学生列表整表返回，无 LIMIT/OFFSET；growth 计划上限 1500 学生时不可用。
**证据：** `api_v1.py` `list_students()` 只有 `search` 参数；OFFSET 在全文件仅 3 处（都不在 students）；studio-admin 前端一次性渲染全部行。
**修复：** `GET /v1/students?search=&status=&page=&per_page=&sort=`（默认 per_page 50，返回 total）；registrations、attendance 列表同样处理；studio-admin 表格加分页控件（super-admin 租户表已有客户端分页可参考，但这次要服务端分页）。
**验证：** 24+ 学生的 seed 租户翻页正确；search+分页组合正确；响应含 total。

## A4 — CSRF 防护

**问题：** 全站无 CSRF token，仅靠 `SESSION_COOKIE_SAMESITE='Lax'`；Lax 不拦截顶层 GET 导航后的同站脚本，且未来若放宽 CORS 会直接暴露。
**证据：** `grep -c csrf backend/` = 0；server.py:134 SameSite=Lax。
**修复：** 轻量方案——所有 fetch 带自定义头 `X-Requested-With: StudioSaaS`，后端对 `/v1/*` 的 mutation 校验该头（浏览器跨站表单无法伪造自定义头）；写成 before_request 中间件，公共端点白名单豁免。UI 三处（super-admin、studio-admin、legacy bridge 的 fetch 封装）统一加头。
**验证：** 无头的 curl mutation → 403；带头正常；test_route_protection 补用例；72+63+34 全绿。

## A5 — 登录与表单交互 UX

**问题：** 登录/表单交互细节缺失，触发限流或慢网络时用户得不到反馈。
**证据：** `grep -c "429\|Too many" super-admin.html backend/frontend/studio-admin.html` = 0（两个 admin UI 不区分 429）；登录按钮无 loading/禁用态；无密码可见性切换；`PERMANENT_SESSION_LIFETIME = 30 天`（管理后台过长）。
**修复：**
1. 登录表单：429 显示"尝试过多，请 1 分钟后再试"倒计时；提交时按钮 disabled + spinner；密码显隐切换；Enter 提交。
2. 全站 fetch 封装统一处理 401（跳登录）、429（提示）、5xx（toast）。
3. 会话策略：idle 超时 24h + "记住我" 勾选才延长到 30 天（Flask session.permanent 分支）。
**验证：** 手动触发 429 看提示；未勾记住我时 cookie 为会话级。

## A6 — XSS 防线制度化

**问题：** 两个 admin UI 各自内联了一份 `esc()` 且使用普遍（好），但没有任何机制防止下一个 PR 忘记转义；两份实现漂移风险。
**证据：** `super-admin.html:1202` 与 `studio-admin.html:1659` 定义完全相同的 esc()；共 24 处 innerHTML 赋值靠人工纪律。
**修复：**
1. 抽 `backend/frontend/assets/ui-common.js`（esc、fetch 封装、toast、modal 助手），两个 admin 引用同一份——顺便为 C2 共享 CSS 打地基。
2. 写一个检查脚本（如 `scripts/check_ui_escaping.py`）：扫描 HTML 中 `innerHTML = \`...${` 模式里未包 `esc(` 的插值，接入 verify_local.sh。
3. 对 registrationFieldsEditor 等动态模板逐处复核一遍。
**验证：** 检查脚本 0 告警；建一个名字含 `<img onerror>` 的学生/租户，全部界面渲染为文本。

---

# B 级 — 功能补全（管理与门户）

## B1 — CSV 数据导出

**问题：** Blueprint §3.2 承诺 studio 数据导出，完全未实现；试点客户离开或对账都需要。
**证据：** `grep -c "csv\|export" backend/frontend/studio-admin.html backend/studiosaas/api_v1.py` = 0。
**修复：** `GET /v1/export/students.csv`、`/v1/export/registrations.csv`、`/v1/export/credit-ledger.csv`（tenant_admin_required，流式生成，UTF-8 BOM 便于 Excel）；studio-admin Settings 加"Data Export"卡片；导出动作写 audit_logs。
**验证：** 三个 CSV 在 Excel/Numbers 打开列对齐；跨租户导出被 403；审计有记录。

## B2 — 家长门户 / 作品分享闭环补完

**问题：** share_tokens 有写入和查询（部分实现），但缺公开查看端与管理 UI，家长拿不到可用链接。
**证据：** `api_v1.py:2101`（INSERT share_tokens）、`:2154`（SELECT）；无 `/v1/public/portfolio/<token>` 路由；studio-admin 无"生成/撤销分享链接"入口。
**修复：**
1. `GET /v1/public/portfolio/<token>`：校验 token_hash+expires_at，返回该学生公开作品集（只读、无 PII 之外内容）+ 一个移动端优先的查看页。
2. studio-admin 学生详情：生成链接（默认 30 天）、复制、撤销、已生成列表。
3. 过期/撤销的 token 访问 → 友好的失效页。
**验证：** 生成→匿名窗口打开→撤销后 404/410；跨租户 token 不可用；isolation 测试补用例。

## B3 — 邮件通知服务 v1

**问题：** `email_templates`、`notification_logs` 两张表建了但零引用，注册提交/审核结果全靠家长自己猜。
**证据：** `grep -c "notification_logs\|email_templates" api_v1.py` = 0。
**修复：** `services/notifications.py`：`send(tenant_id, template_key, to, context)`，后端可切换（STUDIOSAAS_EMAIL_BACKEND=console|smtp，pilot 用 console 打日志即可）；接两个触发点——公共注册提交成功（给家长确认）、审核 approve/reject（结果通知）；每次发送落 notification_logs；模板取 email_templates，缺省用内置默认。
**验证：** console 后端下提交注册能看到渲染后的邮件日志；notification_logs 有行；模板可被租户覆盖。

## B4 — Support Mode（平台支持模式）

**问题：** README §13 / Blueprint §3.1 要求的 support mode 不存在；平台运营者现在要么用 NULL-tenant 超管身份静默访问租户数据（无痕迹），要么无法支持客户。
**证据：** `grep -ci "support.mode" super-admin.html api_v1.py` = 0。
**修复：** Super Admin 租户操作里加"Enter Support Mode"：写 audit（support.session_started/ended，含原因必填）→ 带 support 标记跳转该租户 studio-admin → 顶部醒目横幅"Support Mode - 操作将被审计"→ 会话内所有 mutation 的 audit 额外带 support_session 标记 → 退出按钮。
**验证：** 进入/退出/期间操作三类审计齐全；横幅在所有 section 可见。

## B5 — 公共租户页升级为真实 Landing Page

**问题：** 租户公开页只是壳，离 README §15 的"真实工作室网站"差距大，影响试点销售。
**证据：** `tenant-template/index.html` 仅 6KB，无 Hero/About/Programs/Gallery/FAQ 结构（无 section id）。
**修复：** 按 README §15 重做 tenant-template/index.html：Hero（logo+slogan+CTA）、About（welcome_message）、Programs（公开 courses）、Gallery（公开 portfolio，可空）、Contact（contact_*）、Register CTA；全部数据来自 `/v1/public/<slug>/brand` + 新增 `/v1/public/<slug>/programs`；用 Design_System token；移动端优先；空数据段落自动隐藏。老租户工作区提供再生成命令。
**验证：** 三个 demo 租户各自品牌正确渲染；Lighthouse 移动端 ≥ 90；无跨租户数据。

---

# C 级 — 结构 / 美化 / 工程

## C1 — 继续拆分 api_v1.py

**证据：** 已到 **4606 行**；`services/` 已有 media.py、tenant_archive.py（方向正确）。
**修复：** 按序抽离（每步全量验证一次）：registrations → attendance → credits → students → admin_tenants 到 `routes/` + `services/`；蓝图注册保持 URL 不变。目标：api_v1.py < 1500 行。
**验证：** 每步后 34+72+63 测试全绿、URL 无变化（对比 `app.url_map` 快照）。

## C2 — 设计 token 收敛 + 共享样式

**证据：** studio-admin.html 硬编码 hex **91 处**、super-admin 55 处（Design_System.md 明文禁止）；两个 admin 各自维护近乎重复的内联 CSS。
**修复：** 建 `backend/frontend/assets/ui-common.css`（token 变量 + button/card/form/table/badge/toast 组件类，值取自 docs/Design_System.md）；两个 admin 改引用，逐段替换硬编码色值；配合 A6 的 ui-common.js 完成公共层。
**验证：** 硬编码 hex 降到 <10（图标/品牌色例外要注释）；两 admin 视觉回归手测。

## C3 — Legacy CMS 去运行时 Babel + 退役计划

**证据：** `legacy-root/index.html` 3668 行，是唯一使用 `vendor/babel.min.js` 的页面（浏览器内编译 JSX，首屏慢且 CSP 不友好）。
**修复：** 短期——把 JSX 预编译为静态 JS（一次性 build 脚本），vendor 移除 babel；长期——列出 legacy CMS 仍独有的功能清单，与 studio-admin 对齐后写退役时间表进 docs/Development_Roadmap.md。
**验证：** CMS 全功能手测（test_cms 72 项本就覆盖 root 版）；首屏无 babel 网络请求。

## C4 — PWA 品牌中立化

**证据：** `sw.js` 头部仍是 "Let's Paint CMS"、缓存前缀 `lpcms-assets-*`（版本号已叫 tenant-pwa 但命名残留）；根 manifest 图标是 Let's Paint 素材。
**修复：** sw.js 改名 StudioSaaS + `ss-assets-*` 前缀（保留旧前缀清理逻辑一版）；根 manifest/图标换 StudioSaaS 中性素材；租户级 manifest 已按 slug 作用域（测试已验证），补租户自定义图标（settings.logo_url 有值时生成）。
**验证：** 新装 PWA 名称/图标正确；旧缓存被清理；`test_health.py` 的 manifest 用例仍绿。

## C5 — Playwright 浏览器冒烟 + verify_local.sh 补 pytest

**证据：** API 层已有 34 个 pytest，但浏览器端 0 自动化；`verify_local.sh` 不含 pytest（grep = 0）。
**修复：** `e2e/` + Playwright：四条链路（超管登录建租户 → studio admin 建学生记课时 → 公共页提交注册 → 审核转化为学生）；verify_local.sh 加入 `pytest -q`；README 补运行说明。
**验证：** 本地 `npx playwright test` 四链路绿；verify_local.sh 一键全绿。

## C6 — 界面语言统一策略

**证据：** admin 界面全英文（中文字符 0），legacy CMS/根 register 中文（server.py 错误消息也是中文），同一产品两种语言。
**修复：** 决策记入 Blueprint：pilot 语言 = 英文（澳洲市场）；legacy CMS 界面文案与 server.py 面向用户的错误消息切英文（内部注释可留）；租户面向家长的文案继续走 copy_pack 机制按租户配置。
**验证：** grep 面向用户字符串无中文残留（copy_pack 数据除外）；test_cms 断言若依赖中文消息需同步更新。

---

## 完成定义

- A 级全部完成 → 更新 docs/Current_Sprint.md 并把"External Pilot"评估从 NO-GO 重新评估。
- 每项独立 commit + 全量验证；文档（API.md / Database.md / QA_Checklist.md）随代码同步。
