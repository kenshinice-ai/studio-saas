# StudioSaaS Improvement Sprint Prompt (v5 — CMS 核心版)

Version: v5.0
Date: 2026-07-03
Supersedes: codingprompt.md v4（v4 基于"公共页面 = 门面"的假设，已被产品方向纠偏推翻；v3 的 A/B 项已完成，见 git 历史）

## 0. 产品定位（本版一切优先级的依据）

**这套 SaaS 的客户是 tenants（工作室老板）。** 他们绝大多数时间花在 CMS（`/<slug>/cms`，`legacy-root/index.html`）里：排课、签到、管理学生、课时与费用。**CMS 是重点中的重点。**

- CMS 不是"待退役的过渡层"——它源自真实工作室运营（Let's Paint），是 tenants 付费使用的核心工作台。文档中所有"legacy bridge is transitional"的表述在执行 A5 时修正。
- 公共主页（`/<slug>`）意义不大：保留为未来给 tenants 客人的附加服务，页面上需要一个到 CMS 的入口，但**不投入开发资源**。
- CMS 的中文界面是面向目标用户的特性，**不要**做"统一英文"改造。
- studio-admin（`/<slug>/studio-admin`，英文）定位为"设置与管理面板"（品牌、注册审核、导出、分享链接），与 CMS 分工，见 A5。

## 1. CMS 现状地图（2026-07-03 深夜复审）

`legacy-root/index.html`（3669 行 React，浏览器内 Babel 编译）：

| Tab | 功能 | 现状 |
|---|---|---|
| dashboard | 指标 + 今日排班入口 | ✔ |
| roster | **每日排班 + 上课签到 + 一键消课 + 班次组模板** | ✔ 但只有"当日名单"模型，无周课表 |
| students | 学生、课时余额、调整、作品、生日、活跃度分层（活跃/低频/流失风险） | ✔ |
| topup | 充值 + 复制充值确认（发家长） | ✔ |
| pending | 待处理报名 | ⚠ 与 v1 registrations 审核流是否同源待统一 |
| stats | 图表统计 | ✔ |
| logs | 操作日志 | ✔ |
| 设置 | PIN 锁、备份导出/恢复、CSV | ⚠ 备份仍是 JSON 时代设计 |

**已核实的关键问题：**
1. CMS 的签到/充值/课时调整全部走 `legacy-cms/save` **整包写回**（grep：CMS 内 0 处调用 v1 attendance/credits 端点）→ CMS 签到**不产生** `attendance_sessions` 记录，studio-admin 的考勤页看不到 CMS 的签到，两套账本并行。
2. CMS 界面 0 处链接到 studio-admin；landing 页脚只链 studio-admin 不链 CMS。
3. 排课 = 每日 roster + 手动模板，没有"每周三 4pm 素描班"的周期课表。
4. 3669 行 JSX 每次打开都在浏览器里 Babel 编译（核心产品首屏最慢）。

## 2. 工作规则

1. A → B → C 顺序；每项独立 commit + 全量验证 + 报告【改动文件/验证结果/风险/下一步】。
2. schema 变更走 `backend/db/migrations/`（下一编号 0007）。
3. **改 CMS 前先跑 `test_cms.py`（72 项）拿基线；改完必须回到全绿**——它是 CMS 的行为契约。
4. 带 cookie 的 curl 写操作加 `-H 'X-Requested-With: StudioSaaS'`。
5. CMS 的中文文案保持中文；新增 CMS 功能的文案用中文。
6. 禁止引入 FastAPI/微服务/Redis/ES/MQ（docs/Architecture.md §7）。

## 3. 验证命令合集

```bash
python3 -m py_compile backend/server.py backend/studiosaas/*.py backend/studiosaas/services/*.py backend/scripts/*.py
cd backend && ../.venv/bin/python -m pytest -q                  # 37
cd backend && ../.venv/bin/python test_cms.py                   # 72 — CMS 行为契约
cd backend && ../.venv/bin/python test_tenant_isolation.py     # 110
python3 backend/scripts/check_ui_escaping.py
```

---

# A 级 — CMS 核心强化（tenants 的日常工作台）

## A1 — 周期课表（排课系统）

**问题：** "排课"是 tenants 花时间最多的事，但 CMS 只有"当日名单 + 手动模板"，每周固定班级要天天手动排。
**证据：** roster tab 的模板功能是"保存常用班次组"（一次性名单快照）；无 weekday/时间段概念；`class_schedules` 表不存在。
**修复：**
1. migration 0007：`class_schedules`（id, tenant_id, course_id, weekday smallint 0-6, start_time time, duration_minutes, capacity, label, is_active, created_at）+ `class_schedule_students`（schedule_id, student_id, UNIQUE 对）。
2. v1 端点（tenant_admin）：schedules CRUD + 学员名单管理 + `GET /v1/roster?date=` 返回"当日应到名单"（由 weekday 匹配的 schedules 展开 + 手动增删）。
3. CMS roster tab 升级为两个视图：
   - **课表视图**：按周几分列展示班次（时间、课程、人数/容量），点击编辑学员名单——中文界面，沿用 CMS 现有风格。
   - **今日视图**（现有）：自动预填今日课表学员，保留手动加人/模板兼容；签到流程不变。
