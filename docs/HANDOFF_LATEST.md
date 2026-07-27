# StudioSaaS 交接文档（持续更新）

> 本文件在**每轮改动开始时和完成时**都更新（用户 2026-07-26 明确要求），
> 始终反映最新状态。历史交接见 `docs/HANDOFF_2026-07-26.md`（v7.3.x 时期）。
> 最后更新：2026-07-27（Logo 二轮 Crafted P 定稿 + 出品署名 · **已完成**）

---

## ✅ Logo 二轮：Crafted P 定稿 + Paradise Production 署名（2026-07-27，已完成）

双视角研究（设计本体 4 候选 + 甲方 12 项加权评分表）→ 用户拍板
**D · Crafted P**（82/100，唯一过 75 替换线；现行 monoline 64/100）：

- **新 mark**：实心 P + 星火即字腔（负空间共同主角），碗 60.5% 帽高、
  超椭圆肩上倾应力、字干微收、墨陷阱；命中甲方三条要求（星火共同
  主角/放弃线框/恰一处手作温度）。字标 P 同族化改造，锁定组合光学
  重排（mark 0.75 缩放）。全部根资产由 `render_assets.py` 单源重生成；
  Super Admin 头部内联 mark 已同步；manifest 无需改动。
- **品牌架构（用户决策）**：产品牌 PWE Studio SaaS 不变；
  「PWE = Paradise WE，与创作者共有的一方天域」入品牌故事；
  **出品署名（唯一形式）「A PARADISE PRODUCTION · 天域文创出品」**
  ——10px/600/0.08em/slate，只出现在：PPT 封面+尾页、Super Admin
  登录页脚、README 页脚、品牌文档；**禁入租户面，永不与 mark 锁定**。
  规范见 Brand_Identity.md §10（v2.0，含 §11 changelog 64→82）。
- **PPT**：两张深色页换新 logo-light.png，署名恰好两处零修饰，
  v7.7.7 与全部事实价格未动，验证+渲染 QA 通过。
- 研究存档：`docs/design/brand/round2/`（4 候选 SVG + compare 页 +
  RATIONALE + CLIENT_PERSPECTIVE 评分表；C 方案经 16px 测试自我淘汰）。

---

## ✅ v7.7.7 生产就绪整改 + DB 安保 + 销售套件轮（2026-07-27，本轮已完成）

三个并行 agent（Well-Architected 部署审计 / 数据库安全专项 / 销售 PPT）
+ 主线修复。**部署审计 4 阻塞 + 7 应修、安保审计 2 阻塞 + 3 应修全部
落地**；明细见 README §4.18。要点：

- **部署套件**：`requirements.lock` 生产精确锁版；镜像内置 pg_dump +
  README_AWS **§9 备份章**（每日 cron/0600/EBS DLM 卷快照/季度还原演练）；
  nginx **bootstrap 配置**解决 certbot 先有鸡还是先有蛋；tenants 卷 +
  开机重生成（运行时建的租户门户不再随镜像重建丢失）；compose 日志上限
  + SMTP/超时变量透传；systemd ReadWritePaths 补 tenants/archives；
  §7 迁移补数据卷 + chown；`/v1/health?deep=1` DB 探针接入容器健康检查。
- **DB 安保**：最小权限 RDS 角色 + `sslmode=require` 写死在套件；
  backup 脚本 0600/密码走 PGPASSWORD/iCloud 路径警告（存量 dump 已收紧）；
  balance-query 在学员签发访问码后强制要求（关闭姓名+手机存在性预言机）；
  unlock 恒定功耗 + 每 IP 平坦限流（关闭时序预言机）。审计其余判定
  SECURE（参数化 SQL/PBKDF2-600k/哈希令牌/隔离/支持门全干净）。
