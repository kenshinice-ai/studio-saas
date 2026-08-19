# PWE Studio Edition（单店独立版）· 方案

> **状态：v10.10.2 源码候选（2026-08-16），未提交、未打包、未交付。**
> 最后验证的 Edition 运行包仍为 v10.6.3；方案 A，定价已拍板。
> 基于 StudioSaaS v10.10.2 candidate。产品名：**PWE Studio Edition**。

---

## 1. 产品定义

**一句话**：把一个租户的完整四界面（门户 / 快速报名 / 运营 CMS / Studio
Admin）作为**独立软件包**整体交付给客户，部署在客户自己（或我们代管）的
服务器上，**完全脱离平台 Super Admin 的管理**。

**商业模型**：

| 阶段 | 内容 | 收费 |
|---|---|---|
| 交付 | 环境搭建 + 品牌配置 + 数据迁移 + 上线验收 | **一次性 setup 费**（详见 COMMERCIAL.md） |
| 后期 | 版本升级 / 备份代管 / 故障响应 / 功能咨询 | **单独的维护协议**，按选购计费 |
| 不含 | 平台侧任何服务 —— 无 Super Admin、无支持模式、无平台数据通道 | — |

**与 SaaS 版的关系**：同一套产品能力，两种交付形态。SaaS 版按月订阅、
平台托管；独立版一次买断部署权、数据与运维主权归客户。

## 2. 独立版里「有什么、没什么」

| | SaaS 版 | 独立版 |
|---|---|---|
| 门户 / 报名 / CMS / Studio Admin | ✅ | ✅ 完整保留 |
| 多租户 | ✅ | ❌ 恰好一个租户，安装时固化 |
| Super Admin 控制台 | ✅ 平台方 | ❌ **整面关闭**（路由 404） |
| 平台支持模式（super admin 进店） | ✅ 审计后可进 | ❌ 概念不存在 |
| 套餐/订阅/用量计费 | ✅ | ❌ 关闭（无 plan 限制或设为无限） |
| 租户生命周期（试用/逾期/归档） | ✅ | ❌ 固定 active |
| 角色权限（owner→staff）/ 审计 / 双语 / 主题 | ✅ | ✅ 完整保留 |
| 数据归属 | 平台库中一租户 | **客户自己的独立数据库** |
| 更新方式 | 平台统一发布 | 发布包交付，维护协议内代装 |

## 3. 技术路线（已确定）

### 当前交付方案：同一代码库 + `STUDIOSAAS_MODE=standalone`
同一仓库、同一发布流程，通过 standalone 运行模式交付：
- 启动时要求库中**恰好一个 active 租户**（安装脚本创建），否则拒绝启动；
- `/platform-admin`、`/super-admin`、`/v1/admin/*`、`/v1/plans*` 写路径全部 404/关闭；
- 平台成员（tenant_id IS NULL 的 super_admin）不允许存在；
- plan 限制读取为无限（或安装时写入一个 unlimited plan 行）；
- 根路径 `/` 直接跳转到该租户门户（而非 super-admin）。

当前状态：独立版启动不变量、平台面关闭、租户边界、导入校验、升级回滚和
独立版打包验证均已实现；每次交付仍必须以正式 Edition 包和交付日验收为准。

### 方案 B：fork 出精简代码库
删掉平台面后单独维护。优点是包更小；缺点是**双份维护成本随时间线性
增长**，与本项目「modular monolith、不过早分裂」的架构政策相悖。**不推荐**。

### 方案 C：复用 legacy 单店 CMS（server.py 旧版 /api）
旧版单店模式还在（`STUDIOSAAS_ENABLE_LEGACY_CMS=1`），但它是 v7 之前的
JSON 文件形态：无角色权限、无审计、无门户/品牌系统，已被平台面 410。
**只适合作为历史参考，不适合作为交付产品。不推荐。**

## 4. 文档索引（本文件夹）

| 文件 | 内容 |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | 必须环境：硬件/系统/依赖/网络/域名 |
| [DATABASE.md](DATABASE.md) | 独立数据库、平台→独立的数据迁移路径 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | 部署方式（Docker 主路径 + 裸机备选）、更新与回滚 |
| [DEPLOYMENT_PLAN.md](DEPLOYMENT_PLAN.md) | 面向客户与实施人员的完整部署方案、前提、安装和签收清单 |
| [COMMERCIAL.md](COMMERCIAL.md) | 收费结构、交付边界、维护协议档位 |
| [RUNBOOK.md](RUNBOOK.md) | **实施工程师**交付日手册（安装/TLS/备份/验收/交接/回滚） |
| [OPERATIONS.md](OPERATIONS.md) | **客户版**操作手册（备份自查、恢复、故障自查、更新、联系方式） |
| [templates/](templates/) | 学员导入模板（CSV + 转换器），仅「现有系统迁入」路径需要 |
| `install.sh` / `docker-compose.edition.yml` | 安装向导与单机 compose（最小权限应用 DB 角色、稳定配置/备份目录） |
| `upgrade.sh` | 升级前自动数据库备份、稳定 `current` 切换、健康失败自动回滚 |
| `tools/` | 平台侧导出 + 独立版导入（manifest 校验、空库前置、账本对账） |