4. 现有"班次组模板"提供一键转换为周期班次的入口（迁移用户习惯）。
**验证：** 建"周三 16:00 素描班"+3 学员 → 周三的今日视图自动出现 3 人 → 签到扣课时正常；非周三不出现；test_cms 72 全绿（roster 旧行为兼容）；isolation 补 schedules 跨租户负向用例。

## A2 — 签到/课时账本统一（消除双轨账）

**问题：** CMS 签到不写 `attendance_sessions`，studio-admin 考勤页与 CMS 各记各账；课时扣减两条路径（bridge 整包 save vs v1 credit_transactions），审计与对账不可信。
**证据：** CMS 内 0 处调用 v1 attendance/credits 端点；`attendance_sessions` 只被 studio-admin 的 check-in 写入。
**修复：**
1. CMS 的签到/撤销改调 `POST /s/<slug>/v1/attendance/check-in` 与 `/attendance/<id>/void`（端点已存在，含课时 consume/refund 与审计）；充值/课时调整改调 `POST /v1/students/<id>/credit-transactions`。
2. bridge 的 `legacy-cms/save` 对 balance/签到字段改为**忽略并告警日志**（防旧 tab 覆盖，portfolio 已有同款保护先例），学生基本信息仍可整包保存。
3. CMS 的"今日已签到"状态从 v1 attendance 读取（`GET /v1/attendance?date=`），撤销按钮映射 void。
4. 兼容：CMS 历史 logs 展示保留；新签到同时出现在 studio-admin 考勤页。
**验证：** CMS 签到 → studio-admin 考勤页立即可见同一条记录、课时余额两边一致、credit_transactions 出现 consume 行；撤销 → refund 行；test_cms 涉及签到的用例改走新路径后全绿；对同一学生连续两次签到的防重行为与原 CMS 一致。

## A3 — CMS 首屏性能（预编译，去浏览器 Babel）

**问题：** 核心工作台每次打开都要在浏览器里编译 3669 行 JSX。
**证据：** `legacy-root/index.html` 加载 `vendor/babel.min.js`（全站唯一使用者）；`<script type="text/babel">`。
**修复：**
1. 一次性构建脚本 `backend/scripts/build_cms.py`（或 npx babel 命令写入 README）：抽出 JSX → 预编译为 `legacy-root/cms-app.js`（普通 JS）→ index.html 改为 `<script src>` 引用，删除 babel 加载。
2. 保留源 JSX 于 `legacy-root/src/cms-app.jsx` 供后续修改，构建命令写入 docs；vendor 移除 babel.min.js。
3. 静态资源加版本参数防缓存。
**验证：** CMS 全功能手测（登录/PIN/roster/签到/充值/学生/作品/设置）；test_cms 72 全绿；Network 面板无 babel 请求、首屏可感知变快。

## A4 — CMS pending 与 v1 注册审核统一

**问题：** 注册审核在 studio-admin 有完整状态机（review_note、duplicate、转化建学生、邮件通知），CMS 的 pending tab 若走旧数据路径则形成双轨流程。
**证据：** CMS pending tab 数据来自 bridge 大 JSON；v1 registrations 有 6 状态 + 通知。
**修复：**
1. CMS pending tab 改为直连 `GET /s/<slug>/v1/registrations?status=pending`（读）与 `PATCH /v1/registrations/<id>`（批准/拒绝，中文按钮），批准即转化建学生 + 家长邮件——与 studio-admin 完全同一状态机。
2. bridge save 的 pending 字段同样改为忽略（防覆盖）。
**验证：** 公共页提交注册 → CMS pending 出现 → CMS 内批准 → 学生出现在 students tab + 家长收到邮件 + studio-admin 里状态一致；test_cms pending 相关用例调整后全绿。

## A5 — 三个界面的定位、互通与入口

**问题：** CMS（运营）与 studio-admin（设置）无相互入口；landing 无 CMS 入口（用户点名要求）；文档仍称 CMS 为"transitional"。
**证据：** CMS 内 studio-admin 链接 0 处；landing 页脚只链 studio-admin。
**修复：**
1. CMS 设置区加"🎨 品牌与网站设置（Studio Admin）"链接；studio-admin 导航加"打开 CMS 工作台"。
2. landing 页脚改为 "Studio Login → /<slug>/cms"（保留 studio-admin 链接次之）。
3. docs 修正定位：Architecture/Blueprint 中 CMS 描述改为"核心运营工作台"，studio-admin 为"设置与管理面板"，landing 为"附加服务（低优）"；README 分流指引同步。
**验证：** 三个界面互达；文档 grep "transitional" 清零（历史决策记录除外）。