- **销售套件**：`docs/sales/PWE_StudioSaaS_销售介绍.pptx`（13 页，品牌
  配色，逐项事实核实：201 隔离检查、15 theme-modes、定价按 plans seed）
  + `talk_track.md` 讲稿与异议应对。商务联系方式为占位，可自行替换。
  **二轮文案润色（用户点名）**：13 页标题全部改写为面向画室/音乐/舞蹈
  主理人的艺术语言（「你的才华，不该耗在台账和聊天记录里」「每一节课的
  去向，像五线谱一样清晰」「管理退到幕后，作品站上台前」等），痛点四卡
  按「被偷走的创作时间/信任」重构；标题写意、要点写实，全部数字与定价
  一字未动；逐页 LibreOffice 渲染 QA 无溢出，讲稿同步对齐。
- **版本 v7.7.7 全量统一**：VERSION/server.py/README + 7 份 guides +
  Deployment.md 头 + PPT 封面。验证：131 pytest + 73 smoke +
  201 isolation 全绿；生产镜像重建实测（pg_dump 17.10 + 锁定版依赖）。

---

## ✅ LetsPaint 真实数据导入轮（2026-07-27，本轮已完成）

`lets-paint-studio` 从 demo 租户转为**真实数据租户**：

- **导入源**：`~/Downloads/LetsPaint_2026-07-27.json`（sha256 c318f4e4…，
  导入前已 `backup_postgres.py backup` 全库备份）。
- **执行**：`import_lets_paint_json.py --apply --reset-all-students
  --confirm-tenant lets-paint-studio` — 清空该租户 demo 数据
  （registrations + students 级联 + 非 logo 媒体；品牌/成员/课程保留），
  写入 **43 名真实学员 + 期初余额 165 课时**（migration 类型账本行，
  含来源摘要）；另 upsert 两个真实套餐（标准课包 $1200/10 节、
  1 对 1 专业辅导 $1500/10 节），demo 套餐停用。
  历史 logs/排课/媒体/访问码等按「只保留核心」原则不导入。
- **脚本硬化**：`_delete_all_students` 从全库 DELETE 改为**租户范围**
  （原脚本假设整库皆 demo，会误删其他租户）。
- **防覆盖锁**：导入成功后自动写入 `settings.demo_seed_locked=true`；
  `seed_random_demo_data.py` 全量路径 SKIP 该租户、`--only-slug` 路径
  直接拒绝（均已实测）。解锁需手动清除该标志。
- **验证**：owner 登录 → legacy-cms/data 43 人/165 课时/0 待审核/
  2 真实套餐；131 pytest 全绿。
- **注意**：这是本地 `studiosaas_local_test` 库的数据；AWS 迁移时随
  pg_dump 一起走（Deployment §3.2），锁标志在 settings 里随行。

---

## ✅ v7.7.0 遗留清零 + 品牌识别轮（2026-07-27，本轮已完成）

五个并行 agent（studio-admin hex/行内报错/审计面板 · super-admin 二轮 ·
CMS/门户走查小项 · PWE 品牌识别 · 角色手册+FAQ）+ 后端主线。
逐项明细见 README §4.17。

- **Roadmap 全清**：支持会话强制门（403 `support_session_required`，
  5 条隔离检查钉住，override `STUDIOSAAS_ENFORCE_SUPPORT_GATE=0`）；
  Owner 审计端点 `GET /s/<slug>/v1/audit-logs` + Studio Admin 数据分析
  面板；studio-admin 样式层 161 hex → 0（28 个新语义 token，残留 33 处
  为主题数据属正确保留）；品牌表单 12 字段行内报错；media token hex 化
  以「UUIDv4 已 122 位随机 + 门后访问」结论关闭；Redis 按政策押后。
- **PWE 品牌识别**：「P 里的火花」— P 字母格 + 琥珀四角星火花；
  Studio Navy `#0F172A` + Spark Amber `#F59E0B`；纯几何字标（零字体
  依赖）；`docs/design/brand/render_assets.py` 一表出全部 SVG/PNG；
  根目录 icons/manifest/favicon.svg 全部重生成；四个界面 head 已接入
  平台 favicon 组；Super Admin 头部 mark 内联。