## 5. 已拍板决策（2026-07-29）

1. **技术路线：方案 A**（同代码库 + `STUDIOSAAS_MODE=standalone`）。
2. **交付定价**：启程 $1,499 / 主场 $2,999 / 开幕 $4,999（差异见
   COMMERCIAL.md §1）。
3. **部署位置两个选项**：客户云账号（$1,499 入门档默认）或我们代管
   （体现在 $4,999 档内含；$2,999 档可加购）。
4. **维护协议**：守护 $499 / 护航 $1,499 / 托管 $2,999 每年；入门档
   含**每年 2 次升级 + 年度安全审计**。无维护客户享**免费 1 次更新**
   （12 个月内），此后单次收费。
5. **回迁 SaaS**：通道长期保留，价格按当时规模详谈。
6. **页脚署名**：默认保留；去署名一次性 **$499**。
7. **产品名**：**PWE Studio Edition**（正式名）。

运行时默认通过 `/v1/health` 的 `showProducerCredit=true` 展示署名；已购买
去署名选项的交付在稳定配置中设置：

```bash
STUDIOSAAS_SHOW_PRODUCER_CREDIT=0
```

除明确的 `0/false/no/off` 与 `1/true/yes/on` 外，其他值会让配置校验失败，
不会静默猜测。

## 6. v10.10.2 Edition 候选交付基线（尚未发布）

1. ✅ 后端 `STUDIOSAAS_MODE=standalone` 开关 + 启动校验 + 路由关闭
   —— `config.is_standalone()`（每次读环境，不缓存）、`server` 启动不变量
   （恰一 active 租户 + 零平台成员，安装器可用 `STUDIOSAAS_SKIP_STANDALONE_CHECKS=1`
   越过首次引导）、`api_v1` 前置钩子关掉 `/v1/admin/*` 与套餐写路径、
   `/` 跳单租户门户、plan 限额中性化、两个 seed 脚本拒绝执行。
   当前版本要求数据库**总共恰好一个租户且必须 active**，并禁止任何
   `tenant_id IS NULL` 平台成员，不再只检查 active 记录。
2. ✅ `standalone-edition/install.sh` 安装向导（Docker 一条命令，含首次引导、
   `/etc/pwe-studio` secrets、`/var/lib/pwe-studio` 数据库备份、root cron、
   运维 wrapper、TLS 命令打印、验收清单回显、`--force-reinstall` 二次确认）
3. ✅ 导出/导入工具 `tools/export_tenant_bundle.py`（只读，复用
   `tenant_archive.SNAPSHOT_TABLES` 单一清单）→ `tools/import_tenant_bundle.py`
   （可信整包 SHA-256、数据库与媒体逐文件哈希、空库前置、剔平台成员、
   重置密码、账本双向对账）
4. ✅ 独立版专属 isolation 检查组（`backend/test_standalone_mode.py`、
   `backend/test_tenant_isolation.py`）+ 打包脚本 `--edition` 参数
   （`deploy/aws/build_aws_bundle.sh`，产物 `PWE-Studio-Edition-<ver>.tar.gz`，
   `BUILD_INFO` 记 `mode=standalone`）
5. ✅ `upgrade.sh` 使用稳定 `releases/shared/current` 边界，升级前备份，
   健康失败自动恢复上一代码与配置；应用运行使用 `studiosaas_app`
   最小权限角色，迁移权限在 server 启动前用完即移除。
6. ✅ 交付 runbook [RUNBOOK.md](RUNBOOK.md)（实施工程师）+ 客户版操作手册
   [OPERATIONS.md](OPERATIONS.md)（工作室负责人）+ 学员导入模板
   [templates/](templates/)（CSV 模板 + 转换器，转换即用服务端同一函数校验）

> **当前交付边界**：媒体文件的独立备份自动化和默认异地副本暂不包含在标准
> Edition 安装中。PostgreSQL 每日备份已经闭环；媒体 Docker volume 会在
> 应用升级中保留，但不能视为服务器故障后的可恢复副本。

**端到端实测**（scratch PostgreSQL 库，两条数据路径 + 三个负例）：

| 场景 | 结果 |
|---|---|
| 平台导出 → 空库导入 → standalone 启动 | 30 表 163 行；账本 165.00 包内=库内；平台成员 0；`/`→`/lets-paint-studio`、`/super-admin`→404 |
| CSV → JSON → 导入 → standalone 启动 | 3 名学员（含 1 归档）；期初 16.50 记为单条 `migration` 账本行 |
| 导出对平台库的副作用 | 无：租户仍 `active`，`tenant_archives` 0 行 |
| 二次导入非空库 | 拒绝，exit 1 |
| 篡改包（改一个 JSON 字节） | sha256 拦下，中英文说明，exit 1 |

---

*A PARADISE PRODUCTION · 天域文创出品*
