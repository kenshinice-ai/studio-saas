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
bash deploy/aws/build_aws_bundle.sh 7.4.0
# → dist/PWE-StudioSaaS-aws-7.4.0.tar.gz (+ .sha256)
```

要求 git 工作树干净；bundle 内含 `BUILD_INFO`（版本 + commit + 构建时间）。
上传到 EC2：

```bash
scp dist/PWE-StudioSaaS-aws-7.4.0.tar.gz ubuntu@<EC2_IP>:~
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

## 3. 路径 A — Docker（推荐）

```bash
# EC2 上（一次性）：安装 docker
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-v2 nginx
sudo usermod -aG docker ubuntu && newgrp docker

# 解包
tar xzf PWE-StudioSaaS-aws-7.4.0.tar.gz && cd PWE-StudioSaaS-aws-7.4.0

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
sudo mkdir -p /opt/studiosaas/{app,data,media}
sudo tar xzf ~/PWE-StudioSaaS-aws-7.4.0.tar.gz --strip-components=1 -C /opt/studiosaas/app
cd /opt/studiosaas
sudo python3 -m venv venv && sudo ./venv/bin/pip install -r app/backend/requirements.txt

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

```bash
sudo cp deploy/aws/nginx/studiosaas.conf /etc/nginx/sites-available/studiosaas
sudo ln -s /etc/nginx/sites-available/studiosaas /etc/nginx/sites-enabled/
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d studiosaas.cc.cd     # 或使用 Cloudflare Origin Cert
sudo nginx -t && sudo systemctl reload nginx
```

应用只信任来自 localhost 的代理头（`_client_ip()`），与「nginx 与应用同机」
的拓扑天然匹配——不要把 8899 暴露到公网安全组。

## 7. 数据迁移（本地试点 → AWS）

```bash
# 本地
pg_dump "postgresql://$USER@localhost:5432/studiosaas_local_test" \
  --no-owner --no-privileges -Fc -f studiosaas.dump
# EC2（能到达 RDS）
pg_restore --no-owner --no-privileges -d "$STUDIOSAAS_DATABASE_URL" studiosaas.dump

# 媒体（Docker 路径：先拷进 volume）
docker cp media/. $(docker compose -f deploy/aws/docker-compose.yml ps -q app):/media/
```

迁移窗口内冻结本地写入；DNS 切换后保留 tunnel 48h 作回滚。

## 8. 部署后验证清单

```bash
curl -fsS https://studiosaas.cc.cd/v1/health          # {"ok":true,...}
curl -fsS -o /dev/null -w '%{http_code}\n' https://studiosaas.cc.cd/register   # 404（有意关闭）
```

- [ ] `/super-admin` 登录成功且已轮换密码
- [ ] `/<slug>` 门户、`/<slug>/register`、`/<slug>/cms`、`/<slug>/studio-admin` 均 200
- [ ] 手机 4G 提交一条真实注册 → CMS 待审列表可见
- [ ] CMS 上传照片 → 媒体 volume 中出现文件
- [ ] session cookie 带 `Secure`（`curl -I` 检查 `Set-Cookie`）
- [ ] RDS 自动快照开启；`BACKUP_STUDIOSAAS_NOW` 等价物：`pg_dump` cron（见 docs/Deployment.md §3.2）
