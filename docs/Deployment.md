# StudioSaaS Deployment Guide

Version: v8.1.0
Date: 2026-07-31（Stage 2 上线记录：2026-07-30）
Scope: 生产运行于 AWS Lightsail 单实例，域名 `https://pwestudio.online`，
当前版本 v8.1.0（21 项迁移已应用）。
本地部署仍是开发与验证路径；**Cloudflare Tunnel 已退出生产链路，仅供本地开发**，
不得再为该域名重新引入。生产事实与实测证据见
[`HANDOFF_LATEST.md`](HANDOFF_LATEST.md) §0，操作命令见 §0.2。

部署路径分三个阶段，每个阶段都是上一阶段的超集，数据与代码不推倒重来：

| 阶段 | 形态 | 目的 | 状态 |
|---|---|---|---|
| Stage 0 | 本地 Mac：waitress + 本机 PostgreSQL | 开发与全量验证 | 使用中 |
| Stage 1 | Stage 0 + cloudflared tunnel → `studiosaas.cc.cd` | 早期邀请测试 | 已退役为本地开发用途 |
| Stage 2 | AWS Lightsail 单实例：host nginx 终止 TLS + 容器内 PostgreSQL 16 + 本机媒体卷 | 生产 | **已上线 2026-07-30** |

Stage 2 实际落地形态与下文 3.1 的早期设计不同：**未采用 RDS / S3 / SES**。
数据库与媒体都在同一实例上，每日逻辑备份加媒体卷归档由 cron 执行，恢复演练已通过；
异地备份副本、监控与 SLA 仍未完成，且在客户文档中如实披露为未完成。

---

## 1. Stage 0 — 本地部署（已验证）

### 1.1 启动

```bash
# 依赖（一次性）
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt

# 数据库（一次性）
createdb -h localhost -p 5432 studiosaas_local_test
cd backend && python scripts/run_migrations.py
STUDIOSAAS_ADMIN_PASSWORD='<strong unique local secret>' \
  python scripts/seed_super_admin.py
python scripts/seed_local_test_tenants.py

# 启动
PORT=8901 STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
  .venv/bin/python backend/server.py
# 或直接: ./start_studiosaas_local.sh
```

### 1.2 验证基线（v8.1.0）

| 检查 | 命令 | 期望 |
|---|---|---|
| 健康 | `curl localhost:8901/v1/health` | `{"ok":true,...}` |
| pytest | `cd backend && ../.venv/bin/python -m pytest -q` | 全绿、不得以 skip 绕过 PostgreSQL gate |
| CMS 冒烟 | `../.venv/bin/python test_cms.py` | 73 通过 |
| 租户隔离 | `../.venv/bin/python test_tenant_isolation.py` | 需包含品牌草稿/发布/恢复、角色权限、来源漏斗与跨租户检查 |
| 页面 | `/`、`/<slug>`、`/<slug>/cms`、`/<slug>/register`、`/<slug>/studio-admin` | 200；根 `/register` 404 |

---

## 2. Stage 1 — Cloudflare Tunnel 公网试点（已退役为本地开发用途）

> **本节自 2026-07-30 起不再描述生产。** 生产在 AWS Lightsail 上有静态 IP 与
> Route 53 委派，隧道会额外引入一个第三方跳转、第二份需要轮换的凭据，并与
> certbot HTTP-01 争夺同一主机名。隧道保留下来只为在没有公网 IP 的机器上做
> 本地演示；`pwestudio.online` 不得再启用它。生产链路见
> [`HANDOFF_LATEST.md`](HANDOFF_LATEST.md) §0。

### 2.1 原理

`cloudflared` 从本机向 Cloudflare 建立出站连接，无需公网 IP / 端口转发 / 路由器配置。HTTPS 证书由 Cloudflare 边缘自动提供。

```
访客 → https://studiosaas.cc.cd (Cloudflare 边缘, TLS)
     → tunnel (出站长连接)
     → 本机 cloudflared → http://localhost:8901 (waitress)
```

### 2.2 一次性配置

```bash
# 1. 授权（浏览器登录 Cloudflare，选择 cc.cd 域）
cloudflared tunnel login          # 生成 ~/.cloudflared/cert.pem

# 2. 建隧道
cloudflared tunnel create studiosaas   # 生成 ~/.cloudflared/<TUNNEL_ID>.json 凭据

# 3. DNS 绑定（在 cc.cd 区创建 studiosaas 的 CNAME → tunnel）
cloudflared tunnel route dns studiosaas studiosaas.cc.cd

# 4. 配置文件 ~/.cloudflared/config.yml
tunnel: <TUNNEL_ID>
credentials-file: /Users/llmacbookpro/.cloudflared/<TUNNEL_ID>.json
ingress:
  - hostname: studiosaas.cc.cd
    service: http://localhost:8901
  - service: http_status:404
```

### 2.3 运行（按需模式，2026-07-09 定稿）

