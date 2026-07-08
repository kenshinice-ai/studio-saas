# StudioSaaS Deployment Guide

Version: v1.0
Date: 2026-07-09
Scope: 本地部署 → Cloudflare Tunnel 公网试点（`https://studiosaas.cc.cd`）→ AWS 正式部署。

部署路径分三个阶段，每个阶段都是上一阶段的超集，数据与代码不推倒重来：

| 阶段 | 形态 | 目的 |
|---|---|---|
| Stage 0 | 本地 Mac：waitress + 本机 PostgreSQL | 开发与全量验证 |
| Stage 1 | Stage 0 + cloudflared tunnel → `studiosaas.cc.cd` | 公网试点测试（真实手机/家长注册链路） |
| Stage 2 | AWS：EC2/Lightsail + RDS PostgreSQL + S3 媒体 | 正式多租户运营 |

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
python scripts/seed_super_admin.py && python scripts/seed_local_test_tenants.py

# 启动
PORT=8899 STUDIOSAAS_DATABASE_URL=postgresql://$(whoami)@localhost:5432/studiosaas_local_test \
  .venv/bin/python backend/server.py
# 或直接: ./start_studiosaas_local.sh
```

### 1.2 验证基线（2026-07-09 全绿）

| 检查 | 命令 | 期望 |
|---|---|---|
| 健康 | `curl localhost:8899/v1/health` | `{"ok":true,...}` |
| pytest | `cd backend && ../.venv/bin/python -m pytest -q` | 37 passed |
| CMS 冒烟 | `../.venv/bin/python test_cms.py` | 72 通过 |
| 租户隔离 | `../.venv/bin/python test_tenant_isolation.py` | 110 passed |
| 页面 | `/`、`/<slug>`、`/<slug>/cms`、`/<slug>/register`、`/<slug>/studio-admin` | 200；根 `/register` 404 |

---

## 2. Stage 1 — Cloudflare Tunnel 公网试点

### 2.1 原理

`cloudflared` 从本机向 Cloudflare 建立出站连接，无需公网 IP / 端口转发 / 路由器配置。HTTPS 证书由 Cloudflare 边缘自动提供。

```
访客 → https://studiosaas.cc.cd (Cloudflare 边缘, TLS)
     → tunnel (出站长连接)
     → 本机 cloudflared → http://localhost:8899 (waitress)
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
    service: http://localhost:8899
  - service: http_status:404
```

### 2.3 运行（按需模式，2026-07-09 定稿）

试点采用**按需开关**，不装常驻服务：

| 操作 | 方式 |
|---|---|
| 开始公网测试 | 双击 `START_STUDIOSAAS_ONLINE.command`（起服务+隧道；不重灌数据不重置密码；关窗即停） |
| 结束测试 | 关闭该终端窗口，或双击 `STOP_STUDIOSAAS_ONLINE.command` |
| 测试前备份 | 双击 `BACKUP_STUDIOSAAS_NOW.command` |
| 本地开发（会重灌 demo 数据） | `START_STUDIOSAAS_LOCAL.command`（保留轮换后的 super admin 密码） |

若将来要常驻：LaunchAgent 模板在 `deploy/launchd/`，`bash deploy/install_launch_agents.sh` 一键安装（备份定时 + 隧道自愈）。

### 2.4 公网试点安全清单（开 tunnel 前逐项确认）

| # | 项 | 状态 / 操作 |
|---|---|---|
| 1 | v1 限流/审计使用真实访客 IP（信任来自 localhost 的 `CF-Connecting-IP`） | ✅ 2026-07-09（api_v1.py `_client_ip()`） |
| 2 | Secure cookie | ✅ 2026-07-09：隧道来源的请求自动给 session cookie 加 Secure（自定义 SessionInterface）；本地 http 开发不受影响；`COOKIE_SECURE=1` 全局强制仍可用 |
| 3 | 默认密码 | ✅ 2026-07-09：7 个特权账号全部轮换，新密码在 `~/.studiosaas/pilot-credentials.txt`（600）；LOCAL 启动脚本会沿用轮换密码 |
| 4 | 备份 | ✅ 2026-07-09：`BACKUP_STUDIOSAAS_NOW.command` 一键备份（keep 14）；恢复演练通过（restore-dry-run，10 迁移核验）；按需模式不装定时，模板在 `deploy/launchd/` |
| 5 | super-admin 面收紧 | ⚠️ 手动：Cloudflare Zero Trust → Access → 给 `studiosaas.cc.cd/super-admin*` 加邮箱 OTP 策略（仪表盘操作，见 Current_Sprint P0-5） |
| 6 | Cloudflare 区设置 | 建议开 Bot Fight Mode（仪表盘）；SSL/TLS 模式无所谓（tunnel 不走 origin 证书） |

### 2.5 试点验证

```bash
curl -sS https://studiosaas.cc.cd/v1/health
# 手机 4G（非 WiFi）打开 https://studiosaas.cc.cd/lets-paint-studio/register 提交注册
# CMS 手机上传照片（验证 S1/S2 的 HEIC + SW 修复在真机生效）
```

---

## 3. Stage 2 — AWS 正式部署

### 3.1 目标架构（试点后第一版，单可用区，成本优先）

```
Route53/Cloudflare DNS
  → EC2 t4g.small (ARM, Ubuntu 24.04)
      nginx (TLS 终止, 静态缓存) → waitress :8899
  → RDS PostgreSQL 16 (db.t4g.micro, 20GB gp3, 自动快照 7 天)
  → S3 (媒体文件, P3-03 storage_provider 切换)
  → SES (注册/审批邮件, 替换 console backend)
```

预估月成本（悉尼 ap-southeast-2）：EC2 ~US$12 + RDS ~US$13 + S3/流量 ~US$3 ≈ **US$30/月**。
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
| `PORT` | 8899 | 8899 | 8899（nginx 上游） |
| `COOKIE_SECURE` | 不设 | **1** | **1**（P3-01 后 production 强制） |
| `STUDIOSAAS_ENV` | local | local | production |
| `STUDIOSAAS_MEDIA_ROOT` | ./media | ./media | S3 (P3-03) |
| SMTP（notifications） | console | console/SMTP | SES SMTP |