- **Super Admin 二轮**：走查发现的 54 条英文串全部入词典（套餐额度行
  重构为逐节点）；审计时间本地化；CMS/Admin 快链改走支持模式对话框
  （公开面保持直链）；健康徽章并入 pill 体系（AA 对比度）。
- **CMS/门户**：待审核时间截到分钟、10 状态中文、同手机号疑似重复
  徽章、60 分钟双语、损坏图片优雅降级（tile 移出 tab 序）。
- **角色手册 7 份全部 7.7.0**：新增前台/店员专属手册；支持门/Owner
  审计/分享链接权限描述与代码逐条核实；各角色 FAQ 补齐。
- **验证**：131 pytest + 73 smoke + **201 isolation**（+5 支持门检查）
  全绿；四件套检查通过；版本三处统一 7.7.0。

---

## ✅ v7.6.0 修复与 UI 升级轮（2026-07-27，本轮已完成）

针对 v7.5.0 全量审计（`docs/Project_Audit_2026-07-27.md`）的修复轮：
四个修复 agent 并行（后端 / 数据库 / Super Admin UI / legacy 面），
文档 agent 收尾。改动**已提交并推送，main 与 codex/studiosaas-v7.3.1
已对齐本提交**。

- **修复统计**：审计 **3 HIGH / 13 MED / 20 LOW 全部清零**，另加
  Super Admin 控制台专业化改版（KPI 卡、漏斗可视化、告警组件、表格
  筛选、顶部按钮组；新增 `--line-strong`/`--row-hover`/`--head-bg` 等
  token）。要点：`_is_local_request` 改 remote_addr 判定；限流器加锁
  +惰性清理；裸 `refund` 归一为 refund_out 语义；503 在 pilot/production
  固定文案；新迁移 **0020**（删两个冗余索引）；0016/schema_v1 DO 块
  可重跑修复；`connect()` 支持超时覆盖（维护脚本传 0）；归档裁掉
  `users.password_hash`；super-admin logout 崩溃修复 + pill 对比度达标
  （4.84–6.92:1）+ 29 处转义盲区清零 + admin-i18n 补 ~75 键；
  shared-portfolio 灯箱键盘可达 + 最小双语；legacy register emoji 16 处
  清零、删 CDN 兜底与 maximum-scale。逐项明细见 README §4.16。
- **验证基线**：**131 pytest** 全绿（新增
  `tests/test_v760_backend_fixes.py`）；check_terminology /
  check_inline_script / check_ui_escaping（扩展版）三件套通过；
  0020 与 0016/schema_v1 重跑在真实 PostgreSQL 实测通过；
  四个界面浏览器实测。
- **版本三处统一 v7.6.0**（VERSION / server.py APP_VERSION / README）；
  guides 六份手册"适用版本"7.4.1 → 7.6.0（审计 DOC1）；API/Database/
  Roadmap/QA_Checklist/Deployment 同步（503 文案、refund 同义、超时
  新机制、迁移 0020、测试数 131）。
- **遗留（roadmap 在案）**：61 处 raw hex token 化、super_admin 支持
  会话强制门、Owner 审计日志入口、品牌表单行内报错、media token
  hex 化、P3-04 Redis 限流。

---

## 历史轮次（压缩记录）

- **v7.5.0 全量项目审计轮（2026-07-27，已完成）**：四方向只读审计
  （UI/UX、后端、数据库、文档），基线 f710bdc；健康面七条不变量全
  PASS、schema 零漂移；产出 3H/13M/20L 发现清单
  （`docs/Project_Audit_2026-07-27.md`），全部已在 v7.6.0 轮修复。
