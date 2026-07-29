# StudioSaaS — AWS 部署包说明 (Stage 2)

本目录是随代码一起发布的 AWS 部署套件。目标架构与成本估算见
`docs/Deployment.md` §3（EC2 t4g.small + RDS PostgreSQL 16 + S3 ≈ US$30/月）。

```
deploy/aws/
├── README_AWS.md          # 本文（打包后复制为 bundle 根部的 DEPLOY_AWS_FIRST.md）
├── Dockerfile             # 生产镜像（python:3.11-slim + waitress）
├── entrypoint.sh          # 等库 → 迁移 → 启动；生产模式强制校验 secrets
├── docker-compose.yml     # Docker 路径；`--profile local-db` 可单机彩排
├── .env.example           # 环境变量模板（真实值放 Secrets Manager）
├── nginx/studiosaas.conf  # 主机 nginx：TLS 终止 + 反代 127.0.0.1:8899
├── systemd/studiosaas.service  # 非 Docker 路径（venv + waitress + systemd）
└── build_aws_bundle.sh    # 从干净 git 树打出 dist/PWE-StudioSaaS-aws-<ver>.tar.gz
```

两条部署路径任选其一：**A. Docker（推荐）** 或 **B. 裸机 systemd**。
两条路径共享同样的 nginx、RDS、环境变量与安全清单。

---

## 1. 打包（在开发机上）

```bash
bash deploy/aws/build_aws_bundle.sh <version>
# → dist/PWE-StudioSaaS-aws-<version>.tar.gz (+ .sha256)
```

要求 git 工作树干净；bundle 内含 `BUILD_INFO`（版本 + commit + 构建时间）。
上传到 EC2：

```bash
scp dist/PWE-StudioSaaS-aws-<version>.tar.gz ubuntu@<EC2_IP>:~
```

## 2. AWS 资源准备（一次性）

| 资源 | 规格 | 要点 |
|---|---|---|
| EC2 | t4g.small, Ubuntu 24.04 ARM | 安全组只开 80/443（+ 你的 IP 的 22） |
| RDS | PostgreSQL 16, db.t4g.micro, 20GB gp3 | 私有子网；安全组仅允许 EC2 SG；自动快照 7 天 |
| S3 | 媒体桶（P3-03 之前可暂缓） | 阻止公开访问；由应用代理读写 |
| Secrets Manager | `studiosaas/prod` | 存 DATABASE_URL、SESSION_SECRET、API_KEY |
| DNS | `studiosaas.cc.cd` → EC2 | 保留 Cloudflare tunnel 作 48h 回滚通道 |

生成两个互不相同的强随机密钥：

```bash
openssl rand -hex 32   # STUDIOSAAS_SESSION_SECRET
openssl rand -hex 32   # STUDIOSAAS_API_KEY
```

**最小权限数据库角色（必做）**：不要让应用使用 RDS master 用户。用 master
连上后创建专属角色，应用连接串只用它（并强制 `?sslmode=require`）：

```sql
CREATE ROLE studiosaas_app LOGIN PASSWORD '<strong-random>';
CREATE DATABASE studiosaas OWNER studiosaas_app;
-- 迁移与运行时同用此角色即可；它拥有自己的库，无实例级权限。
```

**数据驻留与加密**：所有数据静态存储于 ap-southeast-2；建 RDS 时勾选
storage encryption（默认 KMS 键即可），EBS 卷同样勾选加密。

## 3. 路径 A — Docker（推荐）

```bash
# EC2 上（一次性）：安装 docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 nginx
sudo usermod -aG docker ubuntu && newgrp docker

# 解包
tar xzf PWE-StudioSaaS-aws-<version>.tar.gz && cd PWE-StudioSaaS-aws-<version>

# 配置环境（真实值从 Secrets Manager 取出）
cp deploy/aws/.env.example deploy/aws/.env && chmod 600 deploy/aws/.env
vim deploy/aws/.env    # 填 STUDIOSAAS_DATABASE_URL / SESSION_SECRET / API_KEY

# 首次启动（自动跑迁移；首启临时设 STUDIOSAAS_SEED_SUPER_ADMIN=1）
docker compose -f deploy/aws/docker-compose.yml --env-file deploy/aws/.env up -d --build
docker compose -f deploy/aws/docker-compose.yml logs -f app   # 看到 waitress 启动即成功
curl -fsS http://127.0.0.1:8899/v1/health
```

