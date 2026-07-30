# StudioSaaS — AWS 部署包说明 (Stage 2)

本目录是随代码一起发布的 AWS 部署套件。目标架构与成本估算见
`docs/Deployment.md` §3。生产有两条明确路径：RDS PostgreSQL，或
`pwestudio.online` 首发采用的 Lightsail 单机 PostgreSQL 拓扑。

```
deploy/aws/
├── README_AWS.md          # 本文（打包后复制为 bundle 根部的 DEPLOY_AWS_FIRST.md）
├── Dockerfile             # 生产镜像（python:3.11-slim + waitress）
├── entrypoint.sh          # 等库 → 迁移 → 启动；生产模式强制校验 secrets
├── docker-compose.yml     # Docker 路径；`--profile local-db` 可单机彩排
├── docker-compose.lightsail.yml # Lightsail 单机生产覆盖层
├── lightsail.env.example  # pwestudio.online 单机生产变量模板
├── lightsail_ctl.sh       # 稳定项目名、备份、状态与安全停机命令
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
| DNS | `pwestudio.online` → Lightsail 固定 IP | 主链路不依赖 Cloudflare Tunnel |

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

### 3.1 pwestudio.online 的 Lightsail 单机生产路径

首发实例为 2 GB RAM / 2 vCPU / 60 GB SSD，应用与 PostgreSQL 16 同机。
这是有意的低成本首发拓扑，不是 RDS 等价物：必须同时启用每日逻辑备份、
Lightsail 自动快照和季度还原演练，增长后再迁移 RDS。

```bash
sudo mkdir -p /opt/pwestudio/{releases,shared,backups/postgres}
sudo chown -R ubuntu:ubuntu /opt/pwestudio

cp deploy/aws/lightsail.env.example /opt/pwestudio/shared/production.env
chmod 600 /opt/pwestudio/shared/production.env
# 替换四个 CHANGE_ME；每个值分别运行一次 openssl rand -hex 32

bash deploy/aws/lightsail_ctl.sh up
bash deploy/aws/lightsail_ctl.sh status
bash deploy/aws/lightsail_ctl.sh backup
```

升级时始终使用 Compose 项目名 `pwestudio`，并让
`/opt/pwestudio/current` 指向当前解包目录。禁止运行
`docker compose down -v`；它会删除 PostgreSQL 和媒体数据卷。

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

# 2) 先用 --staging 验一次 HTTP-01 链路，不消耗正式配额
sudo apt-get install -y certbot
sudo certbot certonly --webroot -w /var/www/html \
    -d pwestudio.online -d www.pwestudio.online \
    --staging --non-interactive --agree-tos --email <ops@…> --cert-name pwestudio-staging

# 3) 通过后删掉 staging，签正式证书（apex + www 同一 lineage）
sudo certbot delete --cert-name pwestudio-staging --non-interactive
sudo certbot certonly --webroot -w /var/www/html \
    -d pwestudio.online -d www.pwestudio.online \
    --non-interactive --agree-tos --email <ops@…> --cert-name pwestudio.online

# 4) 切到含 TLS 的正式配置
sudo cp deploy/aws/nginx/studiosaas.conf /etc/nginx/sites-available/studiosaas
sudo nginx -t && sudo systemctl reload nginx
```

**为什么用 `certonly --webroot` 而不是 `--nginx`**：两份配置都把
`/.well-known/acme-challenge/` 交给 nginx 自己从 webroot 应答，而不是反代给
应用。否则续期会依赖应用健康——证书恰好在你最需要它的那次故障中过期。
`--staging` 一步是因为 Let's Encrypt 每周限 5 张同名证书，链路配错时不该
拿正式配额去试。

**www 必须先有 A 记录**：HTTP-01 会逐个域名验证，`www` 无解析则整张证书失败。

`studiosaas.conf` 是完整参考（server_tokens off、gzip、20m 上传上限、HSTS）。
走 Cloudflare 橙云的部署可跳过 certbot，用 Origin Cert 直接填入。**首发的
pwestudio.online 不走 Cloudflare**：有固定 IP + Route 53 时，tunnel 只是多一
跳、多一份凭据，并与 certbot HTTP-01 争同一主机名。

应用只信任来自 localhost 的代理头（`_client_ip()`），与「nginx 与应用同机」
的拓扑天然匹配——不要把 8899 暴露到公网安全组。

### 6.1 共享 TLS 参数

`deploy/aws/nginx/pwestudio-tls.conf` 装到 `/etc/nginx/snippets/`，被 apex 与
www 两个 443 块同时 `include`。加固过的 apex 旁边放一个默认配置的 www 块，
等于留了一条明面上的降级路径。TLS 1.2 只留前向保密的 AEAD 套件（无 CBC、
无 RSA 密钥交换、无 3DES）；session 缓存开，ticket 关。

### 6.2 不要开 OCSP stapling

Let's Encrypt 的证书 AIA 里只有 `CA Issuers - URI:http://ye1.i.lencr.org/`、
**没有 OCSP responder URL**（OCSP 已被短有效期 + CRL 取代）。此时
`ssl_stapling on` 会被 nginx 接受、然后每次 reload 打印
`"ssl_stapling" ignored, no OCSP responder URL in the certificate` ——
一个长期存在的警告会训练运维忽略 reload 输出，而真正的错误恰好出现在那里。
续期后可复验：