- **v7.5.0 文档与 UX 审计轮（2026-07-26，已完成，ef8b1f8 + f710bdc 已
  push）**：文档全量刷新（README 枚举表 / API / Database / Architecture /
  Design_System / Admin_Guide 角色矩阵）、UI/UX 修复批次（reduced-motion /
  focus-visible / 触控 40px / CMS emoji 清零 / 登录行内报错）、
  `docs/guides/` 六份角色手册新增、ui-ux-pro-max skill 同步；
  Blueprint setup fee 定价统一 **AUD 299–999**（用户拍板，勿改回）；
  `verify_local.sh` 全量通过，AWS 打包产物 sha256 校验 OK。

---

## 0. 当前状态一览

- **版本**：v7.7.7（VERSION / server.py APP_VERSION / README 三处一致；
  v7.4.0=RBAC/a11y/AWS 套件，v7.4.1=数据库与复审稳定性修复，
  v7.5.0=文档全量刷新 + UI/UX 修复批次 + docs/guides 角色手册，
  v7.6.0=审计 3H/13M/20L 全量修复 + Super Admin UI 专业化改版，
  v7.7.0=roadmap 全清 + PWE 品牌识别 + Super Admin 二轮，
  v7.7.7=生产就绪整改 + DB 安保 + 销售套件）
- **提交状态**：v7.7.0 已提交并推送（9de05ab，分支
  `codex/studiosaas-v7.3.1`）；v7.6.0=59af5a2（main 已对齐该提交，
  9de05ab 尚未合入 main）
- **打包产物**：`dist/PWE-StudioSaaS-aws-7.7.0.tar.gz`（sha256 校验 OK，
  含 BUILD_INFO，本轮产出）
- **验证基线**：**131 pytest** + 73 smoke + **201 tenant-isolation** 全绿
  （201 含 v7.7.0 新增的 5 条支持门检查）
- **AWS 部署包**：`bash deploy/aws/build_aws_bundle.sh <ver>` →
  `dist/PWE-StudioSaaS-aws-<ver>.tar.gz`（含 BUILD_INFO；需干净 git 树）
- **迁移**：0001–0020；`schema_v1.sql` 已与迁移链**零漂移**（实测比对列/约束/索引；
  0020 只删冗余索引，无新表）

## 1. v7.4.0 做了什么（详见 README §4.14）

三条主线，全部已提交并验证：

1. **RBAC 全量审计修复** — 旧版 `/api/*` 在 pilot/production 410 关闭；
   parent-only 用户拒绝登录；财务边界（analytics:read / credits:read）落到
   /dashboard 与 /packages；新权限 `credits:refund`、`portfolio:share`
   （owner/manager）；legacy-cms/save 放行 students:write（套餐段仍限管理层）；
   CMS save() 布尔契约（22 个调用点全检查）；teacher 获得 roster 标签页。
2. **可访问性整改** — 两控制台 label/for 全覆盖、模态焦点还原+捕获、
   ARIA tab 键盘契约、门户画廊/灯箱键盘可达、自定义报名字段逐字段报错、
   aria-label 随语言切换、Super Admin 图标 SVG 化。
3. **AWS 部署套件** — `deploy/aws/`（Dockerfile/entrypoint/compose/nginx/
   systemd/打包脚本），Docker 端到端彩排通过（自动迁移→健康→旧接口 410）。

## 2. 深度复核轮（v7.4.1）修复清单

### 数据库稳定性审计（9 项，全部已修）