数据落在名为 `studiosaas-data`（CMS json/密钥/照片）与 `studiosaas-media`
（作品集媒体）的 docker volume，升级镜像不丢数据。

**升级**：解包新 bundle → 同一条 `up -d --build`。entrypoint 先跑迁移再起服务。
**回滚**：`docker compose ... down` → 用上一个 bundle 重新 `up -d --build`
（迁移必须向后兼容，同 docs/Release_Runbook.md）。

## 4. 路径 B — 裸机 systemd

```bash
sudo useradd --system --create-home --home /opt/studiosaas studiosaas
sudo mkdir -p /opt/studiosaas/{app,data,media} && sudo mkdir -p /opt/studiosaas/app/backend/archives /opt/studiosaas/app/tenants
sudo tar xzf ~/PWE-StudioSaaS-aws-<version>.tar.gz --strip-components=1 -C /opt/studiosaas/app
cd /opt/studiosaas
sudo python3 -m venv venv && sudo ./venv/bin/pip install -r app/deploy/aws/requirements.lock

# 环境文件（600，root）
sudo tee /opt/studiosaas/studiosaas.env >/dev/null <<'EOF'
STUDIOSAAS_DATABASE_URL=postgresql://...
STUDIOSAAS_SESSION_SECRET=...
STUDIOSAAS_API_KEY=...
COOKIE_SECURE=1
EOF
sudo chmod 600 /opt/studiosaas/studiosaas.env
sudo chown -R studiosaas:studiosaas /opt/studiosaas/data /opt/studiosaas/media

sudo cp app/deploy/aws/systemd/studiosaas.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now studiosaas
systemctl status studiosaas && curl -fsS http://127.0.0.1:8899/v1/health
```

## 5. 密钥管理

生产 entrypoint 会**拒绝启动**缺少 `STUDIOSAAS_SESSION_SECRET` /
`STUDIOSAAS_API_KEY` 的容器，两值相同也会被 server.py 拒绝。推荐流程：

```bash
aws secretsmanager get-secret-value --secret-id studiosaas/prod \
  --query SecretString --output text > deploy/aws/.env && chmod 600 deploy/aws/.env
```

首次部署完成后：

1. `STUDIOSAAS_SEED_SUPER_ADMIN` 改回 `0`；
2. 运行 `backend/scripts/rotate_pilot_credentials.py` 轮换所有特权账号；
3. 给 `/super-admin*` 加第二层保护（Cloudflare Access 邮箱 OTP）。

## 6. nginx + TLS

**顺序很重要**：`studiosaas.conf` 引用的证书在 certbot 运行前不存在，直接装它
`nginx -t` 会失败并卡死 certbot。先装 HTTP 引导配置，让 certbot 自己升级：

```bash
# 1) HTTP-only 引导配置
sudo cp deploy/aws/nginx/studiosaas-bootstrap.conf /etc/nginx/sites-available/studiosaas
sudo ln -s /etc/nginx/sites-available/studiosaas /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# 2) certbot 签发并自动改写为 HTTPS（含 80→443 跳转）
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d studiosaas.cc.cd
sudo nginx -t && sudo systemctl reload nginx
```

`studiosaas.conf` 保留为手工维护的完整参考（server_tokens off、gzip、
20m 上传上限）；certbot 改写后可对照它补齐这几项。走 Cloudflare 橙云的
部署可跳过 certbot，用 Origin Cert 直接填入 studiosaas.conf。

应用只信任来自 localhost 的代理头（`_client_ip()`），与「nginx 与应用同机」
的拓扑天然匹配——不要把 8899 暴露到公网安全组。

## 7. 数据迁移（本地试点 → AWS）