---

# B 级 — 运营深化（费用 / 学生 / 员工）

## B1 — 费用与课时运营闭环

**问题：** 低课时提醒只有界面标红，无主动通知；充值确认靠手动复制文本发家长。
**修复：**
1. 低课时自动提醒：`scripts/send_weekly_digest.py`（新建）每周汇总低课时学生发 studio 邮箱；tenants.settings.notifications 开关（studio-admin Settings 卡 + CMS 设置区入口）。
2. 充值确认邮件：CMS topup 完成后，若家长有邮箱，提供"📧 邮件发送确认"按钮（新模板 `topup_receipt`，复用 notifications 服务）；无邮箱保持复制文本。
3. 收入统计核对：stats 的金额图表数据源确认走 credit_transactions（fee_aud_cents），与 CSV 账本一致。
**验证：** digest 对 3 个 demo 租户输出正确名单；充值后邮件（console）内容含金额课时；stats 数字与 ledger CSV 合计一致。

## B2 — 生日与流失运营动作

**问题：** CMS 已有生日提醒（15 处）与活跃度分层（活跃/低频/流失风险），但只能看，没有动作。
**修复：** 生日列表加"复制祝福（发家长）"与"📧 发送祝福"（模板 `birthday_greeting`）；流失风险名单并入每周 digest；dashboard 顶部本周生日提示。
**验证：** 生日学生（seed 数据含生日）触发展示与发送；digest 含流失名单。

## B3 — 员工（staff）账号与受限视图

**问题：** schema/权限模型已有 staff 角色（可读写学生/签到，不可动设置），但无任何 UI 创建 staff，教师场景（只做签到）无法落地。
**修复：**
1. studio-admin Settings "Team" 卡：邀请 staff（邮箱 + 密码设置链接复用 password_setup_tokens）、列表、停用。
2. v1 端点：`GET/POST /v1/team`、`PATCH /v1/team/<membership_id>`（tenant owner 权限）。
3. CMS 按角色收敛：staff 登录 CMS 时隐藏 topup/设置/备份，保留 roster 签到与 students 只读+签到（auth /me 已返回 role）。
**验证：** 邀请 staff → 设密登录 → CMS 只见受限功能 → 签到成功且审计 actor 正确；staff 调 settings/export 端点 403（isolation 补用例）。

## B4 — CMS 备份/导出对接新体系

**问题：** CMS 设置里的"备份导出/恢复"是单工作室 JSON 时代设计，误导现租户。
**修复：** 该区块改为：租户数据导出（链接三个 CSV 端点）+ 平台备份说明（backup_postgres.py runbook 链接）；旧 JSON 导出按钮标注"旧版格式（兼容保留）"。
**验证：** CSV 三链接在 CMS 内可用（owner 权限）；文案准确。

---

# C 级 — 工程与降级项

## C1 — 拆分 api_v1.py（临界）

**证据：** 5263 行且每 sprint +600。A1/B3 又要加路由——**先做本项或与 A1 同步做**：新功能直接写进 `routes/schedules.py`、`routes/team.py`，存量按 auth/admin/students/credits_attendance/registrations/portfolio_share/export/public/legacy 逐模块搬。
**验证：** 每步 url_map diff 为空 + 三套件全绿。

## C2 — E2E（CMS 主链路）+ CI

改编 v4-C3：Playwright 链路以 CMS 为主——①owner 登录 CMS ②建周课表 ③今日视图签到 ④充值 ⑤pending 批准。GitHub Actions 跑 py_compile+pytest+escaping。

## C3 — 内存限流器清扫（v4-A5 降级）

`_public_rate_limit` 无 sweep，键无限累积。仿 server.py `_rate_buckets` 加定期清扫 + 键数上限。

## C4 — 数据维护与索引（v4-C6）

migration 0007 顺带：`idx_notification_logs_tenant_created`；`scripts/db_maintenance.py` 清过期 tokens；Admin_Guide runbook。

## C5 — 共享 CSS / PWA 品牌中立（低优）

ui-common.css 收敛 token（studio-admin 93 处硬编码 hex）；sw.js 去 "Let's Paint/lpcms" 命名。CMS 样式**不动**（自成体系且用户熟悉）。

## C6 — 公共面（landing/注册页）——按产品方向搁置

v4 的 A1（注册页现代化）/A6（SEO）/B1（Gallery）明确**降级搁置**：landing 保持现状仅加 CMS 入口（A5 已含）；注册页 iframe 壳可用即可；未来作为"官网附加服务"再立项。家长注册体验如影响转化率由用户判断后再提级。

---

## 完成定义

- A 级完成 = tenants 可以在 CMS 里完成"建周课表 → 每日自动排班 → 签到消课 → 充值"全流程，且每一步与 v1 账本（attendance_sessions/credit_transactions）同源一致。
- test_cms.py 在每一项 CMS 改动后必须回到 72/72（允许因行为升级修改断言，需在 commit message 说明）。
