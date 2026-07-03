# StudioSaaS Improvement Sprint Prompt (v4)

Version: v4.0
Date: 2026-07-03
Supersedes: codingprompt.md v3（v3 的 A1–A6、B1–B5 已全部完成并验证，见 `docs/Current_Sprint.md` "A/B Sprint" 表与 git 历史 875c256..eeb12a9。C 级未做的项并入本版）

你接手的是 StudioSaaS 多租户 creative studio SaaS。本文件是**当前开发周期的唯一任务清单**，基于 2026-07-03 深夜的第三轮全量复审（每条附证据）。规范见 `docs/`，状态跟踪见 `docs/Current_Sprint.md`。

## 已就位的能力（不要重复造）

- 认证：登录限流、记住我/空闲超时、CSRF 头守卫（`X-Requested-With: StudioSaaS`，带 cookie 的 v1 mutation 必带）、一次性密码设置链接（password_setup_tokens）、last_login 跟踪
- 共享层：`/assets/ui-common.js`（esc + fetch 补丁）、`scripts/check_ui_escaping.py`、`scripts/run_migrations.py`（0001–0006）、`scripts/regenerate_tenant_workspaces.py`、seed `--only-slug`
- 功能：CSV 导出、作品分享链接 + `/shared/portfolio` 查看页、邮件通知 v1（console/SMTP，`services/notifications.py`）、Support Mode（审计打标）、租户公共主页（`/<slug>`，CMS 在 `/<slug>/cms`）、考勤闭环、注册审核转化、租户归档
- 测试：pytest 37、隔离测试 110、test_cms 72，全绿

## 工作规则

1. 按 A → B → C 顺序执行；每完成一项跑验证、报告【改动文件/验证结果/风险/下一步】、独立 commit（`feat(A2): ...`）。
2. schema 变更必须走 `backend/db/migrations/`（下一个编号 0007）。
3. 带 cookie 的 curl 写操作记得加 `-H 'X-Requested-With: StudioSaaS'`。
4. 不做一次性大重写；pilot 阶段禁止引入 FastAPI/微服务/Redis/ES/MQ（docs/Architecture.md §7）。
5. 新增 innerHTML 模板必须过 `esc()`（检查器会拦）。

