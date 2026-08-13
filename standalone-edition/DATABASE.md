# PWE Studio Edition · 数据库与数据迁移

> 当前正式交付基线：v9.9.5。本文描述标准 Docker Compose Edition；完整
> 安装、TLS、备份和签收顺序见 [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md)。

## 1. 数据库形态

- 客户**独立的 PostgreSQL 16 库**，schema 与平台版完全一致；正式包启动时
  按仓库中的有序迁移执行，`schema_migrations` 簿记保留，未来升级继续走
  同一迁移机制。
- 库中**总共恰好一个租户且状态必须为 active**，安装时创建并固化；
  standalone 模式启动校验强制此不变量，归档/停用的额外租户同样拒绝
- **不存在任何** `tenant_id IS NULL` 的平台成员行（不论角色和状态）；
  plans 表写入 `edition` unlimited 行，运行时 plan 容量与 feature 检查同时
  在 standalone 模式中性化
- 数据库 owner `studiosaas` 只用于启动迁移、角色授权和受控恢复；
  server.py 使用 `studiosaas_app` 最小权限角色运行（CRUD，无
  SUPERUSER/CREATEDB/CREATEROLE/schema ownership）

多租户 schema 保留租户列的代价（每表一个 uuid 列）换来的是：
平台↔独立版**双向迁移零 schema 转换**，且所有隔离测试语义不变。

## 2. 三条数据来源路径

### 路径 1：从 SaaS 平台迁出（老客户转独立版）
1. 平台侧：支持会话下执行租户导出 —— 复用 `tenant_archive.py`
   快照机制（全量 JSON，含同意链证据）+ 媒体目录
   打包（`media/<tenant>/` + photos + portfolio）
2. 独立侧：`install.sh --import-bundle <包> --expected-bundle-sha256 <平台记录值>`
   建库→跑迁移→验证可信整包 SHA→导入快照→校验计数、媒体清单与账本一致性
3. 平台侧收尾：按合同约定归档或删除原租户（永久删除有确认短语 +
   最终快照，流程已有）

> 实现说明：tenant_archive 快照当前是「归档」用途，导入器是本方案
> 新增件（快照 JSON → INSERT 序列，schema 相同所以是直录）。

### 路径 2：从客户现有系统迁入（新客户）
沿用 lets-paint-studio 实战验证过的核心导入流程
（`import_lets_paint_json.py` 模式）：学员档案 + 期初课时余额走
migration 账本行；套餐 upsert；历史流水按「只保留核心」原则不迁。
Excel 来源由实施工程师转 JSON（模板随交付包提供）。

### 路径 3：全新开店（无历史数据）
安装向导直接建租户 + owner + 行业预设，当天可用。

## 3. 备份与恢复（交付默认配置）

- root-owned `/etc/cron.d/pwe-studio-<slug>-backup` 每日调用
  `backup_postgres.py backup`，写入
  `/var/lib/pwe-studio/<slug>/backups/postgres`。
- dump 和 manifest 均为 `0600`，默认保留最近 14 份，并记录迁移版本和关键
  表计数。
- 恢复演练使用 owner 连接创建临时同级数据库，恢复后比较 migration inventory
  和关键表计数，再删除临时数据库。
- 真实恢复必须使用 `--confirm studiosaas`，先停止应用写入，并由客户明确
  批准；备份点之后的报名、课次、账本和配置会丢失。
- 媒体/照片自动备份和默认异地副本不属于标准 Edition 安装。named volume
  只保证应用升级时不主动删除媒体，不能覆盖整台服务器损坏。
- 异地数据库副本、媒体备份、监控和灾备演练属于维护协议或定制项目。

## 4. 迁移完整性规则

- 原始文件由客户或数据负责人授权提供，并保留不可变原件和 SHA-256。
- 每个学生、课程和套餐应有稳定 external ID；不能只用姓名、电话或邮箱
  自动去重。
- 重复、缺失、非法日期、余额不一致和含义不明确的字段必须进入例外清单。
- 不猜测、不静默丢弃、不自动合并；最终导入前必须由客户批准映射和例外。
- 最终切换前冻结源系统，执行一次 rehearsal，完成计数、样本记录、期初余额
  和流水总额对账，再执行正式导入。

## 5. 数据层验收证据

至少记录以下对账项：

| 项目 | 来源数量/金额 | Edition 数量/金额 | 结果 |
|---|---:|---:|---|
| 学员 |  |  |  |
| active 学员 |  |  |  |
| 课程 |  |  |  |
| 套餐 |  |  |  |
| 期初课时余额 |  |  |  |
| 课时流水金额 |  |  |  |
| 媒体文件 |  |  |  |
| 被拒绝或待确认记录 |  |  |  |

## 6. 与平台版的差异清单（数据层）

| 项 | 平台版 | 独立版 |
|---|---|---|
| tenants 行数 | N | 总数恰好 1 且 active（启动校验） |
| 平台成员 | 有 | `tenant_id IS NULL` 的任何成员均禁止 |
| plans / subscriptions | 商业计费 | 单行 unlimited / 短路 |
| tenant_usage 用量结算 | 平台巡检 | 保留但仅作自检展示 |
| audit_logs | 平台+租户两级 | 仅租户级（owner 可见，已有端点） |
| demo_seed_locked | 真实租户加锁 | 安装即全库加锁（防误 seed） |