```bash
openssl s_client -connect pwestudio.online:443 -servername pwestudio.online \
  </dev/null 2>/dev/null | openssl x509 -noout -ocsp_uri     # 应为空
```

### 6.3 安全头归属：应用发内容策略，nginx 只发 HSTS

`backend/server.py:777-796` 已在每个响应上发完整 CSP、X-Frame-Options、
Permissions-Policy、Referrer-Policy、X-Content-Type-Options。nginx 曾重复发其中
两个，线上出现重复头。现在 nginx **只**发 HSTS —— 因为它还要覆盖应用没有产生
的响应：容器重启时 nginx 自己的 502，恰恰是最不该提供降级选项的时刻。

### 6.4 nginx 版本约束

Ubuntu 24.04 是 nginx 1.24，HTTP/2 是 `listen` 参数；1.25+ 的 `http2 on;`
指令在这里 `nginx -t` 会失败（已被配置测试挡在 reload 之前，线上未受影响）。

### 6.5 维护页

502/503/504 走 `/var/www/pwestudio/__maintenance.html`（品牌化、`internal`、
`no-store`、`Retry-After: 30`）。升级会让容器重启几秒，nginx 原生的
「502 Bad Gateway」看起来像网站坏了，而不是在更新。

### 6.6 从开发机操作线上实例

`deploy/aws/pwestudio_remote.sh` 是笔记本这一侧，**不含任何凭据**；接入靠
`~/.ssh/config` 的 `Host pwestudio` 别名，私钥放 `~/.ssh/`。

> **不要把私钥放在 iCloud 同步目录里**：那里保不住 mode 600（ssh 会直接拒绝
> 使用），而且同步过的私钥是一份你控制不了的副本。

所有触碰生产数据的动作都委派给实例上的 `lightsail_ctl.sh`，笔记本永远不是
生产流程的事实来源，两边也就不会各自漂移。

```bash
bash deploy/aws/pwestudio_remote.sh status    # 容器 + deep health
bash deploy/aws/pwestudio_remote.sh health    # 公网 HTTPS / DNS / 证书 / 跳转
bash deploy/aws/pwestudio_remote.sh backups   # 磁盘上有什么 + cron 日志
bash deploy/aws/pwestudio_remote.sh backup    # 立刻备份
bash deploy/aws/pwestudio_remote.sh drill     # 恢复演练（安全）
bash deploy/aws/pwestudio_remote.sh certs     # 到期时间 + 续期 timer
bash deploy/aws/pwestudio_remote.sh deploy dist/PWE-StudioSaaS-aws-<ver>.tar.gz
bash deploy/aws/pwestudio_remote.sh ssh
```

`deploy` 会在上传前拒掉 `mode=standalone` 的包（装到 SaaS 主机上会在软链已经
切过去之后才拒绝启动）、先备份、失败时**自动把 `current` 软链回滚**并复验健康。
删卷 / 删库 / 真实恢复这类命令故意不在这里，它们留在实例上，运维能在上下文里
读到确认提示。

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
curl -fsS https://pwestudio.online/v1/health          # {"ok":true,...}
curl -fsS -o /dev/null -w '%{http_code}\n' https://pwestudio.online/register   # 404（有意关闭）
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

**9.1 数据库逻辑备份**（RDS 快照之外的可下载、可演练副本）。镜像内置的
`pg_dump` **主版本必须与服务端一致**（Dockerfile 的 `ARG PG_MAJOR`，当前 16）；
不钉版本会拿到 17 客户端，而 17 的 `pg_restore` 会发 PG17 才有的
`SET transaction_timeout = 0`，PG16 服务端拒收——**日常 dump 看起来正常，
还原演练永远失败**。换服务端大版本时同一个改动里 bump `PG_MAJOR`。

脚本在镜像里的路径是 **`backend/scripts/backup_postgres.py`**（WORKDIR 是
`/app`）。写成 `scripts/backup_postgres.py` 的 cron 会每天静默失败。

备份目录是主机绑定挂载，属主必须是镜像用户 **uid 10001**、组给运维用户、
模式 2750，否则 `pg_dump` 在一个「看起来存在且可写」的目录上拿到
Permission denied。`lightsail_ctl.sh` 每次运行都断言这件事，不依赖安装时的
一次性 chown。

Lightsail 单机路径直接用控制脚本（已包含上面三点）：

```bash
# /etc/cron.d/pwestudio-backup —— 每日 03:15 UTC，root
15 3 * * * root cd /opt/pwestudio/current && \
  bash deploy/aws/lightsail_ctl.sh backup >> /var/log/pwestudio-backup.log 2>&1
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
# Lightsail 单机：一条命令，自动取最新 dump
bash deploy/aws/lightsail_ctl.sh restore-dry-run
# 或指定
bash deploy/aws/lightsail_ctl.sh restore-dry-run --dump <file>
```

演练会建一个临时库再删掉，因此需要 **owner 角色**（运行时角色
`studiosaas_app` 故意没有 createdb）。控制脚本只为这一条命令注入 owner URL，
应用进程始终看不到它。

**通过的标准是 `"ok": true` 且 `critical_counts` 与 manifest 一致** —— 不是
「dump 文件存在」。恢复演练是唯一能证明备份可用的动作。

**迁移媒体后必跑**：还原数据库而媒体树不完整（或来自另一套安装）会留下
「variant 行在、文件不在」的状态，公开面每个 logo 都 404。
`backend/scripts/backfill_media_variants.py --check` 会校验**文件**而非只看行。