| 严重度 | 修复 | 位置 |
|---|---|---|
| HIGH | 归档快照补齐 0015–0017 六表（发布同意事件=法律证据） | `services/tenant_archive.py` SNAPSHOT_TABLES |
| MED | DB 超时：connect 5s / statement 30s / lock 10s（env 可调 `STUDIOSAAS_DB_*`） | `studiosaas/db.py` |
| MED | 旧档案编辑余额路径：FOR UPDATE + 带符号增量 + creditHours 记增量 | api_v1.py `_apply_absolute_balance` |
| MED | schema_v1.sql 补 0015–0017 + 0011 索引，零漂移 | `db/schema_v1.sql` 尾部 |
| MED | legacy-cms/save 服务端 rev 冲突检查（租户行锁 + 409 conflict + force 覆盖） | api_v1.py legacy_cms_save 开头 |
| MED | backup_postgres.py 补 `import sys` | scripts |
| L-M | 账本 CSV 导出归一化 consume/expire 符号 | export_credit_ledger_csv |
| L-M | 注册审批 FOR UPDATE（防并发双转化） | registration status 路由 |
| LOW | 迁移 0019：portfolio/notification 索引 + 删重复唯一索引；0016 标注 PG16+；`prune_event_tables.py` 保留脚本；compose 归档卷 | db/migrations、scripts、deploy/aws |

### 变更逻辑复审（6 项 CONFIRMED，全部已处理）

1. 登录拒绝消息区分「仅 parent」vs「无有效成员」（消息+审计 reason 都不再误导）
2. `end_support_session` 恢复宽松鉴权（防支持横幅卡死），注释说明为何不用 @auth_required
3. 删除死代码 `canSharePortfolio`（CMS 无分享 UI；后端权限已生效）
4. ConfirmDialog：Escape/遮罩点击对 acknowledge 对话框会先跑 onConfirm（reload 类通知不再丢）
5. dashboard 财务投影改 fail-closed（actor 缺失时剥离而非泄漏）
6. rev guard —— 已在数据库轮实现服务端强制（复审时是纯客户端）

复审同时确认：退款门无绕过（legacy_type 检查先于映射）、装饰器替换角色集完全等价、
media/upload kind 分发穷尽、schedule DELETE 双调用方安全、CMS save 22 个调用点全检查。

## 3. 已知未决 / 设计决策（有据可查，暂不做）

- ~~支持会话是 UI 提示~~ → **v7.7.0 已强制**（见顶部本轮记录）。
- ~~租户 Owner 无自有审计日志入口~~ → **v7.7.0 已上线**。
- **v1 save 无 shrink guard**：v1 save 不删除学生（absence≠delete），rev guard
  已挡 stale 覆盖，故不需要 server.py 式的缩水防护。
- **账本历史符号不回写**：consume 正负混存是历史事实，导出层归一化；不做
  数据迁移改写账本历史。
- `programs[]` / `gallery[].title` 单语存储（产品决策，见 Glossary）。

## 4. 常用命令（与上一份一致，补充两条）

```bash
# 全量验证（发布门槛）
STUDIOSAAS_DATABASE_URL=postgresql://$USER@localhost:5432/studiosaas_local_test \
STUDIOSAAS_REQUIRE_POSTGRES=1 bash backend/scripts/verify_local.sh

# CMS 改完必须重建；模板改完必须重生成
bash backend/scripts/build_cms.sh
.venv/bin/python backend/scripts/regenerate_tenant_workspaces.py

# 新增：事件表保留清理（建议每月 cron）
python backend/scripts/prune_event_tables.py --dry-run

# 新增：AWS 打包
bash deploy/aws/build_aws_bundle.sh <version>
```

## 5. 下一个会话注意

- 改任何迁移时：**同步 `db/schema_v1.sql` 和 `tenant_archive.py SNAPSHOT_TABLES`**
  （两个清单在 0015–0017 时期都漂移过，v7.4.1 轮才补上）。
- `tenants/<slug>/` 是生成目录，别手改；改模板后跑 regenerate。
- Edit 工具对 `\uXXXX` 字面量匹配不了（presets.py / index.html），用脚本替换。
- 浏览器会缓存 `/v1/industry-presets`，排查样式问题先排除缓存。
- CSRF：v1 写请求需要 `X-Requested-With: StudioSaaS` 头（值不是 XMLHttpRequest）。