试点采用**按需开关**，不装常驻服务：

| 操作 | 方式 |
|---|---|
| 开始公网测试 | 双击 `START_STUDIOSAAS_ONLINE.command`（从项目内 `.runtime` 读取环境/CMS/Tunnel 文件 → 数据库迁移 → 保留全部现有密码 → 本地健康 → 隧道 → 公网健康；不重灌业务数据） |
| 结束测试 | 关闭该终端窗口，或双击 `STOP_STUDIOSAAS_ONLINE.command` |
| 测试前备份 | 双击 `BACKUP_STUDIOSAAS_NOW.command` |
| 本地开发（默认保留真实数据） | `START_STUDIOSAAS_LOCAL.command`（仅在显式设置 `STUDIOSAAS_SEED_DEMO=1` 时生成 demo 学员） |

若将来要常驻：LaunchAgent 模板在 `deploy/launchd/`，`bash deploy/install_launch_agents.sh` 一键安装（备份定时 + 隧道自愈）。

### 2.4 公网试点安全清单（开 tunnel 前逐项确认）

| # | 项 | 状态 / 操作 |
|---|---|---|
| 1 | v1 限流/审计使用真实访客 IP（信任来自 localhost 的 `CF-Connecting-IP`） | ✅ 2026-07-09（api_v1.py `_client_ip()`） |
| 2 | Secure cookie | ✅ 2026-07-09：隧道来源的请求自动给 session cookie 加 Secure（自定义 SessionInterface）；本地 http 开发不受影响；`COOKIE_SECURE=1` 全局强制仍可用 |
| 3 | 特权密码 | 源码无固定特权密码。启动器默认保留现有 hash；只有显式提供 `STUDIOSAAS_ADMIN_PASSWORD` 时才创建/重置账号并更新 0600 本机凭据文件。永久生产部署前仍须独立轮换并加 Cloudflare Access 等第二层保护。 |
| 4 | 备份 | ✅ 2026-07-09：`BACKUP_STUDIOSAAS_NOW.command` 一键备份（keep 14）；恢复演练通过（restore-dry-run，10 迁移核验）；按需模式不装定时，模板在 `deploy/launchd/` |
| 5 | super-admin 面收紧 | `/platform-admin` 直接显示应用登录并继续执行平台级 RBAC；`/super-admin*` 可保留 Cloudflare Access 邮箱 OTP 作为双重保护入口。两条入口共享同一受保护 API，不能用隐藏 slug 代替鉴权。 |
| 6 | Cloudflare 区设置 | 建议开 Bot Fight Mode（仪表盘）；SSL/TLS 模式无所谓（tunnel 不走 origin 证书） |

### 2.5 试点验证

```bash
curl -sS https://studiosaas.cc.cd/v1/health
# 手机 4G（非 WiFi）打开 https://studiosaas.cc.cd/lets-paint-studio/register 提交注册
# CMS 手机上传照片（验证 S1/S2 的 HEIC + SW 修复在真机生效）
```

所有验证通过并提交后生成可复现发布包：

```bash
cd backend
bash scripts/package_release.sh
```

当前候选的逐项证据和未关闭阻塞项记录在
[`Release_Readiness_2026-07-12.md`](Release_Readiness_2026-07-12.md)。AWS 已于
2026-07-30 上线，但这不豁免任何一项：迁移、媒体衍生图检查、真实 PostgreSQL
隔离测试与本地浏览器链路仍是每次发布的必过项。

---

## 3. Stage 2 — AWS 正式部署（已上线 2026-07-30）

> **生产已上线。** 实际形态是 Lightsail 单实例 + host nginx 终止 TLS +
> 容器内 PostgreSQL 16 + 本机媒体卷，**未使用 RDS / S3 / SES**。实测事实、
> 边缘加固决策（含刻意不开 OCSP stapling 的原因）与运维命令见
> [`HANDOFF_LATEST.md`](HANDOFF_LATEST.md) §0–§0.3；下文 3.1 是上线前的目标
> 架构记录，与实际落地不同，保留作为决策留痕。
>
> 仍未完成、且在客户文档中如实披露为未完成：异地备份副本、可用性监控与备份
> 失败告警、值班归属与合同化 SLA、特权账号 MFA。

> **部署套件已随仓库发布：`deploy/aws/`**（Dockerfile、docker-compose、nginx、
> systemd、`.env.example`、`build_aws_bundle.sh`）。逐步操作手册见
> [`deploy/aws/README_AWS.md`](../deploy/aws/README_AWS.md)；打包命令：
>
> ```bash
> bash deploy/aws/build_aws_bundle.sh <version>
> # → dist/PWE-StudioSaaS-aws-<version>.tar.gz (+ .sha256，内含 BUILD_INFO)
> ```
>
> 下文 3.1–3.3 是架构与迁移决策记录；具体命令以 README_AWS.md 为准。