```bash
# 本地
pg_dump "postgresql://$USER@localhost:5432/studiosaas_local_test" \
  --no-owner --no-privileges -Fc -f studiosaas.dump
# EC2（能到达 RDS）
pg_restore --no-owner --no-privileges -d "$STUDIOSAAS_DATABASE_URL" studiosaas.dump

# 媒体 + 旧版 CMS 数据（Docker 路径：拷进对应 volume 并修正属主 —
# 容器以 uid 10001 运行，docker cp 会写成 root 属主导致上传/清理失败）
APP=$(docker compose -f deploy/aws/docker-compose.yml ps -q app)
docker cp media/. "$APP":/media/
docker cp backend/photos "$APP":/data/photos 2>/dev/null || true
docker cp backend/portfolio "$APP":/data/portfolio 2>/dev/null || true
docker compose -f deploy/aws/docker-compose.yml exec -u root app \
  chown -R studiosaas:studiosaas /media /data
```

迁移窗口内冻结本地写入；DNS 切换后保留 tunnel 48h 作回滚。

## 8. 部署后验证清单

```bash
curl -fsS https://studiosaas.cc.cd/v1/health          # {"ok":true,...}
curl -fsS -o /dev/null -w '%{http_code}\n' https://studiosaas.cc.cd/register   # 404（有意关闭）
```

- [ ] `/platform-admin` 应用登录成功且已轮换密码；`/super-admin` Access 双重验证别名可用
- [ ] `/<slug>` 门户、`/<slug>/register`、`/<slug>/cms`、`/<slug>/studio-admin` 均 200
- [ ] 手机 4G 提交一条真实注册 → CMS 待审列表可见
- [ ] CMS 上传照片 → 媒体 volume 中出现文件
- [ ] session cookie 带 `Secure`（`curl -I` 检查 `Set-Cookie`）
- [ ] RDS 自动快照开启
- [ ] 逻辑备份 cron 已装（见下）且 dry-run 还原演练通过一次
- [ ] 卷快照策略已建（见下）——**媒体照片与归档快照不在 pg_dump 里**
- [ ] CloudWatch 三条最低告警：EC2 StatusCheckFailed、RDS FreeStorageSpace
      < 2GB、RDS CPUUtilization > 90%（15 分钟）；外部拨测 `/v1/health`
- [ ] 事件表保留清理已排期（月度）：
      `docker compose ... exec app python scripts/prune_event_tables.py`

## 9. 备份（正式部署必装，非可选）

**9.1 数据库逻辑备份**（RDS 快照之外的可下载、可演练副本）。镜像已内置
`pg_dump`（postgresql-client），备份写到 `/data`（持久卷）并自动 0600 +
保留 14 份：

```bash
# /etc/cron.d/studiosaas-backup —— 每日 03:15
15 3 * * * ubuntu cd /home/ubuntu/PWE-StudioSaaS-aws-* && \
  docker compose -f deploy/aws/docker-compose.yml exec -T app \
  python scripts/backup_postgres.py backup --backup-dir /data/backups/postgres \
  >> /var/log/studiosaas-backup.log 2>&1
```

可选异地副本（强烈建议）：紧接一行 `aws s3 sync /var/lib/docker/volumes/…`
不可直取 volume 路径时，用
`docker compose ... exec -T app tar -C /data/backups -cz postgres | aws s3 cp - s3://<bucket>/db/$(date +%F).tar.gz`。

**9.2 卷备份（照片/归档/租户工作区）** —— 二选一：

- **EBS 快照（推荐）**：AWS 控制台 → Lifecycle Manager (DLM) → 为 EC2 根卷
  建每日快照策略，保留 7 天。一条策略同时覆盖 /data、/media、/archives、
  /tenants 四个 docker volume（都在根卷上）。
- **tar-to-S3 cron**：
  ```bash
  30 3 * * * ubuntu docker run --rm \
    -v aws_studiosaas-media:/media:ro -v aws_studiosaas-data:/data:ro \
    -v aws_studiosaas-archives:/archives:ro alpine \
    tar -cz /media /data /archives | aws s3 cp - s3://<bucket>/volumes/$(date +\%F).tar.gz
  ```

**9.3 还原演练**（每季度一次，或换机前）：

```bash
docker compose -f deploy/aws/docker-compose.yml exec app \
  python scripts/backup_postgres.py restore-dry-run /data/backups/postgres/<dump>
```