## 验证命令合集

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/studiosaas/services/*.py backend/scripts/*.py
cd backend && ../.venv/bin/python -m pytest -q                  # 37 tests
cd backend && ../.venv/bin/python test_tenant_isolation.py     # 110 checks
cd backend && ../.venv/bin/python test_cms.py                  # 72 checks
python3 backend/scripts/check_ui_escaping.py
bash backend/scripts/verify_local.sh
```

---

# A 级 — 体验闭环与一致性（先做）

## A1 — 注册页现代化（最大的割裂点）

**问题：** 全站已是英文现代风（新主页、admin、分享页），唯独家长注册页还是 iframe 套着的**中文 legacy 页**——转化漏斗最关键的一页体验最差。
**证据：** `tenant-template/register.html` 仅 124 行：`lang="zh-CN"`，body 里两个 iframe 指向 `/_legacy/register`（legacy-root/register.html，798 行中文 UI）。
**修复：**
1. 重写 `tenant-template/register.html` 为原生移动优先英文表单，与 B5 主页同一设计语言（品牌色运行时注入、design token）。
2. 动态渲染 `brand.registrationProfile.fields`（后端已提供每租户自定义字段），家长/学生分组、consent 勾选、可选照片上传（走 `/v1/public/<slug>/registration-media` 现有端点）、清晰的成功/重复提交状态（后端已返回 duplicate 信息）。
3. 提交走 `/v1/public/<slug>/registrations`（已有限流与通知）。
4. `scripts/regenerate_tenant_workspaces.py` 全量再生成；legacy 注册壳保留 `/_legacy/register` 供过渡，写退役备注。
**验证：** 提交→pending 出现在 studio-admin→家长收到确认邮件（console）；重复提交提示正确；上传预览可用；escaping check 通过；test_cms/isolation 全绿。

## A2 — 忘记密码自助流程

**问题：** studio admin 忘记密码只能找平台管理员手动发链接，pilot 阶段就会成为支持负担。
**证据：** 三个界面 grep "forgot|reset password" ≈ 0（super-admin 命中的 1 处是 Reset Password 输入框）；密码设置链接仅 super admin 能生成。
**修复（复用现成积木）：**
1. `POST /v1/auth/forgot-password` {email, tenantSlug?}：查 users+active membership → 生成 password_setup_tokens（复用 A2/v3 的表和 `/setup-password` 页）→ 用 `services/notifications.py` 发邮件（新模板 key `password_reset`）。**防枚举**：无论邮箱存在与否一律返回 `{ok:true}`；按 IP+email 限流（复用 `_login_rate_limited`）。
2. 两个 admin 登录表单加 "Forgot password?" 链接 → 小表单提交。
3. 审计 `auth.password_reset_requested`。
**验证：** 有效邮箱走通全链路（邮件里链接→设密→登录）；无效邮箱同样 200 且不发邮件；限流生效；pytest 补用例。

## A3 — 邮件模板管理 UI

**问题：** 通知在发、`email_templates` 表就绪，但租户完全无法自定义文案。
**证据：** 两个 admin grep email_template = 0；模板只能靠直接写库。
**修复：**
1. `GET/PUT /s/<slug>/v1/email-templates`（tenant_admin）：列出 4 个 key（registration_received/approved/rejected + password_reset）的当前值（自定义或默认）+ 保存 + `DELETE` 恢复默认。
2. studio-admin Settings 加 "Email Templates" 卡：下拉选模板、subject/body 编辑、占位符对照表（{parent_name} {student_name} {studio_name} …）、"Send test to me" 按钮（发到 studio admin 邮箱，走 console/SMTP）。
3. 保存审计 `settings.email_template_updated`。
**验证：** 自定义后触发注册确认用的是新文案；恢复默认生效；XSS：模板 body 是纯文本邮件不进 HTML，UI 编辑器输出过 esc。

## A4 — 注册审核队列 UI 补强

**问题：** 后端能力（分页 total、status 筛选、review_note、duplicate_of、reviewed_by/at）前端只用了一半。
**证据：** studio-admin grep registrationPager = 0（无分页）；review 相关仅 6 处（有 Approve/Reject 但审核历史与 duplicate 关联展示薄弱）；dance-dance 现有 16 条 pending 全量渲染。
**修复：**
1. registrations 表格加分页（复用 A3/v3 学生分页模式）+ 状态筛选下拉 + 待审计数徽标显示在左侧导航 "Registrations" 上（dashboard.pending_registrations 已有数据）。
2. 每行展开/详情弹窗：message、payload 自定义字段、审核历史（reviewed_at/by、review_note）、duplicate_of 链接跳转。
3. Reject/Archive 必须填 note（后端已存，前端强制）。
**验证：** 16 条 pending 分页正确；筛选 approved 只见已批；reject 无 note 被前端拦截；徽标数字与 dashboard 一致。

## A5 — 内存限流器清扫

**问题：** `_public_rate_limit` 字典只增不减——每个 IP、每个 `login-email:<ip>:<email>` 组合都永久留键，长期运行内存缓慢增长（server.py 自己的 `_rate_buckets` 有 sweep，api_v1 的没有）。
**证据：** `grep -c "sweep\|pop\|del" api_v1.py` 对该字典 = 0。
**修复：** 仿照 server.py：记录 last_sweep 时间戳，每 N 分钟（如 10）遍历删除所有条目全过期的键；加防御上限（键数 > 50k 时强制清扫）。写成小函数在各限流入口调用。
**验证：** 单测：塞入过期键 → 触发清扫 → 字典缩小；限流行为不变（429 用例仍过）。

## A6 — Landing 页 SEO / PWA 收尾

**问题：** 新主页没有 SEO/分享元数据，收藏/安装体验缺失。
**证据：** `tenants/dance-dance/index.html` grep "og:|description|favicon" ≈ 0；`<html lang="en">` 有了但无 meta description、无 OG 卡片、无 favicon、无 manifest link（register 模板反而有 manifest）。
**修复：**
1. 模板 `<head>` 补：`<meta name="description" content="{{TENANT_NAME}} — classes, programs and registration">`、OG title/description/url、`<link rel="icon" href="/{{TENANT_SLUG}}/favicon">`。
2. 新路由 `GET /<slug>/favicon`：租户 logo 存在则 302 到 logo URL，否则回平台 icon-192.png。
3. landing 也挂 manifest（复用租户级 manifest 机制）。
4. 再生成全部工作区。
**验证：** curl 看 head 标签齐全；favicon 路由对有/无 logo 两种租户正确；Lighthouse SEO 分 ≥ 90（手测）。

---

# B 级 — 功能深化

## B1 — 公共作品展示（Gallery）

**问题：** README §15 的 Gallery 段缺失——主页少了艺术工作室最有说服力的内容。
**证据：** landing 无 Gallery 段；`grep -c gallery api_v1.py` = 0；`portfolio_items.visibility` 已有 private/shared 值。
**修复：**
1. 明确语义：新增 visibility 值 `public`（migration 0007 扩 CHECK，若现值是自由文本则直接用）或复用 'shared' 作为"官网可见"——查 schema 现状后二选一并写入 Database.md。
2. `GET /v1/public/<slug>/gallery`：返回最多 12 件官网可见作品（媒体走公共媒体路由但**不带学生身份**，只给图 + 可选标题；隐私：默认不显示学生姓名）。
3. studio-admin Portfolio 每件作品加 "Show on website" 开关（PATCH portfolio item visibility）。
4. landing 加 Gallery 段（懒加载网格 + 灯箱，复用 shared-portfolio 的样式）。
**验证：** 开关打开的作品出现在主页；关闭即消失；私有作品不可能泄漏（isolation 补负向用例：gallery 响应不含 private/shared-only 项与学生 PII）。

## B2 — Studio Dashboard 升级

**问题：** Overview 只有 5 个静态计数，不是"每日驾驶舱"。
**证据：** `/v1/dashboard` 返回 `{active_students, low_balance, pending_registrations, portfolio_items, students}`；无今日考勤、无趋势、无行动入口。
**修复：**
1. dashboard 端点补：`today_attendance`（attendance_sessions 当日未作废数）、`week_registrations`（7 天报名数）、`low_balance_students`（前 5 名列表带余额）、`recent_activity`（该租户 audit_logs 最近 8 条，动作翻译成人话）。
2. Overview 区重排：四个指标卡（点击跳对应 section）+ "需要处理" 列表（待审注册、低余额学生）+ 最近活动流。
**验证：** 数字与各 section 实际一致；点击卡片正确跳转；无数据时空状态友好。

## B3 — 通知设置与每周摘要

**问题：** 通知只发给家长；studio 老板自己收不到任何运营信息（legacy CMS 有 weekly report，新体系没有）。
**证据：** notifications.py 只有 3 个家长向模板；tenants.settings 无 notification 配置；无摘要任务。
**修复：**
1. studio-admin Settings "Notifications" 卡：接收邮箱（默认 studio_admin_email）、开关"新注册即时通知"、开关"每周摘要"。存 tenants.settings.notifications。
2. 即时：public 注册创建后若开关开 → 给 studio 发 `new_registration_studio` 模板邮件。
3. 摘要：`scripts/send_weekly_digest.py`（供 cron/手动）：每租户统计本周注册/考勤/低余额 → 邮件；notification_logs 落表。
**验证：** 开关开→提交注册→studio 收到两封中的即时那封；digest 脚本对 3 个 demo 租户输出正确；关掉开关不发。

## B4 — 列表批量操作

**问题：** 学生 50/页、注册 16+ 条 pending，逐条点效率低。
**证据：** 两个列表均无复选框/批量按钮。
**修复：**
1. 学生列表：行复选框 + 全选当页；批量归档（逐条调用现有 archive 端点即可，前端串行 + 进度提示）、"导出选中"（前端过滤生成 CSV 或加 ids 参数到导出端点）。
2. 注册队列：批量标记 contacted / 批量归档（复用 PATCH 端点）。
3. 危险操作（批量归档）需确认弹窗显示数量。
**验证：** 批量归档 3 名学生审计出现 3 条；批量后列表刷新与 total 正确。

---

# C 级 — 工程与打磨

## C1 — 拆分 api_v1.py（已到临界点）

**证据：** 本轮已涨到 **5263 行**（v3 审计时 4606，一个 sprint +657——不拆会继续膨胀）。`services/` 已有 media、tenant_archive、notifications 三个先例。
**修复：** 逐模块抽到 `backend/studiosaas/routes/`（auth, admin_tenants, students, credits_attendance, registrations, portfolio_share, export, public, legacy_bridge），blueprint 注册保持 URL 不变；每搬一个模块全量验证一次；目标 api_v1.py < 800 行（仅 blueprint 装配 + 共享助手）。
**验证：** 每步 `app.url_map` 快照 diff 为空；37+110+72 全绿。

## C2 — 共享 CSS 与 token 收敛

**证据：** studio-admin **93** 处硬编码 hex、super-admin 55 处（Design_System.md 明令禁止）；两个 admin ~600 行近重复内联 CSS；本轮新页面（setup-password/shared-portfolio/landing）又各自内联了一份 token。
**修复：** `/assets/ui-common.css`：token 变量 + button/card/form/table/badge/toast/modal 组件类（值取 docs/Design_System.md）；五个页面逐段替换；hex 目标 <10（品牌注入点例外注释）。
**验证：** 视觉手测五页；grep hex 计数达标；escaping/pytest 不回归。

## C3 — Playwright E2E + CI

**证据：** e2e 目录不存在；浏览器自动化 0；无 CI。
**修复：** `e2e/` + Playwright：①超管登录建租户 ②studio 登录建学生+记课时 ③公共页提交注册→审核转化 ④分享链接家长查看。GitHub Actions：py_compile + pytest + check_ui_escaping（DB 用 services 容器跑 isolation 可后续加）。
**验证：** 本地 `npx playwright test` 四链路绿；push 触发 CI 绿。

## C4 — PWA 品牌中立化

**证据：** `sw.js` 首行仍 "Let's Paint CMS"、缓存前缀 `lpcms-assets-*`；根 manifest 图标为 Let's Paint 素材。
**修复：** 改名 StudioSaaS/`ss-assets-*`（保留旧前缀清理一版）；根 icons 换中性素材；与 A6 的租户 favicon/manifest 打通。
**验证：** 新装 PWA 名称图标正确；旧缓存清除；manifest pytest 用例仍绿。

## C5 — Legacy 层瘦身

**证据：** legacy-root/index.html 3669 行 React-in-browser（vendor babel 仅它使用）；根级单工作室 `/api/*` 仍全量暴露（test_cms 覆盖它，但产品上已无入口指向根 CMS）。
**修复：** ①一次性预编译 JSX 为静态 JS，vendor 去 babel；②列出 legacy CMS 独有功能清单 vs studio-admin，写退役时间表进 Roadmap；③评估根 /api/* 是否加 `STUDIOSAAS_ENABLE_LEGACY_ROOT` 开关（默认本地开、staging 关）。
**验证：** test_cms 72 项全绿（必要时调整启动方式）；CMS 手测全功能。

## C6 — 数据维护与索引补全

**证据：** `notification_logs` 只有主键索引（tenant 查询将全表扫）；password_setup_tokens/share_tokens 过期行无清理；audit_logs 无保留策略。
**修复：** migration 0007：`idx_notification_logs_tenant_created (tenant_id, created_at DESC)`；`scripts/db_maintenance.py`：删过期 30 天以上的 setup tokens、过期 90 天以上的 share tokens（已撤销/过期）、可选 audit 归档报告（不删，报告体量）；接入 Admin_Guide runbook。
**验证：** 迁移幂等两遍；维护脚本 dry-run 输出行数、执行后计数下降。

## C7 — 界面语言统一

**证据：** register 模板 `lang="zh-CN"`（A1 重写时顺带解决）；legacy CMS/根 register 中文；server.py 面向用户错误消息中文（如"提交太频繁"）。
**修复：** 决策记入 Blueprint：pilot 语言 = 英文；server.py 用户可见 message 切英文（test_cms 断言同步改）；legacy CMS 界面文案随 C5 处理；家长文案继续走 copy_pack。
**验证：** grep 面向用户中文残留清零（copy_pack 数据除外）；test_cms 全绿。

---

## 完成定义

- A 级完成 → 更新 docs/Current_Sprint.md，注册转化链路（主页→注册→审核→通知）可整体演示。
- B1 完成后 isolation 测试必须包含 gallery 隐私负向用例。
- C1 拆分期间任何一步 url_map 变化即回退重做。