### 3.1 目标架构（试点后第一版，单可用区，成本优先）

```
Route53/Cloudflare DNS
  → EC2 t4g.small (ARM, Ubuntu 24.04)
      nginx (TLS 终止, 静态缓存) → waitress :8901
  → RDS PostgreSQL 16 (db.t4g.micro, 20GB gp3, 自动快照 7 天)
  → S3 (媒体文件, P3-03 storage_provider 切换)
  → SES (注册/审批邮件, 替换 console backend)
```

预估月成本（悉尼 ap-southeast-2）：EC2 ~US$15 + RDS ~US$15-19 + EBS/快照/流量 ~US$5 ≈ **US$35-45/月**（2026-07 审计校准）。

**数据驻留与加密**：全部数据静态存储于 ap-southeast-2；RDS 与 EBS 均开启
storage encryption。备份三层：RDS 自动快照 + 每日 pg_dump cron（写入持久卷，
0600，14 份滚动）+ EBS DLM 卷快照（覆盖媒体/归档/租户工作区——它们不在
pg_dump 里）。具体命令见 `deploy/aws/README_AWS.md` §9。
更省的替代：Lightsail $10 套餐（同机 Postgres）≈ US$10/月，但放弃 RDS 快照/监控，试点期可接受。

### 3.2 迁移步骤

1. **P3-01 配置分层**（前置代码任务）：`STUDIOSAAS_ENV=production` 时强制 `COOKIE_SECURE=1`、拒绝缺省 secret、结构化访问日志落文件。
2. **建 RDS**：PostgreSQL 16，私有子网，仅允许 EC2 安全组访问；`run_migrations.py` 建 schema。
3. **数据迁移**：本地 `pg_dump studiosaas_local_test | psql <RDS_URL>`；媒体目录 `aws s3 sync media/ s3://<bucket>/media/`。
4. **P3-03 S3 媒体分支**：media service 按 `storage_provider` 切 S3（boto3），本地回退保留。
5. **EC2 部署**：systemd 服务运行 waitress；nginx 反代 + Let's Encrypt（或继续 Cloudflare 代理橙云，origin 用 Cloudflare Origin Cert）。
6. **nginx 层透传真实 IP**：`proxy_set_header X-Forwarded-For`；`_client_ip()` 的 localhost 信任规则天然兼容（nginx 与应用同机）。
7. **CI/CD（P3-02）**：GitHub Actions — push main → ssh 部署脚本（pull + migrations + systemctl restart）；发布前跑 pytest + verify_local。
8. **DNS 切换**：`studiosaas.cc.cd` CNAME 从 tunnel 改指 EC2（或保留 Cloudflare 代理）。tunnel 保留为回滚通道 48h。
9. **回滚方案**：DNS 切回 tunnel + 本地库从迁移时刻快照恢复（迁移期间冻结写入或接受数据差）。

### 3.3 扩容路线（Phase 3+，按 Roadmap 排期，勿提前）

多实例时才需要：ALB + 2×EC2（限流迁 Redis/ElastiCache）、RDS Multi-AZ、CloudFront 挂 S3 媒体、ECS Fargate 容器化。试点阶段明确不做。

---

## 4. 环境变量总表

| 变量 | Stage 0 | Stage 1 (tunnel) | Stage 2 (AWS) |
|---|---|---|---|
| `STUDIOSAAS_DATABASE_URL` | 本机 postgres | 同左 | RDS URL（Secrets Manager） |
| `PORT` | 8901 | 8901 | 8901（nginx 上游） |
| `COOKIE_SECURE` | 不设 | **1** | **1**（P3-01 后 production 强制） |
| `STUDIOSAAS_ENV` | local | local | production |
| `STUDIOSAAS_API_KEY` | 自动生成的本地文件 | 独立强随机值 | Secrets Manager |
| `STUDIOSAAS_SESSION_SECRET` | 自动生成的本地文件 | 与 API key 不同的强随机值 | Secrets Manager |
| `STUDIOSAAS_MEDIA_DIR` | `backend/media` | 持久化本地目录 | S3 adapter 前使用持久卷（P3-03） |
| `STUDIOSAAS_DB_CONNECT_TIMEOUT` | 默认 5（秒，v7.4.1） | 同左 | 按需调优 |
| `STUDIOSAAS_DB_STATEMENT_TIMEOUT_MS` | 默认 30000（v7.4.1） | 同左 | 按需调优 |
| `STUDIOSAAS_DB_LOCK_TIMEOUT_MS` | 默认 10000（v7.4.1） | 同左 | 按需调优 |
| `STUDIOSAAS_ENABLE_LEGACY_CMS` | 不设（local 下旧版 `/api/*` 可用） | 不设 | 不设——pilot/production 下旧版 `/api/*` 返回 410；仅单工作室安装显式设 `1`（v7.4.0） |
| SMTP（notifications） | console | console/SMTP | SES SMTP |
